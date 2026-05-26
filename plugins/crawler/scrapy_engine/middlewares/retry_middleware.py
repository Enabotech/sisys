"""重试中间件模块

指数退避重试，基于 Scrapy 内置 RetryMiddleware 扩展
"""

from __future__ import annotations

import logging

from scrapy.downloadermiddlewares.retry import RetryMiddleware as ScrapyRetryMiddleware

logger = logging.getLogger(__name__)


class RetryMiddleware(ScrapyRetryMiddleware):
    """指数退避重试中间件

    继承 Scrapy 内置 RetryMiddleware，增加可配置的重试延迟
    """

    def __init__(self, settings):
        """初始化重试中间件

        Args:
            settings: Scrapy 设置
        """
        super().__init__(settings)
        self._max_retry_times = settings.getint("RETRY_TIMES", 3)
        self._retry_http_codes = set(
            settings.getlist("RETRY_HTTP_CODES", [500, 502, 503, 504, 408, 429]),
        )

    def _retry(self, request, reason, spider):
        """重试请求

        Args:
            request: 原始请求
            reason: 重试原因
            spider: Spider 实例

        Returns:
            重试请求
        """
        retries = request.meta.get("retry_times", 0) + 1

        if retries <= self._max_retry_times:
            logger.debug(
                "重试 %s (第 %d/%d 次): %s",
                request.url,
                retries,
                self._max_retry_times,
                reason,
            )
            return super()._retry(request, reason, spider)

        logger.warning("重试次数已用尽: %s", request.url)
        return None
