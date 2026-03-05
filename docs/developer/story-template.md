# Story [编号]: [名称]

Status: backlog

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

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

### 1. [层类型] 测试
- [ ] [测试项 1] - [验证内容]
- [ ] [测试项 2] - [验证内容]
- [ ] [测试项 3] - [验证内容]

### 2. 性能要求
- [ ] [性能指标 1]
- [ ] [性能指标 2]
- [ ] [性能指标 3]

### 3. 覆盖率要求
- [ ] [层类型] 层覆盖率≥[目标值]%
- [ ] 集成测试覆盖率≥[目标值]%

### 4. 代码质量
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过
- [ ] [特定质量要求]

### 5. 测试文件
- [ ] `tests/unit/[layer]/test_[component].py` - 单元测试
- [ ] `tests/integration/test_[component]_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - [层类型] 测试要求

## Dev Notes

### 相关架构模式和约束

### 项目结构说明

### 前一个故事学习经验

### Git 智能分析

### 最新技术信息

## Dev Agent Record

### Agent Model Used

- **Model**: [模型名称]
- **Version**: create-story workflow v[版本]
- **Execution Date**: [日期]

### Debug Log References

- Workflow Config: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\workflow.yaml`
- Instructions: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\instructions.xml`
- Template: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\template.md`

### Completion Notes List

- [ ] 故事需求从 epics_v1.0.md 提取
- [ ] 架构约束从 architecture.md 提取
- [ ] 前一个故事学习经验整合
- [ ] 最新技术信息研究
- [ ] 状态设置为 ready-for-dev

### File List

**创建的文件：**
- `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\[编号]-[name].md`

**已实现的文件：**
- [列出实现的文件]

---

**Story Details:**
- Story ID: [编号]
- Story Key: [编号]-[name]
- File: `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\[编号]-[name].md`
- Status: backlog

**Completion Summary:**
1. [ ] All tasks completed
2. [ ] All acceptance criteria implemented
3. [ ] Code review completed
4. [ ] Sprint status synced

**Next Steps:**
- For new features, create follow-up stories
- Run tests to verify implementation

---

## 模板使用说明

### 适用场景

本模板适用于所有 Story 创建，包括：
- 领域层 Story（实体、事件、仓储）
- 应用层 Story（用例、命令、查询）
- 基础设施层 Story（数据库、缓存、消息队列）
- 接口层 Story（API、CLI、事件监听）

### TDD 测试要求模板

**领域层 Story：**
```markdown
### 1. 领域测试
- [ ] 实体创建测试 - 验证工厂方法
- [ ] 状态转换测试 - 验证状态机逻辑
- [ ] 领域事件测试 - 验证事件发布

### 2. 覆盖率要求
- [ ] 领域层覆盖率≥90%
- [ ] 单元测试覆盖率≥85%
```

**基础设施层 Story：**
```markdown
### 1. 基础设施测试
- [ ] 连接测试 - 验证 [组件] 连接
- [ ] CRUD 测试 - 验证基本操作
- [ ] 性能测试 - 验证延迟和吞吐量

### 2. 覆盖率要求
- [ ] 基础设施层覆盖率≥75%
- [ ] 集成测试覆盖率≥70%
```

**架构层 Story：**
```markdown
### 1. 架构测试
- [ ] 机制实现测试 - 验证 [机制] 功能
- [ ] 集成测试 - 验证组件协作
- [ ] 性能测试 - 验证路由延迟

### 2. 覆盖率要求
- [ ] 架构层覆盖率≥85%
- [ ] 集成测试覆盖率≥75%
```

### 相关文档

- [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md)
- [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md)
- [Epic 1 Story 1.1 试点计划](./epic1-story1.1-pilot-plan.md)

---

**模板版本:** 1.0.0
**创建日期:** 2026-03-04
**最后更新:** 2026-03-04
