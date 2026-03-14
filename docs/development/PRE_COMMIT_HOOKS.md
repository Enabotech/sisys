# 📜 预提交 Hooks 使用指南

## 项目宪法

**每次代码 git 提交必须使用预提交 hooks 执行检查→修改→通过循环**

这是项目的强制性要求，所有代码提交都必须经过自动化检查流程。

---

## 🎯 宪法原则

1. **检查 (Check)** → 运行所有 hooks 检查代码问题
2. **修改 (Fix)** → 自动修复可修复的问题（格式化、导入排序等）
3. **通过 (Pass)** → 所有检查通过后才能提交

### 核心原则

- ✅ **不允许绕过 hooks**（除非紧急情况使用 `--no-verify`）
- ✅ **自动修复优先**（能自动修复的问题不阻塞提交）
- ✅ **快速反馈**（失败时立即显示详细错误信息）

---

## 📦 安装步骤

### 1. 安装 pre-commit

```bash
# 使用 pip
pip install pre-commit

# 或使用 poetry（推荐）
poetry add --group dev pre-commit
```

### 2. 安装 git hooks

```bash
# 在项目根目录执行
pre-commit install
```

这会安装 git commit hook，每次提交时自动运行检查。

### 3. 验证安装

```bash
# 运行所有文件的完整检查
pre-commit run --all-files
```

---

## 🔄 工作流程

### 本地提交流程

```
git add <files>
    ↓
git commit
    ↓
┌─────────────────────────────────────┐
│   预提交 hooks 自动运行（仅检查暂存文件）   │
│                                     │
│   1. 代码格式化 (Ruff Format)        │
│   2. 代码检查 (Ruff Lint + Auto-fix) │
│   3. 类型检查 (MyPy)                 │
│   4. 安全扫描 (Bandit)               │
│   5. 密钥检测 (Detect Secrets)       │
│   6. 基础检查 (YAML/JSON/大文件等)    │
└─────────────────────────────────────┘
    ↓
    ├─ ✅ 所有检查通过 → 提交成功
    │
    └─ ❌ 有检查失败 → 提交被阻止
           ↓
           根据错误信息修复代码
           ↓
           重新 git add + git commit
```

### CI/CD 推送流程

```
git push
    ↓
┌─────────────────────────────────────┐
│   GitHub Actions / CI/CD 完整检查      │
│                                     │
│   运行所有 hooks（检查全部文件）        │
│   + 运行完整测试套件                 │
│   + 运行 BDD 验收测试                 │
│   + 验证领域事件 Schema              │
│   + 验证 OpenAPI 规范                │
└─────────────────────────────────────┘
```

---

## 🛠️ Hooks 详解

### 1. 基础检查 (pre-commit-hooks)

```yaml
- trailing-whitespace      # 删除行尾空格
- end-of-file-fixer        # 确保文件以换行符结尾
- check-yaml              # 验证 YAML 语法
- check-json              # 验证 JSON 语法
- check-added-large-files  # 检查大文件（>1MB）
- check-merge-conflict    # 检查合并冲突标记
- detect-private-key      # 检测私钥
- check-case-conflict     # 检查大小写冲突
```

### 2. 代码质量 (Ruff) - 自动修复

```yaml
- ruff                    # 代码检查 + 自动修复
- ruff-format            # 代码格式化
```

**自动修复内容：**
- 导入排序（isort）
- 代码风格（PEP 8）
- 常见错误修复
- 未使用代码删除

### 3. 类型检查 (MyPy) - 强制

```yaml
- mypy                   # 类型注解检查
```

**检查内容：**
- 类型注解完整性
- 类型兼容性
- 返回值类型
- 参数类型

### 4. 安全扫描 (Bandit) - 强制

```yaml
- bandit                 # 安全漏洞扫描
```

**检测内容：**
- SQL 注入
- 命令注入
- 硬编码密码
- 不安全的加密算法
- 其他常见安全漏洞

### 5. 密钥检测 (Detect Secrets) - 强制

```yaml
- detect-secrets         # 检测密钥泄露
```

**检测内容：**
- API 密钥
- 数据库密码
- AWS 凭证
- 私钥
- 其他敏感信息

### 6. SDD 工具链验证（Story 0.1）- 推送时运行

```yaml
- validate-schemas       # 验证领域事件 Schema
- validate-openapi       # 验证 OpenAPI 规范
- pytest-bdd            # 运行 BDD 验收测试
```

---

## 💡 使用技巧

### 查看 hooks 状态

```bash
# 查看已安装的 hooks
pre-commit sample-config

# 查看 hooks 版本
pre-commit autoupdate --dry-run
```

### 手动运行检查

```bash
# 运行所有文件的检查
pre-commit run --all-files

# 仅运行特定 hook
pre-commit run ruff --all-files
pre-commit run mypy --all-files
```

### 更新 hooks

```bash
# 更新所有 hooks 到最新版本
pre-commit autoupdate
```

### 临时跳过 hooks（紧急情况）

```bash
# ⚠️ 仅在紧急情况下使用
git commit --no-verify -m "紧急修复"
```

**注意：** 这会绕过所有检查，应在事后尽快补上检查。

### 修复典型问题

#### 问题 1: Ruff 格式化失败

```bash
# 手动运行 Ruff 修复
poetry run ruff check --fix .
poetry run ruff format .
```

#### 问题 2: MyPy 类型检查失败

```bash
# 查看具体类型错误
poetry run mypy src/

# 添加缺失的类型注解
# 例如：def greet(name: str) -> str:
```

#### 问题 3: Bandit 安全警告

```bash
# 查看详细安全报告
poetry run bandit -r src/ -f html -o bandit-report.html
```

#### 问题 4: 检测到密钥

```bash
# 1. 立即撤销泄露的密钥
# 2. 从 git 历史中删除密钥
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/secret/file" \
  --prune-empty --tag-name-filter cat -- --all
# 3. 强制推送
git push --force
```

---

## 🚨 常见问题

### Q1: 为什么我的提交被阻止了？

**A:** 预提交 hooks 检测到代码问题。查看终端输出的错误信息，根据提示修复代码。

### Q2: 如何跳过某个 hook？

**A:** 不建议跳过。如确有需要，在 `.pre-commit-config.yaml` 中设置 `stages: [manual]`。

### Q3: hooks 运行太慢怎么办？

**A:**
- 本地提交仅检查暂存文件（快速）
- 完整检查在 CI/CD 推送时运行
- 可考虑将 MyPy 等慢速检查设为 `stages: [push]`

### Q4: 如何调试 hook 失败？

**A:**
```bash
# 运行详细输出
pre-commit run --verbose --all-files

# 仅运行特定 hook
pre-commit run <hook-id> --verbose
```

---

## 📋 检查清单

每次提交前，确保：

- [ ] 已安装 pre-commit 和 git hooks
- [ ] 代码已通过所有本地 hooks 检查
- [ ] 没有密钥/敏感信息提交
- [ ] 类型注解完整（新代码）
- [ ] 代码格式化符合规范
- [ ] 安全扫描无高危问题

---

## 🔗 相关文档

- [pre-commit 官方文档](https://pre-commit.com)
- [Ruff 文档](https://docs.astral.sh/ruff/)
- [MyPy 文档](https://mypy.readthedocs.io/)
- [Bandit 文档](https://bandit.readthedocs.io/)
- [detect-secrets 文档](https://github.com/Yelp/detect-secrets)

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-13 | 初始版本，强制执行检查→修改→通过循环 |

---

**📜 宪法宣誓：** 每一次提交都是对代码质量的承诺！
