# Story 2-1: 文档上传（17 种格式）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。
>
> **🔧 技术约束：**
> 1. **存储层已就绪** — `DocumentStoragePort`（应用层端口）和 `MinIODocumentStorage`（基础设施层实现）已在 Epic 1 Story 1.7 中实现，通过 `resolve("document_storage")` 注入
> 2. **实体已存在** — `Document` 实体（`src/domain/entities/document.py`）已定义 `document_id`/`filename`/`mime_type`/`file_size_bytes`/`parse_status` 等字段
> 3. **领域事件已存在** — `DocumentProcessed` 事件（`src/domain/events/document_events.py`）已实现，双通道配置已在 `configs/event_channels.yaml` 注册
> 4. **MVP 范围** — 本 Story 仅负责文件接收（上传 → 校验 → 存储 → 元数据持久化），不负责文档解析（Story 2.2a 负责）
> 5. **分片上传** — MinIO 原生支持分片上传，Story 1.7 已在 `ObjectOperations`（`src/infrastructure/storage/minio/object_operations.py`）中实现分片逻辑（含 `calculate_part_size()` 四级策略 + `resume_multipart_upload()`），本 Story 需在应用层编排分片上传流程
> 6. **事件关系** — `DocumentUploaded`（本 Story 新增，上传完成触发）与 `DocumentProcessed`（已有，解析完成触发）是文档生命周期中的两个不同阶段事件，Story 2.2a 将消费 `DocumentUploaded` 并在解析完成后发布 `DocumentProcessed`

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 上传 17 种格式的文档（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html/rtf + zip/tar 压缩包）,
**So that** 系统可以处理企业现有各类文档。

### 业务价值

本 Story 是 Epic 2（文档与数据管理）的第一个 Story，也是文档处理流水线的入口。负责：
1. **格式支持** — 17 种文档格式 + zip/tar 压缩包的接收与校验
2. **分片上传** — 大文件（>100MB）分片上传，断点续传
3. **批量上传** — 并发上传 ≥20，总大小 ≤20GB
4. **元数据持久化** — 文档信息写入 PostgreSQL，原始文件存入 MinIO
5. **事件触发** — 上传完成后发布 `DocumentUploaded` 事件，触发后续解析流水线

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 2: 文档与数据管理，Story 2.1

**前置依赖:** Epic 1 Story 1.7（MinIO 对象存储层 — 已完成 ✅）

**后续依赖:** Story 2.2a（文档解析基础格式）依赖本 Story

**覆盖 FR:** FR-DM-01（用户可以上传 17 种格式的文档）

**or.md 公理追溯:** or.md 二.1.(1) — 支持上传 pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html/rtf + zip/tar 压缩包（rtf 为 Story 级补充，补足 or.md/PRD 计数 17 vs 实列 16 的差异）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 17 种格式文件上传

**Given** 用户已登录并具有上传权限（RBAC 角色包含 `document:upload` 权限）
**When** 用户通过 REST API 上传单个文件（支持 17 种格式）
**Then** 系统校验文件格式和 MIME 类型，拒绝不支持的格式
**And** 系统校验文件大小不超过单文件限制（20GB）
**And** 文件存入 MinIO `raw-documents` bucket，路径 `documents/{user_id}/{doc_type}/{YYYY-MM}/{timestamp}`
**And** 文档元数据写入 PostgreSQL（document_id, filename, mime_type, file_size_bytes, parse_status=PENDING, tenant_id）
**And** 返回 `document_id` 和上传状态

**验证标准/Validation Criteria:**
- [ ] 支持 17 种格式（15 种文档格式 + 2 种压缩格式）：pdf, txt, doc, docx, ppt, pptx, xls, xlsx, csv, jpeg, png, gif, markdown（含 .md 扩展名）, html, rtf, zip, tar
- [ ] MIME 类型与文件扩展名双向校验
- [ ] 不支持的格式返回 400 + 明确错误信息
- [ ] 空文件拒绝（file_size_bytes > 0）
- [ ] 文件名长度限制（≤255 字符）和特殊字符校验

### AC-2: 分片上传与断点续传

**Given** 用户上传大文件（>100MB）
**When** 系统启动分片上传
**Then** 分片大小根据文件总大小动态调整（<100MB 不分片, 100MB-1GB 10MB 分片, 1GB-10GB 50MB 分片, >10GB 100MB 分片），复用 `ObjectOperations.calculate_part_size()` 已有实现
**And** 分片上传状态持久化至 Redis（TTL 24 小时）
**And** 网络中断后可通过 `upload_id` 恢复上传
**And** 所有分片上传完成后自动合并

**验证标准/Validation Criteria:**
- [ ] 分片策略按文档规定四级分片
- [ ] Redis 记录 upload_id、已上传分片列表、ETag
- [ ] 断点续传正确恢复（查询已上传分片，跳过已完成的）
- [ ] 分片上传超时自动清理（TTL 到期）

### AC-3: 批量上传与并发控制

**Given** 用户批量上传多个文件（拖拽或选择多个文件）
**When** 系统接收批量上传请求（总大小 ≤20GB）
**Then** 并发处理上传请求（并发数 ≥20）
**And** 每个文件独立校验、独立存储、独立返回状态
**And** 部分文件失败不影响其他文件上传
**And** 返回批量上传结果汇总（成功数/失败数/各文件详情）

**验证标准/Validation Criteria:**
- [ ] 批量上传支持并发 ≥20
- [ ] 部分失败不回滚已成功文件
- [ ] 总大小限制校验（≤20GB）
- [ ] 批量上传结果包含每个文件的状态

### AC-4: 压缩包处理

**Given** 用户上传 zip 或 tar 压缩包
**When** 系统接收压缩包文件
**Then** 解压并遍历内部文件，过滤支持的格式
**And** 不支持的内部文件跳过并记录警告
**And** 每个内部文件作为独立文档入库
**And** 记录来源压缩包信息

**验证标准/Validation Criteria:**
- [ ] zip/tar 解压正确
- [ ] 内部文件格式过滤
- [ ] 嵌套压缩包支持（最多 3 层，超出层数的内部文件跳过并记录警告）
- [ ] 压缩炸弹防护（解压后总大小 ≤20GB，与批量上传限制一致；或膨胀比超过 10:1 时拒绝）
- [ ] 路径穿越防护（`../` 检测）

### AC-5: 上传事件发布

**Given** 文档上传完成并存入 MinIO
**When** 元数据写入 PostgreSQL 后
**Then** 发布 `DocumentUploaded` 领域事件（realtime Redis + reliable RabbitMQ 双通道）
**And** 事件包含 document_id、filename、mime_type、file_size_bytes、tenant_id、uploaded_by
**And** 事件触发后续文档解析流水线（Story 2.2a 消费此事件）

**验证标准/Validation Criteria:**
- [ ] `DocumentUploaded` 事件定义于 `src/domain/events/document_events.py`
- [ ] 事件通道配置更新至 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`
- [ ] 事件通过 `DualChannelEventBus` 发布
- [ ] 事件包含完整的文档元数据

### AC-6: 上传结果确认

**Given** 文档已上传成功
**When** 用户通过 `document_id` 查询上传结果
**Then** API 返回文档元数据（document_id, filename, mime_type, file_size, parse_status, created_at）
**And** 不存在的 document_id 返回 404
**And** 跨租户隔离（租户 A 看不到租户 B 的文档）

**验证标准/Validation Criteria:**
- [ ] `GET /api/v1/documents/{document_id}` 返回文档详情
- [ ] 不存在的 document_id 返回 404
- [ ] 跨租户隔离（tenant_id 过滤）

> **注：** 文档列表查询（分页、过滤、排序）推迟至后续 Story。本 Story 仅实现上传后的单条确认查询。

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] `DocumentUploaded` 事件定义于 `src/domain/events/document_events.py`
  - 字段：`document_id: uuid.UUID`, `filename: str`, `mime_type: str`, `file_size_bytes: int`, `tenant_id: str`, `uploaded_by: str`
  - 继承 `DomainEvent` 基类，`event_type="DocumentUploaded"`
  - 使用 `@dataclass(frozen=True)`（非 Pydantic）
  - 自动注册到事件注册表（`__init_subclass__`）

#### 数据模型 (Data Models)

- [ ] `Document` 实体已存在于 `src/domain/entities/document.py`，**本 Story 扩展以下内容**：
  - 新增 `tenant_id: str` 字段（租户隔离，默认空字符串，向后兼容）
  - 新增 `uploaded_by: str` 字段（上传者，默认空字符串，向后兼容）
- [ ] `SUPPORTED_FORMATS` 常量定义于 `src/domain/value_objects/document_format.py`
  - 17 种格式的 MIME 类型映射（`dict[str, str]`）
  - 文件扩展名与 MIME 类型双向查询方法
  - 格式校验方法 `is_supported(filename, mime_type) -> bool`
- [ ] `UPLOAD_LIMITS` 常量定义于 `src/domain/value_objects/upload_limits.py`
  - `MAX_FILE_SIZE: int = 20 * 1024 * 1024 * 1024`（20GB）
  - `MAX_BATCH_SIZE: int = 20 * 1024 * 1024 * 1024`（20GB）
  - `MAX_BATCH_COUNT: int = 100`（单批最大文件数）
  - `MAX_FILENAME_LENGTH: int = 255`
  - `CHUNK_SIZES: dict` 分片策略映射

#### 统一端口定义注册与管理 (Port Contract)

- [ ] **新增端口** `document_repository` — 定义于 `src/domain/ports/document_repository.py`
  - Protocol 接口：`save(document: Document) -> Document`
  - Protocol 接口：`find_by_id(document_id: UUID, tenant_id: str) -> Document | None`
  - Protocol 接口：`find_by_tenant(tenant_id: str, filters, pagination) -> list[Document]`
  - 注册至 `src/domain/ports/registry.py`
- [ ] **现有端口复用**（不新增）：
  - `document_storage`（`DocumentStoragePort`） — MinIO 文档存储，`resolve("document_storage")`
  - `l1_cache`（`L1CachePort`） — Redis 缓存，用于分片上传状态
  - `event_publisher`（`EventPublisher`） — 事件发布（定义于 `src/domain/ports/event_publisher.py`）
- [ ] **不新增 DocumentUploadPort** — `DocumentUploadService` 直接作为应用服务（非端口），在 composition_root 中注册为服务
- [ ] 端口实现仅在 `src/composition_root.py` 统一注册
- [ ] 端口契约测试位于 `tests/contracts/test_port_contract_document_upload.py`
- [ ] 端口具备唯一名称、版本、owner、兼容策略

#### 端口契约清单执行约束（强制）

| 端口名称 | 接口 | 实现类 | 生命周期 | Owner |
|---------|------|--------|---------|-------|
| `document_repository` | `DocumentRepositoryPort` (domain/ports) | `PostgresDocumentRepository` (infrastructure/storage/postgresql) | SCOPED | doc-team |
| `document_storage` | `DocumentStoragePort` (application/ports) | `MinIODocumentStorage` (infrastructure/storage/minio) — **已注册** | SCOPED | storage-team |
| `event_publisher` | `EventPublisher` (domain/ports) | `DualChannelEventBus` (infrastructure/messaging) — **已注册** | SINGLETON | messaging-team |
| `l1_cache` | `L1CachePort` (domain/ports) | `RedisCacheAdapter` (infrastructure/storage/redis) — **已注册** | SCOPED | storage-team |

> **注：** `DocumentUploadService` 是应用服务而非端口，直接在 composition_root 中实例化注册（非端口模式）。`ChunkedUploadManager` 位于 infrastructure 层（`src/infrastructure/storage/redis/chunked_upload_manager.py`），通过 `L1CachePort` 操作 Redis 分片状态。

#### API 契约 (API Contract)

- [ ] 端点定义：
  - `POST /api/v1/documents` — 单文件上传（multipart/form-data）
  - `POST /api/v1/documents/batch` — 批量上传（multipart/form-data, 多文件）
  - `POST /api/v1/documents/chunked/init` — 分片上传初始化
  - `PUT /api/v1/documents/chunked/{upload_id}/parts/{part_number}` — 分片上传
  - `POST /api/v1/documents/chunked/{upload_id}/complete` — 分片上传完成
  - `GET /api/v1/documents/{document_id}` — 上传结果确认查询
- [ ] 遵循 JSON:API 风格（data/meta/links 结构）
- [ ] API 版本管理：`/api/v1/documents`
- [ ] API 契约测试：`tests/contracts/test_api_contract_document_upload.py`

#### 六边形架构约束（必须遵守）

**四层架构定义**

| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**依赖方向矩阵**

| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_document_upload.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_document_upload.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | DocumentFormat 值对象 | 格式校验、MIME 映射 | `tests/unit/domain/value_objects/test_document_format.py` | Task 1 |
| **TDD 单元测试** | UploadLimits 常量 | 大小限制、分片策略 | `tests/unit/domain/value_objects/test_upload_limits.py` | Task 1 |
| **TDD 单元测试** | Document 实体扩展 | tenant_id/uploaded_by 字段 | `tests/unit/domain/entities/test_document.py` | Task 1 |
| **TDD 单元测试** | DocumentUploaded 事件 | 事件构造、字段校验 | `tests/unit/domain/events/test_document_uploaded.py` | Task 2 |
| **TDD 单元测试** | DocumentRepositoryPort 接口 | 端口契约签名 | `tests/unit/domain/ports/test_document_repository.py` | Task 2 |
| **TDD 单元测试** | PostgresDocumentRepository | CRUD 操作、租户隔离 | `tests/unit/infrastructure/storage/postgresql/test_document_repository.py` | Task 3 |
| **TDD 单元测试** | DocumentUploadService | 上传编排逻辑 | `tests/unit/application/services/test_document_upload_service.py` | Task 4 |
| **TDD 单元测试** | ChunkedUploadManager | 分片上传状态管理 | `tests/unit/infrastructure/storage/redis/test_chunked_upload_manager.py` | Task 5 |
| **TDD 单元测试** | ArchiveExtractor | 压缩包解压、格式过滤 | `tests/unit/infrastructure/external_services/test_archive_extractor.py` | Task 6 |
| **TDD 单元测试** | 文档上传 API 路由 | 请求/响应格式、认证、校验 | `tests/unit/interfaces/api/test_document_upload_routes.py` | Task 7 |
| **TDD 契约测试** | API 契约 | 端点、状态码、请求/响应结构 | `tests/contracts/test_api_contract_document_upload.py` | Task 0 |
| **TDD 契约测试** | 端口契约 | 端口注册、版本、兼容性 | `tests/contracts/test_port_contract_document_upload.py` | Task 0 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `tests/acceptance/test_acceptance_document_upload.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_acceptance_document_upload.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试完成清单确认 | `tests/acceptance/test_acceptance_document_upload.feature` | Task 10 |
| **集成测试** | 文档上传完整流程 | API→Service→MinIO→PG→事件 | `tests/integration/test_document_upload_integration.py` | Task 8 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `tests/unit/architecture/test_arch_document_upload.py` | Task 9 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）
- [ ] **接口层覆盖率 ≥85%**（`pytest --cov=src/interfaces`）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）
- [ ] **关键路径覆盖率 100%**（格式校验、大小限制、分片上传、事件发布）

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 环境不一致 |
| **资源唯一性** | 使用 `TestTenant` UUID 前缀隔离 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/MinIO 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突 |
| **BDD async** | 步骤函数用 `event_loop.run_until_complete()` | context 数据丢失 |

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 17 种格式文件上传 | Task 1 | DocumentFormat 值对象 + UploadLimits 常量 | `test_document_format.py` |
| AC-1 | 17 种格式文件上传 | Task 2 | DocumentUploaded 事件 + 端口定义 | `test_document_uploaded.py` |
| AC-1 | 17 种格式文件上传 | Task 3 | PostgresDocumentRepository CRUD | `test_document_repository.py` |
| AC-1 | 17 种格式文件上传 | Task 4 | DocumentUploadService 编排 | `test_document_upload_service.py` |
| AC-1 | 17 种格式文件上传 | Task 7 | API 路由实现 | `test_document_upload_routes.py` |
| AC-2 | 分片上传与断点续传 | Task 5 | ChunkedUploadManager | `test_chunked_upload_manager.py` |
| AC-2 | 分片上传与断点续传 | Task 7 | 分片上传 API 端点 | `test_document_upload_routes.py` |
| AC-3 | 批量上传与并发控制 | Task 4 | 批量上传编排 | `test_document_upload_service.py` |
| AC-3 | 批量上传与并发控制 | Task 7 | 批量上传 API 端点 | `test_document_upload_routes.py` |
| AC-4 | 压缩包处理 | Task 6 | ArchiveExtractor | `test_archive_extractor.py` |
| AC-5 | 上传事件发布 | Task 2 | DocumentUploaded 事件定义 | `test_document_uploaded.py` |
| AC-5 | 上传事件发布 | Task 4 | 事件发布编排 | `test_document_upload_service.py` |
| AC-6 | 上传结果确认 | Task 3 | Repository 查询方法 | `test_document_repository.py` |
| AC-6 | 上传结果确认 | Task 7 | 确认 API 端点 | `test_document_upload_routes.py` |
| AC-1~6 | 完整流程验证 | Task 8 | 集成测试 | `test_document_upload_integration.py` |
| AC-1~6 | 架构约束验证 | Task 9 | 架构验证测试 | `test_arch_document_upload.py` |
| AC-1~6 | 规范定义前置 | Task 0 | 契约/验收测试编写 | `test_api_contract_*.py` + `test_acceptance_*.feature` |
| AC-1~6 | 收尾验收 | Task 10 | 完成清单确认 | `test_acceptance_*.feature` + `test_acceptance_*.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~6

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `DocumentUploaded` 领域事件（`src/domain/events/document_events.py` 新增）
- [ ] Subtask 0.2: 定义 `SUPPORTED_FORMATS` 常量和 `DocumentFormat` 值对象（`src/domain/value_objects/document_format.py` 新建）
- [ ] Subtask 0.3: 定义 `UPLOAD_LIMITS` 常量（`src/domain/value_objects/upload_limits.py` 新建）
- [ ] Subtask 0.4: 扩展 `Document` 实体字段（tenant_id, uploaded_by）
- [ ] Subtask 0.5: 定义 `DocumentRepositoryPort` 端口（`src/domain/ports/document_repository.py` 新建，命名与项目 `UserRepositoryPort`/`RoleRepositoryPort` 模式一致）
- [ ] Subtask 0.6: 更新 `docs/api/openapi.yaml` 文档上传端点定义
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_document_upload.feature`
- [ ] Subtask 0.8: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_document_upload.py`
- [ ] Subtask 0.9: 编写 API 契约测试 `tests/contracts/test_api_contract_document_upload.py`
- [ ] Subtask 0.10: 编写端口契约测试 `tests/contracts/test_port_contract_document_upload.py`
- [ ] Subtask 0.11: 更新 `configs/event_channels.yaml` 添加 `DocumentUploaded` 事件通道配置
- [ ] Subtask 0.12: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域值对象与实体扩展

**关联 AC:** AC-1

#### TDD 循环 A：DocumentFormat 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_document_format.py`（格式校验、MIME 映射、17 种格式覆盖） |
| 🟢 绿 | 实现 `src/domain/value_objects/document_format.py` 最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 DocumentFormat 失败测试（is_supported、get_mime_type、get_extension、17 种格式枚举）
- [ ] Subtask 1.2: 🟢 绿 — 实现 DocumentFormat 值对象
- [ ] Subtask 1.3: 🔄 重构 — 优化 DocumentFormat 代码

#### TDD 循环 B：UploadLimits 常量

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_upload_limits.py`（大小限制、分片策略计算） |
| 🟢 绿 | 实现 `src/domain/value_objects/upload_limits.py` 最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 UploadLimits 失败测试（MAX_FILE_SIZE、CHUNK_SIZES、get_chunk_size）
- [ ] Subtask 1.5: 🟢 绿 — 实现 UploadLimits 常量和分片策略方法
- [ ] Subtask 1.6: 🔄 重构 — 优化 UploadLimits 代码

#### TDD 循环 C：Document 实体扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/entities/test_document.py`（新增字段校验、validate 扩展） |
| 🟢 绿 | 修改 `src/domain/entities/document.py` 新增 tenant_id/uploaded_by 字段（默认空字符串，向后兼容） |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 1.7: 🔴 红 — 编写 Document 扩展字段失败测试（tenant_id、uploaded_by 字段存在性和默认值）
- [ ] Subtask 1.8: 🟢 绿 — 扩展 Document 实体
- [ ] Subtask 1.9: 🔄 重构 — 优化 Document 代码

**完成标准/Definition of Done:**
- [ ] DocumentFormat 值对象实现完成（17 种格式全覆盖）
- [ ] UploadLimits 常量实现完成（四级分片策略）
- [ ] Document 实体扩展完成（新字段向后兼容）
- [ ] 所有 TDD 循环测试通过
- [ ] 领域层覆盖率 ≥90%

---

### Task 2: 领域事件与仓储端口定义

**关联 AC:** AC-1, AC-5

#### TDD 循环 A：DocumentUploaded 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_document_uploaded.py`（事件构造、字段校验、序列化） |
| 🟢 绿 | 实现 `src/domain/events/document_events.py` 新增 DocumentUploaded |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 DocumentUploaded 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 DocumentUploaded 事件
- [ ] Subtask 2.3: 🔄 重构 — 优化事件代码

#### TDD 循环 B：DocumentRepositoryPort 端口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_document_repository.py`（Protocol 签名验证） |
| 🟢 绿 | 实现 `src/domain/ports/document_repository.py` Protocol 接口（命名为 `DocumentRepositoryPort`，与项目 `UserRepositoryPort`/`RoleRepositoryPort` 模式一致） |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 2.4: 🔴 红 — 编写 DocumentRepositoryPort 端口签名测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 DocumentRepositoryPort Protocol
- [ ] Subtask 2.6: 🔄 重构 — 优化端口代码

**完成标准/Definition of Done:**
- [ ] DocumentUploaded 事件实现完成
- [ ] DocumentRepositoryPort 端口实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 端口契约测试通过

---

### Task 3: PostgreSQL 文档仓储实现

**关联 AC:** AC-1, AC-6

#### TDD 循环 A：PostgresDocumentRepository

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/postgresql/test_document_repository.py`（CRUD、租户隔离、分页） |
| 🟢 绿 | 实现 `src/infrastructure/storage/postgresql/document_repository.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 PostgresDocumentRepository 失败测试（save、find_by_id、find_by_tenant）
- [ ] Subtask 3.2: 🟢 绿 — 实现 PostgresDocumentRepository（使用 SQLAlchemy AsyncSession）
- [ ] Subtask 3.3: 🔄 重构 — 优化 Repository 代码
- [ ] Subtask 3.4: 创建 Alembic migration（`documents` 表：document_id, tenant_id, filename, mime_type, file_size_bytes, document_type, parse_status, uploaded_by, version, metadata JSONB, created_at, updated_at）
- [ ] Subtask 3.5: 创建必要索引（`idx_documents_tenant_id` 租户隔离, `idx_documents_tenant_created_at` 时间排序）

**完成标准/Definition of Done:**
- [ ] PostgresDocumentRepository CRUD 操作实现完成
- [ ] 租户隔离正确（tenant_id 过滤）
- [ ] Alembic migration 创建完成
- [ ] 所有 TDD 循环测试通过
- [ ] 基础设施层覆盖率 ≥75%

---

### Task 4: 文档上传服务（应用层编排）

**关联 AC:** AC-1, AC-3, AC-5

#### TDD 循环 A：DocumentUploadService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_document_upload_service.py`（单文件上传、批量上传、事件发布） |
| 🟢 绿 | 实现 `src/application/services/document_upload_service.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 编写 DocumentUploadService 失败测试（upload 单文件、upload_batch 批量、事件发布、格式校验失败、大小超限）
- [ ] Subtask 4.2: 🟢 绿 — 实现 DocumentUploadService（编排格式校验→Document 实体构造→MinIO 存储→PG 元数据→事件发布，依赖注入 DocumentRepositoryPort + DocumentStoragePort + EventPublisher）
- [ ] Subtask 4.3: 🔄 重构 — 优化服务代码
- [ ] Subtask 4.4: 在 `src/composition_root.py` 注册 `document_repository` 端口和 `DocumentUploadService` 服务

**完成标准/Definition of Done:**
- [ ] DocumentUploadService 编排逻辑实现完成
- [ ] 端口注册到 composition_root.py
- [ ] 所有 TDD 循环测试通过
- [ ] 应用层覆盖率 ≥85%

---

### Task 5: 分片上传管理器（基础设施层）

**关联 AC:** AC-2

#### TDD 循环 A：ChunkedUploadManager

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/redis/test_chunked_upload_manager.py`（分片策略、Redis 状态管理、断点续传） |
| 🟢 绿 | 实现 `src/infrastructure/storage/redis/chunked_upload_manager.py`（通过 L1CachePort 操作 Redis，复用 ObjectOperations 分片逻辑） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 5.1: 🔴 红 — 编写 ChunkedUploadManager 失败测试（init_upload、upload_part、complete_upload、resume_upload、TTL 过期）
- [ ] Subtask 5.2: 🟢 绿 — 实现 ChunkedUploadManager（Redis 存储分片状态，委托 ObjectOperations 执行实际分片上传）
- [ ] Subtask 5.3: 🔄 重构 — 优化分片管理代码

**完成标准/Definition of Done:**
- [ ] ChunkedUploadManager 实现完成（四级分片策略）
- [ ] Redis 状态管理正确（upload_id → 分片列表 → ETag）
- [ ] 断点续传功能正常
- [ ] 所有 TDD 循环测试通过

---

### Task 6: 压缩包处理

**关联 AC:** AC-4

#### TDD 循环 A：ArchiveExtractor

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/test_archive_extractor.py`（zip/tar 解压、格式过滤、嵌套检测、压缩炸弹防护、路径穿越防护） |
| 🟢 绿 | 实现 `src/infrastructure/external_services/archive_extractor.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 6.1: 🔴 红 — 编写 ArchiveExtractor 失败测试（extract_zip、extract_tar、嵌套深度、压缩炸弹、路径穿越 `../`）
- [ ] Subtask 6.2: 🟢 绿 — 实现 ArchiveExtractor（使用标准库 zipfile/tarfile）
- [ ] Subtask 6.3: 🔄 重构 — 优化解压代码

**完成标准/Definition of Done:**
- [ ] ArchiveExtractor 实现 zip/tar 解压
- [ ] 格式过滤正确（跳过不支持的格式）
- [ ] 安全防护完整（压缩炸弹、路径穿越）
- [ ] 嵌套解压最多 3 层
- [ ] 所有 TDD 循环测试通过

---

### Task 7: API 路由实现

**关联 AC:** AC-1~6

#### TDD 循环 A：文档上传 API 路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_document_upload_routes.py`（POST 单文件、POST 批量、分片上传端点、GET 确认、认证校验） |
| 🟢 绿 | 实现 `src/interfaces/api/document_upload.py`（FastAPI 路由） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 7.1: 🔴 红 — 编写 API 路由失败测试（单文件上传、批量上传、分片上传、确认查询、错误处理）
- [ ] Subtask 7.2: 🟢 绿 — 实现文档上传 FastAPI 路由（multipart/form-data 处理，依赖注入 DocumentUploadService）
- [ ] Subtask 7.3: 🔄 重构 — 优化 API 路由代码
- [ ] Subtask 7.4: 注册路由至 `src/interfaces/api/app.py`

> **注：** CLI 上传命令（`sisys document upload --file`）推迟至 Epic 7 Story 7.1（CLI 命令接口），届时调用已实现的 DocumentUploadService。

**完成标准/Definition of Done:**
- [ ] API 路由实现完成（POST/GET 端点）
- [ ] 所有端点通过认证中间件
- [ ] 所有 TDD 循环测试通过
- [ ] 接口层覆盖率 ≥85%

---

### Task 8: 集成测试

**关联 AC:** AC-1~6

#### 集成测试实现

- [ ] Subtask 8.1: 创建 `tests/integration/test_document_upload_integration.py`
- [ ] Subtask 8.2: 实现完整上传流程集成测试（API → Service → MinIO → PG → 事件发布）
- [ ] Subtask 8.3: 实现分片上传集成测试（大文件分片 → 断点续传 → 合并）
- [ ] Subtask 8.4: 实现批量上传集成测试（并发上传 → 部分失败处理）
- [ ] Subtask 8.5: 实现压缩包上传集成测试（zip/tar → 内部文件入库）
- [ ] Subtask 8.6: 实现跨租户隔离集成测试

**完成标准/Definition of Done:**
- [ ] 所有集成测试通过
- [ ] 集成测试覆盖率 ≥70%
- [ ] 并行测试 `pytest tests/ -n 8` 通过

---

### Task 9: SDD 架构约束验证测试

**关联 AC:** AC-1~6

> **性质说明：** SDD 规范验证测试（验证架构/约束是否被遵守）。

- [ ] Subtask 9.1: 创建 `tests/unit/architecture/test_arch_document_upload.py`
- [ ] Subtask 9.2: 验证 domain 层零外部依赖（import-linter 规则）
- [ ] Subtask 9.3: 验证依赖方向正确（interfaces → application → domain, infrastructure → application → domain）
- [ ] Subtask 9.4: 验证端口注册完整性（registry 中 document_repository 存在且版本正确）
- [ ] Subtask 9.5: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-1~6

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_document_upload.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_document_upload.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 10.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 10.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单
- [ ] Subtask 10.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 10.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] 测试完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Hexagonal / Ports & Adapters），严格四层分层
- **设计约束:** 领域层零依赖（import-linter 强制校验），依赖方向 domain ← application ← interfaces/infrastructure
- **接口治理:** 统一端口注册（`PortSpec` 元数据）、`Registry`/`Resolver`/`ContractGate`、`Composition Root` 装配
- **技术栈:** Python 3.11+ / FastAPI 0.111+ / Pydantic 2.4+ / SQLAlchemy 2.0+（async）/ MinIO / PostgreSQL 15+ / Redis 7.0+

### 关键架构决策

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **MinIO 对象存储（已选）** | 版本控制、WORM、分片上传、S3 兼容 | 需额外部署 MinIO 服务 | ✅ 9/10 |
| PostgreSQL 文档元数据 | JSONB 灵活元数据、pgvector 向量 | 需处理大表性能 | ✅ 8/10 |
| Redis 分片上传状态 | TTL 自动清理、高性能 | 分片状态可能丢失（可接受） | ✅ 8/10 |

### 已有代码复用清单

> ⚠️ **以下组件已存在，禁止重复实现，必须复用：**

| 组件 | 路径 | 用途 |
|------|------|------|
| `Document` 实体 | `src/domain/entities/document.py` | 扩展字段（tenant_id, uploaded_by） |
| `DocumentProcessed` 事件 | `src/domain/events/document_events.py` | 参考，新增 `DocumentUploaded`（不同生命周期阶段） |
| `L4ObjectPort` | `src/domain/ports/l4_object.py` | 底层对象存储接口 |
| `DocumentStoragePort` | `src/application/ports/document_storage_port.py` | `store_document()` 方法 |
| `MinIODocumentStorage` | `src/infrastructure/storage/minio/minio_document_storage.py` | MinIO 文档存储实现 |
| `MinIOAdapter` | `src/infrastructure/storage/minio/minio_adapter.py` | MinIO S3 适配器 |
| `ObjectOperations` | `src/infrastructure/storage/minio/object_operations.py` | 分片上传逻辑（`calculate_part_size()` + `resume_multipart_upload()`） |
| `MinIOConfig` | `src/infrastructure/config/minio.py` | MinIO 配置 |
| `PortSpec` / `PortRegistry` | `src/domain/ports/registry.py` | 端口注册中心 |
| `DomainEvent` 基类 | `src/domain/events/base.py` | 事件基类（自动注册、序列化） |
| `EventPublisher` | `src/domain/ports/event_publisher.py` | 事件发布端口 |
| `DualChannelEventBus` | `src/infrastructure/messaging/` | 双通道事件发布 |
| `TestTenant` | `tests/isolation.py` | UUID 前缀租户隔离 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   └── document.py                      # [已有] 扩展 tenant_id/uploaded_by
│   ├── events/
│   │   └── document_events.py               # [已有] 新增 DocumentUploaded 事件
│   ├── ports/
│   │   ├── registry.py                      # [已有] 注册新端口
│   │   ├── resolver.py                      # [已有] 解析新端口
│   │   ├── contract_gate.py                 # [已有] 契约门禁
│   │   └── document_repository.py           # [新建] DocumentRepositoryPort Protocol
│   └── value_objects/
│       ├── document_format.py               # [新建] 17 种格式 MIME 映射
│       └── upload_limits.py                 # [新建] 上传限制常量
├── application/
│   ├── ports/
│   │   └── document_storage_port.py         # [已有] DocumentStoragePort
│   ├── services/
│   │   └── document_upload_service.py       # [新建] 上传编排服务（非端口，直接服务注册）
│   └── use_cases/
│       └── document_processing.py           # [已有，骨架] 上传完成后触发解析
├── infrastructure/
│   ├── storage/
│   │   ├── minio/                           # [已有] MinIO 文档存储
│   │   │   ├── minio_document_storage.py    # [已有] MinIODocumentStorage
│   │   │   ├── minio_adapter.py             # [已有] MinIOAdapter
│   │   │   ├── object_operations.py         # [已有] 分片上传逻辑（calculate_part_size + resume_multipart_upload）
│   │   │   └── minio_repository.py          # [已有] MinIO 仓储外观
│   │   ├── postgresql/
│   │   │   └── document_repository.py       # [新建] PostgresDocumentRepository
│   │   └── redis/
│   │       └── chunked_upload_manager.py    # [新建] 分片上传状态管理（通过 L1CachePort 操作 Redis）
│   ├── external_services/
│   │   └── archive_extractor.py             # [新建] 压缩包解压
│   └── config/
│       └── minio.py                         # [已有] MinIOConfig
├── interfaces/
│   └── api/
│       ├── document_upload.py               # [新建] FastAPI 上传路由
│       └── app.py                           # [已有] 注册新路由
└── composition_root.py                      # [已有] 注册新端口和服务

tests/
├── unit/
│   ├── domain/
│   │   ├── entities/test_document.py        # [已有，扩展] 新增字段测试
│   │   ├── events/test_document_uploaded.py # [新建]
│   │   ├── ports/test_document_repository.py # [新建]
│   │   └── value_objects/
│   │       ├── test_document_format.py      # [新建]
│   │       └── test_upload_limits.py        # [新建]
│   ├── application/
│   │   └── services/
│   │       └── test_document_upload_service.py # [新建]
│   ├── infrastructure/
│   │   ├── storage/
│   │   │   ├── postgresql/test_document_repository.py # [新建]
│   │   │   └── redis/test_chunked_upload_manager.py   # [新建]
│   │   └── external_services/test_archive_extractor.py   # [新建]
│   ├── interfaces/
│   │   └── api/test_document_upload_routes.py  # [新建]
│   └── architecture/test_arch_document_upload.py # [新建]
├── integration/
│   └── test_document_upload_integration.py     # [新建]
├── contracts/
│   ├── test_api_contract_document_upload.py    # [新建]
│   └── test_port_contract_document_upload.py   # [新建]
└── acceptance/
    ├── test_acceptance_document_upload.feature  # [新建]
    └── test_acceptance_document_upload.py       # [新建]
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1-19-cost-metrics-basic](./1-19-cost-metrics-basic.md) — Epic 1 最后一个 Story

**关键学习/Key Learnings:**
- 事件扩展必须保持向后兼容（新字段提供默认值 0/None）
- DI 注册时 impl 字符串延迟加载，拼写错误不会立即报错，需测试覆盖
- composition_root.py 注册顺序影响依赖解析，确保被依赖的端口先注册
- frozen dataclass 不可变，事件字段必须有默认值或通过 `__post_init__` 设置
- `TestTenant` UUID 前缀隔离是并行测试的基础，新端口测试也必须使用

**应用到本故事/Applied to This Story:**
- [ ] Document 实体新增字段提供默认值（向后兼容）
- [ ] DocumentUploaded 事件所有字段设置合理默认值
- [ ] 端口 impl 字符串拼写检查纳入契约测试
- [ ] 集成测试使用 `TestTenant` 进行租户隔离

### Story 1-7 MinIO 学习经验

**来源:** [Story 1-7-minio-object-layer](./1-7-minio-object-layer.md) — MinIO 存储层实现

**关键学习/Key Learnings:**
- 流式上传防止 OOM：`upload_object` 接受 `file_path` 或 `AsyncIterator[bytes]`，不接受全量 `bytes`
- 分片上传逻辑已在 `MinIORepository` 中实现，应用层只需编排
- `BucketManager` 负责桶命名规范验证
- Redis 断点续传状态 TTL 24 小时
- WORM 存储 Object Lock COMPLIANCE 模式，7 年保留

**应用到本故事/Applied to This Story:**
- [ ] 复用 `ObjectOperations` 分片上传实现（`calculate_part_size()` + `resume_multipart_upload()`），不在应用层重复
- [ ] 断点续传状态存 Redis，TTL 24 小时
- [ ] 上传文件流式处理，禁止全量 `bytes` 加载

### 实现细节补充 Implementation Details

**FastAPI 配置：**
- 请求体大小限制：`app.add_middleware(MultipartBodySizeLimit, max_body_size=20*1024*1024*1024)` 或在 nginx/uvicorn 层配置
- multipart 字段名：单文件 `file: UploadFile`，批量 `files: list[UploadFile]`
- 分片上传字段名：`part: UploadFile`，分片元数据通过请求体 JSON 传递

**认证与上下文：**
- API 认证：JWT（OAuth 2.1），通过认证中间件自动注入 `user_id` 和 `tenant_id`
- 从请求上下文（`request.state.user_id` / `request.state.tenant_id`）获取用户信息
- 权限检查：RBAC 中间件校验 `document:upload` 权限

**PostgreSQL 租户隔离：**
- 沿用项目 `Schema per Tenant` 模式（`TestTenant.postgres_schema`），documents 表创建在各租户 schema 下
- Alembic migration 需支持模板化 schema（参考已有 migration 模式）

**事件发布机制：**
- 通过 Outbox 模式异步发布（写入 event_outbox 表，由后台 worker 投递至 Redis + RabbitMQ 双通道）
- DocumentUploadService 调用 `EventPublisher.publish(event)` → 写入 Outbox → 确认事务提交 → 后台投递

**分片上传流程：**
1. `POST /chunked/init` — 返回 `upload_id` + 推荐分片大小（从 `UploadLimits.get_chunk_size(file_size)` 计算）
2. `PUT /chunked/{upload_id}/parts/{part_number}` — 上传分片，返回 ETag
3. `POST /chunked/{upload_id}/complete` — 合并分片，创建 Document 实体，发布事件

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | [模型名称] |
| **Version** | create-story workflow v2.7.0 |
| **Execution Date** | 2026-05-29 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **PRD** | `_bmad-output/planning-artifacts/prd.md` |
| **UX 设计** | `_bmad-output/planning-artifacts/ux-design-specification.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-19-cost-metrics-basic.md` |
| **MinIO Story** | `_bmad-output/implementation-artifacts/stories/1-7-minio-object-layer.md` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（Story 1-19 + Story 1-7）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有代码复用清单编制
- [x] 端口契约清单制定

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-1-document-upload-17-formats.md`

**待创建的文件/To Be Created (Dev Story 实施):**

领域层（新建）:
- `src/domain/value_objects/document_format.py` — 17 种格式 MIME 映射
- `src/domain/value_objects/upload_limits.py` — 上传限制常量
- `src/domain/ports/document_repository.py` — DocumentRepositoryPort Protocol

领域层（修改）:
- `src/domain/entities/document.py` — 扩展 tenant_id/uploaded_by
- `src/domain/events/document_events.py` — 新增 DocumentUploaded 事件

应用层（新建）:
- `src/application/services/document_upload_service.py` — 上传编排服务（非端口）

基础设施层（新建）:
- `src/infrastructure/storage/postgresql/document_repository.py` — PostgresDocumentRepository
- `src/infrastructure/storage/redis/chunked_upload_manager.py` — 分片上传状态管理
- `src/infrastructure/external_services/archive_extractor.py` — 压缩包解压

接口层（新建）:
- `src/interfaces/api/document_upload.py` — FastAPI 上传路由

配置（修改）:
- `src/composition_root.py` — 注册新端口和服务
- `configs/event_channels.yaml` — 新增 DocumentUploaded 事件通道
- `deploy/postgresql/alembic/versions/` — 新增 documents 表 migration

测试文件（新建）:
- `tests/unit/domain/value_objects/test_document_format.py`
- `tests/unit/domain/value_objects/test_upload_limits.py`
- `tests/unit/domain/events/test_document_uploaded.py`
- `tests/unit/domain/ports/test_document_repository.py`
- `tests/unit/application/services/test_document_upload_service.py`
- `tests/unit/infrastructure/storage/postgresql/test_document_repository.py`
- `tests/unit/infrastructure/storage/redis/test_chunked_upload_manager.py`
- `tests/unit/infrastructure/external_services/test_archive_extractor.py`
- `tests/unit/interfaces/api/test_document_upload_routes.py`
- `tests/unit/architecture/test_arch_document_upload.py`
- `tests/integration/test_document_upload_integration.py`
- `tests/contracts/test_api_contract_document_upload.py`
- `tests/contracts/test_port_contract_document_upload.py`
- `tests/acceptance/test_acceptance_document_upload.feature`
- `tests/acceptance/test_acceptance_document_upload.py`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.1 |
| **Story Key** | 2-1-document-upload-17-formats |
| **File** | `_bmad-output/implementation-artifacts/stories/2-1-document-upload-17-formats.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0-1（Epic 2 第一个 Story，文档处理流水线入口） |
| **覆盖 FR** | FR-DM-01（17 种格式上传） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（11 个 Task，Task 0-10）
2. [x] All acceptance criteria specified 所有验收标准已定义（6 个 AC）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

---

### 🔧 文档审查修复 Docs Review Fixes

> 第1轮审查修订（2026-05-29）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | AC-1 验证标准 markdown/md 重复计数 | P0 | 统一为 "markdown（含 .md 扩展名）"，明确 15+2=17 |
| 2 | content_hash/find_by_content_hash 秒传超出 FR-DM-01 范围 | P0 | 移除秒传功能，从实体/端口/Task 中全面删除 |
| 3 | DocumentUploadPort 混合业务与技术接口 | P0 | 移除该端口，DocumentUploadService 直接作为服务注册 |
| 4 | ChunkedUploadManager 放在 application 层违反依赖规则 | P0 | 下移至 infrastructure/storage/redis/ |
| 5 | EventPublisherPort 命名错误 | P0 | 修正为 EventPublisher |
| 6 | MinIORepository 分片逻辑引用不准确 | P0 | 修正为 ObjectOperations |
| 7 | AC-6 查询 API 范围蔓延 | P1 | 精简为仅上传结果确认，列表查询推迟 |
| 8 | CLI 命令属于 Epic 7 范围 | P1 | 移除 CLI 相关 Subtask，推迟至 Epic 7 |
| 9 | 压缩炸弹阈值 50GB 无依据 | P1 | 修正为 ≤20GB（与批量上传限制一致）+ 10:1 膨胀比 |
| 10 | 缺少 PG 索引策略 | P1 | Task 3 增加 Subtask 3.5 索引创建 |
| 11 | DocumentRepository 命名不一致 | P1 | 统一为 DocumentRepositoryPort |

> 第2轮审查修订（2026-05-29）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 12 | 格式计数14+2=16≠17，缺少1种文档格式 | P0 | 新增 rtf 格式，达到 15+2=17 |
| 13 | content_hash 残留（测试分类表第278行） | P0 | 修正为 tenant_id/uploaded_by |
| 14 | document_upload_port 残留（Task 9 Subtask 9.4） | P0 | 移除引用 |
| 15 | CLI 残留（项目结构、AC-1 When 语句） | P1 | 清除所有 CLI 引用 |
| 16 | 测试分类表缺 Task 3 和 Task 10 行 | P1 | 补充缺失行 |
| 17 | Completion Summary Task 数量错误（10→11） | P1 | 修正为 11 个 Task |

---

**故事版本/Story Version:** v0.0.4
**创建日期/Created:** 2026-05-29
**最后更新/Last Updated:** 2026-05-29
**更新说明/Description:**
- v0.0.4: 第5轮终审 — 追溯矩阵补齐Task 0/10行、or.md公理追溯补充rtf说明
- v0.0.3: 第2轮审查修订 — 修复残留不一致（格式计数/幽灵条目/测试表缺失/CLI残留/content_hash残留）
- v0.0.2: 第1轮审查修订 — 修复 P0 格式计数/秒传范围蔓延/架构层级违规/命名错误，P1 CLI/查询范围修正/索引策略
- v0.0.1: 创建故事文件
