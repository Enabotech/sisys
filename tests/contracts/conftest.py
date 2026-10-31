"""公共 fixture 定义 - 端口契约测试基础设施

本文件定义所有契约测试共享的 fixture：
- registry: 提供已初始化的端口注册中心
- resolver: 提供全局端口解析器（get_resolver——SINGLETON 缓存复用）

注意: bootstrap() 由 tests/conftest.py 的 _bootstrap_once 自动调用
"""

from __future__ import annotations

import pytest

from src.domain.ports.registry import _global_registry
from src.domain.ports.resolver import get_resolver


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
    """提供全局端口解析器（核销 R2 批 K14——原裸 ``Resolver()`` 新建实例
    缓存对 SINGLETON 端口绕过生命周期强制重构造，构造有注册副作用的实现
    （metrics→Prometheus Duplicated timeseries）必炸；get_resolver 复用
    全局缓存，与 test_port_contract_application 的 F6 适配形态一致）.

    Returns:
        Resolver: 全局端口解析器实例
    """
    return get_resolver()
