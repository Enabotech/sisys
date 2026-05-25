"""Unit 测试专属配置

本文件定义 unit 测试目录的专属 fixture 和 pytest hook：
- pytest_collection_modifyitems: 自动为 unit 目录下的测试添加 @pytest.mark.unit
- 导入根 fixtures.py 中适用于 unit 测试的 fixture

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from tests.fixtures import (  # noqa: F401
    isolated_tenant,
    reset_test_environment,
    resolver,
    test_tenant,
)


def pytest_collection_modifyitems(config, items):
    """自动为 unit 目录下的测试添加 @pytest.mark.unit

    Args:
        config: pytest 配置对象
        items: 收集到的测试项列表
    """
    for item in items:
        if "tests/unit" in str(item.fspath):
            item.add_marker("unit")
