# SISYS 同步代码最优重构方案（第三版）

**生成日期**: 2026-05-01
**版本**: v3.0（第二轮审查 - 深入分析调用链与依赖关系）
**依据**: sync-code-analysis.md + sisys-sync-architecture.md + sync-code-design-mastery.md + 源码实地审查 + 调用链分析
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

## 1. 当前问题全景（第二轮审查校正）

### 1.1 问题分布矩阵

| 层级 | P0（阻塞循环） | P1（性能风险） | P2（可接受） |
|------|---------------|---------------|-------------|
| Infrastructure | 4 | 4 | 4 |
| Interfaces | 1 | 0 | 0 |
| **总计** | **5** | **4** | **4** |

### 1.2 关键发现：调用链分析揭示更深层问题

通过源码审查和调用链分析，发现以下深层问题：

#### 发现1：event_listener.py 的设计悖论

**源码位置**：`src/infrastructure/audit/event_listener.py:74-121`

**当前设计问题**：
```python
def handle_event(self, event: DomainEvent) -> None:
    # 1. 检测是否在 async 上下文
    try:
        asyncio.get_running_loop()
        raise RuntimeError("handle_event() called from async context")
    except RuntimeError as e:
        if "no running event loop" not in str(e).lower():
            raise

    # 2. 如果在 sync 上下文，使用 asyncio.run()
    asyncio.run(self._audit_service.log(...))  # 问题！
```

**悖论**：
- `AuditService.log()` 是 `async` 方法（见 `src/domain/services/audit_service.py:34`）
- `handle_event()` 被设计为 sync 方法，但需要调用 async 方法
- `asyncio.run()` 创建新事件循环会阻塞调用线程

**深层问题**：
- 如果从 async 上下文调用 `handle_event()`，会抛出 RuntimeError（这不是优雅降级）
- 原方案中的 `_sync_wrapper` 内部又创建事件循环，与原问题相同

**正确解决方案**：

```python
# 方案A：从主事件循环调度任务（推荐）
def handle_event(self, event: DomainEvent) -> None:
    """同步入口 - 在 sync 上下文中安全调用。"""
    audit_data = self._extract_audit_data(event)
    try:
        loop = asyncio.get_running_loop()
        # 在已有事件循环中调度任务（不阻塞）
        loop.call_soon(
            lambda: asyncio.create_task(
                self._audit_service.log(
                    actor=audit_data["actor"],
                    action_type=audit_data["action_type"],
                    target_resource=audit_data["target_resource"],
                    old_value=audit_data.get("old_value"),
                    new_value=audit_data.get("new_value"),
                    correlation_id=audit_data.get("correlation_id"),
                    correction_level=audit_data.get("correction_level"),
                )
            )
        )
    except RuntimeError:
        # 没有运行中的事件循环，使用 to_thread
        asyncio.to_thread(self._async_log_wrapper, audit_data)

async def _async_log_wrapper(self, audit_data: dict[str, Any]) -> None:
    """Async 包装器 - 在 to_thread 上下文中执行。"""
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

**宗师级要点**：
- `loop.call_soon()` 将任务调度到事件循环，不阻塞
- 在 to_thread 中执行 async 函数需要新的事件循环，但这是隔离的

---

#### 发现2：auto_trigger_listener.py 的双层反模式

**源码位置**：`src/interfaces/event_listeners/listeners/auto_trigger_listener.py:110-124`

**源码确认的问题**：
```python
def _worker_loop(self) -> None:
    loop = asyncio.new_event_loop()      # 问题1：每事件创建新循环
    asyncio.set_event_loop(loop)
    try:
        while self._running:
            try:
                event_type, event = self._event_queue.get(timeout=0.1)
                asyncio.run(self._process_event(event_type, event))  # 问题2：嵌套 asyncio.run()
            except queue.Empty:
                continue
    finally:
        loop.close()
```

**问题分析**：
1. 外层是后台线程，每次创建新的事件循环
2. 在这个新循环中调用 `asyncio.run()` 处理事件
3. 每次处理事件都重复这个模式

**重构方案**：

```python
# src/interfaces/event_listeners/listeners/auto_trigger_listener.py

import asyncio
from typing import Callable, Awaitable, Any
from collections.abc import Callable
from src.domain.events.base import DomainEvent

class AutoTriggerListener:
    """自动触发监听器 - 纯 asyncio 实现。

    架构变更：
    - 移除 threading.Thread
    - 使用 asyncio.Queue 作为事件队列
    - 使用 asyncio.create_task() 处理事件
    - 单一事件循环，无嵌套
    """
    def __init__(
        self,
        auto_trigger_service,  # AutoTriggerService 实例
        registered_event_types: list[str]
    ):
        self._auto_trigger_service = auto_trigger_service
        self._registered_event_types = registered_event_types
        self._event_queue: asyncio.Queue[tuple[str, DomainEvent]] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._handler_map: dict[str, Callable[..., Awaitable[None]]] = {}

    def register_handlers(self, event_listener) -> None:
        """注册处理器 - 从同步上下文调用。"""
        self._running = True
        # 创建工作循环任务
        self._worker_task = asyncio.create_task(self._worker_loop())

        for event_type in self._registered_event_types:
            handler = self._create_handler(event_type)
            event_listener.on_event(event_type, handler)
            logger.debug(f"Registered handler for event type: {event_type}")

    def _create_handler(self, event_type: str) -> Callable[[DomainEvent], None]:
        """创建处理器函数。"""
        def handle_event(event: DomainEvent) -> None:
            try:
                self._event_queue.put_nowait((event_type, event))
            except Exception as e:
                logger.error(f"Failed to queue event {event_type}: {e}")
        return handle_event

    async def stop(self) -> None:
        """停止监听器。"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

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
                await self._process_event(event_type, event)
            except Exception as ex:
                logger.error(f"Error processing event {event_type}: {ex}")

    async def _process_event(self, event_type: str, event: DomainEvent) -> None:
        """处理事件 - 直接在主事件循环中 await。"""
        try:
            if event_type == "HeartbeatTriggered":
                from src.domain.events.heartbeat_events import HeartbeatTriggered
                heartbeat_event = HeartbeatTriggered.from_dict(event.to_dict())
                triggered = await self._auto_trigger_service.on_heartbeat_event(heartbeat_event)
            else:
                triggered = await self._auto_trigger_service.on_domain_event(event)

            if triggered:
                logger.info(f"Trigger processed: type={triggered.trigger_type}, session_id={triggered.session_id}")
        except Exception as e:
            logger.error(f"Failed to process event {event_type}: {e}")
```

---

#### 发现3：调用方约束决定重构方案

通过分析 `EventListener.dispatch()` 的实现：

```python
# src/domain/events/listener.py:67-86
def dispatch(self, event: DomainEvent) -> None:
    """Dispatch an event to all registered handlers.

    Each handler is wrapped in try/except to prevent one handler's
    failure from blocking subsequent handlers.
    """
    errors: list[Exception] = []
    for handler in self._handlers.get(event.event_type, []):
        try:
            handler(event)  # 调用同步 handler
        except Exception as e:
            errors.append(e)
```

**约束**：
- `EventListener.dispatch()` 调用同步 `handler(event)`
- handler 必须是 `Callable[[DomainEvent], None]`
- 如果 handler 内需要调用 async 方法，必须有桥接机制

**因此**：
- `handle_event()` 必须是同步方法
- 但它需要调用 `AuditService.log()` 这个 async 方法
- 这就是为什么需要 `asyncio.run()` 或类似的桥接机制

---

## 2. 分阶段重构路径

### Phase 0: 紧急修复（P0）

#### P0-1: `event_listener.py` - asyncio.run() 反模式

**问题根因**：sync 方法调用 async 方法，需要桥接机制

**最优重构方案**：

```python
# src/infrastructure/audit/event_listener.py

import asyncio
from typing import Any

class AuditEventListener:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    def handle_event(self, event: DomainEvent) -> None:
        """同步入口 - 用于 EventListener.sync_dispatch() 场景。

        策略：根据上下文选择合适的桥接方式
        1. 如果有运行中的事件循环，使用 call_soon 调度任务
        2. 如果没有事件循环（在 to_thread 中），创建新循环执行
        """
        audit_data = self._extract_audit_data(event)
        if audit_data is None:
            logger.debug(f"Event {event.event_type} filtered, not recording audit")
            return

        try:
            loop = asyncio.get_running_loop()
            # 已在事件循环中，使用 call_soon 调度
            loop.call_soon(
                lambda: asyncio.create_task(
                    self._audit_service.log(
                        actor=audit_data["actor"],
                        action_type=audit_data["action_type"],
                        target_resource=audit_data["target_resource"],
                        old_value=audit_data.get("old_value"),
                        new_value=audit_data.get("new_value"),
                        correlation_id=audit_data.get("correlation_id"),
                        correction_level=audit_data.get("correction_level"),
                    )
                )
            )
        except RuntimeError:
            # 不在事件循环中（在 to_thread 回调中），创建新循环
            asyncio.run(self._audit_service.log(
                actor=audit_data["actor"],
                action_type=audit_data["action_type"],
                target_resource=audit_data["target_resource"],
                old_value=audit_data.get("old_value"),
                new_value=audit_data.get("new_value"),
                correlation_id=audit_data.get("correlation_id"),
                correction_level=audit_data.get("correction_level"),
            ))

    async def handle_event_async(self, event: DomainEvent) -> None:
        """异步入口 - 用于 RabbitMQ consumer 等 async 场景。"""
        audit_data = self._event_to_audit(event)
        if audit_data is None:
            logger.debug(f"Event {event.event_type} filtered, not recording audit")
            return

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

**宗师级要点**：
- 使用 `loop.call_soon()` + `create_task()` 在已有循环中调度，不阻塞
- 只有在真正没有循环时才用 `asyncio.run()`（to_thread 回调场景）
- 消除原设计中"检测到循环就报错"的悖论设计

---

#### P0-2: `local_model_health.py` - 同步 HTTP 改异步

**当前问题**：使用同步 `requests.Session`

**重构方案**：

```python
# src/infrastructure/routing/local_model_health.py

import httpx
from typing import Protocol

class HealthCheckPort(Protocol):
    """健康检查端口抽象"""
    async def check(self) -> bool: ...

class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 模型健康检查适配器"""
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
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=cls._timeout)
        try:
            response = await cls._client.get(cls._endpoint)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False

    @classmethod
    async def close(cls) -> None:
        if cls._client:
            await cls._client.aclose()
            cls._client = None
```

---

#### P0-3: `auto_trigger_listener.py` - 消除 Thread + asyncio.run()

**问题**：后台线程 + 每事件创建新事件循环

**重构方案**：见上方"发现2"

---

### Phase 1: 架构统一（P1）

#### P1-1: `file_memory_adapter.py` - 文件 I/O 异步化

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
        self._ensure_base_path()  # 启动时调用，可接受

    def _ensure_base_path(self) -> None:
        """同步确保路径存在。"""
        base_path = Path(self.config.memory_l0_path)
        base_path.mkdir(parents=True, exist_ok=True)

    async def write(self, memory_id: str, memory_type: str, content: str) -> None:
        """异步写入。"""
        dir_path = Path(self.config.memory_l0_path) / memory_type
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{memory_id}.md"
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def read(self, memory_id: str, memory_type: str) -> str:
        """异步读取。"""
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    async def delete(self, memory_id: str, memory_type: str) -> None:
        """异步删除。"""
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if file_path.exists():
            file_path.unlink()

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查是否存在。"""
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        return file_path.exists()
```

---

#### P1-2: `memory_index.py` - 索引操作异步化（含文件锁）

**问题**：`fcntl.flock` 文件锁 + 同步 I/O

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

    fcntl.flock 是线程级锁，使用 asyncio.to_thread() 封装到线程池，
    保留锁的原子性语义，同时不阻塞事件循环。
    """
    MAX_INDEX_LINES = 200

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._index_path = Path(config.get_index_path())
        self._lock_path = self._index_path.with_suffix(".lock")

    async def truncate(self) -> None:
        """截断索引 - 在线程池中执行。"""
        def _truncate():
            with open(self._index_path, encoding="utf-8") as f:
                lines = f.readlines()
            content_lines = [line for line in lines if line.strip() and not line.startswith("#")]
            if len(content_lines) <= self.MAX_INDEX_LINES:
                return
            lines_to_keep = lines[-self.MAX_INDEX_LINES:]
            temp_path = self._index_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.writelines(lines_to_keep)
            temp_path.rename(self._index_path)

        await asyncio.to_thread(_truncate)

    async def update_entry(self, entry: dict) -> None:
        """更新索引条目 - 在线程池中执行。"""
        def _update():
            entries = self._read_entries_locked_sync()
            memory_id = entry["memory_id"]
            entries = [e for e in entries if e["memory_id"] != memory_id]
            is_group = entry.get("is_group", False)
            path = f"group/{entry['type']}/{memory_id}.md" if is_group else f"{entry['type']}/{memory_id}.md"
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
        return await asyncio.to_thread(self._read_entries_locked_sync)

    def _read_entries_locked_sync(self) -> list[dict]:
        """同步带锁读取。"""
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
        """同步带锁写入。"""
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

    def _ensure_lock_file(self) -> None:
        """确保锁文件存在。"""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.touch(exist_ok=True)

    def _parse_index(self, content: str) -> list[dict]:
        """解析索引内容。"""
        import re
        INDEX_LINE_PATTERN = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = INDEX_LINE_PATTERN.match(line)
            if match:
                name, path, desc = match.groups()
                parts = Path(path).parts
                if len(parts) >= 2:
                    is_group = parts[0] == "group"
                    mem_type = parts[1] if is_group else parts[0]
                    mem_id = Path(path).stem
                    entries.append({
                        "name": name,
                        "type": mem_type,
                        "memory_id": mem_id,
                        "description": desc,
                        "is_group": is_group,
                    })
        return entries

    def _format_entries(self, entries: list[dict]) -> str:
        """格式化索引条目。"""
        lines = []
        for entry in entries:
            path = entry.get("path")
            if not path:
                path = f"group/{entry['type']}/{entry['memory_id']}.md" if entry.get("is_group") else f"{entry['type']}/{entry['memory_id']}.md"
            lines.append(f"- [{entry['name']}]({path}) — {entry.get('description', '')}")
        return "\n".join(lines) + "\n"
```

---

#### P1-3: `integrity_service.py` - async 方法内同步 I/O

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
        # 文件读取在线程池中执行
        chunks = await asyncio.to_thread(self._read_chunks_sync, file_path, part_size)

        # MinIO 操作在线程池中执行（如果 SDK 是同步的）
        return await asyncio.to_thread(
            self._upload_chunks_sync,
            chunks,
            object_name,
            bucket
        )

    @staticmethod
    def _read_chunks_sync(file_path: str, part_size: int) -> list[bytes]:
        """同步读取文件分片。"""
        chunks = []
        with open(file_path, "rb") as f:
            while True:
                data = f.read(part_size)
                if not data:
                    break
                chunks.append(data)
        return chunks

    def _upload_chunks_sync(self, chunks: list[bytes], object_name: str, bucket: str):
        """同步上传分片。"""
        client = self._client.client
        parts = []
        for part_number, data in enumerate(chunks, 1):
            etag = client._put_object(
                bucket,
                object_name,
                data,
                length=len(data),
                part_number=part_number,
            )
            parts.append({"PartNumber": part_number, "ETag": etag})
        return parts
```

---

## 3. 架构抽象层新增

### 3.1 端口接口定义

```python
# src/interfaces/ports/file_port.py
from abc import ABC, abstractmethod

class FilePort(ABC):
    """文件操作抽象端口"""
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
    """健康检查抽象端口"""
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
    """基于 aiofiles 的文件适配器"""
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
    """Ollama 健康检查适配器"""
    _client: httpx.AsyncClient | None = None

    def __init__(self, endpoint: str = "http://localhost:11434/api/health", timeout: float = 5.0):
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

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
```

---

## 4. 重构优先级与工作量评估

### 4.1 优先级矩阵

| 优先级 | 文件 | 问题 | 修复策略 | 工时 | 风险 | 调用链约束 |
|--------|------|------|----------|------|------|------------|
| **P0-1** | `event_listener.py` | asyncio.run() | call_soon + create_task | 0.5d | 低 | EventListener.dispatch() 需要 sync handler |
| **P0-2** | `local_model_health.py` | 同步 requests | HealthCheckPort + httpx | 0.5d | 低 | 无 |
| **P0-3** | `auto_trigger_listener.py` | Thread+asyncio | 重构为纯 asyncio | 2d | 中 | EventListener.on_event() 需要 sync handler |
| **P1-1** | `file_memory_adapter.py` | 同步文件I/O | aiofiles | 1d | 低 | 调用方需要改为 await |
| **P1-2** | `memory_index.py` | 同步I/O+flock | to_thread（保留锁语义） | 1d | 中 | 调用方需要改为 await |
| **P1-3** | `integrity_service.py` | async内同步I/O | to_thread | 0.5d | 低 | 无 |
| **P1-4** | `object_operations.py` | async内同步I/O | to_thread | 0.5d | 低 | 无 |
| **P2** | `engine.py` | sync engine | 评估后决策 | 0.5d | 低 | 无 |

### 4.2 阶段划分

```
Week 1: P0 紧急修复
├── event_listener.py → call_soon + create_task（0.5d）
└── local_model_health.py → HealthCheckPort + httpx（0.5d）

Week 2: P0-3 架构统一（重点）
└── auto_trigger_listener.py → 纯 asyncio（2d）

Week 3: P1 文件 I/O 异步化
├── file_memory_adapter.py → aiofiles（1d）
├── memory_index.py → to_thread + flock 语义（1d）
├── integrity_service.py → to_thread（0.5d）
└── object_operations.py → to_thread（0.5d）

Week 4: P2 优化 + 验证
├── engine.py → 评估决策（0.5d）
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

async def test_event_loop_not_blocked():
    """验证事件循环不被阻塞。"""
    start = asyncio.get_event_loop().time()
    # 调用重构后的方法
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 1.0, "Event loop was blocked!"
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

```bash
git checkout -b feature/sync-async-refactor-v3
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

### 8.1 核心原则（新增两项）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     宗师级设计的八个原则                                 │
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
│ 7. 调用链约束优先                                                        │
│    分析调用链确定约束，选择匹配的重构方案                                  │
│    例：EventListener.dispatch() 需要 sync handler                       │
│                                                                         │
│ 8. 优雅降级                                                              │
│    使用 call_soon() + create_task() 在已有循环中调度                     │
│    只有在没有循环时才用 asyncio.run()                                     │
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

## 附录A：第二轮审查新发现

| 发现 | 文件 | 影响 |
|------|------|------|
| EventListener.dispatch() 需要 sync handler | event_listener.py | 影响重构方案选择 |
| AuditService.log() 是 async 方法 | audit_service.py | 无 sync 版本可用 |
| AutoTriggerService 是纯 async | auto_trigger_service.py | handler 必须桥接 |

---

## 附录B：完整文件修改清单

| 文件 | 修改类型 | 新增抽象 | 调用链约束 |
|------|----------|----------|------------|
| `event_listener.py` | 重构 | call_soon + create_task | EventListener.dispatch() 需要 sync |
| `local_model_health.py` | 重构 | `HealthCheckPort` | 无 |
| `auto_trigger_listener.py` | 重构 | 纯 asyncio Queue | EventListener.on_event() 需要 sync |
| `file_memory_adapter.py` | 重构 | `FilePort` + `AioFilesAdapter` | 调用方改 await |
| `memory_index.py` | 重构 | to_thread + 锁语义 | 调用方改 await |
| `integrity_service.py` | 重构 | to_thread | 无 |
| `object_operations.py` | 重构 | to_thread | 无 |
| `engine.py` | 评估决策 | - | 无 |
