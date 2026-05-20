# PostgreSQL 仓储开发模板

> **版本**: v1.0.0
> **创建日期**: 2026-05-20
> **维护者**: Platform Team

---

## 概述

本文档定义 SISYS 系统中 PostgreSQL 仓储的标准开发模板。所有新建仓储必须遵循此模板。

---

## 核心规则

1. **无参构造** — 仓储不接收 session 参数，通过 `get_session()` 从 ContextVar 获取
2. **继承 PostgreSQLAdapter** — 复用泛型基类的 CRUD 实现
3. **禁止构造函数注入 session** — 除非需要非默认隔离级别（参考 AuditUnitOfWork）

---

## 标准仓储模板

### 1. 创建领域端口

```python
# src/domain/ports/some_repository.py
"""领域层 XXX 仓储端口模块"""

from typing import Protocol, runtime_checkable

from src.domain.ports.l2_rdb import L2RdbPort
from src.domain.entities.some_entity import SomeEntity


@runtime_checkable
class SomeRepositoryPort(L2RdbPort[SomeEntity], Protocol):
    """XXX 仓储端口协议"""

    async def find_by_name(self, name: str) -> SomeEntity | None:
        """按名称查找"""
        ...
```

### 2. 创建 SQLAlchemy Model

```python
# src/infrastructure/storage/postgresql/models.py (追加到现有文件)
# 或 src/infrastructure/storage/postgresql/models/some_model.py

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models import Base


class SomeModel(Base):
    """XXX SQLAlchemy 模型"""

    __tablename__ = "some_table"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ...其他字段
```

### 3. 创建仓储实现

```python
# src/infrastructure/storage/postgresql/repository/some_repository.py
"""基础设施层 XXX 仓储实现模块

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from uuid import UUID

from src.domain.entities.some_entity import SomeEntity
from src.domain.ports.some_repository import SomeRepositoryPort
from src.infrastructure.storage.postgresql.models.some_model import SomeModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)


class SomeRepository(PostgreSQLAdapter[SomeEntity, SomeModel], SomeRepositoryPort):
    """XXX 仓储实现

    继承 PostgreSQLAdapter 泛型基类，自动获得 CRUD 能力
    Session 通过 ContextVar 获取，无需构造器注入
    """

    pk_column = "id"  # 按需覆写主键列名（如 "memory_id"）

    def __init__(self) -> None:
        """初始化仓储。无参构造，session 由 ContextVar 提供。"""
        super().__init__(SomeModel)

    def _to_entity(self, model: SomeModel) -> SomeEntity:
        """ORM 模型 → 领域实体"""
        return SomeEntity(
            id=model.id,
            name=model.name,
            # ...
        )

    def _to_model(self, entity: SomeEntity) -> SomeModel:
        """领域实体 → ORM 模型"""
        return SomeModel(
            id=str(entity.id),
            name=entity.name,
            # ...
        )

    async def find_by_name(self, name: str) -> SomeEntity | None:
        """按名称查找（端口协议实现）"""
        from sqlalchemy import select

        stmt = select(SomeModel).where(SomeModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
```

### 4. 注册到 DI 容器

```python
# src/composition_root.py — bootstrap() 函数中追加

from src.domain.ports.some_repository import SomeRepositoryPort

register_port(
    name="some_repo",
    version="v1.0.0",
    interface=SomeRepositoryPort,
    impl="src.infrastructure.storage.postgresql.repository.some_repository.SomeRepository",
    module="src.infrastructure.storage.postgresql.repository.some_repository",
    lifetime=Lifetime.SCOPED,
    owner="platform-team",
)
```

### 5. 编写测试

```python
# tests/unit/infrastructure/storage/test_some_repository.py
"""XXX 仓储单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.session_context import with_session


@pytest.fixture
def mock_entity():
    """测试用领域实体"""
    from src.domain.entities.some_entity import SomeEntity
    return SomeEntity(id="test-id", name="test-name")


@pytest.mark.asyncio
async def test_save_entity(mock_entity):
    """测试保存实体"""
    mock_session = AsyncMock(spec=AsyncSession)

    async with with_session(mock_session):
        repo = SomeRepository()
        # 执行保存
        await repo.save(mock_entity)

    # 验证 flush 被调用
    mock_session.flush.assert_called()
```

---

## 检查清单

新建仓储时，确认以下各项：

- [ ] 领域端口继承 `L2RdbPort[TEntity]`，使用 `@runtime_checkable` 装饰
- [ ] 实现类继承 `PostgreSQLAdapter[TEntity, TModel]`，无参构造函数
- [ ] `_to_entity()` 和 `_to_model()` 已实现
- [ ] `pk_column` 已正确设置（默认 "id"）
- [ ] DI 注册使用模块路径字符串（非 lambda），`Lifetime.SCOPED`
- [ ] 测试使用 `with_session()` fixture，不直接导入 session_context 内部函数
- [ ] 文件头包含 Google 风格中文注释（文件头/类/关键方法）
