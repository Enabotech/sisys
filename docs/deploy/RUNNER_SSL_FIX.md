# Gitea Runner SSL 证书问题修复指南

## 🔴 问题症状

工作流失败，错误信息：
```
tls: failed to verify certificate: x509: certificate signed by unknown authority
```

## 📋 原因分析

1. **自签名 SSL 证书**: Gitea 和 Harbor 使用自签名证书
2. **Runner 不信任**: Gitea Runner 的 CA 证书库中没有这些证书
3. **Variables 缺失**: `HARBOR_REGISTRY` 变量未配置或为空

---

## 🛠️ 解决方案

### 步骤 1: 运行 SSL 修复脚本

```bash
# 赋予执行权限
chmod +x scripts/ci/fix-runner-ssl.sh

# 以 root 权限运行
sudo ./scripts/ci/fix-runner-ssl.sh
```

### 步骤 2: 配置 Gitea Variables

访问 Gitea 仓库设置，添加以下 Variables：

**URL**: `https://gitea.sisys.local/{owner}/{repo}/settings/actions/variables`

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `HARBOR_REGISTRY` | `harbor.sisys.local` | Harbor 仓库地址 |
| `HARBOR_PROJECT` | `sisys` | Harbor 项目名 |
| `GPU_ENABLED` | `false` | 是否启用 GPU (可选) |
| `GPU_RUNNER_LABEL` | `gpu-node` | GPU Runner 标签 (可选) |

**操作步骤**:
1. 登录 Gitea
2. 进入仓库 → 设置 → Actions → 变量
3. 点击"新建变量"
4. 添加上述变量

### 步骤 3: 验证配置

```bash
# 1. 验证 SSL 证书
curl -I https://gitea.sisys.local
curl -I https://harbor.sisys.local

# 2. 验证 Docker 登录
docker login https://harbor.sisys.local \
  -u 'robot$sisys+gitea-runner-push' \
  -p 'gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd'

# 3. 验证 Gitea Actions 连接
curl -H "Authorization: token 1f182aca3d38b66f7e49c034d98fb15bf02434b7" \
  https://gitea.sisys.local/api/v1/user/repos

# 4. 检查 Runner 状态
sudo systemctl status gitea-runner
```

### 步骤 4: 重新运行工作流

1. 访问：`https://gitea.sisys.local/{owner}/{repo}/actions`
2. 找到 `Build Dependency Image` 工作流
3. 点击"Run workflow"
4. 选择分支（main 或 develop）
5. 点击"Run workflow"

---

## 🔍 故障排查

### 问题 1: 证书仍然不信任

**症状**: 运行脚本后仍然报错

**解决**:
```bash
# 手动检查证书
ls -la /usr/local/share/ca-certificates/

# 重新生成证书
sudo update-ca-certificates --fresh

# 重启 Runner
sudo systemctl restart gitea-runner

# 查看 Runner 日志
sudo journalctl -u gitea-runner -f
```

### 问题 2: HARBOR_REGISTRY 为空

**症状**: 日志显示 `evaluated to '%!t(string=/sisys/...)'`

**解决**:
1. 确认 Variables 已正确配置（区分 Secrets 和 Variables）
2. 检查变量名拼写：`HARBOR_REGISTRY`（不是 `HARBOR_REGISTRY_URL`）
3. 重新运行工作流

### 问题 3: Docker 无法连接 Harbor

**症状**: `docker login` 失败

**解决**:
```bash
# 检查 Docker 证书
ls -la /etc/docker/certs.d/harbor.sisys.local/

# 手动配置
sudo mkdir -p /etc/docker/certs.d/harbor.sisys.local
sudo cp /usr/local/share/ca-certificates/harbor-sisys.crt \
  /etc/docker/certs.d/harbor.sisys.local/ca.crt

# 重启 Docker
sudo systemctl restart docker
```

### 问题 4: Runner 服务未运行

**症状**: `systemctl status gitea-runner` 失败

**解决**:
```bash
# 检查服务名
systemctl list-services | grep gitea

# 启动服务
sudo systemctl start gitea-runner

# 设置开机自启
sudo systemctl enable gitea-runner
```

---

## 📊 验证清单

- [ ] SSL 证书已安装到 `/usr/local/share/ca-certificates/`
- [ ] CA 证书库已更新 (`update-ca-certificates`)
- [ ] Docker 证书已配置到 `/etc/docker/certs.d/`
- [ ] Gitea Runner 已重启
- [ ] Gitea Variables 已配置
- [ ] `curl` 可以访问 Gitea 和 Harbor
- [ ] `docker login` 可以登录 Harbor
- [ ] 工作流可以成功运行

---

## 🔗 相关文档

- [CI_CD_ARGOCD_INTEGRATION_SUMMARY.md](./docs/deploy/CI_CD_ARGOCD_INTEGRATION_SUMMARY.md)
- [CI_CD_PIPELINE_TEMPLATE.md](./docs/deploy/CI_CD_PIPELINE_TEMPLATE.md)
- [build-dependency-image.yml](./.gitea/workflows/build-dependency-image.yml)

---

## 📞 联系支持

如果问题仍未解决，请提供以下信息：

1. Runner 日志：`sudo journalctl -u gitea-runner -n 100`
2. 工作流完整日志
3. 证书文件列表：`ls -la /usr/local/share/ca-certificates/`
4. Variables 配置截图
