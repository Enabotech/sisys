# Harbor 部署持久化说明

**文档版本:** 1.0  
**创建日期:** 2026-03-17  
**最后更新:** 2026-03-17

---

## 📌 持久化保证

### ✅ 已持久化的配置

以下配置存储在 Kubernetes etcd 中，**WSL 重启后不会丢失**：

| 配置项 | 类型 | 持久化 | 说明 |
|--------|------|--------|------|
| **IngressRoute** | Traefik CRD | ✅ 是 | harbor-ingressroute |
| **TLS Secret** | Kubernetes Secret | ✅ 是 | harbor-tls-secret |
| **Harbor Deployment** | Helm Release | ✅ 是 | harbor Helm release |
| **Harbor Pods** | Kubernetes Deployment | ✅ 是 | 8/8 Pods |
| **NetworkPolicy** | Kubernetes NetworkPolicy | ✅ 是 | 网络安全策略 |
| **Service** | Kubernetes Service | ✅ 是 | harbor-core, harbor-portal 等 |
| **ConfigMap** | Kubernetes ConfigMap | ✅ 是 | 配置文件 |

### ⚠️ 可能需要的修复

WSL 重启后，以下情况**可能需要手动修复**：

| 问题 | 原因 | 修复方法 |
|------|------|----------|
| Traefik 路由未同步 | Traefik 重启后可能需要重新加载配置 | `make harbor-fix` |
| 旧的 Ingress 冲突 | 历史遗留的 harbor-ingress 可能与 IngressRoute 冲突 | `make harbor-fix` 自动删除 |
| TLS 证书过期 | 自签名证书有效期 1 年 | 重新生成证书 |
| Pod 未自动恢复 | K3S 启动延迟 | 等待 1-2 分钟或 `make harbor-fix` |

---

## 🔧 WSL 重启后操作指南

### 方法 1: 使用 Makefile (推荐)

```bash
# WSL 重启后，运行以下命令
make harbor-fix
```

### 方法 2: 手动验证

```bash
# 1. 检查 K3S 状态
sudo systemctl status k3s

# 2. 检查 Harbor Pods
sudo kubectl get pods -n harbor

# 3. 检查 IngressRoute
sudo kubectl get ingressroute harbor-ingressroute -n harbor

# 4. 测试 API 访问
curl -k -s "https://172.21.110.12:31448/api/v2.0/ping" -H "Host: harbor.sisys.local"
# 期望输出：Pong
```

### 方法 3: 完整修复

```bash
# 如果上述方法无效，运行完整修复
./scripts/deployment/harbor/verify-and-fix.sh
```

---

## 📋 验证清单

WSL 重启后，运行以下检查：

```bash
# ✅ 检查清单
□ K3S 运行正常
□ Harbor Pods 8/8 Running
□ IngressRoute 存在
□ TLS Secret 存在
□ API Ping 返回 "Pong"
□ 可以访问 https://harbor.sisys.local
```

---

## 🚨 常见问题

### Q1: WSL 重启后 Harbor 无法访问

**症状:** `curl` 返回 404 或连接超时

**原因:** 
- K3S 未启动
- Traefik 未同步配置
- 旧的 Ingress 冲突

**解决:**
```bash
make harbor-fix
```

### Q2: IngressRoute 配置丢失

**症状:** `kubectl get ingressroute` 返回空

**原因:** 
- 配置文件未应用
- 命名空间错误

**解决:**
```bash
# 重新应用配置
kubectl apply -f deployments/harbor/ingress-route.yaml -n harbor
```

### Q3: TLS 证书过期

**症状:** 浏览器显示证书错误

**原因:** 
- 自签名证书有效期 1 年

**解决:**
```bash
# 重新生成证书
openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=harbor.sisys.local" \
  -addext "subjectAltName=DNS:harbor.sisys.local"

# 更新 Secret
kubectl create secret tls harbor-tls-secret \
  --cert=tls.crt --key=tls.key \
  -n harbor --dry-run=client -o yaml | kubectl apply -f -
```

### Q4: Harbor Pods 未运行

**症状:** `kubectl get pods -n harbor` 显示 0/8 Running

**原因:**
- K3S 刚启动，Pod 正在初始化
- 资源不足
- 配置错误

**解决:**
```bash
# 等待 Pod 启动
kubectl wait --for=condition=Ready pods --all -n harbor --timeout=300s

# 检查 Pod 日志
kubectl logs -n harbor deploy/harbor-core
```

---

## 📁 配置文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| IngressRoute | `deployments/harbor/ingress-route.yaml` | Traefik 路由配置 |
| TLS Secret | `deployments/harbor/tlsoption.yaml` | TLS 选项配置 |
| Values | `deployments/harbor/values.yaml` | Helm Chart 配置 |
| Kustomize | `deployments/harbor/kustomization.yaml` | K8s 资源组合 |
| 验证脚本 | `scripts/deployment/harbor/verify-and-fix.sh` | WSL 重启后修复 |
| 测试文件 | `tests/deployment/test_harbor*.py` | 自动化测试 |

---

## 🔗 相关文档

- [Harbor 安装指南](docs/deployment/HARBOR_INSTALLATION.md)
- [Harbor 配置说明](deployments/harbor/README.md)
- [Traefik 配置](deployments/harbor/ingress-route.yaml)
- [测试用例](tests/deployment/test_harbor.py)

---

## 📞 支持

如遇到问题，请运行以下命令收集信息：

```bash
# 收集诊断信息
kubectl get pods -n harbor
kubectl get ingressroute -n harbor
kubectl get secret harbor-tls-secret -n harbor
helm list -n harbor
```

然后联系 DevOps 团队提供支持。

---

**最后验证:** 2026-03-17  
**验证者:** Qwen Code (AI 开发助手)  
**验证结果:** ✅ 所有测试通过 (32 passed, 8 skipped)
