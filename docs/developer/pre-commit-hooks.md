# 📜 预提交 Hooks 规范指南

> **项目宪法**：每次代码 git 提交必须使用预提交 hooks 执行**检查→修改→通过**循环

**版本：** 1.0
**最后更新：** 2026-03-13
**状态：** 强制执行

---

## 🎯 宪法原则

### 核心条文

**第一条【强制执行】** 每次代码 git 提交必须使用预提交 hooks 执行检查→修改→通过循环。

**第二条【自动循环】** 预提交 hooks 自动执行：
1. **检查（Check）** - 运行所有 hooks 检查代码问题
2. **修改（Fix）** - 自动修复可修复的问题
3. **通过（Pass）** - 所有检查通过后才能提交

**第三条【不可绕过】** 不允许绕过 hooks（除非紧急情况使用 `--no-verify`，事后须补检）。

### 工作流程

```
git add <files>
    ↓
git commit
    ↓
┌─────────────────────────────────────┐
│   预提交 hooks 自动运行              │
│                                     │
│   ✅ 检查通过 → 提交成功             │
│   ❌ 检查失败 → 提交被阻止           │
└─────────────────────────────────────┘
```

---

## 📦 快速开始

### 5 分钟设置

#### 步骤 1: 安装依赖

```bash
# 使用 poetry（推荐）
poetry add --group dev pre-commit

# 或使用 pip
pip install pre-commit
```

#### 步骤 2: 安装 git hooks

```bash
# 在项目根目录执行
make hooks-install

# 或直接使用 pre-commit 命令
pre-commit install
```

#### 步骤 3: 验证安装

```bash
# 运行完整检查（所有文件）
make hooks-run

# 或直接使用 pre-commit 命令
pre-commit run --all-files
```

---

## 📋 检查项目

### 提交时自动运行（快速检查）

| 检查项 | 工具 | 自动修复 | 说明 |
|--------|------|---------|------|
| **代码格式化** | Ruff Format | ✅ | 统一代码风格 |
| **代码质量** | Ruff Lint | ✅ | 检测常见错误 |
| **类型检查** | MyPy | ❌ | 类型注解验证 |
| **安全扫描** | Bandit | ❌ | 安全漏洞检测 |
| **密钥检测** | Detect Secrets | ❌ | 防止密钥泄露 |
| **基础检查** | pre-commit-hooks | ✅ | YAML/JSON/大文件等 |

### 推送时运行（完整检查）

| 检查项 | 工具 | 说明 |
|--------|------|------|
| **Schema 验证** | validate_schemas.py | 领域事件 Schema 符合性 |
| **OpenAPI 验证** | openapi-spec-validator | OpenAPI 3.1 规范 |
| **BDD 测试** | pytest-bdd | Gherkin 验收测试 |

---

## 🛠️ 安装步骤

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

## 💡 日常使用

### 正常提交流程

```bash
# 1. 暂存文件
git add src/my_file.py

# 2. 提交（hooks 自动运行）
git commit -m "feat: 添加新功能"

# 如果 hooks 失败，根据错误信息修复后重新提交
```

### 手动运行检查

```bash
# 运行所有文件的检查
make hooks-run

# 或单独运行特定检查
make lint          # Ruff 代码检查
make format        # Ruff 格式化
make type-check    # MyPy 类型检查
make security      # 安全扫描
```

### 修复典型问题

#### 代码格式化问题

```bash
# 自动格式化
make format

# 或手动运行
poetry run ruff format src/
```

#### 代码质量问题

```bash
# 自动修复
poetry run ruff check --fix src/

# 查看详细报告
poetry run ruff check src/
```

#### 类型检查问题

```bash
# 运行类型检查
make type-check

# 添加缺失的类型注解
# 例如：def greet(name: str) -> str:
```

---

## 🚨 常见问题

### Q: 提交被阻止怎么办？

**A:** 查看终端输出的错误信息，根据提示修复代码。

**示例输出：**
```
Ruff 代码检查与自动修复......................Failed
- hook id: ruff
- exit code: 1
- files were modified by this hook

src/my_file.py:10:1: F401 [*] `os` imported but unused
```

**修复方法：**
```bash
# 自动修复未使用的导入
poetry run ruff check --fix src/my_file.py

# 重新提交
git add src/my_file.py
git commit -m "fix: 移除未使用的导入"
```

### Q: 如何紧急绕过 hooks？

**A:** 仅在紧急情况下使用 `--no-verify`：

```bash
git commit --no-verify -m "紧急修复"
```

**注意：** 事后应尽快补上检查：
```bash
make hooks-run
```

### Q: hooks 运行太慢？

**A:**
- 本地提交仅检查暂存文件（通常 <5 秒）
- 完整检查在 CI/CD 推送时运行
- 可将慢速检查设为仅推送时运行

---

## ⚡ 性能优化

### 问题描述

**原始问题：** 每次 git 提交时，pre-commit 都要重新初始化并安装环境，耗时 3-5 分钟。

**原因分析：**
1. 使用远程仓库的 hooks（如 `ruff-pre-commit`）需要创建隔离的虚拟环境
2. 虽然提示"will be reused"，但实际使用中经常因为版本更新、缓存清理等原因重新安装
3. 每个 hook 都独立安装环境，累积时间很长

### 优化方案

**核心思路：** 使用本地已安装的工具链，避免重复创建虚拟环境。

### 优化前配置

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.15.6
  hooks:
    - id: ruff
      args: [--fix, --exit-non-zero-on-fix]
```

**问题：** 每次都要从 GitHub 下载并安装到独立环境

### 优化后配置

```yaml
- repo: local
  hooks:
    - id: ruff
      name: "Ruff 代码检查与自动修复"
      entry: poetry run ruff check --fix
      language: system  # ← 关键：使用系统已安装的工具
      types: [python]
```

**优势：** 直接使用 poetry 已安装的 ruff，无需重复安装

### 性能对比

| 阶段 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 首次运行 | 5 分钟 | 44 秒 | **85%** |
| 后续运行 | 不稳定 | 稳定 19 秒 | **稳定** |

---

## 📊 Hooks 详解

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

## 🔧 使用技巧

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
- [.pre-commit-config.yaml](../../.pre-commit-config.yaml) - 项目 hooks 配置文件

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-13 | 初始版本，合并自多个预提交文档，强制执行检查→修改→通过循环 |

---

**📜 宪法宣誓：** 每一次提交都是对代码质量的承诺！
