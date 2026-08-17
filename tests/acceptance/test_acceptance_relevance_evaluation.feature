# language: zh-CN
功能: 检索相关性评估（LLM-as-a-Judge）

  作为质量工程师
  我希望系统评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性 < 0.6 标注"数据不足"
  以便防止基于不足数据生成幻觉内容，确保摘要生成质量

  背景:
    假如 RelevanceEvaluationPort 端口契约已定义
    并且 相关性评估服务已初始化
    并且 LLMClientPort Mock 已就绪

  # =============================================================================
  # AC-1 多维评估 Schema 定义
  # =============================================================================
  场景: AC-1 - RelevanceEvaluation Schema 定义
    当 定义 RelevanceEvaluation Schema
    那么 RelevanceEvaluation 是 Pydantic BaseModel 子类
    并且 包含 context_relevance completeness timeliness 维度字段
    并且 包含 context_relevance_reason completeness_reason timeliness_reason 理由字段
    并且 包含 overall_score 综合评分字段（@computed_field 自动计算）
    并且 包含 should_block 阻断标记字段（@computed_field 自动计算）
    并且 包含 block_reason 阻断理由字段（should_block=True 时必填）
    并且 overall_score 为 (context_relevance + completeness + timeliness) / 3.0
    并且 should_block 为 overall_score < 0.6
    并且 各维度 score 范围约束在 0-1 之间

  场景: AC-1 - RuleBasedEvaluation Schema 定义
    当 定义 RuleBasedEvaluation Schema
    那么 RuleBasedEvaluation 是 Pydantic BaseModel 子类
    并且 包含 has_valid_results min_score max_score avg_score result_count quick_block 字段
    并且 空结果时 has_valid_results=False 且 min_score=max_score=avg_score=0.0
    并且 空结果时 quick_block=True

  # =============================================================================
  # AC-2 检索相关性评估端口契约
  # =============================================================================
  场景: AC-2 - RelevanceEvaluationPort 协议定义
    当 定义 RelevanceEvaluationPort 协议
    那么 RelevanceEvaluationPort 包含 evaluate 方法
    并且 evaluate 接受 query_text search_results config 参数
    并且 RelevanceEvaluationPort 包含 quick_rule_check 方法
    并且 quick_rule_check 接受 query_text search_results 参数
    并且 端口在 composition_root.py 中注册为 relevance_evaluation_service

  # =============================================================================
  # AC-3 检索相关性评估异常体系
  # =============================================================================
  场景: AC-3 - LLM 评估调用失败抛出领域异常
    当 LLM 评估调用返回错误
    那么 系统抛出 RelevanceEvaluationError
    并且 异常 code 为 EXCEPTION_360
    并且 异常 context 包含 query_text 和 result_count

  场景: AC-3 - 检索结果不足阻断抛出领域异常
    当 系统检查到检索结果综合评分 < 0.6
    那么 系统抛出 RelevanceEvaluationBlockedError
    并且 异常 code 为 EXCEPTION_361
    并且 异常 context 包含 overall_score 和 block_reason

  # =============================================================================
  # AC-4 检索相关性评估应用服务
  # =============================================================================
  场景: AC-4 - 相关性评估成功
    当 以有效查询调用相关性评估
    那么 系统先执行 quick_rule_check 规则预检
    并且 系统调用 LLMClientPort.structured_generate 方法
    并且 返回 RelevanceEvaluationResult 实例
    并且 结果包含各维度分数和综合评分

  场景: AC-4 - 空检索结果直接阻断
    当 检索结果为空时调用相关性评估
    那么 系统不调用 LLM
    并且 返回 should_block=True 的阻断结果
    并且 block_reason 为"数据不足"

  场景: AC-4 - LLM 调用失败抛出领域异常
    当 LLM 评估调用返回错误
    那么 系统抛出 RelevanceEvaluationError
    并且 异常 code 为 EXCEPTION_360

  # =============================================================================
  # AC-6 与摘要生成服务的集成
  # =============================================================================
  场景: AC-6 - 评估守卫阻断摘要生成
    当 检索结果综合评分 < 0.6
    那么 摘要生成服务不调用 LLM 生成
    并且 返回"数据不足"的阻断响应

  # =============================================================================
  # AC-7 检索相关性评估 API 端点
  # =============================================================================
  场景: AC-7 - 通过 API 请求相关性评估
    当 通过 POST /api/v1/search/evaluate 请求相关性评估
    那么 返回 200 状态码
    并且 响应体包含 overall_score context_relevance completeness timeliness 字段
    并且 响应体包含 should_block 和 block_reason 字段
