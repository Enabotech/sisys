"""AuditOutboxModel 模型单元测试

R5 留项 D11⑥ 清偿：mark_failed 错误消息按列宽截断——error_message 列为
String(1000)，超长错误串（如内嵌任意长 payload repr 的反序列化消息）在
PG 侧抛错不截断，未截断将使发布周期事务失败（与 event_outbox 侧 R3-F2
修复同款的对称防御）。

Run with:
    poetry run pytest tests/unit/infrastructure/storage/postgresql/models/test_audit_outbox_model.py -v
"""

from __future__ import annotations

from uuid import uuid4

from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel


class TestAuditOutboxModel:
    """AuditOutboxModel 行为契约。"""

    def test_mark_failed_truncates_long_error(self) -> None:
        """超长错误消息必须截断至列宽（防 VARCHAR(1000) 溢出炸事务）。"""
        record = AuditOutboxModel(event_id=uuid4(), payload={"k": "v"})
        record.mark_failed("x" * 2500)
        assert record.error_message is not None
        assert len(record.error_message) == 1000, "错误消息必须按 error_message 列宽截断"

    def test_mark_failed_normal_error_kept(self) -> None:
        """常规长度错误消息原样保留（截断不引入行为变化）。"""
        record = AuditOutboxModel(event_id=uuid4(), payload={})
        record.mark_failed("publish failed: connection refused")
        assert record.error_message == "publish failed: connection refused"
        assert record.retry_count == 1
        assert record.status == "failed"
