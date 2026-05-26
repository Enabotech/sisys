"""文件名清洗器模块

处理文件名中的非法字符、长度限制、Windows 保留名等问题
零外部依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FilenameSanitizer:
    """文件名清洗器

    Attributes:
        max_length: 文件名最大长度（含扩展名）
    """

    max_length: int = 200

    _ILLEGAL_CHARS: re.Pattern[str] = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    _RESERVED_NAMES: frozenset[str] = frozenset(
        {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
    )

    def sanitize(self, raw_name: str, extension: str = "") -> str:
        """清洗原始文件名并追加扩展名

        Args:
            raw_name: 原始文件名
            extension: 文件扩展名（不含点号）

        Returns:
            清洗后的合法文件名
        """
        name = raw_name.strip()

        # 替换非法字符为下划线
        name = self._replace_illegal_chars(name)

        # 合并连续空格/下划线
        name = self._collapse_whitespace(name)

        # 去除首尾空白和点号
        name = name.strip(". ")

        # 处理 Windows 保留名
        name = self._handle_reserved_name(name)

        # 长度截断
        name = self._truncate(name, extension)

        # 追加扩展名
        if extension and not name.endswith(f".{extension}"):
            name = f"{name}.{extension}"

        return name

    def _replace_illegal_chars(self, name: str) -> str:
        """替换文件名中的非法字符为下划线"""
        return self._ILLEGAL_CHARS.sub("_", name)

    def _collapse_whitespace(self, name: str) -> str:
        """合并连续空格和下划线为单空格"""
        return re.sub(r"[\s_]+", " ", name).strip()

    def _handle_reserved_name(self, name: str) -> str:
        """处理 Windows 保留文件名"""
        base = name.split(".")[0].upper() if "." in name else name.upper()
        if base in self._RESERVED_NAMES:
            return f"_{name}"
        return name

    def _truncate(self, name: str, extension: str) -> str:
        """截断过长的文件名"""
        if not extension:
            return name[: self.max_length]

        # 为扩展名预留空间（点号 + 扩展名）
        max_base = self.max_length - len(extension) - 1
        if max_base <= 0:
            return name[: self.max_length]
        return name[:max_base]
