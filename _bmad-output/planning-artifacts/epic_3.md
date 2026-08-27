## Epic 3: 智能检索与知识发现 ✅ 已完成

**目标：** 实现混合检索（Dense + Sparse + Graph）、分层检索、契约化摘要和高保真溯源。

**包含 FR：** SR-01, SR-02, SR-03, SR-04, SR-05, SR-06, SR-07, SR-08, CP-02, SA-02, SA-03

Epic 3 ✅ 已完成（2026-08-21 回顾），全部 14 个 Story Done，验收测试全覆盖。

**📦 价值组：智能检索与溯源**
> 用户可以检索文档并追溯至原始坐标点

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 3.1a | **Dense 语义检索** | 支持语义相似度检索（bge-m3 嵌入） | 依赖 Epic 1 Story 1.6（Qdrant） | **P0-1a（关键路径）** |
| Story 3.1b | **BM25 稀疏检索 + RRF 融合** | 支持关键词检索，与 Dense 检索融合 | 依赖 Story 3.1a | **P0-1b（关键路径）** |
| Story 3.2a | **LLM Client 基础设施** | 统一 LLM 调用端口（结构化输出 + 熔断 + 重试），供所有 LLM 相关 Story 复用 | 依赖 Story 1.17（UDMR 路由） | **P0-1c（公共基础设施）** |
| Story 3.2b | 实体抽取（LLM+ 规则混合） | 构建知识图谱的实体和关系 | 依赖 Story 3.1b + Story 3.2a | P0-2 |
| Story 3.3 | 战略领域词典库管理 | 实体抽取准确率持续提升 | 依赖 Story 3.2b | P1-3 |
| Story 3.4 | RRF 融合排序 | 综合多种检索信号提升相关性 | 依赖 Story 3.1b | P0-4 |
| Story 3.5 | 分层检索（L1-L4） | 支持自顶向下和自底向上的双向检索 | 依赖 Story 3.4 | P0-5 |
| Story 3.6 | 契约化结构化摘要生成 | 摘要质量可控且可验证 | 依赖 Story 3.5 | P1-6 |
| Story 3.7 | 检索相关性评估 | 防止基于不足数据生成幻觉内容 | 依赖 Story 3.6 | P1-7 |
| Story 3.8 | 高保真溯源（Bounding Box 级） | 从结论快速追溯至原始文档坐标点 | 依赖 Epic 2 Story 2.3 | **P0-8（关键路径）** |
| Story 3.9 | 语义缓存 | 减少重复检索和 LLM 调用，降低 Token 消耗 | 依赖 Story 3.1a | P1-9 |
| Story 3.10 | 战略档案库永久存储 | 形成企业长期记忆和知识积累 | 依赖 Epic 1 Story 1.5/1.7 | P1-10 |
| Story 3.11 | 事实有效期标签管理 | 支持时间轴演进的动态知识网络查询 | 依赖 Story 3.10 | P1-11 |
| Story 3.12 | 数据陈旧标记 | 提醒用户注意数据时效性 | 依赖 Story 3.11 | P1-12 |

**✅ 依赖关系验证：**
- Epic 3 依赖 Epic 1 的存储层（Story 1.6 Qdrant, Story 1.5 PostgreSQL, Story 1.7 MinIO）
- Epic 3 依赖 Epic 2 的版面信息保留（Story 2.3）用于 Bounding Box 溯源
- Epic 3 内部故事依赖均为**顺序依赖**（检索流水线）
- Epic 3 可独立交付价值（用户检索和溯源）
- 不依赖 Epic 4-8

**⚠️ 关键路径说明：**
- **Story 3.8（高保真溯源）依赖 Epic 2 Story 2.3（版面信息保留）**
- Story 3.8 是核心用户体验（30 秒溯源），必须优先执行

---

### Story 3.1a: Dense 语义检索

As a **分析师**,
I want **系统执行 Dense 语义检索（bge-m3 嵌入，余弦相似度）**,
So that **支持语义相似度检索，理解查询的深层含义**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] Dense 检索测试 - 验证 bge-m3 嵌入生成
   - [ ] 余弦相似度测试 - 验证相似度计算
   - [ ] Payload 过滤测试 - 验证元数据过滤

2. **性能要求**
   - [ ] 检索延迟 P95<200ms（初检）
   - [ ] 嵌入生成延迟 P95<50ms
   - [ ] 并发检索≥50

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_dense_retrieval.py` - 单元测试
   - [ ] `tests/integration/test_dense_retrieval_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 用户输入检索查询
**When** 系统执行 Dense 检索
**Then** 使用 bge-m3 生成查询嵌入（维度 1024），在 Qdrant 中执行余弦相似度检索
**And** 检索延迟 P95<200ms（初检）
**And** 支持 Payload 过滤（元数据过滤）

### Story 3.1b: BM25 稀疏检索 + RRF 融合

As a **分析师**,
I want **系统执行 BM25 稀疏检索并与 Dense 检索融合（RRF 算法）**,
So that **同时支持语义检索和关键词检索，综合提升相关性**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] BM25 检索测试 - 验证关键词检索
   - [ ] RRF 融合测试 - 验证 Reciprocal Rank Fusion 算法

2. **性能要求**
   - [ ] 检索延迟 P95<800ms（MVP，含 RRF 融合）
   - [ ] BM25 检索延迟 P95<100ms
   - [ ] RRF 融合延迟 P95<50ms
   - [ ] 并发检索≥50

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_bm25_rrf.py` - 单元测试
   - [ ] `tests/integration/test_bm25_rrf_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 用户输入检索查询
**When** 系统执行混合检索
**Then** BM25 检索与 Dense 检索（Story 3.1a）并行执行，双路召回
**And** 使用 RRF（Reciprocal Rank Fusion）融合两路结果
**And** 检索延迟 P95<800ms（MVP，含 RRF 融合）

### Story 3.2a: LLM Client 基础设施

As a **系统架构师**,
I want **系统具备统一 LLM Client 基础设施（端口 + 结构化输出 + 容错机制）**,
So that **所有需要 LLM 调用的 Story（实体抽取、摘要生成、Agent 推理）复用同一套可靠的基础设施**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] LLM Client 测试 - 验证结构化输出（instructor/JSON Mode）
   - [ ] 熔断器测试 - 验证 Closed→Open→HalfOpen 三态转换
   - [ ] 重试测试 - 验证指数退避重试（1s→2s→4s）
   - [ ] 结构化输出 Schema 验证测试

2. **性能要求**
   - [ ] LLM 调用超时控制 P95<30 秒
   - [ ] 熔断器切换延迟 P95<50ms

3. **覆盖率要求**
   - [ ] 领域层覆盖率≥90%
   - [ ] 基础设施层覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/domain/ports/test_llm_client_port.py` - 端口单元测试
   - [ ] `tests/unit/infrastructure/external_services/llm/test_llm_client.py` - LLM Client 单元测试
   - [ ] `tests/integration/test_integration_llm_client.py` - 集成测试

**实施指南:**
- 依赖 Story 1.17 UDMR 路由，目前已配置真实可用的 GLM 与 DEEPSEEK 云端大模型
- 容错模式参考：`EmbeddingAPIClient`（`embedding_api_client.py` + `circuit_breaker.py`）
- 结构化输出：`instructor`（Pydantic 验证 + 自动重试修复）
- LLM Client 通用化：httpx.AsyncClient + tenacity 指数退避重试

**Given** LLM API endpoint 已配置
**When** 调用 `LLMClientPort.structured_generate(prompt, schema, config)`
**Then** 返回经验证的 JSON 结构（Pydantic Schema 约束）
**And** 熔断器（连续 5 次失败断开 30 秒）+ 指数退避重试（3 次：1s→2s→4s）

---

### Story 3.2b: 实体抽取（LLM+ 规则混合）

As a **知识工程师**,
I want **系统抽取实体（LLM+ 规则混合策略），输出三元组**,
So that **构建知识图谱的实体和关系**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 实体抽取测试 - 验证 LLM+ 规则混合策略
   - [ ] 规则基测试 - 验证 AC 自动机/正则/依存句法
   - [ ] LLM 语义测试 - 验证 Few-Shot+CoT+Schema 约束（基于 Story 3.2a 的 `LLMClientPort`）
   - [ ] 冲突仲裁测试 - 验证规则权重 0.6/LLM 权重 0.4
   - [ ] L5 Neo4j 持久化测试 - 验证实体/关系 MERGE 写入

2. **性能要求**
   - [ ] 规则基抽取准确率≥80%
   - [ ] LLM 语义抽取召回率≥90%
   - [ ] 冲突仲裁准确率≥85%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_entity_extraction.py` - 单元测试
   - [ ] `tests/integration/test_entity_extraction_integration.py` - 集成测试

**实施指南:**
- 参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例
- LLM 调用通过 `LLMClientPort`（Story 3.2a 交付），不使用裸 httpx
- 规则引擎使用 pyahocorasick + re（领域层零外部服务依赖）
- L5 Neo4j 持久化复用现有 `L5GraphPort`

**Given** 文档解析完成
**When** 系统执行实体抽取
**Then** 规则基抽取（领域词典 AC 自动机、正则、依存句法）准确率≥80%
**And** LLM 语义抽取（Few-Shot+CoT+Schema 约束）高召回率，冲突仲裁器融合（规则权重 0.6/LLM 权重 0.4）
**And** 抽取结果通过 L5GraphPort 写入 Neo4j（MERGE 语义）

### Story 3.3: 战略领域词典库管理

As a **领域专家**,
I want **系统管理战略领域词典库，支持热更新与版本管理**,
So that **实体抽取准确率持续提升**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 词典管理测试 - 验证添加/修改/删除词条
   - [ ] 热更新测试 - 验证无需重启系统
   - [ ] 版本管理测试 - 验证回滚功能

2. **性能要求**
   - [ ] 词典热更新延迟 P95<100ms
   - [ ] 版本回滚延迟 P95<200ms
   - [ ] 核心战略概念覆盖率≥95%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_domain_dictionary.py` - 单元测试
   - [ ] `tests/integration/test_domain_dictionary_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 战略领域词典已初始化
**When** 添加新词或修改现有词条
**Then** 词典热更新（无需重启系统），版本管理支持回滚
**And** 核心战略概念覆盖率≥95%

### Story 3.4: RRF 融合排序

As a **搜索工程师**,
I want **系统融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序**,
So that **综合多种检索信号提升相关性**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] RRF 融合测试 - 验证三路结果融合
   - [ ] ColBERT 重排序测试 - 验证 Top-K 精排
   - [ ] 权重配置测试 - 验证可配置权重

2. **性能要求**
   - [ ] RRF 融合延迟 P95<50ms
   - [ ] ColBERT 重排序延迟 P95<200ms
   - [ ] 并发检索≥50

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_rrf_fusion.py` - 单元测试
   - [ ] `tests/integration/test_rrf_fusion_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 三路检索结果已获取
**When** 执行 RRF 融合排序
**Then** 可配置权重的 RRF 算法融合三路结果
**And** 集成 ColBERT-v2 重排序器对 Top-K 候选精排

### Story 3.5: 分层检索（L1-L4）

> **命名说明：** 此处 L1-L4 为检索粒度级别（Retrieval Granularity），区别于存储层级别 L0-L5（L0 文件系统→L1 Redis→L2 PostgreSQL→L3 Qdrant→L4 MinIO→L5 Neo4j）。

As a **系统架构师**,
I want **系统执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）**,
So that **支持自顶向下和自底向上的双向检索**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 分层检索测试 - 验证 L1-L4 四级索引
   - [ ] 自顶向下测试 - 验证 L1→L4 遍历
   - [ ] 自底向上测试 - 验证 L4→L1 遍历
   - [ ] Parent-Child 层级测试 - 验证层级关系

2. **性能要求**
   - [ ] 初检延迟 P95<200ms
   - [ ] 精排延迟 P95<250ms
   - [ ] 融合延迟 P95<50ms
   - [ ] 并发检索≥50

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_layered_retrieval.py` - 单元测试
   - [ ] `tests/integration/test_layered_retrieval_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 四级分层索引已构建（Parent-Child 层级）
**When** 执行分层检索
**Then** 支持"自顶向下"（L1→L4）和"自底向上"（L4→L1）双向遍历
**And** 延迟预算分级约束（初检 200ms + 精排 250ms + 融合 50ms）

### Story 3.6: 契约化结构化摘要生成

As a **分析师**,
I want **系统生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema**,
So that **摘要质量可控且可验证**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 摘要生成测试 - 验证 LLM 生成摘要
   - [ ] JSON Schema 测试 - 验证 Pydantic V2 Schema 验证
   - [ ] 多视角测试 - 验证财务/市场/技术视角

2. **性能要求**
   - [ ] 摘要生成延迟 P95<30 秒
   - [ ] Schema 验证通过率 100%
   - [ ] 摘要质量评分≥8/10

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_contract_summary.py` - 单元测试
   - [ ] `tests/integration/test_contract_summary_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 检索结果已获取
**When** 调用 LLM 生成摘要
**Then** 输出强制遵守预定义的 JSON Schema 契约（财务/市场/技术视角）
**And** 通过 Pydantic V2 Schema 验证

### Story 3.7: 检索相关性评估（LLM-as-a-Judge）

As a **质量工程师**,
I want **系统评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性<0.6 标注"数据不足"**,
So that **防止基于不足数据生成幻觉内容**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 相关性评估测试 - 验证 LLM-as-a-Judge 多维评估
   - [ ] 阻断测试 - 验证相关性<0.6 标注"数据不足"
   - [ ] 多维评估测试 - 验证相关性/完整性/时效性

2. **性能要求**
   - [ ] 相关性评估延迟 P95<3s（含 LLM-as-Judge 评估，规则预检 P95<100ms）
   - [ ] 评估准确率≥90%
   - [ ] 阻断准确率 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_relevance_evaluation.py` - 单元测试
   - [ ] `tests/integration/test_relevance_evaluation_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 检索结果已获取
**When** 执行相关性评估
**Then** LLM-as-a-Judge 多维评估（相关性、完整性、时效性）
**And** 相关性<0.6 标注"数据不足"，阻断直接生成

### Story 3.8: 高保真溯源（Bounding Box 级）

As a **企业战略人员**,
I want **系统保留引文"三元组"特征（文档 ID、切片 ID、字符范围），支持 Bounding Box 级溯源**,
So that **从结论快速追溯至原始文档坐标点**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 溯源测试 - 验证引文"三元组"特征
   - [ ] Bounding Box 测试 - 验证 PDF 坐标点定位
   - [ ] 溯源卡片测试 - 验证文档 ID/页码/置信度显示

2. **性能要求**
   - [ ] 溯源响应<300ms
   - [ ] 定位准确率≥95%
   - [ ] 并发溯源≥50

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_traceability.py` - 单元测试
   - [ ] `tests/integration/test_traceability_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 检索结果包含引文信息
**When** 用户点击结论文字
**Then** 弹出溯源卡片，显示文档 ID、页码、置信度
**And** 点击"跳转"后自动定位至 PDF 坐标点（响应<300ms，准确率≥95%）

### Story 3.9: 语义缓存

As a **性能工程师**,
I want **系统执行语义缓存（相似度>0.9 直接返回缓存结果）**,
So that **减少重复检索和 LLM 调用，降低 Token 消耗**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 语义缓存测试 - 验证相似度>0.9 返回缓存
   - [ ] 缓存命中率测试 - 验证减少重复检索
   - [ ] TTL 测试 - 验证缓存失效策略

2. **性能要求**
   - [ ] 缓存命中延迟 P95<50ms
   - [ ] 缓存命中率≥40%
   - [ ] Token 消耗降低 40-50%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_semantic_cache.py` - 单元测试
   - [ ] `tests/integration/test_semantic_cache_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 查询已执行过
**When** 新查询与历史查询相似度>0.9
**Then** 直接返回缓存结果，不执行检索和 LLM 调用
**And** 缓存失效策略（TTL 24h + 事件驱动失效 + 版本感知失效）

### Story 3.10: 战略档案库永久存储

As a **知识管理专家**,
I want **系统永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差**,
So that **形成企业长期记忆和知识积累**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 档案存储测试 - 验证关键假设变量/决策依据/执行偏差存储
   - [ ] 永久存储测试 - 验证向量存储 + 对象存储协同
   - [ ] 归档测试 - 验证 SP/BP 规划完成归档

2. **性能要求**
   - [ ] 归档延迟 P95<500ms
   - [ ] 存储完整性 100%
   - [ ] 查询延迟 P95<200ms

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_strategic_archive.py` - 单元测试
   - [ ] `tests/integration/test_strategic_archive_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** SP/BP 规划完成
**When** 归档至战略档案库
**Then** 关键假设变量、决策依据、实际执行偏差永久存储
**And** 向量存储 + 对象存储协同架构

### Story 3.11: 事实有效期标签管理

As a **分析师**,
I want **系统管理事实有效期标签（valid_from/valid_until）**,
So that **支持时间轴演进的动态知识网络查询**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 有效期标签测试 - 验证 valid_from/valid_until 管理
   - [ ] 时间轴查询测试 - 验证按时间范围查询
   - [ ] 数据陈旧测试 - 验证超 12 个月自动标记

2. **性能要求**
   - [ ] 时间轴查询延迟 P95<200ms
   - [ ] 数据陈旧标记准确率 100%
   - [ ] 降权处理准确率 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_validity_period.py` - 单元测试
   - [ ] `tests/integration/test_validity_period_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 战略档案已存储
**When** 查询历史决策
**Then** 支持按时间范围查询，显示事实有效期标签
**And** 超 12 个月数据自动标记"数据陈旧"并降权

### Story 3.12: 数据陈旧标记

As a **合规工程师**,
I want **系统执行数据陈旧标记（超 12 个月自动降权）**,
So that **提醒用户注意数据时效性**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 数据陈旧测试 - 验证超 12 个月自动降权
   - [ ] 提示测试 - 验证生成结果中提示"数据陈旧"
   - [ ] 降权处理测试 - 验证排序分数降低

2. **性能要求**
   - [ ] 数据陈旧标记延迟 P95<100ms
   - [ ] 降权处理准确率 100%
   - [ ] 提示准确率 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_data_staleness.py` - 单元测试
   - [ ] `tests/integration/test_data_staleness_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 引用数据已存储超 12 个月
**When** 检索或生成结果引用该数据
**Then** 强制在生成结果中提示"数据陈旧"
**And** 自动降权处理（排序分数降低）
