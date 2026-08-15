"""Story 3.5 分层检索 API 契约测试

验证 OpenAPI 3.1 契约定义与实际实现一致。
遵循 story-template.md §SDD 规范定义 — API 契约测试

注意：当前 API 路由（src/interfaces/api/layered_retrieval.py）尚未实现，
端点标记为 x-implemented: false。本测试仅验证契约定义完整性。
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


class TestLayeredRetrievalPathsInContract:
    """分层检索 API 路径在契约中定义"""

    LAYERED_PATH = "/api/v1/search/layered"

    def test_layered_search_path_exists(self) -> None:
        """POST /api/v1/search/layered 路径存在"""
        spec = load_openapi_spec()
        assert self.LAYERED_PATH in spec["paths"]
        path_item = spec["paths"][self.LAYERED_PATH]
        assert "post" in path_item
        # 端点标记为未实现，保留契约定义供后续迭代
        assert path_item["post"].get("x-implemented") is False

    def test_layered_search_request_schema(self) -> None:
        """LayeredRetrievalRequest schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "LayeredRetrievalRequest" in schemas
        props = schemas["LayeredRetrievalRequest"]["properties"]
        assert "query_text" in props
        assert "target_level" in props
        assert "collection" in props
        assert "limit" in props
        assert "direction" in props

    def test_layered_search_response_schema(self) -> None:
        """LayeredRetrievalResponse schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "LayeredRetrievalResponse" in schemas
        props = schemas["LayeredRetrievalResponse"]["properties"]
        assert "results" in props
        assert "total" in props
