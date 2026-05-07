"""LocalModelHealth — 向后兼容别名。

.. deprecated::
    此类已被 LocalModelHealthFacade 取代。
    请使用 src.application.services.local_model_health_facade.LocalModelHealthFacade

向后兼容：保留旧代码导入路径 `from src.infrastructure.routing.local_model_health import LocalModelHealth`
"""

from __future__ import annotations

from src.application.services.local_model_health_facade import (
    LocalModelHealthFacade,
)

# 向后兼容别名
LocalModelHealth = LocalModelHealthFacade

__all__ = ["LocalModelHealth", "LocalModelHealthFacade"]
