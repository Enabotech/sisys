# 📜 预提交 Hooks 快速入门

## 5 分钟快速设置

### 步骤 1: 安装 pre-commit

```bash
# 使用 poetry（推荐）
poetry add --group dev pre-commit

# 或使用 pip
pip install pre-commit
```

### 步骤 2: 安装 git hooks

```bash
# 在项目根目录执行
make hooks-install

# 或直接使用 pre-commit 命令
pre-commit install
```

### 步骤 3: 验证安装

```bash
# 运行完整检查（所有文件）
make hooks-run

# 或直接使用 pre-commit 命令
pre-commit run --all-files
```

---

## 🎯 宪法原则

**每次 git commit 必须自动执行：检查→修改→通过循环**

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

## 📚 详细文档

- [PRE_COMMIT_HOOKS.md](PRE_COMMIT_HOOKS.md) - 完整使用指南
- [.pre-commit-config.yaml](../../.pre-commit-config.yaml) - 配置文件

---

## ✅ 检查清单

设置完成后，确认：

- [ ] pre-commit 已安装
- [ ] git hooks 已安装（`make hooks-install`）
- [ ] 完整检查通过（`make hooks-run`）
- [ ] 理解提交流程和宪法原则
- [ ] 知道如何修复常见问题

---

**🎉 恭喜！您已成功设置预提交 Hooks，开始高质量的代码之旅！**
