"""语义分块基础设施实现

实现 SemanticChunkerPort 端口协议，基于规则驱动的语义边界检测和令牌预算聚合。
v4 增强：BGE-M3 精准 token 计数 + 上下文前缀 + Child-Parent 双层索引。
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import uuid
from typing import Any, Callable

from src.domain.exceptions.storage_exceptions import ChunkingError
from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedTable
from src.domain.value_objects.semantic_chunk import (
    ChunkBoundaryType,
    ChunkingConfig,
    IndexLevel,
    SemanticChunk,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BGE-M3 精准 token 计数
# ---------------------------------------------------------------------------


# BGE-M3 tokenizer 路径解析逻辑
# 优先级: SISYS_BGE_M3_TOKENIZER_PATH → EMBEDDING_MODEL_PATH + /tokenizer.json → 默认路径
def _resolve_tokenizer_path() -> str:
    """解析 BGE-M3 tokenizer.json 文件路径

    优先级：
    1. SISYS_BGE_M3_TOKENIZER_PATH 环境变量（精确指定 tokenizer.json 路径）
    2. EMBEDDING_MODEL_PATH 环境变量 + /tokenizer.json（与 embedding 服务共享模型目录）
    3. 默认路径（与 .env 中 EMBEDDING_MODEL_PATH 一致）
    """
    # 精确路径优先
    if "SISYS_BGE_M3_TOKENIZER_PATH" in os.environ:
        return os.environ["SISYS_BGE_M3_TOKENIZER_PATH"]

    # 从 EMBEDDING_MODEL_PATH 推导（与 embedding 服务同源）
    model_path = os.environ.get("EMBEDDING_MODEL_PATH", "")
    if model_path:
        return os.path.join(model_path, "tokenizer.json")

    # 最终 fallback（与 .env 中 EMBEDDING_MODEL_PATH 默认值一致）
    return "/mnt/x/.cache/BAAI/bge-m3/models--BAAI--bge-m3/tokenizer.json"


_BGE_M3_TOKENIZER_PATH = _resolve_tokenizer_path()

# 模块级惰性加载的 tokenizer 实例（线程安全）
_bge_m3_tokenizer: Any = None
_bge_m3_load_attempted: bool = False
_bge_m3_lock: threading.Lock = threading.Lock()


def _get_bge_m3_tokenizer() -> Any:
    """惰性加载 BGE-M3 tokenizer（模块级单例）

    首次调用时从本地文件加载 tokenizer.json，后续调用复用实例。
    加载失败时返回 None，调用方应降级为 estimate_tokens()。

    Returns:
        tokenizers.Tokenizer 实例，或 None（加载失败时）
    """
    global _bge_m3_tokenizer, _bge_m3_load_attempted

    # 快速路径：已加载则直接返回（不需要加锁）
    if _bge_m3_load_attempted:
        return _bge_m3_tokenizer

    # 双重检查锁定（double-checked locking）：确保仅初始化一次
    with _bge_m3_lock:
        if _bge_m3_load_attempted:
            return _bge_m3_tokenizer

        _bge_m3_load_attempted = True
        try:
            import tokenizers

            _bge_m3_tokenizer = tokenizers.Tokenizer.from_file(_BGE_M3_TOKENIZER_PATH)
            logger.info("BGE-M3 tokenizer 已加载: %s", _BGE_M3_TOKENIZER_PATH)
        except FileNotFoundError:
            logger.warning(
                "BGE-M3 tokenizer 文件不可用: %s，降级为字符启发式 token 估算",
                _BGE_M3_TOKENIZER_PATH,
            )
            _bge_m3_tokenizer = None
        except ImportError:
            logger.warning("tokenizers 库不可用，降级为字符启发式 token 估算。安装: pip install tokenizers")
            _bge_m3_tokenizer = None
        except Exception as e:
            logger.warning("BGE-M3 tokenizer 加载失败: %s，降级为字符启发式 token 估算", e)
            _bge_m3_tokenizer = None

    return _bge_m3_tokenizer


def _count_tokens_bge_m3(text: str) -> int:
    """使用 BGE-M3 XLM-RoBERTa tokenizer 精确计算 token 数量

    当 tokenizer 不可用时，自动降级为 estimate_tokens() 并记录 WARNING。

    Args:
        text: 待计数的文本

    Returns:
        精确的 token 数量（至少 1；空字符串返回 0）
    """
    if not text:
        return 0

    tokenizer = _get_bge_m3_tokenizer()
    if tokenizer is None:
        return estimate_tokens(text)

    try:
        encoding = tokenizer.encode(text)
        return max(1, len(encoding.ids))
    except Exception:
        logger.warning("BGE-M3 tokenizer 编码失败，降级为字符启发式")
        return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    """字符启发式 token 估算（领域层纯函数，零依赖）。

    参考 XLM-RoBERTa（SentencePiece）tokenizer 的字符比例：
    - 中文字符 ≈ 1.25 字符/token → 1 token ≈ 0.8 中文字符
    - 英文词 ≈ 0.83 词/token → 1 token 约覆盖 5 英文字符
    - 数字 ≈ 1 token 覆盖 4 个数字字符
    - 标点 ≈ 1 token 覆盖 2 个标点字符
    - 空白字符 ≈ 1 token 覆盖 4 个空白字符

    精度：启发式 vs XLM-RoBERTa tokenizer 误差 <20%。

    Args:
        text: 待估算的文本

    Returns:
        估算的 token 数（至少 1）
    """
    if not text:
        return 0

    total_tokens: float = 0

    # 中文字符范围（Unicode CJK 统一表意文字）
    cjk_pattern = re.compile(r"[一-鿿㐀-䶿豈-﫿]")
    cjk_chars = cjk_pattern.findall(text)
    total_tokens += len(cjk_chars) * 0.8

    # 英文单词（按 5 字符/词估算）
    word_pattern = re.compile(r"[a-zA-Z]+")
    for word in word_pattern.findall(text):
        total_tokens += len(word) / 5

    # 数字（按 4 字符/数字 token 估算）
    digit_pattern = re.compile(r"[0-9]+")
    for num in digit_pattern.findall(text):
        total_tokens += len(num) / 4

    # 其他字符（标点、特殊符号等）
    other_pattern = re.compile(r"[^\w\s]")
    other_count = len(other_pattern.findall(text))
    total_tokens += other_count * 0.5

    # 空白字符
    total_tokens += text.count(" ") * 0.25
    total_tokens += text.count("\n") * 0.25

    return max(1, round(total_tokens))


class SemanticChunkerImpl:
    """语义分块器实现

    基于规则驱动的语义边界检测和令牌预算聚合，零 ML 模型依赖。

    算法流程：
    1. 遍历 ParsedDocument.pages（page_number 升序）
    2. 每页内按阅读顺序迭代元素的 content
    3. 检测语义边界并切分段落
    4. 按 ChunkingConfig 聚合段落为目标大小分块
    5. 生成 SemanticChunk 列表（含完整元数据）
    """

    def __init__(self) -> None:
        """初始化语义分块器"""
        # 预热 tokenizer（首调用时加载，后续复用模块级单例）
        _get_bge_m3_tokenizer()

    async def chunk(
        self,
        parsed_doc: ParsedDocument,
        config: ChunkingConfig | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[SemanticChunk]:
        """对解析完成的结构化文档执行语义分块

        v4 增强：
        - BGE-M3 精准 token 计数（替代字符启发式）
        - 上下文前缀拼接（从 doc_metadata["doc_title"] + 标题链构建）
        - Child-Parent 双层索引（cfg.child_chunk_size_tokens 非 None 时触发）

        Args:
            parsed_doc: 解析完成的结构化文档
            config: 分块配置（为 None 时使用默认值）
            metadata: 文档级元数据（透传到每个分块；含 doc_title, business_domain 等）

        Returns:
            SemanticChunk 列表（空文档返回空列表，不抛异常）

        Raises:
            ChunkingError: 分块算法内部异常（如不可序列化的数据结构）
        """
        try:
            cfg = config or ChunkingConfig()
            document_id = parsed_doc.document_id
            doc_metadata = metadata or {}

            # v4: 根据配置选择 token 计数函数
            if cfg.token_count_type == "heuristic":
                _count_fn = estimate_tokens
            else:
                _count_fn = _count_tokens_bge_m3

            # 提取所有文本片段
            segments = list(self._extract_segments(parsed_doc))

            if not segments:
                return []

            # 聚合片段为分块（使用配置指定的 token 计数函数）
            chunks = self._aggregate_segments(segments, cfg, document_id, doc_metadata, _count_fn)

            # v4: Child-Parent 双层切分
            if cfg.child_chunk_size_tokens is not None and cfg.parent_chunk_size_tokens is not None:
                chunks = self._split_child_parent(chunks, cfg)

            return chunks
        except (ValueError, TypeError, KeyError) as e:
            try:
                doc_uuid = uuid.UUID(parsed_doc.document_id)
            except (ValueError, TypeError):
                doc_uuid = uuid.uuid4()
            raise ChunkingError(
                document_id=doc_uuid,
                reason=f"语义分块内部异常: {e}",
                cause=e,
            )

    def _extract_segments(
        self,
        doc: ParsedDocument,
    ) -> list[tuple[ChunkBoundaryType, str, int]]:
        """提取所有文本片段及其边界类型和页码

        Args:
            doc: 解析完成的结构化文档

        Yields:
            (boundary_type, text, page_number) 元组
        """
        segments: list[tuple[ChunkBoundaryType, str, int]] = []
        prev_page = 0

        for page in doc.pages:
            current_page = page.page_number

            # 跨页检测：页码变化时插入 PAGE_BREAK 边界
            if prev_page > 0 and current_page != prev_page:
                segments.append((ChunkBoundaryType.PAGE_BREAK, "", current_page))
            prev_page = current_page

            # 处理文本元素
            for element in page.texts:
                boundary = self._classify_boundary(element)
                content = element.content.strip()
                if not content:
                    continue

                # PDF/HTML 等大块文本需要二次段落分割
                if boundary == ChunkBoundaryType.PARAGRAPH and len(content) > 500:
                    # 先尝试双换行分割（PDF/Word 段落分隔）
                    sub_paragraphs = re.split(r"\n\s*\n", content)
                    if len(sub_paragraphs) <= 1:
                        # 无双换行，按单换行分句聚合（HTML 分隔符为 \n）
                        sub_paragraphs = [line.strip() for line in content.split("\n") if line.strip()]

                    for para in sub_paragraphs:
                        para = para.strip()
                        if para:
                            segments.append((ChunkBoundaryType.PARAGRAPH, para, current_page))
                else:
                    segments.append((boundary, content, current_page))

            # 处理表格元素
            for table in page.tables:
                if not table.rows:  # 跳过空表格
                    continue
                text = self._flatten_table(table)
                segments.append((ChunkBoundaryType.TABLE, text, current_page))

        return segments

    def _classify_boundary(self, element: ParsedElement) -> ChunkBoundaryType:
        """根据元素 metadata 分类边界类型

        支持多种标题格式归一化：
        - Markdown/HTML: "h1"~"h6" → SECTION_HEADER
        - Word: "Heading 1"~"Heading 9" → SECTION_HEADER
        - Word 变体: "Heading 1 Char" 等含 "heading" 子串的样式 → SECTION_HEADER
        - 其他/无 style → PARAGRAPH

        Args:
            element: 解析元素

        Returns:
            边界类型
        """
        style = element.metadata.get("style", "")
        if not style:
            return ChunkBoundaryType.PARAGRAPH

        style_lower = style.lower()

        # Markdown/HTML 格式: "h1"~"h6"（严格正则匹配，避免误判）
        if re.match(r"^h[1-6]$", style_lower):
            return ChunkBoundaryType.SECTION_HEADER

        # Word 格式: "Heading 1"~"Heading 9"
        if re.match(r"^heading [1-9]$", style_lower):
            return ChunkBoundaryType.SECTION_HEADER

        # Word 变体: 含 "heading" 子串的样式
        if "heading" in style_lower:
            return ChunkBoundaryType.SECTION_HEADER

        return ChunkBoundaryType.PARAGRAPH

    def _flatten_table(self, table: ParsedTable) -> str:
        """将 ParsedTable 展平为 pipe-separated 结构化文本

        Args:
            table: 表格解析结果

        Returns:
            结构化文本字符串
        """
        lines: list[str] = []
        caption = table.table_caption or ""
        prefix = f"[表格: {caption}]" if caption else "[表格]"
        lines.append(prefix)

        if table.header:
            lines.append("| " + " | ".join(table.header) + " |")

        for row in table.rows:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _aggregate_segments(
        self,
        segments: list[tuple[ChunkBoundaryType, str, int]],
        cfg: ChunkingConfig,
        document_id: str,
        doc_metadata: dict[str, Any],
        count_fn: Callable[[str], int] | None = None,
    ) -> list[SemanticChunk]:
        """按 token 预算聚合片段为分块

        Args:
            segments: 片段列表（boundary_type, text, page_number）
            cfg: 分块配置
            document_id: 文档标识符
            doc_metadata: 文档级元数据

        Returns:
            SemanticChunk 列表
        """
        chunks: list[SemanticChunk] = []
        current_parts: list[tuple[ChunkBoundaryType, str, int]] = []
        current_tokens = 0
        chunk_index = 0

        # 默认使用 bge-m3，可通过 count_fn 覆盖
        _count = count_fn if count_fn is not None else _count_tokens_bge_m3

        for boundary, text, page in segments:
            text_tokens = _count(text)

            # PAGE_BREAK 边界：创建新分块后跳过追加
            if boundary == ChunkBoundaryType.PAGE_BREAK:
                if current_parts:
                    chunks.append(self._create_chunk(current_parts, chunk_index, document_id, page, doc_metadata, _count))
                    chunk_index += 1
                    current_parts, current_tokens = [], 0
                continue

            # 硬边界：章节/表格边界，必然创建新分块
            if boundary in (ChunkBoundaryType.SECTION_HEADER, ChunkBoundaryType.TABLE):
                if current_parts:
                    chunks.append(self._create_chunk(current_parts, chunk_index, document_id, page, doc_metadata, _count))
                    chunk_index += 1
                    current_parts, current_tokens = [], 0

            # 检查当前段落是否超过 max_chunk_size_tokens
            if text_tokens >= cfg.max_chunk_size_tokens:
                if current_parts:
                    chunks.append(self._create_chunk(current_parts, chunk_index, document_id, page, doc_metadata, _count))
                    chunk_index += 1
                    current_parts, current_tokens = [], 0

                # 按字符比例切分此大段
                sub_texts = self._split_by_token_limit(text, cfg.max_chunk_size_tokens)
                for i, sub_text in enumerate(sub_texts):
                    sub_tokens = _count(sub_text)
                    current_parts.append((ChunkBoundaryType.TOKEN_LIMIT, sub_text, page))
                    current_tokens += sub_tokens
                    if i < len(sub_texts) - 1:
                        chunks.append(self._create_chunk(current_parts, chunk_index, document_id, page, doc_metadata, _count))
                        chunk_index += 1
                        current_parts, current_tokens = [], 0
                continue

            # Token 预算：仅当 current_parts 非空且超限时触发
            if current_parts and current_tokens + text_tokens > cfg.target_chunk_size_tokens:
                chunks.append(self._create_chunk(current_parts, chunk_index, document_id, page, doc_metadata, _count))
                chunk_index += 1
                current_parts, current_tokens = [], 0

            current_parts.append((boundary, text, page))
            current_tokens += text_tokens

        # 处理剩余片段
        if current_parts:
            chunks.append(self._create_chunk(current_parts, chunk_index, document_id, page, doc_metadata, _count))

        # 合并过小分块
        return self._merge_small_chunks(chunks, cfg)

    def _create_chunk(
        self,
        parts: list[tuple[ChunkBoundaryType, str, int]],
        chunk_index: int,
        document_id: str,
        page: int,
        doc_metadata: dict[str, Any],
        count_fn: Callable[[str], int] | None = None,
    ) -> SemanticChunk:
        """从片段列表创建 SemanticChunk 值对象（v4 增强）

        v4 增强：
        - 使用 BGE-M3 精准 token 计数
        - 构建上下文前缀 chunk_header
        - content 包含前缀，token_count 不包含前缀

        Args:
            parts: 片段列表
            chunk_index: 分块索引
            document_id: 文档标识符
            page: 当前页码（用于 fallback）
            doc_metadata: 文档级元数据

        Returns:
            SemanticChunk 实例
        """
        # 聚合文本内容（不含前缀）
        texts = [t for _, t, _ in parts if t]
        raw_content = "\n\n".join(texts)

        # 页码范围
        pages = [p for _, _, p in parts]
        page_start = min(pages) if pages else page
        page_end = max(pages) if pages else page

        # 边界类型：取第一个片段的类型
        boundary_type = parts[0][0] if parts else ChunkBoundaryType.PARAGRAPH

        # v4: 构建上下文前缀
        chunk_header = self._build_chunk_header(parts, doc_metadata)

        # v4: 带前缀的完整 content
        if chunk_header:
            content = chunk_header + "\n" + raw_content
        else:
            content = raw_content

        # 内容哈希（基于带前缀的完整 content）
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # v4: BGE-M3 精准 token 计数（仅针对原始内容，不含前缀）
        _count = count_fn if count_fn is not None else _count_tokens_bge_m3
        token_count = _count(raw_content)

        # 安全转换 document_id
        try:
            doc_uuid = uuid.UUID(document_id) if document_id else uuid.uuid4()
        except (ValueError, TypeError) as e:
            # 无法转换时使用随机 UUID 作为 fallback
            fallback_uuid = uuid.uuid4()
            raise ChunkingError(
                document_id=fallback_uuid,
                reason=f"document_id 不是有效的 UUID 格式: {document_id}",
                cause=e,
            )

        return SemanticChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_uuid,
            content=content,
            chunk_index=chunk_index,
            boundary_type=boundary_type,
            token_count=token_count,
            page_start=page_start,
            page_end=page_end,
            content_hash=content_hash,
            metadata=dict(doc_metadata),
            chunk_header=chunk_header,
            index_level=IndexLevel.PARENT,
        )

    def _merge_chunks(self, chunk_a: SemanticChunk, chunk_b: SemanticChunk) -> SemanticChunk:
        """合并两个相邻分块，保持语义完整性

        Args:
            chunk_a: 前一个分块
            chunk_b: 后一个分块

        Returns:
            合并后的分块
        """
        content = chunk_a.content + "\n\n" + chunk_b.content
        return SemanticChunk(
            chunk_id=chunk_a.chunk_id,
            document_id=chunk_a.document_id,
            content=content,
            chunk_index=chunk_a.chunk_index,
            boundary_type=chunk_a.boundary_type,
            token_count=_count_tokens_bge_m3(content),
            page_start=min(chunk_a.page_start, chunk_b.page_start),
            page_end=max(chunk_a.page_end, chunk_b.page_end),
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            metadata=chunk_a.metadata,
            chunk_header=(
                chunk_a.chunk_header if len(chunk_a.chunk_header) >= len(chunk_b.chunk_header) else chunk_b.chunk_header
            ),
            index_level=IndexLevel.PARENT,
        )

    def _find_safe_split_point(self, text: str, max_chars: int) -> int:
        """在 max_chars 之前的最近语义边界处切分

        优先在换行符、句号等语义边界处切分，保持语义完整性。
        无语义边界时回退到字符级硬切分。

        Args:
            text: 待切分的文本
            max_chars: 最大字符数

        Returns:
            切分点索引（包含边界分隔符）
        """
        # 优先在换行符处切分
        candidate = text.rfind("\n", 0, max_chars)
        if candidate != -1:
            return candidate + 1
        # 其次在中文句号处切分
        candidate = text.rfind("。", 0, max_chars)
        if candidate != -1:
            return candidate + 1
        # 其次在英文句号处切分
        candidate = text.rfind(".", 0, max_chars)
        if candidate != -1:
            return candidate + 1
        # 无语义边界时回退到字符级硬切分
        return max_chars

    def _split_by_token_limit(self, text: str, max_tokens: int) -> list[str]:
        """按 token 硬限制切分文本

        优先在语义边界（换行符、句号）处切分，
        无语义边界时回退到字符级硬切分。

        Args:
            text: 待切分的文本
            max_tokens: 最大 token 数

        Returns:
            切分后的文本列表
        """
        total_tokens = _count_tokens_bge_m3(text)
        if total_tokens <= max_tokens:
            return [text]

        # 按字符比例估算每段最大字符数（应用 0.95 安全因子，
        # 因为 bge-m3 token 计数与字符比例估算之间存在方差）
        ratio = max_tokens / total_tokens
        chars_per_segment = max(1, int(len(text) * ratio * 0.95))
        segments: list[str] = []
        i = 0
        while i < len(text):
            segment_end = min(i + chars_per_segment, len(text))
            # 在语义边界处切分
            if segment_end < len(text):
                segment_end = self._find_safe_split_point(text, segment_end)
                # 防御：切分点必须严格前进，防止切分点恰好在 i 处（如边界字符
                # 位于 i-1 时 _find_safe_split_point 返回 i）导致死循环
                if segment_end <= i:
                    segment_end = i + 1
            segments.append(text[i:segment_end])
            i = segment_end
        return segments

    def _merge_small_chunks(self, chunks: list[SemanticChunk], cfg: ChunkingConfig) -> list[SemanticChunk]:
        """合并过小分块，但保持语义边界完整性

        规则：
        - 分块 token 数 < min_chunk_size_tokens 时尝试合并
        - 以 SECTION_HEADER 开头的分块：向后合并后续内容到标题分块（标题保留）
        - 以 TABLE/PAGE_BREAK 开头的分块不向后合并
        - 段落分块：向后合并到前一个分块

        Args:
            chunks: 分块列表
            cfg: 分块配置

        Returns:
            合并后的分块列表
        """
        if not chunks:
            return chunks

        merged: list[SemanticChunk] = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            if chunk.token_count < cfg.min_chunk_size_tokens and i > 0:
                first_boundary = chunk.boundary_type
                if first_boundary in (
                    ChunkBoundaryType.SECTION_HEADER,
                    ChunkBoundaryType.TABLE,
                    ChunkBoundaryType.PAGE_BREAK,
                ):
                    # 硬边界分块（含标题）：向后合并后一个分块的内容到标题分块
                    if i + 1 < len(chunks):
                        chunk = self._merge_chunks(chunk, chunks[i + 1])
                        merged.append(chunk)
                        i += 1  # 跳过已合并的后续分块
                    else:
                        merged.append(chunk)
                else:
                    # 段落分块：向后合并到前一个分块
                    merged[-1] = self._merge_chunks(merged[-1], chunk)
            else:
                merged.append(chunk)
            i += 1

        return merged

    # ------------------------------------------------------------------
    # v4 新增方法
    # ------------------------------------------------------------------

    def _build_chunk_header(
        self,
        parts: list[tuple[ChunkBoundaryType, str, int]],
        doc_metadata: dict[str, Any],
    ) -> str:
        """构建上下文前缀（v4 新增）

        对标 Anthropic Contextual Retrieval (2026)，利用解析阶段已有的
        文档标题和标题层级数据，拼结构前缀。

        格式：
        - 有文档标题 + 章节路径: [文档: 《title》→ h1_path → h2_path]
        - 仅文档标题: [文档: 《title》]
        - 无标题信息: 返回空字符串

        Args:
            parts: 片段列表
            doc_metadata: 文档级元数据（含 doc_title）

        Returns:
            上下文前缀字符串，或空字符串
        """
        doc_title = doc_metadata.get("doc_title", "")

        # 收集标题路径
        title_path: list[str] = []
        for boundary, text, _ in parts:
            if boundary == ChunkBoundaryType.SECTION_HEADER and text:
                title_path.append(text)

        # 构建前缀
        if doc_title and title_path:
            path_str = " → ".join(title_path)
            return f"[文档: 《{doc_title}》→ {path_str}]"
        elif doc_title:
            return f"[文档: 《{doc_title}》]"
        elif title_path:
            path_str = " → ".join(title_path)
            return f"[{path_str}]"
        else:
            return ""

    def _split_child_parent(
        self,
        chunks: list[SemanticChunk],
        cfg: ChunkingConfig,
    ) -> list[SemanticChunk]:
        """Child-Parent 双层切分（v4 新增）

        对标 Qdrant 1.15 Multivector group_by：
        - 父块 ~parent_chunk_size_tokens，不索引
        - 子块 ~child_chunk_size_tokens，索引 + 关联父块

        单层模式（child_chunk_size_tokens=None）时跳过此方法。

        Args:
            chunks: 聚合后的父块列表（单层模式）
            cfg: 分块配置

        Returns:
            Child + Parent 混合列表（双层模式），或原列表（单层模式）
        """
        if cfg.child_chunk_size_tokens is None:
            return chunks

        result: list[SemanticChunk] = []
        for parent in chunks:
            # 父块标记为 PARENT 层级
            parent_obj = SemanticChunk(
                chunk_id=parent.chunk_id,
                document_id=parent.document_id,
                content=parent.content,
                chunk_index=len(result),
                boundary_type=parent.boundary_type,
                token_count=parent.token_count,
                page_start=parent.page_start,
                page_end=parent.page_end,
                content_hash=parent.content_hash,
                metadata=dict(parent.metadata),
                parent_chunk_id=None,
                index_level=IndexLevel.PARENT,
                chunk_header=parent.chunk_header,
            )
            result.append(parent_obj)

            # 按 child_chunk_size_tokens 切分子块
            child_texts = self._split_by_token_limit(parent.content, cfg.child_chunk_size_tokens)
            for child_text in child_texts:
                child_tokens = _count_tokens_bge_m3(child_text)
                child_obj = SemanticChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=parent.document_id,
                    content=child_text,
                    chunk_index=len(result),
                    boundary_type=parent.boundary_type,
                    token_count=child_tokens,
                    page_start=parent.page_start,
                    page_end=parent.page_end,
                    content_hash=hashlib.sha256(child_text.encode("utf-8")).hexdigest(),
                    metadata=dict(parent.metadata),
                    parent_chunk_id=parent.chunk_id,
                    index_level=IndexLevel.CHILD,
                    chunk_header=parent.chunk_header,
                )
                result.append(child_obj)

        return result


__all__ = [
    "SemanticChunkerImpl",
    "estimate_tokens",
    "_count_tokens_bge_m3",
    "_get_bge_m3_tokenizer",
]
