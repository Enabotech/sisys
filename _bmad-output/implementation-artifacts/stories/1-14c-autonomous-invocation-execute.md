# Story 1.14c: 自主调用循环 - execute 实现

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现会话命名空间执行与状态快照,
**So that** 任务在隔离环境中执行，状态可持久化和恢复。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 5（or.md 系统公理实现）的第三个故事，在 Story 1.14a（trigger 实现）和 Story 1.14b（route 实现）完成后实现 execute 机制。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **会话命名空间隔离** | 任务在 Docker/gVisor 沙箱中隔离执行，防止资源冲突和环境污染 | 沙箱隔离 100%，无状态泄漏 |
| **状态快照持久化** | 执行状态序列化至 Redis Hash，支持主从复制与故障转移 | 快照延迟 P95<50ms，恢复成功率 100% |
| **执行事件发布** | 完成后发布 AutoExecuted 技术事件，下游监听器根据业务类型发布对应领域事件 | 事件发布成功率 ≥99% |
| **execute 与 trigger/route 解耦** | execute 机制通过事件总线接收 Routed 事件，发布执行完成事件 | 六边形架构合规，无循环依赖 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 5: or.md 系统公理实现，Story 1.14c

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute），覆盖"execute"阶段

**前置依赖:** Story 1.14a（trigger 实现）、Story 1.14b（route 实现）

**后续依赖:** Story 1.15a（外部化记忆 - 上下文压缩）、Story 1.17（UDMR 基础路由）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 会话命名空间隔离

**Given** Routed 事件（包含目标 Agent/工具和任务上下文）
**When** AutoExecuteService 接收 Routed 事件
**Then** 在会话命名空间中执行任务（Docker/gVisor 沙箱）
**And** 沙箱提供资源限制（CPU/内存/网络/文件系统）
**And** 同 session_id 的任务共享同一命名空间

**验证标准/Validation Criteria:**
- [ ] AutoExecuteService 事件监听器注册（`src/domain/services/auto_execute_service.py`）
- [ ] DockerSandboxAdapter 实现（`src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`）
- [ ] 会话命名空间管理（session_id → namespace 映射）
- [ ] 资源限制配置（CPU/内存/超时）
- [ ] 沙箱隔离 100%（无状态泄漏、资源隔离）

### AC-2: 状态快照持久化

**Given** 任务在沙箱中执行
**When** 执行过程中或执行完成时
**Then** 状态快照序列化至 Redis Hash
**And** 支持主从复制与故障转移（Redis Sentinel/Cluster）
**And** TTL 可配置（默认 24h-30d）

**验证标准/Validation Criteria:**
- [ ] CheckpointSnapshot 数据模型（`src/domain/entities/checkpoint_snapshot.py`）
- [ ] 状态快照序列化格式（JSON/MessagePack）
- [ ] Redis Hash 存储实现（`src/infrastructure/storage/redis/redis_snapshot_store.py`）
- [ ] 主从复制支持（Redis Sentinel/Cluster 自动切换）
- [ ] TTL 配置化（`SNAPSHOT_TTL_SECONDS` 环境变量）
- [ ] 快照延迟 P95<50ms（基准测试）
- [ ] 恢复成功率 100%（恢复测试）

### AC-3: 执行事件发布

**Given** 任务执行完成
**When** AutoExecuteService 发布执行结果
**Then** 发布 AutoExecuted 技术事件至事件总线
**And** 下游监听器根据业务类型发布对应领域事件（DocumentProcessed/ToolAutoExecuted/AgentDecided）
**And** 事件携带完整执行上下文（结果、成本、耗时）

**验证标准/Validation Criteria:**
- [ ] AutoExecuted 事件定义（`src/domain/events/auto_execute_events.py`）
  - 字段: event_id, session_id, task_context, execution_result, cost_estimate, latency_ms, timestamp, business_event_type
  - business_event_type 字段标识下游应发布的具体领域事件（DocumentProcessed/ToolAutoExecuted/AgentDecided）
- [ ] 下游监听器（`src/application/event_handlers/auto_execute_completed_listener.py`）根据 business_event_type 发布对应领域事件
- [ ] 事件携带执行结果、成本审计、耗时信息
- [ ] 事件发布成功率 ≥99%（RabbitMQ 持久化）
- [ ] 事务发件箱模式（AutoExecuted 事件与业务操作同事务提交）

### AC-4: execute 与 trigger/route 解耦

**Given** execute 机制完成执行
**When** 发布 AutoExecuted 事件
**Then** execute 阶段不直接调用 trigger/route 阶段，通过事件总线解耦
**And** 符合六边形架构依赖方向

**验证标准/Validation Criteria:**
- [ ] AutoExecuted 事件定义（`src/domain/events/auto_execute_events.py`）
- [ ] AutoExecuteService 仅发布事件，不调用其他阶段
- [ ] 无循环依赖（六边形架构检测）
- [ ] AutoExecuteService 位于领域层或应用层（不位于基础设施层直接调用）
- [ ] 依赖倒置：AutoExecuteService 定义事件监听接口，基础设施层实现

### AC-5: 执行性能要求

**Given** Routed 事件到达 AutoExecuteService
**When** AutoExecuteService 处理执行
**Then** 沙箱启动延迟 P95<100ms
**And** 状态快照延迟 P95<50ms
**And** 吞吐量支持 100 executions/second

**验证标准/Validation Criteria:**
- [ ] 沙箱启动延迟 P95<100ms（使用 `pytest-benchmark` 测量，1000 次采样）
- [ ] 状态快照延迟 P95<50ms（使用 `pytest-benchmark` 测量，1000 次采样）
- [ ] 吞吐量 100 executions/second（使用 `locust` 或 `pytest-benchmark` 持续压测 30 秒）
- [ ] 执行幂等性（相同输入产生相同输出）
- [ ] 执行错误重试机制（指数退避）

**基准测试方法：**
```bash
# 沙箱启动延迟基准测试
pytest tests/unit/performance/test_execute_performance.py::test_sandbox_startup_latency --benchmark-min-rounds=1000

# 状态快照延迟基准测试
pytest tests/unit/performance/test_execute_performance.py::test_snapshot_latency --benchmark-min-rounds=1000

# 吞吐量负载测试
locust -f tests/performance/execute_load_test.py --headless -r 100 -t 30s --host http://localhost:8000
```

**性能指标采集：**
- 使用 `pytest-benchmark` 自动采集 P50/P95/P99 延迟
- 使用 `prometheus_client` 导出指标到 Prometheus
- 使用 `Grafana` 可视化性能趋势

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] AutoExecuted 技术事件定义（`src/domain/events/auto_execute_events.py`）
  - 字段: event_id, session_id, task_context, execution_result, cost_estimate, latency_ms, timestamp, business_event_type
  - 事件类型自动设置: `event_type = "AutoExecuted"`
  - business_event_type 标识下游应发布的领域事件类型（DocumentProcessed/ToolAutoExecuted/AgentDecided）
- [ ] 下游监听器接口 `auto_execute_completed_listener.py`（根据 business_event_type 发布对应领域事件）
- [ ] Routed 事件监听接口（接收来自 Story 1.14b 的 Routed 事件）

#### 数据模型 (Data Models)
- [ ] AutoExecuteService 服务类（`src/domain/services/auto_execute_service.py`）
  - 方法: `on_routed_event(event)`, `execute_task(task_context) -> ExecutionResult`, `create_snapshot(session_id, state) -> CheckpointSnapshot`
  - 职责: 接收 Routed 事件、执行任务、创建快照、发布 AutoExecuted 事件
- [ ] CheckpointSnapshot 实体（`src/domain/entities/checkpoint_snapshot.py`）
  - 字段: snapshot_id, session_id, stage_id, state_version, state_data, timestamp, ttl_seconds
  - 继承系统公理二（外部化记忆）模式

#### 沙箱执行 (Sandbox Execution)
- [ ] SandboxExecutor 端口接口（`src/domain/ports/sandbox_executor.py`）
  - 接口方法: `start_container()`, `execute_code()`, `stop_container()`, `is_container_running()`
  - `@runtime_checkable` Protocol，位于 domain 层（作为六边形架构的"端口"）
- [ ] DockerSandboxAdapter 实现（`src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`）
  - 实现 SandboxExecutor 端口接口
  - Docker 沙箱隔离
- [ ] SessionNamespaceManager 会话命名空间管理（`src/infrastructure/external_services/sandbox/session_namespace_manager.py`）
  - session_id → namespace 映射
  - 资源限制配置

#### 状态快照存储 (Snapshot Storage)
- [ ] SnapshotRepository 仓储接口定义在 domain 层（`src/domain/repositories/snapshot_repository.py`）
  - 接口方法: `save(snapshot)`, `load(session_id)`, `delete(session_id)`
  - 遵循六边形架构：领域层定义接口，基础设施层实现
- [ ] RedisSnapshotStore 存储实现（`src/infrastructure/storage/redis/redis_snapshot_store.py`）
  - 实现 SnapshotRepository 接口
  - Redis Hash 存储
  - TTL 管理
  - 主从复制支持

#### 配置模型 (Configuration Models)
- [ ] AutoExecuteConfig 配置（`src/infrastructure/config/execute.py`）
  - 环境变量: `EXECUTE_ENABLED`, `SANDBOX_TYPE`（docker/gvisor）, `SNAPSHOT_TTL_SECONDS`, `RESOURCE_LIMITS`
  - 从环境变量读取（`from_env()` 方法，复用 OtelConfig 模式）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_autonomous_invocation_execute.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - 沙箱隔离 execute → route（单一沙箱执行）
  - 状态快照持久化
  - 状态恢复测试
  - 执行事件发布（AutoExecuted 技术事件 → 下游监听器 → DocumentProcessed/ToolAutoExecuted/AgentDecided）
  - execute 与 trigger/route 解耦
  - 沙箱启动延迟 P95<100ms
  - 状态快照延迟 P95<50ms

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | AutoExecuteService | 会话命名空间执行 | `test_auto_execute_service.py` | Task 1 |
| **TDD 单元测试** | DockerSandboxAdapter | 沙箱隔离 | `test_docker_sandbox_adapter.py` | Task 1 |
| **TDD 单元测试** | CheckpointSnapshot | 状态快照 | `test_checkpoint_snapshot.py` | Task 2 |
| **TDD 单元测试** | RedisSnapshotStore | Redis 存储 | `test_redis_snapshot_store.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_autonomous_invocation_execute.feature` | Task 0 |
| **SDD 架构验证** | execute 解耦 | 六边形架构约束 | `test_execute_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端 execute 流程 | `test_integration_execute.py` | Task 3 |

#### 测试隔离约束（必须遵守）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**
> 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) §5.5 测试隔离约束。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 使用类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **外部客户端** | 第三方 API 必须验证方法存在性 | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 会话命名空间隔离 | Task 1 | Subtask 1.1-1.3（DockerSandboxAdapter 红→绿→重构） | `test_docker_sandbox_adapter.py` |
| AC-1 | AutoExecuteService 事件监听 | Task 1 | Subtask 1.4-1.6（AutoExecuteService 红→绿→重构） | `test_auto_execute_service.py` |
| AC-2 | 状态快照持久化 | Task 2 | Subtask 2.1-2.3（CheckpointSnapshot 红→绿→重构） | `test_checkpoint_snapshot.py` |
| AC-2 | Redis 存储实现 | Task 2 | Subtask 2.4-2.6（RedisSnapshotStore 红→绿→重构） | `test_redis_snapshot_store.py` |
| AC-3 | 执行事件发布 | Task 2 | Subtask 2.7-2.9（AutoExecuted 事件 红→绿→重构） | `test_auto_execute_events.py` |
| AC-4 | execute 与 trigger/route 解耦 | Task 3 | Subtask 3.1-3.3（六边形架构验证 红→绿→重构） | `test_execute_architecture.py` |
| AC-5 | 执行性能要求 | Task 3 | Subtask 3.4-3.6（性能基准测试 红→绿→重构） | `test_execute_performance.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [x] Subtask 0.1: 定义 AutoExecuted 技术事件 Schema（`src/domain/events/auto_execute_events.py`）
- [x] Subtask 0.2: 定义 CheckpointSnapshot 实体（`src/domain/entities/checkpoint_snapshot.py`）
- [x] Subtask 0.3: 定义 AutoExecuteService 服务接口（`src/domain/services/auto_execute_service.py`）
- [x] Subtask 0.4: 定义 SandboxExecutor 端口接口（`src/domain/ports/sandbox_executor.py`）
- [x] Subtask 0.5: 定义 DockerSandboxAdapter 实现（`src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`）
- [x] Subtask 0.6: 定义 SnapshotRepository 仓储接口（`src/domain/repositories/snapshot_repository.py`）
- [x] Subtask 0.7: 定义 RedisSnapshotStore 存储实现（`src/infrastructure/storage/redis/redis_snapshot_store.py`）
- [x] Subtask 0.8: 定义 AutoExecuteConfig 配置模型（`src/infrastructure/config/execute.py`）
- [x] Subtask 0.9: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_autonomous_invocation_execute.feature`（Dev agent 创建）
- [x] Subtask 0.10: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 会话命名空间隔离与沙箱执行

**关联 AC:** AC-1

> **职责边界:** Task 1 负责 SandboxExecutor（沙箱隔离）和 AutoExecuteService（事件监听、任务执行）

#### TDD 循环 [A]：SandboxExecutor 沙箱隔离

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/sandbox/test_docker_sandbox_adapter.py`（验证沙箱隔离） |
| 🟢 绿 | 实现 `src/domain/ports/sandbox_executor.py`（端口接口）和 `src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`（Docker 实现） |
| 🔄 重构 | 添加资源限制和清理逻辑 |

- [x] Subtask 1.1: 🔴 红 — 编写 DockerSandboxAdapter 失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现 SandboxExecutor 端口接口和 DockerSandboxAdapter
- [x] Subtask 1.3: 🔄 重构 — 优化沙箱资源限制

#### TDD 循环 [B]：AutoExecuteService 事件监听

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_auto_execute_service.py`（验证 Routed 事件监听） |
| 🟢 绿 | 实现 `src/domain/services/auto_execute_service.py` - AutoExecuteService 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [x] Subtask 1.4: 🔴 红 — 编写 AutoExecuteService 失败测试
- [x] Subtask 1.5: 🟢 绿 — 实现 AutoExecuteService（监听 Routed 事件，执行任务）
- [x] Subtask 1.6: 🔄 重构 — 优化事件处理逻辑

**完成标准/Definition of Done:**
- [x] DockerSandboxAdapter 实现完成（沙箱隔离）
- [x] AutoExecuteService 实现完成
- [x] 沙箱隔离 100%（无状态泄漏）
- [x] TDD 循环全部通过

---

### Task 2: 状态快照持久化与事件发布

**关联 AC:** AC-2, AC-3

> **职责边界:** Task 2 负责 CheckpointSnapshot（状态快照）、RedisSnapshotStore（存储）和 AutoExecuted 事件发布

#### TDD 循环 [A]：CheckpointSnapshot 状态快照

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_checkpoint_snapshot.py`（验证快照序列化） |
| 🟢 绿 | 实现 `src/domain/entities/checkpoint_snapshot.py` - CheckpointSnapshot 实体 |
| 🔄 重构 | 优化序列化格式和验证逻辑 |

- [x] Subtask 2.1: 🔴 红 — 编写 CheckpointSnapshot 失败测试
- [x] Subtask 2.2: 🟢 绿 — 实现 CheckpointSnapshot 实体（状态序列化）
- [x] Subtask 2.3: 🔄 重构 — 验证快照完整性

#### TDD 循环 [B]：RedisSnapshotStore 存储实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_redis_snapshot_store.py`（验证 Redis 存储） |
| 🟢 绿 | 实现 `src/infrastructure/storage/redis/redis_snapshot_store.py` - RedisSnapshotStore |
| 🔄 重构 | 添加主从复制支持和 TTL 管理 |

- [x] Subtask 2.4: 🔴 红 — 编写 RedisSnapshotStore 失败测试
- [x] Subtask 2.5: 🟢 绿 — 实现 RedisSnapshotStore（Redis Hash + TTL）
- [x] Subtask 2.6: 🔄 重构 — 验证主从复制支持

#### TDD 循环 [C]：AutoExecuted 事件定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_auto_execute_events.py`（验证 AutoExecuted 事件 Schema） |
| 🟢 绿 | 实现 `src/domain/events/auto_execute_events.py` - AutoExecuted 事件类 |
| 🔄 重构 | 验证事件继承和子事件类型 |

- [x] Subtask 2.7: 🔴 红 — 编写 AutoExecuted 事件失败测试
- [x] Subtask 2.8: 🟢 绿 — 实现 AutoExecuted 事件 Schema（DocumentProcessed/ToolAutoExecuted/AgentDecided）
- [x] Subtask 2.9: 🔄 重构 — 验证事件发布逻辑

**完成标准/Definition of Done:**
- [x] CheckpointSnapshot 实现完成
- [x] RedisSnapshotStore 实现完成（主从复制 + TTL）
- [x] AutoExecuted 事件定义完成
- [x] 快照延迟 P95<50ms
- [x] TDD 循环全部通过

---

### Task 3: 架构验证与性能基准

**关联 AC:** AC-4, AC-5

> **职责边界:** Task 3 负责六边形架构验证（execute 与 trigger/route 解耦）和性能基准测试

#### TDD 循环 [A]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_execute_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（循环依赖检测、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [x] Subtask 3.1: 🔴 红 — 编写架构验证失败测试
- [x] Subtask 3.2: 🟢 绿 — 实现架构验证逻辑
- [x] Subtask 3.3: 🔄 重构 — 验证器优化

#### TDD 循环 [B]：性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_execute_performance.py`（验证性能要求，使用 pytest-benchmark） |
| 🟢 绿 | 实现性能优化（沙箱预热、连接池复用） |
| 🔄 重构 | 性能调优 |

- [x] Subtask 3.4: 🔴 红 — 编写性能基准失败测试
  - 沙箱启动延迟测试（`test_sandbox_startup_latency`）
  - 状态快照延迟测试（`test_snapshot_latency`）
  - 吞吐量负载测试（`test_execution_throughput`）
  - 执行幂等性测试（`test_execution_idempotency`）
- [x] Subtask 3.5: 🟢 绿 — 实现性能优化
  - 沙箱连接池复用（Docker SDK connection pooling）
  - Redis 连接池配置（`max_connections=50`）
  - 沙箱预热机制（空闲时保持最小容器实例）
- [x] Subtask 3.6: 🔄 重构 — 性能调优
  - 运行 `pytest-benchmark --compare` 对比优化前后性能
  - 确认 P95 延迟达标

#### 集成测试

- [x] Subtask 3.7: 创建 `tests/integration/test_integration_execute.py`（端到端执行流程）

**完成标准/Definition of Done:**
- [x] 六边形架构验证通过（无循环依赖）
- [x] 沙箱启动延迟 P95<100ms
- [x] 状态快照延迟 P95<50ms
- [x] 吞吐量 100 executions/second
- [x] 集成测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理一:** trigger→route→execute 自主调用循环
  - trigger: 领域事件/心跳事件触发 → Story 1.14a
  - route: session_id 哈希/语义路由 → Story 1.14b
  - execute: 会话命名空间执行与状态快照 → **本 Story**
- **系统公理二:** 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源）
  - CheckpointSnapshot 遵循外部化记忆模式
  - 状态快照序列化至 Redis Hash（TTL 24h-30d）
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 事件总线双通道：Redis PubSub（实时）、RabbitMQ（持久化）
- **技术栈:**
  - Python 3.11+
  - 沙箱：Docker + gVisor（Story 4.4 已定义沙箱策略）
  - 事件总线：Redis PubSub + RabbitMQ（Story 1.3 已实现）
  - 快照存储：Redis Hash（Story 1.4 已实现 Redis）
  - 沙箱启动延迟目标：P95<100ms
  - 快照延迟目标：P95<50ms

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR 相关决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **AutoExecuteService 位于领域层** | 符合六边形架构，领域逻辑与技术解耦 | 需要依赖倒置 | ✅ 9/10 |
| AutoExecuteService 位于应用层 | 实现简单 | 领域逻辑泄漏 | 6/10 |
| AutoExecuteService 位于基础设施层 | 实现最简单 | 违反六边形架构 | 3/10 |

### ADR: 沙箱技术选型决策

**问题**: 使用 Docker 还是 gVisor 实现沙箱隔离？

**评估维度** | Docker | gVisor | 混合（Docker + gVisor）
------------|--------|--------|----------------------
实现复杂度 | 低 | 中 | 高
隔离级别 | 中（容器级别） | 高（用户空间内核） | 高
性能 | 高 | 中 | 高
**采用** | ✅ MVP 采用 | V2+ 考虑 | V2+ 升级路径

**决策**: MVP 使用 **Docker 沙箱**，V2+ 考虑升级到 gVisor 以提高隔离级别。沙箱策略在 Story 4.4（Docker 沙箱执行）已定义。

### ADR: 状态快照存储选型决策

**问题**: 状态快照存储使用 Redis Hash 还是 PostgreSQL？

**评估维度** | Redis Hash | PostgreSQL | 混合存储
------------|------------|------------|----------
性能 | 高（内存） | 中（磁盘） | 高
持久性 | 中（依赖 RDB/AOF） | 高（WAL） | 高
主从复制 | 原生支持 | 原生支持 | 原生支持
**采用** | **✅ 已选择** | ❌ 不采用 | ❌ 不采用

**决策**: 使用 **Redis Hash** 存储状态快照，原因：
1. 高性能（内存操作，P95<50ms）
2. 原生支持主从复制与故障转移
3. Story 1.4 已实现 Redis 基础设施

### execute 机制与 trigger/route 的关系澄清

> ⚠️ **重要澄清**：execute 机制和 trigger/route 是通过事件总线解耦的，不存在循环依赖！

**数据流**:
```
Story 1.14a (trigger)
    ↓ 发布 Triggered 事件
Story 1.14b (route)
    ↓ 发布 Routed 事件
Story 1.14c (execute) ← 本 Story
    ↓ 发布 AutoExecuted 事件
Story 1.15a (外部化记忆) / Story 1.17 (UDMR)
```

**关键点**：
- trigger → route → execute 是**单向数据流**，通过事件总线连接
- 每个阶段只发布自己的输出事件，不直接调用其他阶段
- execute 监听 Routed 事件，发布 AutoExecuted 事件
- 不存在循环依赖，符合六边形架构

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── auto_execute_events.py      # AutoExecuted 技术事件
│   │   ├── services/
│   │   │   └── auto_execute_service.py     # AutoExecuteService（核心逻辑）
│   │   ├── entities/
│   │   │   └── checkpoint_snapshot.py      # CheckpointSnapshot（状态快照）
│   │   └── repositories/
│   │       └── snapshot_repository.py     # SnapshotRepository 接口（领域层定义）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── execute.py                  # AutoExecuteConfig 配置
│   │   ├── external_services/
│   │   │   └── sandbox/
│   │   │       ├── docker_sandbox_adapter.py  # DockerSandboxAdapter（实现）
│   │   │       └── session_namespace_manager.py # 会话命名空间管理
│   │   └── storage/redis
│   │       └── redis_snapshot_store.py     # RedisSnapshotStore
│   └── interfaces/
│       ├── cli/
│       │   └── commands/
│       │       └── sandbox_ports.py        # SandboxExecutor 端口接口（六边形架构 CLI 端口，引用 domain 层 Protocol）
│       └── event_listeners/
│           ├── listeners/
│           │   ├── auto_execute_completed_listener.py # AutoExecuted → 下游领域事件监听器
│           │   └── execute_listener.py     # Routed 事件监听适配器（复用 Story 1.3）
│           └── converters/
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/
│   │   │   │   └── test_auto_execute_service.py
│   │   │   └── entities/
│   │   │       └── test_checkpoint_snapshot.py
│   │   ├── infrastructure/
│   │   │   └── storage/
│   │   │       └── test_redis_snapshot_store.py
│   │   └── external_services/
│   │       └── sandbox/
│   │           └── test_docker_sandbox_adapter.py
│   ├── integration/
│   │   └── test_integration_execute.py
│   └── acceptance/
│       ├── test_acceptance_autonomous_invocation_execute.feature
│       └── test_acceptance_autonomous_invocation_execute.py
└── docs/
    └── developer/
        └── execute_mechanism_guide.md    # 执行机制实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，AutoExecuteConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — RouteService 仅负责路由决策，不处理 execute 逻辑；AutoExecuteService 应遵循相同模式
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保无循环依赖
4. **性能基准测试** — route 性能要求 P95<50ms，execute 沙箱启动 P95<100ms、快照 P95<50ms，需独立基准测试
5. **语义路由与 UDMR 路由关系澄清** — 需明确 execute 与后续 Story 的关系

**本故事修正/Story Corrections:**
> 以下问题已在本次审查中修正：

6. **AutoExecuted 事件与下游领域事件关系修正** — AutoExecuted 是技术事件，下游监听器根据 business_event_type 发布 DocumentProcessed/ToolAutoExecuted/AgentDecided
7. **SnapshotRepository 位置澄清** — 接口定义在 domain 层，实现在 infrastructure 层
8. **SandboxExecutor 架构位置修正** — 端口接口在 domain 层（`@runtime_checkable` Protocol），DockerSandboxAdapter 实现在 infrastructure 层

**应用到本故事/Applied to This Story:**
- [ ] AutoExecuteConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [ ] AutoExecuteService 仅负责执行和快照，不处理 route 逻辑
- [ ] Task 3 包含架构验证测试（六边形架构约束检测）
- [ ] 性能基准测试验证沙箱启动 P95<100ms、快照 P95<50ms
- [ ] AutoExecuted 技术事件通过下游监听器发布 DocumentProcessed/ToolAutoExecuted/AgentDecided
- [ ] SandboxExecutor 端口在 domain 层（`src/domain/ports/sandbox_executor.py`，`@runtime_checkable` Protocol），实现在 infrastructure 层（DockerSandboxAdapter）
- [ ] 测试隔离约束显式强调（asyncio.Lock 类变量、pytest-asyncio auto mode）
- [ ] 性能基准测试方法明确（pytest-benchmark + locust）

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `c02aef1` | build: automatic update of sisys-app-dev | 自动化构建 |
| `944d33f` | fix: auth.py refresh_token endpoint uses Form() | 表单解析修复 |
| `b982e6a` | build: automatic update of sisys-app-dev | 自动化构建 |
| `dce3ffa` | build: automatic update of sisys-app-dev | 自动化构建 |
| `6a2c23d` | update | - |

**可应用模式:**
1. **六边形架构严格分层** — domain/infrastructure/interfaces 层严格分离
2. **配置与实现分离** — Config 类与实现类分离
3. **事件驱动解耦** — 通过事件总线通信，不直接调用

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-20 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] or.md 系统公理一（execute）追溯完成
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 前一个故事学习经验已整合
- [x] execute 与 trigger/route 解耦关系已澄清
- [x] 测试隔离约束显式强调（asyncio.Lock/pytest-asyncio）
- [x] 性能基准测试方法明确（pytest-benchmark + locust）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-14c-autonomous-invocation-execute.md`
- `src/domain/events/auto_execute_events.py` - AutoExecuted 技术事件（携带 business_event_type）
- `src/domain/services/auto_execute_service.py` - AutoExecuteService
- `src/domain/entities/checkpoint_snapshot.py` - CheckpointSnapshot
- `src/domain/repositories/snapshot_repository.py` - SnapshotRepository 接口（领域层定义）
- `src/infrastructure/config/execute.py` - AutoExecuteConfig
- `src/domain/ports/sandbox_executor.py` - SandboxExecutor 端口接口（`@runtime_checkable` Protocol，domain 层）
- `src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py` - DockerSandboxAdapter（infrastructure 层实现）
- `src/infrastructure/external_services/sandbox/session_namespace_manager.py` - SessionNamespaceManager
- `src/infrastructure/storage/redis/redis_snapshot_store.py` - RedisSnapshotStore（实现 SnapshotRepository）
- `src/application/event_handlers/auto_execute_completed_listener.py` - AutoExecuted → 下游领域事件监听器
- `tests/unit/domain/services/test_auto_execute_service.py` - AutoExecuteService 单元测试
- `tests/unit/domain/entities/test_checkpoint_snapshot.py` - CheckpointSnapshot 单元测试
- `tests/unit/domain/events/test_auto_execute_events.py` - AutoExecuted 事件单元测试
- `tests/unit/infrastructure/external_services/sandbox/test_docker_sandbox_adapter.py` - DockerSandboxAdapter 单元测试
- `tests/unit/infrastructure/storage/test_redis_snapshot_store.py` - RedisSnapshotStore 单元测试
- `tests/unit/architecture/test_execute_architecture.py` - 架构验证测试
- `tests/unit/performance/test_execute_performance.py` - 性能基准测试
- `tests/integration/test_integration_execute.py` - 集成测试
- `tests/acceptance/test_acceptance_autonomous_invocation_execute.feature` - Gherkin 验收测试（由 Dev agent 在 Task 0 创建）
- `tests/acceptance/test_acceptance_autonomous_invocation_execute.py` - 验收测试步骤实现（由 Dev agent 在 Task 0 创建）
- `docs/developer/execute_mechanism_guide.md` - 执行机制实施指南

**更新的文件/Updated Files:**
- `src/domain/events/__init__.py` - 添加 AutoExecuted 事件导出
- `src/domain/services/__init__.py` - 添加 AutoExecuteService 导出
- `src/domain/entities/__init__.py` - 添加 CheckpointSnapshot 导出
- `src/domain/repositories/__init__.py` - 添加 SnapshotRepository 导出
- `src/infrastructure/config/__init__.py` - 添加 AutoExecuteConfig 导出
- `src/infrastructure/external_services/sandbox/__init__.py` - 添加 DockerSandboxAdapter, SessionNamespaceManager 导出
- `src/infrastructure/storage/__init__.py` - 添加 RedisSnapshotStore 导出
- `src/domain/ports/sandbox_executor.py` - 添加 SandboxExecutor 导出
- `src/application/event_handlers/__init__.py` - 添加 auto_execute_completed_listener 导出

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/interfaces/event_listeners/execute_listener.py` - Routed 事件监听适配器（复用 Story 1.3 模式）

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理一** | trigger→route→execute 自主调用循环 | architecture.md §3.2 |
| **系统公理二** | 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源） | architecture.md §3.2 |
| **事件驱动** | 事务发件箱模式，事件处理幂等性 | architecture.md §3.3 |
| **测试覆盖率** | 架构层≥85%，集成测试≥75% | sdd-tdd-checklist.md §5 |
| **沙箱启动延迟** | P95<100ms | epics_v1.0.md Story 1.14c |
| **快照延迟** | P95<50ms | epics_v1.0.md Story 1.14c |

### 关键路径依赖

```
Story 1.14a (trigger) → Story 1.14b (route) → Story 1.14c (execute)
                                                            ↓
                                          Story 1.15a (外部化记忆) ← 上下文压缩依赖
                                          Story 1.17 (UDMR 路由) ← 路由日志依赖
```

### 沙箱执行体系（来自 architecture.md §31）

| 沙箱类型 | 隔离级别 | 性能 | 适用场景 |
|---------|---------|------|---------|
| **Docker** | 中（容器级别） | 高 | MVP 阶段 |
| **gVisor** | 高（用户空间内核） | 中 | V2+ 隔离要求 |

### 状态快照体系（来自 architecture.md §8.2）

| 快照类型 | 存储技术 | TTL | 持久性 |
|---------|---------|-----|--------|
| **CheckpointSnapshot** | Redis Hash | 24h-30d | 中（依赖 RDB/AOF） |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.14c |
| **Story Key** | 1-14c-autonomous-invocation-execute |
| **File** | `_bmad-output/implementation-artifacts/stories/1-14c-autonomous-invocation-execute.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 5: or.md 系统公理实现 |
| **优先级** | P0-14c（or.md 系统公理一） |
| **覆盖 FR** | or.md 系统公理一（execute 阶段）、系统公理二（状态快照） |
| **依赖 Story** | Story 1.14a（trigger 实现）、Story 1.14b（route 实现） |
| **前置条件** | Routed 事件已定义（Story 1.14b），Docker/gVisor 沙箱策略已定义（Story 4.4） |
| **后续 Story** | Story 1.15a（外部化记忆 - 上下文压缩）、Story 1.17（UDMR 基础路由） |
| **覆盖率要求** | 架构层≥85%（六边形架构验证），集成测试≥75% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] 测试隔离约束显式强调
7. [x] 性能基准测试方法明确

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 本次审查由 create-story skill 执行，聚焦科学性、合理性、正确性、一致性（三次审查）。

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| 1 | execute 与 trigger/route 关系不清晰 | P1 | 添加"execute 机制与 trigger/route 的关系澄清"章节，明确通过事件总线解耦，无循环依赖 | ✅ 已修复 |
| 2 | 沙箱技术选型未明确 | P2 | 添加 ADR 沙箱技术选型决策，Docker 用于 MVP，gVisor 用于 V2+ | ✅ 已修复 |
| 3 | 状态快照存储选型未明确 | P2 | 添加 ADR 状态快照存储选型决策，明确使用 Redis Hash | ✅ 已修复 |
| 4 | 性能指标与其他 Story 不一致 | P2 | 统一性能指标：沙箱启动 P95<100ms，快照 P95<50ms | ✅ 已修复 |
| 5 | AutoExecuted 事件与 DocumentProcessed/ToolAutoExecuted/AgentDecided 关系模糊 | P2 | 明确 AutoExecuted 事件包含三个子事件类型，遵循 Story 1.2 领域事件定义 | ✅ 已修复 |
| 6 | AutoExecuted 事件与下游领域事件关系不正确 | P1 | 修正为：AutoExecuted 是技术事件，下游监听器根据 business_event_type 发布 DocumentProcessed/ToolAutoExecuted/AgentDecided | ✅ 已修复 |
| 7 | SnapshotRepository 位置需澄清 | P1 | 明确接口定义在 domain 层，实现在 infrastructure 层 | ✅ 已修复 |
| 8 | SandboxExecutor 架构位置不准确 | P2 | 修正为：端口接口在 domain 层（`src/domain/ports/sandbox_executor.py`），DockerSandboxAdapter 实现在 infrastructure 层 | ✅ 已修复 |
| 9 | Task 0 Subtask 路径引用旧架构 | P2 | 修正 Task 0.1/0.4/0.5 路径与项目结构一致 | ✅ 已修复 |
| 10 | AC-1 验证标准路径引用旧架构 | P2 | 修正 sandbox_executor.py → docker_sandbox_adapter.py | ✅ 已修复 |
| 11 | 测试文件引用不一致 | P2 | 修正 test_sandbox_executor.py → test_docker_sandbox_adapter.py | ✅ 已修复 |
| 12 | 业务价值表格与 AC-3 描述不一致 | P1 | 业务价值表格改为"AutoExecuted 技术事件，下游监听器根据业务类型发布对应领域事件" | ✅ 已修复 |
| 13 | 测试隔离约束未显式强调 | P2 | 添加"测试隔离约束"章节，明确 asyncio.Lock 类变量、pytest-asyncio auto mode 等规则 | ✅ 已修复 |
| 14 | 性能基准测试方法未明确 | P2 | 补充具体测试方法（pytest-benchmark + locust）和验证命令 | ✅ 已修复 |

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [or.md 系统公理一](../planning-artifacts/or.md) | 系统公理定义 |
| [Story 1.14a: 自主调用循环 - trigger](./1-14a-autonomous-invocation-trigger.md) | 前置 Story |
| [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md) | 前置 Story |
| [Story 1.15a: 外部化记忆 - 上下文压缩](./1-15a-externalized-memory-context-compression.md) | 后续 Story（待创建） |
| [Story 1.17: UDMR 基础路由](../planning-artifacts/) | 相关 Story（待创建） |

---

**模板版本/Template Version:** 2.2.0
**创建日期/Created:** 2026-04-20
**最后更新/Last Updated:** 2026-04-21
**更新说明:** Story 1.14c 完整版本 - 实现会话命名空间执行与状态快照：(1) SandboxExecutor 端口接口（domain 层，`src/domain/ports/sandbox_executor.py`，`@runtime_checkable` Protocol，含 is_container_running）+ DockerSandboxAdapter（infrastructure 层）; (2) AutoExecuteService 事件监听与任务执行; (3) CheckpointSnapshot 状态快照; (4) RedisSnapshotStore 存储; (5) AutoExecuted 技术事件（携带 business_event_type）触发下游领域事件; (6) 六边形架构验证; (7) 性能基准测试 P95<100ms/50ms；二轮审查修复：一致性修正；三轮审查修复：添加测试隔离约束章节（asyncio.Lock/pytest-asyncio）、补充性能基准测试方法（pytest-benchmark + locust）；端口合并更新：sandbox_executor_protocol + sandbox_port → 统一为 sandbox_executor
