"""
Tool 注册中心 —— 按名称管理全部 Tool 实例。

实现 IToolRegistry 抽象接口。
"""

import logging
from typing import Optional

from app.tools.base import BaseTool
from app.tools.interfaces import IToolRegistry

logger = logging.getLogger("tools.registry")


class ToolRegistry(IToolRegistry):
    """
    Tool 注册中心。

    用法：
        reg = ToolRegistry()
        reg.register(ContentParser())
        tool = reg.get("content_parser")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError(f"Tool 缺少 name: {type(tool).__name__}")
        if tool.name in self._tools:
            raise ValueError(f"Tool [{tool.name}] 已注册，不允许重复")
        self._tools[tool.name] = tool
        logger.info(f"注册 Tool: {tool.name} ({type(tool).__name__})")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_names(self) -> list[str]:
        return list(self._tools.keys())
