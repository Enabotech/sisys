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

企业积累大量历史纸质文档扫描件和图像 PDF，这些文档无嵌入文本层，无法通过常规 PDF 解析提取内容。
本 Story 引入 PaddleOCR-VL-1.6 作为 OCR 引擎，通过 Docker 服务化部署（GPU 加速），
对扫描件进行高精度 OCR 识别（中/英），输出带置信度评分的结构化文本，
低于阈值（0.85）自动标注为"待人工复核"，确保进入下游分析的数据质量可靠。

本 Story 是 Epic 2 文档处理流水线的 P1 增强节点：依赖 Story 2-2a（基础格式解析），
完成后扫描件即可纳入全文检索与知识发现（Epic 3）的处理范围。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: OCR 解析扫描件 PDF

**Given** 上传的 PDF 文档为扫描件（无嵌入文本层，pages 全部为图像）
**When** 系统执行 OCR 解析
**Then** 提取文本内容，输出 `ParsedElement` 列表，每个元素含 `confidence` 字段
**And** 支持中文和英文识别
**And** `confidence < 0.85` 时自动在 `metadata["needs_review"] = True` 标注为"待人工复核"

**验证标准/Validation Criteria:**
- [ ] 扫描件 PDF 解析后 `parse_status = COMPLETED`
- [ ] 每个 `ParsedElement.content` 包含 OCR 识别文本
- [ ] `ParsedElement.confidence` 值域 [0.0, 1.0]
- [ ] `confidence < 0.85` 的元素含 `metadata["needs_review"] = True`
- [ ] 中文文本正确识别（抽样精确率 ≥ 95%）
- [ ] 英文文本正确识别（抽样精确率 ≥ 95%）

### AC-2: 常规 PDF 不受影响

**Given** 上传的 PDF 文档为常规文本 PDF（含嵌入文本层）
**When** 系统执行文档解析
**Then** 使用现有 `PDFParser`（pypdf）解析，不触发 OCR
**And** `ParsedElement.confidence` 保持默认值 1.0（非 OCR 场景）
**And** 解析行为与 Story 2-2a/2-2b 完全一致

**验证标准/Validation Criteria:**
- [ ] 常规 PDF 解析路径不变
- [ ] OCR 端口未注入时不触发 OCR 逻辑
- [ ] 回归测试：已有 PDF 解析测试全部通过

### AC-3: OCR 服务不可用时的降级

**Given** PaddleOCR-VL 服务未启动或不可达
**When** 系统尝试对扫描件执行 OCR 解析
**Then** 记录 WARNING 日志，返回 `parse_status = FAILED`
**And** `metadata["parse_error"]` 包含降级原因
**And** 不阻塞文档处理流水线（文档实体状态正确更新为 FAILED）

**验证标准/Validation Criteria:**
- [ ] OCR 连接超时 -> `parse_status = FAILED`
- [ ] OCR 返回非 200 -> `parse_status = FAILED`
- [ ] 异常信息记录到 `parse_error`，不泄露内部实现细节
- [ ] 降级不触发未捕获异常

### AC-4: 置信度标注与质量标记

**Given** OCR 解析完成，`ParsedElement` 含 `confidence` 评分
**When** 置信度 < 0.85
**Then** `metadata["needs_review"] = True`
**When** 置信度 ≥ 0.85
**Then** `metadata["needs_review"] = False` 或不设置该字段
**And** 置信度信息持久化到 `Document.metadata["parse_result"]`

**验证标准/Validation Criteria:**
- [ ] 置信度阈值配置为常量 `OCR_CONFIDENCE_THRESHOLD = 0.85`
- [ ] 低置信度元素正确标注
- [ ] 高置信度元素不标注
- [ ] parse_result 持久化包含完整置信度数据

### AC-5: PaddleOCR-VL 服务化部署

**Given** RTX 5090 (Blackwell SM120, 32GB GDDR7) GPU 环境，`deploy/app/docker-compose.yml` 已配置所有基础服务
**When** 在 `docker-compose.yml` 中直接添加 `paddleocr-vl-vllm` + `paddleocr-vl-api` 两服务定义（与现有 `embedding-api` 一样内联），
两服务声明 `profiles: [gpu]`，
并执行 `cd deploy/app && docker compose up -d`（基础服务）和 `docker compose --profile gpu up -d`（含 GPU 服务）
**Then** PaddleOCR-VL-1.6 两服务与所有基础服务可独立管理：
  - `paddleocr-vl-api` → `localhost:8080`（API 服务）
  - `paddleocr-vl-vllm` → 内部 `8118`（vLLM 推理，仅 API 服务访问）
**And** 非 GPU 环境下 `docker compose up -d` 仅启动基础服务，不因 GPU 缺失而失败
**And** `/layout-parsing` 端点可接受 base64 编码的 PDF/图像
**And** 返回结构化 JSON（含 `prunedResult`、`markdown`、置信度信息）

**验证标准/Validation Criteria:**
- [ ] `cd deploy/app && docker compose up -d` 一键启动基础服务（不含 PaddleOCR-VL）
- [ ] `cd deploy/app && docker compose --profile gpu up -d` 额外启动 PaddleOCR-VL 两服务
- [ ] `docker compose ps` 显示 `sisys-paddleocr-vl-api` + `sisys-paddleocr-vl-vllm` 均为 `healthy`（GPU 环境）
- [ ] `curl -X POST http://localhost:8080/layout-parsing` 返回 200
- [ ] CUDA 12.9+ 驱动兼容，GPU 显存分配正常（推荐 `gpu-memory-utilization: 0.3`）
- [ ] SISYS 应用可通过 `http://paddleocr-vl-api:8080` 容器名调用
- [ ] 模型/镜像不在 git 中（`.gitignore` 忽略大文件）
- [ ] `docs/deploy/paddleocr-vl-setup.md` 存在且含首次镜像拉取耗时说明（~30-60 分钟）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

> **决策：本 Story 不新增领域事件。** OCR 解析结果通过现有的 `DocumentProcessed` 事件发布，
> OCR 置信度信息包含在 `Document.metadata["parse_result"]` 中。
> 此决策与 Story 2-3（版面检测）和 Story 2-4（表格提取）保持一致——增强功能不新增事件。

- [x] 复用现有 `DocumentProcessed` 事件（`src/domain/events/document_events.py`）
- [x] OCR 结果通过 `parse_result` dict 传递，无需新事件字段

#### 数据模型 (Data Models)

- [ ] 复用现有 `ParsedElement`（`src/domain/value_objects/parsed_document.py:167`）：
  - `confidence: float = 1.0` — 已有字段，注释"OCR 场景由 Story 2-5 实现"
  - `metadata: dict[str, Any]` — OCR 结果通过此字段承载（`needs_review`、`ocr_engine` 等）
- [ ] 复用现有 `ParsedDocument`、`ParsedPage`、`BoundingBox` — 不新增值对象
- [ ] ~~新增领域值对象：`ScannedPageDetection`~~ **（删除——实现中不使用，`detect_scanned_pages()` 返回 `list[int]` 页码列表，检测元数据通过日志记录）**

#### 统一端口定义注册与管理 (Port Contract)

- [ ] 端口契约定义位于 `src/domain/ports/ocr.py` — **新增 `OCRPort`**
  - `recognize(file_path: str, page_numbers: list[int] | None = None) -> list[OCRPageResult]` — 对指定页面执行 OCR
  - 返回 `OCRPageResult`（定义在 `src/domain/value_objects/ocr_result.py`）：
    - `page_number: int`
    - `elements: list[ParsedElement]` — OCR 识别后的 ParsedElement，含 `confidence`
    - `raw_response: dict[str, Any]` — PaddleOCR-VL 原始响应（调试用）
- [ ] 端口注册中心 `src/domain/ports/registry.py`：`OCRPort` 登记为 `PortSpec`
  - `name="ocr"`, `version="v1.0.0"`, `lifetime=SCOPED`, `owner="epic-2"`
- [ ] 端口解析器 `src/domain/ports/resolver.py`：可通过 `resolve("ocr")` 获取实现
- [ ] 端口契约测试：`tests/contracts/test_port_contract_ocr.py`
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象 `OCRPort`，不直接依赖 `PaddleOCRVLAdapter`

#### 端口契约清单执行约束（强制）

- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口（`OCRPort` + `ScannedPageDetector` 如有），禁止语义重复端口
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

**端口清单：**

| Port Name | Interface | Implementation | Registration | Lifetime | Version | Owner |
|-----------|-----------|----------------|--------------|----------|---------|-------|
| `ocr` | `OCRPort` | `PaddleOCRVLAdapter` | `src/domain/ports/ocr.py` | SCOPED | v1.0.0 | epic-2 |

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增的领域异常必须在 Task 0 中完成设计。
> **禁止 `raise ValueError`：** 所有验证失败均使用领域异常体系。
> **参考模式：** OCR 异常作为 `external` 的独立子域（与 `embedding`/`sandbox` 同级别），
> 拥有专属异常模块（`ocr_exceptions.py`）、编码范围（320-329，预留 10 个码）、子域注册和测试。

**新增异常：**

| 异常类 | 编码 | 基类 | 归属子域 | 场景 |
|--------|------|------|---------|------|
| `OCRConnectionError` | EXCEPTION_320 | `ExternalException` | ocr | PaddleOCR-VL 服务不可达/连接超时 |
| `OCRProcessingError` | EXCEPTION_321 | `ExternalException` | ocr | PaddleOCR-VL 返回错误/响应解析失败 |

**预留编码（本 Story 不实现，后续迭代追加）：**
| 预留编码 | 预期场景 |
|---------|---------|
| EXCEPTION_322 | OCR 响应格式错误（JSON 解析失败/结构不匹配） |
| EXCEPTION_323 | OCR 模型错误（GPU OOM/模型加载失败） |
| EXCEPTION_324 | OCR 速率限制（Rate Limit 429） |
| EXCEPTION_325-329 | 预留扩展 |

- [ ] 归属模块与基类 — 新建 `src/domain/exceptions/ocr_exceptions.py`，继承 `ExternalException`（参考 `embedding_exceptions.py`/`sandbox_exceptions.py` 模式）
- [ ] 唯一编码分配 — OCR 子域编码范围 320-329（预留 8 个扩展位），`grep -r "EXCEPTION_320\|EXCEPTION_321" src/domain/exceptions/` 验证无碰撞
- [ ] 构造器参数设计 — `OCRConnectionError(service_url: str, cause: Exception | None = None)`，`OCRProcessingError(service_url: str, status_code: int | None = None, response_body: str | None = None)`
- [ ] 消息安全性审查 — 错误消息不泄露 API key/完整 URL/原始响应 body（仅暴露状态码和截断的摘要）
- [ ] 编码注册 — 在 `_code_ranges.py` 中新增 OCR 子域：
  - `CODE_RANGES` 添加 `"ocr": (320, 329)`
  - `_CLASS_TO_SUBDOMAIN` 添加 `"OCRConnectionError": "ocr"` + `"OCRProcessingError": "ocr"`
- [ ] 导出完整性 — `ocr_exceptions.py` 的 `__all__` + `src/domain/exceptions/__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过
- [ ] BDD 验收场景 — 异常路径的 Gherkin 场景纳入 Edge Cases（AC-3）

#### API 契约 (API Contract)

> **决策：本 Story 不新增 REST API 端点。** OCR 是内部文档处理流水线的增强步骤，
> 不暴露独立的 API 端点。文档解析通过现有 `POST /api/v1/documents/{id}/parse` 触发，
> OCR 作为解析流程的一部分自动执行。

- [x] 无新增 API 端点
- [x] 现有 API 响应结构不变（`parse_result` 扩展包含 OCR 置信度信息）
- [x] 无新增 `docs/api/openapi.yaml` 变更

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
- 禁止导入：requests, httpx, docker, paddleocr, fastapi, pydantic, sqlalchemy 等

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_ocr.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_ocr.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**Gherkin 场景清单：**

```gherkin
Feature: OCR 解析扫描件文档

  Scenario: 扫描件 PDF 成功 OCR 解析
    Given PaddleOCR-VL 服务正常运行
    And 已上传一份中文扫描件 PDF（无嵌入文本层）
    When 系统对文档执行解析
    Then 解析状态为 COMPLETED
    And parse_result 包含 OCR 提取的文本内容
    And 每个文本元素的 confidence 值在 [0.0, 1.0] 范围内
    And 中文文本内容非空

  Scenario: 低置信度元素自动标注待复核
    Given PaddleOCR-VL 服务正常运行
    And 已上传一份模糊扫描件（预期 OCR 置信度偏低）
    When 系统对文档执行解析
    Then 解析状态为 COMPLETED
    And 存在 confidence < 0.85 的元素
    And 这些元素的 metadata.needs_review 为 True

  Scenario: 常规文本 PDF 不触发 OCR
    Given 已上传一份常规文本 PDF（含嵌入文本层）
    When 系统对文档执行解析
    Then 解析状态为 COMPLETED
    And ParsedElement.confidence 保持默认值 1.0
    And 未调用 OCRPort.recognize

  Scenario: OCR 服务不可用时降级处理
    Given PaddleOCR-VL 服务未启动
    And 已上传一份扫描件 PDF
    When 系统对文档执行解析
    Then 解析状态为 FAILED
    And parse_error 包含 OCR 服务不可用信息
    And 错误信息不泄露内部 URL/端口等实现细节

  Scenario: 混合 PDF（部分页面为扫描件）
    Given PaddleOCR-VL 服务正常运行
    And 已上传一份混合 PDF（第 1-2 页为文本，第 3-4 页为扫描件）
    When 系统对文档执行解析
    Then 解析状态为 COMPLETED
    And 第 1-2 页使用 PDFParser 提取文本
    And 第 3-4 页通过 OCR 提取文本
    And 第 3-4 页元素的 confidence < 1.0
```

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- Edge Cases 必须包含：OCR 服务不可用、混合 PDF、空页面、超大文件超时

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | OCRPort 端口契约 | Protocol 方法签名、行为语义 | `test_ocr_port.py` | Task 1 |
| **TDD 单元测试** | OCRResult 值对象 | 构造/序列化/校验 | `test_ocr_result.py` | Task 1 |
| **TDD 单元测试** | 扫描页检测领域服务 | 文本密度计算、阈值判断 | `test_scanned_page_detector.py` | Task 2 |
| **TDD 单元测试** | PaddleOCRVLAdapter | HTTP 请求/响应解析/降级/超时 | `test_paddleocr_vl_adapter.py` | Task 3 |
| **TDD 单元测试** | DocumentParsingService OCR 集成 | OCR 步骤注入/调用/结果合并 | `test_document_parsing_service_ocr.py` | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_ocr.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_ocr.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单 | `test_acceptance_ocr.feature` | Task 6 |
| **TDD 契约测试** | 端口契约 / 接口抽象 / registry | 端口注册、版本、兼容性 | `test_port_contract_ocr.py` | Task 0 |
| **TDD 领域异常测试** | `src/domain/exceptions/ocr_exceptions.py` | 构造/属性/`to_dict()` 序列化/cause 链 | `tests/unit/domain/exceptions/test_ocr_exceptions.py` | Task 1 |
| **TDD 领域异常测试** | 编码唯一性 + 子域范围 | 自动反射扫描 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖、禁止跨层引用 | `test_arch_document_ocr.py` | Task 5 |
| **集成测试** | PaddleOCR-VL 真实调用 | Mock HTTP 响应 / TestContainer | `test_integration_ocr.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（关键业务逻辑，不变量验证）
- [ ] **应用层覆盖率 ≥85%**（核心业务流，OCR 步骤编排）
- [ ] **基础设施层覆盖率 ≥75%**（HTTP 适配器，响应解析）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）

> ⚠️ **非骨架 Story，不适用覆盖率豁免。** 必须达到标准覆盖率。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [ ] **禁止 `# noqa`、`# type: ignore` 等抑制注释**

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离** | PaddleOCR-VL API 测试使用 Mock（`unittest.mock.AsyncMock`/`responses`/`aioresponses`），集成测试使用真实 Docker 服务 | 测试依赖外部服务不稳定 |
| **资源唯一性** | 测试数据使用 UUID 标识符 | ID 冲突或状态污染 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | `asyncio.Lock` 类变量；Mock HTTP 使用 `aioresponses` 或 `httpx.MockTransport` | 锁失效或异步问题 |
| **pytest-asyncio** | BDD 步骤使用 `event_loop.run_until_complete()` | 直接用 `@pytest.mark.asyncio` 导致 context 丢失 |

**禁止行为：**
- ❌ 单元测试直接调用真实 PaddleOCR-VL 服务（慢、不稳定、污染）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 测试间共享 Mock 状态
- ❌ `asyncio.Lock` 使用实例变量

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | OCR 解析扫描件 PDF，提取文本+置信度 | Task 2 | 扫描页检测 | `test_scanned_page_detector.py` |
| AC-1 | OCR 解析扫描件 PDF，提取文本+置信度 | Task 3 | PaddleOCRVLAdapter | `test_paddleocr_vl_adapter.py` |
| AC-1 | OCR 解析扫描件 PDF，提取文本+置信度 | Task 4 | OCR 步骤集成 | `test_document_parsing_service_ocr.py` |
| AC-2 | 常规 PDF 不受影响 | Task 4 | OCR 步骤跳过逻辑 | `test_document_parsing_service_ocr.py` |
| AC-3 | OCR 服务不可用降级 | Task 3 | Adapter 异常处理 | `test_paddleocr_vl_adapter.py` |
| AC-3 | OCR 服务不可用降级 | Task 4 | 应用层降级编排 | `test_document_parsing_service_ocr.py` |
| AC-4 | 置信度标注与质量标记 | Task 1 | OCRResult 值对象校验 | `test_ocr_result.py` |
| AC-4 | 置信度标注与质量标记 | Task 4 | DocumentParsingService 标记逻辑 | `test_document_parsing_service_ocr.py` |
| AC-5 | PaddleOCR-VL 服务化部署 | Task 5 | docker-compose.yml 内联写入（profiles: [gpu]）+ paddleocrvl/ 参考模板 | `deploy/app/paddleocrvl/` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5

> **目的：** 在进入代码实现前，明确 Schema、端口契约、异常契约、验收标准与六边形架构边界。
>
> ⚠️ **P0 前提：PaddleOCR-VL API 响应格式实测验证**
> 在 Subtask 0.1-0.9 之前，必须先调用一次 PaddleOCR-VL `/layout-parsing` 真实 API（GPU 环境或已部署的测试实例），
> 获取完整 JSON 响应示例并保存为 `tests/data/paddleocr_vl_response_sample.json`。
> **验证清单：**
> - 确认 `prunedResult.parsing_res_list` 中每个 block 是否包含 `confidence` 字段
> - 确认 `fileType` 参数的准确枚举值（0=PDF/1=image 是否与实际 API 一致）
> - 确认 `block_content` 的实际格式（Markdown/纯文本/HTML）
> - 将真实响应结构作为 Mock 测试 fixture 的**唯一数据来源**（禁止凭空构造）
>
> **若无法在 Task 0 阶段访问 GPU 环境：** 参考 PaddleOCR-VL 官方文档中的示例响应体（URL: `https://www.paddleocr.ai/latest/version3.x/pipeline_usage/PaddleOCR-VL-NVIDIA-Blackwell.html`），
> 并在 Task 5 集成测试阶段补做真实 API 验证，如有差异则回溯修正 Adapter 解析逻辑。

- [ ] Subtask 0.0: **PaddleOCR-VL API 响应格式实测**（P0 前提，保存 `tests/data/paddleocr_vl_response_sample.json`）
- [ ] Subtask 0.1: 定义 OCRResult 值对象 Schema（`src/domain/value_objects/ocr_result.py`）：
  - `OCRPageResult`（frozen dataclass）：`page_number: int, elements: list[ParsedElement], raw_response: dict[str, Any]`
  - `OCRConfidenceMark`（frozen dataclass，`_mark_low_confidence()` 方法内部使用的辅助值对象）：`element_index: int, confidence: float | None, needs_review: bool`（`confidence=None` 时视为未知，`needs_review=True`）
- [ ] Subtask 0.2: 定义 `OCRPort` 端口契约（`src/domain/ports/ocr.py`）：
  - `recognize(file_path: str, page_numbers: list[int] | None = None) -> list[OCRPageResult]`
- [ ] Subtask 0.3: 定义扫描页检测逻辑（`src/domain/services/scanned_page_detector.py`）：
  - 纯函数：`detect_scanned_pages(pages: list[ParsedPage]) -> list[int]`（返回需要 OCR 的页码列表）
  - 检测策略：文本密度 = 总字符数 / 页面数，密度 < `SCANNED_PAGE_TEXT_DENSITY_THRESHOLD` 判定为扫描页
- [ ] Subtask 0.4: 定义 OCR 子域异常（**新建** `src/domain/exceptions/ocr_exceptions.py`）：
  - `OCRConnectionError(EXCEPTION_320)` — 继承 `ExternalException`（参考 `EmbeddingAPIError` 模式）
  - `OCRProcessingError(EXCEPTION_321)` — 继承 `ExternalException`
  - 模块 `__all__` 导出 + Google 风格中文 docstring
- [ ] Subtask 0.5: 更新异常编码注册：
  - `_code_ranges.py`：`CODE_RANGES` 添加 `"ocr": (320, 329)` + `_CLASS_TO_SUBDOMAIN` 添加两个 OCR 异常类
  - `src/domain/exceptions/__init__.py`：导入 OCR 异常模块并加入 `__all__`
  - `src/interfaces/api/exception_handlers.py`：`EXCEPTION_HTTP_MAP` 添加映射：
    - `OCRConnectionError(320)` → **504 Gateway Timeout**（连接超时/不可达，上游未响应）
    - `OCRProcessingError(321)` → **502 Bad Gateway**（上游返回错误/响应解析失败）
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_ocr.feature`（5 个场景）
- [ ] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_ocr.py`（骨架，@given/@when/@then 空函数）
- [ ] Subtask 0.8: 编写端口契约测试 `tests/contracts/test_port_contract_ocr.py`
- [ ] Subtask 0.9: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] 端口契约测试运行失败（`OCRPort` 尚未实现）

---

### Task 1: OCRPort 端口契约 + OCRResult 值对象 + 领域异常

**关联 AC:** AC-4

> **目的：** 确立 `OCRPort` 作为领域层抽象，`OCRResult` 作为值对象，异常作为领域契约。
> 这是后续所有实现的基础。

#### TDD 循环 A：OCRResult 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_ocr_result.py`（构造、序列化、校验） |
| 🟢 绿 | 实现 `OCRPageResult` + `OCRConfidenceMark`（`src/domain/value_objects/ocr_result.py`） |
| 🔄 重构 | 添加 Google 风格中文 docstring，统一 `to_dict()` 序列化模式 |

- [ ] Subtask 1.1: 🔴 红 — 编写 OCRResult 值对象测试（构造/`to_dict()`/`confidence` 值域校验 [0.0, 1.0]）
- [ ] Subtask 1.2: 🟢 绿 — 实现 `OCRPageResult`（frozen dataclass）+ `OCRConfidenceMark`
- [ ] Subtask 1.3: 🔄 重构 — 完善 docstring，对齐 `ParsedElement` 的序列化风格

#### TDD 循环 B：OCRPort 端口契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_ocr_port.py`（Protocol 结构验证） |
| 🟢 绿 | 实现 `OCRPort` Protocol（`src/domain/ports/ocr.py`） |
| 🔄 重构 | 在 `src/domain/ports/__init__.py` 导出，添加 `@runtime_checkable` |

- [ ] Subtask 1.4: 🔴 红 — 编写 OCRPort 契约测试（Protocol 方法签名、`__init__` 导出）
- [ ] Subtask 1.5: 🟢 绿 — 实现 `OCRPort` Protocol（`recognize` → `list[OCRPageResult]`）
- [ ] Subtask 1.6: 🔄 重构 — 添加 `@runtime_checkable`，更新 `src/domain/ports/__init__.py`

#### TDD 循环 C：OCR 子域异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写异常构造/`to_dict()`/HTTP 映射/子域范围测试 |
| 🟢 绿 | 实现 `ocr_exceptions.py` 模块 + `OCRConnectionError`(320) + `OCRProcessingError`(321) |
| 🔄 重构 | 注册子域编码范围，完善 docstring，运行编码唯一性测试 |

- [ ] Subtask 1.7: 🔴 红 — 编写 OCR 异常测试（构造/`to_dict()`/HTTP 映射 502/编码唯一性/子域范围 320-329）
- [ ] Subtask 1.8: 🟢 绿 — 创建 `src/domain/exceptions/ocr_exceptions.py`（参考 `embedding_exceptions.py` 模式），实现异常类 + `__all__` + `__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] Subtask 1.9: 🔄 重构 — `_code_ranges.py` 注册 OCR 子域（`CODE_RANGES` + `_CLASS_TO_SUBDOMAIN`），运行全量异常测试确认无碰撞

**完成标准/Definition of Done:**
- [ ] `OCRResult` 值对象实现完成（frozen dataclass，`to_dict()` 序列化）
- [ ] `OCRPort` Protocol 定义完成（`@runtime_checkable`，导出自 `__init__.py`）
- [ ] `OCRConnectionError`(320) 和 `OCRProcessingError`(321) 注册完成
- [ ] 端口契约测试通过（`test_port_contract_ocr.py`）
- [ ] 所有 TDD 循环测试通过
- [ ] 领域层覆盖率 ≥ 90%

---

### Task 2: 扫描页检测领域服务

**关联 AC:** AC-1, AC-2

> **目的：** 实现纯函数式扫描页检测逻辑，判断 PDF 页面是否需要 OCR。
> 这是 OCR 步骤的触发器——只在需要时才调用 PaddleOCR-VL。

#### TDD 循环 A：ScannedPageDetector 领域服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_scanned_page_detector.py`（文本密度计算、阈值判断、边界场景） |
| 🟢 绿 | 实现 `scanned_page_detector.py`（纯函数，仅用 stdlib） |
| 🔄 重构 | 抽取常量为模块级 `SCANNED_PAGE_TEXT_DENSITY_THRESHOLD` |

- [ ] Subtask 2.1: 🔴 红 — 编写扫描页检测测试：
  - 空页面（0 字符）→ 判定为扫描页
  - 高密度文本页 → 判定为文本页（不触发 OCR）
  - 混合页面列表 → 正确分类每个页面
  - 边界值：恰好等于阈值 → 不触发 OCR
- [ ] Subtask 2.2: 🟢 绿 — 实现 `detect_scanned_pages(pages: list[ParsedPage]) -> list[int]`
  - 纯函数，零外部依赖
  - **逐页比较**（非全文档平均）：对每个 `page` 独立计算 `char_count = sum(len(e.content) for e in page.elements)`
  - 若 `char_count < SCANNED_PAGE_TEXT_DENSITY_THRESHOLD` → 该页判定为扫描页，加入返回列表
  - 阈值常量 `SCANNED_PAGE_TEXT_DENSITY_THRESHOLD = 50`（单页 < 50 字符 → 扫描件；该值为经验值，可通过环境变量覆盖）
  - **设计理由：** 逐页比较确保混合 PDF（部分文本页+部分扫描页）正确识别，Gherkin 场景"混合 PDF"依赖此行为
- [ ] Subtask 2.3: 🔄 重构 — 抽取常量，完善 docstring，处理边缘场景（`pages=[]`）

**完成标准/Definition of Done:**
- [ ] `detect_scanned_pages()` 实现完成
- [ ] 所有 TDD 测试通过
- [ ] 领域层覆盖率 ≥ 90%（纯函数，易达到）

---

### Task 3: PaddleOCRVLAdapter 基础设施实现

**关联 AC:** AC-1, AC-3

> **目的：** 实现 `PaddleOCRVLAdapter`，作为 `OCRPort` 的基础设施层实现，
> 通过 HTTP 调用 PaddleOCR-VL 服务化 API。

> ⚠️ **技术决策：** 使用 `httpx.AsyncClient`（项目已有依赖）进行 HTTP 通信，
> 不引入 `requests`（同步阻塞）或 `aiohttp`（额外依赖）。

#### TDD 循环 A：PaddleOCRVLAdapter 核心逻辑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/document_parsing/test_paddleocr_vl_adapter.py`（Mock HTTP） |
| 🟢 绿 | 实现 `PaddleOCRVLAdapter`（HTTP 调用 + 响应解析 + 异常处理） |
| 🔄 重构 | 抽取响应解析为独立方法，添加超时/重试/日志 |

- [ ] Subtask 3.1: 🔴 红 — 编写 PaddleOCRVLAdapter 单元测试（使用 `httpx.MockTransport`，项目已有模式）：
  - 成功场景：Mock 返回 PaddleOCR-VL 标准响应 → 验证 `list[OCRPageResult]` 输出
  - 连接超时 → 抛出 `OCRConnectionError`
  - HTTP 4xx/5xx → 抛出 `OCRProcessingError`
  - 响应 JSON 解析失败 → 抛出 `OCRProcessingError`
  - 空页面（无文字块）→ 返回空 `elements` 列表
  - 中文识别结果正确映射到 `ParsedElement`
  - 英文识别结果正确映射到 `ParsedElement`
  - 置信度从 `prunedResult` 中提取（⚠️ **P0 前提：须在 Task 0 实测 PaddleOCR-VL API 确认置信度字段存在**；若无置信度字段则所有元素 `confidence=None`，下游按"未知"处理触发 `needs_review=True`）
- [ ] Subtask 3.2: 🟢 绿 — 实现 `PaddleOCRVLAdapter`（`src/infrastructure/document_parsing/paddleocr_vl_adapter.py`）：
  - 构造函数：`__init__(self, base_url: str = "http://localhost:8080", timeout: float = 300.0)`
  - `recognize()` 方法：
    1. **安全写临时文件：** 使用 `tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)` + `os.fchmod(0o600)` 创建临时文件，`try/finally` 确保 `os.unlink()` 清理（含 `CancelledError` 场景）
    2. 读取文件为 base64（PDF 文件）或 bytes（图像）；**大文件限制：** 单次请求 ≤ 50MB（原始文件），超大文件需预先拆分
    3. POST `{base_url}/layout-parsing`，payload: `{"file": base64_data, "fileType": 0/1}`
    4. **PDF 按页拆分：** 若 `page_numbers` 指定了页码范围，调用 `pdfplumber` 或 `pypdf` 拆分 PDF 为单页文件后分别请求（PaddleOCR-VL `/layout-parsing` 无原生页码过滤参数）
    5. 解析 `resp.json()["result"]["layoutParsingResults"][].prunedResult.parsing_res_list`
    6. 将每个 block 的 `block_content`（Markdown 格式）通过 `_strip_markdown()` 转为纯文本后映射为 `ParsedElement(content=plain_text, confidence=extracted_confidence, metadata={"ocr_format": "markdown", "original_block": block_content, ...})`
    7. 按页组织为 `OCRPageResult`
  - 异常处理：
    - `httpx.ConnectError` / `httpx.TimeoutException` → `OCRConnectionError`
    - HTTP status != 200 → `OCRProcessingError`
    - JSON decode error → `OCRProcessingError`
  - 日志：INFO 记录请求耗时，WARNING 记录低置信度元素数量
- [ ] Subtask 3.3: 🔄 重构 — 抽取 `_call_ocr_api()`、`_parse_response()`、`_block_to_element()`、`_strip_markdown()`、`_split_pdf_pages()` 方法，添加 `retries=2`（指数退避：1s→2s，仅对 5xx/连接错误重试，每次重试独立超时），配置超时从构造参数传入

#### TDD 循环 B：image_parser.py 增强（可选——统一 OCR 后端）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 ImageParser + OCR 集成测试 |
| 🟢 绿 | ImageParser 可选注入 `ocr: OCRPort | None`，替换 pytesseract |
| 🔄 重构 | 向后兼容：`ocr=None` 时回退 pytesseract |

- [ ] Subtask 3.4: 🔴 红 — 编写 ImageParser OCR 注入测试
- [ ] Subtask 3.5: 🟢 绿 — `ImageParser.__init__` 新增 `ocr: OCRPort | None = None`，`ocr is not None` 时用 PaddleOCR-VL 替代 pytesseract
- [ ] Subtask 3.6: 🔄 重构 — 降级兼容：`ocr=None` 时保持 pytesseract 路径（向后兼容）

**完成标准/Definition of Done:**
- [ ] `PaddleOCRVLAdapter` 实现完成
- [ ] HTTP 通信正确（超时、重试、错误处理）
- [ ] PaddleOCR-VL 响应正确映射到 `OCRPageResult` + `ParsedElement`
- [ ] 基础设施层覆盖率 ≥ 75%
- [ ] ImageParser 向后兼容（可选 OCR 注入）

---

### Task 4: DocumentParsingService OCR 集成 + 置信度标记

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 将 OCR 作为可选增强步骤注入 `DocumentParsingService`，
> 遵循与 `layout_detector` 和 `table_extractor` 相同的注入/降级模式。

#### TDD 循环 A：DocumentParsingService OCR 步骤

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_document_parsing_service_ocr.py` |
| 🟢 绿 | 在 `DocumentParsingService` 中注入 `ocr` + 添加 `_apply_ocr()` 方法 |
| 🔄 重构 | 对齐现有降级模式，抽取置信度标记逻辑 |

- [ ] Subtask 4.1: 🔴 红 — 编写 OCR 集成单元测试（Mock `OCRPort`）：
  - OCR 端口注入 → 扫描页触发 OCR → `ParsedDocument.pages` 中 `ParsedElement.confidence` 更新
  - OCR 端口注入 → 文本页不触发 OCR → `ParsedElement.confidence` 保持 1.0
  - OCR 端口未注入（`ocr=None`）→ 整个 OCR 步骤跳过
  - OCR 调用抛出 `OCRConnectionError` → WARNING 日志 + `parse_status = FAILED`
  - OCR 调用抛出 `OCRProcessingError` → WARNING 日志 + `parse_status = FAILED`
  - 置信度 < 0.85 的元素 → `metadata["needs_review"] = True`
  - 置信度 ≥ 0.85 的元素 → `metadata["needs_review"]` 不设置（或 `False`）
  - OCR 返回空结果 → 页面保持原始状态，日志 INFO
- [ ] Subtask 4.2: 🟢 绿 — 修改 `DocumentParsingService`（`src/application/services/document_parsing_service.py`）：
  - 构造函数新增参数：`ocr: OCRPort | None = None`（注：构造函数已有 8 个参数，本 Story 增至 9 个——后续 Epic 应考虑重构为 Pipeline/Chain of Responsibility 模式，但本 Story 保持与 `layout_detector`/`table_extractor` 一致的注入风格）
  - 新增 `_apply_ocr(self, parsed_doc: ParsedDocument, file_path: str, mime_type: str) -> ParsedDocument` 方法（签名与 `_apply_layout_detection`/`_apply_table_extraction` 对齐）：
    0. **守卫：** `if self._ocr is None: return parsed_doc`（OCR 端口未注入时静默跳过）
    1. 调用 `detect_scanned_pages()` 识别需要 OCR 的页码
    2. 如果无扫描页，直接返回 `parsed_doc`
    3. 调用 `ocr.recognize(file_path, scanned_pages)`
    4. **部分页失败处理：** 若 `recognize()` 返回结果少于请求的 `scanned_pages`，成功页合并回 `ParsedDocument`，失败页保持原始状态，`metadata["ocr_failed_pages"]` 记录失败页码，不阻塞整体流程
    5. 将 OCR 结果的 `ParsedElement` 替换/合并到对应页面
    6. 标记低置信度元素（`needs_review`）
  - 在 `parse_document()` 流程中（解析后、版面检测前）调用 `_apply_ocr()`
  - 版本号升级：`document_parsing_service` v1.2.0 → v1.3.0
- [ ] Subtask 4.3: 🔄 重构 — 抽取 `_mark_low_confidence()` 为独立方法，对齐 `_apply_layout_detection()` 的降级模式（`try/except` → WARNING + 返回原始结果，但不阻塞流程），更新 `composition_root.py` 中 `_create_parsing_service()` 工厂函数以注入 `ocr`

#### TDD 循环 B：composition_root.py 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写注册验证测试（端口可解析、契约兼容） |
| 🟢 绿 | 在 `composition_root.py` 注册 `ocr` 端口 + 注入到 `DocumentParsingService` |
| 🔄 重构 | 对齐注册顺序和降级模式 |

- [ ] Subtask 4.4: 🔴 红 — 扩展 `tests/contracts/test_port_contract_ocr.py` 验证注册
- [ ] Subtask 4.5: 🟢 绿 — `composition_root.py` 注册：
  ```python
  register_port(PortSpec(
      name="ocr",
      version="v1.0.0",
      interface=OCRPort,
      impl="src.infrastructure.document_parsing.paddleocr_vl_adapter.PaddleOCRVLAdapter",
      lifetime=Lifetime.SCOPED,
      owner="epic-2",
  ))
  ```
  - `_create_parsing_service()` 中：使用 inline try/except 块（与 `layout_detector`/`table_extractor` 一致，**不使用 `_safe_resolve`**）：
    ```python
    _ocr = None
    try:
        _ocr = resolver.resolve("ocr")
    except (ImportError, RuntimeError, OSError) as e:
        logger.warning("OCR 服务不可用，扫描件解析将降级: %s", e)
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"OCR port config error: {e}") from e
    ```
  - `DocumentParsingService` 构造传入 `ocr=_ocr`
  - **ImageParser OCR 注入：** 在 `CompositeDocumentParser` lambda 中，ImageParser 的三个 MIME 注册行传入 `ocr=_ocr`（`ImageParser(ocr=_ocr)`），确保图像格式也受益于 PaddleOCR-VL
- [ ] Subtask 4.6: 🔄 重构 — 验证注册顺序（ocr 必须在 document_parsing_service 之前注册），**版本号 v1.2.0→v1.3.0 三处同步清单：**
    1. `src/composition_root.py` 中 `document_parsing_service` PortSpec 的 `version="v1.3.0"`
    2. `tests/contracts/test_port_contract_layout_detector.py` 中 `test_document_parsing_service_still_registered` 的版本断言更新为 `"v1.3.0"`
    3. 本 Story 文件各处版本引用（Dev Notes/完成标准/Story Version）同步更新

**完成标准/Definition of Done:**
- [ ] `DocumentParsingService` OCR 步骤实现完成
- [ ] OCR 注入/降级模式与 `layout_detector`/`table_extractor` 一致
- [ ] 置信度标记逻辑正确
- [ ] `composition_root.py` 注册 + 工厂函数更新
- [ ] 应用层覆盖率 ≥ 85%
- [ ] Story 2-2a/2-2b 回归测试全部通过

---

### Task 5: Docker Compose 部署配置 + 集成测试

**关联 AC:** AC-5

> **目的：** 将 PaddleOCR-VL-1.6 两服务以 `profiles: [gpu]` 方式直接内联写入 `docker-compose.yml`（与现有 `embedding-api` 一致），
> 实现 GPU 服务可选启动（非 GPU 环境不阻断基础服务）。`deploy/app/paddleocrvl/` 保留为独立参考模板。
> **注意：** 集成测试使用 `httpx.MockTransport` Mock HTTP 优先（fixture 数据须来自真实 API 录播），仅在 GPU 可用时执行真实 OCR 测试。

#### 部署配置

- [ ] Subtask 5.1: **规范 `deploy/app/paddleocrvl/paddleocrvl.yaml` 为参考模板**（文件已存在，修正为规范格式，保留作为独立部署参考）：
  - 服务名修正：`paddleocr-vlm-server` → `paddleocr-vl-vllm`
  - 容器名统一 `sisys-` 前缀：`sisys-paddleocr-vl-api`、`sisys-paddleocr-vl-vllm`
  - 两服务添加 `profiles: [gpu]` 和 `networks: [sisys-network]`
  - VLM healthcheck 端口修正：`8080` → `8118`
  - API 端口变量化：`${PADDLEOCR_VL_API_PORT:-8080}:8080`

- [ ] Subtask 5.2: **规范 `deploy/app/paddleocrvl/envparam`**（对齐变量名）：
  - `API_IMAGE_TAG_SUFFIX` → `API_IMAGE_TAG`，`VLM_IMAGE_TAG_SUFFIX` → `VLM_IMAGE_TAG`
  - 新增 `API_REGISTRY`、`VLM_MODEL_NAME`、`PADDLEOCR_VL_API_PORT`

- [ ] Subtask 5.3: **在 `deploy/app/docker-compose.yml` 中直接内联写入两服务**（与现有 `embedding-api` 模式一致，不使用 `include:`）：

  **`paddleocr-vl-vllm`（VLM 推理 — 内部）：**
  - 镜像：`${PADDLEOCR_VL_REGISTRY:-harbor.sisys.local}/paddleocr-genai-vllm-server:${VLM_IMAGE_TAG:-latest-nvidia-gpu-sm120}`
  - GPU 独占（`deploy.resources.reservations.devices`），内部 `--port 8118`，vLLM backend
  - `container_name: sisys-paddleocr-vl-vllm`，`profiles: [gpu]`，healthcheck 指向 `8118`

  **`paddleocr-vl-api`（API — 对外）：**
  - 镜像：`${PADDLEOCR_VL_REGISTRY:-harbor.sisys.local}/paddleocr-vl:${API_IMAGE_TAG:-latest-nvidia-gpu-sm120}`
  - 端口 `"${PADDLEOCR_VL_API_PORT:-8080}:8080"`，依赖 vllm 服务 healthy
  - `container_name: sisys-paddleocr-vl-api`，`profiles: [gpu]`，healthcheck 指向 `/health`

  **行为：**
  - `docker compose up -d` → 基础服务（Redis/PostgreSQL/...）+ embedding-api
  - `docker compose --profile gpu up -d` → 基础服务 + PaddleOCR-VL 两服务

- [ ] Subtask 5.4: 更新 `.gitignore`：忽略 OCR 模型缓存（Docker volume 管理，不纳入 git）
- [ ] Subtask 5.5: 编写 `docs/deploy/paddleocr-vl-setup.md`（**新建**，含：CUDA 12.9+ 驱动要求、镜像拉取耗时预估 30-60 分钟、`docker compose --profile gpu pull` 提前拉取、`docker compose --profile gpu up -d` 启动、镜像来源验证 `docker image inspect`）

#### 集成测试

- [ ] Subtask 5.6: 创建 `tests/integration/test_integration_ocr.py`：
  - 使用 `httpx.MockTransport` Mock PaddleOCR-VL HTTP API
  - 端到端流程：上传扫描件 → 解析 → OCR → 置信度标记 → 结果持久化
  - 错误场景：OCR 服务不可用降级
  - 验证 `Document.metadata["parse_result"]` 包含 OCR 结果
- [ ] Subtask 5.7: （可选——仅 GPU 可用）真实 OCR 集成测试：
  - `@pytest.mark.skipif(not _gpu_available(), reason="需要 GPU")`
  - 使用真实 Docker PaddleOCR-VL 服务
  - 验证中文/英文识别准确率

**完成标准/Definition of Done:**
- [ ] `cd deploy/app && docker compose up -d` 一键启动所有服务（含 PaddleOCR-VL 两服务）
- [ ] `docker compose ps` 显示两服务均为 healthy
- [ ] 部署文档完整（`docs/deploy/paddleocr-vl-setup.md`）
- [ ] 集成测试通过（Mock HTTP）
- [ ] CI 环境不依赖 GPU，Mock 测试可运行

---

### Task 6: SDD 架构约束验证 + 开发结束验收测试

**关联 AC:** AC-1 ~ AC-5

> **性质说明：** 验证前面 Task 创建的代码是否符合六边形架构约束，以及交付物完成清单。
>
> ⚠️ **架构验证应持续执行，非集中到 Task 6：**
> - Task 1 完成后：运行 `test_arch_document_ocr.py`（OCR domain 部分）+ 检查 domain 层零外部依赖
> - Task 3 完成后：运行 `import-linter` 检查 infrastructure 层依赖方向
> - Task 4 完成后：检查 composition_root 注册方向 + 契约测试
> - Task 6 仅做**全量最终确认**，非首次验证

#### 架构验证测试

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_arch_document_ocr.py`：
  - 领域层零外部依赖验证（`src/domain/ports/ocr.py` 无第三方 import）
  - `src/domain/value_objects/ocr_result.py` 无第三方 import
  - `src/domain/services/scanned_page_detector.py` 无第三方 import
  - 依赖方向验证（domain ← application ← infrastructure）
  - 端口注册完整性（`ocr` 在 `registry.py` 中）
- [ ] Subtask 6.2: 运行全量架构测试 + `import-linter` 检查

#### 开发结束验收测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_ocr.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_ocr.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 6.3: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 6.4: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 6.5: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** `docs/architecture/architecture.md` + Story 2-3/2-4 Dev Notes

- **架构模式:** 六边形架构（Ports & Adapters）— 领域层定义 `OCRPort` Protocol，基础设施层实现 `PaddleOCRVLAdapter`
- **设计约束:** 领域层零外部依赖（仅 Python stdlib），依赖方向 domain ← application ← infrastructure
- **接口治理:** 统一端口注册（`PortSpec` 元数据 + `register_port()`）→ `composition_root.py` 单一注册入口 → 契约测试验证
- **增强注入模式（Story 2-3/2-4 复用）:** 可选构造函数参数（`ocr: OCRPort | None = None`）+ 三级降级策略：
  - Port=None → 跳过增强（不记录日志）
  - 运行时异常 → WARNING 日志 + 返回原始结果（OCR 步骤失败不阻塞解析）
  - 初始化失败 → raise（配置错误，需人工介入）
- **技术栈:** Python 3.11+ / httpx（已有依赖）/ PaddleOCR-VL-1.6（Docker 服务化部署，vLLM backend）

### 关键架构决策

**来源:** 本 Story 架构评审

#### OCR 引擎选型：PaddleOCR-VL-1.6 (vLLM Backend)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **PaddleOCR-VL-1.6 + vLLM** | 109 语言支持，VLM 级文档理解，版面分析+OCR 一体化，vLLM 高性能推理，Apache 2.0 许可，RTX 5090 (Blackwell SM120) 原生支持 | Docker 部署复杂度，镜像较大（~13-15GB），需 CUDA 12.9+ | ✅ 9/10 |
| Tesseract (pytesseract) | 轻量，已在项目中使用，MIT 许可 | 中文准确率低（~70-80%），无法达到 95% 准确率要求，无版面理解 | 4/10 |
| PaddleOCR (PP-OCRv4) | 中文效果好，Apache 2.0 许可 | PaddlePaddle 框架重，ONNX 导出不完整，Python 3.11+ 兼容性待确认，无 VLM 级理解 | 6/10 |
| Azure/AWS OCR API | 免运维，高可用 | 成本高（按页计费），数据出境合规风险（企业战略文档敏感），网络延迟 | 5/10 |

**决策理由：**
1. PaddleOCR-VL-1.6 是 PaddleOCR 最新 VLM 系列，文档理解能力远超传统 OCR
2. RTX 5090 (Blackwell SM120) 已有官方 Docker 镜像支持（`-sm120` 后缀）
3. vLLM backend 是官方推荐的推理引擎，性能最优
4. Apache 2.0 许可无商业合规风险
5. 服务化部署架构清晰：API 服务（8080）+ VLM 推理服务（8118）分离，职责单一

#### 扫描件检测策略：文本密度法 vs ML 分类器

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **文本密度法（纯函数）** | 零依赖，确定性，无模型加载开销，领域层可实现 | 边缘场景（图文混排）可能误判 | ✅ 8/10 |
| ML 分类器（如 PyMuPDF 页面分类） | 准确率高 | 引入额外依赖，推理延迟，AGPL 许可风险 | 5/10 |
| 两阶段（先文本密度 + 不确定时 OCR 兜底） | 兼顾性能和准确率 | 实现复杂度高 | 7/10（V1 可选增强） |

**决策理由：**
1. 文本密度法零外部依赖，可在领域层实现（符合六边形架构约束）
2. MVP 阶段简洁优先，边缘场景后续迭代
3. 阈值可配置（`SCANNED_PAGE_TEXT_DENSITY_THRESHOLD` 默认为 50 字符/页）
4. 即使误判（文本页被 OCR），OCR 结果也不会比原文本差（PaddleOCR-VL 准确率 ≥ 95%）

#### 文本分块策略：VLM 版面分析自然分块 vs 后处理切分

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **VLM 自然分块（1:1 映射）** | 版面语义完整，阅读顺序保证，零额外开销 | 粒度由 VLM 决定，不可控 | ✅ 9/10 |
| 按句子/滑动窗口切分 | 粒度可控，适合语义检索 | 破坏版面语义（表格跨句断裂），增加复杂度 | 5/10 |
| 混合：VLM 分块 + 长文本二次切分 | 兼顾语义和粒度 | 实现复杂，边界判断易出错 | 6/10 |

**决策理由：**
1. PaddleOCR-VL 返回的 `parsing_res_list` 中每个 block 是版面分析后的**语义完整最小单元**（title/text/table/figure），`block_label` 已标注区域类型
2. `parsing_res_list` 按阅读顺序排列，1:1 映射为 `ParsedElement` 保留了这个顺序——这对下游（全文检索、知识图谱）至关重要
3. 更细粒度的切分（按句子、滑动窗口）是 Story 2-8（语义分块）的职责，不应在 OCR 阶段越界处理
4. `ParsedElement.metadata` 中保留 `ocr_format: "markdown"` 和 `original_markdown`，下游如需重新分块有原始数据可用

**实现：** 一个 PaddleOCR-VL block → 一个 `ParsedElement`，`content` 为 `_strip_markdown(block_content)` 纯文本，`metadata` 保留原始 Markdown 和 `block_label`。

```
./
├── deploy/app/
│   ├── docker-compose.yml                  # [MODIFY] 内联添加 paddleocr-vl-vllm + paddleocr-vl-api 两服务（profiles: [gpu]）
│   └── paddleocrvl/                        # [MODIFY] 规范化为参考模板（独立部署参考，修正服务名/网络/healthcheck）
│       ├── paddleocrvl.yaml                # [MODIFY] 参考模板：vLLM + API 两服务定义规范
│       └── envparam                        # [MODIFY] 对齐变量名，新增缺失变量
│
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── __init__.py                  # [MODIFY] 导出 OCRPort
│   │   │   └── ocr.py                       # [NEW] OCRPort Protocol
│   │   ├── value_objects/
│   │   │   └── ocr_result.py                # [NEW] OCRPageResult + OCRConfidenceMark
│   │   ├── services/
│   │   │   └── scanned_page_detector.py     # [NEW] 扫描页检测纯函数
│   │   └── exceptions/
│   │       ├── __init__.py                  # [MODIFY] 导入 ocr_exceptions 模块
│   │       ├── ocr_exceptions.py            # [NEW] OCR 子域异常（EXCEPTION_320/321）
│   │       └── _code_ranges.py              # [MODIFY] 注册 OCR 子域（CODE_RANGES + _CLASS_TO_SUBDOMAIN）
│   │
│   ├── application/
│   │   └── services/
│   │       └── document_parsing_service.py  # [MODIFY] 注入 ocr + _apply_ocr() 方法
│   │
│   ├── infrastructure/
│   │   └── document_parsing/
│   │       ├── paddleocr_vl_adapter.py      # [NEW] PaddleOCRVLAdapter（httpx HTTP 调用）
│   │       └── image_parser.py              # [MODIFY] 可选 ocr 注入（替换 pytesseract）
│   │
│   ├── interfaces/
│   │   └── api/
│   │       └── exception_handlers.py        # [MODIFY] EXCEPTION_320 → 504 / EXCEPTION_321 → 502
│   │
│   └── composition_root.py                  # [MODIFY] 注册 ocr 端口 + 注入 parsing service
│
├── docs/deploy/
│   └── paddleocr-vl-setup.md                # [NEW] 部署指南
│
└── tests/
    ├── unit/
    │   ├── domain/
    │   │   ├── ports/test_ocr_port.py              # [NEW]
    │   │   ├── value_objects/test_ocr_result.py    # [NEW]
    │   │   ├── services/test_scanned_page_detector.py  # [NEW]
    │   │   └── exceptions/test_ocr_exceptions.py      # [NEW] OCR 子域异常测试
    │   ├── application/
    │   │   └── services/test_document_parsing_service_ocr.py  # [NEW]
    │   ├── infrastructure/
    │   │   └── document_parsing/
    │   │       ├── test_paddleocr_vl_adapter.py    # [NEW]
    │   │       └── test_image_parser.py            # [MODIFY] OCR 注入测试
    │   └── architecture/
    │       └── test_arch_document_ocr.py           # [NEW]
    │
    ├── integration/
    │   └── test_integration_ocr.py                 # [NEW]
    │
    ├── acceptance/
    │   ├── test_acceptance_ocr.feature             # [NEW]
    │   └── test_acceptance_ocr.py                  # [NEW]
    │
    └── contracts/
        └── test_port_contract_ocr.py               # [NEW]
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 2-4 表格行列语义提取](./2-4-table-semantic-extraction.md)

**关键学习/Key Learnings:**
1. **[MUST] 可选增强注入模式** — `table_extractor` 作为 Optional 构造参数注入 `DocumentParsingService`，`ocr` 遵循相同模式（默认 None，优雅降级）
2. **[MUST] 三级降级策略一致性** — Port=None→跳过增强（不记日志）；运行时异常→WARNING 日志+返回原始结果；初始化失败→raise（配置错误，不降级）
3. **[MUST] 值对象后向兼容扩展** — `ParsedTable.metadata` 使用 `field(default_factory=dict)`；OCR 结果通过现有 `ParsedElement.confidence` + `metadata` 字段承载，不新增顶层字段
4. **[MUST] 临时文件安全** — OCR 前写临时文件必须使用 `tempfile.NamedTemporaryFile(delete=False)` + `os.fchmod(0o600)` + `try/finally os.unlink()` 确保安全创建和清理（含 `CancelledError` 场景）。PaddleOCR-VL HTTP 调用是 async 的（`httpx.AsyncClient`），无需 `to_thread`，但文件 I/O 仍需 try/finally
5. **[SHOULD] MIME 类型一致性** — `composition_root.py` 中的 MIME 类型应与 `DocumentFormat` 常量匹配，不在基础设施层重新定义

**来源:** [Story 2-3 版面信息保留](./2-3-layout-preservation-doclaynet.md)

**关键学习/Key Learnings:**
1. **[MUST] 契约门禁版本升级** — `document_parsing_service` v1.1.0→v1.2.0 时，PortSpec/Composition Root/契约测试断言三者同步更新；本 Story 升级到 v1.3.0 需同步更新三处（详见 Subtask 4.6 三处同步清单）
2. **[REF] ONNX 模型存储** — DocLayNet ONNX 模型存储在 MinIO model repo，不纳入 git；PaddleOCR-VL 模型由 Docker 镜像管理，同样不纳入 git
3. **[MUST] 领域层零依赖** — 版面检测 ML 模型完全封装在基础设施层，领域层仅定义 Protocol + 值对象；OCR 同理

**来源:** [Story 2-2a 文档解析基础格式](./2-2a-document-parsing-basic-formats.md)

**关键学习/Key Learnings:**
1. **[MUST] PDFParser 文本提取** — `pdf_parser.py` 使用 pypdf 提取文本层，扫描件 PDF 将提取到极少文本（触发 OCR）；常规 PDF 提取到正常文本（跳过 OCR）。**这是扫描页检测的输入来源——检测必须在 PDFParser 解析后执行。**
2. **[MUST] 错误消息脱敏** — Exception `str(e)` 不得直接写入 metadata（安全：防内部路径泄露）；`OCRProcessingError` 只暴露状态码和截断至 200 字符的响应摘要，不暴露完整响应体（企业内部文档内容敏感）
3. **[REF] 安全漏洞** — python-docx XXE 注入（CWE-611），任何 XML 格式解析需 XXE 防护；PaddleOCR-VL HTTP 通信使用 httpx 默认安全配置

**来源:** [Story 2-1 文档上传](./2-1-document-upload-17-formats.md)

**关键学习/Key Learnings:**
1. **[MUST] DI 注册延迟加载陷阱** — impl 字符串拼写错误不会立即报错，需要契约测试覆盖；`ocr` 端口注册后运行 `test_port_contract_ocr.py` 验证
2. **[SHOULD] TestTenant 隔离** — 并行测试 UUID 前缀隔离，新端口测试也必须使用
3. **[MUST] MinIO 流式下载 + 临时文件安全** — `document_storage.retrieve()` 返回 `AsyncIterator[bytes]`，禁止全量加载到内存；OCR 前需写入临时文件（`tempfile` + `os.fchmod(0o600)` + `try/finally os.unlink()`），PaddleOCR-VL API 需要 base64 编码
4. **[SHOULD] _ALLOWED_TEMP_SUFFIXES 白名单** — `.pdf` 已在白名单中，OCR 处理 PDF 无需扩展；若后续支持图像格式 OCR（`.jpg`/`.png`），需添加对应后缀

### 应用到本故事/Applied to This Story:
- [x] OCR 端口注入模式与 `layout_detector`/`table_extractor` 完全对齐
- [x] 降级策略三级一致
- [x] 不新增领域事件，通过现有 `DocumentProcessed` 传递 OCR 结果
- [x] 版本号 v1.2.0 → v1.3.0，PortSpec/Composition Root/契约测试三处同步
- [x] OCR 模型由 Docker 镜像管理，不纳入 git
- [x] PaddleOCR-VL 部署：`docker-compose.yml` 直接内联写入两服务（`profiles: [gpu]`），`paddleocrvl/` 保留为独立参考模板（与 `embedding-api` 模式一致）

---

## 🔧 PaddleOCR-VL-1.6 技术参考

### 部署架构

```
┌─────────────────────────────────────────┐
│         SISYS Application               │
│  DocumentParsingService._apply_ocr()    │
│         │ httpx.AsyncClient             │
│         │ POST /layout-parsing          │
│         ▼                               │
│  localhost:8080 (paddleocr-vl-api)      │
│  ┌─────────────────────────────────┐    │
│  │  Pipeline Service               │    │
│  │  Layout Analysis → VLM Call     │    │
│  └──────────┬──────────────────────┘    │
│             │ internal HTTP             │
│             ▼                           │
│  localhost:8118 (vLLM Server)           │
│  ┌─────────────────────────────────┐    │
│  │  PaddleOCR-VL-1.6-0.9B Model    │    │
│  │  NVIDIA RTX 5090 (Blackwell)     │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### API 调用方式

```python
import base64
import httpx

async with httpx.AsyncClient(timeout=300.0) as client:
    with open(file_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "file": b64_data,
        "fileType": 0,  # 0=PDF, 1=image
    }
    resp = await client.post(
        "http://localhost:8080/layout-parsing",
        json=payload,
    )
    resp.raise_for_status()

    result = resp.json()["result"]
    for page_result in result["layoutParsingResults"]:
        for block in page_result["prunedResult"]["parsing_res_list"]:
            # block: {block_bbox, block_label, block_content, block_id}
            # ⚠️ block_content 为 Markdown 格式，需 _strip_markdown() 转为纯文本后存入 ParsedElement.content
            # ⚠️ 置信度字段存在性待 Task 0 实测 PaddleOCR-VL API 确认
```

### GPU 要求

| 项目 | 要求 |
|------|------|
| GPU | RTX 5090 (Blackwell SM120, 32GB GDDR7) |
| CUDA | ≥ 12.9 |
| Docker | ≥ 19.03 |
| 镜像 | `paddleocr-vl:latest-nvidia-gpu-sm120` (~10GB) |
| VLM 镜像 | `paddleocr-genai-vllm-server:latest-nvidia-gpu-sm120` (~13GB) |
| GPU 内存 | 建议 ≥ 8GB（0.9B 模型约需 4-6GB，vLLM KV cache + CUDA kernel 开销需额外 2-4GB） |
| `gpu-memory-utilization` | 推荐 0.3（0.9B 模型 + vLLM 约需 10-13GB，RTX 5090 32GB 留足余量；可根据模型大小调整） |

### 重要约束

- **Python 版本:** PaddleOCR 支持 3.9-3.13，与项目 Python 3.11+ 兼容
- **vLLM 与 Transformers 冲突:** vLLM 和 SGLang 与 Transformers 引擎所需的 `transformers` 库版本存在冲突，需使用独立 venv（Docker 方式天然隔离）
- **强烈不建议直接调用 VLM 推理服务（8118）:** 必须通过 API 服务（8080）的 `/layout-parsing` 端点调用，VLM 服务仅为内部组件
- **离线部署:** 提供 `-offline` 后缀镜像（如 `paddleocr3.3-nvidia-gpu-sm120-offline`）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | DeepSeek V4 Pro |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-07-29 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/config.yaml` |
| **Instructions** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **异常设计文档** | `docs/architecture/sisys-uni-exception-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-4-table-semantic-extraction.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **PaddleOCR-VL 官方文档** | https://www.paddleocr.ai/latest/version3.x/pipeline_usage/PaddleOCR-VL-NVIDIA-Blackwell.html |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` Epic 2 Stori 2.5 提取
- [ ] 架构约束从 `architecture.md` + Story 2-3/2-4 Dev Notes 提取
- [ ] 前一个故事学习经验整合（Story 2-1/2-2a/2-3/2-4）
- [ ] PaddleOCR-VL-1.6 技术调研完成（API + Docker 部署 + RTX 5090 Blackwell）
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐 Epic 2 统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/2-5-ocr-parsing-scanned-documents.md`

**待创建的文件/To Be Created (Dev Story 实施):**

领域层：
- `src/domain/ports/ocr.py` — OCRPort Protocol
- `src/domain/value_objects/ocr_result.py` — OCRPageResult + OCRConfidenceMark
- `src/domain/services/scanned_page_detector.py` — 扫描页检测
- `src/domain/exceptions/ocr_exceptions.py` — OCR 子域异常（EXCEPTION_320/321）
- `src/domain/exceptions/__init__.py` — 修改（导入 ocr_exceptions 模块）
- `src/domain/exceptions/_code_ranges.py` — 修改（注册 OCR 子域）

应用层：
- `src/application/services/document_parsing_service.py` — 修改（OCR 步骤注入）

基础设施层：
- `src/infrastructure/document_parsing/paddleocr_vl_adapter.py` — PaddleOCRVLAdapter
- `src/infrastructure/document_parsing/image_parser.py` — 修改（可选 OCR 注入）

接口层：
- `src/interfaces/api/exception_handlers.py` — 修改（EXCEPTION_320/321 映射）

组合根：
- `src/composition_root.py` — 修改（ocr 端口注册 + 工厂函数）

部署：
- `deploy/app/paddleocrvl/paddleocrvl.yaml` — PaddleOCR-VL 两服务定义（vLLM + API）
- `deploy/app/paddleocrvl/envparam` — 镜像标签 + VLM 后端配置
- `deploy/app/docker-compose.yml` — 修改（内联添加两服务：`profiles: [gpu]`）
- `docs/deploy/paddleocr-vl-setup.md` — 部署指南（CUDA 12.9+ / 镜像拉取 / GPU 配置）

测试文件：
- `tests/unit/domain/ports/test_ocr_port.py`
- `tests/unit/domain/exceptions/test_ocr_exceptions.py`
- `tests/unit/domain/value_objects/test_ocr_result.py`
- `tests/unit/domain/services/test_scanned_page_detector.py`
- `tests/unit/application/services/test_document_parsing_service_ocr.py`
- `tests/unit/infrastructure/document_parsing/test_paddleocr_vl_adapter.py`
- `tests/unit/architecture/test_arch_document_ocr.py`
- `tests/integration/test_integration_ocr.py`
- `tests/acceptance/test_acceptance_ocr.feature`
- `tests/acceptance/test_acceptance_ocr.py`
- `tests/contracts/test_port_contract_ocr.py`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 2.5 |
| **Story Key** | 2-5-ocr-parsing-scanned-documents |
| **File** | `_bmad-output/implementation-artifacts/stories/2-5-ocr-parsing-scanned-documents.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 2: 文档与数据管理 |
| **价值组** | 文档全生命周期管理 |
| **优先级** | P1-5（V1 优先级） |
| **覆盖 FR** | FR-DM-05 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-6，7 Tasks）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 + OCRPort 注入模式）
4. [x] Previous story learnings integrated 前序故事学习经验已整合（Story 2-1/2-2a/2-3/2-4）
5. [x] PaddleOCR-VL-1.6 tech research completed 技术调研完成
6. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes

> 本 Story 经过 5 轮多 Agent 并行审查修订（科学性与可行性 / 代码一致性 / 合理性与业界最佳实践）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | RTX 5090 显存规格错误：24GB → 实际 32GB GDDR7 | P0 | 修正 GPU 要求表和 AC-5 描述，gpu-memory-utilization 0.7→0.3 |
| 2 | 文本密度公式错误：平均值导致混合 PDF 场景失效 | P0 | 改为逐页独立比较（`char_count < THRESHOLD`），支持混合 PDF |
| 3 | PaddleOCR-VL 置信度字段存在性未验证 | P0 | Task 0 新增 Subtask 0.0：实测 API 响应格式，保存 fixture |
| 4 | 部署文件标记 `[NEW]` 但 `paddleocrvl.yaml`/`envparam` 已存在 | P1 | 改为 `[MODIFY]`，Subtask 5.1/5.2 "创建"→"验证并更新" |
| 5 | `_apply_ocr()` 方法签名缺少 `mime_type` 参数 | P1 | 签名对齐 `_apply_layout_detection` 三参数模式 |
| 6 | 扫描页检测缺少时序依赖说明 | P1 | 明确检测在 PDFParser 解析后执行，依赖 `ParsedPage.elements` |
| 7 | Markdown 到纯文本转换缺失 | P1 | Adapter 增加 `_strip_markdown()` 步骤，`ParsedElement.metadata` 保留原始 Markdown |
| 8 | 置信度默认值 1.0 过于乐观 | P1 | 改为 `None`（未知），触发 `needs_review=True` |
| 9 | HTTP 状态码映射：连接超时 502→504 | P1 | `OCRConnectionError(320)`→504，`OCRProcessingError(321)`→502 |
| 10 | 临时文件安全未定义 | P1 | Adapter 指定 `tempfile` + `os.fchmod(0o600)` + `try/finally os.unlink()` |
| 11 | Docker Compose `include` 阻断所有服务 | P1 | 改用 `profiles: [gpu]`，`docker compose --profile gpu up -d` 选择性启动 |
| 12 | `_safe_resolve` 函数不存在 | P1 | 改为 inline try/except（与 layout_detector/table_extractor 一致） |
| 13 | 版本号三处同步缺显式清单 | P1 | Subtask 4.6 增加三文件路径清单 |
| 14 | 架构验证集中在 Task 6 | P1 | Task 6 增加持续验证说明，每个 Task 完成后即运行对应架构检查 |
| 15 | PDF 按页拆分机制未定义 | P1 | Adapter `recognize()` 增加 `_split_pdf_pages()` 步骤（PaddleOCR-VL 无原生页码过滤） |
| 16 | Dev Notes 错误声称 embedding-api 使用 `include` | P2 | 修正为 `profiles` 机制说明 |
| 17 | `ScannedPageDetection` 值对象定义后未使用 | P1 | 从数据模型中删除（实现中不使用） |
| 18 | Lessons Learned 无优先级区分 | P1 | 全部加 `[MUST]`/`[SHOULD]`/`[REF]` 标签 |
| 19 | Docker Compose include+profiles 内部矛盾（Subtask 5.3 vs AC-5 vs 文件清单） | P0 | 统一为内联写入 docker-compose.yml（与 embedding-api 一致），paddleocrvl/ 保留参考模板 |
| 20 | `tests/fixtures/` 为单文件 `fixtures.py`，非目录，无法存放 JSON fixture | P1 | 路径改为 `tests/data/paddleocr_vl_response_sample.json` |
| 21 | Story 状态 `backlog` 与 sprint-status.yaml `ready-for-dev` 不一致 | P1 | 同步为 `ready-for-dev` |
| 22 | AC→Task 追溯矩阵残留 `include` 描述 | P1 | 更新为 `profiles: [gpu] 内联写入 docker-compose.yml` |
| 23 | 项目结构 exception_handlers 注释 HTTP 映射不精确 | P1 | `EXCEPTION_320/321→502` → `320→504 / 321→502` |
| 24 | 审查日期"待定" + 完成总结未勾选 + Last Updated 未更新 | P2 | 三处全部更新为完成状态 |

---

### 🔍 代码审查发现 Review Findings

**审查日期:** 2026-07-29（5 轮多 Agent 并行审查：科学性与可行性 / 代码一致性 / 合理性与最佳实践 / 交叉验证 / 全量复查）

#### 需决策 Decision Needed

- [ ] —

#### 已修复 Patch

- [ ] —

#### 已推迟 Defer

- [ ] —

---

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-07-29
**最后更新/Last Updated:** 2026-07-29（5 轮多 Agent 并行文档审查修订）
**更新说明/Description:**
- v1.0.0: 创建故事文件——OCR 解析扫描件文档（PaddleOCR-VL-1.6 + RTX 5090 Blackwell）
- 5 轮审查修订：修正 RTX 5090 显存规格、文本密度公式、置信度默认值、HTTP 状态码映射、部署方案简化（include→内联写入）、21 项 P0/P1/P2 问题修复
