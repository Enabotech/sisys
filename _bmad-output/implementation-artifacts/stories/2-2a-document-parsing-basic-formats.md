# Story 2-2a: 文档解析与内容提取（基础格式）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。
>
> **🔧 技术约束：**
> 1. **解析库已安装** — `pypdf ^6.12.1`、`python-docx ^1.1.0`、`openpyxl ^3.1.2`、`pillow ^12.1.1`、`pytesseract ^0.3.10` 已在 `pyproject.toml` 中声明，无需新增依赖
> 2. **现有 Mock 任务替换** — `src/infrastructure/workflow/tasks/document_tasks.py` 的 `parse_document()` 当前返回 mock 数据，本 Story 将实现真实解析逻辑
> 3. **ParseStatus 已存在** — `Document.parse_status` 字段（`PENDING/IN_PROGRESS/COMPLETED/FAILED`）已在 Story 2-1 实现
> 4. **事件已定义** — `DocumentUploaded`（上传完成触发）和 `DocumentProcessed`（解析完成触发）已存在于 `src/domain/events/document_events.py`
> 5. **MVP 范围** — 本 Story 仅解析基础格式（PDF/Word/TXT），扩展格式（PPT/Excel/图像/HTML）由 Story 2-2b 负责
> 6. **DocLayNet 预留** — 解析输出需预留 `bbox` 字段（x, y, width, height, page），为 Story 2-3 版面保留做准备

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统自动解析上传的基础格式文档（PDF/Word/TXT）并提取文本、表格、图像内容,
**So that** 非结构化文档转化为结构化知识资产，支撑后续智能检索与战略分析。

### 业务价值

本 Story 是 Epic 2（文档与数据管理）的核心处理环节，承接 Story 2-1（文档上传），为后续 Stories 打下基础：
1. **核心格式解析** — PDF/DOCX/TXT 三种基础格式的文本与表格提取
2. **结构化输出** — 解析结果转换为统一 JSON Schema，供后续流水线消费
3. **版面信息预留** — 为 DocLayNet 版面保留（Story 2-3）预留 bbox 字段
4. **事件驱动触发** — 消费 `DocumentUploaded` 事件，发布 `DocumentProcessed` 事件
5. **准确率保障** — 基础格式解析准确率 ≥95%（抽样验证）

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 2: 文档与数据管理，Story 2.2a

**前置依赖:** Story 2-1（文档上传 — 已完成 ✅）

**后续依赖:** Story 2-2b（扩展格式解析）、Story 2-3（DocLayNet 版面保留）、Story 3-1a（语义检索）均依赖本 Story

**覆盖 FR:** FR-DM-02（文档解析与内容提取）

**or.md 公理追溯:** or.md 二.1.(2) — "解析 17 种格式文档，提取文本、表格、图像内容，输出结构化 JSON"

---

## ✅ Acceptance Criteria 验收标准

### AC-1: PDF 文档解析

**Given** 用户上传的 PDF 文档已存入 MinIO（`parse_status=PENDING`）
**When** 系统收到 `DocumentUploaded` 事件并触发解析流程
**Then** 使用 `pypdf` 解析 PDF，提取文本内容
**And** 检测并提取表格（基于文本定位推断）
**And** 输出结构化 JSON（包含 pages、texts、tables、images 字段）
**And** 更新 `parse_status=COMPLETED`，发布 `DocumentProcessed` 事件
**And** 解析失败时设置 `parse_status=FAILED` 并记录错误信息

**验证标准/Validation Criteria:**
- [x] PDF 文本提取准确率 ≥95%（抽样验证，纯文本 PDF）
- [x] 表格检测基于文本定位推断（非图像识别，Story 2-4 语义提取增强）
- [x] 输出 JSON 包含 `pages` 数组（每页 texts/tables/images）
- [x] 每个元素预留 `bbox` 字段（DocLayNet 预留，MVP 填 null）
- [x] 加密 PDF 返回解析失败（`parse_status=FAILED`，错误信息明确）
- [x] 空 PDF（0 页）返回解析失败
- [x] 超大 PDF（>500 页）解析超时保护（P95<500ms 单页处理，整体超限降级处理）

### AC-2: Word 文档解析

**Given** 用户上传的 DOCX 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 使用 `python-docx` 解析 DOCX，提取文本、表格内容
**And** 识别段落样式（标题/正文/列表）
**And** 输出结构化 JSON（格式与 PDF 输出一致）
**And** 更新 `parse_status=COMPLETED`，发布 `DocumentProcessed` 事件

**验证标准/Validation Criteria:**
- [x] DOCX 文本提取准确率 ≥95%（抽样验证）
- [x] 表格提取包含行列结构
- [x] 段落样式识别（paragraph.style.name → heading/body/list）
- [x] 旧版 DOC 格式不支持（返回 `parse_status=FAILED`，错误信息明确建议转换为 DOCX）
- [x] 空 DOCX（无内容）返回解析失败

### AC-3: TXT 文档解析

**Given** 用户上传的 TXT 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 按段落分割文本（空行分隔）
**And** 自动检测编码（UTF-8/GBK/GB18030）
**And** 输出结构化 JSON（单页结构，texts 数组）

**验证标准/Validation Criteria:**
- [x] 编码自动检测（内置方案：依次尝试 UTF-8 → GBK → GB18030，**不引入 chardet 新依赖** — pyproject.toml 中无 chardet）
- [x] 段落分割逻辑（连续空行分隔）
- [x] 无扩展名编码错误返回解析失败
- [x] 超大 TXT（>10MB）分块处理

### AC-4: 解析结果结构化输出

**Given** 文档解析完成
**When** 生成解析结果 JSON
**Then** 输出遵循统一 Schema（见 SDD 规范）
**And** 包含 `document_id`、`mime_type`、`pages` 数组
**And** 每页包含 `texts`、`tables`、`images` 数组
**And** 每个元素包含 `content`、`bbox`（预留）、`confidence` 字段
**And** 存储至 PostgreSQL `documents.metadata` JSONB 字段

**验证标准/Validation Criteria:**
- [x] JSON Schema 严格定义（见 SDD 规范）
- [x] `bbox` 字段结构 `{x, y, width, height, page}`（MVP 填 null，Story 2-3 实现）
- [x] `confidence` 字段默认 1.0（OCR 场景由 Story 2-5 实现真实置信度）
- [x] 元数据持久化与 `parse_status` 更新在事务内完成

### AC-5: 解析事件触发与状态流转

**Given** 文档上传完成并发布 `DocumentUploaded` 事件
**When** 事件处理器收到事件
**Then** 从 MinIO 下载文件，执行解析
**And** 解析成功后更新 `parse_status=COMPLETED`
**And** 发布 `DocumentProcessed` 事件（包含 `parse_result` 字段）
**And** 解析失败时设置 `parse_status=FAILED`，不发布 `DocumentProcessed`

**验证标准/Validation Criteria:**
- [x] 事件消费通过 Prefect 流程触发（`document_processing_flow` 已定义解析编排骨架，消费端由 Prefect 调度器或 RabbitMQ consumer 触发）
- [x] 状态流转：`PENDING → IN_PROGRESS → COMPLETED/FAILED`
- [x] `DocumentProcessed.parse_result` 包含完整解析输出
- [x] 失败场景不发布 `DocumentProcessed`，仅记录错误日志
- [x] MVP 触发方式：Prefect flow 由调用方主动触发（`document_processing_flow(document_id, file_path, event_publisher)`），RabbitMQ 事件消费者不在本 Story 范围（推迟至 Epic 7 API 集成 Story 7-2 REST API 接口或后续专用事件消费者 Story）

### AC-6: 解析准确率验证

**Given** 系统完成文档解析
**When** 进行抽样验证（≥10 个样本）
**Then** 基础格式（PDF/DOCX/TXT）解析准确率 ≥95%
**And** 准确率定义：提取内容与原文档内容的一致度（人工对比）

**验证标准/Validation Criteria:**
- [x] 准确率抽样验证流程定义（验收测试覆盖）
- [x] 失败样本记录并分析原因
- [x] P95 解析延迟 <500ms（单文档处理，**测量范围：仅 parser.parse() 纯解析时间，不含 MinIO 下载、临时文件 IO、repo.save()**）
- [x] 并发解析能力 ≥10（Task 8 集成测试验证，使用 asyncio.gather() 并发调用 parse_document）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] `DocumentProcessed` 事件已存在于 `src/domain/events/document_events.py`
  - 字段：`document_id: uuid.UUID`, `parse_result: dict[str, Any]`, `embedding: list[float] | None`
  - 本 Story 需扩展 `parse_result` 字段的 Schema 定义（见下方）
- [x] `DocumentUploaded` 事件已存在，本 Story 消费此事件触发解析流程

#### 数据模型 (Data Models)

- [x] `ParsedDocument` 值对象 — 解析结果顶层容器
  ```python
  @dataclass(frozen=True)
  class ParsedDocument:
      """解析结果顶层容器"""
      document_id: str
      mime_type: str
      pages: list[ParsedPage]
      parse_status: Literal["completed", "failed"]
      error_message: str | None = None
      parse_timestamp: str = ""  # ISO 8601

      def to_dict(self) -> dict[str, Any]:
          """序列化为 JSON 可存储字典"""
          return {
              "document_id": self.document_id,
              "mime_type": self.mime_type,
              "pages": [p.to_dict() for p in self.pages],
              "parse_status": self.parse_status,
              "error_message": self.error_message,
              "parse_timestamp": self.parse_timestamp,
          }
  ```

- [x] `ParsedPage`/`ParsedElement`/`ParsedTable`/`BoundingBox` 值对象 — 解析结果结构化组件
  ```python
  @dataclass(frozen=True)
  class ParsedPage:
      """单页解析结果"""
      page_number: int
      texts: list[ParsedElement]
      tables: list[ParsedTable]
      images: list[ParsedElement]  # MVP 仅记录存在，不提取内容

  @dataclass(frozen=True)
  class ParsedElement:
      """解析元素（文本/图像）"""
      content: str
      bbox: BoundingBox | None = None  # DocLayNet 预留，MVP 填 None
      confidence: float = 1.0  # OCR 场景由 Story 2-5 实现

      def to_dict(self) -> dict[str, Any]:
          """序列化为 JSON 可存储字典"""
          return {"content": self.content, "bbox": None, "confidence": self.confidence}

  @dataclass(frozen=True)
  class BoundingBox:
      """元素边界框坐标"""
      x: float
      y: float
      width: float
      height: float
      page: int

  @dataclass(frozen=True)
  class ParsedTable:
      """表格解析结果"""
      rows: list[list[str]]
      bbox: BoundingBox | None = None
      confidence: float = 1.0

      def to_dict(self) -> dict[str, Any]:
          """序列化为 JSON 可存储字典"""
          return {"rows": self.rows, "bbox": None, "confidence": self.confidence}
  ```

**序列化路径说明：** `ParsedDocument`（frozen dataclass）→ `to_dict()` → 存入 `DocumentProcessed.parse_result`（`dict[str, Any]`）和 `Document.metadata["parse_result"]`（JSONB）。端口 `DocumentParserPort.parse()` 返回强类型 `ParsedDocument`，应用层 `DocumentParsingService` 调用 `.to_dict()` 转换为 dict 后传给事件和仓储。

- [x] `ParseResult` TypedDict — 存储到 `Document.metadata["parse_result"]` 的 JSON 结构
  ```python
  class ParseResult(TypedDict):
      document_id: str
      mime_type: str
      pages: list[dict[str, Any]]  # ParsedPage 的 JSON 序列化形式
      parse_status: Literal["completed", "failed"]
      error_message: str | None
      parse_timestamp: str  # ISO 8601
  ```

#### 统一端口定义注册与管理 (Port Contract)

- [ ] **新增端口** `document_parser` — 定义于 `src/domain/ports/document_parser.py`
  - 使用 `@runtime_checkable` 装饰器 + `class DocumentParserPort(Protocol)`
  - Protocol 接口：`parse(file_path: str, mime_type: str) -> ParsedDocument`（接收本地文件路径 + MIME 类型用于路由，返回强类型解析结果）
  - 注册至 `src/domain/ports/registry.py`，version="1.0.0"，owner="epic-2"
  - 契约测试位于 `tests/contracts/test_port_contract_document_parser.py`
  - **说明：** `mime_type` 参数用于 CompositeDocumentParser 内部路由决策（选择 PDFParser/WordParser/TextParser），单格式解析器忽略此参数
- [x] **现有端口复用**：
  - `document_repository`（`DocumentRepositoryPort`） — 使用 `save()` 方法更新 `parse_status` 和 `metadata`（项目仓储端口无 update_* 方法，统一用 `save()` 全量更新，与 Story 2-1 模式一致）
  - `document_storage`（`DocumentStoragePort`） — 通过继承的 `L4ObjectPort.retrieve(bucket_type="raw-documents", object_key=..., version_id=None) -> AsyncIterator[bytes]` 从 MinIO 下载文件
  - `event_publisher`（`EventPublisher`） — 发布 `DocumentProcessed`

**端口契约清单：**

| 端口名称 | 接口 | 实现 | 注册位置 | Lifetime | Version | Owner |
|---------|------|------|----------|----------|---------|-------|
| `document_parser` | `DocumentParserPort` | `CompositeDocumentParser` | domain/ports/document_parser.py | SCOPED | 1.0.0 | epic-2 |
| `document_repository` | `DocumentRepositoryPort` | `PostgreSQLDocumentRepository` | domain/ports/document_repository.py | SCOPED | 1.0.0 | epic-2 |
| `document_storage` | `DocumentStoragePort` | `MinIODocumentStorage` | application/ports/document_storage_port.py | SCOPED | 1.0.0 | epic-1 |
| `event_publisher` | `EventPublisher` | `DualChannelEventBus` | domain/ports/event_publisher.py | SCOPED | 1.0.0 | epic-1 |

#### API 契约 (API Contract)

- [x] 本 Story 无新增 API 端点（解析流程由事件驱动触发）
- [x] 后续可通过 `GET /api/v1/documents/{id}` 查询解析结果（`metadata.parse_result`）

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：pypdf, python-docx, openpyxl, pytesseract, pillow, prefect, fastapi, pydantic, sqlalchemy 等

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_document_parse.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_document_parse.py`
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | PDFParser | PDF 文本提取 | `test_pdf_parser.py` | Task 1 |
| **TDD 单元测试** | WordParser | DOCX 文本/表格提取 | `test_word_parser.py` | Task 2 |
| **TDD 单元测试** | TextParser | TXT 编码检测/分段 | `test_text_parser.py` | Task 3 |
| **TDD 单元测试** | CompositeDocumentParser | MIME 类型路由 | `test_composite_parser.py` | Task 4 |
| **TDD 单元测试** | DocumentParsingService | 编排流程/状态更新 | `test_document_parsing_service.py` | Task 5 |
| **TDD 契约测试** | DocumentParserPort | 端口注册/版本/方法 | `test_port_contract_document_parser.py` | Task 0 |
| **SDD 架构验证** | 六边形架构 | 依赖方向/零依赖 | `test_arch_document_parser.py` | Task 7 |
| **集成测试** | 解析流水线 | 上传→解析→事件发布 | `test_document_parse_integration.py` | Task 8 |
| **验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_document_parse.feature` | Task 0 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **领域层覆盖率 ≥90%**
- [ ] **应用层覆盖率 ≥85%**
- [ ] **基础设施层覆盖率 ≥75%**

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

- [ ] 使用 `TestTenant` UUID 前缀隔离测试数据
- [ ] BDD 步骤使用 `event_loop.run_until_complete()`
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | PDF 文档解析 | Task 1 | PDFParser 实现 | `test_pdf_parser.py` |
| AC-2 | Word 文档解析 | Task 2 | WordParser 实现 | `test_word_parser.py` |
| AC-3 | TXT 文档解析 | Task 3 | TextParser 实现 | `test_text_parser.py` |
| AC-4 | 解析结果结构化输出 | Task 0 | ParsedDocument Schema | 契约测试 |
| AC-5 | 解析事件触发与状态流转 | Task 5 | DocumentParsingService | `test_document_parsing_service.py` |
| AC-6 | 解析准确率验证 | Task 9 | 验收测试抽样验证 | `test_acceptance_document_parse.feature` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-4（解析结果结构化输出）

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `ParsedPage`/`ParsedElement`/`ParsedTable`/`BoundingBox` 值对象（`src/domain/value_objects/parsed_document.py`）
- [ ] Subtask 0.2: 定义 `ParseResult` TypedDict（`src/domain/value_objects/parsed_document.py`）
- [ ] Subtask 0.3: 定义 `DocumentParserPort` Protocol（`src/domain/ports/document_parser.py`）
- [ ] Subtask 0.4: 注册 `document_parser` 端口至 `registry.py`
- [ ] Subtask 0.5: 编写端口契约测试（`tests/contracts/test_port_contract_document_parser.py`）
- [ ] Subtask 0.6: 编写 Gherkin 验收测试（`tests/acceptance/test_acceptance_document_parse.feature`）
- [ ] Subtask 0.7: 编写 BDD 步骤实现（`tests/acceptance/test_acceptance_document_parse.py`）
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: PDF 文档解析器实现

**关联 AC:** AC-1

#### TDD 循环 A：PDFParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_pdf_parser.py`（文本提取、表格检测、加密拒绝） |
| 🟢 绿 | 实现 `PDFParser` 类最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 PDFParser 失败测试
  - 测试场景：纯文本 PDF 提取、多页 PDF、表格检测、加密 PDF 拒绝、空 PDF 拒绝
- [ ] Subtask 1.2: 🟢 绿 — 实现 `PDFParser.parse(file_path) -> ParsedDocument`
  - 使用 `pypdf.PdfReader` 提取文本
  - 表格检测：基于文本定位推断（非图像识别）
  - 异常处理：加密/空文档返回 `ParseResult` with `parse_status="failed"`
- [ ] Subtask 1.3: 🔄 重构 — 优化 PDFParser 代码

**完成标准/Definition of Done:**
- [ ] PDFParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥85%

---

### Task 2: Word 文档解析器实现

**关联 AC:** AC-2

#### TDD 循环 A：WordParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_word_parser.py`（文本提取、表格提取、样式识别） |
| 🟢 绿 | 实现 `WordParser` 类最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 WordParser 失败测试
  - 测试场景：DOCX 文本提取、表格结构、段落样式、旧版 DOC 拒绝
- [ ] Subtask 2.2: 🟢 绿 — 实现 `WordParser.parse(file_path) -> ParsedDocument`
  - 使用 `python-docx.Document` 提取文本和表格
  - 段落样式识别（`paragraph.style.name`）
  - 旧版 DOC 格式拒绝（返回 failed）
- [ ] Subtask 2.3: 🔄 重构 — 优化 WordParser 代码

**完成标准/Definition of Done:**
- [ ] WordParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥85%

---

### Task 3: TXT 文档解析器实现

**关联 AC:** AC-3

#### TDD 循环 A：TextParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_text_parser.py`（编码检测、段落分割） |
| 🟢 绿 | 实现 `TextParser` 类最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 TextParser 失败测试
  - 测试场景：UTF-8 编码、GBK 编码、段落分割、超大文件分块
- [ ] Subtask 3.2: 🟢 绿 — 实现 `TextParser.parse(file_path) -> ParsedDocument`
  - 编码自动检测（尝试 UTF-8 → GBK → GB18030）
  - 段落分割（连续空行分隔）
- [ ] Subtask 3.3: 🔄 重构 — 优化 TextParser 代码

**完成标准/Definition of Done:**
- [ ] TextParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥85%

---

### Task 4: 组合解析器（MIME 类型路由）

**关联 AC:** AC-1, AC-2, AC-3

#### TDD 循环 A：CompositeDocumentParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_composite_parser.py`（MIME 类型路由） |
| 🟢 绿 | 实现 `CompositeDocumentParser` 类最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 编写 CompositeDocumentParser 失败测试
  - 测试场景：PDF MIME 调用 PDFParser、DOCX MIME 调用 WordParser、TXT MIME 调用 TextParser、未知 MIME 拒绝
- [ ] Subtask 4.2: 🟢 绿 — 实现 `CompositeDocumentParser.parse(file_path, mime_type)` — 实现 `DocumentParserPort` 协议
  - MIME 类型映射：`application/pdf → PDFParser`、`application/vnd.openxmlformats-officedocument.wordprocessingml.document → WordParser`、`text/plain → TextParser`
  - 组合模式：内部持有各格式 Parser 实例，`mime_type` 参数用于路由决策
  - 未知 MIME 类型抛出 `ValueError`
- [ ] Subtask 4.3: 在 `src/composition_root.py` 注册 `document_parser` 端口（impl 指向 CompositeDocumentParser，SCOPED lifetime）
- [ ] Subtask 4.4: 🔄 重构 — 优化 CompositeDocumentParser 代码

**完成标准/Definition of Done:**
- [ ] CompositeDocumentParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥85%

---

### Task 5: 文档解析服务（应用层编排）

**关联 AC:** AC-5

> **前置修复：** Story 2-1 的 `DocumentUploadService.upload()` 调用 `store_document()` 后未将返回的 `object_key` 存入 `Document.metadata`。
> 本 Task 的 Subtask 5.0 必须先修复此 GAP，否则解析服务无法获取文件位置。

#### TDD 循环 A：DocumentParsingService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_document_parsing_service.py`（解析编排、状态更新） |
| 🟢 绿 | 实现 `DocumentParsingService` 类最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 5.0: 修复 `DocumentUploadService` — 存储 MinIO object_key 到 `Document.metadata`
  - **(a)** 修改 `upload()` 方法：捕获 `store_document()` 返回值，存入 `doc.metadata["storage_object_key"]`（在 `repo.save(doc)` 之前）
  - **(b)** 修改 `register_document()` 方法：新增参数 `object_key: str`，存入 `doc.metadata["storage_object_key"]`
  - **(c)** 修改 API 路由 `src/interfaces/api/document_upload.py` 中 `register_document()` 调用处，传入 `object_key`（从 `ChunkedUploadManager.complete_upload()` 返回值获取）
  - **(d)** 编写测试验证 `upload()` 和 `register_document()` 两条路径均正确存储 `storage_object_key`
  - **修改文件**：`src/application/services/document_upload_service.py`、`src/interfaces/api/document_upload.py`
- [ ] Subtask 5.1: 🔴 红 — 编写 DocumentParsingService 失败测试
  - 测试场景：下载文件→写临时文件→解析→更新状态→发布事件→清理临时文件、解析失败状态处理
- [ ] Subtask 5.2: 🟢 绿 — 实现 `DocumentParsingService.parse_document(document_id: UUID)`
  - 编排流程：
    1. `repo.find(query)` 获取 Document 实体（含 `metadata["storage_object_key"]`）
    2. `object_key = document.metadata["storage_object_key"]` — 读取 MinIO 对象键
    3. `stream = document_storage.retrieve(bucket_type="raw-documents", object_key=object_key)` — 获取 AsyncIterator[bytes]
    4. 写入 `tempfile.NamedTemporaryFile(delete=False)` — **桥接逻辑：retrieve() 返回字节流，pypdf/python-docx 需要 file_path**
    5. `parser.parse(temp_file_path)` 调用解析器
    6. `parsed_doc.to_dict()` 转换为 dict
    7. 更新 Document 实体：`parse_status=COMPLETED`，`metadata["parse_result"]=result_dict`
    8. `repo.save(updated_document)` 全量更新（项目中仓储端口无 update_* 方法）
    9. `event_publisher.publish(DocumentProcessed(...))` 发布事件
    10. `os.unlink(temp_file_path)` 清理临时文件（finally 块）
  - 事务：`repo.save()` 与事件发布在同一 `session_context()` 事务内（架构保证：ContextVar 共享 AsyncSession）
- [ ] Subtask 5.3: 🔄 重构 — 优化 DocumentParsingService 代码

**完成标准/Definition of Done:**
- [ ] DocumentParsingService 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥85%

---

### Task 6: Prefect 任务替换（真实解析逻辑）

**关联 AC:** AC-5

> **目的：** 将 `document_tasks.py` 的 mock 实现替换为真实解析逻辑
> **关键约束：** Prefect `@task` 是独立函数，无法通过构造器注入服务。通过 `get_resolver().resolve("document_parsing_service")` 获取服务实例。

- [ ] Subtask 6.1: 🔴 红 — 编写 `parse_document` 任务测试（调用真实 Service）
- [ ] Subtask 6.2: 🟢 绿 — 修改 `parse_document(document_id: UUID, file_path: str) -> dict[str, Any]`
  - 当前签名保持不变（`document_id` + `file_path`）
  - 通过 `get_resolver().resolve("document_parsing_service")` 获取 `DocumentParsingService`
  - 调用 `service.parse_document(document_id)` 执行完整解析流程
  - **注意**：Prefect task 接收的 `file_path` 参数在重构后不再需要（Service 内部从 MinIO 下载），但为保持 API 兼容性保留参数签名
- [ ] Subtask 6.3: 🟢 绿 — 修改 `document_processing_flow`：移除内部事件发布逻辑（由 `DocumentParsingService` 统一发布，避免重复发布 `DocumentProcessed`）
- [ ] Subtask 6.4: 🔄 重构 — 保持 Prefect @task 装饰器和 retries=2

**完成标准/Definition of Done:**
- [ ] Prefect 任务真实解析逻辑实现
- [ ] retries 机制保留

---

### Task 7: SDD 架构约束验证测试

**关联 AC:** 所有 AC

> **性质说明：** 本 Task 是 SDD 规范验证测试，验证六边形架构约束。

- [ ] Subtask 7.1: 创建 `tests/unit/architecture/test_arch_document_parser.py`
- [ ] Subtask 7.2: 验证 `DocumentParserPort` 位于 domain 层
- [ ] Subtask 7.3: 验证 `PDFParser/WordParser/TextParser` 位于 infrastructure 层
- [ ] Subtask 7.4: 验证领域层无外部依赖（pypdf, python-docx 等）

**完成标准/Definition of Done:**
- [ ] 所有架构测试通过
- [ ] 循环依赖检测使用 ruff/isort

---

### Task 8: 集成测试

**关联 AC:** AC-5, AC-6（并发解析）

- [ ] Subtask 8.1: 创建 `tests/integration/test_document_parse_integration.py`
- [ ] Subtask 8.2: 测试完整解析流水线（上传→解析→状态更新→事件发布）
- [ ] Subtask 8.3: 测试解析失败场景（加密 PDF、空文档、未知 MIME）
- [ ] Subtask 8.4: 测试并发解析 ≥10 文档（使用 `asyncio.gather()` 并发调用 `parse_document`，验证无竞态、无资源泄漏）
- [ ] Subtask 8.5: 测试临时文件清理（解析完成后 temp 文件已删除）

**完成标准/Definition of Done:**
- [ ] 集成测试全部通过
- [ ] 覆盖率≥70%

---

### Task 9: 开发结束验收测试

**关联 AC:** AC-6

- [ ] Subtask 9.1: 完善 Gherkin 验收场景（准确率验证）
- [ ] Subtask 9.2: 运行完整验收测试套件
- [ ] Subtask 9.3: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`sisys-core-domain-design.md`](../../docs/architecture/sisys-core-domain-design.md) §17.1

- **版面保留模式（DocLayNet 标准）：** `LayoutPreservingParser` 记录元素坐标（bbox: x, y, width, height, page）
- **OCR 置信度管理：** `OCRProcessor.CONFIDENCE_THRESHOLD = 0.85`，低置信度区域标记 `needs_review`
- **DQI 数据质量基准：** DQI = 0.4*完整性 + 0.3*唯一性 + 0.3*时效性，阈值 0.6

### 关键架构决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **pypdf（选中）** | 纯 Python、无外部依赖、支持加密检测 | 表格识别较弱 | ✅ 8/10 |
| **pdfplumber** | 表格提取更精确 | 依赖 pdfminer.six，额外依赖 | 7/10 |
| **unstructured.io** | 全格式统一接口 | 重依赖（torch 等）、部署复杂 | 6/10 |

### 项目结构说明

```
src/
├── domain/
│   ├── value_objects/
│   │   └── parsed_document.py        # [新建] ParsedPage/Element/Table/BoundingBox
│   └── ports/
│       └── document_parser.py        # [新建] DocumentParserPort Protocol
│
├── application/
│   └── services/
│       └── document_parsing_service.py  # [新建] 解析编排服务
│
├── infrastructure/
│   ├── external_services/
│   │   └── document_parsing/         # [新建目录]
│   │       ├── pdf_parser.py         # PDFParser（使用 pypdf）
│   │       ├── word_parser.py        # WordParser（使用 python-docx）
│   │       ├── text_parser.py        # TextParser（编码检测）
│   │       └── composite_parser.py   # CompositeDocumentParser（MIME 路由）
│   └── workflow/tasks/
│       └── document_tasks.py         # [修改] parse_document 替换 mock
│
└── composition_root.py               # [修改] 注册 document_parser 端口

tests/
├── unit/
│   ├── domain/value_objects/test_parsed_document.py
│   ├── domain/ports/test_document_parser.py
│   ├── infrastructure/external_services/document_parsing/
│   │   ├── test_pdf_parser.py
│   │   ├── test_word_parser.py
│   │   ├── test_text_parser.py
│   │   └── test_composite_parser.py
│   ├── application/services/test_document_parsing_service.py
│   └── architecture/test_arch_document_parser.py
│
├── integration/
│   └── test_document_parse_integration.py
│
├── contracts/
│   └── test_port_contract_document_parser.py
│
└── acceptance/
    ├── test_acceptance_document_parse.feature
    └── test_acceptance_document_parse.py
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 2-1-document-upload-17-formats](./2-1-document-upload-17-formats.md)

**关键学习/Key Learnings:**
1. **事件扩展向后兼容** — `DocumentProcessed` 已存在，扩展 `parse_result` Schema 不影响事件构造
2. **DI 注册延迟加载陷阱** — impl 字符串拼写错误不立即报错，需契约测试覆盖
3. **事件双注册** — 新增事件需同时更新 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`
4. **TestTenant 隔离** — 并行测试 UUID 前缀隔离，新端口测试也必须使用
5. **MinIO 流式处理** — `document_storage.retrieve()` 返回 `AsyncIterator[bytes]`（继承自 `L4ObjectPort.retrieve()`），禁止全量 bytes 加载（防 OOM）
6. **Prefect 任务 retries** — `parse_document` 已有 `retries=2`，替换实现需保留
7. **状态流转事务原子性** — `parse_status` 更新与 Outbox 写入需同一事务
8. **仓储无 update_* 方法** — 项目中所有仓储端口统一使用 `save()` 全量更新，不存在 `update_parse_status()` 等部分更新方法

**应用到本故事/Applied to This Story:**
- [ ] `DocumentParserPort` impl 字符串拼写纳入契约测试
- [ ] 解析服务使用 `TestTenant` 进行租户隔离
- [ ] 文件下载：`L4ObjectPort.retrieve(bucket_type="raw-documents", object_key=...)` → 写入临时文件 → 解析器读取 file_path → 清理临时文件
- [ ] Prefect 任务替换保留 `retries=2`
- [ ] `parse_status` 更新通过 `repo.save()` 全量更新，与事件发布同一事务
- [ ] 解析器单元测试使用本地 fixture 文件（非 MinIO 下载），集成测试覆盖完整 retrieve→parse 流程

### 文件下载桥接逻辑（核心技术路径）

**来源:** `src/domain/ports/l4_object.py`（L4ObjectPort）, `src/application/ports/document_storage_port.py`（DocumentStoragePort 继承 L4ObjectPort）

**问题：** `pypdf.PdfReader` 和 `python-docx.Document` 需要 **文件路径**（`str`），但 MinIO 下载 API `L4ObjectPort.retrieve()` 返回 `AsyncIterator[bytes]`。

**桥接方案：**
```python
import os
import tempfile

async def _download_to_temp(self, bucket_type: str, object_key: str) -> str:
    """从 MinIO 下载文件到临时文件，返回临时文件路径"""
    stream = self._document_storage.retrieve(bucket_type, object_key)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
    try:
        async for chunk in stream:
            tmp.write(chunk)
        tmp.close()
        return tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise
```

**临时文件清理：** 在 `DocumentParsingService.parse_document()` 的 `finally` 块中调用 `os.unlink(temp_path)`。

**MinIO object_key 获取：** Story 2-1 存在 GAP — `DocumentUploadService.upload()` 调用 `store_document()` 后未捕获返回值。本 Story Task 5 Subtask 5.0 需修复：将 `object_key` 存入 `Document.metadata["storage_object_key"]`。解析服务通过 `repo.find()` 获取 Document 后读取此字段。`register_document()` 方法（分片上传路径）也需同步修复。

### 解析库技术细节

**pypdf 使用要点：**
```python
from pypdf import PdfReader

reader = PdfReader(file_path)
# 加密检测
if reader.is_encrypted:
    return ParsedDocument(parse_status="failed", error_message="PDF is encrypted")

for page in reader.pages:
    text = page.extract_text()
    # 表格检测：基于文本定位推断（简化实现）
```

**python-docx 使用要点：**
```python
from docx import Document

doc = Document(file_path)
for paragraph in doc.paragraphs:
    style = paragraph.style.name  # "Heading 1", "Normal", "List Bullet"
for table in doc.tables:
    rows = [[cell.text for cell in row.cells] for row in table.rows]
```

**编码检测（TXT）：**
```python
# 简化实现：依次尝试 UTF-8 → GBK → GB18030
def detect_encoding(content: bytes) -> str:
    for encoding in ["utf-8", "gbk", "gb18030"]:
        try:
            content.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"  # 默认
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | [模型名称] |
| **Version** | create-story workflow v2.7.0 |
| **Execution Date** | 2026-05-31 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/sisys-core-domain-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-1-document-upload-17-formats.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `sisys-core-domain-design.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范
- [ ] 解析库技术细节补充

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-2a-document-parsing-basic-formats.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/value_objects/parsed_document.py` — 解析结果值对象
- `src/domain/ports/document_parser.py` — DocumentParserPort Protocol
- `src/application/services/document_parsing_service.py` — 解析编排服务
- `src/infrastructure/external_services/document_parsing/pdf_parser.py` — PDF 解析器
- `src/infrastructure/external_services/document_parsing/word_parser.py` — Word 解析器
- `src/infrastructure/external_services/document_parsing/text_parser.py` — TXT 解析器
- `src/infrastructure/external_services/document_parsing/composite_parser.py` — 组合解析器

**待修改的文件/To Be Modified:**
- `src/domain/ports/registry.py` — 注册 document_parser 端口
- `src/composition_root.py` — DI 注册
- `src/infrastructure/workflow/tasks/document_tasks.py` — 替换 mock 实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.2a |
| **Story Key** | 2-2a-document-parsing-basic-formats |
| **File** | `_bmad-output/implementation-artifacts/stories/2-2a-document-parsing-basic-formats.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0-2a（MVP 关键路径） |
| **覆盖 FR** | FR-DM-02（文档解析与内容提取） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成（10 个 Task）
2. [ ] All acceptance criteria specified 所有验收标准已定义（6 个 AC）
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

---

### 下一步 Next Steps

- [ ] Story 状态 `ready-for-dev`
- [ ] 运行 `dev-story` 开始实施
- [ ] 开发完成后执行 `code-review`
- [ ] 自动化测试通过

---

**故事版本/Story Version:** v0.4.0
**创建日期/Created:** 2026-05-31
**最后更新/Last Updated:** 2026-05-31
**更新说明/Description:**
- v0.4.0: Round 3 审查修订 — P0 DocumentParserPort签名(mime_type)、Subtask5.0扩展(register_document路径)、并发解析≥10、事件去重(Subtask6.3)、ParsedDocument顶层值对象、composition_root注册(Subtask4.3)
- v0.3.0: Round 2 审查修订 — P0 object_key GAP修复(Subtask 5.0)、MinIO bucket_type/retrieve签名精确化
- v0.2.0: Round 1 审查修订 — 修复 P0 问题（文件下载桥接/仓储更新/编码依赖/事件消费/序列化路径/Prefect DI）
- v0.1.0: 创建故事文件
