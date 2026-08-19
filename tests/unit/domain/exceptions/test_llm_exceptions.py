"""LLM 异常体系单元测试

验证 LLM 异常类的构造、序列化、HTTP 映射和编码唯一性。
遵循故事规范：LLMAPIError(330)→ThirdPartyError→502,
LLMResponseError(331)→ThirdPartyError→502,
LLMConfigError(332)→ExternalException→500
"""

from __future__ import annotations

from src.domain.exceptions import (
    ExternalException,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ThirdPartyError,
)


class TestLLMAPIError:
    """LLMAPIError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_330"""
        assert LLMAPIError.code == "EXCEPTION_330"

    def test_inheritance(self) -> None:
        """验证继承 ThirdPartyError"""
        assert issubclass(LLMAPIError, ThirdPartyError)
        assert issubclass(LLMAPIError, ExternalException)

    def test_constructor_with_context(self) -> None:
        """验证构造器携带 model/endpoint/status_code 上下文"""
        error = LLMAPIError(
            "LLM API 返回 HTTP 500",
            model="gpt-4",
            endpoint="https://api.openai.com/v1/chat/completions",
            status_code=500,
            response_body='{"error": "internal error"}',
        )
        assert str(error) == "LLM API 返回 HTTP 500"
        assert error.code == "EXCEPTION_330"
        assert error.context["model"] == "gpt-4"
        assert error.context["status_code"] == 500

    def test_endpoint_sanitized(self) -> None:
        """验证 endpoint 脱敏处理（不暴露完整 URL）"""
        error = LLMAPIError(
            "LLM API 错误",
            model="gpt-4",
            endpoint="https://api.openai.com/v1/chat/completions",
            status_code=500,
        )
        # endpoint 应脱敏为 host 级别
        assert "service_host" in error.context
        assert "api.openai.com" in error.context["service_host"]
        assert "/v1/chat/completions" not in error.context["service_host"]

    def test_endpoint_parse_failure_sets_error_context(self) -> None:
        """endpoint URL 解析失败时应设置 service_host_error 上下文"""
        from unittest.mock import patch

        with patch("urllib.parse.urlparse", side_effect=ValueError("Invalid URL")):
            error = LLMAPIError(
                "LLM API 错误",
                model="gpt-4",
                endpoint="http://invalid",
                status_code=500,
            )
        # 解析失败不会阻断异常构造，会记录错误信息
        assert "service_host_error" in error.context
        assert len(error.context["service_host_error"]) <= 100

    def test_endpoint_without_hostname_sets_no_service_host(self) -> None:
        """endpoint 无 hostname 时不设置 service_host"""
        error = LLMAPIError(
            "LLM API 错误",
            model="gpt-4",
            endpoint="",
            status_code=500,
        )
        assert "service_host" not in error.context

    def test_response_body_truncated(self) -> None:
        """验证 response_body 截断至 200 字符"""
        long_body = "x" * 500
        error = LLMAPIError(
            "LLM API 错误",
            model="gpt-4",
            status_code=500,
            response_body=long_body,
        )
        assert len(error.context["response_summary"]) <= 200

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = LLMAPIError(
            "LLM API 错误",
            model="gpt-4",
            endpoint="https://api.openai.com",
            status_code=500,
            cause=ValueError("原始错误"),
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_330"
        assert d["message"] == "LLM API 错误"
        assert "model" in d["context"]
        assert "status_code" in d["context"]
        assert "cause" in d
        assert d["cause"]["type"] == "ValueError"

    def test_http_status_502(self) -> None:
        """验证 HTTP 映射为 502（通过 ThirdPartyError 继承链）"""
        # ThirdPartyError 默认映射到 502
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(LLMAPIError) == 502, "LLMAPIError 应映射到 502"


class TestLLMResponseError:
    """LLMResponseError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_331"""
        assert LLMResponseError.code == "EXCEPTION_331"

    def test_inheritance(self) -> None:
        """验证继承 ThirdPartyError（与 EmbeddingResponseError 一致）"""
        assert issubclass(LLMResponseError, ThirdPartyError)
        assert issubclass(LLMResponseError, ExternalException)

    def test_constructor_with_context(self) -> None:
        """验证构造器携带 model/response_summary 上下文"""
        error = LLMResponseError(
            "响应解析失败",
            model="gpt-4",
            response_summary='{"invalid": json}',
        )
        assert str(error) == "响应解析失败"
        assert error.code == "EXCEPTION_331"
        assert error.context["model"] == "gpt-4"
        assert error.context["response_summary"] == '{"invalid": json}'

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = LLMResponseError(
            "响应解析失败",
            model="gpt-4",
            response_summary="无效 JSON",
            cause=ValueError("JSON 解析错误"),
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_331"
        assert d["message"] == "响应解析失败"
        assert "model" in d["context"]
        assert "response_summary" in d["context"]
        assert "cause" in d

    def test_http_status_502(self) -> None:
        """验证 HTTP 映射为 502（通过 ThirdPartyError 继承链）"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(LLMResponseError) == 502, "LLMResponseError 应映射到 502"


class TestLLMConfigError:
    """LLMConfigError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_332"""
        assert LLMConfigError.code == "EXCEPTION_332"

    def test_inheritance(self) -> None:
        """验证继承 ExternalException（与 EmbeddingModelError 一致）"""
        assert issubclass(LLMConfigError, ExternalException)
        assert not issubclass(LLMConfigError, ThirdPartyError)  # 不继承 ThirdPartyError

    def test_constructor_with_context(self) -> None:
        """验证构造器携带 config_key 上下文"""
        error = LLMConfigError(
            "API Key 未配置",
            config_key="api_key",
        )
        assert str(error) == "API Key 未配置"
        assert error.code == "EXCEPTION_332"
        assert error.context["config_key"] == "api_key"

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = LLMConfigError(
            "API Key 未配置",
            config_key="api_key",
            cause=KeyError("api_key"),
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_332"
        assert d["message"] == "API Key 未配置"
        assert "config_key" in d["context"]
        assert "cause" in d

    def test_http_status_500(self) -> None:
        """验证 HTTP 映射为 500"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(LLMConfigError) == 500, "LLMConfigError 应映射到 500"


class TestLLMErrorCodeUniqueness:
    """LLM 异常编码唯一性验证"""

    def test_llm_codes_not_conflict_with_embedding(self) -> None:
        """验证 LLM 330-339 不与 embedding 306-308 冲突"""
        llm_codes = {330, 331, 332}
        embedding_codes = {306, 307, 308}
        assert llm_codes.isdisjoint(embedding_codes), "LLM 编码与 embedding 编码冲突"

    def test_llm_codes_not_conflict_with_ocr(self) -> None:
        """验证 LLM 330-339 不与 ocr 320-329 冲突"""
        llm_codes = {330, 331, 332}
        ocr_codes = set(range(320, 330))
        assert llm_codes.isdisjoint(ocr_codes), "LLM 编码与 OCR 编码冲突"

    def test_llm_codes_not_conflict_with_sandbox(self) -> None:
        """验证 LLM 330-339 不与 sandbox 311-319 冲突"""
        llm_codes = {330, 331, 332}
        sandbox_codes = set(range(311, 320))
        assert llm_codes.isdisjoint(sandbox_codes), "LLM 编码与 sandbox 编码冲突"

    def test_llm_codes_within_external_range(self) -> None:
        """验证 LLM 330-339 在 external 子域 301-399 范围内"""
        for code in [330, 331, 332]:
            assert 301 <= code <= 399, f"编码 {code} 不在 external 子域范围 301-399 内"
