"""PhoenixConfig 配置单元测试（Story 5.7 — Task 1 TDD 循环 A）

覆盖：from_env 四变量矩阵（默认值 / 覆盖 / OTel 端点 fallback 链[R1-F8 三级：
PHOENIX_OTLP_ENDPOINT > OTEL_EXPORTER_OTLP_TRACES_ENDPOINT（信号级）>
OTEL_EXPORTER_OTLP_ENDPOINT（通用级）] / 空串视为未设 / bool 三态）+ 101 守卫
五场景参数化（isinstance → code → context 三段式）+ from_env 非法数值 101 包装
（google_patents from None 先例）。

Run with:
    poetry run pytest tests/unit/infrastructure/config/test_phoenix_config.py -v
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.phoenix import PhoenixConfig

_PHOENIX_VARS = (
    "PHOENIX_TRACING_ENABLED",
    "PHOENIX_OTLP_ENDPOINT",
    "PHOENIX_PROJECT_NAME",
    "PHOENIX_TRACES_SAMPLER_ARG",
)

#: fallback 链的 OTel 侧环境变量（R1-F8 两级：信号级 > 通用级——进程 env 防污染逐用例清理）
_OTEL_ENDPOINT_VARS = (
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
)


class TestPhoenixConfigFromEnv:
    """from_env 四变量解析（bool 三态 + fallback 链 + 空串视为未设）。"""

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """默认值矩阵：false / localhost:4317（gRPC）/ sisys-agent / 1.0 全采样。"""
        for var in _PHOENIX_VARS:
            monkeypatch.delenv(var, raising=False)
        for var in _OTEL_ENDPOINT_VARS:
            monkeypatch.delenv(var, raising=False)

        config = PhoenixConfig.from_env()

        assert config.enabled is False
        assert config.endpoint == "http://localhost:4317"
        assert config.project_name == "sisys-agent"
        assert config.sampling_ratio == 1.0

    def test_from_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """覆盖矩阵：四变量全注入逐项生效（PHOENIX 专属采样变量——与 event-bus 栈互不干扰）。"""
        monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "true")
        monkeypatch.setenv("PHOENIX_OTLP_ENDPOINT", "http://phx.example:4317")
        monkeypatch.setenv("PHOENIX_PROJECT_NAME", "proj-x")
        monkeypatch.setenv("PHOENIX_TRACES_SAMPLER_ARG", "0.5")

        config = PhoenixConfig.from_env()

        assert config.enabled is True
        assert config.endpoint == "http://phx.example:4317"
        assert config.project_name == "proj-x"
        assert config.sampling_ratio == 0.5

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("true", True), ("1", True), ("yes", True), ("false", False), ("0", False), ("no", False)],
    )
    def test_from_env_bool_three_states(self, monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool) -> None:
        """bool 三态解析（MetricsConfig 惯例：in ("true", "1", "yes")）。"""
        monkeypatch.setenv("PHOENIX_TRACING_ENABLED", raw)

        assert PhoenixConfig.from_env().enabled is expected

    def test_from_env_endpoint_fallback_to_otel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fallback 链：PHOENIX_OTLP_ENDPOINT 未设时取 OTEL_EXPORTER_OTLP_ENDPOINT。"""
        monkeypatch.delenv("PHOENIX_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-fallback:4317")

        assert PhoenixConfig.from_env().endpoint == "http://otel-fallback:4317"

    def test_from_env_endpoint_fallback_to_otel_traces_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fallback 链（R1-F8）：仅设信号级 OTEL_EXPORTER_OTLP_TRACES_ENDPOINT 时采用（OTel 规范信号级）。"""
        monkeypatch.delenv("PHOENIX_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otel-traces-only:4317")

        assert PhoenixConfig.from_env().endpoint == "http://otel-traces-only:4317"

    def test_from_env_traces_level_takes_precedence_over_generic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fallback 链优先级（R1-F8）：信号级 OTEL_EXPORTER_OTLP_TRACES_ENDPOINT > 通用级（OTel 规范）。"""
        monkeypatch.delenv("PHOENIX_OTLP_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otel-traces-first:4317")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-generic-second:4317")

        assert PhoenixConfig.from_env().endpoint == "http://otel-traces-first:4317"

    def test_from_env_phoenix_endpoint_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fallback 链优先级：PHOENIX_OTLP_ENDPOINT > OTEL_EXPORTER_OTLP_TRACES_ENDPOINT > 通用级。"""
        monkeypatch.setenv("PHOENIX_OTLP_ENDPOINT", "http://phx-first:4317")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otel-traces-second:4317")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-generic-third:4317")

        assert PhoenixConfig.from_env().endpoint == "http://phx-first:4317"

    def test_from_env_empty_string_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """空串视为未设：各级均空串回默认值（set-but-empty 不触发 101——compose 注入空串形态）。"""
        monkeypatch.setenv("PHOENIX_OTLP_ENDPOINT", "")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

        config = PhoenixConfig.from_env()

        assert config.endpoint == "http://localhost:4317"

    def test_from_env_empty_phoenix_falls_to_nonempty_otel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """空串视为未设：PHOENIX 空串 + OTEL 非空 → fallback 到 OTEL 值。"""
        monkeypatch.setenv("PHOENIX_OTLP_ENDPOINT", "")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-nonempty:4317")

        assert PhoenixConfig.from_env().endpoint == "http://otel-nonempty:4317"

    def test_from_env_invalid_sampling_ratio_raises_101(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """非法数值 101 包装（from_env 解析层——ValueError 禁裸抛，google_patents from None 先例）。"""
        monkeypatch.setenv("PHOENIX_TRACES_SAMPLER_ARG", "not-a-number")

        with pytest.raises(ConfigurationError) as excinfo:
            PhoenixConfig.from_env()

        assert excinfo.value.code == "EXCEPTION_101"
        assert "sampling_ratio" in excinfo.value.context


class TestPhoenixConfigGuards:
    """__post_init__ 101 守卫五场景（构造期统一守护——from_env 与直构造两路径）。"""

    @pytest.mark.parametrize(
        ("field", "overrides"),
        [
            ("enabled", {"enabled": "true"}),
            ("project_name", {"project_name": "   "}),
            ("endpoint", {"endpoint": "ftp://collector:4317"}),
            ("sampling_ratio", {"sampling_ratio": "high"}),
            ("sampling_ratio", {"sampling_ratio": 1.5}),
            ("sampling_ratio", {"sampling_ratio": 0.0}),
        ],
        ids=[
            "enabled-non-bool",
            "project-name-blank",
            "endpoint-bad-scheme",
            "sampling-non-numeric",
            "sampling-above-1",
            "sampling-zero",
        ],
    )
    def test_guard_raises_101_with_field_context(self, field: str, overrides: dict) -> None:
        """三段式：isinstance ConfigurationError → code 101 → context 携带字段名与实际值。"""
        base: dict = {
            "enabled": True,
            "endpoint": "http://localhost:4317",
            "project_name": "sisys-agent",
            "sampling_ratio": 1.0,
        }
        base.update(overrides)

        with pytest.raises(ConfigurationError) as excinfo:
            PhoenixConfig(**base)

        assert isinstance(excinfo.value, ConfigurationError)
        assert excinfo.value.code == "EXCEPTION_101"
        assert field in excinfo.value.context
        assert excinfo.value.context[field] == overrides[field]

    def test_guard_enabled_int_rejected(self) -> None:
        """bool 子类防呆：int 1 非 bool（isinstance 先行——bool 是 int 子类反向不成立）。"""
        from typing import Any, cast

        with pytest.raises(ConfigurationError) as excinfo:
            PhoenixConfig(enabled=cast(Any, 1))  # 故意传 int 验证运行时守卫（类型层经 cast 透传违规值）

        assert excinfo.value.code == "EXCEPTION_101"
        assert "enabled" in excinfo.value.context

    def test_guard_endpoint_requires_http_prefix(self) -> None:
        """endpoint 前缀守卫：https 合法 / 裸主机名拒。"""
        PhoenixConfig(endpoint="https://secure.example:4317")  # 合法自证
        with pytest.raises(ConfigurationError):
            PhoenixConfig(endpoint="collector:4317")

    def test_sampling_boundaries_legal(self) -> None:
        """零界合法性自证（守卫不误伤）：1.0 全采样与 0.5 均合法；0 等价禁用应走 enabled=false。"""
        assert PhoenixConfig(sampling_ratio=1.0).sampling_ratio == 1.0
        assert PhoenixConfig(sampling_ratio=0.5).sampling_ratio == 0.5

    def test_frozen_dataclass_immutable(self) -> None:
        """frozen 形态（本 Story 自设加严规格——先例 MetricsConfig 是普通 dataclass）。"""
        import dataclasses

        config = PhoenixConfig()

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(config, "enabled", True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
