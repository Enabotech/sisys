# Story 2-8: 语义分块

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** RAG 工程师,
**I want** 系统对文档进行语义分块（基于文档语义边界而非固定字数切片）,
**So that** 检索结果更符合语义完整性。

### 业务价值

语义分块是文档从"解析完成"到"可检索"的关键中间环节（FR-DM-08，P0/MVP），直接影响检索质量：

- **语义完整性**：按章节标题、段落边界、表格边界、页面边界进行自然切分，保证每个分块包含完整语义单元
- **检索精度提升**：相比固定字数切片，语义边界切分避免"半句话"出现在相邻两个分块中，提升 RRF 融合排序的准确性
- **向量化前置条件**：分块后的文本段落是 `generate_embedding`（Story 3.1a）和 `index_document`（Qdrant）的输入单元
- **Epic 3 关键依赖**：Story 3.1a（Dense 语义检索）和 Story 3.1b（BM25 稀疏检索）均依赖语义分块的输出

本 Story 是 Epic 2 文档处理流水线的第 8 个节点，**依赖 Story 2.2a（基础格式解析）** 提供 `ParsedDocument` 输入。**被 Epic 3 Story 3.1a（Dense 语义检索）依赖**——分块输出直接作为 Qdrant 向量索引的单元。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 语义边界识别与切分

**Given** 文档解析完成，`ParsedDocument` 包含结构化页面/文本/表格元素
**When** 系统执行语义分块
**Then** 基于以下语义边界进行切分：
  - 段落边界（连续文本中的空行/双换行）
  - 章节标题边界（`ParsedElement.metadata["style"]` 中的 `"h1"`~`"h6"` 或 `"Heading 1"`~`"Heading 9"` 样式——具体见代码库调研关键发现第 1 条）
  - 表格边界（`ParsedTable` 元素始终作为独立分块边界，表格内容不分割）
  - 页面边界（跨页文本不合并——新页起新分块）
  - Token 硬限制边界（`token_limit`：单段超过 `max_chunk_size_tokens` 时按字符比例硬切分）
**And** 分块内容保持原始阅读顺序（page_number 升序 → 同页内 texts 列表原始顺序——解析器已保证元素顺序，不依赖 bbox 坐标排序）

**验证标准/Validation Criteria:**
- [ ] 段落边界识别准确：`\n\n` 或 `\n\s*\n` 模式切分段落
- [ ] 章节标题识别准确：`ParsedElement.metadata["style"]` 中的 `"h1"`~`"h6"` 或 `"Heading 1"`~`"Heading 9"` 样式作为新分块起点（非 DocLayNet label）
- [ ] 表格独立分块：每个 `ParsedTable` 对应一个独立分块，表格行列被展平为结构化文本
- [ ] 页面边界必然切分：`ParsedPage.page_number` 变更时必然创建新分块
- [ ] 阅读顺序保持：分块列表的 `chunk_index` 严格按原始阅读顺序递增

### AC-2: Token 计数与分块大小控制

**Given** 语义边界已识别
**When** 系统聚合相邻文本段落为分块
**Then** 每个分块的 token 数量控制在目标范围内：
  - 目标大小：≈300 tokens（通过 `ChunkingConfig.target_chunk_size_tokens` 可配置）
  - 最小阈值：≥50 tokens（低于阈值的分块合并到前一个分块，除非跨越语义边界）
  - 最大硬限制：≤8192 tokens（bge-m3 `max_length` 硬限制；服务启动时加载 BGE-M3 tokenizer 配置读取）
**And** 分块不跨语义边界合并（段落边界可合并，但章节/表格/页面边界不合并）

**验证标准/Validation Criteria:**
- [ ] Token 计数使用字符启发式算法（中文≈0.8 tokens/字符，英文≈1.2 tokens/词），参考 XLM-RoBERTa（SentencePiece）tokenizer 比例，无需引入第三方 tokenizer 库
- [ ] 目标大小 300 tokens 在 `ChunkingConfig` 中单点配置
- [ ] 分块大小在 `min_chunk_size_tokens`（50）到 `max_chunk_size_tokens`（8192）之间，实际聚合范围围绕 `target_chunk_size_tokens`（300）波动
- [ ] 语义边界优先级高于大小控制（不牺牲语义完整性换取大小均匀）
- [ ] `SemanticChunk.token_count` 字段记录实际估算 token 数

### AC-3: 分块元数据完整性

**Given** 语义分块生成完成
**When** 分块被存储和索引
**Then** 每个分块携带完整的元数据：
  - `chunk_id`: UUID，分块唯一标识
  - `document_id`: 所属文档 UUID
  - `chunk_index`: 文档内排序序号（0-indexed，严格递增）
  - `boundary_type`: 分块边界类型（`paragraph` / `section_header` / `table` / `page_break` / `token_limit`）
  - `token_count`: 估算 token 数
  - `page_range`: [start_page, end_page] 页码范围（1-indexed）
  - `content_hash`: 分块内容的 SHA256 哈希（用于去重和变更检测）
  - `metadata`: 扩展元数据字典（包含文档级 `business_domain`、`license` 等透传字段）

**验证标准/Validation Criteria:**
- [ ] 所有元数据字段非空且类型正确
- [ ] `content_hash` 使用 `hashlib.sha256(content.encode()).hexdigest()` 计算
- [ ] `page_range` 精确反映分块涉及的页码范围
- [ ] `boundary_type` 准确表示创建此分块的语义边界类型
- [ ] 分块元数据可序列化为 JSON（`to_dict()` 方法）

### AC-4: 分块集成到文档流水线

**Given** 文档解析完成并发布 `DocumentProcessed` 事件
**When** 语义分块处理器接收事件
**Then** 对 `ParsedDocument` 执行分块
**And** 分块结果存入 `document.metadata["chunks"]`（JSONB 列表）
**And** 发布 `RAGIndexed` 事件（含 `chunk_count`）
**And** 分块延迟 P95 < 500ms

**验证标准/Validation Criteria:**
- [ ] 分块结果持久化到 `documents.metadata` JSONB 列
- [ ] 分块不阻塞解析主流程（异步事件驱动触发）
- [ ] 分块失败不影响文档的 `parse_status`（解析状态保持 COMPLETED）
- [ ] `RAGIndexed` 事件的 `chunk_count` 准确反映实际分块数量

### AC-5: 分块文本格式化

**Given** 分块包含文本和表格内容
**When** 生成分块的 `content` 字符串
**Then** 文本按阅读顺序拼合
**And** 表格内容展平为结构化字符串格式：
  ```
  [表格: 标题或位置]
  | 表头1 | 表头2 | ...
  | 数据1 | 数据2 | ...
  ```
  （标题/前缀行单独一行，表头和数据行各占一行，pipe-separated 格式）
**And** 文档级元数据（`business_domain`）透传到分块 `metadata` 中

**验证标准/Validation Criteria:**
- [ ] 表格展平格式包含表头（如有）和数据行
- [ ] 表格展平文本保持列对齐（pipe-separated 格式）
- [ ] 分块 content 不包含 Markdown 标记（纯文本）
- [ ] 空表格（无数据行）被跳过（不产生分块）

---

## 🏗️ SDD+TDD 融合开发

### SDD 规范定义（Task 0 — 必选前置）

#### 领域事件 Schema

- [ ] 本 Story 不需要新增领域事件。
  - 分块完成后发布**已有的** `RAGIndexed` 事件（`src/domain/events/workflow_events.py`）
  - `RAGIndexed` 的 `chunk_count` 字段从默认值 0 更新为实际分块数量
  - **注意：** `RAGIndexed` 事件当前缺少 `tenant_id` 字段。需在 `RAGIndexed` 事件定义中新增 `tenant_id: str = ""` 字段，与 `DocumentProcessed` 事件对齐，确保多租户场景下事件可正确路由
  - 分块通过事件处理器监听 `DocumentProcessed` 异步触发（对齐 Story 2-6 `DocumentVersionHandler` 模式）
  - 事件订阅注册：`SemanticChunkingHandler` 需要在 `composition_root.py` 中注册为 `SINGLETON` 端口，并通过 `EventListener` 或消息总线消费者绑定到 `DocumentProcessed` 事件

#### 数据模型

- [ ] 新建 `ChunkBoundaryType` 枚举（`src/domain/value_objects/semantic_chunk.py`）

  ```python
  from enum import Enum

  class ChunkBoundaryType(str, Enum):
      PARAGRAPH = "paragraph"        # 段落边界（\n\n）
      SECTION_HEADER = "section_header"  # 章节标题边界
      TABLE = "table"                # 表格边界
      PAGE_BREAK = "page_break"      # 跨页边界
      TOKEN_LIMIT = "token_limit"    # 硬限制 token 上限切分
  ```

- [ ] 新建 `ChunkingConfig` 值对象（`src/domain/value_objects/semantic_chunk.py`）

  ```python
  @dataclass(frozen=True)
  class ChunkingConfig:
      target_chunk_size_tokens: int = 300   # 目标分块大小（or.md 二.3.(5) 明确要求）
      min_chunk_size_tokens: int = 50       # 最小分块阈值（低于则合并）
      max_chunk_size_tokens: int = 8192     # 硬限制：BGE-M3 的 max_length（XLM-RoBERTa tokenizer）
  ```

  **设计说明：**
  - `max_chunk_size_tokens=8192` 对齐 bge-m3 模型的最大输入长度（FlagEmbedding 文档，基于 XLM-RoBERTa 位置编码扩展至 8192，非标准 XLM-RoBERTa 默认的最大位置编码 512）
  - 所有阈值可配置，允许未来根据模型变更调整
  - frozen dataclass 仅使用 Python 标准库（`dataclasses`），满足领域层零依赖

- [ ] 新建 `SemanticChunk` 值对象（`src/domain/value_objects/semantic_chunk.py`）

  ```python
  @dataclass(frozen=True)
  class SemanticChunk:
      chunk_id: uuid.UUID               # UUID，分块唯一标识
      document_id: uuid.UUID            # 所属文档 UUID
      content: str                      # 分块文本内容
      chunk_index: int                  # 排序序号（0-indexed）
      boundary_type: ChunkBoundaryType  # 创建边界类型
      token_count: int                  # 估算 token 数
      page_start: int                   # 起始页码（1-indexed）
      page_end: int                     # 结束页码（1-indexed）
      content_hash: str                 # SHA256 内容哈希
      metadata: dict[str, Any]          # 扩展元数据（business_domain 等）

      def to_dict(self) -> dict[str, Any]: ...
  ```

  **设计说明：**
  - frozen dataclass，构造后不可变
  - `to_dict()` 方法用于序列化到 `document.metadata["chunks"]` JSONB 列
  - `content_hash` 在构造时由调用方计算（`hashlib.sha256`），值对象不持有哈希逻辑
  - 所有字段在构造时强制传入（无默认值），确保值对象语义完整

#### 统一端口定义注册与管理

- [ ] 新建 `SemanticChunkerPort` 领域端口（`src/domain/ports/semantic_chunker.py`）

  ```python
  @runtime_checkable
  class SemanticChunkerPort(Protocol):
      async def chunk(
          self,
          parsed_doc: ParsedDocument,
          config: ChunkingConfig | None = None,
      ) -> list[SemanticChunk]:
          """对解析完成的结构化文档执行语义分块。

          算法流程：
          1. 遍历 ParsedDocument.pages（page_number 升序）
          2. 每页内按阅读顺序迭代元素的 content
          3. 检测语义边界并切分段落
          4. 按 ChunkingConfig 聚合段落为目标大小分块
          5. 生成 SemanticChunk 列表（含完整元数据）

          Args:
              parsed_doc: 解析完成的结构化文档
              config: 分块配置（为 None 时使用 ChunkingConfig() 默认值）

          Returns:
              SemanticChunk 列表（按 chunk_index 升序；空文档返回空列表，不抛异常）

          Raises:
              ChunkingError: 分块算法内部异常（如不可序列化的数据结构）
          """
          ...
  ```

  **设计规则对齐：**
  - R1：`SemanticChunkerPort` 是领域层抽象端口（Protocol），定义纯业务契约
  - R2：应用层 `SemanticChunkingService` 注入此端口（组合注入模式）
  - R3：基础设施层 `SemanticChunkerImpl` 实现此端口

- [ ] 端口注册到 composition_root（`name="semantic_chunker"`, `version="v1.0.0"`, `lifetime=SINGLETON`）
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_semantic_chunker.py`）

#### 领域异常契约

- [ ] 新增异常：`ChunkingError`（EXCEPTION_218）
  - 归属模块：`storage_exceptions.py`（存储子域，编码范围 211-219；已使用 211-217，218 空闲可用）
  - 继承自 `BusinessRuleViolationError`（EXCEPTION_207）—— 分块失败是"业务规则违反"
    - **继承说明**：storage 子域异常继承 business 基类，CI 规则 R2 允许。`DocumentVersionConflictError`（216）继承 `ConflictError`，`MetadataValidationError`（217）继承 `BusinessRuleViolationError`，本异常对齐 `MetadataValidationError` 模式
  - 构造器参数（对齐 `BaseException.__init__` 标准模式）：
    ```python
    def __init__(
        self,
        document_id: UUID,
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
    ```
  - 消息格式：`"语义分块失败: document_id={doc_id}, reason={reason}"`
  - `context` 暴露：`{"document_id": str, "reason": str}`（合并到传入的 `context` 字典）
  - 适用场景：`ChunkingError` 仅用于内部算法异常（如不可序列化的数据结构导致分块失败）。空文档/所有页面无有效文本内容时，分块器返回空列表且不抛异常。
- `_CLASS_TO_SUBDOMAIN` 注册：`"ChunkingError": "storage"`（在 `_code_ranges.py` 中）
- [ ] 异常注册到 `_code_ranges.py`、`__init__.py`、`exception_handlers.py`
  - HTTP 映射：`ChunkingError` → `422 UNPROCESSABLE ENTITY`
- [ ] 测试覆盖：构造/`to_dict()`/HTTP 映射/编码唯一性/子域范围

#### API 契约

- [ ] **不新增 API 端点**。分块是内部流水线机制，无外部 REST 接口
- [ ] 分块结果通过文档查询 API 的 `metadata.chunks` 字段暴露（无需修改 OpenAPI schema——metadata 已是 JSONB 自由字段）

#### 六边形架构约束

| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | `SemanticChunk` 值对象 + `ChunkBoundaryType` 枚举 + `ChunkingConfig` + `SemanticChunkerPort` |
| application | `src/application/` | `SemanticChunkingService` 编排 + `SemanticChunkingHandler` 事件处理器 |
| infrastructure | `src/infrastructure/` | `SemanticChunkerImpl` 实现（规则驱动的边界检测和文本聚合） |
| interfaces | `src/interfaces/` | 无新增（分块无外部接口） |

**领域层零依赖原则**
- `src/domain/value_objects/semantic_chunk.py` 仅使用 Python 标准库（dataclass / uuid / enum / hashlib）

#### 验收标准 Gherkin

- [ ] 验收测试文件：`tests/acceptance/test_acceptance_semantic_chunking.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_semantic_chunking.py`
- [ ] 覆盖场景：
  - 场景 1: 单段落短文档 → 生成 1 个分块
  - 场景 2: 多段落文档 → 按段落边界切分，每块 ≈300 tokens
  - 场景 3: 章节标题边界 → `metadata["style"]` 中的 `"h1"`~`"h6"` 或 `"Heading 1"`~`"Heading 9"` 样式触发新分块
  - 场景 4: 表格独立分块 → 表格内容展平为结构化文本
  - 场景 5: 跨页边界 → 新页码必然新分块
  - 场景 6: 大段落超过 max_chunk_size_tokens → 按 token_limit 类型硬切分，验证 `boundary_type` 为 `TOKEN_LIMIT`
  - 场景 7: 空文档 → 返回空列表（不抛异常）
  - 场景 8: Markdown 输出顺序异常 → 标题先于段落，分块按原始阅读顺序聚合，标题作为独立硬边界
  - 场景 9: PDF 整页文本二次分割 → 单页含多个段落（\n\n 分隔），正确分割为逻辑段落
  - 场景 10: HTML body_blob 二次分割 → 标题逐个提取，剩余 body 文本按段落分割
  - 场景 11: 空表格跳过 → 无数据行的表格不产生分块
  - 场景 12: content_hash 一致性 → 相同内容产生相同哈希，内容变更后哈希变化
  - 场景 13: Word Heading 样式归一化 → `"Heading 1"`~`"Heading 9"` 均识别为 `SECTION_HEADER` 边界
  - Edge Cases: 纯表格文档（无文本）、全中文/全英文/中英混合 token 计数精度验证（误差 <20%）

**Task 0 完成标志：**
- [ ] 规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | SemanticChunk 值对象 | 构造/不可变性/to_dict/content_hash | `test_semantic_chunk.py` | Task 1 |
| **TDD 单元测试** | ChunkingConfig | 默认值/自定义值/不可变性 | `test_semantic_chunk.py` | Task 1 |
| **TDD 单元测试** | SemanticChunkerImpl | 段落边界/章节边界/表格边界/页面边界/token 计数/边界聚合/硬限制切分 | `test_semantic_chunker_impl.py` | Task 2 |
| **TDD 单元测试** | SemanticChunkingService | Mock 端口测试编排逻辑（`_make_service()` 工厂函数模式） | `test_semantic_chunking_service.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_semantic_chunking.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_semantic_chunking.py` | Task 0 |
| **TDD 验收测试** | 收尾验收 | 完成清单最终确认 | `.feature` + `.py` | Task 6 |
| **TDD 契约测试** | SemanticChunkerPort | 端口注册/版本/方法签名 | `test_port_contract_semantic_chunker.py` | Task 1 |
| **TDD 领域异常测试** | ChunkingError | 构造/to_dict/HTTP 422 映射 | `test_chunking_exceptions.py` | Task 1 |
| **TDD 领域异常测试** | 编码唯一性 + 子域范围 | 自动反射扫描 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_semantic_chunking.py` | Task 4 |
| **集成测试** | 解析→分块完整流程 | 真实 PG/MinIO + Mock 嵌入 | `test_semantic_chunking_integration.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

| 层类型 | 目标值 | 说明 |
|--------|--------|------|
| 整体 | ≥80% | pytest --cov=src --cov-fail-under=80 |
| 领域层 | ≥90% | SemanticChunk + ChunkingConfig + ChunkBoundaryType + ChunkingError |
| 应用层 | ≥85% | SemanticChunkingService + SemanticChunkingHandler |
| 基础设施层 | ≥90% | SemanticChunkerImpl（规则驱动的边界检测算法，纯确定性逻辑，无外部依赖） |
| 集成测试 | ≥70% | 解析→分块完整流程 |

#### 代码质量门禁
- [ ] Ruff 检查通过（`ruff check src/ tests/`）
- [ ] MyPy 类型检查通过（`mypy src/`）
- [ ] 性能基准测试通过（分块延迟 P95 < 500ms）
- [ ] **禁止** `# noqa`、`# type: ignore` 等抑制注释
- [ ] **禁止** `raise ValueError` — 使用 `ChunkingError` 领域异常

### Known Limitation: Markdown 标题—段落归属偏差

**问题描述：** Markdown 解析器先输出所有标题、再所有段落、最后所有表格（非文档原始顺序）。分块器仅将标题作为独立硬边界，可能导致标题后的段落被错误归入后一个标题的分块。

**示例：**
```
# 第一章
段落A属于第一章。
# 第二章
段落B属于第二章。
```
MD 解析器输出：`[H1, H2, P1, P2]`
当前分块结果：Chunk1=`第一章`，Chunk2=`第二章`+`段落A`+`段落B`（段落A被错误归入第二章）

- **影响范围：** `text/markdown` 格式文档
- **严重程度：** P1（MVP 可接受，RRF 融合排序可部分弥补段落归属偏差）
- **计划修复：** 待配合 Story 2-2a MD 解析器输出顺序修复，或新增分块后排序逻辑
- **当前缓解措施：** 仅将标题作为硬边界切分，检索时依赖 RRF 融合排序弥补归属偏差

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 语义边界识别与切分 | Task 2 | 2.4-2.9 | `test_semantic_chunker_impl.py` |
| AC-2 | Token 计数与分块大小控制 | Task 2 | 2.1-2.3, 2.7-2.9 | `test_semantic_chunker_impl.py` |
| AC-3 | 分块元数据完整性 | Task 1 | 1.1-1.6 | `test_semantic_chunk.py` |
| AC-4 | 分块集成到文档流水线 | Task 3 | 3.1-3.6 | `test_semantic_chunking_service.py` |
| AC-5 | 分块文本格式化 | Task 2 | 2.4-2.6 | `test_semantic_chunker_impl.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3

- [ ] Subtask 0.1: 定义 SemanticChunk / ChunkBoundaryType / ChunkingConfig 值对象规范
- [ ] Subtask 0.2: 定义 SemanticChunkerPort 端口契约
- [ ] Subtask 0.3: 定义 ChunkingError 异常契约（EXCEPTION_218）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_semantic_chunking.feature`
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_semantic_chunking.py`
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层 — 值对象、端口与异常

**关联 AC:** AC-3

#### TDD 循环 A：ChunkBoundaryType 枚举 + ChunkingConfig 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_semantic_chunk.py`（测试枚举值/Config 默认值/不可变性） |
| 🟢 绿 | 实现 `src/domain/value_objects/semantic_chunk.py`（`ChunkBoundaryType` + `ChunkingConfig`） |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写枚举和 Config 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现枚举和 Config
- [ ] Subtask 1.3: 🔄 重构 — 优化代码

#### TDD 循环 B：SemanticChunk 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SemanticChunk 测试（构造/不可变性/to_dict/字段访问） |
| 🟢 绿 | 实现 `SemanticChunk` frozen dataclass + `to_dict()` |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写值对象失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 `SemanticChunk`
- [ ] Subtask 1.6: 🔄 重构 — 优化代码

#### TDD 循环 C：SemanticChunkerPort 端口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_semantic_chunker.py` |
| 🟢 绿 | 实现 `src/domain/ports/semantic_chunker.py`（`SemanticChunkerPort` Protocol） |
| 🔄 重构 | 注册端口到 composition_root（`name="semantic_chunker"`, `SINGLETON`） |

- [ ] Subtask 1.7: 🔴 红 — 端口契约测试
- [ ] Subtask 1.8: 🟢 绿 — 实现端口 Protocol
- [ ] Subtask 1.9: 🔄 重构 — composition_root 注册

#### TDD 循环 D：ChunkingError 异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_chunking_exceptions.py`（构造/`to_dict()`/HTTP 422 映射） |
| 🟢 绿 | 在 `src/domain/exceptions/storage_exceptions.py` 中新增 `ChunkingError`（EXCEPTION_218） |
| 🔄 重构 | 注册到 `_code_ranges.py`、`__init__.py`、`exception_handlers.py` |

- [ ] Subtask 1.10: 🔴 红 — 异常测试
- [ ] Subtask 1.11: 🟢 绿 — 实现异常类
- [ ] Subtask 1.12: 🔄 重构 — 三处同步注册 + 编码唯一性验证

**完成标准/Definition of Done:**
- [ ] 值对象全部实现且测试通过
- [ ] 端口契约定义且测试通过
- [ ] 异常测试通过（构造/to_dict/HTTP 映射/编码唯一性）
- [ ] 领域层覆盖率 ≥ 90%

---

### Task 2: 基础设施层 — SemanticChunkerImpl 实现

**关联 AC:** AC-1, AC-2, AC-5

> **核心算法：** 规则驱动的语义边界检测 + 令牌预算聚合，无 ML 模型依赖。

#### Token 计数算法

```python
import re

def estimate_tokens(text: str) -> int:
    """字符启发式 token 估算（领域层纯函数，零依赖）。

    参考 XLM-RoBERTa（SentencePiece）tokenizer 的字符比例：
    - 中文字符 ≈ 1.25 字符/token → 1 token ≈ 0.8 中文字符
    - 英文词 ≈ 0.83 词/token → 1 token 约覆盖 5 英文字符（= avg word 5 chars / 1.2 tokens per word）
    - 混合文本：按字符类别分段估算后取加权平均

    精度：启发式 vs XLM-RoBERTa tokenizer 误差 <20%（足够达到 300±50 tokens 的目标精度）。
    """
    ...
```

#### TDD 循环 A：Token 计数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 token 计数测试（中文/英文/中英混合/空字符串/纯标点/长文本） |
| 🟢 绿 | 实现 `estimate_tokens()` 纯函数 |
| 🔄 重构 | 优化字符类别分段逻辑 |

- [ ] Subtask 2.1: 🔴 红 — token 计数测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `estimate_tokens()`
- [ ] Subtask 2.3: 🔄 重构 — 优化

#### TDD 循环 B：边界检测

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写边界检测测试（段落边界/章节标题/表格/页面） |
| 🟢 绿 | 实现 `_detect_boundaries()` 私有方法 |
| 🔄 重构 | 提取边界检测策略 |

- [ ] Subtask 2.4: 🔴 红 — 边界检测失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现边界检测
- [ ] Subtask 2.6: 🔄 重构 — 策略提取

#### TDD 循环 C：分块聚合

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写分块聚合测试（单段落/多段落聚合/大小控制/最小阈值合并/最大限制硬切分） |
| 🟢 绿 | 实现 `_aggregate_chunks()` 私有方法 |
| 🔄 重构 | 优化合并策略 |

- [ ] Subtask 2.7: 🔴 红 — 分块聚合失败测试
- [ ] Subtask 2.8: 🟢 绿 — 实现分块聚合
- [ ] Subtask 2.9: 🔄 重构 — 优化合并策略

**算法伪代码：**

```python
class SemanticChunkerImpl:
    async def chunk(self, parsed_doc: ParsedDocument, config=None) -> list[SemanticChunk]:
        cfg = config or ChunkingConfig()
        segments = self._extract_segments(parsed_doc)  # [(boundary_type, text, page_num)]
        chunks = self._aggregate_segments(segments, cfg)
        return chunks

    def _extract_segments(self, doc: ParsedDocument) -> Generator[tuple[ChunkBoundaryType, str, int], None, None]:
        """提取所有文本片段及其边界类型和页码。

        关键处理：
        - 跨页检测：页码变化时自动插入 PAGE_BREAK 边界
        - PDF/HTML 二次分割：对长文本元素（>500 字符）按 \n\n 拆分为逻辑段落
        - 标题样式归一化：处理 "h1"/"Heading 1" 等多种格式
        """
        prev_page = 0
        for page in doc.pages:
            # 跨页检测：页码变化时生成 PAGE_BREAK 边界
            if page.page_number != prev_page and prev_page > 0:
                yield (ChunkBoundaryType.PAGE_BREAK, "", page.page_number)  # 使用新页码
            prev_page = page.page_number

            for element in page.texts:
                boundary = self._classify_boundary(element)
                content = element.content
                # PDF/HTML 等大块文本需要二次段落分割
                # 判定条件：元素内容过长（>500 字符）且包含段落分隔符
                if boundary == ChunkBoundaryType.PARAGRAPH and len(content) > 500:
                    # 先尝试双换行分割（PDF/Word 段落分隔）
                    sub_paragraphs = re.split(r"\n\s*\n", content.strip())
                    if len(sub_paragraphs) <= 1:
                        # 无双换行，按单换行分句聚合（HTML 分隔符为 \n）
                        sub_paragraphs = [line.strip() for line in content.split("\n") if line.strip()]
                    for para in sub_paragraphs:
                        if para.strip():
                            yield (ChunkBoundaryType.PARAGRAPH, para.strip(), page.page_number)
                else:
                    yield (boundary, content, page.page_number)

            for table in page.tables:
                if not table.rows:  # 跳过空表格（AC-5 要求）
                    continue
                text = self._flatten_table(table)
                yield (ChunkBoundaryType.TABLE, text, page.page_number)

    def _classify_boundary(self, element: ParsedElement) -> ChunkBoundaryType:
        """根据元素 metadata 分类边界类型。

        支持多种标题格式归一化：
        - Markdown/HTML: "h1"~"h6" → SECTION_HEADER
        - Word: "Heading 1"~"Heading 9" → SECTION_HEADER
        - Word 变体: "Heading 1 Char", "heading 1 + 中文" 等含 heading 子串的样式 → SECTION_HEADER
        - 其他/无 style → PARAGRAPH
        """
        style = element.metadata.get("style", "")
        if not style:
            return ChunkBoundaryType.PARAGRAPH

        style_lower = style.lower()
        # Markdown/HTML 格式: "h1"~"h6"（严格正则匹配，避免误判 "body"、"highlight" 等）
        if re.match(r"^h[1-6]$", style_lower):
            return ChunkBoundaryType.SECTION_HEADER
        # Word 格式: "Heading 1"~"Heading 9"
        if re.match(r"^heading [1-9]$", style_lower):
            return ChunkBoundaryType.SECTION_HEADER
        # Word 变体: 含 "heading" 子串的样式（如 "Heading 1 Char"）
        if "heading" in style_lower:
            return ChunkBoundaryType.SECTION_HEADER

        return ChunkBoundaryType.PARAGRAPH

    def _flatten_table(self, table: ParsedTable) -> str:
        """将 ParsedTable 展平为 pipe-separated 结构化文本"""
        lines = []
        caption = table.table_caption or ""
        prefix = f"[表格: {caption}]" if caption else "[表格]"
        lines.append(prefix)
        if table.header:
            lines.append("| " + " | ".join(table.header) + " |")
        for row in table.rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def _aggregate_segments(self, segments, cfg) -> list[SemanticChunk]:
        """按 token 预算聚合片段为分块"""
        chunks = []
        current_parts = []
        current_tokens = 0

        for boundary, text, page in segments:
            text_tokens = estimate_tokens(text)

            # PAGE_BREAK 边界：创建新分块后跳过追加（空文本不进入 current_parts）
            if boundary == ChunkBoundaryType.PAGE_BREAK:
                if current_parts:
                    chunks.append(self._create_chunk(current_parts, ...))
                    current_parts, current_tokens = [], 0
                continue  # 跳过 PAGE_BREAK 空文本

            # 硬边界：章节/表格边界，必然创建新分块
            if boundary in (ChunkBoundaryType.SECTION_HEADER, ChunkBoundaryType.TABLE):
                if current_parts:
                    chunks.append(self._create_chunk(current_parts, ...))
                    current_parts, current_tokens = [], 0

            # 检查当前段落是否超过 max_chunk_size_tokens（硬限制优先于预算）
            if text_tokens >= cfg.max_chunk_size_tokens:
                if current_parts:  # 先刷新已有段落
                    chunks.append(self._create_chunk(current_parts, ...))
                    current_parts, current_tokens = [], 0
                # 按字符比例切分此大段
                sub_texts = self._split_by_token_limit(text, cfg.max_chunk_size_tokens)
                for i, sub_text in enumerate(sub_texts):
                    sub_tokens = estimate_tokens(sub_text)
                    current_parts.append((ChunkBoundaryType.TOKEN_LIMIT, sub_text, page))
                    current_tokens += sub_tokens
                    if i < len(sub_texts) - 1:
                        chunks.append(self._create_chunk(current_parts, ...))
                        current_parts, current_tokens = [], 0
                continue

            # Token 预算：仅当 current_parts 非空且超限时触发（避免空分块）
            if current_parts and current_tokens + text_tokens > cfg.target_chunk_size_tokens:
                chunks.append(self._create_chunk(current_parts, ...))
                current_parts, current_tokens = [], 0

            current_parts.append((boundary, text, page))
            current_tokens += text_tokens

        if current_parts:
            chunks.append(self._create_chunk(current_parts, ...))

        # 后处理：合并过小分块（< min_chunk_size_tokens）到前一个分块
        # 注意：以 SECTION_HEADER/TABLE/PAGE_BREAK 开头的分块禁止向后合并
        # 短标题分块向前合并到后一个分块（标题属于其后内容）
        return self._merge_small_chunks(chunks, cfg)

    def _create_chunk(
        self,
        parts: list[tuple[ChunkBoundaryType, str, int]],
        chunk_index: int,
        document_id: uuid.UUID,
        metadata: dict[str, Any],
    ) -> SemanticChunk:
        """从片段列表创建 SemanticChunk 值对象。

        聚合策略：
        - content：各片段文本按双换行拼接
        - page_range：取片段中最小和最大页码
        - boundary_type：取第一个片段的边界类型
        - token_count：调用 estimate_tokens 重新估算
        - content_hash：SHA256 计算
        """
        # 聚合文本内容（过滤空文本）
        texts = [t for _, t, _ in parts if t]
        content = "\n\n".join(texts)

        # 页码范围
        pages = [p for _, _, p in parts]
        page_start = min(pages) if pages else 1
        page_end = max(pages) if pages else 1

        # 边界类型：取第一个片段的类型
        boundary_type = parts[0][0] if parts else ChunkBoundaryType.PARAGRAPH

        # 内容哈希
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Token 估算
        token_count = estimate_tokens(content)

        return SemanticChunk(
            chunk_id=uuid.uuid4(),
            document_id=document_id,
            content=content,
            chunk_index=chunk_index,
            boundary_type=boundary_type,
            token_count=token_count,
            page_start=page_start,
            page_end=page_end,
            content_hash=content_hash,
            metadata=metadata,
        )

    def _merge_chunks(self, chunk_a: SemanticChunk, chunk_b: SemanticChunk) -> SemanticChunk:
        """合并两个相邻分块，保持语义完整性。

        合并规则：
        - content：按双换行拼接
        - page_range：取并集
        - boundary_type：取 chunk_a 的类型
        - token_count：两分块 token 数之和（线性近似，无需重新估算）
        - content_hash：重新计算
        """
        content = chunk_a.content + "\n\n" + chunk_b.content
        return SemanticChunk(
            chunk_id=chunk_a.chunk_id,
            document_id=chunk_a.document_id,
            content=content,
            chunk_index=chunk_a.chunk_index,
            boundary_type=chunk_a.boundary_type,
            token_count=chunk_a.token_count + chunk_b.token_count,
            page_start=min(chunk_a.page_start, chunk_b.page_start),
            page_end=max(chunk_a.page_end, chunk_b.page_end),
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            metadata=chunk_a.metadata,
        )

    def _split_by_token_limit(self, text: str, max_tokens: int) -> list[str]:
        """按 token 硬限制切分文本（基于字符比例估算，不引入第三方 tokenizer）"""
        total_tokens = estimate_tokens(text)
        if total_tokens <= max_tokens:
            return [text]
        # 按字符比例切分：每个子段最多 max_tokens 个 token
        ratio = max_tokens / total_tokens
        chars_per_segment = max(1, int(len(text) * ratio))
        segments = []
        for i in range(0, len(text), chars_per_segment):
            segments.append(text[i:i + chars_per_segment])
        return segments

    def _merge_small_chunks(self, chunks: list, cfg) -> list:
        """合并过小分块，但保持语义边界完整性。

        规则：
        - 分块 token 数 < min_chunk_size_tokens 时尝试合并
        - 以 SECTION_HEADER 开头的分块不向后合并（避免跨章节污染）
        - 以 TABLE/PAGE_BREAK 开头的分块不向后合并
        - 短标题分块向前合并到后一个分块（标题属于其后内容）
        """
        if not chunks:
            return chunks
        merged = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            # 检查是否需要合并
            if chunk.token_count < cfg.min_chunk_size_tokens and i > 0:
                # 检查当前分块是否以硬边界开头
                first_boundary = chunk.boundary_type
                if first_boundary in (ChunkBoundaryType.SECTION_HEADER, ChunkBoundaryType.TABLE, ChunkBoundaryType.PAGE_BREAK):
                    # 硬边界分块 → 向前合并到后一个分块
                    if i + 1 < len(chunks):
                        chunks[i + 1] = self._merge_chunks(chunk, chunks[i + 1])
                    else:
                        merged.append(chunk)
                else:
                    # 段落分块 → 向后合并到前一个分块
                    merged[-1] = self._merge_chunks(merged[-1], chunk)
            else:
                merged.append(chunk)
            i += 1
        return merged
```

**完成标准/Definition of Done:**
- [ ] `SemanticChunkerImpl` 实现且测试通过
- [ ] 段落/章节/表格/页面边界检测准确
- [ ] Token 计数误差 <20%
- [ ] 分块大小在 `min_chunk_size_tokens`（50）到 `max_chunk_size_tokens`（8192）范围内，实际聚合围绕 `target_chunk_size_tokens`（300）波动
- [ ] `to_dict()` 序列化正确
- [ ] 基础设施层覆盖率 ≥ 90%

---

### Task 3: 应用层 — SemanticChunkingService 与事件处理器

**关联 AC:** AC-4

#### TDD 循环 A：SemanticChunkingService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_semantic_chunking_service.py`（Mock `SemanticChunkerPort` 测试完整编排流程） |
| 🟢 绿 | 实现 `src/application/services/semantic_chunking_service.py` |
| 🔄 重构 | 运行 `ruff` + `mypy` |

```python
class SemanticChunkingService:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        semantic_chunker: SemanticChunkerPort,
        event_publisher: EventPublisher,
    ) -> None: ...

    async def chunk_document(self, document_id: UUID, tenant_id: str) -> list[SemanticChunk]:
        """对文档执行语义分块并持久化结果。

        1. 从仓储获取 Document 实体
        2. 从 document.metadata["parse_result"] 重构 ParsedDocument
        3. 调用 semantic_chunker.chunk(parsed_doc, config)
        4. 将分块列表序列化为 dict 列表，存入 document.metadata["chunks"]
        5. 保存 Document 实体
        6. 发布 RAGIndexed 事件（chunk_count=len(chunks)）
        """
        ...

    @staticmethod
    def parsed_document_from_dict(data: dict[str, Any]) -> ParsedDocument:
        """从 parse_result dict 重构 ParsedDocument 值对象。

        由于 ParsedDocument 是 frozen dataclass，需递归重构所有嵌套值对象。
        ParsedDocument 本身无 from_dict() 方法，此方法作为应用层反序列化工具。

        实现要点：
        - 递归处理 ParsedPage → ParsedElement / ParsedTable 嵌套层级
        - BoundingBox 为 None 时对应 JSON null
        - ColumnInfo 需要从 col_type 字符串重建 ColumnType 枚举
        """
        pages = []
        for page_data in data.get("pages", []):
            texts = [
                ParsedElement(
                    content=e["content"],
                    bbox=BoundingBox(**e["bbox"]) if e.get("bbox") else None,
                    confidence=e.get("confidence", 1.0),
                    metadata=e.get("metadata", {}),
                )
                for e in page_data.get("texts", [])
            ]
            tables = [self._parsed_table_from_dict(t) for t in page_data.get("tables", [])]
            images = [
                ParsedElement(
                    content=img["content"],
                    bbox=BoundingBox(**img["bbox"]) if img.get("bbox") else None,
                    confidence=img.get("confidence", 1.0),
                    metadata=img.get("metadata", {}),
                )
                for img in page_data.get("images", [])
            ]
            pages.append(ParsedPage(
                page_number=page_data["page_number"],
                texts=texts,
                tables=tables,
                images=images,
            ))

        return ParsedDocument(
            document_id=data["document_id"],
            mime_type=data["mime_type"],
            pages=pages,
            parse_status=data.get("parse_status", "completed"),
            error_message=data.get("error_message"),
            parse_timestamp=data.get("parse_timestamp", ""),
        )

    @staticmethod
    def _parsed_table_from_dict(data: dict[str, Any]) -> ParsedTable:
        """从 dict 重构 ParsedTable 值对象（辅助方法）。

        处理 column_types 和 merged_cells 的递归重建：
        - column_types: 从 col_type 字符串重建 ColumnType 枚举
        - merged_cells: 直接构造 MergedCell 值对象
        """
        column_types = None
        if data.get("column_types"):
            column_types = [
                ColumnInfo(
                    name=ct["name"],
                    col_type=ColumnType(ct["col_type"]),
                    confidence=ct.get("confidence", 1.0),
                    nullable_ratio=ct.get("nullable_ratio", 0.0),
                    sample_values=ct.get("sample_values", []),
                )
                for ct in data["column_types"]
            ]
        merged_cells = None
        if data.get("merged_cells"):
            merged_cells = [MergedCell(**mc) for mc in data["merged_cells"]]

        return ParsedTable(
            rows=data.get("rows", []),
            bbox=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
            header=data.get("header"),
            column_types=column_types,
            merged_cells=merged_cells,
            semantic_confidence=data.get("semantic_confidence"),
            table_caption=data.get("table_caption"),
        )
```

- [ ] Subtask 3.1: 🔴 红 — 编写服务失败测试（3 个场景：成功分块/空文档/解析异常）
- [ ] Subtask 3.2: 🟢 绿 — 实现 `SemanticChunkingService`
- [ ] Subtask 3.3: 🔄 重构 — 优化编排逻辑

#### TDD 循环 B：SemanticChunkingHandler 事件处理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/event_handlers/test_semantic_chunking_handler.py` |
| 🟢 绿 | 实现 `src/application/event_handlers/semantic_chunking_handler.py` |
| 🔄 重构 | 注册到 composition_root + `__init__.py` 导出 |

```python
class SemanticChunkingHandler:
    """监听 DocumentProcessed 事件，异步触发语义分块。

    对齐 Story 2-6 DocumentVersionHandler 模式：
    - 错误隔离：分块失败不影响文档的 parse_status
    - 异步非阻塞：不阻塞解析主流程
    """

    def __init__(self, semantic_chunking_service: SemanticChunkingService) -> None: ...

    async def handle_document_processed(self, event: DocumentProcessed) -> None:
        """文档解析完成后自动触发语义分块"""
        try:
            await self._service.chunk_document(
                document_id=event.document_id,
                tenant_id=event.tenant_id,
            )
        except Exception as e:
            logger.warning("语义分块失败（不影响解析状态）: document_id=%s, error=%s", ...)
```

- [ ] Subtask 3.4: 🔴 红 — 编写事件处理器失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现事件处理器
- [ ] Subtask 3.6: 🔄 重构 — 注册到 composition_root，导出到 `__init__.py`

**完成标准/Definition of Done:**
- [ ] 应用服务实现且测试通过
- [ ] 事件处理器实现且测试通过
- [ ] 分块结果正确持久化到 `document.metadata["chunks"]`
- [ ] `RAGIndexed` 事件正确发布（含 `chunk_count`）
- [ ] 应用层覆盖率 ≥ 85%

---

### Task 4: SDD 架构约束验证测试

**关联 AC:** AC-1

- [ ] Subtask 4.1: 创建 `tests/unit/architecture/test_arch_semantic_chunking.py`
- [ ] Subtask 4.2: 验证领域层零外部依赖（`semantic_chunk.py` + `semantic_chunker.py` 仅标准库）
- [ ] Subtask 4.3: 验证异常继承链正确（`ChunkingError` → `BusinessRuleViolationError` → `BusinessException`）
- [ ] Subtask 4.4: 验证 `SemanticChunkerPort` 是 `@runtime_checkable Protocol`
- [ ] Subtask 4.5: 验证 `SemanticChunk` 为 `frozen=True` dataclass
- [ ] Subtask 4.6: 验证 `SemanticChunkerImpl.__module__` 包含 `"infrastructure"`（基础设施层放置检查）
- [ ] Subtask 4.7: 验证 `isinstance(SemanticChunkerImpl(), SemanticChunkerPort)` 通过运行时兼容性检查
- [ ] Subtask 4.8: 验证 `SemanticChunkingHandler` 注册到 composition_root（`_global_registry` 检查）
- [ ] Subtask 4.9: 运行 `ruff check` + `mypy` + 完整测试套件

**完成标准/Definition of Done:**
- [ ] 所有架构验证测试通过
- [ ] 领域层零依赖验证通过
- [ ] 异常继承链验证通过

---

### Task 5: 集成测试 — 解析→分块完整流程

**关联 AC:** AC-1, AC-2, AC-3, AC-4

- [ ] 新建 `tests/integration/test_semantic_chunking_integration.py`
  - 测试 1: 短文档完整流程（解析→分块→持久化→验证）
  - 测试 2: 多章节长文档（章节标题边界检测）
  - 测试 3: 表格文档（表格独立分块 + 展平格式）
  - 测试 4: 多页文档（页面边界切分）
  - 测试 5: 中英混合文档（token 计数准确性）
  - 测试 6: 分块后的 `metadata.chunks` JSONB 存储和读取（含反序列化为 `SemanticChunk` 验证）
  - 测试 7: `RAGIndexed` 事件发布验证 — Mock EventPublisher 验证 `chunk_count` 准确性

**集成测试约束：**
- 使用真实 PostgreSQL（transaction rollback）
- Schema 自创建（fixture 内完成）
- 测试数据使用 UUID 唯一标识符
- Mock/MinIO（集成测试仅验证分块逻辑，不涉及对象存储）

**完成标准/Definition of Done:**
- [ ] 集成测试全部通过
- [ ] 集成测试覆盖率 ≥ 70%

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写收尾验收场景 |
| 🟢 绿 | 实现 BDD 步骤 |
| 🔄 重构 | 收敛场景命名、统一断言 |

- [ ] Subtask 6.1: 验证 `src` 完成清单逐项确认
- [ ] Subtask 6.2: 验证 `tests` 目录完成清单逐项确认
- [ ] Subtask 6.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 6.4: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] 所有完成清单已验证
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 关键架构决策

| 决策 | 方案 | 理由 |
|------|------|------|
| **分块触发方式** | 事件驱动（`SemanticChunkingHandler` 监听 `DocumentProcessed`） | 对齐 Story 2-6 `DocumentVersionHandler` 模式；关注点分离（解析不关心分块）；错误隔离（分块失败不影响解析状态） |
| **分块存储方式** | `document.metadata["chunks"]` JSONB 列表 | 无需新增数据库迁移；JSONB 天然支持列表查询（`jsonb_array_length`）；单文档分块数通常 < 1000，JSONB 性能满足需求 |
| **Token 计数算法** | 字符启发式（无 tiktoken 依赖） | 零外部依赖满足领域层约束；误差 <20% 满足 300±50 token 目标精度；参考 XLM-RoBERTa SentencePiece 比例 |
| **边界检测策略** | 规则驱动（`metadata["style"]` + 正则 + 页面号） | 确定性逻辑 100% 可靠；无 LLM/ML 依赖保证 P95<500ms；`metadata["style"]` 在各解析器中均有输出 |
| **表格格式化** | pipe-separated 结构化文本 | 保持表格语义在分块中的可读性；方便后续嵌入向量捕获行列关系 |
| **分块粒度** | 平均 300 tokens，硬限制 8192 tokens | 对齐 bge-m3 最佳实践（300 tokens 平衡语义完整性与检索精度）；8192 硬限制对齐 bge-m3 max_position_embeddings |
| **端口设计** | `SemanticChunkerPort` Protocol（领域层）→ `SemanticChunkerImpl`（基础设施层） | 遵循 R1/R2/R3 设计规则；端口可替换（未来可切换为 LLM-based chunker） |

### 项目结构变更

```
src/
├── domain/
│   ├── value_objects/
│   │   └── semantic_chunk.py              # NEW — ChunkBoundaryType + ChunkingConfig + SemanticChunk
│   ├── ports/
│   │   └── semantic_chunker.py            # NEW — SemanticChunkerPort Protocol
│   └── exceptions/
│       ├── storage_exceptions.py          # MODIFY — 新增 ChunkingError (EXCEPTION_218)
│       ├── _code_ranges.py               # MODIFY — 注册 ChunkingError
│       └── __init__.py                    # MODIFY — 导出 ChunkingError
│
├── application/
│   ├── event_handlers/
│   │   └── semantic_chunking_handler.py   # NEW — 监听 DocumentProcessed
│   └── services/
│       └── semantic_chunking_service.py   # NEW — 分块编排服务
│
├── infrastructure/
│   └── document_parsing/
│       └── semantic_chunker_impl.py       # NEW — SemanticChunkerImpl
│
├── interfaces/
│   └── api/
│       └── exception_handlers.py          # MODIFY — ChunkingError → 422 映射
│
└── composition_root.py                     # MODIFY — 注册 semantic_chunker + semantic_chunking_service + handler

tests/
├── unit/
│   ├── domain/
│   │   ├── value_objects/
│   │   │   └── test_semantic_chunk.py            # NEW
│   │   └── exceptions/
│   │       └── test_chunking_exceptions.py       # NEW
│   ├── application/
│   │   ├── services/
│   │   │   └── test_semantic_chunking_service.py # NEW
│   │   └── event_handlers/
│   │       └── test_semantic_chunking_handler.py # NEW
│   ├── infrastructure/
│   │   └── document_parsing/
│   │       └── test_semantic_chunker_impl.py        # NEW — SemanticChunkerImpl 单元测试
│   └── architecture/
│       └── test_arch_semantic_chunking.py         # NEW
├── integration/
│   └── test_semantic_chunking_integration.py     # NEW
├── contracts/
│   └── test_port_contract_semantic_chunker.py    # NEW
└── acceptance/
    ├── test_acceptance_semantic_chunking.feature # NEW
    └── test_acceptance_semantic_chunking.py      # NEW

# 无新增数据库迁移 — chunks 存储在 documents.metadata JSONB 列
```

### 前一个故事学习经验（Story 2-7 元数据校验）

**关键学习：**
1. **领域值对象优先** — Story 2-7 的 `DocumentMetadata` 值对象封装了所有校验逻辑，零外部依赖。本 Story 的 `SemanticChunk`、`ChunkingConfig` 同样应在领域层定义
2. **frozen dataclass 不可变** — 所有值对象统一使用 `@dataclass(frozen=True)`，构造后不可变
3. **异常继承 BusinessRuleViolationError** — 对齐 `MetadataValidationError`（217）的继承模式，CI 规则 R2 允许 storage 子域 → business 基类的合法跨子域继承
4. **事件驱动异步触发** — 对齐 Story 2-6 `DocumentVersionHandler` 模式，不修改主流程服务代码
5. **Google 风格中文 docstring** — 对齐全项目规范

### 性能设计

| 文档规模 | 段落数 | 预期分块数 | 目标延迟 |
|---------|--------|-----------|---------|
| 小文档（<10KB） | 1-5 | 1-3 | <50ms |
| 中文档（10KB-1MB） | 5-50 | 3-30 | <200ms |
| 大文档（1-10MB） | 50-500 | 30-300 | <500ms |

算法复杂度：Token 计数 O(n)（字符启发式算法，零 I/O），边界检测 O(n)，分块聚合 O(n)。总时间复杂度 O(n)，n = ParsedDocument 文本总字符数。

### 代码库调研关键发现（影响实现的关键约束）

以下发现来自对现有文档解析器和 Qdrant 向量层的深入调研，直接影响分块算法的设计：

1. **章节标题检测必须使用 `metadata["style"]`（非 DocLayNet labels）**
   - DocLayNet 的 `Section-header` label 仅用于版面检测排序，**检测后被丢弃**（`_apply_text_detections` 仅写入 `layout_confidence`）
   - Markdown 解析器在 `ParsedElement.metadata["style"]` 中保留 `"h1"`~`"h6"` 标题级别
   - Word 解析器保留 `"Heading 1"`~`"Heading 9"` 样式名
   - HTML 解析器保留 `"h1"`~`"h6"` 标签名
   - **分块器必须以 `metadata.get("style", "")` 作为章节边界判断依据**

2. **Markdown 解析器输出顺序问题**
   - Markdown 解析器**先输出所有标题、再所有段落、最后所有表格**（非文档原始顺序）
   - 分块器在全文档聚合时需意识到：标题与其所属章节段落可能分布在 pages[0].texts 列表的不同位置
   - **解决方案**：分块逻辑不依赖元素在 texts 列表中的位置推断段落归属；仅将标题作为独立硬边界

3. **PDF/HTML 解析粒度不足**
   - PDF 解析器：整页文本作为一个 `ParsedElement`（无段落分割）
   - HTML 解析器：body 全文作为一个 `ParsedElement`（无段落分割）
   - **分块器必须对这些格式做内部段落分割**（按 `\n\n` 双换行拆分 content 为多个"逻辑段落"后再聚合）
   - TXT/Markdown/DOCX/PPTX 解析器已按段落分割，无需额外处理

4. **DocLayNet bbox 阅读顺序不可靠**
   - 版面检测采用"顺序索引一一对应"（positional matching）而非空间 IoU 匹配
   - **分块器不依赖 bbox 坐标排序**；使用页面内 texts 列表的原始顺序（解析器已保证顺序）

5. **Qdrant Point ID 哈希问题**
   - Qdrant 的 `_normalize_point_id()` 会将 UUID 字符串哈希为整数
   - **原始 `chunk_id` 必须存入 Qdrant payload**（不能仅依赖 point ID）
   - 务必同时写入 `tenant_id`、`business_domain`、`content_hash` 到 payload（检索服务依赖这些字段过滤）

6. **Token 计数库可用性**
   - `tokenizers 0.22.2`（HuggingFace Rust tokenizer）已在 `poetry.lock` 的 main 组（via litellm 传递依赖）
   - 可加载 BGE-M3 的 XLM-RoBERTa tokenizer.json 做精确 token 计数
   - **MVP 方案**：使用字符启发式（零 I/O，P95<50ms 亚毫秒级），后续可用 `tokenizers` 做精确切换
   - `tiktoken` 也在 lock 中，但与 XLM-RoBERTa tokenizer 不匹配（OpenAI vs SentencePiece），不能用

7. **HTML 解析器使用 `\n` 单换行分隔符**
   - HTML 解析器使用 `body.get_text(separator="\n")`，内容以**单换行符** `\n` 分隔，而非 `\n\n` 双换行
   - **二次分割必须同时支持 `\n` 和 `\n\n`**：先尝试双换行分割，无匹配时再按单换行分句聚合

8. **`RAGIndexed` 事件缺少 `tenant_id` 字段**
   - `RAGIndexed` 事件（`workflow_events.py`）当前仅包含 `document_id`, `index_name`, `chunk_count`
   - **需在事件定义中新增 `tenant_id: str = ""` 字段**，与 `DocumentProcessed` 事件对齐

### 向后兼容性

| 场景 | 行为 | 影响 |
|------|------|------|
| `DocumentProcessed` 事件发布后 | `SemanticChunkingHandler` 异步触发分块 | 新增行为，向后兼容 |
| 现有文档（解析完成但未分块） | `metadata.chunks` 字段不存在或为空 | 不影响现有查询和检索 |
| `generate_embedding` 当前实现 | 不分块，全文档单向量 | 保持现有行为（仅 Story 3.1a 集成时修改） |
| `RAGIndexed` 事件 | `chunk_count` 从 0 变为实际数，新增 `tenant_id` 字段 | 新增字段值填充，语义增强 |
| `RAGIndexed` 事件 `tenant_id` | 新增 `tenant_id: str = ""` 字段（对齐 `DocumentProcessed`） | 向后兼容（默认空字符串） |

---

## 🤖 开发代理记录 Dev Agent Record

| 配置项 | 值 |
|--------|-----|
| **Model** | DeepSeek V4 Pro |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-08-02 |

### 完成清单

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事（Story 2-7）学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范
- [ ] 端口遵循 R1/R2/R3 设计规则（SemanticChunkerPort Protocol → SemanticChunkerImpl）
- [ ] AC → Task → Subtask 追溯矩阵完成

### 待创建文件清单

**Created:**
- `_bmad-output/implementation-artifacts/stories/2-8-semantic-chunking.md`

**To Be Created (Dev Story):**
- `src/domain/value_objects/semantic_chunk.py` — 值对象
- `src/domain/ports/semantic_chunker.py` — 端口
- `src/domain/exceptions/storage_exceptions.py` — MODIFY
- `src/domain/exceptions/_code_ranges.py` — MODIFY
- `src/domain/exceptions/__init__.py` — MODIFY
- `src/application/services/semantic_chunking_service.py` — 应用服务
- `src/application/event_handlers/semantic_chunking_handler.py` — 事件处理器
- `src/infrastructure/document_parsing/semantic_chunker_impl.py` — 基础设施实现
- `src/composition_root.py` — MODIFY
- `src/interfaces/api/exception_handlers.py` — MODIFY
- `tests/unit/domain/value_objects/test_semantic_chunk.py`
- `tests/unit/domain/exceptions/test_chunking_exceptions.py`
- `tests/unit/application/services/test_semantic_chunking_service.py`
- `tests/unit/application/event_handlers/test_semantic_chunking_handler.py`
- `tests/unit/infrastructure/document_parsing/test_semantic_chunker_impl.py`
- `tests/unit/architecture/test_arch_semantic_chunking.py`
- `tests/integration/test_semantic_chunking_integration.py`
- `tests/contracts/test_port_contract_semantic_chunker.py`
- `tests/acceptance/test_acceptance_semantic_chunking.feature`
- `tests/acceptance/test_acceptance_semantic_chunking.py`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.8 |
| **Story Key** | 2-8-semantic-chunking |
| **File** | `_bmad-output/implementation-artifacts/stories/2-8-semantic-chunking.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0（MVP），内部执行优先级 P1-8 |
| **覆盖 FR** | FR-DM-08 |
| **依赖** | Story 2.2a（基础格式解析）提供 ParsedDocument 输入 |
| **被依赖** | Epic 3 Story 3.1a（Dense 语义检索）—— 分块输出作为 Qdrant 索引单元 |
| **性能目标** | 分块延迟 P95<500ms，平均片段≈300 tokens，语义完整性≥90% |

### 完成总结

1. [ ] All tasks defined
2. [ ] All acceptance criteria specified
3. [ ] Architecture constraints extracted
4. [ ] Previous story learnings integrated
5. [ ] Sprint status synced to `ready-for-dev`

---

**故事版本/Story Version:** v3.1.0
**创建日期/Created:** 2026-08-02
**最后更新/Last Updated:** 2026-08-02
**更新说明/Description:**
- v1.0.0: 创建故事文件 — 语义分块（规则驱动的语义边界检测 + Token 预算聚合）
- v2.0.0: 审查修正版 — 修复 P0/P1 问题
- v3.0.0: 第二轮审查修订版 — 修复 17 个 P0 问题
- v3.1.0: R2 深度审查修正版 — 修复 R2 轮审查发现的 P0/P1 问题：修正 Gherkin 场景 3 引用 `Section-header` label 的严重误导；补充 `_parsed_table_from_dict` 方法（含 column_types/merged_cells/images 递归重建）；补充 `_create_chunk`/`_merge_chunks` 完整方法实现；修复 `_aggregate_segments` 单段超限时空分块创建缺陷；修复 `_merge_small_chunks` 控制流缺陷；修复 PAGE_BREAK 空文本追加问题；新增 AC-1 token_limit 边界类型定义；补充 `_CLASS_TO_SUBDOMAIN` 注册说明；澄清 `ChunkingError` 适用场景；标记 MD 段落归属偏差为 Known Limitation；验收场景从 9 扩展至 13 个；集成测试新增 RAGIndexed 事件验证和反序列化验证；架构验证新增 `__module__`/isinstance/注册检查
