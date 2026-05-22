"""Unit tests for CloudHealthChecker.

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.infrastructure.config.udmr import CloudModelConfig
from src.infrastructure.external_services.llm.cloud_health_checker import (
    CloudHealthChecker,
)


def _make_cloud(model: str = "MiniMax-M2.7") -> CloudModelConfig:
    """辅助构造 CloudModelConfig."""
    return CloudModelConfig(
        api_type="anthropic",
        endpoint="https://api.example.com",
        api_key="TESTING_DUMMY_KEY",
        model=model,
        enabled=True,
        max_tokens=4096,
    )


# ===================================================================
# 初始化测试
# ===================================================================


class TestCloudHealthCheckerInit:
    """初始化测试."""

    def test_init_with_cloud_configs(self) -> None:
        """应存储云端配置和超时."""
        clouds = [_make_cloud("model-a")]
        checker = CloudHealthChecker(cloud_configs=clouds, timeout=30)
        assert checker._timeout == 30

    def test_init_empty_clouds(self) -> None:
        """无云端配置时仍可初始化."""
        checker = CloudHealthChecker(cloud_configs=[], timeout=30)
        assert checker._timeout == 30

    def test_init_default_timeout(self) -> None:
        """默认超时为 600 秒."""
        checker = CloudHealthChecker(cloud_configs=[])
        assert checker._timeout == 600


# ===================================================================
# check() 测试
# ===================================================================


class TestCloudHealthCheckerCheck:
    """check() 测试."""

    @pytest.mark.asyncio
    async def test_check_returns_true_when_healthy(self) -> None:
        """云端可用时返回 True."""
        clouds = [_make_cloud()]
        checker = CloudHealthChecker(cloud_configs=clouds, timeout=30)
        with patch.object(checker, "_check_model_health", return_value=True):
            result = await checker.check()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_returns_false_when_unhealthy(self) -> None:
        """云端不可用时返回 False."""
        clouds = [_make_cloud()]
        checker = CloudHealthChecker(cloud_configs=clouds, timeout=30)
        with patch.object(checker, "_check_model_health", return_value=False):
            result = await checker.check()
            assert result is False

    @pytest.mark.asyncio
    async def test_check_skips_disabled_clouds(self) -> None:
        """应跳过 disabled 的云端模型."""
        clouds = [_make_cloud(), CloudModelConfig(model="disabled-model", enabled=False)]
        checker = CloudHealthChecker(cloud_configs=clouds, timeout=30)
        with patch.object(checker, "_check_model_health", return_value=True) as mock:
            await checker.check()
            # 只检查第一个 enabled 模型
            mock.assert_called_once_with(clouds[0])

    @pytest.mark.asyncio
    async def test_check_returns_false_when_no_enabled_clouds(self) -> None:
        """无 enabled 云端模型时返回 False."""
        clouds = [CloudModelConfig(model="disabled", enabled=False)]
        checker = CloudHealthChecker(cloud_configs=clouds, timeout=30)
        result = await checker.check()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_returns_false_when_no_clouds(self) -> None:
        """无云端配置时返回 False."""
        checker = CloudHealthChecker(cloud_configs=[], timeout=30)
        result = await checker.check()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_returns_false_on_exception(self) -> None:
        """检查异常时返回 False."""
        clouds = [_make_cloud()]
        checker = CloudHealthChecker(cloud_configs=clouds, timeout=30)
        with patch.object(checker, "_check_model_health", side_effect=Exception("error")):
            result = await checker.check()
            assert result is False


# ===================================================================
# close() 测试
# ===================================================================


class TestCloudHealthCheckerClose:
    """close() 测试."""

    @pytest.mark.asyncio
    async def test_close_releases_resources(self) -> None:
        """close() 应释放资源（无异常）."""
        checker = CloudHealthChecker(cloud_configs=[])
        await checker.close()  # 无异常即为成功

    @pytest.mark.asyncio
    async def test_close_multiple_calls(self) -> None:
        """多次调用 close() 应无异常."""
        checker = CloudHealthChecker(cloud_configs=[])
        await checker.close()
        await checker.close()  # 重复调用无异常
