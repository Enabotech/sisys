"""基础设施层数据源适配器包（Story 4.1b）

8 个数据源适配器（实现 DataSourcePort）：
- WorldBankAdapter / IMFAdapter / EurostatAdapter（统计类，无 Key）
- USPTOAdapter / IPCCAdapter（专利/环境，无 Key）
- NewsAPIAdapter / TavilyAdapter（新闻/搜索，需 API Key，条件注册）
- ChinaNBSAdapter（中国国家统计局，复用 CrawlerClientPort）
"""
