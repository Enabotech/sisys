"""session_context 模块单元测试（ContextVar 会话管理——set/get/reset/clear）

覆盖 clear_session（Story 5.6 R1-F2 新增的免 Token 复位 API——防御性泄漏自愈
通道：原 reset_session 需持有原 Token，他场景泄漏的 session 在无 Token 场景
不可复位；R2-F6 补测：修复引入的真实守卫此前零测试覆盖——「未验证守卫」）。

Run with:
    poetry run pytest tests/unit/infrastructure/storage/postgresql/test_session_context.py -v
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.session_context import (
    clear_session,
    get_session,
    get_session_optional,
    reset_session,
    set_session,
)


def _fake_session() -> AsyncSession:
    """假 session（cast 静态定形——运行时零操作零 IO，只验 ContextVar 语义）."""
    return cast(AsyncSession, object())


class TestClearSession:
    """clear_session（免 Token 复位——置 None 与未设置语义等价）。"""

    def test_clear_restores_unset_state(self) -> None:
        """set → clear → get_session_optional 返回 None（泄漏自愈形态）."""
        sentinel = _fake_session()
        token = set_session(sentinel)
        assert get_session_optional() is sentinel
        reset_session(token)  # 基线复原（防跨测试污染）
        set_session(sentinel)
        clear_session()
        assert get_session_optional() is None

    def test_get_session_raises_runtime_error_after_clear(self) -> None:
        """clear 后 get_session 复抛 RuntimeError（与「从未设置」语义等价——
        场景③ 坏仓储 fallback 分派前提在自愈后依然成立）."""
        sentinel = _fake_session()
        set_session(sentinel)
        clear_session()
        with pytest.raises(RuntimeError, match="No AsyncSession in context"):
            get_session()

    def test_clear_idempotent_on_unset_context(self) -> None:
        """未设置状态下 clear 幂等（optional 保持 None 不抛——条件自愈可无条件调用）."""
        clear_session()
        assert get_session_optional() is None
