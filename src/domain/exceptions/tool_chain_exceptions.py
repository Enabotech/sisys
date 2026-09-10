"""领域层工具链异常模块

定义工具链编排相关的领域异常（DAG 工具链编排，独立于 tool 子域）。
异常是领域契约的一部分，遵循异常编码范围约束。

toolchain 子域（390-399）共 4 个异常：
- EXCEPTION_390 ToolChainCycleDetectedError
- EXCEPTION_391 ToolChainDuplicateNodeError
- EXCEPTION_392 ToolChainNodeNotFoundError
- EXCEPTION_393 ToolChainExecutionFailedError

子域嵌套说明：
- toolchain (390-399) ⊂ external (301-399)，物理上嵌套但语义独立
- 与 tool (380-389) 子域同处理方式：flat CODE_RANGES + 测试 fixture 注册嵌套
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException


class ToolChainCycleDetectedError(BusinessException):
    """DAG 包含循环依赖（A→B→C→A，含自依赖 A→A 作为长度为 1 的环）

    父类 BusinessException → HTTP 422（语义错误，校验失败）。

    Attributes:
        code: 错误码 EXCEPTION_390
        message: 默认消息
    """

    code = "EXCEPTION_390"
    message = "ToolChain DAG cycle detected"

    def __init__(
        self,
        message: str | None = None,
        chain_id: str | None = None,
        cycle_path: list[str] | None = None,
    ) -> None:
        context: dict = {}
        if chain_id is not None:
            context["chain_id"] = chain_id
        if cycle_path is not None:
            context["cycle_path"] = cycle_path
        super().__init__(message=message, context=context)


class ToolChainDuplicateNodeError(BusinessException):
    """DAG 节点重复（同一 node_id 出现两次）

    父类 BusinessException → HTTP 422（语义错误，校验失败）。

    Attributes:
        code: 错误码 EXCEPTION_391
        message: 默认消息
    """

    code = "EXCEPTION_391"
    message = "ToolChain DAG duplicate node"

    def __init__(
        self,
        message: str | None = None,
        chain_id: str | None = None,
        duplicate_node_id: str | None = None,
    ) -> None:
        context: dict = {}
        if chain_id is not None:
            context["chain_id"] = chain_id
        if duplicate_node_id is not None:
            context["duplicate_node_id"] = duplicate_node_id
        super().__init__(message=message, context=context)


class ToolChainNodeNotFoundError(BusinessException):
    """DAG 边引用的上游节点不存在（如 B 依赖 X，但 X 未在 nodes 列表中）

    父类 BusinessException → HTTP 404（资源缺失）。

    Attributes:
        code: 错误码 EXCEPTION_392
        message: 默认消息
    """

    code = "EXCEPTION_392"
    message = "ToolChain DAG node not found"

    def __init__(
        self,
        message: str | None = None,
        chain_id: str | None = None,
        missing_node_id: str | None = None,
        referenced_by_node_ids: list[str] | None = None,
    ) -> None:
        context: dict = {}
        if chain_id is not None:
            context["chain_id"] = chain_id
        if missing_node_id is not None:
            context["missing_node_id"] = missing_node_id
        if referenced_by_node_ids is not None:
            context["referenced_by_node_ids"] = referenced_by_node_ids
        super().__init__(message=message, context=context)


class ToolChainExecutionFailedError(BusinessException):
    """工具链执行整体失败（FAIL_FAST 策略下首个节点失败后整链终止）

    父类 BusinessException → HTTP 500（执行失败）。

    Attributes:
        code: 错误码 EXCEPTION_393
        message: 默认消息
    """

    code = "EXCEPTION_393"
    message = "ToolChain execution failed"

    def __init__(
        self,
        message: str | None = None,
        chain_run_id: str | None = None,
        chain_id: str | None = None,
        failed_node_id: str | None = None,
        original_error_code: str | None = None,
        original_stage: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        context: dict = {}
        if chain_run_id is not None:
            context["chain_run_id"] = chain_run_id
        if chain_id is not None:
            context["chain_id"] = chain_id
        if failed_node_id is not None:
            context["failed_node_id"] = failed_node_id
        if original_error_code is not None:
            context["original_error_code"] = original_error_code
        if original_stage is not None:
            context["original_stage"] = original_stage
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "ToolChainCycleDetectedError",
    "ToolChainDuplicateNodeError",
    "ToolChainNodeNotFoundError",
    "ToolChainExecutionFailedError",
]
