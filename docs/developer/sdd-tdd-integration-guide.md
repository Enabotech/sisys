# SDD+TDD 融合模式项目整合指南

**版本:** 1.0.0
**日期:** 2026-03-04
**目的:** 指导如何将 SDD+TDD 融合模式内容整合到现有文档和交付件中

---

## 📋 整合原则

**核心理念：** 不是创建孤立的新文档，而是将融合模式**内建**到现有文档结构中。

### 整合策略

1. **需求与设计文档** - 增加融合模式说明和约束
2. **开发文档交付件** - 更新 Story 验收标准和实施指南
3. **代码交付件** - 添加 TDD 测试模板和示例

---

## 一、需求与设计类文档更新

### 1.1 prd.md 更新 ✅

**更新位置:** 第 1 章 产品概述 - 开发模式

**已更新内容:**
```markdown
| **开发模式** | Qwen Code Agent + SDD+TDD 融合模式（Specification-Driven + Test-Driven Development） |

**开发模式详细说明：**

本项目采用**SDD+TDD 融合开发模式**，将规范驱动（SDD）与测试驱动（TDD）有机结合，通过 Qwen Code Agent 智能辅助，实现质量内建：

1. **SDD 规范驱动** - 保证方向正确
   - 领域事件 Schema 定义（Pydantic V2）
   - API 契约定义（OpenAPI 3.1）
   - 验收标准定义（Gherkin 格式/pytest-bdd）
   - 数据模型定义（SQLAlchemy）

2. **TDD 测试驱动** - 保证实现正确
   - 红阶段：在实现之前编写失败测试
   - 绿阶段：编写刚好让测试通过的最小实现
   - 重构阶段：保持测试通过的前提下优化代码

3. **Qwen Code Agent 智能辅助** - 提升开发效率
   - 生成测试初稿
   - 辅助实现代码
   - 提供重构建议
   - 规范验证

**质量门禁：**
- 领域层覆盖率 ≥90%
- 应用层覆盖率 ≥85%
- 整体覆盖率 ≥80%
- 严重错误 = 0，高危漏洞 = 0

**相关文档：**
- `docs/developer/sdd-tdd-fusion-guide.md` - 融合模式完整指南
- `docs/developer/sdd-tdd-checklist.md` - 实施检查清单
- `docs/developer/epic1-story1.1-pilot-plan.md` - 试点实施计划
```

**下一步:** 在 NFR 测试覆盖计划章节增加融合模式测试要求

---

### 1.2 architecture.md 更新

**更新位置:** 第 24 章 附录 D 测试策略

**待添加内容:** 在第 24.1 节前添加"24.1 SDD+TDD 融合开发模式"

**建议内容:**
```markdown
### 24.1 SDD+TDD 融合开发模式

**核心理念：** 将规范驱动（SDD）与测试驱动（TDD）有机结合，实现质量内建。

#### 24.1.1 融合模式架构

```markdown
┌─────────────────────────────────────────────────────────┐
│              SDD+TDD 融合开发流程 (6 步循环)               │
├─────────────────────────────────────────────────────────┤
│  1. SDD 规范定义 → 2. TDD 红 → 3. TDD 绿 → 4. TDD 重构    │
│     ↓                                              ↓    │
│  规范：Schema/API/验收                           优化代码 │
│     ↓                                              ↓    │
│  5. SDD 规范验证 ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←← 6. CI/CD │
└─────────────────────────────────────────────────────────┘
```

#### 24.1.2 SDD 规范定义

**规范文档清单：**

| 规范类型 | 文档位置 | 验证工具 | 验收标准 |
|---------|---------|---------|---------|
| **领域事件 Schema** | `src/domain/events/` | Pydantic V2 | 100% 验证通过 |
| **API 契约** | `docs/api/openapi.yaml` | Schemathesis | 契约测试 100% 通过 |
| **验收标准** | `tests/acceptance/*.feature` | pytest-bdd | Gherkin 格式 |
| **数据模型** | `src/domain/entities/` | SQLAlchemy | 模型验证通过 |

#### 24.1.3 TDD 红 - 绿 - 重构循环

**红阶段（编写失败测试）：**
- 在实现之前编写测试
- 基于验收标准（Gherkin）
- 验证测试失败（预期行为）
- Qwen Code Agent 生成测试初稿

**绿阶段（最小实现）：**
- 只编写让测试通过的代码
- 不追求完美，先跑通流程
- Qwen Code Agent 辅助实现

**重构阶段（优化代码）：**
- 保持测试通过的前提下优化
- 应用设计模式/架构原则
- Qwen Code Agent 提供重构建议

#### 24.1.4 质量门禁

| 检查类型 | 工具 | 阈值 | 阻断级别 |
|---------|------|------|---------|
| **领域层覆盖率** | pytest-cov | ≥90% | P0 阻断 |
| **应用层覆盖率** | pytest-cov | ≥85% | P1 阻断 |
| **基础设施层覆盖率** | pytest-cov | ≥75% | P1 阻断 |
| **整体覆盖率** | pytest-cov | ≥80% | P0 阻断 |
| **Ruff 代码检查** | ruff | 严重错误=0 | P0 阻断 |
| **MyPy 类型检查** | mypy | 错误率<5% | P0 阻断 |
| **安全扫描** | bandit | 高危漏洞=0 | P0 阻断 |

#### 24.1.5 实施工具

**Makefile 命令：**
```bash
# SDD 规范定义
make sdd-define

# TDD 红 - 绿 - 重构循环
make tdd-red TARGET=domain/entities
make tdd-green TARGET=domain/entities
make tdd-refactor TARGET=domain/entities

# SDD 规范验证
make sdd-verify

# 完整开发循环
make sdd-tdd-cycle STORY=1.1
```

**相关文档：**
- `docs/developer/sdd-tdd-fusion-guide.md` - 融合模式完整指南
- `docs/developer/sdd-tdd-checklist.md` - 实施检查清单
- `docs/developer/epic1-story1.1-pilot-plan.md` - 试点实施计划

**后续章节编号调整:**
- 原 24.1 测试金字塔 → 24.2 测试金字塔
- 原 24.2 契约测试策略 → 24.3 契约测试策略
- 原 24.3 性能基准测试 → 24.4 性能基准测试
- ... 依此类推

---

### 1.3 qwen_agent.md 更新（待创建）

**文件位置:** `_bmad-output/planning-artifacts/qwen_agent.md` 或 `docs/developer/qwen_agent.md`

**待添加内容:** Qwen Code Agent 在融合模式中的使用指南

**建议大纲:**
```markdown
# Qwen Code Agent 在 SDD+TDD 融合模式中的使用指南

## 1. SDD 规范定义阶段

### 1.1 生成领域事件 Schema
提示词示例：
"基于以下业务需求，生成领域事件 Schema：
- 业务场景：...
- 事件类型：...
要求：使用 Pydantic V2，继承 DomainEvent"

### 1.2 生成 API 契约
提示词示例：
"基于以下用例，生成 OpenAPI 3.1 规范：
- 用例：创建战略规划
- 输入：...
- 输出：..."

### 1.3 生成验收标准（Gherkin）
提示词示例：
"基于以下用户故事，生成 Gherkin 验收标准：
As a ...
I want ...
So that ...
要求：包含正常路径和异常路径"

## 2. TDD 红阶段

### 2.1 生成单元测试初稿
提示词示例：
"基于以下 SDD 规范，生成 TDD 单元测试初稿：
规范：...
要求：
- 使用 pytest 格式
- 包含正常路径和异常路径测试
- 使用 Arrange-Act-Assert 模式"

### 2.2 生成验收测试
提示词示例：
"基于以下 Gherkin 验收标准，生成 pytest-bdd 测试实现：
Feature: ...
Scenario: ..."

## 3. TDD 绿阶段

### 3.1 辅助实现代码
提示词示例：
"基于以下失败的测试，生成 TDD 最小实现：
测试代码：...
要求：
- 只编写让测试通过的代码
- 不追求完美
- 保持代码简洁"

## 4. TDD 重构阶段

### 4.1 提供重构建议
提示词示例：
"以下代码通过了所有测试，但需要重构：
代码：...
要求：
- 应用设计模式
- 添加类型注解
- 改进命名
- 保持测试通过"

## 5. SDD 规范验证

### 5.1 规范验证
提示词示例：
"验证以下代码是否符合 SDD 规范：
代码：...
规范：...
检查项：
- Schema 验证
- 类型检查
- 命名规范
- 架构约束"
```

---

## 二、开发文档类交付件更新

### 2.1 epics_v1.0.md 更新

**更新位置:** 每个 Story 的验收标准部分

**更新模式:** 在现有 Story 验收标准后增加"TDD 测试要求"

**示例（Story 1.1）:**
```markdown
### Story 1.1: 六边形架构骨架

As a **系统架构师**,
I want **实现领域驱动六边形架构骨架**,
So that **领域逻辑与技术实现隔离，支持独立演进和测试**。

**Acceptance Criteria:**

**Given** 项目初始化完成
**When** 创建领域层、应用层、接口层、基础设施层目录结构
**Then** 领域层仅依赖 Python 标准库，不包含任何外部框架导入
**And** 各层之间依赖方向正确（基础设施层→应用层→领域层）

**TDD 测试要求（新增）：**

1. **架构约束测试**
   - [ ] 领域层零依赖测试（FR-AR-01）
   - [ ] 依赖方向测试
   - [ ] 导入检查测试

2. **覆盖率要求**
   - [ ] 领域层覆盖率≥90%
   - [ ] 整体覆盖率≥80%

3. **代码质量**
   - [ ] Ruff 检查通过（严重错误=0）
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过（高危漏洞=0）

**实施指南:**
参考 `docs/developer/epic1-story1.1-pilot-plan.md`
```

**需要更新的 Story 列表:**
- [ ] Story 0.1-0.3（Iteration 0）- 回顾性更新
- [ ] Story 1.1-1.19（Epic 1）- 逐个更新
- [ ] Epic 2-8 的 Story - 批量更新

---

### 2.2 Story 0.1-0.3 文档更新（回顾性）

#### Story 0.1: 开发环境搭建

**更新位置:** Implementation Tasks 后增加"TDD 实施说明"

**待添加内容:**
```markdown
## TDD 实施说明（新增 2026-03-04）

**SDD+TDD 融合模式工具链：**

本项目已建立完整的 SDD+TDD 融合开发模式工具链：

1. **测试框架** - pytest/pytest-cov/pytest-mock/factory_boy
2. **代码质量** - ruff/mypy/black/bandit
3. **规范验证** - pydantic/schemathesis/pytest-bdd
4. **CI/CD** - GitHub Actions（6 个 Job）

**Makefile 命令：**
```bash
# SDD 规范定义
make sdd-define

# TDD 红 - 绿 - 重构循环
make tdd-red TARGET=domain/entities
make tdd-green TARGET=domain/entities
make tdd-refactor TARGET=domain/entities

# 完整开发循环
make sdd-tdd-cycle STORY=1.1
```

**相关文档：**
- `docs/developer/sdd-tdd-fusion-guide.md` - 融合模式完整指南
- `docs/developer/sdd-tdd-checklist.md` - 实施检查清单


#### Story 0.2: CI/CD 流水线

**更新位置:** Tasks 后增加"TDD 集成说明"

**待添加内容:**
```markdown
## TDD 集成说明（新增 2026-03-04）

**CI/CD 流水线已集成 TDD 测试门禁：**

阶段 2: 单元测试
- 运行 `pytest tests/unit/ --cov=src --cov-fail-under=80`
- 领域层覆盖率≥90%
- 应用层覆盖率≥85%

**质量门禁：**
- 覆盖率<80% 阻断流水线
- 领域层覆盖率<90% 阻断流水线

**TDD 红 - 绿 - 重构循环已整合到开发流程：**
参考 `docs/developer/sdd-tdd-checklist.md`
```

#### Story 0.3: 测试框架搭建

**更新位置:** 整个文档更新为 SDD+TDD 融合测试框架

**待添加内容:**
```markdown
## SDD+TDD 融合测试框架（新增 2026-03-04）

**本 Story 建立的测试框架支持 SDD+TDD 融合模式：**

### 测试分层

1. **单元测试（70%）** - TDD 驱动开发
   - 领域层测试（覆盖率≥90%）
   - 应用层测试（覆盖率≥85%）
   - 基础设施层测试（覆盖率≥75%）

2. **集成测试（20%）** - 契约验证
   - 外部服务集成
   - 数据库集成
   - 事件总线集成

3. **E2E 测试（10%）** - 验收验证
   - 用户旅程测试
   - 完整业务流程测试

### TDD 红 - 绿 - 重构循环

**红阶段：**
```bash
make tdd-red TARGET=domain/entities
```

**绿阶段：**
```bash
make tdd-green TARGET=domain/entities
```

**重构阶段：**
```bash
make tdd-refactor TARGET=domain/entities
```

### 测试模板

**单元测试模板：**
```python
# tests/unit/domain/entities/test_<entity>.py
class Test<Entity>:
    def test_create_<entity>_with_valid_data(self):
        """Given 有效的领域数据，When 创建实体，Then 成功创建"""
        # Arrange
        # Act
        # Assert
```

**验收测试模板：**
```gherkin
# tests/acceptance/test_<feature>.feature
Feature: <功能名称>
  Scenario: <场景名称>
    Given <前置条件>
    When <触发动作>
    Then <预期结果>
```

**完整模板参考：** `docs/developer/sdd-tdd-fusion-guide.md` 附录

---

### 2.3 新增 Story 模板

**文件位置:** `docs/developer/story-template.md`

**建议内容:**
```markdown
# Story [编号]: [名称]

Status: backlog

## Story

As a **[角色]**,
I want **[功能]**,
So that **[价值]**。

## Acceptance Criteria

**Given** [前置条件]
**When** [触发动作]
**Then** [预期结果]
**And** [额外断言]

## SDD 规范定义

### 领域事件 Schema
- [ ] 事件定义（`src/domain/events/`）
- [ ] Pydantic 验证通过

### API 契约
- [ ] OpenAPI 定义（`docs/api/openapi.yaml`）
- [ ] 契约测试通过

### 验收标准（Gherkin）
- [ ] `tests/acceptance/test_story_[编号].feature`
- [ ] 业务方评审通过

## Tasks / Subtasks

- [ ] Task 1: [任务名称]
  - [ ] Subtask 1.1: [子任务]
  - [ ] Subtask 1.2: [子任务]

## TDD 测试要求

### 单元测试
- [ ] 领域层测试（覆盖率≥90%）
- [ ] 应用层测试（覆盖率≥85%）

### 代码质量
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过
- [ ] 安全扫描通过

## Dev Notes

### 相关架构模式和约束

### 项目结构说明

### 前一个故事学习经验

### Git 智能分析

### 最新技术信息

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
```

---

## 三、代码交付件更新

### 3.1 测试模板代码

**已创建位置:**
- `tests/unit/domain/entities/test_strategic_plan.py` - TDD 示例
- `tests/unit/architecture/test_hexagonal_architecture.py` - 架构约束测试
- `tests/acceptance/test_plan_events.feature` - 验收测试示例

**待创建:**
- `tests/unit/domain/entities/test_base_entity.py` - 基类测试模板
- `tests/unit/application/usecases/test_create_plan.py` - 用例测试模板
- `tests/unit/infrastructure/repositories/test_plan_repository.py` - 仓储测试模板

### 3.2 领域实体代码

**已创建位置:**
- `src/domain/entities/strategic_plan.py` - TDD 重构示例
- `src/domain/events/plan_events.py` - SDD Schema 示例
- `src/domain/exceptions/*.py` - 领域异常示例

**待创建:**
- `src/domain/entities/base.py` - 领域实体基类
- `src/domain/events/base.py` - 领域事件基类
- `src/domain/repositories/base.py` - 仓储基类接口

### 3.3 Makefile 命令

**已更新位置:** `Makefile`

**新增命令:**
- `make sdd-define` - SDD 规范定义
- `make tdd-red TARGET=x` - TDD 红阶段
- `make tdd-green TARGET=x` - TDD 绿阶段
- `make tdd-refactor TARGET=x` - TDD 重构阶段
- `make tdd-cycle TARGET=x` - TDD 完整循环
- `make sdd-tdd-cycle STORY=x` - SDD+TDD 完整开发循环
- `make sdd-verify` - SDD 规范验证

**帮助信息:** 已更新，包含融合模式命令说明

---

## 四、整合检查清单

### 需求与设计文档

| 文档 | 更新内容 | 状态 | 备注 |
|------|---------|------|------|
| `prd.md` | 开发模式说明（第 1 章） | ✅ 已完成 | 2026-03-04 更新 |
| `prd.md` | NFR 测试覆盖计划更新 | ⏳ 待执行 | P1 优先级 |
| `architecture.md` | 第 24 章 测试策略（增加 SDD+TDD 融合模式） | ⏳ 待执行 | P1 优先级 |
| `architecture.md` | 第 19 章 测试覆盖要求（更新覆盖率指标） | ⏳ 待执行 | P2 优先级 |
| `qwen_agent.md` | Qwen Code Agent 在融合模式中的使用指南 | ❌ 待创建 | P2 优先级 |

**完成度：** 1/5 (20%)

---

### 开发文档交付件

| 文档 | 更新内容 | 状态 | 备注 |
|------|---------|------|------|
| `epics_v1.0.md` | Story 1.1-1.3 验收标准（增加 TDD 测试要求） | ⏳ 待执行 | P1 优先级 |
| `epics_v1.0.md` | Story 1.4-1.19 验收标准 | ⏳ 待执行 | P2 优先级 |
| `epics_v1.0.md` | Epic 2-8 Story 验收标准 | ⏳ 待执行 | P3 优先级 |
| `0-1-dev-environment-setup.md` | TDD 工具链说明 | ⏳ 待执行 | P2 优先级 |
| `0-2-ci-cd-pipeline.md` | TDD 集成说明（CI/CD 门禁） | ⏳ 待执行 | P2 优先级 |
| `0-3-test-framework-setup.md` | 融合测试框架更新 | ⏳ 待执行 | P2 优先级 |
| `story-template.md` | Story 模板（新增文档） | ❌ 待创建 | P2 优先级 |

**完成度：** 0/7 (0%)

---

### 代码交付件

| 文件 | 更新内容 | 状态 | 备注 |
|------|---------|------|------|
| `Makefile` | SDD+TDD 融合模式命令 | ✅ 已完成 | 2026-03-04 更新 |
| `Makefile` | 帮助信息更新 | ✅ 已完成 | 2026-03-04 更新 |
| `tests/unit/domain/entities/test_strategic_plan.py` | TDD 完整示例 | ✅ 已完成 | 2026-03-04 创建（entities/子目录） |
| `tests/unit/domain/events/test_events_base.py` | 事件基类测试 | ✅ 已完成 | 2026-03-04 移动（events/子目录） |
| `tests/unit/architecture/test_hexagonal_architecture.py` | 架构约束测试 | ✅ 已完成 | 2026-03-04 创建 |
| `tests/unit/application/usecases/test_use_cases.py` | 用例测试 | ✅ 已完成 | 2026-03-04 移动（usecases/子目录） |
| `tests/unit/infrastructure/persistence/test_repositories.py` | 仓储测试 | ✅ 已完成 | 2026-03-04 移动（persistence/子目录） |
| `tests/unit/interfaces/api/test_api.py` | API 测试 | ✅ 已完成 | 2026-03-04 移动（api/子目录） |
| `tests/unit/shared/test_configuration.py` | 配置测试 | ✅ 已完成 | 2026-03-04 移动（shared/子目录） |
| `tests/acceptance/test_plan_events.feature` | 验收测试示例 | ⏳ 待创建 | P1 优先级 |
| `tests/unit/domain/entities/test_base_entity.py` | 基类测试模板 | ❌ 待创建 | P2 优先级 |
| `tests/unit/application/usecases/test_create_plan.py` | 用例测试模板 | ❌ 待创建 | P2 优先级 |
| `tests/unit/infrastructure/repositories/test_plan_repository.py` | 仓储测试模板 | ❌ 待创建 | P2 优先级 |
| `src/domain/entities/base.py` | 领域实体基类 | ❌ 待创建 | P1 优先级 |
| `src/domain/events/base.py` | 领域事件基类 | ❌ 待创建 | P1 优先级 |
| `src/domain/repositories/base.py` | 仓储基类接口 | ❌ 待创建 | P1 优先级 |

**完成度：** 9/16 (56%)

**目录结构对应关系：**
```
src/
├── domain/
│   ├── entities/
│   │   └── strategic_plan.py
│   ├── events/
│   │   └── base.py
│   ├── repositories/
│   └── exceptions/
├── application/
│   └── usecases/
├── infrastructure/
│   └── persistence/
├── interfaces/
│   └── api/
└── shared/

tests/unit/
├── domain/
│   ├── entities/
│   │   └── test_strategic_plan.py  # 对应 src/domain/entities/
│   ├── events/
│   │   └── test_events_base.py     # 对应 src/domain/events/
│   ├── repositories/
│   └── exceptions/
├── application/
│   └── usecases/
│       └── test_use_cases.py       # 对应 src/application/usecases/
├── infrastructure/
│   └── persistence/
│       └── test_repositories.py    # 对应 src/infrastructure/persistence/
├── interfaces/
│   └── api/
│       └── test_api.py             # 对应 src/interfaces/api/
├── shared/
│   └── test_configuration.py       # 对应 src/shared/
└── architecture/
    └── test_hexagonal_architecture.py  # 架构约束测试
```

**测试结果：**
```
tests/unit/: 82 passed, 6 skipped ✅
- domain/entities/: 22 passed
- domain/events/: 12 passed
- architecture/: 12 passed
- application/usecases/: 4 passed
- infrastructure/persistence/: 14 passed
- interfaces/api/: 6 skipped (需要外部依赖)
- shared/: 12 passed
```

---

### 支持文档

| 文档 | 用途 | 状态 | 备注 |
|------|------|------|------|
| `sdd-tdd-fusion-guide.md` | 融合模式完整指南 | ✅ 已完成 | 2026-03-04 创建 |
| `sdd-tdd-checklist.md` | 实施检查清单 | ✅ 已完成 | 2026-03-04 创建 |
| `epic1-story1.1-pilot-plan.md` | Story 1.1 试点计划 | ✅ 已完成 | 2026-03-04 创建 |
| `sdd-tdd-integration-guide.md` | 文档整合指南（本文档） | ✅ 已完成 | 2026-03-04 创建 |
| `story-template.md` | Story 模板 | ❌ 待创建 | P2 优先级 |
| `qwen_agent_prompt_library.md` | Qwen Code Agent 提示词库 | ❌ 待创建 | P3 优先级 |

**完成度：** 4/6 (67%)

---

### 总体完成度

| 类别 | 已完成 | 待执行 | 待创建 | 完成度 |
|------|-------|-------|-------|-------|
| 需求与设计文档 | 1 | 4 | 1 | 20% |
| 开发文档交付件 | 0 | 6 | 1 | 0% |
| 代码交付件 | 9 | 1 | 6 | 56% |
| 支持文档 | 4 | 0 | 2 | 67% |
| **总计** | **14** | **11** | **10** | **40%** |

---

## 五、实施优先级

### P0（立即执行）- ✅ 已完成

| 任务 | 完成日期 | 交付物 |
|------|---------|--------|
| `prd.md` 开发模式说明 | 2026-03-04 | 第 1 章更新 |
| `Makefile` 命令更新 | 2026-03-04 | 8 个新命令 + 帮助信息 |
| TDD 测试示例代码 | 2026-03-04 | 2 个测试文件 |

**P0 完成度：** 3/3 (100%) ✅

---

### P1（本周执行）- 2026-03-04 至 2026-03-08

| 优先级 | 任务 | 负责人 | 预计工时 | 状态 |
|-------|------|--------|---------|------|
| **P1-1** | `architecture.md` 第 24 章 测试策略更新 | Charlie | 2 小时 | ⏳ 待执行 |
| **P1-2** | `epics_v1.0.md` Story 1.1-1.3 验收标准更新 | Charlie | 3 小时 | ⏳ 待执行 |
| **P1-3** | `src/domain/entities/base.py` 领域基类 | Elena | 4 小时 | ⏳ 待执行 |
| **P1-4** | `src/domain/events/base.py` 事件基类 | Elena | 3 小时 | ⏳ 待执行 |
| **P1-5** | `src/domain/repositories/base.py` 仓储基类 | Elena | 3 小时 | ⏳ 待执行 |
| **P1-6** | `tests/acceptance/test_plan_events.feature` 验收测试 | Dana | 2 小时 | ⏳ 待执行 |

**P1 完成度：** 0/6 (0%) ⏳

**P1 里程碑：**
- [ ] 架构文档测试策略章节更新
- [ ] Epic 1 Story 1.1-1.3 验收标准包含 TDD 要求
- [ ] 领域基类代码框架完成

---

### P2（下周执行）- 2026-03-11 至 2026-03-15

| 优先级 | 任务 | 负责人 | 预计工时 | 状态 |
|-------|------|--------|---------|------|
| **P2-1** | `qwen_agent.md` 使用指南 | Charlie | 4 小时 | ❌ 待执行 |
| **P2-2** | `epics_v1.0.md` Story 1.4-1.19 验收标准更新 | Elena | 8 小时 | ❌ 待执行 |
| **P2-3** | `0-1-dev-environment-setup.md` TDD 工具链说明 | Elena | 2 小时 | ❌ 待执行 |
| **P2-4** | `0-2-ci-cd-pipeline.md` TDD 集成说明 | Charlie | 2 小时 | ❌ 待执行 |
| **P2-5** | `0-3-test-framework-setup.md` 融合测试框架更新 | Dana | 3 小时 | ❌ 待执行 |
| **P2-6** | `story-template.md` Story 模板 | Charlie | 3 小时 | ❌ 待执行 |
| **P2-7** | 基类测试模板（3 个文件） | Elena | 6 小时 | ❌ 待执行 |
| **P2-8** | 用例测试模板 | Elena | 4 小时 | ❌ 待执行 |
| **P2-9** | 仓储测试模板 | Elena | 4 小时 | ❌ 待执行 |

**P2 完成度：** 0/9 (0%) ❌

**P2 里程碑：**
- [ ] Qwen Code Agent 使用指南完成
- [ ] Epic 1 所有 Story 验收标准更新完成
- [ ] Story 0.1-0.3 文档回顾性更新完成
- [ ] 测试模板代码库完成

---

### P3（后续执行）- 2026-03-18 起

| 优先级 | 任务 | 负责人 | 预计工时 | 状态 |
|-------|------|--------|---------|------|
| **P3-1** | `epics_v1.0.md` Epic 2-8 Story 验收标准更新 | 全体 | 16 小时 | ❌ 待执行 |
| **P3-2** | `architecture.md` 第 19 章 测试覆盖要求更新 | Charlie | 2 小时 | ❌ 待执行 |
| **P3-3** | `qwen_agent_prompt_library.md` 提示词库 | Elena | 4 小时 | ❌ 待执行 |

**P3 完成度：** 0/3 (0%) ❌

---

### 实施路线图

```
2026-03-04 (今日)
    │
    ├─ P0 完成 ✅
    │  └─ prd.md、Makefile、TDD 示例代码
    │
2026-03-04 ~ 2026-03-08 (第 1 周)
    │
    ├─ P1 执行 ⏳
    │  ├─ architecture.md 第 24 章
    │  ├─ Story 1.1-1.3 验收标准
    │  └─ 领域基类代码
    │
2026-03-11 ~ 2026-03-15 (第 2 周)
    │
    ├─ P2 执行 ❌
    │  ├─ qwen_agent.md 使用指南
    │  ├─ Story 0.1-0.3 回顾性更新
    │  ├─ Story 模板创建
    │  └─ 测试模板代码库
    │
2026-03-18 ~ (第 3 周起)
    │
    └─ P3 执行 ❌
       ├─ Epic 2-8 Story 批量更新
       └─ 提示词库创建
```

---

## 六、维护说明

### 文档维护

| 文档 | 负责人 | 维护频率 | 审核周期 |
|------|--------|---------|---------|
| `prd.md` | Alice (PO) | 按需更新 | 每 Epic |
| `architecture.md` | Charlie (架构师) | 按需更新 | 每 Epic |
| `epics_v1.0.md` | 开发团队 | 每 Story 前 | 每 Story |
| `Story 文档` | Story 负责人 | 每 Story | 每 Story |
| `sdd-tdd-*.md` 系列 | Charlie | 按需更新 | 每月 |

### 代码维护

| 代码 | 负责人 | 维护频率 | 审核周期 |
|------|--------|---------|---------|
| 测试模板 | Dana (QA) | 按需更新 | 每月 |
| 领域代码 | Elena + Charlie | 每 Story | 每 Story |
| Makefile | Charlie | 按需更新 | 每月 |

### 更新流程

```
1. 发现需要更新的内容
         ↓
2. 在对应文档中添加/修改
         ↓
3. 更新本检查清单（四、整合检查清单）
         ↓
4. 更新实施优先级（五、实施优先级）
         ↓
5. 通知相关团队（Slack/钉钉）
         ↓
6. 提交代码审查
```

### 检查清单更新规范

**状态标记：**
- ✅ 已完成 - 任务已完成并验证
- ⏳ 进行中 - 任务正在执行
- ❌ 待执行 - 任务未开始
- 🚫 已取消 - 任务取消

**完成度计算：**
```
完成度 = 已完成任务数 / (已完成 + 待执行 + 进行中) × 100%
```

---

**文档结束**
