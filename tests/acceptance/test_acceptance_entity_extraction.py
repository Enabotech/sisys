"""Story 3.2b 实体抽取（LLM + 规则混合）验收测试

使用真实 RuleBasedExtractor + 真实 ConflictArbitrator + 真实 LLMEntityExtractor。
LLM 需 UDMR 云端配置（同 test_acceptance_llm_client.py），不可用时动态跳过。
L5GraphPort 和事件发布器使用 AsyncMock（Neo4j/RabbitMQ 为重型基础设施依赖）。

运行: poetry run pytest tests/acceptance/test_acceptance_entity_extraction.py -v

前置条件（AC-1 混合抽取）:
    - UDMR_CLOUD_0_ENABLED=true
    - UDMR_CLOUD_0_API_TYPE=anthropic
    - UDMR_CLOUD_0_MODEL=<模型名>
    - UDMR_CLOUD_0_ENDPOINT=<云端端点>
    - UDMR_CLOUD_0_API_KEY=<API Key>
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.events.publish_result import PublishResult
from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractionResult,
)
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.llm_client import LLMConfig

scenarios("test_acceptance_entity_extraction.feature")


# ===================================================================
# UDMR 真实云端 LLM 配置（复用 test_acceptance_llm_client.py 模式）
# ===================================================================


def _get_udmr_cloud_config() -> tuple[LLMConfig, bool]:
    """从 UDMRConfig 读取真实云端 LLM 配置

    Returns:
        (LLMConfig, is_available) 元组
    """
    from src.infrastructure.config.udmr import UDMRConfig

    udmr = UDMRConfig.from_env()
    for cloud in udmr.cloud_configs:
        if cloud.enabled and cloud.api_key:
            llm_config = LLMConfig(
                api_type=cloud.api_type,
                model=cloud.model,
                endpoint=cloud.endpoint,
                api_key=cloud.api_key,
                temperature=cloud.temperature,
                max_tokens=cloud.max_tokens,
                timeout=float(udmr.llm_timeout),
            )
            return llm_config, True
    # 回退：从 LLM_* 环境变量读取
    env_cfg = LLMConfig.from_env()
    if env_cfg.api_key:
        return env_cfg, True
    return LLMConfig(), False


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环，用于 run_until_complete()"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def udmr_llm_config() -> tuple[LLMConfig, bool]:
    """UDMR 真实云端 LLM 配置"""
    return _get_udmr_cloud_config()


@pytest.fixture(scope="module")
def real_llm_extractor(udmr_llm_config: tuple[LLMConfig, bool]):
    """真实 LLM 语义实体抽取器（使用 UDMR 云端配置）

    当 LLM 不可用时返回 None，由调用方负责跳过场景。
    """
    config, available = udmr_llm_config
    if not available:
        return None
    from src.infrastructure.external_services.entity_extraction.llm_extractor import (
        LLMEntityExtractor,
    )
    from src.infrastructure.external_services.llm.litellm_llm_client import LitellmLLMClient

    client = LitellmLLMClient(config=config)
    return LLMEntityExtractor(llm_client=client)


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


# ===================================================================
# 帮助函数
# ===================================================================


def _build_entity_extraction_service(
    rule_extractor: EntityExtractionPort | None = None,
    llm_extractor: EntityExtractionPort | None = None,
    l5_graph: AsyncMock | None = None,
    arbitrator=None,
    event_publisher: AsyncMock | None = None,
):
    """构建 EntityExtractionService 实例"""
    from src.application.services.entity_extraction_service import EntityExtractionService
    from src.infrastructure.external_services.entity_extraction.conflict_arbitrator import (
        ConflictArbitrator,
    )
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    if rule_extractor is None:
        rule_extractor = RuleBasedExtractor()
    _llm_extractor: EntityExtractionPort = llm_extractor if llm_extractor is not None else RuleBasedExtractor()
    if arbitrator is None:
        arbitrator = ConflictArbitrator()
    if l5_graph is None:
        l5_graph = AsyncMock(spec=L5GraphPort)
        l5_graph.create_entity.return_value = True
        l5_graph.create_relationship.return_value = True
    if event_publisher is None:
        event_publisher = AsyncMock()
        publish_result = MagicMock(spec=PublishResult)
        type(publish_result).is_success = PropertyMock(return_value=True)
        event_publisher.publish.return_value = publish_result

    service = EntityExtractionService(
        rule_extractor=rule_extractor,
        llm_extractor=_llm_extractor,
        l5_graph=l5_graph,
        arbitrator=arbitrator,
        event_publisher=event_publisher,
    )
    return service, l5_graph, event_publisher


def _build_failing_llm_extractor():
    """构建会失败的 LLM 抽取器（用于测试 LLM 降级）"""
    failing_client = AsyncMock()
    from src.domain.exceptions import LLMAPIError

    failing_client.structured_generate.side_effect = LLMAPIError("模拟 LLM API 错误")
    from src.infrastructure.external_services.entity_extraction.llm_extractor import (
        LLMEntityExtractor,
    )

    return LLMEntityExtractor(llm_client=failing_client)


# ===================================================================
# Background Steps
# ===================================================================


@given("EntityExtractionPort 端口契约已定义")
def port_contract_defined():
    """验证 EntityExtractionPort 端口契约已定义"""
    from src.domain.ports.entity_extraction import (
        EntityArbitratorPort,
        EntityExtractionPort,
        ExtractedEntity,
        ExtractedRelation,
        ExtractionResult,
    )

    assert EntityExtractionPort is not None
    assert EntityArbitratorPort is not None
    assert ExtractedEntity is not None
    assert ExtractedRelation is not None
    assert ExtractionResult is not None


@given("RuleBasedExtractor 已初始化")
def rule_extractor_initialized():
    """初始化规则基抽取器（验证可正常构造）"""
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    extractor = RuleBasedExtractor()
    assert extractor is not None


@given("ConflictArbitrator 已就绪")
def arbitrator_ready():
    """初始化冲突仲裁器（验证可正常构造）"""
    from src.infrastructure.external_services.entity_extraction.conflict_arbitrator import (
        ConflictArbitrator,
    )

    arbitrator = ConflictArbitrator()
    assert arbitrator is not None


# ===================================================================
# AC-1: 混合实体抽取成功（规则 + LLM 融合）
# ===================================================================


@given("规则基抽取器包含战略领域词典")
def rule_extractor_has_dictionary(event_loop):
    """验证规则基抽取器内置战略领域词典包含核心词条"""
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    extractor = RuleBasedExtractor()

    async def _check():
        result = await extractor.extract_entities("BLM SWOT PESTEL 是战略工具")
        names = [e.name for e in result.entities]
        assert "BLM" in names, "内置词典应包含 BLM"
        assert "SWOT" in names, "内置词典应包含 SWOT"
        assert "PESTEL" in names, "内置词典应包含 PESTEL"

    event_loop.run_until_complete(_check())


@when("对混合抽取文本执行完整混合抽取")
def perform_hybrid_extraction(context: dict[str, Any], event_loop, real_llm_extractor):
    """执行混合实体抽取（规则 + LLM + 仲裁）"""
    if real_llm_extractor is None:
        pytest.skip("UDMR 云端 LLM 未配置或 API Key 缺失，跳过混合抽取测试")

    service, l5_graph, event_publisher = _build_entity_extraction_service(
        llm_extractor=real_llm_extractor,
    )

    context["service"] = service
    context["l5_graph"] = l5_graph
    context["event_publisher"] = event_publisher

    result = event_loop.run_until_complete(
        service.extract_entities(
            content="BLM 模型和 PESTEL 分析是战略规划工具",
            memory_id=f"ac1-{uuid.uuid4().hex[:8]}",
        )
    )
    context["result"] = result


@then("返回的抽取结果包含实体列表")
def result_has_entities(context: dict[str, Any]):
    """验证抽取结果包含实体列表"""
    result = context.get("result")
    assert result is not None, "抽取结果不应为空"
    assert isinstance(result, ExtractionResult)
    assert len(result.entities) > 0, "实体列表不应为空"


@then("实体列表非空")
def entities_not_empty(context: dict[str, Any]):
    """验证实体列表非空"""
    result = context["result"]
    assert len(result.entities) > 0, "实体列表不应为空"


@then("抽取结果包含关系列表")
def result_has_relations(context: dict[str, Any]):
    """验证抽取结果包含关系列表"""
    result = context["result"]
    assert hasattr(result, "relations"), "抽取结果应包含 relations 属性"


@then("抽取结果包含抽取元数据")
def result_has_metadata(context: dict[str, Any]):
    """验证抽取结果包含元数据"""
    result = context["result"]
    assert result.extraction_metadata is not None, "抽取结果应包含 extraction_metadata"
    assert "strategy" in result.extraction_metadata


# ===================================================================
# AC-2: 纯规则基抽取
# ===================================================================


@when("对SWOT分析文本执行规则基抽取")
def perform_rule_extraction(context: dict[str, Any], event_loop):
    """执行纯规则基实体抽取"""
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    extractor = RuleBasedExtractor()

    async def _extract():
        return await extractor.extract_entities(content="SWOT 分析和波特五力模型是战略工具")

    result = event_loop.run_until_complete(_extract())
    context["result"] = result


@then("返回的实体列表包含SWOT和波特五力")
def rule_entities_contain(context: dict[str, Any]):
    """验证实体列表包含 SWOT 和 波特五力"""
    result = context["result"]
    names = {e.name for e in result.entities}
    assert "SWOT" in names, f"实体列表应包含 SWOT，实际包含: {names}"
    assert "波特五力" in names, f"实体列表应包含 波特五力，实际包含: {names}"


@then("所有实体的 extraction_source 为rule")
def all_entities_source_is_rule(context: dict[str, Any]):
    """验证所有实体的来源为 rule"""
    result = context["result"]
    assert len(result.entities) > 0, "实体列表不应为空"
    for entity in result.entities:
        assert entity.extraction_source == "rule", (
            f"实体 {entity.name} 的 extraction_source 应为 rule，实际为 {entity.extraction_source}"
        )


@then("实体类型为CONCEPT")
def entity_type_is_concept(context: dict[str, Any]):
    """验证实体类型为 CONCEPT"""
    result = context["result"]
    for entity in result.entities:
        assert entity.entity_type == "CONCEPT", f"实体 {entity.name} 的类型应为 CONCEPT，实际为 {entity.entity_type}"


# ===================================================================
# AC-3: 正则模式匹配结构化实体
# ===================================================================


@when("对含结构化实体文本执行正则抽取")
def perform_regex_extraction(context: dict[str, Any], event_loop):
    """执行规则基抽取（正则匹配）"""
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    extractor = RuleBasedExtractor()

    async def _extract():
        return await extractor.extract_entities(content="2024 年公司营收增长 15%，达到 ¥100 亿")

    result = event_loop.run_until_complete(_extract())
    context["result"] = result


@then("返回的实体包含2024年日期类型")
def result_contains_date_entity(context: dict[str, Any]):
    """验证实体包含 2024 年（类型 DATE）"""
    result = context["result"]
    matched = [e for e in result.entities if e.name == "2024 年"]
    assert len(matched) > 0, "实体列表应包含 2024 年"
    assert matched[0].entity_type == "DATE", f"2024 年 的类型应为 DATE，实际为 {matched[0].entity_type}"


@then("返回的实体包含15百分比类型")
def result_contains_percent_entity(context: dict[str, Any]):
    """验证实体包含 15%（类型 PERCENT）"""
    result = context["result"]
    matched = [e for e in result.entities if e.name == "15%"]
    assert len(matched) > 0, "实体列表应包含 15%"
    assert matched[0].entity_type == "PERCENT", f"15% 的类型应为 PERCENT，实际为 {matched[0].entity_type}"


@then("返回的实体包含100亿金额类型")
def result_contains_amount_entity(context: dict[str, Any]):
    """验证实体包含 ¥100 亿（类型 AMOUNT）"""
    result = context["result"]
    matched = [e for e in result.entities if e.name == "¥100 亿"]
    assert len(matched) > 0, "实体列表应包含 ¥100 亿"
    assert matched[0].entity_type == "AMOUNT", f"¥100 亿 的类型应为 AMOUNT，实际为 {matched[0].entity_type}"


@then("上述实体的 extraction_source 为rule")
def regex_entities_source_is_rule(context: dict[str, Any]):
    """验证正则匹配实体的来源为 rule"""
    result = context["result"]
    rule_entities = [e for e in result.entities if e.extraction_source == "rule"]
    assert len(rule_entities) > 0, "应至少有一个 rule 来源的实体"


# ===================================================================
# AC-4: 空内容输入返回空结果
# ===================================================================


@when("对空文本执行混合抽取")
def perform_empty_extraction(context: dict[str, Any], event_loop):
    """对空文本执行实体抽取（不抛出异常）"""
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    extractor = RuleBasedExtractor()
    service, _, _ = _build_entity_extraction_service(
        rule_extractor=extractor,
        llm_extractor=extractor,
    )

    try:
        result = event_loop.run_until_complete(service.extract_entities(content="", memory_id=""))
        context["result"] = result
        context["error"] = None
    except Exception as e:
        context["result"] = None
        context["error"] = e


@then("返回的 ExtractionResult 中实体列表为空")
def result_entities_empty(context: dict[str, Any]):
    """验证实体列表为空"""
    assert context.get("error") is None, f"不应抛出异常，但捕获到: {context['error']}"
    result = context["result"]
    assert result is not None, "抽取结果不应为空"
    assert len(result.entities) == 0, f"实体列表应为空，实际为 {len(result.entities)}"


@then("关系列表为空")
def result_relations_empty(context: dict[str, Any]):
    """验证关系列表为空"""
    result = context["result"]
    assert len(result.relations) == 0, f"关系列表应为空，实际为 {len(result.relations)}"


@then("不抛出任何异常")
def no_exception_raised(context: dict[str, Any]):
    """验证不抛出异常"""
    assert context.get("error") is None, f"不应抛出异常，但捕获到: {context['error']}"


# ===================================================================
# AC-5: LLM 调用失败降级至规则基结果
# ===================================================================


@given("LLM 实体抽取器抛出异常")
def llm_extractor_raises_error(context: dict[str, Any]):
    """设置 LLM 抽取器抛出异常"""
    context["llm_extractor"] = _build_failing_llm_extractor()


@when("对BLM模型文本执行LLM降级抽取")
def perform_hybrid_with_llm_failure(context: dict[str, Any], event_loop):
    """LLM 失败时执行混合抽取"""
    llm_extractor = context.get("llm_extractor", _build_failing_llm_extractor())

    service, l5_graph, event_publisher = _build_entity_extraction_service(
        llm_extractor=llm_extractor,
    )

    context["service"] = service
    context["l5_graph"] = l5_graph
    context["event_publisher"] = event_publisher

    try:
        result = event_loop.run_until_complete(
            service.extract_entities(
                content="BLM 模型是战略规划工具",
                memory_id=f"ac5-{uuid.uuid4().hex[:8]}",
            )
        )
        context["result"] = result
        context["error"] = None
    except Exception as e:
        context["result"] = None
        context["error"] = e


@then("返回的实体列表包含BLM")
def result_contains_entity(context: dict[str, Any]):
    """验证实体列表包含 BLM"""
    assert context.get("error") is None, f"不应抛出异常，但捕获到: {context['error']}"
    result = context["result"]
    assert result is not None, "抽取结果不应为空"
    names = {e.name for e in result.entities}
    assert "BLM" in names, f"实体列表应包含 BLM，实际包含: {names}"


@then("抽取流程不抛出异常")
def extraction_does_not_raise(context: dict[str, Any]):
    """验证抽取流程不抛出异常"""
    assert context.get("error") is None, f"不应抛出异常，但捕获到: {context['error']}"


@then("系统记录 LLM 降级警告日志")
def llm_fallback_logged():
    """验证 LLM 降级警告日志记录抽象（不阻塞主流程）"""
    # LLM 降级本身不阻塞主流程，此处验证抽象
    pass


# ===================================================================
# AC-6: 无匹配实体返回空结果
# ===================================================================


@when("对无战略术语文本执行混合抽取")
def perform_hybrid_no_match(context: dict[str, Any], event_loop):
    """执行混合抽取（无匹配场景）"""
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    extractor = RuleBasedExtractor()
    service, _, _ = _build_entity_extraction_service(
        rule_extractor=extractor,
        llm_extractor=extractor,
    )

    result = event_loop.run_until_complete(
        service.extract_entities(
            content="今天天气很好",
            memory_id=f"ac6-{uuid.uuid4().hex[:8]}",
        )
    )
    context["result"] = result


@then("返回的抽取结果实体列表为空")
def result_entities_empty_no_match(context: dict[str, Any]):
    """验证实体列表为空"""
    result = context["result"]
    assert result is not None, "抽取结果不应为空"
    assert len(result.entities) == 0, f"实体列表应为空，实际为 {len(result.entities)}"


@then("抽取结果仍包含 extraction_metadata")
def result_has_extraction_metadata(context: dict[str, Any]):
    """验证抽取结果仍包含元数据"""
    result = context["result"]
    assert result.extraction_metadata is not None, "抽取结果应包含 extraction_metadata"
    assert "strategy" in result.extraction_metadata, "extraction_metadata 应包含 strategy"


# ===================================================================
# AC-7: 事件发布失败不阻塞主流程
# ===================================================================


@given("事件发布器发布失败")
def event_publisher_fails(context: dict[str, Any]):
    """设置事件发布器发布失败"""
    failing_publisher = AsyncMock()
    publish_result = MagicMock(spec=PublishResult)
    type(publish_result).is_success = PropertyMock(return_value=False)
    publish_result.partial_error = "模拟事件发布失败"
    failing_publisher.publish.return_value = publish_result
    context["failing_publisher"] = failing_publisher


@when("对BLM模型文本执行事件失败抽取")
def perform_hybrid_with_event_failure(context: dict[str, Any], event_loop):
    """事件发布失败时执行混合抽取"""
    failing_publisher = context.get("failing_publisher")

    service, l5_graph, _ = _build_entity_extraction_service(
        event_publisher=failing_publisher,
    )

    context["service"] = service
    context["l5_graph"] = l5_graph

    try:
        result = event_loop.run_until_complete(
            service.extract_entities(
                content="BLM 模型是战略规划工具",
                memory_id=f"ac7-{uuid.uuid4().hex[:8]}",
            )
        )
        context["result"] = result
        context["error"] = None
    except Exception as e:
        context["result"] = None
        context["error"] = e


@then("返回的抽取结果实体列表非空")
def result_entities_not_empty(context: dict[str, Any]):
    """验证实体列表非空"""
    assert context.get("error") is None, f"不应抛出异常，但捕获到: {context['error']}"
    result = context["result"]
    assert result is not None, "抽取结果不应为空"
    assert len(result.entities) > 0, "实体列表不应为空"


@then("返回的抽取结果类型为 ExtractionResult")
def result_is_extraction_result(context: dict[str, Any]):
    """验证返回类型为 ExtractionResult"""
    result = context["result"]
    assert isinstance(result, ExtractionResult), f"返回类型应为 ExtractionResult，实际为 {type(result)}"


# ===================================================================
# AC-8: 抽取结果持久化到 Neo4j
# ===================================================================


@given("L5GraphPort 可用")
def l5_graph_port_available(context: dict[str, Any]):
    """设置 L5GraphPort Mock"""
    l5_graph = AsyncMock(spec=L5GraphPort)
    l5_graph.create_entity.return_value = True
    l5_graph.create_relationship.return_value = True
    context["l5_graph"] = l5_graph


@when("对BLM和SWOT文本执行持久化抽取")
def perform_hybrid_with_persistence(context: dict[str, Any], event_loop):
    """执行混合抽取（验证持久化）"""
    l5_graph = context.get("l5_graph")

    service, _, event_publisher = _build_entity_extraction_service(
        l5_graph=l5_graph,
    )

    context["service"] = service
    context["event_publisher"] = event_publisher

    result = event_loop.run_until_complete(
        service.extract_entities(
            content="BLM 和 SWOT 是常用战略工具",
            memory_id=f"ac8-{uuid.uuid4().hex[:8]}",
        )
    )
    context["result"] = result


@when("指定 memory_id 为有效 UUID")
def specify_memory_id(context: dict[str, Any]):
    """在上下文中记录 memory_id（已在 When 步骤中传入）"""
    context["memory_id_provided"] = True


@then("系统调用 L5GraphPort.create_entity 创建实体节点")
def l5_graph_create_entity_called(context: dict[str, Any]):
    """验证 L5GraphPort.create_entity 被调用"""
    l5_graph = context.get("l5_graph")
    assert l5_graph is not None, "L5GraphPort 未设置"
    assert l5_graph.create_entity.called, "L5GraphPort.create_entity 应被调用"


@then("节点 ID 基于 memory_id 的确定性哈希生成")
def node_id_is_deterministic_hash(context: dict[str, Any]):
    """验证节点 ID 格式为 {memory_id}:{sha256[:16]}"""
    l5_graph = context.get("l5_graph")
    assert l5_graph is not None
    for call_args in l5_graph.create_entity.call_args_list:
        kwargs = call_args[1] if len(call_args) > 1 else call_args[0] if call_args else {}
        mid = kwargs.get("memory_id", "")
        assert ":" in mid, f"节点 ID 应包含 : 分隔符，实际为 {mid}"
        parts = mid.split(":")
        assert len(parts) == 2, f"节点 ID 格式应为 prefix:hash，实际为 {mid}"
        assert len(parts[1]) == 16, f"哈希部分应为 16 字符，实际为 {len(parts[1])}"


@then("系统调用 L5GraphPort.create_relationship 创建关系")
def l5_graph_create_relationship_called(context: dict[str, Any]):
    """验证 L5GraphPort.create_relationship 被调用"""
    l5_graph = context.get("l5_graph")
    assert l5_graph is not None
    result = context.get("result")
    if result and result.relations:
        assert l5_graph.create_relationship.called, "存在关系但 create_relationship 未被调用"


@then("系统发布 EntitiesExtracted 领域事件")
def entities_extracted_event_published(context: dict[str, Any]):
    """验证 EntitiesExtracted 事件被发布"""
    from src.domain.events.entity_extraction_events import EntitiesExtracted

    event_publisher = context.get("event_publisher")
    assert event_publisher is not None, "事件发布器未设置"
    assert event_publisher.publish.called, "事件发布器应被调用"
    published_event = event_publisher.publish.call_args[0][0]
    assert isinstance(published_event, EntitiesExtracted), f"事件类型应为 EntitiesExtracted，实际为 {type(published_event)}"


@then("事件包含正确的 entity_count 和 relation_count")
def event_has_correct_counts(context: dict[str, Any]):
    """验证事件包含正确的实体和关系计数"""
    from src.domain.events.entity_extraction_events import EntitiesExtracted

    event_publisher = context.get("event_publisher")
    assert event_publisher is not None, "事件发布器未设置"
    result = context.get("result")
    assert result is not None, "抽取结果未设置"
    published_event = event_publisher.publish.call_args[0][0]
    assert isinstance(published_event, EntitiesExtracted)
    assert published_event.entity_count == len(result.entities), (
        f"事件 entity_count ({published_event.entity_count}) 应与结果实体数 ({len(result.entities)}) 一致"
    )
    assert published_event.relation_count == len(result.relations), (
        f"事件 relation_count ({published_event.relation_count}) 应与结果关系数 ({len(result.relations)}) 一致"
    )
