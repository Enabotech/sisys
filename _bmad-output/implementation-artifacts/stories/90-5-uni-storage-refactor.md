# Story 90-5: 统一存储架构重构（存储端口 ABC 化）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 完成统一存储架构的端口 ABC 化改造,
**So that** 遵循六边形架构依赖倒置原则，实现 L0-L5 六层存储架构的完整端口抽象。

### 业务价值

| 组件 | 现状 | 目标 |
|------|------|------|
| **L1CachePort** | 缺失 | 新增 `src/domain/ports/l1_cache.py` |
| **L3VectorPort** | 缺失（现有 vector_storage.py 是 Protocol） | 新增 `src/domain/ports/l3_vector.py` ABC |
| **L4ObjectPort** | 缺失（现有 storage.py 是 ObjectStorageRepository） | 新增 `src/domain/ports/l4_object.py` ABC |
| **L5GraphPort** | 缺失 | 新增 `src/domain/ports/l5_graph.py` ABC |
| **UnifiedStoragePort** | 缺失 | 新增 `src/domain/ports/unified_storage.py` |
| **StorageLayer/StorageTier** | 缺失 | 新增 `src/domain/ports/storage_enums.py` |
| **SemanticCachePort** | 缺失 | 新增 `src/domain/ports/semantic_cache.py` |
| **RedisMemoryCache** | sync | 重构为 async |

### 方案背景

**来源**: `docs/architecture/sisys-uni-storage-design.md` v2.0

**迁移路径 Phase 1（定义 Port 接口）:**
1. 新增 `src/domain/ports/l1_cache.py` → `L1CachePort`
2. 新增 `src/domain/ports/l3_vector.py` → `L3VectorPort`
3. 新增 `src/domain/ports/l4_object.py` → `L4ObjectPort`
4. 新增 `src/domain/ports/l5_graph.py` → `L5GraphPort`
5. 新增 `src/domain/ports/unified_storage.py` → `UnifiedStoragePort`
6. 新增 `src/domain/ports/storage_enums.py` → `StorageLayer`, `StorageTier`

**迁移路径 Phase 2（实现 Adapter）:**
1. `RedisMemoryCache` 重构为 async
2. `QdrantAdapter` 实现 `L3VectorPort`
3. `MinIOAdapter` 实现 `L4ObjectPort`
4. `Neo4jAdapter` 实现 `L5GraphPort`

**迁移路径 Phase 3（创建网关）:**
1. `UnifiedStorageGateway`
2. `UnifiedStorageFactory`
3. `StoragePolicyService`

---

## ✅ Acceptance Criteria 验收标准

### AC-1: L1CachePort 接口定义

**Given** 需要统一的 L1 缓存抽象
**When** 定义 `L1CachePort` 接口
**Then** 接口包含 `get()`, `set()`, `delete()`, `invalidate_pattern()` 四个抽象方法

**验证标准:**
- [ ] `src/domain/ports/l1_cache.py` 定义 ABC 类
- [ ] 4 个抽象方法签名符合设计文档 §3.3
- [ ] 领域层零外部依赖（仅用 abc + typing）

### AC-2: L3VectorPort 接口定义

**Given** 需要统一的 L3 向量存储抽象
**When** 定义 `L3VectorPort` 接口
**Then** 接口包含 `upsert_points()`, `delete_points()`, `get_point()`, `search()`, `search_sparse()` 五个抽象方法

**验证标准:**
- [ ] `src/domain/ports/l3_vector.py` 定义 ABC 类
- [ ] 5 个抽象方法签名符合设计文档 §3.5
- [ ] 与现有 VectorStorage Protocol 语义兼容

### AC-3: L4ObjectPort 接口定义

**Given** 需要统一的 L4 对象存储抽象
**When** 定义 `L4ObjectPort` 接口
**Then** 接口包含 `store()`, `retrieve()`, `delete()`, `get_metadata()`, `archive()` 五个抽象方法

**验证标准:**
- [ ] `src/domain/ports/l4_object.py` 定义 ABC 类
- [ ] 5 个抽象方法签名符合设计文档 §3.6
- [ ] 与现有 ObjectStorageRepository 语义兼容

### AC-4: L5GraphPort 接口定义

**Given** 需要统一的 L5 图存储抽象
**When** 定义 `L5GraphPort` 接口
**Then** 接口包含 `create_entity()`, `get_entity()`, `delete_entity()`, `create_relationship()`, `delete_relationship()`, `find_related()`, `execute_query()`, `execute_write_query()` 八个抽象方法

**验证标准:**
- [ ] `src/domain/ports/l5_graph.py` 定义 ABC 类
- [ ] 8 个抽象方法签名符合设计文档 §3.7
- [ ] 使用 memory_id 作为实体主键

### AC-5: UnifiedStoragePort 接口定义

**Given** 需要统一的存储入口抽象
**When** 定义 `UnifiedStoragePort` 接口
**Then** 接口包含 `save()`, `read()`, `delete()`, `exists()` 四个抽象方法

**验证标准:**
- [ ] `src/domain/ports/unified_storage.py` 定义 ABC 类
- [ ] 4 个抽象方法签名符合设计文档 §3.9
- [ ] 使用 StorageLayer 和 StorageTier 枚举

### AC-6: StorageEnums 定义

**Given** 需要统一的存储层级枚举
**When** 定义 `StorageLayer`, `StorageTier`, `DataAccessPattern` 枚举
**Then** 三个枚举符合设计文档 §3.8

**验证标准:**
- [ ] `src/domain/ports/storage_enums.py` 定义三个枚举
- [ ] StorageLayer: L0_FILE, L1_CACHE, L2_SQL, L3_VECTOR, L4_OBJECT, L5_GRAPH
- [ ] StorageTier: HOT, WARM, COLD, FROZEN
- [ ] DataAccessPattern: FREQUENT, OCCASIONAL, RARE, ARCHIVED

### AC-7: RedisMemoryCache 异步重构

**Given** L1CachePort 接口已定义
**When** 重构 `RedisMemoryCache` 为异步实现
**Then** 使用 `redis.asyncio` 替代 `redis`

**验证标准:**
- [ ] `src/infrastructure/storage/redis/redis_memory_cache.py` 所有方法改为 async
- [ ] 使用 `await self._redis.get()` 等异步调用
- [ ] Key 格式: `memory:user:{user_id}:{name}` 或 `memory:group:{group_id}:{name}`
- [ ] TTL: 24h-30h 随机值

### AC-8: QdrantAdapter 实现

**Given** L3VectorPort 接口已定义
**When** 实现 `QdrantAdapter`
**Then** 适配器包装现有 QdrantVectorStorage

**验证标准:**
- [ ] `src/infrastructure/storage/qdrant/qdrant_adapter.py` 实现 L3VectorPort
- [ ] 所有方法使用 async/await
- [ ] points 参数使用 list[dict]

### AC-9: L5 适配器实现

**Given** L5GraphPort 接口已定义
**When** 实现 Neo4jAdapter
**Then** 适配器包装现有 Neo4jGraphStorage

**验证标准:**
- [ ] `src/infrastructure/storage/neo4j/neo4j_adapter.py` 实现 L5GraphPort
- [ ] 所有方法使用 async/await
- [ ] 使用 memory_id 作为实体主键

### AC-10: UnifiedStorageGateway 实现

**Given** 所有 Port 接口已定义
**When** 实现 `UnifiedStorageGateway`
**Then** 网关编排 L0-L5 各层存储

**验证标准:**
- [ ] `src/application/services/unified_storage_gateway.py` 实现 UnifiedStoragePort
- [ ] 依赖注入所有 Port 接口
- [ ] save() 实现 L0 同步写入 + Outbox 事件发布
- [ ] read() 实现 L1 → L2 → L0 读取流程

### AC-11: 领域层端口导出更新

**Given** 新增的端口
**When** 更新 `src/domain/ports/__init__.py`
**Then** 所有端口统一导出

**验证标准:**
- [ ] 导出 L1CachePort
- [ ] 导出 L3VectorPort
- [ ] 导出 L4ObjectPort
- [ ] 导出 L5GraphPort
- [ ] 导出 UnifiedStoragePort
- [ ] 导出 StorageLayer, StorageTier

### AC-12: 端到端测试

**Given** 所有组件实现完成
**When** 运行完整测试套件
**Then** 所有测试通过

**验证标准:**
- [ ] `pytest tests/unit/domain/ports/ -v` 通过
- [ ] `pytest tests/unit/infrastructure/storage/ -v` 通过
- [ ] `ruff check` + `mypy` 通过

---

## 📋 Tasks / Subtasks 任务分解

### Task 1: L1CachePort + RedisMemoryCache 异步

**关联 AC:** AC-1, AC-7

- [x] Subtask 1.1: 🔴 红 — 编写 L1CachePort 测试
- [x] Subtask 1.2: 🟢 绿 — 实现 L1CachePort ABC
- [x] Subtask 1.3: 🔴 红 — 编写 RedisMemoryCache async 测试
- [x] Subtask 1.4: 🟢 绿 — 重构 RedisMemoryCache 为 async
- [x] Subtask 1.5: 🔄 重构 — 优化代码，运行 ruff + mypy

### Task 2: L3VectorPort + QdrantAdapter

**关联 AC:** AC-2, AC-8

- [x] Subtask 2.1: 🔴 红 — 编写 L3VectorPort 测试
- [x] Subtask 2.2: 🟢 绿 — 实现 L3VectorPort ABC
- [x] Subtask 2.3: 🔴 红 — 编写 QdrantAdapter 测试
- [x] Subtask 2.4: 🟢 绿 — 实现 QdrantAdapter
- [x] Subtask 2.5: 🔄 重构 — 优化代码

### Task 3: L4ObjectPort + MinIOAdapter

**关联 AC:** AC-3

- [x] Subtask 3.1: 🔴 红 — 编写 L4ObjectPort 测试
- [x] Subtask 3.2: 🟢 绿 — 实现 L4ObjectPort ABC
- [x] Subtask 3.3: 🔴 红 — 编写 MinIOAdapter 测试
- [x] Subtask 3.4: 🟢 绿 — 实现 MinIOAdapter
- [x] Subtask 3.5: 🔄 重构 — 优化代码

### Task 4: L5GraphPort + Neo4jAdapter

**关联 AC:** AC-4, AC-9

- [x] Subtask 4.1: 🔴 红 — 编写 L5GraphPort 测试
- [x] Subtask 4.2: 🟢 绿 — 实现 L5GraphPort ABC
- [x] Subtask 4.3: 🔴 红 — 编写 Neo4jAdapter 测试
- [x] Subtask 4.4: 🟢 绿 — 实现 Neo4jAdapter
- [x] Subtask 4.5: 🔄 重构 — 优化代码

### Task 5: UnifiedStoragePort + StorageEnums

**关联 AC:** AC-5, AC-6

- [x] Subtask 5.1: 🔴 红 — 编写 StorageEnums 测试
- [x] Subtask 5.2: 🟢 绿 — 实现 StorageLayer, StorageTier, DataAccessPattern
- [x] Subtask 5.3: 🔴 红 — 编写 UnifiedStoragePort 测试
- [x] Subtask 5.4: 🟢 绿 — 实现 UnifiedStoragePort ABC
- [x] Subtask 5.5: 🔄 重构 — 优化代码

### Task 6: UnifiedStorageGateway

**关联 AC:** AC-10

- [x] Subtask 6.1: 🔴 红 — 编写 UnifiedStorageGateway 测试
- [x] Subtask 6.2: 🟢 绿 — 实现 UnifiedStorageGateway
- [x] Subtask 6.3: 🔄 重构 — 实现 save/read/delete/exists 完整逻辑

### Task 7: 端口导出 + 集成测试

**关联 AC:** AC-11, AC-12

- [x] Subtask 7.1: 🔴 红 — 编写端口导出测试
- [x] Subtask 7.2: 🟢 绿 — 更新 __init__.py 导出所有端口
- [x] Subtask 7.3: 🟢 绿 — 运行完整测试套件
- [x] Subtask 7.4: 🔄 重构 — 修复失败测试

---

## 📝 Dev Notes 开发笔记

### 架构来源

**来源:** `docs/architecture/sisys-uni-storage-design.md` v2.0

### 项目结构

```
src/
├── domain/
│   └── ports/
│       ├── l1_cache.py         # NEW: L1CachePort
│       ├── l3_vector.py         # NEW: L3VectorPort
│       ├── l4_object.py         # NEW: L4ObjectPort
│       ├── l5_graph.py          # NEW: L5GraphPort
│       ├── unified_storage.py    # NEW: UnifiedStoragePort
│       ├── storage_enums.py      # NEW: StorageLayer/StorageTier
│       └── semantic_cache.py     # NEW: SemanticCachePort
├── application/
│   └── services/
│       └── unified_storage_gateway.py  # NEW: UnifiedStorageGateway
└── infrastructure/
    └── storage/
        ├── redis/
        │   └── redis_memory_cache.py  # UPDATE: async
        └── qdrant/
            └── qdrant_vector_adapter.py  # NEW: L3VectorPort impl
        └── neo4j/
            └── neo4j_adapter.py  # NEW: L5GraphPort impl
```

### 设计原则

1. **零外部依赖**: Domain 层仅用 abc + typing
2. **异步优先**: 所有 I/O 操作使用 async/await
3. **ABC 统一**: 所有 Port 使用 ABC 而非 Protocol
4. **适配器模式**: L3-L5 使用适配器包装现有实现

---

## 🤖 开发代理记录

| 配置项 | 值 |
|--------|-----|
| **Model** | claude-opus-4-7 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-08 |

### 完成清单

- [x] 故事需求从 sisys-uni-storage-design.md v2.0 提取
- [x] 架构约束从 architecture.md §11 提取
- [x] Phase 1-3 迁移路径定义完成
- [x] 状态设置为 `ready-for-dev`

---

## 📊 故事详情

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 20-5 |
| **Story Key** | 20-5-uni-storage-refactor |
| **File** | `_bmad-output/implementation-artifacts/stories/20-5-uni-storage-refactor.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 90: 重大重构 |

### 下一步

- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

**模板版本/Template Version:** 2.5.0
**创建日期/Created:** 2026-05-08
