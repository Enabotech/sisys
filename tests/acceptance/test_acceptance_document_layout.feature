# language: zh-CN
功能: 文档版面信息保留（DocLayNet 标准）

  作为分析师
  我希望系统保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式
  以便支持高保真溯源至原始文档坐标点，为 Epic 3 Story 3.8 Bounding Box 级溯源提供数据基础

  背景:
    假如 版面检测环境已就绪

  # =========================================================================
  # AC-1: BoundingBoxResult 值对象与 LayoutDetector 端口
  # =========================================================================

  场景: BoundingBoxResult 值对象创建与序列化
    假如 一个有效的 DocLayNet 版面检测结果
    那么 BoundingBoxResult 包含正确的 label 和 confidence
    并且 BoundingBoxResult.to_dict() 输出完整字典
    并且 BoundingBoxResult 为不可变对象

  场景: LayoutDetector 端口协议合规
    假如 LayoutDetector Protocol 已定义
    那么 端口包含 detect 方法签名
    并且 端口是 runtime_checkable 的

  # =========================================================================
  # AC-2: ONNX 版面检测实现
  # =========================================================================

  场景: OnnxLayoutDetector 检测单页版面元素
    假如 一个模拟的 ONNX 推理会话返回单元素检测结果
    当 调用 detect 方法处理页面图像
    那么 返回包含 1 个 BoundingBoxResult 的列表
    并且 结果的 label 为 DocLayNet 标准类别
    并且 坐标格式为 xywh（x/y/width/height）

  场景: OnnxLayoutDetector 模型文件缺失时抛出 FileNotFoundError
    假如 ONNX 模型文件路径不存在
    当 初始化 OnnxLayoutDetector
    那么 抛出 FileNotFoundError 异常

  场景: OnnxLayoutDetector 空图像返回空列表
    假如 一个模拟的 ONNX 推理会话返回空结果
    当 调用 detect 方法处理页面图像
    那么 返回空列表

  # =========================================================================
  # AC-3: 解析管线集成
  # =========================================================================

  场景: PDF 解析后元素 bbox 字段不为 null
    假如 版面检测器已注入到文档解析服务
    并且 一个包含文本内容的 PDF 文件
    当 系统解析并检测该 PDF 文件版面
    那么 匹配成功的 ParsedElement 的 bbox 不为 null
    并且 bbox 包含完整的 5 个字段（x/y/width/height/page）

  场景: 非 PDF 格式的 bbox 保持 null
    假如 版面检测器已注入到文档解析服务
    并且 一个 TXT 文本文件
    当 系统解析该 TXT 文件
    那么 所有 ParsedElement 的 bbox 为 null

  场景: layout_detector 未注入时优雅降级
    假如 版面检测器未注入到文档解析服务
    并且 一个包含文本内容的 PDF 文件
    当 系统解析该 PDF 文件
    那么 所有 ParsedElement 的 bbox 为 null
    并且 解析状态为 completed

  # =========================================================================
  # AC-4: Composition Root 注册与版本升级
  # =========================================================================

  场景: layout_detector 端口已注册到 Composition Root
    那么 layout_detector 端口版本为 v1.0.0
    并且 layout_detector 生命周期为 SINGLETON

  场景: pdf_page_renderer 端口已注册到 Composition Root
    那么 pdf_page_renderer 端口版本为 v1.0.0
    并且 pdf_page_renderer 生命周期为 SCOPED

  # =========================================================================
  # AC-5: Bounding Box 级溯源数据可用性
  # =========================================================================

  场景: ParsedElement.to_dict() 输出包含完整 bbox 数据
    假如 一个已填充 bbox 的 ParsedElement
    那么 to_dict() 输出 bbox 为完整字典
    并且 bbox 字典包含 x/y/width/height/page 五个字段
    并且 metadata 包含 layout_confidence 字段

  场景: ParsedTable.to_dict() 输出包含完整 bbox 数据
    假如 一个已填充 bbox 的 ParsedTable
    那么 to_dict() 输出 bbox 为完整字典

  # =========================================================================
  # 开发结束验收：src 完成清单确认
  # =========================================================================

  场景: src 目录完成清单逐项确认
    那么 BoundingBoxResult 值对象存在于 domain 层
    并且 LayoutDetector 端口定义存在于 domain 层
    并且 PdfPageRendererPort 端口定义存在于 domain 层
    并且 OnnxLayoutDetector 实现存在于 infrastructure 层
    并且 PdfPageRenderer 实现存在于 infrastructure 层
    并且 layout_matching 领域服务存在于 domain 层
    并且 layout_detector 端口已注册到 Composition Root
    并且 pdf_page_renderer 端口已注册到 Composition Root

  场景: tests 目录完成清单逐项确认
    那么 BoundingBoxResult 单元测试文件存在
    并且 LayoutDetector 端口测试文件存在
    并且 OnnxLayoutDetector 单元测试文件存在
    并且 PdfPageRenderer 单元测试文件存在
    并且 layout_matching 单元测试文件存在
    并且 架构约束测试文件存在
    并且 集成测试文件存在
    并且 端口契约测试文件存在
    并且 验收测试场景文件存在
