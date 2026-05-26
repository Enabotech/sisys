"""视频格式处理器单元测试

验证 VideoFormatHandler 视频扩展名识别和 ffmpeg.probe() 元数据提取
"""

from __future__ import annotations

from unittest.mock import patch

from plugins.crawler.core.format.handlers.video_handler import VideoFormatHandler
from plugins.crawler.core.value_objects import FileMetadata


class TestVideoFormatHandler:
    """VideoFormatHandler 扩展名/MIME 识别测试"""

    def setup_method(self) -> None:
        self.handler = VideoFormatHandler()

    def test_can_handle_mp4(self) -> None:
        """应识别 .mp4 扩展名"""
        assert self.handler.can_handle("video.mp4", "")

    def test_can_handle_avi(self) -> None:
        """应识别 .avi 扩展名"""
        assert self.handler.can_handle("video.avi", "")

    def test_can_handle_mov(self) -> None:
        """应识别 .mov 扩展名"""
        assert self.handler.can_handle("video.mov", "")

    def test_can_handle_mkv(self) -> None:
        """应识别 .mkv 扩展名"""
        assert self.handler.can_handle("video.mkv", "")

    def test_can_handle_webm(self) -> None:
        """应识别 .webm 扩展名"""
        assert self.handler.can_handle("video.webm", "")

    def test_can_handle_wmv(self) -> None:
        """应识别 .wmv 扩展名"""
        assert self.handler.can_handle("video.wmv", "")

    def test_can_handle_flv(self) -> None:
        """应识别 .flv 扩展名"""
        assert self.handler.can_handle("video.flv", "")

    def test_can_handle_m4v(self) -> None:
        """应识别 .m4v 扩展名"""
        assert self.handler.can_handle("video.m4v", "")

    def test_can_handle_3gp(self) -> None:
        """应识别 .3gp 扩展名"""
        assert self.handler.can_handle("video.3gp", "")

    def test_can_handle_video_mime(self) -> None:
        """应通过视频 MIME 类型识别"""
        assert self.handler.can_handle("unknown", "video/mp4")

    def test_can_handle_mkv_mime(self) -> None:
        """应通过 video/x-matroska MIME 类型识别"""
        assert self.handler.can_handle("unknown", "video/x-matroska")

    def test_cannot_handle_mp3(self) -> None:
        """不应处理音频格式 mp3"""
        assert not self.handler.can_handle("audio.mp3", "")

    def test_cannot_handle_pdf(self) -> None:
        """不应处理 PDF"""
        assert not self.handler.can_handle("test.pdf", "application/pdf")

    def test_supported_extensions(self) -> None:
        """supported_extensions 应包含全部视频格式"""
        expected = {"mp4", "avi", "mov", "mkv", "webm", "wmv", "flv", "m4v", "3gp"}
        assert set(self.handler.supported_extensions) == expected


class TestVideoMetadataExtraction:
    """VideoFormatHandler 元数据提取测试"""

    def setup_method(self) -> None:
        self.handler = VideoFormatHandler()

    @patch("ffmpeg.probe")
    def test_title_and_artist_extracted(self, mock_probe) -> None:
        """应从 ffmpeg.probe format.tags 提取 title 和 artist"""
        mock_probe.return_value = {
            "format": {
                "tags": {
                    "title": "产品发布会录像",
                    "artist": "市场部",
                },
            },
        }

        meta = self.handler.extract_metadata("/fake/path.mp4")
        assert meta.title == "产品发布会录像"
        assert meta.author == "市场部"

    @patch("ffmpeg.probe")
    def test_uppercase_tags(self, mock_probe) -> None:
        """应兼容大写 TAG 键名"""
        mock_probe.return_value = {
            "format": {
                "tags": {
                    "TITLE": "大写标题",
                    "ARTIST": "大写作者",
                },
            },
        }

        meta = self.handler.extract_metadata("/fake/path.mp4")
        assert meta.title == "大写标题"
        assert meta.author == "大写作者"

    @patch("ffmpeg.probe")
    def test_no_tags_returns_empty(self, mock_probe) -> None:
        """无 tags 时应返回空元数据"""
        mock_probe.return_value = {"format": {}}

        meta = self.handler.extract_metadata("/fake/path.mp4")
        assert meta == FileMetadata()

    @patch("ffmpeg.probe")
    def test_no_format_returns_empty(self, mock_probe) -> None:
        """无 format 节点时应返回空元数据"""
        mock_probe.return_value = {}

        meta = self.handler.extract_metadata("/fake/path.mp4")
        assert meta == FileMetadata()

    def test_probe_exception_returns_empty(self) -> None:
        """ffmpeg.probe 异常时应返回空元数据"""
        meta = self.handler.extract_metadata("/nonexistent/file.mp4")
        assert meta == FileMetadata()

    @patch("ffmpeg.probe")
    def test_probe_error_returns_empty(self, mock_probe) -> None:
        """ffmpeg.probe 抛出 Error 时应返回空元数据"""
        mock_probe.side_effect = Exception("ffprobe error")

        meta = self.handler.extract_metadata("/fake/path.mp4")
        assert meta == FileMetadata()
