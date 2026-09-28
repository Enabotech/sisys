"""数据源配置数值范围校验单元测试（Story 4.1b R2-2-B4/H2）

8 个数据源 config 的 from_env 范围校验（对齐 embedding.py 内联先例）：
- timeout / ttl_seconds 必须为正（7 个 HTTP 适配器 config）
- china_nbs：poll_interval_sec / poll_timeout_sec 必须为正 + interval < timeout 关系校验
  （interval <= 0 忙循环 hammer crawler 服务；interval >= timeout 首轮即超时）
- ipcc：max_bytes 必须为正（G7 已覆盖，此处参数化补齐 timeout/ttl）

非法配置启动期 fail-fast（ConfigurationError 101），优于运行期诡异故障。
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.china_nbs import ChinaNBSConfig
from src.infrastructure.config.eurostat import EurostatConfig
from src.infrastructure.config.imf import IMFConfig
from src.infrastructure.config.ipcc import IPCCConfig
from src.infrastructure.config.newsapi import NewsAPIConfig
from src.infrastructure.config.tavily import TavilyConfig
from src.infrastructure.config.uspto import USPTOConfig
from src.infrastructure.config.worldbank import WorldBankConfig

# (config 类, env 前缀)——均为 frozen dataclass + from_env classmethod（结构一致，参数化表用 Any 标注）
_HTTP_CONFIGS: list[tuple[Any, str]] = [
    (WorldBankConfig, "WORLDBANK"),
    (IMFConfig, "IMF"),
    (EurostatConfig, "EUROSTAT"),
    (USPTOConfig, "USPTO"),
    (NewsAPIConfig, "NEWSAPI"),
    (TavilyConfig, "TAVILY"),
    (IPCCConfig, "IPCC"),
]


class TestHttpConfigRangeValidation:
    @pytest.mark.parametrize(("config_cls", "prefix"), _HTTP_CONFIGS, ids=[p for _, p in _HTTP_CONFIGS])
    def test_zero_timeout_raises_101(self, config_cls: Any, prefix: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(f"{prefix}_TIMEOUT", "0")
        with pytest.raises(ConfigurationError) as exc_info:
            config_cls.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.parametrize(("config_cls", "prefix"), _HTTP_CONFIGS, ids=[p for _, p in _HTTP_CONFIGS])
    def test_negative_ttl_raises_101(self, config_cls: Any, prefix: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(f"{prefix}_TTL_SECONDS", "-5")
        with pytest.raises(ConfigurationError) as exc_info:
            config_cls.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.parametrize(("config_cls", "prefix"), _HTTP_CONFIGS, ids=[p for _, p in _HTTP_CONFIGS])
    def test_defaults_pass(self, config_cls: Any, prefix: str) -> None:
        """默认值路径不受范围校验影响（回归保护）。"""
        config = config_cls.from_env()
        assert config.timeout > 0
        assert config.ttl_seconds > 0


class TestChinaNBSConfigRangeValidation:
    def test_zero_poll_interval_raises_101(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """poll_interval <= 0 会忙循环 hammer crawler 服务，启动期拒绝。"""
        monkeypatch.setenv("CHINA_NBS_POLL_INTERVAL_SEC", "0")
        with pytest.raises(ConfigurationError) as exc_info:
            ChinaNBSConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    def test_interval_not_less_than_timeout_raises_101(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """interval >= timeout 首轮即超时（参数关系非法），消息含两个值。"""
        monkeypatch.setenv("CHINA_NBS_POLL_INTERVAL_SEC", "10")
        monkeypatch.setenv("CHINA_NBS_POLL_TIMEOUT_SEC", "5")
        with pytest.raises(ConfigurationError) as exc_info:
            ChinaNBSConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"
        assert "10" in exc_info.value.message and "5" in exc_info.value.message

    def test_defaults_pass(self) -> None:
        config = ChinaNBSConfig.from_env()
        assert 0 < config.poll_interval_sec < config.poll_timeout_sec
