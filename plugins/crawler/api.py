"""Crawler FastAPI 应用模块

提供爬虫服务的 REST API
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field, model_validator

from plugins.crawler.core.entities import CrawlTask
from plugins.crawler.messaging.console_publisher import ConsolePublisher
from plugins.crawler.plugin import CrawlerPlugin
from plugins.crawler.storage.local_storage import LocalStorage


class CrawlTaskRequest(BaseModel):
    """提交爬取任务请求"""

    domains: list[str] = Field(..., min_length=1, description="目标域名列表")
    seed_urls: list[str] = Field(default_factory=list, description="种子 URL")
    follow_subdomains: bool = Field(default=True, description="跟踪子域名")
    max_depth: int = Field(default=3, ge=1, le=10, description="最大深度")
    allowed_extensions: list[str] = Field(default_factory=list, description="文件扩展名")
    url_patterns: dict[str, list[str]] | None = Field(default=None, description="URL 模式")
    max_files: int = Field(default=1000, ge=1, le=10000, description="最大文件数")
    download_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="下载延迟")
    use_browser: bool = Field(default=False, description="启用 Playwright 浏览器模式（绕过 WAF）")
    auth_storage_state_path: str = Field(default="", description="Playwright storageState JSON 文件路径（需启用浏览器模式）")
    auth_headers: dict[str, str] = Field(default_factory=dict, description="额外请求头（如 Authorization）")

    @model_validator(mode="after")
    def validate_auth_config(self) -> "CrawlTaskRequest":
        """校验认证配置合法性"""
        if self.auth_storage_state_path and not self.use_browser:
            raise ValueError("auth_storage_state_path 需要 use_browser=true")
        return self


class CrawlTaskResponse(BaseModel):
    """爬取任务响应"""

    task_id: str
    status: str
    domains: list[str]
    files_crawled: int
    files_failed: int
    total_size_bytes: int
    started_at: str | None = None
    completed_at: str | None = None


def _task_to_response(result: Any) -> CrawlTaskResponse:
    """将 CrawlResult 转换为响应模型

    Args:
        result: CrawlResult 实例

    Returns:
        CrawlTaskResponse
    """
    return CrawlTaskResponse(
        task_id=result.task_id,
        status=result.status.value,
        domains=[],
        files_crawled=len(result.files),
        files_failed=len(result.failed_urls),
        total_size_bytes=result.total_size_bytes,
        started_at=result.started_at.isoformat() if result.started_at else None,
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
    )


def create_app() -> FastAPI:
    """创建 FastAPI 应用

    Returns:
        配置好的 FastAPI 实例
    """
    app = FastAPI(title="SISYS Crawler Service", version="0.1.0")

    plugin = CrawlerPlugin()
    plugin.install()
    plugin.activate(
        storage=LocalStorage(),
        publisher=ConsolePublisher(),
    )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """健康检查"""
        return {"status": "healthy"}

    @app.post("/tasks", status_code=201)
    async def create_task(request: CrawlTaskRequest) -> dict[str, str]:
        """创建爬取任务"""
        url_include: tuple[str, ...] = ()
        url_exclude: tuple[str, ...] = ()
        if request.url_patterns:
            url_include = tuple(request.url_patterns.get("include", []))
            url_exclude = tuple(request.url_patterns.get("exclude", []))

        task = CrawlTask(
            domains=tuple(request.domains),
            seed_urls=tuple(request.seed_urls),
            follow_subdomains=request.follow_subdomains,
            max_depth=request.max_depth,
            allowed_extensions=tuple(request.allowed_extensions) if request.allowed_extensions else (),
            url_include=url_include,
            url_exclude=url_exclude,
            max_files=request.max_files,
            download_delay=request.download_delay,
            use_browser=request.use_browser,
            auth_storage_state_path=request.auth_storage_state_path,
            auth_headers=request.auth_headers,
        )
        task_id = plugin.start_crawl(task)
        return {"task_id": task_id, "status": "submitted"}

    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> CrawlTaskResponse:
        """查询任务状态"""
        result = plugin.get_task_status(task_id)
        if result is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Task not found")
        return _task_to_response(result)

    @app.delete("/tasks/{task_id}")
    async def cancel_task(task_id: str) -> dict[str, Any]:
        """取消任务"""
        success = plugin.cancel_task(task_id)
        if not success:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Cannot cancel task")
        return {"task_id": task_id, "status": "cancelled"}

    @app.get("/tasks")
    async def list_tasks() -> list[CrawlTaskResponse]:
        """列出所有任务"""
        return [_task_to_response(r) for r in plugin.list_tasks()]

    @app.get("/formats")
    async def list_formats() -> dict[str, list[str]]:
        """列出支持的文件格式"""
        return {"formats": plugin.list_supported_formats()}

    return app


app = create_app()
