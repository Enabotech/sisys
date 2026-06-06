# Story 2-5: OCR 解析（扫描件/图像 PDF）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统对扫描件或图像 PDF 进行 OCR 解析（中/英），提取置信度并标注,
**So that** 历史纸质文档和扫描件可被系统处理。

### 业务价值

Epic 2 文档与数据管理的 P0 Story（FR-DM-05），补齐文档处理流水线中扫描件/图像 PDF 的处理能力。

在 Story 2-2a（基础格式解析）、Story 2-3（版面信息保留）和 Story 2-4（表格语义提取）完成后，
现有 PDFParser（基于 pypdf）仅能提取原生文本层的 PDF 文字，对于扫描件或图片型 PDF（页面无文本层），
`page.extract_text()` 返回空字符串，导致解析结果中 `texts=[]`——这些页面成为知识盲区。

本 Story 引入 OCR 引擎作为 PDF 解析的降级增强通道：当 PDFParser 检测到某页文本为空时，
通过已有的 `PdfPageRenderer`（pypdfium2）将页面渲染为图像，再由 OCR 引擎（pytesseract）识别文字，
输出结构化 `ParsedElement` 列表（含 text、confidence、metadata）。对单张图像文件（JPEG/PNG/GIF），
扩展现有 `ImageParser` 的 OCR 结果以输出更完整的置信度信息。

**核心假设：** MVP 阶段 OCR 聚焦于中英双语识别（`chi_sim+eng`），复用已有 pytesseract 依赖。
扫描页检测使用"文本提取为空"作为触发条件（不引入额外的图像分类模型）。
置信度 < 0.85 时自动标注 `needs_review=True`。多页 PDF 逐页独立 OCR，单页失败不影响其他页。

**非本 Story 范围：**
- 数学公式识别（LaTeX/MathML 双格式）→ Story 17.1（V2 P2）
- OCR 后版面检测（将 OCR 文本框与 DocLayNet 检测结果匹配）→ 后续 Story
- 手写体识别 → V2+
- 非中/英语言 OCR → V2+

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 扫描件 PDF 页面 OCR 识别

**Given** PDF 文档某页无文本层（pypdf `extract_text()` 返回空）
**When** 系统检测到该页为扫描页
**Then** 通过 `PdfPageRenderer` 渲染该页为图像
**And** 调用 OCR 引擎识别图像中的文字（中英双语）
**And** 识别结果写入该页 `texts` 列表（每个 `ParsedElement` 含 `content`/`confidence`/`metadata={"source": "ocr"}`）
**And** 有文本层的页面保持不变（不触发 OCR）
**And** 全页 OCR 置信度从 `pytesseract.image_to_data()` 的 word-level confidence 聚合为平均值

**验证标准/Validation Criteria:**
- [ ] 扫描页（空文本）→ OCR 识别，page.texts 非空
- [ ] 原生文本页（有文本）→ 跳过 OCR，page.texts 保持原值
- [ ] `ParsedElement.metadata["source"]` = `"ocr"`（区别于原生提取 `"text"`）
- [ ] `ParsedElement.metadata["needs_review"]` = `True` 当置信度 < 0.85
- [ ] OCR 结果 `ParsedElement.confidence` 值域 [0.0, 1.0]

### AC-2: 中英双语 OCR 支持

**Given** 扫描页包含中文和/或英文内容
**When** OCR 引擎执行识别
**Then** 正确识别中文字符（简体优先，支持繁体）
**And** 正确识别英文字符
**And** 混排页面同时识别中英文
**And** 中文识别准确率 ≥ 90%（抽样验证，≥18/20 页）
**And** 英文识别准确率 ≥ 95%（抽样验证，≥19/20 页）

**验证标准/Validation Criteria:**
- [ ] pytesseract 语言参数使用 `lang="chi_sim+eng"`
- [ ] 中文测试集：20 页中文扫描件/图片 PDF，≥18 页可识别主要文本
- [ ] 英文测试集：20 页英文扫描件/图片 PDF，≥19 页可识别主要文本
- [ ] 混排测试：中英混排页面两种文字均可识别

### AC-3: 图像文件 OCR 增强

**Given** 单张图像文件（JPEG/PNG/GIF，MIME: image/jpeg, image/png, image/gif）
**When** ImageParser 执行解析
**Then** OCR 结果 `ParsedElement` 包含完整 `confidence` 字段（从 word-level 聚合，值域 [0.0, 1.0]）
**And** `metadata` 包含 `source="ocr"` 和 `needs_review` 标记（置信度 < 0.85 时为 True）
**And** GIF 仅处理第一帧（保持现有行为）
**And** pytesseract 不可用时降级返回图像元数据（保持现有行为，不抛异常）

**验证标准/Validation Criteria:**
- [ ] 图像 OCR 结果 `ParsedElement.confidence` 为聚合 float（非硬编码 0.5）
- [ ] `needs_review` 标记与置信度阈值 0.85 联动
- [ ] 向后兼容：下游消费 `ParsedElement.content` 的代码不受影响
- [ ] MIME 类型为 `image/*` 时才执行 `ImageParser`（非 PDF）

### AC-4: 文档解析服务 OCR 编排集成

**Given** 文档解析服务（`DocumentParsingService`）已完成基础解析
**When** 文档 MIME 类型为 `application/pdf`
**Then** 调用 `_apply_ocr()` 方法对扫描页进行 OCR 增强
**And** OCR 引擎通过可选构造函数参数注入（`ocr_engine: OcrEnginePort | None = None`）
**And** 注入模式与 `layout_detector` 和 `table_extractor` 保持一致（Optional 参数 + 三级降级）
**And** OCR 仅处理 PDF 格式（`image/*` 由 `ImageParser` 直接处理，不经过此路径）

**验证标准/Validation Criteria:**
- [ ] `ocr_engine` 端口未注入（None）→ 跳过 OCR，保持不变
- [ ] `mime_type != "application/pdf"` → 跳过 OCR
- [ ] OCR 执行完成后，parsed_doc.pages 中扫描页 texts 已填充
- [ ] OCR 失败（单页）→ WARNING 日志 + 该页保持空 texts
- [ ] OCR 失败（全部页）→ WARNING 日志 + 返回原 parsed_doc
- [ ] OCR 不改变 `parse_status`（始终为 completed）

### AC-5: 容错与降级

**Given** OCR 可能因各种原因失败（pytesseract 不可用/渲染失败/内存不足）
**When** OCR 过程中发生错误
**Then** 逐页独立降级：单页 OCR 失败不影响其他页面
**And** 日志记录降级原因（WARNING 级别，含页码和异常摘要）
**And** OCR 失败页的 texts 保持为空列表（不抛异常，不阻断解析主流程）
**And** `parse_status` 不受影响（仍为 `"completed"`）
**And** 降级策略与 `_apply_layout_detection()` 和 `_apply_table_extraction()` 保持一致

**验证标准/Validation Criteria:**
- [ ] 逐页 try/except：第 1 页 OCR 失败不影响第 2 页
- [ ] pytesseract 未安装 → composition_root 降级 ocr_engine=None（优雅降级）
- [ ] 渲染失败（文件损坏）→ WARNING 日志 + 该页 texts=[]
- [ ] OCR 超时（单页 > 60s）→ WARNING 日志 + 该页 texts=[]
- [ ] OCR 不修改非 PDF 文档的解析结果

### AC-6: 性能要求

**Given** 扫描 PDF 有 N 页
**When** 系统执行 OCR
**Then** 单页 OCR 延迟 P95 < 5s（含渲染 + OCR）
**And** 多页 PDF 逐页顺序处理（避免并行 OCR 导致内存峰值）
**And** 渲染分辨率使用 150 DPI（与 layout_detector 共用 PdfPageRenderer 默认配置）
**And** OCR 总超时 = max（现有解析超时 300s，N × 5s），以较长者为准

**验证标准/Validation Criteria:**
- [ ] 单页 A4 扫描件（150 DPI 渲染 + OCR）< 5s（P95）
- [ ] 50 页扫描 PDF 全流程 < 300s（含解析 + OCR + 版面检测 + 表格提取）
- [ ] OCR 通过 `asyncio.to_thread()` 运行（不阻塞事件循环）
- [ ] 渲染图片内存及时释放（不在内存中累积）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 复用 `DocumentProcessed` 事件（Story 2-2a 已定义），**不新增事件** — OCR 结果通过 `parse_result` dict 中的 `pages[].texts[]` 传递
- [ ] 复用 `DocumentUploaded` 事件触发解析流程（不变）

#### 数据模型 (Data Models)
- [ ] **复用** 现有值对象（`src/domain/value_objects/parsed_document.py`）：
  - `ParsedElement`：`content` 存放 OCR 文本，`confidence` 存放 OCR 置信度，`metadata` 含 `source`/`needs_review`
  - `ParsedPage`：`texts` 存放 OCR 结果的 `ParsedElement` 列表
  - `ParsedDocument`：不变
  - 不新增值对象（OCR 结果直接映射到现有 `ParsedElement`）
- [ ] **可选新增** `OcrPageResult` 值对象（`src/domain/value_objects/ocr_result.py`）— 仅当 OCR 引擎需要返回比 `ParsedElement` 更丰富的中间结果时引入，否则使用现有 `ParsedElement`

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `OcrEnginePort` 端口契约（`src/domain/ports/ocr_engine.py`）：
  - `@runtime_checkable` + `Protocol`
  - `recognize(image_bytes: bytes, page_number: int) -> OcrPageResult`（或直接返回 `ParsedElement`）
  - 接收渲染后的页面图像字节，返回识别结果（文本 + 置信度 + 语言信息）
- [ ] **端口注册** — 在 `src/composition_root.py` 中调用 `register_port()` 注册 `ocr_engine` 端口
- [ ] **端口契约门禁**（`src/domain/ports/contract_gate.py`）：新端口变更通过兼容性检查
- [ ] **端口契约测试**（`tests/contracts/test_port_contract_ocr_engine.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称 `ocr_engine`、版本 `v1.0.0`、owner `epic-2`

**端口契约清单：**

| 端口名称 | 接口 | 实现 | 注册位置 | Lifetime | Version | Owner |
|---------|------|------|----------|----------|---------|-------|
| `ocr_engine` | `OcrEnginePort` | `TesseractOcrEngine` | domain/ports/ocr_engine.py | SCOPED | v1.0.0 | epic-2 |
| `pdf_page_renderer` | `PdfPageRendererPort` | `PdfPageRenderer` | domain/ports/pdf_page_renderer.py | SCOPED | v1.0.0（复用） | epic-2 |
| `document_parsing_service` | `DocumentParsingService` | — | application/services/ | SCOPED | v1.2.0→v1.3.0 | epic-2 |

> **版本升级说明：**
> - `document_parsing_service` v1.3.0：构造函数新增可选参数 `ocr_engine: OcrEnginePort | None = None`，编排逻辑增加 OCR 降级增强步骤（`_apply_ocr()`）。向后兼容（可选参数，默认 `None` 时跳过）。
> - `ocr_engine`：OCR 引擎，将渲染后的页面图像字节识别为文本，复用 `PdfPageRenderer` 进行页面渲染。
> - `PdfPageRenderer` 复用已有实现（Story 2-3），版本不变。

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 不新增领域异常。OCR 引擎的运行时异常在应用层通过降级策略处理（WARNING 日志 + 返回原始结果），不抛异常跨层传播。

- [ ] **不新增领域异常** — OCR 失败场景统一通过降级策略处理（与 `_apply_layout_detection()` / `_apply_table_extraction()` 一致）
- [ ] OCR 引擎初始化失败（pytesseract 未安装）由 composition_root 捕获为 `ImportError`，降级 ocr_engine=None
- [ ] OCR 运行时失败（渲染错误/识别超时）由 `_apply_ocr()` 捕获，WARNING 日志 + 保持原解析结果

#### API 契约 (API Contract)
- [x] 复用 `GET /api/v1/documents/{document_id}` 查询端点（不变）
- [x] 解析结果存储于 `Document.metadata["parse_result"]` JSONB 字段（不变，OCR 结果内含）
- [x] 复用 `POST /api/v1/documents` 上传端点（不变）

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
- 禁止导入：包括且不限于 pytesseract, pypdfium2, Pillow, pypdf, onnxruntime, numpy, fastapi, sqlalchemy 等

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_ocr.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_ocr.py`
- [ ] HAPPY PATH: 扫描 PDF 全部页面 OCR 识别（中文）
- [ ] HAPPY PATH: 扫描 PDF 全部页面 OCR 识别（英文）
- [ ] HAPPY PATH: 混合 PDF（前 2 页有文本层 + 后 2 页扫描页）— 仅扫描页触发 OCR
- [ ] HAPPY PATH: 单张 JPEG 图像 OCR（ImageParser 路径，置信度 + needs_review）
- [ ] EDGE CASE: 全部页面有文本层（OCR 完全不触发，无副作用）
- [ ] EDGE CASE: 全部页面为扫描页（每页都触发 OCR）
- [ ] EDGE CASE: 单页 OCR 失败（渲染失败/超时）→ 该页 texts=[]，其他页正常
- [ ] EDGE CASE: OCR 置信度 < 0.85 → needs_review=True
- [ ] EDGE CASE: OCR 置信度 ≥ 0.85 → needs_review=False
- [ ] EDGE CASE: ocr_engine 未注入（None）→ 跳过 OCR，解析结果不变
- [ ] EDGE CASE: pytesseract 未安装 → composition_root 降级，解析正常完成（无 OCR 增强）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

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
| **TDD 单元测试** | OcrEnginePort 端口 | Protocol 合规/类型检查/签名约束 | `test_ocr_engine_port.py` | Task 1 |
| **TDD 单元测试** | TesseractOcrEngine | OCR 识别/mock pytesseract/降级/逐页独立 | `test_tesseract_ocr_engine.py` | Task 2 |
| **TDD 单元测试** | ImageParser OCR 增强 | 置信度聚合/needs_review 标记/GIF 首帧 | `test_image_parser.py`（扩展） | Task 2 |
| **TDD 单元测试** | DocumentParsingService OCR 集成 | `_apply_ocr()` 编排/mock ocr_engine/降级 | `test_document_parsing_service.py`（扩展） | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_ocr.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_ocr.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_ocr.feature` | Task 5 |
| **TDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_ocr.py` | Task 5 |
| **TDD 契约测试** | 端口契约 / OcrEnginePort | 注册/版本/兼容性/实现解析 | `test_port_contract_ocr_engine.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖/端口在 domain | `test_arch_document_ocr.py` | Task 4 |
| **集成测试** | 端到端 OCR 流程 | 扫描 PDF 上传→解析→OCR→事件发布 | `test_integration_ocr.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- `OcrEnginePort` Protocol + 可能的值对象
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- `TesseractOcrEngine` + `ImageParser` OCR 增强
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- `_apply_ocr()` 编排逻辑
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

- [ ] TesseractOcrEngine 单元测试：mock pytesseract（`pytesseract.image_to_string` + `pytesseract.image_to_data`）
- [ ] ImageParser OCR 测试：mock pytesseract + Pillow Image.open
- [ ] DocumentParsingService OCR 测试：mock OcrEnginePort + PdfPageRendererPort
- [ ] 不使用真实 Tesseract 安装（单元测试通过 mock 验证行为，集成测试依赖真实环境）
- [ ] 程序化生成测试用图像字节（`PIL.Image.new()` 或固定 bytes fixture）
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] BDD 步骤函数：使用 `event_loop.run_until_complete()` 运行 async 测试（不使用 `@pytest.mark.asyncio`）
- [ ] `asyncio.Lock` 使用类变量而非实例变量

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 扫描件 PDF 页面 OCR 识别 | Task 2 + Task 3 | Task 2: TesseractOcrEngine; Task 3: _apply_ocr() | `test_tesseract_ocr_engine.py`; `test_document_parsing_service.py` |
| AC-2 | 中英双语 OCR 支持 | Task 2 | Task 2: TesseractOcrEngine 语言参数 + 准确率验证 | `test_tesseract_ocr_engine.py` |
| AC-3 | 图像文件 OCR 增强 | Task 2 | Task 2: ImageParser 扩展 — 置信度聚合/needs_review | `test_image_parser.py`（扩展） |
| AC-4 | 文档解析服务 OCR 编排集成 | Task 3 | Task 3: DocumentParsingService._apply_ocr() | `test_document_parsing_service.py`（扩展） |
| AC-5 | 容错与降级 | Task 1 + Task 2 + Task 3 | Task 1: OcrEnginePort 协议定义; Task 2: TesseractOcrEngine 降级; Task 3: _apply_ocr() 降级 | `test_ocr_engine_port.py`; `test_tesseract_ocr_engine.py`; `test_document_parsing_service.py` |
| AC-6 | 性能要求 P95 < 5s/页 | Task 2 + Task 3 | Task 2: TesseractOcrEngine 性能优化; Task 3: 逐页顺序处理 | 性能基准测试 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-4, AC-5

> **目的：** 在进入代码实现前，明确端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `OcrEnginePort` Protocol（`src/domain/ports/ocr_engine.py`）—— `@runtime_checkable`，`recognize(image_bytes, page_number) -> ...`
- [ ] Subtask 0.2: 更新端口注册中心（`registry.py`）与端口导出（`__init__.py`）
- [ ] Subtask 0.3: 编写端口契约测试 `tests/contracts/test_port_contract_ocr_engine.py`
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_ocr.feature`（11 个 Scenario：2 Happy Path + 3 Happy Path 混合 + 6 Edge Cases）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_ocr.py`
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层 — `OcrEnginePort` 端口协议定义

**关联 AC:** AC-4, AC-5

> **说明：** OCR 引擎的端口协议定义在领域层。`recognize()` 方法接收渲染后的页面图像字节，返回识别结果。
> 遵循 Story 2-3 的 `LayoutDetector` 和 Story 2-4 的 `TableExtractorPort` 端口定义模式。

#### TDD 循环 A：OcrEnginePort Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_ocr_engine_port.py`（验证 Protocol 可被实现类满足/runtime_checkable/isinstance 检查/接口签名约束/recognize 参数类型验证） |
| 🟢 绿 | 在 `src/domain/ports/ocr_engine.py` 实现 `OcrEnginePort` Protocol（`recognize(image_bytes, page_number) -> ...`） |
| 🔄 重构 | Google 中文注释、端口文档完善、`__init__.py` 导出 |

- [ ] Subtask 1.1: 🔴 红 — 编写 `TestOcrEnginePort`（Protocol 合规检查/实现类 isinstance 验证/签名约束）
- [ ] Subtask 1.2: 🟢 绿 — 实现 `OcrEnginePort` Protocol 最小代码
- [ ] Subtask 1.3: 🔄 重构 — 完善 docstring、更新 ports `__init__.py` 导出

**完成标准/Definition of Done:**
- [ ] `OcrEnginePort` Protocol 定义完成
- [ ] 端口协议测试通过
- [ ] 领域层零外部依赖（仅标准库 `typing`/`dataclasses`）

---

### Task 2: 基础设施层 — `TesseractOcrEngine` 实现 + `ImageParser` OCR 增强

**关联 AC:** AC-1, AC-2, AC-3, AC-5, AC-6

> **说明：** 实现 Tesseract OCR 引擎，基于 pytesseract（Apache-2.0 许可证，已在 `pyproject.toml` 中）。
> 同时增强现有 `ImageParser` 的 OCR 结果输出（置信度聚合 + needs_review 标记）。

#### TDD 循环 A：TesseractOcrEngine

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/document_parsing/test_tesseract_ocr_engine.py`（mock pytesseract：中文识别/英文识别/中英混排/空图像/噪声图像/低置信度标记/pytesseract ImportError 降级/逐页独立性验证） |
| 🟢 绿 | 实现 `src/infrastructure/document_parsing/tesseract_ocr_engine.py`：`TesseractOcrEngine` 类，实现 `OcrEnginePort` |
| 🔄 重构 | 置信度聚合逻辑优化、语言参数配置化、错误消息清理 |

- [ ] Subtask 2.1: 🔴 红 — 编写 TesseractOcrEngine 测试（mock pytesseract, ≥12 个 test case）
- [ ] Subtask 2.2: 🟢 绿 — 实现 `TesseractOcrEngine.recognize()` 最小代码
- [ ] Subtask 2.3: 🔄 重构 — 置信度聚合（word-level average → page-level）、阈值常量提取

#### TDD 循环 B：ImageParser OCR 增强

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/infrastructure/document_parsing/test_image_parser.py`（验证 ParsedElement.confidence 为聚合值而非硬编码 0.5/验证 metadata["needs_review"]/高置信度不标记/低置信度标记/GIF 首帧不变） |
| 🟢 绿 | 修改 `src/infrastructure/document_parsing/image_parser.py`：置信度聚合计算 + needs_review 阈值逻辑 |
| 🔄 重构 | 重构 magic number 0.5 为常量 `DEFAULT_OCR_CONFIDENCE`、阈值 `OCR_REVIEW_THRESHOLD = 0.85` |

- [ ] Subtask 2.4: 🔴 红 — 编写 ImageParser OCR 增强测试（≥5 个 test case）
- [ ] Subtask 2.5: 🟢 绿 — 增强 ImageParser OCR 结果输出
- [ ] Subtask 2.6: 🔄 重构 — 提取常量、完善 docstring

**完成标准/Definition of Done:**
- [ ] `TesseractOcrEngine` 实现完成，实现 `OcrEnginePort`
- [ ] `ImageParser` OCR 结果增强完成（confidence 聚合 + needs_review）
- [ ] 基础设施测试通过，覆盖率 ≥ 75%

---

### Task 3: 应用层 — `DocumentParsingService` OCR 集成 + `Composition Root` 注册

**关联 AC:** AC-1, AC-4, AC-5, AC-6

> **说明：** 将 `ocr_engine` 以 Story 2-3 `layout_detector` 和 Story 2-4 `table_extractor` 相同模式注入 `DocumentParsingService`，
> 新增 `_apply_ocr()` 编排方法。仅 PDF 格式触发，逐页检测空文本 → 渲染 → OCR → 回填。
> 同步更新 `composition_root.py` 端口注册。

#### TDD 循环 A：DocumentParsingService._apply_ocr()

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/services/test_document_parsing_service.py`（ocr_engine 注入/ocr_engine=None 跳过/仅 PDF 触发/扫描页 OCR 回填/原生文本页跳过/逐页降级/全部页 OCR 失败恢复/mock ocr_engine + mock pdf_page_renderer/WARNING 日志降级） |
| 🟢 绿 | 修改 `src/application/services/document_parsing_service.py`：新增可选参数 `ocr_engine: OcrEnginePort | None = None`，实现 `_apply_ocr()` 方法 |
| 🔄 重构 | 降级策略与 `_apply_layout_detection()` 对齐、超时保护 |

- [ ] Subtask 3.1: 🔴 红 — 编写 DocumentParsingService OCR 集成测试（≥10 个 test case）
- [ ] Subtask 3.2: 🟢 绿 — 实现 `_apply_ocr()` 编排方法
- [ ] Subtask 3.3: 🔄 重构 — 降级策略三场景：None→跳过 / 运行时异常→WARNING+原始结果 / 逐页独立降级

#### TDD 循环 B：Composition Root 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 contract test 验证端口可解析（`test_port_contract_ocr_engine.py` 中 `test_ocr_engine_port_registered`） |
| 🟢 绿 | 修改 `src/composition_root.py`：注册 `ocr_engine` 端口，注入到 `document_parsing_service` 工厂函数 |
| 🔄 重构 | 版本号升级（v1.2.0→v1.3.0）、端口契约清单更新 |

- [ ] Subtask 3.4: 🔴 红 — 编写端口注册验证测试
- [ ] Subtask 3.5: 🟢 绿 — 实现 Composition Root 注册 + `_create_parsing_service()` 工厂更新
- [ ] Subtask 3.6: 🔄 重构 — 版本升级 + 已存测试无回归验证

**完成标准/Definition of Done:**
- [ ] `DocumentParsingService` OCR 集成完成（v1.2.0 → v1.3.0）
- [ ] `composition_root.py` 注册完成
- [ ] 所有已有测试无回归
- [ ] 应用层覆盖率 ≥ 85%

---

### Task 4: SDD 架构约束验证测试

**关联 AC:** AC-1, AC-4, AC-5

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 4.1: 创建 `tests/unit/architecture/test_arch_document_ocr.py`
- [ ] Subtask 4.2: 实现领域层零外部依赖验证（`OcrEnginePort` 仅使用标准库）
- [ ] Subtask 4.3: 实现依赖方向验证（domain → application/infrastructure 禁止引用）
- [ ] Subtask 4.4: 实现 `OcrEnginePort` 端口在 domain/ports 中定义验证
- [ ] Subtask 4.5: 实现基础设施实现类满足 Protocol 验证（`isinstance(x, OcrEnginePort)`）
- [ ] Subtask 4.6: 实现循环依赖检测（使用 ruff `E` 规则或 `isort --check-only`）
- [ ] Subtask 4.7: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

### Task 5: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_ocr.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_ocr.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 5.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 5.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 5.3: 运行集成测试 `tests/integration/test_integration_ocr.py`（端到端：扫描 PDF 上传→解析→OCR→事件发布）
- [ ] Subtask 5.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md) §1.3, [`sisys-implementation-patterns.md`](../../docs/architecture/sisys-implementation-patterns.md)

- **架构模式:** 六边形架构（Ports & Adapters）— 领域层定义 `OcrEnginePort` 端口协议，基础设施层实现 `TesseractOcrEngine`
- **设计约束:** 领域层零外部依赖（纯 Python 标准库）；依赖方向 domain ← application ← infrastructure
- **增强注入模式（Story 2-3/2-4 复用）:** Optional 构造函数参数（`ocr_engine: OcrEnginePort | None = None`）+ 三级降级（None→跳过 / 运行时异常→WARNING+原始结果 / 初始化失败→raise）
- **接口治理:** 统一端口注册（`PortSpec` 元数据 + `register_port()`）→ `composition_root.py` 唯一注册入口 → 契约测试验证
- **技术栈:** Python 3.11+; pytesseract 0.3.10+ (Apache-2.0) 已存在依赖; pypdfium2 (BSD-3-Clause) 已由 PdfPageRenderer 使用; Pillow 12.1.1+ (MIT-CMU) 已存在依赖

### 关键架构决策

**来源:** [`docs/archive/document-parser-spike.md`](../../docs/archive/document-parser-spike.md) - §2.2.4 pdf2image + OCR 方案

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **pytesseract (Apache-2.0)** | 已在 pyproject.toml 中、MIT 兼容许可证、中英双语支持、chi_sim+eng 语言包成熟、与 Pillow 无缝集成 | 精度受图像质量影响大、对复杂排版识别效果一般 | ✅ 8/10 |
| PaddleOCR (Apache-2.0) | 中文识别精度更高（CTPN+CRNN）、支持表格结构识别、端到端深度学习 | 依赖 PaddlePaddle 框架（体积大）、GPU 推荐（CPU 慢）、部署复杂度高 | 7/10 |
| EasyOCR (Apache-2.0) | 支持 80+ 语言、开箱即用、深度学习模型 | PyTorch 依赖（体积大）、首次运行需下载模型、中文精度不如 PaddleOCR | 6/10 |
| Cloud Vision API (商业) | 最高精度、免运维 | 成本高、数据出境风险、网络依赖 | 4/10 |

**决策理由：**
1. pytesseract 已在项目 `pyproject.toml` 中作为现有依赖（Story 2-2a ImageParser 使用），零增量依赖成本
2. ImageParser 已有 pytesseract OCR 使用经验和降级模式，实现风险最低
3. pytesseract + chi_sim+eng 语言包对标准扫描件中英文识别率可满足 MVP 需求（中≥90%, 英≥95%）
4. Apache-2.0 许可证企业商用合规
5. PaddleOCR/EasyOCR 可预留给 V2 精度优化（需要时可替换 OcrEnginePort 实现，端口协议不变）

**扫描页检测策略（关键设计决策）：**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **文本提取为空检测** | 零额外成本、复用 pypdf extract_text() 结果、简单可靠 | 部分页面可能同时含文本层和图片（极少数场景），保守策略会导致 OCR 遗漏 | ✅ 8/10 |
| 图像分类模型（CNN） | 精准区分扫描页/原生页 | 引入额外模型依赖、推理延迟、复杂部署 | 5/10 |
| 文件元数据判断 | 扫描仪通常写入 Producer 元数据 | 不可靠（元数据可能缺失或被修改） | 4/10 |

**决策理由：** MVP 采用"文本提取为空检测"策略——对 pypdf `extract_text()` 返回空字符串的页面触发 OCR。
优点：零额外依赖、逻辑简单、已覆盖 95%+ 的扫描件场景（扫描件无文本层是物理事实）。
少数同时含文本层和嵌入图片的 PDF 页面（如 Word 导出的图文混排 PDF）已有文本层，不需要 OCR。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── ports/
│   │   ├── __init__.py                    # [MODIFY] 导出 OcrEnginePort
│   │   └── ocr_engine.py                  # [NEW] OcrEnginePort Protocol
│   └── value_objects/
│       └── parsed_document.py             # [NO CHANGE] 复用 ParsedElement/ParsedPage/ParsedDocument
│
├── application/
│   └── services/
│       └── document_parsing_service.py    # [MODIFY] 注入 ocr_engine + _apply_ocr()
│
├── infrastructure/
│   └── document_parsing/
│       ├── tesseract_ocr_engine.py        # [NEW] TesseractOcrEngine（实现 OcrEnginePort）
│       └── image_parser.py                # [MODIFY] OCR 置信度聚合 + needs_review 标记
│
└── composition_root.py                    # [MODIFY] 注册 ocr_engine 端口 + _create_parsing_service 更新

tests/
├── unit/
│   ├── domain/
│   │   └── ports/test_ocr_engine_port.py                 # [NEW] OcrEnginePort 协议测试
│   ├── application/
│   │   └── services/test_document_parsing_service.py     # [MODIFY] 扩展 OCR 编排测试
│   ├── infrastructure/
│   │   └── document_parsing/
│   │       ├── test_tesseract_ocr_engine.py              # [NEW] TesseractOcrEngine 测试
│   │       └── test_image_parser.py                      # [MODIFY] 扩展 OCR 增强测试
│   └── architecture/
│       └── test_arch_document_ocr.py                     # [NEW] 架构约束测试
├── integration/
│   └── test_integration_ocr.py                           # [NEW] 端到端 OCR 集成测试
├── acceptance/
│   ├── test_acceptance_ocr.feature                       # [NEW] Gherkin 场景
│   └── test_acceptance_ocr.py                            # [NEW] BDD 步骤实现
└── contracts/
    └── test_port_contract_ocr_engine.py                  # [NEW] 端口契约验证
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 2-4-表格行列语义提取](./2-4-table-semantic-extraction.md)

**关键学习/Key Learnings:**
1. **可选增强注入模式** — `table_extractor` 作为 Optional 构造函数参数注入 `DocumentParsingService`；Story 2-5 的 `ocr_engine` 应遵循同样模式（默认 None，支持优雅降级）
2. **降级策略一致性** — 三级降级：port=None → 跳过增强（无日志）；运行时异常 → WARNING 日志 + 返回原始结果；初始化失败（依赖缺失）→ raise（配置错误，不降级）
3. **Composition Root 工厂降级** — `_create_parsing_service()` 中 try/except 捕获 ImportError/FileNotFoundError，降级端口为 None（Story 2-4 的 table_extractor 模式 + Story 2-3 的 layout_detector 模式）
4. **asyncio.to_thread + try/finally** — Story 2-2b 修复：`asyncio.to_thread()` 包装的同步操作被取消时要清理资源；Story 2-5 的 OCR 调用同样需要 try/finally 确保临时图像数据清理

**应用到本故事/Applied to This Story:**
- [ ] `ocr_engine` 作为 Optional 构造函数参数注入 `DocumentParsingService`（默认 None）
- [ ] 降级策略与 `_apply_layout_detection()` / `_apply_table_extraction()` 对齐（三级降级）
- [ ] `composition_root._create_parsing_service()` 中 try/except ImportError 降级 ocr_engine=None
- [ ] OCR 调用使用 `asyncio.to_thread()` + 逐页独立 try/except

**来源:** [Story 2-3-版面信息保留](./2-3-layout-preservation-doclaynet.md)

**关键学习/Key Learnings:**
1. **PdfPageRenderer 复用** — Story 2-3 引入 `PdfPageRenderer` 将 PDF 页面渲染为 PNG 供 `LayoutDetector` 消费；Story 2-5 的 `TesseractOcrEngine` 可直接复用此渲染器，不重复实现
2. **逐页独立处理** — `_apply_layout_detection()` 逐页独立 try/except，单页失败不影响其他页；`_apply_ocr()` 应遵循同样模式
3. **渲染 DPI 150** — Story 2-3 使用 150 DPI 作为默认渲染分辨率（平衡速度与质量），OCR 同样使用此配置（中文 OCR 150 DPI 已足够）

**应用到本故事/Applied to This Story:**
- [x] 复用已有 `PdfPageRenderer` 渲染 PDF 页面为 PNG（不创建新的渲染器）
- [x] 逐页独立 try/except + 单页失败不影响其他页
- [x] 使用 150 DPI 渲染分辨率（与 layout_detector 一致）

**来源:** [Story 2-2a-文档解析基础格式](./2-2a-document-parsing-basic-formats.md)

**关键学习/Key Learnings:**
1. **ImageParser 已有 pytesseract OCR** — `image_parser.py:97-117` 已实现 pytesseract OCR 提取，但置信度在 OCR 失败时硬编码为 0.5（应聚合 word-level confidence）
2. **PDFParser 空文本检测** — `pdf_parser.py:112` 中 `page.extract_text()` 返回空字符串时 `texts=[]`，这是 OCR 的触发条件
3. **错误消息清理** — 异常 `str(e)` 禁止直接写入 metadata（安全：防止内部路径泄露）

**应用到本故事/Applied to This Story:**
- [x] ImageParser 置信度从硬编码 0.5 改为 word-level 聚合
- [x] OCR 触发条件：pypdf `extract_text()` 返回空字符串
- [x] OCR 错误消息使用预定义的 sanitized 消息

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.8 |
| **Version** | create-story workflow — SDD+TDD 融合模式模板 v2.9.0 |
| **Execution Date** | 2026-06-06 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` (v2.9.0) |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` §Epic 2, Story 2-5 |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-4-table-semantic-extraction.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **技术选型参考** | `docs/archive/document-parser-spike.md` §2.2.4 pdf2image+OCR |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` §Epic 2, Story 2-5 和 FR-DM-05 提取
- [ ] 架构约束从 `architecture.md` §1.3/§9/§11 和 story-template.md §六边形架构约束 提取
- [ ] 前一个故事学习经验从 Story 2-4/2-3/2-2a 整合
- [ ] 现有代码分析完成：ImageParser（已有 pytesseract OCR）、PDFParser（扫描页检测点）、PdfPageRenderer（复用渲染器）、DocumentParsingService（注入模式对齐）
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范（Story 2-3/2-4 模式复用）
- [ ] AC→Task→Subtask 追溯矩阵完整（6 AC × 6 Task）
- [ ] 每个 Task 含独立 TDD 红→绿→重构循环
- [ ] 技术选型决策记录（pytesseract vs PaddleOCR vs EasyOCR vs Cloud Vision API）
- [ ] 扫描页检测策略决策记录（文本为空 vs 图像分类 vs 元数据判断）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-5-ocr-parsing-scanned-documents.md`

**待创建的文件/To Be Created (Dev Story 实施):**

*领域层新增:*
- `src/domain/ports/ocr_engine.py` — OcrEnginePort 端口协议
- `src/domain/ports/__init__.py` — 追加导出 OcrEnginePort

*基础设施层新增/修改:*
- `src/infrastructure/document_parsing/tesseract_ocr_engine.py` — TesseractOcrEngine 实现
- `src/infrastructure/document_parsing/image_parser.py` — OCR 置信度聚合 + needs_review 增强

*应用层修改:*
- `src/application/services/document_parsing_service.py` — 新增 ocr_engine 注入 + `_apply_ocr()` 方法

*组合根修改:*
- `src/composition_root.py` — 注册 ocr_engine 端口 + 更新 `_create_parsing_service()`

*测试文件新增/修改:*
- `tests/unit/domain/ports/test_ocr_engine_port.py` — 端口协议测试
- `tests/unit/infrastructure/document_parsing/test_tesseract_ocr_engine.py` — OCR 引擎测试（≥12 个 test case）
- `tests/unit/infrastructure/document_parsing/test_image_parser.py` — 扩展 OCR 增强测试（≥5 个 test case）
- `tests/unit/application/services/test_document_parsing_service.py` — 扩展 OCR 编排测试（≥10 个 test case）
- `tests/unit/architecture/test_arch_document_ocr.py` — 架构约束测试
- `tests/contracts/test_port_contract_ocr_engine.py` — 端口契约验证
- `tests/acceptance/test_acceptance_ocr.feature` — Gherkin 场景（11 个 Scenario）
- `tests/acceptance/test_acceptance_ocr.py` — BDD 步骤实现
- `tests/integration/test_integration_ocr.py` — 端到端集成测试

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.5 |
| **Story Key** | 2-5-ocr-parsing-scanned-documents |
| **File** | `_bmad-output/implementation-artifacts/stories/2-5-ocr-parsing-scanned-documents.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0（FR-DM-05 MVP 必需） / 执行优先级 P1-5 |
| **覆盖 FR** | FR-DM-05（扫描件/图像 PDF OCR 解析，中/英，置信度标注） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-5，6 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-6，6 个 AC）
3. [x] Architecture constraints extracted 架构约束已提取（六边形架构/端口契约/领域零依赖）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 2-4 + 2-3 + 2-2a）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes

> 待 `bmad-review-adversarial-general` 审查后填写。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| — | — | — | — |

---

### 🔍 代码审查发现 Review Findings

> 待 `code-review` 完成后填写。

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-06-06
**最后更新/Last Updated:** 2026-06-06
**更新说明/Description:**
- v1.0.0: 创建故事文件（遵循 SDD+TDD 融合模式模板 v2.9.0，复用 Story 2-3/2-4 增强注入模式）
