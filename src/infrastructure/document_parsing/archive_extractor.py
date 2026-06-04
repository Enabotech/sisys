"""基础设施层压缩包解压器

使用标准库 zipfile/tarfile 解压 zip/tar 压缩包，
支持格式过滤、嵌套深度限制、压缩炸弹防护、路径穿越防护、symlink 防护。
"""

from __future__ import annotations

import io
import os
import tarfile
import zipfile
from dataclasses import dataclass, field
from typing import BinaryIO

from src.domain.exceptions import StorageError, ValidationError
from src.domain.value_objects.document_format import ARCHIVE_EXTENSIONS, SUPPORTED_FORMATS, _extract_extension
from src.domain.value_objects.upload_limits import MAX_ARCHIVE_EXTRACTED_SIZE, MAX_NESTING_DEPTH


@dataclass
class ExtractedFile:
    """解压后的文件信息"""

    filename: str
    content: BinaryIO
    mime_type: str
    size: int
    source_archive: str = ""
    depth: int = 0


@dataclass
class ExtractResult:
    """解压结果"""

    files: list[ExtractedFile] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_extracted_size: int = 0


class ArchiveExtractor:
    """压缩包解压器"""

    def extract(
        self,
        archive_data: BinaryIO,
        archive_name: str,
        current_depth: int = 0,
    ) -> ExtractResult:
        """解压压缩包

        Args:
            archive_data: 压缩包二进制数据流
            archive_name: 压缩包文件名
            current_depth: 当前嵌套深度

        Returns:
            ExtractResult 包含解压后的文件和跳过的文件
        """
        ext = _extract_extension(archive_name)
        if ext == "zip":
            return self._extract_zip(archive_data, archive_name, current_depth)
        if ext == "tar":
            return self._extract_tar(archive_data, archive_name, current_depth)
        return ExtractResult(warnings=[f"不支持的压缩格式: {archive_name}"])

    def _extract_zip(
        self,
        archive_data: BinaryIO,
        archive_name: str,
        current_depth: int,
    ) -> ExtractResult:
        result = ExtractResult()

        try:
            with zipfile.ZipFile(archive_data, "r") as zf:
                total_size = 0

                for info in zf.infolist():
                    if info.is_dir():
                        continue

                    # symlink 防护
                    if self._is_symlink_zip(info):
                        result.warnings.append(f"跳过符号链接: {info.filename}")
                        result.skipped.append({"filename": info.filename, "reason": "符号链接"})
                        continue

                    # 路径穿越防护
                    if self._has_path_traversal(info.filename):
                        result.warnings.append(f"跳过路径穿越: {info.filename}")
                        result.skipped.append({"filename": info.filename, "reason": "路径穿越"})
                        continue

                    # 格式过滤
                    inner_ext = _extract_extension(os.path.basename(info.filename))
                    if inner_ext is None or inner_ext not in SUPPORTED_FORMATS:
                        result.skipped.append({"filename": info.filename, "reason": "不支持的格式"})
                        continue

                    mime_type = SUPPORTED_FORMATS.get(inner_ext, "")
                    content = io.BytesIO(zf.read(info.filename))
                    file_size = content.getbuffer().nbytes

                    # 压缩炸弹防护
                    if total_size + file_size > MAX_ARCHIVE_EXTRACTED_SIZE:
                        raise StorageError(message="解压后总大小超过限制（压缩炸弹防护）")

                    if current_depth < MAX_NESTING_DEPTH - 1 and inner_ext in ARCHIVE_EXTENSIONS:
                        nested_result = self.extract(content, os.path.basename(info.filename), current_depth + 1)
                        result.files.extend(nested_result.files)
                        result.skipped.extend(nested_result.skipped)
                        result.warnings.extend(nested_result.warnings)
                        total_size += nested_result.total_extracted_size
                    else:
                        if inner_ext in ARCHIVE_EXTENSIONS and current_depth >= MAX_NESTING_DEPTH - 1:
                            result.warnings.append(f"跳过嵌套压缩包（深度超限）: {info.filename}")
                            result.skipped.append({"filename": info.filename, "reason": "嵌套深度超限"})
                            continue

                        total_size += file_size
                        result.files.append(
                            ExtractedFile(
                                filename=os.path.basename(info.filename),
                                content=content,
                                mime_type=mime_type,
                                size=file_size,
                                source_archive=archive_name,
                                depth=current_depth,
                            )
                        )

                result.total_extracted_size = total_size

        except zipfile.BadZipFile as e:
            raise ValidationError(message=f"无效的 ZIP 文件: {e}") from e

        return result

    def _extract_tar(
        self,
        archive_data: BinaryIO,
        archive_name: str,
        current_depth: int,
    ) -> ExtractResult:
        result = ExtractResult()

        try:
            with tarfile.open(fileobj=archive_data, mode="r:*") as tf:
                total_size = 0

                for member in tf.getmembers():
                    if not member.isfile():
                        # symlink 防护（非普通文件中的特殊类型）
                        if member.issym() or member.islnk():
                            result.warnings.append(f"跳过符号链接: {member.name}")
                            result.skipped.append({"filename": member.name, "reason": "符号链接"})
                        continue

                    # 路径穿越防护
                    if self._has_path_traversal(member.name):
                        result.warnings.append(f"跳过路径穿越: {member.name}")
                        result.skipped.append({"filename": member.name, "reason": "路径穿越"})
                        continue

                    basename = os.path.basename(member.name)
                    inner_ext = _extract_extension(basename)
                    if inner_ext is None or inner_ext not in SUPPORTED_FORMATS:
                        result.skipped.append({"filename": member.name, "reason": "不支持的格式"})
                        continue

                    mime_type = SUPPORTED_FORMATS.get(inner_ext, "")
                    f = tf.extractfile(member)
                    if f is None:
                        continue
                    content_bytes = f.read()
                    content = io.BytesIO(content_bytes)
                    file_size = len(content_bytes)

                    if total_size + file_size > MAX_ARCHIVE_EXTRACTED_SIZE:
                        raise StorageError(message="解压后总大小超过限制（压缩炸弹防护）")

                    if current_depth < MAX_NESTING_DEPTH - 1 and inner_ext in ARCHIVE_EXTENSIONS:
                        nested_result = self.extract(content, basename, current_depth + 1)
                        result.files.extend(nested_result.files)
                        result.skipped.extend(nested_result.skipped)
                        result.warnings.extend(nested_result.warnings)
                        total_size += nested_result.total_extracted_size
                    else:
                        if inner_ext in ARCHIVE_EXTENSIONS and current_depth >= MAX_NESTING_DEPTH - 1:
                            result.warnings.append(f"跳过嵌套压缩包（深度超限）: {member.name}")
                            result.skipped.append({"filename": member.name, "reason": "嵌套深度超限"})
                            continue

                        total_size += file_size
                        result.files.append(
                            ExtractedFile(
                                filename=basename,
                                content=content,
                                mime_type=mime_type,
                                size=file_size,
                                source_archive=archive_name,
                                depth=current_depth,
                            )
                        )

                result.total_extracted_size = total_size

        except tarfile.TarError as e:
            raise ValidationError(message=f"无效的 TAR 文件: {e}") from e

        return result

    def _has_path_traversal(self, filepath: str) -> bool:
        """检测路径穿越（../）"""
        normalized = os.path.normpath(filepath)
        return normalized.startswith("..") or ".." in filepath

    def _is_symlink_zip(self, info: zipfile.ZipInfo) -> bool:
        """检测 ZIP 中的符号链接"""
        return (info.external_attr >> 16) & 0o170000 == 0o120000
