"""基础设施层文档解析器通用阈值

集中管理 PDF/Word/TXT 解析器的文件大小与页数上限，避免阈值散落各处
参考业界：Apache Tika（100MB）/ AWS Textract（10MB 同步）— 本项目取均衡值
"""

from __future__ import annotations

# 单文件最大字节数（防御解压炸弹/内存耗尽 DoS）
MAX_PDF_BYTES: int = 100 * 1024 * 1024  # 100MB
MAX_DOCX_BYTES: int = 50 * 1024 * 1024  # 50MB（DOCX 内嵌 OOXML 可塞 10GB+，必须限制）
MAX_TXT_BYTES: int = 10 * 1024 * 1024  # 10MB（与原 TextParser 行为一致）

# PDF 最大页数（防御超大 PDF 处理超时）
MAX_PDF_PAGES: int = 500
