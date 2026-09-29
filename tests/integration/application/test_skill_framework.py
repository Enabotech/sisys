"""内部框架型 Skills 集成测试（7 个 Skills 无标记全链路 + 207 误用守护 + 缺数据引导面）

真实服务链路：真实 ToolExecutionEngine + 真实 InMemorySkillLoader（load_sop 加载
真实 SKILL.md frontmatter——含成熟化 schema 双写断言）；Mock 仅限 LLM/Sandbox
（AsyncMock，LLM 按内容特征分派「生成代码」→ Code 阶段）。

纯内部型链路特点（与 4-1c/4-1d 集成测试的差异，D9 决策）：
- 无 Redis 依赖：无标记主链路零 resolver 调用（引擎 :329-331 无标记快速返回）；
  207 场景的 resolver 为 fake cache 构造（白名单校验先于任何缓存/适配器访问）
- 无 xdist_group 分组（无共享缓存键）
- 用户内部输入主通道：ToolCall.arguments → Think prompt（f-string 注入 dict repr，
  特征串「规划执行步骤」）
- 零外部源不变量行为面：注入沙箱代码不含 DATA_SOURCES 前言 +
  EvidencePackage.data_sources == ()

范本：tests/integration/application/test_skill_mixed_data.py（Story 4-1d）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.domain.entities.tool import Tool
from src.domain.exceptions.base_exceptions import DomainError
from src.domain.ports.l1_cache import L1CachePort
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall, ToolResultStatus
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
from tests.unit.application.skills.skill_framework_contracts import (
    FRAMEWORK_SKILL_SLUGS,
    assert_framework_data_sources_empty,
    assert_io_schema_contract,
    build_min_arguments,
)

pytestmark = [pytest.mark.integration]

# 零标记分析代码（纯内部型 Code 阶段产物——不含任何 $DATA_SOURCE 标记）
_MARKER_FREE_CODE: str = 'result = {"summary": "基于内部业务输入的框架分析完成", "fit_score": 3, "findings": ["条目齐备"]}'

# 标记误用代码（SOP 误写 $DATA_SOURCE 标记场景模拟——空白名单下应 207）
_MISUSED_MARKER_CODE: str = 'data = $DATA_SOURCE("world-bank", "行业基准查询")'


def _make_llm(code: str, prompts: list[str]) -> AsyncMock:
    """Fake LLM：按内容特征分派（prompt 含「生成代码」→ Code 阶段返回注入代码）。"""

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


class _FrameworkExecution:
    """执行产物收集器（结果/异常/prompt/沙箱代码）。"""

    def __init__(self) -> None:
        self.metadata: Any = None
        self.result: Any = None
        self.error: DomainError | None = None
        self.prompts: list[str] = []
        self.sandbox_codes: list[str] = []


def _build_engine(code: str, execution: _FrameworkExecution, *, with_resolver: bool) -> ToolExecutionEngine:
    """构建真实 Engine（可选注入真实 Resolver——207 场景前提）。

    resolver 构造同款 4-1c 验收（adapters={} + fake cache + 真实事件总线）：
    cache 为必填位置参数但白名单校验先于缓存访问（fake 不会被触达）。
    """
    engine = ToolExecutionEngine(
        llm_client=_make_llm(code, execution.prompts),
        sandbox=_make_sandbox(execution.sandbox_codes),
    )
    if with_resolver:
        resolver = DataSourceResolverService(
            adapters={},
            cache=AsyncMock(spec=L1CachePort),
            event_publisher=InMemoryEventBus(),
        )
        engine.set_data_source_resolver(resolver)
    return engine


async def _run_framework_skill(
    slug: str,
    code: str,
    arguments: dict[str, Any] | None = None,
    *,
    with_resolver: bool = False,
) -> _FrameworkExecution:
    """驱动真实 Engine 执行（真实 load_sop 白名单 + extensions 注入）。

    仅捕获 DomainError（异常是领域契约：非领域异常逃逸直接使测试红）。
    """
    loader = InMemorySkillLoader()
    document = await loader.load_sop(slug)
    execution = _FrameworkExecution()
    execution.metadata = document.frontmatter
    engine = _build_engine(code, execution, with_resolver=with_resolver)
    tool = Tool(tool_id=uuid.uuid4(), name="集成测试工具", slug=slug)
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=f"it-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": document.frontmatter},
    )
    try:
        execution.result = await engine.execute(
            tool_id=tool.tool_id,
            tool=tool,
            tool_call=ToolCall(tool_id=tool.tool_id, arguments=arguments if arguments is not None else {}),
            context=context,
        )
        execution.error = None
    except DomainError as exc:
        execution.result = None
        execution.error = exc
    return execution


def _think_prompt(execution: _FrameworkExecution) -> str:
    """提取 Think 阶段提示词（特征串「规划执行步骤」——engine :521-522 f-string 注入）。"""
    think_prompts = [p for p in execution.prompts if "规划执行步骤" in p]
    assert think_prompts, f"未捕获到 Think 阶段提示词（捕获 {len(execution.prompts)} 条）"
    return think_prompts[0]


class TestMarkerFreeFullChain:
    """[A] 无标记全链路（7 Skill 参数化：内部数据主通道 + 零 preamble + 空溯源）。"""

    @pytest.mark.parametrize("slug", FRAMEWORK_SKILL_SLUGS)
    async def test_skill_full_chain_internal_data_main_channel(self, slug: str) -> None:
        """零标记分析代码 → SUCCESS + arguments repr 进 Think prompt + 零 preamble + 空溯源。"""
        arguments = build_min_arguments(slug)
        execution = await _run_framework_skill(slug, _MARKER_FREE_CODE, arguments=arguments)

        assert execution.error is None, f"执行失败: {execution.error}"
        assert execution.result is not None
        assert execution.result.status == ToolResultStatus.SUCCESS
        # arguments 主通道：Think prompt 含 dict repr 子串（f-string 单引号形态）
        assert repr(arguments) in _think_prompt(execution), "Think prompt 未包含内部数据参数 repr 子串"
        # 零 preamble：注入沙箱代码不含 DATA_SOURCES 前言与标记残留
        assert execution.sandbox_codes, "沙箱未收到代码（链路未到达 Execute 阶段）"
        for code in execution.sandbox_codes:
            assert not code.split("\n", 1)[0].startswith("DATA_SOURCES = "), "纯内部型链路不应注入 DATA_SOURCES 前言"
            assert "$DATA_SOURCE" not in code, "纯内部型链路注入代码不应残留数据源标记"
        # 零外部源不变量行为面：evidence 空溯源
        assert execution.result.evidence_package is not None
        assert execution.result.evidence_package.data_sources == (), "纯内部型输出证据不应含外部数据溯源"

    @pytest.mark.parametrize("slug", FRAMEWORK_SKILL_SLUGS)
    async def test_skill_metadata_matured_from_real_sop(self, slug: str) -> None:
        """链路消费的 tool_metadata 来自真实成熟 frontmatter（schema 双写 + 空声明）。"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        assert_framework_data_sources_empty(slug, document)
        assert_io_schema_contract(slug, document.frontmatter)


class TestMarkerMisuseGuard:
    """[B] 207 误用守护（resolver 注入前提 + 101 对照负例）。"""

    async def test_marker_code_with_resolver_raises_207(self) -> None:
        """空白名单 + 标记代码 + resolver 注入 → EXCEPTION_207 逐字（白名单校验前置）。"""
        execution = await _run_framework_skill("business-model-canvas", _MISUSED_MARKER_CODE, with_resolver=True)
        assert execution.error is not None, "预期 207 异常但执行成功"
        assert execution.error.code == "EXCEPTION_207", f"error_code 不符: {execution.error.code} != EXCEPTION_207"

    async def test_marker_code_without_resolver_raises_101(self) -> None:
        """判别力负例：同一标记代码 + resolver 未注入 → EXCEPTION_101（非 207）。

        引擎 :333-337——标记存在 + resolver 缺失先于白名单校验 fail-fast。
        """
        execution = await _run_framework_skill("business-model-canvas", _MISUSED_MARKER_CODE, with_resolver=False)
        assert execution.error is not None, "预期 101 异常但执行成功"
        assert execution.error.code == "EXCEPTION_101", (
            f"error_code 不符: {execution.error.code} != EXCEPTION_101（应先于白名单校验 fail-fast）"
        )


class TestInsufficientDataGuidance:
    """[B] 缺数据引导面（空 arguments → Think prompt 空 dict repr；文档级语义归 AC-2）。"""

    @pytest.mark.parametrize("slug", FRAMEWORK_SKILL_SLUGS[:1])
    async def test_empty_arguments_empty_dict_in_think_prompt(self, slug: str) -> None:
        """空 arguments（ToolCall.arguments 默认空 dict 合法）→ Think prompt 含 {}。"""
        execution = await _run_framework_skill(slug, _MARKER_FREE_CODE, arguments={})
        assert execution.error is None, f"空 arguments 执行失败: {execution.error}"
        assert execution.result is not None
        assert execution.result.status == ToolResultStatus.SUCCESS
        think_prompt = _think_prompt(execution)
        assert repr({}) in think_prompt, f"Think prompt 未包含空参数字典 repr: {think_prompt[:120]}"
        # 引擎行为基线：ToolResultStatus 生产零 INSUFFICIENT_DATA 设置点（:209 硬编码
        # SUCCESS）——内部数据不足的引导语义由 SOP 失败处理章节文档级承载（AC-2）
        assert execution.result.status != "insufficient_data"
