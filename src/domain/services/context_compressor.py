"""领域层上下文压缩器模块

检索-压缩循环的核心步骤（系统公理二：压缩前必须持久化）。
输入 Top-100 文档（~50K tokens），输出压缩后上下文（~2K tokens）。
压缩率 ≥ 70%，质量评分不足时触发二次生成。

设计决策：
- 注入 LLMClientPort（LLM 摘要生成，通过 generate() 标准文本生成，
  领域层不强制结构化 Schema，避免领域层依赖 pydantic）
- 注入 PersistentNoteTaker verify_persisted 检查前置条件
- 压缩算法：LLM 摘要生成（Temperature=0.3）+ 关键信息抽取
- 压缩率验证：≥70%，不足触发二次压缩
- 质量评估委托 CompressionQualityEvaluator（<0.7 触发二次生成）
- 领域层零外部依赖，仅依赖领域层端口
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.domain.exceptions import EntityValidationError
from src.domain.ports.l1_cache import L1CachePort
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMClientPort, LLMConfig
from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator
from src.domain.services.persistent_note_taker import PersistentNote, PersistentNoteTaker

# 压缩配置常量
_COMPRESSION_RATIO_TARGET: float = 0.70
_CONTEXT_SIZE_LIMIT: int = 2000
_LLM_TEMPERATURE: float = 0.3
_LLM_MAX_TOKENS: int = 2500
_LLM_TIMEOUT: float = 60.0
_KEY_ENTITY_LIMIT: int = 20
_DOCUMENT_CONTEXT_LIMIT: int = 20
_DOCUMENT_PREVIEW_CHARS: int = 500

# 压缩上下文缓存 TTL（24 小时，复用 L1 缓存）
_COMPRESSED_CACHE_TTL: int = 86400


@dataclass(frozen=True)
class CompressedContext:
    """压缩上下文值对象

    Attributes:
        context: 压缩后的上下文文本（~2K tokens）
        compression_ratio: 压缩率（≥0.70）
        quality_score: 质量评分（0-1，<0.7 触发二次生成）
        token_count: 压缩后 token 数（估算）
        original_token_count: 原始 token 数（估算）
        persistent_note_ref: 关联的持久化笔记 ID（UUID 字符串）
        query: 原始查询文本
        key_entities: 输入的关键实体列表
        rerun_count: 重试次数（首次为 0，二次生成为 1）
    """

    context: str = ""
    compression_ratio: float = 0.0
    quality_score: float = 0.0
    token_count: int = 0
    original_token_count: int = 0
    persistent_note_ref: str = ""
    query: str = ""
    key_entities: list[dict[str, Any]] = field(default_factory=list)
    rerun_count: int = 0


class ContextCompressor:
    """上下文压缩器

    压缩流程（对齐架构设计 §17.1.5.1）：
    1. 验证持久化笔记已完成（前置条件，失败抛出错误）
    2. 基于持久化笔记中的 Top-20 关键实体提取关键信息
    3. LLM 摘要生成（Temperature=0.3，低温度保证稳定性）
    4. 压缩率验证（≥70%，不足触发二次压缩）
    5. 质量评估委托 CompressionQualityEvaluator（<0.7 触发二次生成）
    6. 压缩结果缓存至 L1（TTL 24 小时）
    """

    def __init__(
        self,
        llm_client: LLMClientPort,
        note_taker: PersistentNoteTaker,
        quality_evaluator: CompressionQualityEvaluator | None = None,
        l1_cache: L1CachePort | None = None,
    ) -> None:
        """初始化上下文压缩器

        Args:
            llm_client: LLM 客户端端口（用于摘要生成）
            note_taker: 持久化笔记记录器（用于 verify_persisted 前置检查）
            quality_evaluator: 压缩质量评估器（可选，None 时跳过质量评估）
            l1_cache: L1 缓存端口（可选，用于压缩结果缓存）
        """
        self._llm_client = llm_client
        self._note_taker = note_taker
        self._quality_evaluator = quality_evaluator
        self._l1_cache = l1_cache

    async def compress(
        self,
        retrieved_docs: list[SearchResult],
        query: str,
        persistent_note: PersistentNote,
    ) -> CompressedContext:
        """压缩检索结果至 LLM 上下文

        前置条件：persistent_note 已验证（压缩前必须持久化）。

        Args:
            retrieved_docs: 检索结果文档列表
            query: 原始查询文本
            persistent_note: 已持久化的笔记（persisted=True）

        Returns:
            CompressedContext 压缩上下文

        Raises:
            EntityValidationError: 持久化笔记未完成时
        """
        # 0. 验证持久化已完成（前置条件）
        if not PersistentNoteTaker.verify_persisted(persistent_note):
            raise EntityValidationError(
                message="Compression requires persistent note to be persisted first",
                context={"service": "ContextCompressor", "note_id": str(persistent_note.note_id)},
            )

        # 获取关键实体（Top-20）
        key_entities = persistent_note.entities[:_KEY_ENTITY_LIMIT]

        # 估算原始 token 数
        original_token_count = self._estimate_tokens(retrieved_docs)

        # 1. LLM 摘要生成（Temperature=0.3）
        prompt = self._build_compress_prompt(
            retrieved_docs=retrieved_docs,
            query=query,
            key_entities=key_entities,
        )
        summary_text = await self._generate_summary(prompt)

        # 构建上下文
        context = self._build_context(summary_text, query)

        # 2. 压缩率验证
        compressed_tokens = self._estimate_chars_tokens(context)
        compression_ratio = 1.0 - (compressed_tokens / max(original_token_count, 1))
        rerun_count = 0

        if compression_ratio < _COMPRESSION_RATIO_TARGET:
            # 压缩率不足，触发二次压缩
            context = await self._recompress(context, query)
            compressed_tokens = self._estimate_chars_tokens(context)
            compression_ratio = 1.0 - (compressed_tokens / max(original_token_count, 1))
            rerun_count = 1

        # 3. 质量评估
        quality_score = 0.8  # 默认评分（未注入评估器时）
        if self._quality_evaluator is not None:
            quality_score = await self._quality_evaluator.evaluate(
                compressed_context=context,
                original_docs=retrieved_docs,
                key_entities=key_entities,
            )
            if quality_score < 0.7:
                # 质量不足，触发二次生成
                context = await self._regenerate(context, query)
                quality_score = await self._quality_evaluator.evaluate(
                    compressed_context=context,
                    original_docs=retrieved_docs,
                    key_entities=key_entities,
                )
                rerun_count += 1

        # 4. 缓存压缩结果
        await self._cache_compressed(persistent_note.note_id, context)

        return CompressedContext(
            context=context,
            compression_ratio=round(compression_ratio, 4),
            quality_score=round(quality_score, 4),
            token_count=compressed_tokens,
            original_token_count=original_token_count,
            persistent_note_ref=str(persistent_note.note_id),
            query=query,
            key_entities=key_entities,
            rerun_count=rerun_count,
        )

    async def _generate_summary(self, prompt: str) -> str:
        """LLM 摘要生成（Temperature=0.3）

        Args:
            prompt: 压缩 prompt

        Returns:
            摘要文本
        """
        result = await self._llm_client.generate(
            prompt=prompt,
            config=LLMConfig(
                temperature=_LLM_TEMPERATURE,
                max_tokens=_LLM_MAX_TOKENS,
                timeout=_LLM_TIMEOUT,
            ),
            system_prompt=(
                "你是一个专业的企业战略分析摘要生成器。"
                "请基于检索文档提取关键信息，保留核心事实、数据、结论和推理链。"
                "压缩目标：保留核心语义，去除冗余，压缩率≥70%。"
                "请直接输出摘要正文，不要包含任何额外的解释或格式标记。"
            ),
        )
        return result.content.strip()

    async def _recompress(self, context: str, query: str) -> str:
        """二次压缩（压缩率不足时触发）

        Args:
            context: 初次压缩结果
            query: 原始查询

        Returns:
            进一步压缩后的上下文
        """
        prompt = (
            f"请对以下内容进行更强的压缩，在保留核心信息的前提下进一步减少篇幅。\n\n"
            f"原始查询：{query}\n\n"
            f"内容：{context[:4000]}\n\n"
            f"请直接输出压缩后的正文，不要包含解释或格式标记。"
        )
        result = await self._llm_client.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.2, max_tokens=1500, timeout=_LLM_TIMEOUT),
        )
        return self._truncate_context(result.content)

    async def _regenerate(self, context: str, query: str) -> str:
        """二次生成（质量不足时触发）

        Args:
            context: 初次生成的上下文
            query: 原始查询

        Returns:
            重新生成的上下文
        """
        prompt = (
            f"请重新生成以下内容的摘要，确保覆盖所有关键实体、数据点和推理链。\n\n"
            f"原始查询：{query}\n\n"
            f"内容：{context[:4000]}\n\n"
            f"请直接输出重新生成的摘要正文，不要包含解释或格式标记。"
        )
        result = await self._llm_client.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.4, max_tokens=_LLM_MAX_TOKENS, timeout=_LLM_TIMEOUT),
        )
        return self._truncate_context(result.content)

    async def _cache_compressed(self, note_id: UUID, context: str) -> None:
        """缓存压缩结果

        Args:
            note_id: 笔记 ID
            context: 压缩上下文
        """
        if self._l1_cache is None:
            return
        try:
            await self._l1_cache.set(
                key=f"compressed:{note_id}",
                value=json.dumps({"context": context, "note_id": str(note_id)}, ensure_ascii=False),
                ttl=_COMPRESSED_CACHE_TTL,
            )
        except Exception:
            # 缓存失败降级跳过（不影响主流程）
            return

    @staticmethod
    def _build_compress_prompt(
        retrieved_docs: list[SearchResult],
        query: str,
        key_entities: list[dict[str, Any]],
    ) -> str:
        """构建压缩 prompt

        Args:
            retrieved_docs: 检索结果
            query: 原始查询
            key_entities: 关键实体列表

        Returns:
            LLM 输入 prompt
        """
        context_parts: list[str] = []
        for i, r in enumerate(retrieved_docs[:_DOCUMENT_CONTEXT_LIMIT], 1):
            if not isinstance(r, dict):
                continue
            payload = r.get("payload", {})
            if not isinstance(payload, dict):
                continue
            content = payload.get("content") or payload.get("summary_text") or ""
            if content:
                context_parts.append(f"[文档 {i}]\n{content[:_DOCUMENT_PREVIEW_CHARS]}")

        context_text = "\n\n".join(context_parts)
        entity_text = ", ".join(e.get("name", "") for e in key_entities if e.get("name"))

        return (
            f"请基于以下检索文档，为查询「{query}」生成摘要。\n\n"
            f"关键实体（需覆盖）：{entity_text}\n\n"
            f"检索文档：\n{context_text}\n\n"
            f"要求：\n"
            f"1. 保留核心事实、数据、结论和推理链\n"
            f"2. 覆盖关键实体\n"
            f"3. 压缩率≥70%，去除冗余"
        )

    @staticmethod
    def _build_context(summary_text: str, query: str) -> str:
        """构建最终上下文

        Args:
            summary_text: 摘要文本
            query: 原始查询

        Returns:
            格式化的上下文文本（截断至 _CONTEXT_SIZE_LIMIT）
        """
        return "".join([f"查询：{query}\n\n", summary_text])[:_CONTEXT_SIZE_LIMIT]

    @staticmethod
    def _truncate_context(context: str) -> str:
        """截断上下文至上限

        Args:
            context: 待截断的上下文

        Returns:
            截断后的上下文
        """
        return context[:_CONTEXT_SIZE_LIMIT]

    @staticmethod
    def _estimate_tokens(docs: list[SearchResult]) -> int:
        """估算文档 token 总数

        按 4 字符/token 粗略估算（CJK 密度更高，此处取保守值）。

        Args:
            docs: 检索结果列表

        Returns:
            估算的 token 数
        """
        total_chars = 0
        for r in docs:
            if not isinstance(r, dict):
                continue
            payload = r.get("payload", {})
            if not isinstance(payload, dict):
                continue
            content = payload.get("content") or payload.get("summary_text") or ""
            total_chars += len(str(content))
        return max(total_chars // 4, 1)

    @staticmethod
    def _estimate_chars_tokens(text: str) -> int:
        """估算文本 token 数

        Args:
            text: 文本

        Returns:
            估算的 token 数
        """
        return max(len(text) // 4, 1)


__all__ = [
    "CompressedContext",
    "ContextCompressor",
]
