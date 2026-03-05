# Qwen Code Agent 在 SDD+TDD 融合模式中的使用指南

**版本:** 1.0.0
**日期:** 2026-03-04
**作者:** Agimtech 团队

---

## 目录

1. [概述](#概述)
2. [SDD 规范定义阶段](#sdd-规范定义阶段)
3. [TDD 红阶段](#tdd-红阶段)
4. [TDD 绿阶段](#tdd-绿阶段)
5. [TDD 重构阶段](#tdd-重构阶段)
6. [SDD 规范验证](#sdd-规范验证)
7. [最佳实践](#最佳实践)
8. [常见问题](#常见问题)

---

## 概述

本指南介绍如何在 SDD+TDD 融合开发模式中使用 Qwen Code Agent 提高开发效率。

### Qwen Code Agent 能力

1. **代码生成** - 根据规范生成代码
2. **测试生成** - 根据需求生成测试用例
3. **规范验证** - 验证代码是否符合规范
4. **重构建议** - 提供代码重构建议
5. **文档生成** - 生成代码文档和注释

### 融合模式流程

```
┌─────────────────────────────────────────────────────────┐
│              SDD+TDD 融合开发流程 (6 步循环)               │
├─────────────────────────────────────────────────────────┤
│  1. SDD 规范定义 → 2. TDD 红 → 3. TDD 绿 → 4. TDD 重构    │
│     ↓              ↓           ↓           ↓            │
│  Qwen 辅助       Qwen 生成    Qwen 辅助    Qwen 建议     │
│  规范定义        测试初稿     实现代码     重构方案      │
│     ↓              ↓           ↓           ↓            │
│  5. SDD 规范验证 ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←← 6. CI/CD │
│     ↓                                                              │
│  Qwen 验证                                                    │
└─────────────────────────────────────────────────────────┘
```

---

## SDD 规范定义阶段

### 1.1 生成领域事件 Schema

**场景：** 需要创建新的领域事件

**提示词模板：**
```
基于以下业务需求，生成领域事件 Schema：

业务场景：[描述业务场景]
事件类型：[事件名称]
事件载荷：[包含的字段]

要求：
- 使用 Pydantic V2
- 继承 DomainEvent 基类
- 包含 event_type 自动设置
- 包含完整的类型注解
```

**示例：**
```
基于以下业务需求，生成领域事件 Schema：

业务场景：战略规划创建时发布事件
事件类型：PlanCreated
事件载荷：plan_id, creator_id, plan_type

要求：
- 使用 Pydantic V2
- 继承 DomainEvent 基类
- 包含 event_type 自动设置为"plan.created"
- 包含完整的类型注解
```

**预期输出：**
```python
class PlanCreated(DomainEvent):
    """规划创建事件"""
    event_type: str = "plan.created"
    plan_id: UUID
    creator_id: str
    plan_type: PlanType
```

---

### 1.2 生成 API 契约

**场景：** 需要定义 REST API 接口

**提示词模板：**
```
基于以下用例，生成 OpenAPI 3.1 规范：

用例：[用例名称]
端点：[HTTP 方法] [路径]
输入：[请求体/参数]
输出：[响应体]
错误：[可能的错误响应]

要求：
- 使用 OpenAPI 3.1 格式
- 包含完整的 Schema 定义
- 包含错误响应定义
```

**示例：**
```
基于以下用例，生成 OpenAPI 3.1 规范：

用例：创建战略规划
端点：POST /api/v1/plans
输入：plan_type, creator_id
输出：plan_id, status
错误：400 Bad Request, 401 Unauthorized

要求：
- 使用 OpenAPI 3.1 格式
- 包含完整的 Schema 定义
- 包含错误响应定义
```

---

### 1.3 生成验收标准（Gherkin）

**场景：** 需要编写验收测试

**提示词模板：**
```
基于以下用户故事，生成 Gherkin 验收标准：

用户故事：
As a [角色]
I want [功能]
So that [价值]

要求：
- 使用 Gherkin 格式（Given-When-Then）
- 包含正常路径场景
- 包含异常路径场景
- 包含边界条件场景
```

**示例：**
```
基于以下用户故事，生成 Gherkin 验收标准：

用户故事：
As a 系统架构师
I want 实现领域驱动六边形架构骨架
So that 领域逻辑与技术实现隔离，支持独立演进和测试

要求：
- 使用 Gherkin 格式（Given-When-Then）
- 包含正常路径场景
- 包含异常路径场景
- 包含边界条件场景
```

**预期输出：**
```gherkin
Feature: 六边形架构骨架
  Scenario: 领域层仅依赖 Python 标准库
    Given 项目初始化完成
    When 检查领域层导入
    Then 领域层不包含任何外部框架导入
    And 领域层仅使用 Python 标准库

  Scenario: 各层依赖方向正确
    Given 六边形架构已创建
    When 检查依赖关系
    Then 基础设施层→应用层→领域层依赖方向正确
```

---

## TDD 红阶段

### 2.1 生成单元测试初稿

**场景：** 需要编写测试用例

**提示词模板：**
```
基于以下 SDD 规范，生成 TDD 单元测试初稿：

规范：
- [领域事件 Schema]
- [API 契约]
- [验收标准]

要求：
- 使用 pytest 格式
- 包含正常路径和异常路径测试
- 使用 Arrange-Act-Assert 模式
- 测试名称清晰表达意图（test_<scenario>_<expected>）
```

**示例：**
```
基于以下 SDD 规范，生成 TDD 单元测试初稿：

规范：
- 领域实体：StrategicPlan
- 工厂方法：create(id, plan_type, creator_id)
- 状态变更方法：change_status(new_status)
- 状态转换规则：draft→in_progress→approved

要求：
- 使用 pytest 格式
- 包含正常路径和异常路径测试
- 使用 Arrange-Act-Assert 模式
- 测试名称清晰表达意图
```

**预期输出：**
```python
class TestStrategicPlan:
    """战略规划领域实体测试"""

    def test_create_plan_with_valid_data(self):
        """Given 有效的领域数据，When 创建战略规划，Then 成功创建"""
        # Arrange
        plan_id = uuid4()
        creator_id = "agent_ceo"

        # Act
        plan = StrategicPlan.create(
            id=plan_id,
            plan_type=PlanType.SP,
            creator_id=creator_id,
        )

        # Assert
        assert plan.id == plan_id
        assert plan.plan_type == PlanType.SP
        assert plan.status == PlanStatus.DRAFT
```

---

### 2.2 生成验收测试实现

**场景：** 需要将 Gherkin 场景转换为 pytest-bdd 测试

**提示词模板：**
```
基于以下 Gherkin 验收标准，生成 pytest-bdd 测试实现：

Feature: [功能名称]
  Scenario: [场景名称]
    Given [前置条件]
    When [触发动作]
    Then [预期结果]

要求：
- 使用 pytest-bdd 装饰器（@given, @when, @then）
- 使用 target_fixture 传递数据
- 包含完整的 fixture 定义
```

---

## TDD 绿阶段

### 3.1 辅助实现代码

**场景：** 需要编写最小实现让测试通过

**提示词模板：**
```
基于以下失败的测试，生成 TDD 最小实现：

测试代码：
[粘贴测试代码]

要求：
- 只编写让测试通过的代码
- 不追求完美
- 保持代码简洁
- 使用类型注解
```

**示例：**
```
基于以下失败的测试，生成 TDD 最小实现：

测试代码：
def test_create_plan_with_valid_data():
    plan = StrategicPlan.create(
        id=uuid4(),
        plan_type=PlanType.SP,
        creator_id="agent_ceo",
    )
    assert plan.status == PlanStatus.DRAFT

要求：
- 只编写让测试通过的代码
- 不追求完美
- 保持代码简洁
- 使用类型注解
```

**预期输出：**
```python
class StrategicPlan:
    """战略规划领域实体"""

    def __init__(self, id: UUID, plan_type: PlanType, creator_id: str):
        self.id = id
        self.plan_type = plan_type
        self.status = PlanStatus.DRAFT
        self.creator_id = creator_id

    @classmethod
    def create(cls, id: UUID, plan_type: PlanType, creator_id: str) -> "StrategicPlan":
        return cls(id, plan_type, creator_id)
```

---

## TDD 重构阶段

### 4.1 提供重构建议

**场景：** 需要优化代码质量

**提示词模板：**
```
以下代码通过了所有测试，但需要重构：

代码：
[粘贴代码]

要求：
- 应用设计模式
- 添加类型注解
- 改进命名
- 保持测试通过
- 提取重复代码
- 简化复杂逻辑
```

**示例：**
```
以下代码通过了所有测试，但需要重构：

代码：
class StrategicPlan:
    def __init__(self, id, plan_type, status, creator_id, created_at, updated_at, version, blm_stage):
        self.id = id
        self.plan_type = plan_type
        self.status = status
        # ... 很多字段

要求：
- 应用设计模式
- 添加类型注解
- 改进命名
- 保持测试通过
- 使用 dataclass 简化
```

**预期输出：**
```python
@dataclass
class StrategicPlan:
    """战略规划领域实体"""
    id: UUID
    plan_type: PlanType
    status: PlanStatus = PlanStatus.DRAFT
    creator_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
```

---

## SDD 规范验证

### 5.1 规范验证

**场景：** 需要验证代码是否符合规范

**提示词模板：**
```
验证以下代码是否符合 SDD 规范：

代码：
[粘贴代码]

规范：
[粘贴规范]

检查项：
- Schema 验证
- 类型检查
- 命名规范
- 架构约束
```

**示例：**
```
验证以下代码是否符合 SDD 规范：

代码：
class StrategicPlan(AggregateRoot):
    def __init__(self, id: UUID, ...):
        super().__init__(id)

规范：
- 领域层零依赖（FR-AR-01）
- 继承 AggregateRoot 基类
- 使用类型注解

检查项：
- Schema 验证
- 类型检查
- 命名规范
- 架构约束（领域层不依赖外部框架）
```

---

## 最佳实践

### 6.1 提示词编写技巧

1. **明确上下文** - 提供足够的背景信息
2. **具体需求** - 清晰描述期望的输出
3. **示例驱动** - 提供示例帮助理解
4. **迭代优化** - 根据输出调整提示词

### 6.2 代码审查技巧

1. **验证测试** - 确保生成的测试能运行
2. **检查覆盖率** - 确保覆盖所有场景
3. **验证规范** - 确保符合 SDD 规范
4. **人工审查** - 不要完全依赖 AI 生成

### 6.3 常见问题解决

**问题：** 生成的代码不符合项目规范

**解决：**
```
请按照以下项目规范重新生成：
- 使用 [具体规范]
- 遵循 [命名约定]
- 参考 [示例代码]
```

**问题：** 生成的测试覆盖率不足

**解决：**
```
请补充以下场景的测试：
- [边界条件]
- [异常路径]
- [特殊场景]
```

---

## 常见问题

### Q1: Qwen Code Agent 生成的代码可以直接使用吗？

**A:** 不建议直接使用。应该：
1. 审查生成的代码
2. 运行测试验证
3. 根据项目规范调整
4. 确保符合架构约束

### Q2: 如何让 Qwen Code Agent 理解项目规范？

**A:** 提供项目规范文档：
```
请参考以下项目规范：
- 架构规范：[architecture.md]
- 编码规范：[coding-standards.md]
- 测试规范：[testing.md]
```

### Q3: TDD 红阶段测试失败是正常的吗？

**A:** 是的！TDD 红阶段测试应该失败，这证明：
1. 测试是有效的（不是假阳性）
2. 实现代码确实需要编写
3. 测试驱动了开发流程

### Q4: 如何平衡 SDD 规范和 TDD 测试？

**A:** 两者相辅相成：
- SDD 规范定义"做什么"
- TDD 测试验证"做得对"
- Qwen Code Agent 辅助两者

---

## 相关文档

- [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md)
- [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md)
- [Epic 1 Story 1.1 试点计划](./epic1-story1.1-pilot-plan.md)
- [SDD+TDD 整合指南](./sdd-tdd-integration-guide.md)

---

**文档结束**
