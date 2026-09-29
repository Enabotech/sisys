"""Story 4.1e — 内部框架 Skills 验收测试（Acceptance Tests）

7 个纯内部框架 Skills（value-proposition-canvas / business-model-canvas /
org-design-framework / strategy-map / dependency-graph / raci-matrix /
gantt-chart）基于用户输入的内部业务信息输出结构化分析。

BDD 风格（范本 test_acceptance_skill_mixed_data.py）：
    - @scenario 显式绑定（每场景一个 test_* 函数，无 scenarios() 批量导入）
    - 步骤产物经场景级共享领域对象 execution 传递（无 target_fixture）
    - 场景级共享 event_loop + run_until_complete（禁止 @pytest.mark.asyncio）
    - LLM 按内容特征分派（prompt 含「生成代码」→ Code 阶段，非序数）
    - Fake 仅限 LLM/Sandbox 与 resolver cache 端口（真实 InMemorySkillLoader + 真实 ToolExecutionEngine）

纯内部型链路特点（与 4-1c/4-1d 的差异）：
    - 无 Redis 依赖：无标记主链路零 resolver 调用（引擎 :329-331 无标记快速返回）；
      207 场景的 resolver 为 fake cache 构造（白名单校验先于任何缓存/适配器访问）。
    - 用户内部输入的唯一数据通道 = ToolCall.arguments → Think prompt
      （f-string 注入 dict repr，特征串「规划执行步骤」）。
    - 注入沙箱代码不含 DATA_SOURCES 前言（无标记 → 零 preamble 注入）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.domain.entities.tool import Tool
from src.domain.exceptions import BusinessRuleViolationError
from src.domain.exceptions.base_exceptions import DomainError
from src.domain.ports.l1_cache import L1CachePort
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall, ToolResultStatus
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
from tests.unit.application.skills.skill_mixed_data_contracts import build_min_arguments

FEATURE: str = "test_acceptance_skill_framework.feature"

# 零标记分析代码（纯内部型 Code 阶段产物——SOP 引导沙箱代码不含任何 $DATA_SOURCE 标记）
_MARKER_FREE_CODE: str = 'result = {"summary": "基于内部业务输入的框架分析完成", "fit_score": 3, "findings": ["条目齐备"]}'

# 标记误用代码（模拟 SOP 误写 $DATA_SOURCE 标记——空白名单下应 207 安全失败）
_MISUSED_MARKER_CODE: str = 'data = $DATA_SOURCE("world-bank", "行业基准查询")'


class _SkillExecution:
    """Skill 执行上下文（场景级共享领域对象：given 装配、when 写入、then 读取）。"""

    def __init__(self) -> None:
        self.slug: str = ""
        self.metadata: Any = None  # ToolMetadata（真实 load_sop 解析的 frontmatter）
        self.documents: dict[str, Any] = {}  # 负向跳转场景的多文档缓存（slug → SkillDocument）
        self.result: Any = None  # ToolResult
        self.error: DomainError | None = None
        self.arguments: dict[str, Any] = {}
        self.prompts: list[str] = []
        self.sandbox_codes: list[str] = []


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    """真实进程内事件总线（207 场景 resolver 构造依赖）。"""
    return InMemoryEventBus()


@pytest.fixture
def execution() -> _SkillExecution:
    """场景级共享执行上下文（given 装配 → when 写入产物 → then 读取断言）。"""
    return _SkillExecution()


# ===================================================================
# Helpers
# ===================================================================


def _run_async(event_loop: Any, coro: Any) -> Any:
    """同步调度异步协程（BDD 步骤禁止 @pytest.mark.asyncio，共用场景级循环）。"""
    return event_loop.run_until_complete(coro)


def _make_llm(code: str, prompts: list[str]) -> AsyncMock:
    """Fake LLM：按内容特征分派（prompt 含「生成代码」→ Code 阶段返回注入代码）。

    全部 prompt 捕获留存（Think prompt 的 arguments repr 断言依据）。
    """

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        prompts.append(prompt)
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)
    return llm


def _make_sandbox(sandbox_codes: list[str]) -> AsyncMock:
    """Fake Sandbox：捕获注入后的代码（零 preamble 断言依据）。"""

    async def _sandbox_execute(session_id: str, code_arg: str, **_kwargs: Any) -> dict[str, Any]:
        sandbox_codes.append(code_arg)
        return {"status": "ok", "output": "done"}

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(side_effect=_sandbox_execute)
    sandbox.stop_container = AsyncMock()
    return sandbox


def _run_engine(
    execution: _SkillExecution,
    event_loop: Any,
    event_bus: InMemoryEventBus,
    code: str,
    arguments: dict[str, Any] | None = None,
) -> None:
    """驱动真实 Engine 执行（无 resolver 注入——纯内部型主链路零采集依赖）。

    extensions["tool_metadata"] 注入真实 load_sop 解析的 frontmatter——
    复刻 4-1c 双入口接线语义；产物写入 execution（结果/异常/prompt/沙箱代码）。
    """
    engine = ToolExecutionEngine(
        llm_client=_make_llm(code, execution.prompts),
        sandbox=_make_sandbox(execution.sandbox_codes),
    )
    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug=execution.slug)
    exec_context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": execution.metadata},
    )
    execution.arguments = arguments if arguments is not None else {}
    try:
        execution.result = _run_async(
            event_loop,
            engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=ToolCall(tool_id=tool.tool_id, arguments=execution.arguments),
                context=exec_context,
            ),
        )
        execution.error = None
    except DomainError as exc:  # BDD 异常断言统一入口（isinstance + code 在 Then 步骤校验）
        execution.result = None
        execution.error = exc


def _run_engine_with_resolver(
    execution: _SkillExecution,
    event_loop: Any,
    event_bus: InMemoryEventBus,
    code: str,
) -> None:
    """驱动真实 Engine + 真实 Resolver 执行含标记代码（207 场景）。

    resolver 构造同款 4-1c 验收（adapters={} + fake cache + 真实事件总线）：
    白名单校验先于任何缓存/适配器访问（data_source_resolver.fetch_many 逐源前置
    _check_whitelist），fake cache 不会被触达但 cache 为必填位置参数。
    """
    engine = ToolExecutionEngine(
        llm_client=_make_llm(code, execution.prompts),
        sandbox=_make_sandbox(execution.sandbox_codes),
    )
    resolver = DataSourceResolverService(
        adapters={},
        cache=AsyncMock(spec=L1CachePort),
        event_publisher=event_bus,
    )
    engine.set_data_source_resolver(resolver)
    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug=execution.slug)
    exec_context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": execution.metadata},
    )
    execution.arguments = {}
    try:
        execution.result = _run_async(
            event_loop,
            engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=ToolCall(tool_id=tool.tool_id, arguments=execution.arguments),
                context=exec_context,
            ),
        )
        execution.error = None
    except DomainError as exc:
        execution.result = None
        execution.error = exc


def _think_prompts(execution: _SkillExecution) -> list[str]:
    """提取 Think 阶段提示词（特征串「规划执行步骤」——tool_execution_engine :522）。"""
    think_prompts = [p for p in execution.prompts if "规划执行步骤" in p]
    assert think_prompts, f"未捕获到 Think 阶段提示词（捕获 {len(execution.prompts)} 条）"
    return think_prompts


# ===================================================================
# 场景绑定（@scenario 显式逐场景，无 scenarios() 批量导入）
# ===================================================================


@scenario(FEATURE, "value-proposition-canvas 内部数据经主通道驱动五阶段分析")
def test_value_proposition_canvas_internal_data_main_channel(execution: _SkillExecution) -> None:
    """vpc：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "business-model-canvas 内部数据经主通道驱动五阶段分析")
def test_business_model_canvas_internal_data_main_channel(execution: _SkillExecution) -> None:
    """bmc：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "org-design-framework 内部数据经主通道驱动五阶段分析")
def test_org_design_framework_internal_data_main_channel(execution: _SkillExecution) -> None:
    """org-design：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "strategy-map 内部数据经主通道驱动五阶段分析")
def test_strategy_map_internal_data_main_channel(execution: _SkillExecution) -> None:
    """strategy-map：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "dependency-graph 内部数据经主通道驱动五阶段分析")
def test_dependency_graph_internal_data_main_channel(execution: _SkillExecution) -> None:
    """dependency-graph：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "raci-matrix 内部数据经主通道驱动五阶段分析")
def test_raci_matrix_internal_data_main_channel(execution: _SkillExecution) -> None:
    """raci：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "gantt-chart 内部数据经主通道驱动五阶段分析")
def test_gantt_chart_internal_data_main_channel(execution: _SkillExecution) -> None:
    """gantt：arguments 主通道 + 零标记直通 + 空溯源全链路。"""
    pass


@scenario(FEATURE, "纯内部框架 Skill 空白名单安全失败")
def test_pure_internal_framework_skill_empty_whitelist_safe_failure(execution: _SkillExecution) -> None:
    """纯内部框架 Skill（data_sources 空 tuple）含标记 → 207 安全失败（永久设计态）。"""
    pass


@scenario(FEATURE, "内部数据不足时经模板缺口登记引导补全")
def test_insufficient_internal_data_gap_register_guidance(execution: _SkillExecution) -> None:
    """空 arguments → Think prompt 空 dict repr + SOP 缺口登记语义引导。"""
    pass


@scenario(FEATURE, "dependency-graph 与 gantt-chart 负向触发互相跳转")
def test_dependency_graph_gantt_chart_mutual_negative_trigger(execution: _SkillExecution) -> None:
    """纯拓扑 vs 含时间排程：两 Skill 负向触发章节互相指向。"""
    pass


@scenario(FEATURE, "strategy-map 与 bsc-scorecard 负向触发互相跳转")
def test_strategy_map_bsc_scorecard_mutual_negative_trigger(execution: _SkillExecution) -> None:
    """定性因果链 vs 定量计分卡：两 Skill 负向触发章节互相指向。"""
    pass


# ===================================================================
# 步骤实现
# ===================================================================


@given(parsers.parse('加载技能 "{slug}" 的 L2 技能元数据'))
def load_skill_metadata(execution: _SkillExecution, event_loop: Any, slug: str) -> None:
    """真实 load_sop 加载 SKILL.md，frontmatter 即空白名单依据。"""
    loader = InMemorySkillLoader()
    document = _run_async(event_loop, loader.load_sop(slug))
    execution.slug = slug
    execution.metadata = document.frontmatter
    execution.documents[slug] = document


@given("该技能 frontmatter 未声明任何外部数据源")
def verify_no_external_data_sources(execution: _SkillExecution) -> None:
    """纯内部型一等不变量：data_sources == ()（D1 决策——不写键解析为空 tuple）。"""
    assert execution.metadata is not None, "前置步骤未加载技能元数据"
    assert execution.metadata.data_sources == (), (
        f"{execution.slug}: 纯内部框架 Skill 不应声明任何外部数据源（实际 {execution.metadata.data_sources}）"
    )


@when("该技能携带内部数据参数执行且分析代码不含数据源标记")
def run_with_marker_free_code(execution: _SkillExecution, event_loop: Any, event_bus: InMemoryEventBus) -> None:
    """携带最小内部数据 arguments（yaml required 链程序化构造）执行零标记分析代码。"""
    _run_engine(
        execution,
        event_loop,
        event_bus,
        code=_MARKER_FREE_CODE,
        arguments=build_min_arguments(execution.slug),
    )


@when("该技能携带空内部数据参数执行")
def run_with_empty_arguments(execution: _SkillExecution, event_loop: Any, event_bus: InMemoryEventBus) -> None:
    """空 arguments（ToolCall.arguments 默认空 dict 合法）执行零标记分析代码。"""
    _run_engine(execution, event_loop, event_bus, code=_MARKER_FREE_CODE, arguments={})


@when(parsers.parse('代码含白名单外数据源 "{source}" 标记经 Engine Execute 阶段处理'))
def run_with_misused_marker(execution: _SkillExecution, event_loop: Any, event_bus: InMemoryEventBus, source: str) -> None:
    """SOP 误写标记场景模拟：含 $DATA_SOURCE 标记代码经真实 Engine + Resolver 处理。"""
    _run_engine_with_resolver(execution, event_loop, event_bus, code=_MISUSED_MARKER_CODE)


@then("执行结果为成功")
def verify_execution_success(execution: _SkillExecution) -> None:
    assert execution.error is None, f"执行失败: {execution.error}"
    assert execution.result is not None
    assert execution.result.status == ToolResultStatus.SUCCESS


@then("内部数据参数已进入规划提示词")
def verify_arguments_in_think_prompt(execution: _SkillExecution) -> None:
    """Think prompt 含 arguments 的 Python repr 子串（f-string 注入 dict 单引号形态）。"""
    think_prompts = _think_prompts(execution)
    assert repr(execution.arguments) in think_prompts[0], f"Think prompt 未包含内部数据参数 repr 子串: {think_prompts[0][:120]}"


@then("规划提示词包含空参数字典")
def verify_empty_arguments_in_think_prompt(execution: _SkillExecution) -> None:
    """空 arguments 场景：Think prompt 含空 dict repr（{}）。"""
    think_prompts = _think_prompts(execution)
    assert repr({}) in think_prompts[0], f"Think prompt 未包含空参数字典 repr: {think_prompts[0][:120]}"


@then("注入沙箱代码不含 DATA_SOURCES 前言")
def verify_no_data_sources_preamble(execution: _SkillExecution) -> None:
    """零标记 → 零 preamble 注入（与 4-1d 双通道并存语义的对照差异）。"""
    assert execution.sandbox_codes, "沙箱未收到代码（链路未到达 Execute 阶段）"
    for code in execution.sandbox_codes:
        assert not code.split("\n", 1)[0].startswith("DATA_SOURCES = "), (
            f"纯内部型链路不应注入 DATA_SOURCES 前言（实际首行: {code.splitlines()[0][:80]}）"
        )
        assert "$DATA_SOURCE" not in code, "纯内部型链路注入代码不应残留数据源标记"


@then("输出证据不含外部数据溯源")
def verify_evidence_empty_data_sources(execution: _SkillExecution) -> None:
    """零外部源不变量行为面：EvidencePackage.data_sources == ()。"""
    result = execution.result
    assert result is not None and result.evidence_package is not None
    assert result.evidence_package.data_sources == (), (
        f"纯内部型输出证据不应含外部数据溯源（实际 {result.evidence_package.data_sources}）"
    )


@then("技能 SOP 含数据缺口登记引导")
def verify_sop_gap_register_guidance(execution: _SkillExecution) -> None:
    """内部数据不足的文档级引导：SOP body 含数据缺口登记区与关键词。"""
    document = execution.documents.get(execution.slug)
    assert document is not None, "前置步骤未加载技能文档"
    assert "数据缺口登记" in document.body, f"{execution.slug}: SOP 缺少数据缺口登记引导区"
    assert "INSUFFICIENT_DATA" in document.body, f"{execution.slug}: SOP 缺少 INSUFFICIENT_DATA 语义引导"


@then("抛出 BusinessRuleViolationError")
def verify_business_rule_violation(execution: _SkillExecution) -> None:
    assert execution.error is not None, "预期抛出 BusinessRuleViolationError 但执行成功"
    assert isinstance(execution.error, BusinessRuleViolationError), f"异常类型不符: {type(execution.error).__name__}"


@then(parsers.parse("错误码为 EXCEPTION_{code:d}"))
def verify_error_code(execution: _SkillExecution, code: int) -> None:
    """error_code 逐字断言（4-1c R1-P1-1 判别力先例）。"""
    assert execution.error is not None, "预期异常未发生"
    assert execution.error.code == f"EXCEPTION_{code}", f"错误码不符: {execution.error.code} != EXCEPTION_{code}"


@then(parsers.parse('技能 "{source}" 的负向触发章节指向 "{target}"'))
def verify_negative_trigger_cross_reference(execution: _SkillExecution, source: str, target: str) -> None:
    """负向触发双向跳转：source 的 SOP §2 负向触发章节含 target slug 字面串。"""
    document = execution.documents.get(source)
    assert document is not None, f"前置步骤未加载技能 {source} 文档"
    section = document.body.split("负向触发", 1)[-1].split("\n## ", 1)[0]
    assert target in section, f"{source}: 负向触发章节未指向 {target}（分工跳转缺失）"
