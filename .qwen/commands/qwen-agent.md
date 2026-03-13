---
name: 'qwen-agent'
description: 'Qwen Code Agent 配置加载器 - 用于 sisys 项目的多 Agent 协作开发'
version: '1.0.0'
---

# Qwen Code Agent 配置加载器

**项目：** sisys - 企业战略规划管理系统
**架构：** 六边形架构 + 事件驱动
**开发模式：** Qwen Code Agent + SDD（Specification-Driven Development）

---

## 🚀 快速激活

### 方式 1：加载完整配置
```bash
# 在 Qwen Code 中执行
@qwen-agent load-config
```

### 方式 2：指定 Agent 角色
```bash
# 激活特定 Agent
@qwen-agent activate domain_agent_1
@qwen-agent activate infrastructure_agent_1
@qwen-agent activate test_agent_1
```

### 方式 3：Party Mode 多 Agent 协作
```bash
# 启动多 Agent 评审
@qwen-agent party-mode --agents=4
```

---

## 📋 可用 Agent 角色

### 领域层 Agent
| Agent | 职责 | 技能 |
|-------|------|------|
| `domain_agent_1` | 领域层开发专家 | DDD, Python, 领域建模，六边形架构 |
| `domain_agent_2` | 领域服务专家 | 领域服务，领域事件，业务逻辑 |

### 基础设施层 Agent
| Agent | 职责 | 技能 |
|-------|------|------|
| `infrastructure_agent_1` | 数据库专家 | PostgreSQL, Redis, SQL 优化 |
| `infrastructure_agent_2` | 消息队列专家 | RabbitMQ, 事件驱动，Outbox 模式 |
| `infrastructure_agent_3` | 向量/图存储专家 | Qdrant, Neo4j, 混合检索 |

### 工作流引擎 Agent
| Agent | 职责 | 技能 |
|-------|------|------|
| `workflow_agent_1` | Prefect 工作流专家 | Prefect, 数据管道 |
| `workflow_agent_2` | LangGraph Agent 编排专家 | LangGraph, 状态机，BLM/BEM |

### AI/ML Agent
| Agent | 职责 | 技能 |
|-------|------|------|
| `ai_agent_1` | LLM 路由专家 | LiteLLM, UDMR, Qwen |
| `ai_agent_2` | RAG 专家 | RAG, BGE-M3, 混合检索 |

### 测试 Agent
| Agent | 职责 | 技能 |
|-------|------|------|
| `test_agent_1` | 单元测试专家 | pytest, 单元测试，Mock |
| `test_agent_2` | 集成测试专家 | 集成测试，E2E, 性能测试 |

### 支持 Agent
| Agent | 职责 | 技能 |
|-------|------|------|
| `doc_agent` | 技术文档专家 | Markdown, API 文档 |
| `review_agent` | 代码审查专家 | 代码审查，安全扫描，mypy |
| `bmad_master_agent` | BMAD Master Agent | BMAD, Party Mode |

---

## 🎯 典型工作流

### 1. 领域层开发
```bash
# 激活领域层 Agent
@qwen-agent activate domain_agent_1

# 任务：创建 StrategicPlan 实体
# 参考架构：architecture.md 第 17.4 节
# 输出：src/domain/models/strategic_plan.py
```

### 2. 基础设施实现
```bash
# 激活数据库 Agent + 消息队列 Agent
@qwen-agent activate infrastructure_agent_1 infrastructure_agent_2

# 任务：实现 PostgreSQL 仓储 + RabbitMQ Outbox
# 参考架构：architecture.md 第 10.3 节、第 11 章
```

### 3. 测试驱动开发
```bash
# 激活测试 Agent
@qwen-agent activate test_agent_1

# 任务：为领域服务编写 pytest 测试
# 目标覆盖率：≥85%
```

### 4. 代码审查
```bash
# 激活审查 Agent
@qwen-agent activate review_agent

# 任务：审查 PR #001
# 检查：类型检查 (mypy) + Lint(ruff) + 安全扫描
```

### 5. Party Mode 架构评审
```bash
# 启动多 Agent 评审
@qwen-agent party-mode --agents=4 \
  --roles=domain_agent_1,infrastructure_agent_1,test_agent_1,review_agent \
  --topic="MVP 架构完整性评审"
```

---

## ⚙️ 配置参数

### 全局配置
```yaml
communication_language: "Chinese"  # 中文输出
max_context_tokens: 128000
temperature: 0.7
top_p: 0.9
```

### 并行度管理
```yaml
max_concurrent_agents: 6  # 最佳并行数
task_queue_enabled: true
conflict_detection_enabled: true
```

### 代码审查
```yaml
auto_review_enabled: true
checks:
  - type_check   # mypy
  - lint         # ruff
  - security     # 安全扫描
  - performance  # 性能分析
```

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `.qwen/qwen-agent-config.yaml` | Agent 配置文件 |
| `_bmad-output/planning-artifacts/architecture.md` | 完整架构设计 |
| `_bmad-output/planning-artifacts/mvp-implementation-plan.md` | MVP 实施计划 |
| `_bmad-output/planning-artifacts/prd.md` | 产品需求文档 |

---

## 🔧 使用示例

### 示例 1：创建新领域实体
```bash
@qwen-agent domain_agent_1
任务：基于 architecture.md 第 9 章，创建 RoutingDecisionLog 实体
要求：
  - 使用 Pydantic v2
  - 包含所有必需字段
  - 添加类型注解
  - 编写单元测试
```

### 示例 2：实现 UDMR 路由
```bash
@qwen-agent ai_agent_1
任务：实现 UDMR L1 合规性网关
参考：architecture.md 第 4.2 节
输出：src/infrastructure/ai/udmr/compliance_gateway.py
```

### 示例 3：数据库迁移
```bash
@qwen-agent infrastructure_agent_1
任务：创建 Alembic 迁移脚本
表：routing_decision_logs, isolation_switch_logs
参考：architecture.md 第 11 章
```

---

## 📊 MVP 实施优先级

| 优先级 | Agent | 任务 |
|-------|-------|------|
| P0 | domain_agent_1 | 领域层核心实体 |
| P0 | infrastructure_agent_1 | PostgreSQL 仓储实现 |
| P0 | infrastructure_agent_2 | RabbitMQ + Outbox |
| P1 | workflow_agent_1 | Prefect 工作流 |
| P1 | ai_agent_1 | UDMR 路由框架 |
| P2 | test_agent_1 | 单元测试覆盖 |
| P2 | doc_agent | API 文档生成 |

---

## 🎓 最佳实践

1. **任务分解** - 将大任务拆分为小任务分配给不同 Agent
2. **上下文隔离** - 每个 Agent 独立上下文，避免冲突
3. **自动审查** - 启用 mypy + ruff 自动检查
4. **人类审批** - 关键代码需要人类最终审批
5. **文档同步** - 代码变更同步更新文档

---

**版本：** 1.0.0
**更新日期：** 2026-02-26
**维护者：** sisys 开发团队
