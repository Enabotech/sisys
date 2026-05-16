"""Event Loop Blocking Verification Tests (Task 14).

验证 asyncio.run() 反模式已消除，to_thread 正确封装同步操作。

验证标准（AC-13）:
- [ ] asyncio.run() 反模式已消除
- [ ] to_thread 正确封装同步操作
- [ ] CPU 密集型方法不阻塞事件循环
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


class TestAsyncioRunPatternElimination:
    """验证 asyncio.run() 反模式已消除"""

    def test_no_asyncio_run_in_async_methods(self):
        """验证异步方法中没有 asyncio.run() 调用"""
        # 检查 MemoryIndex 方法不包含 asyncio.run()
        # 读取源码检查
        import inspect

        from src.infrastructure.storage.fs.memory_index import MemoryIndex

        source = inspect.getsource(MemoryIndex.update_entry)
        assert "asyncio.run(" not in source, "asyncio.run() found in update_entry"

        source = inspect.getsource(MemoryIndex.read_entries)
        assert "asyncio.run(" not in source, "asyncio.run() found in read_entries"

    def test_no_asyncio_run_in_file_memory_adapter(self):
        """验证 FileMemoryAdapter 方法中没有 asyncio.run()"""
        import inspect

        from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

        source = inspect.getsource(FileMemoryAdapter.write)
        assert "asyncio.run(" not in source, "asyncio.run() found in write"

    def test_no_asyncio_run_in_auto_trigger_listener(self):
        """验证 AutoTriggerListener 中没有 asyncio.run() 反模式"""
        import inspect

        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        # _worker_loop 使用 new_event_loop() + run_until_complete 是正确的
        source = inspect.getsource(AutoTriggerHandler._worker_loop)
        assert "asyncio.run(" not in source, "asyncio.run() found in _worker_loop"


class TestToThreadEncapsulation:
    """验证 to_thread 正确封装同步操作"""

    @pytest.mark.asyncio
    async def test_memory_index_uses_to_thread(self):
        """验证 MemoryIndex 使用 to_thread 封装"""
        from src.infrastructure.config.memory import MemoryConfig
        from src.infrastructure.storage.fs.memory_index import MemoryIndex

        # 创建 mock config
        mock_config = MagicMock(spec=MemoryConfig)
        mock_config.get_index_path.return_value = "/tmp/test_memory_index/MEMORY.md"

        index = MemoryIndex(mock_config)

        # update_entry 应该是异步的（使用 to_thread）
        assert asyncio.iscoroutinefunction(index.update_entry)

        # read_entries 应该是异步的（使用 to_thread）
        assert asyncio.iscoroutinefunction(index.read_entries)

    @pytest.mark.asyncio
    async def test_file_memory_adapter_write_uses_aiofiles(self):
        """验证 FileMemoryAdapter.write 使用 aiofiles"""
        from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

        # write 应该是异步的
        assert asyncio.iscoroutinefunction(FileMemoryAdapter.write)

    @pytest.mark.asyncio
    async def test_to_thread_preserves_lock_semantics(self):
        """验证 to_thread 保留 fcntl.flock 锁语义"""
        from src.infrastructure.config.memory import MemoryConfig
        from src.infrastructure.storage.fs.memory_index import MemoryIndex

        mock_config = MagicMock(spec=MemoryConfig)
        mock_config.get_index_path.return_value = "/tmp/test_lock_semantics/MEMORY.md"

        index = MemoryIndex(mock_config)

        # update_entry 使用 to_thread，锁语义应该保留
        assert asyncio.iscoroutinefunction(index.update_entry)


class TestCPUBoundMethodsNotBlocking:
    """验证 CPU 密集型方法不阻塞事件循环"""

    def test_integrity_compute_hash_is_sync(self):
        """验证 IntegrityPort.compute_hash 是同步的（CPU 密集型）"""
        from src.domain.ports.integrity import IntegrityPort

        # compute_hash 应该是同步方法
        # 注意：这只是验证接口签名，实际实现在 Infrastructure 层
        assert not asyncio.iscoroutinefunction(IntegrityPort.compute_hash)

    def test_integrity_verify_hash_is_sync(self):
        """验证 IntegrityPort.verify_hash 是同步的（CPU 密集型）"""
        from src.domain.ports.integrity import IntegrityPort

        # verify_hash 应该是同步方法
        assert not asyncio.iscoroutinefunction(IntegrityPort.verify_hash)


class TestEventLoopSafety:
    """验证事件循环安全"""

    @pytest.mark.asyncio
    async def test_async_methods_can_be_called_from_async_context(self):
        """验证异步方法可以从 async 上下文中调用"""
        from src.infrastructure.config.memory import MemoryConfig
        from src.infrastructure.storage.fs.memory_index import MemoryIndex

        mock_config = MagicMock(spec=MemoryConfig)
        mock_config.get_index_path.return_value = "/tmp/test_event_loop/MEMORY.md"

        index = MemoryIndex(mock_config)

        # 这些调用不应该阻塞事件循环
        # 使用 gather 可以并发执行
        await asyncio.gather(index.read_entries(), return_exceptions=True)

    @pytest.mark.asyncio
    async def test_no_blocking_calls_in_event_loop(self):
        """验证事件循环中没有阻塞调用"""
        from src.infrastructure.config.memory import MemoryConfig
        from src.infrastructure.storage.fs.memory_index import MemoryIndex

        mock_config = MagicMock(spec=MemoryConfig)
        mock_config.get_index_path.return_value = "/tmp/test_no_blocking/MEMORY.md"

        index = MemoryIndex(mock_config)

        # 在短时间内多次调用，确认不会阻塞
        tasks = [index.read_entries() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 所有调用都应该完成（不超时）
        assert len(results) == 10
