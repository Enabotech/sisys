"""品牌预设常量单元测试（Story 6-11 Task 4——Task 0.2 冻结表值级防漂移）。

覆盖面：
- COLOR_SCHEME_PRESETS 三键 exact set（corporate-blue/graphite/burgundy）
- 每套 5 色 hex 与冻结表逐字一致（参数化逐套逐键——防漂移即守护）
- 呈现名映射（商务蓝/石墨灰/酒红——CLI 输出与 BrandSection status 共用单源）
- FONT_PRESETS 两键（stsong→CID 名直用零注册/noto-sans-sc→TTF 注册名）
- 五色键与 BrandRenderSpec 五色键同名直映（dataclasses.fields 断言——
  键名漂移即红）

Run with:
    poetry run pytest tests/unit/application/test_brand_template_presets.py -v
"""

import dataclasses

import pytest

from src.application.ports.brand_template import COLOR_SCHEME_PRESETS, FONT_PRESETS

#: Task 0.2 冻结表逐字钦定（corporate-blue 商务蓝/graphite 石墨灰/burgundy 酒红——
#: 每套 5 色；三套五色与渲染器默认四色 #444444/#F2F2F2/#E8E8E8/#BBBBBB
#: 逐对互斥已数学验证[最小差 1/255 可判别]）
_FROZEN_SCHEMES: dict[str, dict[str, str]] = {
    "corporate-blue": {
        "display_name": "商务蓝",
        "title_color": "#1F4E79",
        "header_bg_color": "#DCE6F1",
        "grid_color": "#9CB4D6",
        "callout_bg_color": "#EEF3FA",
        "callout_text_color": "#33517A",
    },
    "graphite": {
        "display_name": "石墨灰",
        "title_color": "#37474F",
        "header_bg_color": "#ECEFF1",
        "grid_color": "#B0BEC5",
        "callout_bg_color": "#F5F7F8",
        "callout_text_color": "#455A64",
    },
    "burgundy": {
        "display_name": "酒红",
        "title_color": "#7B1F2B",
        "header_bg_color": "#F5E6E8",
        "grid_color": "#C9A0A8",
        "callout_bg_color": "#FAF0F1",
        "callout_text_color": "#6E3B44",
    },
}

#: 字体冻结表（stsong→CID 名直用零注册——渲染器 _FONT_NAME :60 同值；
#: noto-sans-sc→TTF 注册名——资产通道）
_FROZEN_FONTS: dict[str, dict[str, str]] = {
    "stsong": {"display_name": "STSong-Light（内置宋体）", "font_name": "STSong-Light"},
    "noto-sans-sc": {"display_name": "Noto Sans SC（黑体）", "font_name": "NotoSansSC"},
}


class TestColorSchemePresets:
    """配色套三键冻结（Task 0.2——exact set+逐字值级）。"""

    def test_exact_keys(self) -> None:
        """三键 exact set（多列/漏列双红——集合等值双向判别）。"""
        assert set(COLOR_SCHEME_PRESETS.keys()) == set(_FROZEN_SCHEMES.keys())

    @pytest.mark.parametrize("scheme_key", list(_FROZEN_SCHEMES))
    def test_scheme_values_frozen_verbatim(self, scheme_key: str) -> None:
        """每套 5 色+呈现名与冻结表逐字一致（参数化逐套）。"""
        preset = COLOR_SCHEME_PRESETS[scheme_key]
        frozen = _FROZEN_SCHEMES[scheme_key]
        for field_name, expected in frozen.items():
            actual = getattr(preset, field_name)
            assert actual == expected, f"{scheme_key}.{field_name} 漂移: {actual} != {expected}"

    @pytest.mark.parametrize("scheme_key", list(_FROZEN_SCHEMES))
    def test_scheme_display_names(self, scheme_key: str) -> None:
        """呈现名映射（CLI 输出与 BrandSection status 共用单源）。"""
        assert COLOR_SCHEME_PRESETS[scheme_key].display_name == _FROZEN_SCHEMES[scheme_key]["display_name"]

    def test_preset_color_keys_mirror_render_spec(self) -> None:
        """配色套五色键与 BrandRenderSpec 五色键同名直映（dataclasses.fields
        断言——键名漂移即红：预设对象属性直供 spec 构造）。"""
        from src.application.ports.pdf_report import BrandRenderSpec

        spec_color_keys = {f.name for f in dataclasses.fields(BrandRenderSpec) if f.name.endswith("_color")}
        preset_fields = {f.name for f in dataclasses.fields(COLOR_SCHEME_PRESETS["graphite"])}
        assert spec_color_keys <= preset_fields, f"五色键不同名直映: {spec_color_keys - preset_fields}"


class TestFontPresets:
    """字体预设两项冻结。"""

    def test_exact_keys(self) -> None:
        """两键 exact set（stsong/noto-sans-sc）。"""
        assert set(FONT_PRESETS.keys()) == set(_FROZEN_FONTS.keys())

    @pytest.mark.parametrize("font_key", list(_FROZEN_FONTS))
    def test_font_values_frozen(self, font_key: str) -> None:
        """注册名+呈现名逐字一致（stsong 与渲染器 _FONT_NAME 同值直用）。"""
        preset = FONT_PRESETS[font_key]
        assert preset.font_name == _FROZEN_FONTS[font_key]["font_name"]
        assert preset.display_name == _FROZEN_FONTS[font_key]["display_name"]
