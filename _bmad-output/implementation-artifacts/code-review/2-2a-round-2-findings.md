# Story 2-2a 第 2 轮代码审查报告

**日期**: 2026-06-02
**审查模式**: 3 Agent 并行（Security + Performance/Concurrency + Architecture Compliance）
**审查范围**: Story 2-2a 文档解析全量生产代码

---

## 新增 P0 发现（3 项，第 1 轮未覆盖）

### F11: python-docx XXE 外部实体注入 (CWE-611)

- **来源**: Security Specialist
- **文件**: `src/infrastructure/external_services/document_parsing/word_parser.py:83-84`
- **攻击场景**: 攻击者上传特制 DOCX，内嵌恶意 DTD 引用读取 /etc/passwd 或请求云元数据端点 (169.254.169.254)。python-docx < 1.1.2 默认不禁用外部实体解析。
- **修复建议**: 升级 python-docx >= 1.1.2，或使用 defusedxml 包装解析

### F12: async 事件循环中同步文件写入阻塞

- **来源**: Performance Specialist
- **文件**: `src/application/services/document_parsing_service.py:159`
- **描述**: `tmp.write(chunk)` 在 async 循环中同步执行，高并发时阻塞事件循环
- **修复建议**: 使用 `loop.run_in_executor(None, tmp.write, chunk)` 或 aiofiles

### F13: 解析操作无 asyncio 超时保护

- **来源**: Performance Specialist
- **文件**: `src/application/services/document_parsing_service.py:55-128`
- **描述**: parse_document() 无超时机制，畸形文件可永久挂起协程
- **修复建议**: 用 asyncio.wait_for() 包裹解析调用，timeout=300s

---

## P1 发现（10 项，含第 1 轮遗留）

| ID | 来源 | 描述 | 文件 |
|----|------|------|------|
| F4 | R1 Blind | PDF except Exception 过宽 | pdf_parser.py |
| F5 | R1 Edge | 解压炸弹绕过文件大小检查 | pdf_parser.py:79 |
| F6 | R1 Edge | MIME 类型注入 | composite_parser.py:44 |
| F7 | R1 Auditor | TXT >10MB 硬拒绝 | text_parser.py:48-58 |
| F8 | R1 Edge | parse_error 暴露内部信息 | document_parsing_service.py:126 |
| F14 | R2 Security | DOCX 解压炸弹 (50MB→数GB) | word_parser.py:58-78 |
| F15 | R2 Security | storage_object_key 路径遍历 | document_parsing_service.py:77 |
| F16 | R2 Security | 依赖版本未锁定 (CVE 暴露) | pyproject.toml |
| F17 | R2 Perf | PDF/Parser 全量内存加载 | pdf_parser.py:78-79 |
| F18 | R2 Perf | TXT 编码检测 3 次全量 decode | text_parser.py:104-116 |
| F19 | R2 Arch | DocumentParsingService 缺端口接口 | document_parsing_service.py:31 |
| F20 | R2 Arch | Domain 实体状态被应用层直接修改 | document_parsing_service.py:79-110 |

---

## P2 发现（15 项）

详见各 Agent 详细报告。涵盖：to_dict() 内存翻倍、CompositeParser ValueError 设计、编码回退顺序、BoundingBox 索引不一致、DI 解析器注册粒度、临时文件双重清理等。

---

## 架构合规总结

| 维度 | 状态 |
|------|------|
| 依赖方向 (domain→app→infra) | ✅ 通过 |
| Protocol 契约 (显式继承) | ✅ 通过 |
| 值对象纯度 (frozen, 无外部依赖) | ✅ 通过 |
| OCP 合规 (parsers dict 注入) | ✅ 通过 |
| 关注点分离 (编排 vs 解析) | ✅ 通过 |
| DI 注册粒度 | ⚠️ P2 改进 |
| 领域封装 (实体可变修改) | ⚠️ P1 |
