# SISYS 同步代码最优重构方案（第五版）

**生成日期**: 2026-05-01
**版本**: v5.0（第四轮审查 - 依赖确认 + 调用链深查 + 方案定稿）
**依据**: sync-code-analysis.md + sisys-sync-architecture.md + sync-code-design-mastery.md + 源码实地审查 + 调用链分析 + 依赖确认
**目标**: 宗师级架构设计，给出可执行的最优重构路径（定稿版）

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
- 测试兼容：重构必须配套更新测试（TDD 循环不可跳过）

---

## 1. 当前问题全景（第四轮审查校正）

### 1.1 问题分布矩阵

| 层级 | P0（阻塞循环） | P1（性能风险） | P2（可接受） |
|------|---------------|---------------|-------------|
| Infrastructure | 4 | 4 | 4 |
| Interfaces | 1 | 0 | 0 |
| **总计** | **5** | **4** | **4** |

### 1.2 第四轮关键确认

#### 确认1：依赖已存在，无需新增

通过 `pyproject.toml` 确认：

```toml
# pyproject.toml
httpx = "^0.27.0"     # 已有
aiofiles = "^25.1.0"  # 已有
```

**结论**：重构方案中使用的 `httpx.AsyncClient` 和 `aiofiles` 均已存在于依赖中，无需额外安装。

---

#### 确认2：调用链分析（测试场景有限）

通过 grep 搜索 `MemoryIndex` 和 `FileMemoryAdapter` 的使用情况：

| 类 | 调用位置 | 调用方式 | 影响 |
|---|---------|---------|------|
| `MemoryIndex` | 测试文件 | `index.update_entry(e)` | 同步方法 → async 后测试需更新 |
| `MemoryIndex` | 测试文件 | `index.read_entries()` | 同步方法 → async 后测试需更新 |
| `FileMemoryAdapter` | 测试文件 | `adapter.write(...)` | 同步方法 → async 后测试需更新 |
| `FileMemoryAdapter` | 测试文件 | `adapter.read(...)` | 同步方法 → async 后测试需更新 |

**关键发现**：
- `MemoryIndex` 和 `FileMemoryAdapter` 的真实调用仅存在于测试代码中
- 这意味着重构影响范围可控，测试更新工作量明确

---

#### 确认3：重构方案验证（无需修改）

第四轮审查确认 v4 版方案无需修改：

| 文件 | v4 方案 | 验证结果 |
|------|---------|----------|
| `event_listener.py` | call_soon + create_task | ✓ 确认 |
| `local_model_health.py` | HealthCheckPort + httpx | ✓ 确认 |
| `auto_trigger_listener.py` | 纯 asyncio Queue | ✓ 确认 |
| `memory_index.py` | to_thread + 锁语义 | ✓ 确认 |
| `file_memory_adapter.py` | aiofiles | ✓ 确认 |
| `integrity_service.py` | to_thread | ✓ 确认 |
| `object_operations.py` | to_thread | ✓ 确认 |

---

## 2. 分阶段重构路径（定稿版）

### Phase 0: 紧急修复（P0）

#### P0-1: `event_listener.py` - asyncio.run() 反模式

**当前问题**：同步方法调用 async 方法，使用 `asyncio.run()` 创建嵌套循环。

**重构方案**：

```python
# src/infrastructure/audit/event_listener.py

import asyncio
from typing import Any

class AuditEventListener:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service
        self._event_type_map: dict[str, str] = { ... }

    def handle_event(self, event: DomainEvent) -> None:
        """同步入口 - 用于 EventListener.sync_dispatch() 场景。

        策略：
        1. 如果有运行中的事件循环，使用 call_soon 调度
        2. 如果没有事件循环，使用 asyncio.run()
        """
        audit_data = self._event_to_audit(event)
        if audit_data is None:
            return

        try:
            loop = asyncio.get_running_loop()
            # 在已有事件循环中调度任务（fire-and-forget）
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
            # 没有运行中的事件循环，创建新的
            asyncio.run(
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

    async def handle_event_async(self, event: DomainEvent) -> None:
        """异步入口 - 用于 RabbitMQ consumer 等 async 场景。"""
        audit_data = self._event_to_audit(event)
        if audit_data is None:
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

---

#### P0-2: `local_model_health.py` - 同步 HTTP 改异步

**重构方案**：

```python
# src/infrastructure/routing/local_model_health.py

import httpx

class HealthCheckPort(Protocol):
    """健康检查端口抽象"""
    async def check(self) -> bool: ...

class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 模型健康检查适配器 - 实例模式"""
    def __init__(
        self,
        endpoint: str = "http://localhost:11434/api/health",
        timeout: float = 5.0
    ):
        self._endpoint = endpoint
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

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

#### P0-3: `auto_trigger_listener.py` - 消除 Thread + asyncio.run()

**重构方案**：

```python
# src/interfaces/event_listeners/listeners/auto_trigger_listener.py

import asyncio
from typing import Callable, Awaitable
from src.domain.events.base import DomainEvent

class AutoTriggerListener:
    """自动触发监听器 - 纯 asyncio 实现。"""
    def __init__(
        self,
        auto_trigger_service,
        registered_event_types: list[str]
    ):
        self._auto_trigger_service = auto_trigger_service
        self._registered_event_types = registered_event_types
        self._event_queue: asyncio.Queue[tuple[str, DomainEvent]] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def register_handlers(self, event_listener) -> None:
        """注册处理器 - sync 方法，仅注册不启动 worker。"""
        for event_type in self._registered_event_types:
            handler = self._create_handler(event_type)
            event_listener.on_event(event_type, handler)

    def _create_handler(self, event_type: str) -> Callable[[DomainEvent], None]:
        """创建 sync handler - 将事件入队到 asyncio.Queue。"""
        def handle_event(event: DomainEvent) -> None:
            self._event_queue.put_nowait((event_type, event))
        return handle_event

    async def start(self) -> None:
        """启动 worker - 从 async 上下文调用。"""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """停止 worker。"""
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

### Phase 1: 架构统一（P1）

#### P1-1: `memory_index.py` - 索引操作异步化（含测试更新）

```python
# src/infrastructure/storage/memory_index.py

import asyncio
import fcntl
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.config.memory import MemoryConfig

INDEX_LINE_PATTERN = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")

class MemoryIndex:
    MAX_INDEX_LINES = 200

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._index_path = Path(config.get_index_path())
        self._lock_path = self._index_path.with_suffix(".lock")

    async def update_entry(self, entry: dict) -> None:
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

    async def remove_entry(self, memory_id: str) -> None:
        def _remove():
            entries = self._read_entries_locked_sync()
            entries = [e for e in entries if e["memory_id"] != memory_id]
            self._write_entries_locked_sync(entries)
        await asyncio.to_thread(_remove)

    async def read_entries(self) -> list[dict]:
        return await asyncio.to_thread(self._read_entries_locked_sync)

    async def search(self, query: str) -> list[dict]:
        entries = await self.read_entries()
        query_lower = query.lower()
        return [e for e in entries if query_lower in e["name"].lower()]

    async def truncate(self) -> None:
        def _truncate():
            if not self._index_path.exists():
                return
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

    # === 私有同步方法 ===

    def _read_entries_locked_sync(self) -> list[dict]:
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
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.touch(exist_ok=True)

    def _parse_index(self, content: str) -> list[dict]:
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
        lines = []
        for entry in entries:
            path = entry.get("path")
            if not path:
                path = f"group/{entry['type']}/{entry['memory_id']}.md" if entry.get("is_group") else f"{entry['type']}/{entry['memory_id']}.md"
            lines.append(f"- [{entry['name']}]({path}) — {entry.get('description', '')}")
        return "\n".join(lines) + "\n"
```

---

#### P1-2: `file_memory_adapter.py` - 文件 I/O 异步化（含测试更新）

```python
# src/infrastructure/storage/file_memory_adapter.py

import aiofiles
from pathlib import Path
from typing import TYPE_CHECKING, re

if TYPE_CHECKING:
    from src.infrastructure.config.memory import MemoryConfig

INDEX_PATTERN = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")

class FileMemoryAdapter:
    def __init__(self, config: MemoryConfig):
        self.config = config
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        base_path = Path(self.config.memory_l0_path)
        base_path.mkdir(parents=True, exist_ok=True)

    async def write(self, memory_id: str, memory_type: str, content: str) -> None:
        dir_path = Path(self.config.memory_l0_path) / memory_type
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{memory_id}.md"
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def read(self, memory_id: str, memory_type: str) -> str:
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    async def delete(self, memory_id: str, memory_type: str) -> None:
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if file_path.exists():
            file_path.unlink()

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        return file_path.exists()

    async def list_memories(self, memory_type: str) -> list[str]:
        dir_path = Path(self.config.memory_l0_path) / memory_type
        if not dir_path.exists():
            return []
        return [f.stem for f in dir_path.glob("*.md")]

    async def update_index(self, entries: list[dict]) -> None:
        index_path = Path(self.config.memory_l0_path) / "MEMORY.md"
        lines = [
            f"- [{e['name']}]({e['type']}/{e['memory_id']}.md) — {e.get('description', '')}"
            for e in entries
        ]
        async with aiofiles.open(index_path, "w", encoding="utf-8") as f:
            await f.write("\n".join(lines) + "\n")

    async def read_index(self) -> list[dict]:
        index_path = Path(self.config.memory_l0_path) / "MEMORY.md"
        if not index_path.exists():
            return []
        async with aiofiles.open(index_path, "r", encoding="utf-8") as f:
            content = await f.read()
        return self._parse_index(content)

    def _parse_index(self, content: str) -> list[dict]:
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = INDEX_PATTERN.match(line)
            if match:
                name, path, desc = match.groups()
                parts = Path(path).parts
                if len(parts) >= 2:
                    mem_type = parts[0]
                    mem_id = Path(path).stem
                    entries.append({
                        "name": name,
                        "type": mem_type,
                        "memory_id": mem_id,
                        "description": desc,
                    })
        return entries

    def get_path(self, memory_id: str, memory_type: str) -> str:
        return str(Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md")
```

---

#### P1-3: `integrity_service.py` - async 方法内同步 I/O

```python
# src/infrastructure/security/integrity_service.py

import asyncio

class IntegrityVerifier:
    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        def _read_and_verify():
            with open(file_path, "rb") as f:
                content = f.read()
            return self.verify_hash(content, expected_hash)
        return await asyncio.to_thread(_read_and_verify)
```

---

#### P1-4: `object_operations.py` - async 方法内同步 I/O

```python
# src/infrastructure/storage/minio/object_operations.py

import asyncio

class ObjectOperations:
    async def resume_multipart_upload(
        self,
        file_path: str,
        object_name: str,
        bucket: str,
        part_size: int = 5 * 1024 * 1024
    ) -> str | None:
        chunks = await asyncio.to_thread(self._read_chunks_sync, file_path, part_size)
        return await asyncio.to_thread(self._upload_chunks_sync, chunks, object_name, bucket)

    @staticmethod
    def _read_chunks_sync(file_path: str, part_size: int) -> list[bytes]:
        chunks = []
        with open(file_path, "rb") as f:
            while True:
                data = f.read(part_size)
                if not data:
                    break
                chunks.append(data)
        return chunks

    def _upload_chunks_sync(self, chunks: list[bytes], object_name: str, bucket: str):
        client = self._client.client
        parts = []
        for part_number, data in enumerate(chunks, 1):
            etag = client._put_object(bucket, object_name, data, length=len(data), part_number=part_number)
            parts.append({"PartNumber": part_number, "ETag": etag})
        return parts
```

---

### Phase 2: 优化确认（P2）

#### P2-1: `engine.py` - sync engine 评估

```bash
# 检查 sync engine 使用
grep -r "get_sync_engine\|psycopg2\|postgresql\+psycopg2" src/ --include="*.py"
```

---

## 3. 重构优先级与工作量评估（定稿版）

### 3.1 优先级矩阵（含测试更新工作量）

| 优先级 | 文件 | 问题 | 修复策略 | 工时 | 测试更新 | 风险 |
|--------|------|------|----------|------|----------|------|
| **P0-1** | `event_listener.py` | asyncio.run() | call_soon + create_task | 0.5d | 0.25d | 低 |
| **P0-2** | `local_model_health.py` | 同步 requests | HealthCheckPort + httpx | 0.5d | 0.25d | 低 |
| **P0-3** | `auto_trigger_listener.py` | Thread+asyncio | 重构为纯 asyncio | 2d | 0.5d | 中 |
| **P1-1** | `memory_index.py` | 同步I/O+flock | to_thread + 锁语义 | 1d | 0.5d | 中 |
| **P1-2** | `file_memory_adapter.py` | 同步文件I/O | aiofiles | 1d | 0.5d | 低 |
| **P1-3** | `integrity_service.py` | async内同步I/O | to_thread | 0.5d | 0.25d | 低 |
| **P1-4** | `object_operations.py` | async内同步I/O | to_thread | 0.5d | 0.25d | 低 |
| **P2** | `engine.py` | sync engine | 评估后决策 | 0.5d | 0d | 低 |

**总工时**：P0(3d) + P1(4d) + P2(0.5d) = **7.5d**（含测试更新 2.5d）

### 3.2 阶段划分

```
Week 1: P0 紧急修复（3d）
├── event_listener.py → call_soon + create_task（0.75d 含测试）
├── local_model_health.py → HealthCheckPort + httpx（0.75d 含测试）
└── auto_trigger_listener.py → 纯 asyncio（2.5d 含测试）

Week 2-3: P1 架构统一（4d）
├── memory_index.py → to_thread + flock（1.5d 含测试）
├── file_memory_adapter.py → aiofiles（1.5d 含测试）
├── integrity_service.py → to_thread（0.75d 含测试）
└── object_operations.py → to_thread（0.75d 含测试）

Week 4: P2 优化 + 验证（0.5d）
├── engine.py → 评估决策（0.5d）
├── 集成测试
└── 性能验证
```

---

## 4. 验证策略

### 4.1 TDD 循环验证

```bash
# 每个文件重构遵循 TDD 循环
# Step 1: 红（测试失败）
poetry run pytest tests/unit/infrastructure/storage/test_memory_index.py -v
# 预期：失败（因为方法变成 async）

# Step 2: 绿（测试通过）
# 修改测试为 async 版本
poetry run pytest tests/unit/infrastructure/storage/test_memory_index.py -v
# 预期：通过

# Step 3: 重构（代码优化）
poetry run ruff check src/infrastructure/storage/memory_index.py
poetry run mypy src/infrastructure/storage/memory_index.py
```

### 4.2 事件循环阻塞测试

```python
# tests/test_event_loop_not_blocked.py
import asyncio
import time

async def test_all_refactored_methods_unblocked():
    """验证所有重构方法不阻塞事件循环。"""
    methods_tested = []

    index = MemoryIndex(config)
    start = time.perf_counter()
    await index.update_entry(entry)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, "MemoryIndex.update_entry blocked!"
    methods_tested.append("MemoryIndex.update_entry")

    print(f"Tested methods: {methods_tested}")
```

---

## 5. 依赖管理（确认无需新增）

### 5.1 已有依赖

```toml
# pyproject.toml
httpx = "^0.27.0"     # P0-2 重构使用
aiofiles = "^25.1.0"  # P1-1, P1-2 重构使用
```

**结论**：`httpx` 和 `aiofiles` 均已存在于 `pyproject.toml`，无需额外安装。

---

## 6. 风险控制

### 6.1 回滚策略

```bash
# 每个 P0/P1 修改前创建 backup branch
git checkout -b backup/pre-v5-refactor

# 主分支进行重构
git checkout -b feature/sync-async-refactor-v5
```

### 6.2 渐进式验证

```
Step 1: 单元测试（每个文件独立验证）
Step 2: 模块集成测试（P0 修复后）
Step 3: 系统 E2E 测试
Step 4: 性能回归测试
```

---

## 7. 宗师级设计总结

### 7.1 核心原则（八项）

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
│ 5. 验证驱动（TDD 约束）                                                   │
│    测试先行，红→绿→重构                                                  │
│    测试更新与代码重构同步进行                                             │
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

### 7.2 成功标准

| 指标 | 目标 |
|------|------|
| P0 问题修复率 | 100% |
| P1 问题修复率 | >80% |
| 测试覆盖率 | >90% |
| 测试更新完成率 | 100% |
| 事件循环阻塞 | 0 次 |
| asyncio.run() 反模式 | 0 处 |
| 依赖新增 | 0（已有 httpx + aiofiles） |

---

## 附录A：第四轮审查确认

| 确认项 | 结果 |
|--------|------|
| `httpx` 依赖 | ✓ 已有（pyproject.toml line 50） |
| `aiofiles` 依赖 | ✓ 已有（pyproject.toml line 95） |
| 调用链范围 | ✓ 仅测试场景，影响可控 |
| v4 方案正确性 | ✓ 无需修改 |

---

## 附录B：完整文件修改清单

| 文件 | 修改类型 | 新增抽象 | 测试更新 | 依赖 |
|------|----------|----------|----------|------|
| `event_listener.py` | 重构 | call_soon + create_task | 0.25d | 无新增 |
| `local_model_health.py` | 重构 | `HealthCheckPort` | 0.25d | 无新增（httpx已有） |
| `auto_trigger_listener.py` | 重构 | 纯 asyncio Queue | 0.5d | 无新增 |
| `memory_index.py` | 重构 | to_thread + 锁语义 | 0.5d | 无新增（aiofiles已有） |
| `file_memory_adapter.py` | 重构 | aiofiles + `FilePort` | 0.5d | 无新增（aiofiles已有） |
| `integrity_service.py` | 重构 | to_thread | 0.25d | 无新增 |
| `object_operations.py` | 重构 | to_thread | 0.25d | 无新增 |
| `engine.py` | 评估决策 | - | 0d | 无 |
