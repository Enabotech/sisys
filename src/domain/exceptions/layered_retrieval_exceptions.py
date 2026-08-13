"""领域层 分层检索（L1-L4）异常模块

定义分层检索领域的业务异常，覆盖检索编排失败与非法层级遍历场景。
遵循统一异常设计规范：继承 BusinessException，编码分配至 retrieval 子域（280-289）。

消息安全性：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException


class LayeredRetrievalError(BusinessException):
    """分层检索编排失败

    当检索编排流程出现不可恢复的错误（如 L4 检索与 L3 回溯均失败、
    分层检索服务内部状态异常）时抛出。

    Attributes:
        code: 错误码 EXCEPTION_280
        message: 默认消息
    """

    code = "EXCEPTION_280"
    message = "分层检索编排失败"


class LevelTransitionError(BusinessException):
    """层级遍历非法

    当目标层级与当前层级的遍历路径非法（如非相邻层级直接遍历、
    MVP 阶段尝试多级全遍历）时抛出。

    Attributes:
        code: 错误码 EXCEPTION_281
        message: 默认消息
    """

    code = "EXCEPTION_281"
    message = "层级遍历非法"


__all__ = [
    "LayeredRetrievalError",
    "LevelTransitionError",
]
