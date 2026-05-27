"""Playwright 资源过滤模块

定义 should_abort_request 谓词函数，中止无关资源请求以加速页面加载
"""

from __future__ import annotations

_ABORT_RESOURCE_TYPES = frozenset(
    {
        "image",  # 图片（jpg/png/gif/svg/webp 等）
        "font",  # 字体（woff/woff2/ttf/eot 等）
        "stylesheet",  # CSS 样式表
        "media",  # 视频/音频（mp4/mp3/wav 等）
    }
)


def should_abort_request(request) -> bool:
    """中止无关资源请求（图片/字体/CSS/媒体）

    scrapy-playwright 的 PLAYWRIGHT_ABORT_REQUEST 配置项接受一个 callable，
    对每个浏览器发起的子请求调用，返回 True 则中止该请求。

    Args:
        request: Playwright Request 对象

    Returns:
        是否中止该请求
    """
    return request.resource_type in _ABORT_RESOURCE_TYPES
