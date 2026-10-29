# language: zh-CN
功能: CheckpointWithEvaluation 集成（Story 5.10——FR-EV-04）

  作为可观测性工程师
  我想要实现评估历史累积器与 Checkpoint 快照集成（EvaluationCheckpointRecorder 累积 + to_checkpoint_snapshot 打包 + 真实持久化/恢复 + 主链第八可选依赖接入）
  以便评估历史随 Checkpoint 持久化，支持漂移趋势追踪与历史质量回溯

  # =========================================================================
  # AC-1: CheckpointWithEvaluation 聚合与快照转换（组件级——纯内存零服务依赖）
  # =========================================================================

  场景: AC-1.1 - EvaluationCheckpoint 域守卫与聚合等长守卫
    假如 真实 EvaluationCheckpoint 与 CheckpointWithEvaluation frozen DTO 已装配（手工构造——纯数据类）
    当 执行五分数字段越界与类型违规参数化构造与三序列等长守卫构造
    那么 五分数域守卫断言通过（[-0.01/1.01/True/"0.5"] 抛 ValidationError 201 三段式——context 携字段名）
    并且 agent_id 非空守卫断言通过（空串抛 201）
    并且 frozen 不可变断言通过（setattr 抛 FrozenInstanceError）
    并且 三序列等长守卫断言通过（history 3 + trend 2 抛 201）

  场景: AC-1.2 - to_checkpoint_snapshot 打包（state_data 四键契约）
    假如 手算锚聚合已构造（3 条评估记录——分数取 0.1/0.3/0.5 一位小数）
    当 调用 to_checkpoint_snapshot(session_id, state_version=1) 打包
    那么 打包结构断言通过（stage_id=="evaluation" + state_data 四键存在 + snapshot_id 非空 UUID + ttl_seconds==86400 + state_version==1 默认值）
    并且 手算锚逐值断言通过（三序列长度 == 3 + 逐值精确相等）
    并且 MAX_HISTORY_SIZE 常量单源断言通过（== 100 模块常量）

  场景: AC-1.3 - from_snapshot 往返一致性与空历史退化锚
    假如 手算锚聚合已构造（3 条评估记录——分数取 0.1/0.3/0.5 一位小数）
    当 执行打包后 from_snapshot 解包往返
    那么 往返一致性断言通过（三序列逐值精确相等 + recorded_at isoformat 往返相等 + agent_id 相等）
    并且 空历史退化锚断言通过（零记录聚合打包三序列空列表 + 恢复空聚合）

  # =========================================================================
  # AC-2: 主链接入——第八可选依赖 + record 块 + 独立降级网（链级——OTel 通道 + 零 IO 替身）
  # =========================================================================

  场景: AC-2.1 - 主链 record 块执行与 predicted 持久化
    假如 链级全局追踪通道已启用（场景级 initialize + InMemory exporter）
    并且 checkpoint 工作流链已装配（Fake LLM 幻觉分注入 + 真实 Recorder + 手写零 IO _RecordingSnapshotRepo 替身 + drift_detector 注入）
    当 调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流
    那么 record 调用断言通过（替身捕获 1 个 CheckpointSnapshot + state_data 四键 + 末条五分数字段逐值相等 + agent_id 相等 + recorded_at 近期时刻）
    并且 predicted 持久化断言通过（predicted_confidence == result.evidence.confidence——V1-EV3 兑现锚）
    并且 命名空间与顺序断言通过（session_id=="agent-evaluation-{agent_id}" + stage_id=="evaluation" + record 块在三键后漂移前）
    并且 连续执行累积断言通过（同 agent 连续 2 次 execute → 第二次快照历史长度 == 2 + trend 长度 == 2）

  场景: AC-2.2 - record 失败独立降级网（452 不阻断主链与漂移块）
    假如 链级全局追踪通道已启用（场景级 initialize + InMemory exporter）
    并且 降级工作流链已装配（_RaisingSnapshotRepo——save 抛 StorageError + drift 预填充场景）
    当 调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流
    那么 record 失败降级断言通过（主链正常返回 + eval 三键仍在 + 漂移块仍执行 drift.detected==True）
    并且 WARNING 日志断言通过（WARNING 级 + 文本含 452 静态 message "评估历史持久化失败"）

  场景: AC-2.3 - 降级联动与构造签名八依赖基线
    假如 工作流模块已加载
    当 检查漂移失败联动与评估降级联动与 None 默认路径与构造签名
    那么 漂移失败联动断言通过（漂移块抛 451 → record 已完成替身捕获非空 + 主链正常返回）
    并且 评估降级联动断言通过（evaluate 抛 450 → record 零调用 + 主链正常返回）
    并且 None 默认路径断言通过（七参构造行为与 5.9 基线一致 + record 块零执行）
    并且 八依赖签名断言通过（inspect.signature 参数清单尾部 checkpoint_recorder + 默认 None + 外层共享 catch 三元组不变）
    并且 存量断言同步 ×7 基线断言通过（5-3/5-7/5-8/5-9 存量全家回归绿）

  # =========================================================================
  # AC-3: 持久化与恢复——真实 Redis 往返 + 命名空间隔离 + 恢复式语义（真实服务）
  # =========================================================================

  场景: AC-3.1 - 真实 Redis 落键验证
    假如 真实 Redis 服务可用（场景级独立客户端 + TestTenant UUID 前缀隔离——不可用则动态跳过）
    并且 真实 Recorder 已装配（组合注入真实 RedisSnapshotStore）
    当 record 多次（≥3 次——累积后持久化）
    那么 落键验证断言通过（hget build_key("snapshot", session_id) "latest" 非空 + 两层 json_loads 解析 + 三序列与 record 传入逐值相等）
    并且 TTL 语义断言通过（快照 ttl_seconds == 86400 实体默认）

  场景: AC-3.2 - 重启恢复与累积延续
    假如 真实 Redis 服务可用（前一场景已落键——session 独立键）
    并且 新构造 Recorder 实例已装配（模拟重启——内存累积清零）
    当 调用 restore(session_id) 从快照恢复后继续 record 1 次
    那么 重启恢复断言通过（restore 返回聚合非空 + 历史长度 == 最后快照 + 逐值精确相等——重启存活锚）
    并且 累积延续断言通过（新快照历史 == 恢复历史 + 1 + 首条 == 恢复首条——恢复式语义灌回三 deque）
    并且 快照不存在断言通过（restore 未 record 过的 UUID session_id → None 正常态）

  场景: AC-3.3 - 趋势时序与自清理
    假如 真实 Redis 服务可用（场景级独立客户端）
    并且 真实 Recorder 已装配（record 注入序已知）
    当 执行多次 record 后验证趋势序列顺序与 teardown 清理
    那么 趋势时序断言通过（hallucination_trend 顺序 == record 注入顺序——值序非单调性）
    并且 自清理断言通过（teardown delete 后 RedisSnapshotStore.exists(session_id) is False——只清自己创建的键）

  # =========================================================================
  # AC-4: 端口接线、架构合规与组合根注册（静态 + 接线——零 OTel 全局触碰）
  # =========================================================================

  场景: AC-4.1 - 组合根接线与降级防护
    假如 组合根注册模块已加载
    当 检查 agent_checkpoint 端口注册与 use case 工厂第八依赖接线
    那么 组合根注册 resolve 四件断言通过（可达/isinstance/PortSpec 元数据/SINGLETON）
    并且 use case 工厂注入断言通过（resolve 实例 _checkpoint_recorder 非 None 且 isinstance AgentCheckpointPort）
    并且 CR1-DF2 降级防护断言通过（未注册形态 resolve_optional None + use case 构造成功）
    并且 端口契约 11 维度断言通过（REQUIRED_METHODS ["record","restore"] + _DummyResolver snapshot_repository 分支）

  场景: AC-4.2 - 架构静态扫描
    假如 交付文件存在性已确认
    当 执行架构静态扫描（内联轻量版——全量验证器归 tests/unit/architecture）
    那么 application 触碰文件零新增第三方断言通过
    并且 domain 触碰面收窄断言通过（EvaluationHistoryError 仅异常三件内 + events 零触碰——OD-6 契约）
    并且 组合根外零实例化与依赖方向断言通过
    并且 主链 record 块静态锚断言通过（record 调用 + predicted=result.evidence.confidence + 内层 except EvaluationHistoryError + 漂移块前序）
    并且 .env.example 零改动断言通过 + xdist 组互异断言通过（checkpoint-evaluation-perf 与既有 14 组不冲突）

  # =========================================================================
  # AC-5: 性能双锚——快照创建 P95<100ms + 评估历史查询 P95<50ms（委托集成计时）
  # =========================================================================

  场景: AC-5.1 - 快照创建 P95 小于 100ms
    假如 集成计时委托模块已加载（_PERF_CACHE 委托采样——满窗锚预填充 100 条）
    当 执行 P95 委托采样（warmup 1 + 20 采样 + quantiles exclusive [18]）
    那么 save P95 小于 100ms 断言通过（CHECKPOINT_SAVE_P95_LIMIT_SECONDS 常量单源）
    并且 正向锚断言通过（采样批次 save 调用计数 == warmup + 采样数 21）
    并且 满窗锚断言通过（预填充 100 条历史经 record 公共路径——最大体积形态下双锚成立）

  场景: AC-5.2 - 评估历史查询 P95 小于 50ms
    假如 集成计时委托模块已加载（_PERF_CACHE 委托采样——同批 20 采样）
    当 执行查询 P95 委托采样（完整 restore 调用——load + 解包）
    那么 query P95 小于 50ms 断言通过（CHECKPOINT_QUERY_P95_LIMIT_SECONDS 常量单源）
    并且 正向锚断言通过（采样批次 load 调用计数 == warmup + 采样数 21）
    并且 口径声明断言通过（save 含 Redis RTT / 满窗口径 / 本地 Redis 前提 / 门=回归绊线 / 20 样本方差五注记落 docstring）

  # =========================================================================
  # 收尾: 完成清单逐项确认（Task 6 追加——14 终态）
  # =========================================================================

  场景: 收尾 - 完成清单逐项确认
    假如 开发完成清单已就绪（src 2 新建 + 7 修改 + tests 7 新建 + 3 追加 + 6 存量签名同步）
    当 逐项验证 src 与 tests 完成清单
    那么 src 完成清单断言通过（agent_checkpoint 端口/Recorder 实现/452 四件套/主链第八依赖/组合根区段/ports 导出）
    并且 tests 四目录完成清单断言通过（七件新建 + test_run_agent_workflow 追加块 + 452 异常用例 + expected_types + 存量同步 ×7）
