"""EncryptionService 单元测试。

验证 EncryptionService 正确实现密码哈希和验证功能。
"""

from __future__ import annotations

import pytest

from src.infrastructure.security.encryption_service import EncryptionService


class TestEncryptionService:
    """测试 EncryptionService 加密服务。"""

    @pytest.fixture
    def service(self) -> EncryptionService:
        """创建 EncryptionService 实例。"""
        return EncryptionService()

    def test_hash_password_returns_hash(self, service: EncryptionService) -> None:
        """hash_password 应返回哈希字符串。"""
        hashed = service.hash_password("test_password")
        assert hashed is not None
        assert hashed != "test_password"
        assert len(hashed) > 0

    def test_hash_password_different_each_time(self, service: EncryptionService) -> None:
        """每次哈希应使用不同 salt，生成不同哈希。"""
        hash1 = service.hash_password("password123")
        hash2 = service.hash_password("password123")
        assert hash1 != hash2

    def test_verify_password_correct(self, service: EncryptionService) -> None:
        """正确密码应验证通过。"""
        hashed = service.hash_password("my_secret_password")
        result = service.verify_password("my_secret_password", hashed)
        assert result is True

    def test_verify_password_incorrect(self, service: EncryptionService) -> None:
        """错误密码应验证失败。"""
        hashed = service.hash_password("correct_password")
        result = service.verify_password("wrong_password", hashed)
        assert result is False

    def test_verify_password_invalid_hash(self, service: EncryptionService) -> None:
        """无效哈希格式应返回 False。"""
        result = service.verify_password("password", "not_a_valid_hash")
        assert result is False

    def test_verify_password_empty_password(self, service: EncryptionService) -> None:
        """空密码验证应返回 False。"""
        hashed = service.hash_password("some_password")
        result = service.verify_password("", hashed)
        assert result is False

    def test_timing_safe_verify_always_returns_true(self, service: EncryptionService) -> None:
        """timing_safe_verify 应始终返回 True。"""
        result = service.timing_safe_verify("any_password")
        assert result is True

    def test_needs_rehash_false_for_modern_hash(self, service: EncryptionService) -> None:
        """现代 bcrypt 哈希不需要 rehash。"""
        modern_hash = "$2b$12$abcdefghijklmnopqrstuu4PZB8APALaZ4dCqKPQXqKqKXqKqKq"
        result = service.needs_rehash(modern_hash)
        assert result is False

    def test_needs_rehash_true_for_old_bcrypt_variant(self, service: EncryptionService) -> None:
        """旧的 $2a$ bcrypt 哈希需要 rehash。"""
        old_hash = "$2a$12$abcdefghijklmnopqrstuu4PZB8APALaZ4dCqKPQXqKqKXqKqKq"
        result = service.needs_rehash(old_hash)
        assert result is True

    def test_hash_and_verify_integration(self, service: EncryptionService) -> None:
        """完整哈希验证流程。"""
        password = "SecureP@ssw0rd!2024"  # pragma: allowlist secret
        hashed = service.hash_password(password)
        assert service.verify_password(password, hashed) is True
        assert service.verify_password("WrongPassword", hashed) is False

    def test_verify_password_unicode_password(self, service: EncryptionService) -> None:
        """Unicode 密码应正常工作。"""
        password = "密码テスト🔐"
        hashed = service.hash_password(password)
        assert service.verify_password(password, hashed) is True

    def test_verify_password_special_characters(self, service: EncryptionService) -> None:
        """特殊字符密码应正常工作。"""
        password = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        hashed = service.hash_password(password)
        assert service.verify_password(password, hashed) is True
