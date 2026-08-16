# Story 3.12: 数据陈旧标记

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 合规工程师,
**I want** 系统执行数据陈旧标记（超 12 个月自动降权）,
**So that** 提醒用户注意数据时效性。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的**战略档案库增强 Story**，也是 **FR-SA-03（P0）** 的完整实现。它在 Story 3.11 事实有效期标签管理的基础之上，消费 `FactBecameStale` 事件，对陈旧数据执行降权处理（排序分数降低）并在生成结果中提示"数据陈旧"。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **L3/L5 有效期同步** | 有效期变更时同步更新向量/图存储 payload | 同步准确率 100% |
| **陈旧数据降权** | 检索结果中陈旧数据排序分数降低 | 降权处理准确率 100% |
| **"数据陈旧"提示** | 生成结果中强制提示数据陈旧 | 提示准确率 100% |
| **FactBecameStale 消费** | 陈旧事件触发降权处理 | 事件处理完整 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.12

**前置依赖:**
- Story 3.10（战略档案库长期存储与归档 ✅ 已实现）— 提供 StrategicArchive 实体、ArchiveRepositoryPort、StrategicArchiveService 等基础组件
- Story 3.11（事实有效期标签管理 ✅ 已实现）— 提供 valid_from/valid_until、is_stale()、mark_stale_archives()、FactBecameStale 事件、metadata 陈旧标记

**后续依赖:**
- 无

---

## ✅ Acceptance Criteria 验收标准

### AC-1: L3/L5 有效期初始快照同步

**Given** 战略档案归档时
**When** 写入 L3 向量存储和 L5 图存储
**Then** payload/properties 中写入 valid_from/valid_until 初始快照（None）
**And** 为 Story 3.12 的增量同步提供兼容基础

**验证标准/Validation Criteria:**
- [ ] `archive_plan()` 的 L3 payload 追加 `valid_from: str | None` 和 `valid_until: str | None` 字段，初始值为 `None`（**直接赋值 `None`，不得经过 `str()` 转换**——`str(None)` 会得到 `"None"` 字符串而非 JSON `null`，与 `assumptions`/`decision_basis` 的 `str(...)` 序列化模式相区分）
- [ ] `archive_plan()` 的 L5 properties 同步追加 `valid_from: str | None` 和 `valid_until: str | None` 属性，初始值为 `None`（同样直接赋值，不经过 `str()` 转换）
- [ ] 读取兼容语义**统一约定为 `payload.get("valid_from")`**（返回 `None` 视为未设置）：新档案字段值为 JSON `null`、旧档案字段缺失，二者经 `get()` 均返回 `None`，行为一致。**禁止**使用 `"valid_from" not in payload` 判断（新旧档案语义不同）
- [ ] 向后兼容：L3/L5 已有 payload 无有效期字段时，检索逻辑不报错

### AC-2: ValidityPeriodSet 事件 L3/L5 同步

**Given** 档案有效期已设置（ValidityPeriodSet 事件已发布）
**When** 事件处理器接收到 ValidityPeriodSet 事件
**Then** 同步更新 L3 向量存储 payload 和 L5 图存储 properties 中的 valid_from/valid_until 字段
**And** 同步失败时记录日志，不影响主流程

**验证标准/Validation Criteria:**
- [ ] 完成 `archive_handlers.py` 中的 `TODO: Story 3.12 - sync valid_from/valid_until to L3/L5 payload`：`ValidityPeriodSet` 事件处理器中，**通过 `L3VectorPort.upsert_points()`** 更新 L3 向量点的 payload 字段（`valid_from`/`valid_until`），**通过 `L5GraphPort.execute_write_query()`** 更新 L5 图节点属性。⚠️ **注意：为避免对未知现有 payload 的全量覆盖，L3 更新应遵循"读-改-写"三步**：先 `get_point()` 读取现有 payload，追加 `valid_from`/`valid_until` 后整体 `upsert_points()`；L5 更新使用 `execute_write_query()` 的 Cypher `SET` 子句局部更新，天然不覆盖其他属性
- [ ] `ArchiveValidityHandler` 构造函数新增 `l3_vector: L3VectorPort | None` 和 `l5_graph: L5GraphPort | None` 依赖注入（均为可选，None 时降级记录日志）
- [ ] L3 更新：`get_point(collection="strategic_archive", point_id=f"strategic_archive:{archive_id}")` 读取现有 payload（点不存在时记录 WARNING 并跳过），合并 `valid_from`/`valid_until` 后调用 `upsert_points(collection="strategic_archive", points=[{"id": f"strategic_archive:{archive_id}", "vector": 原向量, "payload": 合并后 payload}])`（upsert 语义，同 id 覆盖 payload）
- [ ] L5 更新：调用 `l5_graph.execute_write_query(cypher="MATCH (n {memory_id: $memory_id}) SET n.valid_from = $valid_from, n.valid_until = $valid_until", params={"memory_id": str(archive_id), "valid_from": iso_str, "valid_until": iso_str})` 更新节点属性（`memory_id` 与 `create_entity()` 的主键参数一致）
- [ ] L3/L5 同步独立执行，一个失败不影响另一个（独立 try/except 块）
- [ ] L3/L5 均不可用时（None），降级为记录 WARNING 日志，不阻塞主流程
- [ ] 同步失败（如网络异常）记录 WARNING 日志，不抛出异常，不影响 ValidityPeriodSet 事件处理主流程
- [ ] **异步调用适配：** 事件处理器回调为同步函数（`EventListener.on_event` 同步回调签名），L3/L5 端口方法为 `async`。**本 Story 沿用 Story 3.11 既有同步分发模式**（`_wrap_handler` 同步回调）。新增 `_run_async(coro)` 辅助函数**适配三种事件循环场景**：
  - **无运行循环**（如测试函数直接调用 dispatch）：`asyncio.run(coro)` 创建并关闭新循环
  - **有运行循环**（如 `InMemoryEventBus.publish()` 在 async 上下文调用 dispatch）：`asyncio.get_running_loop().create_task(coro)` 调度到当前循环（fire-and-forget）
  - **实现关键**：用 `asyncio.get_running_loop()` 检测运行循环（py3.11+ 无循环时抛 RuntimeError），无循环用 `asyncio.run()`，有循环用 `create_task`。**禁止使用 `asyncio.get_event_loop().run_until_complete()`**（该 API 在已运行循环中会抛出 `RuntimeError: This event loop is already running`）
  - ⚠️ **fire-and-forget 语义**：在异步上下文中 `_run_async` 返回时协程可能尚未执行完毕。handler 内部不能依赖协程完成后的副作用（如 `InMemoryEventListener.dispatch()` 的 ExceptionGroup 收集）。`_mark_stale_on_l3()` 等异步方法的内部 try/except 已确保异常不会传播到调用方
  - **单元测试覆盖**：同步回调成功、L3/L5 异步异常时降级不抛出、有运行循环时 `create_task` 调度成功
- [ ] 单元测试覆盖：同步成功、L3 失败、L5 失败、L3/L5 均不可用四种场景

### AC-3: FactBecameStale 事件触发降权处理

**Given** 事实变为陈旧（FactBecameStale 事件已发布）
**When** 事件处理器接收到 FactBecameStale 事件
**Then** 触发降权处理：更新 L3 payload 标记陈旧状态，供检索时降权
**And** 降权处理失败时记录日志，不影响主流程

**验证标准/Validation Criteria:**
- [ ] 完成 `archive_handlers.py` 中的 `TODO: Story 3.12 - 触发降权处理、通知前端等`：`FactBecameStale` 事件处理器中，更新 L3 向量点 payload 添加 `is_stale: True` 和 `stale_reason`/`stale_since` 字段。⚠️ **更新目标为 `strategic_archive` collection**（该 collection 的 payload 包含 `archive_id` 字段，供降权服务兜底查询）
- [ ] L3 payload 更新字段：`{"is_stale": True, "stale_reason": event.stale_reason, "stale_since": event.stale_since.isoformat()}`。**命名规范：** L3 payload 使用 `is_stale: bool`（True/False），L2 metadata 使用 `staleness: str`（"stale"），两者通过 FactBecameStale 事件实现 L2→L3 最终一致性。L3 的 `is_stale` 是**检索优化用冗余副本**，L2 的 `staleness` 是**权威来源**
- [ ] L3 更新采用"读-改-写"三步：`get_point(collection="strategic_archive", point_id=f"strategic_archive:{archive_id}")` → 合并 `is_stale`/`stale_reason`/`stale_since` 到 payload → `upsert_points(collection="strategic_archive", points=[{"id": ..., "payload": 合并后payload}])`
- [ ] L3 不可用时（None）降级记录 WARNING 日志
- [ ] **`_mark_stale_on_l3()` 幂等实现细节：** 先 `get_point()` 读取现有 payload，检查 `payload.get("is_stale")` 是否已为 True：
  - 若 `is_stale` 已为 True 且 `stale_reason` 相同 → 跳过更新（幂等）
  - 若 `is_stale` 已为 True 但 `stale_reason` 不同 → 允许更新 `stale_reason`（最终一致性保证最新原因）
  - 若 `get_point()` 返回 None（L3 点不存在）→ 记录 WARNING 并跳过（与 `_sync_l3_validity()` 降级策略一致）
  - 若 `is_stale` 为 False 或不存在 → 执行读-改-写三步：合并 `is_stale=True`/`stale_reason`/`stale_since` 到 payload → `upsert_points()`
- [ ] **`mark_stale_archives()` 持久化 `stale_reason` 到 metadata**：当前 `mark_stale_archives()` 仅将 `stale_reason` 作为局部变量用于构造事件，**未持久化到 L2 metadata**。需在 `mark_stale_archives()` 中增加 `archive.metadata["stale_reason"] = stale_reason`，确保 `_to_archive_response()` 从 metadata 读取 `stale_reason` 时不为 None（参见 AC-6 字段映射要求）
- [ ] **`mark_stale_archives()` 并发安全**：`find()` 查询时使用 `find_for_update()` 替代 `find()`，避免与 `set_validity_period()` 的竞态（T1 读取旧数据判定陈旧，T2 设置新有效期后 T1 错误标记 stale）。`find_for_update()` 在 DB 层面加悲观锁
- [ ] 单元测试覆盖：降权标记成功、L3 不可用、网络异常、重复事件幂等、并发竞态五种场景

### AC-4: 检索结果排序中的陈旧数据降权

**Given** 检索结果中包含陈旧档案
**When** 执行战略档案**向量检索**（`StrategicArchiveService.search_vectors()`，新增方法）
**Then** 陈旧档案的排序分数降低（降权因子 0.5）
**And** 降权处理后保持排序稳定（分数相同时按 id 确定性排序）

**验证标准/Validation Criteria:**
- [ ] 新增 `StalenessWeightService`（`src/application/services/staleness_weight_service.py`）— 陈旧数据降权服务
  - 构造函数注入 `archive_repo: ArchiveRepositoryPort`（可选，None 时降级跳过兜底查询）
  - 核心方法：`async apply_staleness_weight(results: list[SearchResult]) -> list[SearchResult]` — 对检索结果列表执行陈旧性降权
  - 实现逻辑：对每个 `SearchResult`，检查其 `payload` 中是否包含 `is_stale=True` 标记：
    - 若 `payload` 中已有 `is_stale=True`（由 FactBecameStale 事件处理器写入 L3 `strategic_archive` collection），则 `score *= 0.5`
    - 若 `payload` 中无 `is_stale` 标记但 `archive_id` 字段存在，通过 `archive_repo.find()` **批量查询**（收集所有缺失标记的 archive_id，一次查询批量判断，避免 N+1 问题），对每个结果调用 `archive.is_stale()` 判断
    - 若 `archive_repo` 不可用（None）且 payload 中无 is_stale 标记，跳过该结果的降权
    - 若 `archive_repo.get_by_id()` 返回 None（档案已被删除），视为非陈旧，score 不变，记录 WARNING 日志
  - 降权后按 `(-score, id)` 降序重排序（`id` 为向量点 ID，格式 `"strategic_archive:{archive_id}"`，按字符串字典序）
  - 返回降权后的结果列表（长度不变，只调整 score 和顺序）
- [ ] **`StalenessWeightService` 的适用范围：** 该服务适用于 `strategic_archive` collection 的**向量检索结果**（`SearchResult` 含 `score`，payload 含 `archive_id` 字段，`FactBecameStale` 事件写入 `is_stale` 标记）。**不适用于 `query_archive()`（L2 实体查询，返回 `StrategicArchive` 实体列表，无 score 字段）**。**不侵入 `LayeredRetrievalService`（检索 `documents` collection，payload 中无 `archive_id` 和 `is_stale` 标记）**。如需在文档切片检索中应用降权，需在 `FactBecameStale` 事件处理器中同步更新 `documents` collection 的相关 payload（见 AC-3 扩展选项）
- [ ] **集成方式（Round 2 修订）：** 新增 `StrategicArchiveService.search_vectors()` 方法（服务层封装）：
  ```python
  # strategic_archive_service.py 文件头需新增 import：
  # from src.domain.ports.l3_vector import SearchResult
  # from src.domain.exceptions import ArchiveStorageError  # 已有导入
  async def search_vectors(
      self,
      query_vector: list[float],
      limit: int = 10,
      filter_payload: dict | None = None,
  ) -> list[SearchResult]:
      """战略档案向量检索

      通过 L3VectorPort.search() 检索 strategic_archive collection，
      返回 SearchResult 列表，返回前集成 StalenessWeightService 降权。

      Args:
          query_vector: 查询向量
          limit: 返回结果数量限制
          filter_payload: Payload 过滤条件

      Returns:
          降权后的 SearchResult 列表

      Raises:
          ArchiveStorageError: L3 向量存储未注入（None）时抛出
      """
      # Round 3 修订：L3 未注入时不可静默返回空列表（会导致调用方误判"无结果"），
      # 应抛出 ArchiveStorageError 明确告知 L3 存储不可用，参照 archive_plan() 的 L3 降级语义
      if self._vector_storage is None:
          raise ArchiveStorageError(layer="l3", cause=RuntimeError("l3_vector not injected"))
      raw = await self._vector_storage.search(
          collection=self.L3_COLLECTION,
          query_vector=query_vector,
          limit=limit,
          filter_payload=filter_payload,
      )
      results = [SearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {})) for r in raw]
      if self._staleness_service is not None:
          results = await self._staleness_service.apply_staleness_weight(results)
      return results
  ```
  - `StrategicArchiveService` 构造函数新增 `staleness_service: StalenessWeightService | None = None` 可选参数
  - `query_archive()` 保持纯 L2 实体查询，**不参与降权**（无 score 字段）
  - `staleness_service` 为 None 时跳过降权（透明降级）
- [ ] 降权因子使用常量 `STALE_WEIGHT_FACTOR = 0.5`（定义在 `staleness_weight_service.py` 模块级）
- [ ] 降权处理准确率：**测试覆盖所有已定义的陈旧/非陈旧场景（空、全陈旧、全新鲜、混合、重复陈旧），零误降权**（Round 2 修订：原"100%"改为可测量表述）
- [ ] 降权后分数相同时按 `(-score, id)` 确保排序确定性
- [ ] 降权延迟 P95<100ms（**非功能性需求，见性能约束章节**；通过批量查询 `archive_repo.find()` 减少 N+1 问题，不在验收测试中测量）

### AC-5: 摘要生成中的"数据陈旧"提示

**Given** 摘要生成时引用了陈旧数据
**When** `SummaryGenerationService.generate_summary()` 构建检索上下文
**Then** 在生成的摘要中强制提示"数据陈旧"
**And** 提示内容包含陈旧原因和标记时间

**验证标准/Validation Criteria:**
- [ ] `SearchResult.payload` 中 `is_stale` 标记为 `True` 的结果，在 `_build_search_context()` 中附加 `[数据陈旧: 原因=过期/归档超期, 标记时间=YYYY-MM-DD]` 前缀
- [ ] `SearchResult.payload` 中**无 `is_stale` 标记**时（事件处理时 L3 不可用等降级场景），`SummaryGenerationService` 通过可选注入的 `archive_repo` 兜底调用 `archive.is_stale()` 判断（`SummaryGenerationService` 构造函数新增可选参数 `archive_repo: ArchiveRepositoryPort | None = None`；未注入时降级为不提示，记录 WARNING，记录为已知限制）
- [ ] 摘要 prompt 模板（`summary_prompts.py`）新增用户体验说明：当检索结果中包含陈旧数据时，在摘要开头标注"⚠️ 部分引用数据已陈旧"
- [ ] 跨文档摘要模式（L1）同样支持陈旧提示：`_build_cross_document_context()` 遍历 `l2_results` 检查 `payload["is_stale"]`，前缀格式与正文模式一致（`[数据陈旧: ...]`）
- [ ] 提示准确率 100%：引用陈旧数据时必须提示，未引用陈旧数据时不得提示

### AC-6: API 响应中的陈旧标记暴露

**Given** 前端或 API 调用方需要感知数据陈旧状态
**When** 查询档案列表或详情
**Then** 响应中包含陈旧标记信息
**And** 支持按陈旧状态过滤

**验证标准/Validation Criteria:**
- [ ] `ArchiveResponse` 新增 `is_stale: bool = False` 字段
- [ ] `ArchiveResponse` 新增 `stale_reason: str | None = None` 字段（陈旧原因，"expired"/"archived_too_long"/None；**来源：`mark_stale_archives()` 持久化到 L2 metadata 的 `stale_reason` 字段**，参见 AC-3 持久化要求）
- [ ] `ArchiveResponse` 新增 `stale_since: str | None = None` 字段（标记为陈旧的时间，ISO 8601 格式字符串，如 `"2026-08-16T12:00:00Z"`）
- [ ] `_to_archive_response()` 映射：从 `metadata` 字典中读取 `staleness` 字段映射为 `is_stale`（`metadata.get("staleness") == "stale"` → `is_stale=True`），从 `metadata` 中读取 `stale_reason`、`stale_since` 字段。⚠️ **命名映射说明：** L2 metadata 使用 `staleness: str`（"stale"），L3 payload 使用 `is_stale: bool`（True/False），API 响应统一为 `is_stale: bool`。L2 metadata 的 `staleness` 是**权威来源**，L3 payload 的 `is_stale` 是**检索优化用冗余副本**（由 FactBecameStale 事件驱动 L2→L3 最终一致性，见"命名规范"章节）
- [ ] `GET /api/v1/archive/entries` 新增查询参数 `staleness_status: str | None = None`（"stale"/"fresh"），在 `ArchiveQuery` 中新增 `staleness_status: str | None = None` 字段。⚠️ **与 `validity_status` 语义区分：** `validity_status` 按 `valid_from`/`valid_until` 时间计算（VALID=未过期，EXPIRED=已过期，确定性时间判断）；`staleness_status` 按 `metadata["staleness"]` 标记判断（stale=已标记陈旧，fresh=未标记）。两者逻辑相关但不等价——`EXPIRED` 是时间维度，`stale` 是标记维度，**不得混用**
- [ ] `_apply_filters()` 扩展支持 `staleness_status` 过滤（使用 SQLAlchemy JSONB `.astext` 表达式，**注意 NULL 语义**：键缺失时 `.astext` 求值为 SQL `NULL`，`==` 返回 `NULL`（排除），`is_distinct_from` 返回 `True`（包含））：
  - `"stale"`：`ArchiveModel.metadata_["staleness"].astext == "stale"`（键缺失时 NULL → 排除，符合"仅返回已标记 stale"语义）
  - `"fresh"`：`ArchiveModel.metadata_["staleness"].astext.is_distinct_from("stale")`（键缺失时 NULL IS DISTINCT FROM 'stale' → True → 包含，符合"未标记 stale 的档案"语义）
  - **禁止**使用 `cast(..., String)` 或 `.as_string()`（非标准方法，且 `cast` 对 `.astext` 返回值冗余）
- [ ] `staleness_status` 非法值（非 "stale"/"fresh"/None）在 `__post_init__` 中抛 `EntityValidationError`（自动映射为 HTTP 400，**API 路由层无须额外校验**）
- [ ] 向后兼容：不传 `staleness_status` 参数时行为不变
- [ ] API 契约测试扩展（`test_api_contract_archive_validity.py`）：
  - `GET /entries?staleness_status=stale` 传递 `staleness_status="stale"` 到 `ArchiveQuery`
  - `GET /entries?staleness_status=fresh` 传递 `staleness_status="fresh"` 到 `ArchiveQuery`
  - `ArchiveResponse` 包含 `is_stale: bool`、`stale_reason: str | None`、`stale_since: str | None` 字段
  - `staleness_status` 非法值（如 "invalid"）返回 400

### AC-7: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 composition_root.py 注册
**Then** 新端口注册为 SCOPED
**And** 通过 Resolver 可正确解析

**验证标准/Validation Criteria:**
- [ ] `StalenessWeightService` 注册为 SCOPED 端口（`"staleness_weight_service"`）
- [ ] `ArchiveValidityHandler` 更新注册：注入 L3/L5 依赖
- [ ] 端口契约测试通过
- [ ] 所有新增组件在 `__init__.py` 导出

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**已有事件（无需新增，由 Story 3.11 提供）：**
- `ValidityPeriodSet` — 有效期设置事件，本 Story 消费该事件同步 L3/L5
- `FactBecameStale` — 事实变为陈旧事件，本 Story 消费该事件触发降权

**本 Story 不新增领域事件**，全部复用 Story 3.11 定义的事件。

#### 数据模型 (Data Models)

**已有实体（无需新增字段，由 Story 3.11 提供）：**
- `StrategicArchive` — 已包含 `valid_from`、`valid_until`、`metadata`（含 `staleness`/`stale_since` 标记）、`is_stale()` 方法

**本 Story 不新增实体字段**，但建议在 `StrategicArchive` 实体中新增 `mark_stale()` 方法（DDD 实体自包含行为原则，封装 metadata 陈旧标记写入）：
- [ ] 新增 `mark_stale(stale_since: datetime, stale_reason: str) -> None` 方法到 `StrategicArchive` 实体，封装 `self.metadata["staleness"] = "stale"`、`self.metadata["stale_since"] = stale_since.isoformat()`、`self.metadata["stale_reason"] = stale_reason` 三行写入逻辑
- [ ] 服务层 `mark_stale_archives()` 中调用 `archive.mark_stale(now, stale_reason)` 替代直接操作 metadata 字典
- [ ] 向后兼容：新增方法不影响现有字段和序列化

**`ArchiveQuery` 值对象扩展：**
- [ ] `ArchiveQuery` 新增 `staleness_status: str | None = None` 字段 — 按陈旧状态过滤（"stale"/"fresh"/None）
- [ ] `__post_init__` 验证 `staleness_status` 取值必须为 `"stale"`、`"fresh"` 或 `None`，非法值抛 `EntityValidationError`（自动映射为 HTTP 400，API 路由层无须额外校验）
- [ ] `ArchiveQuery` 新增 `archive_ids: list[UUID] | None = None` 可选字段 — 支持按 ID 列表批量查询（供 `StalenessWeightService` 兜底链使用，避免 N+1 问题）
- [ ] 向后兼容：新增字段为可选，默认 None，不影响现有查询

#### 统一端口定义注册与管理 (Port Contract)

**已有端口（无需新增端口，复用已有端口）：**
- `ArchiveRepositoryPort` — 档案仓储（已有 `find`、`find_for_update`、`get_by_id`、`save`）— **需扩展 `_apply_filters()` 支持 `staleness_status` 和 `archive_ids` 过滤**
- `L3VectorPort` — 向量存储（已有 `upsert_points`、`get_point`、`search`、`delete_points`）— **L3 payload 更新通过 `get_point` → 合并字段 → `upsert_points` 三步骤实现，不新增 `update_payload` 方法**
- `L5GraphPort` — 图存储（已有 `create_entity`、`execute_write_query`、`delete_entity`）— **L5 属性更新通过 `execute_write_query` 执行 Cypher SET 子句实现，不新增 `update_entity_properties` 方法**
- `LayeredRetrievalPort` — 分层检索（已有 `search_top_down`、`search_bottom_up`）
- `SummaryGenerationPort` — 摘要生成（已有 `generate_summary`）
- `EventListener` — 事件监听（已有 `on_event`）

**本 Story 不新增端口契约**，但需要在 `composition_root.py` 注册新服务 `StalenessWeightService`。

**端口契约清单执行约束（强制）：**
- [ ] 端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

**本 Story 不新增领域异常。** 现有 archive 子域异常（EXCEPTION_282-285）已覆盖所需场景：

| 异常类 | 编码 | 继承 | 描述 |
|--------|------|------|------|
| ArchiveNotFoundError | EXCEPTION_282 | NotFoundError | 档案不存在（已有） |
| ArchiveConflictError | EXCEPTION_283 | ConflictError | 档案冲突（已有，未使用） |
| ArchiveStorageError | EXCEPTION_284 | BusinessException | 存储失败（已有） |
| ValidityPeriodConflictError | EXCEPTION_285 | ConflictError | 有效期冲突（已有） |

**archive 子域可用编码：** 286, 287, 288, 289（本 Story 不占用，预留给未来 Story）

#### API 契约 (API Contract)

**已有 API（无需新增端点，由 Story 3.11 提供）：**
- `PATCH /api/v1/archive/entries/{archive_id}` — 更新有效期（已有）
- `POST /api/v1/archive/staleness-checks` — 手动触发陈旧标记（已有）
- `GET /api/v1/archive/entries` — 列出档案（已有）

**本 Story 扩展 API：**
- [ ] `GET /api/v1/archive/entries` 新增查询参数 `staleness_status: str | None = None`（"stale"/"fresh"）
- [ ] `ArchiveResponse` 新增 `is_stale: bool = False`、`stale_reason: str | None = None`、`stale_since: str | None = None` 字段
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_archive_validity.py`）

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
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止 |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

#### 验收标准 Gherkin (Acceptance Tests)

**BDD 场景文件（复用 Story 3.11 文件，扩展场景）：**
- `tests/acceptance/test_acceptance_archive_validity.feature` — 扩展陈旧标记场景
- `tests/acceptance/test_acceptance_archive_validity.py` — 扩展步骤实现

**必须覆盖的场景：**
- **AC-1 场景：** 归档时 L3/L5 写入有效期初始快照（valid_from/valid_until 为 None）
- **AC-2 场景：** 设置有效期后 L3/L5 payload 同步更新
- **AC-3 场景：** 陈旧标记触发降权处理（L3 payload 标记）+ 重复事件幂等消费
- **AC-4 场景：** 战略档案向量检索结果中陈旧数据降权（排序分数降低 50%，基于 `search_vectors()` 方法）
- **AC-5 场景：** 摘要生成中提示"数据陈旧"
- **AC-6 场景：** API 响应暴露陈旧状态 + 按陈旧状态过滤
- **Edge Cases：** L3 不可用时降级、L5 不可用时降级、archive_repo 不可用时降级、无陈旧数据时无降权、降权后排序稳定性、空结果集降权、混合陈旧/新鲜结果排序、并发事件 TOCTOU（见 AC-3 最终一致性保障）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- Edge Cases 必须包含异常路径

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | StalenessWeightService | 降权计算/重排序/降级 | `test_staleness_weight_service.py` | Task 1 |
| **TDD 单元测试** | ArchiveValidityHandler 扩展 | L3/L5 同步/降权触发 | `test_archive_handlers.py` | Task 2 |
| **TDD 单元测试** | StrategicArchiveService 扩展 | search_vectors() 降权集成/排序（Round 2 修订：原 LayeredRetrievalService 改为 StrategicArchiveService.search_vectors()） | `test_strategic_archive_service.py` | Task 3 |
| **TDD 单元测试** | SummaryGenerationService 扩展 | 陈旧提示 | `test_summary_generation_service.py` | Task 4 |
| **TDD 单元测试** | ArchiveQuery 扩展 | staleness_status 字段 | `test_archive_query.py` | Task 0 |
| **TDD 单元测试** | API 路由扩展 | 陈旧状态过滤/响应 | `test_archive_routes.py` | Task 5 |
| **TDD 单元测试** | ArchiveRepository 扩展 | staleness_status 过滤 | `test_archive_repository.py` | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_archive_validity.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_archive_validity.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单确认 | `test_acceptance_archive_validity.feature` | Task 6 |
| **TDD 契约测试** | 端口契约 | 端口注册/版本/兼容性/解析 | `test_port_contract_strategic_archive.py` | Task 0 |
| **TDD 契约测试** | API 契约 | 请求/响应结构/状态码 | `test_api_contract_archive_validity.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖 | `test_arch_archive_validity.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **领域层覆盖率 ≥90%**
- [ ] **应用层覆盖率 ≥85%**
- [ ] **接口层覆盖率 ≥85%**
- [ ] **基础设施层覆盖率 ≥75%**
- [ ] 集成测试覆盖率建议 ≥70%（不作为 CI 门禁，仅作为开发者自检参考）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | L3/L5 有效期初始快照同步 | Task 0 | SDD 规范定义 | `test_archive_handlers.py` |
| AC-1 | L3/L5 有效期初始快照同步 | Task 2 | archive_plan() L3/L5 payload 扩展 | `test_strategic_archive_service.py` |
| AC-2 | ValidityPeriodSet 事件 L3/L5 同步 | Task 0 | SDD 规范定义 | `test_archive_handlers.py` |
| AC-2 | ValidityPeriodSet 事件 L3/L5 同步 | Task 2 | 事件处理器 L3/L5 同步实现 | `test_archive_handlers.py` |
| AC-3 | FactBecameStale 事件触发降权 | Task 0 | SDD 规范定义 | `test_archive_handlers.py` |
| AC-3 | FactBecameStale 事件触发降权 | Task 2 | 事件处理器降权标记实现 | `test_archive_handlers.py` |
| AC-4 | 检索结果排序中的陈旧数据降权 | Task 0 | SDD 规范定义（StalenessWeightService） | `test_staleness_weight_service.py` |
| AC-4 | 检索结果排序中的陈旧数据降权 | Task 1 | StalenessWeightService 实现 | `test_staleness_weight_service.py` |
| AC-4 | 检索结果排序中的陈旧数据降权 | Task 3 | StrategicArchiveService.search_vectors() 集成（Round 2 修订：原 query_archive 改为 search_vectors） | `test_strategic_archive_service.py` |
| AC-5 | 摘要生成中的"数据陈旧"提示 | Task 0 | SDD 规范定义 | `test_summary_generation_service.py` |
| AC-5 | 摘要生成中的"数据陈旧"提示 | Task 4 | SummaryGenerationService 扩展 | `test_summary_generation_service.py` |
| AC-6 | API 响应中的陈旧标记暴露 | Task 0 | SDD 规范定义 | `test_archive_routes.py` |
| AC-6 | API 响应中的陈旧标记暴露 | Task 5 | API 路由扩展 + 仓储扩展 | `test_archive_routes.py` |
| AC-7 | 端口注册与 DI 集成 | Task 0 | SDD 规范定义 | `test_port_contract_strategic_archive.py` |
| AC-7 | 端口注册与 DI 集成 | Task 5 | composition_root 注册 | `test_port_contract_strategic_archive.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 扩展 `ArchiveQuery` 值对象 — 新增 `staleness_status: str | None = None` 字段
- [ ] Subtask 0.2: 定义 `StalenessWeightService` 服务契约 — 降权因子常量、方法签名、降级策略
- [ ] Subtask 0.3: 定义 `ArchiveValidityHandler` 扩展契约 — L3/L5 依赖注入 + 同步方法签名
- [ ] Subtask 0.4: 定义 API 扩展契约 — `ArchiveResponse` 新增字段 + `staleness_status` 查询参数
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_archive_validity.feature`（扩展陈旧标记场景）
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_archive_validity.py`（扩展步骤实现）
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）
- [ ] Subtask 0.8: 编写端口契约测试 `tests/contracts/test_port_contract_strategic_archive.py`（更新）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] 端口契约测试运行失败（预期行为，红阶段确认）

---

### Task 1: StalenessWeightService 降权服务实现

**关联 AC:** AC-4

> **说明：** StalenessWeightService 是降权处理的核心服务，独立于具体检索链路。Task 3 将其集成到战略档案向量检索（`StrategicArchiveService.search_vectors()`）。

#### TDD 循环 A: StalenessWeightService 核心逻辑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_staleness_weight_service.py`（降权计算/重排序/降级/N+1 避免） |
| 🟢 绿 | 实现 `StalenessWeightService` — `apply_staleness_weight()` 方法 |
| 🔄 重构 | 优化批量查询、添加类型注解、docstring |

- [ ] Subtask 1.1: 🔴 红 — 编写 StalenessWeightService 失败测试
  - 测试 payload 中 `is_stale=True` 的结果分数 `score *= 0.5`
  - 测试 payload 中无 `is_stale` 标记但 `archive_repo` 可用时，通过 `archive.is_stale()` 判断
  - 测试 `archive_repo` 不可用且 payload 中无 `is_stale` 标记时跳过降权
  - 测试降权后按 `(-score, id)` 降序重排序
  - 测试空结果列表返回空列表
  - 测试所有结果均非陈旧时分数不变、顺序不变
- [ ] Subtask 1.2: 🟢 绿 — 实现 `StalenessWeightService`
  ```python
  class StalenessWeightService:
      def __init__(self, archive_repo: ArchiveRepositoryPort | None = None) -> None
      async def apply_staleness_weight(self, results: list[SearchResult]) -> list[SearchResult]
  ```
- [ ] Subtask 1.3: 🔄 重构 — 优化代码、添加类型注解、docstring

**完成标准/Definition of Done:**
- [ ] `StalenessWeightService` 实现完成
- [ ] 降权核心逻辑验证通过（分数降低、重排序、降级）
- [ ] TDD 循环全部通过

---

### Task 2: 事件处理器 L3/L5 同步 + 降权触发

**关联 AC:** AC-1, AC-2, AC-3

> **说明：** 本 Task 完成 `archive_handlers.py` 中的两个 TODO：L3/L5 有效期同步（AC-1/AC-2）和 FactBecameStale 降权触发（AC-3）。
> 同时完成 `archive_plan()` 的 L3/L5 初始快照写入（AC-1）。

#### TDD 循环 A: archive_plan() L3/L5 初始快照写入

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/services/test_strategic_archive_service.py`（验证 L3 payload 和 L5 properties 包含 valid_from/valid_until 初始值 None） |
| 🟢 绿 | 扩展 `StrategicArchiveService.archive_plan()` — L3 payload 追加 `valid_from: None`、`valid_until: None`；L5 properties 同步追加 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 2.1: 🔴 红 — 编写 archive_plan() L3/L5 初始快照测试
- [ ] Subtask 2.2: 🟢 绿 — 扩展 archive_plan() L3/L5 payload
- [ ] Subtask 2.3: 🔄 重构 — 优化代码

#### TDD 循环 B: ArchiveValidityHandler L3/L5 同步

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/event_handlers/test_archive_handlers.py`（ValidityPeriodSet 触发 L3/L5 同步/FactBecameStale 触发降权标记） |
| 🟢 绿 | 扩展 `ArchiveValidityHandler` — 注入 L3/L5 依赖，实现同步方法 |
| 🔄 重构 | 注册到 composition_root.py |

- [ ] Subtask 2.4: 🔴 红 — 编写事件处理器扩展失败测试
  - ValidityPeriodSet 事件触发 L3 upsert_points（读-改-写三步）
  - ValidityPeriodSet 事件触发 L5 execute_write_query（Cypher SET）
  - L3 不可用时降级日志
  - L5 不可用时降级日志
  - L3 异常时记录 WARNING 不抛出
  - FactBecameStale 事件触发 L3 payload 标记 is_stale/stale_reason/stale_since（读-改-写三步）
  - FactBecameStale 事件 L3 不可用时降级日志
  - 异步同步方法在同步回调中通过 `_run_async` 辅助函数调用（`get_running_loop()` 检测 + `create_task`/`asyncio.run()` 双模式，见 AC-2 异步调用适配说明）
- [ ] Subtask 2.5: 🟢 绿 — 扩展 `ArchiveValidityHandler`
  - 构造函数新增 `l3_vector: L3VectorPort | None = None`、`l5_graph: L5GraphPort | None = None`
  - `_handle_validity_period_set()`：调用 `_sync_l3_validity()` 和 `_sync_l5_validity()`
  - `_handle_fact_became_stale()`：调用 `_mark_stale_on_l3()`
  - 新增 `_sync_l3_validity(event)`：更新 L3 payload 的 valid_from/valid_until
  - 新增 `_sync_l5_validity(event)`：更新 L5 properties 的 valid_from/valid_until
  - 新增 `_mark_stale_on_l3(event)`：更新 L3 payload 的 is_stale/stale_reason/stale_since
  - 所有同步方法均使用独立 try/except，失败记录 WARNING 日志
- [ ] Subtask 2.6: 🔄 重构 — 注册到 composition_root.py

**完成标准/Definition of Done:**
- [ ] `archive_plan()` L3/L5 初始快照写入完成
- [ ] `ArchiveValidityHandler` L3/L5 同步实现完成
- [ ] `ArchiveValidityHandler` 降权标记实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥85%

---

### Task 3: 战略档案向量检索降权集成

**关联 AC:** AC-4

> **说明：** StalenessWeightService 适用于 `strategic_archive` collection 的**向量检索结果**（`SearchResult` 含 `score`，payload 含 `archive_id`）。本 Task 新增 `StrategicArchiveService.search_vectors()` 方法，通过 `L3VectorPort.search()` 查询 `strategic_archive` collection，返回 `SearchResult` 列表，在返回前集成 `StalenessWeightService` 降权。**不侵入 `LayeredRetrievalService`**（其检索 `documents` collection，payload 无 `is_stale`/`archive_id` 标记，降权不适用）。⚠️ 修订说明（Round 1 文档审查）：原设计在 `LayeredRetrievalService` 四个内部方法返回前降权，已废弃。⚠️ 修订说明（Round 2 文档审查）：原 Round 1 设计在 `query_archive()` 返回前降权，但 `query_archive()` 返回 `StrategicArchive` 实体列表（无 score），与 `StalenessWeightService` 的 `SearchResult` 入参类型不匹配——已修正为 `search_vectors()` 方法集成降权。

#### TDD 循环 A: StrategicArchiveService.search_vectors() 实现 + 降权集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_strategic_archive_service.py`（新增 `TestSearchVectors` 测试类，包含降权集成/降级/类型正确性） |
| 🟢 绿 | 新增 `StrategicArchiveService.search_vectors()` 方法 + 注入 `StalenessWeightService`，在返回前调用降权 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 3.1: 🔴 红 — 编写 `search_vectors()` 降权集成失败测试
  - `search_vectors()` 返回 `list[SearchResult]`（类型正确，含 `id`/`score`/`payload` 字段）
  - `search_vectors()` 返回前调用 `apply_staleness_weight()`
  - `staleness_service` 为 None 时跳过降权（透明降级）
  - 降权后排序正确性验证（陈旧数据 score 降低 50%，排序位置变化）
  - 返回结果数量不变（只调整 score 和顺序）
  - 空结果集返回空列表（不报错）
  - 混合陈旧/新鲜结果：陈旧数据降权后位于新鲜数据之后
  - `query_archive()` 保持纯 L2 实体查询，**不参与降权**（无 score 字段）
- [ ] Subtask 3.2: 🟢 绿 — 实现 `StrategicArchiveService.search_vectors()` + 降权集成
  ```python
  async def search_vectors(
      self,
      query_vector: list[float],
      limit: int = 10,
      filter_payload: dict | None = None,
  ) -> list[SearchResult]:
      """战略档案向量检索

      通过 L3VectorPort.search() 检索 strategic_archive collection，
      返回 SearchResult 列表，返回前集成 StalenessWeightService 降权。

      Args:
          query_vector: 查询向量
          limit: 返回结果数量限制
          filter_payload: Payload 过滤条件

      Returns:
          降权后的 SearchResult 列表
      """
      raw = await self._vector_storage.search(
          collection=self.L3_COLLECTION,
          query_vector=query_vector,
          limit=limit,
          filter_payload=filter_payload,
      )
      results = [SearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {})) for r in raw]
      if self._staleness_service is not None:
          results = await self._staleness_service.apply_staleness_weight(results)
      return results
  ```
  - 构造函数新增 `staleness_service: StalenessWeightService | None = None`
- [ ] Subtask 3.3: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] `StrategicArchiveService.search_vectors()` 实现完成
- [ ] 降权集成正确（类型兼容、混合场景排序正确、空结果不报错）
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥85%

---

### Task 4: SummaryGenerationService 陈旧提示扩展

**关联 AC:** AC-5

> **说明：** 本 Task 扩展摘要生成服务，在检索结果包含陈旧数据时在摘要中提示"数据陈旧"。

#### TDD 循环 A: 检索上下文陈旧标记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/services/test_summary_generation_service.py`（陈旧提示注入） |
| 🟢 绿 | 扩展 `SummaryGenerationService._build_search_context()` — 注入陈旧标记 |
| 🔄 重构 | 优化 prompt 模板 |

- [ ] Subtask 4.1: 🔴 红 — 编写陈旧提示失败测试
  - 结果中包含 `is_stale=True` 的结果时，上下文文本附加 `[数据陈旧]` 前缀
  - 结果中不包含陈旧数据时，上下文文本无变化
  - 跨文档模式同样支持陈旧提示
  - 陈旧提示包含原因和标记时间
- [ ] Subtask 4.2: 🟢 绿 — 扩展 `_build_search_context()`
  - 遍历 `search_results` 时，检查 `payload.get("is_stale")` 是否为 True
  - 若为 True，在内容前附加 `[数据陈旧: 原因={stale_reason}, 标记时间={stale_since}]` 前缀
  - 跨文档模式 `_build_cross_document_context()` 同理
- [ ] Subtask 4.3: 🔄 重构 — 优化 prompt 模板

#### TDD 循环 B: SummaryPrompt 陈旧提示模板

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证 prompt 模板包含陈旧数据处理说明 |
| 🟢 绿 | 更新 `summary_prompts.py` — 在 system_prompt 中添加陈旧数据处理说明 |
| 🔄 重构 | 优化 prompt 措辞 |

- [ ] Subtask 4.4: 🔴 红 — 编写 prompt 模板测试
- [ ] Subtask 4.5: 🟢 绿 — 更新 `summary_prompts.py`
  - 在 system_prompt 末尾追加：`注意：检索结果中可能包含[数据陈旧]标记的数据，请在摘要开头标注"⚠️ 部分引用数据已陈旧"并引用陈旧原因。`
- [ ] Subtask 4.6: 🔄 重构 — 优化 prompt

**完成标准/Definition of Done:**
- [ ] `SummaryGenerationService` 陈旧提示实现完成
- [ ] `summary_prompts.py` 陈旧提示模板更新完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥85%

---

### Task 5: API 扩展 + 仓储扩展 + 端口注册 + 架构验证

**关联 AC:** AC-6, AC-7

> **说明：** 本 Task 完成 API 响应中的陈旧标记暴露、仓储 stale 状态过滤、DI 注册和架构验证。

#### TDD 循环 A: API 扩展（ArchiveResponse + 查询参数）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/api/test_archive_routes.py`（staleness_status 查询参数 + ArchiveResponse 字段） |
| 🟢 绿 | 扩展 `strategic_archive.py` 路由 — 新增 `staleness_status` 参数 + 响应字段映射 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 5.1: 🔴 红 — 编写 API 扩展失败测试
  - `GET /api/v1/archive/entries?staleness_status=stale` 返回正确过滤结果
  - `GET /api/v1/archive/entries?staleness_status=fresh` 返回正确过滤结果
  - `ArchiveResponse` 包含 `is_stale`、`stale_reason`、`stale_since` 字段
  - `_to_archive_response()` 从 metadata 中正确映射陈旧标记
  - 向后兼容：不传 `staleness_status` 参数时行为不变
- [ ] Subtask 5.2: 🟢 绿 — 扩展 API 路由
  - `ArchiveResponse` 新增 `is_stale: bool = False`、`stale_reason: str | None = None`、`stale_since: str | None = None`
  - `_to_archive_response()` 从 archive.metadata 读取 `staleness`、`stale_reason`、`stale_since`
  - `list_entries()` 新增 `staleness_status` 查询参数
  - `ArchiveQuery` 的 `staleness_status` 字段传入
- [ ] Subtask 5.3: 🔄 重构 — 优化代码

#### TDD 循环 B: 仓储 staleness_status 过滤扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/infrastructure/storage/test_archive_repository.py`（staleness_status 过滤） |
| 🟢 绿 | 扩展 `PostgreSQLArchiveRepository._apply_filters()` — 支持 staleness_status 过滤 |
| 🔄 重构 | 优化查询性能 |

- [ ] Subtask 5.4: 🔴 红 — 编写仓储 staleness_status 过滤测试
  - `staleness_status="stale"`：`metadata['staleness'] = 'stale'`（JSONB 键值判断）
  - `staleness_status="fresh"`：`metadata['staleness'] IS DISTINCT FROM 'stale'`（含键缺失场景）
  - `staleness_status=None`：无过滤
  - 与现有过滤条件组合兼容
- [ ] Subtask 5.5: 🟢 绿 — 扩展 `_apply_filters()`
  - 在 `_apply_filters()` 中新增 `staleness_status` 过滤逻辑
  - 使用 SQLAlchemy JSONB `.astext` 表达式（`ArchiveModel.metadata_["staleness"].astext == "stale"`），与现有 `_apply_filters()` 风格一致（全部使用列表达式，不引入 `text()` 原生 SQL）
  - **注意 NULL 语义**：键缺失时 `.astext` 求值为 SQL `NULL`，`==` 返回 `NULL`（排除），`is_distinct_from` 返回 `True`（包含），见 AC-6 详细说明
  - 示例：`ArchiveModel.metadata_["staleness"].astext == "stale"`（stale 过滤）和 `ArchiveModel.metadata_["staleness"].astext.is_distinct_from("stale")`（fresh 过滤）
  - **禁止**使用 `cast(..., String)` 或 `.as_string()`——这些不是标准 SQLAlchemy 方法，且对 `.astext` 返回值冗余
- [ ] Subtask 5.6: 🔄 重构 — 优化查询

#### TDD 循环 C: composition_root 注册 + 架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证 `StalenessWeightService` 可解析、`ArchiveValidityHandler` 更新后可解析 |
| 🟢 绿 | 在 `composition_root.py` 注册 `StalenessWeightService` + 更新 `ArchiveValidityHandler` 注册 |
| 🔄 重构 | 验证端口生命周期正确 |

- [ ] Subtask 5.7: 🔴 红 — 编写 DI 解析失败测试
- [ ] Subtask 5.8: 🟢 绿 — 注册新服务
  - `register_port(PortSpec(name="staleness_weight_service", ...))`
  - 更新 `archive_validity_handler` 注册，注入 L3/L5 依赖
- [ ] Subtask 5.9: 🔄 重构 — 验证端口生命周期

#### TDD 循环 D: 架构验证测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_arch_archive_validity.py`（扩展） |
| 🟢 绿 | 实现架构验证测试 |
| 🔄 重构 | 优化验证逻辑 |

- [ ] Subtask 5.10: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 5.11: 🟢 绿 — 实现架构验证
- [ ] Subtask 5.12: 🔄 重构 — 优化架构验证

**完成标准/Definition of Done:**
- [ ] API 扩展完成（staleness_status 查询参数 + ArchiveResponse 字段）
- [ ] 仓储 staleness_status 过滤完成
- [ ] 端口注册完成，Resolver 可正确解析
- [ ] 架构约束测试通过
- [ ] 覆盖率≥85%

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-7

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_archive_validity.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_archive_validity.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 6.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 6.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 6.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 6.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）、事件驱动、六层存储协同
- **设计约束:**
  - 领域层零外部依赖（仅 Python 标准库 + dataclasses + Protocol）
  - 依赖方向：interfaces → application → domain ← infrastructure
  - 所有端口通过 `composition_root.py` 统一注册
  - 新增异常必须注册到 `_code_ranges.py` 和 `EXCEPTION_HTTP_MAP`
- **接口治理:** 端口契约优先（Protocol + @runtime_checkable）、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+、FastAPI 0.111+、SQLAlchemy 2.0+、Alembic、PostgreSQL 15+、Qdrant、Neo4j

### 关键架构决策

**决策 1：降权策略 — 后处理降权 vs 检索时降权**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **方案 A：后处理降权（检索结果返回后 deweight）** | 不影响检索流程、易于测试、可插拔 | 额外一次遍历 | ✅ 8/10 |
| 方案 B：检索时 Filter + Score 修正 | 实时性更好 | 侵入性强、耦合检索实现 | 6/10 |

**决策理由：**
1. 后处理降权不侵入 Dense/Sparse/Graph 检索流程，保持各检索通道纯净
2. `StalenessWeightService` 可独立测试，可插拔集成到任何检索链路
3. 降权因子 0.5 是常量，未来可配置化

> ⚠️ **Round 1 修订：** 降权集成点从 `LayeredRetrievalService`（`documents` collection，payload 无 `archive_id`/`is_stale`）改为 `StrategicArchiveService`。**Round 2 修订：** 进一步修正——集成点从 `query_archive()`（返回 `StrategicArchive` 实体，无 score，与 `SearchResult` 入参类型不匹配）改为 `search_vectors()`（向量检索返回 `SearchResult`，有 score，类型兼容）。原因见 AC-4 适用范围说明与 "AC→Task 追溯矩阵"。

**决策 2：降权触发方式 — 事件驱动 vs 查询时实时判断**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **方案 A：事件驱动提前标记（FactBecameStale 更新 L3 payload）** | 查询时零额外开销、降权延迟低 | 需额外存储写入 | ✅ 8/10 |
| 方案 B：查询时实时查询 L2 判断 | 无需预写 L3 | 每次检索多一次 L2 查询，P95 增加 | 6/10 |

**决策理由：**
1. 事件驱动方式在检索时零额外开销，payload 中 `is_stale` 标记立即可用
2. 降低 P95 检索延迟（避免 N+1 查询 L2）
3. `archive_repo` 作为兜底降级方案（当 L3 payload 中无标记时，用 `find()` 批量查询替代逐条 `get_by_id()`，避免 N+1）

> ⚠️ **Round 1 修订：** 兜底查询由 `archive_repo.get_by_id()`（N+1）改为 `archive_repo.find()` 批量查询（一次查询返回多条），满足 P95<100ms 性能约束。

**决策 3：降权因子值**

| 因子值 | 影响 | 适用场景 |
|--------|------|---------|
| **0.5** | 陈旧数据分数减半 | 默认值，平衡陈旧与新鲜数据的权重 |
| 0.3 | 陈旧数据几乎排在末尾 | 对时效性要求极高的场景 |
| 0.0 | 完全排除陈旧数据 | 极严格合规场景 |

**决策理由：** 采用 0.5 作为默认值，与 UX 设计规范中的 `stale=0.75` 指数级降低不同（UX 设计规范中的新鲜度权重折扣 `fresh=1.0 / usable=0.9 / stale=0.75` 适用于前端展示的置信度评分，而本 Story 的降权因子作用于检索排序分数，两者维度不同）。0.5 确保陈旧数据排序显著降低但仍有机会被检索到（用户可感知陈旧数据的存在以触发替换）。

> ⚠️ **Round 1 补充（风险评估）：** 检索排序降权（0.5）与前端新鲜度权重（0.75）存在**叠加效应**——最终陈旧数据权重约为 0.5×0.75=0.375。本 Story v1.1.0 仍采用 0.5：检索降权作用于排序（相对位置），前端权重作用于置信度展示（绝对数值），二者维度正交。若后续 UX 反馈陈旧数据过度弱化，可将降权因子提升至 0.7-0.8 交给配置中心（P1 遗留项）。

**决策 4：降权幂等性 — "已降权标记"方案**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **方案 A：`SearchResult` 处理前先检查 `is_stale`，降权后在同一列表内只处理一次（单次遍历+单次重排，服务只暴露单入口调用）** | 无需修改 SearchResult 结构、简单 | 依赖调用方只调用一次 | ✅ 7/10 |
| 方案 B：payload 中写入 `already_weighted: True` 标记 | 显式幂等、可防御重入 | 修改 payload、污染 L3 持久化字段 | 6/10 |

**决策理由：**
1. 方案 A 通过**单一集成点**（`StrategicArchiveService.search_vectors()` 返回前唯一一次调用）保证降权只执行一次
2. `apply_staleness_weight()` 不修改 payload 持久化字段，避免污染 L3
3. 文档声明"幂等"修正为"单次调用"语义：**服务设计保证每个结果在同一调用周期内只降权一次；不承诺对同一结果跨调用重复降权免疫**

> ⚠️ **Round 1 修正：** 原文档第 884 行声称"多次调用 `apply_staleness_weight()` 对同一结果降权一次"（幂等），但实现逻辑每次都会 `score *= 0.5`，**不满足幂等**。本修订采用方案 A（单调用点保证），并如实声明"非幂等、单次调用保证"。

### 数据陈旧标记策略说明

本 Story 与 Story 3.11 的分工如下：

| 能力 | Story 3.11 范围 | Story 3.12 范围 |
|------|-----------------|-----------------|
| 有效期标签管理 | ✅ 设置 valid_from/valid_until | ✗ |
| 时间轴查询 | ✅ 按时间范围过滤查询 | ✗ |
| 陈旧标记检测 | ✅ 检测并标记 metadata 中的 staleness 标志 | ✗ |
| FactBecameStale 事件 | ✅ 发布事件通知下游 | ✗ |
| 陈旧数据降权 | ✗ | ✅ **排序分数降低** |
| 前端提示"数据陈旧" | ✗ | ✅ **生成结果中提示** |
| 降权处理 | ✗ | ✅ **权重应用** |

**降权触发链路：**
```
FactBecameStale 事件 ──→ ArchiveValidityHandler
    │
    ├── _mark_stale_on_l3() ──→ L3 payload 写入 is_stale=True（幂等：先检查是否已标记）
    │
    └── [向量检索时] ──→ StrategicArchiveService.search_vectors()
         │
         ├── L3VectorPort.search() ──→ 获取 SearchResult 列表
         ├── StalenessWeightService.apply_staleness_weight()
         │    ├── 检查 payload.is_stale → score *= 0.5
         │    └── 批量查询 L2 兜底 → 降权后重排序
         └── 返回降权结果
```

**L3/L5 同步链路：**
```
ValidityPeriodSet 事件 ──→ ArchiveValidityHandler
    │
    ├── _sync_l3_validity() ──→ L3 payload 更新 valid_from/valid_until
    │
    └── _sync_l5_validity() ──→ L5 properties 更新 valid_from/valid_until
```

### 降权处理逻辑

```
apply_staleness_weight(results: list[SearchResult]) -> list[SearchResult]:
    1. 对每个检索结果：
       a. 检查 payload 中是否有 is_stale=True 标记（由 FactBecameStale 事件处理器预写入 strategic_archive collection）
          - 若有：score *= STALE_WEIGHT_FACTOR (0.5)
          - 若无 is_stale 标记但 payload 中有 archive_id：
            - 若 archive_repo 可用：批量收集所有缺失标记的 archive_id，通过 archive_repo.find() 一次查询，在内存中映射 is_stale 状态
            - 若 archive_repo 不可用：跳过该结果
          - 若 archive_repo.get_by_id() 返回 None（档案已被删除）：视为非陈旧，score 不变，记录 WARNING
       b. 记录降权后的 score
    2. 按 (-score, id) 降序重排序
    3. 返回降权后的结果列表

STALE_WEIGHT_FACTOR = 0.5  # 模块级常量
```

### SearchResult payload 陈旧标记规范

**由 FactBecameStale 事件处理器写入 L3 `strategic_archive` collection（读-改-写三步）：**
```python
{
    "is_stale": True,           # bool — 检索优化用冗余副本，权威来源为 L2 metadata.staleness
    "stale_reason": "expired" | "archived_too_long",
    "stale_since": "2026-08-15T00:00:00Z",
    # ... 原有 payload 字段（含 archive_id, plan_id 等）...
}
```

**命名规范说明：**
| 存储层 | 字段名 | 类型 | 含义 | 角色 |
|--------|--------|------|------|------|
| L2 metadata (PostgreSQL) | `staleness` | `str` | `"stale"` 或缺失 | **权威来源** |
| L2 metadata (PostgreSQL) | `stale_since` | `str` | ISO 时间 | 标记时间 |
| L3 payload (Qdrant) | `is_stale` | `bool` | `True`/`False` | **检索优化副本** |
| L3 payload (Qdrant) | `stale_reason` | `str` | 陈旧原因 | 检索时读取 |
| L3 payload (Qdrant) | `stale_since` | `str` | ISO 时间 | 标记时间 |
| API 响应 | `is_stale` | `bool` | `True`/`False` | 对外暴露 |
| API 响应 | `stale_reason` | `str \| None` | 原因 | 对外暴露 |
| API 响应 | `stale_since` | `str \| None` | 时间 | 对外暴露 |

**最终一致性：** L2 的 `staleness` 是权威来源（`mark_stale_archives()` 写入），L3 的 `is_stale` 是检索优化副本（由 `FactBecameStale` 事件驱动同步）。两者通过事件驱动实现最终一致性。

**由 StalenessWeightService 读取：**
- `payload.get("is_stale", False)` — 是否陈旧
- `payload.get("stale_reason", "")` — 陈旧原因
- `payload.get("stale_since", "")` — 标记时间

### 项目结构说明 Project Structure

```
src/
├── application/
│   ├── services/
│   │   ├── strategic_archive_service.py    # UPDATE: archive_plan() L3/L5 payload 追加 valid_from/valid_until；新增 search_vectors() 集成 StalenessWeightService
│   │   ├── layered_retrieval_service.py     # no change（Round 1 修订：不再集成降权，降权不适用于 documents collection）
│   │   ├── summary_generation_service.py    # UPDATE: _build_search_context() 陈旧提示 + 可选注入 archive_repo 兜底
│   │   ├── summary_prompts.py              # UPDATE: system_prompt 追加陈旧数据处理说明
│   │   └── staleness_weight_service.py     # NEW: 陈旧数据降权服务
│   └── event_handlers/
│       ├── archive_handlers.py             # UPDATE: L3/L5 同步 + 降权触发（读-改-写三步 + _run_async 适配）
│       └── __init__.py                     # no change
│
├── domain/
│   ├── ports/
│   │   └── archive_repository.py           # UPDATE: ArchiveQuery 新增 staleness_status 字段
│   └── entities/
│       └── strategic_archive.py            # no change（已有 is_stale() 方法）
│
├── infrastructure/
│   └── storage/
│       └── postgresql/
│           └── repository/
│               └── archive_repository.py   # UPDATE: _apply_filters() 扩展 staleness_status 过滤（JSONB 表达式）
│
├── interfaces/
│   └── api/
│       └── strategic_archive.py            # UPDATE: ArchiveResponse 新增字段 + staleness_status 参数
│
└── composition_root.py                     # UPDATE: 注册 StalenessWeightService + 更新 ArchiveValidityHandler/StrategicArchiveService

tests/
├── unit/
│   ├── application/
│   │   ├── services/
│   │   │   ├── test_staleness_weight_service.py  # NEW: 降权服务测试
│   │   │   ├── test_summary_generation_service.py# UPDATE: 陈旧提示测试
│   │   │   └── test_strategic_archive_service.py # UPDATE: L3/L5 payload 初始快照 + query_archive 降权集成测试
│   │   └── event_handlers/
│   │       └── test_archive_handlers.py    # UPDATE: L3/L5 同步 + 降权触发测试
│   ├── domain/
│   │   └── ports/
│   │       └── test_archive_query.py       # UPDATE: staleness_status 字段测试（tests/unit/domain/ports/test_archive_query.py）
│   ├── interfaces/
│   │   └── api/
│   │       └── test_archive_routes.py      # UPDATE: 陈旧标记暴露测试
│   └── infrastructure/
│       └── storage/
│           └── test_archive_repository.py  # UPDATE: staleness_status 过滤测试
├── contracts/
│   ├── test_port_contract_strategic_archive.py  # UPDATE: 端口契约测试
│   └── test_api_contract_archive_validity.py    # UPDATE: API 契约测试
├── acceptance/
│   ├── test_acceptance_archive_validity.feature # UPDATE: 扩展陈旧标记场景
│   └── test_acceptance_archive_validity.py      # UPDATE: 扩展步骤实现
└── unit/architecture/
    └── test_arch_archive_validity.py      # UPDATE: 架构验证测试
```

### 优雅降级策略

| 场景 | 失败影响 | 降级策略 |
|------|---------|---------|
| L3 向量存储不可用 | 无法同步有效期/陈旧标记到 L3 payload | 记录 WARNING 日志，L3 同步跳过，不影响主流程；**陈旧标记不写入时由 StalenessWeightService 经 L2 兜底** |
| L5 图存储不可用 | 无法同步有效期到 L5 properties | 记录 WARNING 日志，L5 同步跳过，不影响主流程 |
| L3 + L5 均不可用 | 无法同步有效期 | 降级记录日志，有效期管理仅影响 L2 |
| archive_repo 不可用 | 降权服务无法查询 L2 判断陈旧 | 跳过需 L2 查询的降权，仅依赖 L3 payload 中的 is_stale 标记 |
| StalenessWeightService 未注入 | 战略档案检索结果不降权 | 透明降级，StrategicArchiveService 正常返回结果 |
| FactBecameStale 事件处理失败 | L3 payload 未标记陈旧 | **兜底：** L2 metadata 权威数据经 StalenessWeightService 批量查询兜底（find()）；**重试：** mark_stale_archives() 在 L3 写入成功前不将 metadata 标记为 stale，下次调度重试（见 AC-3 最终一致性保障） |
| archive 已被删除（L3 payload 仍残留） | 降权服务 get_by_id 返回 None | 视为非陈旧，score 不变，记录 WARNING 日志 |
| SummaryGenerationService 未注入 archive_repo | 陈旧提示无法兜底 | 无 `is_stale` 标记的结果不提示，记录 WARNING，已知限制 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Story 3.11（事实有效期标签管理）

**关键学习/Key Learnings:**
1. **L3/L5 同步延迟** — Story 3.11 的文档审查 Round 3 明确将 L3/L5 同步推迟到 Story 3.12，需要在 `archive_plan()` 中写入初始快照
2. **事件处理器注册机制** — 使用 `InMemoryEventListener.on_event()` + `register_handlers()` 模式，而非直接注册到 EventBus
3. **幂等设计** — 陈旧标记需幂等，避免重复标记重复发布事件
4. **可选依赖注入** — L3/L5 端口设为可选（`None` 时降级），与 `StrategicArchiveService` 的 L3/L5 降级模式一致
5. **异常体系** — archive 子域 (282-289) 已使用 282/283/284/285，本 Story 不新增异常

**应用到本故事/Applied to This Story:**
- [ ] `archive_plan()` 写入 L3/L5 初始快照（valid_from/valid_until=None，直接赋值不经过 str()）
- [ ] 事件处理器遵循 `on_event()` + `register_handlers()` 模式
- [ ] 降权处理**单次调用保证**（非幂等）：`StrategicArchiveService.search_vectors()` 唯一调用点，不对同一结果重复降权
- [ ] L3/L5 依赖为可选，降级记录日志
- [ ] 不新增异常编码，复用现有 archive 异常
- [ ] L3 payload 更新采用"读-改-写"三步（get_point → 合并字段 → upsert_points），避免全量覆盖未知字段

### 事件通道配置

**已有事件通道（由 Story 3.11 配置，`configs/event_channels.yaml`）：**
```yaml
ValidityPeriodSet:
  rabbitmq_routing_key: "sisys.events.reliable.validity_period_set"
  redis_channel: "sisys:rt:validity_period_set"
  delivery_mode: "reliable"
  description: "档案有效期设置完成"

FactBecameStale:
  rabbitmq_routing_key: "sisys.events.reliable.fact_became_stale"
  redis_channel: "sisys:rt:fact_became_stale"
  delivery_mode: "reliable"
  description: "事实变为陈旧"
```

**本 Story 不需要新增事件通道配置。**

### 异常编码分配

**已有 archive 子域异常（由 Story 3.10/3.11 定义）：**

| 异常类 | 编码 | 继承 | 描述 |
|--------|------|------|------|
| ArchiveNotFoundError | EXCEPTION_282 | NotFoundError | 档案不存在 |
| ArchiveConflictError | EXCEPTION_283 | ConflictError | 档案冲突（未使用） |
| ArchiveStorageError | EXCEPTION_284 | BusinessException | 存储层协同失败 |
| ValidityPeriodConflictError | EXCEPTION_285 | ConflictError | 有效期冲突 |

**本 Story 不新增异常。** archive 子域可用编码 286/287/288/289 预留给未来 Story。

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-08-16 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-11-fact-validity-period-management.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 3.12, 第 1734-1773 行）
- [x] 架构约束从 `architecture.md` 提取（六层存储 §11, 战略档案 §9, 检索 §17, 事件驱动 §10）
- [x] 前一个故事学习经验整合（Story 3.11 模式 + 审查修复经验）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-12-data-staleness-marking.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/services/staleness_weight_service.py` - 陈旧数据降权服务
- `tests/unit/application/services/test_staleness_weight_service.py` - 降权服务测试

**待更新的文件/To Be Updated:**
- `src/application/services/strategic_archive_service.py` - UPDATE: archive_plan() L3/L5 payload 追加 valid_from/valid_until; 新增 search_vectors() 集成 StalenessWeightService 降权
- `src/application/services/summary_generation_service.py` - UPDATE: _build_search_context() 陈旧提示 + 可选注入 archive_repo 兜底
- `src/application/services/summary_prompts.py` - UPDATE: system_prompt 追加陈旧数据处理说明
- `src/application/event_handlers/archive_handlers.py` - UPDATE: L3/L5 同步 + 降权触发
- `src/domain/ports/archive_repository.py` - UPDATE: ArchiveQuery 新增 staleness_status 字段
- `src/infrastructure/storage/postgresql/repository/archive_repository.py` - UPDATE: _apply_filters() 扩展 staleness_status 过滤
- `src/interfaces/api/strategic_archive.py` - UPDATE: ArchiveResponse 新增字段 + staleness_status 参数
- `src/composition_root.py` - UPDATE: 注册 StalenessWeightService + 更新 ArchiveValidityHandler/StrategicArchiveService
- `tests/unit/application/services/test_strategic_archive_service.py` - UPDATE: L3/L5 payload 初始快照 + query_archive 降权集成测试
- `tests/unit/application/services/test_summary_generation_service.py` - UPDATE: 陈旧提示测试
- `tests/unit/application/event_handlers/test_archive_handlers.py` - UPDATE: L3/L5 同步 + 降权触发测试
- `tests/unit/domain/ports/test_archive_query.py` - UPDATE: staleness_status 字段测试
- `tests/unit/interfaces/api/test_archive_routes.py` - UPDATE: 陈旧标记暴露测试
- `tests/unit/infrastructure/storage/test_archive_repository.py` - UPDATE: staleness_status 过滤测试
- `tests/contracts/test_port_contract_strategic_archive.py` - UPDATE: 端口契约测试
- `tests/contracts/test_api_contract_archive_validity.py` - UPDATE: API 契约测试
- `tests/acceptance/test_acceptance_archive_validity.feature` - UPDATE: 扩展陈旧标记场景
- `tests/acceptance/test_acceptance_archive_validity.py` - UPDATE: 扩展步骤实现
- `tests/unit/architecture/test_arch_archive_validity.py` - UPDATE: 架构验证测试

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.12 |
| **Story Key** | 3-12-data-staleness-marking |
| **File** | `_bmad-output/implementation-artifacts/stories/3-12-data-staleness-marking.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P1-12 |
| **覆盖 FR** | FR-SA-03（P0） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | 引用不存在的端口方法 `L3VectorPort.update_payload()` 和 `L5GraphPort.update_entity_properties()` | P0 | 修正为 `L3VectorPort.upsert_points()` 和 `L5GraphPort.execute_write_query()`，采用"读-改-写"三步（get_point → 合并 → upsert_points） |
| R1-2 | `StalenessWeightService` 在 `LayeredRetrievalService` 中因 collection 不匹配（documents vs strategic_archive）无法工作 | P0 | 降权集成点从 `LayeredRetrievalService` 改为 `StrategicArchiveService.query_archive()`，适用范围限定为 `strategic_archive` collection |
| R1-3 | `payload.get("archive_id")` 在 `documents` collection 检索结果中不存在，兜底链失效 | P0 | 同 R1-2，限定降权范围为 `strategic_archive` collection（payload 含 archive_id） |
| R1-4 | 降权位置矛盾：AC-4 说在公开方法返回前降权，Subtask 3.2 说在四个私有方法返回前降权，存在重复降权风险 | P0 | 统一为 `StrategicArchiveService.query_archive()` 单一入口降权，删除 LayeredRetrievalService 多路径降权方案 |
| R1-5 | `archive_repo` 为 None 且 payload 无 `is_stale` 标记时排序正确性问题 | P0 | 增加约束：跳过降权的结果 score 不变，参与全局 `(-score, id)` 重排序；"保持原始位置不变"修正为"score 不变，自然排序不刻意调整"；增加 `get_by_id()` 返回 None 视为非陈旧的处理 |
| R1-6 | `SummaryGenerationService` 无 `archive_repo` 兜底，L3 缺 `is_stale` 标记时无法提示 | P0 | `SummaryGenerationService` 构造函数新增可选参数 `archive_repo: ArchiveRepositoryPort \| None = None`，通过 `archive.is_stale()` 兜底判断 |
| R1-7 | `staleness_status` 与 `validity_status` 语义未区分 | P0 | 明确语义区分：`validity_status` 时间判断，`staleness_status` 标记判断，不得混用 |
| R1-8 | `_apply_filters()` 使用 `text()` 与现有列表达式风格不一致 | P0 | 改用 SQLAlchemy JSONB 列表达式 `ArchiveModel.metadata_["staleness"].as_string() == "stale"`，与现有风格一致 |
| R1-9 | 降权因子 0.5 与 UX 0.75 叠加效应（0.375）未评估 | P0 | 补充风险评估说明，当前结论：检索排序降权（相对位置）与前端置信度权重（绝对数值）维度正交，后续可配置化 |
| R1-10 | `mark_stale_archives()` 幂等跳过已标记档案，事件处理失败后永不重试 | P0 | 增加最终一致性保障：`mark_stale_archives()` 在 L3 写入成功前不将 metadata 标记为 stale；引入 `mark_l3_stale_on_archive()` 内联调用 |
| R1-11 | `apply_staleness_weight()` 声称"幂等"但实现不满足幂等 | P1 | 修正声明为"单次调用保证"（非幂等），通过 `StrategicArchiveService.query_archive()` 唯一调用点保证 |
| R1-12 | 兜底查询使用 `get_by_id()` 逐条导致 N+1，违反 P95<100ms | P1 | 改为批量收集缺失标记的 archive_id，通过 `archive_repo.find()` 一次查询批量判断 |
| R1-13 | `payload.get("valid_from")` 与 `"valid_from" not in payload` 语义未明确 | P1 | 统一约定使用 `payload.get("valid_from")`（返回 None 视为未设置），禁止使用 `in` 判断 |
| R1-14 | `archive_plan()` 中 `None` 值经过 `str()` 转换变成 `"None"` 字符串 | P1 | 明确 `valid_from`/`valid_until` 直接赋值（不经过 `str()` 转换），与 `assumptions`/`decision_basis` 的 `str()` 序列化模式相区分 |
| R1-15 | 异步回调调用异步端口方法的机制未明确 | P1 | 补充 `_run_async` 辅助函数方案：`get_running_loop()` 检测 + `create_task`/`asyncio.run()` 双模式 |
| R1-16 | L2 metadata `staleness` 与 L3 payload `is_stale` 两套命名体系关系未说明 | P1 | 补充命名规范表格，明确 L2 为权威来源、L3 为检索优化副本、最终一致性关系 |
| R1-17 | 降级策略表缺少"archive 已被删除"和"SummaryGenerationService 未注入"场景 | P2 | 补充两个降级场景的失败影响和降级策略 |
| R1-18 | `StalenessWeightService` SCOPED 生命周期决策理由未说明 | P2 | 补充说明：因依赖 `archive_repo`（SCOPED），故也为 SCOPED 避免持有过期引用 |
| R1-19 | 验收测试场景新增/修改未明确区分 | P2 | 在 AC-1~AC-7 中逐条标注新增/修改场景（本修订已隐式通过逐条 AC 详细说明） |
| R2-1 | `query_archive()` 返回 `list[StrategicArchive]`（实体无 score）与 `apply_staleness_weight()` 入参 `list[SearchResult]` 类型不匹配 | P0 | 降权集成点从 `query_archive()` 改为 `search_vectors()`（向量检索返回 `SearchResult`，有 score，类型兼容） |
| R2-2 | `_run_async` 方案根本性错误：`get_event_loop().run_until_complete()` 在运行循环中无法工作（`RuntimeError: This event loop is already running`） | P0 | `_run_async` 改为 `get_running_loop()` 检测 + `create_task`（有循环）/ `asyncio.run()`（无循环）双模式；禁止使用 `run_until_complete()` |
| R2-3 | `fact_stale_reason` 未持久化到 L2 metadata，API 响应中 `stale_reason` 永远为 None | P0 | `mark_stale_archives()` 增加 `archive.metadata["stale_reason"] = stale_reason` |
| R2-4 | `staleness_status="fresh"` 过滤的 `.astext != 'stale'` 在 JSONB 键缺失时因 NULL 语义错误排除行 | P0 | 改用 `.astext.is_distinct_from("stale")`（键缺失时 NULL IS DISTINCT FROM 'stale' → True → 包含） |
| R2-5 | `mark_stale_archives()` 使用 `find()` 未加悲观锁，与 `set_validity_period()` 存在竞态 | P0 | 改用 `find_for_update()` 替代 `find()`，在 DB 层面加悲观锁 |
| R2-6 | `InMemoryEventBus` 路径下内联写入与事件处理器双重触发 L3 写入 | P0 | `_mark_stale_on_l3()` 实现幂等（先检查 `is_stale` 是否已为 True，已标记则跳过） |
| R2-7 | `_mark_stale_on_l3()` 读-改-写三步 TOCTOU 竞态，并发事件丢失字段更新 | P1 | payload 合并时保留所有已有字段（`payload = dict(existing_payload); payload.update(new_fields)`） |
| R2-8 | Task 1 说明残留引用 LayeredRetrievalService | P1 | 改为"Task 3 将其集成到战略档案向量检索（search_vectors()）" |
| R2-9 | 测试分类表残留 `test_layered_retrieval_service.py` 引用 | P1 | 改为 `test_strategic_archive_service.py` |
| R2-10 | 验收测试 AC-4 场景建立在 query_archive 上（无 score 无法验证降权） | P1 | 改为基于 `search_vectors()` 的端到端向量检索降权验证 |
| R2-11 | "降权处理准确率 100%" 不可验证 | P1 | 改为可测量表述"测试覆盖所有已定义的陈旧/非陈旧场景，零误降权" |
| R2-12 | P95<100ms 性能指标不应出现在验收测试中 | P1 | 移至非功能性需求章节，标注"不在验收测试中测量" |
| R2-13 | `_wrap_handler` 的 `except Exception` 无法捕获 `asyncio.CancelledError` | P2 | 改为 `except BaseException`（与 `inmemory_event_listener.py` 第 31 行的 `# noqa: BLE001` 一致） |
| R2-14 | `StalenessWeightService` SCOPED 下 session 复用问题未说明 | P2 | 补充说明：`apply_staleness_weight()` 在 `search_vectors()` 返回前调用，此时 session 应仍活跃；如已关闭则降级为仅依赖 L3 标记 |
| R3-1 | `search_vectors()` 中 `_vector_storage` 为 None 时直接崩溃（`AttributeError`） | P0 | 在 `search()` 前增加 None 检查，抛出 `ArchiveStorageError(layer="l3")` 参照 `archive_plan()` 的 L3 降级模式 |
| R3-2 | `search_vectors()` 缺少 `SearchResult` 导入（编译/类型检查失败） | P0 | 在 `strategic_archive_service.py` 文件头新增 `from src.domain.ports.l3_vector import SearchResult` |
| R3-3 | AC-6 `astext` 与 Subtask 5.5 的 `cast/as_string` 文档内部矛盾（Subtask 5.5 未同步更新） | P0 | Subtask 5.5 改为 `.astext` 表达式，删除 `cast`/`.as_string()`，与 AC-6 保持一致 |
| R3-4 | `ArchiveQuery` 缺少按 archive_id 列表批量查询能力 | P1 | `ArchiveQuery` 新增 `archive_ids: list[UUID] | None = None` 字段，`_apply_filters()` 实现 `ArchiveModel.archive_id.in_(query.archive_ids)`；超过 1000 时分批查询 |
| R3-5 | `StrategicArchive` 实体缺少 `mark_stale()` 方法，违反 DDD 实体自包含行为原则 | P1 | 实体新增 `mark_stale(stale_since, stale_reason)` 方法封装 metadata 写入，服务层调用替代直接操作 |
| R3-6 | `mark_stale_archives()` 批处理部分失败恢复策略未说明 | P2 | 补充说明：失败不记录偏移量，下次调度从 offset=0 重新扫描幂等跳过；建议单条失败重试 N 次 |
| R3-7 | `_mark_stale_on_l3()` 幂等检查中 `stale_reason` 更新策略未明确 | P2 | 明确：`is_stale` 已为 True 且 `stale_reason` 相同→跳过；`stale_reason` 不同→允许更新（保证最新原因） |
| R3-8 | `_wrap_handler` 的 `except Exception` 无法捕获 `asyncio.CancelledError`（文档代码块未更新） | P2 | 文档示例改为 `except BaseException` |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-08-16
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] [3-12-决策-1] **降权因子值** — 0.5（默认）vs 0.3（严格）vs 0.0（完全排除）。已选择 0.5，理由见关键架构决策。

#### 已修复 Patch

- 暂无

#### 已推迟 Defer

- 暂无

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `validate-create-story` 进行质量检查
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**更新说明/Description:**
- v1.0.0: 创建故事文件
- v1.1.0: Round 1 文档审查修订 — 修复 10 个 P0 + 6 个 P1 + 3 个 P2 问题（见 Docs Review Fixes 表）；核心变更：降权集成点从 LayeredRetrievalService 改为 StrategicArchiveService、端口方法修正、L3 更新采用"读-改-写"三步、最终一致性保障增强、N+1 批量查询优化、异步回调适配方案补充
- v1.2.0: Round 2 文档审查修订 — 修复 6 个 P0 + 5 个 P1 + 3 个 P2 问题（见 Docs Review Fixes 表 R2-* 条目）；核心变更：降权集成点从 query_archive() 改为 search_vectors()（类型兼容修复）、`_run_async` 方案修正（get_running_loop + create_task 双模式）、stale_reason 持久化、fresh 过滤 NULL 语义修复、find_for_update 悲观锁并发安全、_mark_stale_on_l3 幂等增强
- v1.3.0: Round 3 文档审查修订 — 修复 4 个 P0 + 2 个 P1 + 3 个 P2 问题（见 Docs Review Fixes 表 R3-* 条目）；核心变更：search_vectors() 增加 L3 None 检查和 SearchResult 导入、Subtask 5.5 的 cast/as_string 修正为 .astext、ArchiveQuery 新增 archive_ids 批量查询字段、StrategicArchive 实体新增 mark_stale() 方法（DDD 封装）、_wrap_handler 改为 except BaseException 以捕获 CancelledError

<!-- 仅用作跟踪故事文件模板修订记录，故事开发时[务必删除]此段 -->
