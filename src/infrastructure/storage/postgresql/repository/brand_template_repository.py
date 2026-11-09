"""PostgreSQL 品牌模板仓储（Story 6-11——L2 brand_templates 表）。

session_factory 可选尾参 + save/get/list 三方法双模式 fallback
（report_repository :37-46/:116-124 直系形态）。

fallback 防呆（report_repository 模块 docstring 同款纪律）：fallback 分派
必须直调 ``session_context.get_session()`` 并 catch ``RuntimeError``——经
``PostgreSQLAdapter._session`` property 则 RuntimeError 被包成
InvalidStateError（``from None``），except 永不命中。

UPSERT 落库语义（OD-12 钦定）：save 按实体 template_id 落库（有行 UPDATE
color_scheme/font_preset/logo_object_key/updated_at 四字段——template_id/
name/created_at 不变；无行 INSERT），**仓储不承载保留判断**——保留语义与
L4 对象键锚定的单源承载位在服务侧（save 编排先 get_by_name 取既有
template_id 与 logo_object_key 后传入）。并发双 INSERT 撞 UNIQUE(name)
与 UPDATE 形态 None 时间戳撞 NOT NULL 的 IntegrityError 均包装 495（防御
义务归仓储——tool_version SAVEPOINT 先例的简化形态：单语句粒度捕获，
无需 SAVEPOINT 嵌套）。

读路径同包装（R1-F2——契约「PG 读写失败→495」兑现）：``_do_get_by_name``
/``_do_list`` 对协议外异常兜底包装 495（layer="l2"）——与 ``_persist``
「防御义务归仓储」同位，全部消费方（服务编排/consultant_view 段级容错/
pdf 品牌前置）单点受益；fallback 分派层 RuntimeError（无 session 无
factory 配置缺失）在包装面外保持显式上抛（docstring 钦定语义）；fallback
with-factory 模式下 session_context 提交期故障与 ``_persist`` 同边界（最
小面一致取舍）。
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateStorageError
from src.infrastructure.storage.postgresql.models.brand_template import BrandTemplateModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter
from src.infrastructure.storage.postgresql.session_context import get_session, session_context

logger = logging.getLogger(__name__)


class PostgreSQLBrandTemplateRepository(PostgreSQLAdapter[BrandTemplate, BrandTemplateModel]):
    """品牌模板仓储实现（BrandTemplateRepositoryProtocol——L2 配置行）。

    通过 ``_to_entity``/``_to_model`` 隔离领域层与 ORM 层（UUID/时间戳
    直映射——本表无 enum/JSONB 转换面）。
    """

    pk_column: str = "template_id"

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """初始化品牌模板仓储.

        Args:
            session_factory: fallback 独立会话工厂（CLI/后台路径——None 时无
                ContextVar session 则 RuntimeError 上抛，配置缺失显式失败；
                组合根恒注入使生产 CLI 不落此形态）。
        """
        super().__init__(BrandTemplateModel)
        self._session_factory = session_factory

    def _to_entity(self, model: BrandTemplateModel) -> BrandTemplate:
        """ORM 模型 → 领域实体（直映射——无 enum/JSONB 转换面）。

        Args:
            model: ORM 行。

        Returns:
            BrandTemplate 实体。
        """
        return BrandTemplate(
            template_id=model.template_id,
            name=model.name,
            color_scheme=model.color_scheme,
            font_preset=model.font_preset,
            logo_object_key=model.logo_object_key,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, template: BrandTemplate) -> BrandTemplateModel:
        """领域实体 → ORM 模型（INSERT 分支用——UPDATE 分支就地 setattr 不经本函数）。

        Args:
            template: 模板实体。

        Returns:
            BrandTemplateModel ORM 实例。
        """
        return BrandTemplateModel(
            template_id=template.template_id,
            name=template.name,
            color_scheme=template.color_scheme,
            font_preset=template.font_preset,
            logo_object_key=template.logo_object_key,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    async def save(self, template: BrandTemplate) -> BrandTemplate:
        """保存品牌模板行（按 template_id 纯 UPSERT——双模式 fallback）。

        Args:
            template: 模板实体（template_id 主键——同名修订由服务侧先行
                get_by_name 传入既有 template_id）。

        Returns:
            保存后的模板实体（id/时间戳应用侧已定——零 DB 回读依赖）。

        Raises:
            BrandTemplateStorageError: L2 落库失败（495——IntegrityError
                包装：UNIQUE(name) 并发撞/NOT NULL 时间戳撞）。
            RuntimeError: 无请求 session 且无 factory（配置缺失显式失败）。
        """
        try:
            get_session()
        except RuntimeError:
            # CLI/后台路径（无请求 session）——经注入工厂走独立会话 commit
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._persist(template)
        return await self._persist(template)

    async def _persist(self, template: BrandTemplate) -> BrandTemplate:
        """实际保存（按 template_id UPSERT：有行 UPDATE 四字段/无行 INSERT）。

        Args:
            template: 模板实体。

        Returns:
            原模板实体。

        Raises:
            BrandTemplateStorageError: IntegrityError 包装（495——并发双
                INSERT 撞 UNIQUE(name)/UPDATE 形态 None 时间戳撞 NOT NULL）。
        """
        try:
            statement = select(BrandTemplateModel).where(BrandTemplateModel.template_id == template.template_id)
            result = await self._session.execute(statement)
            existing = result.scalar_one_or_none()
            if existing is not None:
                # UPDATE 分支：四配置字段前进（template_id/name/created_at 不变——
                # 保留语义归服务侧单源；updated_at None 时 UPDATE 写 NULL 撞 NOT
                # NULL 走 IntegrityError→495——实体构造通则的反面防御路径）
                existing.color_scheme = template.color_scheme
                existing.font_preset = template.font_preset
                existing.logo_object_key = template.logo_object_key
                existing.updated_at = template.updated_at
            else:
                self._session.add(self._to_model(template))
            await self._session.flush()
            return template
        except IntegrityError as error:
            raise BrandTemplateStorageError(
                layer="l2",
                message="品牌模板行落库失败（并发同名冲突或时间戳缺失——IntegrityError 包装）",
                cause=error,
            ) from error

    async def get_by_name(self, name: str) -> BrandTemplate | None:
        """按业务键 name 唯一查找（UNIQUE 至多一行——双模式 fallback）。

        Args:
            name: 模板名（业务键）。

        Returns:
            模板实体；无记录返回 None（服务侧 None 抛 494 的前提）。

        Raises:
            BrandTemplateStorageError: L2 读失败（495——协议外异常兜底
                包装，防御义务归仓储）。
            RuntimeError: 无请求 session 且无 factory（配置缺失显式失败）。
        """
        try:
            get_session()
        except RuntimeError:
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._do_get_by_name(name)
        return await self._do_get_by_name(name)

    async def _do_get_by_name(self, name: str) -> BrandTemplate | None:
        """实际查询（name 业务键唯一查找）。

        Args:
            name: 模板名。

        Returns:
            模板实体或 None。

        Raises:
            BrandTemplateStorageError: L2 读失败（495——连接/表缺失等协议外
                异常兜底包装，与 _persist 的 IntegrityError 包装同位）。
        """
        try:
            statement = select(BrandTemplateModel).where(BrandTemplateModel.name == name)
            result = await self._session.execute(statement)
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model is not None else None
        except BrandTemplateStorageError:
            raise
        except Exception as error:  # 读路径防御包装——契约「PG 读写失败→495」
            raise BrandTemplateStorageError(layer="l2", cause=error) from error

    async def list_templates(self) -> list[BrandTemplate]:
        """全量清单（updated_at 降序+name 字典序 tie-break——双模式 fallback）。

        Returns:
            模板实体清单（最新修订优先——CLI 列表行序与品牌段「最新行」共同锚）。

        Raises:
            BrandTemplateStorageError: L2 读失败（495——协议外异常兜底
                包装，防御义务归仓储）。
            RuntimeError: 无请求 session 且无 factory（配置缺失显式失败）。
        """
        try:
            get_session()
        except RuntimeError:
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._do_list()
        return await self._do_list()

    async def _do_list(self) -> list[BrandTemplate]:
        """实际查询（双序全量）。

        Returns:
            模板实体清单。

        Raises:
            BrandTemplateStorageError: L2 读失败（495——协议外异常兜底
                包装，与 _do_get_by_name 同位）。
        """
        try:
            statement = select(BrandTemplateModel).order_by(BrandTemplateModel.updated_at.desc(), BrandTemplateModel.name.asc())
            result = await self._session.execute(statement)
            return [self._to_entity(model) for model in result.scalars().all()]
        except BrandTemplateStorageError:
            raise
        except Exception as error:  # 读路径防御包装——契约「PG 读写失败→495」
            raise BrandTemplateStorageError(layer="l2", cause=error) from error
