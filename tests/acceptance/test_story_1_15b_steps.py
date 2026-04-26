"""Gherkin 验收测试步骤实现 - Story 1.15b.

用于 tests/acceptance/test_story_1.15b.feature
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    pass

from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter
from src.infrastructure.storage.memory_index import MemoryIndex

scenarios("test_story_1_15b.feature")

# ==============================================================================
# Background Steps (背景步骤)
# ==============================================================================


@given("记忆系统已初始化")
def memory_system_initialized():
    """记忆系统已初始化（无操作，fixture 提供组件）"""
    pass


@given(parsers.parse('用户 "{user_name}" 已认证'))
def user_authenticated(user_name: str):
    """用户已认证（无操作，测试用户 ID 通过 fixture 提供）"""
    pass


@given(parsers.parse('群组 "{group_name}" 已创建'))
def group_created(group_name: str):
    """群组已创建（无操作，群组 ID 通过 fixture 提供）"""
    pass


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def test_user_id() -> str:
    """测试用户 ID fixture."""
    return str(uuid.uuid4())


@pytest.fixture
def test_group_id() -> str:
    """测试群组 ID fixture."""
    return str(uuid.uuid4())


@pytest.fixture
def memory_index(tmp_path) -> MemoryIndex:
    """MemoryIndex fixture for acceptance tests."""
    from src.infrastructure.config.memory import MemoryConfig

    config = MemoryConfig(memory_l0_path=str(tmp_path))
    return MemoryIndex(config)


@pytest.fixture
def file_adapter(tmp_path) -> FileMemoryAdapter:
    """FileMemoryAdapter fixture for acceptance tests."""
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter

    config = MemoryConfig(memory_l0_path=str(tmp_path))
    return FileMemoryAdapter(config)


@pytest.fixture
def created_memories(memory_index: MemoryIndex) -> list:
    """跟踪已创建的记忆条目."""
    return []


# ==============================================================================
# AC-1: L0 MEMORY.md 入口
# ==============================================================================


@given("用户创建记忆")
def create_memory(memory_index: MemoryIndex, file_adapter: FileMemoryAdapter, created_memories: list):
    """创建记忆"""
    memory_id = str(uuid.uuid4())
    entry = {
        "name": "test-memory",
        "type": "user",
        "memory_id": memory_id,
        "description": "测试记忆",
    }
    memory_index.update_entry(entry)
    # 写入 L0 文件
    content = "---\nname: test-memory\ndescription: 测试记忆\ntype: user\n---\n这是测试记忆内容。"
    file_adapter.write(memory_id, "user", content)
    created_memories.append(entry)


@given(parsers.parse('用户创建记忆 "{name}" 类型为 "{memory_type}"'))
def create_memory_named(name: str, memory_type: str, memory_index: MemoryIndex, created_memories: list):
    """创建指定名称和类型的记忆"""
    memory_id = str(uuid.uuid4())
    entry = {
        "name": name,
        "type": memory_type,
        "memory_id": memory_id,
        "description": f"{name} 的描述",
    }
    memory_index.update_entry(entry)
    created_memories.append(entry)


@when("记忆保存成功")
def memory_saved():
    """记忆保存成功（无操作，由 Given 步骤创建）"""
    pass


@then(parsers.parse('MEMORY.md 索引包含条目 "- [{name}]({path}) — {description}"'))
def check_index_entry(name: str, path: str, description: str, memory_index: MemoryIndex):
    """检查索引包含指定条目"""
    entries = memory_index.read_entries()
    # path like "user/uuid.md" - uuid is literal, path prefix should match
    path_parts = path.rsplit("/", 1)
    path_prefix = path_parts[0] if len(path_parts) == 2 else ""
    for e in entries:
        # 构建 entry 的完整 path
        entry_path = f"{e['type']}/{e['memory_id']}.md"
        if e["name"] == name and path_prefix in entry_path and e["description"] == description:
            return
    assert False, f"未找到索引条目: - [{name}]({path}) — {description}"


@when("读取 MEMORY.md 索引")
def read_memory_index(memory_index: MemoryIndex):
    """读取 MEMORY.md 索引"""
    return memory_index.read_entries()


@then("每行格式为 '- [Title](type/uuid.md) — description'")
def check_index_format(memory_index: MemoryIndex):
    """检查索引格式"""
    import re

    pattern = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")
    entries = memory_index.read_entries()
    assert len(entries) > 0, "索引为空"
    for entry in entries:
        path = f"{entry['type']}/{entry['memory_id']}.md"
        assert pattern.match(f"- [{entry['name']}]({path}) — {entry['description']}"), f"索引格式错误: {entry}"


@given(parsers.parse("创建 {count:d} 条记忆"))
def create_many_memories(count: int, memory_index: MemoryIndex, created_memories: list):
    """创建多条记忆"""
    for i in range(count):
        memory_id = str(uuid.uuid4())
        entry = {
            "name": f"memory-{i}",
            "type": "user",
            "memory_id": memory_id,
            "description": f"描述 {i}",
        }
        memory_index.update_entry(entry)
        created_memories.append(entry)


@then("MEMORY.md 索引正好 200 行")
def check_index_200_lines(memory_index: MemoryIndex):
    """检查索引正好 200 行"""
    entries = memory_index.read_entries()
    assert len(entries) == 200, f"索引行数应为 200，实际为 {len(entries)}"


@then("最新 200 条记忆被保留")
def check_latest_200_preserved(memory_index: MemoryIndex, created_memories: list):
    """检查最新 200 条记忆被保留"""
    entries = memory_index.read_entries()
    assert len(entries) == 200
    # 创建 200 条记忆时，最新 200 条就是全部（因为不超过 200 行不会截断）
    # 顺序按写入顺序：memory-0 到 memory-199
    assert "memory-0" in entries[0]["name"], f"第一条应该是 memory-0，实际是 {entries[0]['name']}"
    assert "memory-199" in entries[-1]["name"], f"最后一条应该是 memory-199，实际是 {entries[-1]['name']}"


# ==============================================================================
# AC-2: Private/Group 记忆分离
# ==============================================================================


@then(parsers.parse('记忆文件位于 "{path_pattern}"'))
def check_memory_file_path(path_pattern: str, memory_index: MemoryIndex):
    """检查记忆文件路径"""
    entries = memory_index.read_entries()
    assert len(entries) > 0, "索引为空"
    # 路径模式如 "user/" 或 "group/user/"
    for entry in entries:
        entry_path = f"{entry['type']}/{entry['memory_id']}.md"
        if entry.get("is_group"):
            entry_path = f"group/{entry_path}"
        assert path_pattern in entry_path, f"路径不匹配：期望 {path_pattern}，实际 {entry_path}"


@given(parsers.parse('用户 "{user_name}" 创建 Private 记忆 "{memory_name}"'))
def create_private_memory(user_name: str, memory_name: str, memory_index: MemoryIndex, created_memories: list):
    """创建 Private 记忆"""
    memory_id = str(uuid.uuid4())
    entry = {
        "name": memory_name,
        "type": "user",
        "memory_id": memory_id,
        "description": f"Private memory for {user_name}",
        "is_group": False,  # Private
    }
    memory_index.update_entry(entry)
    created_memories.append(entry)


@given(parsers.parse('用户创建 Group 记忆 "{memory_name}" 属于群组 "{group_name}"'))
def create_group_memory(memory_name: str, group_name: str, memory_index: MemoryIndex, created_memories: list):
    """创建 Group 记忆"""
    memory_id = str(uuid.uuid4())
    entry = {
        "name": memory_name,
        "type": "user",
        "memory_id": memory_id,
        "description": f"Group memory for {group_name}",
        "is_group": True,  # Group
    }
    memory_index.update_entry(entry)
    created_memories.append(entry)


@when(parsers.parse("其他用户尝试读取该记忆"))
def try_read_by_other_user():
    """其他用户尝试读取 - 待实现"""
    raise NotImplementedError("MemoryAccessControl 实现尚未完成")


@when(parsers.parse('用户 "{user_name}" 尝试读取该记忆'))
def try_read_by_user(user_name: str):
    """指定用户尝试读取 - 待实现"""
    raise NotImplementedError("MemoryAccessControl 实现尚未完成")


@then("读取被拒绝，抛出 MemoryAccessDeniedError")
def read_denied_error():
    """读取被拒绝（由 when 步骤抛出异常）"""
    pass


@then(parsers.parse('错误原因为 "{reason}"'))
def check_error_reason(reason: str, exc_info: pytest.ExceptionInfo):
    """检查错误原因"""
    assert exc_info.value.reason == reason


# ==============================================================================
# AC-3: 六层存储协同
# ==============================================================================


@then("L0 文件系统存在 .md 文件")
def check_l0_file_exists(memory_index: MemoryIndex):
    """检查 L0 文件系统存在 .md 文件"""
    from pathlib import Path

    entries = memory_index.read_entries()
    assert len(entries) > 0, "索引为空"
    for entry in entries:
        # 构建文件路径
        base_path = Path(memory_index.config.get_index_path()).parent
        memory_path = base_path / entry["type"] / f"{entry['memory_id']}.md"
        if entry.get("is_group"):
            memory_path = base_path / "group" / entry["type"] / f"{entry['memory_id']}.md"
        assert memory_path.exists(), f"记忆文件不存在: {memory_path}"


@then("Redis 存在缓存")
def check_redis_cache_exists():
    """检查 Redis 缓存存在 - 待实现"""
    raise NotImplementedError("RedisMemoryCache 实现尚未完成")


@then(parsers.parse("缓存 TTL 在 {min:d}-{max:d} 秒范围内"))
def check_ttl_range(min_ttl: int, max_ttl: int):
    """检查 TTL 范围 - 待实现"""
    raise NotImplementedError("RedisMemoryCache 实现尚未完成")


# ==============================================================================
# AC-5: 记忆操作触发索引与缓存
# ==============================================================================


@then("MemoryIndex 索引已更新")
def check_index_updated(memory_index: MemoryIndex):
    """检查索引已更新"""
    entries = memory_index.read_entries()
    assert len(entries) > 0, "索引未更新"


@then("Redis 缓存已写入")
def check_cache_written():
    """检查缓存已写入 - 待实现"""
    raise NotImplementedError("RedisMemoryCache 实现尚未完成")


@when("用户删除记忆")
def delete_memory():
    """删除记忆 - 待实现"""
    raise NotImplementedError("MemoryService 实现尚未完成")


@then("MemoryIndex 条目已移除")
def check_index_entry_removed():
    """检查索引条目已移除 - 待实现"""
    raise NotImplementedError("MemoryIndex 实现尚未完成")


@then("Redis 缓存已失效")
def check_cache_invalidated():
    """检查缓存已失效 - 待实现"""
    raise NotImplementedError("RedisMemoryCache 实现尚未完成")


# ==============================================================================
# AC-6: 性能要求
# ==============================================================================


@then(parsers.parse("Redis TTL 在 {min:d}-{max:d} 秒范围内"))
def check_redis_ttl_range(min_ttl: int, max_ttl: int):
    """检查 Redis TTL 范围 - 待实现"""
    raise NotImplementedError("RedisMemoryCache 实现尚未完成")


@then("L0 写入成功后 100ms 内 L2 写入完成")
def check_l0_l2_sync_latency():
    """检查 L0→L2 同步延迟 - 待实现"""
    raise NotImplementedError("SixLayerStorageCoordinator 实现尚未完成")


@then(parsers.parse("memory_metadata 记录全部存在"))
def check_metadata_records():
    """检查 metadata 记录 - 待实现"""
    raise NotImplementedError("MemoryMetadataRepository 实现尚未完成")


@then(parsers.parse("成功率 = {success_rate:d}%"))
def check_success_rate(success_rate: int):
    """检查成功率 - 待实现"""
    raise NotImplementedError("MemoryService 实现尚未完成")
