# Story 91.2: Outbox 毒消息终态机制（archived 终态迁移 + requeue 入口）

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 来源：5-1 代码审查周期留项 D11 残余①（proposal-d11 §6 切分的 D11-b）。
> **前置依赖：本地 PG 环境修复**（当前 5433 认证失败，集成验证阻塞项）。

---

## 📖 Story 描述

**As a** 平台运维工程师,
**I want** Outbox 重试耗尽的事件迁移至 archived 终态并提供 requeue 重放入口与巡检消费,
**So that** 毒消息/发布失败耗尽事件不再静默滞留（零日志零恢复路径），事件可追溯、可人工重放、可观测。

### 业务价值

- **闭环 R3-F1 的语义残余**：SELECT 过滤（`retry_count < max_retries`）消除了队头阻塞，但超限行停留在 failed 惰性滞留态——零日志监控盲区、运维 SQL 是唯一恢复路径、表无限增长（cleanup 只清 published）
- **补全既有状态机的最后一公里**：实体层 `OutboxEntity.mark_archived()` **已实现且有测试钉住**（failed→archived 终态）；PG 模型 CheckConstraint 已允许 archived——缺的只是 PG 仓储方法 + poller 终态接线 + requeue + 巡检消费（`count_by_status` 已由 D11-a 交付）
- **审计合规**：RELIABLE 通道事件（审计合规型）从「静默丢失」变为「archived 可追溯 + 显式重放」

### 立项依据

- 设计方案：`_bmad-output/implementation-artifacts/proposals/proposal-d11-outbox-dead-letter.md`（方案 A archived 终态补全——三方案对比已裁定；§5 验收标准 7 条；§6 D11-b 范围定义）
- 前序交付：D11-a 已落地 DLQ dequeue 毒隔离 + `count_by_status()` 巡检（2026-10-15，commit c6f1d02a）
- 实测风险基线：RabbitMQ 中断 ≈10-20 秒即耗尽默认 max_retries=3（1s/2s/4s 退避）——恢复后该批事件静默丢失

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 超限行 archived 终态迁移

**Given** Outbox 行重试耗尽（毒 payload 反序列化失败达到上限 / 发布失败 retry_count ≥ max_retries）
**When** 迁移窗口到达（get_unpublished 选中或 poller 终局）
**Then** 行迁移至 `archived` 终态并产生 ERROR 级日志（含 event_id/retries/error，可告警分拣）

**验证标准:**
- [ ] 毒 payload 行：反序列化失败计数达上限后迁移 archived（R3-F1 白盒断言语义不回退——合法行仍正常返回）
- [ ] 发布失败行：poller `process_one` 重试耗尽处（mark_failed 后）迁移 archived + ERROR 日志
- [ ] 实体状态机沿用既有 `mark_archived()`（failed→archived，非法迁移抛 InvalidStateTransitionError）——零状态机语义变化（除 AC-2 的 requeue 迁移）

### AC-2: requeue 重放入口

**Given** 行处于 archived 终态
**When** 调用 `requeue(event_id)`
**Then** archived → pending 迁移成功，retry_count 清零、error_message 清空

**验证标准:**
- [ ] 实体层补 archived → pending 迁移（**状态机评审点**：archived 从死终态变为可显式 requeue——唯一入口守卫，防误重放；评审通过后实施）
- [ ] PG 仓储 `requeue(event_id)`：archived 行重置为 pending（retry_count=0/error_message=None）；非 archived 状态调用抛 InvalidStateTransitionError
- [ ] requeue 后行重新进入 get_unpublished 选择集（集成验证）

### AC-3: cleanup 扩展与巡检消费

**验证标准:**
- [ ] `cleanup_old_published_records` 扩展可选 archived 清理（默认保留 90 天，参数化）
- [ ] `count_by_status()`（D11-a 已交付）集成验证：archived 计数正确
- [ ] 巡检消费入口：CLI 命令（如 `sisys-agent outbox status`）或 metrics 端点暴露各状态计数（**形态裁定留 Task 0**——倾向 CLI，零部署依赖）

### AC-4: 无毒路径零回归

**Given** 无毒行/无超限行的正常发布流
**When** 全量回归
**Then** 合法路径行为与现状逐字等价（get_unpublished 正常返回/poller 发布成功标记 published 不变）

**验证标准:**
- [ ] 既有 outbox 全树测试零回归（含 R2/R3 的毒隔离与白盒断言用例）
- [ ] 真实 PG 集成测试：终态迁移/requeue/巡检三链路（**前置：PG 环境修复**）

---

## 🏗️ SDD+TDD 融合开发

### Task 0: SDD 规范定义（必选前置）

- [ ] **状态机评审**：archived → pending 迁移放开（AC-2）——守卫设计（requeue 唯一入口）与语义论证记录
- [ ] **形态裁定 D-1**：巡检消费入口（CLI vs metrics 端点 vs 两者）——倾向 CLI（零部署依赖，metrics 归观测专项）
- [ ] 迁移窗口设计定稿（proposal 方案 A：get_unpublished 分流重构——SELECT 放宽为 pending/failed 全量 + Python 侧分流「未超限正常处理 / 超限即归档」，应用层保持空批早退语义）
- [ ] Gherkin 验收场景（AC-1~AC-4）

### 领域异常契约

无新增异常（复用 `InvalidStateTransitionError` 状态机守卫）。

### 端口契约变更

| 端口 | 变更 | 兼容性 |
|------|------|--------|
| `OutboxRepository` | 新增 `requeue(event_id) -> None`；`cleanup_old_published_records(older_than_days, include_archived=False)` 参数扩展 | 追加方法经 ContractGate 兼容评审；参数默认值向后兼容 |

### TDD 循环（概要）

| 循环 | 红 | 绿 | 重构 |
|------|----|----|------|
| A 实体 requeue 迁移 | archived→pending 成功/非法态抛/清零断言 | `OutboxEntity.requeue()` | 既有状态机测试零回归 |
| B 仓储 requeue + archived 迁移 | mock 模式：requeue 三态/超限行归档 | 仓储方法 + get_unpublished 分流 | 白盒断言保持 |
| C poller 终局接线 | 重试耗尽 → archived + ERROR 日志 | process_one 终局分支 | 幂等恢复语义不回退 |
| D cleanup 扩展 + 巡检 CLI | archived 清理计数/status 命令输出 | 实现 | — |
| E PG 集成 | 真实 PG 三链路（迁移/requeue/巡检） | （应直接转绿） | 前置 PG 修复 |

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | Task | 验证 |
|----|------|------|
| AC-1 | Task 0 设计 + Task B/C | 单测 + 集成终态断言 |
| AC-2 | Task 0 评审 + Task A/B | 状态机测试 + requeue 三态 |
| AC-3 | Task D | cleanup 参数化 + 巡检命令 |
| AC-4 | Task E + 全量回归 | 零回归 + 真实 PG |

## 📋 Tasks / Subtasks 任务分解

### Task 0: SDD 规范（状态机评审 + D-1 裁定 + 迁移窗口定稿 + Gherkin）
### Task 1: 实体层 archived→pending 迁移（TDD A）
### Task 2: 仓储层 requeue + 超限归档分流（TDD B）
### Task 3: poller 终局接线（TDD C）
### Task 4: cleanup 扩展 + 巡检消费入口（TDD D，按 D-1 裁定）
### Task 5: PG 集成验证（TDD E，**前置：本地 PG 5433 认证修复**）
### Task 6: 收尾（全量回归 + deferred-work D11 核销 + 文档同步）

---

## 📝 Dev Notes 开发笔记

### 关键架构决策

| # | 决策点 | 选定 | 依据 |
|---|--------|------|------|
| DC-1 | 终态形态 | archived（复用实体既有状态机） | proposal-d11 三方案对比裁定；实体已实现+有测试，补「最后一公里」 |
| DC-2 | 迁移窗口 | get_unpublished 应用层分流 | 归档执行窗口需要（SQL 过滤使超限行不可达）；空批早退语义等价保持 |
| DC-3 | DLQ 表方案 | 弃用 | 跨表搬运破坏事务边界与追溯上下文（proposal §3-B） |

### 已知风险与前置

1. **PG 环境前置**（阻塞 Task 5）：本地 5433 认证失败（R1 周期即存在）——需先修复 .env 凭据或容器；单元级（mock）可先行
2. **状态机语义变化**：archived 从死终态变可 requeue——Task 0 评审项（守卫：requeue 唯一入口）
3. **requeue 消费面**：价值在 RabbitMQ 消费方上线后完整（deferred-work「RabbitMQ 消费方」条目）——本 Story 交付仓储能力，消费面随消费方 Story
4. 迁移窗口分流重构触碰 R3-F1 的 get_unpublished——白盒断言（`retry_count < event_outbox.max_retries` 子串）需按新语义更新（全量选择 + 应用层过滤），**必须保持「超限行不进正常发布批」的语义不变**

### 验收测试约束

- 真实 PG 集成（Schema 隔离 + savepoint rollback 先例）；Gherkin 按 R6 范本
- 5-1 周期全部 outbox 测试（R2 毒隔离/R3 过滤/清偿轮 DLQ+count_by_status）零回归

---

## 🤖 开发代理记录 Dev Agent Record

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Execution Date** | 2026-10-15（立项） |

### 完成清单 Completion Notes List

- [x] 立项（依据 proposal-d11 方案 A + D11-a 前序交付实测）
- [ ] dev-story 实施（从前置 PG 环境修复开始）

### 文件清单 File List

**创建的文件：** `_bmad-output/implementation-artifacts/stories/91-2-outbox-dead-letter-termination.md`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 91.2 |
| **Story Key** | 91-2-outbox-dead-letter-termination |
| **Epic** | Epic 91: 技术债清偿专项 |
| **优先级** | P3（运维可观测 + 审计合规闭环；RabbitMQ 消费方上线前完成即可） |
| **来源** | 5-1 审查周期 D11①（proposal-d11 D11-b 切分） |
| **前置** | 本地 PG 环境修复；Task 0 状态机评审 |
| **预估** | 2 天（proposal §6 口径，含 PG 集成验证） |

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-15
