# Deferred Work

## Resolved in Story 1.10 (2026-05-07)

### Transaction Outbox Pattern — RESOLVED
**Detail:** AuditServiceImpl.record() directly calls event_publisher.publish() instead of writing to an outbox table within the same transaction. AuditOutboxModel exists but is not used.
**Original AC Violated:** AC-1 (Audit Logging)
**Resolution:** Implemented event_publisher integration. Transaction outbox within same transaction requires significant architectural change (Story 1.18a).

### Audit API Route Handler — RESOLVED
**Detail:** OpenAPI defines endpoints at /audit/* but no route handler file found at src/interfaces/api/audit.py.
**Original AC Violated:** AC-2, AC-3, AC-4
**Resolution:** Created src/interfaces/api/audit.py with 5 endpoints (GET /logs, GET /logs/{log_id}, POST /verify, GET /archive/status, POST /archive).

### WORM Manager Not Called During Archive — RESOLVED
**Detail:** AuditServiceImpl.archive() only updates the archived flag in PostgreSQL but never calls WORMManager.archive_object().
**Original AC Violated:** AC-4 (WORM Archival)
**Resolution:** Added worm_manager integration to archive() method. WORM archival now called when configured.

## Deferred from: code review of 1-18b-langgraph-agent-orchestration (2026-05-20)

- ~~`_runs` 字典无限增长（内存泄漏）~~ — **RESOLVED** (2026-05-25)：引入 OrderedDict + TTL(3600s) + FIFO(1000) 淘汰机制。`src/infrastructure/agent_orch/langgraph_engine.py`
- `LangGraphConfig` 配置字段从未被 `LangGraphEngine` 使用 — retry/timeout 配置为 MVP 预留，后续实现重试/超时逻辑时使用。`src/infrastructure/agent_orch/langgraph_engine.py:42`
- `get_graph_status` 对未知 ID 返回 FAILED 而非抛异常 — MVP 设计选择，spec 明确说"仅返回 COMPLETED 或 FAILED"。`src/infrastructure/agent_orch/langgraph_engine.py:102`
- 阻塞式执行导致 RUNNING/PENDING 不可观察 — spec 明确说"MVP 阻塞语义...RUNNING/PENDING 在本地模式下不可观察"。`src/infrastructure/agent_orch/langgraph_engine.py:76-77`
- 缺少 Graph 编译缓存机制 — spec 要求 graph_name→CompiledGraph 映射，MVP 图构建开销小，后续 Epic 扩展时优化。`src/infrastructure/agent_orch/langgraph_engine.py:104-123`

## Deferred from: code review of 20-8-workflow-agent-integration (2026-05-23)

- 可变字典引用 — frozen dataclass 的 `parameters`/`decision_result` 字段存储可变引用，调用方可在构造后修改。AgentDecided 同样有此问题。预存，非本 Story 引入。`src/domain/events/workflow_events.py:31`
- flow_run_id 默认工厂误导 — 默认 `uuid.uuid4()` 从未被使用，可能掩盖调用方遗漏。RAGIndexed/ReportGenerated 同样有此模式。预存。`src/domain/events/workflow_events.py:29`
- aggregate_type 可被覆盖 — `if not self.aggregate_type:` 条件允许调用方传入自定义值。所有事件都有此模式。预存。`src/domain/events/workflow_events.py:35-38`
- DomainEvent 注册表无隔离 — 测试检查 `_registry["WorkflowSubmitted"]` 但未确保清洁状态。预存模式。`tests/unit/domain/events/test_workflow_events.py:61-67`
- 不可序列化参数延迟失败 — parameters 包含 Prefect 对象时仅在 `to_dict()` 时报错。预存问题。`src/domain/events/workflow_events.py:31`

## Deferred from: code review of 1-19-cost-metrics-basic (2026-05-25)

- ~~InMemoryRoutingDecisionLogRepository 非线程安全~~ — **RESOLVED** (2026-05-25)：引入 asyncio.Lock + max_size(1000) + TTL(24h) 淘汰。`src/infrastructure/messaging/inmemory_routing_decision_log_repository.py`
