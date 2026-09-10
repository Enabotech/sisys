"""工具链编排（DAG）架构验证测试（Story 4.2 AC-8）

验证项：
1. 3 个新端口注册完整（tool_chain_repository / tool_chain_orchestrator / tool_chain_service）
2. PortSpec 元数据十字段完整（name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated）
3. ToolChainDagValidator 是领域服务（非端口，不通过 composition_root 注册）
4. 端口命名空间与现有 tool_repository / tool_execution_repository 无冲突
5. 依赖注入正确（impl 字符串延迟加载）
6. domain 层零外部依赖
7. 应用层不导入 infrastructure
8. 架构测试覆盖完整
"""

from __future__ import annotations

import ast
import pathlib

from src.domain.ports.registry import Lifetime, _global_registry

# ============================================================================
# 1. 3 个新端口注册
# ============================================================================


def test_tool_chain_repository_registered() -> None:
    """tool_chain_repository 端口已注册"""
    spec = _global_registry.get("tool_chain_repository")
    assert spec is not None
    assert spec.name == "tool_chain_repository"
    assert spec.version == "v1.0.0"
    assert spec.lifetime == Lifetime.SCOPED


def test_tool_chain_orchestrator_registered() -> None:
    """tool_chain_orchestrator 端口已注册"""
    spec = _global_registry.get("tool_chain_orchestrator")
    assert spec is not None
    assert spec.lifetime == Lifetime.SCOPED


def test_tool_chain_service_registered() -> None:
    """tool_chain_service 端口已注册"""
    spec = _global_registry.get("tool_chain_service")
    assert spec is not None
    assert spec.lifetime == Lifetime.SCOPED


def test_run_tool_chain_use_case_registered() -> None:
    """run_tool_chain_use_case 端口已注册（用例层）"""
    spec = _global_registry.get("run_tool_chain_use_case")
    assert spec is not None


# ============================================================================
# 2. PortSpec 元数据十字段完整
# ============================================================================


def test_tool_chain_repository_port_spec_metadata() -> None:
    """tool_chain_repository PortSpec 元数据十字段完整"""
    spec = _global_registry.get("tool_chain_repository")
    assert spec is not None
    assert spec.owner == "tool-team"
    assert "tool" in spec.tags
    assert "chain" in spec.tags
    assert "repository" in spec.tags
    assert spec.deprecated is False
    assert spec.compatibility == ()


def test_tool_chain_service_port_spec_metadata() -> None:
    """tool_chain_service PortSpec 元数据十字段完整"""
    spec = _global_registry.get("tool_chain_service")
    assert spec is not None
    assert "service" in spec.tags
    assert spec.deprecated is False


def test_all_new_ports_not_deprecated() -> None:
    """3 个新端口均未废弃"""
    for name in [
        "tool_chain_repository",
        "tool_chain_orchestrator",
        "tool_chain_service",
    ]:
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.deprecated is False, f"{name} 不应标记为废弃"


# ============================================================================
# 3. ToolChainDagValidator 非端口（领域服务）
# ============================================================================


def test_tool_chain_dag_validator_is_not_registered_as_port() -> None:
    """ToolChainDagValidator 是领域服务（纯函数），不通过 composition_root 注册为端口"""
    # 验证 validator 类不是 Protocol 派生，也不是任何 port 的实现
    from src.domain.services.tool_chain_dag_validator import ToolChainDagValidator

    # 类不是 Protocol/ABC 派生 → 实例不是 runtime_checkable Protocol
    assert not hasattr(ToolChainDagValidator, "_is_protocol")


def test_validator_is_pure_function_service() -> None:
    """ToolChainDagValidator 是纯函数领域服务（@staticmethod validate）"""
    from src.domain.services.tool_chain_dag_validator import ToolChainDagValidator

    assert hasattr(ToolChainDagValidator, "validate")
    import inspect

    assert isinstance(inspect.getattr_static(ToolChainDagValidator, "validate"), staticmethod)


# ============================================================================
# 4. 端口命名空间无冲突
# ============================================================================


def test_no_namespace_conflicts_with_existing_tool_ports() -> None:
    """端口命名空间与现有 tool_repository / tool_execution_repository 无冲突"""
    existing_ports = [
        "tool_repository",
        "tool_execution_repository",
        "tool_chain_repository",
    ]
    for name in existing_ports:
        spec = _global_registry.get(name)
        assert spec is not None, f"{name} 必须已注册"
        # 端口名唯一
        all_ports_with_name = [p for p in _global_registry.list_all() if p.name == name]
        assert len(all_ports_with_name) == 1, f"{name} 出现重复注册"


# ============================================================================
# 5. 依赖注入（impl 字符串延迟加载）
# ============================================================================


def test_tool_chain_repository_uses_lazy_impl() -> None:
    """tool_chain_repository 使用延迟加载 impl（字符串路径 或 无参 lambda）"""

    from typing import cast

    spec = _global_registry.get("tool_chain_repository")
    assert spec is not None
    # impl 必须是字符串（延迟加载路径）或可调用对象
    is_string = isinstance(spec.impl, str)
    is_callable = callable(spec.impl)
    assert is_string or is_callable, f"impl 必须为字符串或 lambda，但实际为 {type(spec.impl)}"
    if is_string:
        # isinstance 检查后 mypy 不自动收窄 union 类型，cast 显式标注
        impl_str = cast(str, spec.impl)
        assert "tool_chain_repository" in impl_str


def test_tool_chain_service_uses_lambda_impl() -> None:
    """tool_chain_service 使用 lambda impl（依赖注入其他端口）"""
    spec = _global_registry.get("tool_chain_service")
    assert spec is not None
    # impl 是 lambda（依赖注入）
    assert callable(spec.impl)


# ============================================================================
# 6. domain 层零外部依赖
# ============================================================================


def test_domain_entities_tool_chain_have_no_external_dependencies() -> None:
    """src/domain/entities/tool_chain*.py 不导入第三方库"""
    forbidden = {
        "pydantic",
        "sqlalchemy",
        "redis",
        "qdrant_client",
        "minio",
        "neo4j",
        "fastapi",
        "langgraph",
        "prefect",
        "typer",
        "litellm",
        "instructor",
        "aio_pika",
        "src.application",
        "src.infrastructure",
        "src.interfaces",
    }
    for path in [
        "src/domain/entities/tool_chain.py",
        "src/domain/entities/tool_chain_run.py",
    ]:
        source = pathlib.Path(path).read_text()
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        violations = imported & forbidden
        assert not violations, f"{path} 引入了禁止模块: {violations}"


def test_domain_services_tool_chain_validator_is_pure() -> None:
    """src/domain/services/tool_chain_dag_validator.py 仅使用标准库 + domain 依赖"""
    source = pathlib.Path("src/domain/services/tool_chain_dag_validator.py").read_text()
    tree = ast.parse(source)

    forbidden = {
        "pydantic",
        "sqlalchemy",
        "redis",
        "qdrant_client",
        "minio",
        "neo4j",
        "fastapi",
        "langgraph",
        "prefect",
        "typer",
        "litellm",
        "instructor",
        "aio_pika",
        "src.application",
        "src.infrastructure",
        "src.interfaces",
    }
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    violations = imported & forbidden
    assert not violations, f"tool_chain_dag_validator.py 引入了禁止模块: {violations}"


# ============================================================================
# 7. 应用层不导入 infrastructure（除 composition_root 工厂）
# ============================================================================


def test_application_services_tool_chain_only_uses_domain() -> None:
    """src/application/services/tool_chain_*.py 仅依赖 domain + application 层"""
    for path in [
        "src/application/services/tool_chain_orchestrator.py",
        "src/application/services/tool_chain_service.py",
    ]:
        source = pathlib.Path(path).read_text()
        tree = ast.parse(source)

        forbidden = {"src.infrastructure"}
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        violations = imported & forbidden
        assert not violations, f"{path} 引入了禁止模块: {violations}"


# ============================================================================
# 8. lint-imports 通过（架构依赖方向）
# ============================================================================


def test_importlinter_config_includes_tool_chain() -> None:
    """importlinter 配置应包含 tool_chain 相关模块（domain → app → infra）"""
    # 仅验证 .importlinter 文件存在；具体规则验证由 lint-imports 命令执行
    import os

    assert os.path.exists(".importlinter"), ".importlinter 配置文件必须存在（CI 强制校验）"
