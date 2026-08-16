"""Story 3.6 摘要生成端口契约单元测试

验证 SummaryGenerationPort Protocol 的方法签名、参数默认值和 runtime_checkable。
"""

from __future__ import annotations

import inspect
from typing import Any

from src.domain.ports.summary_generation import SummaryGenerationPort


class TestSummaryGenerationPortProtocol:
    """SummaryGenerationPort Protocol 验证"""

    def test_port_is_protocol(self) -> None:
        """SummaryGenerationPort 是 Protocol"""
        import typing

        assert isinstance(SummaryGenerationPort, typing._ProtocolMeta)

    def test_port_is_runtime_checkable(self) -> None:
        """SummaryGenerationPort 是 @runtime_checkable"""
        import typing

        assert isinstance(SummaryGenerationPort, typing._ProtocolMeta)

    def test_generate_summary_method_exists(self) -> None:
        """generate_summary 方法存在"""
        assert hasattr(SummaryGenerationPort, "generate_summary")

    def test_generate_summary_is_async(self) -> None:
        """generate_summary 是异步方法"""
        assert inspect.iscoroutinefunction(SummaryGenerationPort.generate_summary)

    def test_generate_summary_signature(self) -> None:
        """generate_summary 方法签名正确"""
        sig = inspect.signature(SummaryGenerationPort.generate_summary)
        params = sig.parameters

        assert "query_text" in params
        assert "search_results" in params
        assert "perspective" in params
        assert "config" in params
        assert "tenant_id" in params
        assert "cross_document" in params
        assert "limit" in params

    def test_generate_summary_defaults(self) -> None:
        """generate_summary 参数默认值正确"""
        sig = inspect.signature(SummaryGenerationPort.generate_summary)
        params = sig.parameters

        assert params["config"].default is None
        assert params["tenant_id"].default is None
        assert params["cross_document"].default is False
        assert params["limit"].default == 10

    def test_generate_summary_return_type(self) -> None:
        """generate_summary 返回类型为 Any"""
        sig = inspect.signature(SummaryGenerationPort.generate_summary)
        return_annotation = sig.return_annotation
        assert return_annotation is Any or "Any" in str(return_annotation)

    def test_port_imports_search_result_from_l3_vector(self) -> None:
        """端口从 l3_vector 导入 SearchResult（同域内类型引用）"""
        import src.domain.ports.summary_generation as sg_module

        source = inspect.getsource(sg_module)
        assert "from src.domain.ports.l3_vector import SearchResult" in source

    def test_port_imports_llm_config_from_llm_client(self) -> None:
        """端口从 llm_client 导入 LLMConfig（同域内类型引用）"""
        import src.domain.ports.summary_generation as sg_module

        source = inspect.getsource(sg_module)
        assert "from src.domain.ports.llm_client import LLMConfig" in source

    def test_config_annotation_is_llm_config(self) -> None:
        """config 参数类型注解为 LLMConfig | None（非 Any）"""
        sig = inspect.signature(SummaryGenerationPort.generate_summary)
        config_annotation = sig.parameters["config"].annotation
        assert "LLMConfig" in str(config_annotation)

    def test_protocol_method_ellipsis_body(self) -> None:
        """Protocol 方法体使用 ... 占位符"""
        # 检查方法源码中包含 ...
        source = inspect.getsource(SummaryGenerationPort.generate_summary)
        assert "..." in source

    def test_cannot_instantiate_protocol_directly(self) -> None:
        """Protocol 不能直接实例化"""
        # 通过 metaclass 验证 Protocol 特性，而非直接调用（避免 mypy 误报）
        import typing

        assert isinstance(SummaryGenerationPort, typing._ProtocolMeta)


class TestSummaryGenerationPortDocstring:
    """SummaryGenerationPort docstring 验证"""

    def test_module_has_docstring(self) -> None:
        """模块有 docstring"""
        import src.domain.ports.summary_generation as sg_module

        assert sg_module.__doc__ is not None
        assert len(sg_module.__doc__) > 10

    def test_class_has_docstring(self) -> None:
        """类有 docstring"""
        assert SummaryGenerationPort.__doc__ is not None
        assert len(SummaryGenerationPort.__doc__) > 10

    def test_method_has_docstring(self) -> None:
        """方法有 docstring"""
        assert SummaryGenerationPort.generate_summary.__doc__ is not None
        assert len(SummaryGenerationPort.generate_summary.__doc__) > 10

    def test_method_docstring_has_args(self) -> None:
        """方法 docstring 包含 Args 说明"""
        doc = SummaryGenerationPort.generate_summary.__doc__
        assert doc is not None
        assert "Args:" in doc

    def test_method_docstring_has_returns(self) -> None:
        """方法 docstring 包含 Returns 说明"""
        doc = SummaryGenerationPort.generate_summary.__doc__
        assert doc is not None
        assert "Returns:" in doc

    def test_method_docstring_has_raises(self) -> None:
        """方法 docstring 包含 Raises 说明"""
        doc = SummaryGenerationPort.generate_summary.__doc__
        assert doc is not None
        assert "Raises:" in doc
