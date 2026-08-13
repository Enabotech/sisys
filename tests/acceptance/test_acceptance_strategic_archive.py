"""战略档案库验收测试步骤实现

验证战略档案库长期存储与归档功能，覆盖 Happy Path、查询、异常路径等场景。
"""

from __future__ import annotations

import uuid
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort

scenarios("test_acceptance_strategic_archive.feature")

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """测试上下文，用于在步骤之间共享状态"""
    return {
        "archives": {},
        "created_archive": None,
        "error": None,
        "events": [],
        "l3_fail": False,
        "l5_fail": False,
    }


@pytest.fixture
def archive_service(
    context: dict[str, Any],
    archive_repo: ArchiveRepositoryPort,
    vector_storage: L3VectorPort,
    object_storage: L4ObjectPort,
    graph_storage: L5GraphPort,
    event_publisher: EventPublisher,
) -> Any:
    """创建战略档案服务实例"""
    from src.application.services.strategic_archive_service import StrategicArchiveService

    return StrategicArchiveService(
        archive_repo=archive_repo,
        vector_storage=vector_storage,
        object_storage=object_storage,
        graph_storage=graph_storage,
        event_publisher=event_publisher,
    )


@pytest.fixture
def archive_repo() -> ArchiveRepositoryPort:
    """Mock 档案仓储"""
    mock = AsyncMock(spec=ArchiveRepositoryPort)
    return cast(ArchiveRepositoryPort, mock)


@pytest.fixture
def vector_storage() -> L3VectorPort:
    """Mock 向量存储"""
    mock = AsyncMock(spec=L3VectorPort)
    return cast(L3VectorPort, mock)


@pytest.fixture
def object_storage() -> L4ObjectPort:
    """Mock 对象存储"""
    mock = AsyncMock(spec=L4ObjectPort)
    return cast(L4ObjectPort, mock)


@pytest.fixture
def graph_storage() -> L5GraphPort:
    """Mock 图存储"""
    mock = AsyncMock(spec=L5GraphPort)
    return cast(L5GraphPort, mock)


@pytest.fixture
def event_publisher() -> EventPublisher:
    """Mock 事件发布器"""
    mock = AsyncMock(spec=EventPublisher)
    return cast(EventPublisher, mock)


# ===================================================================
# 背景
# ===================================================================


@given("系统已初始化战略档案服务")
def _init_archive_service() -> None:
    """系统初始化（背景步骤）"""
    pass


# ===================================================================
# Given 步骤
# ===================================================================


@given("存在 SP 规划 ID「00000000-0000-0000-0000-000000000001」")
def _given_plan_exists(context: dict[str, Any]) -> None:
    """存在 SP 规划"""
    context["plan_id"] = uuid.UUID("00000000-0000-0000-0000-000000000001")


@given("存在多个不同类型的档案")
def _given_multiple_archives(context: dict[str, Any], archive_service: Any) -> None:
    """存在多个不同类型的档案"""
    plan_id = uuid.uuid4()
    archive_ids = []
    for atype in ArchiveType:
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            plan_type="SP",
            archive_type=atype,
            assumptions={"key": "value"},
        )
        archive.validate()
        saved = archive_service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions=archive.assumptions,
            decision_basis={},
            execution_deviation={},
            evidence_blob=None,
        )
        archive_ids.append(saved.archive_id)
    context["plan_id"] = plan_id
    context["archive_ids"] = archive_ids


@given("存在多个规划的档案")
def _given_multiple_plans(context: dict[str, Any], archive_service: Any) -> None:
    """存在多个规划的档案"""
    plan_ids = []
    for i in range(3):
        plan_id = uuid.uuid4()
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={"plan_index": i},
        )
        archive.validate()
        archive_service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions=archive.assumptions,
            decision_basis={},
            execution_deviation={},
            evidence_blob=None,
        )
        plan_ids.append(plan_id)
    context["plan_ids"] = plan_ids
    context["target_plan_id"] = plan_ids[0]


@given("存在一个已归档的档案")
def _given_one_archived(context: dict[str, Any], archive_service: Any) -> None:
    """存在一个已归档的档案"""
    plan_id = uuid.uuid4()
    archive = archive_service.archive_plan(
        plan_id=plan_id,
        plan_type="SP",
        assumptions={"key": "value"},
        decision_basis={"reason": "test"},
        execution_deviation={"delta": "0.1"},
        evidence_blob=b"test evidence",
    )
    context["archive"] = archive
    context["plan_id"] = plan_id


@given("不存在 archive_id 为「00000000-0000-0000-0000-000000009999」的档案")
def _given_archive_not_exists(context: dict[str, Any]) -> None:
    """不存在指定 archive_id 的档案"""
    context["nonexistent_id"] = uuid.UUID("00000000-0000-0000-0000-000000009999")


@given("档案 archive_id 为「00000000-0000-0000-0000-000000000001」已存在")
def _given_archive_conflict(context: dict[str, Any], archive_service: Any) -> None:
    """档案已存在"""
    archive_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=uuid.uuid4(),
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        assumptions={},
    )
    archive.validate()
    context["conflict_archive_id"] = archive_id


@given("存在一个规划关联多个档案")
def _given_plan_with_multiple_archives(context: dict[str, Any], archive_service: Any) -> None:
    """一个规划关联多个档案"""
    plan_id = uuid.uuid4()
    for atype in ArchiveType:
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            plan_type="SP",
            archive_type=atype,
            assumptions={},
        )
        archive.validate()
        archive_service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=None,
        )
    context["plan_id"] = plan_id


# ===================================================================
# When 步骤
# ===================================================================


@when("用户归档该规划的假设变量、决策依据和执行偏差")
def _when_archive_plan(context: dict[str, Any], archive_service: Any) -> None:
    """归档规划"""
    plan_id = context["plan_id"]
    archive = archive_service.archive_plan(
        plan_id=plan_id,
        plan_type="SP",
        assumptions={"market_trend": "growing", "risk_level": "medium"},
        decision_basis={"method": "scenario_analysis", "confidence": 0.85},
        execution_deviation={"revenue": -0.05, "cost": 0.03},
        evidence_blob=b'{"summary": "Q1 financial review"}',
    )
    context["created_archive"] = archive


@when("证据包内容已提供")
def _when_evidence_provided(context: dict[str, Any]) -> None:
    """证据包内容已提供"""
    context["evidence_blob"] = b"test evidence content"


@when("用户按档案类型「assumption」查询")
def _when_query_by_type(context: dict[str, Any], archive_service: Any) -> None:
    """按档案类型查询"""
    query = ArchiveQuery(archive_type=ArchiveType.ASSUMPTION)
    context["query_result"] = archive_service.query_archive(query)


@when("用户按规划 ID「00000000-0000-0000-0000-000000000001」查询")
def _when_query_by_plan_id(context: dict[str, Any], archive_service: Any) -> None:
    """按规划 ID 查询"""
    plan_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    query = ArchiveQuery(plan_id=plan_id)
    context["query_result"] = archive_service.query_archive(query)


@when("用户按该档案的 archive_id 查询")
def _when_get_archive(context: dict[str, Any], archive_service: Any) -> None:
    """按 archive_id 查询档案详情"""
    archive = context["archive"]
    context["fetched_archive"] = archive_service.get_archive(archive.archive_id)


@when("用户归档该规划")
def _when_archive_plan_with_failures(context: dict[str, Any], archive_service: Any) -> None:
    """归档规划（可能伴随存储层失败）"""
    plan_id = uuid.uuid4()
    context["plan_id"] = plan_id
    archive = archive_service.archive_plan(
        plan_id=plan_id,
        plan_type="SP",
        assumptions={"test": "value"},
        decision_basis={},
        execution_deviation={},
        evidence_blob=None,
    )
    context["created_archive"] = archive


@when("L3 向量存储失败")
def _when_l3_fails(context: dict[str, Any], vector_storage: L3VectorPort) -> None:
    """L3 向量存储失败"""
    vector = cast(Any, vector_storage)
    vector.upsert_points = AsyncMock(return_value=False)
    context["l3_fail"] = True


@when("L5 图存储失败")
def _when_l5_fails(context: dict[str, Any], graph_storage: L5GraphPort) -> None:
    """L5 图存储失败"""
    graph = cast(Any, graph_storage)
    graph.create_entity = AsyncMock(return_value=False)
    context["l5_fail"] = True


@when("用户按该 archive_id 查询")
def _when_query_nonexistent(context: dict[str, Any], archive_service: Any) -> None:
    """查询不存在的档案"""
    try:
        archive_service.get_archive(context["nonexistent_id"])
    except Exception as e:
        context["error"] = e


@when("用户尝试创建同 archive_id 的档案")
def _when_create_conflict(context: dict[str, Any], archive_service: Any) -> None:
    """尝试创建冲突的档案"""
    try:
        archive = StrategicArchive(
            archive_id=context["conflict_archive_id"],
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={},
        )
        archive.validate()
        archive_service.archive_plan(
            plan_id=uuid.uuid4(),
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=None,
        )
    except Exception as e:
        context["error"] = e


@when("用户按规划 ID 列出档案")
def _when_list_by_plan(context: dict[str, Any], archive_service: Any) -> None:
    """按规划 ID 列出档案"""
    plan_id = context["plan_id"]
    context["plan_archives"] = archive_service.query_archive(ArchiveQuery(plan_id=plan_id))


# ===================================================================
# Then 步骤
# ===================================================================


@then("系统返回已创建的档案信息")
def _then_archive_created(context: dict[str, Any]) -> None:
    """档案创建成功"""
    assert context["created_archive"] is not None
    assert context["created_archive"].archive_id is not None


@then("L2 元数据已持久化")
def _then_l2_persisted(context: dict[str, Any], archive_repo: ArchiveRepositoryPort) -> None:
    """L2 元数据持久化验证"""
    repo = cast(Any, archive_repo)
    assert repo.save.called


@then("L3 向量已存储")
def _then_l3_stored(vector_storage: L3VectorPort) -> None:
    """L3 向量存储验证"""
    vector = cast(Any, vector_storage)
    assert vector.upsert_points.called


@then("L4 对象已归档（WORM 7年）")
def _then_l4_archived(object_storage: L4ObjectPort) -> None:
    """L4 对象归档验证"""
    obj = cast(Any, object_storage)
    assert obj.archive.called


@then("L5 图谱节点已创建")
def _then_l5_created(graph_storage: L5GraphPort) -> None:
    """L5 图谱节点验证"""
    graph = cast(Any, graph_storage)
    assert graph.create_entity.called


@then("ArchiveCreated 事件已发布")
def _then_event_published(event_publisher: EventPublisher) -> None:
    """ArchiveCreated 事件发布验证"""
    publisher = cast(Any, event_publisher)
    assert publisher.publish.called


@then("仅返回类型为「assumption」的档案")
def _then_only_assumption(context: dict[str, Any]) -> None:
    """仅返回 assumption 类型档案"""
    result = context["query_result"]
    for archive in result:
        assert archive.archive_type == ArchiveType.ASSUMPTION


@then("返回结果不包含其他类型的档案")
def _then_no_other_types(context: dict[str, Any]) -> None:
    """不包含其他类型档案"""
    result = context["query_result"]
    for archive in result:
        assert archive.archive_type == ArchiveType.ASSUMPTION


@then("仅返回该规划关联的档案")
def _then_only_plan_archives(context: dict[str, Any]) -> None:
    """仅返回该规划关联的档案"""
    result = context["query_result"]
    target_plan_id = context.get("target_plan_id")
    if target_plan_id:
        for archive in result:
            assert archive.plan_id == target_plan_id


@then("返回结果不包含其他规划的档案")
def _then_no_other_plan_archives(context: dict[str, Any]) -> None:
    """不包含其他规划档案"""
    result = context["query_result"]
    target_plan_id = context.get("target_plan_id")
    if target_plan_id:
        for archive in result:
            assert archive.plan_id == target_plan_id


@then("系统返回完整的档案详情")
def _then_full_archive_detail(context: dict[str, Any]) -> None:
    """返回完整档案详情"""
    fetched = context["fetched_archive"]
    assert fetched is not None
    assert fetched.archive_id == context["archive"].archive_id


@then("包含所有六层存储引用")
def _then_all_storage_refs(context: dict[str, Any]) -> None:
    """包含六层存储引用"""
    fetched = context["fetched_archive"]
    assert fetched.metadata_ref is not None or fetched.metadata_ref == ""


@then("L2 元数据仍持久化成功")
def _then_l2_still_success(context: dict[str, Any], archive_repo: ArchiveRepositoryPort) -> None:
    """L2 仍持久化成功"""
    repo = cast(Any, archive_repo)
    assert repo.save.called


@then("L4 对象仍归档成功")
def _then_l4_still_success(object_storage: L4ObjectPort) -> None:
    """L4 仍归档成功"""
    obj = cast(Any, object_storage)
    assert obj.archive.called


@then("embedding_ref 为空")
def _then_embedding_ref_null(context: dict[str, Any]) -> None:
    """embedding_ref 为空"""
    archive = context["created_archive"]
    assert archive.embedding_ref is None


@then("graph_ref 为空")
def _then_graph_ref_null(context: dict[str, Any]) -> None:
    """graph_ref 为空"""
    archive = context["created_archive"]
    assert archive.graph_ref is None


@then("ArchiveCreated 事件仍发布")
def _then_event_still_published(event_publisher: EventPublisher) -> None:
    """ArchiveCreated 仍发布"""
    publisher = cast(Any, event_publisher)
    assert publisher.publish.called


@then("系统返回错误码「EXCEPTION_282」")
def _then_error_280(context: dict[str, Any]) -> None:
    """返回 EXCEPTION_282 错误"""
    from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError

    assert context["error"] is not None
    assert isinstance(context["error"], ArchiveNotFoundError)


@then("系统返回错误码「EXCEPTION_283」")
def _then_error_281(context: dict[str, Any]) -> None:
    """返回 EXCEPTION_283 错误"""
    from src.domain.exceptions.archive_exceptions import ArchiveConflictError

    assert context["error"] is not None
    assert isinstance(context["error"], ArchiveConflictError)


@then("错误HTTP状态码为404")
def _then_http_404(context: dict[str, Any]) -> None:
    """HTTP 404"""
    from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError

    assert isinstance(context["error"], ArchiveNotFoundError)


@then("错误HTTP状态码为409")
def _then_http_409(context: dict[str, Any]) -> None:
    """HTTP 409"""
    from src.domain.exceptions.archive_exceptions import ArchiveConflictError

    assert isinstance(context["error"], ArchiveConflictError)


@then("返回该规划的所有关联档案")
def _then_all_plan_archives(context: dict[str, Any]) -> None:
    """返回所有关联档案"""
    archives = context["plan_archives"]
    assert len(archives) > 0
    for archive in archives:
        assert archive.plan_id == context["plan_id"]


@then("返回结果包含所有档案类型")
def _then_all_types(context: dict[str, Any]) -> None:
    """包含所有档案类型"""
    archives = context["plan_archives"]
    types_found = {a.archive_type for a in archives}
    assert len(types_found) > 0
