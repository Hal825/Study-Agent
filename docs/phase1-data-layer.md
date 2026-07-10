# Phase 1: Data Layer 架构设计文档

> 从 "能用" 到 "线程安全、可观测、可回滚" 的 Data Layer 基础设施。

---

## 目录

1. [设计目标](#1-设计目标)
2. [整体架构](#2-整体架构)
3. [异常体系](#3-异常体系)
4. [BaseMemoryStore —— Runtime 基类](#4-basememorystore--runtime-基类)
5. [BaseBusinessRepository —— Business 基类](#5-basebusinessrepository--business-基类)
6. [过期数据清理机制](#6-过期数据清理机制)
7. [UnitOfWork —— 跨存储事务](#7-unitofwork--跨存储事务)
8. [DI Container](#8-di-container)
9. [并发模型](#9-并发模型)
10. [测试验证](#10-测试验证)
11. [待演进项](#11-待演进项)

---

## 1. 设计目标

Phase 1 的数据层解决四个基底问题：

| 问题 | 现状（优化前） | 目标（优化后） |
|------|---------------|---------------|
| **并发安全** | 纯字典操作，asyncio 下无锁。Agent 图节点并发执行时存在数据竞争 | `asyncio.Lock` 保护每个读写操作，10 并发 writer 验证通过 |
| **异常不可追踪** | 原生 `KeyError` / `IndexError` 直接抛出，无法区分 "不存在" 和 "存储挂了" | 5 级异常树，每条异常携带 `store_name` + `operation` + `detail` |
| **过期数据泄漏** | TTL 仅惰性清理（get 时检查），永不访问的 key 永久驻留内存 | 后台 `CleanupScheduler` 每 5 分钟主动扫描清除 |
| **跨存储无事务** | Agent 同时写 Checkpoint + Note，一个成功一个失败时数据不一致 | `UnitOfWork` 补偿事务：成功提交，失败 LIFO 逆序回滚 |

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     DI Container                              │
│  checkpoint_store  session_store  cache_store               │
│  note_repo         user_pref_repo                           │
│  cleanup_scheduler  uow_factory                              │
│  llm_service       export_service  event_bus                │
└──────────────────────────────────────────────────────────────┘
         │                │                  │
         ▼                ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Runtime Store   │ │ Business Repo│ │  Infrastructure   │
│                 │ │              │ │                  │
│ BaseMemoryStore │ │BaseBusiness  │ │ CleanupScheduler │
│  ├─ Checkpoint  │ │ Repository   │ │ UnitOfWorkFactory│
│  ├─ Session     │ │  ├─ Note     │ │                  │
│  └─ Cache       │ │  └─ User     │ │                  │
└────────┬────────┘ └──────┬───────┘ └──────────────────┘
         │                 │
         ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                   exceptions.py                               │
│  StorageError → NotFound / Write / Connection / Timeout /     │
│                 Integrity                                     │
└──────────────────────────────────────────────────────────────┘
```

### 分层职责

| 层 | 职责 | 生命周期 |
|----|------|---------|
| **Runtime Store** | Checkpoint 快照、会话状态、热点缓存 | 单次会话 / 单次 Agent 执行，可丢失 |
| **Business Repository** | 用户笔记、偏好设置 | 跨会话持久化，不可丢失 |
| **Infrastructure** | 后台清理、跨存储事务协调 | 与应用生命周期一致 |

### 接口-实现分离

每个存储模块都遵循 "接口先行" 模式：

```
interfaces.py          ← 抽象接口（上层依赖）
    ↑
    │  实现
    │
runtime/session_store.py  ← 具体实现（容器注入时选择）
```

上层代码（Agent、API）永远只 import `interfaces.py`，不感知底层是内存还是 Redis/PostgreSQL。切换存储后端只需改 `Container.create_xxx()` 工厂方法。

---

## 3. 异常体系

路径：`backend/app/data/exceptions.py`

### 设计原则

**分层语义，逐级具体。** 上层可以按粒度选择捕获范围：

```python
# 捕获所有存储错误（最粗）
except StorageError: ...

# 只捕获"数据不存在"（最细）
except StoreNotFoundError: ...
```

### 异常树

```
StorageError                     # 根异常
├── StoreNotFoundError           # 数据不存在（非系统故障）
├── StoreWriteError              # 写入失败
├── StoreConnectionError         # 连接失败（仅生产环境，内存实现不抛出）
├── StoreTimeoutError            # 操作超时
└── StoreIntegrityError          # 数据完整性约束违反（UnitOfWork 回滚时）
```

### 异常结构

每个异常实例携带三个诊断字段：

```python
class StorageError(Exception):
    store_name: str    # 哪个 store 抛出的，如 "MemorySessionStore"
    operation: str     # 什么操作，如 "get" / "set" / "save"
    detail: str        # 原始错误信息，用于调试
```

### 使用示例

```python
# BaseMemoryStore._locked_context 在生产代码中自动封装
try:
    result = await self._get_impl(key)
except Exception as e:
    raise StoreNotFoundError(
        f"[{self._store_name}] 读取失败: key={key}",
        store_name=self._store_name,
        operation="get",
        detail=str(e),
    ) from e
```

链路保留 (`from e`) 意味着栈追踪不会断裂，调试时可以看到完整的异常传播路径。

---

## 4. BaseMemoryStore —— Runtime 基类

路径：`backend/app/data/runtime/base.py`

### 动机

三个 Runtime store（Checkpoint / Session / Cache）在优化前各自独立实现，存在三类重复：

1. **锁逻辑重复**：每个方法都要手写 `async with self._lock:`
2. **日志逻辑缺失**：无法追踪哪个 store 在什么时候做了什么操作
3. **异常处理缺失**：原生异常直接穿透到上层

### 核心设计

```python
class BaseMemoryStore:
    def __init__(self, name: str = ""):
        self._lock = asyncio.Lock()          # 全局互斥锁
        self._store_name = name              # 日志标识
        self._logger = logging.getLogger(...) # 专用 logger
```

### 子类覆写点

| 方法 | 子类职责 | 父类提供 |
|------|---------|---------|
| `_get_impl(key)` | 返回 key 对应的值 | 锁 + 日志 + 异常封装 |
| `_set_impl(key, value)` | 写入 key-value | 同上 |
| `_delete_impl(key)` | 删除 key | 同上 |
| `_clear_impl()` | 清空全部数据 | 同上 |
| `_cleanup_expired()` | 清理过期数据，返回条数 | 同上 |

父类对外暴露的 `get()` / `set()` / `delete()` / `clear()` / `cleanup()` 方法封装了完整的**锁获取 → 耗时记录 → 异常转换**链路。

### _locked_context —— 核心机制

```python
@asynccontextmanager
async def _locked_context(self, operation: str, key: str):
    start = time.perf_counter()
    async with self._lock:          # 互斥锁
        try:
            yield                   # 执行子类实现
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            if elapsed > 100:       # 慢操作告警
                self._logger.warning(f"[{operation}] key={key} 耗时 {elapsed:.0f}ms")
            elif elapsed > 10:      # 正常操作，DEBUG 级别
                self._logger.debug(f"[{operation}] key={key} 耗时 {elapsed:.0f}ms")
```

三层设计：

- `>100ms`：WARNING 级别 —— 生产环境触发告警
- `10ms~100ms`：DEBUG 级别 —— 本地开发可追踪
- `<10ms`：静默 —— 避免日志洪水

**为什么用 asyncio.Lock 而非 threading.Lock？** 我们这个项目全部跑在 asyncio event loop 里，Agent 图节点、Tool 执行、SSE 推送都是协程。`threading.Lock` 会阻塞整个 event loop，切换到 `asyncio.Lock` 让其他协程在锁释放前可以继续跑不相关的任务。

### 参数化策略

所有子类构造时传入 `name` 参数，自动生成独立的 logger 实例：

```python
# Session store 的日志
logger = logging.getLogger("data.runtime.MemorySessionStore")

# Cache store 的日志
logger = logging.getLogger("data.runtime.MemoryCacheStore")
```

这样在生产环境可以通过 logging 配置按 store 粒度设置日志级别。

---

## 5. BaseBusinessRepository —— Business 基类

路径：`backend/app/data/business/base.py`

### 与 BaseMemoryStore 的差异

| 维度 | BaseMemoryStore | BaseBusinessRepository |
|------|----------------|----------------------|
| 数据结构 | Key-Value | 实体模型（Pydantic） |
| 操作语义 | get/set/delete | save/get/delete/list/count |
| 分页支持 | 无 | limit + offset |
| 锁粒度 | 每个 KV 操作 | 每个 CRUD 操作 |
| 泛型 | 无 | `Generic[ModelT]`，类型安全 |

### 泛型设计

```python
ModelT = TypeVar("ModelT", bound=BaseModel)

class BaseBusinessRepository(Generic[ModelT]):
    async def _save_impl(self, model: ModelT) -> str: ...
    async def _get_impl(self, entity_id: str) -> Optional[ModelT]: ...
    async def _list_impl(self, user_id: str, limit: int, offset: int) -> list[ModelT]: ...
```

子类继承时绑定具体类型：

```python
class MemoryNoteRepository(BaseBusinessRepository[StudyNote], NoteRepository):
    ...
```

### UserPreferenceRepository 的特殊处理

`UserPreferenceRepository` 的接口不是标准实体 CRUD（它用 `user_id` 而非 `entity_id`，有 `update` 和 `reset` 方法），因此它：
- 继承 `BaseBusinessRepository[UserPreference]` 复用锁 + 日志
- 覆写所有的 `_xxx_impl` 方法供基类调用
- 但对外暴露的方法 (`get` / `update` / `reset`) 直接使用 `self._locked_context()`，不走基类的标准 CRUD 模板

这是 **"Template Method Pattern 允许子类选择性地走模板或直通底层"** 的设计。

---

## 6. 过期数据清理机制

路径：`backend/app/data/cleanup.py`

### 问题

优化前，MemorySessionStore 和 MemoryCacheStore 的 TTL 过期只在 `get()` 触发时**惰性清理**：

```
set(key, value, ttl=600)  →  写入，expires_at = now + 600s
... 600s 后 ...
get(key)                   →  发现过期，删除，返回 None  ✅
... key 再也没被访问 ...
                            →  永久残留！ ❌
```

这在 Agent 场景下很致命：一次 Agent 执行会创建数十个临时 session key，如果用户刷新页面重来，旧 key 没人访问，就永远占着内存。

### 方案：双轨清理

```
主动扫描（CleanupScheduler）         惰性清理（get 时触发）
         │                                  │
         ▼                                  ▼
  每 300s 遍历全部数据              访问时检查 expires_at
  批量清除过期条目                  单条删除
         │                                  │
         └──────────┬───────────────────────┘
                    ▼
             保证过期数据最终被清除
```

### CleanupScheduler 实现

```python
class CleanupScheduler:
    def __init__(self, interval_seconds: int = 300):
        self._interval = interval_seconds
        self._stores: list[BaseMemoryStore] = []   # 注册的存储
        self._task: Optional[asyncio.Task] = None  # 后台协程
```

核心循环：

```python
async def _loop(self):
    while self._running:
        await asyncio.sleep(self._interval)
        for store in self._stores:
            try:
                count = await store.cleanup()       # 每个 store 独立清理
                if count > 0:
                    logger.info(f"[{store.store_name}] cleaned {count}")
            except Exception as e:
                logger.error(f"cleanup failed for {store.store_name}: {e}")
                # 不抛出，继续处理下一个 store
```

关键设计决策：

1. **`asyncio.sleep` 而非 `time.sleep`**：不阻塞 event loop，其他协程可以继续运行
2. **异常隔离**：单个 store 清理失败不影响其他 store 的清理
3. **手动触发接口**：`run_once()` 返回 `{store_name: count}` 字典，调试用

### 清理策略对比

| 维度 | 惰性清理 | 主动扫描 |
|------|---------|---------|
| 触发时机 | get() 时 | 定时器 |
| 清理范围 | 单 key | 全部数据 |
| 时间复杂度 | O(1) 平摊 | O(n) 全量 |
| 内存回收保证 | 否（依赖访问） | 是 |

### 生命周期管理

```python
# main.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    container = get_container()
    await container.cleanup_scheduler.start()   # 启动后台任务
    yield
    await container.cleanup_scheduler.stop()     # 取消后台任务
```

---

## 7. UnitOfWork —— 跨存储事务

路径：`backend/app/data/unit_of_work.py`

### 问题场景

Agent 生成笔记的执行路径涉及两个存储：

```
1. CheckpointStore.put()  ← Runtime，标记 Agent 进度
2. NoteRepository.save()  ← Business，持久化结果

场景：步骤 1 成功，步骤 2 失败（如 LLM 返回空内容）
结果：checkpoint 已写入但笔记没保存 → 数据不一致
```

### 方案：补偿事务（Compensating Transaction）

不追求 ACID 事务（内存实现做不到），而是用 **"补偿"** 模式：

> 每个写操作同时注册一个反向操作（补偿函数）。正常退出时补偿丢弃；异常退出时按 LIFO 逆序执行补偿。

```
正常流程：
  save_checkpoint → 注册补偿: remove_checkpoint
  save_note        → 注册补偿: delete_note
  __aexit__(exc_type=None) → 丢弃所有补偿 ✓

异常流程：
  save_checkpoint → 注册补偿: remove_checkpoint
  save_note        → ... 抛出异常
  __aexit__(exc_type=RuntimeError) → 逆序执行补偿:
    1. delete_note        (先注册的后执行)
    2. remove_checkpoint  (后注册的先执行)
```

### 核心实现

```python
class UnitOfWork:
    async def __aenter__(self) -> "UnitOfWork":
        self._compensations.clear()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            await self._rollback()      # 逆序执行补偿
        else:
            self._compensations.clear()  # 丢弃补偿
        return False  # 不吞异常
```

### 补偿注册

```python
async def save_note(self, note: StudyNote) -> str:
    note_id = await self.note_repo.save(note)

    # 注册补偿：如果后续失败，删除这条笔记
    async def compensate():
        await self.note_repo.delete(note_id)

    self._register(compensate)
    return note_id
```

### 失败处理

单个补偿函数执行失败**不会阻断**后续补偿：

```python
async def _rollback(self):
    for compensation in reversed(self._compensations):
        try:
            await compensation()
        except Exception as e:
            self._logger.error(f"Compensation FAILED: {e}")
            # 继续执行下一个补偿，不抛出
```

### 工厂模式

通过 `UnitOfWorkFactory` 持有容器引用，上层只需一行代码：

```python
async with container.uow_factory.create() as uow:
    await uow.save_checkpoint(...)
    note_id = await uow.save_note(note)
```

### 局限性（Phase 1）

- 仅支持 CheckpointStore + NoteRepository 两种操作的补偿
- 补偿是"尽力而为"，不是严格原子性（一个补偿失败不影响其他补偿执行）
- 不处理并发冲突（两个 UoW 同时操作同一个 note）

这些在切换到 PostgreSQL 后可以通过数据库事务自然解决。

---

## 8. DI Container

路径：`backend/app/container.py`

### 设计

```python
@dataclass
class Container:
    # Runtime
    checkpoint_store: CheckpointStore
    session_store: SessionStore
    cache_store: CacheStore

    # Business
    note_repo: NoteRepository
    user_pref_repo: UserPreferenceRepository

    # Infrastructure
    cleanup_scheduler: CleanupScheduler
    uow_factory: UnitOfWorkFactory

    # Services
    llm_service: LLMService
    export_service: ExportService
    event_bus: EventBus
```

### 工厂方法

```python
@classmethod
def create_dev(cls) -> "Container":
    """开发环境：全部使用内存实现"""
    checkpoint_store = MemoryCheckpointStore()
    session_store = MemorySessionStore()
    cache_store = MemoryCacheStore()
    ...

@classmethod
def create_prod(cls) -> "Container":
    """生产环境：Redis + PostgreSQL（待实现）"""
    checkpoint_store = RedisCheckpointStore(REDIS_URL)
    session_store = RedisSessionStore(REDIS_URL)
    cache_store = RedisCacheStore(REDIS_URL)
    note_repo = PostgresNoteRepository(DATABASE_URL)
    ...
```

### 单例管理

```python
_container: Container | None = None

def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container.create_dev()
    return _container
```

惰性初始化保证环境变量在 `main.py` 的 `load_dotenv()` 之后才被读取。

---

## 9. 并发模型

### 锁策略

每个 store 实例内部使用一个**全局 `asyncio.Lock`** 保护所有操作：

```
         ┌─────────────┐
         │  asyncio.Lock│
         └──────┬──────┘
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  get()       set()      delete()
```

这是**粗粒度锁**。选择粗粒度的理由：

1. Phase 1 的并发度低（Agent 串行节点为主），锁竞争不是瓶颈
2. 内存字典的读写是 ns 级别的，即使排队也感知不到延迟
3. 细粒度锁（per-key 锁）需要维护锁字典，增加复杂度，而收益在 Phase 1 不明显

### 验证

10 个协程并发写入，每个写 20 个 key：

```python
async def writer(sid, n):
    for i in range(20):
        await c.session_store.set(sid, f'k{i}', f'val-{n}-{i}')

await asyncio.gather(*[writer(f's{w}', w) for w in range(10)])
# 结果：200 次写入全部成功，无数据竞争
```

---

## 10. 测试验证

Phase 1 优化通过 5 项集成测试：

| 测试项 | 验证内容 | 结果 |
|--------|---------|------|
| Container 创建 | 所有服务实例化无异常 | ✅ |
| 并发写入 | 10 协程 x 20 次写入，数据完整性 | ✅ |
| 主动清理 | 注入过期 key，`run_once()` 清除 | ✅ |
| UoW 提交 | 正常退出后笔记持久化 | ✅ |
| UoW 回滚 | 异常退出后笔记被补偿删除 | ✅ |
| FastAPI 加载 | 应用启动，路由注册 | ✅ |

---

## 11. 待演进项

以下在 Phase 1 中**故意不做**，留到后期迭代：

### 中优（业务稳定后）

| 项 | 说明 |
|----|------|
| BaseRuntimeStore 顶层抽象 | 提取所有 Runtime Store 的公共接口签名，与 BaseMemoryStore 形成双基类 |
| BaseBusinessRepository 接口抽象 | 提取 `_save_impl` 等方法的 `@abstractmethod` 声明 |
| ModelMapper 转换层 | Pydantic ↔ SQLAlchemy 双向转换，降低接入 PG 的开发成本 |
| 多数据源自由组合 | Container 支持 `create(use_cache=redis, use_db=postgres)` 的混合模式 |
| 故障降级 | Redis 不可用时自动 fallback 到内存实现 |
| 通用分页/批量操作/软删除 | `BaseBusinessRepository` 内置 `bulk_save`、`soft_delete` |

### 低优（长期架构）

| 项 | 说明 |
|----|------|
| 冷热数据分离归档 | 超过 N 天的笔记压缩归档到对象存储 |
| 全链路监控埋点 | Prometheus metrics：操作次数、耗时分布、清理速率 |
| 游标分页 | 替代 offset 分页，支持大数据量场景 |
| LRU 缓存淘汰 | 当缓存条目超过上限时自动淘汰最久未访问的条目 |
| Read-Only 副本路由 | 读写分离：写走主库，查询走只读副本 |

---

## 附录 A：文件清单

```
backend/app/data/
├── exceptions.py                      # NEW  异常体系（5 个异常类）
├── interfaces.py                      # KEPT 抽象接口（未变）
├── cleanup.py                         # NEW  后台清理调度器
├── unit_of_work.py                    # NEW  补偿事务 UnitOfWork
├── runtime/
│   ├── base.py                        # NEW  BaseMemoryStore 基类
│   ├── checkpoint_store.py            # REFACTORED  继承 BaseMemoryStore
│   ├── session_store.py               # REFACTORED  继承 BaseMemoryStore + _cleanup_expired
│   └── cache_store.py                 # REFACTORED  继承 BaseMemoryStore + _cleanup_expired
└── business/
    ├── base.py                        # NEW  BaseBusinessRepository 基类
    ├── models.py                      # KEPT 未变
    └── repository/
        ├── note_repo.py               # REFACTORED  继承 BaseBusinessRepository[StudyNote]
        └── user_repo.py               # REFACTORED  继承 BaseBusinessRepository[UserPreference]
```

## 附录 B：关键设计决策记录

| 决策 | 选择 | 替代方案 | 理由 |
|------|------|---------|------|
| 锁类型 | `asyncio.Lock` | `threading.Lock` | 全异步环境，threading.Lock 会阻塞 event loop |
| 锁粒度 | 每实例一把全局锁 | per-key 锁 | Phase 1 并发度低，粗粒度锁实现简单 |
| 事务模式 | 补偿事务 | 两阶段提交 | 内存存储不支持真正的 ACID，补偿事务符合场景 |
| TTL 清理 | 惰性 + 定时双轨 | 纯惰性 | 纯惰性清理无法回收永不访问的过期数据 |
| 依赖注入 | 手动工厂方法 | DI 框架（dependency-injector） | 当前服务数量少，框架引入的认知成本 > 收益 |
| 异常设计 | 继承树 | 单一 StorageError | 分类异常允许上层按需捕获不同粒度 |
| 慢操作阈值 | 100ms | 50ms / 200ms | 内存操作正常应在 1ms 内，100ms 是保守阈值 |
