"""SISYS_USE_TEST_PORTS 端口隔离权威性测试

背景（Story 5-4 代码审查 R1-F02 实测）：tests/conftest.py 模块级
`_disable_litellm_logging_worker()` 在 pytest 收集期 import litellm，
litellm import 期 load_dotenv() 将 .env 的 dev 端口（REDIS_PORT=6379/
POSTGRES_PORT=5432 等）注入 os.environ。若端口解析层无守卫，测试端口
6380/5433 会被 Layer 3 env 覆盖静默翻回 dev 端口——验收/集成测试实际
读写 dev 实例（污染 dev 数据 + P95 计时/隔离断言的有效性失真）。

双向锁定：
- config 侧——get_test_env() 解析结果保持 TEST_CONFIG 端口
- os.environ 侧——_sync_config_to_environ 强制覆写注入的 dev 端口
  （防生产代码 Config.from_env() 与测试端口解析分叉 split-brain）
"""

from __future__ import annotations

import os

import pytest

from tests.environments import get_test_env

# litellm load_dotenv 注入形态的 dev 端口污染集（.env 同款键值）
_DEV_PORT_POLLUTION = {
    "REDIS_PORT": "6379",
    "POSTGRES_PORT": "5432",
    "QDRANT_PORT": "6333",
    "QDRANT_GRPC_PORT": "6334",
    "RABBITMQ_PORT": "5672",
    "RABBITMQ_MGMT_PORT": "15672",
}

# TEST_CONFIG 对应的期望测试端口（config 侧与 os.environ 侧同值）
_EXPECTED_TEST_PORTS = {
    "REDIS_PORT": "6380",
    "POSTGRES_PORT": "5433",
    "QDRANT_PORT": "6335",
    "QDRANT_GRPC_PORT": "6336",
    "RABBITMQ_PORT": "5673",
    "RABBITMQ_MGMT_PORT": "15673",
}


def _inject_dev_port_pollution(monkeypatch: pytest.MonkeyPatch) -> None:
    """预注入 litellm 形态的 dev 端口污染（模拟第三方 import 副作用）"""
    for key, value in _DEV_PORT_POLLUTION.items():
        monkeypatch.setenv(key, value)


class TestTestPortsSwitchBlocksDevPortPollution:
    """测试端口开关生效时，dev 端口污染不得击穿隔离（双向断言）"""

    def test_config_side_keeps_test_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关生效+dev 端口已注入，When get_test_env，Then config 侧保持测试端口"""
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        _inject_dev_port_pollution(monkeypatch)

        config = get_test_env()

        assert config.redis.port == 6380
        assert config.postgres.port == 5433
        assert config.qdrant.port == 6335
        assert config.qdrant.grpc_port == 6336
        assert config.rabbitmq.port == 5673
        assert config.rabbitmq.mgmt_port == 15673

    def test_environ_side_overwrites_injected_dev_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关生效+dev 端口已注入，When get_test_env，Then os.environ 被强制覆写为测试端口

        生产代码 Config.from_env()（如 infrastructure/config/redis.py）读 os.getenv
        ——setdefault 对已注入的 dev 端口是 no-op，必须强覆写防 split-brain。
        """
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        _inject_dev_port_pollution(monkeypatch)

        get_test_env()

        for key, expected in _EXPECTED_TEST_PORTS.items():
            assert os.environ[key] == expected, f"{key} 应被强制覆写为测试端口 {expected}"

    def test_minio_endpoint_not_rebuilt_from_injected_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关生效+MINIO_HOST 注入，When get_test_env，Then endpoint 不被 host 分支内联重建

        endpoint 是 host:port 派生值——host 分支内联读 MINIO_API_PORT 重建 endpoint
        会绕过端口守卫（localhost:9010 → localhost:9000），须整体跳过。
        """
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        monkeypatch.setenv("MINIO_HOST", "localhost")
        monkeypatch.setenv("MINIO_API_PORT", "9000")

        config = get_test_env()

        assert config.minio.endpoint == "localhost:9010"
        assert os.environ["MINIO_ENDPOINT"] == "localhost:9010"


class TestDevModeKeepsExplicitPortOverride:
    """测试端口开关未启用时，显式端口 env 覆盖语义保持不变（防过度修复）"""

    def test_explicit_port_env_still_overrides_in_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关未设+显式 REDIS_PORT，When get_test_env，Then 尊重显式覆盖"""
        monkeypatch.delenv("SISYS_USE_TEST_PORTS", raising=False)
        monkeypatch.setenv("REDIS_PORT", "6399")

        config = get_test_env()

        assert config.redis.port == 6399, "dev 模式下显式端口 env 覆盖应保留（Layer 3 最高优先级语义）"
