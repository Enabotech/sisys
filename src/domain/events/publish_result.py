"""领域层 发布结果类型模块

定义事件发布操作的通道无关结果类型，领域层不感知具体传输技术
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelResult:
    """单个通道的发布结果"""

    channel_name: str  # "realtime" / "reliable" / "inmemory"
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class PublishResult:
    """事件发布结果（通道无关）

    语义定义：
    - is_success: 全部通道成功才算成功
    - is_full_failure: 全部通道失败
    - partial_error: 返回第一个失败通道的错误信息
    """

    event_id: str
    results: tuple[ChannelResult, ...] = ()

    @property
    def is_success(self) -> bool:
        """全部通道成功才算成功"""
        if not self.results:
            return False
        return all(r.success for r in self.results)

    @property
    def is_full_failure(self) -> bool:
        """所有通道都失败"""
        return len(self.results) > 0 and not any(r.success for r in self.results)

    @property
    def partial_error(self) -> str | None:
        """返回第一个失败通道的错误信息"""
        for r in self.results:
            if not r.success and r.error:
                return r.error
        return None

    # 向后兼容属性（便于渐进迁移）
    @property
    def redis_success(self) -> bool:
        return any(r.channel_name == "realtime" and r.success for r in self.results)

    @property
    def redis_error(self) -> str | None:
        for r in self.results:
            if r.channel_name == "realtime" and not r.success:
                return r.error
        return None

    @property
    def outbox_saved(self) -> bool:
        return any(r.channel_name == "reliable" and r.success for r in self.results)

    @property
    def outbox_error(self) -> str | None:
        for r in self.results:
            if r.channel_name == "reliable" and not r.success:
                return r.error
        return None
