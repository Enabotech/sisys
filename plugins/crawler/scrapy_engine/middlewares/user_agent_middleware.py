"""User-Agent 轮换中间件模块

UA 池随机轮换，避免被目标网站识别为爬虫
"""

from __future__ import annotations

import logging
import secrets

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class UserAgentRotationMiddleware:
    """UA 池随机轮换中间件"""

    def __init__(self, user_agents: list[str] | None = None):
        """初始化 UA 轮换中间件

        Args:
            user_agents: 自定义 UA 列表，为 None 时使用默认列表
        """
        self._user_agents = user_agents or DEFAULT_USER_AGENTS

    @classmethod
    def from_crawler(cls, crawler):
        """从 Scrapy Crawler 实例创建中间件

        Args:
            crawler: Scrapy Crawler 实例

        Returns:
            UserAgentRotationMiddleware 实例
        """
        custom_uas = crawler.settings.getlist("USER_AGENT_POOL", None)
        return cls(user_agents=custom_uas if custom_uas else None)

    def process_request(self, request, spider):
        """处理请求：设置随机 UA

        Args:
            request: Scrapy Request
            spider: Spider 实例
        """
        ua_index = secrets.randbelow(len(self._user_agents))
        request.headers["User-Agent"] = self._user_agents[ua_index]
