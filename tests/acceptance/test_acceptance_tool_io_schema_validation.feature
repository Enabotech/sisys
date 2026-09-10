# language: zh-CN
# Story 4.3 — 工具输入/输出 Schema 验证(BDD 验收场景,完整覆盖 8 条 AC)

功能: 工具输入/输出 Schema 验证
  作为战略工具平台的质量工程师
  我希望在 Tool 调用前/后对输入/输出数据做 JSON Schema 契约化校验
  以便工具输出符合预期格式,防止 LLM 模型漂移导致的脏数据污染下游分析

  背景:
    假如战略工具执行服务已初始化包含真实仓储与 Schema 验证器

  # ============================================================================
  # AC-1: SchemaValidator 领域服务(纯函数 JSON Schema 校验)
  # ============================================================================

  场景: AC-1.1 - INPUT 校验通过(类型 + 必填字段全部匹配)
    当调用 SchemaValidator 校验合法 arguments
    那么返回 is_valid 等于 True

  场景: AC-1.2 - INPUT 类型校验失败(number 期望 string)
    当调用 SchemaValidator 校验非法 arguments 含 name 字段类型不匹配
    那么返回 is_valid 等于 False

  场景: AC-1.3 - INPUT additionalProperties 拦截未声明字段
    当调用 SchemaValidator 校验 arguments 含 schema 未声明字段
    那么返回 is_valid 等于 False

  场景: AC-1.4 - 空 schema 向后兼容(4.1a 回归)
    当调用 SchemaValidator 校验 arguments 对空 schema
    那么返回 is_valid 等于 True

  场景: AC-1.5 - 嵌套对象递归校验
    当调用 SchemaValidator 校验嵌套字段类型不匹配
    那么返回 is_valid 等于 False

  场景: AC-1.6 - SchemaViolation 序列化脱敏 datetime
    当调用 SchemaViolation 含 datetime 字段 to_dict
    那么 actual 字段为 ISO 字符串

  # ============================================================================
  # AC-2: SchemaValidatorPort 应用层端口(jsonschema 库委托)
  # ============================================================================

  场景: AC-2.1 - jsonschema 库委托完整 Draft 7+ 验证
    当调用 JsonSchemaValidatorImpl 校验含 minimum 关键词的 input_schema
    那么返回 is_valid 等于 False

  场景: AC-2.2 - validate_schema_compatibility required 新增破坏性
    当调用 validate_schema_compatibility 比较新旧 schema 且新 required 包含旧 required
    那么返回 is_compatible 等于 False

  场景: AC-2.3 - validate_schema_compatibility 类型放宽兼容
    当调用 validate_schema_compatibility 比较新旧 schema 且类型由 integer 放宽为 number
    那么返回 is_compatible 等于 True

  场景: AC-2.4 - validate_schema_compatibility additionalProperties 收紧
    当调用 validate_schema_compatibility 且 additionalProperties 由 true 变为 false
    那么返回 is_compatible 等于 False

  # ============================================================================
  # AC-3: ToolInputValidator + ToolOutputValidator 装饰器
  # ============================================================================

  场景: AC-3.1 - INPUT strict 校验失败抛异常
    当构造 ToolInputSchemaValidationError 实例
    那么异常的 code 等于 EXCEPTION_395

  场景: AC-3.2 - ToolOutputValidator 重试耗尽抛异常
    当构造 ToolResultValidationError 含 schema_violations 参数
    那么异常的 context 含 schema_violations 字段

  # ============================================================================
  # AC-4: ToolResult 状态扩展(status=invalid 语义完善)
  # ============================================================================

  场景: AC-4.1 - ToolResult 新增 validation_violations 字段
    当构造 ToolResult 不指定 validation_violations
    那么 validation_violations 默认空元组

  场景: AC-4.2 - ToolResult 新增 retry_count 字段
    当构造 ToolResult 不指定 retry_count
    那么 retry_count 默认 0

  场景: AC-4.3 - EvidencePackage.validation 接受 dict 结构化失败详情
    当构造 EvidencePackage validation 为 dict 含 passed 键
    那么 validate_complete 不抛错

  场景: AC-4.4 - ToolResultValidationError schema_violations 向后兼容
    当构造 ToolResultValidationError 不指定 schema_violations
    那么 context 不含 schema_violations 字段

  # ============================================================================
  # AC-5: SchemaValidationRecord 聚合根 + 仓储端口 + migration 013
  # ============================================================================

  场景: AC-5.1 - SchemaValidationRecord 11 字段聚合根
    当创建 INPUT 失败的 SchemaValidationRecord
    那么 repository.save 持久化成功
    并且 repository.get_by_id 可查回

  场景: AC-5.2 - 双租户隔离
    当分别创建 tenantA 和 tenantB 各一条 INPUT 失败记录
    那么查询 tenantA 仅返回一条
    并且查询 tenantB 仅返回一条

  场景: AC-5.3 - asyncio.Lock 类变量并发安全
    当并发保存 50 条 SchemaValidationRecord
    那么 list_all 返回 50 条无丢失

  # ============================================================================
  # AC-6: ToolSchemaValidationFailed 领域事件 + 双通道配置
  # ============================================================================

  场景: AC-6.1 - 事件 13 字段含 tenant_id baseline + is_final
    当构造 ToolSchemaValidationFailed 实例
    那么 event_type 等于 ToolSchemaValidationFailed
    并且 tenant_id 与 schema_version 与 is_final 字段均存在

  场景: AC-6.2 - 事件单通道 realtime 投递(本期,reliable 4.7 启用)
    当 ToolSchemaValidationFailed 事件发布
    那么 realtime 通道投递 1 次
    并且 reliable 通道不投递

  # ============================================================================
  # AC-7: 与 ToolExecutionEngine 集成(Validate 阶段增强)
  # ============================================================================

  场景: AC-7.1 - ToolExecutionEngine 向后兼容 4 字段 __init__
    当构造 ToolExecutionEngine 仅传 4 字段
    那么构造成功不抛错
    并且 _retry_call 仍可用

  场景: AC-7.2 - ToolOutputValidator 包裹 Engine 装饰器模式
    当构造 ToolOutputValidator 包裹 Engine 实例
    那么 isinstance 检查通过

  # ============================================================================
  # AC-8: 端口注册与架构约束
  # ============================================================================

  场景: AC-8.1 - 2 端口注册元数据完整性
    当验证 schema_validator 端口注册
    那么 name 等于 schema_validator
    并且 lifetime 等于 SCOPED

  场景: AC-8.2 - 架构约束 lint-imports 验证通过
    当运行 lint-imports 校验
    那么 domain 层零外部依赖通过

  # ============================================================================
  # 收尾验收
  # ============================================================================

  场景: 收尾 - 覆盖率门禁达标
    当执行覆盖率门禁检查
    那么门禁检查通过
