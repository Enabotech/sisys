"""领域层 上传限制常量

定义文档上传的大小限制、批量限制和分片策略。
分片策略阈值与 ObjectOperations.calculate_part_size() 对齐。
"""

from __future__ import annotations

# 单文件最大大小：20GB
MAX_FILE_SIZE: int = 20 * 1024 * 1024 * 1024

# 批量上传总大小上限：20GB
MAX_BATCH_SIZE: int = 20 * 1024 * 1024 * 1024

# 单批最大文件数
MAX_BATCH_COUNT: int = 100

# 文件名最大长度
MAX_FILENAME_LENGTH: int = 255

# 分片大小阈值（字节）— 与 ObjectOperations.calculate_part_size() 四级策略对齐
MB: int = 1024 * 1024
SINGLE_UPLOAD_THRESHOLD: int = 100 * MB  # < 100MB 不分片
MEDIUM_PART_SIZE: int = 10 * MB  # 100MB ~ 1GB：10MB 分片
LARGE_PART_SIZE: int = 50 * MB  # 1GB ~ 10GB：50MB 分片
XLARGE_PART_SIZE: int = 100 * MB  # >= 10GB：100MB 分片

# 分片策略映射（文件大小上界 → 分片大小）
CHUNK_SIZES: dict[int, int] = {
    SINGLE_UPLOAD_THRESHOLD: 0,  # < 100MB → 不分片
    1 * 1024 * MB: MEDIUM_PART_SIZE,  # < 1GB → 10MB
    10 * 1024 * MB: LARGE_PART_SIZE,  # < 10GB → 50MB
}

# Redis 分片上传状态 TTL（秒）：24 小时
CHUNKED_UPLOAD_TTL: int = 24 * 60 * 60

# 压缩包解压后最大总大小：20GB（与批量上传限制一致）
MAX_ARCHIVE_EXTRACTED_SIZE: int = MAX_BATCH_SIZE

# 压缩包最大膨胀比
MAX_COMPRESSION_RATIO: int = 10

# 最大嵌套解压深度
MAX_NESTING_DEPTH: int = 3


def get_chunk_size(file_size: int) -> int:
    """根据文件大小计算分片大小

    分片策略与 ObjectOperations.calculate_part_size() 对齐：
    - < 100MB → 不分片（返回 0）
    - < 1GB → 10MB 分片
    - < 10GB → 50MB 分片
    - >= 10GB → 100MB 分片

    Args:
        file_size: 文件大小（字节）

    Returns:
        分片大小（字节），0 表示不分片
    """
    if file_size < SINGLE_UPLOAD_THRESHOLD:
        return 0
    if file_size < 1 * 1024 * MB:
        return MEDIUM_PART_SIZE
    if file_size < 10 * 1024 * MB:
        return LARGE_PART_SIZE
    return XLARGE_PART_SIZE
