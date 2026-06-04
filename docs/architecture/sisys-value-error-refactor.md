# ValueError → 领域异常迁移重构详细设计

**状态：** 待实施
**创建日期：** 2026-06-04
**作者：** Agimtech
**父文档：** [sisys-uni-exception-design.md](sisys-uni-exception-design.md)（§4.4 阶段四遗留任务）
**评审状态：** 待评审

### 修订历史

| 日期 | 版本 | 变更说明 | 作者 |
|------|------|---------|------|
| 2026-06-04 | v1.0 | 初始版本 | Agimtech |
| 2026-06-04 | v1.1 | 文档审查修订：修正 agent.py(8)/strategic_plan.py(10)/应用层(22) 数量；新增 §2.4.2 except ValueError 捕获站点分析；新增 §4.5.3 配置层异常链策略；新增 ADR-001 设计决策；新增 §4.6.3 validate() 返回类型差异表；增强 §6.1 监控告警风险、§6.2 回滚策略 | Agimtech |

---

## 1. 背景与动机

### 1.1 问题描述

当前系统中存在 **186 处 `raise ValueError`**（分布在 57 个源文件中），与已建立的领域异常体系并存。这导致：

| 问题 | 影响 | 严重度 |
|------|------|--------|
| **语义模糊** | ValueError 无法区分"参数格式错误"和"业务规则违反"，调用方无法按类型精确处理 | 🔴 高 |
| **错误码丢失** | ValueError 不携带 `EXCEPTION_XXX` 编码，无法精确定位监控告警 | 🔴 高 |
| **上下文缺失** | ValueError 不支持 `context` 字段，无法携带 `field_name`、`entity_id` 等调试信息 | 🟡 中 |
| **错误链断裂** | ValueError 不支持 `cause` 链，无法追溯根因异常 | 🟡 中 |
| **响应格式不统一** | 临时兜底处理器返回通用 `EXCEPTION_201`，而非具体编码 | 🟡 中 |
| **指标采集粗粒度** | 所有 ValueError 都记为 `ValueError:EXCEPTION_201`，无法区分具体失败模式 | 🟡 中 |

### 1.2 当前临时方案

`exception_handlers.py` 中已注册 `_handle_value_error` 兜底处理器，将所有 ValueError 统一映射为 HTTP 400 + `EXCEPTION_201`。这是过渡方案，迁移完成后应移除。

### 1.3 设计目标

| 目标 | 度量标准 |
|------|---------|
| 全系统 ValueError 清零 | `src/` 目录下所有 ValueError 全部迁移为领域异常 |
| 语义精确性 | 每个异常携带唯一错误码 + 领域上下文 |
| 迁移零破坏 | 所有 pytest.raises(ValueError) 同步更新，测试 100% 通过 |
| 测试覆盖率不降 | 整体 ≥80%，domain ≥90% |
| 分批可交付 | 每批独立 PR，可单独合入 |

---

## 2. 现状全面调研

### 2.1 ValueError 分布全景

```
src/ 目录 ValueError 分布（186 处）— 全部迁移
├── domain/entities/         ~51 处（9 个文件）    ← 批次 1-3：EntityValidationError / EntityStateTransitionError / EntityBusinessRuleError
├── domain/value_objects/      7 处（2 个文件）    ← 批次 4：EntityValidationError
├── domain/events/            15 处（3 个文件）    ← 批次 5：EntityValidationError
├── domain/ports/              1 处（1 个文件）    ← 批次 6：ConflictError
├── application/              22 处（6 个文件）    ← 批次 7：ValidationError
├── infrastructure/config/    36 处（9 个文件）    ← 批次 9：ConfigurationError
├── infrastructure/storage/   18 处（9 个文件）    ← 批次 8/9：ValidationError / ConfigurationError
├── infrastructure/messaging/  8 处（6 个文件）    ← 批次 8：ValidationError / ConfigurationError / InvalidStateError
├── infrastructure/saga/       5 处（3 个文件）    ← 批次 8：InvalidStateTransitionError / ValidationError / NotFoundError
├── infrastructure/其他       23 处（9 个文件）    ← 批次 8/9：ValidationError / ConfigurationError / EmbeddingAPIError

tests/ 目录（194 处 pytest.raises(ValueError)，50 个文件）— 全部同步更新
```

### 2.2 ValueError 语义分类

所有 ValueError 可归为以下六类：

| 类别 | 数量（约） | 典型消息 | 领域异常映射 |
|------|-----------|---------|-------------|
| **A. UUID 格式验证** | 8 | `"agent_id must be a valid UUID"` | `ValidationError` |
| **B. 非空字符串验证** | 8 | `"name must not be empty"` | `ValidationError` |
| **C. 枚举/类型验证** | 6 | `"role must be a valid AgentRole"` | `ValidationError` |
| **D. 数值范围验证** | 15 | `"route_score must be between 0.0 and 1.0"` | `ValidationError` |
| **E. 状态转换守卫** | 10 | `"Can only start from IDLE, current: running"` | `InvalidStateTransitionError` |
| **F. 业务约束验证** | 8 | `"total_tokens must equal prompt + completion"` | `BusinessRuleViolationError` |

### 2.3 实体 ValueError 使用模式

| 模式 | 触发时机 | 代表文件 | 数量 |
|------|---------|---------|------|
| **模式 A**：`validate()` 方法（显式调用） | 延迟校验，调用方决定何时触发 | `agent.py`、`checkpoint.py`、`tool.py` | ~35 |
| **模式 B**：`__post_init__()` 方法（自动触发） | 构造时立即校验 | `audit_log.py`、`memory_metadata.py` | ~4 |
| **模式 C**：业务方法状态守卫 | 状态转换时校验 | `agent.py`（start/complete/fail/restart/wait）、`checkpoint.py`（complete/recover） | ~10 |

### 2.4 调用方影响分析

#### 2.4.1 异常抛出侧（raise ValueError → 领域异常）

| 调用方层级 | 是否捕获实体 ValueError | 影响 |
|-----------|----------------------|------|
| `src/domain/entities/` | ❌ 不存在 `except ValueError` | 无影响，异常自然上浮 |
| `src/application/` | ❌ 不捕获实体 ValueError | 无影响 |
| `src/infrastructure/` | ❌ 不捕获实体 ValueError | 无影响 |
| `src/interfaces/api/` | ✅ 兜底处理器 `_handle_value_error` | 迁移后移除兜底 |
| `tests/` | ✅ 194 处 `pytest.raises(ValueError)` | **需全部同步修改** |

#### 2.4.2 异常捕获侧（except ValueError 站点）

全系统共 **37 处 `except ValueError`**，按迁移行为分为三类：

| 类别 | 数量 | 代表文件 | 迁移行为 |
|------|------|---------|---------|
| **A. 捕获 Python 内置 ValueError**（int/float/UUID 解析） | ~27 | `config/udmr.py`, `config/qdrant.py`, `config/neo4j.py`, `config/redis.py`, `config/auto_route.py`, `config/auto_trigger.py`, `config/minio.py`, `config/langgraph.py`, `token_payload.py` | ✅ **保留** `except ValueError`，仅修改内部的 `raise` 为 `ConfigurationError` |
| **B. 捕获被迁移的项目 ValueError**（service 调用） | ~7 | `interfaces/api/document_upload.py`（4处）, `interfaces/api/audit.py`（3处） | ⚠️ **移除整个 try/except 块**，因为 service 已直接 raise 领域异常（无需二次包装） |
| **C. 捕获外部库/混合模式 ValueError** | ~3 | `prefect_engine.py`（2处）, `monitoring/aggregator.py`, `messaging/redis_subscriber.py`, `storage/qdrant/vector_storage.py`, `document_parsing/text_parser.py`, `embedding_api_client.py` | ✅ **保留** `except ValueError`，仅修改 re-raise（如有） |

> **关键风险点**：`document_upload.py` 中 4 处 `except ValueError as e: raise ValidationError(...)` 模式——迁移后 `document_upload_service.py` 直接 raise `ValidationError`，不再经过 ValueError 通道，原有捕获代码将**静默失效**（`ValidationError` 不继承 `ValueError`）。批次 7 必须同步移除这些 try/except 块。

#### 2.4.3 总结

**关键结论**：生产代码中实体 ValueError 无任何显式 catch，仅被接口层兜底处理器拦截。迁移的破坏面集中在测试代码（194 处 `pytest.raises`）和少量 `except ValueError` 捕获站点（需分类处理）。

---

## 3. 业界最佳实践对标

### 3.1 DDD 领域验证异常模式

| 框架/实践 | 验证异常策略 | 要点 |
|-----------|-------------|------|
| **Vaughn Vernon（IDDD）** | 领域特定异常，`DomainException` 层次结构 | "验证失败是领域概念，应使用领域语言表达" |
| **Eric Evans（DDD 蓝皮书）** | 领域不变量违反使用领域异常 | "不变量是领域契约的一部分" |
| **Spring Framework** | `MethodArgumentNotValidException` → `@ExceptionHandler` | 统一拦截 + 自动 HTTP 映射 |
| **.NET DDD** | `DomainException` 层次 + FluentValidation | 验证结果对象 + 领域异常组合 |
| **Python 高质量 DDD** | 领域异常继承 `DomainError`，而非 `ValueError` | ValueError 用于"参数类型/格式"错误，领域异常用于"业务规则"错误 |

### 3.2 ValueError 的语义边界

Python 官方文档对 ValueError 的定义：

> Raised when an operation or function receives an argument that has the right type but an inappropriate value.

**ValueError 适用场景**（仅限 Python 标准库内部）：
- 数值格式转换失败：`int("abc")`（由 Python 内部抛出，非业务代码主动 raise）
- 类型构造参数无效：`datetime(year=-1)`（由 Python 内部抛出）
- 本系统**禁止主动 `raise ValueError`**——所有验证失败均使用领域异常

**领域异常适用场景**（业务层面验证）：
- 实体不变量违反：`agent_id must be UUID`
- 业务规则违反：`total_tokens must equal prompt + completion`
- 状态转换守卫：`Can only start from IDLE`

### 3.3 本系统采纳方案

**核心原则**：全系统零 ValueError——所有验证失败均使用领域异常体系，统一错误码、上下文和结构化日志。

> **业界对标**：Spring Framework 配置错误使用 `ConfigurationError`（系统异常子类），
> 而非 Java 内置 `IllegalArgumentException`。本系统 `ConfigurationError`（EXCEPTION_101）
> 已在领域异常体系中定义，正是为配置验证场景设计的。

```
领域层验证：  ValueError → EntityValidationError / EntityStateTransitionError / EntityBusinessRuleError
应用层验证：  ValueError → ValidationError（输入参数验证）/ BusinessRuleViolationError
基础设施层配置验证：ValueError → ConfigurationError（系统配置参数）
基础设施层运行时验证：ValueError → ValidationError / NotFoundError / InvalidStateError 等（按语义选择）
```

**架构合规性**：`infrastructure → domain` 依赖方向是六边形架构允许的。
当前已有 13 个 infrastructure 文件导入了 `src.domain.exceptions`（messaging 6 个、
storage/minio 4 个、security 2 个、embedding 1 个），证明此模式已广泛应用。

---

## 4. 设计方案

### 4.1 设计规则遵循

本设计严格遵循以下架构规则：

| 规则 | 本方案体现 |
|------|-----------|
| **R1**：领域层统一抽象基础端口 | 领域异常体系（`DomainError` 根类 + 三层分类）已建立，本方案为实体新增专用异常子类 |
| **R2**：应用层端口组合注入 R1 端口 | 应用层使用领域异常（`ValidationError` 等），无需引入新抽象 |
| **R3**：基础设施层实现领域端口 | `ErrorMapper`、`ExceptionHandlers` 按需扩展映射表 |
| **R4**：接口层适配外部请求 | 移除 ValueError 兜底处理器，所有异常走领域异常通道 |

### 4.2 新增实体验证异常

> **设计决策 ADR-001**：为何新增三个实体专用异常子类，而非直接用 `ValidationError` + context 区分？
>
> **背景**：`ValidationError`（EXCEPTION_201）和 `BusinessRuleViolationError`（EXCEPTION_207）已能通过 `context` dict 携带 `{"entity": "Agent", "field": "agent_id"}` 信息区分失败模式。
>
> **决策**：新增 `EntityValidationError`（242）、`EntityStateTransitionError`（243）、`EntityBusinessRuleError`（244）三个子类。
>
> **理由**：
> 1. **监控告警按错误码路由**：Grafana/Prometheus 告警规则通常按 `X-Error-Code` header（即 exception code）配置，而非 context 字段。EXCEPTION_201 涵盖 FastAPI 请求验证 + 实体不变量验证 + 应用层参数验证三种完全不同的问题域，无法按 code 区分告警。拆分后 EXCEPTION_242 专用于实体验证失败，告警可精确路由。
> 2. **EntityStateTransitionError 有独立结构价值**：继承父类 `InvalidStateTransitionError` 的 `from_status`/`to_status` 属性，提供强类型的状态信息（非通用 context dict）。
> 3. **与现有体系一致**：项目已有 `PasswordValidationError`（231）继承 `ValidationError`（201）、`BucketNameValidationError`（214）继承 `ValidationError`（201）的先例——为特定领域子域创建专用验证异常是既有模式。

#### 4.2.1 异常类设计

在 `src/domain/exceptions/business_exceptions.py` 中新增三类实体专用异常：

```python
# === 新增实体验证异常 ===

class EntityValidationError(ValidationError):
    """实体不变量验证失败.

    用于实体 validate() 方法和 __post_init__() 中的构造器守卫。
    携带具体的字段名和实体类型上下文。

    Attributes:
        code: 错误码 EXCEPTION_242
        message: 默认消息
    """
    code = "EXCEPTION_242"
    message = "Entity validation failed"


class EntityStateTransitionError(InvalidStateTransitionError):
    """实体状态转换守卫失败.

    用于实体状态机方法（start/complete/fail/restart/wait/recover 等）。
    携带 from_status、to_status 和实体类型上下文。

    继承自 InvalidStateTransitionError（EXCEPTION_208），
    保持与 Outbox 状态机异常的一致性。

    Attributes:
        code: 错误码 EXCEPTION_243
        message: 默认消息
    """
    code = "EXCEPTION_243"
    message = "Entity state transition failed"

    def __init__(
        self,
        from_status: str,
        to_status: str,
        message: str | None = None,
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(from_status, to_status, message)
```

> **注意**：父类 `InvalidStateTransitionError.__init__` 会自动生成 `"Invalid state transition: {from} -> {to}: {message}"` 格式的完整消息。当 `from_status == to_status` 时（如 "Checkpoint is already completed" → "Invalid state transition: completed -> completed: Checkpoint is already completed"），前缀信息冗余。这是当前 ValueError 消息的固有特征，子类保持兼容不引入额外转换逻辑。


class EntityBusinessRuleError(BusinessRuleViolationError):
    """实体业务规则违反.

    用于实体内部跨字段约束验证（如 total_tokens = prompt + completion）。
    携带违反的具体规则和实体上下文。

    Attributes:
        code: 错误码 EXCEPTION_244
        message: 默认消息
    """
    code = "EXCEPTION_244"
    message = "Entity business rule violation"
```

#### 4.2.2 错误码分配

| 编码 | 类名 | 继承链 | HTTP 映射 | 用途 |
|------|------|--------|----------|------|
| EXCEPTION_242 | `EntityValidationError` | `ValidationError` → `BusinessException` | 400 | 实体不变量验证（UUID/非空/枚举/数值范围） |
| EXCEPTION_243 | `EntityStateTransitionError` | `InvalidStateTransitionError` → `InvalidStateError` → `BusinessException` | 409 | 实体状态转换守卫 |
| EXCEPTION_244 | `EntityBusinessRuleError` | `BusinessRuleViolationError` → `BusinessException` | 422 | 实体跨字段业务约束 |

> **编码选择理由**：使用 24X 范围（2XX 业务异常的实体子域），与已有角色异常（22X）、权限异常（24X）同级别。242-244 编码已通过 `grep` 验证无碰撞。

#### 4.2.3 HTTP 映射表更新

在 `EXCEPTION_HTTP_MAP` 中新增三个精确映射：

```python
EXCEPTION_HTTP_MAP: dict[type[BaseException], int] = {
    # ... 已有映射 ...
    # 实体验证异常（精确映射，覆盖基类回退）
    EntityValidationError: status.HTTP_400_BAD_REQUEST,
    EntityStateTransitionError: status.HTTP_409_CONFLICT,
    EntityBusinessRuleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}
```

> **说明**：这三个映射实际上可通过 MRO 回退到基类获得正确状态码。显式声明是为了语义明确（精确映射表述了子类特化的业务含义）和文档清晰（`EXCEPTION_HTTP_MAP` 作为异常→HTTP 的完整参考）。`_get_http_status()` 的实现中精确类型匹配（`type(exc) is exc_type`）优先于 `isinstance` 回退，显式注册确保新类被优先匹配。

### 4.3 迁移映射规则

#### 4.3.1 ValueError 消息 → 领域异常映射表

每个 ValueError 按其语义映射到相应的领域异常：

> **异常消息语言策略**：当前系统存在中英文混用（领域实体层使用英文如 `"must be a valid UUID"`，配置层使用中文如 `"格式无效"`）。迁移时**保持各文件现有消息文本不变**（仅替换异常类型），避免因消息文本变化导致客户端匹配失效。统一语言为后续独立优化项。

| ValueError 消息模式 | 目标异常 | 上下文字段 |
|---------------------|---------|-----------|
| `"{field} must be a valid UUID"` | `EntityValidationError` | `{"entity": "Agent", "field": "agent_id"}` |
| `"{field} must not be empty"` | `EntityValidationError` | `{"entity": "Agent", "field": "name"}` |
| `"{field} must be a valid {EnumType}"` | `EntityValidationError` | `{"entity": "Agent", "field": "role", "expected_type": "AgentRole"}` |
| `"{field} must be between {min} and {max}"` | `EntityValidationError` | `{"entity": "RoutingDecisionLog", "field": "route_score", "constraint": "range(0.0, 1.0)"}` |
| `"{field} must be non-negative"` | `EntityValidationError` | `{"entity": "RoutingDecisionLog", "field": "cost_estimate"}` |
| `"{field} must be >= {n}"` | `EntityValidationError` | `{"entity": "Document", "field": "version"}` |
| `"Can only {action} from {state}"` | `EntityStateTransitionError` | `from_status`, `to_status` |
| `"{entity} is already {state}"` | `EntityStateTransitionError` | `from_status`, `to_status` |
| `"Cannot {action} a {state} {entity}"` | `EntityStateTransitionError` | `from_status`, `to_status` |
| `"total_tokens must equal ..."` | `EntityBusinessRuleError` | `{"rule": "token_sum_invariant"}` |
| `"current_phase must not be in completed_phases"` | `EntityBusinessRuleError` | `{"rule": "phase_not_in_completed"}` |
| `"Invalid {FIELD} value"` 或 `"FIELD must be positive"` | `ConfigurationError` | `{"field": "UDMR_LLM_TIMEOUT", "constraint": "positive"}` |
| `"FIELD 格式无效"` 或 `"FIELD 值非法"` | `ConfigurationError` | `{"field": "EMBEDDING_API_URL", "constraint": "url_format"}` |

#### 4.3.2 按文件分类的迁移方案

##### 领域实体（9 个文件，~51 处）

| 文件 | ValueError 数 | EntityValidationError | EntityStateTransitionError | EntityBusinessRuleError |
|------|-------------:|----------------------:|--------------------------:|-----------------------:|
| `agent.py` | 8 | 3（validate） | 5（start/complete/fail/restart/wait） | 0 |
| `checkpoint.py` | 5 | 3（validate） | 2（complete/recover） | 0 |
| `strategic_plan.py` | 10 | 5（validate） | 3（advance_phase/complete_phase） | 2（phase_invariant） |
| `routing_decision_log.py` | 13 | 13（validate，返回 None） | 0 | 0 |
| `document.py` | 7 | 7（validate + validate_metadata） | 0 | 0 |
| `tool.py` | 4 | 4（validate） | 0 | 0 |
| `audit_log.py` | 2 | 2（__post_init__） | 0 | 0 |
| `memory_metadata.py` | 1 | 1（__post_init__） | 0 | 0 |
| `memory_change_history.py` | 1 | 1（__post_init__） | 0 | 0 |

##### 领域值对象（2 个文件，7 处）

| 文件 | ValueError 数 | 迁移方案 |
|------|-------------:|---------|
| `token_consumption.py` | 2 | → `EntityValidationError`（数值范围验证） |
| `token_payload.py` | 5 | → `EntityValidationError`（格式验证） |

##### 领域事件（3 个文件，15 处）

| 文件 | ValueError 数 | 迁移方案 |
|------|-------------:|---------|
| `events/base.py` | 8 | → `EntityValidationError`（字段验证） |
| `events/saga_events.py` | 4 | → `EntityValidationError`（状态验证） |
| `events/audit_events.py` | 3 | → `EntityValidationError`（字段验证） |

##### 领域端口（1 个文件，1 处）

| 文件 | ValueError 数 | 迁移方案 |
|------|-------------:|---------|
| `ports/registry.py` | 1 | → `ConflictError`（端口重复注册） |

##### 应用层（6 个文件，22 处）

| 文件 | ValueError 数 | 迁移方案 |
|------|-------------:|---------|
| `document_upload_service.py` | 9 | → `ValidationError`（输入验证） |
| `dense_search_service.py` | 4 | → `ValidationError`（参数验证） |
| `orchestration_service.py` | 4 | → `ValidationError`（参数验证） |
| `l1_text_extractor.py` | 2 | → `ValidationError`（输入验证） |
| `l1_compressor.py` | 1 | → `ValidationError`（输入验证） |
| `event_dict_to_json.py` | 2 | → `ValidationError`（格式验证） |

##### 基础设施层（全部迁移）

**配置验证 → ConfigurationError**（系统级参数校验）：

| 文件 | ValueError 数 | 迁移方案 |
|------|-------------:|---------|
| `config/udmr.py` | 12 | → `ConfigurationError`（环境变量数值/格式验证） |
| `config/auto_route.py` | 5 | → `ConfigurationError`（路由配置参数验证） |
| `config/auto_trigger.py` | 4 | → `ConfigurationError`（触发器配置验证） |
| `config/qdrant.py` | 4 | → `ConfigurationError`（向量存储端口/超时验证） |
| `config/neo4j.py` | 3 | → `ConfigurationError`（图存储连接池验证） |
| `config/redis.py` | 2 | → `ConfigurationError`（缓存超时/TTL 验证） |
| `config/minio.py` | 2 | → `ConfigurationError`（对象存储超时验证） |
| `config/embedding.py` | 3 | → `ConfigurationError`（嵌入 API URL/超时验证） |
| `config/langgraph.py` | 1 | → `ConfigurationError`（LangGraph 环境变量验证） |
| `monitoring/otel_config.py` | 5 | → `ConfigurationError`（OTel 采样参数验证） |
| `monitoring/event_metrics.py` | 1 | → `ConfigurationError`（指标采样参数验证） |
| `monitoring/static_token_estimator.py` | 1 | → `ValidationError`（路由类型参数验证） |
| `storage/postgresql/postgresql_manager.py` | 1 | → `ConfigurationError`（隔离级别验证） |

**运行时技术验证 → ValidationError**：

| 文件 | ValueError 数 | 迁移方案 |
|------|-------------:|---------|
| `storage/neo4j/models.py` | 6 | → `ValidationError`（图节点属性验证） |
| `storage/redis/chunked_upload_manager.py` | 3 | → `NotFoundError` / `ConflictError` |
| `storage/qdrant/models.py` | 2 | → `ValidationError` |
| `storage/neo4j/neo4j_adapter.py` | 2 | → `ValidationError` |
| `storage/neo4j/graph_storage.py` | 1 | → `ValidationError` |
| `storage/redis/redis_snapshot_store.py` | 1 | → `ValidationError` |
| `storage/redis/semantic_cache.py` | 1 | → `ValidationError` |
| `storage/redis/cleanup.py` | 1 | → `ValidationError` |
| `messaging/dual_channel_event_bus.py` | 2 | → `InvalidStateError` |
| `messaging/inmemory_event_store.py` | 2 | → `ValidationError` |
| `messaging/inmemory_event_bus.py` | 1 | → `ValidationError` |
| `messaging/rabbitmq_consumer.py` | 1 | → `ConfigurationError` |
| `messaging/adapters/sqlalchemy_event_outbox_adapter.py` | 1 | → `ConfigurationError` |
| `messaging/adapters/event_outbox_adapter.py` | 1 | → `ConfigurationError` |
| `saga/saga_context.py` | 3 | → `InvalidStateTransitionError` / `ValidationError` |
| `saga/saga_orchestrator.py` | 1 | → `ValidationError` |
| `saga/saga_repository.py` | 1 | → `NotFoundError` |
| `document_parsing/archive_extractor.py` | 4 | → `ValidationError` / `StorageError`（注：其中 2 处为包装外部异常模式：`except zipfile.BadZipFile as e: raise ValueError(...) from e`，迁移后直接 raise `StorageError`） |
| `document_parsing/pdf_page_renderer.py` | 1 | → `ValidationError` |
| `document_parsing/_encoding.py` | 1 | → `ValidationError` |
| `agent_orch/langgraph_engine.py` | 3 | → `ValidationError` |
| `workflow/prefect_engine.py` | 2 | → `ValidationError` |
| `security/data_integrity_service_impl.py` | 1 | → `ConfigurationError` |
| `external_services/embedding/embedding_api_client.py` | 4 | → `ValidationError` / `EmbeddingAPIError` |

### 4.4 实体迁移前后对比

#### checkpoint.py 迁移示例

**迁移前**（ValueError）：
```python
def validate(self) -> bool:
    if not isinstance(self.checkpoint_id, uuid.UUID):
        raise ValueError("checkpoint_id must be a valid UUID")
    if not self.phase_identifier or not self.phase_identifier.strip():
        raise ValueError("phase_identifier must not be empty")
    if not isinstance(self.status, CheckpointStatus):
        raise ValueError("status must be a valid CheckpointStatus")
    return True

def complete(self) -> None:
    if self.status == CheckpointStatus.COMPLETED:
        raise ValueError("Checkpoint is already completed")
    ...

def recover(self, mode: RecoveryMode) -> None:
    if self.status == CheckpointStatus.COMPLETED:
        raise ValueError("Cannot recover a completed checkpoint")
    ...
```

**迁移后**（领域异常）：
```python
from src.domain.exceptions import (
    EntityValidationError,
    EntityStateTransitionError,
)

def validate(self) -> bool:
    if not isinstance(self.checkpoint_id, uuid.UUID):
        raise EntityValidationError(
            message="checkpoint_id must be a valid UUID",
            context={"entity": "Checkpoint", "field": "checkpoint_id"},
        )
    if not self.phase_identifier or not self.phase_identifier.strip():
        raise EntityValidationError(
            message="phase_identifier must not be empty",
            context={"entity": "Checkpoint", "field": "phase_identifier"},
        )
    if not isinstance(self.status, CheckpointStatus):
        raise EntityValidationError(
            message="status must be a valid CheckpointStatus",
            context={"entity": "Checkpoint", "field": "status", "expected_type": "CheckpointStatus"},
        )
    return True

def complete(self) -> None:
    if self.status == CheckpointStatus.COMPLETED:
        raise EntityStateTransitionError(
            from_status=self.status.value,
            to_status="completed",
            message="Checkpoint is already completed",
        )
    ...

def recover(self, mode: RecoveryMode) -> None:
    if self.status == CheckpointStatus.COMPLETED:
        raise EntityStateTransitionError(
            from_status=self.status.value,
            to_status="recovered",
            message="Cannot recover a completed checkpoint",
        )
    ...
```

#### agent.py 迁移示例

**迁移前**（ValueError）：
```python
def start(self) -> None:
    if self.status != AgentStatus.IDLE:
        raise ValueError(f"Can only start from IDLE, current: {self.status.value}")
    self.status = AgentStatus.RUNNING
    self.updated_at = datetime.now(UTC)
```

**迁移后**（领域异常）：
```python
def start(self) -> None:
    if self.status != AgentStatus.IDLE:
        raise EntityStateTransitionError(
            from_status=self.status.value,
            to_status=AgentStatus.RUNNING.value,
            message=f"Can only start from IDLE, current: {self.status.value}",
        )
    self.status = AgentStatus.RUNNING
    self.updated_at = datetime.now(UTC)
```

### 4.5 异常处理器变更

#### 4.5.1 移除 ValueError 兜底处理器

迁移完成后，从 `exception_handlers.py` 中移除：

```python
# 删除注册行（含 # type: ignore[arg-type] 注释）
# self._app.add_exception_handler(ValueError, self._handle_value_error)  # type: ignore[arg-type]

# 删除处理器方法
# async def _handle_value_error(self, request, exc): ...  # 已移除
```

> **关于 `# type: ignore[arg-type]`**：FastAPI 的 `add_exception_handler` 类型签名期望 `type[Exception]`，`ValueError` 作为 Python 内置异常类在某些 mypy 版本中触发类型检查误报。此注释仅服务于 ValueError 注册行——移除注册行后该注释自然消失，无需单独处理。

#### 4.5.2 配置层迁移说明

配置层 ValueError 迁移为 `ConfigurationError` 后的行为变化：

| 场景 | 迁移前（ValueError） | 迁移后（ConfigurationError） |
|------|---------------------|---------------------------|
| **启动时 fail-fast** | 未捕获 ValueError → 进程崩溃，输出纯文本 traceback | 未捕获 ConfigurationError → 进程崩溃，但携带 `EXCEPTION_101` 编码 + 结构化上下文 |
| **日志格式** | 无结构化日志 | 结构化 JSON：`{"code": "EXCEPTION_101", "context": {"field": "UDMR_LLM_TIMEOUT"}}` |
| **HTTP 请求路径** | 不会到达（启动已失败） | 不会到达（启动已失败） |
| **运维监控** | 无法按编码区分配置失败类型 | 按编码精确告警 |

> **结论**：配置层 ValueError 迁移为 ConfigurationError 是纯收益变更——即使进程启动崩溃，
> 运维也能从日志中精确识别哪个配置项、什么原因失败，而非在一大段 traceback 中搜索。

#### 4.5.3 配置层异常链统一策略

配置解析代码中 `raise ValueError(...) from e` 与 `raise ValueError(...) from None` 用法不一致。迁移时统一策略：

| 场景 | 推荐 | 理由 |
|------|------|------|
| 类型转换失败（`int()`/`float()` 解析环境变量） | `from None` | 底层 `ValueError("invalid literal for int()")` 对运维无意义，切断链可避免噪音 |
| 第三方库校验失败（如 pydantic 验证） | `from e` | 保留第三方库的错误上下文，便于排查 |
| 业务范围校验失败（如 timeout > 0） | 不包装（直接 raise ConfigurationError） | 无需异常链 |

迁移时统一应用此策略，消除 `udmr.py`、`embedding.py`、`langgraph.py` 等文件中 `from e`/`from None` 的用法不一致。

### 4.6 测试迁移方案

#### 4.6.1 测试文件修改量估算

| 测试类型 | 文件数 | 修改处数 | 修改模式 |
|---------|--------|---------|---------|
| 领域实体测试 | 9 | ~55 | `pytest.raises(ValueError)` → `pytest.raises(EntityValidationError)` 等 |
| 领域值对象测试 | 2 | ~7 | 同上 |
| 领域事件测试 | 5 | ~16 | 同上 |
| 应用层测试 | 5 | ~22 | `pytest.raises(ValueError)` → `pytest.raises(ValidationError)` |
| 基础设施测试 | 29 | ~94 | 仅迁移文件对应的测试需修改 |
| **总计** | **50** | **~194** | - |

> **注意**：另有 ~12 个测试文件包含 `isinstance(x, ValueError)` 或 `except ValueError` 模式（如 `test_hexagonal_architecture_constraints.py`、`test_audit_endpoint.py`），这些文件不在此次 `pytest.raises` 迁移范围内，但需在批次 10 清理阶段逐文件审查。

#### 4.6.3 validate() 方法返回类型差异

当前实体 `validate()` 方法存在返回类型差异：

| 实体 | validate() 返回类型 | 说明 |
|------|-------------------|------|
| `agent.py` | `-> bool` | 返回 `True` |
| `checkpoint.py` | `-> bool` | 返回 `True` |
| `strategic_plan.py` | `-> bool` | 返回 `True` |
| `document.py` | `-> bool` | 返回 `True` |
| `tool.py` | `-> bool` | 返回 `True` |
| `routing_decision_log.py` | `-> None` | **不返回值** |

迁移时**保持各文件现有签名不变**，仅替换异常类型。`routing_decision_log.validate()` 迁移后仍返回 `None`（不添加 `return True`）。

#### 4.6.2 测试迁移模板

**模式 1：不变量验证测试**
```python
# 迁移前
def test_validate_rejects_invalid_uuid():
    agent = Agent(agent_id="not-uuid", role=AgentRole.CEO, name="test")
    with pytest.raises(ValueError, match="agent_id must be a valid UUID"):
        agent.validate()

# 迁移后
def test_validate_rejects_invalid_uuid():
    agent = Agent(agent_id="not-uuid", role=AgentRole.CEO, name="test")
    with pytest.raises(EntityValidationError, match="agent_id must be a valid UUID") as exc_info:
        agent.validate()
    assert exc_info.value.context["entity"] == "Agent"
    assert exc_info.value.context["field"] == "agent_id"
```

**模式 2：状态转换测试**
```python
# 迁移前
def test_start_from_non_idle():
    agent = Agent(agent_id=uuid4(), role=AgentRole.CEO, name="test", status=AgentStatus.RUNNING)
    with pytest.raises(ValueError, match="Can only start from IDLE"):
        agent.start()

# 迁移后
def test_start_from_non_idle():
    agent = Agent(agent_id=uuid4(), role=AgentRole.CEO, name="test", status=AgentStatus.RUNNING)
    with pytest.raises(EntityStateTransitionError, match="Can only start from IDLE") as exc_info:
        agent.start()
    assert exc_info.value.from_status == "running"
    assert exc_info.value.to_status == "running"
```

**模式 3：业务规则测试**
```python
# 迁移前
def test_token_sum_invariant():
    log = RoutingDecisionLog(...)
    with pytest.raises(ValueError, match="total_tokens must equal"):
        log.validate()

# 迁移后
def test_token_sum_invariant():
    log = RoutingDecisionLog(...)
    with pytest.raises(EntityBusinessRuleError, match="total_tokens must equal") as exc_info:
        log.validate()
    assert exc_info.value.context["rule"] == "token_sum_invariant"
```

---

## 5. 迁移执行步骤

### 5.1 分批策略

按影响面和风险从低到高分批，每批一个独立 PR：

```
批次 0: 基础设施准备（新增异常类 + 映射表 + 测试工具）
    ↓
批次 1: 最小实体（tool, audit_log, memory_*）— 8 处，影响面最小
    ↓
批次 2: 中等实体（checkpoint, document）— 12 处
    ↓
批次 3: 复杂实体（agent, strategic_plan, routing_decision_log）— 30 处
    ↓
批次 4: 领域值对象（token_consumption, token_payload）— 7 处
    ↓
批次 5: 领域事件（base, saga_events, audit_events）— 15 处
    ↓
批次 6: 领域端口（registry）— 1 处
    ↓
批次 7: 应用层（document_upload, dense_search, orchestration, text_processing）— 22 处
    ↓
批次 8: 基础设施层-运行时（storage, messaging, saga, document_parsing, 其他）— ~40 处
    ↓
批次 9: 配置层与监控层（config/*, monitoring/*, storage 运行时残留）— ~47 处
    ↓
批次 10: 清理（移除 ValueError 兜底处理器 + 更新文档 + 全系统零 ValueError 验证）
```

### 5.2 详细执行步骤（含 checkbox 跟踪）

#### 批次 0：基础设施准备

- [ ] **0.1** 在 `src/domain/exceptions/business_exceptions.py` 中新增 `EntityValidationError`（EXCEPTION_242）、`EntityStateTransitionError`（EXCEPTION_243）、`EntityBusinessRuleError`（EXCEPTION_244）
- [ ] **0.2** 在 `src/domain/exceptions/__init__.py` 中添加新类的导出和 `__all__` 注册
- [ ] **0.3** 在 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 中添加三个新映射条目
- [ ] **0.4** 在 `tests/unit/domain/exceptions/` 中添加新异常类的单元测试（构造、to_dict、错误码唯一性）
- [ ] **0.5** 在 `tests/unit/interfaces/api/test_exception_handlers.py` 中添加 HTTP 映射测试
- [ ] **0.6** 运行全量测试确认无回归：`poetry run pytest tests/`

#### 批次 1：最小实体迁移

- [ ] **1.1** 迁移 `src/domain/entities/tool.py`（4 处 ValueError → EntityValidationError）
- [ ] **1.2** 迁移 `src/domain/entities/audit_log.py`（2 处 ValueError → EntityValidationError）
- [ ] **1.3** 迁移 `src/domain/entities/memory_metadata.py`（1 处 ValueError → EntityValidationError）
- [ ] **1.4** 迁移 `src/domain/entities/memory_change_history.py`（1 处 ValueError → EntityValidationError）
- [ ] **1.5** 更新对应测试文件（`test_tool.py`、`test_audit_log.py`、`test_memory_metadata.py`、`test_memory_change_history.py`）
- [ ] **1.6** 运行 `poetry run pytest tests/unit/domain/entities/ -v` 确认通过
- [ ] **1.7** 运行全量测试确认无回归

#### 批次 2：中等实体迁移

- [ ] **2.1** 迁移 `src/domain/entities/checkpoint.py`（5 处：3 EntityValidationError + 2 EntityStateTransitionError）
- [ ] **2.2** 迁移 `src/domain/entities/document.py`（7 处 EntityValidationError）
- [ ] **2.3** 更新 `test_checkpoint.py`（5 处 pytest.raises 修改 + context 断言增强）
- [ ] **2.4** 更新 `test_document.py`（6 处 pytest.raises 修改 + context 断言增强）
- [ ] **2.5** 运行 `poetry run pytest tests/unit/domain/entities/ -v`
- [ ] **2.6** 运行全量测试确认无回归

#### 批次 3：复杂实体迁移

- [ ] **3.1** 迁移 `src/domain/entities/agent.py`（8 处：3 EntityValidationError + 5 EntityStateTransitionError）
- [ ] **3.2** 迁移 `src/domain/entities/strategic_plan.py`（10 处：5 EntityValidationError + 3 EntityStateTransitionError + 2 EntityBusinessRuleError）
- [ ] **3.3** 迁移 `src/domain/entities/routing_decision_log.py`（13 处 EntityValidationError，注意：validate() 返回 None 非 bool，迁移后保持签名不变）
- [ ] **3.4** 更新 `test_agent.py`（10 处 pytest.raises 修改 + from_status/to_status 断言增强）
- [ ] **3.5** 更新 `test_strategic_plan.py`（15 处 pytest.raises 修改）
- [ ] **3.6** 更新 `test_routing_decision_log.py`（18 处 pytest.raises 修改）
- [ ] **3.7** 运行 `poetry run pytest tests/unit/domain/entities/ -v`
- [ ] **3.8** 运行全量测试确认无回归

#### 批次 4：领域值对象迁移

- [ ] **4.1** 迁移 `src/domain/value_objects/token_consumption.py`（2 处 EntityValidationError）
- [ ] **4.2** 迁移 `src/domain/value_objects/token_payload.py`（5 处 EntityValidationError）
- [ ] **4.3** 更新 `test_token_consumption.py`（2 处）
- [ ] **4.4** 更新 `test_token_payload.py`（5 处）
- [ ] **4.5** 运行 `poetry run pytest tests/unit/domain/value_objects/ -v`
- [ ] **4.6** 运行全量测试确认无回归

#### 批次 5：领域事件迁移

- [ ] **5.1** 迁移 `src/domain/events/base.py`（8 处 EntityValidationError）
- [ ] **5.2** 迁移 `src/domain/events/saga_events.py`（4 处 EntityValidationError）
- [ ] **5.3** 迁移 `src/domain/events/audit_events.py`（3 处 EntityValidationError）
- [ ] **5.4** 更新 `test_events_base.py`（9 处）
- [ ] **5.5** 更新 `test_saga_events.py`（4 处）
- [ ] **5.6** 更新 `test_audit_events.py`（2 处）
- [ ] **5.7** 更新 `test_event_serialization.py`（2 处）
- [ ] **5.8** 更新 `test_event_publisher.py`（1 处）
- [ ] **5.9** 运行 `poetry run pytest tests/unit/domain/events/ -v`
- [ ] **5.10** 运行全量测试确认无回归

#### 批次 6：领域端口迁移

- [ ] **6.1** 迁移 `src/domain/ports/registry.py`（1 处 ValueError → ConflictError）
- [ ] **6.2** 确认 `tests/` 中对应的 `pytest.raises(ValueError)` 并更新
- [ ] **6.3** 运行 `poetry run pytest tests/ -v -k registry`

#### 批次 7：应用层迁移

- [ ] **7.1** 迁移 `src/application/services/document_upload_service.py`（9 处 ValueError → ValidationError）
- [ ] **7.2** 迁移 `src/application/services/dense_search_service.py`（4 处 ValueError → ValidationError）
- [ ] **7.3** 迁移 `src/application/services/orchestration_service.py`（4 处 ValueError → ValidationError）
- [ ] **7.4** 迁移 `src/application/use_cases/text_processing/l1_text_extractor.py`（2 处 ValueError → ValidationError）
- [ ] **7.5** 迁移 `src/application/use_cases/text_processing/l1_compressor.py`（1 处 ValueError → ValidationError）
- [ ] **7.6** 迁移 `src/application/event_handlers/event_dict_to_json.py`（2 处 ValueError → ValidationError）
- [ ] **7.7** 更新对应测试文件（~22 处 pytest.raises 修改）
- [ ] **7.8** **移除** `src/interfaces/api/document_upload.py` 中 4 处 `except ValueError as e: raise ValidationError(...)` 的间接捕获块——迁移后 service 直接 raise `ValidationError`（不经过 ValueError 通道），原有捕获代码静默失效，整个 try/except 块应删除
- [ ] **7.9** 检查 `src/interfaces/api/audit.py` 中 3 处 `except ValueError`（行200/234/259），确认迁移后是否需要修改（审计端点捕获的是 Python 内置 ValueError，不涉及此次迁移的异常类型）
- [ ] **7.10** 运行 `poetry run pytest tests/unit/application/ -v`
- [ ] **7.11** 运行全量测试确认无回归

#### 批次 8：基础设施层-运行时迁移

- [ ] **8.1** 迁移 `src/infrastructure/storage/neo4j/models.py`（6 处 → ValidationError）
- [ ] **8.2** 迁移 `src/infrastructure/storage/redis/chunked_upload_manager.py`（3 处 → NotFoundError / ConflictError）
- [ ] **8.3** 迁移 `src/infrastructure/storage/qdrant/models.py`（2 处 → ValidationError）
- [ ] **8.4** 迁移 `src/infrastructure/storage/neo4j/neo4j_adapter.py`（2 处 → ValidationError）
- [ ] **8.5** 迁移 `src/infrastructure/messaging/dual_channel_event_bus.py`（2 处 → InvalidStateError）
- [ ] **8.6** 迁移 `src/infrastructure/messaging/inmemory_event_store.py`（2 处 → ValidationError）
- [ ] **8.7** 迁移 `src/infrastructure/messaging/inmemory_event_bus.py`（1 处 → ValidationError）
- [ ] **8.8** 迁移 `src/infrastructure/messaging/rabbitmq_consumer.py`（1 处 → ConfigurationError）
- [ ] **8.9** 迁移 `src/infrastructure/messaging/adapters/sqlalchemy_event_outbox_adapter.py`（1 处 → ConfigurationError）
- [ ] **8.10** 迁移 `src/infrastructure/messaging/adapters/event_outbox_adapter.py`（1 处 → ConfigurationError）
- [ ] **8.11** 迁移 `src/infrastructure/saga/saga_context.py`（3 处 → InvalidStateTransitionError / ValidationError）
- [ ] **8.12** 迁移 `src/infrastructure/saga/saga_orchestrator.py`（1 处 → ValidationError）
- [ ] **8.13** 迁移 `src/infrastructure/saga/saga_repository.py`（1 处 → NotFoundError）
- [ ] **8.14** 迁移 `src/infrastructure/document_parsing/archive_extractor.py`（4 处 → ValidationError / StorageError）
- [ ] **8.15** 迁移 `src/infrastructure/document_parsing/pdf_page_renderer.py`（1 处 → ValidationError）
- [ ] **8.16** 迁移 `src/infrastructure/document_parsing/_encoding.py`（1 处 → ValidationError）
- [ ] **8.17** 迁移 `src/infrastructure/agent_orch/langgraph_engine.py`（3 处 → ValidationError）
- [ ] **8.18** 迁移 `src/infrastructure/workflow/prefect_engine.py`（2 处 → ValidationError）
- [ ] **8.19** 迁移 `src/infrastructure/security/data_integrity_service_impl.py`（1 处 → ConfigurationError）
- [ ] **8.20** 迁移 `src/infrastructure/external_services/embedding/embedding_api_client.py`（4 处 → ValidationError / EmbeddingAPIError）
- [ ] **8.21** 更新对应测试文件（~60 处 pytest.raises 修改）
- [ ] **8.22** 运行 `poetry run pytest tests/unit/infrastructure/ -v`
- [ ] **8.23** 运行全量测试确认无回归

#### 批次 9：配置层与监控层迁移

- [ ] **9.1** 迁移 `src/infrastructure/config/udmr.py`（12 处 ValueError → ConfigurationError，携带 `{"field": "UDMR_LLM_TIMEOUT"}` 等上下文）
- [ ] **9.2** 迁移 `src/infrastructure/config/auto_route.py`（5 处 → ConfigurationError）
- [ ] **9.3** 迁移 `src/infrastructure/config/auto_trigger.py`（4 处 → ConfigurationError）
- [ ] **9.4** 迁移 `src/infrastructure/config/qdrant.py`（4 处 → ConfigurationError）
- [ ] **9.5** 迁移 `src/infrastructure/config/neo4j.py`（3 处 → ConfigurationError）
- [ ] **9.6** 迁移 `src/infrastructure/config/redis.py`（2 处 → ConfigurationError）
- [ ] **9.7** 迁移 `src/infrastructure/config/minio.py`（2 处 → ConfigurationError）
- [ ] **9.8** 迁移 `src/infrastructure/config/embedding.py`（3 处 → ConfigurationError）
- [ ] **9.9** 迁移 `src/infrastructure/config/langgraph.py`（1 处 → ConfigurationError）
- [ ] **9.10** 迁移 `src/infrastructure/monitoring/otel_config.py`（5 处 → ConfigurationError）
- [ ] **9.11** 迁移 `src/infrastructure/monitoring/event_metrics.py`（1 处 → ConfigurationError）
- [ ] **9.12** 迁移 `src/infrastructure/monitoring/static_token_estimator.py`（1 处 → ValidationError）
- [ ] **9.13** 迁移 `src/infrastructure/storage/redis/semantic_cache.py`（1 处 → ValidationError）
- [ ] **9.14** 迁移 `src/infrastructure/storage/redis/redis_snapshot_store.py`（1 处 → ValidationError）
- [ ] **9.15** 迁移 `src/infrastructure/storage/redis/cleanup.py`（1 处 → ValidationError）
- [ ] **9.16** 迁移 `src/infrastructure/storage/neo4j/graph_storage.py`（1 处 → ValidationError）
- [ ] **9.17** 迁移 `src/infrastructure/storage/postgresql/postgresql_manager.py`（1 处 → ConfigurationError）
- [ ] **9.18** 更新配置层测试文件（`test_udmr_config.py` ~13 处、`test_route_config.py` ~7 处、`test_auto_trigger_config.py` ~5 处、`test_qdrant_config.py` ~4 处、`test_neo4j_config.py` ~3 处、`test_redis_config_extension.py` ~2 处、`test_minio_config.py` ~1 处、`test_langgraph_config.py` ~1 处）
- [ ] **9.19** 更新监控层测试文件（`test_event_monitoring.py` ~7 处、`test_static_token_estimator.py` ~2 处）
- [ ] **9.20** 运行 `poetry run pytest tests/unit/infrastructure/config/ tests/unit/infrastructure/monitoring/ -v`
- [ ] **9.21** 运行全量测试确认无回归

#### 批次 10：清理与收尾

- [ ] **10.1** 确认全系统零 ValueError：`grep -r "raise ValueError" src/` 返回空
- [ ] **10.2** 确认测试零 ValueError 断言：`grep -r "pytest.raises(ValueError)" tests/` 返回空
- [ ] **10.3** 从 `exception_handlers.py` 移除 `_handle_value_error` 方法和注册
- [ ] **10.4** 移除 `# type: ignore[arg-type]` 注释（如注册行已删除）
- [ ] **10.5** 运行错误码唯一性测试：`poetry run pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v`
- [ ] **10.6** 运行覆盖率检查：`poetry run pytest --cov=src tests/`
- [ ] **10.7** 运行 import-linter 检查：`poetry run lint-imports`
- [ ] **10.8** 更新 `sisys-uni-exception-design.md`：更新 §3.1 层次图、§3.7 编码注册表、§4.4 阶段四任务状态
- [ ] **10.9** 更新监控告警规则：实体状态转换告警从匹配 `EXCEPTION_208` 扩展为匹配 `EXCEPTION_208,EXCEPTION_243`（或使用编码前缀 `EXCEPTION_24*`）
- [ ] **10.10** 运行全量测试最终确认：`poetry run pytest tests/`
- [ ] **10.11** 更新本设计文档状态为"已完成"

---

## 6. 风险评估与缓解

### 6.1 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 测试修改遗漏导致 CI 失败 | 🟡 中 | 🟡 中 | 每批全量测试 + grep 验证 |
| 异常消息格式变化影响客户端 | 🟢 低 | 🔴 高 | 消息文本保持不变，仅类型和上下文变化 |
| 错误码碰撞 | 🟢 低 | 🟡 中 | 批次 0 预先验证 + 唯一性测试 |
| 配置层迁移引入启动时崩溃格式变化 | 🟢 低 | 🟡 中 | ConfigurationError 继承 Exception，traceback 格式不变；仅增加 code/context 元数据 |
| 并行开发冲突 | 🟡 中 | 🟡 中 | 每批独立 PR，顺序合入 |
| 监控告警规则未同步更新（EXCEPTION_243 替换 208） | 🟡 中 | 🟡 中 | 批次 0 发布时通知运维更新告警规则：实体状态转换告警从匹配 `EXCEPTION_208` 改为匹配 `EXCEPTION_243`（或同时匹配两者）；如使用编码前缀匹配（`EXCEPTION_24*`），验证 243-244 已被纳入 |

### 6.2 回滚策略

每个批次为独立 PR，如发现问题可单独回滚。回滚方法：

```bash
git revert <commit-hash>  # 回滚特定批次
```

**依赖约束**：
- 批次 0 的异常类新增是后续批次的前置依赖，如需回滚批次 0 需先回滚所有后续批次
- 批次 1-9 之间无硬依赖，可独立回滚

**部分回滚场景**：
- 如批次 N 被回滚但批次 N+1 已合入：先回滚 N+1，再回滚 N，然后修复 N 后重新提交 N+1（可能需要 rebase）
- 推荐在批次 N 全量测试通过且部署验证 24 小时后再合入批次 N+1，降低连锁回滚风险

**merge conflict 预处理**：每批次基于上一批次的 HEAD 提交（而非 main），通过 rebase 保持线性历史，减少跨批次冲突。

---

## 7. 验收标准

| # | 标准 | 验证方法 |
|---|------|---------|
| AC-1 | 全系统零 ValueError | `grep -r "raise ValueError" src/` 返回空 |
| AC-2 | 测试零 ValueError 断言 | `grep -r "pytest.raises(ValueError)" tests/` 返回空 |
| AC-3 | 所有 3 个新异常类已导出 | `python -c "from src.domain.exceptions import EntityValidationError, EntityStateTransitionError, EntityBusinessRuleError"` |
| AC-4 | 错误码唯一 | `poetry run pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v` 通过 |
| AC-5 | ValueError 兜底处理器已移除 | `grep "_handle_value_error" src/interfaces/api/exception_handlers.py` 返回空 |
| AC-6 | 全量测试通过 | `poetry run pytest tests/` 全绿 |
| AC-7 | 覆盖率门禁通过 | 整体 ≥80%，domain ≥90%，application ≥85% |
| AC-8 | import-linter 通过 | `poetry run lint-imports` 无违规 |
| AC-9 | 异常处理器集成测试通过 | ValueError 不再返回结构化响应；领域异常返回正确 HTTP 状态码 + 错误码 |
| AC-10 | 设计文档更新完成 | `sisys-uni-exception-design.md` §3.1/§3.7/§4.4 已同步更新 |
| AC-11 | 监控告警规则已同步 | 实体状态转换告警已更新为匹配 EXCEPTION_243（含 208 兼容） |

---

## 8. 文件变更清单

### 新增文件

无新增文件。新增的异常类添加到已有模块 `business_exceptions.py` 中。

### 修改文件

#### 批次 0（基础设施）

| 文件 | 操作 | 变更说明 |
|------|------|---------|
| `src/domain/exceptions/business_exceptions.py` | 修改 | 新增 EntityValidationError/EntityStateTransitionError/EntityBusinessRuleError |
| `src/domain/exceptions/__init__.py` | 修改 | 新增 3 个导出 + __all__ 注册 |
| `src/interfaces/api/exception_handlers.py` | 修改 | EXCEPTION_HTTP_MAP 新增 3 个映射 |
| `tests/unit/domain/exceptions/test_error_code_uniqueness.py` | 修改 | 新增编码验证 |

#### 批次 1-3（领域实体）

| 文件 | 操作 | ValueError → 领域异常数量 |
|------|------|--------------------------|
| `src/domain/entities/tool.py` | 修改 | 4 处 |
| `src/domain/entities/audit_log.py` | 修改 | 2 处 |
| `src/domain/entities/memory_metadata.py` | 修改 | 1 处 |
| `src/domain/entities/memory_change_history.py` | 修改 | 1 处 |
| `src/domain/entities/checkpoint.py` | 修改 | 5 处 |
| `src/domain/entities/document.py` | 修改 | 7 处 |
| `src/domain/entities/agent.py` | 修改 | 8 处 |
| `src/domain/entities/strategic_plan.py` | 修改 | 10 处 |
| `src/domain/entities/routing_decision_log.py` | 修改 | 13 处 |
| 对应 9 个测试文件 | 修改 | ~55 处 pytest.raises 修改 |

#### 批次 4（值对象）

| 文件 | 操作 | 数量 |
|------|------|------|
| `src/domain/value_objects/token_consumption.py` | 修改 | 2 处 |
| `src/domain/value_objects/token_payload.py` | 修改 | 5 处 |
| 对应测试文件 | 修改 | 7 处 |

#### 批次 5（领域事件）

| 文件 | 操作 | 数量 |
|------|------|------|
| `src/domain/events/base.py` | 修改 | 8 处 |
| `src/domain/events/saga_events.py` | 修改 | 4 处 |
| `src/domain/events/audit_events.py` | 修改 | 3 处 |
| 对应测试文件 | 修改 | 16 处 |

#### 批次 6-7（端口 + 应用层）

| 文件 | 操作 | 数量 |
|------|------|------|
| `src/domain/ports/registry.py` | 修改 | 1 处 |
| `src/application/services/document_upload_service.py` | 修改 | 9 处 |
| `src/application/services/dense_search_service.py` | 修改 | 4 处 |
| `src/application/services/orchestration_service.py` | 修改 | 4 处 |
| `src/application/use_cases/text_processing/l1_text_extractor.py` | 修改 | 2 处 |
| `src/application/use_cases/text_processing/l1_compressor.py` | 修改 | 1 处 |
| `src/application/event_handlers/event_dict_to_json.py` | 修改 | 2 处 |
| `src/interfaces/api/document_upload.py` | 修改 | 移除 4 处 `except ValueError` 间接捕获块 |
| 对应测试文件 | 修改 | ~22 处 |

#### 批次 8（基础设施层-运行时）

| 文件 | 操作 | 数量 |
|------|------|------|
| `src/infrastructure/storage/neo4j/models.py` | 修改 | 6 处 |
| `src/infrastructure/storage/redis/chunked_upload_manager.py` | 修改 | 3 处 |
| `src/infrastructure/storage/qdrant/models.py` | 修改 | 2 处 |
| `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 修改 | 2 处 |
| `src/infrastructure/messaging/dual_channel_event_bus.py` | 修改 | 2 处 |
| `src/infrastructure/messaging/inmemory_event_store.py` | 修改 | 2 处 |
| `src/infrastructure/messaging/inmemory_event_bus.py` | 修改 | 1 处 |
| `src/infrastructure/messaging/rabbitmq_consumer.py` | 修改 | 1 处 |
| `src/infrastructure/messaging/adapters/sqlalchemy_event_outbox_adapter.py` | 修改 | 1 处 |
| `src/infrastructure/messaging/adapters/event_outbox_adapter.py` | 修改 | 1 处 |
| `src/infrastructure/saga/saga_context.py` | 修改 | 3 处 |
| `src/infrastructure/saga/saga_orchestrator.py` | 修改 | 1 处 |
| `src/infrastructure/saga/saga_repository.py` | 修改 | 1 处 |
| `src/infrastructure/document_parsing/archive_extractor.py` | 修改 | 4 处 |
| `src/infrastructure/document_parsing/pdf_page_renderer.py` | 修改 | 1 处 |
| `src/infrastructure/document_parsing/_encoding.py` | 修改 | 1 处 |
| `src/infrastructure/agent_orch/langgraph_engine.py` | 修改 | 3 处 |
| `src/infrastructure/workflow/prefect_engine.py` | 修改 | 2 处 |
| `src/infrastructure/security/data_integrity_service_impl.py` | 修改 | 1 处 |
| `src/infrastructure/external_services/embedding/embedding_api_client.py` | 修改 | 4 处 |
| 对应测试文件 | 修改 | ~60 处 |

#### 批次 9（配置层与监控层）

| 文件 | 操作 | 数量 |
|------|------|------|
| `src/infrastructure/config/udmr.py` | 修改 | 12 处 |
| `src/infrastructure/config/auto_route.py` | 修改 | 5 处 |
| `src/infrastructure/config/auto_trigger.py` | 修改 | 4 处 |
| `src/infrastructure/config/qdrant.py` | 修改 | 4 处 |
| `src/infrastructure/config/neo4j.py` | 修改 | 3 处 |
| `src/infrastructure/config/redis.py` | 修改 | 2 处 |
| `src/infrastructure/config/minio.py` | 修改 | 2 处 |
| `src/infrastructure/config/embedding.py` | 修改 | 3 处 |
| `src/infrastructure/config/langgraph.py` | 修改 | 1 处 |
| `src/infrastructure/monitoring/otel_config.py` | 修改 | 5 处 |
| `src/infrastructure/monitoring/event_metrics.py` | 修改 | 1 处 |
| `src/infrastructure/monitoring/static_token_estimator.py` | 修改 | 1 处 |
| `src/infrastructure/storage/redis/semantic_cache.py` | 修改 | 1 处 |
| `src/infrastructure/storage/redis/redis_snapshot_store.py` | 修改 | 1 处 |
| `src/infrastructure/storage/redis/cleanup.py` | 修改 | 1 处 |
| `src/infrastructure/storage/neo4j/graph_storage.py` | 修改 | 1 处 |
| `src/infrastructure/storage/postgresql/postgresql_manager.py` | 修改 | 1 处 |
| 对应测试文件 | 修改 | ~44 处 |

#### 批次 10（清理）

| 文件 | 操作 | 变更说明 |
|------|------|---------|
| `src/interfaces/api/exception_handlers.py` | 修改 | 移除 _handle_value_error + 注册 |
| `docs/architecture/sisys-uni-exception-design.md` | 修改 | 更新 §3.1/§3.7/§4.4 |
| `docs/architecture/sisys-value-error-refactor.md` | 修改 | 状态改为"已完成" |

---

## 9. 参考资料

- [sisys-uni-exception-design.md](sisys-uni-exception-design.md) — 统一异常处理设计（父文档）
- [architecture.md](architecture.md) §13.2 — 领域层目录结构
- [Python Exception Hierarchy](https://docs.python.org/3/library/exceptions.html) — ValueError 语义定义
- Vaughn Vernon《实现领域驱动设计》第 5 章 — 领域异常设计原则
- Eric Evans《领域驱动设计》第 6 章 — 不变量验证策略
