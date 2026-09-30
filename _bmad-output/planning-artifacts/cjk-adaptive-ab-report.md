# 中文参数 CJK 自适应 A/B 实测报告（Story 4.1f AC-1）

> **日期：** 2026-09-30 | **状态：** 断言层验证完成；真实 key 实测面**待补**（key 属外部申请资产，就绪后补测）
> **证据等级声明：** 本报告结论分两级——【断言级】MockTransport 请求形态验证（已完备）；【实测级】真实端点质量对比（key 就绪后补，当前零实测数据）

---

## 一、改动内容（Phase 0 微改动）

| 适配器 | 改动 | 注入参数 | 依据 |
|--------|------|---------|------|
| tavily | fetch 内 `_contains_cjk(query)` 门控 | 请求体 + `"country": "china"` | Tavily 官方 /search 参数表：`country` 为官方全名枚举（含 china），"Boost search results from a specific country"，**仅 topic=general 时可用**（本适配器不传 topic，默认 general——生效成立） |
| newsapi | 同上 | params + `"language": "zh"` | NewsAPI 官方 /v2/everything 参数：`language` 为 ISO 639-1（zh=中文）；`country` 属 /v2/top-headlines 端点不适用 |

- 检测规则：`any("一" <= ch <= "鿿" for ch in query.query)`（CJK 统一表意文字区段；中英混合 query 判定为真）
- 非 CJK 路径：请求体/参数与既有形态**逐键一致**（回归基线断言锁定——零既有影响）

## 二、【断言级】验证结果（已完备——单测 + 验收双面）

| 验证项 | 结果 | 证据 |
|--------|------|------|
| tavily CJK → country=china | ✅ | `TestTavilyCjkAdaptiveParams.test_cjk_query_adds_country_china`（38 passed 之一） |
| tavily 中英混合 → 同注入 | ✅ | `test_mixed_cjk_english_query_adds_country` |
| tavily 非 CJK → 请求体逐键零变化 | ✅ | `test_non_cjk_query_body_unchanged_baseline`（键集 == {api_key, query, max_results}） |
| newsapi CJK → language=zh | ✅ | `TestNewsAPICjkAdaptiveParams.test_cjk_query_adds_language_zh` |
| newsapi 中英混合 → 同注入 | ✅ | `test_mixed_cjk_english_query_adds_language` |
| newsapi 非 CJK → 参数逐键零变化 | ✅ | `test_non_cjk_query_params_unchanged_baseline`（键集 == {q, pageSize, sortBy}） |
| 既有行为零回归 | ✅ | 受影响 13 个声明 Skill（newsapi 8 ∪ tavily 10 去重——Task 6 声明重分配**前**口径，计数以契约库 SSOT 为准）+ 契约/架构三层 1130 passed（时点值） |
| 验收场景（BDD） | ✅ | `test_acceptance_data_source_expansion.py` AC-1.1~1.4 四场景（AC-1.1/1.3 由红转绿） |

## 三、【实测级】待补项（key 就绪后执行——AC-1 此时方可升级为完整完成）

1. **A/B 质量对比**：同 query（建议「比亚迪 战略动态 并购 新能源汽车」「宁德时代 产能扩张」两组）在改动前后对比结果相关性/权威源覆盖率
2. **中英混合语料反效果检验**（风险 R10）：混合 query 的 country 收窄是否漏掉英文权威源——若实测证明反效果，回退方案为 `language=zh-cn` 替代（Tavily 官方 language 参数，ISO 639-1；两参数互补）
3. **topic/domains 参数评估**（epics AC-1 偏差登记项）：`topic=news|finance`（tavily）/`domains`（newsapi）是否引入——有实测证据再议（本 Story 未预加，避免影响 13 个 Skill 英文场景）

## 四、剩余缺口结论（证据等级：官方文档分析——非实测）

基于官方参数文档覆盖面分析（非实测数据）：`country=china`（地域加权）+ `language=zh`（语言过滤）组合启用后，**预计**中文检索质量的主要缺口（预筛报告「中文参数缺口」结论：适配器未传中文参数）预计可覆盖（待实测级验证确认）；但「专职中文源」（百度千帆/东财等）是否仍必要，**依赖第三节实测级验证**——在实测数据就位前**不下否定结论**（AC-1 按两态设计记「部分完成」，缺口判断 defer 至 key 就绪，owner 已知情）。

## 五、结论

- CJK 自适应规则的**正确性不依赖实测**（断言级全绿）：门控确定性、零回归、参数官方存在性已验证
- 真实质量增益与反效果检验待 key（已登记 Story R7/R8 与 Defer 台账——key 到位人工补跑）
