"""LLMClientPort + LLMConfig + LLMResponse 单元测试

领域层端口契约测试，验证：
- LLMConfig frozen dataclass 构造和工厂方法
- LLMResponse frozen dataclass 构造
- LLMClientPort Protocol 结构验证

领域层零外部依赖：仅使用 Python 标准库
"""

from __future__ import annotations

from typing import get_type_hints

from src.domain.ports.llm_client import LLMClientPort, LLMConfig, LLMResponse


class TestLLMConfig:
    """LLMConfig 值对象测试"""

    def test_frozen_dataclass(self) -> None:
        """验证 LLMConfig 是 frozen dataclass，创建后不可修改"""
        config = LLMConfig(
            api_type="openai",
            model="gpt-4",
            endpoint="https://api.openai.com",
            api_key="sk-test",  # pragma: allowlist secret
            temperature=0.7,
            max_tokens=100,
            timeout=30.0,
        )
        assert config.api_type == "openai"
        assert config.model == "gpt-4"
        assert config.endpoint == "https://api.openai.com"
        assert config.api_key == "sk-test"  # pragma: allowlist secret
        assert config.temperature == 0.7
        assert config.max_tokens == 100
        assert config.timeout == 30.0

    def test_default_values(self) -> None:
        """验证默认值正确"""
        config = LLMConfig(api_type="openai", model="gpt-4")
        assert config.endpoint is None
        assert config.api_key is None
        assert config.temperature == 0.7
        assert config.max_tokens is None
        assert config.timeout == 600.0

    def test_api_type_literal(self) -> None:
        """验证 api_type 使用 Literal 类型约束"""
        hints = get_type_hints(LLMConfig)
        # 运行时检查类型提示是否包含 Literal（通过字符串表示）
        assert "Literal" in str(hints.get("api_type", "")), "api_type 应使用 Literal 类型"

    def test_from_env(self) -> None:
        """验证 from_env() 从环境变量构建 LLMConfig"""
        import os

        os.environ["LLM_API_TYPE"] = "anthropic"
        os.environ["LLM_MODEL"] = "claude-3-opus"
        os.environ["LLM_ENDPOINT"] = "https://api.anthropic.com"
        os.environ["LLM_API_KEY"] = "sk-ant-test"  # pragma: allowlist secret
        os.environ["LLM_TEMPERATURE"] = "0.5"
        os.environ["LLM_MAX_TOKENS"] = "200"
        os.environ["LLM_TIMEOUT"] = "120.0"

        try:
            config = LLMConfig.from_env()
            assert config.api_type == "anthropic"
            assert config.model == "claude-3-opus"
            assert config.endpoint == "https://api.anthropic.com"
            assert config.api_key == "sk-ant-test"  # pragma: allowlist secret
            assert config.temperature == 0.5
            assert config.max_tokens == 200
            assert config.timeout == 120.0
        finally:
            for key in [
                "LLM_API_TYPE",
                "LLM_MODEL",
                "LLM_ENDPOINT",
                "LLM_API_KEY",
                "LLM_TEMPERATURE",
                "LLM_MAX_TOKENS",
                "LLM_TIMEOUT",
            ]:
                os.environ.pop(key, None)

    def test_from_env_defaults(self) -> None:
        """验证 from_env() 使用默认值"""
        config = LLMConfig.from_env()
        assert config.api_type == "openai"
        assert config.model == "qwen2.5:7b"
        assert config.temperature == 0.7
        assert config.timeout == 600.0

    def test_frozen_cannot_modify(self) -> None:
        """验证 frozen dataclass 不可修改"""
        config = LLMConfig(api_type="openai", model="gpt-4")
        import pytest

        with pytest.raises(AttributeError):
            config.model = "gpt-3.5"  # type: ignore[misc]

    def test_immutable_hashable(self) -> None:
        """验证 frozen dataclass 可哈希（可用作字典键）"""
        config = LLMConfig(api_type="openai", model="gpt-4")
        d = {config: "value"}
        assert d[config] == "value"


class TestLLMResponse:
    """LLMResponse 值对象测试"""

    def test_frozen_dataclass(self) -> None:
        """验证 LLMResponse 是 frozen dataclass"""
        response = LLMResponse(
            content="Hello, world!",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model="gpt-4",
        )
        assert response.content == "Hello, world!"
        assert response.finish_reason == "stop"
        assert response.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert response.model == "gpt-4"

    def test_default_values(self) -> None:
        """验证默认值"""
        response = LLMResponse(content="Hello")
        assert response.finish_reason is None
        assert response.usage is None
        assert response.model is None

    def test_frozen_cannot_modify(self) -> None:
        """验证 frozen dataclass 不可修改"""
        response = LLMResponse(content="Hello")
        import pytest

        with pytest.raises(AttributeError):
            response.content = "World"  # type: ignore[misc]


class TestLLMClientPort:
    """LLMClientPort Protocol 测试"""

    def test_is_protocol(self) -> None:
        """验证 LLMClientPort 是 typing.Protocol"""
        # Protocol classes have _is_protocol flag
        assert getattr(LLMClientPort, "_is_protocol", False) is True

    def test_has_generate_method(self) -> None:
        """验证 port 包含 generate 方法"""
        assert hasattr(LLMClientPort, "generate"), "LLMClientPort 应包含 generate 方法"

    def test_has_structured_generate_method(self) -> None:
        """验证 port 包含 structured_generate 方法"""
        assert hasattr(LLMClientPort, "structured_generate"), "LLMClientPort 应包含 structured_generate 方法"

    def test_has_close_method(self) -> None:
        """验证 port 包含 close 方法"""
        assert hasattr(LLMClientPort, "close"), "LLMClientPort 应包含 close 方法"

    def test_generate_signature(self) -> None:
        """验证 generate 方法签名"""
        import inspect

        sig = inspect.signature(LLMClientPort.generate)
        params = {name: param for name, param in sig.parameters.items() if name != "return"}
        assert "prompt" in params, "generate 应包含 prompt 参数"
        assert "config" in params, "generate 应包含 config 参数"
        # config 参数应为可选
        assert params["config"].default is None, "config 应默认为 None"

    def test_structured_generate_signature(self) -> None:
        """验证 structured_generate 方法签名"""
        import inspect

        sig = inspect.signature(LLMClientPort.structured_generate)
        params = {name: param for name, param in sig.parameters.items() if name != "return"}
        assert "prompt" in params, "structured_generate 应包含 prompt 参数"
        assert "response_schema" in params, "structured_generate 应包含 response_schema 参数"
        assert "config" in params, "structured_generate 应包含 config 参数"
        assert params["config"].default is None, "config 应默认为 None"

    def test_response_schema_type_any(self) -> None:
        """验证 structured_generate 的 response_schema 参数为 type[Any] 而非 type[BaseModel]"""
        import inspect

        sig = inspect.signature(LLMClientPort.structured_generate)
        response_schema_param = sig.parameters.get("response_schema")
        assert response_schema_param is not None, "structured_generate 应包含 response_schema 参数"
        # 类型注解应为 type[Any]
        hint = response_schema_param.annotation
        hint_str = str(hint)
        assert "Any" in hint_str, f"response_schema 应为 type[Any]，实际为 {hint_str}"

    def test_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""

        # 使用 runtime_checkable 验证
        assert hasattr(LLMClientPort, "__instancecheck__"), "应为 runtime_checkable"

    def test_concrete_implementation_validation(self) -> None:
        """验证符合 Protocol 的类可通过 isinstance 检查"""

        class MockLLMClient:
            async def generate(self, prompt: str, config: LLMConfig | None = None) -> LLMResponse:
                return LLMResponse(content="test")

            async def structured_generate(self, prompt: str, response_schema: type, config: LLMConfig | None = None):
                return response_schema()

            async def close(self) -> None:
                pass

        client = MockLLMClient()
        # 验证 Protocol 的 isinstance 检查
        assert isinstance(client, LLMClientPort), "MockLLMClient 应通过 isinstance 检查"
