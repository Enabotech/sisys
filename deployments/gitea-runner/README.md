# Gitea Runner 配置说明

## 📋 文件清单

```
deployments/gitea-runner/
├── gitea-runner.yaml           # 主配置文件 (唯一需要应用的)
├── gitea-runner-token-secret.yaml  # Token Secret 模板
├── Chart.yaml                  # Helm Chart 定义
└── values.yaml                 # Helm values (可选)
```

## 🚀 快速部署

### 前置条件

1. **Token 已配置**
   ```bash
   kubectl create secret generic gitea-runner-token \
     --from-literal=token=YOUR_TOKEN \
     -n gitea-actions
   ```

2. **Gitea 地址配置**
   - **外部访问**: `https://gitea.sisys.local/`
   - **内部访问**: `http://gitea-http.gitea.svc.cluster.local:3000`
   - 配置使用内部 HTTP 地址避免 TLS 证书问题
   - 如需使用 HTTPS，请编辑 `gitea-runner.yaml` 中的 `GITEA_INSTANCE_URL`

### 部署命令

```bash
# 一键部署
kubectl apply -f deployments/gitea-runner/gitea-runner.yaml

# 验证部署
kubectl get pods -n gitea-actions -l app=gitea-runner
```

## ⚙️ 配置说明

### 核心配置项

| 配置项 | 默认值 | 说明 | 修改方法 |
|--------|--------|------|---------|
| **replicas** | 3 | Runner 副本数 | 编辑 Deployment.spec.replicas |
| **image** | `gitea/act_runner:0.3.0` | Runner 镜像 | 编辑 Deployment.spec.template.spec.containers[0].image |
| **GITEA_INSTANCE_URL** | `http://gitea-http.gitea.svc.cluster.local:3000` | Gitea 内部地址 | 编辑 env 配置 |
| **GITEA_RUNNER_NAME** | `k8s-runner` | Runner 名称 | 编辑 env 配置 |
| **GITEA_RUNNER_LABELS** | `docker,k8s,standard` | Runner 标签 | 编辑 env 配置 |

**外部访问配置**:
如需使用 `https://gitea.sisys.local/`，需要配置 TLS 证书验证或使用 `insecure: true` 选项。

### 资源限制

| 资源 | Request | Limit |
|------|---------|-------|
| **CPU** | 250m | 2000m |
| **Memory** | 512Mi | 2Gi |

### 卷挂载

| 卷名 | 类型 | 路径 | 说明 |
|------|------|------|------|
| **containerd-sock** | hostPath | `/run/k3s/containerd/containerd.sock` | K3s containerd socket |
| **runner-config** | emptyDir | `/root/.config/act_runner` | Runner 配置目录 |

## 🔍 故障排除

### 查看日志

```bash
# 查看所有 Runner 日志
kubectl logs -n gitea-actions -l app=gitea-runner

# 查看特定 Pod 日志
kubectl logs -n gitea-actions gitea-runner-xxxxx-xxxxx
```

### 常见问题

#### 1. Pod 无法启动

```bash
# 检查 Pod 状态
kubectl describe pod -n gitea-actions -l app=gitea-runner

# 检查事件
kubectl get events -n gitea-actions --sort-by='.lastTimestamp'
```

#### 2. Runner 无法连接 Gitea

```bash
# 验证 Gitea 地址
kubectl exec -n gitea-actions gitea-runner-xxxxx-xxxxx -- curl http://10.42.0.5:3000/api/v1/version

# 检查 Token
kubectl get secret gitea-runner-token -n gitea-actions -o jsonpath='{.data.token}' | base64 -d
```

#### 3. Runner 显示离线

```bash
# 重启 Runner
kubectl rollout restart deployment/gitea-runner -n gitea-actions

# 验证状态
kubectl get pods -n gitea-actions -l app=gitea-runner
```

## 📊 监控指标

### Pod 状态

```bash
kubectl get pods -n gitea-actions -l app=gitea-runner -o wide
```

### 资源使用

```bash
kubectl top pods -n gitea-actions -l app=gitea-runner
```

## 🧹 卸载

```bash
# 删除所有资源
kubectl delete -f deployments/gitea-runner/gitea-runner.yaml

# 删除命名空间
kubectl delete namespace gitea-actions

# 删除 Secret
kubectl delete secret gitea-runner-token -n gitea-actions
```

## 📖 参考文档

- [Gitea Runner 官方文档](https://docs.gitea.com/usage/actions/runner)
- [Story 0.8](../../../_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md)
- [K3s containerd 配置](https://docs.k3s.io/advanced#containerd)
