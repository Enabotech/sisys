# Story 6-3: Checkpoint 快照创建（持久化笔记→压缩→StrategicArchive 归档→完整形态快照→CheckpointReached 发布→恢复数据面）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统在 BLM 阶段完成后创建 Checkpoint 完整形态快照（执行"持久化笔记→上下文压缩→StrategicArchive 归档→快照落库→CheckpointReached 发布"五步机制，携带阶段标识、完成状态、用户反馈请求、修正记录），
**So that** 支持阶段审批和中断恢复——高管可在关键决策点查看阶段产物并修正关键参数后从恢复点继续（恢复执行引擎与审批交互面归 Story 6-6）。

### 业务价值

- 覆盖 **FR-SP-03 (P0)**：系统可以创建 Checkpoint 快照（阶段标识、完成状态、用户反馈、修正记录）[or.md 五.4 / prd.md L1870]
- 6-1 交付了 BLM 流程宿主与图 state 产物、6-2 交付了 per-step 快照**骨架**（恢复点位数据面，零压缩零持久化笔记）；本 Story 落地 Checkpoint **机制完整面**——architecture.md 五步机制（§8.2 主链 L792-802 + §11.2.6 触发链 L1246-1254 + L850 归档位 + L871 发布行**四源合成**——OD-12；§8.2 原链无归档步/发布步，非单源五步）+ 系统公理二（压缩前必须持久化）+ `persistent_note_ref` 强制关联 + SHA-256 完整性验证 + TTL 30 天 + `CheckpointReached` 真实发布点（6-1 AC-4/6-2 AC-3 负向断言钦定的"6.3 语义分立"兑现）
- **清偿 1-15b 钦定接线义务**：sprint-status.yaml L180 注释原文"TODO: 实现 1.15b L3(Qdrant)/L4(MinIO) 触发"——1-15b L298-300 成文"L3 Qdrant：压缩后内容 >500 tokens 时触发（Story 6.3 实现）；L4 MinIO：Checkpoint 创建时触发（Story 6.3 实现）"，经 StrategicArchiveService（3-10 交付，L2 强制+L3/L5 可降级+L4 WORM 编排）接线落地
- **激活休眠的检索-压缩循环**：PersistentNoteTaker/ContextCompressor/CompressionQualityEvaluator（Epic 3 检索重构 commit 1235b011 交付）当前生产消费方仅组合根注册（deferred-work.md L132"检索-压缩循环待接线——归宿 Epic 6+"）——本 Story 成为首个真实消费方
- Epic 6 内部顺序依赖：6-1（done）→ 6-2（done）→ **6-3（本 Story）** → 6-5a 报告（消费 Checkpoint 面数据）/ 6-6 摘要查看与恢复（消费本 Story 恢复数据面）

### 与 6-1/6-2 的范围边界（出处逐行声明）

| 面（出处） | 6-1/6-2 已交付（禁重复造轮） | 6-3 增量（本 Story） |
|---|---|---|
| 流程宿主（6-1 交付记录） | `SpBlmGraph` 8 节点/六子步骤执行链/图 state 产物（gap_artifacts/insight_step_results/synthesis）——6-1 边界表钦定"阶段产物落 state 供 6.3 快照消费" | 零改动复用（Checkpoint 创建的输入源） |
| 快照骨架（6-2 边界表+端口契约区 L23-44） | latest + per-step 双键族（`sisys:snapshot:blm-planning-{plan_id}[:{step}]`，state_data 七键，TTL 86400）——端口契约原文钦定"Story 6-3 Checkpoint 完整机制的恢复点位数据面" | 零改动复用（骨架键族与 TTL 维持不变——OD-3）；完整形态**独立键族**叠加 |
| 事件（6-1 DC-8/6-2 AC-3 负向断言） | `PlanningStarted`/`BlmStageCompleted`；`CheckpointReached` 全链资产在位（事件类/yaml/router 双登记）但**零发布**（负向断言钉死） | **`CheckpointReached` 真实发布点落地**（新文件——OD-4：blm_planning_service.py 等三文件零触碰，负向契约断言面保持绿） |
| 持久化笔记/压缩（Epic 3 交付/deferred L132） | PersistentNoteTaker.take_notes/ContextCompressor.compress/CompressionQualityEvaluator——休眠资产（零生产消费方） | 首个真实消费方接线（检索-压缩循环激活） |
| 战略档案（3-10 交付） | StrategicArchiveService.archive_plan（L2 强制→L3 向量→L4 WORM→L5 图谱，ArchiveCreated 事件） | Checkpoint 归档接线（载荷=压缩产物+持久化笔记实体/摘要——architecture L850"StrategicArchive = Checkpoint 快照前的强制持久化"） |
| 恢复（6-1 OD：跨 run 恢复归 6.3） | 无（6-1 R3"结果即取即用，跨 run 恢复零依赖归 6.3"） | 恢复**数据面**（快照读回+完整性验证+状态恢复+修正记录应用）；恢复**执行引擎**（Replay 重放/Override 同步/CheckpointRecovered）归 6-6（OD-1） |
| 审批交互（epic 6.6） | 无 | 不做（6-6 落摘要查看/审批流/并发审批） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Checkpoint 创建五步完整机制

**Given** BLM 前两阶段某步已完成，调用方持阶段产物输入（query/检索证据/summary 直供——per-step 快照骨架仅为背景不参与创建路径断言）
**When** 显式调用 Checkpoint 创建（用例/CLI——OD-5：MVP 同步链下"阶段完成即暂停等审批"物理不可达，由显式调用触发）
**Then** 依次执行五步：① `PersistentNoteTaker.take_notes()` 持久化原始上下文（提取 Top-20 实体+血缘+摘要回填）→ ② `ContextCompressor.compress()` 压缩上下文（≥70%+质量≥0.7——AC-2，编排层终态门禁 fail-loud）→ ③ `StrategicArchiveService` 归档（载荷=压缩产物+持久化笔记实体/摘要，L2 元数据+L3 向量+L4 WORM——AC-5；顺序依据 §11.2.6 触发链「take_notes→compress→StrategicArchive 持久化」+ L850「StrategicArchive=Checkpoint 快照前强制持久化」——压缩先于归档、归档先于快照落库，五步序四源合成声明见 OD-12）→ ④ 创建 Checkpoint 完整形态快照（`persistent_note_ref` 强制非空+checksum——AC-3）序列化至 Redis Hash（TTL 30 天=2592000s）→ ⑤ 发布 `CheckpointReached`（AC-4）
**And** 快照 state_data 携带阶段标识（stage_id/stage_number——Checkpoint 编号体系 CP-1/CP-2-7/CP-8，13 键契约见数据模型节）、完成状态、compressed_context 与压缩元数据
**And** 五步编排任一强制环节（压缩前置持久化校验 242 透传/压缩终态门禁/归档 L2·L4 及归档内 ArchiveCreated 发布失败/快照落库）失败时抛领域异常并携带 checkpoint 上下文（不产出半成品快照——AC-2 负向；**归档侧残留语义**：③失败时①②已写的 L1 笔记缓存 `note:{note_id}`（TTL 30 天自清）、②压缩结果缓存 `compressed:{note_id}`（TTL 86400 自清——context_compressor.py:189/289-303）、③内已写的 L2 档案行（指向真实笔记）与 L3 Qdrant 点（archive_id 可溯）为可接受残留、不补偿清理——快照面无半成品即不变量边界，OD-12 声明）

**验证标准/Validation Criteria:**
- [ ] 一次完整创建后：Redis 完整形态快照可读回（键族见 OD-3），`persistent_note_ref` 非空且指向真实 PersistentNote（L1 缓存 `note:{note_id}` 可读回）
- [ ] `state_data` 键契约完整（Task 0 冻结 **13 键**——与数据模型节键族逐键同源：checkpoint_no/stage_id/stage_number/plan_id/completed/summary/compressed_context/compression_ratio/quality_score/token_count/persistent_note_ref/correction_history/created_via——**created_via 值域钦定**（R3-E）：`"cli"` / `"use_case"` 两值小写枚举，端口 docstring 登记；**归档关联注记**（R3-C）：13 键无归档引用键——快照↔归档行经 plan_id 关联查询（archive_plan 入参同 plan_id），不引入 archive_id 键）
- [ ] TTL=2592000（30 天）经快照实体 `ttl_seconds` 与 Redis TTL 双验
- [ ] Checkpoint 编号体系落位：CP-1/CP-2-7 对齐 core-domain §17.4.1（CP-1=performance_gap 后 / CP-2-7=六子步骤各一）；**CP-8=synthesis 后为本 Story 钦定**（设计图 §17.4.1 CP-8 挂阶段 3「战略意图与目标」后——6-2 已交付 synthesis 第八 stage，synthesis 完成点是 BLM 前两阶段最后恢复点，钦定 CP-8 使前两阶段恢复点闭环；阶段 3 Checkpoint 由后续 Story 对位设计图）——**BLM 前两阶段 8 个恢复点**（非设计图全量 14 点口径）；六子步骤映射名以 6-2 STAGE_VALUE_DOMAIN 为准（§17.4.2 第六步「看风险」已被 6-2 OD-2 裁定不采用）
- [ ] 六子步骤各自可独立创建 Checkpoint（CP-2~CP-7），互不覆盖（独立键）

### AC-2: 系统公理二强制（压缩前必须持久化）

**Given** Checkpoint 创建流程执行
**When** 到达压缩步骤
**Then** 前置校验链生效：`PersistentNoteTaker.verify_persisted(note)` 为 True 方可进入 `compress()`（ContextCompressor 既有前置校验复用，零改动）；压缩产物 `compression_ratio ≥ 0.70` 且 `quality_score ≥ 0.70`——不足时既有二次压缩/二次生成路径复用，**二次路径耗尽仍不达标时编排层终态门禁 fail-loud**（R1-F2 实测：compress 无最终门禁、不达标产物原样静默返回——门禁落编排服务，抛 483，快照零落库；OD-7）
**And** 快照构造守卫：`persistent_note_ref` 为空 **且 checkpoint_no 非空（完整形态）**时构造快照 → 抛 `CheckpointIntegrityError`（484——Task 0 已冻结码位；双条件限定防 6-1/6-2/5-10 既有全默认构造误触发，R2A-11），**禁止产出无持久化引用的完整形态快照**（0 次违规口径——设计文档 §2.1 验收表）
**And** 归档强制环节失败抛 `ArchiveStorageError`（code 284，archive 子域——3-10 既有异常透传不吞；**触发面三层**：L2 存储失败/L4 存储失败/**归档内 ArchiveCreated 发布失败**（Outbox 原子性设计 :286-294，同样不容错）——与第⑤步 CheckpointReached「发布失败降级不回滚」是两套容错语义：③内事件失败→全链阻断，⑤事件失败→降级日志，编排服务不得在③步吞 ArchiveCreated 发布失败）

**验证标准/Validation Criteria:**
- [ ] 未持久化笔记（persisted=False）传入压缩 → 既有 `EntityValidationError` 路径零回归（ContextCompressor :132-137 复用验证——R2B-9 行号统一）
- [ ] 空引用构造完整形态快照 → 新增异常抛出（红测：构造点守卫）
- [ ] 压缩率/质量评分不足 → 二次路径触发（Fake LLM 口径下注入首轮不足产物断言 rerun_count ≥ 1）
- [ ] 二次路径耗尽仍不达标（Fake 压缩产物双指标不足的固定返回形态）→ 编排层终态门禁抛 483 且 save 零调用（fail-loud——R1-F2 静默终态的编排层闭环）
- [ ] 归档 L4 失败注入 → `ArchiveStorageError` 透传且快照不落库（负向：无半成品）

### AC-3: 完整性验证（SHA-256 checksum）

**Given** Checkpoint 完整形态快照已创建
**When** 执行完整性验证
**Then** checksum 计算覆盖**身份五字段 + 恢复载荷**：`session_id/stage_id/state_version/checkpoint_no/persistent_note_ref` + `state_data` 规范化序列化（`json.dumps(state_data, sort_keys=True, ensure_ascii=False)`——Task 0 冻结，OD-11；参照设计文档 §2.1 语义的钦定扩展：保留其版本分量（state_version）、身份字段改写（checkpoint_id→session_id 承载——Redis 键族主键；snapshot_id 每次更新轮换故不参与，R2A-14 措辞校准）、**增量载荷覆盖**（state_data 序列化参与——完整性保护扩展至恢复载荷 compressed_context 等 13 键，业界内容寻址完整性标准））；篡改任一参与字段或 state_data 任一键后重算不匹配 → 恢复入口抛完整性异常（484）
**And** 恢复入口（AC-7）强制先 `verify_integrity()` 再恢复（校验失败拒绝恢复）；`verify_integrity() -> bool` 纯判定无副作用，484 抛出点在恢复编排调用方（实体方法不抛——签名与行为一致）；checksum 由编排服务在④步构造时显式计算写入（**不在 `__post_init__` 自动算**——6-1/6-2/5-10 既有构造零扰动）、apply_correction 经 `with_updated_state` 更新后**必须重算替换**（服务层重算点钦定——载荷已变而 checksum 不重算则修正后快照恒 verify 红）

**验证标准/Validation Criteria:**
- [ ] 创建→读回→verify 全绿（round-trip）
- [ ] 篡改 state_data 任一键（compressed_context/summary/correction_history）/替换 persistent_note_ref/篡改实体顶层 checkpoint_no → 重算不匹配 verify 红（突变实证——state_data 序列化参与 checksum 的直接可达性，OD-11）
- [ ] checksum 算法：SHA-256 hexdigest（标准库 hashlib——domain 零依赖合规）

### AC-4: CheckpointReached 真实发布

**Given** Checkpoint 完整形态快照落库成功
**When** 发布步骤执行
**Then** 发布 `CheckpointReached(checkpoint_id=快照 ID, phase_identifier=stage_id, user_feedback_request=True)`（Epic 1 既有事件类**零字段变更**——OD-9：plan 关联经 DomainEvent 既有 `metadata` 构造参数承载，Task 0 核验 base.py 构造签名）
**And** 发布走既有 reliable 单通道（event_channels.yaml L74-77 + ChannelRouter.DEFAULT_MAPPINGS L120-125 双登记**零 diff**——资产已就绪，仅落发布点）
**And** 发布失败不回滚快照落库（快照是真相源，事件是通知面——降级日志，与 6-1 快照写容错同语义；**CLI 成功口径钦定**（R3-D）：exit 0 判据=快照落库成功——发布降级不改变 exit code，仅 warning 日志）

**验证标准/Validation Criteria:**
- [ ] 发布点位于**新文件**（checkpoint 应用服务/用例），`blm_planning_service.py`/`run_blm_planning.py`/`get_blm_planning_status.py`/`blm_planning_prompts.py` 四文件源码零 `CheckpointReached` 引用——既有负向契约断言（test_event_channel_mapping_blm_planning.py L88-104/L126-134）**零修改通过**
- [ ] 真实 publisher + PG outbox 装配下落行可断言（行筛选路径 `payload->'payload'->>'phase_identifier'` 或 `->>'checkpoint_id'`——**禁用 plan_id 通道**：事件类字段族无 plan_id（6-2 R1-F3 实证），Task 0 钦定断言键）
- [ ] **6.2-DF3 清偿**：引入合法发布者后，为 6-2 的负向双通道 LIKE 转义补独立守护（`market\_insight%` 转义形态在 6-3 发布者在位时获得真实红路径——本 Story 契约测试承载）
- [ ] 6-2 验收 AC-3 场景（市场洞察 run 内零 CheckpointReached）**零适配通过**——run 路径与创建用例路径正交（OD-4 的行为级证据）

### AC-5: L3/L4 触发接线（1-15b 钦定义务清偿）

**Given** Checkpoint 创建流程的持久化笔记与压缩步骤完成（③归档执行时压缩产物已就绪——五步序 OD-12）
**When** 归档步骤执行
**Then** 经 `StrategicArchiveService` 落 L2-L5：L2 元数据（PostgreSQL，强制）+ L3 向量（Qdrant `strategic_archive` collection——1-15b L299"压缩后内容 >500 tokens 时触发"条件对象=压缩产物（compressed_context ~2K tokens 恒 >500），在 Checkpoint 场景**恒真**，按 archive_plan 现状无条件写入即可，**禁实现恒真条件分支**——1-15b 条件语义为记忆内容分档，对 Checkpoint 不适用，OD-10 声明）+ L4 对象（MinIO WORM `archive-evidence`，强制）+ L5 图谱（可降级）
**And** 归档载荷 = 压缩产物 + 持久化笔记实体/摘要（Task 0.8② 冻结映射：compressed_context→evidence_blob/decision_basis、笔记 entities Top-20+summary+lineage→assumptions——`plan_type="checkpoint"` 钦定、`archive_type` 默认 ASSUMPTION 维持）；L3/L5 失败优雅降级不阻断创建（3-10 既有降级语义零改动）；L2/L4 失败及归档内 ArchiveCreated 发布失败抛 `ArchiveStorageError`（284）阻断（AC-2 三层触发面）

**验证标准/Validation Criteria:**
- [ ] 真实链集成：归档后 PG `strategic_archives` 行存在 + Qdrant 点可搜（`search_vectors` 读回）+ MinIO 对象可取（blob_ref 解引用）
- [ ] 归档载荷断言：压缩产物入档（evidence_blob 解引用含 compressed_context）+ 持久化笔记关键实体（Top-20）与摘要入档（assumptions/decision_basis 映射——Task 0.8② 冻结归档载荷契约）
- [ ] **take_notes 输入源钦定（Task 0）**：`retrieved_docs: list[SearchResult]`（dict 形态——payload.content 键）由调用方构造——**per-step 快照 state_data 非 SearchResult 形态**，用例入参直接接收调用方提供的检索证据（或从 state_data.summary/structured_output 构造最小 SearchResult dict——`{"id":…, "payload": {"content": …}}` 形态，Task 0 钦定构造规则）；take_notes 第四参 session_id 与快照键同源（`CHECKPOINT_SESSION_PREFIX+plan_id+":"+checkpoint_no`——端口 docstring 序列化契约区登记）
- [ ] sprint-status.yaml L180 TODO 注释随本 Story 清偿更新（"实现 1.15b L3(Qdrant)/L4(MinIO) 触发"→已落地注记）

### AC-6: 用户反馈请求与修正记录

**Given** Checkpoint 完整形态快照在位（FR-SP-03 四要素：阶段标识✓/完成状态✓/用户反馈/修正记录）
**When** 用户对 Checkpoint 提交修正（关键参数修正——恢复数据面入口）
**Then** 修正记录以**既有** `CorrectionRecord`（Epic 1 骨架——correction_type/previous_value/new_value/applied_by/applied_at **五字段**，对齐 or.md L305 修正日志要素 5/7 MVP 子集；docstring 提及的 correction_id 类中无此字段——注记差异）写入快照 correction_history，经 `with_updated_state` 不可变更新（state_version+1，**透传新增四字段**——R2A-3）+ checksum 重算替换（AC-3 重算点）后 **save 覆盖同键**（**单键单版本存活钦定**——R3-T2：session_id 键不变、新版本覆盖旧版本，修正历史经 correction_history 在最新快照内累积承载，**不建版本键链**——乐观锁 expected_state_version 与键内存活（唯一）版本比较；与 6-1 latest 键覆盖同语义），修正后快照保留原 persistent_note_ref 血缘链
**And** 修正记录可随快照读回并供 6-6 审批面消费（修正历史清单）；`Checkpoint` 聚合状态机驱动点钦定（OD-12 附则——避免「恢复面驱动 recover() 守卫则全部恢复场景被 243 拒绝」的机理冲突）：**创建面**第④步内（checksum 计算前——R2A-5 时序钦定）**仅当 completed=True 时**构造 `Checkpoint` 聚合并调 `complete()`（守卫驱动+status 映射进 state_data.completed=True；completed=False 时聚合保持 IN_PROGRESS **不调 complete()**——否则 False↔IN_PROGRESS 映射与端口/CLI 的 completed 参数成死分支）、**修正面**经 apply_correction 追加 correction_records；**恢复面只读不驱动 recover()**（恢复执行引擎归 6-6）——「已 completed 拒绝 recover → 243」限定为聚合单测激活验证（test_checkpoint.py 既有断言在位）+ 6-6 边界，不进 6-3 恢复场景

**验证标准/Validation Criteria:**
- [ ] 既有 CorrectionRecord 零改动复用（五字段族与 or.md 要素映射注记落 docstring——Subtask 1.6；correction_id 仅 docstring 提及无字段——差异注记）
- [ ] 修正应用 → 新快照 state_version 递增 + correction_history 追加 + 原快照字段保留 + **checksum 重算后 round-trip verify 绿**（修正链完整性闭环——AC-3 重算点）
- [ ] `user_feedback_request=True` 随事件发布（AC-4 联动——阶段审批请求语义）

### AC-7: 恢复数据面与双模式判定

**Given** Checkpoint 完整形态快照族在位（≥3 个：如 CP-1/CP-3/CP-5）
**When** 从指定 Checkpoint 恢复
**Then** 执行：load（快照读回）→ `verify_integrity()`（AC-3——失败抛完整性异常拒绝恢复）→ 反序列化恢复状态（阶段产物/压缩上下文/修正记录）→ 组装恢复视图 DTO（供 6-6 消费）
**And** 恢复模式判定纯函数：影响范围 = 该 Checkpoint 之后的后续 Checkpoint 数；**≥2 → 强制 Replay / <2 → 推荐 Override**（判定函数纯计算零副作用——双模式执行引擎归 6-6，OD-1）
**And** 非法恢复操作异常三分（Task 0.3 钦定口径）：**不存在的 checkpoint 键 → 480 `PlanningNotFoundError`**（复用既有类承载 checkpoint 语境——构造参数语境 Task 0.3 钦定；含 JSON 损坏型：load 静默 None 语义下损坏 JSON 与不存在键同路径不可区分，统一 480）/ **checksum 不匹配（损坏快照）→ 484 `CheckpointIntegrityError`**（verify 层——AC-3）/ **版本倒退与状态非法 → 482 `PlanningStateError` 追加触发点**（既有码已有 6-1 R1-5 同 plan_id 重跑守卫生产触发点在位 blm_planning_service.py:242——本 Story 是**第二触发点**而非处子激活；「预留」措辞出处 _code_ranges.py:181-182/exception_handlers.py:306 注释，类定义/注册/映射零改动，预留 409 映射已在位）

**验证标准/Validation Criteria:**
- [ ] 恢复视图 DTO 键契约完整（Task 0 冻结：checkpoint_no/stage/compressed_context/state_data/修正历史/后续 checkpoint 清单/建议恢复模式）
- [ ] 判定纯函数：0/1 后续 → Override 推荐、≥2 → Replay 强制（边界值 2 恰好强制——突变实证）
- [ ] 不存在键恢复 → 480（钉死——Task 0.3 已钦定：键不存在与 JSON 损坏同路径统一 480，复用 PlanningNotFoundError 承载 checkpoint 语境）；checksum 不匹配 → 484；版本倒退 → 482（三码三分，Task 3 红测对齐）
- [ ] 482 第二触发点落位后 `EXCEPTION_HTTP_MAP` 409 映射在位（既有注册零改动验证——预留映射已存在）

### AC-8: 性能与持久化成功率

**Given** Checkpoint 创建在测试管线中执行（Fake LLM 管线开销口径——OD-6）
**When** 采样计时
**Then** **创建提交窗口 P95<100ms**：口径 = 压缩产物就绪后的"快照构造+序列化+Redis pipeline 提交"窗口（持久化笔记的实体抽取与 LLM 压缩延迟显式出栈独立计量——6-1 DC-7/6-2 OD-3 口径差声明先例，口径差落测试 docstring）
**And** 快照持久化成功率 100%（强制环节零吞错；可降级环节失败计入降级计数不计入失败）
**And** 恢复数据面 P95 口径 = load+verify+反序列化窗口（<100ms 量级预期；epic 的 Replay P95<60s/Override P95<15s 完整执行口径**归 6-6**——OD-1 边界，本 Story 不断言）

**验证标准/Validation Criteria:**
- [ ] 创建窗口采样 ≥20 轮，P95 = **sorted(durations)**[ceil(0.95*n)-1] < 100ms（6-1/6-2 同款数学口径；n=20 时取次大值——升序排序前提显式声明）；采样形态钦定（OD-12 附则）：单次全链预热取得固定压缩产物 → 20 轮仅执行「快照构造起点→真实 snapshot_repository.save 返回」窗口（直调真实端口，**禁每轮全链**——30s BDD 硬超时预算）；20 轮 = 20 个独立 plan_id 各建 CP-1（键唯一互不覆盖，20/20 可读回——checkpoint_no 值域 8 值上限下同 plan 不可承载 20 键）
- [ ] 计时窗口钦定：快照构造起点 → Redis save 返回（Task 0 钉死观测点）
- [ ] 成功率口径：N 次创建 N 次快照可读回（强制环节零失败语义测试承载）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **零新增领域事件、零事件字段变更**（本 Story 钦定——OD-9）：
  - `CheckpointReached` 是 Epic 1 既有资产（`src/domain/events/checkpoint_events.py:16-37`，字段族 checkpoint_id/phase_identifier/user_feedback_request），双登记在位（event_channels.yaml:74-77 + channel_router.py:120-125，reliable 单通道）——本 Story 仅落**发布点**，事件定义/导出（events/__init__.py:13,63）/outbox 通路（DomainEvent._registry 自动注册）/双登记**全部零 diff**
  - plan 关联经 DomainEvent 既有 `metadata` 构造参数承载（**已核验定谳**：`src/domain/events/base.py:74` 有真实字段 `metadata: dict[str, Any] = field(default_factory=dict)`——`CheckpointReached(..., metadata={"plan_id": ...})` 可直接构造，correlation_id 备选分支删除；metadata 落 to_dict **顶层**（:160-164）非 payload 子字典——plan 关联 outbox 断言键为 `payload->'metadata'->>'plan_id'`，R1-D1 调研实证）
  - `CheckpointRecovered` **继续不发布**（恢复完成事件归 6-6 恢复执行面——OD-1）
- [ ] 守护测试承载：既有负向断言（契约+验收+集成三层）零修改通过 = 发布点落位正确的行为级证据

#### 数据模型 (Data Models)

**领域层实体扩展**（`src/domain/entities/checkpoint_snapshot.py` 就地扩展，纯标准库，向后兼容）：

> **Epic 1 骨架资产复用裁定（禁重复造轮）**：`src/domain/entities/checkpoint.py` 既有四类**必须复用激活**（Epic 1 骨架交付，当前生产消费面仅单测——6-3 是首个激活方）：`CorrectionRecord`（:17，**五字段** correction_type/previous_value/new_value/applied_by/applied_at——or.md L305 修正日志要素 5/7 MVP 子集；docstring :21 提及的 correction_id 类中无此字段，注记差异；**零改动复用**，"置信度变化/影响因子"等 6-6 审批面要素届时再扩展）/ `RecoveryMode`（:36，str Enum REPLAY/OVERRIDE，成员值小写 "replay"/"override"——值域与本 Story 判定语义完全一致，零改动；**双枚举知悉注记**：events/enums.py:48 另有同名枚举（值 "Replay"/"Override" 首字母大写）被 CheckpointRecovered 使用——6-6 恢复执行面消费建议恢复模式时需显式转换，6-3 内不冲突）/ `CheckpointStatus`（:43，PENDING/IN_PROGRESS/COMPLETED/RECOVERED——FR-SP-03"完成状态"承载）/ `Checkpoint`（:53，**实际九字段**：checkpoint_id/phase_identifier/status/recovery_mode/summary/correction_records + created_at/completed_at/updated_at（:68-70 时间戳三字段——Task 0 钦定序列化取舍：聚合不整体序列化进 state_data，仅 status 经映射进 completed 键、correction_records 进 correction_history 键）+ validate :72/complete :98/recover :117 状态机守卫 EntityStateTransitionError 243——**聚合根语义激活**：驱动点钦定见 AC-6（创建面 complete()/修正面追加/恢复面只读））。`CheckpointSnapshot`（快照载体）与 `Checkpoint`（状态机聚合）协作分工：前者承载数据面（state_data/persistent_note_ref/checksum），后者承载状态面（完成/恢复状态机）。

- [ ] `CheckpointSnapshot` 新增字段（全部带默认值——6-1/6-2/5-10 三消费面既有构造零破坏；实体不在 entities/__init__.py 导出——消费方直接模块 import，扩展零导出改动）：
  - `persistent_note_ref: str = ""`（持久化笔记引用——UUID 字符串；非空守卫见 AC-2）
  - `checksum: str = ""`（SHA-256 hexdigest——**编排服务在④步构造时显式计算写入**（不在 `__post_init__` 自动算——6-1/6-2/5-10 既有构造零扰动）；apply_correction 更新后服务层重算替换；verify 时重算比对）
  - `snapshot_metadata: dict[str, Any] = field(default_factory=dict)`（压缩元数据键族：compression_ratio/quality_score/token_count/original_token_count/rerun_count——键契约 Task 0 冻结；**双位分工声明**（R2A-10）：compression_ratio/quality_score/token_count 同时存在于实体 snapshot_metadata 与 state_data——两处由同一 CompressedContext 产物同源填充（写入单一来源）、读侧以 state_data 为权威（6-6 消费面/checksum 覆盖位）——防双写源分叉漂移）
  - `checkpoint_no: str = ""`（Checkpoint 编号标识——CP-1/CP-2-7/CP-8 形态，与 stage_number 语义分工：checkpoint_no 是全局恢复点编号字符串，state_data 内可另存 int 序号）
- [ ] 新增方法：
  - `_calculate_checksum() -> str`（SHA-256，参与字段集 Task 0 冻结 **（OD-11）**：`session_id/stage_id/state_version/checkpoint_no/persistent_note_ref` + `state_data` 规范化序列化 `json.dumps(state_data, sort_keys=True, ensure_ascii=False)`——参照设计文档 §2.1 语义的钦定扩展（§2.1 原文 checkpoint_id/stage_id/state_version/persistent_note_ref：保留版本分量、身份字段同构改写、增量载荷覆盖使 AC-3 篡改 state_data 场景可达）；标准库 hashlib+json）
  - `verify_integrity() -> bool`（纯判定重算比对、无副作用不抛异常；缺失 persistent_note_ref 或 checksum 不匹配返回 False——484 抛出点在恢复编排调用方 checkpoint_service.recover，签名与行为一致——AC-3）
- [ ] **复用既有** `CorrectionRecord`（`src/domain/entities/checkpoint.py:17`——**五字段**零改动，MVP 无需 field_path：修正定位经 previous_value/new_value 与调用上下文承载，6-6 审批面需要时再扩展——YAGNI；correction_id 仅 docstring 提及——注记不补字段）
- [ ] **复用既有** `RecoveryMode`/`CheckpointStatus`/`Checkpoint`（checkpoint.py:36/:43/:53——零改动；`Checkpoint` 状态机激活：complete()/recover() 守卫已就位）
- [ ] 新增领域服务纯函数 `recommend_recovery_mode(affected_checkpoint_count: int) -> RecoveryMode`（影响评估判定——AC-7；**返回既有 RecoveryMode 枚举**；≥2 强制 REPLAY、<2 推荐 OVERRIDE；落 `src/domain/services/recovery_mode.py` 新文件，纯标准库）

**完整形态快照 state_data 键契约**（Task 0 冻结——登记于新端口文件模块 docstring 序列化契约区，6-2 三级契约同款纪律）：

- [ ] 键族（**13 键**——Task 0.2 冻结唯一版本，全文同源）：`checkpoint_no`/`stage_id`/`stage_number`（int 序号——CP 位置数字形式，对齐编号体系）/`plan_id`/`completed`（完成状态 bool——CheckpointStatus 映射：True↔COMPLETED/False↔IN_PROGRESS，Task 0 钦定映射表）/`summary`（阶段摘要——承自 per-step 骨架同名字段，调用方直供）/`compressed_context`（压缩后上下文 str）/`compression_ratio`/`quality_score`/`token_count`（压缩产物 token 数——读侧 6-6 显示面）/`persistent_note_ref`/`correction_history`（修正记录 list[dict]，初始空）/`created_via`（触发源标识）
- [ ] 键族契约钦定：`compressed_context` 恒为 str（压缩产物 context 字段）；`correction_history` 恒存在（初始 `[]`——禁"无修正时键缺失"形态，6-2"键恒在"同款纪律，6-6 读侧免双兼容）；`persistent_note_ref` 恒非空（构造守卫保证）
- [ ] 快照键族：session_id = `f"blm-checkpoint-{plan_id}:{checkpoint_no}"`（新前缀单源常量——`CHECKPOINT_SESSION_PREFIX = "blm-checkpoint-"`，最终键 `sisys:snapshot:blm-checkpoint-{plan_id}:{checkpoint_no}`；**与 6-2 骨架键族（blm-planning- 前缀）显式区分**，读侧判别规则 = 前缀 + state_data 含 checkpoint_no 锚）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] **新增端口 1 个**（应用层端口——R2：组合注入 R1 基础端口）：`CheckpointServicePort`（或拆创建/恢复两端口——Task 0 钦定形态；建议单端口双方法组，避免同义接口重复）落 `src/application/ports/checkpoint.py`：
  - 创建方法：`create_checkpoint(plan_id, checkpoint_no, stage_id, query, retrieved_docs, user_id, summary, completed) -> CheckpointSnapshot`（五步编排——入参含持久化笔记所需的 query/检索证据与快照载荷；**内部派生键**：take_notes 第四参 session_id 与快照键同源 `CHECKPOINT_SESSION_PREFIX+plan_id+":"+checkpoint_no`——Task 0.2 钦定落端口 docstring）
  - 修正方法：`apply_correction(session_id 键族参数, correction: CorrectionRecord, expected_state_version: int) -> CheckpointSnapshot`（AC-6——**乐观锁式版本参数**：与键内存活快照 state_version 比对，不匹配（版本倒退/并发过期）→ 482；承载 Task 3 版本倒退红测的构造通道，OD-12 附则）
  - 恢复方法：`recover_checkpoint(...) -> CheckpointRecoveryView`（AC-7——恢复视图 DTO）
  - 判定方法：`recommend_recovery_mode(...) -> RecoveryMode`（透传领域纯函数——可选，直接消费领域服务亦可，Task 0 钦定）
- [ ] 组合注入清单（端口构造参数）：`persistent_note_taker`（domain 服务，已注册 2236-2249，SCOPED）/`context_compressor`（domain 服务，已注册 2262-2276，SCOPED）/`strategic_archive_service`（应用层服务，已注册 2209-2227，SCOPED）/`snapshot_repository`（R1 基础端口，已注册 949-963，SCOPED）/`event_publisher`（R1 基础端口，已注册 605-614）——**五依赖全部既有注册，零新基础端口**；lifetime 组合注记：checkpoint_service 钦定 SINGLETON 注入四 SCOPED 依赖——与 blm_planning_service（SINGLETON :1580-1598 lambda 八参含 SCOPED snapshot_repository）直接先例同款（单例捕获首次 resolve 的 SCOPED 实例，进程级共享——既有形态，R2-D1 亲证）；`checkpoint_use_case` lifetime Task 0 顺手钦定（建议 SINGLETON——无状态透传）
- [ ] 端口契约清单（唯一事实源——禁止语义重复新增）：

| 端口 | 层 | 注册名（composition_root） | 本 Story 动作 |
|---|---|---|---|
| `CheckpointServicePort` | application/ports | `checkpoint_service`（新增，v1.0.0，SINGLETON——无状态编排服务） | **新增** + 契约测试 |
| `SnapshotRepositoryProtocol` | domain/ports | `snapshot_repository`（L950，既有） | 复用（协议零改动；实现层 RedisSnapshotStore 白名单扩列——OD-2） |
| `EventPublisher` | domain/ports | `event_publisher`（L605，既有） | 复用，零改动 |
| `persistent_note_taker` | domain/services | `persistent_note_taker`（L2237，既有） | 复用（首个生产消费方） |
| `context_compressor` | domain/services | `context_compressor`（L2263，既有） | 复用（首个生产消费方） |
| `strategic_archive_service` | application/services | `strategic_archive_service`（L2209，既有 v1.1.0） | 复用（Checkpoint 归档接线） |
| `CreateCheckpointUseCase`（+Recovery 用例，Task 0 钦定拆分） | application/use_cases | `checkpoint_use_case`（新增） | 新增 + resolve 可达测试 |

- [ ] 组合根 `src/composition_root.py` 新增注册 2~3 个（checkpoint_service + checkpoint_use_case[+checkpoint_recovery_use_case]）——**既有注册零 diff**（Task 4 守护）
- [ ] 契约测试 `tests/contracts/test_port_contract_checkpoint.py` 新建（形态对齐 test_port_contract_blm_planning.py：注册可达/spec 元数据/真实构造 resolve/注入链签名）

#### 端口契约清单执行约束（强制）

- [ ] 本清单是唯一事实源（Single Source of Truth）；实现中确需新端口时回 Task 0 补登记 + Contract Gate + 契约测试，禁止边写边加
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象（6-1/6-2 纪律沿袭）
- [ ] 禁止绕过 `SnapshotRepositoryProtocol` 直持 Redis 客户端（读径=经端口 load——6-1 DC-6 同款纪律）

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> 完整检查清单详见 [`sisys-uni-exception-design.md §3.12`](../../docs/architecture/sisys-uni-exception-design.md)；编码分配策略详见 §3.3。

- [ ] **新增领域异常（planning 子域 483-489 预留段取码——`_code_ranges.py` L183 成文"483-489 预留 planning 域"，`sisys-uni-exception-design.md` §3.3.2 L755 双处成文）**，继承 `BusinessException`，落 `src/domain/exceptions/planning_exceptions.py` 就地追加：

| 异常类 | code | 触发场景 | HTTP 映射建议 |
|---|---|---|---|
| `CheckpointCreationError` | EXCEPTION_483 | 五步编排强制环节失败（持久化笔记失败/快照落库失败等——AC-1 负向） | 500 |
| `CheckpointIntegrityError` | EXCEPTION_484 | persistent_note_ref 缺失守卫/checksum 校验失败/篡改检测（AC-2/AC-3） | 409 |
| `CheckpointCompressionError` | ~~EXCEPTION_485~~ **不设码** | 压缩二次路径耗尽仍不达标 → **编排层终态门禁抛 483**（R1-F2 实测反转原预判：ContextCompressor 二次路径耗尽后无最终门禁、不达标产物**原样静默返回不抛**（context_compressor.py:161-186）——「降级路径下不可达」的旧依据不成立；门禁落编排服务（compress 返回后校验双指标）后该路径可达且恰是 483 触发面「编排强制环节失败」，独立码语义冗余不设——OD-7 裁定依据随本审查更新） | — |

- [ ] **482 `PlanningStateError` 追加第二触发点**（既有码**已有生产触发点在位**：6-1 R1-5 同 plan_id 重跑守卫 blm_planning_service.py:242；planning_exceptions.py:16-17 模块 docstring 已记「已激活」——「预留，6.3 Checkpoint 恢复面消费时激活」措辞的出处是 _code_ranges.py:181-182 与 exception_handlers.py:306 注释两处滞后注释；planning_exceptions.py:104 实文为「6.3 Checkpoint 恢复面的状态机守卫扩展位」）：恢复面版本倒退/状态非法——本 Story 新增触发点与 BLM 面既有触发点并存，**类定义/注册/映射零改动**（预留映射 409 已在位）
- [ ] **486-489 保持预留**（本 Story 不占用——留给 6-6 恢复执行面）
- [ ] **禁占** financial 471-479（双重成文预留）与 storage 211-219（9 码全满——Agent 调研实证）
- [ ] 完整 4 项 Checklist 逐项履行：定义文件（planning_exceptions.py 就地追加）→ `_code_ranges.py` `_CLASS_TO_SUBDOMAIN` 注册 + 唯一性 grep（`grep -rn "EXCEPTION_48[3-5]" src/` 预检零占用）→ `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP` → 码段校验测试（test_error_code_uniqueness.py + test_code_ranges.py 全绿 + test_exception_handlers.py）
- [ ] **Story 异常契约文档**：本表即小节（code/parent/触发场景齐备）
- [ ] 异常路径 Gherkin 场景纳入 Edge Cases（AC-2/AC-3 负向场景）

#### API 契约 (API Contract)

- [ ] **零 REST API 变更**（BLM/Checkpoint 面 REST 接线归 7-2——6.1-DF5 先例沿袭）
- [ ] CLI 新增子命令：**扁平子命令 `checkpoint-create`**（argparse 形态钦定——`build_parser()` 内 `subparsers.add_parser("checkpoint-create")` 块 + `main()` 分发分支 + `_run_checkpoint_create_cli` 五步定式函数，参考 `_run_blm_plan_cli` :626-666：参数解析/UUID 守卫先于 bootstrap/用例调用/结果打印/exit 0 成功·1 业务异常；顶级 prog="sisys-agent" 扁平子命令族无嵌套分组——两候选嵌套名不采，R2-F18 钦定）；参数面钦定：`--plan-id`/`--checkpoint-no`/`--stage-id`/`--query`/`--user-id`/`--summary`（retrieved_docs 经空列表构造——take_notes 实体抽取对空检索证据降级容忍 :238-246；`--completed` 默认 True 显式创建面）；**重复创建语义注记**（R3-D）：MVP 允许同 checkpoint_no 重复创建=覆盖快照+追加归档行/事件行（无唯一性约束、不做归档幂等——测试场景用独立 plan_id 规避）；**恢复面 CLI 入口归 6-6**（审批交互面入口——6-3 恢复数据面经用例层消费，R1-F27/R2-F19 裁定消除 owning Task 缺口）

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
- **本 Story 特别注意**：checksum 用标准库 hashlib；Checkpoint 编号/修正记录/判定纯函数全标准库；持久化笔记与压缩编排是**应用层**服务组合 domain 服务（domain 服务已存在且合规——Epic 3 交付时已验证）

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

**设计规则 R1~R4 落点**（用户钦定）：
- **R1** 领域层统一抽象基础端口 → 复用 `SnapshotRepositoryProtocol`/`EventPublisher`/`EntityExtractionPort`/`ArchiveRepositoryPort`/`L3VectorPort`/`L4ObjectPort`（全部既有，本 Story 零新增基础端口）
- **R2** 应用层端口组合注入基础端口 → `CheckpointServicePort`（应用层新端口）组合注入 persistent_note_taker/context_compressor/strategic_archive_service/snapshot_repository/event_publisher 五依赖（既有注册 resolve 注入——6-1 blm_planning_service 同款形态）
- **R3** 基础设施层实现端口并管理技术 → 复用 `RedisSnapshotStore`（Redis Hash JSON 序列化——OD-2 裁定沿用；**序列化白名单扩列四字段——唯一 infra 改动，OD-2/R2A-1**）/`PostgreSQLArchiveRepository`/`QdrantVectorStorage`/`MinIORepository`（含 WORMManager）；零新基础设施实现
- **R4** 接口层适配外部请求 → CLI `checkpoint-create` 子命令（agent_cli.py 既有五步定式）；无 REST 面

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_checkpoint_snapshot.feature`（OD-8 命名——功能名族，禁故事编号后缀）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_checkpoint_snapshot.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）——钉死 **13 场景**（AC-1×2 / AC-2×2 / AC-3×1 / AC-4×2 / AC-5×1 / AC-6×1 / AC-7×2 / AC-8×1 / 收尾×1，Task 0.4 定稿钉死确定值并全文同步，禁范围值进入后续 Task）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（模块级 `event_loop` fixture + `_run_async` helper——6-1/6-2 三件套）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——本 Story 异常路径 = 空引用构造守卫（484）/checksum 篡改（484）/归档 L4 失败阻断（ArchiveStorageError 透传——单测层承载注记见 Task 5.3）/恢复不存在键 480/checksum 损坏 484/版本倒退 482（三分已钦定 Task 0.3）；**压缩 LLM 失败注入**归集成层（Fake LLM 豁免面）
- **R6 模板合规**：feature/py 组织结构对齐 `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`/`.py`——R6 承载四点 = `# language: zh-CN` 中文 Gherkin + AC 横幅注释分组（`# ===` 分隔）+ `@scenario(...)` 多行字面量路径绑定 + 场景绑定与步骤实现交替排列（**注意**：R6 文件自身 py 仅绑定 30 场景中 17 个属旧模板欠账，新文件禁沿用——13 场景全绑定；pytestmark/context dict/`_run_async` 不在 R6 文件中，由 6-1/6-2 三件套基建承载）；**断言必须真实**（禁 then-pass 占位——5-3 用户裁定沿袭）；装配形态对齐 6-1/6-2（真实服务链 + Fake LLM/Fake Embedding 双豁免（外部 SaaS）+ 延迟 import 纪律 + 场景三属性分档表 docstring + teardown 链）；**BDD 硬超时**：conftest `run_with_bdd_timeout` 30s 约束下禁止单步骤内跑全管线多次（性能采样场景独立化；AC-7 多 Checkpoint 前置的三点创建分三个 Given 步骤逐个执行——每步一次全链，R2-F6）
- **场景分化维度表（Task 0.4 钉死输入——含收尾共 13 场景全枚举，R2B-18）**：AC-1×2 = 五步全链创建（13 键断言+TTL）/六子步骤多 Checkpoint 独立性（CP-2/CP-5 双点不覆盖）；AC-2×2 = 空引用构造守卫红/压缩质量门禁（注入首轮不足→rerun；**终态门禁→483 场景归单测层承载——Task 2 红测**，R2A-13）；AC-3×1 = checksum round-trip+篡改红；AC-4×2 = 事件发布字段与 outbox 落行/6-2 负向断言面零破坏互证（同 run 内 BLM 流程零发布+创建用例发布恰一行）；AC-5×1 = L2+L3+L4 三层归档断言（真实服务）；AC-6×1 = 修正记录往返+版本递增；AC-7×2 = 恢复视图+判定纯函数边界（恰 2 强制 Replay）/非法恢复三分（480/484/482）；AC-8×1 = 创建窗口 P95<100ms（20 轮采样）；**收尾×1 = src 与四测试目录完成清单存在性断言（Task 7.3 承载）**
- **pytestmark**：显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.database, pytest.mark.redis, pytest.mark.qdrant, pytest.mark.minio, pytest.mark.xdist_group("blm-planning-perf")]`（**marker 名以 pyproject 注册为准**：`database` 非 `postgresql`——pyproject markers 无 postgresql 且 `--strict-markers` 开启，照写收集即错，R2-F23 钦定；xdist_group 挂法 = **整模块 pytestmark 级**——6-1/6-2 四处先例同款非场景级 decorator，R2-F24）；服务不可达环境 `pytest.skip()` 动态跳过（禁 `@pytest.mark.skip` 写死）
- **6-1/6-2 回归面（强制）**：CheckpointSnapshot 实体扩展后全仓 grep 消费方测试（6-1 验收 14 场景/6-2 验收 14 场景/6-1+6-2 集成 9 场景/service 单测/domain models 单测——**外加四类 5-10/存储面消费方**（R2-F16 补全）：`tests/unit/application/services/test_evaluation_checkpoint_recorder.py`（×5）、`tests/unit/infrastructure/storage/test_redis_snapshot_store.py`（×3——**序列化直测：R2A-1 裁定后该文件从「预期零适配」改为「扩展序列化用例」**（新四字段 round-trip+旧数据回退）——既有七字段断言保持零适配；失配即回 Task 1 修白名单而非删断言）、`tests/acceptance/test_acceptance_autonomous_invocation_execute.py`（×3）、`tests/integration/test_integration_execute.py`（×1）；扩展带默认值向后兼容预期零适配；发现失配即回 Task 1 修守卫/白名单）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（实体字段级冻结/state_data 键契约/端口方法签名/异常码分配/CLI 入口/锚定义务七条裁定）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态 = 步骤函数运行期失败：延迟 import 抛 `ImportError`（缺失类名）或断言步 `AssertionError`；**收集期零错误本身即延迟 import 纪律的自证**——6-2 先例）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：① 组合根新注册 resolve 可达（checkpoint_service/checkpoint_use_case——注入链五依赖非 None）② CheckpointReached 真实发布验证（发布点代码位 + outbox 落行可断言 + 既有负向断言面零修改通过）③ 检索-压缩循环激活验证（persistent_note_taker/context_compressor 被生产代码 resolve——休眠清偿证据）④ CLI checkpoint-create 入口接线（新用例测试）；「已实现未接线」组件登记 deferred-work
- [ ] **锚定义务七条裁定落档**（Task 0.7——deferred-work 台账更新，逐条处置见 Dev Notes「锚定义务清单」）：
  1. deferred L132 检索-压缩循环待接线（Epic 6+ 核实）→ **本 Story 核销**（首个生产消费方落地）
  2. deferred L127 记忆链路 12 端口（锚"6-3 恢复面或 Epic 9"）→ Task 0 调研裁定（预判：不触发——Checkpoint 恢复读快照存储不走 unified_storage 记忆链路，锚位顺延 Epic 9，与 6-1 同款裁定形态）
  3. deferred L170 消费基建四件（候选"6-3 Checkpoint 恢复消费面"）→ Task 0 调研裁定（预判：**不触发**——6-3 是 CheckpointReached 的生产方而非消费方，与 5-3 同款"纯生产方"裁定；锚位顺延 6-6 审批流转/Epic 8）
  4. deferred L195 checkpointer（图工厂可选参数属 6-3）→ Task 0 调研裁定（预判：不引入——6-3 快照走应用层显式创建，不改 `SpBlmGraph.compile()`；注记落档）
  5. deferred L293 CHECKPOINTED 第六态（触发 6.3 再评估）→ Task 0 调研裁定（预判：不引入——MVP 显式触发面下第六态语义仍不可达；与 L306 AgentStatus 同族互链注记一并更新）
  6. 6.2-DF3（L340）CheckpointReached LIKE 转义守护 → **本 Story 清偿**（AC-4 承载）
  7. 6.2-DF5（L342）`_runs` 无淘汰机制（快照真源切换/恢复面实施时处理）→ Task 0 调研裁定（预判：6-3 恢复面读快照存储不依赖 `_runs`（单 run 状态组装器），真源切换不发生；注记落档维持 deferred 或按实施形态核销）

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
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言；6-1 属性形态断裂族三犯教训详见 Dev Notes）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | CheckpointSnapshot 扩展 | 新字段默认值兼容/守卫/checksum/verify_integrity/round-trip | `tests/unit/domain/entities/test_checkpoint_snapshot.py`（扩展） | Task 1 |
| **TDD 单元测试** | Checkpoint 聚合激活（复用 Epic 1 骨架） | validate 不变量/complete·recover 状态机守卫/CorrectionRecord round-trip——激活验证 | `tests/unit/domain/entities/test_checkpoint.py`（既有，扩展） | Task 1 |
| **TDD 单元测试** | 影响评估纯函数 | ≥2/<2 边界/返回既有 RecoveryMode 枚举 | `tests/unit/domain/services/test_recovery_mode.py`（新建） | Task 1 |
| **TDD 单元测试** | CheckpointService 五步编排 | 调用序（note→compress→archive→snapshot→publish）/守卫抛点/容错语义/事件构造/压缩终态门禁 | `tests/unit/application/test_checkpoint_service.py`（新建） | Task 2 |
| **TDD 单元测试** | 恢复数据面 | load/verify/反序列化/DTO 键契约/482 第二触发点/版本递增 | `tests/unit/application/test_checkpoint_service.py`（同文件分组） | Task 3 |
| **TDD 单元测试** | 领域异常 | 483/484 构造/context/to_dict/HTTP 映射 | `tests/unit/domain/exceptions/test_planning_exceptions.py`（既有文件扩展）+ `tests/unit/interfaces/api/test_exception_handlers.py`（既有文件扩展） | Task 1 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~8 全覆盖） | `test_acceptance_checkpoint_snapshot.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_checkpoint_snapshot.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约 | 新端口注册/版本/注入链/resolve 可达 | `tests/contracts/test_port_contract_checkpoint.py`（新建） | Task 2 |
| **TDD 契约测试** | 事件通道守护 | CheckpointReached 发布接线正向守护 + 6.2-DF3 转义守护 + 既有负向断言零修改通过 | `tests/contracts/test_event_channel_mapping_blm_planning.py`（扩展）+ 新守护用例 | Task 4 |
| **SDD 架构验证** | 六边形架构约束 | domain 零依赖（扩展后复核）/服务落位/发布点落位守护（负向：blm_planning 四文件零引用）/公理二链路守护 | `tests/unit/architecture/test_checkpoint.py`（新建，epics 钦定名） | Task 6 |
| **集成测试** | 真实链协作 | 创建全链（真 Redis/PG/Qdrant/MinIO + Fake LLM/Fake Embedding 双豁免）/outbox 落行/公理二负向/恢复+篡改/性能采样 | `tests/integration/test_integration_checkpoint.py`（新建，OD-8） | Task 5 |
| **回归测试** | 6-1/6-2 消费方适配 | CheckpointSnapshot 扩展向后兼容（验收 14+14/集成 4+5/service+domain 单测全绿零适配） | 6-1/6-2 既有测试文件（预期零修改） | Task 4 |
| **回归测试** | CLI 入口回归 | 既有 blm-plan 8 用例零破坏 + 新子命令用例 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 2 |
| **单元测试** | 用例层 | CreateCheckpointUseCase 编排/参数守卫 | `tests/unit/application/use_cases/test_checkpoint_use_case.py`（新建） | Task 2 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**（本 Story 主改动层——epics 钦定）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）——实体扩展/纯函数部分遵循
- [ ] **集成测试覆盖率 ≥75%**（epics 钦定）
- [ ] **关键路径 100% 覆盖（枚举分支逐一有专属用例口径）**：五步编排调用序（含压缩终态门禁分支）/ persistent_note_ref 守卫 / checksum verify（round-trip+三类篡改）/ 事件发布 / 恢复验证链（三分异常各一）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`，禁止 `--no-verify`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **BDD async 配合** | BDD 步骤函数不使用 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()`（模块级 event_loop fixture + `_run_async`） | context 数据丢失 |
| **延迟 import 纪律** | 本 Story 新交付模块一律步骤函数体内延迟 import | pytest 收集期 collection error |
| **真实服务清理** | teardown 链式清理：outbox 按 event_id 精确 DELETE / Qdrant 点按 ID 精确 DELETE / MinIO 对象精确删除 / PG archive 行按 ID 精确 DELETE / Redis 键逐键精确删除（禁 flush） | 跨场景污染 |
| **快照键隔离** | checkpoint 键族用 UUID 前缀 plan_id 生成，与 6-1/6-2 键族前缀显式区分（blm-checkpoint- vs blm-planning-） | 键冲突 |
| **归档隔离** | StrategicArchive 归档用独立 plan_id（UUID 前缀），L3 点/L4 对象按 archive_id 精确清理 | 真实数据污染 |
| **性能场景口径** | 创建窗口采样 20 轮固定输入（Fake LLM 返回固定压缩产物——压缩延迟显式出栈 OD-6） | 采样冲突 |
| **xdist 分组** | 性能/采样场景挂 `xdist_group("blm-planning-perf")`（复用既有组名——6-2 R2-2 先例：与 6-1/6-2 采样场景全局同 worker 串行，防跨组并行抬 P95） | 采样冲突 |
| **事件清理** | 事件 outbox 登记入 context（`_outbox_event_ids`——**含 ⑤ CheckpointReached 与 ③ ArchiveCreated 两类**，R2A-8）供 teardown 精确删除 | 残留行 |
| **pytestmark** | 显式全套声明（marker 名以 pyproject 注册为准——database 非 postgresql；xdist_group 模块级挂） | marker 漏打/收集错误 |

**禁止行为：**
- ❌ 验收/集成测试 mock 真实服务（Fake LLM + Fake Embedding 双豁免——外部 SaaS 同类（LLM 摘要/实体抽取与 embedding 向量），R2-F2；如需 stub 边界端口须 `AsyncMock(spec=)` + 显式真实 dict return_value 且仅限无安全清理方案的纯单元场景）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio` / pytest-xdist 并行时 BDD 步骤内 `asyncio.run()`
- ❌ autouse fixture 删除全局匹配资源
- ❌ `@pytest.mark.skip` 写死跳过（用 `pytest.skip()` 动态探测跳过）
- ❌ 修改阈值/规则消除告警；`# noqa`/`# type: ignore`/`# pylint: disable` 等抑制注释（红线）
- ❌ 裸 `pytest tests/`（会挂起——显式四目录：`pytest tests/unit tests/integration tests/contracts tests/acceptance`）
- ❌ 手动 delete/truncate 共享表（自创建自清理）

**验证要求：**
- [ ] `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance` 四目录全量通过（含 6-1/6-2 全部既有测试零回归）
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` / `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 五步编排+快照落库+TTL 30 天 | Task 0 / Task 2 | 0.1-0.2 规范 / 2.1 编排实现 | `test_checkpoint_service.py` |
| AC-1 | 实体完整形态字段与编号体系 | Task 1 | 1.1-1.2 实体扩展 | `test_checkpoint_snapshot.py` |
| AC-1 | 集成全链验证 | Task 5 | 5.1 场景① | `test_integration_checkpoint.py` |
| AC-2 | 公理二守卫+压缩门禁 | Task 0 / Task 1 / Task 2 | 0.3 异常设计 / 1.2 守卫 / 2.2 编排守卫抛点 | `test_checkpoint_snapshot.py` + `test_checkpoint_service.py` |
| AC-2 | 公理二负向集成 | Task 5 | 5.3 场景③ | `test_integration_checkpoint.py` |
| AC-3 | checksum 计算+完整性验证 | Task 1 | 1.2 checksum/verify | `test_checkpoint_snapshot.py` |
| AC-3 | 篡改检测集成 | Task 5 | 5.4 场景④ | `test_integration_checkpoint.py` |
| AC-4 | CheckpointReached 发布点 | Task 2 | 2.1 发布步骤 | `test_checkpoint_service.py` |
| AC-4 | 发布接线守护+DF3 清偿 | Task 4 | 4.2 守护扩展 | `test_event_channel_mapping_blm_planning.py` |
| AC-4 | outbox 落行集成 | Task 5 | 5.2 场景② | `test_integration_checkpoint.py` |
| AC-5 | L2-L5 归档接线（1-15b 清偿） | Task 2 / Task 5 | 2.1 归档步骤 / 5.1 三层断言 | `test_checkpoint_service.py` + 集成 |
| AC-6 | 修正记录复用+不可变更新 | Task 1 / Task 3 | 1.5 聚合激活 / 3.1 修正应用 | `tests/unit/domain/entities/`（既有扩展——test_checkpoint.py）+ `test_recovery_mode.py`（新建）+ `test_checkpoint_service.py` |
| AC-7 | 恢复数据面+判定纯函数+482 第二触发点 | Task 1 / Task 3 | 1.5 纯函数 / 3.1 恢复实现 | `test_recovery_mode.py` + `test_checkpoint_service.py` |
| AC-8 | 创建窗口 P95+成功率 | Task 5 / Task 7 | 5.5 性能采样 / 7.2 验收 | 集成 + 验收（xdist_group） |
| 全 AC | 新端口契约 | Task 2 / Task 4 | 2.1 端口定义 / 4.1 契约测试 | `test_port_contract_checkpoint.py` |
| 全 AC | CLI 接线（R4） | Task 2 | 2.3 用例+CLI | `test_agent_cli.py` |
| 全 AC | 6-1/6-2 回归面 | Task 4 | 4.3 回归验证 | 6-1/6-2 既有文件 |
| 全 AC | 架构约束验证 | Task 6 | 6.1~6.4 四验证器 | `test_checkpoint.py` |
| 全 AC | 锚定义务+收尾 | Task 0 / Task 7 | 0.7 裁定 / 7.3-7.5 收尾 | 验收收尾 + deferred 台账 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-8（全部规范面）

> **目的：** 在进入代码实现前，明确实体字段级契约、state_data 键契约、端口方法签名、异常码分配、发布点落位与锚定义务七条裁定。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定稿 Checkpoint 完整形态实体字段级契约（上文数据模型节逐字段冻结：persistent_note_ref/checksum/snapshot_metadata 五键/checkpoint_no + checksum 参与字段集——**OD-11 已钦定：身份五字段+state_data 规范化序列化**；**复用面确认**：CorrectionRecord/RecoveryMode/CheckpointStatus/Checkpoint 既有四类零改动复用——字段映射注记而非字段定义）；**Checkpoint 编号体系钦定**：checkpoint_no 值域 = {"CP-1", "CP-2".."CP-7", "CP-8"}（**BLM 前两阶段 8 恢复点**——CP-1=performance_gap 完成后/CP-2-7=六子步骤各一（对齐 §17.4.1）/CP-8=synthesis 后（**本 Story 钦定**——设计图 §17.4.1 CP-8 挂阶段 3，6-2 交付 synthesis 第八 stage 使前两阶段恢复点闭环；R1-D4 调研定谳）；与 stage_id 映射表冻结：CP-1↔performance_gap、CP-2↔market_insight_trend…CP-7↔market_insight_opportunity_gap、CP-8↔market_insight_synthesis（六子步骤名以 6-2 STAGE_VALUE_DOMAIN 为准——§17.4.2 第六步「看风险」已被 6-2 OD-2 裁定不采用）；**与既有 Checkpoint.phase_identifier 的承载分工钦定**：phase_identifier 复用 stage 值域（STAGE_VALUE_DOMAIN 同源——与 CheckpointReached.phase_identifier 同口径），checkpoint_no 是序号锚）；冻结后登记于本 Story 文件（实现 Task 不得增删字段）
- [ ] Subtask 0.2: 钦定完整形态快照键契约与 state_data 键契约（上文数据模型节：`blm-checkpoint-` 前缀单源常量/checkpoint_no 后缀/**13 键族**/correction_history 恒在/persistent_note_ref 恒非空；take_notes 第四参 session_id 与快照键同源钦定一并登记）；登记于新端口文件模块 docstring 序列化契约区（6-2 三级契约同款纪律）；**6-2 既有骨架键族契约零改动注记**（blm-planning- 前缀双键族维持 86400——OD-3）
- [ ] Subtask 0.3: 冻结异常码分配（483/484 必设 + 485 **裁定不设**——OD-7 已按 R1-F2 实测更新：compress 无最终门禁静默返回不达标产物，编排层终态门禁抛 483 承载）；**恢复面异常三分钦定**（R1-D1 定谳：load 静默 None 语义下 JSON 损坏与不存在键同路径不可区分——键不存在与 JSON 损坏统一 480 PlanningNotFoundError（复用既有类承载 checkpoint 语境——构造参数语境本 Subtask 钦定，与 480 既有 docstring"plan_id 不存在"语义对齐复核）/checksum 不匹配→484/版本倒退与状态非法→482 第二触发点（经 apply_correction 乐观锁参数构造））；482 叙事口径：已有 6-1 R1-5 生产触发点在位（blm_planning_service.py:242），本 Story 追加非处子激活；运行 `grep -rn "EXCEPTION_48[3-9]" src/` 预检零占用（R1-D2 已实跑零命中）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_checkpoint_snapshot.feature`（**13 场景钉死确定值**：AC-1×2/AC-2×2/AC-3×1/AC-4×2/AC-5×1/AC-6×1/AC-7×2/AC-8×1/收尾×1——按场景分化维度表定稿，钉死后全文同步，禁范围值进入后续 Task）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_checkpoint_snapshot.py`（docstring 五段：模板基准声明（R6——postgresql_relational_layer 对齐）/场景三属性分档表（依赖 Redis/PG/Qdrant/MinIO 四真实服务的场景逐档动态 skip；**embedding-api 依赖注记**：strategic_archive_service 强制依赖 embedding_service（组合根 :1758 EmbeddingAPIClient 外部 SaaS）——Fake Embedding 与 Fake LLM 同为外部 SaaS 豁免（固定维度向量 AsyncMock 注入，L3 写入链可构造；**禁照抄 3-10 验收/集成 AsyncMock L3/L4/L5/embedding 的先例**——违反本 Story no-mock 红线，R2-F2 钦定））/门控档位/延迟 import 纪律/Run with + 隔离清单；模块级期望常量独立构造——state_data 13 键族/checkpoint_no 值域禁经被测服务生成；pytestmark 见验收标准节 marker 钦定）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——预期运行期 `ImportError`（延迟 import 缺失类名）或 `AssertionError`，收集期零错误；记录失败形态）
- [ ] Subtask 0.7: **锚定义务七条裁定落档**（deferred-work.md 逐条更新：#1 L132 核销注记 / #2 L127 顺延注记 / #3 L170 顺延注记（生产方非消费方裁定）/ #4 L195 注记 / #5 L293 注记（含 L306 互链）/ #6 L340 DF3 清偿 / #7 L342 DF5 处置注记；sprint-status.yaml L180 TODO 注释更新由 Task 7 收尾承载）
- [ ] Subtask 0.8: 既有资产复核（作为实现 Task 改动输入）：① DomainEvent base.py 构造签名核验（**R1-D2 已定谳**：metadata 参数在位（:74）——AC-4 plan 关联通道已钦定 metadata，本项转为构造样例登记）② StrategicArchiveService.archive_plan 入参与持久化笔记载荷映射表冻结（**三项冻结**：载荷映射——compressed_context→evidence_blob/decision_basis、笔记 entities Top-20/summary/lineage→assumptions；入参取值——`plan_type="checkpoint"` 钦定、archive_type 默认 ASSUMPTION 维持；bytes 序列化形态——evidence_blob 为 compressed_context UTF-8 bytes）③ CheckpointReached 负向断言面清单复核（契约 L88-104/L126-134 + 6-2 验收 L1221-1348 + 6-2 集成 7 处——确认零修改通过条件）④ `grep -rn "CheckpointSnapshot(" src/ tests/` 消费面清单（扩展兼容性输入——**六文件全域**：含 5-10 面两文件与 redis_snapshot_store 直测/自动执行面，见回归面清单）⑤ Checkpoint 聚合复用面核验（`grep -rn "from src.domain.entities.checkpoint import\|entities.checkpoint" src/ tests/`——既有生产消费面与测试文件盘点，激活验证落位）⑥ 1-15a/1-15b File List 与磁盘不一致事实知悉注记（SixLayerStorageCoordinator/memory_index 等已被 90-5 重构移除——L3/L4 接线以 StrategicArchiveService 现状为准，故事文本的 coordinator 形态不采信）⑦ **context_compressor 注册块 evaluator 注入在位性核验**（组合根 :2262-2276 lambda 的 quality_evaluator=resolve_optional 是否实际注入——未注入则质量二次路径不可触发，AC-2 质量维度 VC 收窄为压缩率维度并声明——R1-F18）⑧ **归档 L4 失败注入归属裁定**（集成层禁 mock 真实服务（no-mock 红线）下「bucket 不可达双探测 skip」不可构造稳定红——裁定单测层 AsyncMock 承载（6-2 R3-4 同款互斥裁定），Task 5.3 集成场景聚焦正常面——R2B-10 消除悬空引用）
- [ ] Subtask 0.9: 链路接线断言清单四项定义（组合根 resolve 可达/CheckpointReached 真实发布+负向面零修改/检索-压缩循环激活/CLI 接线——见 Task 0 完成标志）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（字段表冻结/键契约/异常码/端口签名/编号体系/七条裁定）
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] OD-1~OD-12 落档（见 Dev Notes「关键架构决策」——含 R1 审查新增 OD-11 checksum 字段集/OD-12 五步序合成）+ deferred-work 台账更新

---

### Task 1: 领域层——实体完整形态扩展（含序列化白名单配套）+ Checkpoint 聚合激活 + 恢复判定纯函数 + 异常

**关联 AC:** AC-1 / AC-2 / AC-3 / AC-6 / AC-7（实体承载面；含序列化白名单扩列——唯一 infrastructure 触点，OD-2/R2A-1：实体新增四字段不扩白名单则 save 静默丢弃 → load 缺失 → checksum 恒空 → 恢复恒误报 484——实体扩展与序列化读回必须同循环闭环）

#### TDD 循环 A：CheckpointSnapshot 完整形态扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/entities/test_checkpoint_snapshot.py`：新字段默认值向后兼容（既有构造零参通过——checksum 空串默认不自动算，AC-3 初始化链）/ persistent_note_ref+checksum+snapshot_metadata+checkpoint_no 填充构造 / **守卫：persistent_note_ref 为空 + checkpoint_no 非空时构造抛 484**（空引用守卫——Task 0 钦定守卫触发条件：进入完整形态即校验）/ _calculate_checksum 确定性（同输入同输出——身份五字段+state_data 规范化序列化参与，OD-11）/ verify_integrity round-trip 绿 + 篡改红（**篡改 state_data 任一键**（compressed_context 等——载荷参与 checksum 的可达性证明）/替换 persistent_note_ref/篡改实体顶层 checkpoint_no → False）/**with_updated_state 透传断言**（更新后新四字段保留——R2A-3：现状实现只透传原七字段，修正通道会静默丢失新字段）/ **异常用例组**（483/484 构造与 code 断言——`tests/unit/domain/exceptions/test_planning_exceptions.py` 扩展 + `tests/unit/interfaces/api/test_exception_handlers.py` HTTP 映射扩展，R2B-13 owning 落位：异常类未定义时红=AttributeError）/ **序列化 round-trip**（`tests/unit/infrastructure/storage/test_redis_snapshot_store.py` 扩展：新四字段经 save→load 读回不丢失+旧七字段数据 load 缺键回退默认值——R2A-1） |
| 🟢 绿 | `src/domain/entities/checkpoint_snapshot.py` 就地新增四字段（全部默认值——向后兼容）+ 两方法（hashlib SHA-256；**verify 纯判定返回 bool 不抛——484 抛出点在恢复编排调用方，OD-11**）+ **`with_updated_state` 透传新增四字段**（checksum 除外——由服务层重算写入，R2A-3）；新增异常类落地（planning_exceptions.py 追加 483/484 + 4 项 Checklist 全链——485 不设码）；**`redis_snapshot_store.py` 序列化白名单扩列四字段+读侧缺键回退**（唯一 infra 改动，OD-2/R2A-1） |
| 🟡 变异 | 删除守卫分支 → 空引用用例红 → 还原绿；checksum 参与字段删一个（如 state_data 序列化项）→ 篡改 state_data 用例红 → 还原绿 |
| 🔄 重构 | docstring 全中文 Google 风格更新（属性说明+公理二注记+**可哈希性注记**：既有 dict 字段基础上新增 dict 字段——frozen dataclass hash 本已抛 TypeError，注记维持）；`ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写实体扩展失败测试（上述用例组）
- [ ] Subtask 1.2: 🟢 绿 — 实现四字段+两方法+异常落地
- [ ] Subtask 1.3: 🟡 变异 — 守卫/checksum 参与字段双突变实证
- [ ] Subtask 1.4: 🔄 重构 — 注释/类型/命名收敛 + 异常测试全绿（test_error_code_uniqueness/test_code_ranges/test_exception_handlers）

#### TDD 循环 B：恢复判定纯函数 + Checkpoint 聚合激活

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `tests/unit/domain/services/test_recovery_mode.py`（0/1→OVERRIDE、2/3/10→REPLAY、**边界 2 恰好 REPLAY**、负数与非法入参→EntityValidationError）+ 扩展既有 `tests/unit/domain/entities/test_checkpoint.py`（**实测已存在**——import Checkpoint/CheckpointStatus/RecoveryMode :8；补激活验证：correction_records 序列化 round-trip/**complete 守卫经创建面④生产调用断言**（completed=True 路径——AC-6/OD-12 附则 a；**recover 守卫维持既有聚合单测断言不进 6-3 编排**——恢复面只读，R2A-4：编排面生产调用 recover() 会触发「全部恢复场景被 243 拒绝」陷阱）） |
| 🟢 绿 | 实现 `src/domain/services/recovery_mode.py` 纯函数（返回既有 RecoveryMode——import 自 entities/checkpoint.py；Checkpoint 生产代码零改动——激活=应用层消费） |
| 🟡 变异 | 判定阈值 2→3 → 边界用例红 → 还原绿；Checkpoint.recover 守卫删除 → 既有守卫用例红 → 还原绿 |
| 🔄 重构 | docstring（or.md L305 修正日志要素注记/core-domain §8.1 双模式语义注记/Epic 1 骨架激活注记） |

- [ ] Subtask 1.5: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 恢复判定纯函数 + Checkpoint 聚合激活验证（循环 B）
- [ ] Subtask 1.6: 🔄 重构 — 复用面 docstring 注记收敛（CorrectionRecord 五字段与 or.md 要素映射注记落 entities/checkpoint.py——**注释级增强零行为改动**；correction_id 仅 docstring 提及的差异注记一并落）

**完成标准/Definition of Done:**
- [ ] 实体扩展完成，既有用例零回归（带默认值向后兼容——test_checkpoint_snapshot.py 既有用例+5-10 面用例全绿）；**序列化白名单扩列闭环**（新四字段 save→load round-trip 直测绿+旧数据缺键回退绿——R2A-1）
- [ ] Checkpoint 聚合激活验证通过（validate/complete/recover 守卫断言在位——复用面生产消费首证）
- [ ] 领域层零依赖复核（扩展后仍纯标准库——hashlib/json/uuid 均标准库）
- [ ] 异常 4 项 Checklist 全绿（编码唯一性/子域范围/HTTP 映射/导出完整性）
- [ ] 覆盖率：枚举分支逐一有专属用例+突变实证佐证（守卫三分支+verify 两分支+判定边界+压缩终态门禁）

---

### Task 2: 应用层——CheckpointService 五步编排 + 端口 + 用例 + 组合根 + CLI

**关联 AC:** AC-1 / AC-2 / AC-4 / AC-5

#### TDD 循环 A：端口定义与服务编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `tests/unit/application/test_checkpoint_service.py`：五步调用序断言（**note_taker.take_notes → compressor.compress → archive_service.archive_plan → snapshot_repository.save → event_publisher.publish**——OD-12 五步序：压缩先于归档（§11.2.6 触发链+1-15b 压缩后内容条件对象）；**AsyncMock(spec=ProtocolClass) 五依赖 + 调用序记录**，6-2 Mock 工厂模式）/ persistent_note_ref 从压缩产物透传（CompressedContext.persistent_note_ref → 快照字段）/ TTL=2592000 / state_data **13 键** / CheckpointReached 构造字段（checkpoint_id=快照 snapshot_id、phase_identifier=stage_id、user_feedback_request=True、metadata plan 关联——**已定谳 metadata 通道**，plan 关联断言键 `payload->'metadata'->>'plan_id'`）/ 发布失败不回滚（publisher 抛异常 → 快照仍在——save 调用先于 publish 且 publish 容错）/ 归档 L2·L4·ArchiveCreated 发布失败（archive_plan 抛 ArchiveStorageError 284）→ 483 包装透传且 save 零调用（无半成品）/ **压缩终态门禁**（compress 返回双指标不足产物 → 483 抛出且 save/archive 零调用——R1-F2 静默终态的编排层 fail-loud） |
| 🟢 绿 | 新建 `src/application/ports/checkpoint.py`（端口+前缀常量+序列化契约 docstring）+ `src/application/services/checkpoint_service.py`（五步编排——R2 组合注入五依赖；守卫/容错/事件构造按红测实现） |
| 🟡 变异 | 编排步骤删除归档调用 → 调用序断言红 → 还原绿；TTL 字面量改 86400 → TTL 用例红 → 还原绿 |
| 🔄 重构 | 类型注解/docstring（五步流程图注记——architecture §8.2 对齐）/`ruff`+`mypy` |

#### TDD 循环 B：用例 + 组合根 + CLI

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `tests/unit/application/use_cases/test_checkpoint_use_case.py`（编排透传/参数守卫/plan_id UUID 校验）+ 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（checkpoint-create 子命令：成功 exit 0+输出含 checkpoint_no/业务异常 exit 1——五步定式断言）+ 新建 `tests/contracts/test_port_contract_checkpoint.py`（注册可达/spec 元数据/真实构造 resolve 五依赖注入链非 None——形态对齐 test_port_contract_blm_planning.py） |
| 🟢 绿 | 新建 `src/application/use_cases/create_checkpoint.py`（+恢复用例骨架归 Task 3——本 Task 只创建用例）；组合根新增注册（checkpoint_service v1.0.0 SINGLETON lambda 五依赖 + checkpoint_use_case）；agent_cli.py 新增 checkpoint-create 子命令（五步定式） |
| 🟡 变异 | 组合根注册删除 → 契约测试红 → 还原绿；CLI 输出删 checkpoint_no → CLI 用例红 → 还原绿 |
| 🔄 重构 | 命名/注解收敛；组合根注册注释（与既有 blm_planning_service 注册同风格） |

- [ ] Subtask 2.1: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 端口定义+服务五步编排（循环 A）
- [ ] Subtask 2.2: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 守卫与容错语义（循环 A——483 包装/发布容错/归档透传）
- [ ] Subtask 2.3: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 用例+组合根+CLI（循环 B）

**完成标准/Definition of Done:**
- [ ] 五步编排关键路径 100% 覆盖（正常/守卫/容错三分支）
- [ ] 契约测试全绿（新端口注册可达+注入链）
- [ ] CLI 既有 8 用例零回归 + 新子命令用例绿
- [ ] `ruff` + `mypy` 通过

---

### Task 3: 应用层——恢复数据面（load+verify+恢复视图+修正应用+482 第二触发点）

**关联 AC:** AC-6 / AC-7

#### TDD 循环 A：恢复与修正

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/test_checkpoint_service.py`（恢复分组）：apply_correction（构造 CorrectionRecord → with_updated_state 不可变更新 → state_version+1 → correction_history 追加 → persistent_note_ref 血缘保留 → **checksum 重算替换后 round-trip verify 绿**——AC-3 重算点）/ recover（load → verify_integrity（False → 编排层抛 484 拒绝恢复——实体纯判定）→ 组装恢复视图 DTO ≥7 键——Task 0 冻结键族）/ 键不存在 → 480（load 返回 None 语义——含 JSON 损坏同路径）/ 损坏快照（**读回后篡改 state_data 再 verify**——checksum 不匹配构造路径）→ 484 / 版本倒退（**apply_correction 传 expected_state_version 低于键内存活版本**——乐观锁式参数，OD-12 附则）→ **482 第二触发点** / 判定纯函数透传（后续 checkpoint 清单计数 → recommend_recovery_mode） |
| 🟢 绿 | checkpoint_service 扩展恢复方法组（+恢复视图 DTO——dataclass 落端口文件或 use_cases 层，Task 0 钦定）；482 新触发点（既有类零改动） |
| 🟡 变异 | verify 调用删除 → 篡改快照恢复用例红 → 还原绿；482 触发点删除 → 版本倒退用例红 → 还原绿 |
| 🔄 重构 | 恢复视图 DTO docstring（6-6 消费面注记——OD-1 边界声明）/`ruff`+`mypy` |

- [ ] Subtask 3.1: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 修正应用+恢复视图+守卫激活（循环 A）

**完成标准/Definition of Done:**
- [ ] 恢复三分支（正常/不存在/损坏）关键路径 100% 覆盖
- [ ] 482 第二触发点验证：恢复面触发点在位 + 既有 HTTP 映射 409 零改动通过
- [ ] 修正历史 round-trip 用例绿（写入→读回→追加→再读回）

---

### Task 4: 契约守护与 6-1/6-2 回归面

**关联 AC:** AC-4 / 全 AC 回归

> **性质说明：** 本 Task 是 SDD 规范验证（守护型）+ 适配器契约变更回归面（记忆纪律：改共享契约后全仓 grep 消费方测试，禁只跑直接文件）。

- [ ] Subtask 4.1: 新建 `tests/contracts/test_port_contract_checkpoint.py` 全量绿（Task 2 已建——本 Subtask 复核 resolve 可达+五依赖注入链+SINGLETON lifetime 断言）
- [ ] Subtask 4.2: 扩展 `tests/contracts/test_event_channel_mapping_blm_planning.py`：**CheckpointReached 发布接线正向守护**（新 checkpoint 服务文件源码含发布调用——存在性断言）+ **既有负向断言零修改通过验证**（blm_planning_service/run_blm_planning/get_blm_planning_status/blm_planning_prompts 四文件零引用断言保持——发布点落位正确的行为级证据）+ **6.2-DF3 清偿：LIKE 转义独立守护**（**纯模式级断言钦定**——无 DB 依赖：守护用例断言 6-2 侧断言 SQL 模式串含转义形态 `market\_insight%` 而非未转义 `market_insight%`（源文件字面校验+注入未转义形态可检出的模式检测函数——契约目录维持零服务依赖，R2-F29 钦定））+ event_channels.yaml/DEFAULT_MAPPINGS 对 CheckpointReached **零 diff 守护**（既有双登记保持断言）
- [ ] Subtask 4.3: **6-1/6-2 回归面全量验证**（CheckpointSnapshot 扩展向后兼容实证）：6-1 验收 14 场景 + 6-2 验收 14 场景 + 6-1/6-2 集成 9 场景 + service/domain 单测全绿（预期零适配——扩展带默认值；发现失配即回 Task 1 修守卫而非适配测试）；6-2 AC-3 负向断言零适配通过 = run 路径与创建用例正交的行为级证据（AC-4 最后一条 VC）
- [ ] Subtask 4.4: 组合根注册面复核（新注册 2~3 个在位 + 既有注册零 diff——`git diff src/composition_root.py` 变更仅新增块）+ 事件 yaml/router 零 diff 守护 + CLI 全量回归

**完成标准/Definition of Done:**
- [ ] 6-1/6-2 全部既有测试零回归通过（以运行时收集数为准）
- [ ] 守护测试通过（发布接线正向+负向零修改+转义守护+零 diff）
- [ ] 契约目录全量绿（含新增 checkpoint 契约）

---

### Task 5: 集成测试——真实链五场景

**关联 AC:** AC-1 / AC-2 / AC-3 / AC-4 / AC-5 / AC-7 / AC-8

> **模式：** 6-1/6-2 集成同款——真实 Redis/真实 PG（outbox+archive）/真实 Qdrant（L3）/真实 MinIO（L4）+ **Fake LLM+Fake Embedding 双豁免**（压缩摘要/实体抽取 LLM 消费点+embedding 向量——外部 SaaS；take_notes 的 entity_extractor 与 compress 的 llm_client 两注入位并列，R1-F26）；服务不可达双探测动态 skip；`try/finally` 自包含（teardown：**outbox 按 event_id 精确 DELETE——`_outbox_event_ids` 收集面覆盖全部两类事件**：⑤ CheckpointReached + **③ ArchiveCreated**（archive_plan 每次调用落一行——R2A-8，照 5.2 先例只收集 ⑤ 会残留 ③ 事件行污染真实 PG）/ Qdrant 点按 ID DELETE / MinIO 对象精确删除 / PG archive 行按 ID DELETE / Redis 键逐键删除——**点名三键族**：`sisys:snapshot:blm-checkpoint-*` 快照键 + `note:{note_id}` 笔记缓存键 + `compressed:{note_id}` 压缩缓存键，R2A-8）。

- [ ] Subtask 5.1: 场景① 创建全链：真实链五步完整跑通（输入=真实检索证据或构造 SearchResult 族）——完整形态快照读回（13 键+persistent_note_ref+checksum verify 绿+TTL 30 天）+ PG strategic_archives 行存在 + Qdrant 点 search_vectors 读回 + MinIO blob_ref 解引用成功 + L1 缓存 note:{note_id} 读回（Fake LLM 固定压缩产物——期望键族独立构造）
- [ ] Subtask 5.2: 场景② 事件落行：真实 publisher + 真实 PG outbox（6-1 集成场景③装配先例——clear_singleton + resolve 覆写 + PG 双预检 skip + event_id 收集 teardown）——CheckpointReached 落行恰一行 + 行字段断言（event_type/payload checkpoint_id/phase_identifier——**断言键钦定 phase_identifier 通道**，禁 `payload->'payload'->>'plan_id'` 通道（事件 payload 子字典无 plan_id——6-2 R1-F3 实证；**plan 关联走 metadata 顶层通道 `payload->'metadata'->>'plan_id'` 不在禁止列**——OD-9，R2A-16 通道限定））+ 6-2 run 零发布互证（同装配下跑一次市场洞察 run——outbox 零 CheckpointReached 行，与 6-2 既有断言同构）
- [ ] Subtask 5.3: 场景③ 公理二负向+归档阻断：构造未持久化笔记压缩 → EntityValidationError 零回归 / 空引用构造快照 → 484 / 归档 L4 失败注入（Fake archive 服务注入失败形态——**注**：集成层禁 mock 真实服务，L4 失败注入以"bucket 不可达环境双探测 skip"或单测层承载，Task 0.8 钦定落位——预判单测层承载（6-2 R3-4 no-mock 互斥裁定同款），集成场景聚焦正常面）
- [ ] Subtask 5.4: 场景④ 恢复+篡改：多 Checkpoint（CP-1/CP-3/CP-5 三点——**逐个创建**，每点一次完整五步链（集成面无 BDD 超时约束），R2-F6 形态钦定）→ recover CP-3（视图 DTO 键族+后续清单 [CP-5]+判定 override（1<2））/ recover CP-1（后续 [CP-3,CP-5] 判定 replay（2≥2 边界））/ 篡改快照后 recover → 484 拒绝（**读回后篡改 state_data 再存**——checksum 不匹配构造路径，OD-11）/ apply_correction round-trip + 版本递增 + checksum 重算 verify 绿
- [ ] Subtask 5.5: 场景⑤ 性能采样：创建提交窗口 P95<100ms（≥20 轮——**口径钦定**：快照构造起点→Redis save 返回；**采样形态 OD-12 附则**：单次全链预热取得固定压缩产物→20 轮仅快照窗口直调真实端口（禁每轮全链）；Fake LLM 固定产物使压缩延迟出栈；docstring 声明 OD-6 口径差；task/query 文本固定；**20 轮=20 个独立 plan_id 各建 CP-1**（键唯一互不覆盖，20/20 可读回——值域 8 值上限下同 plan 不可承载 20 键，R1-F17）；模块级 pytestmark 挂 xdist_group("blm-planning-perf")）+ 持久化成功率（20/20 快照可读回）
- [ ] Subtask 5.6: 验证型变异：对 5.1 键族断言与 5.2 行断言做突变注入-还原实证（集成层断言活体证明——期望键族删键红/断言行 event_type 改名红）

**完成标准/Definition of Done:**
- [ ] 五场景全部通过（服务门控动态 skip 环境下降级为已跑场景全绿）
- [ ] 性能场景 xdist_group 串行无采样冲突（复用 blm-planning-perf 组）
- [ ] 集成覆盖率≥75% 维持（Task 7.4 覆盖率数值记录项承载——R2-F15 挂钩闭环）

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 全 AC / 六边形架构全局

> **性质说明：** 本 Task 是 **SDD 规范验证测试**（验证架构/约束是否被遵守），非 TDD 单元测试。

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_checkpoint.py`（epics 钦定名）验证器 A——domain 零依赖：扩展后 checkpoint_snapshot.py/entities/checkpoint.py/recovery_mode.py 三文件 AST/import 扫描零第三方（沿 6-1 test_blm_planning_arch.py 验证器 A 形态）
- [ ] Subtask 6.2: 验证器 B——服务落位：CheckpointService 仅存在于应用层；端口仅存在于 application/ports；StrategicArchive 编排不越层（checkpoint 服务不得直接 import infrastructure——import-linter 覆盖+源码断言双形态）
- [ ] Subtask 6.3: 验证器 C——发布点落位守护：CheckpointReached 发布调用仅存在于 checkpoint 应用服务面（正向存在性 + 负向 blm_planning 四文件零引用——与契约测试 4.2 双防线）
- [ ] Subtask 6.4: 验证器 D——公理二链路守护：checkpoint_service 源码压缩调用前必有 verify_persisted（或经 ContextCompressor 前置校验的间接保证声明——Task 0 钦定断言形态：源码级调用序断言 take_notes 先于 compress；**compress→archive 序由 Task 2 调用序断言承载——本验证器不重复守护**，R2A-15 分工声明）
- [ ] Subtask 6.5: 循环依赖检测使用 ruff/isort（不引入额外工具）+ 运行完整测试套件并生成报告（四目录全量）

**完成标准/Definition of Done:**
- [ ] 四验证器通过，任何违规即测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-8 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已建 13 场景含收尾场景骨架（红阶段已验证）；本 Task 实现收尾场景的步骤断言（不新增场景数——13 总数钉死，R2B-17） |
| 🟢 绿 | 实现全部 BDD 步骤（真实服务装配链——teardown 链含 Qdrant/MinIO 精确清理扩展），全场景转绿 |
| 🟡 变异 | 验收级断言抽检突变（键族断言/checkpoint_no 值域断言/负向断言各一） |
| 🔄 重构 | 收敛场景命名、统一断言表达（断言消息含实测值+规则锚——6-1/6-2 风格） |

- [ ] Subtask 7.1: AC-1~AC-4 场景全绿（五步创建×2/公理二守卫×2/checksum×1/发布×2）
- [ ] Subtask 7.2: AC-5~AC-8 场景全绿（L3/L4 归档×1/修正记录×1/恢复+判定×2/性能×1）
- [ ] Subtask 7.3: 收尾场景——src 完成清单（实体扩展/VO/纯函数/异常/端口/服务/用例/组合根/CLI）+ 四测试目录完成清单（本 Story 测试分类表全文件存在性）逐项断言
- [ ] Subtask 7.4: 四目录全量回归 + ruff + mypy 收尾校验 + 覆盖率数值记录（整体≥80%/domain≥90%/application≥85%/集成≥75% 四项实测值落 Story 记录）+ 三条红线 grep 自查零输出（raise ValueError/手动 HTTPException/继承内置 Exception）
- [ ] Subtask 7.5: deferred-work 台账最终更新（锚定义务七条处置终态注记）+ sprint-status.yaml L180 TODO 注释清偿更新（"实现 1.15b L3(Qdrant)/L4(MinIO) 触发"→已落地注记——随 dev-story 流转一并处理）

**完成标准/Definition of Done:**
- [ ] src 与四测试目录完成清单逐项验证确认（收尾场景断言绿）
- [ ] 开发结束验收测试通过（含 6-1/6-2 零回归）
- [ ] Story 可进入 `review`（待代码审查后 done）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（reliable 单通道——CheckpointReached 既有登记）+ 系统公理二（外部化记忆：压缩前必须持久化）
- **设计约束:** 领域层零依赖（import-linter 强制）；`@dataclass(frozen=True)` + `with_updated_state`/`dataclasses.replace` 不可变更新；checkpoint 服务经端口组合注入（R2）
- **接口治理:** 统一端口注册（PortSpec：name/version/interface/impl/module/lifetime/owner/compatibility/tags）、Registry/Resolver/ContractGate、组合根唯一装配、契约优先
- **技术栈:** Python 3.11+ / Redis 7.0+（快照 Hash）/ PostgreSQL（outbox+archive L2）/ Qdrant（L3 向量）/ MinIO（L4 WORM）/ pytest-bdd
- **关键架构条款:** §8.2 五步流程（L792-802）/ L1587"Checkpoint 持久化由 Epic 6/Story 6.3 实现" / L1594 L3 Checkpoint 压缩行 / §11.2.6 L3 压缩触发（L1246-1254——take_notes→compress→StrategicArchive 持久化链）/ L850 StrategicArchive=Checkpoint 快照前强制持久化/ L801 TTL 30 天钦定位 / L871 CheckpointReached reliable+7 年

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | 范围边界：6-3 落**创建完整面**（五步机制+完整性验证+TTL 30 天+发布点）+**恢复数据面**（load/verify/恢复视图/修正记录/482 第二触发点）+**双模式判定纯函数**（≥2→Replay 强制/<2→Override 推荐——纯计算零副作用）；**恢复执行引擎**（Replay 重放重跑后续阶段/Override pending_sync/CheckpointOverridden/CheckpointRecovered 事件）+**摘要查看/审批交互/并发审批**归 6-6。epic 6.3 文本中的"双模式恢复"按 or.md 五.6（Replay/Override 完整协议对应 prd **FR-SP-06/07/08 均为 P1**）与 epic 6.6（"修正关键参数后恢复运行"+"并发审批 5 个"依赖 6.3）读为机制背景而非 6-3 交付面；6-2 OD-1 中"Replay-Override 恢复"表述按本裁定收敛为"判定+数据面" | prd.md FR-SP-03 (P0) vs FR-SP-06/07/08/09 (P1) 优先级划分 + epics 6.6 依赖钦定 + 6-2 OD-1 先例（本表细化而非推翻） |
| **OD-2** | 序列化形态：**沿用 RedisSnapshotStore 既有 JSON 序列化**（`_snapshot_to_hash`/`_hash_to_snapshot` L50-87），不引入 msgpack。设计文档 §8.2"msgpack → Redis Hash"是传输形态示例，本质约束 = 持久化（Redis Hash）+完整性（SHA-256）+TTL（30 天）三件套，JSON 全满足；改 msgpack 需迁移 6-1/6-2/5-10 三消费面读回且引入第三方依赖（infrastructure 层虽可依赖但收益为零——纯传输编码差异）。**白名单扩列（R2A-1 P0 修订）**：`_snapshot_to_hash`/`_hash_to_snapshot` 现为显式七字段白名单（redis_snapshot_store.py:59-67/:79-87）——实体新增四字段（persistent_note_ref/checksum/snapshot_metadata/checkpoint_no）必须扩列白名单，否则 save 静默丢弃+load 缺失 → checksum 恒空 → verify 恒 False → 每次恢复误报 484；**读侧缺键回退默认值**（6-1/6-2/5-10 旧数据向后兼容——旧快照 load 后新字段为默认空值不抛）；`redis_snapshot_store.py` 因此成为本 Story **唯一 infrastructure 改动文件** | 全 src 零 msgpack 引用（Agent 调研实证）+ 既有 JSON 管线三消费面零回归原则 + R2A-1 实证（七字段白名单 :59-67/:79-87 显式列举——「零改动 infrastructure」旧声明作废） |
| **OD-3** | 快照**双轨制**：6-2 骨架键族（`blm-planning-` 前缀 latest+per-step，TTL 86400）**零改动维持**；6-3 完整形态**独立键族**（`blm-checkpoint-{plan_id}:{checkpoint_no}`，TTL 2592000=30 天）。6-2 端口契约"6-3 升级 30 天完整形态"解读为"完整形态快照 TTL 30 天"（非全体键族升级——骨架是流程状态面，30 天无意义；完整形态是审批/恢复面，30 天是合规要求）。读侧判别：前缀 + state_data 含 checkpoint_no 锚 | 设计文档 §2.1"Redis Hash TTL 30 天"语义 + 键族职责分离（流程状态面 vs 审批恢复面）+ 6-2 键契约零破坏 |
| **OD-4** | 发布点落位：CheckpointReached 发布**仅存在于新文件**（checkpoint 应用服务/用例），`blm_planning_service.py`/`run_blm_planning.py`/`get_blm_planning_status.py`/`blm_planning_prompts.py` 四文件零触碰——既有负向契约断言（test_event_channel_mapping_blm_planning.py L88-104/L126-134）与 6-2 验收 AC-3 断言**零修改通过**（BLM run 路径与创建用例路径正交——run 内零发布语义保持，"6.3 语义分立"兑现为"发布点在创建面而非流程面"） | 6-1 AC-4/6-2 AC-3 负向断言的钦定语义（"发布归 6.3"）+ 最小改动面 + 6-2 测试资产零适配 |
| **OD-5** | 触发面：MVP **显式调用**（CreateCheckpointUseCase + CLI checkpoint-create 子命令）。epic"BLM 阶段完成→触发 Checkpoint 创建"的自动触发（BlmStageCompleted 事件驱动）依赖消费基建四件（deferred L170——outbox poller/RabbitMQConsumer 均未激活），MVP 不可达；自动触发归消费基建激活后的后续 Story | 6-1 R1-8"步骤边界快照点"同款物理可达性裁定 + deferred L170 消费基建现状 + 5-3/5-11"纯生产方"先例 |
| **OD-6** | 性能口径：**创建提交窗口 P95<100ms** = 压缩产物就绪后的"快照构造+序列化+Redis 提交"窗口（持久化笔记实体抽取与 LLM 压缩延迟显式出栈——Fake LLM 固定产物口径，口径差声明落测试 docstring）；持久化成功率 100%（强制环节零吞错）；epic 的"恢复 P95<60s（Replay）/P95<15s（Override）"是完整恢复执行口径**归 6-6**（OD-1），本 Story 恢复数据面仅声明 load+verify 窗口量级预期不断言门禁 | 6-1 DC-7/6-2 OD-3 口径差声明先例 + epic 性能行与交付面口径对齐（含 LLM 调用的全链 P95<100ms 物理不可达） |
| **OD-7** | 异常码分配：483 `CheckpointCreationError`（编排强制环节失败——含**压缩终态门禁**：compress 二次路径耗尽仍不达标时编排层校验双指标 fail-loud，485 独立码**不设**——原「降级路径下不可达」预判已被 R1-F2 实测反转：compress 无最终门禁、不达标产物原样静默返回，门禁落编排层后恰是 483 触发面，独立码语义冗余）/484 `CheckpointIntegrityError`（引用缺失+校验失败双场景）；482 既有码追加第二触发点（已有 6-1 R1-5 生产触发点在位——恢复面版本倒退/状态非法经 apply_correction 乐观锁参数 expected_state_version 构造）；486-489 留 6-6 | `_code_ranges.py` L183 预留段成文 + R1-F2 实测（context_compressor.py:161-186 无最终门禁静默返回）+ blm_planning_service.py:242 既有 482 触发点实证 |
| **OD-8** | 测试文件命名（禁故事编号后缀）：unit/architecture 用 epics 钦定 `test_checkpoint.py`（**与 epics L2177 一致**）；integration `test_integration_checkpoint.py`（**对 epics L2178 钦定名 `test_checkpoint_integration.py` 的显式偏离**——依仓规前缀 tests/integration/ 全目录 test_integration_* 惯例，R2-F21 拆分声明）；acceptance `test_acceptance_checkpoint_snapshot.feature/.py`；unit 实体/纯函数按组件名（test_checkpoint_snapshot.py 扩展/Checkpoint 聚合激活测试落 entities 目录**既有** test_checkpoint.py/test_recovery_mode.py——R2-F11 统一「既有扩展」）；服务 `test_checkpoint_service.py` | epics L2177-2178 钦定名（半采半离）+ 记忆「禁止故事编号命名文件」+ 6-2 OD-7 先例 |
| **OD-9** | CheckpointReached **零字段变更**（Epic 1 既有 frozen 事件类——改字段=1-2 契约面+outbox 适配回归，收益零）；plan 关联经 DomainEvent 既有 `metadata` 构造参数承载（**已核验定谳**：base.py:74 真实字段 `metadata: dict[str, Any]`——构造可用，correlation_id 备选删除）；outbox 断言键 = `payload->'payload'->>'phase_identifier'`（stage_id 值域 market_insight_*/performance_gap——BLM 命名空间前缀可判别）或 checkpoint_id 通道，plan 关联断言键 `payload->'metadata'->>'plan_id'`（metadata 在 to_dict **顶层**非 payload 内——R1-D1 实证），**禁 payload 子字典内找 plan_id**（字段族无 plan_id——6-2 R1-F3 实证） | 事件类现状（checkpoint_events.py:16-37）+ 6-2 R1-F2/R1-F3 双通道 SQL 实证 + base.py:74/160-164 构造与序列化实证 + 最小契约变更原则 |
| **OD-10** | L3 触发条件直落：1-15b L299"压缩后内容 >500 tokens 时触发"在 Checkpoint 场景**恒真**——条件对象=压缩产物 compressed_context（~2K tokens 恒 >500；五步序 OD-12 下③归档执行时压缩产物已就绪，条件对象在位），按 StrategicArchiveService.archive_plan 现状无条件 L3 写入（端口在位即写），**禁实现恒真条件分支**——1-15b 条件语义为记忆内容分档设计，对 Checkpoint 压缩产物不适用 | 1-15b 故事文本 vs archive_plan 实现现状（L139-187 端口在位即写）+ YAGNI（恒真分支是死代码）+ §11.2.6 触发链（压缩先于归档——条件对象时序在位） |
| **OD-11** | **checksum 参与字段集钦定**：`session_id/stage_id/state_version/checkpoint_no/persistent_note_ref` + `state_data` 规范化序列化（`json.dumps(state_data, sort_keys=True, ensure_ascii=False)`）——参照设计文档 §2.1（原文 checkpoint_id/stage_id/state_version/persistent_note_ref）的钦定扩展：①保留版本分量 state_version（防版本字段篡改）；②身份字段改写（checkpoint_id→session_id 承载——Redis 键族主键；snapshot_id 每次更新轮换故不参与，身份与版本由 session_id+state_version 承载——R2A-14）；③**增量载荷覆盖**（state_data 序列化参与——完整性保护扩展至恢复载荷 compressed_context 等 13 键，业界内容寻址完整性标准；AC-3「篡改 state_data→verify 红」场景可达性的唯一构造通道）；初始化链：编排服务④步显式计算写入（不在 `__post_init__` 自动算——6-1/6-2/5-10 既有构造零扰动）、apply_correction 后服务层重算替换；`verify_integrity() -> bool` 纯判定（484 抛出在恢复编排调用方） | 设计文档 §2.1 L152 原文字段集 + AC-3 篡改场景可达性要求 + R1-1 评审发现（原字段集「对齐 §2.1」声明失实且载荷零保护——R1-19 并入本行登记）+ 业界内容寻址完整性实践 |
| **OD-12** | **五步序四源合成钦定**：①take_notes 持久化→②compress 压缩（含编排层终态门禁）→③StrategicArchive 归档（载荷=压缩产物+笔记实体摘要）→④快照落库→⑤CheckpointReached 发布。出处合成：§8.2 L792-802 主链（持久化→压缩→快照→完整性验证——无归档步无发布步，checksum 计算内嵌④创建步）+ §11.2.6 L1246-1254 触发链（take_notes→compress→StrategicArchive 持久化——**压缩先于归档**）+ L850（StrategicArchive=Checkpoint 快照前强制持久化——**归档先于快照落库**）+ L871/epics L2144-2149（发布步）。**epics 五步序（归档末位）显式不采**：末位归档会产出「快照已落库而归档失败」半成品，违反 AC-1 无半成品不变量；1-15b「压缩后内容」条件对象在②③序下时序在位（OD-10）。附则三则：a) `Checkpoint` 聚合驱动点（创建面**④内 checksum 计算前**、仅 completed=True 时 complete()/修正面 apply_correction/恢复面只读——AC-6/R2A-5 时序钦定）；b) apply_correction 乐观锁参数 expected_state_version（版本倒退→482 构造通道）；c) 性能采样形态（单次全链预热+20 轮快照窗口直调、20 独立 plan_id——AC-8）。归档侧残留语义：③失败时 L1 笔记缓存/②压缩结果缓存（均 TTL 自清）与③内已写 L2 行、L3 点为可接受残留（R2A-6 补全） | §8.2/§11.2.6/L850/L871 四源原文 + epics L2144-2149 序差异 + AC-1 无半成品不变量 + R1-4/R2-22 评审发现（三源归纳改写与条件对象错位） |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/
│   ├── entities/checkpoint_snapshot.py        ▲ 完整形态扩展（四字段+checksum/verify——Task 1）
│   ├── entities/checkpoint.py                 = 零改动复用（CorrectionRecord/RecoveryMode/CheckpointStatus/Checkpoint——Epic 1 骨架激活；Subtask 1.6 注释级 docstring 增强可选）
│   ├── services/recovery_mode.py              ★ 新建恢复判定纯函数（Task 1——返回既有 RecoveryMode）
│   └── exceptions/planning_exceptions.py      ▲ 追加 483/484（Task 1——485 不设码）
├── application/
│   ├── ports/checkpoint.py                    ★ 新建（端口+CHECKPOINT_SESSION_PREFIX+序列化契约 docstring——Task 2）
│   ├── services/checkpoint_service.py         ★ 新建（五步编排+恢复方法组——Task 2/3）
│   └── exceptions/(_code_ranges.py+__init__.py)+interfaces/api/exception_handlers.py ▲ 异常 4 项 Checklist 联动（Task 1——R2B-15 补录）
│   └── _code_ranges.py / __init__.py / interfaces/api/exception_handlers.py ▲ 异常 4 项 Checklist 联动（Task 1——结构树补录 R2B-15）
│   └── use_cases/create_checkpoint.py         ★ 新建（+恢复用例——Task 2/3）
├── infrastructure/
│   └── storage/redis/redis_snapshot_store.py  ▲ 序列化白名单扩列四字段+读侧缺键回退（Task 1——唯一 infra 改动，OD-2/R2A-1）
├── interfaces/
│   └── api/exception_handlers.py              ▲ EXCEPTION_HTTP_MAP 增量（Task 1——REST 路由面仍零改动归 7-2，R2B-14）
├── entrypoints/agent_cli.py                   ▲ checkpoint-create 子命令（Task 2——R4）
└── composition_root.py                        ▲ 新增 2~3 注册块（checkpoint_service/checkpoint_use_case——Task 2）

tests/
├── unit/
│   ├── domain/entities/test_checkpoint_snapshot.py   ▲ 扩展（Task 1）
│   ├── domain/entities/test_checkpoint.py            ▲ 激活验证扩展（Task 1——既有文件，复用面断言）
│   ├── domain/services/test_recovery_mode.py         ★ 新建（Task 1）
│   ├── infrastructure/storage/test_redis_snapshot_store.py ▲ 序列化 round-trip 用例扩展（Task 1——R2A-1）
│   ├── domain/exceptions/test_planning_exceptions.py ▲ 483/484 用例扩展（Task 1）
│   └── interfaces/api/test_exception_handlers.py     ▲ HTTP 映射用例扩展（Task 1）
│   ├── application/test_checkpoint_service.py        ★ 新建（Task 2/3）
│   ├── application/use_cases/test_checkpoint_use_case.py ★ 新建（Task 2）
│   ├── architecture/test_checkpoint.py               ★ 新建（Task 6，epics 钦定名）
│   └── interfaces/cli/test_agent_cli.py              ▲ 扩展（Task 2）
├── integration/test_integration_checkpoint.py        ★ 新建（Task 5，OD-8）
├── contracts/
│   ├── test_port_contract_checkpoint.py              ★ 新建（Task 2/4）
│   └── test_event_channel_mapping_blm_planning.py    ▲ 扩展守护（Task 4——发布接线+DF3 转义）
└── acceptance/
    ├── test_acceptance_checkpoint_snapshot.feature/.py ★ 新建（Task 0/7，R6 模板）
    └── （6-1/6-2 既有验收文件零修改——Task 4 回归验证）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 锚定义务七条处置注记（Task 0/7）
_bmad-output/implementation-artifacts/sprint-status.yaml ▲ L180 TODO 注释清偿（Task 7）
```

（▲ 修改 / ★ 新建 / = 零改动 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话+Agent 双重核验；行号基准 HEAD@fac317da，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| `CheckpointSnapshot` 实体 | `src/domain/entities/checkpoint_snapshot.py:16` | 七字段现状（snapshot_id/session_id/stage_id/state_version/state_data/timestamp/ttl_seconds）+ with_updated_state :39——**无 persistent_note_ref/checksum/serialize**，扩展基线；docstring 声明"序列化由基础设施层负责"；不在 entities/__init__.py 导出（消费方直接模块 import——扩展零导出改动） |
| **Checkpoint 聚合（Epic 1 骨架——复用激活）** | `src/domain/entities/checkpoint.py` | `CorrectionRecord` :17（**五字段**：correction_type/previous_value/new_value/applied_by/applied_at——or.md L305 修正日志要素 5/7 MVP 子集；correction_id 仅 docstring :21 提及无字段）/ `RecoveryMode` :36（str Enum，成员值 replay/override 小写——events/enums.py:48 另有同名枚举值首字母大写被 CheckpointRecovered 用，6-6 消费面转换注记）/ `CheckpointStatus` :43（pending/in_progress/completed/recovered）/ `Checkpoint` :53（**九字段**——:62-70 含 created_at/completed_at/updated_at；validate :72 不变量守卫/complete :98 与 recover :117 状态机守卫 EntityStateTransitionError 243——complete/recover 前置均为 PENDING/IN_PROGRESS/RECOVERED，COMPLETED 被拒）——**生产消费面仅单测，6-3 首个激活方** |
| 快照 JSON 序列化 | `src/infrastructure/storage/redis/redis_snapshot_store.py:50-87` | `_snapshot_to_hash`/`_hash_to_snapshot`——OD-2 沿用依据；save :102-133（latest 覆盖+pipeline hset+expire）；load :135-164（异常静默 None） |
| `SnapshotRepositoryProtocol` | `src/domain/ports/snapshot_repository_protocol.py:13-45` | save/load/delete 三方法（无 list——恢复视图的"后续清单"经 checkpoint_no 序号推导，非 port.list） |
| `PersistentNoteTaker` | `src/domain/services/persistent_note_taker.py:101` | take_notes :132-138（query/retrieved_docs:user_id:session_id → PersistentNote）；verify_persisted :293；实体抽取失败降级空列表 :238-246；血缘审计 :248-268；L1 缓存 TTL 30 天 :33 |
| `PersistentNote` VO | `src/domain/services/persistent_note_taker.py:43` | note_id/query/user_id/session_id/entities(Top-20)/extraction_result/lineage/summary(上层回填)/persisted/persisted_at/created_at |
| `ContextCompressor` | `src/domain/services/context_compressor.py:79` | compress :111-116（retrieved_docs/query/persistent_note → CompressedContext）；verify_persisted 前置校验 :132-137；压缩率目标 0.70 :38；二次压缩 :161-166；质量二次生成 :176-186；CJK 感知 token 估算 :375-425 |
| `CompressedContext` VO | `src/domain/services/context_compressor.py:52` | context/compression_ratio/quality_score/token_count/original_token_count/**persistent_note_ref** :73/query/key_entities/rerun_count——快照扩展字段的直接数据源 |
| `CompressionQualityEvaluator` | `src/domain/services/compression_quality_evaluator.py:39` | QUALITY_THRESHOLD=0.70 :32；纯计算无 LLM（熵 0.40/实体覆盖 0.40/冗余 0.20） |
| `CheckpointReached` 事件 | `src/domain/events/checkpoint_events.py:16-37` | 字段族 checkpoint_id/phase_identifier/user_feedback_request（**无 plan_id**）；aggregate_type="Checkpoint"；零字段变更（OD-9） |
| DomainEvent base | `src/domain/events/base.py:117-174` | to_dict 语义（子类字段并入 payload；metadata/correlation_id 非空才出现——L150-164）；`_registry` 自动注册 :76-90——Task 0.8 核验构造签名（metadata 通道） |
| 事件双登记（既有） | `configs/event_channels.yaml:74-77` + `src/infrastructure/messaging/channel_router.py:120-125` | CheckpointReached reliable 单通道双登记在位——本 Story 零 diff |
| 负向契约断言面 | `tests/contracts/test_event_channel_mapping_blm_planning.py:89-108,127-134` | 四文件零 CheckpointReached 引用断言——OD-4 发布点落位的守护依据（零修改通过条件） |
| `StrategicArchiveService` | `src/application/services/strategic_archive_service.py:32` | archive_plan :71-80（L2 强制→L3 降级→L4 强制→L5 降级→引用回写）；L3 collection "strategic_archive" :39；L4 bucket "archive-evidence" :40；ArchiveStorageError L2/L4 抛 :99 |
| 组合根既有注册 | `src/composition_root.py` | persistent_note_taker :2236-2249 / compression_quality_evaluator :2251-2260 / context_compressor :2262-2276 / strategic_archive_service :2209-2227 / snapshot_repository :949-963 / event_publisher :605-614 / blm_planning_service :1580-1598（PortSpec 典型形态——新注册样板） |
| planning 异常预留段 | `src/domain/exceptions/_code_ranges.py:183` | "483-489 预留 planning 域"成文；已占 480/481/482（:176-182）；482 **非处子预留**：planning_exceptions.py:16-17 模块 docstring 已记「已激活（R1-5 重跑守卫）」+ blm_planning_service.py:242 生产 raise 在位；「预留，6.3 恢复面消费时激活」措辞出处=_code_ranges.py:181-182 与 exception_handlers.py:306 两处滞后注释；planning_exceptions.py:104 实文为「6.3 Checkpoint 恢复面的状态机守卫扩展位」 |
| 482 HTTP 预留映射 | `src/interfaces/api/exception_handlers.py:304-306` | 480→404/481→500/482→409（注释"预留——6.3 恢复面消费"）——激活=零改动验证 |
| per-step 骨架契约 | `src/application/ports/blm_planning.py:23-44` | 第三级契约（6-2 交付）——本 Story 输入源；"6-3 升级 30 天完整形态"注记在此（OD-3 解读依据） |
| `BLM_PLANNING_SESSION_PREFIX` | `src/application/ports/blm_planning.py:62` | `"blm-planning-"` 单源常量——新 CHECKPOINT_SESSION_PREFIX 的相邻扩展位（同文件或新端口文件，Task 0 钦定） |
| 6-2 快照写入方法 | `src/application/services/blm_planning_service.py:660-702,704-730` | `_write_step_checkpoint`/`_write_snapshot_and_publish`——本 Story 零触碰（OD-4）；构造形态参照 |
| UnifiedStorageGateway | `src/application/services/unified_storage_gateway.py:36` | 记忆子系统面（L0/L1+MemoryChanged）——**非 Checkpoint 面**（is_checkpoint 仅 tier 决策参数 :139-143）；Checkpoint 归档走 StrategicArchiveService（architecture L850 钦定） |
| 验收装配先例 | `tests/acceptance/test_acceptance_blm_planning.py` / `test_acceptance_market_insight.py` | `_assemble_blm_chain` 形态（6-1 :718 原型；6-2 文件内实名 `_assemble_market_insight_chain` :715——形态复用注记，R2-F4）/teardown 链/Fake LLM 豁免（`_make_fake_llm` 工厂——AsyncMock(spec=LLMClientPort) 按 response_schema 身份分派返回字面量 Schema 实例）/延迟 import 纪律——本 Story 装配参照（扩展 Qdrant/MinIO 清理步 + Fake Embedding 外部 SaaS 豁免） |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-3 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L132 | 检索-压缩循环待接线（persistent_note_taker/context_compressor 等——归宿"Epic 6+ 核实"） | **核销**：本 Story 成为首 个生产消费方（checkpoint_service resolve 两端口）——核销注记落档 |
| 2 | L127 | unified_storage+L0/memory 12 端口休眠（锚"6-3 恢复面或 Epic 9"） | 预判**顺延 Epic 9**：Checkpoint 恢复读快照存储（snapshot_repository）不走记忆链路（unified_storage 是用户记忆面）——注记落档 |
| 3 | L170 | 事件消费基建四件（候选"6-3 Checkpoint 恢复消费面"） | 预判**顺延**：6-3 是 CheckpointReached 生产方非消费方（5-3 同款裁定）——注记落档（锚 6-6/Epic 8） |
| 4 | L195 | checkpointer（图工厂可选参数属 6.3） | 预判**不引入**：6-3 快照走应用层显式创建，不改 SpBlmGraph.compile()——注记落档 |
| 5 | L293 | CHECKPOINTED 第六态（触发 6.3 再评估；与 L306 AgentStatus 同族互链） | 预判**不引入**：MVP 显式触发面下第六态语义不可达（6-1 先例维持）——注记落档（L306 一并更新） |
| 6 | L340（6.2-DF3） | CheckpointReached 负向双通道 LIKE 转义无独立守护 | **清偿**：AC-4 承载（发布者在位后补转义守护测试——Task 4.2） |
| 7 | L342（6.2-DF5） | `_runs` dict 无淘汰机制（触发"6-3 快照真源切换/恢复面"） | Task 0 裁定：预判**维持 deferred**——6-3 恢复读快照存储不依赖 `_runs`（单 run 状态组装器），真源切换不发生；按实施形态终裁 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-2 市场洞察六子步骤](./6-2-market-insight-six-substeps.md)（五轮文档审查 + 五轮代码审查收敛 done）+ Story 6-1（同款双五轮）

**关键学习/Key Learnings:**
- **Epic 1 骨架资产复用（本 Story 创建期实证教训）**：立 Story 时曾将 CorrectionRecord/RecoveryMode 钦定为"新建"——四 Agent 调研+主会话亲读发现 `src/domain/entities/checkpoint.py`（Epic 1 骨架）已交付四类且生产消费面仅单测。**修正为复用激活**（禁重复造轮——checklist 红线第一条）。教训内化：**新增领域类型前必须全仓 grep 同语义类型**（domain/entities+value_objects+services 三目录），骨架期资产（Epic 1）大量处于"已定义未激活"态
- **属性形态断裂族**（6-1 两犯教训 + 本审查 R1 再证）：跨对象取属性前先核对该类型真实字段形态——本 Story 高危点：`CompressedContext.persistent_note_ref` 是 **str**（`str(note_id)` 赋值）而 PersistentNote.note_id 是 UUID——透传时类型对齐；`SearchResult` 是 dict 形态（`r.get("payload")`）非对象属性——构造检索证据时形态对齐；`CorrectionRecord` 实际 **5 字段**（correction_id 仅 docstring 提及无字段——R1-F5 定谳）且 `previous_value/new_value` 是 **str 字段**（非 Any）——修正载荷序列化时 str 化；per-step 快照键名是 **structured_output**（非 structured_content——R1-F10 定谳）；`Checkpoint` 聚合实际 **9 字段**（含时间戳三字段）——序列化取舍已钦定（OD-12 附则）
- **断言判别力**：禁恒真断言；期望值独立构造（state_data 键族/checkpoint_no 值域模块级常量）；负向断言防"过滤键空真"（AC-4 断言键钦定 phase_identifier——plan_id 通道对 CheckpointReached 恒 NULL 的 6-2 R1-F2 教训直接继承）
- **no-mock 红线互斥裁定**（6-2 R3-4）：验收/集成层无法构造的真实服务失败（如 Redis/MinIO 写失败）归单测层 AsyncMock 承载，验收 Edge Cases 不含写失败容错——本 Story 归档 L4 失败注入落位同理（Task 0.8/5.3 钦定）
- **键恒在纪律**（6-2 R1-F6）：correction_history 恒存在（初始 []）、structured_output 式"降级时键缺失"形态禁止——6-6 读侧免双兼容
- **TDD Task 边界**（6-2 R1-2）：服务切换与消费方适配必须同一 Task 红绿闭环——本 Story 实体扩展（Task 1）与 6-1/6-2 回归验证（Task 4.3）分离的依据 = 扩展带默认值向后兼容（预期零适配），若 Task 4.3 发现失配即证明"零适配"假设破产、回 Task 1 修守卫（而非适配测试）
- **BDD 三件套 + 性能口径**：模块级 event_loop + context dict + `_run_async`；teardown 链"断言失败也执行"；P95 口径差声明落 docstring（OD-6）；采样 task 文本固定 + xdist_group 复用 blm-planning-perf
- **红线三处漏网教训**（6-1 R5）：全程零抑制注释 + 提交信息禁 AI 署名 + 三条 grep 自查

**应用到本故事/Applied to This Story:**
- [ ] CorrectionRecord/RecoveryMode/CheckpointStatus/Checkpoint 复用激活（Task 1 循环 B——零新建重复类型）
- [ ] persistent_note_ref 类型对齐（str 透传）与 SearchResult dict 形态在 Task 0.8 资产复核显式登记
- [ ] AC-4 断言键 phase_identifier 钦定（禁 plan_id 通道）+ 负向断言非空锚
- [ ] 归档失败注入落位 Task 0.8 钦定（预判单测层）
- [ ] correction_history 键恒在 + 实体扩展向后兼容假设的 Task 4.3 验证闭环
- [ ] 性能口径 OD-6 + xdist_group 复用 + Fake LLM 固定产物
- [ ] 全程禁抑制注释 + 提交信息禁 AI 署名 + 三红线 grep

### 其他约束速查

- **风险集中登记**：①最大回归风险 = CheckpointSnapshot 实体扩展的三消费面（6-1/6-2/5-10——带默认值预期零适配，Task 4.3 实证）；②键族风险 = 双前缀并存（blm-planning-/blm-checkpoint-——读侧判别规则 OD-3）；③口径风险 = P95 提交窗口（OD-6）/恢复性能归 6-6（OD-1）/msgpack→JSON（OD-2）；④发布风险 = 负向断言面零修改（OD-4 落位纪律——四文件零触碰）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore；提交信息禁 AI 署名
- **覆盖率**：整体≥80% / domain≥90% / application≥85%（主改动层）/ 集成≥75%
- **验收/集成禁 mock**（真实服务优先 + `pytest.skip()` 动态跳过；Fake LLM+Fake Embedding 双豁免——外部 SaaS）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-02 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.3 L2120-2181） |
| **架构文档** | `docs/architecture/architecture.md`（§8.2 主链 L792-802/§10/§11.2.6 L1246-1254/L801 TTL 30 天/L850 StrategicArchive/L871 事件/L1587/L1594） |
| **需求权威** | `_bmad-output/planning-artifacts/prd.md`（FR-SP-03 L1870 P0；FR-SP-06~09 P1 归 6-6）+ `or.md`（L27/L44/L305/L479 五.4；L481-485 五.6） |
| **Checkpoint 设计** | `docs/architecture/sisys-checkpoint-timetravel-design.md`（§2.1 CheckpointSnapshot 完整形态/§2.2-2.3 Replay-Override 归 6-6） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.4.1 Checkpoint 编号体系 L1807-1835） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-2-market-insight-six-substeps.md`（OD-1 边界钦定/五轮审查教训） |
| **留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L127/L132/L170/L195/L293/L306/L340/L342） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml`（L180 TODO 注释） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 6.3 节 + prd FR 优先级边界）
- [x] 架构约束从 `architecture.md` + checkpoint-timetravel 设计 + core-domain §17.4.1 提取
- [x] 前一个故事学习经验整合（6-1/6-2 双五轮审查教训全量应用）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（快照双轨制/发布点落位/异常 483-489 段/锚定义务七条）
- [x] 多 Agent 并行调研（checkpoint 基建/外部化记忆与档案/接线面与异常/验收模板四视角）+ 主会话独立核验关键代码事实（CheckpointSnapshot/PersistentNoteTaker/ContextCompressor/UnifiedStorageGateway/StrategicArchiveService/entities-checkpoint 聚合/R6 模板亲读——**Epic 1 骨架资产 checkpoint.py 四类在创建期被发现并修正为复用激活**）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-3-checkpoint-snapshot-creation.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/services/recovery_mode.py` - 恢复判定纯函数（Task 1——返回既有 RecoveryMode）
- `src/application/ports/checkpoint.py` - Checkpoint 服务端口+键契约（Task 2）
- `src/application/services/checkpoint_service.py` - 五步编排+恢复方法组（Task 2/3）
- `src/application/use_cases/create_checkpoint.py` - 创建/恢复用例（Task 2/3）
- `tests/unit/domain/services/test_recovery_mode.py` - 纯函数单测（Task 1）
- `tests/unit/application/test_checkpoint_service.py` - 服务单测（Task 2/3）
- `tests/unit/application/use_cases/test_checkpoint_use_case.py` - 用例单测（Task 2）
- `tests/unit/architecture/test_checkpoint.py` - 架构四验证器（Task 6）
- `tests/integration/test_integration_checkpoint.py` - 集成五场景（Task 5）
- `tests/contracts/test_port_contract_checkpoint.py` - 端口契约（Task 2/4）
- `tests/acceptance/test_acceptance_checkpoint_snapshot.feature` - Gherkin 13 场景（Task 0）
- `tests/acceptance/test_acceptance_checkpoint_snapshot.py` - BDD 步骤实现（Task 0/7）

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/domain/entities/checkpoint_snapshot.py` - 完整形态扩展+with_updated_state 透传（Task 1）
- `src/domain/entities/checkpoint.py` - 零行为改动（Subtask 1.6 注释级 docstring 增强可选——CorrectionRecord 五字段要素映射注记）
- `src/infrastructure/storage/redis/redis_snapshot_store.py` - 序列化白名单扩列四字段+读侧缺键回退（Task 1——唯一 infra 改动，OD-2/R2A-1）
- `tests/unit/infrastructure/storage/test_redis_snapshot_store.py` - 新四字段 round-trip+旧数据回退用例扩展（Task 1——R2A-1）
- `tests/unit/domain/exceptions/test_planning_exceptions.py` - 483/484 用例扩展（Task 1——R2-F10 补录）
- `tests/unit/interfaces/api/test_exception_handlers.py` - EXCEPTION_HTTP_MAP 增量用例扩展（Task 1——R2-F10 补录）
- `tests/unit/domain/entities/test_checkpoint.py` - 激活验证扩展（Task 1）
- `src/domain/exceptions/planning_exceptions.py` - 483/484 追加（Task 1——485 不设码，OD-7）
- `src/domain/exceptions/_code_ranges.py` - `_CLASS_TO_SUBDOMAIN` 注册（Task 1）
- `src/domain/exceptions/__init__.py` - 导出（Task 1）
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 增量（Task 1）
- `src/composition_root.py` - 新增 2~3 注册块（Task 2）
- `src/entrypoints/agent_cli.py` - checkpoint-create 子命令（Task 2）
- `tests/unit/domain/entities/test_checkpoint_snapshot.py` - 扩展（Task 1）
- `tests/unit/interfaces/cli/test_agent_cli.py` - 扩展（Task 2）
- `tests/contracts/test_event_channel_mapping_blm_planning.py` - 发布接线+DF3 守护扩展（Task 4）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 七条处置注记（Task 0/7）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - L180 TODO 清偿注记（Task 7）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.3 |
| **Story Key** | 6-3-checkpoint-snapshot-creation |
| **File** | `_bmad-output/implementation-artifacts/stories/6-3-checkpoint-snapshot-creation.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力 |
| **优先级** | P0-3 |
| **覆盖 FR** | FR-SP-03（P0）——FR-SP-06/07/08（P1）判定面预铺归 6-6 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-8）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/公理二/快照双轨制/发布点落位/异常 483-489）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-1/6-2 双五轮审查教训）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | checksum 字段集不含 state_data，AC-3「篡改 state_data 字段→verify 红」场景不可构造；「对齐 §2.1」声明失实（§2.1 含 state_version） | P0 | OD-11 钦定：身份五字段（session_id/stage_id/state_version/checkpoint_no/persistent_note_ref）+ state_data 规范化序列化参与；初始化链（编排显式计算/修正后重算）；verify_integrity 纯判定+应用层抛 484 |
| R1-4/R2-22 | 五步序（归档②）与 §11.2.6 触发链（take_notes→compress→StrategicArchive）及 1-15b「压缩后内容」条件对象错位；「§8.2 五步流程」单源引用实为三源归纳 | P1 | OD-12：五步序调整为 note→compress→archive→snapshot→publish；四源合成声明（§8.2 主链+§11.2.6 触发链+L850+L871/epics）；epics 末位归档显式不采（无半成品不变量）；AC-1/AC-5/Task 2/测试分类表全传播 |
| R1-3 | AC-2 压缩终态门禁未钦定——compress 无最终门禁静默返回不达标产物（R1-F2 实测），Then「产物达标」无机制保证 | P1 | 编排层终态门禁 fail-loud（483、save/archive 零调用）；OD-7/Subtask 0.3 裁定依据更新（485 不设码理由反转）；AC-2 VC 与 Task 2 红测补用例 |
| R1-2/R1-15 | 恢复面异常切分三处打架（AC-7「损坏快照→482」vs Task 3「→484」）；load 静默 None 下 JSON 损坏与不存在键同路径 | P1 | 三分钦定：键不存在+JSON 损坏→480（复用 PlanningNotFoundError）/checksum 不匹配→484/版本倒退与状态非法→482；AC-7/Task 0.3/Task 3/Edge Cases 四处对齐 |
| R1-8 | 「版本倒退→482」红测与 apply_correction 签名矛盾（无 version 入参不可构造） | P1 | apply_correction 增 expected_state_version 乐观锁参数（端口签名+Task 3 红测+OD-12 附则） |
| R1-6 | Checkpoint 聚合守卫驱动点未钦定——恢复对象全是 completed 快照，若恢复面驱动 recover() 则全部恢复场景被 243 拒绝 | P1 | 三面钦定：创建面 complete()（status 映射 completed 键——R2A-5 勘误：④内 checksum 计算前、仅 completed=True 时调用，原「④后」已废）/修正面 apply_correction/恢复面只读不驱动 recover()；243 场景限定聚合单测+6-6 边界 |
| R1-7/R2-26 | state_data 键契约三版本（L46 含 stage_number/L51 含 token_count/L186 11 键均不一致） | P1 | 13 键定稿（+stage_number+token_count），三处同源；「八键以上」「≥10 键」范围值全部清零 |
| R1-9/R2-20 | CP-8↔synthesis 映射引「对齐 §17.4.1」失实（设计图 CP-8 挂阶段 3）；「MVP 前 8 个恢复点」自创口径 | P1 | CP-1/CP-2-7 对齐 §17.4.1 + CP-8 本 Story 钦定声明（AC-1 VC/Subtask 0.1 两处）；「BLM 前两阶段 8 恢复点」口径；六子步骤名背书引 6-2 STAGE_VALUE_DOMAIN |
| R1-5/R2-25 | CorrectionRecord「六字段」实为五字段（correction_id 仅 docstring）——全文 6 处 | P1 | 全文「六字段」→「五字段」+ 差异注记（AC-6/数据模型/Subtask 1.6/锚点表/Lessons） |
| R1-10 | AC-5 VC 引用不存在的键名 structured_content（实际 structured_output） | P1 | 改 structured_output（per-step 七键真实键名） |
| R1-11/R2-1 | 验收场景计数 off-by-one：钉死 14 vs 逐 AC 点数 13（Subtask 7.1/7.2 互证） | P1 | 全文 14→13（五处）；6-1/6-2 的 14 场景计数保留（他 Story 资产） |
| R2-2 | embedding-api 第五外部依赖无门控无豁免（strategic_archive_service 强制依赖 embedding_service）；3-10 AsyncMock 先例是反面教材 | P1 | Fake LLM+Fake Embedding 双豁免（外部 SaaS 同类）钦定——Subtask 0.5/装配先例/禁 mock 行/集成模式四处传播；禁照抄 3-10 mock 形态注记 |
| R1-12 | 两层 publisher 容错语义未分层（ArchiveCreated 不容错 vs CheckpointReached 降级） | P2 | AC-2 触发面三层声明（含 ArchiveCreated 发布失败 :286-294）+ AC-4 语义差异句 |
| R1-13/R1-14 | ②步失败部分副作用残留未承认；「持久化环节失败」无失败面可构造 | P2 | AC-1 归档侧残留语义裁定（L1 TTL 自清/L2 可接受）；强制环节枚举改写（242 透传/终态门禁/归档三层/落库） |
| R1-16/R1-17/R1-18 | lifetime 契约疑义；20 轮采样 vs 值域 8 上限冲突；evaluator 注入在位性未核验 | P2 | SINGLETON→SCOPED 先例实证注记（blm_planning_service :1580-1598）；20 独立 plan_id 钦定；Subtask 0.8⑦ evaluator 核验项 |
| R2-3/R2-4/R2-7 | AC-8 采样超时形态未钦定；L4 失败注入三层归属互斥；take_notes.session_id 来源未钦定 | P2 | 单次全链预热+20 轮快照窗口直调（OD-12 附则）；L4 注入注记单测层；session_id 快照键同源钦定 |
| R2-16/R2-17/R2-23 | 回归面漏四类消费方（redis_snapshot_store 直测最关键）；CLI 参数面未钦定（retrieved_docs 不可经 argparse）；pytestmark 含未注册 marker postgresql | P2 | 回归面补四文件；CLI 六参数+空列表构造钦定（argparse 扁平 checkpoint-create）；marker 改 database+xdist 模块级挂法 |
| R1-22/R1-23/R1-24/R1-25/R1-26/R1-27/R1-28 及 R2 P3 族 | 482 叙事过时/行号漂移（L847→L850、L89-108→L88-104）/plan 关联 SQL 路径（metadata 顶层）/P95 sorted 前提/Fake LLM 豁免面过窄/checkpoint-recover 无 owning Task/checksum 初始化链；OD-8 半真半假/OD-10 漏/矩阵 2.2 归属/File List 缺两文件/覆盖率口径/集成覆盖率挂钩/OD-9 二选一悬空/双 RecoveryMode 枚举/6-2 装配实名/CLI 二选一与实际结构不符 | P3 | 逐项校准（见 v1.1.0 各节内联修复——482 锚点表改写/行号订正/metadata 定谳+SQL 键/sorted 前文/双豁免/recover 归 6-6/显式计算写入/OD-8 拆分半采半离/OD-1~OD-12/矩阵 2.1/File List 补录/枚举分支口径/Task 7.4 挂钩/OD-9 定谳/枚举转换注记/_assemble_market_insight_chain 实名/扁平子命令钦定） |

**Round 2 修复表（回归核查——R2A 修复回归 + R2B 传播完备性；行号基准 v1.1.0 提交态 758fb4bf，v1.2.0 编辑后行号有漂移——引用以关键词 grep 定位为准）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2A-1 | RedisSnapshotStore 序列化白名单为显式七字段（:59-67/:79-87）——新增四字段 save 静默丢弃/load 缺失 → checksum 恒空 → verify 恒 False → 恢复恒误报 484；「infrastructure 零改动」声明使全部读回验收物理不可实现且 store 直测全绿掩盖（v1.0.0 遗留 P0，Round 1 未触及） | P0 | redis_snapshot_store.py 登记为唯一 infra 改动文件（白名单扩列四字段+读侧缺键回退默认值兼容旧数据）——OD-2/R3/端口表/结构树/File List 五处声明修订 + Task 1 循环 A 增序列化 round-trip 红测 + 回归面处置口径改「扩展用例」 |
| R2A-2/R2B-5 | Task 1 绿「verify 抛 484」与纯判定钦定矛盾（R1-1 传播缺口）；`[+485]` 三处残留与「485 不设码」矛盾 | P1 | Task 1 绿改纯判定返回 bool；`[+485]` 全清零 |
| R2A-3 | `with_updated_state` 现状只透传原七字段——钦定修正通道会静默丢弃全部新增四字段（守卫因 checkpoint_no 同空不触发） | P1 | Task 1 循环 A 增透传断言+绿行增透传实现（checksum 除外——服务层重算）；AC-6 同步 |
| R2A-4 | Task 1 循环 B 仍要求「recover 守卫经 6-3 编排消费面生产调用断言」——243 陷阱回潮入口（R1-6 传播缺口） | P1 | 改「complete 守卫经创建面④生产调用断言 + recover 守卫维持聚合单测不进编排」 |
| R2B-1/R2A-7 | AC-2 句内「②内事件失败」旧序步号（ArchiveCreated 在③）——句内新旧步号并存 | P1 | 改「③内事件失败」 |
| R2B-2/R2A-6 | AC-1「②已写的 L2 档案行」旧步号；残留清单漏②压缩缓存 compressed:{note_id} 与③内 L3 点 | P1 | 改「③已写」+ 残留清单补全（note:/compressed:/L2 行/L3 点四类——含 R2A-6 实证行号）；OD-12 残留句同步 |
| R2B-3 | 文档标题五步链缺归档步（v1.0.0 四步残文） | P1 | 标题补「StrategicArchive 归档」 |
| R2A-5 | complete() 时机与条件性未钦定（「④后」vs「④内」打架；无条件调用使 completed=False 全成死分支） | P2 | 钦定「④内 checksum 计算前、仅 completed=True 时调用；False 保持 IN_PROGRESS」——AC-6/OD-12 附则 a 两处 |
| R2A-8 | 集成 teardown 未覆盖③ ArchiveCreated outbox 行（每次归档落一行）与 note:/compressed: 键族——照 5.2 先例只收集⑤会残留污染真实 PG | P2 | Task 5 模式行+隔离约束表：_outbox_event_ids 收集面覆盖两类事件+Redis 清理点名三键族 |
| R2A-9/R2B-7 | AC-6 五字段标签下仅列 4 名（漏 applied_by）——属性形态断裂族复发 | P2 | 补 applied_by |
| R2B-4 | 「482 激活」五处残留与「第二触发点」钦定口径冲突 | P2 | 五处统一「482 第二触发点」 |
| R2B-8/R2A-12 | 锚点表负向断言行号仍 :89-108,127-134（AC-4/OD-4/0.8③ 已改——漏改；实测 88-104/126-134） | P2 | 锚点表订正 |
| R2B-10 | 三处引「Task 0.8 钦定落位（L4 注入）」悬空（0.8①-⑦ 无对应项） | P2 | Subtask 0.8 补第⑧项（单测层承载裁定） |
| R2B-13 | 异常测试用例（test_planning_exceptions/test_exception_handlers 扩展）声明归 Task 1 但 Task 1 红测无 owning 位（异常类未定义红=AttributeError 的红阶段缺失） | P2 | Task 1 循环 A 红测增「异常用例组」+绿行异常落地对齐（TDD 红绿同循环） |
| R2B-14/R2B-15 | 结构树 interfaces「零改动」与 exception_handlers 增量矛盾；结构树缺 5 个待修改文件 | P2 | 结构树 interfaces 区改增量行+tests 区补三文件+src 区补异常 Checklist 联动行 |
| R2B-17 | Task 7 红行「补充收尾场景」使 13 读作 14（off-by-one 家族复发） | P2 | 改「13 场景含收尾骨架已建，本 Task 实现收尾步骤断言」 |
| R2A-10/R2A-11/R2A-13/R2A-14/R2A-15/R2A-16/R2B-6/R2B-9/R2B-11/R2B-12/R2B-16/R2B-18/R2B-19 | 双位冗余无同源声明/守卫限定词缺失/终态门禁 VC 无承载/OD-11 snapshot_id 措辞/验证器 D 分工/plan_id 通道限定/AC-2 段级模糊/L132-137 行号/R1-19 悬空/修复表勘误口径/既有新建摇摆/维度表缺收尾/版本说明计数口径 | P3 | 逐项内联修复（双位分工声明/checkpoint_no 非空限定/单测层承载注记/措辞校准/分工声明/通道限定/直书 484/行号统一/R1-19 并入 R1-1 行/勘误注记本表头/既有扩展统一/收尾×1 补枚举/计数口径注记） |

**Round 3 修复表（单深度推演——主会话基于两轮证据执行：13 场景三轴/六条时间线/红测可写性/失败矩阵推演）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-T2 | apply_correction 产新版本后 save 同键覆盖——「单键单版本存活 vs 版本键链」未钦定（dev 分叉自由度：版本链会改键族设计） | P2 | AC-6 钦定「单键单版本存活」：新版本覆盖同键、修正历史经 correction_history 在最新快照内累积、不建版本键链——乐观锁与键内唯一版本比较，与 6-1 latest 键覆盖同语义 |
| R3-D | ⑤发布失败降级后 CLI exit code 未钦定；④失败后重试同 checkpoint_no 的重复归档行语义未钦定 | P3 | AC-4 钦定 exit 0 判据=快照落库成功（发布降级仅 warning）；CLI 节注记重复创建=覆盖快照+追加归档行（MVP 无唯一约束，测试用独立 plan_id 规避） |
| R3-E | created_via 值域未钦定；13 键无归档引用键（快照↔归档关联方式） | P3 | created_via 值域钦定 "cli"/"use_case" 两值；归档关联注记：经 plan_id 关联查询不引入 archive_id 键 |
| R3 证伪留痕 | ①步失败可构造性（take_notes 全降级——首个 fail-loud 在②的 242，AC-1 枚举已覆盖）；T5 篡改链（replace/with_updated_state 两构造路径均 verify 红——与构造方式无关）；AC-7② 版本倒退构造（expected_state_version=0 对 v1）；C 轴红测可写性（三 VO/异常真实构造可行） | — | 推演成立无需修改——留痕防 R5 重推 |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待实施后）
**审查模式:** （待定——沿 6-1/6-2 五轮循环先例）

#### 需决策 Decision Needed

- [ ] （待审查后填写）

#### 已修复 Patch

- [ ] （待审查后填写）

#### 已推迟 Defer

- [ ] （待审查后填写）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.0
**创建日期/Created:** 2026-11-02
**最后更新/Last Updated:** 2026-11-02
**更新说明/Description:**
- v1.3.0: 文档审查 Round 3 单深度推演（主会话执行——13 场景三轴全过/六条长状态时间线/TDD 红测可写性/五步失败矩阵）：**P2×1** 修正后「单键单版本存活 vs 版本键链」钦定（AC-6）；**P3×2** CLI exit 0 口径+重复创建语义（AC-4/CLI 节）、created_via 值域+归档关联注记（AC-1 VC）；**证伪留痕×4**（①失败不可构造性/T5 篡改双路径/版本倒退构造/红测可写性——推演成立防重推）
- v1.2.0: 文档审查 Round 2 回归核查（R2A 修复回归 + R2B 传播完备性双 Agent）：**P0×1** 序列化白名单断裂（redis_snapshot_store 七字段白名单丢弃新四字段 → 恢复恒误报 484——唯一 infra 改动钦定 OD-2/R2A-1）；**P1×6** with_updated_state 透传缺口/Task 1 绿 verify 抛与纯判定矛盾/循环 B recover 守卫回潮/两处旧步号残文/标题缺归档步/[+485] 残留；**P2×9** complete() 时机条件化/teardown 双事件收集/applied_by/482 第二触发点五处/锚点表行号/0.8⑧/异常用例 owning/结构树五文件/Task 7 off-by-one；**P3×13** 逐项校准（发现计数口径：本行按修复簇计——P0×1+P1×6+P2×9+P3×13=29 簇，含 R2A 16 项+R2B 19 项的合并去重）
- v1.1.0: 文档审查 Round 1（四视角调研 A1-A4 + 双评审 R1/R2——D1~D5 循环第 1 轮）：**P0×1** checksum 契约链（OD-11 钦定身份五字段+state_data 序列化——AC-3 篡改场景可达）；**P1×11** 五步序对齐 §11.2.6 触发链（压缩先于归档——OD-12 四源合成+epics 末位序显式不采）/压缩终态门禁（R1-F2 实测反转 485 裁定依据）/异常三分（480-JSON 损坏同路径/484/482 第二触发点）/场景计数 14→13/embedding-api 双豁免/CP-8 映射声明改钦定/版本倒退乐观锁参数/state_data 13 键三版本统一/聚合驱动点三面钦定/两层 publisher 容错分层/metadata 通道定谳；**P2/P3×20+** 六字段→五字段、structured_content→structured_output、行号校准（L850/L88-104）、marker database、回归面补四文件、CLI argparse 扁平钦定等
- v1.0.0: 创建故事文件（四 Agent 并行调研 + 主会话独立核验关键代码事实；钦定 OD-1~OD-10 偏离声明；Checkpoint 完整形态实体字段规范冻结；快照双轨制键契约；异常 483-489 段分配；锚定义务七条清单；发布点落位 OD-4；Epic 1 骨架资产 checkpoint.py 四类复用激活裁定——创建期修正"新建"初稿防重复造轮）
