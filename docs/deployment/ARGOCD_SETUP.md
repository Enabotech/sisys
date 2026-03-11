# ArgoCD v3.3.2 部署指南

**版本：** 1.0
**日期：** 2026-03-05
**适用：** K3S 集群 (Story 0.1-0.3 完成后)

---

## 📋 概述

本指南介绍如何在 K3S 集群上部署 ArgoCD v3.3.2 GitOps 持续部署工具，实现自动化应用部署。

**技术栈:**
- ArgoCD v3.3.2 ✅ (已由 Agimtech 验证)
- Git (代码仓库)
- Kustomize/Helm (配置管理)

---

## 🔧 前置条件

- [ ] K3S 集群已部署 (Story 0.1 ✅)
- [ ] Gitea 已部署 (Story 0.2 ✅)
- [ ] Harbor 已部署 (Story 0.3 ✅)
- [ ] Helm v3 已安装

---

## 📦 步骤 1: 创建命名空间

```bash
# 创建 ArgoCD 命名空间
kubectl create namespace argocd
```

---

## 📦 步骤 2: 安装 ArgoCD

```bash
# 使用官方清单安装
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.3.2/manifests/install.yaml

# 查看部署状态
kubectl get pods -n argocd
kubectl get svc -n argocd

# 等待所有 Pod 就绪
kubectl rollout status deployment/argocd-server -n argocd
kubectl rollout status deployment/argocd-repo-server -n argocd
kubectl rollout status deployment/argocd-applicationset-controller -n argocd
```

---

## 📦 步骤 3: 配置访问

```bash
# 修改服务类型为 NodePort 或 LoadBalancer
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "NodePort"}}'

# 或者配置 Ingress
cat > argocd-ingress.yaml <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server
  namespace: argocd
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
  - host: argocd.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: argocd-server
            port:
              number: 80
EOF

kubectl apply -f argocd-ingress.yaml
```

### 配置本地 hosts

```bash
# 添加 hosts 条目
echo "10.0.0.1 argocd.local" | sudo tee -a /etc/hosts

# 浏览器访问：http://argocd.local
```

---

## 📦 步骤 4: 获取初始密码

```bash
# 获取 admin 初始密码
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 登录 ArgoCD
# 用户名：admin
# 密码：(上一步输出的密码)
```

---

## 📦 步骤 5: 连接 Gitea 仓库

```bash
# 安装 ArgoCD CLI (自动检测最新版本)

# 方法 1: 使用官方安装脚本 (推荐)
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 755 argocd-linux-amd64 /usr/local/bin/argocd
rm argocd-linux-amd64

# 方法 2: 使用 Homebrew (Mac/Linux)
brew install argocd

# 方法 3: 使用 Chocolatey (Windows)
choco install argocd-cli

# 方法 4: 使用 Scoop (Windows)
scoop install argocd

# 验证安装
argocd version --client
# 期望输出：argocd: v3.3.2 (最新稳定版)

# 登录 ArgoCD
argocd login argocd.sisys.local --username admin --password <password> --insecure

# 添加 Gitea 仓库
argocd repo add http://gitea.sisys.local:3000/username/repo.git \
  --username <gitea-username> \
  --password <gitea-password> \
  --insecure-ignore-host-key

# 验证仓库连接
argocd repo list
```

---

## 📦 步骤 6: 创建 Application

```bash
# 创建 Application 示例
cat > my-app.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: http://gitea.local:3000/username/my-app-config.git
    targetRevision: HEAD
    path: manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

kubectl apply -f my-app.yaml
```

---

## ✅ 验收标准

- [ ] ArgoCD v3.3.2 部署成功
- [ ] Git 仓库集成配置完成
- [ ] 多环境 (Dev/Test/Prod) 配置完成
- [ ] 自动同步策略配置完成
- [ ] 可以通过 http://argocd.local 访问

---

**下一步：** `docs/deployment/GITEA_RUNNER_SETUP.md`
