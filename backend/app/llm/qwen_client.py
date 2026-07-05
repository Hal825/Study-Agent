"""
Qwen LLM 客户端
================
封装通义千问 API（OpenAI 兼容接口），供工具层调用。
URL 和 KEY 从 .env 导入，模型名由调用方显式指定。
"""

import os
import json
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from .models import QWEN_AVAILABLE_MODELS

logger = logging.getLogger(__name__)


class QwenClient:
    """
    Qwen LLM 客户端 —— 封装通义千问对话能力。

    可用模型定义在 models.py 中，调用时显式传入 model 参数。
    """

    # 可用模型列表，从 models.py 统一引用
    AVAILABLE_MODELS = QWEN_AVAILABLE_MODELS

    def __init__(self, model: str):
        """
        Args:
            model: 模型名称，必须显式指定（如 "qwen3.7-max-preview"）。
        """
        self.model = model
        self.client = AsyncOpenAI(
            api_key=os.getenv("QWEN_API_KEY", ""),
            base_url=os.getenv(
                "QWEN_API_BASE",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
        )

    async def chat(
        self,
        message: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        top_p: float = 0.8,
        max_tokens: int = 8192,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        **kwargs,
    ) -> str:
        """
        非流式对话：接收用户消息，返回完整回复。
        优先尝试流式调用（兼容仅支持 stream 的模型），若流式返回空则回退到非流式。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        try:
            # 先尝试流式
            accumulated = []
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        accumulated.append(delta.content)

            if accumulated:
                return "".join(accumulated)

            # 流式返回空，回退到非流式
            logger.warning("QwenClient.chat 流式返回空，回退到非流式调用")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error("QwenClient.chat 异常: %s", str(e))
            raise

    async def chat_stream(
        self,
        message: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        top_p: float = 0.8,
        max_tokens: int = 8192,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式对话：逐步 yield 回复文本片段（JSON 格式）。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield json.dumps(
                        {"content": delta.content}, ensure_ascii=False
                    )

            yield json.dumps({"done": True}, ensure_ascii=False)

        except Exception as e:
            error_msg = f"⚠️ Qwen API 调用失败：{str(e)}"
            logger.error("QwenClient.chat_stream 异常: %s", str(e))
            yield json.dumps({"content": error_msg}, ensure_ascii=False)
            yield json.dumps({"done": True}, ensure_ascii=False)