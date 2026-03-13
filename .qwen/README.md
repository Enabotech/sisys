# Qwen Code Agent 配置指南

本目录包含 sisys 项目的 Qwen Code Agent 配置文件和使用说明。

---

## 📁 文件结构

```
.qwen/
├── qwen-agent-config.yaml    # Agent 配置文件（核心）
├── commands/
│   └── qwen-agent.md         # Agent 激活和使用说明
│   └── *.md                  # 其他 BMAD Agent 配置
└── README.md                 # 本文件
```

---

## 🚀 快速开始

### 1. 加载 Agent 配置

在 Qwen Code 对话中，使用以下命令加载配置：

```bash
# 方式 1：使用 qwen-agent 命令
@qwen-agent

# 方式 2：直接指定角色
@qwen-agent activate domain_agent_1
```

### 2. 查看可用 Agent

```bash
@qwen-agent list-agents
```

### 3. 激活特定 Agent

```bash
# 领域层开发
@qwen-agent activate domain_agent_1

# 数据库实现
@qwen-agent activate infrastructure_agent_1

# 测试编写
@qwen-agent activate test_agent_1
```

### 4. 多 Agent 协作（Party Mode）

```bash
# 启动 4 个 Agent 进行架构评审
@qwen-agent party-mode --agents=4 \
  --roles=domain_agent_1,infrastructure_agent_1,test_agent_1,review_agent
```

---

## 🎯 Agent 角色说明

### 领域层（Domain Layer）

| Agent | 职责 | 适用场景 |
|-------|------|---------|
| `domain_agent_1` | 领域层开发专家 | 创建领域实体、值对象、聚合根 |
| `domain_agent_2` | 领域服务专家 | 实现领域服务、领域事件 |

### 基础设施层（Infrastructure Layer）

| Agent | 职责 | 适用场景 |
|-------|------|---------|
| `infrastructure_agent_1` | 数据库专家 | PostgreSQL 表设计、SQL 优化 |
| `infrastructure_agent_2` | 消息队列专家 | RabbitMQ 配置、Outbox 模式 |
| `infrastructure_agent_3` | 向量/图存储专家 | Qdrant/Neo4j 实现 |

### 工作流引擎（Workflow Engine）

| Agent | 职责 | 适用场景 |
|-------|------|---------|
| `workflow_agent_1` | Prefect 专家 | 数据管道、文档处理流程 |
| `workflow_agent_2` | LangGraph 专家 | Agent 协作图、BLM 状态机 |

### AI/ML

| Agent | 职责 | 适用场景 |
|-------|------|---------|
| `ai_agent_1` | LLM 路由专家 | UDMR 实现、LiteLLM 集成 |
| `ai_agent_2` | RAG 专家 | 混合检索、BGE-M3 嵌入 |

### 测试（Test）

| Agent | 职责 | 适用场景 |
|-------|------|---------|
| `test_agent_1` | 单元测试专家 | pytest 测试、Mock |
| `test_agent_2` | 集成测试专家 | E2E 测试、性能测试 |

### 支持（Support）

| Agent | 职责 | 适用场景 |
|-------|------|---------|
| `doc_agent` | 技术文档专家 | Markdown 文档、API 文档 |
| `review_agent` | 代码审查专家 | mypy/ruff 检查、安全扫描 |
| `bmad_master_agent` | BMAD 协调员 | Party Mode 评审 |

---

## 💡 使用示例

### 示例 1：创建领域实体

```bash
@qwen-agent domain_agent_1

任务：创建 RoutingDecisionLog 实体
要求：
  - 参考 architecture.md 第 4.5 节
  - 使用 Pydantic v2
  - 包含以下字段：id, task_id, timestamp, l1_result, l2_scores, l3_decision
  - 添加类型注解和文档字符串
  - 编写单元测试
```

### 示例 2：实现数据库仓储

```bash
@qwen-agent infrastructure_agent_1

任务：实现 RoutingDecisionLog 仓储
要求：
  - 使用 SQLAlchemy 2.0
  - 实现 CRUD 操作
  - 添加 Alembic 迁移脚本
  - 参考 architecture.md 第 11 章
```

### 示例 3：代码审查

```bash
@qwen-agent review_agent

任务：审查 PR #001 - 领域层实体实现
检查项：
  - [ ] 类型检查 (mypy)
  - [ ] Lint 检查 (ruff)
  - [ ] 安全扫描
  - [ ] 架构一致性验证
```

---

## ⚙️ 配置说明

### 全局配置（qwen-agent-config.yaml）

```yaml
global:
  communication_language: "Chinese"  # 中文输出
  max_context_tokens: 128000
  temperature: 0.7
  top_p: 0.9
```

### 并行度管理

```yaml
parallelism:
  max_concurrent_agents: 6  # 最佳并行数（不超过 8 个）
  task_queue_enabled: true
  conflict_detection_enabled: true
```

### 代码审查

```yaml
code_review:
  auto_review_enabled: true
  checks:
    - type_check   # mypy 类型检查
    - lint         # ruff 代码风格
    - security     # 安全扫描
    - performance  # 性能分析
  merge_strategy: "human_approval"  # 人类最终审批
```

---

## 📊 MVP 实施计划

参考：`_bmad-output/planning-artifacts/mvp-implementation-plan.md`

### P0 优先级（核心路径）

1. `domain_agent_1` - 领域层核心实体
2. `infrastructure_agent_1` - PostgreSQL 仓储
3. `infrastructure_agent_2` - RabbitMQ + Outbox

### P1 优先级

4. `workflow_agent_1` - Prefect 工作流
5. `ai_agent_1` - UDMR 路由框架
6. `workflow_agent_2` - LangGraph 状态机

### P2 优先级

7. `test_agent_1` - 单元测试覆盖
8. `test_agent_2` - 集成测试
9. `doc_agent` - API 文档

---

## 🔧 故障排除

### 问题：Agent 无法激活

**解决：**
1. 检查配置文件路径：`.qwen/qwen-agent-config.yaml`
2. 确认 Agent 名称正确
3. 重新加载 Qwen Code

### 问题：多 Agent 上下文冲突

**解决：**
1. 减少并发 Agent 数量（建议≤6）
2. 启用上下文隔离：`context_isolation: true`
3. 使用任务队列管理

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| `_bmad-output/planning-artifacts/architecture.md` | 完整架构设计（6000+ 行） |
| `_bmad-output/planning-artifacts/prd.md` | 产品需求文档 |
| `_bmad-output/planning-artifacts/mvp-implementation-plan.md` | MVP 实施计划 |
| `.qwen/commands/bmad-*.md` | BMAD Agent 配置 |

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-02-26 | 初始版本，基于 architecture.md 6.0.0 |

---

**维护者：** sisys 开发团队
**最后更新：** 2026-02-26
