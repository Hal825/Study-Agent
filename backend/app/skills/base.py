"""
Skill 抽象基类 —— 可组合的能力单元。

Skill 是 Tool 的编排者 + Prompt 的消费者，
介于 Agent Layer 和 Tool Layer 之间。

Agent → Skill → Tool
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph

from app.tools.base import BaseTool
from app.prompts.registry import PromptRegistry


# ============================================================
# Skill 上下文 & 结果
# ============================================================

class SkillContext(BaseModel):
    """Skill 执行的统一上下文。"""
    user_input: str = ""
    user_id: str = "anonymous"
    session_id: str = ""
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillResult(BaseModel):
    """Skill 执行的统一返回。"""
    success: bool
    skill_id: str
    output: Any = None
    intermediate_steps: list[dict] = Field(default_factory=list)
    error: str | None = None


# ============================================================
# 抽象接口
# ============================================================

class BaseSkill(ABC):
    """
    统一 Skill 抽象接口。

    所有 Skill（NoteGen, KnowledgeGraph, QA, FlashCard...）
    必须实现此接口。

    子类需要:
    1. 定义 skill_id / name / description 属性
    2. 声明 required_tools()
    3. 实现 build_graph()
    4. 按需覆写 validate_input()

    依赖注入:
    - inject_dependencies(tools, prompt_registry, llm_service) 由框架调用
    - get_tool(name) 便捷访问注入的 Tool
    """

    # ---- 子类必须定义 ----

    @property
    @abstractmethod
    def skill_id(self) -> str:
        """技能唯一标识，如 note_gen / knowledge_graph / qa_gen"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """技能展示名称，如 笔记生成"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """技能描述"""
        ...

    @abstractmethod
    def required_tools(self) -> list[str]:
        """
        声明本 Skill 依赖的 Tool 名称列表。
        框架在初始化时自动注入 Tool 实例。
        """
        ...

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        构建该 Skill 的 LangGraph 状态图。

        返回已编译的 CompiledStateGraph，
        由 AgentExecutor 调用 astream() 执行。
        """
        ...

    # ---- 可选覆写 ----

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def requires_human_confirm(self) -> bool:
        """是否需要人类确认节点"""
        return False

    def validate_input(self, context: SkillContext) -> Optional[SkillResult]:
        """
        输入校验钩子。
        返回 SkillResult 表示校验失败，
        返回 None 表示校验通过。
        """
        if not context.user_input.strip():
            return SkillResult(
                success=False,
                skill_id=self.skill_id,
                error="输入内容不能为空",
            )
        return None

    # ---- 框架注入（子类不覆写） ----

    _tools: dict[str, BaseTool] = {}
    _prompt_registry: Optional[PromptRegistry] = None
    _llm_service: Optional[Any] = None  # LLMService (避免循环引用)

    def inject_dependencies(
        self,
        tools: dict[str, BaseTool],
        prompt_registry: PromptRegistry,
        llm_service: Any,
    ) -> None:
        """
        由框架在初始化时调用，注入依赖。

        Args:
            tools: {tool_name: ToolInstance} 本 Skill 需要的所有 Tool
            prompt_registry: 全局 Prompt 模板注册中心
            llm_service: 全局 LLM 服务实例
        """
        self._tools = tools
        self._prompt_registry = prompt_registry
        self._llm_service = llm_service

    def get_tool(self, name: str) -> BaseTool:
        """
        获取已注入的 Tool 实例。

        Raises:
            KeyError: Tool 未注入
        """
        if name not in self._tools:
            raise KeyError(
                f"Skill [{self.skill_id}] 需要的 Tool [{name}] 未注入，"
                f"可用: {list(self._tools.keys())}"
            )
        return self._tools[name]

    @property
    def tool_names(self) -> list[str]:
        """已注入的 Tool 名称列表。"""
        return list(self._tools.keys())
