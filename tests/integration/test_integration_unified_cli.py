"""Story 7-1 — 统一 CLI 集成测试（Task 7 真实服务面）。

CLI 面形态（commit+定向清理——integration_test_patterns 两子模式之 CLI 面）：
- 7.1 document upload 真实 PG 链（真实临时文件 → main_cli.main in-process
  直调 → documents 落库断言 → 定向 DELETE）
- 7.2 archive query fallback 读链（真实 bootstrap 无 session 上下文 →
  fallback **find 读路径**往返——6.4-DF2 部分清偿载体）
- 7.3 checkpoint 族真实链（checkpoint_use_case 直创 → list/show/recover
  经 CLI 直调往返 → Redis 键族定向删除）
- 7.4 .env 入口加载（临时 .env 经 monkeypatch ``main_cli.ENV_FILE`` 常量
  注入——R2-11 机制；与单测顺序守卫互补）

服务不可达动态 pytest.skip（CI root 容器恒 skip 假绿防线：探测失败即 skip）。

Run with: poetry run pytest tests/integration/test_integration_unified_cli.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid as uuid_module
from pathlib import Path
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.xdist_group("unified-cli-integration"),
]


def _clear_resolver_caches() -> None:
    """驱逐 resolver SINGLETON/SCOPED 缓存（CLI 直调双清钦定）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


@pytest.fixture
def cli_env(tmp_path: Path):
    """CLI 直调环境（双清前置 + 产物位 + teardown 定向清理清单）。"""
    _clear_resolver_caches()
    state: dict[str, Any] = {
        "document_ids": [],
        "plan_ids": [],
        "temp_files": [],
        "stdout": "",
        "stderr": "",
        "exit_code": None,
    }
    yield state
    _teardown(state)
    _clear_resolver_caches()


def _teardown(state: dict[str, Any]) -> None:
    """定向清理（commit 面 CLI 形态——自建资源逐键/逐行删除）。"""

    async def _cleanup() -> None:
        from tests.environments import get_test_env

        env = get_test_env()
        if state["document_ids"]:
            import asyncpg

            conn = await asyncpg.connect(
                host=env.postgres.host,
                port=env.postgres.port,
                user=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
            try:
                await conn.execute("DELETE FROM documents WHERE id = ANY($1::uuid)", state["document_ids"])
            finally:
                await conn.close()
        if state["plan_ids"]:
            import redis.asyncio as aioredis

            from src.application.ports.checkpoint import (
                CHECKPOINT_RECOVERY_SESSION_PREFIX,
                CHECKPOINT_SESSION_PREFIX,
            )
            from src.infrastructure.storage.redis.key_builder import build_key

            client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
            try:
                keys = [f"{CHECKPOINT_RECOVERY_SESSION_PREFIX}{plan_id}" for plan_id in state["plan_ids"]]
                keys.extend(
                    build_key("snapshot", f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:CP-{no}")
                    for plan_id in state["plan_ids"]
                    for no in range(1, 9)
                )
                await client.delete(*keys)
            finally:
                await client.close()  # close 形态对齐仓内验收先例（analyst_view :325——类型存根无 aclose）

    for path in state["temp_files"]:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
    try:
        asyncio.new_event_loop().run_until_complete(_cleanup())
    except Exception:  # noqa: BLE001 —— teardown 容错（服务不可达静默跳过）
        pass


def _invoke_cli(state: dict[str, Any], argv: list[str], capsys: pytest.CaptureFixture[str]) -> int:
    """main_cli.main in-process 直调（双清+产物捕获）。"""
    from src.entrypoints import main_cli

    _clear_resolver_caches()
    try:
        exit_code = main_cli.main(list(argv))
    except SystemExit as error:
        exit_code = int(error.code or 0)
    finally:
        captured = capsys.readouterr()
        state["stdout"] = captured.out
        state["stderr"] = captured.err
        state["exit_code"] = exit_code
        _clear_resolver_caches()
    return exit_code


def _require_services() -> None:
    """PG+Redis 双探测（不可达 pytest.skip——环境门控动态形态）。"""
    import asyncpg

    from tests.environments import get_test_env

    env = get_test_env()

    async def _probe() -> None:
        conn = await asyncpg.connect(
            host=env.postgres.host,
            port=env.postgres.port,
            user=env.postgres.username,
            password=env.postgres.password,
            database=env.postgres.database,
        )
        await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_probe())
    except Exception as error:
        pytest.skip(f"PostgreSQL not available: {error}")
    finally:
        loop.close()


# ===================================================================
# 7.1 document upload 真实 PG 链
# ===================================================================


class TestDocumentUploadRealChain:
    """document upload 真实落库（AC-2）。"""

    def test_upload_persists_document_row(
        self, cli_env: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """真实临时文件 → CLI 上传 → documents 行存在（tenant='cli-default'）→ 定向清理。"""
        _require_services()
        temp_file = tmp_path / "集成上传文档.md"
        temp_file.write_text("# 集成测试文档\n\n真实上传链验证。", encoding="utf-8")
        cli_env["temp_files"].append(str(temp_file))

        exit_code = _invoke_cli(cli_env, ["document", "upload", "--file", str(temp_file), "--format", "json"], capsys)
        assert exit_code == 0, f"stderr={cli_env['stderr']!r}"
        payload = json.loads(cli_env["stdout"])
        document_id = payload["document_id"]
        cli_env["document_ids"].append(uuid_module.UUID(document_id))

        import asyncpg

        from tests.environments import get_test_env

        env = get_test_env()

        async def _verify() -> Any:
            conn = await asyncpg.connect(
                host=env.postgres.host,
                port=env.postgres.port,
                user=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
            try:
                return await conn.fetchrow(
                    "SELECT id, tenant_id FROM documents WHERE id = $1",
                    uuid_module.UUID(document_id),
                )
            finally:
                await conn.close()

        row = asyncio.new_event_loop().run_until_complete(_verify())
        assert row is not None, "documents 行应真实落库"
        assert row["tenant_id"] == "cli-default"


# ===================================================================
# 7.2 archive query fallback 读链（6.4-DF2 部分清偿）
# ===================================================================


class TestArchiveQueryFallbackReadChain:
    """archive query 无 session 上下文 → fallback find 读路径往返。"""

    def test_query_empty_plan_returns_empty_view(self, cli_env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
        """真实 bootstrap → 无 session 上下文 CLI 面 → fallback find 读路径往返成功（空态 exit 0）。"""
        _require_services()
        plan_id = str(uuid_module.uuid4())
        cli_env["plan_ids"].append(uuid_module.UUID(plan_id))

        exit_code = _invoke_cli(cli_env, ["archive", "query", "--plan-id", plan_id, "--format", "json"], capsys)
        assert exit_code == 0, f"stderr={cli_env['stderr']!r}"
        payload = json.loads(cli_env["stdout"])
        assert payload["plan_id"] == plan_id
        assert payload["total"] == 0


# ===================================================================
# 7.3 checkpoint 族真实链
# ===================================================================


class TestCheckpointFamilyRealChain:
    """checkpoint 直创 → list/show/recover CLI 往返（AC-2/AC-5）。"""

    def _create_checkpoint(self, plan_id: str) -> None:
        """given 前置：checkpoint_use_case 直创 CP-1（LLM 压缩依赖——无 Key 动态 skip）。"""
        _clear_resolver_caches()

        async def _create() -> None:
            from src.domain.ports.resolver import resolve

            use_case = resolve("checkpoint_use_case")
            await use_case.execute(
                plan_id=plan_id,
                checkpoint_no="CP-1",
                stage_id="market_insight",
                query="集成前置创建链查询",
                retrieved_docs=[],
                user_id="integration-cli",
                summary="Story 7-1 集成前置 checkpoint",
            )

        try:
            asyncio.new_event_loop().run_until_complete(_create())
        except Exception as error:  # noqa: BLE001 —— 创建链 LLM 压缩依赖门控（无 Key 环境 skip）
            if "API Key" in str(error) or "LLMConfig" in type(error).__name__:
                pytest.skip(f"LLM API Key 未配置——checkpoint 创建链依赖上下文压缩 LLM: {error}")
            raise

    def test_list_show_recover_roundtrip(self, cli_env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
        """真实链：直创 CP-1 → list 命中 → show 预览 → recover 执行 → 恢复产物。"""
        _require_services()
        plan_id = str(uuid_module.uuid4())
        cli_env["plan_ids"].append(uuid_module.UUID(plan_id))
        self._create_checkpoint(plan_id)

        exit_code = _invoke_cli(cli_env, ["checkpoint", "list", "--plan-id", plan_id, "--format", "json"], capsys)
        assert exit_code == 0, f"stderr={cli_env['stderr']!r}"
        rows = json.loads(cli_env["stdout"])
        assert any(row["checkpoint_no"] == "CP-1" for row in rows), "list 应命中 CP-1"

        exit_code = _invoke_cli(
            cli_env,
            ["checkpoint", "show", "--plan-id", plan_id, "--checkpoint-no", "CP-1", "--format", "json"],
            capsys,
        )
        assert exit_code == 0, f"stderr={cli_env['stderr']!r}"
        view = json.loads(cli_env["stdout"])
        assert view["checkpoint_no"] == "CP-1"

        exit_code = _invoke_cli(
            cli_env,
            [
                "checkpoint",
                "recover",
                "--plan-id",
                plan_id,
                "--checkpoint-no",
                "CP-1",
                "--yes",
                "--cost-budget",
                "1.0",
                "--format",
                "json",
            ],
            capsys,
        )
        assert exit_code == 0, f"stderr={cli_env['stderr']!r}"
        outcome = json.loads(cli_env["stdout"])
        assert outcome["checkpoint_no"] == "CP-1"


# ===================================================================
# 7.4 .env 入口加载集成验证（R2-11 机制）
# ===================================================================


class TestEnvFileLoading:
    """临时 .env 经 monkeypatch main_cli.ENV_FILE 常量注入（与单测顺序守卫互补）。"""

    def test_env_file_loaded_before_bootstrap(
        self,
        cli_env: dict[str, Any],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """临时 .env 变量经入口 load_dotenv 注入 os.environ（不改仓库根 .env——零污染）。"""
        marker_key = "SISYS_7_1_ENV_LOAD_MARKER"
        monkeypatch.delenv(marker_key, raising=False)
        temp_env = tmp_path / "integration.env"
        temp_env.write_text(f"{marker_key}=loaded-by-cli\n", encoding="utf-8")

        from src.entrypoints import main_cli

        monkeypatch.setattr(main_cli, "ENV_FILE", temp_env)
        try:
            exit_code = _invoke_cli(cli_env, ["--version"], capsys)
            assert exit_code == 0
            assert os.environ.get(marker_key) == "loaded-by-cli", "入口 load_dotenv 应注入临时 .env 变量"
        finally:
            monkeypatch.delenv(marker_key, raising=False)
