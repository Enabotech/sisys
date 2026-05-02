"""IntegrityPort — 数据完整性验证抽象端口。

设计原则：
- verify_file(): I/O 密集型 → async + to_thread
- compute_hash()/verify_hash(): CPU 密集型 → sync（事件循环中直接调用不阻塞）

注意：使用 str | None 类型定义算法，避免引入 infrastructure 层依赖。
实现内部将字符串转换为 HashAlgorithm enum。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IntegrityPort(ABC):
    """数据完整性验证抽象端口。

    设计原则：
    - verify_file(): I/O 密集型 → async + to_thread
    - compute_hash()/verify_hash(): CPU 密集型 → sync（事件循环中直接调用不阻塞）

    注意：使用 str | None 类型定义算法，避免引入 infrastructure 层依赖。
    实现内部将字符串转换为 HashAlgorithm enum。
    """

    @abstractmethod
    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        """验证文件完整性（I/O 密集型）。

        Args:
            file_path: 文件路径
            expected_hash: 期望的哈希值

        Returns:
            True 如果哈希匹配，False 否则
        """
        pass

    @abstractmethod
    def compute_hash(self, data: str | bytes, algorithm: str | None = None) -> str:
        """计算数据哈希（CPU 密集型，直接调用不阻塞事件循环）。

        Args:
            data: 数据
            algorithm: 算法字符串（"sha256"/"sha512"/"md5"），None 使用默认算法

        Returns:
            十六进制编码的哈希值
        """
        pass

    @abstractmethod
    def verify_hash(
        self,
        data: str | bytes,
        expected_hash: str,
        algorithm: str | None = None,
    ) -> bool:
        """验证数据哈希（CPU 密集型，直接调用不阻塞事件循环）。

        Args:
            data: 数据
            expected_hash: 期望的哈希值
            algorithm: 算法字符串（"sha256"/"sha512"/"md5"），None 使用默认算法

        Returns:
            True 如果哈希匹配
        """
        pass
