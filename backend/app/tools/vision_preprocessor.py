"""
视觉预处理工具 —— VisionPreprocessorTool。

将图片（教材扫描、板书照片等）通过 Qwen3-VL-Flash 转换为
标准 Markdown 文本（含 LaTeX 数学公式），供 Agent 后续处理。

继承 BaseTool[VisionInput, VisionOutput]，支持：
- 缓存去重（相同图片 MD5 → 直接返回）
- 图片压缩（降低 API 延迟）
- 自动 LaTeX 修复
"""

import asyncio
import base64
import hashlib
import logging
import os
import time
from typing import Optional

from openai import OpenAI

from app.tools.base import BaseTool, ToolResult, ToolStatus
from app.tools.vision_models import VisionInput, VisionOutput
from app.tools.vision_utils import ImageCompressor, MarkdownCleaner
from app.data.interfaces import CacheStore

logger = logging.getLogger("tools.vision")


class VisionPreprocessorTool(BaseTool[VisionInput, VisionOutput]):
    """
    视觉预处理工具。

    职责：
    1. 生成缓存 Key → vision:{md5}
    2. 查缓存 → 命中直接返回
    3. 压缩图片 → Base64 编码
    4. 调用 Qwen VL API（OpenAI 兼容接口）
    5. 清洗 Markdown → 写入缓存 → 返回
    """

    name = "vision_preprocessor"
    description = "将图片转换为 Markdown 文本（含 LaTeX 公式），支持缓存去重"

    # ---- 构建提示词 ----

    DEFAULT_PROMPT = """你是一个顶级的学术文档OCR专家，尤其擅长数学公式识别。
请分析这张图片，并严格按照以下规则输出Markdown格式的文本：
1. 所有数学公式必须使用LaTeX语法：
   - 行间公式（独占一行）使用 $$ ... $$ 包裹。
   - 行内公式（与文字混合）使用 $ ... $ 包裹。
2. 分式 (\\frac{}{})、根号 (\\sqrt{})、上下标 (^_)、积分 (\\int)、求和 (\\sum) 必须精确识别。
3. 如果是表格数据，使用Markdown表格管道符 (|) 输出。
4. 如果是普通文字，按段落输出，保留换行。
5. 只输出提取后的内容，不要包含"图片中识别到如下内容"等解释性文字。"""

    def __init__(
        self,
        cache_store: Optional[CacheStore] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Args:
            cache_store: 缓存存储实例（可选，传入则启用缓存）
            api_key: Qwen API Key（默认从环境变量 QWEN_API_KEY 读取）
            base_url: Qwen API 兼容地址（默认从 QWEN_BASE_URL 或 QWEN_API_BASE 读取）
            model: VL 模型名称（默认从 QWEN_VL_MODEL 读取，fallback: qwen3-vl-flash）
        """
        self._cache = cache_store

        self._api_key = api_key or os.getenv("QWEN_API_KEY", "")
        if not self._api_key:
            logger.warning("QWEN_API_KEY 未设置，视觉预处理将不可用")

        self._base_url = (
            base_url
            or os.getenv("QWEN_BASE_URL", "")
            or os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )
        self._model = model or os.getenv("QWEN_VL_MODEL", "qwen3-vl-flash")
        self._max_image_size = int(os.getenv("VISION_IMAGE_MAX_SIZE", "1024"))
        self._cache_ttl = int(os.getenv("VISION_CACHE_TTL", "604800"))

        if self._api_key:
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        else:
            self._client = None

        logger.info(
            "VisionPreprocessorTool 初始化: model=%s, base_url=%s, cache=%s, max_size=%d",
            self._model, self._base_url,
            "enabled" if cache_store else "disabled",
            self._max_image_size,
        )

    # ---- BaseTool 接口 ----

    @property
    def input_schema(self) -> type[VisionInput]:
        return VisionInput

    @property
    def output_schema(self) -> type[VisionOutput]:
        return VisionOutput

    @property
    def timeout_seconds(self) -> float:
        return 30.0

    @property
    def retry_count(self) -> int:
        return 1  # LLM 调用偶尔会超时，重试一次

    @property
    def retry_delay_seconds(self) -> float:
        return 2.0

    async def execute(self, input_data: VisionInput) -> VisionOutput:
        """核心执行逻辑。"""
        if not self._client:
            raise RuntimeError("Qwen API Key 未配置，无法执行视觉识别")

        image_bytes = input_data.image_bytes
        if not image_bytes:
            raise ValueError("图片数据为空")

        # ---- 1. 生成缓存 Key ----
        img_hash = hashlib.md5(image_bytes).hexdigest()
        cache_key = f"vision:{img_hash}"

        # ---- 2. 查缓存 ----
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached is not None:
                    logger.info(f"[vision] 缓存命中: {cache_key[:16]}...")
                    return VisionOutput(**cached) if isinstance(cached, dict) else cached
            except Exception as e:
                logger.debug(f"[vision] 缓存查询异常(已忽略): {e}")

        # ---- 3. 压缩图片 ----
        start = time.perf_counter()
        compressed = await ImageCompressor.compress(image_bytes, max_size=self._max_image_size)
        compress_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"[vision] 图片压缩: {len(image_bytes)/1024:.0f}KB → {len(compressed)/1024:.0f}KB, "
            f"{compress_ms:.0f}ms"
        )

        # ---- 4. Base64 编码 ----
        base64_str = base64.b64encode(compressed).decode("ascii")

        # ---- 5. 调用 Qwen VL API ----
        prompt = input_data.custom_prompt or self.DEFAULT_PROMPT

        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_str}",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=4096,
            temperature=0.1,  # 低温度保证 OCR 准确性
        )
        api_ms = (time.perf_counter() - start) * 1000

        raw_text = response.choices[0].message.content or ""
        logger.info(
            f"[vision] API 调用完成: model={self._model}, "
            f"{api_ms:.0f}ms, {len(raw_text)} chars"
        )

        # ---- 6. 清洗 Markdown ----
        cleaned = MarkdownCleaner.clean(raw_text)

        char_count = len(cleaned)
        is_math_heavy = self._detect_math_heavy(cleaned)

        output = VisionOutput(
            raw_text=raw_text,
            cleaned_markdown=cleaned,
            char_count=char_count,
            is_math_heavy=is_math_heavy,
        )

        # ---- 7. 写入缓存 ----
        if self._cache:
            try:
                await self._cache.set(
                    cache_key, output.model_dump(), ttl_seconds=self._cache_ttl
                )
                logger.debug(f"[vision] 已写入缓存: {cache_key[:16]}... TTL={self._cache_ttl}s")
            except Exception as e:
                logger.debug(f"[vision] 缓存写入异常(已忽略): {e}")

        return output

    # ---- 辅助方法 ----

    @staticmethod
    def _detect_math_heavy(text: str) -> bool:
        """检测文本是否包含大量数学公式。"""
        # 统计 $...$ 和 $$...$$ 以及 \ 开头的 LaTeX 命令
        dollar_pairs = text.count("$$") // 2
        inline_math = max(0, (text.count("$") - text.count("$$") * 2)) // 2
        latex_commands = len([c for c in text if c == "\\"])

        total_indicators = dollar_pairs + inline_math + latex_commands
        return total_indicators > 5
