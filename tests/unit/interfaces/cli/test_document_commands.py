"""文档 CLI 命令单元测试（Story 7-1 Typer 化——upload/search/version 保形重构）。

测试 document_commands 的 Typer 命令契约（经统一入口 main 行为面直调）：
    - 租户双通道 fail-loud（--tenant-id + SISYS_TENANT_ID env 回退——242）
    - upload 文件存在性守卫先于 bootstrap（242）
    - search 端口调用形态（hybrid_search_service.search）
    - version snapshot/list 存量保形（错误处理定式对齐 [EXCEPTION_code] stderr）

既有测试适配（OD-10 行为修复背书——义务非回归）：--tenant 改名 --tenant-id
双通道无 default 兜底；错误输出 stdout→stderr 定式；patch 点随函数形态漂移。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.entrypoints import cli_main
from src.interfaces.cli.commands import document_commands


class _StubUploadService:
    """上传服务替身（单测 mock 合法——捕获调用参数）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def upload(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return type("D", (), {"document_id": "11111111-1111-1111-1111-111111111111", "filename": kwargs.get("filename", "")})()


class _StubSearchService:
    """检索服务替身（捕获 collection/query/tenant 调用形态）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def search(self, **kwargs: Any) -> list[object]:
        self.calls.append(kwargs)
        return [type("R", (), {"document_id": "d-1", "score": 0.9, "text": "战略"})()]


class _StubVersionService:
    """版本服务替身（snapshot/list 双方法）。"""

    def __init__(self) -> None:
        self.snapshot_calls: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []

    async def create_snapshot(self, **kwargs: Any) -> object:
        self.snapshot_calls.append(kwargs)
        return type(
            "S",
            (),
            {
                "snapshot_id": "s-1",
                "document_id": kwargs.get("document_id"),
                "version": 1,
                "created_by": kwargs.get("created_by", ""),
            },
        )()

    async def list_versions(self, **kwargs: Any) -> list[object]:
        self.list_calls.append(kwargs)
        return [type("V", (), {"version": 1, "created_by": "cli7", "diff_summary": "初始", "created_at": None})()]


def _patch_services(monkeypatch: pytest.MonkeyPatch) -> tuple[_StubUploadService, _StubSearchService, _StubVersionService]:
    """三服务替身注入（document_commands 模块级 get_resolver patch 点）。"""
    upload = _StubUploadService()
    search = _StubSearchService()
    version = _StubVersionService()
    services = {
        "document_upload_service": upload,
        "hybrid_search_service": search,
        "document_version_service": version,
    }

    class _FakeResolver:
        def resolve(self, name: str) -> object:
            return services[name]

    monkeypatch.setattr(document_commands, "get_resolver", lambda: _FakeResolver())
    return upload, search, version


class TestTenantGuard:
    """租户双通道 fail-loud（Task 0.1 租户参数栏钦定）。"""

    def test_tenant_flag_channel(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--tenant-id 旗标通道（合法 UUID 值传入 service）。"""
        _patch_services(monkeypatch)
        monkeypatch.delenv("SISYS_TENANT_ID", raising=False)
        upload_file = tmp_path / "doc.md"
        upload_file.write_text("内容", encoding="utf-8")
        tenant = "22222222-2222-2222-2222-222222222222"

        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                str(upload_file),
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--tenant-id",
                tenant,
                "--uploaded-by",
                "cli7",
            ]
        )
        assert exit_code == 0, capsys.readouterr()

    def test_tenant_env_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """SISYS_TENANT_ID env 回退通道（旗标缺省时 env 生效）。"""
        upload, _, _ = _patch_services(monkeypatch)
        upload_file = tmp_path / "doc.md"
        upload_file.write_text("内容", encoding="utf-8")
        tenant = "33333333-3333-3333-3333-333333333333"
        monkeypatch.setenv("SISYS_TENANT_ID", tenant)

        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                str(upload_file),
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--uploaded-by",
                "cli7",
            ]
        )
        assert exit_code == 0, capsys.readouterr()
        assert upload.calls[0]["tenant_id"] == tenant

    def test_tenant_missing_fail_loud(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """双通道皆缺 → 242 fail-loud（守卫先于 bootstrap——无 default 兜底）。"""
        _patch_services(monkeypatch)
        monkeypatch.delenv("SISYS_TENANT_ID", raising=False)
        upload_file = tmp_path / "doc.md"
        upload_file.write_text("内容", encoding="utf-8")

        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                str(upload_file),
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--uploaded-by",
                "cli7",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err, f"租户缺失应 242 stderr: {captured.err!r}"


class TestUploadCommand:
    """upload 参数契约与守卫（文件存在性 242 先于 bootstrap）。"""

    def test_file_not_exists_guard(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """文件不存在 → 242 stderr + exit 1（守卫先于一切 IO）。"""
        _patch_services(monkeypatch)
        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                "/nonexistent/x.md",
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--tenant-id",
                "t",
                "--uploaded-by",
                "cli7",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err

    def test_upload_dry_run_zero_service_calls(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--dry-run：动作清单+零 service 调用（client 语义）。"""
        upload, _, _ = _patch_services(monkeypatch)
        upload_file = tmp_path / "doc.md"
        upload_file.write_text("内容", encoding="utf-8")

        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                str(upload_file),
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--tenant-id",
                "44444444-4444-4444-4444-444444444444",
                "--uploaded-by",
                "cli7",
                "--dry-run",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "将上传" in captured.out
        assert not upload.calls, "dry-run 零 service 调用失败"

    def test_upload_json_envelope_whitelist(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--format json：data 白名单（document_id/filename/tenant_id/document_type/status）。"""
        _patch_services(monkeypatch)
        monkeypatch.delenv("SISYS_TENANT_ID", raising=False)
        upload_file = tmp_path / "战略.md"
        upload_file.write_text("战略内容", encoding="utf-8")

        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                str(upload_file),
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--tenant-id",
                "55555555-5555-5555-5555-555555555555",
                "--uploaded-by",
                "cli7",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        envelope = json.loads(captured.out)
        assert envelope["command"] == "sisys document upload"
        assert envelope["data"]["document_id"] == "11111111-1111-1111-1111-111111111111"
        # R3 升级：set 相等锁白名单（原 membership 断言对加键钝感）+ status 值锁
        assert set(envelope["data"]) == {"document_id", "filename", "tenant_id", "document_type", "status"}, (
            f"upload 白名单漂移: {sorted(envelope['data'])}"
        )
        assert envelope["data"]["status"] == "uploaded"


class TestSearchCommand:
    """search 端口调用形态（hybrid_search_service.search 全参）。"""

    def test_search_calls_service_full_params(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """全参调用（collection/query_text/tenant_id 直传 service）。"""
        _, search, _ = _patch_services(monkeypatch)
        exit_code = cli_main.main(
            [
                "document",
                "search",
                "--query",
                "战略",
                "--collection",
                "docs_c1",
                "--tenant-id",
                "66666666-6666-6666-6666-666666666666",
            ]
        )
        assert exit_code == 0, capsys.readouterr()
        assert search.calls[0]["collection"] == "docs_c1"
        assert search.calls[0]["query_text"] == "战略"
        assert search.calls[0]["tenant_id"] == "66666666-6666-6666-6666-666666666666"

    def test_search_dry_run_degenerate(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """读命令 dry-run 退化态：守卫+动作回显（零 service）。"""
        _, search, _ = _patch_services(monkeypatch)
        exit_code = cli_main.main(["document", "search", "--query", "战略", "--tenant-id", "t1", "--dry-run"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "将" in captured.out
        assert not search.calls

    def test_search_kernel_cleanup_called(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """search 异步内核 finally 关池 spy（R3 补锁——R1-F8 原零断言）。"""
        import uuid as uuid_module

        _patch_services(monkeypatch)
        cleanup_calls: list[str] = []

        async def _spy_cleanup() -> None:
            cleanup_calls.append("cleanup")

        monkeypatch.setattr(document_commands, "run_cleanup_async", _spy_cleanup)
        exit_code = cli_main.main(["document", "search", "--query", "战略", "--tenant-id", str(uuid_module.uuid4())])
        capsys.readouterr()
        assert exit_code == 0
        assert cleanup_calls == ["cleanup"], f"内核 finally 应恰一次关池: {cleanup_calls}"


class TestVersionListCommand:
    """version list 存量接线（--tenant-id 改名+定式对齐）。"""

    def test_version_list_calls_service(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """list 经统一入口调用 document_version_service.list_versions。"""
        _, _, version = _patch_services(monkeypatch)
        doc_id = "77777777-7777-7777-7777-777777777777"
        exit_code = cli_main.main(["document", "version", "list", "--id", doc_id, "--tenant-id", "t7"])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        assert version.list_calls, "version list 未触达服务"
        assert str(version.list_calls[0]["document_id"]) == doc_id

    def test_version_list_json_envelope_whitelist(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """version list json data 白名单 set 相等（R3 补锁——原 json 面零覆盖）。"""
        _patch_services(monkeypatch)
        exit_code = cli_main.main(
            [
                "document",
                "version",
                "list",
                "--id",
                "77777777-7777-7777-7777-777777777777",
                "--tenant-id",
                "t7",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        data = json.loads(captured.out)["data"]
        assert set(data) == {"document_id", "versions"}, f"version list 白名单漂移: {sorted(data)}"
        first = data["versions"][0]
        assert set(first) == {"version", "created_by", "created_at", "diff_summary"}, f"versions 项白名单漂移: {sorted(first)}"

    def test_version_list_invalid_uuid_242_stderr(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """非法文档 ID → [EXCEPTION_242] stderr + exit 1（定式对齐——OD-10）。"""
        _patch_services(monkeypatch)
        exit_code = cli_main.main(["document", "version", "list", "--id", "not-a-uuid", "--tenant-id", "t7"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err, f"定式：错误应走 stderr 非 stdout: {captured.err!r}"


class TestVersionSnapshotCommand:
    """version snapshot 存量保形（Typer 化挂载——第 14 命令注记）。"""

    def test_snapshot_description_required_exit_2(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--description 缺省不传 → exit 2（R3 补锁——F6 必填语义而非参数存在性）。"""
        import uuid as uuid_module

        _patch_services(monkeypatch)
        exit_code = cli_main.main(
            ["document", "version", "snapshot", "--id", str(uuid_module.uuid4()), "--tenant-id", "t8", "--user", "cli7"]
        )
        captured = capsys.readouterr()
        assert exit_code == 2, f"缺 --description 应解析层 exit 2（必填语义）: exit={exit_code} err={captured.err!r}"

    def test_snapshot_calls_service(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """snapshot 经统一入口调用 create_snapshot。"""
        _, _, version = _patch_services(monkeypatch)
        doc_id = "88888888-8888-8888-8888-888888888888"
        exit_code = cli_main.main(
            ["document", "version", "snapshot", "--id", doc_id, "--tenant-id", "t8", "--user", "cli7", "--description", "初始"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        assert version.snapshot_calls, "snapshot 未触达服务"
        assert version.snapshot_calls[0]["created_by"] == "cli7"

    def test_snapshot_json_envelope_whitelist(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """snapshot json data 白名单 set 相等（R3 补锁——原 json 面零覆盖）。"""
        _patch_services(monkeypatch)
        exit_code = cli_main.main(
            [
                "document",
                "version",
                "snapshot",
                "--id",
                "88888888-8888-8888-8888-888888888888",
                "--tenant-id",
                "t8",
                "--user",
                "cli7",
                "--description",
                "初始",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        data = json.loads(captured.out)["data"]
        assert set(data) == {"snapshot_id", "document_id", "version", "created_by"}, f"snapshot 白名单漂移: {sorted(data)}"

    def test_snapshot_invalid_uuid_242_stderr(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """非法 ID → 242 stderr（保形适配——原 print stdout 定式升级）。"""
        _patch_services(monkeypatch)
        exit_code = cli_main.main(["document", "version", "snapshot", "--id", "bad", "--tenant-id", "t8", "--description", "x"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err
