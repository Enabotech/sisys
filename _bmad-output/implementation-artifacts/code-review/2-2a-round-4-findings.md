# Story 2-2a 第 4 轮代码审查报告

**日期**: 2026-06-02
**审查模式**: 3 Agent 并行（Deep Correctness + Error Message Audit + Cross-Layer Consistency）
**审查范围**: Story 2-2a 全部生产代码（领域/应用/基础设施层）

---

## P0 发现（3 项）

### 深度正确性

| ID | 描述 | 文件 |
|----|------|------|
| F39 | `_download_to_temp` L155 `os.fchmod` 在 try 块之前 — 若 fchmod 抛异常，NamedTemporaryFile 句柄泄漏 + 孤儿文件残留 | document_parsing_service.py:155 |
| F40 | TextParser L82-101 解析主逻辑无 `except Exception` 包裹 — 与 PDF/Word 解析器防御深度不一致，`_detect_and_decode`/`_split_paragraphs` 异常直接穿透到 Service 层 | text_parser.py:82-101 |

### 错误消息审计

| ID | 描述 | 文件 |
|----|------|------|
| F41 | Service L126 `str(e)` 直接写入 `metadata["parse_error"]` — 异常消息可能包含内部文件路径（如 `/home/app/data/xxx.pdf`）、数据库连接串片段，违反 OWASP 安全脱敏原则 | document_parsing_service.py:126 |

---

## P1 发现（8 项）

| ID | 来源 | 描述 |
|----|------|------|
| F42 | DeepCorrectness | `_detect_and_decode` L116 `errors="replace"` 全部编码失败后产生 � 损坏文本但仍返回 completed — 调用方无法区分"正常解析"与"损坏文本" |
| F43 | DeepCorrectness | `_download_to_temp` L159 `tmp.write(chunk)` 同步 IO 在 async 循环中阻塞事件循环（与 R2 F12 同一根因，不同位置） |
| F44 | DeepCorrectness | PDF/Word `os.path.getsize` OSError 返回 failed + 日志，但 TXT L61 仅 `logger.exception` + 返回 failed — 日志级别不一致（TXT 用 exception 含 traceback，PDF/Word 的行为需核实） |
| F45 | ErrorAudit | PDF L140 错误消息"请检查文件是否损坏或重试"与 Word L123 完全相同 — 两个解析器使用相同的通用消息，调用方无法区分哪个解析器失败 |
| F46 | ErrorAudit | TXT L56-58 错误消息包含内部实现细节"当前版本不支持分块处理" — 用户面向的消息不应承诺未来功能 |
| F47 | CrossLayer | `CompositeDocumentParser.parse()` L44 对不支持的 MIME 抛出 `ValueError`，但 PDF/Word/Text 解析器对错误统一返回 `ParsedDocument(failed)` — 同一端口接口的两种错误处理模式不一致 |
| F48 | CrossLayer | Service L79-80 直接修改 `document.metadata`（mutable dict），而 L89 同样直接修改 `parse_status` — 领域实体可变修改分散在应用层多处，违反领域封装原则 |
| F49 | CrossLayer | `_limits.py` 阈值定义在 `infrastructure` 层，但被 `text_parser.py`（也在 infrastructure）引用 — 阈值是业务规则应属于 domain 或至少 application 层配置 |

---

## P2 发现（14 项）

| ID | 来源 | 描述 |
|----|------|------|
| F50 | DeepCorrectness | PDF L111 循环内 `page.extract_text() or ""` — 每页调用 extract_text 可能触发 pypdf 内部缓存失效，大 PDF 性能退化 |
| F51 | DeepCorrectness | Word L96 `for row in table.rows` 嵌套 `for cell in row.cells` — python-docx 对合并单元格会多次返回同一 cell，导致数据重复 |
| F52 | DeepCorrectness | `_download_to_temp` L161 `hasattr(stream, "aclose")` — 鸭子类型检查脆弱，若流对象有 aclose 但语义不同会静默错误 |
| F53 | DeepCorrectness | TXT L85 `_split_paragraphs` 结果仅过滤 `p.strip()` 非空 — 全空白行（如 `\t  \t`）会通过 strip 检查但实际无内容 |
| F54 | DeepCorrectness | PDF L78-79 `with open(file_path, "rb") as f: reader = PdfReader(f)` — PdfReader 在 with 块内创建但可能在块外惰性读取页面，文件句柄已关闭 |
| F55 | ErrorAudit | TXT L68 错误消息"无法访问文件" — 覆盖了"文件不存在"和"权限不足"两种不同根因，用户无法采取针对性行动 |
| F56 | ErrorAudit | Word L53 错误消息"请转换为 DOCX" — 未告知用户如何转换或用什么工具 |
| F57 | ErrorAudit | PDF L73 错误消息含"可能为解压炸弹" — 安全术语暴露给最终用户，不应出现在用户面向消息中 |
| F58 | ErrorAudit | Service L126 `str(e)` 可能暴露 pypdf/python-docx 库版本信息（异常消息含模块路径） |
| F59 | CrossLayer | `ParsedDocument.to_dict()` 各层均使用 `dict[str, Any]` 返回类型 — 缺少 TypedDict 约束，JSON 序列化格式无编译期保证 |
| F60 | CrossLayer | PDF/Word/TXT 解析器各自生成 `doc_id = str(uuid.uuid4())`，但 Service L101 用 `replace` 覆盖 — 双重 ID 生成浪费且容易混淆 |
| F61 | CrossLayer | `ParsedDocument.is_failed()`/`is_completed()` 封装了字符串比较，但 Service L103 直接调用 `.is_failed()` 后又访问 `.error_message` — 封装不一致 |
| F62 | CrossLayer | `_ALLOWED_TEMP_SUFFIXES` 定义在 Service 类外部模块级，但与 `_download_to_temp` 强耦合 — 应作为类常量或注入配置 |
| F63 | DeepCorrectness | `_download_to_temp` L150 `os.path.splitext(object_key)[1].lower() or ".tmp"` — 若 object_key 无后缀（如 `"document"`），splitext 返回 `""`，lower 后仍为 `""`，falsy 走 `.tmp` 兜底正确，但逻辑隐晦应显式判断 |

---

## 跨层一致性深度分析

### 错误处理模式对比

| 解析器 | 输入校验层 | 解析异常包裹 | 错误返回方式 |
|--------|-----------|-------------|-------------|
| PDFParser | ✅ OSError + 大小 + 加密 + 页数 | ✅ `except Exception` | `ParsedDocument(failed)` |
| WordParser | ✅ OSError + 大小 + DOC 拒绝 | ✅ `except Exception` | `ParsedDocument(failed)` |
| TextParser | ✅ OSError + 大小 + 空内容 | ❌ **缺失** | `ParsedDocument(failed)` |
| CompositeDocumentParser | ❌ 无 | ❌ 无 | `raise ValueError` |

**结论**: 同一 `DocumentParserPort` 协议下存在三种不同的错误处理策略，调用方（Service）无法统一处理。建议 CompositeDocumentParser 捕获未知 MIME 并返回 `ParsedDocument(failed)`，与具体解析器保持一致。

### 安全脱敏层级

```
L1: 解析器层 → 返回脱敏消息（✅ PDF/Word 已实现，⚠️ TXT 缺失）
L2: Service 层 → str(e) 再次暴露（❌ F41/F58）
L3: 日志层 → logger.exception 含完整 traceback（✅ 正确，仅日志不对外）
```

**结论**: L1→L2 之间存在安全防护断层。解析器返回的脱敏消息已在 `ParsedDocument.error_message` 中，但 Service 层 `except` 分支用 `str(e)` 覆盖了脱敏结果。

---

## 正面发现

1. **PDF/Word 异常脱敏设计一致**: 两个解析器均使用 `logger.exception` + 通用用户消息模式
2. **TXT OSError 处理精确**: L61 仅捕获 `OSError` 而非宽泛 `Exception`，与 PDF L57/Word L60 一致
3. **`_download_to_temp` 错误恢复**: L165-172 except 块清理临时文件后再 `raise`，资源泄漏防护正确
4. **后缀白名单校验**: `_ALLOWED_TEMP_SUFFIXES` frozenset 防御路径遍历/恶意后缀注入
5. **`os.fchmod` 使用**: L155 使用 fd 级权限设置消除 TOCTOU 窗口（设计意图正确，仅 try 块位置需调整）
6. **`asyncio.to_thread` 使用**: Service L98 正确将 CPU 密集解析卸载到线程池

---

## 自反思评审结论

3 个 P0 修复方案初评：

- **F39 (fchmod 在 try 前)**: 修复方案为将 `os.fchmod` 移入 try 块，并在 except 分支确保 tmp.close() + os.unlink。初评 **优秀** — 修复明确、影响范围小、无副作用。

- **F40 (TXT 缺失 except Exception)**: 修复方案为在 L82-101 解析主逻辑外包裹 `except Exception: logger.exception + return ParsedDocument(failed)`，与 PDF/Word 对齐。初评 **良好** — 需注意 `_detect_and_decode` 中 `UnicodeDecodeError` 已被内层捕获，外层 Exception 仅兜底意外错误。

- **F41 (Service str(e) 安全泄漏)**: 修复方案为在 Service except 分支使用通用消息 + `repr(e)` 仅记录日志。初评 **优秀** — 修复明确、安全收益高、无副作用。需注意与解析器返回的 `ParsedDocument.error_message` 路径区分（解析器已脱敏的消息可安全使用）。

**按规则"非优秀禁止改动代码"，本轮仅 F39/F41 可执行代码修改，F40 需改进方案后重新评审。**
