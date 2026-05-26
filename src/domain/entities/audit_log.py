"""领域层审计日志实体模块

定义审计日志领域实体，仅依赖标准库，无外部 ORM 框架
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AuditLog:
    """审计日志领域实体（不可变）.

    领域层核心实体，封装审计日志的业务逻辑
    仅依赖标准库，不依赖任何外部ORM框架
    """

    log_id: UUID
    timestamp: datetime
    actor: str
    action_type: str
    target_resource: str
    old_value: dict[str, Any] = field(default_factory=dict)
    new_value: dict[str, Any] = field(default_factory=dict)
    correction_level: int | None = None
    checksum: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.actor:
            raise ValueError("actor is required for AuditLog")
        if not self.action_type:
            raise ValueError("action_type is required for AuditLog")

    @classmethod
    def create(
        cls,
        actor: str,
        action_type: str,
        target_resource: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        correction_level: int | None = None,
        correlation_id: str | None = None,
    ) -> AuditLog:
        """创建审计日志实例，自动生成 ID 和时间戳

        Args:
            actor: 用户 ID 或系统组件标识
            action_type: 操作类型
            target_resource: 被操作资源
            old_value: 操作前状态
            new_value: 操作后状态
            correction_level: 纠正级别（L0-L3）
            correlation_id: 关联 ID

        Returns:
            AuditLog 新实例
        """
        return cls(
            log_id=uuid4(),
            timestamp=datetime.now(UTC),
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value=old_value or {},
            new_value=new_value or {},
            correction_level=correction_level,
        )

    def compute_checksum(self) -> str:
        """计算 SHA256 校验和用于完整性验证

        Returns:
            str: SHA256 hex digest
        """
        content = json.dumps(
            {
                "log_id": str(self.log_id),
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "actor": self.actor,
                "action_type": self.action_type,
                "target_resource": self.target_resource,
                "old_value": self.old_value,
                "new_value": self.new_value,
                "correction_level": self.correction_level,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_checksum(self) -> bool:
        """验证校验和是否匹配

        Returns:
            True 如果校验和匹配
        """
        if self.checksum is None:
            return False
        return self.checksum == self.compute_checksum()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示

        Returns:
            dict 包含所有审计字段
        """
        return {
            "log_id": str(self.log_id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "actor": self.actor,
            "action_type": self.action_type,
            "target_resource": self.target_resource,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "correction_level": self.correction_level,
            "checksum": self.checksum,
            "archived": self.archived,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
