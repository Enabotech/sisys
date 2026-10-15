# Story 91.1: API 认证守卫统一化（HTTPException 收敛至统一异常体系）

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环。
> 来源：5-1 代码审查周期留项 D8 收窄残余（deferred-work.md「D8·P3·范围收窄」剩余项）。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 9 个 API 路由文件中复制粘贴的认证守卫收敛为单一共享依赖并接入统一异常体系,
**So that** 接口层零手动 `raise HTTPException`（红线收口）、认证逻辑单点维护、401 响应经统一 ExceptionHandlers 出口。

### 业务价值

- **红线收口**：消除 src 层全部 26 处手动 `raise HTTPException`（CLAUDE.md §5「禁止手动 raise HTTPException」的最后残余面）
- **消除复制粘贴**：同一段 `get_current_user` 认证依赖在 9 文件 ×26 处重复——修一处漏洞需改 9 处的维护风险
- **可观测性统一**：401 异常进入统一异常体系（EXCEPTION 编码 + context），告警分拣与领域异常一致

### 立项调研事实（2026-10-15 实测，Story 编写依据）

1. **26 处 raise 全部是 HTTP_401_UNAUTHORIZED**，语义单一（认证守卫），非杂散异常——形态为各路由文件内联的 `get_current_user` 闭包依赖（`Depends(oauth2_scheme)` → 无 token/校验失败 → `raise HTTPException(401, detail=..., headers={"WWW-Authenticate": "Bearer"})`），同段代码 9 文件复制
2. **分布**：strategic_archive×6、document_upload×5、domain_dictionary×5、summary×5、tools×5、relevance_evaluation×4、auth×4、traceability×4、equilibrium_security×3（部分文件含 Not authenticated/Invalid token 两个变体）
3. **项目先例已完备（零新增异常域）**：`AuthenticationError(BusinessException)`（business_exceptions.py:45）已存在；`EXCEPTION_HTTP_MAP` 已注册 `AuthenticationError → 401`（exception_handlers.py:151）；handler 已实现 401 时自动附加 `WWW-Authenticate: Bearer` header（exception_handlers.py:390-392，OAuth2 规范要求）——即**改造仅是接线，异常体系与 handler 零改动**
4. 前置甄别：embedding demo 服务（infrastructure 域）的 HTTPException 不在断言面（非 interfaces 路由）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 共享认证依赖单点化

**Given** 9 个路由文件各自内联 `get_current_user` 认证依赖
**When** 抽取共享认证依赖模块
**Then** 认证逻辑（含 raise）仅存在一处，9 文件经 `Depends` 引用；26 处 raise 收敛为 1 处

**验证标准:**
- [ ] 共享依赖模块定义于 interfaces 层（如 `src/interfaces/api/auth_dependency.py`），提供 `get_current_user` 依赖与 `TokenPayload` 返回契约
- [ ] 9 路由文件删除内联定义，改为 import 共享依赖
- [ ] `grep -rn "raise HTTPException" src/interfaces/api/ | grep -v exception_handlers` 零命中

### AC-2: 统一异常体系接线

**Given** 共享认证依赖单点
**When** 认证失败（无 token / token 无效或过期）
**Then** raise `AuthenticationError`（领域异常，EXCEPTION 编码），由 ExceptionHandlers 统一映射 401 + `WWW-Authenticate: Bearer` header（既有 handler 行为，无改动）

**验证标准:**
- [ ] 单测：无 token → AuthenticationError；token 校验失败 → AuthenticationError（cause 链保留根因）
- [ ] 集成：401 响应含 `WWW-Authenticate: Bearer` header（OAuth2 规范，既有 handler 契约）
- [ ] **响应 body 契约裁定落地**（见 Task 0 设计裁定 D-1）：与改造前兼容或显式迁移（含测试断言同步）

### AC-3: 路由行为回归零变化

**Given** 9 个路由经共享依赖认证
**When** 既有路由测试与验收测试运行
**Then** 全部通过（认证通过路径行为不变；401 路径按 D-1 裁定形态）

**验证标准:**
- [ ] 既有 9 文件路由单测全绿（必要时按 D-1 裁定同步断言）
- [ ] API 契约测试（OpenAPI 401 响应定义）不回归
- [ ] `tests/unit/interfaces/api/test_exception_handlers.py` 等共享测试全绿

### AC-4: 红线终态

**验证标准:**
- [ ] 全 src `grep -rn "raise HTTPException"` 零命中（exception_handlers.py 自身的映射注册除外——其为统一出口非手动 raise）
- [ ] 红线三条 grep 自查零输出

---

## 🏗️ SDD+TDD 融合开发

### Task 0: SDD 规范定义（必选前置）

- [ ] **设计裁定 D-1（响应 body 契约）**：改造前 401 body 为 FastAPI 默认 `{"detail": "..."}`；改造后走 ExceptionHandlers 统一 body（`{"code": "EXCEPTION_xxx", "message": ...}` 形态）。裁定项：①对外契约兼容优先——handler 对 401 输出兼容 detail 形态（不推荐，污染统一出口）；②**契约显式迁移（倾向）**——统一 body 形态，既有测试断言同步更新，OpenAPI 401 schema 更新；③折中——401 保留 detail 字段并行 code。产出裁定记录进 Dev Notes
- [ ] 共享依赖模块契约（函数签名/返回 TokenPayload/依赖注入形态/异常契约）定稿
- [ ] 验收标准 Gherkin（AC-1~AC-4 场景化）

### 数据模型 / 端口契约

- 无新增端口/事件/异常（**全部复用既有**：AuthenticationError + EXCEPTION_HTTP_MAP 401 注册 + handler WWW-Authenticate 行为——立项调研第 3 条）
- 共享依赖属 interfaces 层模块组织（非端口），仿 FastAPI Depends 惯例

### 领域异常契约

| 异常 | 编码 | 状态 | 说明 |
|------|------|------|------|
| `AuthenticationError`（复用） | 既有 | 401 | 已注册 EXCEPTION_HTTP_MAP + WWW-Authenticate header——零新增 |

### TDD 循环（概要）

| 循环 | 红 | 绿 | 重构 |
|------|----|----|------|
| A 共享依赖 | 共享模块测试（无 token/坏 token → AuthenticationError；好 token → TokenPayload） | 实现 `auth_dependency.py` | 类型与 docstring |
| B 路由切换 | 逐文件切换后该文件路由测试全绿（401 断言按 D-1 裁定） | 9 文件 import 切换 | 删除内联定义 |
| C 契约回归 | API 契约测试 + OpenAPI 校验 | （应直接转绿） | — |

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | Task | 验证 |
|----|------|------|
| AC-1 | Task 0 契约 + Task 1 共享依赖 | grep 零命中 + 单点断言 |
| AC-2 | Task 1 + D-1 裁定 | 单测/集成 401 + header |
| AC-3 | Task 2 路由切换 | 9 文件测试 + 契约测试 |
| AC-4 | Task 3 收口 | 红线 grep |

## 📋 Tasks / Subtasks 任务分解

### Task 0: SDD 规范定义（D-1 裁定 + 契约定稿 + Gherkin）
- [ ] D-1 响应 body 契约裁定（三选一，倾向②，记录理由）
- [ ] 共享依赖契约与 Gherkin 验收场景
- [ ] 红测试先行（Gherkin 红阶段验证）

### Task 1: 共享认证依赖（TDD 循环 A）
- [ ] 🔴 `tests/unit/interfaces/api/test_auth_dependency.py`（认证三路径）
- [ ] 🟢 `src/interfaces/api/auth_dependency.py`（get_current_user + AuthenticationError）
- [ ] 🟡 变异实证（删认证 raise → 测试红）
- [ ] 🔄 ruff + mypy

### Task 2: 9 路由文件切换（TDD 循环 B，逐文件小步）
- [ ] 逐文件：内联定义删除 → import 共享依赖 → 该文件测试绿（9 文件清单见调研第 2 条）
- [ ] 401 断言按 D-1 裁定同步（如选②：detail → code/message）

### Task 3: 收口验证（TDD 循环 C）
- [ ] 全 src 红线 grep 零命中
- [ ] 全量 unit+contracts + 受影响验收回归
- [ ] 文档同步（deferred-work D8 核销）

---

## 📝 Dev Notes 开发笔记

### 关键架构决策

| # | 决策点 | 选定 | 备选（弃用理由） |
|---|--------|------|-----------------|
| DC-1 | 修法形态 | **抽取共享依赖 + 单点 raise AuthenticationError** | 逐处换异常类保留 9 份复制（弃用：不消除复制粘贴维护风险）；保留 HTTPException 仅豁免（弃用：红线收口目标） |
| DC-2 | 异常体系 | 复用 AuthenticationError（401 已注册 + header 已支持） | 新增异常（弃用：零增益） |

### 已知风险

1. **401 响应 body 契约变化**（D-1 裁定核心）——`{"detail": ...}` → 统一 body 形态；需排查既有测试断言（grep `detail` 于 9 文件测试）与外部消费方（当前无前端消费，风险可控）
2. `auth.py` 自身含 4 处 raise——其为认证端点（登录/token 签发），语义与资源路由的认证守卫不同（如凭据错误 401 属业务响应）——Task 2 逐处甄别，非一刀切

### 验收测试约束

- 按 R6 最新范本（`@scenario` 显式绑定 + context dict + AC 编号场景名）
- 无 Redis/PG 依赖场景不设服务门控背景（5-1 R3-D4 先例）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Execution Date** | 2026-10-15（立项） |

### 完成清单 Completion Notes List

- [x] 立项调研（26 处分布实测/语义单一确认/先例完备性核实）
- [x] Story 创建（create-story 立项版，待 dev-story 实施）

### 文件清单 File List

**创建的文件：** `_bmad-output/implementation-artifacts/stories/91-1-api-auth-unification.md`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 91.1 |
| **Story Key** | 91-1-api-auth-unification |
| **Epic** | Epic 91: 技术债清偿专项 |
| **优先级** | P3（红线收口价值 + 维护风险消除） |
| **来源** | 5-1 审查周期 D8 残余（deferred-work.md 登记） |
| **预估** | 1 天（含 D-1 裁定与 9 文件回归） |

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-15
