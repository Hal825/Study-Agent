"""
视觉预处理工具 —— 数据模型定义。

VisionInput:  图片二进制数据 + 文件名 + 可选自定义提示
VisionOutput: 模型原始文本 + 清洗后的 Markdown + 统计信息
"""

from pydantic import BaseModel, Field


class VisionInput(BaseModel):
    """视觉预处理 Tool 输入。"""
    image_bytes: bytes = Field(..., description="图片二进制数据")
    file_name: str = Field(default="", description="文件名（用于日志和缓存 Key）")
    custom_prompt: str | None = Field(default=None, description="允许覆盖默认 OCR 提示词")

    model_config = {"arbitrary_types_allowed": True}


class VisionOutput(BaseModel):
    """视觉预处理 Tool 输出。"""
    raw_text: str = Field(..., description="模型返回的原始文本")
    cleaned_markdown: str = Field(..., description="清洗后的标准 Markdown（含 LaTeX）")
    char_count: int = Field(default=0, description="文本长度统计")
    is_math_heavy: bool = Field(default=False, description="是否包含大量公式")
