"""爬取任务子进程执行器模块

在独立子进程的主线程中运行 Scrapy CrawlerProcess，规避在服务进程内
运行爬虫的三重冲突（Scrapy 的运行时契约要求进程主线程 + 独立 reactor）：

1. signal handler 只能在主线程安装（后台线程内 ValueError）
2. AsyncioSelectorReactor 会与服务进程（uvicorn）正在运行的事件循环冲突
3. Twisted reactor 是进程级单例且不可重启（第二个任务必然失败）

用法：
    python -m plugins.crawler.task_runner <task_json> <result_json>

任务 JSON 结构：
    {"task": {...CrawlTask.from_dict 格式...}, "settings": {...CrawlerSettings 字段...}}

结果 JSON 结构：
    {"status": "completed"|"failed", "files": [...CrawledFile 字段...],
     "failed_urls": [...], "elapsed_time_sec": float}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _crawl_file_fields(item: dict) -> dict:
    """从 Scrapy item 提取 CrawledFile 字段

    Args:
        item: item_scraped 信号携带的 CrawledFileItem

    Returns:
        CrawledFile 构造字段字典
    """
    return {
        "url": item.get("url", ""),
        "file_path": item.get("file_path", ""),
        "file_name": item.get("file_name", ""),
        "file_size": item.get("file_size", 0),
        "content_type": item.get("content_type", ""),
        "file_extension": item.get("file_extension", ""),
        "smart_name": item.get("smart_name", ""),
        "naming_strategy": item.get("naming_strategy_used", ""),
        "stored_path": item.get("stored_path", ""),
        "task_id": item.get("task_id", ""),
        "parent_url": item.get("parent_url", ""),
        "page_title": item.get("page_title", ""),
        "link_text": item.get("link_text", ""),
        "depth": item.get("depth", 0),
        "metadata_title": item.get("metadata_title", ""),
        "metadata_author": item.get("metadata_author", ""),
    }


def run_task(task_json_path: str, result_json_path: str) -> int:
    """执行单个爬取任务并写出结果 JSON

    Args:
        task_json_path: 任务 JSON 文件路径
        result_json_path: 结果 JSON 输出路径

    Returns:
        进程退出码（0 成功，1 失败）
    """
    import asyncio
    import logging

    from scrapy import signals
    from scrapy.crawler import CrawlerProcess

    from plugins.crawler.config.settings import CrawlerSettings
    from plugins.crawler.core.entities import CrawlResult, CrawlTask
    from plugins.crawler.messaging.console_publisher import ConsolePublisher

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    payload = json.loads(Path(task_json_path).read_text(encoding="utf-8"))
    task = CrawlTask.from_dict(payload["task"])
    settings = CrawlerSettings(**payload["settings"])

    scrapy_settings = settings.to_scrapy_settings()
    process = CrawlerProcess(settings=scrapy_settings)

    files: list[dict] = []
    failed_urls: list[str] = []

    # pydispatcher 按弱引用持有 receiver：匿名 lambda 无强引用会被 GC 静默断连，
    # 必须用具名局部函数（栈帧持有强引用直至 process.start() 返回）
    def _on_item_scraped(item: dict, response, spider) -> None:
        files.append(_crawl_file_fields(item))

    def _on_item_dropped(item: dict, response, exception, spider) -> None:
        failed_urls.append(item.get("url", ""))

    crawler = process.create_crawler("domain")
    crawler.signals.connect(_on_item_scraped, signal=signals.item_scraped)
    crawler.signals.connect(_on_item_dropped, signal=signals.item_dropped)

    extensions = task.allowed_extensions or settings.allowed_extensions
    process.crawl(
        crawler,
        task_id=task.task_id,
        domains=task.domains,
        seed_urls=task.seed_urls,
        allowed_extensions=extensions,
        max_depth=task.max_depth,
        follow_subdomains=task.follow_subdomains,
        use_browser=task.use_browser,
        auth_storage_state_path=task.auth_storage_state_path,
    )

    # 主线程阻塞运行（CrawlerProcess 的契约场景）
    process.start()

    stats = crawler.stats.get_stats() if crawler.stats else {}
    finish_reason = stats.get("finish_reason", "")
    succeeded = finish_reason == "finished"

    elapsed = stats.get("elapsed_time_seconds", 0.0)
    result = {
        "status": "completed" if succeeded else "failed",
        "finish_reason": finish_reason,
        "files": files,
        "failed_urls": failed_urls,
        "elapsed_time_sec": elapsed,
    }
    Path(result_json_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 任务级完成事件（子进程内独立事件循环，安全）
    crawl_result = CrawlResult(task_id=task.task_id)
    crawl_result.total_size_bytes = sum(f.get("file_size", 0) for f in files)
    if succeeded:
        crawl_result.mark_completed()
    else:
        crawl_result.mark_failed()
    asyncio.run(ConsolePublisher().publish_crawl_completed(crawl_result))

    return 0 if succeeded else 1


def main() -> None:
    """CLI 入口：解析参数并执行任务"""
    if len(sys.argv) != 3:
        print("用法: python -m plugins.crawler.task_runner <task_json> <result_json>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(run_task(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
