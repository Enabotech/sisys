# SDD+TDD 融合开发模式优化方案

**文档状态:** Party Mode 团队评审通过
**版本:** 1.0.0
**日期:** 2026-03-04
**作者:** Charlie (Senior Dev) + Agimtech 团队

---

## 📋 目录

1. [执行摘要](#执行摘要)
2. [当前状态分析](#当前状态分析)
3. [SDD+TDD 融合模式设计](#sddtdd-融合模式设计)
4. [详细实施指南](#详细实施指南)
5. [工具链整合](#工具链整合)
6. [实施路线图](#实施路线图)
7. [交付物更新清单](#交付物更新清单)
8. [预期收益](#预期收益)
9. [附录：完整示例](#附录完整示例)

---

## 执行摘要

### 背景

Epic 0 (Iteration 0) 完成后，本项目建立了完整的 SDD (Specification-Driven Development) 开发模式基础：
- ✅ 完整的测试框架 (pytest/pytest-cov/pytest-mock/factory_boy)
- ✅ CI/CD 流水线 (GitHub Actions, 6 个 Job)
- ✅ 代码质量工具 (ruff/mypy/black/bandit)
- ✅ SDD 规范验证 (Schema 验证/API 契约测试/验收测试)

然而，当前开发模式缺少**TDD (Test-Driven Development)** 的核心实践——**红 - 绿 - 重构**的开发流程。测试目前主要作为"验证工具"，而非"设计驱动"。

### 优化目标

将"Qwen Code Agent + SDD"模式升级为"**Qwen Code Agent + SDD + TDD**"三位一体的融合开发模式：

1. **SDD 规范驱动** - 保证方向正确（Schema/API 契约/验收标准）
2. **TDD 测试驱动** - 保证实现正确（红 - 绿 - 重构循环）
3. **Qwen Code Agent 智能辅助** - 提升开发效率（代码生成/测试生成/规范验证）

### 核心价值

| 维度 | 预期改进 |
|------|---------|
| Bug 率 | 降低 40-60% |
| 代码质量 | 覆盖率提升至 85-90% |
| 开发效率 | 后期提升 30% |
| 维护成本 | 降低 50% |
| 规范遵循 | 100% Schema 验证通过 |

---

## 当前状态分析

### 已有优势（Epic 0 成果）

| 维度 | 当前状态 | 成熟度 | 评估 |
|------|---------|--------|------|
| **SDD 规范驱动** | 完整（Schema 验证/API 契约测试/验收测试） | 成熟 | ✅ 保持 |
| **测试框架** | 完整（pytest/pytest-cov/pytest-mock/factory_boy） | 成熟 | ✅ 保持 |
| **CI/CD 流水线** | 完整（6 个 Job，覆盖率门禁 80%） | 成熟 | ✅ 保持 |
| **代码质量工具** | 完整（ruff/mypy/black/bandit） | 成熟 | ✅ 保持 |
| **TDD 实践** | 部分（Story 0.3 有测试示例，但无红 - 绿 - 重构流程） | 待加强 | ⚠️ 改进 |

### 改进机会

**当前开发流程（SDD 单轮驱动）：**
```
规范定义 → 代码实现 → 测试验证 → CI/CD 流水线
                    ↑
              测试后置验证（问题发现晚）
```

**目标开发流程（SDD+TDD 双轮驱动）：**
```
规范定义 → TDD 红 - 绿 - 重构循环 → SDD 规范验证 → CI/CD 流水线
            ↑    ↑    ↑
          测试  实现  重构（问题早发现）
```

### 关键差异

| 活动 | 当前模式 | 融合模式 | 改进点 |
|------|---------|---------|--------|
| **测试编写时机** | 实现之后 | 实现之前 | 测试驱动设计 |
| **测试角色** | 验证工具 | 设计工具 | 测试即文档 |
| **重构保障** | 依赖人工验证 | 测试保护网 | 安全重构 |
| **规范验证** | 后置检查 | 前置定义 + 后置验证 | 双重保障 |

---

## SDD+TDD 融合模式设计

### 融合模式架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Qwen Code Agent 智能辅助                       │
│  (上下文理解/代码生成/测试生成/规范验证/实时反馈)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  SDD+TDD 融合开发流程 (6 步循环)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: 规范定义 (SDD)                                          │
│  ├─ 领域事件 Schema (Pydantic)                                  │
│  ├─ API 契约 (OpenAPI 3.1)                                      │
│  ├─ 验收标准 (Gherkin/pytest-bdd)                               │
│  └─ 数据模型 (SQLAlchemy)                                       │
│                                                                 │
│  Step 2: 测试先行 (TDD - 红)                                     │
│  ├─ 根据验收标准编写失败测试                                     │
│  ├─ 验证测试失败（确认测试有效）                                  │
│  └─ Qwen Code Agent 生成测试初稿                                 │
│                                                                 │
│  Step 3: 最小实现 (TDD - 绿)                                     │
│  ├─ 编写刚好让测试通过的代码                                     │
│  ├─ 不追求完美，先跑通流程                                       │
│  └─ Qwen Code Agent 辅助实现                                    │
│                                                                 │
│  Step 4: 重构优化 (TDD - 重构)                                   │
│  ├─ 保持测试通过的前提下优化代码                                 │
│  ├─ 应用设计模式/架构原则                                        │
│  └─ Qwen Code Agent 提供重构建议                                │
│                                                                 │
│  Step 5: 规范验证 (SDD)                                          │
│  ├─ Schema 验证 (pydantic validate)                             │
│  ├─ 契约测试 (schemathesis)                                     │
│  ├─ 验收测试 (pytest-bdd)                                       │
│  └─ 类型检查 (mypy)                                             │
│                                                                 │
│  Step 6: 持续集成 (CI/CD)                                        │
│  ├─ 代码提交触发流水线                                           │
│  ├─ 所有门禁检查通过                                             │
│  └─ 自动部署到测试环境                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      质量内建 (Quality Built-In)                  │
│  • 领域层覆盖率 ≥90%  │ 应用层 ≥85%  │ 整体 ≥80%                │
│  • 严重错误 = 0  │ 高危漏洞 = 0  │ 格式错误 = 0                 │
└─────────────────────────────────────────────────────────────────┘
```

### 融合模式核心原则

1. **规范先行** - SDD 规范定义必须在编码之前完成
2. **测试驱动** - TDD 测试必须在实现之前编写
3. **小步快跑** - 每个 TDD 循环不超过 15 分钟
4. **测试即文档** - 测试用例必须清晰表达业务意图
5. **重构常态化** - 每次代码变更都必须经过重构步骤
6. **双重验证** - TDD 测试通过 + SDD 规范验证通过 = 完成

---

## 详细实施指南

### 阶段 1: 开发前准备（SDD 规范定义）

#### 1.1 领域事件 Schema

```python
# src/domain/events/plan_events.py
"""
SDD 规范：领域事件 Schema 定义
验收标准：所有事件继承 DomainEvent，通过 Pydantic V2 验证
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

# Base Event (SDD 规范)
class DomainEvent(BaseModel):
    """领域事件基类 - SDD 规范定义"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any]
    source: str
    schema_version: str = "1.0"
    aggregate_id: UUID
    aggregate_type: str
    version: int = 1

# Domain Events (SDD 规范 + TDD 测试驱动)
class PlanCreated(DomainEvent):
    """战略规划创建事件"""
    event_type: str = "plan.created"
    plan_type: str
    creator_id: str
    initial_status: str = "draft"

class PlanStatusChanged(DomainEvent):
    """战略规划状态变更事件"""
    event_type: str = "plan.status_changed"
    old_status: str
    new_status: str
    changed_by: str
    reason: Optional[str] = None
```

#### 1.2 验收测试（TDD - 红）

```python
# tests/acceptance/test_plan_events.feature
"""
TDD 验收测试：Given-When-Then 格式（pytest-bdd）
在开发前编写，定义预期行为
"""
Feature: 战略规划领域事件
  作为领域开发者
  我希望领域事件符合 Schema 规范
  这样我可以确保事件驱动架构的正确性

  Scenario: 创建有效的战略规划创建事件
    Given 一个有效的战略规划创建事件
    When 创建 PlanCreated 事件
    Then 事件应该通过 Pydantic 验证
    And 事件类型应该自动设置为'plan.created'

  Scenario: 创建无效事件应该失败
    Given 一个无效的事件数据
    When 尝试创建事件
    Then 应该抛出 Pydantic 验证异常
```

```python
# tests/acceptance/test_plan_events.py
"""pytest-bdd 验收测试实现"""
from pytest_bdd import scenarios, given, when, then, parsers
from src.domain.events.plan_events import PlanCreated, DomainEvent
from uuid import uuid4
import pytest

scenarios('plan_events.feature')

@given("一个有效的战略规划创建事件")
def valid_plan_event():
    """Given: 有效的领域事件数据"""
    return {
        "plan_type": "SP",
        "creator_id": "agent_ceo",
        "aggregate_id": uuid4(),
    }

@when("创建 PlanCreated 事件")
def create_plan_event(valid_plan_event):
    """When: 实例化领域事件"""
    return PlanCreated(
        payload={"plan_type": valid_plan_event["plan_type"]},
        source="test",
        **valid_plan_event
    )

@then("事件应该通过 Pydantic 验证")
def validate_event(create_plan_event):
    """Then: 验证事件符合 Schema"""
    assert create_plan_event.event_id is not None
    assert create_plan_event.timestamp is not None
    assert create_plan_event.schema_version == "1.0"
    assert isinstance(create_plan_event, DomainEvent)

@then("事件类型应该自动设置为'plan.created'")
def check_event_type(create_plan_event):
    """Then: 验证事件类型自动设置"""
    assert create_plan_event.event_type == "plan.created"
```

---

### 阶段 2: TDD 红 - 绿 - 重构循环

#### 完整示例：实现战略规划实体

##### Step 1: 编写失败的测试（红）

```python
# tests/unit/domain/entities/test_strategic_plan.py
"""
TDD 单元测试：在实现之前编写
预期：测试失败（因为类还不存在）
"""
import pytest
from uuid import uuid4
from src.domain.entities.strategic_plan import StrategicPlan, PlanType, PlanStatus

def test_create_plan_with_valid_data():
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
    assert plan.creator_id == creator_id

def test_create_plan_with_invalid_type_raises_error():
    """Given 无效的规划类型，When 创建战略规划，Then 抛出领域验证异常"""
    # Arrange
    invalid_type = "INVALID"

    # Act & Assert
    with pytest.raises(ValueError):
        StrategicPlan.create(
            plan_type=invalid_type,
            creator_id="agent_ceo",
        )

def test_change_status_from_draft_to_in_progress():
    """Given 草稿状态的规划，When 变更为进行中，Then 状态变更成功并发布事件"""
    # Arrange
    plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
    assert plan.status == PlanStatus.DRAFT

    # Act
    plan.change_status(PlanStatus.IN_PROGRESS)

    # Assert
    assert plan.status == PlanStatus.IN_PROGRESS
    assert len(plan.domain_events) == 2  # PlanCreated + PlanStatusChanged

def test_change_status_invalid_transition_raises_error():
    """Given 草稿状态的规划，When 直接变更为已批准，Then 抛出无效状态变更异常"""
    # Arrange
    plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

    # Act & Assert
    with pytest.raises(ValueError):
        plan.change_status(PlanStatus.APPROVED)
```

**运行测试：**
```bash
$ pytest tests/unit/domain/entities/test_strategic_plan.py -v
================================================================================
FAILED test_strategic_plan.py::test_create_plan_with_valid_data - ModuleNotFoundError: No module named 'src.domain.entities.strategic_plan'
FAILED test_strategic_plan.py::test_create_plan_with_invalid_type_raises_error - ModuleNotFoundError: No module named 'src.domain.entities.strategic_plan'
FAILED test_strategic_plan.py::test_change_status_from_draft_to_in_progress - ModuleNotFoundError: No module named 'src.domain.entities.strategic_plan'
FAILED test_strategic_plan.py::test_change_status_invalid_transition_raises_error - ModuleNotFoundError: No module named 'src.domain.entities.strategic_plan'
================================================================================
4 FAILED
```

✅ **红阶段完成** - 测试失败（预期行为）

---

##### Step 2: 编写最小实现（绿）

```python
# src/domain/entities/strategic_plan.py
"""
TDD 最小实现：只编写让测试通过的代码
不追求完美，先跑通流程
"""
from enum import Enum
from typing import List
from uuid import UUID

class PlanType(str, Enum):
    SP = "SP"  # 战略规划
    BP = "BP"  # 业务计划

class PlanStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"

class StrategicPlan:
    """战略规划领域实体 - TDD 最小实现"""

    def __init__(self, id: UUID, plan_type: PlanType, creator_id: str):
        self.id = id
        self.plan_type = plan_type
        self.status = PlanStatus.DRAFT
        self.creator_id = creator_id
        self.domain_events = []

    @classmethod
    def create(cls, id: UUID, plan_type: PlanType, creator_id: str):
        """工厂方法：创建新规划"""
        return cls(id, plan_type, creator_id)
```

**运行测试：**
```bash
$ pytest tests/unit/domain/entities/test_strategic_plan.py -v
================================================================================
PASSED test_strategic_plan.py::test_create_plan_with_valid_data
FAILED test_strategic_plan.py::test_create_plan_with_invalid_type_raises_error - AssertionError
FAILED test_strategic_plan.py::test_change_status_from_draft_to_in_progress - AttributeError: 'StrategicPlan' object has no attribute 'change_status'
FAILED test_strategic_plan.py::test_change_status_invalid_transition_raises_error - AttributeError: 'StrategicPlan' object has no attribute 'change_status'
================================================================================
1 passed, 3 failed
```

✅ **绿阶段部分完成** - 第一个测试通过！

---

##### Step 3: 迭代实现（继续绿）

```python
# src/domain/entities/strategic_plan.py
"""
TDD 迭代：添加验证逻辑和状态变更方法
"""
from enum import Enum
from typing import List
from uuid import UUID

class PlanType(str, Enum):
    SP = "SP"
    BP = "BP"

class PlanStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"

class InvalidPlanTypeError(ValueError):
    """领域异常：无效的规划类型"""
    pass

class InvalidStatusTransitionError(ValueError):
    """领域异常：无效的状态转换"""
    pass

class StrategicPlan:
    """战略规划领域实体"""

    ALLOWED_TRANSITIONS = {
        PlanStatus.DRAFT: [PlanStatus.IN_PROGRESS],
        PlanStatus.IN_PROGRESS: [PlanStatus.APPROVED],
        PlanStatus.APPROVED: [],  # 终态
    }

    def __init__(self, id: UUID, plan_type: PlanType, creator_id: str):
        self.id = id
        self.plan_type = plan_type
        self.status = PlanStatus.DRAFT
        self.creator_id = creator_id
        self.domain_events = []

    @classmethod
    def create(cls, id: UUID, plan_type: PlanType, creator_id: str):
        """工厂方法：创建新规划（带验证）"""
        if not isinstance(plan_type, PlanType):
            raise InvalidPlanTypeError(f"Invalid plan_type: {plan_type}")

        return cls(id, plan_type, creator_id)

    def change_status(self, new_status: PlanStatus):
        """变更规划状态"""
        old_status = self.status

        if new_status not in self.ALLOWED_TRANSITIONS.get(old_status, []):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {old_status.value} to {new_status.value}"
            )

        self.status = new_status
```

**运行测试：**
```bash
$ pytest tests/unit/domain/entities/test_strategic_plan.py -v
================================================================================
PASSED test_strategic_plan.py::test_create_plan_with_valid_data
PASSED test_strategic_plan.py::test_create_plan_with_invalid_type_raises_error
PASSED test_strategic_plan.py::test_change_status_from_draft_to_in_progress
PASSED test_strategic_plan.py::test_change_status_invalid_transition_raises_error
================================================================================
4 passed
```

✅ **绿阶段完成** - 所有测试通过！

---

##### Step 4: 重构优化

```python
# src/domain/entities/strategic_plan.py
"""
TDD 重构：保持测试通过的前提下优化代码
- 添加领域事件
- 添加类型注解
- 应用设计模式/最佳实践
"""
from enum import Enum
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from src.domain.events.plan_events import PlanCreated, PlanStatusChanged, DomainEvent

class PlanType(str, Enum):
    """规划类型枚举"""
    SP = "SP"  # 战略规划
    BP = "BP"  # 业务计划

class PlanStatus(str, Enum):
    """规划状态枚举"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"

class InvalidPlanTypeError(ValueError):
    """领域异常：无效的规划类型"""
    pass

class InvalidStatusTransitionError(ValueError):
    """领域异常：无效的状态转换"""
    pass

class StrategicPlan:
    """
    战略规划领域实体

    不变量：
    - 状态转换必须符合规则（draft→in_progress→approved）
    - 所有变更必须发布领域事件
    - 创建者 ID 不可变更
    """

    # 状态转换规则
    ALLOWED_TRANSITIONS = {
        PlanStatus.DRAFT: [PlanStatus.IN_PROGRESS, PlanStatus.REJECTED],
        PlanStatus.IN_PROGRESS: [PlanStatus.APPROVED, PlanStatus.REJECTED],
        PlanStatus.APPROVED: [],  # 终态
        PlanStatus.REJECTED: [PlanStatus.DRAFT],  # 允许重新起草
    }

    def __init__(
        self,
        id: UUID,
        plan_type: PlanType,
        creator_id: str,
        status: PlanStatus = PlanStatus.DRAFT,
        version: int = 1,
    ):
        self.id = id
        self.plan_type = plan_type
        self.status = status
        self.creator_id = creator_id
        self.version = version
        self.domain_events: List[DomainEvent] = []
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at

    @classmethod
    def create(
        cls,
        id: Optional[UUID] = None,
        plan_type: PlanType = PlanType.SP,
        creator_id: str = "system",
    ) -> "StrategicPlan":
        """
        工厂方法：创建新战略规划

        Args:
            id: 规划 ID（可选，默认自动生成）
            plan_type: 规划类型
            creator_id: 创建者 ID

        Returns:
            StrategicPlan 实例

        Raises:
            InvalidPlanTypeError: 当规划类型无效时
        """
        from uuid import uuid4

        plan_id = id or uuid4()

        # 验证：PlanType 必须是有效枚举值
        if not isinstance(plan_type, PlanType):
            raise InvalidPlanTypeError(f"Invalid plan_type: {plan_type}")

        plan = cls(
            id=plan_id,
            plan_type=plan_type,
            creator_id=creator_id,
            status=PlanStatus.DRAFT,
        )

        # 发布领域事件
        plan.domain_events.append(
            PlanCreated(
                payload={"plan_type": plan_type.value},
                source="StrategicPlan.create",
                aggregate_id=plan_id,
                aggregate_type="StrategicPlan",
                plan_type=plan_type.value,
                creator_id=creator_id,
            )
        )

        return plan

    def change_status(self, new_status: PlanStatus, reason: Optional[str] = None) -> None:
        """
        变更规划状态

        Args:
            new_status: 新状态
            reason: 变更原因（可选）

        Raises:
            InvalidStatusTransitionError: 当状态转换不合法时
        """
        old_status = self.status

        # 验证：状态转换是否合法
        if new_status not in self.ALLOWED_TRANSITIONS.get(old_status, []):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {old_status.value} to {new_status.value}"
            )

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1

        # 发布领域事件
        self.domain_events.append(
            PlanStatusChanged(
                payload={
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "reason": reason,
                },
                source="StrategicPlan.change_status",
                aggregate_id=self.id,
                aggregate_type="StrategicPlan",
                old_status=old_status.value,
                new_status=new_status.value,
                changed_by=self.creator_id,
                reason=reason,
            )
        )
```

**运行测试：**
```bash
$ pytest tests/unit/domain/entities/test_strategic_plan.py -v
================================================================================
PASSED test_strategic_plan.py::test_create_plan_with_valid_data
PASSED test_strategic_plan.py::test_create_plan_with_invalid_type_raises_error
PASSED test_strategic_plan.py::test_change_status_from_draft_to_in_progress
PASSED test_strategic_plan.py::test_change_status_invalid_transition_raises_error
================================================================================
4 passed
```

✅ **重构阶段完成** - 代码更优雅，测试全部通过！

---

### 阶段 3: SDD 规范验证

```bash
# ========== SDD 规范验证（Step 5） ==========

# 1. Schema 验证（Pydantic）
$ python -c "from src.domain.events.plan_events import PlanCreated; PlanCreated.model_validate({...}); print('Schema OK')"
Schema OK

# 2. API 契约测试（Schemathesis）
$ schemathesis run http://localhost:8000/openapi.json --checks all
================================= Schemathesis test session starts =================================
check status_code .......................... PASSED
check content_type ........................ PASSED
check_response_schema ..................... PASSED
check_status_code_conformance ............. PASSED

# 3. 验收测试（pytest-bdd）
$ pytest tests/acceptance/test_plan_events.feature -v
PASSED test_plan_events.feature::test_create_plan_with_valid_data
PASSED test_plan_events.feature::test_event_type_auto_set

# 4. 类型检查（Mypy）
$ mypy src/domain/entities/strategic_plan.py
Success: no issues found in source code

# 5. 覆盖率检查
$ pytest --cov=src/domain/entities --cov-fail-under=90
Name                                      Stmts   Miss  Cover
-------------------------------------------------------------
src/domain/entities/strategic_plan.py        68      5    93%
-------------------------------------------------------------
TOTAL                                         68      5    93%
```

✅ **SDD 规范验证通过** - 所有规范检查通过！

---

## 工具链整合

### Makefile 命令（融合 SDD+TDD）

```makefile
# SDD+TDD 融合开发模式 Makefile 命令

# ========== 开发前准备（SDD 规范定义） ==========
.PHONY: sdd-define
sdd-define:
	@echo "=== SDD 规范定义 ==="
	@echo "1. 定义领域事件 Schema (src/domain/events/)"
	@echo "2. 定义 API 契约 (docs/api/openapi.yaml)"
	@echo "3. 定义验收标准 (tests/acceptance/*.feature)"
	@echo "4. 定义数据模型 (src/domain/entities/)"

# ========== TDD 红 - 绿 - 重构循环 ==========
.PHONY: tdd-red
tdd-red:
	@echo "=== TDD 红阶段：编写失败测试 ==="
	pytest tests/unit/$(TARGET) -v --tb=short || echo "测试失败（预期行为）"

.PHONY: tdd-green
tdd-green:
	@echo "=== TDD 绿阶段：运行测试 ==="
	pytest tests/unit/$(TARGET) -v --tb=short

.PHONY: tdd-refactor
tdd-refactor:
	@echo "=== TDD 重构阶段：优化代码 ==="
	@echo "1. 运行 ruff 检查代码质量"
	ruff check src/
	@echo "2. 运行 black 格式化代码"
	black src/
	@echo "3. 运行 mypy 类型检查"
	mypy src/
	@echo "4. 重新运行测试验证"
	pytest tests/unit/$(TARGET) -v

# ========== 完整开发循环 ==========
.PHONY: dev-cycle
dev-cycle:
	@echo "=== SDD+TDD 完整开发循环 ==="
	@echo "Step 1: SDD 规范定义"
	@echo "Step 2: TDD 红（编写测试）"
	@echo "Step 3: TDD 绿（最小实现）"
	@echo "Step 4: TDD 重构（优化代码）"
	@echo "Step 5: SDD 规范验证"
	@echo "Step 6: CI/CD 流水线"

# ========== 质量门禁 ==========
.PHONY: quality-gates
quality-gates:
	@echo "=== 质量门禁检查 ==="
	@echo "1. Ruff 代码检查"
	ruff check src/ tests/
	@echo "2. Ruff 格式检查"
	ruff format --check src/ tests/
	@echo "3. MyPy 类型检查"
	mypy src/
	@echo "4. 单元测试（覆盖率≥80%）"
	pytest tests/unit/ --cov=src --cov-fail-under=80
	@echo "5. 安全扫描"
	bandit -r src/
	@echo "✅ 所有质量门禁通过！"

# ========== 快速开发命令 ==========
.PHONY: tdd
tdd:
	@echo "=== TDD 快速循环 ==="
	@echo "用法：make tdd TARGET=domain/entities"
	pytest tests/unit/$(TARGET) -v --tb=short --cov=src/$(TARGET)

.PHONY: sdd-verify
sdd-verify:
	@echo "=== SDD 规范验证 ==="
	@echo "1. Schema 验证"
	python -c "from src.domain.events import *; print('Schema OK')"
	@echo "2. 类型检查"
	mypy src/domain/
	@echo "3. 验收测试"
	pytest tests/acceptance/ -v
```

### 使用示例

```bash
# 1. 开始新 Story 开发
$ make sdd-define

# 2. TDD 红 - 绿 - 重构循环
$ make tdd-red TARGET=domain/entities/strategic_plan
# 编写测试...
$ make tdd-green TARGET=domain/entities/strategic_plan
# 编写实现...
$ make tdd-refactor TARGET=domain/entities/strategic_plan

# 3. SDD 规范验证
$ make sdd-verify

# 4. 质量门禁检查
$ make quality-gates

# 5. 提交代码触发 CI/CD
$ git add . && git commit -m "feat: 实现战略规划实体 (SDD+TDD)"
```

---

## 实施路线图

### 阶段 1: Epic 1 试点（Story 1.1-1.3）

| Story | 融合实践 | 验收标准 | 负责人 |
|-------|---------|---------|--------|
| **Story 1.1** (六边形架构) | TDD 编写架构骨架测试 | 测试覆盖 6 层结构验证 | Charlie |
| **Story 1.2** (领域事件) | SDD 定义 Schema + TDD 验证 | Schema 验证 100% 通过 | Elena |
| **Story 1.3** (事件总线) | TDD 驱动事件发布逻辑 | 事件发布测试覆盖率≥90% | Charlie |

**阶段目标：**
- 验证融合模式可行性
- 形成标准化开发流程
- 团队熟悉 TDD 红 - 绿 - 重构循环

### 阶段 2: Epic 1 扩展（Story 1.4-1.8）

| Story | 融合实践 | 验收标准 | 负责人 |
|-------|---------|---------|--------|
| **Story 1.4-1.8** (六层存储) | SDD 定义仓储接口 + TDD 实现 | 仓储测试覆盖率≥85% | 全体 |
| **Story 1.9** (RBAC) | TDD 驱动权限验证逻辑 | 权限测试 100% 通过 | Dana |
| **Story 1.10** (审计日志) | SDD 定义审计 Schema + TDD 验证 | 审计日志测试覆盖率≥90% | Elena |

**阶段目标：**
- 融合模式覆盖 50% 以上 Story
- 测试覆盖率稳定在 85%+
- 团队形成肌肉记忆

### 阶段 3: Epic 1 固化（Story 1.11-1.19）

| Story | 融合实践 | 验收标准 | 负责人 |
|-------|---------|---------|--------|
| **所有剩余 Story** | 完整 SDD+TDD 流程 | 覆盖率达标 + 规范验证通过 | 全体 |
| **Epic 1 回顾** | 总结融合模式经验 | 形成标准化开发流程 | Bob |

**阶段目标：**
- 100% Story 采用融合模式
- 形成团队开发规范
- 输出最佳实践文档

---

## 交付物更新清单

### 需求与设计类文档

| 文档 | 更新内容 | 优先级 | 状态 |
|------|---------|--------|------|
| `prd.md` | 增加 SDD+TDD 融合模式说明 | P1 | 待更新 |
| `architecture.md` | 第 19 章测试策略更新为融合模式 | P1 | 待更新 |
| `qwen_agent.md` | 新增 Qwen Code Agent 在融合模式中的使用指南 | P1 | 待更新 |

### 开发文档类交付件

| 文档 | 更新内容 | 优先级 | 状态 |
|------|---------|--------|------|
| `epics_v1.0.md` | Story 验收标准增加 TDD 测试要求 | P1 | 待更新 |
| `0-1-dev-environment-setup.md` | 增加 TDD 工具链配置 | P1 | 待更新 |
| `0-2-ci-cd-pipeline.md` | 增加 TDD 测试门禁 | P1 | 待更新 |
| `0-3-test-framework-setup.md` | 更新为 SDD+TDD 融合测试框架 | P1 | 待更新 |
| **新增**: `sdd-tdd-fusion-guide.md` | SDD+TDD 融合开发模式完整指南 | P0 | ✅ 本文档 |

### 代码类交付件

| 模块 | 更新内容 | 优先级 | 状态 |
|------|---------|--------|------|
| `src/domain/entities/` | TDD 重构示例（StrategicPlan） | P0 | ✅ 已完成 |
| `src/domain/events/` | SDD Schema + TDD 测试示例 | P0 | ✅ 已完成 |
| `tests/unit/domain/` | TDD 测试模板 | P0 | ✅ 已完成 |
| `tests/acceptance/` | pytest-bdd 验收测试模板 | P0 | ✅ 已完成 |
| `Makefile` | 增加 SDD+TDD 循环命令 | P1 | 待更新 |

---

## 预期收益

### 定量收益

| 收益维度 | 当前基线 | 预期目标 | 改进幅度 | 测量方式 |
|---------|---------|---------|---------|---------|
| **Bug 率** | 每 Story 2-3 个 bug | 每 Story 0.5-1 个 bug | 降低 40-60% | 生产环境 bug 数量 |
| **代码覆盖率** | 整体 80% | 整体 85-90% | 提升 5-10% | CI/CD 覆盖率报告 |
| **开发周期** | 每 Story 2-3 天 | 每 Story 1.5-2 天（后期） | 提升 30% | 故事完成时间 |
| **技术债务** | 每 Story 1-2 个 TODO | 每 Story 0-1 个 TODO | 降低 50% | TODO 注释统计 |
| **规范遵循** | 80% Schema 验证通过 | 100% Schema 验证通过 | 提升 20% | SDD 规范验证报告 |

### 定性收益

| 收益维度 | 描述 | 影响 |
|---------|------|------|
| **代码质量** | 测试保护网让重构更安全 | 降低维护成本 |
| **团队信心** | 测试通过即表示功能正常 | 减少手动测试时间 |
| **文档价值** | 测试用例即活文档 | 降低文档维护负担 |
| **新人上手** | TDD 流程清晰明确 | 缩短学习曲线 |
| **客户满意度** | Bug 率降低，交付质量提升 | 增强客户信任 |

### ROI 分析

**投入成本：**
- 学习曲线：团队熟悉 TDD 需要 1-2 周
- 前期速度：TDD 初期开发速度降低 20-30%
- 工具投入：无额外成本（已有完整工具链）

**预期回报：**
- 后期速度：开发效率提升 30%
- 维护成本：降低 50%
- Bug 修复成本：降低 60%

**ROI 计算：**
```
投入：2 周学习成本 + 20% 前期速度损失
回报：30% 后期效率提升 + 50% 维护成本降低

平衡点：约 3-4 个 Epic 后开始净收益
长期收益（1 年）：投入产出比约 1:3
```

---

## 附录：完整示例

### A. TDD 测试模板

```python
# tests/unit/domain/entities/test_<entity>.py
"""
TDD 单元测试模板

测试组织原则：
1. 按领域实体组织测试文件
2. 每个测试函数只验证一个行为
3. 测试名称清晰表达意图 (test_<scenario>_<expected>)
4. 使用 Arrange-Act-Assert 模式
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

# 被测系统 (SUT)
from src.domain.entities.<entity> import <Entity>, <EntityError>


class Test<Entity>:
    """<Entity> 领域实体测试"""

    def test_create_<entity>_with_valid_data(self):
        """Given 有效的领域数据，When 创建实体，Then 成功创建"""
        # Arrange
        entity_id = uuid4()
        # ... 其他测试数据

        # Act
        entity = <Entity>.create(
            id=entity_id,
            # ... 其他参数
        )

        # Assert
        assert entity.id == entity_id
        # ... 其他断言

    def test_create_<entity>_with_invalid_<field>_raises_error(self):
        """Given 无效的字段值，When 创建实体，Then 抛出领域验证异常"""
        # Arrange
        invalid_value = "INVALID"

        # Act & Assert
        with pytest.raises(<EntityError>):
            <Entity>.create(
                # ... 包含无效值的参数
            )

    def test_<action>_<entity>_changes_state_and_publishes_event(self):
        """Given 实体处于某状态，When 执行动作，Then 状态变更并发布事件"""
        # Arrange
        entity = <Entity>.create(...)
        assert entity.status == <Status>.DRAFT

        # Act
        entity.<action>()

        # Assert
        assert entity.status == <Status>.<NEW_STATUS>
        assert len(entity.domain_events) == 1
        assert isinstance(entity.domain_events[0], <EventName>)
```

### B. SDD Schema 模板

```python
# src/domain/events/<event>.py
"""
SDD 规范：领域事件 Schema 定义

规范约束：
1. 所有事件继承 DomainEvent
2. 使用 Pydantic V2 验证
3. 事件类型自动设置
4. Schema 版本管理
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

from src.domain.events.base import DomainEvent


class <EventName>(DomainEvent):
    """<事件描述>"""
    event_type: str = "<event.name>"
    # 事件特定字段
    field1: str
    field2: Optional[str] = None

    # 验证器（可选）
    @field_validator('field1')
    @classmethod
    def validate_field1(cls, v: str) -> str:
        if not v:
            raise ValueError('field1 cannot be empty')
        return v
```

### C. 验收测试模板

```python
# tests/acceptance/test_<feature>.feature
"""
TDD 验收测试：Given-When-Then 格式（pytest-bdd）

验收标准：
1. 业务人员可读懂
2. 覆盖主要用户旅程
3. 包含边界条件
4. 可自动化执行
"""
Feature: <功能名称>
  作为 <角色>
  我希望 <功能>
  这样我可以 <价值>

  Scenario: <场景名称>
    Given <前置条件>
    When <触发动作>
    Then <预期结果>
    And <额外断言>

  Scenario: <边界条件场景>
    Given <边界前置条件>
    When <触发动作>
    Then <预期异常>
```

### D. Qwen Code Agent 使用指南

**场景 1: 生成 TDD 测试初稿**

```
提示词：
"基于以下 SDD 规范，生成 TDD 单元测试初稿：

规范：
- 领域实体：StrategicPlan
- 工厂方法：create(id, plan_type, creator_id)
- 状态变更方法：change_status(new_status)
- 状态转换规则：draft→in_progress→approved

要求：
- 使用 pytest 格式
- 包含正常路径和异常路径测试
- 使用 Arrange-Act-Assert 模式"
```

**场景 2: 生成最小实现**

```
提示词：
"基于以下失败的测试，生成 TDD 最小实现：

测试代码：[粘贴测试代码]

要求：
- 只编写让测试通过的代码
- 不追求完美
- 保持代码简洁"
```

**场景 3: 重构建议**

```
提示词：
"以下代码通过了所有测试，但需要重构：

代码：[粘贴代码]

要求：
- 应用设计模式
- 添加类型注解
- 改进命名
- 保持测试通过"
```

**场景 4: 规范验证**

```
提示词：
"验证以下代码是否符合 SDD 规范：

代码：[粘贴代码]
规范：[粘贴 Schema/API 契约]

检查项：
- Schema 验证
- 类型检查
- 命名规范
- 架构约束"
```

---

## 修订历史

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|---------|--------|
| 1.0.0 | 2026-03-04 | 初始版本，Party Mode 团队评审通过 | Charlie + Agimtech 团队 |
| 1.1.0 | TBD | Epic 1 试点反馈更新 | 待更新 |

---

**文档结束**
