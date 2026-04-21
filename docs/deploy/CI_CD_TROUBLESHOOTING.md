# CI/CD Pipeline 故障排除指南

## 目录

1. [Pipeline 执行问题](#pipeline-执行问题)
2. [Docker 镜像问题](#docker-镜像问题)
3. [Kubernetes 部署问题](#kubernetes-部署问题)
4. [GPU 调度问题](#gpu-调度问题)
5. [Harbor 问题](#harbor-问题)
6. [ArgoCD 问题](#argocd-问题)
7. [性能优化](#性能优化)

---

## Pipeline 执行问题

### 1. Pipeline 无法触发

**症状**: 代码提交后 Pipeline 未执行

**可能原因**:
- Gitea Actions 未启用
- Workflow 文件语法错误
- 分支不匹配

**解决方案**:

```bash
# 1. 检查 Gitea Actions 是否启用
# Gitea UI → 仓库设置 → Actions → 启用

# 2. 验证 Workflow 语法
yamllint .gitea/workflows/ci.yaml
yamllint .gitea/workflows/cd.yaml

# 3. 检查分支配置
# 确保推送到配置的分支 (main/develop)
git branch  # 查看当前分支
git push origin main  # 推送到正确分支
```

### 2. Pipeline 执行失败 - 代码质量检查

**症状**: Ruff 或 MyPy 检查失败

**解决方案**:

```bash
# 本地运行检查
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src/ tests/

# 修复代码风格问题
poetry run ruff check . --fix
poetry run ruff format .

# 忽略特定规则 (谨慎使用)
# 在 pyproject.toml 中添加
[tool.ruff]
ignore = ["E501"]  # 忽略行过长
```

### 3. Pipeline 执行失败 - 测试覆盖率不足

**症状**: `Coverage failure: total of 75 is less than fail-under=80`

**解决方案**:

```bash
# 查看覆盖率报告
poetry run coverage report --show-missing

# 生成 HTML 报告查看详细缺失
poetry run coverage html
open htmlcov/index.html

# 添加缺失的测试
# 优先测试核心业务逻辑
```

### 4. Pipeline 执行超时

**症状**: `Error: The operation was canceled.`

**可能原因**:
- 测试执行时间过长
- 依赖下载慢
- 资源不足

**解决方案**:

```yaml
# 1. 增加超时时间 (在 workflow 中)
timeout-minutes: 60

# 2. 使用预构建镜像加速
# 确保使用 dependency image

# 3. 优化测试并行度
pytest -n auto  # 使用 pytest-xdist 并行执行
```

### 5. 并发冲突

**症状**: `concurrency group already running`

**解决方案**:

```yaml
# 在 workflow 中配置并发控制
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true  # 取消进行中的任务
```

---

## Docker 镜像问题

### 1. 镜像构建失败

**症状**: `error building image: failed to solve base image`

**解决方案**:

```bash
# 1. 验证基础镜像存在
docker pull harbor.sisys.local/sisys/dependency:latest

# 2. 检查 Dockerfile 语法
docker build -f deploy/docker/dockerfile.app --no-cache .

# 3. 查看构建日志
docker build -f deploy/docker/dockerfile.app . 2>&1 | tee build.log
```

### 2. 镜像推送失败

**症状**: `denied: requested access to the resource is denied`

**解决方案**:

```bash
# 1. 验证 Harbor 登录
docker login harbor.sisys.local

# 2. 检查 Harbor 权限
# Harbor UI → 项目 → 成员 → 检查用户权限

# 3. 使用机器人账户
docker login harbor.sisys.local -u robot$ci-pipeline -p <token>
```

### 3. 镜像大小过大

**症状**: 镜像超过 5GB

**解决方案**:

```dockerfile
# 1. 使用多阶段构建
FROM dependency-image AS builder
# ... 构建
FROM dependency-image AS final
COPY --from=builder /app/dist ./dist

# 2. 清理缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
RUN rm -rf /root/.cache/pip

# 3. 使用 .dockerignore
# 在 .dockerignore 中排除不必要的文件
.git
tests/
docs/
*.md
```

### 4. 镜像拉取慢

**症状**: `Pulling image...` 超过 10 分钟

**解决方案**:

```bash
# 1. 使用本地镜像缓存
docker pull harbor.sisys.local/sisys/dependency:latest

# 2. 配置镜像加速器
# /etc/docker/daemon.json
{
  "registry-mirrors": ["https://harbor.sisys.local"]
}

# 3. 预拉取镜像
# 在 Pipeline 开始前预拉取
```

---

## Kubernetes 部署问题

### 1. Pod 无法启动

**症状**: `CrashLoopBackOff` 或 `Error`

**解决方案**:

```bash
# 1. 查看 Pod 日志
kubectl logs -n sisys-test -l app=sisys-app

# 2. 查看 Pod 详情
kubectl describe pod -n sisys-test -l app=sisys-app

# 3. 检查环境变量
kubectl exec -n sisys-test <pod-name> -- env

# 4. 检查 Secret 是否存在
kubectl get secret -n sisys-test
```

### 2. 服务无法访问

**症状**: `Connection refused` 或 `503 Service Unavailable`

**解决方案**:

```bash
# 1. 检查 Service
kubectl get svc -n sisys-test

# 2. 检查 Endpoints
kubectl get endpoints -n sisys-test

# 3. 测试服务连通性
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://sisys-app.sisys-test.svc.cluster.local/health

# 4. 检查 Ingress
kubectl get ingress -n sisys-test
```

### 3. 资源不足

**症状**: `Insufficient cpu` 或 `Insufficient memory`

**解决方案**:

```bash
# 1. 查看节点资源
kubectl top nodes

# 2. 调整资源请求
# deploy/kubernetes/k8s/deployment.yaml
resources:
  requests:
    memory: "1Gi"  # 降低请求
    cpu: "500m"

# 3. 扩展集群
# 添加更多节点
```

### 4. 健康检查失败

**症状**: `Readiness probe failed`

**解决方案**:

```bash
# 1. 检查健康检查端点
kubectl exec -n sisys-test <pod-name> -- curl -f http://localhost:8000/health/ready

# 2. 调整探针配置
# 增加初始延迟和超时
livenessProbe:
  initialDelaySeconds: 60  # 增加启动时间
  timeoutSeconds: 10
  failureThreshold: 5
```

---

## GPU 调度问题

### 1. Pod 一直处于 Pending

**症状**: `0/3 nodes are available: 3 Insufficient nvidia.com/gpu`

**解决方案**:

```bash
# 1. 检查 GPU 节点
kubectl get nodes -l nvidia.com/gpu.present=true

# 2. 检查 GPU 资源
kubectl describe nodes | grep -A 10 "Allocated resources"

# 3. 检查 NVIDIA Device Plugin
kubectl get pods -n kube-system | grep nvidia

# 4. 重新安装 Device Plugin
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/deploy/kubernetes/static/nvidia-device-plugin.yml
```

### 2. GPU 无法识别

**症状**: `CUDA error: no CUDA-capable device is detected`

**解决方案**:

```bash
# 1. 验证容器内 GPU 可见性
kubectl exec -n sisys-test <pod-name> -- nvidia-smi

# 2. 检查容器运行时
# 确保使用支持 GPU 的运行时
# /etc/docker/daemon.json
{
  "default-runtime": "nvidia"
}

# 3. 验证 PyTorch CUDA
kubectl exec -n sisys-test <pod-name> -- \
  python3 -c "import torch; print(torch.cuda.is_available())"
```

### 3. GPU 性能低下

**症状**: GPU 利用率低于 50%

**解决方案**:

```yaml
# 1. 确保 GPU 直通
# 避免 CPU 瓶颈
resources:
  requests:
    cpu: "2000m"  # 增加 CPU
    memory: "4Gi"

# 2. 使用 GPU 亲和性
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: nvidia.com/gpu.product
              operator: In
              values:
                - "NVIDIA-A100"
```

---

## Harbor 问题

### 1. 漏洞扫描失败

**症状**: `Scan failed: no scanner found`

**解决方案**:

```bash
# 1. 检查 Trivy 状态
# Harbor UI → 管理 → 漏洞扫描 → 查看状态

# 2. 重启 Trivy
kubectl restart deployment -n harbor harbor-trivy

# 3. 手动触发扫描
# Harbor UI → 项目 → 仓库 → 镜像 → 扫描
```

### 2. 存储空间不足

**症状**: `no space left on device`

**解决方案**:

```bash
# 1. 查看存储使用
# Harbor UI → 管理 → 存储

# 2. 清理旧镜像
./scripts/image/cleanup-old-versions.sh

# 3. 扩展存储
# 根据 Harbor 部署方式扩展 PVC
kubectl get pvc -n harbor
kubectl edit pvc -n harbor harbor-data
```

---

## ArgoCD 问题

### 1. 应用不同步

**症状**: `OutOfSync`

**解决方案**:

```bash
# 1. 查看差异
argocd app diff sisys-app

# 2. 手动同步
argocd app sync sisys-app

# 3. 启用自动同步
argocd app set sisys-app --sync-policy automated

# 4. 查看同步历史
argocd app history sisys-app
```

### 2. 部署卡住

**症状**: `Progressing` 状态超过 10 分钟

**解决方案**:

```bash
# 1. 查看 ArgoCD 日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller

# 2. 强制刷新
argocd app get sisys-app --refresh hard

# 3. 回滚到上一版本
argocd app rollback sisys-app
```

### 3. 健康检查失败

**症状**: `Health: Degraded`

**解决方案**:

```bash
# 1. 查看健康状态
argocd app get sisys-app

# 2. 自定义健康检查
# 在 Application YAML 中配置
health:
  custom:
    lua: |
      hs = {}
      hs.status = "Healthy"
      return hs
```

---

## 性能优化

### 1. 加速依赖安装

```yaml
# 使用预构建镜像
FROM harbor.sisys.local/sisys/dependency:${GIT_SHA}

# 而不是
RUN poetry install  # 每次重新安装
```

### 2. 优化镜像构建

```dockerfile
# 使用构建缓存
docker build --cache-from harbor.sisys.local/sisys/app:buildcache \
  --cache-to harbor.sisys.local/sisys/app:buildcache .

# 多阶段构建减少最终镜像大小
```

### 3. 并行执行

```yaml
# CI Pipeline 并行执行独立任务
jobs:
  code-quality:
    # ...
  unit-tests:
    needs: []  # 不依赖其他任务
  security-scan:
    needs: []  # 不依赖其他任务
```

### 4. 减少测试时间

```bash
# 使用 pytest-xdist 并行测试
pytest -n auto

# 只运行变更相关的测试
pytest --last-failed

# 跳过慢速测试 (开发环境)
pytest -m "not slow"
```

---

## 日志收集

### Pipeline 日志

```bash
# Gitea UI → Actions → 选择运行 → 下载日志
# 或查看实时日志
```

### Kubernetes 日志

```bash
# 查看 Pod 日志
kubectl logs -n sisys-test -l app=sisys-app

# 查看历史日志
kubectl logs -n sisys-test -l app=sisys-app --previous

# 跟踪日志
kubectl logs -f -n sisys-test -l app=sisys-app
```

### ArgoCD 日志

```bash
# 查看 ArgoCD 应用日志
argocd app logs sisys-app

# 查看 ArgoCD 控制器日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

---

## 联系支持

如果以上方案无法解决问题，请收集以下信息并联系支持团队：

1. Pipeline 执行日志
2. Kubernetes Pod 日志和描述
3. 错误截图
4. 复现步骤

---

## 相关文档

- [CI/CD Pipeline 模板使用指南](./CI_CD_PIPELINE_TEMPLATE.md)
- [Secrets 配置指南](./CI_CD_SECRETS_GUIDE.md)
