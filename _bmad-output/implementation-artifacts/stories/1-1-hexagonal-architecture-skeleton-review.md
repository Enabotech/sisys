# Code Review Report — Story 1.1: 六边形架构骨架

**Review Date:** 2026-04-12
**Commit:** `325973a feat(story-1.1): implement hexagonal architecture skeleton`
**Review Mode:** Full Review (with Spec)
**Reviewers:** Blind Hunter, Edge Case Hunter, Acceptance Auditor
**Status:** ⚠️ **不通过 — 需修复 5 个 P0 问题后重新审查**

---

## 📊 审查摘要

| 指标 | 值 |
|------|-----|
| **变更文件数** | 39 |
| **+添加 / -删除** | +2,158 / -429 |
| **总发现数** | 47 |
| **P0 阻断项** | 5 |
| **P1 高优先级** | 8 |
| **P2 中优先级** | 5 |
| **P3 低优先级** | 4 |
| **代码质量评分** | **6.5/10**（修复 P0 后预期 8.5/10） |

---

## 🔴 P0 阻断性问题（必须修复）

### P0-01: `DomainEvent.from_dict()` 序列化/反序列化在 `aggregate_id=None` 时崩溃

**文件:** `src/domain/events/base.py:52-61`

**问题描述:**
`to_dict()` 总是将 `aggregate_id` 转为字符串 `"None"`，而 `from_dict()` 直接调用 `uuid.UUID("None")` 导致 `ValueError`。任何没有 aggregate_id 的系统级事件都无法进行序列化/反序列化循环。

**复现步骤:**
```python
event = DomainEvent(event_type="Test")  # aggregate_id defaults to None
d = event.to_dict()                     # d["aggregate_id"] == "None"
DomainEvent.from_dict(d)                # ValueError: badly formed hexadecimal UUID string
```

**影响:** 事件溯源/重放管道中数据丢失，生产环境难以诊断。

**修复方案:**
```python
# to_dict() — 条件序列化
def to_dict(self) -> dict[str, Any]:
    result = {
        "event_id": str(self.event_id),
        "event_type": self.event_type,
        "occurred_on": self.occurred_on.isoformat(),
        "payload": self.payload,
    }
    if self.aggregate_id is not None:
        result["aggregate_id"] = str(self.aggregate_id)
    return result

# from_dict() — 安全解析
@classmethod
def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
    agg_id = None
    if data.get("aggregate_id") is not None:
        agg_id = uuid.UUID(data["aggregate_id"])
    return cls(
        event_id=uuid.UUID(data["event_id"]),
        event_type=data["event_type"],
        aggregate_id=agg_id,
        payload=data.get("payload", {}),
        occurred_on=datetime.fromisoformat(data["occurred_on"]),
    )
```

**审查层:** Edge Case Hunter

---

### P0-02: `StrategicPlan.advance_phase()` 允许跳过中间阶段

**文件:** `src/domain/entities/strategic_plan.py:73-85`

**问题描述:**
`advance_phase()` 只检查 `next_idx > current_idx`，不要求 `next_idx == current_idx + 1`。调用者可以从 `STRATEGIC_INTENT` 直接跳到 `EXECUTION_MONITORING`，跳过 4 个中间阶段。

**复现步骤:**
```python
plan = StrategicPlan(plan_id=uuid4(), name="Test")
plan.advance_phase(BLMPhase.EXECUTION_MONITORING)  # 跳过 4 个阶段
```

**影响:** BLM 模型语义被违反，中间阶段检查点从未记录，破坏审计追踪和恢复能力。

**修复方案:**
```python
if next_idx != current_idx + 1:
    raise ValueError("Can only advance to the immediately next phase")
```

**审查层:** Edge Case Hunter

---

### P0-03: `StrategicPlan.advance_phase()` 不检查 `status` 守卫

**文件:** `src/domain/entities/strategic_plan.py:73-85`

**问题描述:**
已归档（`ARCHIVED`）或已批准（`APPROVED`）的计划仍然可以推进阶段。状态生命周期约束在领域层未 enforced。

**复现步骤:**
```python
plan = StrategicPlan(plan_id=uuid4(), name="Test", status=PlanStatus.ARCHIVED)
plan.advance_phase(BLMPhase.MARKET_INSIGHT)  # 成功执行
```

**影响:** 业务生命周期不变量在领域层未强制执行。

**修复方案:**
```python
if self.status in (PlanStatus.ARCHIVED, PlanStatus.APPROVED):
    raise ValueError(f"Cannot advance phase when plan is {self.status.value}")
```

**审查层:** Edge Case Hunter

---

### P0-04: `_get_imports()` 遇到 `SyntaxError` 返回 `[]`，架构测试产生误报

**文件:** `tests/unit/architecture/test_hexagonal_architecture.py:23-26`

**问题描述:**
`ast.parse` 失败时返回 `[]`（空导入列表）。这意味着有语法错误的文件会被静默跳过，测试仍然通过——即使代码已损坏。

**复现步骤:**
```python
# 在 src/domain/entities/agent.py 中添加不完整语法
def foo(  # 缺少闭合括号
# 运行 test_domain_no_external_imports — 仍然通过
```

**影响:** 架构测试假阳性——域代码中的语法错误不会被检测。

**修复方案:**
```python
def _get_imports(file_path: Path) -> list[str]:
    with open(file_path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
            return []  # unreachable, but keeps type checker happy
```

**审查层:** Edge Case Hunter

---

### P0-05: `.importlinter` 域名禁止列表是白名单方式，未列出的包可绕过

**文件:** `.importlinter:9-22`

**问题描述:**
`forbidden_modules` 是显式禁止列表，但 `pyproject.toml` 中的许多第三方包未被列入。例如 `requests`, `httpx`, `docker`, `psycopg2`, `boto3`, `numpy`, `pandas` 等。开发者在域层 `import requests`，`lint-imports` 会通过。

**影响:** 域层"零外部依赖"保证未被完全执行——仅被列出的包被阻止。

**修复方案:**
使用 `independence` 约束替代白名单：
```ini
[importlinter:contract:domain-independent-layer]
name = Domain layer must be an independent layer
type = independence
modules =
    src.domain
```

或者使用 `layers` 约束 + 外部导入检查：
```ini
[importlinter:contract:domain-no-external]
name = Domain layer must not import external packages
type = forbidden
source_modules = src.domain
forbidden_modules = <all external packages>
```

**审查层:** Edge Case Hunter

---

## 🟠 P1 高优先级问题

### P1-01: `Checkpoint.complete()` 可重复调用，覆盖 `completed_at` 时间戳

**文件:** `src/domain/entities/checkpoint.py:63-66`

**修复方案:** 添加状态守卫
```python
def complete(self) -> None:
    if self.status == CheckpointStatus.COMPLETED:
        raise ValueError("Checkpoint is already completed")
    self.status = CheckpointStatus.COMPLETED
    self.completed_at = datetime.now(UTC)
    self.updated_at = self.completed_at
```

---

### P1-02: `Checkpoint.recover()` 可在 COMPLETED 状态调用，静默改写状态

**文件:** `src/domain/entities/checkpoint.py:68-76`

**修复方案:** 添加状态守卫
```python
def recover(self, mode: RecoveryMode) -> None:
    if self.status == CheckpointStatus.COMPLETED:
        raise ValueError("Cannot recover a completed checkpoint")
    self.status = CheckpointStatus.RECOVERED
    self.recovery_mode = mode
    self.updated_at = datetime.now(UTC)
```

---

### P1-03: `Document.embedding` 不验证 NaN/Inf 值，下游 Qdrant 会崩溃

**文件:** `src/domain/entities/document.py`

**修复方案:** 在 `validate()` 中添加 embedding 检查
```python
import math
if self.embedding is not None:
    for i, val in enumerate(self.embedding):
        if not isinstance(val, (int, float)):
            raise ValueError(f"embedding[{i}] must be a number")
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"embedding[{i}] contains NaN/Inf")
```

---

### P1-04: `DomainEvent.payload` 接受不可 JSON 序列化的值

**文件:** `src/domain/events/base.py:30`

**修复方案:** 在 `to_dict()` 中添加序列化验证或使用 `json.dumps()` 检查
```python
import json

def to_dict(self) -> dict[str, Any]:
    # ... existing code ...
    try:
        json.dumps(self.payload)
    except (TypeError, ValueError) as e:
        raise ValueError(f"payload is not JSON serializable: {e}")
    return result
```

---

### P1-05: `Agent` 无状态转换方法，status 通过直接赋值修改

**文件:** `src/domain/entities/agent.py`

**修复方案:** 添加状态转换方法
```python
def start(self) -> None:
    if self.status != AgentStatus.IDLE:
        raise ValueError(f"Can only start from IDLE, current: {self.status.value}")
    self.status = AgentStatus.RUNNING

def complete(self) -> None:
    if self.status != AgentStatus.RUNNING:
        raise ValueError(f"Can only complete from RUNNING, current: {self.status.value}")
    self.status = AgentStatus.COMPLETED

def fail(self, reason: str = "") -> None:
    self.status = AgentStatus.FAILED
```

---

### P1-06: `correction_records: list[dict]` 无 schema 验证

**文件:** `src/domain/entities/checkpoint.py:40`

**修复方案:** 定义强类型 `CorrectionRecord` dataclass 替代 `dict`

---

### P1-07: `EventPublisher` 不是 ABC，可被直接实例化

**文件:** `src/domain/events/publisher.py`

**修复方案:** 改为抽象基类
```python
from abc import ABC, abstractmethod

class EventPublisher(ABC):
    @abstractmethod
    def publish(self, event: "DomainEvent") -> None:
        raise NotImplementedError
```

---

### P1-08: `BaseRepository` 使用 bare `raise NotImplementedError`（无错误消息）

**文件:** `src/domain/repositories/base.py:27,34,41,48`

**修复方案:**
```python
raise NotImplementedError("BaseRepository.get_by_id must be implemented by subclass")
```

---

## 🟡 P2 中优先级问题

### P2-01: `TestRuffCheck` 注释说接受 exit code 0/1，但断言只接受 0

**文件:** `tests/unit/quality/test_code_quality.py:40-46`

**影响:** 误导性文档；任何 ruff lint 违规都会导致测试失败。

---

### P2-02: `DocumentVersion` 无 `validate()` 方法，版本号可为负数

**文件:** `src/domain/entities/document.py:31-36`

---

### P2-03: `DomainEvent` 是 `frozen=True` 但子类用 `object.__setattr__` 绕过不可变性

**文件:** `src/domain/events/plan_events.py`

**影响:** 不可变契约通过约定而非类型系统强制执行。

---

### P2-04: `from_dict()` 对缺失字段抛出原始 `KeyError` 而非 `ValueError`

**文件:** `src/domain/events/base.py:52-61`

---

### P2-05: `strategic_plan.validate()` 中 `created_at` 的 None 检查是死代码

**文件:** `src/domain/entities/strategic_plan.py:64`

---

## 🟢 P3 低优先级/代码气味

| # | 问题 | 位置 |
|---|------|------|
| **P3-01** | `Document.bump_version()` 无版本号上限保护 | `src/domain/entities/document.py:101-117` |
| **P3-02** | 测试目录命名应为 `tests/architecture/` 而非 `tests/unit/architecture/` | 项目结构 |
| **P3-03** | `tests/deployment/config.py` 模块级别执行 `subprocess.run()` 影响非 WSL2 环境 | `tests/deployment/config.py` |
| **P3-04** | 实体工厂辅助函数 `_make_*` 使用 `dict` 类型注解而非 `dict[str, Any]` | 所有测试文件 |

---

## ✅ Acceptance Auditor 验收结果

| AC | 状态 | 验证详情 |
|----|------|----------|
| **AC-1** | ⚠️ **部分通过** | 目录结构正确，依赖方向验证使用 `import-linter` 正确。但 `.importlinter` 禁止列表不完整（P0-05）。 |
| **AC-2** | ✅ **通过** | 5 个核心实体全部创建，各有 `validate()` 方法，仅使用 Python 标准库。 |
| **AC-3** | ⚠️ **部分通过** | 领域事件基类 + 5 个核心事件 + `EventPublisher` 接口已定义。仓储接口完整。但架构测试有语法错误盲点（P0-04）。 |

---

## 📋 修复优先级排序

| 优先级 | 编号 | 问题 | 状态 |
|--------|------|------|------|
| **P0** | P0-01 | `DomainEvent.from_dict()` 序列化崩溃 | ❌ 待修复 |
| **P0** | P0-02 | `advance_phase()` 允许跳阶段 | ❌ 待修复 |
| **P0** | P0-03 | `advance_phase()` 不检查 status 守卫 | ❌ 待修复 |
| **P0** | P0-04 | 架构测试语法错误盲点 | ❌ 待修复 |
| **P0** | P0-05 | `.importlinter` 禁止列表不完整 | ❌ 待修复 |
| **P1** | P1-01~P1-08 | 8 个高优先级问题 | ❌ 待修复 |
| **P2** | P2-01~P2-05 | 5 个中优先级问题 | ❌ 待修复 |
| **P3** | P3-01~P3-04 | 4 个低优先级问题 | ❌ 待修复 |

---

## 📝 审查结论

**Story 1.1 未通过 Code Review。** 5 个 P0 阻断性问题必须在合并前修复。

**建议行动:**
1. 优先修复 P0-01 ~ P0-05
2. 运行 `pytest` 确认修复后所有测试通过
3. 重新运行 `code-review` 进行二次审查
4. 二次审查通过后再合并到 main 分支

---

**审查工具:** BMad Code Review (bmad-code-review skill)
**审查方法:** Parallel Adversarial Review (Blind Hunter + Edge Case Hunter + Acceptance Auditor)
**审查日期:** 2026-04-12
