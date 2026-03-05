# Self-hosted Runner 快速启动指南

**5 分钟快速配置 Self-hosted Runner**
**日期：** 2026-03-05

---

## ⚡ 快速开始（3 步）

### 步骤 1: 获取 GitHub Token

1. 打开 **https://github.com/Agimtech/sisys/settings/actions/runners**
2. 点击 **Add runner** 按钮
3. 复制 **Runner registration token**（1 小时有效）

```
┌─────────────────────────────────────────┐
│  Runner registration token              │
│  ┌─────────────────────────────────┐   │
│  │ ABCDEFGHIJKLMNOPQRSTUVWXYZ123   │ ← 复制这个
│  └─────────────────────────────────┘   │
│                                        │
│  ⏱️  Expires in 59 minutes             │
└─────────────────────────────────────────┘
```

---

### 步骤 2: 运行安装脚本

**PowerShell (管理员):**

```powershell
# 进入脚本目录
cd g:\ai\sisys\scripts

# 运行安装脚本（替换 YOUR_TOKEN）
.\setup-runner.ps1 -GitHubToken "ABCDEFGHIJKLMNOPQRSTUVWXYZ123"   # pragma: allowlist secret
```

**预期输出：**

```
=== 1. 系统检查 ===
✓ C 盘可用空间：512.5GB
✓ Docker 已安装：Docker version 25.0.3
✓ Docker 服务运行正常
✓ Git 已安装：git version 2.44.0

=== 2. 创建安装目录 ===
✓ 目录创建成功：C:\actions-runner

=== 3. 下载 GitHub Actions Runner ===
最新版本：v2.322.0
✓ 下载完成

=== 4. 解压 Runner ===
✓ 解压完成

=== 5. 配置 Runner ===
✓ Runner 配置成功

=== 6. 注册为 Windows 服务 ===
✓ 服务安装成功

=== 7. 配置 Docker Buildx ===
✓ Buildx builder 创建成功

=== 8. 配置防火墙规则 ===
✓ 防火墙规则配置完成

=== 9. 启动 Runner 服务 ===
✓ 服务启动成功

=== ✅ 安装完成！ ===
```

---

### 步骤 3: 验证 Runner

**在 GitHub 仓库中验证：**

1. 访问：**https://github.com/Agimtech/sisys/settings/actions/runners**
2. 查看 Runner 列表
3. 确认状态为 **Online** ✅

```
┌─────────────────────────────────────────┐
│  Runners                                │
│                                         │
│  🟢 sisys-local-runner                  │
│     self-hosted, windows, x64, gpu     │
│     Last online: now                   │
│     Status: Online ✅                  │
└─────────────────────────────────────────┘
```

---

## 🧪 测试 Runner

### 推送测试代码

```bash
# 提交一个小改动
git add .
git commit -m "test: trigger CI with self-hosted runner"
git push origin develop
```

### 查看工作流运行

1. 访问：**https://github.com/Agimtech/sisys/actions**
2. 查看最新的工作流运行
3. 确认 Job 使用了 **sisys-local-runner**

```
┌─────────────────────────────────────────┐
│  Workflow runs                          │
│                                         │
│  ✅ test: trigger CI...                 │
│     Run #123 by Agimtech                │
│     sisys-local-runner                  │
│     Total time: 3m 25s                 │
└─────────────────────────────────────────┘
```

---

## 🔧 常用命令

### 管理 Runner 服务

```powershell
# 查看状态
cd C:\actions-runner
.\manage-runner.ps1 status

# 启动服务
.\manage-runner.ps1 start

# 重启服务
.\manage-runner.ps1 restart

# 停止服务
.\manage-runner.ps1 stop

# 查看日志
.\manage-runner.ps1 logs

# 卸载服务
.\manage-runner.ps1 uninstall
```

### Docker 管理

```powershell
# 查看 Buildx builders
docker buildx ls

# 清理 Docker
docker system prune -af --volumes

# 查看 Docker 镜像
docker images

# 查看 Docker 容器
docker ps -a
```

---

## 📊 性能对比

| 指标 | GitHub-hosted | Self-hosted (本地) | 提升 |
|------|--------------|-------------------|------|
| **构建时间** | 15-30 分钟 | 3-8 分钟 | **3-5x** ⚡ |
| **磁盘空间** | 14GB 限制 | 1TB SSD | **70x+** 💾 |
| **内存** | 7-16GB | 32GB | **2-4x** 🧠 |
| **成本** | $0.008/分钟 | 电费 (~$5/月) | **90% 节省** 💰 |

---

## ⚠️ 常见问题

### Q1: Runner 显示 Offline

**解决：**

```powershell
# 检查服务状态
.\manage-runner.ps1 status

# 重启服务
.\manage-runner.ps1 restart

# 查看日志
.\manage-runner.ps1 logs
```

如果还是 Offline，重新运行安装脚本获取新 Token。

---

### Q2: Docker 构建失败

**解决：**

```powershell
# 清理 Docker
docker system prune -af --volumes

# 重建 Buildx
docker buildx rm sisys-builder
docker buildx create --use --name sisys-builder

# 测试 Docker
docker run --rm hello-world
```

---

### Q3: 磁盘空间不足

**解决：**

```powershell
# 清理 Docker 镜像
docker image prune -af

# 清理 Runner 工作目录
Remove-Item -Path "C:\actions-runner\_work\*" -Recurse -Force

# 清理临时文件
Remove-Item -Path "$env:TEMP\*" -Recurse -Force
```

---

### Q4: GPU 不可用

**解决：**

```powershell
# 检查 NVIDIA 驱动
nvidia-smi

# 如果显示 GPU 信息，说明驱动正常
# 在工作流中使用 GPU 标签
runs-on: [self-hosted, windows, gpu]
```

---

## 🎯 下一步

### 配置工作流使用 Self-hosted Runner

**修改 `.github/workflows/ci.yml`:**

```yaml
build-docker:
  name: Build Docker Image
  runs-on: [self-hosted, windows, gpu]  # ← 使用本地 Runner
  timeout-minutes: 20
  # ... 其他配置
```

### 配置混合 CI/CD

参考文档：`docs/developer/HYBRID_CI_CD_SCHEME.md`

---

## 📞 获取帮助

**文档：**
- 完整配置指南：`docs/developer/SELF_HOSTED_RUNNER_SETUP.md`
- 混合 CI/CD 方案：`docs/developer/HYBRID_CI_CD_SCHEME.md`
- 安装脚本：`scripts/setup-runner.ps1`

**GitHub 资源：**
- [Self-hosted Runner 官方文档](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Runner 故障排查](https://docs.github.com/en/actions/hosting-your-own-runners/troubleshooting-self-hosted-runners)

---

## ✅ 检查清单

- [ ] 获取 GitHub Token
- [ ] 运行安装脚本
- [ ] 验证 Runner Online
- [ ] 测试推送代码
- [ ] 查看工作流运行
- [ ] 配置管理命令
- [ ] 了解故障排查

---

**完成时间：** 5-10 分钟
**难度：** ⭐⭐☆☆☆ (简单)
**负责人：** Charlie (DevOps)
