# language: zh-CN
功能: Story 1.13 - K8s 动态扩缩容

  作为运维工程师
  我想要系统暴露 Prometheus /metrics HTTP 端点，支持基于负载的自动扩缩容
  以便 K8s HPA 可以根据应用自定义指标实现动态扩缩容，响应时间<5 分钟

  场景: AC-1 - Prometheus /metrics HTTP 端点返回 Prometheus 格式
    假如 EventMetricsCollector 已实现（Story 1.3）
    假如 BusinessMetricsCollector 已实现
    假如 MetricsAggregator 已实现
    当 访问 /metrics 端点
    那么 应返回 Prometheus 文本格式指标
    并且 应包含 # HELP 和 # TYPE 注释行
    并且 应聚合 EventMetricsCollector 指标（events_processed_total）
    并且 应聚合 BusinessMetricsCollector 指标（sisys_agent_sessions_active）

  场景: AC-1 - Prometheus 格式兼容（指标类型支持）
    假如 BusinessMetricsCollector 已注册 Gauge 指标
    当 访问 /metrics 端点
    那么 应支持 Counter 类型指标
    并且 应支持 Gauge 类型指标
    并且 应支持 Histogram 类型指标
    并且 应支持 Summary 类型指标

  场景: AC-2 - 自定义业务指标暴露
    假如 Prometheus 端点已实现
    当 访问 /metrics 端点
    那么 应暴露 sisys_agent_sessions_active 指标（当前活跃 Agent 会话数）
    并且 应暴露 sisys_task_queue_length 指标（任务队列长度）
    并且 应暴露 sisys_events_processing_rate 指标（事件处理速率）
    并且 应暴露 sisys_cache_hit_rate 指标（缓存命中率）

  场景: AC-3 - K8s HPA 基于自定义指标扩缩容
    假如 Prometheus 端点暴露自定义业务指标
    假如 Prometheus Adapter 已部署（将 Prometheus 指标转换为 External Metrics）
    当 K8s HPA 基于自定义指标配置
    那么 HPA 应能够根据 sisys_agent_sessions_active 进行扩缩容决策
    并且 HPA 应能够根据 sisys_task_queue_length 进行扩缩容决策

  场景: AC-4 - 扩缩容响应时间<5 分钟
    假如 K8s HPA 已配置
    当 系统负载变化触发扩缩容
    那么 扩缩容完成时间应小于 5 分钟
    并且 Prometheus 指标采集间隔应 ≤15 秒
    并且 HPA 检查周期应 ≤60 秒

  场景: AC-5 - Grafana 可观测性
    假如 所有指标已暴露
    假如 Grafana Dashboard 已配置
    当 监控面板需要展示系统状态
    那么 Grafana 应展示 Agent 会话数面板
    并且 Grafana 应展示任务队列长度面板
    并且 Grafana 应展示事件处理速率面板
    并且 Grafana 应展示缓存命中率面板
