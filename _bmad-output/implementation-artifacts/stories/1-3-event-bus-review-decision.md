# Story 1.3 审查决议文件（修订版）

**审查日期:** 2026-04-12
**审查方式:** Party Mode 多代理审查 + 架构师修正
**参与代理:** Winston (Architect), Murat (Tea), Amelia (Dev), Mary (Analyst), Bob (SM), BMad Master (环境/CI/CD), Quinn (QA), Barry (Quick Dev)
**决议选项:** **选项 B（修订）** — 保留当前结构，明确优先级，Task 5 保留在本故事最后完成

---

## 📋 决议摘要

经多代理审查与架构师修正，Story 1.3 保留现有 Task 结构（Task 0-6），将 Task 按优先级分为三级：**Must-Have（必须完成）**、**Should-Have（应该完成）**、**Could-Have（本故事最后完成）**。同时补充环境配置、测试策略、依赖包确认等缺失内容，并修正原决议中的 4 项 P0/P1 问题。

**关键变更（与原决议相比）：**
- ✅ Task 5（监控与可观测性）**保留在 Story 1.3 最后完成**，不移至 Story 1.4
- ✅ 修正 P0-01: 明确 RabbitMQ 组件使用 `async/await`
- ✅ 修正 P0-02: Docker Compose 移除 `postgres-test`（Story 1.3 用 InMemoryOutboxRepository）
- ✅ 修正 P1-01: 补充路由键模式文档
- ✅ 修正 P1-02: Makefile 用健康检查等待替代 `sleep 10`

---

## 🎯 优先级分级

### 🔴 Must-Have（必须完成，Story 1.3 核心范围）

| Task | 描述 | 关联 AC | 理由 |
|------|------|---------|------|
| **Task 0** | SDD 规范定义（前置） | AC-1 | 接口、数据模型、配置模型、Gherkin 验收测试是后续所有实现的基础 |
| **Task 1** | Redis Pub/Sub 实时事件通道 | AC-1 | 核心实时通知能力，业务价值直接可见 |
| **Task 2** | RabbitMQ 持久化事件通道 | AC-2 | 核心可靠传输能力，业务状态型事件必需 |
| **Task 3** | 事务发件箱模式（Outbox Pattern） | AC-3 | 保证事件与业务操作原子性，防止事件丢失 |
| **Task 6** | 架构约束验证测试 | AC-6 | 确保六边形架构依赖方向正确，防止架构腐化 |

**完成标志：** 以上 Task 全部完成且测试通过，是 Story 1.3 的最低完成标准。

---

### 🟡 Should-Have（应该完成，Story 1.3 期望范围）

| Task | 描述 | 关联 AC | 理由 |
|------|------|---------|------|
| **Task 4** | 事件处理幂等性与重试机制 | AC-4 | 提升系统可靠性，幂等性检查(SET NX)为必须，重试机制可简化实现（固定延迟代替指数退避+jitter） |

**完成标志：** MVP 阶段至少实现幂等性检查(`IdempotencyChecker`)，重试机制可用固定延迟(`RetryPolicy` 简化版)代替指数退避。若 Sprint 时间充裕再完善指数退避+jitter+死信队列。

---

### 🔵 Could-Have（本故事最后完成，部分组件拆分至后续故事）

| Task | 描述 | 关联 AC | 理由 | 执行时机 | 拆分说明 |
|------|------|---------|------|---------|---------|
| **Task 5.1** | EventMetrics + EventMetricsCollector 基础版 | AC-5 | 事件处理指标采集，与事件总线强绑定 | **Must/Should Task 全部完成后执行** | ✅ 保留在 Story 1.3 |
| **Task 5.2** | OpenTelemetry Trace 基础版（简化） | AC-5 | span 创建+属性设置，默认不启用导出 | **Must/Should Task 全部完成后执行** | ✅ 保留在 Story 1.3（简化实现） |
| **Task 5.3** | Prometheus /metrics 端点 | AC-5 | HTTP 端点暴露指标供 Prometheus 抓取 | — | 🔵 移至 Story 1.13（K8s 扩缩容需要 Prometheus 指标源） |
| **Task 5.4** | OpenTelemetry OTLP 导出器 | AC-5 | 全链路追踪导出至 OTLP 后端 | — | 🔵 移至 Story 1.16（集成测试框架包含端到端追踪验证） |
| **Task 5.5** | Redis 缓存指标扩展 | AC-5 | 缓存命中率、延迟指标 | — | 🔵 移至 Story 1.4（Redis 缓存层实施时添加） |

**完成标志：**
- **Story 1.3 范围**：Task 5.1 + Task 5.2 完成（`EventMetrics` 数据类 + `EventMetricsCollector` 基础计数器 + OpenTelemetry span 创建+属性，默认 `EVENT_BUS_OTEL_TRACE_ENABLED=false`）
- **后续故事范围**：Task 5.3/5.4/5.5 分别在 Story 1.13/1.16/1.4 实施时完成
- Story 1.3 不阻塞核心功能验收，简化实现可接受

---

## 📊 更新后的 AC → Task 追溯矩阵

| AC | 验收标准描述 | 优先级 | 关联 Task | 是否阻断 Story 完成 |
|----|-------------|--------|-----------|-------------------|
| AC-1 | Redis Pub/Sub 实时事件通道实现 | 🔴 Must | Task 0, Task 1 | ✅ 是 |
| AC-2 | RabbitMQ 持久化事件通道实现 | 🔴 Must | Task 2 | ✅ 是 |
| AC-3 | 事务发件箱模式实现 | 🔴 Must | Task 3 | ✅ 是 |
| AC-4 | 事件处理幂等性与重试机制 | 🟡 Should | Task 4 | ⚠️ 部分（幂等性检查必须，重试可简化） |
| AC-5 | 事件处理监控与可观测性 | 🔵 Could | Task 5.1, Task 5.2 | ❌ 否（简化实现可接受，本故事最后执行；Task 5.3/5.4/5.5 移至后续故事） |
| AC-6 | 架构约束验证测试就绪 | 🔴 Must | Task 6 | ✅ 是 |

**AC-4 拆分说明：**
- **AC-4.1 幂等性检查**（Must）: `IdempotencyChecker` 基于 Redis `SET NX`，TTL 7 天
- **AC-4.2 重试机制**（Should）: `RetryPolicy` 简化版（固定延迟 1s，最大 3 次）+ `DeadLetterQueue` 基础实现

---

## 🔧 补充决议（已修正）

### 1. 测试环境策略

**决议：** 采用 **单元测试 Mock + 集成测试 Docker Compose** 分层策略。

| 测试类型 | 依赖策略 | pytest 标记 | 说明 |
|---------|---------|-------------|------|
| **单元测试** | Mock（`unittest.mock` / `fakeredis`） | `@pytest.mark.unit` | 快速执行，无外部依赖 |
| **集成测试** | Docker Compose（Redis + RabbitMQ 真实实例） | `@pytest.mark.integration` | 验证真实连接、序列化、网络异常 |
| **验收测试（Gherkin）** | Docker Compose | `@pytest.mark.e2e` | 端到端业务场景验证 |

**实施要求：**
- 单元测试必须能在无 Docker 环境下运行（`pytest -m unit`）
- 集成测试标记为 `@pytest.mark.redis` / `@pytest.mark.rabbitmq`，默认跳过
- CI/CD 中显式启用集成测试（`pytest -m integration`）
- **RabbitMQ 组件测试必须使用 `pytest-asyncio`**（因 `aio-pika` 是异步客户端）

---

### 2. Docker Compose 测试环境配置（已修正）

**决议：** 在 Story 1.3 实施时创建 `docker-compose.test.yml`，包含以下服务：

**修正说明：** 移除 `postgres-test` 服务，Story 1.3 的 Outbox 使用 `InMemoryOutboxRepository`，PostgreSQL 持久化延后至 Story 1.5(持久化层)时启用。

```yaml
# docker-compose.test.yml（Story 1.3 实施时创建）
version: "3.8"

services:
  redis-test:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  rabbitmq-test:
    image: rabbitmq:3-management-alpine
    ports:
      - "5673:5672"
      - "15673:15672"
    environment:
      RABBITMQ_DEFAULT_USER: sisys_test
      RABBITMQ_DEFAULT_PASS: test_password
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**Makefile 命令补充（已修正）：**
```makefile
# Story 1.3 实施时添加到 Makefile
.PHONY: test-env-up test-env-down test-integration test-wait

test-env-up:
	docker-compose -f docker-compose.test.yml up -d
	@echo "Waiting for services to be healthy..."
	@docker-compose -f docker-compose.test.yml ps --format json \
	  | jq -r '.[] | select(.Health == "healthy") | .Service' \
	  | while read svc; do echo "$$svc is healthy"; done || \
	(docker-compose -f docker-compose.test.yml ps && exit 1)

test-env-down:
	docker-compose -f docker-compose.test.yml down -v

test-integration: test-env-up
	@# 等待 Redis 健康
	@until redis-cli -p 6380 ping | grep -q PONG; do \
	  echo "Waiting for Redis..."; sleep 1; done
	@# 等待 RabbitMQ 健康
	@until docker-compose -f docker-compose.test.yml exec -T rabbitmq-test \
	  rabbitmq-diagnostics check_running >/dev/null 2>&1; do \
	  echo "Waiting for RabbitMQ..."; sleep 2; done
	@echo "All services are ready."
	pytest -m integration --cov=src --cov-fail-under=80
	make test-env-down
```

**修正说明：** 用健康检查循环替代 `sleep 10`，更可靠地等待服务就绪。

---

### 3. 环境变量清单（.env.example 更新）

**决议：** Story 1.3 实施时需更新 `.env.example`，增加以下事件总线专用变量：

```bash
# ===========================================
# Event Bus - Redis Pub/Sub (实时通知型)
# ===========================================
EVENT_BUS_REDIS_HOST=localhost
EVENT_BUS_REDIS_PORT=6379
EVENT_BUS_REDIS_DB=1
EVENT_BUS_REDIS_PASSWORD=
EVENT_BUS_REDIS_MAX_CONNECTIONS=10
EVENT_BUS_REDIS_SOCKET_TIMEOUT=5.0

# ===========================================
# Event Bus - RabbitMQ (业务状态型)
# ===========================================
EVENT_BUS_RABBITMQ_HOST=localhost
EVENT_BUS_RABBITMQ_PORT=5672
EVENT_BUS_RABBITMQ_USER=sisys
EVENT_BUS_RABBITMQ_PASSWORD=your_rabbitmq_password_here
EVENT_BUS_RABBITMQ_VHOST=/
EVENT_BUS_RABBITMQ_EXCHANGE_NAME=sisys.events
EVENT_BUS_RABBITMQ_EXCHANGE_TYPE=topic
EVENT_BUS_RABBITMQ_PREFETCH_COUNT=10
EVENT_BUS_RABBITMQ_HEARTBEAT=60

# 路由键规范（补充）
# 格式: sisys.events.{event_type}
# 示例: sisys.events.DocumentProcessed, sisys.events.AgentDecided
# 交换机绑定: sisys.events.# (通配符匹配所有事件)

# ===========================================
# Event Bus - Outbox Pattern
# ===========================================
EVENT_BUS_OUTBOX_POLL_INTERVAL_SECONDS=1
EVENT_BUS_OUTBOX_BATCH_SIZE=50
EVENT_BUS_OUTBOX_MAX_RETRIES=3

# ===========================================
# Event Bus - Idempotency & Retry
# ===========================================
EVENT_BUS_IDEMPOTENCY_TTL_SECONDS=604800  # 7 天
EVENT_BUS_RETRY_BASE_DELAY_SECONDS=1
EVENT_BUS_RETRY_MAX_DELAY_SECONDS=60
EVENT_BUS_RETRY_MAX_ATTEMPTS=3
EVENT_BUS_RETRY_JITTER_ENABLED=true

# ===========================================
# Event Bus - Monitoring (Task 5, 本故事最后完成)
# ===========================================
EVENT_BUS_METRICS_ENABLED=true
EVENT_BUS_PROMETHEUS_PORT=9091
EVENT_BUS_OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
EVENT_BUS_OTEL_TRACE_ENABLED=false  # MVP 可关闭，性能敏感时启用
```

**说明：**
- 事件总线使用独立 Redis DB（DB=1），与应用缓存（DB=0）隔离
- RabbitMQ 使用独立 vhost（`/`），避免与其他服务冲突
- **补充路由键规范**：`sisys.events.{event_type}`，交换机绑定 `sisys.events.#` 通配符
- Outbox 轮询间隔、重试策略均可配置
- OpenTelemetry Trace MVP 可关闭，性能敏感时启用

---

### 4. 依赖包确认（已修正）

**决议：** 检查 `pyproject.toml`，确认以下依赖已存在：

| 依赖包 | 当前状态 | 版本 | 用途 |
|--------|---------|------|------|
| `redis` | ✅ 已存在 | `^5.0.1` | Redis 客户端 |
| `aio-pika` | ✅ 已存在 | `^9.3.0` | RabbitMQ **异步**客户端（`async/await`） |
| `opentelemetry-api` | ✅ 已存在 | `^1.21.0` | OpenTelemetry API（Task 5） |
| `opentelemetry-sdk` | ✅ 已存在 | `^1.21.0` | OpenTelemetry SDK（Task 5） |
| `opentelemetry-exporter-otlp` | ✅ 已存在 | `^1.21.0` | OTLP 导出器（Task 5） |
| `prometheus-client` | ✅ 已存在 | `^0.21.1` | Prometheus 指标导出 |
| `pytest-asyncio` | ✅ 已存在 | — | 异步测试支持（RabbitMQ 组件必需） |
| `fakeredis` | ❌ 需添加 | — | Redis Mock（单元测试） |
| `pytest-bdd` | ✅ 已存在 | `^8.0.0` | Gherkin 验收测试 |

**需添加的测试依赖：**
```toml
[tool.poetry.group.test.dependencies]
fakeredis = "^2.20.0"  # Redis Mock 支持单元测试
```

**兼容性确认：**
- ✅ `fakeredis ^2.20.0` 兼容 `redis ^5.0.1`（fakeredis 2.20+ 支持 redis-py 5.x）
- ✅ `aio-pika ^9.3.0` 基于 `aiormq` 异步客户端，需 `pytest-asyncio` 测试

---

### 5. Task 实施顺序建议（已修正，含 Task 5 拆分）

**推荐的实施顺序（考虑依赖关系与风险）：**

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
  Task 4 → 幂等性与重试（Must: 幂等性检查, Should: 简化重试）

Phase 5（可观测性基础，本故事最后完成）:
  Task 5.1 → EventMetrics + EventMetricsCollector 基础计数器
  Task 5.2 → OpenTelemetry Trace 基础版（span 创建+属性，默认关闭导出）

最终验证:
  Task 6 → 架构约束全量验证（确保所有 Task 完成后依赖方向仍正确）
```

**Task 5 拆分归属表：**

| Task 5 子任务 | 归属故事 | 范围 | 实施时机 |
|-------------|---------|------|---------|
| **Task 5.1** | Story 1.3 ✅ | `EventMetrics` 数据类 + `EventMetricsCollector` 基础计数器 | Story 1.3 Phase 5 |
| **Task 5.2** | Story 1.3 ✅ | OpenTelemetry span 创建+属性设置，`EVENT_BUS_OTEL_TRACE_ENABLED=false` | Story 1.3 Phase 5 |
| **Task 5.3** | Story 1.13 🔵 | Prometheus `/metrics` HTTP 端点暴露指标 | Story 1.13（K8s 扩缩容） |
| **Task 5.4** | Story 1.16 🔵 | OpenTelemetry OTLP 导出器配置 | Story 1.16（集成测试框架） |
| **Task 5.5** | Story 1.4 🔵 | Redis 缓存命中率、延迟指标扩展 | Story 1.4（Redis 缓存层） |

**修正说明：**
- Task 6 分两阶段执行：Phase 3 **增量验证**（检查 Redis/RabbitMQ 客户端导入仅在基础设施层），最终完成后**全量验证**（验证全量依赖方向、层分离）
- Phase 1-2 完成后应能运行 `pytest -m unit` 并通过
- Phase 3 完成后 Story 1.3 核心功能就绪
- Phase 4-5 根据 Sprint 剩余时间执行，Task 5.1/5.2 简化实现不阻塞 Story 完成
- **Task 5.3/5.4/5.5 明确拆分至后续故事**，避免 Story 1.3 范围蔓延

---

## ⚠️ 风险识别与缓解（已修正）

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| RabbitMQ 异步集成复杂度高 | 阻塞 Task 2 | 中 | 先用简单同步实现验证逻辑，后续改为 `async/await`；确保 `pytest-asyncio` 配置正确 |
| OutboxPollingPublisher 线程安全 | 数据不一致 | 中 | `InMemoryOutboxRepository` 使用 `threading.Lock()`（同步）或 `asyncio.Lock()`（异步），明确选择一种 |
| 集成测试执行时间长 | CI/CD 超时 | 低 | 标记为 `@integration`，CI 中按需启用；健康检查等待替代 `sleep` |
| Task 5 范围蔓延 | 阻塞 Story 完成 | 中 | **已拆分 Task 5.3/5.4/5.5 至后续故事**，Story 1.3 仅实现 Task 5.1/5.2 基础监控 |
| Task 5 拆分过细导致后续集成困难 | Story 1.4/1.13/1.16 实施时指标不兼容 | 低 | Story 1.3 定义清晰的 `EventMetrics` 接口契约，后续故事复用扩展 |
| Story 1.3 无 Prometheus 端点无法验证指标 | 单元测试只能验证计数器逻辑 | 低 | 单元测试 Mock Prometheus Registry，Story 1.13 集成验证 HTTP 端点 |
| fakeredis 版本不兼容 | 单元测试失败 | 低 | 已确认 `fakeredis ^2.20.0` 兼容 `redis ^5.0.1` |

---

## ✅ 审查结论（修订版）

**决议：Story 1.3 保留现有结构，按优先级分级执行，Task 5 拆分后基础部分保留在本故事最后完成。**

- **Must-Have（Task 0, 1, 2, 3, 6）**：Story 1.3 核心范围，必须完成
- **Should-Have（Task 4）**：期望完成，至少实现幂等性检查，重试可简化
- **Could-Have（Task 5.1, 5.2）**：保留在 Story 1.3 最后完成，简化实现可接受，不阻塞核心功能验收
- **拆分至后续故事（Task 5.3, 5.4, 5.5）**：
  - Task 5.3（Prometheus `/metrics` 端点）→ Story 1.13（K8s 动态扩缩容）
  - Task 5.4（OpenTelemetry OTLP 导出器）→ Story 1.16（集成测试框架）
  - Task 5.5（Redis 缓存指标扩展）→ Story 1.4（Redis 高速缓存层）

**前置条件（实施前必须完成）：**
1. ✅ 创建 `docker-compose.test.yml`（仅 Redis + RabbitMQ，无 PostgreSQL）
2. ✅ 更新 `.env.example` 增加事件总线变量（含路由键规范）
3. ✅ 添加 `fakeredis ^2.20.0` 到测试依赖
4. ✅ 确认 `pytest-asyncio` 已配置（`pyproject.toml` 中 `asyncio_mode = "auto"` 或测试文件加 `@pytest.mark.asyncio`）

**完成标志：**
- Must-Have Task 全部完成且测试通过
- Task 4 至少实现幂等性检查(`IdempotencyChecker`)
- Task 5.1/5.2 至少实现 `EventMetrics` + `EventMetricsCollector` 基础计数器 + OpenTelemetry span 创建（OTLP 导出器不启用）
- 覆盖率达标（领域层 ≥90%，基础设施层 ≥75%，整体 ≥80%）
- `ruff check` + `mypy` + `import-linter` 全部通过
- Gherkin 验收测试通过（至少 1 个端到端场景）

---

## 📝 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|---------|--------|
| 1.0 | 2026-04-12 | 初始 Party Mode 审查决议 | 多代理审查团队 |
| 1.1 | 2026-04-12 | **架构师修正版**：<br>1. Task 5 保留在 Story 1.3 最后完成，不移至 Story 1.4<br>2. 修正 P0-01: 明确 RabbitMQ 组件使用 `async/await` + `pytest-asyncio`<br>3. 修正 P0-02: Docker Compose 移除 `postgres-test`<br>4. 修正 P1-01: 补充路由键模式文档 `sisys.events.{event_type}`<br>5. 修正 P1-02: Makefile 用健康检查等待替代 `sleep 10`<br>6. 修正 Task 6: 分两阶段验证（Phase 3 增量 + 最终全量）<br>7. 修正 AC-4: 拆分幂等性(Must)与重试(Should) | 架构师 |
| 1.2 | 2026-04-12 | **Task 5 拆分修正版**：<br>1. Task 5 拆分为 5.1/5.2/5.3/5.4/5.5 五个子任务<br>2. Task 5.1/5.2 保留 Story 1.3（EventMetrics + Collector + Otel span 基础）<br>3. Task 5.3 移至 Story 1.13（Prometheus /metrics 端点）<br>4. Task 5.4 移至 Story 1.16（OTLP 导出器配置）<br>5. Task 5.5 移至 Story 1.4（Redis 缓存指标扩展）<br>6. 更新 AC-5 追溯矩阵、Phase 5 实施顺序、风险识别、完成标志 | 架构师 |

---

**审查人:** Party Mode 多代理审查团队 + 架构师修正
**批准人:** Agimtech（待确认）
**状态:** `approved-with-conditions`（附带条件批准）

---

**文件版本:** 1.1
**创建日期:** 2026-04-12
**关联文件:** `1-3-event-bus-implementation.md`
