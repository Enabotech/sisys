"""Acceptance 测试专属配置

本文件定义 acceptance 测试目录的专属 fixture 和 pytest hook：
- pytest_collection_modifyitems: 自动标记 @pytest.mark.acceptance 及服务依赖
- acceptance_env_config: session 级环境配置 fixture
- LLM 端点可达性探测 helper（防止内网不可达 endpoint 导致 fixture 误判可用）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any
from urllib.parse import urlparse

import pytest

from tests.environments import TestEnvConfig, get_test_env

# LLM 端点可达性探测超时（秒）：仅 TCP 连接探测，不等 HTTP 响应
_LLM_ENDPOINT_PROBE_TIMEOUT = 3.0

# BDD 调用层硬超时（秒）：防止 LLM 客户端内部 timeout 失效时 BDD 卡死
# 实际超时取 min(LLMConfig.timeout, _BDD_HARD_TIMEOUT)
_BDD_HARD_TIMEOUT = 30.0


def probe_llm_endpoint_reachable(endpoint: str | None) -> bool:
    """快速探测 LLM 端点 TCP 可达性，避免 fixture 误判导致测试卡死.

    仅做 TCP 握手（不发送 HTTP 请求），3 秒超时。
    - endpoint 为空（本地模型）→ 返回 True（litellm 默认本地可达）
    - TCP 连接成功 → 返回 True
    - 任何异常（DNS 失败/连接拒绝/超时）→ 返回 False

    Args:
        endpoint: LLM 端点 URL（如 http://172.21.96.1:8888/v1）

    Returns:
        True 如果 TCP 可达，False 否则
    """
    if not endpoint:
        return True  # 本地模型，依赖 litellm 默认端点
    try:
        parsed = urlparse(endpoint)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=_LLM_ENDPOINT_PROBE_TIMEOUT):
            return True
    except (OSError, socket.timeout, ValueError):
        return False


def run_with_bdd_timeout(
    event_loop: asyncio.AbstractEventLoop,
    coro: Any,
    cfg_timeout: float,
) -> Any:
    """在 event_loop 上运行协程，强制 BDD 硬超时保护.

    防止以下场景卡死整个 pytest session：
    1. LLM 客户端内部 timeout 配置错误（如默认 600s）
    2. 端点 TCP 黑洞但 HTTP 等待响应
    3. asyncio.wait_for 未正确传递给 litellm 内部 HTTP 客户端

    Args:
        event_loop: 模块级事件循环
        coro: 异步协程
        cfg_timeout: LLMConfig.timeout 值

    Returns:
        协程结果

    Raises:
        asyncio.TimeoutError: BDD 硬超时触发时
        其他异常: 透传原异常
    """
    effective_timeout = min(cfg_timeout, _BDD_HARD_TIMEOUT)
    return event_loop.run_until_complete(
        asyncio.wait_for(coro, timeout=effective_timeout),
    )


# 服务依赖关键词 → marker 映射表
_SERVICE_MARKERS: dict[str, str] = {
    "redis": "redis",
    "qdrant": "qdrant",
    "postgres": "database",
    "minio": "minio",
    "neo4j": "neo4j",
    "rabbitmq": "database",
}


@pytest.fixture(scope="session")
def acceptance_env_config() -> TestEnvConfig:
    """Acceptance 测试 session 级环境配置

    Returns:
        TestEnvConfig: 测试环境配置实例
    """
    return get_test_env()


def pytest_collection_modifyitems(config, items):
    """自动为 acceptance 目录下的测试添加 marker

    1. 所有 acceptance 测试添加 @pytest.mark.acceptance
    2. 根据文件名中的服务关键词添加服务依赖 marker

    Args:
        config: pytest 配置对象
        items: 收集到的测试项列表
    """
    for item in items:
        if "tests/acceptance" not in str(item.fspath):
            continue

        item.add_marker("acceptance")

        # 按文件名检测服务依赖并自动标记
        filename = str(item.fspath).lower()
        for keyword, marker in _SERVICE_MARKERS.items():
            if keyword in filename:
                item.add_marker(marker)
