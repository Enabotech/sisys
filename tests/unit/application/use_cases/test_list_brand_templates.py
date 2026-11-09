"""ListBrandTemplatesUseCase 单元测试（Story 6-11 Task 5——零参透传/异常传播）。

Run with:
    poetry run pytest tests/unit/application/use_cases/test_list_brand_templates.py -v
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.brand_template import BrandTemplateServicePort
from src.application.use_cases.list_brand_templates import ListBrandTemplatesUseCase
from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateStorageError


def _make_rows(count: int = 2) -> list[BrandTemplate]:
    """模板行清单构造 helper。"""
    now = datetime.now(UTC)
    return [
        BrandTemplate(
            template_id=uuid.uuid4(),
            name=f"test-{index}-模板",
            color_scheme="graphite",
            font_preset="stsong",
            created_at=now,
            updated_at=now,
        )
        for index in range(count)
    ]


def _make_use_case(**overrides: Any) -> tuple[ListBrandTemplatesUseCase, AsyncMock]:
    """构造被测用例（服务端口 AsyncMock）。"""
    service = AsyncMock(spec=BrandTemplateServicePort)
    service.list_brand_templates.return_value = tuple(_make_rows())
    for key, value in overrides.items():
        setattr(service, key, value)
    return ListBrandTemplatesUseCase(brand_service=service), service


class TestListBrandTemplatesUseCase:
    """用例三面（零参透传/异常传播/返回）。"""

    async def test_zero_args_passthrough(self) -> None:
        """零参透传（全局模板清单——CLI 族第二个零参数命令）。"""
        use_case, service = _make_use_case()
        await use_case.execute()
        service.list_brand_templates.assert_awaited_once_with()

    async def test_returns_tuple(self) -> None:
        """返回服务产物（tuple 化清单透传）。"""
        rows = tuple(_make_rows(3))
        use_case, service = _make_use_case()
        service.list_brand_templates.return_value = rows
        result = await use_case.execute()
        assert result is rows and len(result) == 3

    async def test_storage_error_propagates(self) -> None:
        """495 传播（PG 读写失败——不吞不包装）。"""
        use_case, service = _make_use_case()
        service.list_brand_templates.side_effect = BrandTemplateStorageError(layer="l2")
        with pytest.raises(BrandTemplateStorageError):
            await use_case.execute()

    async def test_empty_tuple_state(self) -> None:
        """空清单透传（零模板空态——CLI 空态呈现的数据面前提）。"""
        use_case, service = _make_use_case()
        service.list_brand_templates.return_value = ()
        result = await use_case.execute()
        assert result == ()
