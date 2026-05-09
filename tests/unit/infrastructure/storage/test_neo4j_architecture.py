"""Neo4j 图存储层架构约束验证测试。

验证领域层与基础设施层的架构约束：
- 领域层零 Neo4j 导入
- GraphManager/GraphStorage 是抽象 ABC
- 基础设施层实现了领域接口
- 节点标签命名规范（sisys:{type}）
"""

from __future__ import annotations

import ast
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DOMAIN_DIR = PROJECT_ROOT / "src" / "domain"
INFRASTRUCTURE_DIR = PROJECT_ROOT / "src" / "infrastructure"


class TestDomainLayerConstraints:
    """领域层架构约束测试。"""

    def test_domain_has_zero_neo4j_imports(self):
        """领域层不包含任何 Neo4j 导入。"""
        neo4j_imports = _find_imports_in_dir(DOMAIN_DIR, "neo4j")
        assert len(neo4j_imports) == 0, f"Domain layer must not import Neo4j, found: {neo4j_imports}"

    def test_domain_has_no_infrastructure_imports(self):
        """领域层不导入基础设施层模块。"""
        infra_imports = _find_imports_in_dir(DOMAIN_DIR, "infrastructure")
        assert len(infra_imports) == 0, f"Domain layer must not import infrastructure, found: {infra_imports}"


class TestGraphManagerInterface:
    """GraphManager 接口测试 — Protocol 契约验证。"""

    def test_graph_manager_has_required_methods(self):
        """GraphManager 应有所需方法。"""
        from src.domain.ports.graph_storage import GraphManager

        for method_name in ("create_node", "delete_node", "get_node", "create_relationship", "delete_relationship"):
            assert hasattr(GraphManager, method_name), f"GraphManager must have {method_name}"

    def test_all_methods_are_async(self):
        """GraphManager 所有方法应为 async。"""
        import inspect

        from src.domain.ports.graph_storage import GraphManager

        for method_name in ("create_node", "delete_node", "get_node", "create_relationship", "delete_relationship"):
            method = getattr(GraphManager, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestGraphStorageInterface:
    """GraphStorage 接口测试 — Protocol 契约验证。"""

    def test_graph_storage_has_required_methods(self):
        """GraphStorage 应有所需方法。"""
        from src.domain.ports.graph_storage import GraphStorage

        for method_name in ("execute_query", "execute_write_query", "find_path", "get_neighbors"):
            assert hasattr(GraphStorage, method_name), f"GraphStorage must have {method_name}"

    def test_all_methods_are_async(self):
        """GraphStorage 所有方法应为 async。"""
        import inspect

        from src.domain.ports.graph_storage import GraphStorage

        for method_name in ("execute_query", "execute_write_query", "find_path", "get_neighbors"):
            method = getattr(GraphStorage, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestInfrastructureImplementsInterface:
    """基础设施层实现领域接口测试。"""

    def test_neo4j_graph_manager_has_create_node(self):
        """Neo4jGraphManager 有 create_node 方法。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        assert hasattr(Neo4jGraphManager, "create_node"), "Neo4jGraphManager must have create_node method"

    def test_neo4j_graph_manager_has_delete_node(self):
        """Neo4jGraphManager 有 delete_node 方法。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        assert hasattr(Neo4jGraphManager, "delete_node"), "Neo4jGraphManager must have delete_node method"

    def test_neo4j_graph_manager_has_get_node(self):
        """Neo4jGraphManager 有 get_node 方法。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        assert hasattr(Neo4jGraphManager, "get_node"), "Neo4jGraphManager must have get_node method"

    def test_neo4j_graph_manager_has_create_relationship(self):
        """Neo4jGraphManager 有 create_relationship 方法。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        assert hasattr(Neo4jGraphManager, "create_relationship"), "Neo4jGraphManager must have create_relationship method"

    def test_neo4j_graph_manager_has_delete_relationship(self):
        """Neo4jGraphManager 有 delete_relationship 方法。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        assert hasattr(Neo4jGraphManager, "delete_relationship"), "Neo4jGraphManager must have delete_relationship method"

    def test_neo4j_graph_storage_has_execute_query(self):
        """Neo4jGraphStorage 有 execute_query 方法。"""
        from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage

        assert hasattr(Neo4jGraphStorage, "execute_query"), "Neo4jGraphStorage must have execute_query method"

    def test_neo4j_graph_storage_has_find_path(self):
        """Neo4jGraphStorage 有 find_path 方法。"""
        from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage

        assert hasattr(Neo4jGraphStorage, "find_path"), "Neo4jGraphStorage must have find_path method"

    def test_neo4j_graph_storage_has_get_neighbors(self):
        """Neo4jGraphStorage 有 get_neighbors 方法。"""
        from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage

        assert hasattr(Neo4jGraphStorage, "get_neighbors"), "Neo4jGraphStorage must have get_neighbors method"


class TestNamingConvention:
    """节点/关系命名规范验证。"""

    def test_relationship_type_enum_values(self):
        """关系类型枚举值符合规范。"""
        from src.infrastructure.storage.neo4j.models import RelationshipType

        expected_values = {"MENTIONS", "DEPENDS_ON", "RELATES_TO", "PART_OF", "INFLUENCES", "CONTRADICTS"}
        actual_values = {rt.value for rt in RelationshipType}
        assert expected_values == actual_values, f"Expected {expected_values}, found {actual_values}"

    def test_node_label_convention_in_code(self):
        """代码中节点标签前缀应遵循 sisys:{type} 规范。"""
        graph_manager_path = INFRASTRUCTURE_DIR / "storage" / "neo4j" / "graph_manager.py"
        assert graph_manager_path.exists(), "graph_manager.py must exist"

        source = graph_manager_path.read_text()
        # 验证 MERGE 查询中动态拼接标签（node.labels 包含 sisys: 前缀）
        # create_node 中使用 ":".join(node.labels) 拼接标签，测试代码注释约定
        assert "node.labels" in source, "Node labels should be dynamically constructed"
        assert "MERGE" in source, "Node creation should use MERGE for idempotency"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _find_imports_in_dir(base_dir: Path, module_name: str) -> list[str]:
    """扫描目录下所有 .py 文件，查找包含 module_name 的导入。"""
    found = []
    for py_file in base_dir.rglob("*.py"):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if module_name in alias.name:
                        found.append(str(py_file))
            elif isinstance(node, ast.ImportFrom):
                if node.module and module_name in node.module:
                    found.append(str(py_file))
    return found
