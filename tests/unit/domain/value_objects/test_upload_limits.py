"""Tests for UploadLimits constants — 大小限制与分片策略"""

from src.domain.value_objects.upload_limits import (
    MAX_ARCHIVE_EXTRACTED_SIZE,
    MAX_BATCH_COUNT,
    MAX_BATCH_SIZE,
    MAX_COMPRESSION_RATIO,
    MAX_FILE_SIZE,
    MAX_FILENAME_LENGTH,
    MAX_NESTING_DEPTH,
    MB,
    get_chunk_size,
)


class TestMaxFileSize:
    """验证单文件大小限制"""

    def test_max_file_size_is_20gb(self) -> None:
        assert MAX_FILE_SIZE == 20 * 1024 * 1024 * 1024

    def test_max_batch_size_is_20gb(self) -> None:
        assert MAX_BATCH_SIZE == 20 * 1024 * 1024 * 1024

    def test_max_batch_count_is_100(self) -> None:
        assert MAX_BATCH_COUNT == 100

    def test_max_filename_length_is_255(self) -> None:
        assert MAX_FILENAME_LENGTH == 255


class TestGetChunkSize:
    """验证四级分片策略（与 ObjectOperations.calculate_part_size 对齐）"""

    def test_small_file_no_chunk(self) -> None:
        """< 100MB 不分片"""
        assert get_chunk_size(50 * MB) == 0

    def test_boundary_100mb_uses_10mb(self) -> None:
        """恰好 100MB 进入 10MB 分片路径（严格小于 < 100MB 不分片）"""
        assert get_chunk_size(100 * MB) == 10 * MB

    def test_500mb_uses_10mb(self) -> None:
        """100MB ~ 1GB 使用 10MB 分片"""
        assert get_chunk_size(500 * MB) == 10 * MB

    def test_boundary_1gb_uses_50mb(self) -> None:
        """恰好 1GB 使用 50MB 分片"""
        assert get_chunk_size(1 * 1024 * MB) == 50 * MB

    def test_5gb_uses_50mb(self) -> None:
        """1GB ~ 10GB 使用 50MB 分片"""
        assert get_chunk_size(5 * 1024 * MB) == 50 * MB

    def test_boundary_10gb_uses_100mb(self) -> None:
        """恰好 10GB 使用 100MB 分片"""
        assert get_chunk_size(10 * 1024 * MB) == 100 * MB

    def test_20gb_uses_100mb(self) -> None:
        """>= 10GB 使用 100MB 分片"""
        assert get_chunk_size(20 * 1024 * 1024 * MB) == 100 * MB

    def test_zero_size_no_chunk(self) -> None:
        """0 字节不分片"""
        assert get_chunk_size(0) == 0

    def test_1_byte_no_chunk(self) -> None:
        """1 字节不分片"""
        assert get_chunk_size(1) == 0

    def test_99mb_no_chunk(self) -> None:
        """99MB 不分片"""
        assert get_chunk_size(99 * MB) == 0

    def test_99mb_999999(self) -> None:
        """99.99MB 不分片（严格小于 100MB）"""
        assert get_chunk_size(100 * MB - 1) == 0


class TestArchiveLimits:
    """验证压缩包相关限制"""

    def test_max_nesting_depth_is_3(self) -> None:
        assert MAX_NESTING_DEPTH == 3

    def test_max_compression_ratio_is_10(self) -> None:
        assert MAX_COMPRESSION_RATIO == 10

    def test_max_archive_extracted_size_is_20gb(self) -> None:
        assert MAX_ARCHIVE_EXTRACTED_SIZE == MAX_BATCH_SIZE
