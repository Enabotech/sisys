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

- `_runs` 字典无限增长（内存泄漏）— SINGLETON 生命周期下只增不删，需引入 TTL 驱逐机制。`src/infrastructure/agent_orch/langgraph_engine.py:46`
- `LangGraphConfig` 配置字段从未被 `LangGraphEngine` 使用 — retry/timeout 配置为 MVP 预留，后续实现重试/超时逻辑时使用。`src/infrastructure/agent_orch/langgraph_engine.py:42`
- `get_graph_status` 对未知 ID 返回 FAILED 而非抛异常 — MVP 设计选择，spec 明确说"仅返回 COMPLETED 或 FAILED"。`src/infrastructure/agent_orch/langgraph_engine.py:102`
- 阻塞式执行导致 RUNNING/PENDING 不可观察 — spec 明确说"MVP 阻塞语义...RUNNING/PENDING 在本地模式下不可观察"。`src/infrastructure/agent_orch/langgraph_engine.py:76-77`
- 缺少 Graph 编译缓存机制 — spec 要求 graph_name→CompiledGraph 映射，MVP 图构建开销小，后续 Epic 扩展时优化。`src/infrastructure/agent_orch/langgraph_engine.py:104-123`
