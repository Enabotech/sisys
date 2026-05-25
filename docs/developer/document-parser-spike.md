"""文档解析库技术选型对比报告

针对 SISYS 项目 Epic 2 文档上传与解析功能，对 PDF/Word/TXT 三种核心格式的解析库进行技术选型对比分析。
涵盖文本提取质量、表格提取能力、图片提取、性能、API 易用性、许可证、依赖复杂度七大维度，
并给出 MVP 阶段推荐方案及六边形架构集成策略。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

# 文档解析库技术选型对比报告 (Spike)

> 文档版本：1.0.0
> 创建日期：2026-05-25
> 最后更新：2026-05-25
> 关联 Epic：Epic 2 — 文档上传与解析
> 状态：待评审

---

## 1. 背景与目标

SISYS 是面向企业高管的 AI 驱动战略规划与决策智能平台。Epic 2 需要实现文档上传和解析功能，
最终支持 17 种文件格式。MVP 阶段先支持 PDF / Word / TXT 三种核心格式。

### 1.1 系统现状

| 组件 | 状态 | 说明 |
|------|------|------|
| MinIO (L4) | 已部署 | 原始文档 WORM 存储 |
| Qdrant (L3) | 已部署 | 向量嵌入存储 |
| pyproject.toml 中的文档依赖 | 已添加 | PyPDF2 3.0.1 / python-docx 1.1.0 / pytesseract 0.3.10 |
| 六边形架构 | 已实施 | domain(零依赖) / application / infrastructure / interfaces |

### 1.2 选型目标

1. **文本提取质量**：中文支持优先（简繁体），格式保留完整（标题/段落/列表层级）
2. **表格提取能力**：行列结构清晰，合并单元格可识别
3. **图片提取**：嵌入图片可提取，带坐标信息（用于 RAG 溯源）
4. **性能**：大文件（50+ 页）处理稳定，内存可控
5. **六边形架构兼容**：domain 层零外部依赖，解析库仅在 infrastructure 层引入
6. **许可证合规**：无 AGPL 等 copyleft 限制（SISYS 为企业商业软件）

---

## 2. PDF 解析库对比

### 2.1 综合对比表

| 维度 | PyMuPDF (fitz) | pdfplumber | pypdf (原 PyPDF2) | pdf2image + OCR |
|------|----------------|------------|-------------------|-----------------|
| **文本提取质量** | 优秀 — C++ 内核，Levenshtein 距离最低，cosine similarity 最高 | 良好 — 文本提取需配置参数 | 基础 — 纯 Python，长文本偶尔乱序 | 取决于 OCR 引擎质量 |
| **中文支持** | 优秀 — 原生 Unicode 支持，CJK 字体处理完善 | 良好 — 依赖 pdfminer.six 的 CJK 支持 | 基础 — 可提取但偶有字符丢失 | 取决于 OCR 语言包 |
| **表格提取** | 支持 — 基础表格识别，复杂表格效果一般 | **最佳** — 独创表格检测算法，行列结构清晰 | 有限 — 无内置表格提取 | 需额外表格识别库 |
| **图片提取** | 优秀 — 提取嵌入图片 + 坐标 + 尺寸 | 良好 — 可提取图片对象 | 基础 — 可提取嵌入图片 | N/A（本身就是图片） |
| **解析速度** | **最快** — C++ 内核 MuPDF，50 页 < 0.5s | 中等 — 纯 Python，50 页 ~3-5s | 中等 — 纯 Python，50 页 ~2-3s | 慢 — 依赖 poppler 渲染 + OCR |
| **内存占用** | 低 — C++ 管理，流式处理 | 中等 — 全页加载到内存 | 中等 — 全页加载 | 高 — 图片渲染占用大 |
| **API 易用性** | 优秀 — `page.get_text()` / `page.get_images()` 一行调用 | 良好 — `page.extract_text()` / `page.extract_tables()` | 良好 — `reader.pages[i].extract_text()` | 复杂 — 多步管道（渲染→OCR→后处理） |
| **许可证** | **AGPL-3.0**（需商业授权） | MIT | BSD-3-Clause | pdf2image: MIT / pytesseract: Apache-2.0 |
| **依赖复杂度** | 低 — 仅 C++ 共享库 | 中等 — 依赖 pdfminer.six | 低 — 纯 Python | 高 — 依赖 poppler + tesseract |
| **维护活跃度** | 高 — Artifex 商业维护 | 高 — 社区活跃 | 高 — PyPA 维护 | 中等 — 稳定但迭代慢 |
| **适用场景** | 高性能文本提取 + 图片定位 | 表格密集型文档 | 简单文本提取 + 合并拆分 | 扫描件 / 纯图片 PDF |

### 2.2 各库详细分析

#### 2.2.1 PyMuPDF (fitz)

**优势：**
- 性能领先：基于 MuPDF C++ 引擎，解析速度约为 pdfplumber 的 5-10 倍
- 文本提取精度最高：学术评测（arXiv 2410.09871v1）显示 Levenshtein 距离最低、cosine similarity 最高
- 图片提取能力完整：可获取嵌入图片的坐标（x0, y0, x1, y1）、尺寸、颜色空间等元数据，适用于 RAG 溯源场景
- 布局分析：支持获取文本块（text block）的边界框，可重建文档结构
- 中文支持：原生 CJK 字体处理，无需额外配置

**风险：**
- **许可证为 AGPL-3.0**：这是最大的风险点。AGPL 要求通过网络使用该软件的用户可获得完整源代码，SISYS 作为企业商业软件，必须向 Artifex 购买商业许可证
- 商业许可证费用需向 Artifex 咨询，年费可能在数千至数万美元级别
- 社区版功能与商业版一致，但合规使用需授权

**结论：** 性能和功能均为最优，但 AGPL 许可证是阻断性风险。若预算允许购买商业许可证，则为首选。

#### 2.2.2 pdfplumber

**优势：**
- **表格提取能力最强**：独创的表格检测算法，基于线条和边框识别表格结构，支持合并单元格识别
- 文本提取质量好：基于 pdfminer.six，布局感知提取
- MIT 许可证：无商业使用限制
- 可视化调试：支持将检测到的表格、文本框渲染为图片，便于调试

**风险：**
- 性能中等：纯 Python 实现，大文件（100+ 页）处理速度明显慢于 PyMuPDF
- 内存占用较高：每页加载为完整对象，大文件可能 OOM
- 文本提取需调参：默认参数可能丢失部分文本，需根据文档特点调整 `x_tolerance` / `y_tolerance`

**结论：** 表格提取场景下的最佳选择，MIT 许可证无合规风险。适合作为 PDF 表格提取的专用工具。

#### 2.2.3 pypdf (原 PyPDF2)

**优势：**
- 纯 Python 实现：无 C 扩展依赖，跨平台兼容性好
- BSD 许可证：无商业使用限制
- 功能全面：除文本提取外，支持合并、拆分、加密、解密、旋转等 PDF 操作
- PyPA 维护：社区活跃，版本迭代稳定（已从 PyPDF2 迁移至 pypdf 4.x）

**风险：**
- 文本提取质量基础：长段落偶尔乱序，CJK 字符可能丢失
- 无内置表格提取：需配合其他库或自行实现
- 性能中等：纯 Python 实现的固有瓶颈

**结论：** 适合简单的文本提取和 PDF 操作（合并/拆分），不适合作为主要解析引擎。

#### 2.2.4 pdf2image + OCR

**优势：**
- 扫描件处理：唯一能处理纯图片/扫描 PDF 的方案
- OCR 精度可控：通过更换 OCR 引擎（Tesseract / PaddleOCR / EasyOCR）调整精度
- 中文 OCR 支持好：安装 `chi_sim` / `chi_tra` 语言包后支持简繁体中文

**风险：**
- 处理链路长：poppler 渲染 → 图片生成 → OCR 识别 → 文本后处理，多步管道
- 性能瓶颈：50 页扫描件处理时间可能超过 30 秒
- 外部依赖重：需要安装系统级 poppler 和 tesseract 二进制
- 内存占用高：图片渲染阶段内存峰值大

**结论：** 扫描件场景的必需方案，但不应作为主流程。建议作为降级策略：先尝试文本提取，失败后走 OCR 通道。

---

## 3. Word 解析库对比

### 3.1 综合对比表

| 维度 | python-docx | docx2txt |
|------|-------------|----------|
| **文本提取质量** | 优秀 — 按段落遍历，样式保留完整 | 良好 — 一行提取全部文本，无样式 |
| **表格提取** | 优秀 — 完整的表格对象模型，支持合并单元格 | 不支持 |
| **图片提取** | 优秀 — 可提取嵌入图片 + 关系引用 | 基础 — 可提取图片到目录 |
| **样式保留** | 优秀 — 可读取字体/大小/颜色/加粗/斜体 | 不支持 |
| **文档创建/修改** | 支持 — 完整的创建和修改能力 | 不支持 |
| **API 易用性** | 良好 — 面向对象 API，需遍历段落 | 优秀 — `docx2txt.process()` 一行搞定 |
| **许可证** | MIT | MIT |
| **依赖复杂度** | 中等 — 依赖 lxml | 低 — 最小依赖 |
| **维护活跃度** | 高 — python-openxml 组织维护 | 低 — 久未更新 |
| **适用场景** | 需要结构化解析（表格/样式/图片） | 仅需快速提取纯文本 |

### 3.2 各库详细分析

#### 3.2.1 python-docx

**优势：**
- 完整的 docx 对象模型：段落 (Paragraph) / 表格 (Table) / 图片 (InlineShape) / 样式 (Style) 全覆盖
- 表格解析能力优秀：`table.rows` / `table.columns` 遍历，`cell.text` 获取文本，支持合并单元格检测
- 图片提取完整：通过 `document.part.related_parts` 获取嵌入图片的二进制数据和元信息
- 样式信息可获取：字体名称、大小、颜色、加粗、斜体、对齐方式等
- MIT 许可证，已在 pyproject.toml 中添加依赖 (1.1.0)

**风险：**
- 依赖 lxml：C 扩展库，在部分环境（如 Alpine Linux）安装可能需要额外配置
- API 相对底层：需要手动遍历段落和表格，无高级文本提取 API

**结论：** Word 文档解析的标准选择，功能全面，已在项目依赖中。无需额外引入。

#### 3.2.2 docx2txt

**优势：**
- 极简 API：`docx2txt.process(file_path)` 一行提取全部文本
- 图片提取：可指定输出目录提取嵌入图片
- 零配置：无额外依赖

**风险：**
- 功能极其有限：无表格提取、无样式保留、无结构化信息
- 项目不活跃：最近更新较少，长期维护存疑
- 不适合复杂文档：企业战略文档通常包含大量表格和格式化内容

**结论：** 不推荐。python-docx 已在项目依赖中且功能更全面，无引入 docx2txt 的必要。

---

## 4. TXT 解析方案

### 4.1 编码检测库对比

| 维度 | chardet | cchardet | charset-normalizer |
|------|---------|----------|-------------------|
| **准确率** | 99.3%（2517 测试文件） | ~55.9% | 高（与 chardet 相当） |
| **速度** | 中等（最新版已大幅提速） | 快（C++ 实现，约 3.5x） | 快（最新 chardet 已超越） |
| **Python 3.11+ 支持** | 完全支持 | 不完全支持（已知兼容性问题） | 完全支持 |
| **API 兼容性** | 标准 API | chardet 兼容（drop-in） | 独立 API |
| **许可证** | LGPL-2.1 | MPL-1.1 | MIT |
| **维护活跃度** | 高 — 2025 年持续更新 | 低 — 久未更新 | 高 — 活跃维护 |
| **编码覆盖数** | 49+ | 较少 | 广泛 |

### 4.2 推荐方案

**编码检测**：使用 Python 标准库 `tokenize` 或 BOM 检测作为首选，chardet 作为降级方案。

理由：
1. 大部分 TXT 文件使用 UTF-8，Python 内置检测（BOM 头 + UTF-8 解码尝试）可覆盖 80%+ 场景
2. chardet 最新版本（5.x）已大幅提升速度（47x faster than 4.0），准确率 99.3%
3. cchardet 在 Python 3.11+ 上存在兼容性问题，且准确率仅 55.9%，不推荐
4. charset-normalizer 作为 chardet 的现代替代品（MIT 许可证），可在 chardet 不够用时引入

### 4.3 换行符处理

统一换行符策略：
- 读取时使用 `open(file, newline='')` 保留原始换行符
- 处理后统一转换为 `\n`（Linux 标准）
- 段落识别：连续两个 `\n` 视为段落分隔符

---

## 5. MVP 阶段推荐方案

### 5.1 格式与库映射

| 格式 | 推荐库 | 备选库 | 理由 |
|------|--------|--------|------|
| **PDF** | pdfplumber | pypdf（简单文本） | 表格提取能力最强，MIT 许可证无合规风险，文本提取质量好 |
| **Word (.docx)** | python-docx | — | 已在项目依赖中，功能全面（表格/样式/图片），MIT 许可证 |
| **TXT** | 标准库 + chardet | charset-normalizer | Python 内置检测 + chardet 降级，覆盖绝大多数编码场景 |

### 5.2 PDF 方案补充说明

**为什么不选 PyMuPDF？**

PyMuPDF 在性能和文本提取质量上优于 pdfplumber，但其 AGPL-3.0 许可证是阻断性风险。
SISYS 作为企业商业软件，使用 AGPL 库需要购买商业许可证。MVP 阶段选择 pdfplumber（MIT）可规避此风险。

**后续可选路径：**
- 若 pdfplumber 性能不满足生产需求，可评估 PyMuPDF 商业许可证采购
- 若需要扫描件 OCR，在 Task 级别引入 pdf2image + pytesseract 作为降级通道

### 5.3 pyproject.toml 依赖变更

当前项目已包含以下依赖：

```toml
# Document Processing
pypdf2 = "^3.0.1"       # 需迁移至 pypdf 4.x（PyPDF2 已停止维护）
python-docx = "^1.1.0"  # Word 解析，保留
openpyxl = "^3.1.2"     # Excel 解析，Epic 2 后续
pillow = "^12.1.1"      # 图片处理，保留
pytesseract = "^0.3.10" # OCR，保留（降级通道）
```

**MVP 需要新增：**

```toml
pdfplumber = "^0.11.0"  # PDF 解析（文本 + 表格）
chardet = "^5.2.0"      # TXT 编码检测（降级方案）
```

**需要迁移：**

```toml
# 移除
pypdf2 = "^3.0.1"
# 替换为（若保留 PDF 操作能力）
pypdf = "^5.0.0"        # PyPDF2 的继任者，API 有变化
```

---

## 6. 六边形架构集成策略

### 6.1 分层设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│ interfaces 层                                                           │
│   FastAPI 路由: POST /api/v1/documents/upload                           │
│   CLI 命令:    sisys document upload                                     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 调用
┌───────────────────────────────▼─────────────────────────────────────────┐
│ application 层                                                          │
│   DocumentProcessingUseCase — 文档处理用例                               │
│   TextExtractorService (应用层端口 Protocol) — 文本提取服务抽象           │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 依赖
┌───────────────────────────────▼─────────────────────────────────────────┐
│ domain 层（零外部依赖）                                                  │
│   Document 实体 — 文档领域模型（format, title, content_ref）              │
│   DocumentParserPort (Protocol) — 文档解析端口接口                       │
│   ParsedDocument 值对象 — 解析结果（text, tables, images, metadata）     │
│   DocumentFormat 枚举 — PDF / DOCX / TXT 等                             │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 实现
┌───────────────────────────────▼─────────────────────────────────────────┐
│ infrastructure 层                                                       │
│   PdfPlumberParser — pdfplumber 实现 DocumentParserPort                 │
│   PythonDocxParser — python-docx 实现 DocumentParserPort                │
│   TxtParser — 标准库 + chardet 实现 DocumentParserPort                  │
│   DocumentParserFactory — 工厂模式，按格式路由到对应解析器               │
│   PytesseractOcrParser — OCR 降级通道（扫描件 PDF）                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 端口接口设计

#### 6.2.1 领域端口 — DocumentParserPort

```python
# src/domain/ports/document_parser.py

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DocumentParserPort(Protocol):
    """文档解析端口接口

    定义统一的文档解析契约，由 infrastructure 层的具体解析器实现。
    遵循六边形架构原则：领域层仅定义接口，不引入任何外部依赖。

    实现类：
        - PdfPlumberParser（pdfplumber）
        - PythonDocxParser（python-docx）
        - TxtParser（标准库 + chardet）
    """

    def parse(self, file_path: str, **kwargs: object) -> ParsedDocument:
        """解析文档，提取文本、表格、图片等结构化内容

        Args:
            file_path: 文档文件路径（由 L4 MinIO 下载到本地临时文件）
            **kwargs: 格式特定参数（如 PDF 页码范围、TXT 编码提示等）

        Returns:
            解析结果，包含提取的结构化内容

        Raises:
            DocumentParseError: 文档解析失败
            UnsupportedFormatError: 不支持的文档格式
        """
```

#### 6.2.2 解析结果值对象 — ParsedDocument

```python
# src/domain/value_objects/parsed_document.py

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableBlock:
    """表格块值对象

    Attributes:
        rows: 行数据，每行为单元格文本列表
        header: 表头行（可选）
        bbox: 边界框坐标 (x0, y0, x1, y1)，用于溯源
    """

    rows: tuple[tuple[str, ...], ...]
    header: tuple[str, ...] | None = None
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class ImageBlock:
    """图片块值对象

    Attributes:
        image_data: 图片二进制数据
        format: 图片格式（PNG / JPEG 等）
        bbox: 边界框坐标 (x0, y0, x1, y1)，用于溯源
        page_number: 所在页码（PDF 专用）
    """

    image_data: bytes
    format: str = ""
    bbox: tuple[float, float, float, float] | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class ParsedDocument:
    """文档解析结果值对象

    不可变值对象，包含文档解析后的结构化内容。
    由 infrastructure 层解析器构造，通过端口接口返回给 application 层。

    Attributes:
        text: 提取的纯文本内容
        tables: 提取的表格列表
        images: 提取的图片列表
        metadata: 文档元数据（页数、作者、创建时间等）
        format: 文档格式标识
    """

    text: str
    tables: tuple[TableBlock, ...] = ()
    images: tuple[ImageBlock, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    format: str = ""
```

### 6.3 端口注册与组合根

```python
# src/composition_root.py — 端口注册示例

# PDF 解析器
container.register(
    PortSpec(
        name="pdf_parser",
        version="1.0.0",
        interface=DocumentParserPort,
        impl="src.infrastructure.external_services.document_processing.pdf_plumber_parser.PdfPlumberParser",
        lifetime="TRANSIENT",  # 每次请求创建新实例，避免状态泄漏
        tags=["document", "parser", "pdf"],
    )
)

# Word 解析器
container.register(
    PortSpec(
        name="docx_parser",
        version="1.0.0",
        interface=DocumentParserPort,
        impl="src.infrastructure.external_services.document_processing.python_docx_parser.PythonDocxParser",
        lifetime="TRANSIENT",
        tags=["document", "parser", "docx"],
    )
)

# TXT 解析器
container.register(
    PortSpec(
        name="txt_parser",
        version="1.0.0",
        interface=DocumentParserPort,
        impl="src.infrastructure.external_services.document_processing.txt_parser.TxtParser",
        lifetime="TRANSIENT",
        tags=["document", "parser", "txt"],
    )
)
```

### 6.4 文档解析工厂

```python
# src/infrastructure/external_services/document_processing/document_parser_factory.py

from __future__ import annotations

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.exceptions.business_exceptions import UnsupportedFormatError


class DocumentParserFactory:
    """文档解析器工厂

    根据文档格式路由到对应的解析器实例。
    通过 composition_root 注入各格式解析器。
    """

    def __init__(self, parsers: dict[str, DocumentParserPort]) -> None:
        """初始化工厂

        Args:
            parsers: 格式到解析器的映射字典
        """
        self._parsers = parsers

    def get_parser(self, format: str) -> DocumentParserPort:
        """获取指定格式的解析器

        Args:
            format: 文档格式标识（如 "pdf", "docx", "txt"）

        Returns:
            对应格式的文档解析器

        Raises:
            UnsupportedFormatError: 不支持的文档格式
        """
        parser = self._parsers.get(format.lower())
        if parser is None:
            raise UnsupportedFormatError(f"不支持的文档格式: {format}")
        return parser
```

### 6.5 解析流程与存储协同

```
用户上传文档 (FastAPI / CLI)
    │
    ├─→ L4 MinIO 存储原始文件（WORM）
    │
    ├─→ DocumentParserFactory.get_parser(format)
    │       │
    │       ├─→ PdfPlumberParser.parse(file_path)
    │       ├─→ PythonDocxParser.parse(file_path)
    │       └─→ TxtParser.parse(file_path)
    │
    ├─→ 返回 ParsedDocument（text + tables + images + metadata）
    │
    ├─→ 文本 → L3 Qdrant 向量嵌入（BGE-M3）
    │
    ├─→ 表格 → L2 PostgreSQL 结构化存储
    │
    ├─→ 图片 → L4 MinIO 单独存储 + 坐标元数据
    │
    └─→ 发布 DocumentProcessed 领域事件（双通道）
```

---

## 7. 潜在风险与缓解措施

### 7.1 风险矩阵

| # | 风险 | 严重度 | 概率 | 缓解措施 |
|---|------|--------|------|----------|
| R1 | pdfplumber 大文件（100+ 页）性能不足 | 中 | 中 | 实现分页流式解析，每页单独处理；生产环境可考虑 PyMuPDF 商业许可证 |
| R2 | pdfplumber 内存占用过高导致 OOM | 高 | 低 | 限制单文件页数上限（MVP: 200 页）；实现 `with pdfplumber.open()` 上下文管理确保资源释放 |
| R3 | 复杂 PDF 表格（多层嵌套、合并单元格）提取失败 | 中 | 中 | pdfplumber 的 `table_settings` 支持自定义线条检测策略；降级为纯文本段落处理 |
| R4 | 扫描件 PDF 无法提取文本 | 高 | 中 | 实现 OCR 降级通道：文本提取结果为空时，自动切换到 pdf2image + pytesseract |
| R5 | TXT 编码检测失败（罕见编码） | 低 | 低 | 降级策略：BOM → chardet → latin-1 兜底；记录告警日志 |
| R6 | python-docx 解析 .doc 格式失败 | 中 | 中 | .doc 格式不在 MVP 范围；解析时检查文件魔数（PK zip header）拒绝 .doc 格式 |
| R7 | PyMuPDF AGPL 许可证合规风险 | 高 | 已规避 | MVP 不引入 PyMuPDF；若后续评估需使用，必须先完成商业许可证采购流程 |
| R8 | pypdf2 已停止维护（项目依赖中的版本） | 低 | 已识别 | 迁移至 pypdf 4.x+ 或直接使用 pdfplumber 替代文本提取功能 |

### 7.2 OCR 降级通道设计

```
PDF 文本提取流程：
    │
    ├─→ 1. pdfplumber 提取文本
    │       │
    │       ├─→ 文本量 > 阈值（如 page_count * 50 字符）→ 成功
    │       │
    │       └─→ 文本量 < 阈值 → 判定为扫描件
    │               │
    │               └─→ 2. OCR 降级通道
    │                       ├─→ pdf2image 渲染为图片（DPI 300）
    │                       ├─→ pytesseract OCR 识别（lang='chi_sim+eng'）
    │                       └─→ 返回 OCR 文本 + 置信度
    │
    └─→ 3. 返回 ParsedDocument（标记提取方式：text / ocr）
```

---

## 8. 后续扩展路线（Epic 2 完整 17 格式）

MVP 完成后，按以下优先级逐步扩展：

| 优先级 | 格式 | 推荐库 | 说明 |
|--------|------|--------|------|
| P1 | Excel (.xlsx) | openpyxl（已在依赖中） | 表格数据直接提取 |
| P1 | CSV | Python 标准库 csv | 结构化数据 |
| P2 | PPT (.pptx) | python-pptx | 演示文稿文本 + 图片 |
| P2 | Markdown | Python 标准库 + markdown 解析 | 结构化文档 |
| P2 | HTML | BeautifulSoup4 | 网页内容提取 |
| P3 | JSON / XML | Python 标准库 json / xml.etree | 结构化数据 |
| P3 | 图片（PNG/JPG） | pytesseract / PaddleOCR | OCR 文字识别 |
| P4 | EPUB | ebooklib | 电子书解析 |
| P4 | RTF | striprtf | 富文本格式 |

---

## 9. 决策总结

### 9.1 MVP 推荐方案

| 格式 | 推荐库 | 许可证 | 理由 |
|------|--------|--------|------|
| **PDF** | pdfplumber | MIT | 表格提取最佳，文本质量好，无合规风险 |
| **Word** | python-docx | MIT | 已在依赖中，功能全面，标准选择 |
| **TXT** | 标准库 + chardet | PSF / LGPL | 内置检测为主，chardet 降级 |

### 9.2 关键决策记录

| 决策编号 | 决策 | 理由 | 影响范围 |
|----------|------|------|----------|
| ADR-DP-001 | PDF 解析选择 pdfplumber 而非 PyMuPDF | AGPL 许可证合规风险 | infrastructure 层 PDF 解析 |
| ADR-DP-002 | 不引入 docx2txt | python-docx 功能更全面且已在依赖中 | infrastructure 层 Word 解析 |
| ADR-DP-003 | TXT 编码检测采用分层降级策略 | 标准 BOM 检测覆盖 80%+ 场景，减少外部依赖 | infrastructure 层 TXT 解析 |
| ADR-DP-004 | 解析器通过 DocumentParserPort Protocol 抽象 | 六边形架构 domain 层零外部依赖约束 | domain/infrastructure 层 |

---

## 参考来源

- [I Tested 7 Python PDF Extractors (2025 Edition)](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257)
- [A Comparative Study of PDF Parsing Tools (arXiv)](https://arxiv.org/html/2410.09871v1)
- [PyMuPDF vs pdfplumber 对比实战 (CSDN)](https://blog.csdn.net/weixin_41544125/article/details/150074943)
- [Comparing 4 Methods for PDF Text Extraction](https://medium.com/social-impact-analytics/comparing-4-methods-for-pdf-text-extraction-in-python-fd34531034f)
- [PyMuPDF 官方文档 — 许可证说明](https://pymupdf.io/)
- [pdfplumber PyPI](https://pypi.org/project/pdfplumber/)
- [python-docx 官方文档](https://python-docx.readthedocs.io/en/latest/user/documents.html)
- [chardet FAQ — 准确率对比](https://chardet.readthedocs.io/en/latest/faq.html)
- [chardet GitHub — 最新版本性能数据](https://github.com/chardet/chardet)
- [Charset Detection in Python (ByteTunnels)](https://bytetunnels.com/posts/charset-detection-python-chardet-cchardet-charset-normalizer/)
