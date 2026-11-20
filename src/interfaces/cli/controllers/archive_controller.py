"""archive 命令控制器

消费端口（AC-5 表）：``blm_chain_trace_use_case``（:2567——
``execute(*, plan_id, include_blob=False)``）。

6.4-DF2 部分清偿载体：CLI 面（无 session 上下文）经真实 bootstrap 走
fallback **find 读路径**（集成/验收承载）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from src.interfaces.cli._guards import canonical_uuid
from src.interfaces.cli.formatters import get_formatter

PORT_NAME = "blm_chain_trace_use_case"


def run_query(*, plan_id: str, fmt: str, resolve: Callable[[str], Any]) -> int:
    """真实执行归档追溯查询（canonical 归一 → execute → 视图渲染）。"""
    normalized = canonical_uuid(plan_id, field="plan_id")
    use_case = resolve(PORT_NAME)
    view = asyncio.run(use_case.execute(plan_id=normalized))
    payload = {
        "plan_id": getattr(view, "plan_id", normalized),
        "total": getattr(view, "total", 0),
        "archived_count": getattr(view, "archived_count", 0),
        "records": list(getattr(view, "records", ()) or ()),
    }
    print(get_formatter(fmt)(payload))
    return 0
