"""品牌模板服务（Story 6-11——save 编排/清单/渲染规格组装）。

R2 组合注入 R1：注入 brand_template_repository（R1 基础端口——UPSERT 落库）
+ l4_object（R1 基础端口——logo store/retrieve 通道）。

save 编排钦定序（OD-12）：``get_by_name`` 先行（保留语义与 L4 键锚定的单源
承载位——同名取既有 template_id+logo_object_key）→ 值域校验+name 前置预检
（242 提前于 L4 store——防「非法 name+logo 形态」产生孤儿 logo 对象，实体
``__post_init__`` 保留为最终防线）→ logo 四重校验（494）→ [logo_path 在场]
L4 store（``logos/{template_id}`` 单键覆盖）→ 实体构造（updated_at 服务侧
定时戳——DDL server_default 仅 INSERT 初值不承载修订前进）→ repo.save
（仓储按 template_id 纯 UPSERT 落库，不承载保留判断；失败时对**本次新写**
logo 键 best-effort 补偿删除防孤儿对象——修订既有键形态不补偿[删除即丢
PG 行仍引用的既有 logo]，「覆盖后落库失败」的 bytes/行配置错位低概率窗口
注记接受——R1-F5 裁定）。

服务无状态（SINGLETON 并发共享安全——每次调用全部局部态）。
"""

import logging
import uuid
from datetime import UTC, datetime

from src.application.ports.brand_template import (
    BRAND_ASSETS_BUCKET_TYPE,
    COLOR_SCHEME_PRESETS,
    FONT_PRESETS,
    LOGO_OBJECT_KEY_TEMPLATE,
    BrandTemplateServicePort,
    preset_keys_message,
    validate_logo_file,
)
from src.application.ports.pdf_report import BrandRenderSpec
from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateStorageError, BrandTemplateValidationError
from src.domain.ports.brand_template_repository import BrandTemplateRepositoryProtocol
from src.domain.ports.l4_object import L4ObjectPort

logger = logging.getLogger(__name__)

__all__ = ["BrandTemplateService"]


class BrandTemplateService(BrandTemplateServicePort):
    """品牌模板服务实现（save/list/get_render_spec 三方法编排）。"""

    def __init__(
        self,
        *,
        brand_template_repository: BrandTemplateRepositoryProtocol,
        l4_object: L4ObjectPort,
    ) -> None:
        """初始化服务（双依赖 keyword-only——R2 组合注入 R1）。

        Args:
            brand_template_repository: 品牌模板仓储（R1——UPSERT 落库）。
            l4_object: L4 对象存储端口（R1——logo store/retrieve 通道）。
        """
        self._repository = brand_template_repository
        self._l4_object = l4_object

    async def save_brand_template(
        self,
        *,
        name: str,
        color_scheme: str,
        font_preset: str,
        logo_path: str | None = None,
    ) -> BrandTemplate:
        """保存品牌模板（编排钦定序——见模块 docstring）。

        Args:
            name: 模板名（业务键——同名=修订覆盖）。
            color_scheme: 配色预设键。
            font_preset: 字体预设键。
            logo_path: 本地 Logo 路径（None=保留既有 logo）。

        Returns:
            保存后的模板实体。

        Raises:
            BrandTemplateValidationError: 494——非法预设 key/Logo 四负例。
            EntityValidationError: 242——name 空值/超长（预检构造透传）。
            BrandTemplateStorageError: 495——L4 logo 上传失败。
        """
        # ① get_by_name 先行（保留语义与键锚定单源——OD-12 钦定序首步）
        existing = await self._repository.get_by_name(name)
        template_id = existing.template_id if existing is not None else uuid.uuid4()
        existing_logo_key = existing.logo_object_key if existing is not None else None
        # ② 值域校验+name 前置预检（预检=预构造实体——非法即 242 透传且先于 L4，
        #    防「非法 name+logo 形态」store 先行产生孤儿 logo 对象——R3 裁定）
        if color_scheme not in COLOR_SCHEME_PRESETS or font_preset not in FONT_PRESETS:
            raise BrandTemplateValidationError(
                field="color_scheme" if color_scheme not in COLOR_SCHEME_PRESETS else "font_preset",
                message=preset_keys_message(),
                context_extra={"template_name": name},
            )
        BrandTemplate(template_id=template_id, name=name, color_scheme=color_scheme, font_preset=font_preset)
        # ③ logo 校验（四负例 494 直抛——helper 直抛领域异常，无包装层）+ ④ L4 store（单键覆盖）
        logo_object_key = existing_logo_key
        newly_stored_object_key: str | None = None  # 本次新写键（repo.save 失败补偿锚——非既有键覆盖形态）
        if logo_path is not None:
            content_type = validate_logo_file(logo_path)
            object_key = LOGO_OBJECT_KEY_TEMPLATE.format(template_id=template_id)
            try:
                await self._l4_object.store(
                    bucket_type=BRAND_ASSETS_BUCKET_TYPE,
                    object_key=object_key,
                    file_path=logo_path,
                    content_type=content_type,
                )
            except Exception as error:
                raise BrandTemplateStorageError(layer="l4", message="Logo 对象上传失败", cause=error) from error
            if object_key != existing_logo_key:
                newly_stored_object_key = object_key
            logo_object_key = object_key
        # ⑤ 实体构造（保留语义：无 logo_path 沿用既有键；updated_at 服务侧定时戳）
        now = datetime.now(UTC)
        template = BrandTemplate(
            template_id=template_id,
            name=name,
            color_scheme=color_scheme,
            font_preset=font_preset,
            logo_object_key=logo_object_key,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        # ⑥ repo.save（仓储纯 UPSERT——保留判断归本服务单源；失败时对本次新写
        #    logo 键 best-effort 补偿删除——修订既有键形态 newly_stored 为 None 不动）
        try:
            return await self._repository.save(template)
        except BrandTemplateStorageError:
            await self._cleanup_orphan_logo_if_any(newly_stored_object_key)
            raise
        except Exception as error:  # 仓储协议外异常防御包装
            await self._cleanup_orphan_logo_if_any(newly_stored_object_key)
            raise BrandTemplateStorageError(layer="l2", cause=error) from error

    async def _cleanup_orphan_logo_if_any(self, object_key: str | None) -> None:
        """本次新写 logo 键的 best-effort 补偿删除（repo.save 失败防孤儿对象）。

        补偿删除失败仅告警不掩盖原始异常（Saga 补偿形态——原始 495 正常
        上抛，warning 带 bucket/object_key/错误三要素保可观测）；修订既有
        键形态调用方传 None（删除即丢 PG 行仍引用的既有 logo——错位窗口
        模块 docstring 注记接受）。

        Args:
            object_key: 本次新上传的对象键（None=无补偿义务零副作用）。
        """
        if object_key is None:
            return
        try:
            await self._l4_object.delete(bucket_type=BRAND_ASSETS_BUCKET_TYPE, object_key=object_key)
        except Exception as error:
            logger.warning(
                "Logo 孤儿对象补偿删除失败（bucket_type=%s, object_key=%s）: %s",
                BRAND_ASSETS_BUCKET_TYPE,
                object_key,
                error,
            )

    async def list_brand_templates(self) -> tuple[BrandTemplate, ...]:
        """全量清单（仓储 list 透传 tuple 化——行序语义归仓储 ORDER BY 单源）。"""
        return tuple(await self._repository.list_templates())

    async def get_render_spec(self, template_name: str) -> BrandRenderSpec:
        """按模板名组装渲染规格（预设映射+L4 logo 读回）。

        Args:
            template_name: 模板名（业务键）。

        Returns:
            BrandRenderSpec 7 键（预设常量单源映射五色+font_name；logo bytes
            经 retrieve 异步迭代聚合——chain_of_thought :298 同款形态）。

        Raises:
            BrandTemplateValidationError: 494——模板不存在（message 含模板名）
                /行内预设键脏。
            BrandTemplateStorageError: 495——L4 logo 读回失败。
        """
        template = await self._repository.get_by_name(template_name)
        if template is None:
            raise BrandTemplateValidationError(
                field="template_name",
                message=f"品牌模板不存在: {template_name}（先执行 brand-template-save 保存）",
                context_extra={"template_name": template_name, "reason": "模板不存在"},
            )
        color_preset = COLOR_SCHEME_PRESETS.get(template.color_scheme)
        font_preset = FONT_PRESETS.get(template.font_preset)
        if color_preset is None or font_preset is None:
            raise BrandTemplateValidationError(
                field="color_scheme" if color_preset is None else "font_preset",
                message=f"模板行预设键脏（{template.color_scheme}/{template.font_preset}）——{preset_keys_message()}",
                context_extra={"template_name": template_name, "reason": "行内预设键不在值域"},
            )
        logo_bytes: bytes | None = None
        if template.logo_object_key:
            try:
                chunks: list[bytes] = []
                async for chunk in self._l4_object.retrieve(
                    bucket_type=BRAND_ASSETS_BUCKET_TYPE, object_key=template.logo_object_key
                ):
                    chunks.append(chunk)
                logo_bytes = b"".join(chunks)
            except Exception as error:
                raise BrandTemplateStorageError(layer="l4", message="Logo 对象读回失败", cause=error) from error
        return BrandRenderSpec(
            font_name=font_preset.font_name,
            title_color=color_preset.title_color,
            header_bg_color=color_preset.header_bg_color,
            grid_color=color_preset.grid_color,
            callout_bg_color=color_preset.callout_bg_color,
            callout_text_color=color_preset.callout_text_color,
            logo=logo_bytes,
        )
