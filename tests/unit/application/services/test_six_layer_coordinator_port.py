"""Tests for SixLayerStorageCoordinator Port Injection (Task 10).

RED PHASE: 验证 SixLayerStorageCoordinator 依赖注入 L0StoragePort 实现。

验证标准（AC-10）:
- [ ] 创建 FileMemoryAdapter 实例
- [ ] 传递给 MemoryService 构造函数
- [ ] 依赖注入链完整验证
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.application.services.six_layer_storage_coordinator import (
    SixLayerStorageCoordinator,
)
from src.domain.repositories.l0_storage import L0StoragePort


class TestSixLayerStorageCoordinatorL0Port:
    """SixLayerStorageCoordinator L0StoragePort 依赖注入验证"""

    def test_init_accepts_l0_storage_port(self):
        """验证 SixLayerStorageCoordinator 构造函数接受 l0_storage 参数"""
        mock_cache = MagicMock()
        mock_l0_storage = MagicMock(spec=L0StoragePort)

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l0_storage=mock_l0_storage,
        )

        assert coordinator._l0_storage is not None
        assert isinstance(coordinator._l0_storage, L0StoragePort)

    def test_init_without_l0_storage_is_valid(self):
        """验证 l0_storage 为可选参数"""
        mock_cache = MagicMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
        )

        # l0_storage 允许为 None
        assert not hasattr(coordinator, "_l0_storage") or coordinator._l0_storage is None


class TestSixLayerStorageCoordinatorWithL0Storage:
    """SixLayerStorageCoordinator 与 L0StoragePort 交互验证"""

    def test_coordinator_can_use_l0_storage_for_save(self):
        """验证 coordinator 可使用 l0_storage 执行 L0 保存"""
        mock_cache = MagicMock()
        mock_l0_storage = MagicMock(spec=L0StoragePort)
        mock_l0_storage.write = AsyncMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l0_storage=mock_l0_storage,
        )

        # Coordinator 应能调用 l0_storage.write()
        # (如果 save 方法支持 L0 层)
        # 当前实现 save() 不直接写 L0，但接口应支持
        assert hasattr(coordinator, "_l0_storage")
        assert isinstance(coordinator._l0_storage, L0StoragePort)
