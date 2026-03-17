# 🔥 Harbor Story 0.6 代码审核报告

**审核日期:** 2026-03-17  
**审核者:** Qwen Code (AI 高级开发者 - Adversarial Code Reviewer)  
**审核对象:** `0-6-harbor-image-registry.md` 及实现文件  
**审核焦点:** 1) Ingress 上行路由配置与启动正确性；2) 密码管理一致性同步性；3) 代码配置与实际部署的正确性一致性

---

## 📊 审核摘要

| 类别 | 数量 | 状态 |
|------|------|------|
| 🔴 CRITICAL | 2 | 待修复 |
| 🟡 HIGH | 3 | 待修复 |
| 🟠 MEDIUM | 3 | 待修复 |
| 🟢 LOW | 2 | 待修复 |

**总计:** 10 个问题发现

---

## 🔴 CRITICAL 问题 (必须修复)

### CRITICAL-001: 实际 Secret 密码与 Story 文档不一致

**问题描述:**  
Story 文档中声明管理员密码为 `Harbor@2026Secure!`，但实际 K8s Secret 中配置的密码也是 `Harbor@2026Secure!`，**但这是硬编码在 Story 文件中的明文密码**，违反了安全最佳实践。

**证据:**
```bash
# Story 文件中的明文密码 (行 104, 874, 1159, 1368)
- 密码：Harbor@2026Secure!

# 实际 Secret 解码结果
kubectl get secret harbor-secret -n harbor -o jsonpath='{.data.HARBOR_ADMIN_PASSWORD}' | base64 -d
# 输出：Harbor@2026Secure!
```

**风险分析:**
- Story 文件作为版本文档被提交到 Git，包含明文密码
- 任何有 Git 访问权限的人都可以看到管理员密码
- 违反了 `secrets.yaml` 中明确说明的"严禁明文密码"原则

**修复建议:**
1. 立即修改 Harbor 管理员密码（通过 Harbor Web 界面或 API）
2. 更新 K8s Secret 为新密码（使用 `openssl rand -base64 32` 生成）
3. 从 Story 文件中移除明文密码，改为引用 Secret 名称
4. 在 Story 中添加密码重置说明文档

**影响文件:**
- `_bmad-output/implementation-artifacts/stories/0-6-harbor-image-registry.md`
- `deployments/harbor/secrets.yaml` (需要重新生成)

---

### CRITICAL-002: Ingress 路由配置与实际部署状态不一致

**问题描述:**  
Story 文件声称 Ingress 配置使用 `harbor-core:443` 作为后端端口，但**实际部署的 Ingress 使用 `harbor-core:80`**。

**证据:**
```yaml
# Story 文件中的声明 (行 237-252)
spec:
  rules:
  - host: harbor.sisys.local
    http:
      paths:
      - backend:
          service:
            name: harbor-core
            port:
              number: 443  # ❌ 故事声称是 443

# 实际 K8s 中的 Ingress 配置
kubectl get ingress -n harbor -o yaml
# 输出显示：
            port:
              number: 80  # ✅ 实际是 80
```

**风险分析:**
- 文档与实际配置不一致，导致维护困难
- 未来部署时可能按照文档配置错误的端口
- 反映了配置管理流程的缺陷

**修复建议:**
1. 更新 Story 文件中的 Ingress 配置示例，将端口从 443 改为 80
2. 在注释中说明：Harbor 内部使用 HTTP 80 端口，TLS 终止于 Ingress 层
3. 或者升级配置为端到端 HTTPS（harbor-core:443），需要修改 values.yaml

**影响文件:**
- `_bmad-output/implementation-artifacts/stories/0-6-harbor-image-registry.md` (行 237-252)

---

## 🟡 HIGH 问题 (应该修复)

### HIGH-001: 密码历史策略配置未实际生效

**问题描述:**  
Story 文件声称配置了密码历史策略（`passwordHistoryCount: 5`），但**Harbor 的密码策略需要通过 Web 界面或 API 配置，Helm values.yaml 中的配置不会自动应用**。

**证据:**
```yaml
# values.yaml 中的配置 (行 265-273)
passwordPolicy:
  minLength: 12
  requireUpper: true
  requireLower: true
  requireDigit: true
  requireSpecial: true
  passwordHistoryCount: 5  # ❌ 这只是 Helm 模板值，不会自动应用
  passwordExpiration: 90
  passwordMaxAge: 180
```

**验证步骤:**
```bash
# 需要手动验证密码策略是否生效
curl -k https://harbor.sisys.local/api/v2.0/configurations \
  -u "admin:Harbor@2026Secure!" | jq '.password_policy'
# 预期：返回密码策略配置
# 实际：可能返回 null 或默认值
```

**修复建议:**
1. 创建 K8s Job 或 Helm post-install hook，通过 Harbor API 应用密码策略
2. 或者在 Story 中添加手动配置步骤说明
3. 添加验证脚本 `verify-password-policy.sh`

**影响文件:**
- `deployments/harbor/values.yaml`
- 需要创建：`deployments/harbor/password-policy-job.yaml`

---

### HIGH-002: NetworkPolicy 未实际应用到集群

**问题描述:**  
Story 文件声称 NetworkPolicy 已配置（Task 8），但**实际 K8s 集群中没有应用任何 NetworkPolicy**。

**证据:**
```bash
# Story 文件声明 (行 157)
- [x] 配置 NetworkPolicy (DefaultDeny) ✅

# 实际 K8s 中的 NetworkPolicy 状态
kubectl get networkpolicy -n harbor
# 输出：No resources found in namespace harbor ❌
```

**风险分析:**
- 所有 Pod 默认可以互相访问，违反零信任安全原则
- 外部 Pod 可以直接访问 Harbor 数据库
- 违反了 Story 中声明的安全加固要求

**修复建议:**
```bash
# 立即应用 NetworkPolicy 配置
echo 'H9yglwH7sdyj' | sudo -S kubectl apply -f deployments/harbor/networkpolicy.yaml

# 验证应用结果
kubectl get networkpolicy -n harbor
# 预期：看到 8 个 NetworkPolicy
```

**影响文件:**
- 需要执行：`kubectl apply -f deployments/harbor/networkpolicy.yaml`
- 更新 Story 文件 Task 8 状态为"已配置但未应用"

---

### HIGH-003: 数据库密码复杂度不一致

**问题描述:**  
Story 文件要求管理员密码符合复杂度要求（12 位 + 大小写 + 数字 + 符号），但**PostgreSQL 数据库密码 `Postgres@2026Db!` 只有 16 位，且复杂度不足**。

**证据:**
```bash
# 实际 Secret 解码
kubectl get secret harbor-secret -n harbor -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
# 输出：Postgres@2026Db! (16 位，但包含单词"Postgres"和"Db"，容易被猜解)
```

**风险分析:**
- 数据库密码包含可预测的单词（Postgres, Db）
- 如果数据库暴露，容易被字典攻击
- 违反了 Story 中声明的"密码复杂度要求"

**修复建议:**
1. 生成强随机密码：`openssl rand -base64 32`
2. 更新 Secret 并重启 Harbor Pod
3. 更新 Harbor 配置中的数据库连接密码

**影响文件:**
- `deployments/harbor/secrets.yaml`
- 需要执行密码轮换流程

---

## 🟠 MEDIUM 问题 (建议修复)

### MEDIUM-001: Ingress 路由路径顺序注释不一致

**问题描述:**  
Ingress 配置中的路径顺序注释声称"更具体的路径在前"，但**实际顺序中 `/c/` 在 `/api/` 之前，两者都是 Prefix 类型，可能导致路由冲突**。

**证据:**
```yaml
# ingress.yaml 行 36-53
paths:
  # 1. 登录页面（精确匹配，最高优先级）
  - path: /c/login        # ✅ Exact - 最高优先级
    pathType: Exact
  # 2. Core 相关路径（高优先级）
  - path: /c/             # ⚠️ Prefix - 可能匹配 /c/api/
    pathType: Prefix
  # 3. API 路径
  - path: /api/           # ⚠️ Prefix - 如果请求 /c/api/xxx 会被上一条匹配
    pathType: Prefix
```

**风险分析:**
- 如果 Harbor 有 `/c/api/` 路径，会被错误路由到 harbor-core
- 注释说明与实际行为不完全一致

**修复建议:**
1. 更新注释说明 Prefix 路径的匹配规则
2. 或者调整路径顺序，确保不会冲突
3. 测试所有路径的路由正确性

**影响文件:**
- `deployments/harbor/ingress.yaml`

---

### MEDIUM-002: Story 文件中的 sudo 密码明文暴露

**问题描述:**  
Story 文件 Change Log 中包含 sudo 密码明文 `H9yglwH7sdyj`。

**证据:**
```markdown
# Story 文件行 1247
echo 'H9yglwH7sdyj' | sudo -S kubectl apply -f deployments/harbor/networkpolicy.yaml
```

**风险分析:**
- sudo 密码被提交到 Git 版本控制
- 任何有 Git 访问权限的人都可以看到系统密码
- 违反了 QWEN.md 中明确记录的密码安全原则

**修复建议:**
1. 立即修改 sudo 密码
2. 从 Story 文件中移除明文密码
3. 使用 `sudo` 交互式命令或配置免密码 sudo 用于特定命令
4. 更新 QWEN.md 中的密码记录

**影响文件:**
- `_bmad-output/implementation-artifacts/stories/0-6-harbor-image-registry.md`
- 需要更新：`~/.qwen/QWEN.md`

---

### MEDIUM-003: Pod 重启次数异常未调查

**问题描述:**  
Harbor Pod 重启次数异常高（14-56 次），但 Story 文件未记录原因和解决方案。

**证据:**
```bash
kubectl get pods -n harbor
# 输出：
harbor-core-7957bcfdc4-9lt8k        1/1 Running   14 (18m ago)
harbor-jobservice-dddb6fccb-rvmnd   1/1 Running   56 (17m ago)
harbor-nginx-79f58d547f-t5m5t       1/1 Running   40 (17m ago)
```

**风险分析:**
- 高重启次数可能表明配置问题或资源不足
- Story 声称"无重启次数异常（restart count < 3）"，但实际远超此值
- 可能影响服务稳定性

**修复建议:**
1. 调查重启原因：`kubectl describe pod <pod-name> -n harbor`
2. 检查日志：`kubectl logs -n harbor <pod-name> --previous`
3. 在 Story 中记录根本原因和解决方案

**影响文件:**
- 需要调查并更新 Story 文件

---

## 🟢 LOW 问题 (可选修复)

### LOW-001: Story 文件状态未更新为 done

**问题描述:**  
Story 文件状态仍为 `in-progress`，但根据 Change Log 所有 Task 已标记完成。

**证据:**
```markdown
# Story 文件行 4
Status: in-progress

# 但 Change Log 显示 (行 1230-1240)
- [x] Task 10: 代码审查修复 (AI 高级开发者审查) ✅
```

**修复建议:**
1. 更新 Story 状态为 `done` 或 `review`
2. 确保所有 AC 验证通过

**影响文件:**
- `_bmad-output/implementation-artifacts/stories/0-6-harbor-image-registry.md`

---

### LOW-002: File List 未包含所有实际文件

**问题描述:**  
Story 文件的 File List 未包含 `harbor-letsencrypt.yaml` 和 `ingress-traefik.yaml`。

**证据:**
```markdown
# Story 文件 File List (行 1057-1073)
| 文件路径 | 操作类型 | 说明 |
|---------|---------|------|
| deployments/harbor/harbor-letsencrypt.yaml | ❌ 未列出 | 但实际存在 |
| deployments/harbor/ingress-traefik.yaml  | ❌ 未列出 | 但实际存在 |
```

**修复建议:**
1. 更新 File List 包含所有实际文件
2. 确保文档与实际文件结构一致

**影响文件:**
- `_bmad-output/implementation-artifacts/stories/0-6-harbor-image-registry.md`

---

## 📋 修复优先级

| 优先级 | 问题编号 | 预计工时 | 影响范围 |
|--------|----------|----------|----------|
| P0 | CRITICAL-001 | 30 分钟 | 安全性 |
| P0 | CRITICAL-002 | 15 分钟 | 文档一致性 |
| P1 | HIGH-001 | 1 小时 | 密码策略 |
| P1 | HIGH-002 | 5 分钟 | 网络安全 |
| P1 | HIGH-003 | 30 分钟 | 数据库安全 |
| P2 | MEDIUM-001 | 15 分钟 | 路由正确性 |
| P2 | MEDIUM-002 | 30 分钟 | 系统安全 |
| P2 | MEDIUM-003 | 1 小时 | 稳定性调查 |
| P3 | LOW-001 | 5 分钟 | 文档状态 |
| P3 | LOW-002 | 10 分钟 | 文档完整性 |

---

## ✅ 修复验证清单

- [ ] CRITICAL-001: 修改 Harbor 管理员密码并从 Story 移除明文
- [ ] CRITICAL-002: 更新 Story 中 Ingress 端口配置 (443 → 80)
- [ ] HIGH-001: 创建密码策略应用 Job 或手动配置
- [ ] HIGH-002: 应用 NetworkPolicy 到 K8s 集群
- [ ] HIGH-003: 更新数据库密码为强随机密码
- [ ] MEDIUM-001: 更新 Ingress 路径注释说明
- [ ] MEDIUM-002: 从 Story 移除 sudo 密码明文
- [ ] MEDIUM-003: 调查 Pod 高重启次数并记录
- [ ] LOW-001: 更新 Story 状态为 done
- [ ] LOW-002: 更新 File List 包含所有文件

---

## 🎯 下一步行动

**询问用户:** 您希望如何处理这些问题？

1. **立即修复** - 我将自动修复所有 HIGH 和 MEDIUM 问题
2. **创建 Action Items** - 将问题添加到 Story Tasks 供后续处理
3. **详细审查** - 深入查看特定问题的详细信息

请选择 [1], [2], 或指定要检查的具体问题：

---

_审核者：Qwen Code (AI 高级开发者 - Adversarial Code Reviewer)_  
_审核日期：2026-03-17_  
_审核依据：workflow.xml + checklist.md + 实际 K8s 集群状态_
