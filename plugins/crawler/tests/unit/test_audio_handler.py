"""音频格式处理器单元测试

验证 AudioFormatHandler 音频扩展名识别和 tinytag 元数据提取
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from plugins.crawler.core.format.handlers.audio_handler import AudioFormatHandler
from plugins.crawler.core.value_objects import FileMetadata


class TestAudioFormatHandler:
    """AudioFormatHandler 扩展名/MIME 识别测试"""

    def setup_method(self) -> None:
        self.handler = AudioFormatHandler()

    def test_can_handle_mp3(self) -> None:
        """应识别 .mp3 扩展名"""
        assert self.handler.can_handle("audio.mp3", "")

    def test_can_handle_wav(self) -> None:
        """应识别 .wav 扩展名"""
        assert self.handler.can_handle("audio.wav", "")

    def test_can_handle_flac(self) -> None:
        """应识别 .flac 扩展名"""
        assert self.handler.can_handle("music.flac", "")

    def test_can_handle_ogg(self) -> None:
        """应识别 .ogg 扩展名"""
        assert self.handler.can_handle("audio.ogg", "")

    def test_can_handle_aac(self) -> None:
        """应识别 .aac 扩展名"""
        assert self.handler.can_handle("audio.aac", "")

    def test_can_handle_wma(self) -> None:
        """应识别 .wma 扩展名"""
        assert self.handler.can_handle("audio.wma", "")

    def test_can_handle_m4a(self) -> None:
        """应识别 .m4a 扩展名"""
        assert self.handler.can_handle("audio.m4a", "")

    def test_can_handle_audio_mime(self) -> None:
        """应通过音频 MIME 类型识别"""
        assert self.handler.can_handle("unknown", "audio/mpeg")

    def test_can_handle_wav_mime(self) -> None:
        """应通过 audio/wav MIME 类型识别"""
        assert self.handler.can_handle("unknown", "audio/wav")

    def test_cannot_handle_mp4(self) -> None:
        """不应处理视频格式 mp4"""
        assert not self.handler.can_handle("video.mp4", "")

    def test_cannot_handle_pdf(self) -> None:
        """不应处理 PDF"""
        assert not self.handler.can_handle("test.pdf", "application/pdf")

    def test_supported_extensions(self) -> None:
        """supported_extensions 应包含全部音频格式"""
        expected = {"mp3", "wav", "ogg", "flac", "aac", "wma", "m4a"}
        assert set(self.handler.supported_extensions) == expected


class TestAudioMetadataExtraction:
    """AudioFormatHandler 元数据提取测试"""

    def setup_method(self) -> None:
        self.handler = AudioFormatHandler()

    def test_extract_returns_empty_on_invalid_file(self) -> None:
        """无效文件应返回空元数据"""
        meta = self.handler.extract_metadata("/nonexistent/file.mp3")
        assert meta == FileMetadata()

    def test_extract_returns_empty_on_empty_file(self) -> None:
        """空文件应返回空元数据"""
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(b"")
        tmp.close()
        try:
            meta = self.handler.extract_metadata(tmp.name)
            assert meta == FileMetadata()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    @patch("tinytag.TinyTag.get")
    def test_title_and_artist_extracted(self, mock_get) -> None:
        """应从 tinytag 提取 title 和 artist"""
        tag = MagicMock()
        tag.title = "会议录音"
        tag.artist = "张三"
        mock_get.return_value = tag

        meta = self.handler.extract_metadata("/fake/path.mp3")
        assert meta.title == "会议录音"
        assert meta.author == "张三"

    @patch("tinytag.TinyTag.get")
    def test_no_title_returns_empty(self, mock_get) -> None:
        """tinytag 无 title 时应返回空 title"""
        tag = MagicMock()
        tag.title = None
        tag.artist = None
        mock_get.return_value = tag

        meta = self.handler.extract_metadata("/fake/path.mp3")
        assert meta.title == ""
        assert meta.author == ""

    @patch("tinytag.TinyTag.get")
    def test_tinytag_exception_returns_empty(self, mock_get) -> None:
        """tinytag 异常时应返回空元数据"""
        mock_get.side_effect = Exception("parse error")

        meta = self.handler.extract_metadata("/fake/path.mp3")
        assert meta == FileMetadata()
