# Gitea Runner TLS 证书配置方案

## 🎯 问题描述

Gitea Runner 通过 HTTPS 访问 Gitea 时出现 TLS 证书验证失败：

```
level=error msg="Cannot ping the Gitea instance server"
  error="unavailable: tls: failed to verify certificate:
  x509: certificate signed by unknown authority"
```

**根本原因**: Gitea 使用自签名证书，Runner Pod 不信任该证书。

---

## 🔧 解决方案对比

| 方案 | 复杂度 | 安全性 | 推荐场景 |
|------|--------|--------|----------|
| 内部 HTTP | ⭐ | ⭐⭐ | 开发/测试 |
| CA 证书挂载 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 生产环境 ✅ |
| cert-manager | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 多服务 |
| Service Mesh | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 大规模 |

---

## ✅ 推荐方案：CA 证书挂载

### 步骤 1: 获取 Gitea TLS 证书

**方法 A: 从 Traefik Secret 获取**

```bash
# 找到 Traefik TLS Secret
kubectl get secret -n gitea | grep -i tls

# 提取证书
kubectl get secret <tls-secret-name> -n gitea \
  -o jsonpath='{.data.tls\.crt}' | base64 -d > gitea-ca.crt
```

**方法 B: 从浏览器导出**

1. 访问 `https://gitea.sisys.local`
2. 点击地址栏锁图标
3. 点击"证书有效"
4. 选择"详细信息" → "导出"
5. 保存为 `gitea-ca.crt` (Base64 编码 X.509)

**方法 C: 使用脚本自动获取**

```bash
chmod +x scripts/deployment/gitea-runner/configure-tls-ca.sh
bash scripts/deployment/gitea-runner/configure-tls-ca.sh
```

### 步骤 2: 创建 ConfigMap

```bash
kubectl create configmap gitea-tls-ca \
  --from-file=ca.crt=gitea-ca.crt \
  -n gitea-actions
```

### 步骤 3: 更新 Runner 配置

编辑 `gitea-runner.yaml`：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitea-tls-ca
  namespace: gitea-actions
data:
  ca.crt: |
    -----BEGIN CERTIFICATE-----
    (CA 证书内容)
    -----END CERTIFICATE-----
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitea-runner
  namespace: gitea-actions
spec:
  template:
    spec:
      containers:
        - name: runner
          image: docker.io/gitea/act_runner:0.3.0
          env:
            - name: GITEA_INSTANCE_URL
              value: "https://gitea.sisys.local"
            # 指定 CA 证书路径
            - name: NODE_EXTRA_CA_CERTS
              value: "/etc/ssl/certs/gitea-ca.crt"
            - name: REQUESTS_CA_BUNDLE
              value: "/etc/ssl/certs/gitea-ca.crt"
          volumeMounts:
            - name: ca-certs
              mountPath: /etc/ssl/certs/gitea-ca.crt
              subPath: ca.crt
              readOnly: true
      volumes:
        - name: ca-certs
          configMap:
            name: gitea-tls-ca
```

### 步骤 4: 应用配置

```bash
kubectl apply -f gitea-runner.yaml
```

### 步骤 5: 验证

```bash
# 查看 Pod 状态
kubectl get pods -n gitea-actions -l app=gitea-runner

# 查看日志确认 TLS 验证成功
kubectl logs -n gitea-actions -l app=gitea-runner --tail=20 | grep -E "ping|SUCCESS"

# 预期输出:
# level=debug msg="Successfully pinged the Gitea instance server"
# level=info msg="Runner registered successfully."
# SUCCESS
```

---

## 🔍 故障排除

### 问题 1: 证书格式错误

**症状**: Pod 启动失败，日志显示证书解析错误

**解决方案**:
```bash
# 验证证书格式
openssl x509 -in gitea-ca.crt -text -noout

# 确保证书是 PEM 格式
head -1 gitea-ca.crt  # 应显示 -----BEGIN CERTIFICATE-----
```

### 问题 2: ConfigMap 未正确挂载

**症状**: Runner 仍然报 TLS 验证错误

**解决方案**:
```bash
# 检查 ConfigMap 是否存在
kubectl get configmap gitea-tls-ca -n gitea-actions

# 检查 Pod 中证书文件
kubectl exec -n gitea-actions <pod-name> -- cat /etc/ssl/certs/gitea-ca.crt

# 检查环境变量
kubectl exec -n gitea-actions <pod-name> -- env | grep CA
```

### 问题 3: 证书过期

**症状**: 之前正常，突然 TLS 验证失败

**解决方案**:
```bash
# 检查证书有效期
openssl x509 -in gitea-ca.crt -noout -dates

# 更新证书
kubectl create configmap gitea-tls-ca \
  --from-file=ca.crt=new-gitea-ca.crt \
  -n gitea-actions \
  --dry-run=client -o yaml | kubectl apply -f -

# 重启 Pod
kubectl rollout restart deployment/gitea-runner -n gitea-actions
```

---

## 📊 方案选择决策树

```
是否需要 HTTPS?
├─ 否 → 使用内部 HTTP (当前方案)
│   GITEA_INSTANCE_URL=http://gitea-http.gitea.svc.cluster.local:3000
│
└─ 是 → 是否有证书管理基础设施？
    ├─ 否 → CA 证书挂载 (推荐)
    │   挂载 ConfigMap 到 Pod
    │
    ├─ 是 → 是否使用 cert-manager?
    │   ├─ 是 → Certificate 资源自动管理
    │   └─ 否 → 是否使用 Service Mesh?
    │       ├─ 是 → Istio mTLS 自动处理
    │       └─ 否 → CA 证书挂载
```

---

## 📖 参考文档

- [Kubernetes ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Node.js TLS 配置](https://nodejs.org/api/tls.html)
- [OpenSSL 证书管理](https://www.openssl.org/docs/man1.1.1/man1/x509.html)
