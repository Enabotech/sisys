# Alembic 数据库迁移指南

本文档介绍 sisys 项目中 PostgreSQL 数据库的 Alembic 迁移管理。

---

## 目录

1. [快速开始](#快速开始)
2. [目录结构](#目录结构)
3. [环境变量配置](#环境变量配置)
4. [常用命令](#常用命令)
5. [创建新迁移](#创建新迁移)
6. [迁移最佳实践](#迁移最佳实践)
7. [故障排除](#故障排除)
8. [生产环境部署](#生产环境部署)

---

## 快速开始

### 1. 配置环境变量

```bash
# PostgreSQL 连接配置
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=sisys
export POSTGRES_USERNAME=postgres
export POSTGRES_PASSWORD=postgres
```

### 2. 执行迁移

```bash
cd deploy/postgresql/alembic

# 首次迁移
poetry run alembic upgrade head

# 验证当前版本
poetry run alembic current
```

### 3. 查看迁移历史

```bash
poetry run alembic history
```

---

## 目录结构

```
deploy/postgresql/alembic/
├── alembic.ini          # Alembic 配置文件
├── env.py               # 迁移环境配置（从环境变量读取数据库 URL）
├── script.py.mako       # 新迁移脚本模板
└── versions/           # 迁移版本脚本目录
    ├── 001_initial.py   # 初始迁移（创建核心表）
    └── ...              # 后续迁移脚本
```

---

## 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL 主机地址 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 端口 |
| `POSTGRES_DATABASE` | `sisys` | 数据库名 |
| `POSTGRES_USERNAME` | `postgres` | 数据库用户名 |
| `POSTGRES_PASSWORD` | `""` | 数据库密码 |

### Docker 环境示例

```bash
# 本地开发
export POSTGRES_HOST=localhost
export POSTGRES_PASSWORD=postgres

# Docker Compose 环境
export POSTGRES_HOST=postgres
export POSTGRES_PASSWORD=sisys_password
export POSTGRES_DATABASE=sisys
export POSTGRES_USERNAME=sisys
```

### Docker Compose 配置参考

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: sisys
      POSTGRES_USER: sisys
      POSTGRES_PASSWORD: sisys_password
    ports:
      - "5432:5432"
```

---

## 常用命令

### 基本操作

```bash
# 进入 alembic 目录
cd deploy/postgresql/alembic

# 升级到最新版本
poetry run alembic upgrade head

# 升级到指定版本
poetry run alembic upgrade <revision>

# 回滚到上一个版本
poetry run alembic downgrade -1

# 回滚到指定版本
poetry run alembic downgrade <revision>

# 查看当前版本
poetry run alembic current

# 查看迁移历史
poetry run alembic history

# 查看可用版本
poetry run alembic heads

# 查看版本详细信息
poetry run alembic show <revision>
```

### 生成迁移

```bash
# 自动生成迁移（基于模型变更）
poetry run alembic revision --autogenerate -m "描述迁移内容"

# 手动创建空迁移
poetry run alembic revision -m "描述迁移内容"
```

### 离线模式（不连接数据库）

```bash
# 生成 SQL 脚本（用于检查或手动执行）
poetry run alembic upgrade head --sql > migration.sql

# 查看 SQL 而不执行
poetry run alembic upgrade head --sql
```

### 验证

```bash
# 检查迁移脚本语法
poetry run alembic check

# 验证当前状态
poetry run alembic validate
```

---

## 创建新迁移

### 步骤 1：修改模型

在 `src/infrastructure/storage/postgresql/models/` 中修改对应的 SQLAlchemy 模型。

### 步骤 2：生成迁移

```bash
poetry run alembic revision --autogenerate -m "add_phone_to_users"
```

### 步骤 3：检查生成的迁移

编辑 `versions/xxx_add_phone_to_users.py`，确保：
- `upgrade()` 正确添加/修改/删除列
- `downgrade()` 正确回滚操作
- 包含必要的索引和约束

### 步骤 4：测试迁移

```bash
# 升级
poetry run alembic upgrade head

# 回滚
poetry run alembic downgrade -1

# 重新升级确认
poetry run alembic upgrade head
```

### 迁移脚本模板

```python
"""迁移描述。

Revision ID: <revision_id>
Revises: <上一版本revision>
Create Date: <创建日期>
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "<revision_id>"
down_revision = "<上一版本revision>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级操作。"""
    # 添加列
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))

    # 创建索引
    op.create_index("ix_users_phone", "users", ["phone"])

    # 添加检查约束
    op.create_check_constraint(
        "ck_users_phone_format",
        "users",
        "phone IS NULL OR phone ~ '^[0-9]{10,20}$'"
    )


def downgrade() -> None:
    """回滚操作。"""
    op.drop_constraint("ck_users_phone_format", "users", type_="check")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
```

---

## 迁移最佳实践

### 1. 幂等性

迁移脚本必须支持重复执行和回滚：

```python
# ✅ 正确：幂等操作
op.create_table("users", ...)
op.add_column("users", sa.Column("email", ...))

# ❌ 错误：非幂等操作
op.create_table("users", ...)  # 重复执行会失败
```

### 2. 数据迁移

对于需要数据迁移的场景，使用 `op.execute()` 执行原始 SQL：

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("status", sa.String(20), server_default="active"))

    # 数据迁移
    op.execute("UPDATE users SET status = 'active' WHERE status IS NULL")

    # 修改默认值为 NULL（允许）
    op.alter_column("users", "status", server_default=None)
```

### 3. 大表注意事项

```python
def upgrade() -> None:
    # 大表添加列使用 NOT NULL + 默认值（PostgreSQL 11+）
    op.add_column("orders", sa.Column("total", sa.Numeric(10, 2), server_default="0"))

    # 对于需要立即加锁的操作，分两步：
    # 1. 添加可空列
    op.add_column("orders", sa.Column("new_column", sa.String(50), nullable=True))

    # 2. 后台迁移数据（应用层处理）
```

### 4. 多阶段迁移

对于复杂变更，分成多个迁移：

```
001_initial.py           # 创建基础表
002_add_xxx.py          # 添加新功能
003_migrate_xxx.py      # 数据迁移
004_cleanup_xxx.py      # 清理/优化
```

### 5. 禁止操作

- ❌ 不要修改已发布的迁移 `upgrade()` / `downgrade()`
- ❌ 不要删除其他迁移依赖的列
- ❌ 不要在生产环境测试回滚

---

## 故障排除

### 问题：password authentication failed

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"
```

**解决：** 设置正确的密码环境变量

```bash
export POSTGRES_PASSWORD=your_password
```

### 问题：database "xxx" does not exist

```
psycopg2.errors.InvalidCatalogName: database "xxx" does not exist
```

**解决：** 先创建数据库

```bash
docker exec -it <container_name> psql -U postgres -c "CREATE DATABASE sisys;"
```

### 问题：relation "xxx" already exists

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable) relation "xxx" already exists
```

**原因：** 迁移脚本非幂等，或已手动创建表。

**解决：**
1. 检查 `alembic_history` 表
2. 清理后重新执行：`poetry run alembic downgrade -1 && poetry run alembic upgrade head`

### 问题：SSL connection error

**解决：** 配置 SSL 或使用 `postgres://` 而非 `postgresql+asyncpg://`

```bash
export POSTGRES_HOST=localhost
```

### 问题：迁移卡住

**解决：** 检查是否有其他连接占用

```bash
# 查看活动连接
docker exec -it <container_name> psql -U postgres -d sisys -c "SELECT * FROM pg_stat_activity WHERE datname = 'sisys';"
```

---

## 生产环境部署

### 1. 部署前检查

```bash
# 1. 确保所有迁移已通过测试
poetry run alembic upgrade head

# 2. 检查迁移历史
poetry run alembic history

# 3. 生成 SQL 脚本审查
poetry run alembic upgrade head --sql > deploy_migration.sql
cat deploy_migration.sql
```

### 2. 生产环境变量

```bash
export POSTGRES_HOST=postgres.internal
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=sisys_prod
export POSTGRES_USERNAME=sisys
export POSTGRES_PASSWORD=<生产环境密码>
```

### 3. 部署流程

```bash
# 1. 备份数据库（必须）
docker exec <postgres_container> pg_dump -U postgres sisys_prod > backup_$(date +%Y%m%d).sql

# 2. 执行迁移
poetry run alembic upgrade head

# 3. 验证
poetry run alembic current

# 4. 检查表结构
docker exec <postgres_container> psql -U postgres -d sisys_prod -c "\dt"
```

### 4. 回滚流程

```bash
# 1. 回滚前确认
poetry run alembic history

# 2. 执行回滚
poetry run alembic downgrade -1

# 3. 验证
poetry run alembic current
```

### 5. CI/CD 集成

```yaml
# .gitea/workflows/deploy.yml 示例
- name: Run Database Migrations
  run: |
    cd deploy/postgresql/alembic
    export POSTGRES_HOST=${{ secrets.POSTGRES_HOST }}
    export POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}
    poetry run alembic upgrade head
```

---

## 核心表说明

| 表名 | 说明 | 关联 |
|------|------|------|
| `event_outbox` | 事务发件箱（Outbox Pattern） | 存储待发布事件 |
| `users` | 用户表 | `user_roles` → `roles` |
| `roles` | 角色表 | `user_roles` ← `users`, `role_permissions` → `permissions` |
| `permissions` | 权限表 | `role_permissions` ← `roles` |
| `user_roles` | 用户-角色关联表 | CASCADE 删除 |
| `role_permissions` | 角色-权限关联表 | CASCADE 删除 |

---

## 参考链接

- [Alembic 官方文档](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [PostgreSQL 文档](https://www.postgresql.org/docs/)
