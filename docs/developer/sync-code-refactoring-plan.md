# SISYS 同步代码最优重构方案

**生成日期**: 2026-05-01
**依据**: sync-code-analysis.md + sisys-sync-architecture.md + sync-code-design-mastery.md
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

---

## 1. 当前问题全景

### 1.1 问题分布矩阵

| 层级 | P0（阻塞循环） | P1（性能风险） | P2（可接受） |
|------|---------------|---------------|-------------|
| Infrastructure | 2 | 5 | 4 |
| Interfaces | 0 | 1 | 1 |
| **总计** | **2** | **6** | **5** |

### 1.2 问题根因分类

```
┌─────────────────────────────────────────────────────────────┐
│                   问题根因分类                              │
├─────────────────────────────────────────────────────────────┤
│ Type-A: 上下文错配                                          │
│   ├── event_listener.py: asyncio.run() 在 sync 方法         │
│   └── local_model_health.py: requests.Session 同步调用     │
│                                                             │
│ Type-B: 混合架构                                            │
│   └── auto_trigger_listener.py: Thread + asyncio.run()     │
│                                                             │
│ Type-C: 同步 I/O                                            │
│   ├── file_memory_adapter.py: Path.write_text/read_text     │
│   ├── memory_index.py: open() + rename()                    │
│   ├── integrity_service.py: open() in async 方法            │
│   └── object_operations.py: open() in async 方法            │
│                                                             │
│ Type-D: 配置加载（启动时一次性，可接受）                       │
│   └── event_bus_config_loader.py                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 分阶段重构路径

### Phase 0: 紧急修复（P0 - 必须立即修复）

#### P0-1: `event_listener.py` - 消除 asyncio.run() 反模式

**当前问题**:
```python
def handle_event(self, event: DomainEvent) -> None:
    asyncio.run(self._audit_service.log(...))  # 创建新循环，阻塞主循环
```

**重构方案**:
```python
# src/infrastructure/audit/event_listener.py

import asyncio
from typing import Any

class AuditEventListener:
    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    def handle_event(self, event: DomainEvent) -> None:
        """同步入口 - 委托到线程池，不阻塞事件循环。"""
        audit_data = self._extract_audit_data(event)
        asyncio.to_thread(
            self._run_sync_log,
            audit_data["actor"],
            audit_data["action_type"],
            audit_data["resource"]
        )

    async def handle_event_async(self, event: DomainEvent) -> None:
        """异步入口 - 在 asyncio 上下文中直接 await。"""
        audit_data = self._extract_audit_data(event)
        await self._audit_service.log(
            actor=audit_data["actor"],
            action_type=audit_data["action_type"],
            resource=audit_data["resource"]
        )

    def _run_sync_log(
        self,
        actor: str,
        action_type: str,
        resource: dict[str, Any]
    ) -> None:
        """在线程中执行的同步日志方法。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self._audit_service.log(
                    actor=actor,
                    action_type=action_type,
                    resource=resource
                )
            )
        finally:
            loop.close()
```

**或者更简洁的方案 - 如果 AuditService 支持同步调用**:
```python
def handle_event(self, event: DomainEvent) -> None:
    audit_data = self._extract_audit_data(event)
    # 直接调用同步方法，不创建新事件循环
    self._audit_service.log_sync(
        actor=audit_data["actor"],
        action_type=audit_data["action_type"],
        resource=audit_data["resource"]
    )
```

**验证方式**:
```bash
# 启动事件循环，调用 handle_event，确保不阻塞
pytest tests/infrastructure/audit/test_event_listener.py -v
```

---

#### P0-2: `local_model_health.py` - 同步 HTTP 改异步

**当前问题**:
```python
import requests  # 同步库

def check(self) -> bool:
    response = session.get(self.endpoint, timeout=5)  # 阻塞！
```

**重构方案**:
```python
# src/infrastructure/routing/local_model_health.py

import httpx
from abc import ABC, abstractmethod
from typing import Protocol

class HealthCheckPort(Protocol):
    """健康检查端口抽象 - 六边形架构接口层"""
    async def check(self) -> bool: ...

class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 模型服务健康检查适配器"""
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

**调用方修改**:
```python
# 原来
health = LocalModelHealth()
is_healthy = health.check()  # 同步调用

# 重构后
health = OllamaHealthAdapter()
is_healthy = await health.check()  # 异步调用
```

**验证方式**:
```bash
poetry run python -c "
import asyncio
from src.infrastructure.routing.local_model_health import OllamaHealthAdapter

async def test():
    adapter = OllamaHealthAdapter()
    result = await adapter.check()
    print(f'Ollama health: {result}')
    await adapter.close()

asyncio.run(test())
"
```

---

### Phase 1: 架构统一（P1 - 高优先级）

#### P1-1: `auto_trigger_listener.py` - 消除 Thread + asyncio.run()

**重构愿景**：从混合架构到纯 asyncio

**当前问题**:
```python
class AutoTriggerListener:
    def start(self):
        self._worker_thread = threading.Thread(target=self._worker_loop)
        self._worker_thread.start()  # 创建线程

    def _worker_loop(self):
        loop = asyncio.new_event_loop()  # 每事件创建新循环
        while self._running:
            event = self._event_queue.get()
            asyncio.run(self._process_event(...))  # 反模式
```

**重构方案**:

```python
# src/interfaces/event_listeners/listeners/auto_trigger_listener.py

import asyncio
from typing import Callable, Awaitable

class AutoTriggerListener:
    """自动触发监听器 - 纯 asyncio 实现"""
    def __init__(
        self,
        process_callback: Callable[[str, Any], Awaitable[None]]
    ):
        self._process_callback = process_callback
        self._event_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动监听器 - 在 asyncio 上下文中调用"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """停止监听器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def enqueue(self, event_type: str, event: Any) -> None:
        """入队方法 - 可从同步上下文调用"""
        self._event_queue.put_nowait((event_type, event))

    async def _worker_loop(self) -> None:
        """工作循环 - 纯 asyncio"""
        while self._running:
            try:
                event_type, event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process_callback(event_type, event)
            except Exception as ex:
                # 错误处理日志
                print(f"Error processing event {event_type}: {ex}")

    async def _process_callback(
        self,
        event_type: str,
        event: Any
    ) -> None:
        """实际的回调处理 - 委托给外部提供的回调"""
        await self._process_callback(event_type, event)
```

**集成方式修改**:
```python
# 原来
listener = AutoTriggerListener()
listener.start()  # 同步启动

# 重构后
listener = AutoTriggerListener(process_callback=my_handler)
await listener.start()  # 异步启动
```

---

#### P1-2: `file_memory_adapter.py` - 文件 I/O 异步化

**当前问题**:
```python
def write(self, memory_id: str, memory_type: str, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")  # 同步阻塞

def read(self, memory_id: str, memory_type: str) -> str | None:
    return file_path.read_text(encoding="utf-8")  # 同步阻塞
```

**重构方案**:

```python
# src/infrastructure/storage/file_memory_adapter.py

import aiofiles
from pathlib import Path
from src.interfaces.ports.file_port import FilePort  # 新增抽象

class FileMemoryAdapter:
    """L0 文件存储适配器 - 支持异步操作"""
    def __init__(self, config: MemoryConfig):
        self._config = config

    def _get_file_path(self, memory_id: str, memory_type: str) -> Path:
        dir_path = Path(self.config.memory_l0_path) / memory_type
        return dir_path / f"{memory_id}.md"

    async def write(
        self,
        memory_id: str,
        memory_type: str,
        content: str
    ) -> None:
        file_path = self._get_file_path(memory_id, memory_type)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def read(
        self,
        memory_id: str,
        memory_type: str
    ) -> str | None:
        file_path = self._get_file_path(memory_id, memory_type)
        if not file_path.exists():
            return None
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            return await f.read()

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        return self._get_file_path(memory_id, memory_type).exists()

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        file_path = self._get_file_path(memory_id, memory_type)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
```

**调用方修改示例**:
```python
# 原来
adapter = FileMemoryAdapter(config)
adapter.write(memory_id, memory_type, content)  # 同步

# 重构后
await adapter.write(memory_id, memory_type, content)  # 异步
```

---

#### P1-3: `memory_index.py` - 索引操作异步化

**重构方案**:

```python
# src/infrastructure/storage/memory_index.py

import aiofiles
import asyncio
from pathlib import Path

class MemoryIndex:
    """记忆索引 - 使用 asyncio.to_thread() 封装同步 I/O"""
    def __init__(self, index_path: str, lock_path: str):
        self._index_path = Path(index_path)
        self._lock_path = Path(lock_path)

    async def truncate(self) -> None:
        """清空索引 - 使用线程池避免阻塞"""
        def _truncate():
            with open(self._index_path, encoding="utf-8") as f:
                lines = f.readlines()

            temp_path = self._index_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                # 保留标题行
                for line in lines:
                    if line.startswith("#"):
                        f.write(line)
                f.flush()
                temp_path.rename(self._index_path)

        await asyncio.to_thread(_truncate)

    async def get_all_entries(self) -> list[dict]:
        """获取所有索引条目"""
        def _read():
            with open(self._index_path, encoding="utf-8") as f:
                return self._parse_entries(f.read())

        return await asyncio.to_thread(_read)

    def _parse_entries(self, content: str) -> list[dict]:
        """解析索引内容"""
        entries = []
        # ... 解析逻辑
        return entries
```

---

#### P1-4: `integrity_service.py` - 文件验证异步化

**重构方案**:

```python
# src/infrastructure/security/integrity_service.py

import asyncio

class IntegrityService:
    """完整性服务 - async 方法中使用 to_thread"""
    async def verify_file(
        self,
        file_path: str,
        expected_hash: str
    ) -> bool:
        def _read_and_verify():
            with open(file_path, "rb") as f:
                content = f.read()
            return self.verify_hash(content, expected_hash)

        return await asyncio.to_thread(_read_and_verify)

    async def compute_hash(self, file_path: str) -> str:
        def _compute():
            hash_obj = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()

        return await asyncio.to_thread(_compute)
```

---

#### P1-5: `object_operations.py` - MinIO 上传异步化

**重构方案**:

```python
# src/infrastructure/storage/minio/object_operations.py

import asyncio

class ObjectOperations:
    """MinIO 对象操作 - async 方法中使用 to_thread"""
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

        chunks = await asyncio.to_thread(_read_chunks)

        # 后续 MinIO 操作如果支持 async，直接 await
        # 否则继续使用 to_thread
        return await self._upload_chunks_async(chunks, object_name, bucket)
```

---

### Phase 2: 优化确认（P1 - 可选优化）

#### P2-1: `engine.py` - 删除 sync engine

**评估标准**：
- 如果系统中没有 sync 数据库访问需求 → 删除
- 如果有遗留代码需要 sync 访问 → 保留但隔离

```python
# 评估命令
grep -r "get_sync_engine\|psycopg2" src/ --include="*.py"
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
```

---

## 4. 重构优先级与工作量评估

### 4.1 优先级矩阵

| 优先级 | 文件 | 问题 | 修复策略 | 工时 | 风险 |
|--------|------|------|----------|------|------|
| **P0** | `event_listener.py` | asyncio.run() | to_thread / 双接口 | 0.5d | 低 |
| **P0** | `local_model_health.py` | 同步 requests | HealthCheckPort + httpx | 0.5d | 低 |
| **P1** | `auto_trigger_listener.py` | Thread+asyncio | 重构为纯 asyncio | 2d | 中 |
| **P1** | `file_memory_adapter.py` | 同步文件I/O | aiofiles | 1d | 低 |
| **P1** | `memory_index.py` | 同步文件I/O | to_thread | 0.5d | 低 |
| **P1** | `integrity_service.py` | async内同步I/O | to_thread | 0.5d | 低 |
| **P1** | `object_operations.py` | async内同步I/O | to_thread | 0.5d | 低 |
| **P2** | `engine.py` | sync engine | 评估后删除 | 0.5d | 低 |
| **P2** | `event_bus_config_loader.py` | 启动时调用 | 确认后可保留 | - | - |

### 4.2 阶段划分

```
Week 1: P0 紧急修复
├── event_listener.py → 双接口 + to_thread
└── local_model_health.py → HealthCheckPort + httpx

Week 2-3: P1 架构统一
├── auto_trigger_listener.py → 纯 asyncio（重点）
├── file_memory_adapter.py → aiofiles
├── memory_index.py → to_thread
├── integrity_service.py → to_thread
└── object_operations.py → to_thread

Week 4: P2 优化 + 验证
├── engine.py → 评估删除
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

### 5.2 集成测试验证

```bash
# 事件循环不阻塞测试
poetry run pytest tests/integration/ -v -k "async"
```

### 5.3 性能基准测试

```python
# 基准测试脚本
import asyncio
import time

async def benchmark_sync_vs_async():
    # 同步版本基准
    start = time.perf_counter()
    for _ in range(1000):
        with open("test.txt", "w") as f:
            f.write("test")
    sync_time = time.perf_counter() - start

    # 异步版本
    start = time.perf_counter()
    for _ in range(1000):
        async with aiofiles.open("test.txt", "w") as f:
            await f.write("test")
    async_time = time.perf_counter() - start

    print(f"Sync: {sync_time:.3f}s, Async: {async_time:.3f}s")
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
1. 备份原文件
2. 创建 git branch
3. 编写失败的测试用例
4. 重构
5. 验证测试通过

```bash
git branch backup/sync-refactor
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
┌─────────────────────────────────────────────────────────────────────┐
│                     宗师级设计的五个原则                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ 1. 单一事件循环                                                      │
│    一个进程只应有一个 asyncio 事件循环                                │
│    禁止在已运行循环中调用 asyncio.run()                               │
│                                                                     │
│ 2. 上下文纯净                                                        │
│    sync 代码在 sync 上下文，async 代码在 async 上下文                 │
│    不混用，不搭桥                                                     │
│                                                                     │
│ 3. 端口抽象                                                          │
│    所有外部依赖通过 Hexagon Port 接口隔离                            │
│    Infrastructure 层实现，Interfaces 层引用                          │
│                                                                     │
│ 4. 渐进式改造                                                        │
│    优先修复阻塞主循环的 P0 问题                                       │
│    不追求一次性完成                                                   │
│                                                                     │
│ 5. 验证驱动                                                          │
│    测试先行，红→绿→重构                                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
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

## 附录：完整文件修改清单

| 文件 | 修改类型 | 新增抽象 |
|------|----------|----------|
| `event_listener.py` | 重构 | 双接口（handle_event + handle_event_async） |
| `local_model_health.py` | 重构 | `HealthCheckPort` |
| `auto_trigger_listener.py` | 重构 | 纯 asyncio `asyncio.Queue` |
| `file_memory_adapter.py` | 重构 | `FilePort` + `AioFilesAdapter` |
| `memory_index.py` | 重构 | `asyncio.to_thread()` |
| `integrity_service.py` | 重构 | `asyncio.to_thread()` |
| `object_operations.py` | 重构 | `asyncio.to_thread()` |
| `engine.py` | 评估删除 | - |
| `event_bus_config_loader.py` | 保持（启动时） | - |
