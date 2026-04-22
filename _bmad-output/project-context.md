---
generated: 2026-04-12
project_name: sisys
user_name: Agimtech
document_status: complete
version: 1.0.0
source_documents:
  - or.md (企业战略规划管理智库系统需求特性列表)
  - prd.md (产品需求文档)
  - ux-design-specification.md (UX 设计规格)
  - architecture.md (架构设计文档)
  - interface-design.md (接口设计规范)
  - sdd-tdd-checklist.md (SDD+TDD 融合模式检查清单)
  - epics_v1.0.md (Epic 和用户故事分解)
  - sprint-status.yaml (Sprint 状态追踪)
---

# sisys - 项目上下文

**目标受众：** AI Agent 开发者
**目标：** 提供 AI Agent 在实现代码时必须遵循的关键规则、模式和约定

---

## 📑 目录索引

### 🚀 快速开始（新 Agent 必读）
- [1. 项目概述](#1-项目概述) - 产品定位、核心痛点、差异化优势
- [2. 技术栈](#2-技术栈) - 完整技术选型（语言/框架/存储/消息/监控）
- [10. 快速参考](#10-快速参考) - 关键命令、文档位置

### 🏗️ 架构规则（实施前必须理解）
- [3. 架构原则](#3-架构原则必须遵守) - 六边形架构、系统公理、事件驱动、CLI+Skills、UDMR、EIP、Checkpoint、修正分级
- [4. 代码约定与模式](#4-代码约定与模式) - 项目结构、命名约定、代码组织规则

### 🔨 开发与测试
- [5. 测试策略](#5-测试策略) - SDD+TDD 融合模式、质量门禁、测试金字塔
- [6. CI/CD 流水线](#6-cicd-流水线) - 代码提交检查、Story 完成定义
- [8. 开发工作流](#8-开发工作流) - 分支命名、提交约定、Sprint 状态

### 📊 指标与目标
- [7. 关键性能指标](#7-关键性能指标) - 性能/质量/安全目标

### 📚 领域知识速查
- [11. 领域实体速查](#11-领域实体速查) - 9 个核心实体及不变约束
- [12. 领域事件速查](#12-领域事件速查) - 10 种领域事件及下游触发
- [13. UX 设计速查](#13-ux-设计速查) - 三视图架构、核心体验要求、设计系统

### 🔌 接口设计规范
- [14. 接口设计规范](#14-接口设计规范来自-interface-designmd) - 接口分层、CLI 命令、Skills 加载、四层映射、SAP 协议、REST API、事件监听、安全分层、监控指标

### ⚠️ 避坑指南
- [9. 常见陷阱与避免策略](#9-常见陷阱与避免策略) - 架构/测试/性能陷阱

---

## 1. 项目概述

sisys 是面向大中型企业高管团队、企业战略与市场体系人员和专业顾问的 **AI 驱动战略规划与决策智能平台**。系统通过多 Agent 协作（CEO/CFO/CMO/CTO/COO/CHO/AUD 七种专业角色）和内置合规审计（7 年 WORM 存储），解决企业战略规划中的三大核心痛点：
- 高管团队协调难 - 战略规划需要多角色视角，但高管时间难以协调，决策质量依赖个人经验
- 数据分散决策难 - 决策质量依赖数据，但企业数据分散在不同系统，难以形成完整洞察
- 流程长效率低 - 大中型企业战略规划参与人员多、流程长、效率低，从数周到数月不等

### 1.1 核心差异化

| 能力 | 用户价值 |
|------|---------|
| 输入企业数据 → 最优战略规划 | 精准高效制定 SP/BP，避免人为偏差 |
| 多 Agent 辩论 | 模拟高管团队多视角辩论，风险识别率≥90% |
| 高保真溯源 | Bounding Box 坐标级跳转至原始文档，30 秒内完成 |
| 全流程闭环 | 从 SP 到 BP 到执行设计的完整链路 |
| 合规内建 | 7 年 WORM 存储、审计追踪、数据主权隔离 |

---

## 2. 技术栈

### 2.1 核心技术

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **语言** | Python | 3.11+ | 主要开发语言 |
| **API 框架** | FastAPI | 0.104+ | REST API |
| **CLI 框架** | Typer | 0.24+ | 命令行接口（基于 click 封装） |
| **工作流引擎** | Prefect | 3.6+ | 确定性数据管道 |
| **Agent 编排** | LangGraph | 1.0+ | Agent 认知推理 |
| **模型路由** | LiteLLM | 最新 | 统一 LLM 代理 |
| **嵌入模型** | bge-m3 | 最新 | 向量嵌入（1024 维） |

### 2.2 存储层（五层架构）

| 层级 | 技术 | 版本 | 存储内容 | TTL |
|------|------|------|---------|-----|
| **L1 高速缓存** | Redis | 7.0+ | 会话状态、语义缓存、公共黑板 | 24h-30d |
| **L2 关系存储** | PostgreSQL | 15+ | 用户/RBAC、审计元数据、业务实体 | 永久 |
| **L3 向量存储** | Qdrant | 1.7+ | 嵌入向量、混合检索 payload | 永久 |
| **L4 对象存储** | MinIO | 最新 | 原始文档、证据包、审计归档 | 7 年 (WORM) |
| **L5 图存储** | Neo4j | 5.x | 知识图谱、实体关系、依赖图 | 永久 |

### 2.3 消息与事件

| 技术 | 用途 |
|------|------|
| RabbitMQ 3.12+ | 持久化事件通道 + 事务发件箱 |
| Redis 发布/订阅 | 实时事件通道 |
| aio-pika | RabbitMQ Python 客户端 |

### 2.4 沙箱与安全

| 技术 | 版本 | 用途 |
|------|------|------|
| Docker | 最新 | MVP 沙箱执行隔离 |
| gVisor | V2 | 代码执行隔离（用户空间内核） |

### 2.5 监控与可观测性

| 技术 | 用途 |
|------|------|
| Prometheus | 指标收集 |
| Grafana | 可视化仪表盘 |
| OpenTelemetry | 分布式追踪 |

### 2.6 前端（V1+）

| 技术 | 用途 |
|------|------|
| React 18 | 前端框架 |
| TypeScript | 类型安全 |
| Ant Design 5.x | 设计系统基础 |
| CSS-in-JS | 主题定制 |
| PDF.js | PDF 查看器（Bounding Box 溯源） |
| ECharts | 数据可视化（龙卷风图、热力图） |

### 2.7 CI/CD 基础设施

| 技术 | 版本 | 用途 |
|------|------|------|
| K3S | v1.34.5 | 轻量级 K8s 运行时 |
| Gitea | v125.4 | 代码托管 |
| Harbor | v2.14.3 | 镜像仓库 |
| ArgoCD | v3.2.7 | 持续部署 |

### 2.8 关键依赖

| 库 | 用途 |
|------|------|
| Pydantic V2 | Schema 验证、数据验证 |
| SQLAlchemy | ORM、数据模型 |
| Instructor | 强制 LLM 输出符合 Schema |
| pytest | 单元测试框架 |
| pytest-bdd | 验收测试（Gherkin 格式） |
| ruff | 代码检查和格式化 |
| mypy | 类型检查 |
| bandit | 安全扫描 |

---

## 3. 架构原则（必须遵守）

### 3.1 领域驱动六边形架构

**严格分层，依赖方向不可逆：**

```
接口层 (Interfaces)
    ↓ 调用
应用层 (Application) - 用例服务
    ↓ 调用
领域层 (Domain) - 核心实体、领域服务接口、仓储接口
    ↑ 实现
基础设施层 (Infrastructure) - 仓储实现、外部适配器
```

**关键规则：**

- ✅ **领域层零依赖**：领域层仅依赖 Python 标准库与领域模型，**绝不依赖任何外部框架**
- ✅ **依赖倒置**：领域层定义接口，基础设施层实现接口
- ✅ **仓储模式**：领域层不直接依赖具体存储实现，通过仓储接口访问
- ❌ **禁止跨层调用**：领域层不能调用应用层或基础设施层
- ❌ **禁止循环依赖**：任何循环依赖都是架构违规

### 3.2 系统公理（所有设计的基础）

#### 公理一：自主调用 (Autonomous Invocation)

```
trigger(事件) → route(路由) → execute(执行)
```

- trigger：领域事件或周期性心跳事件触发
- route：基于 session_id 哈希或语义路由至目标 Agent 或工具
- execute：在会话命名空间中执行，支持状态持久化与中断恢复

#### 公理二：外部化记忆 (Externalized Memory)

- **LLM 上下文 = 缓存**：仅保留当前任务必需的压缩信息
- **磁盘记忆 = 真相源**：会话状态与推理轨迹持久化至战略档案库
- **压缩前必须持久化**：防止信息丢失
- **上下文压缩率目标**：≥70%
- **循环流程**：检索->持久化笔记->压缩->LLM 上下文注入->生成与验证->反馈与演进

### 3.3 事件驱动架构

**双通道事件总线：**

| 事件类型 | 通道 | 理由 |
|---------|------|------|
| 实时通知型 | Redis 发布/订阅 | 低延迟、允许丢失 |
| 业务状态型 | RabbitMQ + Outbox | 可靠性要求高 |
| 审计事件型 | RabbitMQ + WORM 归档 | 合规要求 7 年存储 |

**事件格式标准化（必须遵守）：**

```python
class DomainEvent(BaseModel):
    event_id: UUID
    event_type: str
    timestamp: datetime
    payload: dict
    source: str
    schema_version: str
    aggregate_id: UUID
    aggregate_type: str
    version: int
```

**事务发件箱模式（必须使用）：**

- 事件与业务操作同事务提交至 PostgreSQL `event_outbox` 表
- 后台处理器轮询发布至 RabbitMQ
- 保证最终一致性

### 3.4 CLI + Skills 核心设计原则

**设计哲学：CLI 为内核，MCP 为外延**

| 编号 | 原则 | 验收标准 |
|------|------|---------|
| **P1** | CLI 是 LLM 的母语 | 内部工具 100% 有 CLI 入口 |
| **P2** | Skills 渐进式披露 | Agent 启动上下文 < 500 tokens |
| **P3** | Skill = SOP + Examples | 23 种工具各有完整 SOP + input_examples |
| **P4** | MCP 退居生态层 | MVP 阶段 MCP 代码量 = 0 |
| **P5** | Less scaffolding, more model | 工具选择准确率 ≥ 85% |
| **P6** | 负向触发条件 | 误触发率 < 5% |
| **P7** | input_examples 驱动 | 每个 Skill 1-5 个典型输入示例 |

**CLI 命令结构：**

- 三级命令结构：`sisys <service> <resource> <action> [options]`
- 示例：`sisys tool run pestel --input data.json`
- 6 个核心服务模块：`document/tool/agent/plan/checkpoint/archive`
- 2 个辅助模块：`system/config`
- Agent 友好参数：`--yes`（跳过确认）/`--dry-run`（预览）/`--mock`（模拟）
- 所有命令支持 `--format json/table/pretty` 输出格式切换

### 3.5 统一动态模型路由框架 (UDMR)

**三层决策架构：**

```
L1 合规性网关 → L2 任务复杂度评估 → L3 路由决策执行
```

**L1 合规性网关（必须首先执行）：**

- 敏感数据检查（PII/商业秘密）
- 数据驻留限制（境内/跨境）
- 白名单校验（允许的模型列表）

**L2 四因子评分（权重固定）：**

| 因子 | 权重 |
|------|------|
| 语义匹配度 | 35% |
| 历史成功率 | 30% |
| 成本效率 | 20% |
| 任务复杂度 | 15% |

**L3 路由决策阈值：**

- 云模型优势阈值：0.15（超过才选云端）
- 本地质量阈值：0.70（低于则选云端）
- 目标：本地路由占比 ≥80%、成本节省 ≥50%

**路由决策延迟目标：** P95<50ms

### 3.6 弹性视角隔离协议 (EIP)

**四级隔离等级：**

| 等级 | 名称 | Prompt 隔离 | 工具隔离 | 数据隔离 |
|------|------|-----------|---------|---------|
| **L4** | 硬隔离 | 独立 | 严格隔离 | 只读 |
| **L3** | 软隔离 | 独立 | 共享工具 | 受限写入 |
| **L2** | 协作态 | 独立身份 | 共享工具池 | 自由写入 |
| **L1** | 融合态 | 共享上下文 | 完全共享 | 完全共享 |

**关键规则：**

- 默认状态：L4 硬隔离
- 联合任务完成后 **30 分钟无活动自动恢复至 L4**
- 所有隔离切换自动记录至 `IsolationSwitchLog` 并归档至 WORM 存储

### 3.7 Checkpoint 双模式恢复

**Replay 模式（强一致性）：**

- 修改点后所有状态重新计算
- 适用于假设/逻辑变更
- 影响≥2 个后续 Checkpoint 强制使用

**Override 模式（弱一致性）：**

- 仅修改指定状态，后续状态不变
- 需人工确认一致性风险
- 适用于拼写/格式调整
- 影响<2 个后续 Checkpoint 推荐使用

**Time-travel 两阶段能力：**

1. 单点恢复：从任意 Checkpoint 恢复执行
2. 分支对比：创建分支→执行恢复→差异对比→合并/放弃

### 3.8 修正分级判定体系

**四级修正分级：**

| 级别 | 类型 | 审批 | SLA |
|------|------|------|-----|
| **L0** | 拼写/格式 | 自动固化 | - |
| **L1** | 参数/权重微调 | 自动固化 | - |
| **L2** | 约束变更 | 专家确认（1 人） | 4 小时（紧急 1 小时） |
| **L3** | 假设/逻辑/战略修改 | 委员会审批（≥3 人） | 48 小时 |

**五维特征加权算法（判定级别）：**

| 特征 | 权重 |
|------|------|
| 修正类型 | 30% |
| 置信度变化 | 25% |
| 影响范围 | 20% |
| 可逆性 | 15% |
| 领域关键度 | 10% |

**级别映射：**

- 得分≥0.85 → L0
- 0.75≤得分<0.85 → L1
- 0.60≤得分<0.75 → L2
- 得分<0.60 → L3

---

## 4. 代码约定与模式

### 4.1 项目结构

```
sisys/
├── src/
│   ├── domain/                    # 领域层（零外部依赖）
│   │   ├── entities/              # 核心实体（Document, Agent, Tool, etc.）
│   │   ├── services/              # 领域服务接口
│   │   ├── events/                # 领域事件定义
│   │   ├── repositories/          # 仓储接口
│   │   └── value_objects/         # 值对象
│   ├── application/               # 应用层
│   │   ├── use_cases/             # 用例服务
│   │   ├── commands/              # 命令定义
│   │   ├── queries/               # 查询定义
│   │   └── dto/                   # 数据传输对象
│   ├── interfaces/                # 接口层
│   │   ├── cli/                   # CLI 适配器（Typer）
│   │   ├── api/                   # REST API 适配器（FastAPI）
│   │   └── event_listeners/       # 事件监听适配器
│   └── infrastructure/            # 基础设施层
│       ├── repositories/          # 仓储实现
│       ├── external_services/     # 外部服务适配器
│       ├── message_bus/           # 消息总线实现
│       ├── storage/               # 五层存储实现
│       └── workflow_engines/      # Prefect/LangGraph 包装器
├── tests/
│   ├── unit/                      # 单元测试
│   ├── integration/               # 集成测试
│   ├── acceptance/                # 验收测试（.feature 文件）
│   └── contract/                  # 契约测试
├── docs/
│   ├── developer/                 # 开发文档
│   └── api/                       # API 文档
└── _bmad-output/                  # BMad 输出 artifacts
    ├── planning-artifacts/        # 规划产物
    └── implementation-artifacts/  # 实现产物
```

### 4.2 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| **文件命名** | kebab-case | `document-service.py`, `event-bus.py` |
| **类命名** | PascalCase | `DocumentService`, `DomainEvent` |
| **函数/方法命名** | snake_case | `process_document()`, `execute_tool()` |
| **变量命名** | snake_case | `document_id`, `event_timestamp` |
| **常量命名** | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| **测试文件命名** | `test_<模块名>.py` | `test_document_service.py` |
| **验收测试文件命名** | `<场景>.feature` | `document_upload.feature` |

### 4.3 代码组织规则

- ✅ **领域层**：仅包含实体、值对象、领域服务接口、仓储接口、领域事件
- ✅ **应用层**：用例服务、命令/查询、DTO、编排逻辑
- ✅ **接口层**：CLI 适配器、API 适配器、事件监听器
- ✅ **基础设施层**：仓储实现、外部服务适配器、消息总线、存储实现
- ❌ **禁止**：领域层包含任何基础设施相关代码
- ❌ **禁止**：跨层直接调用（必须通过接口）

### 4.4 文档约定

- ✅ **领域事件**：必须定义 Pydantic V2 Schema
- ✅ **API 端点**：必须定义 OpenAPI 3.1 规范
- ✅ **用例**：必须编写 Gherkin 格式验收标准
- ✅ **数据模型**：必须定义 SQLAlchemy 实体
- ✅ **代码注释**：高价值注释，解释"为什么"而非"做什么"

---

## 5. 测试策略

### 5.1 开发模式：SDD+TDD 融合

**红 - 绿 - 重构循环：**

1. **红阶段**：编写失败的测试（基于验收标准）
2. **绿阶段**：编写刚好让测试通过的最小实现
3. **重构阶段**：保持测试通过的前提下优化代码

**质量门禁（必须达标）：**

| 指标 | 要求 |
|------|------|
| 整体覆盖率 | ≥80% |
| 领域层覆盖率 | ≥90% |
| 应用层覆盖率 | ≥85% |
| 基础设施层覆盖率 | ≥75% |
| 严重错误 | 0 |
| 高危漏洞 | 0 |

### 5.2 测试金字塔

```
E2E 测试 (10%)
├── 溯源成功路径
├── 高管仪表盘加载
├── 白标报告生成
└── 品牌模板切换

集成测试 (30%)
├── 表格 + 筛选 + 分页联动
├── 溯源卡片 + PDF 查看器
├── 财务组件 + 数据源
└── 主题切换 + 组件样式

单元测试 (60%)
├── 基础组件
├── 业务组件
└── 工具函数
```

### 5.3 关键测试场景

| 场景 | 验证点 |
|------|-------|
| 文档上传与解析 | 17 种格式支持、解析准确率≥95% |
| 高保真溯源 | 响应<300ms、定位准确率≥95% |
| 多 Agent 辩论 | 风险识别率≥90%、辩论轮次控制 |
| Checkpoint 恢复 | Replay/Override 模式正确性 |
| UDMR 路由 | 本地占比≥80%、路由延迟 P95<50ms |
| EIP 隔离 | 隔离等级切换正确性、30 分钟自动恢复 |
| 修正分级判定 | 五维加权算法准确率≥85% |

---

## 6. CI/CD 流水线

### 6.1 代码提交前检查清单

- [ ] 所有本地测试通过
- [ ] 所有规范验证通过
- [ ] 所有质量检查通过
- [ ] 覆盖率达标
- [ ] 代码已格式化

### 6.2 CI/CD 阶段

| 阶段 | 检查项 | 失败条件 |
|------|-------|---------|
| **1. 代码质量门禁** | Ruff 检查、Ruff 格式、MyPy 类型 | 严重错误=0、格式错误=0、错误率<5% |
| **2. 单元测试** | 单元测试执行 | 整体覆盖≥80%、领域层≥90%、应用层≥85% |
| **3. 集成测试** | 集成测试执行 | 外部服务 Mock 正确 |
| **4. 安全扫描** | Bandit、Safety | 高危漏洞=0 |
| **5. 构建与部署** | Docker 镜像构建、推送、部署 | 健康检查通过 |

### 6.3 Story 完成定义（DoD）

一个 Story 被认为完成，当且仅当：

- [ ] SDD 规范定义完成（领域事件 Schema、API 契约、验收标准）
- [ ] TDD 红 - 绿 - 重构循环完成
- [ ] SDD 规范验证通过（Schema 验证、API 契约测试、验收测试、类型检查）
- [ ] 覆盖率达标（整体≥80%、领域层≥90%、应用层≥85%）
- [ ] 代码质量检查通过（Ruff、MyPy、Bandit）
- [ ] CI/CD 流水线通过
- [ ] 文档更新（代码注释、README、API 文档）

---

## 7. 关键性能指标

### 7.1 性能目标

| 指标 | MVP | V1 | V2 |
|------|-----|----|----|
| 检索延迟 P95 | <800ms | <500ms | <300ms |
| 路由决策延迟 P95 | <100ms | <50ms | <30ms |
| 系统可用性 | 99% | 99.5% | 99.9% |
| 并发 Agent 会话 | 10 | 50 | 200 |
| Checkpoint 恢复时间 | <60s | <30s | <15s |

### 7.2 质量目标

| 指标 | 目标 |
|------|------|
| 修正分级准确率 | ≥85% |
| Strat-Bench 通过率 | ≥90% |
| 提示注入检测准确率 | ≥95% |
| 多 Agent 辩论风险识别率 | ≥90% |
| 溯源定位准确率 | ≥95% |

### 7.3 安全与合规目标

| 指标 | 目标 |
|------|------|
| 数据泄露事件 | 0 |
| 审计日志完整性 | 100% |
| WORM 存储合规性 | 7 年不可变存储 |
| 权限控制准确率 | 100% |
| 数据加密覆盖率 | 100% |

---

## 8. 开发工作流

### 8.1 分支命名约定

- 功能分支：`feature/<epic>-<story>-<description>`
- 修复分支：`fix/<description>`
- 发布分支：`release/<version>`

### 8.2 提交消息约定

```
<type>(<scope>): <description>

feat(domain): add Document entity
fix(api): resolve pagination bug
docs(architecture): update storage section
```

| Type | 描述 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `test` | 测试相关 |
| `refactor` | 代码重构 |
| `chore` | 日常维护 |

### 8.3 当前 Sprint 状态

- **Epic 0 Iteration 0**：✅ 已完成（3 stories）
- **Epic 0 Iteration 1**：🔄 进行中（9 done, 2 ready-for-dev）
- **Epic 1-19**：📋 待开始（140 stories）

**下一步行动：**

1. 完成 Epic 0 Iteration 1 剩余 Stories（0-17/0-18）
2. 启动 Epic 1 Story 1.1（六边形架构骨架）

---

## 9. 常见陷阱与避免策略

### 9.1 架构陷阱

| 陷阱 | 症状 | 避免策略 |
|------|------|---------|
| **领域层泄漏** | 领域层导入基础设施包 | CI 门禁检查领域层零依赖 |
| **循环依赖** | 模块 A 导入 B，B 导入 A | 依赖倒置，使用接口 |
| **跨层调用** | 领域层直接调用 Redis/PostgreSQL | 通过仓储接口访问 |

### 9.2 测试陷阱

| 陷阱 | 症状 | 避免策略 |
|------|------|---------|
| **测试实现先行** | 先写实现后补测试 | 严格执行红 - 绿 - 重构循环 |
| **测试覆盖率虚高** | 测试覆盖但不验证业务逻辑 | 验收测试基于用户旅程 |
| **Mock 过度使用** | Mock 所有外部依赖导致测试无意义 | 关键路径使用真实依赖 |

### 9.3 性能陷阱

| 陷阱 | 症状 | 避免策略 |
|------|------|---------|
| **上下文爆炸** | LLM 上下文过长导致截断 | 压缩前必须持久化，压缩率≥70% |
| **检索延迟超标** | 检索超过 800ms | 三路融合+分级精排 Top-100→Top-20 |
| **路由决策慢** | UDMR 决策超过 50ms | 语义匹配预计算、缓存候选模型 |

---

## 10. 快速参考

### 10.1 关键命令

```bash
# 完整开发循环
make sdd-define          # SDD 规范定义
make tdd-red TARGET=...  # TDD 红阶段
make tdd-green TARGET=... # TDD 绿阶段
make tdd-refactor TARGET=... # TDD 重构阶段
make sdd-verify          # SDD 规范验证
make quality-gates       # 质量门禁检查

# 快速测试
pytest tests/unit/ -v                    # 运行单元测试
pytest tests/acceptance/ -v              # 运行验收测试
pytest --cov=src --cov-fail-under=80     # 运行覆盖率检查

# 代码质量
ruff check src/ tests/                   # Ruff 检查
ruff format src/ tests/                  # Ruff 格式化
mypy src/                                # MyPy 类型检查
bandit -r src/                           # 安全扫描
```

### 10.2 关键文档位置

| 文档 | 位置 |
|------|------|
| 产品需求文档 | `_bmad-output/planning-artifacts/prd.md` |
| 架构设计文档 | `_bmad-output/planning-artifacts/architecture.md` |
| UX 设计规格 | `_bmad-output/planning-artifacts/ux-design-specification.md` |
| Epic 分解 | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| Sprint 状态 | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| SDD+TDD 检查清单 | `docs/developer/sdd-tdd-checklist.md` |

---

## 11. 领域实体速查

| 实体 | 关键属性 | 不变约束 |
|------|---------|---------|
| **Document** | 元数据、版本历史、解析结果、嵌入向量 | 最小元字段集校验、版本冲突检测 |
| **Agent** | 身份档案、权责边界、领域知识、技能 | 视角隔离、会话状态持久化 |
| **Tool** | 唯一标识、I/O Schema、执行逻辑、验证器 | 契约化输出、沙箱执行隔离 |
| **StrategicPlan** | BLM 六阶段、Checkpoint 机制 | BLM 模型流程不变性 |
| **BusinessPlan** | BEM 六阶段、SP 映射 | SP 输出到 BP 输入的 Schema 强制映射 |
| **Checkpoint** | 阶段标识、完成状态、修正记录 | 双模式恢复、Time-travel 能力 |
| **StrategicArchive** | 关键假设、决策依据、执行偏差 | 向量+对象存储协同、不可变存储 |
| **RoutingDecisionLog** | 任务 ID、评分、选定模型、成本 | WORM 存储 7 年 |
| **IsolationSwitchLog** | Agent ID、隔离等级、触发原因 | WORM 存储 7 年 |

---

## 12. 领域事件速查

**领域事件定义：**领域层中的 Domain Event 必须使用标准库类型定义，不依赖 Pydantic 或其他第三方库；Pydantic 仅用于应用层/基础设施层的边界校验、序列化与反序列化。领域事件与传输 DTO 必须分离，必要时通过 TypeAdapter 做无样板转换。

| 事件 | 携带内容 | 触发下游 |
|------|---------|---------|
| **DocumentProcessed** | 文档 ID、解析结果、嵌入向量 | 实体抽取、图谱构建 |
| **ToolExecuted** | 工具 ID、执行结果、成本审计 | Agent 决策、成本聚合 |
| **AgentDecided** | Agent ID、决策结果、置信度 | SYS Agent 仲裁、审计日志 |
| **CheckpointReached** | 阶段标识、用户反馈请求 | 用户交互、状态持久化 |
| **CorrectionApproved** | 修正类型、前后值、审批链 | 自动固化、版本注册 |
| **StrategicDeviationWarning** | 偏差类型、等级、实际值 | Agent 响应、偏差分析 |
| **HeartbeatTriggered** | 心跳 ID、唤醒原因、待办事项 | 周期性检查、偏差预警 |
| **IsolationLevelSwitched** | Agent ID、原/目标等级、触发原因 | 公共黑板更新、状态同步 |
| **CheckpointRecovered** | Checkpoint ID、恢复模式、修改内容 | 战略档案更新、分支管理 |
| **RoutingDecided** | 任务 ID、评分、选定模型 | 路由决策日志存储、成本监控 |

---

## 13. UX 设计速查

### 13.1 三视图架构

| 视图 | 用户 | 信息密度 | 关键原则 |
|------|------|---------|---------|
| **高管视图** | CEO/CFO/CTO | 低（30 秒决策） | 第一屏只显示 3 个关键指标 |
| **分析师视图** | 战略管理部 | 高（深度分析） | 快捷键、批量操作、专业工具 |
| **顾问视图** | 咨询/投行 | 中（项目交付） | 白标输出、多租户隔离 |

### 13.2 核心体验要求

| 体验 | 目标 | 验收标准 |
|------|------|---------|
| 高保真溯源 | 30 秒内跳转至原始文档坐标点 | 响应<300ms、定位准确率≥95% |
| 高管仪表盘 | 30 秒内理解并决策 | 30 秒理解率≥90% |
| 白标报告 | 品牌元素 100% 准确应用 | 导出时间<1 分钟、质量评分≥9/10 |
| 财务量化 | 每个战略建议显示 NPV/IRR | 财务量化覆盖率 100% |

### 13.3 设计系统

- **基础**：Ant Design 5.x + CSS-in-JS + Design Tokens
- **颜色**：主色 `#1890ff`、状态色（绿 `#52c41a`/黄 `#faad14`/红 `#ff4d4f`）
- **字体**：PingFang SC, Microsoft YaHei, sans-serif
- **关键组件**：溯源卡片、风险热力图、财务量化组件、高管仪表盘

---

## 14. 接口设计规范（来自 interface-design.md）

### 14.1 接口分层架构

**设计哲学：CLI + Skills 为内核，MCP 为外延**

```
【外部用户/系统】
      │
      ▼
┌─────────────────┐     ┌──────────────────┐
│   CLI 接口层     │     │   REST API 层     │  ← 对外（用户/集成）
│   sisys CLI     │     │   FastAPI 0.104+  │
│   (typer 0.24+) │     │   OpenAPI 3.1     │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
┌──────────────────────────────────────┐
│       应用层用例服务 (Use Cases)      │
└──────────────────┬───────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│   CLI 工具层     │     │   Skills 层       │  ← 核心（内部主干）
│   sisys doc     │     │   AGENT.md        │
│   sisys tool    │     │   IDENTITY.md     │
│   sisys agent   │     │   TOOLS.md        │
│   sisys plan    │     │   SKILL.md × 23   │
│   sisys checkpt │     │   MEMORY.md       │
└────────┬────────┘     │   HEARTBEAT.md    │
         │              └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
┌──────────────────────────────────────┐
│       领域层 (Domain)                 │
│  Document / Tool / Agent / Plan      │
└──────────────────────────────────────┘
```

**接口职责矩阵：**

| 接口层 | 职责 | 用户 | 方向 | 版本 | 优先级 |
|--------|------|------|------|------|-------|
| **CLI** | 系统内部能力暴露 | 用户 + Agent | 外→内 | MVP | **P0** |
| **Skills** | Agent 行为知识（SOP） | Agent 内部 | 内部 | MVP | **P0** |
| **REST API** | 外部系统集成 | 第三方系统 | 外→内 | MVP | **P0** |
| **SAP** | Agent 间通信 | Agent 之间 | 横向 | V1 | **P1** |
| **LLM Adapter** | 统一 LLM 调用 | 系统内部 | 内→外 | MVP | **P0** |
| **MCP** | 外部 Agent 生态 | 外部 Agent | 外→内 | V2+ | **P2** |

### 14.2 CLI 命令结构

**三级命令结构：** `sisys <service> <resource> <action> [flags]`

**6 个核心服务模块 + 2 个辅助模块：**

| 服务模块 | 职责 | 示例命令 |
|---------|------|---------|
| `sisys document` | 文档管理 | `upload`, `parse`, `search`, `version` |
| `sisys tool` | 工具箱 | `run`, `chain run`, `schema`, `list` |
| `sisys agent` | Agent 协作 | `run`, `status`, `arbitrate` |
| `sisys plan` | 战略规划 | `generate`, `export`, `review` |
| `sisys checkpoint` | Checkpoint 管理 | `list`, `show`, `recover` |
| `sisys archive` | 战略档案 | `query`, `timeline`, `diff` |
| `sisys system` | 系统管理（辅助） | `auth`, `monitor`, `route` |
| `sisys config` | 配置管理（辅助） | 环境/路由/隔离 |

**Agent 友好参数（必须支持）：**

| 参数 | 描述 | 默认值 |
|------|------|-------|
| `--yes` | 跳过交互式确认 | false |
| `--dry-run` | 预览不执行 | false |
| `--mock` | 使用模拟数据 | false |
| `--session <id>` | 会话命名空间 | 自动生成 |
| `--cost-budget <amount>` | 成本预算上限 | 系统默认 |
| `--timeout <seconds>` | 执行超时 | 300 |

**输出格式（必须支持）：** `json` / `table` / `pretty` / `ndjson` / `csv`

### 14.3 Skills 三级渐进式加载

```
L1: TOOLS.md (< 200 tokens)
    → 工具元数据清单（name + description + trigger + tags + version）
    → Agent 实例化时加载
    → 用于 SkillSelector 推荐

    ↓ 触发匹配

L2: SKILL.md (< 500 行)
    → SOP 完整定义（IDENTITY + TRIGGER + SOP + FAILURE + SCHEMA）
    → 任务执行时加载
    → 必须包含 input_examples（1-5 个）和负向触发条件

    ↓ 按需调用

L3: scripts/references
    → scripts/ 确定性计算（Python 脚本）
    → references/ 理论参考（Markdown）
    → 按需加载
```

**SkillSelector 推荐算法：**
- 关键词匹配 40% + 语义相似度 60%
- 推荐准确率 ≥85%
- 误触发率 <5%

### 14.4 四层映射架构（DDD + EDA + CLI+Skills 统一）

**规则 1：CLI → 用例 → 领域服务 → 领域事件 完整链路**

```
T0: CLI 命令发送
T1: 用例执行开始
    ├── T2: Skill 加载（L1→L2→L3）
    ├── T3: 领域服务执行
    │      └── T4: 领域事件发布 ──→ 事件总线（异步，不阻塞 CLI）
    ├── T5: 证据包打包
T6: 用例返回 DTO
T7: CLI 格式化输出并返回给用户
```

**规则 2：CLI 命令到应用层用例的精确映射**

| CLI 服务模块 | 映射用例 |
|-------------|---------|
| `sisys document` | DocumentProcessingUseCase |
| `sisys tool` | StrategicAnalysisUseCase |
| `sisys agent run` | AgentCollaborationUseCase |
| `sisys agent arbitrate` | AgentCollaborationUseCase + SystemOperationsUseCase |
| `sisys plan` | PlanningGenerationUseCase |
| `sisys checkpoint` | PlanningGenerationUseCase |
| `sisys system` | SystemOperationsUseCase |

**规则 3：Skills 在 DDD 架构中的精确位置**

- L1 TOOLS.md → 接口层的工具元数据清单
- L2 SKILL.md → 应用层的操作流程手册（定义"如何调用领域服务"）
- L3 scripts/references → 基础设施层的确定性计算

**规则 4：CLI 同步响应与事件异步处理的协调**

- CLI 响应不阻塞下游事件处理
- `--wait-for-events` 参数可选等待特定事件完成（超时默认 30 秒）

**规则 5：系统公理一与 CLI 的关系**

- CLI 是"点火开关"（外部触发器）
- 领域事件是"引擎血液"（内部触发器）
- trigger→route→execute 是"引擎运转逻辑"

### 14.5 SAP Agent 间通信协议（V1+）

**消息类型：** REQUEST / RESPONSE / NOTIFICATION / BROADCAST / DEBATE

**消息优先级：** LOW / NORMAL / HIGH / URGENT

**SAP 消息格式：**

```python
class SAPMessage(BaseModel):
    message_id: UUID
    conversation_id: UUID
    timestamp: datetime
    sender_id: str                 # 发送 Agent ID
    receiver_id: str               # 接收 Agent ID，广播时为"broadcast"
    message_type: MessageType
    priority: MessagePriority
    subject: str
    content: Dict[str, Any]
    requires_response: bool = False
    timeout_seconds: int = 300
    correlation_id: UUID = None
    isolation_level: str = "L4"
    blackboard_visible: bool = False
```

**SAP 不可替代的三大场景：**

1. **多 Agent 辩论** - 需要消息类型、置信度交换、公共黑板可见性、裁决状态机
2. **联合分析组（EIP L2 协作态）** - 需要隔离等级动态切换、公共黑板 MVCC、协作状态同步
3. **SYS Agent 裁决** - 需要五维评分、置信度判定、三套方案生成

**安全要求：**

| 安全机制 | 版本 |
|---------|------|
| 消息签名 | MVP |
| 审计日志 | MVP |
| RBAC + 隔离等级 | V1 |
| mTLS 加密 | V2 |

### 14.6 REST API 核心端点

**文档管理：**
- `POST /api/v1/documents` - 上传文档
- `POST /api/v1/documents/batch` - 批量上传（100 个 BP/报告）
- `GET /api/v1/documents/{id}/trace` - 高保真溯源（Bounding Box 坐标）

**工具执行：**
- `POST /api/v1/tools/{id}/execute` - 执行工具
- `POST /api/v1/tool-chains/{id}/execute` - 执行工具链（DAG）

**Agent 协作：**
- `POST /api/v1/agents/{role}/run` - 运行 Agent
- `POST /api/v1/agents/arbitrate` - SYS Agent 裁决

**财务量化（P0）：**
- `POST /api/v1/financial/analyze` - NPV/IRR/现金流
- `POST /api/v1/financial/sensitivity` - 敏感性分析（龙卷风图）

**战略规划：**
- `POST /api/v1/plans/generate` - 生成 SP/BP
- `GET /api/v1/plans/{id}/compare` - 情景对比（3 方案并排）

**Checkpoint 管理：**
- `POST /api/v1/checkpoints/{id}/recover` - 恢复（Replay/Override）

**API Gateway 要求：**
- 统一认证（OAuth 2.1 + JWT）
- 限流（令牌桶算法）
- 路由（基于路径/方法/角色）
- 安全（请求验证 + 注入检测）

### 14.7 事件监听适配器

**10 种领域事件监听映射：**

| 领域事件 | 触发的下游用例 |
|---------|---------------|
| DocumentProcessed | 实体抽取、图谱构建、索引构建 |
| ToolExecuted | 成本聚合、技能演进、Agent 决策 |
| AgentDecided | SYS AGENT 仲裁、公共黑板更新、审计日志 |
| CheckpointReached | 用户反馈、状态持久化 |
| CorrectionApproved | 自动固化、版本注册、演进日志 |
| StrategicDeviationWarning | Agent 响应、偏差分析 |
| HeartbeatTriggered | 周期性任务检查、偏差预警、成本预算校验 |
| IsolationLevelSwitched | 公共黑板权限更新、协作状态同步 |
| CheckpointRecovered | 战略档案库版本更新、分支管理 |
| RoutingDecided | 路由决策日志存储、成本监控 |

**事件处理幂等性保证：**

```python
# 基于 event_id 的 Redis 缓存去重，TTL 7 天
await redis.set(f"processed_event:{event_id}", "1", ex=7*24*3600)
```

**事件处理要求：**
- 成功率 ≥99%
- 延迟 P95 <5s
- 支持事件重放与失败重试（指数退避 + 死信队列）

### 14.8 安全分层架构

```
第一层：隔离
  • Prompt 隔离（每个 Agent 独立系统提示）
  • 工具隔离（RBAC 最小权限）
  • 数据隔离（多租户 Schema per Tenant）

第二层：执行
  • Docker 沙箱（代码执行隔离）
  • 网络白名单（仅允许可信 API）
  • 资源限制（CPU/内存/超时）

第三层：检测
  • ShieldCortex 提示注入检测
  • 视角越界检测（跨角色关键词频率 > 5%）
  • 幻觉累积检测

第四层：审计
  • 不可变存储（WORM）
  • 完整操作日志
  • 7 年保留期限（SOX 合规）

第五层：熔断
  • 辩论过热保护
  • 成本三级熔断
  • 批量熔断（防止 Agent 失控）
```

### 14.9 关键监控指标

| 指标类别 | 指标 | 告警阈值 |
|---------|------|---------|
| **性能** | CLI 命令响应延迟 | P95 > 1s |
| **性能** | Skill 加载延迟 | P95 > 500ms |
| **性能** | LLM 调用延迟 | P95 > 10s |
| **质量** | Skill 触发准确率 | < 85% |
| **质量** | 工具调用准确率 | < 90% |
| **成本** | 单次任务成本 | > 预算 200% |
| **安全** | 提示注入检测 | 准确率 < 95% |
| **可用性** | CLI 可用性 | < 99% |
| **事件** | 事件处理成功率 | < 99% |
| **事件** | 事件处理延迟 | P95 > 5s |

---

**文档版本：** 1.1.0
**最后更新：** 2026-04-12
**维护者：** Agimtech
**更新频率：** 每个 Epic 完成后复审更新
**更新记录：**
- v1.0.0: 初始版本，基于 or.md/prd.md/ux-design-specification.md/architecture.md/sdd-tdd-checklist.md/sprint-status.yaml/epics_v1.0.md
- v1.1.0: 新增 interface-design.md 整合 - 接口分层架构、CLI 命令结构、Skills 三级加载、四层映射架构、SAP 协议、REST API 端点、事件监听适配器、安全分层、监控指标
