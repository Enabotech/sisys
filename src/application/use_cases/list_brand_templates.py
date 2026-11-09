"""品牌模板清单用例（Story 6-11——CLI brand-template-list 零参透传）。

与 get_consultant_view 零参先例同构：全局模板清单（模板不锚定 plan——
跨 plan 复用语义的本义）。
"""

from src.application.ports.brand_template import BrandTemplateServicePort
from src.domain.entities.brand_template import BrandTemplate

__all__ = ["ListBrandTemplatesUseCase"]


class ListBrandTemplatesUseCase:
    """品牌模板清单用例（CLI 入口透传——`brand-template-list` 零参数）。"""

    def __init__(self, *, brand_service: BrandTemplateServicePort) -> None:
        """初始化用例。

        Args:
            brand_service: 品牌模板服务（端口注入）。
        """
        self._brand_service = brand_service

    async def execute(self) -> tuple[BrandTemplate, ...]:
        """执行品牌模板清单查询（零参全局——行序 updated_at 降序由服务承载）。

        Returns:
            模板实体元组（空态空元组）。

        Raises:
            BrandTemplateStorageError: 495——PG 读写失败。
        """
        return await self._brand_service.list_brand_templates()
