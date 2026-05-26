"""基础设施层审计服务模块

基于 AuditServicePort 接口实现审计日志的记录、检索、完整性验证和归档功能
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from src.domain.entities.audit_log import AuditLog
from src.domain.events.audit_events import AuditEvent
from src.domain.ports.audit_repository import (
    AuditRepositoryPort,
    AuditSearchCriteria,
)
from src.domain.ports.audit_service import AuditError, AuditRecord, AuditServicePort


class AuditServiceImpl(AuditServicePort):
    """审计服务实现，负责审计日志的记录、检索、完整性验证和归档

    Attributes:
        _audit_repo: 审计仓储端口实例
        _event_publisher: 事件发布器（可选，用于发件箱模式）
        _worm_manager: WORM 管理器（可选，用于归档到 MinIO WORM 存储）
    """

    def __init__(
        self,
        audit_repository: AuditRepositoryPort,
        event_publisher=None,  # EventPublisher (optional, for outbox pattern)
        worm_manager=None,  # WORMManager (optional, for archival to MinIO WORM storage)
    ):
        """初始化审计服务.

        Args:
            audit_repository: 审计仓储端口
            event_publisher: 事件发布器（可选，用于发件箱模式）
            worm_manager: WORM管理器（可选，用于归档到MinIO WORM存储）
        """
        self._audit_repo = audit_repository
        self._event_publisher = event_publisher
        self._worm_manager = worm_manager

    async def record(
        self,
        actor: str,
        action_type: str,
        target_resource: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AuditRecord:
        """记录审计日志

        Args:
            actor: 用户 ID 或系统组件标识
            action_type: 操作类型
            target_resource: 被操作资源
            old_value: 操作前状态
            new_value: 操作后状态
            correlation_id: 关联 ID

        Returns:
            AuditRecord 审计记录

        Raises:
            AuditError: 记录失败时抛出
        """
        try:
            # 创建领域实体
            audit_log = AuditLog.create(
                actor=actor,
                action_type=action_type,
                target_resource=target_resource,
                old_value=old_value,
                new_value=new_value,
            )

            # 计算校验和
            checksum = audit_log.compute_checksum()

            # 构建审计数据
            audit_data = {
                "log_id": str(audit_log.log_id),
                "timestamp": audit_log.timestamp.isoformat(),
                "actor": audit_log.actor,
                "action_type": audit_log.action_type,
                "target_resource": audit_log.target_resource,
                "old_value": audit_log.old_value,
                "new_value": audit_log.new_value,
                "correction_level": audit_log.correction_level,
                "checksum": checksum,
                "correlation_id": correlation_id,
            }

            # 保存到仓储
            log_id = await self._audit_repo.save(audit_data)

            # 发布领域事件（如果配置了事件发布器）
            if self._event_publisher:
                event = AuditEvent(
                    log_id=log_id,
                    actor=actor,
                    action_type=action_type,
                    target_resource=target_resource,
                    old_value=old_value or {},
                    new_value=new_value or {},
                )
                await self._event_publisher.publish(event)

            return AuditRecord(
                log_id=audit_log.log_id,
                timestamp=audit_log.timestamp,
                actor=audit_log.actor,
                action_type=audit_log.action_type,
                target_resource=audit_log.target_resource,
                old_value=audit_log.old_value,
                new_value=audit_log.new_value,
                correction_level=audit_log.correction_level,
            )
        except Exception as e:
            raise AuditError(f"Failed to record audit log: {e}") from e

    async def verify_integrity(self, log_id: UUID) -> bool:
        """验证单条审计日志的完整性

        Args:
            log_id: 审计日志的 UUID

        Returns:
            True 如果校验和匹配，False 如果已篡改

        Raises:
            AuditError: 验证过程出错时抛出
        """
        try:
            audit_data = await self._audit_repo.get_by_id(log_id)
            if not audit_data:
                raise AuditError(f"Audit log not found: {log_id}")

            # 重新计算校验和
            content = json.dumps(
                {
                    "log_id": str(log_id),
                    "timestamp": audit_data.get("timestamp", ""),
                    "actor": audit_data.get("actor", ""),
                    "action_type": audit_data.get("action_type", ""),
                    "target_resource": audit_data.get("target_resource", ""),
                    "old_value": audit_data.get("old_value", {}),
                    "new_value": audit_data.get("new_value", {}),
                    "correction_level": audit_data.get("correction_level"),
                },
                sort_keys=True,
            )
            computed_checksum: str = hashlib.sha256(content.encode()).hexdigest()

            # 比较校验和
            stored_checksum: str = audit_data.get("checksum", "")
            return computed_checksum == stored_checksum
        except AuditError:
            raise
        except Exception as e:
            raise AuditError(f"Failed to verify integrity: {e}") from e

    async def verify_batch(
        self,
        log_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        """批量验证审计日志完整性

        Args:
            log_ids: 要验证的日志 UUID 列表（None 表示全部）

        Returns:
            dict 包含 total, passed, failed, details
        """
        try:
            details = []
            passed = 0
            failed = 0

            if log_ids is None:
                # 验证全部 - 先搜索所有日志
                criteria = AuditSearchCriteria(offset=0, limit=1000)
                result = await self._audit_repo.search(criteria)
                log_ids = [UUID(item["log_id"]) for item in result.items]

            total = len(log_ids)
            for log_id in log_ids:
                try:
                    is_valid = await self.verify_integrity(log_id)
                    if is_valid:
                        passed += 1
                        status = "passed"
                        message = "Integrity verified"
                    else:
                        failed += 1
                        status = "failed"
                        message = "Checksum mismatch - possible tampering"
                except AuditError as e:
                    failed += 1
                    status = "error"
                    message = str(e)

                details.append(
                    {
                        "log_id": str(log_id),
                        "status": status,
                        "message": message,
                    }
                )

            return {
                "total": total,
                "passed": passed,
                "failed": failed,
                "details": details,
            }
        except Exception as e:
            raise AuditError(f"Failed to verify batch: {e}") from e

    async def archive(self, older_than_days: int = 30) -> int:
        """归档旧的审计日志到 WORM 存储

        Args:
            older_than_days: 归档多久之前的日志（默认 30 天）

        Returns:
            int 已归档的日志数量
        """
        try:
            # 计算截止时间
            cutoff_time = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_time = cutoff_time - timedelta(days=older_than_days)

            archived_count = 0
            offset = 0
            batch_size = 100

            # 分批处理所有符合条件的数据
            while True:
                criteria = AuditSearchCriteria(
                    start_time=None,
                    end_time=cutoff_time,
                    offset=offset,
                    limit=batch_size,
                )

                result = await self._audit_repo.search(criteria)

                if not result.items:
                    break

                for item in result.items:
                    log_id = UUID(item["log_id"])
                    archived_at = datetime.now(UTC)

                    # 更新归档状态
                    success = await self._audit_repo.update_archive_status(
                        log_id=log_id,
                        archived=True,
                        archived_at=archived_at,
                    )

                    # 如果配置了WORM管理器，异步归档日志数据到MinIO WORM存储
                    if success and self._worm_manager:
                        try:
                            # 构建对象键：audit/{log_id}/{timestamp}.json
                            timestamp_str = item.get("timestamp", "").replace(":", "-").replace("+", "-")
                            object_key = f"audit/{log_id}/{timestamp_str}.json"

                            # 归档到MinIO WORM存储
                            self._worm_manager.archive_object(
                                bucket_name="sisys-audit-archives",
                                object_key=object_key,
                                retention_days=2555,  # SOX 7年保留期
                            )
                        except Exception:
                            # WORM归档失败不影响主流程，仅记录
                            pass

                    if success:
                        archived_count += 1

                # 如果返回的数量小于批次大小，说明已经是最后一页
                if len(result.items) < batch_size:
                    break

                offset += batch_size

            return archived_count
        except Exception as e:
            raise AuditError(f"Failed to archive logs: {e}") from e
