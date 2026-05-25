# Epic 2 文档与数据管理 - 测试数据集准备清单

**版本:** 1.0.0
**日期:** 2026-05-25
**用途:** Epic 2 文档解析功能的测试数据集准备指南

---

## 概述

本文档为 SISYS 项目 Epic 2（文档与数据管理）提供完整的测试数据集准备清单。Epic 2 需要支持 17 种文档格式的解析，包括 PDF、Word、TXT、PPT、Excel、图片、HTML、Markdown 及压缩包格式。

测试数据集覆盖正常场景、边界场景和异常场景，确保文档解析功能的健壮性和准确性。

---

## 1. PDF 测试样本

### 1.1 纯文本 PDF

#### 1.1.1 中文纯文本 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 仅含中文文本的 PDF 文档，无表格、图片等复杂元素 |
| **获取方式** | 公开数据集：[中国科学院科技论文](https://www.cnki.net/) 精选论文摘要页 |
| **创建方式** | 使用 WPS/Word 创建中文文档后导出为 PDF |
| **测试目的** | 验证中文字符编码识别、文本提取准确性、段落边界检测 |
| **预期结果** | 文本完整提取，段落结构保持，无乱码，字符识别准确率 ≥99% |
| **文件名建议** | `pdf_text_cn_01_simple.pdf`、`pdf_text_cn_02_multi_page.pdf` |

#### 1.1.2 英文纯文本 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 仅含英文文本的 PDF 文档，包含多段落、多层级标题 |
| **获取方式** | 公开数据集：[arXiv](https://arxiv.org/) 论文 PDF |
| **创建方式** | 使用 LaTeX 生成学术论文格式 PDF |
| **测试目的** | 验证英文字符识别、标题层级解析、段落分割 |
| **预期结果** | 标题层级正确识别，段落边界清晰，特殊字符（如数学符号）正确处理 |
| **文件名建议** | `pdf_text_en_01_simple.pdf`、`pdf_text_en_02_academic.pdf` |

#### 1.1.3 中英混合 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 中英文混合内容的 PDF，包含混排版面（中英文段落交替、双语对照） |
| **获取方式** | 公开数据集：[世界银行报告中文版](https://www.worldbank.org/zh/country/china) |
| **创建方式** | 使用 Word 创建双语对照文档后导出 |
| **测试目的** | 验证中英文混合编码检测、字体切换处理、语言边界识别 |
| **预期结果** | 正确识别段落语言，中英文混排不产生乱码，字符提取完整 |
| **文件名建议** | `pdf_text_mixed_01_bilingual.pdf`、`pdf_text_mixed_02_alternating.pdf` |

### 1.2 含表格的 PDF

#### 1.2.1 简单表格 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含标准规则表格的 PDF，表头明确、无合并单元格 |
| **获取方式** | 自制：使用 Excel 创建表格后打印为 PDF |
| **创建方式** | Excel/WPS 表格导出为 PDF |
| **测试目的** | 验证表格结构识别、行列解析、表头提取 |
| **预期结果** | 表格行列数正确识别，单元格内容准确提取，输出结构化 JSON |
| **文件名建议** | `pdf_table_01_simple.pdf`、`pdf_table_02_multi_header.pdf` |

#### 1.2.2 合并单元格表格 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含跨行、跨列合并单元格的复杂表格 |
| **获取方式** | 自制：使用 Word/WPS 创建带合并单元格的表格后导出 |
| **创建方式** | Word 表格功能创建复杂表格 |
| **测试目的** | 验证合并单元格检测、单元格跨度计算、内容归属判断 |
| **预期结果** | 正确识别合并单元格边界，输出 JSON 包含 rowspan/colspan 信息 |
| **文件名建议** | `pdf_table_03_merged_row.pdf`、`pdf_table_04_merged_col.pdf`、`pdf_table_05_merged_both.pdf` |

#### 1.2.3 跨页表格 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 单个表格跨越多页显示，包含表头重复、续表标识 |
| **获取方式** | 自制：创建超长表格打印为多页 PDF |
| **创建方式** | Word 长表格自动分页导出 |
| **测试目的** | 验证跨页表格合并、表头继承判断、续表识别 |
| **预期结果** | 正确合并跨页表格为单一结构，续表表头处理正确 |
| **文件名建议** | `pdf_table_06_cross_page.pdf`、`pdf_table_07_multi_cross_page.pdf` |

### 1.3 含图片的 PDF

#### 1.3.1 嵌入图片 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | PDF 内嵌入位图图片（JPEG/PNG），图片作为独立元素存在 |
| **获取方式** | 自制：Word 插入图片后导出 PDF |
| **创建方式** | Word/WPS 插入图片功能 |
| **测试目的** | 验证图片元素检测、图片元数据提取、图片位置坐标记录 |
| **预期结果** | 正确识别图片元素，输出图片坐标（x, y, width, height）、格式、大小 |
| **文件名建议** | `pdf_image_01_embedded.jpg.pdf`、`pdf_image_02_multi_image.pdf` |

#### 1.3.2 图文混排 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 文本与图片混合排版，包含图文环绕、图片说明文字 |
| **获取方式** | 公开数据集：[产品手册样本](https://www.yumpu.com/) |
| **创建方式** | 专业排版软件（InDesign/Scribus）或 Word 图文混排 |
| **测试目的** | 验证图文布局解析、阅读顺序判断、图片说明文字关联 |
| **预期结果** | 正确解析图文位置关系，图片与说明文字关联正确 |
| **文件名建议** | `pdf_image_03_text_wrap.pdf`、`pdf_image_04_caption_linked.pdf` |

### 1.4 含公式的 PDF

#### 1.4.1 数学公式 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含行内公式、独立公式块的数学文档，涵盖微积分、线性代数等内容 |
| **获取方式** | 公开数据集：[arXiv 数学论文](https://arxiv.org/list/math/recent) |
| **创建方式** | LaTeX 数学文档编译为 PDF |
| **测试目的** | 验证数学公式识别、LaTeX 还原、公式语义解析 |
| **预期结果** | 公式区域正确识别，可输出 LaTeX 格式或 MathML 结构化表示 |
| **文件名建议** | `pdf_formula_01_math_basic.pdf`、`pdf_formula_02_math_advanced.pdf` |

#### 1.4.2 化学式 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含化学方程式、分子式、结构式的化学文档 |
| **获取方式** | 公开数据集：[ACS Publications](https://pubs.acs.org/) 化学论文 |
| **创建方式** | ChemDraw 或 LaTeX chemfig 宏包生成 |
| **测试目的** | 验证化学符号识别、下标上标处理、分子结构解析 |
| **预期结果** | 化学式正确识别，下标上标结构保持 |
| **文件名建议** | `pdf_formula_03_chemistry.pdf`、`pdf_formula_04_structural.pdf` |

### 1.5 扫描件 PDF（OCR 测试）

#### 1.5.1 中文扫描件 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 纸质中文文档扫描生成的 PDF，包含不同程度的质量（清晰、模糊、倾斜） |
| **获取方式** | 自制：打印中文文档后使用扫描仪生成 |
| **创建方式** | 打印 + 扫描仪/手机扫描 App（如 Scanbot、Adobe Scan） |
| **测试目的** | 验证中文 OCR 识别准确率、倾斜校正、噪声处理 |
| **预期结果** | 中文 OCR 准确率 ≥95%（清晰扫描件），输出置信度标注 |
| **文件名建议** | `pdf_scan_01_cn_clear.pdf`、`pdf_scan_02_cn_blur.pdf`、`pdf_scan_03_cn_tilted.pdf` |

#### 1.5.2 英文扫描件 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 纸质英文文档扫描生成的 PDF |
| **获取方式** | 自制：打印英文文档后扫描 |
| **创建方式** | 打印 + 扫描仪/手机扫描 App |
| **测试目的** | 验证英文 OCR 识别准确率 |
| **预期结果** | 英文 OCR 准确率 ≥98%（清晰扫描件） |
| **文件名建议** | `pdf_scan_04_en_clear.pdf`、`pdf_scan_05_en_degraded.pdf` |

#### 1.5.3 手写内容扫描件 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含手写批注、签名、手写表格的扫描件 |
| **获取方式** | 自制：打印文档后添加手写内容再扫描 |
| **创建方式** | 打印 + 手写 + 扫描 |
| **测试目的** | 验证手写内容 OCR 能力、手写与印刷内容区分 |
| **预期结果** | 手写内容识别（如签名位置检测），手写/印刷内容可区分标注 |
| **文件名建议** | `pdf_scan_06_handwritten.pdf`、`pdf_scan_07_signature.pdf` |

### 1.6 大文件 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 页数超过 100 页的大型 PDF 文档，包含多种内容类型 |
| **获取方式** | 公开数据集：[政府公开报告](https://www.gov.cn/)、[企业年报](https://www.cninfo.com.cn/) |
| **创建方式** | 合并多个 PDF 或使用长文档生成工具 |
| **测试目的** | 验证大文件内存管理、分页处理性能、超时处理 |
| **预期结果** | 处理完成无内存溢出，分页提取正常，总处理时间在可接受范围内 |
| **文件名建议** | `pdf_large_01_100p.pdf`、`pdf_large_02_500p.pdf`、`pdf_large_03_1000p.pdf` |

### 1.7 加密/受保护 PDF

#### 1.7.1 密码加密 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 使用用户密码加密的 PDF 文档 |
| **获取方式** | 自制：使用 PDF 加密工具创建 |
| **创建方式** | `qpdf --encrypt user_password owner_password 256 -- input.pdf output.pdf` |
| **测试目的** | 验证加密检测、密码提示机制、解密后处理能力 |
| **预期结果** | 正确识别加密状态，返回需要密码的错误提示，密码正确后可正常解析 |
| **文件名建议** | `pdf_encrypted_01_user_pw.pdf`、`pdf_encrypted_02_owner_pw.pdf` |

#### 1.7.2 权限受限 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 禁止复制、打印或修改的 PDF 文档 |
| **获取方式** | 自制：使用 PDF 权限设置工具创建 |
| **创建方式** | Adobe Acrobat 权限设置或 `qpdf` 命令行 |
| **测试目的** | 验证权限限制检测、受限处理提示 |
| **预期结果** | 正确识别权限限制，根据限制类型给出相应提示或降级处理 |
| **文件名建议** | `pdf_protected_01_no_copy.pdf`、`pdf_protected_02_no_print.pdf` |

### 1.8 多栏排版 PDF

| 属性 | 描述 |
|------|------|
| **样本描述** | 双栏或多栏排版的 PDF 文档（如学术论文、报纸版面） |
| **获取方式** | 公开数据集：[学术期刊论文](https://www.sciencedirect.com/) |
| **创建方式** | LaTeX 双栏模板或 Word 分栏功能 |
| **测试目的** | 验证多栏布局识别、阅读顺序判断（先左栏后右栏）、跨栏元素处理 |
| **预期结果** | 正确识别栏数，按正确阅读顺序提取文本，跨栏标题正确处理 |
| **文件名建议** | `pdf_multicolumn_01_two_col.pdf`、`pdf_multicolumn_02_three_col.pdf` |

---

## 2. Word 测试样本

### 2.1 .docx 格式

#### 2.1.1 标准 .docx 文档

| 属性 | 描述 |
|------|------|
| **样本描述** | 标准 Word 2007+ 格式文档，包含样式、表格、图片、页眉页脚 |
| **获取方式** | 自制：使用 Microsoft Word 或 WPS 创建 |
| **创建方式** | Word/WPS 创建后保存为 .docx |
| **测试目的** | 验证 .docx 结构解析、样式提取、嵌入元素处理 |
| **预期结果** | 文档结构完整提取，样式信息保留，嵌入元素正确解析 |
| **文件名建议** | `docx_01_standard.docx`、`docx_02_with_styles.docx` |

#### 2.1.2 含表格的 .docx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含复杂表格的 Word 文档（合并单元格、嵌套表格） |
| **获取方式** | 自制 |
| **创建方式** | Word 表格功能创建 |
| **测试目的** | 验证 Word 表格结构解析、合并单元格处理 |
| **预期结果** | 表格结构正确解析，合并单元格信息完整提取 |
| **文件名建议** | `docx_03_table_simple.docx`、`docx_04_table_complex.docx` |

#### 2.1.3 含图片的 .docx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含嵌入图片、图文混排的 Word 文档 |
| **获取方式** | 自制 |
| **创建方式** | Word 插入图片功能 |
| **测试目的** | 验证图片提取、位置信息、图文关联 |
| **预期结果** | 图片正确提取，位置坐标记录，图文关系保持 |
| **文件名建议** | `docx_05_with_images.docx`、`docx_06_text_wrap.docx` |

#### 2.1.4 含页眉页脚的 .docx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含页眉、页脚、页码、页眉图片的 Word 文档 |
| **获取方式** | 自制 |
| **创建方式** | Word 页眉页脚功能 |
| **测试目的** | 验证页眉页脚提取、分页信息、奇偶页差异处理 |
| **预期结果** | 页眉页脚内容正确提取，页码信息保留 |
| **文件名建议** | `docx_07_header_footer.docx`、`docx_08_section_breaks.docx` |

### 2.2 .doc 格式（旧版 Word）

| 属性 | 描述 |
|------|------|
| **样本描述** | Word 97-2003 二进制格式文档 |
| **获取方式** | 公开数据集：[互联网档案馆旧文档](https://archive.org/) 或自制 |
| **创建方式** | Word 2003 或 WPS 兼容模式保存 |
| **测试目的** | 验证旧版格式兼容性、格式转换能力 |
| **预期结果** | 正确解析 .doc 格式，内容完整提取，或提供格式转换建议 |
| **文件名建议** | `doc_01_legacy.doc`、`doc_02_complex.doc` |

### 2.3 大文件 Word

| 属性 | 描述 |
|------|------|
| **样本描述** | 超过 100 页或 50MB 的大型 Word 文档 |
| **获取方式** | 自制：合并多个文档或创建长文档 |
| **创建方式** | Word 长文档功能 |
| **测试目的** | 验证大文件处理性能、内存管理、分块处理 |
| **预期结果** | 处理完成无内存溢出，处理时间在可接受范围内 |
| **文件名建议** | `docx_large_01_100p.docx`、`docx_large_02_50mb.docx` |

---

## 3. TXT 测试样本

### 3.1 UTF-8 编码

| 属性 | 描述 |
|------|------|
| **样本描述** | 标准 UTF-8 编码的纯文本文件，包含中文、英文、特殊字符 |
| **获取方式** | 自制：使用文本编辑器创建 |
| **创建方式** | VSCode/Notepad++ 保存为 UTF-8 |
| **测试目的** | 验证 UTF-8 编码检测、文本提取、特殊字符处理 |
| **预期结果** | 正确识别 UTF-8 编码，文本完整提取，无乱码 |
| **文件名建议** | `txt_utf8_01_cn.txt`、`txt_utf8_02_en.txt`、`txt_utf8_03_mixed.txt` |

### 3.2 GBK/GB2312 编码

| 属性 | 描述 |
|------|------|
| **样本描述** | 使用 GBK 或 GB2312 编码的中文文本文件 |
| **获取方式** | 自制或公开数据集：[旧版中文文档](https://www.gutenberg.org/browse/languages/zh) |
| **创建方式** | 记事本/Notepad++ 选择编码保存 |
| **测试目的** | 验证中文编码自动检测、编码转换能力 |
| **预期结果** | 正确识别 GBK/GB2312 编码，自动转换为 UTF-8 处理 |
| **文件名建议** | `txt_gbk_01_cn.txt`、`txt_gb2312_01_cn.txt` |

### 3.3 不同换行符

| 属性 | 描述 |
|------|------|
| **样本描述** | 分别使用 LF（Unix）、CRLF（Windows）、CR（Mac OS 9）换行符的文本文件 |
| **获取方式** | 自制：使用不同工具创建 |
| **创建方式** | VSCode 选择换行符类型保存，或使用 `dos2unix`/`unix2dos` 转换 |
| **测试目的** | 验证换行符兼容性、行边界识别 |
| **预期结果** | 正确处理所有换行符类型，行边界识别一致 |
| **文件名建议** | `txt_lf_unix.txt`、`txt_crlf_windows.txt`、`txt_cr_macos9.txt` |

### 3.4 空文件

| 属性 | 描述 |
|------|------|
| **样本描述** | 大小为 0 字节的空文本文件 |
| **获取方式** | 自制：`touch empty.txt` |
| **创建方式** | 命令行创建空文件 |
| **测试目的** | 验证空文件处理、边界条件检查 |
| **预期结果** | 正确识别空文件，返回空内容或提示信息，不抛出异常 |
| **文件名建议** | `txt_empty.txt` |

---

## 4. Excel 测试样本

### 4.1 .xlsx 格式

#### 4.1.1 标准 .xlsx 文档

| 属性 | 描述 |
|------|------|
| **样本描述** | 标准 Excel 2007+ 格式电子表格，包含多种数据类型 |
| **获取方式** | 自制：使用 Microsoft Excel 或 LibreOffice Calc 创建 |
| **创建方式** | Excel/LibreOffice 保存为 .xlsx |
| **测试目的** | 验证 .xlsx 结构解析、单元格提取、数据类型识别 |
| **预期结果** | 单元格数据完整提取，数据类型（数字/文本/日期/布尔）正确识别 |
| **文件名建议** | `xlsx_01_standard.xlsx`、`xlsx_02_datatypes.xlsx` |

#### 4.1.2 含公式的 .xlsx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含公式（SUM、VLOOKUP、IF 等）的 Excel 文件 |
| **获取方式** | 自制 |
| **创建方式** | Excel 公式功能创建 |
| **测试目的** | 验证公式检测、公式内容提取、计算结果获取 |
| **预期结果** | 公式表达式正确提取，可选择性获取计算结果 |
| **文件名建议** | `xlsx_03_formulas.xlsx`、`xlsx_04_complex_formulas.xlsx` |

#### 4.1.3 含图表的 .xlsx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含柱状图、饼图、折线图等图表的 Excel 文件 |
| **获取方式** | 自制 |
| **创建方式** | Excel 图表功能创建 |
| **测试目的** | 验证图表检测、图表数据源提取、图表元数据获取 |
| **预期结果** | 图表类型正确识别，图表数据源完整提取 |
| **文件名建议** | `xlsx_05_charts.xlsx`、`xlsx_06_multi_charts.xlsx` |

#### 4.1.4 多 Sheet .xlsx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含多个工作表的 Excel 文件，Sheet 间有/无关联 |
| **获取方式** | 自制 |
| **创建方式** | Excel 多工作表功能 |
| **测试目的** | 验证多 Sheet 解析、Sheet 切换、跨 Sheet 引用处理 |
| **预期结果** | 所有 Sheet 正确识别，内容完整提取，跨 Sheet 引用关联处理 |
| **文件名建议** | `xlsx_07_multi_sheet.xlsx`、`xlsx_08_cross_reference.xlsx` |

### 4.2 .xls 格式（旧版 Excel）

| 属性 | 描述 |
|------|------|
| **样本描述** | Excel 97-2003 二进制格式电子表格 |
| **获取方式** | 公开数据集或自制 |
| **创建方式** | Excel 2003 或 LibreOffice 保存为 .xls |
| **测试目的** | 验证旧版 Excel 格式兼容性 |
| **预期结果** | 正确解析 .xls 格式，内容完整提取 |
| **文件名建议** | `xls_01_legacy.xls`、`xls_02_complex.xls` |

### 4.3 CSV 格式

#### 4.3.1 标准 CSV

| 属性 | 描述 |
|------|------|
| **样本描述** | 标准 CSV 文件，逗号分隔，UTF-8 编码，带表头 |
| **获取方式** | 公开数据集：[Kaggle Datasets](https://www.kaggle.com/datasets)、[UCI ML Repository](https://archive.ics.uci.edu/ml) |
| **创建方式** | Excel 导出 CSV 或文本编辑器创建 |
| **测试目的** | 验证 CSV 解析、分隔符检测、编码处理 |
| **预期结果** | 正确解析 CSV，行列结构完整，编码正确识别 |
| **文件名建议** | `csv_01_standard.csv`、`csv_02_no_header.csv` |

#### 4.3.2 中文 CSV

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含中文内容的 CSV 文件，可能使用不同编码和分隔符 |
| **获取方式** | 自制 |
| **创建方式** | Excel 中文版导出 CSV（默认 GBK 编码，逗号分隔） |
| **测试目的** | 验证中文 CSV 编码检测、分隔符自动识别 |
| **预期结果** | 正确识别中文编码（UTF-8/GBK），正确解析内容 |
| **文件名建议** | `csv_03_cn_utf8.csv`、`csv_04_cn_gbk.csv` |

#### 4.3.3 不同分隔符 CSV

| 属性 | 描述 |
|------|------|
| **样本描述** | 使用不同分隔符的 CSV 文件（分号、制表符、管道符） |
| **获取方式** | 自制或公开数据集：欧洲地区常使用分号分隔 |
| **创建方式** | 文本编辑器创建，设置不同分隔符 |
| **测试目的** | 验证分隔符自动检测能力 |
| **预期结果** | 正确识别分隔符类型，内容完整解析 |
| **文件名建议** | `csv_05_semicolon.csv`、`csv_06_tab.tsv`、`csv_07_pipe.csv` |

---

## 5. PPT 测试样本

### 5.1 .pptx 格式

#### 5.1.1 标准 .pptx 文档

| 属性 | 描述 |
|------|------|
| **样本描述** | 标准 PowerPoint 2007+ 格式演示文稿，包含文本、图片、形状 |
| **获取方式** | 公开数据集：[SlideShare](https://www.slideshare.net/) 下载后转换 |
| **创建方式** | PowerPoint/Keynote/LibreOffice Impress 创建 |
| **测试目的** | 验证 .pptx 结构解析、幻灯片提取、元素识别 |
| **预期结果** | 幻灯片顺序正确，文本和元素完整提取 |
| **文件名建议** | `pptx_01_standard.pptx`、`pptx_02_multi_slide.pptx` |

#### 5.1.2 含图片的 .pptx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含大量图片、图表的演示文稿 |
| **获取方式** | 自制 |
| **创建方式** | PowerPoint 插入图片功能 |
| **测试目的** | 验证图片提取、位置信息、图片元数据获取 |
| **预期结果** | 图片正确提取，位置和大小信息保留 |
| **文件名建议** | `pptx_03_with_images.pptx`、`pptx_04_photo_album.pptx` |

#### 5.1.3 含表格的 .pptx

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含嵌入表格的演示文稿 |
| **获取方式** | 自制 |
| **创建方式** | PowerPoint 表格功能 |
| **测试目的** | 验证表格提取、结构识别 |
| **预期结果** | 表格结构正确解析，数据完整提取 |
| **文件名建议** | `pptx_05_with_tables.pptx` |

### 5.2 .ppt 格式（旧版 PowerPoint）

| 属性 | 描述 |
|------|------|
| **样本描述** | PowerPoint 97-2003 格式演示文稿 |
| **获取方式** | 公开数据集或自制 |
| **创建方式** | PowerPoint 2003 或 LibreOffice 保存为 .ppt |
| **测试目的** | 验证旧版 PPT 格式兼容性 |
| **预期结果** | 正确解析 .ppt 格式，内容完整提取 |
| **文件名建议** | `ppt_01_legacy.ppt`、`ppt_02_complex.ppt` |

---

## 6. 图片测试样本

### 6.1 JPEG/PNG/GIF 格式

| 属性 | 描述 |
|------|------|
| **样本描述** | 不同格式的图片文件（JPEG、PNG、GIF） |
| **获取方式** | 公开数据集：[Unsplash](https://unsplash.com/)、[Pexels](https://www.pexels.com/) |
| **创建方式** | 截图工具、图片编辑软件导出 |
| **测试目的** | 验证图片格式检测、元数据提取、尺寸获取 |
| **预期结果** | 格式正确识别，元数据（EXIF）提取正常，尺寸信息正确 |
| **文件名建议** | `image_01_jpeg.jpg`、`image_02_png.png`、`image_03_gif.gif` |

### 6.2 含文字图片（OCR 测试）

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含文字内容的图片，用于测试 OCR 能力 |
| **获取方式** | 自制：文档截图、扫描图片、拍照 |
| **创建方式** | 截图工具、手机拍照、扫描仪 |
| **测试目的** | 验证图片文字提取（OCR）、中英文识别 |
| **预期结果** | 文字内容正确识别，OCR 准确率达标（中文≥95%，英文≥98%） |
| **文件名建议** | `image_04_text_cn.jpg`、`image_05_text_en.png`、`image_06_text_mixed.jpg` |

### 6.3 不同分辨率图片

| 属性 | 描述 |
|------|------|
| **样本描述** | 不同分辨率和尺寸的图片（低分辨率、高分辨率、超高清） |
| **获取方式** | 公开数据集或自制：图片缩放 |
| **创建方式** | 图片编辑软件调整分辨率 |
| **测试目的** | 验证不同分辨率图片的处理能力、性能表现 |
| **预期结果** | 所有分辨率图片都能正确处理，超大图片有合理的内存管理 |
| **文件名建议** | `image_07_low_res.jpg`、`image_08_hd.jpg`、`image_09_4k.jpg` |

---

## 7. 其他格式

### 7.1 HTML 文件

| 属性 | 描述 |
|------|------|
| **样本描述** | 标准 HTML 文件，包含文本、链接、图片、表格、CSS 样式 |
| **获取方式** | 公开数据集：[Common Crawl](https://commoncrawl.org/)、自制网页保存 |
| **创建方式** | 浏览器"另存为网页"或文本编辑器创建 |
| **测试目的** | 验证 HTML 解析、文本提取、标签处理、编码检测 |
| **预期结果** | 正确提取可见文本，忽略脚本和样式，链接和图片信息保留 |
| **文件名建议** | `html_01_simple.html`、`html_02_complex.html`、`html_03_utf8.html` |

### 7.2 Markdown 文件

| 属性 | 描述 |
|------|------|
| **样本描述** | Markdown 格式文件，包含标题、列表、代码块、表格、链接等元素 |
| **获取方式** | 公开数据集：[GitHub Markdown 文档](https://github.com/) |
| **创建方式** | 文本编辑器创建 .md 文件 |
| **测试目的** | 验证 Markdown 解析、元素提取、结构保留 |
| **预期结果** | Markdown 语法正确解析，结构信息（标题层级、列表层级）保留 |
| **文件名建议** | `markdown_01_simple.md`、`markdown_02_code_blocks.md`、`markdown_03_tables.md` |

### 7.3 压缩包文件

#### 7.3.1 ZIP 压缩包

| 属性 | 描述 |
|------|------|
| **样本描述** | ZIP 格式压缩包，内含多种文档格式 |
| **获取方式** | 自制：将多个测试文件打包 |
| **创建方式** | `zip -r archive.zip files/` 或压缩软件 |
| **测试目的** | 验证 ZIP 解压、批量文档处理、嵌套目录处理 |
| **预期结果** | 正确解压 ZIP 文件，逐个处理内部文档，目录结构保留 |
| **文件名建议** | `zip_01_mixed_docs.zip`、`zip_02_nested_dirs.zip` |

#### 7.3.2 TAR 压缩包

| 属性 | 描述 |
|------|------|
| **样本描述** | TAR 格式压缩包（含 .tar、.tar.gz、.tar.bz2） |
| **获取方式** | 自制 |
| **创建方式** | `tar -czvf archive.tar.gz files/` |
| **测试目的** | 验证 TAR 格式解压、压缩格式检测 |
| **预期结果** | 正确识别压缩类型，解压并处理内部文件 |
| **文件名建议** | `tar_01_plain.tar`、`tar_02_gzip.tar.gz`、`tar_03_bzip2.tar.bz2` |

---

## 8. 异常场景测试数据

### 8.1 空文件

| 属性 | 描述 |
|------|------|
| **样本描述** | 各格式对应的空文件（0 字节） |
| **获取方式** | 自制：`touch empty.pdf` 或创建后清空内容 |
| **创建方式** | 命令行创建或文件编辑器保存空内容 |
| **测试目的** | 验证空文件检测、错误处理、边界条件 |
| **预期结果** | 正确识别空文件，返回明确错误提示，不抛出未处理异常 |
| **文件名建议** | `empty_01.pdf`、`empty_02.docx`、`empty_03.xlsx`、`empty_04.txt` |

### 8.2 超大文件

| 属性 | 描述 |
|------|------|
| **样本描述** | 超过 100MB 的大文件 |
| **获取方式** | 自制：复制填充或使用大文件生成工具 |
| **创建方式** | `fallocate -l 150M large.pdf` 或合并多个文件 |
| **测试目的** | 验证大文件处理策略（分块、流式处理）、内存管理、超时处理 |
| **预期结果** | 有明确的大文件处理策略，内存使用可控，提供处理进度反馈 |
| **文件名建议** | `large_01_100mb.pdf`、`large_02_500mb.pdf`、`large_03_1gb.zip` |

### 8.3 损坏文件

| 属性 | 描述 |
|------|------|
| **样本描述** | 文件头损坏、内容截断、格式错误的文件 |
| **获取方式** | 自制：使用二进制编辑器修改或截断文件 |
| **创建方式** | `dd if=/dev/urandom of=corrupted.pdf bs=1 count=1000` 或截断正常文件 |
| **测试目的** | 验证损坏文件检测、错误处理、错误提示准确性 |
| **预期结果** | 正确识别文件损坏，返回明确的错误类型和提示 |
| **文件名建议** | `corrupted_01_header.pdf`、`corrupted_02_truncated.docx`、`corrupted_03_random.bin` |

### 8.4 错误格式文件

| 属性 | 描述 |
|------|------|
| **样本描述** | 文件扩展名与实际内容不匹配的文件 |
| **获取方式** | 自制：重命名文件扩展名 |
| **创建方式** | `mv actual.txt fake.pdf` |
| **测试目的** | 验证文件类型检测（Magic Number 检测）、扩展名欺骗防护 |
| **预期结果** | 正确识别实际文件类型，返回格式不匹配警告或错误 |
| **文件名建议** | `fake_01_txt_as_pdf.pdf`、`fake_02_jpg_as_docx.docx`、`fake_03_png_as_xlsx.xlsx` |

### 8.5 恶意文件（安全测试）

| 属性 | 描述 |
|------|------|
| **样本描述** | 包含潜在恶意内容的测试文件（非真实恶意软件，而是安全测试样本） |
| **获取方式** | 安全测试工具生成，如 [EICAR 测试文件](https://www.eicar.org/) |
| **创建方式** | EICAR 标准测试字符串或安全测试工具 |
| **测试目的** | 验证安全扫描集成、恶意内容检测、沙箱隔离 |
| **预期结果** | 正确识别潜在风险，拒绝处理或隔离处理 |
| **文件名建议** | `security_01_eicar.txt`、`security_02_macro.docx`（注意：仅在安全环境下使用） |

---

## 9. 测试数据集管理

### 9.1 目录结构建议

```
tests/fixtures/documents/
├── pdf/
│   ├── text/
│   │   ├── pdf_text_cn_01_simple.pdf
│   │   ├── pdf_text_en_01_simple.pdf
│   │   └── pdf_text_mixed_01_bilingual.pdf
│   ├── table/
│   │   ├── pdf_table_01_simple.pdf
│   │   └── pdf_table_03_merged_row.pdf
│   ├── image/
│   │   ├── pdf_image_01_embedded.pdf
│   │   └── pdf_image_03_text_wrap.pdf
│   ├── formula/
│   │   ├── pdf_formula_01_math_basic.pdf
│   │   └── pdf_formula_03_chemistry.pdf
│   ├── scan/
│   │   ├── pdf_scan_01_cn_clear.pdf
│   │   └── pdf_scan_04_en_clear.pdf
│   ├── large/
│   │   ├── pdf_large_01_100p.pdf
│   │   └── pdf_large_02_500p.pdf
│   ├── encrypted/
│   │   └── pdf_encrypted_01_user_pw.pdf
│   └── multicolumn/
│       └── pdf_multicolumn_01_two_col.pdf
├── word/
│   ├── docx_01_standard.docx
│   ├── docx_03_table_simple.docx
│   └── doc_01_legacy.doc
├── txt/
│   ├── txt_utf8_01_cn.txt
│   ├── txt_gbk_01_cn.txt
│   └── txt_empty.txt
├── excel/
│   ├── xlsx_01_standard.xlsx
│   ├── xlsx_03_formulas.xlsx
│   ├── csv_01_standard.csv
│   └── xls_01_legacy.xls
├── ppt/
│   ├── pptx_01_standard.pptx
│   └── ppt_01_legacy.ppt
├── image/
│   ├── image_01_jpeg.jpg
│   ├── image_04_text_cn.jpg
│   └── image_07_low_res.jpg
├── html/
│   └── html_01_simple.html
├── markdown/
│   └── markdown_01_simple.md
├── archive/
│   ├── zip_01_mixed_docs.zip
│   └── tar_02_gzip.tar.gz
├── empty/
│   ├── empty_01.pdf
│   ├── empty_02.docx
│   └── empty_03.xlsx
├── large/
│   ├── large_01_100mb.pdf
│   └── large_02_500mb.pdf
├── corrupted/
│   ├── corrupted_01_header.pdf
│   └── corrupted_02_truncated.docx
├── fake/
│   ├── fake_01_txt_as_pdf.pdf
│   └── fake_02_jpg_as_docx.docx
└── security/
    └── security_01_eicar.txt
```

### 9.2 公开数据集推荐

| 数据集名称 | 网址 | 包含格式 | 适用场景 |
|-----------|------|----------|----------|
| arXiv | https://arxiv.org/ | PDF | 学术论文 PDF |
| Common Crawl | https://commoncrawl.org/ | HTML | 网页文档 |
| Kaggle Datasets | https://www.kaggle.com/datasets | CSV, JSON, 多种 | 结构化数据 |
| UCI ML Repository | https://archive.ics.uci.edu/ml | CSV, TXT | 机器学习数据集 |
| Unsplash | https://unsplash.com/ | JPEG, PNG | 高质量图片 |
| 中国知网 | https://www.cnki.net/ | PDF | 中文论文 |
| 巨潮资讯 | https://www.cninfo.com.cn/ | PDF | 企业年报 |
| EICAR | https://www.eicar.org/ | TXT | 安全测试 |

### 9.3 测试数据维护

1. **版本控制**：将小型测试文件（<1MB）纳入 Git 管理，大型文件使用 Git LFS 或外部存储
2. **定期更新**：每季度审核测试数据集，补充新场景样本
3. **文档记录**：维护 `testdata_index.json`，记录每个样本的元数据
4. **自动化生成**：编写脚本自动生成部分测试数据（如空文件、损坏文件）

---

## 10. 附录

### 10.1 测试数据生成工具

| 工具名称 | 用途 | 命令示例 |
|---------|------|----------|
| `qpdf` | PDF 加密/解密 | `qpdf --encrypt user owner 256 -- in.pdf out.pdf` |
| `convert` (ImageMagick) | 图片格式转换 | `convert input.png output.jpg` |
| `dos2unix` | 换行符转换 | `dos2unix file.txt` |
| `fallocate` | 创建大文件 | `fallocate -l 100M large.bin` |
| `dd` | 创建损坏文件 | `dd if=/dev/urandom of=corrupt.pdf bs=1 count=1000` |
| `zip`/`tar` | 创建压缩包 | `zip -r archive.zip files/` |

### 10.2 密码管理

加密测试文件的密码统一记录在 `tests/fixtures/documents/passwords.json`：

```json
{
  "pdf_encrypted_01_user_pw.pdf": {
    "用户口令": "test123",
    "所有者口令": "owner456"
  },
  "pdf_protected_01_no_copy.pdf": {
    "用户口令": "",
    "所有者口令": "owner789"
  }
}
```

### 10.3 相关文档

- [Epic 2 功能需求](../_bmad-output/planning-artifacts/epics_v1.0.md) - FR-DM-01 至 FR-DM-08
- [测试框架指南](./sdd-tdd-fusion-guide.md) - SDD+TDD 融合开发模式
- [架构设计文档](../architecture/architecture.md) - 文档处理模块架构

---

**作者:** agimtech <agimtech@126.com>

**版权:** Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
