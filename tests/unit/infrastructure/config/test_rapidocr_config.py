"""RapidOCRConfig 单元测试。

测试配置加载、环境变量注入、错误值处理。
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.rapidocr import RapidOCRConfig


class TestRapidOCRConfig:
    """RapidOCRConfig 测试套件。"""

    def test_default_values(self) -> None:
        """默认配置应为空模型目录和并发数 1。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("RAPIDOCR_MODEL_DIR", None)
            os.environ.pop("RAPIDOCR_MAX_CONCURRENCY", None)
            config = RapidOCRConfig.from_env()
            assert config.model_dir == ""
            assert config.max_concurrency == 1

    def test_from_env_reads_model_dir(self) -> None:
        """环境变量应被正确读取。"""
        with mock.patch.dict(os.environ, {"RAPIDOCR_MODEL_DIR": "/models/ocr"}):
            config = RapidOCRConfig.from_env()
            assert config.model_dir == "/models/ocr"

    def test_from_env_reads_concurrency(self) -> None:
        """环境变量应被正确读取并发数。"""
        with mock.patch.dict(os.environ, {"RAPIDOCR_MAX_CONCURRENCY": "4"}):
            config = RapidOCRConfig.from_env()
            assert config.max_concurrency == 4

    def test_from_env_invalid_concurrency_raises_error(self) -> None:
        """非法并发值应触发 ConfigurationError。"""
        with mock.patch.dict(os.environ, {"RAPIDOCR_MAX_CONCURRENCY": "abc"}):
            with pytest.raises(ConfigurationError, match="RAPIDOCR_MAX_CONCURRENCY"):
                RapidOCRConfig.from_env()

    def test_frozen_dataclass(self) -> None:
        """配置对象应不可变。"""
        config = RapidOCRConfig(model_dir="/test", max_concurrency=2)
        with pytest.raises(AttributeError):
            config.model_dir = "/other"  # type: ignore[misc]
