"""文档版本差异计算领域服务

提供 compute_diff 纯函数，用于计算文档版本间的差异摘要。
定义在领域层，仅使用 Python 标准库（difflib），无外部依赖。

diff 计算策略（对齐架构文档 §11.2.9 MemoryChangeHistory.diff_summary 模式）：
- 元数据 diff：比较 old_metadata 与 new_metadata 的字段差异，生成 changed_fields 列表
- 内容 diff：比较 old_content_summary 与 new_content_summary 的文本差异
- 首次版本：is_initial=True 时 diff_summary="initial version"，changed_fields=[]
- 空变更：无差异时 diff_summary="no changes"，changed_fields=[]
"""

from __future__ import annotations

import difflib
from typing import Any

from src.domain.value_objects.document_version import DocumentVersionDiff


def compute_diff(
    old_metadata: dict[str, Any],
    new_metadata: dict[str, Any],
    old_content_summary: str | None = None,
    new_content_summary: str | None = None,
    is_initial: bool = False,
) -> DocumentVersionDiff:
    """计算文档版本间的差异摘要

    Args:
        old_metadata: 旧版本的元数据字典
        new_metadata: 新版本的元数据字典
        old_content_summary: 旧版本的内容摘要字符串
        new_content_summary: 新版本的内容摘要字符串
        is_initial: 是否为首次版本（version=1）

    Returns:
        DocumentVersionDiff 值对象，包含差异摘要和变更字段列表
    """
    # 首次版本：直接返回 initial version 标记
    if is_initial:
        return DocumentVersionDiff(
            diff_summary="initial version",
            changed_fields=[],
            is_initial=True,
        )

    # 计算元数据差异
    changed_fields = _compute_metadata_diff(old_metadata, new_metadata)

    # 计算内容摘要差异
    old_content = (old_content_summary or "").strip()
    new_content = (new_content_summary or "").strip()

    # 如果元数据和内容都无变化，返回 no changes
    if not changed_fields and old_content == new_content:
        return DocumentVersionDiff(
            diff_summary="no changes",
            changed_fields=[],
        )

    # 构建差异摘要
    diff_parts: list[str] = []

    if changed_fields:
        diff_parts.append(f"changed fields: {', '.join(sorted(changed_fields))}")

    if old_content != new_content and old_content and new_content:
        content_diff = _compute_content_diff(old_content, new_content)
        if content_diff:
            diff_parts.append(content_diff)
    elif old_content != new_content:
        diff_parts.append("content changed")

    diff_summary = "; ".join(diff_parts) if diff_parts else "changes detected"

    return DocumentVersionDiff(
        diff_summary=diff_summary,
        changed_fields=changed_fields,
    )


def _compute_metadata_diff(
    old_metadata: dict[str, Any],
    new_metadata: dict[str, Any],
) -> list[str]:
    """计算元数据字段差异，返回发生变更的字段列表

    Args:
        old_metadata: 旧版本元数据
        new_metadata: 新版本元数据

    Returns:
        发生变更的字段名列表
    """
    changed: list[str] = []

    all_keys = set(old_metadata.keys()) | set(new_metadata.keys())

    for key in sorted(all_keys):
        old_val = old_metadata.get(key)
        new_val = new_metadata.get(key)

        if key not in old_metadata:
            # 新增字段
            changed.append(key)
        elif key not in new_metadata:
            # 删除字段
            changed.append(key)
        elif old_val != new_val:
            # 值变更
            changed.append(key)

    return changed


def _compute_content_diff(old_content: str, new_content: str) -> str:
    """计算文本内容差异，生成摘要

    Args:
        old_content: 旧内容摘要
        new_content: 新内容摘要

    Returns:
        差异摘要字符串
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            n=0,  # 只输出变更行，不输出上下文
        )
    )

    # 过滤掉文件头行（---, +++, @@）
    actual_changes = [line for line in diff_lines if line.startswith("+") or line.startswith("-")]
    # 排除 --- 和 +++ 文件头
    actual_changes = [line for line in actual_changes if not line.startswith("---") and not line.startswith("+++")]

    if not actual_changes:
        return ""

    # 限制摘要长度
    max_lines = 10
    if len(actual_changes) > max_lines:
        remaining = len(actual_changes) - max_lines
        summary = "content diff: " + "".join(actual_changes[:max_lines]).rstrip()
        summary += f"\n... and {remaining} more changes"
        return summary

    return "content diff: " + "".join(actual_changes).rstrip()
