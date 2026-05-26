"""Crawler CLI 入口模块

提供命令行接口：crawl（爬取）和 serve（启动服务）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import typer

app = typer.Typer(name="crawler", help="SISYS Crawler Plugin CLI")


@app.command()
def crawl(
    domains: list[str] = typer.Option(..., "--domain", "-d", help="目标域名"),
    output: str = typer.Option("./crawl_output", "--output", "-o", help="输出目录"),
    depth: int = typer.Option(3, "--depth", help="最大爬取深度"),
    formats: str = typer.Option("pdf,txt,docx,xlsx,pptx", "--formats", help="文件格式（逗号分隔）"),
    seed_urls: list[str] = typer.Option([], "--seed-url", "-s", help="种子 URL"),
    follow_subdomains: bool = typer.Option(True, "--follow-subdomains", help="跟踪子域名"),
) -> None:
    """启动爬取任务"""
    from plugins.crawler.core.entities import CrawlTask
    from plugins.crawler.messaging.console_publisher import ConsolePublisher
    from plugins.crawler.plugin import CrawlerPlugin
    from plugins.crawler.storage.local_storage import LocalStorage

    plugin = CrawlerPlugin()
    plugin.install()
    plugin.activate(
        storage=LocalStorage(output_dir=output),
        publisher=ConsolePublisher(),
    )

    extensions = tuple(f.strip() for f in formats.split(",") if f.strip())
    task = CrawlTask(
        domains=tuple(domains),
        seed_urls=tuple(seed_urls),
        max_depth=depth,
        allowed_extensions=extensions,
        follow_subdomains=follow_subdomains,
    )

    task_id = plugin.start_crawl(task)
    typer.echo(f"爬取任务已启动: {task_id}")


@app.command()
def serve(
    host: str = typer.Option("", "--host", help="监听地址"),
    port: int = typer.Option(8900, "--port", help="监听端口"),
) -> None:
    """启动 Crawler REST 服务"""
    import uvicorn

    uvicorn.run(
        "plugins.crawler.api:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    app()
