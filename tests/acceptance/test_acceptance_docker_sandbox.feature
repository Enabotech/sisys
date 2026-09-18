# language: zh-CN
# Story 4.4 — Docker 沙箱执行(BDD 验收场景,完整覆盖 10 条 AC)

功能: Docker 沙箱执行
  作为安全工程师
  我希望系统在 Docker 沙箱中执行工具代码(网络隔离 + 权限最小化 + 资源限制)
  以便防止 LLM 生成代码执行带来的安全风险(数据泄露 / 主机入侵 / 资源耗尽)

背景:
  假如 沙箱会话仓储已初始化(InMemorySandboxSessionRepository)
  并且 沙箱执行适配器已初始化(AioDockerSandboxAdapter)
  并且 沙箱安全装饰器已初始化(SandboxSecurityDecorator)
  并且 ContainerSpec 已定义 12 字段 + 6 项不变量校验
  并且 5 个新沙箱异常已注册(EXCEPTION_315-319)

# =============================================================================
# AC-1 ContainerSpec 值对象 + 不变量校验
# =============================================================================

场景: AC-1.1 - ContainerSpec 12 字段构造成功(digest 模式)
  假如 准备镜像引用 image_with_digest
  当 构造 ContainerSpec 内存限制 512MB CPU 1.0 核
  那么 ContainerSpec 创建成功
  并且 image 字段已填充
  并且 默认 network_mode 等于 none_mode
  并且 默认 read_only_rootfs 为真

场景: AC-1.2 - ContainerSpec 12 字段构造成功(minor tag 模式)
  假如 准备镜像引用 image_with_minor_tag
  当 构造 ContainerSpec
  那么 ContainerSpec 创建成功
  并且 image 字段等于 python_311

场景: AC-1.3 - ContainerSpec 内存超限抛 EntityValidationError
  假如 准备镜像引用 image_with_digest
  当 构造 ContainerSpec 内存限制 2049MB
  那么 抛出 EntityValidationError
  并且 错误码为 EXCEPTION_242

场景: AC-1.4 - ContainerSpec 网络模式非 none 抛 EntityValidationError
  假如 准备镜像引用 image_with_digest
  当 构造 ContainerSpec 网络模式 bridge_mode
  那么 抛出 EntityValidationError
  并且 错误码为 EXCEPTION_242

场景: AC-1.5 - ContainerSpec 镜像包含 :latest 抛 EntityValidationError
  假如 准备镜像引用 image_with_latest
  当 构造 ContainerSpec
  那么 抛出 EntityValidationError
  并且 错误码为 EXCEPTION_242

场景: AC-1.6 - ContainerSpec 不可变(frozen)
  假如 已构造 ContainerSpec
  当 修改 image 字段
  那么 抛出 AttributeError 或 FrozenInstanceError

# =============================================================================
# AC-2 5 个新沙箱异常 EXCEPTION_315-319
# =============================================================================

场景: AC-2.1 - SandboxImagePullError code == EXCEPTION_315
  假如 准备 session_id pull_test_session
  当 构造 SandboxImagePullError 镜像参数 session_id docker_error
  那么 抛出 SandboxImagePullError
  并且 错误码为 EXCEPTION_315
  并且 context.image 等于 image_pull_error
  并且 context.docker_error 等于 manifest_unknown

场景: AC-2.2 - SandboxTimeoutError code == EXCEPTION_316
  假如 准备 session_id timeout_test_session
  当 构造 SandboxTimeoutError 超时 30.0 秒
  那么 抛出 SandboxTimeoutError
  并且 错误码为 EXCEPTION_316
  并且 context.timeout_sec 等于 30.0

场景: AC-2.3 - SandboxResourceLimitExceededError code == EXCEPTION_317
  假如 准备 session_id oom_test_session
  当 构造 SandboxResourceLimitExceededError limit_type mem docker_exit_code 137
  那么 抛出 SandboxResourceLimitExceededError
  并且 错误码为 EXCEPTION_317
  并且 context.limit_type 等于 mem
  并且 context.docker_exit_code 等于 137

场景: AC-2.4 - SandboxQuotaExceededError code == EXCEPTION_318
  当 构造 SandboxQuotaExceededError current_count 50 max_count 50
  那么 抛出 SandboxQuotaExceededError
  并且 错误码为 EXCEPTION_318
  并且 context.current_count 等于 50
  并且 context.max_count 等于 50

场景: AC-2.5 - SandboxConfigurationError code == EXCEPTION_319
  当 构造 SandboxConfigurationError 字段 container_name reason too_long
  那么 抛出 SandboxConfigurationError
  并且 错误码为 EXCEPTION_319
  并且 context.field_name 等于 container_name

场景: AC-2.6 - HTTP 映射 502/504/503/502/502
  假如 准备 5 个新沙箱异常实例
  当 调用 _get_http_status 映射每个异常
  那么 SandboxImagePullError 映射 502
  并且 SandboxTimeoutError 映射 504
  并且 SandboxResourceLimitExceededError 映射 502
  并且 SandboxQuotaExceededError 映射 503
  并且 SandboxConfigurationError 映射 502

# =============================================================================
# AC-3 SandboxExecutor 端口向后兼容扩展
# =============================================================================

场景: AC-3.1 - Protocol 是 @runtime_checkable
  当 读取 SandboxExecutor 类属性
  那么 _is_runtime_protocol 等于 True

场景: AC-3.2 - 4 个既有方法签名扩展(默认参数)
  当 读取 SandboxExecutor.start_container 签名
  那么 参数列表包含 session_id 和 spec
  并且 spec 默认值为 None

场景: AC-3.3 - 新增 health_check 方法
  当 读取 SandboxExecutor.health_check 属性
  那么 方法存在
  并且 方法为 async

场景: AC-3.4 - execute_code 接受 keyword-only timeout_sec
  当 读取 SandboxExecutor.execute_code 签名
  那么 参数列表包含 session_id code timeout_sec
  并且 timeout_sec 为 keyword-only 参数
  并且 timeout_sec 默认值为 None

场景: AC-3.5 - 既有 4.1a 调用行为兼容性(默认参数机制)
  假如 构造 4.1a 既有 mock 适配器(只实现 4 个既有方法)
  当 异步调用 start_container 传入 session_id
  那么 调用不报错(默认参数兼容)

# =============================================================================
# AC-4 SandboxSession + Repository
# =============================================================================

场景: AC-4.1 - SandboxSession 10 字段构造
  假如 准备 session_id sess_001_with_tenant
  当 构造 SandboxSession image_digest python_311_slim
  那么 SandboxSession 创建成功
  并且 session_id 等于 sess_001
  并且 state 默认 state_running
  并且 state_version 默认 0

场景: AC-4.2 - SandboxSession session_id 正则校验
  假如 准备非法 session_id invalid_session_id
  当 构造 SandboxSession
  那么 抛出 EntityValidationError
  并且 错误码为 EXCEPTION_242

场景: AC-4.3 - Repository CRUD (save + get_by_session_id + delete)
  假如 准备 SandboxSession
  当 调用 save 存储
  并且 调用 get_by_session_id 查询
  那么 返回相同 SandboxSession 实例
  当 调用 delete_by_session_id 删除
  并且 调用 get_by_session_id 查询
  那么 返回 None

场景: AC-4.4 - Repository 不继承 L2RdbPort(主键类型决策)
  当 检查 SandboxSessionRepositoryPort.__mro__
  那么 L2RdbPort 不在继承链中
  并且 get_by_session_id 参数 session_id 类型为 str(非 UUID)

# =============================================================================
# AC-5 AioDockerSandboxAdapter 实现
# =============================================================================

场景: AC-5.1 - Happy Path 启动 → 执行 → 停止(需 Docker daemon)
  假如 Docker daemon 可用
  当 调用 start_container 启动会话
  并且 调用 execute_code 执行代码
  并且 调用 stop_container 停止容器
  那么 容器生命周期完整
  并且 执行结果字典 status 字段为 status_completed

场景: AC-5.2 - 网络隔离 network_mode=none_mode (需 Docker daemon)
  假如 Docker daemon 可用
  当 启动容器并执行 curl 命令
  那么 命令失败(网络不可达)

场景: AC-5.3 - 资源限制 OOM kill (需 Docker daemon)
  假如 Docker daemon 可用
  当 启动 mem_limit=128m 容器并执行大内存分配
  那么 抛出 SandboxResourceLimitExceededError
  并且 错误码为 EXCEPTION_317

场景: AC-5.4 - 只读文件系统 (需 Docker daemon)
  假如 Docker daemon 可用
  当 启动 read_only_rootfs=True 容器并尝试写入 /etc/test
  那么 写入失败(Read-only file system)

场景: AC-5.5 - 进程数限制 (需 Docker daemon)
  假如 Docker daemon 可用
  当 启动 pids_limit=10 容器并执行 fork bomb
  那么 fork bomb 被 cgroups 杀死

场景: AC-5.6 - 已知 CVE 沙箱逃逸测试集 0 次 (需 Docker daemon)
  假如 Docker daemon 可用
  当 执行 chroot mount ptrace 逃逸尝试
  那么 所有逃逸尝试均失败(seccomp profile 阻止)

# =============================================================================
# AC-6 30 分钟空闲清理 + 孤儿容器回收
# =============================================================================

场景: AC-6.1 - reap_idle_sessions 清理空闲会话
  假如 仓储中有 1 个空闲会话(last_activity_at > 30 分钟前)
  当 调用 reap_idle_sessions
  那么 返回 1(清理 1 个会话)
  并且 sandbox.stop_container 被调用 1 次

场景: AC-6.2 - 默认 threshold 为 now - 30 分钟
  假如 仓储中有 1 个 45 分钟前活跃的会话
  当 调用 reap_idle_sessions 默认 threshold
  那么 1 个会话被清理

场景: AC-6.3 - reap_idle_sessions 失败隔离
  假如 仓储中有 2 个空闲会话
  并且 sandbox.stop_container 第一次调用抛异常第二次成功
  当 调用 reap_idle_sessions
  那么 2 个 stop_container 都被尝试调用

# =============================================================================
# AC-7 SandboxSecurityDecorator 包裹类
# =============================================================================

场景: AC-7.1 - session_id 注入防御
  假如 准备非法 session_id bad_session_id
  当 调用 execute_code_with_protection
  那么 抛出 SandboxConfigurationError
  并且 错误码为 EXCEPTION_319

场景: AC-7.2 - 并发配额检查
  假如 仓储中已有 10 个 RUNNING 会话(等于 max_concurrent_containers)
  当 调用 execute_code_with_protection 传入新 session_id
  那么 抛出 SandboxQuotaExceededError
  并且 错误码为 EXCEPTION_318

场景: AC-7.3 - 超时控制
  假如 沙箱执行超过 timeout_sec
  当 调用 execute_code_with_protection 应用超时保护
  那么 抛出 SandboxTimeoutError
  并且 错误码为 EXCEPTION_316

场景: AC-7.4 - 不修改 ToolExecutionEngine.__init__ 既有签名
  当 检查 ToolExecutionEngine.__init__ 签名
  那么 参数列表为 [self, llm_client, sandbox, retry_policy, tool_execution_repository]
  并且 参数数量为 5(未增加)

# =============================================================================
# AC-8 集成测试(testcontainers 真实 Docker daemon)
# =============================================================================

场景: AC-8.1 - 启动延迟 P95 < 5s(基准:含镜像预拉取)
  假如 Docker daemon 可用
  当 连续启动 20 个容器并测量延迟
  那么 热启动 P95 小于 2 秒
  并且 冷启动 小于 30 秒(含镜像预拉取)

场景: AC-8.2 - 并发 ≥ 10
  假如 Docker daemon 可用
  当 并发启动 10 个会话
  那么 10 个会话全部启动成功

场景: AC-8.3 - 已知 CVE 沙箱逃逸 0 次
  假如 Docker daemon 可用
  当 执行 chroot mount ptrace 系统调用
  那么 0 次逃逸(seccomp profile + cap_drop ALL 阻止)

场景: AC-8.4 - 事件发布验证(3 个沙箱事件)
  假如 已注册事件订阅者
  当 启动 → 执行 → 停止完整生命周期
  那么 SandboxSessionStarted 事件被发布
  并且 SandboxSessionTerminated 事件被发布

# =============================================================================
# AC-9 性能 + 安全架构验证
# =============================================================================

场景: AC-9.1 - 域层零依赖验证
  当 扫描 src/domain/value_objects/container_spec.py 的 import
  那么 不包含 aiodocker
  并且 不包含 docker
  并且 不包含 testcontainers

场景: AC-9.2 - PortSpec 10 字段元数据验证
  假如 端口 sandbox_session_repository 已注册
  当 读取 PortSpec 元数据
  那么 name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated 全部存在
  并且 version 匹配 ^\d+\.\d+\.\d+$

场景: AC-9.3 - 异常子域归属校验
  假如 5 个新沙箱异常已定义
  当 查询 _CLASS_TO_SUBDOMAIN 映射
  那么 5 个异常均归属 sandbox 子域
  并且 编码在 311-319 范围内

# =============================================================================
# AC-10 端口注册
# =============================================================================

场景: AC-10.1 - 3 个新端口已注册
  假如 composition_root 已加载
  当 查询 sandbox_executor 端口
  那么 已注册
  当 查询 sandbox_session_repository 端口
  那么 已注册
  当 查询 sandbox_session_reaper 端口
  那么 已注册

场景: AC-10.2 - 端口元数据完整(10 字段)
  假如 3 个新端口已注册
  当 读取每个端口的 PortSpec
  那么 10 字段均非空
  并且 owner 等于 sandbox_team
  并且 lifetime 是 Lifetime enum
