# Story 1.3: Event Bus Implementation

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。
>
> **📋 审查决议：** 本 Story 已通过 Party Mode 多代理审查 + 架构师修正（v1.2），按优先级分级执行。
> 详见 [`1-3-event-bus-review-decision.md`](./1-3-event-bus-review-decision.md)。
>
> **🔧 技术约束（v2.0 修订）：**
> 1. **可靠传输仅 Outbox → RabbitMQ**：业务事件的可靠传输仅通过 Outbox → RabbitMQ 完成；Redis Pub/Sub 仅用于实时通知，不参与事务一致性与可靠投递承诺
> 2. **OutboxRepository 以 OutboxEntity 为读写单位**：领域层仓储接口直接读写 `OutboxEntity` 实例，不暴露底层表结构
> 3. **RabbitMQ / Outbox Poller 统一 async 路径**：所有 RabbitMQ 操作与 Outbox Poller 统一使用 `async/await`
> 4. **领域层事件接口与基础设施层异步发布接口分离**：领域层定义同步 `EventPublisher.publish(event)` 接口，基础设施层实现 `AsyncEventPublisher.async_publish(event)` 异步接口

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现双通道事件总线(Redis Pub/Sub + RabbitMQ + 事务发件箱),
**So that** 系统各模块可以通过标准化事件进行异步通信，支持实时事件通知与持久化事件传输。

### 业务价值

本 Story 是 Epic 1(企业级架构基础与合规)的第三个故事，在 Story 1.1(六边形架构骨架)和 Story 1.2(领域事件定义)基础上实现完整的事件总线基础设施。通过实现双通道事件总线，为后续的事件驱动架构、事件溯源、异步业务流提供可靠的消息传输机制。

事件总线是企业战略规划系统中各模块解耦的核心基础设施，支撑以下关键场景:
- **实时事件通知** — 基于 Redis Pub/Sub 实现低延迟领域事件路由与分发（允许丢失的实时通知）
- **持久化事件传输** — 基于 RabbitMQ + 事务发件箱(Outbox)实现可靠事件传输（业务状态型事件）
- **审计事件归档** — 基于 RabbitMQ + WORM 归档实现 7 年合规存储（SOX/ISO27001 要求）
- **事件处理幂等性** — 基于 event_id 的 Redis 缓存去重（TTL 7 天）
- **事件重放与失败重试** — 指数退避重试 + 死信队列（事件处理成功率 ≥99%，延迟 P95 <5s）

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 2: 架构基础与事件驱动

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Redis Pub/Sub 实时通知通道实现

> **📌 约束：Redis 仅用于实时通知，不参与事务一致性与可靠投递承诺。**

**Given** Story 1.1 六边形架构骨架和 Story 1.2 领域事件定义已实现
**When** 实现基于 Redis Pub/Sub 的实时事件通知通道
**Then** 支持事件发布至 Redis 频道供低延迟消费者订阅
**And** 明确标注 Redis 通道为"尽力而为"（允许丢失）

**验证标准/Validation Criteria:**
- [ ] RedisEventPublisher 实现(支持 `publish(event: DomainEvent, channel: str) -> None`)
- [ ] RedisEventSubscriber 实现(支持 `subscribe(channel: str, handler: Callable)`)
- [ ] Redis 频道命名规范(`sisys.events.realtime.{event_type}`，与 RabbitMQ 路由键区分)
- [ ] 事件序列化后发布(JSON 格式，使用 `dataclasses.asdict()` + `json.dumps()`)
- [ ] Redis 连接池配置(支持连接复用，最大连接数可配置)
- [ ] 文档/注释明确标注：Redis 不参与事务一致性、不保证可靠投递
- [ ] Redis 发布/订阅端到端测试通过

### AC-2: RabbitMQ 可靠事件通道实现（async 路径）

> **📌 约束：业务事件的可靠传输仅通过 Outbox → RabbitMQ 完成。统一 async 路径。**

**Given** Redis Pub/Sub 实时通知通道已实现
**When** 实现基于 RabbitMQ 的可靠事件传输通道（异步）
**Then** 支持异步事件发布至 RabbitMQ 交换机
**And** 支持异步消费者按路由键消费事件

**验证标准/Validation Criteria:**
- [ ] `AsyncRabbitMQPublisher` 实现(支持 `async def async_publish(event: DomainEvent, routing_key: str) -> None`)
- [ ] `AsyncRabbitMQConsumer` 实现(支持 `async def async_consume(queue_name: str, handler: Callable)`)
- [ ] RabbitMQ 交换机配置(topic 类型，支持模式匹配路由)
- [ ] RabbitMQ 路由键命名规范(`sisys.events.reliable.{event_type}`，与 Redis 频道区分)
- [ ] 事件消息持久化(durable=True, delivery_mode=2)
- [ ] **所有 RabbitMQ 操作统一使用 `async/await`**
- [ ] RabbitMQ 异步发布/消费端到端测试通过（使用 `pytest-asyncio`）

### AC-3: 事务发件箱模式(Outbox Pattern)实现

> **📌 约束：Outbox 是唯一真源，以 OutboxEntity 为读写单位。Poller 使用 async 路径。**
> **📌 约束：可靠传输仅 Outbox → RabbitMQ，Redis 不参与。**

**Given** RabbitMQ 可靠事件通道已实现
**When** 实现事务发件箱模式保证事件与业务操作原子性
**Then** 事件与业务操作同事务提交至 PostgreSQL `event_outbox` 表
**And** 后台异步 Poller 轮询 OutboxEntity 并发布至 RabbitMQ

**验证标准/Validation Criteria:**
- [ ] OutboxEntity 定义(id, event_id, event_type, payload, status, created_at, published_at, retry_count, error_message)
- [ ] OutboxRepository 接口定义(领域层抽象) **以 OutboxEntity 为读写单位**
  - [ ] `save(entity: OutboxEntity) -> None`(与业务操作同事务，写入 OutboxEntity)
  - [ ] `get_unpublished(limit: int) -> List[OutboxEntity]`(读取未发布的 OutboxEntity)
  - [ ] `mark_published(entity: OutboxEntity) -> None`(标记 OutboxEntity 已发布)
  - [ ] `mark_failed(entity: OutboxEntity, error: str) -> None`(标记 OutboxEntity 失败)
- [ ] InMemoryOutboxRepository 实现(MVP 阶段占位，使用内存列表存储 OutboxEntity)
- [ ] **AsyncOutboxPoller 实现(使用 `async/await` 异步轮询 OutboxEntity，默认 1 秒间隔)**
- [ ] 事务原子性测试通过(业务操作与 OutboxEntity 同事务提交)
- [ ] OutboxEntity 状态变化测试(事件生命周期由 OutboxEntity 状态驱动，非 RabbitMQ 状态)

### AC-4: 事件处理幂等性与重试机制（🟡 Should-Have）

> **AC-4 拆分说明：**
> - **AC-4.1 幂等性检查**（🔴 Must）: `IdempotencyChecker` 基于 Redis `SET NX`，TTL 7 天
> - **AC-4.2 重试机制**（🔴 Must）: `RetryPolicy` 完整实现（指数退避 + jitter + 最大延迟上限）+ `DeadLetterQueue` 基础实现

**Given** 双通道事件总线已实现
**When** 实现事件处理幂等性保证与失败重试机制
**Then** 基于 event_id 的 Redis 缓存去重(TTL 7 天)
**And** 失败事件指数退避重试（含 jitter）+ 死信队列

**验证标准/Validation Criteria:**
- [ ] IdempotencyChecker 实现(基于 Redis `SET NX` 命令) **🔴 Must**
  - [ ] `is_processed(event_id: UUID) -> bool`(检查是否已处理)
  - [ ] `mark_processed(event_id: UUID, ttl: int = 7*24*3600) -> None`(标记已处理)
- [ ] RetryPolicy 实现(完整指数退避 + jitter) **🔴 Must**
  - [ ] `get_delay(retry_count: int) -> float`(计算重试延迟: `min(base * 2^retry_count, max) * jitter`)
  - [ ] `should_retry(retry_count: int, max_retries: int = 3) -> bool`(判断是否重试)
  - [ ] jitter 实现: `random.uniform(0.5, 1.5)` 防止惊群效应
- [ ] DeadLetterQueue 实现(死信队列，存储超过最大重试次数的事件) **🔴 Must**
  - [ ] `enqueue(event: DomainEvent, error: str) -> None`(入队失败事件)
  - [ ] `dequeue() -> Optional[Tuple[DomainEvent, str]]`(出队失败事件)
- [ ] 幂等性测试通过(重复发布相同 event_id 仅处理一次)
- [ ] 重试机制测试通过(指数退避延迟 + jitter + 超过最大次数入死信队列)

### AC-5: 事件处理监控与可观测性（🔵 Could-Have，本故事最后完成，部分组件拆分至后续故事）

> **📌 约束：领域层事件接口与基础设施层异步发布接口分离。**
> - 领域层定义同步 `EventPublisher.publish(event: DomainEvent) -> None` 接口
> - 基础设施层实现 `AsyncRabbitMQPublisher.async_publish(event: DomainEvent) -> None` 异步接口
> - 领域层不感知异步实现细节

> **Task 5 拆分归属表：**
> | 子任务 | 归属故事 | Story 1.3 范围 | 后续故事范围 |
> |--------|---------|--------------|------------|
> | **Task 5.1** | Story 1.3 ✅ | `EventMetrics` + `EventMetricsCollector` 基础计数器 | — |
> | **Task 5.2** | Story 1.3 ✅ | OpenTelemetry span 创建+属性，默认关闭导出 | — |
> | **Task 5.3** | Story 1.13 🔵 | — | Prometheus `/metrics` HTTP 端点 |
> | **Task 5.4** | Story 1.16 🔵 | — | OpenTelemetry OTLP 导出器配置 |
> | **Task 5.5** | Story 1.4 🔵 | — | Redis 缓存命中率、延迟指标扩展 |

**Given** 事件处理基础设施已实现
**When** 实现事件处理监控指标收集（简化版）
**Then** 事件处理成功率、平均延迟、重试次数、死信率纳入统一可观测性体系（基础版）

**验证标准/Validation Criteria:**
- [ ] EventMetrics 定义(事件处理指标) **✅ Story 1.3 范围**
  - [ ] `events_processed_total`(已处理事件总数)
  - [ ] `events_failed_total`(失败事件总数)
  - [ ] `events_retried_total`(重试事件总数)
  - [ ] `events_dlq_total`(死信队列事件总数)
  - [ ] `event_processing_duration_seconds`(事件处理延迟直方图)
- [ ] EventMetricsCollector 实现(指标收集器) **✅ Story 1.3 范围**
  - [ ] `record_processed(event_type: str, duration: float) -> None`(记录成功处理)
  - [ ] `record_failed(event_type: str, error: str) -> None`(记录失败)
  - [ ] `record_retried(event_type: str) -> None`(记录重试)
  - [ ] `record_dlq(event_type: str) -> None`(记录死信)
- [ ] OpenTelemetry Trace 基础版（span 创建+属性，默认 `EVENT_BUS_OTEL_TRACE_ENABLED=false`） **✅ Story 1.3 范围**
- [ ] ~~Prometheus /metrics 端点~~ **🔵 移至 Story 1.13**
- [ ] ~~OpenTelemetry OTLP 导出器配置~~ **🔵 移至 Story 1.16**

### AC-6: 架构约束验证测试就绪

**Given** 事件总线基础设施已实现
**When** 运行架构约束验证测试
**Then** 事件总线实现符合六边形架构依赖方向
**And** 领域层不依赖任何事件总线实现细节
**And** Ruff 检查通过(严重错误=0)
**And** MyPy 类型检查通过(错误率<5%)

**验证标准/Validation Criteria:**
- [ ] 事件总线实现在基础设施层，不泄漏至领域层
- [ ] 领域层仅依赖 EventPublisher/EventListener 接口(Story 1.2 已定义)
- [ ] Redis/RabbitMQ 客户端导入仅在基础设施层
- [ ] 依赖方向测试通过(使用 `import-linter`)
- [ ] Ruff 检查通过(0 错误)
- [ ] MyPy 类型检查通过(0 问题)

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束:** 每个 Task 必须独立完成完整的 TDD 循环(红→绿→重构)，禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义(Task 0 — 必选前置)

> **执行顺序:** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 事件总线接口(已在 Story 1.2 定义)
- [x] EventPublisher 接口(`src/domain/events/publisher.py`)
  - 领域层定义同步接口: `publish(event: DomainEvent) -> None`
  - 领域层不感知异步实现细节
- [x] EventListener 接口(`src/domain/events/listener.py`)
- [x] EventStore 接口(`src/domain/events/store.py`)

#### 新增接口定义
- [ ] OutboxRepository 接口(`src/domain/repositories/outbox.py`) **以 OutboxEntity 为读写单位**
  - [ ] `save(entity: OutboxEntity) -> None`(与业务操作同事务，写入 OutboxEntity)
  - [ ] `get_unpublished(limit: int) -> List[OutboxEntity]`(读取未发布的 OutboxEntity)
  - [ ] `mark_published(entity: OutboxEntity) -> None`(标记 OutboxEntity 已发布)
  - [ ] `mark_failed(entity: OutboxEntity, error: str) -> None`(标记 OutboxEntity 失败)

#### 数据模型
- [ ] OutboxEntity 定义(`src/domain/entities/outbox.py`)
  - [ ] id: int, event_id: UUID, event_type: str, payload: dict
  - [ ] status: str('pending'|'published'|'failed'), created_at: datetime
  - [ ] published_at: Optional[datetime], retry_count: int, error_message: Optional[str]

#### 配置模型
- [ ] RedisConfig 定义(`src/infrastructure/config/redis.py`)
  - [ ] host: str, port: int, db: int, password: Optional[str]
  - [ ] max_connections: int, socket_timeout: float
- [ ] RabbitMQConfig 定义(`src/infrastructure/config/rabbitmq.py`)
  - [ ] host: str, port: int, virtual_host: str, username: str, password: str
  - [ ] exchange_name: str, exchange_type: str='topic'
  - [ ] prefetch_count: int, heartbeat: int

#### 接口分离设计
- [ ] 领域层同步接口: `EventPublisher.publish(event: DomainEvent) -> None`
- [ ] 基础设施层异步实现: `AsyncRabbitMQPublisher.async_publish(event: DomainEvent) -> Coroutine`
- [ ] 领域层不导入任何异步相关类型

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件:`tests/acceptance/test_story_1.3.feature`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖(Happy Path + Edge Cases:Redis 连接失败、RabbitMQ 连接失败、事务回滚、重复 event_id、超过最大重试次数、OutboxEntity 状态转换异常)

**Task 0 完成标志:**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败(🔴 红阶段验证)
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束(适用于每个 Task)

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序:**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码(保持测试通过) | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为:**
- ❌ 先写代码后写测试(违反 TDD 测试先行原则)
- ❌ 将测试编写集中到最后一个 Task(违反 TDD 小步快跑原则)
- ❌ 跳过红阶段验证(未确认测试失败就直接写实现)

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task | 优先级 |
|---------|------|----------|----------|-----------|--------|
| **TDD 单元测试** | Redis Pub/Sub | 验证 Redis 事件发布/订阅、连接池 | `test_redis_event_bus.py` | Task 1 | 🔴 Must |
| **TDD 单元测试** | RabbitMQ async | 验证 RabbitMQ 异步发布/消费、消息持久化 | `test_rabbitmq_event_bus.py` | Task 2 | 🔴 Must |
| **TDD 单元测试** | Outbox Pattern | 验证 OutboxEntity 读写、异步轮询发布、原子性 | `test_outbox_pattern.py` | Task 3 | 🔴 Must |
| **TDD 单元测试** | 幂等性与重试 | 验证 Redis 去重、固定延迟重试、死信队列 | `test_idempotency_retry.py` | Task 4 | 🟡 Should |
| **TDD 单元测试** | 事件监控 | 验证指标收集、OpenTelemetry span 创建 | `test_event_monitoring.py` | Task 5.1, 5.2 | 🔵 Could |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收(Outbox→RabbitMQ 可靠通道端到端) | `test_story_1.3.feature` | Task 0 | 🔴 Must |
| **SDD 架构验证** | 架构约束 | 事件总线依赖方向、接口分离验证 | `test_event_bus_architecture.py` | Task 6 | 🔴 Must |

**测试环境策略（审查决议补充）：**
- 单元测试使用 Mock（`unittest.mock` / `fakeredis ^2.20.0`），标记 `@pytest.mark.unit`
- 集成测试使用 Docker Compose（Redis + RabbitMQ 真实实例），标记 `@pytest.mark.integration`
- **RabbitMQ 组件与 Outbox Poller 测试必须使用 `pytest-asyncio`**（统一 async 路径）
- 集成测试默认跳过，CI/CD 中显式启用（`pytest -m integration`）

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划:

- [ ] **整体覆盖率 ≥80%**(`pytest --cov=src --cov-fail-under=80`) - **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**(`pytest --cov=src/domain`) - **P1 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**(`pytest --cov=src/application`) - **P1 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**(`pytest --cov=src/infrastructure`) - **P1 阻断门禁**
- [ ] **关键路径覆盖率 100%**(所有分支覆盖)

#### 代码质量门禁
- [ ] **Ruff 检查通过**(`ruff check src/`)
- [ ] **MyPy 类型检查通过**(`mypy src/`)
- [ ] **无 P0/P1 级别问题**(代码审查)
- [ ] **预提交 Hooks 通过**(`pre-commit run --all-files`)

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的:** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。
> **优先级说明:** 🔴 Must-Have | 🟡 Should-Have | 🔵 Could-Have

| AC | 验收标准描述 | 优先级 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|--------|-----------|-------------|----------|
| AC-1 | Redis Pub/Sub 实时通知通道实现 | 🔴 Must | Task 0, Task 1 | SDD 规范定义 + RedisEventPublisher/Subscriber | `test_story_1.3.feature`, `test_redis_event_bus.py` |
| AC-2 | RabbitMQ 可靠事件通道(async 路径) | 🔴 Must | Task 2 | AsyncRabbitMQPublisher/Consumer (async/await) | `test_rabbitmq_event_bus.py` |
| AC-3 | 事务发件箱模式(OutboxEntity 为读写单位) | 🔴 Must | Task 3 | OutboxRepository(OutboxEntity) + AsyncOutboxPoller | `test_outbox_pattern.py` |
| AC-4.1 | 事件处理幂等性检查 | 🔴 Must | Task 4 | IdempotencyChecker (Redis SET NX) | `test_idempotency_retry.py` |
| AC-4.2 | 事件处理重试机制(指数退避完整) | 🔴 Must | Task 4 | RetryPolicy (指数退避+jitter) + DeadLetterQueue | `test_idempotency_retry.py` |
| AC-5 | 事件处理监控与可观测性 | 🔵 Could | Task 5.1, 5.2 | EventMetrics + Collector + Otel span 基础 | `test_event_monitoring.py` |
| AC-6 | 架构约束验证测试就绪(含接口分离验证) | 🔴 Must | Task 6 | 事件总线依赖方向验证、领域层/基础设施层接口分离验证 | `test_event_bus_architecture.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则:** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义(必选前置)

**关联 AC:** AC-1

> **目的:** 在进入代码实现前，明确事件总线接口、数据模型、配置模型、验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask: 定义 OutboxRepository 接口(`save`, `get_unpublished`, `mark_published`, `mark_failed`)
- [ ] Subtask: 定义 OutboxEntity 数据模型(id, event_id, event_type, payload, status, created_at, published_at, retry_count)
- [ ] Subtask: 定义 RedisConfig 配置模型(host, port, db, password, max_connections, socket_timeout)
- [ ] Subtask: 定义 RabbitMQConfig 配置模型(host, port, virtual_host, exchange_name, prefetch_count)
- [ ] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.3.feature`
- [ ] Subtask: 运行验收测试，确认失败(🔴 红阶段验证)

**完成标准/Definition of Done:**
- [ ] 接口与数据模型全部定义完毕
- [ ] 配置模型定义完毕
- [ ] 验收测试运行失败(预期行为，红阶段确认)

---

### Task 1: Redis Pub/Sub 实时事件通道

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A:RedisConfig 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_redis_event_bus.py`(验证配置创建、默认值、校验) |
| 🟢 绿 | 实现 `RedisConfig` dataclass(含默认值) |
| 🔄 重构 | 添加 `from_env()` 类方法(从环境变量加载) |

- [ ] Subtask: 创建 `src/infrastructure/config/redis.py`
- [ ] Subtask: 🔴 红 — 编写 `RedisConfig` 失败测试(验证默认值、校验)
- [ ] Subtask: 🟢 绿 — 实现 `RedisConfig` dataclass
- [ ] Subtask: 🔄 重构 — 添加 `from_env()` 方法

#### TDD 循环 B:RedisEventPublisher 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_redis_event_bus.py`(验证事件发布、频道命名、序列化) |
| 🟢 绿 | 实现 `RedisEventPublisher`(基础设施层，使用 `redis-py` 客户端) |
| 🔄 重构 | 添加连接池、异常处理、日志记录 |

- [ ] Subtask: 🔴 红 — 编写 `RedisEventPublisher` 失败测试(验证 `publish()` 方法)
- [ ] Subtask: 🟢 绿 — 实现 `RedisEventPublisher`(实现 Story 1.2 定义的 `EventPublisher` 接口)
- [ ] Subtask: 🔄 重构 — 添加连接池管理、`publish()` 异常处理

#### TDD 循环 C:RedisEventSubscriber 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_redis_event_bus.py`(验证订阅、按频道接收、事件反序列化) |
| 🟢 绿 | 实现 `RedisEventSubscriber`(支持 `subscribe(channel, handler)`) |
| 🔄 重构 | 支持多频道订阅、优雅关闭、反序列化异常处理 |

- [ ] Subtask: 🔴 红 — 编写 `RedisEventSubscriber` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `RedisEventSubscriber`
- [ ] Subtask: 🔄 重构 — 添加多频道支持、优雅关闭逻辑

**完成标准/Definition of Done:**
- [ ] RedisConfig 配置模型实现
- [ ] RedisEventPublisher 事件发布器实现
- [ ] RedisEventSubscriber 事件订阅器实现
- [ ] 所有测试通过
- [ ] 覆盖率≥75%(基础设施层)

---

### Task 2: RabbitMQ 持久化事件通道

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A:RabbitMQConfig 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_rabbitmq_event_bus.py`(验证配置创建、默认值、校验) |
| 🟢 绿 | 实现 `RabbitMQConfig` dataclass(含默认值) |
| 🔄 重构 | 添加 `from_env()` 类方法 |

- [ ] Subtask: 创建 `src/infrastructure/config/rabbitmq.py`
- [ ] Subtask: 🔴 红 — 编写 `RabbitMQConfig` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `RabbitMQConfig` dataclass
- [ ] Subtask: 🔄 重构 — 添加 `from_env()` 方法

#### TDD 循环 B:AsyncRabbitMQPublisher 实现

> **⚠️ 重要:** `aio-pika ^9.3.0` 是异步客户端，统一 async 路径，测试使用 `pytest-asyncio`。
> **📌 接口分离：** 领域层定义同步 `EventPublisher.publish()` 接口，基础设施层实现 `AsyncRabbitMQPublisher.async_publish()` 异步接口。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_rabbitmq_event_bus.py`(验证异步事件发布、交换机声明、路由键、消息持久化) |
| 🟢 绿 | 实现 `AsyncRabbitMQPublisher`(基础设施层，使用 `aio-pika` 异步客户端) |
| 🔄 重构 | 添加连接管理、异常处理、日志记录 |

- [ ] Subtask: 创建 `src/infrastructure/config/rabbitmq.py`（如 Task 2-A 未创建）
- [ ] Subtask: 🔴 红 — 编写 `AsyncRabbitMQPublisher` 失败测试(验证 `async_publish()` 方法、消息持久化) **使用 `@pytest.mark.asyncio`**
- [ ] Subtask: 🟢 绿 — 实现 `AsyncRabbitMQPublisher`(基础设施层异步实现, `async def async_publish()`)
- [ ] Subtask: 🔄 重构 — 添加连接管理、交换机声明(topic 类型)、`async_publish()` 异常处理

**路由键规范（可靠通道）：**
- 格式: `sisys.events.reliable.{event_type}`
- 示例: `sisys.events.reliable.DocumentProcessed`, `sisys.events.reliable.AgentDecided`
- 交换机绑定: `sisys.events.reliable.#` (通配符匹配所有可靠事件)

#### TDD 循环 C:AsyncRabbitMQConsumer 实现

> **⚠️ 重要:** `aio-pika` 异步客户端，统一 async 路径，测试使用 `pytest-asyncio`。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_rabbitmq_event_bus.py`(验证队列声明、异步消费、消息确认、事件反序列化) |
| 🟢 绿 | 实现 `AsyncRabbitMQConsumer`(支持 `async async_consume(queue_name, handler)`) |
| 🔄 重构 | 支持 prefetch_count、手动 ACK/NACK、优雅关闭 |

- [ ] Subtask: 🔴 红 — 编写 `AsyncRabbitMQConsumer` 失败测试 **使用 `@pytest.mark.asyncio`**
- [ ] Subtask: 🟢 绿 — 实现 `AsyncRabbitMQConsumer`
- [ ] Subtask: 🔄 重构 — 添加 prefetch_count、手动 ACK/NACK、优雅关闭逻辑

**完成标准/Definition of Done:**
- [ ] RabbitMQConfig 配置模型实现
- [ ] AsyncRabbitMQPublisher 异步事件发布器实现
- [ ] AsyncRabbitMQConsumer 异步事件消费者实现
- [ ] 所有测试通过
- [ ] 覆盖率≥75%(基础设施层)

---

### Task 3: 事务发件箱模式(Outbox Pattern)

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A:OutboxEntity 与 OutboxRepository 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_outbox_pattern.py`(验证 OutboxEntity 创建、字段校验) |
| 🟢 绿 | 实现 `OutboxEntity` dataclass + `OutboxRepository` 抽象基类 |
| 🔄 重构 | 添加类型注解、docstring、`from_domain_event()` 类方法 |

- [ ] Subtask: 创建 `src/domain/entities/outbox.py`
- [ ] Subtask: 创建 `src/domain/repositories/outbox.py`
- [ ] Subtask: 🔴 红 — 编写 `OutboxEntity` 和 `OutboxRepository` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `OutboxEntity` + `OutboxRepository`(领域层定义)
- [ ] Subtask: 🔄 重构 — 添加类型注解、`from_domain_event()` 方法

#### TDD 循环 B:InMemoryOutboxRepository 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_outbox_pattern.py`(验证 CRUD 操作、状态转换) |
| 🟢 绿 | 实现 `InMemoryOutboxRepository`(MVP 占位，使用内存列表) |
| 🔄 重构 | 添加线程安全锁、按状态过滤 |

- [ ] Subtask: 创建 `src/infrastructure/repositories/outbox.py`
- [ ] Subtask: 🔴 红 — 编写 `InMemoryOutboxRepository` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `InMemoryOutboxRepository`
- [ ] Subtask: 🔄 重构 — 添加线程安全、按状态过滤

#### TDD 循环 C:AsyncOutboxPoller 实现

> **⚠️ 重要:** Poller 使用 `async/await` 编写，与 RabbitMQ 异步客户端保持一致。
> **📌 约束：可靠传输仅 Outbox → RabbitMQ。**

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_outbox_pattern.py`(验证异步轮询发布 OutboxEntity、标记已发布、异常处理) |
| 🟢 绿 | 实现 `AsyncOutboxPoller`(异步协程轮询 OutboxEntity，默认 1 秒间隔，`async def poll_once()`) |
| 🔄 重构 | 支持可配置间隔、优雅关闭、失败重试、批量发布 |

- [ ] Subtask: 🔴 红 — 编写 `AsyncOutboxPoller` 失败测试 **使用 `@pytest.mark.asyncio`**
- [ ] Subtask: 🟢 绿 — 实现 `AsyncOutboxPoller`(异步协程轮询 OutboxEntity，调用 `AsyncRabbitMQPublisher.async_publish()`)
- [ ] Subtask: 🔄 重构 — 添加可配置轮询间隔、优雅关闭逻辑、批量发布优化

**设计约束：**
```
OutboxEntity (PostgreSQL event_outbox) ← 唯一真源，以 OutboxEntity 为读写单位
    │
    ▼ async poll_once()
AsyncOutboxPoller ← 异步协程轮询，每次获取未发布的 OutboxEntity 批量处理
    │
    ├─→ 成功 → mark_published(entity) → OutboxEntity 状态更新
    │
    └─→ 失败 → mark_failed(entity, error) → 记录错误，后续重试
```

**完成标准/Definition of Done:**
- [ ] OutboxEntity 与 OutboxRepository 接口定义完成(以 OutboxEntity 为读写单位)
- [ ] InMemoryOutboxRepository MVP 实现
- [ ] AsyncOutboxPoller 异步实现完成
- [ ] 所有测试通过
- [ ] 覆盖率≥90%(领域层)、≥75%(基础设施层)

---

### Task 4: 事件处理幂等性与重试机制（🔴 Must-Have，完整实现）

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环。**
> **优先级说明:** AC-4.1 幂等性检查(🔴 Must) 必须完成，AC-4.2 重试机制(🔴 Must) 完整实现指数退避+jitter。

#### TDD 循环 A:IdempotencyChecker 幂等性检查 **🔴 Must**

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_idempotency_retry.py`(验证 `is_processed`/`mark_processed`、Redis `SET NX`) |
| 🟢 绿 | 实现 `IdempotencyChecker`(基础设施层，使用 Redis `SET NX` 命令) |
| 🔄 重构 | 支持可配置 TTL、连接池复用 |

- [ ] Subtask: 🔴 红 — 编写 `IdempotencyChecker` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `IdempotencyChecker`(使用 `redis.set(event_id, "1", nx=True, ex=ttl)`)
- [ ] Subtask: 🔄 重构 — 添加可配置 TTL、连接池管理

#### TDD 循环 B:RetryPolicy 重试策略 **🔴 Must（完整指数退避）**

> **完整实现:** 指数退避 + jitter 防止惊群效应 + 最大延迟上限。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_idempotency_retry.py`(验证指数退避延迟计算、最大重试次数判断、jitter) |
| 🟢 绿 | 实现 `RetryPolicy` dataclass(指数退避算法: `delay = min(base * 2^retry_count, max) * jitter`) |
| 🔄 重构 | 添加 jitter 支持(`random.uniform(0.5, 1.5)`)、配置参数验证 |

- [ ] Subtask: 🔴 红 — 编写 `RetryPolicy` 失败测试(验证 `get_delay()` 和 `should_retry()`、指数退避序列)
- [ ] Subtask: 🟢 绿 — 实现 `RetryPolicy` dataclass(完整指数退避 + jitter)
- [ ] Subtask: 🔄 重构 — 添加配置参数验证、类型注解、docstring

#### TDD 循环 C:DeadLetterQueue 死信队列 **🔴 Must**

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_idempotency_retry.py`(验证失败事件入队、出队、队列管理) |
| 🟢 绿 | 实现 `DeadLetterQueue`(基础设施层，使用内存列表) |
| 🔄 重构 | 支持持久化、批量处理、死信事件监控 |

- [ ] Subtask: 🔴 红 — 编写 `DeadLetterQueue` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `DeadLetterQueue`
- [ ] Subtask: 🔄 重构 — 添加持久化支持、监控指标

**完成标准/Definition of Done:**
- [ ] IdempotencyChecker 实现 **🔴 Must**
- [ ] RetryPolicy 完整实现(指数退避+jitter) **🔴 Must**
- [ ] DeadLetterQueue 实现 **🔴 Must**
- [ ] 幂等性测试通过(重复发布仅处理一次)
- [ ] 重试机制测试通过(指数退避 + jitter + 死信队列)
- [ ] 覆盖率≥75%(基础设施层)

**线程安全说明:** `InMemoryOutboxRepository` 使用 `threading.Lock()` 保证线程安全（同步模式）。若后续改为异步模式，切换为 `asyncio.Lock()`。

---

### Task 5: 事件处理监控与可观测性（🔵 Could-Have，本故事最后完成，简化实现）

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环。**
> **Task 5 拆分说明:**
> - ✅ **Task 5.1**: `EventMetrics` + `EventMetricsCollector` 基础计数器 → **保留在 Story 1.3**
> - ✅ **Task 5.2**: OpenTelemetry Trace 基础版（span 创建+属性，默认关闭导出）→ **保留在 Story 1.3**
> - 🔵 **Task 5.3**: Prometheus `/metrics` HTTP 端点 → **移至 Story 1.13**
> - 🔵 **Task 5.4**: OpenTelemetry OTLP 导出器配置 → **移至 Story 1.16**
> - 🔵 **Task 5.5**: Redis 缓存指标扩展 → **移至 Story 1.4**

#### TDD 循环 A:EventMetrics 指标定义 **✅ Task 5.1**

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_monitoring.py`(验证指标定义、初始值) |
| 🟢 绿 | 实现 `EventMetrics` dataclass(包含所有指标字段) |
| 🔄 重构 | 添加 Prometheus Counter/Histogram 注册（Mock Registry，不暴露 HTTP 端点） |

- [ ] Subtask: 创建 `src/infrastructure/monitoring/event_metrics.py`
- [ ] Subtask: 🔴 红 — 编写 `EventMetrics` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `EventMetrics` dataclass
- [ ] Subtask: 🔄 重构 — 添加 Prometheus Counter/Histogram 注册（Mock）

#### TDD 循环 B:EventMetricsCollector 指标收集器 **✅ Task 5.1**

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_monitoring.py`(验证记录成功/失败/重试/死信、指标查询) |
| 🟢 绿 | 实现 `EventMetricsCollector`(线程安全计数器) |
| 🔄 重构 | 支持按事件类型分类 |

- [ ] Subtask: 🔴 红 — 编写 `EventMetricsCollector` 失败测试
- [ ] Subtask: 🟢 绿 — 实现 `EventMetricsCollector`
- [ ] Subtask: 🔄 重构 — 添加按事件类型分类

#### TDD 循环 C:OpenTelemetry Trace 基础版 **✅ Task 5.2（简化实现）**

> **简化策略:** 仅实现 span 创建+属性设置，默认 `EVENT_BUS_OTEL_TRACE_ENABLED=false`，不配置 OTLP 导出器。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_monitoring.py`(验证 Trace 创建、span 属性、配置开关) |
| 🟢 绿 | 实现 OpenTelemetry Trace 包装器（span 创建+属性设置，配置开关控制） |
| 🔄 重构 | 添加 span 属性(event_id, event_type, status, duration)、异常处理 |

- [ ] Subtask: 🔴 红 — 编写 OpenTelemetry Trace 失败测试（验证配置开关）
- [ ] Subtask: 🟢 绿 — 实现 OpenTelemetry Trace 包装器（span 创建+属性）
- [ ] Subtask: 🔄 重构 — 添加完整 span 属性、异常处理

**完成标准/Definition of Done:**
- [ ] EventMetrics 指标定义完成
- [ ] EventMetricsCollector 实现完成
- [ ] OpenTelemetry Trace 基础版完成（span 创建+属性，默认关闭导出）
- [ ] ~~Prometheus /metrics 端点~~ **🔵 移至 Story 1.13**
- [ ] ~~OpenTelemetry OTLP 导出器~~ **🔵 移至 Story 1.16**
- [ ] 所有测试通过
- [ ] 覆盖率≥75%(基础设施层)

---

### Task 6: 架构约束验证测试（🔴 Must-Have，分两阶段执行）

**关联 AC:** AC-6

> **性质说明:** 本 Task 验证事件总线实现是否符合六边形架构约束(依赖方向、层分离)，而非编写单元测试。
> **两阶段验证策略:**
> - **Phase 3 增量验证**: Task 1/2 完成后执行，检查 Redis/RabbitMQ 客户端导入仅在基础设施层
> - **最终全量验证**: 所有 Task 完成后执行，验证全量依赖方向、层分离

#### 架构验证测试实现

**Phase 3 增量验证（Task 1/2 完成后执行）:**
- [ ] Subtask: 验证 Redis 客户端导入仅在基础设施层（`src/infrastructure/events/redis_*.py`）
- [ ] Subtask: 验证 RabbitMQ 客户端导入仅在基础设施层（`src/infrastructure/events/rabbitmq_*.py`）
- [ ] Subtask: 运行 `ruff check src/infrastructure/events/` 确认通过
- [ ] Subtask: 运行 `mypy src/infrastructure/events/` 确认通过

**最终全量验证（所有 Task 完成后执行）:**
- [ ] Subtask: 创建 `tests/unit/architecture/test_event_bus_architecture.py`
- [ ] Subtask: 实现事件总线依赖方向验证(Redis/RabbitMQ 客户端导入仅在基础设施层)
- [ ] Subtask: 实现领域层接口不依赖实现验证(EventPublisher/EventListener/OutboxRepository)
- [ ] Subtask: 使用 `import-linter` 验证事件总线相关依赖方向
- [ ] Subtask: 运行 `ruff check src/infrastructure/events/` 确认通过
- [ ] Subtask: 运行 `mypy src/infrastructure/events/` 确认通过

**完成标准/Definition of Done:**
- [ ] Phase 3 增量验证通过
- [ ] 最终全量验证通过
- [ ] 事件总线依赖方向验证通过
- [ ] 领域层接口不依赖实现验证通过
- [ ] import-linter 依赖方向验证通过
- [ ] Ruff 检查通过(0 错误)
- [ ] MyPy 类型检查通过(0 问题)

---

## 📝 Dev Notes 开发笔记

### 审查决议参考

本 Story 已通过 Party Mode 多代理审查 + 架构师修正（v1.2），详见 [`1-3-event-bus-review-decision.md`](./1-3-event-bus-review-decision.md)。

**关键决议：**
- 优先级分级：Must-Have(Task 0,1,2,3,6) + Should-Have(Task 4) + Could-Have(Task 5.1,5.2)
- Task 5 拆分：5.1/5.2 保留 Story 1.3，5.3/5.4/5.5 移至后续故事
- AC-4 拆分：AC-4.1 幂等性(Must) + AC-4.2 重试(Must)
- Task 6 两阶段验证：Phase 3 增量 + 最终全量

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** Event-Driven Architecture(事件驱动架构) + Outbox Pattern(事务发件箱)
- **设计约束:**
  - **可靠传输仅 Outbox → RabbitMQ**: PostgreSQL `event_outbox` 表是事件持久化的权威来源，与业务操作同事务提交；RabbitMQ 是可靠传输通道；**Redis Pub/Sub 仅用于实时通知**（低延迟<100ms，允许丢失），不参与事务一致性与可靠投递承诺
  - **OutboxRepository 以 OutboxEntity 为读写单位**: 领域层仓储接口直接读写 `OutboxEntity` 实例(`save(entity)`, `get_unpublished() -> List[OutboxEntity]`)，不暴露底层表结构
  - **统一 async 路径**: 所有 RabbitMQ 操作与 Outbox Poller 统一使用 `async/await`(`AsyncRabbitMQPublisher.async_publish()`, `AsyncOutboxPoller.async_poll_once()`)
  - **领域层事件接口与基础设施层异步发布接口分离**: 领域层定义同步 `EventPublisher.publish(event)` 接口，基础设施层实现 `AsyncRabbitMQPublisher.async_publish(event)` 异步接口，领域层不感知异步实现细节
  - 事件处理幂等性:基于 `event_id` 的 Redis 缓存去重(`SET NX` 命令，TTL 7 天)
  - 事件重试机制:完整指数退避 + jitter + 最大延迟上限 + 死信队列(默认最大重试 3 次)
  - 审计事件归档:RabbitMQ + WORM 归档(合规要求 7 年存储)
- **技术栈:** Python 3.11+、`redis-py`(Redis 客户端)、`aio-pika`(RabbitMQ 异步客户端)、OpenTelemetry

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 ADR-003

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **双通道事件总线(选中)** | Redis 低延迟实时通知 + RabbitMQ 可靠持久化，各司其职 | 需要维护两套基础设施 | ✅ 9/10 |
| 仅 Redis | 简单、低延迟 | 不支持可靠消息传输、无死信队列、无消息持久化 | 5/10 |
| 仅 RabbitMQ | 可靠消息传输、死信队列 | 延迟较高、运维复杂 | 7/10 |
| Kafka | 高吞吐、持久化、回溯 | 运维复杂度高、不适合 MVP | 6/10 |

**决策理由:** 企业战略规划系统需要同时支持实时事件通知(如 Agent 决策完成触发 SYS Agent 仲裁)和可靠事件传输(如审计事件归档)，双通道方案在延迟和可靠性之间取得平衡。

### 事件通道选择策略

| 事件类型 | 通道 | 理由 | 示例 |
|---------|------|------|------|
| **实时通知型** | Redis Pub/Sub | 低延迟(<100ms)、允许丢失、高频 | CheckpointReached、HeartbeatTriggered |
| **业务状态型** | RabbitMQ + Outbox | 可靠性要求高、不丢失、事务一致性 | DocumentProcessed、ToolExecuted、AgentDecided |
| **审计事件型** | RabbitMQ + WORM | 合规要求 7 年存储、不可篡改 | CorrectionApproved、RoutingDecided |

### 事件处理流程图

> **📌 架构原则：可靠传输仅 Outbox → RabbitMQ，Redis 仅实时通知，统一 async 路径**

```
┌─────────────────────────────────────────────────────────────┐
│              事件发布流程（Outbox → RabbitMQ 可靠通道）        │
├─────────────────────────────────────────────────────────────┤
│  业务操作(领域层)                                             │
│       │                                                      │
│       ▼                                                      │
│  创建领域事件(DomainEvent dataclass)                          │
│       │                                                      │
│       ├───────→ Redis Pub/Sub(实时通知，尽力而为)             │
│       │              │                                       │
│       │              ▼                                       │
│       │         RedisEventPublisher.publish()                │
│       │              │                                       │
│       │              ▼                                       │
│       │         Redis 频道: sisys.events.realtime.{type}     │
│       │         ⚡ 低延迟<100ms，允许丢失，不参与事务一致性     │
│       │                                                      │
│       └───────→ PostgreSQL event_outbox 表(可靠传输唯一真源)  │
│                      │ 与业务操作同事务提交                     │
│                      ▼                                       │
│                 OutboxEntity(pending 状态)                    │
│                      │                                       │
│                      ▼                                       │
│        AsyncOutboxPoller.async_poll_once()                   │
│        (异步协程轮询 OutboxEntity，默认 1s 间隔)               │
│                      │                                       │
│                      ▼                                       │
│        AsyncRabbitMQPublisher.async_publish()                │
│        (可靠通道，消息持久化，async/await)                     │
│                      │                                       │
│                      ├─ 成功 → mark_published(entity)        │
│                      │         OutboxEntity 状态 → published  │
│                      │                                       │
│                      └─ 失败 → mark_failed(entity, error)    │
│                                OutboxEntity 状态 → failed    │
│                                后续重试                        │
│                      ▼                                       │
│                 RabbitMQ 交换机: sisys.events.reliable       │
│                 📦 可靠传输，支持消息重发/回溯                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    事件处理流程                               │
├─────────────────────────────────────────────────────────────┤
│  AsyncRabbitMQConsumer.async_consume() / RedisEventSubscriber│
│       │                                                      │
│       ▼                                                      │
│  IdempotencyChecker.is_processed(event_id)                   │
│       │                                                      │
│       ├─ 已处理 ────→ 跳过处理                               │
│       │                                                      │
│       └─ 未处理 ────→ 反序列化事件                            │
│                      │                                       │
│                      ▼                                       │
│                 查找注册的事件处理器                           │
│                      │                                       │
│                      ├─ 找到 ────→ handler(event)            │
│                      │         │                              │
│                      │         ├─ 成功 ──→ mark_processed     │
│                      │         │         EventMetricsCollector│
│                      │         │                              │
│                      │         └─ 失败 ──→ RetryPolicy        │
│                      │                   │                    │
│                      │                   ├─ 可重试 ──→ 延迟重试│
│                      │                   │                    │
│                      │                   └─ 不可重试 ──→ DLQ  │
│                      │                                        │
│                      └─ 未找到 ──→ 记录警告日志                │
└─────────────────────────────────────────────────────────────┘
```

**关键设计约束：**
1. **可靠传输仅 Outbox → RabbitMQ**: 事件的生命周期由 OutboxEntity 状态决定（pending → published/failed），RabbitMQ 是可靠通道，Redis 仅实时通知
2. **OutboxRepository 以 OutboxEntity 为读写单位**: 领域层直接读写 `OutboxEntity` 实例，不暴露底层表结构
3. **统一 async 路径**: `AsyncOutboxPoller.async_poll_once()` 和 `AsyncRabbitMQPublisher.async_publish()` 统一使用 `async/await`
4. **接口分离**: 领域层定义同步 `EventPublisher.publish(event)` 接口，基础设施层实现 `AsyncRabbitMQPublisher.async_publish(event)` 异步接口，领域层不感知异步实现细节

### 测试环境策略（审查决议补充）

**分层测试策略：**
| 测试类型 | 依赖策略 | pytest 标记 | 说明 |
|---------|---------|-------------|------|
| **单元测试** | Mock（`unittest.mock` / `fakeredis ^2.20.0`） | `@pytest.mark.unit` | 快速执行，无外部依赖 |
| **集成测试** | Docker Compose（Redis + RabbitMQ 真实实例） | `@pytest.mark.integration` | 验证真实连接、序列化、网络异常 |
| **验收测试（Gherkin）** | Docker Compose | `@pytest.mark.e2e` | 端到端业务场景验证 |

**Docker Compose 配置（`docker-compose.test.yml`，Story 1.3 实施时创建）：**
- `redis-test`: redis:7-alpine, 端口 6380:6379, healthcheck `redis-cli ping`
- `rabbitmq-test`: rabbitmq:3-management-alpine, 端口 5673:5672, healthcheck `rabbitmq-diagnostics check_running`
- **无 PostgreSQL**（Story 1.3 Outbox 使用 InMemoryOutboxRepository，PostgreSQL 延后至 Story 1.5）

**Makefile 命令（Story 1.3 实施时添加）：**
```makefile
test-env-up:
	docker-compose -f docker-compose.test.yml up -d

test-env-down:
	docker-compose -f docker-compose.test.yml down -v

test-integration: test-env-up
	@# 健康检查等待替代 sleep 10
	@until redis-cli -p 6380 ping | grep -q PONG; do echo "Waiting for Redis..."; sleep 1; done
	pytest -m integration --cov=src --cov-fail-under=80
	make test-env-down
```

### 依赖包确认

| 依赖包 | 当前状态 | 版本 | 用途 |
|--------|---------|------|------|
| `redis` | ✅ 已存在 | `^5.0.1` | Redis 客户端 |
| `aio-pika` | ✅ 已存在 | `^9.3.0` | RabbitMQ **异步**客户端（`async/await`） |
| `opentelemetry-api` | ✅ 已存在 | `^1.21.0` | OpenTelemetry API（Task 5） |
| `opentelemetry-sdk` | ✅ 已存在 | `^1.21.0` | OpenTelemetry SDK（Task 5） |
| `prometheus-client` | ✅ 已存在 | `^0.21.1` | Prometheus 指标导出 |
| `pytest-asyncio` | ✅ 已存在 | — | 异步测试支持（RabbitMQ 组件必需） |
| `fakeredis` | ❌ 需添加 | `^2.20.0` | Redis Mock（单元测试） |

**需添加的测试依赖：**
```toml
[tool.poetry.group.test.dependencies]
fakeredis = "^2.20.0"  # Redis Mock 支持单元测试
```

### Task 实施顺序建议（审查决议推荐）

```
Phase 1（核心基础）:
  Task 0 → SDD 规范定义（前置）
  Task 1 → Redis Pub/Sub（简单，快速验证通道）

Phase 2（可靠传输）:
  Task 2 → RabbitMQ 持久化通道（async/await，需 pytest-asyncio）
  Task 3 → Outbox Pattern（InMemoryOutboxRepository + 轮询发布）

Phase 3（架构验证）:
  Task 6 → 架构约束验证（增量验证 Redis/RabbitMQ 导入位置）

Phase 4（增强能力）:
  Task 4 → 幂等性与重试

Phase 5（可观测性基础，本故事最后完成）:
  Task 5.1 → EventMetrics + EventMetricsCollector 基础计数器
  Task 5.2 → OpenTelemetry Trace 基础版（span 创建+属性，默认关闭导出）

最终验证:
  Task 6 → 架构约束全量验证（确保所有 Task 完成后依赖方向仍正确）
```

**完成标志：**
- Must-Have Task(0,1,2,3,6) 全部完成且测试通过
- Task 4 至少实现幂等性检查(`IdempotencyChecker`)
- Task 5.1/5.2 至少实现 `EventMetrics` + `EventMetricsCollector` 基础计数器 + OpenTelemetry span 创建
- 覆盖率达标（领域层 ≥90%，基础设施层 ≥75%，整体 ≥80%）
- `ruff check` + `mypy` + `import-linter` 全部通过
- Gherkin 验收测试通过（至少 1 个端到端场景）

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── outbox.py                    # OutboxEntity 定义
│   │   ├── repositories/
│   │   │   ├── base.py                      # (Story 1.1 已创建)
│   │   │   └── outbox.py                    # OutboxRepository 接口
│   │   ├── events/
│   │   │   ├── __init__.py                  # (Story 1.2 已创建)
│   │   │   ├── base.py                      # (Story 1.1 已创建)
│   │   │   ├── publisher.py                 # (Story 1.2 已创建)
│   │   │   ├── listener.py                  # (Story 1.2 已创建)
│   │   │   ├── store.py                     # (Story 1.2 已创建)
│   │   │   └── enums.py                     # (Story 1.2 已创建)
│   │   └── ...                              # (Story 1.1/1.2 已创建)
│   ├── application/
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   └── adapters.py                  # (Story 1.2 已创建)
│   │   └── ...                              # (后续 Story)
│   └── infrastructure/
│       ├── config/
│       │   ├── __init__.py
│       │   ├── redis.py                     # RedisConfig 配置模型
│       │   └── rabbitmq.py                  # RabbitMQConfig 配置模型
│       ├── events/
│       │   ├── __init__.py
│       │   ├── redis_publisher.py           # RedisEventPublisher 实现
│       │   ├── redis_subscriber.py          # RedisEventSubscriber 实现
│       │   ├── async_rabbitmq_publisher.py  # AsyncRabbitMQPublisher (可靠通道，async)
│       │   ├── async_rabbitmq_consumer.py   # AsyncRabbitMQConsumer (可靠通道，async)
│       │   └── async_outbox_poller.py       # AsyncOutboxPoller (异步协程轮询 OutboxEntity，async)
│       ├── repositories/
│       │   ├── __init__.py
│       │   └── outbox.py                    # InMemoryOutboxRepository 实现
│       ├── monitoring/
│       │   ├── __init__.py
│       │   └── event_metrics.py             # EventMetrics + EventMetricsCollector
│       └── idempotency/
│           ├── __init__.py
│           ├── checker.py                   # IdempotencyChecker
│           ├── retry_policy.py              # RetryPolicy
│           └── dead_letter_queue.py         # DeadLetterQueue
├── tests/
│   ├── unit/
│   │   ├── infrastructure/
│   │   │   ├── events/
│   │   │   │   ├── test_redis_event_bus.py         # Redis Pub/Sub 测试
│   │   │   │   ├── test_rabbitmq_event_bus.py      # RabbitMQ 测试
│   │   │   │   └── test_outbox_pattern.py          # 事务发件箱测试
│   │   │   ├── idempotency/
│   │   │   │   └── test_idempotency_retry.py       # 幂等性与重试测试
│   │   │   └── monitoring/
│   │   │       └── test_event_monitoring.py        # 事件监控测试
│   │   ├── architecture/
│   │   │   ├── test_hexagonal_architecture.py      # (Story 1.1 已创建)
│   │   │   ├── test_event_architecture.py          # (Story 1.2 已创建)
│   │   │   └── test_event_bus_architecture.py      # 事件总线架构测试
│   │   └── domain/
│   │       └── repositories/
│   │           └── test_outbox_repository.py       # OutboxRepository 接口测试
│   └── acceptance/
│       └── test_story_1.3.feature                  # Gherkin 验收测试
└── ...
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.1: 六边形架构骨架](./1-1-hexagonal-architecture-skeleton.md), [Story 1.2: 领域事件定义](./1-2-domain-event-definition.md)

**关键学习/Key Learnings:**
1. **领域层零依赖约束是架构基石** — Story 1.1/1.2 严格遵循领域层仅使用 Python 标准库，为后续基础设施实现提供清晰边界
2. **import-linter 验证依赖方向高效可靠** — 替代手写 ast 扫描，大幅降低架构验证测试复杂度
3. **TDD 红→绿→重构循环内化到每个 Task** — 禁止将测试编写与代码实现分离，确保每个 Task 独立完成完整循环
4. **dataclasses.asdict() 序列化策略清晰** — 领域事件使用 `dataclasses.asdict()` 转换，应用层 TypeAdapter 仅用于 JSON 边界转换

**应用到本故事/Applied to This Story:**
- [ ] 严格遵守领域层零依赖约束(OutboxRepository 接口仅使用 Python 标准库类型注解)
- [ ] 使用 import-linter 验证事件总线相关依赖方向
- [ ] 每个 Task 独立完成 TDD 红→绿→重构循环
- [ ] 继续使用 dataclasses.asdict() 序列化领域事件
- [ ] Redis/RabbitMQ 客户端导入仅在基础设施层，不得泄漏至领域层

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-12 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-2-domain-event-definition.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **项目上下文** | `_bmad-output/project-context.md` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取(双通道事件总线、事务发件箱、幂等性、重试机制)
- [x] 前一个故事学习经验整合(Story 1.1/1.2 领域层零依赖、import-linter、TDD 循环内化)
- [x] 状态设置为 `backlog`(待 `dev-story` 实施时更新为 `ready-for-dev`)
- [x] SDD+TDD 融合开发要求定义完成(Task 0 前置 + 6 个实现 Task)
- [x] 项目结构对齐统一规范
- [x] 事件通道选择策略定义完成(Redis Pub/Sub + RabbitMQ + Outbox)
- [x] 事件处理流程图绘制完成

### 文件清单 File List

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/entities/outbox.py` - OutboxEntity 定义
- `src/domain/repositories/outbox.py` - OutboxRepository 接口
- `src/infrastructure/config/redis.py` - RedisConfig 配置模型
- `src/infrastructure/config/rabbitmq.py` - RabbitMQConfig 配置模型
- `src/infrastructure/events/redis_publisher.py` - RedisEventPublisher 实现
- `src/infrastructure/events/redis_subscriber.py` - RedisEventSubscriber 实现
- `src/infrastructure/events/async_rabbitmq_publisher.py` - AsyncRabbitMQPublisher 实现(async/await)
- `src/infrastructure/events/async_rabbitmq_consumer.py` - AsyncRabbitMQConsumer 实现(async/await)
- `src/infrastructure/events/async_outbox_poller.py` - AsyncOutboxPoller 实现(异步协程轮询 OutboxEntity)
- `src/infrastructure/repositories/outbox.py` - InMemoryOutboxRepository 实现
- `src/infrastructure/monitoring/event_metrics.py` - EventMetrics + EventMetricsCollector
- `src/infrastructure/idempotency/checker.py` - IdempotencyChecker
- `src/infrastructure/idempotency/retry_policy.py` - RetryPolicy
- `src/infrastructure/idempotency/dead_letter_queue.py` - DeadLetterQueue
- `tests/unit/infrastructure/events/test_redis_event_bus.py` - Redis Pub/Sub 测试
- `tests/unit/infrastructure/events/test_rabbitmq_event_bus.py` - RabbitMQ 测试
- `tests/unit/infrastructure/events/test_outbox_pattern.py` - 事务发件箱测试
- `tests/unit/infrastructure/idempotency/test_idempotency_retry.py` - 幂等性与重试测试
- `tests/unit/infrastructure/monitoring/test_event_monitoring.py` - 事件监控测试
- `tests/unit/architecture/test_event_bus_architecture.py` - 事件总线架构测试
- `tests/acceptance/test_story_1.3.feature` - Gherkin 验收测试

**修改的文件/Modified Files (Dev Story 实施时):**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 更新 story 状态为 `ready-for-dev` → `in-progress` → `done`
- `_bmad-output/implementation-artifacts/stories/1-3-event-bus-implementation.md` - 更新状态，标记所有 task 完成

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.3 |
| **Story Key** | 1-3-event-bus-implementation |
| **File** | `_bmad-output/implementation-artifacts/stories/1-3-event-bus-implementation.md` |
| **Status** | `backlog` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 2: 架构基础与事件驱动 |
| **优先级** | P0-3(第三个故事，事件驱动基础) |
| **覆盖 FR** | FR-AR-02(领域事件发布)、FR-CP-04(OpenTelemetry Trace) |

### 完成总结 Completion Summary

> *(待实施后填写)*

### 下一步 Next Steps

- [ ] Story created with `backlog` status
- [ ] 运行 `dev-story` 开始实施(遵循 SDD+TDD 融合模式)
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 可选: 运行 `/bmad:tea:automate` 生成测试(如果 Test Architect 模块已安装)

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-12
**最后更新/Last Updated:** 2026-04-12
**更新说明:** 基于 epics_v1.0.md Story 1.3 定义、architecture.md 双通道事件总线约束、story-template.md 模板创建
