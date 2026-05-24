"""领域层存储加密服务端口模块

定义存储加密服务的抽象接口，遵循六边形架构端口协议
用于等保2.0三级数据保密性

设计原则：
- encrypt_field(): 字段级加密
- decrypt_field(): 字段级解密
- rotate_key(): 密钥轮换
- verify_encryption(): 加密验证

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.storage_encryption_result import (
    EncryptedData,
    EncryptionVerificationResult,
)


@runtime_checkable
class StorageEncryptionServicePort(Protocol):
    """存储加密服务抽象端口

    等保2.0三级数据保密性要求的核心服务端口，负责：
    - 字段级数据加密/解密（AES-256-GCM / SM4-GCM）
    - 密钥轮换管理
    - 加密状态验证

    实现类必须遵循此接口契约，确保端口的可替换性
    """

    async def encrypt_field(
        self,
        plaintext: str,
        key_id: str = "",
    ) -> EncryptedData:
        """加密字段数据

        Args:
            plaintext: 明文数据
            key_id: 密钥标识符（空字符串使用默认密钥）

        Returns:
            EncryptedData 包含密文、密钥ID、算法、IV等
        """
        ...

    async def decrypt_field(
        self,
        encrypted_data: EncryptedData,
    ) -> str:
        """解密字段数据

        Args:
            encrypted_data: 加密数据

        Returns:
            解密后的明文字符串
        """
        ...

    async def rotate_key(
        self,
        old_key_id: str,
        new_key_id: str,
    ) -> int:
        """轮换加密密钥

        Args:
            old_key_id: 旧密钥标识符
            new_key_id: 新密钥标识符

        Returns:
            重新加密的记录数量
        """
        ...

    async def verify_encryption(
        self,
        data_id: str,
    ) -> EncryptionVerificationResult:
        """验证数据加密状态

        Args:
            data_id: 数据唯一标识符

        Returns:
            EncryptionVerificationResult 包含加密验证结果
        """
        ...
