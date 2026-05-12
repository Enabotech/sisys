"""Audit API Contract Tests.

基于 docs/api/openapi.yaml 定义验证 API 契约。
使用 openapi-spec-validator 进行 OpenAPI 规范验证。
"""

from __future__ import annotations

from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename


class TestAuditOpenAPISpec:
    """验证 Audit API OpenAPI 规范。"""

    def test_openapi_spec_is_valid(self) -> None:
        """验证 OpenAPI 规范语法正确。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        validate(spec_dict)

    def test_paths_exist(self) -> None:
        """验证所有 Audit 端点路径存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        expected_paths = [
            "/audit/logs",
            "/audit/logs/{log_id}",
            "/audit/verify",
            "/audit/archive/status",
            "/audit/archive",
        ]

        for path in expected_paths:
            assert path in paths, f"Path {path} not found in OpenAPI spec"

    def test_audit_logs_get_exists(self) -> None:
        """验证审计日志检索端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/audit/logs" in paths
        assert "get" in paths["/audit/logs"]

    def test_audit_logs_detail_get_exists(self) -> None:
        """验证审计日志详情端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/audit/logs/{log_id}" in paths
        assert "get" in paths["/audit/logs/{log_id}"]

    def test_audit_verify_post_exists(self) -> None:
        """验证完整性验证端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/audit/verify" in paths
        assert "post" in paths["/audit/verify"]

    def test_audit_archive_status_get_exists(self) -> None:
        """验证归档状态查询端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/audit/archive/status" in paths
        assert "get" in paths["/audit/archive/status"]

    def test_audit_archive_post_exists(self) -> None:
        """验证手动归档端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/audit/archive" in paths
        assert "post" in paths["/audit/archive"]

    def test_audit_log_response_schema_exists(self) -> None:
        """验证 AuditLogResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "AuditLogResponse" in schemas
        audit_schema = schemas["AuditLogResponse"]
        required = audit_schema.get("required", [])
        assert "log_id" in required
        assert "timestamp" in required
        assert "actor" in required
        assert "action_type" in required
        assert "target_resource" in required
        assert "checksum" in required

    def test_audit_log_list_response_schema_exists(self) -> None:
        """验证 AuditLogListResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "AuditLogListResponse" in schemas
        list_schema = schemas["AuditLogListResponse"]
        required = list_schema.get("required", [])
        assert "items" in required
        assert "total" in required

    def test_integrity_verify_request_schema_exists(self) -> None:
        """验证 IntegrityVerifyRequest schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "IntegrityVerifyRequest" in schemas

    def test_integrity_verify_response_schema_exists(self) -> None:
        """验证 IntegrityVerifyResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "IntegrityVerifyResponse" in schemas
        response_schema = schemas["IntegrityVerifyResponse"]
        required = response_schema.get("required", [])
        assert "total" in required
        assert "passed" in required
        assert "failed" in required

    def test_archive_status_response_schema_exists(self) -> None:
        """验证 ArchiveStatusResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "ArchiveStatusResponse" in schemas
        archive_schema = schemas["ArchiveStatusResponse"]
        required = archive_schema.get("required", [])
        assert "log_id" in required
        assert "archived" in required

    def test_all_audit_endpoints_require_auth(self) -> None:
        """验证所有审计端点需要认证。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        audit_paths = [
            "/audit/logs",
            "/audit/logs/{log_id}",
            "/audit/verify",
            "/audit/archive/status",
            "/audit/archive",
        ]

        for path in audit_paths:
            path_item = paths.get(path, {})
            for method in ["get", "post"]:
                if method in path_item:
                    security = path_item[method].get("security", [])
                    assert len(security) > 0, f"{method.upper()} {path} should require authentication"

    def test_api_version_prefix(self) -> None:
        """验证 API 版本前缀正确。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        servers = spec_dict.get("servers", [])

        assert len(servers) > 0
        assert "/api/v1" in servers[0].get("url", "")

    def test_log_id_path_parameter_exists(self) -> None:
        """验证 log_id 路径参数定义正确。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        log_id_param = paths["/audit/logs/{log_id}"]["get"]["parameters"][0]
        assert log_id_param["name"] == "log_id"
        assert log_id_param["in"] == "path"
        assert log_id_param["required"] is True
        assert log_id_param["schema"]["format"] == "uuid"
