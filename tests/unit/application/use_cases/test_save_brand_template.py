"""SaveBrandTemplateUseCase 单元测试（Story 6-11 Task 5——透传/异常传播/架构注记）。

覆盖面：
- 参数透传（四参 keyword-only 值级断言——CLI→用例→服务传递链）
- 异常传播（494/242 不吞不包装）
- 架构注记测试（getsource 零 EntityValidationError 字样——6-10 :62-69 直系）

Run with:
    poetry run pytest tests/unit/application/use_cases/test_save_brand_template.py -v
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.brand_template import BrandTemplateServicePort
from src.application.use_cases.save_brand_template import SaveBrandTemplateUseCase
from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateValidationError


def _make_template(**overrides: Any) -> BrandTemplate:
    """模板实体构造 helper。"""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "template_id": uuid.uuid4(),
        "name": "test-模板",
        "color_scheme": "corporate-blue",
        "font_preset": "stsong",
    }
    defaults.update(overrides)
    return BrandTemplate(created_at=now, updated_at=now, **defaults)


def _make_use_case(**overrides: Any) -> tuple[SaveBrandTemplateUseCase, AsyncMock]:
    """构造被测用例（服务端口 AsyncMock——mock 仅限单测层纪律）。"""
    service = AsyncMock(spec=BrandTemplateServicePort)
    service.save_brand_template.return_value = _make_template()
    for key, value in overrides.items():
        setattr(service, key, value)
    return SaveBrandTemplateUseCase(brand_service=service), service


class TestSaveBrandTemplateUseCase:
    """用例三面（透传/异常传播/架构注记）。"""

    async def test_full_params_passthrough(self, tmp_path: Any) -> None:
        """四参 keyword-only 透传（name/color_scheme/font_preset/logo_path
        值级断言——await_once_with）。"""
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG\r\n\x1a\nstub")
        use_case, service = _make_use_case()
        await use_case.execute(
            name="商务蓝模板", color_scheme="corporate-blue", font_preset="noto-sans-sc", logo_path=str(logo)
        )
        service.save_brand_template.assert_awaited_once_with(
            name="商务蓝模板",
            color_scheme="corporate-blue",
            font_preset="noto-sans-sc",
            logo_path=str(logo),
        )

    async def test_logo_optional_passthrough(self) -> None:
        """logo_path 可选（缺省 None 透传——CLI 未传时）。"""
        use_case, service = _make_use_case()
        await use_case.execute(name="无 Logo", color_scheme="graphite", font_preset="stsong")
        service.save_brand_template.assert_awaited_once_with(
            name="无 Logo", color_scheme="graphite", font_preset="stsong", logo_path=None
        )

    async def test_validation_error_propagates(self) -> None:
        """494 传播（非法预设键——不吞不包装）。"""
        use_case, service = _make_use_case()
        service.save_brand_template.side_effect = BrandTemplateValidationError(
            field="color_scheme", message="color_scheme 必须为预设键之一"
        )
        with pytest.raises(BrandTemplateValidationError):
            await use_case.execute(name="x", color_scheme="neon", font_preset="stsong")

    async def test_returns_entity(self) -> None:
        """返回服务产物（模板实体透传）。"""
        template = _make_template(name="返回值")
        use_case, service = _make_use_case()
        service.save_brand_template.return_value = template
        result = await use_case.execute(name="返回值", color_scheme="graphite", font_preset="stsong")
        assert result is template

    def test_architecture_note_source_clean(self) -> None:
        """架构注记测试（getsource 零 EntityValidationError 构造字样——值域/
        格式校验归服务层非用例层；6-10 :62-69 直系注记锚形态）。"""
        import inspect

        source = inspect.getsource(SaveBrandTemplateUseCase)
        assert "raise EntityValidationError" not in source, "用例层不应构造 242（校验归服务层）"
