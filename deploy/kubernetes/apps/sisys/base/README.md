# K8s 自定义指标与 HPA 扩缩容配置说明

**Story 1.13: K8s 动态扩缩容**

## 概述

本目录包含 SISYS 应用的 K8s HPA 配置，用于支持基于自定义业务指标的动态扩缩容。

## Prometheus Adapter 部署说明

### 关键说明

**K8s HPA 不能直接使用 Prometheus 自定义指标！**

HPA 的 `External Metrics` 需要通过 **Prometheus Adapter**（如 `prometheus-adapter`）将 Prometheus 指标转换为 K8s External Metrics API。

### Prometheus Adapter 部署职责

| 组件 | 负责方 | 说明 |
|------|--------|------|
| Prometheus Server | Story 0.4 / 运维团队 | 抓取应用 `/metrics` 端点 |
| Prometheus Adapter | ✅ 已配置 (Story 1.13) | 将 Prometheus 指标转换为 K8s External Metrics |
| HPA 配置 | ✅ 已配置 (Story 1.13) | 基于自定义指标的扩缩容策略 |

### Prometheus Adapter 部署

**配置文件**: `deploy/kubernetes/metrics/prometheus-adapter.yaml`

**部署命令**:
```bash
kubectl apply -f deploy/kubernetes/metrics/prometheus-adapter.yaml
```

**部署步骤**:

1. **部署 prometheus-adapter**:
   ```bash
   kubectl apply -f deploy/kubernetes/metrics/prometheus-adapter.yaml
   ```

2. **验证 External Metrics API 可用**:
   ```bash
   kubectl get apiservice v1beta1.external.metrics.k8s.io
   # 应显示: Available

   # 测试查询 SISYS 指标:
   kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/sisys/sisys_agent_sessions_active"
   ```

3. **验证 HPA 能看到外部指标**:
   ```bash
   kubectl describe hpa sisys-app
   # 应显示 External metrics 配置
     --set prometheus.url=http://prometheus-server \
     --set prometheus.port=9090 \
     --set rules.custom[0].seriesQuery='sisys_agent_sessions_active'
   ```

2. **验证 External Metrics API**:
   ```bash
   kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/sisys/sisys_agent_sessions_active"
   ```

3. **配置 HPA 使用自定义指标**:
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: sisys-app
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: sisys-app
     metrics:
       - type: External
         external:
           metric:
             name: sisys_agent_sessions_active
             selector:
               matchLabels:
                 namespace: sisys
           target:
             type: AverageValue
             averageValue: "10"
   ```

## 扩缩容性能要求

| 阶段 | 时间要求 | 说明 |
|------|----------|------|
| 指标采集 | ≤15 秒 | Prometheus scrape_interval |
| HPA 决策 | <60 秒 | HPA 默认同步检查周期 15 秒 |
| Pod 启动 | <180 秒 | ReadinessProbe initialDelaySeconds=30 + 启动时间 |
| **总计** | **<5 分钟** | 端到端扩缩容响应时间 |

## 自定义业务指标

| 指标名称 | 类型 | 说明 | HPA 用途 |
|----------|------|------|----------|
| `sisys_agent_sessions_active` | Gauge | 当前活跃 Agent 会话数 | 扩缩容决策 |
| `sisys_task_queue_length` | Gauge | 任务队列长度 | 扩缩容决策 |
| `sisys_events_processing_rate` | Gauge | 每秒事件处理速率 | 性能监控 |
| `sisys_cache_hit_rate` | Gauge | 缓存命中率（0.0-1.0） | 性能监控 |

## 相关文件

| 文件 | 说明 |
|------|------|
| `service.yaml` | Service 配置（含 Prometheus 注解） |
| `prometheus-servicemonitor.yaml` | Prometheus Operator ServiceMonitor |
| `hpa.yaml` | HPA 资源配置指标配置 |
| `grafana-dashboard.json` | Grafana Dashboard 配置 |
| `grafana-dashboard-configmap.yaml` | Grafana Dashboard Provisioning |

## 参考文档

- [K8s HPA 官方文档](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Prometheus Adapter](https://github.com/prometheus-adapter/prometheus-adapter)
- [Prometheus 指标类型](https://prometheus.io/docs/concepts/metric_types/)
