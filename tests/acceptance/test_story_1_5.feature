# language: zh-CN
功能: PostgreSQL 关系存储层

  作为系统架构师
  我想要实现 PostgreSQL 关系存储层（L2 存储）
  以便系统可以将用户/RBAC、审计元数据、业务实体持久化，满足 ACID 事务与外键约束要求

  背景:
    假如 PostgreSQL 服务可用
    并且 数据库连接正常

  # =========================================================================
  # AC-1: 连接池与引擎
  # =========================================================================

  场景: 数据库引擎懒初始化
    当 创建 PostgreSQLManager 实例
    那么 引擎尚未创建

  场景: 数据库引擎首次调用创建异步引擎
    假如 PostgreSQLManager 实例已创建
    当 首次调用 get_async_engine
    那么 异步引擎已创建
    并且 后续调用返回同一实例

  场景: 数据库引擎健康检查
    假如 PostgreSQLManager 实例已创建
    当 调用 health_check
    那么 返回 True
    并且 执行 SELECT 1 验证连接

  场景: 数据库引擎优雅关闭
    假如 PostgreSQLManager 实例已创建
    当 调用 close
    那么 所有连接已释放
    并且 引擎实例已清空

  # =========================================================================
  # AC-2: Alembic 迁移
  # =========================================================================

  场景: Alembic 迁移配置
    当 加载 alembic.ini 配置
    那么 配置文件存在
    并且 sqlalchemy.url 从环境变量读取
    并且 target_metadata 从模型自动收集

  场景: 初始迁移脚本就绪
    当 检查 deploy/postgresql/alembic/versions/001_initial.py
    那么 迁移文件存在
    并且 包含 event_outbox 表定义
    并且 包含 users 表定义
    并且 包含 roles 表定义
    并且 包含 permissions 表定义
    并且 包含 user_roles 关联表
    并且 包含 role_permissions 关联表

  场景: event_outbox 表结构合规
    假如 迁移脚本已加载
    那么 event_outbox 包含 id 字段 (UUID, PK)
    并且 event_outbox 包含 event_id 字段 (UUID, Unique, NOT NULL)
    并且 event_outbox 包含 event_type 字段 (String(100), NOT NULL)
    并且 event_outbox 包含 payload 字段 (JSONB, NOT NULL)
    并且 event_outbox 包含 status 字段 (String(20), NOT NULL, 默认 pending)
    并且 event_outbox 包含 created_at 字段 (DateTime, NOT NULL)
    并且 event_outbox 包含 published_at 字段 (DateTime, nullable=True)
    并且 event_outbox 包含 retry_count 字段 (Integer, NOT NULL, 默认 0)
    并且 event_outbox 包含 max_retries 字段 (Integer, NOT NULL, 默认 3)
    并且 event_outbox 包含 error_message 字段 (String(1000), nullable=True)
    并且 包含 CHECK 约束 status IN ('pending', 'published', 'failed')
    并且 包含 CHECK 约束 retry_count >= 0
    并且 包含 CHECK 约束 max_retries >= 0

  场景: Alembic 升级迁移执行成功
    假如 PostgreSQL 服务可用
    当 执行 alembic upgrade head
    那么 迁移执行成功
    并且 所有表已创建

  场景: Alembic 降级回滚执行成功
    假如 PostgreSQL 服务可用
    并且 数据库已迁移到最新版本
    当 执行 alembic downgrade -1
    那么 回滚执行成功
    并且 event_outbox 表已删除

  # =========================================================================
  # AC-3: 通用仓储基类
  # =========================================================================

  场景: BaseRepository 保存实体
    假如 BaseRepository 实例已创建
    当 调用 save 方法保存实体
    那么 实体已保存到数据库

  场景: BaseRepository 根据 ID 查询实体
    假如 BaseRepository 实例已创建
    并且 数据库中存在实体
    当 调用 get_by_id 方法
    那么 返回正确的实体

  场景: BaseRepository 查询实体列表
    假如 BaseRepository 实例已创建
    并且 数据库中存在多个实体
    当 调用 list_all 方法
    那么 返回实体列表
    并且 返回数量不超过 limit 参数

  场景: BaseRepository 删除实体
    假如 BaseRepository 实例已创建
    并且 数据库中存在实体
    当 调用 delete 方法
    那么 实体已从数据库删除

  场景: BaseRepository 统计实体数量
    假如 BaseRepository 实例已创建
    并且 数据库中存在多个实体
    当 调用 count 方法
    那么 返回正确的实体数量

  场景: BaseRepository 查询不存在的 ID
    假如 BaseRepository 实例已创建
    当 调用 get_by_id 方法查询不存在的 ID
    那么 返回 None

  # =========================================================================
  # AC-4: OutboxRepository 实现
  # =========================================================================

  场景: 事件保存到发件箱
    假如 PostgreSQLOutboxRepository 实例
    当 调用 save 保存领域事件
    那么 事件已添加到会话
    并且 事件状态为 pending
    并且 事件类型为正确的领域事件类型

  场景: 获取未发布事件
    假如 PostgreSQLOutboxRepository 实例
    并且 发件箱中有多个 pending 状态事件
    当 调用 async_get_unpublished 方法
    那么 返回所有 pending 状态事件
    并且 事件按 created_at 升序排序
    并且 返回数量不超过 limit 参数

  场景: 获取未发布事件（空结果）
    假如 PostgreSQLOutboxRepository 实例
    并且 发件箱中无 pending 状态事件
    当 调用 async_get_unpublished 方法
    那么 返回空列表

  场景: 标记事件已发布
    假如 PostgreSQLOutboxRepository 实例
    并且 发件箱中有 pending 状态事件
    当 调用 async_mark_published 方法
    那么 事件状态变为 published
    并且 published_at 字段已设置
    并且 当前时间戳正确

  场景: 标记事件发布失败
    假如 PostgreSQLOutboxRepository 实例
    并且 发件箱中有 pending 状态事件
    当 调用 async_mark_failed 方法
    那么 事件状态变为 failed
    并且 retry_count 递增
    并且 error_message 字段已设置

  场景: 事件转换器双向转换
    假如 DomainEvent 实例
    当 调用 SQLAlchemyEventOutboxAdapter.from_domain_event
    那么 返回 OutboxModel 实例
    并且 event_id 一致
    并且 event_type 一致
    并且 payload 包含完整事件数据
    当 调用 to_domain_event 转换回来
    那么 返回 DomainEvent 实例
    并且 事件类型与原始事件一致

  场景: 事务原子性 — 事件保存成功 + 业务操作成功 → 都提交
    假如 PostgreSQL 事务上下文
    并且 PostgreSQLOutboxRepository 实例
    当 调用 save 保存领域事件
    并且 业务操作成功
    并且 提交事务
    那么 事件已持久化到数据库
    并且 业务数据已持久化

  场景: 事务原子性 — 事件保存成功 + 业务操作异常 → 都回滚
    假如 PostgreSQL 事务上下文
    并且 PostgreSQLOutboxRepository 实例
    当 调用 save 保存领域事件
    并且 业务操作抛出异常
    并且 回滚事务
    那么 事件未持久化到数据库
    并且 业务数据未持久化

  场景: 事务原子性 — 事件保存失败 + 业务操作成功 → 都回滚
    假如 PostgreSQL 事务上下文
    并且 PostgreSQLOutboxRepository 实例
    当 调用 save 保存领域事件失败
    并且 回滚事务
    那么 事件未持久化到数据库

  # =========================================================================
  # AC-5: 用户与 RBAC 仓储
  # =========================================================================

  场景: UserRepository 根据用户名查询
    假如 UserRepository 实例
    并且 数据库中存在用户
    当 调用 get_by_username 方法
    那么 返回正确的用户实例

  场景: UserRepository 根据邮箱查询
    假如 UserRepository 实例
    并且 数据库中存在用户
    当 调用 get_by_email 方法
    那么 返回正确的用户实例

  场景: RoleRepository 获取角色权限
    假如 RoleRepository 实例
    并且 角色已关联多个权限
    当 调用 get_permissions_for_role 方法
    那么 返回所有关联的权限
    并且 权限数量正确

  场景: PermissionRepository 根据名称查询
    假如 PermissionRepository 实例
    并且 数据库中存在权限
    当 调用 get_by_name 方法
    那么 返回正确的权限实例

  # =========================================================================
  # AC-6: 架构约束
  # =========================================================================

  场景: 领域层零 SQLAlchemy 依赖
    当 扫描 src/domain/ 目录所有文件
    那么 没有任何文件包含 sqlalchemy 导入

  场景: 依赖方向正确
    当 检查基础设施层导入
    那么 基础设施层可以导入领域层接口
    并且 领域层不导入基础设施层实现
