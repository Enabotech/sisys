"""基础设施层数据源适配器包（Story 4.1b + 4.1f）

11 个数据源适配器（实现 DataSourcePort）：
- WorldBankAdapter / IMFAdapter / EurostatAdapter（统计类，无 Key）
- USPTOAdapter / IPCCAdapter（专利/环境，无 Key）
- NewsAPIAdapter / TavilyAdapter（新闻/搜索，需 API Key，条件注册）
- ChinaNBSAdapter（中国国家统计局，复用 CrawlerClientPort）
- EpoOpsAdapter（EPO 专利检索，OAuth2 双凭据门条件注册——Story 4.1f）
- SecEdgarAdapter（SEC 法定披露，免 key 无条件注册 + 强制 UA/限速——Story 4.1f）
- ComtradeAdapter（UN 贸易统计，key 可选增强无条件注册 + 日配额守卫——Story 4.1f）
"""
