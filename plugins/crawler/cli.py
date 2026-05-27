"""Crawler CLI 入口模块

提供命令行接口：crawl（爬取）和 serve（启动服务）
"""

from __future__ import annotations

import typer

app = typer.Typer(name="crawler", help="SISYS Crawler Plugin CLI")


def _try_fill(page, value: str, selectors: list[str]) -> bool:
    """尝试在页面中查找选择器并填入值

    Args:
        page: Playwright Page 对象
        value: 要填入的值
        selectors: CSS 选择器列表

    Returns:
        是否成功填入
    """
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            el.fill(value)
            return True
    return False


def _try_click(page, selectors: list[str]) -> bool:
    """尝试在页面中查找选择器并点击

    Args:
        page: Playwright Page 对象
        selectors: CSS 选择器列表

    Returns:
        是否成功点击
    """
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            el.click()
            return True
    return False


def _auto_login(
    login_url: str,
    username: str,
    password: str,
    storage_path: str,
) -> None:
    """使用 Playwright 自动登录并导出 storageState

    自动检测运行环境：有图形界面时打开可见浏览器（方便手动处理验证码），
    无图形界面时使用 headless 模式自动登录。

    Args:
        login_url: 登录页面 URL
        username: 登录用户名
        password: 登录密码
        storage_path: storageState 导出路径
    """
    import os

    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not has_display)
        context = browser.new_context()
        page = context.new_page()

        typer.echo(f"正在登录: {login_url} ({'可见' if has_display else 'headless'} 模式)")
        page.goto(login_url)
        page.wait_for_load_state("domcontentloaded")

        # 第一步：填写用户名
        _try_fill(
            page,
            username,
            [
                'input[type="email"]',
                'input[name="username"]',
                'input[name="email"]',
                "#email",
                "#username",
            ],
        )
        _try_click(
            page,
            [
                'button[type="submit"]',
                'input[type="submit"]',
            ],
        )
        page.wait_for_timeout(2000)

        # 第二步：填写密码
        _try_fill(
            page,
            password,
            [
                'input[type="password"]',
                'input[name="password"]',
                "#password",
            ],
        )
        _try_click(
            page,
            [
                'button[type="submit"]',
                'input[type="submit"]',
            ],
        )
        page.wait_for_timeout(3000)

        if has_display:
            typer.echo("如有验证码/二次验证，请在浏览器中手动处理，完成后按 Enter 继续...")
            input()
        else:
            # headless 模式：等待页面跳转完成（最长 30 秒）
            try:
                page.wait_for_url("**/**", timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(5000)

        context.storage_state(path=storage_path)
        browser.close()

    typer.echo(f"登录态已保存: {storage_path}")


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
    auth_storage_state: str = typer.Option(
        "", "--auth-storage-state", help="Playwright storageState JSON 文件路径（需配合 --browser）"
    ),
    auth_header: list[str] = typer.Option([], "--auth-header", help="额外请求头（格式: Key=Value，可多次指定）"),
    auth_basic: str = typer.Option("", "--auth-basic", help="HTTP Basic Auth（格式: user:pass）"),
    login_url: str = typer.Option("", "--login-url", help="自动登录页面 URL（配合 --login-user 使用）"),
    login_user: str = typer.Option("", "--login-user", help="登录用户名（自动打开浏览器完成登录）"),
    login_pass: str = typer.Option("", "--login-pass", help="登录密码"),
) -> None:
    """启动爬取任务（阻塞直到完成）"""
    import base64
    import os

    from scrapy.crawler import CrawlerProcess

    from plugins.crawler.config.settings import CrawlerSettings

    extensions = tuple(f.strip() for f in formats.split(",") if f.strip())

    # 解析认证参数
    auth_headers: dict[str, str] = {}

    if auth_basic:
        if ":" not in auth_basic:
            typer.echo("错误: --auth-basic 格式应为 user:pass")
            raise typer.Exit(code=1)
        encoded = base64.b64encode(auth_basic.encode()).decode()
        auth_headers["Authorization"] = f"Basic {encoded}"

    for hdr in auth_header:
        if "=" not in hdr:
            typer.echo(f"警告: 忽略无效 header 格式 '{hdr}'，应为 Key=Value")
            continue
        key, _, value = hdr.partition("=")
        auth_headers[key.strip()] = value.strip()

    if auth_storage_state:
        if not os.path.isfile(auth_storage_state):
            typer.echo(f"错误: storageState 文件不存在: {auth_storage_state}")
            raise typer.Exit(code=1)
        if not browser:
            typer.echo("错误: --auth-storage-state 需要配合 --browser 使用")
            raise typer.Exit(code=1)

    # 自动登录流程：打开浏览器 → 填写凭证 → 导出 storageState
    if login_user:
        import tempfile

        if not browser:
            typer.echo("错误: --login-user 需要配合 --browser 使用")
            raise typer.Exit(code=1)

        target_url = login_url or f"https://login.{domains[0]}"
        storage_path = os.path.join(tempfile.gettempdir(), "crawler", f"login_{domains[0]}.json")

        _auto_login(target_url, login_user, login_pass, storage_path)
        auth_storage_state = storage_path

    settings = CrawlerSettings(
        respect_robots_txt=obey_robots,
        max_depth=depth,
        local_output_dir=output,
        enable_browser=browser,
        browser_concurrent_pages=browser_pages,
        browser_navigation_timeout_ms=browser_timeout * 1000,
        auth_storage_state_path=auth_storage_state,
        auth_headers=auth_headers,
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
        storage_state_path=auth_storage_state,
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
