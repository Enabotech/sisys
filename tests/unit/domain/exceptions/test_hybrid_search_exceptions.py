"""HybridSearchError 异常体系单元测试

验证 HybridSearchError 异常的构造、序列化、HTTP 映射和编码唯一性。
遵循故事规范：HybridSearchError(209)→BusinessException→HTTP 500。
"""

from __future__ import annotations

from src.domain.exceptions import (
    BusinessException,
    HybridSearchError,
)


class TestHybridSearchError:
    """HybridSearchError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_209"""
        assert HybridSearchError.code == "EXCEPTION_209"

    def test_inheritance(self) -> None:
        """验证继承 BusinessException"""
        assert issubclass(HybridSearchError, BusinessException)

    def test_constructor(self) -> None:
        """验证构造器"""
        error = HybridSearchError("三路检索通道均失败")
        assert str(error) == "三路检索通道均失败"
        assert error.code == "EXCEPTION_209"

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = HybridSearchError(
            "三路检索通道均失败",
            cause=RuntimeError("Dense 和 Sparse 通道均失败"),
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_209"
        assert d["message"] == "三路检索通道均失败"
        assert "cause" in d
        assert d["cause"]["type"] == "RuntimeError"

    def test_http_status_500(self) -> None:
        """验证 HTTP 映射为 500"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP, _get_http_status

        error = HybridSearchError("三路检索通道均失败")

        assert HybridSearchError in EXCEPTION_HTTP_MAP, "HybridSearchError 必须在 EXCEPTION_HTTP_MAP 中注册"
        assert EXCEPTION_HTTP_MAP[HybridSearchError] == 500, "HybridSearchError HTTP 映射应为 500"

        http_status = _get_http_status(error)
        assert http_status == 500, f"HybridSearchError 应映射 500, 实际 {http_status}"
