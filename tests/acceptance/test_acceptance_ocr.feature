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