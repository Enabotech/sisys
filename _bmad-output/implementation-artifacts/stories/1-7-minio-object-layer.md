# Story 1-7: MinIO 对象存储层

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 MinIO 对象存储层基础设施适配器,
**So that** 系统可以支持版本控制、WORM 存储、断点续传和对象生命周期管理，满足 7 年审计归档合规要求。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 3（五层存储架构）的第四个存储 Story，实现 L4 对象存储层。MinIO 对象存储是系统的关键基础设施，负责：

1. **原始文档 BLOB 存储** - 支持 17 种格式文档的持久化存储，Bucket 命名规范（documents/audit-logs/versions/backups）
2. **版本快照与断点续传** - MinIO 版本控制启用，分片上传（基于总大小 20GB 动态批次），断点续传记录上传 ID 与分片 ETag
3. **不可变存储（WORM）模式** - 审计日志 Bucket 启用 Object Lock（COMPLIANCE 模式），保留期限 7 年（SOX 合规要求）
4. **对象生命周期管理** - 自动过期策略（临时文件 30 天）、自动分层（热数据→温数据→冷数据）
5. **Checkpoint 旧版本归档** - Replay 模式执行后，旧版本快照归档至 WORM 存储，保留期限 7 年
6. **分支状态存储** - 分支快照与差异记录存储至独立 Bucket，支持分支合并/放弃后的归档管理

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 3

**覆盖 FR:**
- FR-SC-03: WORM 存储基础（MVP 采用 PostgreSQL 审计表方案，V1 升级至 MinIO WORM）
- FR-SA-01: 永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差

**覆盖 NFR:**
- NFR-COMP-02: 审计日志保留（基础 WORM 存储）
- NFR-COMP-05: 审计日志完整性（100% 完整，日志审计工具验证通过）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: MinIO 客户端适配器就绪

**Given** MinIO 服务已部署并可用
**When** 创建 MinIO 客户端适配器封装 S3 兼容 API
**Then** 支持 Bucket 创建、查询、删除操作
**And** 支持对象上传、下载、删除操作
**And** 支持 S3 兼容协议（boto3/minio-py 客户端）

**验证标准/Validation Criteria:**
- [ ] MinIO 客户端适配器实现位于 `src/infrastructure/storage/minio/`
- [ ] Bucket 命名规范验证（documents/audit-logs/versions/backups）
- [ ] 支持连接池与超时配置
- [ ] 错误处理完整（桶不存在、权限不足、网络异常）

### AC-2: 版本控制与断点续传实现

**Given** MinIO Bucket 已启用版本控制
**When** 上传大文件（>100MB）或网络中断后恢复
**Then** 自动启用分片上传（Part 大小可配置，默认 10MB）
**And** 断点续传记录上传 ID 与分片 ETag
**And** 版本 ID 返回并存储至元数据

**验证标准/Validation Criteria:**
- [ ] 分片上传逻辑实现（基于总大小 20GB 动态批次）
- [ ] 断点续传状态持久化至 Redis（TTL 24 小时）
- [ ] 版本 ID 正确返回并记录
- [ ] 网络中断模拟测试通过

### AC-3: WORM 存储与对象生命周期管理

**Given** 审计日志 Bucket 需要合规保护
**When** 启用 Object Lock（COMPLIANCE 模式）
**Then** 对象在保留期限内不可删除、不可修改
**And** 自动过期策略配置（临时文件 30 天）
**And** 自动分层策略配置（热数据→温数据→冷数据）

**验证标准/Validation Criteria:**
- [ ] Object Lock 启用逻辑实现（COMPLIANCE 模式，7 年保留）
- [ ] 生命周期规则配置（Expiration、Transition）
- [ ] 尝试删除锁定对象抛出合规异常
- [ ] 保留期限计算正确（7 年 = 2555 天）

### AC-4: 仓储模式适配器实现

**Given** 领域层定义了 ObjectStorage 仓储接口
**When** 基础设施层实现该接口
**Then** 领域层不直接依赖 MinIO 客户端
**And** 通过依赖注入切换不同存储实现
**And** 支持 Mock 实现用于测试

**验证标准/Validation Criteria:**
- [ ] 领域层仓储接口定义位于 `src/domain/repositories/storage.py`
- [ ] 基础设施层实现位于 `src/infrastructure/storage/minio_repository.py`
- [ ] 依赖方向正确（领域层零 MinIO 依赖）
- [ ] Mock 实现通过所有领域层测试

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 本 Story 不新增领域事件，复用现有 `DocumentProcessed` 事件
- [ ] 对象存储操作作为基础设施层实现，不发布独立事件

#### API 契约 (API Contract)
- [ ] 本 Story 为基础设施层，不直接暴露 API
- [ ] 通过领域层仓储接口间接调用

#### 数据模型 (Data Models)
- [ ] 对象存储元数据模型定义位于 `src/domain/entities/object_metadata.py`
- [ ] 关键字段：
  - `object_id: UUID` - 对象唯一标识
  - `bucket_name: str` - Bucket 名称（必须符合命名规范）
  - `object_key: str` - 对象键（路径）
  - `version_id: Optional[str]` - 版本 ID（启用版本控制时）
  - `content_type: str` - MIME 类型
  - `size_bytes: int` - 对象大小（字节）
  - `etag: str` - ETag 哈希
  - `upload_id: Optional[str]` - 分片上传 ID（断点续传时使用）
  - `uploaded_parts: List[dict]` - 已上传分片信息（断点续传状态）
  - `worm_locked: bool` - 是否启用 WORM 锁定
  - `retention_until: Optional[datetime]` - 保留期限
  - `created_at: datetime` - 创建时间
  - `created_by: str` - 创建者
  - `tags: Dict[str, str]` - 对象标签（用于生命周期管理）

#### 仓储接口 (Repository Interface)
- [ ] 领域层接口定义位于 `src/domain/repositories/storage.py`
- [ ] 接口方法：
  ```python
  class ObjectStorageRepository(ABC):
      @abstractmethod
      async def create_bucket(self, bucket_name: str, enable_versioning: bool = False,
                              enable_object_lock: bool = False) -> bool: ...

      @abstractmethod
      async def upload_object(self, bucket_name: str, object_key: str,
                              data: bytes, content_type: str,
                              tags: Optional[Dict[str, str]] = None) -> ObjectMetadata: ...

      @abstractmethod
      async def upload_object_multipart(self, bucket_name: str, object_key: str,
                                        file_path: str, content_type: str,
                                        part_size: int = 10 * 1024 * 1024) -> ObjectMetadata: ...

      @abstractmethod
      async def resume_multipart_upload(self, bucket_name: str, object_key: str,
                                        upload_id: str) -> ObjectMetadata: ...

      @abstractmethod
      async def download_object(self, bucket_name: str, object_key: str,
                                version_id: Optional[str] = None) -> bytes: ...

      @abstractmethod
      async def delete_object(self, bucket_name: str, object_key: str,
                              version_id: Optional[str] = None) -> bool: ...

      @abstractmethod
      async def get_object_metadata(self, bucket_name: str, object_key: str,
                                    version_id: Optional[str] = None) -> ObjectMetadata: ...

      @abstractmethod
      async def list_objects(self, bucket_name: str, prefix: str = "",
                             recursive: bool = True) -> List[ObjectMetadata]: ...

      @abstractmethod
      async def enable_worm_lock(self, bucket_name: str, object_key: str,
                                 retention_days: int = 2555) -> bool: ...

      @abstractmethod
      async def configure_lifecycle(self, bucket_name: str,
                                    rules: List[LifecycleRule]) -> bool: ...
  ```

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1_7.feature`
- [ ] 场景覆盖：
  - Happy Path: Bucket 创建、对象上传/下载、版本控制、WORM 锁定
  - Edge Cases: 大文件分片上传、网络中断恢复、删除锁定对象失败、命名规范验证

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 对象元数据实体 | 验证元数据创建、字段校验、命名规范 | `test_object_metadata.py` | Task 1 |
| **TDD 单元测试** | MinIO 客户端适配器 | 验证客户端初始化、连接池、错误处理 | `test_minio_client_adapter.py` | Task 2 |
| **TDD 单元测试** | Bucket 管理 | 验证 Bucket 创建、版本控制、Object Lock | `test_bucket_management.py` | Task 3 |
| **TDD 单元测试** | 对象上传/下载 | 验证普通上传、分片上传、断点续传、下载 | `test_object_operations.py` | Task 4 |
| **TDD 单元测试** | WORM 锁定与生命周期 | 验证 WORM 启用、保留期限计算、生命周期规则 | `test_worm_and_lifecycle.py` | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（端到端对象存储操作） | `test_story_1_7.feature` | Task 0 |
| **SDD 架构验证** | 依赖方向 | 领域层零 MinIO 依赖、仓储模式正确 | `test_storage_architecture.py` | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/storage`）- **P1 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain/repositories`）- **P1 阻断门禁**
- [ ] **关键路径覆盖率 100%**（所有分支覆盖，特别是断点续传和 WORM 锁定）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | MinIO 客户端适配器就绪 | Task 0 | SDD 规范定义（数据模型、仓储接口、验收测试） | `test_story_1_7.feature` |
| AC-1 | MinIO 客户端适配器就绪 | Task 1 | 对象元数据实体创建 + 命名规范验证 | `test_object_metadata.py` |
| AC-1 | MinIO 客户端适配器就绪 | Task 2 | MinIO 客户端适配器封装（连接池、错误处理） | `test_minio_client_adapter.py` |
| AC-2 | 版本控制与断点续传实现 | Task 3 | Bucket 管理（版本控制、Object Lock 启用） | `test_bucket_management.py` |
| AC-2 | 版本控制与断点续传实现 | Task 4 | 对象操作（上传/下载、分片上传、断点续传） | `test_object_operations.py` |
| AC-3 | WORM 存储与对象生命周期管理 | Task 5 | WORM 锁定逻辑 + 生命周期规则配置 | `test_worm_and_lifecycle.py` |
| AC-4 | 仓储模式适配器实现 | Task 6 | 依赖方向验证 + Mock 实现 + 领域层测试 | `test_storage_architecture.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 在进入代码实现前，明确数据模型、仓储接口、验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask: 定义对象存储元数据模型（`src/domain/entities/object_metadata.py`）
- [ ] Subtask: 定义领域层仓储接口（`src/domain/repositories/storage.py`）
- [ ] Subtask: 创建 Gherkin 验收测试 `tests/acceptance/test_story_1_7.feature`
- [ ] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 对象元数据实体实现

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：ObjectMetadata 实体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_object_metadata.py`（实体创建、字段校验、命名规范验证） |
| 🟢 绿 | 实现 `ObjectMetadata` 数据类最小代码 |
| 🔄 重构 | 添加类型注解、docstring、应用 Pydantic V2 验证 |

- [ ] Subtask: 🔴 红 — 编写 ObjectMetadata 失败测试（字段校验、命名规范）
- [ ] Subtask: 🟢 绿 — 实现 ObjectMetadata 数据类
- [ ] Subtask: 🔄 重构 — 优化 ObjectMetadata 代码（类型注解、docstring）

#### TDD 循环 B：LifecycleRule 实体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_lifecycle_rule.py`（规则创建、过期策略、转换策略） |
| 🟢 绿 | 实现 `LifecycleRule` 数据类最小代码 |
| 🔄 重构 | 添加类型注解、docstring、验证逻辑 |

- [ ] Subtask: 🔴 红 — 编写 LifecycleRule 失败测试
- [ ] Subtask: 🟢 绿 — 实现 LifecycleRule 数据类
- [ ] Subtask: 🔄 重构 — 优化 LifecycleRule 代码

**完成标准/Definition of Done:**
- [ ] ObjectMetadata 和 LifecycleRule 实体实现完成
- [ ] TDD 循环测试全部通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: MinIO 客户端适配器封装

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：MinioClientAdapter 初始化与连接

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_minio_client_adapter.py`（客户端初始化、连接池、超时配置） |
| 🟢 绿 | 实现 `MinioClientAdapter` 类最小代码（构造函数、连接方法） |
| 🔄 重构 | 应用依赖注入模式、添加类型注解、docstring |

- [ ] Subtask: 🔴 红 — 编写 MinioClientAdapter 失败测试（初始化、连接）
- [ ] Subtask: 🟢 绿 — 实现 MinioClientAdapter 类
- [ ] Subtask: 🔄 重构 — 优化 MinioClientAdapter 代码（依赖注入、类型注解）

#### TDD 循环 B：错误处理与重试机制

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写错误处理测试（网络异常、权限不足、桶不存在） |
| 🟢 绿 | 实现错误映射与重试逻辑（指数退避） |
| 🔄 重构 | 统一错误类型定义、优化重试配置 |

- [ ] Subtask: 🔴 红 — 编写错误处理失败测试
- [ ] Subtask: 🟢 绿 — 实现错误处理与重试逻辑
- [ ] Subtask: 🔄 重构 — 优化错误处理代码

**完成标准/Definition of Done:**
- [ ] MinioClientAdapter 实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 基础设施层覆盖率≥75%

---

### Task 3: Bucket 管理实现 — 含完整 TDD 循环

**关联 AC:** AC-1, AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：Bucket 创建与版本控制

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_bucket_management.py`（Bucket 创建、命名规范验证、版本控制启用） |
| 🟢 绿 | 实现 `create_bucket()` 方法最小代码 |
| 🔄 重构 | 添加命名规范校验、类型注解 |

- [ ] Subtask: 🔴 红 — 编写 Bucket 创建失败测试（命名规范、版本控制）
- [ ] Subtask: 🟢 绿 — 实现 `create_bucket()` 方法
- [ ] Subtask: 🔄 重构 — 优化 Bucket 创建代码（命名规范校验）

#### TDD 循环 B：Object Lock 启用

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 Object Lock 启用测试（COMPLIANCE 模式、保留期限） |
| 🟢 绿 | 实现 `enable_object_lock()` 方法 |
| 🔄 重构 | 优化保留期限计算逻辑 |

- [ ] Subtask: 🔴 红 — 编写 Object Lock 启用失败测试
- [ ] Subtask: 🟢 绿 — 实现 `enable_object_lock()` 方法
- [ ] Subtask: 🔄 重构 — 优化 Object Lock 代码

**完成标准/Definition of Done:**
- [ ] Bucket 管理功能实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥75%

---

### Task 4: 对象操作实现 — 含完整 TDD 循环

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：普通上传与下载

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_object_operations.py`（普通上传、下载、元数据返回） |
| 🟢 绿 | 实现 `upload_object()` 和 `download_object()` 方法 |
| 🔄 重构 | 添加内容类型检测、优化错误处理 |

- [ ] Subtask: 🔴 红 — 编写上传/下载失败测试
- [ ] Subtask: 🟢 绿 — 实现上传/下载方法
- [ ] Subtask: 🔄 重构 — 优化上传/下载代码

#### TDD 循环 B：分片上传与断点续传

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写分片上传测试（大文件分割、分片 ETag 记录） |
| 🟢 绿 | 实现 `upload_object_multipart()` 方法 |
| 🔄 重构 | 优化分片大小计算、添加进度回调 |

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写断点续传测试（上传 ID 持久化、分片状态恢复） |
| 🟢 绿 | 实现 `resume_multipart_upload()` 方法 + Redis 状态持久化 |
| 🔄 重构 | 统一状态管理逻辑、优化 TTL 配置 |

- [ ] Subtask: 🔴 红 — 编写分片上传失败测试
- [ ] Subtask: 🟢 绿 — 实现分片上传方法
- [ ] Subtask: 🔄 重构 — 优化分片上传代码
- [ ] Subtask: 🔴 红 — 编写断点续传失败测试
- [ ] Subtask: 🟢 绿 — 实现断点续传方法
- [ ] Subtask: 🔄 重构 — 优化断点续传代码

**完成标准/Definition of Done:**
- [ ] 对象操作功能实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥75%

---

### Task 5: WORM 锁定与生命周期管理 — 含完整 TDD 循环

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：WORM 锁定逻辑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_worm_and_lifecycle.py`（WORM 启用、保留期限计算、删除锁定对象失败） |
| 🟢 绿 | 实现 `enable_worm_lock()` 方法 |
| 🔄 重构 | 添加合规异常类型、优化保留期限验证 |

- [ ] Subtask: 🔴 红 — 编写 WORM 锁定失败测试
- [ ] Subtask: 🟢 绿 — 实现 WORM 锁定方法
- [ ] Subtask: 🔄 重构 — 优化 WORM 锁定代码

#### TDD 循环 B：生命周期规则配置

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写生命周期规则测试（过期策略、转换策略、规则验证） |
| 🟢 绿 | 实现 `configure_lifecycle()` 方法 |
| 🔄 重构 | 统一规则验证逻辑、优化错误处理 |

- [ ] Subtask: 🔴 红 — 编写生命周期规则失败测试
- [ ] Subtask: 🟢 绿 — 实现生命周期规则配置方法
- [ ] Subtask: 🔄 重构 — 优化生命周期规则代码

**完成标准/Definition of Done:**
- [ ] WORM 锁定与生命周期管理功能实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥75%

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-4

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。
> 它验证前面 Task 创建的代码是否符合六边形架构规则。

#### 架构验证测试实现

- [ ] Subtask: 创建 `tests/unit/infrastructure/test_storage_architecture.py`
- [ ] Subtask: 实现领域层零 MinIO 依赖验证（使用 ast 模块扫描）
- [ ] Subtask: 实现仓储模式正确性验证（接口在领域层，实现在基础设施层）
- [ ] Subtask: 实现 Mock 存储实现并验证领域层测试通过
- [ ] Subtask: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Hexagonal Architecture）、仓储模式（Repository Pattern）
- **设计约束:**
  - 领域层零依赖：领域层不直接依赖 MinIO 客户端
  - 依赖倒置：领域层定义接口，基础设施层实现接口
  - 仓储模式：通过 `ObjectStorageRepository` 接口访问对象存储
- **技术栈:**
  - MinIO Python SDK（minio-py，最新稳定版）
  - boto3（S3 兼容备选）
  - Python 3.11+、Pydantic V2（应用层边界验证）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 4 (ADR-004): 五层存储架构

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **MinIO WORM（选中方案）** | S3 兼容、自托管、Object Lock 支持、7 年合规 | 需要额外运维 | ✅ 9/10 |
| AWS S3 Glacier | 托管服务、自动分层 | 数据出境风险、持续成本 | 6/10 |
| Ceph Object Store | 高可用、分布式 | 运维复杂度高、不适合 MVP | 5/10 |

### MinIO Bucket 命名规范

| Bucket 类型 | 命名规范 | 用途 | 保留策略 |
|------------|---------|------|---------|
| **documents** | `documents-{tenant_id}` | 原始文档存储 | 版本控制启用 |
| **audit-logs** | `audit-logs-{tenant_id}` | 审计日志归档 | WORM COMPLIANCE 模式，7 年 |
| **versions** | `versions-{tenant_id}` | 版本快照存储 | 版本控制启用 |
| **backups** | `backups-{tenant_id}` | Checkpoint 旧版本归档 | WORM COMPLIANCE 模式，7 年 |
| **branches** | `branches-{tenant_id}` | 分支状态存储 | 版本控制启用，合并后可删除 |

### 分片上传策略

| 文件大小 | Part 大小 | 最大分片数 | 断点续传 TTL |
|---------|----------|-----------|-------------|
| < 100MB | 不分片 | 1 | N/A |
| 100MB - 1GB | 10MB | 100 | 24 小时 |
| 1GB - 10GB | 50MB | 200 | 24 小时 |
| > 10GB | 100MB | 200（MinIO 限制） | 24 小时 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── object_metadata.py          # ObjectMetadata, LifecycleRule 实体
│   │   └── repositories/
│   │       └── storage.py                  # ObjectStorageRepository 接口
│   └── infrastructure/
│       └── storage/
│           ├── minio/
│           │   ├── __init__.py
│           │   ├── client_adapter.py       # MinioClientAdapter 实现
│           │   ├── bucket_manager.py       # Bucket 管理逻辑
│           │   ├── object_operations.py    # 对象上传/下载逻辑
│           │   └── worm_lifecycle.py       # WORM 锁定与生命周期管理
│           └── minio_repository.py         # ObjectStorageRepository 实现
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   └── test_object_metadata.py     # 实体单元测试
│   │   └── infrastructure/
│   │       ├── test_minio_client_adapter.py
│   │       ├── test_bucket_management.py
│   │       ├── test_object_operations.py
│   │       ├── test_worm_and_lifecycle.py
│   │       └── test_storage_architecture.py # 架构约束验证
│   └── acceptance/
│       └── test_story_1_7.feature          # Gherkin 验收测试
└── docs/
    └── infrastructure/
        └── minio_setup_guide.md            # MinIO 部署与配置指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1-6: Qdrant 向量存储层](./1-6-qdrant-vector-layer.md)（如已完成）

> ⚠️ 如果 Story 1.6 尚未完成，请参考 Story 1.4（Redis 高速缓存层）或 Story 1.5（PostgreSQL 关系存储层）的学习经验。

**关键学习/Key Learnings:**
1. 存储层适配器实现时，确保领域层接口定义清晰，避免基础设施层泄漏到领域层
2. Mock 存储实现对测试至关重要，特别是断点续传和 WORM 锁定等复杂场景
3. 连接池和超时配置需要在早期确定，避免后期性能调优困难

**应用到本故事/Applied to This Story:**
- [ ] 严格遵循领域层接口定义，不直接暴露 MinIO 客户端
- [ ] 提前设计 Mock 存储实现，支持断点续传和 WORM 锁定模拟
- [ ] 早期确定连接池和超时配置策略

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | [模型名称，如 Qwen Code] |
| **Version** | create-story workflow v[版本] |
| **Execution Date** | [执行日期，如 2026-04-14] |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取（Story 1.7: MinIO 对象存储层）
- [ ] 架构约束从 `architecture.md` 提取（五层存储架构、L4 对象存储层）
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-7-minio-object-layer.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/entities/object_metadata.py` - 对象元数据实体
- `src/domain/repositories/storage.py` - 仓储接口
- `src/infrastructure/storage/minio/client_adapter.py` - MinIO 客户端适配器
- `src/infrastructure/storage/minio/bucket_manager.py` - Bucket 管理
- `src/infrastructure/storage/minio/object_operations.py` - 对象操作
- `src/infrastructure/storage/minio/worm_lifecycle.py` - WORM 锁定与生命周期
- `src/infrastructure/storage/minio_repository.py` - 仓储实现
- `tests/unit/domain/test_object_metadata.py` - 实体单元测试
- `tests/unit/infrastructure/test_minio_client_adapter.py` - 客户端适配器测试
- `tests/unit/infrastructure/test_bucket_management.py` - Bucket 管理测试
- `tests/unit/infrastructure/test_object_operations.py` - 对象操作测试
- `tests/unit/infrastructure/test_worm_and_lifecycle.py` - WORM 与生命周期测试
- `tests/unit/infrastructure/test_storage_architecture.py` - 架构约束测试
- `tests/acceptance/test_story_1_7.feature` - Gherkin 验收测试
- `docs/infrastructure/minio_setup_guide.md` - MinIO 部署指南

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.7 |
| **Story Key** | 1-7-minio-object-layer |
| **File** | `_bmad-output/implementation-artifacts/stories/1-7-minio-object-layer.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 3: 五层存储架构 |
| **优先级** | P0-7 |
| **覆盖 FR** | FR-SC-03, FR-SA-01 |
| **覆盖 NFR** | NFR-COMP-02, NFR-COMP-05 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-4）
3. [x] Architecture constraints extracted 架构约束已提取（五层存储、L4 对象存储层、WORM 合规）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-14
**最后更新/Last Updated:** 2026-04-14
**更新说明:** 基于 story-template.md 创建，整合 or.md/prd.md/architecture.md/epics_v1.0.md/project-context.md 上下文
