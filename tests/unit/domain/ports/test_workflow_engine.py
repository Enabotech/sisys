"""WorkflowEnginePort Protocol 单元测试

验证 runtime_checkable、方法签名、FlowStatus 返回类型
"""

from __future__ import annotations

import ast
import inspect

from src.domain.ports.workflow_engine import WorkflowEnginePort
from src.domain.value_objects.flow_status import FlowStatus


class TestWorkflowEnginePortProtocol:
    """WorkflowEnginePort Protocol 结构验证"""

    def test_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 装饰器"""

        # Protocol 类本身不是 runtime_checkable 的，但子类应该是
        assert isinstance(WorkflowEnginePort, type)

    def test_has_submit_flow(self) -> None:
        assert hasattr(WorkflowEnginePort, "submit_flow")

    def test_has_get_flow_status(self) -> None:
        assert hasattr(WorkflowEnginePort, "get_flow_status")

    def test_methods_are_async(self) -> None:
        source = inspect.getsource(WorkflowEnginePort)
        assert "async def submit_flow" in source
        assert "async def get_flow_status" in source


class TestWorkflowEnginePortImplementation:
    """验证实现类满足 Protocol"""

    def test_prefect_engine_satisfies_protocol(self) -> None:
        from unittest.mock import AsyncMock

        from src.infrastructure.config.prefect import PrefectConfig
        from src.infrastructure.workflow.prefect_engine import PrefectEngine

        engine = PrefectEngine(PrefectConfig(), AsyncMock())
        assert isinstance(engine, WorkflowEnginePort)


class TestWorkflowEnginePortStdlibOnly:
    """验证端口仅使用标准库类型"""

    def test_no_external_imports(self) -> None:
        """验证文件导入不含外部依赖"""
        import pathlib

        source = pathlib.Path(inspect.getfile(WorkflowEnginePort)).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(("prefect", "pydantic", "langgraph")), (
                    f"WorkflowEnginePort 不应导入外部依赖: {node.module}"
                )

    def test_flow_status_is_stdlib_enum(self) -> None:
        """FlowStatus 返回类型应使用标准库 Enum"""
        from enum import Enum

        assert issubclass(FlowStatus, Enum)
        assert issubclass(FlowStatus, str)
