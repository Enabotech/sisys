# Story 4.1b: Skills 数据采集基础设施（DataSourcePort + 8 数据源适配器）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

> **⚠️ 命名澄清（重要）：** 本 Story 的 sprint-status key 为 `4-1b-skills-feat-enhancement`，对应 `epics_v1.0.md` 中的 **Story 4.1b「Skills 数据采集基础设施」**（commit `371eca5a` 明确：sprint-status 的 4-1b 条目即"8 个数据源 + UNSD/OECD 推迟"的数据采集基础设施 Story；key 名 `skills-feat-enhancement` 为 Skills 系列增强故事的概括性 slug）。Story 4-4 文档中的修正注释（"4-1b 是 skills-feat-enhancement，4-1c 才是数据采集集成"）仅指 key 名层面，不改变本 Story 内容 = 数据采集基础设施这一事实。三方权威源（epics_v1.0.md Story 4.1b 定义 / sprint-status.yaml key / commit 371eca5a）已对齐。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** Skills 系统具备完整的数据采集基础设施（DataSourcePort + 8 个真实数据源适配器 + Redis 缓存 + Engine.Execute 阶段 `$DATA_SOURCE` 标记解析）,
**So that** 后续 Skills 完善 Story（4.1c/4.1d/4.1e）可复用统一的数据采集通道，Agent 调用外部数据型 Skills 时自动从权威数据源获取高质量、可靠、新鲜的数据，无需各自实现外部 API 集成。

### 业务价值

Story 4.1a 已完成 Skills 系统骨架（23 个 Skill 元数据 + L1/L2/L3 三级渐进式加载），Story 4.4 已完成 Docker 沙箱执行（`network_mode="none"` 写死为领域不变量）。**沙箱无网络**意味着 Skills 沙箱代码无法自行访问外部数据 API——数据采集必须在宿主机侧完成并注入沙箱执行上下文。本 Story 提供这一公共底座：

1. **统一端口抽象**：`DataSourcePort`（domain 层纯 Protocol）+ `DataSourceRef`/`DataSourceQuery`/`DataSourceResult`/`DataFreshness` 值对象，8 个适配器可插拔
2. **8 个真实数据源适配器**：World Bank / IMF / Tavily / USPTO / IPCC / NewsAPI / Eurostat / 中国国家统计局（复用 crawler 插件），PoC v1/v2 已验证选型
3. **数据缓存与新鲜度**：复用 `L1CachePort`（Redis）按 `ttl_seconds` 自动失效 + 指数衰减新鲜度评分
4. **引擎集成**：`ToolExecutionEngine` Execute 阶段识别 `$DATA_SOURCE(name, query)` 标记 → 白名单校验 → 并发采集 → 数据注入沙箱代码 → 输出含 source/freshness/confidence 溯源元数据

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1b（P0-5 数据采集基础）
**前置依赖:** Story 4.1a（✅ done，Skills 骨架 + ToolExecutionEngine 五阶段）/ Story 4.4（✅ done，Docker 沙箱 network_mode=none）/ Story 1.4（✅ done，Redis L1 缓存）
**后续依赖:** Story 4.1c（6 个外部数据型 Skills 复用本 Story 基础设施）/ Story 4.1d（10 个混合数据型 Skills）/ Story 4.1e（7 个内部框架 Skills）

### ⚠️ Story 范围澄清（重要）

**本 Story 交付（范围边界）：**

- `DataSourcePort` 端口契约 + 值对象 + 8 个适配器实现 + 端口注册
- 数据缓存（复用 `L1CachePort`，不新建缓存端口）+ 新鲜度评分
- `DataSourceResolverPort`/`DataSourceResolverService`（application 层编排：白名单 + 缓存 + 并发 + 新鲜度）
- `$DATA_SOURCE` 标记解析器 + `ToolExecutionEngine` Execute 阶段集成（宿主机侧采集 + 代码内联注入）
- `ToolMetadata.data_sources` 字段扩展（向后兼容，默认空 tuple）
- 4 个新领域异常（data_source 子域 410-419 新编码段）+ `DataSourceFetched`/`DataSourceFetchFailed` 领域事件双通道
- 端口契约测试 + 适配器单元测试 + 集成测试 + 架构验证测试 + BDD 验收测试

**不在本 Story 范围（拆分到其他 Story）：**

- **23 个 Skills 的 data_sources.yaml / SOP 编写**（每个 Skill 的数据源声明与工作坊方法论）→ Story 4.1c/4.1d/4.1e
- **SKILL.md frontmatter 的 data_sources 声明填充** → Story 4.1c 起逐 Skill 完善（本 Story 仅扩展 `ToolMetadata` 字段与解析能力）
- **UNSD / OECD 数据源** → PoC v2 验证不可用（UNSD HTTP 500 / OECD data 端点 404），推迟到后续 Story 重新验证
- **Reuters Connect** → 已排除（年费数千美元），由 NewsAPI 替代
- **多源三角化验证（≥3 独立来源）** → Story 4.1c 集成测试范畴
- **数据源治理（配额管理/成本追踪/降级策略）** → 后续 Story
- **白名单网关代理** → Story 4.4 已明确不做（沙箱 network_mode 写死 none），本 Story 数据采集在宿主机侧完成，天然规避

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

### 领域零依赖（FR-AR-01）

- `src/domain/ports/data_source.py`、`src/domain/value_objects/data_source.py`、`src/domain/exceptions/data_source_exceptions.py`、`src/domain/events/data_source_events.py` **仅允许 Python 标准库**（typing/dataclasses/enum/datetime/uuid/abc）
- **禁止** 导入 pydantic/httpx/redis/tenacity 等任何第三方包（`.importlinter` `domain-no-external-dependencies` 契约强制，CI 失败）
- `DataSourcePort` 必须为 `@runtime_checkable Protocol`

### 异常体系强制

- **禁止** `raise ValueError` / 手动 `raise HTTPException` / 继承内置 Exception
- 所有异常走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前执行三条 grep 自查（零输出）：
  - `grep -rn "raise ValueError" src/`
  - `grep -rn "raise HTTPException" src/`
  - `grep -rn "class.*Exception)" src/domain/exceptions/ | grep -v "DomainError\|BaseException\|SystemException\|BusinessException\|ExternalException\|ThirdPartyError\|Error)"`

### 新增异常完整性 Checklist（5 项强制，对齐 Story 4.4）

1. **定义文件**：`src/domain/exceptions/data_source_exceptions.py`（Google 风格全中文注释）
2. **子域映射**：`_code_ranges.py` 新增 `data_source: (410, 419)` 子域 + `_CLASS_TO_SUBDOMAIN` 注册 4 个新异常类
3. **包导出**：`src/domain/exceptions/__init__.py` 导入 + `__all__` 暴露
4. **子域码段校验**：运行 `tests/unit/domain/exceptions/test_code_ranges.py` 与 `test_error_code_uniqueness.py` 全绿（CLAUDE.md §5 强制 4 项之一）
5. **HTTP 映射注册**：`src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 注册 4 项映射（4-4 实战新增的第 5 项，对齐 Story 4.4 line 99）
6. **设计文档同步**：更新 `docs/architecture/sisys-uni-exception-design.md` §3.3.2 编码分配表（独立项，不与 Checklist 并列；CLAUDE.md §5 异常体系硬约束）

> **编码段决策（Task 0 验证）：** external 子域（301-399）已满（304/305/384 零散空位不足以成段，399 预留 Story 4.7），新增 `data_source: (410, 419)` 子域段（"只追加"原则允许新增段）。`DataSourceError` 直接继承 `ExternalException`（抽象基类占位码 EXCEPTION_3XX，`test_subclass_code_in_same_subdomain_as_parent` 对**抽象基类父类跳过校验**——`test_code_ranges.py:119` `abstract_names = {"DomainError", "BaseException", "SystemException", "BusinessException", "ExternalException"}` + line 185 `if parent_name in abstract_names: continue`），无需在 `allowed_child_parent_subdomains` 注册。`docs/architecture/architecture.md §17.3.1`（line 2720/2740）预留的 skill 子域 42x 段（EXCEPTION_422/423）不受影响（数值为 `[422, 423]`，与 data_source `[410, 419]` 不重叠）。Task 0 必须运行 `grep -rn "EXCEPTION_41[0-9]" src/` 确认零碰撞。

### 抑制告警禁止

- **禁止** `# noqa` / `# type: ignore` / `# pylint: disable`；**禁止**修改阈值/规则消除告警——必须修复根因
- 第三方库缺类型注解时在 `stubs/<package>/__init__.pyi` 创建 PEP 561 存根

### Commit & Push 规范

- 提交信息**禁止**任何 AI 辅助署名（Co-Authored-By: Claude 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- 直接在 main 分支开发（项目约定）

### 数据源安全约束

- **沙箱无网络不变量**：`ContainerSpec.network_mode == "none"` 是领域不变量（`src/domain/value_objects/container_spec.py:45`），**禁止**为数据采集打开沙箱网络——所有外部数据必须在宿主机侧采集后注入
- **API Key 安全**：Tavily/NewsAPI 密钥仅经环境变量注入（`TAVILY_API_KEY`/`NEWSAPI_API_KEY`），禁止硬编码、禁止写入日志/异常消息/`to_dict()` 输出；配置类 `__repr__` 必须脱敏（参考 `RedisConfig.__repr__` 脱敏先例 `src/infrastructure/config/redis.py:40-48`）
- **白名单强制**：Engine 仅允许调用当前 Tool 的 `ToolMetadata.data_sources` 中声明的数据源，违规复用 `BusinessRuleViolationError`（EXCEPTION_207）
- **crawler 合规**：中国国家统计局适配器必须经 `CrawlerClientPort` 复用 crawler 插件（robots.txt 遵守 + UA 轮换 + 域名限速），禁止在适配器内直接 httpx 抓取国家局站点（PoC v2 已验证直连 HTTP 403 反爬拒绝）

### 代码质量门禁

- `poetry run ruff check src/ tests/` 通过（行宽 128，规则 E/F/I/N/W）
- `poetry run mypy src/` 通过
- `poetry run pytest tests/ -n 8` 并行通过，连续 5 次无随机失败
- `pre-commit run --all-files` 通过

---

## 🎯 领域异常契约

> **原则**：异常是领域契约的一部分。本 Story 新增异常必须在 Task 0 完成设计，禁止在实现 Task 中临时定义。

### 已存在异常复用（禁止重复定义同义异常）

| 场景 | 复用异常 | 编码 | 依据 |
|------|---------|------|------|
| 数据源请求超时 | `TimeoutError`（external） | EXCEPTION_302 | 全项目超时统一映射先例（embedding/llm 适配器） |
| 数据源配置错误（缺 API Key/URL） | `ConfigurationError`（system） | EXCEPTION_101 | 配置参数验证标准异常 |
| 白名单违规（Tool 未声明该数据源） | `BusinessRuleViolationError` | EXCEPTION_207 | 跨字段业务约束/策略违规标准异常 |
| 标记解析失败（`$DATA_SOURCE` 语法错误） | `ValidationError`（business） | EXCEPTION_201 | 应用层输入校验标准异常 |
| 缓存服务不可用 | `ServiceUnavailableError` | EXCEPTION_303 | 熔断/服务降级标准异常 |

### 新增异常（Task 0 定义，data_source 子域 410-419）

| 异常类 | 编码 | 父类 | HTTP | 触发场景 |
|--------|------|------|------|---------|
| `DataSourceError` | EXCEPTION_410 | `ExternalException` | 502 | 数据源通用错误基类（具体异常兜底） |
| `DataSourceUnavailableError` | EXCEPTION_411 | `DataSourceError` | 503 | 数据源 5xx/连接失败/熔断断开（重试耗尽后） |
| `DataSourceRateLimitError` | EXCEPTION_412 | `DataSourceError` | 429 | 数据源 429 限流（NewsAPI 免费 100 次/天等） |
| `DataSourceResponseError` | EXCEPTION_413 | `DataSourceError` | 502 | 响应解析失败/required_fields 缺失/schema 不符（**不可重试**） |

**构造器参数设计**：携带 `context` 字典暴露领域上下文（`source_name`、`url`（脱敏，不含 query 中的 key）、`query`），消息面向调用方可理解，不泄露 HTTP 堆栈/API Key。

### 登记确认动作（Task 0 必做）

- [ ] `grep -rn "EXCEPTION_41[0-9]" src/` 零碰撞验证
- [ ] `_code_ranges.py`：`CODE_RANGES["data_source"] = (410, 419)` + `_CLASS_TO_SUBDOMAIN` 4 项注册 + 注释清单
- [ ] `sisys-uni-exception-design.md` §3.3.2 编码分配表追加 4 行
- [ ] `EXCEPTION_HTTP_MAP` 注册 4 项映射
- [ ] 异常测试通过：`tests/unit/domain/exceptions/test_data_source_exceptions.py`（构造/to_dict()/HTTP 映射）+ `test_error_code_uniqueness.py` + `test_code_ranges.py` + `tests/unit/interfaces/api/test_exception_handlers.py`

---

## 🎯 测试隔离约束

### TestTenant UUID 前缀

- 数据缓存键必须带租户前缀：`build_key("cache:datasource", tenant_prefix, source_name, query_hash)`，测试使用 `test_tenant` fixture（`tests/fixtures.py:49`）+ `TestTenant.redis_key_prefix`（`tests/isolation.py:52`）
- 每个测试只清理自己创建的缓存键（`delete_pattern` 限定租户前缀），禁止全库 flush

### 外部服务测试策略

- **单元测试**：`httpx.MockTransport` 注入模式（**仅 crawler 测试使用此模式**，范本 `tests/unit/infrastructure/crawler/test_http_crawler_client.py:44-62`）；embedding/llm 测试使用 `unittest.mock.patch()` + `MagicMock`（范本 `tests/unit/infrastructure/external_services/embedding/test_embedding_api_client.py`）；禁止真实外网调用
- **集成测试**：本地 aiohttp 真实 HTTP 服务器模拟外部 API（范本 `tests/integration/test_integration_llm_client.py`——不 mock 客户端本身，验证完整 HTTP 链路）；真实 Redis 用测试端口 + 租户前缀
- **中国国家统计局集成测试**：crawler 服务不可用时 `pytest.skip()` 动态跳过（**禁止** `@pytest.mark.skip` 写死），范本 `tests/integration/conftest.py:215` 系列 skip 模式
- **真实外网探活测试**（可选 smoke）：动态 skip，不进 CI 默认门禁

### BDD 步骤函数

- **禁止** `@pytest.mark.asyncio`（导致 context 数据丢失），使用 `loop = asyncio.new_event_loop()` + `loop.run_until_complete()` helper（范本 `tests/acceptance/test_acceptance_docker_sandbox.py:44-46`）
- 同一中文文本可能需同时支持 given/when 装饰器

### 并发与事件循环

- `asyncio.Lock` 必须声明为**类变量**（非实例变量）
- pytest-xdist 默认开启（`-n auto --dist loadgroup`），涉及共享外部资源的测试用 `xdist_group` 分组串行
- 缓存并发测试在 async 函数内用 `asyncio.gather()`，不用 `asyncio.run()`

### 真实服务优先

- 集成/验收测试：Redis 用真实实例（测试端口），领域服务/应用服务用真实实例
- Mock 仅限：外部 HTTP 数据源（MockTransport/本地服务器）、LLM 客户端（AsyncMock(spec=LLMClientPort)）、沙箱（按 4-1a 验收测试先例 AsyncMock）

---

## 🌐 端口与数据契约

### 领域端口：DataSourcePort（新增）

**路径**：`src/domain/ports/data_source.py`

```python
@runtime_checkable
class DataSourcePort(Protocol):
    """数据源端口（R1 领域层统一抽象）——单一外部数据源的获取契约。"""

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按查询获取数据。失败抛 data_source 子域异常（不重试语义由适配器内 tenacity 收敛）。"""

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（name/url/ttl_seconds/required_fields/api_type）。"""

    async def health_check(self) -> bool:
        """探活（轻量端点/缓存最近一次成功状态），不消耗配额或最小消耗。"""
```

### 值对象（新增）

**路径**：`src/domain/value_objects/data_source.py`（全部 `@dataclass(frozen=True)`，零外部依赖）

| 值对象 | 关键字段 | 不变量 |
|--------|---------|--------|
| `DataSourceRef` | `name: str` / `url: str` / `ttl_seconds: int = 86400` / `required_fields: tuple[str, ...] = ()` / `api_type: DataSourceApiType` | name 非空且 kebab-case；ttl_seconds ∈ [60, 2592000]（参考 `src/infrastructure/storage/redis/redis_snapshot_store.py:98` 运行时强制校验先例，`checkpoint_snapshot.py:28` docstring 注释范围 [86400, 2592000]）；url 必须 http(s) |
| `DataSourceApiType` | StrEnum：`REST_JSON` / `SDMX_JSON` / `CSV_DOWNLOAD` / `CRAWLER` | — |
| `DataSourceQuery`（Query Object，定义在端口文件） | `source_name: str` / `query: str` / `parameters: tuple[tuple[str, str], ...] = ()` / `tenant_id: UUID \| None = None` | query 非空；source_name 非空 |
| `DataSourceResult` | `source_name` / `payload: str`（JSON 字符串）/ `source_timestamp: datetime` / `fetched_at: datetime` / `freshness: DataFreshness` / `confidence: float` / `cache_hit: bool = False` | confidence ∈ [0,1]（参考 `EvidencePackage.validate_complete()` 校验先例 `src/domain/value_objects/tool_execution.py:178-182`）；payload 非空 |
| `DataFreshness` | `source_timestamp: datetime` / `ttl_seconds: int` / `half_life_seconds: int = 604800`（**新增字段，参考业界指数衰减惯例：Prometheus staleness / Facebook TAO stale-while-revalidate / CDN stale-while-revalidate 协议；7 天半衰期适配 World Bank/IMF 年度数据场景**） | `score(at: datetime) -> float` 指数衰减 ∈ [0,1]；`is_stale(at) -> bool`（age > ttl_seconds） |

### ToolMetadata 字段扩展（向后兼容）

**路径**：`src/application/ports/skill_loader.py`（ToolMetadata 第 50-67 行现有 17 字段）

- 新增 `data_sources: tuple[DataSourceRef, ...] = ()`，**必须带默认值**（frozen dataclass 向后兼容先例，该文件注释行 14-16 既定惯例）
- SKILL.md frontmatter 解析器同步支持可选 `data_sources` 键（本 Story 仅打通解析链路，23 个 SKILL.md 的声明填充属 4.1c/4.1d/4.1e）

### 应用层端口：DataSourceResolverPort（新增，R2 组合注入）

**路径**：`src/application/ports/data_source_resolver.py`

```python
class DataSourceResolverPort(Protocol):
    """数据源解析编排端口——组合 DataSourcePort 集合 + L1CachePort，提供白名单/缓存/新鲜度/并发能力。"""

    async def fetch(self, tool_metadata: ToolMetadata, name: str, query: str) -> DataSourceResult:
        """白名单校验（name ∈ tool_metadata.data_sources）→ 缓存命中返回 → 适配器采集 → 写缓存 → 新鲜度评分。"""

    async def fetch_many(self, tool_metadata: ToolMetadata, requests: tuple[DataSourceQuery, ...]) -> tuple[DataSourceResult, ...]:
        """并发采集（asyncio.gather + return_exceptions 收敛为部分成功），单个失败不阻断其他源。"""
```

实现：`src/application/services/data_source_resolver.py` `DataSourceResolverService`，构造注入 `adapters: Mapping[str, DataSourcePort]`（composition_root 按 `data_source_*` 端口聚合注入）+ `cache: L1CachePort` + `event_publisher: EventPublisher`。

### Engine.Execute 集成契约

> **集成方案决策（关键抉择）**：采用 **`set_resolver()` 后注入方法**（非 `__init__` 参数）以避免破坏 Story 4.4 AC-7.4 BDD 断言（`test_acceptance_docker_sandbox.feature:243-247` 显式断言 `ToolExecutionEngine.__init__` 参数数量 = 5，**未增加**）。此决策保证两 Story 同时合入 main 分支时不破坏 4.4 既有 BDD 测试。

- `ToolExecutionEngine.__init__` **签名保持不变**（与 Story 4.4 AC-7.4 BDD 一致）
- 新增可选 setter `set_data_source_resolver(resolver: DataSourceResolverPort | None) -> None`（None 时撤销注入,等同未注入）
- Engine 内部新增私有属性 `_data_source_resolver: DataSourceResolverPort | None = None`（默认 None，零行为变化）
- composition_root 调用顺序:`tool_execution_engine = ToolExecutionEngine(...)` → `tool_execution_engine.set_data_source_resolver(resolver.resolve_optional("data_source_resolver"))`（后注入模式）
- Execute 阶段前置处理（`_execute_stage`,`src/application/services/tool_execution_engine.py:267`）：当 `_data_source_resolver is not None` 时解析代码中 `$DATA_SOURCE(name, "query")` 标记 → `resolver.fetch_many` 并发采集 → 数据以 Python 字面量前言（preamble）形式内联注入代码（如 `DATA_SOURCES = {"world-bank": {...json...}}`）→ 沙箱执行注入后的代码；当 `_data_source_resolver is None` 时**直接跳过**前置处理,完全保持 4.4 既有行为
- 输出元数据：`EvidencePackage` 扩展可选字段 `data_sources: tuple[DataSourceMeta, ...] = ()`（`DataSourceMeta` 值对象：source_name/source_timestamp/freshness_score/confidence），支撑溯源

### 领域事件（新增，双通道）

**路径**：`src/domain/events/data_source_events.py`（继承 `DomainEvent`，参考 `tool_events.py:22` ToolExecuted 模式）

| 事件 | event_type | aggregate_type | payload 关键字段 | 通道 |
|------|-----------|----------------|-----------------|------|
| `DataSourceFetched` | `DataSourceFetched` | `ToolExecution` | execution_id（aggregate_id）/source_name/query/freshness_score/confidence/cache_hit/latency_ms | realtime（Redis）+ reliable（RabbitMQ+Outbox） |
| `DataSourceFetchFailed` | `DataSourceFetchFailed` | `ToolExecution` | execution_id（aggregate_id）/source_name/query/error_code/error_message | reliable 为主 |

**强制同步**：`configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS`（`src/infrastructure/messaging/channel_router.py:54`）两处同步新增（优先级 yaml > DEFAULT_MAPPINGS，`channel_router.py:50-53` 注释明示）。

### 契约测试文件清单

- `tests/contracts/test_port_contract_data_source.py`（11 维度模式，范本 `tests/contracts/test_port_contract_tool.py:18-242`：PORT_NAME/IMPL_CLS_NAME/MODULE_PATH/EXPECTED_TAGS/EXPECTED_OWNER/REQUIRED_METHODS + `_DummyResolver`）
- `tests/contracts/test_port_contract_data_source_resolver.py`（应用层端口契约）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: DataSourcePort 端口定义与值对象

**Given** Skills 数据采集需要统一的领域层端口抽象
**When** 在 `src/domain/ports/data_source.py` 定义 `DataSourcePort` Protocol 及配套值对象
**Then**
- `DataSourcePort` 为 `@runtime_checkable` Protocol，含 `fetch`/`get_metadata`/`health_check` 三方法，零外部依赖
- `DataSourceRef`（name/url/ttl_seconds/required_fields/api_type）+ `DataSourceQuery` + `DataSourceResult` + `DataFreshness` 值对象完备，不变量经领域异常校验
- `ToolMetadata.data_sources: tuple[DataSourceRef, ...] = ()` 扩展向后兼容（既有 23 个 SKILL.md 解析不受影响）
- 端口在 `composition_root.py` 注册（PortSpec 10 字段 dataclass：`name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated`；常用注册 8 字段含 `module`），契约测试 11 维度通过

**验证标准/Validation Criteria:**
- [ ] `DataSourcePort` runtime_checkable + 三方法签名契约测试通过
- [ ] 值对象不变量单元测试（非法 ttl/name/confidence 抛对应领域异常）
- [ ] ToolMetadata 扩展后既有 skill_loader 测试全绿（回归）
- [ ] domain 层零依赖架构测试通过

### AC-2: 8 个数据源适配器

**Given** PoC v1/v2 已完成数据源选型验证（Eurostat 完全可用；UNSD/OECD 推迟；国家局需 crawler 插件）
**When** 在 `src/infrastructure/external_services/datasources/` 实现 8 个适配器
**Then**
- `WorldBankAdapter`（REST_JSON，GDP/Governance Indicators，无 Key）
- `IMFAdapter`（SDMX_JSON，World Economic Outlook）
- `EurostatAdapter`（SDMX_JSON，欧盟 27 国 + EFTA）
- `USPTOAdapter`（REST_JSON，专利数据）
- `IPCCAdapter`（CSV_DOWNLOAD，环境数据）
- `NewsAPIAdapter`（REST_JSON + `NEWSAPI_API_KEY`，实时新闻流，免费 100 次/天）
- `TavilyAdapter`（REST_JSON + `TAVILY_API_KEY`，Web 搜索 + 新闻聚合）
- `ChinaNBSAdapter`（CRAWLER，复用 `CrawlerClientPort` 经 crawler 插件提交任务，禁止直连抓取）
- 每个适配器：httpx.AsyncClient + tenacity 重试（3 次指数退避，仅 5xx/超时/传输错误可重试，项目惯例 `retry_if_exception(_is_retryable_xxx_error)` 白名单函数模式 `src/infrastructure/external_services/embedding/embedding_api_client.py:51-66`）+ 复用自研 `CircuitBreaker`（`src/infrastructure/external_services/embedding/circuit_breaker.py:51`）+ 内联 except 链错误映射到 data_source 子域异常
- 配置走 dataclass + `from_env()` 模式（参考 `EmbeddingConfig.from_env()` `src/infrastructure/config/embedding.py:31`），API Key 脱敏；**关键安全约束**：Tavily 等 Key 在 URL query 的 API,**except 块必须显式剥除 URL query 中的 key 后再构造异常消息与 `context` 字典**(参考 `LLMConfig.__repr__` 脱敏 `src/infrastructure/config/llm_client.py:97-109`),否则 `cause=e` 异常链可能通过 `str(e)` / 日志 dump 泄露 URL 含 key;异常 `to_dict()` 输出断言零 Key 泄露
- 配置拆分：每端口独立配置文件(`worldbank.py` / `imf.py` / `eurostat.py` / `uspto.py` / `ipcc.py` / `newsapi.py` / `tavily.py` / `china_nbs.py`),对齐项目 11 个 config 文件单一职责惯例(参考 `src/infrastructure/config/embedding.py`/`redis.py`/`llm_client.py`),非单文件聚合

**验证标准/Validation Criteria:**
- [ ] 8 个适配器单元测试（httpx.MockTransport 注入模式，全项目唯一先例 `tests/unit/infrastructure/crawler/test_http_crawler_client.py:44-62`）覆盖：成功/超时/5xx 重试耗尽/429 限流/响应解析失败/熔断断开
- [ ] 异常映射断言：`DataSourceUnavailableError`(411)/`DataSourceRateLimitError`(412)/`DataSourceResponseError`(413)/`TimeoutError`(302)
- [ ] 8 个适配器全部注册到 composition_root（`data_source_<name>` 命名，SINGLETON 生命周期）
- [ ] 配置缺失（无 API Key）抛 `ConfigurationError`(101) 且消息不泄露密钥
- [ ] **CircuitBreaker 差异化配置**：8 个适配器按数据源故障特征差异显式定义熔断参数（`failure_threshold` / `recovery_timeout`）— WorldBank/Eurostat/USPTO 默认 `5/30s`；NewsAPI 早断开 `2/600s`（免费 100 次/天配额敏感）；IPCC 立即熔断 `2/120s`（大文件传输失败代价高）；ChinaNBS 放宽 `10/120s`（爬虫失败率天然高）；Tavily/IMF 默认 `5/30s`

### AC-3: 数据缓存层与新鲜度评分

**Given** 外部数据源有配额限制且数据有时效性
**When** `DataSourceResolverService` 采集数据
**Then**
- 复用 `L1CachePort`（Redis，禁止新建缓存端口），缓存键 `build_key("cache:datasource", tenant, source, query_hash)`，按 `DataSourceRef.ttl_seconds` 自动失效
- 缓存命中直接返回（`cache_hit=True`），不消耗外部配额
- 新鲜度评分：`DataFreshness.score()` 指数衰减 ∈ [0,1]，超过 ttl 标记 stale
- 缓存故障降级：Redis 不可用时直接透传采集（不阻断主流程），记录告警

**验证标准/Validation Criteria:**
- [ ] 缓存命中/失效/TTL 边界单元测试（fakeredis 或 Mock L1CachePort）
- [ ] 新鲜度评分单元测试（time-freeze 注入，衰减曲线边界）
- [ ] 缓存故障降级路径测试
- [ ] 租户隔离：不同租户同查询不共享缓存键

### AC-4: Engine.Execute 阶段 $DATA_SOURCE 增强

**Given** 沙箱 `network_mode="none"` 为领域不变量，沙箱代码无法访问外网
**When** LLM 生成的沙箱代码含 `$DATA_SOURCE(name, "query")` 标记
**Then**
- 标记解析器（`src/application/services/data_source_marker.py`）在宿主机侧提取全部标记，语法错误抛 `ValidationError`(201)
- 白名单校验：name 必须 ∈ 当前 Tool 的 `ToolMetadata.data_sources`，违规抛 `BusinessRuleViolationError`(207)
- 并发采集（asyncio.gather，单源失败收敛为部分成功 + `DataSourceFetchFailed` 事件）
- 数据以 Python 字面量 preamble 内联注入代码后送沙箱执行（禁止打开沙箱网络）
- 输出含 source/freshness/confidence 元数据（`EvidencePackage.data_sources` 扩展，向后兼容默认空 tuple）
- `data_source_resolver=None` 时引擎行为与现状完全一致（回归保护）
- 采集成功发布 `DataSourceFetched` 事件（双通道）

**验证标准/Validation Criteria:**
- [ ] 标记解析器单元测试（单标记/多标记/嵌套引号/语法错误/重复标记去重）
- [ ] 白名单违规测试（未声明数据源 → 207）
- [ ] 引擎集成测试：注入 resolver 后 Execute 阶段代码含注入 preamble；None 时零行为变化
- [ ] 部分失败收敛：1 源失败其余成功，失败事件发布
- [ ] EvidencePackage 扩展回归测试（既有构造不传新字段全绿）

### AC-5: 领域异常与事件契约

**Given** 异常是领域契约，新增异常必须完成 5 项完整性 Checklist
**When** 定义 data_source 子域 4 个新异常（410-413）+ 2 个领域事件
**Then**
- `data_source: (410, 419)` 子域段注册，4 个异常构造/to_dict()/HTTP 映射/编码唯一性/子域范围测试全绿
- `DataSourceFetched`/`DataSourceFetchFailed` 同步登记 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS`
- `sisys-uni-exception-design.md` §3.3.2 编码分配表同步

**验证标准/Validation Criteria:**
- [ ] `tests/unit/domain/exceptions/test_data_source_exceptions.py` 通过
- [ ] `test_error_code_uniqueness.py` + `test_code_ranges.py` 全绿（零碰撞）
- [ ] `tests/unit/interfaces/api/test_exception_handlers.py` HTTP 映射测试通过
- [ ] 事件双通道配置一致性测试通过

### AC-6: 集成测试（真实服务）

**Given** 适配器与引擎集成需要真实链路验证
**When** 运行集成测试
**Then**
- 本地 aiohttp HTTP 服务器模拟外部 API（不 mock 客户端本身），验证 httpx + tenacity + 熔断完整链路
- 真实 Redis（测试端口 + TestTenant 前缀）验证缓存命中/失效
- 中国国家统计局 crawler 集成测试：crawler 服务可达时真实提交任务验证，不可达时 `pytest.skip()` 动态跳过
- 引擎端到端：真实 Engine + 真实 Resolver + 真实 Redis + Mock LLM/Sandbox（按 4-1a 验收先例），验证 `$DATA_SOURCE` 全链路

**验证标准/Validation Criteria:**
- [ ] `tests/integration/application/test_data_source_execution.py` 通过
- [ ] `tests/integration/external_services/data_sources/test_china_nbs_crawler.py` 通过或动态 skip
- [ ] `pytest -n 8` 并行通过，连续 5 次无随机失败

### AC-7: SDD 架构验证测试

**Given** 新增端口/适配器/事件必须满足六边形架构约束
**When** 运行 `tests/unit/architecture/test_arch_data_source.py`
**Then**
- domain 层新文件零外部依赖（AST 黑名单扫描，范本 `test_arch_strategic_tool_impl.py`）
- 端口注册完整性（PortSpec 10 字段 dataclass + 8 适配器 + resolver 全注册）
- 实现类 isinstance Protocol 校验
- 依赖方向校验（application 不 import infrastructure，适配器仅经 composition_root 注册）

### AC-8: BDD 验收测试（Gherkin 中文）

**Given** Story 4.1a 已完成 Skills 系统骨架
**When** Skills 调用需要外部数据
**Then** Engine.Execute 阶段识别 `$DATA_SOURCE` 标记自动采集并注入，输出含 source/freshness/confidence 元数据支持溯源
**And** Edge Cases 覆盖：数据源不存在（白名单外）、数据源不可用（降级/部分失败）、缓存命中、限流 429

**验证标准/Validation Criteria:**
- [ ] `tests/acceptance/test_acceptance_data_source.feature`（`# language: zh-CN`，按 AC 分节）
- [ ] `tests/acceptance/test_acceptance_data_source.py`（scenarios() + context dict + new_event_loop + 真实服务 + AsyncMock 仅限 LLM/Sandbox/外部HTTP）
- [ ] 全部场景通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] `DataSourceFetched` / `DataSourceFetchFailed` 定义于 `src/domain/events/data_source_events.py`，继承 `DomainEvent`（`src/domain/events/base.py:42`）
- [ ] 使用标准库实现（dataclass），禁止领域层依赖 Pydantic
- [ ] 命名符合 `[Aggregate][EventName]` 过去式规范
- [ ] 同步登记 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS`

#### 数据模型 (Data Models)
- [ ] 值对象位于 `src/domain/value_objects/data_source.py`（DataSourceRef/DataSourceApiType/DataSourceResult/DataFreshness/DataSourceMeta）
- [ ] Query Object `DataSourceQuery` 定义在端口文件（DDD Query Object 模式：多字段组合查询）
- [ ] `ToolMetadata.data_sources` 扩展带默认值（向后兼容）
- [ ] `EvidencePackage.data_sources` 扩展带默认值（向后兼容）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] `DataSourcePort` 定义于 `src/domain/ports/data_source.py`（R1 领域层统一抽象）
- [ ] `DataSourceResolverPort` 定义于 `src/application/ports/data_source_resolver.py`（R2 组合注入）
- [ ] 所有端口经 `register_port()` 在 `src/composition_root.py` 统一注册，PortSpec 10 字段完备（name/version/interface/impl/module/lifetime=Lifetime.SINGLETON/owner/tags/deprecated）
- [ ] 8 适配器以 `data_source_<name>` 命名注册（worldbank/imf/eurostat/uspto/ipcc/newsapi/tavily/china-nbs）
- [ ] 禁止业务代码直接实例化适配器，仅经 `resolver.resolve()`
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_data_source.py` + `test_port_contract_data_source_resolver.py`）
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

#### 端口契约清单执行约束（强制）
- [ ] 本 Story「端口与数据契约」节是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry/resolver/contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)
- [ ] 见「🎯 领域异常契约」节：4 个新异常（410-413）+ 5 个复用异常，Task 0 完成设计与登记
- [ ] 编码零碰撞验证：`grep -rn "EXCEPTION_41[0-9]" src/`
- [ ] 编码注册：`_code_ranges.py` 新增 `data_source: (410, 419)` + `_CLASS_TO_SUBDOMAIN` 4 项
- [ ] 导出完整性：`__init__.py` + `__all__` + `EXCEPTION_HTTP_MAP`
- [ ] 测试覆盖：`test_data_source_exceptions.py` + `test_error_code_uniqueness.py` + `test_code_ranges.py` + `test_exception_handlers.py`
- [ ] 设计文档同步：`sisys-uni-exception-design.md` §3.3.2
- [ ] BDD 异常路径场景纳入 Edge Cases

#### API 契约 (API Contract)
- [ ] 本 Story 不新增 REST 端点（纯内部基础设施），无 openapi.yaml 变更
- [ ] 端口契约即 API 契约（见上节）

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 本 Story 交付物 |
|------|------|----------------|
| domain | `src/domain/` | DataSourcePort 端口、值对象、异常、事件（零外部依赖） |
| application | `src/application/` | DataSourceResolverPort/Service、标记解析器、Engine 增强、ToolMetadata 扩展 |
| infrastructure | `src/infrastructure/` | 8 个数据源适配器、配置类（httpx/tenacity/crawler 客户端） |
| interfaces | `src/interfaces/` | 仅 EXCEPTION_HTTP_MAP 映射注册（无新端点） |

**领域层零依赖原则**：仅 Python 标准库；禁止 httpx/pydantic/redis/tenacity 等（.importlinter 强制）

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_data_source.feature`（`# language: zh-CN`）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_data_source.py`
- [ ] Happy Path + Edge Cases 全覆盖（白名单外数据源/不可用降级/缓存命中/429 限流）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async（禁止 `@pytest.mark.asyncio`）
- 同一中文文本可能需要同时支持 given/when 装饰器
- Edge Cases 必须包含异常路径：白名单违规（207）、数据源不可用（411）、限流（412），断言 `error.code` + `error.message`

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 异常契约登记完成（5 项 Checklist）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试
- ❌ 将测试编写集中到最后一个 Task
- ❌ 跳过红阶段验证

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 领域值对象 | 不变量/新鲜度评分/边界 | `tests/unit/domain/value_objects/test_data_source.py` | Task 1 |
| **TDD 单元测试** | 领域端口 | Protocol 契约/Query Object | `tests/unit/domain/ports/test_data_source_port.py` | Task 1 |
| **TDD 领域异常测试** | 异常体系 | 构造/to_dict()/HTTP 映射 | `tests/unit/domain/exceptions/test_data_source_exceptions.py` | Task 2 |
| **TDD 领域异常测试** | 编码唯一性/子域范围 | 零碰撞/继承链一致 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 2 |
| **TDD 单元测试** | 适配器 ×8 | 成功/重试/限流/熔断/解析/异常映射 | `tests/unit/infrastructure/external_services/datasources/test_*_adapter.py` | Task 3/4/5 |
| **TDD 单元测试** | Resolver 服务 | 白名单/缓存/并发/降级/事件 | `tests/unit/application/services/test_data_source_resolver.py` | Task 6 |
| **TDD 单元测试** | 标记解析器 | 标记提取/语法错误/去重 | `tests/unit/application/services/test_data_source_marker.py` | Task 7 |
| **TDD 单元测试** | Engine 增强 | 注入 preamble/None 回归/部分失败 | `tests/unit/application/services/test_tool_execution_engine_datasource.py` | Task 7 |
| **TDD 契约测试** | 端口契约 | 11 维度注册/兼容性/resolve | `tests/contracts/test_port_contract_data_source.py` + `test_port_contract_data_source_resolver.py` | Task 0/6 |
| **TDD 验收测试** | Gherkin 场景 + BDD 步骤 | 业务价值验收 | `tests/acceptance/test_acceptance_data_source.feature` + `.py` | Task 0/10 |
| **集成测试** | 引擎+Resolver+Redis 全链路 | 真实服务协作 | `tests/integration/application/test_data_source_execution.py` | Task 8 |
| **集成测试** | 国家局 crawler | 真实 crawler 服务（动态 skip） | `tests/integration/external_services/data_sources/test_china_nbs_crawler.py` | Task 8 |
| **集成测试** | HTTP 链路 | 本地 aiohttp 服务器模拟外部 API | `tests/integration/external_services/data_sources/test_adapters_http_chain.py` | Task 8 |
| **SDD 架构验证** | 六边形约束 | 零依赖/注册完整/依赖方向 | `tests/unit/architecture/test_arch_data_source.py` | Task 9 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src`）- **P0 阻断门禁**
- [ ] **领域层 ≥90%**（新增值对象/异常/事件全覆盖）
- [ ] **应用层 ≥85%**（Resolver/标记解析器/Engine 增强路径）
- [ ] **基础设施层 ≥75%**（8 适配器含异常分支）
- [ ] **关键路径 100%**：白名单校验、缓存命中/降级、标记解析、异常映射所有分支

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`；第三方库缺类型走 `stubs/` PEP 561 存根）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> 见「🎯 测试隔离约束」节全文。核心：TestTenant UUID 前缀、外部 HTTP 一律 MockTransport/本地服务器、crawler 动态 skip、asyncio.Lock 类变量、BDD 禁 @pytest.mark.asyncio、每测试只清理自有资源。

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | DataSourcePort 端口 + 值对象 + ToolMetadata 扩展 | Task 1 | 全部 | `test_data_source.py` / `test_data_source_port.py` / `test_port_contract_data_source.py` |
| AC-2 | 8 个数据源适配器 | Task 3/4/5 | 各适配器 TDD 循环 | `test_*_adapter.py` ×8 |
| AC-3 | 缓存层 + 新鲜度评分 | Task 1（DataFreshness）/ Task 6（Resolver 缓存集成） | 1.2 / 6.x | `test_data_source.py` / `test_data_source_resolver.py` |
| AC-4 | Engine.Execute $DATA_SOURCE 增强 | Task 7 | 全部 | `test_data_source_marker.py` / `test_tool_execution_engine_datasource.py` |
| AC-5 | 异常与事件契约 | Task 2 | 全部 | `test_data_source_exceptions.py` / `test_code_ranges.py` |
| AC-6 | 集成测试 | Task 8 | 全部 | `test_data_source_execution.py` / `test_china_nbs_crawler.py` / `test_adapters_http_chain.py` |
| AC-7 | 架构验证测试 | Task 9 | 全部 | `test_arch_data_source.py` |
| AC-8 | BDD 验收测试 | Task 0（红）/ Task 10（绿） | 0.4-0.6 / 10.x | `test_acceptance_data_source.feature` / `.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-8 的规范输入）

> **目的：** 在进入代码实现前，明确端口契约、值对象、异常契约、事件 Schema、Gherkin 验收场景与六边形架构边界。

- [ ] Subtask 0.1: 定义领域事件 Schema（`DataSourceFetched`/`DataSourceFetchFailed`，含 payload 字段与双通道登记计划）
- [ ] Subtask 0.2: 定义数据模型（5 个值对象字段级签名 + DataSourceQuery + ToolMetadata/EvidencePackage 扩展方案）
- [ ] Subtask 0.3: 定义端口契约（DataSourcePort / DataSourceResolverPort 方法签名 + 8 个适配器 PortSpec 元数据表：name/version/owner/tags）
- [ ] Subtask 0.4: 异常契约登记（5 项 Checklist：定义文件 + `_code_ranges.py` 子域段 + `__init__.py` 导出 + `EXCEPTION_HTTP_MAP` 注册 + 设计文档 §3.3.2 同步计划）
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_data_source.feature`（Happy Path + 4 个 Edge Cases）
- [ ] Subtask 0.6: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_data_source.py`
- [ ] Subtask 0.7: 编写端口契约测试骨架 `tests/contracts/test_port_contract_data_source.py`（11 维度，此时实现不存在）
- [ ] Subtask 0.8: 运行验收测试 + 契约测试，确认失败（🔴 红阶段验证，失败原因 = ModuleNotFoundError/端口未注册）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（端口/值对象/异常/事件/契约清单）
- [ ] 验收测试与契约测试运行失败（预期行为，红阶段确认）
- [ ] 异常编码零碰撞验证通过

---

### Task 1: 领域层端口与值对象

**关联 AC:** AC-1, AC-3（DataFreshness 部分）

#### TDD 循环 [A]：值对象（DataSourceRef/DataSourceApiType/DataFreshness/DataSourceResult/DataSourceMeta）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_data_source.py`（不变量：非法 ttl/name/confidence/url 抛对应领域异常；freshness 衰减曲线与 stale 边界） |
| 🟢 绿 | 实现 `src/domain/value_objects/data_source.py` 5 个 frozen dataclass |
| 🔄 重构 | 统一校验风格（对齐 `container_spec.py` / `tool_execution.py` 先例），运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写值对象失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 5 个值对象（DataFreshness 含 score/is_stale）
- [ ] Subtask 1.3: 🔄 重构 — 校验逻辑收敛，docstring 完善（Google 风格全中文）

#### TDD 循环 [B]：DataSourcePort Protocol + DataSourceQuery

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_data_source_port.py`（runtime_checkable/方法签名/合规实现 isinstance/不合规实现拒绝） |
| 🟢 绿 | 实现 `src/domain/ports/data_source.py`（Protocol + DataSourceQuery） |
| 🔄 重构 | 类型注解完善（参数级签名对齐契约测试断言） |

- [ ] Subtask 1.4: 🔴 红 — 编写端口失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 DataSourcePort + DataSourceQuery
- [ ] Subtask 1.6: 🔄 重构 — 签名与 docstring 对齐

#### TDD 循环 [C]：ToolMetadata.data_sources 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 ToolMetadata 扩展测试（带 data_sources 构造/默认空 tuple 向后兼容/23 个 SKILL.md 解析回归） |
| 🟢 绿 | 扩展 `src/application/ports/skill_loader.py` ToolMetadata + frontmatter 解析支持可选 `data_sources` 键 |
| 🔄 重构 | 运行既有 skill_loader 全套测试确认零回归 |

- [ ] Subtask 1.7: 🔴 红 — 编写扩展失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 ToolMetadata 扩展 + frontmatter 解析（**关键：`src/application/skills/frontmatter.py:32-41` `LIST_FIELDS` 追加 `"data_sources"`；`frontmatter.py:170-188` `normalize_metadata` 追加 `data_sources=meta.get("data_sources", ())`，否则 YAML 中添加 `data_sources:` 会被静默丢弃**）
- [ ] Subtask 1.9: 🔄 重构 — 回归验证（`pytest tests/unit/application/skills/ tests/unit/application/ports/`）

**完成标准/Definition of Done:**
- [ ] 端口与值对象实现完成，Task 0 契约测试的"接口维度"转绿
- [ ] 领域层覆盖率 ≥90%
- [ ] skill_loader 回归全绿

---

### Task 2: 领域异常与领域事件

**关联 AC:** AC-5

#### TDD 循环 [A]：4 个新异常（data_source 子域 410-413）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_data_source_exceptions.py`（构造/context/to_dict()/cause 链/HTTP 映射） |
| 🟢 绿 | 实现 `src/domain/exceptions/data_source_exceptions.py` + `_code_ranges.py` 子域注册 + `__init__.py` 导出 + `EXCEPTION_HTTP_MAP` 映射 |
| 🔄 重构 | 运行异常全套测试（唯一性/子域范围/HTTP 映射） |

- [ ] Subtask 2.1: 🔴 红 — 编写异常失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 4 个异常 + 5 项完整性 Checklist 登记
- [ ] Subtask 2.3: 🔄 重构 — `pytest tests/unit/domain/exceptions/ tests/unit/interfaces/api/test_exception_handlers.py` 全绿
- [ ] Subtask 2.4: 同步 `sisys-uni-exception-design.md` §3.3.2 编码分配表

#### TDD 循环 [B]：领域事件（DataSourceFetched/DataSourceFetchFailed）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写事件单元测试（event_type/aggregate 归属/payload 序列化/双通道配置一致性） |
| 🟢 绿 | 实现 `src/domain/events/data_source_events.py` + `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 同步登记 |
| 🔄 重构 | 运行事件体系回归测试 |

- [ ] Subtask 2.5: 🔴 红 — 编写事件失败测试
- [ ] Subtask 2.6: 🟢 绿 — 实现 2 个事件 + 双通道登记
- [ ] Subtask 2.7: 🔄 重构 — 事件注册/反序列化回归全绿

**完成标准/Definition of Done:**
- [ ] 异常 5 项 Checklist 完成，编码零碰撞
- [ ] 事件双通道配置一致（yaml 与 DEFAULT_MAPPINGS）
- [ ] 异常/事件测试全绿

---

### Task 3: 数据源适配器 A 组（免 Key 统计类：WorldBank / Eurostat / IMF）

**关联 AC:** AC-2

> **模式范本**：`EmbeddingAPIClient`（`src/infrastructure/external_services/embedding/embedding_api_client.py`）——httpx.AsyncClient + tenacity（3 次指数退避，仅 5xx/超时/传输错误）+ 自研 CircuitBreaker 复用 + 内联 except 链错误映射 + dataclass `from_env()` 配置。
> **单元测试范本**：httpx.MockTransport 注入（`tests/unit/infrastructure/crawler/test_http_crawler_client.py:44-62`）。

#### TDD 循环 [A]：WorldBankAdapter（REST_JSON）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/datasources/test_worldbank_adapter.py`（成功/超时/5xx 重试耗尽→411/解析失败→413/熔断） |
| 🟢 绿 | 实现 `worldbank_adapter.py` + 配置类 |
| 🔄 重构 | 错误映射收敛，ruff + mypy |

- [ ] Subtask 3.1: 🔴 红 — 编写 WorldBankAdapter 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 WorldBankAdapter（GDP/Governance Indicators）
- [ ] Subtask 3.3: 🔄 重构 — 质量门禁通过

#### TDD 循环 [B]：EurostatAdapter（SDMX_JSON）

- [ ] Subtask 3.4: 🔴 红 — 编写 EurostatAdapter 失败测试（SDMX JSON 结构解析）
- [ ] Subtask 3.5: 🟢 绿 — 实现 EurostatAdapter（PoC v1 已验证端点）
- [ ] Subtask 3.6: 🔄 重构 — SDMX 解析健壮性

#### TDD 循环 [C]：IMFAdapter（SDMX_JSON）

- [ ] Subtask 3.7: 🔴 红 — 编写 IMFAdapter 失败测试
- [ ] Subtask 3.8: 🟢 绿 — 实现 IMFAdapter（World Economic Outlook）
- [ ] Subtask 3.9: 🔄 重构 — 与 Eurostat 的 SDMX 公共逻辑评估收敛（**仅当真实重复出现时**，禁止投机抽象）

- [ ] Subtask 3.10: 3 个适配器注册到 composition_root（`data_source_worldbank` / `data_source_eurostat` / `data_source_imf`，SINGLETON）+ 契约测试对应维度转绿

**完成标准/Definition of Done:**
- [ ] 3 个适配器实现 + 单测全绿（含异常映射分支）
- [ ] composition_root 注册完成，端口契约测试通过
- [ ] 基础设施层覆盖率 ≥75%

---

### Task 4: 数据源适配器 B 组（Tavily / NewsAPI / USPTO / IPCC）

**关联 AC:** AC-2

#### TDD 循环 [A]：TavilyAdapter（REST_JSON + API Key）

- [ ] Subtask 4.1: 🔴 红 — 编写 `test_tavily_adapter.py` 失败测试（含 429→412 限流、401/403→ConfigurationError 路径）
- [ ] Subtask 4.2: 🟢 绿 — 实现 TavilyAdapter（`TAVILY_API_KEY` env 注入，缺 Key 抛 ConfigurationError(101)）
- [ ] Subtask 4.3: 🔄 重构 — Key 脱敏验证（`__repr__`/异常消息/to_dict 零泄露）

#### TDD 循环 [B]：NewsAPIAdapter（REST_JSON + API Key）

- [ ] Subtask 4.4: 🔴 红 — 编写 `test_newsapi_adapter.py` 失败测试（免费 100 次/天限额 429 场景）
- [ ] Subtask 4.5: 🟢 绿 — 实现 NewsAPIAdapter（`NEWSAPI_API_KEY`）
- [ ] Subtask 4.6: 🔄 重构 — 质量门禁通过

#### TDD 循环 [C]：USPTOAdapter（REST_JSON，无 Key）

- [ ] Subtask 4.7: 🔴 红 — 编写 `test_uspto_adapter.py` 失败测试（专利查询/分页参数）
- [ ] Subtask 4.8: 🟢 绿 — 实现 USPTOAdapter
- [ ] Subtask 4.9: 🔄 重构 — 质量门禁通过

#### TDD 循环 [D]：IPCCAdapter（CSV_DOWNLOAD）

- [ ] Subtask 4.10: 🔴 红 — 编写 `test_ipcc_adapter.py` 失败测试（CSV 下载/解析/大文件截断保护）
- [ ] Subtask 4.11: 🟢 绿 — 实现 IPCCAdapter
- [ ] Subtask 4.12: 🔄 重构 — 质量门禁通过

- [ ] Subtask 4.13: 4 个适配器注册到 composition_root + 契约测试转绿

**完成标准/Definition of Done:**
- [ ] 4 个适配器实现 + 单测全绿
- [ ] API Key 安全审查通过（零硬编码/零日志泄露）
- [ ] 注册与契约测试通过

---

### Task 5: 中国国家统计局适配器（CrawlerClientPort 复用）

**关联 AC:** AC-2

> **强制约束：** 必须经 `CrawlerClientPort`（`src/domain/ports/crawler_client.py:13`）提交爬虫任务（seed_urls + use_browser 反爬），**禁止**适配器内直接 httpx 抓取国家局站点（PoC v2 已验证直连 403）。

#### TDD 循环 [A]：ChinaNBSAdapter（CRAWLER）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_china_nbs_adapter.py` 失败测试（任务提交/状态轮询/结果解析/任务失败映射 411；CrawlerClientPort 用 AsyncMock(spec=) 单元级 mock） |
| 🟢 绿 | 实现 `china_nbs_adapter.py`（构造注入 CrawlerClientPort，轮询超时/退避策略） |
| 🔄 重构 | 轮询参数配置化，ruff + mypy |

- [ ] Subtask 5.1: 🔴 红 — 编写 ChinaNBSAdapter 失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 ChinaNBSAdapter
- [ ] Subtask 5.3: 🔄 重构 — 质量门禁通过
- [ ] Subtask 5.4: 注册 `data_source_china_nbs`（lambda 工厂注入 `resolver.resolve("crawler_client")`，范本 `composition_root.py:1971-1979`）

**完成标准/Definition of Done:**
- [ ] 适配器实现 + 单测全绿
- [ ] CrawlerClientPort 复用确认（无直连抓取代码）
- [ ] 注册完成，契约测试通过

---

### Task 6: DataSourceResolverService（白名单 + 缓存 + 并发 + 新鲜度）

**关联 AC:** AC-3, AC-4（采集编排部分）

#### TDD 循环 [A]：白名单校验 + 单源采集

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_data_source_resolver.py`（白名单违规→207/正常采集/结果元数据完整） |
| 🟢 绿 | 实现 `src/application/ports/data_source_resolver.py` + `src/application/services/data_source_resolver.py` |
| 🔄 重构 | 职责收敛（Resolver 不做标记解析，只负责采集编排） |

- [ ] Subtask 6.1: 🔴 红 — 编写白名单 + 采集失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现 Resolver 最小代码
- [ ] Subtask 6.3: 🔄 重构 — 质量门禁通过

#### TDD 循环 [B]：Redis 缓存集成 + 新鲜度

- [ ] Subtask 6.4: 🔴 红 — 编写缓存测试（命中 cache_hit=True/失效重采/TTL 边界/租户隔离/Redis 故障降级透传）
- [ ] Subtask 6.5: 🟢 绿 — 集成 L1CachePort（`build_key("cache:datasource", ...)` + `set_with_ttl`）
- [ ] Subtask 6.6: 🔄 重构 — 缓存键构造收敛

#### TDD 循环 [C]：并发采集 + 事件发布

- [ ] Subtask 6.7: 🔴 红 — 编写并发测试（asyncio.gather 部分成功收敛/失败发布 DataSourceFetchFailed/成功发布 DataSourceFetched）
- [ ] Subtask 6.8: 🟢 绿 — 实现 fetch_many + 事件发布（EventPublisher 注入）
- [ ] Subtask 6.9: 🔄 重构 — 事件 payload 与契约对齐
- [ ] Subtask 6.10: Resolver 注册 composition_root（lambda 聚合 8 个 `data_source_*` 端口注入 adapters Mapping）+ `test_port_contract_data_source_resolver.py` 转绿

**完成标准/Definition of Done:**
- [ ] Resolver 全功能实现，单测全绿
- [ ] 缓存降级路径验证（Redis 断连不阻断采集）
- [ ] 应用层覆盖率 ≥85%

---

### Task 7: Engine.Execute $DATA_SOURCE 集成

**关联 AC:** AC-4

#### TDD 循环 [A]：标记解析器（data_source_marker.py）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_data_source_marker.py`（单标记/多标记/嵌套引号/语法错误→ValidationError(201)/重复标记去重/大小写） |
| 🟢 绿 | 实现 `src/application/services/data_source_marker.py`（`parse(code) -> tuple[DataSourceQuery, ...]` + `inject(code, results) -> str` preamble 内联） |
| 🔄 重构 | 正则/AST 选型收敛（优先 ast.literal_eval 安全解析参数，禁止 eval） |

- [ ] Subtask 7.1: 🔴 红 — 编写标记解析器失败测试
- [ ] Subtask 7.2: 🟢 绿 — 实现标记解析器
- [ ] Subtask 7.3: 🔄 重构 — 安全审查（禁止 eval/exec 动态执行标记参数）

#### TDD 循环 [B]：Engine 集成（可选注入，None 零行为变化）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_tool_execution_engine_datasource.py`（注入 resolver 后 Execute 代码含 preamble/None 时零行为变化回归/白名单违规传播/部分失败收敛） |
| 🟢 绿 | 扩展 `ToolExecutionEngine.__init__`（`data_source_resolver: DataSourceResolverPort \| None = None`）+ `_execute_stage` 前置处理 |
| 🔄 重构 | 引擎复杂度控制（Execute 前置逻辑委托标记解析器 + Resolver，引擎本体仅编排） |

- [ ] Subtask 7.4: 🔴 红 — 编写 Engine 集成失败测试
- [ ] Subtask 7.5: 🟢 绿 — 实现 Engine 增强
- [ ] Subtask 7.6: 🔄 重构 — 既有 Engine 测试全绿（零回归）

#### TDD 循环 [C]：EvidencePackage.data_sources 扩展

- [ ] Subtask 7.7: 🔴 红 — 编写 EvidencePackage 扩展失败测试（默认空 tuple 向后兼容/DataSourceMeta 校验）
- [ ] Subtask 7.8: 🟢 绿 — 扩展 `src/domain/value_objects/tool_execution.py` EvidencePackage + Validate 阶段挂载元数据
- [ ] Subtask 7.9: 🔄 重构 — 既有 EvidencePackage 测试全绿
- [ ] Subtask 7.10: composition_root 中 `tool_execution_engine` 注册注入 `resolver.resolve_optional("data_source_resolver")`（保持装饰器栈不变）

**完成标准/Definition of Done:**
- [ ] $DATA_SOURCE 全链路打通（标记→白名单→并发采集→注入→元数据）
- [ ] resolver=None 回归测试通过（零行为变化）
- [ ] 沙箱 network_mode=none 不变量未被破坏（grep 自查无网络配置变更）

---

### Task 8: 集成测试（真实服务）

**关联 AC:** AC-6

> **性质说明：** 本 Task 验证组件间真实协作。真实 Redis + 本地 aiohttp HTTP 服务器 + 真实 Engine/Resolver；Mock 仅限 LLM/Sandbox/外部 SaaS 端点（以本地服务器替代）。

#### 集成测试实现

- [ ] Subtask 8.1: 🔴 红 — 编写 `tests/integration/external_services/data_sources/test_adapters_http_chain.py`（本地 aiohttp 服务器模拟 WorldBank/Eurostat API，验证 httpx + tenacity + 熔断完整链路；范本 `test_integration_llm_client.py`）
- [ ] Subtask 8.2: 🟢 绿 — 本地服务器 fixture + 断言链路行为（重试次数/熔断状态转换）
- [ ] Subtask 8.3: 🔴 红 — 编写 `tests/integration/application/test_data_source_execution.py`（真实 Engine + Resolver + 真实 Redis 测试端口 + TestTenant 前缀 + AsyncMock LLM/Sandbox：`$DATA_SOURCE` 全链路 + 缓存命中二次执行 + 租户隔离）
- [ ] Subtask 8.4: 🟢 绿 — 全链路集成测试通过
- [ ] Subtask 8.5: 编写 `tests/integration/external_services/data_sources/test_china_nbs_crawler.py`（crawler 服务可达时真实任务提交验证；不可达 `pytest.skip()` 动态跳过）
- [ ] Subtask 8.6: 🔄 重构 — `pytest -n 8` 并行验证 + 连续 5 次无随机失败

**完成标准/Definition of Done:**
- [ ] 集成测试全绿（或动态 skip 有据）
- [ ] 并行测试稳定（5 次无随机失败）
- [ ] 无手动 delete/truncate，测试自包含清理

---

### Task 9: SDD 架构约束验证测试

**关联 AC:** AC-7

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构约束是否被遵守）。范本 `tests/unit/architecture/test_arch_strategic_tool_impl.py`。

#### 架构验证测试实现

- [ ] Subtask 9.1: 创建 `tests/unit/architecture/test_arch_data_source.py`（常量区：新文件清单 + FORBIDDEN_IMPORTS 黑名单）
- [ ] Subtask 9.2: 实现 domain 零依赖校验（AST 扫描 data_source.py/data_source_exceptions.py/data_source_events.py/value_objects）
- [ ] Subtask 9.3: 实现端口注册完整性校验（PortSpec 10 字段 + 8 适配器 + resolver 全注册 + SINGLETON 生命周期）
- [ ] Subtask 9.4: 实现依赖方向校验（application 新文件不 import infrastructure；实现类 isinstance Protocol）
- [ ] Subtask 9.5: 实现异常码段校验（410-413 ∈ data_source 子域）
- [ ] Subtask 9.6: 运行完整测试套件并生成合规报告

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 任何违规导致测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-8

> **性质说明：** 对 Story 收尾阶段交付物与完成清单的最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已编写 feature + BDD 骨架（确认失败）；本 Task 补齐全部场景步骤实现 |
| 🟢 绿 | 完成 `tests/acceptance/test_acceptance_data_source.py` 全部步骤（真实服务 + AsyncMock 仅限 LLM/Sandbox/外部HTTP） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 10.1: 场景 1 — Happy Path：Skill 代码含 `$DATA_SOURCE` → 采集 → 注入 → 输出含 source/freshness/confidence
- [ ] Subtask 10.2: 场景 2 — Edge：白名单外数据源 → BusinessRuleViolationError(207)，断言 error.code + error.message
- [ ] Subtask 10.3: 场景 3 — Edge：数据源不可用 → 部分失败收敛 + DataSourceFetchFailed 事件
- [ ] Subtask 10.4: 场景 4 — Edge：缓存命中（二次执行 cache_hit=True，外部调用次数不增）
- [ ] Subtask 10.5: 场景 5 — Edge：429 限流 → DataSourceRateLimitError(412)
- [ ] Subtask 10.6: 运行开发结束验收测试并确认通过
- [ ] Subtask 10.7: 运行 `pytest`、`ruff check`、`mypy` 收尾校验 + 完成清单逐项确认（src + tests/unit + tests/integration + tests/contracts + tests/acceptance）

**完成标准/Definition of Done:**
- [ ] 全部 Gherkin 场景通过
- [ ] 完成清单逐项验证确认
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §17.3 工具箱架构 + §1.5 CLI+Skills 设计原则 + §13.11 Skills 目录结构

- **架构模式:** 六边形架构（Ports & Adapters）+ 端口注册中心（PortSpec/Registry/Resolver/ContractGate）+ 装饰器层叠（ToolOutputValidator/SandboxSecurityDecorator 先例）
- **设计约束:** 领域层零依赖（.importlinter 强制）；依赖方向 interfaces→application→domain；端口仅经 composition_root 注册
- **沙箱无网络不变量:** `ContainerSpec.network_mode="none"`（`src/domain/value_objects/container_spec.py:45`）→ 数据采集必须在宿主机侧（Engine Execute 前置）完成并内联注入
- **Skills 渐进式披露:** L1 TOOLS.md ≤1.2K tokens / L2 SKILL.md ≤500 行 / L3 scripts 按需；本 Story 的 data_sources 声明走 ToolMetadata（L1/L2 元数据面）
- **技术栈:** Python 3.11+ / httpx ^0.27 / tenacity ^9.1 / redis ^5.0 / 自研 CircuitBreaker（复用，禁止引入 pybreaker 等新依赖）

### 关键架构决策

**来源:** 本 Story 设计调研（2026-09-24，4 视角并行代码调研）

| 决策点 | 选中方案 | 备选方案 | 依据 |
|--------|---------|---------|------|
| DataSourcePort 归属层 | ✅ **domain/ports**（10/10） | application/ports（6/10） | LLMClientPort/SandboxExecutor/CrawlerClientPort 外部能力网关均归 domain；application/ports 放技术横切抽象（现有判例） |
| 缓存方案 | ✅ **复用 L1CachePort**（10/10） | 新建 DataSourceCachePort（4/10） | L1CachePort 已有 set_with_ttl/delete_pattern；Simplicity First 禁止重复抽象；key_builder 命名空间工具现成 |
| Engine 集成方式 | ✅ **Engine 构造可选注入 resolver**（9/10） | 新增装饰器层（6/10） | $DATA_SOURCE 标记在 Code 阶段产物内，装饰器看不到中间代码；Engine `_execute_stage` 前置是唯一合理切入点；可选参数 None 零行为变化保证向后兼容 |
| 数据注入方式 | ✅ **Python 字面量 preamble 内联**（9/10） | 沙箱内网络白名单（0/10，违反 4.4 不变量）/ 文件挂载（5/10） | 沙箱 network_mode=none 领域不变量不可破坏；preamble 注入最简单且可审计 |
| HTTP 适配器模式 | ✅ **EmbeddingAPIClient 模板**（httpx+tenacity+自研熔断+内联异常映射）（10/10） | ErrorMapper 装饰器（5/10） | 现行惯例为内联 except 链（官方注释称 ErrorMapper 装饰器为兜底方案）；禁止引入 respx 等新测试依赖，用 httpx.MockTransport |
| 国家局采集 | ✅ **复用 CrawlerClientPort**（10/10） | 适配器直连 httpx（2/10） | PoC v2 验证直连 403 反爬；crawler 插件已有 Playwright/UA 轮换/限速/robots 合规 |
| 异常编码段 | ✅ **新增 data_source (410,419) 子域**（9/10） | 挤占 tool 384/external 304-305（3/10） | external 301-399 已满且零散；399 预留 Story 4.7；"只追加"原则允许新段；架构文档 42x 已预留 skill 子域，410-419 不冲突 |
| 白名单违规异常 | ✅ **复用 BusinessRuleViolationError(207)**（9/10） | 新增 DataSourcePolicyError（4/10） | 禁止同义异常重复定义；策略违规语义吻合 |

### 项目结构说明 Project Structure（本 Story 新增/修改）

```
src/
├── domain/
│   ├── ports/
│   │   └── data_source.py                      # [新增] DataSourcePort + DataSourceQuery
│   ├── value_objects/
│   │   └── data_source.py                      # [新增] DataSourceRef/ApiType/Result/DataFreshness/DataSourceMeta
│   ├── exceptions/
│   │   ├── data_source_exceptions.py           # [新增] 4 个异常（410-413）
│   │   ├── _code_ranges.py                     # [修改] +data_source (410,419) 子域
│   │   └── __init__.py                         # [修改] 导出新异常
│   ├── events/
│   │   └── data_source_events.py               # [新增] DataSourceFetched/DataSourceFetchFailed
│   └── entities/
│       └── tool_execution.py                   # [修改] EvidencePackage +data_sources 字段
├── application/
│   ├── ports/
│   │   ├── data_source_resolver.py             # [新增] DataSourceResolverPort
│   │   └── skill_loader.py                     # [修改] ToolMetadata +data_sources 字段
│   └── services/
│       ├── data_source_resolver.py             # [新增] DataSourceResolverService（白名单+缓存+并发+新鲜度+事件）
│       ├── data_source_marker.py               # [新增] $DATA_SOURCE 标记解析器
│       └── tool_execution_engine.py            # [修改] +data_source_resolver 可选注入 + Execute 前置
├── infrastructure/
│   ├── config/
│   │   └── datasources.py                      # [新增] 8 个数据源配置类（dataclass + from_env，Key 脱敏）
│   ├── external_services/
│   │   └── datasources/                        # [新增] 适配器包
│   │       ├── __init__.py
│   │       ├── _http_helpers.py                # [可选] 纯函数 helper(_build_retry_decorator / _build_default_circuit_breaker / _sanitize_url_query);**禁止预先抽 base.py 抽象类**(8 适配器中仅 6 个 REST_JSON 真正能复用模板,SDMX/CSV/Crawler 三类差异显著;严格遵守 CLAUDE.md §2 Simplicity First 与 Story 977"仅当真实重复出现时";先抽纯函数,不引入强制继承层级;现有 embedding/llm 已重复未抽 base 是先例)
│   │       ├── worldbank_adapter.py
│   │       ├── imf_adapter.py
│   │       ├── eurostat_adapter.py
│   │       ├── uspto_adapter.py
│   │       ├── ipcc_adapter.py
│   │       ├── newsapi_adapter.py
│   │       ├── tavily_adapter.py
│   │       └── china_nbs_adapter.py            # 复用 CrawlerClientPort
│   └── messaging/
│       └── channel_router.py                   # [修改] DEFAULT_MAPPINGS +2 事件
├── interfaces/api/
│   └── exception_handlers.py                   # [修改] EXCEPTION_HTTP_MAP +4 映射
├── composition_root.py                         # [修改] 注册 8 适配器 + resolver + engine 注入
configs/
└── event_channels.yaml                         # [修改] +2 事件双通道
tests/
├── contracts/
│   ├── test_port_contract_data_source.py       # [新增] 11 维度
│   └── test_port_contract_data_source_resolver.py
├── unit/
│   ├── domain/value_objects/test_data_source.py
│   ├── domain/ports/test_data_source_port.py
│   ├── domain/exceptions/test_data_source_exceptions.py
│   ├── application/services/test_data_source_resolver.py
│   ├── application/services/test_data_source_marker.py
│   ├── application/services/test_tool_execution_engine_datasource.py
│   ├── infrastructure/external_services/datasources/test_*_adapter.py  # ×8
│   └── architecture/test_arch_data_source.py
├── integration/
│   ├── application/test_data_source_execution.py
│   └── external_services/data_sources/test_china_nbs_crawler.py
│   └── external_services/data_sources/test_adapters_http_chain.py
└── acceptance/
    ├── test_acceptance_data_source.feature
    └── test_acceptance_data_source.py
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4.1a](./4-1a-strategic-tool-impl.md) + [Story 4.4](./4-4-docker-sandbox-execution.md)

**关键学习/Key Learnings（4.1a，源自 4.1）：**
- PortSpec 10 字段元数据规范（name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated），composition_root 声明式注册
- TOOL_CATALOG 常量作为元数据单一数据源（避免数据漂移）——本 Story 8 个数据源的 DataSourceRef 同样集中定义
- asyncio.Lock 必须类变量（P0-6 教训）
- 事件双通道：yaml + DEFAULT_MAPPINGS 两处同步（4.1 单通道教训）

**关键学习/Key Learnings（4.4）：**
- 装饰器层叠模式（ToolOutputValidator/SandboxSecurityDecorator）+ ExecutionContext.extensions 透传先例（schema_last_violations）
- 第三方库版本钉死（aiodocker 0.25 升级教训）
- xdist 分组串行（sandbox-daemon 组）+ 动态 skip（禁止写死 @pytest.mark.skip）
- 新增异常 5 项 Checklist 实战（含 _code_ranges 子域注册）
- 重试白名单收窄先例：沙箱确定性失败不可重试——本 Story 数据源 4xx/解析失败同样不重试

**应用到本故事/Applied to This Story:**
- [ ] 8 个 DataSourceRef 集中定义（单一数据源原则），适配器注册引用同一常量
- [ ] 新事件双通道两处同步登记 + 一致性测试
- [ ] 异常 5 项 Checklist 在 Task 0/2 完成，编码零碰撞 grep 验证
- [ ] 数据源 4xx/解析失败（413）不重试，仅 5xx/超时/传输错误重试（对齐 4.4 重试收窄先例）
- [ ] crawler 集成测试动态 skip，xdist 分组隔离外部资源

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（k3[1m]）+ 4 个并行调研 Agent（Explore） |
| **Version** | create-story workflow（template.md v2.9.0 结构） |
| **Execution Date** | 2026-09-24 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/config.yaml` |
| **Template** | `.claude/skills/bmad-create-story/template.md`（与 `docs/developer/story-template.md` 一致） |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 4.1b 定义 + commit 371eca5a PoC 结论） |
| **架构文档** | `docs/architecture/architecture.md`（§17.3 工具箱架构 / §13.11 Skills 目录） |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md`（§3.3 编码分配策略） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-4-docker-sandbox-execution.md`（done） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` Story 4.1b 提取（DataSourcePort + 8 适配器 + 缓存 + Engine 增强）
- [x] 架构约束从 `architecture.md` §17.3 + 沙箱无网络不变量提取
- [x] 前一个故事学习经验整合（4.1a + 4.4）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 命名澄清（key=4-1b-skills-feat-enhancement ↔ epics Story 4.1b 数据采集基础设施）
- [x] 多 Agent 并行调研整合（领域端口/应用引擎/基础设施/测试模式 4 视角，全部结论附文件:行号证据）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1b-skills-feat-enhancement.md`

**待创建的文件/To Be Created (Dev Story 实施):** 见「项目结构说明」节（src 17 个新增/修改 + tests 18 个新增）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1b |
| **Story Key** | 4-1b-skills-feat-enhancement |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1b-skills-feat-enhancement.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略决策智能（Executive Decision Intelligence） |
| **优先级** | P0-5（数据采集基础设施，4.1c/4.1d/4.1e 的公共底座） |
| **覆盖 FR** | Epic 4 增量补充（无独立 FR 编号；支撑 FR-ST-01 工具分析数据驱动化 + FR-IF-02 Skills 渐进式加载增强） |
| **前置 Story** | 4-1a-strategic-tool-impl（✅ done）/ 4-4-docker-sandbox-execution（✅ done）/ 1-4 Redis 缓存层（✅ done） |
| **后续 Story** | 4-1c-skills-data-collection-integration / 4-1d-skills-framework-enhancement / 4-1e-skills-internal-framework |
| **估算工作量** | **18-25 人天**（端口与值对象 2 + 异常事件 1.5 + 适配器 8×1~1.5 + Resolver 2 + Engine 集成 2 + 集成/架构/验收测试 4 + 30% 缓冲） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0 + Task 1-10，共 11 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-8，含 Edge Cases）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 4 层 + R1-R5 + 沙箱无网络不变量 + 异常编码段决策）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4.1a PortSpec/双通道 + 4.4 装饰器/重试收窄/动态 skip）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| - | 无（首次创建，待审查） | - | - |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 待 dev-story 实施后填写
**审查模式:** 待填写

#### 需决策 Decision Needed

- [ ] 待填写

#### 已修复 Patch

- [ ] 待填写

#### 已推迟 Defer

- [ ] 待填写

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-09-24
**最后更新/Last Updated:** 2026-09-24
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics_v1.0.md Story 4.1b + commit 371eca5a PoC 结论 + 4 视角并行代码调研）
