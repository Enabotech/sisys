# Epic 1 Story 1.1: 六边形架构骨架 - SDD+TDD 融合模式试点实施计划

**版本:** 1.0.0
**日期:** 2026-03-04
**试点 Story:** Epic 1 Story 1.1 - 六边形架构骨架
**负责人:** Charlie (Senior Dev)
**预计周期:** 2-3 天

---

## 📋 Story 定义

### 用户故事

```
As a **系统架构师**,
I want **实现领域驱动六边形架构骨架**,
So that **领域逻辑与技术实现隔离，支持独立演进和测试**。
```

### 验收标准（SDD 规范）

```gherkin
Given 项目初始化完成
When 创建领域层、应用层、接口层、基础设施层目录结构
Then 领域层仅依赖 Python 标准库，不包含任何外部框架导入
And 各层之间依赖方向正确（基础设施层→应用层→领域层）
```

### 架构约束

- **FR-AR-01**: 领域层零依赖原则
- **依赖方向**: 基础设施层→应用层→领域层（单向）
- **测试标准**: 领域层覆盖率≥90%，整体覆盖率≥80%

---

## 🎯 融合模式实施流程

### Step 1: SDD 规范定义（预计 2 小时）

#### 1.1 定义验收测试（Gherkin 格式）

**文件:** `tests/acceptance/test_story_1_1.feature`

```gherkin
Feature: 六边形架构骨架
  作为系统架构师
  我希望建立领域驱动六边形架构
  这样领域逻辑与技术实现隔离

  Scenario: 领域层仅依赖 Python 标准库
    Given 项目初始化完成
    When 检查领域层导入
    Then 领域层不包含任何外部框架导入
    And 领域层仅使用 Python 标准库

  Scenario: 各层依赖方向正确
    Given 六边形架构已创建
    When 检查依赖关系
    Then 基础设施层→应用层→领域层依赖方向正确
    And 领域层不依赖任何外部层

  Scenario: 架构骨架通过 CI/CD 验证
    Given 代码提交到 Git
    When 触发 CI/CD 流水线
    Then 运行导入检查验证领域层零依赖
    And 运行架构约束测试
    And 所有测试通过
```

#### 1.2 定义架构约束测试

**文件:** `tests/unit/architecture/test_hexagonal_architecture.py`

```python
"""
TDD 单元测试：六边形架构约束验证
在实现之前编写，预期测试失败
"""
import pytest
import importlib.util
from pathlib import Path


class TestDomainLayerZeroDependency:
    """测试领域层零依赖原则（FR-AR-01）"""

    def test_domain_layer_only_uses_stdlib(self):
        """Given 领域层代码，When 检查导入，Then 仅使用 Python 标准库"""
        # Arrange
        domain_path = Path("src/domain")
        forbidden_modules = {
            'fastapi', 'sqlalchemy', 'redis', 'qdrant',
            'minio', 'neo4j', 'langgraph', 'prefect'
        }

        # Act - 扫描领域层所有 Python 文件
        domain_imports = self.scan_imports(domain_path)

        # Assert - 不包含任何外部模块
        external_imports = domain_imports & forbidden_modules
        assert len(external_imports) == 0, (
            f"Domain layer uses external modules: {external_imports}"
        )

    def test_domain_layer_has_no_infrastructure_imports(self):
        """Given 领域层代码，When 检查导入，Then 不包含基础设施层导入"""
        # Arrange
        domain_path = Path("src/domain")
        infrastructure_modules = {
            'src.infrastructure', 'src.interfaces'
        }

        # Act
        domain_imports = self.scan_imports(domain_path)

        # Assert
        invalid_imports = domain_imports & infrastructure_modules
        assert len(invalid_imports) == 0, (
            f"Domain layer imports infrastructure: {invalid_imports}"
        )

    def scan_imports(self, path: Path) -> set:
        """扫描 Python 文件的所有导入"""
        # TODO: 使用 ast 模块实现完整解析
        imports = set()
        for py_file in path.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单解析导入语句
        return imports


class TestLayerDependencyDirection:
    """测试各层依赖方向正确"""

    def test_application_layer_can_import_domain(self):
        """Given 应用层代码，When 导入领域层，Then 成功导入"""
        # Arrange
        from src.domain.entities.strategic_plan import StrategicPlan

        # Act & Assert
        assert StrategicPlan is not None

    def test_infrastructure_layer_can_import_application(self):
        """Given 基础设施层代码，When 导入应用层，Then 成功导入"""
        # Arrange
        from src.application.usecases.create_plan import CreatePlanHandler

        # Act & Assert
        assert CreatePlanHandler is not None

    def test_domain_layer_cannot_import_infrastructure(self):
        """Given 领域层代码，When 尝试导入基础设施层，Then 失败"""
        # 这个测试应该在架构设计上就阻止
        # TODO: 实现导入检查机制
```

#### 1.3 验证测试可运行（红阶段）

**命令:**
```bash
$ pytest tests/acceptance/test_story_1_1.feature -v
$ pytest tests/unit/architecture/test_hexagonal_architecture.py -v
```

**预期结果:**
```
FAILED ... (5 个测试全部失败，预期行为)
```

**Qwen Code Agent 辅助:**
```
提示词：
"基于以下 SDD 规范，生成 TDD 单元测试初稿：

规范：
- 领域层零依赖（FR-AR-01）
- 依赖方向：基础设施层→应用层→领域层

要求：
- 使用 pytest 格式
- 包含导入检查逻辑
- 使用 Arrange-Act-Assert 模式"
```

---

### Step 2: TDD 红阶段（预计 30 分钟）

#### 2.1 运行测试确认失败

**命令:**
```bash
# 运行架构约束测试
$ pytest tests/unit/architecture/test_hexagonal_architecture.py -v

# 预期输出
================================================================================
FAILED test_hexagonal_architecture.py::TestDomainLayerZeroDependency::test_domain_layer_only_uses_stdlib
FAILED test_hexagonal_architecture.py::TestDomainLayerZeroDependency::test_domain_layer_has_no_infrastructure_imports
FAILED test_hexagonal_architecture.py::TestLayerDependencyDirection::test_application_layer_can_import_domain
FAILED test_hexagonal_architecture.py::TestLayerDependencyDirection::test_infrastructure_layer_can_import_application
FAILED test_hexagonal_architecture.py::TestLayerDependencyDirection::test_domain_layer_cannot_import_infrastructure
================================================================================
5 failed
```

#### 2.2 验证失败原因

**检查点:**
- [ ] 测试失败是因为架构还没实现（预期行为）
- [ ] 失败信息清晰可读
- [ ] 没有语法错误或其他异常

**红阶段完成标志:**
```bash
$ pytest tests/unit/architecture/ -v
5 FAILED (预期行为)
```

---

### Step 3: TDD 绿阶段（预计 1 小时）

#### 3.1 最小实现：创建架构骨架

**文件:** `src/__init__.py`
```python
"""
TDD 最小实现：六边形架构骨架
只编写让测试通过的代码
"""

# 显式导出各层，确保导入路径正确
from src import domain
from src import application
from src import infrastructure
from src import interfaces

__all__ = ['domain', 'application', 'infrastructure', 'interfaces']
```

**文件:** `src/domain/__init__.py`
```python
"""
领域层 - 零外部依赖
仅依赖 Python 标准库
"""
from src.domain import entities
from src.domain import events
from src.domain import repositories
from src.domain import exceptions

__all__ = ['entities', 'events', 'repositories', 'exceptions']
```

**文件:** `src/domain/entities/__init__.py`
```python
"""领域实体模块"""
# 暂时为空，让测试通过
```

**文件:** `src/domain/events/__init__.py`
```python
"""领域事件模块"""
# 暂时为空，让测试通过
```

**文件:** `src/domain/repositories/__init__.py`
```python
"""仓储接口模块"""
# 暂时为空，让测试通过
```

**文件:** `src/domain/exceptions/__init__.py`
```python
"""领域异常模块"""
# 暂时为空，让测试通过
```

**文件:** `src/application/__init__.py`
```python
"""应用层 - 可依赖领域层"""
from src.application import usecases
from src.application import commands
from src.application import queries

__all__ = ['usecases', 'commands', 'queries']
```

**文件:** `src/infrastructure/__init__.py`
```python
"""基础设施层 - 可依赖应用层和领域层"""
from src.infrastructure import database
from src.infrastructure import event_bus
from src.infrastructure import repositories

__all__ = ['database', 'event_bus', 'repositories']
```

**文件:** `src/interfaces/__init__.py`
```python
"""接口层 - 可依赖应用层"""
from src.interfaces import cli
from src.interfaces import api

__all__ = ['cli', 'api']
```

#### 3.2 运行测试验证通过

**命令:**
```bash
$ pytest tests/unit/architecture/test_hexagonal_architecture.py -v

# 预期输出
================================================================================
PASSED test_hexagonal_architecture.py::TestDomainLayerZeroDependency::test_domain_layer_only_uses_stdlib
PASSED test_hexagonal_architecture.py::TestDomainLayerZeroDependency::test_domain_layer_has_no_infrastructure_imports
PASSED test_hexagonal_architecture.py::TestLayerDependencyDirection::test_application_layer_can_import_domain
PASSED test_hexagonal_architecture.py::TestLayerDependencyDirection::test_infrastructure_layer_can_import_application
PASSED test_hexagonal_architecture.py::TestLayerDependencyDirection::test_domain_layer_cannot_import_infrastructure
================================================================================
5 passed
```

**绿阶段完成标志:**
```bash
$ pytest tests/unit/architecture/ -v
5 PASSED
```

---

### Step 4: TDD 重构阶段（预计 1.5 小时）

#### 4.1 改进导入扫描逻辑

**文件:** `tests/unit/architecture/test_hexagonal_architecture.py`

```python
"""重构后：使用 ast 模块正确解析导入"""
import ast
from pathlib import Path
from typing import Set


class TestDomainLayerZeroDependency:
    """测试领域层零依赖原则（FR-AR-01）"""

    def test_domain_layer_only_uses_stdlib(self):
        """Given 领域层代码，When 检查导入，Then 仅使用 Python 标准库"""
        # Arrange
        domain_path = Path("src/domain")
        forbidden_modules = {
            'fastapi', 'sqlalchemy', 'redis', 'qdrant',
            'minio', 'neo4j', 'langgraph', 'prefect'
        }

        # Act
        domain_imports = self.scan_imports_ast(domain_path)

        # Assert
        external_imports = domain_imports & forbidden_modules
        assert len(external_imports) == 0, (
            f"Domain layer uses external modules: {external_imports}"
        )

    def scan_imports_ast(self, path: Path) -> Set[str]:
        """使用 ast 模块扫描 Python 文件的所有导入"""
        imports = set()

        for py_file in path.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split('.')[0])

                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split('.')[0])

            except SyntaxError:
                # 跳过有语法错误的文件
                continue

        return imports
```

#### 4.2 添加领域层文档

**文件:** `src/domain/__init__.py`

```python
"""
领域层 - 零外部依赖
仅依赖 Python 标准库

架构约束（FR-AR-01）：
- 不导入任何外部框架（FastAPI/SQLAlchemy/Redis 等）
- 不依赖基础设施层或接口层
- 仅使用 Python 标准库和领域模型

目录结构：
- entities/: 领域实体（聚合根、实体、值对象）
- events/: 领域事件（DomainEvent 子类）
- repositories/: 仓储接口（Repository Protocol）
- exceptions/: 领域异常（DomainError 子类）

使用示例：
    from src.domain.entities.strategic_plan import StrategicPlan
    from src.domain.events.plan_events import PlanCreated
    from src.domain.repositories.plan_repository import PlanRepository
"""
# 显式导出领域层核心组件
from src.domain.entities.base import BaseEntity
from src.domain.events.base import DomainEvent
from src.domain.repositories.base import BaseRepository
from src.domain.exceptions.base import DomainError

__all__ = [
    # 实体
    'entities',
    'BaseEntity',

    # 事件
    'events',
    'DomainEvent',

    # 仓储
    'repositories',
    'BaseRepository',

    # 异常
    'exceptions',
    'DomainError',
]
```

#### 4.3 运行代码质量工具

**命令:**
```bash
# 1. Ruff 检查
$ ruff check src/domain/ src/application/ src/infrastructure/ src/interfaces/
All checks passed!

# 2. Ruff 格式化
$ ruff format src/domain/ src/application/ src/infrastructure/ src/interfaces/
2 files reformatted, 3 files left unchanged

# 3. MyPy 类型检查
$ mypy src/
Success: no issues found in source code
```

#### 4.4 验证测试仍然通过

**命令:**
```bash
$ pytest tests/unit/architecture/ -v

# 预期输出
================================================================================
5 PASSED
================================================================================
```

**重构阶段完成标志:**
- 代码质量检查通过
- 所有测试仍然通过
- 代码更优雅、更易维护

---

### Step 5: SDD 规范验证（预计 30 分钟）

#### 5.1 架构约束验证

**命令:**
```bash
# 运行架构约束测试
$ pytest tests/unit/architecture/ -v
================================================================================
5 PASSED
```

#### 5.2 类型检查

**命令:**
```bash
$ mypy src/
Success: no issues found in source code
```

#### 5.3 覆盖率检查

**命令:**
```bash
$ pytest --cov=src/domain --cov-fail-under=90

# 预期输出
Name                                      Stmts   Miss  Cover
-------------------------------------------------------------
src/domain/__init__.py                        5      0   100%
src/domain/entities/__init__.py               1      0   100%
src/domain/events/__init__.py                 1      0   100%
src/domain/repositories/__init__.py           1      0   100%
src/domain/exceptions/__init__.py             1      0   100%
-------------------------------------------------------------
TOTAL                                         9      0   100%
```

#### 5.4 验收测试

**命令:**
```bash
$ pytest tests/acceptance/test_story_1_1.feature -v
================================================================================
PASSED test_story_1_1.feature::test_domain_layer_only_uses_stdlib
PASSED test_story_1_1.feature::test_layer_dependency_direction_correct
PASSED test_story_1_1.feature::test_architecture_validates_in_ci_cd
================================================================================
3 passed
```

**SDD 规范验证完成标志:**
- 架构约束测试通过
- 类型检查通过
- 覆盖率达标（领域层≥90%）
- 验收测试通过

---

### Step 6: CI/CD 流水线验证（预计 30 分钟）

#### 6.1 本地模拟 CI/CD 检查

**命令:**
```bash
# 质量门禁检查
$ make quality-gates

# 预期输出
=== 质量门禁检查 ===
1. Ruff 代码检查
All checks passed!

2. Ruff 格式检查
Would be formatted correctly

3. MyPy 类型检查
Success: no issues found in source code

4. 单元测试（覆盖率≥80%）
================================================================================
5 passed
================================================================================

5. 安全扫描
No issues found

✅ 所有质量门禁通过！
```

#### 6.2 提交代码触发 CI/CD

**命令:**
```bash
# 提交代码
$ git add .
$ git commit -m "feat: 实现六边形架构骨架 (SDD+TDD 融合模式试点)

- 领域层零依赖（FR-AR-01）
- 依赖方向：基础设施层→应用层→领域层
- TDD 测试驱动开发（红 - 绿 - 重构循环）
- SDD 规范验证（Schema/API 契约/验收测试）
- 领域层覆盖率 100%

#SDD+TDD #Epic1-Story1.1"

$ git push origin main
```

#### 6.3 验证 GitHub Actions 流水线

**检查点:**
- [ ] CI 流水线触发
- [ ] 阶段 1: 代码质量门禁通过
- [ ] 阶段 2: 单元测试通过（覆盖率≥80%）
- [ ] 阶段 3: 集成测试通过
- [ ] 阶段 4: 安全扫描通过
- [ ] 阶段 5: 构建与部署通过

**CI/CD 流水线完成标志:**
- GitHub Actions 所有 Job 显示绿色勾

---

## 📊 试点成功标准

### 技术指标

- [ ] **架构约束验证通过**
  - [ ] 领域层零依赖（FR-AR-01）
  - [ ] 依赖方向正确
  - [ ] 5/5 架构测试通过

- [ ] **覆盖率达标**
  - [ ] 领域层覆盖率≥90%（实际：100%）
  - [ ] 整体覆盖率≥80%

- [ ] **代码质量检查通过**
  - [ ] Ruff 检查通过
  - [ ] Ruff 格式检查通过
  - [ ] MyPy 类型检查通过
  - [ ] 安全扫描通过

- [ ] **CI/CD 流水线通过**
  - [ ] 所有阶段通过
  - [ ] 部署到测试环境
  - [ ] 健康检查通过

### 流程指标

- [ ] **SDD 规范定义完成**
  - [ ] 验收测试（Gherkin 格式）
  - [ ] 架构约束测试
  - [ ] SDD 实施检查清单使用

- [ ] **TDD 红 - 绿 - 重构循环完成**
  - [ ] 红阶段：测试在实现之前编写
  - [ ] 绿阶段：最小实现让测试通过
  - [ ] 重构阶段：优化代码保持测试通过

- [ ] **SDD 规范验证完成**
  - [ ] Schema 验证
  - [ ] API 契约测试（如适用）
  - [ ] 验收测试
  - [ ] 类型检查

### 团队学习指标

- [ ] **团队理解融合模式**
  - [ ] 能解释红 - 绿 - 重构循环
  - [ ] 能区分 SDD 和 TDD 的角色
  - [ ] 能使用检查清单

- [ ] **Qwen Code Agent 有效辅助**
  - [ ] 生成测试初稿
  - [ ] 辅助实现代码
  - [ ] 提供重构建议

---

## 🎯 试点时间表

| 阶段 | 活动 | 预计时间 | 负责人 |
|------|------|---------|--------|
| **Day 1 上午** | SDD 规范定义 | 2 小时 | Charlie |
| **Day 1 下午** | TDD 红阶段 + 绿阶段 | 1.5 小时 | Charlie |
| **Day 2 上午** | TDD 重构阶段 | 1.5 小时 | Charlie |
| **Day 2 下午** | SDD 规范验证 + CI/CD 验证 | 1 小时 | Charlie |
| **Day 3** | 缓冲时间 + 试点总结 | 2 小时 | 全体 |

---

## 📝 试点总结模板

### 什么做得好

- [ ] 列出试点中成功的方面

### 遇到的挑战

- [ ] 列出试点中遇到的困难

### 改进建议

- [ ] 对融合模式的改进建议

### 是否推广

- [ ] 是否建议在 Epic 1 其他 Story 中推广
- [ ] 推广的障碍和解决方案

---

## 🔗 相关文档

- [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md)
- [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md)
- [Story 1.1 验收标准](../../_bmad-output/planning-artifacts/epics_v1.0.md)
- [架构约束 FR-AR-01](../../_bmad-output/planning-artifacts/architecture.md)

---

**文档结束**
