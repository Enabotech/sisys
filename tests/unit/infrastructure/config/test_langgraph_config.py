"""LangGraphConfig 配置单元测试

验证 from_env()、默认值、环境变量覆盖、frozen 特性

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from typing import Any, cast
from unittest.mock import patch

import pytest

from src.infrastructure.config.langgraph import LangGraphConfig


class TestLangGraphConfigDefaults:
    """LangGraphConfig 默认值测试"""

    def test_default_api_url(self) -> None:
        config = LangGraphConfig()
        assert config.api_url == "http://localhost:8000"

    def test_default_checkpoint_table(self) -> None:
        config = LangGraphConfig()
        assert config.checkpoint_table == "langgraph_checkpoints"

    def test_default_retry_max_attempts(self) -> None:
        config = LangGraphConfig()
        assert config.retry_max_attempts == 3

    def test_default_retry_delay_seconds(self) -> None:
        config = LangGraphConfig()
        assert config.retry_delay_seconds == 30

    def test_default_task_timeout_seconds(self) -> None:
        config = LangGraphConfig()
        assert config.task_timeout_seconds == 300

    def test_default_graph_timeout_seconds(self) -> None:
        config = LangGraphConfig()
        assert config.graph_timeout_seconds == 1800


class TestLangGraphConfigFromEnv:
    """LangGraphConfig from_env() 测试"""

    def test_from_env_with_defaults(self) -> None:
        config = LangGraphConfig.from_env()
        assert isinstance(config, LangGraphConfig)
        assert config.api_url == "http://localhost:8000"

    @patch.dict(os.environ, {"LANGGRAPH_API_URL": "http://custom:8123"})
    def test_from_env_override_api_url(self) -> None:
        config = LangGraphConfig.from_env()
        assert config.api_url == "http://custom:8123"

    @patch.dict(os.environ, {"LANGGRAPH_CHECKPOINT_TABLE": "custom_checkpoints"})
    def test_from_env_override_checkpoint_table(self) -> None:
        config = LangGraphConfig.from_env()
        assert config.checkpoint_table == "custom_checkpoints"

    @patch.dict(os.environ, {"LANGGRAPH_RETRY_MAX_ATTEMPTS": "5"})
    def test_from_env_override_retry_attempts(self) -> None:
        config = LangGraphConfig.from_env()
        assert config.retry_max_attempts == 5


class TestLangGraphConfigFrozen:
    """LangGraphConfig frozen 特性测试"""

    def test_frozen_dataclass(self) -> None:
        config = LangGraphConfig()
        with pytest.raises(AttributeError):
            cast(Any, config).api_url = "http://changed"


class TestLangGraphConfigEmptyEnv:
    """空字符串环境变量处理测试"""

    @patch.dict(os.environ, {"LANGGRAPH_RETRY_MAX_ATTEMPTS": ""})
    def test_from_env_empty_string_uses_default(self) -> None:
        """空字符串环境变量应使用默认值"""
        config = LangGraphConfig.from_env()
        assert config.retry_max_attempts == 3

    @patch.dict(os.environ, {"LANGGRAPH_RETRY_MAX_ATTEMPTS": "abc"})
    def test_from_env_invalid_int_raises_value_error(self) -> None:
        """非数字字符串应抛出包含键名的 ValueError"""
        with pytest.raises(ValueError, match="LANGGRAPH_RETRY_MAX_ATTEMPTS"):
            LangGraphConfig.from_env()

    @patch.dict(os.environ, {"LANGGRAPH_API_URL": ""})
    def test_from_env_empty_api_url_uses_default(self) -> None:
        """空字符串 API URL 应使用默认值"""
        config = LangGraphConfig.from_env()
        assert config.api_url == "http://localhost:8000"

    @patch.dict(os.environ, {"LANGGRAPH_GRAPH_TIMEOUT_SECONDS": "7200"})
    def test_from_env_valid_override(self) -> None:
        """有效数字覆盖应正常工作"""
        config = LangGraphConfig.from_env()
        assert config.graph_timeout_seconds == 7200
