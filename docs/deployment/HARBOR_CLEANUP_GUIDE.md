# Harbor 项目垃圾文件清理清单

**审查日期:** 2026-03-17
**审查者:** Qwen Code (AI 高级开发者)
**审查范围:** Harbor 相关实现与部署文件

---

## 📋 清理清单总览

| 类别 | 文件/目录 | 清理建议 | 风险等级 |
|------|----------|----------|----------|
| 废弃配置 | `deployments/harbor/ingress.yaml` | ⚠️ 谨慎清理 | 中 |
| 废弃脚本 | `scripts/deployment/harbor/harbor-ingress-apply.service` | ✅ 可清理 | 低 |
| 废弃脚本 | `scripts/deployment/harbor/apply-ingress.sh` | ✅ 可清理 | 低 |
| 废弃脚本 | `scripts/deployment/harbor/fix-wsl-reboot.sh` | ✅ 可清理 | 低 |
| 临时文件 | `deployments/harbor/robot$robot_test_deployment.json` | ✅ 可清理 | 低 |
| 测试缓存 | `tests/deployment/__pycache__/` | ✅ 可清理 | 无 |
| MyPy 缓存 | `.mypy_cache/3.11/tests/deployment/test_harbor*` | ✅ 可清理 | 无 |
| 旧文档 | `docs/deployment/HARBOR_INGRESS_AUTO_APPLY.md` | ⚠️ 谨慎清理 | 中 |
| 旧文档 | `docs/deployment/HARBOR_PASSWORD_MANAGEMENT.md` | ⚠️ 谨慎清理 | 中 |

---

## 🔴 高风险 - 不建议清理

### 1. 保留文件（正在使用）

以下文件**不应清理**，因为它们正在被使用或有历史参考价值：

| 文件 | 原因 |
|------|------|
| `deployments/harbor/ingress.yaml` | 虽然已废弃，但包含历史配置参考，建议保留但添加废弃说明 |
| `docs/deployment/HARBOR_COSIGN_SIGNING.md` | 完整的 Cosign 使用指南，仍有参考价值 |
| `docs/deployment/HARBOR_ROBOT_ACCOUNT.md` | Robot Account 配置指南，仍有参考价值 |
| `docs/deployment/HARBOR_WEBHOOK_SETUP.md` | Webhook 配置指南，仍有参考价值 |
| `docs/deployment/HARBOR_PERSISTENCE.md` | 持久化说明文档，最新有效 |

---

## 🟡 中风险 - 可清理但需确认

### 1. `deployments/harbor/ingress.yaml`

**状态:** 已废弃（被 `ingress-route.yaml` 替代）

**清理建议:**
```bash
# 方案 A: 添加废弃说明（推荐）
cat >> deployments/harbor/ingress.yaml <<'EOF'

# =============================================================================
# ⚠️ 已废弃
# =============================================================================
# 此文件已被 ingress-route.yaml 替代
# 保留此文件仅供历史参考，不应再使用
# 废弃日期：2026-03-17
# =============================================================================
EOF

# 方案 B: 完全删除（确认不再需要后）
rm deployments/harbor/ingress.yaml
```

**影响:** 无（已不再使用）

---

### 2. `docs/deployment/HARBOR_INGRESS_AUTO_APPLY.md`

**状态:** 过时（已被 `HARBOR_PERSISTENCE.md` 替代）

**内容:** Harbor Ingress 自动应用指南（旧方案）

**清理建议:**
```bash
# 方案 A: 移动到归档目录
mkdir -p docs/deployment/.archive
mv docs/deployment/HARBOR_INGRESS_AUTO_APPLY.md docs/deployment/.archive/

# 方案 B: 删除
rm docs/deployment/HARBOR_INGRESS_AUTO_APPLY.md
```

**影响:** 无（已有更新的持久化文档）

---

### 3. `docs/deployment/HARBOR_PASSWORD_MANAGEMENT.md`

**状态:** 部分过时（密码管理已自动化）

**内容:** Harbor 密码管理指南

**清理建议:**
```bash
# 方案 A: 更新文档（推荐）
# 添加新的自动化密码管理说明

# 方案 B: 移动到归档目录
mkdir -p docs/deployment/.archive
mv docs/deployment/HARBOR_PASSWORD_MANAGEMENT.md docs/deployment/.archive/
```

**影响:** 无（已有自动化脚本）

---

## 🟢 低风险 - 建议清理

### 1. `scripts/deployment/harbor/harbor-ingress-apply.service`

**状态:** 已废弃（被 `harbor-autofix.service` 替代）

**文件大小:** 774 bytes

**清理命令:**
```bash
sudo systemctl stop harbor-ingress-apply.service 2>/dev/null || true
sudo systemctl disable harbor-ingress-apply.service 2>/dev/null || true
sudo rm /etc/systemd/system/harbor-ingress-apply.service 2>/dev/null || true
rm scripts/deployment/harbor/harbor-ingress-apply.service
sudo systemctl daemon-reload
```

**影响:** 无（已被更好的自动化方案替代）

---

### 2. `scripts/deployment/harbor/apply-ingress.sh`

**状态:** 已废弃（被 `harbor-autofix.sh` 替代）

**文件大小:** 2055 bytes

**清理命令:**
```bash
rm scripts/deployment/harbor/apply-ingress.sh
```

**影响:** 无（已被更好的自动化方案替代）

---

### 3. `scripts/deployment/harbor/fix-wsl-reboot.sh`

**状态:** 已废弃（被 `harbor-autofix.sh` 替代）

**文件大小:** 4800 bytes

**清理命令:**
```bash
rm scripts/deployment/harbor/fix-wsl-reboot.sh
```

**影响:** 无（已被更好的自动化方案替代）

---

### 4. `deployments/harbor/robot$robot_test_deployment.json`

**状态:** 临时测试文件

**文件大小:** 1368 bytes

**清理命令:**
```bash
rm 'deployments/harbor/robot$robot_test_deployment.json'
```

**影响:** 无（测试临时文件）

---

## 🟣 无风险 - 安全清理

### 1. Python 测试缓存

**目录:** `tests/deployment/__pycache__/`

**文件:**
- `test_harbor.cpython-311-pytest-8.4.2.pyc`
- `test_harbor_architecture.cpython-311-pytest-8.4.2.pyc`
- `test_argocd_harbor_integration.cpython-311-pytest-8.4.2.pyc`
- `test_harbor_image_push.cpython-311-pytest-8.4.2.pyc`

**清理命令:**
```bash
rm -rf tests/deployment/__pycache__/
```

**影响:** 无（测试运行时会自动重新生成）

---

### 2. MyPy 类型检查缓存

**目录:** `.mypy_cache/3.11/tests/deployment/`

**文件:**
- `test_harbor.data.json` (32761 bytes)
- `test_harbor.meta.json` (2643 bytes)
- `test_harbor_architecture.data.json` (23368 bytes)
- `test_harbor_architecture.meta.json` (2096 bytes)
- `test_argocd_harbor_integration.data.json` (33945 bytes)
- `test_argocd_harbor_integration.meta.json` (2261 bytes)

**清理命令:**
```bash
rm -rf .mypy_cache/3.11/tests/deployment/test_harbor*
rm -rf .mypy_cache/3.11/tests/deployment/test_argocd_harbor_integration*
```

**影响:** 无（类型检查运行时会自动重新生成）

---

## 📊 清理总结

### 可立即清理（无风险）

```bash
# 1. Python 缓存
rm -rf tests/deployment/__pycache__/

# 2. MyPy 缓存
rm -rf .mypy_cache/3.11/tests/deployment/test_harbor*
rm -rf .mypy_cache/3.11/tests/deployment/test_argocd_harbor_integration*

# 3. 临时测试文件
rm 'deployments/harbor/robot$robot_test_deployment.json'
```

**预计释放空间:** ~100 KB

---

### 建议清理（低风险）

```bash
# 1. 废弃的脚本文件
sudo systemctl stop harbor-ingress-apply.service 2>/dev/null || true
sudo systemctl disable harbor-ingress-apply.service 2>/dev/null || true
sudo rm /etc/systemd/system/harbor-ingress-apply.service 2>/dev/null || true
rm scripts/deployment/harbor/harbor-ingress-apply.service
rm scripts/deployment/harbor/apply-ingress.sh
rm scripts/deployment/harbor/fix-wsl-reboot.sh
sudo systemctl daemon-reload
```

**预计释放空间:** ~8 KB

---

### 谨慎清理（中风险）

```bash
# 1. 归档旧文档（不删除，移动到归档目录）
mkdir -p docs/deployment/.archive
mv docs/deployment/HARBOR_INGRESS_AUTO_APPLY.md docs/deployment/.archive/
mv docs/deployment/HARBOR_PASSWORD_MANAGEMENT.md docs/deployment/.archive/

# 2. 添加废弃说明到 ingress.yaml
cat >> deployments/harbor/ingress.yaml <<'EOF'

# =============================================================================
# ⚠️ 已废弃 (Deprecated)
# =============================================================================
# 此文件已被 ingress-route.yaml 替代
# 保留此文件仅供历史参考，不应再使用
# 废弃日期：2026-03-17
# =============================================================================
EOF
```

**预计释放空间:** ~12 KB（如果删除旧文档）

---

## 🚀 一键清理脚本

如需一键清理所有安全文件，可运行：

```bash
#!/bin/bash
# Harbor 垃圾文件清理脚本
# 使用方式：./cleanup-harbor.sh

set -euo pipefail

echo "=========================================="
echo "Harbor 垃圾文件清理"
echo "=========================================="
echo ""

# 1. Python 缓存
echo "🗑️  清理 Python 测试缓存..."
rm -rf tests/deployment/__pycache__/

# 2. MyPy 缓存
echo "🗑️  清理 MyPy 类型检查缓存..."
rm -rf .mypy_cache/3.11/tests/deployment/test_harbor*
rm -rf .mypy_cache/3.11/tests/deployment/test_argocd_harbor_integration*

# 3. 临时文件
echo "🗑️  清理临时测试文件..."
rm -f 'deployments/harbor/robot$robot_test_deployment.json'

# 4. 废弃脚本（可选）
echo "🗑️  清理废弃脚本..."
sudo systemctl stop harbor-ingress-apply.service 2>/dev/null || true
sudo systemctl disable harbor-ingress-apply.service 2>/dev/null || true
sudo rm /etc/systemd/system/harbor-ingress-apply.service 2>/dev/null || true
rm -f scripts/deployment/harbor/harbor-ingress-apply.service
rm -f scripts/deployment/harbor/apply-ingress.sh
rm -f scripts/deployment/harbor/fix-wsl-reboot.sh
sudo systemctl daemon-reload

# 5. 归档旧文档（可选）
echo "📁 归档旧文档..."
mkdir -p docs/deployment/.archive
mv -f docs/deployment/HARBOR_INGRESS_AUTO_APPLY.md docs/deployment/.archive/ 2>/dev/null || true
mv -f docs/deployment/HARBOR_PASSWORD_MANAGEMENT.md docs/deployment/.archive/ 2>/dev/null || true

echo ""
echo "✅ 清理完成！"
echo ""
echo "📊 清理统计:"
echo "   - Python 缓存：已清理"
echo "   - MyPy 缓存：已清理"
echo "   - 临时文件：已清理"
echo "   - 废弃脚本：已清理"
echo "   - 旧文档：已归档"
echo ""
echo "⚠️  注意：ingress.yaml 已保留（添加废弃说明）"
```

---

## ⚠️ 清理前确认清单

在执行清理前，请确认：

- [ ] Harbor 部署正常运行（8/8 Pods Running）
- [ ] API 访问正常（`curl -k https://172.21.110.12:31448/api/v2.0/ping` 返回 "Pong"）
- [ ] Web 界面可访问（`https://harbor.sisys.local:31448/harbor`）
- [ ] 已备份重要配置文件（Git 已提交）
- [ ] 已安装自动化修复服务（`harbor-autofix.service`）

---

## 📞 清理后验证

清理完成后，运行以下命令验证 Harbor 仍正常工作：

```bash
# 1. 验证 API 访问
curl -k -s "https://172.21.110.12:31448/api/v2.0/ping" -H "Host: harbor.sisys.local"
# 期望输出：Pong

# 2. 验证 Web 访问
curl -k -s "https://172.21.110.12:31448/harbor" -H "Host: harbor.sisys.local" | grep -o "<title>.*</title>"
# 期望输出：<title>Harbor</title>

# 3. 验证 Pods 状态
sudo kubectl get pods -n harbor
# 期望输出：8/8 Running

# 4. 运行测试
poetry run pytest tests/deployment/test_harbor.py tests/deployment/test_harbor_architecture.py -v
# 期望输出：32 passed, 8 skipped
```

---

**审查完成时间:** 2026-03-17
**下次审查建议:** 每次 Harbor 重大更新后
