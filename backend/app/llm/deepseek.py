"""
DeepSeek LLM 客户端封装。

使用 OpenAI 兼容接口调用 DeepSeek API。
"""

import os
from openai import OpenAI
from app.prompts.note import NOTE_PROMPTS


def _build_client() -> OpenAI:
    """从环境变量构建 DeepSeek 客户端（OpenAI 兼容）。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置，请检查 .env 文件")

    return OpenAI(api_key=api_key, base_url=base_url)


# 模块级单例客户端
_client: OpenAI | None = None


def get_client() -> OpenAI:
    """获取 DeepSeek 客户端（惰性初始化，确保环境变量已加载）。"""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


async def generate_note(content: str, template_id: str) -> str:
    """
    调用 DeepSeek 生成笔记。

    Args:
        content: 用户上传的学习内容
        template_id: 笔记模板 ID (outline / summary / cornell / qa)

    Returns:
        Markdown 格式的生成笔记
    """
    system_prompt = NOTE_PROMPTS.get(template_id)
    if system_prompt is None:
        raise ValueError(f"未知的笔记模板: {template_id}，可选值为: {list(NOTE_PROMPTS.keys())}")

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    client = get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    result = response.choices[0].message.content
    if result is None:
        raise RuntimeError("DeepSeek API 返回了空内容")

    return result
