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
        prompt, completion = asyncio.get_event_loop().run_until_complete(estimator.estimate("local", "qwen2.5:7b"))
        assert prompt == 256
        assert completion == 512

    def test_local_case_insensitive(self) -> None:
        """路由类型不区分大小写."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.get_event_loop().run_until_complete(estimator.estimate("LOCAL", "qwen2.5:7b"))
        assert prompt == 256
        assert completion == 512


class TestStaticTokenEstimatorCloud:
    """云端模型估算测试."""

    def test_cloud_estimation(self) -> None:
        """云端模型估算: prompt=512, completion=1024."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.get_event_loop().run_until_complete(estimator.estimate("cloud", "MiniMax-M2.7"))
        assert prompt == 512
        assert completion == 1024

    def test_unknown_route_type_defaults_to_cloud(self) -> None:
        """未知路由类型默认使用云端估算."""
        estimator = StaticTokenEstimator()
        prompt, completion = asyncio.get_event_loop().run_until_complete(estimator.estimate("unknown", "test-model"))
        assert prompt == 512
        assert completion == 1024
