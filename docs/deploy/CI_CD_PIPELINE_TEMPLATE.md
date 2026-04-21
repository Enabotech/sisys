# CI/CD Pipeline 模板使用指南

## 目录

1. [概述](#概述)
2. [架构设计](#架构设计)
3. [快速开始](#快速开始)
4. [Pipeline 阶段详解](#pipeline-阶段详解)
5. [配置参数](#配置参数)
6. [Secrets 配置](#secrets-配置)
7. [GPU 任务调度](#gpu-任务调度)
8. [预构建镜像系统](#预构建镜像系统)
9. [故障排除](#故障排除)
10. [最佳实践](#最佳实践)

---

## 概述

本 CI/CD Pipeline 模板为 SISYS 项目提供标准化的持续集成和持续部署流程，包含以下特性：

- ✅ **7 个标准阶段**：代码质量 → 单元测试 → 集成测试 → 安全扫描 → 镜像构建 → 镜像推送 → 自动部署
- ✅ **三层镜像架构**：Layer 1 (基础) + Layer 2 (依赖) + Layer 3 (应用)
- ✅ **GPU 任务调度**：自动识别 GPU 任务并调度到 GPU 节点
- ✅ **性能优化**：预构建依赖镜像，CI 时间缩短 60-70%
- ✅ **安全合规**：Trivy + Bandit 双重安全扫描
- ✅ **自动回滚**：部署失败自动回滚到稳定版本

### 性能对比

| 指标 | 原方案 | 优化后 | 提升 |
|------|--------|--------|------|
| **依赖安装** | 每次 5-10 分钟 | 0 分钟 (预装) | **100%** |
| **镜像构建** | 10-15 分钟 | 5-8 分钟 | **50%** |
| **CI 总时长** | 25-35 分钟 | 8-12 分钟 | **65%** |
| **GPU 测试** | 不支持 | 支持 | **新增** |

---

## 架构设计

### 三层镜像架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 官方基础镜像 (ubuntu:22.04)                             │
│  来源：harbor.sisys.local/sisys/tools/ubuntu:22.04        │
│  大小：~8GB                                                  │
│  更新：手动 (版本升级时)                                     │
│  推送到：harbor.sisys.local/sisys/dependency:l1-latest │
└─────────────────────────────────────────────────────────────┘
                            ↓ docker pull
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: 项目依赖镜像 (Poetry 安装)                          │
│  来源：每周构建 + 依赖变更触发                               │
│  大小：+1-2GB                                                │
│  更新：每周日 18 点 + pyproject.toml/poetry.lock 变更          │
│  推送到：harbor.sisys.local/sisys/dependency:{git-sha}       │
│  清理：保留最近 5 个版本                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓ docker build
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 应用镜像 (业务代码)                                │
│  来源：每次 CI 构建                                          │
│  大小：~2GB (增量层)                                         │
│  更新：每次代码提交                                          │
│  推送到：harbor.sisys.local/sisys/app:{git-sha}              │
└─────────────────────────────────────────────────────────────┘
```

### 完整架构图

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 基础镜像                                  │
│  harbor.sisys.local/sisys/dependency:l1-latest    │
│  (手动导入，不常更新)                                        │
└─────────────────────────────────────────────────────────────┘
                      │ docker pull
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  【独立工作流】Build Dependency Image                       │
│  触发：每周日 18:00 或 pyproject.toml 变更                   │
│                                                             │
│  Layer 2: 项目依赖镜像                                      │
│  harbor.sisys.local/sisys/dependency:{GIT_SHA}              │
│  (预装 Poetry 所有依赖)                                      │
└─────────────────────────────────────────────────────────────┘
                      │ docker pull
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  【CI Pipeline】代码提交触发                                │
│                                                             │
│  jobs:                                                      │
│    - code-quality  ──┐                                      │
│    - unit-tests    ──┤  使用 Layer 2 镜像                   │
│    - integration   ──┤  (无需安装依赖)                      │
│    - security      ──┘                                      │
│         │                                                   │
│         ▼                                                   │
│  【镜像构建】基于 Layer 2 构建 Layer 3                      │
│  Layer 3: 应用镜像                                          │
│  harbor.sisys.local/sisys/app:v1.0.0-{GIT_SHA}                     │
│  (只包含业务代码，增量层)                                    │
└─────────────────────────────────────────────────────────────┘
                      │ docker push
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Harbor 仓库                                                │
│  /sisys/app:{GIT_SHA}                                       │
└─────────────────────────────────────────────────────────────┘
                      │ ArgoCD 检测
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  ArgoCD 自动同步                                            │
│  sisys-app-dev / sisys-app-test / sisys-app-prod            │
└─────────────────────────────────────────────────────────────┘
```

### Layer 2 执行位置详解

**Layer 2 不是在 CI Pipeline 中构建的**，而是有独立的工作流：

```
┌─────────────────────────────────────────────────────────────┐
│  触发条件满足                                                │
│  - 周日 18:00 或                                             │
│  - pyproject.toml/poetry.lock 变更                           │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Gitea Actions: Build Dependency Image                      │
│  (.gitea/workflows/build-dependency-image.yml)              │
│                                                             │
│  步骤:                                                      │
│  1. 检出代码                                                │
│  2. 检出 dockerfile.l2                              │
│  3. 拉取 Layer 1 (基础镜像)                             │
│  4. 基于 Layer 1 构建 Layer 2                               │
│     - 预装所有 Python 包                                    │
│     - 安装项目 Poetry 依赖                                      │
│  5. 推送到 Harbor                                           │
│     - 镜像名：harbor.sisys.local/sisys/dependency:l2-v1.0.0-{GIT_SHA} │
│  6. 清理旧版本 (保留最近 5 个)                               │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Harbor 仓库                                                │
│  /sisys/dependency:{GIT_SHA}                                │
│  (等待 CI Pipeline 使用)                                     │
└─────────────────────────────────────────────────────────────┘
```

**CI Pipeline 使用 Layer 2**:

```yaml
# .gitea/workflows/ci.yaml
jobs:
  code-quality:
    container:
      image: ${{ vars.HARBOR_REGISTRY }}/sisys/dependency:${{ github.sha }}
      # ↑ 使用 Layer 2 镜像，无需重新安装依赖！

  unit-tests:
    container:
      image: ${{ vars.HARBOR_REGISTRY }}/sisys/dependency:${{ github.sha }}
      # ↑ 直接使用预装好的依赖环境
```

### 执行时间线

```
时间轴:

第 1 周 周日 18:00
    │
    ▼
【Layer 2 构建】
harbor.sisys.local/sisys/dependency:abc123
    │
    └─── 保存到 Harbor ───┘

第 2 周 周一 10:00 (代码提交)
    │
    ▼
【CI Pipeline 触发】
    │
    ├── code-quality (使用 Layer 2)
    ├── unit-tests (使用 Layer 2)
    ├── integration (使用 Layer 2)
    │
    └── build-image (基于 Layer 2 构建 Layer 3)
            │
            ▼
        harbor.sisys.local/sisys/app:def456
            │
            ▼
        ArgoCD 部署

第 2 周 周日 18:00
    │
    ▼
【Layer 2 定期构建】(检查依赖是否变更)
```

### Pipeline 流程图

```
代码提交 → CI Pipeline → CD Pipeline → 部署完成
           ↓              ↓
    ┌──────┴──────┐   ┌───┴────┐
    │1. 代码质量   │   │1. 部署测试│
    │2. 单元测试   │   │2. 生产审批│
    │3. 集成测试   │   │3. 部署生产│
    │4. 安全扫描   │   │4. 健康检查│
    │5. 镜像构建   │   │5. 自动回滚│
    │6. 镜像推送   │   └────────┘
    │7. 自动部署   │
    └─────────────┘
```

---

## 快速开始

### 1. 前置条件

确保以下基础设施已就绪：

- ✅ Gitea (代码托管 + Actions)
- ✅ Harbor (镜像仓库)
- ✅ ArgoCD (持续部署)
- ✅ Gitea Runner (支持 Docker 和 K8s)
- ✅ K3S 集群 (支持 GPU 调度)

### 2. 应用 Pipeline 模板

在新项目中，复制以下文件到项目根目录：

```bash
# 复制 Pipeline 配置
cp .gitea/workflows/ci.yaml /path/to/your-project/.gitea/workflows/
cp .gitea/workflows/cd.yaml /path/to/your-project/.gitea/workflows/
cp .gitea/workflows/build-dependency-image.yml /path/to/your-project/.gitea/workflows/

# 复制 Docker 配置
cp deploy/docker/dockerfile.l2 /path/to/your-project/docker/
cp deploy/docker/dockerfile.app /path/to/your-project/docker/

# 复制 K8s 配置
cp deploy/kubernetes/k8s/deployment.yaml /path/to/your-project/deploy/kubernetes/k8s/
cp deploy/kubernetes/k8s/service.yaml /path/to/your-project/deploy/kubernetes/k8s/
```

### 3. 配置 Secrets

在 Gitea 仓库设置中配置以下 Secrets：

```yaml
# Harbor 配置
HARBOR_USERNAME: admin
HARBOR_PASSWORD: <your-password>

# Kubernetes 配置
KUBE_CONFIG_TEST: <base64-encoded-kubeconfig>
KUBE_CONFIG_PRODUCTION: <base64-encoded-kubeconfig>

# 通知配置 (可选)
NOTIFICATION_WEBHOOK: <your-webhook-url>
```

### 4. 配置 Variables

在 Gitea 仓库设置中配置以下 Variables：

```yaml
# Harbor 配置
HARBOR_REGISTRY: harbor.sisys.local

# GPU 配置
GPU_ENABLED: "true"           # 是否启用 GPU
GPU_RUNNER_LABEL: gpu-node    # GPU Runner 标签
```

### 5. 触发 Pipeline

```bash
# 提交代码触发 CI
git add .
git commit -m "feat: 新功能"
git push origin main

# 包含 GPU 任务
git commit -m "feat: GPU 加速功能 [gpu]"
git push origin main
```

---

## Pipeline 阶段详解

### CI Pipeline

#### 阶段 1: 代码质量门禁

- **工具**: Ruff + MyPy
- **检查项**:
  - 代码风格 (PEP 8)
  - 类型注解完整性
  - 代码格式化
- **失败条件**: 任何检查失败

```yaml
# 示例输出
✅ Ruff: 0 errors, 0 warnings
✅ MyPy: Success, no errors
```

#### 阶段 2: 单元测试

- **工具**: pytest + coverage
- **要求**: 覆盖率 ≥ 80%
- **GPU 支持**: 自动检测 GPU 并调度

```bash
# 运行命令
pytest tests/unit --cov=src --cov-report=xml --cov-fail-under=80
```

#### 阶段 3: 集成测试

- **工具**: pytest + Docker Compose
- **依赖服务**: PostgreSQL, Redis
- **GPU 支持**: 可选

```bash
# 运行命令
pytest tests/integration --tb=short
```

#### 阶段 4: 安全扫描

- **工具**: Trivy + Bandit
- **扫描范围**:
  - 代码安全 (Bandit)
  - 依赖漏洞 (Trivy)
  - 容器镜像 (Trivy)

```bash
# 扫描命令
bandit -r src/ -f json -o reports/security/bandit-report.json
trivy fs --format sarif --output reports/security/trivy-fs.sarif
```

#### 阶段 5: 镜像构建

- **策略**: 多阶段构建
- **基础**: 预构建依赖镜像
- **缓存**: Harbor  registry 缓存

```bash
# 构建命令
docker build -f deploy/docker/dockerfile.app \
  --build-arg DEPENDENCY_IMAGE=harbor.sisys.local/sisys/dependency:${GIT_SHA} \
  -t harbor.sisys.local/sisys/app:${GIT_SHA} .
```

#### 阶段 6: 镜像推送

- **目标**: Harbor
- **自动扫描**: Harbor 自动触发漏洞扫描
- **验证**: 推送后自动拉取验证

#### 阶段 7: 自动部署

- **环境**: 测试环境 (main 分支)
- **工具**: ArgoCD
- **健康检查**: 部署后自动执行

---

## 配置参数

### 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `HARBOR_REGISTRY` | Harbor 地址 | harbor.sisys.local | ✅ |
| `HARBOR_PROJECT` | Harbor 项目 | sisys | ✅ |
| `PYTHON_VERSION` | Python 版本 | 3.11 | ✅ |
| `POETRY_VERSION` | Poetry 版本 | 1.8.0 | ✅ |
| `GPU_ENABLED` | 是否启用 GPU | false | ❌ |
| `GPU_RUNNER_LABEL` | GPU Runner 标签 | gpu-node | ❌ |

### Pipeline 参数

```yaml
# CI Pipeline 参数
env:
  DEPENDENCY_IMAGE: harbor.sisys.local/sisys/dependency:${GIT_SHA}
  PYTORCH_IMAGE: harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

---

## Secrets 配置

### 必需 Secrets

| Secret 名称 | 说明 | 格式 |
|------------|------|------|
| `HARBOR_USERNAME` | Harbor 用户名 | 纯文本 |
| `HARBOR_PASSWORD` | Harbor 密码 | 纯文本 |
| `KUBE_CONFIG_TEST` | 测试环境 Kubeconfig | Base64 编码 |
| `KUBE_CONFIG_PRODUCTION` | 生产环境 Kubeconfig | Base64 编码 |

### 可选 Secrets

| Secret 名称 | 说明 |
|------------|------|
| `NOTIFICATION_WEBHOOK` | 部署通知 Webhook |
| `PRODUCTION_NOTIFICATION_WEBHOOK` | 生产部署通知 Webhook |

### Kubeconfig 编码

```bash
# 编码 Kubeconfig
cat ~/.kube/config | base64 -w 0

# 解码验证
echo "<base64-string>" | base64 -d
```

---

## GPU 任务调度

### GPU 检测

Pipeline 自动检测提交消息中的 `[gpu]` 标记：

```bash
# 触发 GPU 任务
git commit -m "feat: GPU 加速训练 [gpu]"
```

### GPU 资源配置

```yaml
# Kubernetes GPU 资源申请
resources:
  requests:
    nvidia.com/gpu: "1"
  limits:
    nvidia.com/gpu: "1"
```

### GPU 节点标签

```yaml
# 节点标签
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: node-type
              operator: In
              values:
                - gpu-node
```

---

## 预构建镜像系统

### 依赖镜像构建

**触发条件**:
- 每周日 18:00 (北京时间)
- `pyproject.toml` 或 `poetry.lock` 变更

**构建流程**:

```bash
# 1. 拉取基础镜像 (Layer 1)
docker pull harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel

# 2. 安装依赖 (Layer 2)
poetry install --only main

# 3. 推送到 Harbor
docker push harbor.sisys.local/sisys/dependency:${GIT_SHA}
```

### 镜像版本管理

- **标签格式**: `dependency:${GIT_SHA}`
- **保留策略**: 保留最近 5 个版本
- **清理脚本**: `scripts/image/cleanup-old-versions.sh`

### 本地 PyTorch 镜像导入

```bash
# 执行导入脚本
./scripts/image/import-pytorch.sh

# 或手动导入
docker load -i /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
docker tag pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
docker push harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

---

## 故障排除

### 常见问题

#### 1. Pipeline 无法触发

**症状**: 代码提交后 Pipeline 未执行

**解决方案**:
```bash
# 检查 Gitea Actions 是否启用
# 检查 .gitea/workflows/ 目录是否存在
# 检查 workflow 文件语法
yamllint .gitea/workflows/ci.yaml
```

#### 2. GPU 任务无法调度

**症状**: Pod 一直处于 Pending 状态

**解决方案**:
```bash
# 检查 GPU 节点
kubectl get nodes -l node-type=gpu-node

# 检查 GPU 资源
kubectl describe nodes | grep -A 5 "Allocated resources"

# 检查 NVIDIA Device Plugin
kubectl get pods -n kube-system | grep nvidia
```

#### 3. 镜像推送失败

**症状**: Harbor 认证失败

**解决方案**:
```bash
# 验证 Harbor 凭据
docker login harbor.sisys.local -u admin -p <password>

# 检查 Secrets 配置
kubectl get secret harbor-secret -n sisys-test -o yaml
```

#### 4. ArgoCD 同步失败

**症状**: 部署后 ArgoCD 显示 OutOfSync

**解决方案**:
```bash
# 手动触发同步
argocd app sync sisys-app

# 检查 ArgoCD 日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### 日志查看

```bash
# 查看 Pipeline 日志
# Gitea UI → Actions → 选择运行 → 查看日志

# 查看 Pod 日志
kubectl logs -n sisys-test -l app=sisys-app

# 查看 GPU 使用情况
nvidia-smi
```

---

## 最佳实践

### 1. 提交规范

```bash
# 功能开发
git commit -m "feat: 添加用户认证功能"

# GPU 任务
git commit -m "feat: GPU 加速模型训练 [gpu]"

# 修复 bug
git commit -m "fix: 修复登录失败问题"

# 依赖更新
git commit -m "chore: 更新依赖版本"
```

### 2. 测试覆盖率

```bash
# 确保覆盖率达标
pytest --cov=src --cov-fail-under=80

# 生成详细报告
pytest --cov=src --cov-report=html --cov-report=term-missing
```

### 3. 镜像优化

```dockerfile
# 使用多阶段构建
FROM dependency-image AS builder
# ... 构建步骤

FROM dependency-image AS final
COPY --from=builder /app/dist ./dist
```

### 4. 安全实践

- 不在代码中硬编码密码
- 使用 Secrets 管理敏感信息
- 定期更新依赖镜像
- 启用 Harbor 漏洞扫描

### 5. 监控告警

```yaml
# Prometheus 监控配置
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"
```

---

## 相关文档

- [Secrets 配置指南](./CI_CD_SECRETS_GUIDE.md)
- [故障排除指南](./CI_CD_TROUBLESHOOTING.md)
- [预构建镜像维护指南](./PREBUILT_IMAGE_MAINTENANCE.md)
- [本地 PyTorch 镜像导入指南](./LOCAL_PYTORCH_IMPORT.md)

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-23 | 初始版本 |
