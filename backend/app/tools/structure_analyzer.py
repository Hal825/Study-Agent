"""
结构分析工具 —— 混合模式（本地预处理 + LLM 分析）。

分析内容的逻辑层次、核心主题和建议的笔记大纲。
"""

from pydantic import BaseModel, Field

from app.tools.base import BaseTool
from app.services.llm_service import LLMService, LLMRequest


# ============================================================
# 输入/输出模型
# ============================================================

class StructureAnalyzerInput(BaseModel):
    """结构分析 Tool 输入。"""
    content: str = Field(..., min_length=1, description="学习内容原文")
    sections: list[dict] = Field(default_factory=list, description="已解析的章节结构（来自 ContentParser）")
    total_words: int = Field(default=0, description="总字数（来自 ContentParser）")


class MainTopic(BaseModel):
    """核心主题。"""
    name: str = Field(..., description="主题名称")
    coverage: str = Field(default="", description="在原文中的覆盖范围描述")
    subtopics: list[str] = Field(default_factory=list, description="子主题列表")


class SuggestedOutlineItem(BaseModel):
    """建议的大纲条目。"""
    heading: str = Field(..., description="大纲标题")
    level: int = Field(default=1, ge=1, le=3, description="层级 1-3")
    key_points: list[str] = Field(default_factory=list, description="该条目下的关键要点")


class StructureAnalyzerOutput(BaseModel):
    """结构分析 Tool 输出。"""
    content_type: str = Field(default="article", description="内容类型：article/lecture/notes/unknown")
    hierarchy_depth: int = Field(default=1, description="内容层次深度")
    main_topics: list[MainTopic] = Field(default_factory=list, description="核心主题列表")
    suggested_outline: list[SuggestedOutlineItem] = Field(default_factory=list, description="建议的笔记大纲")
    complexity: str = Field(default="medium", description="复杂度评估：simple/medium/complex")
    estimated_study_time_minutes: int = Field(default=30, description="预估学习时间（分钟）")


# ============================================================
# Tool 实现
# ============================================================

STRUCTURE_ANALYSIS_PROMPT = """你是一位知识结构分析专家。请分析以下学习内容的结构。

输出要求：
1. 判断内容类型（article: 文章, lecture: 讲义, notes: 笔记, unknown: 无法判断）
2. 评估内容层次深度（1-3）
3. 识别 3-5 个核心主题，每个主题列出子主题
4. 根据内容结构，建议一个学习笔记的大纲（3-5 个一级标题 + 若干二级标题）
5. 评估内容复杂度（simple: 简单入门, medium: 中等深度, complex: 复杂深入）
6. 预估学习时间（分钟）

严格按以下 JSON 格式输出，不要输出其他内容：
{
  "content_type": "article",
  "hierarchy_depth": 2,
  "main_topics": [
    {"name": "主题名", "coverage": "覆盖范围描述", "subtopics": ["子主题1", "子主题2"]}
  ],
  "suggested_outline": [
    {"heading": "大纲标题", "level": 1, "key_points": ["要点1", "要点2"]}
  ],
  "complexity": "medium",
  "estimated_study_time_minutes": 30
}"""


class StructureAnalyzer(BaseTool[StructureAnalyzerInput, StructureAnalyzerOutput]):
    """
    混合模式结构分析工具。

    本地预处理章节结构，LLM 做深层分析。
    """

    name = "structure_analyzer"
    description = "分析学习内容的逻辑结构、识别核心主题、生成建议的笔记大纲"

    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self._llm = llm_service

    @property
    def input_schema(self) -> type[StructureAnalyzerInput]:
        return StructureAnalyzerInput

    @property
    def output_schema(self) -> type[StructureAnalyzerOutput]:
        return StructureAnalyzerOutput

    @property
    def timeout_seconds(self) -> float:
        return 60.0

    @property
    def retry_count(self) -> int:
        return 1

    async def execute(self, input_data: StructureAnalyzerInput) -> StructureAnalyzerOutput:
        import json

        # 本地预处理：计算层次深度
        local_depth = self._calc_depth(input_data.sections)
        local_complexity = self._estimate_complexity(input_data.total_words, local_depth)

        # 构建 LLM 请求消息
        section_text = "\n".join(
            f"{'#' * s.get('level', 1)} {s.get('heading', '')}"
            for s in input_data.sections[:15]
        ) if input_data.sections else "无章节结构"

        user_message = (
            f"内容字数：{input_data.total_words}\n"
            f"章节结构：\n{section_text}\n\n"
            f"内容摘要（前 3000 字）：\n{input_data.content[:3000]}"
        )

        # 调用 LLM
        response = await self._llm.generate(
            LLMRequest(
                system_prompt=STRUCTURE_ANALYSIS_PROMPT,
                user_message=user_message,
                temperature=0.3,
                max_tokens=2048,
            )
        )

        # 解析响应
        try:
            data = json.loads(self._extract_json(response.content))
        except json.JSONDecodeError:
            return StructureAnalyzerOutput(
                content_type="unknown",
                hierarchy_depth=local_depth,
                main_topics=[],
                suggested_outline=[],
                complexity=local_complexity,
                estimated_study_time_minutes=self._estimate_time(input_data.total_words),
            )

        return StructureAnalyzerOutput(
            content_type=data.get("content_type", "unknown"),
            hierarchy_depth=data.get("hierarchy_depth", local_depth),
            main_topics=[
                MainTopic(
                    name=t.get("name", ""),
                    coverage=t.get("coverage", ""),
                    subtopics=t.get("subtopics", []),
                )
                for t in data.get("main_topics", [])
            ],
            suggested_outline=[
                SuggestedOutlineItem(
                    heading=o.get("heading", ""),
                    level=o.get("level", 1),
                    key_points=o.get("key_points", []),
                )
                for o in data.get("suggested_outline", [])
            ],
            complexity=data.get("complexity", local_complexity),
            estimated_study_time_minutes=data.get(
                "estimated_study_time_minutes",
                self._estimate_time(input_data.total_words),
            ),
        )

    # ---- 本地辅助方法 ----

    @staticmethod
    def _calc_depth(sections: list[dict]) -> int:
        """根据章节结构计算层次深度。"""
        if not sections:
            return 1
        max_level = max((s.get("level", 1) for s in sections), default=1)
        return max_level

    @staticmethod
    def _estimate_complexity(total_words: int, depth: int) -> str:
        """根据字数和层次估算复杂度。"""
        if total_words < 1000 and depth <= 1:
            return "simple"
        elif total_words > 5000 or depth >= 3:
            return "complex"
        return "medium"

    @staticmethod
    def _estimate_time(total_words: int) -> int:
        """根据字数估算学习时间（中文约 300 字/分钟）。"""
        return max(5, total_words // 300)

    @staticmethod
    def _extract_json(text: str) -> str:
        """从 LLM 响应中提取 JSON 部分。"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            return "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return text
