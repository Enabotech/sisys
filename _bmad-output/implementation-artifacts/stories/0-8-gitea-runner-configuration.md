# Story 0.8: Gitea Runner 配置

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

<!--
故事创建日期：2026-03-19
创建者：Qwen Code (AI 高级开发者 - BMad Method Story Context Engine)
故事来源：sprint-status.yaml (第一个 backlog 故事)
前置依赖：Story 0.4 (K3S 集群 ✅), Story 0.5 (Gitea ✅), Story 0.6 (Harbor ✅), Story 0.7 (ArgoCD ✅)
-->

## Story

As a **DevOps 工程师**,
I want **配置 Gitea Runner v1.25.4 支持 Docker 和 K8s 执行器**,
so that **实现 CI/CD Pipeline 自动化执行，代码推送后自动触发构建、测试和部署**。

## Acceptance Criteria

1. **Given** K3S 集群已部署 (Story 0.4 ✅ 已完成)
   **When** 运行 Gitea Runner Helm Chart 或 kubectl apply
   **Then** Gitea Runner v1.25.4 部署成功
   - 所有 Pod 状态为 Running (`kubectl get pods -n gitea-actions`，无 CrashLoopBackOff 或 Error 状态)
   - Runner 在 Gitea 管理页面显示为"空闲"状态
   - Pod 启动时间 < 60 秒
   - 无重启次数异常（restart count < 3）

2. **Given** Gitea Runner 已注册
   **When** 配置 Docker Executor
   **Then** Docker 执行器可正常工作
   - Runner 可拉取 `docker.gitea.com/runner-images:ubuntu-latest` 镜像
   - Docker in Docker (dind) 模式配置正确
   - 构建任务可执行 `docker build` 和 `docker push` 命令
   - 镜像构建速度 ≥ 10MB/s（本地网络）

3. **Given** Gitea Runner 已注册
   **When** 配置 K8s Executor
   **Then** K8s 执行器可正常工作
   - Runner 可调用 K8s API 创建临时 Pod 执行任务
   - 每个 Job 在独立 Pod 中执行（资源隔离）
   - 任务完成后 Pod 自动清理
   - 支持并发执行多个 Job

4. **Given** Gitea Runner 配置完成
   **When** 推送代码到 Gitea 仓库
   **Then** CI/CD Pipeline 自动触发
   - Webhook 触发延迟 < 5 秒
   - Pipeline 状态在 Gitea Actions 页面可见
   - 构建日志实时可查
   - 构建结果通知（成功/失败）

5. **Given** Gitea Runner 与 Harbor 集成
   **When** Pipeline 推送镜像到 Harbor
   **Then** 镜像推送成功
   - 使用 Story 0.6 创建的 Robot Account 认证
   - `docker push harbor.sisys.local/sisys/{app}:{tag}` 成功
   - 推送后自动触发 Trivy 漏洞扫描
   - 镜像在 Harbor 界面可见

6. **Given** Gitea Runner 多执行器配置
   **When** 并发提交多个 PR
   **Then** 多个 Pipeline 并行执行
   - 支持至少 3 个并发 Job
   - Job 之间资源隔离（CPU/内存限制）
   - 无资源竞争导致的失败
   - 平均等待时间 < 30 秒

7. **Given** Gitea Runner 配置完成
   **When** 创建 `.gitea/workflows/ci.yaml`
   **Then** Pipeline 语法验证通过
   - YAML 语法正确
   - Actions 语法符合 Gitea 规范
   - 所有引用的 Actions 版本可用
   - Dry-run 测试通过

## Tasks / Subtasks

- [ ] Task 1: Gitea Runner Token 配置 (AC: 1)
  - [ ] 在 Gitea 管理页面创建 Runner Token（设置→Actions）
  - [ ] 存储 Token 到 Kubernetes Secret（`gitea-runner-token`）
  - [ ] 配置 Token 过期策略（建议 90 天轮换）
  - [ ] 验证 Token 权限（至少包含 repo、actions 权限）

- [ ] Task 2: Gitea Runner 部署 (AC: 1, 4)
  - [ ] 方案 A：Helm Chart 部署（推荐）
    - [ ] 添加 Gitea Helm 仓库
    - [ ] 配置 values.yaml（副本数、资源限制、Runner 标签）
    - [ ] 执行 `helm install gitea-runner`
  - [ ] 方案 B：kubectl 部署
    - [ ] 创建 Deployment YAML
    - [ ] 配置环境变量（GITEA_INSTANCE_URL, GITEA_RUNNER_TOKEN）
    - [ ] 执行 `kubectl apply -f gitea-runner.yaml`
  - [ ] 验证 Runner 状态（Gitea 页面显示"空闲"）

- [ ] Task 3: Docker Executor 配置 (AC: 2, 5)
  - [ ] 配置 Docker in Docker (dind) 模式
  - [ ] 预拉取常用镜像（`ubuntu-latest`, `node-latest`, `python-latest`）
  - [ ] 配置 Docker 镜像缓存（加速构建）
  - [ ] 配置 Harbor 免密登录（复用 Story 0.6 Robot Account）
  - [ ] 测试 Docker 构建流程

- [ ] Task 4: K8s Executor 配置 (AC: 3, 6)
  - [ ] 配置 K8s API 访问权限（ServiceAccount + RBAC）
  - [ ] 创建 K8s Executor 配置（`config.yaml`）
  - [ ] 配置 Pod 模板（CPU/内存限制、镜像拉取策略）
  - [ ] 配置 Job 并发限制（默认 3 个并发）
  - [ ] 测试 K8s Job 执行流程

- [ ] Task 5: Pipeline 模板配置 (AC: 4, 7)
  - [ ] 创建标准 CI Pipeline 模板（`.gitea/workflows/ci.yaml`）
  - [ ] 创建标准 CD Pipeline 模板（`.gitea/workflows/cd.yaml`）
  - [ ] 配置 7 阶段 Pipeline（参考 sprint-status.yaml 0-9-ci-cd-pipeline-template）
    - [ ] 阶段 1：代码质量（Ruff + MyPy）
    - [ ] 阶段 2：单元测试（pytest + cov）
    - [ ] 阶段 3：集成测试（Docker Compose）
    - [ ] 阶段 4：安全扫描（Trivy + Bandit）
    - [ ] 阶段 5：镜像构建（Docker Build）
    - [ ] 阶段 6：镜像推送（Harbor）
    - [ ] 阶段 7：自动部署（ArgoCD）
  - [ ] 测试 Pipeline 触发流程

- [ ] Task 6: Harbor 集成配置 (AC: 5)
  - [ ] 复用 Story 0.6 Harbor Robot Account
  - [ ] 配置 Docker Registry 凭据（Kubernetes Secret）
  - [ ] 测试 `docker login` 到 Harbor
  - [ ] 测试 `docker push` 到 Harbor
  - [ ] 验证 Trivy 自动扫描触发

- [ ] Task 7: 多 Runner 配置 (AC: 6)
  - [ ] 配置 Runner 标签（`docker`, `k8s`, `gpu` 等）
  - [ ] 部署多个 Runner 实例（建议 3 个副本）
  - [ ] 配置 Runner 分组（按项目/环境隔离）
  - [ ] 测试并发 Job 执行

- [ ] Task 8: 监控与日志配置
  - [ ] 配置 Runner 日志收集（集成到统一日志系统）
  - [ ] 配置 Pipeline 执行指标（Prometheus metrics）
  - [ ] 配置失败告警（邮件/钉钉/企业微信）
  - [ ] 配置构建时长统计与分析

- [ ] Task 9: 架构合规验证
  - [ ] 验证 TLS 1.3 强制启用（Gitea/Harbor 通信）
  - [ ] 验证 Secret 存储于 Kubernetes Secret（无明文配置）
  - [ ] 验证网络策略（NetworkPolicy 隔离）
  - [ ] 验证资源限制（ResourceQuota + LimitRange）
  - [ ] 运行所有 TDD 测试

- [ ] Task 10: 代码审查修复
  - [ ] 修复 HIGH 优先级问题
  - [ ] 修复 MEDIUM 优先级问题
  - [ ] 修复 LOW 优先级问题
  - [ ] 代码审查记录（审查者、问题数、修复状态）

- [ ] Task 11: 功能验证
  - [ ] AC-1: Runner 部署验证
  - [ ] AC-2: Docker Executor 验证
  - [ ] AC-3: K8s Executor 验证
  - [ ] AC-4: Pipeline 触发验证
  - [ ] AC-5: Harbor 集成验证
  - [ ] AC-6: 并发执行验证
  - [ ] AC-7: Pipeline 语法验证
  - [ ] 架构合规验证

## Dev Notes

### 前置依赖关系

**必须完成的前置 Story：**
- Story 0.4: K3S 集群部署 ✅ (提供 K8s 运行环境)
- Story 0.5: Gitea 代码托管 ✅ (提供 Git 仓库和 Actions 功能)
- Story 0.6: Harbor 镜像仓库 ✅ (提供镜像存储和漏洞扫描)
- Story 0.7: ArgoCD 持续部署 ✅ (提供 GitOps 自动部署)

**后续依赖 Story：**
- Story 0.9: CI/CD Pipeline 模板（标准化 7 阶段 Pipeline）
- Epic 1-16: 集成测试框架（为 Pipeline 提供测试能力）

### 技术选型说明

**Gitea Runner 版本：** v1.25.4（与 Gitea 服务端版本一致）
- 来源：https://blog.gitea.com/release-of-1.25.4
- 发布日期：2026-01-22
- 安全修复：9 个 CVE 漏洞修复
- Go 版本：1.25.6

**执行器选择：**
- **Docker Executor**：适合简单构建任务，资源开销小
- **K8s Executor**：适合复杂任务，资源隔离好，支持并发

**部署方式：**
- **Helm Chart**：推荐，配置管理方便，支持多环境
- **kubectl**：灵活，适合自定义场景

### 关键配置参数

```yaml
# Runner 配置示例
GITEA_INSTANCE_URL: https://gitea.sisys.local
GITEA_RUNNER_TOKEN: <从 Gitea 管理页面获取>
GITEA_RUNNER_NAME: k8s-runner-01
GITEA_RUNNER_LABELS: docker,k8s,standard
GITEA_RUNNER_CAPACITY: 3  # 最大并发 Job 数
```

### Project Structure Notes

**统一项目结构对齐：**
```
_bmad-output/implementation-artifacts/
├── stories/
│   └── 0-8-gitea-runner-configuration.md  # 本故事文件
├── deployments/
│   └── gitea-runner/
│       ├── values.yaml                    # Helm Chart 配置
│       ├── runner-docker-executor.yaml    # Docker 执行器配置
│       ├── runner-k8s-executor.yaml       # K8s 执行器配置
│       └── rbac.yaml                      # RBAC 权限配置
├── scripts/
│   └── gitea-runner/
│       ├── deploy-runner.sh               # 部署脚本
│       ├── register-runner.sh             # 注册 Runner 脚本
│       └── test-pipeline.sh               # Pipeline 测试脚本
├── .gitea/
│   └── workflows/
│       ├── ci.yaml                        # CI Pipeline 模板
│       └── cd.yaml                        # CD Pipeline 模板
└── tests/
    └── gitea-runner/
        ├── test_runner_deployment.py      # Runner 部署测试
        ├── test_docker_executor.py        # Docker 执行器测试
        ├── test_k8s_executor.py           # K8s 执行器测试
        └── test_pipeline_trigger.py       # Pipeline 触发测试
```

### 与 Story 0.7 ArgoCD 的协同

**GitOps 流程：**
```
开发者 push 代码
    ↓
Gitea Webhook 触发
    ↓
Gitea Runner 执行 CI Pipeline
    ↓
构建镜像并推送到 Harbor
    ↓
ArgoCD Image Updater 检测到新镜像
    ↓
ArgoCD 自动同步部署到 K8s
```

### 安全考虑

**凭据管理：**
- 所有 Token 存储于 Kubernetes Secret
- 禁止在 Git 仓库中明文存储密码/Token
- 使用环境变量或 Secret 注入方式

**网络隔离：**
- Runner Pod 使用独立命名空间（`gitea-actions`）
- 配置 NetworkPolicy 限制访问范围
- 仅允许访问 Gitea、Harbor、K8s API

**镜像安全：**
- 使用可信镜像源（`docker.gitea.com`）
- 推送前自动触发 Trivy 扫描
- 配置镜像签名验证（复用 Story 0.6 Cosign）

### References

- [Source: _bmad-output/planning-artifacts/sprint-status.yaml#development_status] - 故事来源和状态追踪
- [Source: _bmad-output/planning-artifacts/architecture-epic0.md] - Epic 0 架构设计（开发 CI/CD 系统）
- [Source: _bmad-output/implementation-artifacts/stories/0-5-gitea-code-hosting.md] - Gitea 部署详情
- [Source: _bmad-output/implementation-artifacts/stories/0-6-harbor-image-registry.md] - Harbor 部署详情
- [Source: _bmad-output/implementation-artifacts/stories/0-7-argocd-continuous-deployment.md] - ArgoCD 部署详情
- [Source: https://blog.gitea.com/release-of-1.25.4] - Gitea 1.25.4 发布说明
- [Source: https://blog.lusyoe.com/article/gitea-runner-on-kubernetes] - Gitea Runner K8s 部署指南
- [Source: https://docs.gitea.com/usage/actions/runner] - Gitea Runner 官方文档

## Dev Agent Record

### Agent Model Used

- **Model**: Qwen Code (AI 高级开发者)
- **Version**: 2026-03-19
- **Mode**: BMad Method Story Context Engine
- **Language**: 中文（文档输出语言）

### Debug Log References

- Story 创建日志：`_bmad-output/logs/create-story-0-8-2026-03-19.log`
- Workflow 执行记录：`_bmad-output/logs/workflow-create-story-execution.log`

### Completion Notes List

- ✅ 故事文件创建完成
- ✅ 所有 Acceptance Criteria 已定义
- ✅ 所有 Tasks 已分解
- ✅ 前置依赖关系已分析
- ✅ 架构合规要求已明确
- ✅ 安全要求已明确
- ✅ 测试要求已明确
- ⏳ 等待 dev-story 执行实施

### File List

**创建的文件：**
- `_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md`

**预期创建的文件（dev-story 执行后）：**
- `deployments/gitea-runner/values.yaml`
- `deployments/gitea-runner/runner-docker-executor.yaml`
- `deployments/gitea-runner/runner-k8s-executor.yaml`
- `deployments/gitea-runner/rbac.yaml`
- `scripts/gitea-runner/deploy-runner.sh`
- `scripts/gitea-runner/register-runner.sh`
- `scripts/gitea-runner/test-pipeline.sh`
- `.gitea/workflows/ci.yaml`
- `.gitea/workflows/cd.yaml`
- `tests/gitea-runner/test_runner_deployment.py`
- `tests/gitea-runner/test_docker_executor.py`
- `tests/gitea-runner/test_k8s_executor.py`
- `tests/gitea-runner/test_pipeline_trigger.py`

---

## 附录：Gitea Runner 配置示例

### Helm Chart 配置示例

```yaml
# deployments/gitea-runner/values.yaml
replicaCount: 3

image:
  repository: gitea/act_runner
  tag: "1.25.4"
  pullPolicy: IfNotPresent

env:
  GITEA_INSTANCE_URL: "https://gitea.sisys.local"
  GITEA_RUNNER_TOKEN: ""  # 从 Secret 注入
  GITEA_RUNNER_NAME: "k8s-runner"
  GITEA_RUNNER_LABELS: "docker,k8s"
  GITEA_RUNNER_CAPACITY: "3"

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 500m
    memory: 1Gi

persistence:
  enabled: true
  size: 10Gi
  storageClass: "local-path"
```

### Docker Executor 配置示例

```yaml
# deployments/gitea-runner/runner-docker-executor.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitea-runner-docker-config
  namespace: gitea-actions
data:
  config.yaml: |
    log:
      level: info
    runner:
      timeout: 10m
    container:
      network: host
      options: --privileged
      workdir: /workspace
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock
```

### K8s Executor 配置示例

```yaml
# deployments/gitea-runner/runner-k8s-executor.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitea-runner-k8s-config
  namespace: gitea-actions
data:
  config.yaml: |
    log:
      level: info
    runner:
      timeout: 10m
    container:
      kubernetes:
        namespace: gitea-actions
        service_account: gitea-runner
        image_pull_secrets:
          - harbor-robot-account
        pod_template: |
          spec:
            containers:
              - name: runner
                resources:
                  limits:
                    cpu: 2000m
                    memory: 4Gi
                  requests:
                    cpu: 500m
                    memory: 1Gi
```

### RBAC 配置示例

```yaml
# deployments/gitea-runner/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: gitea-runner
  namespace: gitea-actions
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: gitea-runner
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "pods/exec"]
    verbs: ["get", "list", "create", "delete"]
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: gitea-runner
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: gitea-runner
subjects:
  - kind: ServiceAccount
    name: gitea-runner
    namespace: gitea-actions
```

### CI Pipeline 模板示例

```yaml
# .gitea/workflows/ci.yaml
name: CI Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # 阶段 1：代码质量
  code-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Ruff linting
        run: ruff check .
      - name: MyPy type checking
        run: mypy src/

  # 阶段 2：单元测试
  unit-test:
    runs-on: ubuntu-latest
    needs: code-quality
    steps:
      - uses: actions/checkout@v3
      - name: Run pytest
        run: pytest tests/unit --cov=src --cov-report=xml

  # 阶段 3：集成测试
  integration-test:
    runs-on: ubuntu-latest
    needs: unit-test
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: pytest tests/integration

  # 阶段 4：安全扫描
  security-scan:
    runs-on: ubuntu-latest
    needs: unit-test
    steps:
      - uses: actions/checkout@v3
      - name: Trivy filesystem scan
        run: trivy fs .
      - name: Bandit security scan
        run: bandit -r src/

  # 阶段 5：镜像构建
  build-image:
    runs-on: ubuntu-latest
    needs: [integration-test, security-scan]
    steps:
      - uses: actions/checkout@v3
      - name: Docker build
        run: docker build -t harbor.sisys.local/sisys/app:${{ github.sha }} .

  # 阶段 6：镜像推送
  push-image:
    runs-on: ubuntu-latest
    needs: build-image
    steps:
      - name: Login to Harbor
        run: docker login harbor.sisys.local -u ${{ secrets.HARBOR_USERNAME }} -p ${{ secrets.HARBOR_PASSWORD }}
      - name: Docker push
        run: docker push harbor.sisys.local/sisys/app:${{ github.sha }}

  # 阶段 7：自动部署（仅 main 分支）
  deploy:
    runs-on: ubuntu-latest
    needs: push-image
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Trigger ArgoCD sync
        run: |
          curl -X POST https://argocd.sisys.local/api/v1/applications/sisys-app/sync \
            -H "Authorization: Bearer ${{ secrets.ARGOCD_TOKEN }}"
```
