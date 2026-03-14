# Cosign 镜像签名指南

**Story 0.6: Harbor 镜像仓库**
**版本:** 1.0
**日期:** 2026-03-14

---

## 📋 目录

1. [概述](#概述)
2. [Cosign 简介](#cosign-简介)
3. [安装 Cosign](#安装-cosign)
4. [Keyless 签名（推荐）](#keyless-签名推荐)
5. [密钥对签名](#密钥对签名)
6. [Kubernetes 集成](#kubernetes-集成)
7. [CI/CD Pipeline 集成](#cicd-pipeline-集成)
8. [最佳实践](#最佳实践)

---

## 概述

Cosign 是 Sigstore 项目的一部分，用于容器镜像的签名和验证。与传统的 Notary 相比，Cosign 提供了更现代、更安全的签名方案。

### Cosign vs Notary

| 特性 | Cosign | Notary (已弃用) |
|------|--------|----------------|
| 密钥管理 | 支持 keyless（无需管理密钥） | 必须管理密钥 |
| 透明日志 | ✅ Rekor 透明日志 | ❌ 无 |
| 身份验证 | OIDC（Google、GitHub 等） | 密钥对 |
| Kubernetes 集成 | ✅ 原生支持 | ⚠️ 有限 |
| 社区支持 | ✅ 活跃开发 | ❌ 已弃用 |
| SLSA 合规 | ✅ 符合 | ❌ 不符合 |

### 签名方式对比

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **Keyless** | 无需管理密钥、自动化友好 | 需要 OIDC 提供商 | CI/CD Pipeline |
| **密钥对** | 离线签名、完全控制 | 需要安全存储密钥 | 本地开发、离线环境 |

---

## Cosign 简介

### 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                    Sigstore 生态系统                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Fulcio    │  │    Rekor    │  │    Cosign   │     │
│  │             │  │             │  │             │     │
│  │  证书颁发   │  │  透明日志   │  │  签名工具   │     │
│  │  (CA)       │  │  (Log)      │  │  (Signer)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

- **Fulcio**: 免费的短期证书颁发机构（用于 keyless 签名）
- **Rekor**: 透明日志，记录所有签名操作
- **Cosign**: 签名和验证工具

### Keyless 签名流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  开发者   │     │  Fulcio  │     │  Harbor  │     │  Rekor   │
│          │     │          │     │          │     │          │
│  1. 请求  │────▶│  2. OIDC │     │          │     │          │
│  证书    │     │  验证    │     │          │     │          │
│          │     │          │     │          │     │          │
│          │◀────│  3. 颁发 │     │          │     │          │
│          │     │  证书    │     │          │     │          │
│          │     │          │     │          │     │          │
│  4. 签名 │     │          │     │  5. 推送 │     │          │
│  镜像    │────▶│          │────▶│  签名    │     │          │
│          │     │          │     │          │     │          │
│          │     │          │     │          │  6. 记录 │     │
│          │     │          │     │          │────▶│  签名    │
│          │     │          │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

## 安装 Cosign

### 方式 1: macOS (Homebrew)

```bash
# 安装
brew install sigstore/cosign/cosign

# 验证安装
cosign version

# 输出示例：
# GitVersion:    v2.2.3
# GitCommit:     abc123...
# GitTreeState:  clean
# BuildDate:     2024-01-01T00:00:00Z
# GoVersion:     go1.21.0
# Compiler:      gc
# Platform:      darwin/amd64
```

### 方式 2: Linux

```bash
# 下载
wget -q https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64

# 安装
sudo mv cosign-linux-amd64 /usr/local/bin/cosign
chmod +x /usr/local/bin/cosign

# 验证
cosign version
```

### 方式 3: Docker

```bash
# 使用 Docker 运行 Cosign（无需安装）
docker run --rm -it gcr.io/projectsigstore/cosign:v2.2.3 version
```

---

## Keyless 签名（推荐）

### 前置条件

1. **OIDC 账户**: Google、GitHub、Microsoft 等账户
2. **Cosign 安装**: v2.0+
3. **Harbor 访问**: 已登录 Harbor

### 步骤 1: 推送镜像

```bash
# 登录 Harbor
docker login harbor.sisys.local -u admin -p Harbor@2026Secure!

# 构建镜像
docker build -t harbor.sisys.local/sisys/myapp:latest .

# 推送镜像
docker push harbor.sisys.local/sisys/myapp:latest
```

### 步骤 2: 签名镜像

```bash
# Keyless 签名（使用 OIDC）
cosign sign harbor.sisys.local/sisys/myapp:latest

# 流程：
# 1. 浏览器打开 OIDC 登录页面（Google/GitHub）
# 2. 登录并授权
# 3. Fulcio 颁发短期证书
# 4. Cosign 使用证书签名镜像
# 5. 签名记录到 Rekor 透明日志

# 输出示例：
# Opening browser to https://oauth2.sigstore.dev/auth/...
# tlog entry created with index: 12345678
# Pushing signature to: harbor.sisys.local/sisys/myapp:latest
```

### 步骤 3: 验证签名

```bash
# 验证签名
cosign verify \
  --certificate-identity-regexp=".*@sisys.local" \
  --certificate-oidc-issuer="https://accounts.google.com" \
  harbor.sisys.local/sisys/myapp:latest

# 输出示例：
# Verification for harbor.sisys.local/sisys/myapp:latest --
# The following checks were performed on each of these signatures:
#   - The cosign claims were validated
#   - Existence of the claims in the transparency log was verified offline
#   - The code-signing certificate was verified using trusted certificate issuer certificates
#
# ✓ Verification successful
```

### 步骤 4: 查看签名详情

```bash
# 查看签名详情
cosign tree harbor.sisys.local/sisys/myapp:latest

# 输出示例：
# 📦 Supply Chain Security Related artifacts for harbor.sisys.local/sisys/myapp:latest
# └── 📦 SBOMs for harbor.sisys.local/sisys/myapp:latest
# └── 🔐 Signatures for harbor.sisys.local/sisys/myapp:latest
#     └── 🍒 sha256:abc123...
```

---

## 密钥对签名

### 适用场景

- ✅ 离线环境签名
- ✅ 需要完全控制密钥
- ✅ 无 OIDC 提供商环境

### 步骤 1: 生成密钥对

```bash
# 生成密钥对
cosign generate-key-pair

# 输入密码保护私钥（至少 8 位）
# 生成文件：
# - cosign.key (私钥，加密存储)
# - cosign.pub (公钥)
```

### 步骤 2: 将公钥导入 Harbor

1. **登录 Harbor Web 界面**
   - 访问：http://harbor.harbor.svc.cluster.local
   - 用户名：`admin`
   - 密码：`Harbor@2026Secure!`

2. **添加可信密钥**
   - 进入项目 `sisys`
   - 点击"配置" → "可信密钥"
   - 点击"新建可信密钥"
   - 粘贴 `cosign.pub` 内容
   - 保存

### 步骤 3: 签名镜像

```bash
# 使用密钥对签名
cosign sign --key cosign.key harbor.sisys.local/sisys/myapp:latest

# 输入私钥密码
# 签名成功后推送到 Harbor
```

### 步骤 4: 验证签名

```bash
# 使用公钥验证
cosign verify --key cosign.pub harbor.sisys.local/sisys/myapp:latest

# 输出示例：
# ✓ Verification successful
```

---

## Kubernetes 集成

### 方式 1: 部署时验证（推荐）

使用 **Kyverno** 或 **OPA Gatekeeper** 在部署时验证镜像签名：

```yaml
# kyverno-cosign-policy.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-cosign-signature
spec:
  validationFailureAction: enforce
  background: false
  rules:
  - name: verify-cosign-keyless
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      image:
        references:
        - "harbor.sisys.local/*"
        verifyDigest: true
        attestors:
        - count: 1
          entries:
          - keyless:
              url: https://rekor.sigstore.dev
              certificate-identity-regexp: ".*@sisys.local"
              certificate-oidc-issuer: "https://accounts.google.com"
```

应用策略：

```bash
kubectl apply -f kyverno-cosign-policy.yaml
```

### 方式 2: 使用 Cosign Webhook

```bash
# 安装 Cosign Webhook
helm install cosign cosign/cosign \
  -n cosign-system \
  --create-namespace

# 配置验证策略
kubectl apply -f cosign-webhook-config.yaml
```

---

## CI/CD Pipeline 集成

### Gitea Actions 示例

```yaml
# .gitea/workflows/ci-cd.yml
name: CI/CD with Cosign Signing

on:
  push:
    branches: [main]

jobs:
  build-and-sign:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # Keyless 签名需要
      packages: write

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Login to Harbor
      uses: docker/login-action@v2
      with:
        registry: harbor.sisys.local
        username: ${{ secrets.HARBOR_USERNAME }}
        password: ${{ secrets.HARBOR_PASSWORD }}

    - name: Build and push image
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: harbor.sisys.local/sisys/myapp:${{ github.sha }}

    - name: Install Cosign
      uses: sigstore/cosign-installer@v3
      with:
        cosign-release: 'v2.2.3'

    - name: Sign image (keyless)
      run: |
        cosign sign harbor.sisys.local/sisys/myapp:${{ github.sha }}

    - name: Verify image
      run: |
        cosign verify \
          --certificate-identity-regexp=".*@sisys.local" \
          --certificate-oidc-issuer="https://accounts.google.com" \
          harbor.sisys.local/sisys/myapp:${{ github.sha }}
```

### 环境变量配置

在 Gitea 中配置 Secrets：

```bash
# Harbor 认证
HARBOR_USERNAME: admin
HARBOR_PASSWORD: Harbor@2026Secure!

# OIDC 配置（如使用 GitHub Actions）
# 需要配置 GitHub OIDC 信任关系
```

---

## 最佳实践

### 1. Keyless 优先

✅ **推荐**: CI/CD Pipeline 使用 keyless 签名
- 无需管理密钥
- 自动化友好
- 符合零信任安全模型

### 2. 证书身份验证

配置严格的证书身份验证策略：

```bash
# 限制特定域名
--certificate-identity-regexp=".*@sisys.local"

# 限制 OIDC 提供商
--certificate-oidc-issuer="https://accounts.google.com"
```

### 3. 透明日志验证

始终验证签名是否记录到 Rekor：

```bash
# 验证时自动检查 Rekor
cosign verify \
  --certificate-identity-regexp=".*@sisys.local" \
  harbor.sisys.local/sisys/myapp:latest
```

### 4. 多因素验证

结合多种验证方式：

```bash
# 验证签名 + SBOM +  attestations
cosign verify \
  --certificate-identity-regexp=".*@sisys.local" \
  --type=cosign \
  harbor.sisys.local/sisys/myapp:latest

# 验证 SBOM
cosign verify-blob \
  --certificate-identity-regexp=".*@sisys.local" \
  sbom.json
```

### 5. 密钥管理（如使用密钥对）

- ✅ 使用 HSM 或 KMS 存储私钥
- ✅ 定期轮换密钥
- ✅ 限制密钥访问权限
- ❌ 不要将私钥提交到 git

### 6. 镜像标签策略

```bash
# ✅ 推荐：使用不可变标签（SHA）
cosign sign harbor.sisys.local/sisys/myapp@sha256:abc123...

# ⚠️ 谨慎：可变标签（latest）
cosign sign harbor.sisys.local/sisys/myapp:latest
```

---

## 故障排查

### 问题 1: OIDC 登录失败

**症状**: `Error: opening browser: exec: "xdg-open": executable file not found`

**原因**: 无图形界面环境无法打开浏览器

**解决**:
```bash
# 使用静态令牌
export SIGSTORE_OIDC_TOKEN=$(cat token.txt)
cosign sign harbor.sisys.local/sisys/myapp:latest
```

### 问题 2: 验证失败 - 证书不匹配

**症状**: `Error: certificate identity does not match`

**原因**: 证书身份与验证策略不匹配

**解决**:
```bash
# 检查实际证书身份
cosign verify \
  --certificate-identity-regexp=".*" \
  harbor.sisys.local/sisys/myapp:latest \
  --format=json | jq '.[].Certificate.Subject'

# 调整验证策略
--certificate-identity-regexp="正确身份"
```

### 问题 3: Rekor 超时

**症状**: `Error: Rekor API timeout`

**原因**: 网络连接问题或 Rekor 服务不可用

**解决**:
```bash
# 检查 Rekor 服务状态
curl -I https://rekor.sigstore.dev

# 重试签名（Rekor 可能暂时不可用）
cosign sign harbor.sisys.local/sisys/myapp:latest
```

---

## 参考文档

- [Cosign 官方文档](https://docs.sigstore.dev/cosign/)
- [Sigstore 项目](https://www.sigstore.dev/)
- [SLSA 框架](https://slsa.dev/)
- [Kubernetes 镜像验证](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)

---

**文档维护者:** DevOps Team
**最后更新:** 2026-03-14
