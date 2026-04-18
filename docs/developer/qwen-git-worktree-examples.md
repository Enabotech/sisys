# Qwen + Git Worktree 并行开发实战示例

**版本:** 1.0.0
**日期:** 2026-03-20
**前置文档:** [qwen-git-worktree-parallel-dev-guide.md](./qwen-git-worktree-parallel-dev-guide.md)

---

## 📖 场景概述

本实战示例演示如何在 **Epic 1** 开发过程中使用 Qwen Code Agent + Git Worktree 进行多 Story 并行开发。

### 背景

Epic 1 包含 19 个 Story，需要加速交付：
- Story 1.1: 六边形架构骨架
- Story 1.2: 领域事件定义
- Story 1.3: 事件总线实现
- Story 1.4-1.8: 五层存储实现
- ...

### 目标

使用 Qwen + Worktree 并行开发模式，同时推进 3 个 Story：
- **Worktree 1**: Story 1.1 - 领域层实体
- **Worktree 2**: Story 1.2 - 领域事件 Schema
- **Worktree 3**: Story 1.3 - 消息队列集成

---

## 🚀 第一天：环境设置与任务规划

### 上午 9:00 - 环境设置

```bash
# 1. 进入项目根目录
cd /mnt/g/ai/sisys

# 2. 使用一键设置脚本创建 3 个 worktrees
./scripts/dev/worktree-setup.sh 1.1 1.2 1.3

# 或使用 Makefile 命令
make worktree-story STORY_NUM=1.1
make worktree-story STORY_NUM=1.2
make worktree-story STORY_NUM=1.3

# 3. 查看所有 worktrees
git worktree list
# 输出：
# /mnt/g/ai/sisys                        [main]
# /home/agimtech/dev/sisys-worktrees/story-1.1  [story/1.1-hexagonal-architecture]
# /home/agimtech/dev/sisys-worktrees/story-1.2  [story/1.2-domain-events]
# /home/agimtech/dev/sisys-worktrees/story-1.3  [story/1.3-event-bus]
```

### 上午 9:30 - 任务规划（使用 Qwen）

```bash
# 在主工作区激活 Qwen，进行任务规划
cd /mnt/g/ai/sisys
@qwen-agent

请帮我规划今天的并行开发任务：

背景：
- 创建了 3 个 worktrees：story-1.1, story-1.2, story-1.3
- 需要同时推进 3 个 Story
- 使用 SDD+TDD 融合开发模式

请帮我：
1. 为每个 Story 推荐合适的 Qwen Agent 角色
2. 制定上午/下午的开发计划
3. 识别潜在的依赖关系和风险
```

**Qwen 回复示例：**

```
📋 今日并行开发计划

🎯 Worktree 分配：

1. story-1.1 (领域层实体)
   - 推荐 Agent: domain_agent_1
   - 任务：实现 StrategicPlan, PlanType, PlanStatus 实体
   - 预计时间：2 小时

2. story-1.2 (领域事件 Schema)
   - 推荐 Agent: domain_agent_2
   - 任务：定义 PlanCreated, PlanStatusChanged 事件
   - 预计时间：1.5 小时

3. story-1.3 (事件总线)
   - 推荐 Agent: infrastructure_agent_2
   - 任务：RabbitMQ + Outbox 模式实现
   - 预计时间：3 小时

⚠️ 依赖关系：
- story-1.2 依赖 story-1.1 的实体定义
- story-1.3 依赖 story-1.2 的事件 Schema

💡 建议：
- 上午：story-1.1 + story-1.2（领域层）
- 下午：story-1.3（基础设施）+ 协同评审
```

---

## 📝 上午：领域层开发

### 上午 10:00 - Worktree 1 (Story 1.1)

```bash
# 进入 worktree
cd ~/dev/sisys-worktrees/story-1.1

# 激活 Qwen Agent
@qwen-agent activate domain_agent_1

# 开始 SDD 规范定义
make sdd-define

# Qwen 辅助生成领域实体
请基于以下需求生成 StrategicPlan 领域实体：

业务场景：企业战略规划管理
实体名称：StrategicPlan
核心属性：
  - id: UUID
  - plan_type: PlanType (SP/BP)
  - status: PlanStatus (draft/in_progress/approved)
  - creator_id: str
  - created_at: datetime

要求：
- 使用六边形架构领域层规范
- 零外部依赖（FR-AR-01）
- 包含工厂方法 create()
- 实现状态转换规则

# Qwen 生成代码后，开始 TDD 红阶段
make tdd-red TARGET=domain/entities/strategic_plan

# 编写测试（Qwen 辅助）
# 在 tests/unit/domain/entities/test_strategic_plan.py 中添加测试
```

**测试代码示例（Qwen 辅助生成）：**

```python
"""TDD 测试：StrategicPlan 领域实体"""
import pytest
from uuid import uuid4
from src.domain.entities.strategic_plan import StrategicPlan, PlanType, PlanStatus

def test_create_plan_with_valid_data(self):
    """Given 有效的领域数据，When 创建战略规划，Then 成功创建"""
    # Arrange
    plan_id = uuid4()
    creator_id = "agent_ceo"

    # Act
    plan = StrategicPlan.create(
        id=plan_id,
        plan_type=PlanType.SP,
        creator_id=creator_id,
    )

    # Assert
    assert plan.id == plan_id
    assert plan.plan_type == PlanType.SP
    assert plan.status == PlanStatus.DRAFT
    assert plan.creator_id == creator_id

def test_change_status_valid_transition(self):
    """Given 草稿状态的规划，When 变更为进行中，Then 状态变更成功"""
    # Arrange
    plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
    assert plan.status == PlanStatus.DRAFT

    # Act
    plan.change_status(PlanStatus.IN_PROGRESS)

    # Assert
    assert plan.status == PlanStatus.IN_PROGRESS
```

### 上午 11:30 - Worktree 2 (Story 1.2)

```bash
# 切换到 story-1.2 worktree
cd ~/dev/sisys-worktrees/story-1.2

# 激活 Qwen Agent
@qwen-agent activate domain_agent_2

# SDD 规范定义：领域事件 Schema
请生成领域事件 Schema：

业务场景：战略规划状态变更时发布事件
事件类型：
  - PlanCreated (规划创建)
  - PlanStatusChanged (状态变更)

要求：
- 继承 DomainEvent 基类
- 使用 Pydantic V2
- 包含完整的类型注解
- event_type 自动设置

# 生成 Schema 后，编写验收测试
make tdd-red TARGET=domain/events

# 在 tests/acceptance/test_plan_events.feature 中定义验收标准
```

**领域事件 Schema（Qwen 辅助生成）：**

```python
"""领域事件 Schema - SDD 规范定义"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4

class DomainEvent(BaseModel):
    """领域事件基类"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict
    source: str
    aggregate_id: UUID
    aggregate_type: str
    version: int = 1

class PlanCreated(DomainEvent):
    """战略规划创建事件"""
    event_type: str = "plan.created"
    plan_type: str
    creator_id: str
    initial_status: str = "draft"

class PlanStatusChanged(DomainEvent):
    """战略规划状态变更事件"""
    event_type: str = "plan.status_changed"
    old_status: str
    new_status: str
    changed_by: str
    reason: Optional[str] = None
```

---

## 🍽️ 中午 12:00 - 休息

```bash
# 提交上午的工作
cd ~/dev/sisys-worktrees/story-1.1
git add .
git commit -m "feat(domain): 实现 StrategicPlan 实体 (SDD+TDD)"

cd ~/dev/sisys-worktrees/story-1.2
git add .
git commit -m "feat(events): 定义领域事件 Schema (SDD)"

# 查看提交状态
git worktree list
```

---

## 🔧 下午：基础设施开发 + 协同评审

### 下午 2:00 - Worktree 3 (Story 1.3)

```bash
# 进入 story-1.3 worktree
cd ~/dev/sisys-worktrees/story-1.3

# 激活基础设施专家 Agent
@qwen-agent activate infrastructure_agent_2

# 任务：实现事件总线（RabbitMQ + Outbox 模式）
请基于以下需求实现事件总线：

技术栈：
- RabbitMQ (消息队列)
- Outbox 模式 (可靠事件发布)
- aio-pika (异步 AMQP 客户端)

要求：
- 实现 EventPublisher 接口
- 实现 Outbox 存储（PostgreSQL）
- 实现事件发布/订阅模式
- 包含重试机制

# 开始 TDD 循环
make tdd-red TARGET=infrastructure/events

# 编写测试（Qwen 辅助）
```

### 下午 4:00 - 跨 Worktree 协同评审

```bash
# 使用 Qwen Party Mode 进行多 Agent 评审
cd ~/dev/sisys-worktrees/story-1.1

# 启动 3 个 Agent 进行跨分支评审
@qwen-agent party-mode --agents=3 \
  --roles=domain_agent_1,infrastructure_agent_2,review_agent \
  --context=../story-1.2,../story-1.3

# 请求评审报告
请帮我评审这 3 个 Story 的实现：

评审重点：
1. 架构一致性（六边形架构约束）
2. 领域模型一致性（跨 Story 对比）
3. 代码质量（ruff/mypy 检查）
4. 测试覆盖率（≥80%）
5. 事件 Schema 兼容性

请生成详细的评审报告。
```

**Qwen Party Mode 评审报告示例：**

```
📊 跨 Story 架构评审报告

✅ 架构一致性检查
- 领域层：零外部依赖 ✓
- 依赖方向：基础设施→应用→领域 ✓
- 六边形架构：符合规范 ✓

⚠️ 领域模型一致性
- Story 1.1 的 PlanType 枚举：SP, BP
- Story 1.2 的事件 Schema 使用了相同的枚举 ✓
- 建议：统一状态枚举命名（draft → DRAFT）

✅ 代码质量
- Ruff 检查：通过
- MyPy 类型检查：通过
- Black 格式化：通过

📈 测试覆盖率
- Story 1.1: 92% ✓
- Story 1.2: 88% ✓
- Story 1.3: 75% ⚠️ (建议提升至 80%)

🔧 改进建议
1. Story 1.3 增加集成测试覆盖
2. 统一枚举命名规范
3. 添加领域事件发布测试
```

### 下午 5:00 - 质量门禁与提交

```bash
# 依次在每个 worktree 中运行质量门禁
cd ~/dev/sisys-worktrees/story-1.1
make quality-gates

cd ~/dev/sisys-worktrees/story-1.2
make quality-gates

cd ~/dev/sisys-worktrees/story-1.3
make quality-gates

# 提交所有更改
cd ~/dev/sisys-worktrees/story-1.1
git add . && git commit -m "feat: 完成 Story 1.1 实现"

cd ~/dev/sisys-worktrees/story-1.2
git add . && git commit -m "feat: 完成 Story 1.2 实现"

cd ~/dev/sisys-worktrees/story-1.3
git add . && git commit -m "feat: 完成 Story 1.3 实现"

# 推送到远程
git push origin story/1.1-hexagonal-architecture
git push origin story/1.2-domain-events
git push origin story/1.3-event-bus
```

---

## 🎯 第二天：Bug 修复 + 新功能并行

### 场景：紧急 Bug 报告

假设在开发 Story 1.4-1.8 时，收到紧急 Bug 报告：

```
Bug #123: 领域事件发布失败
严重程度：高
描述：在高并发场景下，事件总线偶尔丢失事件
影响：战略规划状态变更未通知到订阅方
```

### 上午 9:00 - 创建 Bug 修复 Worktree

```bash
# 基于 main 分支创建紧急 Bug 修复 worktree
git worktree add -b bugfix/event-lost ~/dev/sisys-worktrees/bugfix-123 main

# 进入 worktree
cd ~/dev/sisys-worktrees/bugfix-123

# 激活测试专家 Agent
@qwen-agent activate test_agent_1

# 复现 Bug
请帮我编写 Bug 复现测试：

Bug 描述：高并发场景下事件丢失
并发数：100 个线程同时发布事件
预期：所有事件都应该被发布
实际：偶尔丢失事件

# Qwen 生成复现测试
```

**复现测试（Qwen 辅助生成）：**

```python
"""Bug #123 复现测试：高并发事件丢失"""
import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.infrastructure.events.event_bus import EventBus

async def test_concurrent_event_publishing():
    """Given 高并发场景，When 同时发布 100 个事件，Then 所有事件都应该被发布"""
    # Arrange
    event_bus = EventBus()
    published_events = []

    # 订阅事件
    event_bus.subscribe("plan.created", lambda e: published_events.append(e))

    # Act: 并发发布 100 个事件
    async def publish_event(i):
        await event_bus.publish("plan.created", {"id": i})

    # 使用线程池模拟高并发
    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = [executor.submit(asyncio.run, publish_event(i)) for i in range(100)]
        for future in tasks:
            future.result()

    # Assert
    assert len(published_events) == 100, f"Expected 100 events, got {len(published_events)}"
```

### 上午 10:00 - 修复 Bug

```bash
# 运行复现测试（确认失败）
pytest tests/regression/test_bug_123.py -v
# 输出：FAILED (Expected 100 events, got 95)

# 激活基础设施专家 Agent
@qwen-agent activate infrastructure_agent_2

# 分析原因并修复
Bug 复现成功（丢失 5 个事件）。请分析可能的原因并提供修复方案。

可能的原因：
1. 竞态条件
2. 连接池耗尽
3. 未正确处理异步上下文

请提供修复代码。
```

**修复代码（Qwen 辅助生成）：**

```python
"""Bug #123 修复：添加事件发布锁和重试机制"""
import asyncio
from typing import Callable, Any
from aio_pika import Message

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._lock = asyncio.Lock()  # 添加锁
        self._retry_count = 3  # 重试次数

    async def publish(self, event_type: str, payload: Any) -> None:
        """发布事件（带锁和重试）"""
        for attempt in range(self._retry_count):
            try:
                async with self._lock:  # 使用锁保护
                    if event_type in self._subscribers:
                        for callback in self._subscribers[event_type]:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(payload)
                            else:
                                callback(payload)
                return  # 成功发布，退出重试循环
            except Exception as e:
                if attempt == self._retry_count - 1:
                    raise  # 最后一次重试失败，抛出异常
                await asyncio.sleep(0.1 * (2 ** attempt))  # 指数退避

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
```

### 上午 11:00 - 验证修复

```bash
# 运行复现测试（确认通过）
pytest tests/regression/test_bug_123.py -v
# 输出：PASSED

# 运行质量门禁
make quality-gates

# 提交修复
git add .
git commit -m "fix(events): 修复高并发事件丢失问题 #123

- 添加异步锁保护
- 实现指数退避重试机制
- 增加并发测试覆盖

Closes #123"

# 推送到远程
git push origin bugfix/event-lost

# 创建 PR
# (在 GitHub/Gitee 上创建 Pull Request)
```

---

## 📊 一周并行开发总结

### 成果对比

| 指标 | 传统单线程 | Qwen + Worktree 并行 | 改进 |
|------|-----------|-------------------|------|
| Story 完成数 | 3 个/周 | 6-8 个/周 | +100-167% |
| Bug 修复响应 | 4 小时 | 1 小时 | -75% |
| 代码审查质量 | 中等 | 高（Party Mode） | +50% |
| 上下文切换开销 | 高（30 分钟/次） | 低（<1 分钟） | -95% |
| 测试覆盖率 | 75% | 85-90% | +10-15% |

### 经验总结

**✅ 有效实践：**
1. 每个 Story 使用独立 worktree，避免冲突
2. Qwen Agent 角色与 Story 类型匹配
3. 每天合并主分支，避免冲突累积
4. 使用 Party Mode 进行跨 Story 评审
5. Bug 修复使用独立 worktree，快速响应

**⚠️ 注意事项：**
1. 磁盘空间管理（每个 worktree 约 500MB）
2. 定期清理已完成的 worktrees
3. 避免同时修改相同文件（使用 Git 锁或协调）
4. Qwen 会话保持独立（避免上下文混淆）

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [qwen-git-worktree-parallel-dev-guide.md](./qwen-git-worktree-parallel-dev-guide.md) | 完整指南 |
| [qwen-git-worktree-quick-reference.md](./qwen-git-worktree-quick-reference.md) | 快速参考 |
| [qwen_agent.md](./qwen_agent.md) | Qwen Agent 使用 |
| [sdd-tdd-fusion-guide.md](./sdd-tdd-fusion-guide.md) | SDD+TDD 融合模式 |

---

**维护者:** sisys 开发团队
**最后更新:** 2026-03-20
**版本:** 1.0.0
