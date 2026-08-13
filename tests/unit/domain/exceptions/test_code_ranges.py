"""异常编码子域范围 CI 自动校验。

验证规则：
  Rule 1 - 子域范围：每个具体异常类的编码落在其子域的允许范围内
  Rule 2 - 继承链一致性：子类编码与父类编码同属一个子域
  Rule 3 - 预留范围保护：具体异常类禁止使用基类占位符编码
  Rule 4 - 文档同步：编码分配表与实际代码一致

设计原则：编码由人工分配（语义驱动），CI 自动校验边界（规则驱动）。
参考业界实践：Google Error Model / Stripe API / Kubernetes StatusReason。
"""

from __future__ import annotations

import re

import src.domain.exceptions as exc_module
from src.domain.exceptions._code_ranges import (
    CODE_RANGES,
    get_subdomain_for_class,
    is_placeholder,
)

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _extract_numeric_code(code_str: str) -> int:
    """从 'EXCEPTION_NNN' 提取整数编码，如 'EXCEPTION_242' → 242."""
    match = re.match(r"^EXCEPTION_(\d+)$", code_str)
    if match is None:
        raise ValueError(f"Invalid code format: {code_str}")
    return int(match.group(1))


def _get_concrete_exception_classes() -> list[type]:
    """获取所有具体的（非基类）领域异常类。

    通过 __all__ 发现，按 id() 去重（排除 BaseException/DomainError 别名）。
    """
    classes: list[type] = []
    seen_ids: set[int] = set()
    for name in exc_module.__all__:
        cls = getattr(exc_module, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            if id(cls) not in seen_ids:
                seen_ids.add(id(cls))
                classes.append(cls)
    return classes


def _is_abstract_base(cls: type) -> bool:
    """判断是否为抽象基类（SystemException/BusinessException/ExternalException/DomainError）。"""
    base_names = {"DomainError", "BaseException", "SystemException", "BusinessException", "ExternalException"}
    return cls.__name__ in base_names


# ---------------------------------------------------------------------------
# Rule 1：子域范围校验
# ---------------------------------------------------------------------------


def test_all_concrete_codes_fall_within_subdomain_range() -> None:
    """验证每个具体异常类的编码落在其子域的允许范围内。

    对 _CLASS_TO_SUBDOMAIN 中注册的每个具体类：
    - 提取其数值编码
    - 查找其子域范围
    - 断言: start <= numeric_code <= end
    """
    violations: list[str] = []

    for cls in _get_concrete_exception_classes():
        if _is_abstract_base(cls):
            continue

        class_name = cls.__name__
        code_str = getattr(cls, "code", None)
        if code_str is None:
            continue

        numeric = _extract_numeric_code(code_str)
        if is_placeholder(numeric):
            continue  # 占位符由 Rule 3 处理

        subdomain = get_subdomain_for_class(class_name)
        if subdomain is None:
            violations.append(
                f"{class_name} ({code_str}): 未在 _CLASS_TO_SUBDOMAIN 中注册子域，"
                f"请将类名添加到 _code_ranges.py 的 _CLASS_TO_SUBDOMAIN 字典中"
            )
            continue

        range_info = CODE_RANGES.get(subdomain)
        if range_info is None:
            violations.append(f"{class_name} ({code_str}): 子域 '{subdomain}' 未在 CODE_RANGES 中定义")
            continue

        start, end = range_info
        if not (start <= numeric <= end):
            violations.append(f"{class_name} ({code_str}): 编码 {numeric} 不在子域 '{subdomain}' 的范围 [{start}, {end}] 内")

    assert not violations, f"子域范围违规 ({len(violations)} 项):\n" + "\n".join(f"  - {v}" for v in violations)


# ---------------------------------------------------------------------------
# Rule 2：继承链编码一致性
# ---------------------------------------------------------------------------


def test_subclass_code_in_same_subdomain_as_parent() -> None:
    """验证子类编码与父类编码的继承关系合理。

    子域专用异常（storage/role/entity 等）继承 business 基类是设计意图——允许。
    仅当子域与父域完全不相关（如 entity 继承自 storage）时报告违规。
    """
    violations: list[str] = []
    abstract_names = {"DomainError", "BaseException", "SystemException", "BusinessException", "ExternalException"}

    # 子域 → 父域的合法嵌套关系
    # "storage" 继承自 "business"（201-208）中的 ConflictError/NotFoundError 等 → 允许
    # "entity" 继承自 "business" 中的 ValidationError 等 → 允许
    # 仅同级子域交叉继承时违规（如 entity 继承 storage 的类）
    allowed_child_parent_subdomains: set[tuple[str, str]] = {
        # 子域 → business 基类（标准模式）
        ("storage", "business"),
        ("role", "business"),
        ("service", "business"),
        ("permission", "business"),
        ("entity", "business"),
        ("event", "business"),
        ("transfer", "business"),
        # 子域 → business 基类（词典管理）
        ("dictionary", "business"),
        # 子域 → business 基类（分层检索）
        ("retrieval", "business"),
        # 子域 → external 基类
        ("embedding", "external"),
        ("sandbox", "external"),
        ("ocr", "external"),
        ("llm", "external"),
        ("entity_extraction", "external"),
        # 重排序子域 → external 基类
        ("reranker", "external"),
        # 兜底 → external 基类
        ("fallback", "external"),
    }

    for cls in _get_concrete_exception_classes():
        if _is_abstract_base(cls):
            continue

        class_name = cls.__name__
        code_str = getattr(cls, "code", None)
        if code_str is None:
            continue

        numeric = _extract_numeric_code(code_str)
        if is_placeholder(numeric):
            continue

        child_subdomain = get_subdomain_for_class(class_name)
        if child_subdomain is None:
            continue  # Rule 1 会报告

        # 沿 MRO 向上查找第一个具体的父类
        for parent_cls in cls.__mro__[1:]:
            parent_name = parent_cls.__name__
            if parent_name in abstract_names:
                continue
            parent_code = getattr(parent_cls, "code", None)
            if parent_code is None:
                continue

            parent_numeric = _extract_numeric_code(parent_code)
            if is_placeholder(parent_numeric):
                continue

            parent_subdomain = get_subdomain_for_class(parent_name)
            if parent_subdomain is None:
                continue  # 父类未注册子域

            if child_subdomain != parent_subdomain:
                # 检查是否为合法的子域→基类继承关系
                allowed = (child_subdomain, parent_subdomain) in allowed_child_parent_subdomains
                if not allowed:
                    violations.append(
                        f"{class_name} ({code_str}, 子域={child_subdomain}) 继承自 "
                        f"{parent_name} ({parent_code}, 子域={parent_subdomain}): "
                        f"非法跨子域继承"
                    )
            break  # 只检查第一个具体父类

    assert not violations, f"继承链编码一致性违规 ({len(violations)} 项):\n" + "\n".join(f"  - {v}" for v in violations)


# ---------------------------------------------------------------------------
# Rule 3：预留范围保护
# ---------------------------------------------------------------------------


def test_no_placeholder_codes_in_concrete_classes() -> None:
    """验证具体异常类不使用基类占位符编码。

    占位符编码包括 EXCEPTION_000, EXCEPTION_1XX, EXCEPTION_2XX, EXCEPTION_3XX。
    这些编码仅限 DomainError/SystemException/BusinessException/ExternalException 使用。
    """
    violations: list[str] = []

    for cls in _get_concrete_exception_classes():
        if _is_abstract_base(cls):
            continue

        class_name = cls.__name__
        code_str = getattr(cls, "code", None)
        if code_str is None:
            continue

        # 检查数字部分是否为占位符
        if is_placeholder(_extract_numeric_code(code_str)):
            violations.append(f"{class_name} ({code_str}): 具体异常类禁止使用占位符编码")

    assert not violations, f"预留范围保护违规 ({len(violations)} 项):\n" + "\n".join(f"  - {v}" for v in violations)


# ---------------------------------------------------------------------------
# Rule 4：文档同步校验
# ---------------------------------------------------------------------------


def test_code_ranges_cover_all_registered_classes() -> None:
    """验证 _CLASS_TO_SUBDOMAIN 覆盖了所有具体异常类。

    每个在 __all__ 中导出的具体异常类都必须在 _CLASS_TO_SUBDOMAIN 中有对应条目。
    这确保新增异常类不会被 CI 漏检。
    """
    violations: list[str] = []

    for cls in _get_concrete_exception_classes():
        if _is_abstract_base(cls):
            continue

        class_name = cls.__name__
        code_str = getattr(cls, "code", None)
        if code_str is None:
            violations.append(f"{class_name}: 缺少 code 属性")
            continue

        if is_placeholder(_extract_numeric_code(code_str)):
            continue  # 占位符由 Rule 3 处理

        if get_subdomain_for_class(class_name) is None:
            violations.append(f"{class_name} ({code_str}): 未在 _code_ranges.py 的 _CLASS_TO_SUBDOMAIN 字典中注册")

    assert not violations, f"注册覆盖违规 ({len(violations)} 项):\n" + "\n".join(f"  - {v}" for v in violations)


def test_all_subdomain_ranges_are_valid() -> None:
    """验证 CODE_RANGES 中的所有子域范围格式正确。

    - start <= end
    - 同级子域范围不重叠（子域可在父域范围内嵌套，如 embedding/sandbox ⊆ external）
    - key 不为空
    """
    violations: list[str] = []

    # 构建子域嵌套关系：子域 → 父域
    # embedding 和 sandbox 是 external 的二级子域，允许嵌套
    nested_subdomains: dict[str, str] = {
        "embedding": "external",
        "sandbox": "external",
        "ocr": "external",
        "llm": "external",
        "entity_extraction": "external",
        "reranker": "external",
    }

    for subdomain, (start, end) in CODE_RANGES.items():
        if not subdomain.strip():
            violations.append("子域名不能为空")
            continue
        if start > end:
            violations.append(f"子域 '{subdomain}': start ({start}) > end ({end})")
            continue

    # 排除嵌套子域后，检查其余子域范围不重叠
    covered: dict[int, str] = {}
    for subdomain, (start, end) in CODE_RANGES.items():
        if subdomain in nested_subdomains:
            # 验证嵌套子域确实在其父域范围内
            parent = nested_subdomains[subdomain]
            parent_start, parent_end = CODE_RANGES[parent]
            if not (parent_start <= start <= end <= parent_end):
                violations.append(
                    f"嵌套子域 '{subdomain}' [{start}, {end}] 不在父域 '{parent}' [{parent_start}, {parent_end}] 范围内"
                )
            continue

        for n in range(start, end + 1):
            if n in covered:
                violations.append(f"编码 {n} 冲突: 子域 '{subdomain}' 与 '{covered[n]}' 重叠")
            covered[n] = subdomain

    assert not violations, f"子域范围定义违规 ({len(violations)} 项):\n" + "\n".join(f"  - {v}" for v in violations)
