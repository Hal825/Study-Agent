"""
统一 LLM 服务 —— 封装 LLM 调用，支持多 Provider 切换。

当前支持 DeepSeek，预留 Qwen 等其他 provider 扩展点。
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

from app.data.interfaces import CacheStore


# ============================================================
# 数据类型
# ============================================================

@dataclass
class LLMRequest:
    """统一 LLM 请求。"""
    system_prompt: str = ""
    user_message: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    metadata: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """统一 LLM 响应。"""
    content: str
    model: str = ""
    usage: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    cached: bool = False


# ============================================================
# Provider 抽象
# ============================================================

class BaseLLMProvider(ABC):
    """LLM Provider 抽象接口。"""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """执行 LLM 调用。"""
        ...

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """检查是否支持该模型。"""
        ...


# ============================================================
# DeepSeek Provider
# ============================================================

class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API Provider（OpenAI 兼容接口）。"""

    def __init__(self) -> None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未设置")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._default_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    def supports_model(self, model: str) -> bool:
        return model.startswith("deepseek")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._default_model
        start = time.perf_counter()

        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_message},
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        duration = (time.perf_counter() - start) * 1000
        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            duration_ms=duration,
        )


# ============================================================
# LLM Service（对外统一入口）
# ============================================================

class LLMService:
    """
    统一 LLM 服务。

    功能：
    - 多 Provider 管理（DeepSeek / Qwen / ...）
    - 请求缓存（相同输入去重）
    - 统一接口，对上层隐藏 Provider 差异
    """

    def __init__(
        self,
        providers: Optional[list[BaseLLMProvider]] = None,
        cache: Optional[CacheStore] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self._providers: dict[str, BaseLLMProvider] = {}
        self._cache = cache
        self._default_model = default_model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if providers:
            for p in providers:
                self.register(p)
        else:
            # 默认注册 DeepSeek
            try:
                self.register(DeepSeekProvider())
            except RuntimeError:
                pass  # API key 未设置时静默跳过

    def register(self, provider: BaseLLMProvider) -> None:
        """注册一个 LLM provider。"""
        # 用模块名作为 provider key
        key = type(provider).__name__.lower().replace("provider", "")
        self._providers[key] = provider

    def _resolve_provider(self, model: str) -> BaseLLMProvider:
        """根据 model 名称找到对应的 provider。"""
        for provider in self._providers.values():
            if provider.supports_model(model):
                return provider
        raise ValueError(f"不支持的模型: {model}，已注册的 provider: {list(self._providers.keys())}")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        执行 LLM 调用。

        优先从缓存获取（相同 system + user + model），
        缓存未命中则调用实际 provider。
        """
        # 缓存检查
        cache_key = ""
        if self._cache:
            cache_key = self._build_cache_key(request)
            cached = await self._cache.get(cache_key)
            if cached is not None:
                cached.cached = True
                return cached

        # 调用 provider
        model = request.model or self._default_model
        provider = self._resolve_provider(model)
        response = await provider.generate(request)

        # 写入缓存
        if self._cache and cache_key:
            await self._cache.set(cache_key, response, ttl_seconds=300)

        return response

    async def generate_legacy(self, system_prompt: str, user_message: str) -> str:
        """
        兼容旧版调用方式：返回纯文本字符串。
        用于渐进迁移，待上层重构完成后移除。
        """
        response = await self.generate(
            LLMRequest(system_prompt=system_prompt, user_message=user_message)
        )
        return response.content

    @staticmethod
    def _build_cache_key(request: LLMRequest) -> str:
        """构造缓存 key。"""
        import hashlib
        raw = f"{request.model}:{request.system_prompt[:200]}:{request.user_message[:200]}"
        return f"llm:{hashlib.md5(raw.encode()).hexdigest()}"

    @property
    def available_models(self) -> list[str]:
        """所有可用模型列表。"""
        models = []
        for provider in self._providers.values():
            if hasattr(provider, '_default_model'):
                models.append(provider._default_model)
        return models
