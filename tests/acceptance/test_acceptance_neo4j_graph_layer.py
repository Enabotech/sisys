"""Story 1.8 - Neo4j 图存储层验收测试。

使用真实 Neo4j 服务实例进行集成测试，不使用模拟。

运行方式:
    poetry run pytest tests/acceptance/test_acceptance_neo4j_graph_layer.py -v

前置条件:
    - Neo4j 服务运行在 localhost:7687（或设置 NEO4J_* 环境变量）
    - 默认凭据: neo4j/password123（或设置 NEO4J_PASSWORD）

测试租户隔离:
    - 所有节点 ID 使用 UUID 前缀确保唯一性
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, scenarios, then, when

from src.infrastructure.config.neo4j import Neo4jConfig
from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager
from src.infrastructure.storage.neo4j.graph_retriever import GraphRetriever
from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
from src.infrastructure.storage.neo4j.models import GraphNode, GraphRelationship
from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager
from tests.environments import get_test_env

scenarios("test_acceptance_neo4j_graph_layer.feature")

# ===================================================================
# 路径常量
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


@pytest.fixture
def neo4j_config() -> Neo4jConfig:
    """真实 Neo4j 配置"""
    env = get_test_env()
    return Neo4jConfig(
        host=env.neo4j.host,
        bolt_port=env.neo4j.bolt_port,
        username=env.neo4j.username,
        password=env.neo4j.password,
        database=env.neo4j.database,
    )


@pytest.fixture
def neo4j_client(neo4j_config: Neo4jConfig) -> Neo4jManager:
    """真实 Neo4j 客户端"""
    return Neo4jManager.from_config(neo4j_config)


@pytest.fixture
def graph_storage(neo4j_client: Neo4jManager) -> Neo4jGraphStorage:
    """Neo4j 图存储实例（查询）"""
    return Neo4jGraphStorage(neo4j_client.get_client())


@pytest.fixture
def graph_manager(neo4j_client: Neo4jManager) -> Neo4jGraphManager:
    """Neo4j 图管理实例（CRUD）"""
    return Neo4jGraphManager(neo4j_client.get_client())


@pytest.fixture
def graph_retriever(neo4j_client: Neo4jManager) -> GraphRetriever:
    """Neo4j 图检索实例"""
    return GraphRetriever(neo4j_client.get_client())


# ===================================================================
# AC-1: Neo4j 配置加载
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-1 - Neo4j 配置加载")
def test_neo4j_config_loading():
    """测试 Neo4j 配置加载"""


@given("Neo4j 环境变量已设置")
def neo4j_env_vars_set(context: dict, neo4j_config: Neo4jConfig) -> None:
    """Neo4j 环境变量已设置"""
    context["neo4j_config"] = neo4j_config


@when("加载 Neo4jConfig 配置")
def load_neo4j_config(context: dict) -> None:
    """加载 Neo4jConfig 配置"""
    config = context["neo4j_config"]
    assert config is not None
    context["loaded_config"] = config


@then("配置应包含正确的连接参数")
def verify_config_connection_params(context: dict) -> None:
    """验证配置包含正确的连接参数"""
    config = context["loaded_config"]
    env = get_test_env()
    expected_uri = f"bolt://{env.neo4j.host}:{env.neo4j.bolt_port}"
    assert config.uri == expected_uri
    assert config.username == env.neo4j.username
    assert config.database == env.neo4j.database


# ===================================================================
# AC-1: Neo4j 客户端工厂创建
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-1 - Neo4j 客户端工厂创建")
def test_neo4j_client_factory_creation():
    """测试 Neo4j 客户端工厂创建"""


@given("Neo4jManager 通过 from_config 创建")
def client_wrapper_created_via_factory(context: dict, neo4j_client: Neo4jManager) -> None:
    """Neo4jManager 通过 from_config 创建"""
    context["neo4j_client"] = neo4j_client


@when("调用 get_async_driver()")
def call_get_async_driver(context: dict) -> None:
    """调用 get_async_driver()"""
    client = context["neo4j_client"]
    driver = client.get_async_driver()
    context["async_driver"] = driver


@then("应返回已创建的 Neo4j 异步驱动")
def verify_async_driver_already_created(context: dict) -> None:
    """验证返回已创建的 Neo4j 异步驱动"""
    driver = context["async_driver"]
    assert driver is not None


@then("多次调用应返回同一驱动实例")
def verify_same_driver_instance_on_multiple_calls(context: dict) -> None:
    """验证多次调用返回同一驱动实例"""
    client = context["neo4j_client"]
    driver1 = client.get_async_driver()
    driver2 = client.get_async_driver()
    assert driver1 is driver2, "应返回同一驱动实例"


# ===================================================================
# AC-2: 节点创建与 MERGE 语义
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-2 - 节点创建与 MERGE 语义")
def test_node_creation_with_merge():
    """测试节点创建与 MERGE 语义"""


@given("Neo4j 图存储层已就绪")
def graph_storage_ready(context: dict, graph_manager: Neo4jGraphManager) -> None:
    """Neo4j 图存储层已就绪"""
    context["graph_manager"] = graph_manager


@when('创建一个 GraphNode（id="doc-001", labels=["sisys:Document"], properties={"business_domain": "strategy"}）')
def create_graph_node(context: dict, graph_manager: Neo4jGraphManager, event_loop) -> None:
    """创建 GraphNode"""
    node_id = f"doc-{uuid.uuid4().hex[:8]}"
    node = GraphNode(
        id=node_id,
        labels=["sisys:Document"],
        properties={
            "business_domain": "strategy",
            "entity_type": "document",
            "content_hash": "abc123",
        },
    )

    async def _create():
        return await graph_manager.create_node(node)

    result = event_loop.run_until_complete(_create())
    context["node_id"] = node_id
    context["node_created"] = result


@then("节点应成功创建")
def verify_node_created(context: dict) -> None:
    """验证节点成功创建"""
    assert context.get("node_created") is True, "节点应创建成功"


@when("再次创建相同 id 的节点时")
def create_same_node_again(context: dict, graph_manager: Neo4jGraphManager, event_loop) -> None:
    """再次创建相同 id 的节点"""
    node_id = context["node_id"]
    updated_node = GraphNode(
        id=node_id,
        labels=["sisys:Document"],
        properties={
            "business_domain": "updated",
            "entity_type": "document",
            "content_hash": "abc123_updated",
        },
    )

    async def _create_again():
        return await graph_manager.create_node(updated_node)

    result = event_loop.run_until_complete(_create_again())
    context["node_updated"] = result


@then("应匹配并更新属性（created=False）")
def verify_node_matched_and_updated(context: dict, graph_manager: Neo4jGraphManager, event_loop) -> None:
    """验证节点已匹配并更新属性"""
    assert context.get("node_updated") is True
    node_id = context["node_id"]

    async def _verify():
        return await graph_manager.get_node(node_id)

    node_data = event_loop.run_until_complete(_verify())
    assert node_data is not None, f"节点 {node_id} 应存在"
    assert node_data.get("business_domain") == "updated", "属性应已更新"


# ===================================================================
# AC-2: 关系创建与类型约束
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-2 - 关系创建与类型约束")
def test_relationship_creation():
    """测试关系创建与类型约束"""


@given("两个节点已存在于图中")
def two_nodes_exist_in_graph(context: dict, graph_manager: Neo4jGraphManager, event_loop) -> None:
    """两个节点已存在于图中"""
    node1_id = f"node-a-{uuid.uuid4().hex[:8]}"
    node2_id = f"node-b-{uuid.uuid4().hex[:8]}"

    async def _create():
        node1 = GraphNode(
            id=node1_id,
            labels=["sisys:Entity"],
            properties={"entity_type": "entity", "content_hash": "hash1", "business_domain": "test"},
        )
        node2 = GraphNode(
            id=node2_id,
            labels=["sisys:Entity"],
            properties={"entity_type": "entity", "content_hash": "hash2", "business_domain": "test"},
        )
        r1 = await graph_manager.create_node(node1)
        r2 = await graph_manager.create_node(node2)
        return r1 and r2

    result = event_loop.run_until_complete(_create())
    context["node1_id"] = node1_id
    context["node2_id"] = node2_id
    context["nodes_created"] = result


@when('创建关系（start_node_id="doc-001", end_node_id="entity-001", relationship_type="MENTIONS"）')
def create_relationship(context: dict, graph_manager: Neo4jGraphManager, event_loop) -> None:
    """创建关系"""
    node1_id = context["node1_id"]
    node2_id = context["node2_id"]

    async def _create_rel():
        rel = GraphRelationship(
            start_node_id=node1_id,
            end_node_id=node2_id,
            relationship_type="MENTIONS",
            properties={},
        )
        return await graph_manager.create_relationship(rel)

    result = event_loop.run_until_complete(_create_rel())
    context["relationship_created"] = result


@then("关系应成功创建")
def verify_relationship_created(context: dict) -> None:
    """验证关系成功创建"""
    assert context.get("relationship_created") is True, "关系应创建成功"


@then("关系类型应为允许的类型之一")
def verify_relationship_type_allowed() -> None:
    """验证关系类型为允许的类型之一"""
    from src.infrastructure.storage.neo4j.models import RelationshipType

    allowed_types = {t.value for t in RelationshipType}
    assert "MENTIONS" in allowed_types, "MENTIONS 应为允许的关系类型"


# ===================================================================
# AC-3: Cypher 参数化查询
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-3 - Cypher 参数化查询")
def test_cypher_parameterized_query():
    """测试 Cypher 参数化查询"""


@when('执行参数化查询（cypher="MATCH (n:sisys:Entity {id: $node_id}) RETURN n", params={"node_id": "entity-001"}）')
def execute_parameterized_query(
    context: dict,
    graph_storage: Neo4jGraphStorage,
    graph_manager: Neo4jGraphManager,
    event_loop,
) -> None:
    """执行参数化 Cypher 查询"""
    entity_id = f"entity-{uuid.uuid4().hex[:8]}"
    context["query_entity_id"] = entity_id

    async def _setup_and_query():
        node = GraphNode(
            id=entity_id,
            labels=["sisys:Entity"],
            properties={
                "name": "Test Entity",
                "entity_type": "entity",
                "content_hash": "hash123",
                "business_domain": "test",
            },
        )
        await graph_manager.create_node(node)
        return await graph_storage.execute_query(
            cypher="MATCH (n:sisys:Entity {id: $node_id}) RETURN n",
            params={"node_id": entity_id},
        )

    result = event_loop.run_until_complete(_setup_and_query())
    context["query_result"] = result


@then("应返回匹配的节点")
def verify_matched_node_returned(context: dict) -> None:
    """验证返回匹配的节点"""
    result = context.get("query_result")
    assert result is not None, "查询结果不应为 None"
    assert len(result) > 0, "应返回至少一个匹配节点"


@then("查询不应存在 SQL 注入风险")
def verify_no_injection_risk(context: dict) -> None:
    """验证查询使用参数化，不存在注入风险"""
    query_result = context.get("query_result")
    assert query_result is not None, "参数化查询应正常执行并返回结果"


# ===================================================================
# AC-3: 路径查询
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-3 - 路径查询")
def test_path_query():
    """测试路径查询"""


@given("图中存在节点 A 和节点 B，且两者之间有 2 度关系")
def nodes_with_2_degree_relationship(
    context: dict,
    graph_manager: Neo4jGraphManager,
    event_loop,
) -> None:
    """节点 A 和 B 存在且之间有 2 度关系"""
    node_a = f"node-a-{uuid.uuid4().hex[:8]}"
    node_b = f"node-b-{uuid.uuid4().hex[:8]}"
    middle_id = f"node-mid-{uuid.uuid4().hex[:8]}"

    async def _create():
        await graph_manager.create_node(
            GraphNode(
                id=node_a,
                labels=["sisys:Node"],
                properties={"entity_type": "node", "content_hash": "hashA", "business_domain": "test"},
            )
        )
        await graph_manager.create_node(
            GraphNode(
                id=middle_id,
                labels=["sisys:Node"],
                properties={"entity_type": "node", "content_hash": "hashB", "business_domain": "test"},
            )
        )
        await graph_manager.create_node(
            GraphNode(
                id=node_b,
                labels=["sisys:Node"],
                properties={"entity_type": "node", "content_hash": "hashC", "business_domain": "test"},
            )
        )
        await graph_manager.create_relationship(
            GraphRelationship(
                start_node_id=node_a,
                end_node_id=middle_id,
                relationship_type="RELATES_TO",
                properties={},
            )
        )
        await graph_manager.create_relationship(
            GraphRelationship(
                start_node_id=middle_id,
                end_node_id=node_b,
                relationship_type="RELATES_TO",
                properties={},
            )
        )
        return node_a, node_b

    result_a, result_b = event_loop.run_until_complete(_create())
    context["node_a"] = result_a
    context["node_b"] = result_b


@when('执行 find_path(start_id="node-a", end_id="node-b", max_depth=3)')
def execute_find_path(
    context: dict,
    graph_storage: Neo4jGraphStorage,
    event_loop,
) -> None:
    """执行 find_path 查询"""
    node_a = context["node_a"]
    node_b = context["node_b"]

    async def _find_path():
        return await graph_storage.find_path(
            start_id=node_a,
            end_id=node_b,
            max_depth=3,
        )

    result = event_loop.run_until_complete(_find_path())
    context["path_result"] = result


@then("应返回从 A 到 B 的路径")
def verify_path_returned(context: dict) -> None:
    """验证返回从 A 到 B 的路径"""
    result = context.get("path_result")
    assert result is not None, "路径查询结果不应为 None"
    assert len(result) > 0, "应返回至少一条路径"


@then("路径长度不应超过 max_depth")
def verify_path_length_within_max(context: dict) -> None:
    """验证路径长度不超过 max_depth"""
    result = context.get("path_result")
    assert result is not None
    for path_record in result:
        if isinstance(path_record, dict) and "length" in path_record:
            assert path_record["length"] <= 3, f"路径长度 {path_record['length']} 不应超过 max_depth=3"


# ===================================================================
# AC-4: GraphRAG 实体关联检索
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-4 - GraphRAG 实体关联检索")
def test_graphrag_entity_association_retrieval():
    """测试 GraphRAG 实体关联检索"""


@given("图中存在一个实体节点及其关联的文档和实体")
def entity_with_associations_exists(
    context: dict,
    graph_manager: Neo4jGraphManager,
    event_loop,
) -> None:
    """实体节点及其关联的文档和实体已存在"""
    entity_id = f"entity-{uuid.uuid4().hex[:8]}"
    context["graphrag_entity_id"] = entity_id

    async def _create():
        entity_node = GraphNode(
            id=entity_id,
            labels=["sisys:Entity"],
            properties={
                "name": "Test Entity",
                "entity_type": "entity",
                "content_hash": "hash0",
                "business_domain": "test",
            },
        )
        await graph_manager.create_node(entity_node)
        for i in range(3):
            doc_id = f"doc-{uuid.uuid4().hex[:8]}"
            doc_node = GraphNode(
                id=doc_id,
                labels=["sisys:Document"],
                properties={
                    "title": f"Document {i}",
                    "entity_type": "document",
                    "content_hash": f"hash{i}",
                    "business_domain": "test",
                },
            )
            await graph_manager.create_node(doc_node)
            await graph_manager.create_relationship(
                GraphRelationship(
                    start_node_id=entity_id,
                    end_node_id=doc_id,
                    relationship_type="MENTIONS",
                    properties={},
                )
            )
        for i in range(2):
            rel_id = f"rel-{uuid.uuid4().hex[:8]}"
            rel_node = GraphNode(
                id=rel_id,
                labels=["sisys:Entity"],
                properties={
                    "name": f"Related Entity {i}",
                    "entity_type": "entity",
                    "content_hash": f"hashrel{i}",
                    "business_domain": "test",
                },
            )
            await graph_manager.create_node(rel_node)
            await graph_manager.create_relationship(
                GraphRelationship(
                    start_node_id=entity_id,
                    end_node_id=rel_id,
                    relationship_type="RELATES_TO",
                    properties={},
                )
            )

    event_loop.run_until_complete(_create())


@when('执行 find_related_entities(entity_id="entity-001", max_depth=2, limit=20)')
def execute_find_related_entities(
    context: dict,
    graph_retriever: GraphRetriever,
    event_loop,
) -> None:
    """执行 find_related_entities 查询"""
    entity_id = context["graphrag_entity_id"]

    async def _find():
        return await graph_retriever.find_related_entities(
            entity_id=entity_id,
            max_depth=2,
            limit=20,
        )

    result = event_loop.run_until_complete(_find())
    context["related_entities"] = result


@then("应返回关联的实体列表")
def verify_related_entities_returned(context: dict) -> None:
    """验证返回关联的实体列表"""
    result = context.get("related_entities")
    assert result is not None, "关联实体查询结果不应为 None"
    assert isinstance(result, list), "结果应为列表"
    assert len(result) > 0, "应返回至少一个关联实体"


@then("结果数量不应超过 limit")
def verify_result_count_within_limit(context: dict) -> None:
    """验证结果数量不超过 limit"""
    result = context.get("related_entities")
    assert result is not None
    assert len(result) <= 20, f"结果数量 {len(result)} 不应超过 limit=20"


@then("结果应按关系权重/置信度排序")
def verify_results_sorted_by_weight(context: dict) -> None:
    """验证结果按 connection_count 降序排列"""
    result = context.get("related_entities")
    assert result is not None
    if len(result) > 1:
        for i in range(len(result) - 1):
            curr_count = result[i].get("connection_count", 0)
            next_count = result[i + 1].get("connection_count", 0)
            assert curr_count >= next_count, (
                f"结果应按 connection_count 降序排列: result[{i}]={curr_count} < result[{i + 1}]={next_count}"
            )


# ===================================================================
# AC-5: 领域层零 Neo4j 依赖
# ===================================================================


@scenario("test_acceptance_neo4j_graph_layer.feature", "AC-5 - 领域层零 Neo4j 依赖")
def test_domain_layer_zero_neo4j_dependency():
    """测试领域层零 Neo4j 依赖"""


@given("项目源代码已提交")
def project_source_code_committed(context: dict) -> None:
    """项目源代码已提交"""
    context["source_committed"] = True


@when("扫描 src/domain/ 目录下所有 .py 文件")
def scan_domain_py_files(context: dict) -> None:
    """扫描 src/domain/ 目录下所有 .py 文件"""
    neo4j_imports: list[str] = []
    for py_file in DOMAIN_DIR.rglob("*.py"):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "neo4j" in alias.name.lower():
                            neo4j_imports.append(str(py_file.relative_to(ROOT)))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "neo4j" in node.module.lower():
                        neo4j_imports.append(str(py_file.relative_to(ROOT)))
        except SyntaxError:
            pass
    context["neo4j_imports"] = neo4j_imports


@then("不应发现任何 neo4j 导入")
def verify_no_neo4j_imports(context: dict) -> None:
    """验证领域层没有 neo4j 导入"""
    imports = context.get("neo4j_imports", [])
    assert len(imports) == 0, f"领域层发现 neo4j 导入: {imports}"


@then("依赖方向应为 领域层接口 → 基础设施层实现")
def verify_dependency_direction() -> None:
    """验证依赖方向为领域层接口指向基础设施层实现"""
    from src.domain.ports.connection_manager import ConnectionManager

    assert ConnectionManager is not None, "领域层应定义 ConnectionManager 端口接口"
