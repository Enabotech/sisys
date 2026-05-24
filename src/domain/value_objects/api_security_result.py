"""领域层 API 安全结果值对象

定义 API 安全服务返回的结果类型，用于等保2.0三级接口安全

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    """速率限制检查结果

    Attributes:
        allowed: 请求是否被允许
        remaining: 剩余请求配额
        limit: 请求配额上限
        reset_at: 配额重置时间（ISO 格式）
        retry_after_seconds: 重试等待秒数
    """

    allowed: bool = True
    remaining: int = 0
    limit: int = 100
    reset_at: str = ""
    retry_after_seconds: int = 0


@dataclass(frozen=True)
class AuthValidationResult:
    """API 认证验证结果

    Attributes:
        valid: 认证是否通过
        user_id: 已认证用户标识符
        error_code: 错误码
        error_message: 错误信息
    """

    valid: bool = False
    user_id: str = ""
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class InjectionDetectionResult:
    """注入攻击检测结果

    Attributes:
        detected: 是否检测到注入攻击
        injection_type: 注入类型（sql/xss/command/path_traversal/prompt）
        severity: 严重级别
        sanitized_input: 清洗后的输入
        original_input: 原始输入
    """

    detected: bool = False
    injection_type: str = ""
    severity: str = "medium"
    sanitized_input: str = ""
    original_input: str = ""
