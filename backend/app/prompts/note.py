"""
笔记生成的 System Prompt 模板（兼容层）。

模板内容已迁移至 templates/note/*.md 文件，
通过 PromptRegistry 加载。此模块保留 NOTE_PROMPTS 字典供
已有 API 代码兼容使用，后续逐步替换为 registry.get("note/xxx")。
"""

from app.prompts.registry import get_registry

# 有效的模板 ID（与前端 types/index.ts 中 NOTE_TEMPLATES 保持同步）
VALID_TEMPLATES = {"outline", "summary", "cornell", "qa"}


def _load_note_prompts() -> dict[str, str]:
    """
    从 PromptRegistry 加载全部笔记模板。

    若 registry 未初始化（如测试环境），返回空字典。
    """
    try:
        registry = get_registry()
        prompts = {}
        for tpl_id in VALID_TEMPLATES:
            try:
                prompts[tpl_id] = registry.get(f"note/{tpl_id}")
            except KeyError:
                prompts[tpl_id] = f"[模板 note/{tpl_id} 未找到]"
        return prompts
    except RuntimeError:
        # PromptRegistry 未初始化 —— 返回空字典，调用方自行处理
        return {}


# 延迟加载：首次访问时从 registry 读取
# 这样在 import 时 registry 可能还未初始化，但在实际使用时已就绪
NOTE_PROMPTS: dict[str, str] = _load_note_prompts()


def reload_note_prompts() -> None:
    """重新加载笔记模板（用于模板文件热更新）。"""
    global NOTE_PROMPTS
    NOTE_PROMPTS = _load_note_prompts()
