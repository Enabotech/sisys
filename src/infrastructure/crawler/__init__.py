"""基础设施层 Crawler 适配器包

提供 Crawler HTTP 客户端实现，遵循六边形架构将领域层与外部 Crawler Service 隔离

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

__all__ = ["HttpCrawlerClient"]
