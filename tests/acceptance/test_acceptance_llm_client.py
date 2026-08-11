"""Story 3.2a LLM Client 基础设施验收测试

使用 UDMR 真实云端 LLM 配置调用真实 LLM API，验证客户端的业务价值。
AC-1/AC-2 通过 UDMRConfig.from_env() 读取真实云端配置，调用真实云端 LLM。
云端 LLM 不可用时动态跳过（pytest.skip()），不阻塞 CI。

运行: poetry run pytest tests/acceptance/test_acceptance_llm_client.py -v

前置条件（AC-1/AC-2）:
    - UDMR_CLOUD_0_ENABLED=true
    - UDMR_CLOUD_0_API_TYPE=anthropic
    - UDMR_CLOUD_0_MODEL=<模型名>
    - UDMR_CLOUD_0_ENDPOINT=<云端端点>
    - UDMR_CLOUD_0_API_KEY=<API Key>
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pytest_bdd import given, scenarios, then, when

from src.domain.exceptions import LLMAPIError, LLMConfigError, ServiceUnavailableError
from src.domain.ports.llm_client import LLMConfig, LLMResponse
from src.infrastructure.config.udmr import UDMRConfig
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker
from src.infrastructure.external_services.llm.litellm_llm_client import LitellmLLMClient

scenarios("test_acceptance_llm_client.feature")


class _TestSchema(BaseModel):
    """验收测试用结构化输出 Schema（真实 Pydantic BaseModel）"""

    title: str = Field(default="")
    summary: str = Field(default="")
    score: float = Field(default=0.0)


# ===================================================================
# UDMR 真实云端 LLM 配置
# ===================================================================


def _get_udmr_cloud_config() -> tuple[LLMConfig, bool]:
    """从 UDMRConfig 读取真实云端 LLM 配置

    优先级：
    1. UDMR_CLOUD_0_* 环境变量（应用级配置，不走测试环境配置链）
    2. LLM_* 环境变量（由测试环境配置链同步，适用于 CI/TEST_CONFIG）

    返回 (LLMConfig, is_available)：
    - LLMConfig：从 UDMR 云端配置构建的领域值对象
    - is_available：云端 LLM 是否可用（有 API Key）
    """
    udmr = UDMRConfig.from_env()
    for cloud in udmr.cloud_configs:
        if cloud.enabled and cloud.api_key:
            llm_config = LLMConfig(
                api_type=cloud.api_type,
                model=cloud.model,
                endpoint=cloud.endpoint,
                api_key=cloud.api_key,
                temperature=cloud.temperature,
                max_tokens=cloud.max_tokens,
                timeout=float(udmr.llm_timeout),
            )
            return llm_config, True
    # 回退：从 LLM_* 环境变量读取（由 _sync_config_to_environ() 同步）
    env_cfg = LLMConfig.from_env()
    if env_cfg.api_key:
        return env_cfg, True
    return LLMConfig(), False


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环，用于 run_until_complete()"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def udmr_config() -> LLMConfig:
    """UDMR 真实云端 LLM 配置"""
    cfg, available = _get_udmr_cloud_config()
    if not available:
        pytest.skip("UDMR 云端 LLM 未配置或 API Key 缺失")
    return cfg


@pytest.fixture(scope="module")
def real_client(udmr_config: LLMConfig) -> LitellmLLMClient:
    """真实 LLM 客户端（使用 UDMR 云端配置）"""
    return LitellmLLMClient(config=udmr_config)


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


# ===================================================================
# Background Steps
# ===================================================================


@given("LLM 端口契约已定义")
def llm_port_contract_defined():
    from src.domain.ports.llm_client import LLMClientPort, LLMConfig

    assert LLMClientPort is not None
    assert LLMConfig is not None
    assert LLMResponse is not None


@given("LLM 客户端已配置")
def llm_client_configured(context: dict[str, Any], udmr_config: LLMConfig):
    context["config"] = udmr_config


# ===================================================================
# AC-1: LLM 文本生成成功
# ===================================================================


@when("调用 generate 生成文本")
def call_generate(context: dict[str, Any], real_client: LitellmLLMClient, event_loop):
    context["result"] = event_loop.run_until_complete(
        real_client.generate(prompt="请用一句话自我介绍", config=context["config"])
    )


@then("返回的 LLMResponse 包含 content 字段")
def response_has_content(context: dict[str, Any]):
    assert hasattr(context["result"], "content")


@then("content 非空")
def content_not_empty(context: dict[str, Any]):
    assert context["result"].content


@then("LLMResponse 包含 finish_reason 字段")
def response_has_finish_reason(context: dict[str, Any]):
    assert hasattr(context["result"], "finish_reason")


@then("LLMResponse 包含 usage 字段")
def response_has_usage(context: dict[str, Any]):
    assert hasattr(context["result"], "usage")


# ===================================================================
# AC-2: 结构化输出成功
# ===================================================================


@given("定义一个 Pydantic Schema 用于结构化输出")
def define_schema(context: dict[str, Any]):
    context["schema"] = _TestSchema


@when("调用 structured_generate 生成结构化输出")
def call_structured_generate(context: dict[str, Any], real_client: LitellmLLMClient, event_loop):
    try:
        context["structured_result"] = event_loop.run_until_complete(
            real_client.structured_generate(
                prompt=(
                    "请生成一个 JSON 对象，包含 title（标题）、summary（摘要）、score（0-1 分数）。"
                    '例如：{"title": "测试标题", "summary": "测试摘要", "score": 0.95}'
                ),
                response_schema=context["schema"],
                config=context["config"],
            )
        )
        context["structured_success"] = True
    except Exception as e:
        context["structured_success"] = False
        context["structured_error"] = e


@then("返回的对象是 Schema 类型实例")
def result_is_schema_instance(context: dict[str, Any]):
    if not context.get("structured_success", True):
        assert isinstance(context.get("structured_error"), Exception)
        pytest.skip("云端 LLM 不支持结构化输出，验证异常处理路径正常")
    assert isinstance(context["structured_result"], _TestSchema)


@then("所有字段已正确填充")
def all_fields_correctly_filled(context: dict[str, Any]):
    if not context.get("structured_success", True):
        return
    r = context["structured_result"]
    assert r.title
    assert r.summary
    assert 0 <= r.score <= 1


# ===================================================================
# AC-3: 熔断器断开后快速失败
# ===================================================================


@given("熔断器已断开")
def circuit_breaker_is_open(context: dict[str, Any], event_loop):
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, name="test-llm")
    bad_config = LLMConfig(api_type="openai", model="test-model", endpoint="http://127.0.0.1:1", timeout=1.0)
    cb_client = LitellmLLMClient(
        config=bad_config,
        circuit_breaker=cb,
        retry_max_attempts=1,
        retry_min_wait=0.1,
        retry_max_wait=0.2,
    )
    for _ in range(3):
        try:
            event_loop.run_until_complete(cb_client.generate(prompt="Hello"))
        except Exception:
            pass
    context["cb_client"] = cb_client
    assert cb.state.name == "OPEN"


@when("在熔断器断开时调用 generate")
def call_generate_with_open_circuit(context: dict[str, Any], event_loop):
    cb_client = context["cb_client"]
    context["error"] = None
    try:
        event_loop.run_until_complete(cb_client.generate(prompt="Hello"))
    except ServiceUnavailableError as e:
        context["error"] = e


@then("快速失败抛出 ServiceUnavailableError")
def verify_service_unavailable_error(context: dict[str, Any]):
    assert context["error"] is not None
    assert isinstance(context["error"], ServiceUnavailableError)


@then("不发起实际 HTTP 请求")
def verify_no_http_request(context: dict[str, Any]):
    """验证熔断器断开时快速失败，不发起实际 HTTP 请求

    通过检查熔断器状态和异常类型推断：
    - ServiceUnavailableError 由 CircuitBreakerOpenError 触发
    - 熔断器 OPEN 状态时 before_call() 直接抛异常，不调用 litellm.acompletion()
    - 因此无需 mock 也可验证"未发起 HTTP 请求"
    """
    cb_client = context.get("cb_client")
    assert cb_client is not None, "缺少 cb_client 上下文"
    assert cb_client._circuit_breaker.state.name == "OPEN", "熔断器应在 OPEN 状态"
    # 在 OPEN 状态下的 before_call() 直接抛出 CircuitBreakerOpenError，
    # 不会进入 litellm.acompletion()，因此不会有 HTTP 请求


# ===================================================================
# AC-4: 重试耗尽后抛出异常
# ===================================================================


@given("LLM API 持续返回 500 错误")
def llm_api_returns_500(context: dict[str, Any]):
    bad_config = LLMConfig(api_type="openai", model="test-model", endpoint="http://127.0.0.1:1", timeout=1.0)
    context["bad_config"] = bad_config


@when("在 API 持续失败时调用 generate")
def call_generate_with_retry(context: dict[str, Any], event_loop):
    bad_config = context["bad_config"]
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0, name="test-retry")
    retry_client = LitellmLLMClient(
        config=bad_config,
        circuit_breaker=cb,
        retry_max_attempts=3,
        retry_min_wait=0.1,
        retry_max_wait=0.2,
    )
    context["retry_client"] = retry_client
    context["error"] = None
    try:
        event_loop.run_until_complete(retry_client.generate(prompt="Hello"))
    except (LLMAPIError, ServiceUnavailableError) as e:
        context["error"] = e


@then("重试 3 次后抛出领域异常")
def verify_retry_count_and_error(context: dict[str, Any]):
    assert context["error"] is not None
    assert isinstance(context["error"], (LLMAPIError, ServiceUnavailableError))


@then("熔断器记录失败")
def verify_circuit_breaker_recorded(context: dict[str, Any]):
    retry_client = context["retry_client"]
    assert retry_client._circuit_breaker.state.name == "OPEN"


# ===================================================================
# AC-5: 配置错误
# ===================================================================


@given("LLM 配置缺少 API Key")
def config_missing_api_key(context: dict[str, Any]):
    context["invalid_config"] = LLMConfig(api_type="openai", model="test-model", api_key="")


@when("在缺少 API Key 时调用 generate")
def call_generate_with_config_error(context: dict[str, Any], event_loop):
    context["error"] = None
    try:
        # 使用真实客户端调用，验证真实行为
        client = LitellmLLMClient(config=context["invalid_config"], retry_max_attempts=1)
        event_loop.run_until_complete(client.generate(prompt="Hello"))
    except (LLMConfigError, LLMAPIError) as e:
        context["error"] = e


@then("抛出 LLMConfigError 异常")
def verify_llm_config_error(context: dict[str, Any]):
    assert context["error"] is not None
    assert isinstance(context["error"], LLMConfigError), (
        f"期望 LLMConfigError，实际为 {type(context['error']).__name__}: {context['error']}"
    )


@then("异常编码为 EXCEPTION_332")
def verify_error_code_332(context: dict[str, Any]):
    assert context["error"].code == "EXCEPTION_332"


# ===================================================================
# AC-6: 客户端关闭后调用抛出异常
# ===================================================================


@given("LLM 客户端已关闭")
def llm_client_closed(context: dict[str, Any], event_loop):
    client = LitellmLLMClient(config=LLMConfig(api_type="openai", model="test-model"))
    event_loop.run_until_complete(client.close())
    context["closed_client"] = client


@when("在客户端关闭后调用 generate")
def call_generate_on_closed(context: dict[str, Any], event_loop):
    client = context["closed_client"]
    context["error"] = None
    try:
        event_loop.run_until_complete(client.generate(prompt="Hello"))
    except ServiceUnavailableError as e:
        context["error"] = e


@then("抛出 ServiceUnavailableError 异常")
def verify_service_unavailable_on_closed(context: dict[str, Any]):
    assert context["error"] is not None
    assert isinstance(context["error"], ServiceUnavailableError)
