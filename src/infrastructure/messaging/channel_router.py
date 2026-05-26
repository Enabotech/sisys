"""基础设施层通道路由模块

根据事件类型将领域事件路由到对应的传输通道（Redis 实时或 RabbitMQ 可靠），
领域层通过 EventPublisher 接口发布事件，不感知路由细节
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeliveryMode(Enum):
    """事件传输通道模式（基础设施层概念）

    注意：此枚举位于基础设施层，不属于领域层
    领域层通过事件类型的通道映射推断传输模式
    """

    # 仅实时通道（Redis Pub/Sub）- 可能丢失，低延迟
    REALTIME = "realtime"

    # 仅可靠通道（RabbitMQ + Outbox）- 保证最终一致
    RELIABLE = "reliable"


@dataclass
class ChannelMapping:
    """事件通道映射配置"""

    event_type: str
    redis_channel: str | None = None
    rabbitmq_routing_key: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.RELIABLE
    description: str = ""


class ChannelRouter:
    """通道路由器

    管理事件类型到通道的映射
    支持配置驱动和运行时覆盖
    """

    # 预定义映射（Story 1.3 规范）
    #
    # 优先级：configs/event_channels.yaml > DEFAULT_MAPPINGS
    # - DEFAULT_MAPPINGS: 编译时 baseline，确保 YAML 缺失/不完整时系统可用
    # - event_channels.yaml: 运行时主配置，支持多环境差异化和运维独立调整
    # 新增事件应同时更新两处，保持同步
    DEFAULT_MAPPINGS: dict[str, ChannelMapping] = {
        # REALTIME 事件（5个）
        "AutoExecuted": ChannelMapping(
            event_type="AutoExecuted",
            redis_channel="sisys:rt:auto_executed",
            delivery_mode=DeliveryMode.REALTIME,
            description="自动化执行完成",
        ),
        "AutoTriggered": ChannelMapping(
            event_type="AutoTriggered",
            redis_channel="sisys:rt:auto_triggered",
            delivery_mode=DeliveryMode.REALTIME,
            description="触发事件，实时通知",
        ),
        "AutoRouted": ChannelMapping(
            event_type="AutoRouted",
            redis_channel="sisys:rt:auto_routed",
            delivery_mode=DeliveryMode.REALTIME,
            description="路由决策完成",
        ),
        "HeartbeatTriggered": ChannelMapping(
            event_type="HeartbeatTriggered",
            redis_channel="sisys:rt:heartbeat_triggered",
            delivery_mode=DeliveryMode.REALTIME,
            description="心跳触发",
        ),
        "RoutingDecided": ChannelMapping(
            event_type="RoutingDecided",
            redis_channel="sisys:rt:routing_decided",
            delivery_mode=DeliveryMode.REALTIME,
            description="路由决策完成",
        ),
        # RELIABLE 事件（22个）
        "DocumentProcessed": ChannelMapping(
            event_type="DocumentProcessed",
            redis_channel="sisys:rt:document_processed",
            rabbitmq_routing_key="sisys.events.reliable.document_processed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="文档处理完成",
        ),
        "MemoryChanged": ChannelMapping(
            event_type="MemoryChanged",
            rabbitmq_routing_key="sisys.events.reliable.memory_changed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="记忆变更",
        ),
        "CheckpointReached": ChannelMapping(
            event_type="CheckpointReached",
            rabbitmq_routing_key="sisys.events.reliable.checkpoint_reached",
            delivery_mode=DeliveryMode.RELIABLE,
            description="检查点到达",
        ),
        "AuditEvent": ChannelMapping(
            event_type="AuditEvent",
            rabbitmq_routing_key="audit.audit_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="审计事件",
        ),
        "ToolExecuted": ChannelMapping(
            event_type="ToolExecuted",
            rabbitmq_routing_key="sisys.events.reliable.tool_executed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="工具执行完成",
        ),
        "AgentDecided": ChannelMapping(
            event_type="AgentDecided",
            rabbitmq_routing_key="sisys.events.reliable.agent_decided",
            delivery_mode=DeliveryMode.RELIABLE,
            description="Agent决策完成",
        ),
        "CheckpointRecovered": ChannelMapping(
            event_type="CheckpointRecovered",
            rabbitmq_routing_key="sisys.events.reliable.checkpoint_recovered",
            delivery_mode=DeliveryMode.RELIABLE,
            description="检查点恢复",
        ),
        "IsolationLevelSwitched": ChannelMapping(
            event_type="IsolationLevelSwitched",
            rabbitmq_routing_key="sisys.events.reliable.isolation_level_switched",
            delivery_mode=DeliveryMode.RELIABLE,
            description="隔离级别切换",
        ),
        "CorrectionApproved": ChannelMapping(
            event_type="CorrectionApproved",
            rabbitmq_routing_key="sisys.events.reliable.correction_approved",
            delivery_mode=DeliveryMode.RELIABLE,
            description="纠正审批通过",
        ),
        "StrategicDeviationWarning": ChannelMapping(
            event_type="StrategicDeviationWarning",
            rabbitmq_routing_key="sisys.events.reliable.strategic_deviation_warning",
            delivery_mode=DeliveryMode.RELIABLE,
            description="战略偏差警告",
        ),
        "MFAChallengeIssuedEvent": ChannelMapping(
            event_type="MFAChallengeIssuedEvent",
            rabbitmq_routing_key="sisys.events.reliable.mfa_challenge_issued_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="MFA挑战发出",
        ),
        "IntrusionDetectedEvent": ChannelMapping(
            event_type="IntrusionDetectedEvent",
            rabbitmq_routing_key="sisys.events.reliable.intrusion_detected_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="入侵检测",
        ),
        "DataIntegrityViolationEvent": ChannelMapping(
            event_type="DataIntegrityViolationEvent",
            rabbitmq_routing_key="sisys.events.reliable.data_integrity_violation_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="数据完整性违规",
        ),
        "SensitiveDataDetected": ChannelMapping(
            event_type="SensitiveDataDetected",
            rabbitmq_routing_key="sisys.events.reliable.sensitive_data_detected",
            delivery_mode=DeliveryMode.RELIABLE,
            description="敏感数据检测",
        ),
        "CrossBorderTransferRequested": ChannelMapping(
            event_type="CrossBorderTransferRequested",
            rabbitmq_routing_key="sisys.events.reliable.cross_border_transfer_requested",
            delivery_mode=DeliveryMode.RELIABLE,
            description="跨境传输请求",
        ),
        "DataSovereigntyViolation": ChannelMapping(
            event_type="DataSovereigntyViolation",
            rabbitmq_routing_key="sisys.events.reliable.data_sovereignty_violation",
            delivery_mode=DeliveryMode.RELIABLE,
            description="数据主权违规",
        ),
        "PIPLDataAccessRequested": ChannelMapping(
            event_type="PIPLDataAccessRequested",
            rabbitmq_routing_key="sisys.events.reliable.pipl_data_access_requested",
            delivery_mode=DeliveryMode.RELIABLE,
            description="个人信息保护法数据访问请求",
        ),
        "SagaStatusChanged": ChannelMapping(
            event_type="SagaStatusChanged",
            rabbitmq_routing_key="sisys.events.reliable.saga_status_changed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="Saga状态变更",
        ),
        "RAGIndexed": ChannelMapping(
            event_type="RAGIndexed",
            rabbitmq_routing_key="sisys.events.reliable.rag_indexed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="RAG索引完成",
        ),
        "ReportGenerated": ChannelMapping(
            event_type="ReportGenerated",
            rabbitmq_routing_key="sisys.events.reliable.report_generated",
            delivery_mode=DeliveryMode.RELIABLE,
            description="报告生成完成",
        ),
        "WorkflowSubmitted": ChannelMapping(
            event_type="WorkflowSubmitted",
            rabbitmq_routing_key="sisys.events.reliable.workflow_submitted",
            delivery_mode=DeliveryMode.RELIABLE,
            description="工作流提交完成",
        ),
        "BackupCompletedEvent": ChannelMapping(
            event_type="BackupCompletedEvent",
            rabbitmq_routing_key="sisys.events.reliable.backup_completed_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="备份完成",
        ),
        "EncryptionKeyRotatedEvent": ChannelMapping(
            event_type="EncryptionKeyRotatedEvent",
            rabbitmq_routing_key="sisys.events.reliable.encryption_key_rotated_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="加密密钥轮换完成",
        ),
        # Crawler 事件
        "CrawlCompleted": ChannelMapping(
            event_type="CrawlCompleted",
            redis_channel="sisys:rt:crawl_completed",
            rabbitmq_routing_key="sisys.events.reliable.crawl_completed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="爬取任务完成",
        ),
        "CrawlFailed": ChannelMapping(
            event_type="CrawlFailed",
            redis_channel="sisys:rt:crawl_failed",
            rabbitmq_routing_key="sisys.events.reliable.crawl_failed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="爬取任务失败",
        ),
        "FileCrawled": ChannelMapping(
            event_type="FileCrawled",
            redis_channel="sisys:rt:file_crawled",
            rabbitmq_routing_key="sisys.events.reliable.file_crawled",
            delivery_mode=DeliveryMode.RELIABLE,
            description="单文件爬取完成",
        ),
    }

    def __init__(self, load_defaults: bool = True) -> None:
        """初始化路由器

        Args:
            load_defaults: 是否加载默认映射。False 用于测试场景
        """
        self._mappings: dict[str, ChannelMapping] = {}
        self._overrides: dict[str, DeliveryMode] = {}
        if load_defaults:
            self._init_defaults()

    def _init_defaults(self) -> None:
        """初始化默认映射"""
        for mapping in self.DEFAULT_MAPPINGS.values():
            self._mappings[mapping.event_type] = mapping

    def get_mapping(self, event_type: str) -> ChannelMapping | None:
        """获取事件通道映射

        Args:
            event_type: 事件类型名称

        Returns:
            对应的 ChannelMapping，若未配置则返回 None
        """
        return self._mappings.get(event_type)

    def get_delivery_mode(self, event_type: str) -> DeliveryMode:
        """获取事件的传输模式（支持运行时覆盖）

        Args:
            event_type: 事件类型名称

        Returns:
            对应的 DeliveryMode，默认为 RELIABLE
        """
        if mode := self._overrides.get(event_type):
            return mode
        mapping = self._mappings.get(event_type)
        return mapping.delivery_mode if mapping else DeliveryMode.RELIABLE

    def set_override(self, event_type: str, mode: DeliveryMode) -> None:
        """运行时覆盖传输模式

        注意：此方法仅限启动阶段调用，运行时禁用

        Args:
            event_type: 事件类型名称
            mode: 要设置的传输模式
        """
        # Copy-on-write: 创建新 dict 并原子替换引用
        new_overrides = dict(self._overrides)
        new_overrides[event_type] = mode
        self._overrides = new_overrides
        logger.info("Delivery mode override: %s -> %s", event_type, mode.value)

    def register(self, mapping: ChannelMapping) -> None:
        """注册事件通道映射

        注意：此方法仅限启动阶段调用，运行时禁用

        Args:
            mapping: 事件通道映射配置
        """
        # Copy-on-write: 创建新 dict 并原子替换引用
        new_mappings = dict(self._mappings)
        new_mappings[mapping.event_type] = mapping
        self._mappings = new_mappings
        logger.info("Registered channel mapping for: %s", mapping.event_type)

    def get_redis_channel(self, event_type: str) -> str | None:
        """获取 Redis 通道名

        Args:
            event_type: 事件类型名称

        Returns:
            Redis 通道名，若未配置则返回 None
        """
        mapping = self._mappings.get(event_type)
        return mapping.redis_channel if mapping else None

    def get_rabbitmq_routing_key(self, event_type: str) -> str | None:
        """获取 RabbitMQ 路由键

        Args:
            event_type: 事件类型名称

        Returns:
            RabbitMQ 路由键，若未配置则返回 None
        """
        mapping = self._mappings.get(event_type)
        return mapping.rabbitmq_routing_key if mapping else None

    @classmethod
    def create_for_testing(cls) -> ChannelRouter:
        """创建测试用路由器（无默认映射）

        Returns:
            不含默认映射的 ChannelRouter 实例
        """
        return cls(load_defaults=False)
