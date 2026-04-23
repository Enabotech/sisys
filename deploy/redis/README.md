# Redis 高速缓存层部署指南 — Story 1.4

## 概述

Redis 作为 sisys 六层存储架构的 **L1 高速缓存层**，承担以下职责：

| 职责 | 组件 | 延迟要求 |
|------|------|----------|
| 会话状态缓存 | `RedisSessionStorage` | P95 读取 <5ms |
| 语义缓存 | `RedisSemanticCache` | P95 写入 <10ms |
| 公共黑板 | `RedisPublicBlackboard` | P95 读写 <10ms |
| 事件发布/订阅 | `RedisEventPublisher` / `RedisEventSubscriber` | P95 发布 <10ms |
| 幂等性检查 | `IdempotencyChecker` | P95 获取 <5ms |

## 快速开始

### 1. 本地开发环境

```bash
# 进入部署目录
cd deploy/redis/

# 复制环境变量
cp .env.example .env

# 启动 Redis 容器
docker compose up -d

# 查看日志
docker compose logs -f

# 验证部署
cd ../..
poetry run python scripts/verify_redis_ready.py
```

### 2. 验证部署

运行部署验证脚本（6 项检查）：

```bash
poetry run python scripts/verify_redis_ready.py --host localhost --port 6379
```

预期输出：
```
验证 1: 连接 Redis localhost:6379...
  ✅ Redis 版本 7.2.5 (≥7.0 要求满足)
验证 2: 连接池测试...
  ✅ 连接池正常
验证 3: 基础操作测试...
  ✅ SET/GET/DEL/TTL/EXPIRE 全部正常
验证 4: 序列化性能测试...
  ✅ 序列化性能达标
验证 5: 读写延迟测试...
  ✅ 读写延迟达标
验证 6: 优雅降级测试...
  ✅ 连接失败时正确抛出异常
🎉 所有验证通过！
```

### 3. 停止和清理

```bash
# 停止容器
docker compose down

# 停止并删除数据卷（谨慎操作！）
docker compose down -v
```

## 配置说明

### redis.conf 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `dir` | /data | **重要**：必须与容器 volume 挂载点一致 |
| `maxmemory` | 2gb | 最大内存，根据服务器调整 |
| `maxmemory-policy` | volatile-lru | 淘汰策略，推荐 volatile-lru |
| `timeout` | 300 | 空闲连接超时（秒） |
| `databases` | 16 | 数据库数量 |
| `requirepass` | 注释 | 生产环境必须启用 |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_PORT` | 6379 | Redis 端口 |
| `REDIS_PASSWORD` | 无 | 密码（生产环境必须） |

### 应用层连接配置

```python
from src.infrastructure.config.redis import RedisConfig

config = RedisConfig(
    host="localhost",
    port=6379,
    db=0,
    password=None,  # 生产环境设置
    max_connections=20,
    socket_timeout=5.0,
)
```

## 生产环境部署

### 要求

- Redis ≥7.0
- 内存 ≥2GB
- 启用密码认证 (`requirepass`)
- 主从复制（高可用）
- 定期 RDB 快照

### 主从复制

```yaml
# 主节点 docker-compose.yml（无需特殊配置）

# 从节点 docker-compose.yml 追加
services:
  redis-replica:
    image: harbor.sisys.local/sisys/tools/redis:7.2.5
    command: ["redis-server", "--replicaof", "redis-master", "6379"]
    environment:
      - REDIS_MASTERAUTH=${REDIS_PASSWORD}
```

## 监控和运维

### 健康检查

容器已配置健康检查（`redis-cli ping`），每 30 秒执行一次。

### 慢查询日志

```bash
# 查看慢查询
redis-cli SLOWLOG GET 10

# 查看慢查询数量
redis-cli SLOWLOG LEN
```

### 内存使用

```bash
# 查看内存使用
redis-cli INFO memory

# 查看键数量
redis-cli DBSIZE
```

## 故障排查

### 连接失败

```bash
# 检查容器状态
docker compose ps

# 检查日志
docker compose logs redis
```

### 内存溢出

如果 Redis 内存超限，会根据 `maxmemory-policy` 淘汰 key。推荐 `volatile-lru`（优先淘汰设置了 TTL 的 key）。

### 持久化失败

RDB 快照失败通常是磁盘空间不足或 `dir` 配置路径错误。Docker 部署中 `dir` 必须设置为 `/data`（与 volume 挂载点一致）。检查日志中的配置路径错误信息。

## 架构集成

Redis 在 sisys 中的位置：

```
┌─────────────────────────────────────────────┐
│              应用层 (Application)            │
├─────────────────────────────────────────────┤
│  SessionStorage │ SemanticCache │ Blackboard │
│  EventPublisher │ Idempotency   │ Cleanup    │
├─────────────────────────────────────────────┤
│         Redis 7.0+ (L1 高速缓存层)           │
│  会话状态 │ 语义缓存 │ 公共黑板 │ 事件总线   │
└─────────────────────────────────────────────┘
```

## 相关文档

- Story 1.4: `_bmad-output/implementation-artifacts/stories/1-4-redis-cache-layer.md`
- 验证脚本: `scripts/verify_redis_ready.py`
- 应用配置: `src/infrastructure/config/redis.py`
