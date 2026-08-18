# language: zh-CN
功能: Story 3.12 数据陈旧标记
  合规工程师通过真实档案服务识别并降低陈旧数据权重，确保跨层状态一致。

  背景:
    假如 Story 3.12 PostgreSQL 验收服务已就绪

  场景: AC-3 - 过期档案被标记并发布 FactBecameStale
    假如 存在一个已过期的真实战略档案
    当 执行 Story 3.12 陈旧标记检查
    那么 L2 档案的 staleness 为 "stale"
    并且 L2 档案的 stale_reason 为 "expired"
    并且 已发布当前档案的 FactBecameStale 事件
    当 再次执行陈旧标记检查
    那么 重复检查结果不包含当前档案

  场景: AC-3 - 归档超过十二个月的档案记录正确原因
    假如 存在一个归档超过十二个月且没有 valid_until 的真实战略档案
    当 执行 Story 3.12 陈旧标记检查
    那么 L2 档案的 stale_reason 为 "archived_too_long"

  场景: AC-4 - fresh 和 stale 状态通过真实服务查询
    假如 存在一个 fresh 档案和一个 stale 档案
    当 按 staleness_status 为 "stale" 查询真实档案仓储
    那么 查询结果只包含 stale 档案
    当 按 staleness_status 为 "fresh" 查询真实档案仓储
    那么 查询结果不包含 stale 档案

  场景: AC-1 - 真实 L3/L5 写入有效期初始快照
    假如 真实 L3 和 L5 验收服务已就绪
    当 通过真实服务归档一个战略档案
    那么 L2 档案已持久化
    并且 L3 payload 包含空的有效期快照
    并且 L5 properties 包含空的有效期快照

  场景: AC-2 - ValidityPeriodSet 真实同步 L3/L5
    假如 真实 L3 和 L5 验收服务已就绪
    并且 已通过真实服务归档一个战略档案
    当 通过真实服务设置档案有效期
    那么 L3 payload 的有效期已同步
    并且 L5 properties 的有效期已同步

  场景: AC-3 - FactBecameStale 真实同步 L3
    假如 真实 L3 和 L5 验收服务已就绪
    并且 已通过真实服务归档一个过期战略档案
    当 通过真实服务执行陈旧标记并消费事件
    那么 L3 payload 已标记为陈旧

  场景: AC-4 - 真实 Qdrant 检索对陈旧结果降权
    假如 真实 Qdrant 验收服务已就绪
    当 写入一组真实 fresh 和 stale 向量档案并执行战略档案向量检索
    那么 fresh 结果排序高于 stale 结果
    并且 stale 结果分数已降低

  场景: AC-5 - 真实摘要服务提示陈旧引用
    假如 Story 3.12 PostgreSQL 验收服务已就绪
    并且 已准备一个真实陈旧档案的摘要检索结果
    当 生成 Story 3.12 陈旧摘要上下文
    那么 摘要上下文包含数据陈旧提示

  场景: AC-7 - Story 3.12 组件通过 Resolver 注册
    假如 Story 3.12 Resolver 已初始化
    当 通过 Story 3.12 Resolver 解析组件
    那么 Story 3.12 组件均解析成功
    并且 ArchiveValidityHandler 已注册两个陈旧相关事件
