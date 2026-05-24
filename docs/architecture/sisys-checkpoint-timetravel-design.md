# SISYS Checkpoint 与 Time-Travel 机制详细设计

> **版本:** v8.3.3（从 architecture.md §8 提取）
> **状态:** 设计规范
> **提取日期:** 2026-05-23

---

## 1. Checkpoint 双模式恢复

| 模式 | 适用条件 | 一致性 | 执行延迟 | 成本 |
|------|---------|--------|---------|------|
| **Replay** | 影响≥2 个后续 Checkpoint | 强一致性 | 高 | 高 |
| **Override** | 影响<2 个后续 Checkpoint | 需人工确认 | 低 | 低 |

---

## 2. Checkpoint 实现细节

### 2.1 状态快照序列化格式

```python
class CheckpointSnapshot:
    """检查点状态快照 - 遵循系统公理二（外部化记忆）"""
    checkpoint_id: UUID
    stage_id: str              # BLM/BEM 阶段标识
    stage_number: int          # 阶段序号
    timestamp: datetime
    state_version: str         # 快照版本号

    # 核心状态数据
    state_data: Dict[str, Any]       # 业务状态变量
    context_window: List[Message]    # LLM 上下文窗口（已压缩，~2K tokens）
    working_memory: Dict[str, Any]   # 工作记忆（关键变量）
    tool_outputs: List[ToolResult]   # 工具执行结果

    # 元数据
    metadata: SnapshotMetadata
    checksum: str                    # SHA-256 校验和
    persistent_note_ref: Optional[UUID]  # 关联的持久化笔记引用（压缩前必须持久化）

    def serialize(self) -> bytes:
        """
        序列化为字节流（用于 Redis 存储）

        前置条件：
        1. 已执行持久化笔记步骤（persistent_note_ref 不为空）
        2. context_window 已压缩（压缩率≥70%）
        3. 质量评分≥0.7
        """
        # 验证持久化已完成（系统公理二：压缩前必须持久化）
        if not self.persistent_note_ref:
            raise SnapshotError("序列化前必须执行持久化笔记步骤")

        return msgpack.packb({
            'checkpoint_id': str(self.checkpoint_id),
            'stage_id': self.stage_id,
            'state_data': self.state_data,
            'context_window': [m.dict() for m in self.context_window],
            'working_memory': self.working_memory,
            'tool_outputs': [t.dict() for t in self.tool_outputs],
            'metadata': self.metadata.dict(),
            'checksum': self.checksum,
            'persistent_note_ref': str(self.persistent_note_ref)  # 持久化笔记引用
        }, use_bin_type=True)

    @classmethod
    def deserialize(cls, data: bytes) -> 'CheckpointSnapshot':
        """从字节流反序列化"""
        obj = msgpack.unpackb(data, raw=False)
        return cls(
            checkpoint_id=UUID(obj['checkpoint_id']),
            stage_id=obj['stage_id'],
            state_data=obj['state_data'],
            context_window=[Message(**m) for m in obj['context_window']],
            working_memory=obj['working_memory'],
            tool_outputs=[ToolResult(**t) for t in obj['tool_outputs']],
            metadata=SnapshotMetadata(**obj['metadata']),
            checksum=obj['checksum'],
            persistent_note_ref=UUID(obj['persistent_note_ref']) if obj.get('persistent_note_ref') else None
        )

    async def create_with_persistent_note(
        cls,
        checkpoint_id: UUID,
        stage_id: str,
        state_data: Dict[str, Any],
        raw_context: List[Message],  # 原始上下文（未压缩）
        working_memory: Dict[str, Any],
        tool_outputs: List[ToolResult],
        query: str,
        user_id: str,
        session_id: str
    ) -> 'CheckpointSnapshot':
        """
        工厂方法：创建 CheckpointSnapshot 并执行持久化笔记步骤

        流程：
        1. 持久化笔记（提取实体→生成摘要→记录血缘）
        2. 压缩上下文（基于持久化笔记）
        3. 验证压缩质量
        4. 创建快照

        遵循系统公理二：压缩前必须持久化
        """
        # 步骤 1：持久化笔记（压缩前必须执行）
        note_taker = PersistentNoteTaker()
        persistent_note = await note_taker.take_notes(
            query=query,
            retrieved_docs=raw_context,  # 将原始上下文视为检索结果
            user_id=user_id,
            session_id=session_id
        )

        # 步骤 2：压缩上下文（基于持久化笔记）
        compressor = ContextCompressor()
        compressed_context = await compressor.compress(
            retrieved_docs=raw_context,
            query=query,
            persistent_note=persistent_note
        )

        # 步骤 3：验证压缩质量
        if compressed_context.quality_score < 0.7:
            raise SnapshotError(f"压缩质量不足：{compressed_context.quality_score}")

        # 步骤 4：创建快照
        snapshot = cls(
            checkpoint_id=checkpoint_id,
            stage_id=stage_id,
            state_data=state_data,
            context_window=compressed_context.context,  # 使用压缩后的上下文
            working_memory=working_memory,
            tool_outputs=tool_outputs,
            metadata=SnapshotMetadata(
                compression_ratio=compressed_context.compression_ratio,
                quality_score=compressed_context.quality_score,
                token_count=compressed_context.token_count
            ),
            checksum="",  # 将在创建后计算
            persistent_note_ref=persistent_note.note_id  # 关联持久化笔记
        )

        # 计算校验和
        snapshot.checksum = snapshot._calculate_checksum()

        return snapshot

    def _calculate_checksum(self) -> str:
        """计算快照校验和（SHA-256）"""
        import hashlib
        data = f"{self.checkpoint_id}:{self.stage_id}:{self.state_version}:{self.persistent_note_ref}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """验证快照完整性（包括持久化笔记引用）"""
        if not self.persistent_note_ref:
            raise SnapshotIntegrityError("缺少持久化笔记引用")

        expected_checksum = self._calculate_checksum()
        if self.checksum != expected_checksum:
            raise SnapshotIntegrityError("校验和不匹配")

        return True
```

**持久化笔记与 Checkpoint 关联流程：**

```
┌─────────────────────────────────────────────────────────────────────────┐
│              Checkpoint 创建流程（压缩前持久化）                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. BLM/BEM 阶段完成                                                     │
│     │  输出：state_data, raw_context (LLM 原始上下文，~50K tokens)      │
│     ▼                                                                   │
│  2. 持久化笔记步骤 ← 压缩前必须执行！                                    │
│     │  2.1 提取关键实体（Top-20）→ StrategicArchive（L0-L5）            │
│     │  2.2 生成结构化摘要 → PostgreSQL（L2）                            │
│     │  2.3 记录血缘 → 审计日志 + WORM 归档（L2+L4）                      │
│     │  输出：PersistentNote (note_id, entities, summary, lineage)       │
│     ▼                                                                   │
│  3. 上下文压缩                                                           │
│     │  输入：raw_context + persistent_note                              │
│     │  算法：LLM 摘要生成（Temperature=0.3）+ 关键信息抽取              │
│     │  目标：50K tokens → ~2K tokens（压缩率≥70%）                       │
│     │  验证：质量评分≥0.7（信息熵 + 实体覆盖率）                         │
│     ▼                                                                   │
│  4. CheckpointSnapshot 创建                                              │
│     │  字段：                                                           │
│     │    - context_window: 压缩后的上下文（~2K tokens）                 │
│     │    - persistent_note_ref: 关联持久化笔记 ID（UUID）               │
│     │    - metadata.compression_ratio: 压缩率                           │
│     │    - metadata.quality_score: 质量评分                             │
│     │  序列化：msgpack → Redis Hash（TTL 30 天）                          │
│     ▼                                                                   │
│  5. 完整性验证                                                           │
│     │  检查：persistent_note_ref 不为空                                 │
│     │  检查：checksum 匹配                                              │
│     │  失败 → 抛出 SnapshotIntegrityError                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**验收标准：**

| 检查项 | 验收标准 | 验证方式 |
|--------|---------|---------|
| **持久化笔记引用** | 100% Checkpoint 有关联 persistent_note_ref | 数据库查询 |
| **压缩率** | ≥70% | metadata.compression_ratio |
| **质量评分** | ≥0.7 | metadata.quality_score |
| **完整性验证** | 100% 通过 verify_integrity() | 单元测试 |
| **压缩前持久化** | 0 次违规（无 persistent_note_ref 不允许序列化） | 审计日志 |

---

### 2.2 Replay 模式详细实现

```python
async def replay_mode(self, checkpoint: Checkpoint, modifications: List[Modification]) -> ReplayResult:
    """Replay 模式 - 强一致性保证"""
    # 1. 应用修改到检查点状态
    modified_state = await self.apply_modifications(checkpoint.state, modifications)

    # 2. 获取后续所有阶段
    current_stage = checkpoint.stage
    subsequent_stages = self.get_subsequent_stages(current_stage)

    # 3. 记录重放日志（用于审计）
    replay_log = ReplayLog(
        checkpoint_id=checkpoint.id,
        modifications=modifications,
        subsequent_stages=subsequent_stages,
        start_time=datetime.now()
    )

    # 4. 从修改点重新执行后续所有阶段
    execution_log = []
    for stage in subsequent_stages:
        try:
            # 4.1 加载阶段定义
            stage_def = await self.stage_repo.get(stage)

            # 4.2 执行阶段（调用 LangGraph/Prefect）
            result = await self.execute_stage(stage_def, modified_state)

            # 4.3 记录执行日志
            execution_log.append(StageExecutionLog(
                stage_id=stage,
                status='success',
                output=result.state,
                execution_time=result.execution_time
            ))

            # 4.4 更新状态
            modified_state = result.state

            # 4.5 更新 Checkpoint（持久化）
            await self.checkpoint_repo.update(stage, modified_state)

        except Exception as e:
            # 4.6 执行失败：记录错误并回滚
            await self.rollback(checkpoint.id)
            raise ReplayError(f"Stage {stage} replay failed: {str(e)}")

    # 5. 更新所有受影响的 Checkpoint
    for stage in subsequent_stages:
        await self.checkpoint_repo.update(stage, modified_state)

    # 6. 完成重放，记录审计日志
    replay_log.end_time = datetime.now()
    replay_log.status = 'completed'
    await self.replay_log_repo.save(replay_log)

    return ReplayResult(
        mode="Replay",
        modified_state=modified_state,
        execution_time=replay_log.end_time - replay_log.start_time,
        cost=self.calculate_cost(subsequent_stages),
        affected_checkpoints=subsequent_stages,
        replay_log_id=replay_log.id
    )
```

### 2.3 Override 模式详细实现

```python
async def override_mode(self, checkpoint: Checkpoint, modifications: List[Modification]) -> OverrideResult:
    """Override 模式 - 需人工确认"""
    # 1. 影响范围评估
    affected_checkpoints = await self.assess_impact(checkpoint.id)

    # 2. 生成影响评估报告
    impact_report = await self.generate_impact_report(
        checkpoint_id=checkpoint.id,
        modifications=modifications,
        affected_checkpoints=affected_checkpoints
    )

    # 3. 等待人工确认
    confirmation = await self.wait_for_human_confirmation(impact_report)
    if not confirmation:
        return OverrideResult(status='cancelled', reason='user_rejected')

    # 4. 应用修改（仅修改指定状态，不重新计算）
    modified_state = await self.apply_modifications(checkpoint.state, modifications)

    # 5. 标记后续 Checkpoint 为"待同步"状态
    for cp_id in affected_checkpoints:
        await self.checkpoint_repo.mark_pending_sync(cp_id)

    # 6. 记录审计日志
    override_log = OverrideLog(
        checkpoint_id=checkpoint.id,
        modifications=modifications,
        affected_checkpoints=affected_checkpoints,
        confirmed_by=confirmation.user_id,
        confirmed_at=datetime.now()
    )
    await self.override_log_repo.save(override_log)

    # 7. 触发同步机制（双触发策略）
    # 7.1 事件驱动触发：发布同步事件
    await self.event_bus.publish(CheckpointOverrideCompleted(
        checkpoint_id=checkpoint.id,
        affected_checkpoints=affected_checkpoints,
        timestamp=datetime.now()
    ))

    # 7.2 定时任务触发：注册后台同步任务（延迟 5 分钟执行）
    await self.scheduler.schedule(
        task=self.sync_pending_checkpoints,
        args=[affected_checkpoints],
        run_at=datetime.now() + timedelta(minutes=5)
    )

    return OverrideResult(
        mode="Override",
        modified_state=modified_state,
        affected_checkpoints=affected_checkpoints,
        pending_sync=True,
        override_log_id=override_log.id
    )

async def sync_pending_checkpoints(self, affected_checkpoints: List[UUID]) -> SyncResult:
    """
    同步待同步 Checkpoint（后台惰性同步）

    同步策略：
    1. 惰性同步：仅在用户访问时同步（减少不必要的计算）
    2. 后台批量同步：定时任务批量处理待同步 Checkpoint
    3. 用户访问触发：用户访问某个 Checkpoint 时触发同步
    """
    sync_results = []

    for cp_id in affected_checkpoints:
        # 1. 检查 Checkpoint 是否仍为"待同步"状态
        cp = await self.checkpoint_repo.get(cp_id)
        if cp.status != 'pending_sync':
            continue  # 已被其他操作同步

        # 2. 惰性同步策略：检查是否被用户访问
        if not await self.is_checkpoint_accessed(cp_id):
            # 未被访问：跳过，等待下次定时任务或用户访问触发
            sync_results.append(SyncResult(checkpoint_id=cp_id, status='skipped'))
            continue

        # 3. 用户已访问：执行同步（基于 Override 模式的差异应用）
        # 3.1 计算差异（修改点 vs 当前状态）
        diff = await self.calculate_diff(cp)

        # 3.2 应用差异到 Checkpoint 状态
        synced_state = await self.apply_diff(cp.state, diff)

        # 3.3 更新 Checkpoint 状态
        await self.checkpoint_repo.update(cp_id, synced_state, status='synced')

        # 3.4 记录同步日志
        sync_log = SyncLog(
            checkpoint_id=cp_id,
            sync_type='override_lazy',
            synced_at=datetime.now(),
            diff_applied=diff
        )
        await self.sync_log_repo.save(sync_log)

        sync_results.append(SyncResult(checkpoint_id=cp_id, status='synced'))

    return SyncResult(
        total=len(affected_checkpoints),
        synced=sum(1 for r in sync_results if r.status == 'synced'),
        skipped=sum(1 for r in sync_results if r.status == 'skipped'),
        results=sync_results
    )

async def on_checkpoint_access(self, checkpoint_id: UUID) -> None:
    """
    用户访问 Checkpoint 时的触发器

    如果 Checkpoint 为"待同步"状态，立即触发同步
    """
    cp = await self.checkpoint_repo.get(checkpoint_id)
    if cp.status == 'pending_sync':
        # 立即触发同步（用户访问触发）
        await self.sync_pending_checkpoints([checkpoint_id])
```

**同步机制说明：**

| 触发方式 | 触发条件 | 同步时机 | 适用场景 |
|---------|---------|---------|---------|
| **事件驱动触发** | Override 完成事件 | 立即发布同步事件 | 通知监听器准备同步 |
| **定时任务触发** | 后台调度器 | 延迟 5 分钟执行 | 批量处理待同步 Checkpoint |
| **用户访问触发** | 用户访问 Checkpoint | 访问时立即同步 | 惰性同步，减少不必要计算 |

**同步策略：**
- ✅ **惰性同步**：仅在用户访问时同步，减少后台计算开销
- ✅ **批量同步**：定时任务批量处理多个待同步 Checkpoint
- ✅ **优先级同步**：用户访问的 Checkpoint 优先同步
- ✅ **审计追踪**：所有同步操作记录至 `SyncLog` 并归档至 WORM 存储

---

## 3. Time-Travel 两阶段能力

**第一阶段：单点恢复**
- 从任意 Checkpoint 恢复执行
- 支持修改中间状态变量并从修改点继续
- 状态快照：Redis Hash 序列化，TTL 24 小时 -30 天

**第二阶段：分支对比**
1. 创建分支：从主线 Checkpoint 创建分支快照
2. 分支执行：在分支上执行恢复/修改
3. 并行维护：主线与分支状态并行维护
4. 差异对比视图：表格展示关键变量差异及影响评估
5. 合并/放弃：用户确认合并分支或放弃

---

## 4. 分支合并策略

### 4.1 合并策略矩阵

| 冲突类型 | 检测方式 | 解决策略 | 自动化程度 |
|---------|---------|---------|-----------|
| **无冲突** | 变量无重叠 | 自动合并 | ✅ 全自动 |
| **数据冲突** | 同一变量值不同 | 用户选择（主线/分支/手动编辑） | 🟡 半自动 |
| **逻辑冲突** | 因果关系矛盾 | 强制人工仲裁（SYS AGENT 裁决） | 🔴 全手动 |
| **结构冲突** | 阶段顺序变化 | 专家确认 + 影响评估 | 🔴 全手动 |

### 4.2 分支合并实现

```python
class BranchMerger:
    """分支合并器 - 三阶段合并策略"""

    async def merge(self, branch_id: UUID, user_decision: str) -> MergeResult:
        """合并分支到主线"""
        # 1. 加载分支和主线状态
        branch_state = await self.get_branch_state(branch_id)
        main_state = await self.get_main_state()

        # 2. 冲突检测
        conflicts = await self.detect_conflicts(branch_state, main_state)

        # 3. 根据冲突类型选择合并策略
        if len(conflicts) == 0:
            # 3.1 无冲突：自动合并
            return await self.auto_merge(branch_state, main_state)

        conflict_type = self.classify_conflict_type(conflicts)

        if conflict_type == "data_conflict":
            # 3.2 数据冲突：用户选择
            return await self.user_choice_merge(branch_state, main_state, conflicts)

        elif conflict_type == "logical_conflict":
            # 3.3 逻辑冲突：强制人工仲裁
            return await self.manual_arbitration_merge(branch_state, main_state, conflicts)

        elif conflict_type == "structural_conflict":
            # 3.4 结构冲突：专家确认
            return await self.expert_confirm_merge(branch_state, main_state, conflicts)

        else:
            raise MergeError(f"Unknown conflict type: {conflict_type}")

    async def detect_conflicts(self, branch_state: State, main_state: State) -> List[Conflict]:
        """检测冲突"""
        conflicts = []

        # 1. 变量级冲突检测
        branch_vars = set(branch_state.variables.keys())
        main_vars = set(main_state.variables.keys())

        common_vars = branch_vars & main_vars
        for var in common_vars:
            if branch_state.variables[var] != main_state.variables[var]:
                conflicts.append(Conflict(
                    type='data_conflict',
                    variable=var,
                    branch_value=branch_state.variables[var],
                    main_value=main_state.variables[var],
                    severity='medium'
                ))

        # 2. 因果关系冲突检测（使用规则引擎）
        causal_conflicts = await self.rule_engine.check_causal_conflicts(
            branch_state.causal_graph,
            main_state.causal_graph
        )
        conflicts.extend(causal_conflicts)

        # 3. 阶段顺序冲突检测
        if branch_state.stage_sequence != main_state.stage_sequence:
            conflicts.append(Conflict(
                type='structural_conflict',
                variable='stage_sequence',
                branch_value=branch_state.stage_sequence,
                main_value=main_state.stage_sequence,
                severity='high'
            ))

        return conflicts

    async def user_choice_merge(
        self,
        branch_state: State,
        main_state: State,
        conflicts: List[Conflict]
    ) -> MergeResult:
        """数据冲突：用户选择合并"""
        # 1. 生成冲突解决 UI
        conflict_ui = await self.generate_conflict_ui(conflicts)

        # 2. 等待用户决策
        user_choices = await self.wait_for_user_choices(conflict_ui)

        # 3. 应用用户选择
        merged_state = await self.apply_user_choices(
            branch_state, main_state, user_choices
        )

        # 4. 记录合并日志
        merge_log = MergeLog(
            branch_id=branch_state.branch_id,
            merge_type='user_choice',
            conflicts=conflicts,
            user_choices=user_choices,
            merged_at=datetime.now()
        )
        await self.merge_log_repo.save(merge_log)

        return MergeResult(
            status='success',
            merged_state=merged_state,
            merge_type='user_choice',
            conflicts_resolved=len(conflicts)
        )

    async def manual_arbitration_merge(
        self,
        branch_state: State,
        main_state: State,
        conflicts: List[Conflict]
    ) -> MergeResult:
        """逻辑冲突：强制人工仲裁（SYS AGENT 裁决）"""
        # 1. 提交至 SYS AGENT 裁决器
        dispute = Dispute(
            type='logical_conflict',
            branch_state=branch_state,
            main_state=main_state,
            conflicts=conflicts
        )

        # 2. 等待裁决结果
        arbitration_result = await self.sys_arbiter.arbitrate(dispute)

        # 3. 根据裁决结果合并
        if arbitration_result.confidence >= 0.6:
            merged_state = await self.apply_arbitration_decision(
                branch_state, main_state, arbitration_result
            )
            return MergeResult(
                status='success',
                merged_state=merged_state,
                merge_type='arbitration',
                arbitration_id=arbitration_result.id
            )
        else:
            # 置信度不足：升级至人工专家
            return MergeResult(
                status='escalated',
                reason='low_confidence_arbitration',
                escalation_target='human_expert'
            )
```

### 4.3 差异对比视图

```python
class DiffViewGenerator:
    """差异对比视图生成器"""

    async def generate(self, main_state: State, branch_state: State) -> DiffView:
        """生成差异对比视图"""
        diff_view = DiffView(
            main_checkpoint_id=main_state.checkpoint_id,
            branch_checkpoint_id=branch_state.checkpoint_id,
            generated_at=datetime.now()
        )

        # 1. 关键变量差异对比
        diff_view.variable_diffs = await self.compare_variables(
            main_state.variables, branch_state.variables
        )

        # 2. 因果图差异对比
        diff_view.causal_graph_diff = await self.compare_causal_graphs(
            main_state.causal_graph, branch_state.causal_graph
        )

        # 3. 影响评估
        diff_view.impact_assessment = await self.assess_impact(
            diff_view.variable_diffs, diff_view.causal_graph_diff
        )

        # 4. 建议操作
        diff_view.recommended_action = await self.recommend_action(diff_view)

        return diff_view

    async def compare_variables(
        self,
        main_vars: Dict[str, Any],
        branch_vars: Dict[str, Any]
    ) -> List[VariableDiff]:
        """变量差异对比"""
        diffs = []
        all_vars = set(main_vars.keys()) | set(branch_vars.keys())

        for var in all_vars:
            main_val = main_vars.get(var, '<不存在>')
            branch_val = branch_vars.get(var, '<不存在>')

            if main_val != branch_val:
                # 计算影响范围
                impact = await self.calculate_variable_impact(var, main_val, branch_val)

                diffs.append(VariableDiff(
                    variable_name=var,
                    main_value=main_val,
                    branch_value=branch_val,
                    change_type=self.classify_change_type(main_val, branch_val),
                    impact_score=impact.score,
                    affected_variables=impact.affected_vars
                ))

        return sorted(diffs, key=lambda x: x.impact_score, reverse=True)
```

### 4.4 合并状态机

```python
class MergeStateMachine:
    """合并状态机 - 管理分支合并全流程"""

    STATES = ['created', 'executing', 'pending_merge', 'merging', 'merged', 'abandoned']
    TRANSITIONS = [
        {'trigger': 'start_execution', 'source': 'created', 'dest': 'executing'},
        {'trigger': 'execution_complete', 'source': 'executing', 'dest': 'pending_merge'},
        {'trigger': 'start_merge', 'source': 'pending_merge', 'dest': 'merging'},
        {'trigger': 'merge_success', 'source': 'merging', 'dest': 'merged'},
        {'trigger': 'merge_failed', 'source': 'merging', 'dest': 'pending_merge'},
        {'trigger': 'abandon', 'source': ['created', 'executing', 'pending_merge'], 'dest': 'abandoned'}
    ]

    def __init__(self, branch_id: UUID):
        self.branch_id = branch_id
        self.state = 'created'
        self.machine = Machine(
            model=self,
            states=MergeStateMachine.STATES,
            transitions=MergeStateMachine.TRANSITIONS,
            initial='created'
        )
```

---

## 5. 路由决策日志 WORM 归档时机

| 事件 | 触发条件 | 归档时机 | 存储位置 |
|------|---------|---------|---------|
| **RoutingDecided** | 路由决策完成 | 决策后 24 小时内 | MinIO WORM（7 年） |
| **IsolationLevelSwitched** | 隀离等级切换 | 切换后 24 小时内 | MinIO WORM（7 年） |
| **CheckpointReached** | 检查点到达 | 阶段完成后 1 小时内 | MinIO WORM（7 年） |
