"""接口层文档上传 API 路由模块

提供文档上传的 REST API 端点，包括单文件上传、批量上传、分片上传和文档查询
遵循六边形架构：接口层通过 DI 容器获取应用服务实例
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.value_objects.token_payload import TokenPayload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class ChunkedInitRequest(BaseModel):
    """分片上传初始化请求

    Attributes:
        filename: 文件名
        file_size: 文件大小（字节）
        doc_type: 文档类型（用于路径生成）
    """

    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0)
    doc_type: str = Field(default="other")


class ChunkedInitResponse(BaseModel):
    """分片上传初始化响应

    Attributes:
        upload_id: 上传会话 ID
        chunk_size: 分片大小
        total_parts: 总分片数
    """

    upload_id: str
    chunk_size: int
    total_parts: int


class ChunkedPartResponse(BaseModel):
    """分片上传响应

    Attributes:
        uploaded_parts: 已上传分片数
    """

    uploaded_parts: int


class DocumentResponse(BaseModel):
    """文档响应

    Attributes:
        document_id: 文档 ID
        filename: 文件名
        mime_type: MIME 类型
        file_size_bytes: 文件大小
        parse_status: 解析状态
        created_at: 创建时间
    """

    document_id: str
    filename: str
    mime_type: str
    file_size_bytes: int
    parse_status: str
    created_at: str


class BatchUploadResponse(BaseModel):
    """批量上传响应

    Attributes:
        total: 总文件数
        success: 成功数
        failed: 失败数
        details: 详细结果
    """

    total: int
    success: int
    failed: int
    details: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    """错误响应

    Attributes:
        detail: 错误详情
    """

    detail: str


def get_current_user_dependency(
    auth_service: AuthServicePort,
) -> Callable:
    """创建 get_current_user 依赖工厂

    Args:
        auth_service: 认证服务实例

    Returns:
        依赖函数
    """

    async def get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return await auth_service.verify_token(token)
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return get_current_user


def create_document_upload_router(
    upload_service: Any = None,
    chunked_manager: Any = None,
    document_storage: Any = None,
    auth_service: AuthServicePort | None = None,
    get_current_user_override: Callable | None = None,
) -> APIRouter:
    """创建文档上传 API 路由

    Args:
        upload_service: DocumentUploadService 实例（可选，默认从 DI 容器获取）
        chunked_manager: ChunkedUploadManager 实例（可选，默认从 DI 容器获取）
        document_storage: DocumentStoragePort 实例（可选，默认从 DI 容器获取）
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）
        get_current_user_override: 认证依赖覆盖（测试用）

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

    def _get_service() -> Any:
        if upload_service is not None:
            return upload_service
        from src.domain.ports.resolver import get_resolver

        return get_resolver().resolve("document_upload_service")

    def _get_chunked_manager() -> Any:
        if chunked_manager is not None:
            return chunked_manager
        from src.domain.ports.resolver import get_resolver

        return get_resolver().resolve("chunked_upload_manager")

    def _get_storage() -> Any:
        if document_storage is not None:
            return document_storage
        from src.domain.ports.resolver import get_resolver

        return get_resolver().resolve("document_storage")

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

    @router.post(
        "",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
        summary="单文件上传",
    )
    async def upload_document(
        file: UploadFile,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DocumentResponse:
        """上传单个文件"""
        svc = _get_service()
        content = await file.read()
        file_size = len(content)

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            doc = await svc.upload(
                filename=file.filename or "unknown",
                mime_type=file.content_type or "application/octet-stream",
                file_size_bytes=file_size,
                tenant_id=x_tenant_id,
                uploaded_by=str(current_user.user_id),
                file_path=tmp_path,
            )
            return DocumentResponse(
                document_id=str(doc.document_id),
                filename=doc.filename,
                mime_type=doc.mime_type,
                file_size_bytes=doc.file_size_bytes,
                parse_status=doc.parse_status.value,
                created_at=doc.created_at.isoformat(),
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.post(
        "/batch",
        response_model=BatchUploadResponse,
        summary="批量上传",
    )
    async def upload_batch(
        files: list[UploadFile],
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> BatchUploadResponse:
        """批量上传文件"""
        svc = _get_service()

        file_infos = []
        file_paths = []

        for f in files:
            content = await f.read()
            file_infos.append(
                {
                    "filename": f.filename or "unknown",
                    "mime_type": f.content_type or "application/octet-stream",
                    "file_size_bytes": len(content),
                }
            )
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{f.filename}")
            tmp.write(content)
            tmp.close()
            file_paths.append(tmp.name)

        try:
            result = await svc.upload_batch(
                files=file_infos,
                tenant_id=x_tenant_id,
                uploaded_by=str(current_user.user_id),
                file_paths=file_paths,
            )
            return BatchUploadResponse(**result)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.post(
        "/chunked/init",
        response_model=ChunkedInitResponse,
        summary="初始化分片上传",
    )
    async def chunked_init(
        request: ChunkedInitRequest,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> ChunkedInitResponse:
        """初始化分片上传"""
        storage = _get_storage()
        mgr = _get_chunked_manager()

        minio_upload_id, object_key = await storage.init_multipart_upload(
            user_id=str(current_user.user_id),
            doc_type=request.doc_type,
            filename=request.filename,
        )

        result = await mgr.init_upload(
            request.filename,
            request.file_size,
            minio_upload_id=minio_upload_id,
            object_key=object_key,
        )
        return ChunkedInitResponse(**result)

    @router.put(
        "/chunked/{upload_id}/parts/{part_number}",
        response_model=ChunkedPartResponse,
        summary="上传分片",
    )
    async def chunked_upload_part(
        upload_id: str,
        part_number: int,
        part: UploadFile,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> ChunkedPartResponse:
        """上传单个分片"""
        mgr = _get_chunked_manager()
        storage = _get_storage()

        info = await mgr.get_multipart_info(upload_id)
        if info is None:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="upload_id 不存在或已过期")

        data = await part.read()
        etag = await storage.upload_part(
            minio_upload_id=info["minio_upload_id"],
            object_key=info["object_key"],
            part_number=part_number,
            data=data,
        )

        try:
            result = await mgr.upload_part(upload_id, part_number, etag)
            return ChunkedPartResponse(**result)
        except ValueError as e:
            if "不存在" in str(e):
                raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.post(
        "/chunked/{upload_id}/complete",
        response_model=DocumentResponse,
        summary="完成分片上传",
    )
    async def chunked_complete(
        upload_id: str,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DocumentResponse:
        """完成分片上传"""
        mgr = _get_chunked_manager()
        svc = _get_service()
        storage = _get_storage()
        try:
            state = await mgr.complete_upload(upload_id)
        except ValueError as e:
            if "不存在" in str(e):
                raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        if state.minio_upload_id and state.object_key:
            await storage.complete_multipart_upload(
                minio_upload_id=state.minio_upload_id,
                object_key=state.object_key,
                parts=state.uploaded_parts,
            )

        doc = await svc.register_document(
            filename=state.filename,
            mime_type="application/octet-stream",
            file_size_bytes=state.file_size,
            tenant_id=x_tenant_id,
            uploaded_by=str(current_user.user_id),
            object_key=state.object_key,
        )
        return DocumentResponse(
            document_id=str(doc.document_id),
            filename=doc.filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            parse_status=doc.parse_status.value,
            created_at=doc.created_at.isoformat(),
        )

    @router.get(
        "/{document_id}",
        response_model=DocumentResponse,
        summary="查询文档",
    )
    async def get_document(
        document_id: uuid.UUID,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> DocumentResponse:
        """查询文档详情"""
        svc = _get_service()
        doc = await svc.get_document(document_id, x_tenant_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        return DocumentResponse(
            document_id=str(doc.document_id),
            filename=doc.filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            parse_status=doc.parse_status.value,
            created_at=doc.created_at.isoformat(),
        )

    return router


document_upload_router = create_document_upload_router()


__all__ = ["create_document_upload_router", "document_upload_router"]
