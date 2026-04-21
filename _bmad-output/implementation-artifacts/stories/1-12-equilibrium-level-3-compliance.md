# Story 1.12: 等保 2.0 三级基础要求

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

> **🔧 技术约束（v1.0）：**
> 1. **复用 Story 1.9/1.10/1.11 安全基础设施** — AuthService/PermissionService/AuditService/DataSovereigntyService
> 2. **安全层覆盖率要求≥85%** — 继承 Story 1.9 安全层覆盖率标准
> 3. **集成测试覆盖率≥75%** — 验证多组件协同
> 4. **无高风险项，中危漏洞<5个** — 通过公安部指定测评机构测评
> 5. **等保 2.0 三级通过** — 覆盖身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复

---

## 📖 Story 描述

**As a** 安全工程师,
**I want** 实现等保 2.0 三级基础要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）,
**So that** 通过公安部指定测评机构测评。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 4（安全与合规基础）的第四个也是最后一个故事，在 Story 1.9 (RBAC 权限管理)、Story 1.10 (统一审计日志) 和 Story 1.11 (数据主权隔离) 基础上实现等保 2.0 三级合规系统。等保 2.0 三级作为系统合规的核心认证，承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **身份鉴别** | 双因子认证，验证用户身份 | MFA 覆盖率 100% |
| **访问控制** | 细粒度 RBAC，控制资源访问 | RBAC 覆盖率 100% |
| **安全审计** | 完整日志记录，可追溯 | 审计日志完整性 100% |
| **入侵防范** | 渗透测试，发现并修复漏洞 | 无高风险，中危<5 |
| **数据完整性** | 数据加密，防篡改 | 加密覆盖率 100% |
| **备份恢复** | 定期备份，快速恢复 | 恢复时间 <1 小时 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 4: 安全与合规基础

**覆盖 FR:**
- FR-SC-08: 等保 2.0 三级（Story 1.12）

**覆盖 NFR:**
- NFR-COMP-01: 合规审计（审计日志完整性 100%）
- NFR-COMP-02: 等保 2.0 身份鉴别
- NFR-COMP-03: 等保 2.0 访问控制
- NFR-COMP-04: 等保 2.0 安全审计

### 依赖关系 Dependencies

| 依赖 Story | 依赖类型 | 依赖原因 |
|-----------|---------|---------|
| Story 1-1: Hexagonal Architecture Skeleton | 硬依赖 | 六边形架构模式、依赖注入容器 |
| Story 1-5: PostgreSQL Relational Layer | 硬依赖 | RBAC 策略和审计日志存储于 PostgreSQL |
| Story 1-9: RBAC Permission Management | 硬依赖 | 细粒度 RBAC 权限系统 |
| Story 1-10: Unified Audit Log | 硬依赖 | 安全审计日志基础设施 |
| Story 1-11: Data Sovereignty Isolation | 硬依赖 | 数据主权隔离，PIPL 合规 |
| Story 1-16: Integration Test Framework | 软依赖 | 集成测试框架模式复用 |

### 技术容量规划

| 指标 | MVP | V1 | V2 |
|------|-----|----|----|
| **MFA 覆盖率** | 100% | 100% | 100% |
| **RBAC 覆盖率** | 100% | 100% | 100% |
| **审计日志完整性** | 100% | 100% | 100% |
| **高风险漏洞** | 0 | 0 | 0 |
| **中危漏洞** | <5 | <3 | 0 |
| **渗透测试覆盖率** | ≥90% | ≥95% | 100% |
| **备份恢复时间** | <1h | <30min | <15min |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 身份鉴别 (Identity Authentication)

**Given** 用户访问系统
**When** 用户登录或执行敏感操作时
**Then** 系统执行双因子认证
**And** 验证用户身份合法

**验证标准/Validation Criteria:**
- [ ] 双因子认证（MFA）实现
  - TOTP（基于时间的一次性密码）
  - 支持 Authenticator App
- [ ] 身份鉴别测试通过
  - COMP-02 测试通过
- [ ] MFA 覆盖率 100%

### AC-2: 访问控制 (Access Control)

**Given** 用户已通过身份鉴别
**When** 用户请求访问资源时
**Then** 系统执行细粒度 RBAC 检查
**And** 根据权限决定是否允许访问

**验证标准/Validation Criteria:**
- [ ] 细粒度 RBAC 实现
  - 基于 Story 1.9 扩展
  - 支持资源级权限
- [ ] 访问控制测试通过
  - COMP-03 测试通过
- [ ] RBAC 覆盖率 100%

### AC-3: 安全审计 (Security Audit)

**Given** 系统运行中
**When** 用户执行操作或系统事件发生时
**Then** 系统记录完整审计日志
**And** 日志不可篡改、可追溯

**验证标准/Validation Criteria:**
- [ ] 审计日志完整性
  - 基于 Story 1.10 扩展
  - 覆盖所有安全相关事件
- [ ] 安全审计测试通过
  - COMP-04 测试通过
- [ ] 审计日志完整性 100%

### AC-4: 入侵防范 (Intrusion Prevention)

**Given** 系统面临外部攻击风险
**When** 执行渗透测试时
**Then** 系统能检测并抵御常见攻击
**And** 无高风险项，中危漏洞<5

**验证标准/Validation Criteria:**
- [ ] 渗透测试覆盖率 ≥90%（依据 GB/T 22239-2019 三级要求）
- [ ] 高风险项 = 0
- [ ] 中危漏洞 < 5
- [ ] SEC-01 ~ SEC-07 测试通过

### AC-5: 数据完整性 (Data Integrity)

**Given** 数据在传输和存储中
**When** 数据被访问或修改时
**Then** 系统验证数据完整性
**And** 检测并报告任何篡改

**验证标准/Validation Criteria:**
- [ ] 数据加密实现
  - 传输加密（TLS）
  - 存储加密（AES-256）
- [ ] 完整性验证机制
  - Hash 校验
  - 数字签名
- [ ] 加密覆盖率 100%

### AC-6: 备份恢复 (Backup and Recovery)

**Given** 系统数据需要保护
**When** 需要恢复数据时
**Then** 系统能从备份快速恢复
**And** 恢复时间满足 SLA

**验证标准/Validation Criteria:**
- [ ] 定期备份机制
  - 每日全量备份
  - 增量备份
- [ ] 备份恢复测试通过
  - REL-03 测试通过
- [ ] 恢复时间 < 1 小时

### AC-7: 合规性测试 (Compliance Testing)

**Given** 等保 2.0 三级合规系统已实现
**When** 执行合规性测试时
**Then** 所有测试项通过
**And** 通过公安部指定测评机构测评

**验证标准/Validation Criteria:**
- [ ] COMP-01 ~ COMP-05 测试通过
- [ ] 安全层覆盖率 ≥85%
- [ ] 集成测试覆盖率 ≥75%
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过
- [ ] 安全扫描通过（Bandit）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| All | SDD 规范定义 | Task 0 | Subtask 0.1-0.9 | N/A（规范定义阶段） |
| AC-1 | MFA 双因子认证 | Task 1 | Subtask 1.1-1.3 | `test_equilibrium.py` |
| AC-1 | TOTP 生成/验证 | Task 2 | Subtask 2.1-2.3 | `test_equilibrium.py` |
| AC-1 | MFA 服务 | Task 3 | Subtask 3.1-3.3 | `test_equilibrium.py` |
| AC-4 | 入侵检测 | Task 4 | Subtask 4.1-4.3 | `test_equilibrium.py` |
| AC-4 | 渗透测试 | Task 5 | Subtask 5.1-5.3 | `test_equilibrium.py` |
| AC-4 | 威胁评分 | Task 6 | Subtask 6.1-6.3 | `test_equilibrium.py` |
| AC-5 | 加密服务 | Task 7 | Subtask 7.1-7.3 | `test_equilibrium.py` |
| AC-5 | 完整性验证 | Task 8 | Subtask 8.1-8.3 | `test_equilibrium.py` |
| AC-5 | 数字签名 | Task 9 | Subtask 9.1-9.3 | `test_equilibrium.py` |
| AC-6 | 备份恢复 | Task 10 | Subtask 10.1-10.3 | `test_equilibrium.py` |
| AC-7 | 合规报告 | Task 11 | Subtask 11.1-11.3 | `test_equilibrium.py` |
| AC-2 | RBAC 访问控制扩展 | Task 12 | Subtask 12.1-12.3 | `test_equilibrium.py` |
| AC-3 | 审计日志扩展 | Task 12 | Subtask 12.4-12.6 | `test_equilibrium.py` |
| All | CLI 命令 | Task 13 | Subtask 13.1-13.3 | `test_equilibrium.py` |
| All | API 端点 | Task 13 | Subtask 13.4-13.6 | `test_equilibrium.py` |
| All | 集成测试 | Task 14 | Subtask 14.1-14.5 | `test_security_compliance_integration.py` |
| All | 架构验证 | Task 15 | Subtask 15.1-15.4 | `test_equilibrium.py` |

> **说明：** AC-2（RBAC）和 AC-3（审计日志）主要依赖 Story 1.9/1.10，Task 12 仅做扩展验证。Task 0 是 SDD 规范定义阶段，为后续 Task 提供 Schema 依据。

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> Task 0（SDD 规范定义）是例外，它定义规范而非实现代码，因此不需要 TDD 红→绿→重构循环。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7 (全部)

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。
> **TDD 说明：** Task 0 是 SDD 规范定义阶段，定义 Schema/API 契约/验收标准，本身不是代码实现，无需 TDD 红→绿→重构循环。后续 Task 1-15 的 TDD 测试以 Task 0 定义的规范为输入。

#### TDD 循环 [A]：SDD 规范定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_story_1.12.feature`（Gherkin 验收测试，预期失败） |
| 🟢 绿 | 定义所有领域事件 Schema、API 契约、数据模型 |
| 🔄 重构 | 规范化文档结构、补充说明 |

#### Subtask 分解

- [x] Subtask 0.1: 🔴 红 → 🟢 绿 — 定义 `MFAChallengeIssuedEvent`（`src/domain/events/compliance_events.py`）
  - 字段: `event_id`, `timestamp`, `user_id`, `challenge_type`, `status`
  - 继承 `DomainEvent` 基类
- [x] Subtask 0.2: 🔴 红 → 🟢 绿 — 定义 `IntrusionDetectedEvent`
  - 字段: `event_id`, `timestamp`, `source_ip`, `attack_type`, `severity`, `action_taken`
- [x] Subtask 0.3: 🔴 红 → 🟢 绿 — 定义 `DataIntegrityViolationEvent`
  - 字段: `event_id`, `timestamp`, `data_id`, `expected_hash`, `actual_hash`, `source`
- [x] Subtask 0.4: 🔴 红 → 🟢 绿 — 定义 `MFAChallenge` 数据模型（`src/infrastructure/security/models.py`）
  - 字段: `id`, `user_id`, `challenge_type`, `secret`, `attempts`, `expires_at`, `status`
- [x] Subtask 0.5: 🔴 红 → 🟢 绿 — 定义 `BackupRecord` 和 `IntegrityCheck` 模型
- [x] Subtask 0.6: 🔴 红 → 🟢 绿 — 定义 API 契约（OpenAPI）
  - MFA 端点: `POST /api/v1/auth/mfa/setup`, `POST /api/v1/auth/mfa/verify`
  - 合规状态端点: `GET /api/v1/compliance/status`
  - 备份管理端点: `GET/POST /api/v1/admin/backups`
- [x] Subtask 0.7: 🔴 红 → 🟢 绿 — 定义 CLI 命令规范
  - `sisys system mfa enable --user-id <id>`
  - `sisys system mfa verify --user-id <id> --code <code>`
  - `sisys compliance status --level 3`
  - `sisys system backup create --type full|incremental`
  - `sisys system backup restore --backup-id <id>`
  - `sisys system integrity check --data-type <type>`
- [x] Subtask 0.8: 🔴 红 — 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.12.feature`（预期失败）
- [x] Subtask 0.9: 🔴 红 → 🟢 绿 — 规范化文档结构、补充说明

**完成标准/Definition of Done:**
- [x] 领域事件 Schema 全部定义完毕（MFAChallengeIssuedEvent/IntrusionDetectedEvent/DataIntegrityViolationEvent）
- [x] 数据模型全部定义完毕（MFAChallenge/BackupRecord/IntegrityCheck）
- [x] API 契约全部定义完毕（OpenAPI YAML）
- [x] CLI 命令规范全部定义完毕
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### Task 1: MFA 配置模型实现

**关联 AC:** AC-1

> **目的：** 实现 MFA 挑战模型和配置。

#### TDD 循环 [A]：MFA 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（MFAChallenge 模型测试） |
| 🟢 绿 | 实现 `MFAChallenge` 模型和 `MFAConfig` |
| 🔄 重构 | 添加类型注解、优化命名 |

- [x] Subtask 1.1: 🔴 红 — 编写 MFA 配置模型测试
- [x] Subtask 1.2: 🟢 绿 — 实现 MFAChallenge 模型
- [x] Subtask 1.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] MFA 配置模型定义完整
- [x] TDD 循环通过
- [x] 单元测试覆盖率 ≥85%

---

### Task 2: TOTP 生成器和验证器实现

**关联 AC:** AC-1

> **目的：** 实现 TOTP（基于时间的一次性密码）生成和验证功能。

#### TDD 循环 [A]：TOTP 生成器和验证器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（TOTP 测试） |
| 🟢 绿 | 实现 `TOTPGenerator` 和 `TOTPVerifier` 类 |
| 🔄 重构 | 添加错误处理、日志和密钥轮换支持 |

- [x] Subtask 2.1: 🔴 红 — 编写 TOTP 生成器/验证器测试
- [x] Subtask 2.2: 🟢 绿 — 实现 TOTPGenerator/TOTPVerifier
- [x] Subtask 2.3: 🔄 重构 — 优化代码，添加密钥轮换

**完成标准/Definition of Done:**
- [x] TOTP 生成/验证准确率 100%
- [x] 支持 30 秒过期时间
- [x] TDD 循环通过
- [x] 单元测试覆盖率 ≥85%

---

### Task 3: MFA 服务实现

**关联 AC:** AC-1

> **目的：** 实现 MFA 服务，整合 TOTP 并与 Story 1.9 的权限系统集成。

#### TDD 循环 [A]：MFA 服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（MFAService 测试） |
| 🟢 绿 | 实现 `MFAService` 类 |
| 🔄 重构 | 添加审计日志集成（Story 1.10）、API 层预验证模式（ADR-011） |

- [x] Subtask 3.1: 🔴 红 — 编写 MFA 服务测试
- [x] Subtask 3.2: 🟢 绿 — 实现 MFAService
- [x] Subtask 3.3: 🔄 重构 — 优化代码，集成审计日志（继承 Story 1.11 API 层预验证模式）

**完成标准/Definition of Done:**
- [x] MFA 服务实现完整
- [x] MFA 覆盖率 100%
- [x] TDD 循环通过
- [x] 单元测试覆盖率 ≥85%

---

### Task 4: 入侵检测器实现

**关联 AC:** AC-4

> **目的：** 实现入侵检测基础设施，检测常见攻击模式。

#### TDD 循环 [A]：入侵检测器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（入侵检测测试） |
| 🟢 绿 | 实现 `IntrusionDetector` 类 |
| 🔄 重构 | 添加规则引擎、实时告警 |

- [x] Subtask 4.1: 🔴 红 — 编写入侵检测器测试
- [x] Subtask 4.2: 🟢 绿 — 实现 IntrusionDetector
- [x] Subtask 4.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 入侵检测器实现完整
- [x] 支持常见攻击模式检测
- [x] TDD 循环通过
- [x] 渗透测试覆盖率 ≥90%

---

### Task 5: 渗透测试套件实现

**关联 AC:** AC-4

> **目的：** 实现基于《信息安全技术 信息系统安全等级保护基本要求》（GB/T 22239-2019）的渗透测试。

#### TDD 循环 [A]：渗透测试套件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（渗透测试） |
| 🟢 绿 | 实现等保 2.0 三级渗透测试检测规则 |
| 🔄 重构 | 添加报告生成 |

- [x] Subtask 5.1: 🔴 红 — 编写渗透测试用例
- [x] Subtask 5.2: 🟢 绿 — 实现渗透测试检测规则
- [x] Subtask 5.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 渗透测试覆盖率 ≥90%
- [x] 高风险项 = 0
- [x] 中危漏洞 < 5
- [x] TDD 循环通过

---

### Task 6: 威胁评分服务实现

**关联 AC:** AC-4

> **目的：** 实现威胁评分服务，量化威胁等级。

#### TDD 循环 [A]：威胁评分服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（威胁评分测试） |
| 🟢 绿 | 实现 `ThreatScoringService` 类 |
| 🔄 重构 | 添加实时告警 |

- [x] Subtask 6.1: 🔴 红 — 编写威胁评分测试
- [x] Subtask 6.2: 🟢 绿 — 实现 ThreatScoringService
- [x] Subtask 6.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 威胁评分服务准确率 ≥85%
- [x] 等保 2.0 入侵防范测试通过
- [x] TDD 循环通过

---

### Task 7: 加密服务实现

**关联 AC:** AC-5

> **目的：** 实现数据加密服务（AES-256）。

#### TDD 循环 [A]：加密服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（加密服务测试） |
| 🟢 绿 | 实现 `EncryptionService` 类（AES-256） |
| 🔄 重构 | 添加密钥轮换、TLS 支持 |

- [x] Subtask 7.1: 🔴 红 — 编写加密服务测试
- [x] Subtask 7.2: 🟢 绿 — 实现 EncryptionService
- [x] Subtask 7.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 加密服务实现完整（AES-256）- 复用 Story 1.11 EncryptionService
- [x] 加密覆盖率 100%
- [x] TDD 循环通过

---

### Task 8: 完整性验证器实现

**关联 AC:** AC-5

> **目的：** 实现数据完整性验证（Hash 校验）。

#### TDD 循环 [A]：完整性验证器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（完整性测试） |
| 🟢 绿 | 实现 `IntegrityVerifier` 类 |
| 🔄 重构 | 添加 Hash 算法选择（SHA-256/SHA-512） |

- [x] Subtask 8.1: 🔴 红 — 编写完整性验证测试
- [x] Subtask 8.2: 🟢 绿 — 实现 IntegrityVerifier
- [x] Subtask 8.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 完整性验证准确率 100%
- [x] TDD 循环通过

---

### Task 9: 数字签名服务实现

**关联 AC:** AC-5

> **目的：** 实现数字签名服务。

#### TDD 循环 [A]：数字签名服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（签名服务测试） |
| 🟢 绿 | 实现 `SignatureService` 类 |
| 🔄 重构 | 添加签名验证、证书管理 |

- [x] Subtask 9.1: 🔴 红 — 编写数字签名测试
- [x] Subtask 9.2: 🟢 绿 — 实现 SignatureService
- [x] Subtask 9.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 数字签名服务实现完整
- [x] TDD 循环通过

---

### Task 10: 备份恢复服务实现

**关联 AC:** AC-6

> **目的：** 实现备份恢复基础设施。

#### TDD 循环 [A]：备份服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（备份服务测试） |
| 🟢 绿 | 实现 `BackupService` 和 `RecoveryService` 类 |
| 🔄 重构 | 添加并发控制、进度跟踪 |

- [x] Subtask 10.1: 🔴 红 — 编写备份恢复服务测试
- [x] Subtask 10.2: 🟢 绿 — 实现 BackupService/RecoveryService
- [x] Subtask 10.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] BackupService 支持全量/增量备份
- [x] RecoveryService 支持快速恢复
- [x] 恢复时间 < 1 小时
- [x] TDD 循环通过

---

### Task 11: 合规报告服务实现

**关联 AC:** AC-7

> **目的：** 实现等保合规报告生成服务。

#### TDD 循环 [A]：合规报告服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（合规报告测试） |
| 🟢 绿 | 实现 `ComplianceReportService` 类 |
| 🔄 重构 | 添加报告模板、多格式导出 |

- [x] Subtask 11.1: 🔴 红 — 编写合规报告服务测试
- [x] Subtask 11.2: 🟢 绿 — 实现 ComplianceReportService
- [x] Subtask 11.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] 合规报告服务实现完整（等保合规状态通过API端点返回）
- [x] TDD 循环通过

---

### Task 12: RBAC 和审计日志扩展验证

**关联 AC:** AC-2, AC-3

> **目的：** 验证 Story 1.9/1.10 扩展到等保 2.0 要求。

#### TDD 循环 [A]：RBAC 访问控制扩展验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（RBAC 访问控制扩展测试） |
| 🟢 绿 | 实现资源级权限验证 |
| 🔄 重构 | 优化权限检查逻辑 |

- [x] Subtask 12.1: 🔴 红 — 编写资源级 RBAC 扩展测试
  - 测试用户-角色-资源三级权限模型
  - 测试资源级最小权限原则验证
- [x] Subtask 12.2: 🟢 绿 — 实现资源级权限验证
  - 扩展 Story 1.9 PermissionService
  - 支持 `resource_type` + `resource_id` 粒度
- [x] Subtask 12.3: 🔄 重构 — 优化代码
  - 验证 RBAC 覆盖率达到 100%
  - COMP-03 测试通过

#### TDD 循环 [B]：审计日志扩展验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/security/test_equilibrium.py`（审计日志扩展测试） |
| 🟢 绿 | 实现安全事件全覆盖 |
| 🔄 重构 | 优化日志记录 |

- [x] Subtask 12.4: 🔴 红 — 编写安全事件审计覆盖测试
  - MFA 相关安全事件（MFASetupAttempt, MFAVerifyAttempt, MFAChallengeIssued）
  - 入侵检测事件（IntrusionDetected, BruteForceAttempt）
  - 数据完整性事件（IntegrityViolation, BackupCompleted）
- [x] Subtask 12.5: 🟢 绿 — 实现安全事件全覆盖
  - 扩展 Story 1.10 AuditService
  - 覆盖等保 2.0 三级所有安全事件
- [x] Subtask 12.6: 🔄 重构 — 优化日志记录
  - 验证审计日志完整性达到 100%
  - COMP-04 测试通过

**完成标准/Definition of Done:**
- [x] RBAC 覆盖率 100%（用户-角色-资源三级权限）
- [x] 审计日志完整性 100%（覆盖 MFA/入侵检测/数据完整性事件）
- [x] COMP-03 访问控制测试通过
- [x] COMP-04 安全审计测试通过
- [x] TDD 循环通过

---

### Task 13: CLI/API 集成

**关联 AC:** All

> **目的：** 实现 CLI 命令和 API 端点。

#### TDD 循环 [A]：CLI 命令实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_equilibrium_commands.py`（CLI 测试） |
| 🟢 绿 | 实现 MFA/备份/完整性 CLI 命令 |
| 🔄 重构 | 优化命令结构 |

- [x] Subtask 13.1: 🔴 红 — 编写 CLI 命令测试
- [x] Subtask 13.2: 🟢 绿 — 实现 CLI 命令
- [x] Subtask 13.3: 🔄 重构 — 优化代码

#### TDD 循环 [B]：API 端点实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_equilibrium_endpoints.py`（API 测试） |
| 🟢 绿 | 实现 MFA/合规 API 端点 |
| 🔄 重构 | 添加请求验证 |

- [x] Subtask 13.4: 🔴 红 — 编写 API 端点测试
- [x] Subtask 13.5: 🟢 绿 — 实现 API 端点
- [x] Subtask 13.6: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [x] CLI 命令功能正常
- [x] API 端点功能正常
- [x] TDD 循环通过
- [x] 单元测试覆盖率 ≥85%

---

### Task 14: 集成测试与合规性验证

**关联 AC:** AC-7

> **目的：** 执行集成测试验证等保 2.0 三级合规系统功能。

#### TDD 循环 [A]：集成测试套件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_security_compliance_integration.py`（集成测试，预期失败） |
| 🟢 绿 | 实现集成测试用例（MFA/渗透测试/备份恢复） |
| 🔄 重构 | 优化测试结构、添加测试隔离 |

- [x] Subtask 14.1: 🔴 红 — 编写集成测试框架（预期失败）
- [x] Subtask 14.2: 🟢 绿 — 实现 MFA 集成测试
- [x] Subtask 14.3: 🟢 绿 — 实现渗透测试集成测试
- [x] Subtask 14.4: 🟢 绿 — 实现备份恢复集成测试
- [x] Subtask 14.5: 🔄 重构 — 优化测试隔离、运行 COMP-01 ~ COMP-05

**完成标准/Definition of Done:**
- [x] 集成测试全部通过
- [x] COMP-01 ~ COMP-05 测试通过
- [x] 集成测试覆盖率 ≥75%

---

### Task 15: SDD 架构约束验证测试

**关联 AC:** All

> **性质说明：** 本 Task 是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 15.1: 创建 `tests/unit/security/test_equilibrium_architecture.py`（独立架构验证文件）
- [x] Subtask 15.2: 实现领域层零依赖验证（安全服务仅在应用层/接口层）
- [x] Subtask 15.3: 实现循环依赖检测（使用 ruff 的 `E` 规则）
- [x] Subtask 15.4: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过
- [x] 领域层无安全相关外部依赖
- [x] 无循环依赖
- [x] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（依赖倒置，领域层定义接口，基础设施层实现）
- **设计约束:** 领域层零依赖、安全服务位于应用层/接口层
- **技术栈:** Python 3.11+, FastAPI 0.104+, PostgreSQL 15+, Redis 7.0+, TOTP (pyotp)

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 安全架构决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **复用 Story 1.9/1.10/1.11 安全基础设施** | 减少重复工作，保持一致性 | 需确保版本兼容性 | ✅ 9/10 |
| 独立实现全部安全组件 | 完全控制 | 大量重复工作 | 4/10 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   └── events/
│   │       └── compliance_events.py    # 等保相关领域事件
│   ├── application/
│   │   └── use_cases/
│   │       └── compliance/
│   │           ├── mfa_use_case.py
│   │           └── integrity_use_case.py
│   ├── infrastructure/
│   │   ├── security/
│   │   │   ├── models.py               # 等保相关模型
│   │   │   ├── mfa_service.py          # MFA 服务
│   │   │   ├── totp_generator.py       # TOTP 生成器
│   │   │   ├── intrusion_detector.py   # 入侵检测
│   │   │   ├── encryption_service.py   # 加密服务
│   │   │   ├── backup_service.py       # 备份服务
│   │   │   └── recovery_service.py     # 恢复服务
│   │   └── config/
│   │       └── equilibrium.py          # 等保配置
│   └── interfaces/
│       ├── cli/
│       │   └── equilibrium_commands.py  # CLI 命令
│       └── api/
│           └── equilibrium_endpoints.py # API 端点
└── tests/
    ├── unit/security/
    │   └── test_equilibrium.py         # 单元测试（统一文件）
    └── integration/
        └── test_security_compliance_integration.py  # 集成测试
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1-11](./1-11-data-sovereignty-isolation.md)

**关键学习/Key Learnings:**
1. API 层预验证模式 - 角色验证在 API 层完成，服务保持纯同步
2. 审计日志与业务操作同事务提交，保证数据一致性
3. 事务发件箱模式确保审计事件可靠性
4. 配置延迟加载需考虑线程安全问题

**应用到本故事/Applied to This Story:**
- [ ] MFA 验证采用 API 层预验证模式
- [ ] 安全审计日志同步记录至审计日志（复用 Story 1.10）
- [ ] 等保合规状态检查通过事件总线通知
- [ ] 配置加载考虑线程安全

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-04-20 |
| **Last Review Fix** | 2026-04-21 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-11-data-sovereignty-isolation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验整合（API 层预验证模式复用）
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] AC→Task→Subtask 追溯矩阵已补充

---

### 文件清单 File List

**创建的文件/Created Files:**
- `src/domain/events/compliance_events.py` - 等保领域事件（AC-1~AC-7）
- `src/infrastructure/security/models.py` - 等保相关模型（MFAChallenge/BackupRecord/IntegrityCheck）
- `src/infrastructure/security/totp_generator.py` - TOTP 生成器/验证器（AC-1）
- `src/infrastructure/security/mfa_service.py` - MFA 服务（AC-1）
- `src/infrastructure/security/intrusion_detector.py` - 入侵检测（AC-4）
- `src/infrastructure/security/backup_service.py` - 备份服务（AC-6）
- `src/infrastructure/security/recovery_service.py` - 恢复服务（AC-6）
- `src/infrastructure/security/integrity_service.py` - 完整性验证/数字签名（AC-5）
- `src/infrastructure/security/encryption_service.py` - 密码哈希+AES-256加密（完善AC-5）
- `src/infrastructure/config/equilibrium.py` - 等保配置（Task 13）
- `src/interfaces/cli/equilibrium_commands.py` - CLI 命令（Task 13）
- `src/interfaces/api/equilibrium_endpoints.py` - API 端点模型（Task 13）
- `src/interfaces/api/equilibrium_api.py` - API 路由实现（Task 13）
- `tests/unit/security/test_equilibrium.py` - 单元测试 43 项（Task 1-12）
- `tests/unit/security/test_equilibrium_architecture.py` - 架构验证测试 16 项（Task 15）
- `tests/integration/test_security_compliance_integration.py` - 集成测试 14 项（Task 14）
- `tests/acceptance/test_story_1_12.feature` - BDD 验收测试（Gherkin）
- `tests/acceptance/test_story_1_12_steps.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.12 |
| **Story Key** | 1-12-equilibrium-level-3-compliance |
| **File** | `_bmad-output/implementation-artifacts/stories/1-12-equilibrium-level-3-compliance.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 4: 安全与合规基础 |
| **优先级** | P0 |
| **覆盖 FR** | FR-SC-08: 等保 2.0 三级 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-15）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-7）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] AC→Task→Subtask 追溯矩阵已补充
7. [x] Review fixes applied 审查修复已完成 (v2.2.0)

---

## 📚 模板使用说明 Template Usage Guide

### 快速开始

1. 复制本模板到新文件
2. 替换所有 `[占位符]` 为实际内容
3. 根据 Story 类型调整覆盖率要求（见下表）
4. 确保 Task 0（SDD 规范定义）为必选前置
5. 每个 Task 包含自己的 TDD 循环（🔴红/🟢绿/🔄重构）
6. 填写 AC→Task→Subtask 追溯矩阵

### 适用场景与层类型对应关系

本模板适用于所有 Story 创建。根据六边形架构和 prd.md NFR 测试覆盖计划，Story 按层类型分类，每层有不同的测试要求：

| 层类型 | Story 类型 | Story 编号范围 | 覆盖率要求 | 测试重点 | 示例 |
|--------|-----------|---------------|-----------|---------|------|
| **安全层 (Security)** | 安全层 Story | Story 1.9-1.12 | ≥85% | 认证/授权/RBAC/审计日志/渗透测试 | Story 1.12: 等保 2.0 三级 |

> **注意：**
> 1. **层编号规则** — Story 0.x 为基础设施准备，Story 1.x 为领域层与安全/架构机制，Story 2.x 为应用层，Story 3.x 为接口层
> 2. **覆盖率要求** 源自 epics_v1.0.md CI/CD 质量门禁：整体≥80%，安全层≥85%
> 3. **骨架 Story 覆盖率豁免** — 架构骨架 Story 临时降低覆盖率要求（整体≥30%，对应层≥50%），从下一个非骨架 Story 恢复
> 4. **循环依赖检测** — 统一使用 ruff/isort，不引入 pylint 等额外工具

---

**模板版本/Template Version:** 2.2.0
**创建日期/Created:** 2026-04-20
**最后更新/Last Updated:** 2026-04-21
**更新说明:** v2.2.0 - 审查修复版本：(1) Task 0 补充完整 Subtask 0.1-0.9 分解，(2) AC-2 访问控制覆盖范围明确（资源级权限验证），(3) AC-3 审计日志覆盖明确（MFA/入侵检测/数据完整性事件），(4) 渗透测试补充 GB/T 22239-2019 标准版本号，(5) 追溯矩阵补充 Task 0 行
