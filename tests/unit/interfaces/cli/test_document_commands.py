"""Story 7-1 — document 命令组单元测试（Task 3 TDD：upload / parse）。

重写覆盖存量 version 族断言（R1-F2：旧 argparse version 命令族随
document_commands.py 重写移除——7-1-DF5 归宿，旧断言零保留）。

覆盖 AC-2/AC-5 契约：upload/parse 参数解析→DocumentUploadCommand 冻结字段/
文件不存在领域异常呈现/parse --id 实体族 242 守卫（R5-3 显式点名）/mock
短路/dry-run 端口名/stub resolve 调用契约（真实面）/全局参数尾置形态
（Task 3-6 尾置断言锚——R1-F1 P0 回归）。

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_document_commands.py -v
"""

from __future__ import annotations

import json
import uuid as uuid_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

runner = CliRunner()

_DOC_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"


class _StubUploadService:
    """document_upload_service 端口 stub（记录调用参数——契约断言载体）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def upload(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(document_id=uuid_module.UUID(int=1), filename=kwargs["filename"])


class _StubParsingService:
    """document_parsing_service 端口 stub。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def parse_document(self, document_id: Any, tenant_id: str) -> Any:
        self.calls.append({"document_id": document_id, "tenant_id": tenant_id})
        return SimpleNamespace(
            document_id=document_id,
            parse_status="completed",
            page_count=3,
        )


def _build_app(services: dict[str, Any]) -> typer.Typer:
    """经 create_cli_app 构造含 document 命令组的测试 app（stub resolve 直注）。"""
    from src.interfaces.cli.main import create_cli_app

    def _resolve(name: str) -> Any:
        if name in services:
            return services[name]
        raise KeyError(f"测试未注册端口: {name}")

    return create_cli_app(_resolve)


# ===================================================================
# 命令对象冻结字段（DC-4）
# ===================================================================


class TestDocumentCommandObjects:
    """DocumentUploadCommand / DocumentParseCommand 命令值对象契约。"""

    def test_upload_command_frozen_fields(self) -> None:
        """DocumentUploadCommand frozen dataclass 冻结字段（file/business_domain）。"""
        import dataclasses

        from src.interfaces.cli.controllers.document_controller import DocumentUploadCommand

        command = DocumentUploadCommand(file=Path("/tmp/a.md"), business_domain="市场洞察")
        assert command.file == Path("/tmp/a.md")
        assert command.business_domain == "市场洞察"
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(command, "file", Path("/tmp/b.md"))

    def test_upload_command_to_parameters(self) -> None:
        """命令对象转 parameters 载荷（归一后形态入 mock/dry-run 面）。"""
        from src.interfaces.cli.controllers.document_controller import DocumentUploadCommand

        command = DocumentUploadCommand(file=Path("/tmp/a.md"), business_domain="")
        parameters = command.to_parameters()
        assert parameters["file"] == "/tmp/a.md"
        assert parameters["business_domain"] == ""


# ===================================================================
# upload 命令
# ===================================================================


class TestDocumentUploadCommand:
    """sisys document upload 契约（AC-2/AC-5）。"""

    def test_missing_file_raises_not_found_202(self) -> None:
        """文件不存在 → NotFoundError EXCEPTION_202（领域异常先于 resolve）。"""
        from src.domain.exceptions import NotFoundError
        from src.interfaces.cli.controllers.document_controller import run_upload

        with pytest.raises(NotFoundError) as exc_info:
            run_upload(Path("/nonexistent/file.md"), business_domain="", resolve=lambda name: None)
        assert exc_info.value.code == "EXCEPTION_202"

    def test_cli_missing_file_exit_one_stderr_domain_error(self, tmp_path: Path) -> None:
        """CLI 面：文件不存在 → exit 1 + stderr [EXCEPTION_202]（main_cli 统一出口映射）。"""
        from src.entrypoints import main_cli

        exit_code = main_cli.main(["document", "upload", "--file", str(tmp_path / "missing.md")])
        assert exit_code == 1

    def test_mock_short_circuit_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """--mock --format json：Mock DTO 冻结形态（零 resolve）。"""
        temp_file = tmp_path / "doc.md"
        temp_file.write_text("内容", encoding="utf-8")
        upload_service = _StubUploadService()
        app = _build_app({"document_upload_service": upload_service})
        result = runner.invoke(app, ["document", "upload", "--file", str(temp_file), "--mock", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["mock"] is True
        assert payload["command"] == "document upload"
        assert payload["parameters"]["file"] == str(temp_file)
        assert payload["session"]
        assert upload_service.calls == [], "--mock 面 resolve 调用应为零"

    def test_dry_run_renders_port_name(self, tmp_path: Path) -> None:
        """--dry-run：静态端口名 document_upload_service（composition_root.py:1189）。"""
        temp_file = tmp_path / "doc.md"
        temp_file.write_text("内容", encoding="utf-8")
        upload_service = _StubUploadService()
        app = _build_app({"document_upload_service": upload_service})
        result = runner.invoke(app, ["document", "upload", "--file", str(temp_file), "--dry-run", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert "document_upload_service" in result.stdout
        assert upload_service.calls == [], "--dry-run 面 resolve 调用应为零"

    def test_real_call_contract_via_stub(self, tmp_path: Path) -> None:
        """真实面 stub resolve 调用契约：filename/mime_type/file_size_bytes/tenant_id/uploaded_by/file_path。"""
        temp_file = tmp_path / "战略文档.md"
        temp_file.write_text("# 内容", encoding="utf-8")
        upload_service = _StubUploadService()
        app = _build_app({"document_upload_service": upload_service})
        result = runner.invoke(
            app,
            ["document", "upload", "--file", str(temp_file), "--business-domain", "市场洞察"],
        )
        assert result.exit_code == 0, result.output
        assert len(upload_service.calls) == 1
        call = upload_service.calls[0]
        assert call["filename"] == "战略文档.md"
        assert call["file_path"] == str(temp_file)
        assert call["file_size_bytes"] == temp_file.stat().st_size
        assert call["tenant_id"], "tenant_id 必填取值（CLI 常量）"
        assert call["uploaded_by"], "uploaded_by 必填取值（CLI 常量）"
        assert call["mime_type"]
        assert call["metadata"]["business_domain"] == "市场洞察"
        assert call["metadata"]["source"] and call["metadata"]["license"], "五最小元字段补全（217 校验面）"
        assert str(uuid_module.UUID(int=1)) in result.stdout

    def test_tail_form_global_params(self, tmp_path: Path) -> None:
        """全局参数尾置形态（sisys document upload --file x --mock 后置可达——P0 回归锚 Task 3 落地）。"""
        temp_file = tmp_path / "doc.md"
        temp_file.write_text("内容", encoding="utf-8")
        app = _build_app({"document_upload_service": _StubUploadService()})
        result = runner.invoke(app, ["document", "upload", "--file", str(temp_file), "--mock", "--format", "json"])
        assert result.exit_code == 0, result.output


# ===================================================================
# parse 命令
# ===================================================================


class TestDocumentParseCommand:
    """sisys document parse 契约（实体 ID 族 242 守卫——R5-3）。"""

    def test_non_uuid_id_raises_entity_validation_242(self) -> None:
        """非 UUID --id → EntityValidationError EXCEPTION_242（实体 ID 族契约）。"""
        from src.domain.exceptions import EntityValidationError
        from src.interfaces.cli.controllers.document_controller import run_parse

        with pytest.raises(EntityValidationError) as exc_info:
            run_parse("not-a-uuid", resolve=lambda name: None)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_cli_non_uuid_exit_one(self) -> None:
        """CLI 面：非 UUID --id → exit 1（守卫先于 bootstrap）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["document", "parse", "--id", "not-a-uuid"]) == 1

    def test_real_call_contract_via_stub(self, capsys: pytest.CaptureFixture[str]) -> None:
        """真实面调用契约：parse_document(UUID 实例, tenant_id)（归一后类型）。"""
        parsing_service = _StubParsingService()
        app = _build_app({"document_parsing_service": parsing_service})
        result = runner.invoke(app, ["document", "parse", "--id", _DOC_ID, "--format", "json"])
        assert result.exit_code == 0, result.output
        assert len(parsing_service.calls) == 1
        call = parsing_service.calls[0]
        assert call["document_id"] == uuid_module.UUID(_DOC_ID), "document_id 应归一为 UUID 实例"
        assert call["tenant_id"]

    def test_uppercase_uuid_normalized_hit(self) -> None:
        """大写 --id 归一命中（canonical_uuid 守卫——AC-7 新面清偿在 document 族的呈现）。"""
        parsing_service = _StubParsingService()
        app = _build_app({"document_parsing_service": parsing_service})
        result = runner.invoke(app, ["document", "parse", "--id", _DOC_ID.upper()])
        assert result.exit_code == 0, result.output
        assert parsing_service.calls[0]["document_id"] == uuid_module.UUID(_DOC_ID)

    def test_mock_short_circuit(self) -> None:
        """--mock：DTO parameters 含归一后 document_id（守卫归一先于短路——R4-3 同族语义）。"""
        parsing_service = _StubParsingService()
        app = _build_app({"document_parsing_service": parsing_service})
        result = runner.invoke(app, ["document", "parse", "--id", _DOC_ID.upper(), "--mock", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["parameters"]["document_id"] == _DOC_ID, "大写输入应在短路前归一为 canonical 小写"
        assert parsing_service.calls == []


# ===================================================================
# help 可达与挂载替换
# ===================================================================


class TestDocumentCommandGroupMount:
    """document 命令组挂载（Task 3 替换工厂骨架——R3-4 两时点之二）。"""

    def test_upload_help_exit_zero(self) -> None:
        """sisys document upload --help 自描述可达（AC-5）。"""
        app = _build_app({})
        result = runner.invoke(app, ["document", "upload", "--help"])
        assert result.exit_code == 0
        assert "--file" in result.output

    def test_parse_help_exit_zero(self) -> None:
        """sisys document parse --help 自描述可达（AC-5）。"""
        app = _build_app({})
        result = runner.invoke(app, ["document", "parse", "--help"])
        assert result.exit_code == 0
        assert "--id" in result.output

    def test_version_subcommand_removed(self) -> None:
        """version 子命令已随重写移除（7-1-DF5 归宿——旧命令面不可达）。"""
        app = _build_app({})
        result = runner.invoke(app, ["document", "--help"])
        assert result.exit_code == 0
        assert "version" not in result.output

    def test_default_format_table_rendering(self, tmp_path: Path) -> None:
        """缺省 --format=table 渲染（R1-F30 锚在命令面落地）。"""
        temp_file = tmp_path / "doc.md"
        temp_file.write_text("内容", encoding="utf-8")
        app = _build_app({"document_upload_service": _StubUploadService()})
        result = runner.invoke(app, ["document", "upload", "--file", str(temp_file), "--mock"])
        assert result.exit_code == 0, result.output
        assert not result.stdout.strip().startswith("{")

    def test_yes_without_budget_rejected_via_cli(self, tmp_path: Path) -> None:
        """--yes 缺 --cost-budget → exit 1（守卫在 document 命令面同样生效）。"""
        from src.entrypoints import main_cli

        temp_file = tmp_path / "doc.md"
        temp_file.write_text("内容", encoding="utf-8")
        exit_code = main_cli.main(["document", "upload", "--file", str(temp_file), "--yes"])
        assert exit_code == 1
