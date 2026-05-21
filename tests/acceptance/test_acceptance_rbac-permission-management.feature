# language: zh-CN
功能: RBAC 权限管理

  作为安全工程师
  我想要实现用户认证与 RBAC 权限管理
  以便系统支持细粒度访问控制，满足等保 2.0 三级合规要求

  背景:
    假如 JWT 配置有效
    并且 PostgreSQL 用户表已创建

  # =========================================================================
  # AC-1: 用户认证 (Authentication)
  # =========================================================================

  场景: 有效凭证登录成功
    假如 用户名 "testuser" 密码 "Test@123" 已存在
    当 用户提交登录请求（用户名: "testuser", 密码: "Test@123"）
    那么 系统返回 JWT access_token
    并且 token 包含用户 ID
    并且 token 包含角色列表
    并且 token 包含过期时间

  场景: 无效密码登录失败
    假如 用户名 "testuser" 密码 "Test@123" 已存在
    当 用户提交登录请求（用户名: "testuser", 密码: "Wrong@456"）
    那么 系统返回 401 Unauthorized
    并且 响应包含 "Invalid credentials"

  场景: 不存在用户登录失败
    假如 用户名 "nonexistent" 不存在
    当 用户提交登录请求（用户名: "nonexistent", 密码: "Any@123"）
    那么 系统返回 401 Unauthorized
    并且 响应包含 "Invalid credentials"

  场景: 锁定账户登录失败
    假如 用户 "lockeduser" 已锁定
    当 用户提交登录请求（用户名: "lockeduser", 密码: "Test@123"）
    那么 系统返回 423 Locked
    并且 响应包含 "locked"

  场景: 停用账户登录失败
    假如 用户 "inactiveuser" 已停用
    当 用户提交登录请求（用户名: "inactiveuser", 密码: "Test@123"）
    那么 系统返回 401 Unauthorized
    并且 响应包含 "inactive"

  场景: JWT 令牌验证成功
    假如 系统已生成有效 JWT token
    当 提交 token 验证请求
    那么 系统返回 TokenPayload
    并且 包含正确的 user_id
    并且 包含正确的 username
    并且 包含正确的 roles

  场景: 过期 JWT 令牌验证失败
    假如 系统已生成过期 JWT token
    当 提交 token 验证请求
    那么 系统返回 401 Unauthorized
    并且 响应包含 "expired"

  场景: 刷新令牌获取新 access token
    假如 用户持有有效 refresh token
    当 提交刷新令牌请求
    那么 系统返回新的 access_token
    并且 新 token 包含正确的用户信息

  场景: 无效刷新令牌失败
    假如 用户持有无效 refresh token
    当 提交刷新令牌请求
    那么 系统返回 401 Unauthorized

  场景: 登出使 token 失效
    假如 用户已登录并持有有效 token
    当 提交登出请求
    那么 token 被加入黑名单
    并且 后续使用该 token 的请求被拒绝

  # =========================================================================
  # AC-2: 角色管理 (Role Management)
  # =========================================================================

  场景: 创建新角色
    假如 当前用户是管理员
    当 提交创建角色请求（name: "editor", permissions: ["document:read", "document:write"]）
    那么 系统返回 201 Created
    并且 角色已创建
    并且 权限列表正确

  场景: 创建重复角色名失败
    假如 角色 "admin" 已存在
    当 提交创建角色请求（name: "admin"）
    那么 系统返回 409 Conflict
    并且 响应包含 "already exists"

  场景: 获取角色列表
    假如 系统存在多个角色
    当 提交获取角色列表请求
    那么 系统返回 200 OK
    并且 包含所有角色

  场景: 获取角色详情
    假如 角色 "editor" 已存在
    当 提交获取角色详情请求（role_id: "editor's id"）
    那么 系统返回 200 OK
    并且 包含角色完整信息

  场景: 获取不存在的角色失败
    假如 角色不存在
    当 提交获取角色详情请求（role_id: "nonexistent"）
    那么 系统返回 404 Not Found

  场景: 更新角色
    假如 角色 "editor" 已存在
    当 提交更新角色请求（role_id: "editor's id", permissions: ["document:read"]）
    那么 系统返回 200 OK
    并且 角色已更新

  场景: 更新不存在的角色失败
    假如 角色不存在
    当 提交更新角色请求（role_id: "nonexistent", name: "newname"）
    那么 系统返回 404 Not Found

  场景: 删除角色
    假如 角色 "temp" 已存在且未被使用
    当 提交删除角色请求（role_id: "temp's id"）
    那么 系统返回 204 No Content
    并且 角色已删除

  场景: 删除系统保留角色失败
    假如 角色 "admin" 是系统保留角色
    当 提交删除角色请求（role_id: "admin's id"）
    那么 系统返回 403 Forbidden
    并且 响应包含 "Cannot delete system-reserved role"

  场景: 删除不存在的角色失败
    假如 角色不存在
    当 提交删除角色请求（role_id: "nonexistent"）
    那么 系统返回 404 Not Found

  # =========================================================================
  # AC-3: 权限控制 (Permission Control)
  # =========================================================================

  场景: 分配权限给角色
    假如 角色 "editor" 存在
    当 提交分配权限请求（role_id: "editor's id", permissions: ["document:delete"]）
    那么 系统返回 200 OK
    并且 角色权限已更新

  场景: 分配权限给不存在的角色失败
    假如 角色不存在
    当 提交分配权限请求（role_id: "nonexistent", permissions: ["document:read"]）
    那么 系统返回 404 Not Found

  场景: 撤销角色权限
    假如 角色 "editor" 有权限 "document:write"
    当 提交撤销权限请求（role_id: "editor's id", permission: "document:write"）
    那么 系统返回 200 OK
    并且 权限已撤销

  场景: 撤销不存在的角色权限失败
    假如 角色不存在
    当 提交撤销权限请求（role_id: "nonexistent", permission: "document:read"）
    那么 系统返回 404 Not Found

  场景: 通配符权限匹配
    假如 角色拥有 "document:*" 权限
    当 检查 "document:read" 权限
    那么 返回 True
    当 检查 "document:write" 权限
    那么 返回 True
    当 检查 "document:delete" 权限
    那么 返回 True

  场景: 多角色权限合并
    假如 用户拥有角色 A（document:read）和角色 B（document:write）
    当 检查用户权限
    那么 拥有 document:read 和 document:write

  # =========================================================================
  # AC-4: 越权访问防护 (Privilege Escalation Prevention)
  # =========================================================================

  场景: 低权限用户访问高权限资源被拒绝
    假如 用户只有 "viewer" 角色（document:read）
    当 用户尝试访问管理员资源
    那么 系统返回 403 Forbidden
    并且 响应包含 "Permission denied"

  场景: 未认证用户访问受保护资源被拒绝
    假如 用户未提供有效 token
    当 用户尝试访问受保护资源
    那么 系统返回 401 Unauthorized
    并且 响应包含 "Not authenticated"

  场景: 水平越权防护 - 用户间数据隔离
    假如 用户 A 拥有资源 R
    并且 用户 B 不拥有资源 R
    当 用户 B 尝试访问用户 A 的资源 R
    那么 系统返回 403 Forbidden
    并且 响应包含 "Permission denied"

  场景: 垂直越权防护 - 权限提升被拒绝
    假如 用户只有普通用户角色
    当 用户尝试为自己分配管理员角色
    那么 系统返回 403 Forbidden
    并且 操作被拒绝

  # =========================================================================
  # AC-5: 等保 2.0 合规 (Deng Bao 2.0 Compliance)
  # =========================================================================

  场景: 密码复杂度验证
    当 用户尝试设置密码 "short"
    那么 系统拒绝
    并且 响应包含密码复杂度要求

  场景: 连续登录失败账户锁定
    假如 用户连续 5 次登录失败
    当 用户再次尝试登录
    那么 系统返回 423 Locked
    并且 账户被锁定 30 分钟

  场景: 会话超时验证
    假如 用户 30 分钟无操作
    当 用户发送请求
    那么 系统返回 401 Unauthorized
    并且 响应包含会话超时

  场景: 最小权限原则验证
    假如 用户只有必需的最少权限
    当 用户访问未授权资源
    那么 系统返回 403 Forbidden

  # =========================================================================
  # 架构约束验证
  # =========================================================================

  场景: 领域层零外部依赖
    当 扫描 src/domain/ports/ 目录
    那么 没有任何文件包含 python-jose 导入
    并且 没有任何文件包含 passlib 导入
    并且 没有任何文件包含 bcrypt 导入

  场景: 接口与实现分离
    当 检查认证服务实现
    那么 AuthServicePort 在 domain/ports/
    并且 AuthServiceImpl 在 infrastructure/security/

  场景: 依赖方向正确
    当 检查依赖方向
    那么 infrastructure 可以依赖 domain
    并且 domain 不能依赖 infrastructure
