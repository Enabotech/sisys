# Story 2-8: 语义分块（增强重构 v4）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。

> **🔧 重构说明：** 本版本为 v3（已完成）的增强重构，整合 Epic 2 回顾会议中确认的三项 P0 改进 + 一项 P2 改进 + 一项 P1 端口定义。
> 改动范围聚焦于 `SemanticChunk` 值对象、`ChunkingConfig`、`SemanticChunkingService` 和 `SemanticChunkerImpl`，
> 不新增端口注册（`SemanticBreakDetector` 仅定义 Protocol，不注册实现）。

---

## 📖 Story 描述

**As a** RAG 工程师,
**I want** 系统对文档执行 2026 年业界最佳级别的语义分块（上下文前缀 + 精准 Token 计数 + Child-Parent 双层索引 + 文档类型感知）,
**So that** 检索精度达到 87-90% Top-5 Recall，为 Epic 3 检索系统提供高质量分块输入。

### 业务价值

本 Story 是对已完成 v3 版本的增强重构，基于 Epic 2 回顾会议对标 **Anthropic Contextual Retrieval / Jina AI Late Chunking / Qdrant 1.15 Multivector / LlamaIndex DocAwareChunker** 的结论：

| 改进项 | 优先级 | 2026 行业对标 | 预期收益 |
|--------|--------|-------------|---------|
| 上下文前缀 (Contextual Chunk Header) | **P0** | Anthropic RAG 标准 (2026 演进: LLM 生成 → 结构拼接) | 检索精度 +15-25% |
| Token 精准计数 (BGE-M3 tokenizer) | **P0** | Jina AI Late Chunking 研究 | 消除 ~5% Recall 损失 |
| Child-Parent 双层索引 | **P0** | Qdrant 1.15 Multivector `group_by` | 检索精度 +20-30% |
| 文档类型感知分块 (ChunkingProfile) | **P2** | LlamaIndex DocAwareChunker | 特定场景精度提升 |
| SemanticBreakDetector 端口定义 | **P1** | 端口先行，实现推迟至 Epic 3 Story 3.7 | 架构就绪 |

**来源:** `_bmad-output/planning-artifacts/epics_v1.0.md` - Epic 2: 文档与数据管理，Story 2.8

**前置依赖:** Story 2-2a（基础格式解析 — 已完成 ✅）

**后续依赖:** Epic 3 Story 3.1a（Dense 语义检索）、Story 3.1b（BM25 稀疏检索）

**覆盖 FR:** FR-DM-08（语义分块）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 上下文前缀拼接

**Given** 文档解析完成，`ParsedElement.metadata["style"]` 包含标题层级信息
**When** 系统执行语义分块，构建每个 chunk 的 content
**Then** 每个 chunk 的 content 以结构化上下文前缀开头：
  - 文档标题（从 `ParsedDocument` 元数据获取）
  - → 章节路径（从元素 style 层级累积，如 `h1 > h2`）
  - → 本段内容
**And** 上下文前缀格式：`[文档: {title} → {section_path}]`
**And** 无标题信息时前缀仅包含文档标题，无文档标题时省略前缀
**And** 上下文前缀拼接到 `chunk.content` 开头，不影响 `chunk_index`/`page_range`/`boundary_type` 等其他字段
**And** `content_hash` 基于拼接后的完整 content 计算

**验证标准/Validation Criteria:**
- [ ] 有完整标题链的文档：输出 `[文档: 《2025年报》→ 第四章: 经营业绩 → Q3营收分析]`
- [ ] 仅文档标题、无章节标题：输出 `[文档: 《战略规划书》]`
- [ ] 无标题信息：不添加前缀（chunk.content 保持原始文本）
- [ ] 上下文前缀不计入 `token_count`（前缀是元数据，非检索内容）
- [ ] `content_hash` 基于带前缀的完整 content 计算

### AC-2: BGE-M3 精准 Token 计数

**Given** 文本内容需要估算 token 数
**When** 系统计算 `SemanticChunk.token_count` 和分块聚合决策
**Then** 使用 BGE-M3 的 XLM-RoBERTa SentencePiece tokenizer 做精确 token 计数
**And** `SemanticChunk.token_count` 存储精确 token 数（非估算值）
**And** 分块聚合决策（target/min/max 阈值）基于精确 token 数
**And** 向后兼容：`token_count` 字段类型保持 `int`

**验证标准/Validation Criteria:**
- [ ] `token_count_type` 字段标记为 `"bge-m3"`
- [ ] 中文文本 token 计数误差 < 5%（vs v3 字符启发式误差 ~20%）
- [ ] 英文文本 token 计数误差 < 3%
- [ ] tokenizer 不可用时降级为字符启发式（记录 WARNING 日志）
- [ ] 分块大小控制精度提升：target 300±50 → target 300±30

### AC-3: Child-Parent 双层索引

**Given** 文档分块完成
**When** 语义分块器生成 `SemanticChunk` 列表
**Then** 每个文档生成两类 chunk：
  - **子块（Child）**：~150 tokens，用于 Qdrant 向量索引（`index_level="child"`）
  - **父块（Parent）**：~600 tokens，不索引，子块命中时返回给 LLM（`index_level="parent"`）
**And** 子块通过 `parent_chunk_id` 字段关联父块
**And** 父块的 `parent_chunk_id` 为 `None`
**And** 子块和父块的 `chunk_index` 各自独立递增
**And** 向后兼容：单层模式（`child_chunk_size_tokens=None`）时所有 chunk 的 `parent_chunk_id=None`，行为与 v3 一致

**验证标准/Validation Criteria:**
- [ ] `ChunkingConfig` 新增 `child_chunk_size_tokens: int | None` 和 `parent_chunk_size_tokens: int | None`
- [ ] `SemanticChunk` 新增 `parent_chunk_id: UUID | None` 和 `index_level: Literal["child", "parent"]`
- [ ] `ChunkingConfig.to_dict()` 序列化新字段
- [ ] `SemanticChunk.to_dict()` 序列化新字段
- [ ] Child-Parent 模式下子块数量合理（文档 token 总量 / child_chunk_size_tokens）
- [ ] 单层模式（`child_chunk_size_tokens=None`）时所有 chunk 的 `parent_chunk_id=None`
- [ ] Qdrant payload 中 `parent_chunk_id` 可用于 `group_by` 查询（Epic 3 消费）

### AC-4: 文档类型感知分块策略

**Given** 不同业务域的文档需要不同的分块参数
**When** 分块服务选择分块策略
**Then** `ChunkingProfile` 枚举定义四种策略：
  - `GENERAL`：target=300, min=50, max=8192（默认，等价 v3 行为）
  - `FINANCIAL`：target=400, min=100, max=8192（财报表格密集，需更大上下文）
  - `CONTRACT`：target=250, min=80, max=8192（合同条款精读）
  - `RESEARCH`：target=350, min=60, max=8192（研报章节清晰）
**And** `ChunkingConfig.profile` 字段指定策略
**And** 应用层 `_BUSINESS_DOMAIN_PROFILE_MAP` 将 `business_domain` 映射到 `ChunkingProfile`
**And** 显式传入 `config` 时覆盖 profile 自动选择

**验证标准/Validation Criteria:**
- [ ] `ChunkingProfile` 枚举定义在 `src/domain/value_objects/semantic_chunk.py`（领域层零依赖）
- [ ] `ChunkingConfig.profile: ChunkingProfile = ChunkingProfile.GENERAL`
- [ ] `ChunkingConfig.to_dict()` 序列化 `profile` 字段
- [ ] 四种 profile 的 target/min/max 参数如上定义
- [ ] `ChunkingConfig.for_profile(profile)` 工厂方法返回对应配置

### AC-5: SemanticBreakDetector 端口定义（P1 端口先行）

**Given** 语义分块需要处理弱结构文档（会议纪要/访谈）
**When** Epic 3 Story 3.7 检索评估数据触发阈值（某文档类型 Top-5 Recall < 0.80）
**Then** `SemanticBreakDetector` Protocol 已定义，可直接实现
**And** 端口定义在 `src/domain/ports/semantic_break_detector.py`
**And** 接口签名为 `detect_breaks(segments: list[str], threshold: float = 0.65) -> list[int]`
**And** 端口标记 `status: deferred`，不注册到 composition_root
**And** 端口契约测试覆盖 Protocol 合规性

**验证标准/Validation Criteria:**
- [ ] Protocol 使用 `@runtime_checkable` 装饰器
- [ ] 领域层零外部依赖
- [ ] 端口契约测试 `tests/contracts/test_port_contract_semantic_break_detector.py` 验证 Protocol 合规
- [ ] 端口文件标注 `status: deferred — 实现触发条件: Epic 3 Story 3.7 某文档类型 Top-5 Recall < 0.80`
- [ ] 端口不注册到 `registry.py`（无实现时不注册）

### AC-6: 向后兼容性

**Given** v3 版本的 chunk 数据和下游消费者（`RAGIndexed` 事件、`document.metadata["chunks"]`）
**When** v4 增强重构部署
**Then** 所有现有测试保持通过（无回归）
**And** `SemanticChunk.to_dict()` 新增字段提供合理默认值（`parent_chunk_id`: null, `index_level`: "parent", `chunk_header`: ""）
**And** 单层模式下行为与 v3 完全一致
**And** `ChunkingConfig()` 无参构造行为与 v3 完全一致
**And** `RAGIndexed` 事件结构不变（仅 `chunk_count` 统计包含父子块总数）

**验证标准/Validation Criteria:**
- [ ] 全部现有测试通过（v3 回归验证）
- [ ] `ChunkingConfig().target_chunk_size_tokens == 300`
- [ ] 单层模式下 chunk 列表长度与 v3 一致
- [ ] `SemanticChunk.to_dict()` 输出可被 v3 消费者解析

---

## 🏗️ SDD+TDD 融合开发

### SDD 规范定义（Task 0 — 必选前置）

#### 领域事件 Schema (Domain Events)
- [ ] 复用 `RAGIndexed` 事件（v3 已定义），不新增事件
- [ ] 复用 `DocumentProcessed` 事件触发分块流程

#### 数据模型 (Data Models)

**ChunkBoundaryType 枚举（不变）：**

```python
class ChunkBoundaryType(str, Enum):
    PARAGRAPH = "paragraph"
    SECTION_HEADER = "section_header"
    TABLE = "table"
    PAGE_BREAK = "page_break"
    TOKEN_LIMIT = "token_limit"
```

**ChunkingProfile 枚举（新增）：**

```python
class ChunkingProfile(str, Enum):
    """分块策略配置档案。

    Values:
        GENERAL: 通用文档（默认，等价 v3 行为）
        FINANCIAL: 财报/财务报表（表格密集，需更大上下文）
        CONTRACT: 合同/法律文档（条款精读）
        RESEARCH: 研报/白皮书（章节清晰）
    """
    GENERAL = "general"
    FINANCIAL = "financial"
    CONTRACT = "contract"
    RESEARCH = "research"
```

**ChunkingConfig 值对象（扩展）：**

```python
@dataclass(frozen=True)
class ChunkingConfig:
    """分块配置值对象

    Attributes:
        profile: 分块策略配置档案
        target_chunk_size_tokens: 目标分块大小（父块）
        min_chunk_size_tokens: 最小分块阈值
        max_chunk_size_tokens: 硬限制最大 token 数
        child_chunk_size_tokens: 子块目标大小（None=单层模式）
        parent_chunk_size_tokens: 父块目标大小（None=单层模式）
        token_count_type: Token 计数方式
    """
    profile: ChunkingProfile = ChunkingProfile.GENERAL
    target_chunk_size_tokens: int = 300
    min_chunk_size_tokens: int = 50
    max_chunk_size_tokens: int = 8192
    child_chunk_size_tokens: int | None = None
    parent_chunk_size_tokens: int | None = None
    token_count_type: str = "bge-m3"  # "bge-m3" | "heuristic"

    @staticmethod
    def for_profile(profile: ChunkingProfile) -> ChunkingConfig:
        """根据 profile 创建推荐配置（领域层工厂方法）。

        注意：此方法接收 ChunkingProfile 枚举值，
        business_domain → ChunkingProfile 的映射在应用层完成。
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "profile": self.profile.value,
            "target_chunk_size_tokens": self.target_chunk_size_tokens,
            "min_chunk_size_tokens": self.min_chunk_size_tokens,
            "max_chunk_size_tokens": self.max_chunk_size_tokens,
            "child_chunk_size_tokens": self.child_chunk_size_tokens,
            "parent_chunk_size_tokens": self.parent_chunk_size_tokens,
            "token_count_type": self.token_count_type,
        }
```

**IndexLevel 枚举（新增）：**

```python
class IndexLevel(str, Enum):
    """分块索引层级"""
    CHILD = "child"    # Qdrant 向量索引
    PARENT = "parent"  # LLM 上下文返回
```

**SemanticChunk 值对象（扩展）：**

```python
@dataclass(frozen=True)
class SemanticChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str                    # 带上下文前缀的完整内容
    chunk_index: int
    boundary_type: ChunkBoundaryType
    token_count: int                # 精确 token 数（bge-m3）
    page_start: int
    page_end: int
    content_hash: str
    metadata: dict[str, Any]
    # v4 新增字段
    parent_chunk_id: uuid.UUID | None = None   # Child-Parent 关联
    index_level: IndexLevel = IndexLevel.PARENT # 索引层级
    chunk_header: str = ""                       # 上下文前缀
```

#### 统一端口定义注册与管理 (Port Contract)

**端口契约清单：**

| 端口名称 | 接口 | 实现 | Lifetime | Version | Owner | 变动 |
|---------|------|------|----------|---------|-------|------|
| `semantic_chunker` | `SemanticChunkerPort` | `SemanticChunkerImpl` | SCOPED | v1.0.0→v1.1.0 | epic-2 | 版本升级 |
| `semantic_break_detector` | `SemanticBreakDetector` | — (deferred) | — | v1.0.0 | epic-2 | **新增端口（不注册）** |

**新增端口 `semantic_break_detector`：**

- [ ] 端口契约文件 `src/domain/ports/semantic_break_detector.py`
  - `@runtime_checkable` + `Protocol`
  - `detect_breaks(segments: list[str], threshold: float = 0.65) -> list[int]`
  - 标记 `status: deferred` — 实现触发条件: Epic 3 Story 3.7 检索评估某文档类型 Top-5 Recall < 0.80
- [ ] 端口契约测试：`tests/contracts/test_port_contract_semantic_break_detector.py`
- [ ] 不注册到 `registry.py`（无实现时不注册）
- [ ] 不注册到 `composition_root.py`

**端口签名（SemanticChunkerPort）— v4 扩展：**
- `chunk(parsed_doc, config=None, metadata=None) -> list[SemanticChunk]` — 新增 `metadata` 参数传递文档级上下文
- 版本从 v1.0.0 升级至 v1.1.0（行为增强：上下文前缀 + bge-m3 tokenizer + Child-Parent）
- 契约测试 `test_port_contract_semantic_chunker.py:62` 参数断言从 `["self", "parsed_doc", "config"]` 更新为 `["self", "parsed_doc", "config", "metadata"]`

**`metadata` 参数设计（关键架构决策）：**
- 用途：传递 `ParsedDocument` 中不存在的文档级元数据
- `SemanticChunkingService.chunk_document()` 从 `Document` 实体提取 `{"doc_title": doc.filename, "business_domain": doc.metadata.get("business_domain", "")}`
- 分块器内部通过 `_build_chunk_header()` 读取 `doc_metadata["doc_title"]` 构建上下文前缀
- 向后兼容：`metadata=None` 时上下文前缀退化为仅章节路径（无文档标题）

#### 六边形架构约束
- 领域层零外部依赖
- `ChunkingProfile` 枚举在领域层定义
- `_BUSINESS_DOMAIN_PROFILE_MAP` 在应用层定义
- `SemanticBreakDetector` Protocol 在领域层定义
- bge-m3 tokenizer 通过函数注入进入应用层，不进入领域层

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 扩展 `tests/acceptance/test_acceptance_semantic_chunking.feature`
- [ ] 新增场景覆盖：上下文前缀、Child-Parent 模式、ChunkingProfile、向后兼容
- [ ] BDD 步骤函数使用 `event_loop.run_until_complete()`

---

### TDD 循环约束

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 编写失败测试 | `pytest` 运行失败 |
| **🟢 绿** | 编写最小实现 | `pytest` 通过 |
| **🔄 重构** | 优化代码 | `ruff check` + `mypy` + `pytest` 通过 |

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | SemanticChunk 扩展 | 新字段/parent_chunk_id/to_dict | `test_semantic_chunk.py` (扩展) | Task 1 |
| TDD 单元测试 | ChunkingProfile + Config | 枚举值/for_profile/to_dict | `test_semantic_chunk.py` (扩展) | Task 1 |
| TDD 单元测试 | BGE-M3 Token 计数 | 精准度/中英文/降级 | `test_token_counter.py` (新增) | Task 2 |
| TDD 单元测试 | 上下文前缀 | 标题链累积/边界 case | `test_semantic_chunker_impl.py` (扩展) | Task 3 |
| TDD 单元测试 | Child-Parent 分块 | 父子关联/size/数量 | `test_semantic_chunker_impl.py` (扩展) | Task 4 |
| TDD 单元测试 | 文档类型感知 | profile 路由/覆盖 | `test_semantic_chunking_service.py` (扩展) | Task 5 |
| TDD 单元测试 | SemanticBreakDetector | Protocol 合规 | `test_port_contract_semantic_break_detector.py` (新增) | Task 6 |
| TDD 单元测试 | 向后兼容 | v3 输出等价 | `test_semantic_chunker_impl.py` (扩展) | Task 7 |
| 契约测试 | SemanticChunker Port | 版本 v1.1.0 | `test_port_contract_semantic_chunker.py` (扩展) | Task 0 |
| 契约测试 | SemanticBreakDetector | Protocol 合规 | `test_port_contract_semantic_break_detector.py` (新增) | Task 6 |
| 架构验证 | 六边形架构 | 依赖方向/零依赖 | `test_arch_semantic_chunking.py` (扩展) | Task 8 |
| 集成测试 | 完整分块流程 | parse→chunk→persist→event | `test_integration_semantic_chunking.py` (扩展) | Task 9 |
| 验收测试 | Gherkin 场景 | 业务价值验收 | `test_acceptance_semantic_chunking.feature` (扩展) | Task 0/10 |

---

### 测试要求与质量门禁

#### 覆盖率要求
- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断**
- [ ] **领域层覆盖率 ≥90%**
- [ ] **应用层覆盖率 ≥85%**
- [ ] **基础设施层覆盖率 ≥75%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**
- [ ] **MyPy 类型检查通过**
- [ ] **无 P0/P1 级别问题**
- [ ] **预提交 Hooks 通过**

#### 回归验证
- [ ] v3 全部现有测试通过
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 描述 | 关联 Task | 测试文件 |
|----|------|-----------|----------|
| AC-1 | 上下文前缀 | Task 1 + Task 3 | `test_semantic_chunk.py` + `test_semantic_chunker_impl.py` |
| AC-2 | BGE-M3 Token | Task 2 | `test_token_counter.py` |
| AC-3 | Child-Parent | Task 1 + Task 4 | `test_semantic_chunk.py` + `test_semantic_chunker_impl.py` |
| AC-4 | ChunkingProfile | Task 1 + Task 5 | `test_semantic_chunk.py` + `test_semantic_chunking_service.py` |
| AC-5 | SemanticBreakDetector | Task 6 | `test_port_contract_semantic_break_detector.py` |
| AC-6 | 向后兼容 | Task 7 + Task 8 + Task 9 | 全部测试 |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-6

> **目的：** 明确 Schema、端口契约和验收标准，确认 v3 代码基线。

- [ ] Subtask 0.1: 验证 v3 代码基线（`semantic_chunk.py` / `semantic_chunker.py` / `semantic_chunker_impl.py` / `semantic_chunking_service.py` 当前状态）
- [ ] Subtask 0.2: 定义 `ChunkingProfile` 枚举 + `IndexLevel` 枚举（`semantic_chunk.py` 扩展）
- [ ] Subtask 0.3: 定义 `ChunkingConfig` 扩展字段（profile, child/parent_chunk_size_tokens, token_count_type）
- [ ] Subtask 0.4: 定义 `SemanticChunk` 扩展字段（parent_chunk_id, index_level, chunk_header）
- [ ] Subtask 0.5: 定义 `SemanticBreakDetector` Protocol（`semantic_break_detector.py` 新建）
- [ ] Subtask 0.6: 更新端口契约测试 `test_port_contract_semantic_chunker.py`
  - `test_version_is_v1_0_0`: 期望版本 `"v1.0.0"` → `"v1.1.0"`
  - `test_chunk_method_exists`: 参数断言 `["self", "parsed_doc", "config"]` → `["self", "parsed_doc", "config", "metadata"]`
  - `test_lifetime_is_singleton`: 确认 SINGLETON 不变
- [ ] Subtask 0.7: 编写 Gherkin 验收测试扩展场景
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为）

---

### Task 1: 值对象扩展（ChunkingProfile + ChunkingConfig + SemanticChunk）

**关联 AC:** AC-1, AC-3, AC-4, AC-6

#### TDD 循环 A：ChunkingProfile + IndexLevel 枚举

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_semantic_chunk.py`（4 个枚举值/str 继承/value 访问/IndexLevel） |
| 🟢 绿 | 实现 `ChunkingProfile` + `IndexLevel` 枚举 |
| 🔄 重构 | `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写枚举测试
- [ ] Subtask 1.2: 🟢 绿 — 实现枚举最小代码
- [ ] Subtask 1.3: 🔄 重构

#### TDD 循环 B：ChunkingConfig 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_semantic_chunk.py`（新字段默认值/for_profile 工厂/to_dict 序列化/向后兼容） |
| 🟢 绿 | 实现 `ChunkingConfig` 新字段 + `for_profile()` |
| 🔄 重构 | `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 ChunkingConfig 扩展测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 ChunkingConfig 扩展
- [ ] Subtask 1.6: 🔄 重构

#### TDD 循环 C：SemanticChunk 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_semantic_chunk.py`（新字段/parent_chunk_id/to_dict/chunk_header/向后兼容） |
| 🟢 绿 | 实现 `SemanticChunk` 新字段 |
| 🔄 重构 | 更新 `__all__` 导出 |

- [ ] Subtask 1.7: 🔴 红 — 编写 SemanticChunk 扩展测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 SemanticChunk 扩展
- [ ] Subtask 1.9: 🔄 重构

**完成标准/Definition of Done:**
- [ ] `ChunkingProfile`/`IndexLevel`/`ChunkingConfig`/`SemanticChunk` 全部扩展完成
- [ ] 领域层覆盖率 ≥90%

---

### Task 2: BGE-M3 精准 Token 计数

**关联 AC:** AC-2

> **说明：** `tokenizers 0.22.2` 已在 `poetry.lock` main 组（via litellm 传递依赖）。
> 将字符启发式 `estimate_tokens()` 替换为 bge-m3 tokenizer 精确计数。

#### TDD 循环 A：BGE-M3 Token 计数器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_token_counter.py`（中文精度/英文精度/数字/混合/tokenizer 不可用降级） |
| 🟢 绿 | 实现 `_count_tokens_bge_m3()` |
| 🔄 重构 | 提取降级逻辑；保留 `estimate_tokens()` 作为 fallback |

- [ ] Subtask 2.1: 🔴 红 — 编写 token 计数测试
  - 中文文本：`"战略规划需要系统性思维"` → 精确 token 数 vs 字符估算
  - 英文文本：`"Strategic planning requires systematic thinking"` → 精确 token 数 vs 字符估算
  - 中英混合、数字、特殊字符
  - tokenizer 不可用时降级为 heuristic + WARNING 日志
- [ ] Subtask 2.2: 🟢 绿 — 实现 bge-m3 tokenizer 加载
  - `tokenizers.Tokenizer.from_file("bge-m3-tokenizer.json")` 或使用 `flagembedding` 内置
  - `SemanticChunkerImpl` 构造函数注入 `token_counter: Callable[[str], int] | None = None`
  - 默认使用 bge-m3，降级为 `estimate_tokens`
- [ ] Subtask 2.3: 🔄 重构 — 提取降级逻辑；保持 `estimate_tokens()` 存在

**完成标准/Definition of Done:**
- [ ] BGE-M3 token 计数精度 < 5% 误差
- [ ] tokenizer 不可用时优雅降级
- [ ] `SemanticChunk.token_count` 为精确值

---

### Task 3: 上下文前缀实现

**关联 AC:** AC-1

> **说明：** 在 `SemanticChunkerImpl._create_chunk()` 中拼接 `[文档: {title} → {section_path}]` 前缀。
> 使用 v3 代码库调研已确认的 `metadata["style"]` 标题层级数据。

#### TDD 循环 A：上下文前缀构建

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_semantic_chunker_impl.py`（完整标题链/仅文档标题/无标题/前缀不影响其他字段） |
| 🟢 绿 | 实现 `_build_chunk_header()` + 在 `_create_chunk()` 中调用 |
| 🔄 重构 | 优化标题链累积逻辑 |

- [ ] Subtask 3.1: 🔴 红 — 编写上下文前缀测试
  - 有完整标题链：`h1="第四章"` → `h2="Q3营收"` → `[文档: 《年报》→ 第四章 → Q3营收]`
  - 仅 `h1`：`[文档: 《年报》→ 第四章]`
  - 无标题元素：`title=None` → 不添加前缀
  - 前缀不计入 `token_count`
  - `content_hash` 基于带前缀的完整 content
- [ ] Subtask 3.2: 🟢 绿 — 实现 `_build_chunk_header()` + `chunk_document()` metadata 传递
  - 在 `SemanticChunkingService.chunk_document()` 中构建 metadata:
    ```python
    chunk_metadata = {
        "doc_title": doc.filename,
        "business_domain": doc.metadata.get("business_domain", ""),
    }
    chunks = await self._semantic_chunker.chunk(parsed_doc, config=config, metadata=chunk_metadata)
    ```
  - 分块器内部 `_build_chunk_header(parts, doc_metadata)` 从 `doc_metadata["doc_title"]` 读取标题
  - 格式：`[文档: {title}]` / `[文档: {title} → h1 → h2]` / `[文档: {title} → 第N节]`
  - 标题缺失时退化为仅章节路径
  - **注意：** `ParsedDocument` 无 `title` 字段（v3 设计），文档标题通过 `metadata` dict 传入是唯一可行路径
- [ ] Subtask 3.3: 🔄 重构

**完成标准/Definition of Done:**
- [ ] 上下文前缀拼接正确
- [ ] 不影响其他字段

---

### Task 4: Child-Parent 双层分块

**关联 AC:** AC-3

> **说明：** 当 `ChunkingConfig.child_chunk_size_tokens` 非 None 时，触发双层分块模式。
> 算法：先用父块大小聚合段落 → 每个父块内用子块大小切分 → 子块关联父块。

#### TDD 循环 A：Child-Parent 分块逻辑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_semantic_chunker_impl.py`（父子关联/size 控制/parent_chunk_id/单层模式兼容） |
| 🟢 绿 | 实现 `_split_child_parent()` + 在 `chunk()` 中条件触发 |
| 🔄 重构 | 优化切分逻辑 |

- [ ] Subtask 4.1: 🔴 红 — 编写 Child-Parent 测试
  - 双层模式：子块 ~150 tokens，父块 ~600 tokens
  - `parent_chunk_id` 正确关联
  - 子块 `index_level="child"`，父块 `index_level="parent"`
  - chunk_index 独立递增
  - 单层模式（`child_chunk_size_tokens=None`）：行为与 v3 一致
- [ ] Subtask 4.2: 🟢 绿 — 实现 `_split_child_parent()`
  - 在 `_aggregate_segments()` 后增加父子切分步骤
  - 子块创建逻辑：按 `child_chunk_size_tokens` 在父块文本中切分
  - 子块优先在语义边界（句号、换行）处切分
- [ ] Subtask 4.3: 🔄 重构

**完成标准/Definition of Done:**
- [ ] Child-Parent 模式可配置开启
- [ ] 单层模式行为与 v3 一致

---

### Task 5: 文档类型感知分块集成

**关联 AC:** AC-4

#### TDD 循环 A：ChunkingProfile 路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_semantic_chunking_service.py`（profile 路由/FINANCIAL 参数/CONTRACT 参数/explicit config 覆盖） |
| 🟢 绿 | 实现 `_BUSINESS_DOMAIN_PROFILE_MAP` + 服务集成 |
| 🔄 重构 | 优化映射逻辑 |

- [ ] Subtask 5.1: 🔴 红 — 编写 profile 路由测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 `_resolve_profile_from_domain()` + `chunk_document()` 集成
  ```python
  # 应用层 — business_domain → ChunkingProfile 映射
  _BUSINESS_DOMAIN_PROFILE_MAP: dict[str, ChunkingProfile] = {
      "finance": ChunkingProfile.FINANCIAL,
      "legal": ChunkingProfile.CONTRACT,
      "research": ChunkingProfile.RESEARCH,
  }

  def _resolve_profile_from_domain(business_domain: str) -> ChunkingProfile:
      """将业务域字符串映射到分块策略配置档案。

      应用层职责：business_domain（Document 实体中的字符串）→ ChunkingProfile 枚举。
      领域层 ChunkingConfig.for_profile() 接收 ChunkingProfile 枚举值（非字符串）。
      """
      return _BUSINESS_DOMAIN_PROFILE_MAP.get(
          business_domain, ChunkingProfile.GENERAL
      )
  ```
  - 在 `chunk_document()` 中：无显式 config 时从 `doc.metadata["business_domain"]` 自动选择 profile
  - 显式传入 `config` 参数时覆盖自动选择（优先级：显式 config > profile 自动选择 > 默认 GENERAL）
- [ ] Subtask 5.3: 🔄 重构

**完成标准/Definition of Done:**
- [ ] 四种 profile 的路由映射正确

---

### Task 6: SemanticBreakDetector 端口定义（P1 端口先行）

**关联 AC:** AC-5

> **说明：** 仅定义 Protocol，不实现。端口文件标注 `status: deferred`。

#### TDD 循环 A：SemanticBreakDetector Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_port_contract_semantic_break_detector.py`（Protocol 合规/签名检查） |
| 🟢 绿 | 实现 `src/domain/ports/semantic_break_detector.py`（Protocol 定义） |
| 🔄 重构 | `ruff` + `mypy` |

- [ ] Subtask 6.1: 🔴 红 — 编写 Protocol 合规测试
- [ ] Subtask 6.2: 🟢 绿 — 实现 `SemanticBreakDetector` Protocol
  ```python
  @runtime_checkable
  class SemanticBreakDetector(Protocol):
      """语义断裂检测端口。

      status: deferred — 实现触发条件:
        Epic 3 Story 3.7 检索相关性评估中，任一文档类型 Top-5 Recall < 0.80
      """
      async def detect_breaks(
          self,
          segments: list[str],
          threshold: float = 0.65,
      ) -> list[int]:
          """检测语义断裂点。Returns: 断裂点索引列表"""
          ...

  __all__ = ["SemanticBreakDetector"]
  ```
- [ ] Subtask 6.3: 🔄 重构

**完成标准/Definition of Done:**
- [ ] Protocol 定义在领域层（零外部依赖）
- [ ] 端口契约测试通过
- [ ] 标注 `status: deferred`
- [ ] 不注册到 registry/composition_root

---

### Task 7: 向后兼容性验证

**关联 AC:** AC-6

> **说明：** 验证所有 v4 改动不影响 v3 行为。

- [ ] Subtask 7.1: 运行 v3 全部现有测试，确认通过
- [ ] Subtask 7.2: `ChunkingConfig()` 无参构造行为 = v3
- [ ] Subtask 7.3: 单层模式下 chunk 输出与 v3 等价（除 token_count 更精确 + chunk_header 为空）
- [ ] Subtask 7.4: `SemanticChunk.to_dict()` 输出可被 v3 消费者解析

**完成标准/Definition of Done:**
- [ ] v3 全量测试通过
- [ ] 无行为回归

---

### Task 8: SDD 架构约束验证

**关联 AC:** AC-1 ~ AC-6

- [ ] Subtask 8.1: 扩展 `test_arch_semantic_chunking.py`
  - 验证 `ChunkingProfile`/`IndexLevel` 在 domain 层
  - 验证 `SemanticBreakDetector` 在 domain 层，零外部依赖
  - 验证 bge-m3 tokenizer 不在 domain 层
  - 验证 `_BUSINESS_DOMAIN_PROFILE_MAP` 在 application 层
  - 验证 `SemanticChunk` 新增字段无外部依赖

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过

---

### Task 9: 集成测试

**关联 AC:** AC-1 ~ AC-6

- [ ] Subtask 9.1: 完整分块流程（parse → chunk → persist → RAGIndexed 事件）
- [ ] Subtask 9.2: Child-Parent 模式端到端验证
- [ ] Subtask 9.3: ChunkingProfile 路由集成验证
- [ ] Subtask 9.4: 上下文前缀在持久化数据中的正确性
- [ ] Subtask 9.5: 向后兼容验证（v3 格式数据）

**完成标准/Definition of Done:**
- [ ] 所有集成测试通过
- [ ] 集成测试覆盖率 ≥70%

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-6

- [ ] Subtask 10.1: `src` 完成清单逐项确认
- [ ] Subtask 10.2: `tests` 完成清单逐项确认
- [ ] Subtask 10.3: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 关键架构决策

| 决策 | 方案 | 理由 |
|------|------|------|
| **上下文前缀** | 结构拼接（非 LLM 生成） | 2026 Anthropic 演进: 结构拼接等价于 LLM 生成，零成本 |
| **Token 计数** | BGE-M3 XLM-RoBERTa tokenizer | `tokenizers` 已在 lock；字符启发式误差 20% → 精准误差 <5% |
| **Child-Parent** | `ChunkingConfig` 配置切换；子块索引 + 父块返回 | Qdrant 1.15 `group_by` 原生支持；单层模式向后兼容 |
| **文档类型感知** | `ChunkingProfile` 枚举 + `_BUSINESS_DOMAIN_PROFILE_MAP` | 领域层零依赖；应用层策略路由 |
| **SemanticBreakDetector** | 端口先行，实现延后 | Epic 3 Story 3.7 数据触发；避免提前过度设计 |

### 改动范围（精确）

```
src/domain/value_objects/semantic_chunk.py  ← 核心扩展
  + ChunkingProfile(Enum)
  + IndexLevel(Enum)
  ChunkingConfig: +profile, +child_chunk_size_tokens, +parent_chunk_size_tokens, +token_count_type
  SemanticChunk: +parent_chunk_id, +index_level, +chunk_header

src/domain/ports/semantic_break_detector.py  ← 新建（P1 端口先行）
  + SemanticBreakDetector Protocol (status: deferred)

src/infrastructure/document_parsing/semantic_chunker_impl.py  ← 核心改动
  + _count_tokens_bge_m3()         # Token 精准化
  + _build_chunk_header()          # 上下文前缀
  + _split_child_parent()          # Child-Parent 切分
  ~ _create_chunk()                # 集成前缀 + 新字段
  ~ _aggregate_segments()          # 精确 token 替代估算

src/application/services/semantic_chunking_service.py  ← 应用层扩展
  + _BUSINESS_DOMAIN_PROFILE_MAP
  ~ chunk_document()               # profile 自动选择
  ~ parsed_document_from_dict()    # 不变
```

### 向后兼容性矩阵

> **类型不一致说明：** `ParsedDocument.document_id` 为 `str` 类型，`SemanticChunk.document_id` 为 `uuid.UUID` 类型。
> `SemanticChunkerImpl._create_chunk()` 通过 `uuid.UUID(document_id)` 进行转换，转换失败时抛出 `ChunkingError`。
> v4 不改变此行为（改 `ParsedDocument.document_id` 类型会影响 Story 2-2a/2-2b 的所有解析器）。

| v3 行为 | v4 行为 | 兼容 |
|---------|---------|------|
| `ChunkingConfig()` → target=300 | 完全一致（GENERAL profile 默认 target=300） | ✅ |
| `SemanticChunk.to_dict()` → 10 个 key | 新增 3 个 key（parent_chunk_id: null, index_level: "parent", chunk_header: ""） | ✅ |
| 单层分块（无 Child-Parent） | `child_chunk_size_tokens=None` 时行为一致 | ✅ |
| `estimate_tokens()` | 保留作为 fallback；主路径用 bge-m3 | ✅ |
| `RAGIndexed` 事件 | 不变 | ✅ |
| `document.metadata["chunks"]` | 结构兼容（新增字段有默认值） | ✅ |

### 前一个故事学习经验

**来源:** [Story 2-7 元数据校验](./2-7-metadata-validation.md) + v3 实现经验

**关键学习:**
1. [MUST] frozen dataclass 扩展必须提供默认值 — 所有新字段使用 `field(default=...)`
2. [MUST] `to_dict()` 新增字段向后兼容 — 调用方忽略未知 key
3. [MUST] BGE-M3 tokenizer 降级策略 — 不可用时回退 `estimate_tokens()` + WARNING 日志
4. [SHOULD] 值对象扩展走 `test_semantic_chunk.py` 集中扩展 — 不新建测试文件
5. [REF] 端口先行模式 — `SemanticBreakDetector` 参考项目 `semantic_router_protocol.py` 的 deferred 标注风格

---

## 🤖 开发代理记录 Dev Agent Record

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-08-04 |

### 调试日志引用

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **回顾会议记录** | Epic 2 Retrospective 2026-08-04 |
| **v3 Story 文件** | `_bmad-output/implementation-artifacts/stories/2-8-semantic-chunking.md` |
| **v3 实现** | `src/infrastructure/document_parsing/semantic_chunker_impl.py` |
| **v3 值对象** | `src/domain/value_objects/semantic_chunk.py` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单

- [x] 回顾会议 P0 改进确认（上下文前缀 + BGE-M3 tokenizer + Child-Parent）
- [x] 回顾会议 P2 改进确认（ChunkingProfile）
- [x] 回顾会议 P1 端口先行确认（SemanticBreakDetector）
- [x] Winston 架构边界确认（6 文件修改 + 2 新文件）
- [x] 2026 行业对标分析整合

### 文件清单

**修改的文件/Modified:**
- `src/domain/value_objects/semantic_chunk.py` — ChunkingProfile + IndexLevel + ChunkingConfig 扩展 + SemanticChunk 扩展
- `src/infrastructure/document_parsing/semantic_chunker_impl.py` — bge-m3 tokenizer + 上下文前缀 + Child-Parent
- `src/application/services/semantic_chunking_service.py` — ChunkingProfile 路由
- `tests/unit/domain/value_objects/test_semantic_chunk.py` — 扩展
- `tests/unit/infrastructure/document_parsing/test_semantic_chunker_impl.py` — 扩展
- `tests/unit/application/services/test_semantic_chunking_service.py` — 扩展
- `tests/contracts/test_port_contract_semantic_chunker.py` — 版本 v1.1.0
- `tests/unit/architecture/test_arch_semantic_chunking.py` — 扩展
- `tests/integration/test_integration_semantic_chunking.py` — 扩展
- `tests/acceptance/test_acceptance_semantic_chunking.feature` — 扩展
- `tests/acceptance/test_acceptance_semantic_chunking.py` — 扩展

**新建的文件/Created:**
- `src/domain/ports/semantic_break_detector.py` — SemanticBreakDetector Protocol（deferred）
- `tests/contracts/test_port_contract_semantic_break_detector.py` — 端口契约测试
- `tests/unit/infrastructure/document_parsing/test_token_counter.py` — BGE-M3 token 计数测试

**不变的文件/Unchanged:**
- `src/domain/ports/semantic_chunker.py` — 接口签名不变
- `src/domain/ports/registry.py` — 不注册 SemanticBreakDetector
- `src/composition_root.py` — 不注册 SemanticBreakDetector
- `src/application/event_handlers/semantic_chunking_handler.py` — 不变
- `src/domain/events/workflow_events.py` — RAGIndexed 不变

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.8 |
| **Story Key** | 2-8-semantic-chunking |
| **File** | `_bmad-output/implementation-artifacts/stories/2-8-semantic-chunking.md` |
| **Status** | `done` (v3) → `ready-for-dev` (v4 增强重构) |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0-8（MVP） |
| **覆盖 FR** | FR-DM-08 |
| **v4 新增覆盖** | 上下文前缀 / BGE-M3 Token / Child-Parent / ChunkingProfile / SemanticBreakDetector 端口 |

### 完成总结

1. [x] SDD 规范定义完成（值对象扩展 + 新端口 Protocol）
2. [x] AC-1~AC-6 全部定义
3. [x] 架构约束分析完成
4. [x] 2026 行业对标整合
5. [x] 回顾会议决策落地
6. [x] 向后兼容性保证

---

### 🔧 文档审查修复 Docs Review Fixes

> 第1轮审查修订（2026-08-04）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | `SemanticChunkerPort` 协议与实现签名不一致（协议 2 参数，实现 3 参数含 `metadata`） | P0 | 协议签名扩展为 `chunk(parsed_doc, config=None, metadata=None)`，契约测试参数断言同步更新 |
| 2 | `ParsedDocument` 无 `title` 字段，上下文前缀数据源不明确 | P0 | 通过 `metadata` 参数传递 `doc_title`（从 `Document.filename` 提取），`_build_chunk_header()` 从 `doc_metadata["doc_title"]` 读取 |
| 3 | `ChunkingConfig.to_dict()` 缺少 `token_count_type`/`profile`/child/parent 新字段序列化 | P0 | 补充 `to_dict()` 完整序列化（profile.value + 新字段） |
| 4 | `_BUSINESS_DOMAIN_PROFILE_MAP` 职责边界模糊（领域层 vs 应用层） | P0 | 明确分离：领域层 `ChunkingConfig.for_profile(profile: ChunkingProfile)` + 应用层 `_resolve_profile_from_domain(business_domain: str) -> ChunkingProfile` |
| 5 | `ChunkingConfig.to_dict()` 缺少 `token_count_type` 字段序列化 | P0 | 补充 `to_dict()` 序列化 `profile`, `child_chunk_size_tokens`, `parent_chunk_size_tokens`, `token_count_type` |
| 6 | `SemanticBreakDetector` 端口定义缺少 `__all__` 导出 | P0 | 补充 `__all__ = ["SemanticBreakDetector"]` |
| 7 | `_merge_chunks()` token_count 简单相加需要记录设计决策 | P0 | 在 Child-Parent 分块逻辑和 `_merge_chunks()` 重构中使用 bge-m3 tokenizer 重新计数 |

> 第2轮审查修订（2026-08-04）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 8 | 契约测试 `chunk` 方法参数断言未更新（`["self", "parsed_doc", "config"]` 缺少 `metadata`） | P0 | Subtask 0.6 明确更新契约测试的三项改动（版本 v1.1.0 + 参数断言 + 生命周期） |
| 9 | `SemanticChunkingService.chunk_document()` 调用时不传 `metadata`（v3 中所有 chunk.metadata 始终为空） | P0 | `chunk_document()` 中构建 `metadata={"doc_title": doc.filename, "business_domain": ...}` 传给 `chunk()` |
| 10 | `ParsedDocument.document_id` 为 `str` 但 `SemanticChunk.document_id` 为 `UUID`（类型不一致未记录） | P1 | Dev Notes 向后兼容性矩阵上方补充类型不一致说明 |
| 11 | `page_range` vs `page_start`/`page_end` 术语不一致 | P2 | 已在 AC 描述中统一使用 `page_start`/`page_end`（v3 即如此），AC-3 的 `page_range` 作为概念性描述保持不变 |

---

### 下一步 Next Steps

- [ ] 运行 `dev-story` 开始 v4 增强重构
- [ ] 运行 `code-review` 进行代码审查
- [ ] Epic 3 Story 3.7 检索评估数据达标后触发 `SemanticBreakDetector` 实现

---

**故事版本/Story Version:** v4.1.0

**故事版本/Story Version:** v4.2.0
**创建日期/Created:** 2026-08-02 (v3)
**最后更新/Last Updated:** 2026-08-04 (v4.2.0 — Round 2 审查修订)
**更新说明/Description:**
- v4.2.0: Round 2 审查修订 — 修复 3 项 P0 + 1 项 P1（契约测试参数断言、metadata 传递、类型不一致文档化）
- v4.1.0: Round 1 审查修订 — 修复 7 项 P0 问题（协议签名不一致、文档标题数据源、to_dict 序列化、profile 路由职责分离、__all__ 导出、merge token 计数）
- v4.0.0: 增强重构 — 整合三项 P0（上下文前缀 + BGE-M3 Tokenizer + Child-Parent）+ 一项 P2（ChunkingProfile）+ 一项 P1（SemanticBreakDetector 端口定义），对标 Anthropic/Jina AI/Qdrant 1.15/LlamaIndex 2026 业界最佳实践
- v3.1.0: R2 深度审查修正版 — 修复 R2 轮审查发现的 P0/P1 问题
- v3.0.0: 第二轮审查修订版 — 修复 17 个 P0 问题
- v2.0.0: 初始实现版
