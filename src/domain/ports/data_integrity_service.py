"""领域层数据完整性服务端口模块

定义数据完整性服务的抽象接口，遵循六边形架构端口协议
用于等保2.0三级数据完整性合规

设计原则：
- calculate_checksum(): 计算数据校验和
- verify_checksum(): 验证数据校验和
- verify_data_integrity(): 验证数据完整性并发布事件

注意：与 IntegrityPort（文件级完整性）互补，本端口专注于记录级/字段级验证

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.data_integrity_result import IntegrityResult


@runtime_checkable
class DataIntegrityServicePort(Protocol):
    """数据完整性服务抽象端口

    等保2.0三级数据完整性要求的核心服务端口，负责：
    - SHA256 校验和计算和验证
    - 数据篡改检测和告警
    - 完整性违规事件发布

    实现类必须遵循此接口契约，确保端口的可替换性
    """

    async def calculate_checksum(
        self,
        data: str | bytes,
        algorithm: str = "sha256",
    ) -> str:
        """计算数据的校验和

        Args:
            data: 待计算的数据（字符串或字节）
            algorithm: 哈希算法（sha256/sha512/md5）

        Returns:
            十六进制编码的校验和字符串
        """
        ...

    async def verify_checksum(
        self,
        data: str | bytes,
        expected_hash: str,
        algorithm: str = "sha256",
    ) -> IntegrityResult:
        """验证数据的校验和

        Args:
            data: 待验证的数据
            expected_hash: 预期的校验和
            algorithm: 哈希算法

        Returns:
            IntegrityResult 包含验证结果和详细信息
        """
        ...

    async def verify_data_integrity(
        self,
        data_id: str,
        data: str | bytes,
        stored_hash: str,
        algorithm: str = "sha256",
    ) -> IntegrityResult:
        """验证数据完整性并追踪数据标识

        Args:
            data_id: 数据唯一标识符
            data: 待验证的数据
            stored_hash: 存储的校验和
            algorithm: 哈希算法

        Returns:
            IntegrityResult 包含验证结果、数据标识和详细信息
        """
        ...
