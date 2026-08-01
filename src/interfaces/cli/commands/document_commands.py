"""文档版本管理 CLI 命令

提供文档版本快照的创建和列表查询功能。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from src.domain.ports.registry import _global_registry
from src.domain.ports.resolver import Resolver

logger = logging.getLogger(__name__)


def _get_service():
    """从依赖注入容器获取 DocumentVersionService 实例"""
    resolver = Resolver(_global_registry)
    return resolver.resolve("document_version_service")


def build_version_parser(subparsers: Any) -> None:
    """构建文档版本管理子命令解析器

    Args:
        subparsers: argparse 子命令解析器
    """
    version_parser = subparsers.add_parser(
        "version",
        help="文档版本管理",
        description="管理文档版本快照，包括创建和查询版本历史",
    )

    version_subparsers = version_parser.add_subparsers(
        dest="version_action",
        help="版本管理操作",
    )

    # snapshot 子命令
    snapshot_parser = version_subparsers.add_parser(
        "snapshot",
        help="创建文档版本快照",
        description="创建文档版本快照，记录操作者、时间戳和差异摘要",
    )
    snapshot_parser.add_argument(
        "--id",
        required=True,
        help="文档唯一标识符（UUID）",
    )
    snapshot_parser.add_argument(
        "--tenant",
        default="default",
        help="租户标识符（默认: default）",
    )
    snapshot_parser.add_argument(
        "--user",
        default="cli",
        help="操作者标识（默认: cli）",
    )
    snapshot_parser.add_argument(
        "--description",
        default="",
        help="变更描述",
    )

    # list 子命令
    list_parser = version_subparsers.add_parser(
        "list",
        help="列出版本历史",
        description="查询文档的版本历史列表",
    )
    list_parser.add_argument(
        "--id",
        required=True,
        help="文档唯一标识符（UUID）",
    )
    list_parser.add_argument(
        "--tenant",
        default="default",
        help="租户标识符（默认: default）",
    )


def handle_version(args: argparse.Namespace) -> int:
    """处理文档版本管理命令

    Args:
        args: 命令行参数

    Returns:
        退出码（0=成功，1=错误）
    """
    if args.version_action == "snapshot":
        return _handle_snapshot(args)
    elif args.version_action == "list":
        return _handle_list(args)
    else:
        print("请指定版本管理操作: snapshot 或 list")
        print("使用 'sisys document version --help' 查看帮助")
        return 1


def _handle_snapshot(args: argparse.Namespace) -> int:
    """处理创建版本快照命令

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    from uuid import UUID

    try:
        document_id = UUID(args.id)
    except ValueError:
        print(f"错误: 无效的文档 ID: {args.id}")
        return 1

    try:
        service = _get_service()
        snapshot = asyncio.run(
            service.create_snapshot(
                document_id=document_id,
                tenant_id=args.tenant,
                created_by=args.user,
                change_description=args.description,
            )
        )
        print("版本快照创建成功:")
        print(f"  文档 ID: {snapshot.document_id}")
        print(f"  版本号: {snapshot.version}")
        print(f"  快照 ID: {snapshot.snapshot_id}")
        print(f"  创建者: {snapshot.created_by}")
        print(f"  差异摘要: {snapshot.diff_summary}")
        return 0
    except Exception as e:
        print(f"错误: 创建版本快照失败: {e}")
        return 1


def _handle_list(args: argparse.Namespace) -> int:
    """处理列出版本历史命令

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    from uuid import UUID

    try:
        document_id = UUID(args.id)
    except ValueError:
        print(f"错误: 无效的文档 ID: {args.id}")
        return 1

    try:
        service = _get_service()
        versions = asyncio.run(
            service.list_versions(
                document_id=document_id,
                tenant_id=args.tenant,
            )
        )
        if not versions:
            print("该文档暂无版本历史")
            return 0

        print(f"文档 {args.id} 版本历史:")
        print("-" * 80)
        for v in versions:
            created = v.created_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"  版本 {v.version:3d} | {created} | {v.created_by:<20s} | {v.diff_summary}")
        return 0
    except Exception as e:
        print(f"错误: 查询版本历史失败: {e}")
        return 1
