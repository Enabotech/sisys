"""PrefectConfig 配置单元测试

验证 from_env()、默认值、环境变量覆盖、frozen 特性
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.prefect import PrefectConfig


class TestPrefectConfigDefaults:
    """PrefectConfig 默认值测试"""

    def test_default_api_url(self) -> None:
        config = PrefectConfig()
        assert config.api_url == "http://localhost:4200/api"

    def test_default_work_pool_name(self) -> None:
        config = PrefectConfig()
        assert config.work_pool_name == "sisys-worker-pool"

    def test_default_retry_max_attempts(self) -> None:
        config = PrefectConfig()
        assert config.retry_max_attempts == 3

    def test_default_retry_delay_seconds(self) -> None:
        config = PrefectConfig()
        assert config.retry_delay_seconds == 30

    def test_default_task_timeout_seconds(self) -> None:
        config = PrefectConfig()
        assert config.task_timeout_seconds == 300

    def test_default_flow_timeout_seconds(self) -> None:
        config = PrefectConfig()
        assert config.flow_timeout_seconds == 3600


class TestPrefectConfigFromEnv:
    """PrefectConfig from_env() 测试"""

    def test_from_env_with_defaults(self) -> None:
        config = PrefectConfig.from_env()
        assert isinstance(config, PrefectConfig)
        assert config.api_url == "http://localhost:4200/api"

    @patch.dict(os.environ, {"PREFECT_API_URL": "http://custom:4200/api"})
    def test_from_env_override_api_url(self) -> None:
        config = PrefectConfig.from_env()
        assert config.api_url == "http://custom:4200/api"

    @patch.dict(os.environ, {"PREFECT_WORK_POOL_NAME": "custom-pool"})
    def test_from_env_override_work_pool(self) -> None:
        config = PrefectConfig.from_env()
        assert config.work_pool_name == "custom-pool"

    @patch.dict(os.environ, {"PREFECT_RETRY_MAX_ATTEMPTS": "5"})
    def test_from_env_override_retry_attempts(self) -> None:
        config = PrefectConfig.from_env()
        assert config.retry_max_attempts == 5


class TestPrefectConfigFrozen:
    """PrefectConfig frozen 特性测试"""

    def test_frozen_dataclass(self) -> None:
        config = PrefectConfig()
        with pytest.raises(AttributeError):
            config.api_url = "http://changed"  # type: ignore[misc]
