# SISYS L5 图存储重构详细设计

**版本:** v4.0
**日期:** 2026-05-14
**作者:** Claude Code
**状态:** 设计完成（精简版，架构+接口+伪码）
**基于:** sisys-uni-storage-design.md §L5 重构决策

**设计原则：**
1. Domain层零外部依赖（L5GraphPort仅用Protocol+typing）
2. Infrastructure层薄适配器模式（委托而非拼接Cypher）
3. Application层领域语义封装（MemoryGraphPort继承技术接口）

**已发现问题汇总**（经5轮审查）：

| 类别 | 数量 | 关键问题 |
|------|------|---------|
| **P0-已修复** | 8 | get_neighbors缺失、Memory硬编码8处、竞态条件、非薄适配器、接口映射不完整、数据模型不一致、mock返回值错误、返回原生对象 |
| **P0-未修复** | 5 | conftest.py参数不匹配、MemoryChangedHandler TODO存根、get_neighbors Cypher缺[]、MemoryGraphPort缺导入、文件清单遗漏 |
| **P1-架构** | 4 | §3-§5与§8代码不一致、双轨制策略消失、edge_type/rel_type命名不一致、文件路径混淆 |
| **P1-兼容** | 2 | get_async_driver async改造影响12处、Neo4jConfig缺字段 |

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

**文件**: `src/domain/ports/l5_graph.py`
**基类**: `Protocol`（结构化子类型）
**方法总数**: 13

#### 节点操作

| 方法 | 输入 | 输出 | 语义 |
|------|------|------|------|
| `create_node` | `node_id: str, labels: list[str], properties: dict` | `bool` | MERGE 语义，已存在返回 True |
| `get_node` | `node_id: str` | `dict \| None` | 返回 `{id, labels, properties}` |
| `update_node` | `node_id: str, properties: dict` | `bool` | 增量更新属性 |
| `delete_node` | `node_id: str` | `bool` | DETACH DELETE，同时删除关联边 |
| `node_exists` | `node_id: str` | `bool` | 存在性检查 |

#### 关系操作

| 方法 | 输入 | 输出 | 语义 |
|------|------|------|------|
| `create_relationship` | `source_id: str, target_id: str, rel_type: str, properties: dict \| None = None` | `bool` | MERGE 语义 |
| `delete_relationship` | `source_id: str, target_id: str, rel_type: str` | `bool` | 删除指定关系 |
| `get_relationships` | `node_id: str, rel_type: str \| None = None, direction: str = "BOTH"` | `list[dict]` | 返回 `[{source_id, target_id, type, properties}]`，direction 支持 OUT/IN/BOTH |

#### 图遍历

| 方法 | 输入 | 输出 | 语义 |
|------|------|------|------|
| `find_path` | `start_id: str, end_id: str, max_depth: int = 3` | `list[dict]` | 两节点间所有路径 `[{nodes, relationships, length}]` |
| `get_neighbors` | `node_id: str, rel_type: str \| None = None, direction: str = "BOTH"` | `list[dict]` | 单跳直接邻居 `[{id, labels, properties}]` |
| `find_related` | `node_id: str, max_depth: int = 2, edge_type: str \| None = None` | `list[dict]` | 多跳可达节点 `[{id, labels, properties, path}]` |

> **注意**: `get_neighbors` 仅返回单跳邻居；`find_related` 支持多跳遍历。

#### 低级 Cypher

| 方法 | 输入 | 输出 | 语义 |
|------|------|------|------|
| `execute_query` | `cypher: str, params: dict \| None = None` | `list[dict]` | 只读查询，供领域适配器使用 |
| `execute_write_query` | `cypher: str, params: dict \| None = None` | `list[dict]` | 写入查询，必须使用事务函数 |

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

**文件**: `src/domain/ports/memory_graph.py`（新增）
**基类**: `L5GraphPort, Protocol`
**定位**: Application 层领域语义端口，继承 L5GraphPort 的全部 13 个技术方法，新增记忆领域专用方法

#### 记忆实体操作

| 方法 | 输入 | 输出 | 委托目标 |
|------|------|------|---------|
| `create_memory_entity` | `memory_id, entity_type, properties` | `bool` | `create_node(memory_id, ["Memory", entity_type], {memory_id, **properties})` |
| `get_memory_entity` | `memory_id` | `dict \| None` | `get_node(memory_id)` → 转换为 `{memory_id, type, properties}` |
| `delete_memory_entity` | `memory_id` | `bool` | `delete_node(memory_id)` |
| `memory_entity_exists` | `memory_id` | `bool` | `node_exists(memory_id)` |

#### 记忆关系操作

| 方法 | 输入 | 输出 | 委托目标 |
|------|------|------|---------|
| `link_memories` | `source_id, target_id, relationship_type, properties?` | `bool` | `create_relationship(source_id, target_id, relationship_type, properties)` |
| `unlink_memories` | `source_id, target_id, relationship_type` | `bool` | `delete_relationship(source_id, target_id, relationship_type)` |
| `get_memory_links` | `memory_id, relationship_type?` | `list[dict]` | `get_relationships(memory_id, relationship_type, "BOTH")` → 转换为 `[{source_id, target_id, type, properties}]` |

#### 记忆图遍历

| 方法 | 输入 | 输出 | 委托目标 |
|------|------|------|---------|
| `find_related_memories` | `memory_id, max_depth=2, relationship_type?` | `list[dict]` | `find_related(memory_id, max_depth, edge_type)` → 转换为 `[{memory_id, type, properties, path}]` |
| `get_memory_neighbors` | `memory_id, rel_type?, direction="BOTH"` | `list[dict]` | `get_neighbors(memory_id, rel_type, direction)` → 转换为 `[{memory_id, type, properties}]` |
| `find_memory_path` | `start_id, end_id, max_depth=3` | `list[dict]` | `find_path(start_id, end_id, max_depth)` |

#### 批量操作（可选）

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `batch_create_memory_entities` | `entities: list[dict]` | `list[bool]` | 循环调用 `create_memory_entity` |
| `batch_link_memories` | `links: list[dict]` | `list[bool]` | 循环调用 `link_memories` |

---

## 5. Infrastructure 层实现

### 5.0 Neo4jConnectionProvider（连接池单例）

**职责**: 管理 Neo4j 连接池单例，与 RedisPoolProvider 对称设计

**关键实现策略**:
```
1. 单例模式: 类变量 + __new__ 确保全局唯一实例
2. 线程安全: asyncio.Lock 保护并发初始化
3. 懒初始化: get_client() 首次调用时创建 driver
4. 健康检查: 验证连接可用性 + 池状态
5. 优雅关闭: close() 清理 driver 资源
```

**初始化流程**:
```
init(config) → 创建 Neo4jClientWrapper(uri, username, password, database)
             → 存储到 _client_wrapper 类变量
             → 后续调用 get_client() 直接返回
```

### 5.1 Neo4jGraphStorage（技术适配器）

**职责**: 实现 L5GraphPort 的全部 13 个方法，执行具体 Cypher 操作

**关键实现策略**:

| 功能 | Cypher 模式 | 说明 |
|------|------------|------|
| `create_node` | `MERGE (n {id: $node_id}) SET n:Labels, n += $props` | MERGE 语义 + 动态标签拼接 |
| `get_node` | `MATCH (n {id: $node_id}) RETURN n.id, labels(n), properties(n)` | 结果序列化为 dict |
| `delete_node` | `MATCH (n {id: $node_id}) DETACH DELETE n` | 同时删除关联边 |
| `create_relationship` | `MATCH (s), (t) MERGE (s)-[r:TYPE]->(t)` | rel_type 需白名单校验 |
| `get_neighbors` | `MATCH (n)-[r:TYPE?]->(neighbor)` | OUT/IN/BOTH 方向分支处理 |
| `find_related` | `MATCH path = (start)-[*1..depth]-(end)` | 变长路径遍历 |
| `execute_write_query` | `session.execute_write(tx_fn)` | 必须使用事务函数（非 session.run） |

**事务处理**:
```
execute_write_query(cypher, params):
  async def _tx(tx):
    result = await tx.run(cypher, **params)
    return await result.data()
  session.execute_write(_tx)  # 确保写入路由到 leader
```

**结果序列化**: 所有方法返回 `dict` 或 `list[dict]`，而非 Neo4j 原生 `Node`/`Path` 对象

### 5.2 MemoryGraphAdapter（领域适配器）

**职责**: 实现 MemoryGraphPort，委托给 Neo4jGraphStorage，添加领域语义转换

**委托模式**:
```
create_memory_entity(memory_id, entity_type, properties):
  → storage.create_node(memory_id, ["Memory", entity_type], {memory_id, **properties})

get_memory_entity(memory_id):
  → node = storage.get_node(memory_id)
  → 转换: {memory_id: node.id, type: 从labels提取, properties: node.properties}
```

**标签映射策略**: `Memory` + `entity_type` 双标签，从 Neo4j 返回时提取非 `Memory` 标签作为 `type`

### 5.3 Neo4jAdapter（向后兼容适配器）

**职责**: 薄适配器，纯委托给 Neo4jGraphStorage，消除硬编码 Memory 标签

**委托关系表**:

| Neo4jAdapter 方法 | 委托目标 | 说明 |
|-------------------|---------|------|
| `create_entity(memory_id, entity_type, props)` | `storage.create_node(memory_id, ["Memory", entity_type], props)` | 转换为通用接口 |
| `get_entity(memory_id)` | `storage.get_node(memory_id)` | 直接委托 |
| `find_related(memory_id, depth, type)` | `storage.find_related(memory_id, depth, type)` | 直接委托 |
| `execute_query` | `storage.execute_query` | 直接委托 |
| `execute_write_query` | `storage.execute_write_query` | 直接委托 |

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

### 7.2 测试用例清单

**test_l5_graph_port.py**（Protocol 契约测试）:
- 验证全部 13 个方法为 `async`
- Mock `spec=L5GraphPort` 约束

**test_neo4j_graph_storage.py**（新增，技术实现测试）:
- `create_node`: MERGE 语义 + 动态标签
- `get_node` / `update_node` / `delete_node` / `node_exists`: 节点 CRUD
- `create_relationship` / `delete_relationship` / `get_relationships`: 关系 CRUD
- `find_path` / `get_neighbors` / `find_related`: 图遍历
- `execute_write_query`: 验证使用 `session.execute_write()` 而非 `session.run()`

**test_neo4j_adapter.py**（修改，向后兼容测试）:
- 新增 `get_neighbors` 测试（当前缺失）
- 修正 mock 返回值（`create_entity` 返回 `bool` 而非 `dict`）

**test_memory_graph_adapter.py**（新增，领域适配器测试）:
- `create_memory_entity`: 验证使用 `memory_id` 作为 `node_id`，标签为 `["Memory", entity_type]`
- `get_memory_entity`: 验证标签解析（提取非 `Memory` 标签作为 `type`）
- `link_memories` / `unlink_memories`: 验证委托到 `create_relationship` / `delete_relationship`

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

### Phase 1: Domain 层重构 + P0 问题修复

- [ ] **Step 1.1**: 修复 `Neo4jClientWrapper` 线程安全
  - **问题**: `get_async_driver()` 懒初始化无锁保护
  - **修复**: 添加 `asyncio.Lock` + 双检锁模式，改为 `async def get_async_driver()`
  - **影响**: 需级联修改 `graph_storage.py` / `graph_manager.py` / `graph_retriever.py` 的 `_get_driver()` 为 async

- [ ] **Step 1.2**: 创建 `MemoryGraphPort`
  - **文件**: `src/domain/ports/memory_graph.py`
  - **内容**: 继承 `L5GraphPort, Protocol`，添加记忆领域方法（见 §4.2）

- [ ] **Step 1.3**: 重构 `L5GraphPort`
  - **文件**: `src/domain/ports/l5_graph.py`
  - **内容**: 替换为纯技术接口（见 §3.2），保持 `Protocol` 基类

### Phase 2: Infrastructure 层实现 + P0 问题修复

- [ ] **Step 2.1**: 修复 `execute_write_query` 事务问题
  - **文件**: `src/infrastructure/storage/neo4j/graph_storage.py`
  - **问题**: 使用 `session.run()` 无事务保护
  - **修复**: 改用 `session.execute_write(tx_fn)` 确保写入路由到 leader

- [ ] **Step 2.2**: 完善 `Neo4jGraphStorage` 实现
  - **文件**: `src/infrastructure/storage/neo4j/graph_storage.py`
  - **内容**: 新增 13 个 L5GraphPort 方法的 Cypher 实现（见 §5.1 表格）
  - **注意**: rel_type 参数需白名单校验，labels 需格式校验

- [ ] **Step 2.3**: 重构 `Neo4jAdapter` 为薄适配器
  - **文件**: `src/infrastructure/storage/neo4j/neo4j_adapter.py`
  - **内容**: 移除内联 Cypher，纯委托给 Neo4jGraphStorage（见 §5.3 委托表）

- [ ] **Step 2.4**: 创建 `Neo4jConnectionProvider` 单例
  - **文件**: `src/infrastructure/storage/neo4j/connection_provider.py`
  - **内容**: asyncio.Lock 保护 + 单例模式（见 §5.0）

### Phase 3: 测试更新

- [ ] **Step 3.1**: 修正 `test_l5_graph_port.py`
  - **修复**: mock 返回值与接口一致（`create_entity` 返回 `True` 而非 dict）

- [ ] **Step 3.2**: 更新 `test_neo4j_adapter.py`
  - **新增**: `get_neighbors` 测试用例

- [ ] **Step 3.3**: 创建 `test_neo4j_graph_storage.py`
  - **内容**: 节点 CRUD + 关系 CRUD + 图遍历测试

### Phase 4: 向后兼容验证

- [ ] **Step 4.1**: 运行全量单元测试
- [ ] **Step 4.2**: 运行集成测试（需真实 Neo4j）
- [ ] **Step 4.3**: 验证 `UnifiedStorageGateway._l5` 未受影响

### Phase 5: 创建领域适配器

- [ ] **Step 5.1**: 创建 `BaseGraphAdapter`
  - **文件**: `src/infrastructure/storage/neo4j/base_graph_adapter.py`
  - **内容**: 实现 L5GraphPort 所有方法的委托基类

- [ ] **Step 5.2**: 创建 `MemoryGraphAdapter`
  - **文件**: `src/infrastructure/storage/neo4j/memory_graph_adapter.py`
  - **内容**: 继承 `MemoryGraphPort, BaseGraphAdapter`，实现领域方法

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
