# 混合 CI/CD 方案 - GitHub-hosted + Self-hosted Runner

**目标：** 最大化利用本地强大硬件，同时保持 GitHub-hosted 的便利性
**日期：** 2026-03-05

---

## 🎯 方案概述

### 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    GitHub Repository                     │
└─────────────────────────────────────────────────────────┘
                          │
                          ├──────────────────┐
                          │                  │
              ┌───────────▼──────┐  ┌────────▼────────┐
              │  GitHub-hosted   │  │  Self-hosted    │
              │  Runner          │  │  Runner (本地)  │
              │  (轻量 Job)      │  │  (重量 Job)     │
              └──────────────────┘  └─────────────────┘
                       │                     │
                       │                     ├─ Docker Build
                       │                     ├─ AI Model Tests
                       │                     ├─ Large Data Tests
                       │                     └─ Performance Tests
```

---

## 📋 工作流设计

### 方案 A: 按 Job 类型路由

**轻量 Job → GitHub-hosted**
- Code Quality (linting, type checking)
- Unit Tests (快速，无外部依赖)
- Security Scans (bandit, safety)

**重量 Job → Self-hosted**
- Integration Tests (需要数据库/外部服务)
- Docker Build (磁盘密集)
- AI Model Tests (需要 GPU)
- Performance Tests (需要大内存)
- Large Data Tests (需要 10T 存储)

**实现：**

```yaml
# .github/workflows/ci.yml

name: Hybrid CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # ========== 轻量 Job: GitHub-hosted ==========
  code-quality:
    name: Code Quality Checks
    runs-on: ubuntu-latest  # GitHub-hosted
    timeout-minutes: 10
    steps:
      # ... 代码质量检查步骤

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest  # GitHub-hosted
    timeout-minutes: 15
    steps:
      # ... 单元测试步骤

  # ========== 重量 Job: Self-hosted ==========
  integration-tests:
    name: Integration Tests
    runs-on: [self-hosted, windows, x64]  # 本地 Runner
    timeout-minutes: 30
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      # ... 集成测试步骤

  build-docker:
    name: Build Docker Image
    runs-on: [self-hosted, windows, high-memory]  # 本地 Runner (大内存)
    timeout-minutes: 20
    needs: [unit-tests, integration-tests]
    steps:
      # ... Docker 构建步骤

  ai-model-tests:
    name: AI Model Tests (GPU)
    runs-on: [self-hosted, windows, gpu]  # 本地 Runner (GPU)
    needs: [integration-tests]
    steps:
      - name: Setup GPU
        run: |
          nvidia-smi

      - name: Run AI model tests
        run: |
          poetry run pytest tests/ai/ -v --gpu

  performance-tests:
    name: Performance Tests
    runs-on: [self-hosted, windows, high-memory]  # 本地 Runner (32G RAM)
    needs: [build-docker]
    steps:
      # ... 性能测试步骤

  # ========== 汇总 Job: GitHub-hosted ==========
  upload-coverage:
    name: Upload Coverage to Codecov
    runs-on: ubuntu-latest  # GitHub-hosted
    needs: [unit-tests, integration-tests, ai-model-tests]
    steps:
      # ... 覆盖率上传步骤
```

---

### 方案 B: 按分支路由

**Main/Master 分支 → GitHub-hosted**
- 生产环境构建
- 正式部署
- 对外发布

**Develop/Feature 分支 → Self-hosted**
- 开发环境构建
- 快速迭代测试
- AI 模型实验

**实现：**

```yaml
# .github/workflows/smart-routing.yml

name: Smart CI/CD Routing

on:
  push:
    branches: [main, develop, feature/**]
  pull_request:
    branches: [main, develop]

jobs:
  detect-runner:
    name: Detect Runner Type
    runs-on: ubuntu-latest
    outputs:
      runner-type: ${{ steps.detect.outputs.runner }}
    steps:
      - name: Detect branch and set runner
        id: detect
        run: |
          if [[ "$GITHUB_REF" == "refs/heads/main" ]]; then
            echo "runner=github-hosted" >> $GITHUB_OUTPUT
          else
            echo "runner=self-hosted" >> $GITHUB_OUTPUT

  build:
    name: Build and Test
    runs-on: ${{ needs.detect-runner.outputs.runner-type == 'github-hosted' && 'ubuntu-latest' || 'self-hosted' }}
    needs: [detect-runner]
    steps:
      # ... 构建步骤
```

---

### 方案 C: 按时间路由（成本优化）

**工作时间 (9:00-18:00) → Self-hosted**
- 快速反馈
- 无 GitHub Actions 费用
- 充分利用本地硬件

**非工作时间 → GitHub-hosted**
- 不占用本地资源
- 自动扩展
- 按需付费

**实现：**

```yaml
# .github/workflows/time-based-routing.yml

name: Time-based CI/CD

on:
  push:
    branches: [main, develop]

jobs:
  time-check:
    name: Check Time and Select Runner
    runs-on: ubuntu-latest
    outputs:
      runner-type: ${{ steps.check.outputs.runner }}
    steps:
      - name: Get current hour (UTC+8)
        id: check
        run: |
          HOUR=$(date -d "Asia/Shanghai" +%H)
          if [ $HOUR -ge 9 ] && [ $HOUR -lt 18 ]; then
            echo "runner=self-hosted" >> $GITHUB_OUTPUT
          else
            echo "runner=github-hosted" >> $GITHUB_OUTPUT

  build:
    runs-on: ${{ needs.time-check.outputs.runner-type == 'github-hosted' && 'ubuntu-latest' || 'self-hosted' }}
    needs: [time-check]
    steps:
      # ... 构建步骤
```

---

## 🔧 配置步骤

### 步骤 1: 配置 Self-hosted Runner 标签

在本地 Runner 上配置标签，用于工作流路由：

```powershell
# 编辑 .runner 文件
cd C:\actions-runner
notepad .runner

# 配置标签
{
  "labels": [
    "self-hosted",
    "windows",
    "x64",
    "high-memory",    # 32G RAM
    "gpu",            # 32G VRAM
    "10t-storage",    # 10T HD
    "fast-ssd"        # 1T SSD
  ]
}
```

### 步骤 2: 配置 Runner 组

在 GitHub 仓库中创建 Runner 组：

1. **Settings → Actions → Runners → Runner groups**
2. **Create runner group**
   - Name: `local-runners`
   - Type: `Selected repositories`
   - Repositories: `sisys`
   - Runners: `sisys-local-runner`

### 步骤 3: 更新工作流配置

根据选择的方案更新 `.github/workflows/ci.yml`。

---

## 📊 成本效益分析

### GitHub-hosted 成本

| 项目 | 用量 | 单价 | 月成本 |
|------|------|------|--------|
| Actions Minutes | 3000 分钟/月 | $0.008/分钟 | $24 |
| Storage | 5GB | $0.02/GB | $0.1 |
| Bandwidth | 10GB | $0.02/GB | $0.2 |
| **总计** | | | **$24.3/月** |

### Self-hosted 成本

| 项目 | 用量 | 单价 | 月成本 |
|------|------|------|--------|
| 电费 | 50kWh/月 | ¥0.6/kWh | ¥30 ($4.2) |
| 硬件折旧 | ¥20000/3 年 | - | ¥555 ($77) |
| 网络 | 100GB | ¥0.1/GB | ¥10 ($1.4) |
| **总计** | | | **$82.6/月** |

**注意：** Self-hosted 硬件已购买，折旧为沉没成本。实际边际成本仅 **$5.6/月**（电费 + 网络）。

### 混合方案成本

| 项目 | GitHub-hosted | Self-hosted | 总计 |
|------|--------------|-------------|------|
| 轻量 Job (40%) | $9.72 | - | $9.72 |
| 重量 Job (60%) | - | $3.36 | $3.36 |
| **总计** | **$9.72** | **$3.36** | **$13.08/月** |

**节省：** 相比纯 GitHub-hosted 节省 **46%** ($24.3 → $13.08)

---

## 🚀 性能优化

### 1. 并行执行

```yaml
# 轻量 Job 并行
code-quality:
  runs-on: ubuntu-latest

unit-tests:
  runs-on: ubuntu-latest
  needs: code-quality  # 依赖但可并行

# 重量 Job 并行
integration-tests:
  runs-on: self-hosted

ai-model-tests:
  runs-on: self-hosted
  needs: integration-tests  # 依赖但可并行
```

### 2. 缓存优化

```yaml
- name: Cache Poetry dependencies
  uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pypoetry
      .venv
    key: ${{ runner.os }}-poetry-${{ hashFiles('**/poetry.lock') }}
    restore-keys: |
      ${{ runner.os }}-poetry-

- name: Cache Docker layers
  uses: actions/cache@v4
  with:
    path: /var/lib/docker
    key: ${{ runner.os }}-docker-${{ github.sha }}
```

### 3. 增量构建

```yaml
- name: Build Docker image (incremental)
  uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
    # 仅构建变更层
    build-args: |
      BUILDKIT_INLINE_CACHE=1
```

---

## 📈 监控指标

### Runner 健康度

```yaml
- name: Runner Health Check
  run: |
    echo "CPU: $(Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average | Select-Object -ExpandProperty Average)%"
    echo "Memory: $((Get-WmiObject Win32_OperatingSystem | Select-Object @{N='Free';E={[math]::Round(($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/1MB,2)})}).Free GB"
    echo "Disk: $((Get-WmiObject Win32_LogicalDisk -DeviceId 'C:' | Select-Object @{N='Free';E={[math]::Round($_.FreeSpace/1GB,2)})}).Free GB"
```

### 构建时间追踪

在工作流中添加时间追踪：

```yaml
- name: Record start time
  run: echo "START_TIME=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" >> $GITHUB_ENV

# ... 构建步骤

- name: Record end time
  run: |
    $end = Get-Date
    Write-Host "Build completed at: $end"
    Write-Host "Total time: $(New-TimeSpan -Start $env:START_TIME -End $end)"
```

---

## 🔒 安全考虑

### 1. 网络隔离

```powershell
# 配置 Windows 防火墙
# 仅允许 GitHub Actions IP

$github_ips = @(
    "140.82.112.0/20",
    "143.55.64.0/20",
    "185.199.108.0/22",
    "192.30.252.0/22"
)

foreach ($ip in $github_ips) {
    New-NetFirewallRule -DisplayName "GitHub Actions" -RemoteAddress $ip -Direction Inbound -Action Allow
}
```

### 2. Runner 权限

```powershell
# 使用最小权限原则
# 创建专用服务账户
New-LocalUser -Name "github-runner" -Password (ConvertTo-SecureString "StrongPassword123!" -AsPlainText -Force)

# 仅分配必要权限
Add-LocalGroupMember -Group "Users" -Member "github-runner"
```

### 3. Secrets 管理

```yaml
# 使用 GitHub Secrets
- name: Deploy
  run: |
    docker login -u ${{ secrets.DOCKER_USERNAME }} -p ${{ secrets.DOCKER_PASSWORD }}
```

---

## 🎯 推荐方案

**对于当前项目，推荐采用 方案 A（按 Job 类型路由）：**

| Job 类型 | Runner 类型 | 理由 |
|---------|------------|------|
| Code Quality | GitHub-hosted | 快速、无外部依赖 |
| Unit Tests | GitHub-hosted | 快速、并行执行 |
| Security Scans | GitHub-hosted | 轻量、标准化 |
| **Integration Tests** | **Self-hosted** | **需要数据库、大内存** |
| **Docker Build** | **Self-hosted** | **磁盘密集、1T SSD** |
| **AI Model Tests** | **Self-hosted** | **需要 GPU (32G VRAM)** |
| **Performance Tests** | **Self-hosted** | **需要大内存 (32G)** |
| Coverage Upload | GitHub-hosted | 轻量、标准化 |

**预期效果：**
- ✅ 解决磁盘空间问题
- ✅ 构建时间减少 50%+
- ✅ 成本节省 46%
- ✅ 支持 GPU 加速测试

---

**方案状态：** ⏳ 待实施
**预计实施时间：** 2-4 小时
**负责人：** Charlie (DevOps)
