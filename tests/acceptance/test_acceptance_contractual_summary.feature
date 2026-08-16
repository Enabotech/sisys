# language: zh-CN
功能: 契约化结构化摘要生成

  作为分析师
  我希望系统生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema
  以便摘要质量可控且可验证，满足不同视角的战略分析需求

  背景:
    假如 SummaryGenerationPort 端口契约已定义
    并且 摘要生成服务已初始化
    并且 LLMClientPort Mock 已就绪

  # =============================================================================
  # AC-1 摘要 Schema 契约定义
  # =============================================================================
  场景: AC-1 - 财务视角摘要 Schema 定义
    当 定义 FinancialSummary Schema
    那么 FinancialSummary 是 Pydantic BaseModel 子类
    并且 包含 summary_text key_points confidence_score 固有字段
    并且 包含 revenue_trend profit_analysis risk_factors market_position 视角特有字段
    并且 confidence_score 范围约束在 0-1 之间

  场景: AC-1 - 市场视角摘要 Schema 定义
    当 定义 MarketSummary Schema
    那么 MarketSummary 是 Pydantic BaseModel 子类
    并且 包含 summary_text key_points confidence_score 固有字段
    并且 包含 market_size competitive_landscape growth_drivers customer_insights 视角特有字段
    并且 confidence_score 范围约束在 0-1 之间

  场景: AC-1 - 技术视角摘要 Schema 定义
    当 定义 TechnicalSummary Schema
    那么 TechnicalSummary 是 Pydantic BaseModel 子类
    并且 包含 summary_text key_points confidence_score 固有字段
    并且 包含 technology_stack innovation_points technical_risks architecture_overview 视角特有字段
    并且 confidence_score 范围约束在 0-1 之间

  # =============================================================================
  # AC-2 摘要生成服务端口契约
  # =============================================================================
  场景: AC-2 - SummaryGenerationPort 协议定义
    当 定义 SummaryGenerationPort 协议
    那么 SummaryGenerationPort 包含 generate_summary 方法
    并且 generate_summary 接受 query_text search_results perspective config tenant_id cross_document 参数
    并且 端口在 composition_root.py 中注册为 summary_generation_service

  # =============================================================================
  # AC-3 摘要生成异常体系
  # =============================================================================
  场景: AC-3 - 不支持的视角抛出领域异常
    当 使用不支持的视角调用摘要生成
    那么 系统抛出 SummaryPerspectiveNotSupportedError
    并且 异常 code 为 EXCEPTION_291

  # =============================================================================
  # AC-4 摘要生成应用服务
  # =============================================================================
  场景: AC-4 - 财务视角摘要生成成功
    当 以 financial 视角生成摘要
    那么 系统调用 LLMClientPort.structured_generate 方法
    并且 返回 FinancialSummary Schema 实例
    并且 结果通过 Pydantic Schema 验证

  场景: AC-4 - 市场视角摘要生成成功
    当 以 market 视角生成摘要
    那么 系统调用 LLMClientPort.structured_generate 方法
    并且 返回 MarketSummary Schema 实例
    并且 结果通过 Pydantic Schema 验证

  场景: AC-4 - 技术视角摘要生成成功
    当 以 technical 视角生成摘要
    那么 系统调用 LLMClientPort.structured_generate 方法
    并且 返回 TechnicalSummary Schema 实例
    并且 结果通过 Pydantic Schema 验证

  场景: AC-4 - LLM 调用失败时抛出领域异常
    当 LLM 调用返回错误
    那么 系统抛出 SummaryGenerationError
    并且 异常 code 为 EXCEPTION_290

  # =============================================================================
  # AC-6 L2 文档摘要检索
  # =============================================================================
  场景: AC-6 - L2 文档摘要存储与检索
    当 单文档摘要已生成并存储
    那么 摘要向量写入 document_summaries collection
    并且 LayeredRetrievalService.search_top_down(target_level="L2") 返回摘要结果
    并且 结果 payload 包含 index_level 为 L2

  # =============================================================================
  # AC-7 跨文档摘要
  # =============================================================================
  场景: AC-7a - 跨文档摘要生成
    当 以 cross_document=True 模式生成摘要
    那么 系统先检索 L2 摘要
    并且 聚合 Top-K 摘要结果作为上下文
    并且 生成跨文档摘要并写入 cross_document_summaries collection
    并且 结果 payload 包含 index_level 为 L1

  场景: AC-7b - L1 跨文档摘要检索
    当 跨文档摘要已生成并存储
    那么 LayeredRetrievalService.search_top_down(target_level="L1") 返回跨文档摘要结果

  # =============================================================================
  # AC-8 摘要 API 端点
  # =============================================================================
  场景: AC-8 - 通过 API 请求摘要生成
    当 通过 POST /api/v1/search/summary 请求摘要生成
    那么 返回 200 状态码
    并且 响应体包含 summary query_text perspective confidence_score source_documents 字段
