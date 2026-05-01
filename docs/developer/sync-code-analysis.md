# SISYS 同步代码分析报告

**生成日期**: 2026-05-01
**分析范围**: `src/` 目录下所有 Python 文件
**目的**: 识别阻塞事件循环的同步代码，提出异步化改造建议

---

## 执行摘要

| 严重程度 | 问题类型 | 文件数量 |
|----------|----------|----------|
| **P0** | 关键阻塞（请求路径中禁止） | 2 |
| **P1** | 高风险（初始化/配置） | 9 |
| **P2** | 中风险（进程内锁，可接受） | 5 |

---

## P0 - 关键阻塞（请求路径中禁止）

### 1. `asyncio.run()` 在事件处理器中

**文件**: `src/infrastructure/audit/event_listener.py:106`

```python
def handle_event(self, event: DomainEvent) -> None:
    # ...
    asyncio.run(
        self._audit_service.log(
            actor=audit_data["actor"],
            action_type=audit_data["action_type"],
            ...
        )
    )
```

**问题**: `asyncio.run()` 创建新事件循环并阻塞。如果在 async 上下文中被调用会崩溃。

**修复方案**:
```python
# 方案 A: 使用 handle_event_async() 替代
async def handle_event_async(self, event: DomainEvent) -> None:
    audit_data = self._extract_audit_data(event)
    await self._audit_service.log(...)

# 方案 B: 使用 asyncio.to_thread() 委托到线程池
def handle_event(self, event: DomainEvent) -> None:
    audit_data = self._extract_audit_data(event)
    asyncio.to_thread(
        self._audit_service.log,
        actor=audit_data["actor"],
        ...
    )
```

---

### 2. 同步 HTTP 调用 - requests.Session

**文件**: `src/infrastructure/routing/local_model_health.py:43-52`

```python
class LocalModelHealth:
    def check(self) -> bool:
        try:
            session = _get_session()
            response = session.get(self.endpoint, timeout=5)  # 阻塞！
            return response.status_code == 200
        except Exception:
            return False
```

**问题**: 同步 `requests.Session.get()` 阻塞事件循环。

**修复方案**:
```python
import httpx

class LocalModelHealth:
    _client: httpx.AsyncClient | None = None

    @classmethod
    async def check(cls) -> bool:
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=5.0)
        try:
            response = await cls._client.get(cls._endpoint)
            return response.status_code == 200
        except Exception:
            return False
```

---

## P1 - 高风险（启动时可接受，请求路径中禁止）

### 3. 同步数据库引擎

**文件**: `src/infrastructure/storage/postgresql/engine.py:67-84`

```python
def get_sync_engine(self) -> Engine:
    if self._sync_engine is None:
        from sqlalchemy import create_engine
        self._sync_engine = create_engine(
            self._build_sync_url(),  # postgresql+psycopg2://...
            ...
        )
    return self._sync_engine
```

**说明**: psycopg2 sync 引擎。仅在启动时调用则可接受。

**修复方案**: 删除（如果不需要 sync 访问）或使用 `run_in_executor()`

---

### 4. 后台线程创建新事件循环

**文件**: `src/interfaces/event_listeners/listeners/auto_trigger_listener.py:110-124`

```python
def _worker_loop(self) -> None:
    loop = asyncio.new_event_loop()      # 每事件创建新循环
    asyncio.set_event_loop(loop)
    try:
        while self._running:
            ...
            asyncio.run(self._process_event(event_type, event))  # 反模式
    finally:
        loop.close()
```

**问题**: 每事件创建新事件循环，开销巨大。

**修复方案**: 重构为纯 asyncio
```python
async def _worker_loop(self) -> None:
    while self._running:
        try:
            event = await asyncio.wait_for(
                self._event_queue.get(),
                timeout=1.0
            )
            await self._process_event(event_type, event)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
```

---

### 5. 同步文件写入 - FileMemoryAdapter

**文件**: `src/infrastructure/storage/file_memory_adapter.py:44-59`

```python
def write(self, memory_id: str, memory_type: str, content: str) -> None:
    dir_path = Path(self.config.memory_l0_path) / memory_type
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{memory_id}.md"
    file_path.write_text(content, encoding="utf-8")  # 同步阻塞
```

**修复方案**:
```python
import aiofiles

async def write(self, memory_id: str, memory_type: str, content: str) -> None:
    dir_path = Path(self.config.memory_l0_path) / memory_type
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{memory_id}.md"
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)
```

---

### 6. 同步文件操作 - MemoryIndex

**文件**: `src/infrastructure/storage/memory_index.py:125-141`

```python
def truncate(self) -> None:
    with open(self._index_path, encoding="utf-8") as f:  # 同步读
        lines = f.readlines()
    ...
    temp_path.rename(self._index_path)  # 同步 rename
```

**修复方案**:
```python
async def truncate(self) -> None:
    def _truncate():
        with open(self._index_path, encoding="utf-8") as f:
            lines = f.readlines()
        # ... 处理逻辑
        temp_path.rename(self._index_path)

    await asyncio.to_thread(_truncate)
```

---

### 7. 同步 YAML 加载 - EventBusConfigLoader

**文件**: `src/infrastructure/messaging/event_bus_config_loader.py:37-42`

```python
def load(self, router: ChannelRouter, config_path: str | Path) -> None:
    path = Path(config_path)
    if not path.exists():
        return
    with open(path) as f:  # 同步 I/O
        config: dict[str, Any] = yaml.safe_load(f) or {}
```

**说明**: 配置加载通常在启动时执行一次，可接受。

---

### 8. 同步文件验证 - IntegrityService

**文件**: `src/infrastructure/security/integrity_service.py:177-191`

```python
async def verify_file(self, file_path: str, expected_hash: str) -> bool:
    with open(file_path, "rb") as f:  # 同步阻塞！
        content = f.read()
    return self.verify_hash(content, expected_hash)
```

**修复方案**:
```python
async def verify_file(self, file_path: str, expected_hash: str) -> bool:
    def _read_and_verify():
        with open(file_path, "rb") as f:
            content = f.read()
        return self.verify_hash(content, expected_hash)

    return await asyncio.to_thread(_read_and_verify)
```

---

### 9. MinIO 同步文件读取

**文件**: `src/infrastructure/storage/minio/object_operations.py:371-375`

```python
async def resume_multipart_upload(...):
    ...
    with open(file_path, "rb") as f:  # 同步！
        while True:
            data = f.read(part_size)
            if not data:
                break
            ...
```

**修复方案**:
```python
async def resume_multipart_upload(...):
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
    ...
```

---

## P2 - 中风险（进程内锁，可接受但需记录）

### 10-14. threading.Lock 用于线程安全

| 文件 | 锁类型 | 用途 |
|------|--------|------|
| `src/infrastructure/messaging/event_bus.py:37` | `threading.RLock` | 事件总线线程安全 |
| `src/infrastructure/monitoring/otel_config.py:163` | `threading.Lock` | OTel 初始化锁 |
| `src/interfaces/api/monitoring.py:76` | `threading.Lock` | metrics 路由初始化 |
| `src/infrastructure/monitoring/business_metrics.py:97` | `threading.Lock` | 业务指标更新 |
| `src/infrastructure/config/sovereignty.py:179` | `threading.Lock` | 配置懒加载 |

**评估**: 用于初始化和指标收集，不在请求关键路径上，可接受。

---

## 正面示例（无需修改）

| 文件 | 正确实现 |
|------|----------|
| `rabbitmq_listener.py` | `import aio_pika` ✓ |
| `rabbitmq_publisher.py` | `import aio_pika` ✓ |
| `rabbitmq_consumer.py` | `import aio_pika` ✓ |
| `outbox_processor.py` | `import aio_pika` ✓ |
| `postgresql/engine.py` (async) | 使用 `asyncpg` ✓ |
| `heartbeat_scheduler.py` | 纯 asyncio ✓ |
| `redis_publisher.py` | `redis.asyncio` ✓ |
| `redis_subscriber.py` | `redis.asyncio` ✓ |
| `semantic_cache.py` | `redis.asyncio` ✓ |
| `public_blackboard.py` | `redis.asyncio` ✓ |
| `session_storage.py` | `redis.asyncio` ✓ |
| `redis_retry_queue.py` | `redis.asyncio` ✓ |
| `idempotency_checker.py` | `redis.asyncio` ✓ |

---

## 完整问题清单

| # | 文件:行号 | 问题 | 严重程度 |
|---|-----------|------|----------|
| 1 | `event_listener.py:106` | `asyncio.run()` 在 sync 方法 | P0 |
| 2 | `local_model_health.py:51` | 同步 `requests.Session.get()` | P0 |
| 3 | `engine.py:76` | 同步 `create_engine()` | P1 |
| 4 | `auto_trigger_listener.py:112-118` | 重复创建事件循环 | P1 |
| 5 | `file_memory_adapter.py:59` | 同步 `Path.write_text()` | P1 |
| 6 | `file_memory_adapter.py:77` | 同步 `Path.read_text()` | P1 |
| 7 | `memory_index.py:125` | 同步 `open()` + `rename()` | P1 |
| 8 | `memory_index.py:139` | 同步 `open()` 在 truncate | P1 |
| 9 | `event_bus_config_loader.py:41` | 同步 `open()` + YAML | P1 |
| 10 | `integrity_service.py:189` | async 方法内同步 `open()` | P1 |
| 11 | `object_operations.py:371` | async 方法内同步 `open()` | P1 |

---

## 建议修改优先级

### 第一优先级（必须修复）

1. **`local_model_health.py`** - 改用 `httpx.AsyncClient`
2. **`event_listener.py`** - 使用 `handle_event_async()` 或 `asyncio.to_thread()`

### 第二优先级（建议修复）

3. **`auto_trigger_listener.py`** - 重构为纯 asyncio
4. **`file_memory_adapter.py`** - 使用 `aiofiles`
5. **`memory_index.py`** - 使用 `asyncio.to_thread()`
6. **`integrity_service.py`** - 使用 `asyncio.to_thread()`
7. **`object_operations.py`** - 使用 `asyncio.to_thread()`

### 第三优先级（可选）

8. **`engine.py`** - 删除 `get_sync_engine()`（如不需要）
9. **`event_bus_config_loader.py`** - 确认仅启动时调用

---

## 附录：依赖检查

```bash
# 检查是否已安装 aiofiles
poetry show aiofiles

# 如未安装，添加依赖
poetry add aiofiles
```

**注意**: `httpx` 已在 `pyproject.toml` 依赖中，无需额外安装

---

## 相关文档

- [SISYS Sync Architecture](sisys-sync-architecture.md)
- [SISYS 同步代码问题宗师级设计分析](sync-code-design-mastery.md)
- [Sync Code Optimization Design](sync-code-optimization-design.md)
