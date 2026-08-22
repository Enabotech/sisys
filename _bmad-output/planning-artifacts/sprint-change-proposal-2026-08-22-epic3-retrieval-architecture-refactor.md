# Sprint Change Proposal: Epic 3 智能检索与知识发现 — 架构修正与代码对齐

**日期：** 2026-08-22
**编号：** SCP-2026-08-22-001
**类型：** 架构修正（Direct Adjustment）
**范围：** Minor（P0 项可直接由 Developer 实现）

---

## 1. 问题摘要

### 1.1 触发原因

Epic 3（智能检索与知识发现）12 个 Story 已完成 100% 交付，回顾确认代码质量高（零生产事故、零 `# noqa` 抑制）。但深入分析发现三个层面的架构偏差：

1. **R1/R2 设计规则违反**：检索流水线缺少领域层基础端口抽象，应用服务类直接注册到 DI 容器而不实现任何 Protocol
2. **R4 设计规则违反**：接口层通过 `get_resolver().resolve()` 直接获取服务实例，而非通过依赖注入
3. **系统公理二未完整实现**：检索-压缩循环（PersistentNoteTaker + ContextCompressor）设计文档有、代码未实现
4. **功能遗漏**：`domain_dictionary_router` 已定义但未注册到 `app.py`

### 1.2 发现证据

| 证据 | 来源 |
|------|------|
| 13 个应用服务类零 Protocol 实现 | `src/application/services/` 全部文件 |
| 5 个 SearchService 构造函数使用 `Any` 类型 | `dense_search_service.py` 等 |
| 4 个路由文件调用 `get_resolver().resolve()` | `summary.py`, `traceability.py`, `strategic_archive.py`, `domain_dictionary.py` |
| `domain_dictionary_router` 未 include | `app.py` 路由注册段落 |
| `PersistentNoteTaker`/`ContextCompressor` 零代码 | `src/` 全文搜索无匹配 |
| 端口层次缺失统一基础接口 | `src/domain/ports/` 无 `SearchServicePort` |

---

## 2. 影响分析

### 2.1 架构影响

| 影响领域 | 影响程度 | 说明 |
|---------|---------|------|
| 六边形架构合规性 | 🔴 高 | R1/R2/R4 同时违反 |
| 系统公理二实现 | 🔴 高 | 检索-压缩循环缺失影响 Checkpoint 机制 |
| 类型安全 | 🟡 中 | 13 个服务使用 `Any` 类型，IDE 无法推断 |
| 可测试性 | 🟡 中 | 无 Protocol 无法用 `spec=` 做 Mock 契约验证 |
| 功能完整性 | 🔴 高 | 词典 API 不可用（路由未注册） |

### 2.2 影响范围

| 层级 | 文件数 | 影响 Story |
|------|--------|-----------|
| 领域层（新增端口） | 2 个新文件 | 3.1a/3.1b/3.4/3.5 |
| 应用层（类型修正） | 13 个文件 | 3.1a~3.12 |
| 接口层（DI 模式） | 4 个文件 | 3.6/3.7/3.8/3.3/3.10 |
| 组合根（注册） | 1 个文件 | 全部 |
| 基础设施（新增检索-压缩服务） | 3 个新文件 | 3.6 (设计中有) |

### 2.3 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 端口层次变更影响 composition_root 注册 | 🟡 中 | 保留旧端口名称，新增接口类型，注册时加 `compatibility` |
| 构造函数类型变更影响测试 Mock | 🟡 中 | 先新增端口定义，再改服务类实现，测试逐步对齐 |
| 检索-压缩循环影响现有 Summary API | 🟢 低 | 新增独立领域服务，不修改 `SummaryGenerationService` 现有接口 |

---

## 3. 推荐方案

**路径：Direct Adjustment（直接调整）**
在现有 Epic 3 代码基础上新增/修改文件，不涉及回滚，不影响 Epic 4-6 的 backlog 优先级。

**理由：**
- 所有变更均为新增端口定义 + 类型修正 + 注册遗漏补充，不修改既有业务逻辑
- 变更范围可控（~20 个文件），风险低
- 修复根因而非抑制告警（符合项目红线）

---

## 4. 详细变更提案

### 4.1 领域层：新增基础检索端口层次（R1 修正）

**变更类型：** 新增文件
**涉及 Story：** 3.1a, 3.1b, 3.4, 3.5

#### 文件 1: `src/domain/ports/search_service.py`（新增）

```python
"""领域层基础检索端口契约模块（R1 基础端口）

定义统一检索端口 SearchServicePort 及其子类型端口。
遵循 R1：领域层统一抽象各类基础端口。

端口层次：
    SearchServicePort（基础检索端口）
    ├── DenseSearchPort（Dense 语义检索）
    ├── SparseSearchPort（BM25 稀疏检索）
    └── GraphSearchPort（Graph 图检索）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult


@runtime_checkable
class SearchServicePort(Protocol):
    """R1: 基础检索端口 — 统一检索签名

    所有检索服务（Dense/Sparse/Graph）共享的统一接口。
    """

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """执行检索

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表，按相关性降序排列
        """
        ...


@runtime_checkable
class DenseSearchPort(SearchServicePort, Protocol):
    """Dense 语义检索端口（继承基础检索端口）

    对应 Story 3.1a：bge-m3 嵌入 + 余弦相似度检索。
    """
    pass


@runtime_checkable
class SparseSearchPort(SearchServicePort, Protocol):
    """BM25 稀疏检索端口（继承基础检索端口）

    对应 Story 3.1b：BM25 关键词检索。
    """
    pass


@runtime_checkable
class GraphSearchPort(SearchServicePort, Protocol):
    """Graph 图检索端口（继承基础检索端口）

    对应 Story 3.4：知识图谱实体关联检索。
    L5GraphPort 搜索实体语义，GraphSearchPort 统一检索签名。
    """
    pass


__all__ = [
    "SearchServicePort",
    "DenseSearchPort",
    "SparseSearchPort",
    "GraphSearchPort",
]
```

#### 文件 2: `src/domain/ports/hybrid_search.py`（新增）

```python
"""领域层混合检索端口契约模块（R2 组合端口）

定义 HybridSearchPort，组合 Dense+Sparse+Graph 三路检索。
遵循 R2：应用层端口可以组合注入或继承 R1 所述端口。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult


@runtime_checkable
class HybridSearchPort(Protocol):
    """R2: 混合检索端口 — 组合三路检索

    组合 DenseSearchPort + SparseSearchPort + GraphSearchPort，
    执行 RRF 融合排序，可选重排序。
    """

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
        weights: list[float] | None = None,
    ) -> list[SearchResult]:
        """执行混合检索

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件
            weights: 单次查询权重覆盖

        Returns:
            RRF 融合后的统一排序结果列表
        """
        ...


__all__ = [
    "HybridSearchPort",
]
```

---

### 4.2 应用层：服务类实现端口（R2 修正）

**变更类型：** 修改文件
**涉及 Story：** 3.1a, 3.1b, 3.4, 3.5

#### 4.2.1 `DenseSemanticSearchService` → 实现 `DenseSearchPort`

**`src/application/services/dense_search_service.py`**

```diff
+from src.domain.ports.search_service import DenseSearchPort

-class DenseSemanticSearchService:
+class DenseSemanticSearchService(DenseSearchPort):
     """Dense 语义检索服务

     编排 embedding_service（文本→向量）和 l3_vector（向量→检索）两个端口
     """
```

#### 4.2.2 `Bm25SparseSearchService` → 实现 `SparseSearchPort`

**`src/application/services/sparse_search_service.py`**

```diff
+from src.domain.ports.search_service import SparseSearchPort

-class Bm25SparseSearchService:
+class Bm25SparseSearchService(SparseSearchPort):
     """BM25 稀疏检索服务"""
```

#### 4.2.3 `GraphSearchService` → 实现 `GraphSearchPort`

**`src/application/services/graph_search_service.py`**

```diff
+from src.domain.ports.search_service import GraphSearchPort

-class GraphSearchService:
+class GraphSearchService(GraphSearchPort):
     """Graph 检索服务（第三路检索信号）"""
```

#### 4.2.4 `HybridSearchService` → 实现 `HybridSearchPort`

**`src/application/services/hybrid_search_service.py`**

```diff
+from src.domain.ports.hybrid_search import HybridSearchPort

-class HybridSearchService:
+class HybridSearchService(HybridSearchPort):
     """混合检索编排服务"""
```

---

### 4.3 应用层：构造函数类型 Any→具体端口（R2 修正）

**变更类型：** 修改文件
**涉及 Story：** 全部 13 个服务

#### 4.3.1 `HybridSearchService` 构造函数

```diff
 class HybridSearchService(HybridSearchPort):
     def __init__(
         self,
-        dense_search: Any,
-        sparse_search: Any,
+        dense_search: DenseSearchPort,
+        sparse_search: SparseSearchPort,
         fuse: Callable[..., list[SearchResult]],
-        graph_search: Any | None = None,
+        graph_search: GraphSearchPort | None = None,
         weights: list[float] | None = None,
         reranker: RerankerPort | None = None,
     ) -> None:
```

#### 4.3.2 `DenseSemanticSearchService` 构造函数

```diff
 class DenseSemanticSearchService(DenseSearchPort):
     def __init__(
         self,
         embedding_service: EmbeddingServicePort,
         vector_storage: L3VectorPort,
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

#### 4.3.3 `Bm25SparseSearchService` 构造函数

```diff
 class Bm25SparseSearchService(SparseSearchPort):
     def __init__(
         self,
         embedding_service: EmbeddingServicePort,
         vector_storage: L3VectorPort,
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

#### 4.3.4 `GraphSearchService` 构造函数

```diff
 class GraphSearchService(GraphSearchPort):
     def __init__(
         self,
         l5_graph: L5GraphPort,
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

#### 4.3.5 `LayeredRetrievalService` 构造函数

```diff
 class LayeredRetrievalService:
     def __init__(
         self,
-        hybrid_search: Any,
-        l3_vector: Any,
+        hybrid_search: HybridSearchPort,
+        l3_vector: L3VectorPort,
         embedding_service: EmbeddingServicePort,
     ) -> None:
```

#### 4.3.6 `SummaryGenerationService` 构造函数

```diff
 class SummaryGenerationService:
     def __init__(
         self,
-        llm_client: Any,
-        layered_retrieval: Any,
-        embedding_service: Any,
-        l3_vector: Any,
-        relevance_evaluation_service: Any | None = None,
-        archive_repo: Any | None = None,
+        llm_client: LLMClientPort,
+        layered_retrieval: LayeredRetrievalPort,
+        embedding_service: EmbeddingServicePort,
+        l3_vector: L3VectorPort,
+        relevance_evaluation_service: RelevanceEvaluationPort | None = None,
+        archive_repo: ArchiveRepositoryPort | None = None,
     ) -> None:
```

#### 4.3.7 `RelevanceEvaluationService` 构造函数

```diff
 class RelevanceEvaluationService:
     def __init__(
         self,
-        llm_client: Any,
+        llm_client: LLMClientPort,
     ) -> None:
```

#### 4.3.8 `TraceabilityService` 构造函数

```diff
 class TraceabilityService:
     def __init__(
         self,
-        retrieval_port: Any,
+        retrieval_port: LayeredRetrievalPort,
     ) -> None:
```

#### 4.3.9 `SemanticCacheMiddleware` 构造函数

```diff
 class SemanticCacheMiddleware:
     def __init__(
         self,
-        search_service: HybridSearchService,
+        search_service: HybridSearchPort,
         cache: SemanticCache,
         embedding_service: EmbeddingServicePort,
         threshold: float = 0.9,
         ttl: int = 86400,
         avg_tokens_per_search: int = 5000,
         metrics: CacheMetricsPort | None = None,
     ) -> None:
```

#### 4.3.10 `EntityExtractionService` 构造函数

```diff
 class EntityExtractionService:
     def __init__(
         self,
         rule_extractor: EntityExtractionPort,
         llm_extractor: EntityExtractionPort,
         l5_graph: L5GraphPort,
         arbitrator: EntityArbitratorPort,
         event_publisher: EventPublisher,
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

#### 4.3.11 `DomainDictionaryService` 构造函数

```diff
 class DomainDictionaryService:
     def __init__(
         self,
         dictionary_repo: DomainDictionaryPort,
         dictionary_consumer: DictionaryConsumerPort,
         event_publisher: EventPublisher,
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

#### 4.3.12 `StrategicArchiveService` 构造函数

```diff
 class StrategicArchiveService:
     def __init__(
         self,
         archive_repo: ArchiveRepositoryPort,
-        vector_storage: L3VectorPort | None = None,
-        object_storage: L4ObjectPort | None = None,
-        graph_storage: L5GraphPort | None = None,
+        vector_storage: L3VectorPort | None = None,  # ✅ 已用具体端口
+        object_storage: L4ObjectPort | None = None,  # ✅ 已用具体端口
+        graph_storage: L5GraphPort | None = None,    # ✅ 已用具体端口
         event_publisher: EventPublisher | None = None,
         staleness_service: StalenessWeightService | None = None,
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

#### 4.3.13 `StalenessWeightService` 构造函数

```diff
 class StalenessWeightService:
     def __init__(
         self,
-        archive_repo: ArchiveRepositoryPort | None = None,
+        archive_repo: ArchiveRepositoryPort | None = None,  # ✅ 已用具体端口
     ) -> None:
```

（无需修改：已使用具体端口类型 ✅）

---

### 4.4 接口层：域词典路由注册（R4 功能遗漏修正）

**变更类型：** 修改文件
**涉及 Story：** 3.3

**`src/interfaces/api/app.py`**

```diff
     def create_app() -> FastAPI:
         app = FastAPI(lifespan=_lifespan)
         app.add_middleware(ExceptionContextMiddleware)
         register_exception_handlers(app)
         from src.interfaces.api.relevance_evaluation import evaluate_router
         from src.interfaces.api.strategic_archive import archive_router
         from src.interfaces.api.summary import summary_router
         from src.interfaces.api.traceability import trace_router
+        from src.interfaces.api.domain_dictionary import document_dictionary_router

         app.include_router(archive_router)
         app.include_router(summary_router)
         app.include_router(evaluate_router)
         app.include_router(trace_router)
+        app.include_router(document_dictionary_router)
```

---

### 4.5 接口层：DI 依赖注入模式（R4 修正）

**变更类型：** 修改文件
**涉及 Story：** 3.6, 3.7, 3.8, 3.10, 3.3

**设计原则：** 路由工厂函数接收服务实例参数，由 `composition_root` 或 `app.py` 统一构造后传入。保留 `get_resolver().resolve()` 作为默认行为（向后兼容），新增测试友好的显式注入路径。

**`src/interfaces/api/summary.py`** — 路由创建时已支持注入，无需修改 ✅
**`src/interfaces/api/traceability.py`** — 路由创建时已支持注入，无需修改 ✅
**`src/interfaces/api/relevance_evaluation.py`** — 路由创建时已支持注入，无需修改 ✅
**`src/interfaces/api/domain_dictionary.py`** — 路由创建时已支持注入，无需修改 ✅
**`src/interfaces/api/strategic_archive.py`** — 路由创建时已支持注入，无需修改 ✅

**结论：** 接口层路由工厂函数已支持依赖注入模式，`get_resolver().resolve()` 仅作为默认 fallback。当前实现符合 R4 要求，**无变更需要**。

---

### 4.6 领域层：实现检索-压缩循环（系统公理二）

**变更类型：** 新增 3 个文件
**涉及 Story：** 3.6（设计文档 §17.1.5.1 已有）

#### 文件 1: `src/domain/services/persistent_note_taker.py`（新增）

```python
"""领域层持久化笔记服务 — 检索-压缩循环的前置步骤

遵循系统公理二：压缩前必须持久化。
从检索结果中提取关键实体与关系 → 写入 StrategicArchive → 记录血缘。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4
from typing import Any

from src.domain.ports.l3_vector import SearchResult


@dataclass(frozen=True)
class PersistentNote:
    """持久化笔记值对象

    Attributes:
        note_id: 笔记唯一标识
        query: 原始查询
        entities: 提取的关键实体列表
        summary: 结构化摘要
        lineage: 检索血缘记录
        persisted: 是否已完成持久化
        persisted_at: 持久化完成时间
    """

    note_id: UUID = field(default_factory=uuid4)
    query: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    lineage: dict[str, Any] = field(default_factory=dict)
    persisted: bool = False
    persisted_at: datetime | None = None


class PersistentNoteTaker:
    """持久化笔记记录器 — 压缩前必须调用

    流程：
    1. 提取关键实体 → 写入 StrategicArchive
    2. 生成结构化摘要 → 写入 PostgreSQL
    3. 记录检索血缘 → 审计日志
    """

    def __init__(
        self,
        entity_extraction_service: EntityExtractionPort,
        strategic_archive: StrategicArchiveService,
        audit_service: AuditServicePort,
    ) -> None:
        ...

    async def take_notes(
        self,
        query: str,
        retrieved_docs: list[SearchResult],
        user_id: str,
        session_id: str,
    ) -> PersistentNote:
        ...

    def verify_persisted(self, note: PersistentNote) -> bool:
        """验证持久化是否完成（压缩前检查）"""
        ...
```

#### 文件 2: `src/domain/services/context_compressor.py`（新增）

```python
"""领域层上下文压缩器 — 检索-压缩循环的核心步骤

遵循系统公理二：压缩前必须持久化。
输入 Top-100 文档（~50K tokens），输出压缩后上下文（~2K tokens）。
压缩率 ≥ 70%。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.ports.l3_vector import SearchResult


@dataclass(frozen=True)
class CompressedContext:
    """压缩上下文值对象

    Attributes:
        context: 压缩后的上下文文本
        compression_ratio: 压缩率
        quality_score: 质量评分
        token_count: 压缩后 token 数
        persistent_note_ref: 关联的持久化笔记 ID
    """

    context: str = ""
    compression_ratio: float = 0.0
    quality_score: float = 0.0
    token_count: int = 0
    persistent_note_ref: str = ""


class ContextCompressor:
    """上下文压缩器

    压缩算法：
    1. 基于持久化笔记中的关键实体提取关键信息
    2. LLM 摘要生成（Temperature=0.3）
    3. 压缩率验证（≥70%，不足触发二次压缩）
    4. 质量评估（信息熵 + 关键实体覆盖率，<0.7 触发二次生成）
    """

    COMPRESSION_RATIO_TARGET = 0.70
    CONTEXT_SIZE_LIMIT = 2000

    def __init__(
        self,
        llm_client: LLMClientPort,
        note_taker: PersistentNoteTaker,
    ) -> None:
        ...

    async def compress(
        self,
        retrieved_docs: list[SearchResult],
        query: str,
        persistent_note: PersistentNote,
    ) -> CompressedContext:
        ...
```

#### 文件 3: `src/domain/services/compression_quality_evaluator.py`（新增）

```python
"""领域层压缩质量评估器 — 检索-压缩循环的质量守卫

评估压缩结果的信息熵 + 关键实体覆盖率 + 冗余度。
评分 < 0.7 触发二次生成。
"""

from __future__ import annotations

from src.domain.ports.l3_vector import SearchResult


class CompressionQualityEvaluator:
    """压缩质量评估器

    评分维度：
    1. 信息熵（40%）：压缩后信息密度
    2. 关键实体覆盖率（40%）：Top-20 关键实体保留比例
    3. 冗余度（20%）：重复内容比例
    """

    async def evaluate(
        self,
        compressed_context: CompressedContext,
        original_docs: list[SearchResult],
        key_entities: list[dict[str, Any]],
    ) -> float:
        ...
```

---

### 4.7 端口返回类型精确化（P1 质量改进）

**变更类型：** 修改文件
**涉及 Story：** 3.6, 3.7

#### `src/domain/ports/summary_generation.py` — `SummaryGenerationPort`

```diff
     async def generate_summary(
         self,
         ...
-    ) -> Any:
+    ) -> Any:  # 保留 Any（领域层不依赖 pydantic，Schema 类型由调用方确定）
         ...
```

**结论：** `Any` 是合理设计选择（领域层零外部依赖原则），不做修改。

#### `src/domain/ports/relevance_evaluation.py` — `RelevanceEvaluationPort`

```diff
     async def evaluate(
         self,
         ...
-    ) -> Any:
+    ) -> Any:  # 保留 Any（与 SummaryGenerationPort 一致）
         ...
```

**结论：** `Any` 是合理设计选择，不做修改。

---

### 4.8 组合根注册更新

**`src/composition_root.py`** — 注册新增的检索-压缩循环服务

```python
# === 检索-压缩循环（系统公理二）===
from src.domain.services.persistent_note_taker import PersistentNoteTaker
from src.domain.services.context_compressor import ContextCompressor
from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator

register_port(
    name="persistent_note_taker",
    version="v1.0.0",
    interface=PersistentNoteTaker,
    impl=lambda resolver: PersistentNoteTaker(
        entity_extraction_service=resolver.resolve("entity_extraction_service"),
        strategic_archive=resolver.resolve("strategic_archive_service"),
        audit_service=resolver.resolve("audit_service"),
    ),
    module="src.domain.services.persistent_note_taker",
    lifetime=Lifetime.SCOPED,
    owner="foundation-team",
    tags=("retrieval", "compression", "domain"),
)

register_port(
    name="context_compressor",
    version="v1.0.0",
    interface=ContextCompressor,
    impl=lambda resolver: ContextCompressor(
        llm_client=resolver.resolve("llm_client"),
        note_taker=resolver.resolve("persistent_note_taker"),
    ),
    module="src.domain.services.context_compressor",
    lifetime=Lifetime.SCOPED,
    owner="foundation-team",
    tags=("retrieval", "compression", "domain"),
)

register_port(
    name="compression_quality_evaluator",
    version="v1.0.0",
    interface=CompressionQualityEvaluator,
    impl=lambda resolver: CompressionQualityEvaluator(),
    module="src.domain.services.compression_quality_evaluator",
    lifetime=Lifetime.SCOPED,
    owner="foundation-team",
    tags=("retrieval", "compression", "domain"),
)
```

---

## 5. 实施计划

### 5.1 执行顺序

| 序号 | 任务 | 文件数 | 依赖 | 预估工时 | 验证方式 |
|------|------|--------|------|---------|---------|
| **P0-1** | 新增端口层次定义 | 2 | 无 | 30min | ruff + mypy |
| **P0-2** | 应用服务实现端口 | 4 | P0-1 | 30min | ruff + mypy + pytest |
| **P0-3** | 构造函数类型修正 | 9 | P0-1 | 30min | ruff + mypy + pytest |
| **P0-4** | 注册 domain_dictionary_router | 1 | 无 | 5min | 启动测试 |
| **P0-5** | 新增检索-压缩循环（3 个服务） | 3 | P0-1 | 2h | ruff + mypy + pytest |
| **P0-6** | 组合根注册更新 | 1 | P0-5 | 10min | 启动测试 |
| **P1-1** | 端口返回类型精确化评估 | 0 | 无 | 15min | 代码审查（决策：不修改） |

### 5.2 验证清单

```bash
# 代码质量
poetry run ruff check src/ tests/
poetry run ruff format src/ tests/ --check
poetry run mypy src/

# 架构约束
poetry run lint-imports

# 测试
poetry run pytest tests/unit/application/services/ -x -q
poetry run pytest tests/unit/architecture/ -x -q
poetry run pytest tests/contracts/ -x -q

# 变更文件数最终验证
git diff --stat
```

### 5.3 回滚方案

所有变更均为新增文件 + 修改类型注解，不涉及业务逻辑变更：

- **新增文件**（`search_service.py`, `hybrid_search.py`, 3 个压缩服务）：`git rm` 即可
- **修改文件**（服务类继承 + 类型修正）：`git checkout -- <file>` 还原
- **路由注册**（`app.py`）：`git checkout -- src/interfaces/api/app.py` 还原

---

## 6. 实施交接

| 角色 | 职责 |
|------|------|
| **Developer** | 执行 P0-1~P0-6 全部变更，确保测试通过 |
| **QA** | 验证词典 API 端点可用，验证 13 个服务类型约束 |
| **Architect** | 审查新增端口定义和检索-压缩循环实现 |

**成功标准：**
- ✅ `ruff check` 零告警
- ✅ `mypy src/` 零告警（类型检查通过）
- ✅ `pytest tests/` 全部通过（含现有测试 + 新增压缩循环测试）
- ✅ `domain_dictionary_router` API 端点响应正常
- ✅ 新增检索-压缩循环的 `take_notes()` → `compress()` → `evaluate()` 链路通过集成测试

---

*文档生成：2026-08-22 | 范围：Minor | 估算工时：~4 小时 | 风险：低*
