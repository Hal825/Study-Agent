"""
笔记生成 Skill —— 编排 ContentParser → EntityExtractor → StructureAnalyzer → LLM。

将原有 agent/nodes.py 的 5 个节点函数迁移为 Skill 内部方法，
消除 Agent → Tool 的直接依赖。
"""

import logging
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import NoteAgentState
from app.skills.base import BaseSkill, SkillContext, SkillResult
from app.tools.content_parser import ContentParserInput
from app.tools.entity_extractor import EntityExtractorInput
from app.tools.structure_analyzer import StructureAnalyzerInput
from app.services.llm_service import LLMRequest

logger = logging.getLogger("skills.note_gen")

STAGE_LABELS = {
    "parse": "读取并理解内容...",
    "extract": "提取关键知识点...",
    "analyze": "分析内容结构...",
    "confirm": "等待确认模板...",
    "generate": "生成笔记内容...",
}


class NoteGenerationSkill(BaseSkill):
    """
    笔记生成技能。

    流水线: parse → extract → analyze → confirm → generate
    - parse:    纯本地解析，提取章节/字数/语言
    - extract:  LLM 提取知识实体
    - analyze:  混合分析结构 + 建议大纲
    - confirm:  等待用户确认模板（human-in-the-loop）
    - generate: 注入上下文 → LLM 生成最终笔记
    """

    # ---- 标识 ----

    @property
    def skill_id(self) -> str:
        return "note_gen"

    @property
    def name(self) -> str:
        return "笔记生成"

    @property
    def description(self) -> str:
        return "上传学习内容，选择笔记模板，AI 自动生成结构化笔记"

    # ---- 配置 ----

    @property
    def requires_human_confirm(self) -> bool:
        return True

    def required_tools(self) -> list[str]:
        return ["content_parser", "entity_extractor", "structure_analyzer"]

    def validate_input(self, context: SkillContext) -> SkillResult | None:
        if not context.user_input.strip():
            return SkillResult(
                success=False,
                skill_id=self.skill_id,
                error="输入内容不能为空",
            )
        template_id = context.metadata.get("template_id", "")
        valid = {"outline", "summary", "cornell", "qa"}
        if template_id and template_id not in valid:
            return SkillResult(
                success=False,
                skill_id=self.skill_id,
                error=f"无效的模板 ID '{template_id}'，可选: {list(valid)}",
            )
        return None

    # ---- 图构建 ----

    def build_graph(self) -> StateGraph:
        """构建 5 节点流水线图。"""
        builder = StateGraph(NoteAgentState)

        builder.add_node("parse", self._parse_node)
        builder.add_node("extract", self._extract_node)
        builder.add_node("analyze", self._analyze_node)
        builder.add_node("confirm", self._confirm_node)
        builder.add_node("generate", self._generate_node)

        builder.add_edge(START, "parse")
        builder.add_edge("parse", "extract")
        builder.add_edge("extract", "analyze")
        builder.add_edge("analyze", "confirm")
        builder.add_edge("confirm", "generate")
        builder.add_edge("generate", END)

        checkpointer = MemorySaver()
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_before=["confirm"],  # human-in-the-loop
        )

    # ================================================================
    # 节点方法
    # ================================================================

    async def _parse_node(self, state: NoteAgentState) -> dict[str, Any]:
        """节点 1：解析用户上传的内容。"""
        logger.info(f"[{state.get('session_id', '')}] parse_content 开始")

        parser = self.get_tool("content_parser")
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

    async def _extract_node(self, state: NoteAgentState) -> dict[str, Any]:
        """节点 2：LLM 提取知识实体。"""
        logger.info(f"[{state.get('session_id', '')}] extract_entities 开始")

        extractor = self.get_tool("entity_extractor")
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

    async def _analyze_node(self, state: NoteAgentState) -> dict[str, Any]:
        """节点 3：混合模式分析内容结构。"""
        logger.info(f"[{state.get('session_id', '')}] analyze_structure 开始")

        analyzer = self.get_tool("structure_analyzer")
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

    async def _confirm_node(self, state: NoteAgentState) -> dict[str, Any]:
        """
        节点 4：确认模板选择。

        graph 启用了 interrupt_before=["confirm"]，
        图会在执行此节点前暂停。用户通过 API 确认后，
        human_confirmed 已被 resume_stream 通过 update_state 设置。
        """
        logger.info(
            f"[{state.get('session_id', '')}] confirm_template: "
            f"template={state.get('template_id', '')}, "
            f"confirmed={state.get('human_confirmed', False)}"
        )
        return {
            "stage": "confirm",
            "human_confirmed": state.get("human_confirmed", False),
        }

    async def _generate_node(self, state: NoteAgentState) -> dict[str, Any]:
        """节点 5：注入上下文化 → LLM 生成笔记。"""
        logger.info(f"[{state.get('session_id', '')}] generate_note 开始")

        llm = self._llm_service
        template_id = state["template_id"]

        from app.prompts.note import NOTE_PROMPTS
        system_prompt = NOTE_PROMPTS.get(template_id, NOTE_PROMPTS.get("outline", ""))

        user_message = self._build_enriched_user_message(state)

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

    # ================================================================
    # 辅助方法
    # ================================================================

    @staticmethod
    def _build_enriched_user_message(state: NoteAgentState) -> str:
        """
        从 state 的各中间字段构建增强版用户消息。

        把 Tool 的产出（实体、大纲、复杂度）作为上下文注入。
        """
        parts: list[str] = []
        parts.append(f"## 原始学习内容\n\n{state['content']}")

        sections = state.get("parsed_sections", [])
        if sections:
            parts.append("\n## 内容结构\n")
            for s in sections[:10]:
                prefix = "#" * s.get("level", 1)
                parts.append(f"{prefix} {s.get('heading', '')}")

        key_concepts = state.get("key_concepts", [])
        if key_concepts:
            parts.append("\n## 已识别的核心概念\n")
            parts.append("、".join(key_concepts))

        outline = state.get("suggested_outline", [])
        if outline:
            parts.append("\n## 建议的笔记大纲\n")
            for item in outline[:8]:
                indent = "  " * (item.get("level", 1) - 1)
                parts.append(f"{indent}- {item.get('heading', '')}")

        parts.append(f"\n内容类型: {state.get('content_type', 'unknown')}")
        parts.append(f"复杂度: {state.get('complexity', 'medium')}")
        parts.append(f"预估学习时间: {state.get('estimated_study_time_minutes', 30)} 分钟")
        parts.append(f"语言: {state.get('parsed_language', 'zh')}")

        return "\n".join(parts)
