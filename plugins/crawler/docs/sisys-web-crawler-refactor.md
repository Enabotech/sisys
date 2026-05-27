# Crawler CLI 科学性审查与优化方案

## 一、审查结论摘要

经对标 Typer/Click 生态、AWS CLI/gcloud/Docker 等业界实践，当前 CLI 存在 **6 类问题**，按严重度排序：

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | 命名跨层不一致（同一概念 3 种名字） | 高 | 增加认知负担，容易传错参数 |
| 2 | 浏览器相关选项无条件校验 | 高 | 用户传入无效选项被静默忽略 |
| 3 | `--formats` 默认值与 Settings 不一致（12 vs 36 格式） | 中 | CLI 与 API 行为不同 |
| 4 | 死参数 `browser_concurrent_pages` 从未注入 Scrapy | 中 | `--browser-pages` 形同虚设 |
| 5 | `user_agent` 和 `CRAWL_OUTPUT_DIR` 散落在调用方 | 低 | 维护成本高 |
| 6 | CLI 绕过 CrawlTask 实体层，校验逻辑不复用 | 低 | CLI 与 API 行为可能分叉 |

---

## 二、设计原则（对标业界）

### P1. 命名约定：各层用各层的惯例，概念名统一

业界共识（Django、Scrapy、Microsoft CLI Design Guidance）：

| 层 | 惯例 | 示例 |
|----|------|------|
| CLI 参数 | `--kebab-case` | `--browser-timeout` |
| Python 代码 / 实体 | `snake_case` | `browser_timeout` |
| 环境变量 | `UPPER_SNAKE_CASE` | `CRAWLER_BROWSER_TIMEOUT` |

Typer 自动将 `--kebab-case` 转为 Python `snake_case` 参数名。**概念名在各层保持一致**（都是 `browser_timeout`），只是分隔符随层变化。

**推论**：`CrawlerSettings` 中的 `browser_navigation_timeout_ms` 应改为 `browser_timeout`（秒为单位，与 CLI 一致），内部转 ms 的逻辑收归 `to_scrapy_settings()`。

### P2. 条件校验：依赖选项报错，调优选项警告

业界实践（Docker、AWS CLI）：**冲突/缺失依赖 → 报错退出**。不存在的组合不应静默通过。

本系统分级处理：
- **必须依赖 `--browser`**（缺失则无意义）：`--auth-storage-state`、`--login-user` → **报错**（已有）
- **仅浏览器调优**（缺失则被忽略）：`--browser-timeout`、`--browser-headless`、`--browser-proxy` → **警告**

### P3. 选项分组：`rich_help_panel` 视觉分组

Typer 官方支持 `rich_help_panel`，纯视觉分组，不影响校验。本系统分为 4 组。

### P4. 默认值：单一来源，Config 对象优先

业界共识的优先级：`CLI 参数 > 环境变量 > 配置对象 > 硬编码`

本系统以 `CrawlerSettings()` 实例作为默认值来源，CLI 参数覆盖之。

### P5. 内聚：配置逻辑收归 Settings 类

`user_agent` 和 `CRAWL_OUTPUT_DIR` 不应散落在 `cli.py` / `plugin.py` 后置注入，应收归 `CrawlerSettings.to_scrapy_settings()`。

---

## 三、详细变更

### 阶段 1：命名归一化

**原则**：一个概念一个名字，全链路统一。

| 概念 | 当前 CLI | 当前 Settings | 当前 Entity | 当前 Spider | 统一后（全部层） |
|------|---------|--------------|-------------|-------------|----------------|
| 浏览器模式 | `--browser` | `enable_browser` | `use_browser` | `use_browser` | **`use_browser`** |
| 认证文件 | `--auth-storage-state` | `auth_storage_state_path` | `auth_storage_state_path` | `storage_state_path` | **`auth_storage_state_path`** |
| 深度 | `--depth` | `max_depth` | `max_depth` | `max_depth` | **`max_depth`**（CLI 加 `--max-depth` 别名） |
| 浏览器超时 | `--browser-timeout`（秒） | `browser_navigation_timeout_ms`（ms） | — | — | **`browser_timeout`**（秒，内部转 ms） |

**文件变更**：

| 文件 | 变更 |
|------|------|
| `config/settings.py` | `enable_browser` → `use_browser`；`browser_navigation_timeout_ms` → `browser_timeout`（秒，`to_scrapy_settings()` 内 `* 1000`）；`browser_concurrent_pages` → 删除（见阶段 2） |
| `spiders/domain_spider.py` | 构造器 `storage_state_path` → `auth_storage_state_path`；`_load_cookies(storage_state_path)` → `_load_cookies(auth_storage_state_path)` |
| `plugin.py` | `enable_browser=` → `use_browser=`；`storage_state_path=` → `auth_storage_state_path=`；`browser_navigation_timeout_ms=` → `browser_timeout=` |
| `cli.py` | `enable_browser=browser` → `use_browser=browser`；`storage_state_path=` → `auth_storage_state_path=` |
| `scrapy_engine/settings.py` | 注释更新 |
| 测试文件 | 全部同步字段名 |

### 阶段 2：清除死参数

**`browser_concurrent_pages`**：scrapy-playwright 使用 Scrapy 的 `CONCURRENT_REQUESTS` 控制并发，无独立页面并发配置。该字段从未被 `to_scrapy_settings()` 写入任何 Scrapy 设置。

| 文件 | 变更 |
|------|------|
| `config/settings.py` | 删除 `browser_concurrent_pages` 字段 + `from_env()` 中对应行 |
| `cli.py` | 删除 `--browser-pages` 选项 |
| `plugin.py` | 删除 `browser_concurrent_pages=` 传参行 |

**实体层保留但标注**：`CrawlTask` 中 `max_files`、`max_file_size_mb`、`url_include`、`url_exclude` 保留（API 已对外暴露，不能删），加注释 `# NOTE: 尚未在 spider 中实现`。

### 阶段 3：Settings 内聚化

#### 3a. `user_agent` 从方法参数升级为字段

```python
# Before:
def to_scrapy_settings(self, user_agent: str | None = None) -> dict:
    if user_agent:
        settings["USER_AGENT"] = user_agent

# After:
user_agent: str = ""  # 空串 = UA 轮换中间件处理

def to_scrapy_settings(self) -> dict:
    if self.user_agent:
        settings["USER_AGENT"] = self.user_agent
```

调用方（`cli.py`、`plugin.py`）从 `settings.to_scrapy_settings(user_agent=...)` 改为 `settings.user_agent = ...` 后调用 `settings.to_scrapy_settings()`。

#### 3b. `CRAWL_OUTPUT_DIR` 注入收入 `to_scrapy_settings()`

```python
def to_scrapy_settings(self) -> dict:
    ...
    settings["CRAWL_OUTPUT_DIR"] = self.local_output_dir
    return settings
```

`cli.py` 和 `plugin.py` 删除后置注入行。

#### 3c. `from_env()` 补充缺失字段

`auth_headers` 环境变量加载：`CRAWLER_AUTH_HEADERS` 解析为 JSON dict。

### 阶段 4：CLI 重组

#### 4a. 选项分组

```python
@app.command()
def crawl(
    # ── 目标（无面板，顶层）──
    domains: list[str] = typer.Option(..., "--domain", "-d", help="目标域名"),
    seed_urls: list[str] = typer.Option([], "--seed-url", "-s", help="种子 URL"),
    output: str = typer.Option(..., "--output", "-o",
        help="输出目录", rich_help_panel="目标"),

    # ── 爬取控制 ──
    max_depth: int = typer.Option(3, "--max-depth", "--depth",
        help="最大爬取深度", rich_help_panel="爬取控制"),
    formats: str | None = typer.Option(None, "--formats",
        help="文件格式（逗号分隔，默认全部支持）",
        rich_help_panel="爬取控制"),
    follow_subdomains: bool = typer.Option(True, "--follow-subdomains",
        help="跟踪子域名", rich_help_panel="爬取控制"),
    obey_robots: bool = typer.Option(True,
        "--obey-robots/--no-obey-robots", help="遵守 robots.txt",
        rich_help_panel="爬取控制"),
    download_delay: float = typer.Option(1.0, "--download-delay",
        help="请求间隔（秒）", rich_help_panel="爬取控制"),
    user_agent: str = typer.Option("", "--user-agent", "-u",
        help="User-Agent（留空则自动轮换）", rich_help_panel="爬取控制"),

    # ── 浏览器模式 ──
    browser: bool = typer.Option(False, "--browser/--no-browser",
        help="启用 Playwright 浏览器模式", rich_help_panel="浏览器模式"),
    browser_timeout: int = typer.Option(30, "--browser-timeout",
        help="浏览器页面加载超时（秒）", rich_help_panel="浏览器模式"),
    browser_headless: bool = typer.Option(True,
        "--browser-headless/--no-browser-headless",
        help="浏览器无头模式", rich_help_panel="浏览器模式"),
    browser_proxy: str = typer.Option("", "--browser-proxy",
        help="浏览器代理地址", rich_help_panel="浏览器模式"),

    # ── 认证 ──
    auth_storage_state: str = typer.Option("", "--auth-storage-state",
        help="Playwright storageState JSON（需 --browser）",
        rich_help_panel="认证"),
    auth_header: list[str] = typer.Option([], "--auth-header",
        help="请求头 Key=Value（可多次指定）", rich_help_panel="认证"),
    auth_basic: str = typer.Option("", "--auth-basic",
        help="HTTP Basic Auth user:pass", rich_help_panel="认证"),
    login_url: str = typer.Option("", "--login-url",
        help="自动登录页面 URL", rich_help_panel="认证"),
    login_user: str = typer.Option("", "--login-user",
        help="登录用户名", rich_help_panel="认证"),
    login_pass: str = typer.Option("", "--login-pass",
        help="登录密码", rich_help_panel="认证"),
):
```

#### 4b. 默认值统一

```python
_defaults = CrawlerSettings()

# CLI 参数默认值从 _defaults 派生：
# --max-depth 默认 → _defaults.max_depth
# --obey-robots 默认 → _defaults.respect_robots_txt
# --output 默认 → _defaults.local_output_dir
# --browser-timeout 默认 → _defaults.browser_timeout  # 已改为秒
# --download-delay 默认 → _defaults.download_delay
# --formats 默认 → None（运行时回退到 _defaults.allowed_extensions）
```

#### 4c. 浏览器条件校验

```python
# 函数体顶部，参数解析后立即校验
if not browser:
    _default_timeout = _defaults.browser_timeout
    if browser_timeout != _default_timeout:
        typer.echo(f"警告: --browser-timeout 在非浏览器模式下无效")
    if browser_proxy:
        typer.echo("警告: --browser-proxy 在非浏览器模式下无效")
    if not browser_headless:  # 用户显式传了 --no-browser-headless
        typer.echo("警告: --no-browser-headless 在非浏览器模式下无效")

# 已有的报错校验保持不变
if auth_storage_state and not browser:
    typer.echo("错误: --auth-storage-state 需要配合 --browser 使用")
    raise typer.Exit(code=1)
if login_user and not browser:
    typer.echo("错误: --login-user 需要配合 --browser 使用")
    raise typer.Exit(code=1)
```

### 阶段 5：修复 pyproject.toml 入口

删除 `sisys = "src.cli:app"`（指向不存在的模块）。`crawler` 入口保留。

---

## 四、变更影响矩阵

| 文件 | 阶段 1 | 阶段 2 | 阶段 3 | 阶段 4 | 阶段 5 |
|------|:------:|:------:|:------:|:------:|:------:|
| `cli.py` | ★ | ★ | ★ | ★★ | |
| `config/settings.py` | ★ | ★ | ★ | | |
| `plugin.py` | ★ | ★ | ★ | | |
| `spiders/domain_spider.py` | ★ | | | | |
| `scrapy_engine/settings.py` | ★ | | | | |
| `core/entities.py` | | ★注 | | | |
| `pyproject.toml` | | | | | ★ |
| `tests/unit/test_settings.py` | ★ | ★ | ★ | | |
| `tests/unit/test_domain_spider.py` | ★ | | | | |
| `tests/unit/test_entities.py` | | | | | |

★ = 小改，★★ = 大改

---

## 五、向后兼容性

| 变更 | 兼容性影响 | 处理策略 |
|------|-----------|---------|
| `--browser-pages` 删除 | 已有脚本报 "unrecognized option" | 可接受（该选项从未生效） |
| `--depth` → `--max-depth` | 已有脚本报 "unrecognized option" | **保留 `--depth` 作为隐藏别名**，`--max-depth` 为主名 |
| `enable_browser` → `use_browser` | 仅影响 Python 调用方 | 内部变更，CLI/API 用户无感 |
| `--formats` 默认从 12 变为 36 | CLI 默认抓取更多格式 | 可接受（用户可用 `--formats pdf,docx` 缩窄） |
| `user_agent` 从参数变字段 | 仅影响 `to_scrapy_settings()` 调用方 | 内部变更，无感 |

`--depth` 兼容性处理：保留 `--depth` 作为参数名，帮助文本用 `--max-depth` 展示：

```python
max_depth: int = typer.Option(3, "--max-depth", "--depth",
    help="最大爬取深度", rich_help_panel="爬取控制"),
```

---

## 六、验证方案

每个阶段完成后执行：

```bash
# 1. 代码质量
poetry run ruff check plugins/crawler/ && poetry run ruff format plugins/crawler/

# 2. 单元测试
poetry run pytest plugins/crawler/tests/ -v

# 3. CLI 帮助输出（阶段 4 完成后）
poetry run crawler crawl --help
# 应看到 4 个分组面板，无 --browser-pages

# 4. 条件校验（阶段 4 完成后）
poetry run crawler crawl -d example.com --browser-timeout 60
# 应输出警告: --browser-timeout 在非浏览器模式下无效

# 5. 端到端冒烟测试
poetry run crawler crawl -d example.com --formats pdf --max-depth 1 --no-obey-robots
```
