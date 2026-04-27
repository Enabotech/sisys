# infrastructure 层架构对齐重构方案

**状态:** 待执行
**创建日期:** 2026-04-27
**最后更新:** 2026-04-27
**版本:** 4.0
**核心修正:** 保持 `storage/` 作为统一存储抽象层；`idempotency/` 作为幂等模块合并到 `messaging/`；`cache/` 合并到 `storage/redis/`

---

## 1. 背景与问题

### 1.1 问题

`src/infrastructure/` 目录结构与 `architecture.md` §13.4 定义的目标架构存在显著差异。

### 1.2 发现

**原架构文档 §13.4 存在设计缺陷：**

| 架构定义 | 问题 |
|---------|------|
| `persistence/storage/` | 只含 MinIO，与 `persistence/vector_store/` 等并列不合理 |
| `external_services/file_storage/` | MinIO 作为对象存储应与 Qdrant/Neo4j 同级 |

**结论：**
- 应保持 `storage/` 作为统一存储抽象层，包含所有存储后端（minio, neo4j, postgresql, qdrant, redis）
- `idempotency/` 作为幂等性模块，应合并到 `messaging/` 下
- `cache/` 中的 `redis_memory_cache.py` 应合并到 `storage/redis/`

### 1.3 影响范围

| 指标 | 数量 |
|------|------|
| 源代码文件导入 infrastructure | **66** |
| 测试文件导入 infrastructure | **151** |

---

## 2. 正确的目录映射

### 2.1 实际 `storage/` 结构（重构后）

```
storage/                              # 统一存储抽象层 ⭐
├── minio/                           # 对象存储
├── neo4j/                           # 图存储
├── postgresql/                      # 关系存储
│   └── models/                      # SQLAlchemy 模型
├── qdrant/                          # 向量存储
├── redis/                           # 缓存
│   ├── __init__.py
│   ├── cleanup.py
│   ├── key_builder.py
│   ├── public_blackboard.py
│   ├── redis_memory_cache.py       # ← 从 cache/ 移入
│   ├── semantic_cache.py
│   └── session_storage.py
├── file_memory_adapter.py           # 文件内存适配器
├── memory_index.py                  # 内存索引
├── memory_router.py                 # 内存路由
└── redis_snapshot_store.py          # Redis快照存储
```

### 2.2 需要迁移的模块

| 当前目录/文件 | 目标目录 | 原因 |
|--------------|---------|------|
| `workflow_engines/` | `workflow/` | 重命名 |
| `events/` + `message_bus/` + `adapters/` + `idempotency/` | `messaging/` | 合并为消息系统 |
| `sandbox/` | `external_services/sandbox/` | 归类到外部服务 |
| `cache/redis_memory_cache.py` | `storage/redis/` | Redis 相关缓存统一到 storage |

### 2.3 保持不变的模块

| 模块 | 原因 |
|------|------|
| `storage/` | 统一存储抽象层，符合架构原则 |
| `security/` | 安全服务 |
| `monitoring/` | 监控服务 |
| `routing/` | 路由服务 |
| `scheduler/` | 调度服务 |
| `config/` | 配置管理 |
| `audit/` | 审计服务 |
| `entities/` | 实体定义 |
| `utils/` | 工具函数 |
| `repositories/` | 仓储服务 |

---

## 3. 目标架构（修订后）

```
src/infrastructure/
├── __init__.py
│
├── storage/                              # ✅ 统一存储抽象层（不拆分）
│   ├── __init__.py
│   ├── minio/                           # 对象存储
│   ├── neo4j/                           # 图存储
│   ├── postgresql/                      # 关系存储
│   │   └── models/                      # SQLAlchemy 模型
│   ├── qdrant/                          # 向量存储
│   ├── redis/                           # 缓存
│   │   ├── __init__.py
│   │   ├── cleanup.py
│   │   ├── key_builder.py
│   │   ├── public_blackboard.py
│   │   ├── redis_memory_cache.py       # ← 从 cache/ 移入
│   │   ├── semantic_cache.py
│   │   └── session_storage.py
│   ├── file_memory_adapter.py
│   ├── memory_index.py
│   ├── memory_router.py
│   └── redis_snapshot_store.py
│
├── messaging/                             # ← 合并 events/message_bus/adapters/idempotency
│   ├── __init__.py
│   ├── event_bus.py
│   ├── rabbitmq_consumer.py
│   ├── rabbitmq_publisher.py
│   ├── redis_publisher.py
│   ├── redis_subscriber.py
│   ├── message_serializer.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── event_outbox_adapter.py
│   │   └── sqlalchemy_event_outbox_adapter.py
│   ├── outbox/
│   │   ├── __init__.py
│   │   ├── outbox_processor.py
│   │   └── dead_letter_queue.py
│   └── idempotency/                       # ← 幂等模块
│       ├── __init__.py
│       ├── checker.py
│       └── retry_policy.py
│
├── external_services/                     # ← sandbox 迁移到这里
│   ├── __init__.py
│   ├── sandbox/                           # ← sandbox/ 迁移
│   │   ├── __init__.py
│   │   ├── docker_sandbox_adapter.py
│   │   └── session_namespace_manager.py
│   ├── llm/                              # 占位
│   ├── embedding/                        # 占位
│   └── document_processing/               # 占位
│
├── workflow/                              # ← workflow_engines/ 重命名
│   └── __init__.py
│
├── security/                              # ✅ 不变
├── monitoring/                            # ✅ 不变
├── routing/                              # ✅ 不变
├── scheduler/                             # ✅ 不变
├── config/                               # ✅ 不变
├── audit/                                # ✅ 不变
├── entities/                             # ✅ 不变
├── utils/                               # ✅ 不变
└── repositories/                         # ✅ 不变
```

---

## 4. 执行步骤

### Phase 1: workflow_engines/ → workflow/（低风险）

```bash
# 1. 重命名目录
mv src/infrastructure/workflow_engines src/infrastructure/workflow

# 2. 更新导入
find src/ tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.workflow_engines\./from src.infrastructure.workflow./g' {} \;

# 3. 验证
poetry run python -c "from src.infrastructure.workflow import *"
poetry run pytest tests/ -x -q -k "workflow" 2>/dev/null || echo "No workflow tests"
```

---

### Phase 2: events/ + message_bus/ + adapters/ + idempotency/ → messaging/（中风险）

**当前结构：**
```
events/
├── __init__.py
├── async_outbox_poller.py
├── async_rabbitmq_consumer.py
├── async_rabbitmq_publisher.py
├── in_memory_bus.py
├── in_memory_store.py
├── redis_publisher.py
└── redis_subscriber.py

message_bus/
└── __init__.py  # 空

adapters/
├── __init__.py
├── event_outbox_adapter.py
└── sqlalchemy_event_outbox_adapter.py

idempotency/
├── __init__.py
├── checker.py
├── dead_letter_queue.py
└── retry_policy.py
```

**目标结构：**
```
messaging/
├── __init__.py
├── event_bus.py              # ← in_memory_bus.py
├── rabbitmq_consumer.py     # ← async_rabbitmq_consumer.py
├── rabbitmq_publisher.py     # ← async_rabbitmq_publisher.py
├── redis_publisher.py        # ← redis_publisher.py
├── redis_subscriber.py       # ← redis_subscriber.py
├── message_serializer.py     # ← in_memory_store.py
├── adapters/
│   ├── __init__.py
│   ├── event_outbox_adapter.py
│   └── sqlalchemy_event_outbox_adapter.py
├── outbox/
│   ├── __init__.py
│   ├── outbox_processor.py   # ← async_outbox_poller.py
│   └── dead_letter_queue.py  # ← idempotency/dead_letter_queue.py
└── idempotency/              # ← 幂等模块
    ├── __init__.py
    ├── checker.py            # ← idempotency/checker.py
    └── retry_policy.py       # ← idempotency/retry_policy.py
```

**执行：**
```bash
cd src/infrastructure

# 1. 创建目标目录
mkdir -p messaging/adapters messaging/outbox messaging/idempotency

# 2. 移动并重命名文件
mv events/in_memory_bus.py messaging/event_bus.py
mv events/async_rabbitmq_consumer.py messaging/rabbitmq_consumer.py
mv events/async_rabbitmq_publisher.py messaging/rabbitmq_publisher.py
mv events/redis_publisher.py messaging/redis_publisher.py
mv events/redis_subscriber.py messaging/redis_subscriber.py
mv events/in_memory_store.py messaging/message_serializer.py

# 3. 移动 adapters
mv adapters/event_outbox_adapter.py messaging/adapters/
mv adapters/sqlalchemy_event_outbox_adapter.py messaging/adapters/

# 4. 移动 outbox
mv events/async_outbox_poller.py messaging/outbox/outbox_processor.py
mv idempotency/dead_letter_queue.py messaging/outbox/

# 5. 移动 idempotency
mv idempotency/checker.py messaging/idempotency/
mv idempotency/retry_policy.py messaging/idempotency/

# 6. 删除旧目录
rmdir events message_bus adapters idempotency 2>/dev/null || true

# 7. 创建 __init__.py
touch messaging/__init__.py
touch messaging/adapters/__init__.py
touch messaging/outbox/__init__.py
touch messaging/idempotency/__init__.py

# 8. 更新导入路径
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.events\./from src.infrastructure.messaging./g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.message_bus\./from src.infrastructure.messaging./g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.adapters\./from src.infrastructure.messaging.adapters./g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.idempotency\./from src.infrastructure.messaging.idempotency./g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/src\.infrastructure\.events\.in_memory_bus/src.infrastructure.messaging.event_bus/g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/src\.infrastructure\.events\.async_rabbitmq_consumer/src.infrastructure.messaging.rabbitmq_consumer/g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/src\.infrastructure\.events\.async_rabbitmq_publisher/src.infrastructure.messaging.rabbitmq_publisher/g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/src\.infrastructure\.events\.async_outbox_poller/src.infrastructure.messaging.outbox.outbox_processor/g' {} \;

# 9. 验证
cd ../..
poetry run python -c "from src.infrastructure.messaging import *"
poetry run pytest tests/unit/infrastructure/ -x -q --tb=short -k "messaging or event" 2>/dev/null || true
```

---

### Phase 3: sandbox/ → external_services/sandbox/（低风险）

```bash
cd src/infrastructure

# 1. 创建 external_services 子目录
mkdir -p external_services/sandbox

# 2. 移动 sandbox 内容
mv sandbox/__init__.py external_services/sandbox/
mv sandbox/docker_sandbox_adapter.py external_services/sandbox/
mv sandbox/session_namespace_manager.py external_services/sandbox/
rmdir sandbox

# 3. 更新导入路径
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.sandbox\./from src.infrastructure.external_services.sandbox./g' {} \;
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/src\.infrastructure\.sandbox\./src.infrastructure.external_services.sandbox./g' {} \;

# 4. 验证
cd ../..
poetry run python -c "from src.infrastructure.external_services.sandbox import *"
```

---

### Phase 4: cache/ → storage/redis/（低风险）

```bash
cd src/infrastructure

# 1. 移动 redis_memory_cache.py 到 storage/redis/
mv cache/redis_memory_cache.py storage/redis/

# 2. 删除空的 cache 目录
rmdir cache

# 3. 更新导入路径
find ../../src/ ../../tests/ -name "*.py" -exec sed -i \
  's/from src\.infrastructure\.cache\./from src.infrastructure.storage.redis./g' {} \;

# 4. 验证
cd ../..
poetry run python -c "from src.infrastructure.storage.redis import RedisMemoryCache"
```

---

### Phase 5: 全量验证

```bash
# 1. 语法检查
poetry run python -m py_compile $(find src/infrastructure -name "*.py")

# 2. 全量导入检查
poetry run python -c "
from src.infrastructure.storage import *
from src.infrastructure.storage.redis import *
from src.infrastructure.messaging import *
from src.infrastructure.messaging.idempotency import *
from src.infrastructure.external_services import *
from src.infrastructure.external_services.sandbox import *
from src.infrastructure.workflow import *
from src.infrastructure.security import *
from src.infrastructure.monitoring import *
from src.infrastructure.routing import *
from src.infrastructure.scheduler import *
from src.infrastructure.config import *
from src.infrastructure.audit import *
from src.infrastructure.entities import *
from src.infrastructure.repositories import *
from src.infrastructure.utils import *
print('All imports successful')
"

# 3. 全量测试
poetry run pytest tests/ -x -q --tb=short

# 4. 并行测试
poetry run pytest tests/ -n 8 -q
```

---

## 5. 架构对齐验证

### 5.1 目录结构验证

```bash
find src/infrastructure/ -type d | grep -v __pycache__ | sort
```

**预期输出：**
```
src/infrastructure/
src/infrastructure/audit
src/infrastructure/compression
src/infrastructure/config
src/infrastructure/entities
src/infrastructure/external_services
src/infrastructure/external_services/sandbox
src/infrastructure/messaging
src/infrastructure/messaging/adapters
src/infrastructure/messaging/idempotency
src/infrastructure/messaging/outbox
src/infrastructure/monitoring
src/infrastructure/repositories
src/infrastructure/routing
src/infrastructure/scheduler
src/infrastructure/security
src/infrastructure/storage
src/infrastructure/storage/redis
src/infrastructure/utils
src/infrastructure/workflow
```

**注意：`cache/` 目录应该已被删除**

### 5.2 导入路径验证

```bash
# 检查是否有遗留的旧导入
grep -r "from src.infrastructure.events" src/ tests/ --include="*.py" | wc -l
grep -r "from src.infrastructure.message_bus" src/ tests/ --include="*.py" | wc -l
grep -r "from src.infrastructure.adapters" src/ tests/ --include="*.py" | wc -l
grep -r "from src.infrastructure.idempotency" src/ tests/ --include="*.py" | wc -l
grep -r "from src.infrastructure.sandbox" src/ tests/ --include="*.py" | wc -l
grep -r "from src.infrastructure.workflow_engines" src/ tests/ --include="*.py" | wc -l
grep -r "from src.infrastructure.cache" src/ tests/ --include="*.py" | wc -l

# 期望：全部为 0
```

---

## 6. 风险控制

### 6.1 每步验证清单

每个 Phase 执行后必须验证：
- [ ] `poetry run python -m py_compile` 无错误
- [ ] 相关模块导入成功
- [ ] 单元测试通过

### 6.2 回滚机制

```bash
# 每步执行前提交
git add -A
git commit -m "BEFORE: Phase X - <description>"

# 如需回滚
git reset --hard HEAD~1
```

### 6.3 常见问题

| 问题 | 解决方案 |
|------|---------|
| `ModuleNotFoundError` | 检查导入路径是否完全更新 |
| 循环导入 | 检查 `__init__.py` 是否有循环依赖 |
| 测试失败 | 检查是否遗漏了某个导入更新 |

---

## 7. 执行时间估算

| Phase | 内容 | 风险 | 预估时间 |
|-------|------|------|---------|
| Phase 1 | `workflow_engines/` → `workflow/` | 低 | 10 分钟 |
| Phase 2 | `events/` + `message_bus/` + `adapters/` + `idempotency/` → `messaging/` | 中 | 1.5 小时 |
| Phase 3 | `sandbox/` → `external_services/sandbox/` | 低 | 15 分钟 |
| Phase 4 | `cache/` → `storage/redis/` | 低 | 15 分钟 |
| Phase 5 | 全量验证 | 中 | 1 小时 |
| **总计** | | | **~3.5 小时** |

---

## 8. 预期结果

### 8.1 重构后的目录结构

```
src/infrastructure/
├── __init__.py
├── storage/                              # ✅ 统一存储抽象层（不拆分）
│   ├── __init__.py
│   ├── minio/
│   ├── neo4j/
│   ├── postgresql/
│   │   └── models/
│   ├── qdrant/
│   ├── redis/
│   │   ├── __init__.py
│   │   ├── cleanup.py
│   │   ├── key_builder.py
│   │   ├── public_blackboard.py
│   │   ├── redis_memory_cache.py    # ← 从 cache/ 移入
│   │   ├── semantic_cache.py
│   │   └── session_storage.py
│   ├── file_memory_adapter.py
│   ├── memory_index.py
│   ├── memory_router.py
│   └── redis_snapshot_store.py
│
├── messaging/                            # ← 合并完成
│   ├── __init__.py
│   ├── event_bus.py
│   ├── rabbitmq_consumer.py
│   ├── rabbitmq_publisher.py
│   ├── redis_publisher.py
│   ├── redis_subscriber.py
│   ├── message_serializer.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── event_outbox_adapter.py
│   │   └── sqlalchemy_event_outbox_adapter.py
│   ├── outbox/
│   │   ├── __init__.py
│   │   ├── outbox_processor.py
│   │   └── dead_letter_queue.py
│   └── idempotency/                     # ← 幂等模块
│       ├── __init__.py
│       ├── checker.py
│       └── retry_policy.py
│
├── external_services/                    # ← sandbox 已迁移
│   ├── __init__.py
│   ├── sandbox/
│   │   ├── __init__.py
│   │   ├── docker_sandbox_adapter.py
│   │   └── session_namespace_manager.py
│   ├── llm/                            # 占位
│   ├── embedding/                      # 占位
│   └── document_processing/             # 占位
│
├── workflow/                           # ← 重命名完成
│   └── __init__.py
│
├── security/                           # ✅ 不变
├── monitoring/                          # ✅ 不变
├── routing/                            # ✅ 不变
├── scheduler/                           # ✅ 不变
├── config/                             # ✅ 不变
├── audit/                              # ✅ 不变
├── entities/                           # ✅ 不变
├── repositories/                        # ✅ 不变
└── utils/                             # ✅ 不变
```

### 8.2 架构对齐收益

- ✅ 目录结构更清晰
- ✅ `messaging/` 合并事件总线、适配器、幂等性模块
- ✅ `external_services/` 包含外部依赖服务（sandbox, llm, embedding）
- ✅ `storage/` 保持统一存储抽象层
- ✅ `cache/` 合并到 `storage/redis/`，减少顶层目录
- ✅ 符合六边形架构分层

---

## 9. 后续工作：更新 Architecture.md

重构完成后，需要更新 `architecture.md` §13.4 以反映实际目录结构：

**关键变更：**
1. 保持 `storage/` 作为统一存储抽象层
2. 将 `persistence/` 改为 `storage/` 的别名或移除
3. 更新 `external_services/` 包含 `sandbox/`
4. 添加 `messaging/` 的完整目录结构（含 `idempotency/` 子模块）
5. 更新 `storage/redis/` 包含 `redis_memory_cache.py`

---

**执行状态:** 待执行
**版本:** 4.0
**建议:** 分模块执行，每步验证后进入下一步
