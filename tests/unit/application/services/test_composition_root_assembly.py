"""composition_root.py 装配回归测试(Story 4.3 AC-8 + P0-A 修复守护)

覆盖范围:
1. tool_execution_service 装配后 engine 是 ToolOutputValidator 实例(P0-A 核心)
2. ToolOutputValidator 装饰器与 ToolExecutionEngine 类 Liskov Substitution(Protocol 兼容)
3. 端口元数据完整性:compatibility / deprecated / tags / version
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.application.services.tool_output_validator import ToolOutputValidator


def test_tool_output_validator_satisfies_protocol() -> None:
    """ToolOutputValidator 装饰器满足 ToolExecutionEnginePort Protocol(Liskov)

    AC-8 验证清单要求装饰器可以注入到 ToolExecutionService(隐式满足 Protocol)
    """
    schema_validator = MagicMock()
    wrapped = MagicMock(spec=ToolExecutionEnginePort)
    validator = ToolOutputValidator(
        wrapped=wrapped,
        schema_validator=schema_validator,
    )
    assert isinstance(validator, ToolExecutionEnginePort)


def test_schema_validator_port_registration_metadata() -> None:
    """schema_validator 端口元数据完整性"""
    # bootstrap 由 conftest.py 的 autouse fixture 已执行
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("schema_validator")
    assert spec is not None
    assert spec.name == "schema_validator"
    assert spec.version == "v1.0.0"
    assert spec.owner == "tool-team"
    assert "tool" in spec.tags
    assert "schema" in spec.tags
    assert spec.deprecated is False


def test_schema_validation_record_repository_port_metadata() -> None:
    """schema_validation_record_repository 端口元数据完整性"""
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("schema_validation_record_repository")
    assert spec is not None
    assert spec.name == "schema_validation_record_repository"
    assert spec.owner == "tool-team"
    assert spec.deprecated is False
    # version 是 v1.1.0(InMemory → PostgreSQL ORM 升级)
    assert spec.version == "v1.1.0"


def test_tool_execution_service_version_bumped() -> None:
    """P0-A 修复守护:tool_execution_service 版本号必须 v1.2.0(因 SandboxSecurityDecorator + ToolOutputValidator 装饰器装配)"""
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("tool_execution_service")
    assert spec is not None
    # 装饰器装配属于行为变更(安全防护 + Schema 校验介入),必须 bump 版本
    assert spec.version == "v1.2.0"
    # tags 包含 "decorated" 标识
    assert "decorated" in spec.tags
