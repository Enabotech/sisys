"""统一 sisys CLI 入口验收测试（Story 7-1）。

对应 feature：test_acceptance_unified_cli.feature（19 业务场景——AC-1×4 /
AC-2×5 / AC-3×4 / AC-4×2 / AC-5×1 / AC-6×1 / AC-7×2；AC-8×2 与收尾×2 由
Task 9 追加至最终态 23）。

真实服务验收（无 mock）：Mock 模式（--mock）为产品面短路语义非测试替身；
真实链场景经 in-process 直调 main_cli.main([...])（agent_cli.py:2623 同签名
先例——SystemExit 兜底捕获），直调前后双清（clear_singleton+clear_scoped）；
步骤函数体内延迟 import（收集期零 error，红形态=运行期 ImportError）。

Run with: poetry run pytest tests/acceptance/test_acceptance_unified_cli.py -v

Prerequisites:
    - 真实服务场景（文档上传/解析、Checkpoint 族、轻量真实链、工具 schema）
      需 PostgreSQL 等存储可达，不可达时动态 pytest.skip()
    - Mock/预览/用法错误/守卫场景零外部服务依赖
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid as uuid_module
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.xdist_group("unified-cli-acceptance"),
]

# ===================================================================
# Paths & Constants
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

# Mock 面固定测试 UUID（占位形态——真实场景各自生成并登记 context）
DEFAULT_AGENT_ID = "11111111-1111-1111-1111-111111111111"

# 工具 schema 场景的 slug（AC-6 验收 tool-id 选用已补齐 slug——R1-F38 联动）
SCHEMA_TOOL_SLUG = "pestel-analysis"

# 完成清单（Task 9 收尾场景断言对象 = File List 的 src/测试项存在性）
COMPLETION_SRC_FILES: dict[str, str] = {
    "进程入口（load_dotenv→懒 bootstrap→create_cli_app→派发）": "src/entrypoints/main_cli.py",
    "CLI 工厂（create_cli_app+全局参数+退出码）": "src/interfaces/cli/main.py",
    "共享守卫（canonical_uuid/require_agent_budget）": "src/interfaces/cli/_guards.py",
    "共享 Annotated 参数注解": "src/interfaces/cli/_params.py",
    "document 命令组（upload/parse）": "src/interfaces/cli/commands/document_commands.py",
    "tool 命令组（list/schema/run/chain run）": "src/interfaces/cli/commands/tool_commands.py",
    "agent 命令组（run）": "src/interfaces/cli/commands/agent_commands.py",
    "plan 命令组（generate）": "src/interfaces/cli/commands/planning_commands.py",
    "checkpoint 命令组（list/show/recover）": "src/interfaces/cli/commands/checkpoint_commands.py",
    "archive 命令组（query）": "src/interfaces/cli/commands/archive_commands.py",
    "document 控制器": "src/interfaces/cli/controllers/document_controller.py",
    "tool 控制器": "src/interfaces/cli/controllers/tool_controller.py",
    "agent 控制器": "src/interfaces/cli/controllers/agent_controller.py",
    "plan 控制器": "src/interfaces/cli/controllers/planning_controller.py",
    "checkpoint 控制器": "src/interfaces/cli/controllers/checkpoint_controller.py",
    "archive 控制器": "src/interfaces/cli/controllers/archive_controller.py",
    "JSON 格式化器": "src/interfaces/cli/formatters/json_formatter.py",
    "表格格式化器": "src/interfaces/cli/formatters/table_formatter.py",
    "美化格式化器": "src/interfaces/cli/formatters/pretty_formatter.py",
    "格式化器包入口": "src/interfaces/cli/formatters/__init__.py",
}
COMPLETION_TEST_FILES: dict[str, str] = {
    "格式化器单测": "tests/unit/interfaces/cli/test_cli_formatters.py",
    "CLI 框架单测": "tests/unit/interfaces/cli/test_cli_framework.py",
    "document 命令单测（重写覆盖）": "tests/unit/interfaces/cli/test_document_commands.py",
    "tool 命令单测": "tests/unit/interfaces/cli/test_tool_commands.py",
    "agent/plan 命令单测": "tests/unit/interfaces/cli/test_agent_plan_commands.py",
    "checkpoint/archive 命令单测": "tests/unit/interfaces/cli/test_checkpoint_archive_commands.py",
    "frontmatter input_examples 单测": "tests/unit/application/skills/test_frontmatter_input_examples.py",
    "架构验证测试": "tests/unit/architecture/test_arch_unified_cli.py",
    "端口契约测试": "tests/contracts/test_port_contract_unified_cli.py",
    "集成测试": "tests/integration/test_integration_unified_cli.py",
    "验收 feature": "tests/acceptance/test_acceptance_unified_cli.feature",
    "验收 BDD 步骤实现": "tests/acceptance/test_acceptance_unified_cli.py",
}

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def event_loop() -> Any:
    """模块级事件循环（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失防线）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context(
    event_loop: Any,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> Generator[dict[str, Any], None, None]:
    """场景级状态字典（占位符值位 + CLI 直调产物位 + teardown 清单）。

    直调前双清（防 ConflictError 假红与跨文件 SINGLETON 死池——analyst_view
    前清先例）；yield 后定向清理自建资源（断言失败也执行）再双清。
    """
    _clear_resolver_caches()
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_capsys_ref": capsys,
        "_tmp_path": tmp_path,
        "_plan_ids": [],
        "_document_ids": [],
        "_temp_files": [],
        "plan_id": "",
        "plan_id_upper": "",
        "document_id": "",
        "agent_id": DEFAULT_AGENT_ID,
        "temp_file": "",
        "cli_exit_code": None,
        "cli_stdout": "",
        "cli_stderr": "",
    }
    yield ctx
    _teardown_assets(ctx)
    _clear_resolver_caches()


def _clear_resolver_caches() -> None:
    """驱逐 resolver SINGLETON/SCOPED 缓存（CLI 直调双清钦定——6-6 R3-1 先例）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


def _teardown_assets(ctx: dict[str, Any]) -> None:
    """场景 teardown（断言失败也执行——yield fixture teardown 语义）。

    定向清理本场景自建资源：document upload 的 PG 行（documents 表
    document_id 面）与 L0 临时文件、checkpoint 的 Redis 键族
    （snapshot:blm-checkpoint-{plan}:{cp} + 恢复记录键——checkpoint_recovery
    验收 _cleanup_redis_keys 先例形态）。零手动全表清理。
    """
    loop = ctx["_loop"]
    document_ids = list(ctx["_document_ids"])
    plan_ids = list(ctx["_plan_ids"])
    for path in list(ctx["_temp_files"]):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    async def _cleanup() -> None:
        from src.application.ports.checkpoint import (
            CHECKPOINT_RECOVERY_SESSION_PREFIX,
            CHECKPOINT_SESSION_PREFIX,
        )
        from src.infrastructure.storage.redis.key_builder import build_key

        if document_ids:
            import asyncpg

            from tests.environments import get_test_env

            env = get_test_env()
            conn = await asyncpg.connect(
                host=env.postgres.host,
                port=env.postgres.port,
                user=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
            try:
                await conn.execute("DELETE FROM documents WHERE id = ANY($1::uuid)", document_ids)
            finally:
                await conn.close()
        if plan_ids:
            import redis.asyncio as aioredis

            from tests.environments import get_test_env

            env = get_test_env()
            client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
            try:
                keys = [f"{CHECKPOINT_RECOVERY_SESSION_PREFIX}{plan_id}" for plan_id in plan_ids]
                keys.extend(
                    build_key("snapshot", f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:CP-{no}")
                    for plan_id in plan_ids
                    for no in range(1, 9)
                )
                await client.delete(*keys)
            finally:
                await client.close()  # close 形态对齐仓内验收先例（analyst_view :325——类型存根无 aclose）

    try:
        loop.run_until_complete(_cleanup())
    except Exception:  # teardown 容错（服务不可达时静默跳过——各步独立 try/except 先例）
        pass


def _require_postgres(ctx: dict[str, Any]) -> None:
    """真实 PostgreSQL 探测（不可达 pytest.skip——postgresql_relational_layer 背景探测先例形态）。"""
    import asyncpg

    from tests.environments import get_test_env

    env = get_test_env()

    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(
                host=env.postgres.host,
                port=env.postgres.port,
                user=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
            await conn.close()
            return True
        except Exception:
            return False

    loop = asyncio.new_event_loop()
    is_available = loop.run_until_complete(_check())
    loop.close()
    asyncio.set_event_loop(ctx["_loop"])
    if not is_available:
        pytest.skip(f"PostgreSQL not available at {env.postgres.host}:{env.postgres.port}")


def _invoke_cli(ctx: dict[str, Any], argv: list[str]) -> None:
    """in-process 直调 main_cli.main（延迟 import——红形态=运行期 ImportError）。

    直调前双清（防 ConflictError 假红）、直调后 SystemExit 兜底捕获退出码、
    再双清（防 SINGLETON 连接池跨 loop 残留——checkpoint_recovery 先例）。
    """
    from src.entrypoints import main_cli

    _clear_resolver_caches()
    try:
        ctx["cli_exit_code"] = main_cli.main(list(argv))
    except SystemExit as error:
        ctx["cli_exit_code"] = int(error.code or 0)
    finally:
        captured = ctx["_capsys_ref"].readouterr()
        ctx["cli_stdout"] = captured.out
        ctx["cli_stderr"] = captured.err
        _clear_resolver_caches()


def _create_checkpoint_fixture(ctx: dict[str, Any], plan_id: str, checkpoint_no: str = "CP-1") -> None:
    """经 checkpoint_use_case（CreateCheckpointUseCase :2496）直创 checkpoint（given 前置链）。

    retrieved_docs 空列表 CLI 路径构造先例（docstring 明示）；创建链含 LLM
    上下文压缩依赖——无 Key 环境动态 skip。
    """
    _clear_resolver_caches()

    async def _create() -> None:
        from src.domain.ports.resolver import resolve

        use_case = resolve("checkpoint_use_case")
        await use_case.execute(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id="market_insight",
            query="验收前置创建链查询",
            retrieved_docs=[],
            user_id="acceptance-cli",
            summary="Story 7-1 验收前置 checkpoint",
        )

    try:
        ctx["_loop"].run_until_complete(_create())
    except Exception as error:  # LLM 压缩依赖门控（无 Key 环境 skip）
        if "API Key" in str(error) or "LLMConfig" in type(error).__name__:
            pytest.skip(f"LLM API Key 未配置——checkpoint 创建链依赖上下文压缩 LLM: {error}")
        raise


def _make_temp_file(ctx: dict[str, Any], content: str) -> str:
    """创建临时文件并登记 teardown 清理。"""
    temp_file = ctx["_tmp_path"] / f"cli-acceptance-{uuid_module.uuid4().hex[:8]}.md"
    temp_file.write_text(content, encoding="utf-8")
    ctx["temp_file"] = str(temp_file)
    ctx["_temp_files"].append(str(temp_file))
    return str(temp_file)


# ===================================================================
# Background Steps
# ===================================================================


@given("统一 CLI 进程入口已装配")
def unified_cli_entrypoint_ready():
    """背景步骤：入口装配占位（实际导入检查由各 when 步骤延迟 import 承载）。"""
    pass


# ===================================================================
# AC-1: 统一 CLI 入口与命令解析契约
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "三级命令结构自描述")
def test_three_level_command_structure_self_description(context: dict[str, Any]):
    """验证 sisys --help 三级命令结构自描述与六模块可见。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "版本号查询")
def test_version_query(context: dict[str, Any]):
    """验证 sisys --version 退出码与版本输出。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "用法错误返回退出码 2")
def test_usage_error_exit_code_two(context: dict[str, Any]):
    """验证未知命令/缺必填参数/非法格式值的用法错误退出码。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "领域异常呈现契约")
def test_domain_error_presentation_contract(context: dict[str, Any]):
    """验证 DomainError 的 stderr 呈现格式与退出码 1。"""
    pass


@when("执行 sisys --help")
def execute_sisys_help(context: dict[str, Any]):
    """执行 --help 命令。"""
    _invoke_cli(context, ["--help"])


@when("执行 sisys --version")
def execute_sisys_version(context: dict[str, Any]):
    """执行 --version 命令。"""
    _invoke_cli(context, ["--version"])


@when("执行 sisys unknown-command")
def execute_sisys_unknown_command(context: dict[str, Any]):
    """执行未知命令。"""
    _invoke_cli(context, ["unknown-command"])


@when("执行 sisys document upload")
def execute_sisys_document_upload_missing_args(context: dict[str, Any]):
    """执行缺必填参数的 document upload。"""
    _invoke_cli(context, ["document", "upload"])


@when("执行 sisys tool list --format yaml")
def execute_sisys_tool_list_invalid_format(context: dict[str, Any]):
    """执行非法 --format 值的 tool list。"""
    _invoke_cli(context, ["tool", "list", "--format", "yaml"])


@when("执行 sisys document parse --id not-a-uuid")
def execute_sisys_document_parse_invalid_uuid(context: dict[str, Any]):
    """执行非 UUID 文档标识的 document parse。"""
    _invoke_cli(context, ["document", "parse", "--id", "not-a-uuid"])


@then("退出码为 0")
def verify_exit_code_zero(context: dict[str, Any]):
    """验证退出码为 0（成功——含空态）。"""
    assert context["cli_exit_code"] == 0, (
        f"退出码应为 0，实际 {context['cli_exit_code']}；stdout={context['cli_stdout']!r}；stderr={context['cli_stderr']!r}"
    )


@then("退出码为 1")
def verify_exit_code_one(context: dict[str, Any]):
    """验证退出码为 1（DomainError）。"""
    assert context["cli_exit_code"] == 1, f"退出码应为 1，实际 {context['cli_exit_code']}；stderr={context['cli_stderr']!r}"


@then("退出码为 2")
def verify_exit_code_two(context: dict[str, Any]):
    """验证退出码为 2（用法错误）。"""
    assert context["cli_exit_code"] == 2, f"退出码应为 2，实际 {context['cli_exit_code']}；stdout={context['cli_stdout']!r}"


@then("六大模块命令组全部可见")
def verify_six_module_command_groups(context: dict[str, Any]):
    """验证 --help 输出六大模块命令组全部可见。"""
    for module_name in ("document", "tool", "agent", "plan", "checkpoint", "archive"):
        assert module_name in context["cli_stdout"], f"--help 输出缺模块 {module_name}: {context['cli_stdout']!r}"


@then("输出包含版本号")
def verify_version_output(context: dict[str, Any]):
    """验证 --version 输出包含版本信息。"""
    assert context["cli_stdout"].strip(), "--version 输出为空"
    assert "version" in context["cli_stdout"].lower() or any(char.isdigit() for char in context["cli_stdout"]), (
        f"--version 输出无版本信息: {context['cli_stdout']!r}"
    )


@then("stderr 呈现领域异常编码与消息")
def verify_domain_error_stderr(context: dict[str, Any]):
    """验证 stderr 呈现 [EXCEPTION_NNN] message 格式（agent_cli 逐字对齐契约）。"""
    pattern = re.compile(r"\[EXCEPTION_\d+\] .+")
    assert pattern.search(context["cli_stderr"]), f"stderr 缺 [EXCEPTION_NNN] message 呈现: {context['cli_stderr']!r}"


# ===================================================================
# AC-2: 四大核心工作流端到端
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "文档上传真实链")
def test_document_upload_real_chain(context: dict[str, Any]):
    """验证 document upload 真实服务上传与文档标识输出。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "文档解析真实链")
def test_document_parse_real_chain(context: dict[str, Any]):
    """验证 document parse 真实解析链。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "Agent 运行 Mock 响应")
def test_agent_run_mock_response(context: dict[str, Any]):
    """验证 agent run Mock 响应模式结构化输出。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "规划生成 Mock 响应")
def test_plan_generate_mock_response(context: dict[str, Any]):
    """验证 plan generate Mock 响应模式结构化输出。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "Checkpoint 恢复真实链")
def test_checkpoint_recover_real_chain(context: dict[str, Any]):
    """验证 checkpoint recover 真实恢复链（用例前置创建→恢复）。"""
    pass


@given("真实文档服务可用且临时文件已创建")
def document_service_available_with_temp_file(context: dict[str, Any]):
    """真实文档链前置：PG 探测 + 临时战略文档创建（登记 teardown）。"""
    _require_postgres(context)
    _make_temp_file(context, "# 战略文档\n\n市场洞察分析样例内容。")


@given("文档已通过真实服务上传")
def document_uploaded_via_real_service(context: dict[str, Any]):
    """解析链前置：经 document_upload_service 真实上传并登记 teardown。"""
    _require_postgres(context)
    if not context.get("temp_file"):
        _make_temp_file(context, "# 战略文档\n\n解析链验收样例。")

    async def _upload() -> str:
        from src.domain.ports.resolver import resolve

        service = resolve("document_upload_service")
        document = await service.upload(
            filename=Path(context["temp_file"]).name,
            mime_type="text/markdown",
            file_size_bytes=Path(context["temp_file"]).stat().st_size,
            tenant_id="cli-acceptance",
            uploaded_by="cli-acceptance",
            file_path=context["temp_file"],
            metadata={
                "business_domain": "cli-acceptance",
                "source": "cli-upload",
                "license": "internal",
            },
        )
        return str(document.document_id)

    context["document_id"] = context["_loop"].run_until_complete(_upload())
    context["_document_ids"].append(uuid_module.UUID(context["document_id"]))


@given("Checkpoint 已通过用例前置创建")
def checkpoint_created_via_use_case(context: dict[str, Any]):
    """Checkpoint 族前置：经 checkpoint_use_case 直创 CP-1 并登记 plan_id（大写形态同步备好）。"""
    _require_postgres(context)
    plan_id = str(uuid_module.uuid4())
    context["plan_id"] = plan_id
    context["plan_id_upper"] = plan_id.upper()
    context["_plan_ids"].append(uuid_module.UUID(plan_id))
    _create_checkpoint_fixture(context, plan_id, "CP-1")


@when("执行文档上传命令")
def execute_document_upload_command(context: dict[str, Any]):
    """执行 document upload（临时文件路径经 context 占位）。"""
    _invoke_cli(context, ["document", "upload", "--file", context["temp_file"]])


@when("执行文档解析命令")
def execute_document_parse_command(context: dict[str, Any]):
    """执行 document parse（上传产出的文档标识）。"""
    _invoke_cli(context, ["document", "parse", "--id", context["document_id"]])


@when("执行 Agent 运行 Mock 命令")
def execute_agent_run_mock_command(context: dict[str, Any]):
    """执行 agent run --mock --yes --cost-budget。"""
    _invoke_cli(
        context,
        [
            "agent",
            "run",
            context["agent_id"],
            "--task",
            "分析市场趋势",
            "--mock",
            "--yes",
            "--cost-budget",
            "1.5",
        ],
    )


@when("执行规划生成 Mock 命令")
def execute_plan_generate_mock_command(context: dict[str, Any]):
    """执行 plan generate --mock --yes --cost-budget。"""
    _invoke_cli(
        context,
        [
            "plan",
            "generate",
            "--agent-id",
            context["agent_id"],
            "--task",
            "生成战略规划",
            "--mock",
            "--yes",
            "--cost-budget",
            "2.0",
        ],
    )


@when("执行 Checkpoint 恢复命令")
def execute_checkpoint_recover_command(context: dict[str, Any]):
    """执行 checkpoint recover --plan-id --checkpoint-no --yes --cost-budget。"""
    _invoke_cli(
        context,
        [
            "checkpoint",
            "recover",
            "--plan-id",
            context["plan_id"],
            "--checkpoint-no",
            "CP-1",
            "--yes",
            "--cost-budget",
            "1.0",
        ],
    )


@then("输出包含文档标识")
def verify_document_id_output(context: dict[str, Any]):
    """验证上传输出包含文档标识。"""

    def _is_uuid(value: str) -> bool:
        try:
            uuid_module.UUID(value)
        except ValueError:
            return False
        return True

    assert "document_id" in context["cli_stdout"].lower() or any(_is_uuid(token) for token in context["cli_stdout"].split()), (
        f"输出缺文档标识: {context['cli_stdout']!r}"
    )


@then("输出包含 Mock 响应结构")
def verify_mock_response_structure(context: dict[str, Any]):
    """验证 Mock DTO 冻结形态（mock/command/parameters/session 四要素——格式无关）。

    --format json 时经 JSON 解析断言四键；缺省 table 渲染时断言四要素
    键名与值在场（AC-2 钦定命令行无 --format，输出为缺省 table）。
    """
    text = context["cli_stdout"]
    assert text.strip(), "Mock 输出为空"
    try:
        payload = json.loads(text.strip())
    except json.JSONDecodeError:
        for key in ("mock", "command", "parameters", "session"):
            assert key in text, f"Mock 渲染缺要素 {key}: {text!r}"
        assert "True" in text or "true" in text, "mock 标记值应在场"
        return
    for key in ("mock", "command", "parameters", "session"):
        assert key in payload, f"Mock DTO 缺键 {key}: {payload!r}"
    assert payload["mock"] is True


@then("输出包含恢复结果")
def verify_recovery_output(context: dict[str, Any]):
    """验证 checkpoint recover 输出包含恢复产物。"""
    output = context["cli_stdout"]
    assert "checkpoint" in output.lower() or "recovery" in output.lower() or "恢复" in output, f"输出缺恢复结果: {output!r}"


# ===================================================================
# AC-3: 全局参数与 Agent 模式参数契约
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "Agent 模式缺成本预算拒绝")
def test_agent_mode_missing_budget_rejected(context: dict[str, Any]):
    """验证 --yes 缺 --cost-budget 的拒绝契约。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "预览模式零装配")
def test_dry_run_zero_bootstrap(context: dict[str, Any]):
    """验证 --dry-run 预览输出与零装配语义。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "Mock 模式合法 JSON 输出")
def test_mock_mode_valid_json(context: dict[str, Any]):
    """验证 --mock --format json 组合输出合法性与会话标识。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "预览优先于 Mock")
def test_dry_run_takes_precedence_over_mock(context: dict[str, Any]):
    """验证 --dry-run 与 --mock 同给时预览优先。"""
    pass


@when("执行缺少成本预算的 Agent 命令")
def execute_agent_command_without_budget(context: dict[str, Any]):
    """执行 --yes 但缺 --cost-budget 的 agent run。"""
    _invoke_cli(context, ["agent", "run", context["agent_id"], "--task", "分析", "--yes"])


@when("执行预览模式命令")
def execute_dry_run_command(context: dict[str, Any]):
    """执行 tool run --dry-run。"""
    _invoke_cli(context, ["tool", "run", "pestel-analysis", "--input", "{}", "--dry-run"])


@when("执行 Mock 模式 JSON 输出命令")
def execute_mock_json_command(context: dict[str, Any]):
    """执行 agent run --mock --format json。"""
    _invoke_cli(
        context,
        [
            "agent",
            "run",
            context["agent_id"],
            "--task",
            "分析",
            "--mock",
            "--yes",
            "--cost-budget",
            "1.0",
            "--format",
            "json",
        ],
    )


@when("执行预览与 Mock 叠加命令")
def execute_dry_run_mock_command(context: dict[str, Any]):
    """执行 --dry-run --mock 同给形态（预览优先契约锚）。"""
    _invoke_cli(
        context,
        [
            "agent",
            "run",
            context["agent_id"],
            "--task",
            "分析",
            "--dry-run",
            "--mock",
            "--yes",
            "--cost-budget",
            "1.0",
        ],
    )


@then("输出包含消费端口名与归一后参数")
def verify_dry_run_output(context: dict[str, Any]):
    """验证 --dry-run 输出静态端口名与归一后参数（不 bootstrap）。"""
    assert context["cli_stdout"].strip(), "--dry-run 输出为空"
    assert "端口" in context["cli_stdout"] or "_service" in context["cli_stdout"] or "_use_case" in (context["cli_stdout"]), (
        f"--dry-run 输出缺端口名: {context['cli_stdout']!r}"
    )


@then("输出为合法 JSON 且包含 Mock 标记与会话标识")
def verify_mock_json_with_session(context: dict[str, Any]):
    """验证 JSON 可解析 + mock 标记 + session 字段非空（缺省自动生成入 DTO——R2-4）。"""
    payload = _parse_json_payload(context)
    assert payload.get("mock") is True, f"缺 mock 标记: {payload!r}"
    assert payload.get("session"), f"session 字段为空: {payload!r}"


# ===================================================================
# AC-4: 三态输出格式化器
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "JSON 输出可解析")
def test_json_output_parseable(context: dict[str, Any]):
    """验证 json 格式化器输出 json.loads 可解析。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "表格与美化输出")
def test_table_and_pretty_output(context: dict[str, Any]):
    """验证缺省 table 渲染与 pretty 渲染形态。"""
    pass


@when("执行 Mock 上传 JSON 输出命令")
def execute_mock_upload_json_command(context: dict[str, Any]):
    """执行 document upload --mock --format json。"""
    _make_temp_file(context, "# 战略文档\n\n格式化验收样例。")
    _invoke_cli(context, ["document", "upload", "--file", context["temp_file"], "--mock", "--format", "json"])


@when("执行 Mock 上传命令")
def execute_mock_upload_command(context: dict[str, Any]):
    """执行 document upload --mock（缺省 table 格式）。"""
    _make_temp_file(context, "# 战略文档\n\n格式化验收样例。")
    _invoke_cli(context, ["document", "upload", "--file", context["temp_file"], "--mock"])


@when("执行 Mock 上传美化输出命令")
def execute_mock_upload_pretty_command(context: dict[str, Any]):
    """执行 document upload --mock --format pretty。"""
    _make_temp_file(context, "# 战略文档\n\n格式化验收样例。")
    _invoke_cli(context, ["document", "upload", "--file", context["temp_file"], "--mock", "--format", "pretty"])


@then("输出为合法 JSON")
def verify_valid_json(context: dict[str, Any]):
    """验证输出 json.loads 可解析（pipe 给 jq / LLM 直接消费）。"""
    json.loads(context["cli_stdout"].strip())


@then("输出包含表格渲染")
def verify_table_rendering(context: dict[str, Any]):
    """验证缺省格式为 table 渲染（非 JSON 非空）。"""
    output = context["cli_stdout"]
    assert output.strip(), "table 输出为空"
    assert not output.strip().startswith("{"), f"默认格式应为 table 非 JSON: {output!r}"


@then("输出包含美化渲染")
def verify_pretty_rendering(context: dict[str, Any]):
    """验证 pretty 渲染输出（分组缩进文本非空）。"""
    assert context["cli_stdout"].strip(), "pretty 输出为空"


# ===================================================================
# AC-5: 六模块 CLI 入口覆盖（轻量真实链）
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "轻量真实链三命令")
def test_lightweight_real_chain_four_commands(context: dict[str, Any]):
    """验证 tool list / checkpoint list / archive query 轻量真实链。"""
    pass


@given("真实工具与归档服务可用")
def tool_and_archive_services_available(context: dict[str, Any]):
    """轻量真实链前置：PG 探测 + plan_id 就位（bootstrap 全组合根装配——R3-9 名实注记）。"""
    _require_postgres(context)
    if not context.get("plan_id"):
        plan_id = str(uuid_module.uuid4())
        context["plan_id"] = plan_id
        context["plan_id_upper"] = plan_id.upper()
        context["_plan_ids"].append(uuid_module.UUID(plan_id))


@when("执行工具清单命令")
def execute_tool_list_command(context: dict[str, Any]):
    """执行 tool list。"""
    _invoke_cli(context, ["tool", "list"])


@when("执行 Checkpoint 清单命令")
def execute_checkpoint_list_command(context: dict[str, Any]):
    """执行 checkpoint list --plan-id。"""
    _invoke_cli(context, ["checkpoint", "list", "--plan-id", context["plan_id"]])


@when("执行归档查询命令")
def execute_archive_query_command(context: dict[str, Any]):
    """执行 archive query --plan-id。"""
    _invoke_cli(context, ["archive", "query", "--plan-id", context["plan_id"]])


# ===================================================================
# AC-6: P7 input_examples 暴露
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "工具 schema 暴露输入示例")
def test_tool_schema_exposes_input_examples(context: dict[str, Any]):
    """验证 tool schema JSON 输出含非空 input_examples。"""
    pass


@when("执行工具 schema 查询命令")
def execute_tool_schema_command(context: dict[str, Any]):
    """执行 tool schema <slug> --format json（slug=已补齐 input_examples 的工具——R1-F38 联动）。"""
    _invoke_cli(context, ["tool", "schema", SCHEMA_TOOL_SLUG, "--format", "json"])


@then("输出为合法 JSON 且包含非空输入示例")
def verify_schema_input_examples(context: dict[str, Any]):
    """验证 input_examples 字段非空（P7 承载——skill_loader 通路锚）。"""
    payload = _parse_json_payload(context)
    examples = payload.get("input_examples")
    assert examples, f"input_examples 为空: {payload!r}"


# ===================================================================
# AC-7: 输入守卫与入口环境装配
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "大写 UUID 归一命中")
def test_uppercase_uuid_normalized_hit(context: dict[str, Any]):
    """验证大写 --plan-id 经 canonical 归一后命中（非静默空态）。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "非 UUID 守卫双契约")
def test_non_uuid_guard_dual_contract(context: dict[str, Any]):
    """验证 plan-id 族 242 与 agent-id 族 201 双守卫契约。"""
    pass


@when("执行大写 PlanID 的 Checkpoint 清单命令")
def execute_checkpoint_list_uppercase_plan_id(context: dict[str, Any]):
    """执行 checkpoint list --plan-id <大写UUID>。"""
    _invoke_cli(context, ["checkpoint", "list", "--plan-id", context["plan_id_upper"]])


@when("执行非 UUID PlanID 的 Checkpoint 清单命令")
def execute_checkpoint_list_non_uuid_plan_id(context: dict[str, Any]):
    """执行 checkpoint list --plan-id not-a-uuid（242 守卫族）。"""
    _invoke_cli(context, ["checkpoint", "list", "--plan-id", "not-a-uuid"])


@when("执行非 UUID AgentID 的规划生成命令")
def execute_plan_generate_non_uuid_agent_id(context: dict[str, Any]):
    """执行 plan generate --agent-id not-a-uuid（201 守卫族）。"""
    _invoke_cli(context, ["plan", "generate", "--agent-id", "not-a-uuid", "--task", "分析"])


@then("输出包含 Checkpoint 清单命中")
def verify_checkpoint_list_hit(context: dict[str, Any]):
    """验证大写 --plan-id 归一命中 CP-1（非静默空态——与存量宽松守卫对照）。"""
    assert "CP-1" in context["cli_stdout"], f"大写 --plan-id 未归一命中 CP-1: {context['cli_stdout']!r}"


# ===================================================================
# Shared Helpers
# ===================================================================


def _parse_json_payload(context: dict[str, Any]) -> dict[str, Any]:
    """stdout JSON 解析（多行输出取首个 JSON 文档——json 格式化器单文档契约）。"""
    text = context["cli_stdout"].strip()
    assert text, "stdout 为空（期望 JSON 输出）"
    try:
        payload: dict[str, Any] = json.loads(text)
        return payload
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        assert start >= 0 and end > start, f"stdout 无 JSON 结构（{exc}）: {text!r}"
        try:
            fallback_payload: dict[str, Any] = json.loads(text[start : end + 1])
            return fallback_payload
        except json.JSONDecodeError:
            pytest.fail(f"stdout JSON 片段不可解析: {text!r}")


# ===================================================================
# AC-8: 性能与并发口径（Task 9 追加）
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "框架开销 P95 达标")
def test_framework_overhead_p95_within_budget(context: dict[str, Any]):
    """验证 20 轮 --dry-run 子进程直调采样 P95 < 500ms（NFR-IF-01 V1）。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "并发 10 个轻量命令全部成功")
def test_ten_concurrent_lightweight_commands_all_succeed(context: dict[str, Any]):
    """验证 10 并发轻量子进程（--help/--dry-run 面）全部 exit 0。"""
    pass


def _resolve_direct_command() -> list[str]:
    """子进程直调命令形态（R1-F6：.venv/bin/sisys 存在即用，缺失降级 python -m——禁 poetry run 包装）。"""
    venv_sisys = ROOT / ".venv" / "bin" / "sisys"
    if venv_sisys.is_file():
        return [str(venv_sisys)]
    import sys

    return [sys.executable, "-m", "src.entrypoints.main_cli"]


@when("采样 20 轮预览命令子进程直调耗时")
def sample_twenty_dry_run_subprocess_durations(context: dict[str, Any]):
    """20 轮 --dry-run 子进程直调采样（monotonic 差值测子进程 wall time——R3-8 规避墙钟回拨）。"""
    import math
    import subprocess
    import time

    sample_file = _make_temp_file(context, "# 采样\n")
    command = _resolve_direct_command()
    durations: list[float] = []
    for _ in range(20):
        start = time.monotonic()
        result = subprocess.run(
            [*command, "document", "upload", "--file", sample_file, "--dry-run"],
            capture_output=True,
            cwd=str(ROOT),
            timeout=30,
        )
        durations.append((time.monotonic() - start) * 1000.0)
        assert result.returncode == 0, f"采样命令异常退出: {result.returncode} stderr={result.stderr!r}"
    context["p95_durations"] = durations
    context["p95_ms"] = sorted(durations)[math.ceil(0.95 * len(durations)) - 1]


@then("P95 耗时小于 500 毫秒")
def verify_p95_within_500ms(context: dict[str, Any]):
    """P95 断言（升序第 ceil(0.95×20)=19 个 1-based——R3-8 钉死；NFR-IF-01 V1 <500ms）。"""
    assert context["p95_ms"] < 500.0, f"框架开销 P95={context['p95_ms']:.1f}ms 超 500ms 预算（采样={context['p95_durations']}）"


@when("并发执行 10 个轻量子进程命令")
def run_ten_concurrent_lightweight_subprocesses(context: dict[str, Any]):
    """10 并发轻量子进程（--help/--dry-run 面冻结——R1-F25：零 bootstrap 零服务依赖）。"""
    import concurrent.futures
    import subprocess

    sample_file = _make_temp_file(context, "# 并发采样\n")
    command = _resolve_direct_command()
    commands = [
        [*command, "--help"],
        [*command, "document", "upload", "--file", sample_file, "--dry-run"],
    ] * 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(
                subprocess.run,
                cmd,
                capture_output=True,
                cwd=str(ROOT),
                timeout=60,
            )
            for cmd in commands
        ]
        context["concurrent_exit_codes"] = [future.result().returncode for future in futures]


@then("全部退出码为 0")
def verify_all_concurrent_exit_zero(context: dict[str, Any]):
    """10 并发全部 exit 0 断言。"""
    codes = context["concurrent_exit_codes"]
    assert len(codes) == 10
    assert all(code == 0 for code in codes), f"并发存在非零退出: {codes}"


# ===================================================================
# 收尾完成清单（Task 9 追加）
# ===================================================================


@scenario("test_acceptance_unified_cli.feature", "src 完成清单逐项确认")
def test_src_completion_checklist(context: dict[str, Any]):
    """验证 File List 的 src 交付文件全部存在。"""
    pass


@scenario("test_acceptance_unified_cli.feature", "测试目录完成清单逐项确认")
def test_test_completion_checklist(context: dict[str, Any]):
    """验证 File List 的测试交付文件全部存在。"""
    pass


@then("src 交付文件全部存在")
def verify_src_completion_files(context: dict[str, Any]):
    """src 完成清单存在性断言（File List 对照——两 md 台账与故事文件不入断言面）。"""
    missing = [path for path in COMPLETION_SRC_FILES.values() if not (ROOT / path).is_file()]
    assert not missing, f"src 交付文件缺失: {missing}"


@then("测试交付文件全部存在")
def verify_test_completion_files(context: dict[str, Any]):
    """测试目录完成清单存在性断言。"""
    missing = [path for path in COMPLETION_TEST_FILES.values() if not (ROOT / path).is_file()]
    assert not missing, f"测试交付文件缺失: {missing}"
