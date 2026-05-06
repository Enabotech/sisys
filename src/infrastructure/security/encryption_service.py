"""Encryption Service - 加密服务.

提供密码哈希和验证功能，使用 bcrypt 算法。
遵循六边形架构：基础设施层实现，可以导入外部库 (passlib, bcrypt)。
"""

from __future__ import annotations

from passlib.context import CryptContext

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EncryptionService:
    """加密服务实现.

    使用 passlib + bcrypt 实现密码哈希和验证。
    遵循六边形架构：实现位于 infrastructure 层。
    """

    def hash_password(self, password: str) -> str:
        """哈希密码.

        Args:
            password: 明文密码

        Returns:
            哈希后的密码字符串
        """
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码.

        Args:
            plain_password: 明文密码
            hashed_password: 哈希后的密码

        Returns:
            True 如果密码匹配，False 否则
        """
        return pwd_context.verify(plain_password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """检查密码哈希是否需要重新哈希.

        当 bcrypt 版本升级或配置更改时可能需要。

        Args:
            hashed_password: 哈希后的密码

        Returns:
            True 如果需要重新哈希，False 否则
        """
        # passlib < 1.8 doesn't have needs_rehash, check manually
        # bcrypt hashes start with $2a$, $2b$, or $2y$
        if hashed_password.startswith("$2a$"):
            # Old bcrypt variant, should be upgraded
            return True
        return False
