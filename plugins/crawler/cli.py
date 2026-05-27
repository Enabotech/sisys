"""Crawler CLI 入口模块

提供命令行接口：crawl（爬取）和 serve（启动服务）
"""

from __future__ import annotations

import typer

app = typer.Typer(name="crawler", help="SISYS Crawler Plugin CLI")


@app.command()
def crawl(
    domains: list[str] = typer.Option(..., "--domain", "-d", help="目标域名"),
    output: str = typer.Option("./crawl_output", "--output", "-o", help="输出目录"),
    depth: int = typer.Option(3, "--depth", help="最大爬取深度"),
    formats: str = typer.Option(
        "pdf,txt,doc,docx,xls,xlsx,ppt,pptx,zip,wmv,mp4,mp3,wav", "--formats", help="文件格式（逗号分隔）"
    ),
    seed_urls: list[str] = typer.Option([], "--seed-url", "-s", help="种子 URL"),
    follow_subdomains: bool = typer.Option(True, "--follow-subdomains", help="跟踪子域名"),
    obey_robots: bool = typer.Option(True, "--obey-robots / --no-obey-robots", help="遵守 robots.txt"),
    user_agent: str = typer.Option(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "--user-agent",
        "-u",
        help="User-Agent 字符串",
    ),
    browser: bool = typer.Option(False, "--browser / --no-browser", help="启用 Playwright 浏览器模式（绕过 WAF）"),
    browser_pages: int = typer.Option(4, "--browser-pages", help="浏览器并发页面数"),
    browser_timeout: int = typer.Option(30, "--browser-timeout", help="浏览器页面加载超时（秒）"),
) -> None:
    """启动爬取任务（阻塞直到完成）"""
    from scrapy.crawler import CrawlerProcess

    from plugins.crawler.config.settings import CrawlerSettings

    extensions = tuple(f.strip() for f in formats.split(",") if f.strip())

    settings = CrawlerSettings(
        respect_robots_txt=obey_robots,
        max_depth=depth,
        local_output_dir=output,
        enable_browser=browser,
        browser_concurrent_pages=browser_pages,
        browser_navigation_timeout_ms=browser_timeout * 1000,
    )
    scrapy_settings = settings.to_scrapy_settings(user_agent=user_agent)
    scrapy_settings["CRAWL_OUTPUT_DIR"] = output

    process = CrawlerProcess(settings=scrapy_settings)

    process.crawl(
        "domain",
        task_id="cli-crawl",
        domains=tuple(domains),
        seed_urls=tuple(seed_urls),
        allowed_extensions=extensions,
        max_depth=depth,
        follow_subdomains=follow_subdomains,
        use_browser=browser,
    )

    typer.echo("开始爬取...")
    if browser:
        typer.echo("浏览器模式已启用（Playwright）")
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
