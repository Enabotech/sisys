# 附录 H：多租户隔离详细设计方案

**版本：** 1.0.0
**状态：** 架构评审补充文档
**评审日期：** 2026-02-25
**问题编号：** H5 - 多租户隔离设计深度不足

---

## 目录

1. [多租户架构概述](#1-多租户架构概述)
2. [租户识别与上下文传播](#2-租户识别与上下文传播)
3. [五层存储租户隔离设计](#3-五层存储租户隔离设计)
4. [应用层租户隔离](#4-应用层租户隔离)
5. [RBAC 与租户权限模型](#5-rbac-与租户权限模型)
6. [租户隔离渗透测试方案](#6-租户隔离渗透测试方案)
7. [监控与审计](#7-监控与审计)
8. [实现代码示例](#8-实现代码示例)
9. [验收标准](#9-验收标准)

---

## 1. 多租户架构概述

### 1.1 租户模型定义

**租户（Tenant）** 是本系统的核心隔离单元，代表一个独立的企业客户或组织。每个租户拥有完全隔离的数据、配置、用户和计算资源。

```python
class Tenant(BaseModel):
    """租户实体定义"""
    
    id: UUID                          # 租户唯一标识
    name: str                         # 租户名称
    slug: str                         # 租户短标识（用于域名/路径）
    status: TenantStatus              # 租户状态
    tier: TenantTier                  # 租户等级
    created_at: datetime              # 创建时间
    expires_at: Optional[datetime]    # 过期时间
    settings: TenantSettings          # 租户配置
    data_residency: DataResidency     # 数据驻留要求
    isolation_level: IsolationLevel   # 隔离等级
    max_users: int                    # 最大用户数
    max_storage_bytes: int            # 最大存储容量
    features: List[str]               # 启用的功能列表
```

**租户等级（TenantTier）：**
| 等级 | 名称 | 隔离方式 | 适用客户 | SLA |
|------|------|---------|---------|-----|
| **Basic** | 基础版 | 共享 Schema + Row-Level 隔离 | 中小企业 | 99% |
| **Professional** | 专业版 | Schema per Tenant | 大型企业 | 99.5% |
| **Enterprise** | 企业版 | Database per Tenant | 超大型企业 | 99.9% |
| **Government** | 政务版 | 独立部署 + 物理隔离 | 政府/军工 | 99.99% |

**数据驻留（DataResidency）：**
| 类型 | 描述 | 路由规则 |
|------|------|---------|
| **GLOBAL** | 全球通用 | 可路由至任意区域 |
| **CHINA_DOMESTIC** | 中国境内 | 仅限中国大陆区域 |
| **EU_GDPR** | 欧盟 GDPR | 仅限欧盟区域 |
| **US_ONLY** | 美国境内 | 仅限美国区域 |

### 1.2 隔离等级要求

| 隔离层级 | 隔离对象 | 隔离要求 | 违反后果 |
|---------|---------|---------|---------|
| **L1 网络隔离** | 租户间网络流量 | VPC/子网隔离、安全组 | 数据泄露 |
| **L2 计算隔离** | Agent 执行环境 | Docker/gVisor 沙箱 | 代码注入攻击 |
| **L3 数据隔离** | 五层存储数据 | Schema per Tenant | 数据污染 |
| **L4 缓存隔离** | Redis 缓存键 | 租户前缀隔离 | 缓存污染 |
| **L5 上下文隔离** | LLM Prompt/记忆 | 租户标识注入 | 提示注入 |

### 1.3 租户数据分布

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        多租户数据分布架构                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │   租户 A        │    │   租户 B        │    │   租户 C        │     │
│  │  (Professional) │    │  (Professional) │    │   (Enterprise)  │     │
│  │                 │    │                 │    │                 │     │
│  │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │     │
│  │ │ Schema: A   │ │    │ │ Schema: B   │ │    │ │ Database: C │ │     │
│  │ │ Redis: A:*  │ │    │ │ Redis: B:*  │ │    │ │ Redis: C:*  │ │     │
│  │ │ Qdrant: A   │ │    │ │ Qdrant: B   │ │    │ │ Qdrant: C   │ │     │
│  │ │ MinIO: A/   │ │    │ │ MinIO: B/   │ │    │ │ MinIO: C/   │ │     │
│  │ │ Neo4j: A    │ │    │ │ Neo4j: B    │ │    │ │ Neo4j: C    │ │     │
│  │ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│         │                       │                       │              │
│         └───────────────────────┼───────────────────────┘              │
│                                 │                                       │
│                    ┌────────────▼────────────┐                         │
│                    │    租户路由中间件        │                         │
│                    │  TenantRoutingMiddleware│                         │
│                    └─────────────────────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 租户识别与上下文传播

### 2.1 租户识别机制

**多源租户识别策略：**

| 识别源 | 优先级 | 提取方式 | 适用场景 |
|--------|--------|---------|---------|
| **JWT Token** | 1 | `tenant_id` claim | 认证后的 API 请求 |
| **子域名** | 2 | `tenant.example.com` → `tenant` | SaaS 多租户域名 |
| **请求头** | 3 | `X-Tenant-ID` | 内部服务调用 |
| **路径前缀** | 4 | `/api/v1/{tenant}/...` | 公开 API |
| **API Key** | 5 | 查表映射 | 第三方集成 |

```python
class TenantResolver:
    """租户解析器 - 多源识别"""
    
    def __init__(self):
        self.resolvers: List[TenantResolverStrategy] = [
            JWTTokenResolver(),      # 优先级 1
            SubdomainResolver(),     # 优先级 2
            HeaderResolver(),        # 优先级 3
            PathPrefixResolver(),    # 优先级 4
            APIKeyResolver(),        # 优先级 5
        ]
    
    async def resolve(self, request: Request) -> TenantContext:
        """按优先级解析租户"""
        for resolver in self.resolvers:
            if resolver.can_resolve(request):
                tenant = await resolver.resolve(request)
                if tenant:
                    # 验证租户状态
                    await self.validate_tenant(tenant)
                    return TenantContext(
                        tenant_id=tenant.id,
                        tenant_slug=tenant.slug,
                        tenant_tier=tenant.tier,
                        data_residency=tenant.data_residency,
                        isolation_level=tenant.isolation_level,
                        resolved_at=datetime.utcnow(),
                        resolver_type=type(resolver).__name__
                    )
        
        raise TenantNotFoundError("无法从请求中识别租户")
    
    async def validate_tenant(self, tenant: Tenant) -> None:
        """验证租户状态"""
        if tenant.status != TenantStatus.ACTIVE:
            raise TenantInactiveError(f"租户 {tenant.id} 未激活")
        
        if tenant.expires_at and tenant.expires_at < datetime.utcnow():
            raise TenantExpiredError(f"租户 {tenant.id} 已过期")
```

### 2.2 上下文传播链路

**租户上下文传播链：**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      租户上下文传播链路                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 客户端请求                                                           │
│     │                                                                   │
│     ▼                                                                   │
│  2. API Gateway (Kong/Traefik)                                          │
│     │  └─ 提取 JWT → 验证 → 注入 X-Tenant-ID                            │
│     ▼                                                                   │
│  3. FastAPI 中间件                                                       │
│     │  └─ TenantRoutingMiddleware → TenantContext                       │
│     ▼                                                                   │
│  4. 应用层服务                                                           │
│     │  └─ 依赖注入 → tenant_context: TenantContext                      │
│     ▼                                                                   │
│  5. 领域层服务                                                           │
│     │  └─ 方法参数传递 → tenant_id: UUID                                │
│     ▼                                                                   │
│  6. 基础设施层仓储                                                       │
│     │  └─ 自动注入租户过滤条件 → WHERE tenant_id = ?                    │
│     ▼                                                                   │
│  7. 五层存储                                                             │
│        ├─ PostgreSQL: SET search_path TO tenant_{id}                    │
│        ├─ Redis: KEY = "tenant:{id}:..."                                │
│        ├─ Qdrant: collection = "tenant_{id}_documents"                  │
│        ├─ MinIO: bucket = "tenant-{id}"                                 │
│        └─ Neo4j: MATCH (n:Tenant {id: $id})                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 租户解析器实现

```python
class JWTTokenResolver(TenantResolverStrategy):
    """JWT Token 租户解析器"""
    
    async def resolve(self, request: Request) -> Optional[Tenant]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]
        try:
            # 验证 JWT 并提取 claims
            claims = await self.jwt_verifier.verify(token)
            tenant_id = claims.get("tenant_id")
            
            if not tenant_id:
                return None
            
            # 从缓存或数据库获取租户信息
            return await self.tenant_cache.get(tenant_id)
            
        except JWTValidationError:
            return None


class SubdomainResolver(TenantResolverStrategy):
    """子域名租户解析器"""
    
    async def resolve(self, request: Request) -> Optional[Tenant]:
        host = request.headers.get("Host", "")
        parts = host.split(".")
        
        # 提取子域名：tenant.example.com → tenant
        if len(parts) >= 3:
            subdomain = parts[0]
            if subdomain != "www" and subdomain != "api":
                return await self.tenant_repo.get_by_slug(subdomain)
        
        return None


class HeaderResolver(TenantResolverStrategy):
    """请求头租户解析器"""
    
    async def resolve(self, request: Request) -> Optional[Tenant]:
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            try:
                tenant_uuid = UUID(tenant_id)
                return await self.tenant_cache.get(tenant_uuid)
            except ValueError:
                pass
        return None
```

---

## 3. 五层存储租户隔离设计

### 3.1 L1 缓存层租户隔离（Redis）

**隔离策略：** 键名前缀隔离 + 逻辑分区

```python
class TenantRedisCache:
    """租户 Redis 缓存 - 键名前缀隔离"""
    
    def __init__(self, redis_client: Redis, tenant_context: TenantContext):
        self.redis = redis_client
        self.tenant = tenant_context
        # 租户键名前缀：tenant:{id}:
        self.key_prefix = f"tenant:{tenant_context.tenant_id}:"
    
    def _make_key(self, key: str) -> str:
        """生成租户隔离的键名"""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        full_key = self._make_key(key)
        data = await self.redis.get(full_key)
        return self._deserialize(data) if data else None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        full_key = self._make_key(key)
        serialized = self._serialize(value)
        
        if ttl:
            await self.redis.setex(full_key, ttl, serialized)
        else:
            await self.redis.set(full_key, serialized)
    
    async def delete(self, key: str) -> None:
        """删除缓存"""
        full_key = self._make_key(key)
        await self.redis.delete(full_key)
    
    async def clear_all(self) -> None:
        """清空租户所有缓存"""
        pattern = self._make_key("*")
        async for key in self.redis.scan_iter(pattern):
            await self.redis.delete(key)
    
    # 语义缓存专用方法
    async def semantic_search(
        self,
        query_embedding: List[float],
        threshold: float = 0.9
    ) -> Optional[SemanticCacheResult]:
        """语义缓存搜索 - 租户隔离"""
        # 使用 Redis Stack 向量搜索
        query = f"@tenant_id:{self.tenant.tenant_id}=>[KNN 1 @embedding $vec AS score]"
        results = await self.redis.ft("semantic_cache").search(
            query,
            query_params={"vec": np.array(query_embedding, dtype=np.float32).tobytes()},
            return_fields=["score", "value", "created_at"]
        )
        
        if results.docs and float(results.docs[0].score) >= threshold:
            return SemanticCacheResult(
                value=results.docs[0].value,
                similarity=1 - float(results.docs[0].score),
                hit=True
            )
        
        return None
```

**Redis 键名规范：**
| 键类型 | 格式 | 示例 | TTL |
|--------|------|------|-----|
| 会话状态 | `tenant:{id}:session:{session_id}` | `tenant:abc123:session:xyz789` | 24h |
| 语义缓存 | `tenant:{id}:semantic:{hash}` | `tenant:abc123:semantic:a1b2c3` | 24h |
| Agent 状态 | `tenant:{id}:agent:{agent_id}:state` | `tenant:abc123:agent:ceo:state` | 1h |
| 公共黑板 | `tenant:{id}:blackboard:{session_id}` | `tenant:abc123:blackboard:session1` | 30d |
| 路由缓存 | `tenant:{id}:route:{task_hash}` | `tenant:abc123:route:task123` | 7d |

### 3.2 L2 关系存储层租户隔离（PostgreSQL Schema per Tenant）

**隔离策略：** Schema per Tenant（专业版及以上）

```sql
-- 租户 Schema 创建脚本
CREATE OR REPLACE FUNCTION create_tenant_schema(tenant_uuid UUID)
RETURNS VOID AS $$
DECLARE
    schema_name TEXT;
BEGIN
    -- 生成 Schema 名称
    schema_name := 'tenant_' || replace(tenant_uuid::text, '-', '_');
    
    -- 创建 Schema
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', schema_name);
    
    -- 设置 Schema 权限
    EXECUTE format('GRANT ALL ON SCHEMA %I TO app_user', schema_name);
    
    -- 创建租户专属表（复制公共表结构）
    EXECUTE format('CREATE TABLE %I.documents (LIKE public.documents INCLUDING ALL)', schema_name);
    EXECUTE format('CREATE TABLE %I.agents (LIKE public.agents INCLUDING ALL)', schema_name);
    EXECUTE format('CREATE TABLE %I.strategic_plans (LIKE public.strategic_plans INCLUDING ALL)', schema_name);
    EXECUTE format('CREATE TABLE %I.routing_decision_log (LIKE public.routing_decision_log INCLUDING ALL)', schema_name);
    EXECUTE format('CREATE TABLE %I.isolation_switch_log (LIKE public.isolation_switch_log INCLUDING ALL)', schema_name);
    
    -- 创建租户专属索引
    EXECUTE format('CREATE INDEX idx_%I_documents_created ON %I.documents(created_at)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX idx_%I_plans_status ON %I.strategic_plans(status)', schema_name, schema_name);
    
    -- 记录 Schema 创建日志
    INSERT INTO public.tenant_schemas (tenant_id, schema_name, created_at)
    VALUES (tenant_uuid, schema_name, NOW());
END;
$$ LANGUAGE plpgsql;
```

**租户仓储实现：**
```python
class TenantAwareRepository:
    """租户感知仓储基类"""
    
    def __init__(
        self,
        db_session: AsyncSession,
        tenant_context: TenantContext
    ):
        self.db = db_session
        self.tenant = tenant_context
        self.schema_prefix = f"tenant_{tenant_context.tenant_id.hex}"
    
    async def _get_schema(self) -> str:
        """获取当前租户 Schema"""
        # Professional/Enterprise: Schema per Tenant
        if self.tenant.tier in [TenantTier.PROFESSIONAL, TenantTier.ENTERPRISE]:
            return self.schema_prefix
        # Basic: 共享 Schema + Row-Level 过滤
        return "public"
    
    async def _apply_tenant_filter(self, query: Select) -> Select:
        """应用租户过滤"""
        schema = await self._get_schema()
        
        if schema != "public":
            # Schema per Tenant: 设置 search_path
            await self.db.execute(text(f"SET search_path TO {schema}"))
        else:
            # Row-Level 过滤
            query = query.where(Document.tenant_id == self.tenant.tenant_id)
        
        return query
    
    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """获取文档 - 自动租户过滤"""
        query = select(Document).where(Document.id == document_id)
        query = await self._apply_tenant_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def find_documents(self, limit: int = 100) -> List[Document]:
        """查找文档 - 自动租户过滤"""
        query = select(Document).limit(limit)
        query = await self._apply_tenant_filter(query)
        result = await self.db.execute(query)
        return result.scalars().all()
```

**数据库连接配置：**
```python
class TenantDatabaseConnection:
    """租户数据库连接管理"""
    
    async def get_connection(self, tenant: TenantContext) -> AsyncSession:
        """获取租户数据库连接"""
        
        if tenant.tier == TenantTier.ENTERPRISE:
            # Enterprise: 独立数据库
            db_url = f"postgresql://{tenant.id}/sisys"
        else:
            # Professional/Basic: 共享数据库
            db_url = settings.database_url
        
        # 创建引擎
        engine = create_async_engine(
            db_url,
            pool_size=20,
            max_overflow=40
        )
        
        # 创建会话
        async_session = sessionmaker(engine, class_=AsyncSession)
        session = async_session()
        
        # 设置 Schema
        if tenant.tier in [TenantTier.PROFESSIONAL, TenantTier.ENTERPRISE]:
            schema_name = f"tenant_{tenant.tenant_id.hex}"
            await session.execute(text(f"SET search_path TO {schema_name}"))
        
        return session
```

### 3.3 L3 向量存储层租户隔离（Qdrant）

**隔离策略：** Collection per Tenant

```python
class TenantQdrantClient:
    """租户 Qdrant 客户端 - Collection 隔离"""
    
    def __init__(self, qdrant_client: AsyncQdrantClient, tenant_context: TenantContext):
        self.client = qdrant_client
        self.tenant = tenant_context
        # 租户 Collection 前缀
        self.collection_prefix = f"tenant_{tenant_context.tenant_id.hex}"
    
    def _get_collection_name(self, collection_type: str) -> str:
        """获取租户 Collection 名称"""
        return f"{self.collection_prefix}_{collection_type}"
    
    async def initialize(self) -> None:
        """初始化租户 Collection"""
        collections = ["documents", "agents", "tools", "plans"]
        
        for coll_type in collections:
            coll_name = self._get_collection_name(coll_type)
            
            # 检查 Collection 是否存在
            exists = await self.client.collection_exists(coll_name)
            
            if not exists:
                # 创建租户 Collection
                await self.client.create_collection(
                    collection_name=coll_name,
                    vectors_config=VectorParams(
                        size=1024,  # BGE-M3 维度
                        distance=Distance.COSINE
                    ),
                    # 启用 Payload 索引
                    optimizers_config=OptimizerConfig(
                        indexing_threshold=20000
                    ),
                    # 租户元数据
                    metadata={
                        "tenant_id": str(self.tenant.tenant_id),
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                
                # 创建 Payload 索引
                await self.client.create_payload_index(
                    collection_name=coll_name,
                    field_name="tenant_id",
                    field_schema=PayloadSchemaType.KEYWORD
                )
                
                await self.client.create_payload_index(
                    collection_name=coll_name,
                    field_name="created_at",
                    field_schema=PayloadSchemaType.INTEGER
                )
    
    async def search(
        self,
        collection_type: str,
        query_vector: List[float],
        limit: int = 10,
        filter_payload: Optional[Dict] = None
    ) -> List[ScoredPoint]:
        """向量搜索 - 租户隔离"""
        coll_name = self._get_collection_name(collection_type)
        
        # 构建过滤条件（双重保障）
        must_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(self.tenant.tenant_id))
            )
        ]
        
        if filter_payload:
            for key, value in filter_payload.items():
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
        
        results = await self.client.search(
            collection_name=coll_name,
            query_vector=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=limit
        )
        
        return results
    
    async def upsert(
        self,
        collection_type: str,
        points: List[PointStruct]
    ) -> None:
        """插入向量 - 自动注入租户 ID"""
        coll_name = self._get_collection_name(collection_type)
        
        # 为每个点注入租户 ID
        for point in points:
            point.payload["tenant_id"] = str(self.tenant.tenant_id)
            point.payload["tenant_slug"] = self.tenant.tenant_slug
        
        await self.client.upsert(
            collection_name=coll_name,
            points=points
        )
    
    async def delete_collection(self) -> None:
        """删除租户所有 Collection"""
        collections = ["documents", "agents", "tools", "plans"]
        
        for coll_type in collections:
            coll_name = self._get_collection_name(coll_type)
            await self.client.delete_collection(coll_name)
```

### 3.4 L4 对象存储层租户隔离（MinIO）

**隔离策略：** Bucket per Tenant

```python
class TenantMinIOClient:
    """租户 MinIO 客户端 - Bucket 隔离"""
    
    def __init__(self, minio_client: Minio, tenant_context: TenantContext):
        self.client = minio_client
        self.tenant = tenant_context
        # 租户 Bucket 名称
        self.bucket_name = f"tenant-{tenant_context.tenant_id.hex}"
    
    async def initialize(self) -> None:
        """初始化租户 Bucket"""
        # 检查 Bucket 是否存在
        exists = await self.client.bucket_exists(self.bucket_name)
        
        if not exists:
            # 创建租户 Bucket
            await self.client.make_bucket(
                self.bucket_name,
                # 启用对象锁定（WORM）
                object_lock=True
            )
            
            # 设置 Bucket 策略（租户隔离）
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": ["s3:*"],
                        "Resource": [
                            f"arn:aws:s3:::{self.bucket_name}/*",
                            f"arn:aws:s3:::{self.bucket_name}"
                        ],
                        "Condition": {
                            "StringNotLike": {
                                "s3:prefix": f"{self.tenant.tenant_id}/*"
                            }
                        }
                    }
                ]
            }
            
            await self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            
            # 启用版本控制
            await self.client.enable_versioning(self.bucket_name)
            
            # 设置对象锁定默认保留规则（7 年）
            await self.client.set_object_lock_config(
                self.bucket_name,
                ObjectLockConfig(
                    object_lock_enabled=True,
                    rule=Rule(
                        default_retention=DefaultRetention(
                            mode=GOVERNANCE,
                            days=2555  # 7 年
                        )
                    )
                )
            )
    
    async def upload_document(
        self,
        object_name: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        retention_days: int = 2555
    ) -> str:
        """上传文档 - WORM 保护"""
        # 生成对象路径：tenant_id/year/month/day/object_name
        today = datetime.utcnow()
        object_path = f"{self.tenant.tenant_id}/{today.year}/{today.month:02d}/{today.day:02d}/{object_name}"
        
        # 上传文件
        await self.client.fput_object(
            bucket_name=self.bucket_name,
            object_name=object_path,
            file_path=file_path,
            content_type=content_type
        )
        
        # 设置对象锁定（WORM）
        await self.client.put_object_retention(
            bucket_name=self.bucket_name,
            object_name=object_path,
            retention=Retention(
                mode=COMPLIANCE,  # COMPLIANCE 模式：连管理员也不能修改
                retain_until_date=datetime.utcnow() + timedelta(days=retention_days)
            )
        )
        
        return object_path
    
    async def get_document(self, object_path: str) -> bytes:
        """获取文档"""
        response = await self.client.get_object(
            bucket_name=self.bucket_name,
            object_name=object_path
        )
        return await response.read()
    
    async def delete_bucket(self) -> None:
        """删除租户 Bucket（仅限未启用 WORM 的对象）"""
        # 列出所有对象
        objects = await self.client.list_objects(self.bucket_name, recursive=True)
        
        # 删除非 WORM 对象
        async for obj in objects:
            if obj.retention_mode is None:
                await self.client.remove_object(self.bucket_name, obj.object_name)
        
        # 删除 Bucket
        await self.client.remove_bucket(self.bucket_name)
```

**MinIO 路径规范：**
| 对象类型 | 路径格式 | 示例 | 保留期 |
|---------|---------|------|--------|
| 原始文档 | `{tenant_id}/docs/{year}/{month}/{day}/{doc_id}.{ext}` | `abc123/docs/2026/02/25/doc123.pdf` | 7 年 |
| 证据包 | `{tenant_id}/evidence/{plan_id}/{checkpoint_id}.zip` | `abc123/evidence/plan456/ckpt789.zip` | 7 年 |
| 审计报告 | `{tenant_id}/audit/{year}/{report_id}.pdf` | `abc123/audit/2026/report123.pdf` | 7 年 |
| 备份快照 | `{tenant_id}/backups/{timestamp}.tar.gz` | `abc123/backups/20260225103000.tar.gz` | 30 天 |

### 3.5 L5 图存储层租户隔离（Neo4j）

**隔离策略：** Tenant Label + 关系隔离

```python
class TenantNeo4jClient:
    """租户 Neo4j 客户端 - Label 隔离"""
    
    def __init__(self, neo4j_driver: AsyncDriver, tenant_context: TenantContext):
        self.driver = neo4j_driver
        self.tenant = tenant_context
    
    async def create_entity(self, entity_type: str, properties: Dict[str, Any]) -> Node:
        """创建实体 - 自动注入租户 Label"""
        async with self.driver.session() as session:
            # 租户专属 Label
            tenant_label = f"Tenant_{self.tenant.tenant_id.hex}"
            
            # Cypher 查询：创建带租户 Label 的节点
            query = f"""
            CREATE (n:`{entity_type}`:`{tenant_label}` $properties)
            SET n.created_at = datetime(),
                n.tenant_id = $tenant_id,
                n.tenant_slug = $tenant_slug
            RETURN n
            """
            
            result = await session.run(
                query,
                properties=properties,
                tenant_id=str(self.tenant.tenant_id),
                tenant_slug=self.tenant.tenant_slug
            )
            
            record = await result.single()
            return record["n"] if record else None
    
    async def find_entities(
        self,
        entity_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Node]:
        """查找实体 - 自动租户过滤"""
        async with self.driver.session() as session:
            tenant_label = f"Tenant_{self.tenant.tenant_id.hex}"
            
            # 构建过滤条件
            where_clauses = []
            params = {"tenant_id": str(self.tenant.tenant_id), "limit": limit}
            
            if filters:
                for key, value in filters.items():
                    where_clauses.append(f"n.{key} = ${key}")
                    params[key] = value
            
            where_clause = " AND ".join(where_clauses)
            if where_clause:
                where_clause = f"AND {where_clause}"
            
            query = f"""
            MATCH (n:`{entity_type}`:`{tenant_label}`)
            WHERE n.tenant_id = $tenant_id {where_clause}
            RETURN n
            LIMIT $limit
            """
            
            result = await session.run(query, **params)
            return [record["n"] async for record in result]
    
    async def create_relationship(
        self,
        start_node_id: str,
        end_node_id: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Relationship:
        """创建关系 - 租户内关系"""
        async with self.driver.session() as session:
            tenant_label = f"Tenant_{self.tenant.tenant_id.hex}"
            
            query = f"""
            MATCH (a:`{tenant_label}` {{id: $start_id}})
            MATCH (b:`{tenant_label}` {{id: $end_id}})
            CREATE (a)-[r:`{rel_type}` $properties]->(b)
            SET r.created_at = datetime(),
                r.tenant_id = $tenant_id
            RETURN r
            """
            
            result = await session.run(
                query,
                start_id=start_node_id,
                end_id=end_node_id,
                properties=properties or {},
                tenant_id=str(self.tenant.tenant_id)
            )
            
            record = await result.single()
            return record["r"] if record else None
    
    async def traverse_graph(
        self,
        start_node_id: str,
        max_depth: int = 3,
        rel_types: Optional[List[str]] = None
    ) -> List[Path]:
        """图遍历 - 租户内遍历"""
        async with self.driver.session() as session:
            tenant_label = f"Tenant_{self.tenant.tenant_id.hex}"
            
            # 关系类型过滤
            rel_filter = ""
            if rel_types:
                rel_types_str = "|".join([f"`{t}`" for t in rel_types])
                rel_filter = f"-[:{rel_types_str}*..{max_depth}]-"
            else:
                rel_filter = f"-[*..{max_depth}]-"
            
            query = f"""
            MATCH path = (start:`{tenant_label}` {{id: $start_id}}){rel_filter}(end:`{tenant_label}`)
            WHERE start.tenant_id = $tenant_id AND end.tenant_id = $tenant_id
            RETURN path
            LIMIT 1000
            """
            
            result = await session.run(
                query,
                start_id=start_node_id,
                tenant_id=str(self.tenant.tenant_id)
            )
            
            return [record["path"] async for record in result]
    
    async def cleanup_tenant_data(self) -> None:
        """清理租户所有图数据"""
        async with self.driver.session() as session:
            tenant_label = f"Tenant_{self.tenant.tenant_id.hex}"
            
            # 删除所有租户节点（级联删除关系）
            query = f"""
            MATCH (n:`{tenant_label}`)
            WHERE n.tenant_id = $tenant_id
            DETACH DELETE n
            """
            
            await session.run(query, tenant_id=str(self.tenant.tenant_id))
```

---

## 4. 应用层租户隔离

### 4.1 租户上下文强制校验

**FastAPI 依赖注入：**
```python
from fastapi import Depends, HTTPException, status

class TenantDependency:
    """租户依赖注入"""
    
    def __init__(self):
        self.resolver = TenantResolver()
        self.context_manager = TenantContextManager()
    
    async def __call__(
        self,
        request: Request,
        authorization: str = Header(..., description="JWT Token")
    ) -> TenantContext:
        """解析并验证租户上下文"""
        try:
            # 解析租户
            context = await self.resolver.resolve(request)
            
            # 将租户上下文注入请求状态
            request.state.tenant_context = context
            
            # 将租户上下文注入上下文管理器（用于异步任务）
            await self.context_manager.set_current(context)
            
            return context
            
        except TenantNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="租户未找到"
            )
        except TenantInactiveError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="租户未激活"
            )
        except TenantExpiredError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="租户已过期"
            )

# 全局依赖
get_tenant = TenantDependency()

# 在路由中使用
@app.get("/api/v1/documents")
async def list_documents(
    tenant: TenantContext = Depends(get_tenant),
    limit: int = Query(100, ge=1, le=1000)
):
    """列出文档 - 自动租户隔离"""
    # 仓储层自动应用租户过滤
    documents = await document_repo.find_documents(limit=limit)
    return {"data": documents}
```

### 4.2 服务间租户传递

**内部服务调用租户传递：**
```python
class TenantPropagationMiddleware(BaseHTTPMiddleware):
    """租户传播中间件 - 服务间调用"""
    
    async def dispatch(self, request: Request, call_next):
        # 从请求头获取租户上下文
        tenant_id = request.headers.get("X-Tenant-ID")
        tenant_tier = request.headers.get("X-Tenant-Tier")
        data_residency = request.headers.get("X-Data-Residency")
        
        # 如果是内部服务调用，验证并传播租户上下文
        if tenant_id and self._is_internal_request(request):
            # 验证内部调用签名
            signature = request.headers.get("X-Internal-Signature")
            if not self._verify_internal_signature(tenant_id, signature):
                raise HTTPException(status_code=401, detail="内部调用签名无效")
            
            # 将租户上下文注入到下游调用
            request.state.tenant_context = TenantContext(
                tenant_id=UUID(tenant_id),
                tenant_tier=TenantTier(tenant_tier) if tenant_tier else TenantTier.BASIC,
                data_residency=DataResidency(data_residency) if data_residency else DataResidency.GLOBAL
            )
        
        response = await call_next(request)
        
        # 在响应头中返回租户信息（用于调试）
        if hasattr(request.state, "tenant_context"):
            response.headers["X-Tenant-ID"] = str(request.state.tenant_context.tenant_id)
        
        return response
    
    def _is_internal_request(self, request: Request) -> bool:
        """检查是否为内部请求"""
        internal_ips = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        client_ip = request.client.host
        return any(ipaddress.ip_address(client_ip) in ipaddress.ip_network(cidr) for cidr in internal_ips)
    
    def _verify_internal_signature(self, tenant_id: str, signature: str) -> bool:
        """验证内部调用签名"""
        expected = hmac.new(
            settings.internal_api_secret.encode(),
            tenant_id.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)


class TenantAwareHTTPClient:
    """租户感知 HTTP 客户端 - 自动传播租户上下文"""
    
    def __init__(self, http_client: httpx.AsyncClient, tenant_context: TenantContext):
        self.client = http_client
        self.tenant = tenant_context
    
    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """发送请求 - 自动注入租户头"""
        # 确保 headers 存在
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        
        # 注入租户上下文
        kwargs["headers"]["X-Tenant-ID"] = str(self.tenant.tenant_id)
        kwargs["headers"]["X-Tenant-Tier"] = self.tenant.tenant_tier.value
        kwargs["headers"]["X-Data-Residency"] = self.tenant.data_residency.value
        
        # 添加内部调用签名
        signature = hmac.new(
            settings.internal_api_secret.encode(),
            str(self.tenant.tenant_id).encode(),
            hashlib.sha256
        ).hexdigest()
        kwargs["headers"]["X-Internal-Signature"] = signature
        
        return await self.client.request(method, url, **kwargs)
```

### 4.3 跨租户访问防护

**跨租户访问控制：**
```python
class CrossTenantAccessGuard:
    """跨租户访问防护器"""
    
    def __init__(self):
        self.access_log: List[CrossTenantAccessLog] = []
    
    async def check_access(
        self,
        source_tenant: TenantContext,
        target_tenant_id: UUID,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> AccessDecision:
        """检查跨租户访问权限"""
        
        # 1. 同一租户：允许
        if source_tenant.tenant_id == target_tenant_id:
            return AccessDecision(allowed=True, reason="同一租户")
        
        # 2. 检查是否有跨租户共享配置
        sharing_config = await self._get_sharing_config(target_tenant_id, resource_id)
        
        if sharing_config:
            # 检查共享范围
            if sharing_config.shared_with_all:
                return AccessDecision(allowed=True, reason="资源已公开共享")
            
            if source_tenant.tenant_id in sharing_config.shared_with_tenants:
                return AccessDecision(allowed=True, reason="资源已共享给本租户")
        
        # 3. 检查是否有跨租户协作关系
        collaboration = await self._get_collaboration(source_tenant.tenant_id, target_tenant_id)
        
        if collaboration and collaboration.is_active:
            if resource_type in collaboration.allowed_resources:
                return AccessDecision(allowed=True, reason="协作关系允许访问")
        
        # 4. 记录拒绝访问日志（用于审计和异常检测）
        await self._log_denied_access(
            source_tenant=source_tenant,
            target_tenant_id=target_tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            timestamp=datetime.utcnow()
        )
        
        return AccessDecision(
            allowed=False,
            reason="跨租户访问未授权",
            should_alert=True  # 触发安全告警
        )
    
    async def _log_denied_access(self, **kwargs) -> None:
        """记录拒绝访问日志"""
        log_entry = CrossTenantAccessLog(**kwargs)
        self.access_log.append(log_entry)
        
        # 持久化到数据库
        await self.access_log_repo.save(log_entry)
        
        # 检查是否为异常模式（同一源租户频繁尝试访问其他租户）
        await self._check_anomaly_pattern(kwargs["source_tenant"])
```

---

## 5. RBAC 与租户权限模型

### 5.1 租户 - 角色 - 权限三维模型

```python
class TenantRolePermission(BaseModel):
    """租户 - 角色 - 权限三维模型"""
    
    id: UUID
    tenant_id: UUID                    # 租户维度
    role_id: UUID                      # 角色维度
    permission_id: UUID                # 权限维度
    resource_scope: Optional[str]      # 资源范围（可选）
    created_at: datetime
    created_by: UUID
    
    class Config:
        # 唯一约束：同一租户下角色和权限的组合唯一
        unique_together = ["tenant_id", "role_id", "permission_id"]


class TenantRole(BaseModel):
    """租户角色"""
    
    id: UUID
    tenant_id: UUID                    # 租户隔离
    name: str                          # 角色名称
    code: str                          # 角色代码
    description: Optional[str]
    is_system_role: bool               # 是否系统预置角色
    permissions: List[Permission] = [] # 权限列表
    users: List[User] = []             # 角色用户
    created_at: datetime


class Permission(BaseModel):
    """权限定义"""
    
    id: UUID
    code: str                          # 权限代码
    name: str                          # 权限名称
    resource_type: str                 # 资源类型
    actions: List[str]                 # 允许的操作
    description: Optional[str]
    
    # 权限代码格式：{resource_type}:{action}
    # 示例：documents:read, documents:write, plans:approve
```

**预置角色定义：**
| 角色代码 | 角色名称 | 权限范围 | 适用场景 |
|---------|---------|---------|---------|
| **tenant_admin** | 租户管理员 | 租户内所有资源 | 企业管理员 |
| **strategy_director** | 战略总监 | 战略规划全流程 | 战略部门负责人 |
| **analyst** | 分析师 | 文档/工具/分析 | 业务分析师 |
| **viewer** | 只读用户 | 只读访问 | 高管查看 |
| **auditor** | 审计员 | 审计日志/合规报告 | 内外部审计 |

### 5.2 租户内权限隔离

```python
class TenantPermissionService:
    """租户权限服务"""
    
    async def check_permission(
        self,
        tenant_context: TenantContext,
        user_id: UUID,
        resource_type: str,
        action: str,
        resource_id: Optional[str] = None
    ) -> PermissionCheckResult:
        """检查用户权限"""
        
        # 1. 获取用户角色
        user_roles = await self.user_role_repo.find_by_user(
            tenant_id=tenant_context.tenant_id,
            user_id=user_id
        )
        
        if not user_roles:
            return PermissionCheckResult(
                allowed=False,
                reason="用户未分配角色"
            )
        
        # 2. 检查角色权限
        for role in user_roles:
            permissions = await self.role_permission_repo.find_by_role(
                tenant_id=tenant_context.tenant_id,
                role_id=role.id
            )
            
            for permission in permissions:
                if (permission.resource_type == resource_type and
                    action in permission.actions):
                    
                    # 3. 检查资源范围（如果有）
                    if resource_id and permission.resource_scope:
                        if not self._match_resource_scope(resource_id, permission.resource_scope):
                            continue
                    
                    return PermissionCheckResult(
                        allowed=True,
                        role=role.name,
                        permission=permission.code
                    )
        
        return PermissionCheckResult(
            allowed=False,
            reason="权限不足"
        )
    
    def _match_resource_scope(self, resource_id: str, scope: str) -> bool:
        """检查资源范围匹配"""
        # 支持通配符：plans:* 或 plans:2026-*
        pattern = scope.replace("*", ".*")
        return bool(re.match(f"^{pattern}$", resource_id))
```

### 5.3 跨租户访问控制

```python
class CrossTenantPermissionService:
    """跨租户权限服务"""
    
    async def grant_cross_tenant_access(
        self,
        source_tenant_id: UUID,
        target_tenant_id: UUID,
        resource_type: str,
        resource_id: str,
        actions: List[str],
        expires_at: Optional[datetime] = None
    ) -> CrossTenantGrant:
        """授予跨租户访问权限"""
        
        # 1. 验证源租户权限（必须是租户管理员）
        caller = await self.get_current_caller()
        if not await self._is_tenant_admin(caller, source_tenant_id):
            raise PermissionDeniedError("只有租户管理员可以授予跨租户访问权限")
        
        # 2. 创建跨租户授权
        grant = CrossTenantGrant(
            id=uuid4(),
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            actions=actions,
            expires_at=expires_at,
            created_by=caller.id,
            created_at=datetime.utcnow()
        )
        
        await self.cross_tenant_grant_repo.save(grant)
        
        # 3. 记录审计日志
        await self.audit_logger.log(
            event_type="cross_tenant_access_granted",
            tenant_id=source_tenant_id,
            user_id=caller.id,
            details={
                "target_tenant_id": str(target_tenant_id),
                "resource_type": resource_type,
                "resource_id": resource_id,
                "actions": actions,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )
        
        return grant
    
    async def revoke_cross_tenant_access(
        self,
        grant_id: UUID,
        reason: str
    ) -> None:
        """撤销跨租户访问权限"""
        
        grant = await self.cross_tenant_grant_repo.get(grant_id)
        if not grant:
            raise NotFoundError(f"跨租户授权 {grant_id} 未找到")
        
        # 验证权限
        caller = await self.get_current_caller()
        if not await self._is_tenant_admin(caller, grant.source_tenant_id):
            raise PermissionDeniedError("只有租户管理员可以撤销跨租户访问权限")
        
        # 撤销授权
        await self.cross_tenant_grant_repo.delete(grant_id)
        
        # 记录审计日志
        await self.audit_logger.log(
            event_type="cross_tenant_access_revoked",
            tenant_id=grant.source_tenant_id,
            user_id=caller.id,
            details={
                "grant_id": str(grant_id),
                "reason": reason
            }
        )
```

---

## 6. 租户隔离渗透测试方案

### 6.1 渗透测试场景（20+ 场景）

| 编号 | 场景名称 | 测试方法 | 预期结果 | 优先级 |
|------|---------|---------|---------|--------|
| **PT-01** | JWT Token 租户 ID 篡改 | 修改 JWT 中的 tenant_id claim | 拒绝访问 | P0 |
| **PT-02** | 子域名租户枚举 | 遍历子域名尝试访问 | 仅返回 404 | P0 |
| **PT-03** | 请求头租户 ID 注入 | 伪造 X-Tenant-ID 头 | 拒绝访问 | P0 |
| **PT-04** | SQL 注入跨租户数据 | 在查询参数中注入 SQL | 查询被限制在租户 Schema | P0 |
| **PT-05** | Redis 键名遍历 | 尝试访问其他租户缓存键 | 键名隔离生效 | P0 |
| **PT-06** | Qdrant Collection 越界 | 尝试查询其他租户 Collection | Collection 不存在 | P0 |
| **PT-07** | MinIO Bucket 遍历 | 尝试列出其他租户 Bucket | 拒绝访问 | P0 |
| **PT-08** | Neo4j 图遍历越界 | 尝试遍历其他租户节点 | 节点不可见 | P0 |
| **PT-09** | 水平权限提升 | 使用租户 A 的 ID 访问租户 B 资源 | 拒绝访问 | P0 |
| **PT-10** | 垂直权限提升 | 普通用户尝试访问管理员功能 | 拒绝访问 | P0 |
| **PT-11** | 服务间调用租户劫持 | 伪造内部调用签名 | 签名验证失败 | P1 |
| **PT-12** | 事件消息租户污染 | 在事件消息中注入其他租户 ID | 事件被拒绝 | P1 |
| **PT-13** | 日志信息泄露 | 检查日志是否包含其他租户数据 | 无泄露 | P1 |
| **PT-14** | 错误信息泄露 | 触发错误检查响应 | 不泄露租户信息 | P1 |
| **PT-15** | API 速率限制绕过 | 使用多个租户 ID 绕过限流 | 限流仍然生效 | P1 |
| **PT-16** | 缓存投毒 | 尝试写入其他租户缓存 | 写入失败 | P1 |
| **PT-17** | 会话固定攻击 | 尝试固定其他租户会话 | 会话隔离 | P1 |
| **PT-18** | 文件上传路径遍历 | 上传文件时尝试写入其他租户目录 | 路径被限制 | P1 |
| **PT-19** | WebSocket 租户隔离 | 通过 WebSocket 尝试访问其他租户 | 连接被拒绝 | P2 |
| **PT-20** | GraphQL 租户注入 | 在 GraphQL 查询中注入租户 ID | 查询被限制 | P2 |
| **PT-21** | 批量操作租户隔离 | 批量操作中包含其他租户资源 | 仅处理本租户 | P2 |
| **PT-22** | 导出功能租户隔离 | 导出数据时尝试包含其他租户 | 仅导出本租户 | P2 |

### 6.2 自动化测试工具

```python
class TenantIsolationPenetrationTester:
    """租户隔离渗透测试器"""
    
    def __init__(self, base_url: str, test_tenants: List[TenantFixture]):
        self.base_url = base_url
        self.tenants = test_tenants
        self.results: List[TestResult] = []
    
    async def run_all_tests(self) -> PenetrationTestReport:
        """运行所有渗透测试"""
        test_methods = [
            self.test_jwt_tenant_tampering,
            self.test_subdomain_enumeration,
            self.test_header_tenant_injection,
            self.test_sql_injection_cross_tenant,
            self.test_redis_key_traversal,
            self.test_qdrant_collection_boundary,
            self.test_minio_bucket_traversal,
            self.test_neo4j_graph_boundary,
            self.test_horizontal_privilege_escalation,
            self.test_vertical_privilege_escalation,
        ]
        
        for test_method in test_methods:
            try:
                result = await test_method()
                self.results.append(result)
            except Exception as e:
                self.results.append(TestResult(
                    test_name=test_method.__name__,
                    passed=False,
                    error=str(e)
                ))
        
        return self._generate_report()
    
    async def test_jwt_tenant_tampering(self) -> TestResult:
        """PT-01: JWT Token 租户 ID 篡改测试"""
        # 获取租户 A 的有效 JWT
        tenant_a = self.tenants[0]
        tenant_b = self.tenants[1]
        
        valid_token = await self._get_jwt_for_tenant(tenant_a)
        
        # 篡改 tenant_id claim
        tampered_token = self._tamper_jwt_claim(valid_token, "tenant_id", str(tenant_b.tenant_id))
        
        # 尝试访问租户 B 的资源
        response = await self._make_request(
            url=f"{self.base_url}/api/v1/documents",
            token=tampered_token
        )
        
        # 预期：401 或 403
        passed = response.status_code in [401, 403]
        
        return TestResult(
            test_name="PT-01: JWT Token 租户 ID 篡改",
            passed=passed,
            details={
                "original_tenant": str(tenant_a.tenant_id),
                "tampered_tenant": str(tenant_b.tenant_id),
                "response_status": response.status_code,
                "response_body": response.text[:500]
            }
        )
    
    async def test_redis_key_traversal(self) -> TestResult:
        """PT-05: Redis 键名遍历测试"""
        tenant_a = self.tenants[0]
        tenant_b = self.tenants[1]
        
        # 在租户 A 的缓存中写入测试数据
        await self._set_cache_key(tenant_a, "test_key", "test_value")
        
        # 尝试使用租户 B 的上下文访问租户 A 的键
        try:
            # 直接尝试访问租户 A 的键名
            key = f"tenant:{tenant_a.tenant_id}:test_key"
            value = await self.redis_client.get(key)
            
            # 如果返回了值，说明隔离失败
            passed = value is None
            
        except Exception as e:
            # 抛出异常也是正确的行为
            passed = True
        
        return TestResult(
            test_name="PT-05: Redis 键名遍历",
            passed=passed,
            details={
                "attempted_access": f"tenant:{tenant_a.tenant_id}:test_key",
                "from_tenant": str(tenant_b.tenant_id)
            }
        )
    
    async def test_sql_injection_cross_tenant(self) -> TestResult:
        """PT-04: SQL 注入跨租户数据测试"""
        tenant_a = self.tenants[0]
        tenant_b = self.tenants[1]
        
        # 在租户 A 中创建测试文档
        doc_id = await self._create_document(tenant_a, "Test Document")
        
        # 使用租户 B 的上下文，尝试 SQL 注入访问租户 A 的文档
        malicious_query = f"{doc_id}' OR '1'='1"
        
        response = await self._make_request(
            url=f"{self.base_url}/api/v1/documents",
            params={"search": malicious_query},
            tenant=tenant_b
        )
        
        # 检查结果中是否包含租户 A 的文档
        documents = response.json().get("data", [])
        passed = not any(doc["id"] == str(doc_id) for doc in documents)
        
        return TestResult(
            test_name="PT-04: SQL 注入跨租户数据",
            passed=passed,
            details={
                "malicious_query": malicious_query,
                "documents_returned": len(documents)
            }
        )
    
    def _generate_report(self) -> PenetrationTestReport:
        """生成渗透测试报告"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        return PenetrationTestReport(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            pass_rate=passed_tests / total_tests if total_tests > 0 else 0,
            results=self.results,
            generated_at=datetime.utcnow(),
            recommendation="通过" if failed_tests == 0 else "需要修复"
        )
```

### 6.3 验收标准

| 指标 | 目标值 | 测量方式 | 验收条件 |
|------|--------|---------|---------|
| **渗透测试通过率** | 100% | 自动化测试 + 人工验证 | 所有 P0/P1 场景通过 |
| **跨租户访问拒绝率** | 100% | 渗透测试统计 | 所有越界访问被拒绝 |
| **隔离失效事件数** | 0 | 监控告警统计 | 生产环境零事件 |
| **审计日志完整性** | 100% | 日志审计 | 所有访问可追溯 |

---

## 7. 监控与审计

### 7.1 租户隔离监控指标

```python
class TenantIsolationMetrics:
    """租户隔离监控指标"""
    
    # Prometheus 指标定义
    
    # 跨租户访问尝试次数
    cross_tenant_access_attempts = Counter(
        "tenant_isolation_cross_tenant_attempts_total",
        "跨租户访问尝试次数",
        ["source_tenant_id", "target_tenant_id", "resource_type", "action"]
    )
    
    # 跨租户访问拒绝次数
    cross_tenant_access_denials = Counter(
        "tenant_isolation_cross_tenant_denials_total",
        "跨租户访问拒绝次数",
        ["source_tenant_id", "target_tenant_id", "resource_type", "reason"]
    )
    
    # 租户解析失败次数
    tenant_resolution_failures = Counter(
        "tenant_isolation_resolution_failures_total",
        "租户解析失败次数",
        ["resolver_type", "failure_reason"]
    )
    
    # 租户上下文传播延迟
    tenant_context_propagation_latency = Histogram(
        "tenant_isolation_context_propagation_latency_seconds",
        "租户上下文传播延迟",
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
    )
    
    # 各层存储隔离状态
    storage_isolation_status = Gauge(
        "tenant_isolation_storage_status",
        "存储隔离状态",
        ["tenant_id", "storage_layer", "status"]
    )
    
    # 租户配额使用率
    tenant_quota_usage = Gauge(
        "tenant_quota_usage_ratio",
        "租户配额使用率",
        ["tenant_id", "quota_type"]
    )
```

**Grafana 仪表板配置：**
```json
{
  "dashboard": {
    "title": "多租户隔离监控",
    "panels": [
      {
        "title": "跨租户访问尝试 vs 拒绝",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(tenant_isolation_cross_tenant_attempts_total[5m])",
            "legendFormat": "尝试次数"
          },
          {
            "expr": "rate(tenant_isolation_cross_tenant_denials_total[5m])",
            "legendFormat": "拒绝次数"
          }
        ]
      },
      {
        "title": "租户解析失败率",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(tenant_isolation_resolution_failures_total[5m])",
            "legendFormat": "失败率"
          }
        ]
      },
      {
        "title": "租户配额使用率 Top 10",
        "type": "bargauge",
        "targets": [
          {
            "expr": "topk(10, tenant_quota_usage_ratio{quota_type=\"storage\"})",
            "legendFormat": "{{tenant_id}}"
          }
        ]
      }
    ]
  }
}
```

### 7.2 跨租户访问审计日志

```python
class TenantIsolationAuditLogger:
    """租户隔离审计日志器"""
    
    async def log_cross_tenant_access_attempt(
        self,
        source_tenant_id: UUID,
        target_tenant_id: UUID,
        user_id: UUID,
        resource_type: str,
        resource_id: str,
        action: str,
        decision: AccessDecision,
        request_id: str
    ) -> None:
        """记录跨租户访问尝试"""
        
        log_entry = TenantIsolationAuditLog(
            id=uuid4(),
            timestamp=datetime.utcnow(),
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            allowed=decision.allowed,
            denial_reason=decision.reason if not decision.allowed else None,
            request_id=request_id,
            ip_address=await self._get_client_ip(),
            user_agent=await self._get_user_agent()
        )
        
        # 写入审计日志表（WORM 存储）
        await self.audit_log_repo.save(log_entry)
        
        # 如果拒绝且应告警，触发安全告警
        if not decision.allowed and decision.should_alert:
            await self._trigger_security_alert(log_entry)
    
    async def log_tenant_context_switch(
        self,
        user_id: UUID,
        from_tenant_id: UUID,
        to_tenant_id: UUID,
        reason: str
    ) -> None:
        """记录租户上下文切换"""
        
        log_entry = TenantContextSwitchLog(
            id=uuid4(),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            from_tenant_id=from_tenant_id,
            to_tenant_id=to_tenant_id,
            reason=reason
        )
        
        await self.audit_log_repo.save(log_entry)
    
    async def log_storage_isolation_violation(
        self,
        tenant_id: UUID,
        storage_layer: str,
        violation_type: str,
        details: Dict[str, Any]
    ) -> None:
        """记录存储隔离违规"""
        
        log_entry = StorageIsolationViolationLog(
            id=uuid4(),
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            storage_layer=storage_layer,
            violation_type=violation_type,
            details=details
        )
        
        await self.audit_log_repo.save(log_entry)
        
        # 立即触发告警
        await self._trigger_critical_alert(log_entry)
```

**审计日志表结构：**
```sql
CREATE TABLE tenant_isolation_audit_logs (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    source_tenant_id UUID NOT NULL,
    target_tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(500),
    action VARCHAR(50) NOT NULL,
    allowed BOOLEAN NOT NULL,
    denial_reason TEXT,
    request_id VARCHAR(100) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_tenant_audit_timestamp ON tenant_isolation_audit_logs(timestamp);
CREATE INDEX idx_tenant_audit_source_tenant ON tenant_isolation_audit_logs(source_tenant_id);
CREATE INDEX idx_tenant_audit_target_tenant ON tenant_isolation_audit_logs(target_tenant_id);
CREATE INDEX idx_tenant_audit_user ON tenant_isolation_audit_logs(user_id);

-- 分区表（按月分区）
CREATE TABLE tenant_isolation_audit_logs_2026_02 PARTITION OF tenant_isolation_audit_logs
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

### 7.3 异常检测与告警

```python
class TenantIsolationAnomalyDetector:
    """租户隔离异常检测器"""
    
    def __init__(self):
        self.alert_channels: List[AlertChannel] = [
            SlackAlertChannel(),
            EmailAlertChannel(),
            PagerDutyAlertChannel()
        ]
    
    async def detect_and_alert(self) -> None:
        """检测异常并告警"""
        
        # 1. 检测频繁跨租户访问尝试
        await self._detect_frequent_cross_tenant_attempts()
        
        # 2. 检测租户解析失败激增
        await self._detect_tenant_resolution_spike()
        
        # 3. 检测存储隔离违规
        await self._detect_storage_violations()
        
        # 4. 检测异常时间段访问
        await self._detect_abnormal_time_access()
    
    async def _detect_frequent_cross_tenant_attempts(self) -> None:
        """检测频繁跨租户访问尝试"""
        
        # 查询过去 5 分钟内跨租户访问尝试次数
        query = """
        SELECT source_tenant_id, target_tenant_id, COUNT(*) as attempt_count
        FROM tenant_isolation_audit_logs
        WHERE timestamp > NOW() - INTERVAL '5 minutes'
        AND allowed = FALSE
        GROUP BY source_tenant_id, target_tenant_id
        HAVING COUNT(*) > 10
        """
        
        results = await self.db.fetch_all(query)
        
        for row in results:
            alert = SecurityAlert(
                alert_type="FREQUENT_CROSS_TENANT_ATTEMPTS",
                severity=AlertSeverity.HIGH,
                title=f"频繁跨租户访问尝试",
                description=f"租户 {row.source_tenant_id} 在 5 分钟内尝试访问租户 {row.target_tenant_id} {row.attempt_count} 次",
                source_tenant_id=row.source_tenant_id,
                target_tenant_id=row.target_tenant_id,
                attempt_count=row.attempt_count,
                detected_at=datetime.utcnow()
            )
            
            await self._send_alert(alert)
    
    async def _detect_tenant_resolution_spike(self) -> None:
        """检测租户解析失败激增"""
        
        # 使用 CUSUM 算法检测失败率漂移
        current_rate = await self._get_current_resolution_failure_rate()
        baseline_rate = await self._get_baseline_resolution_failure_rate()
        
        if current_rate > baseline_rate * 3:  # 失败率超过基线 3 倍
            alert = SecurityAlert(
                alert_type="TENANT_RESOLUTION_FAILURE_SPIKE",
                severity=AlertSeverity.MEDIUM,
                title="租户解析失败率激增",
                description=f"当前失败率 {current_rate:.2f} 超过基线 {baseline_rate:.2f} 的 3 倍",
                detected_at=datetime.utcnow()
            )
            
            await self._send_alert(alert)
    
    async def _send_alert(self, alert: SecurityAlert) -> None:
        """发送告警"""
        
        for channel in self.alert_channels:
            try:
                await channel.send(alert)
            except Exception as e:
                # 记录告警发送失败
                await self.alert_failure_logger.log(alert, channel, e)
```

**告警规则配置（Prometheus AlertManager）：**
```yaml
groups:
  - name: tenant_isolation
    interval: 30s
    rules:
      - alert: HighCrossTenantAccessDenialRate
        expr: rate(tenant_isolation_cross_tenant_denials_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "跨租户访问拒绝率过高"
          description: "过去 5 分钟内跨租户访问拒绝率超过阈值"
      
      - alert: TenantResolutionFailureSpike
        expr: rate(tenant_isolation_resolution_failures_total[5m]) > 5
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "租户解析失败激增"
          description: "租户解析失败率异常升高"
      
      - alert: StorageIsolationViolation
        expr: tenant_isolation_storage_status{status="violation"} == 1
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "存储隔离违规"
          description: "检测到存储隔离违规事件"
```

---

## 8. 实现代码示例

### 8.1 租户上下文管理器

```python
from contextvars import ContextVar
from typing import Optional
from uuid import UUID

# 异步上下文变量
_tenant_context_var: ContextVar[Optional[TenantContext]] = ContextVar(
    "tenant_context",
    default=None
)


class TenantContextManager:
    """租户上下文管理器 - 支持异步任务"""
    
    async def set_current(self, context: TenantContext) -> None:
        """设置当前租户上下文"""
        _tenant_context_var.set(context)
    
    def get_current(self) -> Optional[TenantContext]:
        """获取当前租户上下文"""
        return _tenant_context_var.get()
    
    def get_current_tenant_id(self) -> Optional[UUID]:
        """获取当前租户 ID"""
        context = self.get_current()
        return context.tenant_id if context else None
    
    async def run_with_tenant(
        self,
        context: TenantContext,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """在指定租户上下文中运行函数"""
        token = _tenant_context_var.set(context)
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        finally:
            _tenant_context_var.reset(token)


# 依赖注入辅助函数
async def get_current_tenant() -> TenantContext:
    """获取当前租户上下文（用于依赖注入）"""
    context = _tenant_context_var.get()
    if not context:
        raise HTTPException(
            status_code=401,
            detail="租户上下文未找到"
        )
    return context
```

### 8.2 租户隔离中间件

```python
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """租户隔离中间件"""
    
    def __init__(
        self,
        app,
        tenant_resolver: TenantResolver,
        context_manager: TenantContextManager
    ):
        super().__init__(app)
        self.resolver = tenant_resolver
        self.context_manager = context_manager
        self.audit_logger = TenantIsolationAuditLogger()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求 - 租户隔离"""
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        
        try:
            # 1. 解析租户上下文
            tenant_context = await self.resolver.resolve(request)
            
            # 2. 设置租户上下文
            await self.context_manager.set_current(tenant_context)
            request.state.tenant_context = tenant_context
            
            # 3. 记录租户解析成功
            await self._log_tenant_resolution(request, tenant_context, request_id)
            
            # 4. 处理请求
            response = await call_next(request)
            
            # 5. 在响应头中添加租户信息（用于调试）
            response.headers["X-Tenant-ID"] = str(tenant_context.tenant_id)
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except TenantNotFoundError as e:
            # 租户未找到
            await self._log_tenant_resolution_failure(request, "not_found", request_id)
            return JSONResponse(
                status_code=401,
                content={"error": "租户未找到", "request_id": request_id}
            )
        
        except TenantInactiveError as e:
            # 租户未激活
            await self._log_tenant_resolution_failure(request, "inactive", request_id)
            return JSONResponse(
                status_code=403,
                content={"error": "租户未激活", "request_id": request_id}
            )
        
        except TenantExpiredError as e:
            # 租户已过期
            await self._log_tenant_resolution_failure(request, "expired", request_id)
            return JSONResponse(
                status_code=403,
                content={"error": "租户已过期", "request_id": request_id}
            )
        
        except Exception as e:
            # 其他异常
            await self._log_tenant_resolution_failure(request, "error", request_id, str(e))
            raise
    
    async def _log_tenant_resolution(
        self,
        request: Request,
        context: TenantContext,
        request_id: str
    ) -> None:
        """记录租户解析成功日志"""
        # 异步记录，不阻塞请求
        asyncio.create_task(self.audit_logger.log_tenant_resolution(
            tenant_id=context.tenant_id,
            user_id=context.user_id if hasattr(context, "user_id") else None,
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            resolver_type=context.resolver_type,
            status="success"
        ))
    
    async def _log_tenant_resolution_failure(
        self,
        request: Request,
        failure_reason: str,
        request_id: str,
        error_message: Optional[str] = None
    ) -> None:
        """记录租户解析失败日志"""
        asyncio.create_task(self.audit_logger.log_tenant_resolution(
            tenant_id=None,
            user_id=None,
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            resolver_type="unknown",
            status="failure",
            failure_reason=failure_reason,
            error_message=error_message
        ))
```

### 8.3 仓储层租户过滤

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text


class TenantAwareRepository:
    """租户感知仓储基类"""
    
    def __init__(
        self,
        db_session: AsyncSession,
        tenant_context: TenantContext
    ):
        self.db = db_session
        self.tenant = tenant_context
    
    async def _get_schema_name(self) -> str:
        """获取 Schema 名称"""
        if self.tenant.tier in [TenantTier.PROFESSIONAL, TenantTier.ENTERPRISE]:
            return f"tenant_{self.tenant.tenant_id.hex}"
        return "public"
    
    async def _apply_tenant_filter(self, query: Select) -> Select:
        """应用租户过滤"""
        # 设置 Schema
        schema = await self._get_schema_name()
        if schema != "public":
            await self.db.execute(text(f"SET search_path TO {schema}"))
        else:
            # Row-Level 过滤
            query = query.where(Document.tenant_id == self.tenant.tenant_id)
        
        return query
    
    # ========== Document Repository 示例 ==========
    
    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """获取文档"""
        query = select(Document).where(Document.id == document_id)
        query = await self._apply_tenant_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def find_documents(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """查找文档"""
        query = select(Document)
        query = await self._apply_tenant_filter(query)
        
        if status:
            query = query.where(Document.status == status)
        
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_document(self, document: Document) -> Document:
        """创建文档 - 自动注入租户 ID"""
        # 确保租户 ID 被设置
        document.tenant_id = self.tenant.tenant_id
        
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document
    
    async def delete_document(self, document_id: UUID) -> bool:
        """删除文档"""
        doc = await self.get_document(document_id)
        if doc:
            await self.db.delete(doc)
            await self.db.commit()
            return True
        return False
    
    # ========== StrategicPlan Repository 示例 ==========
    
    async def get_plan(self, plan_id: UUID) -> Optional[StrategicPlan]:
        """获取战略规划"""
        query = select(StrategicPlan).where(StrategicPlan.id == plan_id)
        query = await self._apply_tenant_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def find_plans(
        self,
        plan_type: Optional[PlanType] = None,
        status: Optional[PlanStatus] = None,
        limit: int = 100
    ) -> List[StrategicPlan]:
        """查找战略规划"""
        query = select(StrategicPlan)
        query = await self._apply_tenant_filter(query)
        
        if plan_type:
            query = query.where(StrategicPlan.plan_type == plan_type)
        if status:
            query = query.where(StrategicPlan.status == status)
        
        query = query.limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
```

---

## 9. 验收标准

### 9.1 隔离测试覆盖率

| 测试类型 | 覆盖率要求 | 测量方式 | 验收条件 |
|---------|----------|---------|---------|
| **单元测试** | ≥95% | pytest-cov | 所有租户隔离逻辑有单元测试 |
| **集成测试** | ≥90% | 测试场景覆盖 | 所有存储层隔离有集成测试 |
| **渗透测试** | 100% | 20+ 场景 | 所有 P0/P1 场景通过 |
| **E2E 测试** | ≥85% | 用户旅程覆盖 | 多租户工作流完整测试 |

### 9.2 渗透测试通过率

| 测试类别 | 场景数 | 通过率要求 | 验收条件 |
|---------|--------|----------|---------|
| **P0 关键场景** | 10 | 100% | 零失败 |
| **P1 重要场景** | 8 | 100% | 零失败 |
| **P2 可选场景** | 4 | ≥75% | 允许 1 个失败 |
| **总计** | 22 | ≥95% | 最多 1 个失败 |

### 9.3 审计完整性

| 审计要求 | 完整性要求 | 验证方式 | 验收条件 |
|---------|----------|---------|---------|
| **跨租户访问日志** | 100% | 日志抽样审计 | 所有访问可追溯 |
| **租户解析日志** | 100% | 日志完整性检查 | 零丢失 |
| **存储隔离违规日志** | 100% | WORM 存储验证 | 7 年可检索 |
| **告警触发日志** | 100% | 告警记录审计 | 所有告警可追溯 |

### 9.4 性能指标

| 指标 | 目标值 | 测量方式 | 验收条件 |
|------|--------|---------|---------|
| **租户解析延迟 P95** | <10ms | Prometheus 监控 | 持续 7 天达标 |
| **租户过滤查询延迟** | <50ms | 数据库监控 | P95 延迟 |
| **跨租户访问拒绝延迟** | <5ms | 应用监控 | 快速拒绝 |
| **审计日志写入延迟** | <100ms | 日志系统监控 | P99 延迟 |

### 9.5 安全合规验收

| 合规要求 | 验收标准 | 验证方式 |
|---------|---------|---------|
| **数据隔离** | 租户数据 100% 隔离 | 渗透测试 + 代码审计 |
| **审计追踪** | 7 年 WORM 存储 | MinIO 配置验证 + 抽样恢复测试 |
| **访问控制** | RBAC + 租户隔离 | 权限测试 + 渗透测试 |
| **加密传输** | TLS 1.3 全链路 | 安全扫描 + 配置审计 |
| **加密存储** | AES-256 | 数据库/对象存储配置验证 |

---

## 附录 A：与主架构文档的映射

| 本设计章节 | 主架构文档章节 | 关联内容 |
|----------|---------------|---------|
| 1. 多租户架构概述 | 第 15 章 风险缓解措施 | 多租户隔离失效风险 |
| 3. 五层存储租户隔离 | 第 11 章 存储架构设计 | 五层存储详细设计 |
| 5. RBAC 与租户权限 | 第 17 章 核心领域架构设计 | 安全设计 |
| 6. 渗透测试方案 | 第 24 章 测试策略 | OWASP 安全测试矩阵 |
| 7. 监控与审计 | 第 26 章 工作流监控 | 监控指标 |

---

## 附录 B：实现检查清单

### B.1 基础设施层实现

- [ ] PostgreSQL Schema per Tenant 迁移脚本
- [ ] Redis 租户键名前缀实现
- [ ] Qdrant Collection per Tenant 实现
- [ ] MinIO Bucket per Tenant 实现
- [ ] Neo4j 租户 Label 隔离实现

### B.2 应用层实现

- [ ] TenantResolver 多源解析器
- [ ] TenantIsolationMiddleware 中间件
- [ ] TenantContextManager 上下文管理器
- [ ] TenantAwareRepository 基类

### B.3 安全层实现

- [ ] TenantPermissionService 权限服务
- [ ] CrossTenantAccessGuard 跨租户防护
- [ ] TenantIsolationAuditLogger 审计日志器
- [ ] TenantIsolationAnomalyDetector 异常检测器

### B.4 测试实现

- [ ] 20+ 渗透测试场景自动化
- [ ] 租户隔离单元测试
- [ ] 租户隔离集成测试
- [ ] 租户隔离 E2E 测试

---

**文档状态：** 完整
**最后更新：** 2026-02-25
**审核人：** 架构团队
**批准人：** CTO
