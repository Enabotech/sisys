# language: zh-CN
功能: Story 1.19 - 成本度量基础（Token 消耗与成本追踪）

  作为运维工程师
  我想要追踪每个任务的 Token 消耗和成本，基于 UDMR 路由日志计算模型调用成本
  以便验证 MVP 成本优化效果并衡量 ROI

  背景:
    假如 UDMR 路由决策已产生 RoutingDecided 事件
    假如 CostCalculator 已配置定价表
    假如 TokenEstimatorPort 已实现

  # =========================================================================
  # AC-1: 模型定价配置
  # =========================================================================

  场景: AC-1 - CloudModelConfig 扩展定价字段（默认值）
    假如 创建 CloudModelConfig 使用默认值
    那么 price_per_input_1k_tokens 应该是 0.02
    并且 price_per_output_1k_tokens 应该是 0.02

  场景: AC-1 - CloudModelConfig 从环境变量解析定价
    假如 设置环境变量 UDMR_CLOUD_0_PRICE_INPUT=0.03
    并且 设置环境变量 UDMR_CLOUD_0_PRICE_OUTPUT=0.04
    当 解析 CloudModelConfig 定价配置
    那么 price_per_input_1k_tokens 应该是 0.03
    并且 price_per_output_1k_tokens 应该是 0.04

  场景: AC-1 - CloudModelConfig 定价非负校验
    假如 设置环境变量 UDMR_CLOUD_0_PRICE_INPUT=-0.01
    当 解析 CloudModelConfig 定价配置
    那么 应该抛出定价异常

  # =========================================================================
  # AC-2: Token 消耗值对象与成本计算服务
  # =========================================================================

  场景: AC-2 - TokenConsumption 不变量验证
    假如 创建 TokenConsumption prompt_tokens=256 completion_tokens=512
    那么 total_tokens 应该是 768

  场景: AC-2 - 本地路由成本计算
    假如 本地模型定价为 input=0.002 output=0.002（每 1K tokens）
    并且 Token 消耗为 prompt=256 completion=512
    当 调用 CostCalculator.calculate()
    那么 成本应该是 0.001536 元

  场景: AC-2 - 云端路由成本计算
    假如 云端模型定价为 input=0.02 output=0.02（每 1K tokens）
    并且 Token 消耗为 prompt=512 completion=1024
    当 调用 CostCalculator.calculate()
    那么 成本应该是 0.03072 元

  场景: AC-2 - 零 Token 输入成本为 0
    假如 Token 消耗为 prompt=0 completion=0
    当 调用 CostCalculator.calculate()
    那么 成本应该是 0.0 元

  # =========================================================================
  # AC-3: RoutingDecided 事件与 RoutingDecisionLog 扩展
  # =========================================================================

  场景: AC-3 - RoutingDecided 事件扩展字段（向后兼容）
    假如 创建默认 RoutingDecided 事件
    那么 prompt_tokens 应该是 0
    并且 completion_tokens 应该是 0
    并且 total_tokens 应该是 0
    并且 cost_actual 应该是 0.0

  场景: AC-3 - RoutingDecisionLog 扩展字段（向后兼容）
    假如 创建默认 RoutingDecisionLog 实体
    那么 log 的 prompt_tokens 应该是 0
    并且 log 的 completion_tokens 应该是 0
    并且 log 的 total_tokens 应该是 0

  # =========================================================================
  # AC-4: CostMetricsListener 事件监听
  # =========================================================================

  场景: AC-4 - CostMetricsListener 处理 RoutingDecided 事件
    假如 RoutingDecided 事件 route_type="local" selected_model="qwen2.5:7b"
    当 CostMetricsListener 处理事件
    那么 应该调用 TokenEstimatorPort.estimate()
    并且 应该调用 CostCalculator.calculate()
    并且 应该更新 RoutingDecisionLog 的 cost_actual
    并且 应该记录 Prometheus 指标

  # =========================================================================
  # AC-5: Prometheus 指标扩展与聚合查询
  # =========================================================================

  场景: AC-5 - Prometheus 指标记录 Token 消耗
    假如 MetricsPort 已初始化
    当 调用 record_token_usage(prompt=256, completion=512, model="qwen2.5:7b", route_type="local")
    那么 sisys_token_prompt_total 指标应该增加 256
    并且 sisys_token_completion_total 指标应该增加 512

  场景: AC-5 - Prometheus 指标记录成本
    假如 MetricsPort 已初始化
    当 调用 record_cost(cost=0.001536, model="qwen2.5:7b", route_type="local")
    那么 sisys_cost_total_cny 指标应该更新为 0.001536
