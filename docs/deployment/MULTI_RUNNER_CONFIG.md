# 多 Runner 配置指南

**Story**: 0.8 - Gitea Runner Configuration
**Task**: 7 - Multi-Runner Configuration
**前置依赖**: Task 1-6 ✅ 已完成

---

## 📋 概述

本指南介绍如何配置多个 Gitea Runner 实例以支持并发 Job 执行，提高 CI/CD Pipeline 的执行效率。

### 架构图

```
┌─────────────┐
│   Gitea     │
│  Repository │
└──────┬──────┘
       │ Webhook
       ▼
┌─────────────────────────────────────────┐
│         Gitea Actions Queue             │
└──────┬────────────────┬─────────────────┘
       │                │
       ▼                ▼
┌─────────────┐  ┌─────────────┐
│  Runner-0   │  │  Runner-1   │
│  (Job 1)    │  │  (Job 2)    │
└─────────────┘  └─────────────┘
       │                │
       ▼                ▼
┌─────────────┐  ┌─────────────┐
│  Runner-2   │  │  Runner-N   │
│  (Job 3)    │  │  (Job N)    │
└─────────────┘  └─────────────┘
```

---

## 🚀 快速开始

### 步骤 1: 验证 Runner 配置

```bash
# 检查 Runner Pods
kubectl get pods -n gitea-actions -l app=gitea-org-runner

# 检查 Runner 标签
kubectl get statefulset gitea-org-runner -n gitea-actions \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="GITEA_RUNNER_LABELS")].value}'
```

### 步骤 2: 配置 Runner 标签

Runner 标签用于标识 Runner 的能力，Pipeline 可以通过 `runs-on` 指定需要的 Runner。

**推荐标签：**
- `linux` / `windows` - 操作系统类型
- `docker` / `k8s` - 执行器类型
- `gpu` - GPU 支持（可选）
- `high-memory` - 高内存（可选）

### 步骤 3: 配置 Runner 副本数

```bash
# 查看当前副本数
kubectl get statefulset gitea-org-runner -n gitea-actions

# 扩展副本数（如果需要）
kubectl scale statefulset gitea-org-runner -n gitea-actions --replicas=5
```

### 步骤 4: 测试并发 Job

```bash
# 运行并发测试脚本
bash scripts/deployment/gitea-runner/test-concurrent-jobs.sh
```

---

## 📁 配置文件说明

### Runner 标签配置

Runner 标签在 StatefulSet 的环境变量中配置：

```yaml
# deploy/kubernetes/gitea-runner/gitea-runner.yaml
spec:
  template:
    spec:
      containers:
      - name: runner
        env:
        - name: GITEA_RUNNER_LABELS
          value: ubuntu-latest,docker,k8s,linux
        - name: GITEA_RUNNER_CAPACITY
          value: "3"  # 每个 Runner 最大并发 Job 数
```

### Runner 分组配置

Runner 分组通过命名空间和标签实现：

```yaml
# 按环境分组
namespace: gitea-actions-dev    # 开发环境 Runner
namespace: gitea-actions-prod   # 生产环境 Runner

# 按项目分组
labels:
  project: sisys
  team: platform
```

---

## 🧪 测试验证

### 测试清单

- [ ] Runner 标签配置正确
- [ ] Runner 副本数 ≥ 3
- [ ] 所有 Runner Pod 运行正常
- [ ] Runner 容量满足并发需求
- [ ] 并发 Job 执行测试通过

### 运行测试

```bash
# 运行测试脚本
bash scripts/deployment/gitea-runner/test-concurrent-jobs.sh

# 运行 pytest 测试
pytest tests/deployment/test_gitea_multi_runner.py -v
```

---

## 🔧 配置详解

### Runner 标签最佳实践

**基础标签（必需）：**
- 操作系统：`linux`, `windows`, `macos`
- 执行器：`docker`, `k8s`

**能力标签（可选）：**
- `gpu` - GPU 加速任务
- `high-memory` - 高内存任务
- `arm64` - ARM 架构
- `self-hosted` - 自托管 Runner

**示例配置：**
```yaml
GITEA_RUNNER_LABELS: ubuntu-latest,docker,k8s,linux,self-hosted
```

### Runner 容量配置

**GITEA_RUNNER_CAPACITY** 定义每个 Runner 实例可同时执行的 Job 数量。

**推荐配置：**
- 小型团队：1-2
- 中型团队：3-5
- 大型团队：5-10

**计算方式：**
```
总并发能力 = Runner 副本数 × 每个 Runner 容量

示例：
3 个 Runner × 容量 3 = 9 个并发 Job
```

### Runner 分组策略

**按环境分组：**
```
gitea-actions-dev   → 开发环境 Pipeline
gitea-actions-test  → 测试环境 Pipeline
gitea-actions-prod  → 生产环境 Pipeline
```

**按项目分组：**
```
gitea-actions-sisys     → SISYS 项目
gitea-actions-platform  → 平台项目
```

---

## 🚨 故障排除

### 问题 1: Job 长时间等待

**症状**: Pipeline 显示 "Waiting for runner"

**解决方案**:
```bash
# 检查 Runner 状态
kubectl get pods -n gitea-actions -l app=gitea-org-runner

# 检查 Runner 标签是否匹配
kubectl get statefulset gitea-org-runner -n gitea-actions \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="GITEA_RUNNER_LABELS")].value}'

# 增加 Runner 副本数
kubectl scale statefulset gitea-org-runner -n gitea-actions --replicas=5
```

---

### 问题 2: Runner 不响应

**症状**: Runner 在 Gitea 页面显示为离线

**解决方案**:
```bash
# 重启 Runner
kubectl rollout restart statefulset gitea-org-runner -n gitea-actions

# 查看 Runner 日志
kubectl logs -n gitea-actions gitea-org-runner-0 --tail=100

# 检查 Token 是否有效
kubectl get secret gitea-org-runner-token -n gitea-actions -o yaml
```

---

### 问题 3: 并发 Job 失败

**症状**: 多个 Job 同时执行时失败

**解决方案**:
1. 检查资源限制（CPU/内存）
2. 增加 Runner 容量
3. 配置 ResourceQuota

```bash
# 查看资源使用
kubectl top pods -n gitea-actions

# 增加容量
kubectl set env statefulset/gitea-org-runner -n gitea-actions \
  GITEA_RUNNER_CAPACITY=5
```

---

## 📊 监控指标

### Prometheus Metrics

```yaml
# Runner 指标
- gitea_actions_runner_idle_count{namespace="gitea-actions"}  # 空闲 Runner 数量
- gitea_actions_runner_busy_count{namespace="gitea-actions"}  # 繁忙 Runner 数量
- gitea_actions_job_queue_depth                              # 等待执行的 Job 数量

# Pod 指标
- kube_pod_status_phase{namespace="gitea-actions",phase="Running"}  # 运行中 Pod
- container_cpu_usage_seconds_total{namespace="gitea-actions"}      # CPU 使用
- container_memory_usage_bytes{namespace="gitea-actions"}           # 内存使用
```

### Grafana 仪表盘

建议创建以下仪表盘：
1. **Runner 健康度** - Pod 状态、在线/离线数量
2. **Job 执行效率** - 队列深度、执行时长、成功率
3. **资源容量** - CPU/内存使用率、并发 Job 数

---

## 📚 参考文档

- [Source: deploy/kubernetes/gitea-runner/gitea-runner.yaml] - Runner 部署配置
- [Source: https://docs.gitea.com/usage/actions/runner] - Gitea Runner 官方文档
- [Source: https://github.com/go-gitea/act_runner] - act_runner GitHub 仓库

---

## ✅ 验收标准

Task 7 完成当以下所有条件满足：

- [x] Runner 标签配置完成（docker, k8s, linux）
- [x] Runner 副本数 ≥ 3
- [x] 所有 Runner Pod 运行正常
- [x] Runner 容量配置满足并发需求
- [x] 并发 Job 测试脚本已创建
- [x] 测试文件已创建：`test_gitea_multi_runner.py`
- [x] 配置文档已创建：`MULTI_RUNNER_CONFIG.md`

---

**最后更新**: 2026-03-22
**维护者**: Agimtech
**状态**: ✅ 完成
