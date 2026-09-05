# sisys 总体接口设计规则

**版本：** 2.0.0
**状态：** DDD+EDA 整合版
**日期：** 2026-04-08
**设计原则：** CLI + Skills 为核心接口，MCP 为外部生态接口，与 DDD 四层架构 + 事件驱动有机整合
**借鉴来源：** Claude Code 渐进式披露 + 钉钉/飞书 CLI 化改造 + 行业 MCP 评估 + or.md DDD+事件驱动架构

---

## 目录

1. [设计哲学与核心原则](#1-设计哲学与核心原则)
2. [接口分层架构](#2-接口分层架构)
3. [四层映射架构（DDD + EDA + CLI+Skills 统一）](#3-四层映射架构ddd--eda--cliskills-统一)
4. [CLI 接口设计规范](#4-cli-接口设计规范)
5. [Skills 渐进式加载机制](#5-skills-渐进式加载机制)
6. [MCP 外部生态接口](#6-mcp-外部生态接口)
7. [SAP Agent 间通信协议](#7-sap-agent-间通信协议)
8. [REST API 集成接口](#8-rest-api-集成接口)
9. [LLM 接入协议](#9-llm-接入协议)
10. [工具间调用协议](#10-工具间调用协议)
11. [Prompt 模板协议](#11-prompt-模板协议)
12. [事件监听适配器规范](#12-事件监听适配器规范)
13. [Web 前端接口规范](#13-web-前端接口规范)
14. [接口版本管理与兼容性](#14-接口版本管理与兼容性)
15. [安全与权限控制](#15-安全与权限控制)
16. [可观测性与监控](#16-可观测性与监控)
17. [实施路线图](#17-实施路线图)
18. [参考文档](#18-参考文档)

---

## 1. 设计哲学与核心原则

### 1.1 核心设计哲学

sisys 采用 **"CLI + Skills 为内核，MCP 为外延"** 的接口架构哲学，基于以下行业共识：

| 来源 | 核心洞察 | 对 sisys 的启示 |
|------|---------|----------------|
| **钉钉/飞书 CLI 化改造** | CLI 是 Agent 操作软件的默认界面 | sisys 内部能力优先通过 CLI 暴露 |
| **Claude Code 渐进式披露** | 三级加载解决上下文爆炸 | Skills 采用 L1 元数据→L2 SOP→L3 资源 |
| **MCP vs CLI benchmark** | CLI 比 MCP 节省 9-32 倍 token | 内部调用不走 MCP |
| **Perplexity CTO 表态** | 72% 上下文被 MCP 占用 | 限制 MCP 仅用于外部生态 |

### 1.2 七条核心原则

| 编号 | 原则 | 描述 | 验收标准 |
|------|------|------|---------|
| **P1** | CLI 是 LLM 的母语 | 系统内部所有能力优先通过 CLI 暴露，Agent 通过 CLI 调用内部工具 | 内部工具 100% 有 CLI 入口 |
| **P2** | Skills = 渐进式披露 | Agent 启动加载 L1 元数据聚合（≤1.2K tokens，23 工具 ≈1150 tokens，Anthropic 风格），按需加载完整 SOP | L1 启动注入 ≤1.2K tokens / L2 ≤500 行 |
| **P3** | Skill = SOP | 不仅定义工具签名，还定义操作流程、失败处理、兜底策略 | 23 种工具各有完整 SOP |
| **P4** | MCP 退居生态层 | MVP/V1 不启用 MCP，V2+ 按需用于外部 Agent 集成 | MVP 阶段 MCP 代码量 = 0 |
| **P5** | Less scaffolding, more model | 依赖模型自身推理进行工具路由，避免硬编码分类器 | 工具选择准确率 ≥ 85% |
| **P6** | 负向触发条件 | 明确"何时不应触发"Skill，避免误激活 | 误触发率 < 5% |
| **P7** | input_examples 驱动 | 为复杂工具提供 1-5 个典型输入示例，提升 Agent 使用准确率 | 工具调用准确率 ≥ 90% |

---

## 2. 接口分层架构

### 2.1 总体分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                        sisys 接口分层架构                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  【外部用户/系统】                                                    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────┐     ┌──────────────────┐                       │
│  │   CLI 接口层     │     │   REST API 层     │  ← 对外（用户/集成）   │
│  │   sisys CLI     │     │   FastAPI 0.104+  │                       │
│  │   (typer 0.24+) │     │   OpenAPI 3.1     │                       │
│  └────────┬────────┘     └────────┬─────────┘                       │
│           │                       │                                  │
│           └───────────┬───────────┘                                  │
│                       ▼                                              │
│  ┌──────────────────────────────────────┐                           │
│  │       应用层用例服务 (Use Cases)      │                           │
│  │  DocumentProcessingUseCase            │                           │
│  │  StrategicAnalysisUseCase             │                           │
│  │  AgentCollaborationUseCase            │                           │
│  │  PlanningGenerationUseCase            │                           │
│  └──────────────────┬───────────────────┘                           │
│                       │                                              │
│           ┌───────────┴───────────┐                                  │
│           ▼                       ▼                                  │
│  ┌─────────────────┐     ┌──────────────────┐                       │
│  │   CLI 工具层     │     │   Skills 层       │  ← 核心（内部主干）    │
│  │   sisys doc     │     │   AGENT.md        │                       │
│  │   sisys tool    │     │   IDENTITY.md     │                       │
│  │   sisys agent   │     │   SOUL.md         │                       │
│  │   sisys plan    │     │   TOOLS.md        │                       │
│  │   sisys checkpt │     │   MEMORY.md       │                       │
│  └────────┬────────┘     │   HEARTBEAT.md    │                       │
│           │              │   SKILL.md × 23   │                       │
│           │              └────────┬─────────┘                       │
│           │                       │                                  │
│           └───────────┬───────────┘                                  │
│                       ▼                                              │
│  ┌──────────────────────────────────────┐                           │
│  │       领域层 (Domain)                 │                           │
│  │  Document / Tool / Agent / Plan      │                           │
│  │  Checkpoint / Archive / RoutingLog   │                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
│  ┌──────────────────────────────────────┐                           │
│  │   MCP 层（V2+ 可选，对外暴露）         │  ← 外延（外部生态）        │
│  │   MCP Registry + MCP Servers         │                           │
│  │   仅用于：外部 Agent 生态集成          │                           │
│  │         企业级统一权限管控             │                           │
│  │         跨系统工具平台对接             │                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
│  ┌──────────────────────────────────────┐                           │
│  │   SAP 层（V1+，Agent 间通信）          │  ← 横向协作               │
│  │   自定义消息协议 + mTLS               │                           │
│  │   用于：多 Agent 协作/辩论/仲裁        │                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
│  ┌──────────────────────────────────────┐                           │
│  │   LLM Adapter 层（内→外）             │  ← 模型调用               │
│  │   LiteLLM 统一代理 + UDMR 路由       │                           │
│  │   用于：统一调用本地/云端 LLM API      │                           │
│  └──────────────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 接口职责矩阵

| 接口层 | 职责 | 用户 | 方向 | 版本 | 优先级 |
|--------|------|------|------|------|-------|
| **CLI** | 系统内部能力暴露 | 用户 + Agent | 外→内 | MVP | **P0** |
| **Skills** | Agent 行为知识（SOP） | Agent 内部 | 内部 | MVP | **P0** |
| **REST API** | 外部系统集成 | 第三方系统 | 外→内 | MVP | **P0** |
| **SAP** | Agent 间通信 | Agent 之间 | 横向 | V1 | **P1** |
| **LLM Adapter** | 统一 LLM 调用 | 系统内部 | 内→外 | MVP | **P0** |
| **MCP** | 外部 Agent 生态 | 外部 Agent | 外→内 | V2+ | **P2** |

### 2.3 接口依赖关系

```
CLI ──→ Use Cases ──→ Domain
              │
Skills ──→ Agent ──→ ToolService ──→ Domain
              │
LLM Adapter ──→ Agent（推理时调用）
              │
SAP ──→ Agent 之间（协作时调用）
              │
MCP ──→ 外部 Agent 发现/调用工具箱（V2+ 启用）
```

---

## 3. 四层映射架构（DDD + EDA + CLI+Skills 统一）

### 3.1 核心设计哲学

本节定义 CLI+Skills 接口设计与 or.md 原有的 DDD 四层架构 + 事件驱动架构的精确映射关系，解决三层脱节问题：

| 脱节问题 | 描述 | 解决方案 |
|---------|------|---------|
| **脱节 1** | CLI 命令 → 应用层用例缺少精确映射规范 | 定义 CLI-to-UseCase 映射规则 |
| **脱节 2** | Skills → 领域服务关系不明确 | 定义 Skills 在 DDD 架构中的精确位置 |
| **脱节 3** | 领域事件发布与 CLI 响应协调机制缺失 | 定义同步响应与异步事件处理的协调规则 |

### 3.2 四层映射架构图

```
┌──────────────────────────────────────────────────────────────────────────┐
│              sisys 四层映射架构（DDD + EDA + CLI+Skills 统一）             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  【外部触发层】                        【内部触发层】                       │
│  CLI 命令 / REST API / 定时任务        领域事件 / 心跳事件                  │
│       │                                      │                            │
│       │  ① Command Translator                │  ① Event Listener          │
│       ▼                                      ▼                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  接口层 (Interfaces) - 输入适配器 (or.md 1.4.1)                   │    │
│  │  ┌──────────────┐  ┌────────────┐  ┌──────────────────────┐     │    │
│  │  │ CLI 适配器    │  │ REST API   │  │ 事件监听适配器        │     │    │
│  │  │ (typer)      │  │ (FastAPI)  │  │ (RabbitMQ Consumer)  │     │    │
│  │  └──────┬───────┘  └─────┬──────┘  └──────────┬───────────┘     │    │
│  │         │                │                     │                 │    │
│  │         └────────────────┼─────────────────────┘                 │    │
│  │                          ▼                                       │    │
│  │              ┌────────────────────────┐                          │    │
│  │              │ 命令/事件 转换器        │                          │    │
│  │              │ Command/Event →        │                          │    │
│  │              │ ApplicationCommand     │                          │    │
│  │              └───────────┬────────────┘                          │    │
│  └──────────────────────────┼───────────────────────────────────────┘    │
│                             │                                            │
│  ┌──────────────────────────▼────────────────────────────────────────┐  │
│  │  应用层 (Application) - 用例服务 (or.md 1.3) + Skills 操作手册     │  │
│  │  ┌────────────────────────────────────────────────────────────┐  │  │
│  │  │ 用例服务 (5 个)                                             │  │  │
│  │  │ • DocumentProcessingUseCase                                 │  │  │
│  │  │ • StrategicAnalysisUseCase                                  │  │  │
│  │  │ • AgentCollaborationUseCase                                 │  │  │
│  │  │ • PlanningGenerationUseCase                                 │  │  │
│  │  │ • SystemOperationsUseCase                                   │  │  │
│  │  └────────────────────────┬───────────────────────────────────┘  │  │
│  │                           │                                      │  │
│  │  ┌────────────────────────▼───────────────────────────────────┐  │  │
│  │  │ Skills 层 (操作手册，非用例，非领域服务)                      │  │  │
│  │  │ ┌────────────────────────────────────────────────────────┐│  │  │
│  │  │ │ L1: TOOLS.md (≤1.2K tokens) - 23 工具元数据聚合         ││  │  │
│  │  │ │ L2: SKILL.md × 23 (< 500 行) - SOP 完整定义            ││  │  │
│  │  │ │ L3: scripts/references - 按需加载资源                   ││  │  │
│  │  │ │                                                        ││  │  │
│  │  │ │ 职责：指导用例如何调用领域服务                             ││  │  │
│  │  │ │ 不是用例本身，是用例的"操作手册"                           ││  │  │
│  │  │ │ 不是领域服务，领域服务是纯逻辑，Skill 是操作流程           ││  │  │
│  │  │ └────────────────────────────────────────────────────────┘│  │  │
│  │  └────────────────────────┬───────────────────────────────────┘  │  │
│  └───────────────────────────┼──────────────────────────────────────┘  │
│                              │                                         │
│  ┌───────────────────────────▼──────────────────────────────────────┐  │
│  │  领域层 (Domain) - or.md 1.2                                      │  │
│  │  ┌────────────────────────────────────────────────────────────┐  │  │
│  │  │ 领域实体 (6 聚合根)                                          │  │  │
│  │  │ Document / Tool / Agent / Plan / Checkpoint / Archive      │  │  │
│  │  └────────────────────────┬───────────────────────────────────┘  │  │
│  │                           │                                      │  │
│  │  ┌────────────────────────▼───────────────────────────────────┐  │  │
│  │  │ 领域服务接口 (8 个) + 实现 (基础设施层 DI)                   │  │  │
│  │  │ DocumentService / RAGService / ToolService / AgentService  │  │  │
│  │  │ PlanningService / EvaluationService / VisualizationService │  │  │
│  │  │ RoutingService                                             │  │  │
│  │  └────────────────────────┬───────────────────────────────────┘  │  │
│  │                           │                                      │  │
│  │  ┌────────────────────────▼───────────────────────────────────┐  │  │
│  │  │ 领域事件 (10 种) - 由领域实体状态变更时发布                   │  │  │
│  │  │ NOT by Skill, NOT by CLI, NOT by UseCase                   │  │  │
│  │  │ DocumentProcessed / ToolExecuted / AgentDecided / ...      │  │  │
│  │  └────────────────────────┬───────────────────────────────────┘  │  │
│  └───────────────────────────┼──────────────────────────────────────┘  │
│                              │                                         │
│  ┌───────────────────────────▼──────────────────────────────────────┐  │
│  │  事件总线 (Event Bus) - or.md 1.1.2(2)                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │  │
│  │  │ Redis Pub/Sub│  │ RabbitMQ     │  │ Outbox       │           │  │
│  │  │ (实时通知)    │  │ (持久化)     │  │ (事务发件箱) │           │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │  │
│  │         │                 │                  │                   │  │
│  │         └─────────────────┼──────────────────┘                   │  │
│  │                           ▼                                      │  │
│  │              trigger → route → execute                           │  │
│  │              (系统公理一：自主调用循环，or.md 1.1.3(1))            │  │
│  │                           │                                      │  │
│  │                           ▼                                      │  │
│  │              下游用例监听并处理                                    │  │
│  └───────────────────────────┼──────────────────────────────────────┘  │
│                              │                                         │
│  ┌───────────────────────────▼──────────────────────────────────────┐  │
│  │  基础设施层 (Infrastructure) - or.md 1.5                          │  │
│  │  六层存储 / LLM Adapter / MCP (V2+) / 沙箱 / 消息总线实现         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.3 关键映射规则

#### 规则 1：CLI → 用例 → 领域服务 → 领域事件 完整链路

**完整调用链示例：`sisys tool run pestel --input data.json --output result.json`**

| 步骤 | 层级 | 组件 | 操作 | 输出 |
|------|------|------|------|------|
| T0 | 外部触发 | CLI 命令 | 用户执行命令 | 命令行输入 |
| T1 | 接口层 | CLI 适配器（typer） | 解析参数，生成 Command | `ToolExecutionCommand` |
| T2 | 应用层 | StrategicAnalysisUseCase | 接收命令，加载 Skill | `skill = SkillSelector.recommend(...)` |
| T3 | 应用层 | SKILL.md（L2 SOP） | 加载完整操作流程 | SOP 步骤 1-8 |
| T4 | 应用层 | 按 SOP 调用领域服务 | `ToolService.execute("pestel", input)` | 领域服务调用 |
| T5 | 领域层 | ToolService | 执行工具逻辑，状态变更 | 分析结果 |
| T6 | 领域层 | Tool 聚合根 | 状态变更后发布事件 | `ToolExecuted` 事件 |
| T7 | 事件总线 | Redis Pub/Sub + RabbitMQ | 双通道分发事件 | 异步分发 |
| T8 | 应用层 | 下游用例监听 | CostAggregationUseCase / SkillEvolutionUseCase | 异步处理 |
| T9 | 应用层 | 用例返回 DTO | `ToolExecutionResultDTO` | 结构化结果 |
| T10 | 接口层 | CLI 输出适配器 | 根据 `--format` 格式化输出 | 用户看到结果 |

**关键设计：T6 事件发布不阻塞 T10 CLI 响应。下游事件处理是异步的，与 CLI 响应解耦。**

#### 规则 2：CLI 命令到应用层用例的精确映射

| CLI 服务模块 | 映射用例 | or.md 用例定义 |
|-------------|---------|---------------|
| `sisys document upload/parse/search` | DocumentProcessingUseCase | or.md 1.3(1) |
| `sisys tool run/chain/list` | StrategicAnalysisUseCase | or.md 1.3(2) |
| `sisys agent run/status` | AgentCollaborationUseCase | or.md 1.3(3) |
| `sisys agent arbitrate` | AgentCollaborationUseCase + SystemOperationsUseCase | or.md 1.3(3) + 1.3(5) |
| `sisys plan generate/export/review` | PlanningGenerationUseCase | or.md 1.3(4) |
| `sisys checkpoint recover/list/show` | PlanningGenerationUseCase | or.md 1.3(4) |
| `sisys archive query/diff/timeline` | SystemOperationsUseCase（调用 `ArchiveReadModelPort` CQRS 读模型，跨 Plan/Checkpoint 聚合根投影） | or.md 1.3(5) |
| `sisys archive link/branch/create` | SystemOperationsUseCase（操作 Archive 聚合根，发布 `ArchiveCreated/Linked/Branched` 事件） | or.md 1.3(5) |
| `sisys system auth/monitor/route` | SystemOperationsUseCase | or.md 1.3(5) |

#### 规则 3：Skills 在 DDD 架构中的精确位置（对标 Anthropic Claude Code Skills）

**核心原则：Skills 不是领域服务、不是用例，而是"操作手册"（Anthropic Hub-and-Spoke 模式）。**

```
Skills 三级架构与 DDD 层对应（对标 Anthropic Claude Code Skills）

┌─────────────────────────────────────────────────────────────────┐
│  L1: TOOLS.md（应用层元数据清单，YAML frontmatter 聚合）        │
│  ├─ 大小：MVP ≤1.2K tokens / V1 ≤800 tokens / V2 ≤500 tokens   │
│  ├─ 加载时机：Agent 启动时全量预加载到系统提示                  │
│  ├─ 字段：name / description（合并角色/阶段/触发词/负向触发语义）│
│  │       version / sop_path / sop_line_count + accuracy /        │
│  │       false_positive_rate                                    │
│  └─ 触发机制：LLM 基于 description 中的 "Use when..." +          │
│              "Do not use when..." 短语自主判断                    │
│              （Anthropic "description 即触发器"）                  │
│                                                                 │
│  L2: SKILL.md（应用层操作手册，Hub-and-Spoke 结构）             │
│  ├─ 大小：≤500 行（超长规范拆分到 references/*.md）            │
│  ├─ 加载时机：模型判断相关时通过 Read 工具按需加载               │
│  ├─ 章节：Overview / When to Use / When NOT to Use /             │
│  │       Quick Start / Core Workflow / Examples /                │
│  │       Gotchas / References                                    │
│  ├─ 必含："When NOT to Use" 负向触发章节（P6 + Anthropic 强制） │
│  └─ 不实现领域逻辑，只定义调用流程（与 sisys Tool/Agent 解耦）   │
│                                                                 │
│  L3: scripts/ + references/ + assets/（基础设施层 + 应用层辅助）│
│  ├─ scripts/：确定性计算（数据校验/格式转换/排序）              │
│  │   Python 脚本在沙箱中执行（Anthropic "代码优先于 Prompt"）    │
│  ├─ references/：长篇规范（按需链式读取，Hub-and-Spoke 末梢）   │
│  ├─ assets/：模板与示例资源                                    │
│  └─ 通过 SandboxExecutor 端口执行，不直接访问领域层              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**实现状态（2026-09-04）：** Skills 系统**未实现**（设计 100%，实现 0%），详见 `architecture.md §17.3` + Epic 5 蓝图。

#### 规则 4：CLI 同步响应与事件异步处理的协调

```
┌─────────────────────────────────────────────────────────────┐
│  CLI 命令执行时序                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  T0: CLI 命令发送                                            │
│     │                                                       │
│     ▼                                                       │
│  T1: 用例执行开始                                            │
│     │                                                       │
│     ├── T2: Skill 加载（L1→L2→L3）                          │
│     │                                                       │
│     ├── T3: 领域服务执行                                     │
│     │      │                                                │
│     │      ▼                                                │
│     │   T4: 领域事件发布 ──→ 事件总线（异步，不阻塞 CLI）     │
│     │                                                       │
│     ├── T5: 证据包打包                                       │
│     │                                                       │
│     ▼                                                       │
│  T6: 用例返回 DTO                                           │
│     │                                                       │
│     ▼                                                       │
│  T7: CLI 格式化输出并返回给用户                               │
│                                                             │
│  注意：T4 的事件发布不阻塞 CLI 响应                           │
│  下游用例对事件的处理是异步的，与 CLI 响应解耦                  │
│                                                             │
│  如果用户需要等待下游事件处理完成（MVP 不实现，V1+ 可选增强）： │
│  → 使用 --wait-for-events <event-pattern-set>                │
│    --wait-timeout <seconds>（默认 30 秒）参数                  │
│  → CLI 订阅事件总线，等待特定事件完成                         │
│  → MVP 阶段 CLI 采用 fire-and-forget 模式（与 architecture.md │
│    §1.6 规则 4 一致）                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 规则 5：系统公理一与 CLI 的关系

**or.md 1.1.3(1) 原文：**
> 系统基于 trigger(事件)→route(路由)→execute(执行) 的自主调用循环构建

**与 CLI 的关系：**

| 触发器类型 | 来源 | 进入系统的方式 | 示例 |
|-----------|------|---------------|------|
| **外部触发器** | 用户/外部系统 | CLI 命令 / REST API | `sisys document upload` |
| **内部触发器** | 领域事件 / 心跳 | 事件总线监听 | `DocumentUploaded` 事件 |

**完整调用链：**

```
外部触发（CLI）                内部触发（领域事件）
      │                              │
      ▼                              ▼
sisys document upload        DocumentUploaded 事件
      │                              │
      ▼                              ▼
DocumentProcessingUseCase    trigger→route→execute 循环
      │                              │
      ▼                              ▼
发布 DocumentParsed 事件     下游用例自动执行
      │
      ▼
事件总线分发 → 多个消费者并行处理
```

**结论：CLI 是"点火开关"，领域事件是"引擎血液"，trigger→route→execute 是"引擎运转逻辑"。**

---

## 4. CLI 接口设计规范

### 4.1 总体设计原则

借鉴钉钉 `dws` 和飞书 `lark-cli` 的设计哲学：

- **服务/资源/动作** 三级命令结构
- **Agent 友好** 参数设计（`--yes`、`--dry-run`、``--mock`）
- **Unix 哲学**：pipe 组合、文本流、`--help` 自描述

### 4.2 sisys CLI 命令结构

```bash
# 顶层命令
sisys <service> <resource> <action> [options]

# 服务模块（6 个核心 + 2 个辅助）
sisys document   # 文档管理（上传/解析/检索/版本）
sisys tool       # 工具箱（执行/链编排/验证）
sisys agent      # Agent 协作（运行/状态/仲裁）
sisys plan       # 战略规划（生成/审批/导出）
sisys checkpoint # Checkpoint 管理（快照/恢复/修改）
sisys archive    # 战略档案（查询/对比/时间轴）
sisys system     # 系统管理（辅助：用户/权限/监控）
sisys config     # 配置管理（辅助：环境/路由/隔离）
```

### 4.3 完整命令清单

#### 4.3.1 文档管理（sisys document）

```bash
sisys document upload --file <path> [options]
  --format <type>           # 自动检测，可手动指定
  --business-domain <name>  # 业务域分类
  --yes                     # 跳过确认（Agent 模式）
  --dry-run                 # 预览解析结果
  --mock                    # 模拟数据调试

sisys document parse --id <doc-id> [options]
  --output-format <json|markdown|text>
  --extract-tables          # 提取表格语义
  --ocr                     # 启用本地 RapidOCR 扫描件识别

sisys document search --query <text> [options]
  --top-k <n>               # 返回结果数
  --domain <name>           # 业务域过滤
  --time-range <start:end>  # 时间范围
  --format <json|table|pretty>

sisys document version list --id <doc-id>
sisys document version snapshot --id <doc-id> --version <v>
sisys document delete --id <doc-id> --confirm  # 需要确认
```

#### 4.3.2 工具箱（sisys tool）

```bash
sisys tool list [options]
  --domain <name>           # 按领域过滤
  --format <json|table>

sisys tool run <tool-id> [options]
  --input <path>            # 输入数据文件
  --output <path>           # 输出结果文件
  --yes                     # 跳过确认（Agent 模式）
  --dry-run                 # 预览结果
  --mock                    # 模拟数据
  --session <session-id>    # 会话上下文
  --cost-budget <amount>    # 成本预算限制

sisys tool chain run <chain-id> --config <path> [options]
  --parallel                # 并行执行无依赖子任务
  --yes
  --dry-run

sisys tool schema <tool-id> --format <json|pretty>  # 查看工具 Schema
```

#### 4.3.3 Agent 协作（sisys agent）

```bash
sisys agent run <role> --task <text> [options]
  --input <path>            # 输入数据
  --output <path>           # 输出文件
  --skills <list>           # 指定加载的 Skills（逗号分隔）
  --isolation <level>       # 隔离等级 L1-L4
  --yes
  --dry-run

sisys agent status [options]
  --session <session-id>
  --format <json|table|pretty>

sisys agent arbitrate --session <session-id> [options]
  # SYS Agent 裁决入口
```

#### 4.3.4 战略规划（sisys plan）

```bash
sisys plan generate <type> [options]
  # type: SP（战略规划）| BP（业务计划）
  --stage <n>               # 阶段编号
  --checkpoint <id>         # 从 Checkpoint 恢复
  --yes
  --dry-run

sisys plan export --type <SP|BP> --format <pdf|markdown|json>

sisys plan review --id <plan-id>  # 人工审批入口
```

#### 4.3.5 Checkpoint 管理（sisys checkpoint）

```bash
sisys checkpoint list --plan-id <id>
sisys checkpoint show --id <cp-id>
sisys checkpoint recover --id <cp-id> [options]
  --mode <replay|override>  # 恢复模式
  --modifications <path>    # 修改内容文件
  --yes
  --dry-run
```

#### 4.3.6 战略档案（sisys archive）

```bash
sisys archive query [options]
  --time-range <start:end>
  --topic <text>
  --format <json|table>

sisys archive timeline --plan-id <id>  # 时间轴演进查询
sisys archive diff --branch-a <id> --branch-b <id>  # 分支差异对比
```

#### 4.3.7 系统管理（sisys system）

```bash
sisys system auth login --user <name> --password-file <path>  # 凭据登录
sisys system auth logout --token <token>                      # 注销
sisys system auth status                                      # 当前会话状态
sisys system monitor [--metric <name>] [--format json|table]  # 监控指标查询
sisys system route [--model <name>] [--format json]           # UDMR 路由决策查询
sisys system health [--format json|table|pretty]              # 健康检查
sisys system config show <key>                                # 配置项查看
sisys system audit query [--tenant <id>] [--time-range <s:e>] # 审计日志查询
```

#### 4.3.8 配置管理（sisys config）

```bash
sisys config get <key> [--format json|yaml|raw]              # 获取配置
sisys config set <key> <value> [--scope user|project|system] # 设置配置
sisys config list [--scope <scope>] [--format json|yaml]     # 列出配置
sisys config env [--format json|table]                       # 环境变量查看
sisys config isolate [--tenant <id>] [--mode soft|hard]      # 多租户隔离切换
sisys config reload                                           # 热更新配置
```

### 4.4 Agent 专用参数规范

所有命令必须支持以下 Agent 模式参数：

| 参数 | 描述 | 默认值 | Agent 模式必填 | Agent 模式用途 |
|------|------|-------|--------------|--------------|
| `--yes` | 跳过交互式确认 | false | **是** | Agent 调用时必须设 true，否则拒绝执行 |
| `--cost-budget <amount>` | 成本预算上限（**硬上限**，见 §4.4.1） | $1.00 USD/任务 | **是** | Agent 调用时必须显式设置，未设置 → 拒绝执行 |
| `--dry-run` | 预览不执行 | false | 否 | 测试/调试 |
| `--mock` | 使用模拟数据 | false | 否 | 开发调试 |
| `--session <id>` | 会话命名空间 | 自动生成 UUID | 否 | 状态持久化/审计追踪 |
| `--timeout <seconds>` | 执行超时 | 300 | 否 | 防止无限等待 |

#### 4.4.1 `--cost-budget` 硬上限语义（MVP 强制）

```text
# 默认值：$1.00 USD/任务（项目硬编码，见 config/cost_defaults.yaml）
# Agent 模式：必须显式设置（--cost-budget 缺失 → 拒绝执行并提示）

# 触发规则（成本三级熔断）：
# Level 1 (80% of budget): soft warn + 输出 warning 但继续执行
# Level 2 (100% of budget): hard stop + 中断当前 LLM 调用 + 返回部分结果 + 发布 CostBudgetExceeded 事件
# Level 3 (200% of budget): 触发 §16.1 监控告警 + 写入异常审计日志（不可变存储）
# 注：MVP 不实现 auto-degrade（V1+ 可选增强：自动切换 lite 模型 + 续跑）
```

### 4.5 输出格式规范

所有命令必须支持以下输出格式：

| 格式 | 用途 | 适用场景 |
|------|------|---------|
| `--format json` | 结构化输出 | Agent 消费、pipe 给 jq |
| `--format table` | 表格输出 | 人类阅读 |
| `--format pretty` | 美化输出 | 终端展示 |
| `--format ndjson` | 流式 JSON | 大数据量处理 |
| `--format csv` | CSV 输出 | 数据导出 |

---

## 5. Skills 渐进式加载机制（⚠️ 设计示意，未实现 Epic 5）

### 5.1 三级渐进式披露

**对标 Anthropic Claude Code Skills Hub-and-Spoke 范式：**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Skills 三级渐进式披露（Anthropic Hub-and-Spoke）│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: 元数据（Metadata）—— YAML frontmatter 聚合            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • 位置: TOOLS.md（Skill 元数据清单）                     │   │
│  │  • 大小: MVP ≤1.2K tokens / V1 ≤800 / V2 ≤500            │   │
│  │  • 加载时机: Agent 启动时全量预加载到系统提示              │   │
│  │  • 缓存: Redis Hash `skill:l1:metadata`，TTL 300s         │   │
│  │  • 内容: name + description + when + tags + version +     │   │
│  │          allowed_agents + applicable_blm/bem_stages +     │   │
│  │          negative_triggers + accuracy + false_positive_rate │   │
│  │  • 用途: 模型基于 description 自主判断（Anthropic 风格）   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼ 触发匹配（LLM 自决）                  │
│  Level 2: SKILL.md 主体（Hub-and-Spoke 路由表）                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • 位置: skills/<tool-id>/SKILL.md                       │   │
│  │  • 大小: 路由表 ≤30 行（强制）/ 总长 ≤500 行（含示例）     │   │
│  │  • 加载时机: 模型判断相关时通过 Read 工具按需加载         │   │
│  │  • 结构: Overview / When to Use / When NOT to Use /       │   │
│  │          Quick Start / Core Workflow / Examples /           │   │
│  │          Gotchas / References                              │   │
│  │  • 详细规范下沉到 references/*.md（Hub-and-Spoke）         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼ 触发调用                              │
│  Level 3: 资源（Scripts/References/Assets）                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • 位置: skills/<tool-id>/{scripts,references,assets}/     │   │
│  │  • 加载时机: 按需链式读取（Anthropic "Hub-and-Spoke" 末梢）│   │
│  │  • 沙箱: DockerSandboxAdapter 执行 scripts/                │   │
│  │  • 策略: SkillSandboxPolicy（timeout/memory/network/      │   │
│  │          transaction_mode）                              │   │
│  │  • 安全: 路径穿越校验 + iptables 白名单                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.1.1 三级衔接强约束规则（强制）

| 依赖关系 | 强制约束 | 失效后果 |
|---------|---------|---------|
| **L1 → L2** | L2 加载必须先验证 slug 存在且 status=ACTIVE | 加载失败：SkillNotFoundError |
| **L2 → L3** | L3 加载必须在 L2 已加载前提下 | 加载失败：SkillContextMissingError |
| **L3 → L1/L2** | L3 执行结果通过 SkillExecuted 事件回流，更新 L1 元数据 accuracy | 不强制 |

#### 5.1.2 L2 缓存链路（强制）

| 层级 | 缓存位置 | TTL | 失效机制 |
|------|---------|-----|---------|
| L1 (TOOLS.md) | Redis Hash `skill:l1:{version}` | 24h | `SkillMetadataChanged` 事件 → DEL |
| L2 (SKILL.md) | 进程内 LRU（max 23 项） | 同 Session | Session 结束自动释放 |
| L3 (scripts) | 临时文件系统 `/tmp/sisys/skill/{slug}/` | 60min | TTL 过期 + 引用计数=0 |

#### 5.1.3 上下文释放规则（强制）

- **L1**：永不释放（Agent 整个生命周期持有）
- **L2**：Skill 执行完毕后保留 5 分钟（支持短时间内的重复调用），超出后释放
- **L3**：脚本执行完毕后立即释放（沙箱容器销毁）

> ⚠️ **P0-1（架构师视角）**：Hub-and-Spoke 量化 — SKILL.md 路由表必须 ≤30 行，详细规范全部下沉到 references/。这是 Anthropic Claude Code Skills 范式的核心约束，违反将导致上下文爆炸和触发准确率下降。
>
> ⚠️ **P0-4（架构师视角）**：三级衔接强约束 — L1→L2→L3 单向依赖，反向加载会导致脚本上下文缺失。

### 5.2 L1 元数据：TOOLS.md

```markdown
# TOOLS.md - Agent 可用工具清单

## 工具列表

### pestel
- **描述**: 分析政治/经济/社会/技术/环境/法律六大维度对战略的影响
- **触发条件**: 用户提到"宏观环境"、"政策趋势"、"市场洞察-看趋势"、"PESTEL"
- **标签**: [macro, market-insight, external]
- **版本**: 1.0

### swot
- **描述**: 评估内部优势/劣势和外部机会/威胁
- **触发条件**: 用户提到"优劣势"、"SWOT"、"内部能力评估"、"竞争态势"
- **标签**: [strategy, internal-external, competition]
- **版本**: 1.0

### five-forces
- **描述**: 波特五力模型分析行业竞争结构
- **触发条件**: 用户提到"五力"、"行业竞争"、"供应商议价能力"、"进入壁垒"
- **标签**: [competition, industry, structural]
- **版本**: 1.0

... (共 23 种工具，每种约 4-5 行)
```

**设计要点**：
- 整个 TOOLS.md 控制在 **≤1.2K tokens 以内**（MVP 23 工具聚合约 1150 tokens）
- `description` 必须包含明确触发词（借鉴 Claude Code "pushy" 原则）
- 必须包含负向触发条件（"不应在...时使用"）

### 5.3 L2 SOP 主体：SKILL.md

> **⚠️ P0-2（架构师视角）**：SKILL.md 必须严格遵循 Anthropic Hub-and-Spoke 范式：
> 1. **frontmatter 字段强制**（见 §5.3.1 字段规范）
> 2. **路由表 ≤30 行**（强制约束，详见 §5.1 量化）
> 3. **必含章节**：`## When to Use` + `## When NOT to Use` + `## Examples` + `## Gotchas` + `## References`（Anthropic 强制）

#### 5.3.1 SKILL.md frontmatter 字段规范（精减，7 字段标准）

> **修订原则（对标 Anthropic Claude Code Skills）：** 严格区分 **Anthropic 标准字段**（`name` + `description`）与 **sisys 项目扩展字段**（其余 5 个）。原"13 字段标准"过度扩展了硬编码 scaffolding，违反 P5 "Less scaffolding, more model" 原则——本节精减为 7 字段，将角色/阶段/触发词语义合并到 `description` 字段，由 LLM 自主判断。

| 字段 | 类型 | 必填 | 来源 | 约束 | 默认值 |
|------|------|------|------|------|--------|
| **Anthropic 标准字段（2）** ||||||
| `name` | string | ✅ | Anthropic | 1-64 字符，kebab-case，**必须匹配父目录名** | - |
| `description` | string | ✅ | Anthropic | 1-1024 字符，**动词开头 + "Use when..." + "Do not use when..."**（Anthropic 推荐结构，非强制正则） | - |
| **sisys 项目扩展（3）** ||||||
| `version` | string | ✅ | sisys | SemVer 2.0.0（**支持 pre-release** 如 `1.0.0-rc.1`） | "1.0.0" |
| `sop_path` | string | ✅ | sisys | 相对项目根路径（如 `skills/pestel/SKILL.md`） | - |
| `sop_line_count` | int | ✅（CI 自动统计） | sisys | 1-500（含 Examples + Gotchas + References 链接），由 `scripts/check_skill_line_count.py` 自动统计并校验 | - |
| **评测埋点（2，可选）** ||||||
| `accuracy` | object | ❌ | sisys | `{value: 0-1.0, sample_count: int, last_updated: ISO8601}` | `{value: null, sample_count: 0, last_updated: null}` |
| `false_positive_rate` | object | ❌ | sisys | `{value: 0-1.0, sample_count: int, last_updated: ISO8601}` | `{value: null, sample_count: 0, last_updated: null}` |

> **字段精减理由（P5 Less scaffolding）：**
> 1. **`allowed_agents` / `applicable_blm_stages` / `applicable_bem_stages` / `trigger_words` 已删除**：原 4 个字段为硬编码 scaffolding，违反 P5 原则。这 4 类语义全部合并到 `description` 字段：
>    - 角色白名单 → description 中写明 "Use when acting as CEO or CFO"
>    - 阶段适配 → description 中写明 "Use during MARKET_INSIGHT stage"
>    - 触发词 → description 中自然包含触发短语
> 2. **`negative_triggers` 已删除**：负向触发由 SKILL.md 强制章节 `## When NOT to Use` 承载（避免双重负向机制冗余）。
> 3. **`skill_id` / `slug` / `sop_summary` / `model` 已删除**：`skill_id` 由系统生成无需写在 frontmatter；`slug` 与 `name` 同源重复；`sop_summary` 是 `description` 的子集；`model` 与 sisys 多模型路由（UDMR）设计冲突。
> 4. **`sop_line_count` 保留**：作为 CI 校验依据（独立 pre-commit 钩子），不依赖正则约束 description。

> **`description` 字段推荐结构（非强制正则）：**
> ```text
> <动词> <核心功能描述>. Use when <正向触发场景（角色/阶段/任务）>. Do not use when <负向触发场景>.
> ```
> 示例：`Analyze macro-environmental factors (Political, Economic, Social, Technological, Environmental, Legal). Use when evaluating external business environment during MARKET_INSIGHT stage as CEO or CMO. Do not use when performing single-dimension analysis, internal capability evaluation, or industry competitive structure assessment.`
>
> **不强制正则**：仅作为编写建议模板，避免限制作者自然语言表达力。

> **L1 缓存键统一规范**：统一为 `skill:l1:{slug}:{version}`（Hash，TTL 24h，SkillMetadataChanged 事件触发 DEL）。

#### 5.3.2 SKILL.md 完整模板（Hub-and-Spoke，路由表 ≤30 行）

```markdown
---
name: pestel
description: "Analyze macro-environmental factors (Political, Economic, Social, Technological, Environmental, Legal). Use when evaluating external business environment during MARKET_INSIGHT stage as CEO or CMO. Do not use when performing single-dimension analysis, internal capability evaluation, or industry competitive structure assessment."
version: "1.0.0"
sop_path: "skills/pestel/SKILL.md"
---

# PESTEL 宏观环境分析

## Overview
PESTEL 分析工具，评估政治/经济/社会/技术/环境/法律六大外部维度对战略目标的影响。
详细规范见 references/ 目录（SOP、INPUT SCHEMA、FAILURE HANDLING 全部下沉）。

## When to Use
- 用户明确要求"宏观环境分析"、"PESTEL 分析"
- BLM 市场洞察阶段"看趋势"子步骤
- 任务描述包含"政策趋势"、"经济环境"、"社会变化"

## When NOT to Use
- 仅分析单一维度（如只看政策）→ 使用专项分析
- 内部能力评估 → 使用 SWOT
- 行业竞争结构分析 → 使用波特五力

## Quick Start
详见 [references/pestel_quickstart.md](references/pestel_quickstart.md)（≤5 步最小可运行流程）

## Core Workflow
详见 [references/pestel_workflow.md](references/pestel_workflow.md)（L1 强制 / L2 推荐 / L3 可选 SOP）

## SOP

### L1 强制步骤（不可跳过）
1. **读取输入数据**
   ```bash
   sisys document search --query "${target_market}" --top-k 5
   ```
2. **校验数据完整性**
   - 检查 6 个维度是否有数据支撑
   - 数据不足时触发 FR-SR-12 补救机制
3. **执行分析**
   ```bash
   sisys tool run pestel --input input.json --output output.json
   ```
4. **验证输出**
   - 检查输出符合 PESTEL-Analysis-v1 Schema
   - 验证失败重试最多 3 次

### L2 推荐步骤（可跳过）
5. **对比上期结果**
   - 从档案库加载上期 PESTEL 分析
   - 标注新增/消失/变化的因素
6. **生成差异摘要**
   - 输出变化项的置信度评分

### L3 可选步骤
7. **关联其他工具**
   - 如与波特五力结果交叉验证
8. **生成综合洞察**
   - 输出战略建议

## FAILURE HANDLING

| 失败类型 | 处理策略 | 重试次数 | 降级方案 |
|---------|---------|---------|---------|
| 数据不足 | 触发 FR-SR-12 补救 | 1 | 标注"数据缺口" |
| 验证失败 | 重试 + 记录日志 | 3 | 降级为基础分析 |
| 超时 > 30s | 中断执行 | 0 | 返回部分结果 |
| Schema 不匹配 | 报告错误 | 0 | 终止并提示用户 |

## OUTPUT SCHEMA
引用: `schemas/pestel_analysis_v1.json`

## EVIDENCE PACKAGE
- 分析结果 JSON
- 数据源引用列表（文档 ID + 切片 ID + 置信度）
- 成本审计信息（Token 消耗 + 估算 USD）

## Examples

### 示例 1: 新市场进入分析（完整场景）
```yaml
target_market: "东南亚新能源市场"
dimensions: ["political", "economic", "social", "technological"]
data_sources: ["docs/market/sea_energy_2025.pdf"]
time_horizon: "2026-2030"
```

### 示例 2: 政策变化影响评估（最小场景）
```yaml
target_market: "中国市场"
dimensions: ["political", "legal"]
data_sources: ["docs/policy/carbon_tax_2027.txt"]
```

## Gotchas
- ⚠️ **数据不足陷阱**：6 维度必须每个都有数据支撑，否则触发 FR-SR-12 补救机制
- ⚠️ **时间窗口对齐陷阱**：PESTEL 与 BLM Stage 1（差距分析）输出时间必须对齐（≤7 天）
- ⚠️ **维度优先级陷阱**：法律/政策维度优先级 > 经济/社会（合规优先）
- ⚠️ **缓存失效陷阱**：L1 元数据更新后必须发布 `SkillMetadataChanged` 事件

## References
- [references/pestel_quickstart.md](references/pestel_quickstart.md) - 5 步最小流程
- [references/pestel_workflow.md](references/pestel_workflow.md) - L1/L2/L3 SOP 详细
- [references/pestel_input_schema.md](references/pestel_input_schema.md) - JSON Schema
- [references/pestel_failure_handling.md](references/pestel_failure_handling.md) - 失败兜底
- [scripts/analyze.py](scripts/analyze.py) - L3 确定性计算脚本

**设计要点**：
- SKILL.md 控制在 **500 行以内**
- SOP 分三级：L1 强制 / L2 推荐 / L3 可选
- 必须包含 input_examples（1-5 个典型用例）
- 必须包含负向触发条件
- 必须包含失败处理表
```

#### 5.3.3 SKILL.md 强制章节检查清单

实施 SKILL.md 时必须满足：

- [ ] **frontmatter** 完整（7 个字段：5 必填 + 2 可选评测埋点）
- [ ] **Overview** 章节（≤200 字符一段话说明）
- [ ] **When to Use** 章节（≥1 条正向触发条件）
- [ ] **When NOT to Use** 章节（≥1 条负向触发条件）—— **P6 强制**
- [ ] **Quick Start** 章节（≤5 步最小流程）
- [ ] **Core Workflow** 章节（L1 强制 / L2 推荐 / L3 可选）
- [ ] **Examples** 章节（≥1-5 个典型用例）—— **P0-2 新增强制**
- [ ] **Gotchas** 章节（≥3-10 条常见陷阱）—— **P0-2 新增强制**
- [ ] **References** 章节（指向 references/*.md，Hub-and-Spoke 末）
- [ ] **路由表 ≤30 行**（Hub-and-Spoke 强制约束）—— **P0-1 新增量化**
- [ ] **总行数 ≤500 行**（含 Examples + Gotchas + References 链接）
- [ ] **命令式写作**（动词开头，Anthropic 风格）

### 5.4 L3 捆绑资源

```
skills/pestel/
├── SKILL.md              # SOP 主体（< 500 行）
├── scripts/
│   ├── validate_input.py # 输入校验脚本
│   └── analyze.py        # 分析执行脚本（确定性计算）
├── references/
│   ├── pestel_theory.md  # PESTEL 理论参考（按需加载）
│   └── scoring_rules.md  # 评分规则
└── assets/
    └── template.md       # 输出模板
```

### 5.5 Skill 选择器（SkillSelector）—— ⚠️ 设计示意，未实现（Epic 5 Story 5-2）

**关键设计决策（对标 Anthropic Claude Code Skills）：**

> **不实现硬编码关键词/embedding 权重选择器**。原因：
> 1. **违反 P5 原则**（"Less scaffolding, more model"）：硬编码选择器是典型的 scaffolding
> 2. **双重 scaffolding**：关键词权重（40%/60%）+ auto:N 阈值 = 双重不必要复杂度
> 3. **触发准确率依赖 L1 description 质量**，而非算法权重
> 4. **Anthropic Claude Code Skills 范式**：模型基于 description 自主判断（description 即触发器）

**SkillSelector 仅作为辅助查询接口：**

```python
class SkillSelector:
    """
    Skill 辅助查询接口（不是选择器）

    实际 Skill 触发由 Agent LLM 基于 L1 description 自主判断（Anthropic 风格）。
    本接口仅提供基于 BLM/BEM 阶段 + 角色白名单的过滤查询，
    返回候选 Skill 列表供 LLM 二次筛选。
    """

    def __init__(self, repository: SkillRepositoryPort):
        self._repository = repository

    def list_active_skills(self) -> list[Skill]:
        """
        列出所有 ACTIVE 状态的 Skill（不过滤任何角色/阶段字段）。

        实际 Skill 触发由 Agent LLM 基于 L1 description 自主判断（Anthropic 风格）。
        本接口不进行任何硬编码过滤——避免违反 P5 "Less scaffolding, more model"。
        仅返回 ACTIVE 状态 Skill；其他维度的过滤（如角色/阶段）已合并到 description 字段，
        由 LLM 在触发决策时自主完成。

    Returns:
        list[Skill]: 所有 ACTIVE 状态的 Skill 列表（无额外过滤）。
    """
        return [s for s in self._repository.list_all() if s.status == SkillStatus.ACTIVE]
```

**完整 Skill 触发决策树：**

```
1. Agent LLM 接收任务描述
   ↓
2. LLM 基于系统提示中的 L1 TOOLS.md（description 字段含 "Use when..."）自主判断
   ↓
3. LLM 决定调用 1+ 个 Skill（按 description 语义匹配 + 负向触发回避）
   ↓
4. （可选）LLM 调用 SkillSelector.list_active_skills() 获取全量 ACTIVE 列表做参考
   ↓
5. SkillLoader.load_l2_skill(slug) 加载 SKILL.md
   ↓
6. SkillLoader.load_l3_resource(slug, file) 按需加载 scripts/references
   ↓
7. 执行 SOP（结合领域服务）
   ↓
8. 发布 SkillExecuted 事件（埋点：accuracy / false_positive_rate）
```

**对比硬编码选择器（已删除）的优势：**

| 维度 | 硬编码选择器（已废弃） | Anthropic 模型自决 |
|------|-------------------|-------------------|
| 触发准确性 | 依赖权重调参（人工） | 依赖 L1 description 质量（人工写好即可） |
| 维护成本 | 需调参 + 调阈值 | 仅需维护 L1 description |
| 适配新 Skill | 需重新调参 | 仅需补充 L1 description |
| 解释性 | 黑盒分数 | LLM 可解释决策过程 |
| 评测方式 | 准确率 vs 阈值 | description-based A/B 评测 |

> **实施路径：** Epic 5 Story 5-2 SkillSelector 实现 + Story 5-9 验收测试（AC-8 准确率 ≥85% / 误触发率 ≤5%）。

### 5.6 Agent 上下文加载流程

```
Agent 启动
    │
    ▼
┌─────────────────────────────────────┐
│ Step 1: 加载 AGENT.md (< 150 行)    │
│         项目上下文 + 业务域 + 约束    │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 2: 加载 IDENTITY.md + SOUL.md  │
│         身份档案 + 决策风格           │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 3: 加载 TOOLS.md (≤1.2K tokens)│
│         23 种工具元数据清单           │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 4: 接收任务描述                  │
│         task_description             │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 5: LLM 自主判断候选 Skill       │
│        （基于 L1 description + When NOT）│
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 6: 加载匹配 Skill 的 SKILL.md  │
│         完整 SOP（< 500 行）          │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 7: 执行 SOP                    │
│         按需加载 scripts/references  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 8: 输出结果 + 证据包            │
│         释放上下文（为后续任务腾空间） │
└─────────────────────────────────────┘
```

---

## 6. MCP 外部生态接口

### 6.1 定位与启用时机

| 版本 | MCP 角色 | 启用场景 | 理由 |
|------|---------|---------|------|
| **MVP** | ❌ 不启用 | - | 内部走 CLI + Skills，100% 覆盖 |
| **V1** | ❌ 不启用 | - | 多 Agent 协作走 SAP 协议 |
| **V2+** | ✅ 可选启用 | 外部 Agent 生态集成 | 企业级统一权限管控 |
| **V3+** | ✅ 建议启用 | 跨系统工具平台对接 | 与用友/金蝶/华为云集成 |

### 6.2 MCP Registry 设计

```yaml
# mcp/registry.yaml - MCP 工具注册表
tools:
  - tool_id: "pestel"
    name: "PESTEL Macro Environment Analysis"
    description: "Analyze political, economic, social, technological, environmental, and legal factors"
    version: "1.0.0"
    input_schema: "schemas/pestel_input_v1.json"
    output_schema: "schemas/pestel_output_v1.json"
    reliability_score: 0.95  # 历史成功率
    avg_latency_ms: 2500
    avg_cost_usd: 0.05
    tags: ["strategy", "macro-analysis", "external"]

  - tool_id: "swot"
    name: "SWOT Analysis"
    description: "Evaluate internal strengths/weaknesses and external opportunities/threats"
    version: "1.0.0"
    input_schema: "schemas/swot_input_v1.json"
    output_schema: "schemas/swot_output_v1.json"
    reliability_score: 0.97
    avg_latency_ms: 2000
    avg_cost_usd: 0.04
    tags: ["strategy", "internal-external"]

  # ... 共 23 种工具
```

### 6.3 MCP Server 实现 —— ⚠️ MVP 不启用（MVP 代码量 = 0，P4 原则）

> **重要声明（与 §5.1 一致）：** MVP 阶段 MCP 代码量必须为 0（P4 原则）。完整 MCP Server 实现迁移至 V1+ 启用阶段（MCP 规范尚未稳定，过早绑定有架构漂移风险）。
>
> 本节仅作为 V1/V2+ 的**设计参考**（不进入 MVP 实现）。

```text
# === 以下示例仅作 V1+ 设计参考，MVP 不会提交此实现 ===

# mcp/server.py - MCP 服务器实现（设计示意）
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("sisys-toolbox")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """暴露 sisys 工具箱能力"""
    # 注：V1+ 才实现，MVP 阶段此文件不应存在
    ...

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理外部 Agent 的工具调用"""
    # 注：V1+ 才实现，MVP 阶段此文件不应存在
    ...
```

**MVP 阶段约束验证（pre-commit hook）：**

```bash
# 此 grep 在 MVP 阶段必须零输出
grep -rn "from mcp\|import mcp" src/ 2>/dev/null
# 预期输出：（空）

# pyproject.toml 中 mcp 依赖声明应被删除
grep -rn "^mcp" pyproject.toml 2>/dev/null
# 预期输出：（空）
```

> **详见 §5.1** 启用时机表：V1 启用 Read-only MCP 工具桥（预计 2027Q2）；V2 启用 Write MCP 工具桥（预计 2028Q1）。

### 6.4 MCP 与 CLI 的关系

```
同一个工具实现，两种暴露方式：

┌──────────────────────────────────────────────────────┐
│              ToolService（内部实现）                   │
│  • pestel_tool.py                                    │
│  • swot_tool.py                                      │
│  ...                                                 │
└──────────────┬───────────────────────┬───────────────┘
               │                       │
               ▼                       ▼
        ┌──────────────┐       ┌──────────────┐
        │  CLI 适配器   │       │  MCP 适配器   │
        │  sisys tool   │       │  MCP Server  │
        │  run pestel   │       │  (V2+ 启用)   │
        └──────────────┘       └──────────────┘
               │                       │
               ▼                       ▼
        ┌──────────────┐       ┌──────────────┐
        │  Agent 内部   │       │  外部 Agent   │
        │  Skills 调用  │       │  MCP 协议调用  │
        └──────────────┘       └──────────────┘

关键：CLI 和 MCP 共享同一 ToolService 实现，通过适配器模式解耦
```

---

## 7. sisys Agent 间通信协议（SAP - Sysys Agent Protocol）

### 7.1 协议定位

SAP（sisys Agent Protocol）是 sisys 内部 Agent 间的专用通信协议。

**设计原则：内部 Agent 通信是 sisys 的核心差异化能力，需要领域特定设计，不依赖外部标准协议。**

| 协议 | 用途 | 范围 |
|------|------|------|
| **SAP** | sisys 内部 Agent 辩论/裁决/协作 | 系统内部 |
| **CLI** | 用户/外部系统与 sisys 交互 | 外部→内部 |
| **Skills** | Agent 内部操作手册 | Agent 内部 |

**SAP 不可替代的原因：**
- CLI 是单向命令，不支持多 Agent 协商
- Skills 是单 Agent 的操作手册，不包含跨 Agent 交互逻辑
- 外部 Agent 协议（如 Google A2A）面向跨系统任务委派，不覆盖 sisys 的多视角辩论、SYS 裁决、公共黑板等核心场景

### 7.2 为什么 CLI+Skills 不可替代？

**核心结论：SAP 有 CLI+Skills 无法替代的独特价值，但 MVP 阶段不应实现完整协议。**

#### 通信模式的本质差异

| 维度 | CLI | Skills | SAP |
|------|-----|--------|-----|
| **通信方向** | 单向：用户→系统 | 内部：Agent→领域服务 | **双向**：Agent↔Agent |
| **通信性质** | 命令式："去做什么" | 操作手册："怎么做" | **协商式**："你怎么看" |
| **决策权** | 用户决策 | Agent 自主执行 | **多 Agent 协商** |
| **信息流** | 请求→响应 | 加载 SOP→执行 | **辩论/仲裁/共识构建** |
| **失败处理** | 重试/报错 | SOP 兜底策略 | **裁决/降级/用户介入** |

#### SAP 的三大不可替代场景

**场景 1：多 Agent 辩论（不可替代）**

```
CEO Agent: "我认为应该进入东南亚市场"
     │
     │ SAP: DEBATE 消息
     ▼
CFO Agent: "财务分析显示风险过高，建议暂缓"
     │
     │ SAP: RESPONSE + 置信度
     ▼
CTO Agent: "技术可行性没问题，但供应链依赖本地伙伴"
     │
     │ SAP: BROADCAST 到公共黑板
     ▼
SYS Agent: "三视角分歧较大，启动裁决程序..."
```

**为什么 CLI+Skills 做不到：**
- CLI 是单向命令，不支持多 Agent 并行协商
- Skills 是单 Agent 的操作手册，不包含多视角交互逻辑
- 需要**消息类型**（DEBATE/RESPONSE/BROADCAST）、**置信度交换**、**公共黑板可见性**、**裁决状态机**——SAP 独有机制

**场景 2：联合分析组（EIP L2 协作态）**

```
跨领域问题触发 EIP 降级：L4 硬隔离 → L2 协作态

CEO Agent ──→ 公共黑板 ←── CFO Agent
   │              │              │
   │  中间结论     │  中间结论     │
   │  (置信度 0.8) │  (置信度 0.7) │
   │              │              │
   └──────────────┼──────────────┘
                  ▼
          联合输出 + 各 Agent 独立签名（保持责任可追溯）
```

**为什么 CLI+Skills 做不到：**
- CLI 是同步请求-响应，不支持异步协作状态同步
- Skills 是单 Agent 的 SOP，不包含跨 Agent 中间结论交换
- 需要**隔离等级动态切换**、**公共黑板 MVCC**、**协作状态同步**——SAP 独有

**场景 3：SYS Agent 裁决**

```
CEO vs CFO 分歧 → SYS Agent 介入

SYS Agent:
  1. 收集双方论据（SAP REQUEST）
  2. 五维评分（事实 35% + 逻辑 25% + 风险 20% + 资源 15% + 战略 5%）
  3. 置信度判定：≥0.6 自动裁决 / 0.4-0.6 建议复核 / <0.4 强制升级
  4. 未达成一致 → 生成三套方案（保守/激进/AI 融合）+ 强制暂停 5 分钟请求用户介入
```

#### 反模式警告：不要用 CLI 模拟 SAP

```python
# ❌ 反模式：用 CLI 模拟 SAP（违反 DDD 分层 + 职责分离）
class CEOSkill:
    async def debate_with_cfo(self, topic: str):
        result = await cli_run("sisys agent run cfo --task", topic)  # 应用层调用接口层
        if self.analysis != result:
            return self.arbitrate(self.analysis, result)  # CEO 自己做裁决（违反 SYS 职责）

# ✅ 正确：通过 SAP 协议协作
class CEOSkill:
    async def debate_with_cfo(self, topic: str):
        msg = SAPMessage(
            sender_id="ceo", receiver_id="cfo",
            message_type=MessageType.DEBATE,
            priority=MessagePriority.HIGH,
            subject=topic,
            content={"analysis": self.analysis},
            requires_response=True,
            correlation_id=uuid4()
        )
        await self.sap_bus.send(msg)
        response = await self.sap_bus.wait_for_response(msg.correlation_id)
        if self.conflict_detected(response):
            await self.sap_bus.send(SAPMessage(
                sender_id="ceo", receiver_id="sys",
                message_type=MessageType.REQUEST,
                subject="arbitration_required",
                content={"ceo_view": self.analysis, "cfo_view": response.content}
            ))
```

### 7.3 SAP 启用时机

| 版本 | SAP 角色 | 交付物 | 理由 |
|------|---------|-------|------|
| **MVP** | ⚠️ 仅定义 Schema | SAPMessage Pydantic 模型 + 消息类型枚举 | CEO 单 Agent 场景不需要 SAP，但需预留扩展点 |
| **V1** | ✅ 实现核心功能 | 辩论机制 + SYS 裁决 + 公共黑板 | 多 Agent 协作核心差异化能力 |
| **V2+** | ✅ 完整实现 | EIP 协作态 + 隔离切换 + mTLS | 企业级多 Agent 协作必需 |

### 7.4 消息格式定义

```python
class MessageType(str, Enum):
    REQUEST = "request"           # 请求协助
    RESPONSE = "response"         # 响应请求
    NOTIFICATION = "notification" # 通知事件
    BROADCAST = "broadcast"       # 广播到公共黑板
    DEBATE = "debate"             # 辩论消息

class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SAPMessage(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID          # 会话 ID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

# 顶部需导入：
# from datetime import UTC, datetime
    sender_id: str                 # 发送 Agent ID
    receiver_id: str               # 接收 Agent ID，广播时为"broadcast"
    message_type: MessageType
    priority: MessagePriority = MessagePriority.NORMAL
    subject: str                   # 消息主题
    content: Dict[str, Any]        # 消息内容
    context: Dict[str, Any] = Field(default_factory=dict)  # 上下文信息
    requires_response: bool = False
    timeout_seconds: int = 300
    correlation_id: UUID = None    # 关联请求 ID
    isolation_level: str = "L4"    # 隔离等级
    blackboard_visible: bool = False  # 是否对公共黑板可见
```

### 7.5 SAP 通信流程

```
CEO Agent                    CFO Agent
    │                           │
    │─── REQUEST (分析财务影响) ──→│
    │    priority: HIGH          │
    │    timeout: 300s           │
    │                           │
    │                    ┌──────┴───────┐
    │                    │ CFO 加载     │
    │                    │ 财务分析 Skill│
    │                    └──────┬───────┘
    │                           │
    │←── RESPONSE (财务分析报告)──│
    │    confidence: 0.92        │
    │    evidence_package: {...} │
    │                           │
```

### 7.6 安全要求

| 安全机制 | 描述 | 实现版本 |
|---------|------|---------|
| **消息签名** | 防止消息篡改 | MVP |
| **审计日志** | 所有 SAP 通信记录写入 IsolationSwitchLog | MVP |
| **RBAC + 隔离等级** | 跨 Agent 数据访问需授权 | V1 |
| **mTLS 加密** | Agent 间双向 TLS 认证 | V2 |

---

## 8. REST API 集成接口

### 8.1 API 总体设计

```
Base URL: /api/v1
```

### 8.2 完整业务端点清单

#### 8.2.1 文档管理

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/documents` | POST | 单个文档上传 | P0 |
| `/documents/batch` | POST | **批量上传 100 个 BP/报告**（异步任务，返回 `job_id`） | **P0** |
| `/documents/batch/{job_id}` | GET | 批量任务进度查询（`processed`/`failed`/`total`） | **P0** |
| `/documents/batch/{job_id}/results` | GET | 批量任务结果明细 | **P0** |
| `/documents/batch/{job_id}/webhook` | POST | 批量任务完成回调 URL 注册 | P1 |
| `/documents/batch/{job_id}/retry` | POST | 批量任务失败重试 | P1 |
| `/documents/{id}` | GET | 查询文档元数据 | P0 |
| `/documents/{id}/parse` | POST | 触发文档解析 | P0 |
| `/documents/{id}/versions` | GET | 版本历史 | P1 |
| `/documents/{id}/trace` | GET | **高保真溯源（Bounding Box 坐标）** | **P0** |

> **异步任务契约（避免 P95>1s 告警）：** 同步端点仅支持单文档，批量强制走异步任务；任务状态查询、结果下载、回调注册、重试端点配套提供，避免客户端长轮询。

##### 8.2.1.1 异步任务契约示例

```yaml
# POST /documents/batch 响应（202 Accepted）
HTTP/1.1 202 Accepted
Location: /api/v1/documents/batch/{job_id}
{
  "job_id": "uuid",
  "status": "queued",
  "total": 100,
  "estimated_completion_at": "ISO8601"
}

# GET /documents/batch/{job_id} 响应
{
  "job_id": "uuid",
  "status": "running|completed|failed|partial",
  "total": 100,
  "processed": 73,
  "failed": 2,
  "progress_pct": 73.0,
  "started_at": "ISO8601",
  "completed_at": "ISO8601|null"
}
```

#### 8.2.2 工具执行

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/tools/{id}/execute` | POST | 执行单个战略工具 | P0 |
| `/tools/{id}/schema` | GET | 查看工具输入/输出 Schema | P0 |
| `/tool-chains/{id}/execute` | POST | 执行工具链（DAG 编排） | P1 |

#### 8.2.3 Agent 协作

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/agents/{role}/run` | POST | 运行指定角色 Agent | P0 |
| `/agents/{role}/status` | GET | 查询 Agent 执行状态 | P0 |
| `/agents/arbitrate` | POST | SYS Agent 裁决 | P1 |

#### 8.2.4 财务量化分析（P0 新增）

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/financial/analyze` | POST | **财务量化分析（NPV/IRR/现金流）** | **P0** |
| `/financial/sensitivity` | POST | **敏感性分析（单变量/多变量龙卷风图）** | **P0** |

#### 8.2.5 战略规划

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/plans/generate` | POST | 生成 SP/BP 规划 | P0 |
| `/plans/{id}` | GET | 查询规划详情 | P0 |
| `/plans/{id}/compare` | GET | **情景对比（3 方案并排对比）** | **P0** |
| `/plans/{id}/export` | POST | 导出规划（PDF/Markdown/JSON） | P0 |

#### 8.2.6 Checkpoint 管理

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/checkpoints` | GET | 查询 Checkpoint 列表 | P0 |
| `/checkpoints/{id}` | GET | 查询 Checkpoint 详情 | P0 |
| `/checkpoints/{id}/recover` | POST | 恢复 Checkpoint（Replay/Override） | P0 |

#### 8.2.7 战略档案

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/archive/query` | GET | 档案查询 | P0 |
| `/archive/timeline` | GET | 时间轴演进 | P1 |
| `/archive/diff` | GET | 分支差异对比 | P1 |

#### 8.2.8 报告生成（P1 新增）

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/reports/whitelabel` | POST | **白标品牌定制（Logo/配色/字体）** | **P1** |
| `/reports/regulatory` | POST | **监管报告导出（银保监会 1104/EAST）** | **P1** |

#### 8.2.9 风险可视化（P1 新增）

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/risk/heatmap` | GET | **风险热力图（高管视图核心）** | **P1** |

#### 8.2.10 系统管理

| 端点 | 方法 | 用户场景 | 优先级 |
|------|------|---------|-------|
| `/auth/login` | POST | 用户登录 | P0 |
| `/system/health` | GET | 健康检查 | P0 |
| `/system/metrics` | GET | 监控指标查询 | P0 |

### 8.3 API Gateway 要求

| 功能 | 实现 | 要求 |
|------|------|------|
| **统一认证** | OAuth 2.1 + JWT | 所有请求必须认证 |
| **限流** | 令牌桶算法 | 按用户/角色限流 |
| **路由** | 基于路径/方法/角色 | 精细路由控制 |
| **安全** | 请求验证 + 注入检测 | 防止 SQL/XSS 注入 |

---

## 9. LLM 接入协议

### 9.1 统一请求格式

```python
class LLMRequest(BaseModel):
    request_id: UUID
    model: str                     # 路由决定的模型
    messages: List[Message]        # 标准消息格式
    temperature: float = 0.7       # 控制创造性
    max_tokens: int = 4096         # 预算控制
    response_format: Dict          # 期望的输出格式（JSON Schema）
    tools: Optional[List[Tool]]    # 可用工具列表（Function Calling）
    metadata: Dict                 # 追踪用（session_id/task_id/cost_budget）
```

### 9.2 统一响应格式

```python
class LLMResponse(BaseModel):
    request_id: UUID
    content: str                   # 生成内容
    usage: UsageInfo              # Token 消耗
    finish_reason: str            # 完成原因
    cost: Decimal                 # 本次调用成本
    latency_ms: int               # 延迟
    model_used: str               # 实际使用的模型
    trace_id: str                 # 分布式追踪 ID
```

### 9.3 UDMR 路由集成

```
LLM 请求
    │
    ▼
┌─────────────────────────────────────┐
│ L1: 合规性网关                        │
│ • 敏感数据检查                        │
│ • 数据驻留限制                        │
│ • 白名单校验                          │
└──────────────────┬──────────────────┘
                   │ 通过
                   ▼
┌─────────────────────────────────────┐
│ L2: 任务复杂度评估                    │
│ • 语义匹配度 (35%)                   │
│ • 历史成功率 (30%)                   │
│ • 成本效率 (20%)                     │
│ • 任务复杂度 (15%)                   │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ L3: 路由决策执行                      │
│ • 本地质量 ≥ 0.70 → 本地              │
│ • 云端优势 > 0.15 → 云端              │
│ • 否则 → 本地优先                     │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ 调用选定模型                          │
│ • 本地: Ollama + Qwen2.5             │
│ • 云端: Qwen3.5-Plus/Claude/GPT-4   │
└──────────────────┬──────────────────┘
                   │
                   ▼
            返回 LLMResponse
```

---

## 10. 工具间调用协议

### 10.1 内部调用格式（不走 MCP）

```python
class ToolCallRequest(BaseModel):
    call_id: UUID
    tool_id: str                  # 工具唯一标识
    input_data: Dict              # 符合 Pydantic V2 Schema
    session_id: UUID              # 会话上下文
    caller_tool_id: Optional[str] # 调用方（用于溯源）
    cost_budget: Decimal          # 成本预算
    timeout_seconds: int = 300    # 超时时间

class ToolCallResponse(BaseModel):
    call_id: UUID
    output_data: Dict             # 符合 Pydantic V2 Schema
    evidence_package: Dict        # 证据包
    cost: Decimal                 # 实际成本
    execution_time_ms: int        # 执行延迟
    validation_result: Dict       # 验证结果
    caller_trace: List[str]       # 调用链溯源
```

### 10.2 DAG 编排执行

```python
class ToolChainExecutor:
    """
    工具链编排执行器

    支持 DAG 有向无环图定义，按拓扑顺序调度子任务
    """

    async def execute_chain(self, chain_id: str, input_data: Dict) -> Dict:
        # 1. 加载 DAG 定义
        dag = load_tool_chain_dag(chain_id)

        # 2. 有效性校验（检测循环依赖）
        if not dag.is_valid():
            raise InvalidDAGException("Invalid DAG: circular dependency detected")

# 顶部需导入：
# from sisys.domain.exceptions import InvalidDAGException  # 走 sisys 统一异常体系（CLAUDE.md §5 红线）

        # 3. 按拓扑顺序执行
        results = {}
        for node in dag.topological_sort():
            # 4. 收集上游输出作为输入
            node_input = self._collect_upstream_results(node, results)

            # 5. 并行执行无依赖子任务
            if dag.has_parallel_nodes(node):
                parallel_results = await asyncio.gather(
                    *[self._execute_node(n, node_input) for n in dag.get_parallel_nodes(node)]
                )
                results.update(parallel_results)
            else:
                results[node] = await self._execute_node(node, node_input)

        # 6. 聚合最终结果
        return self._aggregate_results(results)
```

---

## 11. Prompt 模板协议

### 11.1 Prompt 加载流程

```
Agent 构建 Prompt
    │
    ▼
┌─────────────────────────────────────┐
│ Step 1: SYSTEM_PROMPT               │
│         从 IDENTITY.md 加载          │
│         （固定系统提示）               │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 2: TASK_PROMPT                 │
│         从模板库按任务类型动态选择     │
│         （如 "market-insight.md"）    │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 3: CONTEXT_PROMPT              │
│         从记忆/RAG 检索加载           │
│         （检索结果摘要）               │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 4: TOOLS_PROMPT                │
│         从 TOOLS.md 加载             │
│         （可用工具列表）               │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Step 5: OUTPUT_SCHEMA               │
│         从 Pydantic Schema 加载      │
│         （强制结构化输出）             │
└──────────────────┬──────────────────┘
                   │
                   ▼
           组合为完整 Prompt 发送 LLM
```

### 11.2 Prompt 模板结构

```markdown
---
name: market-insight
version: "1.0"
applicable_stages: ["market-insight", "strategic-analysis"]
---

# 市场洞察任务模板

## 角色设定
你是 {{agent_role}}，负责执行市场洞察分析。

## 任务描述
{{task_description}}

## 输入数据
{{input_data_summary}}

## 执行要求
1. 使用 BLM 市场洞察六子步骤
2. 每个步骤必须有数据支撑
3. 输出必须符合 MarketInsightOutput Schema

## 约束条件
- 不得编造数据
- 置信度 < 0.6 时必须标注"数据不足"
- 必须引用原始数据源

## 输出格式
```json
{{output_schema}}
```

### 11.3 Prompt 版本管理

| 要求 | 描述 |
|------|------|
| **版本绑定** | 每个 Prompt 模板与系统版本绑定 |
| **回滚支持** | 保留最近 10 个版本，支持一键回滚 |
| **变更追踪** | 记录修改人、时间戳、变更摘要 |
| **Strat-Bench 验证** | 每次修改必须通过结构化差异校验（通过率 ≥ 90%） |

---

## 14. 接口版本管理与兼容性

### 14.1 版本策略

| 接口 | 版本格式 | 兼容性要求 |
|------|---------|-----------|
| **CLI** | `sisys v1.0.0` | 向后兼容 2 个主版本 |
| **REST API** | `/api/v1/` | URL 路径包含版本号 |
| **Skills** | `SKILL.md` frontmatter `version` | 向后兼容 1 个主版本 |
| **MCP** | `registry.yaml` version | 向后兼容 1-2 个版本 |
| **SAP** | 消息头 `protocol_version` | 向后兼容 1 个版本 |
| **LLM Adapter** | LiteLLM 版本 | 跟随 LiteLLM 升级 |

### 14.2 破坏性变更流程

```
提出变更 → 影响评估 → 设计兼容层 → 测试验证 → 发布迁移指南 → 部署
   │           │           │           │           │           │
   ▼           ▼           ▼           ▼           ▼           ▼
  RFC 文档   FR/NFR 影响  兼容适配器  契约测试   用户通知    灰度发布
```

### 14.3 契约测试

| 契约类型 | 工具 | 验证内容 | 通过率要求 |
|---------|------|---------|-----------|
| **CLI 契约** | typer 测试框架 | 命令解析 + 输出格式 | 100% |
| **API 契约** | Schemathesis | OpenAPI 3.1 验证 | 100% |
| **Skill 契约** | jsonschema | SKILL.md Schema 验证 | 100% |
| **MCP 契约** | jsonschema | 工具输入/输出 Schema | 100% |
| **SAP 契约** | Pydantic 模型 | 消息格式验证 | 100% |
| **事件契约** | Pydantic 模型 | 领域事件 Schema | 100% |

---

## 15. 安全与权限控制

### 15.1 安全分层

```
┌─────────────────────────────────────────────────────────────┐
│                    安全分层架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第一层：隔离                                                │
│  • Prompt 隔离（每个 Agent 独立系统提示）                    │
│  • 工具隔离（RBAC 最小权限）                                 │
│  • 数据隔离（多租户 Schema per Tenant）                      │
│                                                             │
│  第二层：执行                                                │
│  • Docker 沙箱（代码执行隔离）                               │
│  • 网络白名单（仅允许可信 API）                              │
│  • 资源限制（CPU/内存/超时）                                 │
│                                                             │
│  第三层：检测                                                │
│  • ShieldCortex 提示注入检测                                 │
│  • 视角越界检测（跨角色关键词频率 > 5%）                     │
│  • 幻觉累积检测                                              │
│                                                             │
│  第四层：审计                                                │
│  • 不可变存储（WORM）                                       │
│  • 完整操作日志                                             │
│  • 7 年保留期限（SOX 合规）                                  │
│                                                             │
│  第五层：熔断                                                │
│  • 辩论过热保护                                             │
│  • 成本三级熔断                                             │
│  • 批量熔断（防止 Agent 失控）                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 15.2 CLI 安全参数

| 参数 | 描述 | 安全级别 |
|------|------|---------|
| `--dry-run` | 预览不执行 | 所有有副作用的命令必须支持 |
| `--confirm` | 需要确认 | 删除/覆盖操作必须要求 |
| `--cost-budget` | 成本上限 | Agent 模式必须设置 |
| `--timeout` | 超时时间 | 防止无限等待 |

### 15.3 Skill 权限控制

```yaml
# SKILL.md 权限声明
allowed_tools:
  - "pestel"
  - "document_search"
data_access:
  read: ["docs/*", "archive/*"]
  write: ["output/*", "evidence/*"]
cost_limit:
  max_usd_per_call: 0.10
  max_tokens_per_call: 50000
```

---

## 16. 可观测性与监控

### 16.1 统一追踪 ID

```python
# 每个请求携带 trace_id，贯穿所有接口层
class TraceContext:
    trace_id: str          # 分布式追踪 ID
    span_id: str           # 当前 Span ID
    parent_span_id: str    # 父 Span ID
    session_id: str        # 会话 ID
    task_id: str           # 任务 ID
```

### 16.2 关键监控指标

| 指标类别 | 指标 | 告警阈值 | 测量方式 |
|---------|------|---------|---------|
| **性能** | CLI 命令响应延迟 | P95 > 1s | OpenTelemetry |
| **性能** | Skill 加载延迟 | P95 > 500ms | 日志分析 |
| **性能** | LLM 调用延迟 | P95 > 10s | LiteLLM metrics |
| **质量** | Skill 触发准确率 | < 85% | 测试集验证 |
| **质量** | 工具调用准确率 | < 90% | 日志分析 |
| **成本** | 单次任务成本 | > 预算 200% | 成本聚合 |
| **安全** | 提示注入检测 | 准确率 < 95% | ShieldCortex |
| **可用性** | CLI 可用性 | < 99% | 健康检查 |

### 16.3 OpenTelemetry 集成

```python
from opentelemetry import trace, metrics

# 所有接口调用自动创建 Span
@tracer.start_as_current_span("sisys.tool.execute")
async def execute_tool(tool_id: str, input_data: Dict):
    span.set_attribute("tool.id", tool_id)
    span.set_attribute("tool.input_hash", hash(input_data))

    result = await tool_service.execute(tool_id, input_data)

    span.set_attribute("tool.output_size", len(result))
    span.set_attribute("tool.cost_usd", result.cost)
    return result
```

---

## 12. 事件监听适配器规范

### 12.1 设计原则

**or.md 1.4.1(3) 原文：**
> 事件监听适配器：支持 RabbitMQ 事件消费者，监听领域事件（文档处理完成、工具执行完成、AGENT 决策完成、隔离等级切换、Checkpoint 恢复、路由决策），触发下游应用层用例

**关键职责：**
- 监听 11 种领域事件（MVP 10 种 + MemoryChanged 补充，与 architecture.md §10.4 对齐；事件总数 26 = MVP 10 + V1/V2 16 扩展）
- 转换为 ApplicationCommand 触发下游用例
- 保证事件处理幂等性，支持重放与失败重试

### 12.2 事件监听架构

```
┌─────────────────────────────────────────────────────────────┐
│                    事件监听适配器架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RabbitMQ Queue                    Event Listener           │
│  ┌──────────────┐                  ┌─────────────────────┐  │
│  │ domain_events│ ──→ consume ──→ │ 1. 反序列化事件      │  │
│  │ (持久化)     │                  │ 2. 幂等性检查        │  │
│  └──────────────┘                  │ 3. 转换为 Command    │  │
│                                    │ 4. 触发下游用例      │  │
│  Redis Pub/Sub                     │ 5. 确认 ACK/NACK     │  │
│  ┌──────────────┐                  └─────────┬───────────┘  │
│  │ real_time    │ ──→ subscribe ──→           │              │
│  │ (实时通知)   │                             │              │
│  └──────────────┘                             │              │
│                                               │              │
│                                  ┌────────────▼───────────┐  │
│                                  │ 下游用例处理            │  │
│                                  │ • CostAggregation      │  │
│                                  │ • SkillEvolution       │  │
│                                  │ • StrategicDeviation   │  │
│                                  │ • BlackboardUpdate     │  │
│                                  └────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 12.3 11 种领域事件监听映射（MVP 10 + MemoryChanged）

| 领域事件 | 监听器 | 触发的下游用例 | or.md 事件流转 |
|---------|--------|---------------|---------------|
| DocumentProcessed | DocumentProcessedListener | 实体抽取用例、图谱构建用例、索引构建用例 | [1] 文档处理事件流转 |
| ToolExecuted | ToolExecutedListener | 成本聚合用例、技能演进用例、Agent 决策用例 | [2] 战略分析事件流转 |
| AgentDecided | AgentDecidedListener | SYS AGENT 仲裁用例、公共黑板更新用例、审计日志用例 | [3] Agent 协作事件流转 |
| CheckpointReached | CheckpointReachedListener | 用户反馈用例、状态持久化用例 | [5] 规划生成事件流转 |
| CorrectionApproved | CorrectionApprovedListener | 自动固化用例、版本注册用例、演进日志用例 | [8] 修正审批事件流转 |
| StrategicDeviationWarning | DeviationWarningListener | 相关 Agent 响应用例、偏差分析报告用例 | - |
| HeartbeatTriggered | HeartbeatListener | 周期性任务检查用例、偏差预警检查用例、成本预算校验用例 | - |
| IsolationLevelSwitched | IsolationSwitchedListener | 公共黑板权限更新用例、协作状态同步用例 | [4] 隔离切换事件流转 |
| CheckpointRecovered | CheckpointRecoveredListener | 战略档案库版本更新用例、分支管理用例 | [6] Checkpoint 恢复事件流转 |
| RoutingDecided | RoutingDecidedListener | 路由决策日志存储用例、成本监控用例 | [7] 路由决策事件流转 |

### 12.4 事件处理幂等性保证

```python
class EventListener:
    """
    事件监听器基类

    关键设计：保证幂等性，支持事件重放与失败重试
    """

    async def handle_event(self, event: DomainEvent):
        # 1. 幂等性检查（基于 event_id）
        if await self.is_event_processed(event.event_id):
            return  # 已处理，跳过

        # 2. 转换为 ApplicationCommand
        command = self.event_to_command(event)

        # 3. 触发下游用例
        try:
            result = await self.use_case.execute(command)
        except Exception as e:
            # 4. 失败处理：NACK + 重试
            await self.handle_failure(event, e)
            raise

        # 5. 标记已处理 + ACK
        await self.mark_event_processed(event.event_id)
        await self.acknowledge(event)

        return result

    async def is_event_processed(self, event_id: str) -> bool:
        """检查事件是否已处理（Redis 缓存）"""
        return await redis.exists(f"processed_event:{event_id}")

    async def mark_event_processed(self, event_id: str):
        """标记事件已处理（TTL 7 天，覆盖事件重放窗口）"""
        await redis.set(f"processed_event:{event_id}", "1", ex=7*24*3600)
```

---

## 13. Web 前端接口规范

### 13.1 设计原则

**or.md 1.4.1(4)-(6) 原文：**
> 无障碍设计适配器：遵循 WCAG 2.1 AA 标准
> 多语言界面适配器：支持中文与英文界面切换
> 分支管理界面适配器：支持创建分支、切换分支、删除分支、分支差异对比视图

### 13.2 三视图架构

| 视图 | 目标用户 | 核心功能 | 对应 FR |
|------|---------|---------|-------|
| **高管视图** | CEO/CFO/CTO 等高管 | 仪表盘（3 个关键指标）、审批中心、审计摘要 | FR-UI-07 |
| **分析师视图** | 战略管理部人员 | 专业工具执行、溯源树展示、报告生成 | FR-UI-06, FR-UI-09 |
| **企业战略与市场人员视图** | 企业战略与市场体系人员 | 流程标准化执行、Checkpoint 管理、证据包打包 | FR-UI-05, FR-UI-10 |

### 13.3 REST API 端点设计

```
# 文档管理
POST   /api/v1/documents                    # 上传文档
GET    /api/v1/documents/{id}               # 查询文档
GET    /api/v1/documents/{id}/versions      # 版本列表
GET    /api/v1/documents/{id}/trace         # 血缘追踪

# 工具执行
POST   /api/v1/tools/{id}/execute           # 执行工具
GET    /api/v1/tools/{id}/schema            # 查看 Schema
POST   /api/v1/tool-chains/{id}/execute     # 执行工具链

# Agent 协作
POST   /api/v1/agents/{role}/run            # 运行 Agent
GET    /api/v1/agents/{role}/status         # 状态查询
POST   /api/v1/agents/arbitrate             # SYS Agent 裁决

# 战略规划
POST   /api/v1/plans/generate               # 生成规划
GET    /api/v1/plans/{id}                   # 查询规划
POST   /api/v1/plans/{id}/export            # 导出规划
POST   /api/v1/checkpoints/{id}/recover     # 恢复 Checkpoint

# 战略档案
GET    /api/v1/archive/query                # 档案查询
GET    /api/v1/archive/timeline             # 时间轴演进
GET    /api/v1/archive/diff                 # 分支差异对比

# 系统管理
POST   /api/v1/auth/login                   # 用户登录
GET    /api/v1/system/health                # 健康检查
GET    /api/v1/system/metrics               # 监控指标
```

### 13.4 无障碍设计要求（WCAG 2.1 AA）

| 要求 | 描述 | 验收标准 |
|------|------|---------|
| **键盘导航** | 所有功能支持纯键盘操作 | 100% 键盘可访问 |
| **屏幕阅读器** | 兼容 NVDA/JAWS/VoiceOver | ARIA 标签完整 |
| **色盲友好配色** | 不依赖颜色传递信息 | 颜色+文字双重编码 |
| **对比度** | 文本与背景对比度 ≥ 4.5:1 | WCAG AA 标准 |
| **焦点可见** | 键盘焦点元素有明确边框 | 焦点环 2px 以上 |

### 13.5 多语言设计要求

| 要求 | 描述 | 验收标准 |
|------|------|---------|
| **术语表统一** | 战略领域术语中英文对照 | 术语表覆盖 100% 领域概念 |
| **界面切换** | 中/英文一键切换 | 切换延迟 < 100ms |
| **翻译准确率** | 专业术语翻译准确率 ≥ 95% | 领域专家审核 |

---

## 17. 实施路线图

### 17.1 MVP 阶段（P0）

| 任务 | 交付物 | Story 关联 | 工作量 | or.md 追溯 |
|------|-------|-----------|-------|-----------|
| 定义 sisys CLI 6 个服务模块 | `cli/commands/` 骨架 | Story 7.1 | 2 周 | or.md 1.4.1(1) |
| 实现 CLI 基础框架 | typer 0.24+ 类型注解驱动 | Story 7.1 | 1 周 | or.md 1.4.1(1) |
| 设计 TOOLS.md 元数据清单 | `agents/ceo/TOOLS.md` | Story 5.2 | 1 周 | or.md 1.1.3(2) |
| 编写 3 个 Pilot SKILL.md | pestel/swot/five-forces | Story 4.1 | 2 周 | or.md 1.2.2(3) |
| 实现 SkillSelector | `list_active_skills()` 列表查询（无硬编码过滤） | Story 5.3 | 2 周 | or.md 1.1.3(1) |
| 定义 LLMRequest/LLMResponse | `domain/llm/protocol.py`（**`@dataclass(frozen=True)` 端口契约**，CLAUDE.md §5 领域层零依赖） + `application/llm/dto.py`（Pydantic DTO 序列化） | Story 1.14b | 1 周 | or.md 1.5.2(2) |
| 实现 LLM Adapter（LiteLLM） | `infrastructure/llm/` | Story 1.14b | 2 周 | or.md 1.5.2(2) |
| 定义 ToolCallRequest/Response | `domain/tool/protocol.py`（**`@dataclass(frozen=True)` 端口契约**） + `interfaces/api/v1/schemas/tool_schemas.py`（FastAPI Pydantic） | Story 4.3 | 1 周 | or.md 1.2.2(3) |
| 实现事件监听适配器 | RabbitMQ Consumer | Story 1.2 | 2 周 | or.md 1.4.1(3) |
| 实现 Command Translator | CLI → ApplicationCommand | Story 7.1 | 1 周 | or.md 1.3 |

### 17.2 V1 阶段（P1）

| 任务 | 交付物 | Story 关联 | or.md 追溯 |
|------|-------|-----------|-----------|
| 补全 20 个 SKILL.md | `skills/` 完整 | Story 4.x | or.md 1.2.2(3) |
| 实现 SAP 协议（三层） | `domain/agent/sap/protocol.py`（端口契约 `@dataclass(frozen=True)`） + `application/agent/sap_use_case.py`（用例编排） + `interfaces/sap/`（HTTP/mTLS 适配层） | Story 9.x | or.md 1.3(3) |
| 实现多 Agent 协作 | SYS Agent 裁决 | Story 9.6 | or.md 1.3(3) |
| 实现 Skill 版本管理 | 版本注册 + 回滚 | Story 4.6 | or.md 1.2.1(2) |
| 实现 Web 前端三视图 | 高管/分析师/战略人员视图 | Story 6.9/6.10 | or.md 1.4.1(4)-(6) |
| 实现事件幂等性保证 | processed_event 缓存 | Story 1.2 | or.md 1.6 |

### 17.3 V2+ 阶段（P2）

| 任务 | 交付物 | Story 关联 |
|------|-------|-----------|
| 实现 MCP Registry | `mcp/registry.yaml` | Story 4.8 |
| 实现 MCP Server | `mcp/server.py` | Story 4.8 |
| 外部 Agent 集成测试 | 跨系统工具调用 | Story 16.x |
| 企业级统一权限 | OAuth 2.1 + mTLS | Story 16.x |

---

## 18. 参考文档

| 文档 | 来源 | 核心借鉴 |
|------|------|---------|
| **钉钉 CLI** | `github.com/open-dingtalk/dingtalk-workspace-cli` | Agent 友好参数（--yes/--dry-run） |
| **飞书 CLI** | `github.com/larksuite/cli` | 三层架构（Shortcut/API/Raw） |
| **Claude Code Skills** | Anthropic 官方文档 | 三级渐进式披露 |
| **Claude Code CLAUDE.md** | GitHub 最佳实践 | 路由文件 < 150 行 |
| **MCP vs CLI Benchmark** | ScaleKit | Token 成本对比数据 |
| **sisys or.md** | 项目需求规格 | 系统公理一/二、DDD 四层、MVP 10 种领域事件（MVP 实现，总数 26 含 V1/V2 扩展）、8 种事件流转 |
| **sisys architecture.md** | 项目架构设计 | 六边形架构 + UDMR + EIP |
| **sisys epics_v1.0.md** | Epic 分解 | FR 溯源矩阵 |

---

**文档维护**：
- 本规则随架构决策记录（ADR）同步更新
- 每次接口变更必须更新对应版本号和契约测试
- 新成员入职必须阅读并通过本规则的理解测试
- **v2.0 更新**：整合 DDD 四层架构 + 事件驱动架构，新增四层映射架构、事件监听适配器、Web 前端接口规范
