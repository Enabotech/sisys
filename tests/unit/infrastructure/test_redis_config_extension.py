"""RedisConfig 扩展字段测试。

验证 retry_on_timeout 和 default_ttl 新字段。
"""

from __future__ import annotations

import os
from unittest.mock import patch

from src.infrastructure.config.redis import RedisConfig


class TestRedisConfigExtension:
    """RedisConfig 扩展字段测试。"""

    def test_retry_on_timeout_default_value(self) -> None:
        """retry_on_timeout 默认值为 True。"""
        config = RedisConfig()
        assert config.retry_on_timeout is True

    def test_default_ttl_default_value(self) -> None:
        """default_ttl 默认值为 86400（24 小时）。"""
        config = RedisConfig()
        assert config.default_ttl == 86400

    def test_retry_on_timeout_custom_value(self) -> None:
        """retry_on_timeout 可自定义。"""
        config = RedisConfig(retry_on_timeout=False)
        assert config.retry_on_timeout is False

    def test_default_ttl_custom_value(self) -> None:
        """default_ttl 可自定义。"""
        config = RedisConfig(default_ttl=3600)
        assert config.default_ttl == 3600

    def test_from_env_new_fields(self) -> None:
        """from_env() 支持新环境变量。"""
        with patch.dict(
            os.environ,
            {
                "REDIS_RETRY_ON_TIMEOUT": "false",
                "REDIS_DEFAULT_TTL": "7200",
            },
            clear=False,
        ):
            config = RedisConfig.from_env()
            assert config.retry_on_timeout is False
            assert config.default_ttl == 7200

    def test_from_env_backward_compatible(self) -> None:
        """from_env() 向后兼容：新环境变量未设置时使用默认值。"""
        env_vars = {
            "REDIS_HOST": "testhost",
            "REDIS_PORT": "6380",
            "REDIS_DB": "1",
            "REDIS_MAX_CONNECTIONS": "20",
            "REDIS_SOCKET_TIMEOUT": "10.0",
        }
        # 清除新环境变量（如果存在）
        for key in ["REDIS_RETRY_ON_TIMEOUT", "REDIS_DEFAULT_TTL"]:
            os.environ.pop(key, None)

        with patch.dict(os.environ, env_vars, clear=False):
            config = RedisConfig.from_env()
            # 已有字段
            assert config.host == "testhost"
            assert config.port == 6380
            assert config.db == 1
            assert config.max_connections == 20
            assert config.socket_timeout == 10.0
            # 新字段使用默认值
            assert config.retry_on_timeout is True
            assert config.default_ttl == 86400
