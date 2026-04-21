# SDD+TDD 融合模式实施检查清单

**版本:** 1.2.0
**日期:** 2026-04-21
**用途:** 每个 Story 开发时的检查清单
---

**Story模板:** `docs/developer/story-template.md`

## 📋 开发前检查清单（SDD 规范定义）

### 1. 规范文档准备

- [ ] **领域事件 Schema 已定义** (`src/domain/events/`)
  - [ ] 所有事件继承 `DomainEvent`
  - [ ] 使用 Pydantic V2 验证
  - [ ] 事件类型自动设置
  - [ ] Schema 版本管理

- [ ] **API 契约已定义** (`docs/api/openapi.yaml`)
  - [ ] 端点定义完整
  - [ ] 请求/响应 Schema 完整
  - [ ] 错误响应定义
  - [ ] OpenAPI 3.1 规范

- [ ] **验收标准已编写** (`tests/acceptance/*.feature`)
  - [ ] Gherkin 格式（Given-When-Then）
  - [ ] 覆盖主要用户旅程
  - [ ] 覆盖边界条件
  - [ ] 业务方可理解

- [ ] **数据模型已定义** (`src/domain/entities/`)
  - [ ] 实体类定义
  - [ ] 值对象定义
  - [ ] 领域服务接口
  - [ ] 仓储接口

### 2. TDD 测试准备

- [ ] **pytest-bdd 验收测试已编写** (`tests/acceptance/`)
  - [ ] `.feature` 文件定义场景
  - [ ] `.py` 文件实现步骤
  - [ ] 测试可运行（预期失败）

- [ ] **TDD 单元测试已编写** (`tests/unit/`)
  - [ ] 测试文件按领域组织
  - [ ] 使用 Arrange-Act-Assert 模式
  - [ ] 测试名称清晰表达意图
  - [ ] 包含正常路径和异常路径

- [ ] **红阶段验证**
  - [ ] 运行测试确认失败
  - [ ] 失败原因符合预期
  - [ ] Qwen Code Agent 已生成测试初稿

---

## 🔴🟢🔄 开发中检查清单（TDD 红 - 绿 - 重构）

### 3. 红阶段（编写失败测试）

- [ ] 测试在实现之前编写
- [ ] 测试基于验收标准
- [ ] 验证测试失败（预期行为）
- [ ] 失败信息清晰可读
- [ ] **本阶段不编写实现代码**

**红阶段完成标志：**
```bash
$ pytest tests/unit/<TARGET> -v
FAILED ... (预期行为)
```

### 4. 绿阶段（最小实现）

- [ ] 只编写让测试通过的代码
- [ ] 不追求完美，先跑通流程
- [ ] 不添加额外功能
- [ ] 可以硬编码（如果能让测试通过）
- [ ] Qwen Code Agent 辅助实现

**绿阶段完成标志：**
```bash
$ pytest tests/unit/<TARGET> -v
PASSED ... (所有测试通过)
```

### 5. 重构阶段（优化代码）

- [ ] 保持测试通过的前提下优化
- [ ] 应用设计模式
- [ ] 改进命名
- [ ] 添加类型注解
- [ ] 添加文档字符串
- [ ] 消除代码重复
- [ ] Qwen Code Agent 提供重构建议

**重构阶段完成标志：**
```bash
# 重构前测试通过
$ pytest tests/unit/<TARGET> -v
PASSED ...

# 重构（black/ruff/mypy）
$ black src/<TARGET>
$ ruff check src/<TARGET> --fix
$ mypy src/<TARGET>

# 重构后测试仍然通过
$ pytest tests/unit/<TARGET> -v
PASSED ... (必须全部通过！)
```

### 5.5 测试隔离与数据清理

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

#### 数据库测试隔离规则

- [ ] **集成测试使用 transaction rollback**，禁止手动 `delete`/`truncate`
- [ ] **Schema 初始化在 fixture 内完成**，不依赖外部迁移命令
- [ ] **每个测试创建自己的测试数据**，不依赖预置数据
- [ ] **测试数据使用唯一标识符**（如 `uuid4()`），避免 ID 冲突

#### 外部服务隔离规则

- [ ] **Redis 测试前清理或使用 fakeredis**
- [ ] **Neo4j/Qdrant 测试数据用唯一标识符隔离**
- [ ] **外部 API 调用使用 mock/stub**

#### 并行测试隔离规则（Story 20-1 实战经验）

> **核心规则：并行测试必须使用 UUID 前缀隔离资源，禁止 autouse fixture 删除全局共享资源。**

**资源隔离前缀规范：**
- [ ] **Redis keys**: `test:{uuid}:` 格式
- [ ] **RabbitMQ queues**: `test_{uuid}_queue_` 格式
- [ ] **Qdrant collections**: `test_{uuid}_` 格式
- [ ] **PostgreSQL schemas**: `test_{uuid}` 格式
- [ ] **MinIO buckets**: `test-{uuid}` 格式

**Fixture 依赖管理：**
- [ ] **清理 fixture 必须显式依赖被清理的资源 fixture**
  - ✅ 正确：`semantic_cache(redis_config, flush_redis_before_test: None)`
  - ❌ 错误：假设 autouse flush_redis_before_test 会先执行
- [ ] **每个测试清理自己的资源**，不依赖 autouse fixture 删除 "所有" test_* 资源
  - ❌ 错误：autouse cleanup 删除所有 `test_*` collection → 会误删其他测试的资源
  - ✅ 正确：每个测试在 finally 块中清理自己创建的资源

**asyncio 上下文注意事项：**
- [ ] **asyncio.Lock 必须是类变量**，不是实例变量
  - ✅ 正确：`_lock: asyncio.Lock = asyncio.Lock()`（类变量）
  - ❌ 错误：`_lock: asyncio.Lock = field(default_factory=asyncio.Lock)`（实例变量）
- [ ] **使用 `id(task)` 而非 `task.ident` 获取任务标识**
  - `task.ident` 在某些 Python 版本中不存在
- [ ] **threading.current_thread().ident 可能为 None**
  - 需显式处理：`tid if tid is not None else 0`

**pytest-asyncio auto mode 配置：**
- [ ] **删除所有 `scope=module/event_loop` fixture**
- [ ] **在 `pyproject.toml` 配置 `asyncio_mode = "auto"`**
- [ ] **异步测试使用 `@pytest.mark.asyncio` 标记**

**Real Neo4j Client 使用规范：**
- [ ] **Neo4jClientWrapper 没有 `session()` 方法**
- [ ] 必须使用 `get_async_driver().session(database=...)` 获取 session

**违反约束的后果：**
- ❌ 测试间相互影响（数据泄漏导致随机失败）
- ❌ 测试依赖执行顺序（违反 pytest 独立性原则）
- ❌ CI 环境与本地环境不一致
- ❌ 并行测试失败（共享数据竞争）
- ❌ mypy 类型错误（asyncio.Lock 实例变量、None 处理）

---

### 5.6 并行测试验证清单

> **每个 Story 必须验证并行执行（`pytest -n 4`）无冲突。**

- [ ] 运行 `pytest tests/ -n 4` 验证并行测试通过
- [ ] 连续运行 5 次验证稳定性
- [ ] 验证无资源冲突（collection/queue/key 不被误删）
- [ ] 验证 mypy 类型检查通过

---

## ✅ 开发后检查清单（SDD 规范验证）

### 6. SDD 规范验证

- [ ] **Schema 验证**
  ```bash
  $ python -c "from src.domain.events import *; print('Schema OK')"
  Schema OK
  ```

- [ ] **API 契约测试**
  ```bash
  $ schemathesis run http://localhost:8000/openapi.json --checks all
  check status_code .......................... PASSED
  check content_type ........................ PASSED
  check_response_schema ..................... PASSED
  ```

- [ ] **验收测试**
  ```bash
  $ pytest tests/acceptance/*.feature -v
  PASSED ...
  ```

- [ ] **类型检查**
  ```bash
  $ mypy src/
  Success: no issues found in source code
  ```

### 7. 覆盖率检查

- [ ] **整体覆盖率 ≥80%**
  ```bash
  $ pytest --cov=src --cov-fail-under=80
  ```

- [ ] **领域层覆盖率 ≥90%**
  ```bash
  $ pytest --cov=src/domain --cov-fail-under=90
  ```

- [ ] **应用层覆盖率 ≥85%**
  ```bash
  $ pytest --cov=src/application --cov-fail-under=85
  ```

- [ ] **基础设施层覆盖率 ≥75%**
  ```bash
  $ pytest --cov=src/infrastructure --cov-fail-under=75
  ```

### 8. 代码质量检查

- [ ] **Ruff 代码检查**
  ```bash
  $ ruff check src/ tests/
  All checks passed!
  ```

- [ ] **Ruff 格式检查**
  ```bash
  $ ruff format --check src/ tests/
  Would be formatted correctly
  ```

- [ ] **MyPy 类型检查**
  ```bash
  $ mypy src/
  Success: no issues found in source code
  ```

- [ ] **安全扫描**
  ```bash
  $ bandit -r src/
  No issues found
  ```

---

## 🚀 CI/CD 流水线检查

### 9. 代码提交前

- [ ] 所有本地测试通过
- [ ] 所有规范验证通过
- [ ] 所有质量检查通过
- [ ] 覆盖率达标
- [ ] 代码已格式化

### 10. CI/CD 流水线

- [ ] **阶段 1: 代码质量门禁**
  - [ ] Ruff 代码检查通过（严重错误=0）
  - [ ] Ruff 格式检查通过（格式错误=0）
  - [ ] MyPy 类型检查通过（错误率<5%）

- [ ] **阶段 2: 单元测试**
  - [ ] 单元测试通过
  - [ ] 整体覆盖率≥80%
  - [ ] 领域层覆盖率≥90%
  - [ ] 应用层覆盖率≥85%

- [ ] **阶段 3: 集成测试**
  - [ ] 集成测试通过
  - [ ] 外部服务 Mock 正确

- [ ] **阶段 4: 安全扫描**
  - [ ] Bandit 安全扫描通过（高危漏洞=0）
  - [ ] Safety 依赖扫描通过（高危漏洞=0）

- [ ] **阶段 5: 构建与部署**
  - [ ] Docker 镜像构建成功
  - [ ] 镜像推送到仓库
  - [ ] 部署到测试环境
  - [ ] 健康检查通过

---

## 📝 Story 完成定义（DoD）

一个 Story 被认为完成，当且仅当：

- [ ] **SDD 规范定义完成**
  - [ ] 领域事件 Schema 已定义
  - [ ] API 契约已定义
  - [ ] 验收标准已编写

- [ ] **TDD 红 - 绿 - 重构循环完成**
  - [ ] 测试在实现之前编写
  - [ ] 所有测试通过
  - [ ] 代码已重构优化

- [ ] **SDD 规范验证通过**
  - [ ] Schema 验证通过
  - [ ] API 契约测试通过
  - [ ] 验收测试通过
  - [ ] 类型检查通过

- [ ] **覆盖率达标**
  - [ ] 整体覆盖率≥80%
  - [ ] 领域层覆盖率≥90%
  - [ ] 应用层覆盖率≥85%

- [ ] **代码质量检查通过**
  - [ ] Ruff 检查通过
  - [ ] Ruff 格式检查通过
  - [ ] MyPy 类型检查通过
  - [ ] 安全扫描通过

- [ ] **CI/CD 流水线通过**
  - [ ] 所有阶段通过
  - [ ] 部署到测试环境
  - [ ] 健康检查通过

- [ ] **文档更新**
  - [ ] 代码注释完整
  - [ ] README 更新（如需要）
  - [ ] API 文档更新（如有变更）

---

## 🎯 快速参考命令

### 完整开发循环

```bash
# 1. SDD 规范定义
make sdd-define

# 2. TDD 红阶段
make tdd-red TARGET=domain/entities

# 3. TDD 绿阶段
make tdd-green TARGET=domain/entities

# 4. TDD 重构阶段
make tdd-refactor TARGET=domain/entities

# 5. SDD 规范验证
make sdd-verify

# 6. 质量门禁检查
make quality-gates
```

### 快速测试

```bash
# 运行单元测试
make tdd TARGET=domain/entities

# 运行验收测试
pytest tests/acceptance/ -v

# 运行覆盖率检查
pytest --cov=src --cov-fail-under=80
```

### 代码质量

```bash
# Ruff 检查
ruff check src/ tests/

# Ruff 格式化
ruff format src/ tests/

# MyPy 类型检查
mypy src/

# 安全扫描
bandit -r src/
```

---

## 📊 检查清单使用说明

### 日常开发流程

1. **开发前**：使用"开发前检查清单"准备规范文档
2. **开发中**：使用"开发中检查清单"执行 TDD 循环
3. **开发后**：使用"开发后检查清单"验证规范
4. **提交前**：使用"CI/CD 流水线检查"确认质量

### 团队审查

- **代码审查**：基于检查清单逐项验证
- **Story 验收**：基于"Story 完成定义"判断完成
- **Epic 回顾**：检查清单执行率作为改进指标

### 持续改进

- 每周回顾检查清单执行情况
- 根据团队反馈调整检查项
- 逐步提高质量标准（如覆盖率要求）

---

**文档结束**
