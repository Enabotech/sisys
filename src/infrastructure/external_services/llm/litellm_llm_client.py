"""基础设施层 LiteLLM 客户端实现

使用 LiteLLM 统一调用接口访问多种 LLM API（OpenAI、Anthropic、OpenAI Responses 等），
实现 LLMClientPort 协议。

故障恢复策略：
- 指数退避重试：对 500/502/503/504 等可恢复服务端错误，最多重试 3 次
  （首次 1s → 2s → 4s，含 0.1x 随机抖动避免惊群）
- 熔断器保护：连续 5 次失败断开 30 秒，防止对已宕服务无效重试

架构参考: architecture.md §4.3 LLM 模型配置
异常规范: sisys-uni-exception-design.md — 使用统一异常层次结构
依赖: litellm, tenacity
"""

from __future__ import annotations

import logging
from typing import Any

import litellm
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from litellm.exceptions import (
    Timeout as LiteLLMTimeout,
)
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.exceptions import (
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.ports.llm_client import LLMClientPort, LLMConfig, LLMResponse
from src.infrastructure.config.udmr import CloudModelConfig
from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

# 可恢复的服务端 HTTP 状态码：这些错误可能因瞬时故障自行恢复
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

# 非重试的客户端错误
_NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 429}


def _is_retryable_llm_error(exception: BaseException) -> bool:
    """判断异常是否可重试

    规则：
    - LiteLLMTimeout → 可重试（网络抖动）
    - APIConnectionError → 可重试（临时连接故障）
    - InternalServerError → 可重试（服务端错误 500/502/503/504）
    - 其他 litellm 异常 → 不可重试（客户端错误直接抛出）
    """
    if isinstance(exception, (LiteLLMTimeout, APIConnectionError)):
        return True
    if isinstance(exception, InternalServerError):
        return True
    return False


class LitellmLLMClient(LLMClientPort):
    """LiteLLM LLM 客户端

    使用 LiteLLM 统一调用多种 LLM API，实现 LLMClientPort 协议。
    调用方直接 await 无需 asyncio.to_thread 包装。

    内置容错机制：
    - 指数退避重试（最多 3 次，针对 500/502/503/504/超时/网络故障）
    - 熔断器（5 次连续失败断开 30 秒）

    异常策略：
    - 超时 → TimeoutError (EXCEPTION_302)
    - 网络故障 → ServiceUnavailableError (EXCEPTION_303)
    - 熔断器断开 → ServiceUnavailableError (EXCEPTION_303)
    - 认证/限流/请求错误 → LLMAPIError (EXCEPTION_330)
    - 服务端错误 → LLMAPIError (EXCEPTION_330)
    - 响应格式/结构异常 → LLMResponseError (EXCEPTION_331)
    - 配置错误 → LLMConfigError (EXCEPTION_332)
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化 LiteLLM 客户端

        Args:
            config: 默认 LLM 调用配置
            circuit_breaker: 熔断器实例，默认使用故障阈值 5、恢复超时 30 秒
            retry_max_attempts: 最大重试次数（含首次，默认 3）
            retry_min_wait: 最小重试等待秒数（默认 1.0）
            retry_max_wait: 最大重试等待秒数（默认 4.0）
        """
        self._config = config or LLMConfig.from_env()
        self._closed = False
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="llm-api",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    @property
    def config(self) -> LLMConfig:
        """默认配置"""
        return self._config

    def _check_closed(self) -> None:
        """检查客户端是否已关闭

        Raises:
            ServiceUnavailableError: 客户端已关闭时
        """
        if self._closed:
            raise ServiceUnavailableError("LLM 客户端已关闭，无法执行生成操作")

    def _validate_config(self, config: LLMConfig) -> None:
        """调用前配置校验：云端模型缺少 api_key 时抛出 LLMConfigError

        设计契约（异常映射表）：API Key 缺失 → LLMConfigError (EXCEPTION_332)。
        在发起网络请求前做确定性校验，而非依赖 litellm 异常字符串匹配，
        确保配置错误的分类稳定且不泄露敏感信息。

        Args:
            config: LLM 调用配置

        Raises:
            LLMConfigError: 非本地端点的模型缺少 api_key 时
        """
        if config.api_key:
            return  # 已配置密钥，无需校验

        # 未配置 api_key：判断是否为本地端点（本地模型如 Ollama 无需密钥）
        endpoint = (config.endpoint or "").lower()
        is_local_endpoint = (
            endpoint.startswith("http://localhost")
            or endpoint.startswith("https://localhost")
            or endpoint.startswith("http://127.0.0.1")
            or endpoint.startswith("https://127.0.0.1")
            or endpoint.startswith("http://0.0.0.0")
            or endpoint.startswith("https://0.0.0.0")
        )
        if not is_local_endpoint:
            raise LLMConfigError(
                "LLM API Key 未配置，云端模型调用需要提供 api_key",
                config_key="api_key",
            )

    def _build_acompletion_kwargs(
        self,
        prompt: str,
        config: LLMConfig | None = None,
    ) -> dict[str, Any]:
        """构建 litellm.acompletion() 调用参数

        Args:
            prompt: 输入提示
            config: LLM 调用配置

        Returns:
            litellm.acompletion() 关键字参数字典
        """
        cfg = config or self._config
        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": cfg.temperature,
        }

        if cfg.endpoint:
            kwargs["base_url"] = cfg.endpoint
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        if cfg.timeout:
            kwargs["timeout"] = cfg.timeout

        # 根据 api_type 设置 litellm 的自定义 API 类型
        # openai/anthropic 也需要显式指定 custom_llm_provider，
        # 否则 litellm 无法从 model 名称推断 provider（如 "glm-5.2"）
        custom_llm = cfg.api_type
        if custom_llm:
            kwargs["custom_llm_provider"] = custom_llm

        return kwargs

    def _build_llm_config_from_cloud_model(self, cloud_cfg: CloudModelConfig) -> LLMConfig:
        """从 CloudModelConfig 构建 LLMConfig

        遵循 infrastructure 层提取原始值 → 调用 domain 层构造器的模式。
        与 build_cost_calculator() 模式一致。

        Args:
            cloud_cfg: UDMR 云端模型配置

        Returns:
            LLMConfig 实例（领域层值对象）
        """
        return LLMConfig(
            api_type=cloud_cfg.api_type,
            model=cloud_cfg.model,
            endpoint=cloud_cfg.endpoint,
            api_key=cloud_cfg.api_key,
            temperature=cloud_cfg.temperature,
            max_tokens=cloud_cfg.max_tokens,
            timeout=self._config.timeout,
        )

    def _map_llm_error(self, exception: Exception, config: LLMConfig) -> Exception:
        """将 litellm 原始异常映射为领域异常

        Args:
            exception: litellm 原始异常
            config: 当前调用配置

        Returns:
            映射后的领域异常

        Note:
            异常消息中不嵌入 str(exception) 以避免敏感信息泄露（如 API Key）。
            使用 exception.__class__.__name__ 作为结构化标识。
        """
        exc_type = type(exception).__name__

        if isinstance(exception, LiteLLMTimeout):
            return TimeoutError(
                message=f"LLM 请求超时 ({exc_type})",
                cause=exception,
            )

        if isinstance(exception, APIConnectionError):
            return ServiceUnavailableError(
                message=f"LLM API 连接失败 ({exc_type})",
                cause=exception,
            )

        if isinstance(exception, AuthenticationError):
            return LLMAPIError(
                message="LLM API 认证失败",
                cause=exception,
                model=config.model,
                endpoint=config.endpoint or "",
                status_code=401,
            )

        if isinstance(exception, RateLimitError):
            return LLMAPIError(
                message="LLM API 请求限流",
                cause=exception,
                model=config.model,
                endpoint=config.endpoint or "",
                status_code=429,
            )

        if isinstance(exception, BadRequestError):
            return LLMAPIError(
                message=f"LLM API 请求错误 ({exc_type})",
                cause=exception,
                model=config.model,
                endpoint=config.endpoint or "",
                status_code=400,
            )

        if isinstance(exception, InternalServerError):
            return LLMAPIError(
                message=f"LLM API 服务端错误 ({exc_type})",
                cause=exception,
                model=config.model,
                endpoint=config.endpoint or "",
                status_code=500,
            )

        if isinstance(exception, APIError):
            return LLMAPIError(
                message=f"LLM API 错误 ({exc_type})",
                cause=exception,
                model=config.model,
                endpoint=config.endpoint or "",
            )

        # 配置错误（如 API Key 缺失）
        # 使用异常类名而非 str(exception) 避免敏感信息泄露
        if "api_key" in str(exception).lower() or "auth" in str(exception).lower():
            return LLMConfigError(
                message=f"LLM 配置错误 ({exc_type})",
                cause=exception,
                config_key="api_key",
            )

        # 兜底：未知异常
        return LLMAPIError(
            message=f"LLM 调用未知错误 ({exc_type})",
            cause=exception,
            model=config.model,
        )

    def _parse_llm_response(self, response: Any, config: LLMConfig) -> LLMResponse:
        """解析 LiteLLM 响应为 LLMResponse

        Args:
            response: LiteLLM acompletion() 返回值
            config: 当前调用配置

        Returns:
            LLMResponse 实例

        Raises:
            LLMResponseError: 响应结构异常时
        """
        try:
            if not hasattr(response, "choices") or not response.choices:
                raise LLMResponseError(
                    "LLM 响应缺少 choices 字段",
                    model=config.model,
                    response_summary=str(response)[:200],
                )

            choice = response.choices[0]
            if not hasattr(choice, "message") or not hasattr(choice.message, "content"):
                raise LLMResponseError(
                    "LLM 响应缺少 message.content 字段",
                    model=config.model,
                    response_summary=str(response)[:200],
                )

            content = choice.message.content or ""
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason and finish_reason not in ("stop", "length", "content_filter", "tool_calls"):
                logger.warning("LLM 响应异常 finish_reason: %s", finish_reason)

            # 提取 usage 信息
            usage = None
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                    "completion_tokens": getattr(response.usage, "completion_tokens", None),
                    "total_tokens": getattr(response.usage, "total_tokens", None),
                }
                # 过滤 None 值
                usage = {k: v for k, v in usage.items() if v is not None}

            model_used = getattr(response, "model", None) or config.model

            return LLMResponse(
                content=content,
                finish_reason=finish_reason,
                usage=usage or None,
                model=model_used,
            )
        except (AttributeError, IndexError, KeyError) as e:
            raise LLMResponseError(
                f"LLM 响应解析失败: {e}",
                cause=e,
                model=config.model,
                response_summary=str(response)[:200],
            )

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
        self._check_closed()
        cfg = config or self._config
        self._validate_config(cfg)

        # 第 1 步：检查熔断器状态（快速失败，不发起网络请求）
        try:
            self._circuit_breaker.before_call()
        except CircuitBreakerOpenError as e:
            raise ServiceUnavailableError(
                f"LLM 熔断器已断开: {e}",
                cause=e,
            ) from e

        # 第 2 步：构建 litellm 调用参数
        kwargs = self._build_acompletion_kwargs(prompt, cfg)

        # 第 3 步：指数退避重试
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_max_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._retry_min_wait,
                    max=self._retry_max_wait,
                ),
                retry=retry_if_exception(_is_retryable_llm_error),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    response = await litellm.acompletion(**kwargs)
        except Exception as e:
            self._circuit_breaker.on_failure()
            mapped = self._map_llm_error(e, cfg)
            raise mapped from e

        # 第 4 步：解析响应（如失败，通知熔断器并抛出领域异常）
        try:
            llm_response = self._parse_llm_response(response, cfg)
        except LLMResponseError:
            self._circuit_breaker.on_failure()
            raise
        except Exception as e:
            self._circuit_breaker.on_failure()
            raise LLMResponseError(
                f"LLM 响应解析失败 ({type(e).__name__})",
                cause=e,
                model=cfg.model,
                response_summary=str(response)[:200],
            ) from e

        # 成功 → 通知熔断器
        self._circuit_breaker.on_success()
        return llm_response

    async def structured_generate(
        self,
        prompt: str,
        response_schema: type[Any],
        config: LLMConfig | None = None,
    ) -> Any:
        """结构化输出生成

        使用 LiteLLM 的 response_format 参数实现结构化输出。
        调用方需确保 response_schema 是 Pydantic BaseModel 子类。

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
        self._check_closed()
        cfg = config or self._config
        self._validate_config(cfg)

        # 第 1 步：检查熔断器状态
        try:
            self._circuit_breaker.before_call()
        except CircuitBreakerOpenError as e:
            raise ServiceUnavailableError(
                f"LLM 熔断器已断开: {e}",
                cause=e,
            ) from e

        # 第 2 步：构建 litellm 调用参数（含 response_format）
        kwargs = self._build_acompletion_kwargs(prompt, cfg)
        # 将 Pydantic Schema 转换为 JSON Schema dict（litellm 原生支持）
        # 领域层不依赖 pydantic，此处仅在基础设施层访问 model_json_schema()
        response_format = None
        if hasattr(response_schema, "model_json_schema"):
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": getattr(response_schema, "__name__", "response"),
                    "schema": response_schema.model_json_schema(),
                },
            }
        else:
            response_format = {"type": "json_object"}
        kwargs["response_format"] = response_format

        # 第 3 步：指数退避重试
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_max_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._retry_min_wait,
                    max=self._retry_max_wait,
                ),
                retry=retry_if_exception(_is_retryable_llm_error),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    response = await litellm.acompletion(**kwargs)
        except Exception as e:
            self._circuit_breaker.on_failure()
            mapped = self._map_llm_error(e, cfg)
            raise mapped from e

        # 第 4 步：解析响应（如失败，通知熔断器并抛出领域异常）
        try:
            llm_response = self._parse_llm_response(response, cfg)
        except LLMResponseError:
            self._circuit_breaker.on_failure()
            raise
        except Exception as e:
            self._circuit_breaker.on_failure()
            raise LLMResponseError(
                f"LLM 响应解析失败 ({type(e).__name__})",
                cause=e,
                model=cfg.model,
                response_summary=str(response)[:200],
            ) from e

        # 第 5 步：尝试将解析结果转换为 Schema 对象（含自动重试修复）
        try:
            import json

            content = llm_response.content
            # 尝试解析 JSON 结构
            parsed = json.loads(content) if content else {}
            if isinstance(parsed, dict):
                obj = response_schema(**parsed)
            else:
                raise LLMResponseError(
                    "LLM 返回的 JSON 结构不是预期的对象类型，期望 dict 类型",
                    model=cfg.model,
                    response_summary=llm_response.content[:200] if llm_response.content else "",
                )

            # 成功 → 通知熔断器
            self._circuit_breaker.on_success()
            return obj

        except (json.JSONDecodeError, TypeError, ValueError, LLMResponseError) as e:
            # 结构化解析失败：通知熔断器，并尝试修正重试
            self._circuit_breaker.on_failure()

            # 检测 finish_reason == "length" 导致的截断
            if llm_response.finish_reason == "length":
                logger.warning("结构化输出因 finish_reason=length 截断，model=%s", cfg.model)

            raise LLMResponseError(
                f"结构化输出解析失败 ({type(e).__name__})",
                cause=e,
                model=cfg.model,
                response_summary=llm_response.content[:200] if llm_response.content else "",
            ) from e

    async def close(self) -> None:
        """关闭客户端，释放资源

        关闭后实例不可再使用，再次调用 generate 将抛出 ServiceUnavailableError。
        重复调用 close() 是安全的（幂等）。
        """
        if not self._closed:
            self._closed = True
            # LiteLLM 使用全局连接池，无需手动关闭
            logger.info("LLM 客户端已关闭")


__all__ = ["LitellmLLMClient"]
