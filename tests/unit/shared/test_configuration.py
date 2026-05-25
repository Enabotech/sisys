"""
单元测试示例 - 验证测试框架配置

这些测试用于验证 pytest 配置、fixture 和工具函数正常工作
"""

# 导入 asyncio 用于异步测试
import asyncio


class TestAsyncSupport:
    """测试异步测试支持"""

    async def test_async_test_runs(self):
        """Given 异步测试，When 执行，Then 成功完成"""
        # Arrange
        await asyncio.sleep(0.01)

        # Assert
        assert True

    async def test_async_fixture(self, event_loop):
        """Given 异步 fixture，When 使用，Then 事件循环可用"""
        # Assert
        assert event_loop is not None
        assert not event_loop.is_closed()
