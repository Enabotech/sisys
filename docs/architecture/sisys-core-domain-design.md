# SISYS 核心领域架构详细设计

> **版本:** v8.3.3（从 architecture.md §17 提取）
> **状态:** 设计参考文档
> **提取日期:** 2026-05-23
> **关联文档:** architecture.md §17, sisys-checkpoint-timetravel-design.md

---

## 17. 核心领域架构设计

> **⚠️ 本章实现状态说明：**
> 本章为设计参考文档，描述完整的领域架构愿景。各节实现状态如下：
>
> | 章节 | 设计内容 | 实现状态 | 说明 |
> |------|---------|---------|------|
> | §17.1 数据处理 | 17种格式解析、OCR、DQI、混合检索、知识图谱 | ❌ 未实现 | 规划于 Epic 2-3 |
> | §17.2 工具箱 | 23种战略工具、沙箱执行、Schema 强制 | ❌ 未实现 | 规划于 Epic 5 |
> | §17.3 Agent 架构 | 7+1角色、EIP、SYS裁决、辩论、SAP协议 | 🟡 骨架实现 | LangGraph引擎已注册，节点为MVP占位（返回硬编码字符串） |
> | §17.4 战略规划 | BLM/BEM状态机、Checkpoint恢复、Time-Travel | ❌ 未实现 | 规划于 Epic 4 |
>
> **已完整实现的核心模块：** 六边形架构框架（§1-§3）、事件总线（§10）、存储子系统（§11）、
> 端口注册与DI（§8）、统一异常体系、事务子系统（Outbox/Saga/UoW）。
> 详见 §19.7 架构就绪评估中的实现完成度矩阵。

[重要说明]本章设计仅供开发参考，执行[EPIC]-[STORY]-[编码]等开发任务时按需调整并及时更新本文档即可！

### 17.1 数据处理架构设计

**设计哲学：** 将多模态非结构化数据（文本/表格/图像/公式/音视频转录）转化为模型可理解、可检索、可推理、可溯源的结构化知识资产。

#### 17.1.1 数据处理全流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        数据处理全流程架构                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ 1. 数据接入  │ →  │ 2. 解析提取  │ →  │ 3. 质量治理  │              │
│  │ - 17 种格式   │    │ - OCR/版面   │    │ - DQI 评分    │              │
│  │ - 断点续传   │    │ - 表格语义   │    │ - 去重清洗   │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ 6. 归档存储  │ ←  │ 5. 知识图谱  │ ←  │ 4. 向量化    │              │
│  │ - WORM 存储   │    │ - 实体抽取   │    │ - BGE-M3     │              │
│  │ - 版本快照   │    │ - 关系构建   │    │ - 混合检索   │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 17.1.2 数据接入层（17 种格式支持）

**支持格式清单：**

| 格式类别 | 具体格式 | 解析引擎 | 特殊处理 |
|---------|---------|---------|---------|
| **文档类** | PDF, DOC, DOCX | Unstructured.io + PDF.js | 版面保留 + Bounding Box |
| **演示类** | PPT, PPTX | Unstructured.io + 自研 | 幻灯片顺序 + 备注提取 |
| **表格类** | XLS, XLSX, CSV | OpenPyXL + Pandas | 合并单元格语义还原 |
| **文本类** | TXT, Markdown | 原生解析 | 编码自动检测 |
| **网页类** | HTML | BeautifulSoup | DOM 树解析 + 正文提取 |
| **图像类** | JPEG, PNG, GIF | Tesseract OCR + CLIP | 图文联合嵌入 |
| **压缩包** | ZIP, TAR | 原生解压 | 递归解析内部文件 |
| **音视频** | 转录文本 | 外部 API 对接 | 时间戳对齐 |

**断点续传实现：**

```python
class ResumableUpload:
    """支持断点续传的分片上传"""

    CHUNK_SIZE = 10 * 1024 * 1024  # 10MB per chunk
    MAX_FILE_SIZE = 20 * 1024 * 1024 * 1024  # 20GB total

    async def upload(self, file: UploadFile, user_id: str) -> UploadResult:
        # 1. 生成文件指纹
        file_hash = await self.calculate_hash(file)

        # 2. 检查是否已存在（秒传）
        existing = await self.check_existing(file_hash)
        if existing:
            return UploadResult(status="exists", file_id=existing.id)

        # 3. 分片上传
        upload_id = await self.initiate_multipart(file.filename)
        chunks = []

        for offset in range(0, file.size, self.CHUNK_SIZE):
            chunk = await file.read(self.CHUNK_SIZE)
            chunk_etag = await self.upload_chunk(upload_id, offset, chunk)
            chunks.append({"offset": offset, "etag": chunk_etag})

            # 保存上传进度（支持断点续传）
            await self.save_progress(upload_id, offset, chunks)

        # 4. 合并分片
        file_id = await self.complete_multipart(upload_id, chunks)

        return UploadResult(status="success", file_id=file_id)
```

#### 17.1.3 解析提取层（高保真深层解析）

**版面保留模式（DocLayNet 标准）：**

```python
class LayoutPreservingParser:
    """版面保留解析器 - 记录元素坐标"""

    async def parse(self, document: Document) -> ParsedDocument:
        elements = []

        for page in document.pages:
            # 1. 版面分析（检测文本/表格/图像/公式）
            layout_blocks = await self.detect_layout(page)

            for block in layout_blocks:
                # 2. 提取元素
                element = {
                    "type": block.type,  # text/table/image/formula
                    "content": block.content,
                    "bbox": {
                        "x": block.x,
                        "y": block.y,
                        "width": block.width,
                        "height": block.height,
                        "page": page.number
                    },
                    "confidence": block.confidence
                }

                # 3. 表格特殊处理（行列语义）
                if block.type == "table":
                    element["table_structure"] = await self.parse_table(block)

                # 4. 公式支持（LaTeX + MathML 双格式）
                if block.type == "formula":
                    element["latex"] = block.latex
                    element["mathml"] = block.mathml

                elements.append(element)

        return ParsedDocument(elements=elements, format="DocLayNet")
```

**OCR 解析（置信度管理）：**

```python
class OCRProcessor:
    """OCR 处理器 - 支持中英文 + 置信度管理"""

    CONFIDENCE_THRESHOLD = 0.85

    async def process(self, image: ImageDocument) -> OCRResult:
        # 1. OCR 识别
        ocr_result = await self.tesseract.recognize(image)

        # 2. 置信度标注
        low_confidence_regions = []
        for text_block in ocr_result.blocks:
            if text_block.confidence < self.CONFIDENCE_THRESHOLD:
                low_confidence_regions.append({
                    "text": text_block.content,
                    "confidence": text_block.confidence,
                    "bbox": text_block.bbox,
                    "flag": "needs_review"
                })

        # 3. 低置信度标记（待人工复核）
        if low_confidence_regions:
            ocr_result.flag = "partial_review_needed"
            ocr_result.review_regions = low_confidence_regions

        return ocr_result
```

#### 17.1.4 质量治理层（数据质量控制）

**复合数据质量基准（DQI）：**

```python
class DataQualityAssessor:
    """数据质量评估器 - DQI 综合评分"""

    # DQI = 0.4*完整性 + 0.3*唯一性 + 0.3*时效性

    async def assess(self, document: ParsedDocument) -> DQIScore:
        # 1. 完整性评分（正文长度>100 字符）
        completeness = min(len(document.text) / 100, 1.0)

        # 2. 唯一性评分（SIMHash 去重）
        similarity = await self.calculate_similarity(document)
        uniqueness = 1.0 - similarity

        # 3. 时效性评分（文档日期）
        age_days = (datetime.now() - document.publish_date).days
        timeliness = max(0, 1.0 - age_days / 365)  # 1 年内满分

        # 4. DQI 综合评分
        dqi_score = (
            0.4 * completeness +
            0.3 * uniqueness +
            0.3 * timeliness
        )

        # 5. 质量门禁（DQI<0.6 阻断）
        if dqi_score < 0.6:
            return DQIScore(
                score=dqi_score,
                status="blocked",
                reason="DQI below threshold"
            )

        return DQIScore(
            score=dqi_score,
            status="passed",
            breakdown={
                "completeness": completeness,
                "uniqueness": uniqueness,
                "timeliness": timeliness
            }
        )
```

#### 17.1.5 向量化与检索层（混合检索架构）

**端口层次设计（R1/R2 架构规则）：**

```
R1: 领域层统一抽象基础端口
    SearchServicePort（基础检索端口）
    ├── DenseSearchPort（Dense 语义检索）
    ├── SparseSearchPort（BM25 稀疏检索）
    └── GraphSearchPort（Graph 图检索）

R2: 应用层组合/继承领域层端口
    └── HybridSearchPort（组合三路检索，RRF 融合 + 重排序）
```

**领域层端口定义（零外部依赖，仅 Protocol）：**

```python
@runtime_checkable
class SearchServicePort(Protocol):
    """R1: 基础检索端口 — 统一检索签名"""

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        ...

@runtime_checkable
class DenseSearchPort(SearchServicePort, Protocol):
    """Dense 语义检索端口（继承基础检索端口）"""
    pass

@runtime_checkable
class SparseSearchPort(SearchServicePort, Protocol):
    """BM25 稀疏检索端口（继承基础检索端口）"""
    pass

@runtime_checkable
class GraphSearchPort(SearchServicePort, Protocol):
    """Graph 图检索端口（继承基础检索端口）"""
    pass

@runtime_checkable
class HybridSearchPort(Protocol):
    """R2: 混合检索端口 — 组合 Dense+Sparse+Graph 三路 RRF 融合"""
    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
        weights: list[float] | None = None,
    ) -> list[SearchResult]:
        ...
```

**文件位置：**
- `src/domain/ports/search_service.py` — SearchServicePort / DenseSearchPort / SparseSearchPort / GraphSearchPort
- `src/domain/ports/hybrid_search.py` — HybridSearchPort

**应用层实现（实现端口，注入领域层端口）：**

```python
class DenseSemanticSearchService(DenseSearchPort):
    """编排 EmbeddingServicePort（文本→向量）和 L3VectorPort（向量→检索）"""
    def __init__(self, embedding_service: EmbeddingServicePort, vector_storage: L3VectorPort) -> None:
        ...

class Bm25SparseSearchService(SparseSearchPort):
    """编排 EmbeddingServicePort（文本→稀疏向量）和 L3VectorPort（稀疏向量→检索）"""
    def __init__(self, embedding_service: EmbeddingServicePort, vector_storage: L3VectorPort) -> None:
        ...

class GraphSearchService(GraphSearchPort):
    """通过 L5GraphPort 搜索实体关联，作为第三路检索信号"""
    def __init__(self, l5_graph: L5GraphPort) -> None:
        ...

class HybridSearchService(HybridSearchPort):
    """三路并行检索 → RRF 融合 → 可选重排序

    降级策略：
    - 三路均成功 → 三路加权 RRF 融合
    - Graph 失败 → 两路（Dense + Sparse）RRF 融合
    - Dense + Sparse 均失败 → 单路 Graph 结果
    - 三路均失败 → HybridSearchError
    """
    def __init__(
        self,
        dense_search: DenseSearchPort,
        sparse_search: SparseSearchPort,
        fuse: Callable[..., list[SearchResult]],
        graph_search: GraphSearchPort | None = None,
        weights: list[float] | None = None,
        reranker: RerankerPort | None = None,
    ) -> None:
        ...
```

**架构说明：**
- ✅ **领域层**：`SearchServicePort` 基础端口定义（零外部依赖，R1 规则）
- ✅ **领域层**：`HybridSearchPort` 组合端口定义（R2 规则，组合三路检索）
- ✅ **应用层**：`Dense/Sparse/Graph/HybridSearchService` 实现端口（注入领域层端口）
- ✅ **基础设施层**：`QdrantAdapter` 实现 `L3VectorPort`，`EmbeddingAPIClient` 实现 `EmbeddingServicePort`
- ✅ **依赖注入**：`composition_root.py` 统一注册，通过 `Resolver` 自动装配

#### 17.1.5.1 检索 - 压缩循环机制（Retrieval-Compression Loop）

**设计哲学：** 遵循系统公理二"外部化记忆"，LLM 上下文=缓存，磁盘记忆=真相源。检索后必须执行压缩，压缩前必须持久化，防止信息丢失。

**循环流程：**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      检索 - 压缩循环（Retrieval-Compression Loop）       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 检索（Retrieval）                                                    │
│     │  输入：用户查询 query                                             │
│     │  输出：Top-100 候选文档（Dense+Sparse+Graph 三路召回）             │
│     │  延迟预算：P95<500ms（初检 200ms+ 融合 50ms+ 精排 250ms）           │
│     ▼                                                                   │
│  2. 持久化笔记（Persistent Note-Taking）← 压缩前必须执行！               │
│     │  输入：retrieved_docs（与步骤 3 共享）                             │
│     │  步骤：                                                           │
│     │  2.1 提取关键实体与关系 → 写入 StrategicArchive（L0-L5 六层存储）    │
│     │  2.2 生成结构化摘要（JSON Schema 强制）→ 写入 PostgreSQL           │
│     │  2.3 记录检索血缘（query/top_k/时间戳/用户 ID）→ 审计日志          │
│     │  输出：PersistentNote（note_id, entities, summary, lineage）        │
│     │  注意：此步骤为压缩的前置条件，但与步骤 3 共享输入数据             │
│     ▼                                                                   │
│  3. 压缩（Compression）                                                  │
│     │  输入：retrieved_docs + query + persistent_note（来自步骤 2）       │
│     │  算法：LLM 摘要生成（Temperature=0.3） + 关键信息抽取             │
│     │  压缩目标：100 文档（~50K tokens）→ 压缩至 5-10 个关键段落（~2K tokens）│
│     │  压缩率：≥70%（验收标准，实际~96%）                                │
│     │  质量评估：信息熵 + 关键实体覆盖率（评分<0.7 触发二次生成）        │
│     │  注意：压缩使用 persistent_note 中的 entities 作为关键信息抽取依据  │
│     ▼                                                                   │
│  4. LLM 上下文注入（Context Injection）                                  │
│     │  输入：压缩后的关键段落（~2K tokens）                             │
│     │  操作：注入至 LLM 上下文窗口（仅保留当前任务必需信息）             │
│     │  防止：上下文爆炸（>128K tokens 时性能下降）                       │
│     ▼                                                                   │
│  5. 生成与验证（Generation & Validation）                                │
│     │  LLM 基于压缩上下文生成答案                                       │
│     │  Auditor 验证事实一致性（引用源可追溯）                           │
│     │  验证失败 → 返回步骤 1 重新检索（扩展查询/放宽阈值）               │
│     ▼                                                                   │
│  6. 反馈与演进（Feedback & Evolution）                                   │
│     │  用户修正 → 修正分级判定（L0-L3）                                 │
│     │  高频修正模式 → Few-Shot 样本 → Prompt 优化                       │
│     └──────────────────────────────────────────→ 返回步骤 1（循环）      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**持久化笔记详细实现（压缩前必须执行）：**

```python
# 文件位置：src/domain/services/persistent_note_taker.py

@dataclass(frozen=True)
class PersistentNote:
    """持久化笔记值对象

    检索-压缩循环中，压缩前必须完成持久化的笔记数据。

    Attributes:
        note_id: 笔记唯一标识
        query: 原始查询文本
        user_id: 发起用户 ID
        session_id: 会话 ID
        entities: 提取的关键实体（Top-20，序列化 dict 列表）
        lineage: 检索血缘记录
        summary: 结构化摘要
        persisted: 是否已完成持久化（压缩前校验必须为 True）
        persisted_at: 持久化完成时间
    """
    note_id: UUID = field(default_factory=uuid4)
    query: str = ""
    user_id: str = ""
    session_id: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    extraction_result: ExtractionResult = field(default_factory=...)
    lineage: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    persisted: bool = False
    persisted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 L1 缓存存储）"""
        ...


class PersistentNoteTaker:
    """持久化笔记记录器 - 压缩前必须调用

    注入：EntityExtractionPort + AuditServicePort + L1CachePort
    """

    async def take_notes(
        self,
        query: str,
        retrieved_docs: list[SearchResult],
        user_id: str,
        session_id: str,
    ) -> PersistentNote:
        """
        执行持久化笔记步骤

        流程：
        1. 提取关键实体与关系 → EntityExtractionPort（失败降级为空实体列表）
        2. 构建检索血缘（query/top_k/document_ids/user_id/session_id/timestamp）
        3. 记录检索血缘 → AuditServicePort（L2+L4 双存储，失败降级跳过）
        4. 持久化完成标记（persisted=True）+ 序列化至 L1 缓存（TTL 30 天）
        """
        ...

    @staticmethod
    def verify_persisted(note: PersistentNote) -> bool:
        """验证持久化是否完成（压缩前检查）"""
        return note.persisted and note.persisted_at is not None
```

**压缩算法详细实现：**

```python
# 文件位置：src/domain/services/context_compressor.py

@dataclass(frozen=True)
class CompressedContext:
    """压缩上下文值对象

    Attributes:
        context: 压缩后的上下文文本（~2K tokens）
        compression_ratio: 压缩率（≥0.70）
        quality_score: 质量评分（0-1，<0.7 触发二次生成）
        token_count: 压缩后 token 数（估算）
        original_token_count: 原始 token 数（估算）
        persistent_note_ref: 关联的持久化笔记 ID
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
    """上下文压缩器 - 遵循系统公理二

    注入：LLMClientPort + PersistentNoteTaker + CompressionQualityEvaluator（可选）+ L1CachePort（可选）
    """

    COMPRESSION_RATIO_TARGET = 0.70
    CONTEXT_SIZE_LIMIT = 2000

    async def compress(
        self,
        retrieved_docs: list[SearchResult],
        query: str,
        persistent_note: PersistentNote,
    ) -> CompressedContext:
        """
        压缩检索结果至 LLM 上下文

        前置条件：persistent_note 已验证（压缩前必须持久化）
        流程：
        1. verify_persisted() 前置检查（失败抛出 EntityValidationError）
        2. LLM 摘要生成（Temperature=0.3，低温度保证稳定性）
        3. 压缩率验证（≥70%，不足触发二次压缩 _recompress()）
        4. 质量评估（信息熵 + 实体覆盖率 + 冗余度，<0.7 触发二次生成 _regenerate()）
        5. 压缩结果缓存至 L1（TTL 24 小时，失败降级跳过）
        """
        ...
```

**质量评估器（压缩后验证）：**

```python
# 文件位置：src/domain/services/compression_quality_evaluator.py

class CompressionQualityEvaluator:
    """压缩质量评估器 - 信息熵 + 关键实体覆盖率 + 冗余度

    评分维度：
    1. 信息熵（40%）：基于字符分布多样性的 Shannon 熵
    2. 关键实体覆盖率（40%）：Top-20 关键实体保留比例
    3. 冗余度（20%）：基于 n-gram 重复检测

    评分 < 0.7 触发二次生成。
    纯计算，无外部调用（P95 < 50ms），领域层零外部依赖。
    """

    async def evaluate(
        self,
        compressed_context: str,
        original_docs: list[SearchResult],
        key_entities: list[dict[str, Any]],
    ) -> float:
        """
        评估压缩质量

        1. 信息熵评分：_calculate_entropy() → Shannon 熵归一化
        2. 关键实体覆盖率：_calculate_coverage() → 实体在文本中出现比例
        3. 冗余度评分：_calculate_redundancy() → n-gram 重复检测
        4. 综合评分：0.40*熵 + 0.40*覆盖率 + 0.20*冗余度
        """
        ...

**验收标准：**

| 指标 | MVP 目标 | V1 目标 | V2 目标 | 测量方式 |
|------|---------|--------|--------|---------|
| **压缩率** | ≥70% | ≥75% | ≥80% | Prometheus |
| **质量评分** | ≥0.7 | ≥0.75 | ≥0.8 | 信息熵 + 实体覆盖率 |
| **持久化完成率** | 100% | 100% | 100% | 审计日志 |
| **循环延迟 P95** | <2s | <1.5s | <1s | 链路追踪 |

---

#### 17.1.6 知识图谱层（GraphRAG 增强）

**LLM+ 规则混合实体抽取：**

```python
class HybridEntityExtractor:
    """混合实体抽取器 - 规则高准确率 + LLM 高召回率"""

    async def extract(self, document: ParsedDocument) -> List[Entity]:
        # 1. 规则基抽取（高准确率≥80%）
        rule_entities = await self.rule_based_extract(document)
        # - 领域词典 AC 自动机匹配
        # - 正则模式（日期/金额/百分比）
        # - 依存句法分析

        # 2. LLM 语义抽取（高召回率）
        llm_entities = await self.llm_extract(document)
        # - Few-Shot + CoT + Schema 约束

        # 3. 冲突仲裁（规则权重 0.6 / LLM 权重 0.4）
        merged_entities = []
        for entity in rule_entities + llm_entities:
            if entity in merged_entities:
                # 置信度融合：查找同源实体
                existing = merged_entities[merged_entities.index(entity)]
                rule_entity = next((e for e in rule_entities if e.id == entity.id), None)
                llm_entity = next((e for e in llm_entities if e.id == entity.id), None)
                if rule_entity and llm_entity:
                    existing.confidence = 0.6 * rule_entity.confidence + 0.4 * llm_entity.confidence
            else:
                merged_entities.append(entity)

        return merged_entities
```

#### 17.1.7 高保真溯源（Bounding Box 级）

**溯源跳转实现：**

```python
class CitationTracer:
    """高保真溯源追踪器"""

    async def trace(self, claim: str) -> CitationResult:
        # 1. 检索相关文档切片
        chunks = await self.retriever.retrieve(claim, top_k=10)

        # 2. 计算引用置信度
        citations = []
        for chunk in chunks:
            similarity = cosine_similarity(claim, chunk.text)
            if similarity > 0.7:  # 阈值
                citations.append({
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "text": chunk.text,
                    "confidence": similarity,
                    "bbox": chunk.bbox,  # Bounding Box 坐标
                    "page": chunk.page_number
                })

        # 3. 溯源树构建
        citation_tree = self.build_citation_tree(citations)

        return CitationResult(
            claim=claim,
            citations=citation_tree,
            highest_confidence=max(c.confidence for c in citations) if citations else 0
        )
```

---

### 17.2 工具箱架构设计

**设计哲学：** 23 种战略工具通过 CLI + Skills 机制暴露给内部 AGENT 调用，V2+ 可选通过 MCP 协议暴露给外部生态，支持工具注册、版本控制、灰度发布与回滚。

#### 17.2.1 工具箱总体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          工具箱架构全景图                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CLI + Skills 协议层（MVP/V1）                  │   │
│  │   - 工具注册表暴露  │  输入/输出 Schema  │  版本/可靠性评分       │   │
│  └────────────────────────────────────────────────── ─────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    MCP 协议层（V2+ 可选，外部生态）               │   │
│  │   - MCP Registry  │  外部 Agent 发现  │  mTLS 认证              │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│         ┌──────────────────────────┼──────────────────────────┐        │
│         │                          │                          │        │
│         ▼                          ▼                          ▼        │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐ │
│  │ 环境分析工具 │          │ 战略选择工具 │          │ 执行管理工具 │ │
│  │ - PESTEL     │          │ - 安索夫矩阵 │          │ - BSC        │ │
│  │ - 波特五力   │          │ - SWOT-TOWS  │          │ - 战略地图   │ │
│  │ - $APPEALS   │          │ - GE 矩阵    │          │ - KPI        │ │
│  └──────────────┘          └──────────────┘          └──────────────┘ │
│         │                          │                          │        │
│         └──────────────────────────┼──────────────────────────┘        │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    工具执行引擎                                  │   │
│  │   - DAG 编排  │  沙箱执行  │  契约验证  │  证据打包               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 17.2.2 23 种战略工具完整清单

| 工具类别 | 工具名称 | 输入 Schema | 输出 Schema | 优先级 |
|---------|---------|-----------|-----------|--------|
| **环境分析** | PESTEL 分析 | 宏观环境数据 | 六维度分析报告 | P0 |
| | 波特五力 | 行业竞争数据 | 五力模型分析 | P0 |
| | $APPEALS | 客户需求数据 | 九维度需求分析 | P0 |
| **竞争分析** | 竞争对手分析 | 竞争对手信息 | 能力雷达图 | P0 |
| | 价值链分析 | 企业内部数据 | 价值环节分析 | P1 |
| | VRIO 框架 | 资源能力清单 | 竞争力评估 | P1 |
| **战略选择** | 安索夫矩阵 | 市场/产品数据 | 增长战略建议 | P0 |
| | SWOT-TOWS | 内外因素分析 | 策略匹配矩阵 | P0 |
| | GE-麦肯锡矩阵 | 业务单元数据 | 业务组合图谱 | P0 |
| | SPACE 矩阵 | 战略定位数据 | 定位分析结果 | P1 |
| | 情景规划 | 趋势数据 | 多情景方案集 | P1 |
| | 价值曲线分析 | 竞争数据 | 差异化曲线 | P1 |
| **商业模式** | 价值主张画布 | 客户痛点数据 | 价值主张地图 | P0 |
| | 商业模式画布 | 商业模式数据 | 九宫格画布 | P0 |
| | 破坏性创新模型 | 技术/市场数据 | 创新类型判断 | P1 |
| **执行管理** | BSC 平衡计分卡 | 战略目标 | 四维度指标 | P0 |
| | 战略地图 | BSC 指标 | 战略可视化图 | P1 |
| | 组织设计框架 | 组织架构数据 | 组织匹配建议 | P1 |
| | 依赖关系图 | 任务列表 | 依赖关系网络 | P1 |
| | RACI 矩阵 | 角色任务数据 | 职责分配矩阵 | P1 |
| | 甘特图 | 项目计划 | 进度可视化图 | P1 |
| | KPI | 业务目标 | 关键绩效指标 | P0 |
| | 变革管理模型 | 变革数据 | 变革路径图 | P2 |

#### 17.2.3 工具标准工作流（Think→Code→Execute→Observe→Validate）

```python
class ToolExecutionEngine:
    """工具执行引擎 - 原子循环"""

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        # 1. Think（规划）
        plan = await self.planner.generate(tool_call)
        # 输出：任务编排 JSON（子任务列表、工具映射、依赖边）

        # 2. Code（代码生成）
        code = await self.code_generator.generate(plan)
        # 生成 Python 代码（数值计算）或数学模型（优化问题）

        # 3. Execute（沙箱执行）
        try:
            result = await self.sandbox.execute(code)
            # Docker 沙箱隔离执行
            # 网络白名单（仅允许可信 API）
        except ExecutionError as e:
            # Validation Feedback 闭环
            if e.retry_count < 3:
                fix_code = await self.code_fixer.fix(e, code)
                return await self.execute(fix_code)
            return ToolResult(status="failed", error=str(e))

        # 4. Observe（结果观察）
        observation = await self.observer.observe(result)
        # 提取关键指标、异常检测、趋势分析

        # 5. Validate（验证）
        validation = await self.validator.validate(observation, tool_call.schema)
        if not validation.passed:
            return ToolResult(status="invalid", reason=validation.reason)

        # 6. 证据打包
        evidence_package = {
            "input_hash": hash(tool_call.input),
            "plan": plan,
            "code": code,
            "result": result,
            "observation": observation,
            "validation": validation,
            "confidence": validation.confidence,
            "citations": result.citations
        }

        return ToolResult(
            status="success",
            output=observation,
            evidence_package=evidence_package,
            cost=result.cost,
            execution_time=result.execution_time
        )
```

#### 17.2.4 数值计算与沙箱执行

**持久化 Jupyter Kernel 沙箱：**

```python
class PersistentSandbox:
    """持久化计算沙箱 - 支持跨步骤变量传递"""

    def __init__(self):
        self.kernel_pool = {}
        self.idle_timeout = 1800  # 30 分钟无活动销毁

    async def get_kernel(self, session_id: str) -> JupyterKernel:
        """获取或创建 Kernel"""
        if session_id not in self.kernel_pool:
            # 创建新 Kernel
            kernel = await self.create_kernel()
            self.kernel_pool[session_id] = {
                "kernel": kernel,
                "last_used": datetime.now()
            }

        # 更新使用时间
        self.kernel_pool[session_id]["last_used"] = datetime.now()

        return self.kernel_pool[session_id]["kernel"]

    async def execute(self, session_id: str, code: str) -> ExecutionResult:
        """在沙箱中执行代码"""
        kernel = await self.get_kernel(session_id)

        # 1. 执行代码
        result = await kernel.execute(code)

        # 2. 捕获 STDERR（Validation Feedback）
        if result.stderr:
            # 检索错误案例库辅助修复
            fix_suggestions = await self.error_db.search(result.stderr)
            result.fix_suggestions = fix_suggestions

        # 3. 结果缓存（相同输入避免重复计算）
        cache_key = hash(code)
        await self.cache.set(cache_key, result, ttl=3600)

        return result

    async def cleanup_idle(self):
        """清理空闲 Kernel"""
        now = datetime.now()
        idle_sessions = [
            sid for sid, data in self.kernel_pool.items()
            if (now - data["last_used"]).seconds > self.idle_timeout
        ]

        for session_id in idle_sessions:
            await self.kernel_pool[session_id]["kernel"].shutdown()
            del self.kernel_pool[session_id]
```

#### 17.2.5 Schema 强制与一致性校验

**Pydantic V2 契约化输出：**

```python
class SchemaEnforcer:
    """Schema 强制器 - Instructor Patch"""

    async def enforce(self, llm_output: str, schema: Type[BaseModel]) -> BaseModel:
        """强制 LLM 输出符合 Schema"""
        try:
            # 使用 Instructor 强制结构化
            result = await instructor.from_openai(llm_output, response_model=schema)
            return result
        except ValidationError as e:
            # 契约测试失败
            if e.retry_count >= 3:
                # 连续 3 次失败触发工具熔断
                await self.trigger_circuit_breaker()
                raise ToolCircuitError("Schema validation failed 3 times")

            # 自动重试（带错误提示）
            fixed_output = await self.llm.fix(e, llm_output)
            return await self.enforce(fixed_output, schema)
```

**一致性校验仲裁器：**

```python
class ConsistencyArbiter:
    """一致性校验仲裁器 - 检测逻辑冲突"""

    async def check(self, tool_outputs: List[ToolResult]) -> ConsistencyReport:
        conflicts = []

        # 1. 财务常识库检测
        for output in tool_outputs:
            # 利润率与成本矛盾检测
            if "profit_margin" in output and "cost" in output:
                if output.profit_margin + output.cost_ratio > 1.0:
                    conflicts.append({
                        "type": "financial_contradiction",
                        "description": "利润率与成本矛盾",
                        "details": f"利润率{output.profit_margin} + 成本率{output.cost_ratio} > 100%"
                    })

        # 2. 规则引擎检测
        rule_conflicts = await self.rule_engine.check(tool_outputs)
        conflicts.extend(rule_conflicts)

        # 3. 生成冲突报告
        return ConsistencyReport(
            has_conflicts=len(conflicts) > 0,
            conflicts=conflicts,
            severity="high" if len(conflicts) > 3 else "medium" if len(conflicts) > 1 else "low"
        )
```

#### 17.2.6 提示词工程与演进（DSPy 理念）

```python
class PromptOptimizer:
    """提示词优化器 - 基于 DSPy 理念"""

    async def optimize(self, feedback_logs: List[FeedbackLog]) -> OptimizedPrompt:
        # 1. 将用户修正转化为 Few-Shot 样本
        few_shot_samples = []
        for log in feedback_logs:
            if log.correction_type in ["L0", "L1"]:
                sample = {
                    "input": log.input,
                    "incorrect_output": log.original_output,
                    "correct_output": log.corrected_output,
                    "correction_type": log.correction_type
                }
                few_shot_samples.append(sample)

        # 2. 多目标优化（NSGA-II 算法）
        # 目标：结构完整性 40% + 逻辑一致性 35% + 成本效率 25%
        optimized_prompts = await self.nsga2.optimize(
            samples=few_shot_samples,
            objectives={
                "structure": 0.40,
                "consistency": 0.35,
                "cost_efficiency": 0.25
            }
        )

        # 3. Pareto 前沿选择
        best_prompt = self.select_from_pareto(optimized_prompts)

        # 4. Strat-Bench 验证（通过率≥90%）
        test_result = await self.strat_bench.test(best_prompt)
        if test_result.pass_rate < 0.90:
            return OptimizationResult(
                status="rejected",
                reason=f"Strat-Bench pass rate {test_result.pass_rate:.2%} < 90%"
            )

        return OptimizationResult(
            status="approved",
            optimized_prompt=best_prompt,
            test_result=test_result
        )
```

---

### 17.3 AGENT 架构设计

**设计哲学：** 7 类高管角色 Agent（CEO/CFO/CMO/CTO/COO/CHO/AUD）+ 1 SYS AGENT，通过弹性视角隔离协议（EIP）实现安全协作。

#### 17.3.1 Agent 身份档案（7+1 角色）

```python
class AgentIdentity:
    """Agent 身份档案 - 7+1 角色定义"""

    # 核心 7 角色
    ROLES = {
        "CEO": {
            "full_name": "首席执行官",
            "responsibilities": ["战略方向", "最终决策", "高管协调"],
            "expertise": ["宏观趋势", "竞争格局", "战略意图"],
            "tools": ["PESTEL", "波特五力", "情景规划"],
            "view": "executive"  # 高管视图
        },
        "CFO": {
            "full_name": "首席财务官",
            "responsibilities": ["财务量化", "投资评估", "风险控制"],
            "expertise": ["财务分析", "估值建模", "资本配置"],
            "tools": ["财务建模", "DCF 估值", "敏感性分析"],
            "view": "analyst"  # 专业人员视图
        },
        "CMO": {
            "full_name": "首席营销官",
            "responsibilities": ["市场洞察", "客户分析", "竞争策略"],
            "expertise": ["市场细分", "客户需求", "竞争格局"],
            "tools": ["$APPEALS", "竞争对手分析", "价值曲线"],
            "view": "analyst"
        },
        "CTO": {
            "full_name": "首席技术官",
            "responsibilities": ["技术趋势", "技术战略", "创新评估"],
            "expertise": ["技术路线图", "技术竞争力", "创新焦点"],
            "tools": ["技术趋势分析", "专利分析", "技术竞争力评估"],
            "view": "analyst"
        },
        "COO": {
            "full_name": "首席运营官",
            "responsibilities": ["运营差距", "执行设计", "内部能力"],
            "expertise": ["运营效率", "价值链", "组织能力"],
            "tools": ["价值链分析", "运营差距分析", "组织设计"],
            "view": "analyst"
        },
        "CHO": {
            "full_name": "首席人力官",
            "responsibilities": ["人才战略", "组织文化", "变革管理"],
            "expertise": ["人才盘点", "组织能力", "变革管理"],
            "tools": ["人才盘点", "组织健康度", "变革管理模型"],
            "view": "analyst"
        },
        "AUD": {
            "full_name": "联席审计官",
            "responsibilities": ["一致性审计", "幻觉检测", "合规检查"],
            "expertise": ["事实核查", "逻辑一致性", "合规审计"],
            "tools": ["事实一致性检查", "逻辑一致性检查", "数值重计算"],
            "view": "auditor",  # 审计视图
            "mode": "sidecar"   # 旁路监听模式
        },

        # +1 仲裁者
        "SYS": {
            "full_name": "系统仲裁官",
            "responsibilities": ["任务分发", "冲突仲裁", "隔离管理"],
            "expertise": ["任务分解", "冲突裁决", "EIP 执行"],
            "tools": ["任务分解器", "裁决状态机", "隔离等级管理器"],
            "view": "system",
            "mode": "orchestrator"  # 编排者模式
        }
    }
```

#### 17.3.2 Agent 标准工作流（9 步原子循环）

**状态机与原子循环的关系**：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent State Machine                         │
│  ┌──────┐   ┌────────┐   ┌──────────┐   ┌────────┐   ┌──────┐ │
│  │ INIT │ → │RUNNING│ → │CHECKPOINT│ → │WAITING │ → │ END  │ │
│  └──────┘   └────────┘   └──────────┘   └────────┘   └──────┘ │
│                  ↓              ↑                            │
│           ┌─────────────┐       │                            │
│           │  9步原子循环 │ ←←←←←┘                            │
│           │ (仅在RUNNING状态执行)  │                            │
│           └─────────────┘                                    │
└─────────────────────────────────────────────────────────────────┘

状态机：定义 Agent 生命周期（start→running→checkpoint→resume→end）
原子循环：定义 RUNNING 状态下的业务逻辑（感知→规划→执行→...）
关系：状态机决定"何时停/何时恢复"，原子循环决定"停的时候做什么"
```

**Agent 生命周期状态机**：

```python
class AgentState(Enum):
    """Agent 生命周期状态 - 与 Checkpoint 机制协同"""
    INIT = "initialized"           # 初始化完成
    RUNNING = "running"             # 运行中（可中断）
    CHECKPOINTED = "checkpointed"   # 已保存（可恢复）
    WAITING = "waiting"             # 等待外部输入（如用户确认）
    COMPLETED = "completed"         # 正常结束
    FAILED = "failed"               # 异常终止

class AgentLifecycle:
    """Agent 生命周期管理器"""

    def __init__(self, workflow: AgentWorkflow):
        self.workflow = workflow
        self.state = AgentState.INIT
        self.checkpoint_manager = CheckpointManager()

    async def run(self, task: AgentTask) -> AgentResult:
        """主循环：状态机驱动 9 步原子循环"""
        try:
            self.state = AgentState.RUNNING

            while self.state == AgentState.RUNNING:
                # 原子循环执行（步骤 1-9）
                result = await self.workflow.execute(task)

                # 状态转换判断
                if result.status == "success":
                    self.state = AgentState.COMPLETED
                elif result.status == "waiting_user_confirm":
                    self.state = AgentState.WAITING
                    await self.save_checkpoint()
                elif result.status == "error_recoverable":
                    self.state = AgentState.RUNNING  # 重试
                else:
                    self.state = AgentState.FAILED

            return result

        except Exception as e:
            self.state = AgentState.FAILED
            raise

    async def save_checkpoint(self):
        """断点保存：ATOMIC 地将运行状态写入 CheckpointSnapshot"""
        checkpoint = CheckpointSnapshot(
            state=self.state,
            workflow_state=self.workflow.get_state(),
            timestamp=datetime.now()
        )
        await self.checkpoint_manager.save(checkpoint)
        self.state = AgentState.CHECKPOINTED

    async def resume(self, checkpoint_id: UUID) -> AgentResult:
        """断点恢复：从 CheckpointSnapshot 恢复到 RUNNING 状态"""
        checkpoint = await self.checkpoint_manager.load(checkpoint_id)
        self.workflow.restore_state(checkpoint.workflow_state)
        self.state = AgentState.RUNNING
        return await self.run(checkpoint.pending_task)
```

**9 步原子循环（仅在 RUNNING 状态执行）**：

```python
class AgentWorkflow:
    """Agent 标准工作流 - 9 步原子循环"""

    @trace  # Phoenix 全链路追踪装饰器
    async def execute(self, task: AgentTask) -> AgentResult:
        # 1. 初始化
        await self.initialize(task)
        # - 加载身份档案（IDENTITY.md）
        # - 加载记忆（MEMORY.md）
        # - 实例化沙箱与记忆容器

        # 2. 感知
        context = await self.perceive(task)
        # - 读取结构化 JSON 数据
        # - 生成全景数据摘要
        # - 摘要质量评估（信息熵 + 实体覆盖率）
        if context.summary_quality < 0.7:
            context = await self.trigger_retrieval(context)  # 二次检索

        # 3. 规划
        plan = await self.plan(context, task)
        # - 生成任务执行 DAG
        # - 匹配工具映射
        # - 定义依赖关系

        # 4. 执行
        results = []
        for subtask in plan.topological_sort():
            result = await self.execute_atom(subtask)
            # Think→Code→Execute→Observe→Validate 原子循环
            results.append(result)

        # 5. 深度思考（可选，关键决策点）
        if task.requires_deep_thinking:
            chains = await self.parallel_thinking(task)
            # 并行生成多条思维链推演路径
            best_chain = self.select_best_chain(chains)
            results.append(best_chain)

        # 6. 验证
        validation = await self.validate(results, task.schema)
        if validation.confidence >= task.target_confidence:
            return self.early_terminate(validation)  # 提前终止

        # 7. 反思
        if not validation.passed:
            reflection = await self.reflect(validation)
            # 错误分析驱动持续改进
            plan = await self.revise_plan(plan, reflection)
            return await self.execute(plan)  # 重试

        # 8. 证据打包
        evidence_package = {
            "input_hash": hash(task.input),
            "plan": plan,
            "results": results,
            "validation": validation,
            "confidence": validation.confidence,
            "citations": self.extract_citations(results),
            "tool_calls": self.extract_tool_calls(results)
        }
        await self.archive.save(evidence_package)

        # 9. 演化（可选）
        if task.should_evolve:
            await self.evolve(results, validation)
            # 匿名化执行轨迹存入演进数据集

        return AgentResult(
            status="success",
            output=validation.output,
            evidence_package=evidence_package,
            cost=self.calculate_cost(results),
            execution_time=self.calculate_time(results)
        )
```

#### 17.3.3 弹性视角隔离协议（EIP）执行

```python
class EIPExecutor:
    """弹性视角隔离协议执行器"""

    # 四级隔离等级
    ISOLATION_LEVELS = {
        "L4": {
            "name": "硬隔离",
            "prompt_isolation": True,    # Prompt 隔离
            "tool_isolation": True,      # 工具严格隔离
            "data_isolation": "read_only",  # 数据只读
            "default": True
        },
        "L3": {
            "name": "软隔离",
            "prompt_isolation": True,
            "tool_isolation": False,     # 共享工具
            "data_isolation": "restricted_write"  # 受限写入
        },
        "L2": {
            "name": "协作态",
            "prompt_isolation": True,    # 保持独立身份
            "tool_isolation": False,     # 共享工具池
            "data_isolation": "free_write",  # 自由写入（附带置信度 + 引用源）
            "auto_recovery": True,       # 30 分钟无活动恢复至 L4
            "joint_output_signature": True  # 联合输出需各 Agent 独立签名
        },
        "L1": {
            "name": "融合态",
            "prompt_isolation": False,   # 共享上下文（SYS AGENT 监督）
            "tool_isolation": False,     # 完全共享
            "data_isolation": "full_shared",  # 完全共享
            "emergency_mode": True,
            "mandatory_audit": True      # 强制审计
        }
    }

    async def evaluate_and_switch(self, agent_id: str, context: IsolationContext) -> str:
        """评估并切换隔离等级"""
        current_level = await self.get_current_level(agent_id)

        # 1. 检测触发条件
        triggers = await self.detect_triggers(context)

        # 2. 判定目标等级
        if triggers.sys_command:
            target_level = triggers.target_level  # SYS 命令直接指定
        elif triggers.keyword_frequency > 0.05:
            target_level = "L3"  # 关键词频率>5% 降级
        elif triggers.task_dependency > 0.7:
            target_level = "L2"  # 任务依赖>0.7 升级
        elif triggers.user_request:
            target_level = triggers.target_level  # 用户请求指定
        else:
            return current_level  # 无触发条件

        # 3. 执行切换
        await self.execute_switch(agent_id, current_level, target_level)

        # 4. 记录审计日志
        log = IsolationSwitchLog(
            agent_id=agent_id,
            previous_level=current_level,
            target_level=target_level,
            trigger_reason=triggers.reason,
            trigger_type=triggers.type
        )
        await self.audit_log.save(log)

        # 5. 设置自动恢复（L2→L4，30 分钟无活动）
        if target_level == "L2":
            await self.schedule_auto_recovery(agent_id, delay_minutes=30)

        return target_level
```

#### 17.3.4 SYS AGENT 裁决状态机

```python
class SYSArbiter:
    """SYS AGENT 裁决状态机 - 五维评分"""

    DIMENSION_WEIGHTS = {
        "factual_accuracy": 0.35,    # 事实准确性
        "logical_consistency": 0.25, # 逻辑一致性
        "risk_controllability": 0.20,# 风险可控性
        "resource_feasibility": 0.15,# 资源可行性
        "strategic_alignment": 0.05  # 战略对齐度
    }

    async def arbitrate(self, dispute: Dispute) -> ArbitrationResult:
        """执行裁决流程"""
        # 1. 收集论据
        arguments = {
            "party_a": dispute.party_a.arguments,
            "party_b": dispute.party_b.arguments,
            "historical_cases": await self.retrieve_similar_cases(dispute)
        }

        # 2. 五维评估
        scores = {}
        for party_id, party_args in arguments.items():
            scores[party_id] = {
                "factual_accuracy": await self.evaluate_factual_accuracy(party_args),
                "logical_consistency": await self.evaluate_logical_consistency(party_args),
                "risk_controllability": await self.evaluate_risk_controllability(party_args),
                "resource_feasibility": await self.evaluate_resource_feasibility(party_args),
                "strategic_alignment": await self.evaluate_strategic_alignment(party_args)
            }

        # 3. 计算综合得分
        final_scores = {}
        for party_id, dimension_scores in scores.items():
            total = sum(
                score * self.DIMENSION_WEIGHTS[dim]
                for dim, score in dimension_scores.items()
            )
            final_scores[party_id] = total

        # 4. 置信度评估
        sorted_scores = sorted(final_scores.values(), reverse=True)
        confidence = (sorted_scores[0] - sorted_scores[1]) / 5.0

        # 5. 决策生成
        if confidence < 0.4:
            # 强制升级人工仲裁
            return await self.escalate_to_human(dispute, scores, confidence)

        decision = self.generate_decision(scores)

        if confidence < 0.6:
            decision.low_confidence_flag = True
            decision.recommend_human_review = True

        return ArbitrationResult(
            decision=decision,
            scores=scores,
            confidence=confidence
        )
```

#### 17.3.5 辩论质量评估器

> **说明：** 辩论质量评估器详细实现见 [第 7.3 节 辩论质量评估器](#73-辩论质量评估器)
>
> 本节描述辩论质量评估器在 SYS AGENT 裁决流程中的集成方式。

**集成方式：**

```python
class SYSArbiter:
    """SYS AGENT 裁决器 - 五维评分状态机"""

    def __init__(self):
        self.debate_evaluator = DebateEvaluator()  # 复用第 7.3 节定义

    async def arbitrate(self, debate_result: DebateResult) -> ArbitrationDecision:
        """
        执行裁决

        流程：
        1. 使用 DebateEvaluator 评估辩论质量
        2. 基于辩论质量计算置信度
        3. 根据置信度决定裁决方式（自动执行/人工复核）
        """
        # 1. 评估辩论质量（复用第 7.3 节 DebateEvaluator）
        debate_quality = await self.debate_evaluator.evaluate_round(debate_result.final_round)

        # 2. 计算置信度
        confidence = self.calculate_confidence(
            debate_quality.gain_rate,
            debate_quality.repetition_rate,
            debate_quality.contributions
        )

        # 3. 决定裁决方式
        if confidence >= 0.6:
            return await self.auto_arbitrate(debate_result)
        elif confidence >= 0.4:
            return await self.manual_review_arbitrate(debate_result)
        else:
            return await self.escalate_arbitrate(debate_result)
```

**与第 7.3 节的关系：**
- 第 7.3 节定义 `DebateEvaluator` 核心实现
- 本节描述 `DebateEvaluator` 在 SYS AGENT 裁决流程中的集成使用
- 所有参数和阈值与第 7.3 节保持一致

#### 17.3.6 Agent 配置格式

**目标：** 定义统一的 Agent 配置格式，支持动态加载和热更新

**配置文件格式 (YAML):**
```yaml
# configs/agents/ceo_agent.yaml
agent:
  id: "agent_ceo"
  name: "CEO"
  display_name: "首席执行官"
  icon: "👔"
  version: "1.0.0"

identity:
  role: "战略决策者"
  background: "20 年 + 企业战略管理经验，擅长宏观战略规划和跨部门协调"
  expertise:
    - "战略规划"
    - "业务设计"
    - "高管协调"
    - "风险决策"

capabilities:
  tools:
    - "差距分析"
    - "市场洞察"
    - "业务设计"
    - "风险矩阵"
    - "战略解码"
  max_context_length: 8192
  reasoning_mode: "strategic"

communication:
  style: "直接、战略性、关注大局"
  tone: "专业、权威、开放"
  language: "zh-CN"

principles:
  - "战略对齐优先"
  - "数据驱动决策"
  - "风险可控"
  - "长期价值导向"

llm_config:
  routing_enabled: true
  preferred_models:
    - "qwen-max"
    - "claude-3-opus"
  fallback_models:
    - "qwen-plus"
  temperature: 0.7
  max_tokens: 2048

eip_config:
  default_isolation_level: "L4"
  allowed_levels:
    - "L4"
    - "L3"
    - "L2"
  collaboration_partners:
    - "agent_cfo"
    - "agent_coo"
    - "agent_cmo"

memory_config:
  L0_entry:
    type: "filesystem"
    index: "MEMORY.md"
    description: "记忆系统统一入口，索引驱动各层访问"
  L1_cache:
    type: "redis"
    ttl: 3600
    description: "会话状态、语义缓存"
  L2_relational:
    type: "postgresql"
    description: "用户/RBAC、审计元数据、业务实体"
  L3_vector:
    type: "qdrant"
    description: "嵌入向量、混合检索 payload"
  L4_object:
    type: "minio"
    worm_retention_days: 2555  # 7 年
    description: "原始文档、证据包、审计归档"
  L5_graph:
    enabled: false  # 可选，按需启用
    type: "neo4j"
    description: "知识图谱、实体关系"

prompts:
  system_prompt: "prompts/ceo_system.md"
  role_prompt: "prompts/ceo_role.md"
  style_guide: "prompts/ceo_style.md"
```

**Agent 配置加载器:**
```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import yaml

class AgentConfig(BaseModel):
    """Agent 配置模型"""
    id: str
    name: str
    display_name: str
    icon: str
    version: str

    identity: Dict[str, Any]
    capabilities: Dict[str, Any]
    communication: Dict[str, str]
    principles: List[str]

    llm_config: Dict[str, Any]
    eip_config: Dict[str, Any]
    memory_config: Dict[str, Any]
    prompts: Dict[str, str]

    @classmethod
    def from_yaml(cls, path: str) -> 'AgentConfig':
        """从 YAML 文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls(**data['agent'])

# 使用示例
config = AgentConfig.from_yaml('configs/agents/ceo_agent.yaml')
```

#### 17.3.7 Agent 间通信协议（SAP - sisys Agent Protocol）

**目标：** 定义 sisys 内部 Agent 间标准通信协议，确保协作一致性

**设计原则：** 内部 Agent 通信使用 SAP 协议，不依赖外部标准（如 Google A2A），V2+ 可通过适配器桥接外部生态

**消息格式:**
```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4, UUID
from enum import Enum

class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"           # 请求协助
    RESPONSE = "response"         # 响应请求
    NOTIFICATION = "notification" # 通知事件
    BROADCAST = "broadcast"       # 广播到公共黑板
    DEBATE = "debate"             # 辩论消息

class MessagePriority(str, Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SAPMessage(BaseModel):
    """Agent 间通信消息（SAP 协议）"""
    message_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID  # 会话 ID，关联同一对话的消息
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # 发送者和接收者
    sender_id: str  # 发送 Agent ID
    receiver_id: str  # 接收 Agent ID，广播时为"broadcast"

    # 消息类型和优先级
    message_type: MessageType
    priority: MessagePriority = MessagePriority.NORMAL

    # 消息内容
    subject: str  # 消息主题
    content: Dict[str, Any]  # 消息内容
    context: Dict[str, Any] = Field(default_factory=dict)  # 上下文信息

    # 元数据
    requires_response: bool = False
    timeout_seconds: int = 300
    correlation_id: UUID = None  # 关联请求 ID（响应时填写）

    # EIP 隔离信息
    isolation_level: str = "L4"
    blackboard_visible: bool = False  # 是否对公共黑板可见
```

#### 17.3.8 Agent 评估与可观测性

**设计原则：** 以开源为首选，不考虑商业方案。评估框架是横切关注点，覆盖整个 Agent 生命周期。

**技术选型：** Phoenix (Arize) - 完全开源（Apache 2.0），LLM 原生可观测性平台

```python
from phoenix.tracing import trace
from phoenix.evals import llm_eval_binary_classifier

class EvaluationHarness:
    """
    Agent 评估与可观测性 - 基于 Phoenix (Arize) 开源方案
    支持：全链路追踪、评估指标、漂移检测（CUSUM）
    """

    def __init__(self, agent_workflow: AgentWorkflow):
        self.workflow = agent_workflow
        self.tracer = PhoenixTracer(project_name="sisys-agent")
        self.cusum_detector = CUSUMDriftDetector()

    @trace
    async def run_with_evaluation(self, task: AgentTask) -> AgentResult:
        """运行 Agent + 评估 + 追踪"""
        # 1. Phoenix 追踪（自动 span 记录）
        with self.tracer.start_span("agent_execution") as span:
            result = await self.workflow.execute(task)

        # 2. 评估输出质量
        eval_result = await self.evaluate(result)
        span.set_attribute("eval.hallucination_score", eval_result.hallucination_score)
        span.set_attribute("eval.context_relevance", eval_result.context_relevance)

        # 3. CUSUM 漂移检测
        self.cusum_detector.update(eval_result.overall_score)
        if self.cusum_detector.is_drifted():
            span.set_attribute("drift.detected", True)
            await self.trigger_recalibration()

        return result

    async def evaluate(self, result: AgentResult) -> EvaluationResult:
        """评估 Agent 输出质量"""
        # 幻觉检测
        hallucination_score = await llm_eval_binary_classifier(
            prompt=f"判断以下回答是否存在幻觉：{result.output}",
            model="gpt-4"
        )

        # 上下文相关性
        context_relevance = self.compute_context_relevance(
            result.evidence_package
        )

        # 置信度校准
        confidence_accuracy = self.compute_confidence_accuracy(
            predicted=result.confidence,
            actual=eval_result.quality_score
        )

        return EvaluationResult(
            hallucination_score=hallucination_score,
            context_relevance=context_relevance,
            confidence_accuracy=confidence_accuracy,
            overall_score=self.weighted_sum(...)
        )

    def compute_confidence_accuracy(
        self,
        predicted: float,
        actual: float
    ) -> float:
        """计算置信度校准准确度（用于 CUSUM 漂移检测）"""
        error = abs(predicted - actual)
        return 1.0 - min(error, 1.0)  # 误差越小，校准越准确
```

**与 Checkpoint 机制集成：**

```python
class CheckpointWithEvaluation:
    """Checkpoint 快照 + 评估数据"""

    def to_checkpoint_snapshot(self) -> CheckpointSnapshot:
        return CheckpointSnapshot(
            checkpoint_id=self.checkpoint_id,
            state_data=self.state_data,
            evaluation_history=self.eval_history,  # 评估历史（CUSUM 用）
            hallucination_trend=self.cusum_detector.get_trend(),
            confidence_accuracy_trend=self.confidence_accuracy_history
        )
```

**技术优势：**

- ✅ 完全开源（Apache 2.0，无使用限制）
- ✅ 与 LangGraph/LangChain 官方集成
- ✅ 内置幻觉检测、上下文相关性评估
- ✅ 支持自定义评估指标
- ✅ 自托管（不依赖云服务，数据自主可控）

**与 §2.5 监控基础设施集成：**

| 组件 | 技术 | 用途 |
|------|------|------|
| 追踪 | PhoenixTracer | 全链路 span 记录（@trace 装饰器） |
| 指标 | Prometheus | 评估指标导出（hallucination_score、context_relevance、confidence_accuracy） |
| 可视化 | Grafana | 评估仪表盘、漂移告警 |
| 分布式追踪 | OpenTelemetry | Phoenix 与 SISYS 追踪系统对接 |

---

### 17.4 战略规划架构设计

**设计哲学：** 严格遵守 BLM 与 BEM 模型的规定流程，通过 Checkpoint 机制实现人工介入，输出五年滚动战略规划（SP）和年度业务计划（BP）。

#### 17.4.1 BLM 六阶段状态机

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BLM 六阶段状态机                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ 1. 业绩差距  │ →  │ 2. 市场洞察  │ →  │ 3. 战略意图  │              │
│  │    分析      │    │   (六子步骤)  │    │   与目标     │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│       │                    │                    │                       │
│       ▼                    ▼                    ▼                       │
│  Checkpoint-1        Checkpoint-2-7        Checkpoint-8                 │
│       │                    │                    │                       │
│       └────────────────────┴────────────────────┘                       │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ 6. 执行设计  │ ←  │ 5. 业务设计  │ ←  │ 4. 创新焦点  │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│       │                    │                    │                       │
│       ▼                    ▼                    ▼                       │
│  Checkpoint-14        Checkpoint-13        Checkpoint-9-12              │
│                                                                         │
│  最终输出：SP 战略规划文档（JSON + PDF）                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 17.4.2 BLM 各阶段详细设计

**阶段 1：业绩差距分析**

```python
class PerformanceGapAnalysis:
    """业绩差距分析 - BLM 阶段 1"""

    # 主导 Agent：CFO（财务差距）、COO（运营差距）
    LEAD_AGENTS = ["CFO", "COO"]

    # 协作 Agent：CEO（战略校准）、AUD（数据审计）
    COLLAB_AGENTS = ["CEO", "AUD"]

    # 建议工具组合
    TOOLS = ["SWOT-TOWS", "KPI", "价值链分析", "GE-麦肯锡矩阵"]

    async def execute(self, input_data: GapInput) -> GapOutput:
        # 1. 财务差距量化（CFO 主导）
        financial_gap = await self.cfo_agent.analyze_financial_gap(
            current_performance=input_data.current,
            target_performance=input_data.target,
            historical_data=input_data.historical
        )

        # 2. 运营差距分析（COO 主导）
        operational_gap = await self.coo_agent.analyze_operational_gap(
            current_operations=input_data.operations,
            benchmark_data=input_data.benchmark
        )

        # 3. 根因识别（SWOT-TOWS）
        root_causes = await self.swot_tows.analyze(
            financial_gap=financial_gap,
            operational_gap=operational_gap
        )

        # 4. 业务组合健康度评估（GE 矩阵）
        portfolio_health = await self.ge_matrix.evaluate(
            business_units=input_data.business_units
        )

        # 5. Checkpoint-1（用户确认）
        checkpoint = Checkpoint(
            stage="performance_gap",
            output={
                "financial_gap": financial_gap,
                "operational_gap": operational_gap,
                "root_causes": root_causes,
                "portfolio_health": portfolio_health
            },
            status="pending_user_feedback"
        )
        await self.checkpoint_repo.save(checkpoint)

        return GapOutput(
            financial_gap=financial_gap,
            operational_gap=operational_gap,
            root_causes=root_causes,
            portfolio_health=portfolio_health,
            checkpoint_id=checkpoint.id
        )
```

**阶段 2：市场洞察（六子步骤）**

```python
class MarketInsight:
    """市场洞察 - BLM 阶段 2（六子步骤）"""

    SUB_STEPS = {
        "2.1_看趋势": {
            "lead_agent": "CEO",
            "collab_agents": ["CTO", "CMO", "CFO"],
            "tools": ["PESTEL", "情景规划"],
            "output": "宏观趋势报告 + 技术演进路线图"
        },
        "2.2_看市场与客户": {
            "lead_agent": "CMO",
            "collab_agents": ["COO", "CEO", "CFO"],
            "tools": ["$APPEALS", "价值主张画布"],
            "output": "客户细分画像 + 需求优先级矩阵"
        },
        "2.3_看竞争": {
            "lead_agent": "CEO",
            "collab_agents": ["CMO", "CTO", "CFO"],
            "tools": ["波特五力", "竞争对手分析"],
            "output": "行业竞争结构图 + 竞争对手能力雷达图"
        },
        "2.4_看自己": {
            "lead_agent": "COO",
            "collab_agents": ["CFO", "CHO"],
            "tools": ["价值链分析", "VRIO 框架"],
            "output": "内部能力评估 + 资源竞争力图谱"
        },
        "2.5_看机会": {
            "lead_agent": "CMO",
            "collab_agents": ["CEO", "CFO"],
            "tools": ["安索夫矩阵", "价值曲线分析"],
            "output": "市场机会地图 + 增长路径建议"
        },
        "2.6_看风险": {
            "lead_agent": "CFO",
            "collab_agents": ["AUD", "CEO"],
            "tools": ["情景规划", "风险矩阵"],
            "output": "风险全景图 + 风险缓解措施"
        }
    }

    async def execute(self, input_data: InsightInput) -> InsightOutput:
        all_outputs = {}

        for step_name, config in self.SUB_STEPS.items():
            # 1. 执行子步骤
            output = await self.execute_sub_step(
                step_name=step_name,
                config=config,
                input_data=input_data
            )
            all_outputs[step_name] = output

            # 2. Checkpoint（每个子步骤）
            checkpoint = Checkpoint(
                stage=f"market_insight_{step_name}",
                output=output,
                status="pending_user_feedback"
            )
            await self.checkpoint_repo.save(checkpoint)

        # 3. 综合洞察报告
        comprehensive_insight = self.synthesize_insights(all_outputs)

        return InsightOutput(
            sub_steps_outputs=all_outputs,
            comprehensive_insight=comprehensive_insight,
            checkpoint_ids=[c.id for c in checkpoints]
        )
```


> **注意:** Checkpoint 双模式恢复和 Time-Travel 机制已迁移至 [sisys-checkpoint-timetravel-design.md](sisys-checkpoint-timetravel-design.md)

---
