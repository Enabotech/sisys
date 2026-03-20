# Git Worktree 并行开发快速参考卡片

**版本:** 1.0.0
**日期:** 2026-03-20
**完整指南:** [qwen-git-worktree-parallel-dev-guide.md](./qwen-git-worktree-parallel-dev-guide.md)

---

## 🚀 快速开始

### 1. 一键设置（推荐）

```bash
# 创建单个 Story worktree
./scripts/dev/worktree-setup.sh 1.1

# 创建多个 Story worktrees
./scripts/dev/worktree-setup.sh 1.1 1.2 1.3

# 自定义目录
./scripts/dev/worktree-setup.sh -b ~/dev/worktrees 1.1 1.2
```

### 2. 手动设置

```bash
# 创建 worktree
git worktree add -b story/1.1-hexagonal-architecture \
  ~/dev/sisys-worktrees/story-1.1 main

# 设置虚拟环境
cd ~/dev/sisys-worktrees/story-1.1
python3 -m venv venv
poetry install --with dev,test

# 激活 Qwen Agent
@qwen-agent activate domain_agent_1
```

---

## 📋 常用命令速查

### Git Worktree

| 命令 | 说明 |
|------|------|
| `git worktree add <path> <branch>` | 创建 worktree |
| `git worktree add -b <branch> <path> <base>` | 创建新分支 worktree |
| `git worktree list` | 查看所有 worktrees |
| `git worktree remove <path>` | 删除 worktree |
| `git worktree prune` | 清理无效 worktrees |

### Qwen Agent

| 命令 | 说明 |
|------|------|
| `@qwen-agent` | 激活默认 Agent |
| `@qwen-agent activate <role>` | 激活特定角色 Agent |
| `@qwen-agent list-agents` | 查看可用 Agent |
| `@qwen-agent party-mode --agents=3` | 多 Agent 协作 |

### Makefile (SDD+TDD)

| 命令 | 说明 |
|------|------|
| `make sdd-define` | SDD 规范定义 |
| `make tdd-red TARGET=<path>` | TDD 红阶段（编写失败测试） |
| `make tdd-green TARGET=<path>` | TDD 绿阶段（运行测试） |
| `make tdd-refactor TARGET=<path>` | TDD 重构阶段 |
| `make quality-gates` | 质量门禁检查 |

---

## 🎯 典型工作流

### 场景 1：新 Story 开发

```bash
# 1. 创建 worktree
git worktree add -b story/1.x-feature \
  ~/dev/sisys-worktrees/story-1.x main

# 2. 进入目录
cd ~/dev/sisys-worktrees/story-1.x

# 3. 激活 Qwen
@qwen-agent activate domain_agent_1

# 4. 开始开发循环
make sdd-define
make tdd-red TARGET=domain/entities
# 编写测试...
make tdd-green TARGET=domain/entities
# 实现代码...
make tdd-refactor TARGET=domain/entities

# 5. 提交
git add . && git commit -m "feat: 实现功能 (SDD+TDD)"
```

### 场景 2：多 Story 并行

```bash
# 上午：Story 1.1
cd ~/dev/sisys-worktrees/story-1.1
@qwen-agent activate domain_agent_1
make tdd-red TARGET=domain/entities

# 下午：Story 1.2
cd ~/dev/sisys-worktrees/story-1.2
@qwen-agent activate domain_agent_2
make sdd-define
```

### 场景 3：Bug 修复 + 新功能

```bash
# 新功能开发中...
cd ~/dev/sisys-worktrees/story-1.1

# 收到紧急 bug 报告
git worktree add -b bugfix/critical \
  ~/dev/sisys-worktrees/bugfix-urgent main

cd ~/dev/sisys-worktrees/bugfix-urgent
@qwen-agent activate test_agent_1
# 修复 bug...

# 返回新功能
cd ~/dev/sisys-worktrees/story-1.1
```

---

## 🎭 Qwen Agent 角色选择

| 开发任务 | 推荐 Agent | 激活命令 |
|---------|-----------|---------|
| 领域层开发 | `domain_agent_1` | `@qwen-agent activate domain_agent_1` |
| 领域事件 | `domain_agent_2` | `@qwen-agent activate domain_agent_2` |
| 应用层 | `application_agent_1` | `@qwen-agent activate application_agent_1` |
| 数据库实现 | `infrastructure_agent_1` | `@qwen-agent activate infrastructure_agent_1` |
| 消息队列 | `infrastructure_agent_2` | `@qwen-agent activate infrastructure_agent_2` |
| 测试开发 | `test_agent_1` | `@qwen-agent activate test_agent_1` |
| 代码审查 | `review_agent` | `@qwen-agent activate review_agent` |
| 多 Agent 协作 | `bmad_master_agent` | `@qwen-agent party-mode` |

---

## 🔧 故障排除

### Worktree 已存在

```bash
# 查看
git worktree list

# 删除
git worktree remove ~/dev/sisys-worktrees/story-1.x

# 或强制删除
git worktree remove ~/dev/sisys-worktrees/story-1.x --force
```

### 虚拟环境问题

```bash
# 重新创建
cd ~/dev/sisys-worktrees/story-1.x
rm -rf venv
python3 -m venv venv
poetry install --with dev,test
```

### Qwen 上下文混淆

```bash
# 清除缓存
rm -rf .qwen/cache/

# 重新激活
@qwen-agent deactivate
@qwen-agent activate domain_agent_1
```

---

## 📊 目录结构

```
~/dev/sisys-worktrees/
├── story-1.1/          # Story 1.1 开发
│   ├── venv/           # 独立虚拟环境
│   └── ...
├── story-1.2/          # Story 1.2 开发
│   ├── venv/
│   └── ...
├── bugfix-urgent/      # 紧急 Bug 修复
│   ├── venv/
│   └── ...
└── pr-123-review/      # PR 代码审查
    ├── venv/
    └── ...
```

---

## 💡 最佳实践

### ✅ 推荐

- 每个 worktree 使用独立虚拟环境
- 使用清晰的命名（story-1.1, bugfix-xxx）
- 每完成一个 TDD 循环就提交
- 每天合并主分支变更
- 定期清理完成的 worktrees

### ❌ 避免

- 在 worktree 中使用模糊名称（test1, new-feature）
- 多个 worktree 共享虚拟环境（除非明确需要）
- 长时间不合并主分支（导致冲突累积）
- 忘记清理已完成的 worktrees

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [qwen-git-worktree-parallel-dev-guide.md](./qwen-git-worktree-parallel-dev-guide.md) | 完整指南 |
| [qwen_agent.md](./qwen_agent.md) | Qwen Agent 使用 |
| [sdd-tdd-fusion-guide.md](./sdd-tdd-fusion-guide.md) | SDD+TDD 融合模式 |

---

**快速参考版本:** 1.0.0
**最后更新:** 2026-03-20
