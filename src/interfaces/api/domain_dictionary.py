"""接口层领域词典 REST API 路由模块

提供词条 CRUD + 热更新 + 快照 + 回滚的 REST API。
遵循六边形架构：接口层通过 DI 容器获取应用服务实例。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.value_objects.token_payload import TokenPayload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ===================================================================
# 请求/响应 Schema
# ===================================================================


class DictionaryEntryCreate(BaseModel):
    """添加词条请求

    Attributes:
        term: 词条文本
        entity_type: 实体类型
        category: 词条类别
        active: 是否启用
    """

    term: str = Field(..., min_length=1, max_length=200)
    entity_type: str = Field(..., min_length=1, max_length=50)
    category: str = Field(default="general", max_length=50)
    active: bool = True


class DictionaryEntryUpdate(BaseModel):
    """修改词条请求

    Attributes:
        entity_type: 实体类型
        category: 词条类别
        active: 是否启用
        version: 当前版本号（乐观锁）
    """

    entity_type: str = Field(..., min_length=1, max_length=50)
    category: str = Field(default="general", max_length=50)
    active: bool = True
    version: int = Field(default=1, ge=1)


class DictionaryEntryResponse(BaseModel):
    """词条响应

    Attributes:
        term: 词条文本
        entity_type: 实体类型
        category: 词条类别
        active: 是否启用
        version: 词条版本
        created_by: 创建者
        created_at: 创建时间
        updated_at: 更新时间
    """

    term: str
    entity_type: str
    category: str
    active: bool
    version: int
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""


class DictionaryListResponse(BaseModel):
    """词条列表响应

    Attributes:
        items: 词条列表
        total: 总数量
        page: 当前页码
        page_size: 每页条数
    """

    items: list[DictionaryEntryResponse]
    total: int
    page: int
    page_size: int


class DictionarySnapshotResponse(BaseModel):
    """快照响应

    Attributes:
        snapshot_id: 快照 ID
        version: 词典版本号
        created_by: 创建者
        created_at: 创建时间
        entry_count: 词条数量
        change_summary: 变更摘要
    """

    snapshot_id: str
    version: int
    created_by: str = ""
    created_at: str = ""
    entry_count: int = 0
    change_summary: dict = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    """操作通知响应

    Attributes:
        message: 操作消息
    """

    message: str


# ===================================================================
# 认证依赖
# ===================================================================


def get_current_user_dependency(auth_service: AuthServicePort) -> Callable:
    """创建 get_current_user 依赖工厂

    Args:
        auth_service: 认证服务端口

    Returns:
        get_current_user 依赖函数
    """

    async def get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload:
        """验证 Bearer token 返回当前用户

        Args:
            token: Bearer token

        Returns:
            当前用户 TokenPayload

        Raises:
            HTTPException: 未认证或 token 无效
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        result: TokenPayload = await auth_service.verify_token(token)
        return result

    return get_current_user


# ===================================================================
# 路由工厂
# ===================================================================


def create_document_dictionary_router(
    dictionary_service: Any = None,
    auth_service: AuthServicePort | None = None,
    get_current_user_override: Callable | None = None,
) -> APIRouter:
    """创建领域词典 API 路由

    Args:
        dictionary_service: DomainDictionaryService 实例（可选，默认从 DI 容器获取）
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）
        get_current_user_override: 认证依赖覆盖（测试用）

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/documents/dictionary", tags=["dictionary"])

    def _get_service() -> Any:
        if dictionary_service is not None:
            return dictionary_service
        from src.domain.ports.resolver import get_resolver

        return get_resolver().resolve("domain_dictionary_service")

    if get_current_user_override is not None:
        get_current_user = get_current_user_override
    elif auth_service is not None:
        get_current_user = get_current_user_dependency(auth_service)
    else:

        async def get_current_user(
            token: str | None = Depends(oauth2_scheme),
        ) -> TokenPayload:
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            from src.domain.ports.resolver import get_resolver

            svc: AuthServicePort = get_resolver().resolve("auth_service")
            try:
                result: TokenPayload = await svc.verify_token(token)
                return result
            except AuthenticationError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    @router.get(
        "/entries",
        response_model=DictionaryListResponse,
        summary="列出词条",
    )
    async def list_entries(
        category: str | None = None,
        entity_type: str | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DictionaryListResponse:
        """按条件列出词条（分页 + 过滤）

        Args:
            category: 按类别过滤
            entity_type: 按实体类型过滤
            active_only: 仅返回启用词条
            page: 页码
            page_size: 每页条数
            current_user: 当前用户

        Returns:
            词条列表 + 分页信息
        """
        del current_user  # 仅认证
        from src.domain.ports.domain_dictionary import DictionaryQuery

        query = DictionaryQuery(
            category=category,
            entity_type=entity_type,
            active_only=active_only,
            page=page,
            page_size=page_size,
        )
        service = _get_service()
        entries = await service.list_entries(query)
        total = await service.count_entries(
            DictionaryQuery(
                category=category,
                entity_type=entity_type,
                active_only=active_only,
                page=1,
                page_size=1,
            )
        )
        return DictionaryListResponse(
            items=[_to_entry_response(e) for e in entries],
            total=total,
            page=page,
            page_size=page_size,
        )

    @router.post(
        "/entries",
        response_model=DictionaryEntryResponse,
        status_code=status.HTTP_201_CREATED,
        summary="添加词条",
    )
    async def add_entry(
        payload: DictionaryEntryCreate,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DictionaryEntryResponse:
        """添加词条

        Args:
            payload: 添加词条请求
            current_user: 当前用户

        Returns:
            已保存的词条
        """
        del current_user  # 仅认证
        from src.domain.ports.domain_dictionary import DictionaryEntry

        entry = DictionaryEntry(
            term=payload.term,
            entity_type=payload.entity_type,
            category=payload.category,
            active=payload.active,
        )
        service = _get_service()
        saved = await service.add_entry(entry, trigger="api")
        return _to_entry_response(saved)

    @router.put(
        "/entries/{term}",
        response_model=DictionaryEntryResponse,
        summary="修改词条",
    )
    async def update_entry(
        term: str,
        payload: DictionaryEntryUpdate,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DictionaryEntryResponse:
        """修改词条

        Args:
            term: 要修改的词条名
            payload: 修改词条请求
            current_user: 当前用户

        Returns:
            更新后的词条
        """
        del current_user  # 仅认证
        from src.domain.ports.domain_dictionary import DictionaryEntry

        entry = DictionaryEntry(
            term=term,
            entity_type=payload.entity_type,
            category=payload.category,
            active=payload.active,
            version=payload.version,
        )
        service = _get_service()
        updated = await service.update_entry(term, entry, trigger="api")
        return _to_entry_response(updated)

    @router.delete(
        "/entries/{term}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="删除词条",
    )
    async def delete_entry(
        term: str,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> None:
        """删除词条

        Args:
            term: 要删除的词条名
            current_user: 当前用户
        """
        del current_user  # 仅认证
        service = _get_service()
        await service.delete_entry(term, trigger="api")

    @router.post(
        "/refresh",
        response_model=NotificationResponse,
        summary="触发热更新",
    )
    async def refresh_dictionary(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> NotificationResponse:
        """触发热更新：将活动词典注入规则抽取器

        Args:
            current_user: 当前用户

        Returns:
            热更新通知
        """
        del current_user  # 仅认证
        service = _get_service()
        await service.refresh_dictionary()
        return NotificationResponse(message="词典已热更新")

    @router.post(
        "/snapshots",
        response_model=DictionarySnapshotResponse,
        status_code=status.HTTP_201_CREATED,
        summary="创建快照",
    )
    async def create_snapshot(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DictionarySnapshotResponse:
        """创建词典快照

        Args:
            current_user: 当前用户

        Returns:
            创建的词典快照
        """
        created_by = current_user.username if current_user else "api"
        service = _get_service()
        snapshot = await service.create_snapshot(created_by)
        return _to_snapshot_response(snapshot)

    @router.post(
        "/rollback/{version}",
        response_model=NotificationResponse,
        summary="回滚至指定版本",
    )
    async def rollback(
        version: int,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> NotificationResponse:
        """回滚至指定版本

        Args:
            version: 目标词典版本号
            current_user: 当前用户

        Returns:
            回滚通知
        """
        del current_user  # 仅认证
        service = _get_service()
        await service.rollback(version, trigger="api")
        return NotificationResponse(message=f"词典已回滚至版本 {version}")

    @router.get(
        "/snapshots",
        response_model=list[DictionarySnapshotResponse],
        summary="列出快照",
    )
    async def list_snapshots(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> list[DictionarySnapshotResponse]:
        """列出所有快照

        Args:
            current_user: 当前用户

        Returns:
            快照列表
        """
        del current_user  # 仅认证
        service = _get_service()
        snapshots = await service.list_snapshots()
        return [_to_snapshot_response(s) for s in snapshots]

    return router


# ===================================================================
# 响应转换
# ===================================================================


def _to_entry_response(entry: Any) -> DictionaryEntryResponse:
    """将领域词条转换为响应模型

    Args:
        entry: DictionaryEntry 领域值对象

    Returns:
        DictionaryEntryResponse 响应模型
    """
    return DictionaryEntryResponse(
        term=entry.term,
        entity_type=entry.entity_type,
        category=entry.category,
        active=entry.active,
        version=entry.version,
        created_by=entry.created_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _to_snapshot_response(snapshot: Any) -> DictionarySnapshotResponse:
    """将领域快照转换为响应模型

    Args:
        snapshot: DictionarySnapshot 领域值对象

    Returns:
        DictionarySnapshotResponse 响应模型
    """
    change_summary = dict(snapshot.change_summary or {})
    entry_count = change_summary.get("entry_count", 0)
    return DictionarySnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        version=snapshot.version,
        created_by=snapshot.created_by,
        created_at=snapshot.created_at,
        entry_count=entry_count,
        change_summary=change_summary,
    )


document_dictionary_router = create_document_dictionary_router()

__all__ = ["create_document_dictionary_router", "document_dictionary_router"]
