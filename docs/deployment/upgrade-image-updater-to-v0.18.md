# ArgoCD Image Updater 升级 v0.14.0 → v0.18.0 方案

> **编写日期**: 2026-04-05
> **最后更新**: 2026-04-05（补充 Webhook Secret 配置）
> **审批状态**: 待审批
> **执行窗口**: 任意（无停机风险，滚动升级约 30 秒）

---

## 📋 升级概览

| 项目 | 内容 |
|------|------|
| **当前版本** | v0.14.0 |
| **目标版本** | v0.18.0 |
| **镜像** | `harbor.sisys.local/sisys/tools/argoprojlabs/argocd-image-updater:v0.18.0` ✅ 已就绪 |
| **停机时间** | 约 30 秒（滚动升级） |
| **风险等级** | 低（配置兼容，仅行为修正） |
| **回滚方式** | `kubectl rollout undo` |

---

## ⚠️ 升级影响总结

| 配置项 | 升级前行为 | 升级后行为 | 影响 |
|--------|-----------|-----------|------|
| `update-strategy: newest-build` | 按字母序排序（`ac04e1f` 最大） | **按构建时间排序**（`4529fa4` 最新） | 🟡 升级后会立即触发更新 |
| `update-strategy: latest` | 当作 `newest-build` | **已废弃，报警告** | 🔴 需改回 `newest-build` |
| `registries.conf` 中 `ping: yes` | 有效 | **被忽略** | 🟢 无功能影响 |
| Webhook | 不支持 | **支持（需 `--enable-webhook`）** | 🟢 新增功能 |
| Webhook Secret | 无此概念 | **必须配置 `webhook.harbor-secret`** | 🔴 新增必填项 |
| Webhook 端点路径 | `/api/v1/webhook`（错误） | **`/webhook?type=harbor`** | 🔴 路径变更 |
| ArgoCD 兼容性 | v2.14.x | **v3.1.7+** | ✅ 当前 ArgoCD v3.2.7，完美兼容 |

### 核心行为变化

```
v0.14.0:  newest-build → 被当作 name(字母序) → ac04e1f 被认为最新
v0.18.0:  newest-build → 按构建时间排序   → 4529fa4 被认为最新
```

**这意味着升级后 dev/test 环境会立即检测到新版本并触发更新。**

---

## 🔧 修改清单（共 3 个文件 + 2 个 Secret 配置）

### 修改 1: `deployments/argocd/image-updater-install.yaml`

共 3 处修改：

#### 修改 1a: 镜像版本

```yaml
# 修改前
image: harbor.sisys.local/sisys/tools/argoprojlabs/argocd-image-updater:v0.14.0

# 修改后
image: harbor.sisys.local/sisys/tools/argoprojlabs/argocd-image-updater:v0.18.0
```

#### 修改 1b: 启动参数（添加 `--enable-webhook`）

```yaml
# 修改前
args:
  - run
  - --loglevel
  - info
  - --health-port
  - "8080"
  - --registries-conf-path
  - /app/config/registries.conf

# 修改后
args:
  - run
  - --loglevel
  - info
  - --health-port
  - "8080"
  - --enable-webhook
  - --registries-conf-path
  - /app/config/registries.conf
```

#### 修改 1c: 版本标识注释

```yaml
# 修改前
# 版本：v0.14.0 (对应 ArgoCD v3.2.x)

# 修改后
# 版本：v0.18.0 (兼容 ArgoCD v3.x)
```

---

### 修改 2: `deployments/argocd/applications/sisys-app-dev.yaml`

回滚之前错误的策略修改：

```yaml
# 修改前（错误地改成了 latest）
argocd-image-updater.argoproj.io/app.update-strategy: latest

# 修改后（恢复为官方新命名）
argocd-image-updater.argoproj.io/app.update-strategy: newest-build
```

---

### 修改 3: `deployments/argocd/applications/sisys-app-test.yaml`

同样回滚：

```yaml
# 修改前
argocd-image-updater.argoproj.io/app.update-strategy: latest

# 修改后
argocd-image-updater.argoproj.io/app.update-strategy: newest-build
```

---

### 修改 4: 更新 `argocd-image-updater-secret`（🔴 新增）

v0.18.0 要求 Webhook Secret 必须配置。

**v0.18.0 要求的 Secret 格式**:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-image-updater-secret
  namespace: argocd
type: Opaque
stringData:
  # Harbor 镜像拉取凭证（现有的，保持不变）
  harbor: "robot$sisys+argocd-pull:<TOKEN>"
  dockerhub: ""

  # ⚠️ 新增：Webhook 签名密钥（v0.18.0 新增要求）
  webhook.harbor-secret: "<自定义密钥字符串>"
```

**当前 Secret 状态对比**:

| 配置项 | 当前状态（v0.14） | 需要状态（v0.18） | 差异 |
|--------|------------------|------------------|------|
| `harbor` | ✅ 有值 | ✅ 保持不变 | 无变化 |
| `dockerhub` | ⚠️ 空字符串 | ⚠️ 可保持空 | 无变化 |
| `webhook.harbor-secret` | ❌ **不存在** | ❌ **必须添加** | 🔴 缺失 |

---

### 修改 5: 更新 Harbor Webhook URL（🔴 必须）

**在 Harbor Web UI 中修改**:

| 字段 | 旧值 | 新值 |
|------|------|------|
| URL | `http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook` | `http://argocd-image-updater.argocd.svc.cluster.local:8080/webhook?type=harbor` |
| Secret/Token | （未配置或占位符） | **与 `webhook.harbor-secret` 完全一致** |

**注意**:
- 端点路径是 `/webhook`，不是 `/api/webhook` 或 `/api/v1/webhook`
- 必须加查询参数 `?type=harbor`
- Harbor 属于"内置支持 Secret"的仓库，不使用 `?secret=` URL 参数方式

---

## 📝 升级步骤（按顺序执行）

### 步骤 1: 修改 YAML 文件

按上述修改 1-3 修改 3 个 YAML 文件。

### 步骤 2: 生成 Webhook Secret

```bash
# 生成随机密钥
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "========================================="
echo "请保存此 Webhook Secret: $WEBHOOK_SECRET"
echo "========================================="
```

**⚠️ 此密钥后续需要在 Harbor Web UI 中配置，请务必保存。**

### 步骤 3: 更新 Kubernetes Secret

```bash
# 获取现有 harbor token
EXISTING_HARBOR=$(kubectl get secret argocd-image-updater-secret -n argocd -o jsonpath='{.data.harbor}' | base64 -d)

# 创建新 Secret（包含 webhook secret）
kubectl create secret generic argocd-image-updater-secret \
  --from-literal=harbor="$EXISTING_HARBOR" \
  --from-literal=dockerhub="" \
  --from-literal="webhook.harbor-secret=$WEBHOOK_SECRET" \
  -n argocd --dry-run=client -o yaml | kubectl apply -f -

# 验证 Secret 已更新
kubectl get secret argocd-image-updater-secret -n argocd -o jsonpath='{.data}' | python3 -c "
import json, base64, sys
data = json.load(sys.stdin)
for k, v in data.items():
    decoded = base64.b64decode(v).decode()
    # 隐藏敏感信息
    if 'secret' in k.lower():
        print(f'{k}: **** (已配置)')
    elif decoded:
        print(f'{k}: {decoded[:20]}...')
    else:
        print(f'{k}: (空)')
"
```

**预期输出**:
```
harbor: robot$sisys+argocd-pull...
dockerhub: (空)
webhook.harbor-secret: **** (已配置)
```

### 步骤 4: 应用配置到集群

```bash
kubectl apply -f /mnt/g/ai/sisys/deployments/argocd/image-updater-install.yaml
kubectl apply -f /mnt/g/ai/sisys/deployments/argocd/applications/sisys-app-dev.yaml
kubectl apply -f /mnt/g/ai/sisys/deployments/argocd/applications/sisys-app-test.yaml
```

### 步骤 5: 重启 Image Updater

```bash
kubectl rollout restart deployment/argocd-image-updater -n argocd
```

### 步骤 6: 观察滚动升级

```bash
kubectl rollout status deployment/argocd-image-updater -n argocd --timeout=120s
```

### 步骤 7: 验证版本

```bash
kubectl exec -n argocd deployment/argocd-image-updater -- argocd-image-updater version
```

**预期输出**:
```
argocd-image-updater: v0.18.0+<commit>
  BuildDate: ...
  GitCommit: ...
  GoVersion: ...
  Platform: linux/amd64
```

### 步骤 8: 验证启动参数

```bash
kubectl get deployment argocd-image-updater -n argocd \
  -o jsonpath='{.spec.template.spec.containers[0].args}'
```

**预期输出**:
```
["run","--loglevel","info","--health-port","8080","--enable-webhook","--registries-conf-path","/app/config/registries.conf"]
```

### 步骤 9: 观察更新行为

```bash
# 观察日志，确认 newest-build 按构建时间排序
kubectl logs -n argocd deployment/argocd-image-updater -f | grep -E "newest-build|update|commit|push"
```

**预期输出**（dev/test 会触发更新）:
```
level=info msg="Successfully updated image 'harbor.sisys.local/sisys/app:dev-v1.0.0-ac04e1f' to 'harbor.sisys.local/sisys/app:dev-v1.0.0-4529fa4'"
level=info msg="Committing 1 parameter update(s) for application sisys-app-dev"
level=info msg="Successfully updated the live application spec"
```

### 步骤 10: 验证 Webhook 端点

```bash
kubectl run webhook-test -n harbor --image=curlimages/curl --rm -it --restart=Never --command -- \
  curl -sv -X POST http://argocd-image-updater.argocd.svc.cluster.local:8080/webhook?type=harbor \
  -H "Content-Type: application/json" \
  -d '{"type":"PUSH_ARTIFACT"}' 2>&1 | head -20
```

**预期输出**: 不再返回 `404 Not Found`（可能返回 200 或 400，说明端点已激活）。

### 步骤 11: 更新 Harbor Webhook 配置（手动）

**在 Harbor Web UI 中操作**:

1. 登录 Harbor → 项目 `sisys` → Webhook
2. 编辑 `argocd-image-updater` Webhook
3. 修改以下字段:

| 字段 | 值 |
|------|-----|
| URL | `http://argocd-image-updater.argocd.svc.cluster.local:8080/webhook?type=harbor` |
| Secret/Token | （步骤 2 中生成的 `$WEBHOOK_SECRET`） |
| 事件类型 | `Push Artifact` ✅ |
| 跳过证书验证 | ✅ |

4. 保存并使用"测试"按钮发送测试请求

### 步骤 12: 验证端到端 Webhook

```bash
# 推送一个测试镜像
docker pull harbor.sisys.local/sisys/app:dev-v1.0.0-test-webhook
docker tag harbor.sisys.local/sisys/app:dev-v1.0.0-4529fa4 harbor.sisys.local/sisys/app:dev-v1.0.0-test-webhook
docker push harbor.sisys.local/sisys/app:dev-v1.0.0-test-webhook

# 观察 Image Updater 日志（应在几秒内收到 Webhook 事件）
kubectl logs -n argocd deployment/argocd-image-updater -f | grep -i webhook
```

**预期输出**:
```
level=info msg="Received webhook event from Harbor"
level=info msg="Processing image update from webhook..."
```

---

## 🔄 回滚预案（如有问题）

### 方式 A: 一键回滚（推荐）

```bash
kubectl rollout undo deployment/argocd-image-updater -n argocd
```

### 方式 B: 恢复旧 YAML

```bash
# 恢复 image 版本为 v0.14.0
# 移除 --enable-webhook 参数
# 重新应用
kubectl apply -f /mnt/g/ai/sisys/deployments/argocd/image-updater-install.yaml
kubectl rollout restart deployment/argocd-image-updater -n argocd
```

### 方式 C: 恢复应用配置

```bash
# 如果策略名修改有问题，恢复为 v0.14 时的原始值
# git checkout -- deployments/argocd/applications/sisys-app-dev.yaml
# git checkout -- deployments/argocd/applications/sisys-app-test.yaml
# kubectl apply -f deployments/argocd/applications/sisys-app-dev.yaml
# kubectl apply -f deployments/argocd/applications/sisys-app-test.yaml
```

---

## ✅ 升级成功标准

| 检查项 | 通过标准 |
|--------|---------|
| Pod 版本 | `v0.18.0` |
| 启动参数 | 包含 `--enable-webhook` |
| Secret 配置 | 包含 `webhook.harbor-secret` |
| dev/test 策略 | `newest-build` 按构建时间排序 |
| Webhook 端点 | `/webhook?type=harbor` 不再返回 404 |
| Harbor Webhook | URL 和 Secret 已更新 |
| 无错误日志 | `kubectl logs` 无 `ERROR` 级别 |
| 现有更新周期正常 | 2 分钟轮询继续工作 |
| Webhook 触发正常 | 推送镜像后几秒内收到事件 |

---

## 📊 版本对照表

| 特性 | v0.14.0 | v0.18.0 |
|------|---------|---------|
| 更新策略 `newest-build` | 当作 `name`(字母序) | ✅ 按构建时间排序 |
| 更新策略 `latest` | ✅ 正常 | ⚠️ 废弃报警 |
| 更新策略 `semver` | ✅ 正常 | ✅ 正常 |
| 更新策略 `digest` | ✅ 正常 | ✅ 正常 |
| Webhook 支持 | ❌ 不支持 | ✅ 支持（`--enable-webhook`） |
| Webhook Secret | 无此概念 | **必须配置 `webhook.harbor-secret`** |
| Webhook 端点 | 无 | **`/webhook?type=harbor`** |
| ArgoCD 兼容 | v2.14.x | v3.1.7+ |
| `registries.conf` `ping` 字段 | ✅ 有效 | ⚠️ 被忽略 |
| 配置方式 | Annotation | Annotation（v1.x 改为 CRD） |
| Harbor 支持 | ✅ 支持 | ✅ 支持（含 Webhook Secret） |

---

## 📝 相关文档

- [ArgoCD Image Updater 官方文档 v0.18](https://argocd-image-updater.readthedocs.io/en/release-0.18/)
- [更新策略文档](https://argocd-image-updater.readthedocs.io/en/release-0.18/basics/update-strategies/)
- [Webhook 配置文档](https://argocd-image-updater.readthedocs.io/en/release-0.18/configuration/webhook/)
- [Registry 配置文档](https://argocd-image-updater.readthedocs.io/en/release-0.18/configuration/registries/)
- [GitHub Release v0.18.0](https://github.com/argoproj-labs/argocd-image-updater/releases/tag/v0.18.0)

---

## 📝 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-04-05 | 初始版本 | AI Code Reviewer |
| 2026-04-05 | 补充 Webhook Secret 配置、修正端点路径 | AI Code Reviewer |
