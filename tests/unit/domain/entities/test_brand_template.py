"""BrandTemplate 实体单元测试（Story 6-11 Task 1 循环 A——白标报告基础）。

覆盖面：
- 7 字段构造（Task 0.1 冻结表逐键——template_id/name/color_scheme/font_preset/
  logo_object_key/created_at/updated_at）
- 默认值（template_id uuid4 工厂/三可空字段 None——应用侧定时戳责任位 OD-12：
  created_at/updated_at 默认 None 诚实反映「服务是唯一定时戳源」，仓储层 None
  落库撞 NOT NULL 由 IntegrityError→495 路径承载防御）
- frozen setattr 拒绝（值对象不可变纪律）
- ``__post_init__`` 242 守卫负例全枚举（name 非空且 ≤100/color_scheme、
  font_preset 非空且 ≤30——domain 契约面；预设 key 值域校验落应用服务的
  依赖方向注记[domain 实体零 application import]）

Run with:
    poetry run pytest tests/unit/domain/entities/test_brand_template.py -v
"""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import EntityValidationError


class TestBrandTemplateConstruction:
    """构造与默认值（7 字段冻结表）。"""

    def test_full_construction_seven_fields(self) -> None:
        """全参构造 7 字段值级直推（模板标识/名称/配色/字体/Logo 键/双时间戳）。"""
        template_id = uuid.uuid4()
        now = datetime.now(UTC)
        template = BrandTemplate(
            template_id=template_id,
            name="商务蓝模板",
            color_scheme="corporate-blue",
            font_preset="noto-sans-sc",
            logo_object_key=f"logos/{template_id}",
            created_at=now,
            updated_at=now,
        )
        assert template.template_id == template_id
        assert template.name == "商务蓝模板"
        assert template.color_scheme == "corporate-blue"
        assert template.font_preset == "noto-sans-sc"
        assert template.logo_object_key == f"logos/{template_id}"
        assert template.created_at == now
        assert template.updated_at == now

    def test_defaults_template_id_factory(self) -> None:
        """默认 template_id（uuid4 工厂——首次新建生成，同名修订由服务保留原值）。"""
        template = BrandTemplate(name="默认形态", color_scheme="graphite", font_preset="stsong")
        assert isinstance(template.template_id, uuid.UUID)

    def test_defaults_nullable_fields_none(self) -> None:
        """可空字段默认 None（logo 可缺席——配色/字体独立生效；双时间戳 None
        是应用侧定时戳责任位的诚实形态——服务构造实体时显式定值）。"""
        template = BrandTemplate(name="无 Logo 模板", color_scheme="burgundy", font_preset="stsong")
        assert template.logo_object_key is None
        assert template.created_at is None
        assert template.updated_at is None

    def test_frozen_setattr_raises(self) -> None:
        """frozen dataclass setattr 拒绝（值对象不可变——修订走新构造非原地变；
        先例形态：test_acceptance_agent_evaluation.py:766 裸赋值无抑制注释）。"""
        template = BrandTemplate(name="冻结态", color_scheme="graphite", font_preset="stsong")
        with pytest.raises(FrozenInstanceError):
            # 内建 setattr 通道（mypy 只读检查豁免内建——运行时 frozen __setattr__ 仍拦）
            setattr(template, "name", "改名")


class TestBrandTemplateGuards:
    """``__post_init__`` 242 守卫负例全枚举（domain 契约面）。"""

    def test_empty_name_raises_242(self) -> None:
        """空 name 拒绝（模板名非空——CLI 呈现与 get_by_name 锚）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            BrandTemplate(name="", color_scheme="graphite", font_preset="stsong")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "name"

    def test_blank_name_raises_242(self) -> None:
        """纯空白 name 拒绝（strip 判空——与 StrategicReport.plan_id 同款形态）。"""
        with pytest.raises(EntityValidationError):
            BrandTemplate(name="   ", color_scheme="graphite", font_preset="stsong")

    def test_name_over_100_raises_242(self) -> None:
        """name 超 100 字符拒绝（DDL VARCHAR(100) 对齐）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            BrandTemplate(name="长" * 101, color_scheme="graphite", font_preset="stsong")
        assert exc_info.value.context["field"] == "name"

    def test_name_exactly_100_passes(self) -> None:
        """name 恰 100 字符边界绿（≤100 含边界）。"""
        template = BrandTemplate(name="名" * 100, color_scheme="graphite", font_preset="stsong")
        assert len(template.name) == 100

    def test_empty_color_scheme_raises_242(self) -> None:
        """空 color_scheme 拒绝。"""
        with pytest.raises(EntityValidationError) as exc_info:
            BrandTemplate(name="模板", color_scheme="", font_preset="stsong")
        assert exc_info.value.context["field"] == "color_scheme"

    def test_color_scheme_over_30_raises_242(self) -> None:
        """color_scheme 超 30 字符拒绝（DDL VARCHAR(30) 对齐）。"""
        with pytest.raises(EntityValidationError):
            BrandTemplate(name="模板", color_scheme="c" * 31, font_preset="stsong")

    def test_color_scheme_exactly_30_passes(self) -> None:
        """color_scheme 恰 30 字符边界绿。"""
        template = BrandTemplate(name="模板", color_scheme="c" * 30, font_preset="stsong")
        assert len(template.color_scheme) == 30

    def test_empty_font_preset_raises_242(self) -> None:
        """空 font_preset 拒绝。"""
        with pytest.raises(EntityValidationError) as exc_info:
            BrandTemplate(name="模板", color_scheme="graphite", font_preset="")
        assert exc_info.value.context["field"] == "font_preset"

    def test_font_preset_over_30_raises_242(self) -> None:
        """font_preset 超 30 字符拒绝。"""
        with pytest.raises(EntityValidationError):
            BrandTemplate(name="模板", color_scheme="graphite", font_preset="f" * 31)

    def test_preset_key_domain_not_guarded_here(self) -> None:
        """预设 key 值域（∈ 三键/两键）不在实体守卫面——值域校验落应用服务
        （依赖方向矩阵：domain 实体零 application import；非法 key 经
        SaveBrandTemplateUseCase 直调抛 494——AC-1/AC-7 口径）。"""
        # 长度与空串守卫内、值域外的构造在此绿（服务层校验前可构造）
        template = BrandTemplate(name="模板", color_scheme="neon-pink", font_preset="comic-sans")
        assert template.color_scheme == "neon-pink"
