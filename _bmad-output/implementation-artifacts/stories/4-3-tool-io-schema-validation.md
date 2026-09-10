# Story 4.3: 工具输入/输出 Schema 验证

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环,禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 质量工程师,
**I want** 系统在 Tool 调用前/后对输入/输出数据做 **JSON Schema 契约化** Schema 验证(domain 层 stdlib 友好子集 + 应用层 jsonschema 库委托完整 Draft 7),失败时按重试策略自动恢复或明确标记不可行,
**So that** 工具输出符合预期格式,防止 LLM 模型漂移(model drift)导致的脏数据污染下游分析。

**设计说明:** Story 标题沿用业务表述"Schema 验证",内容采用 **JSON Schema**(非 Pydantic V2) — 因 Pydantic 违反 domain 层零外部依赖硬约束(`CLAUDE.md §5`),仅在应用层端口实现中**可选**通过 jsonschema 库委托。

### 业务价值

Story 4.1a 已在 `Tool` 聚合根声明 `input_schema / output_schema` 字段(JSON Schema dict,`src/domain/entities/tool.py:84-85`),
但当前 ToolExecutionEngine 五阶段工作流的 **Validate 阶段完全是 LLM-driven 自由文本判定**(`src/application/services/tool_execution_engine.py:317-332`),
**未对 `ToolResult.output` 做 JSON Schema 契约验证**,也未在调用前对 `ToolCall.arguments` 做入参 Schema 校验。

具体缺口:

1. **入参未校验**: `ToolCall.arguments` 直接传给 LLM,无 `jsonschema.validate(arguments, Tool.input_schema)` 调用
2. **出参未校验**: `ToolResult.output` 是 dict,无 `jsonschema.validate(output, Tool.output_schema)` 调用
3. **失败语义缺失**: 即使 Validate 阶段 LLM 判定失败,也只是把 `validation: str` 写入证据包,**ToolResult.status 永远 = SUCCESS**(`tool_execution_engine.py:206`),下游消费者无法区分"执行成功"和"产出不符合契约"
4. **无 Schema 反馈**: 失败时无结构化错误信息(如字段路径 + 期望 vs 实际值)反馈给上游 retry/agent
5. **无 Schema 版本演进**: Tool.version 字段存在,但 output_schema 变更时无兼容性检测

本 Story 引入 **Schema 验证领域服务 + 应用层装饰器 + ToolResult 状态扩展**,让 23 种战略工具产出 **契约化、可验证、可重试** 的结构化结果。

**业务定位:** Epic 4 战略工具箱的 **质量保障层**,位于单工具执行(4.1a)+ 工具链编排(4.2)之上、Validation Feedback 闭环(4.7)之下。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱,FR-ST-03
**前置依赖:** Story 4.1a(Tool 聚合根 + ToolExecutionEngine 五阶段)/ Story 4.2(工具链 DAG 编排,可选依赖 — DAG 节点执行也需 Schema 验证)
**后续依赖:** Story 4.7(Validation Feedback 闭环增强 — Schema 失败自动重试/降级)/ Story 4.6(工具版本管理 — output_schema 兼容性检查)

---

## 🛡️ 硬约束声明(CLAUDE.md §5)

> 本 Story 实施过程中**严格遵守**以下硬约束,违反任何一项需返回 `draft` 状态重新设计。

### 领域零依赖(FR-AR-01)

- `src/domain/` 禁止 import 任何第三方包(`pydantic` 等),仅 Python stdlib
- **关键决策**: JSON Schema 验证逻辑在 domain 层**不依赖 jsonschema / pydantic**;
  使用 stdlib `jsonschema` 不可用(Python 3.11 stdlib 无 jsonschema),采用 stdlib 简化校验
  + 4 个必填关键词自检(`type/properties/required/items`)。完整 JSON Schema 验证能力**委托给应用层端口**(`SchemaValidatorPort`),其实现位于 infrastructure 层,可选用 jsonschema 库。
- `.importlinter` 强制校验:`poetry run lint-imports`

### 异常体系强制(sisys-uni-exception-design.md)

- **禁止** `raise ValueError(...)`
- **禁止** 手动 `raise HTTPException(...)`
- **禁止** 继承内置 `Exception`(除 `DomainError` 基类)
- **必须** 走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前**三条 grep 自查**必须零输出:`grep -rn "raise ValueError\|raise HTTPException\|class.*Exception\b" src/`

### 新增异常完整性 Checklist(4 项强制)

> **关键决策(Round 1 调研结论):** `tool` 子域(380-389)中 380-383 + 385-389 已分配 9 个,**EXCEPTION_384 保留未占用**(`_code_ranges.py:73` 注释);`toolchain` 子域(390-399)当前已分配 5 个(390/391/392/393 + 394=`ToolChainNotFoundError` — 4.2 Round 1 审查新增),**剩 5 个码位(395-399)**,本 Story 占用 4 个(395-398)。

- **新增 `toolchain` 子域追加 4 异常**(沿用 4.2 已建立的 toolchain 子域嵌套声明惯例):
  - EXCEPTION_395 `ToolInputSchemaValidationError`(输入参数违反 Tool.input_schema) — **调整原因**:EXCEPTION_394 已被 `ToolChainNotFoundError`(4.2 R1 审查新增)占用
  - EXCEPTION_396 `ToolOutputSchemaValidationError`(输出结果违反 Tool.output_schema)
  - EXCEPTION_397 `ToolSchemaCompatibilityError`(output_schema 版本不兼容旧 execution)
  - EXCEPTION_398 `ToolSchemaMissingError`(Tool.input_schema / output_schema 为空且无 default_schema)
- 4 项 Checklist:
  1. **定义文件**:在 `src/domain/exceptions/tool_schema_exceptions.py` 创建异常类(新增子域模块,与 tool_chain_exceptions.py 对称)
  2. **`_code_ranges.py` 子域映射**:在 `_CLASS_TO_SUBDOMAIN` 注册 4 个新异常类(子域复用 4.2 已建 `toolchain` 子域 390-399,本 Story 占 395-398)
  3. **`__init__.py` 暴露**:在 `src/domain/exceptions/__init__.py` 导入并加入 `__all__`
  4. **子域码段校验**:异常 `code` 在 `toolchain` 子域 395-398 范围内

### 抑制告警禁止

- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释
- **禁止** mypy 配置 `ignore_missing_imports=true` 豁免
- 第三方库缺类型注解时**必须**创建 PEP 561 stubs(`stubs/<package>/__init__.pyi`)

### Commit & Push 规范

- **禁止** commit 信息含 AI 辅助署名(`Co-Authored-By: Claude` / `anthropic.com` 等)
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 已合入的架构依赖规则
- **禁止** 修改已合入的 alembic migration(只允许新增,本期新增 migration 013)

---

## 🎯 领域异常契约(CLAUDE.md §5 强制)

> 本 Story 涉及的所有异常必须在 Task 0 完成前完成 4 项 Checklist。

### 已存在异常复用

| 异常类 | code | parent | 触发场景 | 复用方式 |
|--------|------|--------|----------|---------|
| `ToolResultValidationError` | EXCEPTION_389 | `ValidationError` (EXCEPTION_201) | ToolResult.status=invalid(本 Story 扩展:`reason` 携带 schema 验证错误详情) | Task 0 扩展:增加 `schema_violations: list[dict]` context 字段 |
| `ToolExecutionRetryExhaustedError` | EXCEPTION_383 | `BusinessException` | Schema 验证失败重试 3 次后仍失败 | 复用(由 ToolExecutionEngine._retry_call 触发) |
| `EntityValidationError` | EXCEPTION_242 | entity 子域 | Schema 字段非 dict / required 字段缺失 | 复用 |

### 候选新增异常(本 Story Task 0 评估)

**关键决策:** `tool` 子域 380-389 中 380-383 + 385-389 已分配 9 个,EXCEPTION_384 保留未占用(`_code_ranges.py:73` 注释)。
本 Story 复用 4.2 已建立的 `toolchain` 子域(390-399),本 Story 占 395-398 共 4 个码位(**EXCEPTION_394 已被 `ToolChainNotFoundError` 4.2 R1 审查新增占用,故顺延 1 位**)。
`toolchain` 子域物理上仍嵌套于 `external: (301, 399)`,语义上与 DAG 编排并列"工具链相关异常"(沿用 4.2 R1 子域嵌套声明惯例)。

**新增 4 个异常(4 项 Checklist 强制):**

| 候选异常 | 触发场景 | parent class | code | 子域 | HTTP 映射 |
|----------|----------|--------------|------|------|-----------|
| `ToolInputSchemaValidationError` | `ToolCall.arguments` 违反 `Tool.input_schema`(类型不匹配 / required 字段缺失 / enum 值越界 / 未声明字段) | `ValidationError` (EXCEPTION_201) | EXCEPTION_395 | toolchain (395-398) | 400 |
| `ToolOutputSchemaValidationError` | `ToolResult.output` 违反 `Tool.output_schema`(LLM 模型漂移导致输出不符合契约) | `ValidationError` (EXCEPTION_201) | EXCEPTION_396 | toolchain (395-398) | 422 |
| `ToolSchemaCompatibilityError` | `Tool.output_schema` 变更(版本号升级)后,旧 in-flight execution 结果与新 schema 不兼容 | `BusinessException` | EXCEPTION_397 | toolchain (395-398) | 409 |
| `ToolSchemaMissingError` | Tool 缺失 input_schema / output_schema 且无 default_schema fallback | `ConfigurationError` (EXCEPTION_101) | EXCEPTION_398 | toolchain (395-398) | 500 |

**HTTP 状态码映射登记**(CLAUDE.md §5 红线延伸):Task 0 必须在 `src/interfaces/api/exception_handlers.py:109` 的模块级常量 `EXCEPTION_HTTP_MAP` 表追加上述 4 个异常的映射(400/422/409/500)。

**toolchain 子域(390-399)剩余码位**:EXCEPTION_399 共 **1 个码位预留**,供后续 Story(4.7 Validation Feedback)扩展。**风险与决策矩阵**:若 4.7 需 ≥2 个新异常,以下三选一(推荐 **方案 A**):

| 方案 | 操作 | 优点 | 缺点 |
|------|------|------|------|
| **方案 A** (推荐) | 扩 `toolchain` 子域到 400-409 | 对称,语义延续,4.7 异常可集中在新子域 | CODE_RANGES 改动 + _CLASS_TO_SUBDOMAIN 调整 |
| **方案 B** | 复用 tool 子域的 EXCEPTION_384 保留位 | 零架构改动 | 语义混杂(toolchain 异常混进 tool 子域) |
| **方案 C** | 申请全新 `toolchain_feedback` 子域(410-419) | 语义最干净 | 子域颗粒度过细 + CODE_RANGES 双重改动 |

**4.7 异常需求预测**:预计新增 2 个异常(沿用 4.2 子域嵌套惯例):
- `ValidationFeedbackRetryExhaustedError`(继承 `BusinessException`, EXCEPTION_399 + 子域预留码位)
- `ValidationFeedbackFallbackFailedError`(继承 `BusinessException`, 子域预留码位)

**复用现有异常(非新增):**
- `EntityValidationError` (EXCEPTION_242) 复用:SchemaValidator 输入数据非 dict / Schema 字段非 dict
- `ToolResultValidationError` (EXCEPTION_389) **扩展**:增加 `schema_violations: list[dict]` context 字段,携带字段路径 + 期望类型 + 实际值(向下兼容,默认值空 list)

### 异常登记确认(Task 0 必做项)

**Task 0 必须完成的 3 项异常登记动作:**

1. **`_code_ranges.py` 更新 toolchain 子域注释**(不新增子域,仅追加 4 异常注释到现有 toolchain 条目)
2. **`sisys-uni-exception-design.md §3.3.2` 表补登记 toolchain 子域新增 4 异常**
3. **新增模块文件**:`src/domain/exceptions/tool_schema_exceptions.py`
   - 4 个新异常类
   - `__all__` 导出
4. **扩展 `ToolResultValidationError`**:`tool_exceptions.py:263-290` 增加 `schema_violations: list[dict]` context 字段(向后兼容)

**5 项 Checklist 自查(CLAUDE.md §5 沿用 4.2 惯例):**
- [ ] Task 0 完成时 `grep -rn "EXCEPTION_395\|EXCEPTION_396\|EXCEPTION_397\|EXCEPTION_398" src/domain/exceptions/` 全部有定义
- [ ] `_CLASS_TO_SUBDOMAIN` 表覆盖 4 个新异常类(`toolchain` 子域)
- [ ] `src/domain/exceptions/__init__.py` 导入并 `__all__` 暴露 4 个新异常
- [ ] `tests/unit/domain/exceptions/test_code_ranges.py` 子域码段校验通过(`toolchain` ∈ [390, 399] 且 4 异常码 ∈ [395, 398])
- [ ] `tests/unit/domain/exceptions/test_error_code_uniqueness.py` 编码唯一性校验通过(注:EXCEPTION_394 已被 ToolChainNotFoundError 占用,本 Story 不复用)
- [ ] `sisys-uni-exception-design.md §3.3.2` 表补登记 4 个新异常
- [ ] **第 5 项**:`EXCEPTION_HTTP_MAP` 表(`src/interfaces/api/exception_handlers.py:109`)追加 4 个新异常的 HTTP 映射(400/422/409/500)
- [ ] 测试覆盖在 `tests/unit/domain/exceptions/test_tool_schema_exceptions.py`,断言 4 个新异常的 parent class(MRO chain 含正确基类)

---

## 🎯 测试隔离约束(CLAUDE.md §5 + template.md §4.4)

> 本 Story 所有测试**严格遵守**以下隔离约束,违反任何一项 CI 阻断。

### 测试租户隔离(TestTenant UUID 前缀)

- 所有集成测试 / 验收测试**必须**使用 `TestTenant` 生成 UUID 前缀
- UUID 前缀覆盖五层存储资源(Redis key / PG schema / Qdrant collection / MinIO bucket / RabbitMQ queue)

### 异步测试约束

- **`asyncio.Lock` 必须声明为类变量**而非实例变量(CLAUDE.md §6 Gotchas)
- **BDD 步骤函数禁止 `@pytest.mark.asyncio`**,统一使用 `event_loop.run_until_complete()`
- pytest-asyncio 当前配置 `asyncio_mode = "auto"`(`pyproject.toml:274`);本期新增的 BDD 步骤函数统一使用 `event_loop.run_until_complete()`
- **并行 Schema 验证测试**:多 Tool 实例共享 SchemaValidatorPort,使用 `asyncio.gather()` 在 async 函数内触发

### 集成测试两种子模式(CLAUDE.md §5)

本 Story 集成测试使用以下两种子模式之一:

1. **真实服务 Schema 隔离模式**(推荐):独立 PG schema + savepoint rollback + 租户隔离 bucket
   - 适用:SchemaValidationRecord 端到端存储、ToolExecutionEngine 集成 Schema 验证
2. **Mock 工厂模式**(例外):`AsyncMock(spec=ProtocolClass)` + `_make_*()` 工厂函数
   - 适用:SchemaValidator 真实实现涉及 jsonschema 库 import 成本场景

### 测试数据清理

- **禁止** 手动 `delete` / `truncate` 任何数据库表
- 使用 savepoint rollback 自动清理(推荐)或 TestTenant UUID 前缀隔离(自清理)

### 验证测试禁止 Mock

- **验收测试禁止 mock**(CLAUDE.md §5)
- 强制使用 `scenarios() + context dict + 真实服务实例 + pytest.skip()` 动态跳过
- 集成测试 mock 仅在"无安全清理的纯基础设施"场景例外

---

## 🌐 API 契约(template.md §4.1.6 强制)

> 本 Story 主要交付应用层 Schema 装饰器 + 领域层 Schema 验证服务,**不直接暴露 HTTP 端点**。
> 但 ToolSchemaValidationFailed 事件订阅契约影响下游订阅者(4.7 Validation Feedback),需在 API 契约小节明确。

### 事件契约(ToolSchemaValidationFailed)

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_type` | `str` | 固定为 `"ToolSchemaValidationFailed"`(**新增**) |
| `execution_id` | `UUID` | 关联 ToolExecution 聚合根 ID |
| `tool_id` | `UUID` | 工具 ID |
| `tenant_id` | `UUID` | 多租户隔离(**Round 1 补充**,**4.2 起的 toolchain 事件 baseline 必填**;4.1a ToolExecuted 是历史遗留未带 tenant_id,**4.6 工具版本管理 Story 需决策是否统一回填**) |
| `aggregate_id` | `UUID` | = `execution_id` |
| `aggregate_type` | `str` | `"ToolExecution"` |
| `validation_phase` | `str` | `"INPUT"` / `"OUTPUT"` / `"COMPATIBILITY"` |
| `schema_violations` | `list[dict]` | 字段路径 + 期望类型 + 实际值 |
| `retry_attempt` | `int` | 当前重试次数(1-based) |
| `failed_at` | `datetime` | 失败时间戳(ISO 8601) |
| `schema_version` | `str` | **Round 1 新增**,Tool.version 快照(校验发起时),4.6 兼容性追踪用 |
| `is_final` | `bool` | **Round 1 新增**,是否终止事件(INPUT 失败 = True;OUTPUT 重试 N 次仅最后一次 = True),简化 4.7 订阅者去重 |

### 内部端口契约(非 HTTP)

- `SchemaValidatorPort.validate_input(tool: Tool, arguments: dict) -> SchemaValidationResult`(应用层端口)
- `SchemaValidatorPort.validate_output(tool: Tool, output: dict) -> SchemaValidationResult`(应用层端口)
- `SchemaValidationRecordRepositoryPort.save(record) / list_by_query(query)`(领域层仓储端口,继承 `L2RdbPort[SchemaValidationRecord]`)

### 契约测试文件

- `tests/contracts/test_event_contract_tool_schema_validation_failed.py`(事件契约:字段必填 + 序列化 + 通道双投递)
- `tests/contracts/test_port_contract_schema_validator.py`(端口契约 11 维度)
- `tests/contracts/test_port_contract_schema_validation_record_repository.py`(端口契约 11 维度)
- **不**创建 `tests/contracts/test_port_contract_schema_validator_service.py`(SchemaValidator 是应用层服务,纯函数测试在 `tests/unit/application/services/test_schema_validator.py`)

---

## 📊 Story Details(template.md §4.6 强制)

| 字段 | 值 |
|------|-----|
| Story ID | `4.3` |
| Story Key | `4-3-tool-io-schema-validation` |
| File | `_bmad-output/implementation-artifacts/stories/4-3-tool-io-schema-validation.md` |
| Status | `ready-for-dev` |
| Epic | Epic 4: 战略工具箱 |
| 价值组 | 战略工具质量保障(Tool Quality Assurance) |
| 优先级 | P0(Epic 4 战略工具箱核心 Story) |
| 估算工作量 | **27-35 人天**(含 SchemaValidator **6 类验证** + 4 端口契约测试 + 1 领域 SchemaValidator 服务 + 2 装饰器 + RetryExecutor 抽离 + 1 聚合根 + 1 类事件(13 字段)+ Alembic migration 013 + 集成测试 + 4.1a ToolResult 字段回归修复 + TDD 完整循环 +30% 缓冲)。**较 18-25 人天原估算上调**:首次引入装饰器学习成本 + RetryExecutor 抽离 + PEP 561 stubs 扩展 + 6 项校验规则扩展(含 additionalProperties)+ 4.1a 23种 Tool 测试回归修复 |
| 覆盖 FR | FR-ST-03(工具输入/输出 Schema 验证) |
| 前置 Story | 4-1a-strategic-tool-impl(已 ready-for-dev)/ 4-2-toolchain-orchestration-dag(可选 — DAG 节点执行复用 Schema 验证) |
| 后续 Story | 4-6-tool-version-management(灰度发布需 Schema 兼容性检查)/ 4-7-validation-feedback-loop(Schema 失败自动重试/降级) |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: SchemaValidator 领域服务(纯函数 JSON Schema 校验)

**Given** Tool 已声明 input_schema / output_schema(JSON Schema dict)
**When** 实现 `SchemaValidator` 领域服务(纯函数,无副作用)
**Then**

- **路径**:`src/domain/services/schema_validator.py`(领域服务,**纯函数**,无外部依赖)
- **核心方法**:
  - `validate_arguments(tool: Tool, arguments: dict) -> SchemaValidationResult` — 入参校验
  - `validate_output(tool: Tool, output: dict) -> SchemaValidationResult` — 出参校验
- **`SchemaValidationResult` frozen dataclass**:
  ```python
  @dataclass(frozen=True)
  class SchemaValidationResult:
      is_valid: bool
      violations: tuple[SchemaViolation, ...] = ()
      validated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

      def to_dict(self) -> dict[str, Any]:
          return {
              "is_valid": self.is_valid,
              "violations": [v.to_dict() for v in self.violations],
              "validated_at": self.validated_at.isoformat(),
          }

  @dataclass(frozen=True)
  class SchemaViolation:
      path: str           # JSON Pointer (RFC 6901),如 "/items/2/name"
      expected: str       # 期望类型/值,如 "string"
      actual: Any         # 实际值(脱敏后)
      message: str        # 人类可读错误
  ```
- **6 项校验规则**(基于 JSON Schema 核心子集,**领域层 stdlib 友好**):
  1. **类型校验**:JSON Schema `type` 关键字(`string` / `number` / `integer` / `boolean` / `array` / `object` / `null`)
  2. **必填字段**:`required` 关键字(Object 顶层缺失字段报错)
  3. **未声明字段禁止**:`additionalProperties: false` 关键字(**P0 风险防御** — 防 LLM 模型漂移注入未声明字段,Anthropic/GPT-4 实测 2-8% 概率;SchemaValidator 默认对所有 `properties` 子 schema 注入 `additionalProperties=false`)
  4. **枚举约束**:`enum` 关键字(值不在枚举集合报错)
  5. **数组 items**:`items` 关键字(数组元素类型约束)
  6. **嵌套对象 properties**:`properties` 关键字(递归校验嵌套对象)
- **不实现**:`$ref` / `allOf` / `anyOf` / `oneOf` / `format` / `const`(留给应用层端口的可选 jsonschema 库实现扩展)
- **空 schema 处理**:`Tool.input_schema == {}` 时 `validate_arguments` 返回 `is_valid=True`(向后兼容 4.1a 既有 Tool 注册),但配合 `ToolSchemaMissingError` (EXCEPTION_398) 记录 warning 日志
- **算法复杂度**:O(N)(N = 数据节点数,递归遍历;实际为 O(N × M),M 为嵌套深度 + enum 集合大小 + required 长度的常数因子)
- **业界参考**:JSON Schema Draft 7 核心子集 + Instructor Pydantic `extra="forbid"`(避免引入 jsonschema 第三方库,保持 domain 层零依赖)

**验证标准/Validation Criteria:**
- [ ] `SchemaValidator` 位于 `src/domain/services/`(**纯函数**,无外部依赖)
- [ ] **6** 项校验规则完整(类型 / required / **additionalProperties** / enum / items / properties)
- [ ] `SchemaValidationResult` 含 `is_valid / violations / validated_at` 三字段
- [ ] `SchemaViolation` 含 `path / expected / actual / message` 四字段
- [ ] 空 schema 返回 `is_valid=True`(向后兼容)
- [ ] 嵌套对象递归校验(properties 嵌套)
- [ ] domain 层零依赖验证通过(`poetry run lint-imports`)
- [ ] 单元测试覆盖:正常 / 类型错误 / required 缺失 / enum 越界 / items 类型错误 / 嵌套对象 / 空 schema
- [ ] **`SchemaValidator._sanitize_actual(value: Any)`** 完整实现(Round 3 新增):处理 datetime/UUID/Decimal/bytes/嵌套 dict/嵌套 list/Pydantic 模型/fallback(NaN/Inf → None),用于 `SchemaViolation.to_dict()` 序列化前置脱敏(防 PostgreSQL JSONB 写入失败)

### AC-2: SchemaValidatorPort 应用层端口(jsonschema 库委托)

**Given** 领域层 SchemaValidator 仅实现 JSON Schema 核心子集,完整 Draft 7+ 能力需委托外部库
**When** 创建 `SchemaValidatorPort` Protocol + jsonschema 库实现
**Then**

- **路径**:
  - Port:`src/application/ports/schema_validator.py`
  - Impl:`src/infrastructure/validation/jsonschema_validator.py`
- **Protocol 方法签名**:
  ```python
  @runtime_checkable
  class SchemaValidatorPort(Protocol):
      """Schema 验证端口协议(应用层)

      委托 jsonschema 库实现完整 JSON Schema Draft 7+ 验证;
      领域层 SchemaValidator(AC-1)仅实现核心子集,本端口扩展全功能。
      """

      def validate_arguments(
          self, tool: Tool, arguments: dict[str, Any],
      ) -> SchemaValidationResult: ...

      def validate_output(
          self, tool: Tool, output: dict[str, Any],
      ) -> SchemaValidationResult: ...

      def validate_schema_compatibility(
          self, old_schema: dict, new_schema: dict,
      ) -> SchemaCompatibilityResult: ...
  ```
- **`JsonSchemaValidatorImpl` 实现要点**:
  - 使用 `jsonschema` 第三方库(Draft 7 validator,**已在 `pyproject.toml:139` dev group 声明**,无需新增依赖)
  - `validate_arguments` / `validate_output` 捕获 `jsonschema.ValidationError` 转换为 `SchemaViolation` 列表(**使用 `iter_errors()` 而非 `validate()`,以提供完整错误反馈**)
  - `validate_schema_compatibility` 检测:
    - **破坏性**:`new["required"] ⊃ old["required"]`(新增必填)/ `new["enum"] ⊂ old["enum"]`(缩小枚举)/ 字段类型 narrow(`string` → `integer`)/ `additionalProperties` 从 `true` 改 `false`
    - **非破坏性**:字段类型 widen(`integer` → `number`)/ `new["required"] ⊆ old["required"]`(删除必填)/ `additionalProperties` 从 `false` 改 `true`
  - 返回 `SchemaCompatibilityResult(is_compatible: bool, breaking_changes: tuple[BreakingChange, ...])`
- **依赖**:`infrastructure/validation` 是**新增子目录**(无现有代码),位于 `src/infrastructure/validation/jsonschema_validator.py`
- **jsonschema 类型存根**:**已有** `stubs/jsonschema/__init__.pyi`(`pyproject.toml:225` `mypy_path = "stubs"`),4.1a 已用 `Draft7Validator.check_schema()` + `SchemaError`。本 Story 需**扩展** stubs 覆盖:`Draft7Validator.__init__` / `Draft7Validator.iter_errors()` / `ValidationError` (含 `path`/`message`/`validator`/`instance` 属性)/ `Draft7Validator.validate()` 顶层函数

**验证标准/Validation Criteria:**
- [ ] `SchemaValidatorPort` Protocol 定义完整(3 方法:validate_arguments / validate_output / validate_schema_compatibility)
- [ ] `JsonSchemaValidatorImpl` 实现完整(jsonschema Draft 7)
- [ ] `validate_arguments` / `validate_output` 正确转换 `jsonschema.ValidationError` → `SchemaViolation`
- [ ] `validate_schema_compatibility` 检测破坏性变更(required 字段删除 / 收紧 enum / 类型变更)
- [ ] `composition_root.py` 注册 `schema_validator` 端口(name=`schema_validator`, version=`v1.0.0`, interface=`SchemaValidatorPort`, impl=`JsonSchemaValidatorImpl`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "schema", "validator")`,compatibility=`()`,deprecated=`False`)
- [ ] jsonschema 库 PEP 561 stubs **扩展**(4.1a 已建 `check_schema`/`SchemaError`,本 Story 扩展 `iter_errors`/`ValidationError`)
- [ ] 端口契约测试 `tests/contracts/test_port_contract_schema_validator.py` 11 维度覆盖
- [ ] **`BreakingChange` / `NonBreakingChange` / `SchemaCompatibilityResult` 值对象完整定义**(Round 3 补充)
- [ ] **`validate_schema_compatibility` 完整规则清单**(Round 3 补充):12 条规则覆盖 8 类破坏性 + 4 类非破坏性

**`BreakingChange` 值对象定义**(对标 Avro BACKWARD 模式 + Confluent Schema Registry + oasdiff 分类):

```python
class ChangeType(str, Enum):
    """破坏性变更类型(强类型,便于 4.6 灰度策略匹配)"""
    REQUIRED_FIELD_ADDED = "required_field_added"           # 新增必填字段
    REQUIRED_FIELD_REMOVED = "required_field_removed"        # 删除必填字段/字段完全删除
    FIELD_TYPE_NARROWED = "field_type_narrowed"             # 类型收窄(integer → string)
    FIELD_TYPE_CHANGED = "field_type_changed"               # 类型完全变更(string → object/array/boolean)
    ENUM_VALUE_REMOVED = "enum_value_removed"                # 枚举值删除(enum 缩小)
    ADDITIONAL_PROPERTIES_RESTRICTED = "additional_props_restricted"  # true → false
    NESTED_SCHEMA_TIGHTENED = "nested_schema_tightened"      # 嵌套 schema 收紧(递归)
    MIN_VALUE_INCREASED = "min_value_increased"             # minimum/minLength 增大

@dataclass(frozen=True)
class BreakingChange:
    """破坏性变更值对象"""
    change_type: ChangeType
    path: str                          # JSON Pointer (RFC 6901),如 "/properties/name/type"
    old_value: Any | None              # 旧 schema 该位置的值
    new_value: Any | None              # 新 schema 该位置的值
    description: str                   # 人类可读描述
    severity: Literal["critical", "major", "minor"] = "major"
    remediation: str | None = None     # 修复建议
```

**`NonBreakingChange` 值对象定义**(7 字段):

```python
class NonBreakingChangeType(str, Enum):
    OPTIONAL_FIELD_ADDED = "optional_field_added"           # 新增可选字段
    FIELD_TYPE_WIDENED = "field_type_widened"              # 类型放宽(integer → number)
    ENUM_VALUE_ADDED = "enum_value_added"                   # 枚举值增加
    ADDITIONAL_PROPERTIES_RELAXED = "additional_props_relaxed"  # false → true
    DEFAULT_ADDED = "default_added"                         # 添加 default 值
    DESCRIPTION_UPDATED = "description_updated"
    PATTERN_RELAXED = "pattern_relaxed"

@dataclass(frozen=True)
class NonBreakingChange:
    change_type: NonBreakingChangeType
    path: str
    old_value: Any | None
    new_value: Any | None
    description: str
```

**`SchemaCompatibilityResult` 值对象定义**(5 字段):

```python
@dataclass(frozen=True)
class SchemaCompatibilityResult:
    """Schema 兼容性检测结果值对象(对标 Avro SchemaValidatorResult)"""
    is_compatible: bool                                          # 是否完全兼容
    compatibility_level: Literal["BACKWARD", "FULL"] = "BACKWARD"  # 对标 Avro 4 类
    breaking_changes: tuple[BreakingChange, ...] = ()
    non_breaking_changes: tuple[NonBreakingChange, ...] = ()
    schema_diff: dict[str, Any] = field(default_factory=dict)   # 完整 diff 摘要(供 UI 渲染)
```

**`validate_schema_compatibility` 完整规则清单**(12 条):

| # | 规则 | 类型 | ChangeType |
|---|------|------|-----------|
| 1 | `new.required ⊃ old.required`(新增必填) | BREAKING | REQUIRED_FIELD_ADDED |
| 2 | `new.required ⊆ old.required`(删除必填) | BREAKING | REQUIRED_FIELD_REMOVED |
| 3 | 字段完全删除(`path ∈ old.properties 但 ∉ new.properties`) | BREAKING | REQUIRED_FIELD_REMOVED |
| 4 | 枚举值减少(`new.enum ⊂ old.enum`) | BREAKING | ENUM_VALUE_REMOVED |
| 5 | 类型完全变更(`string → object/array/boolean`) | BREAKING | FIELD_TYPE_CHANGED |
| 6 | 类型收窄(`integer → string` / `number → integer`) | BREAKING | FIELD_TYPE_NARROWED |
| 7 | `additionalProperties: true → false` | BREAKING | ADDITIONAL_PROPERTIES_RESTRICTED |
| 8 | 嵌套 schema 收紧(递归 properties 单独检查) | BREAKING | NESTED_SCHEMA_TIGHTENED |
| 9 | `minimum` / `minLength` 增大 | BREAKING | MIN_VALUE_INCREASED |
| 10 | 类型放宽(`integer → number`) | NON_BREAKING | FIELD_TYPE_WIDENED |
| 11 | 字段新增(非 required) | NON_BREAKING | OPTIONAL_FIELD_ADDED |
| 12 | `additionalProperties: false → true` | NON_BREAKING | ADDITIONAL_PROPERTIES_RELAXED |

### AC-3: ToolInputValidator + ToolOutputValidator 装饰器(横切关注点)

**Given** Schema 验证是 Tool 调用前后的横切关注点,需对 `ToolExecutionService.execute` / `ToolExecutionEngine.execute` 做透明装饰
**When** 实现 `ToolInputValidator`(装饰 Service 层)+ `ToolOutputValidator`(装饰 Engine 层,**纯 Decorator 外包模式**),并**抽离** `_call_with_retry` 共享工具函数避免重复实现重试逻辑
**Then**

> **关键决策(Round 1 修订):** **统一采用"Decorator 外包 + 包裹"模式**(非 Engine 内部注入)。
> - `ToolInputValidator` 包裹 `ToolExecutionService`(注入 `tool_registry` 解决 Tool 元数据获取)
> - `ToolOutputValidator` 包裹 `ToolExecutionEngine`(持有 engine 引用,调 `_call_with_retry` 复用重试)
> - **重试机制**:**抽离** `_call_with_retry(func, retry_policy, on_failure_callback)` 共享工具函数(`src/application/services/retry_helpers.py`),**不依赖** Engine 私有 `_retry_call` 实例方法
> - Engine 内部 `_retry_call` 重构为薄壳调用 `_call_with_retry`,4.1a 既有 API 兼容

- **路径**:
  - `src/application/services/tool_input_validator.py`(入参装饰器)
  - `src/application/services/tool_output_validator.py`(出参装饰器)
  - `src/application/services/retry_helpers.py`(**新增**,`_call_with_retry` 共享工具函数)
- **装饰器签名**:
  ```python
  class ToolInputValidator:
      """入参 Schema 验证装饰器(包裹 ToolExecutionService)

      在委托前对 arguments 做 Schema 校验(通过注入的 tool_registry 解析 Tool)。
      校验失败策略:
      - strict(默认): 抛 ToolInputSchemaValidationError(EXCEPTION_395),不进 Engine
      - lenient: 记录 warnings 继续执行(用于 MVP/调试)
      """

      def __init__(
          self,
          wrapped: ToolExecutionService,
          schema_validator: SchemaValidatorPort,
          tool_registry: ToolRegistryServicePort,  # 注入以解决 Tool 元数据获取
          event_publisher: EventPublisher,  # 校验失败时发布 ToolSchemaValidationFailed (INPUT)
          failure_policy: Literal["strict", "lenient"] = "strict",
      ) -> None: ...

      async def execute(
          self, tool_id: UUID, tool_call: ToolCall, context: ExecutionContext,
      ) -> ToolResult: ...

  class ToolOutputValidator:
      """出参 Schema 验证装饰器(包裹 ToolExecutionEngine,纯 Decorator 外包)

      在 Engine.execute 返回 ToolResult 前做 Schema 校验。
      校验失败:
      - 调用 _call_with_retry 触发重试(默认沿用 RetryPolicy.max_attempts,可在构造时覆盖)
      - 重试时通过 _build_validate_prompt 注入上轮 violations 给 LLM 作为反馈
      - 重试耗尽 → 设置 ToolResult.status = FAILED + ToolResult.retry_count 填充 + 抛 ToolResultValidationError (EXCEPTION_389)
      - 每次重试失败都通过 event_publisher 发布 ToolSchemaValidationFailed (OUTPUT)
      """

      def __init__(
          self,
          wrapped: ToolExecutionEngine,
          schema_validator: SchemaValidatorPort,
          event_publisher: EventPublisher,  # 校验失败时发布 ToolSchemaValidationFailed (OUTPUT)
          retry_policy: RetryPolicy | None = None,  # 默认沿用 wrapped._retry
      ) -> None: ...

      async def execute(
          self, tool_id: UUID, tool: Tool, tool_call: ToolCall, context: ExecutionContext,
      ) -> ToolResult: ...
  ```
- **依赖注入**:装饰器接收 `SchemaValidatorPort` 抽象(不直接 import `JsonSchemaValidatorImpl`)
- **重试机制**:**抽离** `_call_with_retry(func, retry_policy, on_failure_callback=None)` 工具函数(`retry_helpers.py`),**Engine 内部 `_retry_call` 重构为薄壳**:`_retry_call = lambda func: _call_with_retry(func, self._retry)`,**保留 4.1a 既有 API 兼容**
- **失败反馈**:出参校验失败时,在 retry prompt 中附加 `violations` 结构化错误(而非仅"输出不符合 schema");**通过 `_build_validate_prompt` 注入上轮 violations**
- **事件发布**:装饰器在 INPUT/OUTPUT 校验失败时通过 `EventPublisher.publish()` 发布 `ToolSchemaValidationFailed` 事件(AC-6)

**验证标准/Validation Criteria:**
- [ ] `ToolInputValidator` 装饰器实现完整(strict / lenient 两种策略)
- [ ] `ToolOutputValidator` 装饰器实现完整(自动重试 + violations 反馈)
- [ ] 入参校验失败抛 `ToolInputSchemaValidationError` (**EXCEPTION_395**),不进入 Engine
- [ ] 出参校验失败设置 `ToolResult.status = INVALID`,retry prompt 携带 violations
- [ ] 依赖通过端口注入(不导入具体实现)
- [ ] `_call_with_retry` 工具函数抽出到 `retry_helpers.py`,Engine `_retry_call` 重构为薄壳
- [ ] 单元测试覆盖:strict / lenient / 重试次数 / 重试成功后状态 / 重试耗尽后 FAILED

### AC-4: ToolResult 状态扩展(status=invalid 语义完善)

**Given** `ToolResult.status=INVALID` 已存在(`src/domain/value_objects/tool_execution.py:38`),但当前未被 Schema 验证触发
**When** 扩展 `ToolResult.output` 增加 `validation_violations` 字段 + `evidence_package.validation` 携带 violations
**Then**

- **路径**:
  - 扩展:`src/domain/value_objects/tool_execution.py`(`ToolResult` 增加 `validation_violations: tuple[SchemaViolation, ...]` 字段)
  - 扩展:`src/domain/exceptions/tool_exceptions.py:263-290`(`ToolResultValidationError.__init__` 增加 `schema_violations: list[dict]` 参数,**向后兼容**,默认空 list)
- **`ToolResult` 字段扩展**(共 8 字段,**evidence_package 默认值保留 None 向后兼容**):
  ```python
  @dataclass(frozen=True)
  class ToolResult:
      tool_id: uuid.UUID
      status: ToolResultStatus
      output: dict[str, Any]
      evidence_package: EvidencePackage | None = None   # 【保持向后兼容】默认 None
      started_at: datetime
      completed_at: datetime
      validation_violations: tuple[SchemaViolation, ...] = ()  # 新增
      retry_count: int = 0                                       # 新增(供下游区分原始/重试结果)
  ```
- **向后兼容策略**(避免 4.1a 既有 23 种 Tool 测试回归):
  - `evidence_package` 默认值保持 `None`(**不**强制改为必填,避免 BREAKING CHANGE)
  - `__post_init__` 校验:`status=INVALID` 时 **`validation_violations` 非空** **或** `output` 非空(兼容 4.1a 既有失败路径)
  - 新增字段均为带默认值,放在所有必填字段之后,**不破坏位置参数调用顺序**
  - Task 4 TDD 红阶段**先 grep `ToolResult(`** 全代码库,识别所有实例化点,列出回归清单(预估 1-2 人天修复)
- **`EvidencePackage.validation` 格式升级**(从 `str` → `str | dict`):
  - 成功:`validation = "passed"`(向后兼容)
  - 失败:`validation = {"passed": False, "violations": [...]}`(结构化)
- **`ToolResultValidationError` 扩展**(EXCEPTION_389):
  ```python
  def __init__(
      self,
      message: str | None = None,
      tool_id: str | None = None,
      execution_id: str | None = None,
      reason: str | None = None,
      schema_violations: list[dict] | None = None,  # 新增
  ) -> None:
      context: dict = {}
      # ... 既有逻辑
      if schema_violations is not None:
          context["schema_violations"] = schema_violations  # 新增
      super().__init__(message=message, context=context)
  ```

**验证标准/Validation Criteria:**
- [ ] `ToolResult` 增加 `validation_violations` / `retry_count` 两字段(共 8 字段,**evidence_package 默认 None 保持不变**)
- [ ] `ToolResult` `__post_init__` 校验 `status=INVALID` 时 `validation_violations` 非空 **或** `output` 非空(向后兼容 4.1a 既有失败路径,`EntityValidationError` EXCEPTION_242)
- [ ] `EvidencePackage.validation` 接受 `str | dict`(类型注解 `Union[str, dict]`);`validate_complete()` 同步更新:`dict` 检查 `passed` 键判断完整性
- [ ] `ToolResultValidationError` 扩展 `schema_violations` 参数(向后兼容,默认 None)
- [ ] Task 4 TDD 红阶段 grep `ToolResult(` 回归清单(预估 1-2 人天修复)
- [ ] 单元测试覆盖:status=INVALID 时 violations 缺失抛错 / retry_count 递增 / violations 序列化 to_dict()

### AC-5: SchemaValidationRecord 聚合根 + SchemaValidationRecordRepository 端口

**Given** Schema 验证历史需持久化(用于可靠性评分、调试追踪、Schema 演进分析)
**When** 创建 `SchemaValidationRecord` 聚合根 + 仓储端口
**Then**

- **路径**:
  - `src/domain/entities/schema_validation_record.py`(`SchemaValidationRecord` 聚合根)
  - `src/domain/ports/schema_validation_record_repository.py`(仓储端口 Protocol)
  - `src/infrastructure/storage/inmemory/schema_validation_record_repository.py`(InMemory 实现)
- **`SchemaValidationRecord` 字段**(11 字段):
  - `record_id: UUID`(主键)
  - `execution_id: UUID`(关联 ToolExecution)
  - `tool_id: UUID`
  - `tenant_id: UUID`
  - `validation_phase: Literal["INPUT", "OUTPUT", "COMPATIBILITY"]`
  - `is_valid: bool`
  - `violations: tuple[SchemaViolation, ...]`
  - `retry_attempt: int`
  - `validated_at: datetime`
  - `schema_version: str`(Tool.version 快照,用于兼容性追踪)
  - `failure_reason: str | None`(校验失败时的可读原因)
- **`SchemaValidationRecordQuery` frozen dataclass**(CLAUDE.md §4 决策规则):
  ```python
  @dataclass(frozen=True)
  class SchemaValidationRecordQuery:
      tenant_id: UUID | None = None
      tool_id: UUID | None = None
      execution_id: UUID | None = None
      validation_phase: Literal["INPUT", "OUTPUT", "COMPATIBILITY"] | None = None
      is_valid: bool | None = None
      offset: int = 0
      limit: int = 100
  ```
- **`SchemaValidationRecordRepositoryPort`** 继承 `L2RdbPort[SchemaValidationRecord]`(沿用 4.1a + 4.2 模式):
  ```python
  class SchemaValidationRecordRepositoryPort(L2RdbPort[SchemaValidationRecord], Protocol):
      async def list_by_query(self, query: SchemaValidationRecordQuery) -> list[SchemaValidationRecord]: ...
      async def count(self, query: SchemaValidationRecordQuery) -> int: ...
  ```
- **Alembic migration 013**:`deploy/postgresql/alembic/versions/013_schema_validation_records.py`
  - `schema_validation_records` 表(record_id PK, execution_id, tool_id, tenant_id, validation_phase, is_valid, violations JSONB, retry_attempt, validated_at, schema_version, failure_reason)
  - **4 索引(优化后)**:
    1. `(tenant_id, execution_id)` — **新增**(4.7 Validation Feedback 订阅事件后按 execution_id 查 violations 高频)
    2. `(tenant_id, tool_id, validated_at DESC)` — 替换原 `(tenant_id, tool_id)`(增加时间序列优化)
    3. `(tenant_id, validation_phase, is_valid)` — 替换原 `(tenant_id, validation_phase)`(增加 is_valid 过滤)
    4. `(tenant_id, is_valid, validated_at DESC)` — 替换原 `(tenant_id, is_valid, validated_at)`(按时间倒序)
  - **移除冗余**:`tenant_id` 单列索引在 (tenant_id, *)复合索引已覆盖(PostgreSQL 复合索引可前缀使用)

**验证标准/Validation Criteria:**
- [ ] `SchemaValidationRecord` 聚合根 11 字段完整
- [ ] `SchemaValidationRecordQuery` frozen dataclass(CLAUDE.md §4 决策规则)
- [ ] `SchemaValidationRecordRepositoryPort` 继承 `L2RdbPort[SchemaValidationRecord]` + 扩展 `list_by_query` / `count`
- [ ] `InMemorySchemaValidationRecordRepository` 实现完整(dict + asyncio.Lock 类变量)
- [ ] `composition_root.py` 注册 `schema_validation_record_repository` 端口(lifetime=SCOPED)
- [ ] Alembic migration `013_schema_validation_records.py` 创建(含 4 索引)
- [ ] L2_rdb 存储边界(violations JSONB → L2_rdb;无 L4 依赖)
- [ ] 端口契约测试 `tests/contracts/test_port_contract_schema_validation_record_repository.py` 11 维度覆盖
- [ ] **`InMemorySchemaValidationRecordRepository._lock` 类变量声明**(Round 3 补充):`_lock: lock = lock()` 作为**类变量**(非 `__init__` 内 self._lock),CLAUDE.md §6 Gotchas 强制
- [ ] **并发 save 无数据丢失测试**(Round 3 补充):`asyncio.gather` 触发 100 并发 `save()`,断言 `list_all()` 返回 100 条记录
- [ ] **跨实例锁共享反例测试**(Round 3 补充):验证 `_records: dict` 是**实例变量**(非类变量),与 `_lock` 类变量对比,防止未来误改造成全局共享状态
- [ ] **持久化时机矩阵**(Round 3 补充):INPUT 成功/失败、OUTPUT 成功/中间重试/耗尽、COMPATIBILITY 破坏 均持久化;LLM 调用异常**不**持久化(由 ToolExecutionError 处理)

**Given** Schema 验证失败需异步通知下游订阅者(4.7 Validation Feedback / 监控 / 可靠性评分更新)
**When** 新建 `ToolSchemaValidationFailed` 领域事件 + **realtime 通道本期启用 / reliable 通道 4.7 时启用**
**Then**

> **关键决策(Round 1 修订):** 本期**仅启用 realtime 通道**,reliable 通道**延后到 4.7 启用** — 因本期无订阅者,reliable 通道(RabbitMQ + Outbox)会无限堆积,违反 Kafka/RabbitMQ 最佳实践。

- **路径**:
  - 事件定义:新建 `src/domain/events/tool_schema_events.py`
  - 双通道配置:`configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py:54`(约 line 60,`ChannelRouter.DEFAULT_MAPPINGS` 字典定义起点,±10 行容差)
- **事件 Schema**(**13 字段**,较原 10 字段扩展):
  - **10 原字段**:event_type(继承 DomainEvent) + execution_id / tool_id / tenant_id / aggregate_id / aggregate_type / validation_phase / schema_violations / retry_attempt / failed_at
  - **3 新增字段**: `tenant_id`(原遗漏,**4.2 起的 toolchain 事件 baseline 必填**;4.1a 历史遗留待 4.6 决策) + `schema_version`(4.6 兼容性追踪用) + `is_final: bool`(最后一次重试时 True,**简化 4.7 订阅者去重逻辑**)
  - 完整字段定义见上方"API 契约"节
- **事件触发点**:
  - `ToolInputValidator.execute()`:入参校验失败时发布(`validation_phase = "INPUT"`,**is_final=True** 因 INPUT 不重试)
  - `ToolOutputValidator.execute()`:出参校验失败时发布(`validation_phase = "OUTPUT"`,**每次 retry 失败都发布,仅最后一次 is_final=True**)
- **事件载荷序列化**:`SchemaViolation.to_dict()`(沿用 AC-1 约定,确保下游反序列化一致)
- **依赖注入**:事件发布通过 `EventPublisher`(`src/domain/ports/event_publisher.py:16` 定义 `class EventPublisher(Protocol)`,1.3 已建;**实际类名是 `EventPublisher`,不是 `EventBusPort`**)
- **下游订阅者**(本期不实现订阅者,仅定义契约):
  - 4.7 Validation Feedback:订阅后自动重试或降级(依据 `is_final` 字段去重)
  - 监控:订阅后累计 schema_violations 频次,触发告警
  - Tool.reliability_score 更新:订阅后降低失败 Tool 的可靠性评分

**验证标准/Validation Criteria:**
- [ ] `ToolSchemaValidationFailed` 事件定义完整(**13** 字段,含 `tenant_id` + `schema_version` + `is_final`)
- [ ] `configs/event_channels.yaml` 添加 `ToolSchemaValidationFailed` 映射(**realtime 仅**;reliable 通道**默认 disabled**)
- [ ] `ChannelRouter.DEFAULT_MAPPINGS` 同步更新
- [ ] `ToolInputValidator` + `ToolOutputValidator` 在校验失败时通过 `EventPublisher.publish()` 发布事件
- [ ] 事件契约测试 `tests/contracts/test_event_contract_tool_schema_validation_failed.py` 覆盖(字段必填 + 序列化 + 通道单投递)
- [ ] 单元测试覆盖:INPUT 阶段发布 1 次 is_final=True / OUTPUT 阶段重试 N 次发布 N 次(仅最后一次 is_final=True) / violations 序列化正确
- [ ] **`is_final` 字段在 4.7 订阅契约**(Round 4 新增):去重键 = `(execution_id, validation_phase)` 复合键 + 终止确认超时(如 60s 未收到 is_final=True 视作异常) + realtime at-most-once 兼容性说明(订阅者需幂等处理重复事件)
- [ ] **事件 payload 大小门禁**(Round 4 新增):`schema_violations` 总条数上限 10 条 + `path` 深度截断 ≤10 + 事件总大小 ≤16KB(超出触发 `ToolOutputSchemaValidationError` + payload 截断标记)

### AC-7: 与 ToolExecutionEngine 集成(Validate 阶段增强)

**Given** ToolExecutionEngine.Validate 阶段当前是 LLM 自由文本判定(`tool_execution_engine.py:317-332`)
**When** `ToolOutputValidator` 以**纯 Decorator 外包**方式包裹 Engine(不修改 Engine 源码,**保留 4.1a 向后兼容性**),在 Engine 返回 ToolResult 后做 Schema 契约验证
**Then**

> **关键决策(Round 1 修订):** AC-7 与 AC-3 装饰器模式**统一为"Decorator 外包"**:
> - `ToolExecutionEngine.__init__` **不增加** `output_validator` 参数(避免破坏 4.1a Engine 既有 API)
> - 集成方式:在 `composition_root.py` 装配时,**`ToolOutputValidator(engine)` 替代 `engine`** 注入到 `ToolExecutionService`
> - 重试机制:**抽离**的 `_call_with_retry` 工具函数(`retry_helpers.py`),**Engine 内部 `_retry_call` 重构为薄壳**(4.1a 既有 API 兼容)

- **集成点**:`ToolOutputValidator.execute()` 包裹 `ToolExecutionEngine.execute()`(`tool_execution_engine.py:116` 入口)
- **集成方式**:**纯 Decorator 外包**,Engine 源码**不变**
- **集成时序**:
  1. `ToolOutputValidator.execute()` 委托 `wrapped_engine.execute()` 执行五阶段工作流
  2. Engine 返回 ToolResult 后,`ToolOutputValidator` 调用 `schema_validator.validate_output(tool, result.output)`
  3. 若 violations 非空:`ToolOutputValidator` 调用 `_call_with_retry(partial(engine.execute, ...), retry_policy)` 触发重试
  4. 重试耗尽 → `ToolResult.status = FAILED`,`validation_violations` 填充最后一次 violations,**抛 `ToolResultValidationError` (EXCEPTION_389)**
- **重试 prompt 升级**:重试时附加上一次 violations 给 LLM 作为反馈(在 `Engine._build_validate_prompt` 注入,签名增加 `last_violations` 可选参数)
- **不动 Engine 源码**:**禁止**修改 `ToolExecutionEngine` 既有 4 字段 `__init__`;Engine 内部 `_retry_call` 仅重构为薄壳调用 `_call_with_retry`
- **向后兼容**:`ToolExecutionEngine` 单独实例化(无装饰器)时行为与 4.1a 完全一致(Story 4.1a 测试全部通过)

**验证标准/Validation Criteria:**
- [ ] `ToolExecutionEngine.__init__` **不修改**(保持 4 字段签名)
- [ ] `ToolOutputValidator(engine)` 包裹 Engine,在 composition_root 装配时替代 engine 注入到 Service
- [ ] 重试机制通过 `_call_with_retry` 工具函数,Engine `_retry_call` 重构为薄壳
- [ ] 重试 prompt 附加上一次 violations(`Engine._build_validate_prompt` 注入 `last_violations` 参数)
- [ ] 集成测试:Tool.output_schema 严格 → LLM 输出不符合 → 重试 → 最终通过 / 最终失败
- [ ] 向后兼容:`ToolExecutionEngine(llm, sandbox, retry_policy, repository)` 4 字段调用全部通过(Story 4.1a 测试 0 FAIL)

### AC-8: 端口注册与架构约束

**Given** 所有组件需要注册到 composition_root
**When** 注册 2 个新端口(`schema_validator` + `schema_validation_record_repository`)+ 1 个事件通道(`ToolSchemaValidationFailed`)+ 验证架构约束
**Then**

- **`composition_root.py` 注册清单**(**2 个新端口**):
  - `schema_validator`:name=`schema_validator`, version=`v1.0.0`, interface=`SchemaValidatorPort`, impl=`JsonSchemaValidatorImpl`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "schema", "validator")`
  - `schema_validation_record_repository`:name=`schema_validation_record_repository`, version=`v1.0.0`, interface=`SchemaValidationRecordRepositoryPort`, impl=`InMemorySchemaValidationRecordRepository`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "schema", "repository")`
- **`SchemaValidator` 领域服务 Python 类设计**(领域层纯函数,**非** Protocol):
  ```python
  class SchemaValidator:
      """JSON Schema 核心子集校验器(领域层纯函数服务,无状态、无依赖)

      实现 **6** 项校验规则(类型 / required / enum / items / properties),
      完整 Draft 7+ 验证能力委托 SchemaValidatorPort(应用层)。
      """

      @staticmethod
      def validate_arguments(tool: Tool, arguments: dict) -> SchemaValidationResult: ...

      @staticmethod
      def validate_output(tool: Tool, output: dict) -> SchemaValidationResult: ...
  ```
- **impl 路径用字符串实现延迟加载**(CLAUDE.md §6 Gotchas)
- **六边形架构约束**:`poetry run lint-imports` 通过
- **依赖方向矩阵合规**:domain 零依赖 → application → infrastructure → interfaces

**验证标准/Validation Criteria:**
- [ ] **2 个**新端口注册完整(`schema_validator` / `schema_validation_record_repository`);**`SchemaValidator` 领域服务**(**非** Protocol,**不**通过 composition_root 注册);**`ToolInputValidator` / `ToolOutputValidator` 是应用层服务**(**不**通过 composition_root 注册,作为可注入组件由 composition_root 装配到 `ToolExecutionService`,**非** Engine)
- [ ] PortSpec 元数据十字段完整(name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated);`compatibility=()` 表示向后兼容版本元组,`deprecated=False` 表示未废弃
- [ ] lifetime 决策合理(2 个端口均 = SCOPED)
- [ ] 端口命名空间与现有 tool_repository / tool_execution_repository / tool_chain_repository 无冲突
- [ ] 依赖注入正确(impl 字符串延迟加载)
- [ ] 架构约束验证通过(`poetry run lint-imports`)
- [ ] 架构测试 `tests/unit/architecture/test_arch_tool_io_schema_validation.py` 覆盖完整
- [ ] **`ToolExecutionService.__init__` 接收 `ToolExecutionEnginePort` Protocol 而非类**(Round 3 关键决策):保持 4.1a 既有测试 0 FAIL(`ToolExecutionEngine` 类隐式实现 Protocol),同时允许 `ToolOutputValidator` 装饰器实例注入(PEP 544 structural subtyping)
- [ ] **装饰器 Liskov Substitution 契约测试**(Round 3 关键):`isinstance(ToolOutputValidator(wrapped=engine, ...), ToolExecutionEnginePort)` 为 True;`execute()` 方法签名与 Protocol 完全一致

**`composition_root.py` 装配样板**(Round 3 关键决策):

```python
# src/composition_root.py 现有 tool_execution_service 注册(line 2255 附近)替换为:

register_port(
    name="tool_execution_service",
    version="v1.1.0",  # 升级(Protocol 参数 + 装饰器装配)
    interface=ToolExecutionServicePort,
    impl=lambda resolver: ToolExecutionService(
        registry=resolver.resolve("tool_registry_service"),
        # ToolOutputValidator 包裹 Engine(纯外包,AC-3 + AC-7 一致)
        engine=ToolOutputValidator(
            wrapped=resolver.resolve("tool_execution_engine"),
            schema_validator=resolver.resolve("schema_validator"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
    ),
    module="src.application.services.tool_execution_service",
    lifetime=Lifetime.SCOPED,
    owner="tool-team",
    tags=("tool", "execution", "service", "decorated"),
    compatibility=("v1.0.0",),  # 向后兼容 v1.0.0(ToolExecutionEngine 类仍可传入)
    deprecated=False,
)

# ToolInputValidator 不通过 composition_root 注册,仅在 use case 层组合(可选 strict/lenient 策略)
```

**`_call_with_retry` 工具函数完整签名**(Round 3 关键):

```python
# src/application/services/retry_helpers.py
from typing import Awaitable, Callable, Literal, ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")
OnFailureCallback = Callable[[Exception, int, int, bool], Awaitable[None]]
"""失败回调协议: (exception, current_attempt, max_attempts, will_retry) -> awaitable None"""

async def _call_with_retry(
    func: Callable[[], Awaitable[T]],
    retry_policy: RetryPolicy,
    on_failure_callback: OnFailureCallback | None = None,
    *,
    execution_id: str | None = None,
    tool_id: uuid.UUID | None = None,
    op_name: str = "retry_call",
) -> T:
    """带指数退避的重试调用(共享工具函数)

    Args:
        func: 无参异步函数,返回 T
        retry_policy: 4.1a 既有 RetryPolicy (max_attempts + backoff_strategy + retryable_exceptions)
        on_failure_callback: 失败回调(异常 + 当前 attempt + max + will_retry);**异常吞噬不传播**
        execution_id: 透传到 ToolExecutionRetryExhaustedError context
        tool_id: 透传到 ToolExecutionRetryExhaustedError context
        op_name: 操作名(用于日志 + metrics)
    """
```

**`on_failure_callback` 契约**(Round 3 关键):

| 时机 | 调用? | 参数 |
|------|------|------|
| 第 N 次失败(N < max_attempts) | ✅ | `(exc, N, max_attempts, will_retry=True)` |
| 第 max_attempts 次失败(最后一次) | ✅ | `(exc, max_attempts, max_attempts, will_retry=False)` |
| 重试后成功 | ❌(不调用) | — |
| 非 retryable 异常立即抛出 | ❌(不调用) | — |
| callback 自身抛异常 | ✅ 吞噬不传播,`logger.exception()` 记录 | — |

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束:** 每个 Task 必须独立完成完整的 TDD 循环(红→绿→重构),禁止将测试编写与代码实现分离。

### TDD 循环约束(适用于每个 Task)

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败,且失败原因符合预期(如 `ImportError`、`NameError`) |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码(保持测试通过) | `ruff check` + `mypy` + `pytest` 全部通过 |

**TDD 禁止行为:**
- 禁止先写代码后写测试
- 禁止将测试编写推迟到后续 Task
- 禁止跳过红阶段验证(必须有失败的 pytest 输出作为证据)

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | SchemaValidator 领域服务(纯函数 JSON Schema 校验) | Task 1 | SchemaValidator + SchemaValidationResult + SchemaViolation + **6** 项校验规则 | `tests/unit/domain/services/test_schema_validator.py` |
| AC-2 | SchemaValidatorPort 应用层端口(jsonschema 库委托) | Task 2 | SchemaValidatorPort Protocol + JsonSchemaValidatorImpl + schema_compatibility | `tests/contracts/test_port_contract_schema_validator.py` |
| AC-3 | ToolInputValidator + ToolOutputValidator 装饰器 | Task 3 | 装饰器实现 + strict/lenient + 重试机制 | `tests/unit/application/services/test_tool_input_validator.py` + `test_tool_output_validator.py` |
| AC-4 | ToolResult 状态扩展(status=invalid 语义完善) | Task 4 | ToolResult 新增 validation_violations / retry_count + EvidencePackage.validation 升级 + ToolResultValidationError 扩展 | `tests/unit/domain/value_objects/test_tool_result_validation_43.py` |
| AC-5 | SchemaValidationRecord 聚合根 + 仓储端口 | Task 5 | SchemaValidationRecord + Query + Repository + InMemory + migration 013 | `tests/contracts/test_port_contract_schema_validation_record_repository.py` |
| AC-6 | ToolSchemaValidationFailed 领域事件 + 双通道配置 | Task 6 | ToolSchemaValidationFailed event + event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS | `tests/contracts/test_event_contract_tool_schema_validation_failed.py` |
| AC-7 | 与 ToolExecutionEngine 集成(Validate 阶段增强) | Task 7 | **ToolOutputValidator(engine) 纯外包装饰** + _call_with_retry 重试 + violations 注入 prompt + Engine 源码不变 | `tests/integration/test_integration_tool_io_schema_validation.py` |
| AC-8 | 端口注册与架构约束 | Task 8 | **2 端口**注册(不含 SchemaValidator 领域服务) + PortSpec 元数据 + lint-imports | `tests/unit/architecture/test_arch_tool_io_schema_validation.py` |
| **AC-1~AC-8 收尾** | **开发结束验收测试** | **Task 9** | **src + tests 完成清单断言 + 收尾校验** | `tests/acceptance/test_acceptance_tool_io_schema_validation.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则:** 每个 Task 必须独立完成 红→绿→重构 循环,禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义(必选前置)

**关联 AC:** AC-1 ~ AC-8

> **目的:** 在进入代码实现前,明确 Schema、接口契约、验收标准、异常契约。这是 SDD 规范驱动的基础。

- [ ] Subtask: 定义 `SchemaValidator` 领域服务接口(2 方法:validate_arguments / validate_output)
- [ ] Subtask: 定义 `SchemaValidationResult` + `SchemaViolation` 值对象(2 frozen dataclass)
- [ ] Subtask: 定义 `SchemaValidatorPort` 应用层 Protocol(3 方法:validate_arguments / validate_output / validate_schema_compatibility)
- [ ] Subtask: 定义 `SchemaValidationRecord` 聚合根 Schema(11 字段)+ `SchemaValidationRecordQuery` Query 值对象
- [ ] Subtask: 定义 `SchemaValidationRecordRepositoryPort` Protocol 接口(继承 `L2RdbPort[SchemaValidationRecord]` + 扩展 list_by_query / count)
- [ ] Subtask: 定义 `ToolInputValidator` + `ToolOutputValidator` 装饰器接口(strict/lenient 策略 + retry_count)
- [ ] Subtask: 定义 `ToolSchemaValidationFailed` 领域事件 Schema(13 字段)
- [ ] Subtask: 定义 PortSpec 元数据清单(**2 个新端口**:schema_validator / schema_validation_record_repository;SchemaValidator 领域服务、ToolInputValidator/ToolOutputValidator 应用服务**不**注册端口)
- [ ] Subtask: **新增异常 4 项 Checklist 实施**(ToolInputSchemaValidationError **EXCEPTION_395** / ToolOutputSchemaValidationError EXCEPTION_396 / ToolSchemaCompatibilityError EXCEPTION_397 / ToolSchemaMissingError **EXCEPTION_398**)
- [ ] Subtask: **复用 toolchain 子域 395-398**(更新 `_code_ranges.py` 注释 + `sisys-uni-exception-design.md §3.3.2` 表)
- [ ] Subtask: **扩展 ToolResultValidationError**(EXCEPTION_389 增加 `schema_violations` 参数,向后兼容)
- [ ] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_tool_io_schema_validation.feature`
- [ ] Subtask: 编写 Gherkin 步骤实现 `tests/acceptance/test_acceptance_tool_io_schema_validation.py`
- [ ] Subtask: 运行验收测试,确认失败(🔴 红阶段验证)

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 4 个新增异常 4 项 Checklist 通过(grep 自查零输出)
- [ ] 验收测试运行失败(预期行为,红阶段确认)

---

### Task 1: SchemaValidator 领域服务(纯函数 JSON Schema 校验)

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**

#### TDD 循环 A:SchemaValidationResult + SchemaViolation 值对象

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_schema_validator.py`(验证 SchemaValidationResult 3 字段 + SchemaViolation 4 字段 + to_dict 序列化) | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/services/schema_validator.py` 实现 `SchemaValidationResult` + `SchemaViolation` | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、frozen dataclass | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 SchemaValidationResult / SchemaViolation 失败测试
- [ ] Subtask: 🟢 绿 — 实现值对象
- [ ] Subtask: 🔄 重构 — 类型注解 + docstring

#### TDD 循环 B:SchemaValidator **6** 项校验规则

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_schema_validator.py`(6 项规则测试:类型 / required / enum / items / properties) | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/services/schema_validator.py` 实现 `SchemaValidator.validate_arguments` + `validate_output`(纯函数) | `pytest` 通过 |
| 🔄 重构 | 嵌套对象递归校验 + 空 schema 兼容 + path JSON Pointer 生成 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 **6** 项校验规则失败测试
- [ ] Subtask: 🟢 绿 — 实现 SchemaValidator 静态方法
- [ ] Subtask: 🔄 重构 — 嵌套对象递归 + path 生成

**完成标准/Definition of Done:**
- [ ] SchemaValidator 实现位于 `src/domain/services/`(**纯函数**,无外部依赖)
- [ ] **6** 项校验规则完整(类型 / required / enum / items / properties)
- [ ] SchemaValidationResult 含 is_valid / violations / validated_at 三字段
- [ ] SchemaViolation 含 path / expected / actual / message 四字段
- [ ] 空 schema 返回 is_valid=True(向后兼容)
- [ ] 嵌套对象递归校验
- [ ] domain 层零依赖验证通过
- [ ] 所有测试通过
- [ ] 覆盖率 ≥90%(domain 层)

---

### Task 2: SchemaValidatorPort 应用层端口(jsonschema 库委托)

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**
>
> **依赖关系:** 依赖 Task 1(SchemaValidator 领域服务 + SchemaValidationResult + SchemaViolation)。

#### TDD 循环 A:SchemaValidatorPort Protocol

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_port_contract_schema_validator.py`(11 维度覆盖 + 3 方法签名) | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/ports/schema_validator.py` 定义 Protocol | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、Protocol 约束 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 SchemaValidatorPort 失败测试
- [ ] Subtask: 🟢 绿 — 实现 Protocol
- [ ] Subtask: 🔄 重构 — 类型注解 + Protocol 校验

#### TDD 循环 B:JsonSchemaValidatorImpl + jsonschema 库

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_jsonschema_validator.py`(验证 jsonschema ValidationError 转换 + schema_compatibility) | `pytest` 失败 |
| 🟢 绿 | 在 `src/infrastructure/validation/jsonschema_validator.py` 实现 `JsonSchemaValidatorImpl` | `pytest` 通过 |
| 🔄 重构 | jsonschema 库 PEP 561 stubs 创建(若需要)+ `validate_schema_compatibility` 兼容性检测 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 JsonSchemaValidatorImpl 失败测试
- [ ] Subtask: 🟢 绿 — 实现 jsonschema 委托 + ValidationError 转换
- [ ] Subtask: 🔄 重构 — schema_compatibility 检测 + PEP 561 stubs

**完成标准/Definition of Done:**
- [ ] SchemaValidatorPort Protocol 定义完整(3 方法)
- [ ] JsonSchemaValidatorImpl 实现完整(jsonschema Draft 7)
- [ ] validate_arguments / validate_output 正确转换 jsonschema.ValidationError → SchemaViolation
- [ ] validate_schema_compatibility 检测破坏性变更
- [ ] composition_root.py 注册 schema_validator 端口
- [ ] jsonschema 库 PEP 561 stubs 创建(若库无 py.typed)
- [ ] 端口契约测试 11 维度覆盖
- [ ] 所有测试通过

---

### Task 3: ToolInputValidator + ToolOutputValidator 装饰器

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**
>
> **依赖关系:** 依赖 Task 1 + Task 2(SchemaValidatorPort + JsonSchemaValidatorImpl)。

#### TDD 循环 A:ToolInputValidator 装饰器(strict/lenient)

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_input_validator.py`(strict 抛异常 / lenient 记录警告) | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_input_validator.py` 实现装饰器 | `pytest` 通过 |
| 🔄 重构 | 委托给内部 ToolExecutionService(strict 时抛 **EXCEPTION_395**,lenient 时打印 warning) | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 strict/lenient 失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolInputValidator
- [ ] Subtask: 🔄 重构 — 委托 + **EXCEPTION_395** 抛出

#### TDD 循环 B:ToolOutputValidator 装饰器(自动重试 + violations 反馈)

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_output_validator.py`(重试 3 次 / violations 反馈 / 最终失败抛错) | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_output_validator.py` 实现装饰器 | `pytest` 通过 |
| 🔄 重构 | 重试时 violations 注入 LLM prompt + 抽离的 `_call_with_retry` 工具函数(不依赖 Engine 私有 `_retry_call`) | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写重试失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolOutputValidator
- [ ] Subtask: 🔄 重构 — violations 反馈 LLM + retry 复用

**完成标准/Definition of Done:**
- [ ] ToolInputValidator 装饰器实现完整(strict / lenient 两种策略)
- [ ] ToolOutputValidator 装饰器实现完整(自动重试 3 次 + violations 反馈)
- [ ] 入参校验失败抛 ToolInputSchemaValidationError (**EXCEPTION_395**)
- [ ] 出参校验失败设置 ToolResult.status = INVALID
- [ ] 依赖通过端口注入
- [ ] 所有测试通过

---

### Task 4: ToolResult 状态扩展(status=invalid 语义完善)

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**
>
> **依赖关系:** 依赖 Task 1(SchemaViolation 值对象)。

#### TDD 循环 A:ToolResult 字段扩展

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_result_validation_43.py`(验证 validation_violations / retry_count + status=INVALID 时 violations 非空) | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/value_objects/tool_execution.py` 扩展 ToolResult + __post_init__ 校验 | `pytest` 通过 |
| 🔄 重构 | EvidencePackage.validation 接受 str \| dict + ToolResultValidationError 扩展 schema_violations 参数 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolResult 字段扩展失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolResult 新增字段
- [ ] Subtask: 🔄 重构 — EvidencePackage 升级 + ToolResultValidationError 扩展

**完成标准/Definition of Done:**
- [ ] ToolResult 增加 validation_violations / retry_count 两字段
- [ ] ToolResult __post_init__ 校验 status=INVALID 时 violations 非空
- [ ] EvidencePackage.validation 接受 str | dict
- [ ] ToolResultValidationError 扩展 schema_violations 参数(向后兼容)
- [ ] domain 层零依赖验证通过
- [ ] 所有测试通过
- [ ] 覆盖率 ≥90%(domain 层)

---

### Task 5: SchemaValidationRecord 聚合根 + 仓储端口 + migration 013

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**
>
> **依赖关系:** 依赖 Task 1(SchemaViolation 值对象) + Task 4(ToolResult 扩展)。

#### TDD 循环 A:SchemaValidationRecord 聚合根 + Query

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_schema_validation_record.py`(11 字段 + SchemaValidationRecordQuery + 不变量校验) | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/schema_validation_record.py` 实现聚合根 + Query | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、frozen dataclass | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 SchemaValidationRecord 失败测试
- [ ] Subtask: 🟢 绿 — 实现聚合根
- [ ] Subtask: 🔄 重构 — 不变量校验

#### TDD 循环 B:Repository 端口 + InMemory 实现 + Alembic migration 013

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_port_contract_schema_validation_record_repository.py`(11 维度 + migration 测试) | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/ports/` 定义 Protocol + `src/infrastructure/storage/inmemory/` 实现 + `013_schema_validation_records.py` migration | `pytest` 通过 |
| 🔄 重构 | asyncio.Lock 类变量测试 + GIN(violations JSONB) 索引验证 + migration downgrade 可回滚 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Repository 端口契约失败测试
- [ ] Subtask: 🟢 绿 — 实现 Protocol + InMemory + migration
- [ ] Subtask: 🔄 重构 — asyncio.Lock 类变量 + migration 回滚验证

**完成标准/Definition of Done:**
- [ ] SchemaValidationRecord 聚合根 11 字段完整
- [ ] SchemaValidationRecordQuery frozen dataclass
- [ ] SchemaValidationRecordRepositoryPort 继承 L2RdbPort[SchemaValidationRecord] + 扩展 list_by_query / count
- [ ] InMemorySchemaValidationRecordRepository 实现完整
- [ ] composition_root.py 注册 schema_validation_record_repository 端口
- [ ] Alembic migration 013 创建(含 4 索引)
- [ ] 端口契约测试 11 维度覆盖
- [ ] 所有测试通过

---

### Task 6: ToolSchemaValidationFailed 领域事件 + 双通道配置

**关联 AC:** AC-6

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**
>
> **依赖关系:** 依赖 Task 1(SchemaViolation) + Task 4(ToolResult 扩展)。

#### TDD 循环 A:ToolSchemaValidationFailed 事件定义

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_schema_validation_failed_event.py`(13 字段 + 序列化) | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/events/tool_schema_events.py` 实现事件 dataclass | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、frozen dataclass | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写事件定义失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolSchemaValidationFailed
- [ ] Subtask: 🔄 重构 — 类型注解 + 序列化

#### TDD 循环 B:双通道配置 + 装饰器集成事件发布

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_event_channel_config.py` + 装饰器事件发布测试(INPUT 阶段发布 1 次 / OUTPUT 阶段重试 3 次发布 3 次) | `pytest` 失败 |
| 🟢 绿 | 更新 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` + 装饰器内 **EventPublisher** 调用 | `pytest` 通过 |
| 🔄 重构 | 双通道投递验证测试(INPUT/OUTPUT 阶段各发布正确次数) | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写事件发布失败测试
- [ ] Subtask: 🟢 绿 — 配置双通道 + 装饰器发布
- [ ] Subtask: 🔄 重构 — 双通道投递验证

**完成标准/Definition of Done:**
- [ ] ToolSchemaValidationFailed 事件定义完整(13 字段)
- [ ] configs/event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS 同步更新
- [ ] ToolInputValidator + ToolOutputValidator 在校验失败时通过 **EventPublisher** 发布事件
- [ ] 事件契约测试覆盖(字段必填 + 序列化 + 通道双投递)
- [ ] 单元测试覆盖:INPUT 阶段发布 1 次 / OUTPUT 阶段重试 3 次发布 3 次
- [ ] 所有测试通过

---

### Task 7: 与 ToolExecutionEngine 集成(Validate 阶段增强)

**关联 AC:** AC-7

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**
>
> **依赖关系:** 依赖 Task 1-6 全部完成。

#### TDD 循环 A:ToolOutputValidator 装饰 Engine(纯外包模式)

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_output_validator_with_engine.py`(Engine 包裹 + 调用 _call_with_retry + violations 反馈 + 4.1a 向后兼容) | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_output_validator.py` 实现 `ToolOutputValidator(wrapped=engine, ...)`;**ToolExecutionEngine.__init__ 源码不变** | `pytest` 通过 |
| 🔄 重构 | 通过 `_call_with_retry(func, retry_policy, on_failure_callback)` 工具函数触发重试;Engine `_retry_call` 重构为薄壳;_build_validate_prompt 注入上轮 violations | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolOutputValidator 包裹 Engine 失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolOutputValidator 装饰器(纯外包,**不修改 Engine 源码**)
- [ ] Subtask: 🔄 重构 — 抽离 `_call_with_retry` 工具函数 + Engine `_retry_call` 薄壳化 + violations 注入 prompt

#### TDD 循环 B:集成测试(端到端 Tool 调用 + Schema 验证)

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_integration_tool_io_schema_validation.py`(完整链路:Tool 注册 → execute → schema 失败 → 重试 → 最终失败/成功) | `pytest` 失败 |
| 🟢 绿 | 全部实现 Task 完成后运行 | `pytest` 通过 |
| 🔄 重构 | 真实服务 Schema 隔离模式(savepoint rollback + 租户隔离 bucket) | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写集成测试失败测试
- [ ] Subtask: 🟢 绿 — 实现集成测试
- [ ] Subtask: 🔄 重构 — 真实服务 Schema 隔离

**完成标准/Definition of Done:**
- [ ] **`ToolExecutionEngine.__init__` 不修改**(保持 4 字段签名,**4.1a 23 种 Tool 既有测试 0 FAIL**)
- [ ] `ToolOutputValidator(engine)` 在 `composition_root.py` 装配时**替代 engine** 注入到 `ToolExecutionService`
- [ ] 重试机制通过 `_call_with_retry` 共享工具函数(`retry_helpers.py`),**Engine `_retry_call` 重构为薄壳**
- [ ] 重试 prompt 附加上一次 violations(`Engine._build_validate_prompt` 注入 `last_violations` 可选参数)
- [ ] 集成测试:Tool.output_schema 严格 → LLM 输出不符合 → 重试 → 最终通过 / 最终失败
- [ ] 向后兼容:`ToolExecutionEngine(llm, sandbox, retry_policy, repository)` 4 字段调用全部通过
- [ ] 所有测试通过

---

### Task 8: 端口注册与架构约束验证

**关联 AC:** AC-8

> ⚠️ **本 Task 包含自己的 TDD 循环,禁止将测试推迟到其他 Task。**

#### TDD 循环 A:端口注册 + PortSpec 元数据

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_arch_tool_io_schema_validation.py`(验证 **2 个**新端口注册元数据:schema_validator / schema_validation_record_repository;SchemaValidator 领域服务 + ToolInputValidator/ToolOutputValidator 应用服务**不**注册) | `pytest` 失败 |
| 🟢 绿 | 在 `src/composition_root.py` 注册 schema_validator + schema_validation_record_repository | `pytest` 通过 |
| 🔄 重构 | 验证端口注册元数据完整性 + impl 字符串延迟加载 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写端口注册失败测试
- [ ] Subtask: 🟢 绿 — 实现端口注册
- [ ] Subtask: 🔄 重构 — PortSpec 元数据完整性验证

#### TDD 循环 B:架构约束验证(lint-imports + 循环依赖检测)

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_arch_tool_io_schema_validation.py`(验证 domain 层零外部依赖 + 依赖方向矩阵合规 + 循环依赖检测) | `pytest` 失败 |
| 🟢 绿 | 运行 `poetry run lint-imports` 验证通过 + `ruff check --select E` 检测循环依赖 | 全部通过 |
| 🔄 重构 | 添加架构约束文档 + 端口命名空间澄清 | `ruff check + mypy + pytest + lint-imports` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写架构约束失败测试
- [ ] Subtask: 🟢 绿 — 验证架构约束通过
- [ ] Subtask: 🔄 重构 — 架构约束文档

#### TDD 循环 C:端口契约测试集成验证

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 2 个端口契约测试集成验证(schema_validator + schema_validation_record_repository 全部 11 维度) | `pytest` 失败 |
| 🟢 绿 | 确认所有实现满足所有维度 | `pytest` 通过 |
| 🔄 重构 | 补充 asyncio.Lock 类变量测试 + InMemory SchemaValidationRecordRepository 验证 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写端口契约集成失败测试
- [ ] Subtask: 🟢 绿 — 验证 2 端口契约完整
- [ ] Subtask: 🔄 重构 — 补充类变量测试 + InMemory 验证

**完成标准/Definition of Done:**
- [ ] **2 个**新端口注册完整(schema_validator / schema_validation_record_repository)
- [ ] PortSpec 元数据十字段完整(含 compatibility + deprecated)
- [ ] 依赖注入正确
- [ ] 架构约束验证通过(lint-imports + ruff --select E)
- [ ] 2 端口契约测试通过
- [ ] InMemorySchemaValidationRecordRepository asyncio.Lock 类变量验证通过
- [ ] Alembic migration 013 创建(含 4 索引)
- [ ] 所有测试通过

---

### Task 9: 开发结束验收测试(CLAUDE.md §5 + template.md §4.5)

**关联 AC:** AC-1 ~ AC-8

> ⚠️ **收尾验证 Task:** 全部实现 Task 完成后,进行最终验收。

#### Gherkin Scenario 清单(Round 3 新增)

> **背景(Background)**:战略工具执行服务已初始化(真实 `InMemoryToolRepository` + `ToolRegistryService` + `SchemaValidator` + `SchemaValidationRecordRepository` + Mock LLM/Sandbox 端口适配器)

| # | Scenario | 关联 AC |
|---|----------|---------|
| 1 | INPUT 校验通过 → ToolResult.status=SUCCESS | AC-1 |
| 2 | INPUT strict 校验失败 → 抛 EXCEPTION_395 + 事件发布 1 次(is_final=True) | AC-1 + AC-3 |
| 3 | INPUT lenient 校验失败 → 记录 warning + 继续执行 | AC-3 |
| 4 | 入参 type 校验失败 → violations.path = JSON Pointer | AC-1 |
| 5 | 入参 additionalProperties 拦截未声明字段 → violation | AC-1(Round 1) |
| 6 | 空 schema 向后兼容 → is_valid=True(4.1a 回归) | AC-1 |
| 7 | 嵌套对象递归校验 → violations.path 嵌套 | AC-1 |
| 8 | OUTPUT 重试成功 → 验证 prompt 注入上轮 violations | AC-3 |
| 9 | OUTPUT 重试耗尽 → ToolResult.status=FAILED + 抛 EXCEPTION_389 + 事件发布 N 次(仅最后一次 is_final=True) | AC-3 + AC-4 |
| 10 | Schema 兼容性检测破坏(required 新增) → is_compatible=False | AC-2 |
| 11 | Schema 兼容性检测兼容(类型放宽) → is_compatible=True + non_breaking_changes 非空 | AC-2 |
| 12 | SchemaValidationRecord 持久化(INPUT 失败) → list_by_query 可查 | AC-5 |
| 13 | 双租户隔离 → tenant_A 不可查 tenant_B 记录 | AC-5 |
| 14 | 事件双通道(realtime only) → 投递 1 次,reliable 不触发 | AC-6 |
| 15 | 覆盖率门禁达标 → domain ≥90% / application ≥85% / 整体 ≥80% | Task 9 |

#### BDD Mock 边界决策表(Round 3 新增)

| 组件 | 真实 / Mock | 理由 |
|------|------------|------|
| `InMemoryToolRepository` | **真实** | 4.1a 已建,无安全清理风险 |
| `ToolRegistryService` | **真实** | 纯 Python 域服务 |
| `ToolExecutionEngine` | **真实** | 核心执行引擎,严禁 Mock |
| `LLMClientPort` | **Mock** (`AsyncMock`) | 外部 API + 成本 + 非确定性输出 |
| `SandboxExecutor` | **Mock** (`AsyncMock`) | 容器化,无本地清理能力 |
| `SchemaValidatorPort` | **真实** (`JsonSchemaValidatorImpl`) | 验证逻辑是核心交付 |
| `SchemaValidationRecordRepository` | **真实** (InMemory/PG) | 聚合根持久化 |
| `EventPublisher` | **真实** (InMemory pub/sub) | 事件契约是核心交付 |
| `TestTenant` fixture | **真实** | UUID 前缀隔离,自清理 |
| `SchemaValidator` 领域服务 | **真实** | 零依赖纯函数 |

#### pytest.skip() 触发条件清单(Round 3 新增)

```python
@pytest.fixture(autouse=True)
def skip_if_services_unavailable():
    if not _is_postgres_available():
        pytest.skip("PostgreSQL 不可用,跳过真实 PG 集成验收测试")
    if not _is_redis_available():
        pytest.skip("Redis 不可用,跳过 realtime 通道验收测试")
    if not _is_rabbitmq_available():
        pytest.skip("RabbitMQ 不可用(reliable 通道本期不启用,跳过)")
```

#### TDD 循环:src + tests 完成清单断言 + 收尾校验

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_acceptance_tool_io_schema_validation.py` 收尾场景(验证 src + tests 完成清单断言) | `pytest` 失败 |
| 🟢 绿 | 全部实现 Task 完成后运行 | `pytest` 通过 |
| 🔄 重构 | 收尾校验:`poetry run pytest` + `poetry run ruff check` + `poetry run mypy` + `poetry run lint-imports` | 全部通过 |

- [ ] Subtask: 🔴 红 — 编写完成清单断言失败测试
- [ ] Subtask: 🟢 绿 — 运行所有测试套件
- [ ] Subtask: 🔄 重构 — 收尾校验(pytest + ruff + mypy + lint-imports)

**完成标准/Definition of Done:**
- [ ] src/ 完成清单断言通过(所有新建文件存在)
- [ ] tests/ 完成清单断言通过(单元/集成/契约/验收/架构 5 类全覆盖)
- [ ] `pytest` 全部通过(单元 + 集成 + 契约 + 验收)
- [ ] `ruff check` 通过
- [ ] `mypy` 通过
- [ ] `lint-imports` 通过
- [ ] **覆盖率门禁达标 + CI 强制阻断**(实际门禁位于 `.gitea/workflows/ci.yaml:248,252` + `scripts/check_coverage_gates.py` + `Makefile:271,275`,非 `pyproject.toml fail_under`):domain ≥90% / application ≥85% / 整体 ≥80%(Task 9 运行 `poetry run python scripts/check_coverage_gates.py` 验证)

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** Hexagonal Architecture(六边形架构)+ Decorator Pattern(横切关注点装饰器)
- **设计约束:**
  - 领域层零依赖(FR-AR-01)- 领域层不得依赖任何外部框架,JSON Schema 核心子集在 domain 层用 stdlib 实现
  - 依赖方向:基础设施层→应用层→基础设施层(禁止反向依赖)
  - 仓储模式(FR-AR-04)- SchemaValidationRecord 持久化通过仓储模式向领域层提供统一接口
- **技术栈:** Python 3.11+ + jsonschema 库(Draft 7,仅 application/infrastructure 层使用,domain 层用 stdlib 简化校验)
- **Decorator 模式(纯外包,Round 1 修订):** ToolInputValidator 包裹 ToolExecutionService(Service 层做入参校验,通过注入 `tool_registry` 解决 Tool 元数据获取);ToolOutputValidator 包裹 ToolExecutionEngine(Engine 层做出参校验,通过 `composition_root.py` 装配时替代 engine 注入到 Service);**重试通过抽离的 `_call_with_retry(func, retry_policy, on_failure_callback)` 共享工具函数复用**(GoF《设计模式》第 4 章 Structural Patterns + Spring AOP `@Around` 思想)

### 关键架构决策

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Story 4.3 + 4.7 + 4.6 设计协同

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Decorator 模式(纯外包,选中)** | **4.1a Engine 源码零修改**(向后兼容性最好);ToolInputValidator/ToolOutputValidator 独立可注入;失败语义通过 ToolResult.status 自然表达;重试通过抽离的 `_call_with_retry` 工具函数复用,避免 Engine `_retry_call` 私有方法访问 | 装饰器链调用栈较深(2 层装饰 + Engine);首次引入装饰器模式学习成本;Engine 私有方法需重构为薄壳 | ✅ 9/10 |
| Engine 内联验证(备选 A,已否决) | 调用栈简单 | **破坏 4.1a Engine 既有 `__init__` 4 字段签名**(增加 `output_validator` 参数),23 种 Tool 既有测试大量回归;Engine 单一职责膨胀(5 阶段 + Schema 验证违反 SRP);向后兼容性差 | 5/10 |
| Pydantic V2 全栈(备选 B,已否决) | 类型安全、IDE 提示强 | **违反 domain 层零 pydantic 依赖硬约束**(CLAUDE.md §5 + `.importlinter` 强制校验);Schema 需从 JSON Schema 双向转换为 Pydantic Model,复杂度高 | 3/10 |

**R1-R4 规则应用:**
- **R1 复用**:`Tool.input_schema / output_schema` 字段(4.1a)/ `ToolExecutionEngine._retry_call` 重试机制(4.1a,重构为薄壳调用 `_call_with_retry`)/ **`EventPublisher`**(1.3,实际类名不是 `EventBusPort`)/ `L2RdbPort[SchemaValidationRecord]` 仓储基座(1.5)
- **R2 新建**:`SchemaValidatorPort`(应用层端口,组合 jsonschema 库 + SchemaCompatibility 检测)/ `ToolInputValidator` + `ToolOutputValidator` 应用层装饰器(组合 SchemaValidator + ToolExecutionService)/ `_call_with_retry` 共享工具函数(`retry_helpers.py`)
- **R3 实现**:`JsonSchemaValidatorImpl`(infrastructure/validation)/ `InMemorySchemaValidationRecordRepository`(infrastructure/storage/inmemory)/ `ToolSchemaValidationFailedEvent`(domain events)
- **R4 适配**(本期不实现):HTTP API 端点 `POST /api/v1/tools/{tool_id}/validate-schema`(供运维手动触发 Schema 验证)

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── tool.py                    # 既有(4.1a,含 input_schema/output_schema)
│   │   ├── tool_execution.py          # 既有(4.1a)
│   │   ├── tool_chain.py              # 既有(4.2)
│   │   ├── tool_chain_run.py          # 既有(4.2)
│   │   └── schema_validation_record.py  # 新建 SchemaValidationRecord(4.3)
│   ├── events/
│   │   └── tool_schema_events.py      # 新建 ToolSchemaValidationFailed 事件(4.3)
│   ├── exceptions/
│   │   ├── tool_exceptions.py         # 既有 9 个 tool 子域异常(4.1a) + 扩展 ToolResultValidationError schema_violations 参数(4.3)
│   │   ├── tool_chain_exceptions.py   # 既有 4 个 toolchain 子域异常(4.2)
│   │   └── tool_schema_exceptions.py  # 新建 4 个 toolchain 子域异常 **EXCEPTION_395-398**(4.3)
│   ├── ports/
│   │   ├── l2_rdb.py                  # 既有 L2RdbPort[T] 基座
│   │   ├── tool_repository.py         # 既有(4.1a)
│   │   ├── tool_execution_repository.py  # 既有(4.1a)
│   │   ├── tool_chain_repository.py   # 既有(4.2)
│   │   └── schema_validation_record_repository.py  # 新建(4.3)
│   ├── services/
│   │   └── schema_validator.py        # 新建 SchemaValidator 领域服务(4.3,纯函数)
│   └── value_objects/
│       └── tool_execution.py          # 既有 ToolCall / ToolResult / EvidencePackage(4.1a) + 扩展 validation_violations / retry_count 字段(4.3)
│
├── application/
│   ├── ports/
│   │   ├── tool_execution_service.py  # 既有(4.1a)
│   │   ├── tool_execution_engine.py   # 既有(4.1a)
│   │   ├── tool_chain_service.py      # 既有(4.2)
│   │   ├── tool_chain_orchestrator.py # 既有(4.2)
│   │   └── schema_validator.py        # 新建 SchemaValidatorPort Protocol(4.3)
│   ├── services/
│   │   ├── tool_execution_engine.py   # 既有(4.1a)+ **不修改**(4.3);**`_retry_call` 重构为薄壳**调用 `_call_with_retry`(4.1a 既有 API 兼容)
│   │   ├── tool_execution_service.py  # 既有(4.1a)
│   │   ├── retry_helpers.py           # **新建**(4.3)`_call_with_retry` 共享工具函数(Engine + 装饰器共享)
│   │   ├── tool_input_validator.py    # 新建 ToolInputValidator 装饰器(4.3,包裹 ToolExecutionService)
│   │   └── tool_output_validator.py   # 新建 ToolOutputValidator 装饰器(4.3,**纯外包 Engine** + composition_root 装配时替代 engine 注入 Service)
│   └── use_cases/
│       ├── strategic_analysis.py      # 既有(4.1a)
│       └── run_tool_chain.py          # 既有(4.2)
│
├── infrastructure/
│   ├── storage/
│   │   └── inmemory/
│   │       ├── tool_repository.py             # 既有(4.1a)
│   │       ├── tool_execution_repository.py   # 既有(4.1a)
│   │       ├── tool_chain_repository.py       # 既有(4.2)
│   │       └── schema_validation_record_repository.py  # 新建(4.3)
│   ├── validation/                            # 新建子目录(4.3)
│   │   └── jsonschema_validator.py            # 新建 JsonSchemaValidatorImpl(4.3)
│   └── messaging/
│       └── channel_router.py                  # 既有 ChannelRouter(新增 ToolSchemaValidationFailed 映射 4.3)
│
├── interfaces/                                # 本期不直接修改
└── composition_root.py                        # 新增 2 个端口注册(4.3)
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [`4-2-toolchain-orchestration-dag.md`](4-2-toolchain-orchestration-dag.md)(Story 4.2,已 review)

**关键学习点:**

1. **toolchain 子域嵌套声明惯例**:Story 4.2 R1 决策"新增 toolchain 子域(390-399),嵌套于 external 但语义独立"(`4-2-toolchain-orchestration-dag.md:124-132`)。本 Story 4.3 复用**同一子域**继续分配 395-398(节省码位,延续子域语义边界),不新增 `tool_schema` 子域。

2. **5 项 Checklist 异常体系**(CLAUDE.md §5):Story 4.2 已建立"定义文件 + _code_ranges.py + __init__.py + 子域码段校验 + EXCEPTION_HTTP_MAP 表 5 项"模式。本 Story 4.3 **完全沿用此模式**,新增 4 异常仅需复用 5 项 Checklist。

3. **聚合根 frozen + Query Object 模式**:Story 4.2 `ToolChainDag` / `ToolChainRun` + `ToolChainDagQuery` / `ToolChainRunQuery`(`4-2-toolchain-orchestration-dag.md:392-405`)。本 Story 4.3 `SchemaValidationRecord` + `SchemaValidationRecordQuery` 严格对齐此模式(CLAUDE.md §4 决策规则:多字段组合 + 分页 → Query 值对象)。

4. **`L2RdbPort[T]` 继承 + async 接口约束**:Story 4.2 AC-3 确定 `ToolChainRepositoryPort` 继承 `L2RdbPort[ToolChainDag]`(async 基座)。本 Story `SchemaValidationRecordRepositoryPort` 严格对齐。

5. **InMemory Repository asyncio.Lock 类变量**:Story 4.2 AC-3 + CLAUDE.md §6 Gotchas 明确"asyncio.Lock 必须声明为类变量"(`4-2-toolchain-orchestration-dag.md:248`)。本 Story 4.3 `InMemorySchemaValidationRecordRepository` 严格遵循。

6. **ToolExecutionEngine 五阶段 + 重试机制共享**:Story 4.1a 实现 `ToolExecutionEngine._retry_call`(`tool_execution_engine.py:336`)。本 Story 4.3 抽离 `_call_with_retry(func, retry_policy, on_failure_callback)` 共享工具函数(`retry_helpers.py`),**Engine `_retry_call` 重构为薄壳**(4.1a 既有 API 兼容),**装饰器与 Engine 共享重试逻辑而非重复实现**,避免代码重复 + 保持重试语义一致性。

7. **事件双通道配置模式**:Story 4.2 AC-7 决策"ToolChainExecuted 新事件默认为双通道,同步更新 configs/event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS"(`4-2-toolchain-orchestration-dag.md:1053-1058`)。本 Story 4.3 `ToolSchemaValidationFailed` 沿用此模式。

8. **端口契约测试 11 维度样板**:Story 4.2 提供完整 11 维度样板(`4-2-toolchain-orchestration-dag.md:1274-1303`)。本 Story 4.3 2 个新端口契约测试直接复用此样板。

9. **Alembic migration 严格增量**:Story 4.2 创建 migration 012,本 Story 4.3 创建 migration 013(`schema_validation_records` 表 + 4 索引)。**禁止**修改 012 及之前已合入 migration。

10. **领域服务纯函数 vs 端口分离**:Story 4.2 AC-8 R1 决策"`ToolChainDagValidator` 是领域服务(非 Protocol,**不**通过 composition_root 注册)"(`4-2-toolchain-orchestration-dag.md:650-669`)。本 Story 4.3 `SchemaValidator` 领域服务**同样不注册端口**,与 AC-8 的"2 个新端口"严格区分。

**避免重蹈覆辙:**

- Story 4.1a Task 8 同时实现 4 端口注册 + migration + InMemoryToolRepository 修复,导致 Task 8 验收测试发现遗留 P0 项(`4-1a-strategic-tool-impl.md` 既有经验)。本 Story Task 8 严格聚焦 2 端口注册 + 架构约束,**不混入** InMemorySchemaValidationRecordRepository 并发安全(已在 Task 5 的 InMemory 实现中预先处理 asyncio.Lock)。
- Story 4.2 已注意到"AC-8 注册端口数 vs Task 8 端口数不一致"的早期误报(实际注册 3 端口但 Task 8 描述曾写 4 端口,后修正)。本 Story 4.3 严格保持 AC-8 与 Task 8 端口数完全一致(均为 2 个)。

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | claude-sonnet-4-5(建议) |
| **Version** | create-story workflow v1.0.0 |
| **Execution Date** | 2026-09-10 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-2-toolchain-orchestration-dag.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取(FR-ST-03 / Story 4.3)
- [x] 架构约束从 `architecture.md` 提取(六边形 + Decorator + L2Rdb + EventPublisher)
- [x] 前一个故事(4.2)学习经验整合(10 项关键学习 + 避免重蹈覆辙)
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] toolchain 子域复用 395-398 共 4 个新异常 6 项 Checklist 定义完毕
- [x] 2 个新端口契约定义(schema_validator / schema_validation_record_repository)+ ToolSchemaValidationFailed 事件通道定义
- [x] 6 项 JSON Schema 校验规则(类型 / required / enum / items / properties)+ jsonschema 库委托应用层端口
- [x] Decorator 模式(ToolInputValidator / ToolOutputValidator)边界明确

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-3-tool-io-schema-validation.md`(本文件)

**待创建的文件/To Be Created (Dev Story 实施):**

| 路径 | 描述 |
|------|------|
| `src/domain/services/schema_validator.py` | SchemaValidator 领域服务(纯函数 + **6** 项校验规则) |
| `src/domain/entities/schema_validation_record.py` | SchemaValidationRecord 聚合根 + SchemaValidationRecordQuery |
| `src/domain/events/tool_schema_events.py` | ToolSchemaValidationFailed 领域事件 |
| `src/domain/exceptions/tool_schema_exceptions.py` | 4 个新异常(**EXCEPTION_395/396/397/398**) |
| `src/domain/ports/schema_validation_record_repository.py` | SchemaValidationRecordRepositoryPort Protocol + Query |
| `src/application/ports/schema_validator.py` | SchemaValidatorPort Protocol |
| `src/application/services/retry_helpers.py` | **_call_with_retry(func, retry_policy, on_failure_callback)** 共享工具函数(Engine `_retry_call` 重构为薄壳) |
| `src/application/services/tool_input_validator.py` | ToolInputValidator 装饰器(strict/lenient,注入 tool_registry + event_publisher) |
| `src/application/services/tool_output_validator.py` | ToolOutputValidator 装饰器(**纯外包 Engine** + 调用 _call_with_retry + 注入 event_publisher) |
| `src/infrastructure/validation/jsonschema_validator.py` | JsonSchemaValidatorImpl(jsonschema Draft 7) |
| `src/infrastructure/storage/inmemory/schema_validation_record_repository.py` | InMemorySchemaValidationRecordRepository |
| `deploy/postgresql/alembic/versions/013_schema_validation_records.py` | migration 013 |
| `tests/unit/domain/services/test_schema_validator.py` | SchemaValidator 单元测试 |
| `tests/unit/domain/entities/test_schema_validation_record.py` | SchemaValidationRecord 单元测试 |
| `tests/unit/domain/value_objects/test_tool_result_validation_43.py` | ToolResult 字段扩展单元测试 |
| `tests/unit/application/services/test_tool_input_validator.py` | ToolInputValidator 单元测试 |
| `tests/unit/application/services/test_tool_output_validator.py` | ToolOutputValidator 单元测试 |
| `tests/unit/architecture/test_arch_tool_io_schema_validation.py` | 架构验证测试 |
| `tests/contracts/test_port_contract_schema_validator.py` | SchemaValidator 端口契约 |
| `tests/contracts/test_port_contract_schema_validation_record_repository.py` | Repository 端口契约 |
| `tests/contracts/test_event_contract_tool_schema_validation_failed.py` | 事件契约 |
| `tests/integration/test_integration_tool_io_schema_validation.py` | 集成测试 |
| `tests/acceptance/test_acceptance_tool_io_schema_validation.feature` | Gherkin 验收场景 |
| `tests/acceptance/test_acceptance_tool_io_schema_validation.py` | BDD 步骤实现 |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | `4.3` |
| **Story Key** | `4-3-tool-io-schema-validation` |
| **File** | `_bmad-output/implementation-artifacts/stories/4-3-tool-io-schema-validation.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具质量保障(Tool Quality Assurance) |
| 优先级 | P0(Epic 4 战略工具箱核心 Story,FR-ST-03) |
| 覆盖 FR | FR-ST-03(工具输入/输出 Schema 验证) |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成(Task 0-9,共 10 个 Task)
2. [x] All acceptance criteria specified 所有验收标准已定义(AC-1 ~ AC-8 共 8 个 AC)
3. [x] Architecture constraints extracted 架构约束已提取(六边形 + Decorator + 异常体系 + 双通道事件)
4. [x] Previous story learnings integrated 前一个故事(4.2)学习经验已整合(10 项关键学习)
5. [x] Sprint status synced to `ready-for-dev`

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** TBD(dev-story 完成时填写)
**审查模式:** full(Blind Hunter + Edge Case Hunter + Acceptance Auditor)

#### 需决策 Decision Needed

- [ ] TBD(dev-story 完成后填写)

#### 已修复 Patch

- [ ] TBD(dev-story 完成后填写)

#### 已推迟 Defer

- [ ] TBD(dev-story 完成后填写)

---

## 🔁 4.6/4.7 架构演进路径(Round 4 新增)

> **演进关系**:4.3 交付的 Schema 验证能力是 **4.6 工具版本管理** 与 **4.7 Validation Feedback 闭环** 的前置依赖。

### 4.6 Tool 版本管理(灰度发布/canary/blue-green)

**4.6 对 4.3 的 API 依赖契约**:

| 4.3 交付 API | 4.6 使用方式 |
|---|---|
| `SchemaValidatorPort.validate_schema_compatibility(old_schema, new_schema) -> SchemaCompatibilityResult` | 4.6 Tool 注册新版本前调用,根据 `is_compatible` 决定是否允许灰度 |
| `SchemaCompatibilityResult.breaking_changes[].severity: Literal["critical", "major", "minor"]` | 4.6 灰度策略分级:`major` 强制 canary、`minor` 直接发布、`critical` 拒绝注册 |
| `ChangeType` 枚举(8 类破坏性 + 7 类非破坏性) | 4.6 针对 `REQUIRED_FIELD_ADDED` vs `FIELD_TYPE_NARROWED` 触发不同 rollout 策略 |
| `ToolSchemaValidationFailed.schema_version` | 4.6 查询"特定 Tool 的最近校验记录"高频路径(已建 `migration 013` `(tenant_id, tool_id, validated_at DESC)` 索引) |
| `SchemaValidationRecordRepositoryPort.list_by_query(query)` | 4.6 按 `(tool_id, schema_version)` 查历史 violations,做兼容性影响面分析 |

**4.6 Story 创建时需补充的 API**(可选 P2):
- `SchemaCompatibilityResult.dry_run: bool` 标志位(发布前 dry-run,不实际修改 Tool)
- `SchemaValidatorPort.validate_compatibility_batch(versions: list[tuple[dict, dict]])` 批量校验(灰度发布前批量评估历史版本兼容性)

### 4.7 Validation Feedback 闭环(自动重试/降级/人工审核)

**4.7 对 4.3 的事件订阅契约**:

| 4.3 事件字段 | 4.7 消费方式 |
|---|---|
| `execution_id` + `validation_phase` | **去重键**(复合键),避免重复触发相同 execution 的反馈逻辑 |
| `is_final: bool` | **终止事件标记**(INPUT 失败 = True;OUTPUT 仅最后一次 = True);4.7 需实现 60s 终止确认超时机制 |
| `schema_version: str` | 4.7 重试时按 version 选择对应 schema 重新校验,**避免版本漂移** |
| `schema_violations: list[dict]` | 4.7 反馈给 LLM(自动重试)/ 人工审核(降级到人工)时直接使用 `path` + `expected` + `actual` + `message` |
| `tool_id` + ` tenant_id` | 4.7 按 (tool_id, tenant_id) 查询 `SchemaValidationRecord` 历史做可靠性评分更新 |

**4.7 异常需求预测**(占用 toolchain 子域预留码位):

| 异常类 | parent class | 用途 |
|---|---|---|
| `ValidationFeedbackRetryExhaustedError` (EXCEPTION_399) | `BusinessException` | 4.7 自动重试耗尽,降级到人工审核 |
| `ValidationFeedbackFallbackFailedError` (子域预留码位) | `BusinessException` | 4.7 备选 Tool 替换策略也失败 |
| `ValidationFeedbackHumanReviewTimeoutError` (子域预留码位) | `BusinessException` | 4.7 人工审核 SLA 超时 |
| `ValidationFeedbackCanaryConflictError` (子域预留码位) | `BusinessException` | 4.7 与 4.6 灰度 canary 策略冲突 |

> **决策**:4.7 启动时,若 ≥2 个新异常需扩展 `toolchain` 子域到 **400-409**(Round 4 决策矩阵方案 A)。

### 4.3 → 4.6 → 4.7 反馈闭环示意

```
┌─────────────────────────────────────────────────────────────────┐
│ 4.3 ToolOutputValidator                                          │
│   └─ OUTPUT 校验失败                                              │
│       └─ _call_with_retry 重试 N 次                                │
│           └─ on_failure_callback → EventPublisher                 │
│               └─ ToolSchemaValidationFailed (realtime, is_final=N)│
└──────────────────────────┬───────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4.7 ValidationFeedbackService 订阅                                │
│   └─ 去重键 (execution_id, validation_phase)                       │
│   └─ 检查 is_final,60s 超时兜底                                    │
│   └─ 触发自动重试/降级/人工审核                                     │
│       └─ 重试回到 4.3 Engine (或 4.6 新版本 Tool)                  │
└──────────────────────────┬───────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4.6 ToolRegistry (中间层)                                         │
│   └─ 灰度策略选择(canary/blue-green),按 severity 分级             │
│   └─ 必要时调用 validate_schema_compatibility 拦截破坏性发布        │
└─────────────────────────────────────────────────────────────────┘
```

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试(可选)

---

**故事版本/Story Version:** v1.4.0
**创建日期/Created:** 2026-09-10
**最后更新/Last Updated:** 2026-09-10
**更新说明/Description:**
- v1.0.0: 创建故事文件(基于 Story 4.2 设计模式 + 4 项 Checklist 异常体系 + 2 端口契约 + Decorator 模式 + jsonschema 库应用层委托 + 5 项 Schema 校验规则)
- v1.1.0 (Round 1 修订):
- v1.1.0 (Round 1 修订):
  - 修正 EXCEPTION_394 → EXCEPTION_395-398(因 394 已被 4.2 R1 ToolChainNotFoundError 占用)
  - 修正 EventBusPort → EventPublisher(实际类名)
  - 修正 exception_handlers.py:104 → :109(实际行号)
  - 修正 ChannelRouter 行号 132-137 → 54
  - 6 项校验规则(增加 additionalProperties 防 LLM 模型漂移)
  - 装饰器模式统一为"纯 Decorator 外包"(AC-3 + AC-7 一致)
  - 重试机制抽离 `_call_with_retry` 共享工具函数(避免 Engine 私有方法访问)
  - evidence_package 默认值保留 None(向后兼容)
  - 事件双通道策略调整为本期仅 realtime(reliable 延后 4.7)
  - 事件字段增加 tenant_id / schema_version / is_final(简化 4.7 订阅者去重)
  - 工作量估算 18-25 → 27-35 人天(含首次装饰器引入 + 4.1a 回归修复)
- v1.4.0 (Round 4 修订):
  - toolchain 子域 4.7 异常预留策略升级为决策矩阵(方案 A 扩 400-409 推荐)
  - 4.7 异常需求预测(ValidationFeedbackRetryExhaustedError + FallbackFailedError + HumanReviewTimeoutError + CanaryConflictError)
  - tenant_id baseline 措辞修订:"4.2 起的 toolchain 事件 baseline 必填;4.1a 历史遗留待 4.6 决策"
  - AC-6 验证清单新增 is_final 在 4.7 订阅契约(去重键 + 终止超时 + at-most-once)
  - AC-6 验证清单新增事件 payload 大小门禁(总条数 ≤10 + path 深度 ≤10 + 总大小 ≤16KB)
  - ChannelRouter 行号容差修订(±10 行)
  - 新增 "4.6/4.7 架构演进路径" 小节(API 依赖契约 + 反馈闭环示意图)
- v1.3.0 (Round 3 修订):
  - AC-2 补充 `BreakingChange` / `NonBreakingChange` / `SchemaCompatibilityResult` 值对象完整定义
  - AC-2 补充 `validate_schema_compatibility` 12 条规则清单(8 类破坏性 + 4 类非破坏性)
  - AC-1 验证清单新增 `SchemaValidator._sanitize_actual()` 完整实现(datetime/UUID/Decimal/bytes 脱敏)
  - AC-5 验证清单新增 5 条并发安全断言(asyncio.Lock 类变量 + 100 并发 save + 跨实例锁共享反例)
  - AC-8 补充 `composition_root.py` 装配样板 + `ToolExecutionService` 接收 `ToolExecutionEnginePort` Protocol 决策 + Liskov Substitution 契约测试
  - 补充 `_call_with_retry` 工具函数完整签名 + `on_failure_callback` 调用契约
  - Task 9 补充 15 个 Gherkin Scenario 清单 + BDD Mock 边界决策表 + pytest.skip() 触发条件
- v1.2.0 (Round 2 修订):
  - Task 7 全部改造为"ToolOutputValidator 纯外包 Engine"模式(AC-3 + AC-7 + Task 7 一致)
  - 文件清单新增 `src/application/services/retry_helpers.py`
  - 项目结构补 retry_helpers.py + Engine 注释修订
  - API 契约表格补 `schema_version` + `is_final` 字段(13 字段完整)
  - 子域范围 394-397 → 395-398 全面统一(3 处)
  - `_retry_call` 描述 → `_call_with_retry` 工具函数(多处)
  - "EventBus" 残留 → "EventPublisher"(Completion Notes)
  - 工作量估算 "5 类事件" → "1 类事件(13 字段)"
  - v1.0.0 changelog 修正 "6 项" → "5 项" Schema 校验规则
