# MinIO 部署与配置指南

## 概述

MinIO 是 sisys 系统的 L4 对象存储层，提供 S3 兼容的对象存储服务。
支持版本控制、WORM（Write Once Read Many）存储、断点续传和对象生命周期管理。

## 本地开发部署

### 1. Docker Compose 部署

```yaml
# docker-compose.minio.yml
version: '3.8'

services:
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"      # API
      - "9001:9001"      # Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

volumes:
  minio_data:
```

启动服务：
```bash
docker compose -f docker-compose.minio.yml up -d
```

### 2. 环境变量配置

```bash
# MinIO 连接配置
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export MINIO_SECURE=false
export MINIO_BUCKET_PREFIX=sisys
export MINIO_CONNECT_TIMEOUT=5.0
export MINIO_READ_TIMEOUT=30.0
```

### 3. 验证连接

```python
from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.client_adapter import MinioManager

config = MinIOConfig.from_env()
adapter = MinioManager(config)
assert adapter.health_check(), "MinIO 连接失败"
print("✅ MinIO 连接成功")
```

## 生产部署注意事项

1. **使用 HTTPS** — 设置 `MINIO_SECURE=true`
2. **强密码** — 使用强凭证，不要使用默认 `minioadmin`
3. **数据持久化** — 使用持久卷或分布式部署
4. **监控** — 集成 Prometheus 监控 MinIO 指标
5. **备份** — 定期备份 MinIO 数据到异地

## Bucket 命名规范

| bucket_type | 物理 Bucket 名称 | 用途 |
|------------|-----------------|------|
| `raw-documents` | `sisys-raw-documents` | 原始文档存储 |
| `processed-documents` | `sisys-processed-documents` | 处理后文档 |
| `evidence-packages` | `sisys-evidence-packages` | 证据包 |
| `audit-archives` | `sisys-audit-archives` | 审计归档（WORM 7 年） |
| `backups` | `sisys-backups` | Checkpoint 旧版本归档（WORM 7 年） |
| `branches` | `sisys-branches` | 分支状态存储 |

## WORM 合规配置

审计归档 Bucket 必须启用 Object Lock（COMPLIANCE 模式），保留期限 2555 天（7 年）：

```python
from src.infrastructure.storage.minio.worm_lifecycle import WORMManager
from src.infrastructure.storage.minio.client_adapter import MinioManager
from src.infrastructure.config.minio import MinIOConfig

config = MinIOConfig.from_env()
adapter = MinioManager(config)
worm_manager = WORMManager(adapter.client)

# 启用 WORM 锁定
worm_manager.enable_worm_lock(
    bucket_name="sisys-audit-archives",
    object_key="audit-log-2024.json",
    retention_days=2555  # 7 年 SOX 合规
)
```

## 故障排除

| 问题 | 解决方案 |
|------|---------|
| 连接超时 | 检查 `MINIO_ENDPOINT` 和网络连通性 |
| 凭证错误 | 验证 `MINIO_ACCESS_KEY` 和 `MINIO_SECRET_KEY` |
| Bucket 不存在 | 使用 `BucketManager.create_bucket()` 创建 |
| WORM 锁定错误 | 确认 Object Lock 已启用，对象在保留期内不可删除 |
