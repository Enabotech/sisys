"""领域层 API 安全服务端口模块

定义 API 安全服务的抽象接口，遵循六边形架构端口协议
用于等保2.0三级接口安全

设计原则：
- check_rate_limit(): 速率限制检查
- validate_api_auth(): API 认证验证
- detect_injection_attack(): 注入攻击检测
- add_security_headers(): 安全响应头

注意：validate_api_auth 和 add_security_headers 方法使用 Any 类型
避免领域层引入 HTTP 框架依赖（fastapi.Request/Response）
具体框架类型在 infrastructure 层适配器中处理
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.value_objects.api_security_result import (
    AuthValidationResult,
    InjectionDetectionResult,
    RateLimitResult,
)


@runtime_checkable
class APISecurityServicePort(Protocol):
    """API 安全服务抽象端口

    等保2.0三级接口安全要求的核心服务端口，负责：
    - 速率限制（令牌桶算法）
    - API 认证验证
    - 注入攻击检测（SQL/XSS/命令注入）
    - 安全响应头注入

    实现类必须遵循此接口契约，确保端口的可替换性
    """

    async def check_rate_limit(
        self,
        client_id: str,
        endpoint: str = "",
    ) -> RateLimitResult:
        """检查客户端速率限制

        Args:
            client_id: 客户端标识符
            endpoint: API 端点路径（可选）

        Returns:
            RateLimitResult 包含是否允许、剩余配额、重置时间等
        """
        ...

    async def validate_api_auth(
        self,
        request: Any,
    ) -> AuthValidationResult:
        """验证 API 请求认证

        Args:
            request: HTTP 请求对象（使用 Any 避免领域层引入 HTTP 框架依赖）

        Returns:
            AuthValidationResult 包含认证结果和用户信息
        """
        ...

    async def detect_injection_attack(
        self,
        input_data: str,
        context: str = "",
    ) -> InjectionDetectionResult:
        """检测输入数据中的注入攻击

        Args:
            input_data: 待检测的输入数据
            context: 输入上下文（query/body/header/url）

        Returns:
            InjectionDetectionResult 包含检测结果和清洗后的输入
        """
        ...

    async def add_security_headers(
        self,
        response: Any,
    ) -> Any:
        """为 HTTP 响应添加安全头

        Args:
            response: HTTP 响应对象（使用 Any 避免领域层引入 HTTP 框架依赖）

        Returns:
            添加了安全头的响应对象
        """
        ...
