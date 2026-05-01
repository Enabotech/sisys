# SISYS 同步代码重构方案B（Port+Adapter 宗师级重构 - v1.5）

**生成日期**: 2026-05-01
**版本**: v1.5（第五轮审查修正版）
**依据**: sync-code-analysis.md + sisys-sync-architecture.md + 源码调研 + 端口抽象最佳实践 + 五轮审查反馈
**目标**: 通过端口抽象实现完全六边形架构合规，消除 sync/async 混用

---

## 0. 架构现状分析

### 0.1 六层存储架构调用链

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Application Layer                                     │
│              SixLayerStorageCoordinator (六层存储协同)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│  Domain Layer  │         │  Domain Layer │         │  Domain Layer │
│ MemoryService │         │    (Ports)    │         │   (Events)    │
└───────────────┘         └───────────────┘         └───────────────┘
        │                       ▲                       │
        │                       │                       │
        ▼                       │                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                                     │
│                                                                             │
│  L0: FileMemoryAdapter ────→ [缺失 Port] ────→ .md 文件 CRUD              │
│  L1: RedisMemoryCache ────→ [缺失 Port] ────→ Redis 缓存                  │
│  L2: PostgreSQL ─────────→ MemoryMetadataRepositoryProtocol ✓            │
│  L3: QdrantVector ───────→ VectorStorage Protocol ✓                       │
│  L4: MinIO ──────────────→ ObjectStorageRepository ✓                      │
│  L5: Neo4jGraph ──────────→ GraphStorage Protocol ✓                        │
│                                                                             │
│  IntegrityService ───────→ [缺失 Port] ────→ 文件哈希验证                  │
│  AuditEventListener ─────→ [缺失 Port] ────→ 审计事件记录                  │
│  LocalModelHealth ───────→ [缺失 Port] ────→ Ollama 健康检查              │
│  AutoTriggerListener ────→ [缺失 Port] ────→ 自动触发监听                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 0.2 现有 Port 接口覆盖

| 类别 | 数量 | 覆盖情况 |
|------|------|----------|
| Repository Ports | 10 | L2 Metadata/History, Vector, Graph, Object Storage, Session Storage ✓ |
| Domain Service Ports | 9 | Auth, Audit, Permission, Semantic Cache ✓ |
| **本次方案缺失 Port** | **4** | L0Storage, L1Cache, IndexManager, PathResolver |

**注**：
1. 方案B v1.0 原计划新增 `ObjectOperationsPort`，经审查发现与现有 `ObjectStorageRepository` 职责重叠，已移除。`ObjectOperations` 的 sync I/O 问题通过直接改造实现类解决。
2. **L1CachePort** 属于可选优化（当前 `RedisMemoryCache` 已被 `SixLayerStorageCoordinator` 内部使用，不直接暴露给 Domain 层），本次方案不包含。如需 Domain 层完全解耦，可后续扩展。
3. 本文档中所有"改造后"代码描述的是**目标状态**（async 方法），而非当前源码状态（sync 方法）。

---

## 1. 问题清单与 Port 抽象映射

### 1.1 问题 → Port 映射矩阵

| 问题编号 | 文件:行号 | 问题描述 | 需要创建的 Port | 抽象级别 | 审查修正 |
|----------|-----------|----------|-----------------|----------|----------|
| P0-1 | `event_listener.py:106` | `asyncio.run()` 在 sync 方法 | `AuditService` 已存在 | 修复调用方式 | 无需修改 |
| P0-2 | `local_model_health.py:51` | 同步 `requests.Session` | `HealthCheckPort` | 新增 | 无需修改 |
| P1-1 | `auto_trigger_listener.py:112-118` | 重复创建事件循环 | `EventSubscriberPort` | 已有/重构 | 无需修改 |
| P1-2 | `file_memory_adapter.py:59,77` | 同步 `Path.write/read_text` | `L0StoragePort` | 新增 | 无需修改 |
| P1-3 | `memory_index.py:125,139` | 同步 `open()` + `rename()` | `IndexManagerPort` | 新增 | 无需修改 |
| P1-4 | `integrity_service.py:189` | async 内同步 `open()` | `IntegrityPort` | 新增 | **修正** |
| P1-5 | `object_operations.py:371` | async 内同步 `open()` | **无需新 Port** | 直接改造 | **移除 Port** |
| P2 | `engine.py:76` | 同步 `create_engine()` | 无 | 保持现状 | 无需修改 |
| P2 | `event_bus_config_loader.py:41` | 同步 `open()` + YAML | 无 | 保持现状 | 无需修改 |

**审查修正说明**：
- P1-4 `IntegrityPort`：将 `compute_hash`/`verify_hash` 保留为 sync 方法（CPU 密集型，不阻塞事件循环），仅将 `verify_file` 定义为 async
- P1-5：`ObjectOperationsPort` 与 `ObjectStorageRepository` 职责重叠，移除新 Port，直接改造 `ObjectOperations`

---

## 2. 新增 Port 接口定义（修正版）

### 2.1 HealthCheckPort

**文件**: `src/domain/repositories/health_check.py`

```python
"""HealthCheckPort — 健康检查抽象端口。"""

from abc import ABC, abstractmethod

class HealthCheckPort(ABC):
    """健康检查抽象端口。

    用于检查外部服务（Ollama、Redis 等）的可用性。
    所有健康检查实现必须实现此端口。
    """

    @abstractmethod
    async def check(self) -> bool:
        """检查服务是否可用。

        Returns:
            True 如果服务健康，False 否则。
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭健康检查连接，释放资源。"""
        pass
```

### 2.2 L0StoragePort

**文件**: `src/domain/repositories/l0_storage.py`

```python
"""L0StoragePort — L0 文件系统存储抽象端口。"""

from abc import ABC, abstractmethod

class L0StoragePort(ABC):
    """L0 文件系统存储抽象端口。

    负责 ~/.sisys/memory/*.md 文件的异步读写操作。
    所有 L0 存储实现必须实现此端口。
    """

    @abstractmethod
    async def write(self, memory_id: str, memory_type: str, content: str) -> None:
        """写入记忆文件（I/O 密集型）。

        Args:
            memory_id: 记忆 ID（UUID）
            memory_type: 记忆类型（user/feedback/project/reference）
            content: 记忆内容

        Raises:
            OSError: 如果写入失败
        """
        pass

    @abstractmethod
    async def read(self, memory_id: str, memory_type: str) -> str:
        """读取记忆文件（I/O 密集型）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            记忆内容

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str, memory_type: str) -> None:
        """删除记忆文件（快速同步操作，可用 to_thread 封装）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
        """
        pass

    @abstractmethod
    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在（快速同步操作）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            True 如果存在，False 否则
        """
        pass

    @abstractmethod
    async def list_memories(self, memory_type: str) -> list[str]:
        """列出指定类型的记忆文件。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """
        pass
```

### 2.3 IndexManagerPort

**文件**: `src/domain/repositories/index_manager.py`

```python
"""IndexManagerPort — 记忆索引管理抽象端口。"""

from abc import ABC, abstractmethod

class IndexManagerPort(ABC):
    """记忆索引管理抽象端口。

    负责 MEMORY.md 索引的维护与更新。
    所有索引管理实现必须实现此端口。
    """

    @abstractmethod
    async def update_entry(self, entry: dict) -> None:
        """更新索引条目。

        Args:
            entry: 索引条目，包含 name, type, memory_id, description
        """
        pass

    @abstractmethod
    async def remove_entry(self, memory_id: str) -> None:
        """移除索引条目。

        Args:
            memory_id: 记忆 ID
        """
        pass

    @abstractmethod
    async def read_entries(self) -> list[dict]:
        """读取所有索引条目。

        Returns:
            索引条目列表
        """
        pass

    @abstractmethod
    async def search(self, query: str) -> list[dict]:
        """搜索索引条目。

        Args:
            query: 搜索关键词

        Returns:
            匹配的索引条目列表
        """
        pass

    @abstractmethod
    async def truncate(self) -> None:
        """截断索引到最大行数。

        保留最新 MAX_INDEX_LINES 行。
        """
        pass
```

### 2.4 IntegrityPort（修正版）

**文件**: `src/domain/repositories/integrity.py`

```python
"""IntegrityPort — 数据完整性验证抽象端口。"""

from abc import ABC, abstractmethod
from typing import Any

class IntegrityPort(ABC):
    """数据完整性验证抽象端口。

    设计原则：
    - verify_file(): I/O 密集型 → async + to_thread
    - compute_hash()/verify_hash(): CPU 密集型 → sync（事件循环中直接调用不阻塞）

    注意：使用 str | None 类型定义算法，避免引入 infrastructure 层依赖。
    实现内部将字符串转换为 HashAlgorithm enum。
    """

    @abstractmethod
    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        """验证文件完整性（I/O 密集型）。

        Args:
            file_path: 文件路径
            expected_hash: 期望的哈希值

        Returns:
            True 如果哈希匹配，False 否则
        """
        pass

    @abstractmethod
    def compute_hash(self, data: str | bytes, algorithm: str | None = None) -> str:
        """计算数据哈希（CPU 密集型，直接调用不阻塞事件循环）。

        Args:
            data: 数据
            algorithm: 算法字符串（"sha256"/"sha512"/"md5"），None 使用默认算法

        Returns:
            十六进制编码的哈希值
        """
        pass

    @abstractmethod
    def verify_hash(
        self,
        data: str | bytes,
        expected_hash: str,
        algorithm: str | None = None,
    ) -> bool:
        """验证数据哈希（CPU 密集型，直接调用不阻塞事件循环）。

        Args:
            data: 数据
            expected_hash: 期望的哈希值
            algorithm: 算法字符串（"sha256"/"sha512"/"md5"），None 使用默认算法

        Returns:
            True 如果哈希匹配
        """
        pass
```

---

## 3. Infrastructure 实现类改造

### 3.1 FileMemoryAdapter → L0StoragePort 实现

**文件**: `src/infrastructure/storage/file_memory_adapter.py`

**改造要点**：
- `write()`/`read()`：使用 `aiofiles`（I/O 密集型）
- `delete()`/`exists()`/`list_memories()`：使用 `asyncio.to_thread()`（快速同步操作）

```python
import aiofiles
import asyncio
from pathlib import Path
from src.domain.repositories.l0_storage import L0StoragePort

class FileMemoryAdapter(L0StoragePort):
    """L0 文件系统适配器 - 实现 L0StoragePort。"""

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
        def _delete():
            path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
            if path.exists():
                path.unlink()
        await asyncio.to_thread(_delete)

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        def _check():
            return (Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md").exists()
        return await asyncio.to_thread(_check)

    async def list_memories(self, memory_type: str) -> list[str]:
        def _list():
            dir_path = Path(self.config.memory_l0_path) / memory_type
            if not dir_path.exists():
                return []
            return [p.stem for p in dir_path.glob("*.md")]
        return await asyncio.to_thread(_list)
```

### 3.2 OllamaHealthAdapter → HealthCheckPort 实现

**文件**: `src/infrastructure/routing/local_model_health.py`

**重要说明**：现有类 `LocalModelHealth` 需要重命名为 `OllamaHealthAdapter`，以符合 Port 接口实现类的命名规范（具体技术 + Adapter）。

**改造前**（sync requests）：
```python
class LocalModelHealth:
    def check(self) -> bool:
        session = _get_session()
        response = session.get(self.endpoint, timeout=5)
        return response.status_code == 200
```

**改造后**（async httpx）：
```python
import httpx
from src.domain.repositories.health_check import HealthCheckPort

class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 模型健康检查适配器 - 实现 HealthCheckPort。"""

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

### 3.3 MemoryIndex → IndexManagerPort 实现

**文件**: `src/infrastructure/storage/memory_index.py`

**改造后**（async + to_thread 保留锁语义）：
```python
import asyncio
from src.domain.repositories.index_manager import IndexManagerPort

class MemoryIndex(IndexManagerPort):
    """记忆索引管理器 - 实现 IndexManagerPort。"""

    MAX_INDEX_LINES = 200

    async def update_entry(self, entry: dict) -> None:
        def _update():
            entries = self._read_entries_locked()
            entries = [e for e in entries if e["memory_id"] != entry["memory_id"]]
            entries.append(entry)
            self._write_entries_locked(entries)
        await asyncio.to_thread(_update)

    async def remove_entry(self, memory_id: str) -> None:
        def _remove():
            entries = self._read_entries_locked()
            entries = [e for e in entries if e["memory_id"] != memory_id]
            self._write_entries_locked(entries)
        await asyncio.to_thread(_remove)

    async def read_entries(self) -> list[dict]:
        return await asyncio.to_thread(self._read_entries_locked)

    async def search(self, query: str) -> list[dict]:
        entries = await self.read_entries()
        query_lower = query.lower()
        return [e for e in entries if query_lower in e["name"].lower()]

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

### 3.4 IntegrityVerifier → IntegrityPort 实现

**文件**: `src/infrastructure/security/integrity_service.py`

**改造后**（CPU 密集型保持 sync，I/O 密集型用 to_thread）：
```python
from src.domain.repositories.integrity import IntegrityPort

class IntegrityVerifier(IntegrityPort):
    """数据完整性验证器 - 实现 IntegrityPort。"""

    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        def _read_and_verify():
            with open(file_path, "rb") as f:
                content = f.read()
            return self.verify_hash(content, expected_hash)

        return await asyncio.to_thread(_read_and_verify)

    # CPU 密集型：sync 方法，事件循环中直接调用不阻塞
    def compute_hash(self, data: str | bytes, algorithm: str | None = None) -> str:
        """计算数据哈希（CPU 密集型）。

        注意：Port 接口使用 str 类型以避免 Domain 层依赖 infrastructure 层。
        实现内部将字符串转换为 HashAlgorithm enum。
        """
        # 字符串到 enum 的转换
        if algorithm is None:
            algo = self._default_algorithm
        else:
            from src.infrastructure.security.models import HashAlgorithm
            algo = HashAlgorithm(algorithm)

        if isinstance(data, str):
            data = data.encode("utf-8")

        if algo == HashAlgorithm.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif algo == HashAlgorithm.SHA512:
            return hashlib.sha512(data).hexdigest()
        elif algo == HashAlgorithm.MD5:
            return hashlib.md5(data, usedforsecurity=False).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algo}")

    # CPU 密集型：sync 方法
    def verify_hash(self, data: str | bytes, expected_hash: str, algorithm: str | None = None) -> bool:
        """验证数据哈希（CPU 密集型）。"""
        actual_hash = self.compute_hash(data, algorithm)
        return hmac.compare_digest(actual_hash.lower(), expected_hash.lower())
```

### 3.5 ObjectOperations 改造（移除 P1-5 问题）

**文件**: `src/infrastructure/storage/minio/object_operations.py`

**说明**：经审查，`ObjectOperations` 的 sync 方法已被 `MinIORepository` 通过 `asyncio.to_thread()` 包装，不直接暴露给 Domain 层。`P1-5` 问题（`with open()` at line 371）通过直接改造解决，无需新增 Port。

**改造要点**：
- `resume_multipart_upload()` 内的 `with open()` 用 `to_thread` 封装
- `download_object()` 的 `response.read()` 循环用 `to_thread` 包装

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

async def download_object(
    self,
    bucket_name: str,
    object_key: str,
    version_id: str | None = None,
) -> AsyncIterator[bytes]:
    """流式下载对象（修正版：使用 to_thread 避免阻塞）。"""
    loop = asyncio.get_running_loop()
    client = self._client.client
    response = client.get_object(bucket_name, object_key, version_id=version_id)

    def _read_chunk():
        return response.read(8192)

    try:
        while True:
            data = await loop.run_in_executor(None, _read_chunk)
            if not data:
                break
            yield data
    finally:
        response.close()
        response.release_conn()
```

**性能说明**：`download_object` 每个 chunk 调用一次 `run_in_executor`。对于大文件（如 100MB），会有约 12,800 次 executor 调用。但网络 I/O 等待时间远大于线程切换开销，此设计在生产环境中可接受。

---

## 4. 调用链重构

### 4.1 MemoryService 重构

**文件**: `src/domain/services/memory_service.py`

**改造后**（依赖 Port 接口）：
```python
from src.domain.repositories.l0_storage import L0StoragePort

def __init__(
    self,
    text_extractor,
    compressor,
    metadata_repository,
    history_repository,
    l0_storage: L0StoragePort,  # 依赖 Port 接口
    event_publisher,
):
    self._l0_storage = l0_storage

async def _write_to_l0(self, memory_id, memory_type, content, ...):
    await self._l0_storage.write(str(memory_id), memory_type, md_content)
```

### 4.2 调用方注入配置

**文件**: `src/application/services/six_layer_storage_coordinator.py`

```python
from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter

class SixLayerStorageCoordinator:
    def __init__(self, config: MemoryConfig, ...):
        # L0 存储注入（Port + 实现）
        self._l0_storage: L0StoragePort = FileMemoryAdapter(config)

        # L1 缓存：当前由 SixLayerStorageCoordinator 内部使用，不直接暴露给 Domain 层
        # 如需 Domain 层完全解耦，可后续扩展 L1CachePort（不在本次方案范围内）

        # L2-L5 已有 Port 实现
        self._metadata_repo: MemoryMetadataRepositoryProtocol = ...
        self._vector_storage: VectorStorage = ...
        self._object_storage: ObjectStorageRepository = ...
        self._graph_storage: GraphStorage = ...
```

**风险评估**：调用链重构影响以下组件：
| 调用方 | 改造内容 | 风险等级 | 备注 |
|--------|----------|----------|------|
| `MemoryService` | 依赖 `L0StoragePort` 替代 `FileMemoryAdapter` | 中 | 需修改构造函数签名 |
| `SixLayerStorageCoordinator` | 显式注入 `L0StoragePort` | 低 | |
| `MemoryChangedListener` | 依赖 `IndexManagerPort` 替代 `MemoryIndex` | 中 | 需确认注入点 |

---

## 5. 宗师级设计原则（修正版）

```
┌─────────────────────────────────────────────────────────────────────────┐
│               宗师级设计六原则（方案B专属 - v1.5修正版）                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ 1. 端口抽象                                                              │
│    所有外部依赖通过 Domain 层 Port 接口隔离                              │
│    Infrastructure 实现 Port 接口，Domain 层 只依赖 Port                 │
│                                                                         │
│ 2. 纯异步接口（修正）                                                    │
│    - I/O 密集型方法：async + aiofiles / to_thread                     │
│    - CPU 密集型方法：sync 直接调用（不阻塞事件循环）                     │
│    - 禁止在已运行循环中调用 asyncio.run()                                │
│                                                                         │
│ 3. 单一事件循环                                                          │
│    禁止在已运行循环中调用 asyncio.run()                                │
│    使用 call_soon + create_task 或 to_thread                           │
│                                                                         │
│ 4. 上下文纯净                                                            │
│    sync 代码在 sync 上下文，async 代码在 async 上下文                   │
│    混合场景使用 to_thread 封装                                          │
│                                                                         │
│ 5. 锁语义保留                                                            │
│    fcntl.flock 用 to_thread 封装，保留原子性                             │
│                                                                         │
│ 6. 启动时调用可接受                                                       │
│    engine.py, event_bus_config_loader.py 等启动时调用不阻塞事件循环     │
│                                                                         │
│ 7. 职责单一（新增）                                                       │
│    每个 Port 只抽象一组相关操作，避免职责重叠                              │
│    ObjectStorageRepository 已覆盖对象存储，不重复创建 ObjectOperationsPort│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 工时评估（修正版）

### 6.1 新增 Port 接口

| Port | 文件 | 工时 | 复杂度 |
|------|------|------|--------|
| `HealthCheckPort` | `src/domain/repositories/health_check.py` | 0.5d | 低 |
| `L0StoragePort` | `src/domain/repositories/l0_storage.py` | 0.5d | 低 |
| `IndexManagerPort` | `src/domain/repositories/index_manager.py` | 0.5d | 低 |
| `IntegrityPort` | `src/domain/repositories/integrity.py` | 0.5d | 低 |

**新增 Port 总计**: 2d（原 4d，移除 ObjectOperationsPort）

### 6.2 Infrastructure 实现改造

| 实现类 | 改造内容 | 工时 | 测试更新 |
|--------|----------|------|----------|
| `FileMemoryAdapter` | 实现 L0StoragePort + aiofiles | 1d | 0.5d |
| `OllamaHealthAdapter` | 实现 HealthCheckPort + httpx | 0.5d | 0.25d |
| `MemoryIndex` | 实现 IndexManagerPort + to_thread（5个公开方法+锁） | 1.5d | 0.5d |
| `IntegrityVerifier` | 实现 IntegrityPort | 0.5d | 0.25d |
| `ObjectOperations` | 修复 download_object + resume_multipart_upload | 0.5d | 0.25d |

**实现改造总计**: 4d + 1.75d 测试

### 6.3 调用链重构

| 调用方 | 改造内容 | 工时 |
|--------|----------|------|
| `MemoryService` | 改为依赖 L0StoragePort | 0.5d |
| `SixLayerStorageCoordinator` | 注入 L0StoragePort | 0.5d |
| `MemoryChangedListener` | 改为依赖 IndexManagerPort | 0.5d |

**调用链重构总计**: 1.5d

### 6.4 总工时汇总

| 阶段 | 内容 | 工时 |
|------|------|------|
| **Phase 1** | 4 个 Port 接口定义 | 2d |
| **Phase 2** | 5 个 Infrastructure 实现改造 | 4d |
| **Phase 3** | 测试更新 | 1.75d |
| **Phase 4** | 调用链重构 | 1.5d |
| **Phase 5** | 集成验证 + 测试基础设施 | 2d |

**方案B 总工时**: 11.25d（v1.3修正后，原 10.75d）

---

## 7. 阶段划分

```
Phase 1: Port 接口定义（2d）
├── HealthCheckPort（0.5d）
├── L0StoragePort（0.5d）
├── IndexManagerPort（0.5d）
└── IntegrityPort（0.5d）

Phase 2: Infrastructure 实现改造（4d）
├── FileMemoryAdapter → L0StoragePort 实现（1.5d）
├── OllamaHealthAdapter → HealthCheckPort 实现（0.75d）
├── MemoryIndex → IndexManagerPort 实现（2d，含锁逻辑）
└── IntegrityVerifier → IntegrityPort 实现（0.75d）

Phase 3: ObjectOperations 改造（0.75d）
└── 修复 download_object + resume_multipart_upload（0.75d）

Phase 4: 测试更新（1.75d）
├── 所有 async 方法测试 + TDD 循环
└── Mock 实现准备（FakeL0StorageAdapter, FakeMemoryIndex, FakeHealthAdapter, FakeIntegrityVerifier）

Phase 5: 调用链重构（1.5d）
├── MemoryService 依赖注入调整（0.5d）
├── SixLayerStorageCoordinator 调整（0.5d）
└── MemoryChangedListener 调整（0.5d）

Phase 6: 集成验证（2d）
├── 端到端测试
├── 事件循环阻塞验证
├── 性能回归测试
└── 测试基础设施准备
```

---

## 8. 成功标准

| 指标 | 目标 | 验证方式 |
|------|------|----------|
| Port 接口覆盖 | 100%（所有外部依赖通过 Port） | 代码审查 |
| I/O 方法 async | 100%（I/O 密集型方法为 async） | mypy 检查 |
| CPU 方法 sync | 100%（CPU 密集型方法为 sync） | 代码审查 |
| asyncio.run 反模式 | 0 处 | ruff check |
| 事件循环阻塞 | 0 次 | 性能测试 |
| 六边形架构合规 | 100% | 依赖注入审查 |
| 依赖新增 | 0 | pyproject.toml |

---

## 9. 依赖确认

| 依赖 | 状态 | 用途 |
|------|------|------|
| `httpx` | 已有 | HealthCheckPort 实现 |
| `aiofiles` | 已有 | L0StoragePort 实现 |
| `asyncio` | 标准库 | 所有 async 方法 |
| `cryptography` | 已有 | IntegrityPort 实现 |

**结论**：无需新增依赖。

---

## 10. 附录：Port 接口清单（完整版）

### 10.1 已存在 Port

| Port | 定义位置 | 实现类 |
|------|----------|--------|
| `MemoryMetadataRepositoryProtocol` | `domain/repositories/memory_repository.py` | `PostgreSQLMemoryMetadataRepository` |
| `MemoryChangeHistoryRepositoryProtocol` | `domain/repositories/memory_repository.py` | `PostgreSQLMemoryChangeHistoryRepository` |
| `VectorStorage` | `domain/repositories/vector_storage.py` | `QdrantVectorStorage` |
| `CollectionManager` | `domain/repositories/vector_storage.py` | `QdrantCollectionManager` |
| `ObjectStorageRepository` | `domain/repositories/storage.py` | `MinIORepository` |
| `GraphManager` | `domain/repositories/graph_storage.py` | `Neo4jGraphManager` |
| `GraphStorage` | `domain/repositories/graph_storage.py` | `Neo4jGraphStorage` |
| `SessionStorage` | `domain/repositories/session_storage.py` | `RedisSessionStorage` |
| `SemanticCache` | `domain/services/semantic_cache.py` | `RedisSemanticCache` |
| `AuthService` | `domain/services/auth_service.py` | `AuthServiceImpl` |
| `AuditService` | `domain/services/audit_service.py` | `AuditServiceImpl` |
| `PermissionService` | `domain/services/permission_service.py` | `PermissionServiceImpl` |
| `EventPublisherProtocol` | `domain/services/auto_route_service.py` | `DualChannelEventBus` |

### 10.2 方案B 新增/修改 Port

| Port | 定义位置 | 实现类 | 变更说明 |
|------|----------|--------|----------|
| `HealthCheckPort` | `domain/repositories/health_check.py` | `OllamaHealthAdapter` | **新增** |
| `L0StoragePort` | `domain/repositories/l0_storage.py` | `FileMemoryAdapter` | **新增** |
| `IndexManagerPort` | `domain/repositories/index_manager.py` | `MemoryIndex` | **新增** |
| `IntegrityPort` | `domain/repositories/integrity.py` | `IntegrityVerifier` | **新增**（CPU 方法保留 sync） |

---

## 11. 审查修正记录

| 版本 | 变更说明 |
|------|----------|
| v1.0 | 初始方案 |
| v1.1 | **第一轮审查修正**：<br>- 移除 `ObjectOperationsPort`（与 `ObjectStorageRepository` 职责重叠）<br>- 修正 `IntegrityPort`：`compute_hash`/`verify_hash` 保留 sync（CPU 密集型）<br>- 修正 `download_object`：使用 `run_in_executor` 包装同步读取<br>- 工时修正：13d → 10.75d |
| v1.2 | **第二轮审查修正**：<br>- 添加 L1CachePort 可选优化说明<br>- 明确"目标状态"vs"当前状态"描述 |
| v1.3 | **第三轮审查修正**：<br>- §4.2 移除 L1CachePort 引用，标注为预留接口<br>- IntegrityPort 使用 `Literal` 类型避免 domain 层依赖 infrastructure<br>- LocalModelHealth → OllamaHealthAdapter 重命名说明<br>- download_object 添加性能说明<br>- Phase 2 MemoryIndex 工时调整：1.5d → 2d<br>- 添加调用链风险评估<br>- 添加 Mock 实现准备说明<br>- 工时调整：10.75d → 11.25d |
| v1.4 | **第四轮审查修正**：<br>- IntegrityPort 接口类型从 `Literal["sha256", "sha512", "md5"]` 改为 `str \| None`<br>- 实现内部处理字符串到 HashAlgorithm enum 的转换<br>- 符合 Domain 层零依赖原则 |
| v1.5 | **第五轮审查修正**：<br>- 移除 IntegrityPort 未使用的 `Literal` 导入<br>- 更新 docstring 说明（str \| None 而非 Literal） |

---

**方案B v1.5 核心价值**：
1. 通过端口抽象实现 Domain 层与 Infrastructure 层的完全解耦
2. 区分 I/O 密集型（async）与 CPU 密集型（sync）方法设计
3. 避免 Port 职责重叠，遵循单一职责原则
4. 总工时 11.25d，实现完全六边形架构合规
