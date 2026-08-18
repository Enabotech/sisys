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

  场景: AC-7 - Story 3.12 组件通过 Resolver 注册
    假如 Story 3.12 Resolver 已初始化
    当 通过 Story 3.12 Resolver 解析组件
    那么 Story 3.12 组件均解析成功
    并且 ArchiveValidityHandler 已注册两个陈旧相关事件
