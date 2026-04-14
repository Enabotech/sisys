Feature: PostgreSQL Relational Layer (Story 1.5)

  作为系统架构师
  我想要实现 PostgreSQL 关系存储层（L2 存储）
  以便系统可以将用户/RBAC、审计元数据、业务实体持久化，满足 ACID 事务与外键约束要求

  Background:
    Given PostgreSQL 配置可用
    And 数据库连接正常

  # AC-1: 连接池与引擎
  Scenario: 数据库引擎懒初始化
    When 创建 DatabaseEngine 实例
    Then 引擎尚未创建
    When 首次调用 get_async_engine
    Then 异步引擎已创建
    And 后续调用返回同一实例

  Scenario: 数据库引擎健康检查
    When 调用 health_check
    Then 返回 True
    And 执行 SELECT 1 验证连接

  Scenario: 数据库引擎优雅关闭
    Given 数据库引擎已创建
    When 调用 close
    Then 所有连接已释放
    And 引擎实例已清空

  # AC-2: Alembic 迁移
  Scenario: Alembic 迁移配置
    When 加载 alembic.ini 配置
    Then 配置文件存在
    And sqlalchemy.url 从环境变量读取
    And target_metadata 从模型自动收集

  Scenario: 初始迁移脚本就绪
    When 检查 alembic/versions/001_initial.py
    Then 迁移文件存在
    And 包含 event_outbox 表定义
    And 包含 users 表定义
    And 包含 roles 表定义
    And 包含 permissions 表定义
    And 包含 user_roles 关联表
    And 包含 role_permissions 关联表

  Scenario: event_outbox 表结构合规
    Given 迁移脚本已加载
    Then event_outbox 包含 id 字段 (UUID, PK)
    And event_outbox 包含 event_id 字段 (UUID, Unique, NOT NULL)
    And event_outbox 包含 event_type 字段 (String(100), NOT NULL)
    And event_outbox 包含 payload 字段 (JSONB, NOT NULL)
    And event_outbox 包含 status 字段 (String(20), NOT NULL, 默认 pending)
    And event_outbox 包含 created_at 字段 (DateTime, NOT NULL)
    And event_outbox 包含 published_at 字段 (DateTime, nullable=True)
    And event_outbox 包含 retry_count 字段 (Integer, NOT NULL, 默认 0)
    And event_outbox 包含 max_retries 字段 (Integer, NOT NULL, 默认 3)
    And event_outbox 包含 error_message 字段 (String(1000), nullable=True)
    And 包含 CHECK 约束 status IN ('pending', 'published', 'failed')
    And 包含 CHECK 约束 retry_count >= 0
    And 包含 CHECK 约束 max_retries >= 0

  # AC-3: 通用仓储基类
  Scenario: BaseRepository 提供 CRUD 操作
    Given BaseRepository 实例已创建
    When 调用 save 方法
    Then 实体已保存到数据库
    When 调用 get_by_id 方法
    Then 返回正确的实体
    When 调用 list_all 方法
    Then 返回实体列表
    When 调用 delete 方法
    Then 实体已从数据库删除
    When 调用 count 方法
    Then 返回正确的实体数量

  # AC-4: OutboxRepository 实现
  Scenario: 事件保存到发件箱
    Given PostgreSQLOutboxRepository 实例
    When 调用 save 保存领域事件
    Then 事件已添加到会话
    And 事件状态为 pending
    And 事件类型为正确的领域事件类型

  Scenario: 获取未发布事件
    Given 发件箱中有多个 pending 状态事件
    When 调用 async_get_unpublished 方法
    Then 返回所有 pending 状态事件
    And 事件按 created_at 升序排序
    And 返回数量不超过 limit 参数

  Scenario: 标记事件已发布
    Given 发件箱中有 pending 状态事件
    When 调用 async_mark_published 方法
    Then 事件状态变为 published
    And published_at 字段已设置
    And 当前时间戳正确

  Scenario: 标记事件发布失败
    Given 发件箱中有 pending 状态事件
    When 调用 async_mark_failed 方法
    Then 事件状态变为 failed
    And retry_count 递增
    And error_message 字段已设置

  Scenario: 事件转换器双向转换
    Given DomainEvent 实例
    When 调用 SQLAlchemyEventOutboxAdapter.from_domain_event
    Then 返回 OutboxModel 实例
    And event_id 一致
    And event_type 一致
    And payload 包含完整事件数据
    When 调用 to_domain_event 转换回来
    Then 返回 DomainEvent 实例
    And 事件类型与原始事件一致

  # AC-5: 用户与 RBAC 仓储
  Scenario: UserRepository 根据用户名查询
    Given UserRepository 实例
    And 数据库中存在用户
    When 调用 get_by_username 方法
    Then 返回正确的用户实例
    When 调用 get_by_email 方法
    Then 返回正确的用户实例

  Scenario: RoleRepository 获取角色权限
    Given RoleRepository 实例
    And 角色已关联多个权限
    When 调用 get_permissions_for_role 方法
    Then 返回所有关联的权限
    And 权限数量正确

  Scenario: PermissionRepository 根据名称查询
    Given PermissionRepository 实例
    And 数据库中存在权限
    When 调用 get_by_name 方法
    Then 返回正确的权限实例

  # AC-6: 架构约束
  Scenario: 领域层零 SQLAlchemy 依赖
    When 扫描 src/domain/ 目录所有文件
    Then 没有任何文件包含 sqlalchemy 导入

  Scenario: 依赖方向正确
    When 检查基础设施层导入
    Then 基础设施层可以导入领域层接口
    And 领域层不导入基础设施层实现
