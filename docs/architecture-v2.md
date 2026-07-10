# Study-Agent V2 架构设计

> 从线性 Workflow 重构为 LangGraph Agent 架构。

---

## 1. 分层总览

```
┌──────────────────────────────────────────────────────────┐
│  Agent Layer        LangGraph 图 · 状态机 · 条件分支     │
│                     Human-in-the-loop · Checkpoint        │
├──────────────────────────────────────────────────────────┤
│  Skill Layer        可组合的能力单元                       │
│                     NoteGen · KnowledgeGraph · QA · Card  │
├────────────────────┬─────────────────────────────────────┤
│  Prompt Layer      │  Tool Layer                         │
│  模板管理           │  原子操作                            │
│  动态构造           │  内容解析 · 实体抽取 · 搜索 · 渲染   │
│  版本控制           │  统一 BaseTool 父类                   │
├────────────────────┴─────────────────────────────────────┤
│  Service Layer     LLM · Export · RAG · EventBus(SSE)    │
├──────────────────────────────────────────────────────────┤
│  Data Layer        Runtime (Redis/Checkpoint)            │
│                    Business (PostgreSQL/持久化)            │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 依赖规则 —— 杜绝反向跨层依赖

### 2.1 依赖方向矩阵

```
        Agent  Skill  Prompt  Tool  Service  Data
Agent     -      ↓      ↓      ✗      ✗       ✗
Skill     ✗      -      ↓      ↓      ✗       ✗
Prompt    ✗      ✗      -      ✗      ✗       ✗
Tool      ✗      ✗      ✗      -      ✗       ✗
Service   ✗      ✗      ✗      ✗      -       ↓
Data      ✗      ✗      ✗      ✗      ✗       -
```

- `↓` = 允许依赖（调用/导入）
- `✗` = 禁止依赖
- `-` = 自身

### 2.2 逐条解释

| 规则 | 说明 |
|------|------|
| **Agent → Skill** | Agent 图节点调用 Skill 执行具体任务 |
| **Agent → Prompt** | Agent 的 SystemMessage 从 Prompt 层获取 |
| **Agent → Tool** | ❌ 禁止 —— Agent 不直接调 Tool，必须经过 Skill |
| **Skill → Prompt** | Skill 组合 Tool 结果 + Prompt 模板构造 LLM 请求 |
| **Skill → Tool** | Skill 编排多个 Tool 的执行顺序 |
| **Skill → Service** | ❌ 禁止 —— Skill 不直接调 LLM，通过 Tool 间接 |
| **Prompt → Tool** | ❌ 禁止 —— Prompt 不能 import Tool 实现；但可以**字符串引用** Tool 的 name/description（用于构造 tool-use prompt） |
| **Prompt → 任何其他层** | ❌ 禁止 —— Prompt 层是纯数据 + 模板，不能有任何运行时依赖 |
| **Tool → Prompt** | ❌ 禁止 —— Tool 是无状态的原子操作，不感知提示词 |
| **Tool → Service** | ❌ 允许部分：需要 LLM 的 Tool（如 `SummarizeChunk`）通过注入的 `LLMService` 接口调用，不直接依赖具体实现 |
| **Service → Data** | Service 读写 Data 层的持久化存储 |
| **Data → 任何业务层** | ❌ 禁止 —— Data 层是纯存储，不包含业务逻辑 |

### 2.3 反模式警示

```python
# ❌ 禁止：Tool 直接 import Prompt
from app.prompts import NOTE_PROMPTS  # 违反规则！

# ❌ 禁止：Prompt 直接 import Tool
from app.tools import ContentParser    # 违反规则！

# ✅ 正确：Skill 同时依赖 Tool 和 Prompt
from app.tools import ContentParser
from app.prompts import PromptRegistry

# ✅ 正确：Prompt 以字符串形式引用 Tool
TOOL_PROMPT_TEMPLATE = """
可用工具：
{tool_descriptions}   <!-- 运行时由 Skill 注入，Prompt 层不 import -->
"""
```

---

## 3. Tool Layer —— 统一父类

### 3.1 设计目标

- 所有 Tool 继承同一个抽象基类
- 通用校验、异常处理、日志、超时控制由父类统一实现
- 子类只需实现 `execute()` 核心逻辑
- 输入/输出用 Pydantic 模型约束，类型安全

### 3.2 核心定义

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, ValidationError
from dataclasses import dataclass, field
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)

# ---- 泛型类型变量 ----
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

# ---- 统一结果 ----
class ToolStatus(str, Enum):
    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"

@dataclass
class ToolResult(Generic[OutputT]):
    status: ToolStatus
    data: Optional[OutputT] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    @classmethod
    def success(cls, data: OutputT, duration_ms: float = 0) -> "ToolResult[OutputT]":
        return cls(status=ToolStatus.SUCCESS, data=data, duration_ms=duration_ms)

    @classmethod
    def failure(cls, status: ToolStatus, error: str) -> "ToolResult[OutputT]":
        return cls(status=status, error=error)

    @property
    def ok(self) -> bool:
        return self.status == ToolStatus.SUCCESS

# ---- 抽象基类 ----
class BaseTool(ABC, Generic[InputT, OutputT]):
    """
    统一 Tool 抽象父类。

    子类需要：
    1. 定义 `name` / `description`（类属性或属性方法）
    2. 定义 `input_schema` / `output_schema`（Pydantic 模型）
    3. 实现 `execute()` 核心逻辑
    """

    # ---- 子类必须定义 ----
    name: str
    description: str

    @property
    @abstractmethod
    def input_schema(self) -> type[InputT]:
        """输入参数的 Pydantic 模型类"""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> type[OutputT]:
        """返回值的 Pydantic 模型类"""
        ...

    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT:
        """
        核心执行逻辑。由子类实现。

        此时输入已通过校验，异常会被父类统一捕获。
        """
        ...

    # ---- 可覆写的钩子 ----
    def validate(self, input_data: InputT) -> InputT:
        """
        子类可覆写的业务校验钩子。
        父类已通过 Pydantic 做了 schema 校验，这里做额外的业务规则校验。
        抛出 ValidationError 会被 run() 捕获并返回 ToolStatus.VALIDATION_ERROR。
        """
        return input_data

    @property
    def timeout_seconds(self) -> float:
        """子类可覆写超时时间，默认 30s"""
        return 30.0

    @property
    def retry_count(self) -> int:
        """子类可覆写重试次数，默认 0（不重试）"""
        return 0

    # ---- 父类统一入口（子类不要覆写） ----
    async def run(self, input_data: InputT) -> ToolResult[OutputT]:
        """
        统一执行入口：校验 → 执行 → 异常处理 → 耗时统计 → 日志。

        这是外部调用 Tool 的唯一入口，子类不应覆写此方法。
        """
        start = time.perf_counter()

        # 1. Pydantic schema 校验（自动）
        #    input_data 本身已经是 InputT 实例，Pydantic 在构造时已完成校验
        #    如果调用方传 dict，需要在调用前手动构造

        # 2. 业务校验钩子
        try:
            validated = self.validate(input_data)
        except ValidationError as e:
            duration = (time.perf_counter() - start) * 1000
            logger.warning(f"[{self.name}] 校验失败: {e}")
            return ToolResult.failure(ToolStatus.VALIDATION_ERROR, str(e))

        # 3. 执行（带超时 + 重试）
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                result = await self._execute_with_timeout(validated)
                duration = (time.perf_counter() - start) * 1000
                logger.info(f"[{self.name}] 成功, 耗时 {duration:.0f}ms")
                return ToolResult.success(result, duration_ms=duration)
            except TimeoutError:
                last_error = f"Tool [{self.name}] 超时 ({self.timeout_seconds}s)"
                logger.warning(f"[{self.name}] 超时, attempt {attempt + 1}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"[{self.name}] 异常, attempt {attempt + 1}: {e}")
                if attempt == self.retry_count:
                    break

        duration = (time.perf_counter() - start) * 1000
        status = ToolStatus.TIMEOUT if isinstance(last_error, str) and "超时" in last_error else ToolStatus.EXECUTION_ERROR
        return ToolResult.failure(status, last_error or "未知错误")

    async def _execute_with_timeout(self, input_data: InputT) -> OutputT:
        """内部超时控制"""
        import asyncio
        return await asyncio.wait_for(
            self.execute(input_data),
            timeout=self.timeout_seconds,
        )
```

### 3.3 子类示例

```python
class ContentParseOutput(BaseModel):
    """内容解析 Tool 的输出"""
    title: str = ""
    sections: list[dict] = []
    total_words: int = 0
    language: str = "zh"

class ContentParser(BaseTool[BaseModel, ContentParseOutput]):
    name = "content_parser"
    description = "解析用户上传的学习内容，提取标题、章节结构和统计信息"

    @property
    def input_schema(self) -> type[BaseModel]:
        # 输入就是原始文本，用简单模型包装
        class _Input(BaseModel):
            content: str
            filename: str = ""
        return _Input

    @property
    def output_schema(self) -> type[ContentParseOutput]:
        return ContentParseOutput

    @property
    def timeout_seconds(self) -> float:
        return 10.0  # 纯本地解析，超时设置短一些

    async def execute(self, input_data) -> ContentParseOutput:
        # 核心解析逻辑
        ...
```

### 3.4 Tool Registry

```python
class ToolRegistry:
    """Tool 注册中心：按名称查找 Tool 实例"""

    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        if tool.name in cls._tools:
            raise ValueError(f"Tool [{tool.name}] 已注册")
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> BaseTool:
        if name not in cls._tools:
            raise KeyError(f"Tool [{name}] 未注册")
        return cls._tools[name]

    @classmethod
    def list_all(cls) -> list[BaseTool]:
        return list(cls._tools.values())
```

---

## 4. Prompt Layer —— 位置与约束

### 4.1 设计定位

Prompt 层是**纯数据 + 模板层**，不包含任何运行时逻辑、不 import 任何其他层的实现代码。

```
Prompt Layer
├── templates/          # 静态模板文件（Markdown/YAML/文本）
│   ├── note/
│   │   ├── outline.md
│   │   ├── summary.md
│   │   ├── cornell.md
│   │   └── qa.md
│   └── system/
│       └── base_agent.md
├── registry.py         # PromptRegistry: 加载、缓存、按 key 获取模板
├── builder.py          # PromptBuilder: 运行时填充变量（纯字符串操作）
└── schemas.py          # PromptTemplate 的 Pydantic 模型定义
```

### 4.2 合法与禁止

```python
# ✅ 合法：PromptBuilder 做纯字符串操作
class PromptBuilder:
    def build(self, template: str, variables: dict[str, str]) -> str:
        return template.format(**variables)

# ✅ 合法：PromptRegistry 从文件加载模板
class PromptRegistry:
    def get(self, key: str) -> str:
        return self._cache[key]

# ❌ 禁止：import 任何 Tool 实现
from app.tools import ContentParser   # 编译报错！

# ❌ 禁止：import 任何 Service
from app.services import LLMService   # 编译报错！

# ✅ 合法：模板内容中用字符串引用 Tool 名称
PROMPT = """
你可以使用以下工具：{tool_names}
"""
# tool_names 由 Skill 层在运行时填充，Prompt 层不关心具体值
```

### 4.3 Tool 描述信息的传递方式

Prompt 层需要知道有哪些 Tool 可用时，由 **Skill 层** 负责收集 Tool 的 name + description，拼接后注入 Prompt：

```python
# 这段逻辑属于 Skill 层，不属于 Prompt 层
class NoteGenerationSkill(BaseSkill):
    def _build_system_prompt(self) -> str:
        template = self.prompt_registry.get("note/base")
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in self.tools()
        )
        return template.format(tool_descriptions=tool_descriptions)
```

---

## 5. Skill Layer —— 统一抽象接口

### 5.1 设计目标

- 所有 Skill 实现同一个抽象接口，避免后期每个 Skill 实现方式不同造成维护灾难
- Skill 是 **Tool 的编排者 + Prompt 的消费者**
- 每个 Skill 返回一个 **LangGraph 子图**（`CompiledStateGraph`），由 Agent 层组合或直接挂载

### 5.2 核心定义

```python
from abc import ABC, abstractmethod
from typing import Any
from langgraph.graph import StateGraph

# ---- Skill 上下文 ----
class SkillContext(BaseModel):
    """Skill 执行的统一上下文"""
    user_input: str                          # 用户原始输入
    user_id: str = "anonymous"               # 用户 ID
    session_id: str = ""                     # 会话 ID
    user_preferences: dict[str, Any] = {}    # 用户偏好（从 Business Data 读取）
    metadata: dict[str, Any] = {}            # 额外元数据

# ---- Skill 执行结果 ----
class SkillResult(BaseModel):
    """Skill 执行的统一返回"""
    success: bool
    skill_id: str
    output: Any = None                # 核心输出（类型由具体 Skill 定义）
    intermediate_steps: list[dict] = []  # 中间步骤记录（用于前端展示）
    error: str | None = None

# ---- 抽象接口 ----
class BaseSkill(ABC):
    """
    统一 Skill 抽象接口。

    所有 Skill（NoteGen, KnowledgeGraph, QA, FlashCard...）
    必须实现以下方法。
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

        返回未编译的 StateGraph，由 Agent 层统一编译
        （或 Skill 内部自行编译后返回 CompiledStateGraph）。
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

    def validate_input(self, context: SkillContext) -> SkillResult | None:
        """
        输入校验钩子。返回 SkillResult 表示校验失败，
        返回 None 表示校验通过。
        """
        if not context.user_input.strip():
            return SkillResult(
                success=False, skill_id=self.skill_id,
                error="输入内容不能为空"
            )
        return None

    # ---- 框架注入（子类不覆写） ----
    _tools: dict[str, "BaseTool"] = {}
    _prompt_registry: "PromptRegistry" = None
    _llm_service: "LLMService" = None

    def inject_dependencies(
        self,
        tools: dict[str, "BaseTool"],
        prompt_registry: "PromptRegistry",
        llm_service: "LLMService",
    ) -> None:
        """由框架在初始化时调用，注入依赖"""
        self._tools = tools
        self._prompt_registry = prompt_registry
        self._llm_service = llm_service

    def get_tool(self, name: str) -> "BaseTool":
        """获取已注入的 Tool 实例"""
        if name not in self._tools:
            raise KeyError(f"Skill [{self.skill_id}] 需要的 Tool [{name}] 未注入")
        return self._tools[name]
```

### 5.3 Skill Registry

```python
class SkillRegistry:
    """Skill 注册中心"""

    _skills: dict[str, BaseSkill] = {}

    @classmethod
    def register(cls, skill: BaseSkill) -> None:
        if skill.skill_id in cls._skills:
            raise ValueError(f"Skill [{skill.skill_id}] 已注册")
        cls._skills[skill.skill_id] = skill

    @classmethod
    def get(cls, skill_id: str) -> BaseSkill:
        if skill_id not in cls._skills:
            raise KeyError(f"Skill [{skill_id}] 未注册")
        return cls._skills[skill_id]

    @classmethod
    def list_all(cls) -> list[BaseSkill]:
        return list(cls._skills.values())
```

### 5.4 子类示例

```python
class NoteGenerationSkill(BaseSkill):

    @property
    def skill_id(self): return "note_gen"

    @property
    def name(self): return "笔记生成"

    @property
    def description(self): return "上传学习内容，选择笔记模板，生成结构化笔记"

    @property
    def requires_human_confirm(self): return True  # 需要用户确认模板选择

    def required_tools(self) -> list[str]:
        return ["content_parser", "entity_extractor", "structure_analyzer", "template_renderer"]

    def build_graph(self) -> StateGraph:
        # 定义 NoteGen 的 LangGraph 子图
        builder = StateGraph(NoteGenState)

        builder.add_node("parse", self._parse_node)
        builder.add_node("extract", self._extract_node)
        builder.add_node("confirm_template", self._human_confirm_node)  # interrupt
        builder.add_node("generate", self._generate_node)

        builder.add_edge(START, "parse")
        builder.add_edge("parse", "extract")
        builder.add_edge("extract", "confirm_template")
        builder.add_edge("confirm_template", "generate")
        builder.add_edge("generate", END)

        return builder

    # ... 节点实现方法
```

---

## 6. Data Layer —— 运行时 vs 业务存储

### 6.1 拆分原则

| 维度 | Runtime（运行时） | Business（业务） |
|------|-------------------|-------------------|
| **生命周期** | 单次会话 / 单次 Agent 执行 | 跨会话持久化 |
| **存储后端** | Redis（或 MemorySaver for dev） | PostgreSQL（或 SQLite for dev） |
| **数据内容** | LangGraph checkpoint、agent 中间状态、SSE 连接状态、当前步骤缓存 | 用户档案、历史笔记、知识库、偏好设置 |
| **读写模式** | 高频写入、低延迟读取 | 低频读写、需要索引和查询 |
| **是否可丢失** | 是（丢失后用户需重新开始当前任务） | 否（用户的核心数据） |

### 6.2 模块结构

```
Data Layer
├── runtime/
│   ├── __init__.py
│   ├── checkpoint_store.py    # LangGraph Checkpoint 存储适配
│   │                           #   - dev:  MemorySaver (内存)
│   │                           #   - prod: RedisSaver / PostgresSaver
│   ├── session_store.py        # 当前会话临时状态
│   │                           #   - 用户当前在哪一步
│   │                           #   - 中间结果缓存
│   │                           #   - SSE channel 映射
│   └── cache_store.py          # 热点数据缓存
│                               #   - LLM 响应缓存（相同输入去重）
│                               #   - Token 计数缓存
│
├── business/
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy / Pydantic 数据模型
│   │   ├── User                # 用户
│   │   ├── UserPreference      # 用户偏好（喜欢的模板、知识水平...）
│   │   ├── StudyNote           # 生成的笔记（替代前端 localStorage）
│   │   ├── KnowledgeCard       # 知识卡片（远期）
│   │   └── LearningSession     # 学习会话记录
│   ├── repository/
│   │   ├── user_repo.py        # 用户数据访问
│   │   ├── note_repo.py        # 笔记 CRUD
│   │   └── session_repo.py     # 学习会话 CRUD
│   └── migrations/             # Alembic 数据库迁移
│
└── interfaces.py               # 抽象接口（Repository Pattern）
                                 # 业务层依赖接口，不依赖具体实现
```

### 6.3 关键接口

```python
# ---- Runtime 接口 ----
class CheckpointStore(ABC):
    """LangGraph checkpoint 存储抽象"""
    @abstractmethod
    async def put(self, thread_id: str, checkpoint: dict) -> None: ...
    @abstractmethod
    async def get(self, thread_id: str) -> dict | None: ...
    @abstractmethod
    async def list_threads(self, user_id: str) -> list[str]: ...

class SessionStore(ABC):
    """会话临时状态存储"""
    @abstractmethod
    async def get_state(self, session_id: str, key: str) -> Any: ...
    @abstractmethod
    async def set_state(self, session_id: str, key: str, value: Any, ttl: int = 3600) -> None: ...

# ---- Business 接口 ----
class NoteRepository(ABC):
    """笔记持久化（Repository Pattern）"""
    @abstractmethod
    async def save(self, user_id: str, note: StudyNote) -> str: ...
    @abstractmethod
    async def get(self, note_id: str) -> StudyNote | None: ...
    @abstractmethod
    async def list_by_user(self, user_id: str, limit: int = 50) -> list[StudyNote]: ...
    @abstractmethod
    async def delete(self, note_id: str) -> bool: ...

class UserPreferenceRepository(ABC):
    """用户偏好存取"""
    @abstractmethod
    async def get(self, user_id: str) -> UserPreference: ...
    @abstractmethod
    async def update(self, user_id: str, prefs: dict) -> None: ...
```

### 6.4 依赖注入到上层

```python
# Service 层通过接口依赖 Data 层，不依赖具体实现
class LLMService:
    def __init__(self, cache: CacheStore, note_repo: NoteRepository):
        self._cache = cache          # Runtime
        self._note_repo = note_repo  # Business

# Agent 层依赖 Runtime Data（checkpoint）
# 在 LangGraph 编译时注入 checkpointer
graph = builder.compile(checkpointer=checkpoint_store)
```

---

## 7. 完整依赖关系图

```
                        ┌──────────────┐
                        │ Agent Layer  │
                        └──┬───┬───┬──┘
                           │   │   │
              ┌────────────┘   │   └────────────┐
              ▼                ▼                ▼
        ┌──────────┐   ┌──────────────┐   ┌──────────┐
        │  Skill   │──▶│ Prompt Layer │   │  Agent   │
        │  Layer   │   │ (纯模板数据)  │   │  直接    │
        └────┬─────┘   └──────────────┘   │  依赖    │
             │                             │ Prompt   │
             ▼                             └──────────┘
        ┌──────────┐
        │  Tool    │
        │  Layer   │
        └────┬─────┘
             │ (LLM Tool 通过接口注入)
             ▼
        ┌──────────────┐
        │Service Layer │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │  Data Layer  │
        │ ┌──────────┐ │
        │ │ Runtime  │ │
        │ ├──────────┤ │
        │ │ Business │ │
        │ └──────────┘ │
        └──────────────┘

横向关系：
  Prompt Layer ←→ Tool Layer : 互不依赖，平级独立
  Skill Layer : 同时依赖 Prompt 和 Tool，负责协调两者
```

---

## 8. 迁移路径

### Phase 1：Data Layer + Service Layer 重构
- 拆分 Runtime / Business 存储
- LLMService 统一封装（支持 DeepSeek，预留 Qwen）
- ExportService 保留现有代码
- 新增 EventBus（SSE）基础设施

### Phase 2：Tool Layer + Prompt Layer
- 实现 BaseTool 父类 + ToolRegistry
- 将现有 `prompts/note.py` 迁移为 PromptRegistry
- 实现首批 Tool：ContentParser、EntityExtractor、StructureAnalyzer

### Phase 3：Skill Layer
- 实现 BaseSkill 接口 + SkillRegistry
- 实现 NoteGenerationSkill（替代现有 `agent.py` 的单 API 调用）
- SSE 改造：前端 AgentProgress 从模拟动画变为真实状态订阅

### Phase 4：Agent Layer
- LangGraph 图构建
- Human-in-the-loop 节点（模板确认、结果审查）
- Checkpoint 持久化

### Phase 5：扩展
- KnowledgeGraphSkill、QASkill、FlashCardSkill
- RAG 检索增强
- 间隔复习调度

---

## 9. 关键技术决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | LangGraph | 状态图天然适合学习流程、human-in-the-loop 需要 |
| LLM 调用方式 | 通过 Tool 封装 + Service 注入 | Tool 不直接依赖 LLM，保持可测试性 |
| 前端通信 | SSE（Server-Sent Events） | 单向推送 Agent 状态，实现简单；不需要 WebSocket 的双向 |
| Checkpoint 存储 | dev: MemorySaver, prod: Redis | 渐进式，先跑通再持久化 |
| 业务存储 | PostgreSQL（已有 docker-compose） | 复用现有基础设施 |
| 依赖注入 | 构造函数注入（手动） | 不需要 DI 框架，Python 显式优于隐式 |
