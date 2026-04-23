# Qdrant 向量存储层部署指南 — Story 1.6

## 概述

Qdrant 作为 sisys 六层存储架构的 **L3 向量存储层**，承担以下职责：

| 职责 | 组件 | 延迟要求 |
|------|------|----------|
| 嵌入向量存储 | `QdrantVectorStorage` | P95 写入 <100ms |
| Dense 语义检索 | `QdrantVectorStorage.search()` | P95 检索 <500ms |
| BM25 稀疏检索 | `QdrantVectorStorage.search_sparse()` | P95 检索 <200ms |
| Collection 管理 | `QdrantCollectionManager` | P95 创建 <1s |
| 多租户隔离 | Collection 级别分离 | 100% 隔离验证 |

## 快速开始

### 1. 本地开发环境

```bash
# 进入部署目录
cd deploy/qdrant/

# 复制环境变量
cp .env.example .env

# 启动 Qdrant 容器
docker compose up -d

# 查看日志
docker compose logs -f

# 验证部署
cd ../..
./scripts/check-qdrant.sh
```

### 2. 验证部署

运行健康检查脚本（5 项检查）：

```bash
./scripts/check-qdrant.sh --host localhost --port 6333
```

预期输出：
```
=========================================
Qdrant 健康检查
=========================================
URL: http://localhost:6333
超时: 10s
最大重试次数: 5

检查 1/5: Qdrant 服务连接... ✅ 通过
检查 2/5: Qdrant 版本验证... ✅ 版本 1.7.4（满足 v1.7+ 要求）
检查 3/5: REST API 健康... ✅ 通过
检查 4/5: Collection 创建测试... ✅ 通过
检查 5/5: Collection 清理... ✅ 通过

=========================================
✅ 所有检查通过！Qdrant 服务正常
=========================================
```

### 3. 运行集成测试

```bash
# 确保 Qdrant 服务已启动
docker compose -f deploy/qdrant/docker-compose.yml ps

# 运行集成测试（5 个测试）
poetry run pytest tests/integration/test_qdrant_integration.py -v
```

### 4. 停止和清理

```bash
# 停止容器
docker compose down

# 停止并删除数据卷（谨慎操作！）
docker compose down -v
```

## 配置说明

### qdrant.yaml 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `storage.hnsw_index.m` | 16 | HNSW 连接数，增加可提高检索准确率但降低性能 |
| `storage.hnsw_index.ef_construct` | 128 | HNSW 构建时 ef 参数，推荐 `m*8` |
| `storage.hnsw_index.full_scan_threshold` | 10000 | 全扫描阈值，超过此值使用 HNSW 索引 |
| `log_level` | info | 日志级别（debug/info/warn/error） |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QDRANT_HOST` | localhost | Qdrant 主机地址 |
| `QDRANT_PORT` | 6333 | REST API 端口 |
| `QDRANT_GRPC_PORT` | 6334 | gRPC API 端口 |
| `QDRANT_API_KEY` | 无 | API 密钥（生产环境必须） |
| `QDRANT_HTTPS` | false | 是否使用 HTTPS |
| `QDRANT_TIMEOUT` | 30.0 | 请求超时秒数 |
| `QDRANT_MAX_RETRIES` | 3 | 最大重试次数 |

### 应用层连接配置

```python
from src.infrastructure.config.qdrant import QdrantConfig
from src.infrastructure.storage.qdrant.client import QdrantClientWrapper
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

# 从环境变量加载配置
config = QdrantConfig.from_env()

# 创建客户端
client_wrapper = QdrantClientWrapper(
    host=config.host,
    port=config.port,
    grpc_port=config.grpc_port,
    api_key=config.api_key,
    https=config.https,
    timeout=config.timeout,
    max_retries=config.max_retries,
)

# 创建向量存储
vector_storage = QdrantVectorStorage(client_wrapper)
```

## Collection 命名规范

所有 Collection 应遵循 `sisys:{collection_type}:{namespace}` 规范：

| Collection 类型 | 示例 | 用途 |
|----------------|------|------|
| `documents` | `sisys:documents:finance` | 文档向量存储 |
| `embeddings` | `sisys:embeddings:main` | 嵌入向量缓存 |
| `strategic_archive` | `sisys:strategic_archive:q1_2024` | 战略档案永久存储 |

## 生产环境部署

### 要求

- Qdrant ≥1.7.0
- 内存 ≥2GB
- CPU ≥1 核
- 存储 ≥500GB（根据向量数量调整）

### 生产环境配置要点

```yaml
# docker-compose.prod.yml 关键差异

services:
  qdrant:
    environment:
      # 必须启用 API 密钥
      - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
      # 禁用 Telemetry
      - QDRANT__TELEMETRY__DISABLED=true
    # 增加资源限制
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '2.0'
```

### 高可用部署（集群模式）

```yaml
# 集群节点 1
services:
  qdrant-1:
    environment:
      - QDRANT__CLUSTER__ENABLED=true
      - QDRANT__CLUSTER__P2P__PORT=6335
      - QDRANT__CLUSTER__CONSENSUS__PORT=6336

# 集群节点 2
  qdrant-2:
    environment:
      - QDRANT__CLUSTER__ENABLED=true
      - QDRANT__CLUSTER__P2P__PORT=6335
      - QDRANT__CLUSTER__CONSENSUS__PORT=6336
```

## 监控和运维

### 健康检查

容器已配置健康检查（`curl http://localhost:6333/healthz`），每 30 秒执行一次。

### Collection 管理

```bash
# 查看所有 Collection
curl http://localhost:6333/collections

# 查看特定 Collection 信息
curl http://localhost:6333/collections/sisys:documents:finance

# 删除 Collection
curl -X DELETE http://localhost:6333/collections/sisys:documents:finance
```

### 性能监控

```bash
# 查看 Qdrant Telemetry
curl http://localhost:6333/telemetry

# 查看 Collection 统计
curl http://localhost:6333/collections/{collection_name}
```

## 故障排查

### 服务无法启动

```bash
# 检查容器状态
docker compose ps

# 检查日志
docker compose logs qdrant

# 常见原因：
# 1. 端口被占用：lsof -i :6333
# 2. 配置文件语法错误：检查 qdrant.yaml
# 3. 磁盘空间不足：df -h
```

### Collection 创建失败

```bash
# 查看 Qdrant 日志
docker logs sisys-qdrant | grep ERROR

# 检查 Collection 命名规范
# 应遵循: sisys:{collection_type}:{namespace}
```

### 检索性能不达标

```bash
# 调整 HNSW 查询参数
# 在 search 时指定 ef 参数值（代码层面）
search_params = {"ef": 128}  # 默认 64

# 检查 Collection 配置
curl http://localhost:6333/collections/{collection_name}

# 确认 hnsw_config.m 和 ef_construct 设置
```

## 架构集成

Qdrant 在 sisys 中的位置：

```
┌─────────────────────────────────────────────┐
│              应用层 (Application)            │
├─────────────────────────────────────────────┤
│     RAGService │ HybridSearchService        │
├─────────────────────────────────────────────┤
│     Qdrant v1.7+ (L3 向量存储层)             │
│  Dense 检索 │ BM25 检索 │ RRF 融合          │
└─────────────────────────────────────────────┘
```

## 相关文档

- Story 1.6: `_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md`
- 健康检查脚本: `scripts/check-qdrant.sh`
- 应用配置: `src/infrastructure/config/qdrant.py`
- 架构文档: `_bmad-output/planning-artifacts/architecture.md`
