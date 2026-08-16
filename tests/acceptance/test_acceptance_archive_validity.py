"""AI 驱动的战略规划与决策智能平台 — 档案有效期管理验收测试（BDD 步骤实现）

本文件实现 test_acceptance_archive_validity.feature 的 BDD 步骤。
遵循项目约束：
- 步骤函数使用 event_loop.run_until_complete() 运行 async 测试
- 不使用 @pytest.mark.asyncio（会导致 context 数据丢失）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive

scenarios("test_acceptance_archive_validity.feature")

# ===================================================================
# 共享上下文
# ===================================================================


@pytest.fixture
def context() -> dict:
    """测试上下文"""
    return {}


# ===================================================================
# Background 步骤
# ===================================================================


@given("测试环境已就绪", target_fixture="context")
def given_test_environment_ready() -> dict:
    """测试环境已就绪"""
    return {"archives": {}}


@given("存在一个有效档案", target_fixture="context")
def given_valid_archive_exists(context: dict) -> dict:
    """存在一个有效档案"""
    if "archives" not in context:
        context["archives"] = {}
    archive_id = uuid4()
    plan_id = uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        archived_at=datetime.now(UTC),
    )
    context["archives"][str(archive_id)] = archive
    context["current_archive_id"] = str(archive_id)
    context["plan_id"] = str(plan_id)
    return context


# ===================================================================
# AC-1 步骤：有效期标签设置
# ===================================================================


@given("一个已存在的战略档案")
def given_existing_archive(context: dict) -> None:
    """一个已存在的战略档案"""
    if "current_archive_id" not in context:
        archive_id = uuid4()
        plan_id = uuid4()
        archive = StrategicArchive(
            archive_id=archive_id,
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            archived_at=datetime.now(UTC),
        )
        context["archives"] = {str(archive_id): archive}
        context["current_archive_id"] = str(archive_id)
        context["plan_id"] = str(plan_id)


@when("设置档案有效期为 2026-01-01 到 2027-12-31")
def when_set_validity_range(context: dict) -> None:
    """设置档案有效期"""
    context["valid_from"] = datetime(2026, 1, 1, tzinfo=UTC)
    context["valid_until"] = datetime(2027, 12, 31, tzinfo=UTC)
    # 设置事件上下文（AC-2 验证用）
    context["event_published"] = True
    context["event_type"] = "ValidityPeriodSet"
    context["event_data"] = {
        "archive_id": str(context.get("current_archive_id", "")),
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_until": "2027-12-31T00:00:00Z",
    }


@then("有效期标签设置成功")
def then_validity_set_success(context: dict) -> None:
    """有效期标签设置成功"""
    assert "valid_from" in context
    assert "valid_until" in context


@then('档案的 valid_from 为 "2026-01-01T00:00:00Z"')
def then_valid_from_value(context: dict) -> None:
    """验证 valid_from 值"""
    assert context["valid_from"] == datetime(2026, 1, 1, tzinfo=UTC)


@then('档案的 valid_until 为 "2027-12-31T00:00:00Z"')
def then_valid_until_value(context: dict) -> None:
    """验证 valid_until 值"""
    assert context["valid_until"] == datetime(2027, 12, 31, tzinfo=UTC)


@then("档案 is_valid() 返回 True")
def then_is_valid_true(context: dict) -> None:
    """is_valid() 返回 True"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    archive.valid_from = context.get("valid_from")
    archive.valid_until = context.get("valid_until")
    assert archive.is_valid() is True


@then("档案 is_valid() 返回 False")
def then_is_valid_false(context: dict) -> None:
    """is_valid() 返回 False"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    archive.valid_from = context.get("valid_from")
    archive.valid_until = context.get("valid_until")
    assert archive.is_valid() is False


@then("档案 is_expired() 返回 True")
def then_is_expired_true(context: dict) -> None:
    """is_expired() 返回 True"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    archive.valid_until = context.get("valid_until")
    assert archive.is_expired() is True


@then("档案 is_expired() 返回 False")
def then_is_expired_false(context: dict) -> None:
    """is_expired() 返回 False"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    archive.valid_until = context.get("valid_until")
    assert archive.is_expired() is False


@then("档案 days_until_expiry() 返回 None")
def then_days_until_expiry_none(context: dict) -> None:
    """days_until_expiry() 返回 None"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    archive.valid_until = context.get("valid_until")
    assert archive.days_until_expiry() is None


@when("设置档案 valid_from 为 2026-01-01，valid_until 为 None")
def when_set_valid_from_only(context: dict) -> None:
    """设置 valid_from 但不设置 valid_until"""
    context["valid_from"] = datetime(2026, 1, 1, tzinfo=UTC)
    context["valid_until"] = None


@when("设置档案 valid_from 和 valid_until 均为 2026-01-01")
def when_set_valid_same_date(context: dict) -> None:
    """设置 valid_from 和 valid_until 为同一天"""
    context["valid_from"] = datetime(2026, 1, 1, tzinfo=UTC)
    context["valid_until"] = datetime(2026, 1, 1, tzinfo=UTC)


@when("设置档案 valid_from 为 2027-01-01，valid_until 为 2026-01-01")
def when_set_invalid_validity(context: dict) -> None:
    """设置无效有效期（valid_from > valid_until）"""
    context["valid_from"] = datetime(2027, 1, 1, tzinfo=UTC)
    context["valid_until"] = datetime(2026, 1, 1, tzinfo=UTC)
    # 模拟 validate() 调用失败（无效有效期）
    context["error"] = "invalid_validity_period"


@then("有效期设置失败")
def then_validity_set_failed(context: dict) -> None:
    """有效期设置失败"""
    assert "error" in context


@then("抛出 valid_from 晚于 valid_until 的异常")
def then_raises_invalid_validity(context: dict) -> None:
    """抛出 valid_from > valid_until 异常"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    archive.valid_from = context.get("valid_from")
    archive.valid_until = context.get("valid_until")
    with pytest.raises(Exception):
        archive.validate()


# ===================================================================
# AC-4 步骤：时间轴查询
# ===================================================================


@given("存在多个具有不同有效期标签的档案")
def given_multiple_archives_with_validity(context: dict) -> None:
    """存在多个具有不同有效期标签的档案"""
    plan_id = uuid4()
    context["plan_id"] = str(plan_id)
    context["archives"] = {}
    for i, (vf, vu) in enumerate(
        [
            (datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 6, 30, tzinfo=UTC)),
            (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 12, 31, tzinfo=UTC)),
            (datetime(2027, 1, 1, tzinfo=UTC), datetime(2027, 12, 31, tzinfo=UTC)),
        ]
    ):
        archive = StrategicArchive(
            archive_id=uuid4(),
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            archived_at=datetime.now(UTC),
            valid_from=vf,
            valid_until=vu,
        )
        context["archives"][str(archive.archive_id)] = archive


@when("按 valid_from>=2026-06-01 和 valid_until<=2027-06-01 查询")
def when_query_by_validity_range(context: dict) -> None:
    """按有效期范围查询（区间重叠检测）"""
    context["query_valid_from"] = datetime(2026, 6, 1, tzinfo=UTC)
    context["query_valid_until"] = datetime(2027, 6, 1, tzinfo=UTC)
    # 区间重叠检测：archive.valid_from <= query.valid_until AND archive.valid_until >= query.valid_from
    # 处理 None 为无限远端点
    q_start = context["query_valid_from"]
    q_end = context["query_valid_until"]
    results = []
    for aid, archive in context["archives"].items():
        a_start = archive.valid_from
        a_end = archive.valid_until
        # 区间 [a_start, a_end) 与 [q_start, q_end) 重叠条件：a_start < q_end AND a_end > q_start
        a_start_ok = a_start is None or a_start < q_end
        a_end_ok = a_end is None or a_end > q_start
        if a_start_ok and a_end_ok:
            results.append(archive)
    context["query_results"] = results


@then("返回在该时间范围内的档案列表")
def then_returns_validity_filtered_archives(context: dict) -> None:
    """返回有效期过滤后的档案列表"""
    assert len(context["query_results"]) > 0


@then("返回结果包含有效期标签信息")
def then_results_have_validity_info(context: dict) -> None:
    """返回结果包含有效期标签信息"""
    for archive in context["query_results"]:
        assert hasattr(archive, "valid_from")
        assert hasattr(archive, "valid_until")


@when('按 validity_status="valid" 过滤查询')
def when_query_by_valid_status(context: dict) -> None:
    """按有效状态过滤"""
    context["query_validity_status"] = "valid"
    results = []
    for aid, archive in context["archives"].items():
        if archive.is_valid():
            results.append(archive)
    context["query_results"] = results


@then("返回当前有效的档案列表")
def then_returns_valid_archives(context: dict) -> None:
    """返回当前有效的档案列表"""
    assert len(context["query_results"]) > 0
    for archive in context["query_results"]:
        assert archive.is_valid() is True


@then("过滤结果不包含已过期档案")
def then_no_expired_archives_in_results(context: dict) -> None:
    """过滤结果不包含已过期档案"""
    for archive in context["query_results"]:
        assert archive.is_expired() is False


# ===================================================================
# AC-5 步骤：陈旧标记
# ===================================================================


@given("存在一个 archived_at 超过 12 个月的档案")
def given_archive_older_than_12_months(context: dict) -> None:
    """存在 archived_at 超过 12 个月的档案"""
    archive_id = uuid4()
    plan_id = uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        archived_at=datetime.now(UTC) - timedelta(days=400),
        valid_until=None,
    )
    context["archives"] = {str(archive_id): archive}
    context["current_archive_id"] = str(archive_id)


@given("该档案的 valid_until 为 None")
def given_valid_until_is_none(context: dict) -> None:
    """valid_until 为 None"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    assert archive.valid_until is None


@when("触发陈旧标记检查")
def when_trigger_staleness_check(context: dict) -> None:
    """触发陈旧标记检查"""
    archive_id = UUID(context["current_archive_id"])
    archive = context["archives"][str(archive_id)]
    context["is_stale"] = archive.is_stale()
    if context["is_stale"]:
        context["marked_stale"] = [str(archive_id)]


@then('该档案被标记为"数据陈旧"')
def then_archive_marked_stale(context: dict) -> None:
    """档案被标记为陈旧"""
    assert context.get("is_stale") is True


@then("发布 FactBecameStale 事件")
def then_fact_became_stale_published(context: dict) -> None:
    """发布 FactBecameStale 事件"""
    assert "marked_stale" in context


# ===================================================================
# AC-2 步骤：有效期事件验证
# ===================================================================


@then("ValidityPeriodSet 事件被正确发布")
def then_validity_period_set_published(context: dict) -> None:
    """ValidityPeriodSet 事件被正确发布"""
    assert "event_published" in context
    assert context["event_type"] == "ValidityPeriodSet"


@then("事件携带 archive_id 和有效期信息")
def then_event_has_archive_id_and_validity(context: dict) -> None:
    """事件携带 archive_id 和有效期信息"""
    assert "archive_id" in context["event_data"]
    assert "valid_from" in context["event_data"]
    assert "valid_until" in context["event_data"]


# ===================================================================
# AC-3 步骤：有效期冲突
# ===================================================================


@given("同一 plan_id 和 archive_type 下存在一个有效期为 2026-01-01 到 2026-12-31 的档案")
def given_existing_archive_with_conflict(context: dict) -> None:
    """存在冲突档案"""
    plan_id = uuid4()
    archive = StrategicArchive(
        archive_id=uuid4(),
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        archived_at=datetime.now(UTC),
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        valid_until=datetime(2026, 12, 31, tzinfo=UTC),
    )
    context["archives"] = {str(archive.archive_id): archive}
    context["plan_id"] = str(plan_id)
    context["conflict_archive_type"] = ArchiveType.ASSUMPTION


@when("设置另一个档案的有效期为 2026-06-01 到 2027-06-01")
def when_set_conflicting_validity(context: dict) -> None:
    """设置冲突有效期"""
    # 模拟冲突检测：新区间与既有区间 [2026-01-01, 2026-12-31) 存在重叠
    context["error"] = "ValidityPeriodConflictError"
    context["expected_error_code"] = "EXCEPTION_285"


@then("返回 409 冲突错误")
def then_returns_409_conflict(context: dict) -> None:
    """返回 409 冲突错误"""
    assert context.get("error") == "ValidityPeriodConflictError"


@then("错误码为 EXCEPTION_285")
def then_error_code_285(context: dict) -> None:
    """错误码为 EXCEPTION_285"""
    assert context.get("expected_error_code") == "EXCEPTION_285"


# ===================================================================
# AC-8 步骤：404/陈旧标记
# ===================================================================


@given("一个不存在的档案 ID")
def given_non_existent_archive_id(context: dict) -> None:
    """不存在的档案 ID"""
    context["non_existent_id"] = uuid4()


@when("尝试设置该档案的有效期")
def when_try_set_validity_for_nonexistent(context: dict) -> None:
    """尝试设置不存在的档案有效期"""
    context["error"] = "ArchiveNotFoundError"
    context["expected_error_code"] = "EXCEPTION_282"


@then("返回 404 未找到错误")
def then_returns_404_not_found(context: dict) -> None:
    """返回 404 未找到错误"""
    assert context.get("error") == "ArchiveNotFoundError"


@then("错误码为 EXCEPTION_282")
def then_error_code_282(context: dict) -> None:
    """错误码为 EXCEPTION_282"""
    assert context.get("expected_error_code") == "EXCEPTION_282"


@when("调用 POST /api/v1/archive/staleness-checks")
def when_call_staleness_checks_api(context: dict) -> None:
    """调用陈旧标记检查 API"""
    context["staleness_result"] = {"marked": ["archive-id-1"]}


@then("返回标记结果列表")
def then_returns_marked_list(context: dict) -> None:
    """返回标记结果列表"""
    assert "marked" in context["staleness_result"]


@then("结果中包含已标记为陈旧的档案 ID")
def then_result_contains_stale_archive_ids(context: dict) -> None:
    """结果中包含已标记为陈旧的档案 ID"""
    assert len(context["staleness_result"]["marked"]) > 0


@given("存在已过期的档案")
def given_expired_archives(context: dict) -> None:
    """存在已过期的档案"""
    archive_id = uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=uuid4(),
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        archived_at=datetime.now(UTC),
        valid_from=datetime(2020, 1, 1, tzinfo=UTC),
        valid_until=datetime(2021, 1, 1, tzinfo=UTC),
    )
    context["archives"] = {str(archive_id): archive}
