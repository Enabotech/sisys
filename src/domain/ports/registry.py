"""SISYS 领域层端口注册中心模块

提供六边形架构下所有端口契约的统一注册管理
端口注册时附带元数据（名称、版本、接口、实现、模块）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


class Lifetime(Enum):
    """端口生命周期管理策略"""

    TRANSIENT = "transient"  # New instance per request
    SCOPED = "scoped"  # Single instance per scope
    SINGLETON = "singleton"  # Global single instance


@dataclass(frozen=True)
class PortSpec:
    """端口规格元数据

    Attributes:
        name: 唯一端口名称
        version: 语义化版本号
        interface: 协议接口类型
        impl: 实现类型、工厂函数或模块路径字符串
        module: 实现所在的模块路径
        lifetime: 实例生命周期（默认 SCOPED）
        owner: 负责团队或个人
        compatibility: 兼容版本元组
        tags: 场景/环境选择标签
        deprecated: 是否已废弃
    """

    name: str
    version: str
    interface: Type
    impl: Type | Callable[..., Any] | str
    module: str
    lifetime: Lifetime = Lifetime.SCOPED
    owner: str = ""
    compatibility: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    deprecated: bool = False


class PortRegistry:
    """端口注册中心（单例模式）

    确保所有端口注册的唯一数据源
    """

    _instance: PortRegistry | None = None
    _ports: dict[str, PortSpec] = field(default_factory=dict)

    def __new__(cls) -> PortRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ports = {}
        return cls._instance

    def register(self, spec: PortSpec) -> None:
        """注册端口

        Args:
            spec: 待注册的端口规格

        Raises:
            ValueError: 端口名称已存在且规格不同时抛出
        """
        if spec.name in self._ports:
            existing = self._ports[spec.name]
            if existing != spec:
                raise ValueError(f"Port already registered with different spec: {spec.name}")
            # Same spec already registered - idempotent, skip
            return
        logger.info("Registering port: %s (%s)", spec.name, spec.version)
        self._ports[spec.name] = spec

    def get(self, name: str) -> PortSpec | None:
        """通过名称获取端口规格"""
        return self._ports.get(name)

    def get_by_interface(self, interface: Type) -> PortSpec | None:
        """通过接口类型获取端口规格"""
        for spec in self._ports.values():
            if spec.interface is interface:
                return spec
            if isinstance(interface, type) and isinstance(spec.interface, type):
                if issubclass(spec.interface, interface):
                    return spec
        return None

    def list_all(self) -> list[PortSpec]:
        """列出所有已注册的端口规格"""
        return list(self._ports.values())

    def list_by_tag(self, tag: str) -> list[PortSpec]:
        """按标签过滤列出端口规格"""
        return [spec for spec in self._ports.values() if tag in spec.tags]

    def unregister(self, name: str) -> None:
        """按名称注销端口"""
        if name in self._ports:
            del self._ports[name]
            logger.info("Unregistered port: %s", name)

    def __contains__(self, name: str) -> bool:
        return name in self._ports

    def __len__(self) -> int:
        return len(self._ports)


# 全局注册中心实例
_global_registry = PortRegistry()


def register_port(
    name: str,
    version: str,
    interface: Type,
    impl: Type | Callable[..., Any] | str,
    module: str,
    **kwargs: Any,
) -> None:
    """便捷的端口注册函数

    Args:
        name: 唯一端口名称
        version: 语义化版本号
        interface: 协议接口类型
        impl: 实现类型、工厂函数或模块路径字符串（用于延迟加载）
        module: 模块路径
        **kwargs: 其他 PortSpec 字段（lifetime、owner、tags 等）
    """
    spec = PortSpec(
        name=name,
        version=version,
        interface=interface,
        impl=impl,
        module=module,
        **kwargs,
    )
    _global_registry.register(spec)
