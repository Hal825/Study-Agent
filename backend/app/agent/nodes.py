"""
Agent 图节点实现。

每个节点函数签名: (state: NoteAgentState) → dict[str, Any]
返回的 dict 会被 LangGraph 合并回 state。
"""

import logging
from typing import Any

from app.agent.state import NoteAgentState
from app.tools.content_parser import ContentParserInput
from app.tools.entity_extractor import EntityExtractorInput
from app.tools.structure_analyzer import StructureAnalyzerInput
from app.tools.interfaces import IToolRegistry
from app.services.llm_service import LLMService, LLMRequest

logger = logging.getLogger("agent.nodes")

# 阶段名称映射（用于 SSE 推送）
STAGE_LABELS = {
    "parse": "读取并理解内容...",
    "extract": "提取关键知识点...",
    "analyze": "分析内容结构...",
    "confirm": "等待确认模板...",
    "generate": "生成笔记内容...",
}


def _get_tool(tool_registry: IToolRegistry, name: str):
    """从注册中心获取 Tool，不存在则抛异常。"""
    tool = tool_registry.get(name)
    if tool is None:
        raise RuntimeError(f"Tool [{name}] 未在 ToolRegistry 中注册")
    return tool


# ============================================================
# 节点函数
# ============================================================

async def parse_content_node(state: NoteAgentState) -> dict[str, Any]:
    """
    节点 1：解析用户上传的内容。

    调用 ContentParser 工具，提取标题、章节、字数、语言。
    """
    logger.info(f"[{state.get('session_id', '')}] parse_content 开始")

    parser = _get_tool(_tool_registry, "content_parser")  # type: ignore[name-defined]
    result = await parser.run(ContentParserInput(
        content=state["content"],
        filename="",
    ))

    if not result.ok:
        return {"stage": "parse", "error": f"内容解析失败: {result.error}"}

    data = result.data
    return {
        "stage": "parse",
        "parsed_title": data.title,
        "parsed_sections": [
            {"heading": s.get("heading", ""), "level": s.get("level", 1),
             "content": s.get("content", ""), "start_line": s.get("start_line", 0)}
            for s in data.sections
        ],
        "parsed_total_words": data.total_words,
        "parsed_language": data.language,
    }


async def extract_entities_node(state: NoteAgentState) -> dict[str, Any]:
    """
    节点 2：提取知识实体。

    调用 EntityExtractor（LLM 驱动），从内容中识别概念、术语、关联。
    """
    logger.info(f"[{state.get('session_id', '')}] extract_entities 开始")

    extractor = _get_tool(_tool_registry, "entity_extractor")  # type: ignore[name-defined]
    result = await extractor.run(EntityExtractorInput(
        content=state["content"],
        sections=state.get("parsed_sections", []),
        max_entities=20,
    ))

    if not result.ok:
        return {"stage": "extract", "error": f"实体提取失败: {result.error}"}

    data = result.data
    return {
        "stage": "extract",
        "entities": [
            {"name": e.name, "category": e.category, "importance": e.importance,
             "context": e.context, "related": e.related}
            for e in data.entities
        ],
        "key_concepts": data.key_concepts,
    }


async def analyze_structure_node(state: NoteAgentState) -> dict[str, Any]:
    """
    节点 3：分析内容结构。

    调用 StructureAnalyzer（混合模式），
    生成内容类型判断、核心主题、建议大纲。
    """
    logger.info(f"[{state.get('session_id', '')}] analyze_structure 开始")

    analyzer = _get_tool(_tool_registry, "structure_analyzer")  # type: ignore[name-defined]
    result = await analyzer.run(StructureAnalyzerInput(
        content=state["content"],
        sections=state.get("parsed_sections", []),
        total_words=state.get("parsed_total_words", 0),
    ))

    if not result.ok:
        return {"stage": "analyze", "error": f"结构分析失败: {result.error}"}

    data = result.data
    return {
        "stage": "analyze",
        "content_type": data.content_type,
        "hierarchy_depth": data.hierarchy_depth,
        "main_topics": [
            {"name": t.name, "coverage": t.coverage, "subtopics": t.subtopics}
            for t in data.main_topics
        ],
        "suggested_outline": [
            {"heading": o.heading, "level": o.level, "key_points": o.key_points}
            for o in data.suggested_outline
        ],
        "complexity": data.complexity,
        "estimated_study_time_minutes": data.estimated_study_time_minutes,
    }


async def confirm_template_node(state: NoteAgentState) -> dict[str, Any]:
    """
    节点 4：等待用户确认模板选择。

    此节点使用 LangGraph interrupt() 暂停执行，
    等待前端发送用户确认后再继续。

    实际 interrupt 逻辑在 graph.py 中通过 interrupt_before 配置。
    """
    logger.info(
        f"[{state.get('session_id', '')}] confirm_template: "
        f"template={state.get('template_id', '')}"
    )
    return {"stage": "confirm", "human_confirmed": True}


async def generate_note_node(state: NoteAgentState) -> dict[str, Any]:
    """
    节点 5：生成最终笔记。

    整合所有中间结果 + 用户选择的模板 Prompt → LLM 生成笔记。
    """
    logger.info(f"[{state.get('session_id', '')}] generate_note 开始")

    llm: LLMService = _llm_service  # type: ignore[name-defined]
    template_id = state["template_id"]

    # 获取模板 prompt
    from app.prompts.note import NOTE_PROMPTS
    system_prompt = NOTE_PROMPTS.get(template_id, NOTE_PROMPTS.get("outline", ""))

    # 构建丰富的用户消息：注入解析后的结构化上下文
    user_message = _build_enriched_user_message(state)

    # 调用 LLM
    response = await llm.generate(
        LLMRequest(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.7,
            max_tokens=4096,
        )
    )

    return {
        "stage": "generate",
        "generated_note": response.content,
    }


# ============================================================
# 辅助函数
# ============================================================

def _build_enriched_user_message(state: NoteAgentState) -> str:
    """
    从 state 的各中间字段构建增强版用户消息。

    把 Tool 的产出（实体、大纲、复杂度）作为上下文注入，
    让 LLM 在生成笔记时有更结构化的参考信息。
    """
    parts: list[str] = []

    # 1. 原始内容
    parts.append(f"## 原始学习内容\n\n{state['content']}")

    # 2. 章节结构摘要
    sections = state.get("parsed_sections", [])
    if sections:
        parts.append("\n## 内容结构\n")
        for s in sections[:10]:
            prefix = "#" * s.get("level", 1)
            parts.append(f"{prefix} {s.get('heading', '')}")

    # 3. 关键概念
    key_concepts = state.get("key_concepts", [])
    if key_concepts:
        parts.append(f"\n## 已识别的核心概念\n")
        parts.append("、".join(key_concepts))

    # 4. 建议大纲
    outline = state.get("suggested_outline", [])
    if outline:
        parts.append("\n## 建议的笔记大纲\n")
        for item in outline[:8]:
            indent = "  " * (item.get("level", 1) - 1)
            parts.append(f"{indent}- {item.get('heading', '')}")

    # 5. 元信息
    parts.append(f"\n内容类型: {state.get('content_type', 'unknown')}")
    parts.append(f"复杂度: {state.get('complexity', 'medium')}")
    parts.append(f"预估学习时间: {state.get('estimated_study_time_minutes', 30)} 分钟")
    parts.append(f"语言: {state.get('parsed_language', 'zh')}")

    return "\n".join(parts)


# ============================================================
# 模块级依赖注入（由 executor 在初始化时设置）
# ============================================================

_tool_registry: IToolRegistry | None = None
_llm_service: LLMService | None = None


def inject_dependencies(tool_registry: IToolRegistry, llm_service: LLMService) -> None:
    """注入 Tool Registry 和 LLM Service（在 AgentExecutor 初始化时调用）。"""
    global _tool_registry, _llm_service
    _tool_registry = tool_registry
    _llm_service = llm_service
