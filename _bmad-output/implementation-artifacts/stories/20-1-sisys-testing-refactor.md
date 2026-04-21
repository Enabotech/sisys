# Story 20-1: SISYS 测试工程重构

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。

---

## 📖 Story 描述

**As a** 测试工程师,
**I want** 按照 `sisys-testing-framework.md` 的"四、详细实施计划 (Checklist)" 重构测试系统,
**So that** 解决测试隔离、环境适配和测试可靠性问题，实现 100% 测试通过率。

### 业务价值

本 Story 是测试工程基础设施重构，核心目标：
- **Phase 1**: 紧急修复 3 个致命测试失败 (P1/P2/P6)
- **Phase 2**: 建立测试环境管理层 (environments.py + docker-compose.test.yml)
- **Phase 3**: 建立测试隔离层 (isolation.py + fixtures.py)
- **Phase 4**: 中期验证紧急修复 + 最终验证完整回归
- **Phase 5-8**: 全面重构 4 个测试目录，实现租户隔离和配置标准化

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Phase 1 紧急修复 - 测试失败问题解决

**Given** 本地/CI 环境运行验收测试
**When** 执行 `test_ac2_rabbitmq_documentprocessed`、`test_ac2_rabbitmq_agentdecided`、`test_dense_search_with_filter`
**Then** 这 3 个测试全部通过

**验证标准/Validation Criteria:**
- [ ] `tests/acceptance/test_story_1_3_steps.py` 实现 `temporary_consumer` 异步上下文管理器
- [ ] `tests/acceptance/test_story_1_6_steps.py` 的 `collection_has_different_domains` 添加 `create_collection()` 调用
- [ ] 删除 `scope=module` 的 `event_loop` fixture，使用 pytest-asyncio auto mode

---

### AC-2: Phase 2 环境标准化 - 测试环境管理层建立

**Given** 测试环境配置
**When** 在 Local/CI/K8s 三种环境运行测试
**Then** 自动适配正确的服务连接参数

**验证标准/Validation Criteria:**
- [ ] `tests/environments.py` 实现 `TestEnvironment` 枚举和 `resolve_env()` 函数
- [ ] `TestEnvConfig` 包含 6 个服务 (Redis/PostgreSQL/Qdrant/MinIO/Neo4j/RabbitMQ) 的连接配置
- [ ] `deploy/app/docker-compose.test.yml` 创建，使用测试专用端口
- [ ] CI workflow 设置 `SISYS_TEST_ENV=ci` 让 `environments.py` 自动检测

---

### AC-3: Phase 3 测试隔离 - 租户隔离层建立

**Given** 测试租户隔离机制
**When** 多个测试并行执行 (`pytest -n 4`)
**Then** 测试资源通过 UUID 前缀隔离，无冲突

**验证标准/Validation Criteria:**
- [ ] `tests/isolation.py` 实现 `TestTenant`、`TenantContext`、`generate_test_tenant()`
- [ ] `tests/fixtures.py` 实现 `test_tenant`、`isolated_tenant`、`tenant_context` fixtures
- [ ] `_cleanup_tenant_resources()` 清理所有 6 个服务的测试资源
- [ ] `reset_test_environment` fixture 自动重置全局状态
- [ ] `TenantAwareMock` 类自动添加租户前缀

---

### AC-4: Phase 5 tests/acceptance/ 重构 - 12 个 BDD 文件全面隔离

**Given** 验收测试目录重构
**When** 运行 `tests/acceptance/` 全部测试
**Then** 所有测试使用租户隔离，无状态污染

**验证标准/Validation Criteria:**
- [ ] A1: 所有 fixtures 为 `scope=function`（非 module/session）
- [ ] A2: `test_story_1_3_steps.py` 使用 `temporary_consumer` + UUID 队列名
- [ ] A3: `test_story_1_6_steps.py` 使用 UUID collection 名
- [ ] A4: 所有队列名添加租户前缀 `test_{uuid}_queue`
- [ ] A5: 所有 Redis keys 添加租户前缀 `test:{uuid}:`
- [ ] A6: 所有 Qdrant collections 添加租户前缀 `test_{uuid}_`
- [ ] A7: pytest-asyncio `asyncio_mode = "auto"` 配置正确
- [ ] A8: `reset_test_environment` fixture 存在
- [ ] A9: `temporary_consumer` 使用 UUID 独立队列名
- [ ] A10: 并行执行 `-n 4` 无冲突

---

### AC-5: Phase 6 tests/integration/ 重构 - 15 个 mock 文件验证

**Given** 集成测试目录重构
**When** 运行 `tests/integration/` 全部测试
**Then** 所有 mock 正确使用，状态隔离

**验证标准/Validation Criteria:**
- [ ] I1: 使用 `fakeredis` 而非真实 Redis
- [ ] I2: fixtures 为 `scope=function`
- [ ] I3: PostgreSQL mock 正确
- [ ] I4: `reset_test_environment` fixture 存在
- [ ] I5: `mock_redis` 每个测试后清理
- [ ] I6: `in_memory_store` 状态隔离
- [ ] I7: IdempotencyChecker mock 正确
- [ ] I8: RetryPolicy 测试参数正确

---

### AC-6: Phase 7 tests/integration_real/ 重构 - 6 个真实服务文件标准化

**Given** 真实服务集成测试目录重构
**When** 运行 `tests/integration_real/` 全部测试
**Then** 使用统一环境配置，资源隔离

**验证标准/Validation Criteria:**
- [ ] R1: `conftest.py` 使用 `tests/environments.py`
- [ ] R2: 连接池为 `scope=function`（非 session）
- [ ] R3: 资源清理正确实现
- [ ] R4: Qdrant collection 添加 UUID 前缀
- [ ] R5: Redis keys 添加 UUID 前缀
- [ ] R6: PostgreSQL schema 清理正确
- [ ] R7: 连接配置使用 `get_test_env()`

---

### AC-7: Phase 8 tests/unit/ 重构 - 70 个单元测试检查

**Given** 单元测试目录重构
**When** 运行 `tests/unit/` 全部测试
**Then** 测试正确使用 mock，无泄露

**验证标准/Validation Criteria:**
- [ ] U1: 使用 mock 而非真实服务
- [ ] U2: fixture scope 正确
- [ ] U3: mock 清理正确
- [ ] U4: 无泄露到真实服务
- [ ] U5: async mock 使用 `AsyncMock`
- [ ] U6: pytest.mark 标记正确

---

### AC-8: Phase 4 验证 - 完整回归测试通过

**Given** 完整测试套件
**When** 运行完整验收测试 (本地 + CI)
**Then** 测试通过率 100%

**验证标准/Validation Criteria:**
- [ ] 本地运行 `tests/acceptance/` 全部通过
- [ ] CI pipeline 运行完整测试通过
- [ ] 之前失败的 3 个测试全部通过
- [ ] 并行执行 `-n 4` 无冲突
- [ ] 架构约束验证测试通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束:** 每个 Task 必须独立完成完整的 TDD 循环 (红→绿→重构)

### TDD 循环约束

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 编写失败测试 | `pytest` 运行失败 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码 | `ruff check` + `mypy` + `pytest` 全部通过 |

---

## 📊 AC → Task 追溯矩阵

| AC | 来源 Phase | 关联 Task | 优先级 |
|----|-----------|-----------|--------|
| AC-1 | Phase 1 (P1/P2/P6) | Task 1 | P0 紧急 |
| AC-2 | Phase 2 (P3/P5) | Task 2 | P1 高 |
| AC-3 | Phase 3 (P4) | Task 3 | P1 高 |
| AC-8 | Phase 4 (中期验证) | Task 4 | P0 紧急 |
| AC-4 | Phase 5 (A1-A10) | Task 5 | P1 高 |
| AC-5 | Phase 6 (I1-I8) | Task 6 | P2 中 |
| AC-6 | Phase 7 (R1-R7) | Task 7 | P2 中 |
| AC-7 | Phase 8 (U1-U6) | Task 8 | P3 低 |
| AC-8 | Phase 4 (最终验证) | Task 9 | P0 紧急 |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 1: Phase 1 紧急修复 (P1/P2/P6) — 预计 1-2 天

**关联 AC:** AC-1

#### TDD 循环 [P1]: 修复 async_consume() 阻塞

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 确认 `test_ac2_rabbitmq_documentprocessed` 失败 |
| 🟢 绿 | 在 `test_story_1_3_steps.py` 实现 `temporary_consumer` 异步上下文管理器 |
| 🔄 重构 | 优化启动确认逻辑，添加超时配置 |

- [ ] Subtask 1.1: 🔴 红 — 确认 `test_ac2_rabbitmq_documentprocessed` 失败
- [ ] Subtask 1.2: 🟢 绿 — 实现 `temporary_consumer` (使用 `asyncio.create_task()` 后台运行)
- [ ] Subtask 1.3: 🔄 重构 — 实现 `_wait_for_consumer_ready()` 轮询函数
- [ ] Subtask 1.4: 验证 — 本地运行测试通过

#### TDD 循环 [P2]: 修复 collection 创建缺失

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 确认 `test_dense_search_with_filter` 失败 |
| 🟢 绿 | 在 `test_story_1_6_steps.py` 添加 `create_collection()` 调用 |
| 🔄 重构 | 验证幂等性 |

- [ ] Subtask 1.5: 🔴 红 — 确认 `test_dense_search_with_filter` 失败
- [ ] Subtask 1.6: 🟢 绿 — 在 `collection_has_different_domains` 添加 `create_collection()`
- [ ] Subtask 1.7: 🔄 重构 — 验证幂等性
- [ ] Subtask 1.8: 验证 — 本地运行测试通过

#### TDD 循环 [P6]: 修复 event_loop scope 问题

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 确认 event_loop fixture 冲突存在 |
| 🟢 绿 | 删除 `scope=module` 的 `event_loop` fixture |
| 🔄 重构 — 验证无状态污染 |

- [ ] Subtask 1.9: 🔴 红 — 确认 event_loop fixture 冲突
- [ ] Subtask 1.10: 🟢 绿 — 删除 `event_loop` fixture，使用 pytest-asyncio auto mode
- [ ] Subtask 1.11: 🔄 重构 — 验证无状态污染
- [ ] Subtask 1.12: 验证 — 多次运行测试无污染

**完成标准/Definition of Done:**
- [ ] `test_ac2_rabbitmq_documentprocessed` 本地/CI 都通过
- [ ] `test_ac2_rabbitmq_agentdecided` 本地/CI 都通过
- [ ] `test_dense_search_with_filter` 本地通过
- [ ] 无 event_loop 冲突

---

### Task 2: Phase 2 环境标准化 (P3/P5) — 预计 2-3 天

**关联 AC:** AC-2

#### TDD 循环 [P3]: 实现 tests/environments.py

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写环境检测逻辑测试 |
| 🟢 绿 | 实现 `TestEnvironment` 枚举和 `resolve_env()` 函数 |
| 🔄 重构 | 添加 K8s/容器检测，优化代码 |

- [ ] Subtask 2.1: 🔴 红 — 编写 `TestEnvironment` 枚举测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `TestEnvironment` 枚举 (LOCAL/CI/K8S/AUTO)
- [ ] Subtask 2.3: 🟢 绿 — 实现 `_is_running_in_k8s()` 和 `_is_running_in_container()` 检测函数
- [ ] Subtask 2.4: 🟢 绿 — 实现 `TestEnvConfig` 数据类（6 个服务配置）
- [ ] Subtask 2.5: 🟢 绿 — 实现 `resolve_env()` 主函数（5 种检测优先级）
- [ ] Subtask 2.6: 🟢 绿 — 实现 `get_test_env()` 和 `reset_test_env()` 单例
- [ ] Subtask 2.7: 🔄 重构 — 优化代码
- [ ] Subtask 2.8: 验证 — 三种环境测试通过

#### TDD 循环 [P5]: 创建 docker-compose.test.yml

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 确认当前 docker-compose 端口冲突 |
| 🟢 绿 | 创建 `deploy/app/docker-compose.test.yml` |
| 🔄 重构 | 更新 CI workflow |

- [ ] Subtask 2.9: 🔴 红 — 确认测试端口冲突
- [ ] Subtask 2.10: 🟢 绿 — 创建 `docker-compose.test.yml`（6 个服务，测试专用端口）
- [ ] Subtask 2.11: 🔄 重构 — 更新 CI workflow 设置 `SISYS_TEST_ENV=ci`
- [ ] Subtask 2.12: 验证 — 本地启动测试环境成功

**完成标准/Definition of Done:**
- [ ] `tests/environments.py` 实现完整
- [ ] LOCAL/CI/K8S 三种环境正确识别
- [ ] `docker-compose.test.yml` 创建完成
- [ ] CI workflow 使用测试环境

---

### Task 3: Phase 3 测试隔离 (P4) — 预计 3-4 天

**关联 AC:** AC-3

#### TDD 循环 [P4-isolation]: 实现 tests/isolation.py

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写租户隔离测试 |
| 🟢 绿 | 实现 `TestTenant`、`TenantContext`、`generate_test_tenant()` |
| 🔄 重构 | 确保线程安全 |

- [ ] Subtask 3.1: 🔴 红 — 编写 UUID 唯一性测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 `TestTenant` 数据类
- [ ] Subtask 3.3: 🟢 绿 — 实现资源前缀方法 (rabbitmq_queue_prefix, qdrant_collection, redis_key_prefix, postgres_schema)
- [ ] Subtask 3.4: 🟢 绿 — 实现 `TenantContext` 上下文管理器
- [ ] Subtask 3.5: 🟢 绿 — 实现 `generate_test_tenant()` 函数
- [ ] Subtask 3.6: 🟢 绿 — 实现 pytest fixtures (`test_tenant`, `isolated_tenant_context`)
- [ ] Subtask 3.7: 🟢 绿 — 实现 `TenantAwareMock` 类
- [ ] Subtask 3.8: 🔄 重构 — 确保 `asyncio.current_task().ident` 正确使用
- [ ] Subtask 3.9: 验证 — 并行测试无冲突

#### TDD 循环 [P4-fixtures]: 实现 tests/fixtures.py

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写资源清理测试 |
| 🟢 绿 | 实现 `test_env_config`, `fresh_test_env_config`, `_cleanup_tenant_resources()` |
| 🔄 重构 | 添加日志和异常处理 |

- [ ] Subtask 3.10: 🔴 红 — 编写资源清理测试 (mock 所有服务)
- [ ] Subtask 3.11: 🟢 绿 — 实现 `test_env_config` (session scope)
- [ ] Subtask 3.12: 🟢 绿 — 实现 `fresh_test_env_config` (function scope)
- [ ] Subtask 3.13: 🟢 绿 — 实现 `_cleanup_tenant_resources()` 函数（6 个服务清理）
- [ ] Subtask 3.14: 🟢 绿 — 实现 `isolated_tenant` 和 `tenant_context` fixtures
- [ ] Subtask 3.15: 🟢 绿 — 实现 `cleanup_old_test_resources` session 级 fixture
- [ ] Subtask 3.16: 🟢 绿 — 实现 `reset_test_environment` autouse fixture
- [ ] Subtask 3.17: 🔄 重构 — 优化异常处理和日志
- [ ] Subtask 3.18: 验证 — 清理逻辑正确

**完成标准/Definition of Done:**
- [ ] `tests/isolation.py` 实现完整
- [ ] `tests/fixtures.py` 实现完整
- [ ] pytest-xdist `-n 4` 并行无冲突
- [ ] 资源清理正确

---

### Task 4: Phase 4 中期验证 - 紧急修复验证 (Phase 4) — 预计 0.5 天

**关联 AC:** AC-8 (中期验证)

> **Phase 4 位置说明:** 根据框架设计，Phase 4 是中期验证点，在 Task 3 (Phase 3 建立隔离层) 之后执行。此任务验证 Phase 1 的 3 个紧急修复是否有效。中期验证通过后继续 Phase 5-8，最终完整验证在 Task 9。

- [ ] Subtask 4.1: 运行 Phase 1 修复的 3 个测试
  ```bash
  poetry run pytest tests/acceptance/test_story_1_3_steps.py::test_ac2_rabbitmq_documentprocessed -v
  poetry run pytest tests/acceptance/test_story_1_3_steps.py::test_ac2_rabbitmq_agentdecided -v
  poetry run pytest tests/acceptance/test_story_1_6_steps.py::test_dense_search_with_filter -v
  ```
- [ ] Subtask 4.2: 验证 event_loop 冲突已解决（多次运行无污染）
- [ ] Subtask 4.3: 验证租户隔离在单个测试中工作正常

**完成标准/Definition of Done:**
- [ ] 3 个紧急修复测试全部通过
- [ ] 无 event_loop 冲突
- [ ] 中期验证通过，可继续 Phase 5-8
- [ ] 最终完整验证见 Task 9（包含完整回归测试、并行测试、CI 验证）

---

### Task 5: Phase 5 tests/acceptance/ 重构 (A1-A10) — 预计 3-4 天

**关联 AC:** AC-4

> **12 个 BDD 验收测试文件，~1500 行代码**

- [ ] Subtask 5.1: A1 — 检查所有 fixtures scope，修正为 function
- [ ] Subtask 5.2: A2 — `test_story_1_3_steps.py` 使用 `temporary_consumer` + UUID 队列名
- [ ] Subtask 5.3: A3 — `test_story_1_6_steps.py` 使用 UUID collection 名
- [ ] Subtask 5.4: A4 — 所有队列名添加租户前缀 `test_{uuid}_queue`
- [ ] Subtask 5.5: A5 — 所有 Redis keys 添加租户前缀 `test:{uuid}:`
- [ ] Subtask 5.6: A6 — 所有 Qdrant collections 添加租户前缀 `test_{uuid}_`
- [ ] Subtask 5.7: A7 — 确认 pytest-asyncio `asyncio_mode = "auto"` 配置
- [ ] Subtask 5.8: A8 — 添加 `reset_test_environment` fixture
- [ ] Subtask 5.9: A9 — `temporary_consumer` 使用 UUID 独立队列名
- [ ] Subtask 5.10: A10 — 并行执行 `-n 4` 无冲突验证

**完成标准/Definition of Done:**
- [ ] 12 个文件全部更新
- [ ] 所有资源使用租户隔离
- [ ] 并行测试无冲突

---

### Task 6: Phase 6 tests/integration/ 重构 (I1-I8) — 预计 0.5 天

**关联 AC:** AC-5

> **15 个集成测试文件，使用 fakeredis mock**

- [ ] Subtask 6.1: I1 — 确认使用 fakeredis 而非真实 Redis
- [ ] Subtask 6.2: I2 — 确认 fixtures 为 function scope
- [ ] Subtask 6.3: I3 — 检查 PostgreSQL mock 正确性
- [ ] Subtask 6.4: I4 — 添加 `reset_test_environment` fixture
- [ ] Subtask 6.5: I5 — 验证 `mock_redis` 每个测试后清理
- [ ] Subtask 6.6: I6 — 检查 `in_memory_store` 状态隔离
- [ ] Subtask 6.7: I7 — 确认 IdempotencyChecker mock 正确
- [ ] Subtask 6.8: I8 — 检查 RetryPolicy 测试参数

**完成标准/Definition of Done:**
- [ ] 15 个文件全部验证
- [ ] mock 正确使用
- [ ] 状态隔离

---

### Task 7: Phase 7 tests/integration_real/ 重构 (R1-R7) — 预计 1-2 天

**关联 AC:** AC-6

> **6 个真实服务集成测试文件**

- [ ] Subtask 7.1: R1 — 更新 `conftest.py` 使用 `tests/environments.py`
- [ ] Subtask 7.2: R2 — 检查 `scope=session` 连接池是否改为 function
- [ ] Subtask 7.3: R3 — 添加资源清理 (collection/queue/key cleanup)
- [ ] Subtask 7.4: R4 — 为 Qdrant collections 添加 UUID 前缀
- [ ] Subtask 7.5: R5 — 为 Redis keys 添加 UUID 前缀
- [ ] Subtask 7.6: R6 — PostgreSQL schema 清理正确
- [ ] Subtask 7.7: R7 — 验证连接配置使用 `get_test_env()`

**完成标准/Definition of Done:**
- [ ] 6 个文件全部更新
- [ ] 使用统一环境配置
- [ ] 资源隔离正确

---

### Task 8: Phase 8 tests/unit/ 重构 (U1-U6) — 预计 0.5 天

**关联 AC:** AC-7

> **70 个单元测试文件，7 个子目录**

- [ ] Subtask 8.1: U1 — 确认使用 mock 而非真实服务
- [ ] Subtask 8.2: U2 — 检查 fixture scope 正确性
- [ ] Subtask 8.3: U3 — 验证 mock 清理（每个测试后）
- [ ] Subtask 8.4: U4 — 检查是否有泄露到真实服务的情况
- [ ] Subtask 8.5: U5 — 确认 async mock 使用 `AsyncMock`
- [ ] Subtask 8.6: U6 — 检查 pytest.mark 标记使用

**完成标准/Definition of Done:**
- [ ] 70 个文件全部检查
- [ ] mock 正确使用
- [ ] 无泄露

---

### Task 9: Phase 4 最终验证 - 完整回归测试 (Phase 4) — 预计 1 天

**关联 AC:** AC-8 (最终验证)

> **Phase 4 最终验证说明:** 在 Phase 5-8 全部完成后，执行完整回归测试验证整体系统。

- [ ] Subtask 9.1: 运行完整验收测试套件（本地）
  ```bash
  poetry run pytest tests/acceptance/ -v --tb=short
  ```
- [ ] Subtask 9.2: 运行完整集成测试套件（本地）
  ```bash
  poetry run pytest tests/integration/ tests/integration_real/ -v --tb=short
  ```
- [ ] Subtask 9.3: 运行单元测试套件
  ```bash
  poetry run pytest tests/unit/ -v --tb=short
  ```
- [ ] Subtask 9.4: 并行执行无冲突验证
  ```bash
  poetry run pytest tests/acceptance/ -v -n 4
  ```
- [ ] Subtask 9.5: CI pipeline 完整验证
  ```bash
  git push && 等待 CI pipeline 完成
  ```

**完成标准/Definition of Done:**
- [ ] 本地测试 100% 通过
- [ ] CI 测试 100% 通过
- [ ] 并行测试无冲突
- [ ] 完整回归测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`sisys-testing-framework.md`](../../docs/developer/sisys-testing-framework.md) 四、详细实施计划

### 关键设计决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|-------|
| **UUID 前缀隔离** | 简单可靠，无冲突 | 资源名较长 | ✅ 9/10 |
| asyncio.current_task().ident | 同一进程内准确 | 不跨进程 | ✅ 8/10 |
| pytest-asyncio auto mode | 官方推荐，无冲突 | 需要配置正确 | ✅ 9/10 |
| 测试专用 docker-compose | 完全隔离生产 | 需要额外维护 | ✅ 8/10 |

### 项目结构说明 Project Structure

```
sisys/
├── tests/
│   ├── environments.py          # [新建] Phase 2 - 测试环境配置解析
│   ├── isolation.py              # [新建] Phase 3 - 测试租户隔离管理
│   ├── fixtures.py               # [新建] Phase 3 - 测试资源清理 fixtures
│   ├── conftest.py               # [更新] 添加隔离 fixtures
│   ├── acceptance/               # [更新] Phase 5 - 12 个 BDD 文件
│   │   ├── test_story_1_3_steps.py   # [更新] P1 修复 async_consume
│   │   └── test_story_1_6_steps.py    # [更新] P2 修复 collection 创建
│   ├── integration/              # [更新] Phase 6 - 15 个 mock 文件
│   ├── integration_real/         # [更新] Phase 7 - 6 个真实服务文件
│   └── unit/                    # [检查] Phase 8 - 70 个单元测试
└── deploy/app/
    └── docker-compose.test.yml  # [新建] Phase 2 - 测试专用 docker-compose
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (MiniMax-M2) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-21 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Framework Doc** | `docs/developer/sisys-testing-framework.md` |
| **Phase 1 Checklist** | sisys-testing-framework.md lines 1594-1669 |
| **Phase 2 Checklist** | sisys-testing-framework.md lines 1672-1725 |
| **Phase 3 Checklist** | sisys-testing-framework.md lines 1728-1811 |
| **Phase 4 Checklist** | sisys-testing-framework.md lines 1814-1855 |
| **Phase 5 Checklist** | sisys-testing-framework.md lines 1858-1891 |
| **Phase 6 Checklist** | sisys-testing-framework.md lines 1894-1913 |
| **Phase 7 Checklist** | sisys-testing-framework.md lines 1916-1940 |
| **Phase 8 Checklist** | sisys-testing-framework.md lines 1943-1968 |

### 完成清单 Completion Notes List

- [x] 故事需求从 `sisys-testing-framework.md` 四、详细实施计划提取
- [x] AC 直接映射到 Phase 1-8 的 Checklist
- [x] Task 按执行顺序排列 (Phase 1 → Phase 8)
- [x] 状态设置为 `ready-for-dev`
- [x] **修复 Issue 1**: Phase 4 验证位置 - Task 4 为中期验证点（在 Task 3 后）
- [x] **修复 Issue 2**: Phase 5-8 与 Phase 4 关系 - Task 9 为最终验证点
- [x] **修复 Issue 4**: Task 9 去除重复验证项，聚焦最终回归测试

### 文件清单 File List

**新建文件:**
- `tests/environments.py` - 测试环境配置解析
- `tests/isolation.py` - 测试租户隔离管理
- `tests/fixtures.py` - 测试资源清理 fixtures
- `deploy/app/docker-compose.test.yml` - 测试专用 docker-compose

**更新文件:**
- `tests/acceptance/test_story_1_3_steps.py` - P1 修复
- `tests/acceptance/test_story_1_6_steps.py` - P2 修复
- `tests/acceptance/*.py` - A1-A10 租户隔离
- `tests/integration/*.py` - I1-I8 mock 验证
- `tests/integration_real/*.py` - R1-R7 环境标准化
- `tests/unit/**/*.py` - U1-U6 mock 检查
- `.gitea/workflows/ci.yaml` - 使用测试环境

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 20-1 |
| **Story Key** | 20-1-sisys-testing-refactor |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 20: 测试工程基础设施 |
| **优先级** | P0 (紧急 - 阻塞性问题) |
| **预计工时** | 8-12 天 |

### 执行顺序

```
Task 1 (Phase 1) → Task 2 (Phase 2) → Task 3 (Phase 3) →
Task 4 (Phase 4 中期验证) → Task 5 (Phase 5) → Task 6 (Phase 6) →
Task 7 (Phase 7) → Task 8 (Phase 8) → Task 9 (Phase 4 最终验证)
```

**关键说明:** Phase 4 在框架中出现两次：
- **中期验证点 (Task 4):** 在 Phase 3 建立隔离层后，验证紧急修复是否有效
- **最终验证点 (Task 9):** 在 Phase 5-8 全部完成后，验证完整回归测试

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

**模板版本/Template Version:** 2.2.0
**创建日期/Created:** 2026-04-21
**最后更新/Last Updated:** 2026-04-21
**更新说明:** 修复 Phase 4 验证位置和 Task 重复问题，调整为 9 个 Tasks（Task 4 为中期验证，Task 9 为最终验证）
