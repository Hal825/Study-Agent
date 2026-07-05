"""
DeepSeek LLM 客户端
====================
封装 DeepSeek API（OpenAI 兼容接口），供工具层与 Agent 层调用。
URL 和 KEY 从 .env 导入，模型名由调用方显式指定。
"""

import os
import json
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from .models import DEEPSEEK_AVAILABLE_MODELS

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    DeepSeek LLM 客户端 —— 封装 DeepSeek 对话能力。

    可用模型定义在 models.py 中，调用时显式传入 model 参数。
    支持 function calling（工具调用）。
    """

    # 可用模型列表，从 models.py 统一引用
    AVAILABLE_MODELS = DEEPSEEK_AVAILABLE_MODELS

    def __init__(self, model: str):
        """
        Args:
            model: 模型名称，必须显式指定（如 "deepseek-chat"）。
        """
        self.model = model
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv(
                "DEEPSEEK_BASE_URL",
                "https://api.deepseek.com",
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
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

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
            error_msg = f"⚠️ DeepSeek API 调用失败：{str(e)}"
            logger.error("DeepSeekClient.chat_stream 异常: %s", str(e))
            yield json.dumps({"content": error_msg}, ensure_ascii=False)
            yield json.dumps({"done": True}, ensure_ascii=False)

    async def chat_with_tools(
        self,
        message: str,
        *,
        tools: list[dict] | None = None,
        system_prompt: str = "",
        temperature: float = 0.7,
        top_p: float = 0.8,
        max_tokens: int = 8192,
        **kwargs,
    ) -> object:
        """
        支持工具调用的非流式对话。

        Args:
            message: 用户消息
            tools: OpenAI function calling 格式的工具列表
            system_prompt: 系统提示词
            其它参数同 chat()

        Returns:
            原始 response 对象，调用方可通过
            response.choices[0].message.tool_calls 获取工具调用信息，
            或 response.choices[0].message.content 获取文本回复。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=False,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return response

    async def chat_with_tools_messages(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        top_p: float = 0.8,
        max_tokens: int = 8192,
        **kwargs,
    ) -> object:
        """
        支持工具调用的多轮非流式对话（传入完整 messages 列表）。

        Args:
            messages: 完整对话历史（含 tool 调用结果回填）
            tools: OpenAI function calling 格式的工具列表

        Returns:
            原始 response 对象
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=False,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return response