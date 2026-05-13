# SISYS L4 对象存储层重构详细设计

**版本：** v1.0
**日期：** 2026-05-13
**状态：** 设计完成
**架构师：** Claude Code

---

## 0. 执行摘要

### 0.1 重构目标

1. **统一 Domain 层抽象**：合并 `ObjectStorageRepository` 和 `L4ObjectPort`，以 `L4ObjectPort` 为准
2. **完善四层架构**：建立 Layer 1（Domain通用）→ Layer 2（Application业务）→ Layer 3（Infrastructure技术）→ Layer 4（Infrastructure具体应用）的完整分层
3. **消除代码重复**：确保 `MinIOAdapter` 正确委托 `MinIORepository`，复用已有的分层组件

### 0.2 核心决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 统一抽象基类 | `L4ObjectPort` | 六层架构命名（L0-L5），语义清晰，方法签名更合理 |
| Layer 3 技术实现 | `MinIOAdapter` → `MinIORepository` | 复用已有的 BucketManager/ObjectOperations/WORMManager 分层组件 |
| Layer 2 应用端口 | `DocumentStoragePort(L4ObjectPort)` | 第一个具体应用端口，验证四层架构可行性 |

---

## 1. 现状分析

### 1.1 现有组件清单

```
src/domain/ports/
├── l4_object.py              # L4ObjectPort (Protocol) — 通用对象存储抽象
├── storage.py                # ObjectStorageRepository (Protocol) — 另一个对象存储抽象（待删除）

src/infrastructure/storage/minio/
├── client_adapter.py         # MinioClientAdapter — 连接池管理、错误映射
├── bucket_manager.py         # BucketManager — Bucket CRUD、命名验证、WORM 配置
├── object_operations.py      # ObjectOperations — 上传/下载/元数据/分片上传
├── worm_lifecycle.py          # WORMManager — 合规锁定/生命周期
├── minio_repository.py        # MinIORepository — 实现 ObjectStorageRepository，内部委托上述组件
└── minio_adapter.py          # MinIOAdapter — 实现 L4ObjectPort，委托 MinIORepository
```

### 1.2 接口对应关系

| Port 接口 | 实现 | 状态 |
|-----------|------|------|
| `ObjectStorageRepository` | `MinIORepository` | ⚠️ 待废弃 |
| `L4ObjectPort` | `MinIOAdapter` → `MinIORepository` | ✅ 已委托 |
| 应用层端口 | 无 | ❌ 缺失 |

### 1.3 已有分层组件职责

```
MinioClientAdapter
    ├── 连接池管理（懒加载）
    ├── S3 错误映射
    └── 健康检查

BucketManager
    ├── validate_bucket_name()
    ├── build_bucket_name()
    ├── create_bucket()
    ├── enable_object_lock()
    ├── delete_bucket()
    ├── bucket_exists()
    └── list_buckets()

ObjectOperations
    ├── upload_object()      # 自动分片（<100MB 不分片，>100MB 分片）
    ├── download_object()    # 流式下载，防 OOM
    ├── get_object_metadata()
    ├── delete_object()
    ├── resume_multipart_upload()  # 断点续传
    └── save_multipart_state()     # Redis 状态持久化

WORMManager
    ├── enable_worm_lock()        # Governance 模式保留策略
    ├── archive_object()           # 归档至 WORM 存储
    ├── delete_object()            # WORM 锁定对象抛出 ComplianceLockError
    ├── get_object_retention()
    ├── configure_lifecycle()
    └── list_lifecycle_rules()

MinIORepository (组合上述组件)
    ├── store()    → ObjectOperations.upload_object()
    ├── retrieve() → ObjectOperations.download_object()
    ├── delete()   → WORMManager.delete_object()
    ├── get_metadata() → ObjectOperations.get_object_metadata()
    ├── list_objects() → BucketManager._list_objects_via_client()
    └── archive()  → WORMManager.archive_object()
```

### 1.4 现有问题

| 问题 | 描述 | 影响 |
|------|------|------|
| P1 | `ObjectStorageRepository` 和 `L4ObjectPort` 两个抽象并存 | 维护成本增加，职责不清 |
| P2 | 缺少应用层具体端口（Layer 2） | 无法满足特定业务场景语义 |
| P3 | `L4ObjectPort` 的 `list_objects` 缺少 `bucket_type` 参数 | 与 `ObjectStorageRepository` 不一致 |

---

## 2. 目标架构

### 2.1 四层架构

```
Layer 1: Domain — 通用抽象
═══════════════════════════════════════════════════════════════════
    L4ObjectPort (Protocol)
        ├── store(bucket_type, object_key, file_path, content_type, tags) → str
        ├── retrieve(bucket_type, object_key, version_id) → AsyncIterator[bytes]
        ├── delete(bucket_type, object_key, version_id) → bool
        ├── get_metadata(bucket_type, object_key, version_id) → dict
        ├── archive(bucket_type, object_key, content, retention_days) → str
        └── list_objects(bucket_type, prefix, recursive) → list[dict]

Layer 2: Application — 业务语义
═══════════════════════════════════════════════════════════════════
    DocumentStoragePort(L4ObjectPort, Protocol)
        ├── store_document(user_id, document_type, file_path, content_type, metadata) → str
        ├── retrieve_document(user_id, document_type, document_id, version_id) → AsyncIterator[bytes]
        └── list_user_documents(user_id, document_type, prefix) → list[dict]

Layer 3: Infrastructure — 技术实现 + 存储管理
═══════════════════════════════════════════════════════════════════
    MinIOAdapter(L4ObjectPort)
        └── 委托 MinIORepository

    MinIORepository (实现 L4ObjectPort)
        └── 内部委托:
           ├── BucketManager          → 连接池/bucket CRUD/命名验证
           ├── ObjectOperations       → 上传/下载/元数据/分片
           └── WORMManager            → 合规/生命周期

Layer 4: Infrastructure — 具体应用实现
═══════════════════════════════════════════════════════════════════
    MinIODocumentStorage(DocumentStoragePort)
        └── 组合 MinIOAdapter，实现业务语义
```

### 2.2 关键设计原则

1. **依赖倒置**：Domain 层不依赖 Infrastructure 层
2. **单一职责**：每层只负责自己的职责
3. **可替换性**：Layer 3 可替换为 S3Adapter 等其他实现
4. **可测试性**：每层通过 Port 接口可独立测试

---

## 3. 详细设计

### 3.1 Layer 1: L4ObjectPort（更新）

**文件：** `src/domain/ports/l4_object.py`

**变更：** `list_objects` 增加 `bucket_type` 参数，与 `ObjectStorageRepository` 保持一致。

```python
# src/domain/ports/l4_object.py

class L4ObjectPort(Protocol):
    """L4 对象存储接口（最底层通用抽象）。

    对应 architecture.md §11.1：
    - 原始文档、证据包存储
    - Object Lock COMPLIANCE 模式 7 年 retention

    设计原则：
    - 领域层零外部依赖（仅用 Protocol + typing）
    - 异步优先（async def），除 retrieve 是同步迭代器
    - 技术无关（可使用 MinIO/S3/Azure Blob 等实现）
    """

    async def store(
        self,
        bucket_type: str,
        object_key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> str:
        """存储对象（流式，防 OOM）。

        Args:
            bucket_type: Bucket 类型（如 "raw-documents"）
            object_key: 对象键（路径）
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            版本 ID 或 ETag
        """

    def retrieve(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """流式下载对象（防 OOM）。

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Yields:
            字节流数据块
        """

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象（WORM 锁定对象抛出 ComplianceLockError）。

        Returns:
            是否成功
        """

    async def get_metadata(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict:
        """获取对象元数据。

        Returns:
            元数据字典
        """

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,  # 7 年
    ) -> str:
        """归档对象（带 WORM retention）。

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            content: 对象内容（bytes），None 表示只设置 retention
            retention_days: retention 天数（默认 2555 = 7 年）

        Returns:
            对象 ID 或 ETag
        """

    async def list_objects(
        self,
        bucket_type: str,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[dict]:
        """列出对象，支持前缀过滤。

        Args:
            bucket_type: Bucket 类型
            prefix: 前缀过滤
            recursive: 是否递归列出子目录

        Returns:
            对象元数据列表
        """
```

### 3.2 删除 ObjectStorageRepository

**文件：** `src/domain/ports/storage.py`

**操作：** 删除此文件，迁移所有引用到 `L4ObjectPort`。

**影响文件：**
- `src/infrastructure/storage/minio/minio_repository.py` — 实现改为 `L4ObjectPort`
- 所有导入 `ObjectStorageRepository` 的文件

### 3.3 Layer 3: MinIOAdapter（确认委托）

**文件：** `src/infrastructure/storage/minio/minio_adapter.py`

**状态：** 已正确实现委托 `MinIORepository`，无需修改。

```python
class MinIOAdapter(L4ObjectPort):
    """MinIO 对象存储适配器。

    委托 MinIORepository 处理底层存储逻辑，
    复用已有的 BucketManager/ObjectOperations/WORMManager 分层组件。
    """

    def __init__(self, repository: MinIORepository):
        self._repository = repository

    async def store(self, bucket_type, object_key, file_path, content_type, tags=None) -> str:
        return await self._repository.store(bucket_type, object_key, file_path, content_type, tags)

    def retrieve(self, bucket_type, object_key, version_id=None) -> AsyncIterator[bytes]:
        return self._repository.retrieve(bucket_type, object_key, version_id)

    async def delete(self, bucket_type, object_key, version_id=None) -> bool:
        return await self._repository.delete(bucket_type, object_key, version_id)

    async def get_metadata(self, bucket_type, object_key, version_id=None) -> dict:
        return await self._repository.get_metadata(bucket_type, object_key, version_id)

    async def archive(self, bucket_type, object_key, content=None, retention_days=2555) -> str:
        return await self._repository.archive(bucket_type, object_key, retention_days)

    async def list_objects(self, bucket_type, prefix="", recursive=True) -> list[dict]:
        return await self._repository.list_objects(bucket_type, prefix, recursive)
```

### 3.4 Layer 2: DocumentStoragePort

**新文件：** `src/application/ports/document_storage.py`

```python
"""DocumentStoragePort — 文档存储应用层接口。

继承 L4ObjectPort，提供文档业务语义：
- 自动路径生成（按用户/类型/日期组织）
- 内容校验（大小、类型）
- 版本跟踪

设计原则：
- 应用层零外部依赖
- 异步优先（async def）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from src.domain.ports.l4_object import L4ObjectPort


class DocumentStoragePort(L4ObjectPort, Protocol):
    """文档存储应用层接口。

    继承 L4ObjectPort，提供文档业务语义。
    路径格式: documents/{user_id}/{document_type}/YYYY-MM/{filename}

    具体实现：
    - MinIODocumentStorage (infrastructure)
    """

    # === 文档特有操作 ===

    async def store_document(
        self,
        user_id: str,
        document_type: str,
        file_path: str,
        content_type: str = "application/pdf",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """存储文档（自动组织路径）。

        Args:
            user_id: 用户 ID
            document_type: 文档类型（contract/report/evidence）
            file_path: 本地文件路径
            content_type: MIME 类型
            metadata: 可选元数据

        Returns:
            对象键或 ETag
        """

    def retrieve_document(
        self,
        user_id: str,
        document_type: str,
        document_id: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """下载文档。

        Args:
            user_id: 用户 ID
            document_type: 文档类型
            document_id: 文档 ID
            version_id: 可选版本 ID

        Yields:
            字节流数据块
        """

    async def list_user_documents(
        self,
        user_id: str,
        document_type: str | None = None,
        prefix: str = "",
    ) -> list[dict]:
        """列出用户的文档。

        Args:
            user_id: 用户 ID
            document_type: 可选，按类型过滤
            prefix: 可选，前缀过滤

        Returns:
            文档元数据列表
        """

    async def get_document_metadata(
        self,
        user_id: str,
        document_type: str,
        document_id: str,
    ) -> dict | None:
        """获取文档元数据。

        Args:
            user_id: 用户 ID
            document_type: 文档类型
            document_id: 文档 ID

        Returns:
            元数据字典，不存在返回 None
        """

    # === 继承自 L4ObjectPort 的方法（显式声明以满足类型检查） ===

    async def store(
        self,
        bucket_type: str,
        object_key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> str: ...

    def retrieve(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]: ...

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool: ...

    async def get_metadata(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict: ...

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str: ...

    async def list_objects(
        self,
        bucket_type: str,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[dict]: ...
```

### 3.5 Layer 4: MinIODocumentStorage

**新文件：** `src/infrastructure/storage/minio/document_storage.py`

```python
"""MinIODocumentStorage — MinIO 文档存储实现。

实现 DocumentStoragePort 接口，提供文档业务语义。
组合 MinIOAdapter 处理底层存储。

设计原则：
- 薄适配器层，仅做语义转换
- 复用 MinIOAdapter 的底层存储能力
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from src.application.ports.document_storage import DocumentStoragePort
from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter


class MinIODocumentStorage(DocumentStoragePort):
    """MinIO 文档存储实现。

    实现 DocumentStoragePort 接口，提供文档业务语义。
    组合 MinIOAdapter 处理底层存储。

    路径格式: documents/{user_id}/{document_type}/YYYY-MM/{filename}
    """

    BUCKET_TYPE = "documents"

    def __init__(self, adapter: MinIOAdapter):
        """初始化文档存储。

        Args:
            adapter: MinIO 适配器实例
        """
        self._adapter = adapter

    async def store_document(
        self,
        user_id: str,
        document_type: str,
        file_path: str,
        content_type: str = "application/pdf",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """存储文档（自动组织路径）。

        Args:
            user_id: 用户 ID
            document_type: 文档类型
            file_path: 本地文件路径
            content_type: MIME 类型
            metadata: 可选元数据

        Returns:
            对象键
        """
        date_path = datetime.now().strftime("%Y-%m")
        filename = Path(file_path).name
        object_key = f"documents/{user_id}/{document_type}/{date_path}/{filename}"

        tags = metadata.copy() if metadata else {}
        tags["user_id"] = user_id
        tags["document_type"] = document_type

        return await self._adapter.store(
            bucket_type=self.BUCKET_TYPE,
            object_key=object_key,
            file_path=file_path,
            content_type=content_type,
            tags=tags,
        )

    def retrieve_document(
        self,
        user_id: str,
        document_type: str,
        document_id: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """下载文档。

        Args:
            user_id: 用户 ID
            document_type: 文档类型
            document_id: 文档 ID
            version_id: 可选版本 ID

        Yields:
            字节流数据块
        """
        object_key = f"documents/{user_id}/{document_type}/.../{document_id}"
        return self._adapter.retrieve(self.BUCKET_TYPE, object_key, version_id)

    async def list_user_documents(
        self,
        user_id: str,
        document_type: str | None = None,
        prefix: str = "",
    ) -> list[dict]:
        """列出用户的文档。

        Args:
            user_id: 用户 ID
            document_type: 可选，按类型过滤
            prefix: 可选，前缀过滤

        Returns:
            文档元数据列表
        """
        filter_prefix = f"documents/{user_id}/"
        if document_type:
            filter_prefix += f"{document_type}/"
        filter_prefix += prefix

        return await self._adapter.list_objects(self.BUCKET_TYPE, filter_prefix, recursive=False)

    async def get_document_metadata(
        self,
        user_id: str,
        document_type: str,
        document_id: str,
    ) -> dict | None:
        """获取文档元数据。

        Args:
            user_id: 用户 ID
            document_type: 文档类型
            document_id: 文档 ID

        Returns:
            元数据字典，不存在返回 None
        """
        object_key = f"documents/{user_id}/{document_type}/.../{document_id}"
        try:
            return await self._adapter.get_metadata(self.BUCKET_TYPE, object_key)
        except Exception:
            return None

    # === 继承自 L4ObjectPort 的方法委托 ===

    async def store(self, bucket_type: str, object_key: str, file_path: str,
                    content_type: str = "application/octet-stream",
                    tags: dict[str, str] | None = None) -> str:
        return await self._adapter.store(bucket_type, object_key, file_path, content_type, tags)

    def retrieve(self, bucket_type: str, object_key: str,
                 version_id: str | None = None) -> AsyncIterator[bytes]:
        return self._adapter.retrieve(bucket_type, object_key, version_id)

    async def delete(self, bucket_type: str, object_key: str,
                    version_id: str | None = None) -> bool:
        return await self._adapter.delete(bucket_type, object_key, version_id)

    async def get_metadata(self, bucket_type: str, object_key: str,
                          version_id: str | None = None) -> dict:
        return await self._adapter.get_metadata(bucket_type, object_key, version_id)

    async def archive(self, bucket_type: str, object_key: str,
                      content: bytes | None = None, retention_days: int = 2555) -> str:
        return await self._adapter.archive(bucket_type, object_key, content, retention_days)

    async def list_objects(self, bucket_type: str, prefix: str = "",
                          recursive: bool = True) -> list[dict]:
        return await self._adapter.list_objects(bucket_type, prefix, recursive)
```

---

## 4. 目录结构

### 4.1 重构后结构

```
src/domain/ports/
├── l4_object.py                 # ★ 更新：L4ObjectPort（统一抽象基类）
├── storage.py                  # ★ 删除：ObjectStorageRepository（合并到 L4ObjectPort）
└── ...

src/application/ports/
├── document_storage.py          # ★ 新增：DocumentStoragePort（Layer 2 应用端口）
└── ...

src/infrastructure/storage/minio/
├── minio_adapter.py             # 保持：MinIOAdapter → MinIORepository
├── minio_repository.py          # ★ 更新：实现 L4ObjectPort（移除 ObjectStorageRepository）
├── document_storage.py          # ★ 新增：MinIODocumentStorage（Layer 4 具体应用实现）
└── ...
```

---

## 5. 执行步骤

### Phase 1: 删除 ObjectStorageRepository，迁移到 L4ObjectPort

**目标：** 统一 Domain 层抽象，消除并存接口

| 步骤 | 任务 | 验证 |
|------|------|------|
| 1.1 | 更新 `src/infrastructure/storage/minio/minio_repository.py` 实现 `L4ObjectPort`（而非 `ObjectStorageRepository`） | 导入检查 |
| 1.2 | 更新所有导入 `ObjectStorageRepository` 的文件，改为 `L4ObjectPort` | `grep -r "ObjectStorageRepository" --include="*.py"` 无结果 |
| 1.3 | 更新 `src/domain/ports/__init__.py` 移除 `ObjectStorageRepository` 导出 | 导入检查 |
| 1.4 | 删除 `src/domain/ports/storage.py` | 文件不存在 |

**影响文件清单：**
```bash
grep -rl "ObjectStorageRepository" --include="*.py" src/
```

### Phase 2: 更新 L4ObjectPort.list_objects 签名

**目标：** 增加 `bucket_type` 参数，与实现一致

| 步骤 | 任务 | 验证 |
|------|------|------|
| 2.1 | 更新 `L4ObjectPort.list_objects` 签名，增加 `bucket_type: str` 参数 | 类型检查 |
| 2.2 | 更新 `MinIOAdapter.list_objects` 委托传递 `bucket_type` | 测试通过 |
| 2.3 | 更新所有调用 `list_objects` 的代码 | 测试通过 |

### Phase 3: 创建 DocumentStoragePort

**目标：** 建立 Layer 2 应用层端口

| 步骤 | 任务 | 验证 |
|------|------|------|
| 3.1 | 创建 `src/application/ports/document_storage.py` | 文件存在 |
| 3.2 | 定义 `DocumentStoragePort(L4ObjectPort, Protocol)` | 类型检查 |
| 3.3 | 添加文档特有方法：`store_document`, `retrieve_document`, `list_user_documents`, `get_document_metadata` | 接口检查 |
| 3.4 | 显式声明继承的 L4ObjectPort 方法（满足类型检查器） | mypy 通过 |

### Phase 4: 创建 MinIODocumentStorage

**目标：** 建立 Layer 4 具体应用实现

| 步骤 | 任务 | 验证 |
|------|------|------|
| 4.1 | 创建 `src/infrastructure/storage/minio/document_storage.py` | 文件存在 |
| 4.2 | 实现 `MinIODocumentStorage(DocumentStoragePort)` | 类型检查 |
| 4.3 | 组合 `MinIOAdapter` 处理底层存储 | 委托检查 |
| 4.4 | 实现路径自动生成（按用户/类型/日期组织） | 功能测试 |

### Phase 5: 更新导出和 __init__.py

**目标：** 确保新端口可被导入

| 步骤 | 任务 | 验证 |
|------|------|------|
| 5.1 | 更新 `src/application/ports/__init__.py` 导出 `DocumentStoragePort` | 导入检查 |
| 5.2 | 更新 `src/infrastructure/storage/minio/__init__.py` 导出 `MinIODocumentStorage` | 导入检查 |

### Phase 6: 回归测试

**目标：** 确保重构不破坏现有功能

| 步骤 | 任务 | 验证 |
|------|------|------|
| 6.1 | 运行单元测试：`pytest tests/unit/domain/ports/test_l4_object_port.py -v` | 通过 |
| 6.2 | 运行单元测试：`pytest tests/unit/infrastructure/storage/test_minio_adapter.py -v` | 通过 |
| 6.3 | 运行集成测试：`pytest tests/integration/ -x -q` | 通过 |
| 6.4 | 运行架构测试：`pytest tests/unit/architecture/ -x -q` | 通过 |

---

## 6. 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| R1: 删除 ObjectStorageRepository 破坏现有调用 | 中 | 高 | Phase 1.2 更新所有引用，Phase 6 完整回归测试 |
| R2: list_objects 签名变更破坏调用方 | 中 | 中 | Phase 2.3 更新所有调用，Phase 6 集成测试覆盖 |
| R3: DocumentStoragePort 继承关系不满足类型检查 | 低 | 中 | Phase 3.4 显式声明继承方法 |

---

## 7. 兼容性考虑

### 7.1 向后兼容

| 组件 | 变更类型 | 兼容策略 |
|------|---------|---------|
| `L4ObjectPort` | 方法签名扩展 | 保持原有方法，新增 `bucket_type` 参数 |
| `MinIOAdapter` | 委托关系不变 | 无需变更 |
| `UnifiedStorageGateway` | 无需变更 | 依赖 `L4ObjectPort`，已兼容 |

### 7.2 影响范围

| 模块 | 影响 | 迁移工作 |
|------|------|---------|
| `MinIORepository` | 实现接口变更 | Phase 1.1 更新 |
| `ObjectStorageRepository` 引用方 | 迁移到 L4ObjectPort | Phase 1.2 更新 |
| `UnifiedStorageGateway` | 无需变更 | - |

---

## 8. 扩展性设计

### 8.1 支持其他对象存储实现

```python
# S3 适配器示例（未来扩展）

class S3Adapter(L4ObjectPort):
    """AWS S3 适配器实现。"""

    def __init__(self, repository: S3Repository):
        self._repository = repository

    async def store(self, bucket_type, object_key, file_path, content_type, tags=None) -> str:
        return await self._repository.store(bucket_type, object_key, file_path, content_type, tags)

    # ... 其他方法类似
```

### 8.2 新增其他应用端口

```python
# AvatarStoragePort 示例

class AvatarStoragePort(L4ObjectPort, Protocol):
    """头像存储应用层接口。"""

    async def store_avatar(self, user_id: str, file_path: str, file_type: str = "image/png") -> str: ...
    async def retrieve_avatar(self, user_id: str) -> AsyncIterator[bytes]: ...
    async def delete_avatar(self, user_id: str) -> bool: ...
```

---

## 9. 验收标准

| 标准 | 描述 | 测量方式 |
|------|------|---------|
| R1 | 所有 Domain 抽象统一到 `L4ObjectPort` | `grep -r "ObjectStorageRepository" --include="*.py"` 无结果 |
| R2 | `MinIOAdapter` 正确委托 `MinIORepository` | `test_minio_adapter.py` 所有测试通过 |
| R3 | `DocumentStoragePort` 正确继承 `L4ObjectPort` | `issubclass(DocumentStoragePort, L4ObjectPort)` |
| R4 | `MinIODocumentStorage` 实现 `DocumentStoragePort` | `isinstance(storage, DocumentStoragePort)` |
| R5 | 所有测试通过 | `pytest tests/ -x -q` |

---

## 10. 附录

### 10.1 术语表

| 术语 | 定义 |
|------|------|
| L4ObjectPort | Layer 4 对象存储抽象端口（通用底层抽象） |
| DocumentStoragePort | 文档存储应用层接口（业务语义） |
| MinIOAdapter | MinIO 技术适配器（Layer 3） |
| MinIODocumentStorage | MinIO 文档存储具体实现（Layer 4） |
| MinIORepository | MinIO 仓储实现（内部委托分层组件） |

### 10.2 参考文档

- [架构文档 - 存储架构设计](../architecture/architecture.md)
- [L1 缓存层重构设计](./sisys-l1-cache-refactor.md)
- [L2 RDB 重构设计](./sisys-l2-rdb-refactor.md)
- [六边形架构模式 - Martin Fowler](https://martinfowler.com/articles/hexagonal-architecture.html)

---

**审批记录**

| 版本 | 日期 | 审批人 | 状态 |
|------|------|--------|------|
| 1.0.0 | 2026-05-13 | - | 初始版本 |
