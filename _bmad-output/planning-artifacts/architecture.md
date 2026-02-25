---
stepsCompleted: [1, 2]
inputDocuments:
  - or.md
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/research/架构草稿.md
  - _bmad-output/planning-artifacts/research/technical-企业战略规划沙箱方案-research-2026-02-18.md
  - _bmad-output/planning-artifacts/research/technical-openclaw-agent-systems-research-2026-02-19.md
workflowType: 'architecture'
project_name: 'sisys'
user_name: 'Agimtech'
date: '2026-02-25'
---

# Architecture Decision Document

_本文档通过逐步协作发现创建。各章节在我们共同完成每个架构决策时追加。_

---

## 初始化完成

**欢迎 Agimtech！** 我已为您的 sisys 项目设置好架构工作区。

### 📄 已发现的输入文档

| 文档类型 | 文件 | 状态 |
|---------|------|------|
| **原始需求** | `or.md` | ✅ 已加载 (623 行) - 核心架构需求规格 |
| **PRD** | `prd.md` | ✅ 已加载 (2402 行) |
| **UX 设计** | `ux-design-specification.md` | ✅ 已加载 (1820 行) |
| **研究文档** | `架构草稿.md` | ✅ 已加载 (728 行) |
| **研究文档** | `technical-企业战略规划沙箱方案-research-2026-02-18.md` | ✅ 已加载 |
| **研究文档** | `technical-openclaw-agent-systems-research-2026-02-19.md` | ✅ 已加载 |
| **docs 文件夹** | - | ❌ 无 markdown 文件 |

---

## 项目上下文分析

### 需求概述

**功能需求分析：**

基于 or.md 和 prd.md，我们识别出 122 项功能需求，分布在 10 个核心领域：

| 功能领域 | 需求数量 | 架构含义 |
|---------|---------|---------|
| 文档与数据管理 | 15 项 (DM-01~DM-15) | 17 种格式解析、版本控制、血缘追踪、高保真溯源 |
| 智能检索与知识发现 | 15 项 (SR-01~SR-15) | 混合检索 (Dense+Sparse+Graph)、GraphRAG、分层检索 |
| 战略工具箱 | 11 项 (ST-01~ST-11) | 23 种战略工具、MCP/A2A 协议、沙箱执行 |
| Agent 协作 | 16 项 (AC-01~AC-16) | 7 种角色、弹性隔离协议 (EIP)、公共黑板、辩论机制 |
| 战略规划流程 | 12 项 (SP-01~SP-12) | BLM 六阶段、BEM 六阶段、Checkpoint 机制、Time-travel |
| 用户交互与报告 | 13 项 (UI-01~UI-13) | 三视图设计、白标输出、PPT/PDF 导出 |
| 系统管理与合规 | 14 项 (SC-01~SC-14) | RBAC、审计日志、WORM 存储、7 年保留 |
| 成本与性能优化 | 12 项 (CP-01~CP-12) | UDMR 路由、语义缓存、成本熔断 |
| 战略档案库 | 10 项 (SA-01~SA-10) | 时序档案、分支管理、向量 + 对象存储协同 |
| 架构约束 | 4 项 (AR-01~AR-04) | DDD 六边形架构、事件驱动、双公理 |

**非功能需求分析：**

39 项非功能需求分布在 7 个质量属性维度：

| 质量属性 | 需求数量 | 关键指标 | 架构影响 |
|---------|---------|---------|---------|
| 性能 | 7 项 | 检索延迟 P95<800ms、路由决策<50ms | 缓存策略、异步处理 |
| 安全性 | 7 项 | 提示注入检测≥95%、0 数据泄露 | 沙箱隔离、ShieldCortex |
| 合规性 | 8 项 | 7 年 WORM 存储、审计日志 100% 完整 | 不可变存储、事件溯源 |
| 可靠性 | 6 项 | Checkpoint 恢复<60 秒 | 快照机制、CUSUM 算法 |
| 可扩展性 | 4 项 | 并发 Agent 会话 10→50→200 | 水平扩展、容器化 |
| 集成性 | 5 项 | ERP/CRM/OA 对接 | API Gateway、事件总线 |
| 可访问性 | 2 项 | WCAG 2.1 AA | 无障碍设计、i18n |

---

### 规模与复杂度

**项目复杂度评估：** 🔴 **企业级**

| 维度 | 评估 |
|------|------|
| **主要技术领域** | 全栈 - Python 后端 + TypeScript 前端 + AI/ML 集成 |
| **架构组件估算** | ~50+ 核心组件（领域实体 9+、领域服务 8+、基础设施 15+、接口 10+、UX 组件 10+） |
| **核心复杂度驱动因素** | 多 Agent 协作、五层存储、合规审计、事件驱动、双核引擎 |

---

### 技术约束与依赖

| 约束 | 来源 | 架构影响 |
|------|------|---------|
| DDD 六边形架构 | or.md | 领域层纯净、依赖倒置、仓储模式 |
| 事件驱动架构 | or.md | 事件总线、事件溯源、CQRS |
| 本地部署优先 | prd.md | 数据境内存储、国产模型适配 |
| SOX/ISO27001 合规 | prd.md | 7 年 WORM 存储、完整审计日志 |
| Ant Design 5.x | ux-design.md | 组件选型、主题定制策略 |
| Prefect + LangGraph | 架构草稿.md | 双核引擎（数据管道 + Agent 状态机） |

---

### 跨领域关注点

| 关注点 | 影响组件 | 实现策略 |
|-------|---------|---------|
| 日志记录 | 所有组件 | OpenTelemetry + Loki 统一日志 |
| 监控 | 所有组件 | Prometheus + Grafana 指标收集 |
| 安全 | 所有组件 | 零信任架构、五层纵深防御 |
| 错误处理 | 所有组件 | 统一异常层次、熔断降级 |
| 配置管理 | 所有组件 | Pydantic Settings、环境变量注入 |
| 测试 | 所有组件 | 测试金字塔（单元 60%/集成 30%/E2E 10%） |

---

**✅ 项目上下文分析完成**

MVP 范围已在 PRD 中完整定义（23 个 P0 级指标），本架构文档将基于 PRD 的 MVP 范围进行架构决策。

---

**准备开始架构决策。**

**您希望如何进行下一步？**

**[C] 继续** - 开始架构决策阶段
