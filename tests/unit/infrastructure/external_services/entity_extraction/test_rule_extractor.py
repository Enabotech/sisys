"""规则基实体抽取器单元测试

验证 RuleBasedExtractor 的 AC 自动机匹配、正则匹配、内置词典和准确率。
遵循 TDD：红阶段先写失败测试。
"""

from __future__ import annotations

import pytest

from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
)
from src.infrastructure.external_services.entity_extraction.rule_extractor import (
    RuleBasedExtractor,
    _create_builtin_dictionary,
)


class TestBuiltinDictionary:
    """内置战略领域词典验证"""

    def test_contains_strategy_terms(self) -> None:
        """验证包含战略管理词条"""
        dictionary = _create_builtin_dictionary()
        terms = {term for term, _ in dictionary}
        for keyword in ["BLM", "BEM", "SWOT", "PESTEL", "战略规划", "市场洞察", "战略意图", "创新焦点", "业务设计", "执行设计"]:
            assert keyword in terms, f"缺少战略词条: {keyword}"

    def test_contains_financial_terms(self) -> None:
        """验证包含财务指标词条"""
        dictionary = _create_builtin_dictionary()
        terms = {term for term, _ in dictionary}
        for keyword in ["NPV", "IRR", "ROI", "现金流", "利润率", "营业收入", "净利润", "EBITDA"]:
            assert keyword in terms, f"缺少财务词条: {keyword}"

    def test_contains_market_terms(self) -> None:
        """验证包含市场概念词条"""
        dictionary = _create_builtin_dictionary()
        terms = {term for term, _ in dictionary}
        for keyword in ["市场份额", "增长率", "市场规模", "竞争格局", "蓝海", "红海", "差异化", "成本领先"]:
            assert keyword in terms, f"缺少市场词条: {keyword}"

    def test_contains_tech_terms(self) -> None:
        """验证包含技术概念词条"""
        dictionary = _create_builtin_dictionary()
        terms = {term for term, _ in dictionary}
        for keyword in ["AI", "人工智能", "云计算", "大数据", "物联网", "数字化转型", "SaaS"]:
            assert keyword in terms, f"缺少技术词条: {keyword}"

    def test_contains_org_role_terms(self) -> None:
        """验证包含组织角色词条"""
        dictionary = _create_builtin_dictionary()
        terms = {term for term, _ in dictionary}
        for keyword in ["CEO", "CFO", "CTO", "COO", "CMO", "CHO", "董事会", "高管团队"]:
            assert keyword in terms, f"缺少组织角色词条: {keyword}"

    def test_contains_100_plus_terms(self) -> None:
        """验证词典包含 100+ 词条"""
        dictionary = _create_builtin_dictionary()
        assert len(dictionary) >= 100, f"词典词条数 {len(dictionary)} < 100"


class TestRuleBasedExtractor:
    """RuleBasedExtractor 测试"""

    @pytest.fixture
    def extractor(self) -> RuleBasedExtractor:
        """创建 RuleBasedExtractor 实例"""
        return RuleBasedExtractor()

    def test_implements_entity_extraction_port(self, extractor: RuleBasedExtractor) -> None:
        """验证实现 EntityExtractionPort"""
        assert isinstance(extractor, EntityExtractionPort)

    # --- Happy Path: AC 自动机匹配 ---

    @pytest.mark.asyncio
    async def test_match_strategy_entity(self, extractor: RuleBasedExtractor) -> None:
        """验证 AC 自动机匹配战略领域实体"""
        result = await extractor.extract_entities("BLM 模型是企业战略规划的重要工具")
        assert len(result.entities) >= 1
        blm_entities = [e for e in result.entities if e.name == "BLM"]
        assert len(blm_entities) >= 1
        assert blm_entities[0].entity_type == "CONCEPT"
        assert blm_entities[0].extraction_source == "rule"

    @pytest.mark.asyncio
    async def test_match_multiple_entities(self, extractor: RuleBasedExtractor) -> None:
        """验证多实体同时匹配"""
        result = await extractor.extract_entities("SWOT 分析和 PESTEL 分析是常用的战略工具")
        names = {e.name for e in result.entities}
        assert "SWOT" in names
        assert "PESTEL" in names
        assert all(e.extraction_source == "rule" for e in result.entities)

    # --- Happy Path: 正则匹配 ---

    @pytest.mark.asyncio
    async def test_match_date(self, extractor: RuleBasedExtractor) -> None:
        """验证正则匹配日期"""
        result = await extractor.extract_entities("2024 年公司营收增长 15%")
        date_entities = [e for e in result.entities if e.entity_type == "DATE"]
        assert len(date_entities) >= 1
        assert "2024" in date_entities[0].name

    @pytest.mark.asyncio
    async def test_match_percent(self, extractor: RuleBasedExtractor) -> None:
        """验证正则匹配百分比"""
        result = await extractor.extract_entities("市场份额增长 15%")
        percent_entities = [e for e in result.entities if e.entity_type == "PERCENT"]
        assert len(percent_entities) >= 1
        assert "15%" in percent_entities[0].name

    @pytest.mark.asyncio
    async def test_match_amount(self, extractor: RuleBasedExtractor) -> None:
        """验证正则匹配金额"""
        result = await extractor.extract_entities("项目投资 ¥100 亿")
        amount_entities = [e for e in result.entities if e.entity_type == "AMOUNT"]
        assert len(amount_entities) >= 1

    # --- Edge Case ---

    @pytest.mark.asyncio
    async def test_empty_content(self, extractor: RuleBasedExtractor) -> None:
        """验证空字符串返回空结果"""
        result = await extractor.extract_entities("")
        assert len(result.entities) == 0
        assert len(result.relations) == 0

    @pytest.mark.asyncio
    async def test_no_match_content(self, extractor: RuleBasedExtractor) -> None:
        """验证无匹配内容返回空列表"""
        result = await extractor.extract_entities("这是一段不包含任何战略术语的普通文本")
        assert len(result.entities) == 0

    # --- 准确率验证 ---

    @pytest.mark.asyncio
    async def test_accuracy_above_80_percent(self, extractor: RuleBasedExtractor) -> None:
        """验证预定义测试集准确率≥80%

        测试集包含 10 个已知实体，规则基应准确识别其中至少 8 个。
        """
        test_text = (
            "BLM 模型从市场洞察开始，通过战略意图明确方向，"
            "创新焦点确定资源投入，业务设计构建竞争优势。"
            "CFO 需要关注 NPV 和 IRR 指标，"
            "而 CTO 则关注 AI 和云计算技术趋势。"
            "2024 年公司营收增长 15%，市场份额提升至 25%。"
            "SWOT 分析显示差异化战略是成本领先的关键。"
        )
        expected_entities = {
            "BLM",
            "市场洞察",
            "战略意图",
            "创新焦点",
            "业务设计",
            "CFO",
            "NPV",
            "IRR",
            "CTO",
            "AI",
            "云计算",
            "SWOT",
            "差异化",
            "成本领先",
        }
        result = await extractor.extract_entities(test_text)
        extracted_names = {e.name for e in result.entities}

        correct = len(expected_entities & extracted_names)
        total = len(expected_entities)
        accuracy = correct / total
        assert accuracy >= 0.8, f"准确率 {accuracy:.0%} < 80%（正确 {correct}/{total}）"

    # --- 词典热更新 ---

    @pytest.mark.asyncio
    async def test_reload_dictionary(self, extractor: RuleBasedExtractor) -> None:
        """验证词典热更新后匹配新实体"""
        # 初始应不匹配自定义词条
        result = await extractor.extract_entities("自定义词条是本次测试的核心概念")
        assert "自定义词条" not in {e.name for e in result.entities}

        # 热更新词典
        extractor.reload_dictionary([("自定义词条", "CONCEPT")])

        # 更新后应匹配
        result = await extractor.extract_entities("自定义词条是本次测试的核心概念")
        assert "自定义词条" in {e.name for e in result.entities}

    # --- 元数据 ---

    @pytest.mark.asyncio
    async def test_extraction_metadata(self, extractor: RuleBasedExtractor) -> None:
        """验证抽取元数据包含策略信息"""
        result = await extractor.extract_entities("BLM 模型")
        assert result.extraction_metadata.get("strategy") == "rule"
        assert "entity_count" in result.extraction_metadata
        assert "duration_ms" in result.extraction_metadata
