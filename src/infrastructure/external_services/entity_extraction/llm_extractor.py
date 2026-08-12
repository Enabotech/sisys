"""基础设施层 LLM 语义实体抽取器模块

实现 EntityExtractionPort 端口，使用 LLMClientPort.structured_generate() 进行语义实体抽取。
使用 Few-Shot + CoT 提示策略，Pydantic Schema 约束输出。
LLM 失败时透明降级（返回空结果，不抛出异常）。
"""

from __future__ import annotations

import logging
import time

from src.domain.exceptions import (
    LLMAPIError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from src.domain.ports.llm_client import LLMClientPort
from src.infrastructure.external_services.entity_extraction.llm_extractor_schema import (
    EntityExtractionSchema,
)

logger = logging.getLogger(__name__)

# Few-Shot 示例：实体抽取
_FEW_SHOT_EXAMPLES = """
## 示例 1

输入文本："BLM 模型从市场洞察开始，通过战略意图明确方向。"
输出：
```json
{
  "entities": [
    {"name": "BLM", "entity_type": "CONCEPT", "confidence": 0.95},
    {"name": "市场洞察", "entity_type": "CONCEPT", "confidence": 0.90},
    {"name": "战略意图", "entity_type": "CONCEPT", "confidence": 0.90}
  ],
  "relations": [
    {"source": "BLM", "target": "市场洞察", "relation_type": "PART_OF", "confidence": 0.85},
    {"source": "BLM", "target": "战略意图", "relation_type": "PART_OF", "confidence": 0.85}
  ]
}
```

## 示例 2

输入文本："CFO 张明在董事会会议上汇报了 2024 年财务预测。"
输出：
```json
{
  "entities": [
    {"name": "CFO", "entity_type": "ORG", "confidence": 0.95},
    {"name": "张明", "entity_type": "PERSON", "confidence": 0.90},
    {"name": "董事会", "entity_type": "ORG", "confidence": 0.85},
    {"name": "2024 年", "entity_type": "DATE", "confidence": 0.95}
  ],
  "relations": [
    {"source": "张明", "target": "CFO", "relation_type": "RELATES_TO", "confidence": 0.90},
    {"source": "张明", "target": "董事会", "relation_type": "RELATES_TO", "confidence": 0.80}
  ]
}
```

## 示例 3

输入文本："AI 技术正在重塑云计算行业格局，数据安全成为关键挑战。"
输出：
```json
{
  "entities": [
    {"name": "AI", "entity_type": "CONCEPT", "confidence": 0.95},
    {"name": "云计算", "entity_type": "CONCEPT", "confidence": 0.90},
    {"name": "数据安全", "entity_type": "CONCEPT", "confidence": 0.85}
  ],
  "relations": [
    {"source": "AI", "target": "云计算", "relation_type": "INFLUENCES", "confidence": 0.85},
    {"source": "数据安全", "target": "云计算", "relation_type": "RELATES_TO", "confidence": 0.80}
  ]
}
```
"""

# 系统提示模板
_SYSTEM_PROMPT_TEMPLATE = """你是一个实体抽取专家，负责从战略管理文本中抽取命名实体和关系。

## 抽取规则

1. **实体类型**：
   - PERSON：人员名称
   - ORG：组织、角色（如 CFO、董事会、华为）
   - LOC：地点（如中国、北京）
   - PRODUCT：产品名称
   - CONCEPT：概念、术语（如 BLM、SWOT、战略规划）
   - DATE：日期（如 2024 年）
   - AMOUNT：金额（如 ¥100 亿）
   - PERCENT：百分比（如 15%）

2. **关系类型**：
   - MENTIONS：提及关系
   - DEPENDS_ON：依赖关系
   - RELATES_TO：相关关系
   - PART_OF：部分关系
   - INFLUENCES：影响关系
   - CONTRADICTS：矛盾关系

3. **置信度规则**：
   - 明确提及的实体置信度 ≥ 0.85
   - 通过上下文推断的实体置信度 0.60-0.85
   - 低置信度实体不输出（< 0.60）

## 推理步骤（CoT）

1. 识别文本中的所有命名实体
2. 确定每个实体的类型
3. 评估每个实体的置信度
4. 识别实体之间的关系
5. 评估每个关系的置信度
6. 输出结构化 JSON

{few_shot_examples}
"""


class LLMEntityExtractor(EntityExtractionPort):
    """LLM 语义实体抽取器

    使用 LLMClientPort.structured_generate() 进行语义实体抽取。
    LLM 失败时透明降级（返回空结果，不抛出异常）。

    Attributes:
        _llm_client: LLMClientPort 实例
    """

    def __init__(self, llm_client: LLMClientPort) -> None:
        """初始化 LLM 语义抽取器

        Args:
            llm_client: LLMClientPort 实例
        """
        self._llm_client = llm_client

    async def extract_entities(
        self,
        content: str,
        domain_context: dict | None = None,
    ) -> ExtractionResult:
        """执行 LLM 语义实体抽取

        Args:
            content: 待抽取的文本内容
            domain_context: 领域上下文（可选，可包含 domain 领域描述信息）

        Returns:
            ExtractionResult 包含抽取的实体和关系列表，失败时返回空结果
        """
        if not content or not content.strip():
            return ExtractionResult(extraction_metadata={"strategy": "llm", "entity_count": 0})

        start_time = time.monotonic()

        # 构建提示
        domain_hint = ""
        if domain_context and "domain" in domain_context:
            domain_hint = f"\n领域上下文：{domain_context['domain']}"

        # 先注入 Few-Shot 示例
        few_shot = _FEW_SHOT_EXAMPLES
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(few_shot_examples=few_shot)

        prompt = (
            f"请从以下文本中抽取实体和关系。\n\n文本：{content}{domain_hint}\n\n请严格按照 JSON Schema 格式输出实体和关系列表。"
        )

        # 调用 LLM（使用 system_prompt 作为 system role，提升系统指令遵循度）
        try:
            result = await self._llm_client.structured_generate(
                prompt=prompt,
                response_schema=EntityExtractionSchema,
                system_prompt=system_prompt,
            )

            # 转换结果为 ExtractionResult
            entities = tuple(
                ExtractedEntity(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    confidence=entity.confidence,
                    extraction_source="llm",
                )
                for entity in result.entities
            )

            relations = tuple(
                ExtractedRelation(
                    source=rel.source,
                    target=rel.target,
                    relation_type=rel.relation_type,
                    confidence=rel.confidence,
                    extraction_source="llm",
                )
                for rel in result.relations
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            return ExtractionResult(
                entities=entities,
                relations=relations,
                extraction_metadata={
                    "strategy": "llm",
                    "entity_count": len(entities),
                    "relation_count": len(relations),
                    "duration_ms": round(duration_ms, 2),
                },
            )

        except (LLMAPIError, ServiceUnavailableError, TimeoutError) as e:
            # 透明降级：LLM 外部服务不可用/超时时返回空结果，不阻塞主流程
            # LLMConfigError（配置错误）和 LLMResponseError（Schema 验证失败）
            # 属于设计/配置级错误，应传播到应用层，此处不捕获
            logger.warning("LLM 实体抽取失败，降级至空结果: %s", e)
            return ExtractionResult(
                extraction_metadata={
                    "strategy": "llm",
                    "entity_count": 0,
                    "error": str(e)[:200],
                },
            )


__all__ = [
    "LLMEntityExtractor",
]
