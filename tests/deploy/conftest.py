"""Deploy 测试专属配置

本文件定义 deploy 测试目录的专属 fixture 和 pytest hook：
- pytest_collection_modifyitems: 自动为 deploy 目录下的测试添加 @pytest.mark.k8s
- 导入 config.py 和 k8s_helpers.py 的工具函数

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from tests.deploy.config import TestConfig
from tests.deploy.k8s_helpers import run_kubectl

__all__ = ["TestConfig", "run_kubectl"]


def pytest_collection_modifyitems(config, items):
    """自动为 deploy 目录下的测试添加 @pytest.mark.k8s

    Args:
        config: pytest 配置对象
        items: 收集到的测试项列表
    """
    for item in items:
        if "tests/deploy" in str(item.fspath):
            item.add_marker("k8s")
