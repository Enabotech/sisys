# 数据源扩展专项 — 候选源可用性预筛报告

> **日期：** 2026-09-29 | **性质：** 「数据源扩展专项」Story 立项输入（判据②的 Task 0 预筛）
> **方法：** 四路并行调研（专利域/企业财报域/行业量化域/中文媒体域），全部关键结论含实测证据（curl 直连端点 / 官方 ToS 抓取），非文档推断。
> **背景：** Skills 23/23 收官后，「源数量充足性」为最后质量缺口——维度级 ≥3 受限于 8 适配器池的语义域分布（专利 1/宏观 4/新闻检索 2/气候 1）。本报告回答「哪些候选源可开发、哪些出局、前置是什么」。

---

## 一、总裁定表（19 个候选源 × 四域）

| 域 | 候选源 | 结论 | 一句话依据 |
|---|---|---|---|
| 专利 | **EPO Espacenet OPS** | ✅ **有条件可行（第一优先）** | 免费注册 OAuth2；4 GB/周免费；`pa=`申请人字段化检索（支持中文「华为」）+ `ti/ab` 关键词；JSON 官方支持；100+ 局含 CN；周更 |
| 专利 | **Google Patents BigQuery** | ✅ **有条件可行（第二优先）** | CN 覆盖实证 99.96%（SSRN 2025）；1 TiB/月免费查询；assignee SQL 精确聚合；短板=季度新鲜度 + GCP 服务账号前置 |
| 专利 | CNIPA 国知局 | ❌ 不可行 | 无公开 API（三大门户 WAF 全拦截：412/202/超时）；批量数据走 ipdps 人工申请+FTP；观察 2026-08 数据开放政策 |
| 专利 | WIPO PATENTSCOPE | ❌ 不可行 | 600–2000 CHF/年付费；SOAP 仅 PCT 文档递送**无检索端点**；明示不含国家局数据（无 CN 国内申请）——三项全错配 |
| 财报 | **SEC EDGAR** | ✅ **可行** | 免费无 key（强制 UA）；10 req/s；XBRL 结构化营收（companyfacts/frames 跨公司横截面天然适合份额加总）+ 全文检索实测命中 3340 份 10-K |
| 财报 | **巨潮资讯 cninfo** | ✅ **可行** | 实测免 key 全通（沪深一号通：300750 宁德时代 + 600519 茅台年报均可查）；公告元数据 + 年报 PDF；无结构化财务（需 PDF 解析二期）；法务确认转载边界 |
| 财报 | **港交所披露易 HKEXnews** | ✅ **可行** | 实测两段式查询全通（prefix.do + titleSearchServlet.do 实测 133 条）；公告 PDF 206；无 XBRL |
| 财报 | 上交所 query.sse.com.cn | ⚠️ 有条件可行 | JSONP + 强制 Referer 实测通；端点稳定性存疑——定位 cninfo 交叉校验源 |
| 财报 | 深交所 szse.cn/api | ❌ 不可行 | 实测 GET 500 / POST 50x——深市由 cninfo 覆盖 |
| 财报 | 东方财富/新浪/同花顺 | ⚠️ 有条件可行（灰区降级源） | 东财实测通且有结构化营收时序（RPT_LICO_FN_CPD）且 robots 宽松，但协议禁行情数据复制/衍生——仅内部引用不作主源；同花顺反爬不建议 |
| 行业量化 | **UN Comtrade** | ✅ **可行（首选）** | 实测无 key 返回 195 条真实记录（中国 2024 HS8703 整车出口）；免费 key 500 次/天、10 万条/次；HS 商品级行业进出口代理（月频） |
| 行业量化 | **OECD SDMX (STAN)** | ✅ **可行** | 实测 STAN 2025 全量 CSV 139,345 行；ISIC 行业级（OECD 成员国，不含中国）——国际行业结构基准 |
| 行业量化 | **FRED** | ✅ 可行 | 免费 key 注册即得；美国行业级（NAICS）强、中国序列弱；署名要求 + 版权序列再分发限制 |
| 行业量化 | EU Open Data Portal | ✅ 可行 | 实测 API 200；Eurostat SBS（NACE 行业级）经此分发；许可随数据集逐集校验 |
| 行业量化 | 中汽协 CAAM / 乘联会 CPCA | ⚠️ 有条件可行 | 公开产销简析免费网页（实测 caam.org.cn http 通 / cada.cn 月报页通）；crawler 月频/周频；HTML 解析维护成本 |
| 行业量化 | **IDC** | ❌ 不可行（致命证据） | ToS §2.2(g) 明文禁爬 + §2.2(e) 禁输入 AI/分析平台 + 订阅 $15K–75K+/年——对本项目三重致命 |
| 行业量化 | **Gartner** | ❌ 不可行（致命证据） | robots.txt 均返回 Cloudflare 挑战页（技术层全拦截）；扩展访问须书面批准；无公开定价 |
| 行业量化 | Statista Connect | ❌ 当前不可行（备选） | credit 计费需销售采购无免费层；**若未来采购是四家中集成成本最低的**（官方 MCP/SDK 现成） |
| 行业量化 | Euromonitor / 电池联盟等协会 | ❌ 不可行 | 纯询价无公开通道 / 无公开官网靠媒体转载（汽协乘联会是例外） |
| 中文媒体 | **现有 tavily/newsapi 适配器参数扩展** | ✅ **最优先微改动（~10 行/适配器）** | 实测确认适配器未传 `language=zh-cn/country=china/topic=news`（tavily_adapter L104-108）与 `language=zh/domains`（newsapi_adapter L105）——中文缺口可能一半是参数未启用；**先验证再决定是否需要新源** |
| 中文媒体 | 百度千帆 AI 搜索 | ⚠️ 有条件可行 | 唯一合规中文搜索通道（直连百度爬取违反 robots）；¥0.036–0.072/次付费 |
| 中文媒体 | 新浪滚动/东财资讯 API | ⚠️ 有条件可行（灰区） | 实测免认证返回当天数据；无文档内部接口——需限频/熔断/改版监控义务登记 |
| 中文媒体 | GDELT 中文 | ❌ 不可行 | 实测中文检索崩坏 + `sourcelang:zho` 返回空 + 1 req/5s 限流 |
| 中文媒体 | RSS 路线（财新/36氪/虎嗅/晚点） | ❌ 全军覆没 | 四源四死：DNS 失效/火山引擎 WAF/超时/无 RSS——`rss+xml` 形态对本域标记不可用 |

**统计：可行 7 + 有条件可行 8 + 不可行 10（含全部付费墙商业机构与 RSS 形态）**

---

## 二、对原设想清单的关键修正

1. **CNIPA/WIPO 出局**（原专利域两候选）→ 专利域改走 **EPO OPS（近实时检索）+ Google Patents BigQuery（CN 全景聚合）** 组合，且 OPS 的 `pa=` 申请人检索直接补齐评审指出的「uspto 无归因」短板
2. **IDC/Gartner/Euromonitor 确认致命**（不可仅归因价格——IDC 合同禁爬+禁 AI 平台、Gartner 技术层全拦截）→ 行业份额量化改走 **Comtrade 贸易代理 + 协会公开产销 + OECD/统计局行业基准** 组合逼近；商业机构独家数据显式声明为能力边界
3. **中文缺口的最优解可能不是新源**——现有 tavily/newsapi 适配器未启用官方中文参数（实测证据），~20 行总改动先验证；验证后剩余缺口再决定百度千帆（付费合规）或东财/新浪（灰区登记）
4. **意外收获**：企业财报域三官方披露源全通（SEC/cninfo/HKEXnews）——企业级数据供给比预想强，且 SEC XBRL frames 支持跨公司营收横截面（份额加总）

## 三、前置申请清单（免费但周期不同，可并行启动）

| 前置项 | 用途 | 申请方式 | 周期 |
|---|---|---|---|
| EPO OPS Consumer Key/Secret | 专利域首选源 | developers.epo.org 免费注册（邮件确认） | 快（即时–数日） |
| UN Comtrade API key | 行业量化首选源 | comtradedeveloper.un.org 注册（500 次/天） | 快 |
| FRED API key | 行业量化补充 | fred.stlouisfed.org 注册 | 即时 |
| GCP 服务账号（BigQuery） | 专利域第二源 | GCP 项目 + 服务账号 JSON（Sandbox 免信用卡） | 需 GCP 账号 |
| 法务确认单 | cninfo/HKEX 公告内部使用边界、东财灰区、千帆采购评估 | 立项时风险登记册 | 法务流程 |

## 四、建议的专项 Story 分期

- **Phase 0（微 Story，先行验证）：** tavily/newsapi 中文参数扩展（各 ~10 行 + 集成测试）——用证据决定中文域剩余缺口
- **Phase 1（第一批适配器）：** EPO OPS（新增 OAuth2 认证模式）+ SEC EDGAR（UA+限速）+ UN Comtrade（key）——三个零许可成本、实测已通
- **Phase 2（第二批）：** Google Patents BigQuery（GCP）+ cninfo/HKEXnews（含 PDF→文本管道拆期）+ CAAM/CADA crawler
- **Phase 3（声明重分配联动）：** 受益 Skill 的 data_sources/维度映射/yaml/frontmatter/契约库四方联动 + `required_fields` 按源定制（原 4.3 defer 项一并承载）+ D2 统一 2 源策略修订决策
- **显式能力边界声明：** IDC/Gartner/Euromonitor 独家份额数据不可得（合同与技术双重壁垒），以代理指标组合替代

---

*调研证据与逐源细节（实测端点/响应/条款原文）见四路调研报告全文；本文件为立项决策摘要 SSOT。*
