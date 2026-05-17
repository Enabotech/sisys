"""MemoryGroupMemberModel 测试

验证 memory_group_members 表结构
"""

from __future__ import annotations

from sqlalchemy import inspect

from src.infrastructure.storage.postgresql.models.memory import MemoryGroupMemberModel


class TestMemoryGroupMemberModel:
    """MemoryGroupMemberModel 测试。"""

    def test_table_name(self):
        """表名应为 memory_group_members。"""
        assert MemoryGroupMemberModel.__tablename__ == "memory_group_members"

    def test_columns_exist(self):
        """所有必需列应存在。"""
        mapper = inspect(MemoryGroupMemberModel)
        columns = {c.name for c in mapper.columns}

        assert "group_id" in columns
        assert "user_id" in columns
        assert "role" in columns

    def test_group_id_is_string(self):
        """group_id 应为 String 类型。"""
        mapper = inspect(MemoryGroupMemberModel)
        group_id_col = mapper.columns["group_id"]
        assert group_id_col.type.__class__.__name__ == "String"

    def test_user_id_is_string(self):
        """user_id 应为 String 类型。"""
        mapper = inspect(MemoryGroupMemberModel)
        user_id_col = mapper.columns["user_id"]
        assert user_id_col.type.__class__.__name__ == "String"

    def test_role_is_string(self):
        """role 应为 String 类型。"""
        mapper = inspect(MemoryGroupMemberModel)
        role_col = mapper.columns["role"]
        assert role_col.type.__class__.__name__ == "String"

    def test_unique_constraint_on_group_id_user_id(self):
        """(group_id, user_id) 应有唯一约束。"""

        # 检查表上是否有复合唯一索引
        table = MemoryGroupMemberModel.__table__
        unique_indexes = [idx for idx in table.indexes if idx.unique and set(idx.columns.keys()) == {"group_id", "user_id"}]
        assert len(unique_indexes) == 1, (
            f"Expected unique index on (group_id, user_id), got: {[idx.columns.keys() for idx in table.indexes]}"
        )
