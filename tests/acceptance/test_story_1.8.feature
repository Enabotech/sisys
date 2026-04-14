# Story 1.8: Neo4j Graph Layer - Acceptance Tests
# 验收标准: AC-1 ~ AC-5

Feature: Neo4j 图存储层
  As a 系统架构师
  I want 实现 Neo4j 图存储层（L5 存储）
  So that 系统可以存储知识图谱、实体关系和依赖图

  Scenario: AC-1 - Neo4j 配置加载
    Given Neo4j 环境变量已设置
      | 变量                    | 值                      |
      | NEO4J_URI               | bolt://localhost:7687   |
      | NEO4J_USERNAME          | neo4j                   |
      | NEO4J_PASSWORD          | test-password           |
      | NEO4J_DATABASE          | neo4j                   |
      | NEO4J_MAX_POOL_SIZE     | 50                      |
      | NEO4J_CONNECT_TIMEOUT   | 30.0                    |
    When 加载 Neo4jConfig 配置
    Then 配置应包含正确的连接参数
      | 字段                      | 期望值                    |
      | uri                       | bolt://localhost:7687     |
      | username                  | neo4j                     |
      | password                  | test-password             |
      | database                  | neo4j                     |
      | max_connection_pool_size  | 50                        |
      | connection_timeout        | 30.0                      |

  Scenario: AC-1 - Neo4j 客户端懒初始化
    Given Neo4jClientWrapper 已实例化但客户端未创建
    When 首次调用 get_async_driver()
    Then 应创建 Neo4j 异步驱动
    And 后续调用应复用同一驱动实例

  Scenario: AC-2 - 节点创建与 MERGE 语义
    Given Neo4j 图存储层已就绪
    When 创建一个 GraphNode（id="doc-001", labels=["sisys:Document"], properties={"business_domain": "strategy"}）
    Then 节点应成功创建
    And 当再次创建相同 id 的节点时应匹配并更新属性（created=False）

  Scenario: AC-2 - 关系创建与类型约束
    Given 两个节点已存在于图中
    When 创建关系（start_node_id="doc-001", end_node_id="entity-001", relationship_type="MENTIONS"）
    Then 关系应成功创建
    And 关系类型应为允许的类型之一

  Scenario: AC-3 - Cypher 参数化查询
    Given Neo4j 图存储层已就绪
    When 执行参数化查询（cypher="MATCH (n:sisys:Entity {id: $node_id}) RETURN n", params={"node_id": "entity-001"}）
    Then 应返回匹配的节点
    And 查询不应存在 SQL 注入风险

  Scenario: AC-3 - 路径查询
    Given 图中存在节点 A 和节点 B，且两者之间有 2 度关系
    When 执行 find_path(start_id="node-a", end_id="node-b", max_depth=3)
    Then 应返回从 A 到 B 的路径
    And 路径长度不应超过 max_depth

  Scenario: AC-4 - GraphRAG 实体关联检索
    Given 图中存在一个实体节点及其关联的文档和实体
    When 执行 find_related_entities(entity_id="entity-001", max_depth=2, limit=20)
    Then 应返回关联的实体列表
    And 结果数量不应超过 limit
    And 结果应按关系权重/置信度排序

  Scenario: AC-5 - 领域层零 Neo4j 依赖
    Given 项目源代码已提交
    When 扫描 src/domain/ 目录下所有 .py 文件
    Then 不应发现任何 neo4j 导入
    And 依赖方向应为 领域层接口 → 基础设施层实现
