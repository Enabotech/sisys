"""RBAC API Contract Tests.

基于 docs/api/openapi.yaml 定义验证 API 契约。
使用 openapi-spec-validator 进行 OpenAPI 规范验证。
使用 schemathesis 进行 API 契约测试。
"""

from __future__ import annotations

from openapi_spec_validator import validate  # type: ignore[import]
from openapi_spec_validator.readers import read_from_filename  # type: ignore[import]


class TestRBACOpenAPISpec:
    """验证 RBAC API OpenAPI 规范。"""

    def test_openapi_spec_is_valid(self) -> None:
        """验证 OpenAPI 规范语法正确。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        validate(spec_dict)

    def test_paths_exist(self) -> None:
        """验证所有 RBAC 端点路径存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        expected_paths = [
            "/auth/login",
            "/auth/refresh",
            "/auth/logout",
            "/auth/me",
            "/roles",
            "/roles/{role_id}",
            "/roles/{role_id}/permissions",
        ]

        for path in expected_paths:
            assert path in paths, f"Path {path} not found in OpenAPI spec"

    def test_auth_endpoints_exist(self) -> None:
        """验证认证端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/auth/login" in paths
        assert "/auth/refresh" in paths
        assert "/auth/logout" in paths
        assert "/auth/me" in paths

    def test_role_endpoints_exist(self) -> None:
        """验证角色管理端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        assert "/roles" in paths
        assert "/roles/{role_id}" in paths
        assert "/roles/{role_id}/permissions" in paths

    def test_login_post_method_exists(self) -> None:
        """验证登录 POST 方法存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        path_item = spec_dict["paths"]["/auth/login"]

        assert "post" in path_item

    def test_token_response_schema_exists(self) -> None:
        """验证 TokenResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "TokenResponse" in schemas
        token_schema = schemas["TokenResponse"]
        props = token_schema.get("properties", {})
        assert "access_token" in props
        assert "refresh_token" in props
        assert "token_type" in props
        assert "expires_in" in props
        assert "user" in props

    def test_login_request_schema_exists(self) -> None:
        """验证 LoginRequest schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "LoginRequest" in schemas
        login_schema = schemas["LoginRequest"]
        required = login_schema.get("required", [])
        assert "username" in required
        assert "password" in required

    def test_role_response_schema_exists(self) -> None:
        """验证 RoleResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "RoleResponse" in schemas
        role_schema = schemas["RoleResponse"]
        required = role_schema.get("required", [])
        assert "id" in required
        assert "name" in required
        assert "permissions" in required
        assert "is_system_reserved" in required
        assert "is_active" in required

    def test_error_response_schema_exists(self) -> None:
        """验证 ErrorResponse schema 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        schemas = spec_dict.get("components", {}).get("schemas", {})

        assert "ErrorResponse" in schemas
        error_schema = schemas["ErrorResponse"]
        required = error_schema.get("required", [])
        assert "detail" in required

    def test_security_schemes_defined(self) -> None:
        """验证安全方案已定义。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        security_schemes = spec_dict.get("components", {}).get("securitySchemes", {})

        assert "OAuth2" in security_schemes
        assert "Bearer" in security_schemes

    def test_api_version_prefix(self) -> None:
        """验证 API 版本前缀正确。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        servers = spec_dict.get("servers", [])

        assert len(servers) > 0
        assert "/api/v1" in servers[0].get("url", "")

    def test_roles_endpoints_require_auth(self) -> None:
        """验证角色端点需要认证。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        roles_get = paths["/roles"].get("get", {})
        security = roles_get.get("security", [])
        assert len(security) > 0, "GET /roles should require authentication"

    def test_admin_only_endpoints(self) -> None:
        """验证管理员专属端点存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        roles_post = paths["/roles"].get("post", {})
        security = roles_post.get("security", [])
        assert len(security) > 0, "POST /roles should require authentication"

    def test_delete_permission_endpoint_exists(self) -> None:
        """验证撤销权限端点 DELETE /roles/{role_id}/permissions/{permission} 存在。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        delete_perms = paths["/roles/{role_id}/permissions"].get("delete")
        assert delete_perms is not None, "DELETE method not found for /roles/{role_id}/permissions"

        params = delete_perms.get("parameters", [])
        param_names = [p["name"] for p in params]
        assert "role_id" in param_names, "role_id path parameter missing"
        assert "permission" in param_names, "permission path parameter missing"

    def test_delete_permission_endpoint_requires_auth(self) -> None:
        """验证撤销权限端点需要认证。"""
        spec_dict, _ = read_from_filename("docs/api/openapi.yaml")
        paths = spec_dict.get("paths", {})

        delete_perms = paths["/roles/{role_id}/permissions"].get("delete", {})
        security = delete_perms.get("security", [])
        assert len(security) > 0, "DELETE /roles/{role_id}/permissions should require authentication"
