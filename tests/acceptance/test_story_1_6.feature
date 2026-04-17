# language: zh-CN

功能: Qdrant 向量存储层
  作为系统架构师
  我希望实现 Qdrant 向量存储层（L3 存储）
  以便系统可以存储嵌入向量并执行混合检索（Dense+Sparse）
  满足检索延迟 P95<800ms 的性能目标

  背景:
    假如 Qdrant 服务可用
    并且 Collection 命名规范为 "sisys:{collection_type}:{namespace}"

  场景: Collection 创建与删除
    当 我创建 Collection "sisys:documents:finance" 向量维度 1024
    那么 Collection 应该存在
    当 我删除 Collection "sisys:documents:finance"
    那么 Collection 应该不存在

  场景: 向量点插入与查询
    假如 Collection "sisys:documents:finance" 已存在
    当 我插入 10 个向量点（带 payload 元数据）
    那么 插入应该成功
    当 我查询向量点 "point-1"
    那么 应该返回对应的向量点数据

  场景: Dense 语义检索
    假如 Collection "sisys:documents:finance" 包含 100 个向量点
    当 我执行 Dense 检索（查询向量 1024 维，limit=10）
    那么 应该返回最多 10 个结果
    并且结果按相似度降序排列

  场景: Dense 检索 payload 过滤
    假如 Collection "sisys:documents:finance" 包含不同业务域的向量点
    当 我执行 Dense 检索并过滤 business_domain="report"
    那么 所有结果的 business_domain 应该为 "report"

  场景: BM25 稀疏检索
    假如 Collection "sisys:documents:finance" 包含文本向量点
    当 我执行 BM25 稀疏检索（稀疏向量从文本构建）
    那么 应该返回关键词匹配的结果

  场景: 多租户隔离
    假如 Collection "sisys:documents:finance" 和 "sisys:documents:hr" 存在
    当 我向 "sisys:documents:finance" 插入向量点
    那么 "sisys:documents:hr" 不应该包含这些向量点

  场景: 领域层零 Qdrant 依赖
    当 我扫描 src/domain/ 目录
    那么 不应该有任何 qdrant_client 导入
