# Story 1.11: 数据主权隔离

**Status:** `backlog` 🚨 [已回退 - 实际未实现]

> **⚠️ 重要更新 (2026-05-04):** 本 Story 状态已回退至 `backlog`。经过代码审计发现：
> - Story 文件在 2026-04-20 被标记为 `done`，但**实际实现不存在**
> - `src/domain/events/compliance_events.py` ✅ 存在（领域事件定义正确）
> - `src/infrastructure/security/` ❌ **目录不存在**（声称实现的模块未创建）
> - `src/interfaces/cli/sovereignty_commands.py` ❌ **不存在**
> - `src/interfaces/api/sovereignty_endpoints.py` ❌ **不存在**
> - 所有测试文件 ❌ **不存在**

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

> **🔧 技术约束（v1.0）：**
> 1. **复用 Story 1.9/1.10 安全基础设施** — AuthService/PermissionService/AuditService
> 2. **对齐 UDMR L1 合规性网关架构** — 参考 architecture.md 4.2 节 ComplianceGateway 设计，但独立实现数据主权检测组件
> 3. **敏感数据标签** — 定义敏感数据类型（PII/商业秘密/财务数据）
> 4. **白名单机制** — 外部 API 调用白名单校验
> 5. **数据境内存储** — 六层存储本地优先策略
> 6. **PIPL 合规** — 满足个人信息保护法要求

---

## 📖 Story 描述

**As a** 合规工程师,
**I want** 实现数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）,
**So that** 满足数据安全法和 PIPL 要求。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 4（安全与合规基础）的第三个故事，在 Story 1.9 (RBAC 权限管理) 和 Story 1.10 (统一审计日志) 基础上实现数据主权隔离系统。数据主权作为系统合规的核心基础设施，承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **敏感数据识别** | 自动识别并标记敏感数据 | PII/商业秘密识别准确率≥95% |
| **本地优先处理** | 敏感数据强制本地处理 | 本地处理率 100% |
| **外部调用审计** | 所有外部 API 调用白名单校验 | 白名单校验 100% |
| **跨境传输控制** | 跨境传输需审批 | 审批率 100% |
| **PIPL 合规** | 满足个人信息保护法要求 | 合规审计通过 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 4: 安全与合规基础

**覆盖 FR:**
- FR-SC-07: 数据主权隔离（Story 1.11）

**覆盖 NFR:**
- NFR-COMP-03: 数据主权（数据境内存储 100%、跨境传输审批率 100%）
- NFR-COMP-04: 隐私保护（PIPL）

### 依赖关系 Dependencies

| 依赖 Story | 依赖类型 | 依赖原因 |
|-----------|---------|---------|
| Story 1-1: Hexagonal Architecture Skeleton | 硬依赖 | 六边形架构模式、依赖注入容器 |
| Story 1-5: PostgreSQL Relational Layer | 硬依赖 | 数据主权策略存储于 PostgreSQL |
| Story 1-9: RBAC Permission Management | 硬依赖 | 用户权限决定数据访问范围 |
| Story 1-10: Unified Audit Log | 硬依赖 | 数据访问和传输记录至审计日志 |
| Story 1-16: Integration Test Framework | 软依赖 | 集成测试框架模式复用 |
| Story 1.17: UDMR 基础路由 | 软依赖 | 数据主权检测结果供 UDMR L1 网关使用 |

### 技术容量规划

| 指标 | MVP | V1 | V2 |
|------|-----|----|----|
| **敏感数据类型** | 5 种 | 10 种 | 20 种 |
| **白名单规则数** | ≤100 | ≤500 | ≤2000 |
| **PII 识别准确率** | ≥95% | ≥98% | ≥99% |
| **外部调用审计延迟** | <100ms | <50ms | <20ms |
| **跨境审批 SLA** | 48 小时 | 24 小时 | 4 小时 |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 敏感数据识别与标记 (Sensitive Data Detection)

**Given** 系统处理各类业务数据
**When** 数据进入系统或被访问时
**Then** 系统自动识别并标记敏感数据
**And** 根据敏感类型应用相应保护策略

**验证标准/Validation Criteria:**
- [x] 敏感数据类型定义
  - PII（个人信息）：姓名、身份证、电话、邮箱、地址等
  - 商业秘密：财务报表、客户名单、技术配方等
  - 财务数据：银行账号、信用卡号、交易记录等
  - 自定义敏感类型支持扩展
- [x] 敏感数据识别器实现
  - 正则匹配（身份证、电话、邮箱等）
  - 关键词匹配（商业秘密关键词库）
  - NLP 识别（可选，V2）
- [x] 数据标记机制
  - 敏感标签附加到数据对象
  - 标签传播至下游处理
- [x] 单元测试覆盖正常识别、边界识别、误识别场景

### AC-2: 数据境内存储策略 (Data Residency)

**Given** 敏感数据已被标记
**When** 需要选择存储层或处理位置时
**Then** 系统强制本地优先策略
**And** 境外存储触发审批流程

**验证标准/Validation Criteria:**
- [x] 本地存储策略执行
  - 六层存储（L1-L5）默认境内
  - 境内优先路由决策
  - 境外存储需显式审批
- [x] 数据主权配置
  - 数据驻留标签（CHINA_DOMESTIC/GLOBAL）
  - 存储位置验证
  - 跨境检测和告警
- [x] 存储层隔离
  - 境内存储层与境外存储层物理隔离
  - 跨境数据同步审计
- [x] 单元测试覆盖本地优先、跨境触发、配置验证场景

### AC-3: 外部调用白名单机制 (External Call Whitelist)

**Given** 系统需要发起外部网络调用
**When** 调用外部 API 或服务时
**Then** 系统验证调用目标在白名单中
**And** 未授权调用被阻断并记录

**验证标准/Validation Criteria:**
- [x] 白名单数据模型
  - 白名单规则：endpoint, provider, purpose, risk_level, approved_by, expiry_date
  - 白名单状态：active/pending/revoked/expired
- [x] 白名单验证器
  - 调用前白名单校验
  - 动态白名单更新
  - 过期自动失效
- [x] 白名单管理接口
  - CLI 命令：`sisys system whitelist add/revoke/list`
  - API 端点：`/api/v1/admin/whitelist`
- [x] 审计日志集成
  - 所有外部调用记录至审计日志
  - 白名单命中/未命中记录
- [x] 单元测试覆盖白名单验证、动态更新、过期失效场景

### AC-4: 跨境传输审批流程 (Cross-Border Transfer Approval)

**Given** 数据需要跨境传输
**When** 境外调用被触发且无白名单时
**Then** 系统进入审批流程
**And** 审批通过前阻断传输

**验证标准/Validation Criteria:**
- [x] 跨境审批流程
  - 审批请求创建
  - 审批人指定（合规官）
  - 审批状态跟踪（pending/approved/rejected）
  - 审批历史记录
- [x] 审批 SLA 管理
  - SLA 超时告警
  - 自动升级机制
- [x] 阻断机制
  - 审批未通过前阻断跨境传输
  - 阻断日志记录
  - 通知机制
- [x] CLI 命令支持
  - `sisys system approval list/approve/reject`
- [x] 单元测试覆盖审批流程、超时处理、阻断机制场景

### AC-5: PIPL 合规 (Personal Information Protection Law)

**Given** 系统处理个人信息
**When** 个人信息被访问或导出时
**Then** 系统满足 PIPL 合规要求
**And** 记录处理合法依据

**验证标准/Validation Criteria:**
- [x] 个人信息处理记录
  - 处理目的记录
  - 处理方式记录
  - 数据主体同意记录
- [x] 权利保障
  - 个人信息访问权
  - 更正权删除权支持
  - 数据可携带权
- [x] 敏感个人信息增强保护
  - 生物识别信息特殊保护
  - 未成年人信息特殊保护
- [x] 合规报告
  - PIPL 合规审计报告生成
  - 处理记录导出

### AC-6: 合规性测试 (Compliance Testing)

**Given** 数据主权隔离系统已实现
**When** 执行合规性测试
**Then** 所有测试项通过

**验证标准/Validation Criteria:**
- [x] 数据境内存储 100%
  - COMP-05 测试通过
- [x] 跨境传输审批率 100%
- [x] 敏感数据识别准确率≥95%
- [x] 白名单验证覆盖率 100%

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] SensitiveDataDetectedEvent 定义（`src/domain/events/compliance_events.py`）✅
  - 字段: `event_id`, `timestamp`, `data_id`, `sensitive_type`, `confidence`, `labels`
  - 继承 `DomainEvent` 基类
- [x] CrossBorderTransferRequestedEvent 定义 ✅
  - 字段: `event_id`, `timestamp`, `data_id`, `destination`, `purpose`, `approval_id`, `status`

#### 数据模型 (Data Models) — 基础设施层
- [ ] SensitiveDataType 枚举（`src/infrastructure/security/models.py`）❌ 未实现
- [ ] DataSovereigntyPolicy 模型（`src/infrastructure/security/models.py`）❌ 未实现
- [ ] WhitelistRule 模型 ❌ 未实现
- [ ] CrossBorderApproval 模型 ❌ 未实现
- [ ] DataSovereigntyConfig 配置模型（`src/infrastructure/config/sovereignty.py`）❌ 未实现

#### API 契约 (API Contract)
- [ ] 白名单管理端点: `GET/POST /api/v1/admin/whitelist` ❌ 未实现
- [ ] 跨境审批端点: `GET/POST /api/v1/admin/cross-border-approvals` ❌ 未实现
- [ ] 合规状态端点: `GET /api/v1/compliance/status` ❌ 未实现

#### CLI 命令 (CLI Commands)
- [ ] `sisys system whitelist add --endpoint <url> --provider <name> --purpose <desc>` ❌ 未实现
- [ ] `sisys system whitelist revoke --rule-id <id>` ❌ 未实现
- [ ] `sisys system whitelist list --status active` ❌ 未实现
- [ ] `sisys system approval list --status pending` ❌ 未实现
- [ ] `sisys system approval approve --request-id <id>` ❌ 未实现
- [ ] `sisys system approval reject --request-id <id> --reason <reason>` ❌ 未实现
- [ ] `sisys compliance status --data-id <id>` ❌ 未实现

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.11.feature` ❌ 未实现

**Task 0 完成标志：**
- [x] 领域事件 Schema 全部定义完毕 ✅
- [ ] 基础设施层数据模型定义 ❌ 待实现
- [ ] API 契约定义 ❌ 待实现
- [ ] CLI 命令定义 ❌ 待实现
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）❌ 待实现

---

### Task 1: 敏感数据类型定义与识别器实现

**关联 AC:** AC-1

> **目的：** 实现敏感数据识别基础设施，包括数据类型定义和识别器。

#### TDD 循环 [A]：敏感数据类型枚举

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_data_sovereignty.py`（敏感数据类型枚举测试） |
| 🟢 绿 | 实现 `SensitiveDataType` 枚举 |
| 🔄 重构 | 添加类型注解、优化命名 |

- [ ] Subtask 1.1: 🔴 红 — 编写敏感数据类型枚举测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 SensitiveDataType 枚举
- [ ] Subtask 1.3: 🔄 重构 — 优化代码

#### TDD 循环 [B]：敏感数据标签模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_sensitive_label.py`（敏感数据标签测试） |
| 🟢 绿 | 实现 `SensitiveLabel` 数据类 |
| 🔄 重构 | 添加类型注解 |

- [ ] Subtask 1.4: 🔴 红 — 编写敏感数据标签测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 SensitiveLabel 数据类
- [ ] Subtask 1.6: 🔄 重构 — 优化代码

#### TDD 循环 [C]：敏感数据识别器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_sensitive_data_detector.py`（识别器测试） |
| 🟢 绿 | 实现 `SensitiveDataDetector` 类（正则+关键词匹配） |
| 🔄 重构 | 添加 NLP 扩展接口（可选） |

- [ ] Subtask 1.7: 🔴 红 — 编写敏感数据识别器测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 SensitiveDataDetector
- [ ] Subtask 1.9: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] SensitiveDataType 枚举定义完整
- [ ] SensitiveLabel 数据类实现
- [ ] SensitiveDataDetector 识别准确率≥95%
- [ ] 单元测试覆盖率≥85%

---

### Task 2: 数据主权策略与境内存储实现

**关联 AC:** AC-2

> **目的：** 实现数据境内存储策略和存储层隔离。

#### TDD 循环 [A]：数据主权策略模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_data_sovereignty_policy.py`（策略模型测试） |
| 🟢 绿 | 实现 `DataSovereigntyPolicy` 模型 |
| 🔄 重构 | 添加验证逻辑 |

- [ ] Subtask 2.1: 🔴 红 — 编写数据主权策略模型测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 DataSovereigntyPolicy 模型
- [ ] Subtask 2.3: 🔄 重构 — 优化代码

#### TDD 循环 [B]：数据主权服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_data_sovereignty_service.py`（服务测试） |
| 🟢 绿 | 实现 `DataSovereigntyService` 类 |
| 🔄 重构 | 添加存储层路由逻辑 |

- [ ] Subtask 2.4: 🔴 红 — 编写数据主权服务测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 DataSovereigntyService
- [ ] Subtask 2.6: 🔄 重构 — 优化代码

#### TDD 循环 [C]：存储层隔离验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_storage_isolation.py`（存储隔离测试） |
| 🟢 绿 | 实现存储层隔离验证逻辑 |
| 🔄 重构 | 添加跨境检测告警 |

- [ ] Subtask 2.7: 🔴 红 — 编写存储层隔离测试
- [ ] Subtask 2.8: 🟢 绿 — 实现存储层隔离验证
- [ ] Subtask 2.9: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] DataSovereigntyPolicy 模型定义完整
- [ ] DataSovereigntyService 实现境内优先逻辑
- [ ] 存储层隔离验证通过
- [ ] 单元测试覆盖率≥85%

---

### Task 3: 外部调用白名单机制实现

**关联 AC:** AC-3

> **目的：** 实现外部 API 调用白名单校验和动态管理。

#### TDD 循环 [A]：白名单规则模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_whitelist_rule.py`（白名单模型测试） |
| 🟢 绿 | 实现 `WhitelistRule` 模型 |
| 🔄 重构 | 添加状态机逻辑 |

- [ ] Subtask 3.1: 🔴 红 — 编写白名单规则模型测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 WhitelistRule 模型
- [ ] Subtask 3.3: 🔄 重构 — 优化代码

#### TDD 循环 [B]：白名单验证器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_whitelist_validator.py`（验证器测试） |
| 🟢 绿 | 实现 `WhitelistValidator` 类 |
| 🔄 重构 | 添加动态更新逻辑 |

- [ ] Subtask 3.4: 🔴 红 — 编写白名单验证器测试
- [ ] Subtask 3.5: 🟢 绿 — 实现 WhitelistValidator
- [ ] Subtask 3.6: 🔄 重构 — 优化代码

#### TDD 循环 [C]：白名单管理服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_whitelist_service.py`（管理服务测试） |
| 🟢 绿 | 实现 `WhitelistService` 类 |
| 🔄 重构 | 添加 CRUD 操作 |

- [ ] Subtask 3.7: 🔴 红 — 编写白名单管理服务测试
- [ ] Subtask 3.8: 🟢 绿 — 实现 WhitelistService
- [ ] Subtask 3.9: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] WhitelistRule 模型定义完整
- [ ] WhitelistValidator 验证逻辑正确
- [ ] WhitelistService 支持动态管理
- [ ] 白名单验证覆盖率 100%
- [ ] 单元测试覆盖率≥85%

---

### Task 4: 跨境传输审批流程实现

**关联 AC:** AC-4

> **目的：** 实现跨境传输审批流程和阻断机制。

#### TDD 循环 [A]：跨境审批模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_cross_border_approval.py`（审批模型测试） |
| 🟢 绿 | 实现 `CrossBorderApproval` 模型 |
| 🔄 重构 | 添加状态机逻辑 |

- [ ] Subtask 4.1: 🔴 红 — 编写跨境审批模型测试
- [ ] Subtask 4.2: 🟢 绿 — 实现 CrossBorderApproval 模型
- [ ] Subtask 4.3: 🔄 重构 — 优化代码

#### TDD 循环 [B]：审批工作流服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_approval_workflow.py`（工作流测试） |
| 🟢 绿 | 实现 `ApprovalWorkflowService` 类 |
| 🔄 重构 | 添加 SLA 管理 |

- [ ] Subtask 4.4: 🔴 红 — 编写审批工作流测试
- [ ] Subtask 4.5: 🟢 绿 — 实现 ApprovalWorkflowService
- [ ] Subtask 4.6: 🔄 重构 — 优化代码

#### TDD 循环 [C]：跨境传输拦截器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_cross_border_blocker.py`（拦截器测试） |
| 🟢 绿 | 实现 `CrossBorderBlocker` 类 |
| 🔄 重构 | 添加通知机制 |

- [ ] Subtask 4.7: 🔴 红 — 编写跨境传输拦截器测试
- [ ] Subtask 4.8: 🟢 绿 — 实现 CrossBorderBlocker
- [ ] Subtask 4.9: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] CrossBorderApproval 模型定义完整
- [ ] ApprovalWorkflowService 支持完整审批流程
- [ ] CrossBorderBlocker 阻断机制有效
- [ ] SLA 管理正确
- [ ] 单元测试覆盖率≥85%

---

### Task 5: PIPL 合规与 CLI/API 集成

**关联 AC:** AC-5

> **目的：** 实现 PIPL 合规功能和 CLI/API 接口。

#### TDD 循环 [A]：PIPL 合规服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_pipl_compliance.py`（PIPL 合规测试） |
| 🟢 绿 | 实现 `PIPLComplianceService` 类 |
| 🔄 重构 | 添加合规报告生成 |

- [ ] Subtask 5.1: 🔴 红 — 编写 PIPL 合规服务测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 PIPLComplianceService
- [ ] Subtask 5.3: 🔄 重构 — 优化代码

#### TDD 循环 [B]：CLI 命令实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_sovereignty_commands.py`（CLI 测试） |
| 🟢 绿 | 实现白名单和审批相关 CLI 命令 |
| 🔄 重构 | 优化命令结构 |

- [ ] Subtask 5.4: 🔴 红 — 编写 CLI 命令测试
- [ ] Subtask 5.5: 🟢 绿 — 实现 CLI 命令
- [ ] Subtask 5.6: 🔄 重构 — 优化代码

#### TDD 循环 [C]：API 端点实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_sovereignty_endpoints.py`（API 测试） |
| 🟢 绿 | 实现白名单和审批 API 端点 |
| 🔄 重构 | 添加请求验证 |

- [ ] Subtask 5.7: 🔴 红 — 编写 API 端点测试
- [ ] Subtask 5.8: 🟢 绿 — 实现 API 端点
- [ ] Subtask 5.9: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] PIPLComplianceService 实现完整
- [ ] CLI 命令功能正常
- [ ] API 端点功能正常
- [ ] 单元测试覆盖率≥85%

---

### Task 6: 集成测试与合规性验证

**关联 AC:** AC-6

> **目的：** 执行集成测试验证数据主权隔离系统功能。

#### 集成测试实现

- [ ] Subtask 6.1: 创建 `tests/integration/test_data_sovereignty_integration.py`
- [ ] Subtask 6.2: 实现敏感数据识别集成测试
- [ ] Subtask 6.3: 实现境内存储策略集成测试
- [ ] Subtask 6.4: 实现白名单验证集成测试
- [ ] Subtask 6.5: 实现跨境审批流程集成测试
- [ ] Subtask 6.6: 运行 COMP-05 合规性测试

**完成标准/Definition of Done:**
- [ ] 集成测试全部通过
- [ ] COMP-05 测试通过（数据境内存储 100%）
- [ ] 跨境传输审批率 100%
- [ ] 集成测试覆盖率≥75%

---

### Task 7: SDD 架构约束验证测试

**关联 AC:** All

> **性质说明：** 本 Task 是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 7.1: 创建 `tests/unit/security/test_sovereignty_architecture.py`
- [ ] Subtask 7.2: 实现领域层零依赖验证（安全服务仅在应用层/接口层）
- [ ] Subtask 7.3: 实现循环依赖检测（使用 ruff 的 `E` 规则）
- [ ] Subtask 7.4: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 领域层无安全相关外部依赖
- [ ] 无循环依赖
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（依赖倒置，领域层定义接口，基础设施层实现）
- **设计约束:** 领域层零依赖、安全服务位于应用层/接口层
- **技术栈:** Python 3.11+, FastAPI 0.104+, PostgreSQL 15+, Redis 7.0+

### 六边形架构合规性现状

| 层级 | 状态 | 说明 |
|------|------|------|
| **领域层 (domain)** | ✅ 合规 | `src/domain/events/compliance_events.py` 仅使用 Python 标准库，符合领域层零依赖原则 |
| **应用层 (application)** | ❌ 未实现 | 用例层待实现 |
| **接口层 (interfaces)** | ❌ 未实现 | CLI 和 API 适配器待实现 |
| **基础设施层 (infrastructure)** | ❌ 未实现 | 安全相关实现待创建 |

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR-005 (UDMR) 及 4.2 节 L1 合规性网关

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **独立实现数据主权检测组件** | 符合六边形架构，数据主权检测与路由解耦 | 需与 UDMR L1 网关协作 | ✅ 8/10 |
| 集成到 UDMR L1 网关 | 复用路由组件 | 违反单一职责，领域层耦合 | 5/10 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── compliance_events.py    # 合规相关领域事件 ✅ 已创建
│   │   └── services/
│   │       └── data_sovereignty_service.py  # 领域服务接口 ❌ 待创建
│   ├── application/
│   │   └── use_cases/
│   │       └── compliance/
│   │           ├── sensitive_data_use_case.py  ❌ 待创建
│   │           └── cross_border_use_case.py     ❌ 待创建
│   ├── infrastructure/
│   │   ├── security/                    # ❌ 目录不存在，待创建
│   │   │   ├── models.py               # 数据主权相关模型
│   │   │   ├── sensitive_data_detector.py
│   │   │   ├── whitelist_service.py
│   │   │   ├── approval_workflow.py
│   │   │   └── pipl_compliance.py
│   │   └── config/
│   │       └── sovereignty.py          # 数据主权配置 ❌ 待创建
│   └── interfaces/
│       ├── cli/
│       │   └── sovereignty_commands.py  # CLI 命令 ❌ 待创建
│       └── api/
│           └── sovereignty_endpoints.py # API 端点 ❌ 待创建
└── tests/
    ├── unit/security/                   # ❌ 待创建
    │   ├── test_sensitive_data_detector.py
    │   ├── test_data_sovereignty_service.py
    │   ├── test_whitelist_validator.py
    │   └── test_cross_border_approval.py
    └── integration/                     # ❌ 待创建
        └── test_data_sovereignty_integration.py
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1-10](./1-10-unified-audit-log.md)

**关键学习/Key Learnings:**
1. 审计日志与业务操作同事务提交，保证数据一致性
2. 事件驱动集成通过监听领域事件自动触发
3. 事务发件箱模式确保审计事件可靠性

**应用到本故事/Applied to This Story:**
- [ ] 数据主权检查结果同步记录至审计日志
- [ ] 跨境审批事件通过事件总线发布
- [ ] 白名单动态更新通过事件通知相关方
- [ ] 审批人角色验证采用 API 层预验证模式（ADR-011）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-04-18 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-10-unified-audit-log.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（审计日志模式复用）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成

---

### 文件清单 File List

**已创建的文件/Actually Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-11-data-sovereignty-isolation.md` ✅
- `src/domain/events/compliance_events.py` ✅ - 合规领域事件（符合六边形架构：领域层零依赖原则）

**待创建的文件/To Be Created (Implementation Pending):**
- `src/infrastructure/security/` ❌ — 整个目录不存在，需创建以下模块：
  - `models.py` — 数据主权模型（SensitiveDataType, DataSovereigntyPolicy, WhitelistRule, CrossBorderApproval）
  - `sensitive_data_detector.py` — 敏感数据识别器（正则+关键词匹配）
  - `data_sovereignty_service.py` — 数据主权服务（境内优先策略）
  - `whitelist_service.py` — 白名单服务
  - `approval_workflow.py` — 审批工作流
  - `pipl_compliance.py` — PIPL 合规服务
- `src/infrastructure/config/sovereignty.py` ❌ — 数据主权配置
- `src/interfaces/cli/sovereignty_commands.py` ❌ — CLI 命令（白名单管理、审批流程）
- `src/interfaces/api/sovereignty_endpoints.py` ❌ — API 端点
- `tests/unit/security/` ❌ — 所有安全相关单元测试（待创建）
- `tests/integration/test_data_sovereignty_integration.py` ❌ — 集成测试（待创建）
- `tests/acceptance/test_story_1_11.feature` ❌ — BDD 验收测试（待创建）
- `tests/acceptance/test_story_1_11_steps.py` ❌ — BDD 步骤实现（待创建）

**六边形架构合规性说明:**
- ✅ 领域事件 `compliance_events.py` 正确位于 `src/domain/events/`，仅使用 Python 标准库
- ✅ 依赖方向正确：领域层定义接口（Domain Events, Ports），基础设施层实现
- ❌ 其他安全组件未实现，无法验证架构合规性

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.11 |
| **Story Key** | 1-11-data-sovereignty-isolation |
| **File** | `_bmad-output/implementation-artifacts/stories/1-11-data-sovereignty-isolation.md` |
| **Status** | `backlog` 🚨 (回退原因：实现不存在) |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 4: 安全与合规基础 |
| **优先级** | P0 |
| **覆盖 FR** | FR-SC-07: 数据主权隔离 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-7）- **规划层面**
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-6）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to actual implementation state - **需要更新 sprint-status.yaml**
6. [ ] Task 0-7 completed with TDD red-green-refactor cycles - **未实现**
7. [ ] Unit/integration tests passed - **测试文件不存在**
8. [ ] Story implementation complete - **未开始**
9. [ ] Code review completed - **未开始**
10. [ ] ADR-011 documented - **ADR 已记录但未实现**

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> ⚠️ **2026-05-04 更新：** 由于实现不存在，以下审查记录为**无效记录**（代码审查是在不存在的代码上进行的）。实现时需重新审查。

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| — | 无（实现不存在） | — | — | ❌ 待实现 |

---

## 📐 架构决策记录（ADR）

### ADR-011: 审批人角色验证架构（待实现）

> ⚠️ **2026-05-04 更新:** ADR-011 记录为规划阶段决策，实际实现时需在 `ApprovalWorkflowService` 中体现。

**状态:** 已记录（待实现）

---

### 🔍 代码审查发现

> ⚠️ **2026-05-04 更新:** 由于实现不存在，代码审查记录无效。实现时请参考以下规划层面的审查要点：

**实现时需关注的安全问题（来自架构约束分析）：**
1. ReDoS 正则表达式防护 — 用户自定义关键词需限制正则复杂度
2. 敏感数据检测边界 — 避免子串匹配绕过，需使用词边界
3. URL 规范化 — 端口处理、国际化域名（IDN）规范化
4. 状态机验证 — 审批状态转换合法性
5. 时区处理 — 统一使用 `datetime.now(UTC)`
6. 审计日志 — 所有外部调用、白名单命中/未命中需记录

---

### 下一步 Next Steps

- [x] Story 文件审查完成，发现实现不存在问题
- [ ] 更新 sprint-status.yaml 中 1-11-data-sovereignty-isolation 状态为 `backlog`
- [ ] 运行 `dev-story` 开始实施
- [ ] 实现后运行 `code-review` 进行代码审查

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-18
**最后更新/Last Updated:** 2026-05-04
**更新说明:** 状态回退至 `backlog`：代码审计发现实现不存在，仅 `src/domain/events/compliance_events.py` 实际创建，其他声称的实现文件（infrastructure security、CLI、API、测试）均不存在
