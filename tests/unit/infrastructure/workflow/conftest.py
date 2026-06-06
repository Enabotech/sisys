"""Prefect workflow 测试专属配置

配置 Prefect 在测试环境下的日志行为，避免 pytest teardown 时
rich.console 向已关闭的文件描述符写入导致 ValueError

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import logging
import os


def pytest_configure(config: object) -> None:
    """pytest 启动时配置 Prefect 环境

    禁用 Prefect CLI 彩色输出并降低日志级别。
    注册 atexit 钩子，在 Python 退出前清理 Prefect 的 rich 日志处理器，
    防止向已关闭的文件描述符写入。

    Args:
        config: pytest 配置对象
    """
    os.environ.setdefault("PREFECT_CLI_COLORS", "false")
    os.environ.setdefault("PREFECT_LOGGING_LEVEL", "WARNING")

    import atexit

    atexit.register(_prefect_log_cleanup)


def _prefect_log_cleanup() -> None:
    """Python 退出前清理 Prefect 日志处理器

    Prefect 使用 rich.console 作为日志输出，在 pytest 关闭 capture
    文件后 rich 尝试写入会引发 ValueError。此函数将所有 Prefect 相关
    日志器的处理器替换为 NullHandler，安全丢弃后续日志。
    """
    for name in ("prefect.server", "prefect"):
        logger = logging.getLogger(name)
        # 清空所有处理器，添加 NullHandler 防止 "No handlers found" 警告
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
