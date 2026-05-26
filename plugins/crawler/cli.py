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
    """启动爬取任务（阻塞直到完成）"""
    from scrapy.crawler import CrawlerProcess

    extensions = tuple(f.strip() for f in formats.split(",") if f.strip())

    process = CrawlerProcess(
        settings={
            "BOT_NAME": "sisys_crawler",
            "SPIDER_MODULES": ["plugins.crawler.scrapy_engine.spiders"],
            "NEWSPIDER_MODULE": "plugins.crawler.scrapy_engine.spiders",
            "ROBOTSTXT_OBEY": False,
            "CONCURRENT_REQUESTS": 8,
            "DOWNLOAD_DELAY": 1.0,
            "DOWNLOAD_TIMEOUT": 30,
            "LOG_LEVEL": "INFO",
            "CRAWL_OUTPUT_DIR": output,
            "ITEM_PIPELINES": {
                "plugins.crawler.scrapy_engine.pipelines.file_download_pipeline.FileDownloadPipeline": 100,
                "plugins.crawler.scrapy_engine.pipelines.format_detection_pipeline.FormatDetectionPipeline": 200,
                "plugins.crawler.scrapy_engine.pipelines.metadata_pipeline.MetadataPipeline": 300,
                "plugins.crawler.scrapy_engine.pipelines.smart_naming_pipeline.SmartNamingPipeline": 400,
                "plugins.crawler.scrapy_engine.pipelines.storage_pipeline.StoragePipeline": 500,
                "plugins.crawler.scrapy_engine.pipelines.notification_pipeline.NotificationPipeline": 600,
            },
        },
    )

    process.crawl(
        "domain",
        task_id="cli-crawl",
        domains=tuple(domains),
        seed_urls=tuple(seed_urls),
        allowed_extensions=extensions,
        max_depth=depth,
        follow_subdomains=follow_subdomains,
    )

    typer.echo("开始爬取...")
    process.start()
    typer.echo(f"爬取完成，输出目录: {output}")


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
