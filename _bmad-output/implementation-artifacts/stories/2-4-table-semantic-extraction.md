# Story 2-4: 表格行列语义提取

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 财务分析师,
**I want** 系统提取表格的行列语义，输出包含表头与列类型的结构化 JSON,
**So that** 财务数据不失真，支持后续分析。

### 业务价值

Epic 2 文档与数据管理的核心 Story（FR-DM-04 P0），属文档处理流水线中表格数据的语义增强环节。

在 Story 2-2a 基础格式解析（PDF/DOCX/TXT）、Story 2-2b 扩展格式解析（PPTX/XLSX/CSV 等）和 Story 2-3 版面信息保留（DocLayNet）完成后，
各解析器已能提取原始表格数据（`ParsedTable.rows` 为 `list[list[str]]`），但缺失表头识别、列类型推断、合并单元格语义还原等结构化语义信息。

本 Story 引入表格语义提取层，对解析器产出的原始 `ParsedTable` 进行语义增强，输出包含 `header`（列名）、`column_types`（列数据类型）、`merged_cells`（合并单元格映射）的结构化 JSON，
为下游 Epic 4 财务量化分析（NPV/IRR）和 Epic 6 战略规划（BLM/BEM 数据驱动分析）提供高质量结构化表格数据。

**核心假设：** MVP 阶段表格语义提取聚焦于 xls/xlsx/csv/PDF 内嵌表格四种核心格式。
PDF 表格初始检测使用 pdfplumber（MIT 许可证，专有表格检测算法）替代 PDFParser 中的 `tables=[]` 占位符 [Source: docs/developer/document-parser-spike.md §5.1]。
表头检测和列类型推断使用纯 Python 启发式算法（领域层零外部依赖），合并单元格还原和跨页表格识别标记为 V1（对应 FR-DM-12）。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 多格式表格解析与结构化输出

**Given** 文档包含表格（xls/xlsx/csv/PDF 内嵌表格）
**When** 系统执行表格语义提取
**Then** 提取表头、列类型、行列语义，输出结构化 JSON
**And** `ParsedTable` 的 `header` 字段包含列名列表（`list[str]`）
**And** `ParsedTable` 的 `column_types` 字段包含列类型信息列表（`list[ColumnInfo]`，每项含 `name`/`col_type`/`confidence`）
**And** 原始 `rows`（`list[list[str]]`）保持不变，语义信息作为新增字段提供
**And** `ParsedTable.to_dict()` 包含完整语义字段

**验证标准/Validation Criteria:**
- [ ] xls/xlsx/csv/PDF 表格四种格式均产出含 `header` 和 `column_types` 的 `ParsedTable`
- [ ] `to_dict()` 输出包含 `header`/`column_types`/`merged_cells`/`semantic_confidence` 字段
- [ ] 向后兼容：下游消费 `rows` 字段的代码不受影响（`rows` 字段不变）
- [ ] 非表格页面/文档不受影响（`tables=[]` 时跳过语义提取）

### AC-2: 表头识别准确率

**Given** 包含明确表头的表格（xls/xlsx/csv/PDF）
**When** 系统执行表头识别
**Then** 表头识别准确率 ≥ 95%
**And** 支持单行表头识别（MVP）
**And** 表头行索引记录在 `ParsedTable.metadata["header_row_indices"]` 中
**And** 表头置信度记录在 `ParsedTable.metadata["header_confidence"]` 中

**验证标准/Validation Criteria:**
- [ ] 表头检测领域服务 `table_header_detector` 位于 `src/domain/services/table_header_detector.py`
- [ ] 使用多特征加权策略（首行类型差异 + 格式特征 + 空值模式），零外部依赖
- [ ] 采样 20 个含表头的测试表格，表头识别正确率 ≥ 95%（≥19/20）
- [ ] 无表头的纯数据表格返回 `header=None` 且置信度降低（不误判）

### AC-3: 列类型推断准确率

**Given** 包含不同数据类型的表格列（字符串/数字/日期/货币/百分比/布尔）
**When** 系统执行列类型推断
**Then** 列类型识别准确率 ≥ 95%
**And** 推断结果包含类型置信度分数（`ColumnInfo.confidence: float`）
**And** 支持的列类型至少包含：STRING / NUMBER / DATE / CURRENCY / PERCENTAGE / BOOLEAN / UNKNOWN
**And** 按列采样推断（前 N 行 + 随机采样），避免全表扫描

**验证标准/Validation Criteria:**
- [ ] 列类型推断领域服务 `table_column_classifier` 位于 `src/domain/services/table_column_classifier.py`
- [ ] 使用正则模式匹配（日期/货币/百分比/布尔）+ 类型转换试探（数字），零外部依赖
- [ ] 采样 20 列不同类型数据，类型推断正确率 ≥ 95%
- [ ] 每列返回 `ColumnInfo` 含 `name`/`col_type: ColumnType`/`confidence`/`nullable_ratio`/`sample_values`

### AC-4: 合并单元格语义还原（V1）

**Given** 包含合并单元格的表格（跨行/跨列，xlsx 格式为主）
**When** 系统执行表格解析
**Then** 正确还原合并单元格语义（rowspan/colspan）
**And** 合并单元格值在对应的所有覆盖单元格中可访问
**And** `ParsedTable.merged_cells` 字段包含 `list[MergedCell]`（`row_start`/`row_end`/`col_start`/`col_end`/`value`）

**验证标准/Validation Criteria:**
- [ ] 合并单元格还原领域服务 `table_merge_resolver` 位于 `src/domain/services/table_merge_resolver.py`（V1）
- [ ] xlsx 格式利用 openpyxl `sheet.merged_cells.ranges` 获取合并信息
- [ ] 合并单元格数据填充到 `rows` 中所有覆盖位置
- [ ] 非 xlsx 格式（csv/PDF）降级为 `merged_cells=None`

### AC-5: PDF 表格初始检测（pdfplumber）

**Given** PDF 文档包含内嵌表格
**When** PDFParser 执行解析
**Then** 使用 pdfplumber 检测 PDF 页面中的表格区域
**And** 提取表格的行列结构（含行/列跨度信息）
**And** PDF 内嵌表格不再输出空 `tables=[]`（替换 Story 2-2a 占位符）
**And** 检测到的表格信息填入 `ParsedPage.tables`

**验证标准/Validation Criteria:**
- [ ] `pdfplumber` 依赖添加至 `pyproject.toml`（MIT 许可证）
- [ ] `PdfTableExtractor` 实现位于 `src/infrastructure/document_parsing/pdf_table_extractor.py`
- [ ] PDFParser 中第 109 行 TODO 注释移除，替换为 pdfplumber 表格检测调用
- [ ] 向后兼容：pdfplumber 未安装时 PDFParser 保持原有行为（tables=[]）
- [ ] 跨页表格识别逻辑位于领域服务（V1）

### AC-6: 性能要求

**Given** 包含表格的文档
**When** 系统执行表格语义提取
**Then** 表格解析延迟 P95 < 500ms（单页简单表格）
**And** 大表格（>1000 行）使用流式处理，内存占用可控
**And** pdfplumber 逐页处理 PDF，避免整文档加载内存溢出

**验证标准/Validation Criteria:**
- [ ] 性能基准测试：单页 10 列表格 < 500ms（P95）
- [ ] 大表格 >1000 行时内存增长 ≤ O(采样行数) 而非 O(总行数)
- [ ] pdfplumber 使用 `pdfplumber.open(pages=[n])` 逐页处理

### AC-7: 容错与降级

**Given** 表格语义提取可能因各种原因失败（复杂表格/不支持的格式/依赖缺失）
**When** 语义提取过程中发生错误
**Then** 系统降级返回原始 `ParsedTable`（语义字段为 None，rows 保持原始值）
**And** 日志记录降级原因和位置（WARNING 级别）
**And** 表格语义提取失败不影响文档解析主流程完成（`parse_status` 仍为 `"completed"`）
**And** 降级策略与 Story 2-3 版面检测保持一致

**验证标准/Validation Criteria:**
- [ ] `table_extractor` 端口未注入（None）→ 跳过增强，保留原始 tables
- [ ] 运行时异常（如 pdfplumber 表格检测失败）→ WARNING 日志 + 保留原始 tables
- [ ] 领域服务异常（表头检测/列类型推断）→ WARNING 日志 + 对应字段为 None
- [ ] 初始化失败（pdfplumber 未安装）→ raise `ImportError`（配置错误，非降级场景）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 复用 `DocumentProcessed` 事件（Story 2-2a 已定义），**不新增事件** — 表格语义提取结果通过 `parse_result` dict 中的 `pages[].tables[]` 传递
- [ ] 复用 `DocumentUploaded` 事件触发解析流程（不变）

#### 数据模型 (Data Models)
- [ ] **扩展** `ParsedTable` 值对象（`src/domain/value_objects/parsed_document.py`）：
  - 新增 `header: list[str] | None = None` — 列名列表
  - 新增 `column_types: list[ColumnInfo] | None = None` — 列类型信息列表
  - 新增 `merged_cells: list[MergedCell] | None = None` — 合并单元格映射（V1）
  - 新增 `semantic_confidence: float | None = None` — 语义提取综合置信度
  - 新增 `table_caption: str | None = None` — 表格标题/说明
  - 所有新字段使用 `field(default=None)` 保持向后兼容
  - 更新 `to_dict()` 序列化方法
- [ ] **新增** `ColumnType` 枚举（`src/domain/value_objects/parsed_document.py`）：
  - 值：`STRING` / `NUMBER` / `DATE` / `CURRENCY` / `PERCENTAGE` / `BOOLEAN` / `UNKNOWN`
- [ ] **新增** `ColumnInfo` 值对象（`@dataclass(frozen=True)`）：
  - 字段：`name: str` / `col_type: ColumnType` / `confidence: float` / `nullable_ratio: float` / `sample_values: list[str]`
  - 方法：`to_dict()`
- [ ] **新增** `MergedCell` 值对象（`@dataclass(frozen=True)`，V1）：
  - 字段：`row_start: int` / `row_end: int` / `col_start: int` / `col_end: int` / `value: str`
  - 方法：`to_dict()`
- [ ] **复用** `BoundingBox`（`x/y/width/height/page`）—— 已存在，无需修改
- [ ] **追加导出** `ColumnType`/`ColumnInfo`/`MergedCell` 至 `src/domain/value_objects/__init__.py`

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `TableExtractorPort` 端口契约（`src/domain/ports/table_extractor.py`）：
  - `@runtime_checkable` + `Protocol`
  - `extract(file_path: str, mime_type: str, tables: list[ParsedTable]) -> list[ParsedTable]`
  - 方法接收原始 ParsedTable 列表，返回语义增强后的 ParsedTable 列表
- [ ] **端口注册** — 在 `src/composition_root.py` 中调用 `register_port()` 注册 `table_extractor` 端口
- [ ] **端口契约门禁**（`src/domain/ports/contract_gate.py`）：新端口变更通过兼容性检查
- [ ] **端口契约测试**（`tests/contracts/test_port_contract_table_extractor.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称 `table_extractor`、版本 `v1.0.0`、owner `epic-2`

**端口契约清单：**

| 端口名称 | 接口 | 实现 | 注册位置 | Lifetime | Version | Owner |
|---------|------|------|----------|----------|---------|-------|
| `table_extractor` | `TableExtractorPort` | `TableSemanticExtractor` | domain/ports/table_extractor.py | SCOPED | v1.0.0 | epic-2 |
| `pdf_table_extractor` | `TableExtractorPort` | `PdfTableExtractor` | domain/ports/table_extractor.py | SCOPED | v1.0.0 | epic-2 |
| `document_parser` | `DocumentParserPort` | `CompositeDocumentParser` | domain/ports/document_parser.py | SCOPED | v1.1.0→v1.2.0 | epic-2 |
| `document_parsing_service` | `DocumentParsingService` | — | application/services/ | SCOPED | v1.1.0→v1.2.0 | epic-2 |

> **版本升级说明：**
> - `document_parsing_service` v1.2.0：构造函数新增可选参数 `table_extractor: TableExtractorPort | None = None`，编排逻辑增加表格语义提取步骤（`_apply_table_extraction()`）。向后兼容（可选参数，默认 `None` 时跳过）。
> - `document_parser`（`CompositeDocumentParser`）v1.2.0：PDF 解析器 `pdf_parser` 集成 `pdf_table_extractor` 可选注入，替换 `tables=[]` 占位符。
> - `table_extractor`：通用表格语义提取器，对解析器产出的原始 ParsedTable 进行语义增强（表头/列类型/合并单元格）。
> - `pdf_table_extractor`：PDF 专用表格检测器，使用 pdfplumber 从 PDF 页面中初始检测表格结构。

#### API 契约 (API Contract)
- [x] 复用 `GET /api/v1/documents/{document_id}` 查询端点（不变）
- [x] 解析结果存储于 `Document.metadata["parse_result"]` JSONB 字段（不变，表格语义数据内含）
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
- 禁止导入：包括且不限于 pdfplumber, openpyxl, onnxruntime, numpy, pillow, fastapi, sqlalchemy 等

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_table_extraction.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_table_extraction.py`
- [ ] HAPPY PATH: 标准表格（xlsx）表头+列类型提取
- [ ] HAPPY PATH: CSV 表格列类型推断
- [ ] HAPPY PATH: PDF 内嵌表格检测与语义提取
- [ ] EDGE CASE: 无表头纯数据表格（header=None）
- [ ] EDGE CASE: 全空表格（rows为空/全None）
- [ ] EDGE CASE: 混合类型列（降级为 STRING 类型，低置信度）
- [ ] EDGE CASE: pdfplumber 检测失败降级（WARNING 日志 + 原始 tables）
- [ ] EDGE CASE: 合并单元格表格语义还原（V1，标记为 @skip 默认跳过）

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
| **TDD 单元测试** | ParsedTable 扩展 + ColumnInfo/MergedCell 值对象 | 创建/序列化/to_dict()/向后兼容 | `test_parsed_document.py`（扩展） | Task 1 |
| **TDD 单元测试** | TableExtractorPort 端口 | Protocol 合规/类型检查/签名约束 | `test_table_extractor_port.py` | Task 2 |
| **TDD 单元测试** | table_header_detector 领域服务 | 表头检测/多特征加权/边缘 case | `test_table_header_detector.py` | Task 3 |
| **TDD 单元测试** | table_column_classifier 领域服务 | 列类型推断/正则模式/置信度评分 | `test_table_column_classifier.py` | Task 3 |
| **TDD 单元测试** | table_merge_resolver 领域服务（V1） | 合并单元格还原/坐标填充 | `test_table_merge_resolver.py` | Task 3 |
| **TDD 单元测试** | TableSemanticExtractor | 语义提取器编排/mock 依赖 | `test_table_semantic_extractor.py` | Task 4 |
| **TDD 单元测试** | PdfTableExtractor | pdfplumber 表格检测/mock | `test_pdf_table_extractor.py` | Task 4 |
| **TDD 单元测试** | DocumentParsingService 集成 | `_apply_table_extraction()`/降级 | `test_document_parsing_service.py`（扩展） | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_table_extraction.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_table_extraction.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_table_extraction.feature` | Task 7 |
| **TDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_table_extraction.py` | Task 7 |
| **TDD 契约测试** | 端口契约 / TableExtractorPort | 注册/版本/兼容性/实现解析 | `test_port_contract_table_extractor.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖/端口在 domain | `test_arch_document_table.py` | Task 6 |
| **集成测试** | 端到端表格语义提取 | 解析→语义增强→事件发布 | `test_integration_table_extraction.py` | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- 新增 `ColumnInfo`/`MergedCell`/`ColumnType` 值对象 + 3 个领域服务
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- `TableSemanticExtractor` + `PdfTableExtractor`
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- 编排逻辑扩展
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

- [ ] 领域服务测试：纯函数测试，无外部依赖，可并行运行
- [ ] PdfTableExtractor 测试：mock pdfplumber（不依赖真实 PDF 文件），mock ONNX InferenceSession
- [ ] 程序化 fixture 生成测试用表格数据（`_create_*()` 工厂函数），不使用静态 fixture 文件
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] BDD 步骤函数：使用 `event_loop.run_until_complete()` 运行 async 测试（不使用 `@pytest.mark.asyncio`）
- [ ] `asyncio.Lock` 使用类变量而非实例变量

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 多格式表格解析与结构化输出 | Task 0 + Task 4 + Task 5 | Task 0: ParsedTable 扩展 Schema 定义; Task 4: TableSemanticExtractor 实现; Task 5: DocumentParsingService 集成 | `test_parsed_document.py`; `test_table_semantic_extractor.py`; `test_document_parsing_service.py` |
| AC-2 | 表头识别准确率 ≥95% | Task 3 + Task 4 | Task 3: table_header_detector 领域服务; Task 4: TableSemanticExtractor 调用 | `test_table_header_detector.py` |
| AC-3 | 列类型推断准确率 ≥95% | Task 3 + Task 4 | Task 3: table_column_classifier 领域服务; Task 4: TableSemanticExtractor 调用 | `test_table_column_classifier.py` |
| AC-4 | 合并单元格语义还原（V1） | Task 3 + Task 4 | Task 3: table_merge_resolver 领域服务; Task 4: TableSemanticExtractor 调用 | `test_table_merge_resolver.py` |
| AC-5 | PDF 表格初始检测（pdfplumber） | Task 4 | Task 4: PdfTableExtractor 实现 | `test_pdf_table_extractor.py` |
| AC-6 | 性能 P95 < 500ms | Task 4 + Task 5 | Task 4: 逐页处理; Task 5: 超时保护 | 性能基准测试 |
| AC-7 | 容错与降级 | Task 5 | Task 5: 降级策略实现 | `test_document_parsing_service.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-7

> **目的：** 在进入代码实现前，明确 Schema、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `ColumnType` 枚举和 `ColumnInfo`/`MergedCell` 值对象 Schema，更新 `__init__.py` 导出
- [ ] Subtask 0.2: 扩展 `ParsedTable` 值对象 Schema（`header`/`column_types`/`merged_cells`/`semantic_confidence`/`table_caption`）
- [ ] Subtask 0.3: 定义 `TableExtractorPort` 端口契约（`src/domain/ports/table_extractor.py`）—— `@runtime_checkable` Protocol，`extract(file_path, mime_type, tables) -> list[ParsedTable]`
- [ ] Subtask 0.4: 更新端口注册中心（`registry.py`）与端口契约门禁（`contract_gate.py`）
- [ ] Subtask 0.5: 编写端口契约测试 `tests/contracts/test_port_contract_table_extractor.py`
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_table_extraction.feature`（8 个 Scenario）
- [ ] Subtask 0.7: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_table_extraction.py`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层 — 值对象扩展

**关联 AC:** AC-1

> **说明：** 扩展现有 `ParsedTable` 值对象，新增 `ColumnType` 枚举和 `ColumnInfo`/`MergedCell` 值对象。
> 所有新字段使用 `field(default=None)` 保持向后兼容，已有消费 `ParsedTable.rows` 的代码不受影响。

#### TDD 循环 A：ColumnType 枚举 + ColumnInfo 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/value_objects/test_parsed_document.py`（`TestColumnType` 枚举值验证; `TestColumnInfo`：创建/to_dict 序列化/frozen 不可变性/confidence 边界 [0.0-1.0]/nullable_ratio 边界/sample_values 默认空列表） |
| 🟢 绿 | 在 `src/domain/value_objects/parsed_document.py` 实现 `ColumnType` 枚举和 `ColumnInfo` dataclass |
| 🔄 重构 | Google 中文注释、添加 `__init__.py` 导出 |

- [ ] Subtask 1.1: 🔴 红 — 编写 `TestColumnType` + `TestColumnInfo` 测试类
- [ ] Subtask 1.2: 🟢 绿 — 实现 `ColumnType` 枚举和 `ColumnInfo` dataclass
- [ ] Subtask 1.3: 🔄 重构 — 完善 docstring、更新导出

#### TDD 循环 B：MergedCell 值对象（V1）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/value_objects/test_parsed_document.py`（`TestMergedCell`：创建/坐标验证/to_dict/frozen 不可变性/row_start ≤ row_end/col_start ≤ col_end） |
| 🟢 绿 | 在 `src/domain/value_objects/parsed_document.py` 实现 `MergedCell` dataclass |
| 🔄 重构 | 添加 V1 标记注释、更新导出 |

- [ ] Subtask 1.4: 🔴 红 — 编写 `TestMergedCell` 测试类
- [ ] Subtask 1.5: 🟢 绿 — 实现 `MergedCell` dataclass
- [ ] Subtask 1.6: 🔄 重构 — 完善 docstring

#### TDD 循环 C：ParsedTable 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `TestParsedTable` 测试类（新增字段默认值验证/to_dict 包含新字段/向后兼容 rows 不变/header=None 时 to_dict 输出 null/column_types=None 时 to_dict 输出 null） |
| 🟢 绿 | 在 `ParsedTable` 新增 5 个字段（`header`/`column_types`/`merged_cells`/`semantic_confidence`/`table_caption`），全部 `field(default=None)` |
| 🔄 重构 | 验证已有解析器测试全部通过（无回归） |

- [ ] Subtask 1.7: 🔴 红 — 扩展 `TestParsedTable` 测试类
- [ ] Subtask 1.8: 🟢 绿 — 扩展 `ParsedTable` dataclass
- [ ] Subtask 1.9: 🔄 重构 — 运行全部已有测试确认无回归

**完成标准/Definition of Done:**
- [ ] `ColumnType`/`ColumnInfo`/`MergedCell` 值对象实现完成
- [ ] `ParsedTable` 扩展完成，向后兼容
- [ ] 值对象测试全部通过，覆盖率 ≥ 90%


---

### Task 2: 领域层 — `TableExtractorPort` 端口协议定义

**关联 AC:** AC-1, AC-7

> **说明：** 表格语义提取的端口协议定义在领域层。`extract()` 方法接收解析器产出的原始 `ParsedTable` 列表，返回语义增强后的 `ParsedTable` 列表。
> 遵循 Story 2-3 的 `LayoutDetector` 端口定义模式。

#### TDD 循环 A：TableExtractorPort Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_table_extractor_port.py`（验证 Protocol 可被实现类满足/runtime_checkable/isinstance 检查/接口签名约束/extract 参数类型验证） |
| 🟢 绿 | 在 `src/domain/ports/table_extractor.py` 实现 `TableExtractorPort` Protocol（`extract(file_path, mime_type, tables) -> list[ParsedTable]`） |
| 🔄 重构 | Google 中文注释、端口文档完善 |

- [ ] Subtask 2.1: 🔴 红 — 编写 `TestTableExtractorPort`（Protocol 合规检查/实现类 isinstance 验证/签名约束）
- [ ] Subtask 2.2: 🟢 绿 — 实现 `TableExtractorPort` Protocol 最小代码
- [ ] Subtask 2.3: 🔄 重构 — 完善 docstring

**完成标准/Definition of Done:**
- [ ] `TableExtractorPort` Protocol 定义完成
- [ ] 端口协议测试通过
- [ ] 领域层零外部依赖（仅标准库 `typing`/`dataclasses`）


---

### Task 3: 领域层 — 表格语义分析领域服务

**关联 AC:** AC-2, AC-3, AC-4

> **说明：** 三个纯 Python 领域服务（零外部依赖），在 Task 4 的 `TableSemanticExtractor` 中被编排调用。
> 每个服务独立可测试，不依赖彼此。

#### TDD 循环 A：table_header_detector（表头检测）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_table_header_detector.py`（标准表头检测/无表头表格/单行表头/首行全文本→表头/首行含数字→非表头/空表格/单行表格/多行表头 V1） |
| 🟢 绿 | 实现 `src/domain/services/table_header_detector.py`：`detect_header(rows: list[list[str]]) -> tuple[int | None, float]` 返回（表头行索引, 置信度） |
| 🔄 重构 | 多特征加权优化、添加阈值常量 |

- [ ] Subtask 3.1: 🔴 红 — 编写表头检测测试（≥15 个 test case）
- [ ] Subtask 3.2: 🟢 绿 — 实现表头检测最小代码（首行类型差异法 + 格式特征法 + 空值模式法）
- [ ] Subtask 3.3: 🔄 重构 — 多特征加权（类型差异 40% + 格式特征 35% + 空值模式 25%）

#### TDD 循环 B：table_column_classifier（列类型推断）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_table_column_classifier.py`（纯数字列→NUMBER/日期列→DATE/货币列→CURRENCY/百分比列→PERCENTAGE/布尔列→BOOLEAN/混合列→STRING/空列→UNKNOWN/置信度评分/采样策略） |
| 🟢 绿 | 实现 `src/domain/services/table_column_classifier.py`：`classify_columns(rows: list[list[str]], sample_size: int = 50) -> list[ColumnInfo]` |
| 🔄 重构 | 正则模式库提取为常量、类型推断优先级排序 |

- [ ] Subtask 3.4: 🔴 红 — 编写列类型推断测试（≥15 个 test case，覆盖 7 种类型）
- [ ] Subtask 3.5: 🟢 绿 — 实现列类型推断最小代码（正则模式匹配 + 类型转换试探）
- [ ] Subtask 3.6: 🔄 重构 — 正则模式常量提取、优先级排序

#### TDD 循环 C：table_merge_resolver（合并单元格还原，V1）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_table_merge_resolver.py`（单行合并/单列合并/跨行跨列合并/无合并单元格/坐标覆盖计算/value 填充验证） |
| 🟢 绿 | 实现 `src/domain/services/table_merge_resolver.py`：`resolve_merged_cells(rows: list[list[str]], merge_ranges: list[tuple[int,int,int,int]]) -> list[MergedCell]` |
| 🔄 重构 | 坐标变换归一化 |

- [ ] Subtask 3.7: 🔴 红 — 编写合并单元格还原测试（≥8 个 test case，标记 V1）
- [ ] Subtask 3.8: 🟢 绿 — 实现合并单元格还原最小代码
- [ ] Subtask 3.9: 🔄 重构 — 完善 docstring

**完成标准/Definition of Done:**
- [ ] 3 个领域服务全部实现
- [ ] 所有领域服务测试通过
- [ ] 领域服务覆盖率 ≥ 90%
- [ ] 领域服务零外部依赖（仅 Python 标准库）


---

### Task 4: 基础设施层 — 表格提取器实现

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **说明：** 实现两个表格提取器：(1) `TableSemanticExtractor` — 通用表格语义增强编排器；(2) `PdfTableExtractor` — PDF 表格初始检测（pdfplumber）。
> `TableSemanticExtractor` 编排调用 Task 3 的领域服务；`PdfTableExtractor` 仅负责 PDF 表格的初始检测，语义增强委托给 `TableSemanticExtractor`。

#### TDD 循环 A：TableSemanticExtractor（通用语义提取编排器）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/document_parsing/test_table_semantic_extractor.py`（标准表格语义提取/无表头表格/空表格列表/领域服务异常降级/mock header_detector/mock column_classifier/mock merge_resolver/非表格 MIME 跳过） |
| 🟢 绿 | 实现 `src/infrastructure/document_parsing/table_semantic_extractor.py`：`TableSemanticExtractor.extract()` —— 编排调用领域服务 |
| 🔄 重构 | 降级策略完善、日志记录 |

- [ ] Subtask 4.1: 🔴 红 — 编写 TableSemanticExtractor 测试（mock 所有领域服务依赖）
- [ ] Subtask 4.2: 🟢 绿 — 实现 `TableSemanticExtractor` 最小代码
- [ ] Subtask 4.3: 🔄 重构 — 降级策略、类型注解

#### TDD 循环 B：PdfTableExtractor（PDF 表格初始检测 + pdfplumber）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/document_parsing/test_pdf_table_extractor.py`（mock pdfplumber：标准表格检测/多表格页面/无表格页面/空页面/合并单元格表格/跨页表格 V1/pdfplumber 未安装降级/逐页处理验证） |
| 🟢 绿 | 实现 `src/infrastructure/document_parsing/pdf_table_extractor.py`：`PdfTableExtractor.extract()` —— pdfplumber 表格检测 + 转换为 ParsedTable |
| 🔄 重构 | 添加 `pdfplumber` 至 `pyproject.toml` |

- [ ] Subtask 4.4: 🔴 红 — 编写 PdfTableExtractor 测试（mock pdfplumber）
- [ ] Subtask 4.5: 🟢 绿 — 实现 `PdfTableExtractor` 最小代码
- [ ] Subtask 4.6: 🔄 重构 — 添加 pdfplumber 依赖、完善降级

**完成标准/Definition of Done:**
- [ ] `TableSemanticExtractor` 实现完成，实现 `TableExtractorPort`
- [ ] `PdfTableExtractor` 实现完成，实现 `TableExtractorPort`
- [ ] 基础设施测试通过，覆盖率 ≥ 75%


---

### Task 5: 应用层 — DocumentParsingService 集成 + Composition Root 注册

**关联 AC:** AC-1, AC-6, AC-7

> **说明：** 将 `table_extractor` 以 Story 2-3 的 `layout_detector` 相同模式注入 `DocumentParsingService`，新增 `_apply_table_extraction()` 编排方法。
> 同步更新 `composition_root.py` 端口注册和 `pdf_parser.py` PDF 表格占位符替换。

#### TDD 循环 A：DocumentParsingService 集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/services/test_document_parsing_service.py`（table_extractor 注入/table_extractor=None 跳过/_apply_table_extraction 调用/mock table_extractor 返回增强 tables/WARNING 日志降级/超时保护/PDF 格式触发 pdf_table_extractor） |
| 🟢 绿 | 修改 `src/application/services/document_parsing_service.py`：新增可选参数 `table_extractor: TableExtractorPort | None = None`，实现 `_apply_table_extraction()` 方法 |
| 🔄 重构 | 降级策略与 `_apply_layout_detection()` 对齐 |

- [ ] Subtask 5.1: 🔴 红 — 编写 DocumentParsingService 集成测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 `_apply_table_extraction()` 编排方法
- [ ] Subtask 5.3: 🔄 重构 — 降级策略三场景：None/运行时异常/初始化失败

#### TDD 循环 B：PDFParser 集成 pdf_table_extractor

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/infrastructure/document_parsing/test_pdf_parser.py`（注入 pdf_table_extractor/tables 非空/pdf_table_extractor=None 保持空 tables） |
| 🟢 绿 | 修改 `src/infrastructure/document_parsing/pdf_parser.py`：新增可选参数 `table_extractor: TableExtractorPort | None = None`，替换 `tables=[]` 占位符 |
| 🔄 重构 | 删除第 109 行 TODO 注释 |

- [ ] Subtask 5.4: 🔴 红 — 编写 PDFParser 表格集成测试
- [ ] Subtask 5.5: 🟢 绿 — 实现 PDFParser 表格检测集成
- [ ] Subtask 5.6: 🔄 重构 — 清理 TODO 注释

#### TDD 循环 C：Composition Root 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 contract test 验证端口可解析（`test_port_contract_table_extractor.py` 中 `test_table_extractor_port_registered`） |
| 🟢 绿 | 修改 `src/composition_root.py`：注册 `table_extractor`/`pdf_table_extractor` 端口，注入到 `document_parsing_service` 和 `pdf_parser` |
| 🔄 重构 | 版本号升级、端口契约清单更新 |

- [ ] Subtask 5.7: 🔴 红 — 编写端口注册验证测试
- [ ] Subtask 5.8: 🟢 绿 — 实现 Composition Root 注册
- [ ] Subtask 5.9: 🔄 重构 — 版本升级 + 已存测试无回归验证

**完成标准/Definition of Done:**
- [ ] `DocumentParsingService` 集成完成（v1.1.0 → v1.2.0）
- [ ] `PDFParser` 表格占位符替换完成
- [ ] `composition_root.py` 注册完成
- [ ] 所有已有测试无回归
- [ ] 应用层覆盖率 ≥ 85%


---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-1, AC-2, AC-3, AC-7

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_arch_document_table.py`
- [ ] Subtask 6.2: 实现领域层零外部依赖验证（`ColumnType`/`ColumnInfo`/`MergedCell`/`ParsedTable`/`TableExtractorPort`/3 个领域服务均仅使用标准库）
- [ ] Subtask 6.3: 实现依赖方向验证（domain → application/infrastructure 禁止引用）
- [ ] Subtask 6.4: 实现 `TableExtractorPort` 端口在 domain/ports 中定义验证
- [ ] Subtask 6.5: 实现基础设施实现类满足 Protocol 验证（`isinstance(x, TableExtractorPort)`）
- [ ] Subtask 6.6: 实现循环依赖检测（使用 ruff `E` 规则或 `isort --check-only`）
- [ ] Subtask 6.7: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败


---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-5, AC-7

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_table_extraction.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_table_extraction.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 7.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 7.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 7.3: 运行集成测试 `tests/integration/test_integration_table_extraction.py`（端到端：解析→表格语义增强→事件发布）
- [ ] Subtask 7.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）— 领域层定义 `TableExtractorPort` 端口协议，基础设施层实现
- **设计约束:** 领域层零外部依赖（纯 Python 标准库）；依赖方向 domain ← application ← infrastructure
- **接口治理:** 统一端口注册（`PortSpec` 元数据 + `register_port()`）→ `composition_root.py` 唯一注册入口 → 契约测试验证
- **增强注入模式（Story 2-3 复用）:** 可选构造函数参数（`table_extractor: TableExtractorPort | None = None`）+ 降级策略（None→跳过 / 运行时异常→WARNING+原始结果 / 初始化失败→raise）
- **技术栈:** Python 3.11+; pdfplumber (MIT) 用于 PDF 表格检测; openpyxl (已有) 用于 XLSX 合并单元格信息

### 关键架构决策

**来源:** [`docs/developer/document-parser-spike.md`](../../docs/developer/document-parser-spike.md) - §5.1 PDF 解析库选择

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **pdfplumber (MIT)** | 专有表格检测算法、行列结构清晰、支持合并单元格识别、MIT 许可证、无额外系统依赖 | 基于文本位置坐标（非 ML），复杂版面表格可能漏检 | ✅ 9/10 |
| pypdf (BSD) | 已在项目中使用、纯 Python、轻量 | **无内置表格提取**，仅能提取文本 | 4/10 |
| camelot-py (MIT) | 高精度表格检测、支持多种解析模式 | 依赖 Ghostscript 系统级依赖、部署复杂 | 6/10 |
| PyMuPDF/fitz (AGPL) | 高性能、内置表格检测 | AGPL-3.0 许可证（企业商用需购买）、商业许可限制 | 5/10 |

**决策理由：**
1. pdfplumber 是 Python 生态中表格检测能力最强的 MIT 许可证库（企业商业软件合规）
2. 无 Ghostscript 等系统级依赖（与 camelot-py 对比），CI/CD 部署简单
3. pypdf（当前使用）无内置表格提取能力，无法满足 Story 2-4 需求
4. PyMuPDF 许可证限制（AGPL-3.0），不符合 SISYS 企业商业软件合规要求

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── ports/
│   │   └── table_extractor.py           # [NEW] TableExtractorPort Protocol
│   ├── services/
│   │   ├── table_header_detector.py     # [NEW] 表头检测领域服务
│   │   ├── table_column_classifier.py   # [NEW] 列类型推断领域服务
│   │   └── table_merge_resolver.py      # [NEW] 合并单元格还原领域服务 (V1)
│   └── value_objects/
│       ├── __init__.py                   # [MODIFY] 导出 ColumnType/ColumnInfo/MergedCell
│       └── parsed_document.py            # [MODIFY] 扩展 ParsedTable + 新增 ColumnType/ColumnInfo/MergedCell
│
├── application/
│   └── services/
│       └── document_parsing_service.py   # [MODIFY] 注入 table_extractor + _apply_table_extraction()
│
├── infrastructure/
│   └── document_parsing/
│       ├── table_semantic_extractor.py   # [NEW] TableSemanticExtractor（通用语义提取编排器）
│       ├── pdf_table_extractor.py        # [NEW] PdfTableExtractor（PDF 表格初始检测 pdfplumber）
│       └── pdf_parser.py                # [MODIFY] 集成 pdf_table_extractor，替换 tables=[]
│
└── composition_root.py                   # [MODIFY] 注册 table_extractor/pdf_table_extractor 端口

tests/
├── unit/
│   ├── domain/
│   │   ├── ports/test_table_extractor_port.py         # [NEW] 端口契约测试
│   │   ├── services/test_table_header_detector.py      # [NEW] 表头检测测试
│   │   ├── services/test_table_column_classifier.py    # [NEW] 列类型推断测试
│   │   ├── services/test_table_merge_resolver.py       # [NEW] 合并单元格测试
│   │   └── value_objects/test_parsed_document.py       # [MODIFY] 扩展值对象测试
│   ├── application/
│   │   └── services/test_document_parsing_service.py   # [MODIFY] 扩展集成测试
│   ├── infrastructure/
│   │   └── document_parsing/
│   │       ├── test_table_semantic_extractor.py        # [NEW]
│   │       ├── test_pdf_table_extractor.py             # [NEW]
│   │       └── test_pdf_parser.py                      # [MODIFY] 扩展表格集成测试
│   └── architecture/
│       └── test_arch_document_table.py                 # [NEW] 架构约束测试
├── integration/
│   └── test_integration_table_extraction.py            # [NEW] 端到端集成测试
├── acceptance/
│   ├── test_acceptance_table_extraction.feature        # [NEW] Gherkin 场景
│   └── test_acceptance_table_extraction.py             # [NEW] BDD 步骤实现
└── contracts/
    └── test_port_contract_table_extractor.py           # [NEW] 端口契约验证
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 2-3-布局信息保留](./2-3-layout-preservation-doclaynet.md)

**关键学习/Key Learnings:**
1. **可选增强注入模式** — layout_detector 作为 Optional 构造函数参数注入 DocumentParsingService；Story 2-4 的 table_extractor 应遵循同样模式（默认 None，支持优雅降级）
2. **降级策略一致性** — 三级降级：port=None → 跳过增强（无日志）；运行时异常 → WARNING 日志 + 返回原始结果；初始化失败（模型缺失/依赖缺失）→ raise（配置错误，不降级）
3. **值对象向后兼容扩展** — Story 2-2b 中 ParsedTable.metadata 字段新增使用 `field(default_factory=dict)`；Story 2-4 的新字段必须使用 `field(default=None)` 保持向后兼容
4. **空间匹配局限性** — PDFParser 不输出 per-element bbox，Story 2-3 的 `_apply_layout_detection` 回退到顺序匹配；Story 2-4 的 PDF 表格提取直接使用 pdfplumber 独立坐标系统，不依赖 PDFParser bbox
5. **asyncio.to_thread + CancelledError** — Story 2-2b 修复：`asyncio.to_thread()` 包装的同步操作被取消时要清理临时文件；Story 2-4 的 pdfplumber 调用同样需要 try/finally 保护
6. **MIME 类型一致性** — Story 2-2b 发现：composition_root 中 MIME 类型应与 domain 层 `DocumentFormat` 常量一致，不在 infrastructure 中重复定义

**应用到本故事/Applied to This Story:**
- [x] `table_extractor` 作为 Optional 构造函数参数注入 `DocumentParsingService`（默认 None）
- [x] 降级策略与 `_apply_layout_detection()` 对齐（三级降级）
- [x] `ParsedTable` 新字段全部 `field(default=None)` 保持向后兼容
- [x] PdfTableExtractor 使用 pdfplumber 独立坐标系统（不依赖 PDFParser）
- [x] pdfplumber 调用使用 `asyncio.to_thread()` + try/finally 清理
- [x] MIME 类型引用 domain 层 `DocumentFormat` 常量

**来源:** [Story 2-2a-基础格式解析](./2-2a-document-parsing-basic-formats.md)

**关键学习/Key Learnings:**
1. **PDFParser 表格占位符** — `pdf_parser.py:109` 明确标注 `"表格检测：MVP 仅契约预留，真实检测推迟至 Story 2-4"`，本 Story 必须替换此占位符
2. **错误消息清理** — 异常 `str(e)` 禁止直接写入 metadata（安全：防止内部路径泄露）
3. **安全漏洞** — python-docx XXE 注入（CWE-611），任何 XML 格式解析需要 XXE 保护（与 Story 2-4 低相关，但提醒注意 pdfplumber 安全性）

**应用到本故事/Applied to This Story:**
- [x] PDFParser 表格占位符替换为 pdfplumber 调用
- [x] 领域服务异常消息使用预定义的 sanitized 错误消息
- [ ] pdfplumber 安全性审查（MIT 许可证，已确认无已知 CVE）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.8 |
| **Version** | create-story workflow — SDD+TDD 融合模式模板 v2.7.0 |
| **Execution Date** | 2026-06-04 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `docs/developer/story-template.md` (v2.7.0) |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-3-layout-preservation-doclaynet.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` §Epic 2, Story 2-4 提取
- [x] 架构约束从 `architecture.md` §1.3/§9/§11 和 `story-template.md` §六边形架构约束 提取
- [x] 前一个故事学习经验从 Story 2-3/2-2a 整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（Story 2-3 模式复用）
- [x] AC→Task→Subtask 追溯矩阵完整（7 AC × 8 Task）
- [x] 每个 Task 含独立 TDD 红→绿→重构循环
- [x] 技术选型决策记录（pdfplumber MIT vs PyMuPDF AGPL vs camelot-py）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-4-table-semantic-extraction.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/table_extractor.py` — TableExtractorPort 端口协议
- `src/domain/services/table_header_detector.py` — 表头检测领域服务
- `src/domain/services/table_column_classifier.py` — 列类型推断领域服务
- `src/domain/services/table_merge_resolver.py` — 合并单元格还原领域服务（V1）
- `src/infrastructure/document_parsing/table_semantic_extractor.py` — 通用表格语义提取编排器
- `src/infrastructure/document_parsing/pdf_table_extractor.py` — PDF 表格初始检测（pdfplumber）
- `src/domain/value_objects/parsed_document.py` — 扩展 ParsedTable + 新增 ColumnType/ColumnInfo/MergedCell
- `src/application/services/document_parsing_service.py` — 集成 `_apply_table_extraction()`
- `src/infrastructure/document_parsing/pdf_parser.py` — 替换表格占位符
- `src/composition_root.py` — 注册端口 + 依赖注入
- `tests/unit/domain/ports/test_table_extractor_port.py`
- `tests/unit/domain/services/test_table_header_detector.py`
- `tests/unit/domain/services/test_table_column_classifier.py`
- `tests/unit/domain/services/test_table_merge_resolver.py`
- `tests/unit/infrastructure/document_parsing/test_table_semantic_extractor.py`
- `tests/unit/infrastructure/document_parsing/test_pdf_table_extractor.py`
- `tests/unit/architecture/test_arch_document_table.py`
- `tests/contracts/test_port_contract_table_extractor.py`
- `tests/integration/test_integration_table_extraction.py`
- `tests/acceptance/test_acceptance_table_extraction.feature`
- `tests/acceptance/test_acceptance_table_extraction.py`
- `pyproject.toml` — 添加 pdfplumber 依赖

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.4 |
| **Story Key** | 2-4-table-semantic-extraction |
| **File** | `_bmad-output/implementation-artifacts/stories/2-4-table-semantic-extraction.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0（FR-DM-04 MVP 必需） / 执行优先级 P1-4 |
| **覆盖 FR** | FR-DM-04（表格行列语义提取、结构化 JSON 输出）/ FR-DM-12（合并单元格语义还原与跨页表格识别，V1） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-7，8 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-7，7 个 AC）
3. [x] Architecture constraints extracted 架构约束已提取（六边形架构/端口契约/领域零依赖）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 2-3 + 2-2a）
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

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-06-04
**最后更新/Last Updated:** 2026-06-04
**更新说明/Description:**
- v1.0.0: 创建故事文件（遵循 SDD+TDD 融合模式模板 v2.7.0）
