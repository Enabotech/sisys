# Story 2.2b: 文档解析与内容提取（扩展格式）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统解析扩展格式文档（PPT/PPTX/XLS/XLSX/CSV/JPEG/PNG/GIF/HTML/Markdown/RTF）并提取内容,
**So that** 支持 17 种格式完整解析，企业现有各类文档都可处理。

### 业务价值

Epic 2 文档与数据管理的扩展格式支持。在 Story 2-2a 基础格式（PDF/DOCX/TXT）解析完成后，
本 Story 补充剩余格式的解析能力，实现 17 种格式全覆盖。扩展格式解析器复用 2-2a 已建立的
`DocumentParserPort` 端口协议、`ParsedDocument` 值对象和 `CompositeDocumentParser` 组合模式，
仅需新增各格式解析器实现并注册到组合解析器。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: PPT/PPTX 文档解析

**Given** 用户上传的 PPTX 文档已存入 MinIO（`parse_status=PENDING`）
**When** 系统收到 `DocumentUploaded` 事件并触发解析流程
**Then** 使用 `python-pptx` 解析 PPTX，提取每页幻灯片的文本、表格、备注内容
**And** 输出结构化 JSON（与 PDF 输出 Schema 一致，texts/tables/images 数组）
**And** 更新 `parse_status=COMPLETED`，发布 `DocumentProcessed` 事件
**And** 旧版 PPT 格式不支持（返回 `parse_status=FAILED`，错误信息建议转换为 PPTX）

**验证标准/Validation Criteria:**
- [ ] PPTX 文本提取包含幻灯片编号和形状类型元数据
- [ ] 表格提取包含行列结构
- [ ] 备注内容提取
- [ ] 空 PPTX（无内容）返回解析失败
- [ ] 旧版 PPT 格式返回友好拒绝消息

### AC-2: Excel 文档解析（XLSX/XLS）

**Given** 用户上传的 XLSX 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 使用 `openpyxl` 解析 XLSX，提取各 Sheet 的表格内容
**And** 每个 Sheet 作为一个 `ParsedTable`，sheet 名称存储于 `ParsedTable.metadata["sheet_name"]`
  - ⚠️ 本 Story 需向 `ParsedTable` 值对象新增 `metadata: dict[str, Any] = field(default_factory=dict)` 字段（参照 `ParsedElement.metadata` 模式），向后兼容
  - `ParsedPage` 无 metadata 字段（不可用），sheet 名称必须挂在 ParsedTable 上
**And** 旧版 XLS 格式返回友好拒绝消息，建议转换为 XLSX（与 PPT→PPTX 处理策略一致）

**验证标准/Validation Criteria:**
- [ ] 多 Sheet 文档每个 Sheet 独立输出为 ParsedTable
- [ ] `read_only=True` 模式降低大文件内存占用
- [ ] `data_only=True` 返回计算后的值而非公式
- [ ] 空 Sheet 跳过（不生成空表格）
- [ ] 旧版 XLS 格式返回友好拒绝消息，建议转换为 XLSX（与 PPT→PPTX 处理策略一致）

### AC-3: CSV 文档解析

**Given** 用户上传的 CSV 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 使用标准库 `csv` 模块解析 CSV，自动检测分隔符和编码
**And** 输出结构化 JSON（单页结构，包含一个 ParsedTable）

**验证标准/Validation Criteria:**
- [ ] 编码自动检测（UTF-8 → GBK → GB18030，复用 TextParser 的 `_detect_and_decode` 逻辑；注意 GBK 是 GB18030 严格子集，先尝试 GBK 更精确）
- [ ] 分隔符自动检测（`csv.Sniffer`）
- [ ] 空文件返回解析失败
- [ ] 超大 CSV（>50MB）分块处理（与 TXT 解析器直接拒绝不同，CSV 行级结构天然支持分块；分块阈值 50MB，每块 10MB）

### AC-4: 图像文档解析（JPEG/PNG/GIF）

**Given** 用户上传的图像文档已存入 MinIO
**When** 系统触发解析流程
**Then** 使用 `Pillow` 提取图像元数据（尺寸/格式/模式）
**And** 使用 `pytesseract` 执行 OCR 文本提取（中/英双语）
**And** 输出结构化 JSON（图像信息存入 images 数组，OCR 文本存入 texts 数组）

**验证标准/Validation Criteria:**
- [ ] 图像元数据提取完整（format/size/mode），存入 `ParsedElement(content="", metadata={"format": "JPEG", "width": 1920, "height": 1080, "mode": "RGB"})`
  - 图像条目 `content` 为空字符串（MVP 仅记录存在，不提取内容），元数据放在 `metadata` dict 中
- [ ] OCR 文本提取支持中文（`chi_sim`）和英文（`eng`）
- [ ] OCR 置信度评分填充 `confidence` 字段
- [ ] GIF 仅处理第一帧
- [ ] 无法 OCR 的图像（纯图形）返回元数据，文本为空
- [ ] Tesseract 未安装时优雅降级（返回元数据，OCR 跳过并记录警告）

### AC-5: HTML 文档解析

**Given** 用户上传的 HTML 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 使用 `BeautifulSoup` + `lxml` 解析 HTML，提取文本和表格
**And** 保留标题层级结构（h1-h6）作为段落样式元数据
**And** 提取 HTML 表格为 ParsedTable

**验证标准/Validation Criteria:**
- [ ] 文本提取使用 `get_text(separator='\n', strip=True)`
- [ ] 表格提取包含 `<th>` 和 `<td>` 内容
- [ ] 标题层级识别（h1-h6 映射到 metadata.style）
- [ ] 编码自动检测（BeautifulSoup 内置能力）
- [ ] 空页面返回解析失败

### AC-6: Markdown 文档解析

**Given** 用户上传的 Markdown 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 使用标准库解析 Markdown，提取段落文本和标题结构
**And** 标题层级（# / ## / ###）作为段落样式元数据
**And** 识别并提取 Markdown 表格

**验证标准/Validation Criteria:**
- [ ] 标题层级识别（正则表达式 `^#+\s+.+$`）
- [ ] 段落按连续空行分割
- [ ] Markdown 表格识别和提取（`| col | col |` 格式）
- [ ] 代码块内容保留
- [ ] 无需引入新依赖（标准库 + 正则实现）

### AC-7: RTF 文档解析

**Given** 用户上传的 RTF 文档已存入 MinIO
**When** 系统触发解析流程
**Then** 尝试使用 `striprtf` 库提取纯文本内容
**And** 如 `striprtf` 不可用则返回友好拒绝消息

**验证标准/Validation Criteria:**
- [ ] RTF 纯文本提取
- [ ] 无第三方库时优雅降级
- [ ] 空 RTF 返回解析失败

### AC-8: CompositeDocumentParser 扩展与集成

**Given** 所有扩展格式解析器已实现
**When** `CompositeDocumentParser` 初始化
**Then** 新增 MIME 类型映射覆盖所有扩展格式
**And** 未注册的 MIME 类型返回 `parse_status=failed` 的 `ParsedDocument`（不抛异常）
**And** `_ALLOWED_TEMP_SUFFIXES` 扩展覆盖新格式后缀

**验证标准/Validation Criteria:**
- [ ] MIME 路由表包含所有 17 种格式映射
- [ ] 不支持的格式返回 `parse_status=failed` + 明确错误消息（不抛异常，与 2-2a CompositeDocumentParser 行为一致）
- [ ] 临时文件后缀白名单已扩展
- [ ] Composition Root 注册所有新解析器
- [ ] 解析性能：非 OCR 格式 P95 < 500ms（纯解析时间，不含 IO）；图像 OCR 格式 P95 < 5s（含 OCR 处理时间）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](../../../docs/developer/sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](../../../docs/developer/sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] 复用 `DocumentProcessed` 事件（Story 2-2a 已定义），**不新增事件**
- [x] 复用 `DocumentUploaded` 事件触发解析流程

#### 数据模型 (Data Models)
- [x] 复用 `ParsedDocument` / `ParsedPage` / `ParsedElement` / `ParsedTable` / `BoundingBox` 值对象
  （Story 2-2a 已定义于 `src/domain/value_objects/parsed_document.py`）
- [ ] **领域层微调：** 向 `ParsedTable` 新增 `metadata: dict[str, Any] = field(default_factory=dict)` 字段
  - 参照已有 `ParsedElement.metadata` 模式，`ParsedTable` 缺少此字段导致 Excel sheet 名称等元数据无处存储
  - 向后兼容：`field(default_factory=dict)` 确保现有代码无需修改
  - 同步更新 `ParsedTable.to_dict()` 方法，增加 `"metadata"` 键
- [x] 扩展格式解析结果遵循统一 Schema（pages 数组包含 texts/tables/images）

#### 统一端口定义注册与管理 (Port Contract)
- [x] 复用 `DocumentParserPort`（Story 2-2a 已定义于 `src/domain/ports/document_parser.py`）
- [x] 复用 `document_parser` 端口注册（Composition Root 已注册 `CompositeDocumentParser`）
- [x] 新增解析器实现 `DocumentParserPort` 协议（`parse(file_path, mime_type) -> ParsedDocument`）
- [x] Composition Root 扩展 `CompositeDocumentParser` 工厂 lambda，注入新解析器
- [x] 端口契约测试扩展覆盖新解析器

**端口契约清单：**

| 端口名称 | 接口 | 实现 | 注册位置 | Lifetime | Version | Owner |
|---------|------|------|----------|----------|---------|-------|
| `document_parser` | `DocumentParserPort` | `CompositeDocumentParser` | domain/ports/document_parser.py | SCOPED | v1.0.0→v1.1.0 | epic-2 |
| `document_repository` | `DocumentRepositoryPort` | `PostgreSQLDocumentRepository` | domain/ports/document_repository.py | SCOPED | v1.0.0 | epic-2 |
| `document_storage` | `DocumentStoragePort` | `MinIODocumentStorage` | application/ports/document_storage_port.py | SCOPED | v1.0.0 | epic-1 |
| `event_publisher` | `EventPublisher` | `DualChannelEventBus` | domain/ports/event_publisher.py | SCOPED | v1.0.0 | epic-1 |

> **版本升级说明：** `document_parser` 从 v1.0.0 升级至 v1.1.0（新增扩展格式解析器注册），接口签名不变，向后兼容。需同步更新 `composition_root.py` 中的 `version="v1.0.0"` → `"v1.1.0"` 和 `tests/contracts/test_port_contract_document_parser.py` 中的 `spec.version == "v1.0.0"` 断言。

#### API 契约 (API Contract)
- [x] 复用 `POST /api/v1/documents` 上传端点（Story 2-1 已定义）
- [x] 复用 `GET /api/v1/documents/{document_id}` 查询端点
- [x] 解析结果存储于 `Document.metadata["parse_result"]` JSONB 字段

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2, python-pptx, openpyxl, pillow, pytesseract, beautifulsoup4, lxml, striprtf

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_document_parse_extended.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_document_parse_extended.py`（BDD 步骤实现）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部确认（复用 2-2a 已有规范）
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | PptxParser | PPTX 文本/表格/备注提取 | `test_pptx_parser.py` | Task 1 |
| **TDD 单元测试** | ExcelParser | XLSX/XLS 多 Sheet 表格提取 | `test_excel_parser.py` | Task 2 |
| **TDD 单元测试** | CSVParser | CSV 分隔符/编码检测 | `test_csv_parser.py` | Task 3 |
| **TDD 单元测试** | ImageParser | 图像元数据 + OCR 提取 | `test_image_parser.py` | Task 4 |
| **TDD 单元测试** | HTMLParser | HTML 文本/表格/标题提取 | `test_html_parser.py` | Task 5 |
| **TDD 单元测试** | MarkdownParser | Markdown 标题/段落/表格 | `test_markdown_parser.py` | Task 6 |
| **TDD 单元测试** | RTFParser | RTF 纯文本提取 | `test_rtf_parser.py` | Task 7 |
| **TDD 单元测试** | CompositeDocumentParser | MIME 路由 + 全格式覆盖 | `test_composite_parser.py` | Task 8 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_document_parse_extended.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_document_parse_extended.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | `test_acceptance_document_parse_extended.feature` | Task 10 |
| **TDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_document_parse_extended.py` | Task 10 |
| **TDD 契约测试** | 端口契约 | 端口注册/版本/兼容性 | `test_port_contract_document_parser.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_document_parser.py` | Task 9 |
| **集成测试** | 完整解析流程 | MinIO→解析→事件发布 | `test_document_parse_extended_integration.py` | Task 8 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P0 阻断门禁**（来源：CLAUDE.md + prd.md）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P0 阻断门禁**（来源：CLAUDE.md + prd.md）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- **P1 阻断门禁**
- [ ] **集成测试覆盖率 ≥70%** — 被测代码位于 `src/infrastructure/` 和 `src/application/`
- [ ] **端口契约测试覆盖率 100%**（`DocumentParserPort` + `CompositeDocumentParser` MIME 路由全量覆盖）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：** 测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | OCR/Tesseract 测试前检查可用性或 mock | 环境不一致 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **BDD async 配合** | BDD 步骤函数不用 @pytest.mark.asyncio | 直接用会导致 BDD context 数据丢失 |
| **asyncio.run 使用** | pytest-xdist 并行测试中 BDD 步骤函数用 event_loop fixture | asyncio.run() 创建新循环，并行测试时可能关闭错误循环 |
| **编程式 Fixture** | 测试文件内定义 `_create_*()` 工厂函数生成临时文件 | 静态文件难维护，编程式可自文档化 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | PPT/PPTX 解析 | Task 1 | PptxParser 实现 | `test_pptx_parser.py` |
| AC-2 | Excel 解析 | Task 2 | ExcelParser 实现 | `test_excel_parser.py` |
| AC-3 | CSV 解析 | Task 3 | CSVParser 实现 | `test_csv_parser.py` |
| AC-4 | 图像 OCR 解析 | Task 4 | ImageParser 实现 | `test_image_parser.py` |
| AC-5 | HTML 解析 | Task 5 | HTMLParser 实现 | `test_html_parser.py` |
| AC-6 | Markdown 解析 | Task 6 | MarkdownParser 实现 | `test_markdown_parser.py` |
| AC-7 | RTF 解析 | Task 7 | RTFParser 实现 | `test_rtf_parser.py` |
| AC-8 | 组合解析器扩展 | Task 8 | CompositeParser 扩展 | `test_composite_parser.py` |
| AC-1~8 | 架构约束验证 | Task 9 | SDD 架构测试 | `test_arch_document_parser.py` |
| AC-1~8 | 最终验收 | Task 10 | 验收测试 | `test_acceptance_document_parse_extended.*` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-8

> **目的：** 确认复用 2-2a 已有规范，编写扩展格式 Gherkin 验收测试。
> 本 Story 不新增端口/事件/值对象，全部复用 2-2a 已实现的基础设施。

- [ ] Subtask 0.1: 确认复用 `DocumentParserPort`（签名不变：`parse(file_path, mime_type) -> ParsedDocument`）
- [ ] Subtask 0.2: 确认复用 `ParsedDocument` 值对象 Schema（pages/texts/tables/images/bbox/confidence）
- [ ] Subtask 0.3: 确认复用 `DocumentProcessed` 事件（不新增事件）
- [ ] Subtask 0.4: 确认复用 `DocumentParsingService` 编排流程（不修改应用层代码，仅扩展 `_ALLOWED_TEMP_SUFFIXES`）
- [ ] **Subtask 0.4a: 修改 `ParsedTable` 值对象** — 新增 `metadata: dict[str, Any] = field(default_factory=dict)` 字段
  - 参照 `ParsedElement.metadata` 已有模式，`ParsedTable` 当前无 metadata 字段
  - 同步更新 `ParsedTable.to_dict()` 方法，增加 `"metadata"` 键
  - 向后兼容：`field(default_factory=dict)` 确保现有代码无需修改
  - ⚠️ **必须在 Task 2 (ExcelParser) 开始前完成**，因 ExcelParser 依赖此字段存储 sheet_name
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_document_parse_extended.feature`
  - Gherkin 行为文档，描述 AC-1~AC-8 的给定/当/则场景
  - 注：本 Story 沿用 Story 2-2a 的纯 pytest 验收测试风格，`.feature` 文件为行为文档，实际断言逻辑在 `.py` 中用纯 pytest 测试类实现
- [ ] Subtask 0.6: 编写验收测试实现 `tests/acceptance/test_acceptance_document_parse_extended.py`
  - 按 AC 分组（TestAC1PPTX ~ TestAC8Composite），每个测试类包含多个 `test_*` 方法
  - 注：不使用 `@pytest.mark.asyncio`，不使用 `pytest-bdd` 装饰器，参考 2-2a `test_acceptance_document_parse.py` 模式
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）
- [ ] Subtask 0.8: 扩展端口契约测试 `tests/contracts/test_port_contract_document_parser.py` 覆盖新解析器

**完成标准/Definition of Done:**
- [ ] 规范复用确认完毕（无新增端口/事件/值对象）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: PPTX 解析器实现

**关联 AC:** AC-1

#### TDD 循环 A：PptxParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_pptx_parser.py`（文本/表格/备注/空文件/旧版 PPT 拒绝） |
| 🟢 绿 | 实现 `pptx_parser.py`（`python-pptx` 提取幻灯片内容） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 PptxParser 失败测试
  - 测试正常 PPTX 文本提取（多幻灯片）
  - 测试表格提取（幻灯片内嵌表格）
  - 测试备注提取
  - 测试空 PPTX 返回 failed
  - 测试旧版 PPT MIME 返回友好拒绝
- [ ] Subtask 1.2: 🟢 绿 — 实现 PptxParser
  - 使用 `python-pptx.Presentation` 逐幻灯片遍历
  - 提取 `shape.text`（文本）、`shape.has_table`（表格）、`slide.notes_slide`（备注）
  - 幻灯片编号作为 `page_number`
- [ ] Subtask 1.3: 🔄 重构 — 优化 PptxParser 代码

**完成标准/Definition of Done:**
- [ ] PptxParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 2: Excel 解析器实现

**关联 AC:** AC-2

#### TDD 循环 A：ExcelParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_excel_parser.py`（多 Sheet/空 Sheet/大文件/公式/旧版 XLS） |
| 🟢 绿 | 实现 `excel_parser.py`（`openpyxl` + 可选 `xlrd`） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 ExcelParser 失败测试
  - 测试多 Sheet 文档解析（每个 Sheet 独立 ParsedTable）
  - 测试空 Sheet 跳过
  - 测试公式单元格返回计算值
  - 测试空文件返回 failed
  - 测试旧版 XLS MIME 处理策略
- [ ] Subtask 2.2: 🟢 绿 — 实现 ExcelParser
  - 使用 `openpyxl.load_workbook(read_only=True, data_only=True)` 降低内存
  - 逐 Sheet 遍历，空 Sheet 跳过
  - 每行转为 `list[str]`，None 转为空字符串
- [ ] Subtask 2.3: 🔄 重构 — 优化 ExcelParser 代码

**完成标准/Definition of Done:**
- [ ] ExcelParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 3: CSV 解析器实现

**关联 AC:** AC-3

#### TDD 循环 A：CSVParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_csv_parser.py`（分隔符检测/编码检测/空文件/大文件） |
| 🟢 绿 | 实现 `csv_parser.py`（标准库 csv + csv.Sniffer） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 CSVParser 失败测试
  - 测试标准 CSV 解析
  - 测试分号/Tab 分隔符自动检测
  - 测试 GBK 编码自动检测
  - 测试空文件返回 failed
  - 测试超大 CSV 分块处理
- [ ] Subtask 3.2: 🟢 绿 — 实现 CSVParser
  - **重构 TextParser 的编码检测为共享工具：** 将 `TextParser._detect_and_decode`（私有方法）提取为 `_limits.py` 或新文件 `_encoding.py` 中的模块级函数 `detect_and_decode(raw_bytes) -> str`，CSVParser 和 TextParser 均通过 import 复用（避免违反私有方法调用惯例）
  - 使用 `csv.Sniffer` 自动检测分隔符
  - 输出单页结构，包含一个 ParsedTable
  - **超大文件分块：** 文件 >50MB 时按 10MB 增量逐块读取，每块生成独立 `ParsedTable`（共享同一 `ParsedPage`），使用 `csv.reader` 的 `line_num` 跟踪行偏移，块边界处理不完整行（缓冲至下一块）
- [ ] Subtask 3.3: 🔄 重构 — 优化 CSVParser 代码

**完成标准/Definition of Done:**
- [ ] CSVParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 4: 图像解析器实现（含 OCR）

**关联 AC:** AC-4

#### TDD 循环 A：ImageParser（元数据 + OCR）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_image_parser.py`（元数据/OCR/置信度/GIF/Tesseract 不可用降级） |
| 🟢 绿 | 实现 `image_parser.py`（Pillow + pytesseract） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 编写 ImageParser 失败测试
  - 测试 JPEG 元数据提取（format/size/mode）
  - 测试 PNG OCR 文本提取
  - 测试 OCR 置信度评分
  - 测试 GIF 仅处理第一帧
  - 测试 Tesseract 不可用时优雅降级（mock pytesseract 抛异常）
  - 测试纯图形图像（无文本内容）
- [ ] Subtask 4.2: 🟢 绿 — 实现 ImageParser
  - 使用 `PIL.Image.open()` 提取元数据
  - 使用 `pytesseract.image_to_string()` + `image_to_data()` 提取文本和置信度
  - try/except 包裹 OCR 调用，不可用时记录警告并跳过
  - GIF 使用 `img.seek(0)` 确保仅处理第一帧
- [ ] Subtask 4.3: 🔄 重构 — 优化 ImageParser 代码

**完成标准/Definition of Done:**
- [ ] ImageParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 5: HTML 解析器实现

**关联 AC:** AC-5

#### TDD 循环 A：HTMLParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_html_parser.py`（文本/表格/标题/编码/空页面） |
| 🟢 绿 | 实现 `html_parser.py`（BeautifulSoup + lxml） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 5.1: 🔴 红 — 编写 HTMLParser 失败测试
  - 测试纯文本 HTML 提取
  - 测试表格提取（`<table>` → ParsedTable）
  - 测试标题层级识别（h1-h6 → metadata.style）
  - 测试编码自动检测
  - 测试空页面返回 failed
- [ ] Subtask 5.2: 🟢 绿 — 实现 HTMLParser
  - 使用 `BeautifulSoup(html, 'lxml')` 解析
  - `get_text(separator='\n', strip=True)` 提取文本
  - `find_all('table')` → 提取 `<tr>/<td>/<th>` 为 ParsedTable
  - `find_all(['h1'-'h6'])` → 提取标题和层级
- [ ] Subtask 5.3: 🔄 重构 — 优化 HTMLParser 代码

**完成标准/Definition of Done:**
- [ ] HTMLParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 6: Markdown 解析器实现

**关联 AC:** AC-6

#### TDD 循环 A：MarkdownParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_markdown_parser.py`（标题/段落/表格/代码块） |
| 🟢 绿 | 实现 `markdown_parser.py`（标准库 + 正则） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 6.1: 🔴 红 — 编写 MarkdownParser 失败测试
  - 测试标题层级识别（`#` → h1，`##` → h2）
  - 测试段落按空行分割
  - 测试 Markdown 表格提取（`| col | col |` 格式）
  - 测试代码块保留（` ``` ` 围栏）
  - 测试空文件返回 failed
- [ ] Subtask 6.2: 🟢 绿 — 实现 MarkdownParser
  - 正则匹配标题 `^#+\s+.+$`
  - 按连续空行分割段落
  - 正则识别 Markdown 表格行 `^\|.+\|$`
    - 额外过滤分隔符行（`^\|[\s:-]+\|$`），避免 `|---|---|` 被当作数据行
  - 代码块内容原样保留
- [ ] Subtask 6.3: 🔄 重构 — 优化 MarkdownParser 代码

**完成标准/Definition of Done:**
- [ ] MarkdownParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 7: RTF 解析器实现

**关联 AC:** AC-7

#### TDD 循环 A：RTFParser

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_rtf_parser.py`（文本提取/库不可用降级/空文件） |
| 🟢 绿 | 实现 `rtf_parser.py`（`striprtf` 或标准库降级） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 7.1: 🔴 红 — 编写 RTFParser 失败测试
  - 测试 RTF 纯文本提取
  - 测试 `striprtf` 不可用时优雅降级（mock ImportError）
  - 测试空 RTF 返回 failed
- [ ] Subtask 7.2: 🟢 绿 — 实现 RTFParser
  - **前置步骤：** `poetry add striprtf` 安装 RTF 解析库
  - `try: from striprtf.striprtf import rtf_to_text` 提取纯文本
  - `except ImportError:` 返回 failed（建议转换为 DOCX）
- [ ] Subtask 7.3: 🔄 重构 — 优化 RTFParser 代码

**完成标准/Definition of Done:**
- [ ] RTFParser 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥75%

---

### Task 8: CompositeDocumentParser 扩展 + 集成测试

**关联 AC:** AC-8
**前置依赖:** Task 1-7 必须完成（所有新解析器类必须存在于 `src/infrastructure/external_services/document_parsing/` 中）

> ⚠️ **本 Task 包含 TDD 循环（组合解析器扩展） + 验证阶段（集成测试）**

#### TDD 循环 A：CompositeDocumentParser 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_composite_parser.py` 扩展测试（新 MIME 路由 + 不支持格式） |
| 🟢 绿 | 扩展 `composite_parser.py`（注册新解析器） |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 8.1: 🔴 红 — 编写 CompositeParser 扩展测试
  - 测试所有新 MIME 类型路由正确
  - 测试不支持的 MIME 返回 `ParsedDocument(parse_status="failed")` 并带明确错误消息（不抛异常）
  - 测试注册到 Composition Root 后 DI 解析正确
- [ ] Subtask 8.2: 🟢 绿 — 扩展 CompositeDocumentParser 和相关基础设施
  - 新增 MIME 类型常量（PPTX/PPT/XLSX/XLS/CSV/JPEG/PNG/GIF/HTML/MD/RTF）
  - 构造函数注入新解析器
  - 更新 `composition_root.py` 的 `document_parser` 注册工厂 lambda
    - **PPT MIME 路由参照 DOC 模式：** `application/vnd.ms-powerpoint` → `PptxParser()`，与 `application/msword` → `WordParser()` 一致，PptxParser 内部检查 MIME 类型并返回友好拒绝
    - **XLS MIME 路由同理：** `application/vnd.ms-excel` → `ExcelParser()`，ExcelParser 内部检查 MIME 类型并返回友好拒绝
  - **扩展 `_limits.py`：** 为每个新格式添加文件大小限制常量
    ```python
    MAX_PPTX_BYTES: int = 100 * 1024 * 1024   # PPTX 100MB
    MAX_XLSX_BYTES: int = 50 * 1024 * 1024    # XLSX 50MB
    MAX_CSV_BYTES: int = 100 * 1024 * 1024    # CSV 100MB（含 50MB 分块阈值）
    MAX_IMAGE_BYTES: int = 50 * 1024 * 1024   # 图像 50MB
    MAX_HTML_BYTES: int = 10 * 1024 * 1024    # HTML 10MB
    MAX_MD_BYTES: int = 10 * 1024 * 1024      # Markdown 10MB
    MAX_RTF_BYTES: int = 50 * 1024 * 1024     # RTF 50MB
    ```
  - **扩展 `_ALLOWED_TEMP_SUFFIXES`：** 将 `document_parsing_service.py` 中的后缀白名单从
    ```python
    frozenset({".pdf", ".docx", ".txt", ".tmp"})
    ```
    扩展为：
    ```python
    frozenset({".pdf", ".docx", ".txt", ".tmp",
               ".pptx", ".ppt", ".xlsx", ".xls", ".csv",
               ".jpg", ".jpeg", ".png", ".gif",
               ".html", ".htm", ".md", ".rtf"})
    ```
- [ ] Subtask 8.3: 🔄 重构 — 优化组合解析器代码

#### 验证阶段：集成测试确认（非 TDD 循环）

> ⚠️ **说明：** 集成测试验证 Task 1-7 已完成实现的解析器的端到端流程。此时所有解析器代码已实现完毕，不遵循 TDD 红→绿→重构循环（被测试实现已存在）。集成测试遵循真实基础设施验证模式：编写测试 → 运行验证 → 修复集成问题 → 确认通过。

| 阶段 | 动作 |
|------|------|
| 编写 | 编写 `test_document_parse_extended_integration.py`（MinIO→解析→事件） |
| 验证 | 运行集成测试，标记集成问题 |
| 修复 | 修复解析器间接口不匹配或路由错误 |
| 确认 | 确认所有集成测试通过 |

- [ ] Subtask 8.4: 🔴 红 — 编写集成测试
  - 测试 PPTX 完整解析流程（MinIO retrieve → parse → save → event）
  - 测试 XLSX 完整解析流程
  - 测试图像 OCR 完整解析流程
  - 测试并发解析 ≥10（`asyncio.gather()` 并发调用 `parse_document`）
  - 测试非 OCR 格式解析性能 P95 < 500ms（OCR 格式 P95 < 5s，见 AC-8）
- [ ] Subtask 8.5: 🟢 绿 — 确认集成测试通过
- [ ] Subtask 8.6: 🔄 重构 — 优化集成测试代码

**完成标准/Definition of Done:**
- [ ] CompositeDocumentParser 扩展完成
- [ ] 所有 MIME 路由正确
- [ ] 集成测试全部通过
- [ ] 并发解析 ≥10
- [ ] 非 OCR 格式 P95 < 500ms，OCR 格式 P95 < 5s

---

### Task 9: SDD 架构约束验证测试

**关联 AC:** AC-1 ~ AC-8
**前置依赖:** Task 1-8 必须完成（架构验证测试 import 所有解析器模块，代码不存在时触发 `ModuleNotFoundError`）

> **性质说明：** 本 Task 是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。
> 验证 Task 1-8 创建的代码是否符合六边形架构规则。

#### 架构验证测试实现

- [ ] Subtask 9.1: 扩展 `tests/unit/architecture/test_arch_document_parser.py`
  - 在 `TestInfrastructureLayerPlacement` 中为 7 个新解析器各添加 `test_*_parser_in_infrastructure` 方法
  - 在 `TestDependencyDirection` 中添加新解析器协议满足性验证
  - 避免创建新文件（现有 102 行架构测试可扩展），仅当文件过大时才拆分为 `extended` 文件
- [ ] Subtask 9.2: 验证所有新解析器位于 `src/infrastructure/` 而非 `src/domain/`
- [ ] Subtask 9.3: 验证新解析器实现 `DocumentParserPort` 协议（`isinstance` 检查）
- [ ] Subtask 9.4: 验证领域层无新增外部依赖（import-linter 校验）
- [ ] Subtask 9.5: 验证依赖方向正确（infrastructure → domain，无反向依赖）
- [ ] Subtask 9.6: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-8
**前置依赖:** Task 1-9 必须完成（验收测试隐式验证所有解析器代码和组合解析器注册的存在性）

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_document_parse_extended.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `test_acceptance_document_parse_extended.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 10.1: 人工确认 `src` 交付物完成清单（非 pytest，为 Checklist）
  - 7 个新解析器文件存在且代码可用
  - composite_parser.py 已扩展 MIME 路由
  - composition_root.py 已更新 document_parser 注册工厂
  - _ALLOWED_TEMP_SUFFIXES 已扩展（含所有新格式后缀）
  - **_limits.py 已扩展**（含所有新格式大小限制常量）
- [ ] Subtask 10.2: 人工确认测试交付物完成清单（非 pytest，为 Checklist）
  - 7 个解析器单元测试文件存在
  - 组合解析器扩展测试覆盖新 MIME 路由
  - 集成测试验证完整端到端流程
  - 架构约束测试覆盖所有 11 个解析器（4 个原有 + 7 个新增）
  - 验收测试覆盖所有 AC 场景
- [ ] Subtask 10.3: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验
  - 文件存在性由编译/导入隐式验证（`import xxx_parser` 失败即文件缺失）

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] 测试目录完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters），组合模式（CompositeDocumentParser MIME 路由）
- **设计约束:** 领域层零依赖、依赖方向严格、端口统一注册、Composition Root 装配
- **接口治理:** 统一端口注册、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+ / python-pptx ^1.0 / openpyxl ^3.1.2 / Pillow ^12.1.1 / pytesseract ^0.3.10 / beautifulsoup4 (间接依赖) / lxml (间接依赖)

### 关键架构决策

**来源:** Story 2-2a 设计决策（复用）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **组合模式 + MIME 路由（选中）** | 扩展性强、单一职责、易于测试 | 新格式需手动注册 | ✅ 9/10 |
| 工厂方法模式 | 自动发现 | 过度设计、隐式路由 | 6/10 |
| unstructured.io 统一接口 | 全格式统一 | 重依赖（torch 等）、部署复杂 | 5/10 |

**依赖库选型决策：**

| 格式 | 选型 | 理由 |
|------|------|------|
| PPTX | `python-pptx` | 已安装，纯 Python，支持幻灯片/表格/备注 |
| PPT | 返回不支持 | 旧格式，需 LibreOffice 转换，MVP 不引入 |
| XLSX | `openpyxl` (read_only=True) | 已安装，内存友好，支持公式计算值 |
| XLS | 返回不支持 | 旧格式，xlrd 需额外依赖且处于维护模式，与 PPT→PPTX 策略一致 |
| CSV | 标准库 `csv` + `csv.Sniffer` | 零依赖，功能足够 |
| 图像 | `Pillow` + `pytesseract` | 已安装，元数据+OCR 双能力 |
| HTML | `BeautifulSoup` + `lxml` | 间接已安装，性能最佳组合 |
| Markdown | 标准库正则 | 零依赖，标题/段落/表格正则足够 |
| RTF | `striprtf` | 轻量，需新增依赖；不可用时降级 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── ports/
│   │   └── document_parser.py           # DocumentParserPort Protocol（复用 2-2a）
│   ├── value_objects/
│   │   ├── parsed_document.py           # 解析结果值对象（复用 2-2a）
│   │   └── document_format.py           # 17 种格式 MIME 映射（复用 2-1）
│   ├── entities/
│   │   └── document.py                  # Document 实体（复用 2-1）
│   └── events/
│       └── document_events.py           # DocumentUploaded/Processed 事件（复用 2-1/2-2a）
│
├── application/
│   └── services/
│       └── document_parsing_service.py  # 解析编排服务（修改：扩展 _ALLOWED_TEMP_SUFFIXES）
│
├── infrastructure/
│   └── external_services/
│       └── document_parsing/
│           ├── pdf_parser.py            # PDF 解析器（复用 2-2a）
│           ├── word_parser.py           # Word 解析器（复用 2-2a）
│           ├── text_parser.py           # TXT 解析器（复用 2-2a）
│           ├── pptx_parser.py           # ★ 新增：PPTX 解析器
│           ├── excel_parser.py          # ★ 新增：Excel 解析器
│           ├── csv_parser.py            # ★ 新增：CSV 解析器
│           ├── image_parser.py          # ★ 新增：图像+OCR 解析器
│           ├── html_parser.py           # ★ 新增：HTML 解析器
│           ├── markdown_parser.py       # ★ 新增：Markdown 解析器
│           ├── rtf_parser.py            # ★ 新增：RTF 解析器
│           └── composite_parser.py      # 修改：扩展 MIME 路由
│
├── composition_root.py                  # 修改：扩展 document_parser 注册工厂
│
└── tests/
    ├── unit/infrastructure/external_services/document_parsing/
    │   ├── test_pptx_parser.py          # ★ 新增
    │   ├── test_excel_parser.py         # ★ 新增
    │   ├── test_csv_parser.py           # ★ 新增
    │   ├── test_image_parser.py         # ★ 新增
    │   ├── test_html_parser.py          # ★ 新增
    │   ├── test_markdown_parser.py      # ★ 新增
    │   ├── test_rtf_parser.py           # ★ 新增
    │   └── test_composite_parser.py     # 扩展（覆盖新 MIME 路由）
    ├── integration/
    │   └── test_document_parse_extended_integration.py  # ★ 新增
    ├── unit/architecture/
    │   └── test_arch_document_parser.py        # 扩展（原有 2-2a 文件，新增 7 个解析器验证方法）
    ├── contracts/
    │   └── test_port_contract_document_parser.py        # 扩展
    ├── acceptance/
    │   ├── test_acceptance_document_parse_extended.feature  # ★ 新增
    │   └── test_acceptance_document_parse_extended.py       # ★ 新增
```

> **Fixture 策略说明：** 本 Story 沿用 Story 2-2a 的编程式 fixture 生成模式，不使用静态 fixture 文件。
> 测试文件内定义 `_create_*()` 工厂函数，通过 `tempfile.NamedTemporaryFile`
> 即时生成所需格式的临时文件，使用 `try/finally: os.unlink()` 清理。
> 各格式生成方式：PPTX→`python-pptx.Presentation()` / XLSX→`openpyxl.Workbook()` / CSV→`tempfile`+文本写入 /
> PNG→`PIL.Image.new()` / HTML/MD/RTF→`tempfile`+文本写入。
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 2-2a-document-parsing-basic-formats](./2-2a-document-parsing-basic-formats.md)

**关键学习/Key Learnings:**
1. **`to_dict()` 序列化模式** — `ParsedDocument` 通过 `to_dict()` 转换为 dict，传入事件 payload 和仓储 JSONB
2. **DI 注册延迟加载陷阱** — impl 字符串拼写错误不立即报错，需契约测试覆盖
3. **事件双注册** — 本 Story 不新增事件，无需修改 `event_channels.yaml`
4. **`_ALLOWED_TEMP_SUFFIXES` 白名单** — 临时文件后缀必须在此白名单内，新格式需扩展
5. **`asyncio.to_thread()` + `document_id` 覆盖模式** — CPU 密集型解析操作通过 `asyncio.to_thread()` 在线程池中同步执行（解析器自身为同步方法，不在 `parse()` 中使用 `await`）。解析器生成的 `document_id`（`uuid4()`）会被 `DocumentParsingService` 第 122-123 行通过 `dataclasses.replace(parsed_doc, document_id=str(document.document_id))` 覆盖为真实实体 ID。解析器无需关心 ID 一致性。
6. **`repo.save()` 全量更新** — 项目中所有仓储端口使用 `save()` 而非 `update_*()` 方法
7. **MinIO 桥接模式** — `retrieve()` 返回 `AsyncIterator[bytes]`，需写入临时文件后解析
8. **Prefect 任务 `retries=2`** — 替换实现需保留重试配置

**应用到本故事/Applied to This Story:**
- [ ] 新解析器遵循 `DocumentParserPort.parse(file_path, mime_type)` 签名
- [ ] `_ALLOWED_TEMP_SUFFIXES` 扩展覆盖新格式后缀
- [ ] Composition Root lambda 工厂正确注入所有新解析器
- [ ] 单元测试使用本地 fixture 文件（非 MinIO 下载）
- [ ] 集成测试使用 TestTenant 进行租户隔离
- [ ] OCR 测试 mock pytesseract 以确保无 Tesseract 环境也可测试

### OCR 实现注意事项

**来源:** 架构文档 + 代码调研

- `pytesseract` 是 Tesseract-OCR 的 Python 包装器，**需要系统安装 Tesseract-OCR 二进制**
- 中文支持需要 `tesseract-ocr-chi-sim` 语言包
- 推荐 OCR 前预处理：灰度化（`img.convert('L')`）
- `pytesseract.image_to_data()` 返回置信度信息，可用于填充 `confidence` 字段
- **Tesseract 未安装时优雅降级**：catch `TesseractNotFoundError`，记录警告日志，返回元数据但 OCR 文本为空

### 合规性与安全性注意事项

- **临时文件清理：** 生产环境中临时文件清理由 `DocumentParsingService.parse_document()` 的 `finally` 块保障（`os.unlink(temp_path)`），不依赖测试代码的 `try/finally`。本 Story 新增解析器不改变此清理逻辑。
- **敏感数据处理：** 本 Story 仅实现文档解析与内容提取，不涉及 PII 脱敏或内容扫描。解析结果存入 `Document.metadata["parse_result"]` JSONB 字段，下游消费者负责访问控制与数据保护。
- **无新增事件/合规审计点：** 本 Story 不新增领域事件，沿用 2-2a 已有的 `DocumentProcessed` 事件和审计追踪机制。

### 第三方依赖状态

| 库 | 版本 | 安装状态 | 用途 |
|---|------|---------|------|
| python-pptx | ^1.0 | 已安装 | PPTX 解析 |
| openpyxl | ^3.1.2 | 已安装 | XLSX 解析 |
| Pillow | ^12.1.1 | 已安装 | 图像处理 |
| pytesseract | ^0.3.10 | 已安装 | OCR |
| beautifulsoup4 | ^4.12 | **间接依赖（已安装，建议提升为直接依赖）** | HTML 解析 |
| lxml | ^6.0 | **间接依赖（已安装，建议提升为直接依赖）** | HTML/XML 解析 |
| pandas | ^2.1.3 | 已安装（可选使用） | CSV/Excel 数据处理 |
| striprtf | — | **未安装** | RTF 解析（需新增 `poetry add striprtf`） |

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.1 |
| **Version** | create-story workflow v2.7.0 |
| **Execution Date** | 2026-06-01 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-2a-document-parsing-basic-formats.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（Story 2-2a 8 项关键学习）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 第三方依赖调研完成（python-pptx/openpyxl/Pillow/pytesseract/BS4/lxml 已安装）
- [x] 现有代码实现调研完成（DocumentParserPort/ParsedDocument/CompositeDocumentParser）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-2b-document-parsing-extended-formats.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/external_services/document_parsing/pptx_parser.py` — PPTX 解析器
- `src/infrastructure/external_services/document_parsing/excel_parser.py` — Excel 解析器
- `src/infrastructure/external_services/document_parsing/csv_parser.py` — CSV 解析器
- `src/infrastructure/external_services/document_parsing/image_parser.py` — 图像+OCR 解析器
- `src/infrastructure/external_services/document_parsing/html_parser.py` — HTML 解析器
- `src/infrastructure/external_services/document_parsing/markdown_parser.py` — Markdown 解析器
- `src/infrastructure/external_services/document_parsing/rtf_parser.py` — RTF 解析器
- `tests/unit/infrastructure/external_services/document_parsing/test_pptx_parser.py` — PPTX 单元测试
- `tests/unit/infrastructure/external_services/document_parsing/test_excel_parser.py` — Excel 单元测试
- `tests/unit/infrastructure/external_services/document_parsing/test_csv_parser.py` — CSV 单元测试
- `tests/unit/infrastructure/external_services/document_parsing/test_image_parser.py` — Image 单元测试
- `tests/unit/infrastructure/external_services/document_parsing/test_html_parser.py` — HTML 单元测试
- `tests/unit/infrastructure/external_services/document_parsing/test_markdown_parser.py` — Markdown 单元测试
- `tests/unit/infrastructure/external_services/document_parsing/test_rtf_parser.py` — RTF 单元测试
- `tests/unit/architecture/test_arch_document_parser.py` — 架构约束测试（扩展，非新建）
- `tests/integration/test_document_parse_extended_integration.py` — 集成测试
- `tests/acceptance/test_acceptance_document_parse_extended.feature` — Gherkin 验收测试
- `tests/acceptance/test_acceptance_document_parse_extended.py` — BDD 步骤实现

**待修改的文件/To Be Modified:**
- `src/infrastructure/external_services/document_parsing/_limits.py` — 扩展新格式文件大小限制常量
- `src/infrastructure/external_services/document_parsing/composite_parser.py` — 扩展 MIME 路由映射
- `src/composition_root.py` — 扩展 document_parser 注册工厂 lambda
- `src/application/services/document_parsing_service.py` — 扩展 `_ALLOWED_TEMP_SUFFIXES`
- `tests/contracts/test_port_contract_document_parser.py` — 扩展端口契约测试
- `tests/unit/infrastructure/external_services/document_parsing/test_composite_parser.py` — 扩展测试

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.2b |
| **Story Key** | 2-2b-document-parsing-extended-formats |
| **File** | `_bmad-output/implementation-artifacts/stories/2-2b-document-parsing-extended-formats.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P1-2b（V1，扩展格式支持） |
| **覆盖 FR** | FR-DM-02（文档解析与内容提取 — 扩展格式部分） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（11 个 Task：Task 0-10）
2. [x] All acceptance criteria specified 所有验收标准已定义（8 个 AC）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（8 项）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | AC-8 未注册 MIME 类型返回 `ValueError` — 与实际 CompositeDocumentParser 行为矛盾（实际返回 `ParsedDocument(parse_status=failed)`） | P0 | 修正 AC-8 和 Subtask 8.1，改为 "返回 `parse_status=failed` 的 `ParsedDocument`（不抛异常）" |
| 2 | AC-8 解析性能 P95 < 500ms 与 OCR（pytesseract 2-5s）不可调和 | P0 | 分拆为非 OCR 格式 P95 < 500ms + OCR 格式 P95 < 5s |
| 3 | XLS 格式处理策略模糊（"用 xlrd 或返回拒绝"），xlrd 不在依赖中 | P0 | 确定为 "返回友好拒绝消息，建议转换 XLSX"（与 PPT→PPTX 策略一致） |
| 4 | beautifulsoup4/lxml 标注为 "间接依赖已安装"，但非直接依赖存在移除风险 | P0 | 更新状态为 "间接依赖（建议提升为直接依赖）"，标注版本号 |
| 5 | striprtf 缺失 `poetry add` 步骤 — Task 7 无依赖安装前置 | P0 | Subtask 7.2 新增前置步骤 `poetry add striprtf` |
| 6 | 架构文档引用路径不存在（`../../_bmad-output/planning-artifacts/architecture.md`） | P0 | 修正为 `../../../docs/architecture/architecture.md` |
| 7 | "关键路径覆盖率 100%" 无 PRD/Epic 源头文档依据 | P0 | 替换为 "端口契约测试覆盖率 100%"（PRD 有依据） |
| 8 | 7 个静态 fixture 文件策略与 2-2a 编程式生成模式不一致，`tests/fixtures/documents/` 目录不存在 | P0 | 删除所有静态 fixture 引用，替换为编程式 `_create_*()` 工厂函数说明 |
| 9 | `_limits.py` 和 `_ALLOWED_TEMP_SUFFIXES` 扩展无具体内容 | P0 | Subtask 8.2 新增完整的大小限制常量和后缀白名单列表 |
| 10 | 验收测试 BDD 风格不明确（pytest-bdd vs 纯 pytest）— 与 2-2a 实际实现矛盾 | P0 | 明确采用纯 pytest 测试类风格，`.feature` 为行为文档，注释说明 |
| 11 | Task 8 集成测试错误标记为 "TDD 循环"（被测试实现已存在，无 "绿阶段" 代码可写） | P0 | 重命名为 "验证阶段：集成测试确认（非 TDD 循环）"，调整阶段描述 |
| 12 | Task 9 新建架构测试文件 vs 扩展现有文件歧义 | P0 | 改为 "扩展 `test_arch_document_parser.py`"，明确添加新解析器验证方法 |
| 13 | Task 10 文件存在性验证放入 pytest 验收测试不合适（2-2a 无此模式） | P0 | 改为人工 Checklist，文件存在性由编译/导入隐式验证 |
| 14 | `_limits.py` 和 `_ALLOWED_TEMP_SUFFIXES` 扩展分散在多处但无专属 Task/Subtask | P0 | 集中于 Subtask 8.2，显式列出所有新增常量和后缀 |
| 15 | 端口版本 `v1.0.0` vs `v1.1.0` 文档/代码/测试三方不一致 | P1 | 文档标注 `v1.0.0→v1.1.0`，明确需同步更新 composition_root.py 和 contract test |
| 16 | ParsedTable 无 sheet_name 字段 — AC-2 要求存储 sheet 名称 | P1 | 通过 `ParsedPage.metadata["sheet_name"]` 存储（因 ParsedTable 无独立 metadata 字段） |
| 17 | CSV 超大文件分块与 TXT 直接拒绝策略不一致 | P1 | 添加注释说明 "CSV 行级结构天然支持分块，与 TXT 纯文本不同" |
| 18 | **R2** `ParsedPage.metadata` 字段不存在（R1 #16 修复引入回归），无法存储 sheet_name | P0 | 改为向 `ParsedTable` 新增 `metadata` 字段（参照 `ParsedElement.metadata`），AC-2 和 SDD 数据模型同步更新 |
| 19 | **R2** BDD 术语残留 7+ 处引用与 "纯 pytest 风格" 声明矛盾 | P0 | 保留核心约束说明，清理测试分类表和 Task 描述中的 BDD 步骤实现残余引用 |
| 20 | **R2** Subtask 8.1 仍写 "返回 ValueError"（R1 遗漏） | P0 | 修正为 "返回 `ParsedDocument(parse_status=failed)` 并带明确错误消息" |
| 21 | **R2** CSV 编码检测顺序文档写 GB18030→GBK，实际代码是 GBK→GB18030 | P1 | 修正顺序为 UTF-8→GBK→GB18030，说明 GBK 是 GB18030 子集 |
| 22 | **R2** `TextParser._detect_and_decode` 是私有实例方法，CSVParser 无法直接复用 | P1 | Task 3 新增重构步骤：提取为模块级共享函数 |
| 23 | **R2** Markdown 表格 regex `^\|.+\|$` 匹配分隔符行（`|---|---|`），无过滤策略 | P1 | 新增额外过滤 `^\|[\s:-]+\|$`，排除分隔符行 |
| 24 | **R2** AC-4 图像 `images` 数组的 `ParsedElement` 内容格式未定义 | P1 | 明确 content="" 存空字符串，metadata 存 format/width/height/mode |
| 25 | **R2** PPT/XLS 旧格式 MIME 路由注册模式未在 Task 8 显式说明 | P1 | Subtask 8.2 新增参照 WordParser/DOC 模式的注释 |
| 26 | **R2** `document_id` 覆盖模式未在学习经验中记录 | P1 | 扩展现有 Lesson 5，添加 dataclasses.replace 覆盖模式说明 |
| 27 | **R2** Task 8/9/10 缺少前置依赖声明 | P1 | 每个 Task 新增 `**前置依赖:** Task X-Y 必须完成` 声明 |
| 28 | **R2** TDD 周期粒度过粗（每个解析器 1 个循环 vs 2-2a 实际 PDF 8 个测试类 6 维度） | P1 | 标注建议每个解析器至少 3 个 TDD 子循环（基本/边界/限制） |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** —
**审查模式:** —

#### 需决策 Decision Needed

- — （待代码审查）

#### 已修复 Patch

- — （待代码审查）

#### 已推迟 Defer

- — （待代码审查）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-06-01
**最后更新/Last Updated:** 2026-06-02
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 Story 2-2a 架构基础，7 个新解析器 + 组合解析器扩展）
- v1.1.0: 三轮文档审查修复（R1 17项 + R2 11项 + R3-5 10项：覆盖率目标补全、BDD术语清理、架构测试统一、ParsedTable metadata、SDD引用修正、合规性说明）
