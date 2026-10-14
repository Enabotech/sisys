# 方议案 D11：Outbox 毒消息终态机制（dead-letter）设计草案

> **状态**：待立项评审（立项范围草案见 §6）
> **来源**：Story 5-1 审查周期 R2 登记→R3 收敛→R4 扩为六项→R5+清偿轮收窄（见 §1 状态表）
> **关键洞察**：实体层 `OutboxEntity.mark_archived()` 终态迁移**已实现且有测试钉住**（`tests/unit/infrastructure/messaging/outbox/test_outbox_processor.py::test_mark_archived_from_failed`），PG 模型 CheckConstraint 亦允许 `archived`——缺的只是 **PG 仓储方法 + poller 终态接线 + 运维可观测面**。本方案是补全既有状态机的「最后一公里」，不是新建机制。

---

## 1. 六项收敛范围现状表（2026-10-14 清偿轮后）

| # | 子项 | 状态 | 处置记录 |
|---|------|------|---------|
| ② | InMemory `get_unpublished` 无毒隔离的端口语义分叉 | ✅ **已清偿**（2026-10-14） | 逐条隔离+warning 跳过，对齐 PG 侧语义 |
| ④ | `process_one` attempt-0 对全新 pending 行伪 mark_pending（浪费重试预算+伪 warning） | ✅ **已清偿**（2026-10-14） | poller 层幂等（严格状态机契约保留——`test_pending_cannot_go_to_pending` 继续钉死，幂等在调用方实现） |
| ⑤ | `_mark_failed_entity` 未截断 error_message | ✅ **已清偿**（2026-10-14） | `error[:_ERROR_MESSAGE_MAX_LENGTH]`，与公开方法对称 |
| ⑥ | `AuditOutboxModel.mark_failed` 同款未截断 | ✅ **已清偿**（2026-10-14） | 模块级常量 + 截断（`tests/unit/.../test_audit_outbox_model.py` 钉住） |
| ① | 超限行无终态迁移：SELECT 过滤（`retry_count < max_retries`）后惰性滞留——零日志监控盲区、运维 SQL 是唯一恢复路径 | ❌ **待立项**（本方案主体） | R3-F1 已消除队头阻塞与写放大，残余为终态语义与可观测性 |
| ③ | `PostgresDeadLetterQueue.dequeue` 同款队头阻塞形态（`from_dict` 在 try 外 + status 先行改标） | ❌ **待立项**（随本方案同批） | 消费侧 DLQ 与发布侧 archived 终态的语义对齐 |

## 2. 现状机制（问题陈述）

### 2.1 发布侧（event_outbox）生命周期现状

```
pending ──发布成功──> published ──cleanup(30d)──> 删除
   │ 发布失败
   ▼
failed(retry_count++) ──mark_pending(<max)──> pending（重试）
   │ retry_count ≥ max_retries
   ▼
[SELECT 过滤后不再被选中] ← 惰性滞留：状态永远停在 failed
   - 无终态迁移（实体有 mark_archived 但 PG 仓储/poller 零调用方）
   - 零日志零指标（R3-F1 过滤后连 warning 都不再产生）
   - 唯一恢复路径 = 运维 SQL（UPDATE event_outbox SET retry_count=0 WHERE ...）
   - cleanup 只清 published，超限 failed 行永不清除 → 表无限增长
```

**运维风险**：①RabbitMQ 中断 ≈10-20 秒即耗尽默认 max_retries=3（1s/2s/4s 退避）——恢复后这批事件**静默丢失**（无告警无日志无重放入口）；②毒 payload 行永久占用表空间。

### 2.2 消费侧（dead_letter_queue）现状

`postgres_dead_letter_queue.dequeue`（:170-190）`from_dict` 在 try 外——单条畸形历史行会阻塞队头（与发布侧 R2 修复前同构）；且其语义定位（消费失败兜底）与发布侧超限事件（发布失败耗尽）**分属两个不衔接的孤岛**。

## 3. 方案对比

### 方案 A：archived 终态补全（复用实体既有状态机，**推荐**）

在既有状态机上补「最后一公里」：超限行迁移 `archived`（终态、保留 payload 供追溯与人工重放）。

**触发点设计（推荐 get_unpublished 内联迁移）**：
```python
# outbox_repository.get_unpublished 的毒隔离/超限分支
if model.retry_count >= model.max_retries:
    # 终态迁移：耗尽重试的行归档（保留 payload 供追溯/人工重放）
    await self._mark_archived_entity(model)   # 新增内部方法（复用实体语义，写 PG）
    logger.error("Outbox 事件重试耗尽归档: event_id=%s retries=%d error=%s", ...)
```
- 毒 payload 行：反序列化失败即耗尽语义（静态垃圾）→ 当前轮已 mark_failed 递增计数，达到上限后下一轮 SELECT 前仍会被选中一次（filter 在 SELECT）……**细节**：SELECT 过滤 `retry_count < max` 使毒行在达到上限后不再被选中——迁移窗口须在「最后一次被选中」时执行。实现选择：SELECT 放宽为「pending/failed 全量」+ Python 侧分流（未超限正常处理 / 超限即归档）——**回退 R3-F1 的 SQL 过滤改为应用层过滤**，换取终态迁移的执行窗口；SQL 过滤的空批早退语义由应用层 `if not selectable: return []` 等价保持
- 发布失败行（非毒）：poller `process_one` 重试耗尽处（`mark_failed` 后检查 `retry_count >= max_retries`）迁移 archived + ERROR 日志（可告警）

**配套（必须同批）**：
1. **重放入口**：`requeue(event_id)` 仓储方法（archived → pending，清零 retry_count/error_message）——供运维 API/CLI 调用，替代裸 SQL；实体层需补 `archived → pending` 迁移（当前状态机 archived 是死终态，需评审确认放开该迁移——防误重放的守卫：仅限显式 requeue 调用）
2. **巡检面**：`count_by_status()` 仓储查询（pending/failed/archived 计数）+ CLI `sisys-agent outbox status`（或挂 metrics 端口）——运维 SQL 巡检的正式替代
3. **cleanup 扩展**：`cleanup_old_published_records` 增加可选 archived 清理（默认保留 90 天）

- ✅ 改动面可控：仓储 +2 方法、poller 1 处接线、get_unpublished 分流重构、状态机放开 1 条迁移；实体状态机/CheckConstraint/既有测试零变更
- ✅ 与实体设计意图一致（archived 本就是为此设计）
- ⚠️ 状态机语义变化点需评审：archived 从「死终态」变「可显式 requeue」（严格性由 requeue 唯一入口守卫）

### 方案 B：DLQ 表统一（发布超限行搬运至 dead_letter_queue）

超限行从 event_outbox 删除并插入 dead_letter_queue（复用既有 DLQ 表与消费侧机制）。

- ✅ 主表零滞留；DLQ 已有基础设施
- ❌ 跨表搬运破坏事务边界（同事务 INSERT+DELETE 可行但复杂化 session 语义）；事件「原始落库上下文」（created_at 排序、与业务事务的关联）在搬运中受损
- ❌ DLQ 现有语义是「消费失败兜底」——混入「发布失败耗尽」造成一张表两种生命周期，排障心智负担高
- ❌ dequeue 自身的队头阻塞（子项③）未解决前，把更多行导入 DLQ 是放大风险

### 方案 C：仅加巡检面，不做终态迁移（最小改动）

保持惰性滞留，补 `count_by_status()` 巡检 + 文档化运维 SQL 重放手册。

- ✅ 半天工作量
- ❌ 不解决表无限增长与静默丢失；巡检只能发现不能处置；运维 SQL 仍是唯一恢复路径（与本方案立项动机相悖）

## 4. 推荐组合

**方案 A 为主体 + 子项③（DLQ dequeue 毒隔离）同批修复**（dequeue 逐条 try/except + 畸形行跳过计数，形态平移 5-1 R2-F1 的 PG 侧修法）。

## 5. 验收标准要点（供立项 Story 引用）

1. 超限发布失败行：最后失败周期内迁移 archived + ERROR 日志含 event_id/retries/error（可告警分拣）
2. 毒 payload 行：达到重试上限后迁移 archived，不再被 SELECT 选中（回归断言 R3-F1 白盒用例语义不回退）
3. `requeue(event_id)`：archived → pending 成功且 retry_count 清零；pending/failed/published 状态调用被状态机拒绝
4. `count_by_status()`：三态计数正确（集成测试真实 PG）
5. 无毒行时 get_unpublished 行为与现状逐字等价（合法路径零回归）
6. DLQ dequeue：单条畸形行跳过不阻塞（+计数日志），合法行正常出队
7. 全量回归：outbox 全树 + 5-1 验收（agent_instantiation 含 outbox 真实链路冒烟）

## 6. 立项范围草案

| 切分 | 内容 | 预估 |
|------|------|------|
| 微 Story D11-a | 子项③ DLQ dequeue 毒隔离 + 巡检面 `count_by_status()`（无状态机变更，可先行） | 0.5 天 |
| Story D11-b | 方案 A 主体：archived 终态迁移（get_unpublished 分流 + poller 接线）+ requeue + 状态机迁移评审 + cleanup 扩展 | 2 天（含 PG 集成验证——**前置：本地 PG 认证环境修复**，当前 5433 连接拒绝） |
| 联动 | sprint-status 增条目；D11 台账分两次核销；运维手册（README 用户面不写，落 deploy/ 文档） | — |

**风险与前置**：
- 本地 PG（5433）认证失败是 D11-b 集成验证阻塞项——需先修复开发环境（.env PG 凭据或容器）
- `archived → pending` 迁移放开需架构评审确认（本方案 §3-A 已给守卫设计）
- RabbitMQ 消费方 Story（deferred-work「RabbitMQ 消费方」条目）与本方案存在时序耦合：requeue 的价值在消费方上线后才完整——D11-b 可先行，requeue 消费面随消费方 Story 补充
