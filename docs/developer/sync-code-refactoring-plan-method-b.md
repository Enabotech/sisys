# SISYS 同步代码重构方案B（Port+Adapter 宗师级重构）

**生成日期**: 2026-05-01
**版本**: v1.0（方案B - 宗师级）
**依据**: sync-code-analysis.md + sisys-sync-architecture.md + 源码调研 + 端口抽象最佳实践
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
│  ObjectOperations ───────→ [缺失 Port] ────→ MinIO 对象操作               │
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
| **缺失 Port** | **4** | L0Storage, L1Cache, IndexManager, PathResolver |

**端口抽象覆盖率**: ~70%（7/10 核心存储类已有 Port）

---

## 1. 问题清单与 Port 抽象映射

### 1.1 问题 → Port 映射矩阵

| 问题编号 | 文件:行号 | 问题描述 | 需要创建的 Port | 抽象级别 |
|----------|-----------|----------|-----------------|----------|
| P0-1 | `event_listener.py:106` | `asyncio.run()` 在 sync 方法 | `AuditService` 已存在，无需新 Port | 修复调用方式 |
| P0-2 | `local_model_health.py:51` | 同步 `requests.Session` | `HealthCheckPort` | 新增 |
| P1-1 | `auto_trigger_listener.py:112-118` | 重复创建事件循环 | `EventSubscriberPort` | 已有/重构 |
| P1-2 | `file_memory_adapter.py:59,77` | 同步 `Path.write/read_text` | `L0StoragePort` | 新增 |
| P1-3 | `memory_index.py:125,139` | 同步 `open()` + `rename()` | `IndexManagerPort` | 新增 |
| P1-4 | `integrity_service.py:189` | async 内同步 `open()` | `IntegrityPort` | 新增 |
| P1-5 | `object_operations.py:371` | async 内同步 `open()` | `ObjectOperationsPort` | 新增 |
| P2 | `engine.py:76` | 同步 `create_engine()` | 无 | 保持现状 |
| P2 | `event_bus_config_loader.py:41` | 同步 `open()` + YAML | 无 | 保持现状 |

---

## 2. 新增 Port 接口定义

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
        """写入记忆文件。

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
        """读取记忆文件。

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
        """删除记忆文件。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        pass

    @abstractmethod
    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在。

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

### 2.4 IntegrityPort

**文件**: `src/domain/repositories/integrity.py`

```python
"""IntegrityPort — 数据完整性验证抽象端口。"""

from abc import ABC, abstractmethod
from typing import Any

class IntegrityPort(ABC):
    """数据完整性验证抽象端口。

    用于验证文件、数据的完整性和数字签名。
    所有完整性验证实现必须实现此端口。
    """

    @abstractmethod
    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        """验证文件完整性。

        Args:
            file_path: 文件路径
            expected_hash: 期望的哈希值

        Returns:
            True 如果哈希匹配，False 否则
        """
        pass

    @abstractmethod
    def compute_hash(self, data: str | bytes, algorithm: str | None = None) -> str:
        """计算数据哈希。

        Args:
            data: 数据
            algorithm: 算法（sha256/sha512/md5）

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
        """验证数据哈希。

        Args:
            data: 数据
            expected_hash: 期望的哈希值
            algorithm: 算法

        Returns:
            True 如果哈希匹配
        """
        pass
```

### 2.5 ObjectOperationsPort

**文件**: `src/domain/repositories/object_operations.py`

```python
"""ObjectOperationsPort — MinIO 对象操作抽象端口。"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

class ObjectOperationsPort(ABC):
    """MinIO 对象操作抽象端口。

    提供流式上传/下载、分片上传、断点续传等对象操作。
    所有对象存储操作实现必须实现此端口。
    """

    @abstractmethod
    async def upload_object(
        self,
        bucket_name: str,
        object_key: str,
        file_path: str,
        content_type: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        """上传对象，大文件自动分片。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            version_id: 对象版本 ID
        """
        pass

    @abstractmethod
    async def download_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """流式下载对象。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Yields:
            字节流数据块
        """
        pass

    @abstractmethod
    async def get_object_metadata(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        """获取对象元数据。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            对象元数据字典
        """
        pass

    @abstractmethod
    async def delete_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    async def resume_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        redis_client: Any,
    ) -> None:
        """恢复分片上传。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            upload_id: 分片上传 ID
            redis_client: Redis 客户端
        """
        pass
```

---

## 3. Infrastructure 实现类改造

### 3.1 FileMemoryAdapter → L0StoragePort 实现

**文件**: `src/infrastructure/storage/file_memory_adapter.py`

**改造前**（sync）：
```python
def write(self, memory_id: str, memory_type: str, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")

def read(self, memory_id: str, memory_type: str) -> str:
    return file_path.read_text(encoding="utf-8")
```

**改造后**（async + aiofiles）：
```python
import aiofiles
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
        return [file_path.stem for file_path in dir_path.glob("*.md")]
```

### 3.2 OllamaHealthAdapter → HealthCheckPort 实现

**文件**: `src/infrastructure/routing/local_model_health.py`

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

**改造前**（sync + fcntl.flock）：
```python
def truncate(self) -> None:
    with open(self._index_path, encoding="utf-8") as f:
        lines = f.readlines()
    # ... 处理 ...
    temp_path.rename(self._index_path)
```

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

**改造后**：
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

    def compute_hash(self, data: str | bytes, algorithm: HashAlgorithm | None = None) -> str:
        # ... 现有实现 ...
        pass

    def verify_hash(self, data: str | bytes, expected_hash: str, algorithm: HashAlgorithm | None = None) -> bool:
        # ... 现有实现 ...
        pass
```

### 3.5 ObjectOperations → ObjectOperationsPort 实现

**文件**: `src/infrastructure/storage/minio/object_operations.py`

**改造后**：
```python
from src.domain.repositories.object_operations import ObjectOperationsPort

class ObjectOperations(ObjectOperationsPort):
    """MinIO 对象操作 - 实现 ObjectOperationsPort。"""

    async def upload_object(
        self,
        bucket_name: str,
        object_key: str,
        file_path: str,
        content_type: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        # ... 使用 asyncio.to_thread 包装 sync 方法 ...
        return await asyncio.to_thread(
            self._sync_upload_object,
            bucket_name, object_key, file_path, content_type, tags
        )

    async def download_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        # ... 流式下载（已有 async 实现）...
        pass

    async def get_object_metadata(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync_get_metadata,
            bucket_name, object_key, version_id
        )

    async def delete_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        return await asyncio.to_thread(
            self._sync_delete_object,
            bucket_name, object_key, version_id
        )

    async def resume_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        redis_client: Any,
    ) -> None:
        def _read_chunks():
            # ... 现有实现 ...
            pass

        chunks = await asyncio.to_thread(_read_chunks)
        # ... 继续处理 ...
```

---

## 4. 调用链重构

### 4.1 MemoryService 重构

**文件**: `src/domain/services/memory_service.py`

**改造前**（直接依赖 FileMemoryAdapter）：
```python
def __init__(
    self,
    text_extractor,
    compressor,
    metadata_repository,
    history_repository,
    file_adapter,  # 直接依赖实现类
    event_publisher,
):
    self._file_adapter = file_adapter

async def _write_to_l0(self, memory_id, memory_type, content, ...):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: self._file_adapter.write(str(memory_id), memory_type, md_content),
    )
```

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

        # L1 缓存注入（待创建 Port）
        self._l1_cache: L1CachePort = RedisMemoryCache(redis_client)

        # L2-L5 已有 Port 实现
        self._metadata_repo: MemoryMetadataRepositoryProtocol = ...
        self._vector_storage: VectorStorage = ...
        self._object_storage: ObjectStorageRepository = ...
        self._graph_storage: GraphStorage = ...
```

---

## 5. 宗师级设计原则

```
┌─────────────────────────────────────────────────────────────────────────┐
│               宗师级设计六原则（方案B专属）                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ 1. 端口抽象                                                              │
│    所有外部依赖通过 Domain 层 Port 接口隔离                              │
│    Infrastructure 实现 Port 接口，Domain 层 只依赖 Port                 │
│                                                                         │
│ 2. 纯异步接口                                                            │
│    所有 Port 方法定义为 async，由实现类使用 aiofiles/httpx 等           │
│    禁止在 Port 接口中出现 sync 方法签名                                  │
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
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 工时评估

### 6.1 新增 Port 接口

| Port | 文件 | 工时 | 复杂度 |
|------|------|------|--------|
| `HealthCheckPort` | `src/domain/repositories/health_check.py` | 0.5d | 低 |
| `L0StoragePort` | `src/domain/repositories/l0_storage.py` | 1d | 中 |
| `IndexManagerPort` | `src/domain/repositories/index_manager.py` | 1d | 中 |
| `IntegrityPort` | `src/domain/repositories/integrity.py` | 0.5d | 低 |
| `ObjectOperationsPort` | `src/domain/repositories/object_operations.py` | 1d | 中 |

**新增 Port 总计**: 4d

### 6.2 Infrastructure 实现改造

| 实现类 | 改造内容 | 工时 | 测试更新 |
|--------|----------|------|----------|
| `FileMemoryAdapter` | 实现 L0StoragePort + aiofiles | 1d | 0.5d |
| `OllamaHealthAdapter` | 实现 HealthCheckPort + httpx | 0.5d | 0.25d |
| `MemoryIndex` | 实现 IndexManagerPort + to_thread | 1d | 0.5d |
| `IntegrityVerifier` | 实现 IntegrityPort | 0.5d | 0.25d |
| `ObjectOperations` | 实现 ObjectOperationsPort | 1d | 0.5d |

**实现改造总计**: 4.5d + 2d 测试

### 6.3 调用链重构

| 调用方 | 改造内容 | 工时 |
|--------|----------|------|
| `MemoryService` | 改为依赖 L0StoragePort | 0.5d |
| `SixLayerStorageCoordinator` | 注入 L0StoragePort/L1CachePort | 0.5d |
| `MemoryChangedListener` | 改为依赖 IndexManagerPort | 0.5d |

**调用链重构总计**: 1.5d

### 6.4 总工时汇总

| 阶段 | 内容 | 工时 |
|------|------|------|
| **Phase 1** | 新增 5 个 Port 接口定义 | 4d |
| **Phase 2** | 5 个 Infrastructure 实现改造 | 4.5d |
| **Phase 3** | 测试更新 | 2d |
| **Phase 4** | 调用链重构 | 1.5d |
| **Phase 5** | 集成验证 | 1d |

**方案B 总工时**: 13d（相比方案A 5.5d 增加 7.5d，但实现完全六边形架构合规）

---

## 7. 阶段划分

```
Phase 1: Port 接口定义（4d）
├── HealthCheckPort（0.5d）
├── L0StoragePort（1d）
├── IndexManagerPort（1d）
├── IntegrityPort（0.5d）
└── ObjectOperationsPort（1d）

Phase 2: Infrastructure 实现改造（4.5d）
├── FileMemoryAdapter → L0StoragePort 实现（1.5d）
├── OllamaHealthAdapter → HealthCheckPort 实现（0.75d）
├── MemoryIndex → IndexManagerPort 实现（1.5d）
├── IntegrityVerifier → IntegrityPort 实现（0.75d）
└── ObjectOperations → ObjectOperationsPort 实现（1.5d）

Phase 3: 测试更新（2d）
└── 所有 async 方法测试 + TDD 循环

Phase 4: 调用链重构（1.5d）
├── MemoryService 依赖注入调整（0.5d）
├── SixLayerStorageCoordinator 调整（0.5d）
└── MemoryChangedListener 调整（0.5d）

Phase 5: 集成验证（1d）
├── 端到端测试
├── 事件循环阻塞验证
└── 性能回归测试
```

---

## 8. 成功标准

| 指标 | 目标 | 验证方式 |
|------|------|----------|
| Port 接口覆盖 | 100%（所有外部依赖通过 Port） | 代码审查 |
| 纯异步接口 | 100%（Port 方法全部为 async） | mypy 检查 |
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

### 10.2 方案B 新增 Port

| Port | 定义位置 | 实现类 |
|------|----------|--------|
| `HealthCheckPort` | `domain/repositories/health_check.py` | `OllamaHealthAdapter` |
| `L0StoragePort` | `domain/repositories/l0_storage.py` | `FileMemoryAdapter` |
| `IndexManagerPort` | `domain/repositories/index_manager.py` | `MemoryIndex` |
| `IntegrityPort` | `domain/repositories/integrity.py` | `IntegrityVerifier` |
| `ObjectOperationsPort` | `domain/repositories/object_operations.py` | `ObjectOperations` |

---

**方案B 核心价值**：通过端口抽象实现 Domain 层与 Infrastructure 层的完全解耦，所有外部依赖通过 Port 接口隔离，达到六边形架构的宗师级标准。
