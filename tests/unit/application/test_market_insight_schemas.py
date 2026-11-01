"""Story 6-2 — 六类型化 Schema / SSOT 映射 / gap 四字段传导单元测试。

TDD 循环 A 载体：六 Schema 字段完备性（期望字段族【独立构造】自 Task 0.1
冻结表——禁 import Schema 后反射自证恒真）；扁平形态（str/float/list[str]
白名单——与 Task 6 架构验证器 C 双承载）；公共 summary+findings 双公共字段
（信封同源——R3-1）；Field description 非空。

TDD 循环 B 载体：MARKET_INSIGHT_STEP_SCHEMA SSOT 映射（形态 A 独立 dict
——六枚举键齐备且值互异）；summarize_gap_for_downstream 四字段全量扩展
（「财务差距=」子串兼容——R2-3）与降级标注零回归。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/application/test_market_insight_schemas.py -v
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.application.services.blm_planning_prompts import (
    DEGRADATION_MARKER_PREFIX,
    MARKET_INSIGHT_STEP_SCHEMA,
    CompetitionInsightSchema,
    GapAnalysisSchema,
    MarketCustomerInsightSchema,
    OpportunityGapInsightSchema,
    OpportunityInsightSchema,
    SelfInsightSchema,
    TrendInsightSchema,
    summarize_gap_for_downstream,
)
from src.domain.value_objects.blm_phases import MarketInsightStep, PerformanceGapArtifacts

# ===================================================================
# 期望字段族（独立构造自 Task 0.1 冻结表——字面量，禁经被测 Schema 反射生成）
# ===================================================================

#: 六步领域要素字段族（不含公共双字段——公共字段独立组断言）
EXPECTED_DOMAIN_FIELDS: dict[str, frozenset[str]] = {
    "trend": frozenset(
        {
            "pestel_political",
            "pestel_economic",
            "pestel_social",
            "pestel_technological",
            "pestel_environmental",
            "pestel_legal",
            "technology_roadmap",
            "scenario_plans",
        }
    ),
    "market_customer": frozenset({"customer_segments", "demand_priority_matrix", "value_proposition_map"}),
    "competition": frozenset(
        {
            "five_forces_supplier_power",
            "five_forces_buyer_power",
            "five_forces_new_entrants",
            "five_forces_substitutes",
            "five_forces_rivalry",
            "competitor_radar",
            "strategy_recommendations",
        }
    ),
    "self": frozenset({"internal_capabilities", "vrio_assessment", "resource_constraints"}),
    "opportunity": frozenset({"opportunity_list", "priority_ranking", "growth_path"}),
    "opportunity_gap": frozenset({"gap_quantification", "capability_match_matrix", "closure_strategies"}),
}

#: 公共双字段（信封同源——R3-1 钦定）
COMMON_FIELDS: frozenset[str] = frozenset({"summary", "findings"})

#: 枚举值 → Schema 类期望映射（SSOT 映射断言锚——独立构造）
EXPECTED_SCHEMA_BY_STEP: dict[str, type] = {
    "trend": TrendInsightSchema,
    "market_customer": MarketCustomerInsightSchema,
    "competition": CompetitionInsightSchema,
    "self": SelfInsightSchema,
    "opportunity": OpportunityInsightSchema,
    "opportunity_gap": OpportunityGapInsightSchema,
}

#: 六类型化 Schema 全集（类型白名单/公共字段/描述符反射遍历载体）。
#: 元素类型用具体联合注解（bare type 会丢失 model_fields 属性可见性——R1 修复）
TYPED_SCHEMA_UNION = (
    type[TrendInsightSchema]
    | type[MarketCustomerInsightSchema]
    | type[CompetitionInsightSchema]
    | type[SelfInsightSchema]
    | type[OpportunityInsightSchema]
    | type[OpportunityGapInsightSchema]
)
ALL_TYPED_SCHEMAS: tuple[TYPED_SCHEMA_UNION, ...] = (
    TrendInsightSchema,
    MarketCustomerInsightSchema,
    CompetitionInsightSchema,
    SelfInsightSchema,
    OpportunityInsightSchema,
    OpportunityGapInsightSchema,
)

#: 声明面类型白名单（AC-1/OD-5——float 属白名单成员但六 Schema 无字段使用，
#: "仅限"为约束语义）
DECLARED_TYPE_WHITELIST: tuple[Any, ...] = (str, float, list[str])


def _make_gap(**overrides: Any) -> PerformanceGapArtifacts:
    """PerformanceGapArtifacts 工厂（默认正常态 + 覆写）。"""
    fields: dict[str, Any] = {
        "financial_gap": "财务差距量化：营收达成率 82%",
        "operational_gap": "运营差距分析：交付周期延长",
        "root_causes": ("价格竞争侵蚀毛利", "供应链成本上升"),
        "portfolio_health": "业务组合健康度：核心业务稳健",
    }
    fields.update(overrides)
    return PerformanceGapArtifacts(**fields)


# ===================================================================
# TDD 循环 A：六类型化 Schema
# ===================================================================


class TestSixTypedSchemas:
    """六类型化 Schema 存在性与结构（Task 0.1 冻结契约）。"""

    def test_six_schema_classes_exist(self) -> None:
        """六类存在且均为 pydantic BaseModel 子类（应用层边界合法依赖）。"""
        for schema_cls in ALL_TYPED_SCHEMAS:
            assert issubclass(schema_cls, BaseModel), f"{schema_cls.__name__} 应为 BaseModel 子类"

    def test_trend_fields_complete(self) -> None:
        """看趋势：PESTEL 六维度 + 技术演进路线图 + 情景规划方案集 + 公共双字段。"""
        actual = frozenset(TrendInsightSchema.model_fields)
        expected = EXPECTED_DOMAIN_FIELDS["trend"] | COMMON_FIELDS
        assert actual == expected, f"trend 键族不一致: 缺 {expected - actual} / 多 {actual - expected}"

    def test_market_customer_fields_complete(self) -> None:
        """看市场与客户：细分画像 + 优先级矩阵 + 价值主张地图 + 公共双字段。"""
        actual = frozenset(MarketCustomerInsightSchema.model_fields)
        expected = EXPECTED_DOMAIN_FIELDS["market_customer"] | COMMON_FIELDS
        assert actual == expected, f"market_customer 键族不一致: {actual ^ expected}"

    def test_competition_fields_complete(self) -> None:
        """看竞争：波特五力五维 + 能力雷达 + 策略建议 + 公共双字段。"""
        actual = frozenset(CompetitionInsightSchema.model_fields)
        expected = EXPECTED_DOMAIN_FIELDS["competition"] | COMMON_FIELDS
        assert actual == expected, f"competition 键族不一致: {actual ^ expected}"

    def test_self_fields_complete(self) -> None:
        """看自己：能力清单 + VRIO 评估 + 资源约束 + 公共双字段。"""
        actual = frozenset(SelfInsightSchema.model_fields)
        expected = EXPECTED_DOMAIN_FIELDS["self"] | COMMON_FIELDS
        assert actual == expected, f"self 键族不一致: {actual ^ expected}"

    def test_opportunity_fields_complete(self) -> None:
        """看机会：机会清单 + 优先级排序 + 增长路径 + 公共双字段。"""
        actual = frozenset(OpportunityInsightSchema.model_fields)
        expected = EXPECTED_DOMAIN_FIELDS["opportunity"] | COMMON_FIELDS
        assert actual == expected, f"opportunity 键族不一致: {actual ^ expected}"

    def test_opportunity_gap_fields_complete(self) -> None:
        """机会差距分析：量化报告 + 匹配矩阵 + 弥合策略 + 公共双字段。"""
        actual = frozenset(OpportunityGapInsightSchema.model_fields)
        expected = EXPECTED_DOMAIN_FIELDS["opportunity_gap"] | COMMON_FIELDS
        assert actual == expected, f"opportunity_gap 键族不一致: {actual ^ expected}"

    def test_common_summary_findings_on_all_six(self) -> None:
        """六 Schema 均含公共双字段 summary: str + findings: list[str]（信封同源——R3-1：
        服务成功分支直读 schema_result.summary/findings，缺字段即 AttributeError）。"""
        for schema_cls in ALL_TYPED_SCHEMAS:
            fields = schema_cls.model_fields
            assert "summary" in fields, f"{schema_cls.__name__} 缺公共字段 summary"
            assert "findings" in fields, f"{schema_cls.__name__} 缺公共字段 findings"
            assert fields["summary"].annotation is str, f"{schema_cls.__name__}.summary 应为 str"
            # list[str] 为 GenericAlias——每次求值产生新实例，is 恒 False，须 == 比较
            assert fields["findings"].annotation == list[str], f"{schema_cls.__name__}.findings 应为 list[str]"

    def test_field_type_whitelist_flat(self) -> None:
        """扁平化强制（OD-5）：全字段注解 ∈ {str, float, list[str]}——嵌套
        BaseModel/list[dict]/Optional 即红（GLM anthropic 端点嵌套 Schema 栈溢出）。"""
        for schema_cls in ALL_TYPED_SCHEMAS:
            for name, field in schema_cls.model_fields.items():
                annotation = field.annotation
                assert annotation in DECLARED_TYPE_WHITELIST, (
                    f"{schema_cls.__name__}.{name} 注解 {annotation} 越出扁平化白名单 "
                    f"{DECLARED_TYPE_WHITELIST}（OD-5——嵌套/Optional 禁入）"
                )

    def test_no_optional_or_none_defaults(self) -> None:
        """禁 Optional[X]/None 默认值字段（model_dump 产 None 会炸 VO 守卫且在
        步级降级 try/except 之外——R1-5）。"""
        for schema_cls in ALL_TYPED_SCHEMAS:
            for name, field in schema_cls.model_fields.items():
                assert field.default is not None, f"{schema_cls.__name__}.{name} 默认值为 None（禁）"
                assert field.default_factory is None, f"{schema_cls.__name__}.{name} 带 default_factory（None 产出禁）"

    def test_field_descriptions_non_empty(self) -> None:
        """每字段 Field description 非空（中文领域语义——生成面质量锚）。"""
        for schema_cls in ALL_TYPED_SCHEMAS:
            for name, field in schema_cls.model_fields.items():
                description = field.description
                assert description and description.strip(), f"{schema_cls.__name__}.{name} description 为空（领域语义缺失）"

    def test_model_dump_flat_json_scalars(self) -> None:
        """model_dump 产物键值均为 JSON 标量/标量列表（VO 值域守卫兼容面）。"""
        schema = TrendInsightSchema(
            summary="趋势结论",
            findings=["发现一"],
            pestel_political="政策评估",
            pestel_economic="经济评估",
            pestel_social="社会评估",
            pestel_technological="技术评估",
            pestel_environmental="环境评估",
            pestel_legal="法律评估",
            technology_roadmap=["短期要点"],
            scenario_plans=["基准情景"],
        )
        dumped = schema.model_dump()
        assert set(dumped) == EXPECTED_DOMAIN_FIELDS["trend"] | COMMON_FIELDS
        for value in dumped.values():
            assert isinstance(value, (str, float, int, bool, list)), f"dump 值 {value!r} 非 JSON 标量/标量列表"
            if isinstance(value, list):
                assert all(isinstance(item, str) for item in value)


# ===================================================================
# TDD 循环 B：schema 映射 SSOT + gap 四字段传导
# ===================================================================


class TestSchemaMappingSSOT:
    """MARKET_INSIGHT_STEP_SCHEMA 映射（形态 A 独立 dict——Subtask 0.1 钦定）。"""

    def test_mapping_six_enum_keys_complete(self) -> None:
        """六枚举键齐备（MarketInsightStep 全值域）。"""
        assert set(MARKET_INSIGHT_STEP_SCHEMA) == set(MarketInsightStep)

    def test_mapping_values_distinct(self) -> None:
        """六值互异（一步一 Schema——错配/复用即红）。"""
        values = list(MARKET_INSIGHT_STEP_SCHEMA.values())
        assert len(values) == len(set(values)), "映射值存在复用（六 Schema 应互异）"

    def test_mapping_step_to_schema_exact(self) -> None:
        """逐步映射精确（trend→TrendInsightSchema 等——独立构造期望表）。"""
        for step, expected_cls in EXPECTED_SCHEMA_BY_STEP.items():
            actual = MARKET_INSIGHT_STEP_SCHEMA[MarketInsightStep(step)]
            assert actual is expected_cls, f"{step} 应映射 {expected_cls.__name__}（实际 {actual.__name__}——SSOT 映射错配）"

    def test_mapping_is_independent_dict_not_config_field(self) -> None:
        """形态 A 钦定：独立 dict（type[BaseModel] 值域），非 StepSemanticConfig 字段。"""
        from src.application.services.blm_planning_prompts import StepSemanticConfig

        assert isinstance(MARKET_INSIGHT_STEP_SCHEMA, dict), "SSOT 映射应为独立 dict（形态 A）"
        config_fields = {f for f in StepSemanticConfig.__dataclass_fields__}
        assert not config_fields & {"schema_cls"}, "StepSemanticConfig 不应承载 schema_cls 字段（形态 A 钦定）"


class TestSummarizeGapFourFields:
    """summarize_gap_for_downstream 四字段全量传导（OD-6——6-1 代码审查 R2-3 执行）。"""

    def test_normal_summary_contains_four_labels(self) -> None:
        """正常态四字段全量标签（财务差距=/运营差距=/根因=/组合健康度=）。"""
        summary = summarize_gap_for_downstream(_make_gap())
        for label in ("财务差距=", "运营差距=", "根因=", "组合健康度="):
            assert label in summary, f"gap 摘要缺标签「{label}」（四字段全量传导——OD-6）"

    def test_financial_gap_substring_backcompat(self) -> None:
        """「财务差距=」子串兼容（6-1 单测 L533 先例——R2-3 钉死）。"""
        summary = summarize_gap_for_downstream(_make_gap())
        assert "财务差距=" in summary

    def test_summary_contains_actual_field_values(self) -> None:
        """四字段内容实值入摘（非仅标签——内容可判别）。"""
        summary = summarize_gap_for_downstream(_make_gap())
        assert "营收达成率 82%" in summary
        assert "交付周期延长" in summary
        assert "价格竞争侵蚀毛利" in summary
        assert "核心业务稳健" in summary

    def test_degraded_summary_marker_unchanged(self) -> None:
        """降级态 [降级] 标注零回归（DEGRADATION_MARKER_PREFIX 单源不变）。"""
        gap = _make_gap(degraded=True, degrade_reason="LLM 调用失败（注入）")
        summary = summarize_gap_for_downstream(gap)
        assert summary.startswith(DEGRADATION_MARKER_PREFIX), "降级标注前缀丢失（单源漂移）"
        assert "performance_gap" in summary
        assert "LLM 调用失败（注入）" in summary

    def test_degraded_branch_not_extended_to_four_fields(self) -> None:
        """降级分支零改动（不注入四字段内容——降级摘要语义保持 6-1 形态）。"""
        gap = _make_gap(degraded=True, degrade_reason="注入原因")
        summary = summarize_gap_for_downstream(gap)
        assert "财务差距=" not in summary, "降级分支不应携带四字段内容（零改动钦定）"

    def test_gap_analysis_schema_untouched(self) -> None:
        """GapAnalysisSchema 四字段结构零改动（6-1 既有——守卫锚）。"""
        fields = frozenset(GapAnalysisSchema.model_fields)
        assert fields == frozenset({"financial_gap", "operational_gap", "root_causes", "portfolio_health"})
