"""公共 fixture 定义 - 端口契约测试基础设施

本文件定义所有契约测试共享的 fixture：
- registry: 提供已初始化的端口注册中心
- resolver: 提供已初始化的端口解析器

注意: bootstrap() 由 tests/conftest.py 的 _bootstrap_once 自动调用
"""

from __future__ import annotations

import pytest

from src.domain.ports.registry import _global_registry
from src.domain.ports.resolver import Resolver


@pytest.fixture(scope="session")
def registry():
    """提供已初始化的端口注册中心

    bootstrap() 由 tests/conftest.py 的 _bootstrap_once 自动调用，
    无需在本文件中重复调用

    Returns:
        PortRegistry: 全局端口注册中心实例
    """
    return _global_registry


@pytest.fixture(scope="session")
def resolver():
    """提供已初始化的 Resolver 实例

    Returns:
        Resolver: 端口解析器实例
    """
    return Resolver()
