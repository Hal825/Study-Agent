"""
Tool Layer 抽象接口 —— 和 Data Layer 接口规范对齐。

上层依赖 IToolRegistry 接口，不依赖具体实现，
支持 MockToolRegistry 用于单元测试。
"""

from abc import ABC, abstractmethod
from typing import Optional
from app.tools.base import BaseTool


class IToolRegistry(ABC):
    """Tool 注册中心抽象接口。"""

    @abstractmethod
    def register(self, tool: BaseTool) -> None:
        """注册一个 Tool 实例。"""
        ...

    @abstractmethod
    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取 Tool，不存在返回 None。"""
        ...

    @abstractmethod
    def list_all(self) -> list[BaseTool]:
        """获取所有已注册 Tool。"""
        ...

    @abstractmethod
    def get_names(self) -> list[str]:
        """获取所有 Tool 名称列表。"""
        ...
