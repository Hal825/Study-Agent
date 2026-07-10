"""
实体提取工具 —— LLM 驱动，从内容中提取关键概念和术语。
"""

from pydantic import BaseModel, Field

from app.tools.base import BaseTool
from app.services.llm_service import LLMService, LLMRequest

# ============================================================
# 输入/输出模型
# ============================================================

class EntityExtractorInput(BaseModel):
    """实体提取 Tool 输入。"""
    content: str = Field(..., min_length=1, description="学习内容原文")
    sections: list[dict] = Field(default_factory=list, description="已解析的章节结构（来自 ContentParser）")
    max_entities: int = Field(default=20, ge=1, le=100, description="最大提取实体数")


class EntityItem(BaseModel):
    """单个知识实体。"""
    name: str = Field(..., description="实体名称")
    category: str = Field(default="", description="分类：概念/术语/人物/公式/事件")
    importance: str = Field(default="medium", description="重要程度：high/medium/low")
    context: str = Field(default="", description="在原文中的简要上下文")
    related: list[str] = Field(default_factory=list, description="相关实体名称")


class EntityExtractorOutput(BaseModel):
    """实体提取 Tool 输出。"""
    entities: list[EntityItem] = Field(default_factory=list, description="提取的实体列表")
    key_concepts: list[str] = Field(default_factory=list, description="核心概念名称（排序前 5）")
    total_extracted: int = Field(default=0, description="提取总数")


# ============================================================
# Tool 实现
# ============================================================

ENTITY_EXTRACTION_PROMPT = """你是一位知识提取专家。请从以下学习内容中提取关键知识实体。

要求：
1. 为每个实体标注类别（概念/术语/人物/公式/事件）
2. 标注重要程度（high: 核心概念, medium: 重要补充, low: 细节提及）
3. 提供每个实体在原文中的简要上下文
4. 标注实体之间的关联关系

请严格按以下 JSON 格式输出，不要输出其他内容：
{
  "entities": [
    {
      "name": "实体名称",
      "category": "概念",
      "importance": "high",
      "context": "在原文中的简要上下文（不超过 50 字）",
      "related": ["关联实体1", "关联实体2"]
    }
  ]
}"""


class EntityExtractor(BaseTool[EntityExtractorInput, EntityExtractorOutput]):
    """
    LLM 驱动的知识实体提取工具。

    使用 LLM 从学习内容中识别关键概念、术语、公式等知识实体。
    """

    name = "entity_extractor"
    description = "从学习内容中提取关键知识实体（概念/术语/人物/公式），标注重要程度和关联关系"

    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self._llm = llm_service

    @property
    def input_schema(self) -> type[EntityExtractorInput]:
        return EntityExtractorInput

    @property
    def output_schema(self) -> type[EntityExtractorOutput]:
        return EntityExtractorOutput

    @property
    def timeout_seconds(self) -> float:
        return 60.0  # LLM 调用需要更长的超时

    @property
    def retry_count(self) -> int:
        return 1  # LLM 偶尔不稳定，重试一次

    async def execute(self, input_data: EntityExtractorInput) -> EntityExtractorOutput:
        import json

        # 构建用户消息 —— 包含全文 + 章节概述
        user_message = f"学习内容：\n\n{input_data.content[:8000]}"  # 截断过长内容
        if input_data.sections:
            section_summary = "\n".join(
                f"- [{s.get('heading', '')}]" for s in input_data.sections[:10]
            )
            user_message += f"\n\n章节结构：\n{section_summary}"

        # 调用 LLM
        response = await self._llm.generate(
            LLMRequest(
                system_prompt=ENTITY_EXTRACTION_PROMPT,
                user_message=user_message,
                temperature=0.3,   # 低温度，要求输出稳定
                max_tokens=2048,
            )
        )

        # 解析 JSON 响应
        try:
            data = json.loads(self._extract_json(response.content))
        except json.JSONDecodeError:
            # LLM 可能不严格按 JSON 返回，降级返回空结果
            return EntityExtractorOutput(
                entities=[],
                key_concepts=[],
                total_extracted=0,
            )

        entities_raw = data.get("entities", [])
        entities = [
            EntityItem(
                name=e.get("name", ""),
                category=e.get("category", ""),
                importance=e.get("importance", "medium"),
                context=e.get("context", ""),
                related=e.get("related", []),
            )
            for e in entities_raw[:input_data.max_entities]
        ]

        # 核心概念 = importance=high 的实体名
        key_concepts = [
            e.name for e in entities
            if e.importance == "high"
        ][:5]

        return EntityExtractorOutput(
            entities=entities,
            key_concepts=key_concepts,
            total_extracted=len(entities),
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """从 LLM 响应中提取 JSON 部分（处理 markdown code block 包裹）。"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉第一行（```json）和最后一行（```）
            return "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return text
