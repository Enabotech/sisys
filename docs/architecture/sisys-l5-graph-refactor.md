# SISYS L5 图存储重构详细设计

**版本:** v3.0
**日期:** 2026-05-13
**作者:** Claude Code (宗师级架构设计)
**状态:** 设计完成（v3.0 五轮审查完成，含未修复P0清单和系统性不一致记录）
**基于:** sisys-uni-storage-design.md §L5 重构决策

**Changelog v2.2 (第一轮调研修复):**
- P0: Neo4jAdapter 缺少 `get_neighbors` 实现
- P0: Neo4jAdapter 硬编码 `Memory` 标签（5处）
- P0: `execute_query`/`execute_write_query` 实现完全相同，无事务区分
- P1: 测试断言与接口定义不符
- P1: `direction` 参数在 src/ 中无实际调用方
- P1: `find_path` 与 `get_neighbors` 返回语义不一致

**Changelog v2.3 (第二轮调研修复):**
- P0: Neo4jAdapter 不是"薄适配器"——自己拼接 Cypher（违反六边形架构）
- P0: Memory 标签硬编码散落 8+ 处（违反 OCP）
- P0: `execute_write_query` 使用 `session.run()` 而非 `session.execute_write()`
- P1: 测试 mock 返回值与接口定义不符
- P1: 向后兼容性影响范围广（6文件需修改）
- P1: 新增双轨制迁移策略

**Changelog v2.4 (第三四轮调研修复):**
- P0: `get_async_driver()` 懒初始化存在竞态条件（非线程安全）
- P0: 接口映射完整度仅 22%（Neo4jGraphStorage 缺失 5/9 方法）
- P1: `find_path`/`get_neighbors` 返回 Neo4j 原生对象而非 dict（虚假 cast）
- P1: `BaseGraphAdapter` 仅存在于设计文档，实际代码未实现
- P1: `test_neo4j_adapter.py` 完全缺失 `get_neighbors` 测试
- P1: `Neo4jGraphStorage` 未实现 L5GraphPort 协议（缺少 create_entity 等）
- P2: `create_node` 接口在 GraphManager 和 L5GraphPort 中语义不同
- P2: `Neo4jConnectionProvider` 单例未实现（使用多例 Neo4jClientWrapper）
- P2: `MemoryGraphPort` 未实现（Application 层抽象缺失）

**Changelog v2.5 (第1轮全面审查 - 4Agent并行调研):**
- **P0-NEW**: `conftest.py` 使用不存在的构造参数（TypeError，集成测试无法运行）
- **P0-NEW**: `MemoryChangedHandler` L5 TODO存根（事件驱动路径完全缺失）
- **P0-NEW**: §0.3 Breaking Change表格遗漏4个方法迁移（find_related/delete_relationship/execute_query/execute_write_query）
- **P1-NEW**: 三种冗余图类（GraphStorage/GraphManager/GraphRetriever）无清晰层次结构
- **P1-NEW**: `relationship_type` Cypher注入风险（f-string无清理）
- **P1-NEW**: L5GraphPort(Protocol)掩盖缺失方法（运行时不检查）
- **P2-NEW**: L5无内存适配器（测试需真实Neo4j）
- **P2-NEW**: GraphManager/GraphRetriever孤立未使用

**Changelog v2.6 (第2轮全面审查 - 4Agent并行调研):**
- **P0-NEW**: `test_l5_graph_port.py` mock返回值与接口不符（create_entity返回dict而非bool）
- **P1-NEW**: §0.5迁移策略与§8执行步骤Phase内容完全不对应（双轨制消失）
- **P1-NEW**: `find_related`参数名跨章节不一致（edge_type vs rel_type）
- **P1-NEW**: Neo4jGraphStorage文件路径不一致（graph_storage.py vs neo4j_graph_storage.py）
- **P1-NEW**: MemoryGraphPort层级矛盾（标为Application层但文件在domain/ports/）
- **P1-NEW**: §8执行状态总览表P0/P1/P2计数与实际Step标注不符
- **P1-NEW**: Step 2.2 Neo4jGraphStorage代码仍含Memory领域语义
- **P1-NEW**: Breaking Change表参数名简写与接口定义完整名不一致
- **P1-NEW**: L5适配器模式与L3/L4不对齐（厚适配器含Cypher vs 薄适配器纯委托）
- **P2-NEW**: P编号跳号（P0-1、P1-5等缺失）
- **P2-NEW**: 执行状态总览表缺少Phase 5

**Changelog v2.7 (第3轮全面审查 - 4Agent并行调研):**
- **P0-NEW**: `get_neighbors` direction="IN" Cypher语法错误（缺少关系方括号，生成无效Cypher）
- **P0-NEW**: Neo4jAdapter与GraphManager数据模型不一致（:Memory硬编码 vs :sisys:{type}动态标签）
- **P0-NEW**: MemoryGraphPort§4.2缺少Protocol基类（§2.2正确但§4.2遗漏）
- **P0-NEW**: §5.1 execute_write_query仍用session.run()（§8已修复但§5未同步）
- **P1-NEW**: `get_memory_links`字段映射错误（r.get("source",{}).get("id")始终返回None）
- **P1-NEW**: `Neo4jConnectionProvider.init()`传递不存在的max_connection_lifetime参数（TypeError）
- **P1-NEW**: `create_node`标签注入风险（labels通过f-string未清理）
- **P1-NEW**: GraphRetriever绕过Port接口直连数据库驱动（死代码，架构违规）
- **P1-NEW**: RelationshipType枚举存在但未使用（类型约束形同虚设）
- **P1-NEW**: L5GraphPort docstring暴露Cypher实现细节（"MERGE语义"）

**Changelog v2.8 (第4轮全面审查 - 3Agent并行调研):**
- **P0-NEW**: `get_neighbors` 所有分支 `rel_type_clause` 缺少 `[]` 中括号，生成无效Cypher（影响所有带rel_type调用）
- **P0-NEW**: `MemoryGraphPort` §4.2缺少 `L5GraphPort` 导入语句（NameError导入即崩溃）
- **P0-NEW**: `BaseGraphAdapter` 未列入 §6.1 文件变更清单（MemoryGraphAdapter依赖缺失）
- **P0-NEW**: §6.3 `__init__.py` 导出缺少 `Neo4jConnectionProvider` 和 `BaseGraphAdapter`
- **P1-NEW**: `get_relationships` BOTH分支 `source_id` 始终返回 `n.id`，方向语义错误
- **P1-NEW**: `create_relationship` 参数名冲突风险（properties键名与保留参数重叠）
- **P1-NEW**: `find_path` 的 `max_depth` 缺少边界校验（0或负数生成无效Cypher）
- **P2-NEW**: `batch_create_memory_entities` 串行await循环（性能不佳）
- **P2-NEW**: §5.3 `cast` 导入未使用（冗余导入）
- **P2-NEW**: §6.1 `l5_graph.py` 标为"修改"但实际是接口重写（低估变更风险）

**Changelog v3.0 (第5轮最终验证 - 3Agent并行调研):**
- **P0-UNFIXED**: `conftest.py` 集成测试参数不匹配 — 无修复方案
- **P0-UNFIXED**: `MemoryChangedHandler` L5 TODO存根 — 无修复方案
- **P0-UNFIXED**: `get_neighbors` §5和§8中Cypher均缺少`[]`中括号 — 两处代码都有错误
- **P0-UNFIXED**: `MemoryGraphPort` §4.2和§8 Step 1.2均缺少L5GraphPort导入 — NameError
- **P0-UNFIXED**: `BaseGraphAdapter` §6.1清单和§6.3导出均遗漏
- **P1-SYSTEMIC**: §3-§5设计代码与§8执行步骤代码13处HIGH级不一致（执行者无法确定以哪版为准）
- **P1-SYSTEMIC**: §0.5双轨制迁移策略在§8执行步骤中完全消失（策略与执行矛盾）
- **P1-SYSTEMIC**: `edge_type` vs `rel_type` 在§3-§5和§8中系统性不一致
- **P1-SYSTEMIC**: `graph_storage.py` vs `neo4j_graph_storage.py` 路径贯穿全文混淆
- **P1-COMPAT**: `get_async_driver()` async改造影响12个调用位置（需级联await）
- **P1-COMPAT**: `Neo4jConfig` 缺少 `max_connection_lifetime` 字段（TypeError）

---

## 0. 现状与目标状态

### 0.1 文档说明

**重要**: 本文档描述**目标架构**，而非当前代码状态。设计文档与实际代码存在差异，这是正常的重构流程。

### 0.2 当前代码状态（Baseline）

| 组件 | 位置 | 接口 | 状态 |
|------|------|------|------|
| `L5GraphPort` | `src/domain/ports/l5_graph.py` | 9个方法：`create_entity/get_entity/delete_entity` + `create_relationship/delete_relationship/find_related/get_neighbors/execute_query/execute_write_query` | 旧接口，含领域语义（memory_id），缺少 `update_node/node_exists/get_relationships` |
| `Neo4jAdapter` | `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 仅实现8个方法 | **缺少 `get_neighbors`** 实现（运行时 AttributeError），硬编码 `Memory` 标签（**8处**），非薄适配器（内联Cypher拼接） |
| `Neo4jGraphStorage` | `src/infrastructure/storage/neo4j/graph_storage.py` | 低级 Cypher 执行器（4个方法） | 已有，实现 `execute_query/execute_write_query/find_path/get_neighbors`，但 `execute_query`/`execute_write_query` 实现完全相同（无事务区分），缺失 `create_entity/get_entity/delete_entity/create_relationship/delete_relationship/find_related` 6个方法 |
| `Neo4jClientWrapper` | `src/infrastructure/storage/neo4j/client.py` | 连接封装 | 已有，懒初始化 driver |
| `graph_manager.py` | `src/infrastructure/storage/neo4j/graph_manager.py` | 调用方 | 使用 Neo4jGraphStorage |
| `graph_retriever.py` | `src/infrastructure/storage/neo4j/graph_retriever.py` | 调用方 | 使用 Neo4jGraphStorage |
| `MemoryGraphPort` | `src/domain/ports/memory_graph.py` | ❌ 不存在 | 待创建 |
| `Neo4jConnectionProvider` | `src/infrastructure/storage/neo4j/connection_provider.py` | ❌ 不存在 | 待创建 |
| `MemoryGraphAdapter` | `src/infrastructure/storage/neo4j/memory_graph_adapter.py` | ❌ 不存在 | 待创建 |
| `MemoryChangedHandler` | `src/application/event_handlers/memory_changed_handler.py` | L5 TODO存根 | L5事件驱动路径完全缺失（第83-86行），未注入L5端口 |
| `conftest.py` (集成) | `tests/integration/conftest.py` | ❌ 参数不匹配 | 使用不存在的构造参数（host/http_port/bolt_port），需改为uri |

### 0.3 Breaking Change 声明

> **⚠️ 重要**: 本次重构对 `L5GraphPort` 接口进行 **breaking change**。

| 旧接口方法 | 新接口方法 | 变化类型 |
|-----------|-----------|---------|
| `create_entity(memory_id, entity_type, properties)` | `create_node(node_id, labels, properties)` | **重命名+语义变更** |
| `get_entity(memory_id)` | `get_node(node_id)` | **重命名** |
| `delete_entity(memory_id)` | `delete_node(node_id)` | **重命名** |
| `create_relationship(source_memory_id, target_memory_id, relationship_type, properties)` | `create_relationship(src_id, tgt_id, rel_type, props)` | 参数名统一 |
| `delete_relationship(source_memory_id, target_memory_id, relationship_type)` | `delete_relationship(src_id, tgt_id, rel_type)` | 参数名统一 |
| `find_related(memory_id, max_depth, relationship_type)` | `find_related(node_id, max_depth, rel_type)` | 参数名统一 |
| `get_neighbors(memory_id, max_depth, edge_type)` | `get_neighbors(node_id, rel_type, direction)` | **语义变更：移除 max_depth，支持 direction** |
| `execute_query(cypher, params)` | `execute_query(cypher, params)` | 保留（需改用 session.execute_read） |
| `execute_write_query(cypher, params)` | `execute_write_query(cypher, params)` | 保留（需改用 session.execute_write） |
| - | `update_node(node_id, properties)` | **新增** |
| - | `node_exists(node_id)` | **新增** |
| - | `get_relationships(node_id, rel_type, direction)` | **新增** |

**影响范围**:
- `test_l5_graph_port.py` 中所有测试需要更新（方法重命名）
- `test_neo4j_adapter.py` 中需要添加 `get_neighbors` 实现
- `Neo4jAdapter` 需要移除硬编码 `Memory` 标签（8处修改，非文档旧版声明的5处）
- `Neo4jGraphStorage` 需要区分 `execute_query`/`execute_write_query` 事务（改用 session.execute_read/execute_write）
- `UnifiedStorageGateway` 声明了 `_l5: L5GraphPort` 但**从未调用**，无需修改
- `conftest.py` 集成测试使用不存在的构造参数（host/http_port/bolt_port），需改为 uri
- `MemoryChangedHandler` L5 路径为 TODO 存根，需在重构后实现

### 0.4 目标架构（Target）

| 组件 | Layer | 职责 |
|------|-------|------|
| `L5GraphPort` | L1 Domain | 纯技术图操作抽象 |
| `MemoryGraphPort` | L2 Application | 记忆图谱领域语义 |
| `Neo4jConnectionProvider` | L3 Infrastructure | 连接池单例管理 |
| `Neo4jGraphStorage` | L3 Infrastructure | 完整实现 L5GraphPort |
| `MemoryGraphAdapter` | L4 Infrastructure | 实现 MemoryGraphPort |

### 0.5 迁移策略（双轨制）

**推荐：双轨制迁移（避免 Breaking Change）**

```
Phase 1: Protocol 接口双轨制
  - L5GraphPort 新增 create_node/get_node/delete_node（保持旧方法）
  - 旧方法标记 @deprecated，委托给新方法

Phase 2: Adapter 实现双轨制
  - Neo4jAdapter 同时实现新旧方法
  - 新方法委托给 Neo4jGraphStorage
  - 旧方法委托给新方法

Phase 3: 完善基础设施
  - Neo4jGraphStorage 新增 create_entity/get_entity 等方法
  - 使用 session.execute_write() 替代 session.run()
  - 移除 Memory 标签硬编码

Phase 4: 测试更新
  - 更新 test_l5_graph_port.py（新方法 + 旧方法 deprecated 测试）
  - 更新 test_neo4j_adapter.py
  - 添加 get_neighbors 测试

Phase 5: 清理废弃接口
  - 移除 create_entity/get_entity/delete_entity
  - 更新所有调用方
```

**文件修改清单：**

| 文件 | 修改数量 | 关键变更 |
|------|----------|----------|
| `src/domain/ports/l5_graph.py` | 6+ | Protocol 方法签名 + docstring |
| `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 15+ | get_neighbors 实现 + Cypher 下沉 + Memory 常量化 |
| `src/infrastructure/storage/neo4j/graph_storage.py` | 5+ | execute_write_query 事务 + 新增方法 |
| `tests/unit/domain/ports/test_l5_graph_port.py` | 9 | mock 返回值修正 |
| `tests/unit/infrastructure/storage/test_neo4j_adapter.py` | 12+ | 添加 get_neighbors + 修正返回值 |

---

## 1. 设计背景与目标

### 1.1 问题陈述

当前 `L5GraphPort` 存在**职责混合**问题：Domain 层端口混合了技术接口与领域语义。

| 问题 | 描述 | 违反原则 |
|------|------|----------|
| P1 | `L5GraphPort` 在 Domain 层定义，但包含 `create_entity(memory_id)` 等记忆领域语义 | 领域层应只定义技术抽象，不含领域知识 |
| P2 | `Neo4jAdapter` 硬编码记忆领域逻辑（`Memory` 标签散落 8+ 处） | 适配器应只做接口转换，不含领域逻辑 |
| P3 | 未来扩展（如 `AgentGraph`、`DocumentGraph`）无法复用现有设计 | 违反 DRY 原则 |
| P4 | `Neo4jAdapter` 自己拼接 Cypher，不是"薄适配器"（违反六边形架构） | 适配器承担基础设施职责 |
| P5 | `execute_write_query` 使用 `session.run()` 而非事务，无重试机制 | 写操作缺乏事务保护和自动重试 |
| P6 | `Neo4jAdapter` 缺少 `get_neighbors` 实现（运行时 AttributeError） | 接口契约缺失 |

### 1.2 设计目标

1. **职责分离**: Domain 层定义纯技术接口，Application 层定义领域语义接口
2. **可扩展性**: 新领域可继承基础图端口，无需复制技术实现
3. **可测试性**: 各层可独立测试，通过 Port 接口解耦
4. **一致性**: L3/L4/L5 遵循相同设计模式（技术抽象 + 领域专用）
5. **向后兼容**: 不破坏现有 `UnifiedStorageGateway` 的调用

### 1.3 与现有架构的对齐

| 文档 | 内容 | 本设计对应 |
|------|------|-----------|
| sisys-uni-storage-design.md §3.7 | L5GraphPort 接口定义 | 基础层技术抽象 |
| sisys-uni-storage-design.md §5.2 | Adapter 实现映射表 | L5 实现分层 |
| architecture.md §11.1 | 六层存储设计 | L5 图存储层级 |

### 1.4 审查修复记录（v2.0）

| 问题 | 类型 | 修复方案 |
|------|------|---------|
| 设计文档与代码不一致 | P0 | 新增 §0 现状与目标状态，明确文档描述目标而非现状 |
| get_neighbors 语义不清 | P1 | 限制 max_depth=1，与 find_related 职责分离 |
| MemoryGraphAdapter 样板代码 | P1 | 新增 BaseGraphAdapter 基类减少样板 |
| ConnectionProvider 初始化 | P2 | 明确同步初始化配置，异步驱动按需创建 |

---

## 2. 架构总览

### 2.1 四层职责模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Layer - L5GraphPort（纯技术图操作抽象）           │
│                                                                  │
│  职责：定义最底层通用图存储接口（节点/关系 CRUD + 图遍历 + Cypher）│
│  位置：src/domain/ports/l5_graph.py                              │
│  特点：领域层零依赖，纯抽象协议                                     │
│  方法：create_node/get_node/update_node/delete_node/node_exists │
│       create_relationship/delete_relationship/get_relationships │
│       find_path/get_neighbors/find_related                      │
│       execute_query/execute_write_query                         │
└─────────────────────────────────────────────────────────────────┘
                              ↑ 继承
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Application Layer - MemoryGraphPort（记忆领域语义）    │
│                                                                  │
│  职责：继承L5GraphPort，定义记忆图谱领域能力                       │
│  位置：src/domain/ports/memory_graph.py                          │
│  端口：MemoryGraphPort(L5GraphPort, ...)                         │
│    - create_memory_entity / get_memory_entity / delete_memory_entity │
│    - link_memories / unlink_memories / get_memory_links          │
│    - find_related_memories / get_memory_neighbors / find_memory_path │
│  特点：绑定 memory_id，添加领域语义（Memory标签、记忆关系类型）    │
└─────────────────────────────────────────────────────────────────┘
                              ↑ 实现（技术）
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - Neo4j技术实现 + 图存储管理              │
│                                                                  │
│  职责：实现L5GraphPort接口 + Neo4j连接池统一管理                   │
│  位置：src/infrastructure/storage/neo4j/                           │
│  组件：                                                          │
│    - Neo4jConnectionProvider (连接池单例)                         │
│    - Neo4jGraphStorage (实现L5GraphPort)                         │
│  特点：技术可替换（未来可新增TigerGraphAdapter等）                │
└─────────────────────────────────────────────────────────────────┘
                              ↑ 实现（领域）
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - 具体应用图端口实现                      │
│                                                                  │
│  职责：实现具体应用图端口（MemoryGraphPort等）                     │
│  位置：src/infrastructure/storage/neo4j/                           │
│  组件：                                                          │
│    - MemoryGraphAdapter (实现MemoryGraphPort)                   │
│      └─ 组合Neo4jGraphStorage处理基础图操作                       │
│  可扩展：AgentGraphAdapter / DocumentGraphAdapter（未来）         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 接口继承关系

```python
# Layer 1: Domain统一抽象（纯技术）
class L5GraphPort(Protocol):
    """纯技术图操作接口 - 最底层抽象"""
    # 节点操作
    async def create_node(self, node_id: str, labels: list[str], properties: dict) -> bool: ...
    async def get_node(self, node_id: str) -> dict | None: ...
    async def update_node(self, node_id: str, properties: dict) -> bool: ...
    async def delete_node(self, node_id: str) -> bool: ...
    async def node_exists(self, node_id: str) -> bool: ...
    # 关系操作
    async def create_relationship(self, source_id: str, target_id: str, rel_type: str, properties: dict | None = None) -> bool: ...
    async def delete_relationship(self, source_id: str, target_id: str, rel_type: str) -> bool: ...
    async def get_relationships(self, node_id: str, rel_type: str | None = None, direction: str = "BOTH") -> list[dict]: ...
    # 图遍历
    async def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> list[dict]: ...
    async def get_neighbors(self, node_id: str, rel_type: str | None = None, direction: str = "BOTH") -> list[dict]: ...
    async def find_related(self, node_id: str, max_depth: int = 2, edge_type: str | None = None) -> list[dict]: ...
    # 低级Cypher
    async def execute_query(self, cypher: str, params: dict | None = None) -> list[dict]: ...
    async def execute_write_query(self, cypher: str, params: dict | None = None) -> list[dict]: ...

# Layer 2: Application领域抽象（继承L5GraphPort）
class MemoryGraphPort(L5GraphPort, Protocol):
    """记忆图谱领域接口 - 继承L5GraphPort"""
    # 记忆实体操作
    async def create_memory_entity(self, memory_id: str, entity_type: str, properties: dict) -> bool: ...
    async def get_memory_entity(self, memory_id: str) -> dict | None: ...
    async def delete_memory_entity(self, memory_id: str) -> bool: ...
    async def memory_entity_exists(self, memory_id: str) -> bool: ...
    # 记忆关系操作
    async def link_memories(self, source_id: str, target_id: str, relationship_type: str, properties: dict | None = None) -> bool: ...
    async def unlink_memories(self, source_id: str, target_id: str, relationship_type: str) -> bool: ...
    async def get_memory_links(self, memory_id: str, relationship_type: str | None = None) -> list[dict]: ...
    # 记忆图遍历
    async def find_related_memories(self, memory_id: str, max_depth: int = 2, relationship_type: str | None = None) -> list[dict]: ...
    async def get_memory_neighbors(self, memory_id: str, rel_type: str | None = None, direction: str = "BOTH") -> list[dict]: ...
    async def find_memory_path(self, start_id: str, end_id: str, max_depth: int = 3) -> list[dict]: ...
    # 批量操作
    async def batch_create_memory_entities(self, entities: list[dict]) -> list[bool]: ...
    async def batch_link_memories(self, links: list[dict]) -> list[bool]: ...

# Layer 3: Infrastructure技术实现
class Neo4jConnectionProvider:
    """Neo4j连接池单例提供者"""
    @classmethod
    def init(cls, config: Neo4jConfig) -> None: ...
    @classmethod
    def get_client(cls) -> Neo4jClientWrapper: ...
    @classmethod
    def close(cls) -> None: ...

class Neo4jGraphStorage(L5GraphPort):
    """Neo4j纯技术实现"""
    def __init__(self, client_wrapper: Neo4jClientWrapper, database: str = "neo4j"): ...

# Layer 4: Infrastructure领域实现
class MemoryGraphAdapter(MemoryGraphPort):
    """记忆图谱领域实现"""
    def __init__(self, storage: L5GraphPort):
        self._storage = storage  # 组合Neo4jGraphStorage

    # 实现MemoryGraphPort所有方法
    async def create_memory_entity(self, memory_id: str, entity_type: str, properties: dict) -> bool:
        return await self._storage.create_node(memory_id, ["Memory", entity_type], properties)
    # ...

    # 委托实现L5GraphPort（满足继承契约）
    async def create_node(self, node_id: str, labels: list[str], properties: dict) -> bool:
        return await self._storage.create_node(node_id, labels, properties)
    # ...
```

### 2.3 与 L1 缓存架构的对比

| 层次 | L1缓存层 | L5图存储层 |
|------|---------|-----------|
| **Layer 1** | L1CachePort（通用缓存抽象） | L5GraphPort（通用图操作抽象） |
| **Layer 2** | SemanticCachePort（语义缓存） | MemoryGraphPort（记忆图谱） |
| **Layer 3** | RedisPoolProvider + RedisL1CacheAdapter | Neo4jConnectionProvider + Neo4jGraphStorage |
| **Layer 4** | RedisSemanticCacheAdapter | MemoryGraphAdapter |
| **可扩展** | MemcachedAdapter（未来） | TigerGraphAdapter / NeptuneAdapter（未来） |

### 2.4 现有架构（问题版）

```
当前架构问题：

Domain Layer
└── L5GraphPort (混合接口: create_entity/memory_id + execute_query)
    MemoryGraphPort (缺失，未独立)

Infrastructure Layer
├── Neo4jGraphStorage (已有，实现部分L5GraphPort方法)
├── Neo4jAdapter → 硬编码Memory领域逻辑 ❌
│     └─ create_entity(memory_id) 使用 "Memory" 标签
│     └─ Cypher MERGE 语义嵌入适配器
└── MemoryGraphAdapter (缺失)

问题：
1. L5GraphPort 混合技术接口与领域语义
2. Neo4jAdapter 承担领域逻辑，违反适配器单一职责
3. 无法复用 L5GraphPort 实现其他领域图（AgentGraph等）
4. 无统一连接池管理，多个Adapter独立管理连接
```

### 2.5 分层职责

| 层级 | 组件 | 职责 | 技术 |
|------|------|------|------|
| **Domain** | `L5GraphPort` | 纯技术图操作抽象 | Protocol（无实现） |
| **Application** | `MemoryGraphPort` | 记忆图谱领域语义 | Protocol（继承 L5GraphPort） |
| **Infrastructure** | `Neo4jGraphStorage` | Neo4j 低级 Cypher 执行 | 实现 L5GraphPort |
| **Infrastructure** | `MemoryGraphAdapter` | 记忆领域逻辑实现 | 实现 MemoryGraphPort |

---

## 3. Domain 层重构：L5GraphPort（纯技术抽象）

### 3.1 设计原则

1. **零外部依赖**: 只依赖 `abc` 和 `typing`
2. **纯技术接口**: 不含任何领域语义（如 memory_id）
3. **异步优先**: 所有方法使用 `async def`
4. **通用图操作**: 支持任意节点类型和关系类型

### 3.2 新 L5GraphPort 接口

```python
# src/domain/ports/l5_graph.py

"""L5GraphPort — L5 图存储抽象端口（Domain层）。

对应 architecture.md §11.1：
- 知识图谱、实体关系
- Cypher、图遍历、Parent-Child 索引

设计原则：
- 纯技术接口：不包含任何领域语义
- 领域知识（如 memory_id）由 Application 层端口定义
- 支持任意节点类型和关系类型

与 MemoryGraphPort 的关系：
- L5GraphPort 是基础技术抽象（Domain 层）
- MemoryGraphPort 是领域语义抽象（Application 层），继承 L5GraphPort
"""

from __future__ import annotations

from typing import Any, Protocol


class L5GraphPort(Protocol):
    """L5 图存储端口（Domain层，纯技术抽象）。

    定义纯技术接口：
    - 节点/关系 CRUD（通用）
    - 图遍历查询（通用）
    - 低级 Cypher 执行（供领域适配器使用）

    不包含任何领域语义（如 memory_id、entity_type），
    领域语义由继承的 Application 层端口定义。
    """

    # ========================================================================
    # 节点操作
    # ========================================================================

    async def create_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> bool:
        """创建节点（MERGE 语义）。

        Args:
            node_id: 节点唯一标识
            labels: 节点标签列表（如 ["Memory", "User"]）
            properties: 节点属性

        Returns:
            是否成功（MERGE 语义：已存在返回 True）
        """

    async def get_node(
        self,
        node_id: str,
    ) -> dict | None:
        """获取节点。

        Args:
            node_id: 节点唯一标识

        Returns:
            节点数据 {id, labels, properties}，不存在返回 None
        """

    async def update_node(
        self,
        node_id: str,
        properties: dict[str, Any],
    ) -> bool:
        """更新节点属性。

        Args:
            node_id: 节点唯一标识
            properties: 要更新的属性（增量更新）

        Returns:
            是否成功
        """

    async def delete_node(
        self,
        node_id: str,
    ) -> bool:
        """删除节点及所有关联边（DETACH DELETE）。

        Args:
            node_id: 节点唯一标识

        Returns:
            是否成功
        """

    async def node_exists(
        self,
        node_id: str,
    ) -> bool:
        """检查节点是否存在。

        Args:
            node_id: 节点唯一标识

        Returns:
            是否存在
        """

    # ========================================================================
    # 关系操作
    # ========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边（MERGE 语义）。

        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型（如 "DEPENDS_ON"）
            properties: 关系属性（可选）

        Returns:
            是否成功（MERGE 语义：已存在返回 True）
        """

    async def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """删除关系边。

        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型

        Returns:
            是否成功
        """

    async def get_relationships(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的关系。

        Args:
            node_id: 节点 ID
            rel_type: 过滤关系类型，None 表示所有
            direction: 方向（"OUT" / "IN" / "BOTH"）

        Returns:
            关系列表 [{source, target, type, properties}, ...]
        """

    # ========================================================================
    # 图遍历
    # ========================================================================

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两节点之间的所有路径。

        Args:
            start_id: 起始节点 ID
            end_id: 结束节点 ID
            max_depth: 最大路径长度

        Returns:
            路径列表 [{nodes, relationships, length}, ...]
        """

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的直接邻居（单跳）。

        语义：只返回通过一条边直接相连的邻居节点。
        如需多跳遍历，使用 find_related 方法。

        与 find_related 的区别：
        - get_neighbors: 单跳直接邻居（1-N 关系）
        - find_related: 多跳可达节点（1-N-N... 关系）

        Args:
            node_id: 节点 ID
            rel_type: 过滤边类型，None 表示所有类型
            direction: 遍历方向（"IN" / "OUT" / "BOTH"），默认 "BOTH"

        Returns:
            直接邻居节点列表 [{id, labels, properties}, ...]
        """

    async def find_related(
        self,
        node_id: str,
        max_depth: int = 2,
        edge_type: str | None = None,
    ) -> list[dict]:
        """查找关联节点（多跳遍历）。

        与 get_neighbors 的区别：
        - get_neighbors: 单跳直接邻居
        - find_related: 多跳可达节点

        Args:
            node_id: 起始节点 ID
            max_depth: 最大遍历深度（默认 2）
            edge_type: 过滤边类型，None 表示所有

        Returns:
            关联节点列表 [{id, labels, properties, path}, ...]
        """

    # ========================================================================
    # 低级 Cypher（供领域适配器使用）
    # ========================================================================

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读 Cypher 查询。

        供领域适配器（如 MemoryGraphAdapter）使用，
        用于实现高级领域语义。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入 Cypher 查询。

        供领域适配器（如 MemoryGraphAdapter）使用，
        用于实现高级领域语义。

        Args:
            cypher: Cypher 写入语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """
```

### 3.3 方法映射：旧 → 新

| 旧方法 | 新方法 | 变化 |
|--------|--------|------|
| `create_entity(memory_id, entity_type, properties)` | `create_node(node_id, labels, properties)` | 参数改为通用，移除 memory_id 语义 |
| `get_entity(memory_id)` | `get_node(node_id)` | 参数改为通用 |
| `delete_entity(memory_id)` | `delete_node(node_id)` | 参数改为通用 |
| - | `update_node(node_id, properties)` | **新增**：支持属性更新 |
| - | `node_exists(node_id)` | **新增**：存在性检查 |
| `create_relationship(src, tgt, type, props)` | `create_relationship(src_id, tgt_id, rel_type, props)` | 参数名统一 |
| `delete_relationship(src, tgt, type)` | `delete_relationship(src_id, tgt_id, rel_type)` | 参数名统一 |
| - | `get_relationships(node_id, rel_type, direction)` | **新增**：获取关系列表 |
| `get_neighbors(memory_id, max_depth, edge_type)` | `get_neighbors(node_id, rel_type, direction)` | 移除 memory_id 语义，支持 direction |
| `find_related(memory_id, max_depth, rel_type)` | `find_related(node_id, max_depth, edge_type)` | 参数名统一 |
| `execute_query(cypher, params)` | `execute_query(cypher, params)` | 不变 |
| `execute_write_query(cypher, params)` | `execute_write_query(cypher, params)` | 不变 |

---

## 4. Application 层：MemoryGraphPort（记忆领域语义）

### 4.1 设计原则

1. **领域语义**: 继承 L5GraphPort，添加记忆领域概念
2. **memory_id 绑定**: 节点 ID 必须使用 memory_id
3. **专用标签**: 使用 `Memory` 作为基础标签
4. **关系语义**: 定义记忆间关系类型（DEPENDS_ON, RELATED_TO 等）

### 4.2 MemoryGraphPort 接口

```python
# src/domain/ports/memory_graph.py (new)

"""MemoryGraphPort — 记忆图谱领域端口（Application层）。

继承 L5GraphPort，添加记忆领域语义：
- memory_id 作为节点主键
- 使用 Memory 标签
- 记忆间关系语义（DEPENDS_ON, RELATED_TO 等）

设计原则：
- 领域层定义，Application 层使用
- 不依赖 Infrastructure
- 可被 MemoryGraphAdapter 实现（委托给 Neo4jGraphStorage）
"""

from __future__ import annotations

from typing import Any, Protocol

if TYPE_CHECKING:
    pass


class MemoryGraphPort(L5GraphPort):
    """记忆图谱端口（Application层，领域语义）。

    继承 L5GraphPort，添加记忆领域语义：
    - memory_id 作为节点主键
    - 使用 Memory 标签
    - 记忆间关系语义

    用于 UnifiedStorageGateway L5 层的高级操作。
    """

    # ========================================================================
    # 记忆实体操作（使用 memory_id 作为主键）
    # ========================================================================

    async def create_memory_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建记忆实体节点。

        等价于 L5GraphPort.create_node，但：
        - node_id 使用 memory_id
        - 标签固定为 ["Memory", entity_type]
        - 属性包含 memory_id

        Args:
            memory_id: 记忆 ID（主键）
            entity_type: 实体类型（如 "user", "project", "reference"）
            properties: 实体属性

        Returns:
            是否成功
        """

    async def get_memory_entity(
        self,
        memory_id: str,
    ) -> dict | None:
        """获取记忆实体。

        Args:
            memory_id: 记忆 ID

        Returns:
            实体数据 {id, type, properties}，不存在返回 None
        """

    async def delete_memory_entity(
        self,
        memory_id: str,
    ) -> bool:
        """删除记忆实体及所有关联边。

        Args:
            memory_id: 记忆 ID

        Returns:
            是否成功
        """

    async def memory_entity_exists(
        self,
        memory_id: str,
    ) -> bool:
        """检查记忆实体是否存在。

        Args:
            memory_id: 记忆 ID

        Returns:
            是否存在
        """

    # ========================================================================
    # 记忆关系操作
    # ========================================================================

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """链接两个记忆（MERGE 语义）。

        Args:
            source_id: 源记忆 ID
            target_id: 目标记忆 ID
            relationship_type: 关系类型（如 "DEPENDS_ON", "RELATED_TO"）
            properties: 关系属性（可选）

        Returns:
            是否成功
        """

    async def unlink_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
    ) -> bool:
        """取消链接两个记忆。

        Args:
            source_id: 源记忆 ID
            target_id: 目标记忆 ID
            relationship_type: 关系类型

        Returns:
            是否成功
        """

    async def get_memory_links(
        self,
        memory_id: str,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """获取记忆的所有链接。

        Args:
            memory_id: 记忆 ID
            relationship_type: 过滤关系类型，None 表示所有

        Returns:
            链接列表 [{source_id, target_id, type, properties}, ...]
        """

    # ========================================================================
    # 记忆图遍历
    # ========================================================================

    async def find_related_memories(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联记忆（多跳遍历）。

        Args:
            memory_id: 起始记忆 ID
            max_depth: 最大遍历深度（默认 2）
            relationship_type: 过滤关系类型，None 表示所有

        Returns:
            关联记忆列表 [{memory_id, type, properties, path}, ...]
        """

    async def get_memory_neighbors(
        self,
        memory_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取记忆的直接邻居（单跳）。

        对应 L5GraphPort.get_neighbors，专用于记忆图谱。

        Args:
            memory_id: 记忆 ID
            rel_type: 过滤边类型，None 表示所有
            direction: 遍历方向（"IN" / "OUT" / "BOTH"），默认 "BOTH"

        Returns:
            邻居记忆列表 [{memory_id, type, properties}, ...]
        """

    async def find_memory_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两个记忆之间的路径。

        Args:
            start_id: 起始记忆 ID
            end_id: 结束记忆 ID
            max_depth: 最大路径长度

        Returns:
            路径列表 [{nodes, relationships, length}, ...]
        """

    # ========================================================================
    # 批量操作（可选）
    # ========================================================================

    async def batch_create_memory_entities(
        self,
        entities: list[dict],
    ) -> list[bool]:
        """批量创建记忆实体。

        Args:
            entities: 实体列表 [{memory_id, entity_type, properties}, ...]

        Returns:
            结果列表 [success, ...]
        """

    async def batch_link_memories(
        self,
        links: list[dict],
    ) -> list[bool]:
        """批量链接记忆。

        Args:
            links: 链接列表 [{source_id, target_id, relationship_type, properties}, ...]

        Returns:
            结果列表 [success, ...]
        """
```

---

## 5. Infrastructure 层实现

### 5.0 Neo4jConnectionProvider（连接池单例）

**业界对标决策：**

| 考量 | 业界常见方案 | SISYS 决策 | 原因 |
|------|-------------|-----------|------|
| 单例模式 | Borg / 实例化参数 | `__new__` + 类变量 | 简洁够用，无需依赖注入 |
| 初始化安全 | 无锁 / asyncio.Lock | `asyncio.Lock` 保护 | 避免并发初始化竞争 |
| 懒初始化 | 首次使用时 | 懒初始化 driver | 减少启动开销 |
| 连接生命周期 | 无限制 | `max_connection_lifetime` | 防止连接老化 |
| 健康检查 | 单一 ping | 双层检查（连接+池） | 区分连通性与池健康 |
| 代理支持 | 常缺失 | SOCKS5 proxy 支持 | 企业环境必需 |

```python
# src/infrastructure/storage/neo4j/connection_provider.py

"""Neo4j连接池统一提供者（单例模式）。

在composition_root初始化时创建单一连接池，
所有Adapter复用此连接池，实现资源统一管理。

遵循六边形架构：
- 资源管理封装在Infrastructure层
- Domain层完全不感知连接池存在

设计原则：
- 线程安全：asyncio.Lock 保护初始化
- 懒初始化：首次获取 driver 时才创建连接
- 连接生命周期：max_connection_lifetime 防止老化连接
- 可测试性：close() 后可重新 init()
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.infrastructure.config.neo4j import Neo4jConfig
from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Neo4jConnectionProvider:
    """Neo4j连接池统一提供者（单例模式）。

    Attributes:
        _instance: 单例实例
        _client_wrapper: Neo4j客户端封装
        _config: Neo4j配置
        _init_lock: 初始化锁（避免并发竞争）
    """

    _instance: Neo4jConnectionProvider | None = None
    _client_wrapper: Neo4jClientWrapper | None = None
    _config: Neo4jConfig | None = None
    _init_lock: asyncio.Lock | None = None

    def __new__(cls) -> Neo4jConnectionProvider:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def init(cls, config: Neo4jConfig | None = None) -> None:
        """初始化连接池（线程安全）。

        Args:
            config: Neo4j配置，默认从环境变量加载
        """
        # 初始化锁（延迟创建，避免类加载时实例化）
        if cls._init_lock is None:
            cls._init_lock = asyncio.Lock()

        async with cls._init_lock:
            if cls._client_wrapper is not None:
                logger.warning("Neo4jConnectionProvider already initialized, skipping")
                return

            config = config or Neo4jConfig.from_env()
            cls._config = config

            cls._client_wrapper = Neo4jClientWrapper(
                uri=config.uri,
                username=config.username,
                password=config.password,
                database=config.database,
                max_connection_pool_size=config.max_connection_pool_size,
                connection_timeout=config.connection_timeout,
                max_retry_time=config.max_retry_time,
                max_connection_lifetime=config.max_connection_lifetime,
            )
            logger.info(
                "Neo4jConnectionProvider initialized: %s (max_connections=%d, max_lifetime=%ds)",
                config.uri,
                config.max_connection_pool_size,
                config.max_connection_lifetime,
            )

    @classmethod
    def get_client(cls) -> Neo4jClientWrapper:
        """获取Neo4j客户端封装。

        Returns:
            Neo4jClientWrapper实例

        Raises:
            RuntimeError: 如果provider未初始化
        """
        if cls._client_wrapper is None:
            raise RuntimeError(
                "Neo4jConnectionProvider not initialized. "
                "Call await Neo4jConnectionProvider.init() before use."
            )
        return cls._client_wrapper

    @classmethod
    def is_initialized(cls) -> bool:
        """检查provider是否已初始化。"""
        return cls._client_wrapper is not None

    @classmethod
    async def health_check(cls) -> bool:
        """双层健康检查（连接 + 池状态）。

        Returns:
            True 如果连接可用且池状态正常
        """
        if cls._client_wrapper is None:
            return False
        return await cls._client_wrapper.health_check()

    @classmethod
    async def close(cls) -> None:
        """关闭连接池。"""
        if cls._client_wrapper is not None:
            await cls._client_wrapper.close()
            cls._client_wrapper = None
            cls._config = None
            logger.info("Neo4jConnectionProvider closed")
```

### 5.1 Neo4jGraphStorage（技术适配器，Layer 3）

**文件：** `src/infrastructure/storage/neo4j/neo4j_graph_storage.py`

```python
# src/infrastructure/storage/neo4j/neo4j_graph_storage.py

"""Neo4jGraphStorage — L5GraphPort 实现（技术适配器）。

Neo4j 低级 Cypher 执行器，实现 L5GraphPort 接口。
不包含任何领域语义，仅负责：
- 节点/关系 CRUD
- 图遍历查询
- Cypher 执行

与 MemoryGraphAdapter 的关系：
- Neo4jGraphStorage 是技术底层
- MemoryGraphAdapter 委托它执行低级操作，组合领域语义
"""

from __future__ import annotations

from typing import Any, cast

from src.domain.ports.l5_graph import L5GraphPort
from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper


class Neo4jGraphStorage(L5GraphPort):
    """Neo4j 图存储实现（技术适配器）。

    实现 L5GraphPort 接口，提供纯技术图操作。
    使用 Cypher 执行所有操作。
    """

    def __init__(
        self,
        client_wrapper: Neo4jClientWrapper,
        database: str = "neo4j",
    ):
        """初始化图存储。

        Args:
            client_wrapper: Neo4j 客户端封装
            database: 数据库名称
        """
        self._client_wrapper = client_wrapper
        self._database = database

    def _get_driver(self):
        """获取异步驱动。"""
        return self._client_wrapper.get_async_driver()

    # ========================================================================
    # 节点操作实现
    # ========================================================================

    async def create_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> bool:
        """创建节点（MERGE 语义）。"""
        labels_str = ":".join(labels)
        cypher = f"""
        MERGE (n {{id: $node_id}})
        SET n:{labels_str}, n += $properties
        RETURN n
        """
        result = await self.execute_write_query(
            cypher,
            {"node_id": node_id, "properties": properties},
        )
        return len(result) > 0

    async def get_node(self, node_id: str) -> dict | None:
        """获取节点。"""
        cypher = """
        MATCH (n {id: $node_id})
        RETURN n.id as id, labels(n) as labels, properties(n) as properties
        """
        result = await self.execute_query(cypher, {"node_id": node_id})
        if not result:
            return None
        return result[0]

    async def update_node(
        self,
        node_id: str,
        properties: dict[str, Any],
    ) -> bool:
        """更新节点属性。"""
        cypher = """
        MATCH (n {id: $node_id})
        SET n += $properties
        RETURN n
        """
        result = await self.execute_write_query(
            cypher,
            {"node_id": node_id, "properties": properties},
        )
        return len(result) > 0

    async def delete_node(self, node_id: str) -> bool:
        """删除节点（DETACH DELETE）。"""
        cypher = """
        MATCH (n {id: $node_id})
        DETACH DELETE n
        """
        await self.execute_write_query(cypher, {"node_id": node_id})
        return True

    async def node_exists(self, node_id: str) -> bool:
        """检查节点是否存在。"""
        cypher = """
        MATCH (n {id: $node_id})
        RETURN count(n) as count
        """
        result = await self.execute_query(cypher, {"node_id": node_id})
        return result[0].get("count", 0) > 0 if result else False

    # ========================================================================
    # 关系操作实现
    # ========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系（MERGE 语义）。"""
        props_clause = ""
        params = {"source_id": source_id, "target_id": target_id, "rel_type": rel_type}
        if properties:
            props_clause = ", ".join([f"r.{k} = ${k}" for k in properties.keys()])
            if props_clause:
                props_clause = f"SET {props_clause}"
            params.update(properties)

        cypher = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:{rel_type}]->(target)
        {props_clause}
        RETURN r
        """
        result = await self.execute_write_query(cypher, params)
        return len(result) > 0

    async def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """删除关系。"""
        cypher = f"""
        MATCH (source {{id: $source_id}})-[r:{rel_type}]->(target {{id: $target_id}})
        DELETE r
        """
        await self.execute_write_query(
            cypher,
            {"source_id": source_id, "target_id": target_id},
        )
        return True

    async def get_relationships(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的关系。

        Args:
            node_id: 节点 ID
            rel_type: 过滤关系类型，None 表示所有
            direction: 方向（"OUT" / "IN" / "BOTH"）

        Returns:
            关系列表 [{source_id, target_id, type, properties}, ...]
        """
        if rel_type:
            rel_type_clause = f":{rel_type}"
        else:
            rel_type_clause = ""

        if direction == "OUT":
            cypher = f"""
            MATCH (n {{id: $node_id}})-[r{rel_type_clause}]->(target)
            RETURN n.id as source_id, target.id as target_id, type(r) as type, properties(r) as properties
            """
        elif direction == "IN":
            cypher = f"""
            MATCH (n {{id: $node_id}})<-[r{rel_type_clause}]-(source)
            RETURN source.id as source_id, n.id as target_id, type(r) as type, properties(r) as properties
            """
        else:  # BOTH
            cypher = f"""
            MATCH (n {{id: $node_id}})-[r{rel_type_clause}]-(other)
            RETURN n.id as source_id, other.id as target_id, type(r) as type, properties(r) as properties
            """

        return await self.execute_query(cypher, {"node_id": node_id})

    # ========================================================================
    # 图遍历实现
    # ========================================================================

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两节点之间的路径。"""
        cypher = f"""
        MATCH path = (start {{id: $start_id}})-[*1..{max_depth}]-(end {{id: $end_id}})
        RETURN path, length(path) as length
        LIMIT 10
        """
        return await self.execute_query(
            cypher,
            {"start_id": start_id, "end_id": end_id},
        )

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取邻居节点（单跳）。

        Args:
            node_id: 节点 ID
            rel_type: 过滤边类型，None 表示所有类型
            direction: 遍历方向（"IN" / "OUT" / "BOTH"），默认 "BOTH"

        Returns:
            邻居节点列表 [{id, labels, properties}, ...]
        """
        if rel_type:
            rel_type_clause = f":{rel_type}"
        else:
            rel_type_clause = ""

        if direction == "OUT":
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_clause}->(neighbor)
            RETURN distinct neighbor.id as id, labels(neighbor) as labels, properties(neighbor) as properties
            LIMIT 50
            """
        elif direction == "IN":
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_clause}-(neighbor)
            RETURN distinct neighbor.id as id, labels(neighbor) as labels, properties(neighbor) as properties
            LIMIT 50
            """
        else:  # BOTH
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_clause}-(neighbor)
            RETURN distinct neighbor.id as id, labels(neighbor) as labels, properties(neighbor) as properties
            LIMIT 50
            """
        return await self.execute_query(cypher, {"node_id": node_id})

    async def find_related(
        self,
        node_id: str,
        max_depth: int = 2,
        edge_type: str | None = None,
    ) -> list[dict]:
        """查找关联节点（多跳遍历）。"""
        if edge_type:
            cypher = f"""
            MATCH path = (start {{id: $node_id}})-[:{edge_type}*1..{max_depth}]-(end)
            WITH path, end
            RETURN end.id as id, labels(end) as labels, properties(end) as properties, path
            LIMIT 50
            """
        else:
            cypher = f"""
            MATCH path = (start {{id: $node_id}})-[*1..{max_depth}]-(end)
            WITH path, end
            RETURN end.id as id, labels(end) as labels, properties(end) as properties, path
            LIMIT 50
            """
        return await self.execute_query(cypher, {"node_id": node_id})

    # ========================================================================
    # 低级 Cypher 实现
    # ========================================================================

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读 Cypher 查询。"""
        driver = self._get_driver()
        query_params = params or {}
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, **query_params)
            records = cast(list[dict[str, Any]], await result.data())
            return records

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入 Cypher 查询。"""
        driver = self._get_driver()
        query_params = params or {}
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, **query_params)
            records = cast(list[dict[str, Any]], await result.data())
            return records
```

### 5.1.5 BaseGraphAdapter（减少样板代码）

由于 `MemoryGraphPort` 继承 `L5GraphPort`，实现类需要同时实现：
1. 领域方法（create_memory_entity 等）
2. 技术方法委托（create_node 等，满足 L5GraphPort 契约）

为减少样板代码，引入 `BaseGraphAdapter` 作为基类：

```python
# src/infrastructure/storage/neo4j/base_graph_adapter.py (new)

"""BaseGraphAdapter — L5GraphPort 委托基类。

将 L5GraphPort 所有方法委托给内部存储，
子类只需实现领域方法，无需重复委托代码。

使用方式：
class MemoryGraphAdapter(BaseGraphAdapter):
    async def create_memory_entity(self, memory_id, entity_type, properties):
        # 只需实现领域逻辑
        return await self._storage.create_node(...)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.ports.l5_graph import L5GraphPort

if TYPE_CHECKING:
    pass


class BaseGraphAdapter(L5GraphPort):
    """L5GraphPort 委托基类。

    将所有 L5GraphPort 方法委托给内部 _storage。
    子类继承此类后，只需实现领域特定方法。

    Attributes:
        _storage: L5GraphPort 实现（如 Neo4jGraphStorage）
    """

    def __init__(self, storage: L5GraphPort):
        """初始化适配器。

        Args:
            storage: L5GraphPort 实现
        """
        self._storage = storage

    # ========================================================================
    # 节点操作委托
    # ========================================================================

    async def create_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> bool:
        """创建节点（委托）。"""
        return await self._storage.create_node(node_id, labels, properties)

    async def get_node(self, node_id: str) -> dict | None:
        """获取节点（委托）。"""
        return await self._storage.get_node(node_id)

    async def update_node(
        self,
        node_id: str,
        properties: dict[str, Any],
    ) -> bool:
        """更新节点（委托）。"""
        return await self._storage.update_node(node_id, properties)

    async def delete_node(self, node_id: str) -> bool:
        """删除节点（委托）。"""
        return await self._storage.delete_node(node_id)

    async def node_exists(self, node_id: str) -> bool:
        """检查节点存在（委托）。"""
        return await self._storage.node_exists(node_id)

    # ========================================================================
    # 关系操作委托
    # ========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系（委托）。"""
        return await self._storage.create_relationship(source_id, target_id, rel_type, properties)

    async def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """删除关系（委托）。"""
        return await self._storage.delete_relationship(source_id, target_id, rel_type)

    async def get_relationships(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取关系（委托）。"""
        return await self._storage.get_relationships(node_id, rel_type, direction)

    # ========================================================================
    # 图遍历委托
    # ========================================================================

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找路径（委托）。"""
        return await self._storage.find_path(start_id, end_id, max_depth)

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取邻居（委托）。"""
        return await self._storage.get_neighbors(node_id, rel_type, direction)

    async def find_related(
        self,
        node_id: str,
        max_depth: int = 2,
        edge_type: str | None = None,
    ) -> list[dict]:
        """查找关联（委托）。"""
        return await self._storage.find_related(node_id, max_depth, edge_type)

    # ========================================================================
    # Cypher 委托
    # ========================================================================

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读查询（委托）。"""
        return await self._storage.execute_query(cypher, params)

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入查询（委托）。"""
        return await self._storage.execute_write_query(cypher, params)
```

### 5.2 MemoryGraphAdapter（领域适配器，Layer 4）

```python
# src/infrastructure/storage/neo4j/memory_graph_adapter.py (new)

"""MemoryGraphAdapter — MemoryGraphPort 实现（领域适配器）。

继承 BaseGraphAdapter，只需实现记忆领域逻辑。
L5GraphPort 委托由基类处理，无需重复代码。

设计分层：
- BaseGraphAdapter: 处理 L5GraphPort 技术委托
- MemoryGraphAdapter: 处理 MemoryGraphPort 领域逻辑
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.memory_graph import MemoryGraphPort
from src.infrastructure.storage.neo4j.base_graph_adapter import BaseGraphAdapter


class MemoryGraphAdapter(MemoryGraphPort, BaseGraphAdapter):
    """记忆图谱领域适配器。

    继承 BaseGraphAdapter 处理所有 L5GraphPort 委托，
    只需实现 MemoryGraphPort 的领域方法。

    使用 memory_id 作为节点主键，
    标签固定为 ["Memory", entity_type]。
    """

    def __init__(self, storage: L5GraphPort):
        """初始化适配器。

        Args:
            storage: L5GraphPort 实现（如 Neo4jGraphStorage）
        """
        super().__init__(storage)

    # ========================================================================
    # 记忆实体操作实现（MemoryGraphPort 领域方法）
    # ========================================================================

    async def create_memory_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建记忆实体节点。"""
        # memory_id 作为节点 ID，标签为 ["Memory", entity_type]
        return await self._storage.create_node(
            node_id=memory_id,
            labels=["Memory", entity_type],
            properties={"memory_id": memory_id, **properties},
        )

    async def get_memory_entity(self, memory_id: str) -> dict | None:
        """获取记忆实体。"""
        node = await self._storage.get_node(memory_id)
        if node is None:
            return None
        # 提取 entity_type 从 labels（排除 "Memory"）
        labels = node.get("labels", [])
        entity_type = next((l for l in labels if l != "Memory"), "unknown")
        return {
            "memory_id": node.get("id"),
            "type": entity_type,
            "properties": node.get("properties", {}),
        }

    async def delete_memory_entity(self, memory_id: str) -> bool:
        """删除记忆实体。"""
        return await self._storage.delete_node(memory_id)

    async def memory_entity_exists(self, memory_id: str) -> bool:
        """检查记忆实体是否存在。"""
        return await self._storage.node_exists(memory_id)

    # ========================================================================
    # 记忆关系操作实现
    # ========================================================================

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """链接两个记忆。"""
        return await self._storage.create_relationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=relationship_type,
            properties=properties,
        )

    async def unlink_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
    ) -> bool:
        """取消链接两个记忆。"""
        return await self._storage.delete_relationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=relationship_type,
        )

    async def get_memory_links(
        self,
        memory_id: str,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """获取记忆的所有链接。"""
        rels = await self._storage.get_relationships(memory_id, relationship_type, "BOTH")
        return [
            {
                "source_id": r.get("source", {}).get("id"),
                "target_id": r.get("target", {}).get("id"),
                "type": r.get("type"),
                "properties": r.get("properties", {}),
            }
            for r in rels
        ]

    # ========================================================================
    # 记忆图遍历实现
    # ========================================================================

    async def find_related_memories(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联记忆。"""
        nodes = await self._storage.find_related(memory_id, max_depth, relationship_type)
        return [
            {
                "memory_id": n.get("id"),
                "type": next((l for l in n.get("labels", []) if l != "Memory"), "unknown"),
                "properties": n.get("properties", {}),
                "path": n.get("path", []),
            }
            for n in nodes
        ]

    async def get_memory_neighbors(
        self,
        memory_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取记忆的邻居（单跳）。"""
        nodes = await self._storage.get_neighbors(memory_id, rel_type, direction)
        return [
            {
                "memory_id": n.get("id"),
                "type": next((l for l in n.get("labels", []) if l != "Memory"), "unknown"),
                "properties": n.get("properties", {}),
            }
            for n in nodes
        ]

    async def find_memory_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两个记忆之间的路径。"""
        return await self._storage.find_path(start_id, end_id, max_depth)

    # ========================================================================
    # 批量操作实现
    # ========================================================================

    async def batch_create_memory_entities(
        self,
        entities: list[dict],
    ) -> list[bool]:
        """批量创建记忆实体。"""
        results = []
        for entity in entities:
            result = await self.create_memory_entity(
                memory_id=entity["memory_id"],
                entity_type=entity["entity_type"],
                properties=entity.get("properties", {}),
            )
            results.append(result)
        return results

    async def batch_link_memories(
        self,
        links: list[dict],
    ) -> list[bool]:
        """批量链接记忆。"""
        results = []
        for link in links:
            result = await self.link_memories(
                source_id=link["source_id"],
                target_id=link["target_id"],
                relationship_type=link["relationship_type"],
                properties=link.get("properties"),
            )
            results.append(result)
        return results
```

### 5.3 Neo4jAdapter（向后兼容适配器）

```python
# src/infrastructure/storage/neo4j/neo4j_adapter.py (重构)

"""Neo4jAdapter — L5GraphPort 实现（向后兼容适配器）。

保持现有接口签名，内部委托给 Neo4jGraphStorage。
用于向后兼容现有测试和调用方。
"""

from __future__ import annotations

from typing import Any, cast

from src.domain.ports.l5_graph import L5GraphPort
from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage


class Neo4jAdapter(L5GraphPort):
    """Neo4j 适配器（向后兼容）。

    保持现有接口签名，内部委托给 Neo4jGraphStorage。
    新代码建议直接使用 Neo4jGraphStorage 或 MemoryGraphAdapter。
    """

    def __init__(self, storage: Neo4jGraphStorage | L5GraphPort):
        """初始化适配器。

        Args:
            storage: Neo4jGraphStorage 或其他 L5GraphPort 实现
        """
        self._storage = storage

    # ========================================================================
    # 节点操作（委托）
    # ========================================================================

    async def create_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> bool:
        """创建节点（MERGE 语义）。"""
        return await self._storage.create_node(node_id, labels, properties)

    async def get_node(self, node_id: str) -> dict | None:
        """获取节点。"""
        return await self._storage.get_node(node_id)

    async def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """更新节点属性。"""
        return await self._storage.update_node(node_id, properties)

    async def delete_node(self, node_id: str) -> bool:
        """删除节点。"""
        return await self._storage.delete_node(node_id)

    async def node_exists(self, node_id: str) -> bool:
        """检查节点是否存在。"""
        return await self._storage.node_exists(node_id)

    # ========================================================================
    # 关系操作（委托）
    # ========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系（MERGE 语义）。"""
        return await self._storage.create_relationship(source_id, target_id, rel_type, properties)

    async def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """删除关系。"""
        return await self._storage.delete_relationship(source_id, target_id, rel_type)

    async def get_relationships(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的关系。"""
        return await self._storage.get_relationships(node_id, rel_type, direction)

    # ========================================================================
    # 图遍历（委托）
    # ========================================================================

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找路径。"""
        return await self._storage.find_path(start_id, end_id, max_depth)

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取邻居（委托）。"""
        return await self._storage.get_neighbors(node_id, rel_type, direction)

    async def find_related(
        self,
        node_id: str,
        max_depth: int = 2,
        edge_type: str | None = None,
    ) -> list[dict]:
        """查找关联节点。"""
        return await self._storage.find_related(node_id, max_depth, edge_type)

    # ========================================================================
    # 低级 Cypher（委托）
    # ========================================================================

    async def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行只读查询。"""
        return await self._storage.execute_query(cypher, params)

    async def execute_write_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行写入查询。"""
        return await self._storage.execute_write_query(cypher, params)
```

---

## 6. 包结构变更

### 6.1 文件变更清单

| 操作 | 文件路径 | 说明 | Layer |
|------|----------|------|-------|
| **修改** | `src/domain/ports/l5_graph.py` | 重构为纯技术接口 | L1 |
| **新增** | `src/domain/ports/memory_graph.py` | MemoryGraphPort 定义 | L2 |
| **新增** | `src/infrastructure/storage/neo4j/connection_provider.py` | Neo4jConnectionProvider 单例 | L3 |
| **新增** | `src/infrastructure/storage/neo4j/neo4j_graph_storage.py` | Neo4jGraphStorage 实现 | L3 |
| **新增** | `src/infrastructure/storage/neo4j/memory_graph_adapter.py` | MemoryGraphAdapter 实现 | L4 |
| **修改** | `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 重构为委托 Neo4jGraphStorage | L3 |
| **修改** | `src/infrastructure/storage/neo4j/__init__.py` | 导出新组件 | - |
| **修改** | `src/domain/ports/__init__.py` | 导出 MemoryGraphPort | - |

### 6.2 Layer 3: 连接池管理（对比L1缓存架构）

```python
# L1缓存层：RedisPoolProvider
# 位置：src/infrastructure/storage/redis/pool_provider.py
class RedisPoolProvider:
    _pool: aioredis.ConnectionPool
    @classmethod
    def init(cls, config: RedisConfig) -> None: ...
    @classmethod
    def get_client(cls) -> aioredis.Redis: ...

# L5图存储层：Neo4jConnectionProvider
# 位置：src/infrastructure/storage/neo4j/connection_provider.py
class Neo4jConnectionProvider:
    _client_wrapper: Neo4jClientWrapper
    @classmethod
    def init(cls, config: Neo4jConfig) -> None: ...
    @classmethod
    def get_client(cls) -> Neo4jClientWrapper: ...
    @classmethod
    async def close(cls) -> None: ...
```

### 6.3 导出更新

```python
# src/infrastructure/storage/neo4j/__init__.py

"""Neo4j 图数据库存储层包。"""

from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter
from src.infrastructure.storage.neo4j.neo4j_graph_storage import Neo4jGraphStorage
from src.infrastructure.storage.neo4j.memory_graph_adapter import MemoryGraphAdapter

__all__ = [
    "Neo4jAdapter",      # 向后兼容
    "Neo4jGraphStorage", # L5GraphPort 技术实现
    "MemoryGraphAdapter", # MemoryGraphPort 领域实现
]
```

```python
# src/domain/ports/__init__.py (追加)

from src.domain.ports.memory_graph import MemoryGraphPort

__all__ = [
    # ... 现有导出 ...
    "MemoryGraphPort",
]
```

---

## 7. 测试设计

### 7.1 测试策略

| 测试类型 | 测试对象 | 验证点 |
|----------|----------|--------|
| **单元测试** | `L5GraphPort` | Protocol 契约（所有方法 async） |
| **单元测试** | `Neo4jGraphStorage` | 技术实现正确性 |
| **单元测试** | `MemoryGraphAdapter` | 领域逻辑正确性 |
| **集成测试** | `Neo4jAdapter` | 向后兼容（委托正确） |

### 7.2 测试文件变更

```python
# tests/unit/domain/ports/test_l5_graph_port.py

class TestL5GraphPortSignature:
    """结构签名测试 — 验证 async 契约。"""

    def test_all_methods_are_async(self) -> None:
        """所有方法应该是 async。"""
        for method_name in [
            "create_node",
            "get_node",
            "update_node",
            "delete_node",
            "node_exists",
            "create_relationship",
            "delete_relationship",
            "get_relationships",
            "find_path",
            "get_neighbors",
            "find_related",
            "execute_query",
            "execute_write_query",
        ]:
            method = getattr(L5GraphPort, method_name)
            assert inspect.iscoroutinefunction(method)
```

```python
# tests/unit/infrastructure/storage/test_neo4j_graph_storage.py (new)

class TestNeo4jGraphStorageCreateNode:
    """create_node 方法验证。"""
    ...

class TestNeo4jGraphStorageRelationships:
    """关系操作验证。"""
    ...

class TestNeo4jGraphStorageTraversal:
    """图遍历验证。"""
    ...
```

```python
# tests/unit/infrastructure/storage/test_memory_graph_adapter.py (new)

class TestMemoryGraphAdapterEntity:
    """记忆实体操作验证。"""

    async def test_create_memory_entity_uses_memory_id_as_node_id(self):
        """验证使用 memory_id 作为节点 ID。"""
        mock_storage = AsyncMock(spec=L5GraphPort)
        mock_storage.create_node = AsyncMock(return_value=True)

        adapter = MemoryGraphAdapter(mock_storage)
        result = await adapter.create_memory_entity(
            memory_id="mem-123",
            entity_type="project",
            properties={"name": "Test"},
        )

        assert result is True
        mock_storage.create_node.assert_called_once_with(
            node_id="mem-123",
            labels=["Memory", "project"],
            properties={"memory_id": "mem-123", "name": "Test"},
        )
```

---

## 8. 执行步骤（含状态跟踪）

### 执行状态总览

| Phase | 状态 | P0修复 | P1修复 | P2修复 |
|-------|------|--------|--------|--------|
| Phase 1 | ⬜ 未开始 | 1 | 1 | 2 |
| Phase 2 | ⬜ 未开始 | 3 | 2 | 1 |
| Phase 3 | ⬜ 未开始 | 0 | 3 | 0 |
| Phase 4 | ⬜ 未开始 | 0 | 0 | 0 |
| Phase 5 | ⬜ 未开始 | 0 | 1 | 0 |

---

### Phase 1: Domain 层重构 + P0问题修复

**目标**: 重构 L5GraphPort 为纯技术接口，修复 Neo4jClientWrapper 竞态条件

#### Step 1.1: 修复 `Neo4jClientWrapper` 线程安全问题（P0-5）

- [ ] **修复位置**: `src/infrastructure/storage/neo4j/client.py`
- [ ] **问题**: `get_async_driver()` 懒初始化存在竞态条件
- [ ] **修复代码**:

```python
# src/infrastructure/storage/neo4j/client.py
# 修改后的代码

from __future__ import annotations

import asyncio
from neo4j import AsyncDriver, AsyncGraphDatabase

class Neo4jClientWrapper:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: float = 30.0,
        max_retry_time: float = 30.0,
    ):
        # ... 现有初始化代码保持不变 ...
        self._driver: AsyncDriver | None = None
        self._driver_lock = asyncio.Lock()  # 新增：线程安全锁

    async def get_async_driver(self) -> AsyncDriver:
        """获取异步驱动（线程安全的懒初始化）。

        使用双检锁模式确保只有一个协程初始化 driver。
        """
        if self._driver is None:
            async with self._driver_lock:
                # 双重检查：其他协程可能在等待锁期间已创建
                if self._driver is None:
                    self._driver = self._create_driver()
        return self._driver

    async def health_check(self) -> bool:
        """检查 Neo4j 服务是否可用。"""
        try:
            driver = await self.get_async_driver()
            async with driver.session(database=self._database) as session:
                result = await session.run("RETURN 1")
                await result.single()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """关闭驱动连接。"""
        async with self._driver_lock:
            if self._driver is not None:
                await self._driver.close()
                self._driver = None
```

- [ ] **验证**: `poetry run python -c "import asyncio; from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper; w = Neo4jClientWrapper(); print(asyncio.iscoroutinefunction(w.get_async_driver))"`

#### Step 1.2: 创建 `src/domain/ports/memory_graph.py`（P2-3）

- [ ] **创建文件**: `src/domain/ports/memory_graph.py`
- [ ] **接口定义**:

```python
# src/domain/ports/memory_graph.py

"""MemoryGraphPort — 记忆图谱领域端口（Application层）。

继承 L5GraphPort，添加记忆领域语义：
- memory_id 作为节点主键
- 使用 Memory 标签
- 记忆间关系语义（DEPENDS_ON, RELATED_TO 等）
"""

from __future__ import annotations

from typing import Any, Protocol

if TYPE_CHECKING:
    pass


class MemoryGraphPort(L5GraphPort):
    """记忆图谱端口（Application层，领域语义）。

    继承 L5GraphPort，添加记忆领域语义。
    """

    async def create_memory_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建记忆实体节点。"""

    async def get_memory_entity(self, memory_id: str) -> dict | None:
        """获取记忆实体。"""

    async def delete_memory_entity(self, memory_id: str) -> bool:
        """删除记忆实体及所有关联边。"""

    async def memory_entity_exists(self, memory_id: str) -> bool:
        """检查记忆实体是否存在。"""

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """链接两个记忆（MERGE 语义）。"""

    async def unlink_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
    ) -> bool:
        """取消链接两个记忆。"""

    async def get_memory_links(
        self,
        memory_id: str,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """获取记忆的所有链接。"""

    async def find_related_memories(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联记忆（多跳遍历）。"""

    async def get_memory_neighbors(
        self,
        memory_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取记忆的直接邻居（单跳）。"""

    async def find_memory_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两个记忆之间的路径。"""

    async def batch_create_memory_entities(self, entities: list[dict]) -> list[bool]:
        """批量创建记忆实体。"""

    async def batch_link_memories(self, links: list[dict]) -> list[bool]:
        """批量链接记忆。"""
```

#### Step 1.3: 重构 `src/domain/ports/l5_graph.py`（P1-6, P2-1）

- [ ] **备份**: `cp src/domain/ports/l5_graph.py src/domain/ports/l5_graph.py.bak`
- [ ] **重构为纯技术接口**:

```python
# src/domain/ports/l5_graph.py (新版本)

"""L5GraphPort — L5 图存储抽象端口（Domain层）。

设计原则：
- 纯技术接口：不包含任何领域语义
- 领域知识（如 memory_id）由 Application 层端口定义
- 支持任意节点类型和关系类型
"""

from __future__ import annotations

from typing import Any, Protocol


class L5GraphPort(Protocol):
    """L5 图存储端口（Domain层，纯技术抽象）。"""

    # ========================================================================
    # 节点操作
    # ========================================================================

    async def create_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> bool:
        """创建节点（MERGE 语义）。

        Returns:
            是否成功（MERGE 语义：已存在返回 True）
        """

    async def get_node(self, node_id: str) -> dict | None:
        """获取节点。

        Returns:
            节点数据 {id, labels, properties}，不存在返回 None
        """

    async def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """更新节点属性（增量更新）。

        Returns:
            是否成功
        """

    async def delete_node(self, node_id: str) -> bool:
        """删除节点及所有关联边（DETACH DELETE）。

        Returns:
            是否成功
        """

    async def node_exists(self, node_id: str) -> bool:
        """检查节点是否存在。

        Returns:
            是否存在
        """

    # ========================================================================
    # 关系操作
    # ========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边（MERGE 语义）。

        Returns:
            是否成功（MERGE 语义：已存在返回 True）
        """

    async def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """删除关系边。

        Returns:
            是否成功
        """

    async def get_relationships(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的关系。

        Args:
            node_id: 节点 ID
            rel_type: 过滤关系类型，None 表示所有
            direction: 方向（"OUT" / "IN" / "BOTH"）

        Returns:
            关系列表 [{source_id, target_id, type, properties}, ...]
        """

    # ========================================================================
    # 图遍历
    # ========================================================================

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两节点之间的所有路径。

        Returns:
            路径列表 [{nodes, relationships, length}, ...]
        """

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的直接邻居（单跳）。

        Returns:
            直接邻居节点列表 [{id, labels, properties}, ...]
        """

    async def find_related(
        self,
        node_id: str,
        max_depth: int = 2,
        rel_type: str | None = None,
    ) -> list[dict]:
        """查找关联节点（多跳遍历）。

        Returns:
            关联节点列表 [{id, labels, properties, path}, ...]
        """

    # ========================================================================
    # 低级 Cypher（供领域适配器使用）
    # ========================================================================

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读 Cypher 查询。

        Returns:
            查询结果列表（字典列表）
        """

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入 Cypher 查询（使用 session.execute_write）。

        Returns:
            查询结果列表（字典列表）
        """
```

- [ ] **更新 `src/domain/ports/__init__.py`**:

```python
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.memory_graph import MemoryGraphPort

__all__ = [
    # ... existing ...
    "L5GraphPort",
    "MemoryGraphPort",
]
```

- [ ] **验证**: `poetry run python -c "from src.domain.ports import L5GraphPort, MemoryGraphPort; print('Domain层重构完成')"`

---

### Phase 2: Infrastructure 层实现 + P0问题修复

**目标**: 实现 Neo4jGraphStorage 完整 L5GraphPort，修复 Neo4jAdapter 非薄适配器问题

#### Step 2.1: 修复 `Neo4jGraphStorage.execute_write_query` 事务问题（P0-4）

- [ ] **修复位置**: `src/infrastructure/storage/neo4j/graph_storage.py`
- [ ] **问题**: `execute_write_query` 使用 `session.run()` 而非 `session.execute_write()`
- [ ] **修复代码**:

```python
# src/infrastructure/storage/neo4j/graph_storage.py
# 修改 execute_write_query 方法

async def execute_write_query(
    self,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> list[dict]:
    """执行写入 Cypher 查询（使用 managed transaction）。

    使用 session.execute_write() 提供：
    - 自动重试（处理 TransientTransactionErrors）
    - 正确的事务边界
    - 因果一致性

    Args:
        cypher: Cypher 写入语句
        params: 查询参数字典

    Returns:
        查询结果列表（字典列表）
    """
    driver = self._get_driver()
    query_params = params or {}

    async def _execute_in_transaction(tx: Any) -> list[dict]:
        result = await tx.run(cypher, **query_params)
        return cast(list[dict[str, Any]], await result.data())

    async with driver.session(database=self._database) as session:
        return await session.execute_write(_execute_in_transaction)

# 同时更新 execute_query 使用 execute_read（可选优化）
async def execute_query(
    self,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> list[dict]:
    """执行只读 Cypher 查询。"""
    driver = self._get_driver()
    query_params = params or {}

    async def _execute_in_transaction(tx: Any) -> list[dict]:
        result = await tx.run(cypher, **query_params)
        return cast(list[dict[str, Any]], await result.data())

    async with driver.session(database=self._database) as session:
        return await session.execute_read(_execute_in_transaction)
```

- [ ] **修复 `get_neighbors` 返回值序列化问题（P1-2）**:

```python
# 在 Neo4jGraphStorage 中修复 get_neighbors 和 find_path 的返回值

async def get_neighbors(
    self,
    node_id: str,
    rel_type: str | None = None,
    direction: str = "BOTH",
) -> list[dict]:
    """获取邻居节点（单跳）。

    修复：返回 dict 而非 neo4j.Node 对象
    """
    if rel_type:
        rel_type_clause = f":{rel_type}"
    else:
        rel_type_clause = ""

    if direction == "OUT":
        cypher = f"""
        MATCH (n {{id: $node_id}}){rel_type_clause}->(neighbor)
        RETURN neighbor.id as id, labels(neighbor) as labels, properties(neighbor) as properties
        LIMIT 50
        """
    elif direction == "IN":
        cypher = f"""
        MATCH (n {{id: $node_id}}){rel_type_clause}-(neighbor)
        RETURN neighbor.id as id, labels(neighbor) as labels, properties(neighbor) as properties
        LIMIT 50
        """
    else:  # BOTH
        cypher = f"""
        MATCH (n {{id: $node_id}}){rel_type_clause}-(neighbor)
        RETURN neighbor.id as id, labels(neighbor) as labels, properties(neighbor) as properties
        LIMIT 50
        """

    result = await self.execute_query(cypher, {"node_id": node_id})
    return result

async def find_path(
    self,
    start_id: str,
    end_id: str,
    max_depth: int = 3,
) -> list[dict]:
    """查找两节点之间的路径。

    修复：返回序列化的路径信息而非 neo4j.Path 对象
    """
    cypher = f"""
    MATCH path = (start {{id: $start_id}})-[*1..{max_depth}]-(end {{id: $end_id}})
    RETURN start.id as start_id, end.id as end_id, length(path) as length,
           [n in nodes(path) | {{id: n.id, labels: labels(n)}}] as nodes,
           [r in relationships(path) | {{type: type(r), start: startNode(r).id, end: endNode(r).id}}] as relationships
    LIMIT 10
    """
    return await self.execute_query(
        cypher,
        {"start_id": start_id, "end_id": end_id},
    )
```

- [ ] **验证**: `poetry run python -c "from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage; print('execute_write_query 事务修复完成')"`

#### Step 2.2: 实现 `Neo4jGraphStorage` 完整 L5GraphPort 方法（P1-1）

- [ ] **新增方法到 `Neo4jGraphStorage`**:

```python
# src/infrastructure/storage/neo4j/neo4j_graph_storage.py
# 在现有方法后追加以下方法

# ========================================================================
# 实体操作（实现 L5GraphPort）
# ========================================================================

async def create_entity(
    self,
    memory_id: str,
    entity_type: str,
    properties: dict[str, Any],
) -> bool:
    """创建实体节点（MERGE 语义）。

    注意：这是旧接口方法，建议使用 create_node
    """
    cypher = """
    MERGE (n:Memory {id: $memory_id})
    SET n.type = $entity_type, n += $properties
    RETURN n
    """
    result = await self.execute_write_query(
        cypher,
        {"memory_id": memory_id, "entity_type": entity_type, "properties": properties},
    )
    return len(result) > 0

async def get_entity(self, memory_id: str) -> dict | None:
    """获取实体。"""
    cypher = """
    MATCH (n:Memory {id: $memory_id})
    RETURN n.id as id, n.type as type, properties(n) as properties
    """
    result = await self.execute_query(cypher, {"memory_id": memory_id})
    if not result:
        return None
    return result[0]

async def delete_entity(self, memory_id: str) -> bool:
    """删除实体及关联边。"""
    cypher = """
    MATCH (n:Memory {id: $memory_id})
    DETACH DELETE n
    """
    await self.execute_write_query(cypher, {"memory_id": memory_id})
    return True

# ========================================================================
# 关系操作（实现 L5GraphPort）
# ========================================================================

async def create_relationship_by_memory(
    self,
    source_memory_id: str,
    target_memory_id: str,
    relationship_type: str,
    properties: dict[str, Any] | None = None,
) -> bool:
    """创建关系边（MERGE 语义）。

    注意：这是旧接口方法，建议使用 create_relationship
    """
    props_clause = ""
    params = {
        "source_memory_id": source_memory_id,
        "target_memory_id": target_memory_id,
        "relationship_type": relationship_type,
    }
    if properties:
        props_clause = ", ".join([f"r.{k} = ${k}" for k in properties.keys()])
        if props_clause:
            props_clause = f"SET {props_clause}"
        params.update(properties)

    cypher = f"""
    MATCH (source:Memory {{id: $source_memory_id}})
    MATCH (target:Memory {{id: $target_memory_id}})
    MERGE (source)-[r:{relationship_type}]->(target)
    {props_clause}
    RETURN r
    """
    result = await self.execute_write_query(cypher, params)
    return len(result) > 0

async def delete_relationship_by_memory(
    self,
    source_memory_id: str,
    target_memory_id: str,
    relationship_type: str,
) -> bool:
    """删除关系边。"""
    cypher = f"""
    MATCH (source:Memory {{id: $source_memory_id}})-[r:{relationship_type}]->(target:Memory {{id: $target_memory_id}})
    DELETE r
    """
    await self.execute_write_query(
        cypher,
        {"source_memory_id": source_memory_id, "target_memory_id": target_memory_id},
    )
    return True

# ========================================================================
# find_related 实现
# ========================================================================

async def find_related(
    self,
    memory_id: str,
    max_depth: int = 2,
    relationship_type: str | None = None,
) -> list[dict]:
    """查找关联实体（多跳遍历）。"""
    if relationship_type:
        cypher = f"""
        MATCH path = (start:Memory {{id: $memory_id}})-[:{relationship_type}*1..{max_depth}]-(end)
        WITH path, end
        RETURN end.id as memory_id, end.type as type, properties(end) as properties
        LIMIT 50
        """
    else:
        cypher = f"""
        MATCH path = (start:Memory {{id: $memory_id}})-[*1..{max_depth}]-(end)
        WITH path, end
        RETURN end.id as memory_id, end.type as type, properties(end) as properties
        LIMIT 50
        """
    result = await self.execute_query(cypher, {"memory_id": memory_id})
    return [
        {
            "memory_id": r.get("memory_id"),
            "type": r.get("type"),
            "properties": r.get("properties", {}),
        }
        for r in result
    ]
```

- [ ] **验证**: `poetry run python -c "from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage; g = Neo4jGraphStorage.__dict__; print('create_entity' in g, 'get_entity' in g, 'delete_entity' in g, 'find_related' in g)"`

#### Step 2.3: 重构 `Neo4jAdapter` 为薄适配器（P0-2, P0-3）

- [ ] **修复位置**: `src/infrastructure/storage/neo4j/neo4j_adapter.py`
- [ ] **问题**: 自己拼接 Cypher，硬编码 Memory 标签
- [ ] **修复代码**:

```python
# src/infrastructure/storage/neo4j/neo4j_adapter.py (重构后)

"""Neo4jAdapter — L5GraphPort 实现（薄适配器）。

设计原则：
- 薄适配器：只做接口转换，不含领域逻辑
- 所有 Cypher 构造委托给 Neo4jGraphStorage
- 移除硬编码 Memory 标签
"""

from __future__ import annotations

from typing import Any, cast

from src.domain.ports.l5_graph import L5GraphPort

if TYPE_CHECKING:
    pass


class Neo4jAdapter(L5GraphPort):
    """Neo4j 图存储适配器（薄适配器）。

    委托所有操作给内部存储，不自己做 Cypher 构造。
    """

    def __init__(self, storage: Any):
        """初始化适配器。

        Args:
            storage: Neo4jGraphStorage 实例
        """
        self._storage = storage

    # ========================================================================
    # 节点操作（委托）
    # ========================================================================

    async def create_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> bool:
        """创建节点（委托）。"""
        return await self._storage.create_node(node_id, labels, properties)

    async def get_node(self, node_id: str) -> dict | None:
        """获取节点（委托）。"""
        return await self._storage.get_node(node_id)

    async def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """更新节点（委托）。"""
        return await self._storage.update_node(node_id, properties)

    async def delete_node(self, node_id: str) -> bool:
        """删除节点（委托）。"""
        return await self._storage.delete_node(node_id)

    async def node_exists(self, node_id: str) -> bool:
        """检查节点存在（委托）。"""
        return await self._storage.node_exists(node_id)

    # ========================================================================
    # 关系操作（委托）
    # ========================================================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系（委托）。"""
        return await self._storage.create_relationship(source_id, target_id, rel_type, properties)

    async def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """删除关系（委托）。"""
        return await self._storage.delete_relationship(source_id, target_id, rel_type)

    async def get_relationships(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取关系（委托）。"""
        return await self._storage.get_relationships(node_id, rel_type, direction)

    # ========================================================================
    # 图遍历（委托）
    # ========================================================================

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找路径（委托）。"""
        return await self._storage.find_path(start_id, end_id, max_depth)

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取邻居（委托）。"""
        return await self._storage.get_neighbors(node_id, rel_type, direction)

    async def find_related(
        self,
        node_id: str,
        max_depth: int = 2,
        rel_type: str | None = None,
    ) -> list[dict]:
        """查找关联（委托）。"""
        return await self._storage.find_related(node_id, max_depth, rel_type)

    # ========================================================================
    # 低级 Cypher（委托）
    # ========================================================================

    async def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行只读查询（委托）。"""
        return await self._storage.execute_query(cypher, params)

    async def execute_write_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行写入查询（委托）。"""
        return await self._storage.execute_write_query(cypher, params)

    # ========================================================================
    # 旧接口方法（deprecated，委托给新接口）
    # ========================================================================

    async def create_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建实体节点。

        Deprecated: 使用 create_node() 替代
        """
        return await self._storage.create_entity(memory_id, entity_type, properties)

    async def get_entity(self, memory_id: str) -> dict | None:
        """获取实体。

        Deprecated: 使用 get_node() 替代
        """
        return await self._storage.get_entity(memory_id)

    async def delete_entity(self, memory_id: str) -> bool:
        """删除实体。

        Deprecated: 使用 delete_node() 替代
        """
        return await self._storage.delete_entity(memory_id)

    async def create_relationship_old(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系。

        Deprecated: 使用 create_relationship() 替代
        """
        return await self._storage.create_relationship_by_memory(
            source_memory_id, target_memory_id, relationship_type, properties
        )

    async def delete_relationship_old(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
    ) -> bool:
        """删除关系。

        Deprecated: 使用 delete_relationship() 替代
        """
        return await self._storage.delete_relationship_by_memory(
            source_memory_id, target_memory_id, relationship_type
        )

    async def find_related_old(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联实体。

        Deprecated: 使用 find_related() 替代
        """
        return await self._storage.find_related(memory_id, max_depth, relationship_type)
```

- [ ] **验证**: `poetry run python -c "from src.infrastructure.storage.neo4j import Neo4jAdapter; print('Neo4jAdapter重构为薄适配器完成')"`

#### Step 2.4: 创建 `Neo4jConnectionProvider` 单例（P2-2）

- [ ] **创建文件**: `src/infrastructure/storage/neo4j/connection_provider.py`

```python
# src/infrastructure/storage/neo4j/connection_provider.py

"""Neo4j 连接池统一提供者（单例模式）。

在 composition_root 初始化时创建单一连接池，
所有 Adapter 复用此连接池，实现资源统一管理。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.infrastructure.config.neo4j import Neo4jConfig
from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Neo4jConnectionProvider:
    """Neo4j 连接池统一提供者（单例模式）。

    Attributes:
        _instance: 单例实例
        _client_wrapper: Neo4j 客户端封装
        _config: Neo4j 配置
        _init_lock: 初始化锁（避免并发竞争）
    """

    _instance: Neo4jConnectionProvider | None = None
    _client_wrapper: Neo4jClientWrapper | None = None
    _config: Neo4jConfig | None = None
    _init_lock: asyncio.Lock | None = None

    def __new__(cls) -> Neo4jConnectionProvider:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def init(cls, config: Neo4jConfig | None = None) -> None:
        """初始化连接池（线程安全）。

        Args:
            config: Neo4j 配置，默认从环境变量加载
        """
        if cls._init_lock is None:
            cls._init_lock = asyncio.Lock()

        async with cls._init_lock:
            if cls._client_wrapper is not None:
                logger.warning("Neo4jConnectionProvider already initialized, skipping")
                return

            config = config or Neo4jConfig.from_env()
            cls._config = config

            cls._client_wrapper = Neo4jClientWrapper(
                uri=config.uri,
                username=config.username,
                password=config.password,
                database=config.database,
                max_connection_pool_size=config.max_connection_pool_size,
                connection_timeout=config.connection_timeout,
                max_retry_time=config.max_retry_time,
                max_connection_lifetime=config.max_connection_lifetime,
            )
            logger.info(
                "Neo4jConnectionProvider initialized: %s (max_connections=%d)",
                config.uri,
                config.max_connection_pool_size,
            )

    @classmethod
    def get_client(cls) -> Neo4jClientWrapper:
        """获取 Neo4j 客户端封装。

        Returns:
            Neo4jClientWrapper 实例

        Raises:
            RuntimeError: 如果 provider 未初始化
        """
        if cls._client_wrapper is None:
            raise RuntimeError(
                "Neo4jConnectionProvider not initialized. "
                "Call await Neo4jConnectionProvider.init() before use."
            )
        return cls._client_wrapper

    @classmethod
    def is_initialized(cls) -> bool:
        """检查 provider 是否已初始化。"""
        return cls._client_wrapper is not None

    @classmethod
    async def health_check(cls) -> bool:
        """双层健康检查（连接 + 池状态）。"""
        if cls._client_wrapper is None:
            return False
        return await cls._client_wrapper.health_check()

    @classmethod
    async def close(cls) -> None:
        """关闭连接池。"""
        if cls._client_wrapper is not None:
            await cls._client_wrapper.close()
            cls._client_wrapper = None
            cls._config = None
            logger.info("Neo4jConnectionProvider closed")
```

- [ ] **验证**: `poetry run python -c "from src.infrastructure.storage.neo4j.connection_provider import Neo4jConnectionProvider; p1 = Neo4jConnectionProvider(); p2 = Neo4jConnectionProvider(); print('单例:', p1 is p2)"`

---

### Phase 3: 测试更新

#### Step 3.1: 更新 `test_l5_graph_port.py` mock 返回值（P1-6）

- [ ] **修复位置**: `tests/unit/domain/ports/test_l5_graph_port.py`
- [ ] **问题**: mock 返回值与接口定义不符
- [ ] **修复代码**:

```python
# tests/unit/domain/ports/test_l5_graph_port.py

# 修改前（错误）：
mock.create_entity.return_value = {"memory_id": "id-1", "type": "user"}

# 修改后（正确）：
mock.create_entity.return_value = True  # create_entity 返回 bool

# 修改前（错误）：
mock.create_relationship.return_value = {"source": "id-1", "target": "id-2", "type": "RELATES_TO"}

# 修改后（正确）：
mock.create_relationship.return_value = True  # create_relationship 返回 bool

# 完整的测试类修改：

class TestL5GraphPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束。"""

    async def test_mock_create_entity_verified(self):
        """Mock create_entity should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.create_entity.return_value = True  # 修复：Protocol 返回 bool

        result = await mock.create_entity("id-1", "user", {"name": "test"})
        assert result is True  # 修复：布尔断言
        mock.create_entity.assert_called_once()

    async def test_mock_get_entity_verified(self):
        """Mock get_entity should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.get_entity.return_value = {"id": "id-1", "type": "user", "properties": {}}  # 修复：使用 id 而非 memory_id

        result = await mock.get_entity("id-1")
        assert result["id"] == "id-1"
        mock.get_entity.assert_called_once_with("id-1")

    async def test_mock_create_relationship_verified(self):
        """Mock create_relationship should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.create_relationship.return_value = True  # 修复：返回 bool

        result = await mock.create_relationship("id-1", "id-2", "RELATES_TO", {})
        assert result is True  # 修复：布尔断言
        mock.create_relationship.assert_called_once()
```

#### Step 3.2: 添加 `test_neo4j_adapter.py` 的 `get_neighbors` 测试（P1-4）

- [ ] **添加测试类**:

```python
# tests/unit/infrastructure/storage/test_neo4j_adapter.py
# 在现有测试类后添加

class TestNeo4jAdapterGetNeighbors:
    """get_neighbors 方法测试。"""

    async def test_get_neighbors_delegates_to_storage(self):
        """验证 get_neighbors 委托给 storage。"""
        mock_storage = AsyncMock(spec=Neo4jGraphStorage)
        mock_storage.get_neighbors.return_value = [
            {"id": "neighbor-1", "labels": ["Memory"], "properties": {}}
        ]

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.get_neighbors("node-1", rel_type="RELATES_TO", direction="OUT")

        mock_storage.get_neighbors.assert_called_once_with("node-1", "RELATES_TO", "OUT")
        assert len(result) == 1

    async def test_get_neighbors_returns_neighbors(self):
        """验证 get_neighbors 返回正确数据结构。"""
        mock_storage = AsyncMock(spec=Neo4jGraphStorage)
        mock_storage.get_neighbors.return_value = [
            {"id": "neighbor-1", "labels": ["Memory", "project"], "properties": {"name": "Test"}}
        ]

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.get_neighbors("node-1")

        assert result[0]["id"] == "neighbor-1"
        assert result[0]["labels"] == ["Memory", "project"]

    async def test_get_neighbors_empty_result(self):
        """验证 get_neighbors 无结果时返回空列表。"""
        mock_storage = AsyncMock(spec=Neo4jGraphStorage)
        mock_storage.get_neighbors.return_value = []

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.get_neighbors("nonexistent")

        assert result == []
```

#### Step 3.3: 创建 `test_neo4j_graph_storage.py`（P1-1）

- [ ] **创建文件**: `tests/unit/infrastructure/storage/test_neo4j_graph_storage.py`

```python
# tests/unit/infrastructure/storage/test_neo4j_graph_storage.py

"""Neo4jGraphStorage 单元测试。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper


class TestNeo4jGraphStorageCreateNode:
    """create_node 方法测试。"""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=Neo4jClientWrapper)

    @pytest.fixture
    def storage(self, mock_client):
        return Neo4jGraphStorage(mock_client, database="neo4j")

    async def test_create_node_returns_bool(self, storage, mock_client):
        """验证 create_node 返回布尔值。"""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute_write = AsyncMock(return_value=[{"n": {}}])

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_client.get_async_driver = MagicMock(return_value=mock_driver)

        result = await storage.create_node("node-1", ["Label"], {"key": "value"})
        assert isinstance(result, bool)


class TestNeo4jGraphStorageExecuteWrite:
    """execute_write_query 事务测试。"""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=Neo4jClientWrapper)

    @pytest.fixture
    def storage(self, mock_client):
        return Neo4jGraphStorage(mock_client, database="neo4j")

    async def test_execute_write_uses_transaction(self, storage, mock_client):
        """验证 execute_write_query 使用 session.execute_write。"""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute_write = AsyncMock(return_value=[{"result": True}])

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_client.get_async_driver = MagicMock(return_value=mock_driver)

        await storage.execute_write_query("CREATE (n)", {})
        mock_session.execute_write.assert_called_once()


class TestNeo4jGraphStorageGetNeighbors:
    """get_neighbors 方法测试。"""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=Neo4jClientWrapper)

    @pytest.fixture
    def storage(self, mock_client):
        return Neo4jGraphStorage(mock_client, database="neo4j")

    async def test_get_neighbors_returns_dict_list(self, storage, mock_client):
        """验证 get_neighbors 返回 dict 列表而非 neo4j.Node。"""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute_read = AsyncMock(return_value=[
            {"id": "n1", "labels": ["L1"], "properties": {"k": "v"}}
        ])

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_client.get_async_driver = MagicMock(return_value=mock_driver)

        result = await storage.get_neighbors("node-1", rel_type="REL", direction="OUT")

        assert isinstance(result, list)
        assert result[0]["id"] == "n1"  # 验证是 dict 而非 neo4j.Node
        assert "labels" in result[0]
```

#### Step 3.4: 运行所有测试

- [ ] **执行测试**:

```bash
poetry run pytest tests/unit/domain/ports/test_l5_graph_port.py -v
poetry run pytest tests/unit/infrastructure/storage/test_neo4j_adapter.py -v
poetry run pytest tests/unit/infrastructure/storage/test_neo4j_graph_storage.py -v
```

---

### Phase 4: 向后兼容验证

#### Step 4.1: 验证 UnifiedStorageGateway 导入正常

- [ ] **验证**:

```bash
poetry run python -c "from src.application.services.unified_storage_gateway import UnifiedStorageGateway; print('UnifiedStorageGateway 导入成功')"
```

#### Step 4.2: 运行集成测试

- [ ] **执行集成测试**:

```bash
poetry run pytest tests/integration/test_six_layer_complete_flow.py -v
```

#### Step 4.3: 清理备份文件

- [ ] **清理**:

```bash
rm src/domain/ports/l5_graph.py.bak
```

---

### Phase 5: 创建 MemoryGraphAdapter（P1-3）

#### Step 5.1: 创建 `src/infrastructure/storage/neo4j/base_graph_adapter.py`

- [ ] **创建基类**:

```python
# src/infrastructure/storage/neo4j/base_graph_adapter.py

"""BaseGraphAdapter — L5GraphPort 委托基类。

将所有 L5GraphPort 方法委托给内部存储，
子类只需实现领域方法，无需重复委托代码。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.ports.l5_graph import L5GraphPort

if TYPE_CHECKING:
    pass


class BaseGraphAdapter(L5GraphPort):
    """L5GraphPort 委托基类。

    将所有 L5GraphPort 方法委托给内部 _storage。
    子类继承此类后，只需实现领域特定方法。
    """

    def __init__(self, storage: L5GraphPort):
        """初始化适配器。

        Args:
            storage: L5GraphPort 实现（如 Neo4jGraphStorage）
        """
        self._storage = storage

    # 节点操作委托
    async def create_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> bool:
        return await self._storage.create_node(node_id, labels, properties)

    async def get_node(self, node_id: str) -> dict | None:
        return await self._storage.get_node(node_id)

    async def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        return await self._storage.update_node(node_id, properties)

    async def delete_node(self, node_id: str) -> bool:
        return await self._storage.delete_node(node_id)

    async def node_exists(self, node_id: str) -> bool:
        return await self._storage.node_exists(node_id)

    # 关系操作委托
    async def create_relationship(self, source_id: str, target_id: str, rel_type: str, properties: dict[str, Any] | None = None) -> bool:
        return await self._storage.create_relationship(source_id, target_id, rel_type, properties)

    async def delete_relationship(self, source_id: str, target_id: str, rel_type: str) -> bool:
        return await self._storage.delete_relationship(source_id, target_id, rel_type)

    async def get_relationships(self, node_id: str, rel_type: str | None = None, direction: str = "BOTH") -> list[dict]:
        return await self._storage.get_relationships(node_id, rel_type, direction)

    # 图遍历委托
    async def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> list[dict]:
        return await self._storage.find_path(start_id, end_id, max_depth)

    async def get_neighbors(self, node_id: str, rel_type: str | None = None, direction: str = "BOTH") -> list[dict]:
        return await self._storage.get_neighbors(node_id, rel_type, direction)

    async def find_related(self, node_id: str, max_depth: int = 2, rel_type: str | None = None) -> list[dict]:
        return await self._storage.find_related(node_id, max_depth, rel_type)

    # Cypher 委托
    async def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        return await self._storage.execute_query(cypher, params)

    async def execute_write_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        return await self._storage.execute_write_query(cypher, params)
```

#### Step 5.2: 创建 `src/infrastructure/storage/neo4j/memory_graph_adapter.py`

- [ ] **创建文件**:

```python
# src/infrastructure/storage/neo4j/memory_graph_adapter.py

"""MemoryGraphAdapter — MemoryGraphPort 实现（领域适配器）。

继承 BaseGraphAdapter，只需实现记忆领域逻辑。
L5GraphPort 委托由基类处理，无需重复代码。
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.memory_graph import MemoryGraphPort
from src.infrastructure.storage.neo4j.base_graph_adapter import BaseGraphAdapter


class MemoryGraphAdapter(MemoryGraphPort, BaseGraphAdapter):
    """记忆图谱领域适配器。

    继承 BaseGraphAdapter 处理所有 L5GraphPort 委托，
    只需实现 MemoryGraphPort 的领域方法。
    """

    def __init__(self, storage: L5GraphPort):
        """初始化适配器。

        Args:
            storage: L5GraphPort 实现（如 Neo4jGraphStorage）
        """
        super().__init__(storage)

    # ========================================================================
    # 记忆实体操作实现
    # ========================================================================

    async def create_memory_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建记忆实体节点。"""
        return await self._storage.create_node(
            node_id=memory_id,
            labels=["Memory", entity_type],
            properties={"memory_id": memory_id, **properties},
        )

    async def get_memory_entity(self, memory_id: str) -> dict | None:
        """获取记忆实体。"""
        node = await self._storage.get_node(memory_id)
        if node is None:
            return None
        labels = node.get("labels", [])
        entity_type = next((l for l in labels if l != "Memory"), "unknown")
        return {
            "memory_id": node.get("id"),
            "type": entity_type,
            "properties": node.get("properties", {}),
        }

    async def delete_memory_entity(self, memory_id: str) -> bool:
        """删除记忆实体。"""
        return await self._storage.delete_node(memory_id)

    async def memory_entity_exists(self, memory_id: str) -> bool:
        """检查记忆实体是否存在。"""
        return await self._storage.node_exists(memory_id)

    # ========================================================================
    # 记忆关系操作实现
    # ========================================================================

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """链接两个记忆。"""
        return await self._storage.create_relationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=relationship_type,
            properties=properties,
        )

    async def unlink_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
    ) -> bool:
        """取消链接两个记忆。"""
        return await self._storage.delete_relationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=relationship_type,
        )

    async def get_memory_links(
        self,
        memory_id: str,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """获取记忆的所有链接。"""
        rels = await self._storage.get_relationships(memory_id, relationship_type, "BOTH")
        return [
            {
                "source_id": r.get("source_id"),
                "target_id": r.get("target_id"),
                "type": r.get("type"),
                "properties": r.get("properties", {}),
            }
            for r in rels
        ]

    # ========================================================================
    # 记忆图遍历实现
    # ========================================================================

    async def find_related_memories(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联记忆。"""
        nodes = await self._storage.find_related(memory_id, max_depth, relationship_type)
        return [
            {
                "memory_id": n.get("id"),
                "type": next((l for l in n.get("labels", []) if l != "Memory"), "unknown"),
                "properties": n.get("properties", {}),
            }
            for n in nodes
        ]

    async def get_memory_neighbors(
        self,
        memory_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取记忆的邻居（单跳）。"""
        nodes = await self._storage.get_neighbors(memory_id, rel_type, direction)
        return [
            {
                "memory_id": n.get("id"),
                "type": next((l for l in n.get("labels", []) if l != "Memory"), "unknown"),
                "properties": n.get("properties", {}),
            }
            for n in nodes
        ]

    async def find_memory_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """查找两个记忆之间的路径。"""
        return await self._storage.find_path(start_id, end_id, max_depth)

    # ========================================================================
    # 批量操作实现
    # ========================================================================

    async def batch_create_memory_entities(self, entities: list[dict]) -> list[bool]:
        """批量创建记忆实体。"""
        results = []
        for entity in entities:
            result = await self.create_memory_entity(
                memory_id=entity["memory_id"],
                entity_type=entity["entity_type"],
                properties=entity.get("properties", {}),
            )
            results.append(result)
        return results

    async def batch_link_memories(self, links: list[dict]) -> list[bool]:
        """批量链接记忆。"""
        results = []
        for link in links:
            result = await self.link_memories(
                source_id=link["source_id"],
                target_id=link["target_id"],
                relationship_type=link["relationship_type"],
                properties=link.get("properties"),
            )
            results.append(result)
        return results
```

- [ ] **验证**: `poetry run python -c "from src.infrastructure.storage.neo4j.memory_graph_adapter import MemoryGraphAdapter; print('MemoryGraphAdapter 创建完成')"`

---

## 9. 验收标准

### 9.1 架构验收

| 检查项 | 标准 | 验证方式 |
|--------|------|----------|
| Domain 层零外部依赖 | L5GraphPort 不导入 Infrastructure | `poetry run pyright src/domain/ports/l5_graph.py` |
| L5GraphPort 无领域语义 | 不含 memory_id、entity_type 参数 | 代码审查 |
| MemoryGraphPort 继承 L5GraphPort | `issubclass(MemoryGraphPort, L5GraphPort)` | `poetry run pytest` |
| Infrastructure 实现 Port | Neo4jGraphStorage 实现 L5GraphPort | `poetry run pytest tests/unit/` |

### 9.2 功能验收

| 功能 | 验收标准 | 测试覆盖 |
|------|----------|----------|
| 节点 CRUD | create/get/update/delete/exists 正常工作 | test_neo4j_graph_storage.py |
| 关系 CRUD | create/delete/get_relationships 正常工作 | test_neo4j_graph_storage.py |
| 图遍历 | find_path/get_neighbors/find_related 正常工作 | test_neo4j_graph_storage.py |
| 记忆实体 | create_memory_entity/get_memory_entity 正常工作 | test_memory_graph_adapter.py |
| 记忆链接 | link_memories/unlink_memories 正常工作 | test_memory_graph_adapter.py |

### 9.3 向后兼容验收

| 组件 | 验收标准 |
|------|----------|
| Neo4jAdapter | 现有测试 `test_neo4j_adapter.py` 全部通过 |
| UnifiedStorageGateway | 导入正常，不报 AttributeError |
| 集成测试 | `test_six_layer_complete_flow.py` 通过 |

---

## 10. 风险与缓解

### 10.1 风险识别

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| L5GraphPort 接口变更破坏现有测试 | 高 | Phase 1 不破坏现有代码，Phase 3 更新测试 |
| MemoryGraphPort 尚未被使用 | 低 | Phase 4 验证，Phase 5 可选实现 |
| Neo4jGraphStorage 与现有 Neo4jAdapter 职责重叠 | 中 | Neo4jAdapter 重构为委托 Neo4jGraphStorage，保持兼容 |

### 10.2 回滚计划

如 Phase 2-4 出现问题：

```bash
# 回滚 Domain 层
git checkout src/domain/ports/l5_graph.py

# 回滚 Infrastructure 层
git checkout src/infrastructure/storage/neo4j/neo4j_adapter.py
```

---

## 11. 未来扩展

### 11.1 其他领域端口

```python
# src/domain/ports/agent_graph.py

class AgentGraphPort(L5GraphPort):
    """Agent 关系图谱端口。

    用于 Agent 之间的依赖关系、协作关系建模。
    """

    async def create_agent_entity(self, agent_id: str, agent_type: str, properties: dict) -> bool
    async def link_agents(self, source_id: str, target_id: str, relationship_type: str) -> bool
    async def find_collaborators(self, agent_id: str, max_depth: int = 2) -> list[dict]
```

### 11.2 其他技术实现

```python
# src/infrastructure/storage/tigergraph/ (未来)
# src/infrastructure/storage/amazon_neptune/ (未来)

# 只需实现 L5GraphPort 接口，即可替换 Neo4jGraphStorage
```

---

**文档状态**: 等待实施
**下一步**: Phase 1 执行（Domain 层重构）
