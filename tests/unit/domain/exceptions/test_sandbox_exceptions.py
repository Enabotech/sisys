"""Story 4.4: 沙箱异常单元测试

验证 5 个新沙箱异常（EXCEPTION_315-319）：
- 构造器 + 上下文字段
- code 与 message 正确
- HTTP 映射
- 子域归属 (sandbox)
- 既有 4 个异常回归测试（EXCEPTION_311-314）
"""

from __future__ import annotations

from src.domain.exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxConfigurationError,
    SandboxError,
    SandboxImagePullError,
    SandboxQuotaExceededError,
    SandboxResourceLimitExceededError,
    SandboxTimeoutError,
)
from src.domain.exceptions._code_ranges import (
    get_range_for_subdomain,
    get_subdomain_for_class,
)


class TestSandboxExceptionHierarchy:
    """沙箱异常继承层次测试"""

    def test_sandbox_error_is_external_exception(self) -> None:
        """SandboxError 应继承 ExternalException"""
        from src.domain.exceptions.external_exceptions import ExternalException

        assert issubclass(SandboxError, ExternalException)

    def test_container_start_error_extends_sandbox_error(self) -> None:
        """ContainerStartError 应继承 SandboxError"""
        assert issubclass(ContainerStartError, SandboxError)

    def test_execution_error_extends_sandbox_error(self) -> None:
        """ExecutionError 应继承 SandboxError"""
        assert issubclass(ExecutionError, SandboxError)

    def test_container_stop_error_extends_sandbox_error(self) -> None:
        """ContainerStopError 应继承 SandboxError"""
        assert issubclass(ContainerStopError, SandboxError)

    def test_image_pull_error_extends_container_start_error(self) -> None:
        """SandboxImagePullError 应继承 ContainerStartError"""
        assert issubclass(SandboxImagePullError, ContainerStartError)

    def test_timeout_error_extends_execution_error(self) -> None:
        """SandboxTimeoutError 应继承 ExecutionError"""
        assert issubclass(SandboxTimeoutError, ExecutionError)

    def test_resource_limit_error_extends_execution_error(self) -> None:
        """SandboxResourceLimitExceededError 应继承 ExecutionError"""
        assert issubclass(SandboxResourceLimitExceededError, ExecutionError)

    def test_quota_error_extends_sandbox_error(self) -> None:
        """SandboxQuotaExceededError 应继承 SandboxError"""
        assert issubclass(SandboxQuotaExceededError, SandboxError)

    def test_configuration_error_extends_sandbox_error(self) -> None:
        """SandboxConfigurationError 应继承 SandboxError"""
        assert issubclass(SandboxConfigurationError, SandboxError)


class TestSandboxExceptionCodes:
    """沙箱异常编码测试"""

    def test_sandbox_error_code_311(self) -> None:
        """SandboxError code 应为 EXCEPTION_311"""
        assert SandboxError.code == "EXCEPTION_311"

    def test_container_start_error_code_312(self) -> None:
        """ContainerStartError code 应为 EXCEPTION_312"""
        assert ContainerStartError.code == "EXCEPTION_312"

    def test_execution_error_code_313(self) -> None:
        """ExecutionError code 应为 EXCEPTION_313"""
        assert ExecutionError.code == "EXCEPTION_313"

    def test_container_stop_error_code_314(self) -> None:
        """ContainerStopError code 应为 EXCEPTION_314"""
        assert ContainerStopError.code == "EXCEPTION_314"

    def test_image_pull_error_code_315(self) -> None:
        """SandboxImagePullError code 应为 EXCEPTION_315"""
        assert SandboxImagePullError.code == "EXCEPTION_315"

    def test_timeout_error_code_316(self) -> None:
        """SandboxTimeoutError code 应为 EXCEPTION_316"""
        assert SandboxTimeoutError.code == "EXCEPTION_316"

    def test_resource_limit_error_code_317(self) -> None:
        """SandboxResourceLimitExceededError code 应为 EXCEPTION_317"""
        assert SandboxResourceLimitExceededError.code == "EXCEPTION_317"

    def test_quota_error_code_318(self) -> None:
        """SandboxQuotaExceededError code 应为 EXCEPTION_318"""
        assert SandboxQuotaExceededError.code == "EXCEPTION_318"

    def test_configuration_error_code_319(self) -> None:
        """SandboxConfigurationError code 应为 EXCEPTION_319"""
        assert SandboxConfigurationError.code == "EXCEPTION_319"

    def test_all_sandbox_codes_in_subdomain_range(self) -> None:
        """所有沙箱异常 code 应在 sandbox 子域 311-319 范围内"""
        sandbox_range = get_range_for_subdomain("sandbox")
        assert sandbox_range == (311, 319)

        sandbox_codes = [
            "EXCEPTION_311",
            "EXCEPTION_312",
            "EXCEPTION_313",
            "EXCEPTION_314",
            "EXCEPTION_315",
            "EXCEPTION_316",
            "EXCEPTION_317",
            "EXCEPTION_318",
            "EXCEPTION_319",
        ]
        for code_str in sandbox_codes:
            numeric = int(code_str.split("_")[1])
            assert sandbox_range is not None
            assert sandbox_range[0] <= numeric <= sandbox_range[1], f"{code_str} 不在 sandbox 子域 {sandbox_range} 范围内"

    def test_all_sandbox_classes_in_subdomain_map(self) -> None:
        """所有沙箱异常类应注册到 _CLASS_TO_SUBDOMAIN['sandbox']"""
        sandbox_classes = [
            "SandboxError",
            "ContainerStartError",
            "ContainerStopError",
            "ExecutionError",
            "SandboxImagePullError",
            "SandboxTimeoutError",
            "SandboxResourceLimitExceededError",
            "SandboxQuotaExceededError",
            "SandboxConfigurationError",
        ]
        for cls_name in sandbox_classes:
            subdomain = get_subdomain_for_class(cls_name)
            assert subdomain == "sandbox", f"{cls_name} 未注册到 sandbox 子域"


class TestNewSandboxExceptionConstructors:
    """5 个新沙箱异常构造器测试"""

    def test_image_pull_error_with_context(self) -> None:
        """SandboxImagePullError 构造器应注入上下文字段"""
        exc = SandboxImagePullError(
            "pull failed",
            image="python:3.11-slim@sha256:abc",
            session_id="sess-1234",
            digest="sha256:abc",
            docker_error="manifest unknown",
        )
        assert exc.context["image"] == "python:3.11-slim@sha256:abc"
        assert exc.context["session_id"] == "sess-1234"
        assert exc.context["digest"] == "sha256:abc"
        assert exc.context["docker_error"] == "manifest unknown"
        assert exc.code == "EXCEPTION_315"

    def test_timeout_error_with_context(self) -> None:
        """SandboxTimeoutError 构造器应注入超时上下文"""
        exc = SandboxTimeoutError(
            "execution timeout",
            session_id="sess-5678",
            timeout_sec=30.0,
            execution_id="exec-001",
            docker_exit_code=124,
        )
        assert exc.context["timeout_sec"] == 30.0
        assert exc.context["execution_id"] == "exec-001"
        assert exc.context["docker_exit_code"] == 124
        assert exc.code == "EXCEPTION_316"

    def test_resource_limit_error_with_context(self) -> None:
        """SandboxResourceLimitExceededError 构造器应注入资源超限上下文"""
        exc = SandboxResourceLimitExceededError(
            "memory limit exceeded",
            session_id="sess-9012",
            limit_type="mem",
            limit_value=512,
            actual_value=600,
            docker_exit_code=137,
        )
        assert exc.context["limit_type"] == "mem"
        assert exc.context["limit_value"] == 512
        assert exc.context["actual_value"] == 600
        assert exc.context["docker_exit_code"] == 137
        assert exc.code == "EXCEPTION_317"

    def test_quota_error_with_context(self) -> None:
        """SandboxQuotaExceededError 构造器应注入配额上下文"""
        exc = SandboxQuotaExceededError(
            "concurrent limit reached",
            current_count=50,
            max_count=50,
            tenant_id="tenant-uuid-1234",
        )
        assert exc.context["current_count"] == 50
        assert exc.context["max_count"] == 50
        assert exc.context["tenant_id"] == "tenant-uuid-1234"
        assert exc.code == "EXCEPTION_318"

    def test_configuration_error_with_context(self) -> None:
        """SandboxConfigurationError 构造器应注入字段错误上下文"""
        exc = SandboxConfigurationError(
            "container name too long",
            field_name="container_name",
            field_value="a" * 100,
            reason_detail="length > 64",
        )
        assert exc.context["field_name"] == "container_name"
        assert exc.context["field_value"] == "a" * 100
        assert exc.context["reason_detail"] == "length > 64"
        assert exc.code == "EXCEPTION_319"


class TestSandboxExceptionHTTPMapping:
    """沙箱异常 HTTP 映射测试"""

    def test_http_map_registers_new_exceptions(self) -> None:
        """EXCEPTION_HTTP_MAP 应注册 5 个新沙箱异常"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert SandboxImagePullError in EXCEPTION_HTTP_MAP
        assert SandboxTimeoutError in EXCEPTION_HTTP_MAP
        assert SandboxResourceLimitExceededError in EXCEPTION_HTTP_MAP
        assert SandboxQuotaExceededError in EXCEPTION_HTTP_MAP
        assert SandboxConfigurationError in EXCEPTION_HTTP_MAP

    def test_http_map_default_502(self) -> None:
        """新沙箱异常默认 HTTP 映射应为 502"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[SandboxImagePullError] == status.HTTP_502_BAD_GATEWAY
        assert EXCEPTION_HTTP_MAP[SandboxResourceLimitExceededError] == status.HTTP_502_BAD_GATEWAY
        assert EXCEPTION_HTTP_MAP[SandboxConfigurationError] == status.HTTP_502_BAD_GATEWAY

    def test_http_map_timeout_504(self) -> None:
        """SandboxTimeoutError HTTP 映射应为 504"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[SandboxTimeoutError] == status.HTTP_504_GATEWAY_TIMEOUT

    def test_http_map_quota_503(self) -> None:
        """SandboxQuotaExceededError HTTP 映射应为 503"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[SandboxQuotaExceededError] == status.HTTP_503_SERVICE_UNAVAILABLE


class TestSandboxExceptionToDict:
    """沙箱异常 to_dict 序列化测试"""

    def test_image_pull_error_to_dict(self) -> None:
        """SandboxImagePullError to_dict 应包含上下文"""
        exc = SandboxImagePullError(
            "pull failed",
            image="img:tag",
            session_id="sess-1",
        )
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_315"
        assert data["context"]["image"] == "img:tag"
        assert data["context"]["session_id"] == "sess-1"

    def test_timeout_error_to_dict(self) -> None:
        """SandboxTimeoutError to_dict 应包含超时上下文"""
        exc = SandboxTimeoutError("timeout", session_id="sess-2", timeout_sec=30.0)
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_316"
        assert data["context"]["timeout_sec"] == 30.0

    def test_configuration_error_to_dict(self) -> None:
        """SandboxConfigurationError to_dict 应包含字段错误"""
        exc = SandboxConfigurationError(
            "bad config",
            field_name="mem_limit",
            field_value=9999,
            reason_detail="over limit",
        )
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_319"
        assert data["context"]["field_name"] == "mem_limit"


class TestSandboxExceptionCauseChain:
    """沙箱异常 cause 链测试"""

    def test_image_pull_error_cause_chain(self) -> None:
        """SandboxImagePullError 应保留 cause 链"""
        original = Exception("original error")
        try:
            raise original
        except Exception:
            try:
                raise SandboxImagePullError("wrapper error", image="img:tag") from original
            except SandboxImagePullError as exc:
                assert exc.__cause__ is original
                assert exc.code == "EXCEPTION_315"
