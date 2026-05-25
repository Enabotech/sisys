"""StaticTokenEstimator 单元测试.

验证静态 Token 估算器的 MVP 策略：
- 本地模型估算: prompt=256, completion=512
- 云端模型估算: prompt=512, completion=1024
- 路由类型不区分大小写
- 未知路由类型默认使用云端估算

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
import logging

import pytest

from src.domain.ports.token_estimator import TokenEstimatorPort
from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator


class TestStaticTokenEstimatorProtocol:
    """协议一致性测试."""

    def test_implements_token_estimator_port(self) -> None:
        """StaticTokenEstimator 应实现 TokenEstimatorPort."""
        estimator = StaticTokenEstimator()
        assert isinstance(estimator, TokenEstimatorPort)

    def test_has_estimate_method(self) -> None:
        """必须包含 estimate 方法."""
        estimator = StaticTokenEstimator()
        assert hasattr(estimator, "estimate")
        assert callable(estimator.estimate)


class TestStaticTokenEstimatorLocal:
    """本地模型估算测试."""

    def test_local_estimation(self) -> None:
        """本地模型估算: prompt=256, completion=512."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.run(estimator.estimate("local", "qwen2.5:7b"))
        assert prompt == 256
        assert completion == 512

    def test_local_case_insensitive(self) -> None:
        """路由类型不区分大小写."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.run(estimator.estimate("LOCAL", "qwen2.5:7b"))
        assert prompt == 256
        assert completion == 512


class TestStaticTokenEstimatorCloud:
    """云端模型估算测试."""

    def test_cloud_estimation(self) -> None:
        """云端模型估算: prompt=512, completion=1024."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.run(estimator.estimate("cloud", "MiniMax-M2.7"))
        assert prompt == 512
        assert completion == 1024

    def test_unknown_route_type_defaults_to_cloud(self) -> None:
        """未知路由类型默认使用云端估算."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.run(estimator.estimate("unknown", "test-model"))
        assert prompt == 512
        assert completion == 1024


class TestStaticTokenEstimatorValidation:
    """StaticTokenEstimator 输入验证测试."""

    def test_empty_route_type_raises(self) -> None:
        """空 route_type 应抛出 ValueError."""
        estimator = StaticTokenEstimator()
        with pytest.raises(ValueError, match="route_type"):
            asyncio.run(estimator.estimate("", "qwen2.5:7b"))

    def test_whitespace_route_type_raises(self) -> None:
        """空白 route_type 应抛出 ValueError."""
        estimator = StaticTokenEstimator()
        with pytest.raises(ValueError, match="route_type"):
            asyncio.run(estimator.estimate("   ", "qwen2.5:7b"))


class TestStaticTokenEstimatorWarningLog:
    """WARNING 日志标识测试."""

    def test_estimate_logs_warning_for_local(self, caplog: pytest.LogCaptureFixture) -> None:
        """本地估算应输出 WARNING 日志."""
        estimator = StaticTokenEstimator()
        with caplog.at_level(logging.WARNING, logger="src.infrastructure.monitoring.static_token_estimator"):
            asyncio.run(estimator.estimate("local", "qwen2.5:7b"))
        assert any("StaticTokenEstimator 返回估算值" in r.message for r in caplog.records)

    def test_estimate_logs_warning_for_cloud(self, caplog: pytest.LogCaptureFixture) -> None:
        """云端估算应输出 WARNING 日志."""
        estimator = StaticTokenEstimator()
        with caplog.at_level(logging.WARNING, logger="src.infrastructure.monitoring.static_token_estimator"):
            asyncio.run(estimator.estimate("cloud", "MiniMax-M2.7"))
        assert any("StaticTokenEstimator 返回估算值" in r.message for r in caplog.records)
        assert any("route_type=cloud" in r.message for r in caplog.records)
