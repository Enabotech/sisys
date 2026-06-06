# Story 2-3: 文档版面信息保留（DocLayNet 标准）

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式，通过 ONNX 运行时实现跨平台推理,
**So that** 支持高保真溯源至原始文档坐标点，为 Epic 3 Story 3.8 Bounding Box 级溯源提供数据基础。

### 业务价值

Epic 2 文档与数据管理的关键路径 Story（P0-3），属跨 Epic 硬依赖（→ Epic 3 Story 3.8 高保真溯源 Bounding Box）。

在 Story 2-2a 基础格式解析（PDF/DOCX/TXT）和 2-2b 扩展格式解析（PPTX/XLSX 等）完成后，
本 Story 引入版面检测模型，为 `ParsedElement` 和 `ParsedTable` 的 `bbox` 字段填充真实坐标值（当前所有解析器均输出 `bbox=None`）。

**核心假设：** MVP 阶段版面检测聚焦于 PDF 文档（可渲染为页面图像进行检测），
其他格式（DOCX 等）在后续 Story 中按需扩展。DocLayNet 是一个数据集标准（11 类版面元素），
而非单一模型——推荐方案为 **Docling Layout (RT-DETR) + ONNX Runtime**，
MIT 许可证，原生 ONNX 模型预导出，符合 SISYS 企业商业软件合规要求。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: LayoutDetector 端口定义（领域层）

**Given** 需要定义版面检测的领域端口抽象
**When** 在 `src/domain/ports/` 创建 `LayoutDetector` Protocol
**Then** 端口定义 `detect(image_bytes: bytes, page_number: int) -> list[BoundingBoxResult]` 方法
**And** `BoundingBoxResult` 为新增领域值对象（`@dataclass(frozen=True)`），包含 `label: str`（DocLayNet 11 类）、`bbox: BoundingBox`、`confidence: float`（页码信息由 `bbox.page` 承载，无需冗余字段）
**And** 端口类使用 `@runtime_checkable` 装饰器，继承 `Protocol`
**And** 端口接口不依赖任何第三方库（领域层零依赖原则）

**验证标准/Validation Criteria:**
- [ ] `LayoutDetector` Protocol 定义在 `src/domain/ports/layout_detector.py`
- [ ] `BoundingBoxResult` 值对象定义在 `src/domain/value_objects/parsed_document.py`（与已有 `BoundingBox`/`ParsedElement` 共处）
- [ ] `BoundingBoxResult` 实现 `to_dict()` 序列化方法
- [ ] 领域层仅使用 Python 标准库（`dataclasses`、`typing`、`abc`）

### AC-2: ONNX 版面检测实现（基础设施层）

**Given** Docling Layout ONNX 模型文件已就绪
**When** 初始化 `OnnxLayoutDetector` 并调用 `detect()` 方法
**Then** 使用 `onnxruntime.InferenceSession` 加载 ONNX 模型
**And** 接收页面图像字节（PNG/JPEG 格式），输出 `BoundingBoxResult` 列表
**And** 支持 CPU 推理（`CPUExecutionProvider`，默认）和 GPU 推理（`CUDAExecutionProvider`，可选）
**And** 检测到的元素类型映射至 DocLayNet 11 类标签（Caption/Footnote/Formula/List-item/Page-footer/Page-header/Picture/Section-header/Table/Text/Title）
**And** 实现必须将 `detect()` 的 `page_number` 参数传入每个返回 `BoundingBoxResult` 的 `bbox.page` 字段（单一数据源原则）

**验证标准/Validation Criteria:**
- [ ] `OnnxLayoutDetector` 实现 `LayoutDetector` Protocol
- [ ] 推理延迟 P95 < 500ms/页（CPU），P95 < 100ms/页（GPU 基准）
- [ ] 坐标准确率 ≥ 95%（检测到的 bbox 与实际版面元素位置匹配，使用 DocLayNet 验证集评估）
- [ ] 模型文件缺失时抛出明确 `FileNotFoundError`（含模型下载指引）
- [ ] `onnxruntime` 库缺失时抛出 `ImportError`（含安装指引 `pip install onnxruntime`）
- [ ] 实现位于 `src/infrastructure/document_parsing/onnx_layout_detector.py`
- [ ] 支持 `__init__(model_path: str, device: str = "cpu")` 构造函数

### AC-3: 解析管线集成（应用层编排）

**Given** 文档（PDF）已通过文本解析器（`PDFParser`）提取文本内容
**And** 文档页面可渲染为图像（用于版面检测模型输入）
**When** `DocumentParsingService` 编排解析流程
**Then** 版面检测结果（`BoundingBoxResult`）与 `ParsedDocument` 中的 `ParsedElement`/`ParsedTable` 按页面匹配
**And** 匹配策略：基于 bbox 的空间 IoU（Intersection over Union）将检测到的版面区域与文本元素关联
**And** 填充 `ParsedElement.bbox` / `ParsedTable.bbox` 为真实 `BoundingBox` 值（替换当前 `None`）
**And** 输出 `ParsedDocument` 的 `to_dict()` 中 `bbox` 字段不再为 `null`

**验证标准/Validation Criteria:**
- [ ] PDF 解析后 `ParsedElement.bbox` 为非 None 值（bbox 匹配成功的元素）
- [ ] bbox 匹配容错：元素级别 IoU > 0.3 视为匹配（**严格大于**，IoU 恰好 = 0.3 时不匹配）
- [ ] PDF 每页渲染为 PNG 图像后传入 `LayoutDetector.detect()`（通过 `PdfPageRendererPort`）
- [ ] 版面检测不影响文本解析准确性（已有解析流程逻辑不受破坏）
- [ ] 非 PDF 格式的 `ParsedElement.bbox` 保持 None（无回归，除非该格式实现页面渲染）
- [ ] `ParsedElement.confidence` 保持原始值 1.0 不被覆盖；版面检测置信度记录在 `metadata["layout_confidence"]` 中
- [ ] 整合流程通过 `DocumentParsingService` 编排

> **降级策略：** 参见 Dev Notes「降级策略 Graceful Degradation Policy」小节，定义了端口未注入/推理运行时错误/渲染失败/空检测等场景的处理方式。

### AC-4: Composition Root 注册与版本升级

**Given** 版面检测功能已实现
**When** 在 `src/composition_root.py` 注册新端口
**Then** `layout_detector` 端口注册为 `LayoutDetector` 接口
**And** 生命周期为 `SINGLETON`（ONNX 模型会话可复用，避免重复加载）
**And** `document_parsing_service` 注入 `layout_detector` 和 `pdf_page_renderer` 依赖（新增可选构造函数参数 `layout_detector: LayoutDetector | None = None`、`pdf_page_renderer: PdfPageRendererPort | None = None`，支持优雅降级）
**And** `document_parsing_service` 版本从 v1.0.0 升级至 v1.1.0（编排逻辑新增版面检测步骤）
**And** `document_parser`（`CompositeDocumentParser`）版本保持 v1.1.0 不变（版面检测是新端口职责，不在 DocumentParserPort 调用链内）

**验证标准/Validation Criteria:**
- [ ] `layout_detector` 端口在 Composition Root 中注册（SINGLETON lifetime）
- [ ] `pdf_page_renderer` 端口在 Composition Root 中注册（SCOPED lifetime）
- [ ] `DocumentParsingService.__init__` 新增 `layout_detector: LayoutDetector | None = None` 和 `pdf_page_renderer: PdfPageRendererPort | None = None` 可选参数
- [ ] Composition Root lambda 工厂传入 `layout_detector=resolver.resolve("layout_detector")` 和 `pdf_page_renderer=resolver.resolve("pdf_page_renderer")`
- [ ] `document_parsing_service` 版本号更新至 v1.1.0
- [ ] 端口合约测试同步更新版本断言
- [ ] 已有测试全部保持通过（无回归）

### AC-5: Bounding Box 级溯源数据可用性

**Given** 版面检测结果已写入 `ParsedDocument` 的 bbox 字段
**When** 下游 Epic 3 Story 3.8 消费 `ParsedDocument.to_dict()` 数据
**Then** `ParsedElement` 结构包含 `{"content": "...", "bbox": {"x": float, "y": float, "width": float, "height": float, "page": int}, "confidence": float, "metadata": {"layout_confidence": float, ...}}`
**And** `ParsedTable` 结构包含 `{"rows": [...], "bbox": {...}, "confidence": float, "metadata": {"layout_confidence": float, ...}}`
**And** 坐标值为绝对像素坐标（基于页面图像原始分辨率）
**And** `document.metadata["parse_result"]` JSONB 包含完整 bbox 数据

**验证标准/Validation Criteria:**
- [ ] `ParsedElement.to_dict()` 输出 `bbox` 为 dict 或 null
- [ ] `ParsedTable.to_dict()` 输出 `bbox` 为 dict 或 null
- [ ] bbox dict 含完整 5 字段（x/y/width/height/page）
- [ ] 溯源测试：可通过元素坐标定位回原始文档对应区域（精确到 ±10 像素）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 复用 `DocumentProcessed` 事件（Story 2-2a 已定义），**不新增事件** — 版面检测结果通过 `parse_result` dict 传递
- [ ] 复用 `DocumentUploaded` 事件触发解析流程（不变）

#### 数据模型 (Data Models)
- [ ] **新增** `BoundingBoxResult` 值对象（`@dataclass(frozen=True)`）：
  - 字段：`label: str`（DocLayNet 11 类标签）、`bbox: BoundingBox`、`confidence: float`
  - 页码信息由 `bbox.page` 承载（`BoundingBox` 已含 `page: int` 字段），避免双重数据源
  - 方法：`to_dict()` 序列化
  - 位于 `src/domain/value_objects/parsed_document.py`（与已有 `BoundingBox`/`ParsedElement` 共文件）
- [ ] **复用** `BoundingBox`（`x/y/width/height/page`）—— 已存在，无需修改
- [ ] **复用** `ParsedDocument`/`ParsedPage`/`ParsedElement`/`ParsedTable` —— bbox 字段已预留，仅需填充值
- [ ] **追加导出** `BoundingBoxResult` 至 `src/domain/value_objects/__init__.py`

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `LayoutDetector` 端口契约（`src/domain/ports/layout_detector.py`）：
  - `@runtime_checkable` + `Protocol`
  - `detect(image_bytes: bytes, page_number: int) -> list[BoundingBoxResult]`
- [ ] **新增** `PdfPageRendererPort` 端口契约（`src/domain/ports/pdf_page_renderer.py`）：
  - `@runtime_checkable` + `Protocol`
  - `render_page(file_path: str, page_number: int) -> bytes`（返回 PNG 图像字节）
- [ ] **更新** `DocumentParserPort` 版本说明（接口签名不变，但输出包含 bbox 数据）
- [ ] **端口注册** — 在 `src/composition_root.py` 中调用 `register_port()` 注册 `layout_detector` 和 `pdf_page_renderer` 端口
- [ ] **端口契约门禁**（`src/domain/ports/contract_gate.py`）：新端口变更通过兼容性检查
- [ ] **端口契约测试**（`tests/contracts/test_port_contract_layout_detector.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称 `layout_detector`/`pdf_page_renderer`、版本 `v1.0.0`、owner `epic-2`

**端口契约清单：**

| 端口名称 | 接口 | 实现 | 注册位置 | Lifetime | Version | Owner |
|---------|------|------|----------|----------|---------|-------|
| `layout_detector` | `LayoutDetector` | `OnnxLayoutDetector` | domain/ports/layout_detector.py | SINGLETON | v1.0.0 | epic-2 |
| `pdf_page_renderer` | `PdfPageRendererPort` | `PdfPageRenderer` | domain/ports/pdf_page_renderer.py | SCOPED | v1.0.0 | epic-2 |
| `document_parser` | `DocumentParserPort` | `CompositeDocumentParser` | domain/ports/document_parser.py | SCOPED | v1.1.0（不变） | epic-2 |
| `document_parsing_service` | `DocumentParsingService` | — | application/services/ | SCOPED | v1.0.0→v1.1.0 | epic-2 |

> **版本升级说明：**
> - `document_parsing_service` v1.1.0：构造函数新增可选参数 `layout_detector: LayoutDetector | None = None` 和 `pdf_page_renderer: PdfPageRendererPort | None = None`，编排逻辑增加版面检测步骤。向后兼容（可选参数，默认 `None` 时跳过版面检测）。
> - `document_parser`（`CompositeDocumentParser`）版本保持 v1.1.0 不变 — 版面检测是 `LayoutDetector` 独立端口的职责，不在 `DocumentParserPort` 的调用链内。
> - `pdf_page_renderer`：PDF 页面渲染端口（`render_page(file_path, page_number) -> bytes`），pypdfium2 + Pillow 实现。仅 PDF 格式需要，非 PDF 格式时跳过渲染步骤。

#### API 契约 (API Contract)
- [x] 复用 `POST /api/v1/documents` 上传端点（不变）
- [x] 复用 `GET /api/v1/documents/{document_id}` 查询端点（不变）
- [x] 解析结果存储于 `Document.metadata["parse_result"]` JSONB 字段（不变，bbox 数据内含）

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
- 禁止导入：包括且不限于 onnxruntime, numpy, pillow, pypdf, fastapi, sqlalchemy 等

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_document_layout.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_document_layout.py`
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

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
| **TDD 单元测试** | BoundingBoxResult 值对象 | 创建/序列化/to_dict() | `test_parsed_document.py`（扩展） | Task 2 |
| **TDD 单元测试** | LayoutDetector 端口 | Protocol 合规/类型检查 | `test_layout_detector_port.py` | Task 2 |
| **TDD 单元测试** | OnnxLayoutDetector | ONNX 推理/bbox 检测/mock | `test_onnx_layout_detector.py` | Task 3 |
| **TDD 单元测试** | PdfPageRenderer | PDF 页面渲染/mock pypdfium2 | `test_pdf_page_renderer.py` | Task 3 |
| **TDD 单元测试** | 版面检测整合 | bbox 匹配/合并逻辑 | `test_layout_matching.py` | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_document_layout.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_document_layout.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_document_layout.feature` | Task 5 |
| **TDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_document_layout.py` | Task 5 |
| **TDD 契约测试** | 端口契约 / LayoutDetector | 注册/版本/兼容性/实现解析 | `test_port_contract_layout_detector.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖/LayoutDetector 在 domain | `test_arch_document_layout.py` | Task 5 |
| **集成测试** | 端到端版面检测流程 | MinIO下载→解析→布局检测→bbox合并→事件发布 | `test_integration_document_layout.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥ 80%**（`pytest --cov=src`）— 目标值，当前 CI 未配置 `--cov-fail-under`，以实际测试通过为准
- [ ] **领域层覆盖率 ≥ 90%**（`pytest --cov=src/domain`）- 新增 `BoundingBoxResult`、`LayoutDetector` Protocol
- [ ] **基础设施层覆盖率 ≥ 75%**（`pytest --cov=src/infrastructure`）- `OnnxLayoutDetector` 实现
- [ ] **应用层覆盖率 ≥ 85%**（`pytest --cov=src/application`）- 编排逻辑扩展
- [ ] **集成测试覆盖率 ≥ 70%**（`pytest --cov=tests/integration`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

- [ ] ONNX 模型测试：使用 mock `InferenceSession` 或小型测试模型（非真实 100MB+ 模型文件）
- [ ] 并行测试 `pytest tests/ -n 8` 通过（ONNX mock 不共享状态）
- [ ] 连续 5 次运行无随机失败
- [ ] BDD 步骤函数：使用 `event_loop.run_until_complete()` 运行 async 测试（不使用 `@pytest.mark.asyncio`）
- [ ] `asyncio.Lock` 使用类变量而非实例变量

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | LayoutDetector + PdfPageRendererPort 端口定义 + BoundingBoxResult 值对象 | Task 0 + Task 1 + Task 2 | Task 0: 端口契约定义; Task 1: BoundingBoxResult; Task 2: LayoutDetector + PdfPageRendererPort Protocol | `test_parsed_document.py`; `test_layout_detector_port.py` |
| AC-2 | ONNX 版面检测 + PDF 页面渲染实现 | Task 3 | 3a: OnnxLayoutDetector; 3b: PdfPageRenderer | `test_onnx_layout_detector.py`; `test_pdf_page_renderer.py` |
| AC-3 | 解析管线集成 | Task 4 | 4a: 版面检测整合服务; 4b: bbox 匹配算法 | `test_layout_matching.py`; `test_document_parsing_service.py` |
| AC-4 | Composition Root 注册 | Task 4 | 4c: 端口注册 + 版本升级 | `test_port_contract_layout_detector.py` |
| AC-5 | Bounding Box 溯源数据可用性 | Task 5 | 5a: 验收场景验证 | `test_acceptance_document_layout.feature` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、端口契约、验收标准与六边形架构边界。

- [x] Subtask 0.1: 定义 `BoundingBoxResult` 值对象 Schema（`label`/`bbox`/`confidence`/`to_dict()`），更新 `__init__.py` 导出
- [x] Subtask 0.2: 定义 `LayoutDetector` 端口契约（`src/domain/ports/layout_detector.py`）—— `@runtime_checkable` Protocol
- [x] Subtask 0.2a: 定义 `PdfPageRendererPort` 端口契约（`src/domain/ports/pdf_page_renderer.py`）—— `@runtime_checkable` Protocol，`render_page(file_path, page_number) -> bytes`
- [x] Subtask 0.3: 更新端口注册中心（`registry.py`）与端口契约门禁（`contract_gate.py`）
- [x] Subtask 0.4: 编写端口契约测试 `tests/contracts/test_port_contract_layout_detector.py`
- [x] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_document_layout.feature`
- [x] Subtask 0.6: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_document_layout.py`
- [x] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: `BoundingBoxResult` 值对象定义

**关联 AC:** AC-1

> **说明：** `BoundingBoxResult` 是 DocLayNet 版面检测输出的值对象，表示一个检测到的版面元素。
> 与已有 `BoundingBox`（纯坐标）不同，`BoundingBoxResult` 携带标签（label）和置信度，代表"某个类型的元素位于某坐标"。

#### TDD 循环 A：BoundingBoxResult 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/value_objects/test_parsed_document.py`（`TestBoundingBoxResult` 类：创建验证/标签枚举/to_dict 序列化/frozen 不可变性） |
| 🟢 绿 | 在 `src/domain/value_objects/parsed_document.py` 实现 `BoundingBoxResult` 数据类（`@dataclass(frozen=True)`，含 `label`/`bbox`/`confidence`/`to_dict()`） |
| 🔄 重构 | 更新 `src/domain/value_objects/__init__.py` 导出；验证 `ParsedElement.to_dict()` 与 `BoundingBoxResult.to_dict()` 输出一致性 |

- [x] Subtask 1.1: 🔴 红 — 编写 `TestBoundingBoxResult` 测试类（值对象创建/字段验证/to_dict 序列化/不可变性/边缘 case）
- [x] Subtask 1.2: 🟢 绿 — 实现 `BoundingBoxResult` 值对象最小代码
- [x] Subtask 1.3: 🔄 重构 — 完善 docstring、添加 Google 中文注释、更新 `__init__.py` 导出

**完成标准/Definition of Done:**
- [ ] `BoundingBoxResult` 值对象实现完成
- [ ] `test_parsed_document.py` 扩展测试通过
- [ ] 值对象覆盖率 ≥ 90%

---

### Task 2: `LayoutDetector` 端口协议定义

**关联 AC:** AC-1

#### TDD 循环 A：LayoutDetector Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_layout_detector_port.py`（验证 Protocol 可被实现类满足/runtime_checkable/isinstance 检查/接口签名约束） |
| 🟢 绿 | 在 `src/domain/ports/layout_detector.py` 实现 `LayoutDetector` Protocol（`detect(image_bytes, page_number) -> list[BoundingBoxResult]`） |
| 🔄 重构 | 完善 docstring、更新端口注册清单 |

- [x] Subtask 2.1: 🔴 红 — 编写 `TestLayoutDetectorPort`（Protocol 合规检查/实现类 isinstance 验证/签名约束）
- [x] Subtask 2.2: 🟢 绿 — 实现 `LayoutDetector` Protocol 最小代码（已在 Task 0 Subtask 0.2 完成）
- [x] Subtask 2.3: 🔄 重构 — Google 中文注释、端口文档完善（已在 Task 0 完成）

**完成标准/Definition of Done:**
- [ ] `LayoutDetector` Protocol 定义完成
- [ ] 端口协议测试通过
- [ ] 领域层零外部依赖（仅标准库）

---

### Task 3: `OnnxLayoutDetector` 基础设施实现

**关联 AC:** AC-2

> **说明：** 实现基于 onnxruntime 的版面检测器。ONNX 模型文件不作为源码提交，通过环境变量 `SISYS_LAYOUT_MODEL_PATH` 或默认路径 `~/models/docling-layout-heron.onnx` 定位。
> 模型下载指引：https://huggingface.co/docling-project/docling-layout-heron-onnx

#### TDD 循环 A：OnnxLayoutDetector 核心实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/document_parsing/test_onnx_layout_detector.py`（mock onnxruntime.InferenceSession：初始化验证/CPU 提供者/detect 调用模型/模型文件缺失/空图像/单元素检测/多元素检测/GPU 提供者参数） |
| 🟢 绿 | 实现 `src/infrastructure/document_parsing/onnx_layout_detector.py`（`__init__` 加载模型/`detect` 推理/输出后处理/错误处理） |
| 🔄 重构 | 提取 `_preprocess`/`_postprocess` 私有方法；添加性能日志；错误信息本地化 |

- [x] Subtask 3.1: 🔴 红 — 编写 `TestOnnxLayoutDetector` 测试（mock onnxruntime 全场景：初始化/CPU/GPU/模型缺失/推理失败/空图像返回空列表/多元素检测/confidence 范围 [0,1]/xyxy→xywh 坐标转换验证）
- [x] Subtask 3.2: 🟢 绿 — 实现 `OnnxLayoutDetector` 类（onnxruntime.InferenceSession 封装/预处理占位/后处理占位/Provider 选择）
- [x] Subtask 3.3: 🔄 重构 — 提取预处理/后处理逻辑；完善 docstring；添加日志

**完成标准/Definition of Done:**
- [ ] `OnnxLayoutDetector` 实现完成
- [ ] 所有 mock 测试通过（不依赖真实 ONNX 模型文件）
- [ ] `ruff check` + `mypy` 通过
- [ ] 基础设施层覆盖率 ≥ 75%

---

### Task 4: 解析管线整合与应用层编排

**关联 AC:** AC-3, AC-4

> **说明：** 本 Task 包含三个 TDD 循环：
> - 循环 A：bbox 匹配算法（基于空间 IoU 将版面检测结果与文本元素关联）
> - 循环 B：`DocumentParsingService` 编排扩展（注入 layout_detector，增加版面检测步骤）
> - 循环 C：Composition Root 注册（新端口、版本升级、ALLOWED_TEMP_SUFFIXES 扩展）

#### TDD 循环 A：Bbox 匹配算法

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_layout_matching.py`（单元素匹配/多元素匹配/IoU 阈值边界/无重叠返回 None/表格式匹配/不同页面隔离/空检测结果/空元素列表） |
| 🟢 绿 | 实现 `src/domain/services/layout_matching.py` 辅助函数（空间 IoU 计算/贪心匹配/阈值过滤 IoU > 0.3，纯领域逻辑零外部依赖，与 `cost_calculator.py` 等领域服务共处） |
| 🔄 重构 | 提取 IoU 计算逻辑；添加边界 case 防护；完善类型注解 |

- [x] Subtask 4.1: 🔴 红 — 编写 `TestBboxMatching`（IoU 计算/单元素匹配/多元素贪心匹配/**IoU 边界：恰好 0.3 不匹配 / 0.3001 匹配 / 1.0 完全重叠**/不同 page_number 不匹配/空输入处理/表格 bbox 匹配/负坐标防御）
- [x] Subtask 4.2: 🟢 绿 — 实现 bbox 匹配逻辑最小代码（位于 `src/domain/services/layout_matching.py`）
- [x] Subtask 4.3: 🔄 重构 — 添加 docstring/性能注释/类型注解

#### TDD 循环 B：DocumentParsingService 编排扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/services/test_document_parsing_service.py`（验证 layout_detector 注入/PDF 解析后 bbox 不为 None/非 PDF 格式 bbox 保持 None/layout_detector 缺失时降级处理） |
| 🟢 绿 | 扩展 `DocumentParsingService`（注入 layout_detector、注入 pdf_page_renderer、编排逻辑增加版面检测步骤、PDF 页面渲染为图像、调用 detect()、调用 bbox 匹配） |
| 🔄 重构 | 提取 `_apply_layout_detection()` 私有方法；添加 layout_detector=None 优雅降级 |

> **架构决策：PDF 页面渲染集成路径**
>
> `DocumentParsingService`（应用层）需要调用 PDF 页面渲染（基础设施层）将 PDF 页面转为图像字节。
> 为保持六边形架构依赖方向，采用 **端口抽象** 模式：
>
> | 方案 | 说明 | 选择 |
> |------|------|------|
> | A: `PdfPageRendererPort` 端口 | 在 domain 层定义 `render_page(file_path, page_number) -> bytes` Protocol，infrastructure 层用 pypdfium2 实现 | **推荐** — 架构干净，应用层仅依赖端口 |
> | B: 合并到 `OnnxLayoutDetector` | 端口方法改为 `detect_pdf_page(file_path, page_number)`，内部处理渲染+推理 | 可选 — 减少端口数量但耦合渲染与检测 |
>
> **推荐方案 A**：`PdfPageRendererPort` 与 `LayoutDetector` 是不同关注点（渲染 vs 检测），分开便于测试和替换。
> 实现位于 `src/infrastructure/document_parsing/pdf_page_renderer.py`（pypdfium2 + Pillow），
> 在 Composition Root 注册为 SCOPED 生命周期，通过构造函数注入到 `DocumentParsingService`。

- [x] Subtask 4.4: 🔴 红 — 编写 Service 编排扩展测试（layout_detector 注入/pdf 版面检测/非 pdf 跳过/layout_detector 缺失时降级）
- [x] Subtask 4.5: 🟢 绿 — 扩展 `DocumentParsingService` 编排逻辑（注入 layout_detector + pdf_page_renderer，PDF 格式触发版面检测，合并 bbox）
- [x] Subtask 4.6: 🔄 重构 — 提取私有方法；完善日志；确保无回归（已有 166 测试通过）

#### TDD 循环 C：Composition Root 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 创建 `tests/contracts/test_port_contract_layout_detector.py`（验证 layout_detector 端口注册/版本 v1.0.0/SINGLETON lifetime/接口类型）；确认 `tests/contracts/test_port_contract_document_parser.py` 仍通过（回归验证） |
| 🟢 绿 | 在 `src/composition_root.py` 注册 `layout_detector` + `pdf_page_renderer`；升级 document_parsing_service 版本至 v1.1.0；composition_root lambda 工厂传入两个依赖 |
| 🔄 重构 | 验证完整端口链：layout_detector → document_parsing_service → document_parser |

- [x] Subtask 4.7: 🔴 红 — 扩展契约测试（layout_detector 端口注册/版本/接口类型/生命周期为 SINGLETON）
- [x] Subtask 4.8: 🟢 绿 — Composition Root 注册 `layout_detector` + `pdf_page_renderer` + 版本升级
- [x] Subtask 4.9: 🔄 重构 — 验证完整端口链：layout_detector → document_parsing_service → document_parser

**完成标准/Definition of Done:**
- [x] bbox 匹配算法实现完成
- [x] DocumentParsingService 编排扩展完成
- [x] Composition Root 注册完成
- [x] 端口契约测试通过
- [x] 已有测试全部保持通过（无回归）
- [x] 应用层覆盖率 ≥ 85%

---

### Task 5: SDD 架构验证与开发结束验收

**关联 AC:** AC-5

> **性质说明：** 本 Task 包含两部分：(1) SDD 架构约束验证测试（验证六边形架构/依赖方向/领域层零依赖）; (2) 开发结束验收测试（收尾交付物与完成清单最终确认）。

#### 架构验证测试实现

- [x] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_document_layout.py`
  - 验证 `OnnxLayoutDetector` 位于 `infrastructure` 层（不污染 domain/application）
  - 验证 `LayoutDetector` Protocol 位于 `domain` 层（零 onnxruntime/numpy 依赖）
  - 验证 `BoundingBoxResult`/`BoundingBox` 位于 `domain` 层（仅标准库依赖）
  - 验证基础设施层实现 `LayoutDetector` Protocol（`isinstance` 检查）
  - 验证依赖方向合规（domain → application → infrastructure → interfaces 各层约束）

- [x] Subtask 5.2: 创建 `tests/integration/test_integration_document_layout.py`
  - 端到端版面检测流程：MinIO 下载 PDF → 文本解析 → PDF 页面渲染（PdfPageRendererPort）→ 版面检测 → bbox 合并 → `DocumentProcessed` 事件发布
  - 使用真实 pypdfium2 库渲染页面图像（小 PDF，1-2 页）
  - mock ONNX 推理（避免真实模型依赖）
  - 验证 `parse_result` JSONB 中 bbox 不为 null

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_document_layout.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_document_layout.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [x] Subtask 5.3: 场景 1 — 验证 `src` 完成清单的逐项确认（BoundingBoxResult 值对象/LayoutDetector 端口/OnnxLayoutDetector 实现/排版编排整合/Composition Root 注册）
- [x] Subtask 5.4: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [x] Subtask 5.5: 运行开发结束验收测试并确认通过
- [x] Subtask 5.6: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过
- [x] 测试输出清晰的合规报告
- [x] 任何违规都会导致测试失败
- [x] `src` 完成清单已逐项验证确认
- [x] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [x] 开发结束验收测试通过
- [x] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ CQRS + 事件驱动
- **设计约束:** 领域层零外部依赖、依赖方向自上而下、端口通过 Composition Root 统一注册
- **接口治理:** 统一端口注册（PortSpec）、Registry/Resolver/ContractGate、契约优先、版本化兼容
- **技术栈:** Python 3.11+、onnxruntime 1.17+、pypdf 4.x、Pillow 10.x、pypdfium2（PDF 页面光栅化）

### 关键架构决策

**来源:** [doclaynet-preparation.md](../../docs/developer/doclaynet-preparation.md) — DocLayNet 技术调研

**版面检测模型选型：**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Docling Layout (RT-DETR) + ONNX Runtime** | MIT 许可证、原生 ONNX 模型预导出、IBM/LF AI 维护、DocLayNet 11 类标准输出、安装轻量 | 模型文件较大（~30-200MB）、CPU 推理偏慢（100-200ms/页） | ✅ 9/10 |
| DocLayout-YOLO | 推理速度快（YOLO 架构）、mAP 79.7% | AGPL-3.0 许可证（Ultralytics 框架）、商业闭源需购买 Enterprise License | 7/10 |
| PaddleOCR PP-Structure | 中文支持最佳、Apache-2.0、23 类版面元素 | PaddlePaddle 重框架依赖、ONNX 导出不完整、Python 3.11+ 兼容性待验证 | 6/10 |

**决策理由：**
1. Docling Layout 是 DocLayNet 生态的官方继承者（IBM/LF AI 基金会项目），与 Story 需求中的 "DocLayNet 标准格式" 完全对齐
2. MIT 许可证无合规风险，适合 SISYS 企业商业软件
3. 官方已提供预导出的 ONNX 模型（docling-layout-heron-onnx），无需手动转换
4. onnxruntime 轻量依赖（~10MB pip 包），符合六边形架构"基础设施层可替换"原则

### DocLayNet 11 类版面元素 → ParsedElement 映射

| DocLayNet 类别 | 编号 | 映射到 ParsedElement | 备注 |
|----------------|------|---------------------|------|
| Caption | 1 | `ParsedElement(content=text, metadata={"category": "Caption"})` | 图表说明文字 |
| Footnote | 2 | `ParsedElement(content=text, metadata={"category": "Footnote"})` | 页脚注释 |
| Formula | 3 | `ParsedElement(content=formula, metadata={"category": "Formula"})` | 数学公式（V2 LaTeX 支持） |
| List-item | 4 | `ParsedElement(content=text, metadata={"category": "List-item"})` | 列表项 |
| Page-footer | 5 | `ParsedElement(content=text, metadata={"category": "Page-footer"})` | 页脚区域 |
| Page-header | 6 | `ParsedElement(content=text, metadata={"category": "Page-header"})` | 页眉区域 |
| Picture | 7 | `ParsedElement(content="", metadata={"category": "Picture"})` | 图片/插图 |
| Section-header | 8 | `ParsedElement(content=text, metadata={"category": "Section-header"})` | 章节标题 |
| Table | 9 | `ParsedTable(rows=..., bbox=..., metadata={"category": "Table"})` | 表格区域 |
| Text | 10 | `ParsedElement(content=text, metadata={"category": "Text"})` | 正文段落 |
| Title | 11 | `ParsedElement(content=text, metadata={"category": "Title"})` | 文档/页面标题 |

### Bbox 匹配算法规格 Matching Algorithm Specification

**匹配策略：** 基于 IoU（Intersection over Union）的空间贪心匹配

| 算法参数 | 值 | 说明 |
|---------|-----|------|
| IoU 阈值 | > 0.3（严格大于）| IoU 恰好 0.3 不匹配，0.3001 匹配 |
| 排序规则 | 按 IoU 降序 | 最高 IoU 的检测-元素对优先匹配 |
| 匹配策略 | 一一对应 | 检测区域被匹配后不再参与后续匹配；元素被匹配后不再参与后续匹配 |
| 页面隔离 | 必须同页 | `bbox.page` 相同才能匹配 |

> **MVP 降级说明（v1.4.0 审查修订）：**
> `layout_matching.py` 中 `match_detections()` 已正确实现 IoU 空间匹配算法并通过完整测试。
> 但当前 `PDFParser` 不输出 bbox（所有 `ParsedElement.bbox=None`），IoU 匹配无法工作（两个 None bbox 无法计算 IoU）。
> 因此 `_apply_layout_detection()` 采用**顺序索引匹配**作为 MVP 临时方案：
> - Table 标签检测结果（`label='Table'`）按顺序映射到 `ParsedTable.bbox`
> - 非 Table 检测结果按顺序映射到 `ParsedElement.bbox`
> - 当 `PDFParser` 未来输出真实坐标时，需切换为 `match_detections()` IoU 算法

**边缘情况处理：**
- 多检测区域覆盖同一元素：首个匹配的检测区域（最高 IoU）"消费"该元素，后续检测区域无法再匹配
- 单检测区域覆盖多元素：仅最高 IoU 的元素获得该 bbox，其余元素 bbox 保持 None
- 无匹配检测区域：静默丢弃（日志记录 DEBUG 级别）
- 无匹配元素：`bbox` 保持 None（当前默认行为）

### 降级策略 Graceful Degradation Policy

**降级场景与处理：**

| 场景 | 触发条件 | 处理策略 | 结果 |
|------|----------|----------|------|
| 端口未注入 | `layout_detector=None` 或 `pdf_page_renderer=None` | 跳过版面检测步骤 | 所有 `ParsedElement.bbox=None` |
| 模型加载失败 | `OnnxLayoutDetector.__init__` 抛出 `FileNotFoundError`/`ImportError` | Composition Root 捕获并降级为 None | 文档解析以无版面检测模式运行 |
| 推理运行时错误 | `detect()` 抛出异常（OOM/内部错误） | 捕获异常，日志 WARNING，该页跳过检测 | 该页所有元素 bbox=None，其他页正常 |
| 渲染失败 | `render_page()` 抛出异常（pypdfium2 错误） | 捕获异常，日志 WARNING，该页跳过检测 | 该页所有元素 bbox=None，其他页正常 |
| 检测返回空列表 | `detect()` 返回 `[]` | 正常情况，无 bbox 匹配 | 该页所有元素 bbox=None |
| 非法页码 | `page_number < 1` | `detect()` 抛出 `ValueError` | 该页跳过检测 |
| 空图像输入 | `image_bytes` 为空 | `detect()` 抛出 `ValueError` | 该页跳过检测 |

**关键原则：** 版面检测是增强功能，运行时失败不应阻断文档解析主流程（文本解析已完成）。仅初始化失败（配置错误）才抛出异常阻断流程。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── value_objects/
│   │   └── parsed_document.py        # [修改] 新增 BoundingBoxResult 值对象
│   ├── services/
│   │   └── layout_matching.py        # [新增] bbox 匹配辅助函数（IoU 计算/贪心匹配，纯领域逻辑零依赖）
│   └── ports/
│       ├── layout_detector.py        # [新增] LayoutDetector Protocol
│       └── pdf_page_renderer.py      # [新增] PdfPageRendererPort Protocol（render_page → bytes）
│
├── application/
│   └── services/
│       └── document_parsing_service.py  # [修改] 注入 layout_detector + pdf_page_renderer，编排增加版面检测步骤
│
├── infrastructure/
│   └── document_parsing/
│       ├── onnx_layout_detector.py   # [新增] OnnxLayoutDetector 实现
│       └── pdf_page_renderer.py      # [新增] PdfPageRenderer 实现（pypdfium2 + Pillow）
│
└── composition_root.py              # [修改] 注册 layout_detector + pdf_page_renderer + 版本升级

tests/
├── unit/
│   ├── domain/
│   │   ├── value_objects/
│   │   │   └── test_parsed_document.py      # [扩展] 新增 TestBoundingBoxResult
│   │   └── ports/
│   │       └── test_layout_detector_port.py  # [新增] Protocol 合规测试
│   ├── domain/services/
│   │   └── test_layout_matching.py              # [新增] IoU 计算/bbox 匹配单元测试
│   ├── application/services/
│   │   └── test_document_parsing_service.py     # [扩展] layout_detector 注入测试
│   ├── infrastructure/document_parsing/
│   │   ├── test_onnx_layout_detector.py      # [新增] OnnxLayoutDetector 单元测试
│   │   └── test_pdf_page_renderer.py          # [新增] PDF 页面渲染单元测试
│   └── architecture/
│       └── test_arch_document_layout.py      # [新增] SDD 架构约束验证
│
├── contracts/
│   └── test_port_contract_layout_detector.py # [新增] 端口契约测试
│
├── integration/
│   └── test_integration_document_layout.py   # [新增] 端到端集成测试
│
└── acceptance/
    ├── test_acceptance_document_layout.feature  # [新增] Gherkin 场景
    └── test_acceptance_document_layout.py       # [新增] BDD 步骤实现
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 2-2b 文档解析扩展格式实现](./2-2b-document-parsing-extended-formats.md)

**关键学习/Key Learnings:**
1. **`to_dict()` 序列化模式** — `ParsedDocument`/`ParsedPage`/`ParsedElement`/`ParsedTable`/`BoundingBox` 均通过 `to_dict()` 序列化为字典。新增值对象必须实现此方法
2. **DI 注册延迟加载陷阱** — `impl` 字符串拼写错误不会立即报错（lazy import），必须通过契约测试覆盖。本 Story 使用 lambda 工厂模式注入 parser 依赖，`layout_detector` 同理
3. **事件无需新增** — Story 2-2b 复用 `DocumentProcessed` 事件，版面检测结果通过 `parse_result` dict 传递。本 Story 同样复用已有事件，不新增领域事件
4. **`_ALLOWED_TEMP_SUFFIXES` 白名单** — 临时文件后缀必须在此白名单内。当前白名单已包含 `.png`/`.jpg`/`.jpeg`/`.tiff`/`.tif`（渲染图像后缀），`.onnx` 不经过临时文件管线（通过 `SISYS_LAYOUT_MODEL_PATH` 直接加载），**无需扩展白名单**
5. **`repo.save()` 是全量更新** — 没有部分更新方法。版面检测结果通过 `document.metadata["parse_result"] = parsed_doc.to_dict()` 完整覆盖
6. **事件双注册** — 如遇新增事件，必须同时更新 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`（本 Story 不新增事件）
7. **领域层零依赖** — DocLayNet 是 ML 模型（依赖 onnxruntime/numpy），必须完全封装在 infrastructure 层。领域层只定义 Protocol 和值对象
8. **测试 mock 策略** — OCR 测试通过 mock pytesseract 进行。本 Story 中的 ONNX 推理同样通过 mock `InferenceSession` 进行单元测试，不依赖真实模型文件
9. **P0 审查修复模式** — Story 2-2b 经历 3 轮文档审查（17+11+10=38 项问题修复），关键教训：AC 要精确描述实际行为、旧版格式返回友好拒绝而非异常、性能指标要区分 OCR/非 OCR 场景
10. **Contract Gate 版本** — Story 2-2b 展示了版本升级的完整流程（v1.0.0 → v1.1.0：PortSpec version/Composition Root 注册/契约测试断言 三处同步更新）

**应用到本故事/Applied to This Story:**
- [x] `BoundingBoxResult.to_dict()` 遵循已有的 `ParsedElement.to_dict()` 模式
- [x] `LayoutDetector` Protocol 使用 `@runtime_checkable` 与 `DocumentParserPort` 一致
- [x] 不新增领域事件，复用 `DocumentProcessed`
- [x] ONNX 模型 mock 测试策略与 OCR mock 策略一致
- [x] 版本升级三处同步更新（PortSpec/Composition Root/契约测试）
- [x] 已有测试全部保持通过（无回归）

### Git 情报 Git Intelligence Summary

**最近提交分析（`git log --oneline -10`）：**

| Commit | 说明 | 对本 Story 的影响 |
|--------|------|-------------------|
| `f7317b02` | feat: Story 2-2b 文档解析扩展格式实现 (7个新解析器 + 组合器15 MIME路由) | `composition_root.py` 当前状态：document_parser v1.1.0，`_ALLOWED_TEMP_SUFFIXES` 18 后缀 |
| `7b5c8829` | refactor(acceptance): 重写文档解析验收测试为pytest-bdd模式 | BDD 步骤模式：event_loop.run_until_complete() 不使用 @pytest.mark.asyncio |
| `c9734cb1` | fix(story-2-2a): CancelledError路径临时文件泄漏+状态丢失修复 | `asyncio.to_thread()` 中使用 try/finally 清理临时文件 |
| `84b46c12` | fix(story-2-2b): 第3-5轮文档审查修复 — 10项P0/P1问题系统修正 | bbox 字段为 null 通过 BDD 验证（第 78 行 `test_acceptance_document_parse.feature`），本 Story 将替换此断言 |

**代码模式与约定：**
- 解析器命名：`{Format}Parser`（如 `PDFParser`）→ 版面检测：`OnnxLayoutDetector`
- 端口命名：`{Domain}Port`（如 `DocumentParserPort`）→ 版面检测：`LayoutDetector`
- Composition Root 注册：lambda 工厂模式（解析器实例化 → 组合解析器 → 服务编排）
- 测试文件命名：`test_{component}.py`，匹配源代码目录结构

### 最新技术信息 Latest Technical Information

**Docling Layout ONNX 模型（2026-05 调研）：**
- **模型名称：** docling-layout-heron-onnx
- **下载地址：** https://huggingface.co/docling-project/docling-layout-heron-onnx
- **许可证：** MIT（代码） + 模型许可证参考 docling-project
- **输入：** 预处理后的文档页面图像（numpy array，形状 `[1, 3, H, W]`，值域 `[0, 1]`）⚠️ **需实现时验证**：通过 `session.get_inputs()[0].shape` 和 Docling 源码确认实际输入规格，`doclaynet-preparation.md` 未记录精确形状/归一化参数
- **输出：** bounding boxes `[N, 4]`（xyxy 格式）+ class labels `[N]` + confidence scores `[N]`
- **推理速度：** CPU ~100-200ms/页，GPU ~20-30ms/页
- **Python 依赖：** `onnxruntime >= 1.17.0`（CPU）/ `onnxruntime-gpu >= 1.17.0`（GPU）+ `numpy >= 1.24`
- **预处理依赖：** `pypdfium2 >= 1.0.0`（PDF 页面光栅化为 PNG，pypdf 本身不支持渲染为光栅图像）+ `Pillow >= 10.0`（图像 resize/normalize）

**依赖版本约束（与本项目技术栈对齐）：**
```toml
# pyproject.toml [tool.poetry.dependencies] 新增
numpy = "^1.24"
onnxruntime = ">=1.17.0,<2.0"     # CPU 版本（默认）
# onnxruntime-gpu 作为可选依赖（extra: gpu）
pypdfium2 = ">=1.0.0"               # PDF 页面光栅化（pypdf 不支持渲染为光栅图像）
Pillow = ">=10.0"                    # 已有依赖（Story 2-2b ImageParser 引入）
```

**关键风险与缓解：**
| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| ONNX 模型文件较大（30-200 MB） | 部署包体积增大、首次下载慢 | 模型文件独立存储在 MinIO 模型仓库，按需下载；不纳入 git 仓库 |
| CPU 推理较慢（100-200ms/页） | 大文档（100+ 页）处理耗时 > 20s | 生产环境推荐 GPU 推理；异步批量处理；MVP 接受 CPU 延迟 |
| 版面检测结果与文本解析结果匹配不准 | bbox 错配导致溯源错误 | 基于空间 IoU 的多重过滤策略；输出匹配置信度；人工可查 |
| onnxruntime 版本兼容性 | 模型无法加载 | 锁定 onnxruntime >= 1.17.0，CI 中验证兼容性 |

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.8 |
| **Version** | create-story workflow v3.0 |
| **Execution Date** | 2026-06-02 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Instructions** | `.claude/skills/bmad-create-story/discover-inputs.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **核心领域设计** | `docs/architecture/sisys-core-domain-design.md` |
| **实现模式** | `docs/architecture/sisys-implementation-patterns.md` |
| **DocLayNet 调研** | `docs/developer/doclaynet-preparation.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-2b-document-parsing-extended-formats.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Epic 2 Story 2.3 全文 + FR-DM-03 P0 需求）
- [x] 架构约束从 `architecture.md` + `sisys-core-domain-design.md` + `sisys-implementation-patterns.md` 提取
- [x] DocLayNet 技术选型基于 `docs/developer/doclaynet-preparation.md` 调研报告
- [x] 前一个故事学习经验整合（Story 2-2b: 8 项关键学习 + 12 项技术构件迁移）
- [x] Git 情报分析（最近 10 次提交中的代码模式与约定）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-3-layout-preservation-doclaynet.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/layout_detector.py` — LayoutDetector Protocol 端口定义
- `src/domain/ports/pdf_page_renderer.py` — [新增] PdfPageRendererPort Protocol 端口定义
- `src/domain/value_objects/parsed_document.py` — [修改] 新增 BoundingBoxResult 值对象
- `src/infrastructure/document_parsing/onnx_layout_detector.py` — OnnxLayoutDetector 实现
- `src/domain/services/layout_matching.py` — [新增] bbox 匹配辅助函数（纯领域逻辑，IoU 计算/贪心匹配）
- `src/application/services/document_parsing_service.py` — [修改] 编排逻辑增加版面检测步骤
- `src/infrastructure/document_parsing/pdf_page_renderer.py` — [新增] PdfPageRenderer 实现（pypdfium2 + Pillow）
- `src/composition_root.py` — [修改] 注册 layout_detector + 版本升级
- `tests/unit/domain/ports/test_layout_detector_port.py` — Protocol 合规测试
- `tests/unit/domain/services/test_layout_matching.py` — IoU 计算/bbox 匹配单元测试
- `tests/unit/infrastructure/document_parsing/test_onnx_layout_detector.py` — OnnxLayoutDetector 单元测试
- `tests/unit/infrastructure/document_parsing/test_pdf_page_renderer.py` — PDF 页面渲染单元测试
- `tests/unit/architecture/test_arch_document_layout.py` — SDD 架构约束验证
- `tests/contracts/test_port_contract_layout_detector.py` — 端口契约测试
- `tests/integration/test_integration_document_layout.py` — 端到端集成测试
- `tests/acceptance/test_acceptance_document_layout.feature` — Gherkin 验收场景
- `tests/acceptance/test_acceptance_document_layout.py` — BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.3 |
| **Story Key** | 2-3-layout-preservation-doclaynet |
| **File** | `_bmad-output/implementation-artifacts/stories/2-3-layout-preservation-doclaynet.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P0-3（关键路径，跨 Epic 硬依赖） |
| **前置依赖** | Story 2-2a 文档解析基础格式（✅ done） |
| **后置依赖** | Epic 3 Story 3.8 高保真溯源 Bounding Box（📋 backlog） |
| **覆盖 FR** | FR-DM-03 版面信息保留（P0） |
| **预计工期** | 4 天 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-5，含 TDD 循环分解）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5，BDD Given/When/Then 格式）
3. [x] Architecture constraints extracted 架构约束已提取（六边形架构/领域层零依赖/DocLayNet 技术选型 ADR）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（10 项关键学习 + 直接技术构件迁移指引）
5. [x] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-06-02
**最后更新/Last Updated:** 2026-06-05
**更新说明/Description:**
- v1.5.0: 代码审查修订（15 Agent 5轮审查）— 防御性校验增强（page_number/image_bytes/数组长度一致性/xyxy→xywh clamp）/BoundingBoxResult confidence 值域约束 [0.0,1.0]/metadata error 键名统一为 parse_error/Table 标签检测结果映射到 ParsedTable.bbox/Composition Root 异常捕获缩窄/ONNX session close()资源释放/shutdown 清理钩子/pdf_page_renderer 日志补全/MVP 降级策略文档化/降级场景表扩展
- v1.4.0: 5轮审查修订（第6-10轮）— PdfPageRendererPort端口体系补充/架构集成路径明确化/降级策略规格化/匹配算法规格化/BoundingBoxResult冗余字段移除/layout_matching归属domain层/项目结构路径修正/覆盖率门禁精确化/ONNX输入格式验证提示/置信度处理规则/追溯矩阵同步/测试分类表补全/Subtask编号同步
- v1.3.0: Round 3-5 审查修订 — 5项P1修正（registry.py描述/FORWARD兼容策略移除/契约测试引用/追溯矩阵Task编号）
- v1.2.0: Round 2 审查修订 — 7项P1问题修正
- v1.1.0: Round 1 审查修订 — 10项P0/P1问题系统修正
- v1.0.0: 创建故事文件
