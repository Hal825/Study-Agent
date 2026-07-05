"""
LLM 模块
=========
统一管理各厂商 LLM 客户端与模型名称常量。
当前实现：
  - qwen_client.py     （通义千问客户端，供工具层调用）
  - deepseek_client.py （DeepSeek 客户端，供工具层调用）
  - models.py          （模型名称常量定义）
后续可扩展：
  - 其它厂商客户端（如智谱 GLM、OpenAI 等）
"""

from .qwen_client import QwenClient
from .deepseek_client import DeepSeekClient
from .models import (
    QWEN_MAX,
    QWEN_PLUS,
    QWEN_TURBO,
    QWEN_3_7_MAX_PREVIEW,
    QWEN_LONG,
    QWQ_PLUS,
    DEEPSEEK_CHAT,
    DEEPSEEK_REASONER,
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_PRO,
    QWEN_AVAILABLE_MODELS,
    DEEPSEEK_AVAILABLE_MODELS,
)

__all__ = [
    "QwenClient",
    "DeepSeekClient",
    "QWEN_MAX",
    "QWEN_PLUS",
    "QWEN_TURBO",
    "QWEN_3_7_MAX_PREVIEW",
    "QWEN_LONG",
    "QWQ_PLUS",
    "DEEPSEEK_CHAT",
    "DEEPSEEK_REASONER",
    "DEEPSEEK_V4_FLASH",
    "DEEPSEEK_V4_PRO",
    "QWEN_AVAILABLE_MODELS",
    "DEEPSEEK_AVAILABLE_MODELS",
]
