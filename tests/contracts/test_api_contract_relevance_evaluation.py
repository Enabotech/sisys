"""Story 3.7 检索相关性评估 API 契约测试

验证 OpenAPI 3.1 契约中 /api/v1/search/evaluate 端点定义。
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
    validate_spec(cast(Any, spec))


class TestRelevanceEvaluationPathsInContract:
    """检索相关性评估 API 路径在契约中定义"""

    EVALUATE_PATH = "/api/v1/search/evaluate"

    def test_evaluate_path_exists(self) -> None:
        """POST /api/v1/search/evaluate 路径存在"""
        spec = load_openapi_spec()
        assert self.EVALUATE_PATH in spec["paths"]
        path_item = spec["paths"][self.EVALUATE_PATH]
        assert "post" in path_item

    def test_evaluate_request_schema(self) -> None:
        """EvaluateRequest schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "EvaluateRequest" in schemas
        props = schemas["EvaluateRequest"]["properties"]
        assert "query_text" in props
        assert "tenant_id" in props

    def test_evaluate_response_schema(self) -> None:
        """EvaluateResponse schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "EvaluateResponse" in schemas
        props = schemas["EvaluateResponse"]["properties"]
        assert "overall_score" in props
        assert "context_relevance" in props
        assert "completeness" in props
        assert "timeliness" in props
        assert "context_relevance_reason" in props
        assert "completeness_reason" in props
        assert "timeliness_reason" in props
        assert "should_block" in props
        assert "block_reason" in props

    def test_evaluate_path_security(self) -> None:
        """评估端点通过认证中间件"""
        spec = load_openapi_spec()
        path_item = spec["paths"][self.EVALUATE_PATH]
        assert "security" in path_item["post"]
