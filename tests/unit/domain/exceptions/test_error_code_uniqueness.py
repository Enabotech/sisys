"""领域异常错误码全局唯一性验证

确保所有领域异常类拥有唯一的 EXCEPTION_NNN 编码，防止监控告警误报。
"""

from __future__ import annotations

import re

import src.domain.exceptions as exc_module


def test_all_error_codes_unique() -> None:
    """验证所有领域异常编码全局唯一

    注意：__all__ 中可能包含向后兼容别名（如 BaseException 是 DomainError 的别名），
    按类对象 id() 去重以排除同一类的多个引用名。
    """
    classes: list[type] = []
    seen_ids: set[int] = set()
    for name in exc_module.__all__:
        cls = getattr(exc_module, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            if id(cls) not in seen_ids:
                seen_ids.add(id(cls))
                classes.append(cls)

    code_to_classes: dict[str, list[str]] = {}
    for cls in classes:
        code = getattr(cls, "code", None)
        if code is not None:
            code_to_classes.setdefault(code, []).append(cls.__name__)

    dup_report = [f"{code}: {names}" for code, names in code_to_classes.items() if len(names) > 1]
    assert not dup_report, f"重复编码: {dup_report}"


def test_all_codes_match_pattern() -> None:
    """验证所有编码符合 EXCEPTION_NNN 或 EXCEPTION_NXX 格式"""
    for name in exc_module.__all__:
        cls = getattr(exc_module, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            code = getattr(cls, "code", None)
            if code is not None:
                # 纯数字编码（如 EXCEPTION_201）或占位编码（如 EXCEPTION_1XX）
                assert re.match(r"^EXCEPTION_\d[X\d]{2}$", code), f"{name}: 编码格式错误 {code}"


def test_no_placeholder_codes_in_concrete_classes() -> None:
    """验证具体异常类不使用占位编码（如 EXCEPTION_1XX）"""
    # 基类允许占位编码
    base_codes = {"EXCEPTION_000", "EXCEPTION_1XX", "EXCEPTION_2XX", "EXCEPTION_3XX"}

    for name in exc_module.__all__:
        cls = getattr(exc_module, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            code = getattr(cls, "code", None)
            if code is not None and code not in base_codes:
                # 非基类应该使用纯数字编码
                numeric_part = code.replace("EXCEPTION_", "")
                assert numeric_part.isdigit(), f"{name}: 具体类应使用数字编码，当前为 {code}"
