"""领域层存储层级策略服务模块

根据数据特征和业务规则决定数据的存储层级
对应 architecture.md §11.2.11 验收标准：
- HOT: 访问频率 ≥100/周
- WARM: 访问频率 10-99/周
- COLD: 访问频率 1-9/周
- FROZEN: 访问频率 = 0 或 Checkpoint
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.ports.storage_enums import DataAccessPattern, StorageTier


@dataclass
class StorageDecision:
    """存储决策结果

    Attributes:
        tier: 存储层级
        access_pattern: 数据访问模式
        ttl_hours: 生存时间（小时），None 表示无过期
        compression_needed: 是否需要压缩
    """

    tier: StorageTier
    access_pattern: DataAccessPattern
    ttl_hours: int | None = None
    compression_needed: bool = False


class StoragePolicyService:
    """存储层级策略领域服务

    根据数据访问频率和内容特征决定存储层级，驱动 UnifiedStorageGateway
    执行分层写入

    Class Attributes:
        FREQUENT_THRESHOLD: 高频访问阈值（≥100/周 → HOT）
        OCCASIONAL_THRESHOLD: 中频访问阈值（10-99/周 → WARM）
        RARE_THRESHOLD: 低频访问阈值（1-9/周 → COLD）
        CHECKPOINT_RETENTION_DAYS: 检查点保留天数（7 年）
    """

    FREQUENT_THRESHOLD = 100  # ≥100/周 → HOT
    OCCASIONAL_THRESHOLD = 10  # 10-99/周 → WARM
    RARE_THRESHOLD = 1  # 1-9/周 → COLD
    CHECKPOINT_RETENTION_DAYS = 2555  # 7 年

    def decide_tier(
        self,
        access_frequency: int,
        content_size: int,
        is_checkpoint: bool = False,
    ) -> StorageDecision:
        """根据数据特征决定存储层级

        Args:
            access_frequency: 访问频率（过去 7 天访问次数）
            content_size: 内容大小（字节）
            is_checkpoint: 是否为检查点快照

        Returns:
            存储决策结果，包含层级、访问模式、TTL 和压缩需求
        """
        if is_checkpoint:
            return StorageDecision(
                tier=StorageTier.FROZEN,
                access_pattern=DataAccessPattern.ARCHIVED,
                compression_needed=True,
            )

        if access_frequency >= self.FREQUENT_THRESHOLD:
            return StorageDecision(
                tier=StorageTier.HOT,
                access_pattern=DataAccessPattern.FREQUENT,
                ttl_hours=24,
            )

        if access_frequency >= self.OCCASIONAL_THRESHOLD:
            return StorageDecision(
                tier=StorageTier.WARM,
                access_pattern=DataAccessPattern.OCCASIONAL,
            )

        if access_frequency >= self.RARE_THRESHOLD:
            return StorageDecision(
                tier=StorageTier.COLD,
                access_pattern=DataAccessPattern.RARE,
                compression_needed=content_size > 10000,
            )

        return StorageDecision(
            tier=StorageTier.FROZEN,
            access_pattern=DataAccessPattern.ARCHIVED,
            compression_needed=True,
        )
