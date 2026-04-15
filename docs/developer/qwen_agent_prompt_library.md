# Qwen Code Agent 提示词库

**版本:** 1.0.0
**日期:** 2026-03-04
**作者:** Agimtech 团队

---

## 目录

1. [SDD 规范定义](#sdd-规范定义)
2. [TDD 测试生成](#tdd-测试生成)
3. [代码实现](#代码实现)
4. [重构优化](#重构优化)
5. [文档生成](#文档生成)
6. [代码审查](#代码审查)

---

## SDD 规范定义

### 1.1 领域事件 Schema

**提示词：**
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

---

### 1.2 API 契约

**提示词：**
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

### 1.3 验收标准（Gherkin）

**提示词：**
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

---

## TDD 测试生成

### 2.1 单元测试初稿

**提示词：**
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

---

### 2.2 验收测试实现

**提示词：**
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

**示例：**
```
基于以下 Gherkin 验收标准，生成 pytest-bdd 测试实现：

Feature: 战略规划领域事件
  Scenario: 创建有效的战略规划创建事件
    Given 一个有效的战略规划创建事件数据
    When 创建 PlanCreated 事件
    Then 事件应该通过 Pydantic 验证
    And 事件类型应该自动设置为'plan.created'

要求：
- 使用 pytest-bdd 装饰器（@given, @when, @then）
- 使用 target_fixture 传递数据
- 包含完整的 fixture 定义
```

---

## 代码实现

### 3.1 最小实现（绿阶段）

**提示词：**
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

---

### 3.2 完整实现

**提示词：**
```
基于以下需求，生成完整实现：

需求：
- [功能需求]
- [性能需求]
- [安全需求]

要求：
- 使用领域驱动设计
- 包含完整的类型注解
- 包含错误处理
- 包含日志记录
```

**示例：**
```
基于以下需求，生成完整实现：

需求：
- 实现战略规划仓储接口
- 支持 CRUD 操作
- 支持事务管理

要求：
- 使用领域驱动设计
- 包含完整的类型注解
- 包含错误处理
- 包含日志记录
```

---

## 重构优化

### 4.1 代码重构建议

**提示词：**
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

---

### 4.2 性能优化

**提示词：**
```
以下代码性能不佳，需要优化：

代码：
[粘贴代码]

性能瓶颈：
- [描述性能问题]

要求：
- 保持测试通过
- 优化算法复杂度
- 减少内存使用
- 添加缓存机制
```

**示例：**
```
以下代码性能不佳，需要优化：

代码：
def find_all_plans():
    plans = []
    for plan_id in plan_ids:
        plan = get_plan_by_id(plan_id)
        plans.append(plan)
    return plans

性能瓶颈：
- 循环查询数据库，N+1 问题

要求：
- 保持测试通过
- 优化算法复杂度
- 减少内存使用
- 添加缓存机制
```

---

## 文档生成

### 5.1 代码注释

**提示词：**
```
为以下代码生成注释：

代码：
[粘贴代码]

要求：
- 使用 Google 风格注释
- 包含参数说明
- 包含返回值说明
- 包含异常说明
```

**示例：**
```
为以下代码生成注释：

代码：
def create_plan(id, plan_type, creator_id):
    plan = StrategicPlan(id, plan_type, creator_id)
    plan.add_event(PlanCreated(plan_id=id, creator_id=creator_id))
    return plan

要求：
- 使用 Google 风格注释
- 包含参数说明
- 包含返回值说明
- 包含异常说明
```

---

### 5.2 API 文档

**提示词：**
```
基于以下代码，生成 API 文档：

代码：
[粘贴代码]

要求：
- 使用 OpenAPI 3.1 格式
- 包含请求/响应示例
- 包含错误响应说明
```

**示例：**
```
基于以下代码，生成 API 文档：

代码：
@app.post("/api/v1/plans")
async def create_plan(plan_data: PlanData):
    plan = plan_service.create(plan_data)
    return {"plan_id": plan.id}

要求：
- 使用 OpenAPI 3.1 格式
- 包含请求/响应示例
- 包含错误响应说明
```

---

## 代码审查

### 6.1 代码质量审查

**提示词：**
```
审查以下代码质量：

代码：
[粘贴代码]

审查要点：
- 代码规范（Ruff）
- 类型注解（MyPy）
- 代码重复
- 复杂度
- 安全性
```

**示例：**
```
审查以下代码质量：

代码：
def process_document(doc):
    # ... 很多代码
    return result

审查要点：
- 代码规范（Ruff）
- 类型注解（MyPy）
- 代码重复
- 复杂度
- 安全性
```

---

### 6.2 安全审查

**提示词：**
```
审查以下代码安全性：

代码：
[粘贴代码]

审查要点：
- SQL 注入
- XSS 攻击
- CSRF 攻击
- 敏感信息泄露
- 权限验证
```

**示例：**
```
审查以下代码安全性：

代码：
@app.get("/api/v1/plans/{plan_id}")
async def get_plan(plan_id):
    plan = db.query(f"SELECT * FROM plans WHERE id = '{plan_id}'")
    return plan

审查要点：
- SQL 注入
- XSS 攻击
- CSRF 攻击
- 敏感信息泄露
- 权限验证
```

---

## 相关文档

- [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md)
- [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md)
- [Qwen Code Agent 使用指南](./qwen_agent.md)

---

**文档结束**
