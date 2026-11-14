"""归档 CLI 命令单元测试（Task 3 循环 C——archive query）。

消费端口：``strategic_archive_service.query_archive(ArchiveQuery)``（CQRS
读模型面——Query Object 值对象 domain/ports/archive_repository.py 定义）。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.entrypoints import cli_main
from src.interfaces.cli.commands import archive_commands


class _StubArchive:
    """归档实体替身。"""

    def __init__(self, archive_id: str, plan_id: str) -> None:
        from src.domain.entities.strategic_archive import ArchiveType

        self.archive_id = archive_id
        self.plan_id = plan_id
        self.archive_type = ArchiveType.ASSUMPTION  # 真实枚举（R3——纯 str 替身掩蔽枚举泄漏形态）
        self.created_at = "2026-11-13T00:00:00"


class _StubArchiveService:
    """归档服务替身（捕获 ArchiveQuery 调用形态）。"""

    def __init__(self) -> None:
        self.queries: list[Any] = []

    async def query_archive(self, query: Any) -> list[_StubArchive]:
        self.queries.append(query)
        return [_StubArchive("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", str(query.plan_id) if query.plan_id else "p-1")]


def _patch_service(monkeypatch: pytest.MonkeyPatch) -> _StubArchiveService:
    """注入归档服务替身。"""
    stub = _StubArchiveService()

    class _FakeResolver:
        def resolve(self, name: str) -> object:
            assert name == "strategic_archive_service", f"端口名漂移: {name}"
            return stub

    monkeypatch.setattr(archive_commands, "get_resolver", lambda: _FakeResolver())
    return stub


class TestArchiveQueryCommand:
    """archive query 命令（ArchiveQuery Query Object 调用形态）。"""

    def test_query_kernel_cleanup_called(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """query 异步内核 finally 关池 spy（R3 补锁——R1-F8 原零断言）。"""
        import uuid as uuid_module

        _patch_service(monkeypatch)
        cleanup_calls: list[str] = []

        async def _spy_cleanup() -> None:
            cleanup_calls.append("cleanup")

        monkeypatch.setattr(archive_commands, "run_cleanup_async", _spy_cleanup)
        exit_code = cli_main.main(
            ["archive", "query", "--plan-id", str(uuid_module.uuid4()), "--tenant-id", str(uuid_module.uuid4())]
        )
        capsys.readouterr()
        assert exit_code == 0
        assert cleanup_calls == ["cleanup"], f"内核 finally 应恰一次关池: {cleanup_calls}"

    def test_query_calls_with_archive_query(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """query 经 ArchiveQuery 调用（plan_id/limit 映射）。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        plan_id = str(uuid_module.uuid4())
        exit_code = cli_main.main(["archive", "query", "--plan-id", plan_id, "--tenant-id", "t-arch", "--limit", "5"])
        assert exit_code == 0, capsys.readouterr()
        query = stub.queries[0]
        assert str(query.plan_id) == plan_id
        assert query.limit == 5

    def test_query_tenant_missing_fail_loud(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """租户缺失 → 242 stderr（租户消费型命令 fail-loud）。"""
        _patch_service(monkeypatch)
        monkeypatch.delenv("SISYS_TENANT_ID", raising=False)
        exit_code = cli_main.main(["archive", "query"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err

    def test_query_plan_id_invalid_uuid_242(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """非法 plan-id → 242 stderr（canonical 归一同构）。"""
        _patch_service(monkeypatch)
        exit_code = cli_main.main(["archive", "query", "--plan-id", "bad", "--tenant-id", "t"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err

    def test_query_json_envelope(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--format json：archives 白名单 set 相等 + 枚举 .value 值断言（R3 升级）。"""
        import uuid as uuid_module

        _patch_service(monkeypatch)
        exit_code = cli_main.main(
            ["archive", "query", "--plan-id", str(uuid_module.uuid4()), "--tenant-id", "t", "--format", "json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        envelope = json.loads(captured.out)
        assert envelope["command"] == "sisys archive query"
        first = envelope["data"]["archives"][0]
        assert set(first) == {"archive_id", "plan_id", "archive_type", "created_at"}, f"白名单漂移: {sorted(first)}"
        assert first["archive_type"] == "assumption", f"ArchiveType 枚举值泄漏类名前缀: {first['archive_type']!r}"

    def test_query_dry_run_zero_service(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run：读命令退化态（零 service）。"""
        stub = _patch_service(monkeypatch)
        exit_code = cli_main.main(["archive", "query", "--tenant-id", "t", "--dry-run"])
        capsys.readouterr()
        assert exit_code == 0
        assert not stub.queries
