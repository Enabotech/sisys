# Story 2-2a 第 1 轮代码审查报告

**日期**: 2026-06-02
**审查模式**: 3 Agent 并行（Blind Hunter + Edge Case Hunter + Acceptance Auditor）
**审查范围**: Story 2-2a 文档解析全量生产代码

---

## P0 发现（3 项）

### F1: 空 DOCX 返回 completed 而非 failed（违反 AC-2）

- **来源**: Acceptance Auditor
- **文件**: `src/infrastructure/external_services/document_parsing/word_parser.py:115`
- **描述**: WordParser.parse() 对无段落、无表格的 DOCX 文件仍返回 parse_status="completed"
- **AC 引用**: AC-2 "空 DOCX（无内容）返回解析失败"
- **修复方向**: 建议在 DocumentParsingService 层做统一空内容检查（覆盖所有解析器类型），而非仅在 WordParser 内部

### F2: 编码检测失败静默降级而非 failed（违反 AC-3）

- **来源**: Acceptance Auditor + Edge Case Hunter（去重合并）
- **文件**: `src/infrastructure/external_services/document_parsing/text_parser.py:116`
- **描述**: _detect_and_decode() 在所有编码失败后使用 errors="replace" 静默产生损坏文本，仍返回 completed
- **AC 引用**: AC-3 "无扩展名编码错误返回解析失败"
- **修复方向**: 使用自定义异常 `EncodingDetectionError` 替代 tuple 返回，保持方法签名简洁

### F3: parse_document TOCTOU 竞态条件

- **来源**: Edge Case Hunter
- **文件**: `src/application/services/document_parsing_service.py:85-90`
- **描述**: PENDING 状态检查与 IN_PROGRESS save 之间存在竞态窗口，两个并发任务可能同时通过守卫
- **修复方向**: 建议仓库层增加原子 CAS 操作 `update_status_if()`，配合 success/except 双路径 re-read 防护

---

## P1 发现（6 项）

| ID | 描述 | 文件 |
|----|------|------|
| F4 | PDF except Exception 过宽吞噬编程错误 | pdf_parser.py |
| F5 | 解压炸弹可绕过文件大小检查 | pdf_parser.py:79 |
| F6 | MIME 类型注入到错误消息无消毒 | composite_parser.py:44 |
| F7 | TXT >10MB 硬拒绝而非分块（违反 AC-3） | text_parser.py:48-58 |
| F8 | parse_error 暴露内部路径/异常详情 | document_parsing_service.py:126 |
| F9 | Word parser import error 导致误导性错误消息 | word_parser.py:81 |

---

## P2 发现（10 项）

详见 Agent 详细报告。涵盖：数值域校验、资源释放时机、文件头长度校验、临时文件 flush、后缀消毒、解析器输入校验、BoundingBox 索引一致性等。

---

## 自反思评审结论

3 个 P0 修复方案初评均为"需改进"：
- F1/F2: 变量名错误（`document_id` vs `doc_id`），F1 应提升到 service 层
- F3: `find()` 参数类型错误，仅覆盖 except 分支未覆盖 success 分支

**按规则"非优秀禁止改动代码"，本轮不执行代码修改。**
