# GitHub Secrets 配置指南

**Story 0.2:** CI/CD 流水线  
**配置方式：** 手动配置（需要仓库管理员权限）  
**配置时间：** 约 5-10 分钟

---

## 📁 访问 GitHub Secrets

1. 打开 GitHub 仓库页面
2. 点击 **Settings** 标签
3. 左侧菜单选择 **Secrets and variables** → **Actions**
4. 点击 **New repository secret** 按钮

---

## 🔑 必需配置的 Secrets

### 1. CODECOV_TOKEN（可选但推荐）

**用途：** 上传测试覆盖率报告到 Codecov

**获取步骤：**
1. 访问 [codecov.io](https://codecov.io/)
2. 使用 GitHub 账号登录
3. 添加你的仓库
4. 在 Settings → General 中找到 **Repository Upload Token**
5. 复制 Token

**配置：**
```
Name: CODECOV_TOKEN
Value: <从 Codecov 复制的 Token>
```

---

### 2. GHCR_TOKEN（可选，如果需要推送 Docker 镜像）

**用途：** 推送 Docker 镜像到 GitHub Container Registry

**获取步骤：**
1. 访问 GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 点击 **Generate new token (classic)**
3. 选择 scopes：
   - `read:packages`
   - `write:packages`
   - `delete:packages`（可选）
4. 生成并复制 Token

**配置：**
```
Name: GHCR_TOKEN
Value: <生成的 Personal Access Token>
```

**注意：** CI/CD 流水线默认使用 `GITHUB_TOKEN`（自动提供），此 Secret 仅在需要额外权限时使用。

---

### 3. SLACK_WEBHOOK_URL（可选）

**用途：** 部署成功后发送 Slack 通知

**获取步骤：**
1. 打开 Slack 工作区
2. 选择要通知的频道
3. 点击频道名称 → Integrations → Add an App
4. 搜索 **Incoming Webhooks**
5. 点击 **Add to Slack** 并选择频道
6. 复制 Webhook URL

**配置：**
```
Name: SLACK_WEBHOOK_URL
Value: https://hooks.slack.com/services/XXXXX/YYYYY/ZZZZZ
```

---

### 4. DINGTALK_WEBHOOK（可选）

**用途：** 部署成功后发送钉钉通知

**获取步骤：**
1. 打开钉钉群聊
2. 点击右上角设置 → 智能群助手 → 添加机器人
3. 选择 **自定义** 机器人
4. 设置机器人名称（如：sisys CI/CD）
5. 勾选 **加签**（记录密钥）
6. 复制 Webhook 地址

**配置：**
```
Name: DINGTALK_WEBHOOK
Value: https://oapi.dingtalk.com/robot/send?access_token=XXXXX
```

**可选：** 如果需要加签验证，还需配置：
```
Name: DINGTALK_SECRET
Value: <机器人密钥>
```

---

### 5. GRAFANA_ADMIN_USER（可选，监控用）

**用途：** Grafana 仪表盘管理员账号

**配置：**
```
Name: GRAFANA_ADMIN_USER
Value: admin
```

---

### 6. GRAFANA_ADMIN_PASSWORD（可选，监控用）

**用途：** Grafana 仪表盘管理员密码

**配置：**
```
Name: GRAFANA_ADMIN_PASSWORD
Value: <设置强密码>
```

**安全提示：** 使用强密码（至少 12 位，包含大小写字母、数字、特殊字符）

---

## 📋 完整 Secrets 列表

| Secret 名称 | 必需 | 说明 | 示例值 |
|-----------|------|------|--------|
| `CODECOV_TOKEN` | 可选 | Codecov 上传 Token | `abc123...` |
| `GHCR_TOKEN` | 可选 | GitHub Container Registry Token | `ghp_...` |
| `SLACK_WEBHOOK_URL` | 可选 | Slack 通知 Webhook | `https://hooks.slack.com/...` |
| `DINGTALK_WEBHOOK` | 可选 | 钉钉通知 Webhook | `https://oapi.dingtalk.com/...` |
| `DINGTALK_SECRET` | 可选 | 钉钉加签密钥 | `SEC...` |
| `GRAFANA_ADMIN_USER` | 可选 | Grafana 管理员账号 | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | 可选 | Grafana 管理员密码 | `<强密码>` |

---

## 🔧 配置步骤（图文说明）

### 步骤 1: 访问 Secrets 页面

```
GitHub 仓库 → Settings → Secrets and variables → Actions
```

### 步骤 2: 添加新 Secret

1. 点击 **New repository secret** 按钮
2. 填写 Name 和 Value
3. 点击 **Add secret** 保存

### 步骤 3: 验证配置

推送代码后，访问 **Actions** 标签查看流水线执行：
- CI 流水线应成功上传覆盖率到 Codecov
- CD 流水线应发送 Slack/钉钉通知（如果配置）

---

## 🛡️ 安全最佳实践

### 1. 最小权限原则

- 仅授予必要的权限
- 使用仓库级 Secret，不使用组织级（除非必需）

### 2. 定期轮换

- 每 90 天轮换一次 Token
- 员工离职后立即轮换

### 3. 环境隔离

- 生产环境使用独立的 Secret
- 使用 GitHub Environments 功能隔离

**配置环境保护规则：**
1. Settings → Environments → New environment
2. 命名为 `production`
3. 启用 **Required reviewers**（需要审批）
4. 添加保护分支（如 `main`）

### 4. 审计日志

- 定期检查 Secret 访问日志
- Settings → Security → Secret scanning

---

## 🧪 验证配置

### 验证 Codecov

1. 推送代码到仓库
2. 访问 GitHub Actions 查看 CI 流水线
3. 确认 "Upload Coverage to Codecov" Job 成功
4. 访问 Codecov 查看覆盖率报告

### 验证通知

1. 推送代码到 `main` 分支
2. 等待 CD 流水线完成
3. 检查 Slack/钉钉是否收到通知

**测试通知消息：**
```yaml
# 在 .github/workflows/cd.yml 中添加测试步骤
- name: Test Slack notification
  run: |
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"🧪 Test notification from sisys CI/CD"}' \
      $SLACK_WEBHOOK_URL
```

---

## 🚨 常见问题

### Q1: Secret 不生效？

**检查：**
- Secret 名称是否正确（区分大小写）
- 是否在正确的仓库配置
- 工作流文件中是否正确引用（`${{ secrets.SECRET_NAME }}`）

### Q2: Codecov 上传失败？

**检查：**
- Token 是否正确复制（无多余空格）
- 仓库是否已在 Codecov 添加
- CI 流水线中 `codecov-action` 版本是否正确

### Q3: Slack 通知收不到？

**检查：**
- Webhook URL 是否正确
- Slack 频道权限设置
- 防火墙是否阻止 webhook

### Q4: 钉钉通知收不到？

**检查：**
- Webhook URL 和 Secret 是否正确
- 机器人是否已添加到群聊
- 加签配置是否匹配

---

## 📝 配置检查清单

在开始部署前，请确认以下配置完成：

- [ ] 访问 GitHub 仓库 Settings
- [ ] 进入 Secrets and variables → Actions
- [ ] 配置 CODECOV_TOKEN（可选）
- [ ] 配置 SLACK_WEBHOOK_URL（可选）
- [ ] 配置 DINGTALK_WEBHOOK（可选）
- [ ] 配置 GRAFANA_ADMIN_USER（可选）
- [ ] 配置 GRAFANA_ADMIN_PASSWORD（可选）
- [ ] 验证所有 Secret 名称拼写正确
- [ ] 推送测试代码验证配置

---

## 🎯 下一步

配置完成后：

1. **推送代码到仓库**
   ```bash
   git add .
   git commit -m "feat: Story 0.2 CI/CD pipeline"
   git push origin main
   ```

2. **验证 CI/CD 流水线**
   - 访问 GitHub Actions 标签
   - 确认所有 Job 成功运行
   - 检查通知是否收到

3. **检查部署结果**
   - 测试环境是否成功部署
   - 健康检查是否通过
   - 覆盖率报告是否上传

---

**🎉 配置完成！**

**参考文档：**
- [GitHub Actions Secrets 官方文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Codecov 文档](https://docs.codecov.com/)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [钉钉群机器人](https://open.dingtalk.com/document/robots/custom-robot-access)
