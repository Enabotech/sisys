# Story 0.18: 用户友好配置向导

Status: ready-for-dev

<!--
故事创建日期：2026-04-11
创建者：Qwen Code (AI 高级开发者 - BMad Method Story Context Engine)
故事来源：sprint-status.yaml (backlog 故事)
前置依赖：Story 0.14/0.15/0.16 (各平台安装包 - 仅负责文件放置，不负责服务部署)

变更日志:
- 2026-04-11: 初始故事创建 - 综合上下文分析完成
  - 从 epics_v1.0.md 提取故事需求
  - 从 PRD/架构/UX 文档提取技术约束
  - 从 Story 0.15 (Mac 安装包) 学习实现模式
- 2026-04-12: 多代理审查修复 (Architect/UX/PM/QA)
  - 修复 P-1: 明确安装包与配置向导职责边界
  - 修复 P-2: 补充 Web UI 启动模型定义
  - 修复 P-3: 明确密码生命周期（哈希存储，不存明文）
  - 修复 P-4: 补充回滚验证测试具体步骤
  - 修复 P-5: MVP 范围裁剪（Task 6 降级为 V1, Task 7 仅中文）
  - 修复 W-1: 严格六边形架构分层映射
  - 修复 W-3: 明确 YAML 配置存储为 L4 退化形态
  - 实施者：待分配
-->

## Story

As a **SISYS 客户 (非技术人员)**,
I want **通过图形化向导配置系统**,
so that **无需修改 YAML 配置文件即可完成系统配置**。

## Acceptance Criteria

1. **Given** 安装完成后首次启动（安装包仅放置文件，不启动服务）
   **When** 自动打开配置向导（或用户从系统托盘/开始菜单主动打开）
   **Then** 显示欢迎引导页
   - 欢迎文案："欢迎使用 SISYS 配置向导"
   - 步骤概览："只需 4 步，约 5 分钟"
   - 明确告知用户结果："配置完成后，您就可以通过浏览器访问 SISYS 系统了"
   - 提供"跳过"选项，**跳过后果说明**：跳过后系统将使用默认配置启动（端口 8080，默认 admin 密码），用户后续可通过 `sisys setup --wizard` 命令重新打开向导
   - 支持中文界面

2. **Given** 配置向导已打开（通过欢迎页点击"开始配置"）
   **When** 用户填写管理员账号信息
   **Then** 显示以下配置项：
   - 用户名（默认：admin，可修改）
   - 密码（≥12 位，含大小写+数字+特殊字符，带强度指示器 - 进度条形式，分弱/中/强三级，颜色分别为红/黄/绿）
   - 确认密码（实时匹配验证）
   - 邮箱（可选，用于密码找回）
   - 密码显示支持"显示/隐藏"切换（眼睛图标）
   - **密码处理规则**：用户输入的密码在后端使用 bcrypt/argon2 **哈希**后写入目标存储（PostgreSQL 用户表或 .htpasswd），配置文件中**不存储密码本身，也不存储哈希**，仅记录"已配置"标记

3. **Given** 用户正在配置系统参数
   **When** 选择安装路径和端口配置
   **Then** 显示以下配置项：
   - 安装路径（默认推荐路径，支持"浏览"按钮修改）
     - Windows: `C:\sisys`
     - macOS: `/Applications/Sisys`
     - Linux: `/opt/sisys`
   - 端口配置（自动检测可用端口，冲突时高亮提示）：
     - SISYS 主服务：[8080]（被占用时自动建议 8081→8082→...）
     - 数据库端口：[5432]（PostgreSQL）
     - 缓存端口：[6379]（Redis）
   - 端口冲突时显示清晰的替代建议和影响说明
   - **低端口号提示**：如果用户选择 < 1024 的端口，提示需要管理员权限

4. **Given** 用户需要选择部署模式
   **When** 选择配置模板
   **Then** 提供预设配置模板选项：
   - **开发模式**（MVP 默认）：单机部署，所有组件在同一机器
     - 适用场景：个人测试/开发环境
     - 资源需求：8 核 CPU, 16GB 内存, 50GB 磁盘
   - **演示模式**：最小资源，快速启动
     - 适用场景：销售演示/培训环境
     - 资源需求：4 核 CPU, 8GB 内存, 20GB 磁盘
   - **生产模式**（V1 推出，MVP 阶段显示为"即将推出"，不可选择）
   - 每个模板显示资源需求预估和部署时间预估

5. **Given** 配置填写完成
   **When** 用户点击"应用"
   **Then** 执行配置应用流程：
   - 显示配置摘要供用户最终确认
   - 执行配置验证（端口占用检查、磁盘空间检查等）
   - 验证失败时显示具体错误和建议修复方案
   - 验证通过后生成配置文件（docker-compose.yml, .env 等）
   - 显示部署进度条（含实时日志输出）
   - 部署完成后显示成功提示和访问地址
   - 支持"查看配置详情"按钮跳转至系统状态页

6. **Given** 配置应用过程中出现异常
   **When** 部署失败或用户取消操作
   **Then** 系统状态回滚到配置应用前
   - 显示清晰的错误信息（用用户语言描述问题，提供明确的解决建议，避免技术术语堆砌）
   - 不残留半配置状态的文件
   - 提供"重试"和"取消"选项
   - 记录详细错误日志供 Story 0.17 诊断工具使用
   - **回滚验证**：回滚完成后自动执行健康检查，验证：
     - 配置文件已恢复到应用前版本（文件哈希对比）
     - 运行中的服务已使用旧配置重启
     - 无临时文件或半配置状态残留
     - 系统可正常访问（HTTP 健康检查通过）

7. **Given** 用户已完成初始配置
   **When** 需要修改配置
   **Then** 支持从系统设置重新打开配置向导
   - 显示当前配置值（非空白表单）
   - 修改后提示需要重启服务
   - **配置变更历史可追溯**（MVP 仅记录变更日志：谁在什么时候改了什么字段，V1 增加完整审计日志和变更对比）
   - **配置导出/导入**（V1 能力，MVP 仅支持查看当前配置摘要）

8. **Given** 非技术用户使用配置向导
   **When** 完成整个配置流程
   **Then** 全程无需接触 YAML/JSON 配置文件
   - 所有配置项通过表单填写
   - 技术细节隐藏在"高级选项"折叠面板中
   - 提供"推荐配置"按钮一键填充最佳实践
   - 配置完成后可生成配置文件预览（只读，供技术人员参考）

9. **Given** 配置部署成功
   **When** 用户看到成功提示页
   **Then** 显示配置完成后的引导页
   - 显示系统访问地址（大字号、可点击、可复制）
   - 提供"首次登录教程"引导（"用刚才设置的管理员账号登录"）
   - 展示已配置的服务列表和状态（PostgreSQL/Redis/Qdrant/MinIO/Neo4j/SISYS）
   - 提供"查看完整配置"入口（只读 YAML 预览，供技术人员参考）
   - 提供"重新配置"选项（返回配置向导）

## Tasks / Subtasks

- [ ] Task 1: 配置向导 UI 框架搭建 (AC: 1, 8)
  - [ ] 创建配置向导组件目录结构
  - [ ] 实现步骤导航组件（支持前进/后退/跳过）
  - [ ] 创建配置表单基础组件（输入框、选择器、端口检测器）
  - [ ] 实现响应式布局（支持桌面端分辨率自适应）

- [ ] Task 2: 管理员账号配置步骤 (AC: 2)
  - [ ] 创建用户名/密码/邮箱表单
  - [ ] 实现密码强度验证逻辑（实时检测）
  - [ ] 添加密码显示/隐藏切换功能
  - [ ] 实现表单验证和错误提示

- [ ] Task 3: 系统参数配置步骤 (AC: 3, 4)
  - [ ] 创建安装路径选择组件（带浏览按钮）
  - [ ] 实现端口自动检测功能
  - [ ] 创建配置模板选择器（开发/生产/演示）
  - [ ] 实现资源需求预估显示组件

- [ ] Task 4: 配置验证引擎 (AC: 5, 6)
  - [ ] 实现配置验证规则引擎
  - [ ] 实现端口占用检测逻辑
  - [ ] 实现磁盘空间检测逻辑
  - [ ] 创建验证错误提示组件

- [ ] Task 5: 配置生成与应用 (AC: 5, 6)
  - [ ] 实现配置文件生成器（docker-compose.yml, .env 等）
  - [ ] 创建配置应用执行器（重启服务、验证启动）
  - [ ] 实现部署进度条组件（含实时日志输出）
  - [ ] 实现异常处理和回滚逻辑

- [ ] Task 6: [V1 P1] 配置历史与导出（MVP 降级为仅记录变更日志）
  - [ ] MVP: 实现基础变更日志记录（谁在什么时候改了什么字段）
  - [ ] V1: 实现配置历史记录完整功能
  - [ ] V1: 创建配置导出/导入功能
  - [ ] V1: 实现配置变更对比显示（diff 视图）
  - [ ] V1: 添加配置审计日志

- [ ] Task 7: [MVP P0] 中文界面 + 无障碍基础
  - [ ] MVP: 实现中文界面（所有表单、提示、错误信息）
  - [ ] MVP: i18n 架构预留（使用 i18next，英文翻译可后续添加）
  - [ ] MVP: 基础无障碍支持（键盘导航、label 关联、色盲友好配色）
  - [ ] V1: 完整 WCAG 2.1 AA 合规 + 英文切换
  - [ ] V1: 屏幕阅读器完整兼容
  - [ ] 技术术语通俗化翻译（tooltip 提示）
  - [ ] 上下文帮助提示（每个字段旁的 ⓘ 图标）

- [ ] Task 8: [MVP P0] 集成测试与 E2E 测试 (All AC)
  - [ ] 编写配置向导完整流程 E2E 测试（含首次安装自动触发场景）
  - [ ] 编写配置验证逻辑单元测试
  - [ ] 编写异常场景测试（端口冲突、空间不足、部署中断）
  - [ ] 编写回滚验证集成测试（含文件哈希对比、服务健康检查）
  - [ ] 编写配置幂等性测试（重复应用配置不产生副作用）
  - [ ] 编写并发配置访问测试（last write wins 策略验证）
  - [ ] 编写前端 React 组件单元测试（React Testing Library）
  - [ ] 编写多分辨率兼容性测试（Playwright Chromium/Firefox/WebKit）

## Dev Notes

### Story 复杂度评估

| 维度 | 评估 | 说明 |
|------|------|------|
| **技术复杂度** | ⭐⭐⭐ 中等 | 涉及 UI 开发、配置验证、服务控制等 |
| **依赖关系** | ⭐⭐ 中等 | 依赖 Story 0.17 的诊断能力（可降级实现） |
| **工作量** | ⭐⭐⭐⭐ 较高 | 预计 5-7 天（含 UI、逻辑、测试） |
| **风险等级** | ⭐⭐ 中低 | 技术成熟，主要难点在用户体验 |
| **测试复杂度** | ⭐⭐⭐ 中等 | 需要多场景、多分辨率、多平台验证 |

**预计工作量分解：**
- Task 1 (UI 框架): 1 天
- Task 2-3 (表单实现): 1.5 天
- Task 4-5 (验证与应用): 2 天
- Task 6 (配置历史): 0.5 天
- Task 7 (多语言): 0.5 天
- Task 8 (测试): 1.5 天

### 前置依赖关系

**必须完成的前置 Story：**
- Story 0.14/0.15/0.16: 各平台安装包（提供基础部署能力）
- Story 0.17: 自动检测与修复（可选依赖，用于增强诊断能力）

**相关 Story：**
- Story 0.9: CI/CD Pipeline 模板（复用配置模板）
- Story 1.1: 六边形架构（遵循领域层零依赖原则）
- Story 7.1: CLI 接口（配置向导应调用 CLI 命令而非直接操作文件）

**后续依赖 Story：**
- Story 1.1-1.19: 所有 Epic 1 故事（依赖基础配置能力）
- Story 7.4: 健康度仪表盘（可显示当前配置摘要）

### 技术选型说明

**前端技术栈：**

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|---------|
| **React + Ant Design 5.x** | 组件丰富、生态成熟、与架构文档一致 | 需要 Node.js 环境 | 生产环境推荐 ✅ |
| Vue 3 + Element Plus | 学习曲线低、中文文档好 | 国际化支持稍弱 | 快速原型 |
| Python + Typer + Rich CLI | 无需前端服务、CLI 原生 | 图形化能力受限 | 纯 CLI 场景 |

**推荐**: 采用 **React + Ant Design 5.x**（与项目整体技术栈一致）

**配置存储方案：**

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **YAML 配置文件** | 人类可读、版本控制友好 | 需要解析器 | 开发/运维 ✅ |
| PostgreSQL 配置表 | 支持查询、审计日志 | 增加复杂度 | V1 增强 |
| JSON 配置 | 解析简单、程序友好 | 人类可读性差 | 内部传输 |

**推荐**: MVP 采用 **YAML 配置文件**（存储在 `$HOME/.sisys/config.yaml`），V1 可同步到 PostgreSQL

**端口检测实现：**
```python
import socket

def check_port_available(port: int) -> bool:
    """检测端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False
```

**密码强度验证规则：**
- 长度 ≥ 12 位
- 包含大写字母 (A-Z)
- 包含小写字母 (a-z)
- 包含数字 (0-9)
- 包含特殊字符 (!@#$%^&*等)
- 不使用常见密码（检查前 10000 常见密码库）

### 架构合规要求

**来源:**
- [Source: _bmad-output/planning-artifacts/architecture.md#1-架构概述与设计哲学] - 六边形架构
- [Source: _bmad-output/planning-artifacts/architecture.md#1.5-CLI+Skills-核心设计原则] - CLI 优先原则
- [Source: _bmad-output/planning-artifacts/architecture.md#11-存储架构设计] - 配置存储
- [Source: _bmad-output/planning-artifacts/prd.md#MVP-功能集合] - MVP 功能需求

**六边形架构在配置向导中的映射：**

```
src/
  domain/
    entities/
      config_profile.py              # 配置实体（端口、路径、模板类型）
      config_change_log.py           # 配置变更日志实体
    services/
      config_validation_service.py   # 配置验证服务（领域规则）
      password_strength_service.py   # 密码强度验证（领域规则）
    ports/
      config_repository.py           # 配置仓储接口（端口）
      service_controller.py          # 服务控制器接口（启停服务）
      config_validation_port.py      # 配置验证端口（可扩展规则）

  application/
    use_cases/
      setup_wizard_use_case.py       # 配置向导用例
      apply_config_use_case.py       # 配置应用用例
      rollback_config_use_case.py    # 配置回滚用例
    dto/
      config_request.py              # 配置请求 DTO
      config_response.py             # 配置响应 DTO

  infrastructure/
    adapters/
      yaml_config_repository.py      # YAML 配置仓储实现（L4 对象存储的 MVP 退化形态）
      postgres_config_repository.py  # PostgreSQL 配置仓储实现（V1 升级路径，L2 关系存储层）
      docker_compose_service.py      # Docker Compose 服务控制
      port_detector.py               # 端口检测实现（socket）
      service_controller.py          # 服务启停实现

  interfaces/
    cli/
      setup_commands.py              # CLI 入口（sisys setup, sisys config apply 等）
    web/
      config_wizard_server.py        # 内嵌 HTTP 服务器（FastAPI/Flask）
      api_routes.py                  # Web API 路由（调用 CLI 命令）

  web/
    config-wizard/                   # React 前端（仅图形化封装）
      src/
        components/
          WizardSteps.tsx
          AccountForm.tsx
          SystemConfigForm.tsx
          TemplateSelector.tsx
          ProgressBar.tsx
        pages/
          WelcomePage.tsx            # 欢迎引导页
          SuccessPage.tsx            # 成功引导页
          WizardPage.tsx
        utils/
          validation.ts
          api.ts
```

**CLI 与 Web UI 职责边界：**
- **CLI 侧（Python）**：真正的业务实现。`sisys setup` / `sisys config validate` / `sisys config apply` / `sisys config rollback` 是核心命令
- **Web 侧（React）**：仅是 CLI 的图形化前端。通过 HTTP 调用内嵌服务器的 API 路由，API 路由再调用 CLI 命令
- **数据流**：Web UI → 内嵌 FastAPI 服务器 → CLI 命令 → 领域服务 → 配置文件
- **启动模型**：`sisys setup --wizard` 启动内嵌 HTTP 服务器（默认端口 8888），自动打开浏览器，配置完成后可选择关闭服务器

**存储架构映射：**
- **MVP 形态**：YAML 配置文件存储在 `$HOME/.sisys/config.yaml`，这是 **L4 对象存储层（MinIO）的 MVP 退化形态**。文件系统作为临时真相源
- **V1 升级路径**：配置同步到 PostgreSQL config 表（L2 关系存储层），YAML 仅作为导出格式
- **审计日志**：所有配置变更记录到 PostgreSQL audit_log 表（即使 MVP 配置存在文件中）

### TDD 测试要求

**测试覆盖率指标：**
- 后端单元测试覆盖率：≥ 80%（使用 pytest-cov 测量）
- 后端集成测试覆盖率：≥ 70%
- 前端 React 组件测试覆盖率：≥ 75%（使用 Jest + React Testing Library）
- E2E 测试覆盖率：关键路径 100%，AC 覆盖率 ≥ 90%
- 契约测试覆盖率：100%（CLI <> Web UI 边界）

**测试文件结构：**
```
tests/config_wizard/
├── conftest.py                          # pytest 夹具配置
├── unit/
│   ├── test_config_validation.py        # 配置验证逻辑测试 (≥15 个测试用例)
│   ├── test_password_strength.py        # 密码强度验证测试 (≥8 个测试用例)
│   ├── test_port_detector.py            # 端口自动检测测试 (≥6 个测试用例)
│   └── test_config_generator.py         # 配置文件生成测试 (≥18 个测试用例，参数化覆盖)
├── integration/
│   ├── test_config_apply.py             # 配置应用集成测试 (≥8 个测试用例)
│   ├── test_config_rollback.py          # 配置回滚集成测试 (≥5 个测试用例)
│   ├── test_config_idempotency.py       # 配置幂等性测试 (≥3 个测试用例)
│   ├── test_concurrent_config.py        # 并发配置访问测试 (≥3 个测试用例)
│   └── test_template_rendering.py       # 模板渲染测试（验证 YAML 语法正确性）(≥6 个测试用例)
├── contract/
│   └── test_cli_web_contract.py         # CLI <> Web UI 契约测试 (≥5 个测试用例)
└── e2e/
    ├── test_wizard_basic_flow.py        # 配置向导基础流程 (≥3 个场景)
    ├── test_wizard_validation.py        # 配置验证流程 (≥3 个场景)
    ├── test_wizard_error_handling.py    # 异常场景 (≥3 个场景)
    ├── test_wizard_rollback.py          # 回滚验证场景 (≥2 个场景)
    └── test_wizard_accessibility.py     # 无障碍基础测试 (axe-core 自动检测)

web/config-wizard/src/__tests__/
├── components/
│   ├── WizardSteps.test.tsx             # 步骤导航组件测试
│   ├── AccountForm.test.tsx             # 管理员账号表单测试
│   ├── SystemConfigForm.test.tsx        # 系统参数表单测试
│   ├── TemplateSelector.test.tsx        # 配置模板选择器测试
│   └── ProgressBar.test.tsx             # 部署进度条测试
└── utils/
    ├── validation.test.ts               # 前端验证逻辑测试
    └── api.test.ts                      # API 调用模拟测试
```

**测试实施步骤 (TDD 流程)：**
1. **红** - 先写失败的测试（定义预期行为）
2. **绿** - 编写最小实现使测试通过
3. **重构** - 优化代码保持测试通过

**验收标准：**
- 所有测试文件存在且可执行
- 测试通过率 100%
- 总体覆盖率 ≥ 80%
- E2E 场景覆盖率 100%

### E2E 测试场景

**场景 0: 安装完成 → 自动打开配置向导 → 欢迎页展示 → 用户完成配置 → 系统可访问**
1. 安装包完成文件放置（不启动服务）
2. 验证自动触发配置向导（打开浏览器到 localhost:8888）
3. 验证欢迎页显示（欢迎文案、步骤概览、跳过选项）
4. 用户点击"开始配置"并走完所有步骤
5. 验证服务启动成功，可通过 http://localhost:8080 访问

**场景 1: 首次安装 → 打开配置向导 → 填写配置 → 应用配置 → 验证启动**
1. 新安装 SISYS → 手动打开配置向导（`sisys setup --wizard`）
2. 填写管理员账号（admin/Password123!/admin@example.com）
3. 选择安装路径和端口（使用默认值）
4. 选择"开发模式"模板
5. 点击"应用"并验证配置生成
6. 验证服务自动启动并可访问
7. 使用新配置的管理员账号登录系统

**场景 2: 端口冲突 → 检测提示 → 自动建议 → 选择替代端口 → 成功应用**
1. 8080 端口已被占用
2. 配置向导检测到冲突并高亮提示（"这个位置已经有其他程序在使用了，试试我们推荐的 8081 怎么样？"）
3. 自动建议 8081 端口
4. 用户确认使用 8081
5. 配置应用成功
6. 验证服务在 8081 端口可访问

**场景 3: 配置错误 → 验证失败 → 显示错误 → 修改配置 → 重新应用**
1. 填写无效的安装路径（如不存在的磁盘）
2. 配置验证失败，显示清晰错误提示（"安装需要 40GB 空间，当前磁盘还剩 XXGB。建议清理一些空间后再试。"）
3. 用户修改为有效路径
4. 重新验证通过
5. 配置应用成功

**场景 4: 部署中断 → 异常处理 → 回滚配置 → 重新部署**
1. 配置应用过程中模拟网络中断（Docker 镜像下载中断）
2. 验证配置回滚到应用前状态，**具体验证步骤**：
   - 配置文件哈希与回滚前一致
   - Docker 容器使用旧配置重启（或保持停止状态）
   - 无临时文件残留（检查 `.sisys/tmp/` 目录为空）
   - HTTP 健康检查通过（或返回预期错误状态）
3. 验证无半配置状态残留
4. 重新运行配置向导
5. 验证配置应用成功

**场景 5: 配置幂等性 → 重复应用不产生副作用**
1. 完成一次配置应用
2. 不修改任何配置，再次点击"应用"
3. 验证系统状态不变（文件哈希一致、服务未重启、无重复日志）

### 安全测试用例

1. **密码强度验证** - 弱密码被拒绝并显示原因
2. **SQL 注入防护** - 表单输入包含特殊字符时正确转义
3. **配置文件权限** - 生成的配置文件权限正确（仅所有者可读写）
4. **敏感数据加密** - 密码在配置文件中加密存储（非明文）
5. **权限提升防护** - 普通用户无法通过配置向导提升权限
6. **配置导出安全** - 导出的配置文件不包含敏感信息（密码哈希）

### 质量门禁清单

| 检查项 | 阈值 | 执行阶段 | 失败动作 |
|--------|------|---------|---------|
| 单元测试覆盖率 | ≥ 80% | CI 测试阶段 | 阻断合并 |
| 集成测试通过率 | 100% | CI 测试阶段 | 阻断合并 |
| E2E 测试通过率 | 100% | CI E2E 阶段 | 阻断合并 |
| 配置验证逻辑覆盖率 | 100% | CI 测试阶段 | 阻断合并 |
| 安全扫描 | 0 error, 0 warning | CI 静态分析 | 阻断合并 |
| 无障碍测试 | WCAG 2.1 AA | CI 无障碍测试 | 警告（记录偏差） |
| 多分辨率测试 | 100% 通过 | CI E2E 阶段 | 警告（记录偏差） |
| 性能基准 | 全部达标 | 性能测试阶段 | 警告（记录偏差） |

### 性能基准

**预期性能指标：**

| 指标 | 目标值 | 测量方式 | 说明 |
|------|--------|---------|------|
| 配置向导加载时间 | < 2 秒 | 从点击应用到界面渲染完成 | 含依赖检查时间 |
| 端口检测时间 | < 1 秒 | 检测 10 个端口的总时间 | 并发检测优化 |
| 配置验证时间 | < 3 秒 | 从点击"应用"到验证完成 | 含磁盘/端口/路径检查 |
| 配置文件生成时间 | < 2 秒 | 从验证通过到文件写入完成 | 含模板渲染时间 |
| 服务启动时间 | < 120 秒 | 从启动命令到服务就绪 | 含 Docker 容器冷启动 |
| 配置回滚时间 | < 10 秒 | 从触发回滚到恢复完成 | 快速回滚保证 |

### 兼容性测试矩阵

| 平台 | 分辨率 | 浏览器 | 优先级 | 说明 |
|------|--------|--------|--------|------|
| Windows 10+ | 1920x1080 | Chrome | P0 | MVP 核心场景 |
| macOS 12+ | 1440x900 | Safari/Chrome | P0 | MVP 核心场景 |
| Windows 10+ | 1366x768 | Chrome | P1 | V1 低分辨率笔记本 |
| macOS 12+ | 2560x1600 | Safari | P1 | V1 Retina 显示屏 |
| Linux (Ubuntu) | 1920x1080 | Firefox | P2 | V2 开发环境 |

**无障碍测试要求（MVP 基础）：**
- 键盘导航 100% 支持（Tab/Enter/Escape）
- 表单标签完整关联（label htmlFor）
- 色盲友好配色（不依赖颜色单独传达信息）
- V1: 完整 WCAG 2.1 AA 合规 + 屏幕阅读器兼容

### 故障排除指南

#### 配置向导无法打开

**症状：** 点击配置向导后无响应

**排查步骤：**
```bash
# 1. 检查 SISYS 服务是否运行
sisys status

# 2. 检查日志
tail -f ~/.sisys/logs/config-wizard.log

# 3. 手动打开配置向导
sisys setup --wizard
```

**常见问题：**
- 服务未启动 → 运行 `sisys start`
- 端口被占用 → 检查 8080 端口占用情况

#### 配置应用失败

**症状：** 点击"应用"后显示错误

**排查步骤：**
```bash
# 1. 查看详细错误日志
sisys diagnose

# 2. 检查磁盘空间
df -h

# 3. 检查端口占用
netstat -tulpn | grep :8080
```

**常见问题：**
- 磁盘空间不足 → 清理空间（需要至少 40GB）
- 端口被占用 → 选择其他端口
- 权限不足 → 使用管理员权限运行

#### 配置回滚失败

**症状：** 部署失败后无法回滚到之前状态

**排查步骤：**
```bash
# 1. 检查配置备份
ls -la ~/.sisys/config-backups/

# 2. 手动恢复配置
sisys config restore --backup <backup-file>

# 3. 重新启动服务
sisys restart
```

### 安全考虑

**密码管理：**
- 密码在配置文件中加密存储（使用 bcrypt 或 argon2）
- 密码传输使用 HTTPS（生产环境）
- 首次登录后强制修改密码（MVP 可选）
- 支持密码找回通过邮箱验证

**配置文件安全：**
- 配置文件权限：600（仅所有者可读写）
- 敏感信息（密码、密钥）加密存储
- 配置导出时自动脱敏（隐藏密码哈希）
- 配置历史加密存储

**权限控制：**
- 配置向导需要管理员权限
- 普通用户只能查看配置（只读模式）
- 配置变更需要认证（防止未授权修改）
- 配置审计日志记录所有变更

### 回滚方案

**场景 1：配置应用后服务无法启动**

```bash
# 1. 自动回滚到配置前状态
sisys config rollback --auto

# 2. 检查回滚状态
sisys status

# 3. 查看回滚日志
tail -f ~/.sisys/logs/rollback.log
```

**场景 2：配置损坏或误修改**

```bash
# 1. 列出可用备份
sisys config backups

# 2. 恢复到指定备份
sisys config restore --backup <backup-file>

# 3. 验证恢复结果
sisys config validate
```

**场景 3：完全重置配置**

```bash
# 1. 重置为默认配置
sisys config reset --default

# 2. 重新运行配置向导
sisys setup --wizard

# 3. 验证新配置
sisys config validate
```

**回滚验证清单：**
- [ ] 配置文件已恢复到正确状态
- [ ] 服务可以正常启动
- [ ] 配置验证通过
- [ ] 无残留的半配置状态

### References

- [Source: _bmad-output/planning-artifacts/sprint-status.yaml#development_status] - 故事来源和状态追踪
- [Source: _bmad-output/planning-artifacts/epics_v1.0.md#Story-0.18] - Epic 0 产品设计（用户友好配置向导）
- [Source: _bmad-output/planning-artifacts/prd.md#MVP-功能集合] - MVP 功能需求
- [Source: _bmad-output/planning-artifacts/architecture.md#1.5-CLI+Skills-核心设计原则] - CLI 优先原则
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Design-System-Foundation] - Ant Design 5.x 设计系统
- [Source: https://ant.design/components/form/] - Ant Design Form 组件文档
- [Source: https://ant.design/components/steps/] - Ant Design Steps 组件文档

### Project Structure Notes

**严格遵循六边形架构分层（与 sisys 根目录对齐）：**

```
sisys/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── config_profile.py          # 配置实体
│   │   │   └── config_change_log.py       # 配置变更日志实体
│   │   ├── services/
│   │   │   ├── config_validation_service.py  # 配置验证服务（领域规则）
│   │   │   └── password_strength_service.py  # 密码强度验证
│   │   └── ports/
│   │       ├── config_repository.py       # 配置仓储接口
│   │       ├── service_controller.py      # 服务控制器接口
│   │       └── config_validation_port.py  # 验证规则扩展端口
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── setup_wizard_use_case.py
│   │   │   ├── apply_config_use_case.py
│   │   │   └── rollback_config_use_case.py
│   │   └── dto/
│   │       ├── config_request.py
│   │       └── config_response.py
│   ├── infrastructure/
│   │   └── adapters/
│   │       ├── yaml_config_repository.py     # YAML 仓储实现（L4 MVP 退化）
│   │       ├── postgres_config_repository.py # PostgreSQL 仓储实现（V1）
│   │       ├── docker_compose_service.py
│   │       ├── port_detector.py
│   │       └── service_controller.py
│   └── interfaces/
│       ├── cli/
│       │   └── setup_commands.py            # CLI 入口
│       └── web/
│           ├── config_wizard_server.py      # 内嵌 HTTP 服务器
│           └── api_routes.py                # Web API 路由
├── web/
│   └── config-wizard/
│       ├── src/
│       │   ├── components/
│       │   ├── pages/
│       │   └── utils/
│       └── package.json
├── tests/
│   └── config_wizard/
│       ├── conftest.py
│       ├── unit/
│       ├── integration/
│       ├── contract/
│       └── e2e/
└── docs/
    └── config-wizard/
        └── CONFIG_WIZARD.md
```

**命名规范：**
- Python 模块：`snake_case`（如 `config_validator.py`）
- React 组件：`PascalCase`（如 `AccountForm.tsx`）
- 测试文件：`test_*.py`（与项目其他测试文件保持一致）
- 配置文件模板：`docker-compose.*.yml`（与环境命名一致）

### 关键实现注意事项

1. **CLI 优先原则（严格执行）**: 配置向导是 `sisys setup` 命令的图形化封装
   - Web UI 通过 HTTP API 调用 CLI 命令（而非直接操作文件）
   - CLI 命令：`sisys setup --wizard`、`sisys config validate`、`sisys config apply`、`sisys config rollback`
   - CLI 命令输出结构化 JSON（供 Web UI 解析）
   - **禁止**：Web UI 绕过 CLI 直接读写配置文件

2. **六边形架构分层（严格遵守）**:
   - **领域层**：配置实体、验证规则、密码强度检查（纯 Python，无外部依赖）
   - **应用层**：用例编排（SetupWizardUseCase、ApplyConfigUseCase）
   - **基础设施层**：YAML 读写、Docker Compose 控制、端口检测
   - **接口层**：CLI 命令入口 + 内嵌 Web API 服务器
   - **依赖方向**：interfaces → application → domain ← infrastructure（领域层零外部依赖）

3. **Web UI 启动模型明确**:
   - `sisys setup --wizard` 启动内嵌 FastAPI 服务器（默认端口 8888）
   - 自动打开默认浏览器到 `http://localhost:8888`
   - 配置完成/取消后自动关闭服务器
   - 安装包安装完成后自动触发此命令

4. **密码生命周期（安全修复）**:
   - 用户在向导中输入密码 → bcrypt/argon2 哈希 → 写入目标存储
   - 配置文件中**不存储密码**，仅记录"已配置"标记
   - 如需要可恢复的密码存储（服务间认证），使用 KMS 或 vault

5. **MVP 范围（严格裁剪）**:
   - **包含**: 开发模式、演示模式模板；中文界面；基础无障碍；变更日志
   - **排除**: 生产模式（V1）；英文切换（V1）；完整审计日志（V1）；配置导出/导入（V1）；变更对比（V1）

6. **配置模板的扩展机制**:
   - MVP: 硬编码 2 个模板（开发/演示）
   - V1 预留: `TemplateProvider` 端口（plugin 方式注册新模板）
   - 模板验证: JSON Schema 校验（确保模板结构正确）

7. **端口检测的跨平台兼容性**:
   - 并发检测多个端口（提升速度）
   - 冲突时自动建议下一个可用端口
   - 低端口号（< 1024）提示需要管理员权限
   - Windows 上 `SYSTEM` 进程占用端口的特殊处理

8. **部署进度日志的结构化输出**:
   - CLI 侧输出结构化事件流（JSON Lines）
   - Web 侧消费并渲染为进度条
   ```python
   {"event": "docker_pull_start", "image": "postgres:15", "timestamp": "..."}
   {"event": "docker_pull_progress", "image": "postgres:15", "percent": 45}
   {"event": "docker_pull_complete", "image": "postgres:15"}
   ```

9. **错误消息微文案规范**:
   - 用用户语言描述问题（不说"端口 8080 被占用"，说"这个位置已经有其他程序在使用了"）
   - 提供明确的解决建议（"试试我们推荐的 8081 怎么样？"）
   - 避免技术术语堆砌（不显示 `OSError: [Errno 98] Address already in use`）
   - 情感安抚（"别担心，这个问题很容易解决"）

10. **回滚验证自动化**:
    - 回滚完成后自动执行健康检查
    - 验证文件哈希一致、服务状态正确、无临时文件
    - 验证结果记录日志（供 Story 0.17 诊断工具使用）

11. **配置幂等性保证**:
    - 重复应用相同配置不产生副作用
    - 使用配置哈希检测是否真正需要变更
    - 幂等性测试纳入 E2E 场景 5

## Dev Agent Record

### Agent Model Used

- **Model**: 待分配
- **Version**: 待实施
- **Mode**: BMad Method Dev Story Engine

### Debug Log References

- Story 实施日志：待创建 `_bmad-output/logs/dev-story-0-18-<date>.log`

### Completion Notes List

待实施

### File List

待实施
