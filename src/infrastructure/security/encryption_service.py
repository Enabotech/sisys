"""SISYS 基础设施层加密服务模块。

基于 passlib + bcrypt 提供密码哈希、验证和防御 timing attack 功能。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import bcrypt
from passlib.context import CryptContext

# 密码哈希配置，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EncryptionService:
    """加密服务实现，使用 passlib + bcrypt 进行密码哈希和验证。"""

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
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

    def timing_safe_verify(self, password: str) -> bool:
        """执行伪密码验证以防御 timing attack。

        使用随机生成的 salt，确保每次调用都执行完整的 bcrypt 计算。
        由于使用随机 salt，验证结果永远为 False，但计算时间是一致的。

        Args:
            password: 明文密码

        Returns:
            始终返回 True（验证结果被忽略，只为执行计算）
        """
        # 使用随机 salt 每次生成新哈希，确保完整 bcrypt 计算
        salt = bcrypt.gensalt(rounds=12)
        bcrypt.hashpw(password.encode(), salt)
        return True

    def needs_rehash(self, hashed_password: str) -> bool:
        """检查密码哈希是否需要重新哈希。

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
