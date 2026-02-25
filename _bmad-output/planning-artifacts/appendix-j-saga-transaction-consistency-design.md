# 附录 J：Saga 事务一致性设计方案

**版本：** 1.0.0
**状态：** 已批准
**创建日期：** 2026-02-25
**评审日期：** 2026-02-25
**解决问题：** H3 - 五层存储架构的跨库事务一致性设计不足

**关联文档：**
- 架构设计文档 v6.0.0 - 第 11 章 存储架构设计
- 架构设计文档 v6.0.0 - 第 10 章 事件驱动架构设计
- 架构设计文档 v6.0.0 - 第 9 章 领域实体完整定义

---

## 文档目录

1. [跨库事务场景识别](#1-跨库事务场景识别)
2. [Saga 模式设计](#2-saga-模式设计)
3. [具体 Saga 流程设计](#3-具体-saga-流程设计)
4. [数据一致性校验机制](#4-数据一致性校验机制)
5. [异常处理与恢复](#5-异常处理与恢复)
6. [监控与审计](#6-监控与审计)
7. [Saga 配置管理](#7-saga-配置管理)
8. [验收标准](#8-验收标准)
9. [与现有架构集成](#9-与现有架构集成)

---

## 1. 跨库事务场景识别

### 1.1 五层存储架构回顾

| 层级 | 技术选型 | 存储内容 | 一致性特点 |
|------|---------|---------|-----------|
| **L1 高速缓存层** | Redis 7.0+ | 会话状态、语义缓存、公共黑板 | 最终一致性，TTL 24h-30d |
| **L2 关系存储层** | PostgreSQL 15+ | 用户/RBAC、审计元数据、业务实体 | 强一致性 (ACID) |
| **L3 向量存储层** | Qdrant 1.7+ | 嵌入向量、混合检索 payload | 最终一致性 |
| **L4 对象存储层** | MinIO WORM | 原始文档、证据包、审计归档 | 强一致性 (WORM) |
| **L5 图存储层** | Neo4j 5.x | 知识图谱、实体关系 | 强一致性 (ACID) |

### 1.2 领域实体跨层分布

| 实体 | 存储层 | 数据分布 | 一致性要求 |
|------|--------|---------|-----------|
| **Document** | L2+L3+L4 | L2: 元数据 / L3: 嵌入向量 / L4: 原始文件 | 最终一致性 |
| **Agent** | L2+L1 | L2: 持久化状态 / L1: 会话快照 | 最终一致性 |
| **Tool** | L2+L1 | L2: 工具定义 / L1: 执行缓存 | 最终一致性 |
| **StrategicPlan** | L2+L4 | L2: 规划元数据 / L4: 证据包 | 强一致性 |
| **BusinessPlan** | L2+L4 | L2: 规划元数据 / L4: 证据包 | 强一致性 |
| **Checkpoint** | L1+L4 | L1: 状态快照 / L4: 归档快照 | 强一致性 |
| **StrategicArchive** | L1-L5 | 五层全分布 | 最终一致性 |
| **RoutingDecisionLog** | L2+L4 | L2: 决策元数据 / L4: WORM 归档 | 强一致性 |
| **IsolationSwitchLog** | L2+L4 | L2: 切换元数据 / L4: WORM 归档 | 强一致性 |

### 1.3 跨库事务场景清单

| 场景编号 | 场景名称 | 涉及存储层 | 业务触发条件 | 一致性要求 |
|---------|---------|-----------|-------------|-----------|
| **S01** | 文档处理与索引 | L2 → L3 → L4 | 用户上传文档 | 最终一致性 |
| **S02** | 战略规划创建 | L2 → L4 | Agent 生成新规划 | 强一致性 |
| **S03** | Checkpoint 保存 | L1 → L4 | BLM/BEM 阶段完成 | 强一致性 |
| **S04** | 路由决策归档 | L2 → L4 | UDMR 路由完成 | 强一致性 |
| **S05** | 隔离切换审计 | L2 → L4 | EIP 隔离等级切换 | 强一致性 |
| **S06** | 知识图谱构建 | L2 → L3 → L5 | 文档解析完成 | 最终一致性 |
| **S07** | 战略档案归档 | L1 → L2 → L3 → L4 → L5 | 规划审批通过 | 最终一致性 |
| **S08** | Agent 状态持久化 | L1 → L2 | Agent 会话结束 | 最终一致性 |
| **S09** | 工具执行记录 | L1 → L2 → L4 | 工具执行完成 | 强一致性 |
| **S10** | 修正分级固化 | L2 → L4 | 修正分级判定完成 | 强一致性 |

---

## 2. Saga 模式设计

### 2.1 编排式 vs 编舞式选择

**决策矩阵：**

| 评估维度 | 编排式 (Orchestration) | 编舞式 (Choreography) | 本系统选择 |
|---------|---------------------|---------------------|-----------|
| **流程复杂度** | 适合复杂多步骤流程 | 适合简单事件驱动 | 编排式 |
| **可见性** | 集中式监控，状态清晰 | 分散式，状态追踪困难 | 编排式 |
| **耦合度** | 参与者只依赖编排器 | 参与者相互解耦 | 编舞式 |
| **单点故障** | 编排器是单点 | 无单点 | 编舞式 |
| **补偿逻辑** | 编排器集中管理 | 各参与者自行处理 | 编排式 |
| **审计追踪** | 天然支持完整审计 | 需要额外机制 | 编排式 |
| **本系统需求** | 强审计要求、复杂流程、合规内建 | - | **混合模式** |

**最终决策：混合式 Saga 模式**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        混合式 Saga 架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    Saga 编排器 (核心流程)                        │  │
│   │   - 战略规划创建 (S02)                                           │  │
│   │   - Checkpoint 保存 (S03)                                        │  │
│   │   - 路由决策归档 (S04)                                           │  │
│   │   - 隔离切换审计 (S05)                                           │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                          │ 发布领域事件                                  │
│                          ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    事件驱动参与者 (辅助流程)                      │  │
│   │   - 文档索引 (S01) ← DocumentProcessed 事件                      │  │
│   │   - 知识图谱构建 (S06) ← DocumentProcessed 事件                  │  │
│   │   - 战略档案归档 (S07) ← PlanApproved 事件                       │  │
│   │   - Agent 状态持久化 (S08) ← SessionEnded 事件                   │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**选择理由：**
1. **核心审计流程**（S02-S05, S09-S10）采用编排式，确保强一致性和完整审计追踪
2. **辅助索引流程**（S01, S06-S08）采用编舞式，降低耦合度，提高可扩展性
3. **合规要求**：SOX/ISO27001 要求关键审计日志必须强一致性，编排式更适合

### 2.2 Saga 执行器架构设计

```python
# src/infrastructure/saga/saga_orchestrator.py

from abc import ABC, abstractmethod
from typing import List, Callable, Any, Dict
from uuid import UUID
from datetime import datetime
from enum import Enum

class SagaStatus(str, Enum):
    """Saga 执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"
    HALTED = "halted"  # 人工干预暂停

class SagaStep(ABC):
    """Saga 步骤抽象基类"""

    def __init__(self, name: str, timeout: int = 300):
        self.name = name
        self.timeout = timeout  # 秒
        self.compensated = False

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> bool:
        """执行正向操作，返回是否成功"""
        pass

    @abstractmethod
    async def compensate(self, context: Dict[str, Any]) -> bool:
        """执行补偿操作，返回是否成功"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """获取步骤描述（用于审计日志）"""
        pass

class SagaContext:
    """Saga 执行上下文"""

    def __init__(self, saga_id: UUID, saga_type: str):
        self.saga_id = saga_id
        self.saga_type = saga_type
        self.status = SagaStatus.PENDING
        self.current_step = 0
        self.steps_data: Dict[str, Any] = {}
        self.errors: List[Dict] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.completed_at: datetime = None

    def set_step_data(self, step_name: str, data: Any):
        """存储步骤执行结果"""
        self.steps_data[step_name] = data

    def get_step_data(self, step_name: str) -> Any:
        """获取步骤执行结果"""
        return self.steps_data.get(step_name)

    def add_error(self, step_name: str, error: str):
        """记录错误"""
        self.errors.append({
            "step": step_name,
            "error": error,
            "timestamp": datetime.utcnow()
        })

class SagaOrchestrator:
    """Saga 编排器"""

    def __init__(
        self,
        saga_id: UUID,
        saga_type: str,
        steps: List[SagaStep],
        event_publisher: Any,
        saga_repository: Any
    ):
        self.context = SagaContext(saga_id, saga_type)
        self.steps = steps
        self.event_publisher = event_publisher
        self.saga_repository = saga_repository
        self.retry_config = {
            "max_retries": 3,
            "retry_delay": 5,  # 秒
            "exponential_backoff": True
        }

    async def execute(self) -> bool:
        """执行 Saga 流程"""
        self.context.status = SagaStatus.RUNNING
        await self._persist_status()

        try:
            for i, step in enumerate(self.steps):
                self.context.current_step = i

                # 执行步骤（带重试）
                success = await self._execute_with_retry(step)

                if not success:
                    # 执行失败，触发补偿
                    await self._compensate(i - 1)
                    self.context.status = SagaStatus.FAILED
                    await self._persist_status()
                    return False

            # 全部成功
            self.context.status = SagaStatus.COMPLETED
            self.context.completed_at = datetime.utcnow()
            await self._persist_status()
            return True

        except Exception as e:
            # 异常处理
            self.context.add_error("orchestrator", str(e))
            await self._compensate(self.context.current_step - 1)
            self.context.status = SagaStatus.FAILED
            await self._persist_status()
            raise

    async def _execute_with_retry(self, step: SagaStep) -> bool:
        """带重试的步骤执行"""
        last_error = None

        for attempt in range(self.retry_config["max_retries"]):
            try:
                # 执行步骤
                success = await step.execute(self.context.steps_data)

                if success:
                    return True

                last_error = f"Step {step.name} returned False"

            except Exception as e:
                last_error = str(e)

            # 重试延迟（指数退避）
            if attempt < self.retry_config["max_retries"] - 1:
                delay = self.retry_config["retry_delay"] * (2 ** attempt)
                await asyncio.sleep(delay)

        # 所有重试失败
        self.context.add_error(step.name, last_error)
        return False

    async def _compensate(self, from_step: int):
        """执行补偿流程（反向顺序）"""
        self.context.status = SagaStatus.COMPENSATING
        await self._persist_status()

        for i in range(from_step, -1, -1):
            step = self.steps[i]

            if not step.compensated:
                try:
                    await step.compensate(self.context.steps_data)
                    step.compensated = True
                except Exception as e:
                    # 补偿失败记录日志（需要人工干预）
                    self.context.add_error(f"compensate:{step.name}", str(e))

        self.context.status = SagaStatus.FAILED
        await self._persist_status()

    async def _persist_status(self):
        """持久化 Saga 状态"""
        self.context.updated_at = datetime.utcnow()
        await self.saga_repository.save(self.context)

        # 发布状态事件
        await self.event_publisher.publish({
            "event_type": "saga.status_changed",
            "saga_id": str(self.context.saga_id),
            "status": self.context.status.value,
            "timestamp": datetime.utcnow().isoformat()
        })
```

### 2.3 补偿事务设计原则

| 原则 | 描述 | 实现方式 |
|------|------|---------|
| **幂等性** | 补偿操作必须幂等，可安全重试 | 使用唯一事务 ID，检查补偿标记 |
| **反向顺序** | 补偿按正向操作的逆序执行 | Saga 编排器自动管理 |
| **局部失败容忍** | 单个补偿失败不阻断整体流程 | 记录失败，继续补偿其他步骤 |
| **人工干预点** | 关键补偿失败时暂停，等待人工处理 | HALTED 状态 + 告警通知 |
| **补偿超时** | 补偿操作有独立超时控制 | 默认 60 秒，可配置 |
| **补偿审计** | 所有补偿操作记录审计日志 | WORM 存储 7 年 |

**补偿操作实现示例：**

```python
# src/infrastructure/saga/steps/document_steps.py

class UploadDocumentStep(SagaStep):
    """步骤 1: 上传文档到对象存储"""

    def __init__(self, object_storage: Any):
        super().__init__("upload_document", timeout=120)
        self.object_storage = object_storage

    async def execute(self, context: Dict[str, Any]) -> bool:
        """上传文档到 MinIO"""
        file_data = context.get("file_data")
        file_id = await self.object_storage.upload(
            bucket="documents",
            data=file_data,
            metadata=context.get("metadata")
        )
        context["document_blob_ref"] = file_id
        return True

    async def compensate(self, context: Dict[str, Any]) -> bool:
        """补偿：删除已上传的文档"""
        blob_ref = context.get("document_blob_ref")
        if blob_ref:
            # 幂等删除（不存在也不报错）
            await self.object_storage.delete_safe(
                bucket="documents",
                object_id=blob_ref
            )
        return True

    def get_description(self) -> str:
        return "上传文档到对象存储 (MinIO WORM)"

class SaveMetadataStep(SagaStep):
    """步骤 2: 保存元数据到关系数据库"""

    def __init__(self, document_repository: Any):
        super().__init__("save_metadata", timeout=30)
        self.document_repository = document_repository

    async def execute(self, context: Dict[str, Any]) -> bool:
        """保存元数据到 PostgreSQL"""
        metadata = {
            "title": context.get("title"),
            "format": context.get("format"),
            "blob_ref": context.get("document_blob_ref"),
            "size": context.get("size"),
            "uploaded_by": context.get("user_id")
        }
        doc_id = await self.document_repository.create(metadata)
        context["document_id"] = doc_id
        return True

    async def compensate(self, context: Dict[str, Any]) -> bool:
        """补偿：软删除元数据记录"""
        doc_id = context.get("document_id")
        if doc_id:
            await self.document_repository.soft_delete(doc_id)
        return True

    def get_description(self) -> str:
        return "保存文档元数据到关系数据库 (PostgreSQL)"

class GenerateEmbeddingStep(SagaStep):
    """步骤 3: 生成嵌入向量并保存到向量数据库"""

    def __init__(self, embedding_service: Any, vector_store: Any):
        super().__init__("generate_embedding", timeout=180)
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def execute(self, context: Dict[str, Any]) -> bool:
        """生成嵌入向量并保存到 Qdrant"""
        # 从对象存储读取文档内容
        content = await self.embedding_service.extract_text(
            context.get("document_blob_ref")
        )

        # 生成嵌入向量
        embedding = await self.embedding_service.encode(content)

        # 保存到向量数据库
        vector_id = await self.vector_store.upsert(
            collection="documents",
            vector=embedding,
            payload={
                "document_id": context.get("document_id"),
                "content_preview": content[:500],
                "created_at": datetime.utcnow().isoformat()
            }
        )
        context["embedding_ref"] = vector_id
        return True

    async def compensate(self, context: Dict[str, Any]) -> bool:
        """补偿：删除向量数据库中的记录"""
        embedding_ref = context.get("embedding_ref")
        if embedding_ref:
            await self.vector_store.delete(
                collection="documents",
                vector_id=embedding_ref
            )
        return True

    def get_description(self) -> str:
        return "生成嵌入向量并保存到向量数据库 (Qdrant)"
```

---

## 3. 具体 Saga 流程设计

### 3.1 S01: 文档处理与索引 Saga

**场景描述：** 用户上传文档后，需要完成元数据保存、文件存储、向量索引、图谱构建

**一致性要求：** 最终一致性（允许短暂不一致，但必须最终收敛）

**Saga 类型：** 编舞式（事件驱动）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    S01: 文档处理与索引 Saga                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  用户上传                                                               │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────┐                                                   │
│  │ Step 1: 上传文件 │ ──────────────────────────────────────┐          │
│  │ (L4: MinIO)     │                                        │          │
│  └─────────────────┘                                        │          │
│     │                                                       │          │
│     ▼                                                       │          │
│  ┌─────────────────┐                                        │          │
│  │ Step 2: 保存元数据│ ───────────────────────────┐          │          │
│  │ (L2: PostgreSQL)│                             │          │          │
│  └─────────────────┘                             │          │          │
│     │                                            │          │          │
│     ▼                                            │          │          │
│  ┌─────────────────┐                             │          │          │
│  │ Step 3: 生成向量 │ ────────────────┐          │          │          │
│  │ (L3: Qdrant)    │                 │          │          │          │
│  └─────────────────┘                 │          │          │          │
│     │                                │          │          │          │
│     ▼                                │          │          │          │
│  ┌─────────────────┐                 │          │          │          │
│  │ Step 4: 抽取实体 │                 │          │          │          │
│  │ (L5: Neo4j)     │                 │          │          │          │
│  └─────────────────┘                 │          │          │          │
│     │                                │          │          │          │
│     ▼                                │          │          │          │
│  ┌─────────────────┐                 │          │          │          │
│  │ Step 5: 发布事件 │ ◄───────────────┴──────────┴──────────┴──────────┤
│  │ DocumentProcessed│    补偿触发（任意步骤失败）                        │
│  └─────────────────┘                                                   │
│                                                                         │
│  正向操作：Upload → SaveMetadata → GenerateEmbedding → ExtractEntities → PublishEvent
│  补偿操作：DeleteFile ← SoftDeleteMetadata ← DeleteEmbedding ← DeleteEntities ← (N/A)
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Saga 实现：**

```python
# src/infrastructure/saga/document_processing_saga.py

class DocumentProcessingSagaOrchestrator:
    """文档处理 Saga 编排器"""

    def __init__(self, dependencies: SagaDependencies):
        self.steps = [
            UploadDocumentStep(dependencies.object_storage),
            SaveMetadataStep(dependencies.document_repository),
            GenerateEmbeddingStep(dependencies.embedding_service, dependencies.vector_store),
            ExtractEntitiesStep(dependencies.entity_extractor, dependencies.graph_store),
            PublishEventStep(dependencies.event_publisher),
        ]
        self.orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="DOCUMENT_PROCESSING",
            steps=self.steps,
            event_publisher=dependencies.event_publisher,
            saga_repository=dependencies.saga_repository
        )

    async def process(self, document_data: DocumentUploadData) -> UUID:
        """执行文档处理 Saga"""
        # 初始化上下文
        self.orchestrator.context.steps_data.update({
            "title": document_data.title,
            "format": document_data.format,
            "file_data": document_data.file_data,
            "size": document_data.size,
            "user_id": document_data.user_id,
        })

        # 执行 Saga
        success = await self.orchestrator.execute()

        if success:
            return self.orchestrator.context.get_step_data("document_id")
        else:
            raise DocumentProcessingError(
                f"Document processing failed: {self.orchestrator.context.errors}"
            )
```

### 3.2 S02: 战略规划创建 Saga

**场景描述：** Agent 完成战略规划生成后，需要保存规划元数据并归档证据包

**一致性要求：** 强一致性（规划元数据和证据包必须同时成功或失败）

**Saga 类型：** 编排式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    S02: 战略规划创建 Saga                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Agent 完成规划生成                                                      │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────┐                                           │
│  │ Step 1: 开启数据库事务   │                                           │
│  │ (PostgreSQL Transaction)│                                           │
│  └─────────────────────────┘                                           │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────┐                                           │
│  │ Step 2: 保存规划元数据   │                                           │
│  │ (L2: PostgreSQL)       │                                           │
│  │ - strategic_plans 表   │                                           │
│  │ - plan_id (主键)       │                                           │
│  └─────────────────────────┘                                           │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────┐                                           │
│  │ Step 3: 保存检查点记录   │                                           │
│  │ (L2: PostgreSQL)       │                                           │
│  │ - checkpoints 表       │                                           │
│  │ - plan_id (外键)       │                                           │
│  └─────────────────────────┘                                           │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────┐                                           │
│  │ Step 4: 提交数据库事务   │                                           │
│  │ (PostgreSQL Commit)    │                                           │
│  └─────────────────────────┘                                           │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────┐                                           │
│  │ Step 5: 归档证据包      │                                           │
│  │ (L4: MinIO WORM)       │                                           │
│  │ - 7 年合规存储          │                                           │
│  └─────────────────────────┘                                           │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────┐                                           │
│  │ Step 6: 发布创建事件    │                                           │
│  │ PlanCreated            │                                           │
│  └─────────────────────────┘                                           │
│                                                                         │
│  正向操作：BeginTx → SavePlan → SaveCheckpoints → CommitTx → ArchiveEvidence → PublishEvent
│  补偿操作：(N/A) ← (N/A) ← (N/A) ← RollbackTx ← DeleteEvidence ← (N/A)
│                                                                         │
│  注意：Step 1-4 在单个数据库事务中，Step 5-6 为独立操作                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Saga 实现：**

```python
# src/infrastructure/saga/plan_creation_saga.py

class PlanCreationSagaOrchestrator:
    """战略规划创建 Saga 编排器"""

    def __init__(self, dependencies: SagaDependencies):
        self.steps = [
            BeginTransactionStep(dependencies.db_connection),
            SavePlanMetadataStep(dependencies.plan_repository),
            SaveCheckpointsStep(dependencies.checkpoint_repository),
            CommitTransactionStep(dependencies.db_connection),
            ArchiveEvidencePackageStep(dependencies.object_storage),
            PublishPlanCreatedEventStep(dependencies.event_publisher),
        ]
        self.orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="PLAN_CREATION",
            steps=self.steps,
            event_publisher=dependencies.event_publisher,
            saga_repository=dependencies.saga_repository
        )

    async def create_plan(self, plan_data: PlanCreationData) -> UUID:
        """执行规划创建 Saga"""
        self.orchestrator.context.steps_data.update({
            "plan_type": plan_data.plan_type,
            "blm_stage": plan_data.initial_stage,
            "creator_id": plan_data.creator_id,
            "checkpoints": plan_data.checkpoints,
            "evidence_package": plan_data.evidence_package,
        })

        success = await self.orchestrator.execute()

        if success:
            return self.orchestrator.context.get_step_data("plan_id")
        else:
            raise PlanCreationError(
                f"Plan creation failed: {self.orchestrator.context.errors}"
            )
```

### 3.3 S03: Checkpoint 保存 Saga

**场景描述：** BLM/BEM 阶段完成后，保存检查点状态快照并归档

**一致性要求：** 强一致性（支持 Time-Travel 恢复）

**Saga 类型：** 编排式

```python
# src/infrastructure/saga/checkpoint_saga.py

class CheckpointStep(SagaStep):
    """Checkpoint 保存步骤"""

    async def execute(self, context: Dict[str, Any]) -> bool:
        """保存检查点到 L1+L4"""
        # 1. 保存状态快照到 Redis (L1)
        await context["redis"].hset(
            f"checkpoint:{context['checkpoint_id']}",
            mapping={
                "state": json.dumps(context["state_snapshot"]),
                "stage": context["blm_stage"],
                "created_at": datetime.utcnow().isoformat()
            }
        )
        # TTL 30 天
        await context["redis"].expire(
            f"checkpoint:{context['checkpoint_id']}",
            30 * 24 * 3600
        )

        # 2. 归档到 MinIO WORM (L4)
        archive_data = {
            "checkpoint_id": context["checkpoint_id"],
            "plan_id": context["plan_id"],
            "stage": context["blm_stage"],
            "state_snapshot": context["state_snapshot"],
            "archived_at": datetime.utcnow().isoformat()
        }

        archive_ref = await context["object_storage"].upload(
            bucket="checkpoints",
            data=json.dumps(archive_data).encode(),
            object_lock=True,  # WORM
            retention_years=7
        )
        context["checkpoint_archive_ref"] = archive_ref

        return True

    async def compensate(self, context: Dict[str, Any]) -> bool:
        """补偿：删除 Redis 缓存，WORM 无法删除需标记作废"""
        # 删除 Redis 缓存
        await context["redis"].delete(f"checkpoint:{context['checkpoint_id']}")

        # WORM 存储无法删除，标记为作废
        if context.get("checkpoint_archive_ref"):
            await context["object_storage"].mark_invalid(
                bucket="checkpoints",
                object_id=context["checkpoint_archive_ref"],
                reason="compensated"
            )

        return True
```

### 3.4 S04: 路由决策归档 Saga

**场景描述：** UDMR 路由决策完成后，保存决策日志并归档到 WORM 存储

**一致性要求：** 强一致性（审计合规要求）

**Saga 类型：** 编排式

```python
# src/infrastructure/saga/routing_decision_saga.py

class RoutingDecisionSagaOrchestrator:
    """路由决策归档 Saga 编排器"""

    def __init__(self, dependencies: SagaDependencies):
        self.steps = [
            SaveRoutingLogStep(dependencies.routing_log_repository),
            ArchiveToWORMStep(dependencies.object_storage),
            UpdateWORMRefStep(dependencies.routing_log_repository),
            PublishRoutingEventStep(dependencies.event_publisher),
        ]
        self.orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="ROUTING_DECISION",
            steps=self.steps,
            event_publisher=dependencies.event_publisher,
            saga_repository=dependencies.saga_repository
        )

    async def archive_decision(self, decision_data: RoutingDecisionData) -> UUID:
        """执行路由决策归档 Saga"""
        self.orchestrator.context.steps_data.update({
            "task_id": decision_data.task_id,
            "l1_result": decision_data.l1_compliance_result,
            "l2_scores": decision_data.l2_model_scores,
            "l3_decision": decision_data.l3_routing_decision,
            "estimated_cost": decision_data.estimated_cost,
        })

        success = await self.orchestrator.execute()

        if success:
            return self.orchestrator.context.get_step_data("decision_id")
        else:
            raise RoutingDecisionError(
                f"Routing decision archiving failed: {self.orchestrator.context.errors}"
            )
```

### 3.5 S06: 知识图谱构建 Saga

**场景描述：** 文档解析完成后，抽取实体关系并构建知识图谱

**一致性要求：** 最终一致性（允许延迟构建）

**Saga 类型：** 编舞式（监听 DocumentProcessed 事件）

```python
# src/infrastructure/saga/knowledge_graph_saga.py

class KnowledgeGraphBuilder:
    """知识图谱构建器 - 事件驱动"""

    def __init__(
        self,
        entity_extractor: EntityExtractor,
        graph_store: GraphStore,
        event_consumer: EventConsumer
    ):
        self.entity_extractor = entity_extractor
        self.graph_store = graph_store
        self.event_consumer = event_consumer

        # 订阅 DocumentProcessed 事件
        self.event_consumer.subscribe(
            event_type="document.processed",
            handler=self._handle_document_processed
        )

    async def _handle_document_processed(self, event: DomainEvent) -> None:
        """处理文档完成事件"""
        document_id = event.payload["document_id"]

        try:
            # Step 1: 抽取实体
            entities = await self.entity_extractor.extract(document_id)

            # Step 2: 抽取关系
            relations = await self.entity_extractor.extract_relations(entities)

            # Step 3: 保存到图数据库
            await self.graph_store.upsert_entities(entities)
            await self.graph_store.upsert_relations(relations)

            # Step 4: 发布图谱构建完成事件
            await self.event_consumer.publish({
                "event_type": "knowledge_graph.built",
                "document_id": document_id,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            # 发送到死信队列
            await self.event_consumer.send_to_dlq({
                "event_type": "knowledge_graph.build_failed",
                "document_id": document_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
```

### 3.6 S07: 战略档案归档 Saga

**场景描述：** 规划审批通过后，将完整档案归档到五层存储

**一致性要求：** 最终一致性（允许延迟归档）

**Saga 类型：** 混合式（编排核心步骤 + 编舞辅助步骤）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    S07: 战略档案归档 Saga                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  规划审批通过 (PlanApproved 事件)                                        │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              编排式部分（强一致性）                               │   │
│  │                                                                  │   │
│  │  Step 1: 更新规划状态为 archived (L2: PostgreSQL)                │   │
│  │  Step 2: 归档最终证据包 (L4: MinIO WORM)                         │   │
│  │  Step 3: 保存归档元数据 (L2: PostgreSQL)                         │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼ ArchiveCompleted 事件                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              编舞式部分（最终一致性）                             │   │
│  │                                                                  │   │
│  │  Listener 1: 缓存归档状态 (L1: Redis)                            │   │
│  │  Listener 2: 归档向量索引 (L3: Qdrant)                           │   │
│  │  Listener 3: 归档图谱关系 (L5: Neo4j)                            │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 数据一致性校验机制

### 4.1 定期一致性校验设计

**校验策略：**

| 校验类型 | 频率 | 范围 | 执行时间 |
|---------|------|------|---------|
| **实时校验** | 每次 Saga 完成 | 当前 Saga 涉及的数据 | 同步执行 |
| **定时校验** | 每小时 | 最近 1 小时的数据 | 后台任务 |
| **全量校验** | 每日凌晨 2 点 | 全部数据 | 后台任务 |
| **抽样校验** | 每周 | 随机抽样 5% | 后台任务 |

**校验规则引擎：**

```python
# src/infrastructure/consistency/consistency_checker.py

from typing import List, Dict, Any
from abc import ABC, abstractmethod

class ConsistencyRule(ABC):
    """一致性校验规则抽象基类"""

    @abstractmethod
    def name(self) -> str:
        """规则名称"""
        pass

    @abstractmethod
    def description(self) -> str:
        """规则描述"""
        pass

    @abstractmethod
    async def check(self, data: Dict[str, Any]) -> ConsistencyResult:
        """执行校验"""
        pass

class DocumentConsistencyRule(ConsistencyRule):
    """文档一致性校验规则"""

    def name(self) -> str:
        return "document_consistency"

    def description(self) -> str:
        return "校验文档在 L2/L3/L4 三层存储中的一致性"

    async def check(self, data: Dict[str, Any]) -> ConsistencyResult:
        """
        校验逻辑：
        1. L2 元数据存在
        2. L3 向量存在
        3. L4 文件存在
        4. 三层引用的 ID 一致
        """
        document_id = data["document_id"]
        issues = []

        # 1. 检查 L2 元数据
        metadata = await self.document_repository.get_by_id(document_id)
        if not metadata:
            issues.append("L2 metadata missing")
        else:
            blob_ref = metadata.blob_ref
            embedding_ref = metadata.embedding_ref

            # 2. 检查 L4 文件
            file_exists = await self.object_storage.exists(
                bucket="documents",
                object_id=blob_ref
            )
            if not file_exists:
                issues.append(f"L4 file missing: {blob_ref}")

            # 3. 检查 L3 向量
            vector_exists = await self.vector_store.exists(
                collection="documents",
                vector_id=embedding_ref
            )
            if not vector_exists:
                issues.append(f"L3 vector missing: {embedding_ref}")

        return ConsistencyResult(
            rule=self.name(),
            passed=len(issues) == 0,
            issues=issues,
            checked_at=datetime.utcnow()
        )

class PlanConsistencyRule(ConsistencyRule):
    """规划一致性校验规则"""

    async def check(self, data: Dict[str, Any]) -> ConsistencyResult:
        """
        校验逻辑：
        1. L2 规划元数据存在
        2. L2 检查点记录存在
        3. L4 证据包存在
        4. 检查点数量匹配
        """
        plan_id = data["plan_id"]
        issues = []

        # 1. 检查 L2 规划元数据
        plan = await self.plan_repository.get_by_id(plan_id)
        if not plan:
            issues.append("L2 plan metadata missing")
        else:
            evidence_ref = plan.evidence_package_ref
            checkpoint_count = plan.checkpoint_count

            # 2. 检查 L4 证据包
            evidence_exists = await self.object_storage.exists(
                bucket="plans",
                object_id=evidence_ref
            )
            if not evidence_exists:
                issues.append(f"L4 evidence package missing: {evidence_ref}")

            # 3. 检查 L2 检查点记录
            checkpoints = await self.checkpoint_repository.get_by_plan_id(plan_id)
            if len(checkpoints) != checkpoint_count:
                issues.append(
                    f"Checkpoint count mismatch: "
                    f"expected {checkpoint_count}, found {len(checkpoints)}"
                )

        return ConsistencyResult(
            rule=self.name(),
            passed=len(issues) == 0,
            issues=issues,
            checked_at=datetime.utcnow()
        )

class ConsistencyCheckerService:
    """一致性校验服务"""

    def __init__(self, rules: List[ConsistencyRule]):
        self.rules = rules
        self.results_repository = ConsistencyResultsRepository()

    async def run_all_checks(self, scope: ConsistencyScope) -> ConsistencyReport:
        """执行所有校验规则"""
        results = []

        for rule in self.rules:
            # 获取待校验数据
            data_items = await self._fetch_data(scope, rule)

            for data in data_items:
                result = await rule.check(data)
                results.append(result)

        # 保存校验结果
        report = ConsistencyReport(
            scope=scope,
            results=results,
            total=len(results),
            passed=sum(1 for r in results if r.passed),
            failed=sum(1 for r in results if not r.passed),
            generated_at=datetime.utcnow()
        )

        await self.results_repository.save(report)
        return report

    async def _fetch_data(self, scope: ConsistencyScope, rule: ConsistencyRule) -> List[Dict]:
        """获取待校验数据"""
        if scope.scope_type == "recent":
            # 最近 N 小时的数据
            return await self._fetch_recent_data(scope.hours, rule)
        elif scope.scope_type == "full":
            # 全量数据
            return await self._fetch_all_data(rule)
        elif scope.scope_type == "sample":
            # 随机抽样
            return await self._fetch_sample_data(rule, sample_rate=0.05)
        else:
            return []
```

### 4.2 不一致数据修复流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    不一致数据修复流程                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │ 一致性校验发现   │                                                   │
│  │ 不一致问题      │                                                   │
│  └────────┬────────┘                                                   │
│           │                                                           │
│           ▼                                                           │
│  ┌─────────────────┐                                                   │
│  │ 问题分类        │                                                   │
│  │ - 可自动修复     │                                                   │
│  │ - 需人工干预     │                                                   │
│  └────────┬────────┘                                                   │
│           │                                                           │
│     ┌─────┴─────┐                                                     │
│     │           │                                                     │
│     ▼           ▼                                                     │
│ ┌───────┐   ┌───────────┐                                            │
│ │自动修复│   │创建工单    │                                            │
│ │流程   │   │通知人工    │                                            │
│ └───┬───┘   └─────┬─────┘                                            │
│     │             │                                                   │
│     ▼             ▼                                                   │
│ ┌───────┐   ┌───────────┐                                            │
│ │验证修复│   │人工处理    │                                            │
│ │结果   │   │工单       │                                            │
│ └───┬───┘   └─────┬─────┘                                            │
│     │             │                                                   │
│     └──────┬──────┘                                                   │
│            │                                                          │
│            ▼                                                          │
│  ┌─────────────────┐                                                   │
│  │ 记录修复日志    │                                                   │
│  │ 归档到 WORM     │                                                   │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**自动修复实现：**

```python
# src/infrastructure/consistency/auto_repair.py

class AutoRepairService:
    """自动修复服务"""

    REPAIRABLE_ISSUES = {
        "L3_vector_missing": "rebuild_vector",
        "L1_cache_missing": "refresh_cache",
        "L2_metadata_inconsistent": "sync_metadata",
    }

    async def repair(self, issue: ConsistencyIssue) -> RepairResult:
        """执行自动修复"""
        repair_strategy = self.REPAIRABLE_ISSUES.get(issue.issue_type)

        if not repair_strategy:
            return RepairResult(
                success=False,
                reason="Issue not auto-repairable",
                requires_manual_intervention=True
            )

        try:
            # 执行修复策略
            if repair_strategy == "rebuild_vector":
                return await self._rebuild_vector(issue)
            elif repair_strategy == "refresh_cache":
                return await self._refresh_cache(issue)
            elif repair_strategy == "sync_metadata":
                return await self._sync_metadata(issue)

        except Exception as e:
            return RepairResult(
                success=False,
                reason=f"Repair failed: {str(e)}",
                requires_manual_intervention=True
            )

    async def _rebuild_vector(self, issue: ConsistencyIssue) -> RepairResult:
        """重建缺失的向量"""
        document_id = issue.context["document_id"]

        # 从 L4 读取文件
        content = await self.object_storage.read(
            bucket="documents",
            object_id=issue.context["blob_ref"]
        )

        # 重新生成向量
        embedding = await self.embedding_service.encode(content)

        # 保存到 L3
        vector_id = await self.vector_store.upsert(
            collection="documents",
            vector=embedding,
            payload={"document_id": document_id}
        )

        # 更新 L2 元数据
        await self.document_repository.update_embedding_ref(
            document_id, vector_id
        )

        return RepairResult(
            success=True,
            new_vector_id=vector_id,
            repaired_at=datetime.utcnow()
        )
```

---

## 5. 异常处理与恢复

### 5.1 Saga 失败处理策略

| 失败类型 | 处理策略 | 重试次数 | 升级条件 |
|---------|---------|---------|---------|
| **临时故障** | 指数退避重试 | 3 次 | 重试全部失败 |
| **业务验证失败** | 立即终止，触发补偿 | 0 次 | N/A |
| **外部服务超时** | 重试 + 熔断 | 3 次 | 熔断器打开 |
| **数据不一致** | 记录问题，继续补偿 | 0 次 | 自动修复失败 |
| **WORM 写入失败** | 重试 + 告警 | 5 次 | 合规风险 |

### 5.2 重试机制设计

```python
# src/infrastructure/saga/retry_policy.py

import asyncio
from typing import Callable, Any
from functools import wraps

class RetryPolicy:
    """重试策略"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def retry(self, func: Callable = None):
        """重试装饰器"""
        def decorator(f: Callable):
            @wraps(f)
            async def wrapper(*args, **kwargs):
                last_error = None

                for attempt in range(self.max_retries + 1):
                    try:
                        return await f(*args, **kwargs)
                    except self.retryable_exceptions as e:
                        last_error = e

                        if attempt == self.max_retries:
                            break

                        # 计算延迟（指数退避 + 抖动）
                        delay = self._calculate_delay(attempt)
                        await asyncio.sleep(delay)

                raise SagaRetryExhaustedError(
                    f"Max retries ({self.max_retries}) exceeded",
                    last_error
                )
            return wrapper

        if func:
            return decorator(func)
        return decorator

    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # 添加 0-10% 的随机抖动
            import random
            delay = delay * (1 + random.random() * 0.1)

        return delay

# 使用示例
@RetryPolicy(
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=(TimeoutError, ConnectionError)
).retry
async def upload_to_minio(data: bytes) -> str:
    """上传到 MinIO（带重试）"""
    return await minio_client.upload(data)
```

### 5.3 死信队列处理

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    死信队列处理架构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │ Saga 执行失败    │                                                   │
│  │ 或补偿失败      │                                                   │
│  └────────┬────────┘                                                   │
│           │                                                           │
│           ▼                                                           │
│  ┌─────────────────┐                                                   │
│  │ 发送到死信队列   │                                                   │
│  │ (RabbitMQ DLQ)  │                                                   │
│  └────────┬────────┘                                                   │
│           │                                                           │
│           ▼                                                           │
│  ┌─────────────────┐                                                   │
│  │ DLQ 消费者       │                                                   │
│  │ - 分类处理      │                                                   │
│  │ - 优先级排序    │                                                   │
│  └────────┬────────┘                                                   │
│           │                                                           │
│     ┌─────┴─────┬─────────────┐                                      │
│     │           │             │                                      │
│     ▼           ▼             ▼                                      │
│ ┌───────┐   ┌───────┐   ┌───────────┐                               │
│ │可重试 │   │需人工 │   │可忽略     │                               │
│ │重新入队│   │创建工单│   │记录日志   │                               │
│ └───┬───┘   └───┬───┘   └───────────┘                               │
│     │           │                                                     │
│     └───────────┘                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**死信队列实现：**

```python
# src/infrastructure/messaging/dead_letter_queue.py

class DeadLetterQueueHandler:
    """死信队列处理器"""

    def __init__(
        self,
        rabbitmq_connection: Any,
        saga_repository: Any,
        notification_service: Any
    ):
        self.connection = rabbitmq_connection
        self.saga_repository = saga_repository
        self.notification_service = notification_service

        # DLQ 分类处理策略
        self.handlers = {
            "retryable": self._handle_retryable,
            "manual_intervention": self._handle_manual,
            "ignorable": self._handle_ignorable,
        }

    async def start_consuming(self):
        """启动 DLQ 消费者"""
        channel = await self.connection.channel()

        # 声明 DLQ
        await channel.queue_declare(
            queue_name="saga.dlq",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": "saga.dlq"
            }
        )

        # 绑定消费者
        await channel.consume(
            queue_name="saga.dlq",
            callback=self._process_dlq_message
        )

    async def _process_dlq_message(self, message: Any):
        """处理 DLQ 消息"""
        dlq_event = message.json()

        # 分类
        category = self._classify(dlq_event)

        # 分发处理
        handler = self.handlers.get(category, self._handle_manual)
        await handler(dlq_event)

    def _classify(self, dlq_event: Dict) -> str:
        """DLQ 事件分类"""
        error_type = dlq_event.get("error_type", "")
        retry_count = dlq_event.get("retry_count", 0)

        # 可重试错误（网络超时、临时故障）
        if error_type in ["timeout", "connection_error"] and retry_count < 5:
            return "retryable"

        # 需人工干预（业务验证失败、数据不一致）
        if error_type in ["validation_error", "consistency_error"]:
            return "manual_intervention"

        # 可忽略（重复事件、已过时）
        if error_type in ["duplicate", "obsolete"]:
            return "ignorable"

        # 默认需人工干预
        return "manual_intervention"

    async def _handle_retryable(self, dlq_event: Dict):
        """可重试事件处理"""
        # 延迟重新入队
        delay = min(2 ** dlq_event.get("retry_count", 0) * 60, 3600)
        await asyncio.sleep(delay)

        # 重新发布到原队列
        await self.event_publisher.publish(
            exchange=dlq_event["original_exchange"],
            routing_key=dlq_event["original_routing_key"],
            message=dlq_event["original_message"]
        )

    async def _handle_manual(self, dlq_event: Dict):
        """需人工干预事件处理"""
        # 创建工单
        ticket_id = await self._create_support_ticket(dlq_event)

        # 发送告警通知
        await self.notification_service.send_alert(
            severity="high",
            title=f"Saga DLQ Manual Intervention Required: {dlq_event['saga_type']}",
            message=f"Ticket ID: {ticket_id}\nError: {dlq_event['error']}",
            recipients=["saga-team@company.com"]
        )

        # 更新 Saga 状态为 HALTED
        await self.saga_repository.update_status(
            saga_id=dlq_event["saga_id"],
            status=SagaStatus.HALTED,
            ticket_id=ticket_id
        )

    async def _handle_ignorable(self, dlq_event: Dict):
        """可忽略事件处理"""
        # 仅记录日志
        logger.info(
            f"Ignorable DLQ event: {dlq_event['saga_id']}, "
            f"type: {dlq_event['error_type']}"
        )
```

---

## 6. 监控与审计

### 6.1 Saga 执行监控指标

| 指标名称 | 类型 | 描述 | 告警阈值 |
|---------|------|------|---------|
| `saga.execution.total` | Counter | Saga 执行总次数 | - |
| `saga.execution.success` | Counter | 成功执行次数 | - |
| `saga.execution.failed` | Counter | 失败执行次数 | 失败率>5% |
| `saga.execution.compensated` | Counter | 触发补偿次数 | 补偿率>10% |
| `saga.execution.duration_seconds` | Histogram | 执行耗时分布 | P95>60s |
| `saga.step.duration_seconds` | Histogram | 单步执行耗时 | P95>10s |
| `saga.step.failure_by_type` | Counter | 各步骤失败次数 | 单步失败>3 次/小时 |
| `saga.retry.count` | Counter | 重试次数 | 重试率>20% |
| `saga.dlq.size` | Gauge | 死信队列大小 | >100 |
| `saga.halted.count` | Gauge | 暂停 Saga 数量 | >10 |

**监控仪表板：**

```python
# src/infrastructure/monitoring/saga_metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Saga 执行指标
SAGA_EXECUTION_TOTAL = Counter(
    'saga_execution_total',
    'Total number of Saga executions',
    ['saga_type', 'status']
)

SAGA_EXECUTION_DURATION = Histogram(
    'saga_execution_duration_seconds',
    'Saga execution duration in seconds',
    ['saga_type'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

SAGA_STEP_DURATION = Histogram(
    'saga_step_duration_seconds',
    'Saga step execution duration in seconds',
    ['saga_type', 'step_name'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

SAGA_COMPENSATION_COUNT = Counter(
    'saga_compensation_total',
    'Total number of Saga compensations',
    ['saga_type', 'step_name']
)

SAGA_RETRY_COUNT = Counter(
    'saga_retry_total',
    'Total number of Saga retries',
    ['saga_type', 'step_name']
)

SAGA_DLQ_SIZE = Gauge(
    'saga_dlq_size',
    'Current size of Saga Dead Letter Queue'
)

SAGA_HALTED_COUNT = Gauge(
    'saga_halted_count',
    'Number of halted Sagas requiring manual intervention'
)

class SagaMetricsCollector:
    """Saga 指标收集器"""

    def __init__(self):
        self.metrics = {
            'execution_total': SAGA_EXECUTION_TOTAL,
            'execution_duration': SAGA_EXECUTION_DURATION,
            'step_duration': SAGA_STEP_DURATION,
            'compensation_count': SAGA_COMPENSATION_COUNT,
            'retry_count': SAGA_RETRY_COUNT,
            'dlq_size': SAGA_DLQ_SIZE,
            'halted_count': SAGA_HALTED_COUNT,
        }

    def record_execution(self, saga_type: str, status: str, duration: float):
        """记录执行指标"""
        SAGA_EXECUTION_TOTAL.labels(saga_type=saga_type, status=status).inc()
        SAGA_EXECUTION_DURATION.labels(saga_type=saga_type).observe(duration)

    def record_step(self, saga_type: str, step_name: str, duration: float):
        """记录步骤指标"""
        SAGA_STEP_DURATION.labels(saga_type=saga_type, step_name=step_name).observe(duration)

    def record_compensation(self, saga_type: str, step_name: str):
        """记录补偿指标"""
        SAGA_COMPENSATION_COUNT.labels(saga_type=saga_type, step_name=step_name).inc()

    def record_retry(self, saga_type: str, step_name: str):
        """记录重试指标"""
        SAGA_RETRY_COUNT.labels(saga_type=saga_type, step_name=step_name).inc()
```

### 6.2 审计日志设计

**审计日志 Schema：**

```python
# src/domain/models/saga_audit_log.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class AuditEventType(str, Enum):
    """审计事件类型"""
    SAGA_STARTED = "saga.started"
    SAGA_STEP_EXECUTED = "saga.step_executed"
    SAGA_STEP_FAILED = "saga.step_failed"
    SAGA_COMPENSATED = "saga.compensated"
    SAGA_COMPLETED = "saga.completed"
    SAGA_FAILED = "saga.failed"
    SAGA_HALTED = "saga.halted"
    SAGA_RESUMED = "saga.resumed"
    SAGA_RETRY = "saga.retry"
    SAGA_DLQ = "saga.dlq"

class SagaAuditLog(BaseModel):
    """Saga 审计日志"""

    log_id: UUID = Field(default_factory=uuid4)
    saga_id: UUID
    saga_type: str

    # 事件信息
    event_type: AuditEventType
    event_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # 步骤信息（如适用）
    step_name: str = None
    step_sequence: int = None

    # 执行结果
    status: str
    error_message: str = None
    error_details: Dict[str, Any] = None

    # 上下文快照
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)

    # 追踪信息
    correlation_id: str
    user_id: str = None
    agent_id: str = None

    # WORM 存储引用
    worm_storage_ref: str = None

    class Config:
        schema_extra = {
            "example": {
                "saga_id": "550e8400-e29b-41d4-a716-446655440000",
                "saga_type": "DOCUMENT_PROCESSING",
                "event_type": "saga.step_executed",
                "step_name": "save_metadata",
                "step_sequence": 2,
                "status": "success",
                "context_snapshot": {
                    "document_id": "doc_12345",
                    "blob_ref": "minio://documents/abc123"
                },
                "correlation_id": "corr_67890"
            }
        }

class SagaAuditLogger:
    """Saga 审计日志记录器"""

    def __init__(
        self,
        event_publisher: Any,
        worm_storage: Any
    ):
        self.event_publisher = event_publisher
        self.worm_storage = worm_storage

    async def log(self, audit_log: SagaAuditLog):
        """记录审计日志"""
        # 1. 发布审计事件
        await self.event_publisher.publish({
            "event_type": f"audit.{audit_log.event_type.value}",
            "saga_id": str(audit_log.saga_id),
            "timestamp": audit_log.event_timestamp.isoformat(),
            "payload": audit_log.dict()
        })

        # 2. 归档到 WORM 存储（关键事件）
        if audit_log.event_type in [
            AuditEventType.SAGA_COMPLETED,
            AuditEventType.SAGA_FAILED,
            AuditEventType.SAGA_HALTED
        ]:
            worm_ref = await self.worm_storage.upload(
                bucket="saga-audit",
                data=audit_log.json().encode(),
                object_lock=True,
                retention_years=7
            )
            audit_log.worm_storage_ref = worm_ref

            # 更新审计日志引用
            await self._update_worm_ref(audit_log.log_id, worm_ref)

    async def _update_worm_ref(self, log_id: UUID, worm_ref: str):
        """更新 WORM 引用到审计日志存储"""
        await self.audit_repository.update_worm_ref(log_id, worm_ref)
```

**审计查询 API：**

```python
# src/interfaces/api/v1/routes/saga_audit_routes.py

from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1/saga-audit", tags=["Saga Audit"])

@router.get("/logs", response_model=List[SagaAuditLog])
async def get_saga_audit_logs(
    saga_id: Optional[UUID] = Query(None, description="Saga ID 过滤"),
    saga_type: Optional[str] = Query(None, description="Saga 类型过滤"),
    event_type: Optional[AuditEventType] = Query(None, description="事件类型过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    status: Optional[str] = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    audit_service: SagaAuditService = Depends()
):
    """查询 Saga 审计日志"""
    logs = await audit_service.query_logs(
        saga_id=saga_id,
        saga_type=saga_type,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        status=status,
        page=page,
        per_page=per_page
    )
    return logs

@router.get("/logs/{log_id}", response_model=SagaAuditLog)
async def get_saga_audit_log(
    log_id: UUID,
    audit_service: SagaAuditService = Depends()
):
    """获取单个审计日志详情"""
    log = await audit_service.get_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return log

@router.get("/logs/{log_id}/worm")
async def download_worm_audit_log(
    log_id: UUID,
    audit_service: SagaAuditService = Depends()
):
    """下载 WORM 归档的审计日志（需要审计权限）"""
    log = await audit_service.get_log_by_id(log_id)
    if not log or not log.worm_storage_ref:
        raise HTTPException(status_code=404, detail="WORM archive not found")

    # 权限检查
    await audit_service.verify_worm_access_permission(log_id)

    # 从 WORM 存储下载
    worm_data = await audit_service.download_from_worm(log.worm_storage_ref)
    return Response(
        content=worm_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=audit_log_{log_id}.json",
            "X-WORM-Verified": "true",
            "X-Retention-Years": "7"
        }
    )
```

---

## 7. Saga 配置管理

### 7.1 Saga 配置表结构

```sql
-- Saga 类型配置表
CREATE TABLE saga_type_config (
    saga_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    consistency_requirement VARCHAR(20) NOT NULL, -- 'strong' or 'eventual'
    saga_pattern VARCHAR(20) NOT NULL,            -- 'orchestration' or 'choreography'
    max_retries INT NOT NULL DEFAULT 3,
    retry_delay_seconds INT NOT NULL DEFAULT 5,
    step_timeout_seconds INT NOT NULL DEFAULT 300,
    compensation_timeout_seconds INT NOT NULL DEFAULT 60,
    dlq_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    audit_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Saga 步骤配置表
CREATE TABLE saga_step_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saga_type VARCHAR(100) NOT NULL REFERENCES saga_type_config(saga_type),
    step_name VARCHAR(100) NOT NULL,
    step_sequence INT NOT NULL,
    handler_class VARCHAR(255) NOT NULL,
    timeout_seconds INT NOT NULL DEFAULT 300,
    retry_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    compensation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(saga_type, step_sequence),
    UNIQUE(saga_type, step_name)
);

-- Saga 执行历史表
CREATE TABLE saga_execution_history (
    saga_id UUID PRIMARY KEY,
    saga_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    total_steps INT NOT NULL,
    completed_steps INT NOT NULL DEFAULT 0,
    failed_step_name VARCHAR(100),
    error_message TEXT,
    compensation_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    retry_count INT NOT NULL DEFAULT 0,
    correlation_id VARCHAR(100),
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_saga_execution_history_type ON saga_execution_history(saga_type);
CREATE INDEX idx_saga_execution_history_status ON saga_execution_history(status);
CREATE INDEX idx_saga_execution_history_started ON saga_execution_history(started_at);
```

### 7.2 默认 Saga 配置

```python
# src/infrastructure/saga/default_config.py

DEFAULT_SAGA_CONFIGS = {
    "DOCUMENT_PROCESSING": {
        "description": "文档处理与索引 Saga",
        "consistency_requirement": "eventual",
        "saga_pattern": "choreography",
        "max_retries": 3,
        "steps": [
            {"name": "upload_document", "sequence": 1, "timeout": 120},
            {"name": "save_metadata", "sequence": 2, "timeout": 30},
            {"name": "generate_embedding", "sequence": 3, "timeout": 180},
            {"name": "extract_entities", "sequence": 4, "timeout": 180},
            {"name": "publish_event", "sequence": 5, "timeout": 10},
        ]
    },
    "PLAN_CREATION": {
        "description": "战略规划创建 Saga",
        "consistency_requirement": "strong",
        "saga_pattern": "orchestration",
        "max_retries": 3,
        "steps": [
            {"name": "begin_transaction", "sequence": 1, "timeout": 10},
            {"name": "save_plan_metadata", "sequence": 2, "timeout": 30},
            {"name": "save_checkpoints", "sequence": 3, "timeout": 30},
            {"name": "commit_transaction", "sequence": 4, "timeout": 10},
            {"name": "archive_evidence", "sequence": 5, "timeout": 60},
            {"name": "publish_event", "sequence": 6, "timeout": 10},
        ]
    },
    "CHECKPOINT_SAVE": {
        "description": "Checkpoint 保存 Saga",
        "consistency_requirement": "strong",
        "saga_pattern": "orchestration",
        "max_retries": 3,
        "steps": [
            {"name": "save_to_redis", "sequence": 1, "timeout": 10},
            {"name": "archive_to_worm", "sequence": 2, "timeout": 60},
            {"name": "publish_event", "sequence": 3, "timeout": 10},
        ]
    },
    "ROUTING_DECISION": {
        "description": "路由决策归档 Saga",
        "consistency_requirement": "strong",
        "saga_pattern": "orchestration",
        "max_retries": 5,  # 合规要求高可靠性
        "steps": [
            {"name": "save_routing_log", "sequence": 1, "timeout": 30},
            {"name": "archive_to_worm", "sequence": 2, "timeout": 60},
            {"name": "update_worm_ref", "sequence": 3, "timeout": 30},
            {"name": "publish_event", "sequence": 4, "timeout": 10},
        ]
    },
    "KNOWLEDGE_GRAPH_BUILD": {
        "description": "知识图谱构建 Saga",
        "consistency_requirement": "eventual",
        "saga_pattern": "choreography",
        "max_retries": 3,
        "steps": [
            {"name": "extract_entities", "sequence": 1, "timeout": 180},
            {"name": "extract_relations", "sequence": 2, "timeout": 180},
            {"name": "upsert_to_graph", "sequence": 3, "timeout": 60},
            {"name": "publish_event", "sequence": 4, "timeout": 10},
        ]
    },
}
```

---

## 8. 验收标准

| 验收项 | 验收标准 | 验证方式 |
|--------|---------|---------|
| **Saga 执行成功率** | ≥99% | 监控指标统计 |
| **补偿成功率** | ≥95% | 补偿日志统计 |
| **数据一致性** | 最终一致性收敛时间<5 分钟 | 一致性校验报告 |
| **审计完整性** | 100% Saga 执行可追溯 | 审计日志抽样 |
| **WORM 合规性** | 7 年 retention 不可篡改 | WORM 存储验证 |
| **死信处理 SLA** | DLQ 消息 24 小时内处理 | 工单系统统计 |
| **监控覆盖率** | 所有 Saga 指标可观测 | Prometheus/Grafana 仪表板 |

---

## 9. 与现有架构集成

### 9.1 依赖注入配置

```python
# src/infrastructure/saga/saga_module.py

class SagaModule:
    """Saga 模块配置"""

    @staticmethod
    def register_dependencies(container: Container):
        """注册 Saga 相关依赖"""

        # 仓储
        container.register(
            SagaRepository,
            use_class=PostgreSQLSagaRepository
        )

        # 事件发布
        container.register(
            SagaEventPublisher,
            use_class=RabbitMQSagaEventPublisher
        )

        # 审计日志
        container.register(
            SagaAuditLogger,
            use_class=WORMSagaAuditLogger
        )

        # 一致性校验
        container.register(
            ConsistencyCheckerService,
            use_factory=ConsistencyCheckerFactory
        )

        # 自动修复
        container.register(
            AutoRepairService,
            use_class=DefaultAutoRepairService
        )

        # Saga 编排器工厂
        container.register(
            SagaOrchestratorFactory,
            use_factory=SagaOrchestratorFactory
        )

        # 具体 Saga 编排器
        container.register(
            DocumentProcessingSagaOrchestrator,
            use_factory=DocumentProcessingSagaFactory
        )
        container.register(
            PlanCreationSagaOrchestrator,
            use_factory=PlanCreationSagaFactory
        )
        # ... 其他 Saga
```

### 9.2 与事件驱动架构集成

```python
# src/infrastructure/messaging/saga_event_handlers.py

class SagaEventHandler:
    """Saga 事件处理器"""

    def __init__(
        self,
        saga_factory: SagaOrchestratorFactory,
        event_consumer: EventConsumer
    ):
        self.saga_factory = saga_factory
        self.event_consumer = event_consumer

        # 订阅触发 Saga 的事件
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """设置事件订阅"""
        # 文档上传完成 → 触发文档处理 Saga
        self.event_consumer.subscribe(
            event_type="document.uploaded",
            handler=self._handle_document_uploaded
        )

        # 规划生成完成 → 触发规划创建 Saga
        self.event_consumer.subscribe(
            event_type="plan.generated",
            handler=self._handle_plan_generated
        )

        # 规划审批通过 → 触发战略档案归档 Saga
        self.event_consumer.subscribe(
            event_type="plan.approved",
            handler=self._handle_plan_approved
        )

    async def _handle_document_uploaded(self, event: DomainEvent):
        """处理文档上传事件"""
        saga = self.saga_factory.create("DOCUMENT_PROCESSING")
        await saga.process(event.payload)

    async def _handle_plan_generated(self, event: DomainEvent):
        """处理规划生成事件"""
        saga = self.saga_factory.create("PLAN_CREATION")
        await saga.create_plan(event.payload)

    async def _handle_plan_approved(self, event: DomainEvent):
        """处理规划审批事件"""
        saga = self.saga_factory.create("ARCHIVE_STRATEGIC_PLAN")
        await saga.archive(event.payload)
```

---

## 总结

本 Saga 事务一致性设计方案针对五层存储架构的特点，采用**混合式 Saga 模式**（编排式 + 编舞式），平衡了**强一致性需求**与**系统解耦**的矛盾。

**核心设计要点：**

1. **场景识别**：识别 10 个关键跨库事务场景，按一致性要求分类处理
2. **模式选择**：核心审计流程采用编排式，辅助索引流程采用编舞式
3. **补偿设计**：幂等、反向、局部失败容忍、人工干预点
4. **一致性校验**：实时 + 定时 + 全量 + 抽样四层校验机制
5. **异常处理**：指数退避重试、死信队列分类处理
6. **监控审计**：完整指标体系 + WORM 7 年审计归档

该方案满足 SOX/ISO27001 合规要求，支持系统长期演进。
