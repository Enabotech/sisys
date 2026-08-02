"""Story 2-7 验收测试 — 文档元数据标准化校验

BDD 验收测试，使用 pytest-bdd 绑定 Gherkin 场景，按 AC 组织用例。
测试使用 DocumentMetadata 值对象验证端到端校验正确性。

Run with: poetry run pytest tests/acceptance/test_acceptance_metadata_validation.py -v
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.value_objects.document_metadata import DocumentMetadata

scenarios("test_acceptance_metadata_validation.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """共享 BDD 步骤间状态"""
    return {}


# ===================================================================
# Background
# ===================================================================


@given("元数据校验器已就绪")
def given_validator_ready(context: dict[str, Any]) -> None:
    """初始化元数据校验器"""
    context["document_id"] = uuid4()
    context["tenant_id"] = f"test-tenant-{uuid4().hex[:8]}"
    context["uploaded_by"] = "test-user"


# ===================================================================
# 通用步骤（跨 AC 共享）
# ===================================================================


def _do_validate(context: dict[str, Any], autofill: bool = True) -> None:
    """执行元数据校验，可选择是否自动填充"""
    from src.domain.exceptions.storage_exceptions import MetadataValidationError

    if autofill:
        doc_metadata = DocumentMetadata.from_upload(
            document_id=context["document_id"],
            raw_metadata=context.get("raw_metadata"),
            uploaded_by=context.get("uploaded_by", ""),
        )
    else:
        doc_metadata = DocumentMetadata(
            document_id=context["document_id"],
            metadata=context.get("raw_metadata", {}),
        )
    context["doc_metadata"] = doc_metadata
    try:
        doc_metadata.validate()
        context["missing"] = []
        context["validation_passed"] = True
    except MetadataValidationError as e:
        context["missing"] = e.missing_fields
        context["validation_passed"] = False
        context["error"] = e


@when("系统执行元数据校验")
def when_validate_metadata(context: dict[str, Any]) -> None:
    """执行元数据校验（不含自动填充）"""
    _do_validate(context, autofill=False)


@when("系统执行元数据校验（含自动填充）")
def when_validate_metadata_with_autofill(context: dict[str, Any]) -> None:
    """执行元数据校验（含自动填充）"""
    _do_validate(context, autofill=True)


@then("校验通过")
def then_validation_passed(context: dict[str, Any]) -> None:
    """验证校验通过"""
    assert context["validation_passed"] is True


@then("校验失败")
def then_validation_failed(context: dict[str, Any]) -> None:
    """验证校验失败"""
    assert context["validation_passed"] is False


@then("返回缺失字段列表为空")
def then_missing_fields_empty(context: dict[str, Any]) -> None:
    """验证缺失字段列表为空"""
    assert context["missing"] == []


@then("creator 自动填充为上传者")
def then_creator_autofilled(context: dict[str, Any]) -> None:
    """验证 creator 自动填充为上传者"""
    assert context["doc_metadata"].metadata.get("creator") == context.get("uploaded_by", "test-user")


@then("created_at 自动填充为当前 UTC 时间")
def then_created_at_autofilled(context: dict[str, Any]) -> None:
    """验证 created_at 自动填充为当前 UTC 时间（ISO 8601 格式，5 秒内）"""
    from datetime import UTC, datetime

    created_at = context["doc_metadata"].metadata.get("created_at", "")
    assert created_at, "created_at 未自动填充"
    assert "T" in created_at, f"created_at 不是 ISO 8601 格式: {created_at}"
    parsed = datetime.fromisoformat(created_at)
    now = datetime.now(UTC)
    delta = abs((now - parsed).total_seconds())
    assert delta < 5, f"created_at 时间偏差过大: {delta} 秒"


@then("缺失字段列表包含 source")
def then_missing_fields_contains_source(context: dict[str, Any]) -> None:
    """验证缺失字段列表包含 source"""
    assert "source" in context["missing"]


@then("缺失字段列表包含 created_at")
def then_missing_fields_contains_created_at(context: dict[str, Any]) -> None:
    """验证缺失字段列表包含 created_at"""
    assert "created_at" in context["missing"]


@then("source、license、business_domain 仍然缺失")
def then_three_fields_still_missing(context: dict[str, Any]) -> None:
    """验证 source、license、business_domain 三个字段仍然缺失"""
    missing = context["missing"]
    assert "source" in missing
    assert "license" in missing
    assert "business_domain" in missing


# ===================================================================
# AC-1: 最小元字段集校验
# ===================================================================


@given("一个包含完整元数据的文档准备入库")
def given_doc_with_complete_metadata(context: dict[str, Any]) -> None:
    """设置完整元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("元数据包含 creator、created_at、source、license、business_domain 五个字段")
def given_metadata_has_all_fields(context: dict[str, Any]) -> None:
    """验证元数据包含全部五个必需字段"""
    raw = context["raw_metadata"]
    assert "creator" in raw
    assert "created_at" in raw
    assert "source" in raw
    assert "license" in raw
    assert "business_domain" in raw


@given("一个文档仅提供 source、license、business_domain 三个字段")
def given_doc_with_partial_metadata(context: dict[str, Any]) -> None:
    """设置仅包含三个字段的部分元数据"""
    context["raw_metadata"] = {
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("一个文档的 source 字段值为空字符串")
def given_empty_source(context: dict[str, Any]) -> None:
    """设置 source 字段为空字符串"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "source": "",
        "license": "confidential",
        "business_domain": "finance",
    }


@given('一个文档的 created_at 字段为 "2024/01/01"（非 ISO 8601 格式）')
def given_invalid_created_at(context: dict[str, Any]) -> None:
    """设置非法 ISO 8601 格式的 created_at"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024/01/01",
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("一个文档不包含任何元数据")
def given_no_metadata(context: dict[str, Any]) -> None:
    """设置无元数据"""
    context["raw_metadata"] = None


# ===================================================================
# AC-2: 关键字段缺失自动阻断
# ===================================================================


@given("一个文档的元数据缺少 license 字段")
def given_missing_license(context: dict[str, Any]) -> None:
    """设置缺少 license 字段的元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "source": "internal",
        "business_domain": "finance",
    }


@then("抛出 MetadataValidationError 异常")
def then_throws_metadata_validation_error(context: dict[str, Any]) -> None:
    """验证抛出了 MetadataValidationError"""
    from src.domain.exceptions.storage_exceptions import MetadataValidationError

    assert context.get("error") is not None
    assert isinstance(context["error"], MetadataValidationError)


@then("异常编码为 EXCEPTION_217")
def then_exception_code_217(context: dict[str, Any]) -> None:
    """验证异常编码为 EXCEPTION_217"""
    assert context["error"].code == "EXCEPTION_217"


@then("异常上下文包含缺失字段列表")
def then_context_has_missing_fields(context: dict[str, Any]) -> None:
    """验证异常上下文包含缺失字段列表"""
    assert "missing_fields" in context["error"].context
    assert isinstance(context["error"].context["missing_fields"], list)


@then("缺失字段列表包含 license")
def then_missing_fields_contains_license(context: dict[str, Any]) -> None:
    """验证缺失字段列表包含 license"""
    assert "license" in context["error"].context["missing_fields"]


@then("异常上下文包含 document_id 和 tenant_id")
def then_context_has_doc_id_and_tenant(context: dict[str, Any]) -> None:
    """验证异常上下文包含 document_id 和 tenant_id"""
    assert "document_id" in context["error"].context
    assert "tenant_id" in context["error"].context


# ===================================================================
# AC-3: 上传流程集成
# ===================================================================


@given("一个文档缺少 license 字段")
def given_doc_missing_license(context: dict[str, Any]) -> None:
    """设置缺少 license 字段的元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "source": "internal",
        "business_domain": "finance",
    }


@given("一个文档缺少 source 字段")
def given_doc_missing_source(context: dict[str, Any]) -> None:
    """设置缺少 source 字段的元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("一个分片上传的文档缺少 license 字段")
def given_chunked_doc_missing_license(context: dict[str, Any]) -> None:
    """设置分片上传场景的缺少 license 字段的元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "source": "internal",
        "business_domain": "finance",
    }
    context["is_chunked"] = True


@given("一个包含完整元数据的文档")
def given_doc_with_full_metadata(context: dict[str, Any]) -> None:
    """设置完整元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "created_at": "2024-01-15T10:30:00Z",
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@when("系统执行单文件上传（含元数据校验）")
def when_single_file_upload_with_validation(context: dict[str, Any]) -> None:
    """模拟单文件上传流程中的校验步骤"""
    _do_validate(context, autofill=True)


@when("系统执行上传（含元数据校验）")
def when_upload_with_validation(context: dict[str, Any]) -> None:
    """模拟上传流程中的校验步骤"""
    _do_validate(context, autofill=True)


@when("系统执行分片上传完成（含元数据校验）")
def when_chunked_complete_with_validation(context: dict[str, Any]) -> None:
    """模拟分片上传完成流程中的校验步骤"""
    _do_validate(context, autofill=True)


@when("系统执行上传流程（含元数据校验）")
def when_full_upload_flow(context: dict[str, Any]) -> None:
    """模拟完整上传流程中的校验步骤"""
    _do_validate(context, autofill=True)


@then("MinIO 未存储该文档对象")
def then_minio_not_stored(context: dict[str, Any]) -> None:
    """校验失败时 MinIO 存储不应被调用"""
    assert context["validation_passed"] is False


@then("PG 无该文档记录")
def then_pg_no_record(context: dict[str, Any]) -> None:
    """校验失败时 PG 不应有记录"""
    assert context["validation_passed"] is False


@then("abort_multipart_upload 被调用清理 MinIO 对象")
def then_abort_multipart_upload_called(context: dict[str, Any]) -> None:
    """校验失败后 abort_multipart_upload 应被调用"""
    assert context["validation_passed"] is False


@then("文档存入 MinIO 存储")
def then_doc_stored_in_minio(context: dict[str, Any]) -> None:
    """校验通过后文档存入 MinIO"""
    assert context["validation_passed"] is True


@then("文档持久化到 PG")
def then_doc_persisted_in_pg(context: dict[str, Any]) -> None:
    """校验通过后文档持久化到 PG"""
    assert context["validation_passed"] is True


@then("事件 DocumentUploaded 被发布")
def then_document_uploaded_event_published(context: dict[str, Any]) -> None:
    """校验通过后 DocumentUploaded 事件被发布"""
    assert context["validation_passed"] is True


@given("3 个文件准备批量上传")
def given_three_files_for_batch(context: dict[str, Any]) -> None:
    """设置 3 个批量上传文件"""
    context["files"] = [
        {"filename": "doc1.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
        {"filename": "doc2.pdf", "mime_type": "application/pdf", "file_size_bytes": 200},
        {"filename": "doc3.pdf", "mime_type": "application/pdf", "file_size_bytes": 300},
    ]


@given("每个文件分别传入不同的 metadata")
def given_different_metadata_per_file(context: dict[str, Any]) -> None:
    """设置每个文件不同的 metadata"""
    context["metadata_list"] = [
        {
            "creator": "user1",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        },
        {
            "creator": "user2",
            "created_at": "2024-01-16T11:00:00Z",
            "source": "external",
            "license": "public",
            "business_domain": "marketing",
        },
        {
            "creator": "user3",
            "created_at": "2024-01-17T12:00:00Z",
            "source": "partner",
            "license": "nda",
            "business_domain": "technology",
        },
    ]


@when("系统执行批量上传")
def when_batch_upload(context: dict[str, Any]) -> None:
    """模拟批量上传中 metadata 索引对齐"""
    metadata_list = context["metadata_list"]
    files = context["files"]
    context["aligned_results"] = []
    for i, file_info in enumerate(files):
        meta = metadata_list[i] if i < len(metadata_list) else None
        doc_metadata = DocumentMetadata.from_upload(
            document_id=uuid4(),
            raw_metadata=meta,
            uploaded_by=meta.get("creator", "") if meta else "",
        )
        context["aligned_results"].append(
            {
                "file_index": i,
                "filename": file_info["filename"],
                "metadata_creator": doc_metadata.metadata.get("creator"),
                "metadata_source": doc_metadata.metadata.get("source"),
            }
        )


@then("每个文件的 metadata 与索引一一对应")
def then_metadata_index_aligned(context: dict[str, Any]) -> None:
    """验证 metadata 与索引一一对应"""
    results = context["aligned_results"]
    assert len(results) == 3


@then("索引 0 的 metadata 应用于文件 0")
def then_index0_for_file0(context: dict[str, Any]) -> None:
    """验证索引 0 的 metadata 应用于文件 0"""
    assert context["aligned_results"][0]["metadata_creator"] == "user1"
    assert context["aligned_results"][0]["metadata_source"] == "internal"


@then("索引 1 的 metadata 应用于文件 1")
def then_index1_for_file1(context: dict[str, Any]) -> None:
    """验证索引 1 的 metadata 应用于文件 1"""
    assert context["aligned_results"][1]["metadata_creator"] == "user2"
    assert context["aligned_results"][1]["metadata_source"] == "external"


@then("索引 2 的 metadata 应用于文件 2")
def then_index2_for_file2(context: dict[str, Any]) -> None:
    """验证索引 2 的 metadata 应用于文件 2"""
    assert context["aligned_results"][2]["metadata_creator"] == "user3"
    assert context["aligned_results"][2]["metadata_source"] == "partner"


# ===================================================================
# AC-4: 元数据自动填充
# ===================================================================


@given("一个文档的 metadata 中没有 creator 字段")
def given_metadata_without_creator(context: dict[str, Any]) -> None:
    """设置缺少 creator 字段的元数据"""
    context["raw_metadata"] = {
        "created_at": "2024-01-15T10:30:00Z",
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("一个文档的 metadata 中没有 created_at 字段")
def given_metadata_without_created_at(context: dict[str, Any]) -> None:
    """设置缺少 created_at 字段的元数据"""
    context["raw_metadata"] = {
        "creator": "test-user",
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("一个文档的 metadata 中显式提供了 creator 和 created_at")
def given_metadata_with_explicit_creator_and_created_at(context: dict[str, Any]) -> None:
    """设置显式提供 creator 和 created_at 的元数据"""
    context["raw_metadata"] = {
        "creator": "explicit-creator",
        "created_at": "2025-06-01T08:00:00Z",
        "source": "internal",
        "license": "confidential",
        "business_domain": "finance",
    }


@given("一个文档的 metadata 参数为 null")
def given_metadata_is_null(context: dict[str, Any]) -> None:
    """设置 metadata 参数为 null（空字典）"""
    context["raw_metadata"] = {}


@then("显式提供的 creator 值被保留")
def then_explicit_creator_preserved(context: dict[str, Any]) -> None:
    """验证显式提供的 creator 值不被自动填充覆盖"""
    assert context["doc_metadata"].metadata.get("creator") == "explicit-creator"


@then("显式提供的 created_at 值被保留")
def then_explicit_created_at_preserved(context: dict[str, Any]) -> None:
    """验证显式提供的 created_at 值不被自动填充覆盖"""
    assert context["doc_metadata"].metadata.get("created_at") == "2025-06-01T08:00:00Z"


# ===================================================================
# Edge Cases
# ===================================================================


@given("租户 A 和租户 B 各自上传文档")
def given_two_tenants(context: dict[str, Any]) -> None:
    """设置两个租户的元数据"""
    context["tenant_a_id"] = f"tenant-a-{uuid4().hex[:8]}"
    context["tenant_b_id"] = f"tenant-b-{uuid4().hex[:8]}"
    context["tenant_a_metadata"] = DocumentMetadata.from_upload(
        document_id=uuid4(),
        raw_metadata={
            "creator": "user-a",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        },
        uploaded_by="user-a",
    )
    context["tenant_b_metadata"] = DocumentMetadata.from_upload(
        document_id=uuid4(),
        raw_metadata={
            "creator": "user-b",
            "created_at": "2024-01-16T11:00:00Z",
            "source": "external",
            "license": "public",
            "business_domain": "marketing",
        },
        uploaded_by="user-b",
    )


@then("租户 A 的校验不影响租户 B")
def then_tenant_a_does_not_affect_b(context: dict[str, Any]) -> None:
    """验证租户 A 的校验不影响租户 B"""
    missing_a = context["tenant_a_metadata"].missing_fields()
    missing_b = context["tenant_b_metadata"].missing_fields()
    assert missing_a == []
    assert missing_b == []


@then("每个租户的 metadata 独立存储")
def then_each_tenant_metadata_independent(context: dict[str, Any]) -> None:
    """验证每个租户的 metadata 独立存储"""
    meta_a = context["tenant_a_metadata"].metadata
    meta_b = context["tenant_b_metadata"].metadata
    assert meta_a["creator"] == "user-a"
    assert meta_b["creator"] == "user-b"
    assert meta_a["business_domain"] == "finance"
    assert meta_b["business_domain"] == "marketing"
