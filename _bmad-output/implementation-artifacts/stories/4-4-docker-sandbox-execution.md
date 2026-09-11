# Story 4.4: Docker 沙箱执行

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 安全工程师,
**I want** 系统在 Docker 沙箱中执行工具代码，网络隔离 + 权限最小化 + 资源限制,
**So that** 防止 LLM 生成代码执行带来的安全风险（数据泄露 / 主机入侵 / 资源耗尽），并支撑 Epic 4 的 Validation Feedback 闭环（Story 4.7）与 Skills 数据采集基础设施（Story **4.1c**，**注**：原文档误标 4.1b，实际 sprint-status.yaml 中 4-1b 是 skills-feat-enhancement）。

### 业务价值

Story 4.1a 已实现 `ToolExecutionEngine` 五阶段工作流（Think→Code→Execute→Observe→Validate），但 `SandboxExecutor` 端口目前由 **mock 实现** 支撑（仅日志 + 字典记录），无法满足生产环境的隔离与安全要求。Story 4.4 将该 mock 替换为 **生产级 Docker 沙箱实现**：

1. **代码执行隔离**：每个会话获得独立容器 + CPU 1 核 / 内存 512MB / 网络默认禁用 / 只读文件系统 + tmpfs `/tmp`
2. **权限最小化**：`--security-opt no-new-privileges` + `cap_drop: ALL` + user namespace remap + 自定义 seccomp profile
3. **网络隔离**：默认断网（`network_mode: "none"`），通过白名单网关访问可信财经 API（架构层预留，应用层无外网调用）
4. **资源回收**：30 分钟无活动自动销毁容器 + 孤儿容器定时清理
5. **错误捕获**：STDERR 自动捕获，支撑 Story 4.7 Validation Feedback 闭环（最大重试 3 次）
6. **可观测**：容器启动延迟 P95 < 5s、并发 ≥ 10、沙箱逃逸 0 次

**业务定位：** Epic 4 战略工具箱的 **安全执行层**，位于工具执行（4.1a）之上、Validation Feedback 闭环（4.7）与 Skills 数据采集（4.1c）之下。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，FR-ST-04
**前置依赖:** Story 4.1a（✅ done，ToolExecutionEngine 已注入 `SandboxExecutor` mock）/ Story 1.7（✅ done，L4 MinIO 对象层）/ Story 1.18a（✅ done，Prefect 工作流引擎）
**后续依赖:** Story **4.1c**（Skills 数据采集基础设施，依赖 4.4 提供安全执行，**注**：原文档误标 4.1b）/ Story 4.7（Validation Feedback 闭环增强，依赖 4.4 捕获 STDERR）

### ⚠️ Story 范围澄清（重要）

**本 Story 范围（4.4）：**

1. **替换 mock 实现**：将 `DockerSandboxAdapter`（mock）替换为基于 `aiodocker` 的真实 Docker 容器管理 `AioDockerSandboxAdapter`；采用**删除 mock + 替换 impl 字符串**策略（不保留 fallback，避免 CLAUDE.md §5 mock 滥用）；CI/本地无 Docker 环境通过 `SISYS_USE_TEST_PORTS=1` 切换（CLAUDE.md §6 既有约定）
2. **`ContainerSpec` 值对象**（领域层）：CPU/内存/网络模式/镜像 digest/seccomp profile/ulimits/pids-limit 等约束的不可变描述（**12 字段**：1 必填 `image` + 11 项默认值；详见 AC-1）
3. **5 个新领域异常**（EXCEPTION_315~319）：`SandboxImagePullError` / `SandboxTimeoutError` / `SandboxResourceLimitExceededError` / `SandboxQuotaExceededError` / `SandboxConfigurationError`
4. **`SandboxExecutor` 端口扩展**：保持向后兼容（4.1a 既有 4 方法签名不变），通过**默认参数**新增可选 `ContainerSpec` / `timeout_sec` 入参 + 新增 `health_check()` 方法
5. **应用层安全编排**：新增 `SandboxSecurityDecorator` 包裹类（**非 Python `@decorator` 语法**，仅借用设计模式术语），在 `ToolExecutionEngine` 装配层注入超时 + 重试 + 配额 + session_id 注入防御；**不修改** `ToolExecutionEngine.__init__`
6. **30 分钟空闲清理**：新增**独立应用层服务** `SandboxSessionReaper`，基于 `SandboxSessionRepositoryPort.list_idle_sessions()` 实现；**不修改** `SessionNamespaceManager`（既有 4.1a 实现无 TTL 机制）
7. **集成测试基础设施**：`testcontainers-python` 真实 Docker daemon + pytest-bdd 验收
8. **架构验证测试**：`tests/unit/architecture/test_docker_sandbox.py`（**注意：epics_v1.0.md:1204 硬要求此路径，不带 `_arch_` 前缀**）验证域层零依赖 + PortSpec 10 字段元数据完整性
9. **Alembic migration 014**：`down_revision = "013"`（**关键**：既有 11 个 migration 的 `revision` 字段都是数字 ID 如 `"013"`/`"012"`/`"011"`，**不是文件名**；详见 `deploy/postgresql/alembic/versions/013_schema_validation_records.py:30`），记录沙箱会话（便于审计 + 配额统计）

**不在本 Story 范围（拆分到其他 Story）：**

- **gVisor 用户空间内核隔离**（更高安全等级）→ 后续 Epic 18 Story 18.1（`epics_v1.0.md:589`，P2 非 MVP，`prd.md:1828` FR-ST-10；非 MVP，本 Story 不涉及）
- **跨工具链共享 Jupyter Kernel**（持久化变量）→ 后续 Story（`or.md:232` 三.3.[2]），当前仅做"30 分钟空闲销毁"
- **白名单网关代理服务**（可信财经 API 访问通道）→ 后续基础设施 Story；本 Story `ContainerSpec.network_mode` 写死为 `"none"`（**删除 `network_whitelist` 字段**，遵循 CLAUDE.md §2 Simplicity First）
- **资源配额按租户维度控制**（多租户公平调度）→ Story 4.7（Validation Feedback 闭环增强）评估
- **沙箱执行结果 Schema 强类型化**（`dict[str, Any]` → `SandboxExecutionResult` VO）→ 当前保持 4.1a 既有契约，4.7 升级

**复用决策（依据 R2 规则）：**

- **R1 复用**（既有，不修改）：
  - `SandboxExecutor` Protocol（4.1a 既有 4 方法）
  - `SessionNamespaceManager`（4.1a 既有，无 TTL 不扩展）
  - `ContainerSecurityServicePort`（4.1a 完整 Protocol + 4 个值对象 `IsolationVerificationResult` / `ResourceLimitsStatus` / `EscapeAttempt` / `NetworkIsolationResult` 复用，**非 stub**）
  - `_call_with_retry`（`src/application/services/retry_helpers.py:62`，4.3 经验）
- **R2 扩展**（默认参数兼容）：
  - `SandboxExecutor` Protocol 新增可选 `spec: ContainerSpec | None = None`（start_container）+ `timeout_sec: float | None = None`（execute_code）+ 新方法 `health_check() -> bool`
  - 调用点零修改（4.1a 既有调用通过默认参数沿用旧行为）
- **R3 新建**（4.4 从零创建）：
  - `ContainerSpec` 值对象（领域层，**12 字段**：1 必填 `image` + 11 项默认值）
  - `SandboxSession` 聚合根（领域层，10 字段）
  - `SandboxSessionQuery` Query 值对象（领域层，frozen dataclass）
  - `SandboxSessionRepositoryPort` Protocol（领域层，**不继承 L2RdbPort**，因主键为字符串 `session_id`，与 L2RdbPort 的 UUID 主键约束不兼容，详见 AC-4 修订说明）
  - 3 个领域事件 `SandboxSessionStarted` / `SandboxSessionTerminated` / `SandboxExecutionFailed`（**继承 `DomainEvent` 基类**，使用基类 `event_id`/`timestamp` 字段，业务字段放 `payload` 或保留为事件自有字段）
  - `AioDockerSandboxAdapter`（基础设施层，替换 mock）
  - `ContainerSpecBuilder`（基础设施层，ContainerSpec → aiodocker kwargs）
  - `SeccompProfileLoader`（基础设施层，加载仓库内置 seccomp profile）
  - `InMemorySandboxSessionRepository`（基础设施层，asyncio.Lock **类变量**）
  - `SandboxSecurityDecorator`（应用层，包裹 ToolExecutionEngine）
  - `SandboxSessionReaper`（应用层，30 分钟空闲清理 + 孤儿容器扫描）

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

> 本 Story 实施过程中**严格遵守**以下硬约束，违反任何一项需返回 `draft` 状态重新设计。

### 领域零依赖（FR-AR-01）

- `src/domain/` 禁止 import 任何第三方包，**`aiodocker` / `docker` / `testcontainers` 均禁止**
- 禁止 import `src.application` / `src.interfaces` / `src.infrastructure`
- `.importlinter` 强制校验：`poetry run lint-imports`

### 异常体系强制（sisys-uni-exception-design.md）

- **禁止** `raise ValueError(...)`
- **禁止** 手动 `raise HTTPException(...)`
- **禁止** 继承内置 `Exception`（除 `DomainError` 基类）
- **必须** 走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前**三条 grep 自查**必须零输出：`grep -rn "raise ValueError\|raise HTTPException\|class.*Exception\b" src/`

### 新增异常完整性 Checklist（**5 项强制**，含 1 项 HTTP 映射注册）

1. **定义文件**：在 `src/domain/exceptions/sandbox_exceptions.py` 新增 5 个异常类（**扩展** 既有 sandbox 子域模块，不新建文件）
2. **`_code_ranges.py` 子域映射**：在 `_CLASS_TO_SUBDOMAIN` 注册 class → 子域对应（**复用 `sandbox` 子域 311-319**，新增占用 315-319，**与既有 311-314 共用子域**，不新建子域）
3. **`__init__.py` 暴露**：在 `src/domain/exceptions/__init__.py` 导入并加入 `__all__`
4. **子域码段校验**：异常 `code` 在 `sandbox` 子域（311-319）范围内（**注意**：本 Story 仅占用 315-319，311-314 已被 4.1a 既有 4 个异常占用）
5. **`EXCEPTION_HTTP_MAP` 注册**：在 `src/interfaces/api/exception_handlers.py` 增加 5 条新异常 → HTTP 状态码映射（默认 502，`SandboxTimeoutError: 504`，`SandboxQuotaExceededError: 503`；既有 sandbox 注释偏差 `# 309~312` 与实际 `EXCEPTION_311~314` 不一致属于历史 bug，本 Story 不修复）

### 抑制告警禁止

- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释
- **禁止** mypy 配置 `ignore_missing_imports=true` 豁免
- `aiodocker` **无 `py.typed`**：**必须**创建 PEP 561 stubs（`stubs/aiodocker/__init__.pyi`），覆盖实际使用的 **9 个 API 面**（`Docker.pull` / `Docker.ping` / `Docker.containers.run` / `Docker.containers.get` / `Docker.containers.list` / `Docker.containers.delete` / `Container.exec_create` / `Container.exec_start` / `Container.stats`）

### Commit & Push 规范

- **禁止** commit 信息含 AI 辅助署名（`Co-Authored-By: Claude` / `anthropic.com` 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 已合入的架构依赖规则
- **禁止** 修改已合入的 alembic migration（只允许新增，本期新增 migration 014）

### Sandbox 安全约束（CLAUDE.md §6 Gotcha 扩展）

- **禁止** 直接调用 `subprocess` 执行用户代码（必须经 Docker 容器）
- **禁止** 容器内提权（必须 `cap_drop: ["ALL"]` + `security_opt=["no-new-privileges"]`）
- **禁止** 网络默认开放（必须 `network_mode: "none"`；本 Story 删除 `network_whitelist` 字段，遵循 CLAUDE.md §2 Simplicity First）
- **禁止** `image: ":latest"`（必须 pin digest 或 minor tag）
- **asyncio.Lock 必须为类变量**：`InMemorySandboxSessionRepository._lock: asyncio.Lock = asyncio.Lock()`（CLAUDE.md §6 Gotcha）
- **session_id 注入防御**：容器名 `f"sisys-sandbox-{tenant_id_short}-{session_id_short}"` 必须校验 session_id 匹配正则 `^[A-Za-z0-9_-]{1,64}$`；tenant_id_short 取 UUID 前 8 字符，session_id_short 截取前 32 字符，**总长度控制在 Docker 上限 64 字符内**
- **容器命名统一约定**（全文唯一格式）：`sisys-sandbox-{tenant_id[:8]}-{session_id[:32]}`（生产）+ 测试场景追加 `TestTenant UUID` 前缀（tenant_id 已含 UUID 前缀）

---

## 🎯 领域异常契约（CLAUDE.md §5 强制）

> 本 Story 涉及的所有异常必须在 Task 0 完成前完成 **5 项 Checklist**（含 1 项 EXCEPTION_HTTP_MAP 注册，详见硬约束章节）。

### 已存在异常复用（来自 Story 4.1a sandbox_exceptions.py）

| 异常类 | code | parent | 触发场景 | 复用方式 |
|--------|------|--------|----------|----------|
| `SandboxError` | EXCEPTION_311 | `ExternalException` | 沙箱基础异常（兜底） | 复用 |
| `ContainerStartError` | EXCEPTION_312 | `SandboxError` | 容器启动失败（除镜像拉取外的其他原因） | 复用 |
| `ExecutionError` | EXCEPTION_313 | `SandboxError` | 容器内代码执行失败（STDERR 非空 / 退出码非 0） | 复用 |
| `ContainerStopError` | EXCEPTION_314 | `SandboxError` | 容器停止 / 移除失败 | 复用 |

### 候选新增异常（本 Story Task 0 评估）

**关键决策：复用 `sandbox` 子域（311-319）**，新增占用 315-319，不新建子域。

| 候选异常 | 触发场景 | parent class | 建议 code | HTTP 映射 | 5 项 Checklist |
|----------|----------|--------------|-----------|-----------|---------------|
| `SandboxImagePullError` | 容器镜像拉取失败（digest 不存在 / daemon 拉取权限不足 / 网络超时） | `ContainerStartError` (EXCEPTION_312) | EXCEPTION_315 | 502 | Task 0 |
| `SandboxTimeoutError` | 代码执行超过 `ContainerSpec.timeout_sec`（默认 30s） | `ExecutionError` (EXCEPTION_313) | EXCEPTION_316 | 504 | Task 0 |
| `SandboxResourceLimitExceededError` | 容器内存 / CPU / pids 超出 cgroups 限制（OOM kill exit 137） | `ExecutionError` (EXCEPTION_313) | EXCEPTION_317 | 502 | Task 0 |
| `SandboxQuotaExceededError` | 并发容器数超过 `MAX_CONCURRENT_CONTAINERS`（默认 50） | `SandboxError` (EXCEPTION_311) | EXCEPTION_318 | 503 | Task 0 |
| `SandboxConfigurationError` | ContainerSpec 字段不合法（镜像 digest 缺失 / mem_limit 越界 / seccomp profile 加载失败 / 容器名超长） | `SandboxError` (EXCEPTION_311) | EXCEPTION_319 | 502 | Task 0 |

**HTTP 映射决策说明**：

- `SandboxConfigurationError` 采用 **502**（与父类 `SandboxError` 一致，标记为上游服务错误），**不采用 500**（500 适用于本系统内部错误，与"配置错误由调用方负责"的语义不符）
- `SandboxTimeoutError` 采用 **504**（与 `TimeoutError` (EXCEPTION_3XX) 子域约定一致，504 Gateway Timeout）
- `SandboxQuotaExceededError` 采用 **503**（与 `ServiceUnavailableError` (EXCEPTION_3XX) 一致，503 Service Unavailable）

**新增异常构造器统一规范**（与 `DomainError.__init__(message, cause, context)` 三参数契约一致）：

```python
class SandboxTimeoutError(ExecutionError):
    """EXCEPTION_316 — 代码执行超时

    Attributes:
        code: 异常编码 EXCEPTION_316
        message: 异常描述 "Sandbox execution timeout"
    """

    code = "EXCEPTION_316"
    message = "Sandbox execution timeout"

    def __init__(
        self,
        reason: str,
        *,
        session_id: str,
        timeout_sec: float,
        execution_id: str | None = None,
        docker_exit_code: int | None = None,
    ) -> None:
        super().__init__(
            reason,
            context={
                "session_id": session_id,
                "timeout_sec": timeout_sec,
                "execution_id": execution_id,
                "docker_exit_code": docker_exit_code,
            },
        )
```

**继承层次设计说明**：

- `SandboxTimeoutError` 继承 `ExecutionError`（而非直接继承 `SandboxError`）—— 因为"超时"是"执行失败"的一种特定场景，语义层次清晰；与 line 174 反模式警告"❌ 复用 `ExecutionError` 直接抛 timeout（缺乏超时上下文）"区分：本 Story 通过**独立异常类** `SandboxTimeoutError` 携带超时上下文，**不是**简单抛 `ExecutionError(timeout_msg)`
- `SandboxConfigurationError` 与 `EntityValidationError` (EXCEPTION_242) 边界划分：
  - `EntityValidationError`：领域层静态字段不变量校验（如 `ContainerSpec.__post_init__` **6 项**不变量），HTTP 400
  - `SandboxConfigurationError`：基础设施层运行时配置错误（如 seccomp profile 文件加载失败、容器名长度超 Docker 64 字符上限），HTTP 502

**禁止设计反模式（CLAUDE.md §5 + 异常 5 轮审查经验）**：

- ❌ 复用 `ExecutionError` 直接抛 timeout（缺乏超时上下文，违反"异常携带领域上下文"原则）→ 修复：必须新建独立 `SandboxTimeoutError` 类
- ❌ 将镜像拉取失败归类为 `ContainerStartError`（无法精确区分"启动配置错误" vs "镜像拉取失败"，监控无法精确告警）→ 修复：必须新建独立 `SandboxImagePullError` 类
- ❌ 新建 `SandboxStateTransitionError`（沙箱容器无状态机概念；如需状态追踪走 `EntityStateTransitionError` EXCEPTION_243）
- ❌ 把"运行时配置错误"归类为 `EntityValidationError`（语义层次不符，`EntityValidationError` 专用于领域层静态不变量）→ 修复：必须新建 `SandboxConfigurationError` 类

### 复用既有异常

| 异常类 | code | parent | 触发场景 |
|--------|------|--------|----------|
| `EntityValidationError` | EXCEPTION_242 | entity 子域 | ContainerSpec 字段不变量校验（mem_limit ≤ 上限 / pids_limit ≤ 上限 / image digest 非空） |
| `EntityBusinessRuleError` | EXCEPTION_244 | entity 子域 | 业务规则违反（如并发容器数 > 配额 / session_id 格式非法） |
| `ConfigurationError` | EXCEPTION_101 | system 子域 | Docker daemon 不可用（连接被拒 / socket 不存在） |

### 登记确认动作（Task 0 必做）

- [ ] 在 `src/domain/exceptions/sandbox_exceptions.py` 新增 5 个异常类
- [ ] 在 `src/domain/exceptions/_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 字典增加 5 行 `("SandboxImagePullError", "sandbox")` 等（与既有 sandbox 子域共用 311-319 范围）
- [ ] 在 `src/domain/exceptions/__init__.py` 导入并加入 `__all__`
- [ ] 在 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 注册 5 条新映射（`SandboxTimeoutError: 504`、`SandboxQuotaExceededError: 503`、其余默认 502）
- [ ] 运行 `poetry run pytest tests/unit/domain/exceptions/test_code_ranges.py -v`（既有测试，必须包含新增异常的子域范围校验）
- [ ] 运行 `poetry run pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v`（既有测试，必须无碰撞）

---

## 🎯 测试隔离约束（CLAUDE.md §4 + §5 强制）

> 沙箱执行涉及真实 Docker daemon，测试隔离要求高于普通集成测试。

### TestTenant UUID 前缀

- 所有测试用容器名 / 卷名 / 网络名加 TestTenant UUID 前缀（`test-{uuid}-sandbox-{session_id}`）
- 集成测试使用 `testcontainers-python` 创建临时 docker network / volume，测试结束自动销毁（testcontainers 自带 `with` 上下文管理器回收）
- **禁止** 集成测试手动 `docker rm` / `docker network rm`（依赖 testcontainers 自清理）

### asyncio.Lock 类变量（CLAUDE.md §6 Gotcha）

- `AioDockerSandboxAdapter._lock: asyncio.Lock = asyncio.Lock()`（**类变量**，非实例变量）
- `InMemorySandboxSessionRepository._lock: asyncio.Lock = asyncio.Lock()`（**类变量**，非实例变量）

### BDD 步骤函数（CLAUDE.md §5 + Story 4.3 commit `099423f1` 经验）

**项目既有 BDD 模式**（52/52 acceptance 文件遵循）：

- **Step 函数形态**：**同步 `def`**（不是 `async def`）— pytest-bdd 8.x 限制
- **异步代码调度**：通过 `event_loop.run_until_complete(coro)` 驱动（不是 pytest-asyncio auto 模式）
  - **Pattern A**：自建 module 级 `event_loop` fixture（`test_acceptance_relevance_evaluation.py:35-40` 等 10+ 文件）
  - **Pattern B**：直接消费 pytest-asyncio 内建 `event_loop` fixture（`test_acceptance_hybrid_search_3_4.py:90, 96, 120, 128`）
- **`@pytest.mark.asyncio`**：**禁止**用于 BDD step 函数（CLAUDE.md §5 红线；会导致 context data 丢失）
  - 项目 8 处 `@pytest.mark.asyncio` 均在 `async def` fixture 或 `async def` 测试函数上，**不在 step 函数本体**
- **Context 传递**：`context: dict[str, Any]` fixture（100% 统一）
- **`asyncio_mode = "auto"`**：全局开启（pyproject.toml:274），**仅用于非 BDD 的 async fixture/test 函数**，**不驱动 BDD step**

**Round 1 修订错误更正**：Round 1 描述"step 函数使用 `async def` + pytest-asyncio auto 模式"与项目实际惯例冲突。Round 2 修订为同步 `def` + `event_loop.run_until_complete()` 模式（对齐 `test_acceptance_strategic_tool_impl.py:424-430` `_run_async()` helper 模式）。

### 真实服务优先（CLAUDE.md §5）

- **单元测试**：Mock 端口（`AsyncMock(spec=SandboxExecutor)`），不连接真实 Docker daemon
- **集成测试**：使用 `testcontainers-python` 启动真实 Docker daemon（自包含：创建 → 执行 → 销毁）
- **验收测试**：使用真实 Docker daemon（开发者本地或 CI runner），禁止 mock；动态 `pytest.skip()`（如 daemon 不可用）

### Schema 隔离

- Alembic migration 014 sandbox_sessions 表使用 `tenant_id` UUID + 复合索引
- 集成测试使用 `test_{uuid}` PG schema + savepoint rollback（**禁止** 手动 delete/truncate）

### 容器生命周期清理

- 测试 fixture 必须显式声明 cleanup（testcontainers 上下文管理器自动处理）
- 禁止 autouse fixture 清理 `test_*` 全局匹配容器（CLAUDE.md §5 禁止行为）

---

## 🌐 API 契约（CLAUDE.md §4 端口契约 + 内/外部接口契约）

### 外部端口契约：SandboxExecutor（向后兼容扩展）

**位置：** `src/domain/ports/sandbox_executor.py`（**既有文件扩展**，非新建）

**向后兼容原则：** 不破坏 4.1a 既有 4 方法的**调用行为**（既有调用点零修改），通过**默认参数**扩展入参签名（注：`@runtime_checkable` Protocol 不验证默认参数；`inspect.signature()` 会反映参数扩展，但既有调用点按位置参数调用不受影响）

```python
@runtime_checkable
class SandboxExecutor(Protocol):
    """沙箱执行协议端口（Story 4.4 扩展，向后兼容 4.1a 既有签名）

    调用行为保持不变：
    - 既有 4 方法位置参数调用不受影响
    - 新增可选 ContainerSpec 参数（默认 None → 沿用既有默认配置）
    - 新增方法 health_check() 用于监控与熔断器集成
    """

    async def start_container(
        self,
        session_id: str,
        spec: ContainerSpec | None = None,  # 新增可选参数（默认 None），向后兼容
    ) -> None: ...

    async def execute_code(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,  # 新增可选 keyword-only 参数（默认 None），向后兼容
    ) -> dict[str, Any]: ...

    async def stop_container(self, session_id: str) -> None: ...

    async def is_container_running(self, session_id: str) -> bool: ...

    # 新增方法（Story 4.4）
    async def health_check(self) -> bool:
        """Docker daemon 健康检查（用于熔断器 + 启动探针）

        Returns:
            daemon 可达返回 True，否则 False（**不抛异常**，由调用方决定熔断）
        """
        ...
```

**4.1a 既有调用点零修改约束：** `ToolExecutionEngine.__init__(self, sandbox: SandboxExecutor)` 既有签名不修改（4.3 装饰器模式经验），所有既有调用点（如 `session_namespace_manager.py:51` / `:73`）通过新参数默认 `None` 沿用旧行为。本 Story 在 `composition_root.py:2220-2239` 的 `tool_execution_engine` lambda impl 处嵌套 `SandboxSecurityDecorator` 包裹（详见 AC-7 修订示例）。

### 内部端口契约：SandboxSessionRepository（新增）

**位置：** `src/domain/ports/sandbox_session_repository.py`

**⚠️ 设计决策（关键 P0 修正）：**

**SandboxSessionRepositoryPort 不继承 `L2RdbPort`**，原因如下：

- `L2RdbPort[T]` 基类主键约束为 `UUID`（`src/domain/ports/l2_rdb.py:26`：`async def get_by_id(self, id: UUID) -> T | None`）
- `SandboxSession` 聚合根业务主键设计为字符串 `session_id: str`（匹配 `^[A-Za-z0-9_-]{1,64}$`），与 L2RdbPort 的 UUID 主键约束**类型不兼容**
- 若强行继承，会导致：
  - mypy 严格模式下 `save(entity)` 调用时无法映射字符串主键到 UUID 入参
  - InMemory 实现违反 Liskov 替换原则
  - 与既有项目惯例冲突（既有 4 个 InMemory 仓储的主键都是 UUID）

**正确方案：** 独立定义 `SandboxSessionRepositoryPort(Protocol)`，通过 `SandboxSessionQuery` Query 值对象（frozen dataclass）支持多字段组合查询（CLAUDE.md §4 端口查询参数决策规则）

```python
@runtime_checkable
class SandboxSessionRepositoryPort(Protocol):
    """沙箱会话仓储端口（领域层，Story 4.4 新增）

    设计决策：**不继承 L2RdbPort**（主键类型冲突，详见上方决策说明）。
    通过独立 Protocol + SandboxSessionQuery Query 值对象实现多字段组合查询。

    基础 CRUD（按字符串 session_id 索引）：
    - async def get_by_session_id(session_id: str) -> SandboxSession | None
    - async def save(session: SandboxSession) -> SandboxSession
    - async def delete_by_session_id(session_id: str) -> None
    - async def list_all() -> list[SandboxSession]

    领域扩展（多字段查询，CLAUDE.md §4 决策规则）：
    - async def find_by_query(query: SandboxSessionQuery) -> list[SandboxSession]
    - async def list_idle_sessions(threshold: datetime) -> list[SandboxSession]
    - async def count_active(tenant_id: UUID | None = None) -> int
    """
```

### ContainerSpec 值对象（新增）

**位置：** `src/domain/value_objects/container_spec.py`

```python
@dataclass(frozen=True)
class ContainerSpec:
    """容器规格值对象（领域层，Story 4.4 新增）

    Attributes:
        image: 镜像引用（必须包含 digest 或 minor tag，禁止 :latest）
        mem_limit_mb: 内存限制（MB，默认 512，上限 2048）
        cpu_quota: CPU 配额（默认 1.0 核，cgroups v2 cpu.max）
        pids_limit: 进程数限制（默认 256，上限 1024）
        network_mode: 网络模式（写死 "none"，遵循 CLAUDE.md §2 Simplicity First）
        read_only_rootfs: 是否只读根文件系统（默认 True）
        tmpfs_mounts: tmpfs 挂载点字典（默认 {"/tmp": "100m"}）
        cap_drop: 移除的 Linux capabilities（默认 ["ALL"]）
        security_opt: 安全选项（默认 ["no-new-privileges"]）
        seccomp_profile: seccomp profile 路径（默认仓库内置 hardened profile）
        userns_mode: user namespace 模式（默认 "host"）
        timeout_sec: 代码执行超时（秒，默认 30，上限 300）

    字段总数：**12 项**（含 image 必填 + **11 项**默认值）
    """
    image: str
    mem_limit_mb: int = 512
    cpu_quota: float = 1.0
    pids_limit: int = 256
    network_mode: str = "none"
    read_only_rootfs: bool = True
    tmpfs_mounts: dict[str, str] = field(default_factory=lambda: {"/tmp": "100m"})
    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges",)
    seccomp_profile: str = "deploy/docker/seccomp/sisys-hardened.json"
    userns_mode: str = "host"
    timeout_sec: float = 30.0

    def __post_init__(self) -> None:
        """字段不变量校验（抛 EntityValidationError EXCEPTION_242）"""
        if self.mem_limit_mb <= 0 or self.mem_limit_mb > 2048:
            raise EntityValidationError(...)
        if self.cpu_quota <= 0 or self.cpu_quota > 8.0:
            raise EntityValidationError(...)
        if self.pids_limit <= 0 or self.pids_limit > 1024:
            raise EntityValidationError(...)
        if self.timeout_sec <= 0 or self.timeout_sec > 300:
            raise EntityValidationError(...)
        if self.network_mode != "none":  # 写死 "none"，未来 V2 扩展时再放宽
            raise EntityValidationError(...)
        if "@sha256:" not in self.image and ":latest" in self.image:
            raise EntityValidationError(...)  # 禁止 latest
```

**注意：** 原文档描述的 `network_whitelist` 字段已**删除**（本 Story 不实现网络白名单网关，遵循 CLAUDE.md §2 Simplicity First），因此 `__post_init__` 不变量校验从原 7 项减少为 **6 项**。

### 领域事件：SandboxSessionStarted / SandboxSessionTerminated（**继承 DomainEvent 基类**）

**位置：** `src/domain/events/sandbox_events.py`

**⚠️ 设计决策（关键 P0 修正）：**

事件必须**继承 `DomainEvent` 基类**（`src/domain/events/base.py:42-69`），使用基类的 `event_id` / `event_type` / `timestamp` / `aggregate_id` / `aggregate_type` 等 12 个标准字段，业务字段（`session_id` / `container_id` 等）保留为事件自有字段或放入 `payload` 字典。

参考 `ToolExecuted(DomainEvent)` 模式（`src/domain/events/tool_events.py:21-46`）。

**通道映射（必须在 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 同步更新）：**

| 事件 | realtime (Redis pub/sub) | reliable (RabbitMQ + Outbox) |
|------|--------------------------|------------------------------|
| `SandboxSessionStarted` | `sisys:rt:sandbox.session.started` | `sisys.events.reliable.sandbox.session.started` |
| `SandboxSessionTerminated` | `sisys:rt:sandbox.session.terminated` | `sisys.events.reliable.sandbox.session.terminated` |
| `SandboxExecutionFailed` | `sisys:rt:sandbox.execution.failed` | `sisys.events.reliable.sandbox.execution.failed` |

**事件 schema 字段**（继承 DomainEvent 基类）：

```python
@dataclass(frozen=True)
class SandboxSessionStarted(DomainEvent):
    """沙箱会话启动事件（继承 DomainEvent 基类）

    基类字段（event_id / event_type / timestamp / source / schema_version /
    aggregate_id / aggregate_type / version / payload / correlation_id /
    causation_id / metadata）自动继承。

    Attributes:
        session_id: 业务标识符（字符串，匹配 ^[A-Za-z0-9_-]{1,64}$）
        container_id: Docker container ID
        image_digest: 实际启动的镜像 digest
        resource_limits: 来自 ContainerSpec.to_dict()
        event_type: 事件类型，固定为"SandboxSessionStarted"
    """

    session_id: str = ""
    container_id: str = ""
    image_digest: str = ""
    resource_limits: dict[str, Any] = field(default_factory=dict)
    event_type: str = field(default="SandboxSessionStarted", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type"""
        if self.aggregate_id is None:
            # aggregate_id 是 UUID 类型，与 session_id（字符串）分离
            # 通过元数据 metadata 传递 session_id 关联
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxSession")
        if "session_id" not in self.metadata:
            object.__setattr__(
                self, "metadata", {**self.metadata, "session_id": self.session_id}
            )
```

**关键修正点**：
- 删除原文档中独立的 `event_id: UUID` + `occurred_at: datetime` 字段（基类已提供 `event_id` + `timestamp`）
- `aggregate_id`（UUID 类型）与 `session_id`（字符串类型）分离，session_id 通过 `metadata` 字典传递
- 子类通过 `event_type: str = field(default="Xxx", init=False)` 标注具体类型（参考 `ToolExecuted` 模式）

### 契约测试文件清单

**⚠️ 重要事实校正（关键 P0 修正）：**

既有 `tests/contracts/test_port_contract_sandbox_executor.py`（4.1a 创建）**实际只有 8 个测试方法**（`test_protocol_is_runtime_checkable` / 4 个 `test_*_method_exists` / `test_start_container_signature` / `test_compliant_implementation` / `test_noncompliant_implementation_fails`），**不是 11 维度**。

本 Story 实施策略：
- `tests/contracts/test_port_contract_sandbox_executor.py`（**既有扩展**）：从 8 维度扩展到 11 维度（对齐 `test_port_contract_tool_execution_service.py:5-16` 样板），新增 3 个维度：
  - `port_version`（新增断言 `spec.version` 非空）
  - `port_owner`（新增断言 `spec.owner == "sandbox-team"`）
  - `port_module`（新增断言 `spec.module` 路径正确）
- `tests/contracts/test_port_contract_sandbox_session_repository.py`（**新建**）：11 维度全量覆盖（直接对齐样板，无既有扩展负担）
- `tests/contracts/test_event_contract_sandbox_events.py`（**新建**）：事件契约（字段必填 + 序列化 + 通道双投递 + 继承 DomainEvent 基类）
- `tests/contracts/test_value_object_contract_container_spec.py`（**新建**）：**12 字段**值对象契约（不变量校验）

**PortSpec 实际 10 字段**（`src/domain/ports/registry.py:44-53`）：
`name / version / interface / impl / module / lifetime / owner / compatibility / tags / deprecated`
（**注意**：register_port 5 个必填位置参数为 `name / version / interface / impl / module`，其余通过 `**kwargs` 透传；本文原文档"7 字段"表述错误）

---

## 📊 Story Details（template.md §4.6 强制）

| 字段 | 值 |
|------|-----|
| Story ID | `4.4` |
| Story Key | `4-4-docker-sandbox-execution` |
| File | `_bmad-output/implementation-artifacts/stories/4-4-docker-sandbox-execution.md` |
| Status | `ready-for-dev` |
| Epic | Epic 4: 战略工具箱 |
| 价值组 | 战略决策智能（Executive Decision Intelligence） |
| 优先级 | P0（Epic 4 战略工具箱核心安全能力） |
| 估算工作量 | **25-35 人天**（含 5 项 Checklist 异常体系 + aiodocker 集成 + 11 维度端口契约测试（含既有 8→11 维度扩展）+ ContainerSpec **12 字段**不变量 + 30 分钟 TTL 清理 + Seccomp profile 配置 + testcontainers 集成测试 + 架构验证测试 + alembic migration 014 + BDD 验收 +30% 缓冲） |
| 覆盖 FR | FR-ST-04（Docker 沙箱执行）/ FR-ST-07（Validation Feedback 闭环前置） |
| 前置 Story | 4-1a-strategic-tool-impl（✅ done）/ 1-7-minio-object-layer（✅ done）/ 1-18a-prefect-workflow-integration（✅ done） |
| 后续 Story | **4-1c-skills-data-collection-integration**（**注**：原文档误标 4-1b，实际 sprint-status.yaml 中 4-1b 是 skills-feat-enhancement，4-1c 才是数据采集集成） / 4-7-validation-feedback-loop |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: ContainerSpec 值对象 + 不变量校验

**Given** 沙箱执行需要可复用的容器规格描述，且需阻止 `image: :latest` / 内存越界等危险配置
**When** 在领域层定义 `ContainerSpec` 值对象
**Then**

- **路径**：`src/domain/value_objects/container_spec.py`
- **字段**（**13 项**，详见上文 ContainerSpec 签名）：
  - 必填：`image: str`（必须包含 `@sha256:` digest 或 `:X.Y` minor tag，禁止 `:latest`）
  - 默认：`mem_limit_mb: int = 512` / `cpu_quota: float = 1.0` / `pids_limit: int = 256`
  - 默认：`network_mode: str = "none"` / `read_only_rootfs: bool = True`
  - 默认：`tmpfs_mounts: dict[str, str] = {"/tmp": "100m"}` / `cap_drop: tuple[str, ...] = ("ALL",)`
  - 默认：`security_opt: tuple[str, ...] = ("no-new-privileges",)` / `seccomp_profile: str = "<仓库内置>"`
  - 默认：`userns_mode: str = "host"` / `timeout_sec: float = 30.0`
  - **注意**：`network_whitelist` 字段已删除（CLAUDE.md §2 Simplicity First，本期不实现网络白名单网关）
- **`__post_init__` 不变量校验**（**违反任一项**抛 `EntityValidationError` EXCEPTION_242）：
  1. `mem_limit_mb ∈ (0, 2048]`
  2. `cpu_quota ∈ (0, 8.0]`
  3. `pids_limit ∈ (0, 1024]`
  4. `timeout_sec ∈ (0, 300]`
  5. `network_mode == "none"`（写死，未来 V2 扩展时再放宽）
  6. `image` 必须包含 `@sha256:` digest **或** `:X.Y` minor tag；**禁止** `:latest`
- **不可变设计**：`@dataclass(frozen=True)` + 容器规格冻结为不可变值对象
- **零依赖**：仅 import `dataclass` / `field`（标准库）+ 领域层异常，禁止 import 任何第三方

**验证标准/Validation Criteria:**

- [ ] `ContainerSpec` 位于 `src/domain/value_objects/container_spec.py`（**领域层**，非应用层）
- [ ] **12 字段**完整（按上文列表）
- [ ] `__post_init__` 触发 **6 项**不变量校验（失败抛 `EntityValidationError` EXCEPTION_242）
- [ ] 禁止 `:latest` 镜像（必须 digest 或 minor tag）
- [ ] 默认 `network_mode="none"` + `read_only_rootfs=True` + `cap_drop=("ALL",)`
- [ ] 域层零依赖验证通过（`poetry run lint-imports`）
- [ ] 单元测试覆盖：`_make_container_spec(**overrides)` 工厂函数 + **6 项**不变量失败测试 + 默认值验证
- [ ] 契约测试 `tests/contracts/test_value_object_contract_container_spec.py` 通过

### AC-2: 5 个新沙箱领域异常（EXCEPTION_315-319）

**Given** 沙箱执行可能遭遇镜像拉取失败 / 代码执行超时 / 资源超限 / 并发配额超限 / 配置错误
**When** 在 `sandbox_exceptions.py` 扩展 5 个新异常类
**Then**

- **路径**：`src/domain/exceptions/sandbox_exceptions.py`（**扩展既有模块**，非新建）
- **5 个异常类**（**占 EXCEPTION_315~319**）：
  | 类名 | code | parent | 触发场景 | 上下文字段 |
  |------|------|--------|----------|-----------|
  | `SandboxImagePullError` | EXCEPTION_315 | `ContainerStartError` (312) | 镜像拉取失败 | `image` / `session_id` / `digest` / `docker_error` |
  | `SandboxTimeoutError` | EXCEPTION_316 | `ExecutionError` (313) | 代码执行超过 `timeout_sec` | `session_id` / `timeout_sec` / `execution_id` / `docker_exit_code` |
  | `SandboxResourceLimitExceededError` | EXCEPTION_317 | `ExecutionError` (313) | 内存 / CPU / pids 超出 cgroups | `session_id` / `limit_type`（mem/cpu/pids）/ `limit_value` / `actual_value` / `docker_exit_code`（通常 137） |
  | `SandboxQuotaExceededError` | EXCEPTION_318 | `SandboxError` (311) | 并发容器数超过 `MAX_CONCURRENT_CONTAINERS` | `current_count` / `max_count` / `tenant_id` |
  | `SandboxConfigurationError` | EXCEPTION_319 | `SandboxError` (311) | ContainerSpec 字段不合法 / seccomp profile 加载失败 | `field_name` / `field_value` / `reason` |
- **构造器签名**：所有异常构造器接受 `reason: str` + `**kwargs` 上下文字段，通过 `super().__init__(reason, context=kwargs)` 注入
- **HTTP 映射**：在 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 注册（默认 502，`SandboxTimeoutError` 例外 504，`SandboxQuotaExceededError` 例外 503）

**验证标准/Validation Criteria:**

- [ ] 5 个异常类位于 `src/domain/exceptions/sandbox_exceptions.py`（既有模块扩展）
- [ ] 每个异常 `code` 在 `sandbox` 子域（311-319）范围内（315-319 各占 1 位）
- [ ] `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 字典增加 5 行
- [ ] `__init__.py` 导入并加入 `__all__`（既有 `__all__` 扩展 5 项）
- [ ] `EXCEPTION_HTTP_MAP` 注册 5 条新映射（`SandboxTimeoutError: 504`，其余默认 502 / 503）
- [ ] 单元测试覆盖：构造器 / `to_dict()` 序列化 / `cause` 链 / HTTP 映射
- [ ] `poetry run pytest tests/unit/domain/exceptions/test_code_ranges.py -v` 通过
- [ ] `poetry run pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v` 通过（无碰撞）
- [ ] 三条 grep 自查零输出：`grep -rn "raise ValueError\|raise HTTPException\|class.*Exception\b" src/`

### AC-3: SandboxExecutor 端口向后兼容扩展

**Given** Story 4.1a 已实现 `SandboxExecutor` 协议 + `ToolExecutionEngine` 既有签名 `__init__(sandbox: SandboxExecutor)`
**When** 扩展 `SandboxExecutor` Protocol（新增可选参数 + 新方法）
**Then**

- **路径**：`src/domain/ports/sandbox_executor.py`（**既有文件扩展**，非新建）
- **既有方法签名保持不变**（4.1a 调用点无需修改）：
  - `async def start_container(self, session_id: str) -> None: ...`（**既有签名**）
  - `async def execute_code(self, session_id: str, code: str) -> dict[str, Any]: ...`（**既有签名**）
  - `async def stop_container(self, session_id: str) -> None: ...`（**既有签名**）
  - `async def is_container_running(self, session_id: str) -> bool: ...`（**既有签名**）
- **扩展方法**（默认参数 → 向后兼容）：
  - `async def start_container(self, session_id: str, spec: ContainerSpec | None = None) -> None`（默认 `None` → 沿用既有默认）
  - `async def execute_code(self, session_id: str, code: str, *, timeout_sec: float | None = None) -> dict[str, Any]`（默认 `None` → 沿用既有默认）
- **新增方法**：
  - `async def health_check(self) -> bool`（daemon 可达 → True，否则 False，**不抛异常**，用于熔断器 + 启动探针）
- **零依赖**：Protocol 仅依赖 `typing.Protocol` / `runtime_checkable` / `Any` + 领域层异常 + 领域层值对象（`ContainerSpec`）
- **运行时检查**：`@runtime_checkable`（既有）

**验证标准/Validation Criteria:**

- [ ] `SandboxExecutor` Protocol 位于 `src/domain/ports/sandbox_executor.py`（既有位置）
- [ ] 4 个既有方法签名**完全保持不变**（4.1a 调用点不破坏）
- [ ] 2 个扩展方法通过默认参数实现向后兼容
- [ ] 新增 `health_check()` 方法（不抛异常，返回 bool）
- [ ] 域层零依赖验证通过（`poetry run lint-imports`）
- [ ] 契约测试 `tests/contracts/test_port_contract_sandbox_executor.py`（**既有**，11 维度）扩展验证向后兼容
- [ ] 单元测试 `tests/unit/domain/ports/test_sandbox_executor_port.py`（**既有**）通过（既有测试用例不修改）

### AC-4: SandboxSession 聚合根 + SandboxSessionRepository 端口

**Given** 沙箱会话需要持久化追踪（启动时间 / 资源限制 / 容器 ID / 空闲 TTL），支撑配额统计与空闲清理
**When** 新建 `SandboxSession` 聚合根 + `SandboxSessionRepositoryPort` 端口
**Then**

- **`SandboxSession` 聚合根**：
  - **路径**：`src/domain/entities/sandbox_session.py`
  - **字段**（10 项）：
    - `session_id: str`（业务标识符，匹配 `^[A-Za-z0-9_-]{1,64}$`，**非 UUID 主键**）
    - `tenant_id: UUID`（多租户隔离）
    - `container_id: str | None`（Docker container ID，启动后填充）
    - `image_digest: str`（实际启动的镜像 digest）
    - `started_at: datetime`
    - `last_activity_at: datetime`（用于 30 分钟 TTL 计算）
    - `terminated_at: datetime | None`（终态时填充）
    - `resource_limits: dict[str, Any]`（来自 `ContainerSpec.to_dict()`）
    - `state: Literal["RUNNING", "TERMINATED", "FAILED"]`（简化为 3 值，**不引入状态机**，避免过度设计）
    - `state_version: int`（乐观锁版本号）
  - **`__post_init__` 不变量**：`session_id` 格式正则 + `tenant_id` 非空 UUID + 终态时 `terminated_at` 必填
  - **不可变设计**：`@dataclass(frozen=True)`
- **`SandboxSessionRepositoryPort`**：
  - **路径**：`src/domain/ports/sandbox_session_repository.py`（**领域层**）
  - **基类**：**独立 Protocol**，**不继承 `L2RdbPort`**（主键类型冲突：L2RdbPort 主键是 UUID，SandboxSession 主键是字符串 session_id）
  - **基础 CRUD**（按字符串 `session_id` 索引）：
    ```python
    async def get_by_session_id(session_id: str) -> SandboxSession | None
    async def save(session: SandboxSession) -> SandboxSession  # 使用 state_version 乐观锁
    async def delete_by_session_id(session_id: str) -> None
    async def list_all() -> list[SandboxSession]
    ```
  - **查询方法**（使用 Query Object 模式，CLAUDE.md §4）：
    ```python
    @dataclass(frozen=True)
    class SandboxSessionQuery:
        """SandboxSession 查询值对象"""
        tenant_id: UUID | None = None
        state: Literal["RUNNING", "TERMINATED", "FAILED"] | None = None
        idle_threshold: datetime | None = None  # last_activity_at < threshold
        offset: int = 0
        limit: int = 100
    ```
  - **领域扩展**：`async def find_by_query(query: SandboxSessionQuery) -> list[SandboxSession]` + `async def list_idle_sessions(threshold: datetime) -> list[SandboxSession]` + `async def count_active(tenant_id: UUID | None = None) -> int`
- **`InMemorySandboxSessionRepository`**：
  - **路径**：`src/infrastructure/storage/inmemory/sandbox_session_repository.py`
  - **模式复用 4.1a**：`dict[str, SandboxSession]`（**按 session_id 字符串索引，非 UUID**） + `asyncio.Lock` **类变量** + frozen dataclass
- **Alembic migration 014**：`deploy/postgresql/alembic/versions/014_sandbox_sessions.py`
  - **关键**：`down_revision = "013"`（参考 `013_schema_validation_records.py:30` 实际 `revision = "013"`）
  - `sandbox_sessions` 表 + 4 索引：tenant_id / (tenant_id, state) / (state, last_activity_at) / container_id UNIQUE
  - **主键**：`session_id VARCHAR(64) PRIMARY KEY`（字符串主键，不使用 UUID）

**验证标准/Validation Criteria:**

- [ ] `SandboxSession` 聚合根位于 `src/domain/entities/sandbox_session.py`（10 字段）
- [ ] `session_id` 正则校验 `^[A-Za-z0-9_-]{1,64}$`（防注入）
- [ ] `SandboxSessionRepositoryPort` 定义在 `src/domain/ports/`（领域层，非应用层）
- [ ] 查询方法使用 `SandboxSessionQuery` frozen dataclass（CLAUDE.md §4 决策规则）
- [ ] `InMemorySandboxSessionRepository` 使用 `asyncio.Lock` **类变量**（CLAUDE.md §6 Gotcha）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_sandbox_session_repository.py` **11 维度**覆盖
- [ ] Alembic migration `014_sandbox_sessions.py` 创建（**`down_revision = "013"`** + 4 索引 + UNIQUE container_id + VARCHAR(64) 主键）
- [ ] `composition_root.py` 注册 `sandbox_session_repository` 端口（**line 102 附近 import + line 821 之后新增 register_port**，lifetime=SCOPED，owner="sandbox-team"）

### AC-5: AioDockerSandboxAdapter 实现（替换 mock）

**Given** 既有 `DockerSandboxAdapter` 是 mock 实现（日志 + 字典记录），无法满足生产安全要求
**When** 实现 `AioDockerSandboxAdapter` 基于 `aiodocker` 真实 Docker daemon 通信
**Then**

- **mock 替换策略**（关键 P1 决策）：
  - **删除** `src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`（mock 不符合生产标准，避免 CLAUDE.md §5 mock 滥用）
  - 修改 `src/composition_root.py:817` 的 `sandbox_executor` impl 字符串为 `AioDockerSandboxAdapter`
  - 本地无 Docker 环境：通过 `SISYS_USE_TEST_PORTS=1` 环境变量切换（CLAUDE.md §6 既有约定，不引入 mock fallback）
- **路径**：`src/infrastructure/external_services/sandbox/aiodocker_sandbox_adapter.py`（**新建文件**）
- **核心实现**：
  - 构造器接受 `docker_socket: str = "unix:///var/run/docker.sock"` + `max_concurrent: int = 50`
  - `async def start_container(self, session_id, spec: ContainerSpec | None = None)`：
    1. 校验 `session_id` 正则 `^[A-Za-z0-9_-]{1,64}$`（防注入）→ 失败抛 `SandboxConfigurationError` (319)
    2. 构造容器名 `f"sisys-sandbox-{tenant_id[:8]}-{session_id[:32]}"`（tenant_id 取 UUID 前 8 字符，session_id 截前 32 字符，总长度 ≤ 56 字符 ≤ Docker 64 字符上限）→ 长度超限抛 `SandboxConfigurationError` (319)
    3. 校验并发数（`_running_count < max_concurrent`）→ 超限抛 `SandboxQuotaExceededError` (318)
    4. 镜像拉取 `await docker.pull(spec.image)` → 失败抛 `SandboxImagePullError` (315)
    5. 容器启动 `await docker.containers.run(spec.image, ...aiodocker_kwargs)` → 失败抛 `ContainerStartError` (312)
    6. 保存 `SandboxSession` 到仓储 → `await self._session_repo.save(session)`
    7. 发布 `SandboxSessionStarted` 事件（继承 DomainEvent 基类，双通道）
  - `async def execute_code(self, session_id, code, *, timeout_sec=None)`：
    1. `asyncio.wait_for(coro, timeout=timeout_sec)` → 超时抛 `SandboxTimeoutError` (316)
    2. `exec_create` + `exec_start` → 非零退出码 / STDERR 非空抛 `ExecutionError` (313)
    3. OOM kill（exit 137）抛 `SandboxResourceLimitExceededError` (317)
    4. 更新 `last_activity_at` → `await self._session_repo.save(session)`（用 state_version 乐观锁）
    5. 返回 `dict[str, Any]`（status / output / error / execution_time_ms），**保持 4.1a 既有契约**；强类型化推迟到 4.7
  - `async def stop_container(self, session_id)`：
    1. `docker.containers.get(container_id).delete(force=True)` → 失败抛 `ContainerStopError` (314)
    2. 更新 `SandboxSession.terminated_at` + `state="TERMINATED"`
    3. 发布 `SandboxSessionTerminated` 事件
  - `async def is_container_running(self, session_id)`：查询 Docker daemon 状态（**不查本地字典**，避免状态漂移）
  - `async def health_check(self)`：`docker.ping()` 成功返回 True，否则 False（**不抛异常**）
- **安全配置（aiodocker kwargs）**：
  - `mem_limit=f"{spec.mem_limit_mb}m"` + `memswap_limit=f"{spec.mem_limit_mb}m"`（禁止 swap）
  - `cpu_period=100000` + `cpu_quota=int(spec.cpu_quota * 100000)`
  - `pids_limit=spec.pids_limit`
  - `network_mode=spec.network_mode`
  - `read_only=spec.read_only_rootfs`
  - `tmpfs=spec.tmpfs_mounts`
  - `cap_drop=list(spec.cap_drop)`
  - `security_opt=list(spec.security_opt)`
  - `userns_mode=spec.userns_mode`
  - `name=f"sisys-sandbox-{tenant_id[:8]}-{session_id[:32]}"`（**总长度 ≤ 56 字符**，留 8 字符 buffer 应对 Docker 命名规则）
- **aiodocker 异常映射**：私有方法 `_map_docker_error(exc, session_id) -> SandboxError`，**不暴露 `str(exc)` 内部实现**
- **stubs/aiodocker/__init__.pyi**（PEP 561 stubs）：覆盖以下 9 个 API 面（**注意**：原文档描述只覆盖 6 个，遗漏关键 API 会触发 mypy `attr-defined` 错误）：
  - `Docker.pull(image)` — 镜像拉取
  - `Docker.ping()` — daemon 健康检查
  - `Docker.containers.run(image, **kwargs)` — 容器启动
  - `Docker.containers.get(container_id)` — 容器查询
  - `Docker.containers.list(filter=...)` — 孤儿容器扫描
  - `Docker.containers.delete(force=True)` — 容器删除
  - `Container.exec_create(cmd, ...)` — 执行命令创建
  - `Container.exec_start(exec_id, ...)` — 执行命令启动
  - `Container.stats(stream=False)` — 资源统计（性能基准）

**验证标准/Validation Criteria:**

- [ ] `AioDockerSandboxAdapter` 位于 `src/infrastructure/external_services/sandbox/aiodocker_sandbox_adapter.py`
- [ ] 实现 `SandboxExecutor` Protocol（既有 4 方法 + 新增 `health_check`）
- [ ] 5 类异常映射完整（镜像拉取 → 315 / 超时 → 316 / 资源超限 → 317 / 配额 → 318 / 配置 → 319）
- [ ] 容器名格式统一 `sisys-sandbox-{tenant_id[:8]}-{session_id[:32]}`，总长度 ≤ 56 字符
- [ ] 旧 `docker_sandbox_adapter.py` mock 文件**已删除**
- [ ] `composition_root.py:817` impl 字符串已切换至 `AioDockerSandboxAdapter`
- [ ] `session_id` 正则校验防注入
- [ ] `execute_code` 通过 `asyncio.wait_for` 实现超时控制
- [ ] 单元测试覆盖：mock aiodocker.Docker，验证所有方法调用路径 + 异常映射
- [ ] `stubs/aiodocker/__init__.pyi` 创建（PEP 561，覆盖 9 个 API 面）
- [ ] `pyproject.toml` **[tool.poetry.dependencies] 主分组** 新增 `aiodocker = "^0.21.0"`

### AC-6: 30 分钟空闲清理 + 孤儿容器回收

**Given** 沙箱会话默认 30 分钟无活动自动销毁（`or.md:232` 三.3.[2]）
**When** 实现空闲 TTL 清理机制
**Then**

- **重要决策**：**新增独立应用层服务** `SandboxSessionReaper`，**不修改**既有 `SessionNamespaceManager`（4.1a 既有实现无 TTL 机制）
- **应用层服务**：`src/application/services/sandbox_session_reaper.py`
  - **核心方法**：`async def reap_idle_sessions(threshold: datetime | None = None) -> int`（返回清理数量；`threshold` 默认 `now - settings.SANDBOX_IDLE_TIMEOUT_MINUTES * 60`，避免硬编码 30 分钟）
  - **逻辑**：
    1. 查询 `list_idle_sessions(threshold)` → 获取空闲会话列表
    2. 对每个空闲会话调用 `sandbox.stop_container(session_id)`
    3. 记录清理日志 + 更新 `SandboxSession.state="TERMINATED"`
    4. 发布 `SandboxSessionTerminated` 事件（`metadata={"reason": "idle_timeout"}`）
- **孤儿容器回收**：启动时扫描 daemon 上所有 `sisys-sandbox-*` 容器（`docker.containers.list(filters={"name": "sisys-sandbox-*"}))`），与本地 `SandboxSession` 仓储对比，差异容器（daemon 有但仓储无）强制清理
  - **安全边界**：孤儿扫描通配符仅匹配本系统 `sisys-sandbox-` 前缀，**避免误删其他项目容器**
  - **风险缓解**：同时校验 label `sisys.sandbox.session_id`（启动容器时设置）确保 100% 归属本系统
- **注册模式**：`sandbox_session_reaper` 作为应用层服务**注册为端口**（与既有 `tool_execution_engine` 模式一致），便于运行时 `resolver.resolve()` 注入调度器
- **注册到 composition_root.py**：`name="sandbox_session_reaper"`（lifetime=SINGLETON，owner="sandbox-team"，**line 2239 之后新增**）

**验证标准/Validation Criteria:**

- [ ] `SandboxSessionReaper` 位于 `src/application/services/sandbox_session_reaper.py`
- [ ] `reap_idle_sessions(threshold)` 返回清理数量（int），threshold 默认从 settings 读取（**非硬编码**）
- [ ] 启动时孤儿容器清理（`docker.containers.list(filters={"name": "sisys-sandbox-*"})` + label 校验）
- [ ] 单元测试覆盖：mock SandboxExecutor + SandboxSessionRepository，验证清理逻辑 + 默认 threshold 行为
- [ ] 集成测试覆盖：真实 Docker daemon + 模拟 30 分钟空闲（可用 `freezegun` 或通过 settings 缩短 TTL 至测试值）
- [ ] `composition_root.py` 注册 `sandbox_session_reaper`（lifetime=SINGLETON）

### AC-7: 应用层安全编排（ToolExecutionEngine 包裹器）

**Given** `ToolExecutionEngine` 既有签名 `__init__(self, sandbox: SandboxExecutor)` 必须保持（4.3 包裹器模式经验）
**When** 实现 `SandboxSecurityDecorator`（**包裹类 wrapper**，非 Python `@decorator` 语法）包裹 `ToolExecutionEngine`，添加超时 + 重试 + 安全校验
**Then**

- **路径**：`src/application/services/sandbox_security_decorator.py`
- **核心职责**：
  1. **超时控制**：`asyncio.wait_for(self.wrapped.sandbox.execute_code(...), timeout=ContainerSpec.timeout_sec)` → 超时抛 `SandboxTimeoutError` (316)
  2. **重试机制**：复用 `src/application/services/retry_helpers.py:62 _call_with_retry`（4.3 经验抽取），最大 3 次指数退避
  3. **会话配额检查**：执行前校验 `_running_count < MAX_CONCURRENT_CONTAINERS`
  4. **session_id 注入防御**：执行前再次校验 session_id 正则
  5. **事件发布**：捕获 STDERR 后发布 `SandboxExecutionFailed` 事件（继承 DomainEvent 基类，仅失败时）
- **包裹类模式**（4.3 经验）：**不修改** `ToolExecutionEngine.__init__`，通过 `composition_root.py` 注入包裹器实例
- **`composition_root.py` 装配**（关键 P0-3 修正 — 必须使用 **lambda + `__import__` 延迟加载**模式，保持与既有 `tool_execution_engine:2220-2239` 风格一致，避免破坏 composition_root.py 的 import 时序设计）：
  ```python
  register_port(
      name="tool_execution_engine",
      version="v1.0.0",
      interface=__import__(
          "src.application.ports.tool_execution_engine",
          fromlist=["ToolExecutionEnginePort"],
      ).ToolExecutionEnginePort,
      impl=lambda resolver: __import__(
          "src.application.services.sandbox_security_decorator",
          fromlist=["SandboxSecurityDecorator"],
      ).SandboxSecurityDecorator(
          wrapped=__import__(
              "src.application.services.tool_execution_engine",
              fromlist=["ToolExecutionEngine"],
          ).ToolExecutionEngine(
              llm_client=resolver.resolve("llm_client"),
              sandbox=resolver.resolve("sandbox_executor"),
              tool_execution_repository=resolver.resolve("tool_execution_repository"),
          ),
          sandbox=resolver.resolve("sandbox_executor"),
      ),
      module="src.application.services.sandbox_security_decorator",
      lifetime=Lifetime.SCOPED,
      owner="tool-team",
      tags=("tool", "execution", "engine", "security"),
  )
  ```

**验证标准/Validation Criteria:**

- [ ] `SandboxSecurityDecorator` 位于 `src/application/services/sandbox_security_decorator.py`（**包裹类，非 `@decorator` 语法**）
- [ ] **不修改** `ToolExecutionEngine.__init__` 签名（4.3 经验）
- [ ] 超时控制使用 `asyncio.wait_for`
- [ ] 重试复用 `_call_with_retry`（最大 3 次指数退避）
- [ ] 单元测试覆盖：mock SandboxExecutor，验证超时 / 重试 / 配额 / session_id 校验
- [ ] 集成测试覆盖：真实 Docker daemon + 验证 30s 超时触发
- [ ] `composition_root.py:2220-2239` 的 `tool_execution_engine` lambda impl **已修改**为嵌套 `SandboxSecurityDecorator`（**注意**：与既有 4.1a 既有 `ToolExecutionEngine` 直接实例化不兼容，需要单独评估向后兼容路径）

### AC-8: 集成测试（testcontainers-python 真实 Docker daemon）

**Given** 沙箱执行涉及真实 Docker daemon，集成测试必须使用真实服务（CLAUDE.md §5 Mock/Fake/Real 三层策略）
**When** 创建集成测试套件
**Then**

- **路径**：`tests/integration/test_docker_sandbox_integration.py`（**epics AC 5 要求路径**，非 `test_integration_docker_sandbox.py`）
- **核心测试场景**：
  1. **容器启动 + 代码执行 + 停止** 完整生命周期（自包含：testcontainers 上下文管理器）
  2. **网络隔离验证**：`network_mode="none"` 容器内 `curl https://api.example.com` 应失败（连接超时）
  3. **资源限制验证**：分配 `mem_limit=128m`，执行 `python -c "x=[1]*10**8"` 应触发 OOM kill（exit 137 → `SandboxResourceLimitExceededError`）
  4. **只读文件系统验证**：容器内 `echo "x" > /etc/test` 应失败（Read-only file system）
  5. **进程数限制验证**：`pids_limit=10`，执行 fork bomb 应被 cgroups 杀死
  6. **沙箱逃逸测试**：尝试 `chroot /` / `mount` / `ptrace` 等系统调用应被 seccomp 阻止
  7. **并发测试**：启动 10 个并发会话，验证全部成功（与 AC-9 性能要求一致）
- **testcontainers 配置**：
  - 使用 `DockerContainer("python:3.11-slim@sha256:<digest>")` 启动测试用 Python 环境
  - fixture 上下文管理器自动清理（`with DockerContainer(...) as container:`）
- **pytest 标记**：`@pytest.mark.integration` + `@pytest.mark.docker`（动态 `pytest.skip()` 若 daemon 不可用）

**验证标准/Validation Criteria:**

- [ ] `tests/integration/test_docker_sandbox_integration.py`（epics AC 5 要求路径）
- [ ] 7 项核心场景全部覆盖（启动 / 网络 / 资源 / 只读 / pids / 逃逸 / 并发）
- [ ] 使用 `testcontainers-python` ≥ 4.13.0 真实 Docker daemon
- [ ] 自包含（testcontainers 上下文管理器自动清理）
- [ ] 动态 `pytest.skip()` 若 Docker daemon 不可用（不写死 `@pytest.mark.skip`）
- [ ] `pyproject.toml` 新增依赖 `testcontainers = {extras = ["docker"], version = "^4.13.0"}`
- [ ] **禁止 mock** Docker SDK（CLAUDE.md §5 集成测试真实服务原则）

### AC-9: 性能 + 安全架构验证测试

**Given** Epic 4 AC 性能要求：沙箱启动延迟 P95 < 5s、并发 ≥ 10、沙箱逃逸 0 次
**When** 创建架构验证测试 + 性能基准测试
**Then**

- **架构验证测试**：`tests/unit/architecture/test_docker_sandbox.py`（**关键 P0-2 修正**：epics_v1.0.md:1204 硬要求此路径，**不带 `_arch_` 前缀**）
  - **域层零依赖**：`poetry run lint-imports` 必须通过（domain 不依赖 aiodocker）
  - **依赖方向矩阵**：`src/domain/` ← `src/application/services/sandbox_security_decorator.py` ← `src/infrastructure/external_services/sandbox/aiodocker_sandbox_adapter.py`
  - **循环依赖检测**：复用既有 `lint-imports`（基于 importlinter）+ `from __future__ import annotations` + AST 静态分析脚本（**注意**：ruff 的 E 规则**不包含**循环依赖检测能力，不能仅用 ruff --select E）
  - **PortSpec 元数据完整性**（关键 P1-1 修正）：3 个端口（`sandbox_executor` / `sandbox_session_repository` / `sandbox_session_reaper`）的 **10 字段**完整性（`name / version / interface / impl / module / lifetime / owner / compatibility / tags / deprecated`）
  - **异常代码唯一性**：EXCEPTION_315~319 与既有代码无碰撞
- **性能基准测试**：`tests/integration/test_performance_docker_sandbox.py`
  - **启动延迟**：连续启动 20 个容器，P95 < 5s（使用 `pytest-benchmark`）
  - **并发能力**：≥ 10 并发会话（与 AC-8 并发测试一致，但作为性能基准）
  - **沙箱逃逸**：跑已知逃逸 CVE 测试集（脱敏后），验证 0 次逃逸
- **测试标记**：`@pytest.mark.benchmark` + `@pytest.mark.slow`（启动延迟测试 mark slow）

**验证标准/Validation Criteria:**

- [ ] `tests/unit/architecture/test_docker_sandbox.py`（**epics AC 5 硬要求路径，无 `_arch_` 前缀**）
- [ ] 4 项架构验证规则全部通过（域层零依赖 + 依赖方向 + 无循环 + PortSpec 10 字段元数据）
- [ ] 性能基准测试 P95 < 5s（启动延迟）
- [ ] 并发 ≥ 10 通过
- [ ] 沙箱逃逸测试 0 次逃逸
- [ ] 集成测试覆盖率 ≥ 75%（epics AC 3 要求）
- [ ] 应用层覆盖率 ≥ 85%（epics AC 3 要求）

### AC-10: BDD 验收测试（Gherkin 中文）

**Given** Story 需通过 Gherkin 验收（CLAUDE.md §5 强制）
**When** 创建中文 Gherkin feature 文件 + BDD step 实现
**Then**

- **Feature 文件**：`tests/acceptance/test_acceptance_docker_sandbox.feature`

  - 文件结构对齐 `test_acceptance_strategic_tool_impl.feature:1-134` + `test_acceptance_tool_io_schema_validation.feature:1-9` 样板：
    - 第 1 行：`# language: zh-CN`
    - 第 2 行：Story 注释（如 `# Story 4.4 — Docker 沙箱执行(BDD 验收场景,完整覆盖 10 条 AC)`）
    - `功能:` 三段式段落（角色 + 需求 + 目的）
    - `背景:` 段落（共用前置条件）
    - 按 AC 编号分组（`# ====` 注释分隔）
    - **场景命名规范**：`场景: AC-N.M - 中文细分描述`（**对齐 4.1a `AC-1a` 与 4.3 `AC-1.1` 样板**）
    - **异常断言双行**：场景 `那么 抛出 XXX异常` + `并且 错误码为 EXCEPTION_xxx`
  - **场景清单**（**完整覆盖 AC-1 ~ AC-10**，对齐 4.1a 5 个 AC + 4.3 8 个 AC 的组织密度）：
    - **场景组 1: AC-1 ContainerSpec 值对象 + 不变量校验**（6 项不变量场景）
      - AC-1.1 ~ AC-1.6: 13 字段构造成功 / 6 项不变量失败 / 默认值验证 / 网络模式 / image 正则 / 不可变冻结
    - **场景组 2: AC-2 5 个新沙箱异常 EXCEPTION_315~319**（5 项异常构造场景）
      - AC-2.1: `SandboxImagePullError` code == `EXCEPTION_315`
      - AC-2.2: `SandboxTimeoutError` code == `EXCEPTION_316` + context.timeout_sec
      - AC-2.3: `SandboxResourceLimitExceededError` code == `EXCEPTION_317` + limit_type="mem"
      - AC-2.4: `SandboxQuotaExceededError` code == `EXCEPTION_318` + current_count/max_count
      - AC-2.5: `SandboxConfigurationError` code == `EXCEPTION_319` + field_name
      - AC-2.6: HTTP 映射（502 / 504 / 503 / 502 / 502）
    - **场景组 3: AC-3 SandboxExecutor 端口向后兼容扩展**
      - AC-3.1 ~ AC-3.5: 4 个既有方法签名 + 默认参数 + 新增 `health_check()` + runtime_checkable
    - **场景组 4: AC-4 SandboxSession + Repository**（场景密度参考 4.1a AC-5）
      - AC-4.1 ~ AC-4.4: 10 字段构造 / session_id 正则校验 / Repository CRUD / Alembic migration 014
    - **场景组 5: AC-5 AioDockerSandboxAdapter 实现**（核心安全场景）
      - AC-5.1: Happy Path 启动 → 执行 → 停止
      - AC-5.2: 网络隔离（`network_mode=none`）
      - AC-5.3: 资源限制（OOM kill）
      - AC-5.4: 只读文件系统
      - AC-5.5: 进程数限制
      - AC-5.6: 沙箱逃逸 0 次
    - **场景组 6: AC-6 30 分钟空闲清理 + 孤儿容器回收**
      - AC-6.1 ~ AC-6.3: TTL 清理 / 孤儿扫描 / `SandboxSessionReaper.reap_idle_sessions()` 验证
    - **场景组 7: AC-7 SandboxSecurityDecorator 包裹类**
      - AC-7.1 ~ AC-7.4: 4 项防护（超时 / 重试 / 配额 / session_id 注入防御）+ 不修改 `ToolExecutionEngine.__init__`
    - **场景组 8: AC-8 集成测试**（testcontainers 真实 Docker daemon）
      - AC-8.1 ~ AC-8.4: 启动延迟 P95 < 5s / 并发 ≥ 10 / 沙箱逃逸 0 / testcontainers 自动清理
    - **场景组 9: AC-9 性能 + 安全架构验证**
      - AC-9.1 ~ AC-9.3: 性能基准 / 域层零依赖 / PortSpec 10 字段元数据
    - **场景组 10: AC-10 端口注册**（对齐 4.1a AC-5）
      - AC-10.1: 3 个新端口已注册（sandbox_executor / sandbox_session_repository / sandbox_session_reaper）
      - AC-10.2: 端口元数据完整（10 字段：name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated）

- **BDD step 文件**：`tests/acceptance/test_acceptance_docker_sandbox.py`

  - 文件结构对齐 `test_acceptance_strategic_tool_impl.py:1-130` 样板：
    - 文件头 docstring 说明样板 + **6 项关键约定**（**关键**：对齐 4.1a 样板）：
      1. 步骤函数使用 `@given / @when / @then` 装饰器 + `context: dict[str, Any]` fixture
      2. 使用**真实服务实例**：`InMemorySandboxSessionRepository` + 真实 `AioDockerSandboxAdapter`（**禁止 mock**，CLAUDE.md §5 红线）
      3. 步骤**严格按 AC 顺序**（AC-1 ~ AC-10），`# ====` 分隔
      4. 异常处理：使用 `try/except` 捕获到 `context["query_error"]`，Then 步骤断言 `isinstance + error.code`
      5. **禁止 mock** 核心域服务（CLAUDE.md §5 红线）；仅允许 mock 端口适配器（与 4.1a 样板一致）
      6. Docker daemon 不可用时使用 `pytest.skip()` 动态跳过（**禁止**写死 `@pytest.mark.skip`）
    - `from __future__ import annotations`
    - 标准库 + pytest + pytest_bdd + domain/infrastructure import
    - `scenarios("test_acceptance_docker_sandbox.feature")` 一行加载
  - **共享 fixtures**：
    ```python
    @pytest.fixture
    def context() -> dict[str, Any]:
        """BDD 步骤间共享状态容器。"""
        return {}

    @pytest.fixture
    def sandbox_session_repository() -> InMemorySandboxSessionRepository:
        """真实 InMemory 沙箱会话仓储（CLAUDE.md §5 真实服务原则）。"""
        return InMemorySandboxSessionRepository()

    @pytest.fixture(scope="module")
    def event_loop():
        """模块级事件循环，用于 run_until_complete()"""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    def _run_async(coro: Any) -> Any:
        """同步调度异步协程（参考 test_acceptance_strategic_tool_impl.py:424-430）。"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_sandbox_adapter() -> AioDockerSandboxAdapter:
        """构造真实 AioDockerSandboxAdapter（连接真实 Docker daemon）。"""
        # 动态跳过: 若 Docker daemon 不可用, pytest.skip()
        ...
    ```
  - **`@pytest.mark.asyncio` 禁止用于 step 函数**（CLAUDE.md §5 红线 + Story 4.3 commit `099423f1` 经验）
  - **Step 函数形态**：**同步 `def`**（不是 `async def`）— pytest-bdd 8.x 限制（项目 52/52 acceptance 文件遵循）
  - **异步代码调度**：通过 `event_loop.run_until_complete(coro)` 驱动（参考 `test_acceptance_strategic_tool_impl.py:424-430` 样板）
  - **异常断言模式**（对齐 4.1a 样板 `test_acceptance_strategic_tool_impl.py`）：
    ```python
    @when("构造 ContainerSpec 内存限制 2049MB")
    def when_construct_container_spec_invalid(context: dict[str, Any]) -> None:
        try:
            ContainerSpec(image="python:3.11-slim@sha256:xxx", mem_limit_mb=2049)
            context["query_error"] = None
        except EntityValidationError as e:
            context["query_error"] = e

    @then("抛出 EntityValidationError")
    def then_entity_validation_error(context: dict[str, Any]) -> None:
        assert context["query_error"] is not None
        assert isinstance(context["query_error"], EntityValidationError)

    @then("错误码为 EXCEPTION_242")
    def then_error_code_242(context: dict[str, Any]) -> None:
        assert context["query_error"].code == "EXCEPTION_242"
    ```
  - context 通过 `context: dict[str, Any]` 跨步骤传递
  - 使用真实 Docker daemon（`pytest.skip()` 若不可用，**禁止 mock**）

**验证标准/Validation Criteria:**

- [ ] `tests/acceptance/test_acceptance_docker_sandbox.feature` 第 1 行 `# language: zh-CN` + 第 2 行 Story 注释
- [ ] Feature 文件包含 **功能:** 三段式（角色 + 需求 + 目的）+ **背景:** 前置条件
- [ ] Feature 文件**完整覆盖 10 个 AC 分组**（AC-1 ~ AC-10，每组 ≥ 1 子场景）
- [ ] 场景命名规范：`场景: AC-N.M - 中文细分描述`（**对齐 4.1a `AC-1a` 与 4.3 `AC-1.1` 样板**）
- [ ] 异常场景双断言：`那么 抛出 XXX异常` + `并且 错误码为 EXCEPTION_xxx`
- [ ] Gherkin 关键字使用中文（`功能:` / `场景:` / `假如` / `当` / `那么` / `并且`，**沿用项目既有约定**）
- [ ] `tests/acceptance/test_acceptance_docker_sandbox.py` 实现所有 step 函数 + 文件头 docstring **6 项关键约定**
- [ ] step 函数使用 **同步 `def`**（不是 `async def`），通过 `event_loop.run_until_complete()` 调度异步代码（**关键**：对齐 `test_acceptance_strategic_tool_impl.py:424-430` 样板）
- [ ] **`@pytest.mark.asyncio` 禁止用于 step 函数**（CLAUDE.md §5 红线）
- [ ] **异常断言模式**：try/except + `context["query_error"]` + `isinstance + error.code`（对齐 4.1a 样板）
- [ ] **禁止 mock** 核心域服务（CLAUDE.md §5 红线）；仅允许 mock 端口适配器（对齐 4.1a 样板）
- [ ] Docker daemon 不可用时 `pytest.skip()`（**禁止**写死 `@pytest.mark.skip`）
- [ ] 全部场景通过（Happy Path + 异常路径 + 端口注册 + 性能基准）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] 事件定义位于 `src/domain/events/sandbox_events.py`
- [ ] 使用标准库 `dataclass(frozen=True)` 实现领域事件校验，**禁止在领域层依赖 Pydantic**
- [ ] 事件命名符合规范：`SandboxSessionStarted` / `SandboxSessionTerminated` / `SandboxExecutionFailed`
- [ ] 事件继承 `DomainEvent` 基类，使用基类 `event_id: UUID` + `timestamp: datetime`（**注意**：基类字段名为 `timestamp`，不是 `occurred_at`；参考 `src/domain/events/base.py:42-69` 12 字段基类契约）
- [ ] 在 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 同步注册双通道映射

#### 数据模型 (Data Models)

- [ ] `ContainerSpec` 值对象定义于 `src/domain/value_objects/container_spec.py`
- [ ] `SandboxSession` 聚合根定义于 `src/domain/entities/sandbox_session.py`
- [ ] `SandboxSessionQuery` 查询值对象定义于 `src/domain/ports/sandbox_session_repository.py`
- [ ] 全部使用 `dataclass(frozen=True)`，**禁止 Pydantic**

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `SandboxExecutor` Protocol 向后兼容扩展（`src/domain/ports/sandbox_executor.py`）
- [ ] `SandboxSessionRepositoryPort` 新增（`src/domain/ports/sandbox_session_repository.py`）
- [ ] `SandboxSecurityDecorator` 应用层服务（**非端口**，组合注入 `SandboxExecutor` + `SandboxSessionRepository`）
- [ ] `SandboxSessionReaper` 应用层服务（**非端口**，组合注入 `SandboxExecutor` + `SandboxSessionRepository`）
- [ ] `composition_root.py` 注册：`sandbox_executor`（既有，impl 切换至 `AioDockerSandboxAdapter`）+ `sandbox_session_repository`（新增）+ `sandbox_session_reaper`（新增）
- [ ] 端口契约测试：`test_port_contract_sandbox_executor.py`（既有扩展）+ `test_port_contract_sandbox_session_repository.py`（新增）

#### 端口契约清单执行约束（强制）

- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

- [ ] 5 个新异常类定义于 `src/domain/exceptions/sandbox_exceptions.py`（EXCEPTION_315~319）
- [ ] `_code_ranges.py` 子域映射注册 5 行
- [ ] `__init__.py` 暴露 + `__all__` 扩展 5 项
- [ ] `EXCEPTION_HTTP_MAP` 注册 5 条新映射
- [ ] 三条 grep 自查零输出
- [ ] 子域范围校验 + 编码唯一性测试通过

#### API 契约 (API Contract)

- [ ] `SandboxExecutor` Protocol 扩展签名确定（向后兼容）
- [ ] 容器名格式 `sisys-sandbox-{tenant_id[:8]}-{session_id[:32]}` 确定（**总长度 ≤ 56 字符**，在 Docker 64 字符上限内；tenant_id 取 UUID 前 8 字符，session_id 截前 32 字符）
- [ ] 安全配置字典（aiodocker kwargs）确定
- [ ] 无新增 HTTP 端点（沙箱执行通过 ToolExecutionEngine 间接调用）

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**

| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**

- 领域层（`src/domain/`）仅使用 Python 标准库
- **禁止** `aiodocker` / `docker` / `testcontainers` 等任何第三方包进入领域层
- 仅 `stubs/aiodocker/__init__.pyi` 提供类型提示（PEP 561 stubs）

**依赖方向矩阵**

| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_docker_sandbox.feature`（7 项场景）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_docker_sandbox.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**

- **Step 函数形态**：**同步 `def`**（不是 `async def`）— pytest-bdd 8.x 限制（项目 52/52 acceptance 文件遵循）
- **异步代码调度**：通过 `event_loop.run_until_complete(coro)` 驱动
  - Pattern A（推荐）：自建 module 级 `event_loop` fixture + `_run_async()` helper（参考 `test_acceptance_strategic_tool_impl.py:424-430`）
  - Pattern B：直接消费 pytest-asyncio 内建 `event_loop` fixture
- **`@pytest.mark.asyncio` 禁止用于 step 函数**（CLAUDE.md §5 红线 + Story 4.3 commit `099423f1` 经验，会导致 context data 丢失）
- **`asyncio_mode = "auto"`** 全局开启（pyproject.toml:274），**仅用于非 BDD 的 async fixture/test 函数**，**不驱动 BDD step**
- 同一中文文本可能需要同时支持 given/when 装饰器
- **Edge Cases 必须包含异常路径** — 至少覆盖：资源不存在（404 → 容器未启动 404）、权限不足（403 → 配置错误 403）、资源冲突（409 → 并发配额 503），响应体验证 `error.code` + `error.message` + `request_id`

**Task 0 完成标志：**

- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**

- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | `ContainerSpec` 值对象 | 不变量校验 | `tests/unit/domain/value_objects/test_container_spec.py` | Task 1 |
| **TDD 单元测试** | `SandboxSession` 聚合根 | 字段不变量 + session_id 正则 | `tests/unit/domain/entities/test_sandbox_session.py` | Task 2 |
| **TDD 单元测试** | 5 个新沙箱异常 | 构造器 / `to_dict()` / HTTP 映射 / 编码唯一性 | `tests/unit/domain/exceptions/test_sandbox_exceptions.py` | Task 0 / Task 3 |
| **TDD 单元测试** | `SandboxExecutor` Protocol 扩展 | 向后兼容验证 | `tests/unit/domain/ports/test_sandbox_executor_port.py`（既有扩展） | Task 4 |
| **TDD 单元测试** | `SandboxSessionRepository` | InMemory 实现 + asyncio.Lock 类变量 | `tests/unit/infrastructure/storage/test_sandbox_session_repository.py` | Task 2 |
| **TDD 单元测试** | `AioDockerSandboxAdapter` | mock aiodocker.Docker 验证调用路径 + 异常映射 | `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_sandbox_adapter.py` | Task 5 |
| **TDD 单元测试** | `SandboxSessionReaper` | mock 验证清理逻辑 | `tests/unit/application/services/test_sandbox_session_reaper.py` | Task 6 |
| **TDD 单元测试** | `SandboxSecurityDecorator` | mock 验证超时 / 重试 / 配额 / session_id 校验 | `tests/unit/application/services/test_sandbox_security_decorator.py` | Task 7 |
| **TDD 契约测试** | `SandboxExecutor` | 11 维度 + 向后兼容 | `tests/contracts/test_port_contract_sandbox_executor.py`（既有扩展） | Task 4 |
| **TDD 契约测试** | `SandboxSessionRepositoryPort` | 11 维度 | `tests/contracts/test_port_contract_sandbox_session_repository.py` | Task 2 |
| **TDD 契约测试** | `SandboxEvents` | 字段必填 + 序列化 + 通道双投递 | `tests/contracts/test_event_contract_sandbox_events.py` | Task 0 |
| **TDD 契约测试** | `ContainerSpec` 值对象 | 不变量校验 | `tests/contracts/test_value_object_contract_container_spec.py` | Task 1 |
| **SDD 架构验证** | 域层零依赖 + 依赖方向 + 端口元数据 | 4 项规则 | `tests/unit/architecture/test_docker_sandbox.py`（epics AC 5 硬要求） | Task 9 |
| **集成测试** | testcontainers-python 真实 Docker daemon | 7 项场景（启动 / 网络 / 资源 / 只读 / pids / 逃逸 / 并发） | `tests/integration/test_docker_sandbox_integration.py` | Task 8 |
| **性能基准** | 启动延迟 P95 < 5s + 并发 ≥ 10 + 沙箱逃逸 0 | 3 项基准 | `tests/integration/test_performance_docker_sandbox.py` | Task 9 |
| **TDD 验收测试** | Gherkin 7 项场景 | Happy Path + Edge Cases | `tests/acceptance/test_acceptance_docker_sandbox.feature` + `.py` | Task 0 + Task 10 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥ 85%**（epics AC 3 强制要求）
- [ ] **集成测试覆盖率 ≥ 75%**（epics AC 3 强制要求）
- [ ] **域层覆盖率 ≥ 90%**（CLAUDE.md §4 标准）
- [ ] **关键路径覆盖率 100%**（沙箱启动 / 执行 / 停止 / 健康检查）

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`），**含 `stubs/aiodocker/__init__.pyi` PEP 561 stubs**
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [ ] **Bandit 检查通过**（pre-commit 内置，跳过项不变）

#### 测试隔离约束（CLAUDE.md §5 强化版）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**沙箱测试专项约束：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **容器命名** | 容器名含 TestTenant UUID 前缀（`sisys-sandbox-{tenant_id[:8]}-{session_id[:32]}`，tenant_id 含 uuid 前缀） | 容器冲突 / 误删其他测试容器 |
| **容器清理** | testcontainers-python 上下文管理器自动清理（**禁止** `docker rm -f`） | 孤儿容器污染 daemon |
| **Schema 隔离** | `sandbox_sessions` 表按 tenant_id 隔离 + savepoint rollback | 数据污染 |
| **asyncio 上下文** | `asyncio.Lock` 类变量；处理 thread.ident 为 None | 锁失效 |
| **BDD async 配合** | BDD 步骤函数使用**同步 `def`** + `event_loop.run_until_complete()` 调度异步代码（项目 52/52 acceptance 文件模式）；**禁止** `@pytest.mark.asyncio` 用于 step 函数（CLAUDE.md §5 红线） | context 数据丢失 / 模式冲突 |
| **外部服务隔离** | Docker daemon 测试用 testcontainers；CI runner 需预装 Docker | 测试失败 |
| **动态跳过** | Docker daemon 不可用时 `pytest.skip()` | 写死 `@pytest.mark.skip` 导致无 Daemon 环境永远失败 |

**禁止行为：**

- ❌ 集成测试手动 `docker rm` / `docker network rm`（应用 testcontainers 自动清理）
- ❌ autouse fixture 删除全局匹配容器（如 `sisys-sandbox-*`）
- ❌ `asyncio.Lock` 使用实例变量
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`

**验证要求：**

- [ ] 并行测试 `pytest tests/ -n 8` 通过（除 `test_performance_*` 与 `test_integration_*` 因 Docker daemon 资源限制不并行）
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过（含 `stubs/aiodocker/__init__.pyi`）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | ContainerSpec 值对象 + 不变量校验 | Task 1 | **1.1 - 1.4**（含 1.4 契约测试） | `test_container_spec.py` / `test_value_object_contract_container_spec.py` |
| AC-2 | 5 个新沙箱异常（EXCEPTION_315-319） | Task 3 | **3.1 - 3.5**（含 3.5 测试运行验证） | `test_sandbox_exceptions.py` |
| AC-3 | SandboxExecutor 端口向后兼容扩展 | Task 4 | **4.1 - 4.4**（含 4.4 契约测试 8→11 维度扩展） | `test_sandbox_executor_port.py`（既有扩展） |
| AC-4 | SandboxSession 聚合根 + Repository 端口 | Task 2 | **2.1 - 2.8**（含 TDD 循环 [A] 2.1-2.3 + TDD 循环 [B] 2.4-2.8） | `test_sandbox_session.py` / `test_sandbox_session_repository.py` / `test_port_contract_sandbox_session_repository.py` / `014_sandbox_sessions.py` |
| AC-5 | AioDockerSandboxAdapter 实现 | Task 5 | **5.1 - 5.6** | `test_aiodocker_sandbox_adapter.py` |
| AC-6 | 30 分钟空闲清理 + 孤儿容器回收 | Task 6 | **6.1 - 6.4**（含 6.4 composition_root 注册） | `test_sandbox_session_reaper.py` |
| AC-7 | SandboxSecurityDecorator 应用层 | Task 7 | **7.1 - 7.4** | `test_sandbox_security_decorator.py` |
| AC-8 | 集成测试（testcontainers） | Task 8 | **8.1 - 8.4** | `test_docker_sandbox_integration.py` |
| AC-9 | 性能 + 安全架构验证测试 | Task 9 | **9.1 - 9.7**（含 9.5 性能基准 + 9.6 循环依赖 + 9.7 完整测试） | `test_docker_sandbox.py` / `test_performance_docker_sandbox.py` |
| AC-10 | BDD 验收测试（Gherkin 中文） | Task 0 + Task 10 | **0.5-0.7 + 10.1-10.5** | `test_acceptance_docker_sandbox.feature` / `.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-2 / AC-10

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定义 `SandboxSessionStarted` / `SandboxSessionTerminated` / `SandboxExecutionFailed` 领域事件（`src/domain/events/sandbox_events.py`）
- [ ] Subtask 0.2: 在 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 注册 3 个事件双通道映射（realtime + reliable）
- [ ] Subtask 0.3: 创建 5 个新沙箱异常类 EXCEPTION_315~319（`src/domain/exceptions/sandbox_exceptions.py` 扩展）
- [ ] Subtask 0.4: 在 `_CLASS_TO_SUBDOMAIN` 注册 5 行 + `EXCEPTION_HTTP_MAP` 注册 5 条映射
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_docker_sandbox.feature`（7 项场景）
- [ ] Subtask 0.6: 编写 BDD 步骤骨架 `tests/acceptance/test_acceptance_docker_sandbox.py`（使用 pytest-bdd `scenarios()` 批量绑定，禁止 `@pytest.mark.asyncio`）
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**

- [ ] 规范项全部定义完毕
- [ ] Gherkin 验收测试运行失败（预期行为，红阶段确认）
- [ ] 三条 grep 自查零输出

---

### Task 1: ContainerSpec 值对象（领域层）

**关联 AC:** AC-1

> **职责：** 单一职责，**仅**定义不可变容器规格值对象 + 6 项不变量校验。

#### TDD 循环 [A]：`ContainerSpec` 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_container_spec.py`（**12 字段** + 6 项不变量失败测试） |
| 🟢 绿 | 实现 `ContainerSpec` 最小代码（`@dataclass(frozen=True)` + `__post_init__`） |
| 🔄 重构 | 优化不变量校验（提取 `_validate_field()` 私有方法，提升可读性） |

- [ ] Subtask 1.1: 🔴 红 — 编写 `ContainerSpec` 失败测试（**12 字段** + 6 项不变量）
- [ ] Subtask 1.2: 🟢 绿 — 实现 `ContainerSpec` 最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化不变量校验代码
- [ ] Subtask 1.4: 契约测试 `tests/contracts/test_value_object_contract_container_spec.py` 通过

**完成标准/Definition of Done:**

- [ ] `ContainerSpec` 实现完成（**12 字段** + 6 项不变量）
- [ ] TDD 循环全部通过
- [ ] 域层覆盖率 ≥ 90%
- [ ] 域层零依赖验证通过（`poetry run lint-imports`）

---

### Task 2: SandboxSession 聚合根 + Repository 端口（领域层 + 基础设施层）

**关联 AC:** AC-4

> **职责：** 定义会话聚合根（含 session_id 注入防御）+ 仓储端口 + InMemory 实现 + Alembic migration 014。

#### TDD 循环 [A]：`SandboxSession` 聚合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_sandbox_session.py`（10 字段 + session_id 正则 + 终态 invariants） |
| 🟢 绿 | 实现 `SandboxSession` 最小代码 |
| 🔄 重构 | 提取 `SESSION_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")` 常量 |

- [ ] Subtask 2.1: 🔴 红 — 编写 `SandboxSession` 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `SandboxSession` 聚合根
- [ ] Subtask 2.3: 🔄 重构 — 提取正则常量 + 优化不变量

#### TDD 循环 [B]：`SandboxSessionRepository` 端口 + InMemory 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_sandbox_session_repository.py`（CRUD + list_idle_sessions + count_active） |
| 🟢 绿 | 实现 `SandboxSessionRepositoryPort` Protocol + `InMemorySandboxSessionRepository` |
| 🔄 重构 | 提取 `_lock: asyncio.Lock` 类变量 + 优化并发安全 |

- [ ] Subtask 2.4: 🔴 红 — 编写 Repository 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 Repository 端口 + InMemory 实现
- [ ] Subtask 2.6: 🔄 重构 — 优化并发安全
- [ ] Subtask 2.7: 契约测试 `tests/contracts/test_port_contract_sandbox_session_repository.py` 11 维度
- [ ] Subtask 2.8: Alembic migration `014_sandbox_sessions.py`（**`down_revision = "013"`** + 4 索引 + UNIQUE container_id + `session_id VARCHAR(64) PRIMARY KEY`）

**完成标准/Definition of Done:**

- [ ] `SandboxSession` + `SandboxSessionRepository` 全部实现
- [ ] TDD 循环 A / B 全部通过
- [ ] 端口契约测试 11 维度通过
- [ ] Alembic migration 014 创建
- [ ] `composition_root.py` 注册 `sandbox_session_repository`（SCOPED）

---

### Task 3: 5 个新沙箱异常（领域层）

**关联 AC:** AC-2

> **职责：** 扩展 `sandbox_exceptions.py` 新增 5 个异常类（EXCEPTION_315~319），完成 **5 项 Checklist**（含 1 项 EXCEPTION_HTTP_MAP 注册）。

#### TDD 循环 [A]：5 个新异常类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_sandbox_exceptions.py`（5 个新异常类测试 + 既有 4 个回归测试） |
| 🟢 绿 | 实现 5 个异常类（继承既有 `SandboxError` / `ContainerStartError` / `ExecutionError`） |
| 🔄 重构 | 提取公共构造器逻辑到基类（**保留** 5 个独立异常类的语义清晰性） |

- [ ] Subtask 3.1: 🔴 红 — 编写 5 个新异常类失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 5 个新异常类
- [ ] Subtask 3.3: 🔄 重构 — 优化异常构造器（提取公共逻辑）
- [ ] Subtask 3.4: `_code_ranges.py` 注册 5 行 + `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP` 注册 5 条
- [ ] Subtask 3.5: 运行 `test_code_ranges.py` + `test_error_code_uniqueness.py` + `test_exception_handlers.py` 验证通过

**完成标准/Definition of Done:**

- [ ] 5 个新异常类实现完成
- [ ] TDD 循环全部通过
- [ ] **5 项 Checklist**全部完成（含 EXCEPTION_HTTP_MAP 注册）
- [ ] 三条 grep 自查零输出

---

### Task 4: SandboxExecutor 端口向后兼容扩展（领域层）

**关联 AC:** AC-3

> **职责：** 扩展既有 `SandboxExecutor` Protocol，保持 4.1a 既有 4 方法**调用行为**（默认参数扩展，`inspect.signature()` 反映但既有调用点零修改）+ 通过默认参数扩展入参 + 新增 `health_check()` 方法。

#### TDD 循环 [A]：Protocol 向后兼容扩展

| 阶段 | 动作 |
|------|------ |
| 🔴 红 | 扩展 `tests/unit/domain/ports/test_sandbox_executor_port.py`（既有 4 方法回归 + 新增 2 方法 + health_check） |
| 🟢 绿 | 扩展 `SandboxExecutor` Protocol（默认参数 + 新增方法） |
| 🔄 重构 | 优化 Protocol docstring，明确向后兼容语义 |

- [ ] Subtask 4.1: 🔴 红 — 编写 Protocol 扩展失败测试
- [ ] Subtask 4.2: 🟢 绿 — 扩展 Protocol（默认参数 + health_check）
- [ ] Subtask 4.3: 🔄 重构 — 优化 Protocol docstring
- [ ] Subtask 4.4: 契约测试 `tests/contracts/test_port_contract_sandbox_executor.py` **从既有 8 维度扩展至 11 维度**（新增 port_version / port_owner / port_module）+ 向后兼容验证

**完成标准/Definition of Done:**

- [ ] `SandboxExecutor` Protocol 向后兼容扩展完成
- [ ] 4 个既有方法**调用行为保持不变**（默认参数扩展，`inspect.signature()` 反映但既有调用点零修改）
- [ ] 既有契约测试 8 维度 + 既有单元测试**全部通过**（不修改既有测试代码）
- [ ] 域层零依赖验证通过

---

### Task 5: AioDockerSandboxAdapter 实现（基础设施层）

**关联 AC:** AC-5

> **职责：** 替换 mock 实现，使用 `aiodocker` 真实 Docker daemon 通信，含 5 类异常映射。

#### TDD 循环 [A]：`AioDockerSandboxAdapter` 主体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_sandbox_adapter.py`（mock aiodocker.Docker + 验证调用路径） |
| 🟢 绿 | 实现 `AioDockerSandboxAdapter` 最小代码（5 个方法 + 异常映射） |
| 🔄 重构 | 提取 `ContainerSpecBuilder`（ContainerSpec → aiodocker kwargs）+ `SeccompProfileLoader` |

- [ ] Subtask 5.1: 🔴 红 — 编写 `AioDockerSandboxAdapter` 失败测试（5 方法 + 5 异常映射）
- [ ] Subtask 5.2: 🟢 绿 — 实现 `AioDockerSandboxAdapter` 主体
- [ ] Subtask 5.3: 🔄 重构 — 提取 `ContainerSpecBuilder` + `SeccompProfileLoader`
- [ ] Subtask 5.4: 创建 `stubs/aiodocker/__init__.pyi`（PEP 561 stubs）
- [ ] Subtask 5.5: `pyproject.toml` 新增依赖 `aiodocker = "^0.21.0"`
- [ ] Subtask 5.6: `composition_root.py` 切换 `sandbox_executor` impl 至 `AioDockerSandboxAdapter`

**完成标准/Definition of Done:**

- [ ] `AioDockerSandboxAdapter` 实现完成
- [ ] TDD 循环全部通过
- [ ] 5 类异常映射验证通过
- [ ] `stubs/aiodocker/__init__.pyi` 创建
- [ ] `mypy` 通过（含 stubs）

---

### Task 6: SandboxSessionReaper 30 分钟空闲清理（应用层）

**关联 AC:** AC-6

> **职责：** 实现空闲 TTL 清理 + 启动时孤儿容器扫描。

#### TDD 循环 [A]：`SandboxSessionReaper`

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_sandbox_session_reaper.py`（mock SandboxExecutor + 验证清理逻辑） |
| 🟢 绿 | 实现 `SandboxSessionReaper.reap_idle_sessions(threshold)` 最小代码 |
| 🔄 重构 | 提取孤儿容器扫描为独立方法 `_reap_orphan_containers()` |

- [ ] Subtask 6.1: 🔴 红 — 编写 Reaper 失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现 `reap_idle_sessions` 主体
- [ ] Subtask 6.3: 🔄 重构 — 提取孤儿容器扫描
- [ ] Subtask 6.4: `composition_root.py` 注册 `sandbox_session_reaper`（SINGLETON）

**完成标准/Definition of Done:**

- [ ] `SandboxSessionReaper` 实现完成
- [ ] TDD 循环全部通过
- [ ] 30 分钟 TTL 逻辑验证通过
- [ ] 孤儿容器扫描实现完成

---

### Task 7: SandboxSecurityDecorator 应用层安全编排

**关联 AC:** AC-7

> **职责：** 装饰器模式（不破坏 4.1a 既有签名），实现超时 + 重试 + 配额 + session_id 校验。

#### TDD 循环 [A]：`SandboxSecurityDecorator`

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_sandbox_security_decorator.py`（mock SandboxExecutor + 验证 4 项防护） |
| 🟢 绿 | 实现 `SandboxSecurityDecorator` 最小代码（4 项防护） |
| 🔄 重构 | 复用 `_call_with_retry`（`retry_helpers.py`）+ 优化重试策略 |

- [ ] Subtask 7.1: 🔴 红 — 编写 `SandboxSecurityDecorator`（**包裹类**，对齐 `ToolOutputValidator` 样板 `src/application/services/tool_output_validator.py:35-44`）失败测试，验证超时 / 重试 / 配额 / session_id 校验 4 项防护
- [ ] Subtask 7.2: 🟢 绿 — 实现 `SandboxSecurityDecorator` 主体
- [ ] Subtask 7.3: 🔄 重构 — 复用 `_call_with_retry`
- [ ] Subtask 7.4: `composition_root.py` 装配装饰器（`tool_execution_engine` impl 切换）

**完成标准/Definition of Done:**

- [ ] `SandboxSecurityDecorator` 实现完成
- [ ] TDD 循环全部通过
- [ ] `ToolExecutionEngine.__init__` 既有签名**完全保持不变**（4.3 经验）
- [ ] 4 项防护全部验证通过

---

### Task 8: 集成测试（testcontainers-python 真实 Docker daemon）

**关联 AC:** AC-8

> **职责：** 7 项核心场景集成测试（启动 / 网络 / 资源 / 只读 / pids / 逃逸 / 并发）。

#### TDD 循环 [A]：集成测试套件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_docker_sandbox_integration.py`（7 项场景） |
| 🟢 绿 | 实现测试用例（testcontainers 上下文管理器 + 真实 Docker daemon） |
| 🔄 重构 | 提取 `_create_test_container()` fixture 工厂函数 |

- [ ] Subtask 8.1: 🔴 红 — 编写集成测试失败用例
- [ ] Subtask 8.2: 🟢 绿 — 实现 7 项场景测试
- [ ] Subtask 8.3: 🔄 重构 — 提取 fixture 工厂函数
- [ ] Subtask 8.4: `pyproject.toml` 新增依赖 `testcontainers = {extras = ["docker"], version = "^4.13.0"}`

**完成标准/Definition of Done:**

- [ ] 7 项场景全部实现
- [ ] 真实 Docker daemon 集成测试通过
- [ ] testcontainers 自动清理验证
- [ ] 动态 `pytest.skip()` 若 daemon 不可用
- [ ] **禁止** mock（CLAUDE.md §5）

---

### Task 9: SDD 架构约束验证测试 + 性能基准

**关联 AC:** AC-9

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）+ 性能基准。

#### 架构验证测试实现

- [ ] Subtask 9.1: 创建 `tests/unit/architecture/test_docker_sandbox.py`（**epics_v1.0.md:1204 硬要求路径，无 `_arch_` 前缀**；4 项规则：域层零依赖 + 依赖方向 + 无循环 + PortSpec 元数据）
- [ ] Subtask 9.2: 实现 `test_domain_zero_dependencies()`（验证 domain 不依赖 aiodocker）
- [ ] Subtask 9.3: 实现 `test_dependency_direction()`（验证 4 层依赖方向）
- [ ] Subtask 9.4: 实现 `test_port_spec_metadata()`（验证 3 个端口的 **10 字段**完整性，含 `module` 必填位置参数 + `compatibility` tuple + `deprecated` bool）
- [ ] Subtask 9.5: 创建 `tests/integration/test_performance_docker_sandbox.py`（启动延迟 P95 < 5s + 并发 ≥ 10 + 沙箱逃逸 0）
- [ ] Subtask 9.6: 实现循环依赖检测（**复用既有 `lint-imports`（基于 importlinter）+ `from __future__ import annotations` + AST 静态分析脚本（基于 `ast` 模块遍历 import 图）；ruff E 规则不包含循环依赖检测能力，不能仅用 `ruff --select E`**）
- [ ] Subtask 9.7: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**

- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）
- [ ] 性能基准 P95 < 5s + 并发 ≥ 10 + 沙箱逃逸 0

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-10

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_docker_sandbox.feature` 中的收尾验收场景（确保 Gherkin 7 项场景全部就绪） |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_docker_sandbox.py` 的 BDD 步骤实现（补全 Task 0 骨架） |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 10.1: 场景 1-3 验证（Happy Path + 网络隔离 + 资源限制）BDD 步骤实现
- [ ] Subtask 10.2: 场景 4-7 验证（超时 + 镜像拉取 + 并发配额 + 30 分钟清理）BDD 步骤实现
- [ ] Subtask 10.3: 运行开发结束验收测试并确认通过（7 项场景）
- [ ] Subtask 10.4: 运行 `pytest` + `ruff check` + `mypy` + `pre-commit run --all-files` 进行收尾校验
- [ ] Subtask 10.5: 更新 `sprint-status.yaml` 将 `4-4-docker-sandbox-execution` 状态从 `in-progress` 推进到 `review`

**完成标准/Definition of Done:**

- [ ] 7 项 BDD 场景全部通过
- [ ] `src` + `tests/unit` + `tests/integration` + `tests/contracts` + `tests/acceptance` 完成清单已逐项验证
- [ ] `pytest` + `ruff check` + `mypy` + `pre-commit` 全部通过
- [ ] Story 可推进至 `review` 状态

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式**: 严格六边形架构（Ports & Adapters），4 层分层 + importlinter CI 强制校验
- **设计约束**:
  - 领域层零外部依赖（含 `aiodocker` / `docker` / `testcontainers` 均禁止）
  - 端口契约通过 `PortSpec` 注册中心统一管理（`src/composition_root.py`）
  - 异常走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
  - 领域事件双通道投递（realtime + reliable），通道配置在 `config/event_channels.yaml`
  - BDD 步骤函数禁用 `@pytest.mark.asyncio`，使用 `event_loop.run_until_complete()`
  - asyncio.Lock 必须为**类变量**（CLAUDE.md §6 Gotcha）
  - 端口契约测试 11 维度（既有模式）
- **接口治理**: PortSpec **10 字段**（name / version / interface / impl / module / lifetime / owner / compatibility / tags / deprecated）
- **技术栈**: Python 3.11+ / aiodocker 0.21.0 / testcontainers-python 4.13.0 / FastAPI 0.104+ / SQLAlchemy 2.0+ / pytest 7+

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策记录 + Epic 4 Story 4.4

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **【选中】aiodocker ≥ 0.21.0（async-native）** | 原生 asyncio 集成，与项目 `asyncio_mode = "auto"` 一致；FastAPI/httpx 生态兼容；无 `subprocess` 调用绕开 Bandit B404/B603 | 第三方库无 `py.typed`（需创建 stubs） | ✅ 9/10 |
| docker-py ≥ 7.2.0（同步 SDK） | 官方维护，API 成熟 | 同步阻塞，需 `asyncio.to_thread()` 包裹 | 6/10 |
| subprocess + nsjail / firejail | 轻量，无需 Docker daemon | 进程级隔离弱于容器；Linux-only | 5/10 |
| gVisor runsc | 用户空间内核，最强隔离（V2 FR-ST-10） | 部署复杂，V2 不在范围 | 7/10（V2 评分） |
| **【选中】testcontainers-python ≥ 4.13.0（集成测试）** | 真实 daemon 验证，自包含清理，符合 CLAUDE.md §5 集成测试原则 | 需 Docker daemon（CI runner 预装） | ✅ 9/10 |
| Mock Docker SDK | 速度快 | 违反 CLAUDE.md §5 集成测试真实服务原则 | 3/10 |
| **【选中】装饰器模式（4.3 经验）** | 不破坏 `ToolExecutionEngine.__init__` 既有签名（4.1a 调用点零修改） | 增加一层调用栈（可忽略） | ✅ 9/10 |
| 修改 ToolExecutionEngine.__init__ 注入 ContainerSpec | 直接可见 | 破坏 4.1a 既有契约，违反"不修改既有实现"原则 | 4/10 |
| **【选中】SandboxSession 聚合根（含 last_activity_at + state_version 乐观锁）** | 支撑配额统计 + TTL 清理 + 乐观锁并发安全 | 字段较多（10 项） | ✅ 8/10 |
| 简化为运行时字典（不持久化） | 实现简单 | 配额统计失效 + 重启丢失会话 + 无法审计 | 5/10 |

### 项目结构说明 Project Structure

```
.
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── sandbox_session.py            # 新增（Task 2）
│   │   ├── value_objects/
│   │   │   └── container_spec.py             # 新增（Task 1）
│   │   ├── events/
│   │   │   └── sandbox_events.py             # 新增（Task 0）
│   │   ├── ports/
│   │   │   ├── sandbox_executor.py           # 既有扩展（Task 4）
│   │   │   └── sandbox_session_repository.py # 新增（Task 2）
│   │   └── exceptions/
│   │       └── sandbox_exceptions.py         # 既有扩展（Task 3，5 个新异常）
│   ├── application/
│   │   └── services/
│   │       ├── sandbox_session_reaper.py     # 新增（Task 6）
│   │       └── sandbox_security_decorator.py # 新增（Task 7）
│   ├── infrastructure/
│   │   └── external_services/
│   │       └── sandbox/
│   │           ├── aiodocker_sandbox_adapter.py          # 新增（Task 5）
│   │           ├── container_spec_builder.py             # 新增（Task 5）
│   │           ├── seccomp_profile_loader.py             # 新增（Task 5）
│   │           └── session_namespace_manager.py          # 既有（Story 4.1a）
│   └── storage/inmemory/
│       └── sandbox_session_repository.py     # 新增（Task 2）
├── stubs/
│   └── aiodocker/
│       └── __init__.pyi                      # 新增（Task 5，PEP 561）
├── deploy/
│   ├── docker/
│   │   └── seccomp/
│   │       └── sisys-hardened.json           # 新增（Task 5，seccomp profile）
│   └── postgresql/alembic/versions/
│       └── 014_sandbox_sessions.py           # 新增（Task 2）
└── tests/
    ├── contracts/
    │   ├── test_port_contract_sandbox_executor.py            # 既有扩展（Task 4）
    │   ├── test_port_contract_sandbox_session_repository.py   # 新增（Task 2）
    │   ├── test_event_contract_sandbox_events.py             # 新增（Task 0）
    │   └── test_value_object_contract_container_spec.py      # 新增（Task 1）
    ├── unit/
    │   ├── domain/
    │   │   ├── entities/test_sandbox_session.py              # 新增（Task 2）
    │   │   ├── value_objects/test_container_spec.py          # 新增（Task 1）
    │   │   └── exceptions/test_sandbox_exceptions.py         # 新增（Task 3）
    │   ├── ports/test_sandbox_executor_port.py               # 既有扩展（Task 4）
    │   ├── application/services/
    │   │   ├── test_sandbox_session_reaper.py                # 新增（Task 6）
    │   │   └── test_sandbox_security_decorator.py            # 新增（Task 7）
    │   ├── infrastructure/
    │   │   ├── storage/test_sandbox_session_repository.py    # 新增（Task 2）
    │   │   └── external_services/sandbox/
    │   │       └── test_aiodocker_sandbox_adapter.py         # 新增（Task 5）
    │   └── architecture/test_docker_sandbox.py               # 新增（Task 9，epics AC 5 硬要求无 _arch_ 前缀）
    ├── integration/
    │   ├── test_docker_sandbox_integration.py                # 新增（Task 8）
    │   └── test_performance_docker_sandbox.py                # 新增（Task 9）
    └── acceptance/
        ├── test_acceptance_docker_sandbox.feature            # 新增（Task 0 + 10）
        └── test_acceptance_docker_sandbox.py                 # 新增（Task 0 + 10）
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-2-toolchain-orchestration-dag.md](./4-2-toolchain-orchestration-dag.md)（status: review）/ Story 4-1a-strategic-tool-impl.md（status: done）

**关键学习/Key Learnings:**

- **R1 复用 `SandboxExecutor` 端口 + 既有 mock 实现**：Story 4.4 不重新定义端口，而是基于 4.1a 既有 `SandboxExecutor` Protocol 向后兼容扩展（默认参数 + 新增方法），避免破坏 `ToolExecutionEngine.__init__` 既有签名
- **R2 装饰器模式经验（4.3）**：4.3 拒绝修改 `ToolExecutionEngine.__init__`（会破坏 4.1a 向后兼容），改用纯装饰器包裹。Story 4.4 复用此模式，新增 `SandboxSecurityDecorator` 包裹 `ToolExecutionEngine`
- **R3 既有 `ContainerSecurityService` 复用**（**注**：SandboxSession 是 Story 4.4 新建，非 4.1a 既有复用，详见 AC-4）：4.1a 已定义 `ContainerSecurityService` 端口 + `IsolationVerificationResult` / `ResourceLimitsStatus` / `EscapeAttempt` / `NetworkIsolationResult` 值对象（位于 `src/domain/value_objects/container_security_result.py`），Story 4.4 复用这些值对象作为 ContainerSpecBuilder 输入
- **asyncio.Lock 类变量**：4.1a `InMemoryToolExecutionRepository._lock: asyncio.Lock = asyncio.Lock()`（**类变量**），Story 4.4 的 `InMemorySandboxSessionRepository` 严格沿用
- **Alembic migration 编号延续**：4-1a → 011、4-2 → 012、4-3 → 013，Story 4.4 → 014（每 Story +1）
- **三层 Mock/Fake/Real 策略**：单元测试 mock 端口（`AsyncMock(spec=SandboxExecutor)`），集成测试真实服务（testcontainers），验收测试真实 Docker daemon + 动态 `pytest.skip()`
- **复合索引优于单列索引**：4-3 migration 013 验证（4 个复合索引，无单列 tenant_id），Story 4.4 migration 014 沿用（4 索引含 UNIQUE container_id）
- **三层 grep 自查零输出**：4-1a / 4-2 / 4-3 均执行 `grep -rn "raise ValueError\|raise HTTPException\|class.*Exception\b" src/` 零输出，Story 4.4 沿用
- **`_call_with_retry` 抽取（4.3 经验）**：Story 4.3 将 `ToolExecutionEngine._retry_call` 抽取为 `retry_helpers.py` 共享工具，Story 4.4 的 `SandboxSecurityDecorator` 复用此工具
- **DDD Query Object 模式**：CLAUDE.md §4 端口查询参数决策规则（多字段组合 + 分页 → frozen dataclass Query VO），Story 4.4 `SandboxSessionQuery` 沿用
- **PortSpec 10 字段完整性**：name / version / interface / impl / module / lifetime / owner / compatibility / tags / deprecated（4-1a / 4-2 / 4-3 一致模式，`src/domain/ports/registry.py:27-53`）
- **契约测试 11 维度**：既有 4 个 Story 一致（name/version/lifetime/owner/tags/compatibility/deprecated + Protocol runtime_checkable + isinstance + 方法签名 + async + DI + 错误路径 + 边界条件 + resolver 行为）
- **exception_handlers HTTP 映射**：4-1a / 4-2 / 4-3 均在 `src/interfaces/api/exception_handlers.py` 注册新异常，Story 4.4 沿用

**应用到本故事/Applied to This Story:**

- [ ] `SandboxExecutor` Protocol 沿用 4.1a 既有签名，**仅通过默认参数扩展**，**不修改**既有调用点
- [ ] `SandboxSecurityDecorator` 沿用 4.3 装饰器模式，**不修改** `ToolExecutionEngine.__init__`
- [ ] `InMemorySandboxSessionRepository` 沿用 4.1a asyncio.Lock 类变量模式
- [ ] Alembic migration 014 沿用 4-3 复合索引 + UNIQUE 约束模式
- [ ] 5 个新异常走 `sandbox_exceptions.py` 扩展既有模块，不新建 `sandbox_*_exceptions.py` 文件
- [ ] 单元测试 mock `AsyncMock(spec=SandboxExecutor)`，集成测试 testcontainers，验收测试真实 daemon
- [ ] 提交前三条 grep 自查零输出
- [ ] 复用 `_call_with_retry`（`retry_helpers.py`）实现沙箱执行重试（最大 3 次指数退避）
- [ ] `SandboxSessionQuery` 沿用 CLAUDE.md §4 决策规则（frozen dataclass）
- [ ] `composition_root.py` 沿用 4 个 Story 一致的 `register_port()` 模式（lambda impl + module string + SCOPED/SINGLETON lifetime）
- [ ] 11 维度端口契约测试（既有模式）
- [ ] 在 `EXCEPTION_HTTP_MAP` 注册 5 条新异常映射

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.5 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-09-11 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（lines 1174-1213） |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` + `docs/architecture/sisys-uni-exception-design.md` |
| **PRD** | `_bmad-output/planning-artifacts/prd.md`（FR-ST-04 line 1816） |
| **OR 公理** | `_bmad-output/planning-artifacts/or.md`（三.3.[1-3] lines 230-233，三.8.[1,4] lines 252-256） |
| **前置 Story** | `_bmad-output/implementation-artifacts/stories/4-1a-strategic-tool-impl.md`（done）/ `4-2-toolchain-orchestration-dag.md`（review）/ `4-3-tool-io-schema-validation.md`（ready-for-dev） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` lines 1174-1213 提取（FR-ST-04 + 5 项 AC + BDD Given/When/Then）
- [x] 架构约束从 `architecture.md` + `CLAUDE.md` §5 + `sisys-uni-exception-design.md` 提取
- [x] 前置故事学习经验整合（4-1a / 4-2 / 4-3 一致模式）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0 + 10 个 Task，每个含完整 TDD 循环）
- [x] 项目结构对齐统一规范（六边形 4 层 + R1-R5 复用决策）
- [x] 5 个新沙箱异常 EXCEPTION_315~319 **5 项 Checklist** 完成
- [x] SandboxExecutor 端口向后兼容扩展方案明确（**不修改** 4.1a 既有签名）
- [x] 装饰器模式应用（SandboxSecurityDecorator 不修改 ToolExecutionEngine）
- [x] PEP 561 stubs/aiodocker/__init__.pyi 创建要求明确（aiodocker 无 py.typed）

### 文件清单 File List

**创建的文件/Created Files:**

- `_bmad-output/implementation-artifacts/stories/4-4-docker-sandbox-execution.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**

**领域层：**
- `src/domain/value_objects/container_spec.py` - ContainerSpec 值对象（Task 1）
- `src/domain/entities/sandbox_session.py` - SandboxSession 聚合根（Task 2）
- `src/domain/events/sandbox_events.py` - 3 个沙箱领域事件（Task 0）
- `src/domain/ports/sandbox_session_repository.py` - SandboxSessionRepositoryPort（Task 2）
- `src/domain/exceptions/sandbox_exceptions.py` - 既有模块扩展 5 个新异常（Task 3）

**应用层：**
- `src/application/services/sandbox_session_reaper.py` - 30 分钟空闲清理（Task 6）
- `src/application/services/sandbox_security_decorator.py` - 装饰器安全编排（Task 7）

**基础设施层：**
- `src/infrastructure/external_services/sandbox/aiodocker_sandbox_adapter.py` - aiodocker 真实实现（Task 5）
- `src/infrastructure/external_services/sandbox/container_spec_builder.py` - ContainerSpec → aiodocker kwargs（Task 5）
- `src/infrastructure/external_services/sandbox/seccomp_profile_loader.py` - seccomp profile 加载（Task 5）
- `src/infrastructure/storage/inmemory/sandbox_session_repository.py` - InMemory 仓储（Task 2）

**部署资源：**
- `stubs/aiodocker/__init__.pyi` - PEP 561 类型存根（Task 5）
- `deploy/docker/seccomp/sisys-hardened.json` - 强化 seccomp profile（Task 5）
- `deploy/postgresql/alembic/versions/014_sandbox_sessions.py` - sandbox_sessions 表（Task 2）

**测试文件：**
- `tests/unit/domain/value_objects/test_container_spec.py` - ContainerSpec 单元测试（Task 1）
- `tests/unit/domain/entities/test_sandbox_session.py` - SandboxSession 单元测试（Task 2）
- `tests/unit/domain/exceptions/test_sandbox_exceptions.py` - 5 个新异常单元测试（Task 3）
- `tests/unit/domain/ports/test_sandbox_executor_port.py` - 既有扩展（Task 4）
- `tests/unit/infrastructure/storage/test_sandbox_session_repository.py` - 仓储单元测试（Task 2）
- `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_sandbox_adapter.py` - 适配器单元测试（Task 5）
- `tests/unit/application/services/test_sandbox_session_reaper.py` - Reaper 单元测试（Task 6）
- `tests/unit/application/services/test_sandbox_security_decorator.py` - Decorator 单元测试（Task 7）
- `tests/unit/architecture/test_docker_sandbox.py` - 架构验证测试（Task 9，**epics AC 5 硬要求路径，无 `_arch_` 前缀**）

**契约测试：**
- `tests/contracts/test_port_contract_sandbox_executor.py` - 既有扩展 11 维度（Task 4）
- `tests/contracts/test_port_contract_sandbox_session_repository.py` - 11 维度（Task 2）
- `tests/contracts/test_event_contract_sandbox_events.py` - 事件契约（Task 0）
- `tests/contracts/test_value_object_contract_container_spec.py` - 值对象契约（Task 1）

**集成测试：**
- `tests/integration/test_docker_sandbox_integration.py` - 7 项场景集成测试（Task 8）
- `tests/integration/test_performance_docker_sandbox.py` - 性能基准（Task 9）

**验收测试：**
- `tests/acceptance/test_acceptance_docker_sandbox.feature` - Gherkin 7 项场景（Task 0 + 10）
- `tests/acceptance/test_acceptance_docker_sandbox.py` - BDD 步骤实现（Task 0 + 10）

**依赖更新：**
- `pyproject.toml` 新增 `aiodocker = "^0.21.0"`（Task 5）+ `testcontainers = {extras = ["docker"], version = "^4.13.0"}`（Task 8）

**配置更新：**
- `src/composition_root.py` 注册 3 个端口（`sandbox_executor` impl 切换 + `sandbox_session_repository` 新增 + `sandbox_session_reaper` 新增）
- `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py` 注册 3 个事件双通道
- `src/domain/exceptions/_code_ranges.py` 增加 5 行子域映射
- `src/domain/exceptions/__init__.py` 扩展 `__all__`
- `src/interfaces/api/exception_handlers.py` 增加 5 条 `EXCEPTION_HTTP_MAP`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.4 |
| **Story Key** | 4-4-docker-sandbox-execution |
| **File** | `_bmad-output/implementation-artifacts/stories/4-4-docker-sandbox-execution.md` |
| **Status** | `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略决策智能（Executive Decision Intelligence） |
| **优先级** | P0（Epic 4 战略工具箱核心安全能力） |
| **覆盖 FR** | FR-ST-04（Docker 沙箱执行，MVP P0）/ FR-ST-07（Validation Feedback 闭环前置） |
| **前置 Story** | 4-1a-strategic-tool-impl（✅ done）/ 1-7-minio-object-layer（✅ done）/ 1-18a-prefect-workflow-integration（✅ done） |
| **后续 Story** | **4-1c-skills-data-collection-integration**（**注**：原文档误标 4-1b，详见 sprint-status.yaml 修正） / 4-7-validation-feedback-loop |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0 + Task 1-10，共 11 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-10，共 10 项 AC）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 4 层 + R1-R5 复用决策 + 沙箱安全约束）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4-1a / 4-2 / 4-3 一致模式 + asyncio.Lock 类变量 + 装饰器模式 + alembic +1）
5. [ ] Sprint status synced to `ready-for-dev`（待 create-story workflow 自动更新）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| - | 无（首次创建，待审查） | - | - |

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 待 dev-story 实施后填写
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] 待 dev-story 实施后填充

#### 已修复 Patch

- [ ] 待 dev-story 实施后填充

#### 已推迟 Defer

- [ ] 待 dev-story 实施后填充

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 模板使用说明 Template Usage Guide

### 适用场景

本 Story 属于 **基础设施层 + 应用层组合**（infrastructure 替换 mock + application 安全编排），覆盖以下层类型：

| 层类型 | 覆盖率要求 | 测试重点 | 本 Story 对应 |
|--------|-----------|---------|----------------|
| **领域层 (Domain)** | ≥90% | 实体不变量 / 端口契约 / 异常体系 / 值对象 | Task 1-4 |
| **应用层 (Application)** | ≥85% | 用例编排 / 装饰器 / 重试 / TTL 清理 | Task 6-7 |
| **基础设施层 (Infrastructure)** | ≥75% | aiodocker 集成 / testcontainers / 异常映射 | Task 5 / Task 8 |

### 关键约束（CLAUDE.md §5 + §6）

1. **领域零依赖**：禁止 `aiodocker` / `docker` / `testcontainers` 进入领域层
2. **PEP 561 stubs**：`aiodocker` 无 `py.typed`，必须创建 `stubs/aiodocker/__init__.pyi`
3. **向后兼容**：不修改 4.1a `SandboxExecutor` 既有 4 方法签名
4. **装饰器模式**：不修改 4.1a `ToolExecutionEngine.__init__`
5. **asyncio.Lock 类变量**：所有 InMemory 仓储严格遵守
6. **异常 5 项 Checklist**（含 EXCEPTION_HTTP_MAP 注册）：5 个新沙箱异常 EXCEPTION_315~319
7. **三层 Mock/Fake/Real**：单元 mock / 集成 testcontainers / 验收真实 daemon
8. **三条 grep 自查**：`grep -rn "raise ValueError\|raise HTTPException\|class.*Exception\b" src/` 零输出

### 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [epics_v1.0.md](../../_bmad-output/planning-artifacts/epics_v1.0.md) | Epic 4: 战略工具箱（lines 756-784 + 1174-1213） |
| [prd.md](../../_bmad-output/planning-artifacts/prd.md) | PRD（FR-ST-04 line 1816 / FR-ST-10 line 1828） |
| [or.md](../../_bmad-output/planning-artifacts/or.md) | 系统公理（三.3.[1-3] 沙箱 / 三.8.[1,4] 网络隔离 + 纵深防御） |
| [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) | 架构设计 |
| [sisys-uni-exception-design.md](../../docs/architecture/sisys-uni-exception-design.md) | 异常设计体系 |
| [CLAUDE.md](../../CLAUDE.md) | 项目硬约束（§5 Hard Constraints + §6 Gotchas） |
| [Story 4.1a](./4-1a-strategic-tool-impl.md) | 前置 Story（SandboxExecutor 既有实现） |
| [Story 4.2](./4-2-toolchain-orchestration-dag.md) | 同 Epic 4 peer Story |
| [Story 4.3](./4-3-tool-io-schema-validation.md) | 装饰器模式经验参考 |

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-09-11
**最后更新/Last Updated:** 2026-09-11
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics_v1.0.md FR-ST-04 + 4-1a/4-2/4-3 一致模式 + R1-R5 复用决策）
