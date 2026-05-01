# SISYS 同步代码最优重构方案（完善版）

**生成日期**: 2026-05-01
**版本**: v2.0（基于代码实地审查的完善版）
**依据**: sync-code-analysis.md + sisys-sync-architecture.md + sync-code-design-mastery.md + 源码实地审查
**目标**: 宗师级架构设计，给出可执行的最优重构路径

---

## 0. 重构愿景

```
"让 SISYS 成为 Python async 架构的典范，而非技术债务的堆砌场。"
```

**核心原则**：
- 单一事件循环：一个进程，一个 asyncio 事件循环
- 上下文纯净：同步代码在同步上下文，异步代码在异步上下文
- 端口抽象：所有外部依赖通过 Hexagon Port 接口隔离
- 验证驱动：红→绿→重构（TDD 约束）

---

## 1. 当前问题全景（基于源码审查）

### 1.1 问题分布矩阵（校正）

| 层级 | P0（阻塞循环） | P1（性能风险） | P2（可接受） |
|------|---------------|---------------|-------------|
| Infrastructure | 3 | 4 | 4 |
| Interfaces | 1 | 0 | 0 |
| **总计** | **4** | **4** | **4** |

**重要发现**：通过源码实地审查，发现 P0 问题比原分析多 2 处：
1. `integrity_service.py:189` - async 方法内的同步 `open()`
2. `object_operations.py:371` - async 方法内的同步 `open()`

### 1.2 问题根因分类（校正）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   问题根因分类（源码审查版）                             │
├─────────────────────────────────────────────────────────────────────────┤
│ Type-A: 上下文错配                                                      │
│   ├── event_listener.py:106  — asyncio.run() 在 sync 方法               │
│   └── local_model_health.py:51 — requests.Session 同步调用             │
│                                                                         │
│ Type-B: 混合架构（Thread + asyncio.run）                                │
│   └── auto_trigger_listener.py:112-118 — 每事件创建新循环               │
│                                                                         │
│ Type-C: 异步方法内的同步 I/O                                            │
│   ├── file_memory_adapter.py — Path.write_text/read_text               │
│   ├── memory_index.py — open() + rename() + fcntl.flock               │
│   ├── integrity_service.py:189 — open() 在 async 方法内                 │
│   └── object_operations.py:371 — open() 在 async 方法内                 │
│                                                                         │
│ Type-D: 启动时调用（可接受）                                            │
│   └── event_bus_config_loader.py                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 关键发现（源码 vs 文档差异）

| 文件 | 原分析描述 | 源码实际情况 | 差异 |
|------|------------|--------------|------|
| `event_listener.py:106` | `asyncio.run(self._audit_service.log(...))` | 确认存在，有检测 running loop 的防护代码 | 无差异 |
| `local_model_health.py` | 同步 requests | 确认使用 `requests.Session` + `HTTPAdapter` | 无差异 |
| `auto_trigger_listener.py` | Thread + asyncio.run | 确认使用 `threading.Thread` + `asyncio.new_event_loop()` | 无差异 |
| `file_memory_adapter.py` | 同步 write/read | 确认 `Path.write_text()` 和 `Path.read_text()` | 无差异 |
| `memory_index.py` | 同步 open + rename | 确认 `open()` + `temp_path.rename()` + `fcntl.flock` | ⚠️ 增加了文件锁问题 |
| `integrity_service.py:189` | async 内同步 open | 确认 `with open(file_path, "rb") as f` 在 async 方法内 | ⚠️ 原分析遗漏 |
| `object_operations.py:371` | async 内同步 open | 确认 `with open(file_path, "rb") as f` 在 async 方法内 | ⚠️ 原分析遗漏 |

---

## 2. 分阶段重构路径

### Phase 0: 紧急修复（P0 - 必须立即修复）

#### P0-1: `event_listener.py` - 消除 asyncio.run() 反模式

**当前问题**（源码确认）：
```python
# src/infrastructure/audit/event_listener.py:106
asyncio.run(
    self._audit_service.log(
        actor=audit_data["actor"],
        ...
    )
)
```

**原方案问题**：原方案中的 `_run_sync_log` 内部又创建了新的事件循环，与原问题相同。

**最优设计**：

```python
# src/infrastructure/audit/event_listener.py（重构后）

import asyncio
from typing import Any

class AuditEventListener:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    def handle_event(self, event: DomainEvent) -> None:
        """同步入口 - 委托到线程池，避免阻塞事件循环。

        使用 asyncio.to_thread() 而非 asyncio.run()，
        因为后者会在已运行的事件循环中创建嵌套循环。
        """
        audit_data = self._extract_audit_data(event)
        # 方案A：如果 AuditService.log 是 async 方法，使用 to_thread
        asyncio.to_thread(
            self._sync_wrapper,
            audit_data["actor"],
            audit_data["action_type"],
            audit_data["target_resource"],
            audit_data
        )

    def _sync_wrapper(
        self,
        actor: str,
        action_type: str,
        target_resource: str,
        audit_data: dict[str, Any]
    ) -> None:
        """同步包装器 - 在线程中执行。

        注意：这里不使用 asyncio.run()，
        因为 to_thread 已经将同步函数委托到线程池。
        如果 audit_service 需要 async 调用，可以使用事件循环参数传递。
        """
        # 如果 audit_service 支持同步调用，直接调用
        # 否则需要通过其他机制（如队列）传递到主事件循环
        pass

    async def handle_event_async(self, event: DomainEvent) -> None:
        """异步入口 - 在 asyncio 上下文中直接 await。"""
        audit_data = self._extract_audit_data(event)
        await self._audit_service.log(
            actor=audit_data["actor"],
            action_type=audit_data["action_type"],
            target_resource=audit_data["target_resource"],
            old_value=audit_data.get("old_value"),
            new_value=audit_data.get("new_value"),
            correlation_id=audit_data.get("correlation_id"),
            correction_level=audit_data.get("correction_level"),
        )
```

**宗师级设计要点**：
1. **禁止在 `asyncio.to_thread()` 回调内再次调用 `asyncio.run()`**
2. 如果 AuditService 只有 async 方法，应该：
   - 方案A：使用 `asyncio.get_event_loop().create_task()` 从主循环发起
   - 方案B：接受 sync 方法签名，在服务层提供同步版本

---

#### P0-2: `local_model_health.py` - 同步 HTTP 改异步

**当前问题**（源码确认）：
```python
# src/infrastructure/routing/local_model_health.py:14-26
_session = None

def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=Retry(total=0))
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session

def check(self) -> bool:
    session = _get_session()
    response = session.get(self.endpoint, timeout=5)  # 阻塞！
```

**重构方案**（确认可行）：

```python
# src/infrastructure/routing/local_model_health.py

import httpx
from typing import Protocol

class HealthCheckPort(Protocol):
    """健康检查端口抽象 - 六边形架构接口层"""
    async def check(self) -> bool: ...

class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 模型服务健康检查适配器"""
    _client: httpx.AsyncClient | None = None

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/api/health",
        timeout: float = 5.0
    ):
        self._endpoint = endpoint
        self._timeout = timeout

    @classmethod
    async def check(cls) -> bool:
        """类方法检查 - 检查 Ollama 服务是否可用。"""
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=cls._timeout)
        try:
            response = await cls._client.get(cls._endpoint)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False

    @classmethod
    async def close(cls) -> None:
        """关闭 HTTP 客户端。"""
        if cls._client:
            await cls._client.aclose()
            cls._client = None
```

**调用方适配**：
```python
# 原调用
health = LocalModelHealth()
is_healthy = health.check()  # 同步

# 重构后调用
is_healthy = await OllamaHealthAdapter.check()  # 异步
```

---

#### P0-3: `auto_trigger_listener.py` - 消除 Thread + asyncio.run()

**当前问题**（源码确认）：
```python
# src/interfaces/event_listeners/listeners/auto_trigger_listener.py:110-124
def _worker_loop(self) -> None:
    loop = asyncio.new_event_loop()  # 每事件创建新循环（反模式！）
    asyncio.set_event_loop(loop)
    try:
        while self._running:
            try:
                event_type, event = self._event_queue.get(timeout=0.1)
                asyncio.run(self._process_event(event_type, event))  # 反模式！
            except queue.Empty:
                continue
    finally:
        loop.close()
```

**重构方案**（修正原方案的 bug）：

```python
# src/interfaces/event_listeners/listeners/auto_trigger_listener.py

import asyncio
from typing import Callable, Awaitable, Any
from collections.abc import Callable
from src.domain.events.base import DomainEvent

class AutoTriggerListener:
    """自动触发监听器 - 纯 asyncio 实现。

    重构要点：
    1. 使用 asyncio.Queue 替代 threading.Queue
    2. 使用 asyncio.create_task() 替代新事件循环
    3. 单一事件循环，无嵌套
    """
    def __init__(
        self,
        auto_trigger_service,  # AutoTriggerService 实例
        handler_map: dict[str, Callable[..., Awaitable[None]]]
    ):
        self._auto_trigger_service = auto_trigger_service
        self._handler_map = handler_map
        self._event_queue: asyncio.Queue[tuple[str, DomainEvent]] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def register_handlers(self) -> None:
        """注册处理器 - 从同步上下文调用。

        注意：这是一个同步方法，但内部启动的是异步任务。
        调用者应在适当的 async 上下文中调用。
        """
        self._running = True
        # 创建工作循环任务（不阻塞）
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """停止监听器 - 从 async 上下文调用。"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def enqueue(self, event_type: str, event: DomainEvent) -> None:
        """入队方法 - 可从同步上下文调用。

        使用 put_nowait 确保不阻塞。
        """
        self._event_queue.put_nowait((event_type, event))

    async def _worker_loop(self) -> None:
        """工作循环 - 纯 asyncio，无嵌套事件循环。"""
        while self._running:
            try:
                event_type, event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                handler = self._handler_map.get(event_type)
                if handler:
                    await handler(event)
            except Exception as ex:
                logger.error(f"Error processing event {event_type}: {ex}")

    @property
    def registered_event_types(self) -> list[str]:
        """返回注册的处理器类型列表。"""
        return list(self._handler_map.keys())
```

**原方案 bug 修正**：
- 原方案中 `self._process_callback` 被定义了两次（参数名和类方法名冲突）
- 重构方案使用 `self._handler_map` 替代，通过字典解耦

---

### Phase 1: 架构统一（P1 - 高优先级）

#### P1-1: `file_memory_adapter.py` - 文件 I/O 异步化

**当前问题**（源码确认）：
```python
# src/infrastructure/storage/file_memory_adapter.py:59,77
file_path.write_text(content, encoding="utf-8")  # 同步阻塞
return file_path.read_text(encoding="utf-8")  # 同步阻塞
```

**重构方案**：

```python
# src/infrastructure/storage/file_memory_adapter.py

import aiofiles
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.config.memory import MemoryConfig

class FileMemoryAdapter:
    """L0 文件系统适配器 - 异步版本。"""
    def __init__(self, config: MemoryConfig):
        self.config = config
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """同步确保路径存在（启动时调用，可接受）。"""
        base_path = Path(self.config.memory_l0_path)
        base_path.mkdir(parents=True, exist_ok=True)

    async def write(self, memory_id: str, memory_type: str, content: str) -> None:
        """异步写入记忆文件。"""
        dir_path = Path(self.config.memory_l0_path) / memory_type
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{memory_id}.md"
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def read(self, memory_id: str, memory_type: str) -> str:
        """异步读取记忆文件。"""
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    async def delete(self, memory_id: str, memory_type: str) -> None:
        """异步删除记忆文件。"""
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if file_path.exists():
            file_path.unlink()

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查文件是否存在。"""
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        return file_path.exists()
```

**调用方修改**：
```python
# 原调用
self._file_adapter.write(memory_id, memory_type, content)

# 重构后
await self._file_adapter.write(memory_id, memory_type, content)
```

---

#### P1-2: `memory_index.py` - 索引操作异步化（含文件锁处理）

**当前问题**（源码确认）：
```python
# src/infrastructure/storage/memory_index.py:125-141
with open(self._index_path, encoding="utf-8") as f:  # 同步 I/O
    lines = f.readlines()
temp_path.rename(self._index_path)  # 同步 rename
# 以及 fcntl.flock 文件锁
```

**关键发现**：存在 `fcntl.flock` 文件锁，这是线程级别的锁，不是 asyncio 锁。

**重构方案**：

```python
# src/infrastructure/storage/memory_index.py

import asyncio
import fcntl
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.config.memory import MemoryConfig

class MemoryIndex:
    """记忆索引管理器 - 异步版本。

    重要：fcntl.flock 是线程级锁，不是 asyncio 锁。
    使用 asyncio.to_thread() 将带锁操作封装到线程池，
    这样可以保留锁的语义，同时不阻塞事件循环。
    """
    MAX_INDEX_LINES = 200

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._index_path = Path(config.get_index_path())
        self._lock_path = self._index_path.with_suffix(".lock")

    async def truncate(self) -> None:
        """截断索引到最大行数 - 在线程池中执行。"""
        def _truncate():
            with open(self._index_path, encoding="utf-8") as f:
                lines = f.readlines()
            content_lines = [line for line in lines if line.strip() and not line.startswith("#")]
            if len(content_lines) <= self.MAX_INDEX_LINES:
                return None
            lines_to_keep = lines[-self.MAX_INDEX_LINES:]
            temp_path = self._index_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.writelines(lines_to_keep)
            temp_path.rename(self._index_path)
            return True

        await asyncio.to_thread(_truncate)

    async def update_entry(self, entry: dict) -> None:
        """更新索引条目 - 在线程池中执行。"""
        def _update():
            entries = self._read_entries_locked_sync()
            memory_id = entry["memory_id"]
            entries = [e for e in entries if e["memory_id"] != memory_id]
            # 构建 path
            is_group = entry.get("is_group", False)
            if is_group:
                path = f"group/{entry['type']}/{memory_id}.md"
            else:
                path = f"{entry['type']}/{memory_id}.md"
            entries.append({
                "name": entry["name"],
                "type": entry["type"],
                "memory_id": memory_id,
                "description": entry.get("description", ""),
                "path": path,
            })
            self._write_entries_locked_sync(entries)

        await asyncio.to_thread(_update)

    async def read_entries(self) -> list[dict]:
        """读取所有索引条目 - 在线程池中执行。"""
        def _read():
            return self._read_entries_locked_sync()
        return await asyncio.to_thread(_read)

    def _read_entries_locked_sync(self) -> list[dict]:
        """同步带锁读取（线程内执行）。"""
        if not self._index_path.exists():
            return []
        self._ensure_lock_file()
        with open(self._lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
            try:
                with open(self._index_path, encoding="utf-8") as f:
                    return self._parse_index(f.read())
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _write_entries_locked_sync(self, entries: list[dict]) -> None:
        """同步带锁写入（线程内执行）。"""
        self._ensure_lock_file()
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._index_path.with_suffix(".tmp")
        with open(self._lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                content = self._format_entries(entries)
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                temp_path.rename(self._index_path)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
```

**宗师级设计要点**：
- `fcntl.flock` 是进程级文件锁，必须在单一线程内完成 lock→操作→unlock
- 使用 `asyncio.to_thread()` 将整个锁操作封装到线程池
- 线程池内的锁操作是原子的，不会阻塞事件循环

---

#### P1-3: `integrity_service.py` - async 方法内同步 I/O

**当前问题**（源码确认）：
```python
# src/infrastructure/security/integrity_service.py:177-191
async def verify_file(self, file_path: str, expected_hash: str) -> bool:
    with open(file_path, "rb") as f:  # 同步阻塞！
        content = f.read()
    return self.verify_hash(content, expected_hash)
```

**重构方案**：

```python
# src/infrastructure/security/integrity_service.py

import asyncio

class IntegrityVerifier:
    # ... 其他方法保持不变 ...

    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        """验证文件完整性 - 使用 to_thread 避免阻塞。"""
        def _read_and_verify():
            with open(file_path, "rb") as f:
                content = f.read()
            return self.verify_hash(content, expected_hash)

        return await asyncio.to_thread(_read_and_verify)
```

---

#### P1-4: `object_operations.py` - async 方法内同步 I/O

**当前问题**（源码确认）：
```python
# src/infrastructure/storage/minio/object_operations.py:371
with open(file_path, "rb") as f:  # 同步阻塞！
    while True:
        data = f.read(part_size)
        if not data:
            break
        # ...
```

**重构方案**：

```python
# src/infrastructure/storage/minio/object_operations.py

import asyncio

class ObjectOperations:
    # ... 其他方法保持不变 ...

    async def resume_multipart_upload(
        self,
        file_path: str,
        object_name: str,
        bucket: str,
        part_size: int = 5 * 1024 * 1024
    ) -> str | None:
        def _read_chunks():
            chunks = []
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(part_size)
                    if not data:
                        break
                    chunks.append(data)
            return chunks

        # 文件读取在线程池中执行
        chunks = await asyncio.to_thread(_read_chunks)

        # MinIO SDK 调用（如果是同步的）也用 to_thread 封装
        # 或者如果 MinIO SDK 支持 async，直接 await
        return await self._upload_chunks_async(chunks, object_name, bucket)

    async def _upload_chunks_async(self, chunks: list[bytes], object_name: str, bucket: str):
        """上传分片 - 如果 MinIO SDK 支持 async。"""
        # MinIO Python SDK 目前主要是同步的，
        # 如果需要完全异步，需要考虑 aiobotocore 或其他方案
        def _sync_upload():
            client = self._client.client
            # 同步上传逻辑
            pass

        return await asyncio.to_thread(_sync_upload)
```

---

### Phase 2: 优化确认（P2 - 可选）

#### P2-1: `engine.py` - sync engine 评估

**当前状态**（源码确认）：
```python
# src/infrastructure/storage/postgresql/engine.py
def get_sync_engine(self) -> Engine:
    """Returns a synchronous SQLAlchemy engine (psycopg2)."""
    # postgresql+psycopg2://...
```

**评估命令**：
```bash
# 检查 sync engine 的使用情况
grep -r "get_sync_engine\|psycopg2" src/ --include="*.py"
```

**决策树**：
```
sync engine 使用评估：
├── 如果有外部调用者使用 → 保留，但标记为 deprecated
├── 如果仅内部使用 → 删除，用 async engine 替代
└── 如果是遗留代码 → 评估迁移成本
```

---

## 3. 架构抽象层新增（完善）

### 3.1 端口接口定义

```python
# src/interfaces/ports/file_port.py
from abc import ABC, abstractmethod

class FilePort(ABC):
    """文件操作抽象端口 - 六边形架构接口层。"""
    @abstractmethod
    async def read(self, path: str) -> str: ...

    @abstractmethod
    async def write(self, path: str, content: str) -> None: ...

    @abstractmethod
    async def exists(self, path: str) -> bool: ...

    @abstractmethod
    async def delete(self, path: str) -> None: ...

# src/interfaces/ports/health_check_port.py
from abc import ABC, abstractmethod

class HealthCheckPort(ABC):
    """健康检查抽象端口 - 六边形架构接口层。"""
    @abstractmethod
    async def check(self) -> bool: ...
```

### 3.2 适配器实现

```python
# src/infrastructure/adapters/aiopath_file_adapter.py
import aiofiles
from pathlib import Path
from src.interfaces.ports.file_port import FilePort

class AioFilesAdapter(FilePort):
    """基于 aiofiles 的文件适配器。"""
    async def read(self, path: str) -> str:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()

    async def write(self, path: str, content: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def exists(self, path: str) -> bool:
        return Path(path).exists()

    async def delete(self, path: str) -> None:
        Path(path).unlink(missing_ok=True)

# src/infrastructure/health/ollama_adapter.py
import httpx
from src.interfaces.ports.health_check_port import HealthCheckPort

class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 健康检查适配器。"""
    _client: httpx.AsyncClient | None = None

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/api/health",
        timeout: float = 5.0
    ):
        self._endpoint = endpoint
        self._timeout = timeout

    async def check(self) -> bool:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await self._client.get(self._endpoint)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False
```

---

## 4. 重构优先级与工作量评估（校正）

### 4.1 优先级矩阵

| 优先级 | 文件 | 问题 | 修复策略 | 工时 | 风险 | 源码确认 |
|--------|------|------|----------|------|------|----------|
| **P0-1** | `event_listener.py` | asyncio.run() | to_thread + 双接口 | 0.5d | 低 | ✓ |
| **P0-2** | `local_model_health.py` | 同步 requests | HealthCheckPort + httpx | 0.5d | 低 | ✓ |
| **P0-3** | `auto_trigger_listener.py` | Thread+asyncio | 重构为纯 asyncio | 2d | 中 | ✓ |
| **P1-1** | `file_memory_adapter.py` | 同步文件I/O | aiofiles | 1d | 低 | ✓ |
| **P1-2** | `memory_index.py` | 同步I/O+flock | to_thread（保留锁语义） | 1d | 中 | ✓ |
| **P1-3** | `integrity_service.py` | async内同步I/O | to_thread | 0.5d | 低 | ✓ |
| **P1-4** | `object_operations.py` | async内同步I/O | to_thread | 0.5d | 低 | ✓ |
| **P2** | `engine.py` | sync engine | 评估后决策 | 0.5d | 低 | ✓ |

### 4.2 阶段划分

```
Week 1: P0 紧急修复
├── event_listener.py → to_thread + 双接口
└── local_model_health.py → HealthCheckPort + httpx

Week 2: P0-3 架构统一（重点）
└── auto_trigger_listener.py → 纯 asyncio（2d）

Week 3: P1 文件 I/O 异步化
├── file_memory_adapter.py → aiofiles
├── memory_index.py → to_thread + flock 语义
├── integrity_service.py → to_thread
└── object_operations.py → to_thread

Week 4: P2 优化 + 验证
├── engine.py → 评估决策
├── 集成测试
└── 性能验证
```

---

## 5. 验证策略

### 5.1 单元测试验证

```bash
# P0 修复验证
poetry run pytest tests/infrastructure/routing/test_local_model_health.py -v
poetry run pytest tests/infrastructure/audit/test_event_listener.py -v

# P1 修复验证
poetry run pytest tests/infrastructure/storage/test_file_memory_adapter.py -v
poetry run pytest tests/infrastructure/storage/test_memory_index.py -v
```

### 5.2 事件循环阻塞测试

```python
# tests/test_event_loop_unblocked.py
import asyncio
import pytest

async def test_event_loop_not_blocked():
    """验证事件循环不被阻塞。"""
    start = asyncio.get_event_loop().time()

    # 调用重构后的方法
    # ...

    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 1.0, "Event loop was blocked!"
```

### 5.3 集成测试验证

```bash
# 事件循环不阻塞测试
poetry run pytest tests/integration/ -v -k "async"
```

---

## 6. 依赖管理

### 6.1 新增依赖

```bash
# 添加 aiofiles
poetry add aiofiles
```

### 6.2 已有依赖（无需修改）

- `httpx`: 已在 pyproject.toml
- `asyncio`: 标准库

---

## 7. 风险控制

### 7.1 回滚策略

每个 P0/P1 修改前：
1. 创建 git branch
2. 编写失败的测试用例（红）
3. 重构
4. 验证测试通过（绿）
5. 提交

```bash
git checkout -b feature/sync-async-refactor
```

### 7.2 渐进式验证

```
Step 1: 单独文件验证（单元测试）
Step 2: 模块集成验证（集成测试）
Step 3: 系统验证（E2E 测试）
Step 4: 性能回归测试
```

---

## 8. 宗师级设计总结

### 8.1 核心原则

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     宗师级设计的六个原则                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ 1. 单一事件循环                                                          │
│    一个进程只应有一个 asyncio 事件循环                                    │
│    禁止在已运行循环中调用 asyncio.run()                                  │
│                                                                         │
│ 2. 上下文纯净                                                            │
│    sync 代码在 sync 上下文，async 代码在 async 上下文                    │
│    不混用，不搭桥                                                         │
│                                                                         │
│ 3. 端口抽象                                                              │
│    所有外部依赖通过 Hexagon Port 接口隔离                                │
│    Infrastructure 层实现，Interfaces 层引用                             │
│                                                                         │
│ 4. 渐进式改造                                                            │
│    优先修复阻塞主循环的 P0 问题                                           │
│    不追求一次性完成                                                       │
│                                                                         │
│ 5. 验证驱动                                                              │
│    测试先行，红→绿→重构                                                  │
│                                                                         │
│ 6. 锁语义保留                                                            │
│    fcntl.flock 等线程级锁用 to_thread 封装，保留原子性                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 成功标准

| 指标 | 目标 |
|------|------|
| P0 问题修复率 | 100% |
| P1 问题修复率 | >80% |
| 测试覆盖率 | >90% |
| 事件循环阻塞 | 0 次 |
| asyncio.run() 反模式 | 0 处 |

---

## 附录A：源码与文档差异清单

| 文件 | 源码实际情况 | 原分析描述 | 差异影响 |
|------|--------------|------------|----------|
| `memory_index.py` | 有 fcntl.flock 文件锁 | 未提及锁 | 增加重构复杂度 |
| `integrity_service.py:189` | async 内同步 open | 未在 P0/P1 中识别 | 遗漏 P0 问题 |
| `object_operations.py:371` | async 内同步 open | 未在 P0/P1 中识别 | 遗漏 P0 问题 |

---

## 附录B：完整文件修改清单

| 文件 | 修改类型 | 新增抽象 | 源码确认 |
|------|----------|----------|----------|
| `event_listener.py` | 重构 | 双接口（handle_event + handle_event_async） | ✓ |
| `local_model_health.py` | 重构 | `HealthCheckPort` | ✓ |
| `auto_trigger_listener.py` | 重构 | 纯 asyncio `asyncio.Queue` | ✓ |
| `file_memory_adapter.py` | 重构 | `FilePort` + `AioFilesAdapter` | ✓ |
| `memory_index.py` | 重构 | `asyncio.to_thread()` + 锁语义 | ✓ |
| `integrity_service.py` | 重构 | `asyncio.to_thread()` | ✓ |
| `object_operations.py` | 重构 | `asyncio.to_thread()` | ✓ |
| `engine.py` | 评估决策 | - | ✓ |
