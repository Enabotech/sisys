# language: zh-CN
# -*- coding: utf-8 -*-
功能: Story 1.10 — 统一审计日志

  作为安全工程师
  我希望实现统一审计日志系统
  以便系统满足等保 2.0 和 SOX 合规要求，支持完整操作追溯和多方检索

  背景:
    假如 审计日志服务已初始化
    并且 PostgreSQL 审计数据库已就绪

  # ===============================================================
  #                      AC-1: 统一审计日志记录
  # ===============================================================

  场景: 记录认证事件
    假如 系统发生用户登录事件
    当 认证服务记录审计日志
    那么 日志应包含 log_id (UUID)
    并且 日志应包含 timestamp (UTC 时间)
    并且 日志应包含 actor (用户标识)
    并且 日志应包含 action_type (authentication:login)
    并且 日志应包含 target_resource (登录资源)
    并且 日志通过事务发件箱模式保证可靠性

  场景: 记录文档操作事件
    假如 用户上传文档
    当 文档服务记录审计日志
    那么 日志应包含 action_type (document:upload)
    并且 日志应包含 old_value 和 new_value (状态变更)
    并且 日志应在同一事务中写入 audit_log 和 audit_outbox 表

  场景: 记录 Agent 决策事件
    假如 Agent 执行决策
    当 Agent 服务记录审计日志
    那么 日志应包含 action_type (agent:decide 或 agent:execute)
    并且 日志应包含 target_resource (被决策的资源)

  场景: 审计事件序列化与反序列化
    假如 已创建 AuditEvent 包含所有 FR-SC-02 字段
    当 执行 to_dict() 序列化
    那么 所有审计字段应正确序列化
    并且 可通过 from_dict() 正确反序列化

  # ===============================================================
  #                         AC-2: 不可变存储
  # ===============================================================

  场景: PostgreSQL 审计表不可更新
    假如 审计日志已写入 PostgreSQL
    当 尝试更新现有日志条目
    那么 应通过 RLS 策略阻止更新
    并且 抛出权限错误

  场景: PostgreSQL 审计表不可删除
    假如 审计日志已写入 PostgreSQL
    当 尝试删除日志条目
    那么 应通过 RLS 策略阻止删除
    并且 抛出权限错误

  场景: 审计日志校验和验证
    假如 审计日志条目包含校验和
    当 执行 verify_integrity()
    那么 未篡改的日志应返回 True
    并且 篡改后的日志应返回 False

  场景: 归档至 WORM 存储
    假如 审计日志需要长期保留（≥7 年）
    当 执行归档操作
    那么 日志应写入 MinIO WORM bucket (audit-archives)
    并且 归档后日志保持不可变

  # ===============================================================
  #                          AC-3: 多维检索
  # ===============================================================

  场景: 按时间范围检索
    假如 审计日志已积累
    当 按 start_time 和 end_time 查询
    那么 应返回指定时间范围内的日志
    并且 支持分页返回

  场景: 按 actor 筛选
    假如 审计日志已积累
    当 按 actor (用户标识) 查询
    那么 应返回该用户的所有操作日志

  场景: 按 action_type 筛选
    假如 审计日志已积累
    当 按 action_type 查询
    那么 应返回指定操作类型的日志

  场景: 按 correction_level 筛选 (FR-SC-04)
    假如 审计日志包含 correction_level
    当 按 correction_level 查询
    那么 应返回指定修正级别的日志

  场景: 审计日志分页查询
    假如 审计日志数量超过单页限制
    当 执行分页查询 (page, page_size)
    那么 应返回正确分页的结果
    并且 包含 total 和 total_pages 信息

  场景: 审计统计查询
    假如 审计日志已积累
    当 查询审计统计
    那么 应返回 by_action_type 统计
    并且 应返回 by_actor 统计
    并且 应返回 total_entries 数量

  # ===============================================================
  #                    AC-4: 等保 2.0 + SOX 合规
  # ===============================================================

  场景: 等保合规报告生成
    假如 需要生成等保 2.0 合规报告
    当 执行 generate_dengbao_report()
    那么 报告应包含登录/登出事件统计
    并且 报告应包含权限变更事件统计
    并且 报告应包含完整性评分
    并且 报告应标记是否通过合规验证

  场景: SOX 合规报告生成
    假如 需要生成 SOX 合规报告
    当 执行 generate_sox_report()
    那么 报告应包含财务相关事件统计
    并且 报告应包含保留期限合规状态
    并且 报告应包含审计追踪完整性验证

  场景: 合规报告包含时间范围
    假如 指定了报告时间范围
    当 生成合规报告
    那么 报告应正确反映指定时间范围内的数据

  # ===============================================================
  #                         AC-5: 事件驱动集成
  # ===============================================================

  场景: 事件监听器自动记录审计日志
    假如 AuthenticationEvent 被发布
    当 AuditEventListener 处理该事件
    那么 应自动记录审计日志
    并且 action_type 应映射为 authentication:login

  场景: 事件类型映射
    假如 DocumentProcessedEvent 被发布
    当 AuditEventListener 处理该事件
    那么 action_type 应映射为 document:process

  场景: 未知事件类型使用通用 action
    假如 UnknownEventType 被发布
    当 AuditEventListener 处理该事件
    那么 action_type 应使用通用格式 (event:unknowneventtype)

  场景: 事件处理提取 actor 信息
    假如 事件 payload 包含 actor
    当 AuditEventListener 处理该事件
    那么 审计日志的 actor 应从 payload 提取

  场景: 事件处理提取 correction_level
    假如 CorrectionApprovedEvent 包含 correction_level
    当 AuditEventListener 处理该事件
    那么 审计日志应包含正确的 correction_level

  场景: 事件处理异常不中断
    假如 事件处理过程中发生异常
    当 AuditEventListener 处理该事件
    那么 不应抛出异常中断处理
    并且 应记录错误日志

  # ===============================================================
  #                            架构约束验证
  # ===============================================================

  场景: AuditEvent 定义在领域层
    假如 检查审计模块架构
    那么 AuditEvent 应定义在 src/domain/events/
    并且 AuditService Protocol 应定义在 src/domain/services/

  场景: 领域层无基础设施依赖
    假如 检查 domain/events/audit_events.py
    那么 不应导入 infrastructure 模块

  场景: 基础设施层实现领域接口
    假如 检查审计服务实现
    那么 AuditServiceImpl 应在 src/infrastructure/audit/
    并且 应实现 domain/services/audit_service.py 中的 Protocol
