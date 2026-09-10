"""PEP 561 类型存根：stdlib graphlib 模块（修复 CycleError.args 类型不准确问题）

提供 graphlib 官方公开 API 的精确类型签名，弥补 CPython typeshed 中
CycleError.args 字段类型过于宽松（tuple[Any, ...]）的不足。

CLAUDE.md §5 红线强制：
- 第三方库缺类型注解时必须创建 PEP 561 stubs
- 严禁使用 # type: ignore / # noqa 等抑制注释

参考 CPython 源码：Lib/graphlib.py
"""

from __future__ import annotations

class TopologicalSorter:
    """Kahn 算法实现的拓扑排序器（CPython 3.9+ 内置）。"""

    def __init__(self, graph: dict[str, list[str] | tuple[str, ...]] | None = ...) -> None: ...
    def add(self, node: str, *predecessors: str) -> None: ...
    def prepare(self) -> None: ...
    def is_active(self) -> bool: ...
    def done(self) -> tuple[str, ...]: ...
    def get_ready(self) -> tuple[str, ...]: ...
    def static_order(self) -> tuple[str, ...]: ...

class CycleError(ValueError):
    """拓扑排序检测到循环依赖。

    继承 ValueError 是 CPython 实际行为。
    args[1] 为参与环路的节点集合（frozenset[str]），非 tuple[Any, ...]。
    """

    def __init__(self, msg: str, nodes: frozenset[str]) -> None: ...
