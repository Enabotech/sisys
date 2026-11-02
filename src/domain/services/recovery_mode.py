"""领域层恢复模式判定纯函数模块（Story 6-3）

影响范围评估：Checkpoint 之后的后续 Checkpoint 数决定恢复模式建议——
≥2 → REPLAY 强制（多后续点重放代价可控且一致性收益大）/<2 → OVERRIDE
推荐（单点修正同步开销更低）。判定纯计算零副作用；双模式执行引擎
（Replay 重放/Override 同步）归 Story 6-6（OD-1 边界）。

语义依据：core-domain-design §8.1 双模式（Replay/Override 完整协议对应
prd FR-SP-06/07/08 均 P1）；or.md 五.6 恢复机制。
"""

from __future__ import annotations

from src.domain.entities.checkpoint import RecoveryMode
from src.domain.exceptions import EntityValidationError

#: 强制 Replay 的后续 Checkpoint 数阈值（恰 2 即强制——AC-7 边界值）
_REPLAY_THRESHOLD: int = 2


def recommend_recovery_mode(affected_checkpoint_count: int) -> RecoveryMode:
    """恢复模式建议判定（纯函数——影响范围计数 → 恢复模式枚举）。

    Args:
        affected_checkpoint_count: 受影响的后续 Checkpoint 数量
            （该 Checkpoint 之后仍存活的恢复点数）。

    Returns:
        RecoveryMode.REPLAY（≥2 强制重放）或 RecoveryMode.OVERRIDE
        （<2 推荐覆盖同步）——返回既有 Epic 1 骨架枚举（小写成员值）。

    Raises:
        EntityValidationError: 计数为负时抛出（影响范围不可为负——fail-loud）。
    """
    if affected_checkpoint_count < 0:
        raise EntityValidationError(
            message="受影响的后续 Checkpoint 数量不可为负",
            context={"service": "recommend_recovery_mode", "affected_checkpoint_count": str(affected_checkpoint_count)},
        )
    if affected_checkpoint_count >= _REPLAY_THRESHOLD:
        return RecoveryMode.REPLAY
    return RecoveryMode.OVERRIDE
