# Story 1.11: 数据主权隔离

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 合规工程师,
**I want** 实现数据主权隔离（敏感数据本地优先处理，外部网络调用需审计与白名单批准）,
**So that** 系统满足数据安全法和 PIPL 要求，确保数据境内存储和跨境传输合规。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 4（安全与合规基础）的第三个故事，在 Story 1.9（RBAC）和 Story 1.10（统一审计日志）基础上实现数据主权隔离机制。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **敏感数据检测** | 自动识别 PII、商业秘密等敏感数据 | 检测准确率≥95%，误报率<5% |
| **本地优先处理** | 敏感数据强制在境内处理，禁止跨境 | 本地处理率 100% |
| **白名单管理** | 外部 API 调用必须经过白名单审批 | 白名单校验通过率 100% |
| **跨境审计** | 跨境数据传输必须经过审批流程 | 审批率 100%，完整审计日志 |
| **PIPL 合规** | 个人信息处理符合 PIPL 要求 | 合规检查通过率 100% |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 4: 安全与合规基础

**覆盖 FR:**
- FR-SC-07: 数据主权隔离（Story 1.11）

**覆盖 NFR:**
- NFR-SEC-03: 数据境内存储 100%
- NFR-SEC-04: 跨境传输审批率 100%

### 依赖关系 Dependencies

| 依赖 Story | 依赖类型 | 依赖原因 |
|-----------|---------|---------|
| Story 1-1: Hexagonal Architecture Skeleton | 硬依赖 | 六边形架构模式、依赖注入容器、领域层接口定义规范 |
| Story 1-9: RBAC Permission Management | 硬依赖 | 权限服务接口 `PermissionServicePort` 已定义，需 RBAC 作为基础 |
| Story 1-10: Unified Audit Log | 硬依赖 | 审计日志基础设施，数据主权违规和跨境审批需记录审计日志 |
| Story 1-15b: Externalized Memory Six-Layer Storage | 软依赖 | L1 合规性网关需感知数据驻留层实现 |

### 技术容量规划

| 指标 | MVP | V1 | V2 |
|------|-----|----|----|
| **敏感数据类型** | PII, 商业秘密, 金融数据(银行/保险/证券/基金/征信) | + 生物识别, 未成年人数据 | + 自定义类型 |
| **区域定义** | CHINA_DOMESTIC (中国大陆), CHINA_HKMO (港澳), OVERSEAS (境外) | + 台湾单独处理 | + 自定义区域 |
| **白名单条目** | ≤100 | ≤1,000 | ≤10,000 |
| **跨境审批 SLA** | 4 小时（紧急 1 小时） | 2 小时 | 1 小时 |
| **敏感数据检测延迟** | <100ms | <50ms | <20ms |
| **数据主体权利** | 访问权/更正权 | + 删除权 | + 可携带权 |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 敏感数据检测

**Given** 数据进入系统（文档上传、用户输入、API 请求）
**When** 执行敏感数据检测
**Then** 系统识别 PII、商业秘密、金融数据等敏感信息
**And** 标记敏感数据类型和置信度
**And** 触发 `SensitiveDataDetected` 事件

**验证标准/Validation Criteria:**
- [ ] 实体类 `SensitiveDataResult` 定义（`src/domain/entities/sensitive_data_result.py`）
- [ ] `SensitiveDataDetector` 服务接口（`src/domain/ports/sensitive_data_detector.py`）
- [ ] 正则表达式检测 PII（姓名、身份证、电话、邮箱）
- [ ] 关键词检测商业秘密（技术配方、客户列表、战略计划）
- [ ] 实体类检测金融数据（银行账号、信用卡号、保险单号、证券账户、基金账号、征信记录）
- [ ] `SensitiveDataDetected` 事件定义（已存在于 `src/domain/events/compliance_events.py`）
- [ ] 单元测试覆盖正常检测、边界情况（空数据、混淆数据）

### AC-2: 本地优先处理（Data Residency Enforcement）

**Given** 检测到敏感数据
**When** 执行数据处理或模型路由
**Then** 敏感数据强制在境内（CHINA_DOMESTIC）处理
**And** 禁止将敏感数据发送至境外模型或服务
**And** 若检测到违规，触发 `DataSovereigntyViolation` 事件

**验证标准/Validation Criteria:**
- [ ] `DataResidencyPolicy` 实体定义（allowed_regions, blocked_regions, CHINA_DOMESTIC/CHINA_HKMO/OVERSEAS）
- [ ] `DataResidencyEnforcer` 服务（`src/infrastructure/security/data_residency_enforcer_impl.py`）
- [ ] `ComplianceGateway` 合规性网关（`src/application/services/compliance_gateway.py`）和 `ComplianceResult`（`src/domain/value_objects/compliance_result.py`）本 Story 新建
- [ ] `ComplianceGateway` 接口定义（`src/domain/ports/compliance_gateway.py`）
- [ ] UDMR 路由集成（`ComplianceResult.forced_local=True` 时强制本地模型）
- [ ] `DataSovereigntyViolation` 事件定义（已存在于 `src/domain/events/compliance_events.py`）
- [ ] 违规补救机制: 数据隔离/销毁/通知义务/整改要求
- [ ] 集成测试验证本地优先策略生效

### AC-3: 白名单管理（Whitelist Management）

**Given** 系统需要调用外部 API
**When** 执行外部 API 调用
**Then** 调用前验证目标 API 是否在白名单中
**And** 验证通过后记录调用日志
**And** 验证失败记录违规并阻止调用

**验证标准/Validation Criteria:**
- [ ] `ExternalAPIWhitelist` 实体定义（`src/domain/entities/external_api_whitelist.py`）
  - 字段: `api_id`, `endpoint`, `provider`, `region`, `is_verified`, `risk_level`, `valid_from`, `valid_until`
  - 风险等级: `HIGH` (高风险-需DPO审批+安全评估), `MEDIUM` (中风险-需主管审批), `LOW` (低风险-自动审批)
  - 高风险审批要求: DPO审批、24小时时效、安全评估报告
- [ ] `WhitelistService` 服务接口（`src/domain/ports/whitelist_service.py`）
- [ ] `WhitelistServiceImpl` 实现（`src/infrastructure/security/whitelist_service_impl.py`）
- [ ] CRUD 接口: 创建/查询/更新/删除白名单条目
- [ ] `is_allowed()` 方法验证 API 是否在白名单且未过期
- [ ] 过期处理策略: 默认自动拒绝，到期前7天续期提醒
- [ ] 单元测试覆盖白名单验证通过、未通过、过期场景

### AC-4: 跨境数据传输审批（Cross-Border Transfer Approval）

**Given** 有数据需要跨境传输
**When** 执行跨境传输请求
**Then** 系统记录传输请求并触发审批流程
**And** 审批通过后执行传输
**And** 所有跨境传输记录至审计日志

**验证标准/Validation Criteria:**
- [ ] `CrossBorderTransferRequest` 实体定义（`src/domain/entities/cross_border_transfer.py`）
  - 字段: `request_id`, `data_id`, `destination`, `purpose`, `status`, `requester`, `approver`, `approval_timestamp`
- [ ] `CrossBorderTransferService` 服务接口（`src/domain/ports/cross_border_transfer_service.py`）
- [ ] `CrossBorderTransferServiceImpl` 实现（`src/infrastructure/security/cross_border_transfer_service_impl.py`）
- [ ] 审批流程: pending → approved/rejected → executed/blocked
- [ ] SLA 控制: 普通 4 小时，紧急 1 小时
- [ ] `CrossBorderTransferRequested` 事件定义（已存在于 `src/domain/events/compliance_events.py`）
- [ ] 审计日志集成（Story 1.10）

### AC-5: PIPL 合规（Personal Information Protection Law）

**Given** 处理个人信息
**When** 执行个人信息访问
**Then** 系统记录处理目的、法律依据、数据主体同意
**And** 验证处理合法性
**And** 记录至审计日志

**验证标准/Validation Criteria:**
- [ ] `PIPLComplianceRecord` 实体定义（`src/domain/entities/pipl_compliance_record.py`）
  - 字段: `access_id`, `personal_data_id`, `purpose`, `legal_basis`, `consent_status`, `accessor`, `accessed_at`, `data_subject_id`
  - 法律依据: consent(同意), contract(合同), legal_obligation(法定义务), vital_interest(生命利益), public_task(公共任务), legitimate_interest(合法权益), minor_consent(未成年人监护人同意)
  - 同意有效性: consent必须为明确同意(非默示)，需支持撤回机制
- [ ] `PIPLComplianceService` 服务接口（`src/domain/ports/pipl_compliance_service.py`）
- [ ] `PIPLComplianceServiceImpl` 实现（`src/infrastructure/security/pipl_compliance_service_impl.py`）
- [ ] 数据主体权利接口: `respond_to_access_request()`, `respond_to_correction_request()`, `respond_to_deletion_request()`, `respond_to_portability_request()`
- [ ] `PIPLDataAccessRequested` 事件定义（已存在于 `src/domain/events/compliance_events.py`）
- [ ] 合规检查测试覆盖所有法律依据场景

### AC-6: 等保 2.0 合规基础

**Given** 系统需要通过等保 2.0 三级测评
**When** 执行数据安全相关测评
**Then** 数据境内存储 100%
**And** 跨境传输审批率 100%
**And** 敏感数据保护符合要求

**验证标准/Validation Criteria:**
- [ ] 安全架构约束验证测试就绪
- [ ] 敏感数据检测覆盖关键类型（PII/商业秘密/金融数据/生物识别）
- [ ] 白名单验证机制正常工作（高/中/低风险分级审批）
- [ ] 跨境审批流程符合 SLA（普通4小时/紧急1小时）
- [ ] 审计日志完整性验证（事件追溯）
- [ ] 数据主体权利响应机制就绪（访问/更正/删除/可携带权）
- [ ] 违规补救机制就绪（隔离/销毁/通知/整改）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 数据模型 (Data Models)

**领域值对象:**
- [ ] `ComplianceResult` (`src/domain/value_objects/compliance_result.py`)
  - 字段: `allowed: bool`, `reason: str`, `forced_local: bool`, `violation_type: str | None`
  - 方法: `is_allowed()`, `is_violation()`, `get_violation_type()`

**领域实体:**
- [ ] `SensitiveDataResult` (`src/domain/entities/sensitive_data_result.py`)
  - 字段: `result_id` (UUID), `source_data_hash`, `sensitive_types: list[SensitiveType]`, `confidence: float`, `labels: list[str]`, `detected_at`
  - 方法: `is_high_confidence()`, `has_type()`, `merge_with()`
  - 说明: 定义为领域实体因需唯一标识和状态变更

**领域实体:**
- [ ] `DataResidencyPolicy` (`src/domain/entities/data_residency_policy.py`)
  - 字段: `policy_id`, `name`, `allowed_regions: list[str]`, `blocked_regions: list[str]`, `enforcement_level`
  - 方法: `is_allowed_region()`, `is_blocked_region()`
- [ ] `ExternalAPIWhitelist` (`src/domain/entities/external_api_whitelist.py`)
  - 字段: `api_id`, `endpoint`, `provider`, `region`, `is_verified`, `risk_level`, `valid_from`, `valid_until`
  - 方法: `is_valid()`, `is_high_risk()`
- [ ] `CrossBorderTransferRequest` (`src/domain/entities/cross_border_transfer.py`)
  - 字段: `request_id`, `data_id`, `destination`, `purpose`, `status`, `requester`, `approver`, `approval_timestamp`
  - 方法: `approve()`, `reject()`, `execute()`, `block()`
- [ ] `PIPLComplianceRecord` (`src/domain/entities/pipl_compliance_record.py`)
  - 字段: `access_id`, `personal_data_id`, `purpose`, `legal_basis`, `consent_status`, `accessor`, `accessed_at`, `data_subject_id`
  - 法律依据类型: consent, contract, legal_obligation, vital_interest, public_task, legitimate_interest, minor_consent
  - 方法: `validate_consent()`, `is_compliant()`, `validate_minor_consent()`

#### 服务接口 (Service Ports)

> ⚠️ **六边形架构约束：服务接口定义在 `src/domain/ports/`，仅依赖 Python 标准库**

- [ ] `SensitiveDataDetectorPort` (`src/domain/ports/sensitive_data_detector.py`)
  - 方法: `detect_sensitive_data(content: str) -> SensitiveDataResult`
- [ ] `DataResidencyEnforcerPort` (`src/domain/ports/data_residency_enforcer.py`)
  - 方法: `enforce_residency(data: Any, target_region: str) -> bool`, `check_violation(data: Any) -> bool`
- [ ] `WhitelistServicePort` (`src/domain/ports/whitelist_service.py`)
  - 方法: `is_allowed(api_endpoint: str) -> bool`, `add_to_whitelist(api: ExternalAPIWhitelist) -> None`
- [ ] `CrossBorderTransferServicePort` (`src/domain/ports/cross_border_transfer_service.py`)
  - 方法: `request_transfer(data: CrossBorderTransferRequest) -> None`, `approve(transfer_id: UUID) -> None`
- [ ] `PIPLComplianceServicePort` (`src/domain/ports/pipl_compliance_service.py`)
  - 方法: `record_access(record: PIPLComplianceRecord) -> None`, `validate_legal_basis(data_id: UUID, legal_basis: str) -> bool`
  - 数据主体权利: `respond_to_access_request()`, `respond_to_correction_request()`, `respond_to_deletion_request()`, `respond_to_portability_request()`
- [ ] `ComplianceGatewayPort` (`src/domain/ports/compliance_gateway.py`)
  - 方法: `check(task: Task) -> ComplianceResult`
  - 说明: UDMR L1 合规性网关端口，Task 为路由任务对象

#### 领域事件 (Domain Events)

> **注意：** 以下事件已在 `src/domain/events/compliance_events.py` 中定义，可直接复用

- [ ] `SensitiveDataDetected` - 敏感数据检测事件
- [ ] `DataSovereigntyViolation` - 数据主权违规事件
- [ ] `CrossBorderTransferRequested` - 跨境传输请求事件
- [ ] `PIPLDataAccessRequested` - PIPL 数据访问请求事件

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_story_1_11.feature`
- [ ] 覆盖场景:
  - 敏感数据检测（PII、商业秘密、金融数据）
  - 本地优先处理验证
  - 白名单验证通过/拒绝
  - 跨境传输审批流程
  - PIPL 合规记录
  - 违规检测和阻止

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证）
- [ ] 红阶段验证应确认测试因"模块不存在/类未定义"而失败，而非业务断言失败
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止跳过或颠倒顺序。**

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
| **TDD 单元测试** | SensitiveDataDetector | PII/商业秘密/金融数据检测 | `test_sensitive_data_detector.py` | Task 1 |
| **TDD 单元测试** | DataResidencyEnforcer | 本地优先策略验证 | `test_data_residency_enforcer.py` | Task 2 |
| **TDD 单元测试** | WhitelistService | 白名单验证 CRUD | `test_whitelist_service.py` | Task 3 |
| **TDD 单元测试** | CrossBorderTransferService | 跨境审批流程 | `test_cross_border_transfer.py` | Task 4 |
| **TDD 单元测试** | PIPLComplianceService | PIPL 合规记录 | `test_pipl_compliance.py` | Task 5 |
| **TDD 安全测试** | 合规性网关 | UDMR L1 集成验证 | `test_compliance_gateway.py` | Task 6 |
| **TDD 架构测试** | 架构约束 | 领域层零依赖验证 | `test_architecture_constraints.py` | Task 7 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-6

> **目的：** 在进入代码实现前，明确数据模型、服务接口、验收标准。

- [ ] Subtask 0.1: 定义 `SensitiveDataResult` 值对象
- [ ] Subtask 0.2: 定义 `DataResidencyPolicy` 实体
- [ ] Subtask 0.3: 定义 `ExternalAPIWhitelist` 实体
- [ ] Subtask 0.4: 定义 `CrossBorderTransferRequest` 实体
- [ ] Subtask 0.5: 定义 `PIPLComplianceRecord` 实体
- [ ] Subtask 0.6: 定义服务接口（5 个 Port）
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1_11.feature`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 敏感数据检测

**关联 AC:** AC-1

#### TDD 循环 A：SensitiveDataDetector

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_sensitive_data_detector.py`（检测 PII/商业秘密/金融数据） |
| 🟢 绿 | 实现 `SensitiveDataDetector` 服务 |
| 🔄 重构 | 优化检测规则和性能 |

- [ ] Subtask 1.1: 🔴 红 — 编写正则检测失败测试（PII: 身份证、电话、邮箱）
- [ ] Subtask 1.2: 🟢 绿 — 实现 PII 正则检测规则
- [ ] Subtask 1.3: 🔴 红 — 编写商业秘密关键词检测失败测试
- [ ] Subtask 1.4: 🟢 绿 — 实现商业秘密检测
- [ ] Subtask 1.5: 🔴 红 — 编写金融数据检测失败测试（银行账号、信用卡）
- [ ] Subtask 1.6: 🟢 绿 — 实现金融数据检测
- [ ] Subtask 1.7: 🔄 重构 — 优化检测性能和边界情况处理

**完成标准:**
- [ ] `SensitiveDataDetector` 实现完成
- [ ] 检测准确率≥95%，误报率<5%
- [ ] 所有测试通过

---

### Task 2: 本地优先处理（Data Residency Enforcement）

**关联 AC:** AC-2

#### TDD 循环 A：DataResidencyEnforcer

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_data_residency_enforcer.py`（本地优先策略验证） |
| 🟢 绿 | 实现 `DataResidencyEnforcer` 服务 |
| 🔄 重构 | 优化策略检查性能 |

- [ ] Subtask 2.1: 🔴 红 — 编写区域策略验证失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `DataResidencyEnforcer`
- [ ] Subtask 2.3: 🔴 红 — 编写违规检测失败测试
- [ ] Subtask 2.4: 🟢 绿 — 实现 `DataSovereigntyViolation` 事件触发
- [ ] Subtask 2.5: 🔄 重构 — 验证 UDMR L1 合规性网关集成

**完成标准:**
- [ ] `DataResidencyEnforcer` 实现完成
- [ ] 本地处理率 100%
- [ ] 所有测试通过

---

### Task 3: 白名单管理

**关联 AC:** AC-3

#### TDD 循环 A：WhitelistService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_whitelist_service.py`（白名单 CRUD + 验证） |
| 🟢 绿 | 实现 `WhitelistService` 服务 |
| 🔄 重构 | 优化白名单查询性能 |

- [ ] Subtask 3.1: 🔴 红 — 编写白名单创建失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现白名单 CRUD
- [ ] Subtask 3.3: 🔴 红 — 编写 `is_allowed()` 验证失败测试
- [ ] Subtask 3.4: 🟢 绿 — 实现白名单验证逻辑
- [ ] Subtask 3.5: 🔄 重构 — 验证过期条目处理

**完成标准:**
- [ ] `WhitelistService` 实现完成
- [ ] 白名单验证 100% 准确
- [ ] 所有测试通过

---

### Task 4: 跨境数据传输审批

**关联 AC:** AC-4

#### TDD 循环 A：CrossBorderTransferService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_cross_border_transfer.py`（审批流程测试） |
| 🟢 绿 | 实现 `CrossBorderTransferService` |
| 🔄 重构 | 验证 SLA 控制和审计日志 |

- [ ] Subtask 4.1: 🔴 红 — 编写传输请求创建失败测试
- [ ] Subtask 4.2: 🟢 绿 — 实现传输请求创建
- [ ] Subtask 4.3: 🔴 红 — 编写审批流程失败测试
- [ ] Subtask 4.4: 🟢 绿 — 实现审批/拒绝逻辑
- [ ] Subtask 4.5: 🔴 红 — 编写 SLA 控制失败测试
- [ ] Subtask 4.6: 🟢 绿 — 实现 SLA 超时处理
- [ ] Subtask 4.7: 🔄 重构 — 验证审计日志集成

**完成标准:**
- [ ] `CrossBorderTransferService` 实现完成
- [ ] 审批率 100%
- [ ] SLA 满足（普通 4 小时，紧急 1 小时）
- [ ] 所有测试通过

---

### Task 5: PIPL 合规

**关联 AC:** AC-5

#### TDD 循环 A：PIPLComplianceService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_pipl_compliance.py`（PIPL 合规测试） |
| 🟢 绿 | 实现 `PIPLComplianceService` |
| 🔄 重构 | 验证法律依据类型覆盖 |

- [ ] Subtask 5.1: 🔴 红 — 编写访问记录失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 `PIPLComplianceService`
- [ ] Subtask 5.3: 🔴 红 — 编写法律依据验证失败测试（6 种类型）
- [ ] Subtask 5.4: 🟢 绿 — 实现法律依据验证
- [ ] Subtask 5.5: 🔄 重构 — 验证所有法律依据场景

**完成标准:**
- [ ] `PIPLComplianceService` 实现完成
- [ ] 合规检查通过率 100%
- [ ] 所有测试通过

---

### Task 6: 合规性网关集成

**关联 AC:** AC-6

#### TDD 循环 A：ComplianceGateway

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_compliance_gateway.py`（UDMR L1 集成测试） |
| 🟢 绿 | 实现合规性网关集成 |
| 🔄 重构 | 验证端到端合规流程 |

- [ ] Subtask 6.1: 🔴 红 — 编写合规性检查失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现 `ComplianceGateway` 集成
- [ ] Subtask 6.3: 🔄 重构 — 验证 UDMR L1 路由决策

**完成标准:**
- [ ] 合规性网关与 UDMR 集成完成
- [ ] 所有合规检查通过
- [ ] 所有测试通过

---

### Task 7: 架构约束验证

**关联 AC:** AC-6

#### TDD 循环：架构约束测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_architecture_constraints.py`（验证领域层零外部依赖） |
| 🟢 绿 | 实现满足架构约束的代码结构 |
| 🔄 重构 | 优化架构检查逻辑 |

- [ ] Subtask 7.1: 🔴 红 — 编写架构约束失败测试（领域层导入外部库检测）
- [ ] Subtask 7.2: 🟢 绿 — 确保所有领域层文件仅使用 Python 标准库
- [ ] Subtask 7.3: 🔴 红 — 编写端口定义位置验证失败测试
- [ ] Subtask 7.4: 🟢 绿 — 确保端口定义在 `src/domain/ports/`
- [ ] Subtask 7.5: 🔄 重构 — 验证服务实现在 `src/infrastructure/security/`

**完成标准:**
- [ ] `test_architecture_constraints.py` 测试通过
- [ ] Ruff 检查通过（严重错误=0）
- [ ] MyPy 类型检查通过（错误率<5%）
- [ ] 领域层零外部依赖验证通过

---

## 测试要求与质量门禁

### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **安全层覆盖率 ≥85%**（`pytest --cov=src/infrastructure/security`）- **P1 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

> ⚠️ **安全层覆盖率要求：** 本 Story 为安全层实现（数据主权/PIPL/等保 2.0），需达到安全层≥85% 标准。

### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`)
- [ ] **MyPy 类型检查通过**（`mypy src/`)
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`)
- [ ] **Bandit 安全扫描通过**（`bandit -r src/`，高危漏洞=0）

### 合规性测试要求

| 测试项 | 目标 | 测试文件 |
|--------|------|----------|
| 敏感数据检测准确率 | ≥95% | `test_sensitive_data_detector.py` |
| 误报率 | <5% | `test_sensitive_data_detector.py` |
| 本地处理率 | 100% | `test_data_residency_enforcer.py` |
| 白名单验证 | 100% 准确 | `test_whitelist_service.py` |
| 跨境审批率 | 100% | `test_cross_border_transfer.py` |
| PIPL 合规检查 | 100% 通过 | `test_pipl_compliance.py` |

---

## 📝 Dev Notes 开发笔记

### 架构约束（来自 project-context.md）

1. **领域层零依赖**: 所有 Port 仅用 `ABC` + Python 标准库
2. **服务实现分离**: 实现类在 `src/infrastructure/security/`（可导入外部库）
3. **事件驱动审计**: 数据主权违规和跨境审批通过事件触发审计日志
4. **六边形架构**: 领域层定义接口，基础设施层实现

### 与 Story 1.9/1.10 的关系

| 组件 | Story 1.9 | Story 1.10 | Story 1.11 |
|------|-----------|------------|-------------|
| PermissionServicePort | 定义 | 复用 | 复用 |
| AuditServicePort | 复用 | 定义 | 复用 |
| ComplianceGateway | 新增 | 新增 | 集成 |

### 复用现有实现

1. **ComplianceEvent 定义** (`src/domain/events/compliance_events.py`) - 已实现 6 个合规事件
2. **PermissionMiddleware** (`src/infrastructure/security/permission_middleware.py`) - 可复用 PermissionContext
3. **PermissionServicePort** (`src/domain/ports/permission_service.py`) - 复用 RBAC 基础

---

## 📚 参考资料

- [Source: docs/architecture/architecture.md] — UDMR L1 合规性网关（第 4 章）
- [Source: src/domain/events/compliance_events.py] — 已定义的合规事件
- [Source: _bmad-output/implementation-artifacts/stories/1-9-rbac-permission-management.md] — RBAC 实现参考
- [Source: _bmad-output/implementation-artifacts/stories/1-10-unified-audit-log.md] — 审计日志参考
- [Source: _bmad-output/project-context.md] — 项目上下文

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | MiniMax-M2 |
| **Version** | story-template.md v2.5.0 |
| **Execution Date** | 2026-05-11 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **Story 1.9** | `_bmad-output/implementation-artifacts/stories/1-9-rbac-permission-management.md` |
| **Story 1.10** | `_bmad-output/implementation-artifacts/stories/1-10-unified-audit-log.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 epics_v1.0.md 提取
- [ ] 架构约束从 architecture.md 提取
- [ ] 前置故事学习经验整合（Story 1.9/1.10）
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 状态设置为 `ready-for-dev`

### 文件清单 File List

**待创建的文件/To Be Created (Dev Story 实施):**

| 文件 | 说明 |
|------|------|
| `src/domain/entities/sensitive_data_result.py` | SensitiveDataResult 实体 |
| `src/domain/entities/data_residency_policy.py` | DataResidencyPolicy 实体 |
| `src/domain/entities/external_api_whitelist.py` | ExternalAPIWhitelist 实体 |
| `src/domain/entities/cross_border_transfer.py` | CrossBorderTransferRequest 实体 |
| `src/domain/entities/pipl_compliance_record.py` | PIPLComplianceRecord 实体 |
| `src/domain/value_objects/compliance_result.py` | ComplianceResult 值对象 |
| `src/domain/ports/sensitive_data_detector.py` | SensitiveDataDetectorPort 接口 |
| `src/domain/ports/data_residency_enforcer.py` | DataResidencyEnforcerPort 接口 |
| `src/domain/ports/whitelist_service.py` | WhitelistServicePort 接口 |
| `src/domain/ports/cross_border_transfer_service.py` | CrossBorderTransferServicePort 接口 |
| `src/domain/ports/pipl_compliance_service.py` | PIPLComplianceServicePort 接口 |
| `src/domain/ports/compliance_gateway.py` | ComplianceGatewayPort 接口 |
| `src/application/services/compliance_gateway.py` | ComplianceGateway 应用服务 |
| `src/infrastructure/security/data_residency_enforcer_impl.py` | DataResidencyEnforcerImpl 实现 |
| `src/infrastructure/security/sensitive_data_detector_impl.py` | SensitiveDataDetectorImpl 实现 |
| `src/infrastructure/security/whitelist_service_impl.py` | WhitelistServiceImpl 实现 |
| `src/infrastructure/security/cross_border_transfer_service_impl.py` | CrossBorderTransferServiceImpl 实现 |
| `src/infrastructure/security/pipl_compliance_service_impl.py` | PIPLComplianceServiceImpl 实现 |
| `tests/unit/domain/entities/test_sensitive_data_result.py` | SensitiveDataResult 测试 |
| `tests/unit/security/test_sensitive_data_detector.py` | SensitiveDataDetector 测试 |
| `tests/unit/security/test_data_residency_enforcer.py` | DataResidencyEnforcer 测试 |
| `tests/unit/security/test_whitelist_service.py` | WhitelistService 测试 |
| `tests/unit/security/test_cross_border_transfer.py` | CrossBorderTransferService 测试 |
| `tests/unit/security/test_pipl_compliance.py` | PIPLComplianceService 测试 |
| `tests/unit/application/test_compliance_gateway.py` | ComplianceGateway 集成测试 |
| `tests/acceptance/test_story_1_11.feature` | Gherkin 验收测试 |
| `tests/architecture/test_architecture_constraints.py` | 架构约束测试 |

**共计 27 个文件**

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.11 |
| **Story Key** | 1-11-data-sovereignty-isolation |
| **File** | `_bmad-output/implementation-artifacts/stories/1-11-data-sovereignty-isolation.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 4: 安全与合规基础 |
| **优先级** | P0 |
| **覆盖 FR** | FR-SC-07 |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成（7 Tasks + Task 0 SDD）
2. [ ] All acceptance criteria specified 所有验收标准已定义（6 ACs）
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Story file created

### 下一步 Next Steps

- [ ] 运行 `dev-story 1-11` 开始实施
- [ ] 运行 `code-review` 进行代码审查
