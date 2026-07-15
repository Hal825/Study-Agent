"""
Chat Agent 图定义 —— 对话式笔记生成的状态图。

图结构：
    START → analyze → present_design → generate_note → present_result → handle_revision → END
                            ↑                ↑                ↑                  │
                       [interrupt]           │                │      (if revision) │
                                             └────────────────┴────────────────────┘

- present_design: interrupt_before，等待用户确认设计框架
- present_result: interrupt_before，等待用户确认或请求修订
- handle_revision: 如果有修订请求，回环到 generate_note
"""

import logging
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.chat_state import ChatAgentState

logger = logging.getLogger("agent.chat_graph")

# 模块级依赖注入（由 chat_executor 初始化时设置）
_tool_registry = None
_llm_service = None
_prompt_registry = None


def inject_chat_dependencies(tool_registry, llm_service, prompt_registry) -> None:
    """注入 Tool Registry、LLM Service 和 Prompt Registry。"""
    global _tool_registry, _llm_service, _prompt_registry
    _tool_registry = tool_registry
    _llm_service = llm_service
    _prompt_registry = prompt_registry


# ============================================================
# 节点函数
# ============================================================

async def analyze_node(state: ChatAgentState) -> dict[str, Any]:
    """
    节点 1：分析用户上传的内容。

    运行 ContentParser → EntityExtractor → StructureAnalyzer，
    将所有分析结果写入 state。
    """
    session_id = state.get("session_id", "")
    logger.info(f"[{session_id}] analyze_node 开始")

    content = state.get("content", "")
    if not content.strip():
        return {"phase": "analyzing", "error": "内容为空"}

    from app.tools.content_parser import ContentParserInput
    from app.tools.entity_extractor import EntityExtractorInput
    from app.tools.structure_analyzer import StructureAnalyzerInput

    updates: dict[str, Any] = {"phase": "analyzing"}

    # --- 1. ContentParser ---
    parser = _tool_registry.get("content_parser")
    if parser:
        result = await parser.run(ContentParserInput(content=content, filename=""))
        if result.ok:
            data = result.data
            updates["parsed_title"] = data.title
            updates["parsed_sections"] = [
                {"heading": s.get("heading", ""), "level": s.get("level", 1),
                 "content": s.get("content", ""), "start_line": s.get("start_line", 0)}
                for s in data.sections
            ]
            updates["parsed_total_words"] = data.total_words
            updates["parsed_language"] = data.language
            logger.info(f"[{session_id}] ContentParser 完成: {data.total_words} 字, {data.language}")
        else:
            logger.warning(f"[{session_id}] ContentParser 失败: {result.error}")
    else:
        logger.warning(f"[{session_id}] ContentParser 未注册")

    # --- 2. EntityExtractor ---
    extractor = _tool_registry.get("entity_extractor")
    if extractor:
        result = await extractor.run(EntityExtractorInput(
            content=content,
            sections=updates.get("parsed_sections", []),
            max_entities=20,
        ))
        if result.ok:
            data = result.data
            updates["entities"] = [
                {"name": e.name, "category": e.category, "importance": e.importance,
                 "context": e.context, "related": e.related}
                for e in data.entities
            ]
            updates["key_concepts"] = data.key_concepts
            logger.info(f"[{session_id}] EntityExtractor 完成: {len(data.entities)} 实体")
        else:
            logger.warning(f"[{session_id}] EntityExtractor 失败: {result.error}")
    else:
        logger.warning(f"[{session_id}] EntityExtractor 未注册")

    # --- 3. StructureAnalyzer ---
    analyzer = _tool_registry.get("structure_analyzer")
    if analyzer:
        result = await analyzer.run(StructureAnalyzerInput(
            content=content,
            sections=updates.get("parsed_sections", []),
            total_words=updates.get("parsed_total_words", 0),
        ))
        if result.ok:
            data = result.data
            updates["content_type"] = data.content_type
            updates["hierarchy_depth"] = data.hierarchy_depth
            updates["main_topics"] = [
                {"name": t.name, "coverage": t.coverage, "subtopics": t.subtopics}
                for t in data.main_topics
            ]
            updates["suggested_outline"] = [
                {"heading": o.heading, "level": o.level, "key_points": o.key_points}
                for o in data.suggested_outline
            ]
            updates["complexity"] = data.complexity
            updates["estimated_study_time_minutes"] = data.estimated_study_time_minutes
            logger.info(f"[{session_id}] StructureAnalyzer 完成: {data.content_type}")
        else:
            logger.warning(f"[{session_id}] StructureAnalyzer 失败: {result.error}")
    else:
        logger.warning(f"[{session_id}] StructureAnalyzer 未注册")

    # 确保有默认值
    updates.setdefault("key_concepts", [])
    updates.setdefault("main_topics", [])
    updates.setdefault("suggested_outline", [])
    updates.setdefault("parsed_sections", [])
    updates.setdefault("parsed_title", "")
    updates.setdefault("parsed_total_words", 0)
    updates.setdefault("parsed_language", "zh")
    updates.setdefault("content_type", "unknown")
    updates.setdefault("complexity", "medium")
    updates.setdefault("estimated_study_time_minutes", 30)
    updates.setdefault("revision_count", 0)

    return updates


async def present_design_node(state: ChatAgentState) -> dict[str, Any]:
    """
    节点 2：生成并展示设计框架。

    调用 LLM 生成设计框架（知识主题、格式建议、个性化选项），
    包含在 state 中供 chat_executor 读取并发送 SSE 事件。

    此节点执行前 graph 会中断（interrupt_before），
    chat_executor 在 run_stream 中先执行到此节点、
    发送事件后再暂停，等待用户确认。
    """
    session_id = state.get("session_id", "")
    logger.info(f"[{session_id}] present_design_node: template={state.get('selected_template', '未选择')}")

    # 构建设计框架的数据结构（由 LLM 生成）
    design_framework = {
        "content_summary": f"内容类型为 {state.get('content_type', '未知')}，"
                           f"复杂度 {state.get('complexity', '中等')}，"
                           f"共 {state.get('parsed_total_words', 0)} 字",
        "topics": [
            {
                "name": t.get("name", ""),
                "coverage": t.get("coverage", ""),
                "subtopics": t.get("subtopics", []),
            }
            for t in state.get("main_topics", [])[:5]
        ],
        "suggested_format": state.get("selected_template", "outline"),
        "format_reasoning": "",
        "alternative_formats": ["summary", "cornell", "qa"],
        "formatting_suggestions": [
            "使用多级标题组织知识结构",
            "加粗关键术语和重要概念",
            "使用列表整理并列知识点",
        ],
        "user_prompts": [
            "你想重点关注哪些主题？有哪些主题可以略过？",
            "你是否希望添加学习批注和复习提示？",
            "你是否希望使用颜色强调来区分不同类型的知识点？",
        ],
    }

    return {
        "phase": "design",
        "human_confirmed": True,
        # 存储设计框架到 state（供 executor 读取并注入 SSE 事件）
        "_design_framework_cache": design_framework,
    }


async def generate_note_node(state: ChatAgentState) -> dict[str, Any]:
    """
    节点 3：根据用户偏好生成笔记。

    将分析结果 + 用户偏好 + 模板 prompt 组合，
    调用 LLM 生成最终笔记。
    流式输出由 chat_executor 通过回调处理。
    """
    session_id = state.get("session_id", "")
    template_id = state.get("selected_template", "outline")
    logger.info(f"[{session_id}] generate_note_node: template={template_id}, "
                f"revision={state.get('revision_count', 0)}")

    from app.prompts.note import NOTE_PROMPTS
    from app.services.llm_service import LLMRequest

    # 如果是修订，使用修订 prompt
    revision_request = state.get("revision_request", "")
    if revision_request and state.get("revision_count", 0) > 0:
        revision_template = _load_revision_prompt()
        system_prompt = revision_template
        user_message = _build_revision_user_message(state)
    else:
        system_prompt = NOTE_PROMPTS.get(template_id, NOTE_PROMPTS.get("outline", ""))
        user_message = _build_enriched_user_message(state)

    # 调用 LLM 生成（非流式，流式在 executor 层处理）
    response = await _llm_service.generate(
        LLMRequest(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.7,
            max_tokens=4096,
        )
    )

    return {
        "phase": "generating",
        "generated_note": response.content,
    }


async def present_result_node(state: ChatAgentState) -> dict[str, Any]:
    """
    节点 4：展示结果，等待用户反馈。

    此节点执行前 graph 会中断（interrupt_before），
    等待用户确认满意或请求修改。
    """
    session_id = state.get("session_id", "")
    generated = state.get("generated_note", "")
    logger.info(f"[{session_id}] present_result_node: 笔记长度={len(generated)}")

    return {
        "phase": "result",
        "human_confirmed": True,
    }


async def handle_revision_node(state: ChatAgentState) -> dict[str, Any]:
    """
    节点 5：处理修订请求。

    如果用户请求了修订，增加计数并路由回 generate_note。
    否则标记为完成。
    """
    session_id = state.get("session_id", "")
    revision = state.get("revision_request", "")

    if revision.strip():
        count = state.get("revision_count", 0) + 1
        logger.info(f"[{session_id}] handle_revision: 第 {count} 次修订 -> 重新生成")
        return {
            "phase": "revising",
            "revision_count": count,
        }
    else:
        logger.info(f"[{session_id}] handle_revision: 无修订请求，完成")
        return {
            "phase": "done",
        }


# ============================================================
# 条件路由
# ============================================================

def _should_revise(state: ChatAgentState) -> str:
    """判断是否需要修订循环。"""
    if state.get("revision_request", "").strip():
        return "generate_note"
    return END


# ============================================================
# 图构建
# ============================================================

def build_chat_graph() -> StateGraph:
    """
    构建对话式笔记生成的 LangGraph 状态图。

    图结构：
        START → analyze → present_design → generate_note → present_result → handle_revision
                                ↑                ↑              │                  │
                           [interrupt]           │              │       (revise)   │
                                                 └──────────────┴──────────────────┘
                                                                         │ (done)
                                                                         END

    Returns:
        已编译的 CompiledStateGraph
    """
    builder = StateGraph(ChatAgentState)

    # 添加节点
    builder.add_node("analyze", analyze_node)
    builder.add_node("present_design", present_design_node)
    builder.add_node("generate_note", generate_note_node)
    builder.add_node("present_result", present_result_node)
    builder.add_node("handle_revision", handle_revision_node)

    # 连线
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "present_design")
    builder.add_edge("present_design", "generate_note")
    builder.add_edge("generate_note", "present_result")
    builder.add_edge("present_result", "handle_revision")

    # 条件路由：修订 → 回到 generate_note，否则 → END
    builder.add_conditional_edges(
        "handle_revision",
        _should_revise,
        {
            "generate_note": "generate_note",
            END: END,
        },
    )

    # 编译图（开发环境用 MemorySaver）
    checkpointer = MemorySaver()
    compiled = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["present_design", "present_result"],
    )

    return compiled


# ============================================================
# 辅助函数
# ============================================================

def _build_enriched_user_message(state: ChatAgentState) -> str:
    """构建增强版用户消息，注入分析结果和用户偏好。"""
    parts: list[str] = []

    # 1. 原始内容
    parts.append(f"## 原始学习内容\n\n{state.get('content', '')}")

    # 2. 用户偏好（如果有）
    selected_topics = state.get("selected_topics", [])
    if selected_topics:
        parts.append(f"\n## 用户希望重点关注的方面\n")
        parts.append("重点关注以下主题：" + "、".join(selected_topics))

    if state.get("enable_annotations"):
        parts.append("\n请在学习笔记中添加**学习批注**，提示读者注意重点和易错点。")

    if state.get("enable_color_emphasis"):
        parts.append("\n请使用符号标注不同概念的重要性（如 ⭐ 表示核心概念）。")

    format_mods = state.get("format_modifications", "")
    if format_mods:
        parts.append(f"\n用户格式要求：{format_mods}")

    custom = state.get("custom_instructions", "")
    if custom:
        parts.append(f"\n用户额外说明：{custom}")

    # 3. 章节结构摘要
    sections = state.get("parsed_sections", [])
    if sections:
        parts.append("\n## 内容结构\n")
        for s in sections[:10]:
            prefix = "#" * s.get("level", 1)
            parts.append(f"{prefix} {s.get('heading', '')}")

    # 4. 关键概念
    key_concepts = state.get("key_concepts", [])
    if key_concepts:
        parts.append("\n## 已识别的核心概念\n")
        parts.append("、".join(key_concepts))

    # 5. 建议大纲
    outline = state.get("suggested_outline", [])
    if outline:
        parts.append("\n## 建议的笔记大纲\n")
        for item in outline[:8]:
            indent = "  " * (item.get("level", 1) - 1)
            parts.append(f"{indent}- {item.get('heading', '')}")

    # 6. 元信息
    parts.append(f"\n内容类型: {state.get('content_type', 'unknown')}")
    parts.append(f"复杂度: {state.get('complexity', 'medium')}")
    parts.append(f"预估学习时间: {state.get('estimated_study_time_minutes', 30)} 分钟")
    parts.append(f"语言: {state.get('parsed_language', 'zh')}")

    return "\n".join(parts)


def _build_revision_user_message(state: ChatAgentState) -> str:
    """构建修订请求的用户消息。"""
    parts: list[str] = []

    parts.append(f"## 原始学习内容\n\n{state.get('content', '')}")
    parts.append(f"\n## 之前的笔记\n\n{state.get('generated_note', '')}")
    parts.append(f"\n## 用户的修改要求\n\n{state.get('revision_request', '')}")
    parts.append(f"\n这是第 {state.get('revision_count', 0)} 次修改。")

    if state.get("enable_annotations"):
        parts.append("\n请保持学习批注。")
    if state.get("enable_color_emphasis"):
        parts.append("\n请保持颜色/符号强调标注。")

    return "\n".join(parts)


def _load_revision_prompt() -> str:
    """加载修订 prompt 模板。"""
    if _prompt_registry:
        try:
            template = _prompt_registry.get("chat/revision")
            if template:
                return template.content
        except Exception:
            pass

    # 回退到内置 prompt
    return """你是一位专业的学习笔记编辑。根据用户的修改要求重新生成笔记。

修改要求：{revision_request}

请直接输出修改后的完整 Markdown 笔记（不要包含解释性文字）。
注意：
1. 只修改用户要求的部分，保留其他内容不变
2. 如果用户要求"展开某部分"，请增加细节
3. 如果用户要求"更换格式"，请完全重新组织
4. 保持高质量的中文输出"""
