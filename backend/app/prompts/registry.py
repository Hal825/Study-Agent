"""
Prompt 注册中心 —— 加载、缓存、查询模板文件。

提供全局单例工厂，与 get_container() 使用习惯统一。
"""

import logging
from pathlib import Path
from typing import Optional

from app.prompts.schemas import PromptTemplate

logger = logging.getLogger("prompts.registry")


class PromptRegistry:
    """
    Prompt 模板注册中心。

    从指定的模板目录加载 .md 文件，
    以目录结构作为 key（如 note/outline → templates/note/outline.md）。

    全局单例模式：通过 get_instance() / get_registry() 获取。
    """

    _instance: Optional["PromptRegistry"] = None

    @classmethod
    def get_instance(cls) -> "PromptRegistry":
        """获取全局单例。未初始化时抛出 RuntimeError。"""
        if cls._instance is None:
            raise RuntimeError(
                "PromptRegistry 尚未初始化，请先通过 Container 创建实例"
            )
        return cls._instance

    def __init__(self, templates_dir: str) -> None:
        """
        Args:
            templates_dir: 模板文件根目录路径（相对于项目根或绝对路径）
        """
        self.templates_dir = Path(templates_dir)
        self._cache: dict[str, PromptTemplate] = {}
        self.reload()

        # 注册为全局单例
        PromptRegistry._instance = self

    # ---- 查询 ----

    def get(self, key: str) -> str:
        """
        按 key 获取模板文本。

        Args:
            key: 模板键，如 "note/outline"

        Returns:
            模板文本内容

        Raises:
            KeyError: 模板不存在
        """
        if key not in self._cache:
            raise KeyError(
                f"模板 [{key}] 不存在，可用模板: {list(self._cache.keys())}"
            )
        return self._cache[key].content

    def get_all_keys(self) -> list[str]:
        """获取所有模板 key。"""
        return list(self._cache.keys())

    def get_template(self, key: str) -> PromptTemplate:
        """
        按 key 获取完整模板对象（含元数据）。

        Raises:
            KeyError: 模板不存在
        """
        if key not in self._cache:
            raise KeyError(f"模板 [{key}] 不存在")
        return self._cache[key]

    # ---- 加载 ----

    def reload(self) -> None:
        """
        重新加载所有模板文件。

        扫描 templates_dir 下所有 .md 文件，
        以相对路径（去掉 .md 后缀）作为 key。
        """
        self._cache.clear()
        if not self.templates_dir.exists():
            logger.warning(f"模板目录不存在: {self.templates_dir}")
            return

        loaded = 0
        for md_file in self.templates_dir.rglob("*.md"):
            key = self._file_to_key(md_file)
            content = md_file.read_text(encoding="utf-8").strip()
            if not content:
                logger.warning(f"模板为空，跳过: {key}")
                continue

            self._cache[key] = PromptTemplate(
                key=key,
                content=content,
                description=f"从 {md_file.relative_to(self.templates_dir)} 加载",
            )
            loaded += 1
            logger.debug(f"已加载模板: {key}")

        logger.info(f"PromptRegistry 加载完成: {loaded} 个模板")

    # ---- 内部 ----

    def _file_to_key(self, file_path: Path) -> str:
        """将文件路径转为模板 key。"""
        rel = file_path.relative_to(self.templates_dir)
        # 去掉 .md 后缀，用 / 连接
        parts = list(rel.parts)
        parts[-1] = parts[-1].replace(".md", "")
        return "/".join(parts)


# ---- 便捷函数 ----

def get_registry() -> PromptRegistry:
    """获取全局 PromptRegistry 单例（便捷函数）。"""
    return PromptRegistry.get_instance()
