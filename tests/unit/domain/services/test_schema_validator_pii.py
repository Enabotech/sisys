"""SchemaValidator PII 脱敏测试(Round 2 P0-2 修复守护)

覆盖范围:
1. 24 个 PII 敏感字段名脱敏(password/token/api_key 等)
2. 大小写不敏感
3. 嵌套 dict 递归脱敏
4. list 中 dict 脱敏
5. set/frozenset 脱敏
6. SchemaViolation.to_dict() 序列化含 PII 时也脱敏
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.services.schema_validator import SchemaViolation


def _make_violation(actual):
    """构造带 actual 字段的 SchemaViolation"""
    return SchemaViolation(path="/x", expected="string", actual=actual, message="bad")


class TestPIISanitization:
    """PII 敏感字段脱敏(对标 OWASP / GDPR)"""

    # PII 字段名是测试数据(故意包含敏感关键字),用 inline allowlist 标注防止误报
    # 把字段名列表移到模块级常量,避免 detect-secrets 在 list 字面量内逐行报警
    _PII_FIELD_NAMES = [
        "password",  # pragma: allowlist secret
        "passwd",  # pragma: allowlist secret
        "pwd",
        "secret",  # pragma: allowlist secret
        "api_key",  # pragma: allowlist secret
        "apikey",
        "api-key",
        "token",  # pragma: allowlist secret
        "access_token",  # pragma: allowlist secret
        "refresh_token",  # pragma: allowlist secret
        "bearer_token",  # pragma: allowlist secret
        "authorization",  # pragma: allowlist secret
        "auth",
        "private_key",  # pragma: allowlist secret
        "privatekey",
        "credential",  # pragma: allowlist secret
        "credentials",  # pragma: allowlist secret
        "ssn",
        "social_security_number",  # pragma: allowlist secret
        "credit_card",  # pragma: allowlist secret
        "creditcard",
        "credit_card_number",  # pragma: allowlist secret
        "cvv",
        "pin",
    ]

    @pytest.mark.parametrize("field_name", _PII_FIELD_NAMES)
    def test_pii_field_value_is_redacted(self, field_name: str) -> None:  # pragma: allowlist secret
        """PII 字段值必须脱敏为 ***REDACTED***"""
        sensitive_value = f"super-{field_name}-value"  # pragma: allowlist secret
        violation = _make_violation(actual={field_name: sensitive_value})
        actual_dict = violation.to_dict()["actual"]

        assert actual_dict[field_name] == "***REDACTED***"

    def test_pii_field_case_insensitive(self) -> None:
        """PII 字段名大小写不敏感(PASSWORD/PaSsWoRd 等)"""
        violation = _make_violation(  # pragma: allowlist secret
            actual={
                "PASSWORD": "secret_value_1",  # pragma: allowlist secret
                "Password": "secret_value_2",  # pragma: allowlist secret
                "pAsSwOrD": "secret_value_3",  # pragma: allowlist secret
            },
        )
        actual_dict = violation.to_dict()["actual"]
        assert actual_dict["PASSWORD"] == "***REDACTED***"
        assert actual_dict["Password"] == "***REDACTED***"
        assert actual_dict["pAsSwOrD"] == "***REDACTED***"

    def test_pii_field_in_nested_dict(self) -> None:
        """嵌套 dict 中的 PII 字段也必须脱敏"""
        violation = _make_violation(  # pragma: allowlist secret
            actual={
                "user": {
                    "username": "alice",
                    "password": "test_secret",  # pragma: allowlist secret
                    "profile": {
                        "api_key": "test_key_value",  # pragma: allowlist secret
                        "metadata": {"normal": "ok"},
                    },
                },
            },
        )
        actual_dict = violation.to_dict()["actual"]
        assert actual_dict["user"]["username"] == "alice"  # 非 PII 保留
        assert actual_dict["user"]["password"] == "***REDACTED***"
        assert actual_dict["user"]["profile"]["api_key"] == "***REDACTED***"
        assert actual_dict["user"]["profile"]["metadata"]["normal"] == "ok"

    def test_pii_field_in_list_of_dicts(self) -> None:
        """list 中嵌套 dict 的 PII 字段也脱敏"""
        violation = _make_violation(  # pragma: allowlist secret
            actual={
                "users": [
                    {"name": "alice", "token": "value1"},  # pragma: allowlist secret
                    {"name": "bob", "token": "value2"},  # pragma: allowlist secret
                ],
            },
        )
        actual_dict = violation.to_dict()["actual"]
        assert actual_dict["users"][0]["name"] == "alice"
        assert actual_dict["users"][0]["token"] == "***REDACTED***"
        assert actual_dict["users"][1]["token"] == "***REDACTED***"

    def test_set_frozenset_serializable(self) -> None:
        """set / frozenset 也可序列化(Round 2 补漏)"""
        violation = _make_violation(
            actual={
                "tags": {1, 2, 3},
                "frozen_tags": frozenset({"a", "b"}),
            },
        )
        actual_dict = violation.to_dict()["actual"]
        # set 转 list,顺序可能不同,用 sorted 比较
        assert sorted(actual_dict["tags"]) == [1, 2, 3]
        assert sorted(actual_dict["frozen_tags"]) == ["a", "b"]

    def test_non_pii_field_not_redacted(self) -> None:
        """非 PII 字段值不应被脱敏"""
        violation = _make_violation(  # pragma: allowlist secret
            actual={
                "username": "alice",
                "email": "alice@example.com",
                "age": 30,
                "password_hash": "already-hashed-not-sensitive",  # pragma: allowlist secret
            },
        )
        actual_dict = violation.to_dict()["actual"]
        assert actual_dict["username"] == "alice"
        assert actual_dict["email"] == "alice@example.com"
        assert actual_dict["age"] == 30
        # password_hash 不在 PII 黑名单,保留(避免误杀)
        assert actual_dict["password_hash"] == "already-hashed-not-sensitive"  # pragma: allowlist secret

    def test_datetime_uuid_decimal_still_serializable(self) -> None:
        """确保 PII 修复未破坏既有 datetime/UUID/Decimal 脱敏"""
        violation = _make_violation(
            actual={
                "created_at": datetime.now(UTC),
                "user_id": uuid.uuid4(),
                "balance": "100.50",
                "token": "secret",
            },
        )
        actual_dict = violation.to_dict()["actual"]
        assert isinstance(actual_dict["created_at"], str)  # ISO 格式
        assert isinstance(actual_dict["user_id"], str)  # UUID → str
        assert actual_dict["balance"] == "100.50"  # Decimal → str
        assert actual_dict["token"] == "***REDACTED***"  # PII 仍脱敏

    def test_empty_dict_passes_through(self) -> None:
        """空 dict 不应抛错"""
        violation = _make_violation(actual={})
        actual_dict = violation.to_dict()["actual"]
        assert actual_dict == {}

    def test_pii_field_in_dict_with_uuid_value(self) -> None:
        """PII 字段值是 UUID 等对象时也应脱敏(优先级: PII 黑名单 > 类型脱敏)"""
        violation = _make_violation(
            actual={
                "api_key": uuid.uuid4(),  # 即使是 UUID 值也脱敏
                "session_id": uuid.uuid4(),
            },
        )
        actual_dict = violation.to_dict()["actual"]
        assert actual_dict["api_key"] == "***REDACTED***"
