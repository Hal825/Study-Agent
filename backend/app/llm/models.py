"""
模型名称常量定义
================
统一管理所有 LLM 模型名称，供工具层和客户端层引用。
"""

# ---------- Qwen 系列模型 ----------
QWEN_MAX = "qwen-max"
QWEN_PLUS = "qwen-plus"
QWEN_TURBO = "qwen-turbo"
QWEN_3_7_MAX_PREVIEW = "qwen3.7-max-preview"
QWEN_LONG = "qwen-long"
QWQ_PLUS = "qwq-plus"

# ---------- DeepSeek 系列模型 ----------
DEEPSEEK_CHAT = "deepseek-chat"
DEEPSEEK_REASONER = "deepseek-reasoner"
DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
DEEPSEEK_V4_PRO = "deepseek-v4-pro"

# ---------- 可用模型列表（供参考） ----------
QWEN_AVAILABLE_MODELS = [
    QWEN_MAX,
    QWEN_PLUS,
    QWEN_TURBO,
    QWEN_3_7_MAX_PREVIEW,
    QWEN_LONG,
    QWQ_PLUS,
]

DEEPSEEK_AVAILABLE_MODELS = [
    DEEPSEEK_CHAT,
    DEEPSEEK_REASONER,
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_PRO,
]
