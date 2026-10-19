"""AgentProfile 值对象单元测试（Story 5-2 — Agent 身份档案加载）

覆盖六档案 frozen 值对象的自校验契约：
- frozen 不可变性与全字段合法构造往返
- agent_id UUID 类型 / role 枚举类型守卫（442）
- 六档案字段先 isinstance(str) 类型守卫再 strip 判空（5-1 R2-F2 教训：
  truthy 标量会越过判空——「responsibilities="战略方向"」静默通过）
- 校验失败统一 AgentProfileError(EXCEPTION_442)（档案资产缺陷语义）
- 上下文出处：or.md 四.1.[1]（L277 七档案枚举）与 architecture.md §11.2.2

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_agent_profile.py -v
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentProfileError


def _make_profile(**kwargs):
    """工厂：构造合法 CEO 档案值对象（可覆盖任意字段）。

    Story 5-2 新模块延迟 import 纪律——模块顶部 import 会使收集期整文件炸。
    """
    from src.domain.value_objects.agent_profile import AgentProfile

    defaults: dict = {
        "agent_id": uuid.uuid4(),
        "role": AgentRole.CEO,
        "identity": "# IDENTITY\nCEO 首席执行官，负责战略方向、最终决策与高管协调。",
        "code_of_conduct": "# CODE\n1. 证据优先；2. 角色隔离纪律。",
        "soul": "# SOUL\n高管决策视角：宏观趋势、竞争格局、战略意图。",
        "user_preferences": "# USER\n偏好简明扼要的结论先行表达。",
        "memory": "# MEMORY\n暂无系统级记忆，此为加载占位。",
        "heartbeat": "# HEARTBEAT\n默认每日频率占位。",
    }
    defaults.update(kwargs)
    return AgentProfile(**defaults)


# ===================================================================
# 合法构造与 frozen
# ===================================================================


class TestValidConstruction:
    """全字段合法构造往返与 frozen 不可变。"""

    def test_full_fields_roundtrip(self) -> None:
        """全字段构造后逐字段读回一致。"""
        agent_id = uuid.uuid4()
        profile = _make_profile(agent_id=agent_id)
        assert profile.agent_id == agent_id
        assert profile.role == AgentRole.CEO
        assert "CEO" in profile.identity
        assert profile.code_of_conduct.startswith("# CODE")
        assert "高管" in profile.soul
        assert profile.user_preferences
        assert profile.memory
        assert profile.heartbeat

    def test_frozen_dataclass(self) -> None:
        """frozen：setattr 抛异常（档案为不可变值对象）。"""
        profile = _make_profile()
        with pytest.raises(Exception, match="cannot assign|frozen"):
            setattr(profile, "identity", "# 篡改")


# ===================================================================
# agent_id / role 类型守卫
# ===================================================================


class TestAnchorTypeGuards:
    """agent_id UUID 与 role 枚举类型校验（442）。"""

    def test_agent_id_must_be_uuid(self) -> None:
        """agent_id 非 UUID 对象 → 442（字符串 UUID 也不接受——契约 UUID 类型）。"""
        with pytest.raises(AgentProfileError) as exc_info:
            _make_profile(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        assert exc_info.value.code == "EXCEPTION_442"

    def test_role_must_be_enum(self) -> None:
        """role 非 AgentRole 枚举（字符串值）→ 442。"""
        with pytest.raises(AgentProfileError) as exc_info:
            _make_profile(role="ceo")
        assert exc_info.value.code == "EXCEPTION_442"


# ===================================================================
# 六档案字段守卫（先类型后空值——truthy 标量越过判空的防线）
# ===================================================================


class TestSixFieldGuards:
    """六档案字段 isinstance(str) 类型守卫 + strip 判空（442）。"""

    @pytest.mark.parametrize(
        "field_name",
        ["identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"],
    )
    def test_non_string_field_rejected(self, field_name: str) -> None:
        """字段非 str（如 int/list）→ 442——类型守卫先于判空。"""
        with pytest.raises(AgentProfileError) as exc_info:
            _make_profile(**{field_name: 12345})
        assert exc_info.value.code == "EXCEPTION_442"

    @pytest.mark.parametrize(
        "field_name",
        ["identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"],
    )
    def test_empty_string_rejected(self, field_name: str) -> None:
        """空串 → 442。"""
        with pytest.raises(AgentProfileError):
            _make_profile(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"],
    )
    def test_whitespace_only_rejected(self, field_name: str) -> None:
        """纯空白（空格/制表符）→ 442。"""
        with pytest.raises(AgentProfileError):
            _make_profile(**{field_name: "   \t   "})

    @pytest.mark.parametrize(
        "field_name",
        ["identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"],
    )
    def test_newline_only_rejected(self, field_name: str) -> None:
        """纯换行 → 442。"""
        with pytest.raises(AgentProfileError):
            _make_profile(**{field_name: "\n\n\n"})


# ===================================================================
# 异常上下文
# ===================================================================


class TestErrorContext:
    """VO 兜底路径的异常 context（profile_path 可空——DC-5 主检在加载器）。"""

    def test_error_context_has_reason(self) -> None:
        """VO 直接构造的校验失败 context 含 reason（兜底路径无文件名）。"""
        with pytest.raises(AgentProfileError) as exc_info:
            _make_profile(soul="   ")
        assert exc_info.value.context.get("reason"), "VO 兜底路径 context 应含 reason"
