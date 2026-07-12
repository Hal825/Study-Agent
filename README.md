# Study Agent 后端架构文档

> 从入口到每一层：FastAPI + LangGraph + 手动 DI 容器的完整后端剖析。

---

## 目录

1. [整体分层架构](#1-整体分层架构)
2. [入口点 —— main.py](#2-入口点--mainpy)
3. [依赖注入容器 —— container.py](#3-依赖注入容器--containerpy)
4. [Data Layer —— 数据层](#4-data-layer--数据层)
5. [LLM Layer —— LLM 客户端层](#5-llm-layer--llm-客户端层)
6. [Prompt Layer —— Prompt 层](#6-prompt-layer--prompt-层)
7. [Tool Layer —— 工具层](#7-tool-layer--工具层)
8. [Agent Layer —— Agent 层](#8-agent-layer--agent-层)
9. [Service Layer —— 服务层](#9-service-layer--服务层)
10. [API Layer —— API 层](#10-api-layer--api-层)
11. [完整请求链路](#11-完整请求链路)
12. [设计亮点总结](#12-设计亮点总结)
13. [文件清单](#13-文件清单)

---

## 1. 整体分层架构

```
┌─────────────────────────────────────────────────┐
│  API Layer (api/)          HTTP 端点             │
├─────────────────────────────────────────────────┤
│  Agent Layer (agent/)      LangGraph 状态图       │
├─────────────────────────────────────────────────┤
│  Service Layer (services/)  业务服务              │
├──────────────────┬──────────────────────────────┤
│  Tool Layer      │  Prompt Layer                │
│  (tools/)        │  (prompts/)                  │
├──────────────────┴──────────────────────────────┤
│  LLM Layer (llm/)  DeepSeek Client              │
├─────────────────────────────────────────────────┤
│  Data Layer (data/)  存储 + 仓库                 │
└─────────────────────────────────────────────────┘
```

### 分层职责

| 层 | 职责 | 依赖方向 |
|----|------|---------|
| **API** | 请求校验、HTTP 响应构造、SSE 流式推送 | → Agent / Service |
| **Agent** | LangGraph 状态图编排，5 节点流水线 | → Tool / Service / Prompt |
| **Service** | LLM 调用、文档导出、事件总线 | → LLM / Data |
| **Tool** | 原子操作：内容解析、实体提取、结构分析 | → LLM Service |
| **Prompt** | 模板加载、变量填充、兼容层 | — |
| **LLM** | DeepSeek API 客户端封装 | — |
| **Data** | Runtime 临时存储 + Business 持久化 | — |

每层只依赖下一层的抽象接口，不依赖具体实现。

---

## 2. 入口点 —— main.py

路径：`backend/app/main.py`

### 启动流程

```
1. load_dotenv()           → 加载 ../../.env (DEEPSEEK_API_KEY 等)
2. lifespan 启动:
   a. get_container()      → 创建全局 DI 容器
   b. 打印可用模型
   c. cleanup_scheduler.start() → 启动后台清理（每 300s）
3. FastAPI 应用:
   a. CORS 中间件 (允许 localhost:5173)
   b. 挂载路由: agent_router + export_router
4. lifespan 关闭:
   a. cleanup_scheduler.stop()
```

### 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | —（必须设置） |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 默认模型 | `deepseek-chat` |

### 路由一览

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/agent/note` | 同步生成笔记 |
| `POST` | `/api/agent/note/stream` | SSE 流式生成笔记 |
| `POST` | `/api/export` | 导出 DOCX/PDF |

---

## 3. 依赖注入容器 —— container.py

路径：`backend/app/container.py`

### Container 数据类

持有全部服务实例（手动 DI，无框架依赖）：

| 领域 | 实例 | 类型（接口） | 职责 |
|------|------|-------------|------|
| Runtime Data | `checkpoint_store` | `CheckpointStore` | LangGraph checkpoint 持久化 |
| Runtime Data | `session_store` | `SessionStore` | 会话临时状态 |
| Runtime Data | `cache_store` | `CacheStore` | LLM 响应缓存 |
| Business Data | `note_repo` | `NoteRepository` | 笔记 CRUD |
| Business Data | `user_pref_repo` | `UserPreferenceRepository` | 用户偏好 |
| Infrastructure | `cleanup_scheduler` | `CleanupScheduler` | 后台过期清理 |
| Infrastructure | `uow_factory` | `UnitOfWorkFactory` | 工作单元工厂 |
| Tool | `tool_registry` | `IToolRegistry` | Tool 注册中心 |
| Prompt | `prompt_registry` | `PromptRegistry` | Prompt 模板注册中心 |
| Service | `llm_service` | `LLMService` | LLM 调用 |
| Service | `export_service` | `ExportService` | 文档导出 |
| Service | `event_bus` | `EventBus` | SSE 事件推送 |
| Agent | `agent_executor` | `AgentExecutor` | LangGraph 执行器 |

### 创建流程 `create_dev()`

```
1. new MemoryCheckpointStore()
2. new MemorySessionStore()
3. new MemoryCacheStore()
4. new MemoryNoteRepository()
5. new MemoryUserPreferenceRepository()
6. new LLMService(cache=cache_store)        ← 注入缓存
7. new ExportService()
8. new EventBus()
9. _build_prompt_registry()                 ← 从 templates/ 加载 .md
10. _build_tool_registry(llm_service)       ← 注册 3 个 Tool
11. new AgentExecutor(tool_registry, llm_service, event_bus)
12. new CleanupScheduler(300s)              ← 注册 session/cache store
13. 组装成 Container 实例
```

### 子工厂方法

```python
_build_tool_registry(llm_service):
    reg = ToolRegistry()
    reg.register(ContentParser())            # 纯本地
    reg.register(EntityExtractor(llm))       # LLM 驱动
    reg.register(StructureAnalyzer(llm))     # 混合模式

_build_prompt_registry():
    templates_dir = "app/prompts/templates"
    return PromptRegistry(templates_dir)     # 加载 templates/note/*.md
```

### 单例模式

模块级 `_container` + `get_container()` 惰性初始化，保证环境变量在 `load_dotenv()` 之后才被读取。测试可通过 `set_container()` 注入 mock 容器。

---

## 4. Data Layer —— 数据层

### 4.1 抽象接口：`data/interfaces.py`

定义所有存储的抽象接口，上层只依赖这些 ABC：

| 接口 | 用途 | 核心方法 |
|------|------|---------|
| `CheckpointStore` | LangGraph checkpoint | `put`, `get`, `get_by_id`, `list_checkpoints`, `delete_thread` |
| `SessionStore` | 会话临时 KV | `get`, `set(key, value, ttl)`, `delete`, `clear_session` |
| `CacheStore` | 热点数据缓存 | `get`, `set(key, value, ttl)`, `delete`, `exists` |
| `NoteRepository` | 笔记 CRUD | `save`, `get`, `list_by_user`, `delete`, `count_by_user` |
| `UserPreferenceRepository` | 用户偏好 | `get`, `update`, `reset` |

同时定义数据模型：

```python
class CheckpointEntry(BaseModel):
    thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
    channel_values, metadata

class StudyNote(BaseModel):
    id, user_id, title, template, content, source_content, created_at

class UserPreference(BaseModel):
    user_id, preferred_template, preferred_depth, language,
    enable_auto_save, metadata
```

### 4.2 异常体系：`data/exceptions.py`

```
StorageError (根异常，携带 store_name / operation / detail)
├── StoreNotFoundError      → get/delete 找不到数据（非系统故障）
├── StoreWriteError         → put/set/save 失败
├── StoreConnectionError    → 外部存储不可达（生产环境预留）
├── StoreTimeoutError       → 操作超时
└── StoreIntegrityError     → 数据完整性约束违反
```

设计原则：
- **分层语义，逐级具体**：上层可以 `except StorageError`（最粗）或 `except StoreNotFoundError`（最细）
- **链路保留**：`raise StoreNotFoundError(...) from e`，栈追踪不中断

### 4.3 Runtime 存储基类：`data/runtime/base.py`

`BaseMemoryStore` — 模板方法模式，子类只需覆写钩子方法：

```
对外暴露 (带锁 + 日志 + 异常):
  get() → _get_impl()
  set() → _set_impl()
  delete() → _delete_impl()
  clear() → _clear_impl()
  cleanup() → _cleanup_expired()
```

**`_locked_context` 核心机制**：

```python
@asynccontextmanager
async def _locked_context(self, operation, key):
    start = time.perf_counter()
    async with self._lock:       # asyncio.Lock 互斥
        yield                    # 执行子类实现
    elapsed = ...                # 记录耗时
    if elapsed > 100ms → WARNING (慢操作告警)
    elif elapsed > 10ms → DEBUG
```

### 4.4 具体实现

**`MemoryCheckpointStore`**：
- 数据结构：`thread_id → ns → list[CheckpointEntry]`
- `put`：追加或覆盖（同名 checkpoint_id 替换）
- `get`：返回最新一条

**`MemorySessionStore`**：
- 数据结构：`session_id → key → (value, expires_at)`
- 双重 TTL 清理：惰性清理（get 时）+ 主动清理（`_cleanup_expired` 全量扫描）

**`MemoryCacheStore`**：
- 数据结构：`key → (value, expires_at)`
- 同样支持 TTL + 双轨清理

### 4.5 Business 存储基类：`data/business/base.py`

`BaseBusinessRepository[ModelT]` — 泛型基类，和 BaseMemoryStore 同样的模式：

| 方法 | 子类钩子 |
|------|---------|
| `save(model) → id` | `_save_impl(model) → id` |
| `get(entity_id) → ModelT` | `_get_impl(entity_id) → ModelT` |
| `delete(entity_id) → bool` | `_delete_impl(entity_id) → bool` |
| `list_by_user(user_id, limit, offset)` | `_list_impl(...)` |
| `count_by_user(user_id) → int` | `_count_impl(user_id) → int` |

**`MemoryNoteRepository`**：
- ID 生成：`note_{timestamp}_{hash}`
- `list_by_user`：按 `created_at` 倒序、分页

**`MemoryUserPreferenceRepository`**：
- `get` 不存在时自动返回默认 `UserPreference`
- `update`：部分更新（merge 现有值）

### 4.6 接口-实现分离

```
interfaces.py          ← 抽象接口（上层依赖）
    ↑
    │  实现
    │
runtime/session_store.py  ← 具体实现（容器注入时选择）
```

上层代码（Agent、API）永远只 import `interfaces.py`，不感知底层是内存还是 Redis/PostgreSQL。切换存储后端只需改 `Container` 工厂方法。

### 4.7 UnitOfWork：`data/unit_of_work.py`

**补偿事务模式**，保证跨存储写入的原子性：

```
async with UnitOfWork.from_container(container) as uow:
    await uow.save_checkpoint(...)   # 写入 + 注册补偿: remove
    await uow.save_note(note)        # 写入 + 注册补偿: delete
# 正常退出 → 补偿丢弃
# 异常退出 → LIFO 逆序执行补偿
```

核心实现：

```python
async def __aexit__(self, exc_type, exc_val, exc_tb):
    if exc_type is not None:
        await self._rollback()       # 逆序执行所有补偿
    else:
        self._compensations.clear()  # 丢弃补偿
    return False                     # 不吞异常
```

补偿失败**不阻断**后续补偿，单个补偿异常不影响其他补偿执行。

### 4.8 CleanupScheduler：`data/cleanup.py`

解决惰性清理导致过期数据永驻内存的问题：

```
主动扫描（CleanupScheduler）      惰性清理（get 时触发）
         │                               │
         ▼                               ▼
  每 300s 遍历全部数据           访问时检查 expires_at
  批量清除过期条目               单条删除
         │                               │
         └───────────┬───────────────────┘
                     ▼
           保证过期数据最终被清除
```

设计决策：
- `asyncio.sleep` 而非 `time.sleep`：不阻塞 event loop
- 异常隔离：单个 store 清理失败不影响其他
- `run_once()` 手动触发接口用于调试

---

## 5. LLM Layer —— LLM 客户端层

### 5.1 旧版兼容模块：`llm/deepseek.py`

模块级单例 `_client`，惰性初始化。`generate_note(content, template_id)` 直接调用 DeepSeek。**已被 `services/llm_service.py` 取代**，保留用于兼容。

### 5.2 新版统一 LLM 服务：`services/llm_service.py`

核心架构：

```
BaseLLMProvider (ABC)          ← Provider 抽象
    └── DeepSeekProvider       ← OpenAI 兼容接口

LLMService                     ← 统一入口
    ├── 管理多个 Provider
    ├── 请求缓存（MD5 → CacheStore）
    └── 统一接口 generate(LLMRequest)
```

**数据类型**：

```python
LLMRequest:
    system_prompt, user_message, model, temperature(0.7), max_tokens(4096)

LLMResponse:
    content, model, usage({prompt/completion/total_tokens}),
    duration_ms, cached(bool)
```

**缓存机制**：

```python
cache_key = f"llm:{md5(model + system[:200] + user[:200])}"
# 命中 → 直接返回，设置 cached=True
# 未命中 → 调用 provider → 写入缓存 (TTL=300s)
```

**Provider 解析**：根据 model 名匹配 provider（`deepseek-chat` → `DeepSeekProvider`）

**`generate_legacy()`**：兼容旧版，返回纯字符串而非 `LLMResponse`

---

## 6. Prompt Layer —— Prompt 层

### 6.1 数据模型：`prompts/schemas.py`

```python
class PromptTemplate(BaseModel):
    key: str          # 模板键，如 "note/outline"
    version: str      # 模板版本
    description: str  # 模板用途描述
    content: str      # 模板文本内容
```

### 6.2 注册中心：`prompts/registry.py` — `PromptRegistry`

- 从 `templates/` 目录递归加载 `.md` 文件
- Key 规则：`templates/note/outline.md` → `"note/outline"`
- 全局单例模式（`_instance`）
- `reload()` 支持热更新

### 6.3 构造器：`prompts/builder.py` — `PromptBuilder`

纯字符串操作：将模板中 `{variable}` 替换为实际值，缺失变量时抛 `ValueError`。

```python
PromptBuilder.build("你好 {name}", name="世界")  # → '你好 世界'
PromptBuilder.build("你好 {name}")               # → ValueError: 模板缺失变量: ['name']
```

### 6.4 笔记模板兼容层：`prompts/note.py`

```python
VALID_TEMPLATES = {"outline", "summary", "cornell", "qa"}
NOTE_PROMPTS = _load_note_prompts()  # 延迟从 PromptRegistry 加载
````

4 个模板文件：`templates/note/{outline,synopsis,cornell,qa}.md`

---

## 7. Tool Layer —— 工具层

### 7.1 抽象基类：`tools/base.py` — `BaseTool[InputT, OutputT]`

**模板方法模式**，子类只需定义 schema 并实现 `execute()`：

```
run(dict | InputT) → ToolResult[OutputT]
  ├── 1. input 自动解析 (dict → Pydantic)
  ├── 2. before_run() 钩子
  ├── 3. validate() 异步业务校验钩子
  ├── 4. execute() 核心逻辑 (带超时 + 重试 + 间隔)
  ├── 5. after_run() 或 on_error() 钩子
  └── 6. 返回 ToolResult
```

**`ToolResult`**：

```python
@dataclass
class ToolResult(Generic[OutputT]):
    status: ToolStatus  # SUCCESS / VALIDATION_ERROR / EXECUTION_ERROR / TIMEOUT
    data: Optional[OutputT]
    error: Optional[str]
    duration_ms: float
```

**可配置属性**：

| 属性 | 默认值 | 用途 |
|------|--------|------|
| `timeout_seconds` | 30.0 | 超时时间 |
| `retry_count` | 0 | 重试次数 |
| `retry_delay_seconds` | 0.0 | 重试间隔 |

**子类必须定义**：`name`, `description`, `input_schema`, `output_schema`, `execute()`

**可覆写钩子**：`before_run()`, `after_run()`, `on_error()`, `validate()`

### 7.2 注册中心：`tools/registry.py` — `ToolRegistry`

字典存储，按 name 去重。实现 `IToolRegistry` 接口：

```python
reg = ToolRegistry()
reg.register(ContentParser())
tool = reg.get("content_parser")
```

### 7.3 三个具体 Tool

| Tool | 类型 | 驱动 | 超时 | 重试 | 职责 |
|------|------|------|------|------|------|
| `ContentParser` | 纯本地 | 正则 | 5s | 0 | 解析 Markdown → 标题/章节/字数/语言 |
| `EntityExtractor` | LLM | DeepSeek | 60s | 1 | 提取知识实体（概念/术语/人物/公式） |
| `StructureAnalyzer` | 混合 | 本地+LLM | 60s | 1 | 层次深度(本地) + 核心主题/大纲(LLM) |

### ContentParser 细节

- 逐行扫描 `#`/`##`/`###` 标题
- 用 `_collect_section_content()` 收集每个标题下的正文
- 字数统计：中文字符 + 英文单词（正则 `[一-鿿]` + `[a-zA-Z]+`）
- 语言检测：比较中英字符比例

### EntityExtractor 细节

- 截断内容到 8000 字符
- 附带章节摘要（前 10 个标题）
- `temperature=0.3` 追求稳定输出
- JSON 解析失败时降级返回空结果
- `_extract_json()` 处理 markdown code block 包裹

### StructureAnalyzer 细节

- 本地计算层次深度和复杂度（基于字数 + 章节层级）
- LLM 只分析前 3000 字符
- 降级策略：LLM 解析失败时用本地估算值填充全部字段

---

## 8. Agent Layer —— Agent 层

### 8.1 状态定义：`agent/state.py` — `NoteAgentState`

LangGraph 的 State Schema（TypedDict），贯穿 5 个节点：

```python
class NoteAgentState(TypedDict, total=False):
    # 用户输入
    content: str
    template_id: str
    session_id: str

    # ContentParser 产出
    parsed_title: str
    parsed_sections: list[SectionInfo]
    parsed_total_words: int
    parsed_language: str

    # EntityExtractor 产出
    entities: list[EntityInfo]
    key_concepts: list[str]

    # StructureAnalyzer 产出
    content_type: str
    hierarchy_depth: int
    main_topics: list[TopicInfo]
    suggested_outline: list[OutlineItem]
    complexity: str
    estimated_study_time_minutes: int

    # 最终输出
    generated_note: str

    # 控制字段
    stage: str
    error: str
    human_confirmed: bool
```

### 8.2 节点实现：`agent/nodes.py`

5 个节点函数，签名：`async (state) → dict`：

```
parse_content_node        → ContentParser.run()        → parsed_*
extract_entities_node     → EntityExtractor.run()      → entities, key_concepts
analyze_structure_node    → StructureAnalyzer.run()     → main_topics, suggested_outline
confirm_template_node     → 标记 human_confirmed        → 等待用户确认 (interrupt)
generate_note_node        → LLM 生成笔记                → generated_note
```

**`generate_note_node` 的核心 —— `_build_enriched_user_message`**：

将 Tool 中间产出注入 LLM 请求，而不是只发原始内容：

```
user_message = 原始学习内容
             + 内容结构（章节摘要，前 10 个）
             + 已识别的核心概念
             + 建议的笔记大纲（前 8 个）
             + 元信息（类型/复杂度/学习时间/语言）
```

**依赖注入**：节点函数通过模块级变量 `_tool_registry` / `_llm_service` 获取依赖，由 `AgentExecutor.__init__` 调用 `inject_dependencies()` 设置。

### 8.3 状态图：`agent/graph.py`

```
START → parse → extract → analyze → confirm → generate → END
```

- 使用 `MemorySaver` 作为 checkpointer（开发环境）
- Phase 4 预留了 `interrupt_before=["confirm"]`（human-in-the-loop，当前注释掉等待前端适配）

### 8.4 执行器：`agent/executor.py` — `AgentExecutor`

两种执行模式：

**`run_stream()` — SSE 流式**：

```
graph.astream(initial_state, config)
  → yield "agent_start"
  → for each node:
      yield "stage_change"   (parse → extract → ...)
      yield "node_finish"
      检查 error → yield "agent_error" + return
  → yield "agent_finish" (含 generated_note)
```

**`run_sync()` — 同步**：

```
await graph.astream(...)
await graph.aget_state(config)
return generated_note   (或 raise RuntimeError)
```

---

## 9. Service Layer —— 服务层

### 9.1 SSE 事件总线：`services/event_bus.py`

**发布-订阅模式**，实现前端实时接收 Agent 执行进度：

```
EventBus
├── publish(AgentEvent)       → 推送到 session 的所有 Queue
├── subscribe(session_id)     → SSESubscription
└── unsubscribe(session_id, q)
```

**SSESubscription**：
- `events()` → `AsyncGenerator[str]`，直接用于 FastAPI `StreamingResponse`
- 每 30s 发送心跳 `: heartbeat\n\n`
- 被取消或超时时自动 `close()`

**事件类型**：

| 事件 | 含义 |
|------|------|
| `agent_start` | Agent 启动 |
| `agent_finish` | 生成完成，`data.result` 包含笔记 |
| `agent_error` | 出错 |
| `node_start` / `node_finish` | 节点状态变更 |
| `tool_start` / `tool_finish` | Tool 执行 |
| `stage_change` | 阶段变更 |
| `human_confirm_required` | 需要人类确认 |
| `stream_chunk` | 流式输出分块 |

**辅助构造函数**：`make_event()`, `stage_change()`, `tool_start()`, `tool_finish()`, `human_confirm_required()`

### 9.2 文档导出：`services/export_service.py`

将 Markdown 导出为 DOCX/PDF：

```
export(md, format)
  → _parse_md_blocks(md)    # Markdown → 结构化块列表
  → _build_docx(blocks)     # 块 → python-docx (A4, 微软雅黑)
  → _build_pdf(blocks)      # 块 → reportlab (Helvetica, 中文降级)
```

**`_parse_md_blocks()`** 支持 9 种块类型：

| 类型 | Markdown | 渲染形式 |
|------|----------|---------|
| `h1/h2/h3` | `# / ## / ###` | 分级标题 |
| `p` | 普通文本 | 段落（支持 `**bold**`） |
| `code` | ` ``` ` | 等宽字体代码块 |
| `quote` | `> ` | 缩进引用（斜体 + 棕色） |
| `ul` / `ol` | `- ` / `1. ` | 无序/有序列表 |
| `table` | `\|...\|` | 表格（表头加粗） |
| `hr` | `---` | 分隔线 |

---

## 10. API Layer —— API 层

### 10.1 Agent 端点：`api/agent.py`

```python
POST /api/agent/note        → 同步生成（兼容旧版）
POST /api/agent/note/stream → SSE 流式生成
```

**请求模型**：

```python
class NoteRequest(BaseModel):
    content: str    # 1-50000 字符
    template: str   # outline | summary | cornell | qa
```

**流程**：

```
1. 校验 template 是否合法
2. get_container() → agent_executor
3. 生成 session_id
4. executor.run_sync(content, template, session_id)
5. 返回 NoteResponse(result=markdown_note)
```

### 10.2 导出端点：`api/export.py`

```python
POST /api/export → 下载 DOCX/PDF 文件
```

**请求模型**：

```python
class ExportRequest(BaseModel):
    content: str    # Markdown 内容
    format: str     # docx | pdf
```

**流程**：

```
1. 校验 format
2. get_container() → export_service
3. export_service.export(content, format) → BytesIO
4. 返回 StreamingResponse (带 Content-Disposition)
```

---

## 11. 完整请求链路

以 `POST /api/agent/note` 为例：

```
 1. FastAPI 接收请求
    └── NoteRequest 校验 (content 1-50000, template ∈ VALID_TEMPLATES)

 2. get_container() → Container 单例

 3. container.agent_executor.run_sync(content, template, session_id)

 4. LangGraph 执行状态图:

    ┌─ PARSE ──────────────────────────────────────────┐
    │ ContentParser.run(content)                        │
    │   → 正则扫描 # / ## / ### 标题                     │
    │   → 统计中文字符 + 英文单词                        │
    │   → 检测语言 (zh/en/mixed)                        │
    │ → state: parsed_title, parsed_sections, words     │
    └───────────────────────────────────────────────────┘

    ┌─ EXTRACT ────────────────────────────────────────┐
    │ EntityExtractor.run(content, sections)            │
    │   → LLMService.generate(prompt)                  │
    │     → 查缓存 (MD5 hash)                           │
    │     → 未命中 → DeepSeekProvider.generate()        │
    │     → 写缓存 (TTL=300s)                           │
    │   → 解析 JSON → EntityItem 列表                   │
    │ → state: entities, key_concepts                   │
    └───────────────────────────────────────────────────┘

    ┌─ ANALYZE ────────────────────────────────────────┐
    │ StructureAnalyzer.run(content, sections, words)   │
    │   → 本地计算: depth, complexity                   │
    │   → LLMService.generate(prompt)                  │
    │   → 解析 JSON → MainTopic + SuggestedOutline     │
    │ → state: main_topics, suggested_outline, ...      │
    └───────────────────────────────────────────────────┘

    ┌─ CONFIRM ────────────────────────────────────────┐
    │ 标记 human_confirmed = True                       │
    │ (Phase 4: interrupt_before 暂停等待用户确认)       │
    └───────────────────────────────────────────────────┘

    ┌─ GENERATE ───────────────────────────────────────┐
    │ 从 NOTE_PROMPTS 取模板 prompt                     │
    │ _build_enriched_user_message(state):             │
    │   原始内容 + 章节结构 + 核心概念                    │
    │   + 建议大纲 + 元信息                              │
    │ LLMService.generate(system_prompt, user_message)  │
    │ → state: generated_note (Markdown)                │
    └───────────────────────────────────────────────────┘

 5. graph.aget_state(config) → 提取 generated_note

 6. 返回 NoteResponse(result=markdown_note)
```

---

## 12. 设计亮点总结

1. **严格的分层架构**：API → Agent → Tool/Service/Prompt → LLM → Data，每层只依赖下一层的抽象接口

2. **手动 DI 容器**：`Container` 数据类 + `create_dev()` 工厂 + `get_container()` 单例，简单、可测试、无框架依赖

3. **模板方法模式**：`BaseMemoryStore`, `BaseBusinessRepository`, `BaseTool` 都使用"基类定义流程，子类实现钩子"的模式，减少重复代码

4. **抽象接口先行**：`data/interfaces.py` 和 `tools/interfaces.py` 定义了全部 ABC，内存实现只是其中一种选择，替换为 Redis/PostgreSQL 只需实现接口，上层代码零改动

5. **LangGraph 状态图**：5 节点线性流水线，每个节点产出的字段通过 `NoteAgentState` 传递，最终 `generate` 节点整合所有中间结果。节点间完全解耦，可独立替换

6. **SSE 实时推送**：EventBus 发布-订阅模式，前端实时看到 Agent 执行进度（parse → extract → analyze → confirm → generate）

7. **补偿事务**：UnitOfWork 用补偿函数模式实现跨存储回滚，单个补偿失败不阻断后续补偿

8. **缓存去重**：LLM 响应按 content hash 缓存（TTL=300s），避免重复调用浪费 token

9. **双轨 TTL 清理**：惰性清理（get 时检查）+ 主动清理（CleanupScheduler 定时扫描），防止过期数据永久泄留

10. **统一异常体系**：5 级异常树，每条异常携带 `store_name` + `operation` + `detail`，便于生产环境排障

---

## 13. 文件清单

```
backend/
├── requirements.txt
├── .env                              # 环境变量（不入库）
└── app/
    ├── __init__.py
    ├── main.py                       # FastAPI 入口 + lifespan
    ├── container.py                  # DI 容器
    │
    ├── api/
    │   ├── __init__.py
    │   ├── agent.py                  # POST /api/agent/note{,/stream}
    │   └── export.py                 # POST /api/export
    │
    ├── agent/
    │   ├── __init__.py
    │   ├── state.py                  # NoteAgentState (TypedDict)
    │   ├── nodes.py                  # 5 个节点函数
    │   ├── graph.py                  # LangGraph 状态图
    │   └── executor.py               # AgentExecutor (run_stream + run_sync)
    │
    ├── services/
    │   ├── __init__.py
    │   ├── llm_service.py            # 统一 LLM 服务 (多 Provider + 缓存)
    │   ├── export_service.py         # Markdown → DOCX/PDF
    │   └── event_bus.py              # SSE 事件总线
    │
    ├── tools/
    │   ├── __init__.py
    │   ├── base.py                   # BaseTool[I,O] 抽象基类
    │   ├── interfaces.py             # IToolRegistry 抽象接口
    │   ├── registry.py               # ToolRegistry 实现
    │   ├── content_parser.py         # 纯本地内容解析
    │   ├── entity_extractor.py       # LLM 驱动实体提取
    │   └── structure_analyzer.py     # 混合模式结构分析
    │
    ├── prompts/
    │   ├── __init__.py
    │   ├── schemas.py                # PromptTemplate 数据模型
    │   ├── registry.py               # PromptRegistry 注册中心
    │   ├── builder.py                # PromptBuilder 变量填充
    │   ├── note.py                   # 笔记模板兼容层
    │   └── templates/
    │       └── note/
    │           ├── outline.md
    │           ├── summary.md
    │           ├── cornell.md
    │           └── qa.md
    │
    ├── llm/
    │   ├── __init__.py
    │   └── deepseek.py               # 旧版 DeepSeek 客户端（兼容）
    │
    └── data/
        ├── __init__.py
        ├── interfaces.py             # 所有存储抽象接口 + 数据模型
        ├── exceptions.py             # 5 级异常体系
        ├── cleanup.py                # 后台清理调度器
        ├── unit_of_work.py           # 补偿事务 UnitOfWork
        ├── runtime/
        │   ├── __init__.py
        │   ├── base.py               # BaseMemoryStore 基类
        │   ├── checkpoint_store.py   # MemoryCheckpointStore
        │   ├── session_store.py      # MemorySessionStore (TTL)
        │   └── cache_store.py        # MemoryCacheStore (TTL)
        └── business/
            ├── __init__.py
            ├── base.py               # BaseBusinessRepository[ModelT] 基类
            ├── models.py             # 数据模型兼容导出
            └── repository/
                ├── __init__.py
                ├── note_repo.py      # MemoryNoteRepository
                └── user_repo.py      # MemoryUserPreferenceRepository
```
