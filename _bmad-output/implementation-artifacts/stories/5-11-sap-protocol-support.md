# Story 5.11: SAP 协议支持（内部 Agent 通信）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统 实现 SAP（sisys Agent Protocol）协议运行时——消息总线（`SAPBus`：五种消息类型分发 + 四级优先级出队 + 请求-响应 correlation 关联）+ JSON 序列化契约 + 公共黑板交互（隔离守卫集成 + MVCC 写入）,
**So that** 多 Agent 协作可通过统一协议进行辩论、裁决、公共黑板交互（协议基础设施就绪——协作场景编排在 Epic 9 接线）。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组收官族 Story（SAP 协议面）：5-3 已交付 SAPMessage Schema 契约（15 字段 Pydantic 模型 + 五值消息类型 + 四值优先级——FR-IF-03 Schema-only，`src/interfaces/sap/` 零消费零运行时）。本 Story 交付**协议运行时**——interface-design.md §7.4 L1315 注记钦定的「bus/传输/序列化/黑板交互归 Story 5.11」全面清偿：`SAPBus` 端口与进程内实现（send/subscribe 优先级分发 + BROADCAST 全员送达 + 请求-响应 correlation_id 关联等待）+ JSON wire format 序列化契约（NFR-INT-05 协议版本兼容的格式稳定性基础）+ 公共黑板桥（blackboard_visible=True 消息经 IsolationGuardPort 守卫后写入 PublicBlackboard MVCC——与 5-5 交付的隔离访问矩阵正确集成）。这是 FR-ST-08（V1 SAP 协议实现）的**协议层**交付：辩论（DEBATE 消息类型）/裁决（REQUEST-RESPONSE 关联链）/公共黑板（BROADCAST + MVCC）三大场景的**协议能力**在本 Story 就绪，场景编排（多 Agent 辩论流程/SYS Agent 裁决状态机/中间结论交换）归 Epic 9（FR-AC-11/12 → Story 9.5/9.6——OD-3 范围切分）。

**范围权威**：epics_v1.0.md L1904-1947（Story 5.11 定义 + AC + 性能锚 L1923 消息传递 P95<200ms / L1924 序列化 P95<50ms / L1925 并发≥50 + 覆盖率 L1928-1929 + Given/When/Then L1944-1947）、L1447（依赖 Story 5.3 + Story 1.3 事件总线——**依赖裁定见 OD-6**）、L519（FR-ST-08 → Story 5.11）、L1454；interface-design.md §7（L1178-1380：L1306 V1 交付表（v1.1.0 勘误：创建期误记 L1305——L1305 是 MVP 行）「辩论机制 + SYS 裁决 + 公共黑板」、L1311-1315 **Story 5-3 注记钦定「bus/传输/序列化/黑板交互归 Story 5.11」**、§7.2 L1290-1291 `sap_bus.send(msg)` + `wait_for_response(correlation_id)` API 形态、§7.6 安全表 V1 行「RBAC + 隔离等级——跨 Agent 数据访问需授权」）；prd.md L1823（FR-ST-08 P2/V1）、L2555（NFR-IF-03：消息传递 P95<200ms + 队列积压<100 条 + 公共黑板 MVCC 读写延迟<50ms）、L2522（NFR-INT-05 协议向后兼容 1-2 个版本）；or.md L86（V1 核心功能）；architecture.md L2169-2172（`src/interfaces/sap/` 目录规划：message.py 已落地 + **bus.py 本 Story**）、L102/L537（L1 Redis 承载公共黑板）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.11） | 后续 Story |
|------|------------------|------------|
| `SAPBus` 端口（Protocol：send/subscribe/wait_for_response/close）+ 进程内实现 `InProcessSAPBus`（`src/interfaces/sap/bus.py`——architecture.md L2172 规划钦定位置（v1.1.0 勘误：创建期误记 L2170——L2170 是 __init__.py 行）） | ✅ 新建 + 契约测试 | — |
| 五种消息类型（REQUEST/RESPONSE/NOTIFICATION/BROADCAST/DEBATE）单播分发 + BROADCAST（receiver_id="broadcast"）全员送达 | ✅ 协议能力 | — |
| 四级优先级（LOW/NORMAL/HIGH/URGENT）分发语义（per-receiver 优先级出队——高优先级插队） | ✅ 协议能力 | — |
| 请求-响应关联（REQUEST `requires_response=True` → `wait_for_response(correlation_id)` → RESPONSE 经 correlation_id resolve + 超时 460） | ✅ 协议能力 | — |
| JSON 序列化契约（SAPMessage ↔ JSON 字符串往返保真——wire format 稳定性，NFR-INT-05 兼容基础） | ✅ | — |
| 公共黑板桥（blackboard_visible=True → IsolationGuardPort.ensure_agent_access(BLACKBOARD, WRITE) 守卫 → PublicBlackboard.post MVCC 写入；L4 写拒绝 449 透传；写失败 462） | ✅ 与 5-5 隔离矩阵/既有黑板端口集成 | — |
| `sap_exceptions.py`（SAPTimeoutError 460 / SAPBusStateError 461 / SAPBlackboardWriteError 462——sap 子域 460-469 新段） | ✅ 注册四件套 | — |
| 组合根 `# === Story 5.11 ===` 区段（sap_bus 端口 SINGLETON 注册）+ 契约测试 + 架构验证器 | ✅ | — |
| 性能三锚（传递 P95<200ms / 序列化 P95<50ms / 并发≥50） | ✅ 集成委托计时 | — |
| SAPMessage Schema（15 字段模型 + 枚举） | ❌ 零改动（5-3 已交付——直接消费） | — |
| **多 Agent 辩论场景编排**（辩论流程状态机/轮次控制/置信度交换决策） | ❌ 不做（FR-AC-11 → Story 9.5；OD-3——协议能力 DEBATE 消息类型本 Story 交付，场景编排归 Epic 9） | Story 9.5 |
| **SYS Agent 裁决流程**（五维评分/置信度判定/三套方案生成） | ❌ 不做（FR-AC-12 → Story 9.6/9.7；OD-3——REQUEST-RESPONSE 关联链是裁决的协议基座，裁决状态机归 Epic 9） | Story 9.6/9.7 |
| 公共黑板「中间结论交换」场景（联合分析组结论读写流程） | ❌ 不做（Story 9.5 场景面；黑板 MVCC 存储已存在） | Story 9.5 |
| EIP 协作态动态切换经 SAP 消息触发 | ❌ 不做（V2+；isolation_level 字段承载已由 5-3 落地） | Story 9.3 / V2 |
| middleware.py（消息签名/审计中间件） | ❌ 不做（`src/interfaces/sap/__init__.py` docstring 钦定归 V2；§7.6 消息签名 MVP 行由 Schema 契约承载） | V2 |
| SAP 通信审计日志写 IsolationSwitchLog（§7.6 MVP 行 L1377） | ❌ 不做（语义错位：IsolationSwitchLog 是隔离等级切换日志，与 SAP 通信审计不同域——规划期设想未随 5.x 隔离体系落地演进；通信审计面归 Epic 9 编排或 7-2 立项评审） | Epic 9 / Story 7-2 |
| mTLS 加密传输 | ❌ 不做（V2+——or.md L86） | V2+ |
| 跨进程/分布式传输（Redis/RabbitMQ 通道形态、水平扩展） | ❌ 不做（OD-4——V2+ 水平扩展面；MVP/V1 单进程前提，wire format 已定） | V2+ |
| **事件消费基建**（Outbox poller 宿主 / RabbitMQConsumer 组合根接线 / 可靠通道 handler 注册机制 / CLI 发布失败退码化） | ❌ 不做（**OD-6 留项处置**：SAP 协议与领域事件消费基建正交——锚位顺延至真实事件消费方 Story） | Epic 6 首个事件消费 Story 立项时定夺 |
| REST API `/agents/arbitrate` 等端点 / CLI 命令 | ❌ 不做（嵌入式协议基础设施；7-2 REST 面立项时评估） | Story 7-2 |
| SAP 总线生产消费方接线（Agent 编排引擎/use case 消费 sap_bus） | ❌ 不做（无生产消费方——多 Agent 编排归 Epic 9；本 Story 经组合根 resolve 可达 + 测试消费） | Epic 9 首个多 Agent 编排 Story |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 测试文件命名从仓内惯例不从 epics 占位名：`tests/unit/interfaces/sap/test_bus.py`（总线行为单测——`tests/unit/interfaces/sap/` 目录 5-3 已建）+ `tests/unit/architecture/test_arch_sap_protocol.py`（AST 架构验证器——per-story 惯例；epics 占位 `tests/unit/architecture/test_sap_protocol.py`）+ `tests/integration/test_integration_sap_protocol.py`（epics 占位 `test_sap_integration.py`）+ `tests/acceptance/test_acceptance_sap_protocol.feature/.py` | epics_v1.0.md L1937-1938（测试文件占位名） | 5-8 OD-1 / 5-9 OD-1 / 5-10 OD-1 同款注记：epics 占位名是规划文本，仓内惯例（unit 按层归目录 / test_arch_* 前缀 / test_integration_* 前缀 / test_acceptance_* 功能性命名）是活代码事实源；规划占位名与仓内惯例的正常偏差，随本 OD 知悉不进台账 |
| OD-2 | 覆盖率口径：epics L1928「应用层覆盖率≥85%」改按**接口层 ≥85%** 执行（本 Story 交付主面 `src/interfaces/sap/bus.py` 在接口层——5-3 架构裁定 SAP 是接口层横向协议）+ 集成测试覆盖率≥75%（L1929 原文）+ 整体≥80%（门禁） | epics_v1.0.md L1928（应用层覆盖率≥85%） | 规划文本写就时（Epic 4 期）SAP bus 预期落 application；5-3 落地已钉死 SAP 全族归 interfaces/sap/（架构守护测试 test_arch_agent_workflow.py L145-172 钉死 domain 禁反向引用）——覆盖率门按实际交付层执行，语义等价（85% 门不变，层归属修正）；domain 触碰面仅 sap_exceptions.py 三异常（≥90% 门由异常测试族全覆盖承载） |
| OD-3 | **V1 交付范围裁定**：epics/or.md「V1 = 辩论机制 + SYS 裁决 + 公共黑板」中的**场景编排面**（辩论流程编排/SYS 裁决状态机/五维评分/三套方案）不在本 Story——本 Story 交付其**协议能力层**（DEBATE 消息类型分发 / REQUEST-RESPONSE correlation 关联链 / blackboard_visible 黑板交互）；场景编排归 Story 9.5（FR-AC-11 公共黑板交换中间结论）/ 9.6（FR-AC-12 SYS Agent 裁决）/ 9.7（三套方案） | or.md L86（V1 实现核心功能：多 Agent 辩论/SYS Agent 裁决/公共黑板 MVCC）+ interface-design.md L1306（V1 交付物——v1.1.0 勘误「辩论机制 + SYS 裁决 + 公共黑板」）+ epics L526-527（FR-AC-11/12 → Story 9.5/9.6） | ①FR-AC-11/12 的 Story 映射表（epics L526-527）已钦定场景编排在 Epic 9——5.11 若实现场景面则与 9.5/9.6 双 Story 重复交付；②MVP 单 Agent（SUPPORTED_ROLES 仅 CEO——`src/application/use_cases/agent_instantiation.py` L48，v1.1.0 勘误：创建期路径缺 use_cases/ 段）无真实多 Agent 辩论/裁决消费方，场景编排无验证载体；③协议能力层（消息类型/优先级/关联/黑板可见性）自洽可测（真实服务验证协议行为），是场景编排的必要前置；④Epic 9 立项时在本 Story 交付的协议运行时之上叠加编排（零协议层返工——wire format 与端口契约稳定） |
| OD-4 | 传输形态 = **进程内 asyncio 总线**（InProcessSAPBus——同进程多 Agent 间消息传递）；跨进程通道（Redis pub/sub / RabbitMQ）与水平扩展是 V2+ 面；JSON 序列化契约（wire format）仍在本 Story 交付（跨进程演进时格式零变更——NFR-INT-05 版本兼容基础） | prd.md L2555（NFR-IF-03「消息队列积压<100 条」暗示队列语义）+ or.md L262（V2+ 水平扩展） | ①MVP 单进程前提已显式声明（5-10 DC-7 同款——uvicorn 多 worker 分叉是 V1 容量面）；②SAPMessage 非领域事件、不进事件总线通道体系（5-3 `src/interfaces/sap/__init__.py` docstring 钉死 + 守护测试）——走 Redis pub/sub 会引入 fire-and-forget 语义（无请求-响应关联，DC-2[5-6] 同族通道语义问题）、走 RabbitMQ 会引入可靠投递基建纠缠（Outbox/poller/consumer 全链——与 OD-6 留项纠缠）；③请求-响应关联（Future + correlation_id 匹配）在进程内最自然（零网络往返、超时精确）；④优先级插队与积压队列语义在进程内 asyncio 优先级队列完整承载；⑤零新运行时依赖（5.7 OD-1 家族原则延续——asyncio 标准库）；⑥wire format JSON 契约的交付保证协议格式稳定（V2+ 换传输实现时消息格式零漂移） |
| OD-5 | `sender_id`/`receiver_id` 承载 **str(agent_id)（UUID 字符串形态）**；bus.send 校验 UUID 可解析性（461 拒绝非 UUID 标识——"broadcast" 约定值豁免） | interface-design.md §7.2 L1282-1284 示意代码（`sender_id="ceo"`——role 名形态） | ①示意代码是 2026 规划期文档示意，Agent 体系落地后全仓标识惯例已收敛：Agent 实体主键 `agent_id: uuid.UUID`、跨层传递一律 `str(agent_id)`（LangGraphEngine DC-5 参数守卫 / CLI / DriftDetected.agent_id: str / EvaluationCheckpoint.agent_id: str / PublicBlackboard.post(agent_id: str) 全一致）——**零「role 字符串作 Agent 标识」先例**；②黑板桥守卫需要 `uuid.UUID(sender_id)`（IsolationGuardPort.ensure_agent_access 签名是 UUID 形态——isolation_guard.py L62-63，v1.1.0 勘误：创建期误记 L63-64）——UUID 校验前置使守卫集成零二次解析失败面；③协议参与方可追溯（审计语义——§7.6 审计日志 MVP 行）；④role 名寻址在 Agent 体系是配置/档案目录键（YamlAgentConfigLoader.load(role)），非运行时实例标识 |
| OD-6 | **留项处置**（deferred-work 钦定 5-11 定夺两项）：R1-DF2（outbox poller 宿主 + CLI 发布失败退码化）与 OD-4·P3（事件订阅消费基建）**均裁定不在本 Story 范围、锚位顺延**——SAP 协议与领域事件消费基建正交：①SAPMessage 非 DomainEvent（5-3 架构钉死不进 event_channels.yaml/ChannelRouter——守护测试在位）；②SAP 总线进程内 asyncio（OD-4），不经 RabbitMQ/Outbox/Redis pub/sub 任何事件通道组件；③SAP 协议运作零事件订阅面（send/subscribe 是 Agent 间消息原语非领域事件消费）；④deferred-work「SAP 协议需要消费 AgentDecided 等」表述（L242）与 5-3 落地架构冲突——以已交付架构事实为准（5-6 OD-4 论证先例：epics/规划与落地冲突时以范围权威+落地事实裁定） | deferred-work.md L169（R1-DF2——「锚位再顺延至 5.11…消费基建归首个事件消费 Story（5-11 sap-protocol-support，P1-11）立项时一并定夺」）+ L242（OD-4·P3——「归宿：5-11 立项时一并定夺…承接方：Story 5-11…依赖 1.3 事件总线的首个消费 Story」） | ①epics L1904-1947 范围权威：5.11 AC 全文（Schema/类型/优先级/隔离等级测试 + 性能 + 覆盖率 + Given/When/Then 消息发送与黑板 MVCC）零事件消费组件；②消费基建缺失四件（调研实证：poller 宿主仅 api_app lifespan 未部署/RabbitMQConsumer 组合根零注册/可靠通道 handler 注册键语义未对齐/realtime start 零调用疑点）是独立基建面，塞入 5-11 则双面范围爆炸违反单 Story 单价值组纪律；③真实首个事件消费方：Epic 6 BLM 流程（6-1 消费流程类事件）或审计消费 Story——届时 poller 宿主/Consumer 接线/handler 注册机制专项定夺；④Task 0.7 在 deferred-work.md 两条目追加顺延注记（锚位 5-11 → Epic 6 首个事件消费 Story，理由如上；R1-DF2 与 OD-4·P3 同批顺延——两登记本就互指同锚） |
| OD-7 | 黑板桥 **fail-loud**：`PublicBlackboard.post` 返回 `version == 0`（RedisPublicBlackboard 既有吞异常行为——ConnectionError/TimeoutError 捕获后 return 0，public_blackboard.py L96-102）时抛 `SAPBlackboardWriteError`（462）；守卫拒绝（449/448/443/447）原样透传。**正交开关钦定（v1.1.0）**：黑板写入是逐消息 opt-in（`blackboard_visible`，默认 False——5-3 Schema 测试族锁定不可改默认）；BROADCAST 类型语义 = 全员送达，**不隐含强制黑板写**（`BROADCAST + blackboard_visible=False` 是合法组合——全员送达 + 零黑板写，AC-3 零写入边界用例覆盖；发送方显式置 True 才走黑板承诺面） | 无规划原文（新增语义裁定——interface-design.md §7.6 V1 行「跨 Agent 数据访问需授权」只定守卫面，未定写失败语义） | ①blackboard_visible=True 是发送方的协议承诺面（interface-design.md L1226「BROADCAST 广播到公共黑板」的准确读法是「广播消息**可以**投递公共黑板」——经 opt-in 开关承载，创建期「BROADCAST 核心语义=黑板写」表述过强，v1.1.0 修正），写失败静默降级 = 静默丢协作数据（Epic 9 联合分析组场景下不可恢复）；②与 5-10「可观测附加面降级」哲学的分界：评估历史是**附加面**（失败丢的是可观测数据，主链无感），显式置位的黑板可见性是消息的**主语义面**（失败丢的是协作本体）；③调用方拿到明确失败可决定重试/降级/裁决升级——总线不代为吞掉；④462 携带 cause 链与 conversation_id context；⑤opt-in 钦定保持 5-3 Schema 交付面零改动（默认 False 是测试族锁定契约，隐含强制 True 会破坏既有测试族） |
| OD-8 | 消息组合约定校验在 **bus 层**（send 时）：①`message_type=BROADCAST` ⇔ `receiver_id="broadcast"`（双向锁定——违者 461）；②非 BROADCAST 消息 `receiver_id="broadcast"` 同样 461；③`message_type=BROADCAST × blackboard_visible` 组合**不校验**（正交开关——OD-7 钦定放行，False 合法） | interface-design.md §7.4 L1339（注释行「receiver_id…广播时为"broadcast"」——v1.1.0 勘误：创建期误记 L1349）+ message.py L45（约定 docstring——Schema 层未校验组合） | ①5-3 交付形态：SAPMessage 是纯字段模型（Pydantic 单字段约束 min_length/枚举），无跨字段校验器——组合约定是协议行为非 Schema 契约（改 Schema 加校验器会破坏 5-3 交付面与既有测试族）；②bus.send 是协议入口（所有消息必经），组合校验在此单点收敛；③fail-loud（461）防 BROADCAST 语义误用（单播地址发广播消息→只有一人收到，静默违背全员送达语义）；④黑板可见性与消息类型正交（OD-7⑤）——类型×可见性交叉校验会造出「广播必须写黑板」的隐含强制，破坏 opt-in 语义 |
| OD-9 | **correlation 锚约定（v1.1.0 新增）**：RESPONSE 的 `correlation_id` = 所应答 REQUEST 的 `message_id`；`wait_for_response(correlation_id)` 的锚即该 REQUEST.message_id（JMS `JMSCorrelationID = 请求 JMSMessageID` 同款惯例）；**不支持**「REQUEST 预设自 correlation_id + wait(该值)」形态 | interface-design.md §7.2 L1283-1291 示意代码（REQUEST 构造时预设 `correlation_id=uuid4()` 且 `wait_for_response(msg.correlation_id)`——与本约定分歧；示意代码是 2026 规划期文档非规范，OD-5 同款裁定延伸） | ①message_id 是必填无默认字段（message.py L69——send 方必然持有），correlation_id 是 `UUID \| None = None` 可选字段（L76）——以必填键作锚使「无 correlation 请求」（NOTIFICATION 等无法关联的形态）天然不进等待路径；②以 REQUEST 自设 correlation_id 作锚要求「send 后本地保存 msg 引用」才可 wait——message_id 锚在协议追踪链（epics Gherkin 点名 message_id/conversation_id/correlation_id 完整追踪链）上语义更正；③**Epic 9 消费方知悉锚**：按 interface-design §7.2 示意编码（wait(预设 correlation_id)）会落入「无挂起条目」路径等满超时伪 460（响应明明已回对）——本 OD 钦定形态为唯一支持形态，7-2/Epic 9 文档评审时同步该分歧 |

> 优先级锚说明（非偏离）：epics L1447 执行优先级 P1-11（执行序）；prd L1823 FR-ST-08 定级 P2（功能等级——V1 承诺）。双锚不矛盾（5.10 同款注记：epics L532/L1446 先例）。

---

## 🔗 前置依赖（全部 ✅ 无阻塞——5.3/1.3 为 done 交付 Story；黑板/隔离基建为既有资产；「就绪」= 既有资产本 Story 直接消费无需先行动作）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.3 | `SAPMessage` 15 字段模型 + `MessageType` 五值 + `MessagePriority` 四值（src/interfaces/sap/{message,types}.py——**本 Story 零改动直接消费**）+ `src/interfaces/sap/__init__.py` 职责边界声明（SAP 非领域事件不进事件通道体系）+ conversation_id→黑板 str 键换算注记（message.py L48-49 归 5.11 处理——本 Story 黑板桥兑现）+ 验收先例（test_acceptance_agent_workflow.py AC-4.1/4.2/4.3 Schema 场景——5.11 不重复 Schema 面） | 消息载体 + 枚举 SSOT + 架构边界 | ✅ done |
| Story 1.3 | 事件总线体系（DualChannelEventBus/ChannelRouter/event_channels.yaml——**本 Story 零触碰**：SAP 不进事件通道体系[OD-6 正交论证]；依赖关系裁定=架构边界确认而非消费） | 依赖声明的边界确认（epics L1447「依赖 Story 1.3」以「SAP 不依赖事件总线」的论证形式兑现——OD-6） | ✅ done |
| 公共黑板基建（1.x 期） | `PublicBlackboard` 端口（src/application/ports/public_blackboard.py——post[返回版本号]/get/get_by_agent/get_latest，R1 基础端口形态）+ `RedisPublicBlackboard` 实现（infrastructure/storage/redis/public_blackboard.py——Sorted Set + incr 版本号 **MVCC**、键 `sisys:blackboard:{conversation_id}`、**post 吞 ConnectionError/TimeoutError 返 0**[L96-102——OD-7 fail-loud 检测点]）+ `BlackboardEntry`（blackboard_entry.py）+ 组合根注册（composition_root.py L818-825——SCOPED，字符串 impl 延迟加载）+ 完整测试族（unit/contracts/integration/acceptance 四层既有） | 黑板写入端口与 MVCC 存储——**直接复用禁新建同义端口**（R2 组合注入） | ✅ 就绪 |
| 隔离守卫（5-4/5-5） | `IsolationGuardPort.ensure_agent_access(actor_agent_id: UUID, target_agent_id: UUID, resource: IsolationResource, operation: AccessOperation)`（src/application/ports/isolation_guard.py L60-87——448/449（v1.1.0 勘误：尾行偏 1）/443/447 分码拒绝，放行静默 None）+ `IsolationResource.BLACKBOARD` + `AccessOperation.READ/WRITE`（domain/value_objects/isolation_access.py）+ `ISOLATION_POLICIES` 策略表（L4=READ_ONLY 黑板写拒绝 449 / L2=FREE_WRITE 放行——5-5 AC-3.3 验收钉死）+ 组合根 `isolation_guard_service` 注册（SINGLETON，L2908） | 黑板桥写入前守卫（§7.6 V1「RBAC + 隔离等级」承载） | ✅ 就绪 |
| 隔离枚举 SSOT | `IsolationLevel`（domain/events/enums.py L39-45——L4/L3/L2/L1；SAPMessage 已 import 复用）+ `MVP_ALLOWED_LEVELS`（isolation_policy.py——排除 L1） | isolation_level 字段语义（零新定义） | ✅ 就绪 |
| 异常体系 | sap 子域 460-469 **空闲段**（_code_ranges.py CODE_RANGES——agent 440-449 已满 + evaluation 450-459 预留 453-459；「前段满/语义独立→开独立段」第六段先例：data_source 410/debate 420/tool_version 430/agent 440/evaluation 450 同款）+ `DomainError` 基类体系（SystemException/BusinessException 构造惯例）+ `EXCEPTION_HTTP_MAP` + CI 校验（test_code_ranges.py + test_error_code_uniqueness.py 自动 8 项） | SAPTimeoutError 460 / SAPBusStateError 461 / SAPBlackboardWriteError 462 落位 | ✅ 就绪 |
| 组合根注册族 | Epic 5 端口族注册形态（agent_* 命名族 + SINGLETON 政策 + lambda/__import__ 延迟加载——L2681-3090 区段形态模板（v1.1.0 勘误：右端截尾）） | sap_bus 注册写法参照 | ✅ 就绪 |
| 测试基建 | tests/acceptance/conftest.py（文件名服务 marker 自动挂载——sap_protocol 文件名不含服务关键词，仅自动挂 acceptance marker）+ **模块级 event_loop fixture 与 `_run_async` 系逐文件自定义**（v1.1.0 勘误：创建期表述将二者归于 conftest——实为各验收文件自带，本 Story 验收文件照 5-9/5-10 同款自带三件套）+ 集成委托计时三件（`_PERF_CACHE` + xdist_group 同组串行 + 常量单源集成定义/验收 import——5-10 先例）+ AST 验证器 helper（test_arch_evaluation.py `_scan_file_top_imports`/`_scan_instantiation_sites`）+ TestTenant（tests/isolation.py）+ 手写零 IO 替身先例（`_RecordingEventPublisher` 全仓 15+ 文件同款） | 测试骨架 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置——deferred-work 钦定 5-11 为定夺方，Task 0 逐条裁定 + deferred-work.md 落注记）：**

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|---------------|
| 1 | **R1-DF2**：outbox 无 poller 宿主（api_app lifespan 未部署 + CLI 路径零宿主——AgentInstantiated/AgentProfileLoaded reliable 事件持续 pending 累积）+ CLI 发布失败无程序化可观测信号（stderr + exit 0）；锚位经 5-3→5-7 两次顺延至 5-11 | deferred-work.md L169 | **Task 0 裁定：本 Story 不处置、锚位顺延至 Epic 6 首个事件消费 Story**（OD-6④——SAP 总线进程内 asyncio 零事件通道组件，poller 宿主与 SAP 协议正交；观测面增强同批顺延）；Task 0.7 在 L169 条目追加 5-11 处置注记 |
| 2 | **OD-4·P3**（5-7 区段编号，非本 Story OD 命名空间）：事件订阅消费基建（EventHandler 形态消费 AgentDecided/AgentInstantiated/AgentProfileLoaded）——RabbitMQ 消费侧/Outbox 轮询宿主专项；「归宿：5-11 立项时一并定夺（R1-DF2 锚位同步顺延）」 | deferred-work.md L242 | **Task 0 裁定：消费基建不属 5-11、锚位顺延**（OD-6——SAPMessage 非 DomainEvent、SAP 总线不经 RabbitMQ/Outbox/Redis pub/sub、SAP 协议运作零事件订阅面；调研实证消费基建缺失四件：poller 宿主未部署/RabbitMQConsumer 组合根零注册/register_handler 队列名 vs _on_message 事件类型键语义未对齐/realtime start 零调用疑点——四件全归消费基建专项）；Task 0.7 在 L242 条目追加 5-11 处置注记（含缺失四件调研结论锚，供未来专项立项输入） |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| SAP 消息模型 | `src/interfaces/sap/message.py`（SAPMessage——15 字段 Pydantic v2）+ `src/interfaces/sap/types.py`（MessageType/MessagePriority） | **直接消费零改动**——bus 的消息载体；15 字段/枚举/默认值/必填约束由 5-3 测试族锁定（tests/unit/interfaces/sap/test_message.py——本 Story 不重复 Schema 断言面） |
| SAP 包边界声明 | `src/interfaces/sap/__init__.py`（docstring：SAP 非领域事件不进 event_channels.yaml/ChannelRouter + bus.py 归 5.11 + middleware.py 归 V2） | **追加导出**——SAPBus/InProcessSAPBus 加入 `__all__` 与 import 块（SAPMessage/MessageType/MessagePriority 三导出保留）；docstring 中「bus 归 5.11」注记随交付更新 |
| 公共黑板端口 | `src/application/ports/public_blackboard.py`（PublicBlackboard Protocol） | **直接消费**——黑板桥构造注入（R2：接口层组件组合注入应用层基础端口——interfaces→application 依赖方向合法 ✓）；禁新建 blackboard_store/sap_blackboard 等同义端口 |
| Redis 黑板实现 | `src/infrastructure/storage/redis/public_blackboard.py`（RedisPublicBlackboard——Sorted Set + incr MVCC 版本） | **经组合根 resolve 注入**——黑板桥不直连 Redis（端口边界）；**post 返 0 = 写失败检测点**（OD-7——L96-102 吞异常行为是既定接口语义）；MVCC 版本号（返回值 int）是 AC-3 断言锚 |
| 隔离守卫端口 | `src/application/ports/isolation_guard.py`（IsolationGuardPort.ensure_agent_access）+ `src/domain/value_objects/isolation_access.py`（IsolationResource.BLACKBOARD / AccessOperation） | **直接消费**——黑板桥写入前守卫调用（actor=uuid(sender_id)、target=uuid(receiver_id) 或 sender 自身[广播形态]、resource=BLACKBOARD、operation=WRITE）；448/449/443/447 拒绝异常**原样透传**（不包装——5-5 分码语义完整保留）；经组合根 resolve("isolation_guard_service") 注入 |
| 隔离等级枚举 | `src/domain/events/enums.py`（IsolationLevel——SAPMessage.isolation_level 已复用） | **直接消费零新定义**——bus 层不重复定义等级枚举（SSOT） |
| 组合根注册形态 | `src/composition_root.py` Epic 5 区段（L2681-3090——lambda resolver（v1.1.0 勘误：右端截尾） + `__import__` 延迟加载 + Lifetime.SINGLETON + owner/tags 惯例；public_blackboard 注册 L818-825 字符串 impl 先例） | **参考照抄**——`# === Story 5.11 ===` 区段 sap_bus 注册（lambda 注入 public_blackboard + isolation_guard_service） |
| 端口契约先例 | `tests/contracts/test_port_contract_agent_checkpoint.py`（11 维度 + _DummyResolver 分发替身 + REQUIRED_METHODS 常量） | **参考照抄**——test_port_contract_sap_bus.py 同款（REQUIRED_METHODS=["send","subscribe","wait_for_response","close"]；Dummy 分发 public_blackboard/isolation_guard_service 两依赖） |
| AST 架构验证器形态 | `tests/unit/architecture/test_arch_checkpoint_evaluation.py`（REPO_ROOT + `_scan_file_top_imports`/`_scan_instantiation_sites` helper + 参数化验证器 + 词边界正则）+ `test_arch_agent_workflow.py` L145-172（TestValidatorCSapPlacement——**domain 禁反向引用 interfaces.sap 既有守护，本 Story 不动它**） | **参考照抄**——test_arch_sap_protocol.py 三验证器（A：interfaces/sap/bus.py 第三方白名单 {pydantic}+标准库 / B：组合根外零实例化 + domain 触碰面收窄 + 依赖方向 / C：bus.py 静态锚 + Protocol 方法面基线 + 零抑制注释） |
| 集成委托计时模式 | `tests/integration/test_integration_checkpoint_evaluation.py`（_PERF_CACHE + 常量单源 + xdist_group 同组 + warmup 1 + 20 采样 quantiles(latencies, n=20)[18] exclusive） | **参考照抄**——性能三锚版本：单 key `sap_perf` 载三指标 summary dict（一次采样产三锚：传递/序列化/并发）；常量 `SAP_DELIVERY_P95_LIMIT_SECONDS = 0.2` + `SAP_SERIALIZATION_P95_LIMIT_SECONDS = 0.05` + `SAP_CONCURRENCY_FLOOR = 50` |
| 手写零 IO 替身族 | `_RecordingEventPublisher`（全仓 15+ 文件同款——duck-typing 实现端口契约捕获调用） | **参考照抄**——验收替身：`_RecordingIsolationGuard`（duck-typing 实现 IsolationGuardPort——放行/拒绝可控）+ `_StubBlackboard`（duck-typing 实现 PublicBlackboard 捕获 post 调用——集成/验收真实 Redis 场景之外的单元替身） |
| 并发 gather 先例 | `tests/acceptance/test_acceptance_red_blue_debate.py` L1092-1103（50 并发 gather + 逐条断言零丢失） | **参考照抄**——AC-5.2 并发 50 消息场景 |
| xdist 组清单（15 组实名） | agent-workflow-perf / agent-isolation-perf / agent-triple-isolation-perf / isolation-switch-log-perf / phoenix-tracer-perf / agent-evaluation-perf / drift-detection-perf / agent-instantiation / agent-profile-loading / data-source-cache / sandbox-daemon / tool-executions-pg / tool-versions-pg / validation-feedback-pg / checkpoint-evaluation-perf | **新组 `sap-protocol-perf` 与 15 组互异**（全仓 grep 断言——5-9/5-10 同款）；**存量同步义务（创建期已实证消解）**：5-9/5-10 验收组断言是子集断言形态（`expected_existing <= existing_groups`），新增第 16 组零破坏、零同步动作 |
| 真实服务装配先例 | `tests/acceptance/test_acceptance_agent_triple_isolation.py` L686-718（真实隔离服务链：实例化 Agent → guard.ensure_agent_access(…, IsolationResource.BLACKBOARD, AccessOperation.WRITE) → 449 断言） | **参考照抄**——AC-3.2 场景（L4 真实链拒绝）：真实 Redis + 真实实例化 CEO Agent + 真实 IsolationManagementService/guard——5-5 AC-3.3 形态延续 |

**明确不存在、本 Story 需新建**（调研实证：`SAPBus|sap_bus|InProcessSAPBus` 在 `src/` 零命中[仅 `src/interfaces/sap/__init__.py` docstring 规划性注记「bus.py 归 5.11」]；`sap_exceptions|SAPTimeoutError|SAPBusStateError|SAPBlackboardWriteError|EXCEPTION_46[012]` 零命中；CODE_RANGES 无 "sap" 子域行；460-469 空闲；组合根 grep -i sap 仅 2 处假阳性 newsapi 注释；`wait_for_response` 全仓零命中[仅 interface-design.md 文档示意]）：

1. `SAPBus` Protocol + `InProcessSAPBus` 进程内实现（`src/interfaces/sap/bus.py`——architecture.md L2172 规划钦定位置（v1.1.0 勘误：创建期误记 L2170——L2170 是 __init__.py 行）；含黑板桥与守卫集成、优先级队列、correlation Future 索引）
2. `sap_exceptions.py`（EXCEPTION_460/461/462——`src/domain/exceptions/sap_exceptions.py` 新文件 + 注册四件套）
3. 组合根 `# === Story 5.11 ===` 区段（sap_bus 注册 + lambda 注入两依赖）
4. `src/interfaces/sap/__init__.py` 追加导出（SAPBus/InProcessSAPBus）
5. 测试资产（新建七件[.feature/.py 分计]）：`tests/unit/interfaces/sap/test_bus.py` / `tests/contracts/test_port_contract_sap_bus.py` / `tests/integration/test_integration_sap_protocol.py` / `tests/unit/architecture/test_arch_sap_protocol.py` / `tests/acceptance/test_acceptance_sap_protocol.feature` + `test_acceptance_sap_protocol.py`；追加：`tests/unit/domain/exceptions/test_sap_exceptions.py`（460-462 用例）
6. 异常注册四件套之注册三动作：`_code_ranges.py`（CODE_RANGES 增 `"sap": (460, 469)` 行 + `_CLASS_TO_SUBDOMAIN` 增三行 + 段注释）+ `domain/exceptions/__init__.py`（导出）+ `interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 460→504 / 461→409 / 462→500——语义就近映射先例：DebateLowDivergenceError 422→422 同款）
7. 文档联动：`docs/architecture/sisys-uni-exception-design.md` §3.3.2（编码分配表插 sap 段行 + 子域范围表更新）；`src/interfaces/sap/__init__.py` docstring「bus 归 5.11」注记更新为交付态
8. 存量触碰（异常注册面）：`tests/unit/interfaces/api/test_exception_handlers.py`（expected_types 集合追加 460/461/462——穷举等值断言，尾部追加策略）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: SAPBus 端口与进程内总线核心——五种消息类型分发 + BROADCAST 全员送达 + 优先级出队 + 协议校验面

**Given** 真实 `InProcessSAPBus`（手工构造——组合注入 `_StubBlackboard`[duck-typing 实现 PublicBlackboard 捕获 post] + `_RecordingIsolationGuard`[duck-typing 放行形态]；**每场景新实例**——SINGLETON 组件验收手工新实例惯例）与真实 `SAPMessage`（15 字段 Pydantic——5-3 交付，`sender_id`/`receiver_id` 用 `str(uuid.uuid4())` 测试标识[OD-5 UUID 形态]）
**When** ①单播：receiver 方 `subscribe(receiver_id, handler)` 注册后，另一方 `send(SAPMessage(message_type=T))`（T ∈ {REQUEST, RESPONSE, NOTIFICATION, DEBATE} 四种非广播类型逐一）②广播：N≥3 个接收方各自 subscribe 后 `send(SAPMessage(message_type=BROADCAST, receiver_id="broadcast"))` ③优先级：同一接收方队列内乱序 send 六条消息——四级各一条（LOW/NORMAL/HIGH/URGENT 乱序注入）+ 追加两条 NORMAL（同级 FIFO 观测对——v1.1.0 补：创建期「四条互异优先级」构造下同级 FIFO 不可观测）④校验面：向未注册 `receiver_id` 单播 / `sender_id` 非 UUID 字符串 / `receiver_id` 非 UUID 非 "broadcast" 约定值 / BROADCAST 组合违规（BROADCAST+receiver≠"broadcast" 与 非 BROADCAST+receiver=="broadcast" 双向）各发一条⑤关闭态：`close()` 后 `send`
**Then** ①**单播送达**：handler 收到的消息与发送实例 15 字段 Pydantic 实例全等（`==`——全字段含 timestamp/subject/context）+ epics L1944-1947 点名十键（message_id/conversation_id/sender_id/receiver_id/message_type/priority/content/correlation_id/isolation_level/blackboard_visible）逐键显式断言 + 总线行为输入键 `requires_response`/`timeout_seconds` 显式点名（v1.1.0 补：创建期「十键点名+逐字段相等」两种强度混写——十键是 epics 验收点名面，15 字段全等是投递保真面）②**广播全员**：N 个接收方 handler 各收到同一 message_id（全员送达零遗漏——接收方集合快照在 send 时刻定格，send 后 subscribe 者不收到；跨接收方不保证同序——各自独立队列异步出队）③**优先级出队**：接收方收到顺序 == URGENT > HIGH > NORMAL×3（三条 NORMAL 按入队序——同级 FIFO 可观测）> LOW（乱序注入实证插队语义；分发是异步消费任务形态，等待队列清空后断言序）④**校验面 fail-loud**：未注册接收方单播 → `SAPBusStateError`（EXCEPTION_461——send 抛出即失败，消息零入队零投递[发送方拿到明确错误自行处置——比静默入队后无人消费更诚实]）；非 UUID sender → 461（reason=invalid_sender_id）；非 UUID 且非 "broadcast" 的 receiver → 461（reason=invalid_receiver_id——v1.1.0 补：闭集成员创建期无触发用例）；BROADCAST 组合双向违规 → 461（OD-8）⑤**关闭态**：close 后 send/subscribe/wait_for_response → 461（reason=bus_closed）；**close 动作清单钦定（v1.1.0）**：幂等 + 取消全部消费任务 + 清空 per-receiver 队列 + 取消挂起 correlation Future（`set_exception(SAPBusStateError 461 bus_closed)`——**在途等待者收 461** 非 CancelledError，与「close 后新调用 → 461」结局统一）
**And** `SAPBus` Protocol 方法面四方法（send/subscribe/wait_for_response/close——`@runtime_checkable`，契约测试锚）；**积压口径注记**：per-receiver 队列长度可观测（NFR-IF-03「积压<100 条」是部署容量面——测试断言并发场景队列最终清空[AC-5.2 承载]，不设阈值门）；**异步 handler 支持**：handler 形态 `Callable[[SAPMessage], Awaitable[None] | None]`（协程 await 后再出队下一条——串行保序）；**handler 异常处置钦定 deliver-continue（v1.1.0）**：消费任务捕获 handler 异常（同步 raise 与异步异常等效）→ log warning（含 message_id 与异常摘要）→ **继续出队下一条**（单条 handler 崩溃不冻结该接收方队列——Actor supervision 隔离惯例）；**校验次序钦定**：`_validate` 开闭态检查首位（closed bus 上任何载荷违规均报 bus_closed——状态先于载荷）；**订阅语义钦定（v1.1.0）**：subscribe 侧同样校验 UUID（非法拒绝 461 reason=invalid_receiver_id——防「永远无法合法收到消息」的死订阅）；同 receiver_id 重复 subscribe **覆盖**（后注册 handler 生效——dict 语义一致）；sender 订阅自身 id 时收到自己的消息（自收合法）；零订阅者 BROADCAST 静默成功零投递（全员=当前空集）

**验证标准/Validation Criteria:**
- [ ] 四种单播类型逐一送达 + 15 字段实例全等 + epics 十键逐键 + requires_response/timeout_seconds 显式断言
- [ ] BROADCAST 三接收方全员收到同一 message_id
- [ ] 优先级出队顺序断言（乱序注入 URGENT/HIGH/NORMAL×3/LOW 六条——插队 + 同级 FIFO 双观测）
- [ ] 未注册接收方 → 461 三段式断言（raises + code + context）
- [ ] 非 UUID sender_id → 461（invalid_sender_id）；非 UUID 非 broadcast 的 receiver_id → 461（invalid_receiver_id——含 subscribe 侧）；"broadcast" 豁免仅 receiver_id 约定值（sender 仍须 UUID）
- [ ] BROADCAST 组合双向违规 → 461（两方向参数化）
- [ ] close 后三方法 → 461 + close 幂等（二次 close 不抛）+ close 时挂起等待者收 461（bus_closed）+ 队列清空 + 消费任务取消
- [ ] 异步 handler 串行保序（同接收方两条消息按入队序处理完成）
- [ ] handler 抛异常 deliver-continue（首条异常 → 后续消息仍送达 + log warning 含 message_id）

### AC-2: 请求-响应关联——REQUEST 等待 + RESPONSE correlation 匹配 resolve + 超时 460

**Given** 真实 `InProcessSAPBus` + 两方装配（请求方 subscribe 自身 receiver_id；响应方 subscribe **自身 receiver_id（即 REQUEST 的 receiver 目标——v1.1.0 措辞修正：创建期「响应方 subscribe 请求方 target」易误读为响应方订阅请求方的 id）**，其 handler 内回发 RESPONSE）
**When** ①关联：请求方 `send(REQUEST, requires_response=True)` 取 `message_id` 作 correlation 锚 → `wait_for_response(correlation_id=该 message_id)` 挂起 → 响应方 handler 构造 `RESPONSE(correlation_id=请求.message_id)` 回发 → Future resolve②超时：`send(REQUEST)` 后无人回发 → `wait_for_response(correlation_id, timeout_seconds=0.1)`（短超时快速验证）③无等待语义：`send(NOTIFICATION, requires_response=False)`（默认）——消息直达 handler，correlation 索引零挂起条目
**Then** ①**关联送达**：`wait_for_response` 返回的 RESPONSE 消息 `correlation_id == 请求.message_id`（关联链闭合——interface-design.md §7.5 REQUEST→RESPONSE 流程的协议承载；**correlation 锚约定见 OD-9**）；请求方 handler **同时**也收到该 RESPONSE（正常单播送达语义不受等待原语影响——双动作：送达 + resolve）②**超时**：抛 `SAPTimeoutError`（EXCEPTION_460——context 携 correlation_id: str[统一 `str(correlation_id)` 换算——参数面 UUID/异常 context 面 str 的口径钦定] 与 timeout_seconds；**等待条目清理**——超时后索引中该 correlation 零残留[等待路径防泄漏 + 迟到响应不 resolve 已超时 Future——v1.1.0 措辞收窄：创建期「防内存泄漏」泛化过强，未 await 的登记条目活至 close，V1 无 TTL 清扫，知悉注记]）；迟到响应（超时后 RESPONSE 才到）→ 零崩溃零 resolve（Future 已清理防御面——log warning）③**默认无等待**：NOTIFICATION 直送 + `wait_for_response` 对无挂起条目的 correlation_id 立即按超时路径处理（等满 timeout 抛 460——不 special-case）④**正常双响应幂等（v1.1.0 新增）**：同 correlation 第二条 RESPONSE 到达（发送方重复回发——正常路径非超时迟到）→ 幂等 resolve 守卫（`future.done()` 检查）零 InvalidStateError 零崩溃（log-ignore——JMS 重复投递幂等惯例）；**条目生命周期钦定**：登记条目保留至超时清理或 close（resolve **不**移除条目——「resolve 即移除」会使 resolve 之后才调 wait 的等待者落入无条目路径等满伪超时）
**And** **timeout 默认值口径**：`wait_for_response(correlation_id, timeout_seconds=None)` 时取**请求消息的 timeout_seconds**（登记条目承载——300 默认，SAPMessage 字段语义承载；显式传参覆盖）；**无挂起条目 + None 的兜底钦定（v1.1.0）**：无登记条目可取时取模块级常量 `SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS = 300.0`（与 SAPMessage.timeout_seconds 默认对齐——创建期该组合无定义）；**计时锚点钦定（v1.1.0）**：timeout 从 `wait_for_response` **调用时刻**起算（asyncio.wait_for duration 语义——非 send 时刻 deadline 语义）；超时抛出前取消底层等待任务；并发多请求挂起互不干扰（两对 REQUEST 并发等待各自 resolve——correlation 键控隔离）

**验证标准/Validation Criteria:**
- [ ] REQUEST→RESPONSE 关联链：wait_for_response 返回消息 correlation_id 匹配（OD-9 锚约定）+ 请求方 handler 双重送达断言
- [ ] 超时 → 460 三段式（raises + code + context 两键）+ 索引清理断言（超时后内部挂起表零残留——行为断言经迟到 RESPONSE 零异常承载）
- [ ] 迟到响应零崩溃（超时后回发 RESPONSE——bus 不抛不 resolve）
- [ ] 正常双 RESPONSE 幂等（第二条 RESPONSE 零 InvalidStateError 零二次 resolve + log-ignore）
- [ ] NOTIFICATION 默认无等待 + 未挂起 correlation 的 wait 按超时路径
- [ ] timeout 默认值取请求消息 timeout_seconds（不传参 300 生效口径——短化场景用显式传参）+ 无条目 + None 兜底 300.0（SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS）
- [ ] 计时锚点 = wait_for_response 调用时刻（duration 语义——docstring 注记）
- [ ] 并发两对请求各自关联 resolve（键控隔离）

### AC-3: 公共黑板交互——blackboard_visible 守卫集成 + MVCC 写入 + 449 透传 + 零写入边界

**Given** ①真实 Redis 场景：真实 `RedisPublicBlackboard`（经组合根 resolve 或手工 `RedisAdapter` 装配——**场景级独立客户端**，session 级跨循环不可用[记忆：acceptance_redis_client_cross_loop_issue]；Redis 不可用 → `pytest.skip` 动态跳过）+ conversation_id 用 UUID 前缀隔离（多测试零键冲突）②守卫真实链场景（AC-3.2）：真实隔离服务链（真实 Redis + 真实实例化 CEO Agent[L4 默认] + 真实 `IsolationGuardPort`——5-5 AC-3.3 装配形态延续）③替身场景（AC-3.1/3.3 单元面）：`_StubBlackboard` 捕获 post + `_RecordingIsolationGuard` 放行形态
**When** ①`send(BROADCAST, blackboard_visible=True)`（guard 放行[替身]）②`send(任意类型, blackboard_visible=True)` 且真实链下 actor 为 L4 Agent（真实 guard——L4=READ_ONLY 黑板写禁止）③`send(NOTIFICATION, blackboard_visible=False)`（默认）
**Then** ①**MVCC 写入**：黑板桥调用 `PublicBlackboard.post(conversation_id=str(message.conversation_id), agent_id=message.sender_id, content={"message_id": str(message.message_id), "message_type": message.message_type.value, "content": message.content, "priority": message.priority.value}[四键最小投影——枚举显式 .value 字符串化{断言确定性：读回比较是纯 str 域；RedisJSONEncoder 虽原生处理 Enum[L28-29——v1.1.0 勘误：创建期误记 L35-36]，显式化消除双层依赖}], confidence=1.0)`——真实 Redis 场景断言：post 返回版本号 ≥1 且**连续两次 post 版本递增**（MVCC incr 语义——5.11 黑板写入面与既有黑板测试族的衔接锚）+ `get(conversation_id)` 读回 content.message_id 相等（写入可读回）；②**守卫拒绝透传**：真实链 L4 写黑板 → `IsolationOperationForbiddenError`（EXCEPTION_449）**原样上抛**（透传不包装——context reason=data_isolation:read_only 保留 5-5 分码语义）+ 黑板零写入（真实 Redis get 空断言）；③**零写入边界**：blackboard_visible=False → `_StubBlackboard` 零 post 调用（可见性开关是写入唯一闸门）——**含 BROADCAST+False 组合用例（v1.1.0 补：全员送达 + 零 post——OD-7 正交开关钦定的行为锚）**
**And** **守卫参数锚**：`ensure_agent_access(actor_agent_id=uuid(sender_id), target_agent_id=uuid(receiver_id)[BROADCAST 形态 target=actor 自身——广播无特定目标], resource=IsolationResource.BLACKBOARD, operation=AccessOperation.WRITE)`；**判定语义注记（v1.1.0）**：守卫判定单边取 **actor 侧**隔离状态（isolation_guard_service `get_isolation_state(actor_agent_id)` 真源——isolation_guard_service.py L107-108），`target_agent_id` 仅参与 cross_agent 布尔判定——**消息的 `isolation_level` 字段是显示性标识（发送时快照），不是判定输入**（判定输入是隔离状态存储——AC-3.2 真实链经实例化 CEO Agent 写入 L4 状态后拒绝；防 dev 误把字段值传给守卫）；**写失败 fail-loud**（OD-7）：`_FailingBlackboard` 替身 post 返 0 → `SAPBlackboardWriteError`（EXCEPTION_462——context 携 conversation_id；消息**不投递**[发送原子性：黑板承诺面失败则整条 send 失败——先黑板后入队次序钦定]）；**449/448/443/447 全族透传注记**：守卫四码不包装不上转译（黑板桥无异常翻译职责）；**自清理**：真实 Redis 场景 teardown `delete(build_key("blackboard", conversation_id))` + 版本键（只清理自己创建的键）

**验证标准/Validation Criteria:**
- [ ] 真实 Redis：blackboard_visible=True 两次 send → 版本号递增 + get 读回 content 匹配
- [ ] 真实链 L4 写黑板 → 449 透传三段式 + 黑板零写入（真实 get 空）
- [ ] blackboard_visible=False → 零 post 调用（替身计数断言——含 BROADCAST+False 组合）
- [ ] post 返 0 → 462 + 消息不投递（接收方 handler 零调用）
- [ ] content 四键最小投影断言（message_id/message_type/content/priority）
- [ ] conversation_id str 换算（message.py L48-49 归 5.11 注记兑现——str(UUID) 形态）
- [ ] 自清理：teardown 后黑板键与版本键均不存在

### AC-4: 序列化契约与端口接线——JSON 往返保真 + 组合根注册 + 契约测试 + 架构合规

**Given** ①真实 `SAPMessage` 全字段实例（15 字段全显式赋值——含 UUID/datetime/枚举/dict 嵌套）②组合根 bootstrap 后的端口注册中心
**When** ①序列化：`serialize(message)` → JSON 字符串 → `deserialize(json_str)` 往返②接线：`resolver.resolve("sap_bus")`③契约与架构验证
**Then** ①**往返保真**：往返实例与原实例逐字段相等（UUID/datetime ISO 感知/枚举 str 值[IsolationLevel "L4" 形态]/dict 嵌套逐值——Pydantic v2 `model_dump_json`/`model_validate_json` 承载；**wire format 稳定性注记**：序列化是跨进程演进[V2+]的格式契约——NFR-INT-05 向后兼容 1-2 个版本的格式基线；坏 JSON/缺字段 JSON 反序列化 → pydantic ValidationError 原样透传[Schema 层契约——bus 不吞不包装]）②**接线四件**：resolve("sap_bus") 非 None 且 isinstance SAPBus（`@runtime_checkable`）+ 实现类 `InProcessSAPBus` + PortSpec 元数据（version v1.0.0 / lifetime SINGLETON[**有状态总线——订阅表+correlation 索引+优先级队列跨 send/wait 共享，状态即功能**——5-9 DC-6/5-10 DC-7 同族论证] / owner=platform / tags=("agent","sap","collaboration")）+ resolve 注入链（实例 `_blackboard` 非 None 且 `_guard` 非 None——两依赖接线可达）
**And** **契约测试**（test_port_contract_sap_bus.py——11 维度 + REQUIRED_METHODS 四方法 + _DummyResolver 分发 public_blackboard/isolation_guard_service）；**架构合规**：bus.py 第三方白名单 **{pydantic}**（`from pydantic import ...` 合法——SAPMessage 同文件族；禁 asyncio 外任何新第三方——asyncio 是标准库）+ 依赖方向（bus.py import src.domain.events.enums[IsolationLevel] + src.application.ports.{public_blackboard,isolation_guard}——interfaces→domain/application 双合法面 ✓）+ 组合根外零实例化（`InProcessSAPBus(` 构造点仅 composition_root.py + tests/）+ `sap_exceptions.py` 仅在 exceptions 注册三件内 + events 零触碰（SAP 非领域事件——event_channels.yaml/ChannelRouter/domain/events 零改动）+ 零抑制注释（noqa/type: ignore 红线）；**装配失败语义（fail-fast 非降级）**：sap_bus 的 lambda 内两依赖 resolve 失败 → raise `ConfigurationError`（EXCEPTION_101）——与 5.6/5.8/5.9 可选依赖 resolve_optional→None 降级族**相反**的裁定依据：那些是可观测附加面[None 默认向后兼容]，SAP 总线是功能主面且零存量消费方[无 None 兼容包袱——装配失败应立即暴露]；**翻译形态钦定（v1.1.0）**：resolver/`_DummyResolver` 对未注册名抛 `KeyError`（resolver.py L94-96），lambda 须显式包装 `try: ... except (KeyError, RuntimeError) as e: raise ConfigurationError(...) from e`（既有组合根 lambda 均让 KeyError 自然传播——零包装先例，本 Story 自造形态须落文字；import 源 `from src.domain.exceptions import ConfigurationError`——契约测试断言 ConfigurationError 依赖此实现）；**惰性装配注记**：lambda 在**首次 `resolve("sap_bus")` 时执行**（SINGLETON 惰性首解析——red_blue_debate_service lambda 注入四依赖同款），非 bootstrap 期阻断；测试形态：_DummyResolver 未注册依赖 → resolve 抛 ConfigurationError 断言

**验证标准/Validation Criteria:**
- [ ] 15 字段全显式实例 JSON 往返逐字段相等（含 datetime tz-aware/枚举 str/UUID/dict 嵌套）
- [ ] 坏 JSON → pydantic ValidationError 透传（零包装断言）
- [ ] resolve 四件断言（可达/isinstance/PortSpec 元数据四项/SINGLETON）
- [ ] 依赖注入链断言（_blackboard/_guard 非 None）
- [ ] 契约测试 11 维度全绿 + REQUIRED_METHODS 四方法
- [ ] AST 验证器 A/B/C 全绿（白名单 {pydantic} + 组合根外零实例化 + events 零触碰 + 零抑制）

### AC-5: 性能三锚——消息传递 P95<200ms + 序列化 P95<50ms + 并发处理≥50

**Given** ①传递口径 = **send→handler 收到全程**（校验+黑板桥跳过[blackboard_visible=False]+入队+异步出队+handler 调用——进程内全链；**本地进程口径**[进程内 µs 级——200ms 门是回归绊线非容量预算，网络传输是 V2+ 面——OD-4 部署形态知悉注记同 5-8 DC-8④ 诚实注记形态]）②序列化口径 = **model_dump_json + model_validate_json 往返**（15 字段满载实例——最大体积形态）③并发口径 = **50 对 send/收齐**（50 条消息并发 send 至同一接收方 + gather 全部送达断言——epics L1925「并发消息处理≥50」）④委托计时三件（常量单源 `SAP_DELIVERY_P95_LIMIT_SECONDS = 0.2` + `SAP_SERIALIZATION_P95_LIMIT_SECONDS = 0.05` + `SAP_CONCURRENCY_FLOOR = 50` 定义于集成模块验收 import 禁双真源 / `_PERF_CACHE` 单 key `sap_perf` 载三指标 summary dict / `xdist_group("sap-protocol-perf")` 同 worker 串行——组名与既有 15 组互异）
**When** ①测量传递延迟（warmup 1 + **20 采样**——`statistics.quantiles(latencies, n=20)[18]` exclusive[5-8/5-9/5-10 同款口径]；单次采样 = 构造消息 → send → handler 收到事件[asyncio.Event] 全程 monotonic 计时）②测量序列化延迟（同批 20 采样 = dump+validate 往返）③并发（一次性 50 条 gather send + 队列清空等待 + 收到计数==50）
**Then** ①传递 P95 < 0.2s（epics L1923 钦定）②序列化 P95 < 0.05s（epics L1924 钦定）③50 条全部送达 + 接收方处理串行完成后队列清空（积压归零——NFR-IF-03 积压口径的行为面承载）
**And** **正向锚**：采样轮 handler 收到计数 == warmup + 采样数（21——防静默跳过假绿）；并发轮 50/50 零丢失（red_blue_debate 50 并发先例同款逐条断言）；口径声明落 docstring（进程内口径 / 绊线定位 / 20 样本方差知悉 / 序列化满载口径四注记——5-8 DC-8④ 形态）；零外部服务依赖（进程内性能面——Redis 探测不适用本 AC；黑板真实 Redis 性能在 AC-3 场景非计时面）；**redis marker 分档钦定（v1.1.0）**：集成文件文件级 `pytestmark=[pytest.mark.integration]`，`TestRealRedisBlackboardBridge` **类级**挂 `pytest.mark.redis`（真实 Redis 依赖归此类）、`TestSAPPerformance` 类级仅 `xdist_group("sap-protocol-perf")` **不挂 redis**（进程内性能与 Redis 无关——挂了会让 `-m "not redis"` 环境连性能三锚一并排除，与「零外部服务依赖」自相矛盾）；验收文件：AC-3 三场景**场景函数级** `@pytest.mark.redis`（文件名 sap_protocol 不含服务关键词、自动挂载不生效——triple_isolation L110-117 显式声明先例的场景级变体；其余 11 场景进程内+替身不挂——`-m "not redis"` 时仅 AC-3 三场景被排除）

**验证标准/Validation Criteria:**
- [ ] 传递 P95<200ms：常量单源 + 委托形态 + 20 采样 quantiles[18] 口径 docstring
- [ ] 序列化 P95<50ms：同批采样 + 满载实例口径
- [ ] 并发 50/50 全送达 + 队列清空断言
- [ ] 正向锚：收到计数 21 + 50/50 零丢失
- [ ] 口径声明落 docstring（四注记）
- [ ] xdist 组互异断言（grep）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] **本 Story 零新领域事件**（SAPMessage 是接口层横向协议非 DomainEvent——5-3 架构钉死 + 守护测试在位；event_channels.yaml/ChannelRouter/domain/events 零改动——AC-4 架构合规断言面）

#### 数据模型 (Data Models)
- [x] **本 Story 零新数据模型**（SAPMessage 15 字段[5-3 交付]直接消费；bus 内部队列条目/Future 索引是实现细节非领域模型）

#### 统一端口定义注册与管理 (Port Contract)
- [x] `SAPBus` Protocol 定义位于 `src/interfaces/sap/bus.py`（接口层横向协议——architecture.md L2172 规划钦定（v1.1.0 勘误）+ 5-3 职责边界延续；**非 domain/application 端口的裁定依据**：SAPMessage Pydantic 载体在 interfaces，application/domain 依赖它会击穿依赖方向矩阵）
- [x] 端口注册中心：`_global_registry` 经组合根 `register_port(name="sap_bus", ...)` 登记 PortSpec（name/version/interface/impl/module/lifetime/owner/tags）
- [x] 端口实现仅在 `src/composition_root.py` 统一注册；业务代码经 `resolver.resolve("sap_bus")` 消费
- [x] 端口契约测试 `tests/contracts/test_port_contract_sap_bus.py`（11 维度 + REQUIRED_METHODS）
- [x] R2 组合注入：SAPBus（接口层）组合注入 PublicBlackboard + IsolationGuardPort（应用层基础端口——interfaces→application 合法面）
- [x] 唯一名称 sap_bus / version v1.0.0 / owner platform / lifetime SINGLETON（有状态论证；**生命周期错配知悉注记 v1.1.0**：SINGLETON 总线经首解析捕获 **SCOPED** public_blackboard 快照——DI 语义上是 captive dependency，但 RedisPublicBlackboard 是无状态包装（客户端经 redis_client 端口间接持有），快照无害；docstring 注记防未来实现引入状态后被 clear_scoped() 击穿）/ tags ("agent","sap","collaboration")

#### 端口契约清单执行约束（强制）
- [x] 本故事文件「现有代码继承」表是唯一事实源；禁新建 blackboard/sap 消息同义端口；未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)
- [x] 归属模块与基类：**sap 子域新段 460-469**（第六段先例：前段满/语义独立→开独立段）；`SAPTimeoutError`（EXCEPTION_460，**BusinessException**——协议交互超时是调用方可处理结果[等待方决定降级/裁决升级]，**直接先例 ToolExecutionTimeoutError 385（BusinessException→HTTP 504——business+超时+504 三合一，v1.1.0 补引：比 DebateLowDivergenceError 422 门控先例更贴切**；460 与 domain 既有 external 族 TimeoutError 302 零码冲突且语义不同域[302=外部服务故障、460=进程内协议交互]）+ `SAPBusStateError`（EXCEPTION_461，**SystemException**——总线状态违规[未注册接收方/非 UUID 标识/组合违规/关闭后操作]属编程与协议契约错误，与 InvalidStateError 同族）+ `SAPBlackboardWriteError`（EXCEPTION_462，**SystemException**——黑板基础设施写失败[post 返 0 检测]，与 StorageError 103 系统资源族同族但不复用[子域分立——事件总线 MessageBusError 与 SAP 协议分立的同款先例：debate 420 段独立于 event 段]）
- [x] 唯一编码分配：460/461/462（grep `EXCEPTION_46[012]` src/ 零碰撞——创建期已实证）；`_code_ranges.py` CODE_RANGES 增 `"sap": (460, 469)` + `_CLASS_TO_SUBDOMAIN` 三行 + 段注释（463-469 预留 sap 域）
- [x] 构造器参数：SAPTimeoutError(correlation_id: str, timeout_seconds: float\|int, message, cause, context_extra) / SAPBusStateError(reason: str, message, **cause**[v1.1.0 补：三异常统一显式 cause 形参——创建期 461 清单缺漏，基类虽支持但规格面应齐全], context_extra——reason 闭集 {receiver_not_registered, invalid_sender_id, invalid_receiver_id, broadcast_convention_violation, bus_closed}[五成员全部有触发用例——v1.1.0 补 invalid_receiver_id 用例]；非法 reason 拒绝 → EntityValidationError[ArchiveStorageError 先例——Task 1 绿]) / SAPBlackboardWriteError(conversation_id: str, message, cause)——context dict 暴露全上下文
- [x] 消息安全性：错误文案面向调用方（协议语义），零内部实现细节
- [x] 编码注册：`_CLASS_TO_SUBDOMAIN` + `sisys-uni-exception-design.md` §3.3.2 编码分配表 + 子域范围表
- [x] 导出完整性：sap_exceptions.py `__all__` + domain/exceptions/__init__.py 导出 + EXCEPTION_HTTP_MAP（460→504 Gateway Timeout / 461→409 Conflict / 462→500——语义就近映射，DebateLowDivergenceError 422→422 先例）
- [x] 测试覆盖：`tests/unit/domain/exceptions/test_sap_exceptions.py`（构造/属性/to_dict/context/cause 链 + reason 闭集）+ `poetry run pytest tests/unit/domain/exceptions/ -v`（8 项自动）+ `test_exception_handlers.py`（expected_types 追加 460/461/462）
- [x] BDD 验收场景：异常路径纳入 Edge Cases（AC-1 校验面/AC-2 超时/AC-3 拒绝与写失败——Gherkin 场景见验收标准）

#### API 契约 (API Contract)
- [x] **本 Story 零 REST 端点**（嵌入式协议基础设施——openapi.yaml 零改动；REST 面 7-2 立项时评估——范围边界表 ❌ 行）

#### 六边形架构约束（必须遵守）
- [x] 依赖方向：bus.py（interfaces）→ domain（events.enums.IsolationLevel 经 SAPMessage 传递）+ application（ports.public_blackboard/isolation_guard）✓ 合法；application/infrastructure/domain **零触碰 interfaces.sap**（守护测试 test_arch_agent_workflow.py 既有 + 本 Story 验证器 B 强化 sap 触碰面收窄）
- [x] 领域层零依赖：sap_exceptions.py 纯标准库（dataclass 继承链——domain/exceptions 族同款）

#### 验收标准 Gherkin (Acceptance Tests)
- [x] `tests/acceptance/test_acceptance_sap_protocol.feature`（14 场景：AC-1×3 + AC-2×3 + AC-3×3 + AC-4×2 + AC-5×2 + 收尾×1——R6 骨架中文 Gherkin）
- [x] `tests/acceptance/test_acceptance_sap_protocol.py`（三属性分档表 docstring + @scenario 绑定 + context/event_loop/_run_async 三件套 + 延迟 import + Redis 探测 skip）
- [x] Happy Path + Edge Cases 全覆盖（校验面/超时/拒绝/写失败四异常族入场景）

**BDD 步骤实现约束：**
- 步骤函数 `event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`——context 丢失红线）
- 同一中文文本双装饰器支持（given/when 复用）
- Edge Cases 含异常路径（461/460/449/462 四码三段式断言——error code 断言经 raises 三段式非 HTTP 响应[嵌入式组件无 HTTP 面]）

#### Task 0 完成标志：
- [x] 规范项全部定义完毕
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [x] **链路接线断言清单**已定义：①组合根 register_port("sap_bus") 装配验证（resolve 可达 + 注入链两依赖非 None——AC-4）②**零事件发布面**（SAP 非领域事件——event_channels.yaml 零条目是正确形态，「已实现未接线」检查不适用事件面）③**零中间件面**（middleware 归 V2）；生产消费方接线（Epic 9）在范围边界表显式登记非「未接线遗留」

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证 | 改坏生产代码 → 测试红 → 还原 → 绿 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试 / 测试集中最后 Task / 跳过红阶段 / 跳过变异实证
- ❌ 浮点 approx / 断言放空（本 Story 主要是整数版本号/计数/字符串相等断言——天然精确）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | sap 异常族 | 460/461/462 构造/属性/to_dict/context/reason 闭集 | `tests/unit/domain/exceptions/test_sap_exceptions.py` | Task 1 |
| TDD 单元测试 | InProcessSAPBus | 单播/广播/优先级/校验面/关闭态/请求-响应/超时/黑板桥 | `tests/unit/interfaces/sap/test_bus.py` | Task 2/3/4 |
| TDD 契约测试 | sap_bus 端口 | 11 维度 + REQUIRED_METHODS 四方法 + Dummy 分发 | `tests/contracts/test_port_contract_sap_bus.py` | Task 2 |
| TDD 验收测试 | Gherkin 场景 | 业务价值验收（14 场景） | `test_acceptance_sap_protocol.feature` | Task 0 |
| TDD 验收测试 | BDD 步骤实现 | 步骤函数 + 真实服务场景 | `test_acceptance_sap_protocol.py` | Task 0 |
| TDD 验收测试 | 收尾验收场景 | src 与测试目录完成清单确认 | 同上两文件 | Task 7 |
| SDD 架构验证 | 六边形架构 | 白名单/实例化收窄/依赖方向/events 零触碰/静态锚/零抑制 | `tests/unit/architecture/test_arch_sap_protocol.py` | Task 6 |
| 集成测试 | 真实 Redis 黑板 + 性能 | MVCC 往返/449 真实链/三锚委托 | `tests/integration/test_integration_sap_protocol.py` | Task 5 |
| 存量追加 | 异常 HTTP 映射 | expected_types 穷举等值 | `tests/unit/interfaces/api/test_exception_handlers.py` | Task 1 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（CI 门禁）- P0
- [ ] **接口层覆盖率 ≥85%**（OD-2 口径修正——epics L1928 应用层 → 实际交付层；**口径统一钦定 v1.1.0：整层 ≥85%**[创建期 Task 2 DoD 写「新文件行覆盖」与节首「接口层覆盖率」两处分母不同]；实测基线：接口层今日 89%（1418 stmts）+ sap 包 100%——bus.py 增量下整层仍 ≈90%，可行；**两段式命令**[Makefile L278-282 陷阱注记——pyproject `source=["src"]` 覆盖 `--cov=src.<layer>` 使 TOTAL 恒全 src]：`poetry run pytest tests/unit/ --cov=src -q && poetry run coverage report --include="src/interfaces/*" --fail-under=85`）- P1
- [ ] **domain 层 ≥90%**（sap_exceptions.py 三异常全覆盖承载）- P1
- [ ] **集成测试覆盖交付行为**（≥75% 口径——真实 Redis 场景 + 性能三锚承载）
- [ ] **关键路径 100%**（send 四分支[校验拒绝/黑板/入队/广播扇出] + wait_for_response 两路径[resolve/超时] + close）

#### 代码质量门禁
- [ ] `poetry run ruff check src/ tests/` 通过
- [ ] `poetry run mypy .`（**全仓含 tests/**——5-9 Task 6.4 漏 tests 面 ×9 教训）
- [ ] `pre-commit run --all-files` 通过
- [ ] 零抑制注释（noqa/type: ignore/pylint: disable——红线 grep 自查）

#### 测试隔离约束（本 Story 特化）

| 约束 | 规则 |
|------|------|
| SINGLETON 总线 | 每场景手工新实例（不走 resolve——跨场景订阅表/索引污染）；性能场景同实例连续采样 |
| 真实 Redis | 场景级独立客户端（session 级跨循环不可用——记忆锚）；conversation_id UUID 前缀；teardown 只清自己创建的黑板键+版本键 |
| 异步 handler | 串行保序依赖消费任务——测试等待队列清空用 asyncio.Event/条件轮询超时上限（禁 sleep 死等） |
| BDD async | `event_loop.run_until_complete()`；禁 `@pytest.mark.asyncio`；禁 xdist 并行下 BDD 步骤内 `asyncio.run()` |
| 性能委托 | `_PERF_CACHE` + xdist_group 逐字同组（集成/验收两文件）；「命中或首次采样」禁先跑断言 |
| 验收禁 mock | 手写零 IO duck-typing 替身（_StubBlackboard/_RecordingIsolationGuard/_FailingBlackboard）；真实服务场景（Redis/隔离链）不可用 `pytest.skip` 动态跳过禁写死 |
| asyncio 原语 | Future/Event 在同 loop 创建（bus 与测试同 loop——模块级 event_loop 驱动） |

**验证要求：**
- [ ] `poetry run pytest tests/ -n 8` 通过（并行隔离）
- [ ] 连续 5 次运行无随机失败
- [ ] ruff + mypy 全仓通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 五种类型单播 + 15 字段全等与十键断言 | Task 2 | 2.1-2.2 | test_bus.py + 验收 AC-1.1 |
| AC-1 | BROADCAST 全员送达 | Task 2 | 2.2 | test_bus.py + 验收 AC-1.1[与单播同场景——v1.1.0 消歧：分发面合一] |
| AC-1 | 优先级出队（乱序插队 + 同级 FIFO） | Task 2 | 2.2 | test_bus.py + 验收 AC-1.2 |
| AC-1 | 校验面（未注册/非 UUID 双侧/组合双向/关闭态 461） | Task 2 | 2.1-2.2 | test_bus.py + 验收 AC-1.3[v1.1.0 勘误：Subtask 对调修正——校验面属循环 A；AC-1.3=校验面专属场景] |
| AC-2 | REQUEST→RESPONSE 关联 resolve | Task 3 | 3.1-3.2 | test_bus.py + 验收 AC-2.1 |
| AC-2 | 超时 460 + 索引清理 + 迟到防御 | Task 3 | 3.1-3.2 | test_bus.py + 验收 AC-2.2 |
| AC-2 | 默认无等待 + 并发键控隔离 | Task 3 | 3.2 | test_bus.py + 验收 AC-2.3 |
| AC-3 | MVCC 写入真实 Redis（版本递增+读回） | Task 4/5 | 4.2/5.1 | 集成 + 验收 AC-3.1 |
| AC-3 | L4 真实链 449 透传 + 零写入 | Task 4/5 | 4.2/5.1 | 集成 + 验收 AC-3.2 |
| AC-3 | False 零写入 + 462 fail-loud + 不投递 | Task 4 | 4.1-4.2 | test_bus.py + 验收 AC-3.3 |
| AC-4 | JSON 往返 15 字段 + 坏 JSON 透传 | Task 2 | 2.3 | test_bus.py + 验收 AC-4.1[v1.1.0 勘误：Subtask 对调修正——序列化属循环 B] |
| AC-4 | 组合根注册 + 注入链 + 契约 11 维度 | Task 2 | 2.3 | test_port_contract_sap_bus.py + 验收 AC-4.2 |
| AC-4 | AST 架构合规（白名单/收窄/零抑制） | Task 6 | 6.1-6.3 | test_arch_sap_protocol.py |
| AC-5 | 传递 P95 + 序列化 P95（委托） | Task 5 | 5.2-5.4 | 集成 + 验收 AC-5.1 |
| AC-5 | 并发 50/50 + 队列清空 | Task 5 | 5.2 | 集成 + 验收 AC-5.2 |
| 收尾 | 完成清单逐项确认 | Task 7 | 7.1-7.4 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5（Gherkin 全场景）+ 留项处置两条

> **目的：** 在进入代码实现前，明确端口契约、异常契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义端口契约规范（SAPBus Protocol 四方法签名——`async def send(self, message: SAPMessage) -> None` / `def subscribe(self, receiver_id: str, handler: Callable[[SAPMessage], Awaitable[None] | None]) -> None` / `async def wait_for_response(self, correlation_id: uuid.UUID, timeout_seconds: float | None = None) -> SAPMessage` / `async def close(self) -> None`[v1.1.0 补签名级钦定：send/wait/close 必须 async——await 守卫与黑板 post；subscribe 同步注册] + InProcessSAPBus 组件职责图——校验面/黑板桥/优先级队列/correlation 索引/消费任务五件；R2 组合注入关系图：bus ← PublicBlackboard + IsolationGuardPort）
- [ ] Subtask 0.2: 定义领域异常契约（460/461/462 三异常——reason 闭集 + context 键 + HTTP 映射 504/409/500）
- [ ] Subtask 0.3: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_sap_protocol.feature`（14 场景：AC-1×3[**v1.1.0 消歧——创建期 AC-1.3 被矩阵两行引用**：AC-1.1=单播四类型+BROADCAST 全员送达（分发面合一）/ AC-1.2=优先级出队（乱序+同级 FIFO）/ AC-1.3=校验面+关闭态 461] + AC-2×3[关联/超时/默认与并发] + AC-3×3[MVCC 真实 Redis/449 真实链/零写入与写失败] + AC-4×2[序列化/接线] + AC-5×2[传递与序列化 P95/并发] + 收尾×1）
- [ ] Subtask 0.4: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_sap_protocol.py`（三属性分档表 docstring + @scenario 绑定 + context/event_loop/_run_async 三件套[**逐文件自定义**——非 conftest 提供，5-9/5-10 验收文件同款] + **延迟 import 钦定（v1.1.0）**：模块顶部仅 stdlib+pytest+pytest_bdd；本 Story 新交付模块[bus/sap_exceptions/集成常量与 helper]一律**步骤函数体内 import**——Task 0-4 窗口期为运行期 ModuleNotFoundError 逐场景 failed 非 collection error[5-10 test_acceptance_checkpoint_evaluation.py L1729/L1737 函数体内 import 集成常量先例] + Redis 探测 skip + AC-3 三场景函数级 `@pytest.mark.redis`[AC-5 marker 分档钦定]）
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证——逐场景 failed 非 collection error）
- [ ] Subtask 0.6: 定义链路接线断言清单（三件——Task 0 完成标志项）
- [ ] Subtask 0.7: **留项处置两条裁定落档**（deferred-work.md 注记：R1-DF2[L169] + OD-4·P3[L242] 锚位顺延至 Epic 6 首个事件消费 Story——OD-6 论证 + 消费基建缺失四件调研结论锚[poller 宿主未部署/RabbitMQConsumer 零注册/handler 注册键语义未对齐/realtime start 零调用]供未来专项立项输入）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] deferred-work.md 两条注记落档

---

### Task 1: SAP 异常三件（460/461/462）+ 注册四件套

**关联 AC:** AC-1（校验面 461）/ AC-2（超时 460）/ AC-3（写失败 462）

#### TDD 循环 A：sap_exceptions.py 三异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_sap_exceptions.py`（三异常：构造/属性/code 唯一/to_dict/context dict[correlation_id+timeout_seconds / reason 闭集 / conversation_id]/cause 链/frozen 继承链[SystemException/BusinessException 基类断言]） |
| 🟢 绿 | 实现 `src/domain/exceptions/sap_exceptions.py`（三异常——evaluation_exceptions.py 构造风格模板：领域参数在前 + `message: str \| None = None`[缺省回落类属性静态文案——v1.1.0 勘误：创建期「message 必填」与模板不符] + `cause: Exception \| None = None`[三异常统一显式形参——460/462 传递、461 预留] + context_extra 合并；SAPTimeoutError 带 correlation_id: str/timeout_seconds 必填形参；SAPBusStateError 带 reason 闭集校验[非法 reason → `EntityValidationError` 携 `context={"field": "reason"}`——**ArchiveStorageError._VALID_LAYERS 先例**（archive_exceptions.py L102-108），v1.1.0 钦定：创建期未定拒绝异常，`raise ValueError` 会击穿红线]；SAPBlackboardWriteError 带 conversation_id） |
| 🟡 变异 | context 键删一个 → to_dict 断言红；reason 闭集删一值 → 闭集校验用例红 → 还原 |
| 🔄 重构 | 注册三动作：`_code_ranges.py`（CODE_RANGES `"sap": (460, 469)` + `_CLASS_TO_SUBDOMAIN` 三行 + 段注释；**R2 继承链 allowlist 无需加 sap 条目**——直接继承 SystemException/BusinessException 基类同 evaluation/agent 先例，MRO 跳过抽象基类自动通过）+ `domain/exceptions/__init__.py` 导出 + `exception_handlers.py` EXCEPTION_HTTP_MAP 三行（460→504/461→409/462→500）+ `sisys-uni-exception-design.md` §3.3.2 两处更新 + `test_exception_handlers.py` **两处同步**（expected_types 追加三码 + 文件头部 import 块追加三类——v1.1.0 补：穷举等值断言漏任一处即红） |

- [ ] Subtask 1.1: 🔴 红 — 三异常失败测试
- [ ] Subtask 1.2: 🟢 绿 — sap_exceptions.py 实现
- [ ] Subtask 1.3: 🟡🔄 变异实证 + 注册四件套 + 文档联动

**完成标准/Definition of Done:**
- [ ] `poetry run pytest tests/unit/domain/exceptions/ tests/unit/interfaces/api/test_exception_handlers.py -v` 全绿（含自动 8 项）
- [ ] grep `EXCEPTION_46[012]` src/ 零碰撞

---

### Task 2: SAPBus 协议 + InProcessSAPBus 核心（分发/优先级/校验/序列化）+ 组合根注册 + 契约测试

**关联 AC:** AC-1（除请求-响应外全部）/ AC-4（序列化 + 接线）

#### TDD 循环 A：总线核心（send/subscribe/优先级/校验面/close）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/sap/test_bus.py` 第一批（TestUnicast 四类型 15 字段全等+十键点名 / TestBroadcast 三接收方全员 / TestPriorityOrder **六条乱序**[四级各一 + 2×NORMAL 同级对——v1.1.0 补：四级互异构造下同级 FIFO 不可观测]：插队 + 同级 FIFO 双断言 / TestValidationFace 未注册 + 非 UUID sender + 非 UUID receiver + 组合双向 + 关闭态 461 参数化 / TestAsyncHandler 串行保序 + **handler 异常 deliver-continue**[首条抛异常后续仍送达] / TestSubscribeFace 重复订阅覆盖 + subscribe 非 UUID 拒绝——`_StubBlackboard`/`_RecordingIsolationGuard` 手写替身；**红形态注记（v1.1.0）**：本文件顶部 import 不存在的 bus.py → collection error 形态的红**合法**[TDD 单元红非验收面——Task 0.5 红线仅约束验收文件]，绿阶段同 Task 消除） |
| 🟢 绿 | 实现 `src/interfaces/sap/bus.py`（`SAPBus` Protocol[@runtime_checkable] 四方法[签名见 Task 0.1 钦定] + `InProcessSAPBus`：订阅表 dict[receiver_id→handler——重复 subscribe 覆盖]+消费任务表[per-receiver 串行消费循环——**handler 异常 try/except 捕获 log warning 后继续下一条**[deliver-continue 钦定]] + per-receiver 优先级队列[heapq——(priority_rank, seq, message) 序计数器破平局保同级 FIFO] + `_validate(message)` 校验面[**开闭态首位**→UUID 解析[sender+receiver 双侧，"broadcast" 豁免]→BROADCAST 组合→注册检查] + `send` 流程[校验→黑板桥位[Task 4 前占位 pass——黑板桥 Task 4 同文件补齐]→入队] + `close`[幂等 + 取消消费任务 + 清空队列 + 挂起 Future set_exception(461 bus_closed)]）；`src/interfaces/sap/__init__.py` 追加导出 |
| 🟡 变异 | 优先级出队改 FIFO 无优先级 → 插队断言红；组合校验删单向 → 参数化红；close 后状态标志删 → 关闭态用例红 → 还原 |
| 🔄 重构 | docstring（协议语义/积压口径/MVP 单进程前提 OD-4 注记/wire format 注记）+ ruff/mypy |

#### TDD 循环 B：序列化 + 组合根注册 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | test_bus.py 第二批（TestSerialization 15 字段满载往返逐字段 + 坏 JSON pydantic 透传[raises ValidationError 无包装]）+ `tests/contracts/test_port_contract_sap_bus.py`（11 维度 + REQUIRED_METHODS + _DummyResolver 分发两依赖 + **降级防护**：Dummy 未注册依赖 → resolve("sap_bus") 抛 ConfigurationError——fail-fast 非 None 降级） |
| 🟢 绿 | bus.py serialize/deserialize（模块级函数——`SAPMessage.model_dump_json`/`model_validate_json` 薄封装）+ 模块级常量 `SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS = 300.0`（AC-2 无条目兜底——Task 3 消费）；composition_root.py `# === Story 5.11 ===` 区段（register_port sap_bus——lambda resolver：`try: resolve("public_blackboard") + resolve("isolation_guard_service") 注入 except (KeyError, RuntimeError) as e: raise ConfigurationError(...) from e`[翻译形态钦定——AC-4]） |
| 🟡 变异 | serialize 键改错 → 往返断言红；PortSpec tags 改错 → 契约断言红 → 还原 |
| 🔄 重构 | 对齐 Epic 5 区段形态（注释块全中文） |

- [ ] Subtask 2.1: 🔴 红 — 总线核心失败测试（第一批）
- [ ] Subtask 2.2: 🟢 绿 — bus.py 实现 + __init__ 导出
- [ ] Subtask 2.3: 🔴🟢 序列化 + 契约测试红绿
- [ ] Subtask 2.4: 🟡🔄 变异实证（三锚）+ 重构（docstring 四注记 + 区段形态）

**完成标准/Definition of Done:**
- [ ] 总线核心 + 序列化 + 契约全绿
- [ ] resolve("sap_bus") 可达 + 注入链断言
- [ ] 接口层新文件行覆盖 ≥85%

---

### Task 3: 请求-响应关联——wait_for_response + Future 索引 + 超时 460

**关联 AC:** AC-2（全部）

#### TDD 循环 A：关联与超时

| 阶段 | 动作 |
|------|------|
| 🔴 红 | test_bus.py 第三批（TestRequestResponse：关联送达[wait 返回 correlation 匹配——OD-9 锚约定 + 请求方 handler 双重送达] / TestTimeout：短超时 460 三段式[raises+code+context correlation_id: str/timeout_seconds] + 超时后索引清理[迟到 RESPONSE 回发零崩溃零 resolve] / **TestDuplicateResponse 正常双响应幂等**[v1.1.0 补：同 correlation 第二条 RESPONSE 零 InvalidStateError——幂等 resolve 守卫] / TestNoWait 默认无等待 + 未挂起 correlation 超时路径[**含 None 不传参兜底 300.0 口径**] / TestConcurrentWait 两对并发各自 resolve 键控隔离 / timeout 默认值取请求消息 timeout_seconds 口径 / **计时锚点用例**[wait 调用时刻起算——响应方延迟回发下 send→wait 间隔不计入]） |
| 🟢 绿 | bus.py 实现 `wait_for_response(correlation_id: UUID, timeout_seconds: float \| None = None)`（挂起 Future 表 dict[UUID→Future]；RESPONSE send 时 correlation_id 在表 → **幂等 resolve**[`if not future.done(): set_result`——重复响应 log-ignore，条目保留至超时清理或 close 非 resolve 移除——AC-2④ 生命周期钦定]；双动作：正常入队送达 + resolve——DC-10]；超时 `asyncio.wait_for`[**计时锚 = wait 调用时刻 duration 语义**] → 清理条目 → 抛 SAPTimeoutError 460[context 双键，correlation_id 统一 str() 换算]；**默认 timeout 钦定实现**：`requires_response=True` 的消息 **send 时在登记表登记 `message_id → (Future, timeout_seconds)`**——wait_for_response 不传 timeout 时从登记条目取请求消息的 timeout_seconds[300 默认]；**无条目 + None → `SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS = 300.0` 兜底**[Task 2 循环 B 交付的模块常量]；登记表与挂起 Future 表同构复用[send 预建 Future + 元数据，wait 只 await]——docstring 注记此口径与 OD-9 锚约定） |
| 🟡 变异 | resolve 动作删[只入队不 resolve] → 关联送达用例红；超时清理删 → 迟到响应用例红[Future 已 done 二次 set_result InvalidStateError 暴露]；幂等守卫删[future.done() 检查移除] → 双 RESPONSE 用例红[InvalidStateError 浮现——v1.1.0 补]；460 改 460 秒级 sleep 死等 → 短超时用例超时红 → 还原 |
| 🔄 重构 | docstring（关联链语义/interface-design §7.5 流程对应/迟到防御/键控隔离）+ ruff/mypy |

- [ ] Subtask 3.1: 🔴 红 — 关联/超时/清理失败测试
- [ ] Subtask 3.2: 🟢 绿 — wait_for_response 实现
- [ ] Subtask 3.3: 🟡🔄 变异实证（三锚：resolve/清理/超时抛出）+ 重构

**完成标准/Definition of Done:**
- [ ] AC-2 六项验证标准全绿
- [ ] 覆盖率：wait_for_response 分支 100%（resolve/超时/清理/默认值）

---

### Task 4: 黑板桥——守卫集成 + MVCC 写入 + fail-loud 462

**关联 AC:** AC-3（替身面；真实 Redis/真实链归 Task 5 集成）

#### TDD 循环 A：黑板桥

| 阶段 | 动作 |
|------|------|
| 🔴 红 | test_bus.py 第四批（TestBlackboardBridge：visible=True → `_StubBlackboard` post 调用断言[conversation_id==str(msg.conversation_id) + agent_id==sender_id + content 四键投影] + `_RecordingIsolationGuard` 调用断言[actor/target/resource=BLACKBOARD/operation=WRITE 四参数——BROADCAST 形态 target==actor] / visible=False → 零 post / 守卫拒绝[替身抛 449] → **透传不包装**[raises IsolationOperationForbiddenError 原类型] + 消息不投递 / `_FailingBlackboard` post 返 0 → SAPBlackboardWriteError 462[context conversation_id + cause 链] + 消息不投递 / 守卫 443/447 族透传参数化） |
| 🟢 绿 | bus.py 补黑板桥（send 流程校验后入队前：`if message.blackboard_visible:` → `await guard.ensure_agent_access(uuid(sender), uuid(receiver if != "broadcast" else sender), BLACKBOARD, WRITE)`[拒绝原样上抛] → `version = await blackboard.post(str(conversation_id), sender_id, content 四键投影)` → `if version == 0: raise SAPBlackboardWriteError`[OD-7——post 返 0 检测]；**次序钦定：先黑板后入队**——黑板承诺面失败则整条 send 失败） |
| 🟡 变异 | visible 条件反转 → False 零 post 断言红；version==0 检测删 → 462 用例红；次序对调[先入队后黑板] → 不投递断言红 → 还原 |
| 🔄 重构 | docstring（OD-7 fail-loud 论证 / 449 族透传职责边界 / content 四键投影契约 / conversation_id str 换算[message.py L48 归 5.11 注记兑现]）+ ruff/mypy |

- [ ] Subtask 4.1: 🔴 红 — 黑板桥失败测试（六场景）
- [ ] Subtask 4.2: 🟢 绿 — 黑板桥实现
- [ ] Subtask 4.3: 🟡🔄 变异实证（三锚：条件/检测/次序）+ 重构

**完成标准/Definition of Done:**
- [ ] 黑板桥六场景全绿（替身面）
- [ ] 449 透传零包装断言（异常类型原样）
- [ ] 覆盖率：黑板桥分支 100%

---

### Task 5: 集成测试与性能——真实 Redis 黑板 + 真实链 449 + 三锚 + xdist 组

**关联 AC:** AC-3（真实服务面）/ AC-5（全部）

> **套件型豁免条款（5-9/5-10 先例）**：本 Task 是验证型测试套件（对 Task 1-4 已交付行为做真实服务与计时验证）——首跑即绿，红阶段由 Task 0 验收红前置承担；断言活性由关键断言的变异实证承担（Subtask 5.3 变异锚：常量单源改错值 → 验收 AC-5 import 消费断言红）。

#### 集成与性能实现

- [ ] Subtask 5.1: `tests/integration/test_integration_sap_protocol.py`——TestRealRedisBlackboardBridge（真实 RedisAdapter+RedisPublicBlackboard+InProcessSAPBus 装配：①visible=True 两次 send → 版本递增 + get 读回 content.message_id 匹配 ②真实隔离链 L4 拒绝[真实 Redis + 实例化 CEO Agent[agent_instantiation 链] + 真实 IsolationGuardPort → 449 透传 + 黑板 get 空] ③自清理[teardown delete 黑板键+版本键]——conversation_id UUID 前缀 + Redis 探测 skip 动态跳过）
- [ ] Subtask 5.2: TestSAPPerformance（**类级 `pytest.mark.xdist_group("sap-protocol-perf")`——不挂 redis**[AC-5 marker 分档钦定：进程内性能零 Redis 依赖]；常量单源 SAP_DELIVERY_P95_LIMIT_SECONDS=0.2 / SAP_SERIALIZATION_P95_LIMIT_SECONDS=0.05 / SAP_CONCURRENCY_FLOOR=50；`_PERF_CACHE` 单 key `sap_perf` 载三指标 summary dict 的 cache-or-compute helper；warmup 1 + 20 采样 quantiles(latencies, n=20)[18] exclusive 口径 docstring；正向锚收到计数==21；并发 50 gather 全送达 + 队列清空）；文件级 `pytestmark=[pytest.mark.integration]`，TestRealRedisBlackboardBridge 类级加挂 `pytest.mark.redis`
- [ ] Subtask 5.3: 变异锚实证（常量单源改错值 → 验收 import 消费断言红 → 还原）+ 全仓 xdist 组 grep 断言（sap-protocol-perf 与 15 组互异）
- [ ] Subtask 5.4: 口径声明落 docstring（进程内口径/绊线定位/20 样本方差/序列化满载四注记——5-8 DC-8④ 形态）+ 验收 AC-5.* 场景接线（委托计时消费——import 集成常量与 helper 禁双真源）

**完成标准/Definition of Done:**
- [ ] 真实 Redis 三场景全绿（不可用环境 skip 且 CI 绿）
- [ ] 三锚达标 + 正向锚 + 变异锚
- [ ] xdist 组互异断言

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-4（架构合规面）

> **性质说明：** 本 Task 是 **SDD 规范验证测试**，非 TDD 单元测试。

#### 架构验证测试实现

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_arch_sap_protocol.py`——验证器 A：`src/interfaces/sap/bus.py` 第三方 import 白名单（允许集 {pydantic}——黑名单断言：forbidden ∩ modules == ∅；asyncio/logging/uuid/dataclasses 等标准库白名单天然过）
- [ ] Subtask 6.2: 验证器 B：组合根外零实例化（`InProcessSAPBus(` 构造点 grep——仅 composition_root.py + tests/）+ domain 触碰面收窄（SAPTimeoutError/SAPBusStateError/SAPBlackboardWriteError 仅在 exceptions 注册三件[sap_exceptions.py/_code_ranges.py/__init__.py]内定义）+ **events 零触碰**（event_channels.yaml/ChannelRouter/domain/events 零 SAP 条目——SAP 非领域事件契约）+ 依赖方向（bus.py import src.application.ports 断言合法 + application/infrastructure/domain 零 import interfaces.sap——与 test_arch_agent_workflow.py 既有守护互补）
- [ ] Subtask 6.3: 验证器 C：bus.py 静态锚（SAPBus Protocol 四方法存在 + `@runtime_checkable` 装饰 + blackboard_visible 条件分支 + ensure_agent_access 调用 + version==0 检测——AST/grep 双形态）+ 零抑制注释（交付文件四件[bus.py/sap_exceptions.py/组合根区段/契约测试] noqa/type: ignore 零命中）+ 循环依赖检测用 ruff/isort 既有钩子（不引入新工具）
- [ ] Subtask 6.4: 运行完整测试套件 + `mypy .` 全仓（含 tests/——5-9 教训）+ ruff 全清

**完成标准/Definition of Done:**
- [ ] 三验证器全绿 + 任何违规测试失败
- [ ] mypy 全仓零错 + ruff 全清

---

### Task 7: 开发结束验收测试

**关联 AC:** 全 AC 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | feature 收尾场景（完成清单逐项——src 七件 + tests 八件存在性） |
| 🟢 绿 | py 步骤实现（文件存在性 + 关键符号断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 7.1: 场景 1 — 验证 `src` 完成清单（bus.py/sap_exceptions.py/组合根区段/__init__ 导出/注册三动作/文档联动两件——**口径注记 v1.1.0**：「src 七件」= 2 新建 + 5 修改的生产/注册面文件；sisys-uni-exception-design.md 与 deferred-work.md 两文档件不计入七件数）
- [ ] Subtask 7.2: 场景 2 — 验证 `tests` 完成清单（unit 两件 + contracts 一件 + integration 一件 + architecture 一件 + acceptance 两件 + exception_handlers 追加）
- [ ] Subtask 7.3: 运行开发结束验收测试确认通过 + 全量 `poetry run pytest tests/ -n 8` 并行绿
- [ ] Subtask 7.4: `poetry run ruff check src/ tests/` + `poetry run mypy .` 收尾校验 + 零抑制 grep 三连（noqa/type: ignore/pylint: disable）+ 禁 AI 署名 grep

**完成标准/Definition of Done:**
- [ ] 完成清单逐项验证确认
- [ ] 全量测试 + 质量门禁全绿
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) + [`interface-design.md §7`](../../../docs/architecture/interface-design.md)

- **架构模式:** 六边形架构；SAP 是**接口层横向协议**（5-3 职责矩阵裁定——非领域事件非事件总线族；bus.py 落位 interfaces/sap/ 是 architecture.md L2169-2172 规划钦定）
- **设计约束:** 领域层零依赖（sap_exceptions.py 纯标准库）；R2 组合注入（SAPBus ← PublicBlackboard + IsolationGuardPort 两应用层基础端口——interfaces→application 合法面）；组合根唯一注册；**SINGLETON 有状态总线**（订阅表+索引+队列跨调用共享）
- **接口治理:** PortSpec 元数据（sap_bus / v1.0.0 / SINGLETON / owner=platform / tags）；fail-fast 装配（两依赖 resolve 失败 raise ConfigurationError——无 None 降级消费方）
- **技术栈:** Python 3.11+ 标准库（asyncio/heapq/uuid/logging）+ pydantic v2（SAPMessage 既有）——**零新运行时依赖**（5.7 OD-1 家族原则第五 Story 延续）

### 关键架构决策 Key Design Decisions

| # | 决策 | 理由 | 备选（弃） |
|---|------|------|-----------|
| DC-1 | 进程内 asyncio 总线（OD-4） | MVP 单进程前提；请求-响应 Future 关联零网络最自然；零新依赖；wire format 交付保演进稳定 | Redis pub/sub（弃——fire-and-forget 无关联语义）；RabbitMQ（弃——引入事件基建纠缠+OD-6 顺延项纠缠） |
| DC-2 | bus.py 落位 `src/interfaces/sap/` | architecture.md L2172 规划钦定（v1.1.0 勘误）+ 5-3 职责矩阵延续 + 守护测试在位 + 依赖方向合法（interfaces→domain/application） | application/ports（弃——SAPMessage Pydantic 载体在 interfaces，application 依赖它击穿依赖矩阵） |
| DC-3 | 黑板桥 = 守卫 + post + fail-loud（OD-7） | §7.6 V1「跨 Agent 数据访问需授权」经 ensure_agent_access(BLACKBOARD, WRITE) 承载；449 族透传保 5-5 分码语义；post 返 0 检测抛 462 | 降级 warning（弃——BROADCAST 主语义静默丢协作数据）；包装 449 为 SAP 异常（弃——分码语义破坏） |
| DC-4 | per-receiver 优先级出队（heapq/四层队列 + 序计数器） | 四级优先级是协议语义（URGENT 插队）；同级 FIFO 保时序公平；积压=队列长度可观测 | 全局单队列（弃——接收方隔离破坏）；send 内联分发（弃——无从插队） |
| DC-5 | 请求-响应 = Future 索引 + wait_for_response + 460 | interface-design §7.2 L1290-1291 API 形态钦定；correlation_id 键控；超时清理防泄漏；迟到防御 | 轮询队列（弃——忙等）；handler 回调直传（弃——等待方无 await 原语） |
| DC-6 | SINGLETON + fail-fast 装配 | 有状态总线跨 send/wait/subscribe 共享（状态即功能——5-9 DC-6/5-10 DC-7 同族）；无 None 降级消费方则 fail-fast（与 5.6/5.8/5.9 可选依赖降级族差异：那些是可观测附加面，SAP 总线是功能主面） | SCOPED（弃——每 resolve 新总线订阅表清零）；TRANSIENT（弃——同） |
| DC-7 | sap 子域 460-469 新段三异常 | agent 段满 + 语义独立（第六段先例）；460 business[交互超时可处理] / 461 system[协议契约违规] / 462 system[基础设施写失败] 分语义归属 | 复用 MessageBusError（弃——事件总线与 SAP 协议子域分立，debate 420 段先例）；evaluation 段借码（弃——语义不同域） |
| DC-8 | 校验面单点收敛 send：UUID 标识 + BROADCAST 组合 + 注册检查 + 关闭态（OD-5/OD-8） | Schema 层无跨字段校验（5-3 交付形态不动）；send 是协议唯一入口；fail-loud 防语义误用 | Schema 加校验器（弃——破坏 5-3 交付面）；各消息类型分散校验（弃——漂移面） |
| DC-9 | 序列化 = Pydantic v2 原生薄封装（serialize/deserialize 模块函数） | wire format 稳定契约（NFR-INT-05 基线）；零手写序列化漂移面；坏 JSON pydantic 透传 | 手写 to_dict/from_dict（弃——15 字段漂移面）；msgpack（弃——无跨语言需求零收益依赖） |
| DC-10 | RESPONSE 双动作（入队送达 + Future resolve） | 等待原语与送达语义正交——请求方 handler 也收到 RESPONSE 是正常单播；wait_for_response 是独立等待面；**V2 知悉注记（v1.1.0）**：resolve 不校验 RESPONSE.sender == 原请求 target（进程内可信域 MVP 可接受——任意参与方可 resolve 他人 correlation；响应者身份绑定归 V2 签名中间件面 middleware.py） | resolve 替代入队（弃——送达语义丢失）；仅入队无 resolve（弃——等待原语失效） |
| DC-11 | 消费任务 deliver-continue + correlation 条目「保留至超时/close」（v1.1.0） | handler 异常捕获 log warning 后继续出队（Actor supervision 隔离惯例——单条崩溃不冻结接收方队列）；resolve 不移除条目 + 幂等守卫（`future.done()` 检查）——「resolve 即移除」会使 resolve 后才 wait 的等待者伪超时、无守卫则正常双响应二次 set_result 崩溃（JMS 重复投递幂等惯例） | 异常传播终止消费任务（弃——队列永久冻结）；resolve 即移除条目（弃——后置 wait 伪 460） |
| DC-12 | lambda fail-fast 显式翻译 `except (KeyError, RuntimeError) → ConfigurationError from e`（v1.1.0） | resolver/替身对未注册名抛 KeyError——契约测试断言 ConfigurationError 依赖 lambda 内显式翻译；既有组合根 lambda 均零包装（KeyError 自然传播），本 Story fail-fast 语义是自造形态必须落文字（防 dev 按字面直写使断言红错位） | 让 KeyError 自然传播（弃——与 AC-4 断言 ConfigurationError 不符且错误语义裸露）；resolve_optional→None 降级（弃——DC-6 已弃） |

### 风险登记

| # | 风险 | 缓解 |
|---|------|------|
| 1 | **真实 Redis 环境依赖**（AC-3 集成/验收 + 449 真实链） | 场景级 TCP ping 探测 → pytest.skip 动态跳过；替身面（Task 4 单测）全绿不依赖 Redis；CI 无 Redis 绿 |
| 2 | **异步消费任务的测试确定性**（优先级断言依赖队列清空时机） | 队列清空等待用 asyncio.Event/带超时条件等待（上限 5s）；禁 sleep 死等；乱序注入在 subscribe 后一次性灌入再统一断言；**deliver-continue 钦定（v1.1.0）消解「handler 异常冻结队列 → 等待死等」形态**——单条 handler 崩溃不冻结队列，清空等待上限恒可达 |
| 3 | **SINGLETON 总线跨场景污染**（订阅表/索引/Future 残留） | 每场景手工新实例（验收/集成不走 resolve）；性能场景同实例连续采样；close 显式清理 |
| 4 | **Future 跨 loop 陷阱**（bus 与测试不同 loop） | 模块级 event_loop fixture + _run_async 同 loop 驱动；bus 内 Future/Event 延迟到调用时创建（同 loop）；验收 conftest 形态延续 |
| 5 | **449 真实链装配成本**（实例化 Agent + 隔离初始化全链） | 复用 5-5 验收装配形态（test_acceptance_agent_triple_isolation.py L686-718——真实链先例逐字参照）；Redis 不可用 skip |
| 6 | **黑板版本键泄漏**（RedisPublicBlackboard 版本键独立于内容键） | teardown 双键清理（blackboard:{conv} + blackboard:{conv}:version——build_key 形态核对）；只清自己创建的 UUID 前缀键 |
| 7 | **_PERF_CACHE 与 xdist 分发**（缓存命中依赖同 worker） | 集成/验收逐字同组 sap-protocol-perf（loadgroup）；组名 15 组互异 grep 断言；「命中或首次采样」形态 |
| 8 | **组合根区段与既有注册冲突**（sap_bus 名冲突/依赖 resolve 顺序） | 创建期 grep 实证 sap 名零占用；lambda 内 resolve 两依赖均为既有注册（public_blackboard L818 / isolation_guard_service L2908——bootstrap 顺序在 sap_bus 之前即可，组合根顺序无关性由 resolver 惰性 resolve 保证） |
| 9 | **协议语义与 Epic 9 演进冲突**（wait_for_response 形态/优先级语义被编排层推翻） | 端口契约 v1.0.0 + PortSpec compatibility 预留；wire format 稳定（DC-9）；OD-3 范围切分显式——Epic 9 在协议层之上叠加零返工；若需演进走 contract_gate 兼容检查 |
| 10 | **异常 HTTP 映射语义争议**（460→504/461→409 非惯例 500） | 语义就近映射先例（DebateLowDivergenceError 422→422）；零 REST 消费方现状下映射是预留面——sisys-uni-exception-design.md §3.3.2 注记说明；7-2 REST 面立项时可评审调整 |

### 项目结构说明 Project Structure

```
src/
├── application/ports/
│   ├── public_blackboard.py        # 零改动（直接消费——R2 注入）
│   └── isolation_guard.py          # 零改动（直接消费——R2 注入）
├── domain/
│   ├── events/                     # 零改动（enums.IsolationLevel 复用；SAP 非领域事件）
│   ├── exceptions/
│   │   ├── sap_exceptions.py       # ★ 5.11 新建：SAPTimeoutError 460 / SAPBusStateError 461 / SAPBlackboardWriteError 462
│   │   ├── __init__.py             # ▲ 修改：三异常导出
│   │   └── _code_ranges.py         # ▲ 修改：CODE_RANGES "sap": (460, 469) + _CLASS_TO_SUBDOMAIN 三行 + 段注释
│   └── value_objects/isolation_access.py  # 零改动（IsolationResource.BLACKBOARD/AccessOperation 复用）
├── infrastructure/
│   └── storage/redis/public_blackboard.py  # 零改动（直接消费——post 返 0 语义是检测点非修改点）
├── interfaces/
│   ├── sap/
│   │   ├── message.py              # 零改动（5-3 交付直接消费）
│   │   ├── types.py                # 零改动
│   │   ├── bus.py                  # ★ 5.11 新建：SAPBus Protocol + InProcessSAPBus + serialize/deserialize
│   │   └── __init__.py             # ▲ 修改：SAPBus/InProcessSAPBus 导出 + docstring bus 注记更新
│   └── api/exception_handlers.py   # ▲ 修改：EXCEPTION_HTTP_MAP 460→504 / 461→409 / 462→500
└── composition_root.py             # ▲ 修改：# === Story 5.11 === 区段（sap_bus 注册）

tests/
├── unit/
│   ├── interfaces/sap/
│   │   ├── test_message.py         # 零改动（5-3 资产）
│   │   └── test_bus.py             # ★ 新建（四批：核心/序列化/请求响应/黑板桥）
│   ├── domain/exceptions/test_sap_exceptions.py  # ★ 新建
│   └── architecture/test_arch_sap_protocol.py    # ★ 新建（验证器 A/B/C）
├── contracts/test_port_contract_sap_bus.py       # ★ 新建（11 维度）
├── integration/test_integration_sap_protocol.py  # ★ 新建（真实 Redis 黑板 + 449 真实链 + 性能三锚 + xdist 组）
├── acceptance/
│   ├── test_acceptance_sap_protocol.feature      # ★ 新建（14 场景）
│   └── test_acceptance_sap_protocol.py           # ★ 新建
└── unit/interfaces/api/test_exception_handlers.py # ▲ expected_types 追加三码
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5-10 CheckpointWithEvaluation 集成](./5-10-checkpoint-with-evaluation-integration.md) + [Story 5-9](./5-9-cusum-drift-detection-recalibration.md)

**关键学习/Key Learnings:**
- 组合根工厂注入与构造参数必须同窗落地（R1-F1 两连教训——本 Story 无主链参数扩展[零 use case 触碰]，但 bus.py 与组合根注册仍需同 Task 同窗：Task 2 循环 B 承载）
- 断言可满足性推演先行（5-9 三个 P0 数学不可满足锚——本 Story 优先级断言[乱序注入+清空后序断言]与并发[50/50 精确计数]均已推演可满足）
- mypy 必须 `mypy .` 全仓含 tests/（5-9 Task 6.4 教训）
- 嵌入式可观测组件定位哲学（5.7-5.10 同族）：本 Story 是嵌入式协议基础设施——无 API/CLI 面、零新领域事件、span 零触碰（SpanAttributeKeys 14 键契约不动——SAP 总线无 span 键需求，不扩 5.7 键表）
- 附加面 vs 主面的降级哲学分界（5-10 DC 哲学的反向应用）：评估历史是附加面降级；SAP 黑板可见性是 BROADCAST 主语义面 fail-loud（OD-7——本 Story 对 5-10 哲学的边界细化而非矛盾）
- 手写零 IO 替身族 + 真实服务场景双轨（验收禁 mock 红线的标准解法）
- 行号锚随 dev 漂移——以 grep 定位为准（5-9 R3-1）

**应用到本故事/Applied to This Story:**
- [x] 同窗纪律：bus.py 实现 + __init__ 导出 + 组合根注册同 Task 2（循环 B）
- [x] 断言可满足性：优先级/并发/超时/版本递增四类断言创建期推演（AC 各 Then 节内嵌口径）
- [x] mypy 全仓口径写入 Task 6.4 与质量门禁
- [x] 嵌入式定位写入范围边界（REST/CLI/事件三 ❌ 行——v1.1.0 勘误：创建期误记「span 四 ❌ 行」，span 论述在 Lessons 正文非范围边界行）
- [x] fail-loud vs 降级分界显式论证（OD-7——与 5-10 哲学的关系自洽）
- [x] 替身 + 真实服务双轨（_StubBlackboard/_RecordingIsolationGuard/_FailingBlackboard + 真实 Redis/真实隔离链）
- [x] 行号锚漂移知悉（「现有代码继承」表尾注——dev 时 grep 重定位）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code） |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-29 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1904-1947/L1447/L519/L1454） |
| **架构文档** | `docs/architecture/architecture.md`（L2169-2172/L102/L185） + `docs/architecture/interface-design.md`（§7 L1178-1380） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/5-10-checkpoint-with-evaluation-integration.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L169 R1-DF2 / L242 OD-4·P3） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` L1904-1947 提取
- [x] 架构约束从 `architecture.md` + `interface-design.md` §7 提取
- [x] 前一个故事学习经验整合（5-10/5-9）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 多 Agent 并行调研（四视角：SAP 现有代码 / Epic5 Agent 体系 / 事件总线消费基建 / 测试模板基建——结论全部落入「现有代码继承」与 OD/DC）
- [x] deferred-work 钦定两项留项处置方案落档（OD-6——Task 0.7 执行）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-11-sap-protocol-support.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/interfaces/sap/bus.py` - SAPBus Protocol + InProcessSAPBus + 序列化
- `src/domain/exceptions/sap_exceptions.py` - 三异常（460/461/462）
- `tests/unit/interfaces/sap/test_bus.py` - 总线单测（四批）
- `tests/unit/domain/exceptions/test_sap_exceptions.py` - 异常单测
- `tests/contracts/test_port_contract_sap_bus.py` - 端口契约测试
- `tests/integration/test_integration_sap_protocol.py` - 集成 + 性能三锚
- `tests/unit/architecture/test_arch_sap_protocol.py` - AST 架构验证器
- `tests/acceptance/test_acceptance_sap_protocol.feature` - Gherkin 场景（14 场景）
- `tests/acceptance/test_acceptance_sap_protocol.py` - BDD 步骤实现

**待修改的文件/To Be Modified:**
- `src/interfaces/sap/__init__.py` - SAPBus/InProcessSAPBus 导出 + docstring 注记更新
- `src/domain/exceptions/__init__.py` - 三异常导出
- `src/domain/exceptions/_code_ranges.py` - sap 子域段注册
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 三行
- `src/composition_root.py` - Story 5.11 区段（sap_bus 注册）
- `docs/architecture/sisys-uni-exception-design.md` - §3.3.2 编码分配表 + 子域范围表
- `tests/unit/interfaces/api/test_exception_handlers.py` - expected_types 追加
- `_bmad-output/implementation-artifacts/deferred-work.md` - 两条留项注记（Task 0.7）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.11 |
| **Story Key** | 5-11-sap-protocol-support |
| **File** | `_bmad-output/implementation-artifacts/stories/5-11-sap-protocol-support.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 5: Agent 协作系统 |
| **价值组** | 单 Agent 战略规划能力（SAP 协议面——迁移自 Epic 4 Story 4.8） |
| **优先级** | P1-11（执行序）；FR-ST-08 P2/V1（功能等级） |
| **覆盖 FR** | FR-ST-08（SAP 协议实现——协议层）；FR-IF-03 运行时兑现（Schema 5-3 已交付）；NFR-IF-03（性能三锚）；NFR-INT-05（wire format 兼容基线） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-5 + 验证标准清单）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 + SAP 接口层横向协议定位 + 依赖方向）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（5-10/5-9 七条）
5. [x] Sprint status synced to `ready-for-dev`
6. [x] 范围边界 21 行精确切分（本 Story 9 行 ✅ / 后续归属 12 行 ❌ 含 Epic 9/V2/OD-6 顺延/审计日志语义错位——v1.1.0 勘误：创建期误记「17 行 = 8✅ + 9❌」，实测 20 行 = 9✅ + 11❌，v1.1.0 补审计日志行后为 21 = 9✅ + 12❌）
7. [x] 偏离声明 9 项（v1.1.0 新增 OD-9——创建期 8 项）+ 关键决策 12 项（v1.1.0 新增 DC-11/DC-12——创建期 10 项）+ 风险登记 10 项

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 同级 FIFO 断言构造不可满足（AC-1 When③ 仅四条互异优先级消息——无同级对可观测） | P1 | When③ 扩为六条（四级各一 + 2×NORMAL 同级观测对）；Then③/验证清单/Task 2 红/矩阵四联位同步（R1-F1） |
| 2 | BROADCAST × blackboard_visible=False 组合未钦定且与 OD-7「核心语义=黑板写」自相矛盾 | P1 | OD-7 正交开关钦定（放行——opt-in 语义，5-3 Schema 默认 False 锁定不可动）+ OD-8③ 组合不校验 + AC-3 零写入边界补 BROADCAST+False 用例（R1-F2） |
| 3 | correlation 条目生命周期两难（resolve 移除与否：保留则双 RESPONSE 崩溃 / 移除则后置 wait 伪超时） | P1 | 钦定保留至超时/close + 幂等 resolve 守卫（future.done()）+ 正常双 RESPONSE 用例 + Task 3 变异锚（R1-F3） |
| 4 | handler 异常冻结队列（消费任务死亡 → 该接收方队列永久冻结） | P1 | deliver-continue 钦定（捕获→log warning 含 message_id→继续出队）+ 用例 + 风险 2 缓解联动（R1-F4） |
| 5 | lambda fail-fast 翻译形态缺失（resolver 抛 KeyError 而非 ConfigurationError——契约测试断言红错位） | P1 | 钦定 `except (KeyError, RuntimeError) → ConfigurationError from e` + import 源 + DC-12（R1-F5） |
| 6 | 范围边界计数三数全错（声称 17=8✅+9❌，实测 20=9✅+11❌） | P2 | 完成总结勘误内联 + 补审计日志 ❌ 行后 21=9✅+12❌（R1-F6） |
| 7 | 验收 AC-1.3 被矩阵两行引用（BROADCAST 与校验面）——14 场景切分未消歧 | P2 | 钦定 AC-1.1=单播+BROADCAST 分发面合一 / AC-1.2=优先级 / AC-1.3=校验面；Task 0.3 与矩阵同步（R1-F7） |
| 8 | timeout 计时锚点未钦定 + 无条目+None 默认值来源空洞 | P2 | 钦定计时锚=wait 调用时刻（duration 语义）+ SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS=300.0 兜底常量（Task 2 循环 B 交付）（R1-F8） |
| 9 | correlation 锚约定与 interface-design §7.2 示意分歧未声明（Epic 9 照示意编码必踩 460） | P2 | 新增 OD-9（锚=REQUEST.message_id，JMS 同款；示意代码非规范）（R1-F9） |
| 10 | reason 闭集成员 invalid_receiver_id 零触发用例（死成员）+ subscribe 侧 UUID 校验未钦定 | P2 | 验证清单补非 UUID receiver 用例（send+subscribe 双侧）+ AC-1 And 订阅语义钦定（R1-F10） |
| 11 | 十键点名/逐字段相等/实例相等性三种强度混写 | P2 | 统一为「15 字段实例全等 + epics 十键逐键 + requires_response/timeout_seconds 显式点名」（R1-F11） |
| 12 | close 语义面未枚举 + 在途等待者结局未定 | P2 | close 动作清单钦定（幂等/取消任务/清空队列/挂起 Future→461 bus_closed）（R1-F12） |
| 13 | Task 2 单测红阶段形态与 Task 0.5 红线隐性双标 | P2 | 钦定单元红允许 collection error 形态（红线仅验收面）——Task 2 红行注记（R1-F13） |
| 14 | 「防内存泄漏」声明过强（未 await 登记条目无清理通道） | P2 | 措辞收窄「等待路径条目清理 + 未 await 条目活至 close 知悉注记」（R1-F14） |
| 15 | reason 闭集校验的拒绝异常未钦定（ValueError 红线邻接） | P2 | 照 ArchiveStorageError._VALID_LAYERS 先例 → EntityValidationError 携 context={"field":"reason"}（R1-F15） |
| 16 | redis marker 分档矛盾（性能类挂 redis 与零依赖自相矛盾 + 验收真 Redis 场景反无 marker） | P2 | 分档钦定：集成类级（TestRealRedisBlackboardBridge 挂 / TestSAPPerformance 不挂）+ 验收 AC-3 三场景函数级（R1-F16） |
| 17 | 覆盖率两处口径不一（整层 vs 新文件）+ 两段式命令缺失 | P2 | 统一整层 ≥85% + 实测基线 89% + 两段式命令落质量门禁（Makefile 陷阱注记）（R1-F17） |
| 18 | §7.6 MVP 行「审计日志写 IsolationSwitchLog」无范围归属（且 OD-5 引其作论据） | P2 | 范围边界补 ❌ 行（语义错位——IsolationSwitchLog 是隔离切换日志非通信日志）（R1-F18） |
| 19 | AC-5 验收 import 集成常量的窗口期形态未钦定（Task 5 才交付集成模块） | P2 | Task 0.4 补 5-10 L1729/L1737 先例括注：步骤函数体内 import（运行期逐场景 failed 非 collection error）（R1-F19） |
| 20 | 行号锚批量勘误（L2170→L2172 ×4 / L1305→L1306 ×2 / L1349→L1339 / L35-36→L28-29 / L63-64→L62-63 / L2681-3074→L2681-3090 ×2 / L60-88→L60-87 / agent_instantiation 路径缺 use_cases/） | P3 | 全部内联「v1.1.0 勘误」标注（9 锚位）（R1-F20） |
| 21 | 零散修正：矩阵 Subtask 对调两处 / SAPBusStateError 补 cause 形参 / AC-2 Given 措辞 / correlation_id 类型口径三处 / Task 0.1 四方法签名级钦定 / 校验次序（开闭态首位）/ SINGLETON captive 依赖注记 / BROADCAST 跨接收方时序+重复订阅覆盖+自收+零订阅边缘钦定 / Task 7 表格行尾管道 / xdist 断言从 AC-4 清单去重 / span 四❌行勘误 / conftest 三件套表述 / message 必填措辞 / 385 先例补引 / test_exception_handlers 两处同步 / R2 allowlist 无需 sap 条款 / 响应方身份 V2 注记 | P3 | 各自内联标注（R1-F21 簇） |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

（待 dev-story 实施后审查填写）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-10-29
**最后更新/Last Updated:** 2026-10-29
**更新说明/Description:**
- v1.0.0: 创建故事文件（四视角并行调研：SAP 现有代码 / Epic5 Agent 体系 / 事件总线消费基建 / 测试模板；8 OD + 10 DC + 10 风险 + 17 行范围边界；deferred-work 两项钦定留项处置方案落档 OD-6）
- v1.1.0: 文档审查周期 Round 1（四视角调研 + 三视角审查，7 Agent 并行）——修复 21 簇：P1×5（同级 FIFO 构造缺口 / BROADCAST×visible 正交开关钦定 / correlation 条目生命周期+幂等 resolve / handler 异常 deliver-continue / lambda fail-fast 翻译形态）+ P2×14（范围边界计数勘误 21 行 / AC-1 场景消歧 / timeout 计时锚+兜底常量 / 新增 OD-9 correlation 锚约定 / invalid_receiver_id 用例 / 十键强度统一 / close 语义清单 / Task 2 红形态 / 泄漏措辞收窄 / 闭集拒绝异常 EntityValidationError / redis marker 分档 / 覆盖率口径统一+两段式命令 / §7.6 审计行归属 / 验收延迟 import 钦定）+ P3 簇（行号锚 9 位勘误 + 16 项零散——DC-11/DC-12 新增、四方法签名钦定、边缘语义钦定等）；OD 8→9 项、DC 10→12 项、范围边界 20→21 行
