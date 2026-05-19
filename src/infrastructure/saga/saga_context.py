"""Saga 上下文 - 基础设施层重新导出

从领域层导入 SagaContext，保持向后兼容
"""

from src.domain.ports.saga_context import SagaContext  # noqa: F401

__all__ = ["SagaContext"]
