"""Story 6-10 - 顾问视图 VO 单元测试（五 VO 键契约 + 三常量 + 构造守卫 + frozen 纪律）.

覆盖面（Task 0.1 冻结表逐键对齐）：
    - 五 VO 键集 exact set：ConsultantView 5 / ProjectsSection 4 / ProjectSummary 6 /
      BrandSection 5 / ExportSection 7（投影白名单防扩散——实现禁增删键）；
    - 三常量值级：BRAND_STATUS_UNCONFIGURED / BRAND_FONT_STATUS /
      PANEL_ARCHIVE_LIMIT==1000（ArchiveQuery limit 覆写单源——默认 20 截断防御）；
    - 构造守卫 242 四形态（ProjectSummary：plan_id 非空字符串/latest_report_type
      值域 {None,"markdown","pdf"}/archive_count ≥0/latest_degraded_section_count
      ≥0 或 None；段级：plan_count 与导出双计数 ≥0——负例全枚举）；
    - frozen 断言（setattr FrozenInstanceError——6-9 R1-F9 mypy 教训直系）；
    - 空态/段降级共用默认值断言（键恒在纪律——None/0/() 降级值）。

Run with:
    poetry run pytest tests/unit/application/test_consultant_view_vos.py -v
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from src.domain.exceptions import EntityValidationError

# ===================================================================
# 工厂（**overrides 形态——6-9 VO 单测同款）
# ===================================================================


def _make_project_summary(**overrides: Any) -> Any:
    """合法 ProjectSummary 构造工厂（6 键投影白名单——行级概况形态）."""
    payload: dict[str, Any] = {
        "plan_id": "123e4567-e89b-12d3-a456-426614174000",
        "archive_count": 2,
        "latest_activity_at": "2026-11-08T10:00:00.000300+00:00",
        "latest_report_type": "pdf",
        "latest_report_at": "2026-11-08T10:00:00.000060+00:00",
        "latest_degraded_section_count": 2,
    }
    payload.update(overrides)
    from src.application.ports.consultant_view import ProjectSummary

    return ProjectSummary(**payload)


def _make_projects_section(**overrides: Any) -> Any:
    """合法 ProjectsSection 构造工厂（4 键段形态）."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "plan_count": 1,
        "projects": (_make_project_summary(),),
    }
    payload.update(overrides)
    from src.application.ports.consultant_view import ProjectsSection

    return ProjectsSection(**payload)


def _make_brand_section() -> Any:
    """BrandSection 构造工厂（零参——恒默认态构造即零 IO 静态段的测试面）."""
    from src.application.ports.consultant_view import BrandSection

    return BrandSection()


def _make_export_section(**overrides: Any) -> Any:
    """合法 ExportSection 构造工厂（7 键段形态）."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "plans_with_reports": 1,
        "plans_with_latest_pdf": 1,
        "latest_pdf_plan_id": "123e4567-e89b-12d3-a456-426614174000",
        "latest_pdf_object_key": "reports/plan/rid.pdf",
        "latest_pdf_generated_at": "2026-11-08T10:00:00.000060+00:00",
    }
    payload.update(overrides)
    from src.application.ports.consultant_view import ExportSection

    return ExportSection(**payload)


def _make_view(**overrides: Any) -> Any:
    """合法 ConsultantView 构造工厂（5 键顶层——顶层无 plan_id 键）."""
    payload: dict[str, Any] = {
        "generated_at": "2026-11-08T10:00:00+00:00",
        "build_degraded": False,
        "projects": _make_projects_section(),
        "brand": _make_brand_section(),
        "export": _make_export_section(),
    }
    payload.update(overrides)
    from src.application.ports.consultant_view import ConsultantView

    return ConsultantView(**payload)


# ===================================================================
# 三常量值级断言
# ===================================================================


class TestFrozenConstants:
    """三常量（品牌两常量+面板查询常量——Task 0.1 冻结）."""

    def test_brand_status_unconfigured_value(self) -> None:
        """BRAND_STATUS_UNCONFIGURED 值级（logo/color 共用——OD-6 品牌面恰两常量）."""
        from src.application.ports.consultant_view import BRAND_STATUS_UNCONFIGURED

        assert BRAND_STATUS_UNCONFIGURED == "未配置（系统默认）"

    def test_brand_font_status_value(self) -> None:
        """BRAND_FONT_STATUS 值级（与渲染器 _FONT_NAME :60 冻结字体事实单源对齐——字面量承载禁 import infra）."""
        from src.application.ports.consultant_view import BRAND_FONT_STATUS

        assert BRAND_FONT_STATUS == "STSong-Light（内置）"

    def test_panel_archive_limit_value(self) -> None:
        """PANEL_ARCHIVE_LIMIT==1000（ArchiveQuery limit 覆写单源——默认 20 截断防御）."""
        from src.application.ports.consultant_view import PANEL_ARCHIVE_LIMIT

        assert PANEL_ARCHIVE_LIMIT == 1000


# ===================================================================
# 五 VO 键集 exact set + 默认值
# ===================================================================


class TestVOKeyContracts:
    """五 VO 键集 exact set（Task 0.1 冻结表逐键——实现禁增删键）."""

    def test_consultant_view_five_keys(self) -> None:
        """ConsultantView 5 键（顶层无 plan_id 键——全局视图零输入 OD-1）."""
        from src.application.ports.consultant_view import ConsultantView

        assert {f.name for f in dataclasses.fields(ConsultantView)} == {
            "generated_at",
            "build_degraded",
            "projects",
            "brand",
            "export",
        }

    def test_projects_section_four_keys(self) -> None:
        """ProjectsSection 4 键（available/degraded/plan_count/projects）."""
        from src.application.ports.consultant_view import ProjectsSection

        assert {f.name for f in dataclasses.fields(ProjectsSection)} == {
            "available",
            "degraded",
            "plan_count",
            "projects",
        }

    def test_project_summary_six_keys(self) -> None:
        """ProjectSummary 6 键（投影白名单——generation_ms/metadata 不入）."""
        from src.application.ports.consultant_view import ProjectSummary

        assert {f.name for f in dataclasses.fields(ProjectSummary)} == {
            "plan_id",
            "archive_count",
            "latest_activity_at",
            "latest_report_type",
            "latest_report_at",
            "latest_degraded_section_count",
        }

    def test_brand_section_five_keys(self) -> None:
        """BrandSection 5 键（degraded 恒 False 零 IO 恒在段）."""
        from src.application.ports.consultant_view import BrandSection

        assert {f.name for f in dataclasses.fields(BrandSection)} == {
            "degraded",
            "configured",
            "logo_status",
            "color_scheme_status",
            "font_status",
        }

    def test_export_section_seven_keys(self) -> None:
        """ExportSection 7 键（latest 遮蔽口径计数+定位三键）."""
        from src.application.ports.consultant_view import ExportSection

        assert {f.name for f in dataclasses.fields(ExportSection)} == {
            "available",
            "degraded",
            "plans_with_reports",
            "plans_with_latest_pdf",
            "latest_pdf_plan_id",
            "latest_pdf_object_key",
            "latest_pdf_generated_at",
        }

    def test_empty_state_defaults(self) -> None:
        """空态/段降级共用默认值（零参构造断默认——键恒在纪律：plan_count 0+空 tuple+两计数 0+latest_pdf 三键 None）.

        零参裸构造形态（R1-F2）：段默认值是 find 级降级路径的 load-bearing 契约
        （服务 find 异常格裸构造 ProjectsSection(degraded=True)），显式传值再断言
        回读属恒真——改零参构造后默认值漂移（如 latest_pdf_plan_id 默认改非 None）即红。
        """
        from src.application.ports.consultant_view import ExportSection, ProjectsSection

        projects = ProjectsSection()
        assert projects.available is False
        assert projects.degraded is False
        assert projects.plan_count == 0
        assert projects.projects == ()

        export = ExportSection()
        assert export.available is False
        assert export.degraded is False
        assert export.plans_with_reports == 0
        assert export.plans_with_latest_pdf == 0
        assert export.latest_pdf_plan_id is None
        assert export.latest_pdf_object_key is None
        assert export.latest_pdf_generated_at is None

    def test_brand_section_defaults(self) -> None:
        """BrandSection 零参构造恒默认态（V1 时点事实——configured False+三 status 常量）."""
        brand = _make_brand_section()
        assert brand.degraded is False
        assert brand.configured is False
        assert brand.logo_status == "未配置（系统默认）"
        assert brand.color_scheme_status == "未配置（系统默认）"
        assert brand.font_status == "STSong-Light（内置）"


# ===================================================================
# 构造守卫 242（负例全枚举——四形态）
# ===================================================================


class TestConstructionGuards:
    """构造守卫（VO 不变量面——违例抛 EntityValidationError 242）."""

    def test_project_summary_empty_plan_id_rejected(self) -> None:
        """守卫形态①：plan_id 空字符串拒绝."""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_project_summary(plan_id="")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_project_summary_non_string_plan_id_rejected(self) -> None:
        """守卫形态①b：plan_id 非字符串拒绝."""
        with pytest.raises(EntityValidationError):
            _make_project_summary(plan_id=12345)

    def test_project_summary_report_type_out_of_domain(self) -> None:
        """守卫形态②：latest_report_type 值域外拒绝（值域 {None,"markdown","pdf"}——frozenset 单源）."""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_project_summary(latest_report_type="branded_pdf")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_project_summary_report_type_domain_members_accepted(self) -> None:
        """值域三成员全通过（None/markdown/pdf——6-11 新类型红是预期演进信号对称注记）."""
        for value in (None, "markdown", "pdf"):
            assert _make_project_summary(latest_report_type=value).latest_report_type == value

    def test_project_summary_negative_archive_count_rejected(self) -> None:
        """守卫形态③：archive_count 负值拒绝."""
        with pytest.raises(EntityValidationError):
            _make_project_summary(archive_count=-1)

    def test_project_summary_negative_degraded_section_count_rejected(self) -> None:
        """守卫形态④：latest_degraded_section_count 负值拒绝（None 合法）."""
        with pytest.raises(EntityValidationError):
            _make_project_summary(latest_degraded_section_count=-1)
        assert _make_project_summary(latest_degraded_section_count=None).latest_degraded_section_count is None

    def test_projects_section_negative_plan_count_rejected(self) -> None:
        """段级守卫：plan_count 负值拒绝."""
        with pytest.raises(EntityValidationError):
            _make_projects_section(plan_count=-1)

    def test_export_section_negative_counts_rejected(self) -> None:
        """段级守卫：导出双计数负值拒绝."""
        with pytest.raises(EntityValidationError):
            _make_export_section(plans_with_reports=-1)
        with pytest.raises(EntityValidationError):
            _make_export_section(plans_with_latest_pdf=-1)


# ===================================================================
# frozen 纪律 + Protocol 契约
# ===================================================================


class TestDataclassDiscipline:
    """frozen dataclass 纪律（setattr 拒绝）+ Protocol runtime_checkable."""

    def test_frozen_setattr_rejected(self) -> None:
        """五 VO 全 frozen（FrozenInstanceError——6-9 R1-F9 mypy 教训直系）."""
        import contextlib

        for obj in (
            _make_view(),
            _make_projects_section(),
            _make_project_summary(),
            _make_brand_section(),
            _make_export_section(),
        ):
            with contextlib.suppress(AttributeError):  # 无属性对象 setattr 前置检查差异防御
                with pytest.raises(dataclasses.FrozenInstanceError):
                    setattr(obj, "degraded" if hasattr(obj, "degraded") else "plan_id", "mutated")

    def test_port_runtime_checkable(self) -> None:
        """ConsultantViewPort runtime_checkable（AsyncMock spec=Port 契约面）."""
        from src.application.ports.consultant_view import ConsultantViewPort

        assert hasattr(ConsultantViewPort, "build_consultant_view")

    def test_port_method_signature_zero_param(self) -> None:
        """端口方法零参签名（build_consultant_view()=={self}——全局视图 OD-1 与 6-8/6-9 keyword-only 分立）."""
        import inspect

        from src.application.ports.consultant_view import ConsultantViewPort

        signature = inspect.signature(ConsultantViewPort.build_consultant_view)
        assert set(signature.parameters.keys()) == {"self"}, "零参数签名（全局视图——顶层无 plan_id 输入面）"
