"""品牌模板应用端口与预设冻结常量（Story 6-11——R2 具体应用端口）。

预设常量单源冻结（「静态值域=冻结常量、PG 行只存 key」模式——TOOL_CATALOG/
PHASE_STEP_DOMAINS 直系）：``COLOR_SCHEME_PRESETS`` 三套×5 色 + ``FONT_PRESETS``
两项；呈现名映射（预设键→中文呈现）是 CLI 输出与 BrandSection status 的共用
单源。R2 组合注入 R1：``BrandTemplateServicePort`` 注入 brand_template_repository
（R1 基础端口）+ l4_object（R1 基础端口——store/retrieve logo 通道）。

五色键与 ``BrandRenderSpec`` 五色键同名直映（配色套属性直供 spec 构造——
键名漂移由单测守护）；font_name 由 FONT_PRESETS 正交供给（不在配色套内）。
三套五色与渲染器默认四色（#444444/#F2F2F2/#E8E8E8/#BBBBBB）逐对互斥已
数学验证（最小差 1/255 可判别——AC-5 内容流色值断言的判别前提）。

TTF 资产注记：noto-sans-sc 的注册名 "NotoSansSC" 对应渲染器
``_TTF_FONT_FILES`` 资产映射（``fonts/NotoSansSC-VF.ttf``——sha256 与许可
登记见渲染器文件头 docstring）。
"""

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PIL import Image

from src.application.ports.pdf_report import BrandRenderSpec
from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateValidationError

__all__ = [
    "COLOR_SCHEME_PRESETS",
    "ColorSchemePreset",
    "FONT_PRESETS",
    "FontPreset",
    "BrandTemplateServicePort",
]


@dataclass(frozen=True)
class ColorSchemePreset:
    """配色套预设（呈现名+五色——五色键与 BrandRenderSpec 五色键同名直映）。

    Attributes:
        display_name: 中文呈现名（CLI 输出与 BrandSection status 共用单源）。
        title_color: H1/H2 标题文字色（6 位 hex）。
        header_bg_color: 表头行底色。
        grid_color: 表格网格线色。
        callout_bg_color: callout 底色。
        callout_text_color: callout 文字色。
    """

    display_name: str
    title_color: str
    header_bg_color: str
    grid_color: str
    callout_bg_color: str
    callout_text_color: str


@dataclass(frozen=True)
class FontPreset:
    """字体预设（呈现名+注册名）。

    Attributes:
        display_name: 中文呈现名（CLI 输出与 BrandSection status 共用单源）。
        font_name: 渲染器注册名（CID 名直用零注册[STSong-Light]/TTF 注册名
            [NotoSansSC]——注册通道归渲染器 ``_ensure_font``）。
    """

    display_name: str
    font_name: str


#: 配色套预设三套（Task 0.2 冻结表逐字钦定——corporate-blue 商务蓝/graphite
#: 石墨灰/burgundy 酒红；值级断言防漂移由单测承载）
COLOR_SCHEME_PRESETS: dict[str, ColorSchemePreset] = {
    "corporate-blue": ColorSchemePreset(
        display_name="商务蓝",
        title_color="#1F4E79",
        header_bg_color="#DCE6F1",
        grid_color="#9CB4D6",
        callout_bg_color="#EEF3FA",
        callout_text_color="#33517A",
    ),
    "graphite": ColorSchemePreset(
        display_name="石墨灰",
        title_color="#37474F",
        header_bg_color="#ECEFF1",
        grid_color="#B0BEC5",
        callout_bg_color="#F5F7F8",
        callout_text_color="#455A64",
    ),
    "burgundy": ColorSchemePreset(
        display_name="酒红",
        title_color="#7B1F2B",
        header_bg_color="#F5E6E8",
        grid_color="#C9A0A8",
        callout_bg_color="#FAF0F1",
        callout_text_color="#6E3B44",
    ),
}

#: 字体预设两项（stsong→CID 内置零注册/noto-sans-sc→TTF 注册——Task 0.2 冻结）
FONT_PRESETS: dict[str, FontPreset] = {
    "stsong": FontPreset(display_name="STSong-Light（内置宋体）", font_name="STSong-Light"),
    "noto-sans-sc": FontPreset(display_name="Noto Sans SC（黑体）", font_name="NotoSansSC"),
}

#: 品牌 L4 桶类型（三段物理桶名第二段——resolve 通道 tenant 恒 default 共享桶，
#: 隔离靠对象键锚 template_id；测试自愈建桶勿带 object_lock——OD-3）
BRAND_ASSETS_BUCKET_TYPE: str = "brand-assets"

#: Logo 对象键模板（单键覆盖——换格式重传同键覆盖零垃圾对象）
LOGO_OBJECT_KEY_TEMPLATE: str = "logos/{template_id}"

#: Logo 大小上限（2MB——防误传大图渲染 OOM）
LOGO_MAX_BYTES: int = 2 * 1024 * 1024

#: Logo 像素维度上限（单边 4000px——平坦色 PNG 可把万像素图压进 KB 级字节，
#: 2MB 字节上限不约束解码内存[实测 9000×9000 白底 PNG 仅 258KB 而渲染峰值
#: RSS 1.1GB]；4000px 解码内存上界 ~64MB 且远超 PDF 渲染面 ≤40mm 显示宽度
#: [严重过采样]——像素与字节是正交守卫）
LOGO_MAX_DIMENSION: int = 4000

#: PNG magic bytes（stdlib 前 8 字节判定）
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: JPEG magic bytes（前 3 字节判定）
_JPEG_MAGIC = b"\xff\xd8\xff"


@runtime_checkable
class BrandTemplateServicePort(Protocol):
    """品牌模板服务端口（R2 具体应用端口——save 编排/清单/渲染规格组装）。"""

    async def save_brand_template(
        self,
        *,
        name: str,
        color_scheme: str,
        font_preset: str,
        logo_path: str | None = None,
    ) -> BrandTemplate:
        """保存品牌模板（UPSERT by name 修订语义——AC-1/AC-2）。

        编排钦定序（OD-12）：``get_by_name`` 先行（同名取既有 template_id+
        logo_object_key——保留语义与 L4 键锚定的单源承载位）→ 值域校验+name
        前置预检 → logo 校验（magic/大小/路径）→ [logo_path 在场]L4 store
        → 实体构造（updated_at 服务侧定时戳）→ repo.save（仓储纯 UPSERT）。

        Args:
            name: 模板名（业务键——同名=修订覆盖非冲突）。
            color_scheme: 配色预设键（值域 ∈ COLOR_SCHEME_PRESETS 三键）。
            font_preset: 字体预设键（值域 ∈ FONT_PRESETS 两键）。
            logo_path: 本地 Logo 图片路径（PNG/JPEG；None=保留既有 logo
                ——缺席≠清除，清除归后续模板管理 Story）。

        Returns:
            保存后的模板实体（七字段——首存新 template_id/修订保留原值）。

        Raises:
            BrandTemplateValidationError: 494——非法预设 key/Logo magic 非法/
                超 2MB/路径不存在。
            EntityValidationError: 242——name 空值/超长（实体守卫透传）。
        """
        ...

    async def list_brand_templates(self) -> tuple[BrandTemplate, ...]:
        """全量模板清单（updated_at 降序+name 字典序 tie-break——最新修订优先）。

        Returns:
            模板实体元组。
        """
        ...

    async def get_render_spec(self, template_name: str) -> BrandRenderSpec:
        """按模板名组装白标渲染规格（预设映射+L4 logo 读回——渲染器直消费形态）。

        Args:
            template_name: 模板名（业务键）。

        Returns:
            BrandRenderSpec 7 键（font_name/五色来自预设常量单源映射；logo
            是 bytes——L4 读取归本服务，渲染器零 IO 纯函数纪律保持）。

        Raises:
            BrandTemplateValidationError: 494——模板不存在（message 含模板名）
                /行内预设键脏（直写行绕过 save 校验的防御包装）。
            BrandTemplateStorageError: 495——L4 logo 读回失败。
        """
        ...


# ---------------------------------------------------------------------------
# 纯函数 helper（校验与 content_type 推断——服务的私有面，端口文件承载常量单源）
# ---------------------------------------------------------------------------


def infer_logo_content_type(head: bytes) -> str:
    """按 magic bytes 推断 Logo content_type（PNG/JPEG 二元）。

    Args:
        head: 文件头字节（前 8 字节足够判两格式）。

    Returns:
        "image/png" / "image/jpeg"。

    Raises:
        BrandTemplateValidationError: 494——非两格式 magic（异常体系红线：
            禁裸 ValueError 逃逸——校验失败族直抛领域异常）。
    """
    if head.startswith(_PNG_MAGIC):
        return "image/png"
    if head.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    raise BrandTemplateValidationError(
        field="logo_path",
        message=f"Logo 文件非 PNG/JPEG 格式（magic bytes 不匹配: {head!r}）",
    )


def validate_logo_file(logo_path: str) -> str:
    """Logo 文件四重校验（路径存在→大小上限→magic bytes→像素维度——返回 content_type）。

    Args:
        logo_path: 本地路径。

    Returns:
        推断的 content_type（"image/png"/"image/jpeg"）。

    Raises:
        BrandTemplateValidationError: 494——四负例之一（路径不存在[文件不可读
            伞形]/超 2MB/非法 magic/像素超限或图像体无法解析——消息含上限
            值与合法格式说明）。
    """
    if not os.path.isfile(logo_path):
        raise BrandTemplateValidationError(
            field="logo_path",
            message=f"Logo 文件不存在或不可读: {logo_path}",
        )
    try:
        size = os.path.getsize(logo_path)
        with open(logo_path, "rb") as handle:
            head = handle.read(8)
    except OSError as error:  # 不可读伞形（PermissionError/TOCTOU 缺失族）
        raise BrandTemplateValidationError(
            field="logo_path",
            message=f"Logo 文件不可读: {logo_path}（{error}）",
        ) from error
    if size > LOGO_MAX_BYTES:
        raise BrandTemplateValidationError(
            field="logo_path",
            message=f"Logo 文件超 2MB 上限（{size} 字节 > {LOGO_MAX_BYTES}）",
        )
    content_type = infer_logo_content_type(head)
    try:
        with Image.open(logo_path) as image:  # 惰性读头取尺寸（零全图解码）
            width, height = image.size
    except OSError as error:  # 图像体不可解析（PIL.UnidentifiedImageError⊂OSError）——与不可读伞形分立
        raise BrandTemplateValidationError(
            field="logo_path",
            message=f"Logo 图像体无法解析（非合法可解码 PNG/JPEG）: {error}",
        ) from error
    if max(width, height) > LOGO_MAX_DIMENSION:
        raise BrandTemplateValidationError(
            field="logo_path",
            message=f"Logo 像素维度超限（{width}×{height} > 单边 {LOGO_MAX_DIMENSION}px 上限）",
        )
    return content_type


def preset_keys_message() -> str:
    """合法预设键清单消息（调用方可理解性——不泄露 SQL/堆栈）。"""
    return (
        f"color_scheme 必须为预设键之一（{'/'.join(COLOR_SCHEME_PRESETS)}）、"
        f"font_preset 必须为预设键之一（{'/'.join(FONT_PRESETS)}）"
    )
