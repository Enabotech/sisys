# 项目全局指令

## 用户角色
- AI Agent 全栈设计与开发
- 主要使用开源环境，面向企业应用
- 可以使用高级工具如 Plan/Explore agent 进行复杂任务，不需要过多解释基础概念

## 核心约束

### Poetry 环境
所有命令必须使用 `poetry run` 运行，不能直接调用命令。

### 六边形架构约束
所有代码必须遵循六边形架构约束：

**领域层零依赖原则**
- 领域层（src/domain/）仅使用 Python 标准库
- 禁止导入：langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | src/domain/ | 核心业务逻辑，零外部依赖 |
| application | src/application/ | 用例编排 |
| interfaces | src/interfaces/ | 适配器 |
| infrastructure | src/infrastructure/ | 技术实现 |

**依赖方向规则**
- 领域层 → 应用/接口/基础设施层：✗ 禁止
- 应用层 → 接口层/基础设施层：✗ 禁止
- 接口层      → 应用层/领域层 ✓ 允许
- 应用层      → 领域层 ✓ 允许
- 基础设施层  → 应用层/领域层 ✓ 允许
- 领域层      → 仅标准库 ✓ 允许

### TDD 开发约束
**每个 Task 必须严格遵守 TDD 红→绿→重构循环：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 先写失败测试，测试文件先于实现存在 | `pytest` 运行失败，失败原因符合预期 |
| 🟢 绿 | 最小实现让测试通过 | `pytest` 全部通过 |
| 🔄 重构 | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest tests/` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试
- ❌ 看到组件已存在就直接写测试验证（验证式 ≠ TDD）
- ❌ 跳过红阶段
- ❌ 把"测试存在且通过"当作完成标志

**核心原则：测试先行，代码跟随** - 测试是驱动开发的，不是验证已存在代码的。

### 测试隔离约束
所有集成/验收测试必须遵循以下约束：

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| 事务隔离 | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| Schema 自创建 | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| 资源唯一性 | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| 外部服务隔离 | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| 并行隔离 | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| 语义缓存隔离 | 多测试用 unique_cache_key 生成不同 embedding | 向量相同会互相覆盖缓存 |
| 清理粒度 | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| 依赖声明 | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| asyncio 上下文 | asyncio.Lock 类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| pytest-asyncio | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| BDD async 配合 | BDD 步骤函数用 event_loop.run_until_complete() | 直接用 @pytest.mark.asyncio 会导致 context 数据丢失 |
| asyncio.run 使用 | 单进程用 asyncio.run()；pytest-xdist 并行时 BDD 步骤用 event_loop fixture | asyncio.run() 可能关闭错误循环 |
| 并发测试 | 真正并发测试在 async 函数内用 asyncio.gather() | 根据场景正确选择 |

**核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

## 评审约束
**评审前必须理解上下文，不要在不了解背景的情况下质疑。**
- 先理解组件的职责边界，再判断是否存在真正的问题
- 分清不同组件的不同职责，不要混淆
- 当用户表达不满时，如果自己的分析正确，应坚持客观判断，不为取悦而放弃正确结论
