"""tool_version 子域异常单元测试（Story 4-6 Task 2 TDD 红→绿）

4 个新异常（430-433，tool_version 子域 (430,439)）：
- EXCEPTION_430 ToolVersionNotFoundError → NotFoundError → 404
- EXCEPTION_431 ToolVersionAlreadyExistsError → ConflictError → 409
- EXCEPTION_432 ToolVersionTrafficWeightError → ValidationError → 400（并存冲突族）
- EXCEPTION_433 ToolVersionRollbackError → InvalidStateError → 409
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    ConflictError,
    DomainError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionNotFoundError,
    ToolVersionRollbackError,
    ToolVersionTrafficWeightError,
)
from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP


class TestToolVersionNotFoundError:
    """EXCEPTION_430（404）测试。"""

    def test_inherits_not_found_error(self) -> None:
        assert isinstance(ToolVersionNotFoundError(), NotFoundError)
        assert isinstance(ToolVersionNotFoundError(), DomainError)

    def test_code_is_430(self) -> None:
        assert ToolVersionNotFoundError().code == "EXCEPTION_430"

    def test_constructor_context(self) -> None:
        exc = ToolVersionNotFoundError(tool_id="t-1", version="9.9.9")
        assert exc.context["tool_id"] == "t-1"
        assert exc.context["version"] == "9.9.9"

    def test_to_dict(self) -> None:
        exc = ToolVersionNotFoundError(version="1.0.0")
        assert exc.to_dict()["code"] == "EXCEPTION_430"

    def test_http_map_404(self) -> None:
        assert EXCEPTION_HTTP_MAP.get(type(ToolVersionNotFoundError())) == 404


class TestToolVersionAlreadyExistsError:
    """EXCEPTION_431（409）测试。"""

    def test_inherits_conflict_error(self) -> None:
        assert isinstance(ToolVersionAlreadyExistsError(), ConflictError)

    def test_code_is_431(self) -> None:
        assert ToolVersionAlreadyExistsError().code == "EXCEPTION_431"

    def test_constructor_context(self) -> None:
        exc = ToolVersionAlreadyExistsError(tool_id="t-1", version="1.0.0")
        assert exc.context["tool_id"] == "t-1"
        assert exc.context["version"] == "1.0.0"

    def test_http_map_409(self) -> None:
        assert EXCEPTION_HTTP_MAP.get(type(ToolVersionAlreadyExistsError())) == 409


class TestToolVersionTrafficWeightError:
    """EXCEPTION_432（400——权重非法 + 并存冲突族）测试。"""

    def test_inherits_validation_error(self) -> None:
        assert isinstance(ToolVersionTrafficWeightError(), ValidationError)

    def test_code_is_432(self) -> None:
        assert ToolVersionTrafficWeightError().code == "EXCEPTION_432"

    def test_constructor_context_weight(self) -> None:
        exc = ToolVersionTrafficWeightError(tool_id="t-1", version="1.0.0", traffic_weight=0)
        assert exc.context["traffic_weight"] == 0

    def test_constructor_context_conflict_family(self) -> None:
        """并存冲突族：活跃 CANARY/单活跃不变量破坏场景。"""
        exc = ToolVersionTrafficWeightError(tool_id="t-1", version="1.1.0", conflict_reason="并存冲突")
        assert exc.context["conflict_reason"] == "并存冲突"

    def test_http_map_400(self) -> None:
        assert EXCEPTION_HTTP_MAP.get(type(ToolVersionTrafficWeightError())) == 400


class TestToolVersionRollbackError:
    """EXCEPTION_433（409）测试。"""

    def test_inherits_invalid_state_error(self) -> None:
        assert isinstance(ToolVersionRollbackError(), InvalidStateError)

    def test_code_is_433(self) -> None:
        assert ToolVersionRollbackError().code == "EXCEPTION_433"

    def test_constructor_context(self) -> None:
        exc = ToolVersionRollbackError(tool_id="t-1", target_version="1.0.0", reason="not_stable_before")
        assert exc.context["target_version"] == "1.0.0"
        assert exc.context["reason"] == "not_stable_before"

    def test_http_map_409(self) -> None:
        assert EXCEPTION_HTTP_MAP.get(type(ToolVersionRollbackError())) == 409


class TestToolVersionSubdomainRegistration:
    """4 个新异常必须注册到 tool_version 子域 (430,439)。"""

    @pytest.mark.parametrize(
        ("exc_cls", "expected_code"),
        [
            (ToolVersionNotFoundError, "EXCEPTION_430"),
            (ToolVersionAlreadyExistsError, "EXCEPTION_431"),
            (ToolVersionTrafficWeightError, "EXCEPTION_432"),
            (ToolVersionRollbackError, "EXCEPTION_433"),
        ],
    )
    def test_exception_in_tool_version_subdomain(
        self,
        exc_cls: type[DomainError],
        expected_code: str,
    ) -> None:
        """子域注册 + 编码 + 全局唯一性（自动扫描测试的输入面）。"""
        from src.domain.exceptions._code_ranges import (
            get_range_for_subdomain,
            get_subdomain_for_class,
        )

        assert get_range_for_subdomain("tool_version") == (430, 439)
        assert get_subdomain_for_class(exc_cls.__name__) == "tool_version"
        assert exc_cls().code == expected_code

    def test_exported_from_package_init(self) -> None:
        """4 类经 src.domain.exceptions.__init__ 导出。"""
        import src.domain.exceptions as exc_module

        for name in (
            "ToolVersionNotFoundError",
            "ToolVersionAlreadyExistsError",
            "ToolVersionTrafficWeightError",
            "ToolVersionRollbackError",
        ):
            assert name in exc_module.__all__, f"{name} 未从异常包导出"
            assert hasattr(exc_module, name)
