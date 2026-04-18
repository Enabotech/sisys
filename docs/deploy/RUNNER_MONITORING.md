# Runner 监控与日志配置指南

**Story**: 0.8 - Gitea Runner Configuration
**Task**: 8 - Monitoring and Logging Configuration
**前置依赖**: Task 1-7 ✅ 已完成

---

## 📋 概述

本指南介绍如何配置 Gitea Runner 的监控和日志系统，实现 Pipeline 执行的可观测性。

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Gitea Runner Pods                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ Runner-0  │  │ Runner-1  │  │ Runner-2  │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │              │              │                       │
└────────┼──────────────┼──────────────┼───────────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    日志收集层                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  kubectl logs / Fluentd / Loki (可选)               │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    监控指标层                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Prometheus (可选) / Gitea Metrics API              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    可视化层                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Grafana Dashboard (可选)                           │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    告警层                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Alertmanager / Webhook (邮件/钉钉/企业微信)        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 步骤 1: 访问 Runner 日志

```bash
# 查看 Runner 日志
kubectl logs -n gitea-actions gitea-org-runner-0 --tail=50

# 实时跟踪日志
kubectl logs -n gitea-actions gitea-org-runner-0 -f

# 查看所有 Runner 日志
kubectl logs -n gitea-actions -l app=gitea-org-runner --tail=20
```

### 步骤 2: 检查 Runner 状态

```bash
# 查看 Runner Pods
kubectl get pods -n gitea-actions -l app=gitea-org-runner

# 查看 Runner StatefulSet
kubectl get statefulset -n gitea-actions gitea-org-runner

# 查看 Runner 详细信息
kubectl describe statefulset -n gitea-actions gitea-org-runner
```

### 步骤 3: 监控 Pipeline 执行

```bash
# 通过 Gitea Web 界面
# 访问：http://gitea-http.gitea.svc.cluster.local:3000/-/actions

# 查看 Gitea 服务
kubectl get svc -n gitea -l app=gitea
```

---

## 📁 日志配置

### 日志收集方式

**方式 1: kubectl logs（基础）**
```bash
# 查看单个 Pod 日志
kubectl logs -n gitea-actions gitea-org-runner-0

# 查看特定容器日志（多容器 Pod）
kubectl logs -n gitea-actions gitea-org-runner-0 -c runner

# 实时跟踪
kubectl logs -n gitea-actions gitea-org-runner-0 -f --tail=100
```

**方式 2: Fluentd（推荐生产环境）**
```yaml
# deploy/kubernetes/gitea-runner/fluentd-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
  namespace: gitea-actions
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/gitea-org-runner-*.log
      pos_file /var/log/fluentd-containers.log.pos
      tag kubernetes.*
      read_from_head true
      <parse>
        @type json
      </parse>
    </source>

    <match kubernetes.**>
      @type elasticsearch
      host elasticsearch.logging.svc.cluster.local
      port 9200
    </match>
```

**方式 3: Loki（轻量级）**
```yaml
# deploy/kubernetes/gitea-runner/loki-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: loki-config
  namespace: monitoring
data:
  loki.yaml: |
    auth_enabled: false
    server:
      http_listen_port: 3100
    ingester:
      lifecycler:
        address: 127.0.0.1
    schema_config:
      configs:
        - from: 2020-10-24
          store: boltdb-shipper
          object_store: filesystem
          schema: v11
          index:
            prefix: index_
            period: 24h
```

---

## 📊 监控指标

### Runner 关键指标

**Pod 级别指标：**
- `kube_pod_status_phase` - Pod 运行状态
- `container_cpu_usage_seconds_total` - CPU 使用率
- `container_memory_usage_bytes` - 内存使用量
- `kube_pod_container_status_restarts_total` - 重启次数

**Runner 业务指标（通过 Gitea API）：**
- Runner 在线数量
- Job 队列深度
- Job 执行时长
- Job 成功率

### Prometheus 配置（可选）

```yaml
# deploy/kubernetes/gitea-runner/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: gitea-runner
  namespace: gitea-actions
  labels:
    app: gitea-runner
spec:
  selector:
    matchLabels:
      app: gitea-runner
  endpoints:
  - port: http
    interval: 30s
    path: /metrics
```

---

## 🔔 告警配置

### 告警规则（可选）

```yaml
# deploy/kubernetes/gitea-runner/alerting-rules.yaml
groups:
- name: gitea-runner-alerts
  rules:
  # Runner Pod 离线告警
  - alert: GiteaRunnerOffline
    expr: kube_pod_status_phase{namespace="gitea-actions",phase="Running"} < 3
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Gitea Runner Pod 离线"
      description: "Runner Pod {{ $labels.pod }} 已离线超过 5 分钟"

  # Job 队列积压告警
  - alert: GiteaJobQueueBacklog
    expr: gitea_actions_queue_depth > 10
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Gitea Job 队列积压"
      description: "Job 队列深度：{{ $value }}"

  # Runner 高重启率告警
  - alert: GiteaRunnerHighRestartRate
    expr: increase(kube_pod_container_status_restarts_total{namespace="gitea-actions"}[1h]) > 3
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Gitea Runner 高重启率"
      description: "Runner {{ $labels.pod }} 1 小时内重启 {{ $value }} 次"
```

### 通知渠道配置

**邮件通知：**
```yaml
# Alertmanager 配置
receivers:
- name: 'email-notifications'
  email_configs:
  - to: 'devops@example.com'
    from: 'alertmanager@example.com'
    smarthost: 'smtp.example.com:587'
    auth_username: 'alertmanager'
    auth_password: 'password'  # pragma: allowlist secret (example only)
```

**钉钉通知：**
```yaml
receivers:
- name: 'dingtalk-notifications'
  webhook_configs:
  - url: 'https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN'
```

**企业微信通知：**
```yaml
receivers:
- name: 'wechat-notifications'
  webhook_configs:
  - url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY'
```

---

## 📈 构建时长统计

### 数据收集

**通过 Gitea API 获取构建历史：**
```bash
#!/bin/bash
GITEA_URL="http://gitea-http.gitea.svc.cluster.local:3000"
GITEA_TOKEN="YOUR_TOKEN"
REPO="org/repo"

# 获取最近 10 次 Workflow 执行
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/repos/$REPO/actions/runs?limit=10" | jq .
```

### 构建时长分析

**关键指标：**
- 平均构建时长
- P95 构建时长
- 构建成功率
- 最慢的 Workflow

**Grafana 查询示例：**
```promql
# 平均 Job 执行时长
avg(gitea_actions_job_duration_seconds)

# P95 执行时长
histogram_quantile(0.95, rate(gitea_actions_job_duration_seconds_bucket[5m]))

# 构建成功率
sum(rate(gitea_actions_job_result{result="success"}[5m]))
/
sum(rate(gitea_actions_job_result[5m]))
```

---

## 🚨 故障排除

### 问题 1: Runner 日志无法访问

**症状**: `kubectl logs` 返回错误

**解决方案**:
```bash
# 检查 Pod 状态
kubectl get pods -n gitea-actions -l app=gitea-org-runner

# 检查 Pod 事件
kubectl describe pod -n gitea-actions gitea-org-runner-0

# 查看上一个实例的日志（如果 Pod 重启了）
kubectl logs -n gitea-actions gitea-org-runner-0 --previous
```

---

### 问题 2: 监控指标缺失

**症状**: Prometheus 中没有 Runner 指标

**解决方案**:
1. 检查 Gitea 是否暴露 metrics 端点
2. 验证 ServiceMonitor 配置
3. 检查 Prometheus 配置

```bash
# 检查 Gitea metrics 端点
kubectl port-forward -n gitea svc/gitea-http 3000:3000
curl http://localhost:3000/metrics

# 检查 ServiceMonitor
kubectl get servicemonitor -n gitea-actions
```

---

### 问题 3: 告警未触发

**症状**:  Runner 离线但未收到告警

**解决方案**:
1. 检查 Alertmanager 配置
2. 验证告警规则
3. 测试通知渠道

```bash
# 检查 Alertmanager 状态
kubectl get pods -n monitoring -l app=alertmanager

# 查看告警规则
kubectl get prometheusrules -n monitoring

# 测试 Webhook
curl -X POST https://webhook.site/your-unique-id
```

---

## 📚 参考文档

- [Source: deploy/kubernetes/gitea-runner/gitea-actions-complete.yaml] - Runner StatefulSet 配置
- [Source: https://docs.gitea.com/usage/actions/runner] - Gitea Runner 官方文档
- [Source: https://prometheus.io/docs/prometheus/latest/configuration/configuration/] - Prometheus 配置文档
- [Source: https://grafana.com/docs/grafana/latest/datasources/prometheus/] - Grafana Prometheus 数据源

---

## ✅ 验收标准

Task 8 完成当以下所有条件满足：

- [x] Runner 日志可访问（kubectl logs）
- [x] Runner 状态可监控（kubectl get pods）
- [x] 监控配置文档已创建
- [x] 测试文件已创建：`test_gitea_monitoring.py`
- [x] 监控脚本已创建（可选）

---

**最后更新**: 2026-03-22
**维护者**: Agimtech
**状态**: ✅ 完成
