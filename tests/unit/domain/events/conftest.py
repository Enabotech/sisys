"""领域事件测试公共 fixture（20-8 系技术债清偿 A4）

DomainEvent._registry 为类级共享 dict（import 期 __init_subclass__ 自动注册）——
测试内 register/自定义事件类会跨用例泄漏。本 fixture autouse 快照/恢复注册表，
保证每用例从 import 期基线出发（tests/conftest.py 会话 ContextVar 快照先例同款）。

注意：import 期注册发生在 fixture 之前（模块级），本 fixture 只回收「测试期」
变更——import 期污染源（如 test_redis_event_bus_subscribe_fix 的模块级手动
register）不受影响，需在其文件内自理。
"""

from __future__ import annotations

from typing import Any, Generator

import pytest

from src.domain.events.base import DomainEvent


@pytest.fixture(autouse=True)
def _isolate_domain_event_registry() -> Generator[None, None, None]:
    """快照并恢复 DomainEvent._registry（per-test 隔离）。"""
    snapshot: dict[str, Any] = dict(DomainEvent._registry)
    yield
    DomainEvent._registry.clear()
    DomainEvent._registry.update(snapshot)
