"""基础设施层数据完整性服务模块

基于 DataIntegrityServicePort 接口实现 SHA256/SHA512/MD5 校验和计算、验证和篡改检测
用于等保2.0三级数据完整性合规
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.domain.exceptions import ConfigurationError
from src.domain.ports.data_integrity_service import DataIntegrityServicePort
from src.domain.value_objects.data_integrity_result import IntegrityResult

_ALGORITHMS = {
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
    "md5": hashlib.md5,
}


class DataIntegrityServiceImpl(DataIntegrityServicePort):
    """数据完整性服务实现，负责校验和计算、验证和篡改检测

    Attributes:
        _event_publisher: 事件发布器（可选，用于发布完整性违规事件）
    """

    def __init__(self, event_publisher: Any = None) -> None:
        """初始化数据完整性服务.

        Args:
            event_publisher: 事件发布器（可选）
        """
        self._event_publisher = event_publisher

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
            十六进制编码的校验和字符串（小写）

        Raises:
            ConfigurationError: 不支持的算法
        """
        hash_func = _ALGORITHMS.get(algorithm)
        if hash_func is None:
            raise ConfigurationError(message=f"Unsupported algorithm: {algorithm}")

        if isinstance(data, str):
            data = data.encode("utf-8")

        return hash_func(data).hexdigest()

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
        actual_hash = await self.calculate_checksum(data, algorithm)
        valid = actual_hash == expected_hash

        return IntegrityResult(
            valid=valid,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            algorithm=algorithm,
            error_message="" if valid else f"Checksum mismatch: expected {expected_hash}, got {actual_hash}",
        )

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
        actual_hash = await self.calculate_checksum(data, algorithm)
        valid = actual_hash == stored_hash

        result = IntegrityResult(
            valid=valid,
            data_id=data_id,
            expected_hash=stored_hash,
            actual_hash=actual_hash,
            algorithm=algorithm,
            error_message=("" if valid else f"Data integrity violation for {data_id}: checksum mismatch (possible tampering)"),
        )

        if not valid and self._event_publisher:
            await self._publish_integrity_violation(data_id, stored_hash, actual_hash)

        return result

    async def _publish_integrity_violation(
        self,
        data_id: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        """发布完整性违规事件

        Args:
            data_id: 数据标识
            expected_hash: 预期哈希
            actual_hash: 实际哈希
        """
        try:
            await self._event_publisher.publish(
                {
                    "event_type": "DataIntegrityViolation",
                    "data_id": data_id,
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                }
            )
        except Exception:
            pass  # 事件发布失败不影响完整性验证结果
