"""TaskEvidencePackage 值对象单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖任务级证据包九字段 frozen 值对象的自校验契约：
- 九字段合法构造往返 + frozen 不可变
- input_hash 口径守卫（64 位十六进制——sha256(task_description).hexdigest()）
- confidence 0.0-1.0 范围守卫
- status 枚举守卫（completed/failed 二值）+ 失败终态 failure_reason 非空守卫
  （AC-3：失败终态同样产包，含失败原因与已执行轨迹）
- artifacts_snapshot 元组对形态守卫（frozen VO 禁可变 dict 字段）
- 三 tuple 字段（task_breakdown/tool_trace/citations）元素级类型守卫
- 校验失败统一 EntityValidationError(EXCEPTION_242)（VO 构造器守卫语义）
- 上下文出处：or.md §四.11.[1]（L343 结构化证据包标准）

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_task_evidence.py -v
"""

from __future__ import annotations

import hashlib

import pytest

from src.domain.exceptions import EntityValidationError


def _make_evidence(**kwargs):
    """工厂：构造合法任务级证据包值对象（可覆盖任意字段）。

    Story 5-3 新模块延迟 import 纪律——模块顶部 import 会使收集期整文件炸。
    """
    from src.domain.value_objects.task_evidence import TaskEvidencePackage

    task_description = "分析新能源汽车行业进入战略并给出三层次建议"
    defaults: dict = {
        "input_hash": hashlib.sha256(task_description.encode()).hexdigest(),
        "task_breakdown": ("执行 PESTEL 宏观环境分析", "综合三层次进入策略建议"),
        "tool_trace": ("pestel:v1.2.0",),
        "artifacts_snapshot": (("pestel_output", '{"P": 0.8, "E": 0.7}'),),
        "confidence": 0.85,
        "confidence_rationale": "结构化检查通过，工具输出完整",
        "citations": ("chunk-001", "chunk-002"),
        "status": "completed",
        "failure_reason": "",
    }
    defaults.update(kwargs)
    return TaskEvidencePackage(**defaults)


# ===================================================================
# 合法构造与 frozen
# ===================================================================


class TestValidConstruction:
    """九字段合法构造往返与 frozen 不可变。"""

    def test_full_fields_roundtrip(self) -> None:
        """全字段构造后逐字段读回一致。"""
        evidence = _make_evidence()
        assert len(evidence.input_hash) == 64
        assert evidence.task_breakdown[0].startswith("执行")
        assert evidence.tool_trace == ("pestel:v1.2.0",)
        assert evidence.artifacts_snapshot[0][0] == "pestel_output"
        assert evidence.confidence == 0.85
        assert "结构化检查" in evidence.confidence_rationale
        assert evidence.citations == ("chunk-001", "chunk-002")
        assert evidence.status == "completed"
        assert evidence.failure_reason == ""

    def test_failed_status_with_reason_legal(self) -> None:
        """失败终态合法形态：status=failed + failure_reason 非空（AC-3）。"""
        evidence = _make_evidence(
            status="failed",
            failure_reason="第 3 次验证未通过：工具输出缺少关键约束字段",
            confidence=0.42,
        )
        assert evidence.status == "failed"
        assert evidence.failure_reason.startswith("第 3 次")

    def test_empty_trace_and_citations_legal(self) -> None:
        """空轨迹/空引用/空快照合法（零工具任务的证据形态）。"""
        evidence = _make_evidence(task_breakdown=(), tool_trace=(), artifacts_snapshot=(), citations=())
        assert evidence.tool_trace == ()
        assert evidence.citations == ()

    def test_frozen_dataclass(self) -> None:
        """frozen：setattr 抛异常（证据包为不可变值对象）。"""
        evidence = _make_evidence()
        with pytest.raises(Exception, match="cannot assign|frozen"):
            setattr(evidence, "confidence", 1.0)


# ===================================================================
# input_hash 口径守卫（sha256 六十四位十六进制）
# ===================================================================


class TestInputHashGuard:
    """input_hash 64 位十六进制格式守卫（242）。"""

    def test_non_string_hash_rejected(self) -> None:
        """非 str → 242（类型守卫先于格式判）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_evidence(input_hash=1234567890)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize("bad_hash", ["", "abc", "z" * 64, "0" * 63, "0" * 65])
    def test_malformed_hash_rejected(self, bad_hash: str) -> None:
        """非 64 位十六进制格式 → 242。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(input_hash=bad_hash)

    def test_hash_algorithm_contract(self) -> None:
        """口径锚：sha256(task_description).hexdigest()（与业务构造侧一致——
        VO 层守 64 位 hex 格式（非 hex 即 242），算法口径锁在服务组装侧单测）。"""
        task_description = "分析新能源汽车行业进入战略并给出三层次建议"
        evidence = _make_evidence(input_hash=hashlib.sha256(task_description.encode()).hexdigest())
        # 不同输入产生不同 hash（构造面存储往返 + 口径非恒定占位串）
        assert evidence.input_hash != hashlib.sha256("其他任务".encode()).hexdigest()


# ===================================================================
# confidence 范围与 status 枚举守卫
# ===================================================================


class TestConfidenceAndStatusGuards:
    """confidence 0.0-1.0 范围 + status 二值枚举 + 失败终态守卫（242）。"""

    @pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, 2.0, -1.0])
    def test_confidence_out_of_range_rejected(self, bad_confidence: float) -> None:
        """confidence 越界 → 242。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_evidence(confidence=bad_confidence)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize("boundary", [0.0, 1.0])
    def test_confidence_boundary_legal(self, boundary: float) -> None:
        """边界值 0.0/1.0 合法。"""
        assert _make_evidence(confidence=boundary).confidence == boundary

    def test_confidence_must_be_float(self) -> None:
        """confidence 非 float（如 str）→ 242。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(confidence="0.85")

    @pytest.mark.parametrize("bad_status", ["success", "FAILED", "running", "", 123])
    def test_invalid_status_rejected(self, bad_status) -> None:
        """status 非 completed/failed → 242。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(status=bad_status)

    def test_failed_without_reason_rejected(self) -> None:
        """失败终态守卫：status=failed 且 failure_reason 空白 → 242（AC-3 核心）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_evidence(status="failed", failure_reason="")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_failed_with_blank_reason_rejected(self) -> None:
        """失败终态守卫：failure_reason 纯空白 → 242。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(status="failed", failure_reason="   \n  ")

    def test_confidence_rationale_must_be_nonempty(self) -> None:
        """置信度依据非空守卫（六类字段之「置信度评分及依据」）。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(confidence_rationale="")


# ===================================================================
# 元组形态守卫（artifacts_snapshot 元组对 + 三 tuple 字段元素级）
# ===================================================================


class TestTupleShapeGuards:
    """artifacts_snapshot 元组对形态与 tuple 字段元素级类型守卫（242）。"""

    def test_artifacts_snapshot_must_be_tuple_of_pairs(self) -> None:
        """artifacts_snapshot 元素必须为二元组（名称, 内容快照）。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(artifacts_snapshot=(("only_name",),))

    def test_artifacts_snapshot_pair_element_types(self) -> None:
        """元组对两元素均须 str。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(artifacts_snapshot=(("name", 12345),))
        with pytest.raises(EntityValidationError):
            _make_evidence(artifacts_snapshot=((12345, "content"),))

    def test_artifacts_snapshot_rejects_dict(self) -> None:
        """dict 形态拒绝——frozen VO 禁可变 dict 字段（不可变纪律）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_evidence(artifacts_snapshot={"pestel_output": '{"P": 0.8}'})
        assert exc_info.value.code == "EXCEPTION_242"

    def test_artifacts_snapshot_rejects_list(self) -> None:
        """list 形态拒绝（元组纪律）。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(artifacts_snapshot=[("pestel_output", "{}")])

    @pytest.mark.parametrize(
        "field_name",
        ["task_breakdown", "tool_trace", "citations"],
    )
    def test_tuple_fields_reject_list(self, field_name: str) -> None:
        """tuple 字段传 list → 242。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(**{field_name: ["item"]})

    @pytest.mark.parametrize(
        "field_name",
        ["task_breakdown", "tool_trace", "citations"],
    )
    def test_tuple_fields_reject_non_str_element(self, field_name: str) -> None:
        """tuple 字段元素非 str → 242。"""
        with pytest.raises(EntityValidationError):
            _make_evidence(**{field_name: (12345,)})
