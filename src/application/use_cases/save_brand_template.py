"""保存品牌模板用例（Story 6-11——CLI brand-template-save 入口透传）。

与 GenerateMarkdownReportUseCase :16-52 同构：keyword-only 透传（无 UUID
守卫——name 非 UUID 参数，非空/长度校验在服务预检与实体守卫承载）。
"""

from src.application.ports.brand_template import BrandTemplateServicePort
from src.domain.entities.brand_template import BrandTemplate

__all__ = ["SaveBrandTemplateUseCase"]


class SaveBrandTemplateUseCase:
    """保存品牌模板用例（CLI 入口透传——`brand-template-save`）。"""

    def __init__(self, *, brand_service: BrandTemplateServicePort) -> None:
        """初始化用例。

        Args:
            brand_service: 品牌模板服务（端口注入）。
        """
        self._brand_service = brand_service

    async def execute(
        self,
        *,
        name: str,
        color_scheme: str,
        font_preset: str,
        logo_path: str | None = None,
    ) -> BrandTemplate:
        """执行品牌模板保存（四参 keyword-only 透传）。

        Args:
            name: 模板名（业务键——同名=修订覆盖非冲突）。
            color_scheme: 配色预设键。
            font_preset: 字体预设键。
            logo_path: 本地 Logo 路径（可选——None 保留既有 logo）。

        Returns:
            保存后的模板实体（七字段）。

        Raises:
            BrandTemplateValidationError: 494——非法预设 key/Logo 四负例。
            EntityValidationError: 242——name 空值/超长（服务预检透传）。
        """
        return await self._brand_service.save_brand_template(
            name=name,
            color_scheme=color_scheme,
            font_preset=font_preset,
            logo_path=logo_path,
        )
