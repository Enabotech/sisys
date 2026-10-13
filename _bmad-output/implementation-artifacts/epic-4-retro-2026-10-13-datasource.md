---
epic: 4
epic_title: 战略工具箱——专题增补回顾（分析工具调用与数据源可用性）
date: 2026-10-13
status: completed
nature: 专题增补回顾（第二次——聚焦差距 #3「数据源门控可用性 P1」闭合验证）
participants:
  - Amelia (Developer - 主持人)
  - Alice (Product Owner)
  - Charlie (Senior Dev)
  - Dana (QA Engineer)
  - Winston (Architect)
  - 3-body (Project Lead)
---

# Epic 4 专题增补回顾：分析战略工具调用实现与数据源可用性

## 一、背景与议题

2026-10-12 标准 Epic 4 回顾留下差距 #3「数据源门控可用性 P1」（影响 Epic 6 市场洞察实证）。本次专题回顾响应 3-body 提出的新约束：**uspto / newsapi / epo-ops / google-patents 四源注册困难、中国用户访问需代理**，评估更方便的替代方案，并裁定数据源供给能否支撑后续 Epic 开发。

取证范围：`registration.py` 注册表 SSOT + 16 个 Skill 的 data_sources 声明全量扫描（49 处引用）+ resolver/marker 降级机制代码审读 + 预筛报告（2026-09-29）+ CJK A/B 报告 + deferred-work.md 2026-10-12 核查记录 + 当日网络验证（EPO 注册政策 / 新闻 API 替代格局）。

## 二、事实矩阵

### 2.1 数据源可用性 × Skill 依赖面 × 大陆可达性

| 数据源 | 组/门 | 状态（2026-10-13） | Skill 引用数 | 大陆直连 |
|---|---|---|---|---|
| tavily | B（单 Key） | ✅ 已配（10-12 探活 200） | **10**（最广） | 当前环境可达 |
| newsapi | B（单 Key） | ❌ 缺 Key | 8 | 普遍不可达 |
| world-bank | A | ✅ 200 | 7 | 可达 |
| china-nbs | A | ✅ crawler 端到端实证 | 6 | ✅（自研插件） |
| imf / eurostat / ipcc | A | ✅ 200 | 3 / 3 / 2 | 可达 |
| sec-edgar | A | ⚠️ 403 待真实调用验证（UA 头） | 1 | 参差 |
| comtrade | A | ✅ 免 Key preview 兜底 | **0（孤立条目）** | 可达 |
| uspto | B（单 Key） | ❌ 缺 Key | 3 | 不稳定 |
| epo-ops | B（OAuth2 双凭据） | ❌ 缺 Key | 3 | **欧洲节点一般可直连** |
| google-patents | C（GCP 双门+文件门） | ❌ 缺凭据 | 3 | **GFW 确定性封锁** |

专利三库（uspto/epo-ops/google-patents）仅被 3 个 Skill 引用且高度重合：competitor-analysis / disruptive-innovation / vrio-framework——三者均同时声明 tavily（已配）。

### 2.2 降级机制验证（Epic 4 交付的底牌）

- 单源未注册（门关→适配器静默缺席）→ `fetch()` 抛 `DataSourceUnavailableError`(411)（`data_source_resolver.py:150-157`）+ `DataSourceFetchFailed` 事件遥测
- 引擎侧 `fetch_many`（`data_source_resolver.py:212-236`）：`asyncio.gather(return_exceptions=True)`，单源失败位填 `None` 占位（`data_source_marker.py:302` 注入字面量 None）——**仅当全部源失败才硬失败**（`any(results)` 收敛）
- Skill SOP 配套降级话术（competitor SKILL.md:282「部分失败不中断分析」；标记读取强制 `.get()` 防御）
- HTTP 出口映射：411 → 503（`exception_handlers.py:249`）

## 三、关键发现

1. **tavily 配置（10-12）后，「零 Key 部署全坍塌」Skill 数从 5 降为 0**——change-management / disruptive-innovation / swot-tows / value-curve-analysis / vrio-framework 原本数据源 100% 需 Key，现在全部有 tavily 兜底。该配置动作的价值此前被低估。
2. **newsapi 实质非必配**——引用它的 8 个 Skill 每一个都有 A 组源或 tavily 伴随（appeals→tavily+china-nbs、kpi-tree→china-nbs、pestel→5 个 A 组源、porters→world-bank+eurostat、swot/value-curve/change-management→tavily、competitor→5 源伴随）。
3. **EPO OPS 是专利域唯一现实主源**——注册对中国开放（国家下拉含 China，免费 OAuth2）、ops.epo.org 欧洲节点大陆一般可直连、数据覆盖 100+ 专利局含 CN 含 US（一源覆盖三库语义域）。google-patents 为最差组合：GCP 注册最难 + bigquery.googleapis.com 确定性封锁（配齐凭据连接层仍 411）。
4. **结构性战略错配**——产品面向中国企业高管，但 12 源中中文源仅 china-nbs 一个；看竞争对手的中国上市公司走 sec-edgar 查不到（预筛实测通的巨潮 cninfo 免 Key 却未立项）。
5. **两个机制性缺口**——①comtrade 注册表无条件注册但零 Skill 引用（4-1f「受益 Skill 声明重分配」遗漏面）；②vrio SKILL.md:205「Key 敏感降级」话术与机制落差：全败场景实际硬失败 503，无执行前预检。
6. **tavily 单点集中风险**——10/16 Skill 依赖，配额与可达性风险未登记。

## 四、3-body 三项裁定

| # | 议题 | 裁定 |
|---|------|------|
| 1 | 专利域三源取舍 | **维持三源计划不变**（不收缩为 EPO OPS 单源；Key 申请行政动作照做，代码层 B/C 组条件注册设计天然支撑——Key 未到位即休眠零代码成本；google-patents 大陆部署需代理/专线前置，显式标注于外部前置） |
| 2 | 中文源扩展 | **Epic 6 前立项 cninfo 巨潮资讯**（预筛 Phase 2 首项提前——A 组范式免 Key，中国上市公司财报公告，competitor-analysis 看竞争子步骤主源） |
| 3 | 机制缺口 | **两项都修**——comtrade 补 Skill 声明联动 + fetch_many 前置「声明源 ∩ 已注册适配器」预检门（交集空 → 数据缺口报告而非 503） |

## 五、后续 Epic 支撑度裁定（核心结论）

> **Epic 5 不受数据源影响，可直接启动**——Agent 协作/评估零外部数据源依赖（SkillSelector 为 L1 元数据匹配；Phoenix 评估用固定数据），与 2026-10-12 回顾结论一致，本次从数据源视角二次确认。
>
> **Epic 6 可启动**——市场洞察六子步骤在当前源池（A 组 7 源 + tavily）下全部可跑通：看趋势=pestel（5/6 源可用）、看市场与客户=appeals（2/3）、看竞争=competitor（4/7）+五力（2/3）、看自己=swot（tavily✅）、看机会=vrio/disruptive（tavily 兜底降级）。专利维度以降级模式运行（None 注入 + 数据缺口标注），属覆盖面缩减而非阻塞；cninfo 立项交付后中文竞争分析进一步闭环。
>
> **能力边界声明**——①IDC/Gartner/Euromonitor 独家份额数据不可得（合同与技术双重壁垒，预筛已证）；②中国专利无免费公开 API（CNIPA WAF 全拦截、ipdps 人工申请）——专利域大陆部署可得上限为 EPO OPS（含 CN 数据）+ 需代理的 uspto/google-patents；商业采购（智慧芽/incoPat）为远期选项；③google-patents 在大陆部署环境依赖代理/专线，否则连接层恒 411。

## 六、行动项

### 6.1 数据源供给

| # | 行动项 | Owner | 优先级 | 成功标准 |
|---|--------|-------|--------|---------|
| 1 | 三源 Key 申请异步启动：**EPO OPS 优先**（developers.epo.org 免费注册、对中国开放、大陆可直连）→ uspto PatentsView → GCP 服务账号（google-patents 外部前置显式标注：大陆部署需代理/专线） | 3-body | 🟡 P1 | 三源 env 门可开启；申请不阻塞任何 Story |
| 2 | **cninfo 巨潮资讯接入立项**（Epic 6 前置）——A 组范式免 Key 接入 + competitor-analysis 看竞争主源联动 + 断言联动清单 | Winston 立项 → Amelia create-story | 🔴 P0 | Story 文件创建（预筛 Phase 2 首项），Epic 6 Story 6.2 前交付 |

### 6.2 机制修正

| # | 行动项 | Owner | 优先级 | 成功标准 |
|---|--------|-------|--------|---------|
| 3 | **comtrade Skill 声明联动**——ansoff-matrix / space-matrix 等行业量化 Skill 补声明（4-1f 验收遗漏面清偿，四方联动断言同步） | Amelia | 🟡 P1 | comtrade 引用数 >0，契约/架构断言绿 |
| 4 | **执行前预检门**——`fetch_many` 前置「声明源 ∩ 已注册适配器」判定：交集空 → 输出数据缺口报告（标注休眠源 + 激活条件），消除 503 硬失败；同步修正 vrio SKILL.md:205 话术落差 | Charlie | 🟡 P1 | 零 Key 场景专利域 Skill 输出缺口报告而非 503 |
| 5 | **sec-edgar UA 真实调用验证**——A 组唯一未真实验证源（「mock 全绿 ≠ 真实可用」在数据源域的清偿） | Dana | 🟡 P1 | 真实调用 200 留证 |
| 6 | **tavily 单点依赖风险登记**——10/16 Skill 依赖，配额/可达性风险显式化 + 触发条件时间线 | Winston | 🟢 P2 | deferred-work.md 登记完成 |

### 6.3 团队协议

- **数据源 Key 类外部前置一律「申请先行、等待不阻塞」**（4-1f 先例——EDGAR 全部工作不等 Key）
- **新源接入默认追求 A 组形态**——优先寻找免 Key 官方通道/preview 兜底（Comtrade D5 先例），Key 仅作配额增强
- **每 Skill 至少一个 A 组源伴随**——新增 Skill 声明审查项，避免「全 B/C 组源」的零 Key 坍塌面重现

## 七、对 2026-10-12 标准回顾差距清单的对账

| 差距（10-12 清单） | 本次状态 |
|---|---|
| #3 数据源门控可用性 P1 | ✅ **闭合**——全量取证 + 降级机制验证 + 支撑度裁定（本文档）；残余为行动项 #1（Key 申请）与 #5（sec-edgar 验证） |
| #2 数据源 Key/插件可用性核查清单（Dana） | ✅ 交付——本文档 §2.1 即核查终态（含 10-12 核查 + 本日增量） |
| #6 差距分析工具缺失 P1 | 未在本次范围（产品决策仍悬：归 CEO Agent 裸推理还是新增工具） |

---

**回顾会议结束**: 2026-10-13
**主持人**: Amelia (Developer)
**记录生成**: Claude Code
