"""基础设施层 UDMR 配置模块

提供统一动态模型路由（UDMR）的配置，包括本地模型和多云端模型配置

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

_VALID_API_TYPES = ("openai", "anthropic", "openai_responses")
_API_TYPE_MAP: dict[str, Literal["openai", "anthropic", "openai_responses"]] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "openai_responses": "openai_responses",
}
_BOOL_TRUE = ("true", "1", "yes", "on")
_BOOL_FALSE = ("false", "0", "no", "off")


@dataclass(frozen=True)
class CloudModelConfig:
    """单云端模型配置.

    Attributes:
        api_type: API 格式类型（openai/anthropic/openai_responses）
        endpoint: 云端 API Base URL
        api_key: API 认证密钥
        model: 模型标识符
        enabled: 是否启用
        max_tokens: 最大 token 数（Anthropic 必需）
        temperature: 生成温度
    """

    api_type: Literal["openai", "anthropic", "openai_responses"] = "openai"
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True
    max_tokens: int | None = None
    temperature: float = 0.7
    price_per_input_1k_tokens: float = 0.02
    price_per_output_1k_tokens: float = 0.02


@dataclass(frozen=True)
class UDMRConfig:
    """统一动态模型路由（UDMR）配置.

    Attributes:
        enabled: 是否启用 UDMR
        local_first: 是否优先使用本地模型
        local_model: 本地模型标识符
        llm_timeout: LLM 调用超时（秒）
        healthcheck_interval: 健康检查间隔（秒）
        cloud_configs: 云端模型配置列表
    """

    enabled: bool = True
    local_first: bool = False
    local_model: str = "qwen2.5:7b"
    llm_timeout: int = 600
    healthcheck_interval: int = 300
    cloud_configs: list[CloudModelConfig] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> UDMRConfig:
        """从环境变量加载配置.

        Returns:
            UDMRConfig 实例

        Raises:
            ValueError: 环境变量值不合法时抛出
        """
        enabled_str = os.getenv("UDMR_ENABLED", "true").lower()
        local_first_str = os.getenv("UDMR_LOCAL_FIRST", "false").lower()
        local_model = os.getenv("UDMR_LOCAL_MODEL", "qwen2.5:7b")
        timeout_str = os.getenv("UDMR_LLM_TIMEOUT", "600")
        healthcheck_str = os.getenv("UDMR_HEALTHCHECK_INTERVAL", "300")

        # 解析超时
        try:
            timeout = int(timeout_str)
            if timeout <= 0:
                raise ValueError(f"UDMR_LLM_TIMEOUT must be positive: {timeout}")
        except ValueError as e:
            raise ValueError(f"Invalid UDMR_LLM_TIMEOUT value: {timeout_str}") from e

        # 解析健康检查间隔
        try:
            healthcheck = int(healthcheck_str)
            if healthcheck <= 0:
                raise ValueError(f"UDMR_HEALTHCHECK_INTERVAL must be positive: {healthcheck}")
        except ValueError as e:
            raise ValueError(f"Invalid UDMR_HEALTHCHECK_INTERVAL value: {healthcheck_str}") from e

        # 循环解析云端模型配置（UDMR_CLOUD_0_* 到 UDMR_CLOUD_9_*）
        cloud_configs: list[CloudModelConfig] = []
        for i in range(10):
            cloud = _parse_cloud_config(i)
            if cloud is not None:
                cloud_configs.append(cloud)

        return cls(
            enabled=enabled_str in _BOOL_TRUE,
            local_first=local_first_str in _BOOL_TRUE,
            local_model=local_model,
            llm_timeout=timeout,
            healthcheck_interval=healthcheck,
            cloud_configs=cloud_configs,
        )


def _parse_cloud_config(index: int) -> CloudModelConfig | None:
    """解析单组云端模型环境变量.

    Args:
        index: 云端模型索引（0-9）

    Returns:
        CloudModelConfig 实例，或 None（未配置/禁用/无效）

    Raises:
        ValueError: api_type 无效或 Anthropic 缺少 max_tokens 或定价为负
    """
    prefix = f"UDMR_CLOUD_{index}_"
    enabled_str = os.getenv(prefix + "ENABLED", "true").lower()

    # 未启用则跳过
    if enabled_str in _BOOL_FALSE:
        return None

    model = os.getenv(prefix + "MODEL", "")
    # 缺少模型名称则跳过
    if not model:
        return None

    api_type_raw = os.getenv(prefix + "API_TYPE", "openai").lower()
    api_type = _API_TYPE_MAP.get(api_type_raw)
    if api_type is None:
        raise ValueError(f"Invalid UDMR_CLOUD_{index}_API_TYPE: {api_type_raw}. Must be one of: {', '.join(_VALID_API_TYPES)}")

    endpoint = os.getenv(prefix + "ENDPOINT", "")
    api_key = os.getenv(prefix + "API_KEY", "")

    # max_tokens 解析
    max_tokens_str = os.getenv(prefix + "MAX_TOKENS", "")
    max_tokens: int | None = None
    if max_tokens_str:
        try:
            max_tokens = int(max_tokens_str)
        except ValueError:
            raise ValueError(f"Invalid UDMR_CLOUD_{index}_MAX_TOKENS: {max_tokens_str}") from None

    # Anthropic 必须提供 max_tokens
    if api_type == "anthropic" and max_tokens is None:
        raise ValueError(f"UDMR_CLOUD_{index}_MAX_TOKENS is required when API_TYPE=anthropic")

    # temperature 解析
    temperature_str = os.getenv(prefix + "TEMPERATURE", "0.7")
    try:
        temperature = float(temperature_str)
    except ValueError:
        raise ValueError(f"Invalid UDMR_CLOUD_{index}_TEMPERATURE: {temperature_str}") from None

    # 定价解析（Story 1.19）
    price_input_str = os.getenv(prefix + "PRICE_INPUT", "0.02")
    try:
        price_input = float(price_input_str)
    except ValueError:
        raise ValueError(f"Invalid UDMR_CLOUD_{index}_PRICE_INPUT: {price_input_str}") from None
    if price_input < 0:
        raise ValueError(f"UDMR_CLOUD_{index}_PRICE_INPUT must be non-negative. Got: {price_input}")

    price_output_str = os.getenv(prefix + "PRICE_OUTPUT", "0.02")
    try:
        price_output = float(price_output_str)
    except ValueError:
        raise ValueError(f"Invalid UDMR_CLOUD_{index}_PRICE_OUTPUT: {price_output_str}") from None
    if price_output < 0:
        raise ValueError(f"UDMR_CLOUD_{index}_PRICE_OUTPUT must be non-negative. Got: {price_output}")

    return CloudModelConfig(
        api_type=api_type,
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        enabled=True,
        max_tokens=max_tokens,
        temperature=temperature,
        price_per_input_1k_tokens=price_input,
        price_per_output_1k_tokens=price_output,
    )
