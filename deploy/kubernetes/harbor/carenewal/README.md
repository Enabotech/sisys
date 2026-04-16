# Harbor 证书自动续期配置

> **创建日期**: 2026-04-07
> **CA 类型**: 内部自签 CA (ECDSA P-256)
> **CA 有效期**: 10 年 (2036-04-04)
> **服务证书有效期**: 90 天 (自动续期)

## 目录结构

```
carenewal/
├── internal-ca.crt              # 内部 CA 证书 (公开)
├── internal-ca.key              # 内部 CA 私钥 (⚠️ 敏感, .gitignore)
├── ca-secret-example.yaml       # CA Secret 示例 (脱敏)
├── clusterissuer.yaml           # cert-manager ClusterIssuer
├── certificates-harbor.yaml     # Harbor Certificate 资源
├── certificates-gitea.yaml      # Gitea Certificate 资源
├── certificates-argocd.yaml     # ArgoCD Certificate 资源
├── ca-sync-rbac.yaml           # CA 同步 RBAC 配置
├── ca-sync-job.yaml            # CA 同步 Job
├── certificate-alerts.yaml      # 监控告警规则
├── reloader-annotations.yaml    # Reloader 注解说明
├── registries.yaml              # K3S 镜像仓库配置
├── k3s-internal-ca.crt          # K3S 使用的 CA 证书
├── test-argocd-ca.crt           # 测试用 CA 证书
└── docker-certs/
    └── ca.crt                   # Docker 客户端信任证书
```

## 快速部署

```bash
# 1. 安装 cert-manager
kubectl apply -k https://github.com/stakater/Reloader/deploy/kubernetes/kubernetes

# 2. 创建 CA Secret
kubectl create secret tls sisys-internal-ca \
  --cert=internal-ca.crt \
  --key=internal-ca.key \
  -n cert-manager

# 3. 应用配置
kubectl apply -f clusterissuer.yaml
kubectl apply -f ca-sync-rbac.yaml
kubectl apply -f certificates-harbor.yaml
kubectl apply -f certificates-gitea.yaml
kubectl apply -f certificates-argocd.yaml

# 4. 同步 CA 到所有命名空间
kubectl create job -n cert-manager ca-sync-manual --from=job/ca-cert-sync

# 5. 如果 default 命名空间有工作负载需要信任 Harbor，执行：
kubectl create secret generic ca-certificates \
  --from-file=ca-certificates.crt=/etc/kubernetes/certs/ca.crt \
  -n default --dry-run=client -o yaml | kubectl apply -f -
```

## 安全须知

- ⚠️ `internal-ca.key` 包含 CA 私钥，**绝对不能提交到 Git**
- 🔐 私钥应存储在安全的密钥管理系统中 (Vault/KMS)
- 📁 备份位置: `/etc/kubernetes/certs/` (权限 600)

## 证书续期验证

```bash
# 检查所有证书状态
kubectl get certificate -A

# 触发续期测试
kubectl annotate certificate harbor-tls -n harbor \
  cert-manager.io/issue-temporary-certificate=true --overwrite

# 验证 CA 同步
kubectl get secret ca-certificates -n gitea-advacts -o jsonpath='{.data.ca-certificates\.crt}' | base64 -d | openssl x509 -noout -subject
```
