"""领域层存储加密结果值对象

定义存储加密服务返回的结果类型，用于等保2.0三级数据保密性

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EncryptedData:
    """加密数据结果

    Attributes:
        ciphertext: 加密后的密文（Base64 编码）
        key_id: 使用的密钥标识符
        algorithm: 加密算法（AES-256-GCM/SM4-GCM）
        iv: 初始化向量（Base64 编码）
        tag: 认证标签（Base64 编码）
    """

    ciphertext: str = ""
    key_id: str = ""
    algorithm: str = "AES-256-GCM"
    iv: str = ""
    tag: str = ""


@dataclass(frozen=True)
class EncryptionVerificationResult:
    """加密验证结果

    Attributes:
        is_encrypted: 数据是否已加密
        key_id: 使用的密钥标识符
        algorithm: 加密算法
        verified: 验证是否通过
    """

    is_encrypted: bool = False
    key_id: str = ""
    algorithm: str = ""
    verified: bool = False
