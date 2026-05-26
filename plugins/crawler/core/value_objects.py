"""Crawler 插件值对象模块

定义爬虫核心值对象：CrawlStatus（枚举）、NamingCandidate（命名候选）、FileMetadata（文件元数据）
零外部依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CrawlStatus(Enum):
    """爬取任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class NamingCandidate:
    """命名候选值对象（不可变）

    Attributes:
        filename: 候选文件名（含扩展名）
        strategy_name: 策略名称（metadata_title / page_title / link_text / url_derived / content_hash）
        confidence: 置信度 0.0~1.0
        source: 来源描述（调试用）
    """

    filename: str
    strategy_name: str
    confidence: float
    source: str = ""


@dataclass(frozen=True)
class FileMetadata:
    """文件元数据值对象（不可变）

    Attributes:
        title: 文件标题
        author: 作者
        subject: 主题
        created: 创建日期字符串
        extra: 其他元数据（不可变元组）
    """

    title: str = ""
    author: str = ""
    subject: str = ""
    created: str = ""
    extra: tuple[tuple[str, str], ...] = ()
