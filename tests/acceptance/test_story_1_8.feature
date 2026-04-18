# language: zh-CN
功能: Neo4j 图存储层

  作为系统架构师
  我想要实现 Neo4j 图存储层（L5 存储）
  以便系统可以存储知识图谱、实体关系和依赖图

  场景: AC-1 - Neo4j 配置加载
    假如 Neo4j 环境变量已设置
    当 加载 Neo4jConfig 配置
    那么 配置应包含正确的连接参数

  场景: AC-1 - Neo4j 客户端懒初始化
    假如 Neo4jClientWrapper 已实例化但客户端未创建
    当 首次调用 get_async_driver()
    那么 应创建 Neo4j 异步驱动
    并且 后续调用应复用同一驱动实例

  场景: AC-2 - 节点创建与 MERGE 语义
    假如 Neo4j 图存储层已就绪
    当 创建一个 GraphNode（id="doc-001", labels=["sisys:Document"], properties={"business_domain": "strategy"}）
    那么 节点应成功创建
    当 再次创建相同 id 的节点时
    那么 应匹配并更新属性（created=False）

  场景: AC-2 - 关系创建与类型约束
    假如 两个节点已存在于图中
    当 创建关系（start_node_id="doc-001", end_node_id="entity-001", relationship_type="MENTIONS"）
    那么 关系应成功创建
    并且 关系类型应为允许的类型之一

  场景: AC-3 - Cypher 参数化查询
    假如 Neo4j 图存储层已就绪
    当 执行参数化查询（cypher="MATCH (n:sisys:Entity {id: $node_id}) RETURN n", params={"node_id": "entity-001"}）
    那么 应返回匹配的节点
    并且 查询不应存在 SQL 注入风险

  场景: AC-3 - 路径查询
    假如 图中存在节点 A 和节点 B，且两者之间有 2 度关系
    当 执行 find_path(start_id="node-a", end_id="node-b", max_depth=3)
    那么 应返回从 A 到 B 的路径
    并且 路径长度不应超过 max_depth

  场景: AC-4 - GraphRAG 实体关联检索
    假如 图中存在一个实体节点及其关联的文档和实体
    当 执行 find_related_entities(entity_id="entity-001", max_depth=2, limit=20)
    那么 应返回关联的实体列表
    并且 结果数量不应超过 limit
    并且 结果应按关系权重/置信度排序

  场景: AC-5 - 领域层零 Neo4j 依赖
    假如 项目源代码已提交
    当 扫描 src/domain/ 目录下所有 .py 文件
    那么 不应发现任何 neo4j 导入
    并且 依赖方向应为 领域层接口 → 基础设施层实现
