# Story 6-6: Checkpoint 摘要查看与恢复（高管审批面——清单/详情/参数修正/双模式恢复执行/CheckpointRecovered 首激活）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行文档审查修订循环（本 Story 已执行五轮——见 Docs Review Fixes 表）+ 人工按 story-template 合规清单核对后再执行 `dev-story`（`validate-create-story` 系上游模板措辞，本仓无该名 skill）。

---

## 📖 Story 描述

**As a** 高管,
**I want** 查看 Checkpoint 摘要（阶段标识、完成状态、关键参数、用户反馈请求、修正历史）并修正关键参数后按双模式恢复运行（Override 待同步标记 / Replay 后续作废+重跑指引，附恢复确认与审批留痕）,
**So that** 参与关键决策点审批——在阶段恢复点上审阅产物、修正参数并驱动检查点体系恢复到一致可用状态。

### 业务价值

- **Epic 6 价值组「战略规划与审批能力」的审批半边**：epics L686「用户可以生成战略规划并审批」——生成侧（6-1~6-5b）已 done，本 Story 交付审批侧首个可用面（P1-6，依赖 6.3）
- **兑现 6-3 OD-1 钦定的 6-6 边界**（6-3 story L660 原文）：「恢复执行引擎（Replay 重放重跑后续阶段/Override pending_sync/CheckpointOverridden/CheckpointRecovered 事件）+ 摘要查看/审批交互/并发审批归 6-6」——本 Story 落地其 MVP 形态（本 Story OD-1 裁定深化边界）
- **深化 FR-SP-03 (P0) 的交互语义**（prd L1870/or.md 五.4 L479）：「各个阶段任务完成后暂停并输出阶段性结果，**用户可反馈与修正该结果，然后继续执行后续任务**」——6-3 交付了快照创建与修正数据面（apply_correction），本 Story 打通「查看→修正→确认→恢复」闭环入口
- **激活三件休眠资产**（Epic 1 骨架零新增激活——6-5a ReportGenerated 首激活同款先例）：`CheckpointRecovered` 事件（checkpoint_events.py:40-69，通道双登记+auto_trigger 监听在位、全仓零生产方）/ `checkpoint_recovery_use_case` 组合根注册（composition_root.py:2321-2332，零消费方）/ `CheckpointRecoveryView.state_version/snapshot_id` 乐观锁基线（6-3 R3-2 专为 6-6 增补）
- **为 Epic 21/22 供给后端能力**：Story 22.4（Checkpoint 恢复模式选择界面 FR-UI-16）直接依赖 6.6（epics L3404）；Story 22.7（Checkpoint 摘要查看+参数修正恢复 FR-UI-20）依赖 22.4（epics L3407）→ 传递依赖 6.6——本 Story 是其唯一后端供给方
- Epic 6 内部顺序：6-3（done，恢复数据面）→ **6-6（本 Story，读面+执行面+入口）** → 6-7 溯源树 / 6-8 高管简化视图（并列 backlog）

### 与 6-3 的范围边界（出处逐行声明）

| 面（出处） | 6-3 已交付（禁重复造轮） | 6-6 增量（本 Story） |
|---|---|---|
| 恢复数据面（6-3 AC-7） | `recover_checkpoint`（load→verify→反序列化→`CheckpointRecoveryView` 9 键组装）+ 后续清单 probe-load 推导（R8-F1）+ 判定透传 | 零改动复用（恢复引擎第一步内消费） |
| 双模式判定（6-3 OD-1） | `recommend_recovery_mode` 纯函数（≥2 REPLAY 强制/<2 OVERRIDE 推荐——recovery_mode.py:21-42） | 零改动复用 + **模式强制语义执法**（建议 REPLAY 而请求 OVERRIDE → 487 拒绝——or.md L622 不变约束承载） |
| 修正面（6-3 AC-6） | `apply_correction`（484 完整性前置→482 乐观锁→correction_history 追加→checksum 重算→同键覆盖）；`CorrectionRecord` 五字段零改动 | 零改动复用（引擎修正步内消费；CLI 入口+审批留痕语义归本 Story） |
| 事件（6-3 OD-9） | `CheckpointReached` 真实发布（metadata 携 plan_id+checkpoint_no 双关联键——R3-3 专为 6-6 免反查） | `CheckpointRecovered` **首激活发布**（既有资产零字段变更——OD-2）；`CorrectionApproved` 不激活（OD-2 裁定） |
| 入口（6-3 CLI 节 L246） | CLI `checkpoint-create`（创建面唯一入口）；「恢复面 CLI 入口归 6-6（审批交互面入口）」 | CLI 三命令：`checkpoint-list` / `checkpoint-show` / `checkpoint-recover`（R4） |
| 摘要读面 | 无（recover_checkpoint 仅单点视图；无 plan 级清单方法） | `list_checkpoints` 新方法 + `CheckpointSummaryView` VO + sync 状态 join（AC-1） |
| 恢复执行 | 无（数据面 only——「恢复执行引擎归 6-6」三处代码钦定：recovery_mode.py:6/ports/checkpoint.py:173/entities/checkpoint.py:68） | `execute_recovery` 新方法（模式裁定→修正应用→双模式分支→恢复记录→事件发布）+ 恢复记录第三键族（OD-3） |
| 完整 Replay/Override 协议 | 无 | **不做**（归 Epic 10 Story 10.2-10.5——epics FR Coverage Map L535-538 权威映射；本 Story MVP 边界见 OD-1） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Checkpoint 清单与摘要查看（四要素显示）

**Given** 某 plan_id 下已存在 ≥3 个完整形态 Checkpoint（如 CP-1/CP-3/CP-5——经既有 `checkpoint-create` 或用例创建）
**When** 高管请求查看摘要（CLI `checkpoint-list --plan-id` / `checkpoint-show --plan-id --checkpoint-no`）
**Then** 清单返回该 plan 全部存活 checkpoint（`range(1, CHECKPOINT_NO_MAX + 1)` 即 CP-1..CP-8 全量 probe——R8-F1 增量 probe-load 模式（现状仅探 n+1..CP-8）的起点扩展，从 CP-1 起；RedisSnapshotStore 无 scan/列举 API，probe 路线是唯一可行面），每项携带 `CheckpointSummaryView` 8 键（checkpoint_no/stage_id/completed/summary/state_version/created_via/timestamp/sync_status——timestamp 由实体 datetime 在服务层 `isoformat()` 转换为 str）；详情返回 6-3 既有 `CheckpointRecoveryView` 9 键原样（零适配复用）
**And** 摘要面四要素齐备（epics L2319 钦定）：**阶段标识**（checkpoint_no+stage_id）/ **完成状态**（completed bool）/ **关键参数**（summary+correction_history 修正历史）/ **用户反馈**（反馈要素由 correction_history 修正响应历史+completed 状态承载；`user_feedback_request` 审批请求标志仅存在于 CheckpointReached 事件 payload（经 outbox 可溯），不在快照 state_data 13 键内、不进摘要 VO——8 键契约不含此键）
**And** sync_status 三值域（in_sync/pending_sync/invalidated）经恢复记录键 join 推导（无恢复记录时全量 in_sync——键恒在纪律的读侧镜像）

**验证标准/Validation Criteria:**
- [ ] 清单场景：3 个已创建点全列出且按 checkpoint_no 序号升序；不存在的编号不出现（probe None 静默跳过——R8-F1 同款）
- [ ] 详情场景：9 键视图与 6-3 验收 S10 同形态（state_version/snapshot_id 值级断言——防「忘填用默认值」零检出，6-3 R3-2 断言形态继承）
- [ ] sync_status 推导：恢复执行后（AC-3）再查清单——Override 后续为 pending_sync / Replay 后续为 invalidated / 恢复起点自身恒 in_sync（新基线——措辞与推导规则一致，纯恢复场景无修正点）
- [ ] plan_id 下零 checkpoint 时返回空清单（不抛 480——清单是枚举面非单点面，与 recover_checkpoint 单点 480 语义分立）

### AC-2: 关键参数修正（乐观锁闭环）

**Given** Checkpoint 已创建且高管持摘要视图（state_version 基线）
**When** 提交修正（CLI `checkpoint-recover --correction-type/--previous-value/--new-value/--applied-by` 四参数成组，或编程面直接调既有 `apply_correction`）
**Then** 修正经 6-3 既有 `apply_correction` 应用：correction_history 追加五字段投影（applied_at isoformat）、state_version +1、checksum 重算封印、同键覆盖单版本存活——**6-3 行为面零改动**（call_order/断言族零适配回归）
**And** 修正后快照可读回且 verify 绿（修正链完整性闭环——6-3 AC-3 语义在入口面复证）；修正记录随 AC-1 摘要面可见（关键参数修正历史显示）
**And** 四参数部分出现（如仅 --correction-type）→ 242 参数守卫（`EntityValidationError`——成组约束**唯一落位=CLI 层** post-parse 检测：四个 args 原始形态仅在 CLI 层可见，`CorrectionRecord` 字段默认值兜底（previous_value/new_value/applied_by 默认空串）下「部分出现」到用例层已不可表达——CLI 层构造真实异常 242（6-3 R1-F18 真实异常构造纪律同款）；用例层承载 confirmed_by 非空 242）；乐观锁基线不匹配（expected_state_version 低于存活版本）→ 482 透传（6-3 第二触发点零改动复用）

**验证标准/Validation Criteria:**
- [ ] 修正往返：history 追加一条（五字段投影）+ 版本 v0→v1 + 原快照字段保留 + checksum 重算后 round-trip verify 绿
- [ ] 连续修正：v0→v1→v2 累积两条（修正链历史累积——6-3 单键单版本语义）
- [ ] 四参数部分出现 → 242（红测：仅一参数 CLI 调用——CLI 层唯一落位；用例层不承载成组守卫见 L63 裁定）
- [ ] 旧基线修正（expected=0 对存活 v1）→ 482 透传（两步构造法——6-3 R6-2 先例复用）

### AC-3: 双模式恢复执行（Override 待同步 / Replay 作废）

**Given** Checkpoint 快照族在位（含 ≥2 后续 checkpoint 的 Replay 场景与 0~1 后续的 Override 场景）
**When** 高管带 `--confirm` 触发恢复执行（`checkpoint-recover`）
**Then** 引擎 `execute_recovery` 编排五步：①入口守卫（checkpoint_no 三重守卫复用——`_parse_checkpoint_number` 零改动）→ ②恢复数据面（复用 `recover_checkpoint`：load+verify+后续清单+建议模式）→ **②.5 模式裁定（裁定先于修正应用——与边界表 L36 编排序对齐：mode 显式传入时执行强制语义执法 487，冲突即拒（零副作用——correction 场景下先落修正再 487 会破坏零副作用语义，裁定必须前置于③））**→ ③修正应用（correction 非 None 时经 `apply_correction`，乐观锁基线取自②视图 state_version；**486 try 面扩包③④两处 save**——修正一体场景下③步 save 失败的 StorageError(103) 不裸逃逸，统一归 486 fail-loud；482/484 在 save 之前触发仍经既有触发点透传不受影响）→ ④双模式分支落恢复记录（第三键族，OD-3）→ ⑤发布 `CheckpointRecovered`（首激活——字段族与 metadata 见 OD-2）
**And** **Override 分支**（<2 后续）：后续 checkpoint 标记 pending_sync（"基于旧版本"——or.md L483 语义，经恢复记录承载不删快照；**pending_sync 清单长度上限=1**——Override 可执行当且仅当后续 ≤1，≥2 后续时建议模式=REPLAY、请求 Override 必 487 拒绝，模式执法的必然推论）；`consistency_risk_level="medium"`（有后续时）/`"low"`（无后续）；一致性风险提示随 CLI 输出
**And** **Replay 分支**（≥2 后续）：后续 checkpoint 全部标记 invalidated（作废——修改点后所有状态重新计算，MVP 形态为标记+指引，实质 LLM 重跑 defer 归 Epic 10，OD-1 四条物理约束论证）；`consistency_risk_level` 恒 `"low"`（强一致作废语义——⑤步恒显式传 `assess_consistency_risk` 函数输出，Replay 输出恰与事件字段默认值同值；CLI dry-run 评估与引擎⑤步同源消费，见数据模型节）；重跑指引（next_action_hint：建议以新 plan_id 经 `blm-plan` 重跑）随 CLI 输出
**And** **模式强制执法**（FR-SP-07 不变约束 or.md L622——OD-6；**执法点=②.5，先于③修正应用**）：显式 `--mode override` 而建议为 REPLAY → 487 `RecoveryModeConflictError` 拒绝执行（零副作用——恢复记录不写、事件不发、**修正不应用**——487 单测补「correction+冲突组合→apply_correction 零调用断言」防裁定后置的实现漂移）；建议 OVERRIDE 而请求 REPLAY → 允许（用户可选更强一致性模式）；**L623 Replay 幂等性 MVP 承载声明**：恢复标记面单键覆盖天然幂等（同 plan 二次恢复覆盖前次记录、invalidated 重复标记幂等——L177 注记②），执行缓存级幂等随实质重跑归 Epic 10
**And** 恢复执行窗口实测填充事件 `execution_delay_ms`（⑤步事件构造前 perf_counter 毫秒差——窗口含①~④步；事件字段的数据源钦定）；事件 `cost` 字段恒 0.0 不显式传（恢复链零 LLM——OD-1，MVP 无成本模型）；恢复记录持久化 TTL 30 天（对齐 checkpoint 键族合规窗）

**验证标准/Validation Criteria:**
- [ ] Override 执行：恢复记录 12 键落库（键契约见数据模型节）+ 后续清单进 pending_sync_checkpoints + 事件 recovery_mode="Override"（events 枚举大写形态——转换函数消费面）
- [ ] Replay 执行：后续清单进 invalidated_checkpoints + 事件 recovery_mode="Replay" + next_action_hint 非空
- [ ] 模式冲突：≥2 后续 + `--mode override` → 487 且恢复记录键不存在（零副作用断言——单测层 save 零调用 call_order 断言；验收层等价形态=恢复记录键不存在+outbox 零行+state_version 不变）
- [ ] 无后续 checkpoint 的恢复（CP-8 尾点）：两分支语义均可达（affected 空清单+low 风险——边界值）
- [ ] 修正+恢复一体（--correction-* 与 --confirm 同给）：③④⑤链式成功且事件 modification_content 携五字段投影

### AC-4: 审批确认流程（两态确认+事件落行）

**Given** 高管已查看摘要（AC-1）并准备恢复
**When** 无 `--confirm` 调用 `checkpoint-recover`
**Then** **dry-run 两态**：输出影响评估（后续清单+建议模式+一致性风险提示+待确认提示）并 exit 0——**不执行恢复**（恢复记录零写入、事件零发布、修正零应用——三零断言）
**And** 带 `--confirm` 调用：执行 AC-3 全链；`CheckpointRecovered` 经既有 reliable 单通道发布（event_channels.yaml:192-195 + channel_router.py:249-254 双登记零 diff），outbox 落行可断言（断言键钦定：`payload->'payload'->>'checkpoint_id'` 通道——**新键路径**（6-3 先例通道是 phase_identifier/user_feedback_request，checkpoint_id 双下钻全仓零先例；结构上经 base.py to_dict 子类字段并入 payload 子字典可达）+ `payload->'metadata'->>'plan_id'` 关联（R3-3 双关联键——6-3 直系先例通道）；**checkpoint_id 值源钦定**：⑤步发布显式传 `checkpoint_id`——修正一体场景取③步 `apply_correction` 返回 sealed 快照的 `snapshot_id`（UUID 同型直传——`with_updated_state` 轮换 snapshot_id，②视图值在修正后失效）、纯恢复场景取 `uuid.UUID(②视图.snapshot_id)`（视图值是 str——R3-2 序列化面 str 化的逆转换），断言预期值单源=`CheckpointRecoveryOutcome.recovered_snapshot_id`）
**And** 发布失败不回滚恢复记录落库（恢复记录是审计真相源、事件是通知面——6-3 ⑤步 CheckpointReached「发布失败降级不回滚」同语义先例，checkpoint_service.py:281-296；CLI exit 0 口径=恢复记录落库成功）
**And** 审批留痕：confirmed_by（--applied-by 或独立 --confirmed-by，Task 0 钦定参数面）与 correction.applied_by 双写恢复记录（高管审批身份的持久化审计面）

**验证标准/Validation Criteria:**
- [ ] dry-run 三零：恢复记录键不存在 + outbox 零 CheckpointRecovered 行 + state_version 不变
- [ ] confirm 执行：outbox 恰一行（checkpoint_id 通道=新键路径零先例+metadata.plan_id=6-3 先例通道，双通道值级断言——预期值单源 Outcome.recovered_snapshot_id）
- [ ] 发布失败注入（单测层 AsyncMock 豁免面）：恢复记录仍落库 + warning 日志 + CLI exit 0
- [ ] confirmed_by 留痕：恢复记录 confirmed_by 键值级断言

### AC-5: 并发审批（5 路互不干扰）

**Given** 5 个独立 plan_id 各持一个已创建 Checkpoint（5 位高管各审各的——并发审批 5 个 Checkpoint，epics L2332）
**When** 并发触发 5 路恢复执行（asyncio.gather——真并发；**每任务会话隔离钦定**：gather 的每个 per-plan 协程体内自建 `AsyncSession` 并 `set_session()`——PEP 567 task 级 context 拷贝使 set 不外泄、深层 `get_session()` 调用期解析自动命中本任务会话；6-3 装配链的共享单 AsyncSession 形态下 5 路并发写 outbox/归档必触发 SQLAlchemy 并发会话防呆 `InvalidRequestError`——共享服务实例不重建、仅会话按任务隔离）
**Then** 5 路全部成功（恢复成功率 100% 口径的并发承载）；各 plan 的恢复记录/事件/修正互不干扰（键族 plan_id 隔离天然保证——同 plan 并发会竞争恢复记录单键，5 独立 plan 语义钦定 OD-10）
**And** 5 行 CheckpointRecovered outbox 落行各恰一行（按 metadata.plan_id 分组计数——非空锚防过滤键空真，6-2 R1-F2 教训继承）

**验证标准/Validation Criteria:**
- [ ] gather 5 路全成功 + 5 恢复记录独立可读回
- [ ] outbox 按 5 个 plan_id 各恰一行（分组断言）
- [ ] 并发下无交叉污染（各恢复记录的 plan_id 键值与发起方一致——值级断言）

### AC-6: 性能与成功率

**Given** Checkpoint 已创建（前置经既有创建链——性能口径不含创建）
**When** 采样计时
**Then** **摘要显示 P95<200ms**（epics L2330）：口径 = `checkpoint-show` 单点窗口（load+verify+视图组装——`recover_checkpoint` 数据面窗口，与 6-3 恢复数据面窗口同构）；`checkpoint-list` 清单窗口（≤8 点 probe-load 全量+恢复记录 join）同门禁覆盖
**And** **恢复执行成功率 100%**：N 次带 confirm 恢复 N 次恢复记录可读回+事件可断言（强制环节零吞错——486 触发面以外无静默失败路径）
**And** **Replay P95<60s / Override P95<15s**（epics 6.3 L2164 完整执行口径归 6-6 的兑现）：本 Story 引擎编排窗口（②~⑤步，纯 Redis/事件数据面操作）实测断言——毫秒量级天然覆盖双门禁；**口径差声明**（OD-8）：引擎窗口不含 LLM 重跑（OD-1 defer），epic 预算针对的完整重放口径由 Epic 10 承接时本引擎窗口是其编排子集
**And** 采样数学口径沿用 6-3 AC-8（`sorted(durations)[ceil(0.95*n)-1]`、n=20 升序取次大值——模块级期望常量独立构造）

**验证标准/Validation Criteria:**
- [ ] show 窗口 20 轮采样 P95<200ms（预热含首次 load——连接池建立，6-3 R8-F5 注记继承）
- [ ] list 窗口同门禁同 20 轮采样 P95<200ms（多 checkpoint 前置场景）
- [ ] 恢复执行窗口 <15s 断言（两模式各采样——远小于门禁的工程冗余断言，漂移即红）
- [ ] 成功率：连续 N≥10 次恢复（独立 plan）全部恢复记录可读回

### AC-7: 异常路径全链（六码分立）

**Given** 恢复执行入口在各类非法输入/状态下调用
**When** 触发异常路径
**Then** 六码分立且零裸异常逃逸（**六码全景**：242/480/482/484/486/487——验收面承载五码 242/480/482/484/487，486 归单测层见下）：**plan_id 非 UUID → 242**（用例守卫——RecoverCheckpointUseCase 镜像先例）/ **checkpoint_no 畸形或越域 → 242**（`_parse_checkpoint_number` 三重守卫复用，畸形零副作用——load 零调用断言，6-3 R1-F2 call_order 断言形态继承）/ **checkpoint 不存在（含 JSON 损坏同路径）→ 480**（`_load_or_480` 复用）/ **checksum 损坏 → 484**（恢复入口 verify 复用）/ **旧基线修正 → 482**（apply_correction 乐观锁既有触发点透传——AC-2 承载）/ **强制 Replay 违反 → 487 新码**（AC-3——执法点②.5 前置）/ **恢复编排强制环节失败 → 486 新码**（fail-loud，**try 面扩包③④两处 save**、except 面钦定 `StorageError`——RedisSnapshotStore.save 唯一异常出口；修正一体场景③步 save 失败同归 486 防 103 逃逸；⑤发布独立降级面不属 486——482/484 在 save 之前触发经既有触发点透传不并入 486）
**And** 486/487 为 planning 段新码（486-489 预留段取码——`_code_ranges.py:189` 成文「留 6-6 恢复执行面」的兑现；485 属 OD-7 钦定永不设码的段内空洞、488/489 继续预留）；6-4 两处缺席断言让位更新（`tests/unit/architecture/test_json_chain_of_thought.py:338-360`（docstring :339-343，range 本体 :356-358）+ `tests/acceptance/test_acceptance_json_chain_of_thought.py:2150-2171`（range 本体 :2168）的 `range(485, 490)` 收窄为**残留码元组 `(485, 488, 489)`**——保留 485 缺席守护（OD-7 永不设码的执法面）；断言处注记「6-6 让位」的兑现义务）

**验证标准/Validation Criteria:**
- [ ] 验收面五码各至少一条专属场景（242/480/482/484/487——红测先行 Task 0 钉死；486 编排失败注入归单测层 AsyncMock 承载——no-mock 红线互斥裁定 6-2 R3-4 先例（6-3 沿用））
- [ ] CLI 面六码 stderr `[EXCEPTION_xxx]` 形态统一（6-3 R1-F18 前缀统一先例继承）
- [ ] 6-4 让位后其守护测试零适配通过（断言收窄而非删除——缺席断言对残留码元组 (485, 488, 489) 继续有效）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **零新增领域事件、零事件字段变更**（本 Story 钦定——OD-2）：
  - `CheckpointRecovered` 是 Epic 1 既有资产（`src/domain/events/checkpoint_events.py:40-69`，字段族 checkpoint_id(UUID)/recovery_mode(events.enums 版——"Replay"/"Override" 首字母大写)/modification_content(dict)/affected_checkpoints(list[str])/consistency_risk_level(str)/execution_delay_ms(float)/cost(float)），双登记在位（event_channels.yaml:192-195 + channel_router.py:249-254，reliable 单通道）+ auto_trigger 监听已注册（auto_trigger_handler.py:65 CheckpointRecovered/:67 CorrectionApproved）——本 Story 仅落**发布点**（恢复引擎⑤步），事件定义/导出/双登记/监听注册**全部零 diff**
  - **⑤步发布 checkpoint_id 传值钦定（OD-2⑦）**：字段默认 default_factory=uuid.uuid4（随机），不显式传值则值级断言不可预期——发布时显式传 `checkpoint_id`：修正一体场景取③步 `apply_correction` 返回 sealed 快照的 `snapshot_id`（`with_updated_state` 轮换 snapshot_id——checkpoint_snapshot.py:145，②视图值在修正后失效）；纯恢复场景取 `uuid.UUID(②视图.snapshot_id)`（视图 str 值逆转换——R3-2 注记「与 outbox 事件 checkpoint_id 序列化面同形态」的兑现）；6-3 ⑤步 `checkpoint_id=snapshot.snapshot_id` UUID 同型直传（R6-24）直系先例
  - 字段族与 or.md L49 (9) 需求语义逐字段吻合（Checkpoint ID/恢复模式/修改内容/影响后续列表/一致性风险等级/执行延迟/成本）——**蓝图事件 CheckpointReplayed/CheckpointOverridden/CheckpointOverrideCompleted（or.md L140/L482-483/设计文档 §2.3）不新建**：Override/Replay 双语义经 CheckpointRecovered.recovery_mode 单事件区分（零新增纪律——6-3 OD-9/6-4 OD-6/6-5a OD-6 三连先例）
  - `CorrectionApproved`（correction_events.py:16-40，通道双登记在位）**不激活**（OD-2 裁定：apply_correction 是 6-3 冻结行为面，加发布会动 call_order 断言族；单事件流足够承载验收语义；approval_chain 多级审批是 V1 语义——deferred-work 登记）
  - 发布容错：⑤步发布失败降级 warning 不回滚恢复记录（6-3 ⑤步 checkpoint_service.py:281-296 成文先例同构）；CLI exit 0 口径=恢复记录落库成功
- [ ] metadata 双关联键沿用：`CheckpointRecovered(..., metadata={"plan_id": ..., "checkpoint_no": ...})`（DomainEvent 既有 `metadata` 构造参数——base.py:74；to_dict 顶层落位 :160-164；R3-3 为 6-6 免反查钦定的通道直接复用，dict 内容扩展与事件类字段族零冲突）
- [ ] 守护测试承载：`tests/contracts/test_event_channel_mapping_checkpoint_recovery.py` 新建（发布接线正向 + 唯一构造位 + 双登记零 diff + 既有 CheckpointReached 断言面零修改复跑）；`test_event_channel_mapping_pdf_report.py` 的 `_FROZEN_EVENT_COUNT=56` 冻结键数基线**零变化**（零新增事件=登记数不变）

#### 数据模型 (Data Models)

**零新领域实体、零既有实体改动**（6-3 已交付全部领域载体——禁重复造轮）：

- [ ] **复用既有**（全部零改动）：`CheckpointSnapshot`（**11 字段（含 checksum）**+verify——恢复记录同形态承载复用；实体构造守卫 `if checkpoint_no and not persistent_note_ref` 在 checkpoint_no="" 时短路不触发，OD-3 承载可行性的代码根基）/ `CorrectionRecord`（五字段——correction_type 必选+previous_value/new_value/applied_by 默认空串/applied_at 默认 now；correction_id 仅 docstring 提及无字段，6-3 R1-F5 定谳维持；「置信度变化/影响因子」等扩展**本 Story 不做**——五字段满足审批留痕语义，YAGNI）/ `RecoveryMode`（entities 版 :45-49 小写）+ events/enums 版（:48-52 大写——双枚举转换见新增纯函数）/ `CheckpointStatus` / `Checkpoint` 聚合（recover() 状态机继续不驱动——6-3 R2A-4 裁定维持：恢复引擎不重建聚合实例，状态面经恢复记录承载）
- [ ] **新增领域纯函数两个**（落 `src/domain/services/recovery_mode.py` 就地扩展）：
  - `to_event_recovery_mode(mode: RecoveryMode) -> EventRecoveryMode`（entities 小写枚举 → events 大写枚举显式映射——6-3 story L171「双枚举知悉注记：6-6 恢复执行面消费建议恢复模式时需显式转换」的兑现；纯标准库）
  - `assess_consistency_risk(mode: RecoveryMode, affected_count: int) -> str`（一致性风险等级同源计算——Override+有后续→"medium"/其余（Override 无后续、Replay 全形态）→"low"；CLI dry-run 评估输出与引擎⑤步事件构造**同源消费**（单一事实源防双实现漂移；恢复记录 12 键与 Outcome 10 键均无风险键，唯一引擎消费落点=⑤事件构造）；纯标准库）
- [ ] **新增应用层 VO 两个**（落 `src/application/ports/checkpoint.py` 就地追加——ChecklistRecoveryView 同文件先例）：
  - `CheckpointSummaryView`（frozen dataclass，**8 键**——Task 0 冻结唯一版本）：`checkpoint_no`/`stage_id`/`completed`(bool)/`summary`(str)/`state_version`(int)/`created_via`(str)/`timestamp`(isoformat str)/`sync_status`(str——值域 "in_sync"/"pending_sync"/"invalidated" 三值钦定)
  - `CheckpointRecoveryOutcome`（frozen dataclass，**10 键**——Task 0 冻结唯一版本）：`checkpoint_no`/`recovery_mode`(entities 枚举)/`corrected`(bool)/`new_state_version`(int)/`affected_checkpoints`(list——MVP 下与 marked_checkpoints 恒等（Override：后续=pending_sync 清单/Replay：后续=invalidated 清单），双字段为 V2 部分标记分叉预留，docstring 钉死该语义预期)/`marked_checkpoints`(list)/`execution_ms`(float)/`next_action_hint`(str——Replay 分支重跑指引/Override 分支风险提示，CLI 展示面)/`recovery_record_session_id`(str——审计回溯锚)/`recovered_snapshot_id`(str——⑤步事件 checkpoint_id 的同值锚：修正一体=③步 sealed.snapshot_id、纯恢复=②视图.snapshot_id；outbox 值级断言的预期值单源，验收/集成步骤函数经 Outcome 直取)
- [ ] **恢复记录 state_data 键契约**（第三键族载荷，Task 0 冻结 **12 键**——登记于端口文件 docstring 序列化契约区第四级，6-3 三级契约扩展）：`plan_id`/`checkpoint_no`（恢复起点）/`recovery_mode`（"replay"/"override" 小写——entities 枚举值形态）/`corrected`(bool)/`correction`（五字段投影 dict 或 {}——无修正时空 dict 键恒在）/`affected_checkpoints`(list)/`pending_sync_checkpoints`(list——Override 分支填充，Replay 时空 [] 键恒在)/`invalidated_checkpoints`(list——Replay 分支填充，Override 时空 [] 键恒在)/`confirmed_by`(str)/`recovered_at`(isoformat)/`execution_ms`(float)/`created_via`（"cli"/"use_case" 两值——6-3 值域纪律复用）
  - **承载形态**（OD-3）：`CheckpointSnapshot` 通用 KV 形态——`session_id = f"blm-checkpoint-recovery-{plan_id}"`（新前缀单源常量 `CHECKPOINT_RECOVERY_SESSION_PREFIX = "blm-checkpoint-recovery-"`），`checkpoint_no=""`（**非完整形态**——不触发实体构造守卫/persistent_note_ref 强制），`ttl_seconds=2592000`（30 天对齐 checkpoint 合规窗），经既有 `snapshot_repository.save/load` 存取（**零新存储设施/零 infra 改动/零新依赖**）；每 plan 最新一次恢复单键覆盖（与 6-2 latest 键同构——同 plan 二次恢复覆盖前次，历史经事件 outbox 可溯）
  - 读侧判别规则扩展：三前缀并存（`blm-planning-`/`blm-checkpoint-`/`blm-checkpoint-recovery-`）——**权威判别键 = 前缀（三前缀互异）+ 实体面 `checkpoint_no=""`（Redis 键无 `:CP-n` 段）+ state_data 含 `recovery_mode` 键**（checkpoint 族 13 键无此键——恢复记录 12 键独有；两族 state_data 均含 checkpoint_no 键，既有第一级契约「前缀 + state_data 含 checkpoint_no 锚」判别语在三前缀并存后不再充分，第四级契约区登记时同步声明其适用范围收窄为 blm-planning vs blm-checkpoint 两族互判）
  - **sync_status 推导规则**（AC-1 join 语义，Task 0 钦定）：`list_checkpoints` 时 load 恢复记录（None → 全量 in_sync）；对每个存活 checkpoint_no——在 `invalidated_checkpoints` → "invalidated"；在 `pending_sync_checkpoints` → "pending_sync"；否则 "in_sync"；恢复起点 checkpoint_no 自身恒 in_sync（新基线）；**两条口径注记**：① 推导仅基于该 plan **最新一次**恢复记录——同 plan 二次恢复单键覆盖后旧恢复的 pending_sync/invalidated 标记从显示面消失（读面回退 in_sync，历史溯源自 outbox CheckpointRecovered 事件流——OD-3 单键覆盖语义的读面后果显式声明）；② invalidated 点在②步后续 probe 中仍按键存在性计入后续数参与模式判定（MVP 判定不消费 sync 标记——重复标记幂等且 487 执法仅更严，完整协议归 Epic 10）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] **既有端口演进 1 个**（v1.0.0 → **v1.1.0**，纯新增方法——ContractGate 兼容性检查通过路径，OD-4）：`CheckpointServicePort`（`src/application/ports/checkpoint.py`）新增两方法组：
  - 读方法：`list_checkpoints(*, plan_id: str) -> list[CheckpointSummaryView]`（`range(1, CHECKPOINT_NO_MAX + 1)` 全量 probe+恢复记录 join sync_status——R8-F1 增量 probe-load 模式从 CP-1 起的全量扩展；**plan_id UUID 守卫=用例层承载**（ListCheckpointsUseCase——服务层不重复守卫，6-3 服务层无 UUID 守卫先例一致）；空族返回空清单不抛 480——AC-1 语义分立）
  - 执行方法：`execute_recovery(*, plan_id: str, checkpoint_no: str, correction: CorrectionRecord | None = None, mode: RecoveryMode | None = None, confirmed_by: str = "", created_via: str = "use_case") -> CheckpointRecoveryOutcome`（五步编排——AC-3；`confirmed` 不入签名：CLI 两态在接口层拦截，无 confirm 的 dry-run 不进引擎——引擎假设调用方已确认，confirmed_by 空串守卫归用例层 242（CLI 层与用例层**双落位**——dry-run 路径也经 CLI 层校验，评估/执行两态参数校验面一致）；`mode=None` 缺省取②步建议模式，显式传入时执行强制语义执法 487）
- [ ] **新增用例端口 2 个**（薄透传+守卫——CreateCheckpointUseCase/RecoverCheckpointUseCase 双先例粒度）：
  - `ListCheckpointsUseCase`（plan_id UUID 守卫+透传 list_checkpoints）落 `src/application/use_cases/checkpoint_approval.py` 新文件
  - `ExecuteCheckpointRecoveryUseCase`（plan_id UUID 守卫+confirmed_by 非空守卫 242+透传 execute_recovery——correction 四参数成组校验**不在用例层承载**：`CorrectionRecord` 默认值兜底下部分出现到用例层不可表达，成组约束唯一落位=CLI 层 post-parse，见 AC-2）
- [ ] 组合注入清单：**既有五依赖零变化**（persistent_note_taker/context_compressor/strategic_archive_service/snapshot_repository/event_publisher——恢复记录复用 snapshot_repository、事件复用 event_publisher，**零新依赖**）；`checkpoint_service` 注册块仅升 version v1.1.0（impl lambda 零变化——契约测试 inspect.getsource 注入面断言零适配）；新增注册 2 个（`checkpoint_list_use_case`/`checkpoint_recovery_execute_use_case`，SINGLETON——无状态透传，6-3 用例注册形态同构）
- [ ] 端口契约清单（唯一事实源——禁止语义重复新增）：

| 端口 | 层 | 注册名（composition_root） | 本 Story 动作 |
|---|---|---|---|
| `CheckpointServicePort` | application/ports | `checkpoint_service`（既有 :2293-2308） | **演进 v1.1.0**（+list_checkpoints/execute_recovery）+ 契约测试扩展 |
| `ListCheckpointsUseCase` | application/use_cases | `checkpoint_list_use_case`（新增） | 新增 + resolve 可达测试 |
| `ExecuteCheckpointRecoveryUseCase` | application/use_cases | `checkpoint_recovery_execute_use_case`（新增） | 新增 + resolve 可达测试 |
| `RecoverCheckpointUseCase` | application/use_cases | `checkpoint_recovery_use_case`（既有 :2321-2332） | 复用（CLI checkpoint-show 消费面——零消费方状态终结） |
| `SnapshotRepositoryProtocol` | domain/ports | `snapshot_repository`（:949-963 既有） | 复用零改动（恢复记录同形态承载——OD-3） |
| `EventPublisher` | domain/ports | `event_publisher`（:605-614 既有） | 复用零改动（CheckpointRecovered 发布） |
| `persistent_note_taker`/`context_compressor`/`strategic_archive_service` | domain+application | 既有 | 复用零改动（create 链依赖——本 Story 零触碰） |

- [ ] 组合根 `src/composition_root.py` 新增 2 注册块 + 1 version 升级——**既有注册行零删改**（Task 4 守护：diff 纯新增+单行 version 变更）
- [ ] 契约测试 `tests/contracts/test_port_contract_checkpoint.py` 扩展（PORT_NAMES 增 2 + v1.1.0 断言 + 新方法签名存在性——inspect.signature 键位断言，6-4 CR1-R3 先例）

#### 端口契约清单执行约束（强制）

- [ ] 本清单是唯一事实源（Single Source of Truth）；实现中确需新端口时回 Task 0 补登记 + Contract Gate + 契约测试，禁止边写边加
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象（6-1/6-2/6-3 纪律沿袭）
- [ ] 禁止绕过 `SnapshotRepositoryProtocol` 直持 Redis 客户端（恢复记录存取=经端口 save/load——OD-3 承载裁定的纪律面）
- [ ] 禁止绕过 `EventPublisher` 直发事件（⑤步发布=经既有端口）

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> 完整检查清单详见 [`sisys-uni-exception-design.md §3.12`](../../docs/architecture/sisys-uni-exception-design.md)；编码分配策略详见 §3.3。

- [ ] **新增领域异常 2 个**（planning 段 **486-489 预留段取码**——OD-7；`_code_ranges.py:189` 成文「486-489 留 6-6 恢复执行面」+ 6-5a story L276「成文预留不可占」双处钦定的兑现），继承 `BusinessException`，落 `src/domain/exceptions/planning_exceptions.py` 就地追加：

| 异常类 | code | 触发场景 | HTTP 映射建议 |
|---|---|---|---|
| `CheckpointRecoveryError` | EXCEPTION_486 | 恢复执行编排强制环节失败（**try 面扩包③④两处 save**——修正一体场景③步 apply_correction 内 save 失败与纯恢复场景④步恢复记录 save 失败统一归 486（不扩包则 StorageError(103) 裸逃逸破坏六码全景——save 无 try 是 6-3 冻结行为面、486 包裹是恢复编排层职责）；构造纯内存零失败面；except 面钦定 `StorageError`（RedisSnapshotStore.save 唯一异常出口 :148-150 包装一切异常）；AC-7 fail-loud；482/484/480 在 save 之前触发经既有触发点透传不并入；⑤发布独立降级面不属 486） | 500 |
| `RecoveryModeConflictError` | EXCEPTION_487 | 模式强制执法拒绝（建议 REPLAY 而请求 OVERRIDE——or.md L622 不变约束「修改影响≥2 个后续 Checkpoint 强制采用 Replay 模式」） | 409 |

- [ ] **485 段内空洞维持 + 488/489 继续预留**（本 Story 取 486/487 两码后 planning 段残留位——485 属 OD-7 三处成文钦定「独立码不设」的段内空洞，缺席守护保留；登记注记维持）
- [ ] **复用码零改动**：242（checkpoint_no 三重守卫+plan_id 守卫+CLI 层四参数成组）/480（`_load_or_480`）/482（apply_correction 乐观锁第二触发点透传）/484（verify+修正前置门禁透传）——六码全景见 AC-7
- [ ] message 组合语义：486 默认 message 组合 reason（`f"Checkpoint 恢复执行失败: {reason}"`——6-3 R1-F3 组合语义先例直接继承：根因对 CLI/API 操作者可见）；487 message 携带建议模式与请求模式（`f"恢复模式冲突: 影响≥2 个后续 Checkpoint 强制 Replay（建议={recommended}, 请求={requested}）"`——可理解性裁决面）
- [ ] 完整 5 项 Checklist 逐项履行：①定义文件（planning_exceptions.py 就地追加，含模块 `__all__`）→ ②`_code_ranges.py` `_CLASS_TO_SUBDOMAIN` 注册 + 唯一性 grep（`grep -rn "EXCEPTION_48[6-9]" src/` 预检——仅注释无类占用）→ ③`__init__.py` 暴露 + `EXCEPTION_HTTP_MAP`（500/409——键为异常类对象非码字符串，新类不注册 HTTP 回落 400，故 map 增量是强制项）→ ④码段校验测试（test_error_code_uniqueness.py + test_code_ranges.py 反射自动承载；**test_exception_handlers.py :385 精确集合相等断言须手动扩 expected_types 两类**——「全绿」以该手动扩展为前提）→ ⑤设计文档同步（§3.12 C4 🔴强制：sisys-uni-exception-design.md §3.3.2 编码分配表 :757 预留行拆分为 486/487 实占行 + 488/489 预留行 + §3.7 错误码注册表新增两行）
- [ ] **6-4 让位义务（强制回归面）**：占 486/487 后更新两处缺席断言——`tests/unit/architecture/test_json_chain_of_thought.py:338-360`（断言内 `range(485, 490)` 收窄为残留码元组 `(485, 488, 489)` 并注明 486/487 已由 6-6 占用；**守护红实证仅此侧可观测**——其扫描面含 src/domain 全目录 rglob，planning_exceptions.py 落地 `code="EXCEPTION_486"` 字面必红）+ `tests/acceptance/test_acceptance_json_chain_of_thought.py:2150-2171`（同款收窄；**该侧四守护文件按现计划零 EXCEPTION_486 字面（EXCEPTION_HTTP_MAP 类对象键控、yaml/router 零触碰），落地后不会红——收窄属预防性对称与 docstring 注记兑现，非红实证**；`_code_ranges.py` 注释更新禁写 EXCEPTION_486/487 完整字面以防误触）；两处 docstring「6-6 落地新增 EXCEPTION_486+ 时预期让位更新」注记同步兑现
- [ ] **Story 异常契约文档**：本表即小节（code/parent/触发场景齐备）
- [ ] 异常路径 Gherkin 场景纳入 Edge Cases（AC-7 场景钉死）

#### API 契约 (API Contract)

- [ ] **零 REST API 变更**（BLM/Checkpoint 面 REST 接线归 7-2——6.1-DF5 先例第五次沿袭；Epic 6 全系列 CLI 入口形态）
- [ ] CLI 新增子命令 **3 个**（argparse 扁平子命令族——`build_parser()` 内 `add_parser` 块 + `main()` 分发分支 + `_run_<cmd>_cli` 五步定式函数，`_run_checkpoint_create_cli` agent_cli.py:1008-1065 直系样板（DomainError `[code]` exit 1 在 :1059-1062）；现存 10 子命令扁平族无重名冲突）：
  - `checkpoint-list --plan-id`（必填）：表格输出清单（checkpoint_no/stage/completed/version/sync_status 五列钦定；**形态钦定**：纯标准库动态列宽表格——两遍法 `max(len(header), max(len(v)))` 算列宽 + `str.ljust` 对齐 + 表头行 + ` | ` 分隔（弃 ASCII 边框）；值域有界全表 ≤64 字符远小于 128 行宽、无需截断策略；completed 输出英文 true/false 保持单测值级断言直白（输出即契约——R1-F18 同哲学）；agent_cli 现无表格先例，此为钦定新形态）
  - `checkpoint-show --plan-id --checkpoint-no`（双必填）：输出 9 键恢复视图（resolve `checkpoint_recovery_use_case`——**既有注册的首个消费方**）
  - `checkpoint-recover --plan-id --checkpoint-no [--correction-type V --previous-value V --new-value V --applied-by V] [--mode {replay,override}] [--confirm] [--confirmed-by V]`：
    - 四个 --correction-* 参数**成组约束**（部分出现 → 242——**CLI 层唯一落位** post-parse 检测+构造真实 EntityValidationError，见 AC-2）
    - `--mode` 缺省取引擎建议；`--mode override` 违反强制语义 → 487；**转换层位钦定**：`add_argument("--mode", choices=("replay","override"))`（:355 choices 先例）+ CLI 层 `RecoveryMode(args.mode)` str-Enum 按值构造 → 用例/端口全链 entities 枚举（events 大写转换仅在引擎⑤步 to_event_recovery_mode 一处）
    - 无 `--confirm` = dry-run（影响评估输出+exit 0+三零；**评估输出含将应用的修正五参数展示**（带 --correction-* 时——仅展示零应用）与 confirmed_by 缺省链提示；风险等级经 assess_consistency_risk 同源计算——与引擎⑤步单一事实源；**冲突组合评估语义**：dry-run 带 `--mode override` 而建议 REPLAY 时评估输出附「该组合 confirm 必拒 487」预检提示——执法在执行态，评估态展示建议/请求双模式并预警；**预计耗时/成本展示 defer 声明**：or.md L484「前端展示预计耗时与成本」MVP 不承载——无成本模型（cost 恒 0.0 事后字段非事前预估），预估展示随完整评估协议归 Epic 10 Story 10.3）；有 = 执行（AC-3/AC-4）
    - `--confirmed-by` 双态语义钦定：dry-run 不要求（评估态未确认）；confirm 执行路径必填——缺省取 `--applied-by`（修正场景）或 CLI 层+用例层双落位守卫 242（纯恢复场景；无修正且无 confirmed-by 时要求显式提供，审批人身份不可缺省空）
    - exit 0 口径：dry-run 评估完成 / 恢复记录落库成功（发布降级不改 exit code——AC-4；exit 1=DomainError `[code] {message}` stderr、exit 2=用法错误——main docstring :1361 既有语义；**缺参与守卫分工**：缺参（--plan-id 等未提供）=argparse required 拦截 exit 2；显式传入的空串/畸形/越域/非 canonical 别名形态（""、cp3、3、CP-99、CP-01）统一 242 守卫）
- [ ] CLI 参数守卫前缀统一：`[EXCEPTION_xxx]` 形态（6-3 R1-F18 真实异常构造纪律——禁字面前缀）

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2, **msgpack**
- **本 Story 特别注意**：双枚举转换纯函数纯标准库；恢复引擎/VO 在应用层（依赖 domain 枚举合规）；**本 Story 零 infrastructure 改动**（恢复记录经既有 RedisSnapshotStore 通用 KV 承载——OD-3，与 6-3「唯一 infra 改动=白名单扩列」对照本 Story 是零 infra 改动 Story）

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

**设计规则 R1~R4 落点**（用户钦定）：
- **R1** 领域层统一抽象基础端口 → 复用 `SnapshotRepositoryProtocol`/`EventPublisher`（本 Story 零新增基础端口）
- **R2** 应用层端口组合注入基础端口 → `CheckpointServicePort`（演进）既有五依赖组合维持——list/execute 两新方法复用同组依赖（零新依赖演进）
- **R3** 基础设施层实现端口并管理技术 → 复用 `RedisSnapshotStore`（恢复记录通用 KV 承载）零改动；零新基础设施实现
- **R4** 接口层适配外部请求 → CLI 三子命令（agent_cli.py 既有五步定式）；无 REST 面

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_checkpoint_recovery.feature`（OD-11 命名——功能名族，禁故事编号后缀）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_checkpoint_recovery.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）——钉死 **14 场景**（AC-1×2 / AC-2×2 / AC-3×3 / AC-4×2 / AC-5×1 / AC-6×2 / AC-7×1 / 收尾×1，Task 0.4 定稿钉死确定值并全文同步，禁范围值进入后续 Task）；**epic 架构测试三项落位对账**（epics L2325-2327）：摘要显示测试→S1/S2、参数修正测试（修正后正确恢复执行）→S3+S9、审批流程测试→S8/S9（OD-5 显式对账）——功能等价重分布

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（模块级 `event_loop` fixture + `_run_async` helper——6-1/6-2/6-3 三件套）
- 同一中文文本可能需要同时支持 given/when 装饰器（共用文本按模块各自重新定义一份 @given——6-x 样板实证形态；Given/When 语义复用时写不同文本）
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——本 Story 六码全景 242/480/482/484/486/487，验收面承载五码 = 480（不存在键恢复执行）/484（checksum 损坏恢复执行）/482（旧基线修正）/242（畸形 checkpoint_no+四参数部分出现）/487（强制 Replay 违反）；486（编排失败注入）与发布失败注入归单测层 AsyncMock 承载（no-mock 红线互斥裁定——6-2 R3-4 先例（6-3 沿用）：验收/集成层无法构造的真实服务失败归单测层）
- **R6 模板合规**：feature/py 组织结构对齐 `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`/`.py`——`# language: zh-CN` 中文 Gherkin + AC 横幅注释分组（`# ===` 分隔）+ `@scenario(...)` 多行字面量路径绑定 + **14 场景全绑定**（R6 文件自身仅绑定 30 场景中 17 个属旧模板欠账，新文件禁沿用）；pytestmark/context dict/`_run_async` 由 6-x 三件套基建承载；**断言必须真实**（禁 then-pass 占位）；装配形态对齐 6-3（真实服务链 + Fake LLM/Fake Embedding 双豁免（外部 SaaS）+ 延迟 import 纪律 + 场景三属性分档表 docstring + teardown 链「断言失败也执行」）
- **BDD 时长纪律（事实口径）**：6-3 形态裸 `_run_async` **无实际硬超时**（conftest `run_with_bdd_timeout` 30s 机制存在但全仓唯一消费方是 test_acceptance_llm_client.py（真 LLM 客户端文件），6-3 checkpoint 验收未接线、pytest-timeout 装而未配；Fake LLM 链无挂死面）——耗时纪律靠场景成本设计承载：多 checkpoint 前置（AC-3 Replay 场景需 3 点：恢复点+2 后续）分 Given 步骤逐个创建（每步一次全链——6-3 R2-F6 先例；实测基线：单创建链 ~0.14-0.23s（2026-11 实测），最重场景粗估 3-5s 无压力）；AC-5 并发场景 5 plan×（1 创建+1 恢复）gather 并行执行（**创建与恢复均入 gather——每任务会话隔离钦定**：per-plan 协程体内自建 `AsyncSession`+`set_session()`（PEP 567 task 级 context 拷贝不外泄，深层 `get_session()` 调用期解析自动命中本任务会话）——6-3 装配链共享单 AsyncSession 形态下 gather 必触发 SQLAlchemy 并发会话防呆，装配契约在 Task 0.5 落档；Fake LLM 是 AsyncMock 固定返回值单循环无线程安全问题）；AC-6 性能采样场景独立化（20 轮窗口直调——6-3 AC-8 形态）
- **场景分化维度表（Task 0.4 钉死输入——含收尾共 14 场景全枚举；S 编号为 6-6 自有编号，跨故事引用一律带故事号前缀）**：AC-1×2 = plan 级清单（3 点全列+sync join+空 plan 空清单边界）/单点详情（9 键+四要素显示——**经 CLI checkpoint-show 入口保红**，见 Task 0.6）；AC-2×2 = 修正往返（history 追加+**连续修正两条累积**+版本递增+checksum 绿——**经 ExecuteCheckpointRecoveryUseCase 修正路径保红**）/修正异常（482 旧基线+242 部分参数双红+**畸形 checkpoint_no 242**——AC-7 畸形面在此承载；482 腿经编程面 apply_correction 构造——execute_recovery 基线引擎内部取②视图，单线程不可构造旧基线（设计使然））；AC-3×3 = Override 执行（恢复记录+**pending_sync 一点**（3 点=CP-1/CP-3/CP-5 恢复 CP-3、后续 CP-5 一点——上限 1 见 AC-3 钦定）+事件+**恢复后再查清单验证 in_sync+pending_sync 两态**+**CP-8 尾点无后续 low 风险边界**（**独立第二 plan 单点 CP-8 恢复承载**——同 plan 二次恢复会单键覆盖洗掉第一 plan 的三态标记（L177 注记①陷阱），故尾点边界用独立 plan 隔离））/Replay 执行（invalidated+指引+**恢复后再查清单 invalidated 态**——与 S5 合并覆盖 sync 三态全谱）/模式冲突 487（零副作用）；AC-4×2 = dry-run 三零（**含带 --correction-* 的评估输出展示断言**）/confirm 执行+修正恢复一体（--correction-* 与 --confirm 同给——AC-3 VC 落位）+outbox 恰一行（checkpoint_id+plan_id 双通道值级——预期值单源 Outcome.recovered_snapshot_id）；AC-5×1 = 5 并发独立 plan 互不干扰；AC-6×2 = 摘要 P95<200ms（show 窗口 20 轮+**list 窗口同门禁**——AC-6 VC 落位）/恢复执行窗口+成功率（采样矩阵钉死：Override×5（建议模式单点 plan）+Replay×5（显式 --mode replay 单点 plan——OD-6 方向性执法「弱替强允」的消费面复用，每样本省 2 次创建链）共 10 次恢复，逐次窗口 <15s+全读回；**窗口载体与蕴含声明**：断言值=Outcome.execution_ms（①~⑤ 组装点窗口 ⊇ ②~⑤ 引擎声明窗口，含①守卫解析差为保守方向）；逐次 <15s 断言严格蕴含 P95<15s≤P95<60s 双门禁——工程冗余断言口径成文）；AC-7×1 = 异常五码分立验收面（480/484 恢复执行入口——242/482→S4、487→S7 已承载，本场景补 480/484 两条）；收尾×1 = src 与四测试目录完成清单存在性断言（Task 7.3 承载）
- **逐场景调用面矩阵（Task 0.5 钦定——验收步骤的驱动面）**：S1/S3/S4(242 腿)/S5/S6/S7/S9/S10/S12/S13 = **编程面**（用例/服务直调——断言锚 Outcome/恢复记录/事件在编程面单源可达；S12 采样窗口=引擎编排窗口编程面口径）；S2/S8 = **CLI 面 in-process 直调** `_run_checkpoint_show_cli`/`_run_checkpoint_recover_cli`（dry-run 是 CLI-only 状态必须驱动 CLI；**每次 CLI 直调前 `get_resolver().clear_singleton()` + `clear_scoped()` 双清钦定**——CLI 函数体内 `asyncio.run` 新建 event loop+resolve，若全局 resolver 已在场景 loop 上 bootstrap：①单例实例绑旧 loop（「Event loop is closed」）；②`snapshot_repository` 是 SCOPED 注册——`clear_singleton()` 只清 `_instances` 不清 `_scoped_context`，scoped 残留的旧 store 持死 loop 客户端且 `RedisSnapshotStore.load` 异常全吞返 None → show 误报 480/sync join 假 in_sync 的**静默失败**（R3 实跑证伪单清形态）；双清先例 test_acceptance_markdown_report.py:145-148；**禁重新 bootstrap**——registry spec 持久+`_ensure_bootstrapped` 自动短路，二次 bootstrap 抛 ConflictError，双清实例即可）；show 入口经 CLI 保红兼证 CLI 接线；S4(482 腿)/S11 采样 = 编程面（S11 采样窗口钉死=recover_checkpoint 数据面窗口+list_checkpoints 窗口——经 CLI 进程面采样会把 ensure_bootstrapped+asyncio.run 建连开销计入窗口冲破 200ms 口径）；**CLI 交互面的完整参数/输出覆盖由 `tests/unit/interfaces/cli/test_agent_cli.py` 承载**（验收只覆盖 S2/S8 两态关键路径 CLI 形态）；S14 收尾=src 与四测试目录存在性断言，无服务调用面（不适用本矩阵）
- **pytestmark**：显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.database, pytest.mark.redis, pytest.mark.qdrant, pytest.mark.minio, pytest.mark.xdist_group("blm-planning-perf")]`（marker 名以 pyproject 注册为准——`database` 非 `postgresql`，6-3 R2-F23 钦定；xdist_group 整模块 pytestmark 级——与 6-3 验收+集成同组串行，互锁结构前提 R8-F2 注记继承）；服务不可达环境 `pytest.skip()` 动态跳过（禁 `@pytest.mark.skip` 写死）
- **创建侧值域纪律（6.3-R1-DF1 互锁解除继承）**：本 Story 验收/集成的 checkpoint 创建侧 **stage_id 一律取 performance_gap**（CP-1 对应的 stage 值——与 checkpoint_no 编号无关，CP-3/CP-5/CP-8 创建同用此值；禁用 market_insight 值域 stage_id——6-2 侧 LIKE 无 plan_id 过滤通道会捕获假红；6-3 R6-6 钦定直接继承）；**创建侧 CheckpointReached 行照常产生**（既有 create_checkpoint ⑤步无条件发布——测试前置创建 3/5/10 点时每点一行），恢复链新增发布的是 CheckpointRecovered（不同 event_type 通道，与 6-2 LIKE 负向断言面正交——performance_gap 值域下 LIKE 臂不命中），互证查询无需 LIKE 通道；**创建侧行的 teardown 清理沿用 6-3 teardown ②步同款定向 DELETE**（见隔离约束表——键计数净增 0 纪律覆盖创建侧行）
- **6-3 回归面（强制）**：CheckpointServicePort 扩展后全仓 grep 消费方测试——6-3 验收 13 场景/集成 5 场景/service 单测（969 行）/契约/CLI/架构全绿零适配（纯新增方法+version 升级预期零适配；`spec.version.startswith("v")` 断言兼容 v1.1.0）；发现失配即回 Task 2/3 修实现而非改测试

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（两 VO 键契约/恢复记录 12 键/端口两方法签名/异常 486-487 分配/CLI 三命令/OD 裁定落档）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态 = 步骤函数运行期失败：延迟 import 抛 `ImportError`（缺失类名/方法）或断言步 `AssertionError`；收集期零错误本身即延迟 import 纪律的自证——6-2/6-3 先例）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：① 组合根新注册 resolve 可达（checkpoint_list_use_case/checkpoint_recovery_execute_use_case——注入链非 None）+ checkpoint_service v1.1.0 resolve 可达 ② CheckpointRecovered 真实发布验证（发布点代码位+outbox 落行 checkpoint_id 通道+双登记零 diff+auto_trigger 监听在位）③ checkpoint_recovery_use_case 首消费方接线（CLI checkpoint-show）④ CLI 三命令入口接线（单测用例承载）；「已实现未接线」组件登记 deferred-work
- [ ] **锚定义务六条处置落档**（Task 0.7——deferred-work 台账更新，逐条处置见 Dev Notes「锚定义务清单」）：L17 langgraph retry/timeout / L170 消费基建四件 / L348（6.3-R1-DF1）/ L349（6.3-R1-DF2）/ L350（6.3-R3-DF1）/ 6-4 两处 485-489 缺席断言让位

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿（证明断言活着） |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言；6-1 属性形态断裂族三犯+6-3 判别力复评教训详见 Dev Notes）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 双枚举+风险等级纯函数 | entities↔events 枚举映射（入参域内显式映射——枚举闭集下非法值经类型系统不可构造，无 else raise 面）/assess_consistency_risk 三分支矩阵 | `tests/unit/domain/services/test_recovery_mode.py`（扩展） | Task 1 |
| **TDD 单元测试** | 领域异常 | 486/487 构造/message 组合/context/to_dict/HTTP 映射 | `tests/unit/domain/exceptions/test_planning_exceptions.py`（扩展）+ `tests/unit/interfaces/api/test_exception_handlers.py`（扩展） | Task 1 |
| **TDD 单元测试** | 读面（list_checkpoints） | probe 全量/升序/sync_status 三态推导/空族空清单/plan_id 守卫 | `tests/unit/application/test_checkpoint_service.py`（扩展——TestListCheckpoints 组） | Task 2 |
| **TDD 单元测试** | 恢复执行引擎（execute_recovery） | 五步编排调用序/模式裁定+487/双模式分支/恢复记录 12 键/事件构造与容错/execution_ms 窗口/486 fail-loud | `tests/unit/application/test_checkpoint_service.py`（扩展——TestExecuteRecovery 组） | Task 3 |
| **TDD 单元测试** | 用例层 | List/Execute 两用例守卫（UUID/confirmed_by——四参数成组归 CLI 层）与透传 | `tests/unit/application/use_cases/test_checkpoint_use_case.py`（扩展） | Task 2/3 |
| **TDD 单元测试** | CLI 三命令 | 参数解析/dry-run 两态/exit code/六码 stderr 形态（486 经 CLI 单测注入承载）/五步定式 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 2/3 |
| **TDD 领域异常测试** | 编码唯一性/子域范围 | 486/487 注册后全量反射扫描 | `tests/unit/domain/exceptions/test_error_code_uniqueness.py` + `test_code_ranges.py`（既有自动承载） | Task 1 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~7 全覆盖） | `test_acceptance_checkpoint_recovery.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_checkpoint_recovery.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约 | v1.1.0 演进/新用例注册/resolve 可达/注入链 | `tests/contracts/test_port_contract_checkpoint.py`（扩展） | Task 2/4 |
| **TDD 契约测试** | 事件通道守护 | CheckpointRecovered 发布接线+双登记零 diff+冻结键数 56 零变化+6-3 既有断言零修改复跑 | `tests/contracts/test_event_channel_mapping_checkpoint_recovery.py`（新建） | Task 4 |
| **SDD 架构验证** | 六边形架构约束 | domain 零依赖（转换函数+异常扩展后复核）/服务落位/发布点守护/键族三前缀判别/6-3 行为面零触碰守护 | `tests/unit/architecture/test_checkpoint_recovery.py`（新建，epics L2344 钦定名） | Task 6 |
| **集成测试** | 真实链协作 | 恢复执行全链（真 Redis/PG+Fake LLM/Embedding）/outbox 落行/恢复记录 round-trip/并发 5 路/6-3 链回归 | `tests/integration/test_integration_checkpoint_recovery.py`（新建，OD-11） | Task 5 |
| **回归测试** | 6-3 消费方适配 | 端口演进向后兼容（验收 13/集成 5/service/契约/CLI/架构全绿零适配） | 6-3 既有测试文件（预期零修改） | Task 4 |
| **回归测试** | 6-4 断言让位 | 两处 485-489 缺席断言收窄后守护测试通过 | `tests/unit/architecture/test_json_chain_of_thought.py` + `tests/acceptance/test_acceptance_json_chain_of_thought.py`（两处收窄——本 Story 唯一预期修改的既有测试对） | Task 1/4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance --cov-fail-under=80`——**禁裸收集**：无路径回落 testpaths=tests 即记忆钦定的挂起形态；addopts 已带 --cov=src 无需重复）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application` 语义——**口径注记**：addopts `--cov=src` 累积使 TOTAL 行为全 src 并集，分层百分比按报告内 application 组 per-file 行人工聚合判读，或以 `-o addopts` 剥离后单跑）- **P1 阻断门禁**（本 Story 主改动层——epics 钦定）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）——转换纯函数+异常扩展部分遵循
- [ ] **集成测试覆盖率 ≥75%**（epics 钦定——**口径钦定**：集成测试对本 Story 交付面的行覆盖，`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_checkpoint_recovery.py --cov=src.application.services.checkpoint_service --cov=src.application.use_cases.checkpoint_approval --cov-report=term-missing` 人工核新增方法行 ≥75%；禁「只跑集成目录+--cov=src 全量」的无意义口径）
- [ ] **关键路径 100% 覆盖（枚举分支逐一有专属用例口径）**：execute_recovery 五步调用序（含 487 拒绝零副作用分支/486 fail-loud 分支/发布降级分支）/ list_checkpoints 三态 join（含无恢复记录全量 in_sync 边界）/ dry-run 三零 / CLI 两态 / 六码异常各一（验收五码+单测 486）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`——与 CLAUDE.md/6-3/6-5b 同款双目录）
- [ ] **MyPy 类型检查通过**（`mypy src/`——当前基线 752 零错误不回退（6-5b R4 实证基线，新增面零新增错误））
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`；**push-stage 注记**：validate-schemas/validate-openapi/pytest-bdd 三钩子 stages=[push]，`--all-files` 默认 commit stage 跳过它们——全覆盖补 `--hook-stage push` 或以逐提交 push 证据链收窄（6-3 先例））

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **Redis 键清理** | 恢复记录第三键族纳入 teardown 链（`_snapshot_session_ids` 登记面扩展——`blm-checkpoint-recovery-{plan_id}` 键在恢复执行前预登记，delete 不存在键 no-op）——6-3 R1-F1 键清理面断裂教训直接继承 | 键累积 30 天污染 |
| **记录壳覆盖** | 验收侧 `_RecordingNoteTaker` 记录壳（6-3 R2-2）复用覆盖创建链缓存键；恢复链无新缓存键（零 LLM/零笔记——引擎纯数据面） | 负向场景泄漏窗口 |
| **outbox 定向清理** | CheckpointRecovered 行按 event_id/metadata.plan_id 精确 DELETE（6-3 teardown ②步同款）；**创建侧 CheckpointReached 行同款定向 DELETE**（创建前置链每点一行——含在键计数净增 0 纪律内） | 事件行累积 |
| **事务隔离** | 集成测试自包含装配类模式（真实提交+定向 DELETE——savepoint 不适用于含 L2/outbox 落库链，6-3/6-4 钦定口径） | 数据泄漏 |
| **资源唯一性** | 测试数据使用 UUID plan_id（并发 5 路=5 独立 plan） | ID 冲突 |
| **外部服务隔离** | Redis/PG/Qdrant/MinIO 真实服务探测 skip；Fake LLM/Fake Embedding 双豁免（创建前置链需要——恢复链本身零 LLM） | 环境不一致 |
| **并行隔离** | xdist_group("blm-planning-perf") 整模块挂法——与 6-3 验收+集成同 worker 串行（互锁结构前提，6-3 R8-F2 注记继承） | 跨文件执行窗口重叠 |
| **asyncio 上下文** | BDD 步骤 event_loop.run_until_complete（三件套）；集成裸 async def（asyncio_mode=auto）；**并发场景 asyncio.gather 在 async 函数内**（禁多 event_loop 交错） | 循环关闭错误 |
| **gather 会话隔离** | AC-5/集成③ 的 gather 路径**每任务自建 AsyncSession + set_session()**（PEP 567 task 级 context 拷贝不外泄；共享单 AsyncSession 下并发写 outbox/归档必触发 SQLAlchemy 并发会话防呆 `InvalidRequestError`——非概率问题，PG 网络 IO 必产生 await 交错点）；**每任务会话生命周期 try/finally 收口**：begin→执行→commit（异常 rollback）→close——5 并发任务会话不关闭会耗尽连接池 | 并发会话防呆必红/连接池耗尽 |
| **性能采样纪律** | 期望常量独立构造（200ms/15s/键清单模块级字面量）；采样前预热含首次真实 load（连接池建立——R8-F5 注记继承） | 恒真/失真 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（定向 DELETE 例外已钦定——6-3 模式）
- ❌ autouse fixture 删除全局匹配资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ pytest-xdist 并行时 BDD 步骤内 asyncio.run()
- ❌ asyncio.Lock 使用实例变量
- ❌ 裸 `tests/` 运行（显式四目录）

**验证要求：**
- [ ] 并行测试 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance -n 8` 通过（显式四目录——裸 tests/ 挂起；-n 8 为对 addopts -n auto 的有意 cap——6-3/6-5b 同款+DF3 负载教训）
- [ ] 无随机失败**等效证据链**（6-3 先例形态，与 Task 7.2 双轮口径统一）：四目录全量双轮零失败+验收单文件 ≥5 轮+关键场景（S5/S9/S10/S12）场景级多轮复跑稳定
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 清单与摘要查看（8 键 VO+sync join+9 键详情） | Task 2 | 2.1~2.6（list 方法+VO+用例+CLI） | `test_checkpoint_service.py`（TestListCheckpoints） |
| AC-1 | 四要素显示+空 plan 边界 | Task 0/7 | 0.4 场景 S1/S2；7.x 收尾 | 验收 feature/py |
| AC-2 | 修正往返+checksum 绿 | Task 3 | 3.x（引擎修正步——apply_correction 复用） | 验收 S3 |
| AC-2 | 242 四参数成组+482 旧基线 | Task 3 | 3.x（用例守卫+CLI 层成组检测） | 验收 S4+`test_checkpoint_use_case.py`（扩展） |
| AC-3 | Override 分支（pending_sync+medium 风险） | Task 3 | 3.1~3.4（引擎） | 验收 S5 |
| AC-3 | Replay 分支（invalidated+指引） | Task 3 | 3.1~3.4 | 验收 S6 |
| AC-3 | 模式强制 487 零副作用 | Task 1/3 | 1.x（异常）+3.x（执法点） | 验收 S7 |
| AC-4 | dry-run 三零+两态 | Task 3 | 3.5（CLI 两态） | 验收 S8+CLI 单测 |
| AC-4 | confirm 执行+outbox 恰一行+发布容错 | Task 3/4 | 3.1/3.2（引擎事件构造与发布）/4.2（守护） | 验收 S9+集成② |
| AC-5 | 5 路并发互不干扰 | Task 3/5 | 3.x（引擎并发安全）+5.x（集成） | 验收 S10 |
| AC-6 | 摘要 P95<200ms/恢复窗口/成功率 | Task 2/3 | 2.x/3.x（窗口实现）+0.4（S11/S12） | 验收 S11/S12 |
| AC-7 | 六码分立+CLI stderr 形态 | Task 1/3 | 1.x（486/487）+3.x（透传） | 验收 S13+单测 |
| 全 AC | 端口 v1.1.0 契约+接线 | Task 2/4 | 2.x/4.1 | 契约测试扩展 |
| 全 AC | 收尾清单断言 | Task 7 | 7.3 | 验收 S14 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-7（全部）

> **目的：** 在进入代码实现前，明确事件裁定、VO/恢复记录键契约、端口契约、异常码分配、CLI 入口、验收场景与架构边界。

- [ ] Subtask 0.1: 冻结数据模型规范——CheckpointSummaryView 8 键 / CheckpointRecoveryOutcome 10 键（含 recovered_snapshot_id 断言锚——修正一体路径 Outcome 值=str(sealed.snapshot_id) str 化；无修正路径 new_state_version=②视图 state_version）/ 恢复记录 state_data 12 键 / **execution_ms 三窗口钦定**（事件 execution_delay_ms=①~④⑤构造前 perf_counter 差；恢复记录 execution_ms=①~④构造点差；Outcome.execution_ms=①~⑤组装点差——三窗口同起点递进，Task 0 成文）/ sync_status 三值域与推导规则（含单键覆盖读面注记+**恢复记录 load 失败/JSON 损坏同归 None→全量 in_sync 的退化语义注记**——RedisSnapshotStore.load 异常全吞实证+**②步后续 probe 半途失败边缘**：个别 hget 失败→后续计数静默缩水→建议模式可能降级 Override 弱化执法（锚点 load 失败→480 捕获、仅部分失败滑过——6-3 继承冻结面+人工确认在环，deferred-work 登记，Epic 10 区分「不存在」与「加载失败」）+**TTL 写时序注记**：恢复记录写时恒晚于被标记 checkpoint→记录寿命恒长于被标记者（结构上无孤儿标记窗）；反向边缘=标记后修正刷新 TTL/新写点可活得比记录久→显示回退 in_sync（标记本指向前修正态，回退合理，历史溯 outbox））/ CHECKPOINT_RECOVERY_SESSION_PREFIX 常量 / to_event_recovery_mode+assess_consistency_risk 两纯函数契约
- [ ] Subtask 0.2: 冻结端口契约——list_checkpoints / execute_recovery 签名（含 mode/correction/confirmed_by/created_via 参数语义与 Raises 面）/ 两新用例守卫面
- [ ] Subtask 0.3: 冻结异常契约——486/487 类名、码位、message 组合语义、HTTP 映射、488/489 残留注记；预检 `grep -rn "EXCEPTION_48[6-9]" src/` 零类占用
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_checkpoint_recovery.feature`（14 场景钉死：AC-1×2/AC-2×2/AC-3×3/AC-4×2/AC-5×1/AC-6×2/AC-7×1/收尾×1——AC 横幅分组+中文 Gherkin，R6 模板）
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_checkpoint_recovery.py` 骨架（docstring 场景三属性分档表/pytestmark 全套+xdist_group/14 场景全绑定/模块级期望常量独立构造/三件套+teardown 链扩展恢复记录键族/Fake LLM/Fake Embedding 工厂复用 6-3 形态/装配链基于 6-3 `_assemble_checkpoint_chain` 扩展）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——**红形态逐场景预判**：S1/S4/S5/S6/S7/S9/S10/S12/S13 ≈9-10 场景延迟 import 抛 ImportError/AttributeError（list_checkpoints/execute_recovery/486/487/新用例缺失）；S2/S3/S11 三场景天然路由到 6-3 既有行为面（recover_checkpoint 9 键视图/apply_correction 修正往返/show 窗口数据面已交付）——**其场景文本必须触达新符号**（S2 经 CLI checkpoint-show 入口/S3 经 ExecuteCheckpointRecoveryUseCase 修正路径/S11 经 checkpoint-show CLI 入口+list 窗口）保红；S8 dry-run 的 AssertionError 形态是步骤内 try/except 包裹 ImportError 转断言三零的实现选择（与延迟 import 纪律通则的显式例外声明）；S11 经 **list 窗口（list_checkpoints 新符号）**保红——show 窗口经 recover_checkpoint 数据面采样（采样调用面见 Task 0.5 矩阵——S11 采样=编程面，经 CLI 进程面采样会把建连开销计入窗口冲破 200ms 口径）；S14 收尾 AssertionError（完成清单存在性）；合计 14 场景全红、收集期零错误）
- [ ] Subtask 0.7: deferred-work.md 六条锚定义务处置注记落档（见 Dev Notes 表）
- [ ] Subtask 0.8: 既有资产复核（四 Agent 调研结论主会话已亲验——实施时行号漂移复核）：① CheckpointRecovered 字族与双登记/监听（checkpoint_events.py:40-69/yaml:192-195/router:249-254/auto_trigger:65）② RecoverCheckpointUseCase 与组合根注册（:89-129/:2321-2332）③ checkpoint_service 五方法行为面（call_order 断言族清单）④ CheckpointRecoveryView 9 键 ⑤ 6-4 两处缺席断言现状（architecture :338-360 + acceptance :2150-2171）⑥ `_FROZEN_EVENT_COUNT=56` 基线
- [ ] Subtask 0.9: 链路接线断言清单四项定义（Task 0 完成标志节钦定内容落档）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] 六条锚定义务处置落档

---

### Task 1: 领域层——双枚举转换纯函数 + 异常 486/487（含 6-4 让位）

**关联 AC:** AC-3（模式执法 487）/AC-7（六码分立）

#### TDD 循环 A：双枚举转换纯函数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_recovery_mode.py` 扩展（转换两方向断言：REPLAY→"Replay"/OVERRIDE→"Override" 值级——events 枚举 `.value` 断言防只验类型；**assess_consistency_risk 三分支矩阵逐支钉死**：Override+1 后续→"medium"/Override+0→"low"/Replay+任意（含 ≥2）→"low"——medium 腿是同源消费漂移的唯一可判别腿（low 与事件默认值同值，Replay 腿不可判别漂移）） |
| 🟢 绿 | 实现 `to_event_recovery_mode(mode)` 于 `src/domain/services/recovery_mode.py` 就地追加（纯标准库映射） |
| 🔄 重构 | 类型注解+docstring（引用 6-3 双枚举知悉注记） |

#### TDD 循环 B：异常 486/487 + 6-4 让位

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_planning_exceptions.py` 扩展（486 reason 组合 message 双形态/487 双模式 message）+ `test_exception_handlers.py` 扩展（486→500/487→409 映射+expected_types 精确集合扩两类）+ 6-4 两处断言**先不改**（红实证观测时点=Task 1.5 类落地后、收窄前的中间态：此时 planning_exceptions.py 已含 EXCEPTION_486/487 字面而断言仍 range(485,490)——architecture 侧必红（src/domain 扫描面）；acceptance 侧按现计划不红（四守护文件零字面）——Task 1.4 本身时点守护仍绿（类未落地），不追幻影红） |
| 🟢 绿 | planning_exceptions.py 追加两类 + `_code_ranges.py` 注册（注释更新禁写 EXCEPTION_486/487 完整字面）+ `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP`；随后 6-4 两处 `range(485, 490)` 收窄为残留码元组 `(485, 488, 489)`（docstring 注记同步——「预期让位更新」兑现）；sisys-uni-exception-design.md §3.3.2/§3.7 同步（C4） |
| 🔄 重构 | 码段校验测试全绿复核（唯一性/子域范围自动反射） |

- [ ] Subtask 1.1: 🔴 红 — 转换函数+风险等级函数失败测试（值级断言）
- [ ] Subtask 1.2: 🟢 绿 — 两纯函数最小实现
- [ ] Subtask 1.3: 🔄 重构 — 转换函数优化
- [ ] Subtask 1.4: 🔴 红 — 486/487 异常失败测试（含 6-4 守护红实证——architecture 侧）
- [ ] Subtask 1.5: 🟢 绿 — 异常落地 + 6-4 两处让位收窄 + 设计文档同步
- [ ] Subtask 1.6: 🔄 重构 — 5 项 Checklist 全链复核（grep 自查/测试全绿）

**完成标准/Definition of Done:**
- [ ] 转换函数+两异常实现完成
- [ ] 变异实证×2（转换映射改错值→红；487 message 漂移→红）
- [ ] 6-4 让位后守护测试绿
- [ ] domain 覆盖率 ≥90% 维持

---

### Task 2: 应用层读面——list_checkpoints + 用例 + CLI（list/show 双命令）+ 组合根

**关联 AC:** AC-1（清单/详情/四要素/sync join）/AC-6（P95<200ms 读窗口）

#### TDD 循环 A：端口方法 + 服务实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_checkpoint_service.py` 扩展 TestListCheckpoints（probe 全量升序/None 跳过/sync 三态推导矩阵/无恢复记录全量 in_sync/空族空清单——AsyncMock 替身沿 6-3 spec 契约形态；plan_id 守卫 242 归用例单测组（服务层不守卫——见端口节裁定）） |
| 🟢 绿 | 实现 `list_checkpoints` + `CheckpointSummaryView`（ports/checkpoint.py 追加 VO+方法签名；service 实现——`range(1, CHECKPOINT_NO_MAX + 1)` 全量 probe 循环复用 `_load_or_480` 的 load 半边（None 静默语义）+恢复记录 load join+timestamp datetime→isoformat 转换） |
| 🔄 重构 | 序列化契约区 docstring 第四级登记（三前缀+12 键+sync 推导规则） |

#### TDD 循环 B：用例 + 组合根 + CLI 双命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_checkpoint_use_case.py` 扩展（ListCheckpointsUseCase 守卫/透传）+ `test_agent_cli.py` 扩展（checkpoint-list **表格断言形态钦定：表头行精确串（五列头+` | `分隔符）+至少一行值级断言（含 sync_status 三态值与 true/false——禁子串存在性弱断言）**/checkpoint-show 九键输出/UUID 守卫 `[EXCEPTION_242]`/退出码）+ 契约测试扩展（PORT_NAMES+resolve）；TestListCheckpoints 补 **timestamp isoformat 字符串值级断言**（实体 datetime→VO str 转换的漂移哨兵——返回 datetime 对象即红） |
| 🟢 绿 | 实现 ListCheckpointsUseCase + 组合根注册 `checkpoint_list_use_case` + CLI 两命令（五步定式——`_run_checkpoint_create_cli` 直系样板；show 命令 resolve 既有 `checkpoint_recovery_use_case`——首消费方） |
| 🔄 重构 | CLI 输出函数 getattr 属性访问形态（零实体 import 依赖——6-3 `_print_checkpoint_result` 先例） |

- [ ] Subtask 2.1: 🔴 红 — TestListCheckpoints 失败测试
- [ ] Subtask 2.2: 🟢 绿 — list_checkpoints + SummaryView 实现
- [ ] Subtask 2.3: 🔄 重构 — 序列化契约 docstring
- [ ] Subtask 2.4: 🔴 红 — 用例/CLI/契约失败测试
- [ ] Subtask 2.5: 🟢 绿 — 用例+注册+CLI 两命令
- [ ] Subtask 2.6: 🔄 重构 — 输出形态统一

**完成标准/Definition of Done:**
- [ ] 读面全链实现（服务→用例→CLI）
- [ ] 变异实证×2（sync 推导映射反转→红；probe 序号排序破坏→红）
- [ ] `checkpoint_recovery_use_case` 首消费方接线（链路接线断言③兑现）
- [ ] 6-3 既有 service 单测零适配（纯新增方法）

---

### Task 3: 应用层恢复执行引擎——execute_recovery + 用例 + CLI recover（dry-run/confirm）+ 组合根

**关联 AC:** AC-2（修正闭环）/AC-3（双模式+487）/AC-4（两态+事件）/AC-5（并发）/AC-6（窗口）/AC-7（486 fail-loud）

#### TDD 循环 A：引擎五步编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 TestExecuteRecovery 组（五步调用序精确列表断言——含 487 零副作用 save/publish 零调用断言（6-3 call_order 断言形态）+**correction+冲突组合 apply_correction 零调用断言**（裁定②.5 前置的实现漂移哨兵）/模式裁定三分支（None 取建议/冲突 487 于②.5/更强允许）/恢复记录 12 键 exact set+confirmed_by 键**值级**断言/事件构造字段值级（recovery_mode 大写转换/modification_content 投影/metadata 双关联键/**checkpoint_id 传值断言**（修正一体=③步 sealed.snapshot_id、纯恢复=uuid.UUID(②视图.snapshot_id)）/**consistency_risk_level 值级（Override+1 后续="medium" 腿承载——同源消费漂移哨兵；Replay="low" 与默认值同值仅断言不判别漂移）**/execution_delay_ms>0/cost==0.0）/486 fail-loud（**try 面扩包③④两处 save**：修正场景 apply_correction save 注入+纯恢复场景恢复记录 save 注入，双路 side_effect StorageError→486 且事件零发布）/发布降级（publish 失败→Outcome 正常返回+恢复记录在）） |
| 🟢 绿 | 实现 `execute_recovery` + `CheckpointRecoveryOutcome`（ports/checkpoint.py 追加；service 实现——①守卫复用 ②recover_checkpoint 内调 ③apply_correction 条件调用（基线取②视图）④分支+恢复记录构造 save（except StorageError → 486 包裹）⑤事件发布（checkpoint_id 传值钦定+转换函数+assess_consistency_risk 同源+降级容错）+Outcome 组装（窗口 perf_counter+recovered_snapshot_id 单源锚） |
| 🔄 重构 | 步骤拆私有方法（编排可读性）+ Raises 面 docstring |

#### TDD 循环 B：用例 + CLI checkpoint-recover（两态）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 ExecuteCheckpointRecoveryUseCase 测试（UUID 守卫/confirmed_by 非空 242/透传——四参数成组不在用例层）+ CLI 测试（dry-run 三零+评估输出 exit 0（含带 --correction-* 评估展示断言）/confirm 执行/`--mode override` 冲突 487 stderr `[EXCEPTION_487]`/CLI 层部分 correction 参数 242（post-parse 检测+真实 EntityValidationError）/`--confirmed-by` 双态缺省链（dry-run 不要求/confirm 必填）） |
| 🟢 绿 | 实现用例（守卫链）+ CLI `_run_checkpoint_recover_cli`（两态分支：无 confirm 构造评估输出不调引擎——resolve ②步仅取视图+assess_consistency_risk 同源计算+修正五参数展示；有 confirm 全参调用）+ 组合根注册 |
| 🔄 重构 | dry-run 评估输出与 Outcome 展示共用打印函数+同源风险计算 |

- [ ] Subtask 3.1: 🔴 红 — TestExecuteRecovery 失败测试
- [ ] Subtask 3.2: 🟢 绿 — execute_recovery + Outcome 实现
- [ ] Subtask 3.3: 🔄 重构 — 编排私有方法拆分
- [ ] Subtask 3.4: 🔴 红 — 用例/CLI 两态失败测试
- [ ] Subtask 3.5: 🟢 绿 — 用例+CLI recover+注册
- [ ] Subtask 3.6: 🔄 重构 — 打印共用化

**完成标准/Definition of Done:**
- [ ] 恢复执行引擎全链实现
- [ ] 变异实证×8（487 执法点删除→冲突场景假绿/恢复记录 12 键删键→exact set 红/事件 mode 不转换→值级断言红/**恢复起点恒 in_sync 覆盖规则删除→join 红**/**CLI dry-run 分支误调引擎→三零断言红**/**confirmed_by 硬编码空串→值级断言红**/**execution_delay_ms 恒 0.0→红**/**⑤步 checkpoint_id 不传值走 default uuid4→S9 值级断言红（R1-2 P1 史契约的回归锚）**）
- [ ] CheckpointRecovered 发布点唯一性（grep 全仓单构造位——`re.compile(r"CheckpointRecovered\(")` 形态+**排除事件定义文件 checkpoint_events.py**（类定义行假阳性——6-3 契约 :161-170 先例的排除形态复刻，排除文件名按本事件定义文件适配），6-3 契约先例）
- [ ] CLI 两态 exit code+异常路径退出语义正确

---

### Task 4: 契约守护与 6-3/6-4 回归面

**关联 AC:** 全 AC（接线与回归）

- [ ] Subtask 4.1: 端口契约测试扩展收口——v1.1.0 断言（spec.version=="v1.1.0" 精确值——演进留痕）/两新用例 PORT_NAMES+spec+resolve+注入链/新方法 inspect.signature 键位断言
- [ ] Subtask 4.2: 新建 `tests/contracts/test_event_channel_mapping_checkpoint_recovery.py`——发布接线正向（唯一构造位+发布调用）/CheckpointRecovered 双登记等值断言（yaml:192-195 ↔ router:249-254）+`_FROZEN_EVENT_COUNT=56` 冻结键数零变化/6-3 CheckpointReached 既有断言面零修改复跑（断言面在 `tests/contracts/test_event_channel_mapping_blm_planning.py:137-182` TestCheckpointReachedPublishWiring——其唯一构造位 grep pattern `CheckpointReached\(` 字面类名，6-6 新增 CheckpointRecovered 构造不误伤）/`CorrectionApproved` 保持零生产方守护（缺席断言——token 锚 `CorrectionApproved(` 全仓构造位 grep+**排除事件定义文件 correction_events.py**（类定义行假阳性——6-3 契约 :165-166 排除形态先例，排除文件名按本事件定义文件适配；裸 token 会撞 auto_trigger:67/yaml:202-205/router:261-266 三处合法登记，构造位形态 grep 天然避开），6-4 CR1-R3 缺席断言先例）
- [ ] Subtask 4.3: 6-3 回归面全绿——验收 13 场景/集成 5 场景/service 单测/契约/CLI/架构六面零适配运行（纯新增+version 升级假设实证；失配即回 Task 2/3）
- [ ] Subtask 4.4: 6-4 让位后守护复跑（architecture+acceptance 两处 json_chain 文件绿）+ **第七面登记**：`test_planning_exceptions.py` 既有 test_485_not_occupied（:246-250 钉死 485 空洞）与 486/487 新增零冲突复跑——防「扩展文件只跑新增组」执行漂移
- [ ] Subtask 4.5: 组合根 diff 审计——纯新增 2 注册块+1 行 version（零删改断言——git diff 形态检查）

**完成标准/Definition of Done:**
- [ ] 全部契约/守护测试通过
- [ ] 6-3/6-4 回归面零适配实证
- [ ] 事件登记面零 diff 实证

---

### Task 5: 集成测试——真实链恢复执行

**关联 AC:** AC-3/AC-4/AC-5/AC-6（真实服务面）

- [ ] Subtask 5.1: 新建 `tests/integration/test_integration_checkpoint_recovery.py`——自包含装配类 `_RecoveryChain`（基于 6-3 `_CheckpointChain`（:176-472）形态：四真实服务+Fake LLM/Embedding 双豁免+SessionContext 激活+teardown 定向清理扩展恢复记录键族+调用前预登记+**gather 路径每任务 AsyncSession 隔离契约**（per-plan 协程体内自建+set_session——共享装配链会话形态下并发写必触发 SQLAlchemy 防呆））
- [ ] Subtask 5.2: 场景①恢复执行全链（3 点创建（CP-1/CP-3/CP-5）→CP-3 恢复（Override——后续仅 CP-5）→恢复记录 12 键+TTL 30 天双验+**pending_sync 一点**（CP-5——Override 后续 ≤1 是模式执法必然推论，pending_sync 清单上限 1）+CheckpointRecovered outbox 恰一行（checkpoint_id+metadata.plan_id 双通道值级——预期值单源 Outcome.recovered_snapshot_id；真实 publisher 装配 clear_singleton 形态，6-3 集成②先例））
- [ ] Subtask 5.3: 场景②Replay 分支+修正一体（≥2 后续+correction→invalidated 全标+事件 Replay+**checkpoint_id=③步 sealed.snapshot_id 断言**+correction 投影落 modification_content+修正链版本递增读回）
- [ ] Subtask 5.4: 场景③并发 5 路（5 独立 plan gather（创建+恢复均入 gather——每任务会话隔离）——各恢复记录/事件行独立值级断言+无交叉污染）
- [ ] Subtask 5.5: 场景④恢复窗口与成功率（采样矩阵：Override×5 建议模式单点+Replay×5 显式 --mode replay 单点（OD-6 弱替强允消费面），逐次窗口 <15s+10 次恢复全读回）+ 变异验证型×2（期望键族删键/event_type 改名——6-3 Task 5 验证型变异先例）

**完成标准/Definition of Done:**
- [ ] 真实链四场景全绿（服务不可达环境 skip）
- [ ] 恢复记录/事件行清理闭环（跑前后键计数净增 0——6-3 R1-F1 纪律；**含创建侧 CheckpointReached 行**）
- [ ] 集成覆盖率 ≥75%（口径见覆盖率要求节——交付面行覆盖）

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 架构合规（六边形+零改动面守护）

- [ ] Subtask 6.1: 新建 `tests/unit/architecture/test_checkpoint_recovery.py`（epics L2344 钦定名——epics 原文语境为单元测试文件名，6-6 落位 unit/architecture/ 子目录承载 SDD 架构验证（名采纳+落位仓规）；与既有 test_checkpoint.py 并存无冲突）验证器 A：domain 零依赖（recovery_mode.py 两纯函数扩展后+planning_exceptions.py 扩展后 AST 黑名单复核——import-linter 二线防线）
- [ ] Subtask 6.2: 验证器 B：服务落位（list/execute 定义唯一性/端口落位/不越层/禁本地 Protocol）
- [ ] Subtask 6.3: 验证器 C：发布点守护（CheckpointRecovered 唯一构造位=checkpoint_service 恢复引擎；**6-3 五方法行为面零触碰守护**——create/build_snapshot/apply_correction/recover_checkpoint/recommend_recovery_mode 源码签名与 call_order 锚不变）
- [ ] Subtask 6.4: 验证器 D：键族三前缀判别（CHECKPOINT_RECOVERY_SESSION_PREFIX 单源常量+三前缀互异断言+恢复记录 checkpoint_no="" 非完整形态断言）
- [ ] Subtask 6.5: 变异实证×2（pydantic 注入 recovery_mode→A 红/恢复引擎外构造事件→C 红——6-3 Task 6 先例）

**完成标准/Definition of Done:**
- [ ] 四验证器全绿
- [ ] 任何违规导致测试失败
- [ ] 循环依赖检测经 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1~AC-7（最终验收）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已建 14 场景含收尾场景骨架（红阶段已验证）；本 Task 实现 S14 收尾场景的步骤断言（不新增场景数——6-3 R2B-17 off-by-one 家族修复语继承） |
| 🟢 绿 | BDD 步骤实现收尾断言（文件存在性+关键符号存在性——6-3 S13 形态先例） |
| 🔄 重构 | 场景命名收敛、断言统一 |

- [ ] Subtask 7.1: 14 场景全绿（装配回灌——真实服务探测/双 Fake 豁免/teardown 六步链扩展/xdist 同组串行验证）
- [ ] Subtask 7.2: 四目录全量回归（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`——显式四目录）双轮零失败
- [ ] Subtask 7.3: S14 收尾清单断言（src 新增/修改文件+四测试目录文件逐项存在性）
- [ ] Subtask 7.4: 质量收口——ruff+mypy 全过/专项覆盖率（application ≥85% 门禁+checkpoint 域新增面 ≥90%——**口径钦定**：checkpoint_approval.py 全新文件按文件级覆盖即新增面覆盖；checkpoint_service.py 新增两方法按 `--cov-report=term-missing` 人工核 missing 行不落在新增方法区间）/三红线 grep 自查零输出（raise ValueError/HTTPException/内置 Exception 继承——新增行）/提交信息禁 AI 署名
- [ ] Subtask 7.5: 台账终态——deferred-work 六条处置注记核销状态回写+新留项登记（CorrectionApproved 未激活/完整重跑 defer Epic 10——OD 登记）；sprint-status 注记更新

**完成标准/Definition of Done:**
- [ ] 14 验收场景全绿+四目录全量双轮零失败
- [ ] 完成清单逐项确认
- [ ] Story 可进入 `code-review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) + [`sisys-checkpoint-timetravel-design.md`](../../../docs/architecture/sisys-checkpoint-timetravel-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（CheckpointRecovered 既有 reliable 单通道登记）+ Checkpoint 双模式恢复协议（§1 L11-14：≥2 强制 Replay 强一致 / <2 推荐 Override 需人工确认）
- **设计约束:** 领域层零依赖（import-linter 强制）；frozen dataclass 不可变 VO；恢复记录经既有 `SnapshotRepositoryProtocol` 通用 KV 承载（禁直持 Redis 客户端）；6-3 冻结契约零触碰（state_data 13 键/checksum 参与集/五方法行为面）
- **接口治理:** 统一端口注册（PortSpec 演进 v1.0.0→v1.1.0 走 ContractGate 兼容检查——纯新增方法非破坏）、Registry/Resolver、组合根唯一装配、契约优先
- **技术栈:** Python 3.11+ / Redis 7.0+（快照+恢复记录 Hash）/ PostgreSQL（outbox）/ pytest-bdd
- **关键设计条款:** 设计文档 §2.2 Replay 流程（L217-283——应用修改→后续清单→重放日志→逐步执行→回滚→审计）/ §2.3 Override 流程（L285-420——影响评估→人工确认→应用修改→mark_pending_sync→审计→双触发同步）/ §3 第一阶段单点恢复=本 Story；**第二阶段分支对比/合并（§3-4）不在本 Story（归 Epic 10 Story 10.5——FR-SP-09 V1 规划承接，时相以 FR Map 为准）**；or.md L69 (3)/L482-484/L622-624 恢复协议语义

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | **范围边界——MVP 恢复执行形态=数据面恢复+重跑指引，LLM 实质重跑 defer 归 Epic 10**。6-6 交付：摘要读面（list/show）+ 修正入口（CLI）+ 恢复执行引擎（模式裁定执法 487→修正应用→双模式分支→恢复记录→CheckpointRecovered 发布）。**Replay 分支 MVP 语义**：后续 checkpoint 全部标记 invalidated（作废）+ 新基线=修正后快照 + 重跑指引输出（建议新 plan_id 经 `blm-plan` 重跑）——「修改点后所有状态重新计算」的**执行**由人工触发新 run 承载，系统保证旧后续不被误用（标记）+审计可溯（恢复记录+事件）。**四条物理约束**（实质重跑在 6-6 不可达）：① checkpoint 无 agent_id/task 关联——6-3 冻结 state_data 13 键无此二键（6-3 Task 0 冻结唯一版本），重跑语境在快照内不可得，扩键=冻结契约变更+13 键 exact set 断言面 ×4 全红；② 同 plan_id 重跑 482 守卫（blm_planning_service.py:253-259 `completed_steps>0` 即拒）+ BLM 服务无「从第 N 步续跑」入口（RunBlmPlanningUseCase 七步一次跑完）；③ `_runs`/`_PlanRunState` 进程内 dict（blm_planning_service.py:182）——CLI 每次调用新进程跨进程不可用 + SpBlmGraph 无 checkpointer（sp_blm_graph.py:105——:14-15 钦定注释+6-3 锚定义务 #4 裁定不引入维持）；④ 完整形态 checkpoint 仅 summary+compressed_context——`run_insight_step` 的 prior_outputs 需 InsightStepResult 结构化对象链（:337-352）不可从压缩产物重建 + per-step 骨架 TTL 86400 << checkpoint 30 天窗口外不可达。**epics 权威映射背书**：FR Coverage Map L535-538 将 FR-SP-06 Replay/FR-SP-07 评估/FR-SP-08 Override/FR-SP-09 Time-travel 映射 Epic 10 Story 10.2/10.3/10.4/10.5（P1，四条全枚举）；Epic 6 FR 集仅 SP-01~04+UI-11（L2003）——6-6 无独立 FR，深化 SP-03 交互语义（or.md 五.4「用户可反馈与修正该结果，然后继续执行后续任务」）。6-3 OD-1 预期的「Replay 重放重跑后续阶段」按本裁定收敛为「标记作废+指引」，完整协议（拓扑重排/失败回滚/WORM 旧版归档/执行缓存幂等/预计耗时成本预估展示/scheduler 双触发/惰性同步/一致性风险检测算法）归 Epic 10 | epics FR Coverage Map 权威映射 + 四条物理约束代码实证 + BDD 30s 硬超时与 Fake LLM 六步装配成本（6-3 OD-13 ~150 行成本不对称先例）+ YAGNI（P1 FR 不在 MVP 强交付） |
| **OD-2** | **零新增领域事件 + CheckpointRecovered 首激活 + CorrectionApproved 不激活**。① CheckpointRecovered（checkpoint_events.py:40-69）字段族与 or.md L49 (9) 逐字段吻合（Checkpoint ID/恢复模式/修改内容/影响后续列表/一致性风险等级/执行延迟/成本），双登记+auto_trigger 监听在位只欠发布点——本 Story 落发布点（恢复引擎⑤步），事件定义零 diff；② 蓝图事件 CheckpointReplayed/CheckpointOverridden/CheckpointOverrideCompleted（or.md L140/L482-483/设计文档 §2.3 L324）**不新建**——双模式语义经 recovery_mode 单事件字段区分（零新增纪律三连先例：6-3 OD-9/6-4 OD-6/6-5a OD-6）；③ CorrectionApproved（correction_events.py:16-40，通道在位）不激活——apply_correction 是 6-3 冻结行为面（call_order 断言族在位），加发布会动 6-3 既有测试；审批留痕经恢复记录 confirmed_by+correction.applied_by 双写承载；多级 approval_chain 是 V1 语义——deferred-work 登记；④ 发布容错=降级 warning 不回滚恢复记录（6-3 ⑤步 checkpoint_service.py:281-296 成文先例同构——恢复记录是审计真相源、事件是通知面）；⑤ metadata 双关联键 {"plan_id","checkpoint_no"}（R3-3 通道直接复用）；⑥ 双枚举转换经 to_event_recovery_mode 显式映射（6-3 story L171 钦定注记兑现——entities "replay"≠events "Replay" 成员值不等是代码事实）；⑦ **⑤步 checkpoint_id 显式传值**（字段默认 default_factory=uuid.uuid4 随机，不传则值级断言不可预期）：修正一体=③步 sealed.snapshot_id（with_updated_state 轮换后的新值）/纯恢复=uuid.UUID(②视图.snapshot_id)（str 逆转换）——6-3 R6-24 UUID 同型直传直系先例；断言预期值单源=Outcome.recovered_snapshot_id；cost 恒 0.0 不显式传 | 事件字段族与需求语义逐字段吻合实证 + 零新增=零 yaml/router diff（`_FROZEN_EVENT_COUNT=56` 零变化）+ 6-3 行为面冻结纪律 + 最小契约变更原则 |
| **OD-3** | **恢复记录承载=第三键族 CheckpointSnapshot 通用 KV 形态**（`blm-checkpoint-recovery-{plan_id}`，`CHECKPOINT_RECOVERY_SESSION_PREFIX` 单源常量）。设计文档 §2.2/§2.3 的 ReplayLog/OverrideLog/SyncLog 三日志族在 MVP **合并为单一恢复记录**（每 plan 最新一次恢复单键覆盖——与 6-2 latest 键同构；历史经事件 outbox 可溯）；承载形态=CheckpointSnapshot（checkpoint_no="" **非完整形态**——不触发构造守卫/persistent_note_ref 强制/checksum 空——非完整性保护对象，恢复记录自身无篡改防护需求（审计面由 outbox 事件+WORM 归档承载）；state_data 12 键冻结）。**否决的备选**：a) 扩 checkpoint state_data 加 sync_status 第 14 键——动 6-3 冻结 13 键契约+checksum 参与集+exact set 断言面 ×4；b) 逐 checkpoint 标记键（pending_sync 写进各后续 checkpoint 键）——同 a) 破坏信封；c) 新增 PG 表——checkpoint 域全 Redis+零 migration（6-3 零 alembic 先例维持，WORM 语义由事件通道承载）；d) 独立标记键族+RedisAdapter 直写——绕开 SnapshotRepositoryProtocol 违反 6-3 端口纪律。sync_status 经恢复记录 join 推导（推导规则 Task 0 钦定——恢复起点恒 in_sync 新基线） | 零新存储设施/零 infra 改动/零新依赖（复用 snapshot_repository）+ 6-3 冻结契约零触碰 + 键族前缀判别先例（OD-3 双轨制扩展为三轨制）+ 设计文档三日志合一的 MVP 收敛（YAGNI） |
| **OD-4** | **端口演进 v1.1.0（单端口继续承载）+ 三 CLI 命令 + 两新用例**。CheckpointServicePort 就地新增 list_checkpoints/execute_recovery（6-3 Task 0 钦定「单端口双方法组，避免同义接口重复」的延续——恢复执行与恢复数据面同域职责；纯新增方法 ContractGate 兼容）；**否决备选**：新 CheckpointRecoveryServicePort——同义接口重复违反端口纪律。CLI 三命令 `checkpoint-list`/`checkpoint-show`/`checkpoint-recover`（扁平子命令族——6-3 checkpoint-create 直系延续；**否决嵌套分组名**——顶级 prog="sisys-agent" 扁平族先例 R2-F18）；checkpoint-correct 独立命令**不设**——修正经 recover --correction-* 内嵌（「修正关键参数后恢复执行」是连续动作 epic 语义）+ 编程面 apply_correction 端口已开放（服务层直接可用）；checkpoint-show resolve 既有 `checkpoint_recovery_use_case`（首消费方——终结零消费方状态） | 端口纪律（禁同义重复）+ CLI 惯例（扁平+五步定式）+ epic AC 语义（修正+恢复连续动作）+ R3-2 乐观锁基线消费闭环 |
| **OD-5** | **审批确认=CLI 两态（dry-run/confirm）**。设计文档 `wait_for_human_confirmation`（§2.3 L301-303 异步等待+拒绝 cancelled）在 MVP 同步 CLI 链物理不可达（无长驻交互会话）；落为**两次进程调用承载**：无 `--confirm` = dry-run（输出影响评估：后续清单+建议模式+一致性风险提示+待确认提示，exit 0，三零断言——不调引擎仅 resolve 视图）；有 `--confirm` = 执行。**不设「缺确认异常」**——dry-run 是正常交互态非错误（否决 486 族增确认码——异常语义留给真失败）；dry-run 评估输出的一致性风险等级与引擎⑤步同经 assess_consistency_risk 纯函数**同源计算**（单一事实源防双实现漂移——Replay 恒 low/Override 有后续 medium 无后续 low 一并钦定）；「审批流程测试」（epics）= dry-run→确认→执行→留痕→事件全链场景承载（S8/S9） | 设计文档人工确认语义的 CLI 同步形态等价改写 + or.md L624「Override 模式必须展示一致性风险提示，用户确认后方可执行」的 MVP 兑现 + 异常语义纯度 |
| **OD-6** | **模式强制执法 487**（or.md L622 不变约束「修改影响≥2 个后续 Checkpoint 强制采用 Replay 模式」的执法面）：建议 REPLAY 而请求 OVERRIDE → 487 `RecoveryModeConflictError` 拒绝（零副作用——save/publish 零调用断言）；建议 OVERRIDE 而请求 REPLAY → **允许**（用户可选更强一致性——强替弱禁、弱替强可，方向性执法）。`--mode` 缺省=建议模式（recommend_recovery_mode 既有判定消费）。Checkpoint.recover() 聚合状态机**继续不驱动**（6-3 R2A-4 裁定维持——防「已 completed 拒绝 recover→243」陷阱；状态面经恢复记录承载） | or.md 不变约束方向性分析（强制 Replay 的动机=防弱一致覆盖大影响面；反向升级无风险）+ 6-3 R2A-4 先例 |
| **OD-7** | **异常 486/487 取码 + 6-4 让位义务**。486 `CheckpointRecoveryError`（编排强制环节失败——恢复记录写库失败 fail-loud，except StorageError；480/482/484 经既有触发点透传不并入——六码分立）；487 `RecoveryModeConflictError`（OD-6 执法）；485 段内空洞维持+488/489 残留预留。**让位义务**：6-4 两处缺席断言（architecture test_json_chain_of_thought.py:338-360 + acceptance :2150-2171 的 `range(485, 490)`）收窄为残留码元组 `(485, 488, 489)`——「6-6 落地新增 EXCEPTION_486+ 时预期让位更新」注记（6-4 CR1-R3 落档）的兑现；收窄非删除（**485 缺席守护保留**——485 属 OD-7 段内空洞永不设码，`range(488,490)` 形态会丢 485 守护故弃；红实证仅 architecture 侧（src/domain 扫描面），acceptance 侧收窄属预防性对称）。486 message 组合 reason（6-3 R1-F3 先例）；487 message 携建议/请求双模式 | `_code_ranges.py:189` 成文预留兑现 + 六码分立语义纯度 + 6-4 让位注记在案的强制回归义务 |
| **OD-8** | **性能口径三段声明**：① 摘要显示 P95<200ms=show 单点窗口（load+verify+视图组装）与 list 清单窗口（≤8 probe+join）双覆盖——纯 Redis 读面毫秒级达标，20 轮采样数学口径沿用 6-3 AC-8（预热含首次 load 建连——R8-F5 注记继承）；② 恢复执行成功率 100%=N 次恢复 N 次恢复记录可读回（强制环节零吞错——486 是显式失败非静默）；③ Replay P95<60s/Override P95<15s（epics 6.3 L2164 归 6-6 的完整执行口径）=**引擎编排窗口口径**（②~⑤步纯数据面毫秒量级）——**口径差声明**（6-3 OD-6 先例形态）：引擎窗口不含 LLM 重跑（OD-1 defer），epic 预算针对的完整重放口径由 Epic 10 承接时本引擎窗口是其编排子集；口径差落测试 docstring | epic 性能行与交付面口径对齐（6-3 OD-6 同款纪律）+ 断言工程冗余（<15s 断言远小于门禁，漂移即红） |
| **OD-9** | **双 RecoveryMode 枚举显式转换**：entities 版（checkpoint.py:45-49，"replay"/"override" 小写——RecoveryView.recommended_mode/引擎入参/恢复记录 state_data 用）与 events 版（events/enums.py:48-52，"Replay"/"Override" 首字母大写——CheckpointRecovered.recovery_mode 用）成员值不等；转换纯函数 `to_event_recovery_mode` 落 domain/services/recovery_mode.py（6-3 story L171 钦定注记「6-6 恢复执行面消费建议恢复模式时需显式转换」兑现；同文件增 `assess_consistency_risk` 风险等级纯函数——CLI dry-run 与引擎⑤步同源）；恢复记录 state_data 用 **entities 小写形态**（与 recommended_mode 可直比——读侧免二次转换）；CLI `--mode` 参数接受小写值域 {replay,override}（choices 拦截+CLI 层 RecoveryMode(args.mode) str-Enum 按值构造——全链单次转换） | 代码事实（两枚举值不等）+ 读侧直比便利 + 纯函数落 domain（零依赖合规） |
| **OD-10** | **并发审批口径=5 独立 plan_id**（epics「并发审批 5 个 Checkpoint」L2332）：asyncio.gather 5 路（各 plan 一创建一恢复）；**同 plan 并发不承载**——恢复记录单键覆盖语义下同 plan 并发恢复会互相覆盖（6-3 单键单版本语义的自然约束），5 独立 plan=5 高管各审各的（epic 语义正解）；并发安全依赖键族 plan_id 隔离（零锁——gather 值级断言无交叉污染） | epic 语义解读（「5 个 Checkpoint」非「1 个 Checkpoint 5 路」）+ 恢复记录单键结构事实 + 零锁简单性 |
| **OD-11** | **测试文件命名（禁故事编号后缀）**：acceptance `test_acceptance_checkpoint_recovery.feature/.py`；integration `test_integration_checkpoint_recovery.py`（**对 epics L2345 钦定名 `test_checkpoint_recovery_integration.py` 的显式偏离**——仓规 tests/integration/ 主流 test_integration_* 前缀惯例（36 文件主流+8 遗留非前缀），6-3 OD-8 同款拆分声明）；unit/architecture `test_checkpoint_recovery.py`（**epics L2344 钦定名采纳**——epics 原文语境为单元测试文件名，6-6 落位 unit/architecture/ 子目录承载 SDD 架构验证（名采纳+落位仓规）；与既有 test_checkpoint.py 不同名并存；6-3 半采半离先例）；service 单测扩展既有 `test_checkpoint_service.py`（同服务同文件分组——6-3 恢复数据面同文件先例）；用例单测扩展既有 `test_checkpoint_use_case.py`；事件通道契约新文件 `test_event_channel_mapping_checkpoint_recovery.py`（6-5b 按功能新文件先例） | epics 钦定名半采半离（6-3 OD-8 先例）+ 记忆「禁止故事编号命名文件」+ 仓规目录前缀惯例 |
| **OD-12** | **本 Story 零 infrastructure 改动 + 零 PG 新依赖**：恢复记录经既有 RedisSnapshotStore 通用 KV 承载（OD-3）；事件经既有 event_publisher（outbox 写入由既有装配承载——组合根 lambda 无 PG 仓储新增）；**6-4 CLI session P0 教训的适用面核验**：本 Story CLI 链 resolve 的服务（checkpoint_service/list·execute 用例/recovery 用例）全部经 Redis+既有 publisher，零新 PG 仓储家族成员——无 session_factory 缺口面（三步排查法核验：组合根 impl lambda 无新 PG 构造/无新仓储成员/CLI 零 set_session 维持既有形态）；agent_cli 五步定式函数族 :885/:963/:1008-1065 直用 | OD-3 承载形态的连带红利 + 6-4 CR1-F1 三步排查法预防性核验（教训应用而非补救） |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/
│   ├── services/recovery_mode.py              ▲ 就地扩展（to_event_recovery_mode+assess_consistency_risk 两纯函数——Task 1）
│   └── exceptions/
│       ├── planning_exceptions.py             ▲ 追加 486/487（Task 1）
│       ├── _code_ranges.py                    ▲ _CLASS_TO_SUBDOMAIN 注册两码（Task 1）
│       └── __init__.py                        ▲ 导出（Task 1）
├── application/
│   ├── ports/checkpoint.py                    ▲ 追加两方法签名+两 VO+第四级序列化契约+恢复记录前缀常量（Task 2/3）
│   ├── services/checkpoint_service.py         ▲ 追加 list_checkpoints/execute_recovery 两方法组（Task 2/3——既有五方法零触碰）
│   └── use_cases/checkpoint_approval.py       ★ 新建（ListCheckpointsUseCase+ExecuteCheckpointRecoveryUseCase——Task 2/3）
├── interfaces/
│   └── api/exception_handlers.py              ▲ EXCEPTION_HTTP_MAP 增量 486→500/487→409（Task 1——REST 路由面仍零改动归 7-2）
├── entrypoints/agent_cli.py                   ▲ checkpoint-list/checkpoint-show/checkpoint-recover 三子命令（Task 2/3——R4）
└── composition_root.py                        ▲ 新增 2 注册块+checkpoint_service version v1.1.0（Task 2/3）

docs/architecture/sisys-uni-exception-design.md  ▲ §3.3.2 编码分配表 :757 预留行拆分+§3.7 注册表新增两行（Task 1——§3.12 C4 🔴强制）

tests/
├── unit/
│   ├── domain/services/test_recovery_mode.py           ▲ 转换函数扩展（Task 1）
│   ├── domain/exceptions/test_planning_exceptions.py   ▲ 486/487 扩展（Task 1）
│   ├── interfaces/api/test_exception_handlers.py       ▲ HTTP 映射扩展（Task 1）
│   ├── application/test_checkpoint_service.py          ▲ TestListCheckpoints/TestExecuteRecovery 两组扩展（Task 2/3）
│   ├── application/use_cases/test_checkpoint_use_case.py ▲ 两新用例扩展（Task 2/3）
│   ├── architecture/test_checkpoint_recovery.py        ★ 新建（Task 6，epics 钦定名）
│   ├── architecture/test_json_chain_of_thought.py      ▲ 485-489 断言让位收窄（Task 1——本 Story 唯一预期修改的既有架构测试）
│   └── interfaces/cli/test_agent_cli.py                ▲ 三命令扩展（Task 2/3）
├── integration/test_integration_checkpoint_recovery.py  ★ 新建（Task 5，OD-11）
├── contracts/
│   ├── test_port_contract_checkpoint.py                ▲ v1.1.0+新用例扩展（Task 2/4）
│   └── test_event_channel_mapping_checkpoint_recovery.py ★ 新建（Task 4）
├── acceptance/
│   ├── test_acceptance_checkpoint_recovery.feature/.py ★ 新建（Task 0/7，R6 模板）
│   └── test_acceptance_json_chain_of_thought.py        ▲ 485-489 断言让位收窄（Task 1——与架构侧同款）
│   （6-3 既有 checkpoint 验收/集成/单测/契约文件零修改——Task 4 回归验证）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 六条锚定义务处置注记+新留项（Task 0/7）
```

（▲ 修改 / ★ 新建 / = 零改动 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话+四 Agent 双重核验；行号基准 HEAD@5959e537，R1 审查期已在 HEAD@a10da227 抽验 20+ 锚点全部命中（其间 src 唯一改动 agent_cli.py:929 单行等量替换零行数漂移），实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| `CheckpointServicePort` 五方法 | `src/application/ports/checkpoint.py:58-190` | create_checkpoint :62-102 / build_snapshot :104-134 / apply_correction :136-165 / recover_checkpoint :167-186 / recommend_recovery_mode :188-190——**本 Story 演进基线（既有五方法行为面零触碰守护——Task 6 验证器 C）**；模块 docstring「序列化契约区（三级契约同款纪律）」（:8/:10/:19/:31——本 Story 扩展第四级） |
| `CheckpointRecoveryView` | `src/application/ports/checkpoint.py:198-230` | 9 键 DTO（checkpoint_no/stage/compressed_context/state_data/correction_history/subsequent_checkpoints/recommended_mode/state_version/snapshot_id——**snapshot_id 是 str 形态**，R3-2 序列化面注记 :218-219）——**零改动复用**（checkpoint-show 直出）；state_version=乐观锁基线（R3-2 专为 6-6） |
| `CHECKPOINT_SESSION_PREFIX`/`CHECKPOINT_TTL_SECONDS`/`CHECKPOINT_NO_MAX` | `src/application/ports/checkpoint.py:49/52/55` | 单源常量三件（"blm-checkpoint-"/2592000/8）——`CHECKPOINT_RECOVERY_SESSION_PREFIX` 的相邻扩展位（本 Story 新增） |
| `CheckpointService` 实现 | `src/application/services/checkpoint_service.py:99-532` | create :132-304（五步编排）/ build_snapshot :306-383 / apply_correction :385-446（484 前置→482 乐观锁→投影追加→重算→覆盖，**返回 sealed 新快照**）/ recover_checkpoint :448-499（load→verify 484→probe 后续清单 :480-486→判定透传）/ recommend :501-510 / `_load_or_480` :512-532 / `_parse_checkpoint_number` :64-96（三重守卫复用）——**本 Story 在此类追加两方法组** |
| `CheckpointRecovered` 事件 | `src/domain/events/checkpoint_events.py:40-69` | 字段族 checkpoint_id(UUID，default_factory=uuid4 **随机——OD-2⑦ 显式传值钦定**)/recovery_mode(**events.enums 版**默认 REPLAY)/modification_content(dict)/affected_checkpoints(list[str])/consistency_risk_level("low")/execution_delay_ms(0.0)/cost(0.0)；`__post_init__` 设 aggregate——**零字段变更，本 Story 落发布点** |
| events 版 RecoveryMode | `src/domain/events/enums.py:48-52` | "Replay"/"Override" 首字母大写——与 entities 版（checkpoint.py:45-49 小写）成员值不等，转换函数消费面（OD-9） |
| 事件双登记（既有） | `configs/event_channels.yaml:192-195` + `src/infrastructure/messaging/channel_router.py:249-254` | CheckpointRecovered reliable 单通道双登记在位——零 diff；CorrectionApproved 同款在位（yaml:202-205/router:261-266——不激活，缺席断言守护） |
| auto_trigger 监听 | `src/application/event_handlers/auto_trigger_handler.py:65/:67` | `_registered_event_types`（:60-72）含 CheckpointRecovered(:65)/CorrectionApproved(:67)——监听已注册只欠发布 |
| 发布容错先例 | `src/application/services/checkpoint_service.py:281-296` | ⑤步 CheckpointReached 事件构造 :281-288（**checkpoint_id=snapshot.snapshot_id UUID 同型直传——R6-24，OD-2⑦ 直系先例**）+发布失败降级 warning 不回滚 :289-296——**恢复引擎⑤步同构形态** |
| metadata 双关联键先例 | checkpoint_service.py:287 + `src/domain/events/base.py:74/160-164` | `metadata={"plan_id","checkpoint_no"}`（R3-3）——CheckpointRecovered 直接复用；to_dict 顶层落位 |
| `RecoverCheckpointUseCase` | `src/application/use_cases/create_checkpoint.py:89-129` | UUID 守卫+透传；docstring「恢复执行引擎归 6-6」——**checkpoint-show 的 resolve 目标（首消费方）** |
| 组合根既有注册 | `src/composition_root.py` | checkpoint_service :2293-2308（v1.0.0 五依赖 lambda——本 Story 升 v1.1.0 零 lambda 变化）/ checkpoint_use_case :2309-2320 / checkpoint_recovery_use_case :2321-2332（零消费方——本 Story 终结）/ snapshot_repository :949-963 / event_publisher :605-614 |
| planning 异常预留段 | `src/domain/exceptions/_code_ranges.py:189-190` | 「485-489 预留 planning 域（486-489 留 6-6 恢复执行面）」成文——本 Story 取 486/487 后注释更新（**禁写 EXCEPTION_486/487 完整字面**）+488/489 残留注记；`_CLASS_TO_SUBDOMAIN` 注册位 :386-390 相邻 |
| 6-4 缺席断言（让位目标） | `tests/unit/architecture/test_json_chain_of_thought.py:338-360`（docstring :339-343、range 本体 :356-358）+ `tests/acceptance/test_acceptance_json_chain_of_thought.py:2150-2171`（range 本体 :2168） | `range(485, 490)` 零占用守护——占 486/487 后收窄残留码元组 `(485, 488, 489)`；两处 docstring「6-6 落地新增 EXCEPTION_486+ 时预期让位更新」注记同步；**单测版扫描面=GUARD_FILES+src/domain rglob（必红）/验收版仅四守护文件（按现计划不红——预防性对称收窄）** |
| 冻结键数基线 | `tests/contracts/test_event_channel_mapping_pdf_report.py:23-24` | `_FROZEN_EVENT_COUNT = 56`——零新增事件=零变化（Task 4 守护复跑） |
| 6-3 CheckpointReached 契约断言面 | `tests/contracts/test_event_channel_mapping_blm_planning.py:137-182` | TestCheckpointReachedPublishWiring（源码含发布+唯一构造位 grep `CheckpointReached\(` 字面+双登记等值）——Task 4.2 零修改复跑面；6-6 新增 `CheckpointRecovered\(` 构造不误伤 |
| BLM 重跑守卫（OD-1 约束②） | `src/application/services/blm_planning_service.py:253-259` | 同 plan_id `completed_steps>0` 抛 482——Replay 实质重跑物理约束实证锚 |
| `_runs` 进程内态（OD-1 约束③） | `src/application/services/blm_planning_service.py:182` + `src/infrastructure/agent_orch/graphs/sp_blm_graph.py:105` | `_PlanRunState` dict 进程内 / compile() 无 checkpointer（:14-15 钦定注释） |
| CLI 五步定式样板 | `src/entrypoints/agent_cli.py:1008-1065`（`_run_checkpoint_create_cli`，DomainError 处理 :1059-1062）+ 分发 :1378-1387 | 参数守卫→ensure_bootstrapped→asyncio.run+resolve→_print（getattr 形态）→DomainError `[code]` exit 1——三命令直系样板；`_close_connection_pools` finally :518-539；exit 语义 docstring :1361 |
| checkpoint-create 注册块 | `src/entrypoints/agent_cli.py:361-416` | argparse 子命令注册形态（本 Story 三命令同构扩展位；现存 10 子命令扁平族无重名） |
| R8-F1 probe 模式 | `src/application/services/checkpoint_service.py:480-486` | 后续清单 probe-load 推导（**现状 CP-(n+1)..CP-8 增量**）——list_checkpoints 全量 probe（从 CP-1 起）的直系复用模式 |
| 6-3 验收装配样板 | `tests/acceptance/test_acceptance_checkpoint_snapshot.py` | `_assemble_checkpoint_chain` :549-653（**共享单 AsyncSession :626-629——gather 场景须每任务会话隔离，见隔离表**）/ `_RecordingNoteTaker` :594-607 / teardown 六步链 :274-301 / Fake 双工厂 :481-530 / outbox 双通道断言 :1341-1374（通道=phase_identifier/user_feedback_request/metadata.plan_id）——本 Story 装配直系基座 |
| 6-3 集成装配样板 | `tests/integration/test_integration_checkpoint.py` | `_CheckpointChain` 自包含装配类 :176-472（cleanup :347-426/query_outbox :428-447——预登记+定向清理）——`_RecoveryChain` 基座 |
| per-step 骨架契约 | `src/application/ports/blm_planning.py:23-44` | 七键+裸 step 值/stage 前缀混合口径——本 Story 零触碰（判别知识） |
| epics Story 6.6 定义 | `_bmad-output/planning-artifacts/epics_v1.0.md:2309-2348` | AC/性能/测试文件名钦定源 |
| checkpoint-timetravel 设计 | `docs/architecture/sisys-checkpoint-timetravel-design.md` | §1 双模式表 L11-14 / §2.2 Replay L217-283 / §2.3 Override+同步 L285-420 / §3 单点恢复=本 Story、分支对比 V2——**设计蓝图与实现的分叉知悉**（设计含 context_window/working_memory 专字段与 msgpack——实现为 state_data 13 键+JSON，6-3 OD-2/OD-11 已裁定） |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-6 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L17 | langgraph retry/timeout 字段（锚"6.6 Checkpoint 摘要查看——checkpoint_table 消费方，届时字段语义定稿"；5-10/6-1 两轮处置锚位保持 6.6） | 预判**不触发，锚位顺延**：6-6 摘要查看读 Redis 快照（snapshot_repository）零图引擎/checkpoint_table 消费——与前两轮裁定同构（第三轮同款）；锚位顺延至真实 checkpoint_table/图引擎字段消费方立项 |
| 2 | L170 | 事件消费基建四件（outbox poller 宿主/RabbitMQConsumer 零注册/队列名语义错位/realtime start 零调用）+观测面增强——锚位候选"6-6 审批流转/Epic 8"；**L170 明示「队列名语义错位未修复前禁止激活消费基建」** | 预判**顺延 Epic 8**：6-6 是 CheckpointRecovered 的**生产方**（恢复引擎⑤步发布）而非任何事件的消费方（审批交互是 CLI 同步两态——OD-5，零事件订阅面；5-3/6-3/6-4/6-5a/6-5b 六连「纯生产方」裁定延续）；注记落档 |
| 3 | L348（6.3-R1-DF1） | 互证全通道 LIKE `market\_insight%` 断言假红预警（6-6 引入 market_insight 值域合法发布时） | **规避性核销**：本 Story 发布 CheckpointRecovered（不同 event_type 通道，与 LIKE 断言正交）且创建侧值域纪律钦定 CP-1（R6 场景分化维度表）——预警条件不触发；注记落档（若后续 Story 引入 market_insight 值域 CheckpointReached 发布者再启） |
| 4 | L349（6.3-R1-DF2） | stage_id 入参值域校验缺失（STAGE_VALUE_DOMAIN 所有权在 6-2） | 预判**不触发，顺延 7-2**：6-6 摘要面显示 stage_id 原样（显示语义零值域消费）、恢复执行不依赖 stage_id 语义（checkpoint_no 是恢复坐标）——零值域消费面；注记落档顺延 REST 入口校验需求时 |
| 5 | L350（6.3-R3-DF1） | ttl_seconds/timestamp 在 checksum 信封外（扩参与集会砖化存量快照） | 预判**维持 deferred 归完整性专项**：6-6 恢复面经既有 verify_integrity（信封内校验）+恢复记录独立承载不受信封外字段影响；扩参与集+存量迁移超出本 Story 边界——注记落档维持 |
| 6 | 6-4 两处断言注记（**台账无既有条目**——注记实际位于两测试文件 docstring：architecture :341-343 + acceptance :2156；Task 0.7 对本条是**台账新建清偿注记**而非更新既有锚位） | 485-489 缺席断言「6-6 落地时让位更新」（architecture :338-360 + acceptance :2150-2171） | **本 Story 清偿**：占 486/487 后两处 `range(485, 490)` 收窄残留码元组 `(485, 488, 489)`（Task 1.5 承载——本 Story 唯一预期修改的既有测试对；红实证仅 architecture 侧可观测） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-3 Checkpoint 快照创建](./6-3-checkpoint-snapshot-creation.md)（五轮文档审查+五轮代码审查收敛 done）+ 6-4/6-5a/6-5b（CLI session P0/事件首激活/渲染净化等）

**关键学习/Key Learnings:**
- **Epic 1 骨架资产复用**（6-3 创建期实证）：新增领域类型/事件前必须全仓 grep 同语义类型——本 Story 直接兑现：CheckpointRecovered/CorrectionApproved 双事件在位（零新增）、CheckpointStatus/RecoveryMode/CorrectionRecord 零改动、`checkpoint_recovery_use_case` 零消费方注册待接线
- **属性形态断裂族**（6-1 三犯+6-3 再证）：跨对象取属性前核对真实字段形态——本 Story 高危点：CheckpointRecovered.recovery_mode 是 **events.enums 版**（大写）而 recommended_mode 是 **entities 版**（小写）——OD-9 转换函数承载；`CheckpointRecoveryView.recommended_mode` 可直比小写值；`affected_checkpoints` 是 list[str]（checkpoint_no 形态非 UUID）；`modification_content` 是 dict（修正投影承载）
- **CLI session P0**（6-4 CR1-F1 三重遮蔽）：组合根 impl lambda 带工厂/PG 仓储家族缺口/CLI set_session 断链三步排查——本 Story 零新 PG 依赖（OD-12 预防性核验），排查法应用为「无缺口实证」而非补救
- **Redis 键清理面断裂**（6-3 R1-F1 实测泄漏 1117+ 键）：新键族必须进 teardown 登记面+调用前预登记——本 Story 恢复记录第三键族（`blm-checkpoint-recovery-*`）Task 0.5 起即入清理链
- **断言判别力**：禁恒真断言；期望值独立构造（模块级字面量常量）；负向断言非空锚（outbox 按 plan_id 分组计数非全量过滤）；487 零副作用=save/publish call_order 空列表断言（6-3 R1-F2 `call_order==[]` 形态）
- **Agent 误报主会话复核**（6-5b R1 教训）：调研结论关键锚点（行号/字段形态/枚举值）主会话亲验后方可入 Story——本 Story 四 Agent 调研+主会话亲验双枚举值不等/事件字段族/用例注册/双登记四组关键事实
- **键恒在纪律**（6-2 R1-F6）：恢复记录 12 键中 correction/pending_sync_checkpoints/invalidated_checkpoints 三键恒存在（分支不适用时空容器）——读侧免双兼容
- **口径差声明**（6-1 DC-7/6-2 OD-3/6-3 OD-6）：性能口径与 epic 文本的差落 docstring（OD-8 引擎窗口 vs 完整重放口径）
- **红绿变异全链**（Epic 4 行动项 7.1-2）：新断言变异实证——本 Story 变异锚钦定（转换映射/487 执法点/12 键 exact set/事件 mode 值/sync 推导）

**应用到本故事/Applied to This Story:**
- [x] CheckpointRecovered 零新增首激活+CorrectionApproved 缺席断言守护（OD-2）
- [x] 双枚举转换函数+值级断言（OD-9——形态断裂族预防）
- [x] 恢复记录键族进 teardown+预登记（R1-F1 教训）
- [x] 6-4 让位断言收窄非删除（Task 1.5）
- [x] 期望常量独立构造+非空锚断言+call_order 空列表断言（S7 零副作用）
- [x] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep
- [x] 四 Agent 调研+主会话亲验闭环（本 Story 创建期已执行——四组关键事实锚点入 Dev Notes 锚点表）

### 其他约束速查

- **风险集中登记**：①最大回归风险=CheckpointServicePort 演进与 checkpoint_service 追加方法（纯新增预期零适配——Task 4.3 六面实证；失配即回 Task 2/3）；②契约风险=恢复记录 12 键与 sync 推导规则（Task 0 冻结唯一版本——实现禁增删键）；③口径风险=性能三段（OD-8）；④发布风险=CheckpointReached 既有断言面零修改（Task 4.2 复跑）；⑤让位风险=6-4 两处断言（收窄后守护测试必须绿——Task 1 红绿双向）；⑥**并发风险=gather 路径共享 AsyncSession**（SQLAlchemy 并发会话防呆必现——每任务会话隔离钦定，Task 0.5/5.1 装配契约承载）；⑦断言风险=checkpoint_id 值级断言的值源（OD-2⑦ 传值钦定+Outcome.recovered_snapshot_id 单源锚——不钦定则 Task 7 验收红且易误诊）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore/pylint disable；提交信息禁 AI 署名
- **覆盖率**：整体≥80% / application≥85%（主改动层）/ domain≥90% / 集成≥75%
- **验收/集成禁 mock**（真实服务优先 + `pytest.skip()` 动态跳过；Fake LLM+Fake Embedding 双豁免——外部 SaaS；486 编排失败/发布失败注入归单测层 AsyncMock——no-mock 红线互斥裁定 6-2 R3-4 先例（6-3 沿用））
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）
- **xdist 串行组**：pytestmark `xdist_group("blm-planning-perf")` 整模块挂法（与 6-3 验收+集成同 worker 串行）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-05 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.6 L2309-2348 + FR Coverage Map L535-538 + L686/L2016/L3404/L3407） |
| **架构文档** | `docs/architecture/architecture.md`（§8.1 双模式表/§8.2 五步链——经 6-3 提取稿引用） |
| **需求权威** | `_bmad-output/planning-artifacts/prd.md`（FR-SP-03 L1870 P0 深化）+ `or.md`（L27/L69 (3)/L479 五.4/L481-485 五.6/L622-624 不变约束） |
| **Checkpoint 设计** | `docs/architecture/sisys-checkpoint-timetravel-design.md`（§1 双模式/§2.2 Replay/§2.3 Override+同步/§3 第一阶段单点恢复=本 Story；与实现分叉知悉） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-3-checkpoint-snapshot-creation.md`（OD-1 边界钦定/R3-2 乐观锁基线/R3-3 metadata 双关联键/五轮双审查教训）+ 6-4（CLI session P0/485-489 让位注记）+ 6-5a/6-5b（事件首激活/发布容错先例） |
| **留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L17/L170/L348/L349/L350 + 6-4 断言注记） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml`（6-6 ready-for-dev L184） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 6.6 节 + FR 优先级边界 + Epic 10 分界核实）
- [x] 架构约束从 checkpoint-timetravel 设计 + 6-3 OD 边界提取
- [x] 前一个故事学习经验整合（6-3 双五轮+6-4 CLI session+6-5a/6-5b 事件先例）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（恢复记录第三键族/端口 v1.1.0 演进/异常 486-487/CLI 三命令/锚定义务六条）
- [x] 多 Agent 并行调研（四视角：checkpoint 域全景/BLM 编排与 CLI/验收集成测试样板/架构治理与设计文档）+ 主会话独立亲验关键代码事实（双 RecoveryMode 枚举值不等/CheckpointRecovered 字段族与双登记/RecoverCheckpointUseCase 与组合根注册/STAGE_VALUE_DOMAIN/6-4 两处缺席断言/CheckpointRecoveryView 9 键——六组锚点亲读实证）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-6-checkpoint-summary-and-recovery.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/use_cases/checkpoint_approval.py` - 两新用例（List/Execute）
- `tests/unit/architecture/test_checkpoint_recovery.py` - 架构四验证器
- `tests/integration/test_integration_checkpoint_recovery.py` - 集成四场景
- `tests/contracts/test_event_channel_mapping_checkpoint_recovery.py` - 事件通道守护
- `tests/acceptance/test_acceptance_checkpoint_recovery.feature` - Gherkin 14 场景
- `tests/acceptance/test_acceptance_checkpoint_recovery.py` - BDD 步骤实现

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/domain/services/recovery_mode.py` - to_event_recovery_mode+assess_consistency_risk 两纯函数
- `src/domain/exceptions/planning_exceptions.py` + `_code_ranges.py` + `__init__.py` - 486/487 三件套
- `docs/architecture/sisys-uni-exception-design.md` - §3.3.2 编码分配表+§3.7 注册表同步（§3.12 C4 🔴）
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 增量
- `src/application/ports/checkpoint.py` - 两方法签名+两 VO+第四级契约+恢复记录前缀常量
- `src/application/services/checkpoint_service.py` - list_checkpoints/execute_recovery 两方法组
- `src/entrypoints/agent_cli.py` - CLI 三子命令
- `src/composition_root.py` - 2 新注册块+version v1.1.0
- `tests/unit/domain/services/test_recovery_mode.py` / `tests/unit/domain/exceptions/test_planning_exceptions.py` / `tests/unit/interfaces/api/test_exception_handlers.py` - Task 1 扩展
- `tests/unit/application/test_checkpoint_service.py` / `tests/unit/application/use_cases/test_checkpoint_use_case.py` / `tests/unit/interfaces/cli/test_agent_cli.py` - Task 2/3 扩展
- `tests/contracts/test_port_contract_checkpoint.py` - v1.1.0 契约扩展
- `tests/unit/architecture/test_json_chain_of_thought.py` + `tests/acceptance/test_acceptance_json_chain_of_thought.py` - 485-489 断言让位收窄（本 Story 唯一预期修改的既有测试）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 六条处置注记+新留项

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.6 |
| **Story Key** | 6-6-checkpoint-summary-and-recovery |
| **File** | `_bmad-output/implementation-artifacts/stories/6-6-checkpoint-summary-and-recovery.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 6: 战略规划流程 (BLM 前两阶段) |
| **价值组** | 战略规划与审批能力（epics L2005——审批半边） |
| **优先级** | P1-6（依赖 Story 6.3——done） |
| **覆盖 FR** | FR-SP-03 (P0) 交互语义深化（or.md 五.4）；FR-SP-06/07/08/09 完整协议归 Epic 10（epics L535-538 权威映射）；FR-UI-16/20（Epic 22）依赖本 Story 后端能力 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7+14 场景钉死）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/端口演进/零 infra 改动/键族三轨制）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-3/6-4/6-5a/6-5b）
5. [x] Sprint status synced to `ready-for-dev`（创建完成时勾选）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | 集成场景①「Override→pending_sync 两点」与自身 487 执法规则矛盾（Override 可执行⇔后续 ≤1，pending_sync 上限 1，任何 3 点布局不可构造两点） | P1 | 改「pending_sync 一点（CP-1/CP-3/CP-5 恢复 CP-3、CP-5 一点）」+ AC-3 钦定 pending_sync 清单上限=1 |
| R1-2 | outbox「checkpoint_id 值级断言（6-3 S6 先例形态）」引用失实（checkpoint_id 双下钻全仓零先例；字段默认 uuid4 随机值级断言不可预期；with_updated_state 轮换 snapshot_id 使修正一体场景②视图值失效） | P1 | OD-2 增⑦：⑤步显式传 checkpoint_id（修正一体=③步 sealed.snapshot_id/纯恢复=uuid.UUID(②视图.snapshot_id)——6-3 R6-24 直传直系先例）；Outcome 增第 10 键 recovered_snapshot_id 断言单源锚；AC-4 措辞改「新键路径+metadata.plan_id 先例通道」 |
| R1-3 | 6-4 让位收窄 range(488,490) 与「485/488/489 继续有效」自相矛盾（丢 485 缺席守护） | P1 | 五处统一收窄为残留码元组 (485, 488, 489)；单测/验收两侧红实证差异注记（仅 architecture 侧必红） |
| R1-4 | 漏列 sisys-uni-exception-design.md §3.3.2/§3.7 同步义务（§3.12 C4 🔴强制） | P1 | Checklist 4→5 项+项目结构+File List 补行（Task 1 承载） |
| R1-5 | S10/集成③ gather 5 路与共享单 AsyncSession 冲突（SQLAlchemy 并发会话防呆必现） | P1 | 每任务会话隔离钦定（per-plan 协程自建 AsyncSession+set_session——PEP 567 task 级 context）；AC-5/隔离表/Task 0.5/5.1 四处落档 |
| R1-6 | 「五码」两套互斥口径（AC-7 Then 含 486 排 482 vs Edge Cases 含 482 排 486） | P1 | 统一六码全景（242/480/482/484/486/487）+验收面五码+486 归单测；六处同步 |
| R1-7 | Status 四处互斥（L3 backlog vs sprint-status ready-for-dev） | P1 | L3→ready-for-dev+调试日志状态词+完成清单勾选同步 |
| R1-8 | 五条 AC 验证标准在 14 场景全枚举中无落位（sync 三态转移/CP-8 尾点/修正一体/list 窗口/畸形 242） | P1 | 场景分化表逐项并入（S4/S5/S6/S9/S11/S12 扩描述） |
| R1-9 | 用例层「四参数成组校验承载」空集（CorrectionRecord 默认值兜底下部分出现不可表达） | P2 | 成组约束唯一落位=CLI 层 post-parse+真实 EntityValidationError；用例层只承载 confirmed_by 242；AC-2/CLI 节/用例节三处同步 |
| R1-10 | dry-run 评估与引擎④⑤步风险等级双源计算+Replay 分支等级未钦定 | P2 | 新增 assess_consistency_risk 领域纯函数同源消费；Replay 恒 low/Override 有后续 medium 钦定；cost 恒 0.0 钦定 |
| R1-11 | 「本 Story 零发布 CheckpointReached」失实（创建前置链每点必发布）+teardown 漏创建侧行清理 | P2 | 表述改「恢复链新增发布 CheckpointRecovered」+teardown 补创建侧行定向 DELETE（净增 0 纪律覆盖） |
| R1-12 | L173 判别规则「恢复记录无 checkpoint_no 键值锚」与 12 键契约矛盾（12 键含 checkpoint_no） | P2 | 权威判别键改「前缀+实体 checkpoint_no=""+state_data 含 recovery_mode 键」；第一级判别语适用范围收窄声明 |
| R1-13 | 「BDD 硬超时 30s 约束」表述失实（6-3 未接 run_with_bdd_timeout、pytest-timeout 未配） | P2 | 改事实口径「裸 _run_async 无实际硬超时——时长纪律靠场景成本设计+实测基线注记」 |
| R1-14 | Task 0.6 红形态「12+1+1」预判不准（S2/S3/S11 天然路由 6-3 既有行为面为绿） | P2 | 改逐场景红锚符号表：S2/S3/S11 场景文本必须触达新符号保红+S8 AssertionError 形态实现选择声明 |
| R1-15 | 集成覆盖率 ≥75%/新增面 ≥90% 无可操作测量口径 | P2 | 口径钦定：交付面 --cov 定向+term-missing 人工核新增方法区间 |
| R1-16 | Task 7 红行 off-by-one 复发（6-3 R2B-17 同款） | P2 | 改「Task 0 已建 14 场景含收尾骨架；本 Task 实现 S14 步骤断言（不新增场景数）」 |
| R1-17 | sync_status 单键覆盖读面后果未声明（二次恢复后旧标记消失）+invalidated 点仍计入后续 probe | P2 | 推导规则补两条口径注记（最新恢复记录口径+probe 不消费标记归 Epic 10） |
| R1-18 | 行号锚点漂移 12 组（CheckpointRecovered :41-79→:40-69 等——含 OD-7/OD-12 内引用） | P2 | 锚点表+全文 30+ 处订正；基线注记补 R1 审查期 HEAD@a10da227 抽验全命中声明 |
| R1-19 | 追溯矩阵 S4/S14 零引用+Subtask 引用错位（2.1~2.3/3.4（事件））+L340 漏列 acceptance 文件 | P2 | 矩阵补 S4/S14 落位+subtask 区间修正+让位行补第二文件 |
| R1-20 | Epic 22 依赖引用过度概括（L3407 是「依赖 Story 22.4」非直接依赖 6.6） | P2 | 改「22.4 直接依赖（L3404）；22.7 依赖 22.4（L3407）→传递依赖」 |
| R1-21 | 其余 P3：CLI 三态/两态措辞、OD-4/6/7 正文零回链、S13 跨故事撞名、OD-1「Task 0.2」未限定、锚定义务第 6 行台账锚位失实、表格输出无先例形态钦定、--mode 转换层位、486 except StorageError、timestamp 转换职责、变异锚补 4 处、probe 语义精确化、四要素 user_feedback_request 精确化、11 字段表述歧义、epics :2344 语境注记 | P3 | 逐项就地订正（正文 20+ 处） |
| R2-1 | 487 模式裁定执行序未钉死——边界表 L36 裁定在修正前而 AC-3 五步枚举无裁定步；裁定后置于③时 correction+冲突场景先落修正再 487 违反零副作用 | P2 | AC-3 五步枚举显式插入②.5 模式裁定（前置于③）+487 条款补「修正不应用」+TestExecuteRecovery 补 correction+冲突 apply_correction 零调用断言 |
| R2-2 | ③步 apply_correction 内 save 失败 StorageError(103) 裸逃逸（save 无 try 是 6-3 冻结面、486 原只包④save）破坏六码全景 | P2 | 486 try 面扩包③④两处 save（修正一体与纯恢复双路注入用例）；AC-7/异常表/Task 3 三处同步 |
| R2-3 | 验收 14 场景调用面（CLI vs 编程面）未逐场景钦定——S8 必须 CLI、S9/S12 断言锚只在编程面、S11 经 CLI 采样口径自相矛盾+CLI-in-BDD 跨循环风险（组合根单例绑旧 loop） | P2 | Task 0.5 新增逐场景调用面矩阵（S2/S8=CLI in-process+clear_singleton 重建；S11 采样=数据面窗口；其余=编程面）+CLI 完整覆盖归单测声明 |
| R2-4 | S5「CP-8 尾点 or S6」未钉死违反禁范围值纪律+同 plan 二次恢复单键覆盖会洗掉三态标记（陷阱） | P2 | 尾点钉死=独立第二 plan 单点 CP-8 恢复承载；删「or S6」；S5/S6 合并覆盖 sync 三态全谱显式声明 |
| R2-5 | R1 联动残留四处：AC-4 VC「6-3 S6 先例形态」措辞+缺预期值单源/L68 用例调用双面红测/L332 用例层四参数成组/L409 矩阵括注 | P2 | 四处就地订正（VC 改新键路径+单源锚；红测改 CLI 层唯一；测试表/矩阵同步） |
| R2-6 | 其余 P3×17：S13 错引 S3（482 归 S4）/L333 五码→六码/L54 修正点→恢复起点/S3 连续修正承载/execution_ms 三窗口未钦定/Replay 恒 low 改显式传函数输出/结构树漏 assess_consistency_risk/S2/S3 保红入口限定/plan_id 守卫层位三处信号/new_state_version 无修正取值+sealed str 化/恢复记录损坏退化注记/Task 1.4 红实证时序措辞/缺席 grep 事件定义文件排除（CheckpointRecovered+CorrectionApproved 两处——类定义行假阳性）/Task 4.4 第七面登记/dry-run 冲突评估预检提示/gather 会话 try/finally 生命周期/实测双数值统一 0.14-0.23s | P3 | 逐项就地订正（正文 18 处） |
| R3-1 | S2/S8 CLI 直调前 `clear_singleton()` 单清不充分——snapshot_repository 是 SCOPED，单清不清 `_scoped_context`，scoped 残留旧 store 持死 loop 客户端且 load 吞错返 None→show 误报 480/sync join 假 in_sync 的静默失败（R3 真实 Redis 实跑证伪）；二次 bootstrap 抛 ConflictError（registry 持久） | P1 | 改双清钦定 `clear_singleton()`+`clear_scoped()`（markdown_report.py:145-148 先例）+禁重新 bootstrap 注记（ensure 自动短路） |
| R3-2 | 其余 P3×7：list 窗口采样轮数未钉（同 20 轮）/S12 窗口载体与蕴含声明缺（Outcome①~⑤⊇②~⑤；逐次<15s 蕴含 P95 双门禁）/「CP-1 值域」可误读为编号约束（实为 stage_id 值域）/调用面矩阵缺 S14 注记/assess_consistency_risk 消费点「④⑤」与「⑤」两套口径（契约唯一落点=⑤）/CLI 缺参 exit 2 与 242 守卫分工未成文（空串归 242）/R2-6 计数 13→17+R1 对码「19+3」→「19 完整+2 部分」订正 | P3 | 逐项就地订正；另 Task 0.1 补合理性终审两注记（probe 半途失败边缘 defer 登记/TTL 写时序无孤儿窗+反向边缘） |
| R4-1 | assess_consistency_risk 判别链断裂（三分支矩阵未逐支钉死+Task 3 事件字段清单漏 consistency_risk_level——「硬编码 low」漂移可存活）；S11 保红入口两套钦定互斥（Task 0.6 CLI 入口 vs 调用面矩阵编程面）；整体覆盖率门禁命令裸收集挂起形态（与四目录纪律自相矛盾） | P2 | Task 1.1 三分支矩阵钉死（medium 腿=唯一可判别腿）+Task 3 字段清单补 consistency_risk_level（Override+1 后续=medium 承载）；S11 改「list 窗口新符号保红+show 数据面采样」；覆盖率命令补显式四目录 |
| R4-2 | 其余 P3×15：分层覆盖率 addopts 累积口径注记/ruff 补 tests//mypy 基线 752 锚/5 次 vs 双轮等效证据链统一/no-mock 先例 6-3 R3-4→6-2 R3-4（三处）/validate-create-story 模板遗留措辞/OD-11 主流前缀措辞/pre-commit push-stage 注记/三红线 git diff 命令化待实施期/dry-run 预计耗时成本 defer 声明（or.md L484 唯一零承载项）/L623 幂等性 MVP 承载声明/OD-1 枚举补 SP-07→10.3+失败回滚/epic 架构测试三项落位对账/V2→Epic 10 措辞/CLI 表格断言形态钦定（表头精确串+行值级）/timestamp isoformat 断言/checkpoint_id 传值变异锚×8/未知值防御悬空义务裁定（枚举闭集不可构造，删短语） | P3 | 逐项就地订正（需求覆盖六源 17 条 100% 承载+门禁全可执行复核结论同步落档） |

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待代码审查）
**审查模式:** （待代码审查）

#### 需决策 Decision Needed

- [ ] （待代码审查）

#### 已修复 Patch

- [ ] （待代码审查）

#### 已推迟 Defer

- [ ] （待代码审查）

---

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 文档审查五轮收敛（本 Story 已执行——v1.5.0 定稿）；story-template 合规人工核对（仓内无 validate-create-story skill）
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.4.0
**创建日期/Created:** 2026-11-05
**最后更新/Last Updated:** 2026-11-05
**更新说明/Description:**
- v1.4.0: 文档审查 Round 4 完备性核查+门禁复核修订（3 Agent 并行【需求覆盖六源核查（epics 17 条 100% 承载+零超范围+P3 声明缺口×6）/测试矩阵七维度判别力复核（断言/覆盖空隙/红绿/变异锚 15 对照/回归面 grep 全集/隔离清理/Fake 契约）/质量门禁九项可执行性复核（pyproject/pre-commit/importlinter 实据）】；**P0/P1 双零收敛**；P2×3：assess_consistency_risk 判别链闭合（三分支矩阵+medium 腿=Override+1 后续唯一可判别腿+S9 值级承载）/S11 保红入口两套钦定互斥消解（Task 0.6 对齐调用面矩阵编程面）/整体覆盖率命令补显式四目录（裸收集挂起形态封堵）；P3×15 就地订正（mypy 752 基线锚/ruff 双目录/等效证据链统一双轮口径/no-mock 先例 6-2 R3-4 正名/validate-create-story 模板遗留处理/or.md L484 预计耗时成本 defer 声明——六源唯一零承载项/L623 幂等性 MVP 承载/OD-1 四条全枚举+失败回滚/epic 架构测试三项对账/V2→Epic 10/CLI 表格断言形态/timestamp 断言/checkpoint_id 变异锚×8/未知值防御悬空裁定等）；Docs Review Fixes 表 R4-1~R4-2 落档）
- v1.2.0: 文档审查 Round 2 修订（3 Agent 并行【回归核查（R1 21 项对码：19 完整+2 部分落地）/交叉引用深度核查（五向闭环 27 条 VC 严格闭环率 85.2%→修正后 27/27；锚点 60+ 个逐一对码零漂移）/执行序深度推演（五步/14 场景/CLI 双态/读侧/让位序/回归面六面全推演）】+主会话亲验 P2 依据两组；P2×5+P3 批量：**顺序语义与调用面四钉死**——②.5 模式裁定前置（correction+冲突零副作用哨兵）/486 try 面扩包③④两处 save（103 逃逸封堵）/逐场景调用面矩阵（S2/S8 CLI in-process+clear_singleton 跨循环防线、S11 采样=数据面窗口、CLI 完整覆盖归单测）/S5 尾点独立 plan 钉死（单键覆盖陷阱消除）；R1 联动残留四处清偿+P3×17 就地订正（execution_ms 三窗口/grep 类定义排除/第七面/会话生命周期等）；Docs Review Fixes 表 R2-1~R2-6 落档）
- v1.1.0: 文档审查 Round 1 修订（7 Agent 并行【D1 调研×4：checkpoint 域核心/事件体系与组合根/异常体系与 6-4 让位/CLI 与测试样板 + D2 审查×3：一致性内审/正确性对码与方案合理性/可行性与最佳实践（含 6-3 验收实测基线）】+ 主会话亲验 8 组关键锚点；P1×8+P2×12+P3×1 计 21 项编号修复+附注若干：**P1 面五项实质矛盾全清**——集成场景① Override pending_sync 两点不可构造（模式执法必然推论上限 1 点）/outbox checkpoint_id 值级断言三重不可达（默认 uuid4 随机+先例引用失实+with_updated_state 轮换 snapshot_id——OD-2⑦ 显式传值钦定+Outcome 第 10 键 recovered_snapshot_id 断言单源锚）/让位收窄 range(488,490) 丢 485 守护（残留码元组 (485,488,489)）/gather 共享 AsyncSession 并发防呆必现（每任务会话隔离钦定）/§3.12 C4 设计文档同步义务遗漏（Checklist 4→5 项）+六码口径统一+Status 四处同步+五条 VC 场景落位；**P2 面**：成组守卫层位正名（CLI 层唯一落位——CorrectionRecord 默认值兜底实证）/风险等级同源纯函数 assess_consistency_risk+Replay 恒 low+cost 恒 0 钦定/创建侧 CheckpointReached 行清理补位/判别规则权威键改 recovery_mode/30s 硬超时表述事实化/Task 0.6 逐场景红锚符号表/两覆盖率口径钦定/off-by-one 家族修复语继承/sync 覆盖读面注记/12 组行号锚点 30+ 处订正；Docs Review Fixes 表 21 项编号落档）
- v1.0.0: 创建故事文件（四 Agent 并行调研【checkpoint 域全景/BLM 编排与 CLI/验收集成测试样板/架构治理与设计文档】+ 主会话亲验六组关键锚点；钦定 OD-1~OD-12 偏离声明：MVP 恢复执行形态四条物理约束论证与 Epic 10 分界/CheckpointRecovered 零新增首激活+CorrectionApproved 不激活/恢复记录第三键族/端口 v1.1.0 演进+CLI 三命令/dry-run 两态确认/模式强制 487/486-487 取码+6-4 让位/性能三段口径/双枚举转换/并发 5 独立 plan/测试命名半采半离/零 infra 零 PG 改动；14 验收场景钉死；锚定义务六条处置预案；6-3 边界表出处逐行声明）
