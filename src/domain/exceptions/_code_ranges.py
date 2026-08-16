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
