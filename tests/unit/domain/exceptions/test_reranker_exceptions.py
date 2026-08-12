"""重排序异常体系单元测试

验证 RerankError 异常的构造、序列化、HTTP 映射和编码唯一性。
遵循故事规范：RerankError(350)→ExternalException→HTTP 500 精确映射。
"""

from __future__ import annotations

from src.domain.exceptions import (
    ExternalException,
    RerankError,
)


class TestRerankError:
    """RerankError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_350"""
        assert RerankError.code == "EXCEPTION_350"

    def test_inheritance(self) -> None:
        """验证继承 ExternalException"""
        assert issubclass(RerankError, ExternalException)

    def test_constructor_with_context(self) -> None:
        """验证构造器携带 model_name/top_k/result_count 上下文"""
        error = RerankError(
            "重排序失败",
            model_name="BAAI/bge-reranker-v2-m3",
            top_k=20,
            result_count=50,
        )
        assert str(error) == "重排序失败"
        assert error.code == "EXCEPTION_350"
        assert error.context["model_name"] == "BAAI/bge-reranker-v2-m3"
        assert error.context["top_k"] == 20
        assert error.context["result_count"] == 50

    def test_constructor_minimal(self) -> None:
        """验证最简构造（仅 message）"""
        error = RerankError("重排序失败")
        assert error.code == "EXCEPTION_350"
        assert error.context == {}

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = RerankError(
            "重排序模型调用超时",
            model_name="BAAI/bge-reranker-v2-m3",
            top_k=20,
            result_count=50,
            cause=TimeoutError("API 超时"),
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_350"
        assert d["message"] == "重排序模型调用超时"
        assert d["context"]["model_name"] == "BAAI/bge-reranker-v2-m3"
        assert d["context"]["top_k"] == 20
        assert d["context"]["result_count"] == 50
        assert "cause" in d
        assert d["cause"]["type"] == "TimeoutError"

    def test_http_status_500_exact_type(self) -> None:
        """验证 HTTP 映射为 500（精确类型匹配，非 isinstance 回退）"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP, _get_http_status

        error = RerankError("重排序失败")

        # 精确类型注册
        assert RerankError in EXCEPTION_HTTP_MAP, "RerankError 必须在 EXCEPTION_HTTP_MAP 中注册"
        assert EXCEPTION_HTTP_MAP[RerankError] == 500, "RerankError HTTP 映射应为 500"

        # 精确类型断言：type(exc) is RerankError 应命中精确映射（500）而非继承回退（502）
        http_status = _get_http_status(error)
        assert http_status == 500, f"RerankError 应映射 500, 实际 {http_status}"

        # 验证 type(exc) is RerankError 为 True（精确匹配）
        assert type(error) is RerankError, "精确类型断言必须为 True"

    def test_http_status_not_502(self) -> None:
        """验证 RerankError 的 HTTP 映射不是 502（基类 ExternalException 的映射）"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(RerankError) == 500
        # 基类 ExternalException 映射为 502
        assert EXCEPTION_HTTP_MAP.get(ExternalException) == 502
