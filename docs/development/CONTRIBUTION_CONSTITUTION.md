# 📜 项目宪法：预提交 Hooks 强制执行规范

## 宪法条文

**第一条【强制执行】** 每次代码 git 提交必须使用预提交 hooks 执行检查→修改→通过循环。

**第二条【自动循环】** 预提交 hooks 自动执行以下流程：
1. **检查（Check）** - 运行所有 hooks 检查代码问题
2. **修改（Fix）** - 自动修复可修复的问题（格式化、导入排序等）
3. **通过（Pass）** - 所有检查通过后才能提交

**第三条【不可绕过】** 不允许绕过 hooks（除非紧急情况使用 `--no-verify`，事后须补上检查）。

---

## 实施细则

### 第一条【 hooks 配置】

预提交 hooks 配置文件为 `.pre-commit-config.yaml`，包含以下检查层：

#### 1. 基础检查层（pre-commit-hooks）
- 删除行尾空格
- 确保文件以换行符结尾
- 验证 YAML/JSON 语法
- 检查大文件（>1MB）
- 检测合并冲突标记
- 检测私钥
- 检测大小写冲突

#### 2. 代码质量层（Ruff）- 自动修复
- 代码格式化（Ruff Format）
- 代码检查与自动修复（Ruff Lint）
- 导入排序（isort）
- 常见错误修复

#### 3. 类型检查层（MyPy）- 强制
- 类型注解完整性
- 类型兼容性
- 返回值类型
- 参数类型

#### 4. 安全扫描层（Bandit）- 强制
- SQL 注入检测
- 命令注入检测
- 硬编码密码检测
- 不安全的加密算法
- 其他常见安全漏洞

#### 5. 密钥检测层（Detect Secrets）- 强制
- API 密钥
- 数据库密码
- AWS 凭证
- 私钥
- 其他敏感信息

#### 6. SDD 工具链验证层（Story 0.1）- 推送时运行
- 领域事件 Schema 验证
- OpenAPI 规范验证
- BDD 验收测试

---

### 第二条【安装流程】

**步骤 1：安装 pre-commit**
```bash
poetry add --group dev pre-commit
```

**步骤 2：安装 git hooks**
```bash
make hooks-install
# 或
pre-commit install
```

**步骤 3：验证安装**
```bash
make hooks-run
# 或
pre-commit run --all-files
```

---

### 第三条【提交流程】

**正常提交流程：**
```bash
# 1. 暂存文件
git add <files>

# 2. 提交（hooks 自动运行）
git commit -m "feat: 添加新功能"

# 3. hooks 检查结果
#    - ✅ 通过 → 提交成功
#    - ❌ 失败 → 提交被阻止，根据错误修复后重新提交
```

**紧急绕过（事后须补检）：**
```bash
git commit --no-verify -m "紧急修复"
# 事后立即运行：
make hooks-run
```

---

### 第四条【修复流程】

**代码格式化问题：**
```bash
make format
# 或
poetry run ruff format src/
```

**代码质量问题：**
```bash
poetry run ruff check --fix src/
```

**类型检查问题：**
```bash
make type-check
# 添加缺失的类型注解
```

**安全扫描问题：**
```bash
make security
# 查看详细报告并修复
```

---

### 第五条【Make 命令】

| 命令 | 说明 |
|------|------|
| `make hooks` | 安装预提交 hooks |
| `make hooks-install` | 安装预提交 hooks |
| `make hooks-uninstall` | 卸载预提交 hooks |
| `make hooks-run` | 运行预提交 hooks（所有文件） |
| `make hooks-check` | 检查 hooks 配置 |
| `make hooks-update` | 更新 hooks 到最新版本 |
| `make hooks-validate` | hooks 完整验证 |

---

### 第六条【文档参考】

- [PRE_COMMIT_QUICKSTART.md](PRE_COMMIT_QUICKSTART.md) - 快速入门（5 分钟设置）
- [PRE_COMMIT_HOOKS.md](PRE_COMMIT_HOOKS.md) - 完整使用指南
- [.pre-commit-config.yaml](../../.pre-commit-config.yaml) - 配置文件
- [Makefile](../../Makefile) - 命令入口

---

## 附则

**生效日期：** 2026-03-13

**解释权：** 本项目所有代码提交必须遵守本宪法。

**修订程序：** 经项目维护者同意后修订。

---

**📜 宪法宣誓：** 每一次提交都是对代码质量的承诺！
