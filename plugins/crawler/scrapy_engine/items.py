"""Scrapy Items 定义模块

定义 CrawledFileItem，Pipeline 链逐步填充字段
"""

from __future__ import annotations

import scrapy


class CrawledFileItem(scrapy.Item):
    """爬取文件 Item — Pipeline 链逐步填充

    Attributes:
        url: 文件下载 URL
        file_path: 本地临时文件路径
        file_name: 原始文件名
        file_size: 文件大小（字节）
        content_type: MIME 类型
        file_extension: 文件扩展名
        detected_format: 检测到的格式
        metadata_title: 文件元数据标题
        metadata_author: 文件元数据作者
        metadata_created: 文件元数据创建日期
        metadata_extra: 额外元数据
        smart_name: 智能命名结果
        naming_strategy_used: 使用的命名策略
        parent_url: 来源页面 URL
        page_title: 来源页面标题
        link_text: 链接锚文本
        depth: 爬取深度
        task_id: 所属任务 ID
    """

    url = scrapy.Field()
    file_path = scrapy.Field()
    file_name = scrapy.Field()
    file_size = scrapy.Field()
    content_type = scrapy.Field()
    file_extension = scrapy.Field()
    detected_format = scrapy.Field()
    metadata_title = scrapy.Field()
    metadata_content_title = scrapy.Field()
    metadata_author = scrapy.Field()
    metadata_created = scrapy.Field()
    metadata_extra = scrapy.Field()
    smart_name = scrapy.Field()
    naming_strategy_used = scrapy.Field()
    parent_url = scrapy.Field()
    page_title = scrapy.Field()
    link_text = scrapy.Field()
    depth = scrapy.Field()
    task_id = scrapy.Field()
