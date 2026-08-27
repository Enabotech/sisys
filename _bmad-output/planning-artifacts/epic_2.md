## Epic 2: 文档与数据管理 ✅ 已完成

**目标：** 实现 17 种格式文档的上传、解析、版本管理和语义分块，支持高保真溯源。

**包含 FR：** DM-01, DM-02, DM-03, DM-04, DM-05, DM-06, DM-07, DM-08

Epic 2 ✅ 已完成（2026-08-04 回顾），全部 9 个 Story Done，验收测试全覆盖。

**📦 价值组：文档全生命周期管理**
> 用户可以上传、解析、管理和溯源各类文档

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 2.1 | 文档上传（17 种格式） | 用户可以上传企业现有各类文档 | 依赖 Epic 1 Story 1.7（MinIO 存储） | **P0-1** |
| Story 2.2a | **文档解析与内容提取（基础格式）** | 支持 PDF/Word/TXT 解析，MVP 核心格式 | 依赖 Story 2.1 | **P0-2a（关键路径）** |
| Story 2.2b | **文档解析与内容提取（扩展格式）** | 支持 17 种格式完整解析（PPT/Excel/图像等） | 依赖 Story 2.2a | P1-2b |
| Story 2.3 | 版面信息保留（DocLayNet） | 支持高保真溯源至原始文档坐标点 | 依赖 Story 2.2a | **P0-3（关键路径）** |
| Story 2.4 | 表格行列语义提取 | 财务数据不失真，支持后续分析 | 依赖 Story 2.2a | P1-4 |
| Story 2.5 | OCR 解析（扫描件/图像 PDF） | 历史纸质文档和扫描件可被处理 | 依赖 Story 2.2a | P1-5 |
| Story 2.6 | 文档版本快照 | 支持版本追溯和回滚 | 依赖 Story 2.2a, Epic 1 Story 1.7 | P1-6 |
| Story 2.7 | 元数据标准化校验 | 确保文档元数据完整性和可追溯性 | 依赖 Story 2.2a | P1-7 |
| Story 2.8 | 语义分块 | 检索结果更符合语义完整性 | 依赖 Story 2.2a, Epic 1 Story 1.6 | P1-8 |

**✅ 依赖关系验证：**
- Epic 2 依赖 Epic 1 的存储层（Story 1.6 Qdrant, Story 1.7 MinIO）
- Epic 2 内部故事依赖均为**顺序依赖**（文档处理流水线）
- Epic 2 可独立交付价值（用户上传和管理文档）
- 不依赖 Epic 3-8

**⚠️ 关键路径说明：**
- **Story 2.3（版面信息保留）是 Epic 3 Story 3.8（高保真溯源）的前置依赖**
- **执行顺序：Story 2.1 → Story 2.2a（基础格式）→ Story 2.3 → Epic 3 Story 3.8**
- Story 2.3 必须提前至前 3 个 Story 执行，否则影响 Epic 3 溯源功能交付
- **Story 2.2b（扩展格式）可延至 V1，不影响 MVP 核心功能**

### Story 2.1: 文档上传（17 种格式）

As a **企业战略人员**,
I want **上传 17 种格式的文档（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html + zip/tar 压缩包）**,
So that **系统可以处理企业现有各类文档**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 文档上传测试 - 验证 17 种格式支持
   - [ ] 分片上传测试 - 验证断点续传
   - [ ] 批量上传测试 - 验证并发处理

2. **性能要求**
   - [ ] 上传延迟 P95<100ms
   - [ ] 并发上传≥20
   - [ ] 总大小支持≤20GB

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_document_upload.py` - 单元测试
   - [ ] `tests/integration/test_integration_document_upload.py` - 集成测试

**实施指南:**

**Given** 用户已登录并具有上传权限
**When** 拖拽或选择文件上传（支持批量，总大小≤20GB）
**Then** 系统接收所有支持格式，显示上传进度
**And** 支持分片上传和断点续传

### Story 2.2a: 文档解析与内容提取（基础格式）

As a **企业战略人员**,
I want **系统解析基础格式文档（PDF/Word/TXT）并提取文本、表格、图像、公式内容**,
So that **MVP 核心格式支持，非结构化文档转化为结构化知识资产**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 文档解析测试 - 验证 PDF/Word/TXT 格式支持
   - [ ] 内容提取测试 - 验证文本/表格/图像/公式提取
   - [ ] 准确率测试 - 验证解析准确率≥95%

2. **性能要求**
   - [ ] 解析延迟 P95<500ms
   - [ ] 解析准确率≥95%
   - [ ] 并发解析≥10

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_document_parse.py` - 单元测试
   - [ ] `tests/integration/test_integration_document_parse.py` - 集成测试

**实施指南:**

**Given** 文档已上传完成（PDF/Word/TXT 格式）
**When** 系统执行文档解析
**Then** 提取文本、表格、图像、公式内容，输出结构化 JSON
**And** 解析准确率≥95%（抽样验证，仅基础格式）
**And** 支持 DocLayNet 版面信息保留（用于 Story 2.3）

**依赖关系：** 依赖 Story 2.1（文档上传）
**执行优先级：** P0-2a（MVP，关键路径）

### Story 2.2b: 文档解析与内容提取（扩展格式）

As a **企业战略人员**,
I want **系统解析扩展格式文档（PPT/Excel/图像/HTML 等）并提取内容**,
So that **支持 17 种格式完整解析，企业现有各类文档都可处理**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 文档解析测试 - 验证 PPT/Excel/图像/HTML 格式支持
   - [ ] OCR 测试 - 验证扫描件/图像 PDF 解析
   - [ ] 表格语义测试 - 验证合并单元格/跨页表格识别

2. **性能要求**
   - [ ] 解析延迟 P95<500ms
   - [ ] 解析准确率≥95%
   - [ ] 并发解析≥10

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_document_parse_extended.py` - 单元测试
   - [ ] `tests/integration/test_document_parse_extended_integration.py` - 集成测试

**实施指南:**

**Given** 文档已上传完成（PPT/PPTX/XLS/XLSX/CSV/JPEG/PNG/GIF/HTML 等扩展格式）
**When** 系统执行文档解析
**Then** 提取文本、表格、图像、公式内容，输出结构化 JSON
**And** 解析准确率≥95%（抽样验证，扩展格式）
**And** 支持 OCR 解析（扫描件/图像 PDF，中/英）
**And** 支持表格语义提取（合并单元格/跨页表格）

**依赖关系：** 依赖 Story 2.2a（基础格式解析）
**执行优先级：** P1-2b（V1，扩展格式支持）

### Story 2.3: 版面信息保留（DocLayNet 格式）

As a **分析师**,
I want **系统保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式**,
So that **支持高保真溯源至原始文档坐标点**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 版面信息测试 - 验证 DocLayNet 格式支持
   - [ ] 坐标记录测试 - 验证元素坐标 x/y/width/height
   - [ ] 溯源测试 - 验证 Bounding Box 级溯源

2. **性能要求**
   - [ ] 坐标记录延迟 P95<100ms
   - [ ] 坐标准确率≥99%
   - [ ] ONNX 格式跨平台推理支持

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_document_layout.py` - 单元测试
   - [ ] `tests/integration/test_document_layout_integration.py` - 集成测试

**实施指南:**

**Given** 文档解析完成
**When** 记录文档元素坐标信息
**Then** 采用 DocLayNet 标准格式（支持 ONNX 格式跨平台推理）
**And** 坐标信息用于 Bounding Box 级溯源

### Story 2.4: 表格行列语义提取

As a **财务分析师**,
I want **系统提取表格的行列语义，输出包含表头与列类型的结构化 JSON**,
So that **财务数据不失真，支持后续分析**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 表格解析测试 - 验证 xls/xlsx/csv/PDF 表格支持
   - [ ] 表头提取测试 - 验证表头识别
   - [ ] 列类型测试 - 验证列类型识别
   - [ ] 合并单元格测试 - 验证合并单元格语义还原
   - [ ] 跨页表格测试 - 验证跨页表格识别

2. **性能要求**
   - [ ] 表格解析延迟 P95<500ms
   - [ ] 表头识别准确率≥95%
   - [ ] 列类型识别准确率≥95%

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_table_extraction.py` - 单元测试
   - [ ] `tests/integration/test_table_extraction_integration.py` - 集成测试

**实施指南:**

**Given** 文档包含表格（xls/xlsx/csv/PDF 表格）
**When** 系统执行表格解析
**Then** 提取表头、列类型、行列语义，输出结构化 JSON
**And** 支持合并单元格语义还原与跨页表格识别（V1）

### Story 2.5: OCR 解析（扫描件/图像 PDF）

As a **企业战略人员**,
I want **系统对扫描件或图像 PDF 进行 OCR 解析（中/英），提取置信度并标注**,
So that **历史纸质文档和扫描件可被系统处理**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] OCR 测试 - 验证扫描件/图像 PDF 解析
   - [ ] 中文 OCR 测试 - 验证中文识别
   - [ ] 英文 OCR 测试 - 验证英文识别
   - [ ] 置信度测试 - 验证置信度评分输出

2. **性能要求**
   - [ ] OCR 解析延迟 P95<1s
   - [ ] 中文识别准确率≥95%
   - [ ] 英文识别准确率≥95%
   - [ ] 置信度评分准确率≥90%

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_ocr.py` - 单元测试
   - [ ] `tests/integration/test_ocr_integration.py` - 集成测试

**实施指南:**

**Given** 上传的文档是扫描件或图像 PDF
**When** 系统执行 OCR 解析
**Then** 提取文本内容，输出置信度评分
**And** 支持中文和英文识别
**And** 置信度评分用于后续质量验证
**And** 置信度<0.85 时自动标注为"待人工复核"

### Story 2.6: 文档版本快照

As a **文档管理员**,
I want **创建文档版本快照，系统记录操作者、时间戳与差异摘要**,
So that **支持版本追溯和回滚**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 版本快照测试 - 验证版本创建
   - [ ] 差异摘要测试 - 验证 diff 计算
   - [ ] 版本冲突测试 - 验证乐观锁/悲观锁

2. **性能要求**
   - [ ] 版本创建延迟 P95<100ms
   - [ ] 差异计算延迟 P95<200ms
   - [ ] 并发版本控制≥10

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_document_version.py` - 单元测试
   - [ ] `tests/integration/test_document_version_integration.py` - 集成测试

**实施指南:**

**Given** 文档已存在于系统
**When** 用户上传新版本或修改文档
**Then** 系统创建版本快照，记录操作者、时间戳、差异摘要（diff）
**And** 支持版本冲突检测（乐观锁/悲观锁可选）

### Story 2.7: 元数据标准化校验

As a **数据治理工程师**,
I want **系统校验入库文档的最小元字段集（creator/created_at/source/license/business_domain）**,
So that **确保文档元数据完整性和可追溯性**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 元数据校验测试 - 验证最小元字段集
   - [ ] 阻断测试 - 验证关键字段缺失自动阻断

2. **性能要求**
   - [ ] 元数据校验延迟 P95<50ms
   - [ ] 元数据校验准确率 100%

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_metadata_validation.py` - 单元测试
   - [ ] `tests/integration/test_metadata_validation_integration.py` - 集成测试

**实施指南:**

**Given** 文档解析完成准备入库
**When** 系统校验元数据
**Then** 最小元字段集完整（creator/created_at/source/license/business_domain）
**And** 关键字段缺失自动阻断入库

### Story 2.8: 语义分块

As a **RAG 工程师**,
I want **系统对文档进行语义分块（基于文档语义边界而非固定字数切片）**,
So that **检索结果更符合语义完整性**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 语义分块测试 - 验证基于文档语义边界切片
   - [ ] 段落边界测试 - 验证段落边界识别
   - [ ] 章节边界测试 - 验证章节边界识别
   - [ ] 表格边界测试 - 验证表格边界识别

2. **性能要求**
   - [ ] 语义分块延迟 P95<500ms
   - [ ] 平均片段长度≈300 tokens（允许配置）
   - [ ] 语义完整性≥90%

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_semantic_chunking.py` - 单元测试
   - [ ] `tests/integration/test_semantic_chunking_integration.py` - 集成测试

**实施指南:**

**Given** 文档解析完成
**When** 系统执行语义分块
**Then** 基于文档语义边界（段落、章节、表格边界）进行切片
**And** 平均片段长度目标≈300 tokens（允许配置）
