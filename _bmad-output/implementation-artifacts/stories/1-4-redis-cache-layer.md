# Story 1.4: Redis Cache Layer

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。
>
> **🔧 技术约束（v1.1 修订）：**
> 1. **复用 Story 1.3 RedisConfig** — `src/infrastructure/config/redis.py` 已定义，需扩展 `retry_on_timeout` 和 `default_ttl` 字段
> 2. **复用 Story 1.3 RedisEventPublisher 连接池** — 各存储服务共享连接池，不重复创建
> 3. **缓存数据结构位于基础设施层** — SessionState/CacheEntry/BlackboardEntry 是存储结构，非核心领域实体
> 4. **IdempotencyChecker 已在 Story 1.3 AC-4.1 定义接口** — 本 Story 仅实现基础设施层适配器

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 Redis 高速缓存层（L1 存储），
**So that** 系统可以将会话状态、语义缓存和公共黑板数据存储在高速缓存中，满足检索延迟 P95<800ms 的性能目标。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 3（五层存储架构）的第一个故事，在 Story 1.3（事件总线实现）基础上实现 L1 高速缓存层。Redis 作为五层存储架构的最上层，承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **会话状态缓存** | 支持 Agent 会话中断恢复，Checkpoint 恢复时间<60 秒 | TTL 可配置（24h-30d） |
| **语义缓存** | 相似度>0.9 的检索请求直接返回缓存结果，Token 成本节省≥30% | 命中率监控，延迟 P95<100ms |
| **公共黑板** | 多 Agent 协作时交换中间结论，支持 MVCC 并发控制 | 读写延迟 P95<50ms |
| **幂等性检查** | 基于 event_id 的 Redis `SET NX` 原子操作去重，TTL 7 天 | 并发测试通过 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 3: 五层存储架构

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Redis 连接池管理与客户端抽象

**Given** Story 1.3 已定义 `RedisConfig` (`src/infrastructure/config/redis.py`) 和 `RedisEventPublisher` 连接池
**When** 扩展 RedisConfig 并实现通用连接池管理器
**Then** 所有 Redis 服务实例（会话存储/语义缓存/公共黑板/幂等检查）共享同一连接池
**And** 连接池支持懒初始化、健康检查、优雅降级

**验证标准/Validation Criteria:**
- [ ] **扩展** `RedisConfig` 配置模型（`src/infrastructure/config/redis.py`）
  - **新增字段**: `retry_on_timeout: bool = True`, `default_ttl: int = 86400`（24 小时）
  - **向后兼容**: 保持 Story 1.3 已有字段不变
- [ ] RedisClient 通用接口定义（`src/infrastructure/storage/redis/client.py`）
  - 方法: `get_pool() -> redis.ConnectionPool`, `health_check() -> bool`, `close() -> None`
  - **不重复创建连接池**，使用单例模式或依赖注入共享
- [ ] 连接池懒初始化（首次调用时创建）
- [ ] 健康检查实现（ping/pong 检测）
- [ ] Redis 连接失败优雅降级（返回 None 或默认值，不抛出异常）
- [ ] 单元测试覆盖连接池创建、复用、关闭场景

### AC-2: 会话状态存储（Session State Storage）

**Given** Redis 连接池已实现
**When** 实现会话状态的序列化存储与恢复
**Then** 支持会话状态的保存、加载、删除
**And** TTL 自动过期（可配置 24h-30d）

**验证标准/Validation Criteria:**
- [ ] SessionState 数据模型定义（`src/infrastructure/entities/session_state.py`）
  > **📌 架构说明**: SessionState 是缓存存储结构，非核心领域实体，位于基础设施层（与 OutboxEntity 一致）
  - 字段: `session_id: str`, `agent_id: str`, `state: dict`, `created_at: datetime`, `updated_at: datetime`, `ttl: int`
- [ ] SessionStorage 接口定义（`src/domain/repositories/session_storage.py`）
  - 方法: `save(session_id, agent_id, state, ttl) -> None`, `load(session_id) -> Optional[dict]`, `delete(session_id) -> None`, `exists(session_id) -> bool`
- [ ] RedisSessionStorage 实现（`src/infrastructure/storage/redis/session_storage.py`）
  - 使用 Redis Hash 存储（`HSET/HGET/HDEL`）
  - 键命名规范: `sisys:session:{session_id}`
  - 自动设置 TTL（`EXPIRE` 命令）
- [ ] JSON 序列化/反序列化（处理 datetime、UUID 等类型）
- [ ] 会话不存在时返回 None（不抛出异常）
- [ ] 单元测试覆盖保存、加载、删除、过期场景

### AC-3: 语义缓存服务（Semantic Cache）

**Given** 会话状态存储已实现
**When** 实现基于查询相似度的语义缓存
**Then** 相似度>0.9 的检索请求直接返回缓存结果
**And** 缓存命中率纳入可观测性指标

**验证标准/Validation Criteria:**
- [ ] CacheEntry 数据模型定义（`src/infrastructure/entities/cache_entry.py`）
  > **📌 架构说明**: CacheEntry 是缓存存储结构，非核心领域实体，位于基础设施层
  - 字段: `cache_key: str`, `query_embedding: list[float]`, `result: dict`, `similarity_threshold: float`, `created_at: datetime`, `ttl: int`
- [ ] SemanticCache 接口定义（`src/domain/services/semantic_cache.py`）
  - 方法: `get(query_embedding: list[float], threshold: float = 0.9) -> Optional[dict]`, `set(query_embedding: list[float], result: dict, ttl: int) -> None`, `invalidate(cache_key: str) -> None`
- [ ] RedisSemanticCache 实现（`src/infrastructure/storage/redis/semantic_cache.py`）
  - 使用 Redis Hash 存储嵌入向量和结果
  - 键命名规范: `sisys:cache:semantic:{cache_key}`
  - **余弦相似度计算使用纯 Python 实现**（项目技术栈不含 numpy，避免额外依赖）
- [ ] 缓存未命中时返回 None（触发正常检索流程）
- [ ] 缓存命中率统计（`hits`, `misses`, `hit_rate`）
- [ ] 单元测试覆盖命中、未命中、过期、失效场景

### AC-4: 公共黑板服务（Public Blackboard）

**Given** 语义缓存服务已实现
**When** 实现多 Agent 协作的公共黑板
**Then** 支持 Agent 间交换中间结论（附带置信度与引用源）
**And** 支持 MVCC 并发控制（读写不阻塞）

**验证标准/Validation Criteria:**
- [ ] BlackboardEntry 数据模型定义（`src/infrastructure/entities/blackboard_entry.py`）
  > **📌 架构说明**: BlackboardEntry 是缓存存储结构，非核心领域实体，位于基础设施层
  - 字段: `conversation_id: str`, `agent_id: str`, `content: dict`, `confidence: float`, `citations: list`, `timestamp: datetime`, `version: int`
- [ ] PublicBlackboard 接口定义（`src/domain/services/public_blackboard.py`）
  - 方法: `post(conversation_id, agent_id, content, confidence, citations) -> int`（返回版本号）, `get(conversation_id) -> list[dict]`, `get_by_agent(conversation_id, agent_id) -> Optional[dict]`, `get_latest(conversation_id) -> Optional[dict]`
- [ ] RedisPublicBlackboard 实现（`src/infrastructure/storage/redis/public_blackboard.py`）
  - 使用 Redis Sorted Set 存储（按 timestamp 排序）
  - 键命名规范: `sisys:blackboard:{conversation_id}`
  - MVCC: 每次写入自增版本号
- [ ] 并发写入测试通过（多 Agent 同时写入不丢失数据）
- [ ] 单元测试覆盖发布、读取、版本冲突场景

### AC-5: 幂等性检查器（IdempotencyChecker）

**Given** Story 1.3 AC-4.1 已定义 IdempotencyChecker 接口策略
**When** 实现基于 Redis `SET NX` 原子操作的幂等性检查基础设施层适配器
**Then** 重复处理相同 event_id 的事件时仅处理一次
**And** TTL 7 天自动过期

**验证标准/Validation Criteria:**
- [ ] IdempotencyChecker 基础设施层实现（`src/infrastructure/storage/redis/idempotency_checker.py`）
  > **📌 复用说明**: Story 1.3 AC-4.1 已定义接口策略，本 Story 实现基础设施层适配器
  - **仅实现** `try_acquire(event_id: UUID, ttl: int = 7*24*3600) -> bool`
  - 使用 `SET key value NX EX ttl` 原子操作
  - 返回 True=首次处理，False=已处理
- [ ] **禁止实现** `is_processed()` + `mark_processed()` 分离方法（避免 Check-Then-Act 竞态条件）
- [ ] 并发测试通过（模拟多消费者同时消费同一 event_id，仅处理一次）
- [ ] Redis 不可用时优雅降级（返回 True，允许处理）

### AC-6: Redis 键命名规范与清理机制

**Given** 所有 Redis 存储服务已实现
**When** 实现统一的键命名规范与清理工具
**Then** 所有 Redis 键遵循 `sisys:{namespace}:{key}` 格式
**And** 支持按命名空间批量清理

**验证标准/Validation Criteria:**
- [ ] RedisKeyBuilder 工具类实现（`src/infrastructure/storage/redis/key_builder.py`）
  - 方法: `build_key(namespace: str, *parts: str) -> str`
  - 示例: `build_key("session", "abc-123")` → `"sisys:session:abc-123"`
- [ ] RedisCleanup 工具类实现（`src/infrastructure/storage/redis/cleanup.py`）
  - 方法: `cleanup_namespace(namespace: str) -> int`（返回删除的键数量）
  - 使用 `SCAN` 命令（不阻塞 Redis，替代 `KEYS`）
- [ ] 所有存储服务使用 KeyBuilder 构建键名
- [ ] 单元测试覆盖键构建、批量清理、空命名空间场景

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 数据模型 (Data Models)
- [ ] SessionState 定义（`src/infrastructure/entities/session_state.py`）
  - 字段: session_id, agent_id, state, created_at, updated_at, ttl
- [ ] CacheEntry 定义（`src/infrastructure/entities/cache_entry.py`）
  - 字段: cache_key, query_embedding, result, similarity_threshold, created_at, ttl
- [ ] BlackboardEntry 定义（`src/infrastructure/entities/blackboard_entry.py`）
  - 字段: conversation_id, agent_id, content, confidence, citations, timestamp, version

#### 仓储/服务接口 (Repository/Service Interfaces)
- [ ] SessionStorage 接口（`src/domain/repositories/session_storage.py`）
- [ ] SemanticCache 接口（`src/domain/services/semantic_cache.py`）
- [ ] PublicBlackboard 接口（`src/domain/services/public_blackboard.py`）

#### 配置模型 (Configuration Models)
- [ ] **扩展** RedisConfig（`src/infrastructure/config/redis.py`）
  - **新增字段**: `retry_on_timeout: bool = True`, `default_ttl: int = 86400`
  - **向后兼容**: 保持 Story 1.3 已有字段不变

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.4.feature`
- [ ] 覆盖场景:
  - 会话状态保存与恢复
  - 语义缓存命中与未命中
  - 公共黑板多 Agent 并发写入
  - 幂等性检查（重复 event_id 仅处理一次）
  - Redis 连接失败优雅降级

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | Redis 连接池 | 连接池创建、复用、关闭 | `test_redis_client.py` | Task 1 |
| **TDD 单元测试** | 会话状态存储 | 保存、加载、删除、过期 | `test_session_storage.py` | Task 2 |
| **TDD 单元测试** | 语义缓存 | 命中、未命中、过期、失效 | `test_semantic_cache.py` | Task 3 |
| **TDD 单元测试** | 公共黑板 | 发布、读取、版本冲突 | `test_public_blackboard.py` | Task 4 |
| **TDD 单元测试** | 幂等性检查 | 原子性获取、并发安全 | `test_idempotency_checker.py` | Task 5 |
| **TDD 单元测试** | 键命名规范 | 键构建、批量清理 | `test_key_builder.py`, `test_cleanup.py` | Task 6 |
| **TDD 集成测试** | Redis 端到端 | 完整存储/读取流程 | `test_redis_integration.py` | Task 7 |
| **SDD 架构验证** | 基础设施层覆盖率 | 基础设施层覆盖率≥75% | `test_coverage.py` | Task 8 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- **P1 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**（接口定义）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

> ⚠️ **骨架 Story 覆盖率豁免：** 如果本 Story 为架构骨架（Skeleton），大量代码为空接口/占位类/`__init__.py`，
> 无法达到上述覆盖率指标。**请将覆盖率要求临时调整为：整体≥30%，基础设施层≥50%。**
> 从下一个非骨架 Story 开始恢复标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Redis 连接池与客户端实现 | Task 1 | RedisConfig + RedisClient | `test_redis_client.py` |
| AC-2 | 会话状态存储 | Task 2 | SessionStorage 接口 + RedisSessionStorage | `test_session_storage.py` |
| AC-3 | 语义缓存服务 | Task 3 | SemanticCache 接口 + RedisSemanticCache | `test_semantic_cache.py` |
| AC-4 | 公共黑板服务 | Task 4 | PublicBlackboard 接口 + RedisPublicBlackboard | `test_public_blackboard.py` |
| AC-5 | 幂等性检查器 | Task 5 | IdempotencyChecker 实现 | `test_idempotency_checker.py` |
| AC-6 | Redis 键命名规范与清理 | Task 6 | RedisKeyBuilder + RedisCleanup | `test_key_builder.py`, `test_cleanup.py` |
| AC-1~AC-6 | Redis 端到端集成测试 | Task 7 | 完整存储/读取流程验证 | `test_redis_integration.py` |
| AC-6 | 架构约束验证 | Task 8 | 基础设施层覆盖率验证 | `test_coverage.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-6

> **目的：** 在进入代码实现前，明确数据模型、接口、配置、验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask: 定义 SessionState 数据模型
- [ ] Subtask: 定义 CacheEntry 数据模型
- [ ] Subtask: 定义 BlackboardEntry 数据模型
- [ ] Subtask: 定义 SessionStorage 接口
- [ ] Subtask: 定义 SemanticCache 接口
- [ ] Subtask: 定义 PublicBlackboard 接口
- [ ] Subtask: 定义 RedisConfig 配置模型
- [ ] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.4.feature`
- [ ] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Redis 连接池管理与客户端抽象

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 复用说明:** Story 1.3 已定义 `RedisConfig`，本 Task 仅扩展字段并实现通用连接池管理器。

#### TDD 循环 A：扩展 RedisConfig 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_redis_config_extension.py`（新字段验证、向后兼容测试） |
| 🟢 绿 | 扩展 `RedisConfig` 添加 `retry_on_timeout` 和 `default_ttl` 字段 |
| 🔄 重构 | 添加类型注解、docstring、from_env 支持 |

- [ ] Subtask: 🔴 红 — 编写 RedisConfig 扩展字段失败测试
- [ ] Subtask: 🟢 绿 — 扩展 RedisConfig 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisConfig 代码

#### TDD 循环 B：RedisClient 通用连接池管理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_redis_client.py`（连接池获取、健康检查、关闭） |
| 🟢 绿 | 实现 `RedisClient` 类（单例模式/依赖注入共享连接池） |
| 🔄 重构 | 添加连接池懒初始化、异常处理、优雅降级 |

- [ ] Subtask: 🔴 红 — 编写 RedisClient 失败测试
- [ ] Subtask: 🟢 绿 — 实现 RedisClient 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisClient 代码

**完成标准/Definition of Done:**
- [ ] RedisConfig 扩展字段和 RedisClient 实现完成
- [ ] TDD 循环全部通过
- [ ] **向后兼容验证**: Story 1.3 的 RedisEventPublisher 仍正常工作
- [ ] 基础设施层覆盖率≥10%

---

### Task 2: 会话状态存储（Session State Storage）

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：SessionState 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_session_state.py`（字段验证、序列化/反序列化） |
| 🟢 绿 | 实现 `SessionState` dataclass 最小代码（`src/infrastructure/entities/session_state.py`） |
| 🔄 重构 | 添加 datetime/UUID 序列化支持 |

- [ ] Subtask: 🔴 红 — 编写 SessionState 失败测试
- [ ] Subtask: 🟢 绿 — 实现 SessionState 最小代码
- [ ] Subtask: 🔄 重构 — 优化 SessionState 代码

#### TDD 循环 B：SessionStorage 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写接口定义验证测试（Protocol 类型检查） |
| 🟢 绿 | 实现 `SessionStorage` Protocol 接口（`src/domain/repositories/session_storage.py`） |
| 🔄 重构 | 添加类型注解、docstring |

- [ ] Subtask: 🔴 红 — 编写 SessionStorage 接口
- [ ] Subtask: 🟢 绿 — 验证接口类型检查通过
- [ ] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 C：RedisSessionStorage 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_session_storage.py`（保存、加载、删除、过期） |
| 🟢 绿 | 实现 `RedisSessionStorage` 类最小代码 |
| 🔄 重构 | 添加 JSON 序列化、TTL 控制、异常处理 |

- [ ] Subtask: 🔴 红 — 编写 RedisSessionStorage 失败测试
- [ ] Subtask: 🟢 绿 — 实现 RedisSessionStorage 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisSessionStorage 代码

**完成标准/Definition of Done:**
- [ ] SessionState、SessionStorage 接口、RedisSessionStorage 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥25%

---

### Task 3: 语义缓存服务（Semantic Cache）

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：CacheEntry 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_cache_entry.py`（字段验证、嵌入向量存储） |
| 🟢 绿 | 实现 `CacheEntry` dataclass 最小代码（`src/infrastructure/entities/cache_entry.py`） |
| 🔄 重构 | 添加嵌入向量序列化支持 |

- [ ] Subtask: 🔴 红 — 编写 CacheEntry 失败测试
- [ ] Subtask: 🟢 绿 — 实现 CacheEntry 最小代码
- [ ] Subtask: 🔄 重构 — 优化 CacheEntry 代码

#### TDD 循环 B：SemanticCache 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写接口定义验证测试 |
| 🟢 绿 | 实现 `SemanticCache` Protocol 接口（`src/domain/services/semantic_cache.py`） |
| 🔄 重构 | 添加类型注解、docstring |

- [ ] Subtask: 🔴 红 — 编写 SemanticCache 接口
- [ ] Subtask: 🟢 绿 — 验证接口类型检查通过
- [ ] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 C：RedisSemanticCache 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_semantic_cache.py`（命中、未命中、相似度计算） |
| 🟢 绿 | 实现 `RedisSemanticCache` 类最小代码 |
| 🔄 重构 | 添加余弦相似度（纯 Python）、缓存命中率统计、异常处理 |

- [ ] Subtask: 🔴 红 — 编写 RedisSemanticCache 失败测试
- [ ] Subtask: 🟢 绿 — 实现 RedisSemanticCache 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisSemanticCache 代码

**完成标准/Definition of Done:**
- [ ] CacheEntry、SemanticCache 接口、RedisSemanticCache 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥40%

---

### Task 4: 公共黑板服务（Public Blackboard）

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：BlackboardEntry 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_blackboard_entry.py`（字段验证、版本号自增） |
| 🟢 绿 | 实现 `BlackboardEntry` dataclass 最小代码（`src/infrastructure/entities/blackboard_entry.py`） |
| 🔄 重构 | 添加 citations 序列化支持 |

- [ ] Subtask: 🔴 红 — 编写 BlackboardEntry 失败测试
- [ ] Subtask: 🟢 绿 — 实现 BlackboardEntry 最小代码
- [ ] Subtask: 🔄 重构 — 优化 BlackboardEntry 代码

#### TDD 循环 B：PublicBlackboard 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写接口定义验证测试 |
| 🟢 绿 | 实现 `PublicBlackboard` Protocol 接口（`src/domain/services/public_blackboard.py`） |
| 🔄 重构 | 添加类型注解、docstring |

- [ ] Subtask: 🔴 红 — 编写 PublicBlackboard 接口
- [ ] Subtask: 🟢 绿 — 验证接口类型检查通过
- [ ] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 C：RedisPublicBlackboard 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_public_blackboard.py`（发布、读取、并发写入） |
| 🟢 绿 | 实现 `RedisPublicBlackboard` 类最小代码 |
| 🔄 重构 | 添加 Sorted Set 操作、MVCC 版本控制、并发测试 |

- [ ] Subtask: 🔴 红 — 编写 RedisPublicBlackboard 失败测试
- [ ] Subtask: 🟢 绿 — 实现 RedisPublicBlackboard 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisPublicBlackboard 代码

**完成标准/Definition of Done:**
- [ ] BlackboardEntry、PublicBlackboard 接口、RedisPublicBlackboard 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥55%

---

### Task 5: 幂等性检查器（IdempotencyChecker）

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环。**
> **关键约束：** 必须使用原子方法 `try_acquire()`，禁止实现 `is_processed()` + `mark_processed()` 分离方法。

#### TDD 循环 A：IdempotencyChecker 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_idempotency_checker.py`（原子性获取、并发安全） |
| 🟢 绿 | 实现 `IdempotencyChecker` 类最小代码 |
| 🔄 重构 | 添加 `SET NX EX` 原子操作、TTL 控制、Redis 不可用降级 |

- [ ] Subtask: 🔴 红 — 编写 IdempotencyChecker 失败测试
- [ ] Subtask: 🟢 绿 — 实现 IdempotencyChecker 最小代码
- [ ] Subtask: 🔄 重构 — 优化 IdempotencyChecker 代码

**完成标准/Definition of Done:**
- [ ] IdempotencyChecker 实现完成
- [ ] TDD 循环全部通过
- [ ] 并发测试通过（多消费者同时消费同一 event_id，仅处理一次）
- [ ] 基础设施层覆盖率≥60%

---

### Task 6: Redis 键命名规范与清理机制

**关联 AC:** AC-6

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：RedisKeyBuilder 工具类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_key_builder.py`（键构建、格式验证） |
| 🟢 绿 | 实现 `RedisKeyBuilder` 类最小代码 |
| 🔄 重构 | 添加命名空间验证、特殊字符处理 |

- [ ] Subtask: 🔴 红 — 编写 RedisKeyBuilder 失败测试
- [ ] Subtask: 🟢 绿 — 实现 RedisKeyBuilder 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisKeyBuilder 代码

#### TDD 循环 B：RedisCleanup 工具类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_cleanup.py`（批量清理、空命名空间） |
| 🟢 绿 | 实现 `RedisCleanup` 类最小代码 |
| 🔄 重构 | 添加 `SCAN` 命令、分批处理、进度统计 |

- [ ] Subtask: 🔴 红 — 编写 RedisCleanup 失败测试
- [ ] Subtask: 🟢 绿 — 实现 RedisCleanup 最小代码
- [ ] Subtask: 🔄 重构 — 优化 RedisCleanup 代码

**完成标准/Definition of Done:**
- [ ] RedisKeyBuilder 和 RedisCleanup 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥70%

---

### Task 7: Redis 端到端集成测试

**关联 AC:** AC-1 ~ AC-6

> **性质说明：** 本 Task 是集成测试，验证所有 Redis 服务的端到端流程。

#### 集成测试实现

- [ ] Subtask: 创建 `tests/integration/test_redis_integration.py`
- [ ] Subtask: 实现会话状态端到端测试（保存→加载→验证→删除）
- [ ] Subtask: 实现语义缓存端到端测试（写入→命中→过期→失效）
- [ ] Subtask: 实现公共黑板端到端测试（多 Agent 并发写入→读取验证）
- [ ] Subtask: 实现幂等性检查端到端测试（并发 event_id 仅处理一次）
- [ ] Subtask: 实现 Redis 连接失败降级测试（服务优雅降级）

**完成标准/Definition of Done:**
- [ ] 所有集成测试通过
- [ ] 测试输出完整的流程验证报告
- [ ] 基础设施层覆盖率≥75%

---

### Task 8: 架构约束验证测试

**关联 AC:** AC-6

> **性质说明：** 本 Task 验证 Redis 缓存层实现是否符合六边形架构约束。

#### 架构验证测试实现

- [ ] Subtask: 创建 `tests/unit/infrastructure/test_architecture_constraints.py`
- [ ] Subtask: 实现领域层零依赖验证（领域层不导入 redis 库）
- [ ] Subtask: 实现依赖方向验证（使用 `import-linter`）
- [ ] Subtask: 实现 Redis 键命名规范验证（所有键遵循 `sisys:{namespace}:{key}`）
- [ ] Subtask: 运行 Ruff 检查（`ruff check src/`，0 错误）
- [ ] Subtask: 运行 MyPy 类型检查（`mypy src/`，0 问题）

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **五层存储架构:** L1 高速缓存层（Redis 7.0+）存储会话状态、语义缓存、公共黑板
- **TTL 规划:** 会话状态 24h-30d，语义缓存 24h，公共黑板 7d，幂等性检查 7d
- **容量规划:** Redis 10GB（MVP），可根据实际使用情况扩容
- **Redis 连接池:** 连接池共享，最大连接数可配置，socket_timeout 可配置
- **领域层零依赖:** 领域层仅定义接口，不依赖任何 Redis 实现细节

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 4 (ADR-004): 五层存储架构

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Redis 7.0+** | 高性能、丰富数据结构、连接池、TTL 自动过期 | 内存成本较高 | ✅ 9/10 |
| Memcached | 简单、纯内存缓存 | 功能单一、无持久化、无丰富数据结构 | 6/10 |
| 本地缓存 | 零网络延迟 | 无法跨进程共享、不支持分布式系统 | 4/10 |

**决策理由：**
1. Redis 支持 Hash、Sorted Set、List 等丰富数据结构，满足会话状态、公共黑板、语义缓存等不同场景
2. 内置 TTL 自动过期机制，无需手动管理缓存失效
3. 支持连接池复用，降低连接建立开销
4. 持久化能力（RDB/AOF）支持缓存数据恢复

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── repositories/
│   │   │   └── session_storage.py      # SessionStorage 接口
│   │   └── services/
│   │       ├── semantic_cache.py       # SemanticCache 接口
│   │       └── public_blackboard.py    # PublicBlackboard 接口
│   └── infrastructure/
│       ├── config/
│       │   └── redis.py                # RedisConfig 配置模型（扩展 Story 1.3）
│       ├── entities/
│       │   ├── session_state.py        # SessionState 数据模型
│       │   ├── cache_entry.py          # CacheEntry 数据模型
│       │   └── blackboard_entry.py     # BlackboardEntry 数据模型
│       └── storage/
│           └── redis/
│               ├── __init__.py
│               ├── client.py           # RedisClient 通用连接池管理器
│               ├── session_storage.py  # RedisSessionStorage 实现
│               ├── semantic_cache.py   # RedisSemanticCache 实现
│               ├── public_blackboard.py # RedisPublicBlackboard 实现
│               ├── idempotency_checker.py # IdempotencyChecker 实现
│               ├── key_builder.py      # RedisKeyBuilder 工具类
│               └── cleanup.py          # RedisCleanup 工具类
├── tests/
│   ├── unit/
│   │   ├── infrastructure/
│   │   │   ├── test_redis_config_extension.py  # RedisConfig 扩展字段测试
│   │   │   ├── test_redis_client.py
│   │   │   ├── test_session_state.py
│   │   │   ├── test_session_storage.py
│   │   │   ├── test_cache_entry.py
│   │   │   ├── test_semantic_cache.py
│   │   │   ├── test_blackboard_entry.py
│   │   │   ├── test_public_blackboard.py
│   │   │   ├── test_idempotency_checker.py
│   │   │   ├── test_key_builder.py
│   │   │   ├── test_cleanup.py
│   │   │   └── test_architecture_constraints.py
│   │   └── domain/
│   │       ├── test_session_storage_interface.py
│   │       ├── test_semantic_cache_interface.py
│   │       └── test_public_blackboard_interface.py
│   ├── integration/
│   │   └── test_redis_integration.py
│   └── acceptance/
│       └── test_story_1.4.feature
└── docs/
    └── infrastructure/
        └── redis_cache_guide.md        # Redis 缓存层实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.3-事件总线实现](./1-3-event-bus-implementation.md)

**关键学习/Key Learnings:**
1. **Redis 连接池生命周期管理** — 每个 Redis 服务实例独立管理连接池，应用层负责关闭时调用 `close()`
2. **领域层接口与基础设施层实现分离** — 领域层定义同步接口，基础设施层实现异步接口，应用层决定调用方式
3. **幂等性检查必须使用原子操作** — `SET NX` 原子操作替代分离的 `is_processed()` + `mark_processed()`，避免 Check-Then-Act 竞态条件
4. **OutboxEntity 位于基础设施层** — 领域层不依赖具体存储实现，通过仓储接口访问

**应用到本故事/Applied to This Story:**
- [ ] Redis 连接池采用 Story 1.3 相同的生命周期管理模式
- [ ] 所有存储服务遵循领域层接口/基础设施层实现分离模式
- [ ] IdempotencyChecker 直接使用 Story 1.3 定义的原子操作策略
- [ ] Redis 键命名规范统一为 `sisys:{namespace}:{key}`

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-13 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-3-event-bus-implementation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-4-redis-cache-layer.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/config/redis.py` — **扩展** RedisConfig（新增 `retry_on_timeout`, `default_ttl`）
- `src/infrastructure/entities/session_state.py` — SessionState 数据模型
- `src/infrastructure/entities/cache_entry.py` — CacheEntry 数据模型
- `src/infrastructure/entities/blackboard_entry.py` — BlackboardEntry 数据模型
- `src/domain/repositories/session_storage.py` — SessionStorage 接口
- `src/domain/services/semantic_cache.py` — SemanticCache 接口
- `src/domain/services/public_blackboard.py` — PublicBlackboard 接口
- `src/infrastructure/storage/redis/client.py` — RedisClient 通用连接池管理器
- `src/infrastructure/storage/redis/session_storage.py` — RedisSessionStorage 实现
- `src/infrastructure/storage/redis/semantic_cache.py` — RedisSemanticCache 实现
- `src/infrastructure/storage/redis/public_blackboard.py` — RedisPublicBlackboard 实现
- `src/infrastructure/storage/redis/idempotency_checker.py` — IdempotencyChecker 实现
- `src/infrastructure/storage/redis/key_builder.py` — RedisKeyBuilder 工具类
- `src/infrastructure/storage/redis/cleanup.py` — RedisCleanup 工具类
- `tests/unit/infrastructure/test_redis_config_extension.py` — RedisConfig 扩展字段测试
- `tests/unit/infrastructure/test_redis_client.py` — RedisClient 单元测试
- `tests/unit/infrastructure/test_session_state.py` — SessionState 单元测试
- `tests/unit/infrastructure/test_session_storage.py` — RedisSessionStorage 单元测试
- `tests/unit/infrastructure/test_cache_entry.py` — CacheEntry 单元测试
- `tests/unit/infrastructure/test_semantic_cache.py` — RedisSemanticCache 单元测试
- `tests/unit/infrastructure/test_blackboard_entry.py` — BlackboardEntry 单元测试
- `tests/unit/infrastructure/test_public_blackboard.py` — RedisPublicBlackboard 单元测试
- `tests/unit/infrastructure/test_idempotency_checker.py` — IdempotencyChecker 单元测试
- `tests/unit/infrastructure/test_key_builder.py` — RedisKeyBuilder 单元测试
- `tests/unit/infrastructure/test_cleanup.py` — RedisCleanup 单元测试
- `tests/unit/infrastructure/test_architecture_constraints.py` — 架构约束验证测试
- `tests/unit/domain/test_session_storage_interface.py` — SessionStorage 接口验证
- `tests/unit/domain/test_semantic_cache_interface.py` — SemanticCache 接口验证
- `tests/unit/domain/test_public_blackboard_interface.py` — PublicBlackboard 接口验证
- `tests/integration/test_redis_integration.py` — Redis 端到端集成测试
- `tests/acceptance/test_story_1.4.feature` — Gherkin 验收测试
- `docs/infrastructure/redis_cache_guide.md` — Redis 缓存层实施指南

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.4 |
| **Story Key** | 1-4-redis-cache-layer |
| **File** | `_bmad-output/implementation-artifacts/stories/1-4-redis-cache-layer.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 3: 五层存储架构 |
| **优先级** | P0 |
| **覆盖 FR** | FR-AR-04 (仓储模式), FR-SA-01 (永久存储基础) |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-13
**最后更新/Last Updated:** 2026-04-13
**更新说明:** 基于 Story 1.3 学习经验，实现 L1 高速缓存层（Redis 7.0+），遵循六边形架构和 SDD+TDD 融合模式
