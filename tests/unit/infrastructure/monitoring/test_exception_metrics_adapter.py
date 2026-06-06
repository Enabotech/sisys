"""基础设施层异常指标适配器单元测试

验证 ExceptionMetricsAdapter 的委托行为：
构造函数创建内部 ExceptionMetricsImpl 实例，
record_exception 正确委托调用
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.infrastructure.monitoring.exception_metrics_adapter import ExceptionMetricsAdapter


class TestExceptionMetricsAdapterConstruction:
    """ExceptionMetricsAdapter 构造函数测试"""

    def test_creates_internal_impl_instance(self) -> None:
        """构造函数应创建 ExceptionMetricsImpl 实例"""
        adapter = ExceptionMetricsAdapter()
        assert adapter._impl is not None

    def test_impl_is_exception_metrics_impl(self) -> None:
        """内部 _impl 应为 ExceptionMetricsImpl 类型"""
        from src.infrastructure.logging.exception_metrics_impl import ExceptionMetricsImpl

        adapter = ExceptionMetricsAdapter()
        assert isinstance(adapter._impl, ExceptionMetricsImpl)

    def test_multiple_constructions_create_separate_instances(self) -> None:
        """每次构造应创建独立的 _impl 实例"""
        adapter1 = ExceptionMetricsAdapter()
        adapter2 = ExceptionMetricsAdapter()
        assert adapter1._impl is not adapter2._impl


class TestExceptionMetricsAdapterDelegation:
    """ExceptionMetricsAdapter 委托行为测试"""

    def test_record_exception_delegates_to_impl(self) -> None:
        """record_exception 应委托到 _impl"""
        adapter = ExceptionMetricsAdapter()
        impl_mock = MagicMock()
        adapter._impl = impl_mock

        adapter.record_exception("ValueError")

        impl_mock.record_exception.assert_called_once_with("ValueError", None)

    def test_record_exception_with_code(self) -> None:
        """record_exception 含 code 参数应正确传递"""
        adapter = ExceptionMetricsAdapter()
        impl_mock = MagicMock()
        adapter._impl = impl_mock

        adapter.record_exception("ConnectionError", code="E001")

        impl_mock.record_exception.assert_called_once_with("ConnectionError", "E001")

    def test_record_exception_without_code_passes_none(self) -> None:
        """record_exception 不含 code 参数时应传递 None"""
        adapter = ExceptionMetricsAdapter()
        impl_mock = MagicMock()
        adapter._impl = impl_mock

        adapter.record_exception("RuntimeError")

        impl_mock.record_exception.assert_called_once_with("RuntimeError", None)

    def test_adapter_has_record_exception_method(self) -> None:
        """ExceptionMetricsAdapter 应具备 record_exception 方法"""
        adapter = ExceptionMetricsAdapter()
        assert hasattr(adapter, "record_exception")
        assert callable(adapter.record_exception)
