# Story 20-6: 端口契约测试补全

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 为 domain/ports 和 application/ports 全部端口补全契约测试,
**So that** 确保每个端口的注册、接口规范、实现一致性得到自动化验证，防止端口契约漂移。

### 业务价值

Epic 20 前序 Story（20-1 ~ 20-5）完成了测试框架、事件总线、异步重构、统一存储架构等重大改造。当前 `composition_root.py` 注册了 **60 个端口**（含基础设施端口如 ConnectionManager x4、EventPublisher x3 等），另有 5 个定义了 Protocol 但未注册的端口需做接口验证。现有仅 3 个端口契约测试。端口契约是六边形架构的核心防线，缺失契约测试意味着：
- 端口注册遗漏无法自动发现
- 接口方法签名变更无法自动检测
- 实现类与接口不匹配无法自动拦截

| 指标 | 现状 | 目标 |
|------|------|------|
| 端口契约测试覆盖 | 3/60（~5%） | 60/60（100%） |
| 端口基础设施测试 | 0 | registry + resolver + contract_gate 全覆盖 |
| verify_contracts.py | 5 个端口验证 | 全部 60 个已注册端口验证 |

### 端口清单总览

> **⚠️ 关键发现：** 5 个端口 Protocol（PermissionRepositoryPort, IndexManagerPort, UnitOfWork, HealthCheckPort, IntegrityPort）定义了接口但未在 `composition_root.py` 注册。这些端口只能做接口验证（方法存在性），无法做注册验证和实现匹配验证。

**已存在契约测试（3 个，需重构使用公共 fixture）：**
| 端口注册名 | 接口 | 测试文件 |
|------|------|---------|
| hash_router | HashRouterProtocol | `tests/contracts/test_port_contract_hash_router.py` |
| user_repo | UserRepositoryPort | `tests/contracts/test_port_contract_user_repo.py` |
| event_publisher | EventPublisher | `tests/contracts/test_port_contract_event_publisher.py` |

**待补全 — domain/ports 存储层（已注册 7 个 + 枚举）：**
| 端口注册名 | 接口类 | 方法数 | 文件 |
|---------|--------|-------|------|
| l0_storage | L0StoragePort | 5 | `src/domain/ports/l0_storage.py` |
| redis_adapter | L1CachePort | 6 | `src/domain/ports/l1_cache.py` |
| l3_vector | L3VectorPort | 9 | `src/domain/ports/l3_vector.py` |
| l4_object | L4ObjectPort | 6 | `src/domain/ports/l4_object.py` |
| l5_graph | L5GraphPort | 9 | `src/domain/ports/l5_graph.py` |
| unified_storage | UnifiedStoragePort | 4 | `src/domain/ports/unified_storage.py` |
| session_storage | SessionStorage | 4 | `src/domain/ports/session_storage.py` |
| StorageEnums | StorageLayer/StorageTier/DataAccessPattern | - | `src/domain/ports/storage_enums.py` |

> **注：** L2RdbPort[T] 是泛型基类，不直接注册；其子类 L2MetadataRepositoryPort 等继承使用。

**待补全 — domain/ports 仓储层（已注册 9 个）：**
| 端口注册名 | 接口类 | 方法数 | 文件 |
|---------|--------|-------|------|
| role_repo | RoleRepositoryPort | 5 | `src/domain/ports/role_repository.py` |
| user_role_repo | UserRoleRepositoryPort | 4 | `src/domain/ports/user_role_repository.py` |
| login_attempt_repo | LoginAttemptRepositoryPort | 7 | `src/domain/ports/login_attempt_repository.py` |
| audit_repo | AuditRepositoryPort | 5 | `src/domain/ports/audit_repository.py` |
| outbox_repo | OutboxRepository | 4 | `src/domain/ports/outbox.py` |
| memory_metadata | L2MetadataRepositoryPort | 3+4 | `src/domain/ports/memory_repository.py` |
| memory_change_history | L2ChangeHistoryRepositoryPort | 1+4 | `src/domain/ports/memory_repository.py` |
| memory_group_member | L2GroupMemberRepositoryPort | 4 | `src/domain/ports/memory_repository.py` |
| snapshot_repository | SnapshotRepositoryProtocol | 3 | `src/domain/ports/snapshot_repository_protocol.py` |

> **注：** PermissionRepositoryPort 和 IndexManagerPort 属于仓储层定义但未注册，将在 Task 5 的未注册 Protocol 接口验证中统一处理（共 5 个未注册 Protocol 完整列表见第 201 行）。

**待补全 — domain/ports 认证/安全/合规（已注册 10 个）：**
| 端口注册名 | 接口类 | 方法数 | 文件 |
|---------|--------|-------|------|
| auth_service | AuthServicePort | 4 | `src/domain/ports/auth_service.py` |
| permission_service | PermissionServicePort | 2 | `src/domain/ports/permission_service.py` |
| token_blacklist | TokenBlacklistPort | 2 | `src/domain/ports/token_blacklist.py` |
| password_validation | PasswordValidationServicePort | 2 | `src/domain/ports/password_validation_service.py` |
| compliance_gateway | ComplianceGatewayPort | 1 | `src/domain/ports/compliance_gateway.py` |
| sensitive_data_detector | SensitiveDataDetectorPort | 1 | `src/domain/ports/sensitive_data_detector.py` |
| data_residency_enforcer | DataResidencyEnforcerPort | 2 | `src/domain/ports/data_residency_enforcer.py` |
| whitelist_service | WhitelistServicePort | 2 | `src/domain/ports/whitelist_service.py` |
| pipl_compliance | PIPLComplianceServicePort | 7 | `src/domain/ports/pipl_compliance_service.py` |
| cross_border_transfer | CrossBorderTransferServicePort | 4 | `src/domain/ports/cross_border_transfer_service.py` |

**待补全 — domain/ports 服务协议与基础设施（已注册 7 个，未注册 3 个）：**

**已注册（可做完整契约验证）：**
| 端口注册名 | 接口类 | 方法数 | 文件 |
|---------|--------|-------|------|
| redis_connection_manager | ConnectionManager | 3 | `src/domain/ports/connection_manager.py` |
| postgresql_connection_manager | ConnectionManager | 3 | 同上（4 个注册共用接口） |
| qdrant_connection_manager | ConnectionManager | 3 | 同上 |
| neo4j_connection_manager | ConnectionManager | 3 | 同上 |
| audit_service | AuditServicePort | 4 | `src/domain/ports/audit_service.py` |
| semantic_router | SemanticRouterProtocol | 1 | `src/domain/ports/semantic_router_protocol.py` |
| sandbox_executor | SandboxExecutor | 4 | `src/domain/ports/sandbox_executor.py` |

**未注册（仅做接口验证）：**
| 接口类 | 方法数 | 文件 |
|--------|-------|------|
| UnitOfWork | 6 | `src/domain/ports/unit_of_work.py` |
| HealthCheckPort | 2 | `src/domain/ports/health_check.py` |
| IntegrityPort | 3 | `src/domain/ports/integrity.py` |

**待补全 — application/ports（已注册 14 个）：**
| 端口注册名 | 接口类 | 基类 | 方法数 | 文件 |
|---------|--------|------|-------|------|
| ~~sandbox_executor~~ | SandboxExecutor | Protocol (@runtime_checkable) | 4 | ~~`src/application/ports/sandbox_port.py`~~ → 已合并至 `src/domain/ports/sandbox_executor.py` |
| semantic_cache | SemanticCache | Protocol | 3 | `src/application/ports/semantic_cache.py` |
| memory_file_storage | MemoryFilePort | L0StoragePort | 3+5 | `src/application/ports/memory_file_port.py` |
| public_blackboard | PublicBlackboard | Protocol | 4 | `src/application/ports/public_blackboard.py` |
| compressor | CompressorService | Protocol | 2 | `src/application/ports/compressor_service.py` |
| session_cache | SessionCachePort | L1CachePort | 4+6 | `src/application/ports/session_cache_port.py` |
| memory_cache | MemoryCachePort | L1CachePort | 4+6 | `src/application/ports/memory_cache_port.py` |
| exception_metrics | ExceptionMetricsPort | Protocol | 1 | `src/application/ports/exception_metrics_port.py` |
| document_storage | DocumentStoragePort | L4ObjectPort | 3+6 | `src/application/ports/document_storage_port.py` |
| memory_vector_storage | MemoryVectorPort | L3VectorPort | 2+9 | `src/application/ports/memory_vector_port.py` |
| text_extractor | TextExtractorService | Protocol | 2 | `src/application/ports/text_extractor_service.py` |
| memory_graph_storage | MemoryGraphPort | L5GraphPort | 2+9 | `src/application/ports/memory_graph_port.py` |
| metrics | MetricsPort | Protocol | 12 | `src/application/ports/metrics_port.py` |
| event_subscriber | EventSubscriber | Protocol | 4 | `src/application/ports/event_subscriber.py` |

**基础设施端口（使用第三方接口，Task 7 验证）：**

> **⚠️ 契约测试策略：** 以下 10 个基础设施端口使用第三方或内部非 Protocol 接口，无法做方法签名验证。
> **Task 7 的 verify_contracts.py 增强版将遍历全部 60 个已注册端口，自动验证这 10 个端口的注册存在性和 Resolver 可解析性。**

| 端口注册名 | 接口类型 | 说明 |
|---------|----------|------|
| redis_client | aioredis.Redis | 第三方类型，无本地 Protocol |
| postgresql_async_engine | AsyncEngine | SQLAlchemy 类型 |
| session_factory | async_sessionmaker | SQLAlchemy 类型 |
| qdrant_client | AsyncQdrantClient | 第三方类型 |
| neo4j_driver | AsyncDriver | 第三方类型 |
| router | ChannelRouter | 内部基础设施类（非 Protocol） |
| redis_bus | EventPublisher | 与 event_publisher 共用接口 |
| rabbitmq_bus | EventPublisher | 与 event_publisher 共用接口 |
| rabbitmq_publisher | RabbitMQPublisher | 内部基础设施类 |
| outbox_poller | AsyncOutboxPoller | 内部基础设施类 |

> **注：** event_publisher 已有契约测试（Task 1 重构），redis_bus 和 rabbitmq_bus 共用 EventPublisher 接口。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 端口基础设施测试完成

**Given** 端口基础设施模块（registry/resolver/contract_gate）
**When** 运行 `pytest tests/contracts/ -v`
**Then** PortRegistry、Resolver、ContractGate 的核心功能全部被测试覆盖

**验证标准:**
- [x] `tests/contracts/test_port_infrastructure.py` 覆盖 PortRegistry.register/get/list_all/unregister
- [x] `tests/contracts/test_port_infrastructure.py` 覆盖 Resolver.resolve/resolve_by_interface 生命周期
- [x] `tests/contracts/test_port_infrastructure.py` 覆盖 ContractGate.check_compatibility 方法
- [x] 测试通过 `pytest tests/contracts/test_port_infrastructure.py -v`

### AC-2: 全部 domain/ports 存储层端口契约测试完成

**Given** L0-L5 + UnifiedStorage + SessionStorage + StorageEnums 共 9 组端口定义
**When** 运行 `pytest tests/contracts/test_port_contract_storage.py -v`
**Then** 所有存储层端口的注册、接口方法、实现一致性通过验证

**验证标准:**
- [x] 每个已注册端口有注册验证（registry.get 断言非 None）
- [x] 每个端口有接口方法签名验证（所有 Protocol 方法存在且 callable）
- [x] L2RdbPort[T] 泛型基类方法签名存在性验证
- [x] StorageEnums 枚举值完整性验证（StorageLayer: 6, StorageTier: 4, DataAccessPattern: 4）

### AC-3: 全部 domain/ports 仓储层端口契约测试完成

**Given** 10 组已注册仓储端口定义（含 memory_repository.py 的 3 个端口）
**When** 运行 `pytest tests/contracts/ -k "repo" -v`
**Then** 所有已注册仓储端口的注册、接口方法、实现一致性通过验证

**验证标准:**
- [x] L2RdbPort 泛型基类契约验证
- [x] L2MetadataRepositoryPort / L2ChangeHistoryRepositoryPort 继承验证
- [x] L2GroupMemberRepositoryPort 独立方法验证
- [x] UserRepositoryPort 已有测试需重构使用公共 fixture（不在本 Task 新增）

### AC-4: 全部 domain/ports 认证/安全/合规端口契约测试完成

**Given** 10 组认证安全合规端口定义
**When** 运行 `pytest tests/contracts/test_port_contract_auth_security.py -v`
**Then** 所有认证安全合规端口的注册、接口方法通过验证

**验证标准:**
- [x] 10 个端口全部有注册验证（registry.get 断言非 None）
- [x] 每个端口有接口方法签名验证（所有 Protocol 方法 callable）
- [x] 每个端口的元数据完整（version/owner/module 非空）

### AC-5: 全部 domain/ports 服务协议端口契约测试完成

**Given** 7 组已注册服务协议端口 + 5 个未注册 Protocol 接口定义
**When** 运行 `pytest tests/contracts/test_port_contract_services.py tests/contracts/test_port_contract_unregistered.py -v`
**Then** 所有已注册服务协议端口的注册、接口方法通过验证，5 个未注册 Protocol 接口方法存在性通过验证

**验证标准:**
- [x] 7 个已注册端口有注册验证 + 实现类方法验证
- [x] 5 个未注册 Protocol 仅做接口方法存在性验证（PermissionRepositoryPort, IndexManagerPort, UnitOfWork, HealthCheckPort, IntegrityPort）

### AC-6: 全部 application/ports 端口契约测试完成

**Given** 14 组应用层端口定义
**When** 运行 `pytest tests/contracts/test_port_contract_application.py -v`
**Then** 所有应用层端口的注册、接口方法通过验证

**验证标准:**
- [x] 14 个端口全部有注册验证（registry.get 断言非 None）
- [x] 每个端口有接口方法签名验证（含继承基类的方法）
- [x] 每个端口的元数据完整（version/owner/module 非空）

### AC-7: verify_contracts.py 增强覆盖全部已注册端口

**Given** composition_root.py 中注册的全部端口
**When** 运行 `python -m tests.contracts.verify_contracts`
**Then** 输出完整的端口清单并验证全部已注册端口可解析

**验证标准:**
- [x] verify_contracts.py 自动遍历 registry.list_all() 验证全部端口
- [x] 每个已注册端口验证可被 Resolver 解析
- [x] 输出结构化 manifest（name/interface/impl/module/lifetime）

### AC-8: 端口契约测试基础架构统一

**Given** 现有 3 个契约测试使用不一致的模式
**When** 重构契约测试基础设施
**Then** 所有契约测试使用统一的 fixture/base class 模式

**验证标准:**
- [x] 创建 `tests/contracts/conftest.py` 定义公共 fixture（registry, resolver）
- [x] 现有 3 个测试文件重构为使用公共 fixture
- [x] 新测试文件全部使用统一模式
- [x] `pytest tests/contracts/ -v` 全部通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 统一端口注册与接口治理
- [x] 端口契约位于 `src/domain/ports` 与 `src/application/ports`
- [x] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口登记为 `PortSpec`
- [x] 端口解析器位于 `src/domain/ports/resolver.py`
- [x] 契约门禁位于 `src/domain/ports/contract_gate.py`
- [x] 端口实现仅可在 `src/composition_root.py` 统一注册

#### 端口契约测试规范

**契约测试三要素（每个端口必须验证）：**
1. **注册验证**：端口在 registry 中存在且 interface 匹配
2. **方法签名验证**：Protocol/ABC 中定义的所有方法在实现类上存在且 callable
3. **元数据验证**：version/owner/lifetime/tags 非空且符合规范

**测试文件命名规范：**
- 基础设施测试：`tests/contracts/test_port_infrastructure.py`
- 存储层端口：`tests/contracts/test_port_contract_storage.py`
- 仓储层端口：`tests/contracts/test_port_contract_repositories.py`
- 认证安全合规端口：`tests/contracts/test_port_contract_auth_security.py`
- 服务协议端口：`tests/contracts/test_port_contract_services.py`
- 应用层端口：`tests/contracts/test_port_contract_application.py`

**公共 fixture（`tests/contracts/conftest.py`）：**

> **⚠️ 注意：** `tests/conftest.py` 已有 `_bootstrap_once` fixture（autouse, session-scoped）自动调用 `bootstrap()`。
> 因此 contracts conftest 不需要重复 bootstrap，只需提供 resolver 便利 fixture。

```python
# tests/contracts/conftest.py
from __future__ import annotations

import pytest
from src.domain.ports.registry import _global_registry
from src.domain.ports.resolver import Resolver


@pytest.fixture(scope="session")
def registry():
    """提供已初始化的端口注册中心（bootstrap 由 tests/conftest.py 自动调用）"""
    return _global_registry


@pytest.fixture(scope="session")
def resolver():
    """提供已初始化的 Resolver"""
    return Resolver()
```

**契约测试统一模式：**
```python
class TestXxxPortContract:
    PORT_NAME = "xxx"
    INTERFACE = XxxProtocol
    REQUIRED_METHODS = ["method1", "method2"]

    def test_port_is_registered(self, registry):
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry):
        """使用 spec.impl 类级别检查方法存在性，避免 resolver.resolve() 实例化"""
        spec = registry.get(self.PORT_NAME)
        impl_cls = spec.impl if isinstance(spec.impl, type) else None
        if impl_cls is None:
            # impl 可能是 lambda 工厂或字符串路径，使用 resolver 解析
            from src.domain.ports.resolver import Resolver
            impl = Resolver().resolve(self.PORT_NAME)
        else:
            impl = impl_cls
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method)
            assert callable(getattr(impl, method))

    def test_metadata_complete(self, registry):
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module
```

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
- 禁止导入：langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

#### 验收标准 Gherkin (Acceptance Tests)

**功能测试文件：** `tests/acceptance/test_acceptance_port_contracts_refactor.feature`

```gherkin
Feature: 端口契约测试补全
  作为系统架构师
  我要为所有端口补全契约测试
  以确保端口注册、接口规范、实现一致性得到自动化验证

  Background:
    Given 端口注册中心已初始化

  Scenario: 所有已注册端口可被 Resolver 解析
    Given 端口注册中心已通过 bootstrap() 初始化
    When 遍历所有已注册端口
    Then 每个端口的 Resolver.resolve() 返回有效实现实例

  Scenario: 已废弃端口未注册
    Given 已废弃端口列表 [VectorStorage, ObjectStorageRepository]
    When 检查注册中心
    Then 废弃端口的 Protocol 类未出现在注册中心

  Scenario: 端口接口方法完整性
    Given 任意已注册端口 P
    When 提取 P 的 interface 的所有公共方法
    Then P 的实现类拥有所有这些方法且为 callable
```

**Task 0 完成标志：**
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 端口清单与契约测试规范文档通过评审

---

### TDD 循环约束（适用于每个 Task）

> **⚠️ 本 Story 为纯测试 Story，不修改 src/ 代码。TDD 循环变体：**
> - **🔴 红** = 编写契约测试断言现有端口注册/接口方法（测试会通过，验证现有实现正确）
> - **🟢 绿** = 确认测试通过（现有代码已满足契约）
> - **🔄 重构** = 优化测试结构（参数化、消除重复）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 编写契约测试（注册验证 + 方法签名验证） | 测试文件编写完成 |
| **🟢 绿** | 运行 `pytest` 确认现有实现满足契约 | `pytest` 全部通过 |
| **🔄 重构** | 参数化重复模式，提取公共 fixture | `ruff check` + `pytest` 全部通过 |

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 契约测试** | 端口基础设施 | registry/resolver/contract_gate | `test_port_infrastructure.py` | Task 1 |
| **TDD 契约测试** | 存储层端口（已注册） | L0-L5 + Unified + Enums + session_storage | `test_port_contract_storage.py` | Task 2 |
| **TDD 契约测试** | 仓储层端口（已注册） | 9 组仓储端口 | `test_port_contract_repositories.py` | Task 3 |
| **TDD 契约测试** | 认证安全合规端口 | 10 组端口 | `test_port_contract_auth_security.py` | Task 4 |
| **TDD 契约测试** | 服务协议端口（已注册） | ConnectionManager x4 + audit_service + semantic_router + sandbox_executor | `test_port_contract_services.py` | Task 5 |
| **TDD 契约测试** | 应用层端口（已注册） | 14 组端口 | `test_port_contract_application.py` | Task 6 |
| **TDD 接口验证** | 未注册 Protocol | UnitOfWork / HealthCheckPort / IntegrityPort / PermissionRepositoryPort / IndexManagerPort | `test_port_contract_unregistered.py` | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_port_contracts_refactor.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_port-contracts-refactor.py` | Task 0 |
| **集成验证** | verify_contracts.py | 全量端口清单与解析 | `verify_contracts.py` | Task 7 |

> **⚠️ 契约测试策略差异：**
> - **已注册端口**：验证 registry 存在 + interface 匹配 + 实现类方法存在 + 元数据完整
> - **未注册 Protocol**：仅验证 Protocol 类存在 + 方法签名完整（无 registry/impl 验证）
> - **基础设施端口（第三方接口）**：仅验证 registry 存在 + resolver 可解析（无方法签名验证）

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **端口基础设施覆盖率 ≥90%**（`pytest --cov=src/domain/ports/registry.py --cov=src/domain/ports/resolver.py --cov=src/domain/ports/contract_gate.py`）

> **测试补全 Story 覆盖率说明：** 本 Story 以新增契约测试为主，不修改 src/ 代码。
> 覆盖率验证重点在 `tests/contracts/` 目录的测试完整性，而非 src/ 覆盖率。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check tests/contracts/`）
- [ ] **MyPy 类型检查通过**（`mypy tests/contracts/`）

#### 测试隔离约束

| 约束类型 | 规则 |
|---------|------|
| **注册中心隔离** | 契约测试使用 registry fixture，不手动注册/注销端口 |
| **解析器隔离** | Resolver 实例不跨测试共享状态 |
| **幂等性** | 测试可重复运行，不依赖执行顺序 |
| **并行安全** | `pytest tests/contracts/ -n 4` 通过 |

**验证要求：**
- [ ] `pytest tests/contracts/ -v` 通过
- [ ] `pytest tests/contracts/ -n 4` 通过（并行）
- [ ] 连续 3 次运行无随机失败

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 端口基础设施测试 | Task 1 | registry/resolver/contract_gate | `test_port_infrastructure.py` |
| AC-2 | 存储层端口契约测试 | Task 2 | L0-L5 + Unified + Enums | `test_port_contract_storage.py` |
| AC-3 | 仓储层端口契约测试 | Task 3 | 9 组待补全仓储端口 | `test_port_contract_repositories.py` |
| AC-4 | 认证安全合规端口测试 | Task 4 | 10 组端口 | `test_port_contract_auth_security.py` |
| AC-5 | 服务协议端口测试 | Task 5 | 7 组已注册 + 5 组未注册 | `test_port_contract_services.py` + `test_port_contract_unregistered.py` |
| AC-6 | 应用层端口测试 | Task 6 | 14 组端口 | `test_port_contract_application.py` |
| AC-7 | verify_contracts 增强 | Task 7 | 全量端口验证 | `verify_contracts.py` |
| AC-8 | 测试基础设施统一 | Task 1 | conftest + 现有测试重构 | `conftest.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部 AC

> **目的：** 在进入测试实现前，明确端口清单、契约测试规范与验收标准。

- [x] Subtask 0.1: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_port_contracts_refactor.feature`
- [x] Subtask 0.2: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_port-contracts-refactor.py`
- [x] Subtask 0.3: 运行验收测试，确认失败（🔴 红阶段验证）
- [x] Subtask 0.4: 创建 `tests/contracts/conftest.py` 定义公共 fixture

**完成标准:**
- [x] 验收测试运行失败（预期行为）
- [x] 公共 fixture 定义完成

---

### Task 1: 端口基础设施测试 + 公共 fixture + 现有测试重构

**关联 AC:** AC-1, AC-8

#### TDD 循环 A：conftest 公共 fixture

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `conftest.py` fixture 引用测试（验证 fixture 可用） |
| 🟢 绿 | 实现 registry / resolver fixture |
| 🔄 重构 | 优化 fixture scope 和依赖注入 |

- [x] Subtask 1.1: 🔴 红 — 编写 fixture 存在性断言测试
- [x] Subtask 1.2: 🟢 绿 — 实现 `tests/contracts/conftest.py`
- [x] Subtask 1.3: 🔄 重构 — 优化 fixture scope

#### TDD 循环 B：PortRegistry 测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 PortRegistry.register/get/list_all/unregister 失败测试 |
| 🟢 绿 | 验证现有 registry 实现通过测试（测试先行验证） |
| 🔄 重构 | 优化测试结构 |

- [x] Subtask 1.4: 🔴 红 — 编写 PortRegistry 核心方法测试
- [x] Subtask 1.5: 🟢 绿 — 运行确认 PortRegistry 通过
- [x] Subtask 1.6: 🔄 重构 — 优化测试组织

#### TDD 循环 C：Resolver 测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 resolve/resolve_by_interface/lifecycle 测试 |
| 🟢 绿 | 验证现有 Resolver 实现 |
| 🔄 重构 | 优化 |

- [x] Subtask 1.7: 🔴 红 — 编写 Resolver 测试
- [x] Subtask 1.8: 🟢 绿 — 运行通过
- [x] Subtask 1.9: 🔄 重构 — 优化

#### TDD 循环 D：ContractGate 测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 check_compatibility 兼容性检查测试 |
| 🟢 绿 | 验证 ContractGate 实现 |
| 🔄 重构 | 优化 |

- [x] Subtask 1.10: 🔴 红 — 编写 ContractGate 测试
- [x] Subtask 1.11: 🟢 绿 — 运行通过
- [x] Subtask 1.12: 🔄 重构 — 优化

#### TDD 循环 E：现有测试重构

- [x] Subtask 1.13: 重构 `test_port_contract_hash_router.py` 使用公共 fixture
- [x] Subtask 1.14: 重构 `test_port_contract_user_repo.py` 使用公共 fixture
- [x] Subtask 1.15: 重构 `test_port_contract_event_publisher.py` 使用公共 fixture

**完成标准:**
- [x] `pytest tests/contracts/test_port_infrastructure.py -v` 通过
- [x] 现有 3 个测试文件重构完成且仍通过
- [x] `ruff check tests/contracts/` 通过

---

### Task 2: domain/ports 存储层端口契约测试

**关联 AC:** AC-2

#### TDD 循环：存储层端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 9 组存储层端口的注册/方法/元数据测试 |
| 🟢 绿 | 运行通过（验证现有注册正确） |
| 🔄 重构 | 优化为参数化测试 |

- [x] Subtask 2.1: 🔴 红 — 编写 L0StoragePort 契约测试（write/read/delete/exists/list_memories）
- [x] Subtask 2.2: 🔴 红 — 编写 L1CachePort 契约测试（get/set/delete/exists/delete_pattern/set_with_ttl）
- [x] Subtask 2.3: 🔴 红 — 编写 L2RdbPort 泛型基类契约测试（get_by_id/save/delete/list_all）
- [x] Subtask 2.4: 🔴 红 — 编写 L3VectorPort 契约测试（upsert_points/delete_points/get_point/search/search_sparse/create_collection/delete_collection/collection_exists/list_collections）
- [x] Subtask 2.5: 🔴 红 — 编写 L4ObjectPort 契约测试（store/retrieve/delete/get_metadata/archive/list_objects）
- [x] Subtask 2.6: 🔴 红 — 编写 L5GraphPort 契约测试（create_entity/get_entity/delete_entity/create_relationship/delete_relationship/find_related/execute_query/execute_write_query/get_neighbors）
- [x] Subtask 2.7: 🔴 红 — 编写 UnifiedStoragePort 契约测试（save/read/delete/exists）
- [x] Subtask 2.8: 🔴 红 — 编写 SessionStorage 契约测试（save/load/delete/exists）
- [x] Subtask 2.9: 🔴 红 — 编写 StorageEnums 枚举完整性测试（StorageLayer L0-L5 / StorageTier HOT~ARCHIVE / DataAccessPattern）
- [x] Subtask 2.10: 🟢 绿 — 运行全部通过
- [x] Subtask 2.11: 🔄 重构 — 参数化通用模式，消除重复

**完成标准:**
- [x] `pytest tests/contracts/test_port_contract_storage.py -v` 通过
- [x] 9 组存储层端口全部覆盖（7 个已注册 + SessionStorage + StorageEnums）

---

### Task 3: domain/ports 仓储层端口契约测试（已注册 9 个）

**关联 AC:** AC-3

> **⚠️ 注意：** UserRepositoryPort 已有契约测试（Task 1 重构），PermissionRepositoryPort/IndexManagerPort 未注册（在 Task 5 接口验证）。
> 本 Task 仅覆盖已注册且无现有测试的 9 个仓储端口。

#### TDD 循环：仓储层端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 9 组已注册仓储端口的契约测试 |
| 🟢 绿 | 运行通过 |
| 🔄 重构 | 参数化通用模式 |

- [x] Subtask 3.1: 🔴 红 — 编写 RoleRepositoryPort 契约测试（get_by_id/get_by_name/list_all/save/delete）
- [x] Subtask 3.2: 🔴 红 — 编写 UserRoleRepositoryPort 契约测试（assign_role/revoke_role/get_user_roles/get_role_users）
- [x] Subtask 3.3: 🔴 红 — 编写 LoginAttemptRepositoryPort 契约测试（record_attempt/get_recent_failed_attempts/is_account_locked/get_lockout_remaining_minutes/clear_attempts/check_and_record_lockout/record_attempt_and_check_lockout）
- [x] Subtask 3.4: 🔴 红 — 编写 AuditRepositoryPort 契约测试（save/get_by_id/search/update_archive_status/get_archive_status）
- [x] Subtask 3.5: 🔴 红 — 编写 OutboxRepository 契约测试（save/get_unpublished/mark_published/mark_failed）
- [x] Subtask 3.6: 🔴 红 — 编写 L2MetadataRepositoryPort 契约测试（get_by_name/list_by_user/list_by_type + 继承方法）
- [x] Subtask 3.7: 🔴 红 — 编写 L2ChangeHistoryRepositoryPort 契约测试（get_by_memory_id + 继承方法）
- [x] Subtask 3.8: 🔴 红 — 编写 L2GroupMemberRepositoryPort 契约测试（is_group_member/is_group_admin/add_member/remove_member）
- [x] Subtask 3.9: 🔴 红 — 编写 SnapshotRepositoryProtocol 契约测试（save/load/delete）
- [x] Subtask 3.10: 🟢 绿 — 运行全部通过
- [x] Subtask 3.11: 🔄 重构 — 参数化通用 CRUD 模式

**完成标准:**
- [x] `pytest tests/contracts/test_port_contract_repositories.py -v` 通过
- [x] 9 组已注册仓储端口全部覆盖

---

### Task 4: domain/ports 认证/安全/合规端口契约测试

**关联 AC:** AC-4

#### TDD 循环：认证安全合规端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 10 组认证安全合规端口的契约测试 |
| 🟢 绿 | 运行通过 |
| 🔄 重构 | 优化 |

- [x] Subtask 4.1: 🔴 红 — 编写 AuthServicePort 契约测试（authenticate/verify_token/refresh_token/logout）
- [x] Subtask 4.2: 🔴 红 — 编写 PermissionServicePort 契约测试（check_permission/get_user_permissions）
- [x] Subtask 4.3: 🔴 红 — 编写 TokenBlacklistPort 契约测试（add/is_blacklisted）
- [x] Subtask 4.4: 🔴 红 — 编写 PasswordValidationServicePort 契约测试（validate/get_requirements）
- [x] Subtask 4.5: 🔴 红 — 编写 ComplianceGatewayPort 契约测试（check）
- [x] Subtask 4.6: 🔴 红 — 编写 SensitiveDataDetectorPort 契约测试（detect_sensitive_data）
- [x] Subtask 4.7: 🔴 红 — 编写 DataResidencyEnforcerPort 契约测试（enforce_residency/check_violation）
- [x] Subtask 4.8: 🔴 红 — 编写 WhitelistServicePort 契约测试（is_allowed/add_to_whitelist）
- [x] Subtask 4.9: 🔴 红 — 编写 PIPLComplianceServicePort 契约测试（7 个方法）
- [x] Subtask 4.10: 🔴 红 — 编写 CrossBorderTransferServicePort 契约测试（request_transfer/approve/reject/list_pending_requests）
- [x] Subtask 4.11: 🟢 绿 — 运行全部通过
- [x] Subtask 4.12: 🔄 重构 — 优化

**完成标准:**
- [x] `pytest tests/contracts/test_port_contract_auth_security.py -v` 通过
- [x] 10 组端口全部覆盖

---

### Task 5: domain/ports 服务协议端口契约测试 + 未注册 Protocol 接口验证

**关联 AC:** AC-5

#### TDD 循环 A：服务协议端口契约测试（已注册）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 7 组已注册服务协议端口的契约测试 |
| 🟢 绿 | 运行通过 |
| 🔄 重构 | 优化 |

- [x] Subtask 5.1: 🔴 红 — 编写 ConnectionManager x4 契约测试（redis/postgresql/qdrant/neo4j_connection_manager）
- [x] Subtask 5.2: 🔴 红 — 编写 AuditServicePort 契约测试（record/verify_integrity/verify_batch/archive）
- [x] Subtask 5.3: 🔴 红 — 编写 SemanticRouterProtocol 契约测试（route）
- [x] Subtask 5.4: 🔴 红 — 编写 SandboxExecutor 契约测试（start_container/execute_code/stop_container/is_container_running）
- [x] Subtask 5.5: 🟢 绿 — 运行全部通过
- [x] Subtask 5.6: 🔄 重构 — 优化 ConnectionManager 参数化

#### TDD 循环 B：未注册 Protocol 接口验证（仅方法签名验证）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 5 个未注册 Protocol 的接口方法存在性测试 |
| 🟢 绿 | 运行通过（仅验证 Protocol 类定义正确） |
| 🔄 重构 | 优化 |

- [x] Subtask 5.7: 🔴 红 — 编写 UnitOfWork 接口验证（begin/commit/rollback/close/begin_nested + async context）
- [x] Subtask 5.8: 🔴 红 — 编写 HealthCheckPort 接口验证（check/close）
- [x] Subtask 5.9: 🔴 红 — 编写 IntegrityPort 接口验证（verify_file/compute_hash/verify_hash）
- [x] Subtask 5.10: 🔴 红 — 编写 PermissionRepositoryPort 接口验证（get_by_name/get_by_id/save/delete/list_all）
- [x] Subtask 5.11: 🔴 红 — 编写 IndexManagerPort 接口验证（update_entry/remove_entry/read_entries/search/truncate）
- [x] Subtask 5.12: 🟢 绿 — 运行全部通过
- [x] Subtask 5.13: 🔄 重构 — 合并到 `test_port_contract_unregistered.py`

**完成标准:**
- [x] `pytest tests/contracts/test_port_contract_services.py -v` 通过（已注册 7 个）
- [x] `pytest tests/contracts/test_port_contract_unregistered.py -v` 通过（未注册 5 个）
- [x] 12 组端口全部覆盖

---

### Task 6: application/ports 应用层端口契约测试

**关联 AC:** AC-6

#### TDD 循环：应用层端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 14 组应用层端口的契约测试 |
| 🟢 绿 | 运行通过 |
| 🔄 重构 | 优化 |

- [x] Subtask 6.1: 🔴 红 — 编写 SandboxExecutor 契约测试（start_container/execute_code/stop_container/is_container_running）
- [x] Subtask 6.2: 🔴 红 — 编写 SemanticCache 契约测试（get/set/invalidate）
- [x] Subtask 6.3: 🔴 红 — 编写 MemoryFilePort 契约测试（update_index/remove_from_index/search_index + 继承 L0StoragePort 方法）
- [x] Subtask 6.4: 🔴 红 — 编写 PublicBlackboard 契约测试（post/get/get_by_agent/get_latest）
- [x] Subtask 6.5: 🔴 红 — 编写 CompressorService 契约测试（compress/supports + CompressionResult dataclass）
- [x] Subtask 6.6: 🔴 红 — 编写 MemoryCachePort 契约测试（get_memory/set_memory/delete_memory/invalidate_owner + 继承 L1CachePort）
- [x] Subtask 6.7: 🔴 红 — 编写 ExceptionMetricsPort 契约测试（record_exception）
- [x] Subtask 6.8: 🔴 红 — 编写 DocumentStoragePort 契约测试（store_document/list_user_documents/get_document_metadata + 继承 L4ObjectPort）
- [x] Subtask 6.9: 🔴 红 — 编写 MemoryVectorPort 契约测试（index_memory/search_similar_memories + 继承 L3VectorPort）
- [x] Subtask 6.10: 🔴 红 — 编写 SessionCachePort 契约测试（save_session/load_session/delete_session/session_exists + 继承 L1CachePort）
- [x] Subtask 6.11: 🔴 红 — 编写 TextExtractorService 契约测试（extract/supports + ExtractionResult dataclass）
- [x] Subtask 6.12: 🔴 红 — 编写 MemoryGraphPort 契约测试（index_memory_relations/get_knowledge_graph + 继承 L5GraphPort）
- [x] Subtask 6.13: 🔴 红 — 编写 MetricsPort 契约测试（collect/collect_as_dict/record_sessions/record_queue_length/record_cache_hit/record_cache_miss/record_event_processed/update_processing_rate/get_hit_rate/get_sessions/get_queue_length/get_processing_rate）
- [x] Subtask 6.14: 🔴 红 — 编写 EventSubscriber 契约测试（subscribe/subscribe_async/start/close）
- [x] Subtask 6.15: 🟢 绿 — 运行全部通过
- [x] Subtask 6.16: 🔄 重构 — 提取继承验证公共模式

**完成标准:**
- [x] `pytest tests/contracts/test_port_contract_application.py -v` 通过
- [x] 14 组应用层端口全部覆盖

---

### Task 7: verify_contracts.py 增强 + 基础设施端口验证 + 集成验证

**关联 AC:** AC-7

> **⚠️ 本 Task 同时覆盖 10 个基础设施端口（第三方/非 Protocol 接口）的注册存在性和 Resolver 可解析性验证。**

#### TDD 循环：verify_contracts 增强

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写增强版 verify_contracts.py 的测试期望 |
| 🟢 绿 | 实现增强版 verify_contracts.py |
| 🔄 重构 | 优化输出格式 |

- [x] Subtask 7.1: 🔴 红 — 编写 verify_contracts 全量端口覆盖测试
- [x] Subtask 7.2: 🟢 绿 — 增强 verify_contracts.py 遍历 registry.list_all()（含 10 个基础设施端口的注册验证）
- [x] Subtask 7.3: 🟢 绿 — 增加实现类方法存在性验证
- [x] Subtask 7.4: 🟢 绿 — 增加已废弃端口排除验证
- [x] Subtask 7.5: 🔄 重构 — 优化输出格式为结构化 manifest
- [x] Subtask 7.6: 运行 `python -m tests.contracts.verify_contracts` 验证全部通过

**完成标准:**
- [x] verify_contracts.py 输出完整端口清单
- [x] 全部已注册端口验证通过
- [x] 已废弃端口确认未注册

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Hexagonal Architecture）
- **设计约束:** 领域层零依赖、依赖倒置、仓储模式
- **接口治理:** 统一端口注册 PortSpec、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+、Protocol（typing）、dataclass（标准库）

### 关键架构决策

**来源:** Story 20-5（统一存储架构重构）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **统一契约测试文件**（按域分组） | 易维护、发现快 | 单文件较大 | ✅ 9/10 |
| 每端口一个测试文件 | 精确隔离 | 60+ 个文件过多 | 6/10 |
| 参数化 pytest 单文件 | 最少代码 | 失败定位难 | 7/10 |

### 项目结构说明

```
tests/
├── contracts/
│   ├── conftest.py                           # NEW: 公共 fixture
│   ├── test_port_infrastructure.py           # NEW: registry/resolver/contract_gate
│   ├── test_port_contract_storage.py         # NEW: 存储层端口（已注册）
│   ├── test_port_contract_repositories.py    # NEW: 仓储层端口（已注册）
│   ├── test_port_contract_auth_security.py   # NEW: 认证安全合规（已注册）
│   ├── test_port_contract_services.py        # NEW: 服务协议端口（已注册）
│   ├── test_port_contract_unregistered.py    # NEW: 未注册 Protocol 接口验证
│   ├── test_port_contract_application.py     # NEW: 应用层端口（已注册）
│   ├── test_port_contract_hash_router.py     # REFACTOR: 使用公共 fixture
│   ├── test_port_contract_user_repo.py       # REFACTOR: 使用公共 fixture
│   ├── test_port_contract_event_publisher.py # REFACTOR: 使用公共 fixture
│   └── verify_contracts.py                   # ENHANCE: 全量验证（含10个基础设施端口）
├── acceptance/
│   ├── test_acceptance_port_contracts_refactor.feature               # NEW: Gherkin 验收场景
│   └── test_acceptance_port-contracts-refactor.py              # NEW: BDD 步骤实现
```

### 前一个故事学习经验

**来源:** [Story 20-5 统一存储架构重构](./20-5-uni-storage-refactor.md)

**关键学习:**
- 所有 Port 使用 Protocol（非 ABC），domain/ports 全部标注 @runtime_checkable
- application/ports 中 6 个 Protocol（SemanticCache, PublicBlackboard, CompressorService, ExceptionMetricsPort, TextExtractorService, MetricsPort）**缺少** @runtime_checkable，不可使用 isinstance() 检查
- SandboxExecutor 已合并至 `src/domain/ports/sandbox_executor.py` 并标注 @runtime_checkable
- 组合根 bootstrap() 是注册的唯一入口，测试须先调用
- L2RdbPort[T] 是泛型基类，L2MetadataRepositoryPort/L2ChangeHistoryRepositoryPort 继承它
- application/ports 的多个端口继承 domain/ports 的基础端口（如 MemoryFilePort 继承 L0StoragePort）

**应用到本故事:**
- [ ] 契约测试须先 bootstrap() 注册中心
- [ ] 继承端口的测试须验证基类方法也存在
- [ ] 使用 hasattr() + callable() 做方法签名验证（不依赖 isinstance，因部分 Protocol 缺少 @runtime_checkable）
- [ ] ⚠️ **resolver.resolve() 实施风险**：对需要外部服务（Redis/PostgreSQL/Qdrant/Neo4j）的端口，resolve() 会尝试实例化基础设施类。契约测试应优先使用 `spec.impl` 类级别方法检查，或对 resolver 配置 overrides 避免实际连接

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | claude-opus-4-7 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-19 |

### 调试日志引用

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/20-5-uni-storage-refactor.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **Composition Root** | `src/composition_root.py` |

### 完成清单

- [x] 端口清单从 src/domain/ports/ 和 src/application/ports/ 代码提取
- [x] 架构约束从 architecture.md 和 project-context.md 提取
- [x] 前一个故事学习经验整合（Story 20-5）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 测试文件结构对齐统一规范

### 文件清单

**待创建的文件:**
- `tests/contracts/conftest.py` - 公共 fixture（registry, resolver）
- `tests/contracts/test_port_infrastructure.py` - 基础设施测试（registry/resolver/contract_gate）
- `tests/contracts/test_port_contract_storage.py` - 存储层端口测试（7 个已注册 + L2RdbPort 基类 + StorageEnums）
- `tests/contracts/test_port_contract_repositories.py` - 仓储层端口测试（已注册 9 个）
- `tests/contracts/test_port_contract_auth_security.py` - 认证安全合规测试（已注册 10 个）
- `tests/contracts/test_port_contract_services.py` - 服务协议端口测试（已注册 7 个）
- `tests/contracts/test_port_contract_unregistered.py` - **NEW: 未注册 Protocol 接口验证（5 个）**
- `tests/contracts/test_port_contract_application.py` - 应用层端口测试（已注册 14 个）
- `tests/acceptance/test_acceptance_port_contracts_refactor.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_port-contracts-refactor.py` - BDD 步骤实现

**待重构的文件:**
- `tests/contracts/test_port_contract_hash_router.py` - 使用公共 fixture
- `tests/contracts/test_port_contract_user_repo.py` - 使用公共 fixture
- `tests/contracts/test_port_contract_event_publisher.py` - 使用公共 fixture

**待增强的文件:**
- `tests/contracts/verify_contracts.py` - 全量端口验证

---

## 📊 故事详情

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 20.6 |
| **Story Key** | 20-6-port-contracts-refactor |
| **File** | `_bmad-output/implementation-artifacts/stories/20-6-port-contracts-refactor.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 20: 重大重构 |
| **优先级** | P0 |
| **覆盖范围** | 60 个已注册端口 + 5 个未注册 Protocol 接口验证 |

### 完成总结

1. [x] All tasks defined 所有任务定义完成（7 Tasks + Task 0）
2. [x] All acceptance criteria specified 8 项验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] 端口清单交叉验证完成（60 已注册 + 5 未注册）
6. [x] Sprint status synced to `ready-for-dev`

### 🔧 审查修订记录（2026-05-19）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 端口总数错误（54 → 60） | P0 | 更新业务价值描述和覆盖率目标 |
| 2 | 仓储层计数错误（11 表格有 12 行） | P0 | 重构端口清单表，区分已注册/未注册 |
| 3 | user_repo 在两个表中重复 | P1 | 从"待补全"表中移除，注明需重构 |
| 4 | 未注册端口（5 个）混入待补全列表 | P0 | 新增"未注册 Protocol"策略说明和独立测试文件 |
| 5 | 服务协议表命名不一致 | P1 | 统一使用端口注册名，拆分已注册/未注册 |
| 6 | TDD 模式不适用于纯测试 Story | P2 | 添加纯测试 Story 的 TDD 变体说明 |
| 7 | login_attempt_repo 方法数错误（6→7） | P0 | 补充 record_attempt_and_check_lockout |
| 8 | MetricsPort 方法数错误（11→12） | P0 | 补充 get_processing_rate |
| 9 | memory_cache 文件路径错误 | P0 | 修正为 application/ports/memory_cache_port.py |
| 10 | fixture 策略冲突（已有 _bootstrap_once） | P0 | 移除冗余 bootstrap，改用 registry fixture 直接引用 _global_registry |
| 11 | 应用层端口表缺 memory_cache 行（13→14） | P0 | 添加 memory_cache 行，完整 14 个 |
| 12 | Task 2 缺 session_storage 子任务 | P0 | 新增 Subtask 2.8，更新完成标准 8→9 组 |
| 13 | Task 3 包含已测试/未注册端口（3.1/3.4/3.12） | P0 | 移除 3 个错误子任务，重新编号，AC-3 计数 13→10 |
| 14 | storage 表 memory_cache 错位放置 | P0 | 从存储表移除（已在应用层） |
| 15 | 仓储层表格计数声明错误（10→9） | P0 | 第3轮审查修正 |
| 16 | 服务协议表格计数声明错误（11→4→7→3） | P0 | 第3轮审查修正 |
| 17 | 10 个基础设施端口无 Task 覆盖 | P0 | 明确 Task 7 的 verify_contracts.py 覆盖；拆分 redis_bus/rabbitmq_bus 为独立行 |
| 18 | AC-5 计数错误（8 组→7 已注册+5 未注册） | P0 | 第3轮审查修正 |
| 19 | AC-2 Given 计数错误（8 组→9 组） | P0 | 第4轮审查修正：新增 SessionStorage + L2RdbPort |
| 20 | AC-4/AC-5/AC-6 缺失验证标准 checkbox | P0 | 第4轮审查补充 |
| 21 | AC-5 Given 未注册计数错误（3→5） | P0 | 第4轮审查修正：Task 5 覆盖全部 5 个未注册 Protocol |
| 22 | pytest keyword 过滤策略复杂/不可靠 | P1 | 第4轮审查：改为直接指定测试文件名 |
| 23 | 项目结构说明缺少 tests/acceptance/ 目录 | P1 | 第4轮审查补充 |
| 24 | Task 3 标题/描述/完成标准"10 个"未同步更新 | P0 | 第5轮修正为"9 个" |
| 25 | Task 2 TDD 表"8 组"未同步 | P0 | 第5轮修正为"9 组" |
| 26 | 文件清单仓储层"10 个"未同步 | P0 | 第5轮修正为"9 个" |
| 27 | 测试分类表仓储层"10 组"未同步 | P0 | 第5轮修正为"9 组" |
| 28 | AC-3 追溯矩阵"10 组"未同步 | P0 | 第5轮修正为"9 组" |
| 29 | resolver.resolve() 实施风险（外部服务依赖） | P1 | 第5轮：更新测试模板用类级别检查，添加风险提示 |
| 30 | 7 个 application/ports Protocol 缺少 @runtime_checkable | P1 | 第5轮：更新学习经验，改用 hasattr/callable |
| 31 | 测试模板 resolver.resolve() 需改为安全模式 | P0 | 第5轮：使用 spec.impl 类级别检查 |

### 下一步

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
