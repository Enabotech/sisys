"""智能命名引擎模块

按优先级链生成多个候选名称，选择置信度最高者，处理冲突
零外部依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import hashlib
import time

from plugins.crawler.core.naming.sanitizer import FilenameSanitizer
from plugins.crawler.core.naming.strategies import (
    strategy_content_hash,
    strategy_link_text,
    strategy_metadata_title,
    strategy_page_title,
    strategy_url_derived,
)
from plugins.crawler.core.value_objects import NamingCandidate


class SmartNamingEngine:
    """智能命名引擎

    按优先级链生成候选，选择置信度最高者，处理冲突

    Attributes:
        _sanitizer: 文件名清洗器
        _conflict_strategy: 冲突处理策略（append_hash / append_counter / overwrite）
        _seen_names: 已使用文件名计数器（冲突检测）
    """

    def __init__(
        self,
        max_length: int = 200,
        conflict_strategy: str = "append_hash",
    ):
        self._sanitizer = FilenameSanitizer(max_length)
        self._conflict_strategy = conflict_strategy
        self._seen_names: dict[str, int] = {}

    def generate_name(
        self,
        metadata_title: str | None = None,
        page_title: str | None = None,
        link_text: str | None = None,
        url: str | None = None,
        file_extension: str = "",
        author: str = "",
    ) -> NamingCandidate:
        """生成最终文件名

        内部调用 5 个策略生成候选列表，选择置信度最高者，处理冲突

        Args:
            metadata_title: 文件元数据标题
            page_title: HTML 页面标题
            link_text: 链接锚文本
            url: 文件下载 URL
            file_extension: 文件扩展名
            author: 作者

        Returns:
            最终命名候选

        Raises:
            ValueError: 无任何可用候选时
        """
        candidates = self._generate_candidates(
            metadata_title=metadata_title,
            page_title=page_title,
            link_text=link_text,
            url=url,
            file_extension=file_extension,
            author=author,
        )

        if not candidates:
            raise ValueError("无可用命名候选")

        chosen = max(candidates, key=lambda c: c.confidence)
        resolved_filename = self._resolve_conflict(chosen.filename)
        return NamingCandidate(
            filename=resolved_filename,
            strategy_name=chosen.strategy_name,
            confidence=chosen.confidence,
            source=chosen.source,
        )

    def reset_seen(self) -> None:
        """重置去重计数器（新任务开始时调用）"""
        self._seen_names.clear()

    def _generate_candidates(
        self,
        metadata_title: str | None = None,
        page_title: str | None = None,
        link_text: str | None = None,
        url: str | None = None,
        file_extension: str = "",
        author: str = "",
    ) -> list[NamingCandidate]:
        """按优先级生成候选列表"""
        candidates: list[NamingCandidate] = []

        # 策略 1: 文件元数据标题
        candidate = strategy_metadata_title(metadata_title or "", file_extension, self._sanitizer)
        if candidate:
            candidates.append(candidate)

        # 策略 2: 页面标题
        candidate = strategy_page_title(page_title or "", author, file_extension, self._sanitizer)
        if candidate:
            candidates.append(candidate)

        # 策略 3: 链接锚文本
        candidate = strategy_link_text(link_text or "", file_extension, self._sanitizer)
        if candidate:
            candidates.append(candidate)

        # 策略 4: URL 路径推导
        if url:
            candidate = strategy_url_derived(url, file_extension, self._sanitizer)
            if candidate:
                candidates.append(candidate)

        # 策略 5: 内容哈希（兜底，始终返回）
        if url:
            candidates.append(strategy_content_hash(url, file_extension))

        return candidates

    def _resolve_conflict(self, filename: str) -> str:
        """处理文件名冲突

        Args:
            filename: 原始文件名

        Returns:
            处理冲突后的文件名
        """
        if filename not in self._seen_names:
            self._seen_names[filename] = 1
            return filename

        self._seen_names[filename] += 1
        base, ext = self._split_extension(filename)

        if self._conflict_strategy == "append_counter":
            return f"{base} ({self._seen_names[filename]}).{ext}" if ext else f"{base} ({self._seen_names[filename]})"
        elif self._conflict_strategy == "append_hash":
            short_hash = hashlib.sha256(f"{filename}{time.time()}".encode()).hexdigest()[:8]
            return f"{base}_{short_hash}.{ext}" if ext else f"{base}_{short_hash}"
        else:
            return filename

    @staticmethod
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
