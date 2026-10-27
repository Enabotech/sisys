"""基础设施层 Phoenix 追踪配置模块（Story 5.7 — FR-EV-01 追踪面）

PhoenixTracer 的环境契约配置（PHOENIX_* 四变量——env 驱动）。PhoenixTracer 以
仓内既有 opentelemetry ^1.21.0 实现同构追踪语义（OD-1——零新运行时依赖，
arize-phoenix 不引入）；project_name 经 OTel Resource service.name 承载
（Phoenix OTLP 接收端按 service.name 归项目），span 经 OTLP gRPC exporter
指向独立部署的 Phoenix server。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

#: bool 三态真值集合（MetricsConfig.from_env 惯例对齐）
_TRUTHY_VALUES = ("true", "1", "yes")


@dataclass(frozen=True)
class PhoenixConfig:
    """Phoenix 全链路追踪配置（frozen——本 Story 自设加严规格，先例 MetricsConfig 是普通 dataclass）

    从环境变量读取，支持启用开关、OTLP 端点（gRPC 协议钉死——对齐 otel_config
    生产形态）、项目名与采样率；未启用时 PhoenixTracer 全链 NoOp 零开销降级。

    Attributes:
        enabled: 是否启用追踪（PHOENIX_TRACING_ENABLED，默认 false——保守
            默认对齐 EVENT_BUS_OTEL_TRACE_ENABLED 形态）
        endpoint: OTLP gRPC 端点（PHOENIX_OTLP_ENDPOINT，未设时 fallback
            OTEL_EXPORTER_OTLP_ENDPOINT，空串视为未设；默认 localhost:4317）
        project_name: Phoenix 项目名（PHOENIX_PROJECT_NAME，默认 "sisys-agent"
            ——epics 钦定值，经 Resource service.name 承载）
        sampling_ratio: 采样率（PHOENIX_TRACES_SAMPLER_ARG，Phoenix 专属采样
            变量——与 event-bus 栈的 OTEL_TRACES_SAMPLER_ARG 互不干扰；默认
            1.0 全采样，范围 (0, 1.0]——0 采样等价禁用应走 enabled=false）
    """

    enabled: bool = False
    endpoint: str = "http://localhost:4317"
    project_name: str = "sisys-agent"
    sampling_ratio: float = 1.0

    def __post_init__(self) -> None:
        """构造期校验（101 fail-fast——from_env 与直构造两路径统一守护）。

        Raises:
            ConfigurationError: EXCEPTION_101——enabled 非 bool（isinstance 先行，
                bool 子类 int 防呆）/ project_name 空 or 空白 / endpoint 非
                http(s) 前缀 / sampling_ratio 非数值（bool 拒）或 ∉ (0, 1.0]
        """
        if not isinstance(self.enabled, bool):
            raise ConfigurationError(
                message=(
                    f"PHOENIX_TRACING_ENABLED 必须为 bool（bool 三态 'true'/'1'/'yes'），实际类型 {type(self.enabled).__name__}"
                ),
                context={"enabled": self.enabled},
            )
        if not isinstance(self.project_name, str) or not self.project_name.strip():
            raise ConfigurationError(
                message=f"PHOENIX_PROJECT_NAME 不能为空或空白，实际值: {self.project_name!r}",
                context={"project_name": self.project_name},
            )
        if not isinstance(self.endpoint, str) or not self.endpoint.startswith(("http://", "https://")):
            raise ConfigurationError(
                message=f"PHOENIX_OTLP_ENDPOINT 必须以 http:// 或 https:// 开头（OTLP gRPC 端点），实际值: {self.endpoint!r}",
                context={"endpoint": self.endpoint},
            )
        if isinstance(self.sampling_ratio, bool) or not isinstance(self.sampling_ratio, (int, float)):
            raise ConfigurationError(
                message=f"PHOENIX_TRACES_SAMPLER_ARG 必须为数值，实际类型 {type(self.sampling_ratio).__name__}",
                context={"sampling_ratio": self.sampling_ratio},
            )
        if not 0 < float(self.sampling_ratio) <= 1.0:
            raise ConfigurationError(
                message=(
                    f"PHOENIX_TRACES_SAMPLER_ARG 必须在 (0, 1.0] 区间（0 采样等价禁用应走 enabled=false），"
                    f"实际值: {self.sampling_ratio}"
                ),
                context={"sampling_ratio": self.sampling_ratio},
            )

    @classmethod
    def from_env(cls) -> PhoenixConfig:
        """从环境变量创建配置（四变量解析 + endpoint fallback 链 + 空串视为未设）。

        Returns:
            PhoenixConfig 实例

        Raises:
            ConfigurationError: EXCEPTION_101——sampling_ratio 环境值非数值
                （解析层包装，ValueError 禁裸抛）或构造期守卫触发
        """
        enabled = os.getenv("PHOENIX_TRACING_ENABLED", "false").lower() in _TRUTHY_VALUES
        # fallback 链：PHOENIX_OTLP_ENDPOINT > OTEL_EXPORTER_OTLP_ENDPOINT > 默认值；
        # 每级 `or` 形态——set-but-empty 等同未设（compose 注入空串不触发 101）
        endpoint = os.getenv("PHOENIX_OTLP_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4317"
        project_name = os.getenv("PHOENIX_PROJECT_NAME") or "sisys-agent"

        raw_sampling = os.getenv("PHOENIX_TRACES_SAMPLER_ARG", "1.0")
        try:
            sampling_ratio = float(raw_sampling)
        except (ValueError, TypeError):
            raise ConfigurationError(
                message=f"PHOENIX_TRACES_SAMPLER_ARG 值非法: {raw_sampling!r}（需要 (0, 1.0] 区间数值）",
                context={"sampling_ratio": raw_sampling},
            ) from None

        return cls(
            enabled=enabled,
            endpoint=endpoint,
            project_name=project_name,
            sampling_ratio=sampling_ratio,
        )


__all__ = ["PhoenixConfig"]
