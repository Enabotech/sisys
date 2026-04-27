# Story 0.30: 应用启动与集成

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现应用启动与事件监听器注册机制,
**So that** 多种 EventListener（MemoryChangedListener、TriggerEventListener、AutoExecuteCompletedListener 等）能够通过 AsyncRabbitMQConsumer 异步消费对应的事件。

### 业务价值

本 Story 是 Epic 0（开发基础设施）的第 30 个故事，属于应用启动与集成基础设施。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **应用入口** | 统一的 `App` 类封装生命周期 | 启动/关闭正常 |
| **依赖注入** | 手动 DI 容器装配服务 | 服务解析正确 |
| **通用事件注册** | 多种 EventListener 注册到 Consumer | 事件消费成功 |
| **优雅关闭** | SIGTERM/SIGINT 处理 | 资源正确释放 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 0: 开发基础设施

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute）和系统公理二（外部化记忆），多种 EventListener.handle() 异步消费是公理实现的必要条件

**已有事件监听器（Story 1.x）：**

| 事件监听器 | 处理事件 | Story | 状态 |
|-----------|---------|-------|------|
| MemoryChangedListener | MemoryChanged | 1.15a | ✅ 已实现 |
| TriggerEventListener | Triggered | 1.14a | ✅ 已实现 |
| AutoExecuteCompletedListener | Executed | 1.14c | ✅ 已实现 |

**前置依赖:** Story 1.3 (AsyncRabbitMQConsumer ✅), Story 1.14a (TriggerEventListener ✅), Story 1.14c (AutoExecuteCompletedListener ✅), Story 1.15a (MemoryChangedListener ✅)

**后续依赖:** Story 1.15b（六层存储协同）、Story 6.3（Checkpoint 快照创建 - L3 压缩触发）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 应用入口与生命周期管理

**Given** SISYS 应用启动
**When** 应用初始化时
**Then** 创建并配置以下组件：
  - 初始化 RabbitMQ 配置（从环境变量或配置文件）
  - 创建 `AsyncRabbitMQConsumer` 实例
  - 创建 `MemoryChangedListener` 实例（注入 SixLayerStorageCoordinator、PostgreSQL repositories）
  - 调用 `consumer.register_handler("memory.changed", listener.handle)` 注册事件处理器
  - 调用 `consumer.async_consume("memory.changed")` 启动消费
  - 优雅关闭时调用 `consumer.close()`

**验证标准/Validation Criteria:**
- [ ] App 类实现（`src/application/app.py`）
- [ ] AppConfig 配置加载（`src/application/config.py`）
- [ ] 生命周期钩子（`src/application/lifecycle.py`）
- [ ] 启动/关闭测试通过

---

### AC-2: 依赖注入容器

**Given** 应用启动
**When** 初始化服务时
**Then** 实现依赖注入容器（手动装配），提供：
  - `Container` 类 - 服务 locator
  - `register_singleton()` - 注册单例服务
  - `register_factory()` - 注册工厂服务
  - `resolve()` - 解析服务实例

**验证标准/Validation Criteria:**
- [ ] Container 类实现（`src/application/di_container.py`）
- [ ] register_singleton() 方法
- [ ] register_factory() 方法
- [ ] resolve() 方法
- [ ] DI 容器单元测试通过

---

### AC-3: MemoryService 事件发布路径

**Given** MemoryService.save() 被调用
**When** 记忆保存成功时
**Then** 事件发布路径：
  - 如果配置了 `AsyncRabbitMQPublisher`：通过 RabbitMQ 发布（生产路径）
  - 如果未配置：降级到 `InMemoryEventBus`（开发/MVP 路径）

**验证标准/Validation Criteria:**
- [ ] 事件发布路径切换逻辑
- [ ] 生产路径测试（需 Mock RabbitMQ）
- [ ] 开发路径测试（InMemoryEventBus）

---

### AC-4: 多种事件监听器注册与消费

**Given** 多种 EventListener 已实现
**When** 应用启动时
**Then** 注册所有事件监听器到 AsyncRabbitMQConsumer：
  - MemoryChangedListener → 处理 memory.changed 队列
  - TriggerEventListener → 处理 trigger.triggered 队列
  - AutoExecuteCompletedListener → 处理 execute.completed 队列

**And** Consumer 接收消息时：
  - 反序列化事件
  - 幂等性检查
  - 调用对应 listener.handle(event) 异步处理
  - 手动 ACK 确认消息

**验证标准/Validation Criteria:**
- [ ] 多种 Listener 注册测试
- [ ] 事件路由到正确 Listener 测试
- [ ] 事件消费流程集成测试

---

### AC-5: 优雅关闭

**Given** 应用收到终止信号（SIGTERM/SIGINT）
**When** 优雅关闭时
**Then** 执行：
  - 停止接受新消息
  - 等待正在处理的消息完成（超时 30 秒）
  - 关闭 RabbitMQ 连接
  - 关闭 PostgreSQL 连接池
  - 关闭 Redis 连接

**验证标准/Validation Criteria:**
- [ ] 信号处理测试
- [ ] 资源释放测试
- [ ] 超时机制测试

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] MemoryChanged 事件定义位于 `src/domain/events/memory_events.py`
- [ ] Pydantic 模型验证通过
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `MemoryChanged`）

#### API 契约 (API Contract)
- [ ] App 入口 API：`app.run()` / `app.shutdown()`
- [ ] Container API：`register_singleton()` / `register_factory()` / `resolve()`
- [ ] 契约测试通过

#### 数据模型 (Data Models)
- [ ] AppConfig 模型定义位于 `src/application/config.py`
- [ ] Container 模型定义位于 `src/application/di_container.py`

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_0_30.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_story_0_30_steps.py`（BDD 步骤实现）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 应用入口与生命周期管理 | Task 1 | Subtask 1.1-1.6 | `test_app.py` |
| AC-2 | 依赖注入容器 | Task 2 | Subtask 2.1-2.3 | `test_di_container.py` |
| AC-4 | 多种事件监听器注册 | Task 2 | Subtask 2.4-2.6 | `test_listener_registry.py` |
| AC-3 | MemoryService 事件发布路径 | Task 3 | Subtask 3.1-3.3 | `test_event_publish.py` |
| AC-4 | Consumer 事件消费 | Task 3 | Subtask 3.4-3.6 | `test_consumer_integration.py` |
| AC-5 | 优雅关闭 | Task 4 | Subtask 4.1-4.4 | `test_shutdown.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定义领域事件 Schema（MemoryChanged 事件属性：memory_id, user_id, name, change_type, is_automatic, new_value）
- [ ] Subtask 0.2: 定义数据模型（AppConfig, Container）
- [ ] Subtask 0.3: 创建 Gherkin 验收测试 `tests/acceptance/test_story_0_30.feature`
- [ ] Subtask 0.4: 创建 BDD 步骤实现 `tests/acceptance/test_story_0_30_steps.py`
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 创建应用入口与生命周期管理

**关联 AC:** AC-1, AC-5

> **[工具先行]** App 类依赖 AppConfig，需先定义配置模型。

#### TDD 循环 [A]：AppConfig 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_app_config.py`（验证配置加载） |
| 🟢 绿 | 实现 `AppConfig` 类最小代码 |
| 🔄 重构 | 添加类型注解、验证逻辑、环境变量映射 |

- [ ] Subtask 1.1: 🔴 红 — 编写 AppConfig 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 AppConfig 最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化 AppConfig 代码

#### TDD 循环 [B]：App 类生命周期

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_app.py`（验证启动/关闭流程） |
| 🟢 绿 | 实现 `App` 类最小代码 |
| 🔄 重构 | 添加生命周期钩子、信号处理 |

- [ ] Subtask 1.4: 🔴 红 — 编写 App 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 App 最小代码
- [ ] Subtask 1.6: 🔄 重构 — 优化 App 代码

**完成标准/Definition of Done:**
- [ ] AppConfig 实现完成
- [ ] App 实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥80%

---

### Task 2: 实现依赖注入容器与监听器注册表

**关联 AC:** AC-2, AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 [A]：Container 类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_di_container.py`（验证注册/解析） |
| 🟢 绿 | 实现 `Container` 类最小代码 |
| 🔄 重构 | 添加类型注解、错误处理 |

- [ ] Subtask 2.1: 🔴 红 — 编写 Container 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 Container 最小代码
- [ ] Subtask 2.3: 🔄 重构 — 优化 Container 代码

#### TDD 循环 [B]：EventListenerRegistry 类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_listener_registry.py`（验证多 Listener 注册/路由） |
| 🟢 绿 | 实现 `EventListenerRegistry` 类最小代码 |
| 🔄 重构 | 添加类型注解、错误处理 |

- [ ] Subtask 2.4: 🔴 红 — 编写 EventListenerRegistry 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 EventListenerRegistry 最小代码
- [ ] Subtask 2.6: 🔄 重构 — 优化 EventListenerRegistry 代码

**完成标准/Definition of Done:**
- [ ] Container 实现完成
- [ ] EventListenerRegistry 实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥80%

---

### Task 3: 集成多种 EventListener 到 Consumer

**关联 AC:** AC-3, AC-4

> **[集成验证]** 本 Task 验证多种 EventListener 与 AsyncRabbitMQConsumer 的通用集成。

#### TDD 循环 [A]：事件发布路径

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_publish.py`（验证路径切换） |
| 🟢 绿 | 实现事件发布路径切换逻辑 |
| 🔄 重构 | 优化代码结构 |

- [ ] Subtask 3.1: 🔴 红 — 编写事件发布路径测试
- [ ] Subtask 3.2: 🟢 绿 — 实现事件发布路径切换
- [ ] Subtask 3.3: 🔄 重构 — 优化事件发布代码

#### TDD 循环 [B]：多种事件监听器注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_listener_registration.py`（验证多 Listener 注册） |
| 🟢 绿 | 实现 EventListenerRegistry 管理多种 Listener |
| 🔄 重构 | 优化 Listener 注册代码 |

- [ ] Subtask 3.4: 🔴 红 — 编写多 Listener 注册失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现 EventListenerRegistry
- [ ] Subtask 3.6: 🔄 重构 — 优化 EventListenerRegistry 代码

#### TDD 循环 [C]：Consumer 事件消费

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_consumer_integration.py`（验证消费流程） |
| 🟢 绿 | 实现 Consumer 注册与启动 |
| 🔄 重构 | 优化 Consumer 集成代码 |

- [ ] Subtask 3.7: 🔴 红 — 编写 Consumer 集成失败测试
- [ ] Subtask 3.8: 🟢 绿 — 实现 Consumer 注册与启动
- [ ] Subtask 3.9: 🔄 重构 — 优化 Consumer 集成代码

**完成标准/Definition of Done:**
- [ ] 事件发布路径实现完成
- [ ] Consumer 集成完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥80%

---

### Task 4: 优雅关闭与资源释放

**关联 AC:** AC-5

> **[SDD 架构约束验证]** 本 Task 验证优雅关闭机制。

#### 架构验证测试实现

- [ ] Subtask 4.1: 创建 `tests/unit/application/test_shutdown.py`
- [ ] Subtask 4.2: 实现信号处理测试
- [ ] Subtask 4.3: 实现资源释放测试
- [ ] Subtask 4.4: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有优雅关闭测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（应用层可依赖基础设施层）
- **设计约束:** 领域层零依赖、依赖方向规则
- **技术栈:** Python 3.11+, aio-pika, asyncio

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **手动 DI 容器** | 简单、无外部依赖、不污染领域层 | 需要手动装配 | ✅ 8/10 |
| FastAPI 依赖注入 | 生态成熟 | 引入额外框架 | 6/10 |
| PyInjector | 功能完整 | 引入外部依赖 | 5/10 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── application/                 # [NEW] 应用层
│   │   ├── __init__.py
│   │   ├── app.py                  # App 类 - 应用入口
│   │   ├── config.py               # AppConfig - 配置加载
│   │   ├── lifecycle.py            # 生命周期钩子
│   │   ├── di_container.py         # Container - DI 容器
│   │   ├── service_assembly.py     # 服务装配
│   │   └── listener_registry.py    # [NEW] EventListenerRegistry - 监听器注册表
│   ├── infrastructure/
│   │   └── events/
│   │       └── async_rabbitmq_consumer.py  # [EXISTING] 已实现
│   └── interfaces/
│       └── event_listeners/
│           ├── memory_changed_listener.py  # [EXISTING] 已实现
│           ├── auto_route_listener.py        # [EXISTING] 已实现
│           ├── auto_trigger_listener.py        # [EXISTING] 已实现
│           └── auto_execute_completed_listener.py  # [EXISTING] 已实现
├── tests/
│   ├── unit/application/
│   │   └── test_app.py            # App 单元测试
│   │   └── test_di_container.py    # Container 单元测试
│   ├── integration/
│   │   └── test_app_lifecycle.py  # 生命周期集成测试
│   └── acceptance/
│       ├── test_story_0_30.feature    # Gherkin 场景
│       └── test_story_0_30_steps.py   # BDD 步骤实现
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Story 0-18 (用户友好配置向导)

**关键学习/Key Learnings:**
- 六边形架构严格分层映射，避免领域层污染
- 测试隔离必须使用 transaction rollback
- DI 容器设计要支持单例和工厂两种模式

**应用到本故事/Applied to This Story:**
- [ ] 应用层 DI 容器不污染领域层
- [ ] 使用 UUID 前缀隔离测试数据
- [ ] Container 支持 register_singleton 和 register_factory

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | claude-sonnet-4-6 |
| **Version** | create-story workflow v2.5.0 |
| **Execution Date** | 2026-04-27 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Template** | `docs/developer/story-template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/0-18-user-friendly-config-wizard.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/0-30-application-startup-and-integration.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/__init__.py` - 模块导出
- `src/application/app.py` - App 类核心实现
- `src/application/config.py` - AppConfig 配置加载
- `src/application/lifecycle.py` - 生命周期钩子
- `src/application/di_container.py` - Container DI 容器
- `src/application/service_assembly.py` - 服务装配
- `src/application/listener_registry.py` - EventListenerRegistry 监听器注册表
- `tests/unit/application/test_app.py` - App 单元测试
- `tests/unit/application/test_di_container.py` - Container 单元测试
- `tests/unit/application/test_listener_registry.py` - ListenerRegistry 单元测试
- `tests/integration/test_app_lifecycle.py` - 生命周期集成测试
- `tests/acceptance/test_story_0_30.feature` - Gherkin 场景
- `tests/acceptance/test_story_0_30_steps.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 0.30 |
| **Story Key** | 0-30-application-startup-and-integration |
| **File** | `_bmad-output/implementation-artifacts/stories/0-30-application-startup-and-integration.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 0: 开发基础设施 |
| **价值组** | Iteration 1 - 产品交付系统 |
| **优先级** | P0 |
| **覆盖 FR** | N/A（基础设施 Story） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [ ] Story created with `backlog` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查

---

**模板版本/Template Version:** 2.5.0
**创建日期/Created:** 2026-04-27
**最后更新/Last Updated:** 2026-04-27
