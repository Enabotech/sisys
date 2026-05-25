"""数据完整性服务单元测试

等保2.0三级数据完整性要求验证:
- AC-5.1: SHA256 校验和计算准确率 100%
- AC-5.2: 篡改检测准确率 100%
- AC-5.3: 完整性违规事件发布

本测试验证 DataIntegrityServiceImpl 的等保合规实现

对应 Story: 1-12-equilibrium-level-3-compliance Task 3 Subtask 3.1-3.5
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.security.data_integrity_service_impl import (
    DataIntegrityServiceImpl,
)


@pytest.fixture
def integrity_service() -> DataIntegrityServiceImpl:
    """创建数据完整性服务实例（含 mock 依赖）"""
    mock_event_publisher = AsyncMock()
    return DataIntegrityServiceImpl(
        event_publisher=mock_event_publisher,
    )


class TestChecksumCalculation:
    """校验和计算验证 (AC-5.1)"""

    async def test_calculate_sha256_checksum_string(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """计算字符串的 SHA256 校验和"""
        checksum = await integrity_service.calculate_checksum(
            data="test data content",
            algorithm="sha256",
        )
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 输出 64 位十六进制
        # 验证校验和格式正确（全小写十六进制）
        assert checksum == checksum.lower()
        assert all(c in "0123456789abcdef" for c in checksum)

    async def test_calculate_sha256_checksum_bytes(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """计算字节数据的 SHA256 校验和"""
        checksum = await integrity_service.calculate_checksum(
            data=b"binary data content",
            algorithm="sha256",
        )
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    async def test_calculate_checksum_returns_hex_lowercase(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """校验和应返回小写十六进制"""
        checksum = await integrity_service.calculate_checksum(
            data="test",
            algorithm="sha256",
        )
        assert checksum == checksum.lower()
        assert all(c in "0123456789abcdef" for c in checksum)

    async def test_calculate_checksum_deterministic(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """相同数据应产生相同校验和"""
        checksum1 = await integrity_service.calculate_checksum(
            data="consistent data",
            algorithm="sha256",
        )
        checksum2 = await integrity_service.calculate_checksum(
            data="consistent data",
            algorithm="sha256",
        )
        assert checksum1 == checksum2

    async def test_calculate_checksum_different_data_different_result(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """不同数据应产生不同校验和"""
        checksum1 = await integrity_service.calculate_checksum(
            data="data version 1",
            algorithm="sha256",
        )
        checksum2 = await integrity_service.calculate_checksum(
            data="data version 2",
            algorithm="sha256",
        )
        assert checksum1 != checksum2


class TestChecksumVerification:
    """校验和验证"""

    async def test_verify_checksum_match(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """验证匹配的校验和"""
        data = "test data"
        checksum = await integrity_service.calculate_checksum(data, "sha256")
        result = await integrity_service.verify_checksum(data, checksum, "sha256")
        assert result.valid is True
        assert result.expected_hash == checksum
        assert result.actual_hash == checksum

    async def test_verify_checksum_mismatch(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """验证不匹配的校验和"""
        data = "original data"
        wrong_checksum = "0000000000000000000000000000000000000000000000000000000000000000"
        result = await integrity_service.verify_checksum(data, wrong_checksum, "sha256")
        assert result.valid is False
        assert result.expected_hash == wrong_checksum
        assert result.actual_hash != wrong_checksum
        assert result.error_message != ""

    async def test_verify_checksum_tampered_data(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """验证被篡改的数据"""
        original_data = "original content"
        original_checksum = await integrity_service.calculate_checksum(original_data, "sha256")
        tampered_data = "tampered content"
        result = await integrity_service.verify_checksum(tampered_data, original_checksum, "sha256")
        assert result.valid is False
        assert "mismatch" in result.error_message.lower() or "tampered" in result.error_message.lower()


class TestDataIntegrityVerification:
    """数据完整性验证 (AC-5.2)"""

    async def test_verify_data_integrity_valid(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """验证数据完整性通过"""
        data_id = "record-001"
        data = "valid data content"
        checksum = await integrity_service.calculate_checksum(data, "sha256")
        result = await integrity_service.verify_data_integrity(data_id, data, checksum, "sha256")
        assert result.valid is True
        assert result.data_id == data_id

    async def test_verify_data_integrity_invalid(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """验证数据完整性失败"""
        data_id = "record-002"
        data = "modified data"
        wrong_checksum = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        result = await integrity_service.verify_data_integrity(data_id, data, wrong_checksum, "sha256")
        assert result.valid is False
        assert result.data_id == data_id
        assert result.error_message != ""

    async def test_verify_data_integrity_publishes_event_on_failure(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """完整性验证失败时应发布事件"""
        data_id = "record-003"
        data = "tampered data"
        wrong_checksum = "0000000000000000000000000000000000000000000000000000000000000001"
        await integrity_service.verify_data_integrity(data_id, data, wrong_checksum, "sha256")
        # 验证事件发布器被调用（如果配置了）
        if integrity_service._event_publisher:
            integrity_service._event_publisher.publish.assert_called()


class TestAlgorithmSupport:
    """算法支持验证"""

    async def test_default_algorithm_is_sha256(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """默认算法应为 SHA256"""
        checksum = await integrity_service.calculate_checksum("test")
        assert len(checksum) == 64  # SHA256 特征

    async def test_sha512_algorithm_supported(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """应支持 SHA512 算法"""
        checksum = await integrity_service.calculate_checksum("test", algorithm="sha512")
        assert len(checksum) == 128  # SHA512 输出 128 位十六进制

    async def test_md5_algorithm_supported(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """应支持 MD5 算法（兼容性用途）"""
        checksum = await integrity_service.calculate_checksum("test", algorithm="md5")
        assert len(checksum) == 32  # MD5 输出 32 位十六进制


class TestIntegrityResultStructure:
    """完整性结果结构验证"""

    async def test_result_has_required_fields(
        self,
        integrity_service: DataIntegrityServiceImpl,
    ) -> None:
        """完整性结果应包含所有必需字段"""
        result = await integrity_service.verify_checksum("test", "abc", "sha256")
        assert hasattr(result, "valid")
        assert hasattr(result, "data_id")
        assert hasattr(result, "expected_hash")
        assert hasattr(result, "actual_hash")
        assert hasattr(result, "algorithm")
        assert hasattr(result, "error_message")
