"""时间戳采样工具（时钟回拨防御——完成/更新时刻采样统一口径）。

墙钟（CLOCK_REALTIME）可被 NTP 修正或 WSL2 hv_utils 宿主同步向后 step，
跨 await 窗口的二次采样晚值可能早于起始值，触发 VO/实体时间序不变量
校验（EntityValidationError）。完成/更新时刻统一经 ``utc_now_after``
下限钳制，保证观测单调（误差=回拨量）；不变量校验本身保留——继续
拒绝外部传入的倒挂数据。
"""

from datetime import UTC, datetime

__all__ = ["utc_now_after"]


def utc_now_after(floor: datetime) -> datetime:
    """UTC 当前时刻采样（不早于 floor——墙钟回拨时钳制到 floor）。

    Args:
        floor: 下限时刻（同一流程的起始采样值——started_at/created_at）。

    Returns:
        当前 UTC 时刻与 floor 的较大者。
    """
    return max(datetime.now(UTC), floor)
