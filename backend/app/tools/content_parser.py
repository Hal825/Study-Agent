"""
内容解析工具 —— 纯本地执行，不依赖 LLM。

解析用户上传的学习内容，提取标题、章节结构、统计信息。
"""

import re
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolResult


# ============================================================
# 输入/输出模型
# ============================================================

class ContentParserInput(BaseModel):
    """内容解析 Tool 输入。"""
    content: str = Field(..., min_length=1, description="原始文本内容")
    filename: str = Field(default="", description="文件名（辅助判断格式）")


class ContentParserOutput(BaseModel):
    """内容解析 Tool 输出。"""
    title: str = Field(default="", description="文档标题")
    sections: list[dict] = Field(default_factory=list, description="章节列表 [{heading, level, content, start_line}]")
    total_words: int = Field(default=0, description="总字数")
    total_lines: int = Field(default=0, description="总行数")
    language: str = Field(default="zh", description="检测到的语言 (zh/en/mixed)")
    format: str = Field(default="markdown", description="内容格式 (markdown/plain_text)")


# ============================================================
# Tool 实现
# ============================================================

class ContentParser(BaseTool[ContentParserInput, ContentParserOutput]):
    """
    纯本地内容解析工具。

    解析 Markdown / 纯文本内容：
    - 提取 h1/h2/h3 标题结构
    - 统计字数、行数
    - 检测语言
    """

    name = "content_parser"
    description = "解析用户上传的学习内容，提取标题、章节结构、字数统计和语言检测"

    @property
    def input_schema(self) -> type[ContentParserInput]:
        return ContentParserInput

    @property
    def output_schema(self) -> type[ContentParserOutput]:
        return ContentParserOutput

    @property
    def timeout_seconds(self) -> float:
        return 5.0  # 纯本地解析，无需长超时

    async def execute(self, input_data: ContentParserInput) -> ContentParserOutput:
        text = input_data.content
        lines = text.split("\n")
        total_lines = len(lines)

        # 提取标题和章节
        sections: list[dict] = []
        title = ""

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                if not title:
                    title = stripped[2:].strip()
                sections.append({
                    "heading": stripped[2:].strip(),
                    "level": 1,
                    "content": self._collect_section_content(lines, i + 1, 2),
                    "start_line": i + 1,
                })
            elif stripped.startswith("## ") and not stripped.startswith("### "):
                sections.append({
                    "heading": stripped[3:].strip(),
                    "level": 2,
                    "content": self._collect_section_content(lines, i + 1, 3),
                    "start_line": i + 1,
                })
            elif stripped.startswith("### "):
                sections.append({
                    "heading": stripped[4:].strip(),
                    "level": 3,
                    "content": self._collect_section_content(lines, i + 1, 999),
                    "start_line": i + 1,
                })

        # 如果没有解析到标题，尝试取第一行有意义文本
        if not title:
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
                    title = stripped[:80]
                    break

        # 字数统计（中文 + 英文单词）
        # 中文字符
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        # 英文单词
        english_words = len(re.findall(r"[a-zA-Z]+", text))
        total_words = chinese_chars + english_words

        # 语言检测
        language = self._detect_language(text, chinese_chars, english_words)

        # 格式检测
        format_type = "markdown" if any(
            line.strip().startswith("#") for line in lines
        ) else "plain_text"

        return ContentParserOutput(
            title=title,
            sections=sections,
            total_words=total_words,
            total_lines=total_lines,
            language=language,
            format=format_type,
        )

    @staticmethod
    def _collect_section_content(lines: list[str], start: int, max_level: int) -> str:
        """从 start 行开始收集内容，直到遇到同级或更高级的标题。"""
        content_lines: list[str] = []
        for i in range(start, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                if level <= max_level:
                    break
            content_lines.append(lines[i])
        return "\n".join(content_lines).strip()

    @staticmethod
    def _detect_language(text: str, chinese_chars: int, english_words: int) -> str:
        """朴素语言检测。"""
        if chinese_chars > english_words * 2:
            return "zh"
        elif english_words > chinese_chars * 2:
            return "en"
        elif chinese_chars > 0 and english_words > 0:
            return "mixed"
        return "zh"  # 默认中文
