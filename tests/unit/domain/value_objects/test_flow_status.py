"""FlowStatus 值对象单元测试

验证枚举值完整性、字符串转换、stdlib-only 依赖
"""

from __future__ import annotations

import ast
import inspect

from src.domain.value_objects.flow_status import FlowStatus


class TestFlowStatusValues:
    """FlowStatus 枚举值完整性测试"""

    def test_has_five_members(self) -> None:
        assert len(FlowStatus) == 5

    def test_pending_value(self) -> None:
        assert FlowStatus.PENDING.value == "PENDING"

    def test_running_value(self) -> None:
        assert FlowStatus.RUNNING.value == "RUNNING"

    def test_completed_value(self) -> None:
        assert FlowStatus.COMPLETED.value == "COMPLETED"

    def test_failed_value(self) -> None:
        assert FlowStatus.FAILED.value == "FAILED"

    def test_retrying_value(self) -> None:
        assert FlowStatus.RETRYING.value == "RETRYING"


class TestFlowStatusStringEnum:
    """FlowStatus str 枚举特性测试"""

    def test_is_string(self) -> None:
        assert isinstance(FlowStatus.PENDING, str)

    def test_string_comparison(self) -> None:
        assert FlowStatus.RUNNING == "RUNNING"

    def test_from_string(self) -> None:
        assert FlowStatus("COMPLETED") is FlowStatus.COMPLETED


class TestFlowStatusStdlibOnly:
    """验证 FlowStatus 仅依赖标准库"""

    def test_no_external_imports(self) -> None:
        source = inspect.getsource(FlowStatus)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(("prefect", "pydantic", "langgraph")), (
                        f"FlowStatus 不应导入外部依赖: {node.module}"
                    )
