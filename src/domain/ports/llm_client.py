"""领域层 LLM 客户端端口模块

定义 LLM 客户端端口契约（LLMClientPort）及其值对象（LLMConfig/LLMResponse）。
遵循六边形架构：领域层零外部依赖，仅使用 Python 标准库。

设计约束：
- LLMClientPort 是 typing.Protocol，使用 @runtime_checkable
- LLMConfig 是 frozen dataclass，封装 LLM 调用参数
- LLMResponse 是 frozen dataclass，封装 LLM 响应结果
- structured_generate() 的 response_schema 参数使用 type[Any]（领域层不依赖 pydantic）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast, runtime_checkable

# LLMConfig 的 api_type 字面量类型
_API_TYPE_LITERAL = Literal["openai", "anthropic", "openai_responses"]


@dataclass(frozen=True)
class LLMConfig:
    """LLM 调用配置值对象

    Attributes:
        api_type: API 格式类型（openai / anthropic / openai_responses）
        model: 模型名称
        endpoint: API 端点（可选，默认为 None 使用 LiteLLM 默认端点）
        api_key: API 密钥（可选，默认为 None 使用环境变量）
        temperature: 采样温度（0.0-2.0，默认 0.7）
        max_tokens: 最大生成 Token 数（可选，默认 None 表示模型默认值）
        timeout: 请求超时秒数（默认 600.0）
    """

    api_type: _API_TYPE_LITERAL = "openai"
    model: str = ""
    endpoint: str | None = None
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    timeout: float = 600.0

    @classmethod
    def from_env(cls) -> LLMConfig:
        """从环境变量构建 LLMConfig

        环境变量：
            LLM_API_TYPE: API 格式类型（默认 "openai"）
            LLM_MODEL: 模型名称（默认 "qwen2.5:7b"）
            LLM_ENDPOINT: API 端点（可选）
            LLM_API_KEY: API 密钥（可选）
            LLM_TEMPERATURE: 采样温度（默认 0.7）
            LLM_MAX_TOKENS: 最大 Token 数（可选）
            LLM_TIMEOUT: 请求超时秒数（默认 600.0）

        Returns:
            LLMConfig 实例
        """
        api_type_str = os.getenv("LLM_API_TYPE", "openai").lower()
        # 验证 api_type 合法性
        valid_types = {"openai", "anthropic", "openai_responses"}
        if api_type_str not in valid_types:
            api_type_str = "openai"

        max_tokens_str = os.getenv("LLM_MAX_TOKENS", "")
        max_tokens: int | None = None
        if max_tokens_str:
            try:
                max_tokens = int(max_tokens_str)
            except ValueError:
                max_tokens = None

        timeout_str = os.getenv("LLM_TIMEOUT", "600.0")
        try:
            timeout = float(timeout_str)
        except ValueError:
            timeout = 600.0

        temperature_str = os.getenv("LLM_TEMPERATURE", "0.7")
        try:
            temperature = float(temperature_str)
        except ValueError:
            temperature = 0.7

        return cls(
            api_type=cast(_API_TYPE_LITERAL, api_type_str),
            model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
            endpoint=os.getenv("LLM_ENDPOINT", None),
            api_key=os.getenv("LLM_API_KEY", None),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def __repr__(self) -> str:
        """脱敏表示：不暴露 api_key 明文

        默认 dataclass __repr__ 会输出 api_key 明文，可能导致密钥泄露到日志。
        此处用掩码替代，保证可观测性的同时保护密钥安全。
        """
        api_key_repr = "***" if self.api_key else "None"
        return (
            f"LLMConfig(api_type={self.api_type!r}, model={self.model!r}, "
            f"endpoint={self.endpoint!r}, api_key={api_key_repr}, "
            f"temperature={self.temperature!r}, max_tokens={self.max_tokens!r}, "
            f"timeout={self.timeout!r})"
        )


@dataclass(frozen=True)
class LLMResponse:
    """LLM 响应结果值对象

    Attributes:
        content: 生成文本内容
        finish_reason: 完成原因（"stop" / "length" / "content_filter" 等）
        usage: Token 消耗统计（如 {"prompt_tokens": 10, "completion_tokens": 20}）
        model: 实际使用的模型名称
    """

    content: str = ""
    finish_reason: str | None = None
    usage: dict | None = None
    model: str | None = None


@runtime_checkable
class LLMClientPort(Protocol):
    """LLM 客户端端口协议

    定义统一的 LLM 调用接口，包含标准文本生成和结构化输出两种模式。
    所有实现类必须提供以下三个方法。
    """

    async def generate(
        self,
        prompt: str,
        config: LLMConfig | None = None,
    ) -> LLMResponse:
        """标准 LLM 文本生成

        Args:
            prompt: 输入提示文本
            config: LLM 调用配置（可选，使用默认配置）

        Returns:
            LLMResponse 包含生成的文本内容

        Raises:
            LLMAPIError: LLM API 返回错误
            LLMResponseError: 响应解析错误
            LLMConfigError: 配置错误
            ServiceUnavailableError: 熔断器断开或客户端已关闭
            TimeoutError: 请求超时
        """
        ...

    async def structured_generate(
        self,
        prompt: str,
        response_schema: type[Any],
        config: LLMConfig | None = None,
    ) -> Any:
        """结构化输出生成

        使用 Pydantic Schema 驱动的结构化输出，返回验证后的 Schema 对象。
        response_schema 参数使用 type[Any] 而非 type[BaseModel]，
        确保领域层不依赖 pydantic。

        Args:
            prompt: 输入提示文本
            response_schema: 目标 Schema 类（Pydantic BaseModel 子类）
            config: LLM 调用配置（可选，使用默认配置）

        Returns:
            response_schema 类型的实例（已验证）

        Raises:
            LLMAPIError: LLM API 返回错误
            LLMResponseError: 响应解析错误（含 Schema 验证失败）
            LLMConfigError: 配置错误
            ServiceUnavailableError: 熔断器断开或客户端已关闭
            TimeoutError: 请求超时
        """
        ...

    async def close(self) -> None:
        """释放资源

        关闭 HTTP 连接池等资源。
        重复调用 close() 是安全的（幂等）。
        """
        ...


__all__ = [
    "LLMClientPort",
    "LLMConfig",
    "LLMResponse",
]
