# P3-1 任务：epics_v1.0.md Epic 2-8 Story 批量更新

**状态:** ⏳ 执行中
**负责人:** 全体
**预计工时:** 16 小时
**截止日期:** 2026-03-25

---

## 更新策略

Epic 2-8 包含 60+ 个 Story，采用批量更新策略：

1. 为每个 Epic 创建标准 TDD 测试要求模板
2. 根据 Story 类型调整测试重点
3. 统一覆盖率要求
4. 添加实施指南引用

---

## Epic 列表

### Epic 2: 文档与数据管理 (9 个 Story)

**Story 列表:**
- Story 2.1: 文档上传 17 种格式
- Story 2.2a: 文档解析基础格式
- Story 2.2b: 文档解析扩展格式
- Story 2.3: 版面信息保留
- Story 2.4: 表格语义提取
- Story 2.5: OCR 解析
- Story 2.6: 文档版本快照
- Story 2.7: 元数据验证
- Story 2.8: 语义分块

**TDD 测试要求模板（基础设施层）:**
```markdown
**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 文档上传测试 - 验证 17 种格式支持
   - [ ] 文档解析测试 - 验证解析准确性
   - [ ] 性能测试 - 验证处理延迟

2. **性能要求**
   - [ ] 上传延迟 P95<100ms
   - [ ] 解析延迟 P95<500ms
   - [ ] 并发处理≥20

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_document_[component].py` - 单元测试
   - [ ] `tests/integration/test_document_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求
```

### Epic 3: 智能检索与知识发现 (13 个 Story)

**Story 列表:**
- Story 3.1a: 稠密语义搜索
- Story 3.1b: BM25 稀疏搜索 RRF
- Story 3.2: 实体提取
- Story 3.3: 领域词典管理
- Story 3.4: RRF 融合排序
- Story 3.5: 分层搜索
- Story 3.6: 契约化结构化摘要
- Story 3.7: 相关性评估
- Story 3.8: 高保真可追溯性
- Story 3.9: 语义缓存
- Story 3.10: 战略档案存储
- Story 3.11: 事实有效性标签
- Story 3.12: 数据陈旧标记

**TDD 测试要求模板（架构层）:**
```markdown
**TDD 测试要求:**

1. **架构测试**
   - [ ] 搜索测试 - 验证搜索准确性
   - [ ] 缓存测试 - 验证缓存命中率
   - [ ] 排序测试 - 验证 RRF 融合

2. **性能要求**
   - [ ] 搜索延迟 P95<800ms
   - [ ] 缓存命中率≥40%
   - [ ] 相关性≥0.6

3. **覆盖率要求**
   - [ ] 架构层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_search_[component].py` - 单元测试
   - [ ] `tests/integration/test_search_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例
```

### Epic 4: 战略工具箱 (5 个 Story)

**Story 列表:**
- Story 4.1: 战略工具注册
- Story 4.2: 工具链编排
- Story 4.3: Schema 验证
- Story 4.4: Docker 沙箱执行
- Story 4.5: 红蓝辩论基础

**TDD 测试要求模板（架构层）:**
```markdown
**TDD 测试要求:**

1. **架构测试**
   - [ ] 工具注册测试 - 验证 23 种工具支持
   - [ ] 编排测试 - 验证 DAG 调度
   - [ ] 沙箱测试 - 验证隔离执行

2. **性能要求**
   - [ ] 工具执行延迟 P95<500ms
   - [ ] 沙箱启动时间<5 秒
   - [ ] 并发执行≥10

3. **覆盖率要求**
   - [ ] 架构层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过

5. **测试文件**
   - [ ] `tests/unit/architecture/test_tool_[component].py` - 单元测试
   - [ ] `tests/integration/test_tool_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例
```

### Epic 5: Agent 协作系统 (6 个 Story)

**Story 列表:**
- Story 5.1: CEO Agent 实例化
- Story 5.2: Agent 身份加载
- Story 5.3: 单 Agent 工作流
- Story 5.4: EIP 基础隔离
- Story 5.5: 三重硬隔离
- Story 5.6: 隔离切换日志

**TDD 测试要求模板（架构层）:**
```markdown
**TDD 测试要求:**

1. **架构测试**
   - [ ] Agent 实例化测试 - 验证 CEO Agent
   - [ ] 身份测试 - 验证 7 个配置文件加载
   - [ ] 隔离测试 - 验证 L4 硬隔离

2. **性能要求**
   - [ ] Agent 启动延迟 P95<200ms
   - [ ] 隔离切换延迟 P95<50ms
   - [ ] 并发 Agent≥10

3. **覆盖率要求**
   - [ ] 架构层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_agent_[component].py` - 单元测试
   - [ ] `tests/integration/test_agent_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例
```

### Epic 6: 战略规划流程 (BLM 前两阶段) (12 个 Story)

**Story 列表:**
- Story 6.1: BLM 前两阶段
- Story 6.2: 市场洞察六步骤
- Story 6.3: Checkpoint 快照创建
- Story 6.4: JSON 思维链输出
- Story 6.5a: Markdown 报告生成
- Story 6.5b: PDF 报告引用索引
- Story 6.6: Checkpoint 审查恢复
- Story 6.7: 可追溯树展示
- Story 6.8: 执行仪表板
- Story 6.9: 分析师视图
- Story 6.10: 顾问视图
- Story 6.11: 白标报告基础

**TDD 测试要求模板（架构层）:**
```markdown
**TDD 测试要求:**

1. **架构测试**
   - [ ] BLM 流程测试 - 验证前两阶段
   - [ ] Checkpoint 测试 - 验证快照创建
   - [ ] 报告测试 - 验证 Markdown/PDF 生成

2. **性能要求**
   - [ ] 报告生成延迟 P95<30 秒
   - [ ] Checkpoint 恢复延迟 P95<60 秒
   - [ ] 并发用户≥10

3. **覆盖率要求**
   - [ ] 架构层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_planning_[component].py` - 单元测试
   - [ ] `tests/integration/test_planning_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例
```

### Epic 7: 多触点用户界面与 API 集成 (8 个 Story)

**Story 列表:**
- Story 7.1: CLI 命令接口
- Story 7.2: REST API 接口
- Story 7.3: API Gateway
- Story 7.4: 健康仪表板
- Story 7.5: 无障碍设计
- Story 7.6: API 契约测试
- Story 7.7: API E2E 测试
- Story 7.8: 骨架屏加载

**TDD 测试要求模板（接口层）:**
```markdown
**TDD 测试要求:**

1. **接口测试**
   - [ ] CLI 测试 - 验证命令执行
   - [ ] API 测试 - 验证 REST 端点
   - [ ] Gateway 测试 - 验证统一入口

2. **性能要求**
   - [ ] API 延迟 P95<100ms
   - [ ] 并发请求≥100
   - [ ] 可用性≥99%

3. **覆盖率要求**
   - [ ] 接口层覆盖率≥70%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] API 契约测试通过

5. **测试文件**
   - [ ] `tests/unit/interfaces/test_[component].py` - 单元测试
   - [ ] `tests/integration/test_interfaces_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 接口测试要求
```

### Epic 8: 用户权限管理与审计合规 (6 个 Story)

**Story 列表:**
- Story 8.1: 审计日志多搜索
- Story 8.2: 修正分类基础
- Story 8.3: L0-L1 自动固化
- Story 8.4: 数据主权执法
- Story 8.5: ShieldCortex 提示注入
- Story 8.6: 渗透测试

**TDD 测试要求模板（安全层）:**
```markdown
**TDD 测试要求:**

1. **安全测试**
   - [ ] 审计测试 - 验证日志搜索
   - [ ] 修正测试 - 验证分类准确性
   - [ ] 渗透测试 - 验证入侵防范

2. **合规要求**
   - [ ] 审计日志完整性 100%
   - [ ] 修正分级准确率≥80%
   - [ ] 提示注入检测≥95%

3. **覆盖率要求**
   - [ ] 安全层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过

5. **测试文件**
   - [ ] `tests/unit/security/test_[component].py` - 单元测试
   - [ ] `tests/integration/test_security_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 安全测试要求
```

---

## 执行步骤

1. 读取 epics_v1.0.md 文件
2. 定位到 Epic 2 Story 2.1（第 XXXX 行）
3. 在 Acceptance Criteria 后添加 TDD 测试要求
4. 重复步骤 2-3 至 Epic 8 Story 8.6
5. 验证文档格式正确
6. 提交更新

---

## 验证清单

- [ ] Epic 2 Story 2.1-2.8 已添加 TDD 测试要求（9 个 Story）
- [ ] Epic 3 Story 3.1-3.12 已添加 TDD 测试要求（13 个 Story）
- [ ] Epic 4 Story 4.1-4.5 已添加 TDD 测试要求（5 个 Story）
- [ ] Epic 5 Story 5.1-5.6 已添加 TDD 测试要求（6 个 Story）
- [ ] Epic 6 Story 6.1-6.11 已添加 TDD 测试要求（12 个 Story）
- [ ] Epic 7 Story 7.1-7.8 已添加 TDD 测试要求（8 个 Story）
- [ ] Epic 8 Story 8.1-8.6 已添加 TDD 测试要求（6 个 Story）
- [ ] 文档格式正确（Markdown 语法、代码块、列表）
- [ ] 测试文件路径正确
- [ ] 覆盖率要求与 architecture.md 一致

---

**备注:** 由于 Story 数量较多（60+ 个），建议分批更新：
- 第 1 批：Epic 2-3（22 个 Story）
- 第 2 批：Epic 4-6（23 个 Story）
- 第 3 批：Epic 7-8（14 个 Story）
