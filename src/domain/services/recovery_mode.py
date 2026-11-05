"""领域层恢复模式判定纯函数模块（Story 6-3/6-6）

影响范围评估：Checkpoint 之后的后续 Checkpoint 数决定恢复模式建议——
≥2 → REPLAY 强制（多后续点重放代价可控且一致性收益大）/<2 → OVERRIDE
推荐（单点修正同步开销更低）。判定纯计算零副作用；双模式执行引擎
（Replay 重放/Override 同步）归 Story 6-6（OD-1 边界）。

Story 6-6 就地扩展两纯函数：to_event_recovery_mode（双枚举显式转换——
entities 小写版 → events 大写版，两版成员值不等是代码事实；6-3 story
L171 钦定注记「6-6 恢复执行面消费建议恢复模式时需显式转换」兑现）+
assess_consistency_risk（一致性风险等级同源计算——CLI dry-run 评估输出
与恢复引擎⑤步事件构造同源消费，单一事实源防双实现漂移）。

语义依据：core-domain-design §8.1 双模式（Replay/Override 完整协议对应
prd FR-SP-06/07/08 均 P1）；or.md 五.6 恢复机制。
"""

from __future__ import annotations

from src.domain.entities.checkpoint import RecoveryMode
from src.domain.events.enums import RecoveryMode as EventRecoveryMode
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


def to_event_recovery_mode(mode: RecoveryMode) -> EventRecoveryMode:
    """双枚举显式转换（entities 小写版 → events 大写版——OD-9）。

    属性形态断裂族预防（6-1 三犯+6-3 再证）：entities 版 RecoveryMode
    （"replay"/"override" 小写——引擎入参/恢复记录 state_data 用）与
    events 版 RecoveryMode（"Replay"/"Override" 首字母大写——
    CheckpointRecovered.recovery_mode 字段用）是同名双枚举且成员值不等，
    跨面消费必须经本函数显式映射（入参域内显式映射——枚举闭集下非法值
    经类型系统不可构造，无 else raise 面）。

    Args:
        mode: entities 版恢复模式枚举（引擎内部判定/CLI --mode 构造产物）。

    Returns:
        events 版恢复模式枚举（⑤步 CheckpointRecovered 事件构造消费面）。
    """
    if mode is RecoveryMode.REPLAY:
        return EventRecoveryMode.REPLAY
    return EventRecoveryMode.OVERRIDE


def assess_consistency_risk(mode: RecoveryMode, affected_count: int) -> str:
    """一致性风险等级同源计算（纯函数——OD-5/R1-10 单一事实源）。

    三分支矩阵（Task 0 冻结唯一版本）：Override+有后续（affected_count>0）
    → "medium"（待同步标记有一致性风险——or.md L623 Override 须展示一致性
    风险提示）/ Override+无后续 → "low" / Replay 全形态 → "low"（强一致
    作废语义——后续全部作废重算无漂移面）。

    消费面（唯一落点=引擎⑤步事件构造+CLI dry-run 评估输出，同源）：
    Replay 分支输出恰与 CheckpointRecovered.consistency_risk_level 默认值
    同值（"low"）——引擎⑤步恒显式传本函数输出（不经默认值路径，防实现
    漂移；medium 腿是同源消费漂移的唯一可判别腿）。

    Args:
        mode: entities 版恢复模式枚举。
        affected_count: 受影响的后续 Checkpoint 数量。

    Returns:
        一致性风险等级（"medium"/"low" 两值钦定）。
    """
    if mode is RecoveryMode.OVERRIDE and affected_count > 0:
        return "medium"
    return "low"
