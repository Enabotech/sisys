"""品牌模板实体（Story 6-11——白标报告基础的领域配置真相源行）。

品牌模板是顾问可保存可复用的白标配置：预设配色套（3 套）与字体预设（2 项）
的键引用 + 可选 Logo 的 L4 对象键——「静态值域=冻结常量、PG 行只存 key」模式
（TOOL_CATALOG/PHASE_STEP_DOMAINS 直系；预设常量单源在 application ports，
本实体零 application import——值域校验落应用服务的依赖方向依据）。

UPSERT by name 修订语义（OD-12）：同名再存=修订覆盖非冲突——保留语义与
L4 对象键锚定的承载位在服务侧（save 编排先 get_by_name 取既有 template_id
与 logo_object_key），仓储仅按 template_id 落库不承载保留判断。

领域零依赖约束：本模块仅依赖标准库与领域异常体系（import-linter 强制）。
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.exceptions import EntityValidationError

__all__ = ["BrandTemplate"]


@dataclass(frozen=True)
class BrandTemplate:
    """品牌模板实体（品牌配置的持久化真相源行——L2 brand_templates 表实体面）。

    幂等锚 = template_id（name UNIQUE 是业务键非主键）：同名修订由服务侧先行
    ``get_by_name`` 取既有 template_id 后按原键 UPDATE（template_id/name/
    created_at 不变+三配置字段与 updated_at 前进）——CLI 面同名保存是模板
    修订的预期用法（无 409 等价错误语义——AC-1 钦定）。

    Attributes:
        template_id: 模板主键（默认 uuid4——首次新建生成，同名修订由服务保留原值）。
        name: 模板名（业务键 UNIQUE——非空且 ≤100 字符；TestTenant 前缀防撞
            是测试面纪律非实体约束）。
        color_scheme: 配色预设键（非空且 ≤30 字符——值域 ∈ COLOR_SCHEME_PRESETS
            三键的校验落应用服务[依赖方向矩阵]，实体仅守卫长度与非空）。
        font_preset: 字体预设键（非空且 ≤30 字符——值域 ∈ FONT_PRESETS 两键
            校验同上落应用服务）。
        logo_object_key: L4 对象键（``logos/{template_id}`` 单键覆盖——None
            表示无 Logo[配色/字体独立生效]；修订时缺席=保留原值由服务侧承载）。
        created_at: 创建时间（UTC——None 是应用侧定时戳责任位的诚实形态：
            服务构造实体时显式定值[OD-12]，DDL server_default 仅 INSERT 初值）。
        updated_at: 修订时间（UTC——服务侧显式定值驱动 UPSERT 前进语义；
            列表行序锚[updated_at 降序+name 字典序 tie-break——最新修订优先]）。
    """

    template_id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    color_scheme: str = ""
    font_preset: str = ""
    logo_object_key: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        """构造期不变量守卫（违例抛 EntityValidationError 242——fail-loud）。

        Raises:
            EntityValidationError: name 为空或超 100 字符（DDL VARCHAR(100)
                对齐）/ color_scheme 为空或超 30 字符 / font_preset 为空或超
                30 字符（预设键值域校验落应用服务——本守卫仅 domain 契约面）。
        """
        if not self.name.strip():
            raise EntityValidationError(
                message="name 不可为空（模板名是业务键与 CLI 呈现锚）",
                context={"entity": "BrandTemplate", "field": "name"},
            )
        if len(self.name) > 100:
            raise EntityValidationError(
                message="name 不可超过 100 字符（DDL VARCHAR(100) 对齐）",
                context={"entity": "BrandTemplate", "field": "name", "length": str(len(self.name))},
            )
        if not self.color_scheme.strip():
            raise EntityValidationError(
                message="color_scheme 不可为空（预设配色套键——值域校验归应用服务）",
                context={"entity": "BrandTemplate", "field": "color_scheme"},
            )
        if len(self.color_scheme) > 30:
            raise EntityValidationError(
                message="color_scheme 不可超过 30 字符（DDL VARCHAR(30) 对齐）",
                context={"entity": "BrandTemplate", "field": "color_scheme"},
            )
        if not self.font_preset.strip():
            raise EntityValidationError(
                message="font_preset 不可为空（预设字体键——值域校验归应用服务）",
                context={"entity": "BrandTemplate", "field": "font_preset"},
            )
        if len(self.font_preset) > 30:
            raise EntityValidationError(
                message="font_preset 不可超过 30 字符（DDL VARCHAR(30) 对齐）",
                context={"entity": "BrandTemplate", "field": "font_preset"},
            )
