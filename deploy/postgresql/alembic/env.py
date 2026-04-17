"""Alembic 环境配置。

自动从基础设施层收集 SQLAlchemy 模型 metadata，支持异步迁移。
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Build database URL from environment variables
def get_url():
    """从环境变量构建数据库 URL。"""
    username = os.getenv("POSTGRES_USERNAME", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DATABASE", "sisys")
    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    生成 SQL 脚本而不连接数据库。
    """
    from src.infrastructure.storage.postgresql.models import pg_registry

    url = config.get_main_option("sqlalchemy.url") or get_url()
    context.configure(
        url=url,
        target_metadata=pg_registry.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection, metadata):
    """执行迁移。"""
    context.configure(connection=connection, target_metadata=metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    使用真实数据库连接执行迁移。
    """
    from src.infrastructure.storage.postgresql.models import pg_registry

    # Build config dict with URL from environment variables
    cfg_dict = config.get_section(config.config_ini_section, {})
    cfg_dict["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        cfg_dict,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations, metadata=pg_registry.metadata)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
