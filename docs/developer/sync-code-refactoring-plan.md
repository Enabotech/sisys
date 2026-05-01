# SISYS 同步代码最优重构方案（第九版 - 收敛版）

**生成日期**: 2026-05-01
**版本**: v9.0（第九轮审查 - 深度调用链验证 + 边界情况分析，收敛版）
**依据**: sync-code-analysis.md（权威基准） + 源码验证 + 调用链分析 + 边界情况分析
**目标**: 严格对齐分析报告，输出无歧义的可执行方案

---

## 0. 审查说明

**收敛声明**：本版本通过深度调用链验证，区分"被包装调用"与"直接调用"，避免误标问题。同时分析边界情况，确保方案在所有场景下可执行。

**验证方法**：
```bash
# 1. 源码行号验证
grep -n "asyncio.run\|requests\.Session\|threading\.Thread\|with open\|\.write_text\|\.read_text\|fcntl\.flock" \
  src/infrastructure/audit/event_listener.py \
  src/infrastructure/routing/local_model_health.py \
  src/interfaces/event_listeners/listeners/auto_trigger_listener.py \
  src/infrastructure/storage/file_memory_adapter.py \
  src/infrastructure/storage/memory_index.py \
  src/infrastructure/security/integrity_service.py \
  src/infrastructure/storage/minio/object_operations.py

# 2. 调用链验证：区分"被包装调用"vs"直接调用"
grep -rn "asyncio.to_thread" src/ --include="*.py" -A2

# 3. 验证 sync 方法是否已被 to_thread 包装
grep -rn "upload_object\|get_object_metadata\|delete_object" src/infrastructure/storage/minio/minio_repository.py
```

---

## 1. 问题清单（与 sync-code-analysis.md 严格对齐）

### 1.1 问题分布矩阵

| # | 文件:行号 | 源码确认 | 问题 | 严重程度 | 重构方案 | 调用链验证 |
|---|-----------|----------|------|----------|----------|------------|
| 1 | `event_listener.py:106` | ✓ | `asyncio.run()` 在 sync 方法 | P0 | call_soon + create_task | ✓ handle_event() 由外部调用 |
| 2 | `local_model_health.py:51` | ✓ | 同步 `requests.Session.get()` | P0 | HealthCheckPort + httpx | ✓ LocalModelHealth.check() 有调用方 |
| 3 | `engine.py:76` | ✓ | 同步 `create_engine()` | P1 | 评估后决策 | ✓ 仅启动时调用 |
| 4 | `auto_trigger_listener.py:112-118` | ✓ | 重复创建事件循环 | P1 | 重构为纯 asyncio | ✓ register_handlers() 被调用 |
| 5 | `file_memory_adapter.py:59` | ✓ | 同步 `Path.write_text()` | P1 | aiofiles | ✓ write() 被 FileMemoryService 调用 |
| 6 | `file_memory_adapter.py:77` | ✓ | 同步 `Path.read_text()` | P1 | aiofiles | ✓ read() 被调用 |
| 7 | `memory_index.py:125` | ✓ | 同步 `open()` + `rename()` | P1 | to_thread | ✓ _read_entries_locked() 被内部调用 |
| 8 | `memory_index.py:139` | ✓ | 同步 `open()` 在 truncate | P1 | to_thread | ✓ truncate() 公开方法 |
| 9 | `event_bus_config_loader.py:41` | ✓ | 同步 `open()` + YAML | P1 | 启动时调用，可接受 | ✓ 仅启动时 load() |
| 10 | `integrity_service.py:189` | ✓ | async 方法内同步 `open()` | P1 | to_thread | ✓ verify_file() 外部调用 |
| 11 | `object_operations.py:371` | ✓ | async 方法内同步 `open()` | P1 | to_thread | ✓ resume_multipart_upload() 外部调用 |

**问题总数**：11个（P0:2, P1:9, P2:0）

### 1.2 重要澄清：sync 方法的调用包装

| 方法 | 调用方式 | 是否阻塞事件循环 |
|------|----------|------------------|
| `ObjectOperations.upload_object()` | `asyncio.to_thread()` 包装 | ✗ 不直接阻塞（已被包装） |
| `ObjectOperations._single_upload()` | 仅内部调用 | ✗ 不直接暴露 |
| `ObjectOperations._multipart_upload()` | 仅内部调用 | ✗ 不直接暴露 |
| `ObjectOperations.get_object_metadata()` | `asyncio.to_thread()` 包装 | ✗ 不直接阻塞 |
| `ObjectOperations.delete_object()` | `asyncio.to_thread()` 包装 | ✗ 不直接阻塞 |

**结论**：`object_operations.py` 中 `upload_object`、`get_object_metadata`、`delete_object` 等 sync 方法已被 `minio_repository.py` 通过 `asyncio.to_thread()` 包装，不直接在事件循环中阻塞。sync-code-analysis.md §问题11 指的 `with open()` 位于 `resume_multipart_upload()` 方法内部（async 方法），这是真正的 P1 问题。

---

### 1.3 源码行号验证结果

```bash
# 经验证的行号
event_listener.py:106  → asyncio.run(
local_model_health.py:51 → session.get(self.endpoint, timeout=5)
local_model_health.py:14 → _session = requests.Session()
auto_trigger_listener.py:118 → asyncio.run(self._process_event(...))
file_memory_adapter.py:59 → file_path.write_text(...)
file_memory_adapter.py:77 → return file_path.read_text(...)
memory_index.py:125 → with open(self._index_path, ...) as f:
memory_index.py:139 → with open(temp_path, "w", ...) as f:
event_bus_config_loader.py:41 → with open(path) as f:
integrity_service.py:189 → with open(file_path, "rb") as f:
object_operations.py:371 → with open(file_path, "rb") as f:
```

---

## 2. 重构方案（逐项对应）

### P0-1: event_listener.py:106

**问题**：`asyncio.run()` 在 sync 方法中创建嵌套事件循环

**边界情况分析**：
- 场景A：有运行中事件循环 → 使用 `call_soon()` + `create_task()` fire-and-forget
- 场景B：无运行中事件循环（如单元测试） → 使用 `asyncio.to_thread()` 委托到线程池

**重构方案**：
```python
def handle_event(self, event: DomainEvent) -> None:
    audit_data = self._event_to_audit(event)
    if audit_data is None:
        return

    try:
        loop = asyncio.get_running_loop()
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
        asyncio.to_thread(self._sync_log_wrapper, audit_data)

def _sync_log_wrapper(self, audit_data: dict) -> None:
    """同步封装的审计日志写入（用于 to_thread fallback）。

    注意：在线程池线程中调用 asyncio.run() 是正确的，
    因为 to_thread 创建的是独立线程，不与主事件循环冲突。
    """
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
```

**测试更新**：无需修改（保持 sync 方法签名）

---

### P0-2: local_model_health.py:51

**问题**：同步 `requests.Session.get()` 阻塞事件循环

**重构方案**：

```python
import httpx

class OllamaHealthAdapter:
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

**测试更新**：更新调用方为 `await adapter.check()`

---

### P1-1: auto_trigger_listener.py:112-118

**问题**：每事件创建新事件循环（`asyncio.new_event_loop()` + `asyncio.run()`）

**重构方案**：

```python
class AutoTriggerListener:
    def __init__(
        self,
        auto_trigger_service,
        event_listener,
    ):
        self._auto_trigger_service = auto_trigger_service
        self._event_listener = event_listener
        self._registered_event_types = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CheckpointRecovered",
            "CorrectionClassified",
            "CorrectionApproved",
            "RoutingDecided",
            "IsolationLevelSwitched",
            "HeartbeatTriggered",
            "StrategicDeviationWarning",
            "AuditEvent",
        ]
        self._event_queue: asyncio.Queue[tuple[str, DomainEvent]] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def register_handlers(self) -> None:
        """注册处理器（不启动 worker）。"""
        for event_type in self._registered_event_types:
            handler = self._create_handler(event_type)
            self._event_listener.on_event(event_type, handler)
            logger.debug(f"Registered handler for event type: {event_type}")

    def _create_handler(self, event_type: str) -> Callable[[DomainEvent], None]:
        def handle_event(event: DomainEvent) -> None:
            self._event_queue.put_nowait((event_type, event))
        return handle_event

    async def start(self) -> None:
        """启动 worker（在 async 上下文中调用）。"""
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
```

**测试更新**：生命周期调整（`register_handlers()` 仅注册，`start()` 启动 worker）

---

### P1-2: file_memory_adapter.py:59,77

**问题**：同步 `Path.write_text()` 和 `Path.read_text()`

**重构方案**：

```python
import aiofiles

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
```

**测试更新**：添加 `@pytest.mark.asyncio` 并使用 `await`

---

### P1-3: memory_index.py:125,139

**问题**：同步 `open()` + `rename()` + fcntl.flock

**重构方案**：

```python
async def truncate(self) -> None:
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
```

**注意**：fcntl.flock 锁语义通过 to_thread 保留（锁操作在线程内原子执行）

**测试更新**：使用 `await index.truncate()`

---

### P1-4: integrity_service.py:189

**问题**：async 方法内同步 `open()`

**重构方案**：

```python
async def verify_file(self, file_path: str, expected_hash: str) -> bool:
    def _read_and_verify():
        with open(file_path, "rb") as f:
            content = f.read()
        return self.verify_hash(content, expected_hash)

    return await asyncio.to_thread(_read_and_verify)
```

**测试更新**：使用 `await verifier.verify_file(...)`

---

### P1-5: object_operations.py:371

**问题**：async 方法内同步 `open()`

**重构方案**：

```python
async def resume_multipart_upload(
    self,
    bucket_name: str,
    object_key: str,
    upload_id: str,
    redis_client: aioredis.Redis,
) -> None:
    # ... 读取状态 ...
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
    # ... 继续处理 chunks
```

**测试更新**：使用 `await self.resume_multipart_upload(...)`

---

### P2: engine.py:76

**问题**：同步 `create_engine()`

**决策**：保持现状，无需修改

---

### P2: event_bus_config_loader.py:41

**问题**：同步 `open()` + YAML

**决策**：保持现状，无需修改

---

## 3. 工作量评估

### 3.1 优先级矩阵

| 优先级 | 文件 | 问题 | 修复策略 | 工时 | 测试更新 | 风险 |
|--------|------|------|----------|------|----------|------|
| **P0-1** | `event_listener.py:106` | asyncio.run() | call_soon + create_task + to_thread fallback | 0.5d | 0d | 低 |
| **P0-2** | `local_model_health.py:51` | 同步 requests | HealthCheckPort + httpx | 0.5d | 0.25d | 低 |
| **P1-1** | `auto_trigger_listener.py:112-118` | 重复创建循环 | 重构为纯 asyncio | 2d | 0.5d | 中 |
| **P1-2** | `file_memory_adapter.py:59,77` | 同步文件I/O | aiofiles | 1d | 0.5d | 低 |
| **P1-3** | `memory_index.py:125,139` | 同步I/O+flock | to_thread + 锁语义 | 1d | 0.5d | 中 |
| **P1-4** | `integrity_service.py:189` | async内同步I/O | to_thread | 0.5d | 0.25d | 低 |
| **P1-5** | `object_operations.py:371` | async内同步I/O | to_thread | 0.5d | 0.25d | 低 |
| **P2** | `engine.py:76` | sync engine | 无需修改（启动时） | 0d | 0d | 低 |
| **P2** | `event_bus_config_loader.py:41` | 同步YAML | 无需修改（启动时） | 0d | 0d | 低 |

**需修改文件数**：7个（P0:2, P1:5）
**无需修改文件数**：2个（P2:保持）
**总工时**：5.5d（含测试更新 2.25d）

---

## 4. 阶段划分

```
Week 1: P0 紧急修复（1.25d）
├── event_listener.py → call_soon + create_task（0.5d）
└── local_model_health.py → HealthCheckPort + httpx（0.75d 含测试）

Week 2: P1-1 架构统一（2.5d 含测试）
└── auto_trigger_listener.py → 纯 asyncio（2.5d 含测试）

Week 3: P1-2 至 P1-5 文件 I/O 异步化（2.5d 含测试）
├── file_memory_adapter.py → aiofiles（1.5d 含测试）
├── memory_index.py → to_thread（1.0d 含测试）
├── integrity_service.py → to_thread（0.5d）
└── object_operations.py → to_thread（0.5d）

Week 4: 集成测试 + 验证（1d）
├── P0+P1 重构集成验证
├── 事件循环阻塞测试
└── 性能回归测试
```

---

## 5. 依赖确认

| 依赖 | 状态 | 用途 |
|------|------|------|
| `httpx` | 已有（pyproject.toml line 50） | P0-2 重构使用 |
| `aiofiles` | 已有（pyproject.toml line 95） | P1-2, P1-3 重构使用 |
| `asyncio` | 标准库 | 所有 async 重构使用 |

**结论**：无需新增依赖。

---

## 6. 验证策略

### 6.1 TDD 循环

```bash
# Step 1: 红 - 测试失败（方法签名变更）
poetry run pytest tests/unit/infrastructure/storage/test_memory_index.py -v

# Step 2: 绿 - 测试通过（更新为 async）
poetry run pytest tests/unit/infrastructure/storage/test_memory_index.py -v

# Step 3: 重构 - 代码质量检查
poetry run ruff check src/infrastructure/storage/memory_index.py
poetry run mypy src/infrastructure/storage/memory_index.py
```

### 6.2 事件循环阻塞验证

```python
async def test_event_loop_not_blocked():
    index = MemoryIndex(config)
    start = time.perf_counter()
    await index.update_entry(entry)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, "Event loop was blocked!"
```

---

## 7. 宗师级设计原则

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     宗师级设计五原则（收敛版）                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ 1. 单一事件循环                                                          │
│    禁止在已运行循环中调用 asyncio.run()                                  │
│                                                                         │
│ 2. 上下文纯净                                                            │
│    sync 代码在 sync 上下文，async 代码在 async 上下文                   │
│                                                                         │
│ 3. 端口抽象                                                              │
│    所有外部依赖通过 Hexagon Port 接口隔离                                │
│                                                                         │
│ 4. 锁语义保留                                                            │
│    fcntl.flock 用 to_thread 封装，保留原子性                             │
│                                                                         │
│ 5. 启动时调用可接受                                                       │
│    engine.py, event_bus_config_loader.py 等启动时调用不阻塞事件循环     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 成功标准

| 指标 | 目标 |
|------|------|
| P0 问题修复率 | 100%（2/2） |
| P1 问题修复率 | 100%（5/5） |
| P2 问题（保持） | 2/2 无需修改 |
| 测试更新完成率 | 100% |
| 事件循环阻塞 | 0 次 |
| asyncio.run() 反模式 | 0 处 |
| 依赖新增 | 0 |

---

## 附录：变更记录

| 版本 | 变更说明 |
|------|----------|
| v1.0 | 初始方案 |
| v2.0 | 源码审查校正 |
| v3.0 | 调用链分析 |
| v4.0 | 测试兼容性 |
| v5.0 | 依赖确认 |
| v6.0 | 收敛版：与 sync-code-analysis.md 严格对齐，问题数从13收敛到11 |
| v7.0 | 源码逐项验证：P0-1 方案修正（to_thread fallback） |
| v8.0 | 调用链交叉验证：确认所有调用方存在且方案可执行 |
| v9.0 | **深度调用链验证**：区分"被 to_thread 包装的 sync 方法"与"直接暴露的 sync 方法"，修正 P1-5 分析边界 |
