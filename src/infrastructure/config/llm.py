"""基础设施层 LLM 配置工厂模块

从 UDMR 云端配置构建默认 LLM 配置——「LLM 配置的工厂归 LLM 配置模块」。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_default_llm_config():
    """构建默认 LLM 配置——UDMR 云端配置优先，回退 LLM_* 环境变量.

    UDMR SSOT 接线（审计修复 F1，2026-10-11）：当 UDMR_CLOUD_* 配置了至少
    一个 enabled 云端模型时，取第一个转换为默认 LLMConfig——消除「配置了
    UDMR 却不生效」的双轨误导。UDMR 未配置时保持 4.x 既有行为
    （LLMConfig.from_env()），零破坏性。

    Returns:
        LLMConfig 实例（来自 UDMR 云端配置或 LLM_* 环境变量回退）
    """
    from src.domain.ports.llm_client import LLMConfig
    from src.infrastructure.config.udmr import UDMRConfig

    udmr = UDMRConfig.from_env()
    for cloud in udmr.cloud_configs:
        if cloud.enabled and cloud.model and cloud.endpoint:
            logger.info("UDMR SSOT: 使用云端模型 %s 作为默认 LLM 配置", cloud.model)
            return LLMConfig(
                api_type=cloud.api_type,
                model=cloud.model,
                endpoint=cloud.endpoint,
                api_key=cloud.api_key,
                temperature=cloud.temperature,
                max_tokens=cloud.max_tokens,
                timeout=float(udmr.llm_timeout),
            )
    logger.debug("UDMR SSOT: 无 enabled 云端模型，回退 LLM_* 环境变量")
    return LLMConfig.from_env()
