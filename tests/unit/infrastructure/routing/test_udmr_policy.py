"""Unit tests for StaticUdmrPolicy.

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

import pytest

from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask
from src.infrastructure.config.udmr import CloudModelConfig
from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy


def _make_cloud(
    model: str = "MiniMax-M2.7",
    enabled: bool = True,
    api_type: Literal["openai", "anthropic", "openai_responses"] = "anthropic",
) -> CloudModelConfig:
    """辅助构造 CloudModelConfig."""
    return CloudModelConfig(
        api_type=api_type,
        endpoint="https://api.example.com",
        api_key="TESTING_DUMMY_KEY",
        model=model,
        enabled=enabled,
        max_tokens=4096 if api_type == "anthropic" else None,
    )


def _make_task(**kwargs: Any) -> UDMRTask:
    """辅助构造 UDMRTask."""
    defaults: dict[str, Any] = {
        "task_id": uuid4(),
        "input": "test input",
        "data_residency": "CHINA_DOMESTIC",
    }
    defaults.update(kwargs)
    return UDMRTask(**defaults)


def _make_compliance(
    allowed: bool = True,
    forced_local: bool = False,
) -> ComplianceResult:
    """辅助构造 ComplianceResult."""
    return ComplianceResult(allowed=allowed, forced_local=forced_local)


# ===================================================================
# 初始化测试
# ===================================================================


class TestStaticUdmrPolicyInit:
    """StaticUdmrPolicy 初始化测试."""

    def test_init_with_cloud_configs(self) -> None:
        """应正确存储云端配置和本地模型."""
        clouds = [_make_cloud("model-a"), _make_cloud("model-b", enabled=False)]
        policy = StaticUdmrPolicy(cloud_configs=clouds, local_model="qwen2.5:7b")
        assert policy._local_model == "qwen2.5:7b"

    def test_init_empty_clouds(self) -> None:
        """无云端配置时仍可初始化."""
        policy = StaticUdmrPolicy(cloud_configs=[], local_model="qwen2.5:7b")
        assert policy._local_model == "qwen2.5:7b"


# ===================================================================
# 云端优先策略测试
# ===================================================================


class TestStaticUdmrPolicyCloudFirst:
    """云端优先路由测试."""

    @pytest.mark.asyncio
    async def test_cloud_first_when_available(self) -> None:
        """合规通过 + 云端可用 → cloud + 第一个 enabled 模型."""
        clouds = [_make_cloud("MiniMax-M2.7"), _make_cloud("deepseek-chat")]
        policy = StaticUdmrPolicy(cloud_configs=clouds, local_model="qwen2.5:7b")
        task = _make_task()
        compliance = _make_compliance(allowed=True, forced_local=False)

        route_type, model, fallback = await policy.route(task, compliance)

        assert route_type == "cloud"
        assert model == "MiniMax-M2.7"
        assert fallback is None

    @pytest.mark.asyncio
    async def test_skips_disabled_clouds(self) -> None:
        """应跳过 disabled 的云端模型."""
        clouds = [_make_cloud("model-a", enabled=False), _make_cloud("model-b")]
        policy = StaticUdmrPolicy(cloud_configs=clouds, local_model="qwen2.5:7b")
        task = _make_task()
        compliance = _make_compliance()

        route_type, model, _ = await policy.route(task, compliance)

        assert route_type == "cloud"
        assert model == "model-b"

    @pytest.mark.asyncio
    async def test_fallback_to_local_when_all_clouds_disabled(self) -> None:
        """所有云端 disabled → local + fallback_reason=unavailable."""
        clouds = [_make_cloud("model-a", enabled=False)]
        policy = StaticUdmrPolicy(cloud_configs=clouds, local_model="qwen2.5:7b")
        task = _make_task()
        compliance = _make_compliance()

        route_type, model, fallback = await policy.route(task, compliance)

        assert route_type == "local"
        assert model == "qwen2.5:7b"
        assert fallback == "unavailable"

    @pytest.mark.asyncio
    async def test_fallback_to_local_when_no_clouds(self) -> None:
        """无云端配置 → local + fallback_reason=unavailable."""
        policy = StaticUdmrPolicy(cloud_configs=[], local_model="qwen2.5:7b")
        task = _make_task()
        compliance = _make_compliance()

        route_type, model, fallback = await policy.route(task, compliance)

        assert route_type == "local"
        assert model == "qwen2.5:7b"
        assert fallback == "unavailable"


# ===================================================================
# L1 合规强制本地测试
# ===================================================================


class TestStaticUdmrPolicyCompliance:
    """L1 合规强制本地路由测试."""

    @pytest.mark.asyncio
    async def test_forced_local_overrides_cloud(self) -> None:
        """forced_local=True → local（即使云端可用）."""
        clouds = [_make_cloud("MiniMax-M2.7")]
        policy = StaticUdmrPolicy(cloud_configs=clouds, local_model="qwen2.5:7b")
        task = _make_task()
        compliance = _make_compliance(allowed=True, forced_local=True)

        route_type, model, fallback = await policy.route(task, compliance)

        assert route_type == "local"
        assert model == "qwen2.5:7b"
        assert fallback is None


# ===================================================================
# local_first 模式测试
# ===================================================================


class TestStaticUdmrPolicyLocalFirst:
    """本地优先模式测试."""

    @pytest.mark.asyncio
    async def test_local_first_uses_local(self) -> None:
        """local_first=True → local（即使云端可用）."""
        clouds = [_make_cloud("MiniMax-M2.7")]
        policy = StaticUdmrPolicy(
            cloud_configs=clouds,
            local_model="qwen2.5:7b",
            local_first=True,
        )
        task = _make_task()
        compliance = _make_compliance()

        route_type, model, fallback = await policy.route(task, compliance)

        assert route_type == "local"
        assert model == "qwen2.5:7b"
        assert fallback is None
