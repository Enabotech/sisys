"""基础设施层嵌入模型配置单元测试

验证 EmbeddingConfig.from_env() 的环境变量读取、
URL 格式校验和超时参数校验行为
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.embedding import EmbeddingConfig


class TestEmbeddingConfigFromEnvUrlValidation:
    """from_env URL 格式校验"""

    def test_valid_url(self, monkeypatch) -> None:
        """有效 URL 应正确加载"""
        monkeypatch.setenv("EMBEDDING_API_URL", "http://localhost:8000")
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        config = EmbeddingConfig.from_env()
        assert config.api_url == "http://localhost:8000"

    def test_empty_url_default(self, monkeypatch) -> None:
        """空 URL 应使用默认空字符串"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        config = EmbeddingConfig.from_env()
        assert config.api_url == ""

    def test_url_trailing_slash_stripped(self, monkeypatch) -> None:
        """URL 尾部斜杠应自动去除"""
        monkeypatch.setenv("EMBEDDING_API_URL", "http://localhost:8000/")
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        config = EmbeddingConfig.from_env()
        assert config.api_url == "http://localhost:8000"

    def test_url_missing_scheme_raises(self, monkeypatch) -> None:
        """缺少 scheme 的 URL 应抛出 ConfigurationError"""
        monkeypatch.setenv("EMBEDDING_API_URL", "localhost:8000")
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        with pytest.raises(ConfigurationError, match="格式无效"):
            EmbeddingConfig.from_env()

    def test_url_missing_netloc_raises(self, monkeypatch) -> None:
        """缺少 netloc 的 URL 应抛出 ConfigurationError"""
        monkeypatch.setenv("EMBEDDING_API_URL", "http://")
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        with pytest.raises(ConfigurationError, match="格式无效"):
            EmbeddingConfig.from_env()

    def test_https_url_supported(self, monkeypatch) -> None:
        """应支持 HTTPS URL"""
        monkeypatch.setenv("EMBEDDING_API_URL", "https://api.example.com/embed")
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        config = EmbeddingConfig.from_env()
        assert config.api_url == "https://api.example.com/embed"


class TestEmbeddingConfigFromEnvTimeoutValidation:
    """from_env 超时参数校验"""

    def test_default_timeout(self, monkeypatch) -> None:
        """默认 timeout 应为 30.0"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        config = EmbeddingConfig.from_env()
        assert config.api_timeout == 30.0

    def test_valid_timeout(self, monkeypatch) -> None:
        """有效的 timeout 值应正确加载"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.setenv("EMBEDDING_API_TIMEOUT", "60.0")
        config = EmbeddingConfig.from_env()
        assert config.api_timeout == 60.0

    def test_integer_timeout(self, monkeypatch) -> None:
        """整数 timeout 应正确转换"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.setenv("EMBEDDING_API_TIMEOUT", "45")
        config = EmbeddingConfig.from_env()
        assert config.api_timeout == 45.0

    def test_non_numeric_timeout_raises(self, monkeypatch) -> None:
        """非数字 timeout 应抛出 ConfigurationError"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.setenv("EMBEDDING_API_TIMEOUT", "abc")
        with pytest.raises(ConfigurationError, match="值非法"):
            EmbeddingConfig.from_env()

    def test_zero_timeout_raises(self, monkeypatch) -> None:
        """零 timeout 应抛出 ConfigurationError"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.setenv("EMBEDDING_API_TIMEOUT", "0")
        with pytest.raises(ConfigurationError, match="正数"):
            EmbeddingConfig.from_env()

    def test_negative_timeout_raises(self, monkeypatch) -> None:
        """负 timeout 应抛出 ConfigurationError"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.setenv("EMBEDDING_API_TIMEOUT", "-10")
        with pytest.raises(ConfigurationError, match="正数"):
            EmbeddingConfig.from_env()


class TestEmbeddingConfigCombined:
    """from_env 组合参数验证"""

    def test_valid_url_and_timeout(self, monkeypatch) -> None:
        """有效 URL + 有效 timeout 应返回正确配置"""
        monkeypatch.setenv("EMBEDDING_API_URL", "http://localhost:8080")
        monkeypatch.setenv("EMBEDDING_API_TIMEOUT", "15.5")
        config = EmbeddingConfig.from_env()
        assert config.api_url == "http://localhost:8080"
        assert config.api_timeout == 15.5

    def test_returns_dataclass_instance(self, monkeypatch) -> None:
        """from_env 应返回 EmbeddingConfig 实例"""
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.delenv("EMBEDDING_API_TIMEOUT", raising=False)
        config = EmbeddingConfig.from_env()
        assert isinstance(config, EmbeddingConfig)
