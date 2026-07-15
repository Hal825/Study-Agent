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
from app.tools.vision_preprocessor import VisionPreprocessorTool

from app.prompts.registry import PromptRegistry

from app.skills import SkillRegistry, NoteGenerationSkill

from app.services.llm_service import LLMService
from app.services.export_service import ExportService
from app.services.event_bus import EventBus

from app.agent.executor import AgentExecutor
from app.agent.chat_executor import ChatAgentExecutor


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
    chat_executor: ChatAgentExecutor

    # Skill Layer
    skill_registry: SkillRegistry
    note_gen_skill: NoteGenerationSkill

    # Vision Tool
    vision_tool: VisionPreprocessorTool

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

        # --- Vision Tool ---
        vision_tool = VisionPreprocessorTool(cache_store=cache_store)

        # --- Skill Layer ---
        skill_registry = SkillRegistry()
        note_gen_skill = NoteGenerationSkill()
        tools_dict = {t.name: t for t in tool_registry.list_all()}
        note_gen_skill.inject_dependencies(
            tools=tools_dict,
            prompt_registry=prompt_registry,
            llm_service=llm_service,
        )
        skill_registry.register(note_gen_skill)

        # --- Agent Layer ---
        agent_executor = AgentExecutor(
            tool_registry=tool_registry,
            llm_service=llm_service,
            event_bus=event_bus,
            skill=note_gen_skill,
            note_repo=note_repo,
            user_pref_repo=user_pref_repo,
        )

        # --- Chat Agent ---
        chat_executor = ChatAgentExecutor(
            tool_registry=tool_registry,
            llm_service=llm_service,
            event_bus=event_bus,
            prompt_registry=prompt_registry,
            note_repo=note_repo,
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
            chat_executor=chat_executor,
            skill_registry=skill_registry,
            note_gen_skill=note_gen_skill,
            vision_tool=vision_tool,
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

    @classmethod
    def create_prod(cls) -> "Container":
        """
        创建生产环境容器 —— PostgreSQL + Redis。

        要求先调用 init_database() 和 init_redis() 初始化基础设施。
        """
        from app.data.database import get_session_factory
        from app.data.redis_client import get_redis_client
        from app.data.business.repository.pg_note_repo import PgNoteRepository
        from app.data.business.repository.pg_user_repo import PgUserPreferenceRepository
        from app.data.runtime.redis_cache import RedisCacheStore

        session_factory = get_session_factory()
        redis_client = get_redis_client()

        # --- Runtime stores ---
        checkpoint_store = MemoryCheckpointStore()   # LangGraph 使用自带 MemorySaver
        session_store = MemorySessionStore()          # 会话级，不持久化
        cache_store = RedisCacheStore(redis_client)   # Redis 缓存

        # --- Business repos ---
        note_repo = PgNoteRepository(session_factory)
        user_pref_repo = PgUserPreferenceRepository(session_factory)

        # --- Services ---
        llm_service = LLMService(cache=cache_store)
        export_service = ExportService()
        event_bus = EventBus()

        # --- Prompt Layer ---
        prompt_registry = cls._build_prompt_registry()

        # --- Tool Layer ---
        tool_registry = cls._build_tool_registry(llm_service)

        # --- Vision Tool ---
        vision_tool = VisionPreprocessorTool(cache_store=cache_store)

        # --- Skill Layer ---
        skill_registry = SkillRegistry()
        note_gen_skill = NoteGenerationSkill()
        tools_dict = {t.name: t for t in tool_registry.list_all()}
        note_gen_skill.inject_dependencies(
            tools=tools_dict,
            prompt_registry=prompt_registry,
            llm_service=llm_service,
        )
        skill_registry.register(note_gen_skill)

        # --- Agent Layer ---
        agent_executor = AgentExecutor(
            tool_registry=tool_registry,
            llm_service=llm_service,
            event_bus=event_bus,
            skill=note_gen_skill,
            note_repo=note_repo,
            user_pref_repo=user_pref_repo,
        )

        # --- Chat Agent ---
        chat_executor = ChatAgentExecutor(
            tool_registry=tool_registry,
            llm_service=llm_service,
            event_bus=event_bus,
            prompt_registry=prompt_registry,
            note_repo=note_repo,
        )

        # --- Cleanup scheduler (仅注册内存存储) ---
        cleanup = CleanupScheduler(interval_seconds=300)
        for store in [session_store, checkpoint_store]:
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
            chat_executor=chat_executor,
            skill_registry=skill_registry,
            note_gen_skill=note_gen_skill,
            vision_tool=vision_tool,
        )
        container.uow_factory = UnitOfWorkFactory(container)
        return container

    @classmethod
    def create(cls) -> "Container":
        """根据 APP_ENV 自动选择开发/生产容器。"""
        app_env = os.getenv("APP_ENV", "development")
        if app_env == "production":
            return cls.create_prod()
        return cls.create_dev()


# 模块级单例
_container: Container | None = None


def get_container() -> Container:
    """获取全局服务容器（根据 APP_ENV 自动选择模式）。"""
    global _container
    if _container is None:
        _container = Container.create()
    return _container


def set_container(container: Container) -> None:
    """注入自定义容器（测试用）。"""
    global _container
    _container = container
