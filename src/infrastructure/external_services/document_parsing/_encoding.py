"""文档解析器共享编码检测工具

提供字节内容 → 文本的编码自动检测功能，供 TextParser 和 CSVParser 共享复用。
"""

from __future__ import annotations


def detect_and_decode(raw_bytes: bytes) -> tuple[str, str]:
    """编码自动检测

    依次尝试 UTF-8 → GBK → GB18030（GB18030 是 GBK 超集，兜底），
    不引入 chardet 依赖。

    Args:
        raw_bytes: 原始字节内容

    Returns:
        (解码后的文本字符串, 使用的编码名称)

    Raises:
        ValueError: 所有编码均解码失败
    """
    for encoding in ["utf-8", "gbk", "gb18030"]:
        try:
            return raw_bytes.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError("无法识别文件编码：尝试了 UTF-8/GBK/GB18030 均失败，请确保文件为上述编码格式")
