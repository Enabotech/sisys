# language: zh-CN
功能: Story 1.17 - UDMR 基础路由（云端优先静态配置）

  作为运维工程师
  我想要配置本地/云端路由策略（云端优先静态配置，云端不可用时回退本地）
  以便 MVP 阶段支持基础路由决策日志和成本追踪

  背景:
    假如 UDMRConfig 已配置本地模型和云端模型
    假如 ComplianceGatewayPort 已实现
    假如 StaticUdmrPolicy 已实现云端优先策略

  # =========================================================================
  # AC-1: UDMR 配置模型
  # =========================================================================

  场景: AC-1 - 解析 UDMR 环境变量配置
    假如 设置环境变量 UDMR_ENABLED=true
    并且 设置环境变量 UDMR_LOCAL_FIRST=false
    并且 设置环境变量 UDMR_LOCAL_MODEL=qwen2.5:7b
    当 调用 UDMRConfig.from_env()
    那么 应该返回 enabled=True, local_first=False, local_model="qwen2.5:7b" 的配置

  场景: AC-1 - 解析多云端模型配置
    假如 设置环境变量 UDMR_CLOUD_0_API_TYPE=anthropic
    并且 设置环境变量 UDMR_CLOUD_0_ENDPOINT=https://api.minimax.chat/anthropic
    并且 设置环境变量 UDMR_CLOUD_0_MODEL=MiniMax-M2.7
    并且 设置环境变量 UDMR_CLOUD_0_MAX_TOKENS=4096
    当 调用 UDMRConfig.from_env()
    那么 应该包含 1 个云端模型配置
    并且 云端模型的 api_type 应该是 "anthropic"
    并且 云端模型的 max_tokens 应该是 4096

  场景: AC-1 - Anthropic 类型缺少 max_tokens 抛出异常
    假如 设置环境变量 UDMR_CLOUD_0_API_TYPE=anthropic
    并且 设置环境变量 UDMR_CLOUD_0_MODEL=MiniMax-M2.7
    并且 未设置 UDMR_CLOUD_0_MAX_TOKENS
    当 调用 UDMRConfig.from_env()
    那么 应该抛出 ConfigurationError 异常

  # =========================================================================
  # AC-2: UDMR 静态路由决策
  # =========================================================================

  场景: AC-2 - 云端优先路由（合规通过 + 云端可用）
    假如 UDMR 配置为云端优先
    并且 L1 合规检查通过（forced_local=False）
    当 UDMRService 执行路由决策
    那么 route_type 应该是 "cloud"
    并且 selected_model 应该是第一个 enabled 的云端模型

  场景: AC-2 - L1 合规检查强制本地
    假如 L1 合规检查返回 forced_local=True（含敏感数据）
    当 UDMRService 执行路由决策
    那么 route_type 应该是 "local"
    并且 selected_model 应该是本地模型

  场景: AC-2 - 云端不可用回退本地
    假如 所有云端模型均 disabled 或不可用
    当 UDMRService 执行路由决策
    那么 route_type 应该是 "local"
    并且 fallback_reason 应该是 "unavailable"

  # =========================================================================
  # AC-3: 云端健康检查
  # =========================================================================

  场景: AC-3 - 云端健康检查通过
    假如 CloudHealthChecker 检查云端模型可用性
    当 云端 API 响应正常
    那么 check() 应该返回 True

  场景: AC-3 - 云端健康检查超时
    假如 CloudHealthChecker 检查云端模型可用性
    当 云端 API 超时
    那么 check() 应该返回 False

  # =========================================================================
  # AC-4: 事件集成
  # =========================================================================

  场景: AC-4 - UDMRHandler 处理 AutoRouted 事件
    假如 UDMRHandler 已注册订阅 AutoRouted 事件
    当 接收到 AutoRouted 事件
    那么 UDMRHandler 应该调用 UDMRService.decide()
    并且 应该发布 RoutingDecided 事件

  场景: AC-4 - 循环防护（排除 RoutingDecided）
    假如 RoutingDecided 事件被发布
    那么 AutoTriggerHandler 不应该被 RoutingDecided 事件触发

  # =========================================================================
  # AC-5: 路由性能
  # =========================================================================

  场景: AC-5 - 路由决策延迟 P95<100ms
    假如 UDMR 配置为静态路由模式
    当 执行 1000 次路由决策
    那么 P95 延迟应该小于 100ms
