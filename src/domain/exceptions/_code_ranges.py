"""异常编码子域范围约束表（CI 专用，非运行时）。

本文件定义所有异常子域的编码范围边界，作为 test_code_ranges.py 的唯一权威输入。
新增异常类时必须按子域归属选取编码；如需新增子域，必须同时更新此表。

编码规则：
- 每个子域分配一个连续的数字范围
- 子类编码必须属于父类编码所在的子域范围
- 禁止使用基类占位符编码（000, 1XX, 2XX, 3XX）作为具体异常类的 code
- 编码一旦分配即成为 API 契约，不可修改或删除（只追加）
"""

from __future__ import annotations

# 子域编码范围约束表
# key: 子域名, value: (起始编码, 结束编码)
# 编码为整数（不含 EXCEPTION_ 前缀），范围闭区间 [start, end]
CODE_RANGES: dict[str, tuple[int, int]] = {
    # 系统级异常（1XX）
    "system": (101, 109),
    # 业务级基类（201-209）
    "business": (201, 209),
    # 存储子域（211-219）
    "storage": (211, 219),
    # 角色子域（221-229）
    "role": (221, 229),
    # 服务子域（231-239）
    "service": (231, 239),
    # 权限子域（241）
    "permission": (241, 241),
    # 实体子域（242-249）—— EntityValidationError/EntityStateTransitionError/EntityBusinessRuleError
    "entity": (242, 249),
    # 事件子域（251-259）
    "event": (251, 259),
    # 跨境传输子域（261-269）
    "transfer": (261, 269),
    # 词典管理子域（270-279）
    "dictionary": (270, 279),
    # 档案子域（282-289）
    "archive": (282, 289),
    # 分层检索子域（280-281）
    "retrieval": (280, 281),
    # 摘要生成子域（290-299）
    "summary": (290, 299),
    # 外部服务（3XX）
    "external": (301, 399),
    # 嵌入服务（306-310）
    "embedding": (306, 310),
    # 沙箱（311-319）
    "sandbox": (311, 319),
    # OCR 子域（320-329）
    "ocr": (320, 329),
    # LLM 子域（330-339）
    "llm": (330, 339),
    # 实体抽取子域（340-349）
    "entity_extraction": (340, 349),
    # 重排序子域（350-359）
    "reranker": (350, 359),
    # 检索相关性评估子域（360-369）
    "relevance": (360, 369),
    # 溯源子域（370-379）
    "traceability": (370, 379),
    # 工具子域（380-389）—— Story 4.1/4.1a 累计注册 9 个异常:
    # EXCEPTION_380 ToolNotFoundError (Story 4.1)
    # EXCEPTION_381 ToolAlreadyExistsError (Story 4.1)
    # EXCEPTION_382 ToolExecutionFailedError (Story 4.1a)
    # EXCEPTION_383 ToolExecutionRetryExhaustedError (Story 4.1a)
    # EXCEPTION_385 ToolExecutionTimeoutError (Story 4.1a)
    # EXCEPTION_386 EvidenceValidationFailedError (Story 4.1a)
    # EXCEPTION_387 SkillNotFoundError (Story 4.1a, Skill 子域归属 tool)
    # EXCEPTION_388 SkillLoadError (Story 4.1a, Skill 子域归属 tool)
    # EXCEPTION_389 ToolResultValidationError (Story 4.1a)
    # EXCEPTION_384 保留未占用；ToolExecutionState 迁移守卫复用 EXCEPTION_243 (EntityStateTransitionError)
    "tool": (380, 389),
    # 工具链子域（390-399）—— Story 4.2 注册 5 个异常 + Story 4.3 注册 4 个异常:
    # EXCEPTION_390 ToolChainCycleDetectedError (Story 4.2)
    # EXCEPTION_391 ToolChainDuplicateNodeError (Story 4.2)
    # EXCEPTION_392 ToolChainNodeNotFoundError (Story 4.2)
    # EXCEPTION_393 ToolChainExecutionFailedError (Story 4.2)
    # EXCEPTION_394 ToolChainNotFoundError (Story 4.2,Round 1 审查修订新增)
    # EXCEPTION_395 ToolInputSchemaValidationError (Story 4.3)
    # EXCEPTION_396 ToolOutputSchemaValidationError (Story 4.3)
    # EXCEPTION_397 ToolSchemaCompatibilityError (Story 4.3)
    # EXCEPTION_398 ToolSchemaMissingError (Story 4.3)
    # EXCEPTION_399 ValidationFeedbackRetryExhaustedError (Story 4.7——预留码位兑现)
    # 子域物理嵌套于 external (301-399)，但语义独立；390-399 已全部分配
    "toolchain": (390, 399),
    # 数据源子域（410-419）—— Story 4.1b 注册 4 个异常:
    # EXCEPTION_410 DataSourceError (Story 4.1b, 数据源通用错误基类)
    # EXCEPTION_411 DataSourceUnavailableError (Story 4.1b, 数据源不可用/重试耗尽)
    # EXCEPTION_412 DataSourceRateLimitError (Story 4.1b, 数据源 429 限流)
    # EXCEPTION_413 DataSourceResponseError (Story 4.1b, 响应解析失败，不可重试)
    # 子域语义归属 external（ExternalException 子类），物理段独立于 301-399（external 已满）
    "data_source": (410, 419),
    # 红蓝辩论子域（420-429）—— Story 4.5 注册 3 个异常:
    # EXCEPTION_420 DebateGenerationError (Story 4.5, 红/蓝视角 LLM 生成失败)
    # EXCEPTION_421 DebateSynthesisError (Story 4.5, 风险视图合成 LLM 调用失败)
    # EXCEPTION_422 DebateLowDivergenceError (Story 4.5, 红蓝重叠率 ≥0.95 分化不足)
    # 420/421 语义归属 external（ExternalException 子类）、422 语义归属 business（BusinessException 子类），
    # 物理段独立于 301-399 与 201-209（两段均无整段空位，遵循 data_source 410-419 独立段先例）
    # EXCEPTION_423-429 预留 V1 多轮辩论（轮次超限/裁决置信度不足/辩论过热等，Story 10.6）
    "debate": (420, 429),
    # 工具版本子域（430-439）—— Story 4.6 注册 4 个异常（灰度发布与回滚）:
    # EXCEPTION_430 ToolVersionNotFoundError (Story 4.6, 版本不存在/回滚目标无记录)
    # EXCEPTION_431 ToolVersionAlreadyExistsError (Story 4.6, (tool_id,version) 重复注册)
    # EXCEPTION_432 ToolVersionTrafficWeightError (Story 4.6, 权重非法/canary_only 直接全量/并存冲突族)
    # EXCEPTION_433 ToolVersionRollbackError (Story 4.6, 无可回滚稳定历史/目标非可回滚态)
    # 物理段独立（tool 380-389 仅剩 384 保留位、toolchain 390-399 已被 4.7 预占 399——两旧段均不可用，
    # 遵循 data_source 410-419 / debate 420-429 独立段先例）
    # EXCEPTION_434-439 暂不分配，保持空段预留
    "tool_version": (430, 439),
    # Agent 子域（440-449）—— Story 5.1 注册 2 个 + 5.2 追加 2 个 + 5.3 追加 2 个 + 5.4 追加 2 个 + 5.5 追加 2 个:
    # EXCEPTION_440 AgentConfigError (Story 5.1, 配置文件缺失/YAML 解析失败/必填字段无效/role 不匹配/state_ttl 越界)
    # EXCEPTION_441 AgentRoleNotSupportedError (Story 5.1, MVP 未开放角色实例化请求)
    # EXCEPTION_442 AgentProfileError (Story 5.2, 档案目录缺失/文件缺失/不可读/编码非法/内容空白/超 64KB 上限/VO 字段类型非法)
    # EXCEPTION_443 AgentNotFoundError (Story 5.2, get_by_id 返回 None——键不存在或 TTL 过期后重放旧 agent_id)
    # EXCEPTION_444 AgentWorkflowError (Story 5.3, 工作流阶段执行失败——LLM 调用失败包装/图执行异常收敛，phase 区分锚点)
    # EXCEPTION_445 ChainOfThoughtValidationError (Story 5.3, 思维链完整性校验失败——终局组装后五字段缺一/空值/结构非法)
    # EXCEPTION_446 IsolationLevelNotSupportedError (Story 5.4, 隔离等级不合法——非法枚举值字符串或
    #   合法枚举越 MVP 白名单即 L1 融合态)
    # EXCEPTION_447 IsolationStateNotInitializedError (Story 5.4, 隔离状态缺失——存量 Agent 无隔离键/
    #   未初始化查询/fail-fast 残留态)
    # EXCEPTION_448 IsolationAccessViolationError (Story 5.5, 跨 Agent 私有资源访问越权——Prompt/数据面
    #   private+cross 格拦截，context 五字段含 reason 等级名)
    # EXCEPTION_449 IsolationOperationForbiddenError (Story 5.5, 当前隔离等级策略禁止的操作——白名单外工具
    #   [tool_not_in_allowlist:{name}] 或 READ_ONLY/RESTRICTED_WRITE 共享面写 [data_isolation:{mode}] 双形态)
    # 445 的 missing_fields 上下文为同码多因区分锚点（异常契约三层校验次序②的改写目标）
    # 440/442/444/445 语义归属 system（SystemException 子类——配置/档案资产/工作流执行属系统资源）、
    # 441/443/446/447/448/449 语义归属 business（BusinessException 子类——阶段性能力范围限制/请求资源不存在/
    # 不支持的隔离取值/隔离状态资源缺失/跨主体越权/等级策略禁止操作），物理段独立（遵循独立段先例）
    # agent 段 440-449 至此全分配（Story 5.5 预留位核销）
    "agent": (440, 449),
    # 评估子域（450-459）—— Story 5.8 注册 1 个 + Story 5.9 取用 1 个 + Story 5.10 取用 1 个
    # （agent 段 440-449 已满后四代开段先例第五段：data_source 410/debate 420/tool_version
    # 430/agent 440 同款「前段满/语义独立 → 开独立段」）:
    # EXCEPTION_450 AgentEvaluationError (Story 5.8, 评估管线执行失败——幻觉检测
    #   LLM 调用包装/Schema 实例守卫/评估模型路由匹配失败收敛面)
    # EXCEPTION_451 DriftDetectionError (Story 5.9, CUSUM 漂移检测管线执行失败——
    #   检测状态机异常防御面；三层降级网第三层 450/332/451)
    # EXCEPTION_452 EvaluationHistoryError (Story 5.10, 评估历史持久化管线执行失败——
    #   record save 失败/restore 结构不完整防御面；record 块专属内层独立降级网
    #   不进共享 catch 三元组；453-459 预留后续评估域异常)
    # 450/451/452 语义归属 system（SystemException 子类——评估/漂移检测/历史持久化
    # 均系统侧可观测行为，AgentWorkflowError[444] 同族论证「工作流执行属系统侧行为」）
    "evaluation": (450, 459),
    # SAP 协议子域（460-469）—— Story 5.11 注册 3 个
    # （evaluation 段 450-459 之后五代开段先例第六段：data_source 410/debate 420/
    #  tool_version 430/agent 440/evaluation 450 同款「前段满/语义独立 → 开独立段」
    #  ——SAP 协议域与事件总线/评估域语义分立，MessageBusError 与 SAP 分立先例同款）:
    # EXCEPTION_460 SAPTimeoutError (Story 5.11, 请求-响应关联等待超时——
    #   wait_for_response 等满 timeout 无 resolve/未挂起条目超时路径；ToolExecutionTimeoutError
    #   385「business+超时+504」三合一先例)
    # EXCEPTION_461 SAPBusStateError (Story 5.11, 总线状态违规——未注册接收方/非 UUID 标识/
    #   BROADCAST 组合双向违规/关闭后操作；reason 闭集五成员)
    # EXCEPTION_462 SAPBlackboardWriteError (Story 5.11, 公共黑板写入失败——post 返 0 检测点
    #   fail-loud[OD-7]；与 StorageError 103 系统资源族同族但不复用[子域分立]；463-469 预留 sap 域)
    # 460 语义归属 business（协议交互超时是调用方可处理结果）；461/462 语义归属 system
    # （SystemException 子类——协议契约违规/基础设施写失败）
    "sap": (460, 469),
    # 财务子域（470-479）—— Story 5.12 注册 1 个
    # （sap 段 460-469 之后六代开段先例第七段：data_source 410/debate 420/tool_version
    #  430/agent 440/evaluation 450/sap 460 同款「前段满/语义独立 → 开独立段」
    #  ——财务估值计算域与 SAP 协议域语义分立，子域分立先例同款）:
    # EXCEPTION_470 FinancialCalculationError (Story 5.12, 财务计算失败——DCF 数值
    #   求解失败双路径[V1 实际触发：bracket 端点同号等病态输入 + NPV 为零 weight
    #   分母失效(CR1-1 补) 均 fail-loud]；语义挂
    #   BusinessRuleViolationError 422 族「业务约束不可满足」；471-479 预留 financial 域)
    # 470 语义归属 business（数值求解失败是调用方可处理结果——调整输入/换方法重试）
    "financial": (470, 479),
    # 兜底（999）——未预期异常的编码，独立于所有子域
    "fallback": (999, 999),
}

# 基类占位符编码——具体异常类禁止使用
# 这些编码仅用于抽象基类（SystemException/BusinessException/ExternalException），
# 不应被任何可直接实例化的异常类使用
PLACEHOLDER_CODES: set[int] = {0, 1, 2, 3}  # EXCEPTION_000, _1XX, _2XX, _3XX


# 异常类 → 子域名映射（通过模块路径推断）
# 格式: {完整类名: 子域名}
# 用于 test_code_ranges.py 的继承链编码一致性校验
_CLASS_TO_SUBDOMAIN: dict[str, str] = {
    # system_exceptions.py
    "ConfigurationError": "system",
    "NetworkError": "system",
    "StorageError": "system",
    "MessageBusError": "system",
    # business_exceptions.py
    "ValidationError": "business",
    "NotFoundError": "business",
    "ConflictError": "business",
    "PermissionDeniedError": "business",
    "AuthenticationError": "business",
    "InvalidStateError": "business",
    "BusinessRuleViolationError": "business",
    "InvalidStateTransitionError": "business",
    "EntityValidationError": "entity",
    "EntityStateTransitionError": "entity",
    "EntityBusinessRuleError": "entity",
    # storage_exceptions.py
    "MinIOConnectionError": "system",
    "MemoryNotFoundError": "storage",
    "BucketNotFoundError": "storage",
    "MemoryVersionConflictError": "storage",
    "BucketNameValidationError": "storage",
    "MemoryAccessDeniedError": "storage",
    "DocumentVersionConflictError": "storage",
    "MetadataValidationError": "storage",
    "ChunkingError": "storage",
    "UploadSessionExpiredError": "storage",
    # role_exceptions.py
    "RoleNotFoundError": "role",
    "RoleAlreadyExistsError": "role",
    "CannotDeleteRoleWithUsersError": "role",
    "CannotDeleteSystemRoleError": "role",
    # service_exceptions.py
    "AuditError": "system",
    "PasswordValidationError": "service",  # pragma: allowlist secret
    "ComplianceLockError": "service",
    # permission_exceptions.py
    "InsufficientTokenError": "permission",
    # event_exceptions.py
    "EventPublishError": "system",
    "VersionError": "event",
    # transfer_exceptions.py
    "TransferNotFoundError": "transfer",
    "TransferNotApprovedError": "transfer",
    # external_exceptions.py
    "ThirdPartyError": "external",
    "TimeoutError": "external",
    "ServiceUnavailableError": "external",
    "UnknownError": "fallback",
    # embedding_exceptions.py
    "EmbeddingAPIError": "embedding",
    "EmbeddingResponseError": "embedding",
    "EmbeddingModelError": "embedding",
    "ModelInferenceError": "embedding",
    "ConcurrencyOverloadError": "embedding",
    # sandbox_exceptions.py
    "SandboxError": "sandbox",
    "ContainerStartError": "sandbox",
    "ContainerStopError": "sandbox",
    "ExecutionError": "sandbox",
    # Story 4.4 新增 5 个沙箱异常
    "SandboxImagePullError": "sandbox",
    "SandboxTimeoutError": "sandbox",
    "SandboxResourceLimitExceededError": "sandbox",
    "SandboxQuotaExceededError": "sandbox",
    "SandboxConfigurationError": "sandbox",
    # ocr_exceptions.py
    "OCRConnectionError": "ocr",
    "OCRProcessingError": "ocr",
    # llm_exceptions.py
    "LLMAPIError": "llm",
    "LLMResponseError": "llm",
    "LLMConfigError": "llm",
    # entity_extraction_exceptions.py
    "EntityExtractionError": "entity_extraction",
    # reranker_exceptions.py
    "RerankError": "reranker",
    # relevance_exceptions.py
    "RelevanceEvaluationError": "relevance",
    "RelevanceEvaluationBlockedError": "relevance",
    # hybrid_search_exceptions.py
    "HybridSearchError": "business",
    # dictionary_exceptions.py
    "DictionaryNotFoundError": "dictionary",
    "DictionaryEntryConflictError": "dictionary",
    "DictionaryVersionConflictError": "dictionary",
    # archive_exceptions.py
    "ArchiveNotFoundError": "archive",
    "ArchiveConflictError": "archive",
    "ArchiveStorageError": "archive",
    "ValidityPeriodConflictError": "archive",
    # layered_retrieval_exceptions.py
    "LayeredRetrievalError": "retrieval",
    "LevelTransitionError": "retrieval",
    # summary_exceptions.py
    "SummaryGenerationError": "summary",
    "SummaryPerspectiveNotSupportedError": "summary",
    # traceability_exceptions.py
    "TraceabilityError": "traceability",
    "TraceabilityNotFoundError": "traceability",
    # tool_exceptions.py (Story 4.1a 新增 7 个异常)
    "ToolNotFoundError": "tool",
    "ToolAlreadyExistsError": "tool",
    "ToolExecutionFailedError": "tool",
    "ToolExecutionRetryExhaustedError": "tool",
    "ToolExecutionTimeoutError": "tool",
    "EvidenceValidationFailedError": "tool",
    "SkillNotFoundError": "tool",
    "SkillLoadError": "tool",
    "ToolResultValidationError": "tool",
    # tool_chain_exceptions.py (Story 4.2 新增 5 个异常)
    "ToolChainCycleDetectedError": "toolchain",
    "ToolChainDuplicateNodeError": "toolchain",
    "ToolChainNodeNotFoundError": "toolchain",
    "ToolChainExecutionFailedError": "toolchain",
    "ToolChainNotFoundError": "toolchain",
    # tool_schema_exceptions.py (Story 4.3 新增 4 个异常)
    "ToolInputSchemaValidationError": "toolchain",
    "ToolOutputSchemaValidationError": "toolchain",
    "ToolSchemaCompatibilityError": "toolchain",
    "ToolSchemaMissingError": "toolchain",
    # validation_feedback_exceptions.py (Story 4.7 新增 1 个异常——预留码位 399 兑现)
    "ValidationFeedbackRetryExhaustedError": "toolchain",
    # data_source_exceptions.py (Story 4.1b 新增 4 个异常)
    "DataSourceError": "data_source",
    "DataSourceUnavailableError": "data_source",
    "DataSourceRateLimitError": "data_source",
    "DataSourceResponseError": "data_source",
    # debate_exceptions.py (Story 4.5 新增 3 个异常)
    "DebateGenerationError": "debate",
    "DebateSynthesisError": "debate",
    "DebateLowDivergenceError": "debate",
    # tool_version_exceptions.py (Story 4.6 新增 4 个异常)
    "ToolVersionNotFoundError": "tool_version",
    "ToolVersionAlreadyExistsError": "tool_version",
    "ToolVersionTrafficWeightError": "tool_version",
    "ToolVersionRollbackError": "tool_version",
    # agent_exceptions.py (Story 5.1 新增 2 个异常, Story 5.2 追加 2 个, Story 5.3 追加 2 个, Story 5.5 追加 2 个)
    "AgentConfigError": "agent",
    "AgentRoleNotSupportedError": "agent",
    "AgentProfileError": "agent",
    "AgentNotFoundError": "agent",
    "AgentWorkflowError": "agent",
    "ChainOfThoughtValidationError": "agent",
    "IsolationLevelNotSupportedError": "agent",
    "IsolationStateNotInitializedError": "agent",
    "IsolationAccessViolationError": "agent",
    "IsolationOperationForbiddenError": "agent",
    # evaluation_exceptions.py (Story 5.8 新增 1 个 + Story 5.9 追加 1 个 + Story 5.10 追加 1 个异常)
    "AgentEvaluationError": "evaluation",
    "DriftDetectionError": "evaluation",
    "EvaluationHistoryError": "evaluation",
    # sap_exceptions.py (Story 5.11 新增 3 个异常——SAP 协议运行时三码)
    "SAPTimeoutError": "sap",
    "SAPBusStateError": "sap",
    "SAPBlackboardWriteError": "sap",
    # financial_exceptions.py (Story 5.12 新增 1 个异常——财务建模估值计算失败码)
    "FinancialCalculationError": "financial",
}


def get_subdomain_for_class(class_name: str) -> str | None:
    """通过类名查找其所属子域。

    Args:
        class_name: 异常类名（如 "EntityValidationError"）

    Returns:
        子域名字符串，未找到则返回 None
    """
    return _CLASS_TO_SUBDOMAIN.get(class_name)


def get_range_for_subdomain(subdomain: str) -> tuple[int, int] | None:
    """通过子域名查找其编码范围。

    Args:
        subdomain: 子域名字符串（如 "entity"）

    Returns:
        (start, end) 编码范围元组，未找到则返回 None
    """
    return CODE_RANGES.get(subdomain)


def is_placeholder(numeric_code: int) -> bool:
    """判断编码是否为基类占位符。

    Args:
        numeric_code: 编码的整数部分（如 242）

    Returns:
        True 如果是占位符编码
    """
    return numeric_code in PLACEHOLDER_CODES
