"""Shared pytest configuration."""

import os
import sys

# litellm 模型价格表本地化开关——必须先于任何 litellm import 生效（litellm
# 在 import 期即尝试拉取远端价格表；本文件的 worker 禁用函数与部分被测
# 模块导入链会触发 litellm import，而 .env 加载链（get_test_env）在 session
# fixture 阶段才执行，晚于 conftest 模块级 import）。setdefault：用户环境
# 显式配置优先。受限网络（GFW）下不设此开关会打 "Failed to fetch remote
# model cost map" 告警并阻塞数秒（litellm 判定值为 .lower()=="true"）。
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Import all fixtures from fixtures.py for shared access
from tests.fixtures import *  # noqa: F403, F401

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_once() -> None:
    """Bootstrap the port registry once per test session."""
    from src.composition_root import bootstrap
    from tests.environments import get_test_env

    get_test_env()
    bootstrap()


# =============================================================================
# PostgreSQL Session Fixtures
# =============================================================================


def _create_mock_session() -> AsyncMock:
    """创建标准 mock AsyncSession（含常用方法预配置）"""
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    session.delete = Mock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.begin = AsyncMock()
    session.begin_nested = AsyncMock()
    session.in_transaction = Mock(return_value=True)
    session.execute = AsyncMock()
    return session


@pytest.fixture
async def pg_session() -> AsyncGenerator[AsyncMock, None]:
    """标准 PostgreSQL mock session fixture

    自动管理 ContextVar 生命周期，测试结束后自动清理
    替代分散在各测试文件中的 set_session()/reset_session() 手动管理

    用法::

        async def test_save(pg_session):
            repo = UserRepository()
            await repo.save(entity)
            pg_session.flush.assert_called()
    """
    from src.infrastructure.storage.postgresql.session_context import with_session

    mock = _create_mock_session()
    async with with_session(mock):
        yield mock


@asynccontextmanager
async def pg_session_context():
    """异步上下文管理器版本的 mock session（用于 fixture 链式组合）

    用法::

        @pytest.fixture
        async def user_repo(pg_session):
            async with pg_session_context() as session:
                yield UserRepository()
    """
    from src.infrastructure.storage.postgresql.session_context import with_session

    mock = _create_mock_session()
    async with with_session(mock):
        yield mock


# =============================================================================
# Session Context 安全网 — 防止 mock session 跨测试泄漏
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_session_ctx():
    """确保每个测试结束后 PostgreSQL session ContextVar 恢复为 None

    防止单元测试中的 mock session 通过 ContextVar 泄漏到验收测试，
    导致 OutboxRepository.save() 等方法在 AsyncMock 上触发 RuntimeWarning。
    """
    from src.infrastructure.storage.postgresql.session_context import _session_ctx

    yield
    _session_ctx.set(None)


# =============================================================================
# litellm 后台日志 worker 禁用 — PytestUnraisableExceptionWarning 根因处置
# =============================================================================


def _disable_litellm_logging_worker() -> None:
    """测试环境禁用 litellm GLOBAL_LOGGING_WORKER（后台日志协程根因级处置）。

    根因（2026-10-20 全量跑实测）：任何 litellm 调用（completion/embedding/
    rerank——含真实与部分 mock 形态）经 utils.async_completion 中
    ``GLOBAL_LOGGING_WORKER.ensure_initialized_and_enqueue`` 拉起模块级后台
    日志协程；测试事件循环关闭后残留协程被 GC 回收触发
    PytestUnraisableExceptionWarning（"Event loop is closed" /
    "task_done() called too many times"）——挂靠点为该进程后续任意测试的
    GC 时机（qdrant/prefect 验收均出现过）。

    处置：模块级替换入口方法为「关闭协程直接丢弃」——worker 从不启动，
    无残留可 GC（litellm 内部日志回调在测试环境无消费方，丢弃零影响；
    入口仅 utils.py/caching_handler.py 两处调用点，单例方法替换全覆盖）。

    版本守卫（R1-F6）：litellm 内部私有结构无稳定性承诺——缺失/改名时
    warnings.warn 显式可观测（禁静默跳过：静默会使 PytestUnraisable
    ExceptionWarning 回归且无从定位；不 raise：conftest 模块级异常会阻断
    全部测试收集，对第三方版本漂移过猛）。
    """
    from collections.abc import Coroutine
    from typing import Any

    from litellm.litellm_core_utils import logging_worker as _lw

    worker = getattr(_lw, "GLOBAL_LOGGING_WORKER", None)
    if worker is None or not hasattr(worker, "ensure_initialized_and_enqueue"):
        import warnings

        warnings.warn(
            "litellm GLOBAL_LOGGING_WORKER 结构缺失或已改名——后台日志协程禁用失效，"
            "PytestUnraisableExceptionWarning 可能回归（litellm 版本升级适配待办）",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    def _discard(async_coroutine: Coroutine[Any, Any, Any]) -> None:
        # 参数名对齐 litellm 签名（调用点均关键字传参 async_coroutine=——
        # 名不匹配会 TypeError 致协程泄漏出 "never awaited" warning）
        async_coroutine.close()  # 未 await 的协程显式关闭（防 "never awaited" warning）

    # setattr 动态赋值形态（替身注入——非 mypy 静态方法赋值面）
    setattr(worker, "ensure_initialized_and_enqueue", _discard)


_disable_litellm_logging_worker()
