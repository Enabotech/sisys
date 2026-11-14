"""集成测试——统一 CLI 入口真实服务全链（Story 7-1 Task 3 循环 C）。

真实服务 Schema 隔离子模式：resolve 组合根既有端口 + TestTenant UUID 前缀
隔离 + 自清理链（创建→执行→清理——禁 delete/truncate）。

覆盖面（AC-1 验证标准⑤）：
    - document upload 真实落库读回（MinIO+PG 全链）
    - tool list 真实元数据（组合根注册工具清单）
    - archive query 真实读（**6.4-DF2 核销场景**：无 session 上下文的 CLI
      归档消费 + 组合根 ``resolve("session_factory")`` 接线守卫断言）

测试形态：CLI 直调为同步段（controller 内 asyncio.run 在同步上下文驱动）；
预置/读回协程经独立 ``asyncio.run`` 串行驱动（同步测试函数——async 测试
宿主 loop 内直调 CLI 会撞 RuntimeError）。
"""

from __future__ import annotations

import asyncio
import json
import uuid as uuid_module
from pathlib import Path
from typing import Any

import pytest

from src.domain.ports.resolver import get_resolver

# xdist_group 收敛单 worker（R4 定谳：CLI 直调链[bootstrap+asyncio.run+MinIO/PG 双写]在
# 全仓四目录并发下与其他 database worker 争用偶发红——隔离/集成目录复跑恒绿，
# 按 4-1f pestel 先例机制闭环，收敛组内串行消除跨 worker 争用）
pytestmark = [pytest.mark.integration, pytest.mark.database, pytest.mark.xdist_group("cli-integration-chain")]


def _tenant_id() -> str:
    """集成租户（UUID 前缀隔离）。"""
    return f"cli7i_{uuid_module.uuid4().hex[:12]}"


def _clear_resolver_caches() -> None:
    """CLI 直调前双清（SCOPED engine 池绑定预置 loop——驱逐后惰性重建）。

    预置协程的 asyncio.run loop 与 CLI 直调 loop 不同——SCOPED 缓存命中的
    连接池跨 loop 必炸「Future attached to a different loop」（验收测试
    _run_cli 双清钦定同源纪律）。
    """
    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


class TestCliDocumentUploadRealChain:
    """upload 真实落库读回（in-process 直调统一入口）。"""

    def test_upload_persisted_and_readable(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """经统一入口 upload → repository 真实读回（MinIO+PG 全链）。"""
        from src.entrypoints import cli_main

        tenant = _tenant_id()
        upload_path = tmp_path / "集成上传文档.md"
        upload_path.write_text("# 集成测试上传\n\n战略文档集成链验证。", encoding="utf-8")
        capsys.readouterr()
        exit_code = cli_main.main(
            [
                "document",
                "upload",
                "--file",
                str(upload_path),
                "--business-domain",
                "tech",
                "--source",
                "internal",
                "--license",
                "confidential",
                "--tenant-id",
                tenant,
                "--uploaded-by",
                "cli7-integration",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, f"upload 失败: {captured.err!r}"
        envelope = json.loads(captured.out)
        document_id = envelope["data"]["document_id"]
        assert document_id, "信封缺 document_id"

        _clear_resolver_caches()  # CLI 直调 loop 的池驱逐（读回协程独立 loop）
        found = asyncio.run(self._read_back(document_id, tenant))
        assert found is not None, "上传文档元数据未能从存储读回（真实落库验证失败）"

        # 自清理链（R1-T1 三段收窄之一）：MinIO 对象经 l4_object.delete 定向清理
        # （key=Document.metadata["storage_object_key"]——upload service :151 写入）；
        # PG 行/L5 无端口删除 API 归 deferred-work 登记（禁手写 SQL delete 顶替）。
        # 提取段整体防御（metadata 偶发 None/缺键形态不反噬场景——清理是尽力而为）
        try:
            metadata = getattr(found, "metadata", None) or {}
            object_key = str(metadata.get("storage_object_key", ""))
        except Exception:
            object_key = ""
        if object_key:
            asyncio.run(self._cleanup_object(object_key))

    @staticmethod
    async def _cleanup_object(object_key: str) -> None:
        """MinIO 对象定向清理（同一 document_storage 端口——清理失败不反噬场景）。"""
        storage = get_resolver().resolve("document_storage")
        try:
            await storage.delete("raw-documents", object_key)
        except Exception as exc:  # 清理失败不反噬（残留登记面见 deferred-work）
            print(f"[清理链警告] MinIO 对象清理失败（可容忍残留）: {type(exc).__name__}: {exc}")

    @staticmethod
    async def _read_back(document_id: str, tenant: str) -> Any:
        """经仓储真实读回（PG 元数据——DocumentQuery Query Object 模式）。

        session_context 测试侧供给（请求路径仓储硬要求——读回与上传对称）。
        """
        from src.domain.ports.document_repository import DocumentQuery
        from src.infrastructure.storage.postgresql.session_context import session_context

        repo = get_resolver().resolve("document_repository")
        factory = get_resolver().resolve("session_factory")
        async with session_context(factory):
            return await repo.find(DocumentQuery(tenant_id=tenant, document_id=uuid_module.UUID(document_id)))


class TestCliToolListRealChain:
    """tool list 真实元数据。"""

    def test_tool_list_real_metadata(self, capsys: pytest.CaptureFixture[str]) -> None:
        """真实组合根工具清单（同步端口——list_tools_metadata Query Object）。"""
        from src.application.ports.tool_execution_service import ToolListQuery

        service = get_resolver().resolve("tool_execution_service")
        tools = service.list_tools_metadata(ToolListQuery())
        assert isinstance(tools, list), "真实工具清单应为 list 形态"

        from src.entrypoints import cli_main

        capsys.readouterr()
        exit_code = cli_main.main(["tool", "list", "--format", "json"])
        captured = capsys.readouterr()
        assert exit_code == 0, f"tool list 失败: {captured.err!r}"
        envelope = json.loads(captured.out)
        # R1-T5 定谳：测试端口库 tool 表可为空（total=0 真实行为）——恒真 >=0 无判别力，
        # 改为环境无关不变量：total 与 tools 长度一致（渲染层丢项即红）
        assert envelope["data"]["total"] == len(envelope["data"]["tools"]), "total 与 tools 长度不变量破裂"


class TestCliArchiveQueryRealChain:
    """archive query 真实读——6.4-DF2 核销场景（无 session 上下文 CLI 归档消费）。"""

    def test_archive_query_without_session_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """无 session 上下文的 CLI 归档消费（fallback 独立会话路径——CR1-F1 分支）。

        6.4-DF2 缺口：集成/验收全走 session_context 请求路径，CLI 无 ContextVar
        会话的 fallback 分支零覆盖——本场景显式清 session 后经统一入口消费。
        """
        from src.entrypoints import cli_main
        from src.infrastructure.storage.postgresql.session_context import clear_session

        _clear_resolver_caches()  # 前序场景 SCOPED 池驱逐（跨场景 loop 污染防御）
        tenant = _tenant_id()
        plan_id = str(uuid_module.uuid4())
        asyncio.run(self._preset_archive(plan_id, tenant))
        _clear_resolver_caches()  # 预置 loop 的 SCOPED 池驱逐（CLI 直调双清纪律）
        clear_session()  # 显式无会话上下文——CLI 消费形态（6.4-DF2 场景语义）
        capsys.readouterr()
        exit_code = cli_main.main(["archive", "query", "--plan-id", plan_id, "--tenant-id", tenant, "--format", "json"])
        captured = capsys.readouterr()
        assert exit_code == 0, f"无会话归档消费失败: {captured.err!r}"
        envelope = json.loads(captured.out)
        assert envelope["data"]["total"] >= 1, "预置归档未命中（无会话 fallback 路径数据面失败）"

    @staticmethod
    async def _preset_archive(plan_id: str, tenant: str) -> None:
        """真实归档预置（archive_plan——L2+L3+L4+L5 全链）。"""
        service = get_resolver().resolve("strategic_archive_service")
        await service.archive_plan(
            plan_id=uuid_module.UUID(plan_id),
            plan_type="SP",
            assumptions={"summary": "CLI 集成归档预置", "tenant": tenant},
        )

    def test_session_factory_wiring_guard(self) -> None:
        """组合根 resolve("session_factory") 接线守卫断言（注册名漂移即红）。

        6.4-DF2 缺口第二面：archive_repository 注册 lambda 的 session_factory
        注入无自动化断言——本守卫锁组合根注册名在册可 resolve。
        """
        factory = get_resolver().resolve("session_factory")
        assert factory is not None, "session_factory 注册名漂移（组合根接线断裂）"
        assert hasattr(factory, "__call__"), "session_factory 应为可调用工厂形态"
