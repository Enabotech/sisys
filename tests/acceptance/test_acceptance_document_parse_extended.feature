# language: zh-CN
功能: Story 2-2b - 文档解析与内容提取（扩展格式）

  作为企业战略人员
  我想要系统解析扩展格式文档（PPTX/Excel/CSV/图像/HTML/Markdown/RTF）
  以便支持 17 种格式完整解析，企业现有各类文档都可处理

  背景:
    假如 Story 2-2a 基础格式解析已实现，DocumentParserPort/ParsedDocument/CompositeDocumentParser 已可用

  # =========================================================================
  # AC-1: PPT/PPTX 文档解析
  # =========================================================================

  场景: AC-1 - 成功解析 PPTX 文档
    假如 有一个包含文本和备注的 PPTX 文件 "strategy.pptx"
    当 系统使用 PptxParser 解析该文件
    那么 parse_status 为 completed
    并且 提取的文本包含幻灯片标题
    并且 备注内容被提取
    并且 每页幻灯片编号作为 page_number

  场景: AC-1 - 解析含表格的 PPTX 文档
    假如 有一个包含内嵌表格的 PPTX 文件 "data.pptx"
    当 系统使用 PptxParser 解析该文件
    那么 parse_status 为 completed
    并且 表格被提取为 ParsedTable

  场景: AC-1 - 解析空 PPTX 文档失败
    假如 有一个无幻灯片的空 PPTX 文件
    当 系统使用 PptxParser 解析该文件
    那么 parse_status 为 failed
    并且 error_message 说明文档为空

  场景: AC-1 - 解析旧版 PPT 格式拒绝
    假如 有一个旧版 PPT 文件 "legacy.ppt"
    当 系统使用 PptxParser 解析 MIME 类型为 application/vnd.ms-powerpoint 的文件
    那么 parse_status 为 failed
    并且 error_message 建议转换为 PPTX

  # =========================================================================
  # AC-2: Excel 文档解析（XLSX/XLS）
  # =========================================================================

  场景: AC-2 - 成功解析多 Sheet XLSX 文档
    假如 有一个包含多个 Sheet 的 XLSX 文件 "data.xlsx"
    当 系统使用 ExcelParser 解析该文件
    那么 parse_status 为 completed
    并且 每个 Sheet 独立输出为 ParsedTable
    并且 sheet 名称存储于 ParsedTable.metadata["sheet_name"]

  场景: AC-2 - 解析旧版 XLS 格式拒绝
    假如 有一个旧版 XLS 文件 "legacy.xls"
    当 系统使用 ExcelParser 解析 MIME 类型为 application/vnd.ms-excel 的文件
    那么 parse_status 为 failed
    并且 error_message 建议转换为 XLSX

  # =========================================================================
  # AC-3: CSV 文档解析
  # =========================================================================

  场景: AC-3 - 成功解析 CSV 文档
    假如 有一个 UTF-8 编码的 CSV 文件 "export.csv"
    当 系统使用 CSVParser 解析该文件
    那么 parse_status 为 completed
    并且 输出单页结构包含一个 ParsedTable
    并且 表头和数据显示正确

  场景: AC-3 - 解析空 CSV 文档失败
    假如 有一个空 CSV 文件
    当 系统使用 CSVParser 解析该文件
    那么 parse_status 为 failed

  # =========================================================================
  # AC-4: 图像文档解析（JPEG/PNG/GIF）
  # =========================================================================

  场景: AC-4 - 成功提取 JPEG 图像元数据
    假如 有一个 JPEG 图像文件 "chart.jpg"
    当 系统使用 ImageParser 解析该文件
    那么 parse_status 为 completed
    并且 images 数组包含图像元数据（format/width/height/mode）
    并且 image 元素的 content 为空字符串

  场景: AC-4 - GIF 仅处理第一帧
    假如 有一个多帧 GIF 图像文件 "animation.gif"
    当 系统使用 ImageParser 解析该文件
    那么 parse_status 为 completed
    并且 images 数组仅包含 1 个元素

  # =========================================================================
  # AC-5: HTML 文档解析
  # =========================================================================

  场景: AC-5 - 成功解析 HTML 文档
    假如 有一个包含标题、段落和表格的 HTML 文件 "report.html"
    当 系统使用 HTMLParser 解析该文件
    那么 parse_status 为 completed
    并且 文本提取包含标题和段落内容
    并且 标题层级映射到 metadata.style
    并且 HTML 表格被提取为 ParsedTable

  场景: AC-5 - 解析空 HTML 文档失败
    假如 有一个空 body 的 HTML 文件
    当 系统使用 HTMLParser 解析该文件
    那么 parse_status 为 failed

  # =========================================================================
  # AC-6: Markdown 文档解析
  # =========================================================================

  场景: AC-6 - 成功解析 Markdown 文档
    假如 有一个包含标题、段落、表格和代码块的 Markdown 文件 "plan.md"
    当 系统使用 MarkdownParser 解析该文件
    那么 parse_status 为 completed
    并且 标题层级识别正确（# → h1，## → h2）
    并且 段落按连续空行分割
    并且 Markdown 表格被提取为 ParsedTable
    并且 代码块内容保留

  场景: AC-6 - 解析空 Markdown 文档失败
    假如 有一个空 Markdown 文件
    当 系统使用 MarkdownParser 解析该文件
    那么 parse_status 为 failed

  # =========================================================================
  # AC-7: RTF 文档解析
  # =========================================================================

  场景: AC-7 - 成功解析 RTF 文档
    假如 有一个包含文本的 RTF 文件 "memo.rtf"
    当 系统使用 RTFParser 解析该文件
    那么 parse_status 为 completed
    并且 提取到 RTF 文本内容

  场景: AC-7 - 解析空 RTF 文档失败
    假如 有一个仅含 RTF 头部的空 RTF 文件
    当 系统使用 RTFParser 解析该文件
    那么 parse_status 为 failed

  # =========================================================================
  # AC-8: CompositeDocumentParser 扩展与集成
  # =========================================================================

  场景: AC-8 - 所有 17 种格式 MIME 路由正确
    假如 Composition Root 已注册所有扩展格式解析器
    当 实例化 CompositeDocumentParser
    那么 MIME 路由表包含预期 15 种 MIME 类型
    并且 document_parser 端口版本为 v1.1.0

  场景: AC-8 - 不支持的 MIME 类型返回失败
    假如 有一个未知 MIME 类型的文件
    当 系统使用 CompositeDocumentParser 解析该文件
    那么 parse_status 为 failed
    并且 返回 ParsedDocument 而非抛异常
    并且 error_message 包含明确错误描述
