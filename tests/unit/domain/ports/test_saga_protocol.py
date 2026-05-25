"""Saga Protocol 接口契约测试

验证 SagaStep 和 SagaRepositoryProtocol 的运行时检查行为
测试 Protocol 定义的 docstring 和签名

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from src.domain.ports.saga import SagaRepositoryProtocol, SagaStep
from src.domain.ports.saga_context import SagaContext
from src.domain.ports.saga_status import SagaStatus


class ValidSagaStep:
    """符合 SagaStep Protocol 的有效实现"""

    def __init__(self, step_name: str = "TestStep") -> None:
        self._name = step_name

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, context: SagaContext) -> SagaContext:
        return context

    async def compensate(self, context: SagaContext) -> SagaContext:
        return context


class ValidSagaRepository:
    """符合 SagaRepositoryProtocol 的有效实现"""

    async def save(self, context: SagaContext) -> None:
        pass

    async def load(self, saga_id: str) -> SagaContext | None:
        return None

    async def update_status(self, saga_id: str, status: SagaStatus) -> None:
        pass


class InvalidSagaStep:
    """不符合 SagaStep Protocol 的无效实现（缺少方法）"""

    @property
    def name(self) -> str:
        return "InvalidStep"


class TestSagaStepProtocol:
    """SagaStep Protocol 契约测试"""

    def test_saga_step_is_runtime_checkable(self) -> None:
        """SagaStep 应是 runtime_checkable Protocol"""
        # runtime_checkable Protocol 可以通过 isinstance 检查
        valid_step = ValidSagaStep()
        assert isinstance(valid_step, SagaStep)

    def test_valid_implementation_passes_isinstance(self) -> None:
        """ValidSagaStep 应通过 isinstance 检查"""
        valid_step = ValidSagaStep()
        assert isinstance(valid_step, SagaStep)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        """InvalidSagaStep（缺少方法）应失败 isinstance 检查"""
        invalid_step = InvalidSagaStep()
        assert not isinstance(invalid_step, SagaStep)

    def test_name_property_is_accessible(self) -> None:
        """SagaStep.name 属性应在 Protocol 定义中可访问"""
        assert hasattr(SagaStep, "name")

    def test_execute_method_is_callable(self) -> None:
        """SagaStep.execute 方法应在 Protocol 中可访问"""
        assert hasattr(SagaStep, "execute")

    def test_compensate_method_is_callable(self) -> None:
        """SagaStep.compensate 方法应在 Protocol 中可访问"""
        assert hasattr(SagaStep, "compensate")

    def test_docstrings_are_defined(self) -> None:
        """SagaStep Protocol 方法应有 docstring"""
        # 访问 Protocol 属性的 __doc__
        name_doc = SagaStep.name.__doc__
        assert name_doc is not None
        assert "步骤唯一名称" in name_doc or name_doc != ""

        execute_doc = SagaStep.execute.__doc__
        assert execute_doc is not None
        assert execute_doc != ""


class TestSagaRepositoryProtocol:
    """SagaRepositoryProtocol 契约测试"""

    def test_saga_repository_is_runtime_checkable(self) -> None:
        """SagaRepositoryProtocol 应是 runtime_checkable Protocol"""
        # runtime_checkable Protocol 可以通过 isinstance 检查
        valid_repo = ValidSagaRepository()
        assert isinstance(valid_repo, SagaRepositoryProtocol)

    def test_valid_repository_passes_isinstance(self) -> None:
        """ValidSagaRepository 应通过 isinstance 检查"""
        valid_repo = ValidSagaRepository()
        assert isinstance(valid_repo, SagaRepositoryProtocol)

    def test_save_method_is_callable(self) -> None:
        """SagaRepositoryProtocol.save 方法应在 Protocol 中可访问"""
        assert hasattr(SagaRepositoryProtocol, "save")

    def test_load_method_is_callable(self) -> None:
        """SagaRepositoryProtocol.load 方法应在 Protocol 中可访问"""
        assert hasattr(SagaRepositoryProtocol, "load")

    def test_update_status_method_is_callable(self) -> None:
        """SagaRepositoryProtocol.update_status 方法应在 Protocol 中可访问"""
        assert hasattr(SagaRepositoryProtocol, "update_status")

    def test_docstrings_are_defined(self) -> None:
        """SagaRepositoryProtocol Protocol 方法应有 docstring"""
        save_doc = SagaRepositoryProtocol.save.__doc__
        assert save_doc is not None
        assert save_doc != ""

        load_doc = SagaRepositoryProtocol.load.__doc__
        assert load_doc is not None
        assert load_doc != ""

        update_doc = SagaRepositoryProtocol.update_status.__doc__
        assert update_doc is not None
        assert update_doc != ""
