# Story 2-2a 第 3 轮代码审查报告

**日期**: 2026-06-02
**审查模式**: 3 Agent 并行（Test Quality + Template Compliance + Integration/E2E）
**审查范围**: Story 2-2a 全部测试代码（单元/集成/验收/契约）

---

## P0 发现（6 项）

### 测试质量

| ID | 描述 | 文件 |
|----|------|------|
| F21 | `os.path.getsize` OSError 路径全部 3 个解析器均未覆盖 | test_pdf/word/text_parser.py |
| F22 | PDF MAX_PDF_PAGES (500页) 超限路径未测试 | test_pdf_parser.py |
| F23 | 服务层 parse_status != PENDING 跳过路径未覆盖 | test_document_parsing_service.py |
| F24 | TXT 编码全失败兜底 (errors="replace") 路径未覆盖 | test_text_parser.py |

### 模板合规

| ID | 描述 |
|----|------|
| F25 | 缺失 `test_api_contract_document_parse.py`（模板要求必选项） |
| F26 | AC→测试追溯矩阵缺失（仅个别方法有 AC 引用，大部分无） |

### 集成/E2E

| ID | 描述 |
|----|------|
| F27 | 集成测试不连接真实 PostgreSQL/MinIO/事件总线 |
| F28 | BDD 验收测试 10/20 个 then 步骤为空（纯 pass），验收测试虚设 |

---

## P1 发现（10 项）

| ID | 来源 | 描述 |
|----|------|------|
| F29 | TestQuality | PDF 准确率测试阈值 0.5 与声称的 95% 不符（假绿风险） |
| F30 | TestQuality | GB18030 编码测试仅验证状态未验证文本内容 |
| F31 | TestQuality | 段落分割测试未验证具体内容 |
| F32 | TestQuality | DOC 格式错误消息断言过于宽泛 |
| F33 | Template | test_composite_parser 内嵌端口契约验证（应移入 contracts/） |
| F34 | Template | 测试路径深度超出模板建议格式 |
| F35 | Integration | 上传→解析 E2E 完整流程无覆盖 |
| F36 | Integration | 错误恢复/重试/乐观锁并发无集成测试 |
| F37 | Integration | BDD AC-4/AC-5 场景缺少 Given/When 步骤 |
| F38 | Integration | DOCX 表格提取未验证行数 |

---

## P2 发现（11 项）

涵盖：死代码 `_create_text_pdf`、集成测试名实不匹配、并发测试仅 PDF、样式元数据未验证、缺失 Subtask 标注、部分方法缺文档字符串、mock 风格不一致、契约测试未验证 isinstance、asyncio_mode 配置冲突、文件命名未触发服务标记、事件发布失败恢复未测。

---

## 正面发现

1. 资源清理严谨：所有临时文件 try/finally + os.unlink
2. Mock 隔离优秀：函数级 fixture，无状态泄漏
3. 异常脱敏测试：PDF/Word 有专门的路径泄漏防护测试
4. JSON 序列化验证：所有解析器 to_dict() 均有验证
5. 架构约束测试：依赖方向/Protocol 合规性验证完整
6. 状态转换验证：Service 测试精确验证 IN_PROGRESS→COMPLETED 顺序
7. Fixture 自包含：动态创建测试文件，不依赖外部 fixture

---

## 最紧急修复项（跨轮次 P0 汇总）

经过 3 轮审查，累计发现 **10 个 P0 问题**：

| 轮次 | ID | 描述 | 分类 |
|------|----|------|------|
| R1 | F1 | 空 DOCX 返回 completed（AC-2） | 功能缺陷 |
| R1 | F2 | 编码失败静默降级（AC-3） | 功能缺陷 |
| R1 | F3 | TOCTOU 竞态（双重触发） | 并发安全 |
| R2 | F11 | python-docx XXE 注入 (CWE-611) | 安全漏洞 |
| R2 | F12 | async 同步 IO 阻塞事件循环 | 性能缺陷 |
| R2 | F13 | 无 asyncio 超时保护 | 可靠性 |
| R3 | F21 | OSError 路径漏测（3 解析器） | 测试覆盖 |
| R3 | F25 | 缺失 API 契约测试 | 模板合规 |
| R3 | F27 | 集成测试无真实基础设施 | 测试覆盖 |
| R3 | F28 | 10/20 BDD then 步骤为空 | 测试质量 |
