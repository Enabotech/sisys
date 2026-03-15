# Story [编号]: [名称]

**Status:** `backlog`

> **Note:** SDD 规范验证为必选项，TDD 测试生成可参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md)。运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** [角色/Role],
**I want** [功能/Feature],
**So that** [价值/Value].

---

## ✅ Acceptance Criteria 验收标准

### AC-1: [验收标准标题]

**Given** [前置条件/Precondition]
**When** [触发动作/Trigger Action]
**Then** [预期结果/Expected Result]
**And** [额外断言/Additional Assertions]

**验证标准/Validation Criteria:**
- [ ] [具体验证项 1]
- [ ] [具体验证项 2]
- [ ] [具体验证项 3]

---

## 🏗️ SDD+TDD 融合开发

> 遵循 **SDD 规范驱动** + **TDD 测试驱动** 双轮开发模式。参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 了解完整的红 - 绿 - 重构循环。

### SDD 规范定义（Step 1）

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] Pydantic 模型验证通过
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `UserCreated`）

#### API 契约 (API Contract)
- [ ] OpenAPI 定义位于 `docs/api/openapi.yaml`
- [ ] 契约测试通过（`tests/contract/test_api_contract.py`）
- [ ] API 版本管理正确（`/api/v1/[resource]`）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_[编号].feature`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

---

### TDD 红 - 绿 - 重构循环（Step 2-4）

#### 红阶段 - 编写失败测试
- [ ] 根据验收标准编写测试初稿
- [ ] 验证测试失败（确认测试有效）
- [ ] 测试命名清晰表达业务意图

#### 绿阶段 - 最小实现
- [ ] 编写刚好让测试通过的代码
- [ ] 不追求完美，先跑通流程

#### 重构阶段 - 优化代码
- [ ] 保持测试通过的前提下优化代码
- [ ] 应用设计模式/架构原则
- [ ] 运行代码质量工具（ruff/black/mypy）

---

### 测试要求与质量门禁

#### 层测试要求
| 测试项 | 验证内容 | 测试文件 |
|--------|----------|----------|
| [测试项 1] | [验证内容] | `test_[component]_[scenario].py` |
| [测试项 2] | [验证内容] | `test_[component]_[scenario].py` |
| [测试项 3] | [验证内容] | `test_[component]_[scenario].py` |

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **[层类型] 层覆盖率 ≥ [目标值]%**（`pytest --cov=src/[layer]`）- **P1 阻断门禁**
  - 领域层：≥90%（关键业务逻辑，不变量验证）
  - 应用层：≥85%（核心业务流，事务管理）
  - 接口层：≥85%（API 路由，请求响应验证）
  - 基础设施层：≥75%（外部依赖适配，连接测试）
  - 安全层：≥85%（认证授权，渗透测试）
  - 架构层：≥85%（核心机制，路由决策）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）
- [ ] **NFR 测试覆盖**（根据 prd.md 第 9 章非功能需求）
  - 性能：检索延迟 P95<800ms(MVP)/<500ms(V1)/<300ms(V2)，路由决策延迟 P95<100ms(MVP)/<50ms(V1)
  - 安全：渗透测试无高危漏洞，中危<5 个，沙箱逃逸 0 次成功
  - 合规：等保 2.0 三级，审计日志 100% 完整，7 年 WORM 存储
  - 可靠性：可用性 99%(MVP)/99.5%(V1)/99.9%(V2)，Checkpoint 恢复成功率≥99%

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试文件结构
| 测试类型 | 文件路径 | 说明 |
|---------|----------|------|
| 单元测试 | `tests/unit/[layer]/test_[component].py` | 测试核心逻辑 |
| 集成测试 | `tests/integration/test_[component]_integration.py` | 测试组件协作 |
| 验收测试 | `tests/acceptance/test_story_[编号].feature` | 测试业务价值 |

> **实施指南:** 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) 和 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md)

---

## 📋 Tasks / Subtasks 任务分解

### Task 1: [任务名称]

**关联 AC:** AC-1, AC-2, ...

- [ ] Subtask 1.1: [子任务描述]
- [ ] Subtask 1.2: [子任务描述]
- [ ] Subtask 1.3: [子任务描述]

**完成标准/Definition of Done:**
- [ ] 代码实现完成
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 代码审查通过
- [ ] SDD 规范验证通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture-epic0.md`](../../_bmad-output/planning-artifacts/architecture-epic0.md)

- **架构模式:** [如 CQRS、Event Sourcing、Hexagonal 等]
- **设计约束:** [如 TLS 1.3、非 root 用户、只读文件系统等]
- **技术栈:** [如 FastAPI v0.111.x、PostgreSQL v15.x+、Redis v5.0+ 等]

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   └── [layer]/
│       ├── [component].py      # 核心实现
│       └── [component]_test.py # 测试
├── tests/
│   ├── unit/[layer]/
│   ├── integration/
│   └── acceptance/
└── docs/
    └── [layer]/
        └── [component]_guide.md
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story [编号]-[名称]](./[编号]-[name].md)

**关键学习/Key Learnings:**
1. [学习点 1]
2. [学习点 2]
3. [学习点 3]

**应用到本故事/Applied to This Story:**
- [ ] [应用点 1]
- [ ] [应用点 2]

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | [模型名称，如 Qwen Code] |
| **Version** | create-story workflow v[版本] |
| **Execution Date** | [执行日期，如 2026-03-14] |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture-epic0.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/[编号]-[name].md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture-epic0.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/[编号]-[name].md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/[layer]/[component].py` - 核心实现
- `tests/unit/[layer]/test_[component].py` - 单元测试
- `tests/integration/test_[component]_integration.py` - 集成测试
- `docs/[layer]/[component]_guide.md` - 实施指南

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | [编号] |
| **Story Key** | [编号]-[name] |
| **File** | `_bmad-output/implementation-artifacts/stories/[编号]-[name].md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |

### 完成总结 Completion Summary

1. [ ] All tasks completed 所有任务完成
2. [ ] All acceptance criteria implemented 所有验收标准实现
3. [ ] Code review completed 代码审查完成
4. [ ] Sprint status synced Sprint 状态同步

### 下一步 Next Steps

- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 模板使用说明 Template Usage Guide

### 适用场景与层类型对应关系

本模板适用于所有 Story 创建。根据六边形架构和 prd.md NFR 测试覆盖计划，Story 按层类型分类，每层有不同的测试要求：

| 层类型 | Story 类型 | Story 编号范围 | 覆盖率要求 | 测试重点 | 示例 |
|--------|-----------|---------------|-----------|---------|------|
| **领域层 (Domain)** | 领域层 Story | Story 1.x | ≥90% | 实体创建/状态转换/领域事件/不变量验证 | Story 1.1: 六边形架构骨架 |
| **应用层 (Application)** | 应用层 Story | Story 2.x | ≥85% | 用例逻辑/命令处理/查询处理/事务管理 | Story 2.1: 用户注册用例 |
| **接口层 (Interfaces)** | 接口层 Story | Story 3.x | ≥85% | API 路由/请求响应验证/事件监听/错误处理 | Story 3.1: REST API |
| **基础设施层 (Infrastructure)** | 基础设施层 Story | Story 0.x, 1.4-1.8 | ≥75% | 连接测试/CRUD 操作/外部适配器/性能基准 | Story 1.4: Redis 缓存层 |
| **安全层 (Security)** | 安全层 Story | Story 1.9-1.12 | ≥85% | 认证/授权/RBAC/审计日志/渗透测试 | Story 1.9: RBAC 权限控制 |
| **架构层 (Architecture)** | 架构层 Story | Story 1.13-1.19 | ≥85% | 核心机制 (UDMR/EIP)/路由决策/多 Agent 协作 | Story 1.13: 统一动态模型路由 |

> **注意：**
> 1. 层编号规则 - Story 0.x 为基础设施准备，Story 1.x 为领域层与安全/架构机制，Story 2.x 为应用层，Story 3.x 为接口层
> 2. 覆盖率要求源自 epics_v1.0.md CI/CD 质量门禁：整体≥80%，领域层≥90%，应用层≥85%，基础设施层≥75%
> 3. NFR 测试要求：性能 (检索延迟 P95<800ms)/安全性 (渗透测试无高危漏洞)/合规性 (等保 2.0 三级/审计日志 100% 完整)
> 4. 整体覆盖率≥80% 为 P0 阻断门禁，各层覆盖率目标为 P1 阻断门禁

### 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [预提交 Hooks 规范](./pre-commit-hooks.md) | 代码质量保障 |
| [架构设计文档](../../_bmad-output/planning-artifacts/architecture.md) | 六边形架构详细说明 |

---

**模板版本/Template Version:** 1.2.0
**创建日期/Created:** 2026-03-04
**最后更新/Last Updated:** 2026-03-15
**更新说明:** 更新各层覆盖率指标，与 epics_v1.0.md CI/CD 质量门禁对齐
