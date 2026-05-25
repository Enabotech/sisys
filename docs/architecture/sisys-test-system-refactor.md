# SISYS 测试系统重构详细设计与执行步骤

**版本：** 1.0.0
**状态：** 待实施
**创建日期：** 2026-05-25
**关联文档：** `sisys-test-system-design.md`（架构设计目标）、`sisys-testing-framework.md`（实施方案）

---

## 目录

1. [重构概览](#1-重构概览)
2. [差距分析详情](#2-差距分析详情)
3. [详细执行步骤](#3-详细执行步骤)
4. [验证清单](#4-验证清单)
5. [文件修改清单](#5-文件修改清单)

---

## 1. 重构概览

### 1.1 与 sisys-test-system-design.md 的关系

| 文档 | 定位 | 内容 |
|------|------|------|
| `sisys-test-system-design.md` | **架构设计目标** | 设计哲学、三层配置覆盖链、分层架构、标杆对标 |
| `sisys-testing-framework.md` | **实施方案** | Phase 1-8 Checklist、具体修复代码片段 |
| 本文档 | **重构执行指南** | 差距分析、代码修改任务（checkbox）、验证步骤 |

### 1.2 重构范围与优先级矩阵

```
┌─────────────────────────────────────────────────────────────────────┐
│                        重构优先级矩阵                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  🔴 P0: 架构偏离（必须立即修复）                                      │
│  ├── #0: 配置覆盖链 5层→3层                                          │
│  ├── #1: RabbitMQ 清理 API 错误                                     │
│  ├── #2: `_get_task_id()` 多进程碰撞风险                              │
│  └── #3: MinIO 配置未同步                                            │
│                                                                     │
│  🟡 P1: 功能缺失（建议修复）                                          │
│  ├── #4: RabbitMQ mgmt_port/认证未同步                               │
│  ├── #5: Neo4j port 未同步                                           │
│  ├── #6: MinIO endpoint 端口硬编码                                   │
│  ├── #7: TestTenant 缺少 exchange_prefix                             │
│  └── #8: TenantAwareMock 重复代码行                                  │
│                                                                     │
│  🟢 P2: 增强优化（可延后）                                            │
│  ├── #9-10: conftest 分层链补全                                       │
│  ├── #11-12: pytest marker 系统清理                                   │
│  ├── #13: 分层覆盖率门禁脚本                                          │
│  └── #14: CI docker-compose.test.yml 适配                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 影响范围统计

| 影响层级 | 文件数 | 改动类型 |
|---------|--------|---------|
| TEM (environments.py) | 1 | 核心重构 + 配置补全 |
| TIL (isolation.py) | 1 | task_id 修复 + 属性补全 |
| Fixtures (fixtures.py) | 1 | RabbitMQ 清理 API 重写 |
| conftest 链 | 3 新建 | unit/acceptance/deploy conftest |
| CI workflow | 1 | compose 文件切换 |
| 新增脚本 | 1 | 分层覆盖率门禁 |

---

## 2. 差距分析详情

### 2.1 TEM (environments.py) 差距

#### 🔴 #0: 配置覆盖链架构偏离（5层 vs 3层）

**设计目标**：三层配置覆盖链
```
Layer 1（最低）: 环境检测 + 预设配置
  → resolve_env() + 选择预设 (LOCAL/CI/K8S/TEST) + SISYS_USE_TEST_PORTS 切换
Layer 2: .env 文件填充
  → 仅填充 Layer 1 输出中的空值/默认值
Layer 3（最高）: os.environ 显式设置
  → 绝对最高优先级，不可被任何机制覆盖
```

**实际实现**（environments.py 第290-337行）：五层配置覆盖链
```python
def get_test_env() -> TestEnvConfig:
    """架构（5层覆盖顺序，从低到高）：
    1. 配置差异化测试环境（CI_CONFIG/K8S_CONFIG/LOCAL_CONFIG）  ← 应合并
    2. 加载.env配置（所有环境共享基础配置）
    3. 判断测试环境（resolve_env）                              ← 应合并
    4. 差异化环境配置覆盖.env相关字段                            ← 冗余
    5. os环境变量最后覆盖（最高优先级）
    """
```

**问题根因**：
1. 步骤 1/3/4 本质上都是"确定运行环境并选择预设配置"的子步骤，不应分层
2. 存在循环依赖：先选预设(1) → 判断环境(3) → 再覆盖预设(4)
3. 代码注释与设计文档不一致，增加维护负担

**重构方向**：
- Layer 1 整合：`resolve_env()` 返回环境类型 → 直接选择对应预设 → 端口切换逻辑内嵌
- Layer 2 简化：`_apply_dotenv_if_empty()` 仅填充空值，不改变已有值
- Layer 3 保持：`_override_config_from_env()` + `_sync_config_to_environ()` 不变

---

#### 🔴 #3: MinIO 配置未同步到 os.environ

**影响**：生产代码调用 `Config.from_env()` 无法读取 MinIO 配置，可能导致连接失败。

**当前 `_sync_config_to_environ()` 缺失项**：
- MinIO endpoint（host:port）
- MinIO access_key / secret_key
- MinIO bucket

**修复位置**：`tests/environments.py` 第442-481行

---

#### 🟡 #4: RabbitMQ mgmt_port/认证未同步

**影响**：Management API 清理队列时无法认证。

**当前 `_sync_config_to_environ()` 缺失项**：
- RabbitMQ mgmt_port
- RabbitMQ username / password

---

#### 🟡 #5: Neo4j port 未同步

**当前 `_sync_config_to_environ()` 缺失项**：
- Neo4j http_port / bolt_port

---

#### 🟡 #6: MinIO endpoint 端口硬编码 9000

**问题代码**（`_override_config_from_env()` 第419-421行）：
```python
if minio_host := os.getenv("MINIO_HOST"):
    config.minio.endpoint = f"{minio_host}:9000"  # 端口硬编码！
```

**修复**：应支持 `MINIO_API_PORT` 环境变量覆盖端口。

---

### 2.2 TIL (isolation.py) 差距

#### 🔴 #2: `_get_task_id()` 使用 id(task) 存在多进程碰撞风险

**设计目标**：使用 `task.ident` + uuid fallback

**当前实现**（isolation.py 第94-111行）：
```python
def _get_task_id(cls) -> int:
    task = asyncio.current_task()
    if task is None:
        return threading.current_thread().ident or 0
    return id(task)  # ❌ 使用 id(task) 而非 task.ident
```

**问题**：
- `id(task)` 在不同 pytest-xdist worker 进程中可能返回相同值（独立地址空间）
- 设计文档明确建议：`task.ident` 为 None 时使用 `uuid.uuid4().int`

---

#### 🟡 #7: TestTenant 缺少 rabbitmq_exchange_prefix

**设计文档要求**：RabbitMQ exchange 资源也需要隔离。

**当前 TestTenant 属性缺失**：`rabbitmq_exchange_prefix`

---

#### 🟡 #8: TenantAwareMock._prefix_name() 重复代码

**问题代码**（isolation.py 第191-192行）：
```python
        return f"{self._tenant.id}_{name}"
        return f"{self._tenant.id}_{name}"  # ← 重复行！
```

---

### 2.3 Fixtures (fixtures.py) 差距

#### 🔴 #1: RabbitMQ 清理使用错误 API

**设计目标**：使用 Management HTTP API 列出并删除队列

**当前错误实现**（fixtures.py 第189-212行）：
```python
# ❌ 错误：被动声明空队列名
result = _channel.queue_declare("", passive=True)  # 返回的是单队列属性，不是列表
for q in result:  # 不会遍历所有队列
    if q.name.startswith(prefix):
        _channel.queue_delete(q.name)
```

**正确方案**（设计文档第1291-1340行）：
```python
# ✅ 使用 Management HTTP API
async with aiohttp.ClientSession(auth=auth, timeout=timeout) as session:
    async with session.get(f"{base_url}/queues") as resp:
        queues = await resp.json()  # 返回所有队列列表
        for q in queues:
            if q["name"].startswith(prefix):
                await session.delete(f"{base_url}/queues/{vhost}/{qname}")
```

---

### 2.4 pytest marker 使用现状

| Marker | 设计预期 | 实际使用 | 使用率 |
|--------|---------|---------|--------|
| `unit` | 全部 259 单元测试 | **0 次** | 0% |
| `integration` | 全部 35 集成测试 | **22 次**（仅 deploy） | 0% (integration目录) |
| `database/redis/qdrant/minio/neo4j` | 服务依赖标记 | **0 次** | 0% |
| `asyncio` | auto 模式下不需要 | **1075 次** | 冗余 |
| `slow` | 慢速测试标记 | **0 次** | 未使用 |

**问题**：marker 系统完全未生效，无法按 `-m unit` 或 `-m redis` 过滤测试。

---

### 2.5 conftest 分层链缺失

| 预期路径 | 设计要求 | 实际状态 |
|---------|---------|---------|
| `tests/conftest.py` | 根级配置 + bootstrap | ✅ 存在 |
| `tests/integration/conftest.py` | mock + real fixture | ✅ 存在 |
| `tests/contracts/conftest.py` | registry + resolver | ✅ 存在 |
| `tests/unit/conftest.py` | unit 专属 fixture + marker | ❌ 不存在 |
| `tests/acceptance/conftest.py` | acceptance 专属 fixture | ❌ 不存在 |
| `tests/deploy/conftest.py` | K8s helpers + marker | ❌ 不存在 |

---

### 2.6 分层覆盖率门禁缺失

**设计目标**：
- domain ≥ 90%
- application ≥ 85%
- overall ≥ 80%

**当前实现**：仅 CI 中 `coverage report --fail-under=80`，无按模块差异化检查。

---

## 3. 详细执行步骤

### Phase 1: 核心基础设施修复（高优先级）🔴

#### 1.0 TEM 配置覆盖链重构：5 层 → 3 层

- [ ] **1.0.1** 重构 `get_test_env()` 注释和文档字符串
  - 文件：`tests/environments.py` 第290-299行
  - 修改：将文档字符串更新为三层模型描述
  - 代码：
    ```python
    def get_test_env() -> TestEnvConfig:
        """获取测试环境配置（单例）

        三层配置覆盖链：
        Layer 1: 环境检测 + 预设配置（resolve_env → 预设选择 → 端口切换）
        Layer 2: .env 文件填充（仅填充空值）
        Layer 3: os.environ 显式设置（最高优先级）
        """
    ```

- [ ] **1.0.2** 合并 Layer 1：统一环境检测和预设选择
  - 文件：`tests/environments.py` 第309-321行
  - 修改：将 resolve_env() 和预设选择合并为单一步骤
  - 代码：
    ```python
    # Layer 1: 环境检测 + 预设配置（合并为单一步骤）
    env = resolve_env()
    if env == TestEnvironment.CI:
        config = copy.deepcopy(CI_CONFIG)
    elif env == TestEnvironment.K8S:
        config = copy.deepcopy(K8S_CONFIG)
    elif env == TestEnvironment.LOCAL:
        # 端口切换内嵌在 LOCAL 分支中
        if os.getenv("SISYS_USE_TEST_PORTS", "").lower() in ("1", "true", "yes"):
            config = copy.deepcopy(TEST_CONFIG)
        else:
            config = copy.deepcopy(LOCAL_CONFIG)
    else:
        config = copy.deepcopy(LOCAL_CONFIG)
    ```

- [ ] **1.0.3** 简化 Layer 2：确认 `_apply_dotenv_if_empty()` 仅填充空值
  - 文件：`tests/environments.py` 第327行
  - 验证：当前实现已是仅填充空值，无需修改

- [ ] **1.0.4** 保持 Layer 3：`_override_config_from_env()` 不变
  - 文件：`tests/environments.py` 第330行
  - 验证：当前实现正确，os.environ 最高优先级

- [ ] **1.0.5** 消除冗余步骤
  - 文件：`tests/environments.py`
  - 修改：删除代码注释中"步骤 3 判断测试环境"和"步骤 4 覆盖"的描述

---

#### 1.1 TEM 配置同步补全

- [ ] **1.1.1** MinIO 配置同步
  - 文件：`tests/environments.py` `_sync_config_to_environ()` 函数
  - 添加：
    ```python
    # MinIO
    os.environ.setdefault("MINIO_ENDPOINT", config.minio.endpoint)
    os.environ.setdefault("MINIO_ACCESS_KEY", config.minio.access_key)
    os.environ.setdefault("MINIO_SECRET_KEY", config.minio.secret_key)
    os.environ.setdefault("MINIO_BUCKET", config.minio.bucket)
    ```

- [ ] **1.1.2** RabbitMQ mgmt_port/认证同步
  - 文件：`tests/environments.py` `_sync_config_to_environ()` 函数
  - 添加：
    ```python
    os.environ.setdefault("RABBITMQ_MGMT_PORT", str(config.rabbitmq.mgmt_port))
    os.environ.setdefault("RABBITMQ_USERNAME", config.rabbitmq.username)
    os.environ.setdefault("RABBITMQ_PASSWORD", config.rabbitmq.password)
    ```

- [ ] **1.1.3** Neo4j port 同步
  - 文件：`tests/environments.py` `_sync_config_to_environ()` 函数
  - 添加：
    ```python
    os.environ.setdefault("NEO4J_HTTP_PORT", str(config.neo4j.http_port))
    os.environ.setdefault("NEO4J_BOLT_PORT", str(config.neo4j.bolt_port))
    ```

- [ ] **1.1.4** MinIO endpoint 端口动态解析
  - 文件：`tests/environments.py` `_override_config_from_env()` 第419-421行
  - 修改：
    ```python
    if minio_host := os.getenv("MINIO_HOST"):
        minio_port = os.getenv("MINIO_API_PORT", "9000")
        config.minio.endpoint = f"{minio_host}:{minio_port}"
    ```

- [ ] **1.1.5** RabbitMQ mgmt_port 覆盖
  - 文件：`tests/environments.py` `_override_config_from_env()` 函数
  - 添加：
    ```python
    if rmq_mgmt_port := os.getenv("RABBITMQ_MGMT_PORT"):
        config.rabbitmq.mgmt_port = int(rmq_mgmt_port)
    ```

---

#### 1.2 TIL `_get_task_id()` 修复

- [ ] **1.2.1** 修改 `_get_task_id()`：优先使用 `task.ident`
  - 文件：`tests/isolation.py` 第94-111行
  - 修改：
    ```python
    @classmethod
    def _get_task_id(cls) -> int:
        """获取当前协程/任务的唯一 ID

        pytest-xdist 多进程隔离原理：
        - 每个 worker 进程独立内存空间，天然隔离
        - task.ident 用于同一进程内的协程区分
        - 若 task.ident 为 None，使用 uuid 避免碰撞
        """
        try:
            task = asyncio.current_task()
            if task is None:
                import threading
                tid = threading.current_thread().ident
                return tid if tid is not None else uuid.uuid4().int
            # ✅ 使用 task.ident（而非 id(task)）
            if task.ident is not None:
                return task.ident
            # fallback: 使用 uuid 避免跨进程碰撞
            return uuid.uuid4().int
        except RuntimeError:
            import threading
            tid = threading.current_thread().ident
            return tid if tid is not None else uuid.uuid4().int
    ```

---

#### 1.3 Fixtures RabbitMQ 清理修复

- [ ] **1.3.1** 修改 `_cleanup_tenant_resources()` RabbitMQ 部分
  - 文件：`tests/fixtures.py` 第189-212行
  - 修改：使用 aiohttp Management HTTP API

- [ ] **1.3.2** 实现 Management API 队列列出
  - 代码：
    ```python
    import aiohttp
    import urllib.parse

    mgmt_host = env_config.rabbitmq.host
    mgmt_port = env_config.rabbitmq.mgmt_port
    base_url = f"http://{mgmt_host}:{mgmt_port}/api"

    auth = aiohttp.BasicAuth(
        env_config.rabbitmq.username or "guest",
        env_config.rabbitmq.password or "guest",
    )
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(auth=auth, timeout=timeout) as session:
        async with session.get(f"{base_url}/queues") as resp:
            if resp.status == 200:
                queues = await resp.json()
                # ... 删除匹配前缀的队列
    ```

- [ ] **1.3.3** 实现队列删除
  - 代码：
    ```python
    prefix = tenant.rabbitmq_queue_prefix
    for q in queues:
        if q.get("name", "").startswith(prefix):
            vhost = urllib.parse.quote(q.get("vhost", "/"), safe="")
            qname = urllib.parse.quote(q["name"], safe="")
            async with session.delete(f"{base_url}/queues/{vhost}/{qname}") as del_resp:
                if del_resp.status == 204:
                    logger.debug(f"Deleted queue {q['name']}")
    ```

---

#### 1.4 TIL TestTenant 增强

- [ ] **1.4.1** 添加 `rabbitmq_exchange_prefix` 属性
  - 文件：`tests/isolation.py` TestTenant 类
  - 添加：
    ```python
    @property
    def rabbitmq_exchange_prefix(self) -> str:
        """RabbitMQ exchange 前缀"""
        return f"test_{self.id}_exchange"
    ```

- [ ] **1.4.2** 删除 TenantAwareMock._prefix_name() 重复代码
  - 文件：`tests/isolation.py` 第192行
  - 操作：删除重复的 `return f"{self._tenant.id}_{name}"`

---

### Phase 2: conftest 分层链补全 🟢

#### 2.1 创建 tests/unit/conftest.py

- [ ] **2.1.1** 创建文件
  - 文件：`tests/unit/conftest.py`（新建）

- [ ] **2.1.2** 定义 pytest_collection_modifyitems hook
  - 代码：
    ```python
    def pytest_collection_modifyitems(config, items):
        """自动为 unit 目录下的测试添加 @pytest.mark.unit"""
        for item in items:
            if "tests/unit" in str(item.fspath):
                item.add_marker("unit")
    ```

- [ ] **2.1.3** 导入根 fixtures.py 中适用于 unit 的 fixture
  - 代码：
    ```python
    from tests.fixtures import (
        test_tenant,
        isolated_tenant,
        reset_test_environment,
        resolver,
    )
    ```

---

#### 2.2 创建 tests/acceptance/conftest.py

- [ ] **2.2.1** 创建文件
  - 文件：`tests/acceptance/conftest.py`（新建）

- [ ] **2.2.2** 定义 acceptance 专属 fixture
  - 代码：
    ```python
    from tests.environments import get_test_env, TestEnvConfig
    from tests.isolation import TestTenant, generate_test_tenant

    @pytest.fixture(scope="session")
    def acceptance_env_config() -> TestEnvConfig:
        return get_test_env()
    ```

- [ ] **2.2.3** 添加 @pytest.mark.acceptance 自动标记
  - 代码：
    ```python
    def pytest_collection_modifyitems(config, items):
        for item in items:
            if "tests/acceptance" in str(item.fspath):
                item.add_marker("acceptance")
    ```

---

#### 2.3 创建 tests/deploy/conftest.py

- [ ] **2.3.1** 创建文件
  - 文件：`tests/deploy/conftest.py`（新建）

- [ ] **2.3.2** 导入 config.py 和 k8s_helpers.py
  - 代码：
    ```python
    from tests.deploy.config import TestConfig
    from tests.deploy.k8s_helpers import run_kubectl, wait, temporary_resource
    ```

- [ ] **2.3.3** 添加 @pytest.mark.k8s 自动标记
  - 代码：
    ```python
    def pytest_collection_modifyitems(config, items):
        for item in items:
            if "tests/deploy" in str(item.fspath):
                item.add_marker("k8s")
    ```

---

### Phase 3: pytest marker 系统清理 🟢

#### 3.1 清理冗余 asyncio marker

- [ ] **3.1.1** 分析：哪些测试需要保留 asyncio marker
  - 说明：`asyncio_mode = "auto"` 下，`async def test_*` 自动处理，通常无需显式标记
  - 例外：BDD 步骤中使用 `event_loop.run_until_complete()` 的场景无需 asyncio marker

- [ ] **3.1.2** 执行清理：移除冗余 asyncio marker
  - 范围：acceptance（926 处）、integration（147 处）
  - 操作：批量删除 `@pytest.mark.asyncio` 装饰器

- [ ] **3.1.3** 验证：pytest collect 无警告
  - 命令：`poetry run pytest tests/ -v --collect-only`

---

#### 3.2 自动 marker 应用策略

- [ ] **3.2.1** unit 测试自动标记 @pytest.mark.unit
  - 已在 Phase 2.1 实现

- [ ] **3.2.2** integration 测试自动标记 @pytest.mark.integration
  - 修改：`tests/integration/conftest.py` 添加 pytest_collection_modifyitems

- [ ] **3.2.3** acceptance 测试自动标记 @pytest.mark.acceptance
  - 已在 Phase 2.2 实现

- [ ] **3.2.4** 按服务依赖自动标记（可选）
  - 说明：需分析测试代码中的服务依赖，添加到 conftest hook

---

### Phase 4: CI 配置修复 🟢

#### 4.1 docker-compose.test.yml 适配

- [ ] **4.1.1** 分析 CI workflow 当前 compose 文件
  - 文件：`.gitea/workflows/ci.yaml` 第325行
  - 当前：`docker compose -f ./deploy/app/docker-compose.yml up -d`

- [ ] **4.1.2** 确认 CI 是否设置 SISYS_TEST_ENV=ci
  - 文件：`.gitea/workflows/ci.yaml`
  - 搜索：`SISYS_TEST_ENV` 环境变量设置

- [ ] **4.1.3** 修改 CI 使用 docker-compose.test.yml
  - 如需要，修改第325行：
    ```yaml
    docker compose -f ./deploy/app/docker-compose.test.yml up -d
    ```

---

#### 4.2 分层覆盖率门禁脚本

- [ ] **4.2.1** 创建 scripts/check_coverage_gates.py
  - 文件：`scripts/check_coverage_gates.py`（新建）

- [ ] **4.2.2** 实现按模块检查覆盖率
  - 代码：
    ```python
    import subprocess
    import sys

    def check_coverage(path: str, threshold: int) -> bool:
        result = subprocess.run(
            ["coverage", "report", "--include", f"{path}/*", "--fail-under", str(threshold)],
            capture_output=True, text=True
        )
        return result.returncode == 0

    checks = [
        ("src/domain", 90),
        ("src/application", 85),
        ("src", 80),
    ]

    all_pass = all(check_coverage(p, t) for p, t in checks)
    sys.exit(0 if all_pass else 1)
    ```

- [ ] **4.2.3** 添加到 CI pipeline
  - 文件：`.gitea/workflows/ci.yaml`
  - 位置：coverage report 后
  - 添加：
    ```yaml
    - name: 分层覆盖率门禁检查
      run: |
        poetry run python scripts/check_coverage_gates.py
    ```

---

### Phase 5: sisys-testing-framework.md Phase 4-8 执行 🟢

#### 5.1 Phase 4 验证与优化

- [ ] **5.1.1** 本地运行验收测试套件
  - 命令：`poetry run pytest tests/acceptance -v --tb=short`

- [ ] **5.1.2** CI 运行验收测试套件
  - 操作：推送后观察 CI logs

- [ ] **5.1.3** 验证 3 个之前失败的测试通过
  - test_ac2_rabbitmq_agentdecided
  - test_ac2_rabbitmq_documentprocessed
  - test_dense_search_with_filter

- [ ] **5.1.4** 架构约束验证测试通过
  - 命令：`poetry run pytest tests/unit/architecture -v`

- [ ] **5.1.5** 检查测试运行时间，优化慢速测试
  - 命令：`poetry run pytest tests/ --durations=20`

- [ ] **5.1.6** 更新覆盖率门禁配置
  - 已在 Phase 4.2 实现

- [ ] **5.1.7** 更新 README（测试环境变量、租户隔离）
  - 文件：项目根目录 README.md

- [ ] **5.1.8** 更新 CI README
  - 文件：`.gitea/README.md`（如存在）

---

#### 5.2 Phase 5-8 重构清单

- [ ] **5.2.1** A1-A10：acceptance 测试文件重构
  - 参考：sisys-testing-framework.md 第1870-1903行

- [ ] **5.2.2** I1-I8：integration 测试文件验证
  - 参考：sisys-testing-framework.md 第1906-1924行

- [ ] **5.2.3** R1-R7：integration_real 测试文件更新
  - 参考：sisys-testing-framework.md 第1928-1951行

- [ ] **5.2.4** U1-U6：unit 测试文件验证
  - 参考：sisys-testing-framework.md 第1955-1979行

---

## 4. 验证清单

### 4.1 测试通过验证

| 验证项 | 命令 | 期望结果 |
|--------|------|---------|
| 单元测试 | `poetry run pytest tests/unit tests/contracts -v` | 全部通过 |
| 集成测试 | `poetry run pytest tests/integration -v` | 全部通过（或 skip 无服务） |
| 验收测试 | `poetry run pytest tests/acceptance -v` | 全部通过（或 skip 无服务） |
| 架构约束 | `poetry run pytest tests/unit/architecture -v` | 全部通过 |

### 4.2 覆盖率门禁验证

| 验证项 | 命令 | 期望结果 |
|--------|------|---------|
| 全局覆盖率 | `poetry run coverage report --fail-under=80` | 通过 |
| 分层门禁 | `poetry run python scripts/check_coverage_gates.py` | domain ≥90%, application ≥85% |

### 4.3 Marker 系统验证

| 验证项 | 命令 | 期望结果 |
|--------|------|---------|
| unit marker | `pytest tests/ -m unit --collect-only | wc -l` | ≈259 |
| integration marker | `pytest tests/ -m integration --collect-only | wc -l` | ≥35 |
| acceptance marker | `pytest tests/ -m acceptance --collect-only | wc -l` | ≈25 |
| asyncio 冗余清理 | `grep -r "@pytest.mark.asyncio" tests/ | wc -l` | ≈0 |

### 4.4 CI 验证

| 验证项 | 期望结果 |
|--------|---------|
| CI pipeline | 全阶段通过 |
| 覆盖率门禁 | ≥80% |
| 分层门禁 | 通过 |

---

## 5. 文件修改清单

### 5.1 修改文件

| 文件 | 修改内容 | Phase |
|------|---------|-------|
| `tests/environments.py` | 配置覆盖链重构 + MinIO/RabbitMQ/Neo4j 同步 | 1.0, 1.1 |
| `tests/isolation.py` | task_id 修复 + exchange_prefix + 删除重复 | 1.2, 1.4 |
| `tests/fixtures.py` | RabbitMQ 清理 API 重写 | 1.3 |
| `tests/integration/conftest.py` | 添加 integration marker hook | 3.2 |
| `.gitea/workflows/ci.yaml` | compose 切换 + 分层门禁 | 4.1, 4.2 |

### 5.2 新建文件

| 文件 | 内容 | Phase |
|------|------|-------|
| `tests/unit/conftest.py` | unit marker hook + fixture 导入 | 2.1 |
| `tests/acceptance/conftest.py` | acceptance marker hook + fixture | 2.2 |
| `tests/deploy/conftest.py` | k8s marker hook + helpers 导入 | 2.3 |
| `scripts/check_coverage_gates.py` | 分层覆盖率门禁脚本 | 4.2 |

### 5.3 批量清理（可选）

| 操作 | 范围 | Phase |
|------|------|-------|
| 删除冗余 asyncio marker | acceptance/*.py, integration/*.py | 3.1 |

---

**文档结束**
