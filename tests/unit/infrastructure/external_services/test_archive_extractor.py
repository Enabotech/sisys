"""Tests for ArchiveExtractor — 压缩包解压器"""

from __future__ import annotations

import io
import tarfile
import zipfile
from unittest.mock import patch

import pytest

from src.domain.value_objects.upload_limits import MAX_NESTING_DEPTH
from src.infrastructure.external_services.archive_extractor import (
    ArchiveExtractor,
)


def _make_zip_file(files: dict[str, bytes]) -> io.BytesIO:
    """构造包含指定文件的 ZIP 压缩包"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


def _make_tar_file(files: dict[str, bytes]) -> io.BytesIO:
    """构造包含指定文件的 TAR 压缩包"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
    buf.seek(0)
    return buf


class TestArchiveExtractorZip:
    """验证 ZIP 解压"""

    def test_extract_zip_single_file(self) -> None:
        """解压包含单个文件的 ZIP"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file({"report.pdf": b"%PDF-1.4 fake content"})

        result = extractor.extract(archive, "archive.zip")

        assert len(result.files) == 1
        assert result.files[0].filename == "report.pdf"
        assert result.files[0].size > 0

    def test_extract_zip_multiple_files(self) -> None:
        """解压包含多个文件的 ZIP"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file(
            {
                "a.pdf": b"pdf-content-a",
                "b.txt": b"text-content-b",
            }
        )

        result = extractor.extract(archive, "multi.zip")

        assert len(result.files) == 2
        filenames = {f.filename for f in result.files}
        assert filenames == {"a.pdf", "b.txt"}

    def test_extract_zip_skips_directories(self) -> None:
        """解压时跳过目录项"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("subdir/", "")  # 目录
            zf.writestr("subdir/file.txt", "hello")
        buf.seek(0)

        result = extractor.extract(buf, "dirs.zip")
        assert len(result.files) == 1
        assert result.files[0].filename == "file.txt"

    def test_extract_zip_skips_unsupported_formats(self) -> None:
        """跳过不支持的文件格式"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file(
            {
                "good.pdf": b"pdf-content",
                "bad.exe": b"exe-content",
            }
        )

        result = extractor.extract(archive, "mixed.zip")

        assert len(result.files) == 1
        assert result.files[0].filename == "good.pdf"
        skipped_names = {s["filename"] for s in result.skipped}
        assert any("bad.exe" in n for n in skipped_names)

    def test_extract_zip_sets_source_archive(self) -> None:
        """解压文件应记录来源压缩包名"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file({"file.pdf": b"content"})

        result = extractor.extract(archive, "my-archive.zip")

        assert result.files[0].source_archive == "my-archive.zip"

    def test_extract_zip_bad_file_raises(self) -> None:
        """无效 ZIP 文件抛出 ValueError"""
        extractor = ArchiveExtractor()
        bad_data = io.BytesIO(b"not a zip file at all")

        with pytest.raises(ValueError, match="无效的 ZIP"):
            extractor.extract(bad_data, "bad.zip")


class TestArchiveExtractorTar:
    """验证 TAR 解压"""

    def test_extract_tar_single_file(self) -> None:
        """解压包含单个文件的 TAR"""
        extractor = ArchiveExtractor()
        archive = _make_tar_file({"report.pdf": b"%PDF-1.4 fake content"})

        result = extractor.extract(archive, "archive.tar")

        assert len(result.files) == 1
        assert result.files[0].filename == "report.pdf"

    def test_extract_tar_multiple_files(self) -> None:
        """解压包含多个文件的 TAR"""
        extractor = ArchiveExtractor()
        archive = _make_tar_file(
            {
                "a.pdf": b"pdf-content",
                "b.txt": b"text-content",
            }
        )

        result = extractor.extract(archive, "multi.tar")

        assert len(result.files) == 2
        filenames = {f.filename for f in result.files}
        assert filenames == {"a.pdf", "b.txt"}

    def test_extract_tar_skips_directories(self) -> None:
        """解压时跳过目录项"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            dir_info = tarfile.TarInfo(name="subdir/")
            dir_info.type = tarfile.DIRTYPE
            tf.addfile(dir_info)
            file_info = tarfile.TarInfo(name="subdir/file.txt")
            file_info.size = 5
            tf.addfile(file_info, io.BytesIO(b"hello"))
        buf.seek(0)

        result = extractor.extract(buf, "dirs.tar")
        assert len(result.files) == 1
        assert result.files[0].filename == "file.txt"

    def test_extract_tar_bad_file_raises(self) -> None:
        """无效 TAR 文件抛出 ValueError"""
        extractor = ArchiveExtractor()
        bad_data = io.BytesIO(b"not a tar file at all")

        with pytest.raises(ValueError, match="无效的 TAR"):
            extractor.extract(bad_data, "bad.tar")


class TestArchiveExtractorUnsupportedFormat:
    """验证不支持的压缩格式"""

    def test_extract_unsupported_format_returns_warning(self) -> None:
        """不支持的格式返回警告"""
        extractor = ArchiveExtractor()
        result = extractor.extract(io.BytesIO(b"data"), "archive.rar")

        assert len(result.files) == 0
        assert any("不支持" in w for w in result.warnings)


class TestArchiveExtractorPathTraversal:
    """验证路径穿越防护"""

    def test_zip_path_traversal_blocked(self) -> None:
        """ZIP 中路径穿越项被跳过"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious")
            zf.writestr("safe.txt", "ok")
        buf.seek(0)

        result = extractor.extract(buf, "evil.zip")

        assert len(result.files) == 1
        assert result.files[0].filename == "safe.txt"
        assert any("路径穿越" in w for w in result.warnings)

    def test_tar_path_traversal_blocked(self) -> None:
        """TAR 中路径穿越项被跳过"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name="../../etc/shadow")
            info.size = 3
            tf.addfile(info, io.BytesIO(b"bad"))
        buf.seek(0)

        result = extractor.extract(buf, "evil.tar")

        assert len(result.files) == 0
        assert any("路径穿越" in w for w in result.warnings)

    def test_has_path_traversal_double_dot(self) -> None:
        """检测包含 .. 的路径"""
        extractor = ArchiveExtractor()
        assert extractor._has_path_traversal("../secret") is True
        assert extractor._has_path_traversal("dir/../secret") is True

    def test_has_path_traversal_safe(self) -> None:
        """安全路径不误报"""
        extractor = ArchiveExtractor()
        assert extractor._has_path_traversal("subdir/file.txt") is False
        assert extractor._has_path_traversal("file.txt") is False


class TestArchiveExtractorSymlink:
    """验证符号链接防护"""

    def test_zip_symlink_blocked(self) -> None:
        """ZIP 中符号链接被跳过"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("link.txt")
            info.external_attr = (0o120000 << 16) | 0o777
            zf.writestr(info, "/etc/passwd")
            zf.writestr("safe.txt", "ok")
        buf.seek(0)

        result = extractor.extract(buf, "symlink.zip")

        assert len(result.files) == 1
        assert result.files[0].filename == "safe.txt"
        assert any("符号链接" in w for w in result.warnings)

    def test_tar_symlink_blocked(self) -> None:
        """TAR 中符号链接被跳过"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            link_info = tarfile.TarInfo(name="link.txt")
            link_info.type = tarfile.SYMTYPE
            link_info.linkname = "/etc/passwd"
            tf.addfile(link_info)
            file_info = tarfile.TarInfo(name="safe.txt")
            file_info.size = 2
            tf.addfile(file_info, io.BytesIO(b"ok"))
        buf.seek(0)

        result = extractor.extract(buf, "symlink.tar")

        assert len(result.files) == 1
        assert any("符号链接" in w for w in result.warnings)

    def test_tar_hardlink_blocked(self) -> None:
        """TAR 中硬链接被跳过"""
        extractor = ArchiveExtractor()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            link_info = tarfile.TarInfo(name="hardlink.txt")
            link_info.type = tarfile.LNKTYPE
            link_info.linkname = "/etc/shadow"
            tf.addfile(link_info)
        buf.seek(0)

        result = extractor.extract(buf, "hardlink.tar")

        assert len(result.files) == 0
        assert any("符号链接" in w for w in result.warnings)


class TestArchiveExtractorCompressionBomb:
    """验证压缩炸弹防护"""

    @patch("src.infrastructure.external_services.archive_extractor.MAX_ARCHIVE_EXTRACTED_SIZE", 1024)
    def test_zip_bomb_detected(self) -> None:
        """ZIP 压缩炸弹触发大小限制"""
        extractor = ArchiveExtractor()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("huge.pdf", "x" * 2048)
        buf.seek(0)

        with pytest.raises(ValueError, match="压缩炸弹"):
            extractor.extract(buf, "bomb.zip")

    @patch("src.infrastructure.external_services.archive_extractor.MAX_ARCHIVE_EXTRACTED_SIZE", 1024)
    def test_tar_bomb_detected(self) -> None:
        """TAR 压缩炸弹触发大小限制"""
        extractor = ArchiveExtractor()

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name="huge.pdf")
            info.size = 2048
            tf.addfile(info, io.BytesIO(b"x" * 2048))
        buf.seek(0)

        with pytest.raises(ValueError, match="压缩炸弹"):
            extractor.extract(buf, "bomb.tar")

    def test_zip_normal_size_within_limit(self) -> None:
        """正常大小文件不触发限制"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file({"small.pdf": b"x" * 1024})

        result = extractor.extract(archive, "normal.zip")
        assert len(result.files) == 1
        assert result.total_extracted_size == 1024


class TestArchiveExtractorNesting:
    """验证嵌套解压"""

    def test_nested_zip_extracted(self) -> None:
        """嵌套 ZIP 被递归解压"""
        extractor = ArchiveExtractor()

        inner_archive = _make_zip_file({"inner.txt": b"inner content"})
        outer_files = {"outer.pdf": b"outer content", "inner.zip": inner_archive.getvalue()}
        outer_archive = _make_zip_file(outer_files)

        result = extractor.extract(outer_archive, "outer.zip")

        filenames = {f.filename for f in result.files}
        assert "outer.pdf" in filenames
        assert "inner.txt" in filenames

    def test_nested_zip_total_size_no_double_count(self) -> None:
        """嵌套解压 total_extracted_size 不双重计算"""
        extractor = ArchiveExtractor()

        inner_content = b"hello world"
        inner_archive = _make_zip_file({"inner.txt": inner_content})
        outer_content = b"outer content data"
        outer_files = {"outer.pdf": outer_content, "inner.zip": inner_archive.getvalue()}
        outer_archive = _make_zip_file(outer_files)

        result = extractor.extract(outer_archive, "outer.zip")

        expected = len(outer_content) + len(inner_content)
        assert result.total_extracted_size == expected

    def test_nested_tar_total_size_no_double_count(self) -> None:
        """嵌套 TAR 解压 total_extracted_size 不双重计算"""
        extractor = ArchiveExtractor()

        inner_buf = io.BytesIO()
        inner_content = b"hello world"
        info = tarfile.TarInfo(name="inner.txt")
        info.size = len(inner_content)
        tf_inner = tarfile.open(fileobj=inner_buf, mode="w:gz")
        tf_inner.addfile(info, io.BytesIO(inner_content))
        tf_inner.close()
        inner_buf.seek(0)

        outer_content = b"outer content data"
        outer_files = {"outer.pdf": outer_content, "inner.tar": inner_buf.getvalue()}
        outer_archive = _make_zip_file(outer_files)

        result = extractor.extract(outer_archive, "outer.zip")

        expected = len(outer_content) + len(inner_content)
        assert result.total_extracted_size == expected

    def test_nested_tar_extracted(self) -> None:
        """嵌套 TAR 被递归解压"""
        extractor = ArchiveExtractor()

        inner_buf = io.BytesIO()
        with tarfile.open(fileobj=inner_buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name="inner.txt")
            info.size = 12
            tf.addfile(info, io.BytesIO(b"inner content"))
        inner_buf.seek(0)

        outer_files = {"outer.pdf": b"outer content", "inner.tar": inner_buf.getvalue()}
        outer_archive = _make_zip_file(outer_files)

        result = extractor.extract(outer_archive, "outer.zip")

        filenames = {f.filename for f in result.files}
        assert "outer.pdf" in filenames
        assert "inner.txt" in filenames

    def test_deeply_nested_skipped_at_limit(self) -> None:
        """超过最大嵌套深度的压缩包被跳过"""
        extractor = ArchiveExtractor()

        archive = _make_zip_file({"deep.pdf": b"deep content"})
        name = "level0.zip"
        for i in range(MAX_NESTING_DEPTH + 1):
            archive = _make_zip_file({name: archive.getvalue()})
            name = f"level{i + 1}.zip"

        result = extractor.extract(archive, "deeply_nested.zip")

        assert any("深度超限" in w for w in result.warnings)


class TestArchiveExtractorFormatFilter:
    """验证格式过滤"""

    def test_only_supported_formats_extracted(self) -> None:
        """仅解压支持格式的文件"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file(
            {
                "doc.pdf": b"pdf",
                "data.csv": b"csv",
                "image.png": b"png",
                "readme.xyz": b"xyz",
                "script.sh": b"sh",
            }
        )

        result = extractor.extract(archive, "mixed.zip")

        filenames = {f.filename for f in result.files}
        assert "doc.pdf" in filenames
        assert "data.csv" in filenames
        assert "image.png" in filenames
        assert "readme.xyz" not in filenames
        assert "script.sh" not in filenames

    def test_mime_type_assigned_correctly(self) -> None:
        """正确分配 MIME 类型"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file({"test.pdf": b"pdf-content"})

        result = extractor.extract(archive, "mime.zip")

        assert result.files[0].mime_type == "application/pdf"


class TestArchiveExtractorExtractedFileMetadata:
    """验证解压文件元数据"""

    def test_extracted_file_has_correct_size(self) -> None:
        """解压文件大小正确"""
        content = b"hello world 12345"
        extractor = ArchiveExtractor()
        archive = _make_zip_file({"test.txt": content})

        result = extractor.extract(archive, "meta.zip")

        assert result.files[0].size == len(content)

    def test_extracted_file_has_depth_zero(self) -> None:
        """顶层解压文件 depth 为 0"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file({"test.txt": b"content"})

        result = extractor.extract(archive, "depth.zip")

        assert result.files[0].depth == 0

    def test_total_extracted_size_summed(self) -> None:
        """total_extracted_size 为所有文件大小之和"""
        extractor = ArchiveExtractor()
        archive = _make_zip_file(
            {
                "a.txt": b"12345",
                "b.txt": b"67890",
            }
        )

        result = extractor.extract(archive, "size.zip")

        assert result.total_extracted_size == 10
