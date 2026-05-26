"""领域层数据完整性结果值对象

定义数据完整性服务返回的结果类型，用于等保2.0三级数据完整性验证
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityResult:
    """数据完整性验证结果

    Attributes:
        valid: 完整性验证是否通过
        data_id: 数据唯一标识符
        expected_hash: 预期哈希值
        actual_hash: 实际哈希值
        algorithm: 哈希算法（sha256/sha512/md5）
        error_message: 错误信息
    """

    valid: bool = False
    data_id: str = ""
    expected_hash: str = ""
    actual_hash: str = ""
    algorithm: str = "sha256"
    error_message: str = ""
