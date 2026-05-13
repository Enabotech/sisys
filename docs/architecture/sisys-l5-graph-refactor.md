# SISYS L5 图存储重构详细设计

**版本:** v2.0
**日期:** 2026-05-13
**作者:** Claude Code (宗师级架构设计)
**状态:** 设计完成（v2.0 修复版）
**基于:** sisys-uni-storage-design.md §L5 重构决策

---

## 0. 现状与目标状态

### 0.1 文档说明

**重要**: 本文档描述**目标架构**，而非当前代码状态。设计文档与实际代码存在差异，这是正常的重构流程。

### 0.2 当前代码状态（Baseline）

| 组件 | 位置 | 接口 | 状态 |
|------|------|------|------|
| `L5GraphPort` | `src/domain/ports/l5_graph.py` | `create_entity/memory_id` 风格 | 旧接口，含领域语义 |
| `Neo4jAdapter` | `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 实现旧 L5GraphPort | 待重构 |
| `Neo4jGraphStorage` | `src/infrastructure/storage/neo4j/graph_storage.py` | 部分实现 | 缺多数方法 |
| `Neo4jClientWrapper` | `src/infrastructure/storage/neo4j/client.py` | 连接封装 | 已有 |
| `MemoryGraphPort` | `src/domain/ports/memory_graph.py` | ❌ 不存在 | 待创建 |
| `Neo4jConnectionProvider` | `src/infrastructure/storage/neo4j/connection_provider.py` | ❌ 不存在 | 待创建 |
| `MemoryGraphAdapter` | `src/infrastructure/storage/neo4j/memory_graph_adapter.py` | ❌ 不存在 | 待创建 |

### 0.3 目标架构（Target）

| 组件 | Layer | 职责 |
|------|-------|------|
| `L5GraphPort` | L1 Domain | 纯技术图操作抽象 |
| `MemoryGraphPort` | L2 Application | 记忆图谱领域语义 |
| `Neo4jConnectionProvider` | L3 Infrastructure | 连接池单例管理 |
| `Neo4jGraphStorage` | L3 Infrastructure | 完整实现 L5GraphPort |
| `MemoryGraphAdapter` | L4 Infrastructure | 实现 MemoryGraphPort |

### 0.4 迁移策略

```
Phase 1: 创建目标接口（不破坏现有代码）
Phase 2: 实现基础设施（Neo4jGraphStorage + ConnectionProvider）
Phase 3: 实现领域适配器（MemoryGraphAdapter）
Phase 4: 重构 Neo4jAdapter 委托
Phase 5: 更新调用方，废弃旧接口
```

---

## 1. 设计背景与目标

### 1.1 问题陈述

当前 `L5GraphPort` 存在**职责混合**问题：Domain 层端口混合了技术接口与领域语义。

| 问题 | 描述 | 违反原则 |
|------|------|----------|
| P1 | `L5GraphPort` 在 Domain 层定义，但包含 `create_entity(memory_id)` 等记忆领域语义 | 领域层应只定义技术抽象，不含领域知识 |
| P2 | `Neo4jAdapter` 硬编码记忆领域逻辑（Cypher 中的 `Memory` 标签、MERGE 语义） | 适配器应只做接口转换，不含领域逻辑 |
| P3 | 未来扩展（如 `AgentGraph`、`DocumentGraph`）无法复用现有设计 | 违反 DRY 原则 |

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
│  端口：MemoryGraphPort                                           │
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
    async def get_neighbors(self, node_id: str, max_depth: int = 1, edge_type: str | None = None) -> list[dict]: ...
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
    async def get_memory_neighbors(self, memory_id: str, max_depth: int = 1, edge_type: str | None = None) -> list[dict]: ...
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
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取节点的直接邻居（单跳）。

        语义：只返回通过一条边直接相连的邻居节点。
        如需多跳遍历，使用 find_related 方法。

        与 find_related 的区别：
        - get_neighbors: 单跳直接邻居（1-N 关系）
        - find_related: 多跳可达节点（1-N-N... 关系）

        Args:
            node_id: 节点 ID
            edge_type: 过滤边类型，None 表示所有类型

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
| `get_neighbors(memory_id, max_depth, edge_type)` | `get_neighbors(node_id, max_depth, edge_type)` | 移除 memory_id 语义 |
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
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取记忆的直接邻居（单跳）。

        对应 L5GraphPort.get_neighbors，专用于记忆图谱。

        Args:
            memory_id: 记忆 ID
            edge_type: 过滤边类型，None 表示所有

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
        """获取节点的关系。"""
        if rel_type:
            rel_type_clause = f":{rel_type}"
        else:
            rel_type_clause = ""

        if direction == "OUT":
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_clause}->(target)
            RETURN startNode(r) as source, endNode(r) as target, type(r) as type, properties(r) as properties
            """
        elif direction == "IN":
            cypher = f"""
            MATCH (n {{id: $node_id}})<{rel_type_clause}-(source)
            RETURN startNode(r) as source, endNode(r) as target, type(r) as type, properties(r) as properties
            """
        else:
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_clause}-(other)
            RETURN n as source, other as target, type(r) as type, properties(r) as properties
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
        max_depth: int = 1,
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取邻居节点。"""
        if edge_type:
            edge_clause = f":{edge_type}"
        else:
            edge_clause = ""

        cypher = f"""
        MATCH (n {{id: $node_id}}){edge_clause}-(neighbor)
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
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取邻居（委托）。"""
        return await self._storage.get_neighbors(node_id, edge_type)

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
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取记忆的邻居（单跳）。"""
        nodes = await self._storage.get_neighbors(memory_id, edge_type)
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
        max_depth: int = 1,
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取邻居。"""
        return await self._storage.get_neighbors(node_id, max_depth, edge_type)

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

## 8. 执行步骤

### Phase 1: Domain 层重构（不破坏现有代码）

**Step 1.1**: 创建 `src/domain/ports/memory_graph.py`

```bash
touch src/domain/ports/memory_graph.py
# 实现 MemoryGraphPort（见 §4.2）
```

**Step 1.2**: 重构 `src/domain/ports/l5_graph.py`

```bash
# 备份旧文件
cp src/domain/ports/l5_graph.py src/domain/ports/l5_graph.py.bak

# 重写为纯技术接口（见 §3.2）
```

**Step 1.3**: 更新 `src/domain/ports/__init__.py`

```python
# 添加 MemoryGraphPort 导出
from src.domain.ports.memory_graph import MemoryGraphPort
__all__ = [..., "MemoryGraphPort"]
```

**Step 1.4**: 验证编译通过

```bash
poetry run python -c "from src.domain.ports import L5GraphPort, MemoryGraphPort"
```

### Phase 1.5: 创建连接池Provider（Layer 3）

**目标：** 创建Neo4j连接池单例，与L1缓存架构的RedisPoolProvider对称

**Step 1.5.1**: 创建 `src/infrastructure/storage/neo4j/connection_provider.py`

```bash
# 实现 Neo4jConnectionProvider（见 §5.0）
```

**Step 1.5.2**: 验证Provider单例

```bash
poetry run python -c "
from src.infrastructure.storage.neo4j.connection_provider import Neo4jConnectionProvider
p1 = Neo4jConnectionProvider()
p2 = Neo4jConnectionProvider()
assert p1 is p2, 'Provider应该是单例'
print('Phase 1.5: SUCCESS')
"
```

### Phase 2: Infrastructure 层实现

**Step 2.1**: 创建 `src/infrastructure/storage/neo4j/neo4j_graph_storage.py`

```bash
touch src/infrastructure/storage/neo4j/neo4j_graph_storage.py
# 实现 Neo4jGraphStorage（见 §5.1）
```

**Step 2.2**: 创建 `src/infrastructure/storage/neo4j/memory_graph_adapter.py`

```bash
touch src/infrastructure/storage/neo4j/memory_graph_adapter.py
# 实现 MemoryGraphAdapter（见 §5.2）
```

**Step 2.3**: 重构 `src/infrastructure/storage/neo4j/neo4j_adapter.py`

```bash
# 重构为委托 Neo4jGraphStorage（见 §5.3）
```

**Step 2.4**: 更新 `src/infrastructure/storage/neo4j/__init__.py`

```python
from src.infrastructure.storage.neo4j.neo4j_graph_storage import Neo4jGraphStorage
from src.infrastructure.storage.neo4j.memory_graph_adapter import MemoryGraphAdapter
__all__ = ["Neo4jAdapter", "Neo4jGraphStorage", "MemoryGraphAdapter"]
```

**Step 2.5**: 验证编译通过

```bash
poetry run python -c "from src.infrastructure.storage.neo4j import Neo4jAdapter, Neo4jGraphStorage, MemoryGraphAdapter"
```

### Phase 3: 测试更新

**Step 3.1**: 更新 `tests/unit/domain/ports/test_l5_graph_port.py`

```bash
# 更新方法名列表（create_entity → create_node 等）
```

**Step 3.2**: 创建 `tests/unit/infrastructure/storage/test_neo4j_graph_storage.py`

```bash
touch tests/unit/infrastructure/storage/test_neo4j_graph_storage.py
# 实现 Neo4jGraphStorage 单元测试
```

**Step 3.3**: 创建 `tests/unit/infrastructure/storage/test_memory_graph_adapter.py`

```bash
touch tests/unit/infrastructure/storage/test_memory_graph_adapter.py
# 实现 MemoryGraphAdapter 单元测试
```

**Step 3.4**: 运行所有测试

```bash
poetry run pytest tests/unit/domain/ports/test_l5_graph_port.py -v
poetry run pytest tests/unit/infrastructure/storage/test_neo4j_adapter.py -v
poetry run pytest tests/unit/infrastructure/storage/test_neo4j_graph_storage.py -v
poetry run pytest tests/unit/infrastructure/storage/test_memory_graph_adapter.py -v
```

### Phase 4: 向后兼容验证

**Step 4.1**: 验证 UnifiedStorageGateway 导入正常

```bash
poetry run python -c "from src.application.services.unified_storage_gateway import UnifiedStorageGateway"
```

**Step 4.2**: 运行集成测试

```bash
poetry run pytest tests/integration/test_six_layer_complete_flow.py -v
```

**Step 4.3**: 清理备份文件

```bash
rm src/domain/ports/l5_graph.py.bak
```

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
