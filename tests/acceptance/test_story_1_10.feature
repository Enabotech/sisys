# Story 1.10: Unified Audit Log - Acceptance Tests

@audit @acceptance
Feature: 统一审计日志 (Unified Audit Log)

  合规工程师需要一个统一的审计日志系统，以便追踪系统中的关键操作，
  支持多维检索，满足等保 2.0 和 SOX 合规要求。

  背景:
    Given 系统已初始化完成
    And PostgreSQL 连接可用
    And 审计日志表已创建

  @AC-1
  Scenario: 记录审计日志
    Given 用户已认证（user_id: "user-123", username: "testuser"）
    When 系统产生登录事件（action_type: "authentication:login"）
    Then 审计日志记录到 PostgreSQL
    And 日志包含字段：log_id, timestamp, actor, action_type, target_resource
    And SHA256 校验和已计算

  @AC-1
  Scenario: 记录认证失败事件
    Given 用户尝试登录（username: "invalid_user"）
    When 认证失败（action_type: "authentication:failed"）
    Then 审计日志记录失败事件
    And 记录包含失败原因

  @AC-2
  Scenario: 按时间范围检索审计日志
    Given 审计日志已记录多条
    When 合规工程师查询时间范围（start: "2026-01-01", end: "2026-12-31"）
    Then 返回该时间范围内的日志
    And 返回结果按时间倒序排列

  @AC-2
  Scenario: 按 actor 检索审计日志
    Given 审计日志已记录多条
    When 合规工程师按 actor 查询（actor: "user-123"）
    Then 返回该用户的所有操作日志

  @AC-2
  Scenario: 按 action_type 检索审计日志
    Given 审计日志已记录多条
    When 合规工程师按 action_type 查询（action_type: "authentication:login"）
    Then 返回所有登录操作日志

  @AC-2
  Scenario: 分页检索审计日志
    Given 审计日志已记录超过 20 条
    When 合规工程师分页查询（page: 1, page_size: 10）
    Then 返回前 10 条日志
    And 返回结果包含 total 字段
    And 再次查询第二页返回接下来的 10 条

  @AC-3
  Scenario: 验证审计日志完整性
    Given 审计日志已记录
    When 系统验证日志完整性（log_id: "{log_id}"）
    Then SHA256 校验和验证通过
    And 返回验证结果（integrity_verified: true）

  @AC-3
  Scenario: 检测篡改的审计日志
    Given 审计日志已记录
    And 日志被篡改（修改 old_value）
    When 系统验证日志完整性（log_id: "{log_id}"）
    Then 校验和验证失败
    And 返回验证结果（integrity_verified: false）

  @AC-3
  Scenario: 批量验证审计日志完整性
    Given 审计日志已记录多条
    When 系统批量验证完整性
    Then 返回验证摘要（total: N, passed: M, failed: K）
    And 包含每条日志的验证详情

  @AC-4
  Scenario: 手动归档旧的审计日志
    Given 审计日志已记录超过 30 天
    When 管理员手动触发归档（older_than_days: 30）
    Then 旧日志归档到 WORM 存储
    And archived 标志更新为 true
    And archived_at 时间戳记录

  @AC-4
  Scenario: 查询归档状态
    Given 审计日志已归档
    When 合规工程师查询归档状态（log_id: "{log_id}"）
    Then 返回归档状态（archived: true, archived_at: "{timestamp}"）

  @AC-5
  Scenario: 登录/登出事件完整记录
    Given 用户执行登录操作
    When 登录成功
    Then 审计日志记录 "authentication:login" 事件

    Given 用户执行登出操作
    When 登出成功
    Then 审计日志记录 "authentication:logout" 事件

  @AC-5
  Scenario: 权限变更事件记录
    Given 管理员授予用户权限（role: "admin"）
    When 权限授予成功
    Then 审计日志记录 "authorization:grant" 事件

    Given 管理员撤销用户权限（role: "admin"）
    When 权限撤销成功
    Then 审计日志记录 "authorization:revoke" 事件

  @AC-5
  Scenario: 越权访问检测
    Given 普通用户尝试访问管理资源
    When 访问被拒绝
    Then 审计日志记录越权访问事件

  @AC-1 @integration
  Scenario: RBAC 与审计集成 - 登录流程
    Given 用户凭证有效
    When 用户登录成功
    Then 认证服务发布 AuditEvent（action_type: "authentication:login"）
    And 审计日志记录到 PostgreSQL
    And 事件包含正确的 actor 和 timestamp

  @AC-1 @integration
  Scenario: RBAC 与审计集成 - 权限变更流程
    Given 管理员用户已登录
    When 管理员授予用户角色
    Then 权限服务发布 AuditEvent（action_type: "authorization:grant"）
    And 审计日志记录权限变更
    And old_value 和 new_value 记录变更前后状态
