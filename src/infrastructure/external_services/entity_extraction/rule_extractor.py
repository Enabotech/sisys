"""基础设施层规则基实体抽取器模块

实现 EntityExtractionPort 端口，使用 AC 自动机（pyahocorasick）+ 正则模式匹配。
内置基础战略领域词典，支持词典热更新。
"""

from __future__ import annotations

import re
import time

import ahocorasick

from src.domain.ports.domain_dictionary import DictionaryConsumerPort
from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractedEntity,
    ExtractionResult,
)


def _create_builtin_dictionary() -> list[tuple[str, str]]:
    """创建内置战略领域词典

    包含约 100+ 核心词条，覆盖战略管理、财务、市场、技术、组织角色等类别。

    Returns:
        list[tuple[str, str]]: (词条, 实体类型) 列表
    """
    dictionary: list[tuple[str, str]] = []

    # 战略管理
    strategy_terms = [
        "BLM",
        "BEM",
        "SP",
        "BP",
        "战略规划",
        "市场洞察",
        "战略意图",
        "创新焦点",
        "业务设计",
        "执行设计",
        "PESTEL",
        "SWOT",
        "TOWS",
        "波特五力",
        "价值链",
        "VRIO",
        "安索夫矩阵",
        "GE-麦肯锡矩阵",
        "SPACE 矩阵",
        "波士顿矩阵",
        "核心竞争力",
        "战略目标",
        "关键成功因素",
        "KPI",
        "OKR",
        "差距分析",
        "愿景",
        "使命",
        "价值观",
    ]
    for term in strategy_terms:
        dictionary.append((term, "CONCEPT"))

    # 财务指标
    financial_terms = [
        "NPV",
        "IRR",
        "ROI",
        "现金流",
        "利润率",
        "资产负债率",
        "营业收入",
        "净利润",
        "EBITDA",
        "ROCE",
        "毛利率",
        "净利率",
        "流动比率",
        "速动比率",
        "资产周转率",
        "权益乘数",
        "DCF",
        "WACC",
        "CAPEX",
        "OPEX",
        "EPS",
    ]
    for term in financial_terms:
        dictionary.append((term, "CONCEPT"))

    # 市场概念
    market_terms = [
        "市场份额",
        "增长率",
        "市场规模",
        "竞争格局",
        "蓝海",
        "红海",
        "差异化",
        "成本领先",
        "集中化战略",
        "市场渗透",
        "市场开发",
        "产品开发",
        "多元化",
        "一体化战略",
        "TAM",
        "SAM",
        "SOM",
        "CAGR",
        "市场占有率",
        "客户满意度",
        "NPS",
    ]
    for term in market_terms:
        dictionary.append((term, "CONCEPT"))

    # 技术概念
    tech_terms = [
        "AI",
        "人工智能",
        "云计算",
        "大数据",
        "物联网",
        "区块链",
        "5G",
        "数字化转型",
        "SaaS",
        "PaaS",
        "IaaS",
        "机器学习",
        "深度学习",
        "自然语言处理",
        "RPA",
        "ERP",
        "CRM",
        "数字化",
        "工业 4.0",
        "智能制造",
        "边缘计算",
        "数字孪生",
    ]
    for term in tech_terms:
        dictionary.append((term, "CONCEPT"))

    # 组织角色
    role_terms = [
        "CEO",
        "CFO",
        "CTO",
        "COO",
        "CMO",
        "CHO",
        "董事会",
        "高管团队",
        "事业部",
        "子公司",
        "集团总部",
        "CIO",
        "CHRO",
        "CDO",
    ]
    for term in role_terms:
        dictionary.append((term, "ORG"))

    return dictionary


# 正则模式：结构化实体
_REGEX_PATTERNS: list[tuple[str, str, str]] = [
    # (模式名, 正则, 实体类型)
    ("date", r"\d{4}\s*年", "DATE"),
    ("date_range", r"\d{4}\s*[-~]\s*\d{4}\s*年", "DATE"),
    ("percent", r"\d+\.?\d*\s*%", "PERCENT"),
    ("amount_cny", r"[¥￥]\s*\d+[\.\d]*\s*[万亿亿]?", "AMOUNT"),
    ("amount_usd", r"\$\s*\d+[\.\d]*\s*[万亿亿]?", "AMOUNT"),
    ("phone", r"1[3-9]\d{9}", "CONTACT"),
    ("email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "CONTACT"),
]

# 编译正则模式
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern), entity_type) for _, pattern, entity_type in _REGEX_PATTERNS
]


class RuleBasedExtractor(EntityExtractionPort, DictionaryConsumerPort):
    """规则基实体抽取器

    使用 AC 自动机（pyahocorasick）匹配命名实体（人员、组织、地点、产品、概念），
    正则模式匹配结构化实体（日期、金额、百分比、联系方式）。

    Attributes:
        _automaton: AC 自动机实例
        _dictionary: 当前词典列表
    """

    def __init__(self, builtin_dictionary: list[tuple[str, str]] | None = None) -> None:
        """初始化规则基抽取器

        Args:
            builtin_dictionary: 内置词典列表（可选，默认使用内置战略领域词典）
        """
        dictionary = builtin_dictionary if builtin_dictionary is not None else _create_builtin_dictionary()
        self._automaton: ahocorasick.Automaton = ahocorasick.Automaton()
        self._dictionary: list[tuple[str, str]] = list(dictionary)
        self._build_automaton()

    def _build_automaton(self) -> None:
        """构建 AC 自动机"""
        self._automaton = ahocorasick.Automaton()
        for idx, (term, entity_type) in enumerate(self._dictionary):
            self._automaton.add_word(term, (idx, term, entity_type))
        if self._dictionary:
            self._automaton.make_automaton()

    def reload_dictionary(self, dictionary: list[tuple[str, str]]) -> None:
        """热更新词典

        Args:
            dictionary: 新词典列表
        """
        self._dictionary = list(dictionary)
        self._build_automaton()

    async def extract_entities(
        self,
        content: str,
        domain_context: dict | None = None,
    ) -> ExtractionResult:
        """执行规则基实体抽取

        Args:
            content: 待抽取的文本内容
            domain_context: 领域上下文（可选）

        Returns:
            ExtractionResult 包含抽取的实体列表
        """
        if not content or not content.strip():
            return ExtractionResult(extraction_metadata={"strategy": "rule", "entity_count": 0})

        start_time = time.monotonic()

        # 1. AC 自动机匹配命名实体
        ac_entities: dict[str, ExtractedEntity] = {}
        if self._dictionary:
            for end_idx, (idx, term, entity_type) in self._automaton.iter(content):
                if term not in ac_entities:
                    ac_entities[term] = ExtractedEntity(
                        name=term,
                        entity_type=entity_type,
                        confidence=0.85,
                        extraction_source="rule",
                        metadata={"position": end_idx},
                    )

        # 2. 正则匹配结构化实体
        regex_entities: dict[str, ExtractedEntity] = {}
        for pattern, entity_type in _COMPILED_PATTERNS:
            for match in pattern.finditer(content):
                matched_text = match.group().strip()
                if matched_text not in regex_entities:
                    regex_entities[matched_text] = ExtractedEntity(
                        name=matched_text,
                        entity_type=entity_type,
                        confidence=0.90,
                        extraction_source="rule",
                        metadata={"position": match.start()},
                    )

        # 合并结果（AC 自动机优先，正则补充）
        all_entities: dict[str, ExtractedEntity] = {}
        all_entities.update(ac_entities)
        # 正则实体不覆盖 AC 自动机已匹配的实体
        for name, entity in regex_entities.items():
            if name not in all_entities:
                all_entities[name] = entity

        duration_ms = (time.monotonic() - start_time) * 1000

        return ExtractionResult(
            entities=tuple(all_entities.values()),
            extraction_metadata={
                "strategy": "rule",
                "entity_count": len(all_entities),
                "duration_ms": round(duration_ms, 2),
            },
        )


__all__ = [
    "RuleBasedExtractor",
    "_create_builtin_dictionary",
]
