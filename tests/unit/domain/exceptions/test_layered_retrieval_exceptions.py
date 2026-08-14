"""Story 3.5 分层检索异常体系单元测试

验证 LayeredRetrievalError 和 LevelTransitionError 异常的构造、序列化、
HTTP 映射和编码唯一性。
遵循故事规范：新增 retrieval 子域（280-289），异常继承 BusinessException。
"""

from __future__ import annotations

from src.domain.exceptions import BusinessException
from src.domain.exceptions.layered_retrieval_exceptions import (
    LayeredRetrievalError,
    LevelTransitionError,
)


class TestLayeredRetrievalError:
    """LayeredRetrievalError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_280"""
        assert LayeredRetrievalError.code == "EXCEPTION_280"

    def test_inheritance(self) -> None:
        """验证继承 BusinessException"""
        assert issubclass(LayeredRetrievalError, BusinessException)

    def test_constructor(self) -> None:
        """验证构造器"""
        error = LayeredRetrievalError("分层检索编排失败")
        assert str(error) == "分层检索编排失败"
        assert error.code == "EXCEPTION_280"

    def test_constructor_with_context(self) -> None:
        """验证构造器携带层级上下文"""
        error = LayeredRetrievalError(
            "分层检索编排失败",
            context={
                "current_level": "L4",
                "target_level": "L3",
                "query_text": "测试查询",
            },
        )
        assert error.code == "EXCEPTION_280"
        assert error.context["current_level"] == "L4"
        assert error.context["target_level"] == "L3"
        assert error.context["query_text"] == "测试查询"

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = LayeredRetrievalError(
            "分层检索编排失败",
            cause=RuntimeError("Dense 检索通道均失败"),
            context={"target_level": "L3"},
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_280"
        assert d["message"] == "分层检索编排失败"
        assert "cause" in d
        assert d["cause"]["type"] == "RuntimeError"
        assert d["context"]["target_level"] == "L3"

    def test_http_status_500(self) -> None:
        """验证 HTTP 映射（500 — 规范要求 500/500）

        Raises:
            AssertionError: HTTP 映射非 500 时抛出
        """
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP, _get_http_status

        error = LayeredRetrievalError("分层检索编排失败")

        assert LayeredRetrievalError in EXCEPTION_HTTP_MAP, "LayeredRetrievalError 必须在 EXCEPTION_HTTP_MAP 中注册"
        http_status = _get_http_status(error)
        assert http_status == 500, f"HTTP 映射异常: {http_status}"


class TestLevelTransitionError:
    """LevelTransitionError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_281"""
        assert LevelTransitionError.code == "EXCEPTION_281"

    def test_inheritance(self) -> None:
        """验证继承 BusinessException"""
        assert issubclass(LevelTransitionError, BusinessException)

    def test_constructor(self) -> None:
        """验证构造器"""
        error = LevelTransitionError("层级遍历非法")
        assert str(error) == "层级遍历非法"
        assert error.code == "EXCEPTION_281"

    def test_constructor_with_levels(self) -> None:
        """验证构造器携带层级上下文"""
        error = LevelTransitionError(
            "层级遍历非法",
            context={
                "current_level": "L4",
                "target_level": "L1",
                "reason": "多级全遍历尚未实现（MVP 仅支持相邻层级单级遍历）",
            },
        )
        assert error.code == "EXCEPTION_281"
        assert error.context["current_level"] == "L4"
        assert error.context["target_level"] == "L1"

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = LevelTransitionError(
            "层级遍历非法",
            cause=ValueError("非相邻层级遍历"),
            context={"current_level": "L2", "target_level": "L4"},
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_281"
        assert d["message"] == "层级遍历非法"
        assert "cause" in d
        assert d["context"]["current_level"] == "L2"

    def test_http_status(self) -> None:
        """验证 HTTP 映射（500 — 规范要求 500/500）"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP, _get_http_status

        error = LevelTransitionError("层级遍历非法")

        assert LevelTransitionError in EXCEPTION_HTTP_MAP, "LevelTransitionError 必须在 EXCEPTION_HTTP_MAP 中注册"
        http_status = _get_http_status(error)
        assert http_status == 500, f"HTTP 映射异常: {http_status}"


class TestRetrievalSubdomain:
    """retrieval 子域范围验证"""

    def test_code_within_retrieval_subdomain(self) -> None:
        """验证编码在 retrieval 子域（280-281）范围内

        说明：Story 3.9/3.10 新增 archive 子域占用 (282, 289)，
        retrieval 子域因此收缩为 (280, 281)，仅容纳本故事的两个异常。
        """
        from src.domain.exceptions._code_ranges import get_range_for_subdomain, get_subdomain_for_class

        assert get_range_for_subdomain("retrieval") == (280, 281), "retrieval 子域范围应为 (280, 281)"

        assert get_subdomain_for_class("LayeredRetrievalError") == "retrieval"
        assert get_subdomain_for_class("LevelTransitionError") == "retrieval"

    def test_code_not_conflict_with_adjacent_subdomains(self) -> None:
        """验证编码不与相邻子域碰撞"""
        from src.domain.exceptions._code_ranges import CODE_RANGES

        # dictionary 子域是 (270, 279)，retrieval 是 (280, 281)，archive 是 (282, 289)，external 是 (301, 399)
        # retrieval 不与任何其他子域重叠
        retrieval_start, retrieval_end = CODE_RANGES["retrieval"]
        for subdomain, (start, end) in CODE_RANGES.items():
            if subdomain == "retrieval":
                continue
            overlap = not (retrieval_end < start or end < retrieval_start)
            assert not overlap, f"retrieval 子域与 {subdomain} 重叠"
