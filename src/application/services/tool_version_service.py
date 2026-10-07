"""应用层工具版本管理服务（Story 4-6 — 灰度发布与回滚核心编排）

ToolVersionService：R2 组合注入（repository + schema_validator + tool_registry +
event_publisher 四基础端口 + max_retained_versions 标量——禁止注入 infrastructure
Config 对象，组合根以 ToolVersionConfig.from_env() 解析后传标量）。

编排蓝图（Story Dev Notes「核心编排流程」的忠实实现）：
- register：双 Schema 兼容性校验（input≈backward / output≈forward）→
  RolloutPolicyService 分级决策（critical 拒 397 / major canary_only / minor any）
- publish：状态感知（PENDING=发起灰度[前置存在 STABLE]/直接全量[canary_only 禁]；
  CANARY=调档[同态]/promote 转正[毕业通道放行]）
- abort：放弃灰度（STABLE 不动）
- rollback：缺省目标 = last_stable_at 最新且排除本次被降级版本（防 ping-pong）；
  多行变更"先降级/清场、后提升"（partial unique index 逐语句校验）
- resolve：规范散列路由 + 惰性初始注册三分支
- retention：注册触发两级排序淘汰（VersionRetentionPlanner 领域纯函数）
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.domain.entities.tool import Tool
from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.events.base import DomainEvent
from src.domain.events.tool_version_events import (
    ToolRolledBack,
    ToolVersionPublished,
    ToolVersionRegistered,
)
from src.domain.exceptions import (
    EntityStateTransitionError,
    EntityValidationError,
)
from src.domain.exceptions.tool_schema_exceptions import ToolSchemaCompatibilityError
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionNotFoundError,
    ToolVersionRollbackError,
    ToolVersionTrafficWeightError,
)
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.tool_version_repository import (
    ToolVersionQuery,
    ToolVersionRepositoryPort,
)
from src.domain.services.tool_version_policy import (
    RolloutPolicyService,
    TrafficRouter,
    VersionRetentionPlanner,
)

logger = logging.getLogger(__name__)

# 发布权重域 (0,100]（服务层校验——实体存储域 [0,100] 供 PENDING=0 初始态）
_WEIGHT_MIN = 1
_WEIGHT_MAX = 100


class ToolVersionService:
    """工具版本管理编排服务（register/publish/abort/rollback/resolve/retention）。

    生命周期 SCOPED；多行状态变更的原子性由仓储 savepoint 语义保证
    （单元层仅断言多行 save 全部发生——原子断言唯一归属集成测试）。
    """

    def __init__(
        self,
        repository: ToolVersionRepositoryPort,
        schema_validator: SchemaValidatorPort,
        tool_registry: ToolRegistryServicePort,
        event_publisher: EventPublisher,
        max_retained_versions: int = 10,
    ) -> None:
        """初始化服务。

        Args:
            repository: 工具版本仓储端口
            schema_validator: Schema 兼容性校验端口（4.3 能力复用）
            tool_registry: 工具注册表端口（工具存在性前置 380）
            event_publisher: 领域事件发布端口（register/publish/abort/rollback
                成功路径发布对应事件；惰性初始注册不发——审计取舍见 Story 事件表）
            max_retained_versions: 版本保留上限标量（组合根从 ToolVersionConfig
                解析后传入——应用层禁止 import infrastructure）
        """
        self._repo = repository
        self._validator = schema_validator
        self._registry = tool_registry
        self._event_publisher = event_publisher
        self._max_retained = max_retained_versions

    async def _publish_event(self, event: DomainEvent) -> None:
        """发布领域事件（fail-soft：发布失败仅告警，不中断业务主流程）。

        EventPublisher 协议约定错误内部消化并返回 PublishResult——本方法
        仅对失败结果记 warning 日志（reliable 通道的可靠投递由 Outbox 保证）。
        """
        result = await self._event_publisher.publish(event)
        if not result.is_success:
            logger.warning("领域事件发布失败: event=%s error=%s", event.event_type, result.partial_error)

    # ------------------------------------------------------------------
    # register_version
    # ------------------------------------------------------------------

    async def register_version(
        self,
        tool_id: uuid.UUID,
        version: str,
        input_schema: dict,
        output_schema: dict,
    ) -> ToolVersion:
        """注册新版本（兼容性分级拦截）。"""
        self._registry.get_tool(tool_id=tool_id)  # 380 if 不存在

        existing = await self._repo.get_by_tool_and_version(tool_id, version)
        if existing is not None:
            raise ToolVersionAlreadyExistsError(tool_id=str(tool_id), version=version)

        stable = await self._find_stable(tool_id)
        if stable is not None:
            decision, breaking_summary = self._decide_rollout(stable, input_schema, output_schema)
            if not decision.allowed:
                raise ToolSchemaCompatibilityError(
                    tool_id=str(tool_id),
                    old_version=stable.version,
                    new_version=version,
                    breaking_changes=breaking_summary,
                )
            mode = decision.mode
        else:
            mode = "any"  # 首版本跳过兼容性校验
            breaking_summary = []

        tv = ToolVersion(
            tool_id=tool_id,
            version=version,
            input_schema=input_schema,
            output_schema=output_schema,
            required_rollout_mode=mode,
        )
        await self._repo.save(tv)
        await self._apply_retention(tool_id)
        await self._publish_event(
            ToolVersionRegistered(
                tool_id=tool_id,
                tool_version=version,
                required_rollout_mode=mode,
                breaking_summary=breaking_summary,
            )
        )
        logger.info("工具版本注册完成: tool=%s version=%s mode=%s", tool_id, version, mode)
        return tv

    # ------------------------------------------------------------------
    # publish_version（状态感知）
    # ------------------------------------------------------------------

    async def publish_version(
        self,
        tool_id: uuid.UUID,
        version: str,
        traffic_weight: int = 100,
    ) -> ToolVersion:
        """发布版本（灰度发起/调档/直接全量/promote 转正）。"""
        self._registry.get_tool(tool_id=tool_id)

        tv = await self._get_version_or_404(tool_id, version)
        if not _WEIGHT_MIN <= traffic_weight <= _WEIGHT_MAX:
            raise ToolVersionTrafficWeightError(
                tool_id=str(tool_id),
                version=version,
                traffic_weight=traffic_weight,
                conflict_reason=f"权重域 (0,100]，got {traffic_weight}",
            )
        # DEPRECATED 版本唯一恢复通道是 rollback 流程（Story 状态机矩阵约束）——
        # publish 双档（灰度/全量）均拒绝，且必须在任何实体改写前拦截
        # （避免失败路径污染仓储持有的共享引用）
        if tv.status is ToolVersionStatus.DEPRECATED:
            raise EntityStateTransitionError(
                from_status=ToolVersionStatus.DEPRECATED.value,
                to_status=ToolVersionStatus.CANARY.value if traffic_weight < _WEIGHT_MAX else ToolVersionStatus.STABLE.value,
                entity_type="ToolVersion",
                entity_id=str(version),
                message="DEPRECATED 版本禁止 publish（唯一恢复通道是 rollback 流程）",
            )

        from_status = tv.status
        if traffic_weight < _WEIGHT_MAX:
            # 灰度档（发起/调档）
            if tv.status is ToolVersionStatus.PENDING:
                active = await self._repo.list_active(tool_id)
                stable = next((v for v in active if v.status is ToolVersionStatus.STABLE), None)
                if stable is None:
                    raise ToolVersionTrafficWeightError(
                        tool_id=str(tool_id),
                        version=version,
                        conflict_reason="无 STABLE 版本不可发起灰度（二元流量分配前提）",
                    )
                canary = next((v for v in active if v.status is ToolVersionStatus.CANARY), None)
                if canary is not None and canary.version_id != tv.version_id:
                    raise ToolVersionTrafficWeightError(
                        tool_id=str(tool_id),
                        version=version,
                        conflict_reason=f"活跃 CANARY {canary.version} 并存冲突",
                    )
                tv.transition_to(ToolVersionStatus.CANARY)
            elif tv.status is ToolVersionStatus.CANARY:
                pass  # 调档（同态迁移——仅更新权重）
            else:
                tv.transition_to(ToolVersionStatus.CANARY)  # STABLE → 243
        else:
            # 全量档（直接全量/promote）
            if tv.status is ToolVersionStatus.PENDING and tv.required_rollout_mode == "canary_only":
                raise ToolVersionTrafficWeightError(
                    tool_id=str(tool_id),
                    version=version,
                    conflict_reason="canary_only 版本禁止 PENDING 直接全量（灰度毕业通道放行）",
                )
            if tv.status in (ToolVersionStatus.PENDING, ToolVersionStatus.CANARY):
                # 直接全量时不得残留活跃灰度（另一版本的 CANARY 会继续承接流量，
                # 造成新旧分流——先 promote/abort 清场再全量）
                active_canary = await self._find_canary(tool_id)
                if active_canary is not None and active_canary.version_id != tv.version_id:
                    raise ToolVersionTrafficWeightError(
                        tool_id=str(tool_id),
                        version=version,
                        conflict_reason=f"活跃 CANARY {active_canary.version} 并存冲突（先 promote/abort 清场）",
                    )
                # 先降级旧 STABLE（partial index 逐语句校验的顺序契约）
                old_stable = await self._find_stable(tool_id)
                tv.transition_to(ToolVersionStatus.STABLE)
                tv.traffic_weight = _WEIGHT_MAX
                if old_stable is not None and old_stable.version_id != tv.version_id:
                    old_stable.transition_to(ToolVersionStatus.DEPRECATED)
                    old_stable.stamp_last_stable()
                    old_stable.traffic_weight = 0
                    await self._repo.save(old_stable)
            else:
                tv.transition_to(ToolVersionStatus.STABLE)  # STABLE → 243

        if from_status is ToolVersionStatus.PENDING and traffic_weight < _WEIGHT_MAX:
            tv.traffic_weight = traffic_weight
        elif traffic_weight < _WEIGHT_MAX:
            tv.traffic_weight = traffic_weight  # 调档更新权重
        saved = await self._repo.save(tv)
        await self._publish_event(
            ToolVersionPublished(
                tool_id=tool_id,
                tool_version=saved.version,
                from_status=from_status.value,
                to_status=saved.status.value,
                traffic_weight=saved.traffic_weight,
            )
        )
        logger.info(
            "工具版本发布: tool=%s version=%s %s→%s w=%s",
            tool_id,
            version,
            from_status.value,
            saved.status.value,
            traffic_weight,
        )
        return saved

    # ------------------------------------------------------------------
    # abort_canary
    # ------------------------------------------------------------------

    async def abort_canary(self, tool_id: uuid.UUID) -> ToolVersion:
        """放弃灰度（活跃 CANARY → DEPRECATED，不记戳；STABLE 不动）。"""
        self._registry.get_tool(tool_id=tool_id)
        canary = await self._find_canary(tool_id)
        if canary is None:
            raise EntityStateTransitionError(
                from_status="none",
                to_status="deprecated",
                entity_type="ToolVersion",
                entity_id=str(tool_id),
            )
        canary.transition_to(ToolVersionStatus.DEPRECATED)
        canary.traffic_weight = 0
        saved = await self._repo.save(canary)
        await self._publish_event(
            ToolVersionPublished(
                tool_id=tool_id,
                tool_version=saved.version,
                from_status=ToolVersionStatus.CANARY.value,
                to_status=ToolVersionStatus.DEPRECATED.value,
                traffic_weight=0,
            )
        )
        logger.info("放弃灰度: tool=%s version=%s", tool_id, saved.version)
        return saved

    # ------------------------------------------------------------------
    # rollback
    # ------------------------------------------------------------------

    async def rollback(
        self,
        tool_id: uuid.UUID,
        target_version: str | None = None,
        trigger: str = "api",
    ) -> ToolVersion:
        """一键回滚（防 ping-pong 缺省目标 + 多行变更先降级后提升）。"""
        if trigger not in ("api", "manual"):
            raise EntityValidationError(
                message=f"trigger must be one of ['api', 'manual']: {trigger!r}",
                context={"entity": "ToolVersion", "field": "trigger"},
            )
        self._registry.get_tool(tool_id=tool_id)

        current = await self._find_stable(tool_id)
        if current is None:
            raise ToolVersionRollbackError(tool_id=str(tool_id), reason="no_stable_history")

        deprecated = await self._repo.list_by_query(
            ToolVersionQuery(tool_id=tool_id, status=ToolVersionStatus.DEPRECATED, limit=10**9)
        )
        stamped = [tv for tv in deprecated if tv.last_stable_at is not None]

        if target_version is None:
            candidates = [tv for tv in stamped if tv.version != current.version]
            if not candidates:
                raise ToolVersionRollbackError(tool_id=str(tool_id), reason="no_stable_history")
            # key 兜底 datetime.min：候选集已过滤 last_stable_at 非空，兜底仅为
            # 类型收窄（datetime | None → datetime），语义上不可达
            target = max(
                candidates,
                key=lambda tv: tv.last_stable_at or datetime.min.replace(tzinfo=UTC),
            )
        else:
            target = await self._get_version_or_404(tool_id, target_version)
            if target.status is not ToolVersionStatus.DEPRECATED or target.last_stable_at is None:
                raise ToolVersionRollbackError(
                    tool_id=str(tool_id),
                    target_version=target_version,
                    reason="not_stable_before",
                )

        # 先降级/清场（partial index 顺序契约），后提升
        deprecated_versions = [current.version]
        current.transition_to(ToolVersionStatus.DEPRECATED)
        current.clear_last_stable()
        current.traffic_weight = 0
        await self._repo.save(current)

        canary = await self._find_canary(tool_id)
        if canary is not None and canary.version_id != target.version_id:
            canary.transition_to(ToolVersionStatus.DEPRECATED)
            canary.traffic_weight = 0
            await self._repo.save(canary)
            deprecated_versions.append(canary.version)

        target.transition_to(ToolVersionStatus.STABLE)
        target.traffic_weight = _WEIGHT_MAX
        saved = await self._repo.save(target)
        await self._publish_event(
            ToolRolledBack(
                tool_id=tool_id,
                from_version=current.version,
                to_version=saved.version,
                trigger=trigger,
                deprecated_versions=deprecated_versions,
            )
        )
        logger.info(
            "工具版本回滚: tool=%s %s→%s trigger=%s",
            tool_id,
            current.version,
            saved.version,
            trigger,
        )
        return saved

    # ------------------------------------------------------------------
    # resolve_version
    # ------------------------------------------------------------------

    async def resolve_version(
        self,
        tool_id: uuid.UUID,
        requested_version: str | None = None,
        route_key: str | None = None,
    ) -> ToolVersion:
        """执行链版本路由（规范散列 + 惰性初始注册三分支）。"""
        if requested_version is not None:
            return await self._get_version_or_404(tool_id, requested_version)

        active = await self._repo.list_active(tool_id)
        canary = next((v for v in active if v.status is ToolVersionStatus.CANARY), None)
        stable = next((v for v in active if v.status is ToolVersionStatus.STABLE), None)

        if canary is not None and stable is not None:
            chosen = (
                canary
                if TrafficRouter.route(route_key or "", canary.version, canary.traffic_weight, stable.version) == canary.version
                else stable
            )
            return chosen
        if stable is not None:
            return stable

        # 三分支：无活跃版本
        total = await self._repo.count(ToolVersionQuery(tool_id=tool_id))
        if total == 0:
            # 惰性初始注册（幂等：并发撞 431 时重读返回既有）
            tool = self._registry.get_tool(tool_id=tool_id)
            return await self._lazy_register_initial(tool)
        raise ToolVersionNotFoundError(tool_id=str(tool_id), version="active")

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    async def list_versions(self, tool_id: uuid.UUID) -> list[ToolVersion]:
        """列出全部版本（注册时间升序）。"""
        self._registry.get_tool(tool_id=tool_id)
        return await self._repo.list_by_query(ToolVersionQuery(tool_id=tool_id, limit=10**9))

    async def get_version_traffic(self, tool_id: uuid.UUID) -> dict[str, Any]:
        """当前流量分布视图。"""
        self._registry.get_tool(tool_id=tool_id)
        active = await self._repo.list_active(tool_id)
        stable = next((v for v in active if v.status is ToolVersionStatus.STABLE), None)
        canary = next((v for v in active if v.status is ToolVersionStatus.CANARY), None)
        return {
            "stable_version": stable.version if stable else None,
            "canary_version": canary.version if canary else None,
            "canary_weight": canary.traffic_weight if canary else None,
        }

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------

    async def _find_stable(self, tool_id: uuid.UUID) -> ToolVersion | None:
        """取当前 STABLE（至多一个——partial index 守护）。"""
        active = await self._repo.list_active(tool_id)
        return next((v for v in active if v.status is ToolVersionStatus.STABLE), None)

    async def _find_canary(self, tool_id: uuid.UUID) -> ToolVersion | None:
        """取活跃 CANARY。"""
        active = await self._repo.list_active(tool_id)
        return next((v for v in active if v.status is ToolVersionStatus.CANARY), None)

    async def _get_version_or_404(self, tool_id: uuid.UUID, version: str) -> ToolVersion:
        """取版本或抛 430。"""
        tv = await self._repo.get_by_tool_and_version(tool_id, version)
        if tv is None:
            raise ToolVersionNotFoundError(tool_id=str(tool_id), version=version)
        return tv

    def _decide_rollout(self, stable: ToolVersion, input_schema: dict, output_schema: dict) -> tuple[Any, list[dict]]:
        """双 Schema 兼容性校验 + 分级决策（领域纯函数）。

        Returns:
            (RolloutDecision, breaking_summary)——决策结果与破坏性变更摘要
            （拒绝路径 397 context 与 Registered 事件 payload 复用同一份数据）
        """
        compat_in = self._validator.validate_schema_compatibility(stable.input_schema, input_schema)  # ≈backward
        compat_out = self._validator.validate_schema_compatibility(stable.output_schema, output_schema)  # ≈forward
        breaking_summary = [
            dataclasses.asdict(b) if dataclasses.is_dataclass(b) else b
            for b in (*compat_in.breaking_changes, *compat_out.breaking_changes)
        ]
        severities = [b.severity for b in (*compat_in.breaking_changes, *compat_out.breaking_changes)]
        order: dict[str, int] = {"critical": 3, "major": 2, "minor": 1}
        max_severity: str | None = max(severities, key=lambda s: order.get(str(s), 0)) if severities else None
        count = len(severities)  # 计数仅作文案——双重上报实态下非稳定契约
        return RolloutPolicyService.decide(max_severity, count), breaking_summary

    async def _apply_retention(self, tool_id: uuid.UUID) -> None:
        """注册触发的保留策略淘汰。"""
        versions = await self._repo.list_by_query(ToolVersionQuery(tool_id=tool_id, limit=10**9))
        for version_id in VersionRetentionPlanner.plan(versions, self._max_retained):
            await self._repo.delete(version_id)

    async def _lazy_register_initial(self, tool: Tool) -> ToolVersion:
        """惰性初始注册（以 Tool.version 建立 STABLE；431 冲突重读幂等）。"""
        tv = ToolVersion(
            tool_id=tool.tool_id,
            version=tool.version,
            input_schema=dict(tool.input_schema),
            output_schema=dict(tool.output_schema),
            status=ToolVersionStatus.STABLE,
            traffic_weight=_WEIGHT_MAX,
        )
        try:
            return await self._repo.save(tv)
        except ToolVersionAlreadyExistsError:
            existing = await self._repo.get_by_tool_and_version(tool.tool_id, tool.version)
            if existing is not None:
                return existing
            raise


__all__ = ["ToolVersionService"]
