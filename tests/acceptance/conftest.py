"""Acceptance 测试专属配置

本文件定义 acceptance 测试目录的专属 fixture 和 pytest hook：
- pytest_collection_modifyitems: 自动标记 @pytest.mark.acceptance 及服务依赖
- acceptance_env_config: session 级环境配置 fixture

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import pytest

from tests.environments import TestEnvConfig, get_test_env

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
