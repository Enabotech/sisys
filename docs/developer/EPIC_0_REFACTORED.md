# Epic 0 重构：开发基础设施 + 产品交付系统 (双轨制)

**版本：** 2.0 (最终版)
**日期：** 2026-03-05
**状态：** ✅ 技术栈已由 Agimtech 验证

---

## 📋 Epic 0 概览

**目标：** 建立两套系统 - 开发 CI/CD 系统 + 产品交付系统

**轨道 1: 开发 CI/CD 系统** (面向工程师)
- Story 0.4: K3S 集群部署
- Story 0.5: Gitea 代码托管
- Story 0.6: Harbor 镜像仓库
- Story 0.7: ArgoCD 持续部署
- Story 0.8: Gitea Runner 配置
- Story 0.9: CI/CD Pipeline 模板

**轨道 2: SISYS 产品交付系统** (面向客户)
- Story 0.14: Windows 安装包
- Story 0.15: Mac 安装包
- Story 0.16: Linux 一键脚本
- Story 0.17: 自动检测与修复
- Story 0.18: 用户友好配置向导

---

## ✅ 技术栈最终确认

**所有版本已由 Agimtech 测试验证：**

| 组件 | 版本 | 状态 | 验证人 |
|------|------|------|--------|
| Gitea | v1.25.4 | ✅ 已发布 | Agimtech |
| Gitea Runner | latest | ✅ 活跃开发 | - |
| Harbor | v2.14.3 | ✅ 已发布 | - |
| ArgoCD | v3.3.2 | ✅ 已发布 | Agimtech |
| K3S | v1.34.5 | ✅ 稳定版 | - |

**风险等级：** 🟢 低 (所有版本已验证)

---

## 📦 价值组 1: 开发 CI/CD 系统

> 为开发团队提供企业级 CI/CD 基础设施

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 0.4 | **K3S 集群部署** | 提供轻量级 K8s 运行时 | 无依赖 | **P0-0** |
| Story 0.5 | **Gitea 代码托管** | 代码版本管理和协作 | 依赖 Story 0.4 | **P0-1** |
| Story 0.6 | **Harbor 镜像仓库** | 安全存储和分发 Docker 镜像 | 依赖 Story 0.4 | **P0-2** |
| Story 0.7 | **ArgoCD 持续部署** | GitOps 自动化部署 | 依赖 Story 0.5, 0.6 | **P0-3** |
| Story 0.8 | **Gitea Runner 配置** | 自动触发 CI/CD 任务 | 依赖 Story 0.5, 0.7 | **P0-4** |
| Story 0.9 | **CI/CD Pipeline 模板** | 标准化 Pipeline 复用 | 依赖 Story 0.8 | **P0-5** |

---

## 📦 价值组 2: SISYS 产品交付系统

> 为客户提供简单快捷的产品部署体验

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 0.14 | **Windows 安装包** | Windows 用户一键安装 | 无依赖 | **P0-6** |
| Story 0.15 | **Mac 安装包** | Mac 用户一键安装 | 无依赖 | **P0-7** |
| Story 0.16 | **Linux 一键脚本** | Linux 用户一键安装 | 无依赖 | **P0-8** |
| Story 0.17 | **自动检测与修复** | 安装问题自动修复 | 依赖 Story 0.14-0.16 | **P0-9** |
| Story 0.18 | **用户友好配置向导** | 图形化配置无需 YAML | 依赖 Story 0.17 | **P0-10** |

---

## Story 详细定义

### Story 0.4: K3S 集群部署

**As a** DevOps 工程师,
**I want** 在高性能 PC 上部署 K3S 集群,
**So that** 提供轻量级 K8s 运行时环境。

**Acceptance Criteria:**

**Given** 13700K + 32G RAM + 1T SSD + 10T HDD 系统
**When** 运行 K3S 安装脚本
**Then** K3S v1.34.5 安装成功
**And** Longhorn 存储配置完成
**And** Traefik 反向代理配置完成
**And** 集群健康检查通过

**技术栈:**
- K3S v1.34.5
- Longhorn v1.5.3
- Traefik v3.x

**TDD 测试要求:**
1. 集群部署测试 - 验证 K3S 安装成功
2. 存储配置测试 - 验证 Longhorn 可用
3. 网络配置测试 - 验证 Traefik 路由正常

**实施指南:** `docs/deployment/K3S_CLUSTER_SETUP.md`

---

### Story 0.5: Gitea 代码托管

**As a** 开发工程师,
**I want** 部署 Gitea v1.25.4 代码托管平台,
**So that** 团队可以进行代码版本管理和协作。

**Acceptance Criteria:**

**Given** K3S 集群已部署
**When** 运行 Gitea Helm Chart
**Then** Gitea v1.25.4 部署成功
**And** PostgreSQL 数据库配置完成
**And** HTTPS 证书配置完成
**And** 初始管理员账号创建成功

**技术栈:**
- Gitea v1.25.4 ✅ (已验证)
- PostgreSQL 15
- Helm v3

**TDD 测试要求:**
1. Gitea 部署测试 - 验证服务可访问
2. 数据库连接测试 - 验证 PostgreSQL 集成
3. HTTPS 配置测试 - 验证证书有效

**实施指南:** `docs/deployment/GITEA_INSTALLATION.md`

---

### Story 0.6: Harbor 镜像仓库

**As a** DevOps 工程师,
**I want** 部署 Harbor v2.14.3 镜像仓库,
**So that** 团队可以安全存储和分发 Docker 镜像。

**Acceptance Criteria:**

**Given** K3S 集群已部署
**When** 运行 Harbor Helm Chart
**Then** Harbor v2.14.3 部署成功
**And** 镜像仓库配置完成
**And** Trivy 漏洞扫描配置完成
**And** 镜像签名配置完成

**技术栈:**
- Harbor v2.14.3 ✅
- Trivy (漏洞扫描)
- Cosign (镜像签名)

**TDD 测试要求:**
1. Harbor 部署测试 - 验证服务可访问
2. 镜像推送测试 - 验证镜像可以推送
3. 漏洞扫描测试 - 验证 Trivy 集成

**实施指南:** `docs/deployment/HARBOR_INSTALLATION.md`

---

### Story 0.7: ArgoCD 持续部署

**As a** DevOps 工程师,
**I want** 部署 ArgoCD v3.3.2 持续部署工具,
**So that** 实现 GitOps 自动化部署。

**Acceptance Criteria:**

**Given** K3S 集群已部署
**When** 运行 ArgoCD 安装脚本
**Then** ArgoCD v3.3.2 部署成功
**And** Git 仓库集成配置完成
**And** 多环境 (Dev/Test/Prod) 配置完成
**And** 自动同步策略配置完成

**技术栈:**
- ArgoCD v3.3.2 ✅ (已验证)
- Git (代码仓库)
- Kustomize/Helm

**TDD 测试要求:**
1. ArgoCD 部署测试 - 验证服务可访问
2. Git 集成测试 - 验证仓库连接
3. 自动同步测试 - 验证 GitOps 流程

**实施指南:** `docs/deployment/ARGOCD_SETUP.md`

---

### Story 0.8: Gitea Runner 配置

**As a** DevOps 工程师,
**I want** 配置 Gitea Runner 执行 CI/CD 任务,
**So that** 代码提交后自动触发构建和测试。

**Acceptance Criteria:**

**Given** Gitea 和 K3S 已部署
**When** 注册 Gitea Runner
**Then** Runner 注册成功
**And** Docker Executor 配置完成
**And** Kubernetes Executor 配置完成 (可选)
**And** 并发控制配置完成

**技术栈:**
- Gitea Runner (最新版)
- Docker Executor (稳定)
- Kubernetes Executor (实验性)

**TDD 测试要求:**
1. Runner 注册测试 - 验证 Runner 在线
2. Docker Executor 测试 - 验证容器构建
3. K8s Executor 测试 - 验证 Pod 调度

**实施指南:** `docs/deployment/GITEA_RUNNER_SETUP.md`

---

### Story 0.9: CI/CD Pipeline 模板

**As a** 开发工程师,
**I want** 创建标准化的 CI/CD Pipeline 模板,
**So that** 所有项目可以复用最佳实践。

**Acceptance Criteria:**

**Given** Gitea + Runner + Harbor + ArgoCD 已部署
**When** 创建新项目
**Then** 可以复用 CI/CD 模板
**And** 包含代码质量检查
**And** 包含单元测试
**And** 包含集成测试
**And** 包含安全扫描
**And** 包含镜像构建
**And** 包含自动部署

**Pipeline 阶段:**
1. 代码质量门禁 (Ruff + MyPy)
2. 单元测试 (pytest + 覆盖率)
3. 集成测试 (Docker Compose)
4. 安全扫描 (Trivy + Bandit)
5. 镜像构建 (Docker Build)
6. 镜像推送 (Harbor)
7. 自动部署 (ArgoCD)

**实施指南:** `docs/deployment/CI_CD_PIPELINE_TEMPLATE.md`

---

### Story 0.14: Windows 安装包

**As a** SISYS 客户 (企业用户),
**I want** 通过图形化安装包在 Windows PC 上部署 SISYS,
**So that** 无需专业技术知识即可使用。

**Acceptance Criteria:**

**Given** Windows 10/11 高性能 PC
**When** 双击 sisys-setup.exe
**Then** 安装向导启动
**And** 自动检测 Docker (如未安装则自动安装)
**And** 自动配置端口和存储
**And** 5 分钟内完成部署
**And** 自动打开浏览器显示访问地址

**安装包内容:**
- sisys-setup.exe (150MB)
- 包含 Docker Desktop 安装包
- 包含 SISYS 产品镜像
- 包含自动配置脚本

**用户体验:**
1. 双击运行
2. 点击"下一步"
3. 等待 5 分钟
4. 完成！自动打开浏览器

**实施指南:** `docs/delivery/WINDOWS_INSTALLER.md`

---

### Story 0.15: Mac 安装包

**As a** SISYS 客户 (Mac 用户),
**I want** 通过 DMG 安装包在 macOS 上部署 SISYS,
**So that** 无需专业技术知识即可使用。

**Acceptance Criteria:**

**Given** macOS 12+ 高性能 Mac
**When** 打开 sisys-cicd.dmg
**Then** 拖拽到 Applications 即可
**And** 自动安装依赖
**And** 自动启动服务
**And** 自动打开浏览器

**安装包内容:**
- sisys-cicd.dmg (150MB)
- 包含 Docker Desktop 安装包
- 包含 SISYS 产品镜像
- 包含自动启动脚本

**实施指南:** `docs/delivery/MAC_INSTALLER.md`

---

### Story 0.16: Linux 一键脚本

**As a** SISYS 客户 (Linux 用户),
**I want** 通过一键脚本在 Linux 服务器上部署 SISYS,
**So that** 无需手动配置即可使用。

**Acceptance Criteria:**

**Given** Ubuntu 22.04 / Debian 11+ / CentOS 9
**When** 运行 `curl -sSL https://sisys.example.com/install.sh | bash`
**Then** 自动检测系统和依赖
**And** 自动安装 Docker
**And** 自动拉取镜像
**And** 自动启动服务
**And** 显示访问地址和密码

**脚本功能:**
- 系统检测
- 依赖安装
- 镜像拉取 (国内加速)
- 端口检测 (自动避让)
- 服务启动
- 密码显示

**实施指南:** `docs/delivery/LINUX_INSTALLER.md`

---

### Story 0.17: 自动检测与修复

**As a** SISYS 客户 (技术小白),
**I want** 安装过程自动检测和修复问题,
**So that** 遇到问题时不会卡住。

**Acceptance Criteria:**

**Given** 安装过程中
**When** 检测到问题
**Then** 自动尝试修复
**And** 修复失败时提供人话提示

**自动修复场景:**
1. 端口被占用 → 自动切换端口
2. 镜像下载失败 → 切换国内镜像源
3. 磁盘空间不足 → 提前预警并建议清理
4. 服务启动失败 → 自动重启并诊断

**人话提示示例:**
❌ 错误：Port 3000 already in use
✅ 提示：端口 3000 被占用，已自动改用 3001 端口

**实施指南:** `docs/delivery/AUTO_DIAGNOSE_AND_FIX.md`

---

### Story 0.18: 用户友好配置向导

**As a** SISYS 客户 (非技术人员),
**I want** 通过图形化向导配置系统,
**So that** 无需修改 YAML 配置文件。

**Acceptance Criteria:**

**Given** 安装完成后
**When** 打开配置向导
**Then** 显示图形化界面
**And** 提供预设配置模板
**And** 支持自定义配置
**And** 配置一键生效

**配置向导界面:**
```
┌────────────────────────────────────┐
│  Sisys 配置向导                     │
├────────────────────────────────────┤
│  设置管理员账号：                   │
│  用户名：[admin        ]           │
│  密码：  [••••••••    ]           │
│  邮箱：  [admin@example.com]      │
├────────────────────────────────────┤
│  选择安装路径：                     │
│  [C:\sisys              ] [浏览]  │
├────────────────────────────────────┤
│  选择端口：                         │
│  Gitea:  [3000]                   │
│  Harbor: [8080]                   │
│  ArgoCD: [8088]                   │
├────────────────────────────────────┤
│      [取消]        [应用]          │
└────────────────────────────────────┘
```

**实施指南:** `docs/delivery/CONFIG_WIZARD.md`

---

## 📋 原有 Story 处理

**Story 0.1 (开发环境搭建):**
- ✅ **保留** - 简化为 Python 环境配置
- 删除 Docker/K3S 相关内容（移到新 Story 0.4）
- 保留：Python 3.11+、Poetry、IDE 配置、SDD 工具链

**Story 0.2 (CI/CD 流水线):**
- ⚠️ **备份后废弃** - 被新 Story 0.4-0.9 替代
- 归档到 `docs/archive/old-story-0.2.md`
- 保留价值：质量门禁概念、Pipeline 阶段设计

**Story 0.3 (测试框架搭建):**
- ✅ **根据新 Story 完善优化** - 与新 Story 0.9 配合使用
- 保留：pytest 配置、Fixture 系统、Mock 框架
- 优化：与新 CI/CD 系统集成、增加 K3S 测试支持

---

## 📚 文档刷新清单

### 部署文档 (6 篇)
- [ ] `docs/deployment/K3S_CLUSTER_SETUP.md`
- [ ] `docs/deployment/GITEA_INSTALLATION.md`
- [ ] `docs/deployment/HARBOR_INSTALLATION.md`
- [ ] `docs/deployment/ARGOCD_SETUP.md`
- [ ] `docs/deployment/GITEA_RUNNER_SETUP.md`
- [ ] `docs/deployment/CI_CD_PIPELINE_TEMPLATE.md`

### 交付文档 (5 篇)
- [ ] `docs/delivery/WINDOWS_INSTALLER.md`
- [ ] `docs/delivery/MAC_INSTALLER.md`
- [ ] `docs/delivery/LINUX_INSTALLER.md`
- [ ] `docs/delivery/AUTO_DIAGNOSE_AND_FIX.md`
- [ ] `docs/delivery/CONFIG_WIZARD.md`

### 更新文档 (3 篇)
- [x] `epics_v1.0.md` - 更新 Epic 0 Story ✅
- [ ] `architecture.md` - 更新架构图
- [ ] `README.md` - 更新快速开始

---

## ✅ 完成标准

**轨道 1 (开发 CI/CD):**
- [ ] K3S 集群部署完成
- [ ] Gitea v1.25.4 部署完成
- [ ] Harbor v2.14.3 部署完成
- [ ] ArgoCD v3.3.2 部署完成
- [ ] Gitea Runner 配置完成
- [ ] CI/CD Pipeline 模板可用

**轨道 2 (产品交付):**
- [ ] Windows 安装包可用
- [ ] Mac 安装包可用
- [ ] Linux 一键脚本可用
- [ ] 自动检测与修复功能可用
- [ ] 用户友好配置向导可用

---

**文档状态：** ✅ 最终版
**技术栈验证：** Agimtech ✅
**实施负责人：** Charlie (轨道 1) + Alice (轨道 2)
**预计完成时间：** 4 周
