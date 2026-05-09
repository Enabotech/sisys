"""StoragePolicyService 单元测试。

验证存储层级策略服务正确实现。
参考 architecture.md §11.2.11 验收标准。
"""

from __future__ import annotations

import pytest

from src.domain.ports.storage_enums import DataAccessPattern, StorageTier
from src.domain.services.storage_tier_strategy import (
    StorageDecision,
    StoragePolicyService,
)


class TestStoragePolicyService:
    """测试存储层级策略服务。"""

    @pytest.fixture
    def service(self) -> StoragePolicyService:
        """创建 StoragePolicyService 实例。"""
        return StoragePolicyService()

    def test_decide_tier_hot_frequency(self, service: StoragePolicyService) -> None:
        """访问频率 >= 100/周 应返回 HOT 层。"""
        result = service.decide_tier(
            access_frequency=service.FREQUENT_THRESHOLD,
            content_size=1000,
        )
        assert result.tier == StorageTier.HOT
        assert result.access_pattern == DataAccessPattern.FREQUENT

    def test_decide_tier_hot_above_threshold(self, service: StoragePolicyService) -> None:
        """访问频率 > 100/周 应返回 HOT 层。"""
        result = service.decide_tier(
            access_frequency=service.FREQUENT_THRESHOLD + 50,
            content_size=1000,
        )
        assert result.tier == StorageTier.HOT

    def test_decide_tier_warm_frequency(self, service: StoragePolicyService) -> None:
        """访问频率 10-99/周 应返回 WARM 层。"""
        result = service.decide_tier(
            access_frequency=service.OCCASIONAL_THRESHOLD,
            content_size=1000,
        )
        assert result.tier == StorageTier.WARM
        assert result.access_pattern == DataAccessPattern.OCCASIONAL

    def test_decide_tier_warm_range(self, service: StoragePolicyService) -> None:
        """访问频率在 10-99 之间应返回 WARM 层。"""
        for freq in range(10, 100):
            result = service.decide_tier(access_frequency=freq, content_size=1000)
            assert result.tier == StorageTier.WARM

    def test_decide_tier_cold_frequency(self, service: StoragePolicyService) -> None:
        """访问频率 1-9/周 应返回 COLD 层。"""
        result = service.decide_tier(
            access_frequency=service.RARE_THRESHOLD,
            content_size=1000,
        )
        assert result.tier == StorageTier.COLD
        assert result.access_pattern == DataAccessPattern.RARE

    def test_decide_tier_cold_range(self, service: StoragePolicyService) -> None:
        """访问频率在 1-9 之间应返回 COLD 层。"""
        for freq in range(1, 10):
            result = service.decide_tier(access_frequency=freq, content_size=1000)
            assert result.tier == StorageTier.COLD

    def test_decide_tier_frozen_zero_access(self, service: StoragePolicyService) -> None:
        """访问频率 = 0 应返回 FROZEN 层。"""
        result = service.decide_tier(
            access_frequency=0,
            content_size=1000,
        )
        assert result.tier == StorageTier.FROZEN
        assert result.access_pattern == DataAccessPattern.ARCHIVED

    def test_decide_tier_checkpoint_frozen(self, service: StoragePolicyService) -> None:
        """检查点快照应强制 FROZEN 层。"""
        result = service.decide_tier(
            access_frequency=999,  # 即使高频率
            content_size=10000,
            is_checkpoint=True,
        )
        assert result.tier == StorageTier.FROZEN
        assert result.access_pattern == DataAccessPattern.ARCHIVED
        assert result.compression_needed is True

    def test_decide_tier_hot_has_ttl(self, service: StoragePolicyService) -> None:
        """HOT 层应有 TTL。"""
        result = service.decide_tier(
            access_frequency=service.FREQUENT_THRESHOLD,
            content_size=1000,
        )
        assert result.ttl_hours is not None
        assert result.ttl_hours == 24

    def test_decide_tier_warm_no_ttl(self, service: StoragePolicyService) -> None:
        """WARM 层应无 TTL。"""
        result = service.decide_tier(
            access_frequency=service.OCCASIONAL_THRESHOLD,
            content_size=1000,
        )
        assert result.ttl_hours is None

    def test_decide_tier_cold_small_content_no_compression(self, service: StoragePolicyService) -> None:
        """COLD 层小内容 (<=10KB) 不压缩。"""
        result = service.decide_tier(
            access_frequency=service.RARE_THRESHOLD,
            content_size=5000,  # < 10000
        )
        assert result.compression_needed is False

    def test_decide_tier_cold_large_content_compression(self, service: StoragePolicyService) -> None:
        """COLD 层大内容 (>10KB) 需压缩。"""
        result = service.decide_tier(
            access_frequency=service.RARE_THRESHOLD,
            content_size=15000,  # > 10000
        )
        assert result.compression_needed is True

    def test_decide_tier_frozen_compression(self, service: StoragePolicyService) -> None:
        """FROZEN 层需要压缩。"""
        result = service.decide_tier(
            access_frequency=0,
            content_size=1000,
        )
        assert result.compression_needed is True

    def test_frozen_checkpoint_retention_days(self, service: StoragePolicyService) -> None:
        """检查点保留 7 年 (2555天)。"""
        assert service.CHECKPOINT_RETENTION_DAYS == 2555

    def test_decision_fields_complete(self, service: StoragePolicyService) -> None:
        """StorageDecision 应包含所有必要字段。"""
        result = service.decide_tier(
            access_frequency=100,
            content_size=5000,
        )
        assert hasattr(result, "tier")
        assert hasattr(result, "access_pattern")
        assert hasattr(result, "ttl_hours")
        assert hasattr(result, "compression_needed")


class TestStorageDecisionValues:
    """测试 StorageDecision 值对象。"""

    def test_hot_decision_values(self) -> None:
        """HOT 层决策值正确。"""
        decision = StorageDecision(
            tier=StorageTier.HOT,
            access_pattern=DataAccessPattern.FREQUENT,
            ttl_hours=24,
            compression_needed=False,
        )
        assert decision.tier == StorageTier.HOT
        assert decision.access_pattern == DataAccessPattern.FREQUENT

    def test_cold_decision_with_compression(self) -> None:
        """COLD 决策支持压缩标志。"""
        decision = StorageDecision(
            tier=StorageTier.COLD,
            access_pattern=DataAccessPattern.RARE,
            compression_needed=True,
        )
        assert decision.compression_needed is True

    def test_frozen_decision_values(self) -> None:
        """FROZEN 层决策值正确。"""
        decision = StorageDecision(
            tier=StorageTier.FROZEN,
            access_pattern=DataAccessPattern.ARCHIVED,
            compression_needed=True,
        )
        assert decision.tier == StorageTier.FROZEN
        assert decision.access_pattern == DataAccessPattern.ARCHIVED
