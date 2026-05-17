# SISYS 统一存储架构详细设计

**版本:** v3.0
**日期:** 2026-05-17
**状态:** 重构完成（四条规则合规）
**基于:** architecture.md §11 存储架构设计 + sisys-storage-refactor-design.md


### 1.2 设计目标

1. **六边形架构纯正**: 所有存储通过 Domain Port 接口解耦
2. **符合 architecture.md §11**: 严格遵循六层存储设计（L0-L5）
3. **统一入口**: 提供 `UnifiedStorageGateway` 统一编排各层
4. **可测试性**: 每个存储层通过 Port 接口可独立测试

### 1.3 与 architecture.md §11 对齐

| §11 章节 | 内容 | 本文档对应 |
|---------|------|-----------|
| 11.1 | 六层存储详细设计 | §3 各层 Port 接口设计 |
| 11.2.5 | L2 PostgreSQL 表设计 | 已有实现，无需变更 |
| 11.2.7 | 三层触发机制 | 已有实现，保持不变 |
| 11.2.11 | 验收标准 | §7 验收标准 |

---

## 2. 架构总览

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Application Layer                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    UnifiedStorageGateway                       │   │
│  │  职责: 统一存储入口，编排 L0-L5 各层存储                        │   │
│  │  依赖: Domain Port 接口（无 Infrastructure 直接依赖）          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │ 依赖 Port 接口
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Domain Layer                                │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐              │
│  │ L0StoragePort │ │ L1CachePort  │  │ L2RdbPort[T]  │
│  ├───────────────┤ ├───────────────┤ ├───────────────┤              │
│  │L3VectorPort   │ │L4ObjectPort   │ │L5GraphPort    │              │
│  └───────────────┘ └───────────────┘ └───────────────┘              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              StoragePolicyService (领域服务)                    │  │
│  │  职责: 根据数据特征决定存储层级(HOT/WARM/COLD/FROZEN)            │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │ 实现 Port 接口
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                           │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐              │
│  │ FileAdapter   │ │ RedisAdapter  │ │ PostgreSQL    │              │
│  │ (L0StoragePort)│ │ (L1CachePort) │ │ Adapter       │              │
│  ├───────────────┤ ├───────────────┤ │ (L2RdbPort[T])│              │
│  │QdrantAdapter  │ │ MinIOAdapter  │ ├───────────────┤              │
│  │ (L3VectorPort) │ │ (L4ObjectPort)│ │ Neo4jAdapter  │              │
│  └───────────────┘ └───────────────┘ │ (L5GraphPort) │              │
│                                      └───────────────┘              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                UnifiedStorageFactory                          │  │
│  │  职责: 根据配置创建各层 Adapter，组装 UnifiedStorageGateway     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 六层存储职责（来自 architecture.md §11.1）

| 层级 | 技术 | 内容 | Port 接口 | Rule 3 实现 | Rule 4 实现 |
|------|------|------|-----------|-------------|-------------|
| **L0** | 文件系统 | MEMORY.md 索引、记忆文件 | `L0StoragePort` | `FileAdapter` | — |
| **L1** | Redis 7.0+ | 通用 KV 缓存 | `L1CachePort` | `RedisAdapter` | `RedisMemoryCache(MemoryCachePort)`, `RedisSessionCache(SessionCachePort)` |
| **L2** | PostgreSQL 15+ | 用户/RBAC、记忆元数据 | `L2RdbPort[T]` | `PostgreSQLAdapter` | `PgMetadataRepo`, `UserRepo[User,UserModel]`, `PermissionRepo[Permission,PermissionModel]` |
| **L3** | Qdrant 1.7+ | 嵌入向量、混合检索 | `L3VectorPort` | `QdrantAdapter` | — |
| **L4** | MinIO WORM | 原始文档、证据包 | `L4ObjectPort` | `MinIOAdapter` | — |
| **L5** | Neo4j 5.x | 知识图谱、实体关系 | `L5GraphPort` | `Neo4jAdapter` | — |

---
