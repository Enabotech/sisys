# language: zh-CN
功能: CUSUM 漂移检测与触发重校准（Story 5.9——FR-EV-03）

  作为可观测性工程师
  我想要实现 CUSUM 漂移检测与触发重校准机制（CUSUMDriftDetector 双侧累积和 + N中M 确认 + DriftDetected 事件 + 主链接入）
  以便自动检测模型性能漂移并触发重校准，保证输出质量稳定

  # =========================================================================
  # AC-1: CUSUMDriftDetector 双侧累积和算法（组件级——零服务依赖）
  # =========================================================================

  场景: AC-1.1 - CUSUM 双侧累积和与预热基线
    假如 真实 CUSUMDriftDetector 实例已装配（模块常量单源断言）
    当 灌入 30 样本交替基线序列与 5 样本漂移注入序列
    那么 预热期行为断言通过（baseline_ready=False + sample_count 递增 + 预热统计 + N=1 时 baseline_std=0.0）
    并且 第 30 样本起基线冻结断言通过（第 31 样本 baseline_ready=True + 后续样本基线不变）
    并且 双侧累积和逐样本 Sₗ 手算锚断言通过（同式表达式实算）
    并且 s35 确认漂移（is_drifted=True + direction=down + level=severe + ratio 同式表达 >8）

  场景: AC-1.2 - N中M 确认与确认后复位
    假如 真实 CUSUMDriftDetector 实例已装配（模块常量单源断言）
    当 执行确认窗边界三形态序列与确认后复位序列
    那么 确认窗未满 5 不确认断言通过（s32-s34 detection True 但 is_drifted=False）
    并且 当前样本条件断言通过（(F,T,T,T,F) 不确认 + (F,T,T,F,T) 确认 + (F,T,T,F,F) 不确认）
    并且 确认后复位断言通过（S 归零重启 + 确认窗清空 + 基线保持 + 再确认间隔锚）

  场景: AC-1.3 - 无漂移对照与正向漂移与防御面
    假如 真实 CUSUMDriftDetector 实例已装配（模块常量单源断言）
    当 执行无漂移对照续灌与正向漂移注入与 degenerate 基线与入参域越界参数化
    那么 无漂移对照断言通过（交替序列续灌恒不触发 + S 有界）
    并且 正向漂移断言通过（0.95×8 确认 up + level=moderate + 前 5 样本余量不触发）
    并且 degenerate 防御断言通过（全同值基线恒不判定 + sample_count 递增）
    并且 入参域守卫断言通过（越界/bool/非数值抛 ValidationError 201 三段式）

  # =========================================================================
  # AC-2: trigger_recalibration 与 DriftDetected 事件（组件级——真实检测器 + 零 IO 替身）
  # =========================================================================

  场景: AC-2.1 - trigger_recalibration 发布 DriftDetected 事件
    假如 真实 CUSUMDriftDetector 实例已装配（注入手写零 IO publisher 替身）
    并且 确认漂移的 DriftAssessment 实例已产出（手算锚序列）
    当 调用 trigger_recalibration 执行事件发布
    那么 发布事件字段真值断言通过（isinstance + metric_name + 逐字段相等 + agent_id 透传）
    并且 未确认 assessment 零发布断言通过（is_drifted=False 注入零捕获）
    并且 事件契约断言通过（注册 + aggregate_type + to_dict 序列化含 agent_id）

  场景: AC-2.2 - 事件通道双登记契约
    假如 事件通道配置模块已加载
    当 检查 DriftDetected 双登记条目
    那么 event_channels.yaml 条目断言通过（rabbitmq_routing_key + delivery_mode reliable）
    并且 ChannelRouter.DEFAULT_MAPPINGS 条目断言通过（同字段逐字一致）

  场景: AC-2.3 - 发布失败降级不阻断
    假如 真实 CUSUMDriftDetector 实例已装配（注入抛异常 publisher 替身）
    并且 确认漂移的 DriftAssessment 实例已产出（手算锚序列）
    当 调用 trigger_recalibration 执行事件发布
    那么 发布失败降级断言通过（不上抛 returns None + caplog error 断言）

  # =========================================================================
  # AC-3: 主链接入——第七可选依赖 + 漂移检测块 + drift.detected span 填值（链级——OTel 通道）
  # =========================================================================

  场景: AC-3.1 - 主链漂移检测执行与 drift.detected span 填值
    假如 链级全局追踪通道已启用（场景级 initialize + InMemory exporter）
    并且 漂移检测工作流链已装配（预填充 34 样本 + Fake LLM 幻觉分注入 + 零 IO publisher 替身）
    当 调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流
    那么 agent_execution 根 span drift.detected 真值断言通过（键字符串逐字对照——OD-2 兑现锚）
    并且 DriftDetected 事件发布断言通过（替身捕获 + direction=down + agent_id 透传）

  场景: AC-3.2 - 漂移检测降级不阻断主链
    假如 链级全局追踪通道已启用（场景级 initialize + InMemory exporter）
    并且 降级工作流链已装配（手写零 IO FakeDriftPort——update 抛 451）
    当 调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流
    那么 主链正常返回断言通过（结果五字段 + eval 三键仍在 + drift.detected 缺席）
    并且 降级 warning 日志断言通过（WARNING 级 + 文本含 451 异常 str）

  场景: AC-3.3 - 构造签名七依赖与存量回归基线
    假如 工作流模块已加载
    当 检查构造签名七依赖清单与 None 默认路径
    那么 七依赖签名断言通过（inspect.signature 参数清单 + 第七参数默认 None）
    并且 None 默认路径断言通过（六参构造行为与 5.8 基线一致 + 漂移块零执行）
    并且 存量断言同步 ×5 基线断言通过（5-7 验收 + 5-7 test_arch + 5-8 test_arch + 单测第六参 + 5-8 验收清单）

  # =========================================================================
  # AC-4: 端口接线、架构合规与组合根注册（静态 + 接线——零 OTel 全局触碰）
  # =========================================================================

  场景: AC-4.1 - 组合根接线与降级防护
    假如 组合根注册模块已加载
    当 检查 agent_drift 端口注册与 use case 工厂接线
    那么 组合根注册 resolve 四件断言通过（可达/isinstance/PortSpec 元数据/SINGLETON）
    并且 use case 工厂注入断言通过（resolve 实例 _drift_detector 非 None 且 isinstance DriftDetectionPort）
    并且 CR1-DF2 降级防护断言通过（未注册形态 resolve_optional None + use case 构造成功）
    并且 端口契约 11 维度断言通过（REQUIRED_METHODS + _DummyResolver event_publisher 分支）

  场景: AC-4.2 - 架构静态扫描
    假如 交付文件存在性已确认
    当 执行架构静态扫描（内联轻量版——全量验证器归 tests/unit/architecture）
    那么 application 触碰文件零新增第三方断言通过
    并且 domain 触碰面收窄断言通过（业务目录零命中 + events 白名单域 + 异常三件内）
    并且 组合根外零实例化与依赖方向断言通过
    并且 主链漂移块静态锚断言通过（update 调用 + DRIFT_DETECTED 常量 + is_drifted 分支 + trigger_recalibration）
    并且 .env.example 零改动断言通过

  # =========================================================================
  # AC-5: 性能双锚——检测延迟 P99 + 合成回测准确率（委托集成计时）
  # =========================================================================

  场景: AC-5.1 - 检测延迟 P99 小于 100ms
    假如 集成计时委托模块已加载（_PERF_CACHE 委托采样）
    当 执行 P99 委托采样（warmup 1 + 100 采样 + quantiles exclusive [98]）
    那么 P99 小于 100ms 断言通过（DRIFT_P99_LIMIT_SECONDS 常量单源）
    并且 正向锚断言通过（采样轮 update 调用计数 == warmup + 采样数 101）

  场景: AC-5.2 - 合成序列回测准确率不低于 85%
    假如 集成计时委托模块已加载（_PERF_CACHE 委托回测）
    当 执行合成回测委托采样（固定种子 20261028 + 40 序列 × 60 样本 + RNG 调用序钉死）
    那么 回测准确率不低于 85% 断言通过（(TP+TN)/40 ≥ 0.85 + 分项计数可观测）
    并且 确定性断言通过（同种子重跑同结果）
    并且 xdist 组互异断言通过（drift-detection-perf 与既有 13 组不冲突）

  # =========================================================================
  # 收尾: 完成清单逐项确认（Task 6 追加——14 终态）
  # =========================================================================

  场景: 收尾 - 完成清单逐项确认
    假如 开发完成清单已就绪（src 七件 + tests 十件新建 + 存量触碰文本锚）
    当 逐项验证 src 与 tests 完成清单
    那么 src 完成清单断言通过（检测器/端口/事件/异常/组合根/通道双登记/主链漂移块文本锚）
    并且 tests 四目录完成清单断言通过（十件新建 + 断言同步 ×5 + expected_types 伴随更新）
