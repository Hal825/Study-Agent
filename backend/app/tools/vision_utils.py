"""
视觉预处理辅助工具 —— 图片压缩 & Markdown 后处理。

纯静态方法，不依赖外部服务。
"""

import io
import re

# 零宽字符正则（常出现在 LLM 输出中）
_ZW_RE = re.compile(r"[​‌‍‎‏﻿­]")


class ImageCompressor:
    """使用 PIL 将图片压缩至目标分辨率（保持宽高比）。"""

    @staticmethod
    async def compress(image_bytes: bytes, max_size: int = 1024) -> bytes:
        """
        将图片长边缩放到 max_size 像素，转换为 JPEG 格式返回。

        Args:
            image_bytes: 原始图片二进制数据
            max_size: 长边最大像素数

        Returns:
            压缩后的 JPEG 图片二进制数据

        Raises:
            ValueError: 无法解码图片
        """
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))

        # 转换为 RGB（处理 RGBA / P 模式）
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(
                img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
            )
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 缩放
        original_size = img.size
        w, h = original_size
        if max(w, h) > max_size:
            ratio = max_size / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()


class MarkdownCleaner:
    """
    修复 Qwen VL 返回的 Markdown 常见瑕疵：

    - 未闭合的 $ / $$ / \\[ / \\] 自动补全
    - 去除零宽字符
    - 清理多余空行
    """

    @staticmethod
    def clean(raw: str) -> str:
        """清洗 Markdown 文本。"""
        text = raw

        # 1. 去除零宽字符
        text = _ZW_RE.sub("", text)

        # 2. 修复常见 LaTeX 包裹问题
        text = MarkdownCleaner._fix_unclosed_delimiters(text)

        # 3. 规范空行（最多连续两个换行）
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 4. 去除首尾多余空白
        text = text.strip()

        return text

    @staticmethod
    def _fix_unclosed_delimiters(text: str) -> str:
        """
        修复未闭合的 $ 和 $$ / \\[ \\] 定界符。

        策略：
        - 统计 $$ 出现次数，奇数时补上 `$$`
        - 统计未配对的行内 $（不跨行的 $），奇数时在末尾补上
        - 统计 \\[ 和 \\] 配对，多的方向补上对应闭合符
        """
        # ---- 行间公式 $$ ----
        double_dollar_count = text.count("$$")
        if double_dollar_count % 2 != 0:
            text += "\n$$"

        # ---- 行间公式 \[ \] ----
        display_open = text.count("\\[")
        display_close = text.count("\\]")
        if display_open > display_close:
            text += "\n\\]"
        elif display_close > display_open:
            text = "\\[\n" + text

        # ---- 行内公式 $ ----
        # 简单策略：统计行内未转义的 $ 符号，若为奇数则在末尾补上
        # 注意跳过 $$ 中的 $
        single_dollar = MarkdownCleaner._count_single_dollar(text)
        if single_dollar % 2 != 0:
            text += "$"

        return text

    @staticmethod
    def _count_single_dollar(text: str) -> int:
        """
        统计行内 $ 符号数量（排除 $$ 中的部分）。

        将 `$$` 视为一个整体（行间公式），单独的 `$` 视为行内公式。
        """
        # 先移除所有 $$ 的位置
        cleaned = text.replace("$$", "")
        # 统计剩余的 $
        return cleaned.count("$")
