# Story 0.17: 自动检测与修复

Status: ready-for-dev

<!--
故事创建日期：2026-04-12
创建者：Qwen Code (BMad Method Story Context Engine)
故事来源：sprint-status.yaml (轨道 2：产品交付系统)
前置依赖：Story 0-14 (Windows ✅), Story 0-15 (Mac ✅), Story 0-16 (Linux ✅)
-->

## Story

As a **SISYS 客户 (非技术用户)**,
I want **安装过程中遇到的问题能够自动检测和修复**,
so that **我遇到安装问题时不会卡住，系统能自动解决问题**。

## Acceptance Criteria

1. **Given** 安装脚本执行过程中
   **When** 检测到端口冲突
   **Then** 自动尝试使用该端口
   **And** 如果被占用，自动切换至下一个可用端口
   **And** 在日志中记录端口变更
   **And** 向用户显示中文提示："端口 X 被占用，已自动改用 Y 端口"

2. **Given** 镜像拉取阶段
   **When** 默认镜像源拉取失败
   **Then** 自动切换至备用镜像源（国内镜像仓库）
   **And** 显示切换原因和当前进度
   **And** 所有源均失败时提供详细的诊断建议

3. **Given** 安装前检查阶段
   **When** 检测到磁盘空间不足（< 50GB 可用）
   **Then** 输出清晰的中文预警："磁盘空间不足，需要至少 50GB 可用空间。当前可用：XX GB"
   **And** 建议清理方案（列出可安全删除的临时文件/缓存）
   **And** 用户可选择忽略预警继续安装或中止安装

4. **Given** 服务启动失败
   **When** Docker Compose 启动服务后健康检查失败
   **Then** 自动获取错误日志并诊断根本原因
   **And** 根据诊断结果自动尝试修复（如重启服务、释放端口、调整资源限制）
   **And** 修复失败时提供中文人话提示和日志文件位置

5. **Given** 安装过程中遇到异常
   **When** 错误发生
   **Then** 捕获异常并尝试自动恢复
   **And** 恢复失败时显示中文错误描述、原因分析、修复建议
   **And** 输出日志文件位置供进一步排查

**自动修复场景汇总:**
| 场景 | 检测方式 | 自动修复动作 | 失败提示 |
|------|---------|------------|---------|
| 端口被占用 | `ss -tlnp` / `lsof -i` | 自动切换端口 → 更新 `.env` | "端口 X 被占用，自动切换至 Y 端口失败，请手动释放端口 X" |
| 镜像下载失败 | `docker pull` 返回非 0 退出码 | 切换镜像源 → 重试（最多 3 次） | "无法下载镜像，请检查网络或手动配置镜像源" |
| 磁盘空间不足 | `df -h` 检测 < 50GB | 预警 + 建议清理临时文件 | "磁盘空间严重不足，需要至少 50GB，当前仅 XX GB" |
| 服务启动失败 | `docker compose ps` 检查 Exit Code | 获取日志 → 诊断 → 重启（最多 3 次） | "服务启动失败，请查看日志：/var/log/sisys/install.log" |
| 内存不足 | `free -m` 检测 < 4GB | 预警 + 建议关闭其他服务 | "内存不足可能导致性能问题，建议至少 8GB" |
| Docker 服务异常 | `docker info` 失败 | 尝试重启 Docker 服务 | "Docker 服务异常，请检查系统状态" |

**人话提示示例:**
```
❌ 错误：Port 3000 already in use
✅ 提示：端口 3000 被其他程序占用，已自动改用 3001 端口

❌ 错误：pull access denied for registry.example.com/app
✅ 提示：无法从当前镜像源下载应用镜像，正在尝试切换备用源... (1/3)

❌ 错误：No space left on device
✅ 提示：磁盘空间不足，需要至少 50GB 可用空间。当前可用：20GB
        建议清理：/tmp 目录 (约 5GB)，Docker 缓存 (约 10GB)
        是否继续安装？[y/N]

❌ 错误：container sisys-app exited with code 1
✅ 提示：SISYS 应用启动失败（错误代码：1）
        可能原因：数据库连接失败
        正在尝试重启服务... (1/3)
        如问题持续存在，请查看完整日志：/var/log/sisys/install.log
```

**实施指南:** `docs/delivery/AUTO_DIAGNOSE_AND_FIX.md`

## Context

**产品交付系统定位：** 本 Story 属于"轨道 2：产品交付系统"，面向最终客户，提供**高级自动诊断与修复能力**，增强 Story 0-14/0-15/0-16 的基础安装脚本。

**与 Story 0-16 的区别与增强：**
- Story 0-16 提供了**基础安装脚本**（Linux 一键脚本），包含基础的端口检测、镜像拉取、服务启动功能
- Story 0-17 在此基础上增加**高级自动诊断与修复引擎**，能够：
  1. 智能诊断服务启动失败的根本原因（分析日志、识别错误模式）
  2. 自动尝试多种修复策略（重启、资源调整、配置优化）
  3. 提供结构化的诊断报告（问题描述、原因分析、修复尝试、最终状态）
  4. 支持更多边缘场景的自动恢复（内存不足、权限问题、网络抖动）

**目标平台：** 本 Story 的自动诊断与修复能力将作为**通用模块**，可复用于 Windows (.exe)、Mac (.dmg)、Linux (.sh) 三种安装包。

## Tasks / Subtasks

- [ ] **T1: 创建通用诊断引擎核心模块** (AC: 1, 4, 5)
  - [ ] T1.1: 实现诊断引擎框架（DiagnosisEngine 类/函数库）
    - 支持注册检查器（Checker）和修复器（Fixer）
    - 提供统一的诊断流程：检测 → 分析 → 修复 → 报告
  - [ ] T1.2: 实现日志采集器（LogCollector）
    - 支持从 Docker 容器日志、系统日志 (journalctl)、应用日志采集
    - 支持按时间范围、组件名称过滤日志
  - [ ] T1.3: 实现错误模式匹配器（ErrorPatternMatcher）
    - 预定义常见错误模式（端口占用、连接拒绝、内存不足、权限错误等）
    - 使用正则表达式 + 关键词匹配识别错误类型
    - 返回诊断结果：问题类型、严重等级、推荐修复动作
  - [ ] T1.4: 实现修复策略注册表（FixerRegistry）
    - 支持注册修复策略（端口切换、服务重启、资源调整、配置更新）
    - 根据诊断结果自动匹配最合适的修复策略
    - 支持修复重试（最多 3 次，间隔 5 秒）

- [ ] **T2: 实现端口冲突自动修复** (AC: 1)
  - [ ] T2.1: 增强 Story 0-16 的端口检测逻辑
    - 检测端口占用时，不仅记录被占用，还尝试自动切换
    - 扫描备选端口范围（如 3000-3010），找到第一个可用端口
  - [ ] T2.2: 实现 `.env` 文件动态更新
    - 读取现有 `.env` 文件，更新端口配置
    - 备份原始 `.env` 文件（`.env.backup.<timestamp>`）
    - 应用新配置重启服务
  - [ ] T2.3: 实现端口变更通知
    - 输出中文提示："端口 X 被占用，已自动改用 Y 端口"
    - 记录端口变更到安装日志

- [ ] **T3: 实现镜像拉取自动切换源** (AC: 2)
  - [ ] T3.1: 增强 Story 0-16 的镜像拉取逻辑
    - 维护镜像源列表（主源、备用源 1、备用源 2）
    - 拉取失败时，自动切换至下一源并重试（最多 3 次）
  - [ ] T3.2: 实现拉取进度显示
    - 显示当前源、已尝试次数、进度百分比
    - 切换源时说明原因（如"主源超时，正在切换备用源..."）
  - [ ] T3.3: 实现全源失败诊断
    - 所有源均失败时，执行网络诊断（ping、DNS 解析、代理检测）
    - 输出详细的修复建议（检查网络、配置代理、手动下载等）

- [ ] **T4: 实现服务启动失败自动诊断与修复** (AC: 4)
  - [ ] T4.1: 实现服务启动失败检测
    - `docker compose ps` 检查容器状态（Exit Code、健康状态）
    - 识别启动失败的服务及其依赖关系
  - [ ] T4.2: 实现日志分析与根因诊断
    - 获取失败容器的最近 100 行日志
    - 使用错误模式匹配器识别问题类型
    - 生成诊断报告（问题描述、可能原因、严重等级）
  - [ ] T4.3: 实现自动修复策略
    - **场景 1: 依赖服务未就绪** → 等待 10 秒后重启
    - **场景 2: 端口冲突** → 调用 T2 端口切换逻辑
    - **场景 3: 资源不足** → 降低资源限制后重启
    - **场景 4: 配置错误** → 恢复默认配置后重启
  - [ ] T4.4: 实现修复结果验证
    - 修复后重新执行健康检查
    - 成功则继续安装，失败则尝试下一修复策略
    - 所有策略失败则输出诊断报告并请求用户干预

- [ ] **T5: 实现磁盘空间与内存不足预警** (AC: 3)
  - [ ] T5.1: 增强安装前检查逻辑
    - 检测磁盘空间（`df -h`），不仅检查是否 < 50GB，还分析各分区使用情况
    - 检测可用内存（`free -m`），< 8GB 预警，< 4GB 预警为严重
  - [ ] T5.2: 实现清理建议生成
    - 扫描可安全删除的临时文件（/tmp、~/.cache、Docker 悬空镜像）
    - 估算可释放空间大小并展示给用户
  - [ ] T5.3: 实现用户交互式确认
    - 空间不足时显示预警，用户可选择"继续安装"或"中止"
    - 记录用户选择到安装日志

- [ ] **T6: 创建诊断报告生成器** (AC: 5)
  - [ ] T6.1: 实现结构化诊断报告
    - 报告包含：问题概述、发生时间、影响组件、原因分析、修复尝试、最终状态
    - 支持输出为文本（终端显示）和文件（保存到日志目录）
  - [ ] T6.2: 实现中文人话提示格式化
    - 使用颜色区分严重等级（红色=严重、黄色=预警、绿色=成功）
    - 使用图标增强可读性（✅ 成功、⚠️ 预警、❌ 错误、🔄 重试中）
  - [ ] T6.3: 集成到 Story 0-16 安装脚本
    - 在关键步骤（镜像拉取、服务启动、健康检查）调用诊断引擎
    - 保持向后兼容：如诊断引擎未触发，原安装流程不受影响

- [ ] **T7: 创建诊断与修复测试用例** (AC: 1-5)
  - [ ] T7.1: 编写端口冲突自动修复测试
    - 模拟端口被占用场景 → 验证自动切换端口 → 验证服务成功启动
  - [ ] T7.2: 编写镜像源切换测试
    - 模拟主源不可达 → 验证自动切换备用源 → 验证镜像成功拉取
  - [ ] T7.3: 编写服务启动失败诊断测试
    - 模拟服务启动失败 → 验证日志采集与根因诊断 → 验证自动修复尝试
  - [ ] T7.4: 编写磁盘空间预警测试
    - 模拟磁盘空间不足 → 验证预警输出 → 验证用户交互确认
  - [ ] T7.5: 编写综合场景测试
    - 模拟多问题并发（端口占用 + 镜像拉取失败）→ 验证诊断引擎顺序处理

## Dev Notes

### 技术栈与工具

| 技术 | 版本 | 用途 |
|------|------|------|
| Bash | 4.4+ | 诊断引擎脚本（Linux） |
| PowerShell | 7.0+ | 诊断引擎脚本（Windows） |
| Python | 3.11+ | 高级诊断逻辑（可选，用于复杂错误模式匹配） |
| Docker | ≥24.0 | 容器日志采集与服务管理 |
| jq | 1.6+ | JSON 配置文件解析（`.env` 更新、诊断报告） |

**注意：** 本 Story 以 **Bash 脚本**为主（与 Story 0-16 技术栈对齐），如遇到复杂逻辑（如日志分析、错误模式匹配），可引入轻量级 Python 脚本作为辅助工具。

### 架构约束

**来源:** [Source: _bmad-output/planning-artifacts/epic0-design.md#轨道 2: 产品交付系统详细架构 - 自动诊断架构]

自动诊断与修复架构已在 `epic0-design.md` 中定义：

```
┌─────────────────┐
│  诊断引擎        │
│  DiagnosisEngine│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  检查注册表      │
│  CheckRegistry  │
│  - 端口检查      │
│  - 磁盘检查      │
│  - 服务检查      │
│  - 网络检查      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  修复注册表      │
│  FixerRegistry  │
│  - 端口切换      │
│  - 服务重启      │
│  - 资源清理      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  诊断报告        │
│  DiagnosisReport│
│  - 检查结果      │
│  - 修复记录      │
│  - 建议事项      │
└─────────────────┘
```

**关键实现要求：**
1. **模块化设计**：诊断引擎必须可复用，不仅限于 Linux 安装脚本，还需支持 Windows/Mac 安装包
2. **检查器 (Checker) 与修复器 (Fixer) 注册表模式**：
   - 使用配置文件或代码注册检查器和修复器的映射关系
   - 检查器返回结构化结果（状态码 + 详细信息）
   - 修复器根据检查结果匹配修复策略
3. **诊断报告格式统一**：
   - 使用 JSON 或 YAML 格式存储诊断报告
   - 终端输出使用中文格式化显示

### 项目结构

```
sisys/                                             # ← 当前项目根目录
└── delivery/                                      # ← 交付件目录
    ├── common/
    │   ├── diagnose_engine.sh                     # ← 通用诊断引擎核心（Bash）
    │   ├── diagnose_engine.py                     # ← 高级诊断逻辑（Python 辅助工具）
    │   ├── checkers/
    │   │   ├── port_checker.sh                    # ← 端口检查器
    │   │   ├── disk_checker.sh                    # ← 磁盘检查器
    │   │   ├── service_checker.sh                 # ← 服务检查器
    │   │   └── network_checker.sh                 # ← 网络检查器
    │   ├── fixers/
    │   │   ├── port_switcher.sh                   # ← 端口切换修复器
    │   │   ├── service_restarter.sh               # ← 服务重启修复器
    │   │   ├── resource_cleaner.sh                # ← 资源清理修复器
    │   │   └── config_updater.sh                  # ← 配置更新修复器
    │   └── report_generator.sh                    # ← 诊断报告生成器
    ├── sisys-linux-installer/
    │   ├── install.sh                             # ← Story 0-16 主安装脚本（需增强集成诊断引擎）
    │   └── ...
    ├── sisys-windows-installer/
    │   └── ...                                    # ← 未来可复用诊断引擎
    ├── sisys-mac-installer/
    │   └── ...                                    # ← 未来可复用诊断引擎
    └── tests/
        ├── test_diagnose_engine.sh                # ← 诊断引擎测试
        ├── test_port_fixer.sh                     # ← 端口修复测试
        ├── test_image_pull_failover.sh            # ← 镜像拉取切换测试
        └── test_service_recovery.sh               # ← 服务恢复测试
```

**文件组织原则：**
- 诊断引擎核心代码放在 `common/` 目录，便于 Windows/Mac/Linux 三平台复用
- 各检查器和修复器独立文件，便于测试和扩展
- 安装脚本 (`install.sh`) 只需调用诊断引擎 API，不内嵌复杂逻辑

### 诊断引擎接口设计

```bash
#!/bin/bash
# diagnose_engine.sh - 通用诊断引擎接口

# 注册检查器
register_checker() {
    local name="$1"
    local check_func="$2"
    local fix_func="$3"
    # 将检查器和修复器注册到全局映射
}

# 执行诊断流程
run_diagnosis() {
    local target="$1"  # 如 "port:3000", "service:sisys-app", "disk:available"

    # 1. 调用检查器
    local check_result=$($check_func "$target")

    # 2. 分析结果
    if [[ "$check_result" == "OK" ]]; then
        echo "✅ $target 检查通过"
        return 0
    fi

    # 3. 调用修复器
    echo "🔄 检测到 $target 异常，正在尝试修复..."
    local fix_result=$($fix_func "$target" "$check_result")

    # 4. 验证修复
    if [[ "$fix_result" == "SUCCESS" ]]; then
        echo "✅ $target 修复成功"
        return 0
    else
        echo "❌ $target 修复失败，请手动干预"
        return 1
    fi
}

# 生成诊断报告
generate_report() {
    local report_file="/var/log/sisys/diagnosis_report_$(date +%Y%m%d_%H%M%S).json"
    # 输出结构化 JSON 报告
}
```

### 与 Story 0-16 的集成点

Story 0-16 的 `install.sh` 中以下位置需要集成诊断引擎：

| Story 0-16 原逻辑 | 集成诊断引擎后 | 触发条件 |
|------------------|--------------|---------|
| `ss -tlnp \| grep $PORT` 检测端口 | 调用 `run_diagnosis "port:$PORT"` | 端口被占用时 |
| `docker pull $IMAGE` 拉取镜像 | 调用 `run_diagnosis "image:$IMAGE"` | 拉取失败时 |
| `docker compose up -d` 启动服务 | 调用 `run_diagnosis "service:$SERVICE"` | 健康检查失败时 |
| `df -h` 检查磁盘空间 | 调用 `run_diagnosis "disk:available"` | 空间 < 50GB 时 |
| 任何 `set -e` 导致的脚本退出 | 捕获 ERR trap，调用诊断引擎 | 异常发生时 |

**集成示例代码片段：**

```bash
# 原 Story 0-16 逻辑
if ss -tlnp | grep -q ":${APP_PORT} "; then
    echo "⚠️  端口 $APP_PORT 被占用"
    # 原逻辑：手动处理...
fi

# Story 0-17 增强后
if ss -tlnp | grep -q ":${APP_PORT} "; then
    run_diagnosis "port:${APP_PORT}" || {
        echo "❌ 端口修复失败，请手动处理"
        exit 1
    }
fi
```

### 错误模式库

预定义的错误模式及其修复策略：

| 错误模式 | 正则表达式 | 诊断结果 | 修复策略 |
|---------|----------|---------|---------|
| 端口占用 | `Address already in use` / `bind: address already in use` | 端口 X 被进程 Y 占用 | 端口切换 → 更新配置 → 重启 |
| 镜像拉取失败 | `pull access denied` / `net/http: request canceled` | 镜像源不可达 | 切换源 → 重试 |
| 磁盘空间不足 | `No space left on device` / `write: no space left` | 磁盘空间 < 阈值 | 预警 + 清理建议 |
| 内存不足 | `Cannot allocate memory` / `OOM killer` | 可用内存 < 阈值 | 预警 + 建议关闭其他服务 |
| 权限不足 | `Permission denied` / `EACCES` | 当前用户权限不足 | 提示使用 sudo 或检查文件权限 |
| 连接拒绝 | `Connection refused` / `dial tcp: connection refused` | 目标服务未启动 | 等待 → 重启依赖服务 |
| 超时 | `Timeout` / `context deadline exceeded` | 网络或资源响应超时 | 增加超时时间 → 重试 |
| Docker 服务异常 | `Cannot connect to the Docker daemon` | Docker 服务未运行 | 尝试启动 Docker 服务 |

### 与相邻 Story 的边界

| Story | 功能 | 与 0-17 的关系 |
|-------|------|--------------|
| 0-14 Windows 安装包 | Windows .exe 安装程序 | 0-17 提供通用诊断引擎，Windows 安装包可复用 |
| 0-15 Mac 安装包 | Mac .dmg 安装程序 | 0-17 提供通用诊断引擎，Mac 安装包可复用 |
| 0-16 Linux 一键脚本 | Linux 安装脚本 | **0-17 增强 0-16，集成诊断引擎实现自动修复** |
| **0-17 自动检测与修复** | **高级诊断与自动修复** | **本 Story** |
| 0-18 用户友好配置向导 | 图形化配置界面 | 0-18 提供 GUI 配置，0-17 在 CLI 安装阶段提供自动修复 |

### TDD 测试要求

**测试覆盖率指标：**
- 诊断引擎核心逻辑覆盖率：≥ 90%（所有检查器 + 修复器）
- 集成测试覆盖率：100%（6 个自动修复场景全部验证）
- 错误模式匹配准确率：≥ 95%（预定义 8 个错误模式 100% 匹配）

**测试文件结构：**
```
delivery/tests/
├── test_diagnose_engine.sh                # 诊断引擎单元测试
├── test_port_fixer.sh                     # 端口修复集成测试
├── test_image_pull_failover.sh            # 镜像拉取切换测试
├── test_service_recovery.sh               # 服务恢复测试
├── test_disk_space_warning.sh            # 磁盘空间预警测试
└── fixtures/
    ├── mock_port_in_use.txt               # 模拟端口占用 ss 输出
    ├── mock_docker_pull_error.txt         # 模拟镜像拉取失败日志
    ├── mock_service_crash_log.txt         # 模拟服务启动失败日志
    └── mock_low_disk_space.txt            # 模拟磁盘空间不足 df 输出
```

**TDD 实施步骤：**
1. **红** - 先写失败测试（定义诊断引擎接口、检查器/修复器行为）
2. **绿** - 实现最小诊断引擎核心（注册表 + 基本检测修复）
3. **重构** - 提取检查器和修复器为独立模块
4. **扩展** - 逐个实现 6 个自动修复场景的测试与代码

**验收标准：**
- 所有测试脚本存在且可执行（`chmod +x delivery/tests/*.sh`）
- ShellCheck 静态分析零警告（`shellcheck -x -s bash deploy/common/*.sh delivery/tests/*.sh`）
- 6 个自动修复场景测试 100% 通过
- 错误模式匹配准确率 ≥ 95%
- 诊断引擎可被 Story 0-16 安装脚本无缝集成

### Testing Standards

- 遵循 Story 0-16 测试标准：`set -euo pipefail`、ShellCheck 零警告
- 使用 mock 文件模拟不同故障场景（端口占用日志、镜像拉取错误等）
- 关键路径测试：6 个自动修复场景（端口切换、镜像源切换、服务重启、磁盘预警、内存预警、网络诊断）
- 集成测试：模拟 Story 0-16 安装过程中触发诊断引擎 → 验证自动修复成功
- 边界测试：修复器重试 3 次后放弃 → 验证诊断报告输出

### References

- [Source: _bmad-output/planning-artifacts/epics_v1.0.md#Story 0.17] - Epic 文档中的 Story 定义
- [Source: _bmad-output/planning-artifacts/epic0-design.md#轨道 2: 产品交付系统详细架构 - 自动诊断架构] - 产品交付系统自动诊断架构
- [Source: _bmad-output/implementation-artifacts/stories/0-16-linux-installer.md] - Story 0-16 Linux 一键脚本（前置依赖，需集成诊断引擎）
- [Source: _bmad-output/planning-artifacts/architecture.md §1.2] - 系统公理二：六层存储架构
- [Source: docs/delivery/AUTO_DIAGNOSE_AND_FIX.md] - 自动检测与修复参考指南

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
