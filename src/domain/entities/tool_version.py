"""领域层工具版本聚合根模块（Story 4-6 — 工具版本管理：灰度发布与回滚）

ToolVersion 聚合根：同一 Tool 的多版本并存单元，携带独立的
input/output Schema 快照与发布状态（PENDING/CANARY/STABLE/DEPRECATED）。

设计要点（Story 4-6 SDD 规范）：
- 多版本归 ToolVersion 新聚合根——Tool 元数据与 ToolRepositoryPort 零改动
- 状态机 7 个合法迁移格 / 8 种触发语义：
  PENDING→CANARY（发起灰度）/ PENDING→STABLE（直接全量，canary_only 禁）/
  CANARY→CANARY（调档同态——渐进放量）/ CANARY→STABLE（promote 转正——灰度毕业）/
  CANARY→DEPRECATED（放弃灰度/清场）/ STABLE→DEPRECATED（被替代/被回滚）/
  DEPRECATED→STABLE（回滚恢复——唯一合法触发方 rollback 流程）
- last_stable_at 三分戳记规则：被新版本替代记戳（曾全量服务标记，回滚候选依据）、
  被回滚显式清空（业界 stable 指针原则：指针只在成功 promotion 时推进）、
  灰度清场不记（从未稳定）
- transition_to 复用 ToolExecution 先例模式，但不带 state_version 乐观锁自增
  （本 Story 仓储以 savepoint 原子性保证，无 CAS 诉求——与先例的差异点）
- 平台级资源：无 tenant_id（工具定义全局共享，与 TOOL_CATALOG 语义一致）
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from enum import Enum

from src.domain.exceptions import EntityStateTransitionError, EntityValidationError

# SemVer 强校验（照搬 Tool._SEMVER_PATTERN 规则——src/domain/entities/tool.py:53）
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

# JSON Schema 关键词（照搬 Tool._JSON_SCHEMA_KEYWORDS 规则——非空 schema 须含其一）
_JSON_SCHEMA_KEYWORDS = frozenset({"type", "properties", "$ref", "allOf", "anyOf", "oneOf"})

# 发布模式值域（小写，与 migration CHECK 值域一致）
_ROLLOUT_MODES = frozenset({"any", "canary_only"})


class ToolVersionStatus(str, Enum):
    """工具版本发布状态枚举。

    成员值显式小写，与 migration 016 的 CHECK 值域一一对应：
    - PENDING: 已注册未发布
    - CANARY: 灰度中（承接 traffic_weight% 流量）
    - STABLE: 当前全量（语义恒 100%）
    - DEPRECATED: 已弃用（含"曾稳定"语义——last_stable_at 非空者为回滚候选）
    """

    PENDING = "pending"
    CANARY = "canary"
    STABLE = "stable"
    DEPRECATED = "deprecated"


# 状态机迁移矩阵（模块级常量——ToolExecution.VALID_TRANSITIONS 先例形态）。
# 7 个合法 (from, to) 格：
#   PENDING→CANARY / PENDING→STABLE / CANARY→CANARY（调档同态）/
#   CANARY→STABLE（promote）/ CANARY→DEPRECATED（abort/清场）/
#   STABLE→DEPRECATED（被替代/被回滚）/ DEPRECATED→STABLE（回滚恢复，
#   唯一合法触发方是 rollback 流程）
VALID_TRANSITIONS: dict[ToolVersionStatus, set[ToolVersionStatus]] = {
    ToolVersionStatus.PENDING: {ToolVersionStatus.CANARY, ToolVersionStatus.STABLE},
    ToolVersionStatus.CANARY: {
        ToolVersionStatus.CANARY,
        ToolVersionStatus.STABLE,
        ToolVersionStatus.DEPRECATED,
    },
    ToolVersionStatus.STABLE: {ToolVersionStatus.DEPRECATED},
    ToolVersionStatus.DEPRECATED: {ToolVersionStatus.STABLE},
}


class ToolVersion:
    """工具版本聚合根。

    一个 ToolVersion 记录 = 某工具某版本号的完整快照（Schema + 发布状态）。
    同一 tool_id 下多版本并存；(tool_id, version) 唯一。

    Attributes:
        version_id: 版本记录主键（UUID）
        tool_id: 所属工具 ID（关联 Tool 聚合根，无外键——011 先例）
        version: SemVer 版本号（X.Y.Z 强校验）
        input_schema: 输入 JSON Schema 快照
        output_schema: 输出 JSON Schema 快照
        status: 发布状态（默认 PENDING）
        traffic_weight: 当前承接流量比例——PENDING=0、CANARY=灰度权重、
            STABLE 语义恒 100；存储域 [0,100]（发布参数域 (0,100] 由服务层校验）
        required_rollout_mode: 发布模式约束（"any" | "canary_only"）
        last_stable_at: 曾为 STABLE 的时间戳（回滚候选依据）；
            被回滚降级时显式清空（指针原则）
        created_at / updated_at: 时间戳（UTC）
    """

    def __init__(
        self,
        tool_id: uuid.UUID | str,
        version: str,
        input_schema: dict | None = None,
        output_schema: dict | None = None,
        status: ToolVersionStatus = ToolVersionStatus.PENDING,
        traffic_weight: int = 0,
        required_rollout_mode: str = "any",
        last_stable_at: datetime | None = None,
        version_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """初始化并校验不变量。

        Args:
            tool_id: 所属工具 ID
            version: SemVer 版本号
            input_schema: 输入 Schema 快照（默认空 dict）
            output_schema: 输出 Schema 快照（默认空 dict）
            status: 发布状态（默认 PENDING）
            traffic_weight: 流量权重（默认 0）
            required_rollout_mode: 发布模式（默认 any）
            last_stable_at: 曾稳定时间戳（默认 None）
            version_id: 主键（默认生成）
            created_at: 创建时间（默认当前 UTC）
            updated_at: 更新时间（默认当前 UTC）

        Raises:
            EntityValidationError: 任一不变量不满足（SemVer/权重域/模式枚举/schema 关键词）
        """
        self.version_id = version_id if version_id is not None else uuid.uuid4()
        self.tool_id = tool_id if isinstance(tool_id, uuid.UUID) else uuid.UUID(str(tool_id))
        self.version = version
        self.input_schema = input_schema if input_schema is not None else {}
        self.output_schema = output_schema if output_schema is not None else {}
        self.status = status
        self.traffic_weight = traffic_weight
        self.required_rollout_mode = required_rollout_mode
        self.last_stable_at = last_stable_at
        now = datetime.now(UTC)
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else now
        self.validate()

    def validate(self) -> bool:
        """校验实体不变量。

        Returns:
            校验通过返回 True

        Raises:
            EntityValidationError: SemVer 非法 / 权重越界 / 模式非枚举 /
                状态类型不符 / 非空 schema 缺关键词
        """
        if not isinstance(self.version, str) or not _SEMVER_PATTERN.match(self.version):
            raise EntityValidationError(
                message=f"version must match SemVer X.Y.Z: {self.version!r}",
                context={"entity": "ToolVersion", "field": "version"},
            )
        if not isinstance(self.traffic_weight, int) or not 0 <= self.traffic_weight <= 100:
            raise EntityValidationError(
                message=f"traffic_weight must be in [0, 100]: {self.traffic_weight}",
                context={"entity": "ToolVersion", "field": "traffic_weight"},
            )
        if self.required_rollout_mode not in _ROLLOUT_MODES:
            raise EntityValidationError(
                message=(f"required_rollout_mode must be one of {sorted(_ROLLOUT_MODES)}: {self.required_rollout_mode!r}"),
                context={"entity": "ToolVersion", "field": "required_rollout_mode"},
            )
        if not isinstance(self.status, ToolVersionStatus):
            raise EntityValidationError(
                message=f"status must be ToolVersionStatus: {self.status!r}",
                context={"entity": "ToolVersion", "field": "status"},
            )
        for field_name, schema in (("input_schema", self.input_schema), ("output_schema", self.output_schema)):
            if schema and not (_JSON_SCHEMA_KEYWORDS & set(schema)):
                raise EntityValidationError(
                    message=(f"{field_name} 非空时须含 JSON Schema 关键词之一: {sorted(_JSON_SCHEMA_KEYWORDS)}"),
                    context={"entity": "ToolVersion", "field": field_name},
                )
        return True

    def can_transition_to(self, new_status: ToolVersionStatus) -> bool:
        """检查状态迁移是否合法（布尔探测，不抛异常）。

        Args:
            new_status: 目标状态

        Returns:
            合法返回 True
        """
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: ToolVersionStatus) -> None:
        """执行状态迁移（非法迁移抛 243）。

        戳记不在迁移内强制——三分规则由调用方组合原语实现：
        - 被新版本替代降级：transition_to(DEPRECATED) + stamp_last_stable(now)
        - 被回滚降级：transition_to(DEPRECATED) + clear_last_stable()
        - 灰度清场降级：transition_to(DEPRECATED)（不记戳）

        与 ToolExecution.transition_to 先例的差异：不携带 state_version 乐观锁
        自增（ToolVersionRepositoryPort 无 CAS 方法，原子性由 savepoint 保证）。

        Args:
            new_status: 目标状态

        Raises:
            EntityStateTransitionError: 迁移路径非法（EXCEPTION_243）
        """
        if not self.can_transition_to(new_status):
            raise EntityStateTransitionError(
                from_status=self.status.value,
                to_status=new_status.value,
                entity_type="ToolVersion",
                entity_id=str(self.version_id),
            )
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def stamp_last_stable(self, at: datetime | None = None) -> None:
        """记录"曾为 STABLE"时间戳（被新版本替代降级时调用——回滚候选依据）。

        Args:
            at: 时间戳（默认当前 UTC）
        """
        self.last_stable_at = at if at is not None else datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def clear_last_stable(self) -> None:
        """显式清空 last_stable_at（被回滚降级时调用——含残留戳清除）。

        业界 stable 指针原则：指针只在成功 promotion 时推进——被回滚放弃的
        版本（含经回滚恢复后再次被降级的残留戳持有者）退出缺省候选与显式
        目标集，第三次缺省回滚不会 ping-pong 复活。
        """
        self.last_stable_at = None
        self.updated_at = datetime.now(UTC)


__all__ = [
    "ToolVersion",
    "ToolVersionStatus",
    "VALID_TRANSITIONS",
]
