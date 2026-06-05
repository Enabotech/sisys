"""Unit 测试专属配置

本文件定义 unit 测试目录的专属 fixture 和 pytest hook：
- pytest_collection_modifyitems: 自动为 unit 目录下的测试添加 @pytest.mark.unit
- 导入根 fixtures.py 中适用于 unit 测试的 fixture
- prefect_test_settings: session 级别禁用 Prefect API 日志（测试环境无 API server）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from tests.fixtures import (  # noqa: F401
    isolated_tenant,
    reset_test_environment,
    resolver,
    test_tenant,
)


@pytest.fixture(scope="session", autouse=True)
def _prefect_test_settings() -> Generator[None, None, None]:
    """禁用 Prefect API 日志处理器（测试环境无 Prefect API server）

    在 unit 测试中，task.fn() 直接调用底层函数，无 flow run 上下文。
    默认的 API log handler 无法发送日志到不存在的 API server，产生警告。
    正确的修复是在测试环境中禁用 API 日志功能（与生产环境配置区分），
    而非抑制误报。

    Prefect 官方文档也建议在无 API server 的环境中关闭此功能。
    """
    from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings

    with temporary_settings({PREFECT_LOGGING_TO_API_ENABLED: False}):
        yield


def pytest_collection_modifyitems(config, items):
    """自动为 unit 目录下的测试添加 @pytest.mark.unit

    Args:
        config: pytest 配置对象
        items: 收集到的测试项列表
    """
    for item in items:
        if "tests/unit" in str(item.fspath):
            item.add_marker("unit")
