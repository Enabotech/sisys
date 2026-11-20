"""utc_now_after 时间戳采样助手单元测试（时钟回拨防御）。"""

from datetime import UTC, datetime, timedelta

from src.domain.value_objects.timestamps import utc_now_after


class TestUtcNowAfter:
    """utc_now_after 不变量（正常采样 + 回拨钳制）。"""

    def test_normal_sampling_not_before_floor(self) -> None:
        """正常路径：floor 在过去时返回当前时刻（>= floor）。"""
        floor = datetime.now(UTC) - timedelta(seconds=1)
        assert utc_now_after(floor) >= floor

    def test_clamped_when_wall_clock_steps_back(self) -> None:
        """时钟回拨防御：floor 落于未来（起始采样后墙钟被向后 step——WSL2 hv_utils/timesyncd 场景）时钳制为 floor。"""
        future_floor = datetime.now(UTC) + timedelta(seconds=5)
        assert utc_now_after(future_floor) == future_floor
