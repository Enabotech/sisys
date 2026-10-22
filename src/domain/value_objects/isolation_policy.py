"""领域层 EIP 隔离策略值对象模块（Story 5.4 — EIP 弹性隔离协议基础）

EIP（弹性隔离协议）四级隔离等级的策略声明载体:
- DataIsolationMode: 数据隔离模式四值枚举（core-domain-design §17.3.3）
- IsolationPolicy: 单级策略 VO（三重隔离维度——Prompt/工具/数据）
- ISOLATION_POLICIES: 四级策略表模块常量（architecture.md §5.1 硬编码表）
- MVP_ALLOWED_LEVELS: MVP 允许等级集（L1 融合态 V2 开放）

设计决策（DC-2）:
- 纯静态领域规则零 IO——常量表 + 工厂函数足够，不建领域服务类
- 四级表是协议契约非部署参数（架构 §5.1 硬编码；per-agent 配置化归 V1）
- L1 融合态 MVP 禁用: 其开放前提（SYS AGENT 监督/紧急态/强制审计）全是 V2 设施
- 本模块交付三重隔离维度的策略声明（数据模型层）；执行时强制拦截归 Story 5.5

零外部依赖（仅标准库 + 同层枚举/异常——.importlinter domain 契约）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError


class DataIsolationMode(str, Enum):
    """数据隔离模式（core-domain-design §17.3.3 L1204/1211/1217/1225 四值）

    Attributes:
        READ_ONLY: 只读（L4 硬隔离——数据仅可读）
        RESTRICTED_WRITE: 受限写入（L3 软隔离——白名单写入）
        FREE_WRITE: 自由写入（L2 协作态——自由读写共享数据）
        FULL_SHARED: 完全共享（L1 融合态——上下文完全共享）
    """

    READ_ONLY = "read_only"
    RESTRICTED_WRITE = "restricted_write"
    FREE_WRITE = "free_write"
    FULL_SHARED = "full_shared"


@dataclass(frozen=True)
class IsolationPolicy:
    """EIP 隔离策略值对象（单级三重隔离维度声明）

    无状态共享规则（四级各一实例常量化于 ISOLATION_POLICIES）；
    策略维度是 5.5 三重强制执行的契约输入（本 Story 仅声明不执行）。

    Attributes:
        level: 隔离等级（枚举键）
        name: 等级名称（如 "硬隔离"——人类可读）
        prompt_isolation: Prompt 隔离（独立上下文/独立身份）
        tool_isolation: 工具隔离（严格隔离/共享工具池）
        data_isolation: 数据隔离模式（四值枚举）
        is_default: 是否默认等级（唯一 True 在 L4——出生即硬隔离）
    """

    level: IsolationLevel
    name: str
    prompt_isolation: bool
    tool_isolation: bool
    data_isolation: DataIsolationMode
    is_default: bool = False

    def __post_init__(self) -> None:
        """不变量校验（非配置 VO——失败抛 EntityValidationError 242）。

        Raises:
            EntityValidationError: name 空白或 level 非 IsolationLevel 实例
                （EXCEPTION_242——裸 str 经 hash 混入语义可能穿透宽松成员判定，
                isinstance 先行是唯一可靠子类型防线）
        """
        if not isinstance(self.level, IsolationLevel):
            raise EntityValidationError(
                message=f"level 必须为 IsolationLevel 枚举实例（实际类型 {type(self.level).__name__}）",
                context={"level": str(self.level)},
            )
        if not isinstance(self.name, str) or not self.name.strip():
            raise EntityValidationError(message="name 不能为空", context={"name": self.name})


ISOLATION_POLICIES: dict[IsolationLevel, IsolationPolicy] = {
    IsolationLevel.L4_HARD: IsolationPolicy(
        level=IsolationLevel.L4_HARD,
        name="硬隔离",
        prompt_isolation=True,
        tool_isolation=True,
        data_isolation=DataIsolationMode.READ_ONLY,
        is_default=True,
    ),
    IsolationLevel.L3_SOFT: IsolationPolicy(
        level=IsolationLevel.L3_SOFT,
        name="软隔离",
        prompt_isolation=True,
        tool_isolation=False,
        data_isolation=DataIsolationMode.RESTRICTED_WRITE,
    ),
    IsolationLevel.L2_COLLAB: IsolationPolicy(
        level=IsolationLevel.L2_COLLAB,
        name="协作态",
        prompt_isolation=True,
        tool_isolation=False,
        data_isolation=DataIsolationMode.FREE_WRITE,
    ),
    IsolationLevel.L1_FUSED: IsolationPolicy(
        level=IsolationLevel.L1_FUSED,
        name="融合态",
        prompt_isolation=False,
        tool_isolation=False,
        data_isolation=DataIsolationMode.FULL_SHARED,
    ),
}
"""四级隔离策略表（architecture.md §5.1 逐行对齐——协议契约非部署参数）

| 等级 | 名称       | Prompt 隔离 | 工具隔离   | 数据隔离          |
|------|------------|-------------|------------|-------------------|
| L4   | 硬隔离     | True        | True       | READ_ONLY         |
| L3   | 软隔离     | True        | False      | RESTRICTED_WRITE  |
| L2   | 协作态     | True        | False      | FREE_WRITE        |
| L1   | 融合态     | False       | False      | FULL_SHARED       |
"""


MVP_ALLOWED_LEVELS: frozenset[IsolationLevel] = frozenset(
    {IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB}
)
"""MVP 允许隔离等级集（L1 融合态排除——SYS 监督/紧急态/强制审计设施均 V2）

core-domain eip_config.allowed_levels=[L4,L3,L2] 先例；V2 开放 L1 时仅改本常量
（CLI SUPPORTED_ISOLATION_LEVELS 与之集合相等双锁——测试断言防漏改）。
"""


def get_isolation_policy(level: IsolationLevel) -> IsolationPolicy:
    """查询指定等级的隔离策略（四级枚举键必命中）

    Args:
        level: 隔离等级（IsolationLevel 枚举实例）

    Returns:
        对应等级的 IsolationPolicy（与 ISOLATION_POLICIES 同源实例）

    Raises:
        EntityValidationError: 非 IsolationLevel 实例入参（EXCEPTION_242——
            isinstance 先行守卫；裸 str "L4" 经 hash 混入语义不可作为键命中依据）
    """
    if not isinstance(level, IsolationLevel):
        raise EntityValidationError(
            message=f"隔离等级必须为 IsolationLevel 枚举实例（实际类型 {type(level).__name__}）",
            context={"level": str(level)},
        )
    return ISOLATION_POLICIES[level]


__all__ = [
    "ISOLATION_POLICIES",
    "MVP_ALLOWED_LEVELS",
    "DataIsolationMode",
    "IsolationPolicy",
    "get_isolation_policy",
]
