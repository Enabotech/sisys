"""应用层检索过滤条件构建工具模块

提供 DenseSemanticSearchService 和 Bm25SparseSearchService 共享的
过滤条件构建函数，消除 Dense/Sparse 两个服务中 _build_filter 的代码重复。
"""

from __future__ import annotations

from typing import Any

from src.domain.exceptions import ValidationError


def build_search_filter(
    tenant_id: str | None,
    filter_payload: dict | None,
) -> dict | None:
    """构建组合过滤条件，自动注入 tenant_id

    合并 filter_payload 和 tenant_id 为统一的过滤条件字典。
    tenant_id 优先级高于 filter_payload 中的同名键。
    返回 None 表示无过滤条件。

    Args:
        tenant_id: 租户 ID（None 时不注入）
        filter_payload: 原始过滤条件

    Returns:
        组合后的过滤条件（含 tenant_id 注入），无过滤条件时返回 None

    Raises:
        ValidationError: tenant_id 为空或仅含空白字符时
    """
    if tenant_id is None and filter_payload is None:
        return None

    combined: dict[str, Any] = {}
    if filter_payload:
        # 排除 filter_payload 中可能存在的 tenant_id 冲突键
        safe_payload = {k: v for k, v in filter_payload.items() if k != "tenant_id"}
        combined.update(safe_payload)
    if tenant_id is not None:
        safe_tid = tenant_id.strip()
        if not safe_tid:
            raise ValidationError(message="tenant_id 不能为空或仅含空白字符")
        combined["tenant_id"] = safe_tid
    return combined if combined else None


__all__ = [
    "build_search_filter",
]
