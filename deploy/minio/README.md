# MinIO 对象存储层部署指南 — Story 1.7

## 概述

MinIO 作为 sisys 五层存储架构的 **L4 对象存储层**，承担以下职责：

- **文档存储**：原始文档、处理后文档、附件等
- **WORM 合规锁**：SOX 合规性 7 年不可篡改保留
- **生命周期管理**：自动过期清理临时对象
- **多租户 Bucket 隔离**：`{prefix}-{type}-{tenant_id}` 命名规范
- **版本控制**：文档历史版本追踪
- **分片上传**：大文件断点续传

## 版本要求

- MinIO Server: `RELEASE.2024-01+`（支持对象锁定和生命周期管理）
- MinIO Client (mc): 与 Server 版本匹配

## 目录结构

```
deploy/minio/
├── .env.example              # 环境变量模板
├── docker-compose.yml        # 本地开发环境
├── docker-compose.prod.yml   # 生产环境
├── minio.conf                # 开发环境配置
├── minio-prod.conf           # 生产环境配置
└── README.md                 # 本文件
```

## 快速开始

### 本地开发环境

```bash
cd deploy/minio
cp .env.example .env
docker compose up -d
```

### 验证部署

```bash
# 检查容器状态
docker compose ps

# 检查健康状态
docker compose exec minio mc ready local

# 访问控制台
# http://localhost:9001
# 用户名: minioadmin
# 密码: minioadmin
```

### 生产环境部署

```bash
cd deploy/minio
cp .env.example .env
# 编辑 .env，设置强密码
docker compose -f docker-compose.prod.yml up -d
```

## 环境变量

| 变量 | 说明 | 开发默认 | 生产要求 |
|------|------|----------|----------|
| `MINIO_ROOT_USER` | Root 用户名 | `minioadmin` | 强用户名 |
| `MINIO_ROOT_PASSWORD` | Root 密码 | `minioadmin` | 强密码（≥8 字符）|
| `MINIO_API_PORT` | API 端口 | `9000` | 按需调整 |
| `MINIO_CONSOLE_PORT` | 控制台端口 | `9001` | 按需调整 |
| `MINIO_SOX_RETENTION_DAYS` | SOX 保留天数 | `2555` | 保持 2555 |

## 网络配置

- API 端口: `9000`（S3 兼容 API）
- 控制台端口: `9001`（Web 管理界面）

## 数据持久化

数据存储在 `/data` 目录，通过 Docker volume 持久化：
- 开发: `sisys-minio-data`
- 生产: `sisys-minio-data-prod`

## 安全注意事项

1. **生产环境必须使用强密码**
2. **启用 TLS**（通过反向代理或 MinIO 原生支持）
3. **限制网络访问**（仅允许应用网络）
4. **定期备份** MinIO 数据卷
5. **启用审计日志**

## 与 sisys 应用集成

应用通过 `MinIORepository` 接口与 MinIO 交互：

```python
# 应用配置示例
MINIO_ENDPOINT=minio.sisys.svc.cluster.local:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_PREFIX=sisys
```

## 故障排查

```bash
# 查看日志
docker compose logs -f minio

# 进入容器
docker compose exec minio sh

# 检查 MinIO 状态
docker compose exec minio mc admin info local
```
