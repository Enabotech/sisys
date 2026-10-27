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
from collections.abc import Generator

import pytest

from tests.environments import get_test_env


def _restore_environ_snapshot(snapshot: dict[str, str]) -> None:
    """按快照恢复 os.environ（删除新增键 + 还原改动键——对任意写入分支免疫）。

    恢复逻辑单一真源：文件级 autouse fixture 的 teardown 与残留锁用例的
    用例内手动恢复共享本函数（R9-F01 提取——用例内验证恢复行为无需等待
    teardown，且两处形态永不漂移）。
    """
    for key in list(os.environ):
        if key not in snapshot:
            del os.environ[key]
    for key, value in snapshot.items():
        if os.environ.get(key) != value:
            os.environ[key] = value


@pytest.fixture(autouse=True)
def _environ_snapshot_restore() -> Generator[None, None, None]:
    """os.environ 全量快照恢复（文件级 autouse——对任意写入分支免疫）。

    get_test_env() 的 _sync_config_to_environ 会向 os.environ 写入 host/端口
    类键，写入面随解析分支不同（CI 分支 setdefault 写 host.docker.internal
    全套 HOST 键与 CI 端口；test-ports 分支强覆写 11 键）——monkeypatch 只恢复
    它自己 setenv 的键，CI 形态用例（R2-F01）的 sync 写入面全部残留
    （QDRANT_HOST/NEO4J_HOST=host.docker.internal 等），同 worker 后续测试经
    Layer 3 覆盖或生产 Config.from_env 直读被打到不存在的 host（R6-F01 实测
    复现：全量跑 10 failed 的 Qdrant DNS/Neo4j resolve 失败族）。快照 diff
    恢复对任意分支写入免疫——删除新增键 + 还原改动键。
    """
    snapshot = dict(os.environ)
    yield
    _restore_environ_snapshot(snapshot)


# litellm load_dotenv 注入形态的 dev 端口污染集（.env 同款键值）。
# 注入集 = _sync_config_to_environ 测试端口模式强覆写写集全量（11 键）——
# monkeypatch teardown 恢复全部被覆写键，防进程内单向污染（R3-F01：写集 ⊋
# 恢复集时后续 ambient 解析被静默漂到测试端口、NEO4J 两键 config/environ 分裂）
_DEV_PORT_POLLUTION = {
    "REDIS_PORT": "6379",
    "POSTGRES_PORT": "5432",
    "QDRANT_PORT": "6333",
    "QDRANT_GRPC_PORT": "6334",
    "RABBITMQ_PORT": "5672",
    "RABBITMQ_MGMT_PORT": "15672",
    "NEO4J_HTTP_PORT": "7474",
    "NEO4J_BOLT_PORT": "7687",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_HOST": "localhost",
    "MINIO_API_PORT": "9000",
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


def _anchor_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式锚定 LOCAL 环境形态（SISYS_TEST_ENV 最高优先级直读）。

    必须 setenv "local" 而非 delenv：resolve_env() 有多层兜底（GITHUB_ACTIONS
    等 CI 变量 / /.dockerenv 容器检测）——CI 容器（gitea act_runner + job
    container）下 delenv 后仍会判 CI，本组 LOCAL 语义断言必红（R2-F01 评审
    实证）。显式锚定对 ambient runner 变量完全免疫。
    """
    monkeypatch.setenv("SISYS_TEST_ENV", "local")


def _inject_dev_port_pollution(monkeypatch: pytest.MonkeyPatch) -> None:
    """预注入 litellm 形态的 dev 端口污染（模拟第三方 import 副作用）"""
    for key, value in _DEV_PORT_POLLUTION.items():
        monkeypatch.setenv(key, value)


class TestTestPortsSwitchBlocksDevPortPollution:
    """测试端口开关生效时，dev 端口污染不得击穿隔离（双向断言）"""

    def test_config_side_keeps_test_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关生效+dev 端口已注入，When get_test_env，Then config 侧保持测试端口"""
        _anchor_local_env(monkeypatch)
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
        _anchor_local_env(monkeypatch)
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        _inject_dev_port_pollution(monkeypatch)

        get_test_env()

        for key, expected in _EXPECTED_TEST_PORTS.items():
            assert os.environ[key] == expected, f"{key} 应被强制覆写为测试端口 {expected}"

    def test_minio_endpoint_not_rebuilt_from_injected_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关生效+MINIO_HOST/API_PORT 注入，When get_test_env，Then endpoint 不被重建且生产读取键被覆写

        endpoint 是 host:port 派生值——host 分支内联读 MINIO_API_PORT 重建 endpoint
        会绕过端口守卫（localhost:9010 → localhost:9000），须整体跳过；生产
        MinIOConfig.from_env 读 MINIO_HOST+MINIO_API_PORT（非 endpoint）——
        sync 侧两键须强覆写防 MinIO 腿 split-brain（R2-F02）。
        """
        _anchor_local_env(monkeypatch)
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        monkeypatch.setenv("MINIO_HOST", "localhost")
        monkeypatch.setenv("MINIO_API_PORT", "9000")

        config = get_test_env()

        assert config.minio.endpoint == "localhost:9010"
        assert os.environ["MINIO_ENDPOINT"] == "localhost:9010"
        assert os.environ["MINIO_HOST"] == "localhost", "生产读取键 HOST 须强覆写（防 split-brain）"
        assert os.environ["MINIO_API_PORT"] == "9010", "生产读取键 API_PORT 须强覆写（防 split-brain）"


class TestDevModeKeepsExplicitPortOverride:
    """测试端口开关未启用时，显式端口 env 覆盖语义保持不变（防过度修复）"""

    def test_explicit_port_env_still_overrides_in_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 开关未设+显式 REDIS_PORT，When get_test_env，Then 尊重显式覆盖"""
        _anchor_local_env(monkeypatch)
        monkeypatch.delenv("SISYS_USE_TEST_PORTS", raising=False)
        monkeypatch.setenv("REDIS_PORT", "6399")

        config = get_test_env()

        assert config.redis.port == 6399, "dev 模式下显式端口 env 覆盖应保留（Layer 3 最高优先级语义）"


class TestCiEnvKeepsPortOverrideSemantics:
    """CI 环境形态下端口门控不触发（反向锁定——防门控误扩打破 CI 现行为）"""

    def test_ci_env_port_override_not_gated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given SISYS_TEST_ENV=ci+开关 on+显式端口，When get_test_env，Then 走 CI_CONFIG 且端口覆盖保留

        CI 形态（cr.yaml L90-91 同款 env 组合）下 TEST_CONFIG 永不被选中——
        端口 env 覆盖语义须与修复前完全一致。注入值用 6390 差异化（与
        CI_CONFIG 预设 6379 不同值）——若门控被误扩到 CI（config.env==LOCAL
        条件被删），端口覆盖被跳过回落 6379，本用例红（判别力锚）。
        """
        monkeypatch.setenv("SISYS_TEST_ENV", "ci")
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "true")
        monkeypatch.setenv("REDIS_PORT", "6390")
        monkeypatch.setenv("REDIS_HOST", "host.docker.internal")  # 预置 host 防 _set_host_env 直写泄漏

        config = get_test_env()

        assert config.env.value == "ci"
        assert config.redis.host == "host.docker.internal", "CI_CONFIG 预设 host 选择锁定"
        assert config.redis.port == 6390, "CI 形态下端口 env 覆盖应保留（门控不得误扩到 CI）"

    def test_ci_sync_writes_restored_and_local_parse_not_breaking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CI 形态解析的 sync 写入面被快照恢复回收，后续 local 形态解析不被击穿。

        回归锁（R6-F01；R9-F01 重构为单用例自含——原「跨用例检查上一用例
        残留」形态在 xdist loadgroup 下同文件用例可跨 worker 乱序，文件内
        定义序不构成执行序保证）：CI 分支的 _sync_config_to_environ
        setdefault 写入面（QDRANT_HOST/NEO4J_HOST 等 host.docker.internal
        全套）若不被快照恢复回收，后续 get_test_env 的 Layer 3 会以残留值
        覆盖 TEST_CONFIG 的 localhost、生产 from_env 直读同中招——全量跑
        Qdrant DNS/Neo4j resolve 失败族的根因形态。

        环境无关化（R9-F01，取代 R8-F01 的 skip 逃避）：CI 进程自带 host 键
        （get_test_env 首次 CI 解析的 setdefault 进程级残留——CI_CONFIG 指向
        宿主网络的合法基线）使「值 != host.docker.internal」**绝对形态**断言
        在 CI 恒红。污染的正确定义是**相对基线的增量变化**而非绝对值——
        单用例内三段断言在本地/CI 同一路径真实执行：

        ① 驱动 + 恢复：CI 形态解析（含恢复活性探针**直接写**——非 monkeypatch
          面，快照恢复是其唯一回收通道）后，手动调用与 autouse fixture 同源
          的 ``_restore_environ_snapshot``（teardown 行为的单一真源）；
        ② 恢复有效性双锚：探针键被删除（R6-F01 修复行为「删除新增键」的
          直接锁）+ os.environ 相对驱动前快照零净漂移（判增量不判绝对值
          ——CI 进程残留 host 键是合法基线，不在断言面）；
        ③ 净环境 local 形态解析：host 类键清空（delenv 屏蔽本地/CI 基线
          差异——含 CI 进程残留）后，local+test-ports 解析的 host 恒
          localhost（残留击穿面的端到端锚）。
        """
        from tests.environments import reset_test_env

        snapshot = dict(os.environ)
        # 驱动：恢复活性探针（直接写——唯一回收通道是被测的快照恢复）+ CI 形态解析
        os.environ["SISYS_ENV_RESTORE_PROBE"] = "ci-case-probe"
        monkeypatch.setenv("SISYS_TEST_ENV", "ci")
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "true")
        config = get_test_env()
        assert config.env.value == "ci", "驱动有效性自证（CI 形态解析已发生）"

        # 恢复（与 autouse fixture teardown 同源——被测行为本体）
        _restore_environ_snapshot(snapshot)

        # ② 恢复有效性双锚
        assert "SISYS_ENV_RESTORE_PROBE" not in os.environ, (
            "恢复活性探针残留——快照恢复未删除新增键（R6-F01 回归：CI 分支 sync setdefault 写入面将同样残留，毒害后续测试）"
        )
        drifted = {
            key: (snapshot.get(key), os.environ.get(key))
            for key in set(snapshot) | set(os.environ)
            if snapshot.get(key) != os.environ.get(key)
        }
        assert not drifted, f"CI 形态解析的写入面未恢复（相对驱动前快照净漂移）: {drifted}"

        # ③ 净环境 local 形态解析（delenv 屏蔽两环境基线差异——teardown 自动恢复）
        reset_test_env()  # 清单例——第二次解析不受 CI 形态单例遮蔽
        for key in (
            "REDIS_HOST",
            "POSTGRES_HOST",
            "QDRANT_HOST",
            "NEO4J_HOST",
            "RABBITMQ_HOST",
            "MINIO_HOST",
            "MINIO_ENDPOINT",
        ):
            monkeypatch.delenv(key, raising=False)
        _anchor_local_env(monkeypatch)
        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")

        config = get_test_env()
        assert config.qdrant.host == "localhost", "TEST_CONFIG 的 qdrant.host 不得被残留 env 覆盖"
        assert config.neo4j.host == "localhost", "TEST_CONFIG 的 neo4j.host 不得被残留 env 覆盖"
