# SISYS 五层存储部署指南

## 快速开始

### 一键启动所有存储服务（本地开发）

```bash
# 1. 复制环境变量文件
for svc in redis postgresql qdrant minio neo4j; do
  cp deploy/$svc/.env.example deploy/$svc/.env
done

# 2. 启动所有服务
docker compose -f deploy/docker-compose.yml up -d

# 3. 验证服务状态
docker compose -f deploy/docker-compose.yml ps

# 4. 运行数据库迁移
poetry run alembic -c deploy/postgresql/alembic/alembic.ini upgrade head
```

### 停止所有服务

```bash
docker compose -f deploy/docker-compose.yml down
```

---

## 服务概览

| 层级 | 服务 | 端口 | 用途 | Story |
|------|------|------|------|-------|
| L1 | Redis | 6379 | 会话状态、语义缓存、Pub/Sub | 1.4 |
| L2 | PostgreSQL | 5432 | 用户/RBAC、审计元数据、Outbox | 1.5 |
| L3 | Qdrant | 6333/6334 | 向量存储、混合检索 | 1.6 |
| L4 | MinIO | 9000/9001 | 对象存储、WORM | 1.7 |
| L5 | Neo4j | 7474/7687 | 图存储、GraphRAG | 1.8 |

---

## 单独服务部署

### Redis（L1 缓存）

```bash
cd deploy/redis
cp .env.example .env
docker compose up -d
```

**健康检查：** `redis-cli -h localhost -p 6379 ping`

---

### PostgreSQL（L2 关系存储）

```bash
cd deploy/postgresql
cp .env.example .env
docker compose up -d

# 运行初始迁移
poetry run alembic -c deploy/postgresql/alembic/alembic.ini upgrade head
```

**健康检查：** `pg_isready -h localhost -p 5432 -U postgres`

---

### Qdrant（L3 向量存储）

```bash
cd deploy/qdrant
cp .env.example .env
docker compose up -d
```

**健康检查：** `curl http://localhost:6333/healthz`

---

### MinIO（L4 对象存储）

```bash
cd deploy/minio
cp .env.example .env
docker compose up -d
```

**控制台：** http://localhost:9001 (默认账号: minioadmin / minioadmin)

**健康检查：** `mc ready local`

---

### Neo4j（L5 图存储）

```bash
cd deploy/neo4j
cp .env.example .env
docker compose up -d
```

**健康检查：** `curl http://localhost:7474/health`

---

## 环境变量说明

### 通用变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COMPOSE_PROJECT_NAME` | sisys | Docker Compose 项目名称 |
| `HARBOR_REGISTRY` | harbor.sisys.local | 镜像仓库地址 |

### Redis 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_HOST` | localhost | Redis 主机 |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `REDIS_DB` | 0 | 数据库编号 |
| `REDIS_PASSWORD` | - | 密码（生产必填） |
| `REDIS_SESSION_TTL` | 86400 | 会话 TTL（秒） |
| `REDIS_CACHE_TTL` | 86400 | 缓存 TTL（秒） |
| `REDIS_BLACKBOARD_TTL` | 604800 | 公共黑板 TTL（秒） |

### PostgreSQL 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_HOST` | localhost | PostgreSQL 主机 |
| `POSTGRES_PORT` | 5432 | PostgreSQL 端口 |
| `POSTGRES_DATABASE` | sisys | 数据库名 |
| `POSTGRES_USERNAME` | postgres | 用户名 |
| `POSTGRES_PASSWORD` | postgres | 密码（生产必改） |
| `POSTGRES_POOL_SIZE` | 5 | 连接池大小 |
| `POSTGRES_MAX_OVERFLOW` | 10 | 最大溢出连接 |

### Qdrant 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QDRANT_HOST` | localhost | Qdrant 主机 |
| `QDRANT_PORT` | 6333 | REST API 端口 |
| `QDRANT_GRPC_PORT` | 6334 | gRPC 端口 |
| `QDRANT_API_KEY` | - | API 密钥（生产必填） |
| `QDRANT_LOG_LEVEL` | info | 日志级别 |

### MinIO 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MINIO_HOST` | localhost | MinIO 主机 |
| `MINIO_API_PORT` | 9000 | API 端口 |
| `MINIO_CONSOLE_PORT` | 9001 | 控制台端口 |
| `MINIO_ROOT_USER` | minioadmin | Root 用户 |
| `MINIO_ROOT_PASSWORD` | minioadmin | Root 密码（生产必改） |
| `MINIO_BUCKET_PREFIX` | sisys | Bucket 前缀 |
| `MINIO_SOX_RETENTION_DAYS` | 2555 | SOX 保留天数（7年） |

### Neo4j 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEO4J_HOST` | localhost | Neo4j 主机 |
| `NEO4J_HTTP_PORT` | 7474 | HTTP 端口 |
| `NEO4J_BOLT_PORT` | 7687 | Bolt 端口 |
| `NEO4J_USERNAME` | neo4j | 用户名 |
| `NEO4J_PASSWORD` | - | 密码（生产必填） |
| `NEO4J_MAX_POOL_SIZE` | 50 | 连接池大小 |
| `NEO4J_HEAP_MAX_SIZE` | 1G | 最大堆内存 |

---

## 网络配置

所有服务通过 `sisys-network` 桥接网络互联。

```
┌─────────────────────────────────────────────────────────┐
│                    sisys-network                         │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  │
│  │  Redis  │  │ PostgreSQL│  │ Qdrant  │  │  MinIO   │  │
│  │  L1     │  │   L2     │  │   L3    │  │    L4    │  │
│  └─────────┘  └──────────┘  └─────────┘  └──────────┘  │
│                          ┌──────────┐                   │
│                          │  Neo4j   │                   │
│                          │   L5     │                   │
│                          └──────────┘                   │
└─────────────────────────────────────────────────────────┘
```

---

## 生产部署检查清单

- [ ] 所有密码已修改为强密码
- [ ] API 密钥已配置（Qdrant、Neo4j）
- [ ] 数据卷已挂载到持久化存储
- [ ] 健康检查已验证
- [ ] 防火墙/安全组已配置
- [ ] 备份策略已启用

---

## 故障排查

### 查看日志

```bash
# 查看所有服务日志
docker compose -f deploy/docker-compose.yml logs

# 查看单个服务
docker compose -f deploy/docker-compose.yml logs redis
docker compose -f deploy/docker-compose.yml logs postgres
docker compose -f deploy/docker-compose.yml logs qdrant
docker compose -f deploy/docker-compose.yml logs minio
docker compose -f deploy/docker-compose.yml logs neo4j
```

### 重建服务

```bash
docker compose -f deploy/docker-compose.yml down
docker compose -f deploy/docker-compose.yml up -d --force-recreate
```
