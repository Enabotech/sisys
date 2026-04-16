# 脚本目录迁移记录

**迁移日期：** 2026-03-19
**迁移原因：** 统一脚本目录结构，将所有部署相关脚本集中到 `scripts/deployment/`

---

## 迁移详情

### 目录结构变更

**迁移前：**
```
scripts/
├── argocd/              # 12 个 ArgoCD 脚本
├── harbor/              # 5 个 Harbor 脚本
└── deployment/
    ├── argocd/         # 空
    ├── harbor/         # 5 个脚本
    └── k3s/            # 10 个脚本
```

**迁移后：**
```
scripts/
└── deployment/
    ├── argocd/         # 12 个（从 scripts/argocd/ 移入）
    ├── harbor/         # 5 个（从 scripts/harbor/ 移入）
    ├── k3s/            # 10 个
    └── gitea-runner/   # 新增
```

### 迁移的文件

**从 `scripts/argocd/` 迁移到 `scripts/deployment/argocd/`：**
1. check-gitea-repos.py
2. check-gitea-scopes.py
3. configure-gitea-integration.sh
4. configure-gitea-webhook.sh
5. configure-image-updater-secret.sh
6. configure-image-updater.py
7. create-gitea-org-repo.py
8. delete-existing-tokens.py
9. deploy-application.py
10. setup-gitea-integration.py
11. update-webhook-url.py
12. verify-gitea-webhook.py

**从 `scripts/harbor/` 迁移到 `scripts/deployment/harbor/`：**
1. harbor-autofix.service
2. harbor-autofix.sh
3. install-autofix.sh
4. verify-and-fix.sh
5. verify-deployment.sh

---

## 需要更新的文件清单

### 高优先级（直接影响使用）

- [x] `docs/deployment/ARGOCD_IMAGE_UPDATER.md` - 2 处引用
- [x] `docs/deployment/ARGOCD_GITEA_TROUBLESHOOTING.md` - 1 处引用
- [x] `docs/deployment/ARGOCD_GITEA_INTEGRATION.md` - 1 处引用
- [x] `_bmad-output/implementation-artifacts/stories/0-7-argocd-continuous-deployment.md` - 20+ 处引用

### 中优先级（注释和文档）

- [x] `deploy/kubernetes/argocd/image-updater-install.yaml` - 1 处注释
- [x] `scripts/deployment/argocd/deploy-application.py` - 1 处文档字符串
- [x] `scripts/deployment/argocd/configure-image-updater.py` - 5 处文档字符串

### 低优先级（配置和测试）

- [x] `.pre-commit-config.yaml` - 1 处注释
- [x] `tests/deployment/test_argocd_multi_environment.py` - 1 处引用

---

## 替换规则

所有路径替换遵循以下规则：

```
scripts/argocd/     →  scripts/deployment/argocd/
scripts/harbor/     →  scripts/deployment/harbor/
```

---

## 验证步骤

迁移完成后，需要验证以下内容：

1. **文档链接检查**
   ```bash
   # 检查文档中是否还有旧路径引用
   grep -r "scripts/argocd/" docs/ --include="*.md"
   grep -r "scripts/harbor/" docs/ --include="*.md"
   ```

2. **脚本执行测试**
   ```bash
   # 测试主要脚本是否可以正常执行
   bash scripts/deployment/argocd/configure-gitea-webhook.sh
   python scripts/deployment/argocd/deploy-application.py --help
   ```

3. **测试用例验证**
   ```bash
   # 运行相关测试
   pytest tests/deployment/test_argocd_multi_environment.py -v
   ```

---

## 回滚方案

如果需要回滚到旧结构：

```bash
# 1. 移回 ArgoCD 脚本
mv scripts/deployment/argocd/* scripts/argocd/
rmdir scripts/deployment/argocd

# 2. 移回 Harbor 脚本
mv scripts/deployment/harbor/* scripts/harbor/
rmdir scripts/deployment/harbor

# 3. 更新所有文档引用回旧路径
# （使用 git revert 或手动替换）
```

---

## 相关文档

- [Story 0.7: ArgoCD 持续部署](_bmad-output/implementation-artifacts/stories/0-7-argocd-continuous-deployment.md)
- [Story 0.8: Gitea Runner 配置](_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md)
- [ArgoCD 镜像更新器配置](docs/deployment/ARGOCD_IMAGE_UPDATER.md)
- [ArgoCD Gitea 集成指南](docs/deployment/ARGOCD_GITEA_INTEGRATION.md)

---

**迁移状态：** ✅ 完成
**最后更新：** 2026-03-19
