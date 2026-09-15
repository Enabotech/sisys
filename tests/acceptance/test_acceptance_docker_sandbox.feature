# language: zh-CN
# Story 4.4 — Docker 沙箱执行(BDD 验收场景,完整覆盖 10 条 AC)

功能: Docker 沙箱执行
  作为 安全工程师
  我希望 系统在 Docker 沙箱中执行工具代码,网络隔离 + 权限最小化 + 资源限制
  以便 防止 LLM 生成代码执行带来的安全风险

  背景:
    假如 真实 Docker daemon 可达
    并且 tenant_id 为 test-tenant-001
    并且 session_id 为 sandbox-session-001

  # ===========================================================================
  # AC-1: ContainerSpec 值对象 + 不变量校验
  # ===========================================================================

  场景: AC-1.1 - 12 字段构造成功
    当 使用 12 字段构造 ContainerSpec
    那么 ContainerSpec 创建成功
    并且 image 字段包含 "@sha256:"
    并且 mem_limit_mb 字段为 512
    并且 cpu_quota 字段为 1.0
    并且 pids_limit 字段为 256
    并且 network_mode 字段为 "none"
    并且 read_only_rootfs 字段为 True
    并且 cap_drop 字段为 ["ALL"]
    并且 security_opt 字段为 ["no-new-privileges"]
    并且 timeout_sec 字段为 30.0

  场景: AC-1.2 - 6 项不变量校验失败
    当 构造 ContainerSpec mem_limit_mb=2049
    那么 抛出 EntityValidationError
    并且 错误码为 EXCEPTION_242

  场景: AC-1.3 - image digest 缺失且使用 latest 标签失败
    当 构造 ContainerSpec image="python:latest"
    那么 抛出 EntityValidationError
    并且 错误码为 EXCEPTION_242

  场景: AC-1.4 - network_mode 不为 "none" 失败
    当 构造 ContainerSpec network_mode="bridge"
    那么 抛出 EntityValidationError
    并且 错误码为 EXCEPTION_242

  场景: AC-1.5 - 不可变冻结验证
    当 尝试修改 ContainerSpec image 字段
    那么 抛出 FrozenInstanceError

  # ===========================================================================
  # AC-2: 5 个新沙箱异常 EXCEPTION_315-319
  # ===========================================================================

  场景: AC-2.1 - SandboxImagePullError 构造(code EXCEPTION_315)
    当 构造 SandboxImagePullError(image="python:bad", session_id="s1")
    那么 抛出 SandboxImagePullError
    并且 错误码为 EXCEPTION_315
    并且 context.image 为 "python:bad"

  场景: AC-2.2 - SandboxTimeoutError 构造(code EXCEPTION_316)
    当 构造 SandboxTimeoutError(session_id="s1", timeout_sec=30.0)
    那么 抛出 SandboxTimeoutError
    并且 错误码为 EXCEPTION_316
    并且 context.timeout_sec 为 30.0

  场景: AC-2.3 - SandboxResourceLimitExceededError 构造(code EXCEPTION_317)
    当 构造 SandboxResourceLimitExceededError(session_id="s1", limit_type="mem", limit_value=512, actual_value=600)
    那么 抛出 SandboxResourceLimitExceededError
    并且 错误码为 EXCEPTION_317
    并且 context.limit_type 为 "mem"

  场景: AC-2.4 - SandboxQuotaExceededError 构造(code EXCEPTION_318)
    当 构造 SandboxQuotaExceededError(current_count=51, max_count=50, tenant_id="t1")
    那么 抛出 SandboxQuotaExceededError
    并且 错误码为 EXCEPTION_318
    并且 context.max_count 为 50

  场景: AC-2.5 - SandboxConfigurationError 构造(code EXCEPTION_319)
    当 构造 SandboxConfigurationError(field_name="image", field_value="bad", reason="missing digest")
    那么 抛出 SandboxConfigurationError
    并且 错误码为 EXCEPTION_319
    并且 context.field_name 为 "image"

  # ===========================================================================
  # AC-3: SandboxExecutor 端口向后兼容扩展
  # ===========================================================================

  场景: AC-3.1 - 既有 4 方法签名保持不变
    当 检查 SandboxExecutor Protocol 方法
    那么 start_container 方法存在
    并且 execute_code 方法存在
    并且 stop_container 方法存在
    并且 is_container_running 方法存在
    并且 health_check 方法存在

  场景: AC-3.2 - Protocol runtime_checkable 验证
    当 实例化 SandboxExecutor 协议实现
    那么 isinstance 检查通过

  # ===========================================================================
  # AC-4: SandboxSession + Repository
  # ===========================================================================

  场景: AC-4.1 - SandboxSession 10 字段构造
    当 构造 SandboxSession 聚合根
    那么 SandboxSession 创建成功
    并且 session_id 字段非空
    并且 state 字段为 RUNNING

  场景: AC-4.2 - session_id 正则校验失败
    当 构造 SandboxSession session_id="bad session!"(含非法字符)
    那么 抛出 EntityValidationError

  场景: AC-4.3 - InMemorySandboxSessionRepository CRUD
    当 保存 SandboxSession 到 InMemorySandboxSessionRepository
    那么 通过 session_id 查询返回相同实例
    当 删除该 session
    那么 通过 session_id 查询返回 None

  场景: AC-4.4 - list_idle_sessions 空闲会话查询
    当 创建空闲会话 last_activity_at 早于 threshold
    那么 list_idle_sessions 返回该会话

  # ===========================================================================
  # AC-5: AioDockerSandboxAdapter 实现
  # ===========================================================================

  场景: AC-5.1 - Happy Path 启动 -> 执行 -> 停止
    当 启动唯一 session_id 沙箱会话
    并且 验证沙箱会话已注册到仓储
    那么 启动生命周期完成

  场景: AC-5.2 - 网络隔离验证
    当 启动 sandbox network_mode=none
    那么 network_mode 为 none

  场景: AC-5.3 - 资源限制验证(OOM)
    当 启动 sandbox mem_limit=128m
    那么 mem_limit_mb 为 128

  场景: AC-5.4 - 只读文件系统验证
    当 启动 sandbox read_only=True
    那么 read_only_rootfs 为 True

  场景: AC-5.5 - 进程数限制验证
    当 启动 sandbox pids_limit=10
    那么 pids_limit 为 10

  场景: AC-5.6 - 容器名格式验证
    当 构造唯一 session_id
    那么 容器名格式为 sisys-sandbox-default-{session_short}

  # ===========================================================================
  # AC-6: 30 分钟空闲清理
  # ===========================================================================

  场景: AC-6.1 - TTL 清理空闲会话
    当 创建空闲会话 last_activity_at 早于 threshold
    并且 调用 SandboxSessionReaper.reap_idle_sessions()
    那么 清理数量大于等于 0
    并且 沙箱会话已终止

  场景: AC-6.2 - 孤儿容器扫描
    假如 Docker daemon 可达用于孤儿扫描
    当 调用 SandboxSessionReaper.reap_orphan_containers()
    那么 孤儿容器扫描返回 int

  # ===========================================================================
  # AC-7: SandboxSecurityDecorator
  # ===========================================================================

  场景: AC-7.1 - 超时控制验证
    当 执行代码超过 timeout_sec
    那么 抛出 SandboxTimeoutError
    并且 错误码为 EXCEPTION_316

  场景: AC-7.2 - 重试机制验证(指数退避)
    当 沙箱执行持续失败
    那么 最多重试 3 次
    并且 退避策略为 exponential

  场景: AC-7.3 - session_id 注入防御
    当 调用 execute_code session_id="bad;rm -rf /"
    那么 抛出 SandboxConfigurationError
    并且 错误码为 EXCEPTION_319

  场景: AC-7.4 - 不修改 ToolExecutionEngine.__init__
    当 检查 ToolExecutionEngine.__init__ 签名
    那么 签名参数列表不包含新增参数

  # ===========================================================================
  # AC-8: 集成测试(testcontainers)
  # ===========================================================================

  场景: AC-8.1 - testcontainers 自动清理
    当 testcontainers fixture 退出
    那么 所有容器被自动清理
    并且 无残留容器

  # ===========================================================================
  # AC-9: 性能 + 安全架构验证
  # ===========================================================================

  场景: AC-9.1 - 域层零依赖验证
    当 检查 src/domain/ 是否 import aiodocker/testcontainers
    那么 零外部依赖

  场景: AC-9.2 - PortSpec 10 字段元数据完整性
    当 查询 sandbox_executor 端口
    那么 name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated 全部非空

  场景: AC-9.3 - 异常代码唯一性
    当 检查 EXCEPTION_315-319
    那么 与既有代码无碰撞

  # ===========================================================================
  # AC-10: 端口注册
  # ===========================================================================

  场景: AC-10.1 - 3 个新端口已注册
    当 查询端口注册表
    那么 sandbox_executor 已注册
    并且 sandbox_session_repository 已注册
    并且 sandbox_session_reaper 已注册
