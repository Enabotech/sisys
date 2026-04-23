# Qdrant 向量存储层部署指南

**Story:** 1.6-Qdrant-Vector-Layer
**版本:** Qdrant v1.7.0+
**最后更新:** 2026-04-14

---

## 📋 目录

1. [概述](#概述)
2. [本地开发环境部署](#本地开发环境部署)
3. [健康检查](#健康检查)
4. [集成测试验证](#集成测试验证)
5. [生产环境部署](#生产环境部署)
6. [故障排查](#故障排查)

---

## 概述

Qdrant 是 SISYS 六层存储架构的 **L3 向量存储层**，负责：

- **嵌入向量存储** - bge-m3 模型生成的 1024 维向量
- **Dense 语义检索** - 基于向量相似度的文档检索（Top-K）
- **BM25 稀疏检索** - 关键词匹配的稀疏检索
- **混合检索基础** - Dense + Sparse 双路召回基座
- **多租户隔离** - 按业务域分离 Collection

**技术选型：**
- 技术：Qdrant 1.7.4+
- 向量维度：1024 维（bge-m3 嵌入模型）
- 相似度度量：COSINE
- HNSW 索引：m=16, ef_construct=128, full_scan_threshold=10000
- 延迟目标：P95<500ms

---

## 本地开发环境部署

### 前置条件

- Docker v20.10+
- Docker Compose v2.0+
- 可用内存 ≥2GB

### 步骤 1: 启动 Qdrant 服务

```bash
# 从项目根目录执行
docker compose -f deploy/qdrant/docker-compose.yml up -d

# 查看日志
docker compose -f deploy/qdrant/docker-compose.yml logs -f qdrant
```

### 步骤 2: 验证部署

```bash
# 运行健康检查脚本
./scripts/check-qdrant.sh

# 或手动验证
curl http://localhost:6333/healthz
curl http://localhost:6333/collections
```

**预期输出：**
```json
{"status":"ok"}
```

### 步骤 3: 配置环境变量

```bash
# 复制并编辑 .env 文件
cp .env.example .env

# 确认 Qdrant 配置
cat .env | grep QDRANT
```

**关键环境变量：**
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QDRANT_HOST` | localhost | Qdrant 主机地址 |
| `QDRANT_PORT` | 6333 | REST API 端口 |
| `QDRANT_GRPC_PORT` | 6334 | gRPC API 端口 |
| `QDRANT_API_KEY` | (空) | API 密钥（生产环境必须设置） |
| `QDRANT_HTTPS` | false | 是否使用 HTTPS |
| `QDRANT_TIMEOUT` | 30.0 | 请求超时秒数 |
| `QDRANT_MAX_RETRIES` | 3 | 最大重试次数 |

---

## 健康检查

### 自动健康检查

Qdrant Docker Compose 配置包含内置健康检查：

```yaml
healthcheck:
  test: ["CMD", "bash", "-c", "curl -f http://localhost:6333/healthz || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

### 手动健康检查

```bash
# 检查服务状态
curl http://localhost:6333/healthz

# 检查 Collections 列表
curl http://localhost:6333/collections

# 检查 Qdrant 版本
curl http://localhost:6333/ | grep version
```

### 运行完整健康检查脚本

```bash
./scripts/check-qdrant.sh
```

**脚本执行 5 项检查：**
1. Qdrant 服务连接
2. Qdrant 版本验证（v1.7+）
3. REST API 健康
4. Collection 创建测试
5. Collection 清理

---

## 集成测试验证

### 运行 Mock 测试（无需 Qdrant 服务）

```bash
# 运行所有 Story 1.6 单元测试
poetry run pytest tests/unit/infrastructure/test_qdrant*.py -v

# 运行架构约束测试
poetry run pytest tests/unit/infrastructure/test_architecture_constraints.py -v
```

### 运行真实服务集成测试（需要 Qdrant 服务运行）

```bash
# 1. 确保 Qdrant 服务已启动
docker compose -f deploy/qdrant/docker-compose.yml up -d

# 2. 运行健康检查
./scripts/check-qdrant.sh

# 3. 运行集成测试
poetry run pytest tests/integration/test_qdrant_integration.py -v
```

**集成测试覆盖：**
- Collection 生命周期（创建→验证→删除）
- 向量点存储端到端流程
- Dense 语义检索流程
- BM25 稀疏检索流程
- 多租户隔离验证

---

## 生产环境部署

### K3S + ArgoCD 部署（推荐）

**前置条件：**
- Story 0.4: K3S 集群已部署
- Story 0.7: ArgoCD 持续部署已配置

**部署步骤：**

1. **创建 Kubernetes 配置**

```yaml
# deploy/qdrant/k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
  namespace: sisys
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
      - name: qdrant
        image: harbor.sisys.local/sisys/tools/qdrant/qdrant:v1.7.1
        ports:
        - containerPort: 6333
          name: http
        - containerPort: 6334
          name: grpc
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 6333
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /healthz
            port: 6333
          initialDelaySeconds: 5
          periodSeconds: 10
        env:
        - name: QDRANT__SERVICE__HTTP_PORT
          value: "6333"
        - name: QDRANT__SERVICE__GRPC_PORT
          value: "6334"
        - name: QDRANT__SERVICE__API_KEY
          valueFrom:
            secretKeyRef:
              name: qdrant-secret
              key: api-key
```

2. **创建 Service**

```yaml
# deploy/qdrant/k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: qdrant
  namespace: sisys
spec:
  selector:
    app: qdrant
  ports:
  - name: http
    port: 6333
    targetPort: 6333
  - name: grpc
    port: 6334
    targetPort: 6334
  type: ClusterIP
```

3. **创建 PersistentVolumeClaim**

```yaml
# deploy/qdrant/k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-data
  namespace: sisys
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: local-path
```

4. **通过 ArgoCD 部署**

```bash
# 添加 GitOps 仓库
argocd app create qdrant \
  --repo https://gitea.sisys.local/sisys/deploy.git \
  --path deploy/qdrant/k8s \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace sisys \
  --sync-policy automated
```

### Docker Swarm 部署

```bash
# 创建 Docker Compose Stack
docker stack deploy -c deploy/qdrant/docker-compose.yml sisys
```

---

## 故障排查

### Qdrant 服务无法启动

**症状：** `docker compose up` 后容器持续重启

**排查步骤：**

```bash
# 1. 查看容器日志
docker logs sisys-qdrant

# 2. 检查端口占用
lsof -i :6333
lsof -i :6334

# 3. 检查磁盘空间
df -h

# 4. 检查 Docker 卷
docker volume ls | grep qdrant
```

**常见原因：**
- 端口被占用 → 修改 `QDRANT_PORT` 环境变量
- 磁盘空间不足 → 清理 Docker 卷或扩展磁盘
- 内存不足 → 调整 Docker 资源限制

### 集成测试失败

**症状：** `test_qdrant_integration.py` 失败

**排查步骤：**

```bash
# 1. 确认 Qdrant 服务运行
docker compose -f deploy/qdrant/docker-compose.yml ps

# 2. 运行健康检查
./scripts/check-qdrant.sh

# 3. 检查网络连接
curl http://localhost:6333/healthz

# 4. 查看测试详细输出
poetry run pytest tests/integration/test_qdrant_integration.py -v --tb=long
```

### Collection 创建失败

**症状：** `create_collection` 调用失败

**排查步骤：**

```bash
# 1. 查看 Qdrant 日志
docker logs sisys-qdrant | grep ERROR

# 2. 检查 Collection 命名规范
# 应遵循: sisys:{collection_type}:{namespace}
# 示例: sisys:documents:finance

# 3. 检查 HNSW 配置
curl http://localhost:6333/collections/sisys:documents:finance
```

### 性能不达标（P95>500ms）

**症状：** 检索延迟超过 500ms

**优化建议：**

1. **调整 HNSW 查询参数**

```python
# 在 search 时指定 ef 参数
search_params = {"ef": 128}  # 默认 64，增加可提高准确率但降低性能
```

2. **检查 Collection 配置**

```bash
# 查看 Collection 信息
curl http://localhost:6333/collections/{collection_name}

# 确认 hnsw_config.m 和 ef_construct
```

3. **监控资源使用**

```bash
# 查看容器资源使用
docker stats sisys-qdrant

# 如果 CPU/内存达到限制，考虑增加资源配额
```

---

## 附录：Collection 命名规范

所有 Collection 应遵循 `sisys:{collection_type}:{namespace}` 规范：

| Collection 类型 | 示例 | 用途 |
|----------------|------|------|
| `documents` | `sisys:documents:finance` | 文档向量存储 |
| `embeddings` | `sisys:embeddings:main` | 嵌入向量缓存 |
| `strategic_archive` | `sisys:strategic_archive:q1_2024` | 战略档案永久存储 |

---

## 参考文档

- [Qdrant 官方文档](https://qdrant.tech/documentation/)
- [Qdrant API 参考](https://qdrant.github.io/qdrant/redoc/index.html)
- [Story 1.6 实现文档](../../_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md)
- [架构文档](../../_bmad-output/planning-artifacts/architecture.md)
