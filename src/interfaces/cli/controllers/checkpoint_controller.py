"""checkpoint 命令控制器

三端口消费（AC-5 表，R3-1/2 勘正后成员）：
- ``checkpoint_list_use_case``（:2524——``execute(*, plan_id)`` 清单面）
- ``checkpoint_recovery_use_case``（:2508——预览视图 ``execute(*, plan_id,
  checkpoint_no)`` 两参 keyword-only 必填，R5 方案 a：无「缺省取最新」合成层）
- ``checkpoint_recovery_execute_use_case``（:2536——执行面全 keyword-only，
  ``created_via`` 固定传 ``"cli"``（R4-2——缺省 "use_case" 会落错触发源
  审计标识）；``confirmed_by`` 非空强制（空串→242 用例守卫），CLI 缺省
  取 ``--session`` 标识且归一先于短路（R4-3））

``--checkpoint-no`` 为 CP-N 编号非 UUID（前缀锚定校验，不入 UUID 守卫族）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from src.domain.exceptions import ValidationError
from src.interfaces.cli._guards import canonical_uuid
from src.interfaces.cli.formatters import get_formatter

PORT_NAME_LIST = "checkpoint_list_use_case"
PORT_NAME_RECOVERY = "checkpoint_recovery_use_case"
PORT_NAME_RECOVERY_EXECUTE = "checkpoint_recovery_execute_use_case"


def validate_checkpoint_no(checkpoint_no: str) -> str:
    """checkpoint 编号守卫（CP-N 前缀锚定——非 UUID 守卫族）。

    Raises:
        ValidationError: EXCEPTION_201——非 CP-N 编号形态
    """
    normalized = checkpoint_no.strip()
    parts = normalized.split("-", 1)
    if len(parts) != 2 or parts[0] != "CP" or not parts[1].isdigit():
        raise ValidationError(
            message=f"checkpoint-no 必须为 CP-N 编号形态: {checkpoint_no!r}",
            context={"checkpoint_no": checkpoint_no},
        )
    return f"CP-{int(parts[1])}"


def run_list(*, plan_id: str, fmt: str, resolve: Callable[[str], Any]) -> int:
    """真实执行清单查询（canonical 归一 → :2524 execute(*, plan_id)）。"""
    normalized = canonical_uuid(plan_id, field="plan_id")
    use_case = resolve(PORT_NAME_LIST)
    summaries = asyncio.run(use_case.execute(plan_id=normalized))
    rows = [
        {
            "checkpoint_no": getattr(item, "checkpoint_no", ""),
            "stage_id": getattr(item, "stage_id", ""),
            "completed": getattr(item, "completed", None),
            "summary": getattr(item, "summary", ""),
            "state_version": getattr(item, "state_version", ""),
            "sync_status": getattr(item, "sync_status", ""),
        }
        for item in summaries
    ]
    print(get_formatter(fmt)(rows))
    return 0


def run_show(*, plan_id: str, checkpoint_no: str, fmt: str, resolve: Callable[[str], Any]) -> int:
    """真实执行详情查询（复合定位 → :2508 预览视图）。"""
    normalized = canonical_uuid(plan_id, field="plan_id")
    normalized_no = validate_checkpoint_no(checkpoint_no)
    use_case = resolve(PORT_NAME_RECOVERY)
    view = asyncio.run(use_case.execute(plan_id=normalized, checkpoint_no=normalized_no))
    payload = {
        "checkpoint_no": getattr(view, "checkpoint_no", normalized_no),
        "stage": getattr(view, "stage", ""),
        "state_version": getattr(view, "state_version", ""),
        "recommended_mode": str(getattr(view, "recommended_mode", "") or ""),
        "correction_history_count": len(getattr(view, "correction_history", ()) or ()),
        "subsequent_checkpoints": list(getattr(view, "subsequent_checkpoints", ()) or ()),
    }
    print(get_formatter(fmt)(payload))
    return 0


def run_recovery_preview(*, plan_id: str, checkpoint_no: str, fmt: str, resolve: Callable[[str], Any]) -> int:
    """recover --dry-run 特化预览（真实消费 :2508 预览视图——AC-5 recover 行注记）。

    与通用 dry-run 零 resolve 短路不同：recover 的预览语义=展示将恢复到的
    状态（:2508 查询）；``--yes`` 缺 budget 守卫仍先于预览（AC-3）。
    """
    normalized = canonical_uuid(plan_id, field="plan_id")
    normalized_no = validate_checkpoint_no(checkpoint_no)
    use_case = resolve(PORT_NAME_RECOVERY)
    view = asyncio.run(use_case.execute(plan_id=normalized, checkpoint_no=normalized_no))
    payload = {
        "port": PORT_NAME_RECOVERY,
        "checkpoint_no": getattr(view, "checkpoint_no", normalized_no),
        "stage": getattr(view, "stage", ""),
        "state_version": getattr(view, "state_version", ""),
        "recommended_mode": str(getattr(view, "recommended_mode", "") or ""),
    }
    print(get_formatter(fmt)(payload))
    return 0


def run_recover(
    *,
    plan_id: str,
    checkpoint_no: str,
    mode: str,
    confirmed_by: str,
    fmt: str,
    resolve: Callable[[str], Any],
) -> int:
    """真实执行恢复（:2536 执行面——created_via="cli" 固定 R4-2）。"""
    normalized = canonical_uuid(plan_id, field="plan_id")
    normalized_no = validate_checkpoint_no(checkpoint_no)
    use_case = resolve(PORT_NAME_RECOVERY_EXECUTE)
    outcome = asyncio.run(
        use_case.execute(
            plan_id=normalized,
            checkpoint_no=normalized_no,
            correction=None,
            mode=mode or None,
            confirmed_by=confirmed_by,
            created_via="cli",
        )
    )
    payload = {
        "checkpoint_no": getattr(outcome, "checkpoint_no", normalized_no),
        "recovery_mode": str(getattr(outcome, "recovery_mode", mode or "") or ""),
        "corrected": getattr(outcome, "corrected", None),
        "new_state_version": getattr(outcome, "new_state_version", ""),
        "affected_checkpoints": getattr(outcome, "affected_checkpoints", None),
        "execution_ms": getattr(outcome, "execution_ms", None),
    }
    print(get_formatter(fmt)(payload))
    return 0
