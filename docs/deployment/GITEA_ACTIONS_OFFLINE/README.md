# Gitea Actions 本地化方案

> 📦 完整的 Actions 本地化解决方案，支持两种部署模式

---

## 🎯 快速开始

### 方案 1: Gitea 仓库镜像 ✅ 推荐

**适用**: 有外网访问

```bash
export GITEA_TOKEN="YOUR_GITEA_TOKEN"
export GITHUB_TOKEN="YOUR_GITHUB_TOKEN"

./scripts/actions/gitea-mirror-actions.sh create-all
```

### 方案 2: 脚本下载推送

**适用**: 完全离线环境

```bash
./scripts/actions/download-actions.sh
./scripts/image/import-pytorch.sh
./scripts/actions/validate-offline.sh
```

---

## 📊 方案对比

| 特性 | 方案 1: Gitea 镜像 | 方案 2: 脚本下载 |
|------|-----------------|----------------|
| 外网依赖 | ⚠️ 需要 (镜像时) | ✅ 仅首次 |
| 配置难度 | ⭐⭐ 简单 | ⭐⭐⭐ 中等 |
| 维护成本 | ⭐⭐ 自动同步 | ⭐⭐⭐ 手动 |
| 离线支持 | ❌ 否 | ✅ 完全离线 |

---

## 🛠️ 工具链

```
scripts/
├── actions/
│   ├── gitea-mirror-actions.sh    # Gitea 原生镜像配置
│   ├── download-actions.sh        # 批量下载 Actions
│   └── validate-offline.sh        # 离线环境验证
│
└── image/
    ├── import-pytorch.sh          # PyTorch 镜像导入
    └── cleanup-old-versions.sh    # 镜像清理
```

---

## 📚 文档导航

### 核心文档

| 文档 | 说明 |
|------|------|
| [最终总结](./FINAL_SUMMARY.md) | 技术总结和最佳实践 |
| [方案对比](./ACTIONS_MIRROR_COMPARISON.md) | 3 种方案详细对比 |

### 相关文档

| 文档 | 说明 |
|------|------|
| [CI/CD Pipeline 模板](../CI_CD_PIPELINE_TEMPLATE.md) | Pipeline 配置和使用 |
| [ArgoCD 集成](../CI_CD_ARGOCD_INTEGRATION_SUMMARY.md) | 持续部署配置 |
| [Secrets 配置](../CI_CD_SECRETS_GUIDE.md) | 敏感信息配置 |
| [故障排查](../CI_CD_TROUBLESHOOTING.md) | 常见问题解决 |

---

## 📦 Actions 镜像清单

| GitHub 仓库 | Gitea 仓库 | 用途 |
|------------|-----------|------|
| `actions/checkout@v4` | `actions/checkout` | 代码检出 |
| `actions/upload-artifact@v4` | `actions/upload-artifact` | 上传产物 |
| `docker/setup-buildx-action@v3` | `actions/setup-buildx-action` | Docker 构建 |
| `docker/login-action@v3` | `actions/login-action` | Harbor 登录 |
| `docker/build-push-action@v5` | `actions/build-push-action` | 镜像推送 |
| `aquasecurity/trivy-action@master` | `actions/trivy-action` | 安全扫描 |
| `Azure/k8s-set-context@v4` | `actions/k8s-set-context` | K8s 上下文 |
| `Azure/k8s-deploy@v5` | `actions/k8s-deploy` | K8s 部署 |

---

## ✅ 验证检查清单

- [ ] 配置 Gitea `DEFAULT_ACTIONS_URL = self`
- [ ] 创建所有 Actions 镜像仓库
- [ ] 导入 PyTorch 镜像到 Harbor
- [ ] 运行 `validate-offline.sh` 验证
- [ ] 测试工作流执行成功

---

## 🔧 维护指南

### 定期同步 (方案 1)

```bash
# 使用 Gitea 镜像功能自动同步
./scripts/actions/gitea-mirror-actions.sh sync-all
```

### 手动更新 (方案 2)

```bash
# 重新下载所有 Actions
./scripts/actions/download-actions.sh
```

---

**版本**: 2.0.0  
**更新日期**: 2026-03-25
