# Story 1.2: 领域事件定义

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 领域工程师,
**I want** 定义核心领域事件（DocumentProcessed, ToolExecuted, AgentDecided, CheckpointReached, CorrectionApproved, StrategicDeviationWarning, HeartbeatTriggered, IsolationLevelSwitched, CheckpointRecovered, RoutingDecided）,
**So that** 系统支持事件驱动架构和事件溯源。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）的第二个故事，紧依赖 Story 1.1（六边形架构骨架）。通过定义统一的领域事件体系，为后续的事件总线（Story 1.3）、自主调用循环（Story 1.14a/b/c）和事件驱动架构奠定基础。

领域事件是系统的"引擎血液"，所有核心业务状态变更均通过事件发布来驱动下游处理（实体抽取、图谱构建、Agent 决策、审计日志等）。正确的事件定义是事件溯源、Checkpoint 恢复、战略偏差预警等关键能力的前提。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 2: 架构基础与事件驱动

**FR 追溯:**
- FR-AR-02: 发布领域事件至事件总线，支持事件重放与失败重试 [Source: epics_v1.0.md#FR-AR-02]

**NFR 追溯:**
- NFR-REL-04: Checkpoint 快照持久化 100% 持久化，故障恢复成功率≥99% [Source: epics_v1.0.md#NFR-REL-04]

---

## ✅ Acceptance Criteria 验收标准

### AC-1: DomainEvent 基类定义正确

**Given** 领域层六边形架构骨架已创建（Story 1.1）
**When** 定义统一的 DomainEvent 基类
**Then** 基类包含标准字段：event_id (UUID)、event_type (str)、timestamp (datetime)、payload (dict)、source (str)、schema_version (str)、aggregate_id (UUID)、aggregate_type (str)、version (int)
**And** 基类使用 Python 标准库类型（dataclasses 模块），不依赖 Pydantic 或任何第三方库
**And** 基类提供序列化/反序列化方法（to_dict / from_dict）

**验证标准/Validation Criteria:**
- [ ] DomainEvent 基类位于 `src/domain/events/base.py`
- [ ] 仅使用 Python 标准库（dataclasses、uuid、datetime）
- [ ] 包含所有 9 个标准字段
- [ ] to_dict() 方法返回可 JSON 序列化的 dict
- [ ] from_dict() 类方法可从 dict 重建事件
- [ ] 单元测试覆盖所有字段和方法

### AC-2: 10 种核心领域事件定义完成

**Given** DomainEvent 基类已定义
**When** 定义 10 种核心领域事件子类
**Then** 每种事件包含特定的 payload 结构
**And** 所有事件正确继承 DomainEvent 基类
**And** 事件命名符合规范（`[Aggregate][EventName]` 格式）

**10 种核心领域事件清单：**

| 事件名称 | 携带内容 | 触发下游 |
|---------|---------|---------|
| **DocumentProcessed** | document_id (UUID)、解析结果 (dict)、嵌入向量 (list)、版本 (int) | 实体抽取、图谱构建、索引构建 |
| **ToolExecuted** | tool_id (str)、执行结果 (dict)、成本审计 (dict)、耗时_ms (int) | 成本聚合、技能演进、Agent 决策 |
| **AgentDecided** | agent_id (str)、决策结果 (dict)、置信度 (float)、辩论轮次 (int) | SYS Agent 仲裁、公共黑板更新、审计日志 |
| **CheckpointReached** | checkpoint_id (str)、阶段标识 (str)、完成状态 (str)、用户反馈请求 (bool) | 用户交互、状态持久化 |
| **CorrectionApproved** | correction_id (str)、修正类型 (str)、前后值 (dict)、审批链 (list) | 自动固化、版本注册、演进日志 |
| **StrategicDeviationWarning** | warning_id (str)、偏差类型 (str)、等级 (str)、实际值 (float)、阈值 (float) | Agent 响应、偏差分析 |
| **HeartbeatTriggered** | heartbeat_id (str)、唤醒原因 (str)、待办事项 (list) | 周期性任务检查、偏差预警、成本预算校验 |
| **IsolationLevelSwitched** | agent_id (str)、原等级 (str)、目标等级 (str)、触发原因 (str) | 公共黑板权限更新、协作状态同步 |
| **CheckpointRecovered** | checkpoint_id (str)、恢复模式 (str)、修改内容 (dict)、分支标识 (str) | 战略档案库版本更新、分支管理 |
| **RoutingDecided** | task_id (str)、评分 (dict)、选定模型 (str)、成本 (float)、延迟_ms (int) | 路由决策日志存储、成本监控 |

**验证标准/Validation Criteria:**
- [ ] 所有 10 个事件类位于 `src/domain/events/`
- [ ] 每个事件类正确继承 DomainEvent 基类
- [ ] 每个事件类的 payload 包含上表所列字段
- [ ] 事件命名符合 `[Aggregate][EventName]` 规范
- [ ] 每个事件类有对应的单元测试

### AC-3: 领域事件与传输 DTO 分离

**Given** 领域层事件已定义
**When** 应用层/基础设施层需要序列化/反序列化事件
**Then** 通过 Pydantic V2 Schema 定义传输 DTO（位于应用层）
**And** 通过 TypeAdapter 做领域事件↔DTO 的无样板转换
**And** 领域层不导入 Pydantic

**验证标准/Validation Criteria:**
- [ ] Pydantic DTO 定义位于 `src/application/dto/events/`
- [ ] TypeAdapter 转换函数位于 `src/application/dto/event_adapter.py`
- [ ] 领域层不包含任何 Pydantic 导入
- [ ] 领域层零依赖测试通过（import-linter 验证）
- [ ] 领域事件↔DTO 双向转换测试通过

### AC-4: 事件发布器接口定义完成

**Given** 领域事件已定义
**When** 领域聚合根状态变更需要发布事件
**Then** 领域层定义事件发布器接口（EventPublisher Protocol）
**And** 基础设施层实现事件发布器（Redis Pub/Sub + RabbitMQ）
**And** 事件发布器接口使用 Python Protocol 定义（标准库 typing）

**验证标准/Validation Criteria:**
- [ ] EventPublisher Protocol 定义位于 `src/domain/events/publisher.py`
- [ ] Protocol 包含 publish(event: DomainEvent) -> None 方法
- [ ] 基础设施层实现位于 `src/infrastructure/events/publisher.py`
- [ ] 领域层不直接依赖 Redis/RabbitMQ
- [ ] 依赖注入测试通过

### AC-5: 事件 Schema 验证通过

**Given** 所有领域事件已定义
**When** 运行事件 Schema 验证
**Then** 所有事件可正确序列化为 dict
**And** 反序列化后的事件与原始事件字段值一致
**And** 事件 schema_version 字段正确标识版本

**验证标准/Validation Criteria:**
- [ ] 所有事件的 to_dict() 返回有效 dict
- [ ] 所有事件的 from_dict() 可正确重建事件
- [ ] 序列化/反序列化往返一致性测试通过
- [ ] schema_version 默认为 "1.0.0"
- [ ] Ruff 检查通过（严重错误=0）
- [ ] MyPy 类型检查通过
- [ ] 安全扫描通过（bandit）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] 使用 Python 标准库类型定义（`dataclasses` 模块），不依赖 Pydantic（领域层零依赖约束 FR-AR-01）
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `DocumentProcessed`, `ToolExecuted`, `AgentDecided`）
- [ ] 事件包含标准字段：event_id (UUID), occurred_on (datetime), aggregate_id, event_type, payload
- [ ] schema_version 默认为 "1.0.0"
- [ ] Pydantic DTO 定义位于 `src/application/dto/events/`
- [ ] TypeAdapter 转换函数位于 `src/application/dto/event_adapter.py`

#### 数据模型 (Data Models)
- [ ] DomainEvent 使用 dataclass 定义
- [ ] 10 种事件子类分别定义特定的 payload 结构
- [ ] EventPublisher Protocol 使用 typing.Protocol 定义

---

## 📋 Tasks / Subtasks

### Task 0: SDD 规范定义与事件 Schema 设计

> **前置条件：** Story 1.1（六边形架构骨架）已完成并通过 review

**描述：** 设计领域事件体系 Schema，定义 DomainEvent 基类、10 种事件子类、传输 DTO 和转换适配器

**验收：**
- [ ] DomainEvent 基类 Schema 设计完成
- [ ] 10 种事件子类 Schema 设计完成
- [ ] Pydantic DTO Schema 设计完成
- [ ] TypeAdapter 转换方案设计
- [ ] 所有 Schema 通过人工评审

**子任务：**
- [ ] 分析 project-context.md 中 12 种领域事件速查表
- [ ] 分析 architecture.md 第 10 章事件驱动架构设计
- [ ] 设计 DomainEvent 基类标准字段
- [ ] 设计 10 种事件子类的 payload 结构
- [ ] 设计 Pydantic V2 DTO（位于应用层）
- [ ] 设计 TypeAdapter 无样板转换方案
- [ ] 更新本 Story 的 SDD 检查清单

### Task 1: TDD — DomainEvent 基类实现

**AC 追溯:** #AC-1, #AC-3, #AC-5

**描述：** 使用 TDD 红→绿→重构循环实现 DomainEvent 基类

**TDD 红阶段：**
- [ ] 编写 `tests/unit/domain/events/test_events_base.py`
- [ ] 测试 DomainEvent 实例化（所有 9 个标准字段）
- [ ] 测试 to_dict() 序列化
- [ ] 测试 from_dict() 反序列化
- [ ] 测试序列化往返一致性
- [ ] 测试 event_id 自动生成
- [ ] 测试 occurred_on 自动设置

**TDD 绿阶段：**
- [ ] 创建 `src/domain/events/base.py`
- [ ] 使用 dataclass 定义 DomainEvent
- [ ] 实现 to_dict() 方法
- [ ] 实现 from_dict() 类方法
- [ ] 所有测试通过

**TDD 重构阶段：**
- [ ] 提取公共逻辑（如有）
- [ ] 优化类型注解
- [ ] 确保 Ruff/MyPy 通过
- [ ] 保持所有测试通过

**验证：**
- [ ] 单元测试覆盖率≥90%
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过

### Task 2: TDD — 10 种领域事件子类实现

**AC 追溯:** #AC-2, #AC-5

**描述：** 使用 TDD 红→绿→重构循环实现 10 种领域事件子类

**TDD 红阶段：**
- [ ] 编写 `tests/unit/domain/events/test_domain_events.py`
- [ ] 为每种事件编写实例化测试
- [ ] 为每种事件编写 payload 验证测试
- [ ] 为每种事件编写序列化/反序列化测试

**TDD 绿阶段：**
- [ ] 创建 `src/domain/events/domain_events.py`（或分文件组织）
- [ ] 实现 DocumentProcessed 事件
- [ ] 实现 ToolExecuted 事件
- [ ] 实现 AgentDecided 事件
- [ ] 实现 CheckpointReached 事件
- [ ] 实现 CorrectionApproved 事件
- [ ] 实现 StrategicDeviationWarning 事件
- [ ] 实现 HeartbeatTriggered 事件
- [ ] 实现 IsolationLevelSwitched 事件
- [ ] 实现 CheckpointRecovered 事件
- [ ] 实现 RoutingDecided 事件
- [ ] 所有测试通过

**TDD 重构阶段：**
- [ ] 提取公共 payload 验证逻辑
- [ ] 优化类型注解
- [ ] 确保代码组织清晰
- [ ] 保持所有测试通过

**验证：**
- [ ] 10 种事件全部实现
- [ ] 每种事件的 payload 包含 epics 和 architecture 中定义的字段
- [ ] 单元测试覆盖率≥90%

### Task 3: TDD — Pydantic DTO 与 TypeAdapter 转换

**AC 追溯:** #AC-3

**描述：** 实现应用层 Pydantic DTO 和领域事件↔DTO 双向转换

**TDD 红阶段：**
- [ ] 编写 `tests/unit/application/dto/events/test_event_dtos.py`
- [ ] 测试 Pydantic DTO 实例化
- [ ] 测试 DTO 验证规则
- [ ] 编写 `tests/unit/application/dto/test_event_adapter.py`
- [ ] 测试领域事件→DTO 转换
- [ ] 测试 DTO→领域事件转换
- [ ] 测试双向往返一致性

**TDD 绿阶段：**
- [ ] 创建 `src/application/dto/events/event_dtos.py`
- [ ] 定义 10 种 Pydantic V2 DTO
- [ ] 创建 `src/application/dto/event_adapter.py`
- [ ] 实现 TypeAdapter 转换函数
- [ ] 所有测试通过

**TDD 重构阶段：**
- [ ] 提取公共 DTO 基类
- [ ] 优化转换逻辑
- [ ] 确保 Ruff/MyPy 通过

**验证：**
- [ ] DTO 验证规则正确（Pydantic V2）
- [ ] 双向转换测试通过
- [ ] 领域层不包含 Pydantic 导入

### Task 4: TDD — EventPublisher Protocol 接口定义

**AC 追溯:** #AC-4

**描述：** 定义领域层事件发布器接口（Protocol）

**TDD 红阶段：**
- [ ] 编写 `tests/unit/domain/events/test_event_publisher.py`
- [ ] 测试 Protocol 定义正确性
- [ ] 测试实现类符合 Protocol
- [ ] 测试依赖注入模式

**TDD 绿阶段：**
- [ ] 创建 `src/domain/events/publisher.py`
- [ ] 定义 EventPublisher Protocol
- [ ] 包含 publish(event: DomainEvent) -> None 方法
- [ ] 所有测试通过

**TDD 重构阶段：**
- [ ] 优化 Protocol 定义
- [ ] 确保 Ruff/MyPy 通过

**验证：**
- [ ] Protocol 定义符合 Python typing.Protocol 规范
- [ ] 领域层零依赖测试通过
- [ ] import-linter 验证通过

### Task 5: 架构约束验证与质量门禁

**AC 追溯:** #AC-1, #AC-3, #AC-4, #AC-5

**描述：** 运行完整的质量门禁检查，确保所有架构约束通过

**子任务：**
- [ ] 运行领域层零依赖测试（import-linter）
- [ ] 验证依赖方向正确
- [ ] 运行 Ruff 检查（严重错误=0）
- [ ] 运行 MyPy 类型检查
- [ ] 运行 Bandit 安全扫描
- [ ] 运行 pytest 覆盖率检查（≥90%）
- [ ] 验证所有 Acceptance Criteria 通过

**验证：**
- [ ] import-linter 通过
- [ ] Ruff 通过（0 错误）
- [ ] MyPy 通过
- [ ] Bandit 通过
- [ ] 覆盖率≥90%
- [ ] 所有 AC 标记为通过

---

## 📝 Dev Notes

### 架构约束与规则

**关键架构规则（必须遵守）：**

1. **领域层零依赖（FR-AR-01）**：领域层仅依赖 Python 标准库与领域模型，**绝不导入任何外部框架**（包括 Pydantic）。[Source: project-context.md#3.1 领域驱动六边形架构]

2. **领域事件格式标准化**：所有事件必须包含 9 个标准字段（event_id, event_type, timestamp, payload, source, schema_version, aggregate_id, aggregate_type, version）。[Source: project-context.md#3.3 事件驱动架构]

3. **Pydantic 分层规则**：Pydantic 仅用于应用层/基础设施层的边界校验、序列化与反序列化。领域事件与传输 DTO 必须分离。[Source: project-context.md#12 领域事件速查]

4. **事件命名规范**：使用 `[Aggregate][EventName]` 格式，如 `DocumentProcessed`。[Source: architecture.md#10 事件驱动架构设计]

### 项目结构约定

```
src/
├── domain/
│   └── events/
│       ├── __init__.py
│       ├── base.py                    # DomainEvent 基类（dataclass）
│       ├── domain_events.py           # 10 种事件子类
│       └── publisher.py               # EventPublisher Protocol
├── application/
│   └── dto/
│       ├── events/
│       │   └── event_dtos.py          # Pydantic V2 DTO 定义
│       └── event_adapter.py           # TypeAdapter 转换函数
└── infrastructure/ (本 Story 不实现，仅定义接口)

tests/
├── unit/
│   ├── domain/
│   │   └── events/
│   │       ├── test_events_base.py    # DomainEvent 基类测试
│   │       ├── test_domain_events.py  # 10 种事件子类测试
│   │       └── test_event_publisher.py # EventPublisher Protocol 测试
│   └── application/
│       └── dto/
│           ├── events/
│           │   └── test_event_dtos.py # Pydantic DTO 测试
│           └── test_event_adapter.py  # TypeAdapter 转换测试
```

### 测试标准

- **测试框架：** pytest + pytest-cov
- **覆盖率要求：** 领域层≥90%，事件模块≥90%
- **测试标记：** 使用 `@pytest.mark.unit` 标记单元测试
- **Fixture：** 使用 conftest.py 提供公共 Fixture
- **TDD 循环：** 严格遵循 红→绿→重构 循环

### 关键技术细节

**DomainEvent 基类设计要点：**
- 使用 `@dataclass` 装饰器
- `event_id` 使用 `uuid4()` 自动生成
- `occurred_on` 使用 `datetime.now(timezone.utc)` 自动设置
- `to_dict()` 使用 `dataclasses.asdict()` 或自定义序列化
- `from_dict()` 使用类方法 `@classmethod` 实现

**10 种事件 payload 关键字段：**
- DocumentProcessed: document_id, parsed_content, embeddings, version
- ToolExecuted: tool_id, result, cost_audit, elapsed_ms
- AgentDecided: agent_id, decision, confidence, debate_rounds
- CheckpointReached: checkpoint_id, stage, status, feedback_requested
- CorrectionApproved: correction_id, type, before_after, approval_chain
- StrategicDeviationWarning: warning_id, deviation_type, level, actual_value, threshold
- HeartbeatTriggered: heartbeat_id, reason, todos
- IsolationLevelSwitched: agent_id, from_level, to_level, reason
- CheckpointRecovered: checkpoint_id, recovery_mode, changes, branch
- RoutingDecided: task_id, scores, selected_model, cost, latency_ms

**Pydantic DTO 设计要点：**
- 使用 Pydantic V2 `BaseModel`
- 字段验证规则（类型、必填、默认值）
- 模型配置使用 `model_config = ConfigDict(...)`
- 与领域事件的转换通过 `event_adapter.py` 中的函数完成

### References

- [Source: project-context.md#3.3 事件驱动架构] - 事件格式标准化、双通道事件总线
- [Source: project-context.md#12 领域事件速查] - 10 种领域事件及下游触发
- [Source: project-context.md#3.1 领域驱动六边形架构] - 领域层零依赖原则
- [Source: architecture.md#10 事件驱动架构设计] - 事件定义、事件总线设计
- [Source: epics_v1.0.md#Story 1.2] - Epic 分解中的故事描述
- [Source: epics_v1.0.md#FR-AR-02] - 功能需求追溯
- [Source: prd.md#架构约束] - 产品需求文档中的架构约束

---

## 🤖 Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

---

## ✅ Checklist

- [x] SDD 规范定义完成（领域事件 Schema、DTO Schema、TypeAdapter 方案）
- [ ] TDD 红→绿→重构循环完成（所有 Task）
- [ ] SDD 规范验证通过（Schema 验证、类型检查）
- [ ] 覆盖率达标（领域层≥90%）
- [ ] 代码质量检查通过（Ruff、MyPy、Bandit）
- [ ] 架构约束验证通过（领域层零依赖、依赖方向正确）
- [ ] 文档更新（代码注释、本 Story 的 Dev Agent Record）
