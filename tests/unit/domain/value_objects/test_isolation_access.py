"""Story 5.5: 三重隔离判定核心单元测试（IsolationResource + 判定矩阵纯函数）

覆盖 AC-1（三重隔离判定核心——domain 纯函数矩阵）:
- IsolationResource 恰 11 成员两归属类（9 private + 2 shared）+ resource_is_private 逐成员
- AccessOperation / IsolationViolationKind 枚举完备性
- IsolationAccessDecision 不变量（allowed↔violation 互斥——242）
- decide_isolation_access 矩阵全格（MVP 三级 × 三类代表资源 × 读写 × 跨/自身 36 格
  + shared+self 格 + L1 前向格——矩阵从 ISOLATION_POLICIES 策略字段派生）
- decide_tool_access 工具白名单判定（L4 严格白名单 / L3·L2 共享池）
- 矩阵派生锚（monkeypatch 策略维度翻转 → 判定随动——禁等级硬编码证据）

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_isolation_access.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.isolation_access import (
    AccessOperation,
    IsolationAccessDecision,
    IsolationResource,
    IsolationViolationKind,
    decide_isolation_access,
    decide_tool_access,
    resource_is_private,
)
from src.domain.value_objects.isolation_policy import (
    ISOLATION_POLICIES,
    DataIsolationMode,
    IsolationPolicy,
    get_isolation_policy,
)

_MVP_LEVELS = (IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB)


class TestIsolationResourceEnum:
    """IsolationResource 11 成员两归属类（Agent 命名空间私有 ×9 + 协作共享面 ×2）。"""

    def test_exactly_eleven_members(self) -> None:
        """恰 11 成员（值小写下划线形态——对齐 DataIsolationMode 命名风格）。"""
        assert {member.value for member in IsolationResource} == {
            "profile",
            "system_prompt",
            "workflow_context",
            "agent_state",
            "isolation_state",
            "session",
            "sandbox_session",
            "tool_execution_history",
            "memory",
            "blackboard",
            "shared_workspace",
        }

    def test_str_enum_mixin(self) -> None:
        """str 混入（序列化直传 JSON——对齐 IsolationLevel/DataIsolationMode 形态）。"""
        assert IsolationResource.PROFILE == "profile"
        assert isinstance(IsolationResource.PROFILE, str)

    @pytest.mark.parametrize(
        ("resource", "expected_private"),
        [
            (IsolationResource.PROFILE, True),
            (IsolationResource.SYSTEM_PROMPT, True),
            (IsolationResource.WORKFLOW_CONTEXT, True),
            (IsolationResource.AGENT_STATE, True),
            (IsolationResource.ISOLATION_STATE, True),
            (IsolationResource.SESSION, True),
            (IsolationResource.SANDBOX_SESSION, True),
            (IsolationResource.TOOL_EXECUTION_HISTORY, True),
            (IsolationResource.MEMORY, True),
            (IsolationResource.BLACKBOARD, False),
            (IsolationResource.SHARED_WORKSPACE, False),
        ],
        ids=[
            "profile",
            "system_prompt",
            "workflow_context",
            "agent_state",
            "isolation_state",
            "session",
            "sandbox_session",
            "tool_execution_history",
            "memory",
            "blackboard",
            "shared_workspace",
        ],
    )
    def test_resource_is_private_per_member(self, resource: IsolationResource, expected_private: bool) -> None:
        """归属分类逐成员断言（9 True + 2 False——矩阵第 1/2 步分类依据）。"""
        assert resource_is_private(resource) is expected_private


class TestOperationAndViolationEnums:
    """AccessOperation 与 IsolationViolationKind 枚举完备性。"""

    def test_access_operation_two_values(self) -> None:
        """读写两值（写涵盖增删改——MVP 不细分）。"""
        assert {op.value for op in AccessOperation} == {"read", "write"}

    def test_isolation_violation_kind_two_values(self) -> None:
        """violation 两值（对应 448/449 分码轴）。"""
        assert {kind.value for kind in IsolationViolationKind} == {"access_violation", "operation_forbidden"}


class TestIsolationAccessDecision:
    """IsolationAccessDecision 决策对象不变量（242——配置互斥）。"""

    def test_frozen_dataclass(self) -> None:
        """frozen（决策对象不可变——纯函数返回值安全共享；Any 变量调用
        规避 mypy 对 frozen 赋值的静态拒绝——运行时行为本身就是要测的）。"""
        decision: Any = IsolationAccessDecision(allowed=True, violation=None, reason="测试")
        with pytest.raises(AttributeError):
            decision.allowed = False

    def test_allowed_with_violation_rejected(self) -> None:
        """allowed=True 带 violation → 242（互斥不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationAccessDecision(
                allowed=True,
                violation=IsolationViolationKind.ACCESS_VIOLATION,
                reason="矛盾决策",
            )
        assert exc_info.value.code == "EXCEPTION_242"

    def test_denied_without_violation_rejected(self) -> None:
        """allowed=False 无 violation → 242（拒绝必有 violation 归属）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationAccessDecision(allowed=False, violation=None, reason="矛盾决策")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_valid_decision_fields(self) -> None:
        """合法决策三件套字段（allowed/violation/reason——放行 violation=None）。"""
        allowed_decision = IsolationAccessDecision(allowed=True, violation=None, reason="放行依据")
        denied_decision = IsolationAccessDecision(
            allowed=False, violation=IsolationViolationKind.OPERATION_FORBIDDEN, reason="拒绝依据"
        )
        assert allowed_decision.violation is None
        assert denied_decision.allowed is False
        assert denied_decision.reason == "拒绝依据"


class TestDecideIsolationAccessMatrix:
    """decide_isolation_access 判定矩阵全格（MVP 三级 36 格 + shared+self 格语义）。"""

    @pytest.mark.parametrize("level", _MVP_LEVELS, ids=["L4", "L3", "L2"])
    @pytest.mark.parametrize(
        "resource",
        [IsolationResource.PROFILE, IsolationResource.AGENT_STATE, IsolationResource.BLACKBOARD],
        ids=["profile", "agent_state", "blackboard"],
    )
    @pytest.mark.parametrize("operation", [AccessOperation.READ, AccessOperation.WRITE], ids=["read", "write"])
    @pytest.mark.parametrize("cross_agent", [True, False], ids=["cross", "self"])
    def test_matrix_cell(
        self, level: IsolationLevel, resource: IsolationResource, operation: AccessOperation, cross_agent: bool
    ) -> None:
        """矩阵逐格（3 级 × 3 资源 × 2 操作 × 2 主体 = 36 格——需求语义断言）。

        矩阵三步（需求规格面）: shared → 读放行/写按 data_isolation；
        private+cross → 拒；private+self → 放行。shared 面不分 cross/self。
        """
        policy = get_isolation_policy(level)
        decision = decide_isolation_access(policy, cross_agent=cross_agent, resource=resource, operation=operation)
        if resource is IsolationResource.BLACKBOARD:  # shared 类代表
            if operation is AccessOperation.READ:
                assert decision.allowed is True, f"{level}/{resource}/{operation}/cross={cross_agent} 共享读应放行"
                assert decision.violation is None
            else:
                expected_allowed = policy.data_isolation in (DataIsolationMode.FREE_WRITE, DataIsolationMode.FULL_SHARED)
                assert decision.allowed is expected_allowed, (
                    f"{level}/{resource}/{operation}/cross={cross_agent} 共享写与 data_isolation={policy.data_isolation} 漂移"
                )
                if expected_allowed:
                    assert decision.violation is None
                else:
                    assert decision.violation is IsolationViolationKind.OPERATION_FORBIDDEN
        elif cross_agent:  # private + cross（含 shared+self 格的 cross 侧对照）
            assert decision.allowed is False, f"{level}/{resource}/{operation}/cross 应拒绝"
            assert decision.violation is IsolationViolationKind.ACCESS_VIOLATION
        else:  # private + self
            assert decision.allowed is True, f"{level}/{resource}/{operation}/self 应放行"
            assert decision.violation is None

    @pytest.mark.parametrize(
        ("level", "expected_write_allowed"),
        [(IsolationLevel.L4_HARD, False), (IsolationLevel.L3_SOFT, False), (IsolationLevel.L2_COLLAB, True)],
        ids=["L4-self-写仍拒", "L3-self-写仍拒", "L2-self-写放行"],
    )
    def test_shared_self_write_not_exempted(self, level: IsolationLevel, expected_write_allowed: bool) -> None:
        """shared+self 格: 自身共享面写不豁免（L4 自身 BLACKBOARD WRITE 仍拒——
        矩阵第 1 步不分 cross/self，单主体轴与 448 跨主体轴正交）。"""
        policy = get_isolation_policy(level)
        decision = decide_isolation_access(
            policy,
            cross_agent=False,
            resource=IsolationResource.BLACKBOARD,
            operation=AccessOperation.WRITE,
        )
        assert decision.allowed is expected_write_allowed

    def test_private_cross_denial_reason_contains_policy_name(self) -> None:
        """拒绝 reason 含等级名（并发串扰判别锚——「硬隔离」/「软隔离」）。"""
        for level, expected_name in ((IsolationLevel.L4_HARD, "硬隔离"), (IsolationLevel.L3_SOFT, "软隔离")):
            policy = get_isolation_policy(level)
            decision = decide_isolation_access(
                policy,
                cross_agent=True,
                resource=IsolationResource.PROFILE,
                operation=AccessOperation.READ,
            )
            assert expected_name in decision.reason, f"{level} 拒绝 reason 须含等级名: {decision.reason!r}"

    def test_shared_write_denial_reason_encodes_data_mode(self) -> None:
        """共享面写拒 reason 编码 data_isolation 模式（449 双形态之一——DC-4）。"""
        policy = get_isolation_policy(IsolationLevel.L4_HARD)
        decision = decide_isolation_access(
            policy,
            cross_agent=True,
            resource=IsolationResource.BLACKBOARD,
            operation=AccessOperation.WRITE,
        )
        assert decision.reason == "data_isolation:read_only"

    def test_l3_restricted_write_denied(self) -> None:
        """L3 RESTRICTED_WRITE 共享面写 MVP 拒（受限写白名单未定义——D-4 偏离声明）。"""
        policy = get_isolation_policy(IsolationLevel.L3_SOFT)
        decision = decide_isolation_access(
            policy,
            cross_agent=True,
            resource=IsolationResource.SHARED_WORKSPACE,
            operation=AccessOperation.WRITE,
        )
        assert decision.allowed is False
        assert decision.violation is IsolationViolationKind.OPERATION_FORBIDDEN
        assert decision.reason == "data_isolation:restricted_write"


class TestL1ForwardSemantics:
    """L1 融合态前向格（MVP 禁用但矩阵格完整——单测锁定防 V2 开放时漏改）。"""

    def test_private_cross_allowed_under_l1(self) -> None:
        """L1 private+cross 放行（FULL_SHARED 语义自洽——单边 actor 侧语义，风险 #7 注记）。"""
        policy = get_isolation_policy(IsolationLevel.L1_FUSED)
        decision = decide_isolation_access(
            policy,
            cross_agent=True,
            resource=IsolationResource.PROFILE,
            operation=AccessOperation.READ,
        )
        assert decision.allowed is True
        assert decision.violation is None

    def test_shared_write_allowed_under_l1(self) -> None:
        """L1 共享面写放行（FULL_SHARED）。"""
        policy = get_isolation_policy(IsolationLevel.L1_FUSED)
        decision = decide_isolation_access(
            policy,
            cross_agent=False,
            resource=IsolationResource.BLACKBOARD,
            operation=AccessOperation.WRITE,
        )
        assert decision.allowed is True


class TestDecideToolAccess:
    """decide_tool_access 工具白名单判定（L4 严格 / L3·L2·L1 共享池）。"""

    def test_l4_tool_in_allowlist_allowed(self) -> None:
        """L4 白名单内放行。"""
        policy = get_isolation_policy(IsolationLevel.L4_HARD)
        decision = decide_tool_access(policy, tool_name="PESTEL 分析", allowed_tools=("PESTEL 分析", "SWOT-TOWS"))
        assert decision.allowed is True
        assert decision.violation is None

    def test_l4_tool_outside_allowlist_denied(self) -> None:
        """L4 白名单外拒（OPERATION_FORBIDDEN——reason 恰为 tool_not_in_allowlist:{name}
        形态，与 449 context reason 对称透传；白名单明细不进 reason——禁泄露）。"""
        policy = get_isolation_policy(IsolationLevel.L4_HARD)
        decision = decide_tool_access(policy, tool_name="幻觉工具", allowed_tools=("PESTEL 分析",))
        assert decision.allowed is False
        assert decision.violation is IsolationViolationKind.OPERATION_FORBIDDEN
        assert decision.reason == "tool_not_in_allowlist:幻觉工具"
        assert "PESTEL" not in decision.reason, "白名单内容禁泄露进 reason"

    @pytest.mark.parametrize("level", _MVP_LEVELS[1:] + (IsolationLevel.L1_FUSED,), ids=["L3", "L2", "L1"])
    def test_shared_pool_levels_allow_any_tool(self, level: IsolationLevel) -> None:
        """tool_isolation=False（L3/L2/L1）共享池——白名单外名也放行。"""
        policy = get_isolation_policy(level)
        decision = decide_tool_access(policy, tool_name="任意工具名", allowed_tools=())
        assert decision.allowed is True
        assert decision.violation is None


class TestMatrixDerivesFromPolicyTable:
    """矩阵派生锚（monkeypatch ISOLATION_POLICIES 维度翻转 → 判定随动——零等级硬编码证据）。"""

    def _patched_policy(self, monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> IsolationPolicy:
        """构造 L4 策略翻转副本并 monkeypatch 进策略表（原对象 frozen 不可变）。"""
        original = ISOLATION_POLICIES[IsolationLevel.L4_HARD]
        patched = IsolationPolicy(
            level=original.level,
            name=original.name,
            prompt_isolation=overrides.get("prompt_isolation", original.prompt_isolation),
            tool_isolation=overrides.get("tool_isolation", original.tool_isolation),
            data_isolation=overrides.get("data_isolation", original.data_isolation),
        )
        monkeypatch.setitem(ISOLATION_POLICIES, IsolationLevel.L4_HARD, patched)
        return get_isolation_policy(IsolationLevel.L4_HARD)

    def test_tool_isolation_flip_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """L4 tool_isolation True→False：白名单外工具判定随动放行（矩阵消费策略字段）。"""
        policy = self._patched_policy(monkeypatch, tool_isolation=False)
        decision = decide_tool_access(policy, tool_name="白名单外工具", allowed_tools=())
        assert decision.allowed is True, "tool_isolation 翻转后判定未随动（矩阵硬编码等级嫌疑）"

    def test_prompt_isolation_flip_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """L4 prompt_isolation True→False：private 跨 Agent 判定随动放行。"""
        policy = self._patched_policy(monkeypatch, prompt_isolation=False)
        decision = decide_isolation_access(
            policy,
            cross_agent=True,
            resource=IsolationResource.PROFILE,
            operation=AccessOperation.READ,
        )
        assert decision.allowed is True, "prompt_isolation 翻转后判定未随动（矩阵硬编码等级嫌疑）"

    def test_data_isolation_flip_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """L4 data_isolation READ_ONLY→FREE_WRITE：共享面写判定随动放行。"""
        policy = self._patched_policy(monkeypatch, data_isolation=DataIsolationMode.FREE_WRITE)
        decision = decide_isolation_access(
            policy,
            cross_agent=True,
            resource=IsolationResource.BLACKBOARD,
            operation=AccessOperation.WRITE,
        )
        assert decision.allowed is True, "data_isolation 翻转后判定未随动（矩阵硬编码等级嫌疑）"
