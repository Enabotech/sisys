# language: zh-CN
# Story 4-7 — Validation Feedback 闭环（BDD 验收场景，覆盖 AC-1 ~ AC-7 + 收尾场景）
#
# 模板:test_acceptance_postgresql_relational_layer.feature 结构风格 +
#       test_acceptance_tool_version_management.feature 工具系场景组织（服务级 BDD）
#
# 防放大/跨尝试反馈/hints 透传为单测口径（test_validation_feedback_service.py /
# test_tool_execution_engine_hints.py），BDD 不重复覆盖——Story BDD 步骤实现约束。

功能: Validation Feedback 闭环（增强重试与不可行标记）

  作为质量保障工程师
  我希望系统在工具执行基础重试耗尽后自动捕获 STDERR、检索错误案例库辅助 LLM 生成修复代码并增强重试
  以便工具执行失败可自动恢复或明确标记不可行，失败历史可追溯

  背景:
    假如 Validation Feedback 服务链已装配（真实服务 + Mock LLM/Sandbox 适配器）

  # ============================================================================
  # AC-1: STDERR 捕获数据链贯通
  # ============================================================================

  场景: AC-1.1 - 沙箱执行失败异常携带 STDERR 与退出码
    假如沙箱适配器执行代码以非零退出码失败
    当适配器抛出执行失败异常
    那么异常 context 携带 stderr 字段（截断至 2000 字符）
    并且异常 context 携带 exit_code 字段

  场景: AC-1.2 - SandboxExecutionFailed 事件填充 execution_id 与 stderr
    假如引擎链执行中沙箱代码失败被包装为执行失败异常
    当安全装饰器发布沙箱执行失败事件
    那么事件的 execution_id 取自外层异常 context
    并且事件的 stderr 取自内层执行异常 context

  场景: AC-1.3 - 反馈闭环沿异常因果链提取 STDERR
    假如触发异常的 cause 链携带执行失败异常
    当闭环提取错误上下文
    那么自定义 cause 属性与 __cause__ 链均可提取 stderr

  # ============================================================================
  # AC-2: 触发判定矩阵（九行全覆盖）
  # ============================================================================

  场景: AC-2.1 - Schema 校验耗尽触发闭环（389-Schema 子路径）
    假如工具输出校验基础重试耗尽抛出校验失败异常 389
    当装饰链最外层捕获触发异常
    那么进入增强反馈闭环且 trigger_code 为 EXCEPTION_389

  场景: AC-2.2 - LLM 瞬时故障校验耗尽触发闭环（389-LLM 子路径）
    假如 LLM 瞬时故障经引擎与校验双层重试耗尽转出 389
    当装饰链最外层捕获触发异常
    那么进入增强反馈闭环且 LLM 瞬时根因直传原触发异常

  场景: AC-2.3 - 沙箱代码执行失败触发闭环（382-EXECUTION 且 cause 属 ExecutionError 族）
    假如沙箱内代码缺陷经引擎兜底包装为 382 且 stage 为 EXECUTION
    并且异常 cause 为执行失败异常 313
    当装饰链最外层捕获触发异常
    那么进入增强反馈闭环且 trigger_code 为 EXCEPTION_382

  场景: AC-2.4 - 混入的配置类故障不进入闭环直传（382-EXECUTION 且 cause 不属族）
    假如引擎兜底宽捕获把 LLM 配置错误 332 包装为 382 且 stage 为 EXECUTION
    当装饰链最外层捕获触发异常
    那么不进入闭环并直传原异常
    并且零观测副作用（无演进日志、无事件、无案例回填）

  场景: AC-2.5 - 沙箱启动失败不进入闭环直传（382-SANDBOX_START）
    假如沙箱启动失败包装为 382 且 stage 为 SANDBOX_START
    当装饰链最外层捕获触发异常
    那么不进入闭环并直传原异常

  场景: AC-2.6 - 引擎总预算超时不进入闭环直传（385）
    假如引擎执行超出总时间预算抛出超时异常 385
    当装饰链最外层捕获触发异常
    那么不进入闭环并直传原异常

  场景: AC-2.7 - 策略违规与标记语法错误不进入闭环直传（207/201）
    假如触发浮出策略违规异常 207 或标记语法错误 201
    当装饰链最外层捕获触发异常
    那么不进入闭环并直传原异常

  场景: AC-2.8 - 数据源故障族不进入闭环直传（410-413）
    假如触发浮出数据源故障族异常
    当装饰链最外层捕获触发异常
    那么不进入闭环并直传原异常

  场景: AC-2.9 - Schema 缺失不进入闭环直传（398）
    假如触发浮出 Schema 缺失异常 398
    当装饰链最外层捕获触发异常
    那么不进入闭环并直传原异常

  # ============================================================================
  # AC-2: 增强重试与修复代码生成
  # ============================================================================

  场景: AC-2.10 - 增强尝试总数为 3 次总尝试语义
    假如进入增强反馈闭环且修复始终失败
    当闭环耗尽
    那么增强尝试次数为 3（attempt 1 至 3 总尝试语义）

  场景: AC-2.11 - 命中恢复案例注入修复配方（CASE_GUIDED）
    假如错误案例库存在同签名的 RECOVERED 案例且 fix_summary 非空
    当闭环组装修复 prompt
    那么修复 prompt 包含案例 fix_summary
    并且该次尝试的 fix_strategy 为 CASE_GUIDED

  场景: AC-2.12 - 命中不可行案例注入负样本提示全量 3 次不缩减（NEGATIVE_CASE_GUIDED）
    假如错误案例库存在同签名的 MARKED_INFEASIBLE 案例且 error_category 匹配
    当闭环组装修复 prompt
    那么修复 prompt 包含负样本提示（此签名已观测到 N 次不可行）
    并且该次尝试的 fix_strategy 为 NEGATIVE_CASE_GUIDED
    并且增强尝试仍为全量 3 次不缩减

  场景: AC-2.13 - 案例库无命中纯 LLM 修复（PURE_LLM）
    假如错误案例库无同签名案例
    当闭环组装修复 prompt
    那么修复 prompt 不包含案例注入
    并且该次尝试的 fix_strategy 为 PURE_LLM

  场景: AC-2.14 - 命中恢复案例但配方为空落 PURE_LLM（LLM_TRANSIENT 首例）
    假如错误案例库存在同签名的 RECOVERED 案例但 fix_summary 为空
    当闭环组装修复 prompt
    那么修复 prompt 不注入空配方
    并且该次尝试的 fix_strategy 为 PURE_LLM

  场景: AC-2.15 - 签名碰撞且分类不匹配抑制负样本（碰撞命中已抑制）
    假如错误案例库存在同签名案例但 outcome 为 MARKED_INFEASIBLE 且 error_category 不匹配
    当闭环组装修复 prompt
    那么修复 prompt 不包含负样本提示
    并且该次尝试的 fix_strategy 为 PURE_LLM

  场景: AC-2.16 - 修复成功返回 SUCCESS 且携带增强尝试次数与恢复事件
    假如第 2 次增强尝试重执行成功
    当闭环返回结果
    那么结果状态为 SUCCESS 且 retry_count 为 2
    并且发布 ToolExecutionRecovered 领域事件（execution_id 与演进日志同源）

  场景: AC-2.17 - 修复生成失败计为该次增强尝试失败
    假如某次增强尝试的修复建议生成持续失败
    当该次尝试结束
    那么该次尝试 detail 为 llm_generation_failed 且不计为重执行失败
    并且闭环继续下一尝试

  场景: AC-2.18 - 增强尝试中浮出不可修复异常中止闭环直传（abort 零观测副作用）
    假如第 1 次增强尝试重执行浮出标记语法错误 201
    当闭环处理该异常
    那么中止闭环并直传该异常
    并且零观测副作用（无演进日志终态、无事件、无案例回填、重放不短路）

  场景: AC-2.19 - LLM 持续故障全耗尽直传不标不可行（LLMAPIError 形态）
    假如 3 次增强尝试全部因 LLM API 持续故障失败（llm_generation_failed）
    当闭环耗尽
    那么直传原触发异常且不返回 INFEASIBLE
    并且零观测副作用（无演进日志终态、无事件、无案例回填）

  场景: AC-2.20 - LLM 网络超时持续故障全耗尽直传（TimeoutError 形态）
    假如 3 次增强尝试全部因 LLM 网络超时持续故障失败
    当闭环耗尽
    那么直传原触发异常且不返回 INFEASIBLE

  # ============================================================================
  # AC-3: 不可行标记与领域事件
  # ============================================================================

  场景: AC-3.1 - 3 次增强重试耗尽标记任务不可行返回 INFEASIBLE
    假如 3 次增强尝试均失败且根因非 LLM 瞬时
    当闭环耗尽
    那么返回 INFEASIBLE 结果且不抛异常
    并且 output 携带失败摘要（error_signature、最终 STDERR 摘要、尝试次数）

  场景: AC-3.2 - 耗尽发布不可行标记领域事件
    假如 3 次增强尝试均失败且根因非 LLM 瞬时
    当闭环耗尽
    那么发布 ToolExecutionMarkedInfeasible 领域事件
    并且事件 execution_id 与演进日志幂等键同源

  场景: AC-3.3 - DAG FAIL_FAST 链不可行仍中断且异常携带失败签名
    假如工具链以 FAIL_FAST 策略执行且某节点结果为 INFEASIBLE
    当编排器构造链执行失败异常
    那么异常 context 携带 error_signature 与 enhanced_retry_count

  场景: AC-3.4 - SKIP_DOWNSTREAM 下游跳过且独立分支正常执行
    假如工具链以 SKIP_DOWNSTREAM 策略执行且某节点结果为 INFEASIBLE
    当链执行完成
    那么该节点下游为 SKIPPED 且独立分支节点正常执行
    并且不可行节点 state 为 INFEASIBLE（非 FAILED 二值折叠）

  # ============================================================================
  # AC-4: 演进日志与持久化
  # ============================================================================

  场景: AC-4.1 - 恢复成功写入 RECOVERED 演进日志
    假如某次增强尝试重执行成功
    当闭环结束
    那么演进日志 final_status 为 RECOVERED
    并且记录 trigger_code、error_signature、enhanced_retry_count、duration_sec
    并且 fix_attempts 携带各次 attempt_execution_id 回链

  场景: AC-4.2 - 耗尽写入 MARKED_INFEASIBLE 演进日志
    假如 3 次增强尝试均失败且根因非 LLM 瞬时
    当闭环耗尽
    那么演进日志 final_status 为 MARKED_INFEASIBLE

  场景: AC-4.3 - 按工具查询反馈历史（list_by_tool）
    假如同一工具已有多次反馈闭环记录
    当按 tool_id 查询演进日志
    那么返回该工具全部反馈历史且支持分页

  场景: AC-4.4 - 按执行标识精确定位单次记录（get_by_execution）
    假如某次执行已写入演进日志
    当按 execution_id 查询
    那么返回该次记录且 execution_id 唯一

  # ============================================================================
  # AC-5: 错误案例库（查询辅助 + 案例回填 + 幂等）
  # ============================================================================

  场景: AC-5.1 - 恢复成功回填 recovered_count 并覆写 fix_summary
    假如闭环以恢复成功结束且 error_category 非 LLM_TRANSIENT
    当案例回填
    那么 recovered_count 递增且 fix_summary 覆写为最近一次成功修复

  场景: AC-5.2 - 耗尽回填 infeasible_count 且 fix_summary 不动
    假如同签名案例已有修复配方
    当闭环以标记不可行结束
    那么 infeasible_count 递增且 fix_summary 保持不变

  场景: AC-5.3 - 同签名重复发生 occurrence_count 幂等递增
    假如同一签名再次触发反馈闭环并结束
    当案例回填
    那么不产生重复行且 occurrence_count 递增
    并且 occurrence_count 等于 recovered_count 与 infeasible_count 合计

  场景: AC-5.4 - LLM 瞬时类成功不覆写 fix_summary
    假如闭环以 LLM_TRANSIENT 类恢复成功结束
    当案例回填
    那么 recovered_count 递增且 fix_summary 不覆写

  # ============================================================================
  # AC-6: 幂等性与事件通道补全
  # ============================================================================

  场景: AC-6.1 - 同触发异常重复进入闭环副作用去重（INFEASIBLE 终态）
    假如某触发异常已以标记不可行结束
    当同一触发异常重复调用 recover
    那么演进日志仍为 1 行且事件不重复发布
    并且返回合成 INFEASIBLE 结论
    并且案例分类计数与 occurrence 同步递增

  场景: AC-6.2 - RECOVERED 终态重放返回可辨识合成摘要
    假如某触发异常已以恢复成功结束
    当同一触发异常重复调用 recover
    那么返回合成 SUCCESS 摘要且 output 携带 replayed 为 true 的标记
    并且合成摘要不含证据包

  场景: AC-6.3 - ToolSchemaValidationFailed 升级 reliable 双登记
    当检查事件通道配置两处（YAML 与 DEFAULT_MAPPINGS）
    那么 ToolSchemaValidationFailed 配置双通道（redis_channel 与 rabbitmq_routing_key）
    并且 delivery_mode 为 reliable

  场景: AC-6.4 - 新增两事件配置双登记 reliable
    当检查事件通道配置两处（YAML 与 DEFAULT_MAPPINGS）
    那么 ToolExecutionMarkedInfeasible 与 ToolExecutionRecovered 均双通道登记
    并且两处配置逐字段一致

  # ============================================================================
  # AC-7: 装配升级
  # ============================================================================

  场景: AC-7.1 - 装饰链四层装配且服务版本升级 v1.4.0
    当检查组合根装配
    那么装饰链层叠为 ValidationFeedbackDecorator 最外层
    并且 tool_execution_service 版本为 v1.4.0 且 tags 含 feedback

  # ============================================================================
  # 收尾场景（开发结束验收）
  # ============================================================================

  场景: 收尾-1 - src 完成清单逐项确认
    当检查 src 生产代码完成清单
    那么 18 个新文件与 17 个修改文件全部就位
    并且领域层零外部依赖保持

  场景: 收尾-2 - tests 四目录完成清单逐项确认
    当检查 tests 完成清单
    那么 unit、integration、contracts、acceptance 四目录测试文件全部就位且可导入
