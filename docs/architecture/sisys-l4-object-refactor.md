# SISYS L4 对象存储层重构详细设计

**版本：** v1.3
**日期：** 2026-05-13
**状态：** 设计完成（代码未执行，需重新审查）
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

### 0.3 架构审查修正（v1.1 → v1.2）

**审查发现以下 P0 阻断问题，已在设计中修正。代码实际执行状态待更新：**

| 问题 | 描述 | 修正方案 | 代码状态 |
|------|------|---------|---------|
| P0-1 | `MinIOAdapter.archive()` 未处理 content 参数 | 明确 content 必须为 None，否则抛出 NotImplementedError | ❌ 未执行 |
| P0-2 | `MinIOAdapter` 缺失 `list_objects` 方法 | 添加 `list_objects()` 方法，委托 `MinIORepository` | ❌ 未执行 |
| P0-3 | `MinIORepository.archive()` 返回 `bool` 而非 `str` | 修改返回类型为 `str` | ❌ 未执行 |

**代码执行状态：**
- ⚠️ `MinIOAdapter.archive()` 仍透传 content 参数，会导致 TypeError
- ⚠️ `MinIOAdapter.list_objects()` 方法缺失
- ⚠️ `MinIORepository` 仍实现 `ObjectStorageRepository`，未迁移到 `L4ObjectPort`
- ⚠️ `DocumentStoragePort` 和 `MinIODocumentStorage` 文件不存在

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

| 问题 | 描述 | 影响 | 优先级 |
|------|------|------|--------|
| P1 | `ObjectStorageRepository` 和 `L4ObjectPort` 两个抽象并存 | 维护成本增加，职责不清 | P1 |
| P2 | 缺少应用层具体端口（Layer 2） | 无法满足特定业务场景语义 | P1 |
| P3 | `L4ObjectPort` 的 `list_objects` 缺少 `bucket_type` 参数 | 与实现不一致 | P1 |
| P4 | `MinIOAdapter.archive()` 未处理 content 参数 | content 被静默丢弃，语义矛盾：设计文档描述"归档对象（带 WORM retention）"，但实际只设置 retention 策略，不上传任何对象数据 | P0 |
| P5 | `MinIOAdapter` 缺失 `list_objects` 方法 | 调用会抛出 AttributeError，破坏 L4ObjectPort 协议完整性 | P0 |
| P6 | `MinIORepository.archive()` 返回 `bool` 而非 `str` | 与 L4ObjectPort 定义不一致，导致类型不匹配 | P0 |

### 1.5 archive() 方法语义矛盾（新增）

**调用链分析：**

```
L4ObjectPort.archive(content=bytes)
    → MinIOAdapter.archive(content=bytes)  # 收到 content，但设计文档说"仅用于接口兼容性"
        → self._repository.archive(...)     # content 参数被静默丢弃
            → MinIORepository.archive(retention_days)  # 无 content 参数
                → WORMManager.archive_object(...) # 根本没有 content 参数
                    → enable_worm_lock(...)       # 只有 retention，没有数据上传
```

**关键发现：**
- `L4ObjectPort.archive()` 声明支持 `content: bytes | None` 参数，暗示可以直接上传内容并设置 WORM retention
- 但整个实现链路（MinIOAdapter → MinIORepository → WORMManager）完全没有处理 content 上传
- `WORMManager.archive_object()` 实际上只是调用 `enable_worm_lock()` 设置 retention 元数据，没有 put_object 操作
- **这意味着 `content` 参数在当前架构下根本无法使用**，传入 content 会导致数据丢失

**修正方案选择：**

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A | 保持现状，明确文档说明 content 必须为 None | 改动最小 | 接口语义与实现不符 |
| B | 修改 MinIOAdapter.archive()，当 content != None 时抛出 NotImplementedError | 明确接口约束，防止静默数据丢失 | 需要修改接口契约 |
| C | 完整实现 content 上传 + WORM retention（需要较大架构变更） | 功能完整 | 工作量大，超出本次重构范围 |

**设计文档推荐方案 B**：在 MinIOAdapter.archive() 开头检查 content != None 并抛出 NotImplementedError。

### 1.6 测试覆盖缺陷（Round 2 深化）

| 测试 | 问题 | 影响 |
|------|------|------|
| `test_archive_with_content` | 未验证 content 参数是否传递到 repository | 无法捕获"content 被静默丢弃"的 bug |
| `MinIOAdapter.list_objects` | 无测试 | 接口缺失未被测试发现 |
| `test_l4_object_port.py` | list_objects 方法未覆盖 | Protocol 测试不完整 |
| `test_list_objects_delegates` | 无测试 | 无法验证 MinIOAdapter.list_objects 委托正确性 |
| **Acceptance 测试** | **直接调用 MinIORepository，跳过 MinIOAdapter** | 适配器层错误无法被发现 |
| **所有 then 步骤** | **全部为 `pass`，无实质断言** | 即使实现完全错误测试也通过 |

**Acceptance 测试问题详解：**
- `tests/acceptance/test_story_1_7_steps.py` 直接调用 `minio_repository.archive()` 而非通过 `MinIOAdapter`
- AC-8/AC-4 的 `verify_object_lock_enabled` 等验证步骤只有 `pass`
- 无法验证 Object Lock 是否真正启用

### 1.7 WORMManager archive_object 实现问题（Round 2 新增）

**实现现状：**
```python
def archive_object(self, bucket_name, object_key, retention_days) -> bool:
    return self.enable_worm_lock(...)  # 薄包装

def enable_worm_lock(...) -> bool:
    client.set_object_retention(bucket_name, object_key, retention)
    return True  # 无条件返回 True，无任何失败路径
```

| 问题 | 描述 |
|------|------|
| 返回值恒 True | 成功时返回 True，失败时抛异常，永远不会返回 False |
| 无 ETag 返回 | `set_object_retention` 是 PUT 操作，不返回响应体 |
| 无实际校验 | 设置 WORM 锁后没有验证是否真正生效 |

**archive_object 实现问题：**
- `archive_object()` 只是 `enable_worm_lock()` 的薄包装，不上传任何数据
- `enable_worm_lock()` 调用 `set_object_retention` 返回值恒为 True（成功）或抛异常（失败），无失败路径
- 无 ETag 返回，无法返回有意义的 `str`（L4ObjectPort.archive 返回类型要求）
- **因此 P0-3 修复需要在 WORMManager 层获取 stat_object 的 ETag**

**修复建议：**
```python
def archive_object(self, bucket_name, object_key, retention_days) -> str:
    # 获取对象元数据以返回 ETag
    stat = self._client.client.stat_object(bucket_name, object_key)
    self.enable_worm_lock(bucket_name, object_key, retention_days)
    return stat.etag  # 返回实际 ETag 而非 dict
```

### 1.8 Protocol 类型检查局限性（Round 2 新增）

| 问题 | 描述 |
|------|------|
| 不强制完整性 | Protocol 是结构化子类型，不检查是否实现所有方法 |
| 隐式缺失 | `list_objects` 缺失不会被编译时检测，除非调用方实际调用 |
| cast 掩盖问题 | `cast("str", ...)` 是纯类型注解，运行时不转换，掩盖了 `bool` 转 `str` 的问题 |

### 1.9 架构一致性完整分析（Round 4 汇总）

#### 1.9.1 接口签名对比

| 方法 | L4ObjectPort | ObjectStorageRepository | MinIOAdapter | MinIORepository |
|------|-------------|------------------------|--------------|-----------------|
| store | ✅ 匹配 | ✅ 匹配 | ✅ | ✅ |
| retrieve | ✅ 匹配 | ✅ 匹配 | ✅ | ✅ |
| delete | ✅ 匹配 | ✅ 匹配 | ✅ | ✅ |
| get_metadata | ✅ 匹配 | ✅ 匹配 | ✅ | ✅ |
| archive | ❌ **content 参数丢失** | ❌ 无 content | ❌ **content 未传递** | ❌ **返回 bool** |
| list_objects | ✅ 有定义 | ✅ 匹配 | ❌ **缺失实现** | ✅ 已实现 |

#### 1.7.2 委托链问题汇总

```
L4ObjectPort (Protocol)
    ↓ 实现
MinIOAdapter
    ↓ 委托 ⚠️ 问题
MinIORepository (实现 ObjectStorageRepository)
    ↓ 组合
BucketManager / ObjectOperations / WORMManager
```

**委托链问题：**
1. `archive`: MinIOAdapter 接收 content 但丢弃，MinIORepository 返回 bool 而非 str
2. `list_objects`: MinIOAdapter 完全缺失该方法，破坏 L4ObjectPort 协议完整性

#### 1.7.3 验收测试覆盖分析

| L4ObjectPort 方法 | 单元测试 | Acceptance 测试 | 覆盖评估 |
|-------------------|---------|----------------|---------|
| store | ✅ | AC-2 | ✅ 已覆盖 |
| retrieve | ✅ | AC-3 | ⚠️ 触发但无验证 |
| delete | ✅ | AC-4 | ⚠️ 仅错误路径 |
| get_metadata | ✅ | **无** | ❌ 未覆盖 |
| archive | ✅ | AC-4, AC-8 | ⚠️ 流程存在但无验证 |
| list_objects | ❌ | **无** | ❌ 完全未覆盖 |

**AC-5/6/7 空实现问题：** 分片上传、断点续传、生命周期规则测试只有 `pass`，里程碑测试未完成。

### 1.10 两个 archive 接口并存的架构问题（Round 3 新增）

**发现：存在两个完全不同的 archive 方法**

| 接口 | 定义位置 | 签名 |
|------|---------|------|
| `L4ObjectPort.archive()` | `src/domain/ports/l4_object.py:96` | `(bucket_type, object_key, content: bytes\|None, retention_days) → str` |
| `ObjectStorageRepository.archive()` | `src/domain/ports/storage.py:116` | `(bucket_type, object_key, retention_days) → bool` |
| `WORMManager.archive_object()` | `worm_lifecycle.py:108` | `(bucket_name, object_key, retention_days) → bool` |

**关键差异：**
1. `L4ObjectPort` 有 `content` 参数，返回 `str`
2. `ObjectStorageRepository` 无 `content` 参数，返回 `bool`
3. 审计服务直接调用 `WORMManager.archive_object()`，不经过任何 Port

**审计服务调用链（不走 L4ObjectPort）：**
```
AuditServiceImpl.archive()
    → self._worm_manager.archive_object()  # 直接调用，不经过 repository
    → enable_worm_lock()
```

**这意味着：**
- L4ObjectPort.archive() 的 content 参数对审计服务完全不可用
- 删除 ObjectStorageRepository 后，审计服务可以继续正常工作（因为它直接用 WORMManager）

### 1.11 删除 ObjectStorageRepository 的实际影响（Round 3 新增）

**实际风险评估：**

| 风险项 | 级别 | 说明 |
|--------|------|------|
| MinIORepository 无法实例化 | 高 | 失去基类，需要改为继承 L4ObjectPort |
| 测试 test_compliance_lock_error 失败 | 低 | ComplianceLockError 已迁移至 exceptions 模块 |
| 调用方破坏 | 低 | UnifiedStorageGateway 用 L4ObjectPort，不受影响 |

**关键发现：接口签名不兼容**

ObjectStorageRepository.archive() 和 L4ObjectPort.archive() 签名不同：
- L4ObjectPort 多 `content: bytes | None` 参数
- L4ObjectPort 返回 `str`，ObjectStorageRepository 返回 `bool`

MinIOAdapter 实现 L4ObjectPort，但调用的是实现 ObjectStorageRepository 的 MinIORepository。

**迁移最小改动范围：**

| 文件 | 改动 |
|------|------|
| `minio_repository.py` | 改继承 L4ObjectPort，修改 archive 签名返回 str |
| `minio_adapter.py` | 添加 list_objects，archive 中检查 content |
| `storage.py` | 删除 |
| `test_storage_architecture.py` | 修改 ComplianceLockError import |

### 1.12 委托矩阵详细分析（Round 3 汇总）

| 方法 | L4ObjectPort | MinIOAdapter | MinIORepository | 委托状态 |
|------|-------------|--------------|-----------------|---------|
| store | ✅ 完整签名 | ✅ 完整委托 | ✅ 正确实现 | **正确** |
| retrieve | ✅ 完整签名 | ✅ 完整委托 | ✅ 正确实现 | **正确** |
| delete | ✅ 完整签名 | ✅ 完整委托 | ✅ 正确实现 | **正确** |
| get_metadata | ✅ 完整签名 | ✅ 完整委托 | ✅ 正确实现 | **正确** |
| archive | ❌ content 参数丢失 | ❌ cast 掩盖 bool→str | ❌ 返回 bool 而非 str | **错误 P0** |
| list_objects | ✅ 完整签名 | ❌ **方法完全缺失** | ✅ 正确实现 | **错误 P0** |

**为什么 store/delete/get_metadata 正确，但 archive/list_objects 有问题：**
- store/delete/get_metadata：L4ObjectPort 和 ObjectStorageRepository 签名完全一致，MinIOAdapter 简单透传正确
- archive：设计文档想支持 content，但实现链路不支持，且返回类型不一致
- list_objects：MinIOAdapter 实现时遗漏，MinIORepository 有实现但适配器层断链

#### 1.7.4 关键结论

1. **Protocol 实现滞后**：MinIOAdapter 漏实现了 `list_objects`，导致 L4ObjectPort 协议不完整
2. **archive 语义断裂**：content 参数在调用链中完全未被处理，导致数据丢失
3. **类型系统失效**：MinIOAdapter 用 `cast("str", ...)` 掩盖了 MinIORepository 返回 bool 的问题
4. **测试覆盖不足**：6 个方法中 3 个无实质验证，1 个完全未覆盖

---

## 2. 目标架构

### 2.1 四层职责模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Layer - L4ObjectPort（统一抽象对象存储端口）      │
│                                                                  │
│  职责：定义最底层通用对象存储接口                                  │
│        (store/retrieve/delete/archive/list_objects)             │
│  位置：src/domain/ports/l4_object.py                             │
│  特点：领域层零依赖，纯抽象协议，技术无关                           │
│        （可使用 MinIO/S3/Azure Blob 等实现）                      │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Application Layer - 具体应用对象存储端口                │
│                                                                  │
│  职责：继承 L4ObjectPort，定义特定业务场景语义                     │
│  位置：src/application/ports/                                     │
│  端口：                                                          │
│    - DocumentStoragePort(L4ObjectPort, ...) (文档存储) ← 本次新增 │
│    - AvatarStoragePort(L4ObjectPort, ...) (头像存储) ← 未来扩展   │
│    - BackupArchivePort(L4ObjectPort, ...) (备份归档) ← 未来扩展   │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - 对象存储技术实现 + 存储管理             │
│                                                                  │
│  职责：实现 L4ObjectPort 接口 + 连接池统一管理                     │
│  位置：src/infrastructure/storage/minio/                          │
│  组件：                                                          │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  MinIOAdapter (L4ObjectPort 实现)                        │  │
│    │  职责：薄适配器层，委托 MinIORepository 处理所有操作      │  │
│    │  特点：技术可替换（未来可新增 S3Adapter 等）              │  │
│    └─────────────────────────────────────────────────────────┘  │
│                              ↑                                   │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  MinIORepository (实现 L4ObjectPort)                    │  │
│    │  职责：组合分层组件，对外提供统一仓储接口                 │  │
│    └─────────────────────────────────────────────────────────┘  │
│                              ↑                                   │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  分层组件（存储管理 + 技术实现）                         │  │
│    │  ┌────────────────┐ ┌────────────────┐ ┌────────────┐  │  │
│    │  │ MinioClient    │ │ BucketManager  │ │  WORM      │  │  │
│    │  │ Adapter        │ │                │ │  Manager   │  │  │
│    │  │ ─ 连接池管理    │ │ ─ Bucket CRUD  │ │ ─ 合规锁定 │  │  │
│    │  │ ─ S3错误映射    │ │ ─ 命名验证     │ │ ─ 生命周期 │  │  │
│    │  │ ─ 健康检查      │ │ ─ WORM配置     │ │            │  │  │
│    │  └────────────────┘ └────────────────┘ └────────────┘  │  │
│    │                         ┌────────────────┐           │  │
│    │                         │ Object         │           │  │
│    │                         │ Operations     │           │  │
│    │                         │ ─ 流式上传/下载 │           │  │
│    │                         │ ─ 分片上传      │           │  │
│    │                         │ ─ 断点续传      │           │  │
│    │                         └────────────────┘           │  │
│    └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - 具体应用对象存储端口实现                │
│                                                                  │
│  职责：实现具体应用存储端口，提供业务语义                          │
│  位置：src/infrastructure/storage/minio/                          │
│  组件：                                                          │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  MinIODocumentStorage (DocumentStoragePort 实现)        │  │
│    │  职责：组合 MinIOAdapter，实现文档业务语义              │  │
│    │  能力：                                                 │  │
│    │    - 自动路径生成 (documents/{user_id}/{type}/YYYY-MM) │  │
│    │    - 文档元数据管理                                     │  │
│    │    - 用户文档列表                                       │  │
│    │  特点：复用 MinIOAdapter 的底层存储能力                │  │
│    └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 基础设施层存储管理详解

Layer 3 是整个 L4 存储架构的核心，包含 **技术适配层** 和 **存储管理层** 两个子层：

#### 2.2.1 技术适配层

```
MinioClientAdapter
├── 职责：封装 MinIO Python SDK，提供统一的客户端接口
├── 能力：
│   ├── 连接池管理（懒加载，每次创建新客户端实例）
│   ├── S3 错误映射（S3Error → 领域异常）
│   └── 健康检查（list_buckets）
└── 特点：各组件独立 _get_client()，不引入全局连接池
```

#### 2.2.2 存储管理层

**BucketManager — Bucket 生命周期管理**
```
├── 职责：Bucket 的创建、删除、存在性检查及命名验证
├── 能力：
│   ├── validate_bucket_name() — 命名规范验证（{prefix}-{type}-{tenant_id}）
│   ├── build_bucket_name() — 构建完整 Bucket 名称
│   ├── create_bucket() — 创建 Bucket（支持 versioning/object_lock）
│   ├── enable_object_lock() — 启用 WORM 对象锁定
│   ├── delete_bucket() — 删除 Bucket（支持强制清空）
│   ├── bucket_exists() — 检查 Bucket 是否存在
│   └── list_buckets() — 列出所有 Bucket
└── 依赖：MinioClientAdapter
```

**ObjectOperations — 对象读写操作**
```
├── 职责：对象的流式上传/下载、元数据查询、分片上传
├── 能力：
│   ├── upload_object() — 自动分片（<100MB 不分片，>100MB 分片）
│   │   ├── <100MB: 单次上传 (fput_object)
│   │   ├── 100MB-1GB: 10MB 分片
│   │   ├── 1GB-10GB: 50MB 分片
│   │   └── >10GB: 100MB 分片
│   ├── download_object() — 流式下载，防 OOM
│   ├── get_object_metadata() — 获取对象元数据
│   ├── delete_object() — 删除对象
│   ├── resume_multipart_upload() — 断点续传（Redis 状态持久化）
│   └── save_multipart_state() — 分片上传状态保存
└── 依赖：MinioClientAdapter
```

**WORMManager — 合规与生命周期管理**
```
├── 职责：WORM 锁定、对象归档、生命周期配置
├── 能力：
│   ├── enable_worm_lock() — 设置 Governance 模式保留策略
│   ├── archive_object() — 归档至 WORM 存储（2555 天 = 7 年）
│   ├── delete_object() — 删除对象（WORM 锁定抛出 ComplianceLockError）
│   ├── get_object_retention() — 获取对象保留策略
│   ├── configure_lifecycle() — 配置 Bucket 生命周期规则
│   └── list_lifecycle_rules() — 列出生命周期规则
└── 依赖：MinioClientAdapter
```

#### 2.2.3 分层设计原则

| 原则 | 说明 |
|------|------|
| **单一职责** | 每个组件只负责一个领域（Bucket/Object/WORM） |
| **依赖注入** | 各组件接受 MinioClientAdapter，不自行创建 |
| **委托模式** | MinIORepository 组合各组件，对外提供统一接口 |
| **可测试性** | 各组件可独立测试，Mock MinioClientAdapter |

### 2.3 接口继承关系

```python
# Layer 1: Domain 统一抽象
class L4ObjectPort(Protocol):
    """L4 对象存储接口 - 最底层抽象"""
    async def store(self, bucket_type: str, object_key: str, file_path: str,
                   content_type: str, tags: dict[str, str] | None = None) -> str: ...
    def retrieve(self, bucket_type: str, object_key: str,
                version_id: str | None = None) -> AsyncIterator[bytes]: ...
    async def delete(self, bucket_type: str, object_key: str,
                    version_id: str | None = None) -> bool: ...
    async def get_metadata(self, bucket_type: str, object_key: str,
                          version_id: str | None = None) -> dict: ...
    async def archive(self, bucket_type: str, object_key: str,
                      content: bytes | None = None, retention_days: int = 2555) -> str: ...
    async def list_objects(self, bucket_type: str, prefix: str = "",
                          recursive: bool = True) -> list[dict]: ...

# Layer 2: Application 具体应用端口
class DocumentStoragePort(L4ObjectPort, Protocol):
    """文档存储接口 - 继承 L4ObjectPort"""
    async def store_document(self, user_id: str, document_type: str,
                              file_path: str, content_type: str = "application/pdf",
                              metadata: dict[str, str] | None = None) -> str: ...
    def retrieve_document(self, user_id: str, document_type: str, document_id: str,
                          version_id: str | None = None) -> AsyncIterator[bytes]: ...
    async def list_user_documents(self, user_id: str, document_type: str | None = None,
                                  prefix: str = "") -> list[dict]: ...

# Layer 3: Infrastructure 技术实现
class MinIOAdapter(L4ObjectPort):
    """MinIO 通用对象存储实现"""
    def __init__(self, repository: MinIORepository): ...

# Layer 4: Infrastructure 具体应用实现
class MinIODocumentStorage(DocumentStoragePort):
    """MinIO 文档存储实现"""
    def __init__(self, adapter: MinIOAdapter):
        self._adapter = adapter

    async def store_document(self, user_id, document_type, file_path, content_type, metadata=None):
        # 自动路径生成
        object_key = f"documents/{user_id}/{document_type}/.../{Path(file_path).name}"
        return await self._adapter.store("documents", object_key, file_path, content_type, metadata)

    # 继承 L4ObjectPort 基础方法
    async def store(self, bucket_type, object_key, file_path, content_type, tags=None) -> str:
        return await self._adapter.store(bucket_type, object_key, file_path, content_type, tags)

    def retrieve(self, bucket_type, object_key, version_id=None) -> AsyncIterator[bytes]:
        return self._adapter.retrieve(bucket_type, object_key, version_id)

    async def delete(self, bucket_type, object_key, version_id=None) -> bool:
        return await self._adapter.delete(bucket_type, object_key, version_id)

    async def get_metadata(self, bucket_type, object_key, version_id=None) -> dict:
        return await self._adapter.get_metadata(bucket_type, object_key, version_id)

    async def archive(self, bucket_type, object_key, content=None, retention_days=2555) -> str:
        return await self._adapter.archive(bucket_type, object_key, content, retention_days)

    async def list_objects(self, bucket_type, prefix="", recursive=True) -> list[dict]:
        return await self._adapter.list_objects(bucket_type, prefix, recursive)
```

### 2.4 与 L1 缓存层架构对照

| 维度 | L1 缓存层 | L4 对象存储层 |
|------|-----------|---------------|
| **Layer 1** | `L1CachePort` (get/set/delete) | `L4ObjectPort` (store/retrieve/delete/archive/list) |
| **Layer 2** | `SemanticCachePort` (语义缓存) | `DocumentStoragePort` (文档存储) |
| **Layer 3** | `RedisL1CacheAdapter` + `RedisPoolProvider` | `MinIOAdapter` + 分层组件 (ClientAdapter/BucketManager/ObjectOperations/WORMManager) |
| **Layer 4** | `RedisSemanticCacheAdapter` (组合 L1CacheAdapter) | `MinIODocumentStorage` (组合 MinIOAdapter) |
| **技术栈** | Redis 7.0+ | MinIO (S3 兼容) |
| **并发模型** | 异步 (redis.asyncio) | 同步 SDK + asyncio.to_thread |

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

### 3.3 Layer 3: MinIORepository（更新实现）

**文件：** `src/infrastructure/storage/minio/minio_repository.py`

**变更：**
1. 实现接口从 `ObjectStorageRepository` 改为 `L4ObjectPort`
2. `archive()` 返回类型从 `bool` 改为 `str`

```python
# src/infrastructure/storage/minio/minio_repository.py

from src.domain.ports.l4_object import L4ObjectPort  # 改用 L4ObjectPort

class MinIORepository(L4ObjectPort):  # 改实现 L4ObjectPort
    """MinIO 对象存储仓储实现。

    实现领域层 L4ObjectPort 接口，
    内部委托给 BucketManager、ObjectOperations 和 WORMManager。
    """

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str:  # 改为返回 str
        """归档对象至 WORM 存储，启用 Object Lock。

        Returns:
            str: 对象 ID 或 ETag
        """
        import asyncio

        bucket_name = self._resolve_bucket_name(bucket_type)
        result = await asyncio.to_thread(
            self._worm_manager.archive_object,
            bucket_name=bucket_name,
            object_key=object_key,
            retention_days=retention_days,
        )
        return str(result) if result else ""

    # 其他方法保持不变...
```

### 3.4 Layer 3: MinIOAdapter（确认委托）

**文件：** `src/infrastructure/storage/minio/minio_adapter.py`

**状态：** 已正确实现委托 `MinIORepository`，但需补充 list_objects 方法。

**重要说明：** `archive()` 方法的 `content` 参数仅用于接口兼容性，实际不支持上传 content。如需上传并归档，请使用 `store()` 方法。

```python
# src/infrastructure/storage/minio/minio_adapter.py

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

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str:
        """归档对象（带 WORM retention）。

        注意：content 参数仅用于接口兼容性，实际不支持上传 content。
        如需上传 content，请使用 store() 方法。
        """
        if content is not None:
            raise NotImplementedError(
                "archive() with content upload is not supported. "
                "Use store() for content upload, then set_retention() for WORM."
            )
        return await self._repository.archive(bucket_type, object_key, retention_days)

    async def list_objects(self, bucket_type, prefix="", recursive=True) -> list[dict]:
        """列出对象，支持前缀过滤。"""
        return await self._repository.list_objects(bucket_type, prefix, recursive)
```

### 3.5 Layer 2: DocumentStoragePort

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

### 3.6 Layer 4: MinIODocumentStorage

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

## 5. 执行步骤（带 checkbox 执行状态跟踪）

> **说明**：每个步骤前的 `[ ]` 表示执行状态，`[ ]` = 待执行，`[x]` = 已完成。执行后更新此文档。

### Phase 1: 删除 ObjectStorageRepository，迁移到 L4ObjectPort

**目标：** 统一 Domain 层抽象，消除并存接口

**状态：待执行**

| Checkbox | 步骤 | 任务 | 验证命令 |
|----------|------|------|---------|
| `[ ]` | 1.1 | 更新 `minio_repository.py` 继承 `L4ObjectPort`（而非 `ObjectStorageRepository`） | `python -c "from src.infrastructure.storage.minio.minio_repository import MinIORepository; from src.domain.ports.l4_object import L4ObjectPort; print('OK' if issubclass(MinIORepository, L4ObjectPort) else 'FAIL')"` |
| `[ ]` | 1.2 | 修改导入：`from src.domain.ports.l4_object import L4ObjectPort` | `grep -r "ObjectStorageRepository" --include="*.py" src/infrastructure/` 无结果 |
| `[ ]` | 1.3 | 更新 `src/domain/ports/__init__.py` 移除 `ObjectStorageRepository` 导出 | 导入检查 |
| `[ ]` | 1.4 | 删除 `src/domain/ports/storage.py` | `test -f src/domain/ports/storage.py && echo "exists" \|\| echo "deleted"` |
| `[ ]` | 1.5 | 修复 `MinIORepository.archive()` 返回类型从 `bool` 改为 `str`，增加 `content: bytes \| None = None` 参数 | `grep -A2 "async def archive" src/infrastructure/storage/minio/minio_repository.py \| grep "-> str"` |
| `[ ]` | 1.6 | 验证所有测试通过 | `pytest tests/unit/infrastructure/storage/test_minio_adapter.py -v` |

**影响文件：**
```bash
grep -rl "ObjectStorageRepository" --include="*.py" src/
```

---

### Phase 2: 修复 MinIOAdapter 方法缺失与 archive 语义

**目标：** 修复 archive 方法签名不一致和 list_objects 方法缺失问题

**状态：待执行**

**前置依赖：** Phase 1 完成（MinIORepository 继承 L4ObjectPort 后才能正确委托）**

| Checkbox | 步骤 | 任务 | 验证命令 |
|----------|------|------|---------|
| `[ ]` | 2.1 | 在 `MinIOAdapter.archive()` 开头添加 content 检查：`if content is not None: raise NotImplementedError(...)` | `grep "NotImplementedError" src/infrastructure/storage/minio/minio_adapter.py` |
| `[ ]` | 2.2 | 添加 `MinIOAdapter.list_objects()` 方法，委托 `MinIORepository.list_objects()` | `grep "def list_objects" src/infrastructure/storage/minio/minio_adapter.py` |
| `[ ]` | 2.3 | 验证 `MinIOAdapter` 实现 `L4ObjectPort` 完整接口 | `python -c "from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter; print('OK')"` |
| `[ ]` | 2.4 | 运行 `test_minio_adapter.py` 验证 archive 和 list_objects | `pytest tests/unit/infrastructure/storage/test_minio_adapter.py -v` |

**archive 语义约束（方案 B）：**
```python
if content is not None:
    raise NotImplementedError(
        "archive() with content upload is not supported. "
        "Use store() for content upload, then set_retention() for WORM."
    )
```

---

### Phase 3: 创建 DocumentStoragePort

**目标：** 建立 Layer 2 应用层端口

**状态：待执行**

**前置依赖：** Phase 1 完成（L4ObjectPort 稳定后 DocumentStoragePort 才能继承）**

| Checkbox | 步骤 | 任务 | 验证命令 |
|----------|------|------|---------|
| `[ ]` | 3.1 | 创建 `src/application/ports/__init__.py`（如不存在） | `test -f src/application/ports/__init__.py && echo "exists"` |
| `[ ]` | 3.2 | 创建 `src/application/ports/document_storage.py`，定义 `DocumentStoragePort(L4ObjectPort, Protocol)` | `test -f src/application/ports/document_storage.py` |
| `[ ]` | 3.3 | 实现 `store_document`, `retrieve_document`, `list_user_documents`, `get_document_metadata` 方法 | `grep "def store_document" src/application/ports/document_storage.py` |
| `[ ]` | 3.4 | 显式声明继承的 L4ObjectPort 方法（满足类型检查） | `mypy src/application/ports/document_storage.py` |
| `[ ]` | 3.5 | 更新 `src/application/ports/__init__.py` 导出 `DocumentStoragePort` | `grep "DocumentStoragePort" src/application/ports/__init__.py` |

---

### Phase 4: 创建 MinIODocumentStorage

**目标：** 建立 Layer 4 具体应用实现

**状态：待执行**

**前置依赖：** Phase 2.2 和 Phase 3.2 完成（需要 MinIOAdapter.list_objects() 和 DocumentStoragePort 接口定义）**

| Checkbox | 步骤 | 任务 | 验证命令 |
|----------|------|------|---------|
| `[ ]` | 4.1 | 创建 `src/infrastructure/storage/minio/document_storage.py` | `test -f src/infrastructure/storage/minio/document_storage.py` |
| `[ ]` | 4.2 | 实现 `MinIODocumentStorage(DocumentStoragePort)`，组合 `MinIOAdapter` | `grep "class MinIODocumentStorage" src/infrastructure/storage/minio/document_storage.py` |
| `[ ]` | 4.3 | 实现路径自动生成：`documents/{user_id}/{document_type}/YYYY-MM/{filename}` | `grep "object_key" src/infrastructure/storage/minio/document_storage.py` |
| `[ ]` | 4.4 | 实现文档特有方法和 L4ObjectPort 继承方法委托 | `mypy src/infrastructure/storage/minio/document_storage.py` |
| `[ ]` | 4.5 | 更新 `src/infrastructure/storage/minio/__init__.py` 导出 `MinIODocumentStorage` | `grep "MinIODocumentStorage" src/infrastructure/storage/minio/__init__.py` |

---

### Phase 5: 回归测试

**目标：** 确保重构不破坏现有功能

**状态：待执行**

| Checkbox | 步骤 | 任务 | 验证命令 |
|----------|------|------|---------|
| `[ ]` | 5.1 | 运行 L4ObjectPort 单元测试 | `pytest tests/unit/domain/ports/test_l4_object_port.py -v` |
| `[ ]` | 5.2 | 运行 MinIOAdapter 单元测试 | `pytest tests/unit/infrastructure/storage/test_minio_adapter.py -v` |
| `[ ]` | 5.3 | 运行集成测试 | `pytest tests/integration/ -x -q` |
| `[ ]` | 5.4 | 运行架构测试 | `pytest tests/unit/architecture/ -x -q` |
| `[ ]` | 5.5 | 运行 mypy 类型检查 | `mypy src/infrastructure/storage/minio/ src/application/ports/document_storage.py` |
| `[ ]` | 5.6 | 验证 P0 问题全部修复（R1-R7 验收标准） | 见验收标准章节 |

---

### 执行状态汇总

| Phase | 状态 | 已完成步骤 | 待执行步骤 |
|-------|------|-----------|------------|
| Phase 1 | `[ ]` 待执行 | 0/6 | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 |
| Phase 2 | `[ ]` 待执行 | 0/4 | 2.1, 2.2, 2.3, 2.4 |
| Phase 3 | `[ ]` 待执行 | 0/5 | 3.1, 3.2, 3.3, 3.4, 3.5 |
| Phase 4 | `[ ]` 待执行 | 0/5 | 4.1, 4.2, 4.3, 4.4, 4.5 |
| Phase 5 | `[ ]` 待执行 | 0/6 | 5.1, 5.2, 5.3, 5.4, 5.5, 5.6 |

**总计：0/26 步骤已完成**

---

## 6. 风险评估与缓解（v1.2 审查更新）

| 风险 | 概率 | 影响 | 缓解措施 | 审查更新 |
|------|------|------|---------|---------|
| R1: 删除 ObjectStorageRepository 破坏现有调用 | 低 | 高 | ObjectStorageRepository 未公开导出，实际无调用方 | ✅ 风险下调 |
| R2: archive 返回类型不一致导致测试失败 | 低 | 高 | 无调用方依赖 bool 返回值，测试已期望 str | ✅ 风险下调 |
| R3: list_objects 签名变更破坏调用方 | 低 | 中 | src/ 下无调用 MinIOAdapter.list_objects()，无破坏风险 | ✅ 风险下调 |
| R4: archive content 参数语义不清导致运行时错误 | 高 | 高 | content 被静默丢弃会导致数据丢失，必须实现 NotImplementedError | ⚠️ 维持高风险 |
| R5: DocumentStoragePort 继承关系不满足类型检查 | 低 | 中 | 显式声明继承方法可解决 | ✅ 风险可控 |
| R6: WORMManager 返回值修改影响审计服务 | 低 | 低 | 审计服务调用 worm_manager.archive_object()，不经过 L4ObjectPort | ✅ 无影响 |
| R7: WORMManager.archive_object() 返回值恒 True | 低 | 高 | archive_object 应返回 stat_object.etag 而非固定 True | ⚠️ 待修复 |
| R8: Acceptance 测试绕过 MinIOAdapter | 中 | 高 | 适配器层错误无法被发现，应直接测试适配器 | ⚠️ 需修复测试 |
| R9: DocumentStoragePort/MinIODocumentStorage 文件缺失 | 高 | 中 | Phase 3/4 执行后风险消除 | ⚠️ 待执行 |

**关键发现（Round 3 审查）：**
- `ObjectStorageRepository` 未在 `__init__.py` 导出，不是公开 API
- `unified_storage_gateway.py` 使用 `L4ObjectPort`，与 `ObjectStorageRepository` 解耦
- 所有 archive 调用方都不依赖 bool 返回值
- src/ 下无任何代码调用 `MinIOAdapter.list_objects()`

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
| R1 | 所有 Domain/Infra 抽象统一到 `L4ObjectPort` | `grep -r "ObjectStorageRepository" --include="*.py" src/` 无结果（排除 tests/） | ❌ 待验证 |
| R2 | `MinIOAdapter` 包含 `list_objects` 方法 | `grep "def list_objects" src/infrastructure/storage/minio/minio_adapter.py` | ❌ 待实现 |
| R3 | `MinIORepository.archive()` 返回 `str` | 类型注解检查 + 运行时验证 | ❌ 待修复 |
| R4 | `MinIOAdapter.archive()` 正确处理 content 参数 | `content != None` 时抛出 `NotImplementedError`（代码检查 + 运行时测试） | ❌ 待实现 |
| R5 | `DocumentStoragePort` 正确继承 `L4ObjectPort` | `issubclass(DocumentStoragePort, L4ObjectPort)` | ❌ 待创建 |
| R6 | `MinIODocumentStorage` 实现 `DocumentStoragePort` | `isinstance(storage, DocumentStoragePort)` | ❌ 待创建 |
| R7 | 所有测试通过 | `pytest tests/unit/infrastructure/storage/test_minio_adapter.py tests/unit/domain/ports/test_l4_object_port.py -v` | ❌ 待验证 |
| R8 | `test_archive_with_content` 测试行为与方案 B 一致 | Phase 2.1 实施后该测试应失败或被修改（方案 B 不支持 content 上传） | ❌ 待验证 |

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
| 1.1.0 | 2026-05-13 | - | 架构审查修正：修复 archive/list_objects 方法问题 |
| 1.2.0 | 2026-05-13 | - | 代码审查更新：确认 P0 问题实际未执行，更新文档状态 |
| 1.3.0 | 2026-05-13 | - | Round 1-5 审查完成：补充架构一致性分析、测试覆盖缺陷、风险重评估、相位编号修正 |
| 1.4.0 | 2026-05-13 | - | Round 6-8 审查完成：WORMManager 实现问题、测试覆盖深化、委托矩阵分析、重复条目清理 |
