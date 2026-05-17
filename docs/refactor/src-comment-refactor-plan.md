# SISYS src/ 目录代码注释重构详细设计与执行方案

**版本:** 1.1.0
**日期:** 2026-05-17
**作者:** agimtech <agimtech@126.com>
**状态:** 待执行

---

## 1. 调研总结

### 1.1 代码库规模

| 层 | 总文件数 | `__init__.py` | 实质代码文件 | 含 class 定义 | 含公共函数 |
|---|---|---|---|---|---|
| domain | 106 | 7 | 99 | 68 | 6 |
| application | 30 | 5 | 25 | 22 | 3 |
| interfaces | 8 | 3 | 5 | 4 | 4 |
| infrastructure | 150 | 22 | 128 | 118 | 5 |
| shared | 1 | 1 | 0 | 0 | 0 |
| **合计** | **295** | **38** | **257** | **212** | **18** |

### 1.2 现状评估

| 检查项 | 现状 | 达标率 |
|---|---|---|
| 模块级 docstring | 257/257 非init文件全覆盖 | 100% |
| __init__.py docstring | 33/39 覆盖 | 85% |
| 公共类 docstring | 全覆盖 | 100% |
| Google 风格 (Args/Returns) | ~200/257 文件使用 | 78% |
| 注释语言统一 | 中/英/混合三态 | **不达标** |
| 模块 Author/Copyright | **297/297 全缺，经 grep 验证为 0** | **不达标** |
| 类型注解 | 基本完整 | 98% |

### 1.3 核心问题清单

| # | 问题 | 影响范围 | 严重度 |
|---|---|---|---|
| P1 | 注释语言不统一（中/英/混合三态） | 257 文件 | **高** |
| P2 | 模块 docstring 缺少 Author/Copyright 节 | **297/297 全部缺失** | **高** |
| P3 | 中文"属性:/"字段:"替代 Google 标准 "Attributes:" | 6 文件 | 中 |
| P4 | 公共方法 docstring 缺少 Args/Returns 节 | ~35 个方法 | 中 |
| P5 | 6 个 __init__.py 缺少模块 docstring | 6 文件 | 低 |
| P6 | 废弃注释/TODO 未规范化 | 3 处 TODO + 7 处 deprecated | 低 |

---

## 2. 设计规则

### 2.0 语言冲突解决

> **已发现的规范冲突：**
> - `reference_project_rules.md` 记录"所有注释统一使用英文"
> - `sisys_code_comment_style.md` 规定"所有注释使用中文"
>
> **决策：以用户任务指令为准，统一使用中文。**

### 2.1 统一注释语言：中文

**决策：所有注释统一使用中文。**

理由：
- 项目主体、架构文档均为中文
- 用户/团队以中文为主要沟通语言
- sisys_code_comment_style.md 规范已明确"所有注释使用中文"

### 2.2 Google 风格节名标准化

| 节名 | 标准 | 当前错误用法 |
|---|---|---|
| Attributes: | Google 标准 | "属性:", "字段:" |
| Args: | Google 标准 | 无误用 |
| Returns: | Google 标准 | 无误用 |
| Raises: | Google 标准 | 无误用 |
| Yields: | Google 标准 | 无误用 |

**规则：节名用英文（Attributes/Args/Returns/Raises/Yields），节内容用中文描述。**

### 2.3 模块 docstring 标准模板

```python
"""SISYS {层名} {模块名}模块。

{一段话概述模块职责，50-120字。}

Attention:
    {仅在需要时添加，说明关键约束或使用注意事项。}

Todo:
    * {仅在需要时添加，关联 Story 编号。}

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""
```

**规则：**
- 每个模块 docstring 必须有 Author 和 Copyright 节
- Attention/Todo 仅在需要时添加
- 概述必须说明模块所属层和职责

### 2.4 类 docstring 标准

```python
class ClassName:
    """{简短描述，一句话。}

    Attributes:
        field1: {中文描述。}
        field2: {中文描述。}

    Note:
        {可选，关键使用说明。}
    """
```

**规则：**
- dataclass/冻结实体必须列出所有字段为 Attributes
- Protocol/ABC 类标注 "抽象协议" 或 "抽象基类"
- Note 仅在存在非显而易见的使用约束时添加

### 2.5 方法/函数 docstring 标准

```python
def method_name(self, param1: str, param2: int = 0) -> bool:
    """{简短描述，一句话。}

    {可选：1-2句话补充说明逻辑细节。}

    Args:
        param1: {中文描述。}
        param2: {中文描述，默认 0。}

    Returns:
        {中文描述返回值含义。}

    Raises:
        ValueError: {中文描述触发条件。}

    Example:
        >>> obj.method_name("hello")
        True
    """
```

**规则：**
- 有参数必有 Args 节；返回非 None 必有 Returns 节
- 类型注解已标注的，Args/Returns 中不重复类型
- Example 仅对公共 API 或复杂逻辑添加
- 纯 property getter（无参数、返回 self.field）可仅用一句话 docstring

### 2.6 特殊注释标记

| 标记 | 格式 | 用途 |
|---|---|---|
| TODO | `# TODO(story-XXX): 描述` | 待实现功能，关联 Story |
| FIXME | `# FIXME: 描述` | 已知缺陷 |
| HACK | `# HACK: 原因 — agimtech` | 临时方案，需标注责任人 |
| DEPRECATED | 在 docstring 中用 `.. deprecated::` | 废弃接口 |
| NOTE | `# NOTE: 描述` | 重要但非显而易见的实现细节 |

### 2.7 __init__.py 标准

有 `__all__` 定义的 `__init__.py` 必须有模块 docstring：

```python
"""SISYS {包名} 包。

提供 {简述导出的公共接口}。
"""

__all__ = [...]
```

纯空包（无导出）的 `__init__.py` 用最小 docstring：

```python
"""SISYS {包名} 包。"""
```

---

## 2.8 参考基准文件（已达标，仅缺 Author/Copyright）

以下文件注释完整、风格一致，可作为重构参考：

- `src/domain/services/memory_service.py` — 完整中文 Google 风格
- `src/application/use_cases/role_management.py` — 完整中文 Google 风格
- `src/infrastructure/security/jwt_service.py` — 完整中文 Google 风格
- `src/infrastructure/config/redis.py` — 环境变量完整列举

---

## 2.9 风险控制

1. **Pre-flight**：执行前先运行 `poetry run ruff check src/ && poetry run pytest tests/ -x`，确认基线通过
2. **增量验证**：每完成一个子包（如 2A Entities），立即运行 `ruff check` + `pytest` 验证无回归
3. **分批提交**：每个 Phase 独立 commit，便于回滚
4. **只改注释不改代码**：严禁在注释重构中夹带逻辑修改、import 调整或格式变更

---

## 3. 执行步骤

### Phase 1: __init__.py 补齐（6 文件）

> **关键修正（v1.1）**：原计划估计 ~240 文件缺 Author/Copyright，实际 grep 验证为 **297/297 全缺**。
> Author/Copyright 将在 Phase 2-6 中随注释重构一并补齐，不再单列。

- [ ] **1.1** `src/shared/__init__.py` — 添加模块 docstring
- [ ] **1.2** `src/infrastructure/messaging/__init__.py` — 添加模块 docstring
- [ ] **1.3** `src/infrastructure/messaging/adapters/__init__.py` — 添加模块 docstring
- [ ] **1.4** `src/infrastructure/messaging/retry/__init__.py` — 添加模块 docstring
- [ ] **1.5** `src/infrastructure/messaging/outbox/__init__.py` — 添加模块 docstring
- [ ] **1.6** `src/infrastructure/middleware/__init__.py` — 添加模块 docstring

### Phase 2: Domain 层注释重构（99 文件）

#### 2A. Entities（~17 文件）

- [ ] **2A.1** `src/domain/entities/agent.py` — 英→中翻译，补 Author/Copyright
- [ ] **2A.2** `src/domain/entities/audit_log.py` — 检查并补全
- [ ] **2A.3** `src/domain/entities/checkpoint.py` — 检查并补全
- [ ] **2A.4** `src/domain/entities/checkpoint_snapshot.py` — 检查并补全
- [ ] **2A.5** `src/domain/entities/cross_border_transfer.py` — 检查并补全
- [ ] **2A.6** `src/domain/entities/data_residency_policy.py` — 检查并补全
- [ ] **2A.7** `src/domain/entities/document.py` — 英→中翻译，补 Author/Copyright
- [ ] **2A.8** `src/domain/entities/external_api_whitelist.py` — 检查并补全
- [ ] **2A.9** `src/domain/entities/memory_change_history.py` — "字段:"→"Attributes:"，补全
- [ ] **2A.10** `src/domain/entities/memory_metadata.py` — 检查并补全
- [ ] **2A.11** `src/domain/entities/permission.py` — "属性:"→"Attributes:"，补 Author/Copyright
- [ ] **2A.12** `src/domain/entities/pipl_compliance_record.py` — 检查并补全
- [ ] **2A.13** `src/domain/entities/role.py` — "属性:"→"Attributes:"，补全
- [ ] **2A.14** `src/domain/entities/routing_decision_log.py` — 检查并补全
- [ ] **2A.15** `src/domain/entities/sensitive_data_result.py` — 检查并补全
- [ ] **2A.16** `src/domain/entities/strategic_plan.py` — 检查并补全
- [ ] **2A.17** `src/domain/entities/tool.py` — 检查并补全
- [ ] **2A.18** `src/domain/entities/user.py` — "属性:"→"Attributes:"，补 Author/Copyright
- [ ] **2A.19** `src/domain/entities/__init__.py` — 补全模块 docstring

#### 2B. Events（~19 文件）

- [ ] **2B.1** `src/domain/events/base.py` — 英→中翻译，补 Author/Copyright
- [ ] **2B.2** `src/domain/events/agent_events.py` — 检查并补全
- [ ] **2B.3** `src/domain/events/audit_events.py` — 检查并补全
- [ ] **2B.4** `src/domain/events/auto_execute_events.py` — 检查并补全
- [ ] **2B.5** `src/domain/events/auto_route_events.py` — 检查并补全
- [ ] **2B.6** `src/domain/events/auto_trigger_events.py` — 检查并补全
- [ ] **2B.7** `src/domain/events/checkpoint_events.py` — 检查并补全
- [ ] **2B.8** `src/domain/events/compliance_events.py` — 检查并补全
- [ ] **2B.9** `src/domain/events/correction_events.py` — 检查并补全
- [ ] **2B.10** `src/domain/events/document_events.py` — 检查并补全
- [ ] **2B.11** `src/domain/events/enums.py` — 检查并补全
- [ ] **2B.12** `src/domain/events/event_store.py` — 检查并补全
- [ ] **2B.13** `src/domain/events/heartbeat_events.py` — 检查并补全
- [ ] **2B.14** `src/domain/events/isolation_events.py` — 检查并补全
- [ ] **2B.15** `src/domain/events/listener.py` — 补 Args/Returns，补 Author/Copyright
- [ ] **2B.16** `src/domain/events/memory_events.py` — "字段:"→"Attributes:"，补全
- [ ] **2B.17** `src/domain/events/planning_events.py` — 检查并补全
- [ ] **2B.18** `src/domain/events/publish_result.py` — 检查并补全
- [ ] **2B.19** `src/domain/events/routing_events.py` — 检查并补全
- [ ] **2B.20** `src/domain/events/tool_events.py` — 检查并补全
- [ ] **2B.21** `src/domain/events/__init__.py` — 补全模块 docstring

#### 2C. Exceptions（~11 文件）

- [ ] **2C.1** `src/domain/exceptions/base_exceptions.py` — 检查并补全
- [ ] **2C.2** `src/domain/exceptions/business_exceptions.py` — 检查并补全
- [ ] **2C.3** `src/domain/exceptions/event_exceptions.py` — 检查并补全
- [ ] **2C.4** `src/domain/exceptions/external_exceptions.py` — 检查并补全
- [ ] **2C.5** `src/domain/exceptions/permission_exceptions.py` — 检查并补全
- [ ] **2C.6** `src/domain/exceptions/role_exceptions.py` — 检查并补全
- [ ] **2C.7** `src/domain/exceptions/sandbox_exceptions.py` — 检查并补全
- [ ] **2C.8** `src/domain/exceptions/service_exceptions.py` — 检查并补全
- [ ] **2C.9** `src/domain/exceptions/storage_exceptions.py` — 检查并补全
- [ ] **2C.10** `src/domain/exceptions/system_exceptions.py` — 检查并补全
- [ ] **2C.11** `src/domain/exceptions/__init__.py` — 补全模块 docstring

#### 2D. Ports（~43 文件）

- [ ] **2D.1** `src/domain/ports/audit_repository.py` — 补 Author/Copyright
- [ ] **2D.2** `src/domain/ports/audit_service.py` — 检查并补全
- [ ] **2D.3** `src/domain/ports/auth_service.py` — 检查并补全
- [ ] **2D.4** `src/domain/ports/compliance_gateway.py` — 检查并补全
- [ ] **2D.5** `src/domain/ports/connection_manager.py` — 检查并补全
- [ ] **2D.6** `src/domain/ports/contract_gate.py` — 检查并补全
- [ ] **2D.7** `src/domain/ports/cross_border_transfer_service.py` — 检查并补全
- [ ] **2D.8** `src/domain/ports/data_residency_enforcer.py` — 检查并补全
- [ ] **2D.9** `src/domain/ports/event_publisher.py` — 检查并补全
- [ ] **2D.10** `src/domain/ports/hash_router_protocol.py` — 检查并补全
- [ ] **2D.11** `src/domain/ports/health_check.py` — 检查并补全
- [ ] **2D.12** `src/domain/ports/index_manager.py` — 检查并补全
- [ ] **2D.13** `src/domain/ports/integrity.py` — 检查并补全
- [ ] **2D.14** `src/domain/ports/l0_storage.py` — 检查并补全
- [ ] **2D.15** `src/domain/ports/l1_cache.py` — 检查并补全
- [ ] **2D.16** `src/domain/ports/l2_rdb.py` — 废弃别名规范化，补全
- [ ] **2D.17** `src/domain/ports/l3_vector.py` — 检查并补全
- [ ] **2D.18** `src/domain/ports/l4_object.py` — 检查并补全
- [ ] **2D.19** `src/domain/ports/l5_graph.py` — 检查并补全
- [ ] **2D.20** `src/domain/ports/login_attempt_repository.py` — 检查并补全
- [ ] **2D.21** `src/domain/ports/memory_repository.py` — 检查并补全
- [ ] **2D.22** `src/domain/ports/outbox.py` — 检查并补全
- [ ] **2D.23** `src/domain/ports/password_validation_service.py` — 检查并补全
- [ ] **2D.24** `src/domain/ports/permission_repository.py` — 检查并补全
- [ ] **2D.25** `src/domain/ports/permission_service.py` — 检查并补全
- [ ] **2D.26** `src/domain/ports/pipl_compliance_service.py` — 检查并补全
- [ ] **2D.27** `src/domain/ports/registry.py` — 检查并补全
- [ ] **2D.28** `src/domain/ports/resolver.py` — 检查并补全
- [ ] **2D.29** `src/domain/ports/role_repository.py` — 检查并补全
- [ ] **2D.30** `src/domain/ports/sandbox_executor_protocol.py` — 检查并补全
- [ ] **2D.31** `src/domain/ports/semantic_router_protocol.py` — 检查并补全
- [ ] **2D.32** `src/domain/ports/sensitive_data_detector.py` — 检查并补全
- [ ] **2D.33** `src/domain/ports/session_storage.py` — 检查并补全
- [ ] **2D.34** `src/domain/ports/snapshot_repository_protocol.py` — 检查并补全
- [ ] **2D.35** `src/domain/ports/storage.py` — DEPRECATED 标记规范化
- [ ] **2D.36** `src/domain/ports/storage_enums.py` — 检查并补全
- [ ] **2D.37** `src/domain/ports/token_blacklist.py` — 检查并补全
- [ ] **2D.38** `src/domain/ports/unified_storage.py` — 检查并补全
- [ ] **2D.39** `src/domain/ports/unit_of_work.py` — 检查并补全
- [ ] **2D.40** `src/domain/ports/user_repository.py` — 检查并补全
- [ ] **2D.41** `src/domain/ports/user_role_repository.py` — 检查并补全
- [ ] **2D.42** `src/domain/ports/whitelist_service.py` — 检查并补全
- [ ] **2D.43** `src/domain/ports/__init__.py` — 废弃注释规范化，补全

#### 2E. Services（~5 文件）

- [ ] **2E.1** `src/domain/services/auto_execute_service.py` — 英→中翻译，补 Author/Copyright
- [ ] **2E.2** `src/domain/services/auto_route_service.py` — 检查并补全
- [ ] **2E.3** `src/domain/services/auto_trigger_service.py` — 检查并补全
- [ ] **2E.4** `src/domain/services/memory_service.py` — 补 Author/Copyright
- [ ] **2E.5** `src/domain/services/storage_tier_strategy.py` — 检查并补全

#### 2F. Value Objects（~5 文件）

- [ ] **2F.1** `src/domain/value_objects/auto_trigger_context.py` — 检查并补全
- [ ] **2F.2** `src/domain/value_objects/compliance_result.py` — 检查并补全
- [ ] **2F.3** `src/domain/value_objects/token_payload.py` — "属性:"→"Attributes:"，补全
- [ ] **2F.4** `src/domain/value_objects/udmr_task.py` — 检查并补全

### Phase 3: Application 层注释重构（25 文件）

#### 3A. Ports（~13 文件）

- [ ] **3A.1** `src/application/ports/compressor_service.py` — 补 Author/Copyright
- [ ] **3A.2** `src/application/ports/document_storage_port.py` — 检查并补全
- [ ] **3A.3** `src/application/ports/event_subscriber.py` — 检查并补全
- [ ] **3A.4** `src/application/ports/exception_metrics_port.py` — 检查并补全
- [ ] **3A.5** `src/application/ports/memory_cache_port.py` — 补 Author/Copyright
- [ ] **3A.6** `src/application/ports/memory_file_port.py` — 检查并补全
- [ ] **3A.7** `src/application/ports/memory_graph_port.py` — 检查并补全
- [ ] **3A.8** `src/application/ports/memory_vector_port.py` — 检查并补全
- [ ] **3A.9** `src/application/ports/metrics_port.py` — 检查并补全
- [ ] **3A.10** `src/application/ports/public_blackboard.py` — 检查并补全
- [ ] **3A.11** `src/application/ports/sandbox_port.py` — 检查并补全
- [ ] **3A.12** `src/application/ports/semantic_cache.py` — 检查并补全
- [ ] **3A.13** `src/application/ports/session_cache_port.py` — 检查并补全
- [ ] **3A.14** `src/application/ports/text_extractor_service.py` — 检查并补全

#### 3B. Use Cases（~5 文件）

- [ ] **3B.1** `src/application/use_cases/document_processing.py` — 英→中翻译，补全
- [ ] **3B.2** `src/application/use_cases/permission_management.py` — 补 Author/Copyright
- [ ] **3B.3** `src/application/use_cases/role_management.py` — 补 Author/Copyright
- [ ] **3B.4** `src/application/use_cases/text_processing/l1_compressor.py` — 补 Author/Copyright
- [ ] **3B.5** `src/application/use_cases/text_processing/l1_text_extractor.py` — 补全

#### 3C. Event Handlers（~6 文件）

- [ ] **3C.1** `src/application/event_handlers/auto_execute_completed_handler.py` — 检查并补全
- [ ] **3C.2** `src/application/event_handlers/auto_route_handler.py` — 检查并补全
- [ ] **3C.3** `src/application/event_handlers/auto_trigger_handler.py` — 英→中翻译，补全
- [ ] **3C.4** `src/application/event_handlers/event_dict_to_json.py` — 检查并补全
- [ ] **3C.5** `src/application/event_handlers/memory_changed_handler.py` — TODO 规范化，补全

#### 3D. Services（~1 文件）

- [ ] **3D.1** `src/application/services/unified_storage_gateway.py` — 补 Author/Copyright

### Phase 4: Interfaces 层注释重构（5 文件）

- [ ] **4.1** `src/interfaces/api/auth.py` — 补 Author/Copyright，检查补全
- [ ] **4.2** `src/interfaces/api/audit.py` — 补 Author/Copyright，检查补全
- [ ] **4.3** `src/interfaces/api/exception_handlers.py` — 补 Args 节，补全
- [ ] **4.4** `src/interfaces/api/middleware/exception_context.py` — 补 Args 节，补全
- [ ] **4.5** `src/interfaces/api/monitoring.py` — 补全

### Phase 5: Infrastructure 层注释重构（128 文件）

#### 5A. Config（~14 文件）

- [ ] **5A.1** `src/infrastructure/config/auth.py` — 检查并补全
- [ ] **5A.2** `src/infrastructure/config/auto_execute.py` — 检查并补全
- [ ] **5A.3** `src/infrastructure/config/auto_route.py` — 检查并补全
- [ ] **5A.4** `src/infrastructure/config/auto_trigger.py` — 检查并补全
- [ ] **5A.5** `src/infrastructure/config/memory.py` — 检查并补全
- [ ] **5A.6** `src/infrastructure/config/metrics.py` — 检查并补全
- [ ] **5A.7** `src/infrastructure/config/minio.py` — 检查并补全
- [ ] **5A.8** `src/infrastructure/config/neo4j.py` — 检查并补全
- [ ] **5A.9** `src/infrastructure/config/postgresql.py` — 检查并补全
- [ ] **5A.10** `src/infrastructure/config/qdrant.py` — 检查并补全
- [ ] **5A.11** `src/infrastructure/config/rabbitmq.py` — 检查并补全
- [ ] **5A.12** `src/infrastructure/config/redis.py` — 补 Author/Copyright

#### 5B. External Services / Sandbox（~2 文件）

- [ ] **5B.1** `src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py` — 检查并补全
- [ ] **5B.2** `src/infrastructure/external_services/sandbox/session_namespace_manager.py` — 检查并补全

#### 5C. Logging（~2 文件）

- [ ] **5C.1** `src/infrastructure/logging/exception_logger.py` — 检查并补全
- [ ] **5C.2** `src/infrastructure/logging/exception_metrics_impl.py` — 检查并补全

#### 5D. Messaging（~25 文件）

- [ ] **5D.1** `src/infrastructure/messaging/channel_router.py` — 补 Args/Returns（6 个方法），补全
- [ ] **5D.2** `src/infrastructure/messaging/dual_channel_event_bus.py` — 补全
- [ ] **5D.3** `src/infrastructure/messaging/error_mapper.py` — 补 Args/Returns（2 个方法），补全
- [ ] **5D.4** `src/infrastructure/messaging/event_bus_config_loader.py` — 检查并补全
- [ ] **5D.5** `src/infrastructure/messaging/event_bus_factory.py` — 检查并补全
- [ ] **5D.6** `src/infrastructure/messaging/event_store.py` — 检查并补全
- [ ] **5D.7** `src/infrastructure/messaging/inmemory_event_bus.py` — 英→中翻译，补全
- [ ] **5D.8** `src/infrastructure/messaging/message_serializer.py` — 检查并补全
- [ ] **5D.9** `src/infrastructure/messaging/rabbitmq_consumer.py` — 检查并补全
- [ ] **5D.10** `src/infrastructure/messaging/rabbitmq_event_bus.py` — 检查并补全
- [ ] **5D.11** `src/infrastructure/messaging/rabbitmq_listener.py` — 检查并补全
- [ ] **5D.12** `src/infrastructure/messaging/rabbitmq_publisher.py` — 补 Author/Copyright
- [ ] **5D.13** `src/infrastructure/messaging/redis_event_bus.py` — 检查并补全
- [ ] **5D.14** `src/infrastructure/messaging/redis_publisher.py` — 检查并补全
- [ ] **5D.15** `src/infrastructure/messaging/redis_subscriber.py` — 检查并补全
- [ ] **5D.16** `src/infrastructure/messaging/adapters/event_outbox_adapter.py` — 补 Args/Returns，补全
- [ ] **5D.17** `src/infrastructure/messaging/adapters/sqlalchemy_event_outbox_adapter.py` — 检查并补全
- [ ] **5D.18** `src/infrastructure/messaging/outbox/dead_letter_queue.py` — 补 Args/Returns，补全
- [ ] **5D.19** `src/infrastructure/messaging/outbox/inmemory_outbox.py` — 检查并补全
- [ ] **5D.20** `src/infrastructure/messaging/outbox/outbox.py` — 检查并补全
- [ ] **5D.21** `src/infrastructure/messaging/outbox/outbox_processor.py` — 补 Returns，补全
- [ ] **5D.22** `src/infrastructure/messaging/outbox/outbox_repository.py` — 补 Args/Returns（3 个方法），补全
- [ ] **5D.23** `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py` — 检查并补全
- [ ] **5D.24** `src/infrastructure/messaging/retry/checker.py` — 检查并补全
- [ ] **5D.25** `src/infrastructure/messaging/retry/dual_idempotency_checker.py` — 检查并补全
- [ ] **5D.26** `src/infrastructure/messaging/retry/redis_retry_queue.py` — 检查并补全
- [ ] **5D.27** `src/infrastructure/messaging/retry/retry_policy.py` — 检查并补全
- [ ] **5D.28** `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` — 检查并补全

#### 5E. Middleware（~1 文件）

- [ ] **5E.1** `src/infrastructure/middleware/session_middleware.py` — 检查并补全

#### 5F. Monitoring（~5 文件）

- [ ] **5F.1** `src/infrastructure/monitoring/aggregator.py` — 检查并补全
- [ ] **5F.2** `src/infrastructure/monitoring/business_metrics.py` — 补 Returns（7 个方法），补全
- [ ] **5F.3** `src/infrastructure/monitoring/event_metrics.py` — 检查并补全
- [ ] **5F.4** `src/infrastructure/monitoring/metrics_port_impl.py` — 检查并补全
- [ ] **5F.5** `src/infrastructure/monitoring/otel_config.py` — "属性:"→"Attributes:"，补全

#### 5G. Routing（~2 文件）

- [ ] **5G.1** `src/infrastructure/routing/hash_router.py` — 检查并补全
- [ ] **5G.2** `src/infrastructure/routing/semantic_router.py` — 补 Args/Returns（4 个方法），补全

#### 5H. Scheduler（~1 文件）

- [ ] **5H.1** `src/infrastructure/scheduler/heartbeat_scheduler.py` — 检查并补全

#### 5I. Security（~15 文件）

- [ ] **5I.1** `src/infrastructure/security/audit_repository_impl.py` — 检查并补全
- [ ] **5I.2** `src/infrastructure/security/audit_service_impl.py` — 检查并补全
- [ ] **5I.3** `src/infrastructure/security/auth_service_impl.py` — 检查并补全
- [ ] **5I.4** `src/infrastructure/security/compliance_gateway_impl.py` — 检查并补全
- [ ] **5I.5** `src/infrastructure/security/cross_border_transfer_service_impl.py` — 检查并补全
- [ ] **5I.6** `src/infrastructure/security/data_residency_enforcer_impl.py` — 检查并补全
- [ ] **5I.7** `src/infrastructure/security/encryption_service.py` — 补 Args/Returns（2 个方法），补全
- [ ] **5I.8** `src/infrastructure/security/jwt_service.py` — 补 Author/Copyright
- [ ] **5I.9** `src/infrastructure/security/password_validation_service.py` — 检查并补全
- [ ] **5I.10** `src/infrastructure/security/permission_middleware.py` — 检查并补全
- [ ] **5I.11** `src/infrastructure/security/permission_service_impl.py` — 检查并补全
- [ ] **5I.12** `src/infrastructure/security/pipl_compliance_service_impl.py` — 检查并补全
- [ ] **5I.13** `src/infrastructure/security/sensitive_data_detector_impl.py` — 检查并补全
- [ ] **5I.14** `src/infrastructure/security/token_blacklist.py` — 检查并补全
- [ ] **5I.15** `src/infrastructure/security/whitelist_service_impl.py` — 检查并补全

#### 5J. Storage — PostgreSQL（~17 文件）

- [ ] **5J.1** `src/infrastructure/storage/postgresql/postgresql_manager.py` — 检查并补全
- [ ] **5J.2** `src/infrastructure/storage/postgresql/session_context.py` — 检查并补全
- [ ] **5J.3** `src/infrastructure/storage/postgresql/models/audit.py` — 检查并补全
- [ ] **5J.4** `src/infrastructure/storage/postgresql/models/audit_outbox.py` — 检查并补全
- [ ] **5J.5** `src/infrastructure/storage/postgresql/models/login_attempt.py` — 检查并补全
- [ ] **5J.6** `src/infrastructure/storage/postgresql/models/memory.py` — 检查并补全
- [ ] **5J.7** `src/infrastructure/storage/postgresql/models/outbox.py` — 检查并补全
- [ ] **5J.8** `src/infrastructure/storage/postgresql/models/permission.py` — 检查并补全
- [ ] **5J.9** `src/infrastructure/storage/postgresql/models/rbac_association.py` — 检查并补全
- [ ] **5J.10** `src/infrastructure/storage/postgresql/models/role.py` — 检查并补全
- [ ] **5J.11** `src/infrastructure/storage/postgresql/models/user.py` — 检查并补全
- [ ] **5J.12** `src/infrastructure/storage/postgresql/repository/login_attempt_repository.py` — 检查并补全
- [ ] **5J.13** `src/infrastructure/storage/postgresql/repository/memory_change_history_repository.py` — 检查并补全
- [ ] **5J.14** `src/infrastructure/storage/postgresql/repository/memory_group_member_repository.py` — 检查并补全
- [ ] **5J.15** `src/infrastructure/storage/postgresql/repository/memory_metadata_repository.py` — 检查并补全
- [ ] **5J.16** `src/infrastructure/storage/postgresql/repository/permission_repository.py` — 检查并补全
- [ ] **5J.17** `src/infrastructure/storage/postgresql/repository/postgresql_adapter.py` — 废弃别名规范化，补全
- [ ] **5J.18** `src/infrastructure/storage/postgresql/repository/role_repository.py` — 检查并补全
- [ ] **5J.19** `src/infrastructure/storage/postgresql/repository/user_repository.py` — 补 Args/Returns，补全
- [ ] **5J.20** `src/infrastructure/storage/postgresql/repository/user_role_repository.py` — 检查并补全

#### 5K. Storage — Redis（~13 文件）

- [ ] **5K.1** `src/infrastructure/storage/redis/blackboard_entry.py` — 检查并补全
- [ ] **5K.2** `src/infrastructure/storage/redis/cache_entry.py` — 检查并补全
- [ ] **5K.3** `src/infrastructure/storage/redis/cleanup.py` — 检查并补全
- [ ] **5K.4** `src/infrastructure/storage/redis/key_builder.py` — 检查并补全
- [ ] **5K.5** `src/infrastructure/storage/redis/public_blackboard.py` — 检查并补全
- [ ] **5K.6** `src/infrastructure/storage/redis/redis_adapter.py` — 补方法 docstring，补全
- [ ] **5K.7** `src/infrastructure/storage/redis/redis_manager.py` — 检查并补全
- [ ] **5K.8** `src/infrastructure/storage/redis/redis_memory_cache.py` — 检查并补全
- [ ] **5K.9** `src/infrastructure/storage/redis/redis_session_cache.py` — 检查并补全
- [ ] **5K.10** `src/infrastructure/storage/redis/redis_snapshot_store.py` — 检查并补全
- [ ] **5K.11** `src/infrastructure/storage/redis/semantic_cache.py` — 检查并补全
- [ ] **5K.12** `src/infrastructure/storage/redis/session_state.py` — 检查并补全
- [ ] **5K.13** `src/infrastructure/storage/redis/session_storage.py` — 检查并补全

#### 5L. Storage — Qdrant（~6 文件）

- [ ] **5L.1** `src/infrastructure/storage/qdrant/bm25_builder.py` — 检查并补全
- [ ] **5L.2** `src/infrastructure/storage/qdrant/collection_manager.py` — 检查并补全
- [ ] **5L.3** `src/infrastructure/storage/qdrant/models.py` — 检查并补全
- [ ] **5L.4** `src/infrastructure/storage/qdrant/qdrant_adapter.py` — 补 Author/Copyright
- [ ] **5L.5** `src/infrastructure/storage/qdrant/qdrant_manager.py` — 检查并补全
- [ ] **5L.6** `src/infrastructure/storage/qdrant/qdrant_memory_vector_storage.py` — 检查并补全
- [ ] **5L.7** `src/infrastructure/storage/qdrant/vector_storage.py` — 检查并补全

#### 5M. Storage — MinIO（~9 文件）

- [ ] **5M.1** `src/infrastructure/storage/minio/bucket_manager.py` — 检查并补全
- [ ] **5M.2** `src/infrastructure/storage/minio/entities.py` — 检查并补全
- [ ] **5M.3** `src/infrastructure/storage/minio/minio_adapter.py` — 检查并补全
- [ ] **5M.4** `src/infrastructure/storage/minio/minio_document_storage.py` — 检查并补全
- [ ] **5M.5** `src/infrastructure/storage/minio/minio_manager.py` — 检查并补全
- [ ] **5M.6** `src/infrastructure/storage/minio/minio_repository.py` — 检查并补全
- [ ] **5M.7** `src/infrastructure/storage/minio/object_operations.py` — 检查并补全
- [ ] **5M.8** `src/infrastructure/storage/minio/worm_lifecycle.py` — 检查并补全

#### 5N. Storage — Neo4j（~7 文件）

- [ ] **5N.1** `src/infrastructure/storage/neo4j/graph_manager.py` — 检查并补全
- [ ] **5N.2** `src/infrastructure/storage/neo4j/graph_retriever.py` — 检查并补全
- [ ] **5N.3** `src/infrastructure/storage/neo4j/graph_storage.py` — 检查并补全
- [ ] **5N.4** `src/infrastructure/storage/neo4j/models.py` — 检查并补全
- [ ] **5N.5** `src/infrastructure/storage/neo4j/neo4j_adapter.py` — 检查并补全
- [ ] **5N.6** `src/infrastructure/storage/neo4j/neo4j_manager.py` — 检查并补全
- [ ] **5N.7** `src/infrastructure/storage/neo4j/neo4j_memory_graph_storage.py` — 检查并补全

#### 5O. Storage — FS（~4 文件）

- [ ] **5O.1** `src/infrastructure/storage/fs/file_memory_adapter.py` — 废弃方法规范化，补全
- [ ] **5O.2** `src/infrastructure/storage/fs/memory_file_storage.py` — 检查并补全
- [ ] **5O.3** `src/infrastructure/storage/fs/memory_index.py` — 检查并补全
- [ ] **5O.4** `src/infrastructure/storage/fs/memory_router.py` — 检查并补全

#### 5P. Utils（~1 文件）

- [ ] **5P.1** `src/infrastructure/utils/json_ser.py` — 英→中翻译，补 Author/Copyright

### Phase 6: 根级文件（~1 文件）

- [ ] **6.1** `src/composition_root.py` — 检查并补全

### Phase 7: 验证

- [ ] **7.1** 运行 `poetry run ruff check src/` 确认无格式问题
- [ ] **7.2** 运行 `poetry run mypy src/` 确认类型检查通过
- [ ] **7.3** 运行 `poetry run pytest tests/` 确认所有测试通过
- [ ] **7.4** 运行 `grep -rn '"""' src/ | grep -c 'Author:'` 统计 Author 覆盖率
- [ ] **7.5** 运行 `grep -rn '属性:' src/` 确认无残留中文节名
- [ ] **7.6** 运行 `grep -rn '字段:' src/` 确认无残留中文节名

---

## 4. 执行顺序建议

| 优先级 | Phase | 文件数 | 原因 |
|---|---|---|---|
| 1 | Phase 1 | 6 | 最小工作量，立即消除零覆盖 |
| 2 | Phase 2 | 99 | 领域层是核心，零依赖，改动风险最低 |
| 3 | Phase 3 | 25 | 应用层用例编排，影响面可控 |
| 4 | Phase 4 | 5 | 接口层最薄，快速完成 |
| 5 | Phase 5 | 128 | 基础设施层最大，按子包分批执行 |
| 6 | Phase 6 | 1 | 根级文件 |
| 7 | Phase 7 | — | 全量验证 |

**每个 Phase 执行策略：**
1. 按子包分批（如 2A → 2B → 2C...），每批完成后运行 `ruff check` + `pytest` 验证
2. "检查并补全" 意味着：读取文件 → 对照规范检查 → 补齐缺失项（主要是 Author/Copyright + 语言统一）
3. 翻译类任务（英→中）需完整翻译 docstring 内容，保持专业术语一致性

---

## 5. 术语一致性表

| 英文 | 中文（统一使用） |
|---|---|
| Entity | 实体 |
| Value Object | 值对象 |
| Aggregate | 聚合 |
| Domain Event | 领域事件 |
| Repository | 仓储 |
| Port | 端口 |
| Adapter | 适配器 |
| Use Case | 用例 |
| Service | 服务 |
| Protocol | 协议 |
| Handler | 处理器 |
| Middleware | 中间件 |
| Serializer | 序列化器 |
| Event Bus | 事件总线 |
| Outbox | 发件箱 |
| Dead Letter Queue | 死信队列 |
| Retry Policy | 重试策略 |
| Snapshot | 快照 |
| Checkpoint | 检查点 |
| Token | 令牌 |
| Permission | 权限 |
| Role | 角色 |
| Audit | 审计 |
| Sandbox | 沙箱 |
| Session | 会话 |
| Cache | 缓存 |
| Vector | 向量 |
| Graph | 图 |
| Object Storage | 对象存储 |

---

## 6. 修正记录

| 版本 | 修正项 | 原值 | 修正值 | 验证方法 |
|---|---|---|---|---|
| v1.1 | P2 Author/Copyright 覆盖率 | ~240 文件 | **297/297 全缺** | `grep -rn 'Author:' src/ --include='*.py'` 返回 0 |
| v1.1 | 规范语言冲突 | 未记录 | reference_project_rules.md(英文) vs style guide(中文) | 文件比对确认 |
| v1.1 | 新增风险控制章节 | 无 | Pre-flight + 增量验证 + 分批提交 + 只改注释 | — |
| v1.1 | 新增参考基准文件 | 无 | 4 个已达标文件 | 逐行验证 |
