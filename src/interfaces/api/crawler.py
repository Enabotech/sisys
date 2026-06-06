"""接口层 Crawler API 路由模块

提供 Crawler 任务管理的 REST API 端点，包括任务提交、状态查询、任务取消、格式列表等
遵循六边形架构：接口层通过 DI 容器获取 CrawlerClientPort 实例
"""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from src.domain.exceptions import ServiceUnavailableError
from src.domain.ports.crawler_client import CrawlerClientPort
from src.domain.ports.resolver import get_resolver

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class SubmitTaskRequest(BaseModel):
    """提交爬取任务请求

    Attributes:
        domains: 目标域名列表
        seed_urls: 种子 URL 列表（可选）
        allowed_extensions: 允许的文件扩展名列表（可选）
        max_depth: 最大爬取深度
        follow_subdomains: 是否跟随子域名
        max_files: 最大文件下载数
        download_delay: 下载延迟秒数
    """

    domains: list[str] = Field(..., min_length=1, description="目标域名列表")
    seed_urls: list[str] | None = Field(default=None, description="种子 URL 列表")
    allowed_extensions: list[str] | None = Field(default=None, description="允许的文件扩展名列表")
    max_depth: int = Field(default=3, ge=1, le=10, description="最大爬取深度")
    follow_subdomains: bool = Field(default=True, description="是否跟随子域名")
    max_files: int = Field(default=1000, ge=1, le=10000, description="最大文件下载数")
    download_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="下载延迟秒数")


class SubmitTaskResponse(BaseModel):
    """提交爬取任务响应

    Attributes:
        task_id: 任务 ID
    """

    task_id: str


class TaskStatusResponse(BaseModel):
    """任务状态响应

    Attributes:
        task_id: 任务 ID
        status: 任务状态
        progress: 进度信息
        files_downloaded: 已下载文件数
        errors: 错误数
        created_at: 创建时间
        updated_at: 更新时间
    """

    task_id: str
    status: str
    progress: float | None = None
    files_downloaded: int | None = None
    errors: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CancelTaskResponse(BaseModel):
    """取消任务响应

    Attributes:
        task_id: 任务 ID
        cancelled: 是否取消成功
    """

    task_id: str
    cancelled: bool


class SupportedFormatsResponse(BaseModel):
    """支持的文件格式响应

    Attributes:
        formats: 支持的文件格式列表
    """

    formats: list[str]


# =============================================================================
# Router Factory
# =============================================================================


def create_crawler_router(
    get_crawler_client: Any | None = None,
) -> APIRouter:
    """创建 Crawler API 路由

    Args:
        get_crawler_client: 获取 CrawlerClientPort 实例的工厂函数（可选）
            默认使用 get_resolver().resolve("crawler_client")

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/crawler", tags=["crawler"])

    def _get_client() -> CrawlerClientPort:
        """获取 CrawlerClientPort 实例"""
        if get_crawler_client is not None:
            return cast(CrawlerClientPort, get_crawler_client())
        return cast(CrawlerClientPort, get_resolver().resolve("crawler_client"))

    @router.post(
        "/tasks",
        response_model=SubmitTaskResponse,
        status_code=status.HTTP_201_CREATED,
        summary="提交爬取任务",
        description="提交一个新的爬取任务到 Crawler Service",
    )
    async def submit_task(request: SubmitTaskRequest) -> SubmitTaskResponse:
        """提交爬取任务

        Args:
            request: 提交任务请求

        Returns:
            包含任务 ID 的响应

        Raises:
            ServiceUnavailableError: Crawler Service 不可用
        """
        client = _get_client()
        try:
            task_id = await client.submit_task(
                domains=request.domains,
                seed_urls=request.seed_urls,
                allowed_extensions=request.allowed_extensions,
                max_depth=request.max_depth,
                follow_subdomains=request.follow_subdomains,
                max_files=request.max_files,
                download_delay=request.download_delay,
            )
            return SubmitTaskResponse(task_id=task_id)
        except Exception as e:
            logger.error("Failed to submit crawler task: %s", e)
            raise ServiceUnavailableError(
                f"Crawler service unavailable: {e}",
                cause=e,
            ) from e

    @router.get(
        "/tasks/{task_id}",
        response_model=TaskStatusResponse,
        summary="查询任务状态",
        description="查询指定爬取任务的状态信息",
    )
    async def get_task_status(task_id: str) -> TaskStatusResponse:
        """查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态信息

        Raises:
            ServiceUnavailableError: Crawler Service 不可用
        """
        client = _get_client()
        try:
            status_data = await client.get_task_status(task_id)
            return TaskStatusResponse(
                task_id=status_data.get("task_id", task_id),
                status=status_data.get("status", "unknown"),
                progress=status_data.get("progress"),
                files_downloaded=status_data.get("files_downloaded"),
                errors=status_data.get("errors"),
                created_at=status_data.get("created_at"),
                updated_at=status_data.get("updated_at"),
            )
        except Exception as e:
            logger.error("Failed to get task status: %s", e)
            raise ServiceUnavailableError(
                f"Crawler service unavailable: {e}",
                cause=e,
            ) from e

    @router.delete(
        "/tasks/{task_id}",
        response_model=CancelTaskResponse,
        summary="取消任务",
        description="取消指定的爬取任务",
    )
    async def cancel_task(task_id: str) -> CancelTaskResponse:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            取消结果

        Raises:
            ServiceUnavailableError: Crawler Service 不可用
        """
        client = _get_client()
        try:
            cancelled = await client.cancel_task(task_id)
            return CancelTaskResponse(task_id=task_id, cancelled=cancelled)
        except Exception as e:
            logger.error("Failed to cancel task: %s", e)
            raise ServiceUnavailableError(
                f"Crawler service unavailable: {e}",
                cause=e,
            ) from e

    @router.get(
        "/formats",
        response_model=SupportedFormatsResponse,
        summary="列出支持的文件格式",
        description="获取 Crawler Service 支持的文件格式列表",
    )
    async def list_supported_formats() -> SupportedFormatsResponse:
        """列出支持的文件格式

        Returns:
            支持的文件格式列表

        Raises:
            ServiceUnavailableError: Crawler Service 不可用
        """
        client = _get_client()
        try:
            formats = await client.list_supported_formats()
            return SupportedFormatsResponse(formats=formats)
        except Exception as e:
            logger.error("Failed to list supported formats: %s", e)
            raise ServiceUnavailableError(
                f"Crawler service unavailable: {e}",
                cause=e,
            ) from e

    return router


# 默认路由实例（用于直接导入）
crawler_router = create_crawler_router()


__all__ = ["create_crawler_router", "crawler_router"]
