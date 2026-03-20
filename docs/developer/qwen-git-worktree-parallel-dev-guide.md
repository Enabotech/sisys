# Qwen Code AI Agent + Git Worktree 并行开发指南

**版本:** 1.0.0
**日期:** 2026-03-20
**作者:** Agimtech 团队
**状态:** 新建

---

## 📋 目录

1. [概述](#概述)
2. [核心概念](#核心概念)
3. [环境设置](#环境设置)
4. [工作流程](#工作流程)
5. [Qwen Agent 配置](#qwen-agent-配置)
6. [并行开发场景](#并行开发场景)
7. [最佳实践](#最佳实践)
8. [故障排除](#故障排除)
9. [快速参考卡片](#快速参考卡片)

---

## 概述

### 目标读者

- 使用 Qwen Code AI Agent 进行辅助开发的开发者
- 需要同时处理多个功能分支的开发者
- 希望提高上下文切换效率的开发者

### 核心价值

| 挑战 | 传统工作流 | Qwen + Worktree 并行工作流 |
|------|-----------|-------------------------|
| **上下文切换** | 频繁 `git checkout`，丢失编辑上下文 | 每个 worktree 独立目录，Qwen 保持独立会话 |
| **多任务并行** | 单一线程，任务阻塞 | 多个 worktree 同时开发，Qwen 多 Agent 协作 |
| **环境隔离** | 虚拟环境切换复杂 | 每个 worktree 独立虚拟环境 |
| **测试干扰** | 不同分支测试相互影响 | 完全隔离的测试环境 |
| **代码审查** | 切换分支查看差异 | 并排对比，Qwen 辅助审查 |

### 适用场景

1. **多 Story 并行开发** - 同时开发 Story 1.1、Story 1.2、Story 1.3
2. **Bug 修复 + 新功能** - 修复紧急 bug 的同时继续新功能开发
3. **代码审查** - 并排对比 PR 分支与主分支
4. **实验性开发** - 在不影响主线的情况下尝试新技术
5. **多版本维护** - 同时维护多个发布版本

---

## 核心概念

### Git Worktree 是什么？

Git Worktree 允许你从同一个 Git 仓库检出多个工作目录，每个工作目录：
- 有独立的分支
- 有独立的文件系统
- 共享 Git 对象数据库（节省磁盘空间）
- 可以独立进行 Git 操作

### Qwen Code Agent 是什么？

Qwen Code 是阿里巴巴开发的 AI 编程助手，在本项目中配置了：
- **多角色 Agent** - 领域专家、基础设施专家、测试专家等
- **SDD+TDD 融合模式** - 规范驱动 + 测试驱动开发
- **上下文感知** - 理解项目架构和编码规范

### 为什么需要并行？

```
传统单线程开发：
┌─────────────────────────────────────┐
│ Story 1.1 (3 天) → Story 1.2 (2 天)  │
│ 等待依赖 → 阻塞 → 完成              │
└─────────────────────────────────────┘
总耗时：5 天

Qwen + Worktree 并行开发：
┌─────────────────────────────────────┐
│ Worktree 1: Story 1.1 (领域层) ──┐  │
│ Worktree 2: Story 1.2 (应用层) ──┼──→ 协同完成
│ Worktree 3: Story 1.3 (基础设施) ─┘  │
└─────────────────────────────────────┘
总耗时：2-3 天（Qwen 辅助 + 并行）
```

---

## 环境设置

### 1. 系统要求

```bash
# Git 版本要求（支持 worktree）
$ git --version
git version 2.9.0 或更高

# Python 版本要求
$ python3 --version
Python 3.11+

# Poetry 版本要求
$ poetry --version
Poetry 1.7.0+
```

### 2. 创建 Worktree 目录结构

```bash
# 主仓库（作为基准）
cd /path/to/sisys

# 查看当前分支
$ git branch
* main
  master

# 创建 worktree 根目录（推荐位置）
mkdir -p ~/dev/sisys-worktrees
```

### 3. 创建功能分支 Worktree

```bash
# 场景：开发 Story 1.1 - 六边形架构骨架

# 1. 创建并检出功能分支
git checkout -b story/1.1-hexagonal-architecture

# 2. 创建 worktree（在独立目录）
git worktree add ~/dev/sisys-worktrees/story-1.1 story/1.1-hexagonal-architecture

# 3. 验证 worktree 创建成功
$ git worktree list
/path/to/sisys              [main]
~/dev/sisys-worktrees/story-1.1  [story/1.1-hexagonal-architecture]
```

### 4. 配置独立虚拟环境

```bash
# 进入 worktree 目录
cd ~/dev/sisys-worktrees/story-1.1

# 创建独立虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装项目依赖
poetry install --with dev,test

# 验证环境
$ pytest --version
pytest 8.0.0
```

### 5. 配置 Qwen Code Agent

```bash
# 在 worktree 目录中打开 Qwen Code
cd ~/dev/sisys-worktrees/story-1.1

# 激活 Qwen Agent（加载项目配置）
@qwen-agent

# 或激活特定角色
@qwen-agent activate domain_agent_1
```

### 6. 多 Worktree 配置示例

```bash
# 创建多个 worktree 用于并行开发

# Worktree 1: Story 1.1 - 领域层
git worktree add ~/dev/sisys-worktrees/story-1.1 story/1.1-hexagonal-architecture

# Worktree 2: Story 1.2 - 领域事件
git worktree add ~/dev/sisys-worktrees/story-1.2 story/1.2-domain-events

# Worktree 3: Story 1.3 - 事件总线
git worktree add ~/dev/sisys-worktrees/story-1.3 story/1.3-event-bus

# Worktree 4: Bug 修复
git worktree add ~/dev/sisys-worktrees/bugfix-urgent bugfix/critical-issue

# 查看所有 worktrees
$ git worktree list
/path/to/sisys                        [main]
~/dev/sisys-worktrees/story-1.1       [story/1.1-hexagonal-architecture]
~/dev/sisys-worktrees/story-1.2       [story/1.2-domain-events]
~/dev/sisys-worktrees/story-1.3       [story/1.3-event-bus]
~/dev/sisys-worktrees/bugfix-urgent   [bugfix/critical-issue]
```

---

## 工作流程

### 标准开发循环（单 Worktree）

```
┌─────────────────────────────────────────────────────────┐
│           Qwen + Worktree 标准开发循环                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 创建 Worktree                                        │
│     $ git worktree add <path> <branch>                  │
│                                                         │
│  2. 激活 Qwen Agent                                      │
│     @qwen-agent activate <role>                         │
│                                                         │
│  3. SDD 规范定义                                         │
│     - 定义领域事件 Schema                                │
│     - 定义 API 契约                                      │
│     - 定义验收标准                                      │
│                                                         │
│  4. TDD 红 - 绿 - 重构循环                                │
│     - 红：编写失败测试                                   │
│     - 绿：最小实现                                       │
│     - 重构：优化代码                                    │
│                                                         │
│  5. 质量门禁                                             │
│     $ make quality-gates                                │
│                                                         │
│  6. 提交代码                                             │
│     $ git add . && git commit -m "..."                  │
│                                                         │
│  7. 清理 Worktree（可选）                                │
│     $ git worktree remove <path>                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 并行开发流程（多 Worktree）

```
┌─────────────────────────────────────────────────────────┐
│              多 Worktree 并行开发流程                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  上午 9:00 - 任务规划                                    │
│  ├─ Worktree 1: Story 1.1 - 领域实体实现                │
│  ├─ Worktree 2: Story 1.2 - 领域事件定义                │
│  └─ Worktree 3: Bug 修复 - 紧急问题                     │
│                                                         │
│  上午 9:30 - Worktree 1（领域层）                        │
│  $ cd ~/dev/sisys-worktrees/story-1.1                   │
│  $ @qwen-agent activate domain_agent_1                  │
│  $ make tdd-red TARGET=domain/entities                  │
│  # 编写领域实体测试...                                  │
│                                                         │
│  上午 11:00 - Worktree 2（领域事件）                     │
│  $ cd ~/dev/sisys-worktrees/story-1.2                   │
│  $ @qwen-agent activate domain_agent_2                  │
│  $ make sdd-define                                      │
│  # 定义领域事件 Schema...                               │
│                                                         │
│  下午 2:00 - Worktree 3（Bug 修复）                      │
│  $ cd ~/dev/sisys-worktrees/bugfix-urgent               │
│  $ @qwen-agent activate test_agent_1                    │
│  # 编写复现测试，修复 bug...                            │
│                                                         │
│  下午 4:00 - 协同评审                                    │
│  # 使用 Qwen Party Mode 进行跨分支评审                  │
│  @qwen-agent party-mode --agents=3                      │
│                                                         │
│  下午 5:00 - 提交与清理                                  │
│  # 依次提交各 worktree 的更改                            │
│  $ git add . && git commit                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Qwen Agent 配置

### 1. 多 Worktree 上下文隔离

每个 worktree 是独立的目录，Qwen Code 会自动识别：

```yaml
# .qwen/qwen-agent-config.yaml
context:
  # 自动检测当前 worktree 路径
  auto_detect_worktree: true

  # 上下文隔离（不同 worktree 使用不同会话）
  isolation:
    enabled: true
    scope: "directory"

  # 共享知识（项目架构、规范等）
  shared_knowledge:
    - docs/architecture.md
    - docs/standards/coding-standards.md
    - .qwen/commands/*.md
```

### 2. 角色分配策略

| Worktree 类型 | 推荐 Agent 角色 | 职责 |
|--------------|----------------|------|
| **领域层开发** | `domain_agent_1` | 领域实体、值对象、聚合根 |
| **应用层开发** | `application_agent_1` | 用例编排、命令查询 |
| **基础设施开发** | `infrastructure_agent_1` | 数据库、消息队列、存储 |
| **测试开发** | `test_agent_1` | 单元测试、集成测试 |
| **Bug 修复** | `test_agent_1` + `review_agent` | 复现问题、修复验证 |
| **代码审查** | `review_agent` + `bmad_master_agent` | 质量检查、架构评审 |

### 3. Party Mode 多 Agent 协作

```bash
# 场景：跨 worktree 架构评审

# 在主 worktree 中启动 Party Mode
cd ~/dev/sisys-worktrees/story-1.1

# 启动 4 个 Agent 进行评审
@qwen-agent party-mode --agents=4 \
  --roles=domain_agent_1,infrastructure_agent_1,test_agent_1,review_agent \
  --context=../story-1.2,../story-1.3

# Qwen 会同时分析多个 worktree 的代码
# 并提供跨分支的架构一致性评审意见
```

### 4. 提示词模板（Worktree 场景）

#### 场景 1：新 Worktree 初始化

```
我正在创建新的 git worktree 用于开发 Story 1.1。

任务：
1. 确认当前分支状态
2. 检查是否有未提交的更改
3. 创建功能分支
4. 设置 worktree 目录
5. 初始化虚拟环境
6. 安装依赖

请逐步指导我完成设置。
```

#### 场景 2：多 Worktree 任务切换

```
我需要在多个 worktree 之间切换任务：

当前状态：
- Worktree 1 (story-1.1): 正在实现领域实体，测试已通过
- Worktree 2 (story-1.2): 需要开始定义领域事件
- Worktree 3 (bugfix): 紧急 bug 需要立即修复

请帮我：
1. 规划今天下午的开发任务
2. 为每个 worktree 推荐合适的 Agent 角色
3. 制定任务优先级
```

#### 场景 3：跨 Worktree 代码审查

```
请帮我审查以下 worktree 的代码变更：

- Worktree 1: story-1.1 (领域层实现)
- Worktree 2: story-1.2 (应用层实现)

审查重点：
1. 架构一致性（六边形架构约束）
2. 代码质量（ruff/mypy 检查）
3. 测试覆盖率（≥80%）
4. 领域模型一致性（跨分支对比）

请生成审查报告。
```

---

## 并行开发场景

### 场景 1：多 Story 并行开发

**背景：** Epic 1 包含 19 个 Story，需要并行开发加速交付

```bash
# ========== 设置阶段 ==========

# 1. 创建 Story 1.1 worktree（领域层）
git worktree add ~/dev/sisys-worktrees/story-1.1 story/1.1-hexagonal-architecture
cd ~/dev/sisys-worktrees/story-1.1
poetry install --with dev,test
@qwen-agent activate domain_agent_1

# 2. 创建 Story 1.2 worktree（领域事件）
git worktree add ~/dev/sisys-worktrees/story-1.2 story/1.2-domain-events
cd ~/dev/sisys-worktrees/story-1.2
poetry install --with dev,test
@qwen-agent activate domain_agent_2

# 3. 创建 Story 1.3 worktree（事件总线）
git worktree add ~/dev/sisys-worktrees/story-1.3 story/1.3-event-bus
cd ~/dev/sisys-worktrees/story-1.3
poetry install --with dev,test
@qwen-agent activate infrastructure_agent_2

# ========== 开发阶段 ==========

# 上午：Story 1.1 - 领域实体
cd ~/dev/sisys-worktrees/story-1.1
make tdd-red TARGET=domain/entities
# 编写测试...
make tdd-green TARGET=domain/entities
# 实现代码...
make tdd-refactor TARGET=domain/entities

# 下午：Story 1.2 - 领域事件
cd ~/dev/sisys-worktrees/story-1.2
make sdd-define
# 定义 Schema...
make tdd-red TARGET=domain/events
# 编写测试...

# ========== 协同阶段 ==========

# 使用 Party Mode 进行跨 Story 评审
cd ~/dev/sisys-worktrees/story-1.1
@qwen-agent party-mode --agents=3 \
  --context=../story-1.2,../story-1.3

# ========== 集成阶段 ==========

# 所有 Story 完成后，合并到主分支
cd /path/to/sisys
git merge story/1.1-hexagonal-architecture
git merge story/1.2-domain-events
git merge story/1.3-event-bus
```

### 场景 2：Bug 修复 + 新功能开发

**背景：** 正在开发新功能时，发现线上紧急 bug

```bash
# ========== 当前状态 ==========
# 你正在 story-1.1 worktree 中开发新功能

cd ~/dev/sisys-worktrees/story-1.1
# 突然收到紧急 bug 报告...

# ========== 创建 Bug 修复 Worktree ==========

# 1. 基于 main 分支创建 bug 修复 worktree
git worktree add -b bugfix/critical-issue ~/dev/sisys-worktrees/bugfix-urgent main

# 2. 激活测试专家 Agent
cd ~/dev/sisys-worktrees/bugfix-urgent
@qwen-agent activate test_agent_1

# 3. 复现 bug
# 根据 bug 报告编写复现测试
pytest tests/regression/test_critical_issue.py -v

# 4. 修复 bug
@qwen-agent activate domain_agent_1
# 分析原因，实施修复...

# 5. 验证修复
make quality-gates
pytest tests/regression/test_critical_issue.py -v

# 6. 提交修复
git add . && git commit -m "fix: 修复紧急问题 #critical"

# ========== 返回新功能开发 ==========

# 切换回 story-1.1 worktree
cd ~/dev/sisys-worktrees/story-1.1
# 继续新功能开发，不受干扰
```

### 场景 3：PR 代码审查

**背景：** 团队成员提交了 PR，需要进行代码审查

```bash
# ========== 准备审查环境 ==========

# 1. 创建 PR 分支 worktree
git fetch origin pull/123/head:pr-123
git worktree add ~/dev/sisys-worktrees/pr-123-review pr-123

# 2. 创建主分支对比 worktree
git worktree add ~/dev/sisys-worktrees/main-compare main

# ========== 使用 Qwen 辅助审查 ==========

cd ~/dev/sisys-worktrees/pr-123-review

# 3. 激活审查 Agent
@qwen-agent activate review_agent

# 4. 请求审查报告
请帮我审查这个 PR：
- 对比 main 分支的变更
- 检查架构一致性
- 运行质量门禁
- 验证测试覆盖率
- 识别潜在问题

# 5. 运行自动化检查
make quality-gates
pytest --cov=src --cov-fail-under=80

# 6. 生成审查报告
@qwen-agent generate-review-report \
  --compare-with=../../main-compare \
  --output=review-report.md
```

### 场景 4：实验性开发

**背景：** 想尝试新技术，但不影响主线开发

```bash
# ========== 创建实验性 Worktree ==========

# 1. 基于 main 创建实验分支
git worktree add -b experiment/new-tech ~/dev/sisys-worktrees/experiment-tech main

# 2. 独立开发环境
cd ~/dev/sisys-worktrees/experiment-tech
poetry add some-new-package

# 3. 激活 Qwen 进行技术咨询
@qwen-agent activate ai_agent_1
请帮我评估这项新技术的可行性：
- 与现有架构的兼容性
- 实施风险
- 迁移成本

# 4. 实验性开发
# 自由尝试，不影响主线...

# 5. 决策点
# 如果实验成功：创建正式分支，提交代码
# 如果实验失败：直接删除 worktree，无副作用
git worktree remove ~/dev/sisys-worktrees/experiment-tech
```

---

## 最佳实践

### 1. Worktree 命名规范

```bash
# 推荐命名模式
~/dev/sisys-worktrees/
├── story-1.1          # Story 1.1
├── story-1.2          # Story 1.2
├── bugfix-<issue>     # Bug 修复
├── pr-<number>-review # PR 审查
├── experiment-<name>  # 实验性开发
└── release-<version>  # 发布分支

# 避免使用模糊名称
❌ ~/dev/sisys-worktrees/test1
❌ ~/dev/sisys-worktrees/new-feature
```

### 2. 虚拟环境管理

```bash
# 每个 worktree 使用独立虚拟环境
~/dev/sisys-worktrees/story-1.1/venv/
~/dev/sisys-worktrees/story-1.2/venv/
~/dev/sisys-worktrees/bugfix-urgent/venv/

# 在 .gitignore 中确保 venv 被忽略
# （项目 .gitignore 已包含 venv/）

# 使用 poetry 统一管理依赖版本
poetry export -f requirements.txt --output requirements.txt
```

### 3. 磁盘空间优化

```bash
# Git worktree 共享对象数据库，节省空间
# 但仍需注意虚拟环境占用

# 查看 worktree 磁盘占用
$ du -sh ~/dev/sisys-worktrees/*

# 清理不需要的 worktree
git worktree prune
rm -rf ~/dev/sisys-worktrees/completed-story

# 使用虚拟环境共享（高级）
# 创建全局虚拟环境，多个 worktree 共享
python3 -m venv ~/dev/venvs/sisys-global
# 在每个 worktree 中 symlink
ln -s ~/dev/venvs/sisys-story-1.1 venv
```

### 4. 上下文管理

```bash
# 使用终端标签页或窗口区分 worktree
# Tab 1: story-1.1 - 领域层开发
# Tab 2: story-1.2 - 应用层开发
# Tab 3: bugfix-urgent - Bug 修复

# 使用 shell 提示显示当前 worktree
# 在 .bashrc 或 .zshrc 中添加：
parse_git_worktree() {
  if [ -f "$(git rev-parse --git-dir)/gitdir" ]; then
    echo "wt:$(basename $(dirname $(git rev-parse --git-dir)))"
  else
    echo "git:$(git branch --show-current)"
  fi
}

# 提示符显示：user@host ~/dev/sisys-worktrees/story-1.1 [wt:story-1.1]
```

### 5. Qwen 会话管理

```bash
# 每个 worktree 保持独立 Qwen 会话
# 避免上下文混淆

# 会话命名建议：
# - story-1.1-domain-session
# - story-1.2-events-session
# - bugfix-urgent-session

# 使用 Qwen 记录功能保存会话历史
@qwen-agent save-session --name=story-1.1-session

# 恢复会话
@qwen-agent load-session --name=story-1.1-session
```

### 6. 提交与合并策略

```bash
# 小步提交，频繁合并
cd ~/dev/sisys-worktrees/story-1.1

# 每完成一个 TDD 循环就提交
git add .
git commit -m "feat(domain): 创建 StrategicPlan 实体 (SDD+TDD)"

# 每天合并主分支变更（避免冲突累积）
git fetch origin
git merge origin/main

# 完成 Story 后合并到开发分支
git checkout story/1.1-hexagonal-architecture
git merge --no-ff story-1.1
git push origin story/1.1-hexagonal-architecture
```

### 7. 测试隔离

```bash
# 确保不同 worktree 的测试不互相干扰
# 使用独立的测试数据库

# 在 pytest.ini 或 pyproject.toml 中配置：
[tool.pytest.ini_options]
addopts = [
    "--cov=src",
    "--cov-report=term-missing",
    "-n", "auto",  # 并行测试
]

# pragma: allowlist secret 使用环境变量区分测试数据库
export TEST_DATABASE_URL="postgresql://user:pass@localhost/sisys_test_story_1_1"  # pragma: allowlist secret
```

---

## 故障排除

### 问题 1: Worktree 创建失败

**错误信息：**
```
fatal: 'story/1.1-hexagonal-architecture' is already checked out
```

**原因：** 分支已在其他 worktree 中检出

**解决方案：**
```bash
# 1. 查看分支在哪个 worktree 中
$ git worktree list

# 2. 选项 A：使用已有 worktree
cd ~/dev/sisys-worktrees/story-1.1

# 3. 选项 B：创建新分支
git worktree add -b story/1.1-new ~/dev/sisys-worktrees/story-1.1-new main
```

### 问题 2: 虚拟环境冲突

**错误信息：**
```
ModuleNotFoundError: No module named 'src'
```

**原因：** 虚拟环境未正确安装或路径错误

**解决方案：**
```bash
# 1. 重新创建虚拟环境
cd ~/dev/sisys-worktrees/story-1.1
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# 2. 重新安装依赖
poetry install --with dev,test

# 3. 验证安装
$ python -c "import src; print('OK')"
```

### 问题 3: Qwen Agent 上下文混淆

**现象：** Qwen 混淆了不同 worktree 的代码

**解决方案：**
```bash
# 1. 清除 Qwen 缓存
rm -rf .qwen/cache/

# 2. 重新激活 Agent
@qwen-agent deactivate
@qwen-agent activate domain_agent_1

# 3. 明确指定上下文
请只分析当前目录 (~/dev/sisys-worktrees/story-1.1) 的代码
```

### 问题 4: Git 冲突

**场景：** 多个 worktree 修改了相同文件

**解决方案：**
```bash
# 1. 查看冲突文件
git status

# 2. 使用 Qwen 辅助解决冲突
@qwen-agent resolve-conflicts \
  --file=src/domain/entities/strategic_plan.py \
  --base=main \
  --ours=story-1.1 \
  --theirs=story-1.2

# 3. 手动解决后标记
git add src/domain/entities/strategic_plan.py
git commit -m "merge: 解决冲突"
```

### 问题 5: 磁盘空间不足

**解决方案：**
```bash
# 1. 查看 worktree 占用
$ git worktree list --porcelain | du -sh

# 2. 清理完成的 worktree
git worktree remove ~/dev/sisys-worktrees/completed-story
git worktree prune

# 3. 清理虚拟环境
find ~/dev/sisys-worktrees -name "venv" -type d -exec du -sh {} \;

# 4. 使用共享虚拟环境（可选）
# 创建全局虚拟环境
python3 -m venv ~/dev/venvs/sisys-shared
# 在各 worktree 中创建 symlink
ln -s ~/dev/venvs/sisys-shared venv
```

---

## 快速参考卡片

### Worktree 命令速查

```bash
# 创建 worktree
git worktree add <path> <branch>
git worktree add -b <new-branch> <path> <base-branch>

# 查看 worktrees
git worktree list
git worktree list --porcelain

# 移动 worktree
git worktree move <old-path> <new-path>

# 删除 worktree
git worktree remove <path>
git worktree remove <path> --force

# 清理无效 worktree
git worktree prune

# 查看 lock 文件
git worktree list --porcelain | grep locked
```

### Qwen Agent 命令速查

```bash
# 激活 Agent
@qwen-agent
@qwen-agent activate <role>

# 查看可用 Agent
@qwen-agent list-agents

# Party Mode
@qwen-agent party-mode --agents=4 --roles=...

# 保存/加载会话
@qwen-agent save-session --name=<name>
@qwen-agent load-session --name=<name>

# 代码审查
@qwen-agent review --compare-with=<path>

# 生成文档
@qwen-agent generate-docs --output=<file>
```

### Makefile 命令速查

```bash
# SDD+TDD 开发循环
make sdd-define
make tdd-red TARGET=<path>
make tdd-green TARGET=<path>
make tdd-refactor TARGET=<path>
make sdd-tdd-cycle STORY=<story>

# 质量门禁
make quality-gates
make lint
make type-check
make test
make test-cov

# 快速开发
make dev-cycle
make tdd TARGET=<path>
make sdd-verify
```

### 典型工作流

```bash
# ========== 开始新 Story ==========
# 1. 创建 worktree
git worktree add -b story/1.x-feature ~/dev/sisys-worktrees/story-1.x main

# 2. 设置环境
cd ~/dev/sisys-worktrees/story-1.x
python3 -m venv venv
poetry install --with dev,test

# 3. 激活 Qwen
@qwen-agent activate domain_agent_1

# 4. 开始开发
make sdd-define
make tdd-red TARGET=domain/entities
# 编写测试...
make tdd-green TARGET=domain/entities
# 实现代码...

# ========== 提交代码 ==========
git add .
git commit -m "feat: 实现功能 (SDD+TDD)"
git push origin story/1.x-feature

# ========== 完成 Story ==========
# 1. 创建 PR
# 2. 清理 worktree
cd /path/to/sisys
git worktree remove ~/dev/sisys-worktrees/story-1.x
```

---

## 附录：完整示例

### 示例：并行开发 Story 1.1 和 Story 1.2

```bash
#!/bin/bash
# parallel-story-dev.sh - 并行开发脚本示例

set -e

# 配置
WORKTREE_BASE=~/dev/sisys-worktrees
STORY_1_1_BRANCH="story/1.1-hexagonal-architecture"
STORY_1_2_BRANCH="story/1.2-domain-events"

echo "=== 创建 Story 1.1 Worktree ==="
git worktree add -b $STORY_1_1_BRANCH $WORKTREE_BASE/story-1.1 main
cd $WORKTREE_BASE/story-1.1
python3 -m venv venv
source venv/bin/activate
poetry install --with dev,test
echo "✅ Story 1.1 Worktree 就绪"

echo "=== 创建 Story 1.2 Worktree ==="
git worktree add -b $STORY_1_2_BRANCH $WORKTREE_BASE/story-1.2 main
cd $WORKTREE_BASE/story-1.2
python3 -m venv venv
source venv/bin/activate
poetry install --with dev,test
echo "✅ Story 1.2 Worktree 就绪"

echo "=== 查看所有 Worktrees ==="
git worktree list

echo ""
echo "🎉 并行开发环境设置完成！"
echo ""
echo "使用指南："
echo "  cd $WORKTREE_BASE/story-1.1  # Story 1.1 开发"
echo "  cd $WORKTREE_BASE/story-1.2  # Story 1.2 开发"
echo ""
echo "Qwen Agent 激活："
echo "  @qwen-agent activate domain_agent_1"
echo ""
```

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [qwen_agent.md](./qwen_agent.md) | Qwen Code Agent 使用指南 |
| [sdd-tdd-fusion-guide.md](./sdd-tdd-fusion-guide.md) | SDD+TDD 融合开发模式 |
| [pre-commit-hooks.md](./pre-commit-hooks.md) | 预提交 Hooks 配置 |
| [testing_guide.md](./testing_guide.md) | 测试框架使用指南 |
| [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) | 完整架构设计文档 |

---

**维护者:** sisys 开发团队
**最后更新:** 2026-03-20
**版本:** 1.0.0
