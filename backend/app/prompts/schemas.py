"""
Prompt Layer 数据模型。
"""

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """一个 Prompt 模板的元数据。"""
    key: str = Field(..., description="模板键，如 note/outline")
    version: str = Field(default="1.0", description="模板版本")
    description: str = Field(default="", description="模板用途描述")
    content: str = Field(..., description="模板文本内容")
