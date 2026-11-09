"""渲染器品牌应用单元测试（Story 6-11 Task 3——白标 PDF 渲染三件）。

覆盖面：
- BrandRenderSpec 7 键契约（Task 0.1 冻结表逐键+frozen+hex 格式 242 守卫+
  五色键+font_name 必填构造契约[缺省构造 TypeError——防默认值与渲染器默认
  参数同值致等价突变锚失效]+logo 默认 None）
- ``PdfRendererPort.render`` v1.1.0 双参签名（keyword-only brand 可选默认 None
  ——既有单参调用零破坏）
- 品牌应用三件：字体（TTF 注册后产物字体资源含注册名/``_style`` base
  fontName spy）、配色（五色键逐色驱动——callout 双色/表头底/网格线/标题色
  经产物内容流 fp_str 格式期望串）、Logo（首页 Image XObject 在场/缺席零流）
- TTF 注册幂等（双 render 不炸——``_FONT_REGISTERED`` 字典化后多字体各自幂等）
- 默认态等价（循环 C）：``rl_config.invariant=1`` 测试前置下
  ``render(doc) == render(doc, brand=None)`` 逐字节——v1.1.0 向后兼容的
  运行面证据（6-5b 契约冻结面）

渲染正例 Logo 用 Pillow 生成最小合法 PNG（仓内既有 PNG 测试字节是截断假体：
magic 8 字节可过守卫但 ImageReader 渲染 492）；magic 负例用文本字节。

Run with:
    poetry run pytest tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer_brand.py -v
"""

import dataclasses
import inspect
import io
from typing import Any, TypedDict

import pytest

from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)

# ======================================================================
# 文档构造 helper（6-5b 测试 _make_document 精简复刻——callout 与 table 双在场
# 覆盖四色参数化面）
# ======================================================================


def _make_document() -> MarkdownReportDocument:
    """构造品牌测试样例文档（表格+callout+bullet 三块型在场）。"""
    sections = (
        ReportSection(
            title="1 业绩差距分析",
            level=2,
            blocks=(
                ReportBlock(
                    kind="table",
                    headers=("维度", "评估"),
                    rows=(("财务", "营收达成率 82%"), ("运营", "交付周期延长")),
                ),
                ReportBlock(kind="bullet_list", items=("短期：平台化架构降本",)),
            ),
        ),
        ReportSection(
            title="1.1 财务差距",
            level=3,
            blocks=(ReportBlock(kind="paragraph", text="财务差距量化：营收达成率 82%"),),
        ),
        ReportSection(
            title="附录 B 降级与数据缺失记录",
            level=2,
            blocks=(ReportBlock(kind="table", headers=("类型", "步骤", "原因"), rows=()),),
        ),
        ReportSection(
            title="附录 C 引文索引",
            level=2,
            blocks=(ReportBlock(kind="callout", text="本报告无检索证据引用"),),
        ),
    )
    return MarkdownReportDocument(
        plan_id="0b6a6c2e-6f4e-4a3b-9c2d-1e2f3a4b5c6d",
        title="战略规划报告（白标品牌测试）",
        meta_rows=(("规划任务", "制定五年战略规划"),),
        sections=sections,
        toc_enabled=True,
    )


#: graphite 配色套五色（Task 0.2 冻结表钦定 hex——与渲染器默认四色互斥已数学验证；
#: TypedDict 键集精确收窄——`**dict[str, str]` 展开形态下 mypy 无法排除 logo
#: 键覆盖[bytes | None]，键集 TypedDict 使构造契约负例（缺键 TypeError）类型干净）
class _SpecColors(TypedDict):
    """五色键 TypedDict（BrandRenderSpec 五色键一一对应——零 logo 键）。"""

    title_color: str
    header_bg_color: str
    grid_color: str
    callout_bg_color: str
    callout_text_color: str


_SPEC_COLORS: _SpecColors = {
    "title_color": "#37474F",
    "header_bg_color": "#ECEFF1",
    "grid_color": "#B0BEC5",
    "callout_bg_color": "#F5F7F8",
    "callout_text_color": "#455A64",
}

#: TTF 注册名（noto-sans-sc 预设——FONT_PRESETS 供给）
_TTF_FONT_NAME = "NotoSansSC"


def _make_spec(**overrides: Any) -> Any:
    """BrandRenderSpec 构造 helper（graphite 套+noto 字体；logo 默认 None）。"""
    from src.application.ports.pdf_report import BrandRenderSpec

    fields: dict[str, Any] = {"font_name": _TTF_FONT_NAME, **_SPEC_COLORS, "logo": None}
    fields.update(overrides)
    return BrandRenderSpec(**fields)


def _make_logo_png_bytes() -> bytes:
    """Pillow 生成最小合法 PNG bytes（渲染正例——可解码性前提）。"""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=(55, 71, 79)).save(buffer, format="PNG")
    return buffer.getvalue()


def _render_brand(document: MarkdownReportDocument, brand: Any) -> bytes:
    """品牌渲染入口（v1.1.0 双参——被测主通道）。"""
    from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

    return ReportLabPdfRenderer().render(document, brand=brand)


def _read_pdf(pdf_bytes: bytes) -> Any:
    """pypdf 读回（产物解析断言通道）。"""
    from pypdf import PdfReader

    return PdfReader(io.BytesIO(pdf_bytes))


def _content_stream(reader: Any) -> bytes:
    """全页内容流拼接（品牌色 fp_str 检索面）。"""
    return b"".join(page.get_contents().get_data() for page in reader.pages)


def _base_fonts(reader: Any) -> list[str]:
    """全页字体资源 BaseFont 名清单（品牌字体在场断言面）。"""
    names: list[str] = []
    for page in reader.pages:
        fonts = page.get("/Resources", {}).get("/Font", {})
        for font in fonts.values():
            names.append(str(font.get_object().get("/BaseFont", "")))
    return names


# ======================================================================
# 循环 A：BrandRenderSpec VO 契约 + render v1.1.0 签名
# ======================================================================


class TestBrandRenderSpecContract:
    """BrandRenderSpec 7 键冻结契约（Task 0.1——实现禁增删键）。"""

    def test_seven_keys_exact_order(self) -> None:
        """7 键 exact set+字段序（font_name/五色键序/logo 尾位）。"""
        from src.application.ports.pdf_report import BrandRenderSpec

        names = [f.name for f in dataclasses.fields(BrandRenderSpec)]
        assert names == [
            "font_name",
            "title_color",
            "header_bg_color",
            "grid_color",
            "callout_bg_color",
            "callout_text_color",
            "logo",
        ]

    def test_frozen_setattr_raises(self) -> None:
        """frozen dataclass setattr 拒绝（值对象不可变——同 spec 恒同产物前提）。"""
        from dataclasses import FrozenInstanceError

        spec = _make_spec()
        with pytest.raises(FrozenInstanceError):
            spec.font_name = "别的字体"

    @pytest.mark.parametrize("color_key", list(_SPEC_COLORS))
    def test_hex_guard_raises_242(self, color_key: str) -> None:
        """五色键 6 位 hex 格式守卫（``^#[0-9A-Fa-f]{6}$``——242 application VO
        先例[consultant_view.py:66-91 等六文件]；参数化逐键）。"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError) as exc_info:
            _make_spec(**{color_key: "not-a-hex"})
        assert exc_info.value.code == "EXCEPTION_242"

    def test_font_name_required_constructor(self) -> None:
        """font_name 必填（缺省构造 TypeError——构造契约：五色键+font_name
        必填即判别保证，默认值不得与渲染器默认参数同值是等价突变锚的判别前提）。"""
        from src.application.ports.pdf_report import BrandRenderSpec

        spec_cls: Any = BrandRenderSpec  # 负例构造走 Any 擦除通道（test_agent_exceptions :481 先例——故意缺参 mypy 必拦）
        with pytest.raises(TypeError):
            spec_cls(**_SPEC_COLORS)

    def test_color_keys_required_constructor(self) -> None:
        """五色键必填（缺任一色键构造 TypeError）。"""
        from src.application.ports.pdf_report import BrandRenderSpec

        spec_cls: Any = BrandRenderSpec  # 同上——负例构造擦除通道
        incomplete = dict(_SPEC_COLORS)
        incomplete.pop("grid_color")
        with pytest.raises(TypeError):
            spec_cls(font_name=_TTF_FONT_NAME, **incomplete)

    def test_logo_default_none_and_bytes_state(self) -> None:
        """logo 唯一可选默认 None；bytes 形态可构造（两态）。"""
        assert _make_spec().logo is None
        with_logo = _make_spec(logo=b"\x89PNG\r\n\x1a\n...")
        assert with_logo.logo == b"\x89PNG\r\n\x1a\n..."


class TestRenderSignatureV110:
    """render v1.1.0 签名（keyword-only brand 可选——既有单参调用零破坏）。"""

    def test_signature_parameter_keys(self) -> None:
        """参数键集 == {self, document, brand}（brand KEYWORD_ONLY+默认 None）。"""
        from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

        signature = inspect.signature(ReportLabPdfRenderer.render)
        assert set(signature.parameters.keys()) == {"self", "document", "brand"}
        brand_param = signature.parameters["brand"]
        assert brand_param.kind is inspect.Parameter.KEYWORD_ONLY
        assert brand_param.default is None

    def test_single_argument_call_unchanged(self) -> None:
        """既有单参调用零破坏（render(document) 路径——v1.0.0 兼容运行面）。"""
        from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

        pdf_bytes = ReportLabPdfRenderer().render(_make_document())
        assert pdf_bytes.startswith(b"%PDF")


# ======================================================================
# 循环 B：渲染器品牌应用三件（字体/配色/Logo）
# ======================================================================


class TestBrandFontApplication:
    """字体参数化（CID 直用/TTF 注册——spec.font_name 驱动 _style base fontName）。"""

    def test_brand_font_in_product_resources(self) -> None:
        """TTF 字体注册后产物字体资源含注册名 NotoSansSC（与默认 STSong-Light
        互斥可判别——黑体形态承载断言；stsong 与默认同字体恒真不可判别）。"""
        pdf_bytes = _render_brand(_make_document(), _make_spec())
        base_fonts = _base_fonts(_read_pdf(pdf_bytes))
        assert any(_TTF_FONT_NAME in name for name in base_fonts), f"NotoSansSC 不在字体资源: {base_fonts}"

    def test_style_base_font_name_spy(self) -> None:
        """``_style`` base fontName==spec 值（单元级直判——品牌态下构造的样式
        全程品牌字体；渲染上下文外手动置态后断言）。"""
        from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

        renderer = ReportLabPdfRenderer()
        renderer._brand = _make_spec()
        style = renderer._style("body")
        assert style.fontName == _TTF_FONT_NAME
        renderer._brand = None
        assert renderer._style("body").fontName != _TTF_FONT_NAME

    def test_ttf_register_idempotent_double_render(self, monkeypatch: pytest.MonkeyPatch, _invariant_rl_config: None) -> None:
        """TTF 注册幂等（双 render byte 级相等——``_FONT_REGISTERED`` 字典化后
        同名重复注册跳过；R1-F10 补强：首渲染注册/次渲染跳过两路径产物等价，
        `%PDF` 前缀冒烟级断言不构成幂等主张的证据）。

        前置：invariant=1（byte 对照结构性前提）+ ``_FONT_REGISTERED`` 置空
        （模块级注册字典跨测试持久——前序测试已注册则双渲染均走跳过路径，
        注册→跳过语义空转；TestDefaultStateEquivalence 同款隔离先例）。
        """
        import src.infrastructure.reporting.reportlab_pdf_renderer as renderer_module

        monkeypatch.setattr(renderer_module, "_FONT_REGISTERED", {})
        first = _render_brand(_make_document(), _make_spec())
        second = _render_brand(_make_document(), _make_spec())
        assert first.startswith(b"%PDF") and second.startswith(b"%PDF")
        assert first == second, "首渲染（注册）与次渲染（跳过）产物应 byte 级相等"


class TestBrandColorApplication:
    """配色参数化（五色键逐色驱动——产物内容流 fp_str 格式期望串）。"""

    def test_callout_colors_in_content_stream(self) -> None:
        """callout 双色（textColor+底色——graphite 套与默认四色互斥判别）。"""
        from reportlab.lib.rl_accel import fp_str

        pdf_bytes = _render_brand(_make_document(), _make_spec())
        content = _content_stream(_read_pdf(pdf_bytes))
        text_rgb = fp_str(0x45 / 255, 0x5A / 255, 0x64 / 255)  # callout_text #455A64
        bg_rgb = fp_str(0xF5 / 255, 0xF7 / 255, 0xF8 / 255)  # callout_bg #F5F7F8
        assert text_rgb.encode("latin-1") in content, f"callout 文字色 {text_rgb} 不在内容流"
        assert bg_rgb.encode("latin-1") in content, f"callout 底色 {bg_rgb} 不在内容流"

    def test_table_header_and_grid_colors(self) -> None:
        """表头底+网格线（fp_str 期望串——reportlab 内容流色值格式，直拼
        ``f'{r/255:.6f}'`` 恒不中）。"""
        from reportlab.lib.rl_accel import fp_str

        pdf_bytes = _render_brand(_make_document(), _make_spec())
        content = _content_stream(_read_pdf(pdf_bytes))
        header_rgb = fp_str(0xEC / 255, 0xEF / 255, 0xF1 / 255)  # header_bg #ECEFF1
        assert header_rgb.encode("latin-1") in content, f"表头底色 {header_rgb} 不在内容流"
        # 网格线色（stroke——``RG`` 大写算子族）：graphite #B0BEC5
        grid_rgb = fp_str(0xB0 / 255, 0xBE / 255, 0xC5 / 255)
        assert grid_rgb.encode("latin-1") in content, f"网格线色 {grid_rgb} 不在内容流"

    def test_title_color_in_content_stream(self) -> None:
        """标题色新能力（H1/H2 标题文字色——现 _style base 无 textColor 默认黑；
        graphite title #37474F 判别）。"""
        from reportlab.lib.rl_accel import fp_str

        pdf_bytes = _render_brand(_make_document(), _make_spec())
        content = _content_stream(_read_pdf(pdf_bytes))
        title_rgb = fp_str(0x37 / 255, 0x47 / 255, 0x4F / 255)  # title #37474F
        assert title_rgb.encode("latin-1") in content, f"标题色 {title_rgb} 不在内容流"

    def test_default_colors_when_brand_none(self) -> None:
        """brand=None 四色走原值（默认四色在内容流——#F2F2F2 callout 底对照）。"""
        from reportlab.lib.rl_accel import fp_str

        from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

        pdf_bytes = ReportLabPdfRenderer().render(_make_document())
        content = _content_stream(_read_pdf(pdf_bytes))
        default_callout_bg = fp_str(0xF2 / 255, 0xF2 / 255, 0xF2 / 255)  # #F2F2F2
        assert default_callout_bg.encode("latin-1") in content


class TestBrandLogoApplication:
    """Logo 参数化（platypus.Image 位图首启——首页标题上方）。"""

    def test_logo_image_xobject_on_first_page(self) -> None:
        """logo bytes 在场 → 首页含 Image XObject（位图首启运行面证据）。"""
        spec = _make_spec(logo=_make_logo_png_bytes())
        pdf_bytes = _render_brand(_make_document(), spec)
        first = _read_pdf(pdf_bytes).pages[0].get("/Resources", {})
        xobjects = first.get("/XObject", {})
        images = [obj for obj in xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
        assert images, f"首页零图像 XObject（logo 缺席）: {list(xobjects.keys())}"

    def test_no_logo_zero_xobject(self) -> None:
        """logo None → 零品牌路径（零图像 XObject——对照腿判别非恒真）。"""
        spec = _make_spec(logo=None)
        pdf_bytes = _render_brand(_make_document(), spec)
        reader = _read_pdf(pdf_bytes)
        for page in reader.pages:
            xobjects = page.get("/Resources", {}).get("/XObject", {})
            images = [obj for obj in xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
            assert not images, "logo None 不应有图像 XObject"

    def test_corrupted_logo_bytes_raises(self) -> None:
        """logo bytes 损坏 → 图像解码失败族异常显式红（不静默降级——编排层
        包装 492 的触发面；渲染器裸抛原生异常）。

        异常族锚（R1-F10 收窄）：ImageReader 经 PIL 解码——reportlab 4.5.1 +
        Pillow 12 实测抛 ``PIL.UnidentifiedImageError``（OSError 子类）；收窄到
        OSError 使「图片解码失败族」与「实现 bug」（TypeError 等非 IO 族）分立
        ——后者正确地红。"""
        spec = _make_spec(logo=b"this-is-not-an-image-at-all")
        with pytest.raises(OSError):
            _render_brand(_make_document(), spec)


# ======================================================================
# 循环 C：默认态等价回归（invariant=1 测试前置——byte 级对照）
# ======================================================================


@pytest.fixture
def _invariant_rl_config() -> Any:
    """reportlab invariant 配置（setup 置 1/teardown 还原——reproducible builds
    标准前置：默认态 trailer /ID 每次渲染含 time.time() 种子随机+CreationDate
    秒粒度漂移，byte 级对照结构性不可比；生产路径日期语义零触碰）。"""
    from reportlab import rl_config

    previous = rl_config.invariant
    rl_config.invariant = 1
    yield rl_config
    rl_config.invariant = previous


class TestDefaultStateEquivalence:
    """默认态等价（6-5b 契约冻结面——v1.1.0 演进的向后兼容运行面证据）。"""

    def test_render_equals_render_brand_none(self, _invariant_rl_config: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """同 document 双渲染 byte 级相等：``render(doc) == render(doc, brand=None)``
        （invariant=1 前提下非确定源已钉死，等价红只剩实现侵入过深一种归因）。"""
        import src.infrastructure.reporting.reportlab_pdf_renderer as renderer_module
        from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

        renderer = ReportLabPdfRenderer()
        # 隔离幂等注册态（双渲染共享模块级注册标记——对等性前提）
        monkeypatch.setattr(renderer_module, "_FONT_REGISTERED", {})
        single = renderer.render(_make_document())
        monkeypatch.setattr(renderer_module, "_FONT_REGISTERED", {})
        branded_none = renderer.render(_make_document(), brand=None)
        assert single == branded_none, f"默认态不等价：单参 {len(single)}B vs brand=None {len(branded_none)}B（实现侵入过深）"
