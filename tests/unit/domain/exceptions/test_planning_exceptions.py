"""Story 6-1 — planning 子域异常单元测试（480~482 新子域段 (480,489) 开段）。

TDD 循环 B 载体：构造/context 领域上下文/to_dict/cause 链/编码唯一性。
五件套齐备性由 test_code_ranges.py（Rule 1~5）与
test_error_code_uniqueness.py（3 项）联动承载——本文件聚焦异常类自身行为。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    PlanningExecutionError,
    PlanningNotFoundError,
    PlanningStateError,
)
from src.domain.exceptions.business_exceptions import BusinessException


class TestPlanningExceptions:
    """planning 子域三异常（480~482）。"""

    def test_planning_not_found_code_480(self) -> None:
        """480 编码 + 404 语义（plan_id 不存在）。"""
        exc = PlanningNotFoundError(plan_id="plan-123")
        assert exc.code == "EXCEPTION_480"
        assert exc.context["plan_id"] == "plan-123"

    def test_planning_execution_error_code_481(self) -> None:
        """481 编码（全流程失败终态——RunBlmPlanningUseCase 终态组装处抛出）。"""
        exc = PlanningExecutionError(agent_id="agent-1", plan_id="plan-123", reason="全部 8 步降级")
        assert exc.code == "EXCEPTION_481"
        assert exc.context["plan_id"] == "plan-123"
        assert exc.context["agent_id"] == "agent-1"
        assert "8 步" in exc.context["reason"]

    def test_planning_state_error_code_482(self) -> None:
        """482 编码（状态机非法推进——已激活：同 plan_id 重跑守卫 R1-5）。"""
        exc = PlanningStateError(plan_id="plan-123", transition="market_insight→performance_gap")
        assert exc.code == "EXCEPTION_482"
        assert exc.context["transition"] == "market_insight→performance_gap"

    def test_business_exception_inheritance(self) -> None:
        """语义继承 BusinessException 基类（非内置 Exception——红线）。"""
        assert issubclass(PlanningNotFoundError, BusinessException)
        assert issubclass(PlanningExecutionError, BusinessException)
        assert issubclass(PlanningStateError, BusinessException)

    def test_to_dict_shape(self) -> None:
        """to_dict 含 code/message/context 三键（DomainError 契约）。"""
        exc = PlanningNotFoundError(plan_id="plan-1")
        payload = exc.to_dict()
        assert payload["code"] == "EXCEPTION_480"
        assert payload["message"]
        assert payload["context"]["plan_id"] == "plan-1"

    def test_cause_chain(self) -> None:
        """cause 链构造（底层异常上下文不丢失）。"""
        root = RuntimeError("底层存储故障")
        exc = PlanningExecutionError(agent_id="a", plan_id="p", reason="级联失败", cause=root)
        assert exc.cause is root
        payload = exc.to_dict()
        assert payload.get("cause") is not None

    def test_message_does_not_leak_internals(self) -> None:
        """静态消息不含内部实现细节（领域契约——消息模板 + context 分离）。"""
        exc = PlanningExecutionError(agent_id="a", plan_id="p", reason="x" * 300)
        # message 是静态领域文案；动态细节进 context（reason 截断防泄漏面）
        assert exc.message == "规划执行失败"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并（调用方附加领域上下文）。"""
        exc = PlanningNotFoundError(plan_id="p", context_extra={"source": "cli"})
        assert exc.context["source"] == "cli"

    def test_codes_unique_across_planning(self) -> None:
        """三异常编码互异（480/481/482）。"""
        codes = {PlanningNotFoundError.code, PlanningExecutionError.code, PlanningStateError.code}
        assert codes == {"EXCEPTION_480", "EXCEPTION_481", "EXCEPTION_482"}


class TestPlanningExceptionRegistration:
    """五件套注册面（_code_ranges/HTTP 映射/子域段——联动校验）。"""

    def test_code_ranges_has_planning_segment(self) -> None:
        """CODE_RANGES 含 planning 段 (480,489)（第八段——410/420/430/440/450/460/470 先例链）。"""
        from src.domain.exceptions._code_ranges import CODE_RANGES

        assert CODE_RANGES.get("planning") == (480, 489)

    def test_planning_range_not_overlapping_financial(self) -> None:
        """planning 段与 financial 段 (470,479) 不重叠（双重成文预留不侵占）。"""
        from src.domain.exceptions._code_ranges import CODE_RANGES

        planning_start, planning_end = CODE_RANGES["planning"]
        financial_start, financial_end = CODE_RANGES["financial"]
        assert planning_start > financial_end, "planning 段不得与 financial 预留段重叠"

    def test_class_to_subdomain_registered(self) -> None:
        """_CLASS_TO_SUBDOMAIN 三条齐备。"""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        assert _CLASS_TO_SUBDOMAIN.get("PlanningNotFoundError") == "planning"
        assert _CLASS_TO_SUBDOMAIN.get("PlanningExecutionError") == "planning"
        assert _CLASS_TO_SUBDOMAIN.get("PlanningStateError") == "planning"

    def test_http_map_registered(self) -> None:
        """EXCEPTION_HTTP_MAP 三异常登记（精确注册 + 值级断言——改挂状态码即红，R1-9④）。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert PlanningNotFoundError in EXCEPTION_HTTP_MAP
        assert PlanningExecutionError in EXCEPTION_HTTP_MAP
        assert PlanningStateError in EXCEPTION_HTTP_MAP
        assert EXCEPTION_HTTP_MAP[PlanningNotFoundError] == status.HTTP_404_NOT_FOUND
        assert EXCEPTION_HTTP_MAP[PlanningExecutionError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[PlanningStateError] == status.HTTP_409_CONFLICT

    def test_no_placeholder_codes(self) -> None:
        """具体类零占位编码（EXCEPTION_000/_2XX 族——Rule 3）。"""
        for exc_cls in (PlanningNotFoundError, PlanningExecutionError, PlanningStateError):
            assert exc_cls.code not in {"EXCEPTION_000", "EXCEPTION_1XX", "EXCEPTION_2XX", "EXCEPTION_3XX"}


@pytest.mark.parametrize(
    "exc_cls",
    [PlanningNotFoundError, PlanningExecutionError, PlanningStateError],
    ids=["480", "481", "482"],
)
def test_exception_is_domain_error_subclass(exc_cls: type) -> None:
    """三异常均为 DomainError 子类（统一异常体系根）。"""
    from src.domain.exceptions.base_exceptions import DomainError

    assert issubclass(exc_cls, DomainError)


class TestCheckpointExceptions:
    """Story 6-3 — Checkpoint 异常（483/484；485 不设码——OD-7）。

    延迟 import 形态：类未定义时红 = 运行期 ImportError（R2B-13 owning 落位）。
    """

    def test_checkpoint_creation_error_code_483(self) -> None:
        """483 编码 + context 领域上下文（五步编排强制环节失败——含压缩终态门禁）。"""
        from src.domain.exceptions import CheckpointCreationError

        exc = CheckpointCreationError(
            plan_id="plan-1",
            checkpoint_no="CP-1",
            reason="压缩二次路径耗尽仍不达标（编排层终态门禁）",
        )

        assert exc.code == "EXCEPTION_483"
        assert exc.context["plan_id"] == "plan-1"
        assert exc.context["checkpoint_no"] == "CP-1"
        assert exc.context["reason"].startswith("压缩二次路径耗尽")

    def test_checkpoint_creation_error_default_message_combines_reason(self) -> None:
        """默认 message 双形态（R1 审查 FR-3——有意变更留痕）。

        reason 非空 → 默认 message 组合根因（CLI/API 人机消费面可见——实测
        静态文案使 483 真实根因对操作者不可见）；reason 空 → 回落类静态文案。
        context["reason"] 结构化字段两形态均保持不变。
        """
        from src.domain.exceptions import CheckpointCreationError

        with_reason = CheckpointCreationError(plan_id="p", checkpoint_no="CP-1", reason="持久化笔记失败: LLM 未配置")
        assert with_reason.message == "Checkpoint 创建失败: 持久化笔记失败: LLM 未配置"
        assert with_reason.message.startswith("Checkpoint 创建失败")
        assert "持久化笔记失败" in with_reason.message

        without_reason = CheckpointCreationError(plan_id="p", checkpoint_no="CP-1")
        assert without_reason.message == "Checkpoint 创建失败"

        overridden = CheckpointCreationError(plan_id="p", checkpoint_no="CP-1", reason="r", message="自定义消息")
        assert overridden.message == "自定义消息"

    def test_checkpoint_creation_error_to_dict_shape(self) -> None:
        """to_dict 含 code/message/context 三键（DomainError 契约）。"""
        from src.domain.exceptions import CheckpointCreationError

        payload = CheckpointCreationError(plan_id="p", checkpoint_no="CP-1", reason="r").to_dict()
        assert payload["code"] == "EXCEPTION_483"
        assert payload["message"]
        assert payload["context"]["checkpoint_no"] == "CP-1"

    def test_checkpoint_integrity_error_code_484(self) -> None:
        """484 编码（引用缺失守卫 + checksum 校验失败双场景——AC-2/AC-3）。"""
        from src.domain.exceptions import CheckpointIntegrityError

        exc = CheckpointIntegrityError(
            session_id="blm-checkpoint-plan-1:CP-1",
            checkpoint_no="CP-1",
            reason="checksum_mismatch",
        )

        assert exc.code == "EXCEPTION_484"
        assert exc.context["session_id"] == "blm-checkpoint-plan-1:CP-1"
        assert exc.context["checkpoint_no"] == "CP-1"

    def test_checkpoint_integrity_error_cause_chain(self) -> None:
        """cause 链透传（to_dict 含 cause——底层异常可追溯）。"""
        from src.domain.exceptions import CheckpointIntegrityError

        root = ValueError("底层损坏")
        exc = CheckpointIntegrityError(session_id="s", checkpoint_no="CP-1", reason="r", cause=root)

        assert exc.cause is root
        assert exc.to_dict().get("cause") is not None

    def test_checkpoint_exceptions_subclass_business_error(self) -> None:
        """两异常均为 BusinessException 子类（planning 段语义继承）。"""
        from src.domain.exceptions import CheckpointCreationError, CheckpointIntegrityError

        assert issubclass(CheckpointCreationError, BusinessException)
        assert issubclass(CheckpointIntegrityError, BusinessException)

    def test_checkpoint_exception_codes_distinct_from_existing(self) -> None:
        """483/484 与既有 480/481/482 编码互异（编码唯一性联动由 test_error_code_uniqueness 承载）。"""
        from src.domain.exceptions import CheckpointCreationError, CheckpointIntegrityError

        existing = {PlanningNotFoundError.code, PlanningExecutionError.code, PlanningStateError.code}
        assert CheckpointCreationError.code == "EXCEPTION_483"
        assert CheckpointIntegrityError.code == "EXCEPTION_484"
        assert CheckpointCreationError.code not in existing
        assert CheckpointIntegrityError.code not in existing

    def test_http_map_registered_value_level(self) -> None:
        """EXCEPTION_HTTP_MAP 值级断言（483→500 / 484→409——改挂状态码即红）。"""
        from fastapi import status

        from src.domain.exceptions import CheckpointCreationError, CheckpointIntegrityError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[CheckpointCreationError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[CheckpointIntegrityError] == status.HTTP_409_CONFLICT

    def test_class_registry_registered_in_code_ranges(self) -> None:
        """_CLASS_TO_SUBDOMAIN 注册（planning 子域——码段校验 Rule 联动）。"""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        assert _CLASS_TO_SUBDOMAIN["CheckpointCreationError"] == "planning"
        assert _CLASS_TO_SUBDOMAIN["CheckpointIntegrityError"] == "planning"

    def test_485_not_occupied(self) -> None:
        """485 不设码钦定（OD-7——独立码语义冗余；编排层终态门禁由 483 承载）。"""
        from src.domain.exceptions.planning_exceptions import __all__ as planning_all

        assert "CheckpointCompressionError" not in planning_all


class TestCheckpointRecoveryExceptions:
    """Story 6-6 — 恢复执行面异常（486/487——planning 段 486-489 预留段取码）。

    延迟 import 形态：类未定义时红 = 运行期 ImportError（6-3 同款 owning 落位）。
    """

    def test_checkpoint_recovery_error_code_486(self) -> None:
        """486 编码 + context 领域上下文（恢复编排强制环节失败——fail-loud）。"""
        from src.domain.exceptions import CheckpointRecoveryError

        exc = CheckpointRecoveryError(
            plan_id="plan-recovery-1",
            checkpoint_no="CP-3",
            reason="恢复记录落库失败: Redis 写入超时",
        )

        assert exc.code == "EXCEPTION_486"
        assert exc.context["plan_id"] == "plan-recovery-1"
        assert exc.context["checkpoint_no"] == "CP-3"
        assert exc.context["reason"].startswith("恢复记录落库失败")

    def test_checkpoint_recovery_error_default_message_combines_reason(self) -> None:
        """486 默认 message 双形态（R1-F3 组合语义先例直接继承——根因对 CLI/API 操作者可见）。"""
        from src.domain.exceptions import CheckpointRecoveryError

        with_reason = CheckpointRecoveryError(plan_id="p", checkpoint_no="CP-1", reason="修正应用落库失败: 连接中断")
        assert with_reason.message == "Checkpoint 恢复执行失败: 修正应用落库失败: 连接中断"
        assert with_reason.message.startswith("Checkpoint 恢复执行失败")

        without_reason = CheckpointRecoveryError(plan_id="p", checkpoint_no="CP-1")
        assert without_reason.message == "Checkpoint 恢复执行失败"

        overridden = CheckpointRecoveryError(plan_id="p", checkpoint_no="CP-1", reason="r", message="自定义消息")
        assert overridden.message == "自定义消息"

    def test_checkpoint_recovery_error_cause_chain(self) -> None:
        """486 cause 链透传（except StorageError 包装——底层异常可追溯）。"""
        from src.domain.exceptions import CheckpointRecoveryError

        root = RuntimeError("Redis connection reset")
        exc = CheckpointRecoveryError(plan_id="p", checkpoint_no="CP-1", reason="save 失败", cause=root)

        assert exc.cause is root
        assert exc.to_dict().get("cause") is not None
        assert exc.to_dict()["code"] == "EXCEPTION_486"

    def test_recovery_mode_conflict_error_code_487(self) -> None:
        """487 编码（模式强制执法拒绝——or.md L622 不变约束承载）。"""
        from src.domain.exceptions import RecoveryModeConflictError

        exc = RecoveryModeConflictError(recommended_mode="Replay", requested_mode="Override")

        assert exc.code == "EXCEPTION_487"
        assert exc.context["recommended_mode"] == "Replay"
        assert exc.context["requested_mode"] == "Override"

    def test_recovery_mode_conflict_message_carries_dual_modes(self) -> None:
        """487 message 携带建议/请求双模式（可理解性裁决面——OD-6）。"""
        from src.domain.exceptions import RecoveryModeConflictError

        exc = RecoveryModeConflictError(recommended_mode="Replay", requested_mode="Override")
        assert "Replay" in exc.message, f"message 缺建议模式（实测={exc.message!r}）"
        assert "Override" in exc.message, f"message 缺请求模式（实测={exc.message!r}）"
        assert "强制 Replay" in exc.message or "强制" in exc.message, "message 缺不变约束语义"

    def test_recovery_exceptions_subclass_business_error(self) -> None:
        """两异常均为 BusinessException 子类（planning 段语义继承）。"""
        from src.domain.exceptions import CheckpointRecoveryError, RecoveryModeConflictError

        assert issubclass(CheckpointRecoveryError, BusinessException)
        assert issubclass(RecoveryModeConflictError, BusinessException)

    def test_recovery_exception_codes_distinct_and_reserved_range(self) -> None:
        """486/487 与既有码互异且落预留段（486-489 留 6-6——485 空洞+488/489 残留维持）。"""
        from src.domain.exceptions import CheckpointRecoveryError, RecoveryModeConflictError

        existing = {
            PlanningNotFoundError.code,
            PlanningExecutionError.code,
            PlanningStateError.code,
            "EXCEPTION_483",
            "EXCEPTION_484",
        }
        assert CheckpointRecoveryError.code == "EXCEPTION_486"
        assert RecoveryModeConflictError.code == "EXCEPTION_487"
        assert CheckpointRecoveryError.code not in existing
        assert RecoveryModeConflictError.code not in existing

    def test_recovery_exception_http_map_registered_value_level(self) -> None:
        """EXCEPTION_HTTP_MAP 值级断言（486→500 / 487→409——改挂状态码即红）。"""
        from fastapi import status

        from src.domain.exceptions import CheckpointRecoveryError, RecoveryModeConflictError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[CheckpointRecoveryError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[RecoveryModeConflictError] == status.HTTP_409_CONFLICT

    def test_recovery_exception_class_registry_registered(self) -> None:
        """_CLASS_TO_SUBDOMAIN 注册（planning 子域——码段校验 Rule 联动）。"""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        assert _CLASS_TO_SUBDOMAIN["CheckpointRecoveryError"] == "planning"
        assert _CLASS_TO_SUBDOMAIN["RecoveryModeConflictError"] == "planning"

    def test_485_hole_and_488_489_reserved_maintained(self) -> None:
        """485 段内空洞维持 + 488/489 继续预留（OD-7——占 486/487 后残留位零占用）。"""
        from src.domain.exceptions.planning_exceptions import __all__ as planning_all

        occupied = {str(number) for number in range(480, 490) if f"EXCEPTION_{number}" in _occupied_code_literals()}
        assert occupied == {"480", "481", "482", "483", "484", "486", "487"}, (
            f"planning 段实占码实测={sorted(occupied)} 期望 480-484+486/487（485 空洞+488/489 预留维持——OD-7）"
        )
        assert len(planning_all) >= 7, "planning 导出面应含 7 类（480-484+486/487）"


def _occupied_code_literals() -> set[str]:
    """planning 异常模块内实占的 EXCEPTION_nnn 字面量集合（485 空洞/488-489 预留判定基面）。"""
    import inspect

    from src.domain.exceptions import planning_exceptions

    source = inspect.getsource(planning_exceptions)
    found: set[str] = set()
    for number in range(480, 490):
        if f'EXCEPTION_{number}"' in source or f"EXCEPTION_{number}'" in source:
            found.add(f"EXCEPTION_{number}")
    return found
