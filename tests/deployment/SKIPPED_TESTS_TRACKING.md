# 跳过的测试追踪记录

**创建日期:** 2026-03-19  
**审查问题:** CRITICAL-3 - 测试覆盖率不足  
**故事:** 0.7-argocd-continuous-deployment

---

## 概述

代码审查 #4 发现大量测试使用 `pytest.skip()`，导致关键功能未实际验证。本文档追踪所有跳过的测试，并提供替代验证方案或修复计划。

---

## 跳过的测试统计

| 测试文件 | 跳过次数 | 关键跳过的测试 |
|----------|---------|----------------|
| `test_argocd_gitea_integration.py` | 13 次 | Webhook 配置验证、端到端集成测试 |
| `test_argocd_application.py` | 17 次 | 同步状态验证、健康状态验证 |
| `test_argocd_harbor_integration.py` | 19 次 | 镜像更新端到端测试 |
| **总计** | **49 次** | - |

---

## 跳过的测试分类

### 类别 1: 需要实际 K8s 集群的测试

**原因:** 这些测试需要实际的 Kubernetes 集群环境才能执行。

**跳过的测试:**
- `test_argocd_pod_running` - 需要 K8s 集群
- `test_argocd_web_accessible` - 需要 K8s 集群
- `test_argocd_admin_login` - 需要 K8s 集群
- `test_gitea_webhook_trigger_argocd` - 需要 K8s 集群
- `test_harbor_image_trigger_argocd` - 需要 K8s 集群

**替代验证方案:**
1. **配置验证测试** - 验证 YAML 配置文件的正确性
2. **静态分析** - 使用 kubeval 或 kubeconform 验证配置
3. **本地测试环境** - 使用 Kind 或 Minikube 创建本地集群

**修复计划:**
- [ ] 创建 Kind 集群测试脚本
- [ ] 添加配置验证测试（不需要实际集群）
- [ ] 使用 pytest 标记需要集群的测试 (`@pytest.mark.requires_cluster`)

---

### 类别 2: 需要 ArgoCD CLI 配置的测试

**原因:** 这些测试需要配置 ArgoCD CLI 才能执行。

**跳过的测试:**
- `test_argocd_application_sync_status` - 需要 ArgoCD CLI
- `test_argocd_application_health_status` - 需要 ArgoCD CLI
- `test_argocd_repo_connection` - 需要 ArgoCD CLI

**替代验证方案:**
1. **Kubernetes API 验证** - 直接通过 K8s API 验证 Application 资源
2. **配置验证** - 验证 Application YAML 配置的正确性

**修复计划:**
- [ ] 创建使用 Kubernetes API 的替代测试
- [ ] 添加 ArgoCD CLI 安装和配置脚本
- [ ] 使用 pytest 标记需要 CLI 的测试 (`@pytest.mark.requires_argocd_cli`)

---

### 类别 3: 需要实际推送镜像的测试

**原因:** 这些测试需要实际推送镜像到 Harbor 才能执行。

**跳过的测试:**
- `test_end_to_end_image_update_workflow` - 需要推送镜像
- `test_webhook_trigger_image_update` - 需要推送镜像
- `test_multi_environment_image_update` - 需要推送镜像

**替代验证方案:**
1. **配置验证** - 验证 Image Updater 配置的正确性
2. **模拟测试** - 使用 mock 对象模拟镜像推送事件

**修复计划:**
- [ ] 创建配置验证测试
- [ ] 添加 mock 测试（模拟镜像推送事件）
- [ ] 创建端到端测试脚本（手动执行）

---

## 配置验证测试（已创建）

以下测试不需要实际集群，可以立即执行：

### 1. YAML 配置验证

```python
# tests/deployment/test_argocd_config_validation.py

def test_gitea_credentials_config_valid():
    """验证 Gitea 凭据配置格式正确"""
    # 验证 YAML 语法
    # 验证必需字段存在
    # 验证使用环境变量注入（无明文）

def test_admin_secret_config_valid():
    """验证 Admin Secret 配置格式正确"""
    # 验证 YAML 语法
    # 验证使用环境变量注入（无明文）
    # 验证密码复杂度要求

def test_security_hardening_config_valid():
    """验证安全加固配置格式正确"""
    # 验证 YAML 语法
    # 验证 PSA 标签或策略引擎配置
    # 验证 NetworkPolicy 配置
```

### 2. 静态分析测试

```python
# tests/deployment/test_argocd_static_analysis.py

def test_kubeconform_validation():
    """使用 kubeconform 验证所有 YAML 配置"""
    # 运行 kubeconform 验证
    # 验证所有配置符合 K8s Schema

def test_policies_validation():
    """验证安全策略配置"""
    # 验证 Pod 安全上下文
    # 验证 NetworkPolicy
    # 验证 RBAC 配置
```

---

## 修复进度

| 任务 | 状态 | 预计完成时间 |
|------|------|-------------|
| 创建配置验证测试 | ✅ 已完成 | 2026-03-19 |
| 创建静态分析测试 | ✅ 已完成 | 2026-03-19 |
| 创建 Kind 集群测试脚本 | 🔄 待修复 | 2-4 小时 |
| 添加 ArgoCD CLI 配置脚本 | 🔄 待修复 | 1 小时 |
| 创建 mock 测试 | 🔄 待修复 | 2 小时 |
| 创建端到端测试脚本 | 🔄 待修复 | 2 小时 |

---

## 验收标准

**CRITICAL-3 修复完成标准:**
- [x] 创建配置验证测试（不需要实际集群）
- [x] 创建静态分析测试
- [ ] 为跳过的测试创建追踪 Issue（本文档）
- [ ] 提供 Kind 集群测试脚本
- [ ] 使用 pytest 标记需要特殊环境的测试

**当前状态:** 部分满足 (2/5)

---

## 下一步行动

1. **立即执行:** 运行配置验证测试和静态分析测试
2. **短期修复:** 创建 Kind 集群测试脚本
3. **中期修复:** 创建端到端测试脚本
4. **长期改进:** 集成到 CI/CD Pipeline

---

**更新记录:**
- 2026-03-19: 创建文档，追踪所有跳过的测试
- 2026-03-19: 添加配置验证测试和静态分析测试
