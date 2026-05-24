# SISYS 实现模式参考手册

> **版本:** v8.3.3（从 architecture.md §18 提取）
> **定位:** 开发模式参考手册（非架构决策文档）
> **提取日期:** 2026-05-23
> **关联文档:** architecture.md §18

---

_本章定义所有 AI Agent 必须遵守的实现规范，确保多人/多 Agent 协作时代码风格、架构模式、数据格式的一致性。_

### 18.1 命名模式

#### 18.1.1 数据库命名约定

| 对象 | 约定 | 示例 |
|------|------|------|
| 表名 | snake_case 复数 | `strategic_plans`, `business_plans`, `agents` |
| 列名 | snake_case | `user_id`, `created_at`, `plan_type` |
| 主键 | `id` (UUID) | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| 外键 | `{referenced_table}_id` | `plan_id`, `agent_id`, `tool_id` |
| 索引 | `idx_{table}_{columns}` | `idx_plans_created_at`, `idx_agents_role_status` |
| 唯一约束 | `uq_{table}_{columns}` | `uq_agents_email`, `uq_plans_version` |
| 检查约束 | `chk_{table}_{purpose}` | `chk_plans_status_valid`, `chk_routing_score_range` |
| 序列 | `{table}_id_seq` | `strategic_plans_id_seq` |

**PostgreSQL DDL 示例:**
```sql
CREATE TABLE strategic_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_type VARCHAR(10) NOT NULL CHECK (plan_type IN ('SP', 'BP')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    blm_stage VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT chk_plans_status_valid CHECK (status IN ('draft', 'in_progress', 'approved', 'archived'))
);

CREATE INDEX idx_plans_created_at ON strategic_plans(created_at);
CREATE UNIQUE INDEX uq_plans_version ON strategic_plans(plan_type, version);
```

#### 18.1.2 API 命名约定

| 对象 | 约定 | 示例 |
|------|------|------|
| 端点 | RESTful 复数 | `GET /api/v1/plans`, `POST /api/v1/agents` |
| 路径参数 | snake_case 在大括号内 | `/api/v1/plans/{plan_id}`, `/api/v1/agents/{agent_id}/tools` |
| 查询参数 | snake_case | `?status=draft&created_after=2026-01-01&page=1&per_page=20` |
| 请求头 | Pascal-Case | `X-Request-ID`, `X-Correlation-ID`, `Authorization` |
| API 版本 | URL 路径 | `/api/v1/`, `/api/v2/` |
| 内容类型 | 标准 MIME | `application/json`, `multipart/form-data` |

**RESTful 端点设计示例:**
```
# 战略规划资源
GET    /api/v1/plans                    # 获取规划列表
POST   /api/v1/plans                    # 创建新规划
GET    /api/v1/plans/{plan_id}          # 获取单个规划
PATCH  /api/v1/plans/{plan_id}          # 部分更新规划
DELETE /api/v1/plans/{plan_id}          # 删除规划
GET    /api/v1/plans/{plan_id}/checkpoints  # 获取规划的检查点
POST   /api/v1/plans/{plan_id}/recover  # 恢复规划到某个检查点

# Agent 资源
GET    /api/v1/agents                   # 获取 Agent 列表
GET    /api/v1/agents/{agent_id}        # 获取单个 Agent
POST   /api/v1/agents/{agent_id}/execute # 执行 Agent 任务
GET    /api/v1/agents/{agent_id}/state  # 获取 Agent 状态
POST   /api/v1/agents/arbitrate         # SYS Agent 裁决

# 财务量化分析（新增）
POST   /api/v1/financial/analyze        # 财务量化分析（NPV/IRR/现金流）
POST   /api/v1/financial/sensitivity    # 敏感性分析（龙卷风图）

# 报告生成（新增）
POST   /api/v1/reports/whitelabel       # 白标品牌定制（Logo/配色/字体）
POST   /api/v1/reports/regulatory       # 监管报告导出（银保监会 1104/EAST）

# 风险可视化（新增）
GET    /api/v1/risk/heatmap             # 风险热力图（高管视图核心）

# 高保真溯源（新增）
GET    /api/v1/documents/{doc_id}/trace # Bounding Box 坐标级溯源

# 路由决策资源
GET    /api/v1/routing-decisions        # 获取路由决策日志
GET    /api/v1/routing-decisions/{decision_id} # 获取单个决策
```

#### 18.1.3 代码命名约定

| 对象 | 约定 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `document_service.py`, `strategic_plan.py`, `routing_decision.py` |
| 包/目录 | snake_case | `domain/`, `application/`, `infrastructure/` |
| 类名 | PascalCase | `StrategicPlan`, `RoutingDecision`, `UDMRService` |
| 异常类 | PascalCase + Error/Exception | `DomainError`, `ValidationError`, `NotFoundError` |
| 函数/方法 | snake_case | `get_user_by_id()`, `create_plan()`, `assess_complexity()` |
| 变量 | snake_case | `user_id`, `plan_status`, `routing_scores` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`, `SIMILARITY_THRESHOLD` |
| 私有方法/变量 | 前缀下划线 | `_internal_method()`, `_cache` |
| 私有属性 | 前缀 `_` | `_internal_cache`, `_db_connection`, `_llm_router` |
| 类型别名 | PascalCase | `PlanId = UUID`, `RoutingScore = float` |

**Python 代码示例:**
```python
# 常量定义
MAX_RETRY_COUNT: int = 3
DEFAULT_TIMEOUT: int = 30
SIMILARITY_THRESHOLD: float = 0.9

# 类型别名
PlanId = UUID
AgentId = str
RoutingScore = float

# 类定义
class StrategicPlan:
    """战略规划实体 - BLM 六阶段模型"""

    def __init__(
        self,
        id: PlanId,
        plan_type: PlanType,
        status: PlanStatus = PlanStatus.DRAFT
    ):
        self._id = id
        self._plan_type = plan_type
        self._status = status
        self._checkpoints: List[Checkpoint] = []

    def add_checkpoint(self, checkpoint: Checkpoint) -> None:
        """添加检查点"""
        self._checkpoints.append(checkpoint)

    def _validate_status(self, status: str) -> bool:
        """验证状态有效性（私有方法）"""
        return status in [s.value for s in PlanStatus]

# 异常定义
class DomainError(Exception):
    """领域层基础异常"""
    pass

class ValidationError(DomainError):
    """验证失败异常"""
    pass

class NotFoundError(DomainError):
    """实体未找到异常"""
    pass
```

#### 18.1.4 事件命名约定

| 对象 | 约定 | 示例 |
|------|------|------|
| 领域事件类 | PascalCase + 过去式 | `DocumentProcessed`, `PlanCreated`, `RoutingDecided` |
| 事件类型字符串 | snake_case + 点分 | `document.processed`, `plan.created`, `routing.decided` |
| 事件 ID | `evt_` + ULID | `evt_01HX8Z9Q2P3Y4R5T6W7V8M0N1K` |
| 聚合 ID | `{type}_{uuid}` | `plan_01hx8z9q-2p3y-4r5t-6w7v-8m0n1k2j3h4g` |
| 命令类 | PascalCase + Command | `CreatePlanCommand`, `UpdateAgentCommand` |
| 查询类 | PascalCase + Query | `GetPlanByIdQuery`, `FindAgentsByRoleQuery` |

**领域事件示例:**
```python
class PlanCreated(BaseModel):
    """战略规划创建事件"""
    event_id: str = Field(default_factory=generate_ulid)
    event_type: str = "plan.created"
    event_version: str = "1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: str  # plan_{uuid}
    aggregate_type: str = "StrategicPlan"
    aggregate_version: int = 1
    payload: Dict[str, Any] = {
        "plan_type": "SP",
        "creator_id": "agent_ceo",
        "initial_status": "draft"
    }
    metadata: EventMetadata
    source: str = "sisys-planning-service"
```

---

### 18.2 结构模式

#### 18.2.1 文件组织模式

**标准 Python 模块结构:**
```python
"""
文档处理服务 - 支持 17 种文档格式的解析与索引

详细文档：
- 支持 PDF、DOCX、XLSX、PPTX、TXT、MD、HTML、XML、JSON、CSV 等格式
- 集成 Unstructured.io 进行多模态解析
- 支持 OCR、表格提取、布局保持
"""

# 导入顺序：标准库 → 第三方库 → 本地库
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from fastapi import Depends, UploadFile
import aiofiles

# 本地导入
from src.domain.models.document import Document
from src.domain.services.rag_service import RAGService
from src.infrastructure.persistence.document_repository import DocumentRepository
```

**模块导出模式 (`__init__.py`):**
```python
# src/domain/__init__.py
"""领域层 - 核心业务逻辑，零外部技术依赖"""

from .models.document import Document
from .models.agent import Agent
from .models.strategic_plan import StrategicPlan
from .services.rag_service import RAGService
from .exceptions import DomainError, ValidationError

__all__ = [
    "Document",
    "Agent",
    "StrategicPlan",
    "RAGService",
    "DomainError",
    "ValidationError",
]
```

#### 18.2.2 类结构模式

**领域实体类结构:**
```python
class StrategicPlan:
    """
    战略规划实体 - 基于 BLM 六阶段模型

    Attributes:
        id: 规划唯一标识 (UUID)
        plan_type: 规划类型 (SP/BP)
        status: 当前状态
        blm_stage: BLM 阶段 (差距分析/市场洞察/业务设计/...)
        checkpoints: 检查点列表
        created_at: 创建时间
        updated_at: 更新时间

    Example:
        >>> plan = StrategicPlan(plan_type=PlanType.SP)
        >>> plan.start_market_insight()
        >>> plan.add_checkpoint(checkpoint)
    """

    # 类变量
    MAX_VERSIONS: int = 10
    ALLOWED_STATUSES: List[str] = ["draft", "in_progress", "approved", "archived"]

    # 初始化
    def __init__(
        self,
        id: UUID,
        plan_type: PlanType,
        status: PlanStatus = PlanStatus.DRAFT,
        creator_id: Optional[str] = None
    ):
        """初始化战略规划"""
        self._id = id
        self._plan_type = plan_type
        self._status = status
        self._creator_id = creator_id
        self._checkpoints: List[Checkpoint] = []
        self._version: int = 1
        self.created_at =  datetime.now(UTC)
        self.updated_at =  datetime.now(UTC)

    # 公共方法 - 业务行为
    def start_market_insight(self) -> None:
        """启动市场洞察阶段"""
        self._blm_stage = BLMStage.MARKET_INSIGHT
        self.updated_at =  datetime.now(UTC)

    def add_checkpoint(self, checkpoint: Checkpoint) -> None:
        """添加检查点"""
        self._checkpoints.append(checkpoint)
        self.updated_at =  datetime.now(UTC)

    def approve(self) -> None:
        """批准规划"""
        if self._status != PlanStatus.IN_PROGRESS:
            raise ValidationError("只有进行中的规划可以批准")
        self._status = PlanStatus.APPROVED
        self.updated_at =  datetime.now(UTC)

    # 私有方法 - 内部实现
    def _validate_status(self, status: str) -> bool:
        """验证状态有效性"""
        return status in self.ALLOWED_STATUSES

    def _calculate_next_version(self) -> int:
        """计算下一个版本号"""
        return self._version + 1

    # 特殊方法
    def __str__(self) -> str:
        return f"StrategicPlan(id={self._id}, type={self._plan_type}, status={self._status})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StrategicPlan):
            return False
        return self._id == other._id
```

**领域服务类结构:**
```python
class UDMRService:
    """
    统一动态模型路由服务 - 三层决策架构

    Responsibilities:
        - L1 合规性检查（敏感数据、数据驻留、白名单）
        - L2 任务复杂度评估（语义匹配、历史成功率、成本效率）
        - L3 路由决策执行（本地优先、云端兜底）

    Dependencies:
        - ComplianceGateway: 合规性网关
        - ComplexityAssessor: 复杂度评估器
        - RouterExecutor: 路由决策执行器
        - RoutingLogRepository: 路由日志仓储
    """

    def __init__(
        self,
        compliance_gateway: ComplianceGateway,
        complexity_assessor: ComplexityAssessor,
        router_executor: RouterExecutor,
        routing_log_repo: RoutingLogRepository
    ):
        self._compliance_gateway = compliance_gateway
        self._complexity_assessor = complexity_assessor
        self._router_executor = router_executor
        self._routing_log_repo = routing_log_repo

    async def route(self, task: Task) -> RoutingDecision:
        """
        执行三层路由决策

        Args:
            task: 待路由的任务

        Returns:
            RoutingDecision: 路由决策结果

        Raises:
            ComplianceError: 当任务未通过合规性检查时
            RoutingError: 当路由决策失败时
        """
        # L1: 合规性检查
        compliance_result = await self._compliance_gateway.check(task)
        if not compliance_result.allowed:
            raise ComplianceError(compliance_result.reason)

        # L2: 复杂度评估
        candidate_models = await self._get_candidate_models(task)
        scored_models = await self._complexity_assessor.assess(task, candidate_models)

        # L3: 路由决策
        decision = await self._router_executor.decide(scored_models)

        # 记录路由日志
        await self._log_routing_decision(task, decision)

        return decision

    async def _get_candidate_models(self, task: Task) -> List[Model]:
        """获取候选模型列表"""
        # 实现细节
        pass

    async def _log_routing_decision(self, task: Task, decision: RoutingDecision) -> None:
        """记录路由决策日志"""
        # 实现细节
        pass
```

#### 18.2.3 目录组织原则

**分层依赖规则:**
```
接口层 (interfaces/)
    ↓ 依赖
应用层 (application/)
    ↓ 依赖
领域层 (domain/)  ← 核心业务逻辑，不依赖任何外层
    ↑ 实现
基础设施层 (infrastructure/)  ← 实现领域层接口
```

**各层职责:**
| 层 | 职责 | 依赖方向 | 示例 |
|----|------|---------|------|
| 领域层 | 核心业务逻辑、实体、值对象、领域服务接口 | 无外部依赖 | `StrategicPlan`, `Agent`, `RAGService` (接口) |
| 应用层 | 用例编排、命令/查询处理、事件分发 | 依赖领域层 | `CreatePlanCommandHandler`, `PlanningUC` |
| 基础设施层 | 技术实现、外部服务适配器、仓储实现 | 依赖领域层 + 应用层接口 | `PostgreSQLPlanRepository`, `OllamaLLMAdapter` |
| 接口层 | 外部适配器、CLI、API、事件监听器 | 依赖应用层 | `FastAPIRoutes`, `CLICommands` |

---

### 18.3 格式模式

#### 18.3.1 API 响应格式

**成功响应 (JSON:API 风格):**
```json
{
  "data": {
    "id": "plan_01hx8z9q2p3y4r5t6w7v8m0n1k",        /* pragma: allowlist secret */
    "type": "strategic_plan",
    "attributes": {
      "plan_type": "SP",
      "status": "draft",
      "blm_stage": "market_insight",
      "version": 1,
      "created_at": "2026-02-25T10:30:00Z",
      "updated_at": "2026-02-25T10:30:00Z"
    },
    "relationships": {
      "creator": {
        "data": { "id": "agent_ceo", "type": "agent" }
      },
      "checkpoints": {
        "data": [
          { "id": "ckpt_01hx8z9q", "type": "checkpoint" }
        ]
      }
    }
  },
  "meta": {
    "request_id": "req_01hx8z9q2p3y4r5t",
    "timestamp": "2026-02-25T10:30:00Z",
    "version": "1.0"
  }
}
```

**错误响应:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数验证失败",
    "details": [
      {
        "field": "plan_type",
        "message": "必须是 'SP' 或 'BP'",
        "invalid_value": "invalid"
      }
    ],
    "request_id": "req_01hx8z9q2p3y4r5t",
    "documentation_url": "https://docs.sisys.ai/errors/validation-error"
  },
  "meta": {
    "timestamp": "2026-02-25T10:30:00Z"
  }
}
```

**分页响应:**
```json
{
  "data": [...],
  "meta": {
    "pagination": {
      "total": 100,
      "page": 1,
      "per_page": 20,
      "total_pages": 5
    }
  },
  "links": {
    "self": "/api/v1/plans?page=1&per_page=20",
    "first": "/api/v1/plans?page=1&per_page=20",
    "prev": null,
    "next": "/api/v1/plans?page=2&per_page=20",
    "last": "/api/v1/plans?page=5&per_page=20"
  }
}
```

**批量操作响应:**
```json
{
  "data": [
    { "id": "plan_1", "type": "strategic_plan", ... },
    { "id": "plan_2", "type": "strategic_plan", ... }
  ],
  "meta": {
    "total": 2,
    "succeeded": 2,
    "failed": 0
  }
}
```

#### 18.3.2 日期时间格式

| 场景 | 格式 | 示例 | 说明 |
|------|------|------|------|
| API 传输 | ISO 8601 + UTC | `2026-02-25T10:30:00Z` | 所有 API 请求/响应使用 UTC |
| 数据库存储 | TIMESTAMP WITH TIMEZONE | `2026-02-25 10:30:00+00` | PostgreSQL 带时区时间戳 |
| 日志记录 | ISO 8601 + 毫秒 | `2026-02-25T10:30:00.123Z` | 精确到毫秒 |
| 用户显示 | 本地化格式 | `2026 年 2 月 25 日 10:30` | 根据用户时区本地化 |
| 内部计算 | datetime 对象 | `datetime(2026, 2, 25, 10, 30, 0)` | Python datetime 对象 |

**Python 时间处理示例:**
```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# 创建 UTC 时间
utc_now = datetime.now(timezone.utc)  # 2026-02-25T10:30:00+00:00

# 转换为特定时区
shanghai_time = utc_now.astimezone(ZoneInfo("Asia/Shanghai"))  # 2026-02-25T18:30:00+08:00

# ISO 8601 格式化
iso_string = utc_now.isoformat()  # '2026-02-25T10:30:00+00:00'
iso_utc = utc_now.strftime('%Y-%m-%dT%H:%M:%SZ')  # '2026-02-25T10:30:00Z'

# 解析 ISO 字符串
parsed = datetime.fromisoformat('2026-02-25T10:30:00Z')
```

#### 18.3.3 数据交换格式

**JSON 字段命名:**
- 使用 snake_case: `user_id`, `plan_type`, `created_at`
- 避免 camelCase: ❌ `userId`, `planType`

**布尔值:**
- 使用 JSON 原生 `true`/`false`
- ❌ 避免 `1`/`0` 或 `"true"`/`"false"` 字符串

**空值处理:**
- 使用 JSON 原生 `null`
- 字段不存在 vs `null` 的语义区分：
  - 字段不存在：该字段未被设置
  - 字段为 `null`：该字段明确设置为空

**数字精度:**
```json
{
  "amount": "100.50",  // 金额使用字符串避免精度丢失
  "quantity": 10,      // 整数直接使用数字
  "score": 0.95,       // 浮点数直接使用数字
  "ratio": 0.3333333   // 高精度浮点数
}
```

**UUID 格式:**
- 小写带连字符：`01hx8z9q-2p3y-4r5t-6w7v-8m0n1k2j3h4g`
- API 响应中带类型前缀：`plan_01hx8z9q-2p3y-4r5t-6w7v-8m0n1k2j3h4g`

---

### 18.4 通信模式

#### 18.4.1 事件结构标准

**领域事件基类（与 §10.2 一致，实际实现使用 `@dataclass(frozen=True)`）:**
```python
from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid
from typing import Any, ClassVar

@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类 - 零外部依赖（无 Pydantic），详见 §10.2"""
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    schema_version: str = "1.0.0"
    aggregate_id: uuid.UUID | None = None
    aggregate_type: str = ""
    version: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: uuid.UUID | None = None
    causation_id: uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _registry: ClassVar[dict[str, type[DomainEvent]]] = {}

    def to_dict(self) -> dict[str, Any]:
        """序列化事件为字典"""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        """使用事件类型注册表从字典反序列化事件"""
        ...
```

> **注意:** 文档 §18.6 架构模式中部分旧示例仍使用 Pydantic `BaseModel` 风格定义，
> 实际代码中 DomainEvent 统一使用 `@dataclass(frozen=True)`，
> Pydantic 仅在应用层/基础设施层边界使用。

**具体领域事件示例:**
```python
from dataclasses import dataclass, field
import uuid
from typing import Any

@dataclass(frozen=True)
class PlanCreatedEvent(DomainEvent):
    """战略规划创建事件"""
    event_type: str = field(default="PlanCreated", init=False)
    plan_type: str = ""
    creator_id: str = ""
    initial_status: str = "draft"

@dataclass(frozen=True)
class RoutingDecidedEvent(DomainEvent):
    """路由决策完成事件"""
    event_type: str = field(default="RoutingDecided", init=False)
    task_id: uuid.UUID | None = None
    selected_model: str = ""
    estimated_cost: float = 0.0
    routing_latency_ms: int = 0
```

#### 18.4.2 状态管理模式

**不可变状态更新:**
```python
from dataclasses import dataclass, field, replace
from typing import Optional, Any, Dict

@dataclass(frozen=True)
class AgentState:
    """Agent 状态 - 不可变"""
    agent_id: str
    role: str
    status: str
    current_task: Optional[str] = None
    isolation_level: str = "L4"
    blackboard: Dict[str, Any] = field(default_factory=dict)

    def with_status(self, new_status: str) -> 'AgentState':
        """返回新状态对象，不修改原对象"""
        return replace(self, status=new_status)

    def with_task(self, task_id: str) -> 'AgentState':
        """分配新任务"""
        return replace(self, current_task=task_id, status="busy")

    def release_task(self) -> 'AgentState':
        """释放任务"""
        return replace(self, current_task=None, status="idle")

# 使用示例
state = AgentState(agent_id="ceo", role="CEO", status="idle")
new_state = state.with_task("task_001")  # 创建新对象
# state 保持不变，new_state 是新对象
```

**动作命名规范:**
```python
# 命令类：动词 + 名词 + Command
class CreateStrategicPlanCommand(BaseModel):
    plan_type: PlanType
    creator_id: str

class UpdateAgentIdentityCommand(BaseModel):
    agent_id: str
    new_identity: str

class RecoverToCheckpointCommand(BaseModel):
    checkpoint_id: UUID
    modifications: List[Modification]

# 查询类：Get/Find + 实体 + By + 条件
class GetStrategicPlanByIdQuery(BaseModel):
    plan_id: UUID

class FindAgentsByRoleQuery(BaseModel):
    role: str

class ListPlansByStatusQuery(BaseModel):
    status: PlanStatus
```

---

### 18.5 流程模式

#### 18.5.1 错误处理模式

**异常层次结构（实际实现，与 `src/domain/exceptions/` 一致）:**
```
BaseException (抽象根类，src/domain/exceptions/base_exceptions.py)
├── SystemException (系统级异常)
│   ├── ConfigurationError (配置错误)
│   ├── NetworkError (网络错误)
│   ├── StorageError (存储错误)
│   └── MessageBusError (消息总线错误)
├── BusinessException (业务级异常)
│   ├── ValidationError (验证失败)
│   ├── NotFoundError (实体未找到)
│   ├── ConflictError (冲突错误)
│   ├── PermissionDeniedError (权限拒绝)
│   ├── AuthenticationError (认证失败)
│   ├── InvalidStateError (无效状态)
│   ├── InvalidStateTransitionError (无效状态转换)
│   ├── BusinessRuleViolationError (业务规则违反)
│   ├── AuditError (审计错误)
│   ├── PasswordValidationError (密码验证失败)
│   ├── ComplianceLockError (合规锁定错误)
│   └── RoleAlreadyExistsError / RoleNotFoundError / ... (角色管理异常)
└── ExternalException (外部服务异常)
    ├── ThirdPartyError (第三方服务错误)
    ├── TimeoutError (超时错误)
    ├── ServiceUnavailableError (服务不可用)
    └── UnknownError (未知外部错误)
```

> **与旧版文档的差异:** 旧版 §18.5.1 使用 `DomainException` / `InfrastructureException` 二层结构，
> 实际已重构为 `SystemException` / `BusinessException` / `ExternalException` 三层体系，
> 详见 `docs/architecture/sisys-uni-exception-design.md`。

**异常类定义:**
```python
# src/domain/exceptions/base_exceptions.py
from typing import Any

class BaseException(Exception):
    """异常层次结构根类（非 Python 内置 BaseException）"""
    def __init__(self, message: str, code: str = "", details: dict[str, Any] | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class SystemException(BaseException):
    """系统级异常 - 基础设施故障（配置/网络/存储/消息）"""
    pass

class BusinessException(BaseException):
    """业务级异常 - 业务规则违反（验证/权限/状态）"""
    pass

class ExternalException(BaseException):
    """外部服务异常 - 第三方服务不可用"""
    pass
```
```

**全局异常处理 (FastAPI):**
```python
# src/interfaces/api/middleware/exception_handlers.py
# 实际实现使用 EXCEPTION_HTTP_MAP 映射表，详见 sisys-uni-exception-design.md

from src.domain.exceptions import (
    BaseException,
    SystemException,
    BusinessException,
    ExternalException,
    ValidationError,
    NotFoundError,
    PermissionDeniedError,
)

async def base_exception_handler(request: Request, exc: BaseException):
    """统一异常处理 - 基于 EXCEPTION_HTTP_MAP 自动映射 HTTP 状态码"""
    status_code = EXCEPTION_HTTP_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code or type(exc).__name__,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None)
            }
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")}
    )

# 注册异常处理器
def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(BaseException, base_exception_handler)
```

#### 18.5.2 日志记录模式

**结构化日志格式:**
```python
import logging
import json
from datetime import datetime
from typing import Dict, Any

class StructuredFormatter(logging.Formatter):
    """结构化日志格式器 - JSON 输出"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp":  datetime.now(UTC).isoformat() + "Z",
            "level": record.levelname,
            "service": "sisys-api",
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "message": record.getMessage(),
            "context": {
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
        }

        # 添加额外字段
        if hasattr(record, "context"):
            log_entry["context"].update(record.context)

        return json.dumps(log_entry, ensure_ascii=False)

# 使用示例
logger = logging.getLogger("sisys.planning")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(StructuredFormatter())
logger.addHandler(handler)

# 记录日志
logger.info(
    "文档处理完成",
    extra={
        "context": {
            "document_id": "doc_01hx8z9q",
            "processing_time_ms": 234,
            "pages_processed": 15
        }
    }
)
```

**日志输出示例:**
```json
{
  "timestamp": "2026-02-25T10:30:00.123Z",
  "level": "INFO",
  "service": "sisys-api",
  "trace_id": "01hx8z9q2p3y4r5t",
  "span_id": "6w7v8m0n",
  "message": "文档处理完成",
  "context": {
    "module": "document_service",
    "function": "process_document",
    "line": 145,
    "document_id": "doc_01hx8z9q",
    "processing_time_ms": 234,
    "pages_processed": 15
  }
}
```

**日志级别使用指南:**
| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 调试信息，开发环境 | `DEBUG: 路由决策详细步骤：L1 通过，L2 评分...` |
| INFO | 正常业务流程 | `INFO: 文档处理完成 document_id=doc_001` |
| WARNING | 可恢复的异常 | `WARNING: LLM API 调用超时，正在重试 (1/3)` |
| ERROR | 需要关注的错误 | `ERROR: 数据库连接失败，请检查配置` |
| CRITICAL | 系统级故障 | `CRITICAL: 消息队列不可用，事件丢失` |

#### 18.5.3 重试模式

**标准重试配置:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.infrastructure.exceptions import DatabaseError, ExternalServiceError

RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 2,
    "initial_delay_ms": 100,
    "max_delay_ms": 10000,
    "retryable_exceptions": [DatabaseError, ExternalServiceError],
}

# 使用装饰器
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.1, max=10),
    retry=retry_if_exception_type((DatabaseError, ExternalServiceError))
)
async def call_external_service(data: Dict[str, Any]) -> Dict[str, Any]:
    """调用外部服务，带重试"""
    # 实现
    pass

# 使用重试管理器类
from tenacity import RetryCallState, retry_if_result

class RetryManager:
    """重试管理器 - 支持自定义重试逻辑"""

    @staticmethod
    def with_custom_logic(
        max_attempts: int = 3,
        retryable_exceptions: tuple = (DatabaseError, ExternalServiceError),
        on_retry: Optional[Callable] = None
    ):
        """自定义重试逻辑"""
        def decorator(func):
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=0.1, max=10),
                retry=retry_if_exception_type(retryable_exceptions),
                after=on_retry  # 每次重试后回调
            )
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper
        return decorator

# 使用示例
@RetryManager.with_custom_logic(
    max_attempts=3,
    on_retry=lambda state: logger.warning(f"重试 {state.attempt_number}")
)
async def create_strategic_plan(data):
    pass
```

---

### 18.6 架构模式

> **⚠️ 实现模式说明：** 本节的代码示例为设计模式规范（V1/V2 目标），
> **与当前 MVP 实现有以下关键差异：**
>
> | 方面 | 文档示例（设计规范） | 实际代码（MVP 实现） | 文件位置 |
> |------|---------------------|---------------------|---------|
> | **接口定义** | `ABC` + `@abstractmethod` | `Protocol` + `@runtime_checkable` | `src/domain/ports/*.py` |
> | **仓储基类** | `IStrategicPlanRepository` | `L2RdbPort[T]` 泛型基类 | `src/domain/ports/l2_rdb.py` |
> | **仓储方法** | `add()/update()/remove()` | `save()/delete()/list_all()` | 同上 |
> | **DomainEvent** | Pydantic `BaseModel` + `Config.frozen` | `@dataclass(frozen=True)` + `__init_subclass__` 注册 | `src/domain/events/base.py` |
> | **异常体系** | `DomainException/InfrastructureException` | `SystemException/BusinessException/ExternalException` | `src/domain/exceptions/__init__.py` |
> | **依赖注入** | `dependency_injector` 库 | 自研 `PortRegistry` + `Resolver` | `src/domain/ports/registry.py`, `resolver.py` |
> | **CQRS** | `commands/queries/handlers` 分离 | 未实现，用 `services+use_cases+event_handlers` | — |
> | **Settings** | `pydantic.BaseSettings` | `pydantic_settings.BaseSettings` | Pydantic v2 变更 |
>
> **阅读指南：** 本节示例展示"目标架构"的代码风格，用于未来 V1/V2 开发参考。
> 当前 MVP 实现遵循 §10、§18.8.1 和各子设计文档中的实际代码模式。

#### 18.6.1 CQRS 模式规范

> **状态：⚠️ 设计完成，待实现（V1）**
> 当前应用层使用 `services/` + `use_cases/` + `event_handlers/` 模式，CQRS 分离规划于 Epic 5。

**命令命名:**
```python
# 命令类：动词 + 名词 + Command
class CreateStrategicPlanCommand(BaseModel):
    plan_type: PlanType
    creator_id: str
    initial_status: PlanStatus = PlanStatus.DRAFT

class UpdateAgentIdentityCommand(BaseModel):
    agent_id: str
    new_identity: str
    reason: str

class RecoverToCheckpointCommand(BaseModel):
    checkpoint_id: UUID
    modifications: List[Modification]
    recovery_mode: str  # "Replay" or "Override"
```

**查询命名:**
```python
# 查询类：Get/Find/List + 实体 + By + 条件
class GetStrategicPlanByIdQuery(BaseModel):
    plan_id: UUID

class FindAgentsByRoleQuery(BaseModel):
    role: str

class ListPlansByStatusQuery(BaseModel):
    status: PlanStatus
    page: int = 1
    per_page: int = 20

class SearchPlansByKeywordQuery(BaseModel):
    keyword: str
    filters: Optional[Dict[str, Any]] = None
```

**命令处理器:**
```python
class CreateStrategicPlanCommandHandler:
    """创建战略规划命令处理器"""

    def __init__(
        self,
        plan_repository: IStrategicPlanRepository,
        event_dispatcher: IEventDispatcher
    ):
        self._plan_repository = plan_repository
        self._event_dispatcher = event_dispatcher

    async def handle(self, command: CreateStrategicPlanCommand) -> UUID:
        """处理创建命令"""
        # 1. 创建实体
        plan = StrategicPlan(
            id=uuid4(),
            plan_type=command.plan_type,
            creator_id=command.creator_id,
            status=command.initial_status
        )

        # 2. 保存到仓储
        await self._plan_repository.add(plan)

        # 3. 发布领域事件
        await self._event_dispatcher.publish(
            PlanCreatedEvent(
                aggregate_id=str(plan.id),
                payload={
                    "plan_type": plan.plan_type.value,
                    "creator_id": plan.creator_id
                }
            )
        )

        return plan.id
```

**查询处理器:**
```python
class GetStrategicPlanByIdQueryHandler:
    """获取战略规划查询处理器"""

    def __init__(
        self,
        plan_repository: IStrategicPlanRepository,
        cache: ISemanticCache
    ):
        self._plan_repository = plan_repository
        self._cache = cache

    async def handle(self, query: GetStrategicPlanByIdQuery) -> Optional[PlanDTO]:
        """处理查询"""
        # 1. 尝试缓存
        cached = await self._cache.get(f"plan:{query.plan_id}")
        if cached:
            return cached

        # 2. 从仓储加载
        plan = await self._plan_repository.get_by_id(query.plan_id)
        if not plan:
            return None

        # 3. 转换为 DTO
        dto = PlanDTO.from_entity(plan)

        # 4. 写入缓存
        await self._cache.set(f"plan:{query.plan_id}", dto, ttl=3600)

        return dto
```

#### 18.6.2 仓储模式规范

**仓储接口:**
```python
from abc import ABC, abstractmethod
from typing import Optional, List, Generic, TypeVar
from uuid import UUID

T = TypeVar('T')

class IStrategicPlanRepository(ABC):
    """战略规划仓储接口"""

    @abstractmethod
    async def add(self, plan: StrategicPlan) -> None:
        """添加新规划"""
        pass

    @abstractmethod
    async def get_by_id(self, plan_id: UUID) -> Optional[StrategicPlan]:
        """根据 ID 获取"""
        pass

    @abstractmethod
    async def update(self, plan: StrategicPlan) -> None:
        """更新规划"""
        pass

    @abstractmethod
    async def remove(self, plan_id: UUID) -> None:
        """删除规划"""
        pass

    @abstractmethod
    async def find_by_criteria(
        self,
        status: Optional[PlanStatus] = None,
        plan_type: Optional[PlanType] = None,
        created_after: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 20
    ) -> List[StrategicPlan]:
        """按条件查询"""
        pass
```

**仓储实现:**
```python
class StrategicPlanRepositoryImpl(IStrategicPlanRepository):
    """战略规划仓储实现 - PostgreSQL"""

    def __init__(self, db: DatabaseConnection):
        self._db = db

    async def add(self, plan: StrategicPlan) -> None:
        """添加新规划"""
        query = """
            INSERT INTO strategic_plans (id, plan_type, status, creator_id, created_at)
            VALUES (:id, :plan_type, :status, :creator_id, :created_at)
        """
        await self._db.execute(query, {
            "id": plan.id,
            "plan_type": plan.plan_type.value,
            "status": plan.status.value,
            "creator_id": plan.creator_id,
            "created_at": plan.created_at
        })

    async def get_by_id(self, plan_id: UUID) -> Optional[StrategicPlan]:
        """根据 ID 获取"""
        query = """
            SELECT * FROM strategic_plans WHERE id = :id
        """
        result = await self._db.fetch_one(query, {"id": plan_id})
        if not result:
            return None
        return self._map_to_entity(result)

    async def find_by_criteria(
        self,
        status: Optional[PlanStatus] = None,
        plan_type: Optional[PlanType] = None,
        created_after: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 20
    ) -> List[StrategicPlan]:
        """按条件查询"""
        query = "SELECT * FROM strategic_plans WHERE 1=1"
        params = {}

        if status:
            query += " AND status = :status"
            params["status"] = status.value

        if plan_type:
            query += " AND plan_type = :plan_type"
            params["plan_type"] = plan_type.value

        if created_after:
            query += " AND created_at >= :created_after"
            params["created_after"] = created_after

        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = per_page
        params["offset"] = (page - 1) * per_page

        results = await self._db.fetch_all(query, params)
        return [self._map_to_entity(r) for r in results]

    def _map_to_entity(self, row) -> StrategicPlan:
        """数据库行映射到实体"""
        return StrategicPlan(
            id=row["id"],
            plan_type=PlanType(row["plan_type"]),
            status=PlanStatus(row["status"]),
            creator_id=row["creator_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
```

#### 18.6.3 领域服务规范

**何时使用领域服务:**
1. 操作涉及多个领域对象，不属于单个实体
2. 需要外部依赖但必须在领域层执行
3. 执行无状态的业务逻辑

**领域服务示例:**
```python
class PlanningService:
    """
    战略规划领域服务

    Responsibilities:
        - 协调多个实体完成复杂业务逻辑
        - 不持有状态，每次调用都是独立的
        - 依赖仓储接口和外部服务接口
    """

    def __init__(
        self,
        plan_repository: IStrategicPlanRepository,
        checkpoint_repository: ICheckpointRepository,
        event_dispatcher: IEventDispatcher
    ):
        self._plan_repository = plan_repository
        self._checkpoint_repository = checkpoint_repository
        self._event_dispatcher = event_dispatcher

    async def execute_blm_stage(
        self,
        plan_id: UUID,
        stage: BLMStage,
        input_data: Dict[str, Any]
    ) -> BLMOutput:
        """
        执行 BLM 阶段

        涉及多个实体：StrategicPlan, Checkpoint, Agent
        需要协调多个步骤
        """
        # 1. 加载规划
        plan = await self._plan_repository.get_by_id(plan_id)
        if not plan:
            raise NotFoundError("StrategicPlan", str(plan_id))

        # 2. 验证阶段转换
        plan.validate_stage_transition(stage)

        # 3. 执行阶段逻辑
        output = await self._execute_stage_logic(plan, stage, input_data)

        # 4. 创建检查点
        checkpoint = Checkpoint(
            stage=stage,
            output=output,
            status="completed"
        )
        plan.add_checkpoint(checkpoint)

        # 5. 保存
        await self._plan_repository.update(plan)
        await self._checkpoint_repository.add(checkpoint)

        # 6. 发布事件
        await self._event_dispatcher.publish(
            PlanStageCompletedEvent(
                aggregate_id=str(plan_id),
                payload={"stage": stage.value, "output": output}
            )
        )

        return output
```

#### 18.6.4 工厂模式规范

**工厂类:**
```python
class StrategicPlanFactory:
    """战略规划工厂 - 复杂对象创建"""

    def __init__(
        self,
        default_checkpoints: List[Checkpoint],
        default_tools: List[Tool]
    ):
        self._default_checkpoints = default_checkpoints
        self._default_tools = default_tools

    def create(
        self,
        plan_type: PlanType,
        creator_id: str
    ) -> StrategicPlan:
        """创建基础战略规划"""
        return StrategicPlan(
            id=uuid4(),
            plan_type=plan_type,
            creator_id=creator_id,
            status=PlanStatus.DRAFT
        )

    def create_with_defaults(
        self,
        plan_type: PlanType,
        creator_id: str
    ) -> StrategicPlan:
        """创建带默认检查点的战略规划"""
        plan = self.create(plan_type, creator_id)

        # 添加默认检查点
        for checkpoint_template in self._default_checkpoints:
            plan.add_checkpoint(checkpoint_template.clone())

        return plan

    def create_from_dto(
        self,
        dto: CreatePlanDTO
    ) -> StrategicPlan:
        """从 DTO 创建战略规划"""
        plan = StrategicPlan(
            id=uuid4(),
            plan_type=dto.plan_type,
            creator_id=dto.creator_id,
            status=dto.initial_status or PlanStatus.DRAFT
        )

        # 添加工具
        for tool_dto in dto.tools:
            tool = Tool.from_dto(tool_dto)
            plan.add_tool(tool)

        return plan
```

---

### 18.7 测试规范

#### 18.7.1 测试命名规范

**单元测试:**
```python
# 命名格式：test_{method}_{scenario}_{expected_result}

class TestStrategicPlan:
    """战略规划单元测试"""

    def test_create_plan_with_invalid_status_raises_validation_error(self):
        """创建规划时状态无效应抛出验证异常"""
        with pytest.raises(ValidationError):
            StrategicPlan(id=uuid4(), plan_type=PlanType.SP, status="invalid")

    def test_update_agent_when_not_found_raises_not_found_error(self):
        """更新不存在的 Agent 应抛出未找到异常"""
        with pytest.raises(NotFoundError):
            await agent_service.update_agent(non_existent_id, {...})

    def test_recover_checkpoint_with_replay_mode_ensures_strong_consistency(self):
        """Replay 模式恢复检查点应保证强一致性"""
        # Arrange
        checkpoint = create_test_checkpoint()

        # Act
        result = await recovery_service.recover(
            checkpoint.id,
            modifications=[],
            mode="Replay"
        )

        # Assert
        assert result.consistency_guarantee == "strong"
```

**集成测试:**
```python
# 命名格式：test_{feature}_{scenario}

class TestStrategicPlanningWorkflow:
    """战略规划工作流集成测试"""

    async def test_strategic_planning_workflow_create_to_approval(self):
        """战略规划工作流：从创建到批准的完整流程"""
        # 测试完整工作流

    async def test_agent_collaboration_with_eip_isolation(self):
        """Agent 协作：EIP 隔离协议测试"""
        # 测试隔离协议

    async def test_udmr_routing_with_local_priority(self):
        """UDMR 路由：本地优先策略测试"""
        # 测试路由决策
```

**测试类命名:**
```python
# 格式：{ClassName}Tests 或 Test{ClassName}
class StrategicPlanTests:
    pass

class TestStrategicPlan:
    pass
```

#### 18.7.2 测试固件（Fixture）规范

**Fixture 命名:**
```python
# 格式：{entity}_data / {entity}_builder / {entity}_factory

@pytest.fixture
def strategic_plan_data() -> Dict[str, Any]:
    """战略规划测试数据"""
    return {
        "plan_type": "SP",
        "status": "draft",
        "creator_id": "agent_ceo"
    }

@pytest.fixture
def strategic_plan_builder():
    """战略规划构建器"""
    return StrategicPlanBuilder()

@pytest.fixture(scope="function")
def db_session():
    """数据库会话 Fixture - 每个测试函数独立"""
    session = create_test_session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture(scope="module")
def app_client():
    """FastAPI 测试客户端 - 每个测试模块共享"""
    app = create_app(test_config=True)
    with TestClient(app) as client:
        yield client
```

**测试数据构建器模式:**
```python
class StrategicPlanBuilder:
    """战略规划测试数据构建器"""

    def __init__(self):
        self._id = uuid4()
        self._plan_type = PlanType.SP
        self._status = PlanStatus.DRAFT
        self._creator_id = "agent_ceo"
        self._checkpoints = []

    def with_id(self, id: UUID) -> 'StrategicPlanBuilder':
        self._id = id
        return self

    def with_status(self, status: PlanStatus) -> 'StrategicPlanBuilder':
        self._status = status
        return self

    def with_creator(self, creator_id: str) -> 'StrategicPlanBuilder':
        self._creator_id = creator_id
        return self

    def with_checkpoint(self, checkpoint: Checkpoint) -> 'StrategicPlanBuilder':
        self._checkpoints.append(checkpoint)
        return self

    def build(self) -> StrategicPlan:
        """构建战略规划实体"""
        plan = StrategicPlan(
            id=self._id,
            plan_type=self._plan_type,
            creator_id=self._creator_id,
            status=self._status
        )
        for checkpoint in self._checkpoints:
            plan.add_checkpoint(checkpoint)
        return plan

# 使用示例
def test_plan_with_multiple_checkpoints():
    plan = (StrategicPlanBuilder()
            .with_status(PlanStatus.IN_PROGRESS)
            .with_checkpoint(create_market_insight_checkpoint())
            .with_checkpoint(create_business_design_checkpoint())
            .build())

    assert len(plan.checkpoints) == 2
```

#### 18.7.3 Mock/Stub 规范

**Mock 命名:**
```python
# 格式：mock_{dependency}

def test_service_with_mock(mock_llm_router, mock_event_bus):
    """使用 Mock 测试服务"""
    # Arrange
    mock_llm_router.route.return_value = {
        "selected_model": "ollama/qwen2.5-7b",
        "estimated_cost": 0.001
    }

    # Act
    result = await udmr_service.route(test_task)

    # Assert
    mock_llm_router.route.assert_called_once()
    assert result.selected_model == "ollama/qwen2.5-7b"
```

**pytest-mock 使用:**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

async def test_service_with_pytest_mock(mocker):
    """使用 pytest-mock 测试"""
    # Mock 仓储
    mock_repo = mocker.patch("src.infrastructure.persistence.PlanRepository")
    mock_repo.get_by_id = AsyncMock(return_value=test_plan)

    # Mock 事件分发器
    mock_event_dispatcher = mocker.patch("src.application.services.EventDispatcher")
    mock_event_dispatcher.publish = AsyncMock()

    # 测试
    result = await service.get_plan(test_id)

    # 验证
    mock_repo.get_by_id.assert_called_once_with(test_id)
```

#### 18.7.4 测试覆盖率要求

| 模块 | 最低覆盖率 | 测量方式 |
|------|----------|---------|
| 领域层 | 90% | `pytest --cov=src/domain --cov-fail-under=90` |
| 应用层 | 85% | `pytest --cov=src/application --cov-fail-under=85` |
| 基础设施层 | 75% | `pytest --cov=src/infrastructure --cov-fail-under=75` |
| 接口层 | 70% | `pytest --cov=src/interfaces --cov-fail-under=70` |
| **整体** | **80%** | `pytest --cov=src --cov-fail-under=80` |

**覆盖率测量命令:**
```bash
# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=80

# 查看未覆盖的行
pytest --cov=src --cov-report=term-missing:skip-covered

# 生成 XML 报告 (CI/CD)
pytest --cov=src --cov-report=xml
```

---

### 18.8 开发规范

#### 18.8.1 依赖注入规范

> **实现说明:** 实际代码使用自研 `PortRegistry` + `Resolver` 模式（`src/domain/ports/registry.py`、`src/domain/ports/resolver.py`），
> 通过 `composition_root.py` 统一注册 ~80 个端口。不使用第三方 DI 框架。

**端口注册（composition_root.py）:**
```python
from src.domain.ports.registry import PortRegistry, PortSpec, register_port
from src.domain.ports.resolver import resolve, Resolver
from src.domain.ports.registry import Lifetime

# 注册端口（支持三种 impl 形式：直接类、工厂 lambda、模块路径字符串）
register_port(
    name="redis_adapter",
    version="v1.0.0",
    interface=L1CachePort,
    impl=RedisAdapter,                          # 直接类
    lifetime=Lifetime.SINGLETON,
)

register_port(
    name="event_publisher",
    version="v1.0.0",
    interface=EventPublisher,
    impl="src.infrastructure.messaging.dual_channel_event_bus.DualChannelEventBus",  # 延迟加载
    lifetime=Lifetime.SINGLETON,
)

register_port(
    name="session_factory",
    impl=lambda: create_async_session(engine),  # 工厂 lambda
    lifetime=Lifetime.SCOPED,
)
```

**端口解析与自动注入:**
```python
from src.domain.ports.resolver import resolve

# 按名称解析
publisher = resolve("event_publisher")

# 按接口类型解析
publisher = resolve_by_interface(EventPublisher)

# 自动注入：Resolver 通过 inspect.signature 解析构造函数参数，
# 先按参数名匹配端口，再按类型注解匹配接口，最后使用默认值
```

**三种生命周期:**
| 生命周期 | 行为 | 典型场景 |
|---------|------|---------|
| `SINGLETON` | 全局唯一实例，缓存于 `_instances` | 连接管理器、事件总线 |
| `SCOPED` | 作用域内唯一，缓存于 `_scoped_context` | 数据库会话、UnitOfWork |
| `TRANSIENT` | 每次解析创建新实例 | 无状态服务、Handler |

**FastAPI 集成:**
```python
# 通过 Resolver 自动注入到 FastAPI 路由
@app.get("/plans/{plan_id}")
async def get_plan(plan_id: UUID):
    service = resolve("planning_service")  # 应用层服务
    return await service.get_plan(plan_id)
```

#### 18.8.2 配置管理规范

**使用 Pydantic Settings:**
```python
from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field
from typing import List, Optional

class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    app_name: str = "sisys"
    debug: bool = False
    environment: str = "development"

    # 数据库
    database_url: str
    database_pool_size: int = 10

    # LLM 配置
    llm_api_key: SecretStr
    llm_base_url: str = "https://api.openai.com/v1"
    local_llm_url: str = "http://localhost:11434"

    # 消息队列
    rabbitmq_url: str
    redis_url: str

    # 安全
    secret_key: SecretStr
    jwt_algorithm: str = "HS256"

    # UDMR 配置
    cloud_advantage_threshold: float = 0.15
    local_quality_threshold: float = 0.70
    allowed_models: List[str] = ["qwen", "claude", "gpt-4"]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

# 使用
settings = Settings()
```

#### 18.8.3 数据库迁移规范

**Alembic 迁移文件:**
```python
# versions/001_create_strategic_plans_table.py
"""create strategic_plans table

Revision ID: 001
Revises:
Create Date: 2026-02-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'strategic_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_type', sa.String(10), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='draft'),
        sa.Column('blm_stage', sa.String(50), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('creator_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("plan_type IN ('SP', 'BP')", name='chk_plans_plan_type'),
        sa.CheckConstraint("status IN ('draft', 'in_progress', 'approved', 'archived')", name='chk_plans_status')
    )

    op.create_index('idx_plans_created_at', 'strategic_plans', ['created_at'])
    op.create_index('idx_plans_status', 'strategic_plans', ['status'])

def downgrade():
    op.drop_index('idx_plans_status', table_name='strategic_plans')
    op.drop_index('idx_plans_created_at', table_name='strategic_plans')
    op.drop_table('strategic_plans')
```

**迁移命令:**
```bash
# 创建新迁移
alembic revision -m "create routing_decision_log table"

# 应用所有迁移
alembic upgrade head

# 应用到特定版本
alembic upgrade 002

# 回退一个版本
alembic downgrade -1

# 查看当前版本
alembic current
```

#### 18.8.4 异步编程规范

**异步函数命名:**
```python
# 格式：async_{verb}_{noun}

async def create_strategic_plan(data: Dict[str, Any]) -> StrategicPlan:
    """创建战略规划"""
    pass

async def get_agent_by_id(agent_id: str) -> Optional[Agent]:
    """根据 ID 获取 Agent"""
    pass

async def execute_routing_decision(task: Task) -> RoutingDecision:
    """执行路由决策"""
    pass
```

**异步最佳实践:**
```python
import asyncio
import aiofiles

# ✅ 正确使用 await
async def process_document(file_path: str) -> Dict[str, Any]:
    """处理文档"""
    # 异步文件读取
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()

    # 异步数据库操作
    document = await db.insert_document(content)

    # 异步外部 API 调用
    result = await llm_client.analyze(content)

    return result

# ❌ 避免阻塞操作
async def bad_example():
    import time
    time.sleep(1)  # ❌ 阻塞整个事件循环

    with open('file.txt', 'r') as f:  # ❌ 同步文件 IO
        content = f.read()

# ✅ 正确做法
async def good_example():
    await asyncio.sleep(1)  # ✅ 非阻塞等待

    async with aiofiles.open('file.txt', 'r') as f:  # ✅ 异步文件 IO
        content = await f.read()
```

#### 18.8.5 类型注解规范

**完整类型提示:**
```python
from typing import Dict, List, Optional, Union, Callable, TypeVar, Generic
from uuid import UUID
from datetime import datetime
from enum import Enum

# 简单类型
def create_plan(
    plan_type: PlanType,
    status: PlanStatus = PlanStatus.DRAFT,
    creator_id: Optional[str] = None
) -> StrategicPlan:
    """创建战略规划"""
    pass

# 复杂类型
T = TypeVar('T')

def process_documents(
    documents: List[Document],
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Union[Document, List[Citation]]]:
    """处理文档列表"""
    pass

# 泛型类
class Repository(Generic[T]):
    """泛型仓储"""

    async def get_by_id(self, id: UUID) -> Optional[T]:
        pass

    async def find_all(self, limit: int = 100) -> List[T]:
        pass

# 回调类型
async def retry_with_backoff(
    operation: Callable[[], Coroutine[None, None, T]],
    max_retries: int = 3,
    on_retry: Optional[Callable[[int], None]] = None
) -> T:
    """带重试执行操作"""
    pass
```

---

### 18.9 文档规范

#### 18.9.1 文档字符串规范

**Google 风格文档字符串:**
```python
def create_strategic_plan(
    plan_type: PlanType,
    status: PlanStatus = PlanStatus.DRAFT,
    creator_id: Optional[str] = None
) -> StrategicPlan:
    """
    创建新的战略规划。

    基于 BLM 六阶段模型创建战略规划，支持 SP(战略规划) 和 BP(业务计划) 两种类型。
    创建的规划初始状态为 DRAFT，需要经过批准流程才能生效。

    Args:
        plan_type: 规划类型，SP(战略规划) 或 BP(业务计划)
        status: 初始状态，默认为 DRAFT
        creator_id: 创建者 ID，通常是 Agent 角色标识

    Returns:
        创建的 StrategicPlan 实例

    Raises:
        ValidationError: 当 plan_type 无效或 status 不合法时
        AuthorizationError: 当创建者无权限创建规划时

    Example:
        >>> plan = create_strategic_plan(PlanType.SP, creator_id="agent_ceo")
        >>> plan.status
        <PlanStatus.DRAFT: 'draft'>
        >>> plan.blm_stage
        <BLMStage.GAP_ANALYSIS: 'gap_analysis'>

    Note:
        - 创建的规划会自动添加 BLM 六阶段的默认检查点
        - 创建者会被自动赋予规划的编辑权限
        - 规划 ID 使用 UUID v4 生成

    See Also:
        - update_strategic_plan: 更新现有规划
        - approve_strategic_plan: 批准规划
        - StrategicPlan: 战略规划实体类
    """
    ...
```

#### 18.9.2 代码注释规范

**好的注释 (解释为什么):**
```python
# 使用 CUSUM 检测是因为它可以识别小的持续性漂移
# 适合监控 LLM 输出质量的微妙变化，比简单的阈值检测更敏感
drift_detected = cusum_detector.detect(metrics)

# 本地路由质量阈值设为 0.70 是基于以下权衡：
# - 过低会导致本地模型处理复杂任务时质量不足
# - 过高会导致过多请求路由到云端，增加成本
# 0.70 是在成本和质量之间的平衡点
if local_score < 0.70:
    route_to_cloud()
```

**避免的注释 (重复代码):**
```python
# ❌ 避免这种注释
counter += 1  # 增加计数器

# ✅ 应该解释为什么
retry_count += 1  # 重试次数，用于指数退避计算
```

#### 18.9.3 Markdown 文档规范

**标题规范:**
```markdown
# Sentence case 标题
## 章节编号与架构文档一致
### 使用清晰的层级结构
```

**代码块:**
```markdown
\`\`\`python
# 必须指定语言
def example():
    pass
\`\`\`

\`\`\`sql
-- SQL 代码块
SELECT * FROM strategic_plans;
\`\`\`
```

**表格:**
```markdown
| 左对齐 | 居中对齐 | 右对齐 |
|:-------|:--------:|-------:|
| 内容   | 内容     | 内容   |
| 长内容 | 长内容   | 长内容 |
```

#### 18.9.4 CHANGELOG 规范

**遵循 Keep a Changelog 格式:**
```markdown
# 变更日志

## [1.2.0] - 2026-02-25

### Added
- UDMR 统一动态模型路由机制（三层决策架构）
- EIP 弹性视角隔离协议（四级隔离等级）
- 修正分级判定体系（五维加权算法）
- SYS AGENT 裁决状态机（五维评分标准）
- 辩论质量评估器（增益率 + 重复率检测）

### Changed
- LangGraph 版本从 0.0.40 升级到 1.0+
- 优化了 Checkpoint 恢复性能，Replay 模式速度提升 40%

### Fixed
- 修正检查点恢复时的状态同步问题
- 修正 RAG 混合检索中 Graph 检索的 payload 过滤 bug
- 修正 Agent 协作时 EIP 隔离等级切换的竞态条件

### Deprecated
- v1 API 端点（将于 2026-08-25 移除，请迁移到 v2）
- 旧的修正分级 L0 自动固化逻辑

### Removed
- 废弃的修正分级 L0 自动固化逻辑
- 已弃用的 Agent 角色配置方式

### Security
- 增加提示注入检测 (ShieldCortex)
- 加强多租户隔离，通过渗透测试验证
- 修复 JWT 令牌验证中的时序攻击漏洞
```

---

### 18.10 执行指南

**所有 AI Agent 必须遵守的规则:**

| 规则编号 | 规则描述 | 验收方式 |
|---------|---------|---------|
| RULE-001 | 所有公共 API 必须有类型注解 | mypy 检查通过 |
| RULE-002 | 所有公共 API 必须有文档字符串 | pylint 检查通过 |
| RULE-003 | 命名必须符合本章约定 | code review + linting |
| RULE-004 | API 响应必须符合 JSON:API 风格 | 自动化测试验证 |
| RULE-005 | 领域事件必须继承 DomainEvent 基类 | 类型检查 + code review |
| RULE-006 | 异常必须使用定义的层次结构 | code review |
| RULE-007 | 日志必须是结构化格式 (JSON) | 日志收集系统验证 |
| RULE-008 | 测试覆盖率必须达到最低要求 | CI/CD 门禁检查 |
| RULE-009 | 数据库迁移必须支持回滚 | Alembic 检查 |
| RULE-010 | 所有配置必须通过 Settings 类管理 | code review |

**违规处理:**
- CI/CD 自动检查失败：阻止合并
- Code Review 发现违规：必须修复后才能合并
- 生产环境发现违规：记录技术债务，安排修复

---
