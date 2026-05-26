"""速率限制中间件模块

域名级别令牌桶限速
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """域名级别令牌桶限速中间件"""

    def __init__(
        self,
        max_requests_per_second: float = 2.0,
    ):
        """初始化限速中间件

        Args:
            max_requests_per_second: 每秒最大请求数
        """
        self._max_rps = max_requests_per_second
        self._domain_tokens: dict[str, float] = defaultdict(lambda: max_requests_per_second)
        self._domain_last_time: dict[str, float] = defaultdict(time.monotonic)

    @classmethod
    def from_crawler(cls, crawler):
        """从 Scrapy Crawler 实例创建中间件

        Args:
            crawler: Scrapy Crawler 实例

        Returns:
            RateLimitMiddleware 实例
        """
        max_rps = crawler.settings.getfloat("RATE_LIMIT_RPS", 2.0)
        return cls(max_requests_per_second=max_rps)

    def process_request(self, request, spider):
        """处理请求：检查速率限制

        Args:
            request: Scrapy Request
            spider: Spider 实例

        Returns:
            None 或 IgnoreRequest
        """
        from urllib.parse import urlparse

        domain = urlparse(request.url).hostname or "unknown"
        now = time.monotonic()
        elapsed = now - self._domain_last_time[domain]

        self._domain_tokens[domain] = min(
            self._max_rps,
            self._domain_tokens[domain] + elapsed * self._max_rps,
        )
        self._domain_last_time[domain] = now

        if self._domain_tokens[domain] < 1.0:
            wait_time = (1.0 - self._domain_tokens[domain]) / self._max_rps
            time.sleep(wait_time)
            self._domain_tokens[domain] = 0.0
        else:
            self._domain_tokens[domain] -= 1.0

        return None
