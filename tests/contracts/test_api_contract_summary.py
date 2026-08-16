"""Story 3.6 契约化摘要生成 API 契约测试

验证 OpenAPI 3.1 契约中 /api/v1/search/summary 端点定义。
"""

from __future__ import annotations

from typing import Any, cast

import yaml
from openapi_spec_validator import validate_spec


def load_openapi_spec() -> dict[str, Any]:
    """加载 OpenAPI 契约文件"""
    with open("docs/api/openapi.yaml") as f:
        return cast(dict[str, Any], yaml.safe_load(f))


def test_openapi_spec_is_valid() -> None:
    """OpenAPI 3.1 规范语法正确"""
    spec = load_openapi_spec()
    validate_spec(cast(Any, spec))  # openapi_spec_validator 类型标注不完整


class TestSummaryPathsInContract:
    """摘要生成 API 路径在契约中定义"""

    SUMMARY_PATH = "/api/v1/search/summary"

    def test_summary_path_exists(self) -> None:
        """POST /api/v1/search/summary 路径存在"""
        spec = load_openapi_spec()
        assert self.SUMMARY_PATH in spec["paths"]
        path_item = spec["paths"][self.SUMMARY_PATH]
        assert "post" in path_item

    def test_summary_request_schema(self) -> None:
        """SummaryRequest schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "SummaryRequest" in schemas
        props = schemas["SummaryRequest"]["properties"]
        assert "query_text" in props
        assert "perspective" in props
        assert "top_k" in props
        assert "tenant_id" in props

    def test_summary_response_schema(self) -> None:
        """SummaryResponse schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "SummaryResponse" in schemas
        props = schemas["SummaryResponse"]["properties"]
        assert "summary" in props
        assert "query_text" in props
        assert "perspective" in props
        assert "confidence_score" in props
        assert "source_documents" in props

    def test_summary_path_security(self) -> None:
        """摘要生成端点通过认证中间件"""
        spec = load_openapi_spec()
        path_item = spec["paths"][self.SUMMARY_PATH]
        assert "security" in path_item["post"]
