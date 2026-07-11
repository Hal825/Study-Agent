"""
依赖注入容器 —— 组装并持有所有服务实例。

上层（API、Agent）通过 container 获取所需服务，
不直接实例化具体实现。
"""

import os
from dataclasses import dataclass

from app.data.runtime.checkpoint_store import MemoryCheckpointStore
from app.data.runtime.session_store import MemorySessionStore
from app.data.runtime.cache_store import MemoryCacheStore
from app.data.runtime.base import BaseMemoryStore
from app.data.business.repository.note_repo import MemoryNoteRepository
from app.data.business.repository.user_repo import MemoryUserPreferenceRepository
from app.data.interfaces import (
    CheckpointStore, SessionStore, CacheStore,
    NoteRepository, UserPreferenceRepository,
)
from app.data.cleanup import CleanupScheduler
from app.data.unit_of_work import UnitOfWorkFactory

from app.tools.interfaces import IToolRegistry
from app.tools.registry import ToolRegistry
from app.tools.content_parser import ContentParser
from app.tools.entity_extractor import EntityExtractor
from app.tools.structure_analyzer import StructureAnalyzer

from app.prompts.registry import PromptRegistry

from app.services.llm_service import LLMService
from app.services.export_service import ExportService
from app.services.event_bus import EventBus

from app.agent.executor import AgentExecutor


@dataclass
class Container:
    """全局服务容器。"""

    # Data Layer — Runtime
    checkpoint_store: CheckpointStore
    session_store: SessionStore
    cache_store: CacheStore

    # Data Layer — Business
    note_repo: NoteRepository
    user_pref_repo: UserPreferenceRepository

    # Data Layer — Infrastructure
    cleanup_scheduler: CleanupScheduler
    uow_factory: UnitOfWorkFactory

    # Tool Layer
    tool_registry: IToolRegistry

    # Prompt Layer
    prompt_registry: PromptRegistry

    # Service Layer
    llm_service: LLMService
    export_service: ExportService
    event_bus: EventBus

    # Agent Layer
    agent_executor: AgentExecutor

    @classmethod
    def create_dev(cls) -> "Container":
        """创建开发环境容器。"""

        # --- Runtime stores ---
        checkpoint_store = MemoryCheckpointStore()
        session_store = MemorySessionStore()
        cache_store = MemoryCacheStore()

        # --- Business repos ---
        note_repo = MemoryNoteRepository()
        user_pref_repo = MemoryUserPreferenceRepository()

        # --- Services ---
        llm_service = LLMService(cache=cache_store)
        export_service = ExportService()
        event_bus = EventBus()

        # --- Prompt Layer ---
        prompt_registry = cls._build_prompt_registry()

        # --- Tool Layer ---
        tool_registry = cls._build_tool_registry(llm_service)

        # --- Agent Layer ---
        agent_executor = AgentExecutor(
            tool_registry=tool_registry,
            llm_service=llm_service,
            event_bus=event_bus,
        )

        # --- Cleanup scheduler ---
        cleanup = CleanupScheduler(interval_seconds=300)
        for store in [session_store, cache_store]:
            if isinstance(store, BaseMemoryStore):
                cleanup.register(store)

        container = cls(
            checkpoint_store=checkpoint_store,
            session_store=session_store,
            cache_store=cache_store,
            note_repo=note_repo,
            user_pref_repo=user_pref_repo,
            cleanup_scheduler=cleanup,
            uow_factory=UnitOfWorkFactory(None),
            tool_registry=tool_registry,
            prompt_registry=prompt_registry,
            llm_service=llm_service,
            export_service=export_service,
            event_bus=event_bus,
            agent_executor=agent_executor,
        )
        container.uow_factory = UnitOfWorkFactory(container)
        return container

    # ================================================================
    # 子工厂方法
    # ================================================================

    @staticmethod
    def _build_tool_registry(llm_service: LLMService) -> IToolRegistry:
        """组装 Tool 注册中心。"""
        reg = ToolRegistry()
        reg.register(ContentParser())
        reg.register(EntityExtractor(llm_service))
        reg.register(StructureAnalyzer(llm_service))
        return reg

    @staticmethod
    def _build_prompt_registry() -> PromptRegistry:
        """组装 Prompt 注册中心。"""
        # 模板目录相对于 backend/ 运行目录
        templates_dir = os.path.join(
            os.path.dirname(__file__), "prompts", "templates"
        )
        return PromptRegistry(templates_dir)


# 模块级单例
_container: Container | None = None


def get_container() -> Container:
    """获取全局服务容器。"""
    global _container
    if _container is None:
        _container = Container.create_dev()
    return _container


def set_container(container: Container) -> None:
    """注入自定义容器（测试用）。"""
    global _container
    _container = container
