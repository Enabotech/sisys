"""安全监控 API 契约测试 — 等保2.0三级

基于 docs/api/openapi.yaml 定义验证安全监控 API 契约
验证9个安全监控端点和对应 schema 的完整性

对应 Story: 1-12-equilibrium-level-3-compliance Task 0 Subtask 0.6
"""

from __future__ import annotations

from typing import Any

from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename


class TestSecurityOpenAPISpec:
    """验证安全监控 API OpenAPI 规范"""

    def test_openapi_spec_is_valid(self) -> None:
        """验证 OpenAPI 规范语法正确"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        validate(spec_dict)


class TestSecurityPathsExist:
    """验证安全监控端点路径存在"""

    def test_all_security_paths_exist(self) -> None:
        """验证所有安全监控端点路径存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        expected_paths = [
            "/security/intrusions",
            "/security/intrusions/{event_id}",
            "/security/intrusions/block",
            "/security/intrusions/stats",
            "/security/integrity/verify",
            "/security/backups",
            "/security/backups/{backup_id}/restore",
            "/security/backups/status",
            "/security/compliance/report",
        ]

        for path in expected_paths:
            assert path in paths, f"Path {path} not found in OpenAPI spec"

    def test_intrusions_get_exists(self) -> None:
        """验证入侵事件列表端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/intrusions" in paths
        assert "get" in paths["/security/intrusions"]

    def test_intrusions_detail_get_exists(self) -> None:
        """验证入侵事件详情端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/intrusions/{event_id}" in paths
        assert "get" in paths["/security/intrusions/{event_id}"]

    def test_intrusions_block_post_exists(self) -> None:
        """验证IP阻断端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/intrusions/block" in paths
        assert "post" in paths["/security/intrusions/block"]

    def test_intrusions_stats_get_exists(self) -> None:
        """验证入侵统计端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/intrusions/stats" in paths
        assert "get" in paths["/security/intrusions/stats"]

    def test_integrity_verify_post_exists(self) -> None:
        """验证数据完整性验证端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/integrity/verify" in paths
        assert "post" in paths["/security/integrity/verify"]

    def test_backups_get_exists(self) -> None:
        """验证备份列表端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/backups" in paths
        assert "get" in paths["/security/backups"]

    def test_backups_post_exists(self) -> None:
        """验证创建备份端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/backups" in paths
        assert "post" in paths["/security/backups"]

    def test_backups_restore_post_exists(self) -> None:
        """验证备份恢复端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/backups/{backup_id}/restore" in paths
        assert "post" in paths["/security/backups/{backup_id}/restore"]

    def test_backups_status_get_exists(self) -> None:
        """验证备份状态端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/backups/status" in paths
        assert "get" in paths["/security/backups/status"]

    def test_compliance_report_get_exists(self) -> None:
        """验证合规报告端点存在"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/security/compliance/report" in paths
        assert "get" in paths["/security/compliance/report"]


class TestSecuritySchemasExist:
    """验证安全监控 schemas 存在"""

    def _get_schemas(self) -> dict[str, Any]:
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas: dict[str, Any] = spec_dict.get("components", {}).get("schemas", {})
        return schemas

    def test_intrusion_event_response_schema_exists(self) -> None:
        """验证 IntrusionEventResponse schema 存在"""
        schemas = self._get_schemas()
        assert "IntrusionEventResponse" in schemas
        required = schemas["IntrusionEventResponse"].get("required", [])
        assert "event_id" in required
        assert "attack_type" in required
        assert "severity" in required

    def test_block_ip_request_schema_exists(self) -> None:
        """验证 BlockIPRequest schema 存在"""
        schemas = self._get_schemas()
        assert "BlockIPRequest" in schemas
        required = schemas["BlockIPRequest"].get("required", [])
        assert "ip_address" in required

    def test_intrusion_stats_response_schema_exists(self) -> None:
        """验证 IntrusionStatsResponse schema 存在"""
        schemas = self._get_schemas()
        assert "IntrusionStatsResponse" in schemas
        required = schemas["IntrusionStatsResponse"].get("required", [])
        assert "total_attacks" in required

    def test_create_backup_request_schema_exists(self) -> None:
        """验证 CreateBackupRequest schema 存在"""
        schemas = self._get_schemas()
        assert "CreateBackupRequest" in schemas
        required = schemas["CreateBackupRequest"].get("required", [])
        assert "backup_type" in required

    def test_backup_response_schema_exists(self) -> None:
        """验证 BackupResponse schema 存在"""
        schemas = self._get_schemas()
        assert "BackupResponse" in schemas
        required = schemas["BackupResponse"].get("required", [])
        assert "backup_id" in required
        assert "success" in required

    def test_restore_backup_response_schema_exists(self) -> None:
        """验证 RestoreBackupResponse schema 存在"""
        schemas = self._get_schemas()
        assert "RestoreBackupResponse" in schemas
        required = schemas["RestoreBackupResponse"].get("required", [])
        assert "success" in required

    def test_compliance_report_response_schema_exists(self) -> None:
        """验证 ComplianceReportResponse schema 存在"""
        schemas = self._get_schemas()
        assert "ComplianceReportResponse" in schemas
        required = schemas["ComplianceReportResponse"].get("required", [])
        assert "total_domains" in required
        assert "compliance_score" in required
        assert "results" in required


class TestSecurityEndpointsRequireAuth:
    """验证安全监控端点需要认证"""

    def test_all_security_endpoints_require_bearer_auth(self) -> None:
        """所有安全监控端点应要求 Bearer 认证"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        security_paths = [
            "/security/intrusions",
            "/security/intrusions/{event_id}",
            "/security/intrusions/block",
            "/security/intrusions/stats",
            "/security/integrity/verify",
            "/security/backups",
            "/security/backups/{backup_id}/restore",
            "/security/backups/status",
            "/security/compliance/report",
        ]

        for path in security_paths:
            path_spec = paths[path]
            for method, operation in path_spec.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    security = operation.get("security", [])
                    assert len(security) > 0, f"{method.upper()} {path} requires authentication"
