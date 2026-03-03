"""
单元测试示例 - 验证测试框架配置。

这些测试用于验证 pytest 配置、fixture 和工具函数正常工作。
"""
# 导入 asyncio 用于异步测试
import asyncio
from datetime import UTC, datetime

import pytest


class TestFixtureConfiguration:
    """测试配置 fixture"""

    def test_test_config_fixture(self, test_config):
        """Given 测试配置 fixture，When 访问配置，Then 返回预期值"""
        # Assert
        assert "database_url" in test_config
        assert "redis_url" in test_config
        assert test_config["test_db_prefix"] == "test_"

    def test_project_root_fixture(self, project_root):
        """Given 项目根目录 fixture，When 访问，Then 返回正确路径"""
        # Assert
        assert project_root.exists()
        assert (project_root / "pyproject.toml").exists()

    def test_test_data_dir_fixture(self, test_data_dir):
        """Given 测试数据目录 fixture，When 访问，Then 返回正确路径"""
        # Assert
        assert test_data_dir.exists()
        assert test_data_dir.name == "data"


class TestMockObjects:
    """测试 Mock 对象"""

    @pytest.mark.asyncio
    async def test_mock_llm_router(self, mock_llm_router):
        """Given Mock LLM 路由器，When 调用 route，Then 返回模拟结果"""
        # Act
        result = await mock_llm_router.route()

        # Assert
        assert result["selected_model"] == "ollama/qwen2.5-7b"
        assert result["estimated_cost"] == 0.001
        mock_llm_router.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_repository(self, mock_repository):
        """Given Mock 仓储，When 调用方法，Then 返回模拟结果"""
        # Arrange
        mock_repository.get_by_id.return_value = {"id": 1, "name": "test"}

        # Act
        result = await mock_repository.get_by_id(1)

        # Assert
        assert result["id"] == 1
        mock_repository.get_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_mock_event_bus(self, mock_event_bus):
        """Given Mock 事件总线，When 发布事件，Then 成功调用"""
        # Act
        await mock_event_bus.publish("test.event", {"data": "value"})

        # Assert
        mock_event_bus.publish.assert_called_once_with("test.event", {"data": "value"})


class TestTimeUtilities:
    """测试时间工具"""

    def test_frozen_time(self, frozen_time):
        """Given 冻结时间 fixture，When 获取当前时间，Then 返回冻结时间"""
        # Act
        now = datetime.now(UTC)

        # Assert
        assert now.year == 2026
        assert now.month == 3
        assert now.day == 3
        assert now.hour == 10
        assert now.minute == 0

    def test_time_travel(self, time_travel):
        """Given 时间旅行工具，When 推进时间，Then 时间改变"""
        # Arrange
        # initial = datetime.now(UTC)

        # Act
        time_travel.move_to("2026-03-04 12:00:00")
        later = datetime.now(UTC)

        # Assert
        assert later.day == 4
        assert later.hour == 12


class TestAssertionHelpers:
    """测试断言辅助函数"""

    def test_assert_contains(self, assert_contains):
        """Given 包含断言，When 元素存在，Then 通过"""
        # Assert
        assert_contains([1, 2, 3], 2)
        assert_contains({"a": 1, "b": 2}, "a")

    def test_assert_not_contains(self, assert_not_contains):
        """Given 不包含断言，When 元素不存在，Then 通过"""
        # Assert
        assert_not_contains([1, 2, 3], 4)
        assert_not_contains({"a": 1}, "b")

    def test_assert_almost_equal(self, assert_almost_equal):
        """Given 近似相等断言，When 浮点数近似，Then 通过"""
        # Assert
        assert_almost_equal(0.1 + 0.2, 0.3, places=7)


class TestRandomDataGenerators:
    """测试随机数据生成器"""

    def test_random_string(self, random_string):
        """Given 随机字符串生成器，When 生成字符串，Then 返回预期格式"""
        # Act
        result = random_string(length=10)

        # Assert
        assert len(result) == 10
        assert result.isalnum()
        assert result.islower()

    def test_random_string_with_prefix(self, random_string):
        """Given 带前缀的随机字符串，When 生成，Then 包含前缀"""
        # Act
        result = random_string(length=8, prefix="test_")

        # Assert
        assert result.startswith("test_")
        assert len(result) == 13

    def test_random_email(self, random_email):
        """Given 随机邮箱生成器，When 生成邮箱，Then 返回有效格式"""
        # Act
        result = random_email()

        # Assert
        assert "@" in result
        assert result.endswith("@example.com")


class TestDataBuilder:
    """测试数据构建器"""

    def test_builder_with_id(self, test_data_builder, uuid_generator):
        """Given 数据构建器，When 设置 ID，Then 包含 ID"""
        # Arrange
        builder = test_data_builder()
        test_id = uuid_generator.next()

        # Act
        result = builder.with_id(test_id).build()

        # Assert
        assert result["id"] == test_id

    def test_builder_with_fields(self, test_data_builder):
        """Given 数据构建器，When 设置多个字段，Then 包含所有字段"""
        # Arrange
        builder = test_data_builder({"base": "value"})

        # Act
        result = builder.with_field("name", "test").with_field("status", "active").build()

        # Assert
        assert result["base"] == "value"
        assert result["name"] == "test"
        assert result["status"] == "active"


class TestAsyncSupport:
    """测试异步测试支持"""

    @pytest.mark.asyncio
    async def test_async_test_runs(self):
        """Given 异步测试，When 执行，Then 成功完成"""
        # Arrange
        await asyncio.sleep(0.01)

        # Assert
        assert True

    @pytest.mark.asyncio
    async def test_async_fixture(self, event_loop):
        """Given 异步 fixture，When 使用，Then 事件循环可用"""
        # Assert
        assert event_loop is not None
        assert not event_loop.is_closed()
