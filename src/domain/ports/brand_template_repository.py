"""品牌模板仓储端口（Story 6-11——R1 基础端口）。

L2 brand_templates 表仓储契约：save 按 template_id 纯 UPSERT 落库（有行
UPDATE 三配置字段+updated_at/无行 INSERT——保留语义与 L4 对象键锚定的承载
位在服务侧[OD-12 钦定：save 编排先 get_by_name 取既有 template_id 与
logo_object_key]，仓储不承载保留判断）；get_by_name 按业务键唯一查找；
list_templates 全量清单（updated_at 降序+name 字典序 tie-break——最新修订
优先：UPSERT 每存必前进 updated_at 而 created_at 不变，created_at 排序下
修订旧模板永沉底与「最新修订优先」语义互斥——R1 修复裁定）。

查询参数决策规则：单字段标识查找 → 直接参数（get_by_name(name)）；
命令型操作 → 直接参数（save(template)）；全量清单零参（list_templates()）。
"""

from typing import Protocol, runtime_checkable

from src.domain.entities.brand_template import BrandTemplate

__all__ = ["BrandTemplateRepositoryProtocol"]


@runtime_checkable
class BrandTemplateRepositoryProtocol(Protocol):
    """品牌模板仓储端口（R1 基础端口——infrastructure 层实现）。"""

    async def save(self, template: BrandTemplate) -> BrandTemplate:
        """保存品牌模板行（按 template_id 纯 UPSERT 落库——服务侧先行钦定序）。

        Args:
            template: 模板实体（template_id 主键——同名修订由服务侧先行
                get_by_name 传入既有 template_id，仓储按主键有行 UPDATE/
                无行 INSERT）。

        Returns:
            保存后的模板实体。

        Raises:
            BrandTemplateStorageError: L2 落库失败（layer="l2"——并发双 INSERT
                撞 UNIQUE(name) 的 IntegrityError 同包装，防御义务归仓储）。
        """
        ...

    async def get_by_name(self, name: str) -> BrandTemplate | None:
        """按业务键 name 唯一查找（UNIQUE 约束至多一行）。

        Args:
            name: 模板名（业务键）。

        Returns:
            模板实体；无记录返回 None。

        Raises:
            BrandTemplateStorageError: L2 读失败（layer="l2"——协议外异常
                兜底包装，防御义务归仓储；契约「PG 读写失败→495」读面）。
        """
        ...

    async def list_templates(self) -> list[BrandTemplate]:
        """全量模板清单（updated_at 降序+name 字典序 tie-break——最新修订优先）。

        Returns:
            模板实体清单（行序是 CLI 列表与品牌段「最新行」的共同语义锚）。

        Raises:
            BrandTemplateStorageError: L2 读失败（layer="l2"——协议外异常
                兜底包装，防御义务归仓储）。
        """
        ...
