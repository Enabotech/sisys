"""CLI 文档版本管理命令单元测试

测试 document_commands CLI 命令的参数解析、路由和异常处理。
使用 Mock 解耦真实服务依赖。
"""

from __future__ import annotations

import argparse
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.interfaces.cli.commands.document_commands import (
    _handle_list,
    _handle_snapshot,
    build_version_parser,
    handle_version,
)


class TestVersionParser:
    """测试 version 命令解析器构建"""

    def test_build_parser_creates_version_subparser(self) -> None:
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        build_version_parser(subparsers)

        # 验证子命令存在
        assert "version" in subparsers.choices

    def test_snapshot_subcommand_parses_args(self) -> None:
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        build_version_parser(subparsers)

        args = main_parser.parse_args(
            [
                "version",
                "snapshot",
                "--id",
                str(uuid4()),
                "--tenant",
                "test_tenant",
            ]
        )
        assert args.command == "version"
        assert args.version_action == "snapshot"
        assert args.tenant == "test_tenant"

    def test_snapshot_default_values(self) -> None:
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        build_version_parser(subparsers)

        args = main_parser.parse_args(["version", "snapshot", "--id", str(uuid4())])
        assert args.tenant == "default"
        assert args.user == "cli"
        assert args.description == ""

    def test_list_subcommand_parses_args(self) -> None:
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        build_version_parser(subparsers)

        args = main_parser.parse_args(["version", "list", "--id", str(uuid4())])
        assert args.version_action == "list"


class TestHandleVersion:
    """测试 handle_version 路由逻辑"""

    def test_invalid_action_prints_help(self, capsys) -> None:
        args = argparse.Namespace(version_action="invalid")
        result = handle_version(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "请指定版本管理操作" in captured.out

    def test_unknown_action_returns_1(self) -> None:
        args = argparse.Namespace(version_action="unknown_action")
        result = handle_version(args)
        assert result == 1


class TestHandleSnapshot:
    """测试 _handle_snapshot 异常处理"""

    def test_invalid_uuid_returns_error(self, capsys) -> None:
        args = argparse.Namespace(
            id="not-a-valid-uuid",
            tenant="default",
            user="test",
            description="desc",
        )
        result = _handle_snapshot(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "无效的文档 ID" in captured.out

    def test_service_error_returns_1(self) -> None:
        with patch(
            "src.interfaces.cli.commands.document_commands._get_service",
            side_effect=RuntimeError("service unavailable"),
        ):
            args = argparse.Namespace(
                id=str(uuid4()),
                tenant="default",
                user="test",
                description="desc",
            )
            result = _handle_snapshot(args)
            assert result == 1

    def test_value_error_returns_1(self) -> None:
        mock_service = AsyncMock()
        mock_service.create_snapshot.side_effect = ValueError("invalid param")

        with (
            patch(
                "src.interfaces.cli.commands.document_commands._get_service",
                return_value=mock_service,
            ),
            patch(
                "src.interfaces.cli.commands.document_commands.asyncio.run",
                side_effect=ValueError("invalid param"),
            ),
        ):
            args = argparse.Namespace(
                id=str(uuid4()),
                tenant="default",
                user="test",
                description="desc",
            )
            result = _handle_snapshot(args)
            assert result == 1


class TestHandleList:
    """测试 _handle_list 异常处理"""

    def test_invalid_uuid_returns_error(self, capsys) -> None:
        args = argparse.Namespace(
            id="bad-uuid",
            tenant="default",
        )
        result = _handle_list(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "无效的文档 ID" in captured.out

    def test_empty_versions_prints_message(self, capsys) -> None:
        mock_service = AsyncMock()
        mock_service.list_versions.return_value = []

        with (
            patch(
                "src.interfaces.cli.commands.document_commands._get_service",
                return_value=mock_service,
            ),
            patch(
                "src.interfaces.cli.commands.document_commands.asyncio.run",
                return_value=[],
            ),
        ):
            args = argparse.Namespace(
                id=str(uuid4()),
                tenant="default",
            )
            result = _handle_list(args)
            assert result == 0
            captured = capsys.readouterr()
            assert "暂无版本历史" in captured.out

    def test_service_raises_returns_error(self) -> None:
        with patch(
            "src.interfaces.cli.commands.document_commands._get_service",
            side_effect=RuntimeError("connection failed"),
        ):
            args = argparse.Namespace(
                id=str(uuid4()),
                tenant="default",
            )
            result = _handle_list(args)
            assert result == 1


__all__ = [
    "TestVersionParser",
    "TestHandleVersion",
    "TestHandleSnapshot",
    "TestHandleList",
]
