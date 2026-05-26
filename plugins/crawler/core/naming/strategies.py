"""命名策略模块

定义 5 个纯函数命名策略，无副作用
优先级：metadata_title(0.95) > page_title(0.80) > link_text(0.65) > url_derived(0.45) > content_hash(0.10)
零外部依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from plugins.crawler.core.naming.sanitizer import FilenameSanitizer
from plugins.crawler.core.value_objects import NamingCandidate


def strategy_metadata_title(
    title: str,
    extension: str,
    sanitizer: FilenameSanitizer,
) -> NamingCandidate | None:
    """策略 1：文件元数据标题（置信度 0.95）

    Args:
        title: 文件内嵌元数据中的标题
        extension: 文件扩展名
        sanitizer: 文件名清洗器

    Returns:
        命名候选，或 None（标题为空时）
    """
    if not title or not title.strip():
        return None
    filename = sanitizer.sanitize(title.strip(), extension)
    return NamingCandidate(
        filename=filename,
        strategy_name="metadata_title",
        confidence=0.95,
        source=f"元数据标题: {title[:50]}",
    )


def strategy_page_title(
    title: str,
    author: str,
    extension: str,
    sanitizer: FilenameSanitizer,
) -> NamingCandidate | None:
    """策略 2：页面标题 + 作者上下文（置信度 0.80）

    Args:
        title: HTML 页面标题
        author: 作者（可选，追加到标题后）
        extension: 文件扩展名
        sanitizer: 文件名清洗器

    Returns:
        命名候选，或 None（标题为空时）
    """
    if not title or not title.strip():
        return None
    base = title.strip()
    if author and author.strip():
        base = f"{base} - {author.strip()}"
    filename = sanitizer.sanitize(base, extension)
    return NamingCandidate(
        filename=filename,
        strategy_name="page_title",
        confidence=0.80,
        source=f"页面标题: {title[:50]}",
    )


def strategy_link_text(
    text: str,
    extension: str,
    sanitizer: FilenameSanitizer,
) -> NamingCandidate | None:
    """策略 3：链接锚文本（置信度 0.65）

    Args:
        text: 锚文本内容
        extension: 文件扩展名
        sanitizer: 文件名清洗器

    Returns:
        命名候选，或 None（文本过短时）
    """
    if not text or len(text.strip()) <= 2:
        return None
    filename = sanitizer.sanitize(text.strip(), extension)
    return NamingCandidate(
        filename=filename,
        strategy_name="link_text",
        confidence=0.65,
        source=f"链接文本: {text[:50]}",
    )


def strategy_url_derived(
    url: str,
    extension: str,
    sanitizer: FilenameSanitizer,
) -> NamingCandidate | None:
    """策略 4：URL 路径推导（置信度 0.45）

    从 URL 路径中推导文件名，如 /reports/2024-annual-report.pdf → 2024 Annual Report

    Args:
        url: 文件下载 URL
        extension: 文件扩展名
        sanitizer: 文件名清洗器

    Returns:
        命名候选，或 None（无法推导时）
    """
    path = urlparse(url).path
    filename = path.split("/")[-1] if "/" in path else path
    name, _ = _split_extension(filename)

    if not name or len(name) <= 2:
        return None

    # 将连字符/下划线替换为空格，首字母大写
    name = name.replace("-", " ").replace("_", " ").strip()
    name = " ".join(word.capitalize() for word in name.split())

    if not name or len(name) <= 2:
        return None

    filename = sanitizer.sanitize(name, extension)
    return NamingCandidate(
        filename=filename,
        strategy_name="url_derived",
        confidence=0.45,
        source=f"URL推导: {url[:80]}",
    )


def strategy_content_hash(url: str, extension: str) -> NamingCandidate:
    """策略 5：内容哈希兜底（置信度 0.10）

    Args:
        url: 文件下载 URL（用于生成哈希）
        extension: 文件扩展名

    Returns:
        命名候选（始终返回有效结果）
    """
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    ext = f".{extension}" if extension else ""
    return NamingCandidate(
        filename=f"crawl_{url_hash}{ext}",
        strategy_name="content_hash",
        confidence=0.10,
        source="内容哈希兜底",
    )


def _split_extension(filename: str) -> tuple[str, str]:
    """分割文件名和扩展名

    Args:
        filename: 完整文件名

    Returns:
        (basename, extension) 元组
    """
    if "." in filename:
        parts = filename.rsplit(".", 1)
        return parts[0], parts[1]
    return filename, ""
