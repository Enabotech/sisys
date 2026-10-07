"""Story 4-6: API 契约测试 — 工具版本管理端点（6 端点 / 5 path）

规范先行模式 B（test_api_contract_document_version.py 先例）：
openapi.yaml 在 Task 0.5 已定义规范——本测试静态断言规范内容（Task 0 即绿）；
路由实现（Task 6）落地后升级为 TestClient 真实请求验证。

端点清单（AC-6 表）：
- POST/GET /tools/{tool_id}/versions —— 注册 / 列表
- POST /tools/{tool_id}/versions/{version}/publish —— 发布（灰度/调档/全量/转正）
- POST /tools/{tool_id}/rollback —— 回滚
- POST /tools/{tool_id}/abort-canary —— 放弃灰度
- GET  /tools/{tool_id}/versions/traffic —— 流量视图
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

OPENAPI_PATH = Path("docs/api/openapi.yaml")

EXPECTED_TOOL_PATHS = {
    "/tools/{tool_id}/versions",
    "/tools/{tool_id}/versions/{version}/publish",
    "/tools/{tool_id}/rollback",
    "/tools/{tool_id}/abort-canary",
    "/tools/{tool_id}/versions/traffic",
}

EXPECTED_TOOL_SCHEMAS = {
    "ToolVersionCreate",
    "ToolVersionResponse",
    "ToolVersionListResponse",
    "PublishRequest",
    "RollbackRequest",
    "TrafficViewResponse",
}


def _load_spec() -> dict[str, Any]:
    """加载 openapi.yaml 规范。"""
    with OPENAPI_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


class TestToolVersionAPIContract:
    """工具版本管理端点的 OpenAPI 契约静态断言（规范先行模式 B）。"""

    def test_all_tool_paths_defined(self) -> None:
        """5 个 tool path 全部定义（6 端点，GET/POST 共享 versions path）。"""
        spec = _load_spec()
        paths = spec.get("paths", {})
        missing = EXPECTED_TOOL_PATHS - set(paths)
        assert not missing, f"OpenAPI 缺少 tool path: {missing}"

    def test_versions_path_supports_post_and_get(self) -> None:
        """versions path 同时支持 POST（注册）与 GET（列表）。"""
        spec = _load_spec()
        path_item = spec["paths"]["/tools/{tool_id}/versions"]
        assert "post" in path_item, "versions 应支持 POST（注册）"
        assert "get" in path_item, "versions 应支持 GET（列表）"

    def test_register_returns_201(self) -> None:
        """注册端点返回 201。"""
        spec = _load_spec()
        responses = spec["paths"]["/tools/{tool_id}/versions"]["post"]["responses"]
        assert "201" in responses

    def test_register_error_codes_declared(self) -> None:
        """注册端点声明 400(242)/401/404(380)/409(431/397)。"""
        spec = _load_spec()
        responses = spec["paths"]["/tools/{tool_id}/versions"]["post"]["responses"]
        for code in ("400", "401", "404", "409"):
            assert code in responses, f"注册端点缺少 {code} 响应定义"

    def test_publish_request_schema_bounds(self) -> None:
        """PublishRequest 权重域 (0,100]：minimum 1 / maximum 100 / default 100。"""
        spec = _load_spec()
        schema = spec["components"]["schemas"]["PublishRequest"]
        weight = schema["properties"]["traffic_weight"]
        assert weight["minimum"] == 1, "权重域 (0,100]——minimum 应为 1（0 无业务语义）"
        assert weight["maximum"] == 100
        assert weight["default"] == 100

    def test_rollback_request_target_optional(self) -> None:
        """RollbackRequest.target_version 可选（缺省回滚最近稳定版）。"""
        spec = _load_spec()
        schema = spec["components"]["schemas"]["RollbackRequest"]
        assert "target_version" in schema["properties"]
        assert "required" not in schema or "target_version" not in schema.get("required", [])

    def test_all_tool_schemas_defined(self) -> None:
        """6 组 tool Schema 全部定义。"""
        spec = _load_spec()
        schemas = spec.get("components", {}).get("schemas", {})
        missing = EXPECTED_TOOL_SCHEMAS - set(schemas)
        assert not missing, f"OpenAPI 缺少 tool schema: {missing}"

    def test_version_response_status_enum(self) -> None:
        """ToolVersionResponse.status 枚举与状态机值域一致（小写四态）。"""
        spec = _load_spec()
        schema = spec["components"]["schemas"]["ToolVersionResponse"]
        assert set(schema["properties"]["status"]["enum"]) == {
            "pending",
            "canary",
            "stable",
            "deprecated",
        }

    def test_all_tool_operations_require_auth(self) -> None:
        """全部 6 端点声明 OAuth2 security。"""
        spec = _load_spec()
        path_item = spec["paths"]["/tools/{tool_id}/versions"]
        for method in ("post", "get"):
            security = path_item[method].get("security", [])
            assert len(security) > 0, f"versions {method} 缺少 security 定义"
        for path in (
            "/tools/{tool_id}/versions/{version}/publish",
            "/tools/{tool_id}/rollback",
            "/tools/{tool_id}/abort-canary",
            "/tools/{tool_id}/versions/traffic",
        ):
            security = spec["paths"][path]["post" if "traffic" not in path else "get"].get("security", [])
            assert len(security) > 0, f"{path} 缺少 security 定义"
