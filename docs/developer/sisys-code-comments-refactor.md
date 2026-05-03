# sisys 代码注释重构方案

## 一、现状总览

| 层级 | 文件数 | 主要风格 | 覆盖率 |
|------|--------|---------|--------|
| domain | ~80 | Google Style 60% / 中文 20% / 无规约 15% | ~85% |
| application | ~10 | 中文为主 50% / Google 40% | ~90% |
| infrastructure | ~60 | Google Style 70% / 中文 25% | ~95% |
| interfaces | ~5 | Google Style 80% | ~80% |

---

## 二、核心问题诊断

### P0 必须修复（影响代码可维护性）

**1. Protocol/ABC 实现类无 docstring**

```python
# 问题示例
class InMemoryEventListener:  # 无 docstring
    """无文档的实现类"""

class SandboxExecutorProtocol(Protocol):  # 无 docstring
    pass
```

**2. `__post_init__` 方法普遍缺失文档**

```python
# 问题：所有 dataclass 的 __post_init__ 都无文档
@dataclass
class MemorySaveRequest:
    user_id: str
    content: str

    def __post_init__(self):  # 无 docstring
        self.content = self.content.strip()
```

**3. 异常类无 docstring**

```python
# 问题
class LayerNotFoundError(Exception):  # 无 docstring
    pass
```

**4. 私有方法 `_method` 大多无文档**

```python
# 问题
def _build_async_url(self) -> str:  # 无 docstring
    """构建异步引擎连接 URL。"""  # 只有一个简单描述
```

### P1 强烈推荐（影响团队协作）

**5. 中英混用风格不统一**

```python
# 同一文件内混用
"""JWT Service — JWT token generation and validation."""
def create_access_token(...):
    """Create a new JWT access token."""
    # 英文方法注释，但...
    def _rule_compress(text: str) -> str:
        """规则压缩：去除停用词、冗余空格、换行。"""  # 中文
```

**6. 文件头缺少标准结构**

```python
# 问题：文件头缺少 Architecture/References/Sections
"""Neo4j 图数据库连接配置模型。"""
# 应该包含 Architecture 层、References 来源等
```

---

## 三、标准化注释模板

### 模板 1：文件头（强制标准）

```python
"""<ModuleName> — <一句话功能描述>.

Architecture:
    Layer: <domain|application|infrastructure|interfaces>
    Depends: <允许的外部依赖（仅 domain 层需声明仅用标准库）>
    Constraints: <特殊约束或限制>

References:
    - ADR-<N>: <决策标题>
    - Story <ID>: <故事标题>
    - SDD §<section>: <架构文档章节>

Note:
    <重要说明、P0 约束、或暂时未实现的功能>
"""
```

**⚠️ 领域层约束（硬性要求）**：
```python
# domain 层文件头必须明确声明标准库依赖
"""MemoryService — 记忆服务领域接口.

Architecture:
    Layer: domain
    Depends: uuid, datetime (stdlib only)
    Constraints: 领域层零外部依赖 — 仅允许 Python 标准库
                 禁止导入：langgraph, prefect, fastapi, pydantic, sqlalchemy,
                 redis, qdrant, minio, neo4j, aio_pika, litellm 等
...
"""
```

**示例（domain 层）**：

```python
"""MemoryService — 记忆服务领域接口.

Architecture:
    Layer: domain
    Depends: uuid, datetime (stdlib only)
    Constraints: 领域层零外部依赖原则

References:
    - ADR-008: Memory service design
    - Story 3.1: 记忆服务实现

Note:
    实现类位于 src/application/services/memory_service_impl.py
"""
```

**示例（infrastructure 层）**：

```python
"""Neo4jConfig — Neo4j 图数据库连接配置模型.

Architecture:
    Layer: infrastructure (config)
    Depends: os, dataclasses (stdlib)

References:
    - Story 1.6: QdrantConfig (配置风格参考)
    - ADR-016: Graph storage decision
"""
```

### 模板 2：类 docstring（强制标准）

```python
class <ClassName>:
    """<一句话职责描述>.

    详细说明（可选）: <使用场景、设计决策、约束条件>

    Attributes:
        attr1: <类型> — <描述>
        attr2: <类型> — <描述>

    Raises:
        ExceptionType: <何时抛出>
    """
```

> **Note**：中文标签（使用场景、与其他组件的关系、状态机/约束）是项目定制，
> 便于快速理解架构关系。pydoclint 扫描时建议使用 `--ignore=D417` 或配置
> `notation = "google"` 并忽略非标准节名。
> 如需完全符合 Google 标准，可改用 `Attributes:`、`Raises:` 英文标签。

### 模板 3：方法 docstring（强制标准）

```python
def <method>(self, <args>) -> <return_type>:
    """<一句话描述（动词开头）>.

    详细说明: <设计决策、使用注意、边界条件>

    Args:
        <param>: <类型> — <描述>

    Returns:
        <类型>: <描述>

    Raises:
        <Exception>: <何时抛出>

    Example:
        >>> result = obj.method(arg1, arg2)
    """
```

### 模板 4：Protocol/抽象类 docstring

```python
class <ServiceName>Protocol:
    """Protocol for <服务职责描述>.

    This protocol defines the contract for <服务名称>.
    Implementations must satisfy all method signatures and semantics defined here.

    Example:
        >>> class MyService(<ServiceName>Protocol):
        ...     async def method(self, arg: str) -> dict:
        ...         ...
    """

    def method(self, arg: str) -> dict:
        """Handle <操作>.

        Args:
            arg: Description of arg.

        Returns:
            dict: Description of return value.

        Raises:
            SomeError: Description of when exception is raised.
        """
        ...
```

> **Note**：Protocol 中的方法需要定义签名和文档契约，实现类继承后应保持语义一致。
> Google 风格中 Protocol 类文档描述整体契约，具体方法在类级别描述。

---

## 四、优先级修复清单

### Phase 1: P0 问题（必须修复，影响可维护性）

| 序号 | 问题类型 | 影响范围 | 修复建议 |
|------|----------|----------|----------|
| 1 | Protocol/ABC 实现类无 docstring | domain/events/listener.py, domain/services/*.py | 为所有实现类添加 docstring |
| 2 | `__post_init__` 无文档 | 所有 dataclass | 为所有 `__post_init__` 添加文档 |
| 3 | 异常类无 docstring | 散落在各文件 | 统一添加异常说明 |
| 4 | 私有方法 `_method` 无文档 | infrastructure 层为主 | 补充文档 |

### Phase 2: P1 问题（强烈推荐，影响协作效率）

| 序号 | 问题类型 | 影响范围 | 修复建议 |
|------|----------|----------|----------|
| 5 | 中英混用 | application 层、部分 domain | 统一为英文或中文 |
| 6 | 文件头缺少标准结构 | domain 层为主 | 添加 Architecture/References |
| 7 | dataclass 内部类无文档 | 散落 | 补充 Attributes 说明 |

### Phase 3: P2 问题（建议，提升体验）

| 序号 | 问题类型 | 修复建议 |
|------|----------|----------|
| 8 | 缺少 Example 代码 | 为关键方法添加使用示例 |
| 9 | 缺少 Note 说明 | 为复杂逻辑添加设计说明 |

---

## 五、修复示例对比

### 修复前（agent.py）

```python
class Agent:
    """Agent entity with identity profile and responsibility boundaries.

    Invariant constraints:
    - agent_id must be a valid UUID
    - role must be a valid AgentRole
    - name must not be empty
    """

    def validate(self) -> bool:
        """Validate invariant constraints.

        Returns:
            True if all invariants are satisfied.

        Raises:
            ValueError: If any invariant is violated.
        """
```

### 修复后

```python
class Agent:
    """Agent 实体 — 身份 profile 与职责边界.

    表示系统中执行任务的人工智能代理，具有明确角色和职责范围。

    Invariant constraints:
        - agent_id: 必须为有效 UUID
        - role: 必须为有效 AgentRole
        - name: 不能为空

    使用场景:
        - 通过 AgentFactory 创建
        - 通过 AgentRepository 持久化
        - 通过 AgentService 管理生命周期

    Attributes:
        agent_id: UUID — 代理唯一标识
        role: AgentRole — 代理角色（CEO/CFO/...）
        name: str — 代理名称
        description: str — 代理描述（可选）
        status: AgentStatus — 当前状态
        failure_reason: str — 失败原因（如有）
        domain_knowledge: list[str] — 领域知识列表
        responsibilities: list[str] — 职责列表
        created_at: datetime — 创建时间
        updated_at: datetime — 更新时间

    Example:
        >>> agent = Agent(
        ...     agent_id=uuid.uuid4(),
        ...     role=AgentRole.CTO,
        ...     name="Tech Lead",
        ...     description="负责技术决策"
        ... )
        >>> agent.validate()
        True
    """

    def validate(self) -> bool:
        """校验 Agent 的不变式约束.

        检查 agent_id、role、name 是否满足定义的所有约束。

        Returns:
            bool: 所有约束均满足时返回 True

        Raises:
            ValueError: 任意约束被违反时抛出

        Example:
            >>> agent.validate()
            True
            >>> agent.name = ""
            >>> agent.validate()
            ValueError: name must not be empty
        """
```

---

## 六、业界成熟工具选型与配置

### 1. Ruff — Docstring 检查（推荐）

**规则集**：pydocstyle (D)

| 规则 | 说明 | 严重级别 |
|------|------|----------|
| D100-D107 | 文档缺失检查（模块/类/方法/函数/包/嵌套类/__init__） | Error |
| D200-D215 | 格式规范（空白行、缩进、摘要位置） | Warning |
| D300-D301 | 引号转义 | Error |
| D400-D416 | 内容规范（首字母大写、标点、节名称格式） | Warning |
| D417 | 参数未文档化 | Error |

**启用方式**：

在 `pyproject.toml` 中添加：

```toml
[tool.ruff]
line-length = 128
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "D"]  # 添加 D 规则集
```

**推荐配置**（选择性启用避免噪音）：

```toml
[tool.ruff]
select = ["D", "D100", "D101", "D102", "D103", "D107", "D417"]  # 聚焦文档缺失
extend-ignore = [
    "D200",  # 允许单行 docstring
    "D203",  # 允许类前无空白行
    "D213",  # 允许多行 docstring 第二行在左侧
    "D405",  # 允许节名首字母大写
]
```

**运行检查**：

```bash
poetry run ruff check src/ --select=D
```

---

### 2. Ruff — Docstring 自动修复

Ruff 提供部分自动修复能力：

| 规则 | 自动修复 | 说明 |
|------|----------|------|
| D200 | ✅ | 将 docstring 压缩到一行（如果符合） |
| D205 | ✅ | 摘要后添加空行 |
| D400 | ✅ | 末尾添加句号 |
| 其他 | ❌ | 需手动修复 |

**批量自动修复**：

```bash
# 只修复有自动修复能力的规则
poetry run ruff check src/ --select=D --fix --unsafe-fixes

# 查看可修复的问题
poetry run ruff check src/ --select=D --show-fixes
```

---

### 3. pydoclint — 深度 docstring 检查

**特点**：
- Google/NumPy docstring 格式强制检查
- 参数类型检查（与实际签名对照）
- Returns/Yields/Raises 完整性检查

> **⚠️ 规则说明**：以下为常用规则子集（共 70+ 条），完整规则见 [pydoclint 官方文档](https://pydoclint.readthedocs.io/)。

**规则集**：

| 规则 | 说明 |
|------|------|
| DOC101 | Summary 不以动词第三人称单数结尾 |
| DOC102 | Summary 首字母大写 |
| DOC103 | Summary 末以句号结尾 |
| DOC201 | Args 缺少文档 |
| DOC202 | Returns 缺少文档 |
| DOC203 | Yields 缺少文档 |
| DOC204 | Raises 缺少文档 |
| DOC205 | Sections 缩进不正确 |
| DOC206 | Sections 之间有空行 |
| DOC207 | 节名称不以冒号结尾 |
| DOC208 | Section 内容为空 |

**安装**：

```bash
poetry add --group dev pydoclint
```

**配置**（pyproject.toml）：

```toml
[tool.pydoclint]
verification_timeout = 120
notation = "google"  # 或 "numpy"
exclude = ["tests/", "**/__init__.py"]
```

**运行**：

```bash
poetry run pydoclint src/
```

---

### 4. 检测脚本（基于 Ruff/pydoclint）

#### 检测缺少文件头的模块

```bash
#!/bin/bash
# 检测缺少标准文件头的模块（限制搜索深度）
echo "=== 缺少标准文件头的文件 (检查 Architecture: 关键字) ==="
MISSING=0
for f in $(find src -maxdepth 4 -name "*.py" -type f 2>/dev/null); do
    if ! grep -q "Architecture:" "$f" 2>/dev/null; then
        echo "  MISSING: $f"
        MISSING=$((MISSING + 1))
    fi
done
echo "  总计: $MISSING 个文件缺少 Architecture 头"
```

#### 检测文档缺失（D100-D107）

```bash
#!/bin/bash
echo "=== 缺少文档的公共定义 ==="
poetry run ruff check src/ --select=D100,D101,D102,D103,D104,D105,D106,D107 --output-format=short

echo "=== 缺少参数文档的方法 ==="
poetry run ruff check src/ --select=D417 --output-format=short
```

#### 检测 docstring 格式问题

```bash
#!/bin/bash
echo "=== docstring 格式问题 ==="
poetry run ruff check src/ --select=D200,D201,D202,D203,D204,D205 --output-format=short

echo "=== 内容规范问题 ==="
poetry run ruff check src/ --select=D400,D401,D402,D403 --output-format=short
```

#### 综合检测脚本

```bash
#!/bin/bash
# sisys 代码注释综合检测脚本

echo "=========================================="
echo "sisys 代码注释规范性检测"
echo "=========================================="

# 1. 检查缺少文档的公共定义
echo ""
echo "[1/5] 检查缺少文档的公共定义..."
poetry run ruff check src/ --select=D100,D101,D102,D103,D104,D105,D106,D107 --output-format=short 2>&1 || true

# 2. 检查缺少 __init__ 文档
echo ""
echo "[2/5] 检查缺少 __init__ 文档..."
poetry run ruff check src/ --select=D107 --output-format=short 2>&1 || true

# 3. 检查缺少参数文档
echo ""
echo "[3/5] 检查缺少参数文档..."
poetry run ruff check src/ --select=D417 --output-format=short 2>&1 || true

# 4. 检查 docstring 格式问题
echo ""
echo "[4/5] 检查 docstring 格式问题..."
poetry run ruff check src/ --select=D200,D201,D202,D203,D204,D205,D400,D401 --output-format=short 2>&1 || true

# 5. 检查缺少标准文件头（无 Architecture 关键字）
echo ""
echo "[5/5] 检查缺少标准文件头..."
MISSING=0
for f in $(find src -maxdepth 4 -name "*.py" -type f 2>/dev/null); do
    if ! grep -q "Architecture:" "$f" 2>/dev/null; then
        echo "  MISSING: $f"
        MISSING=$((MISSING + 1))
    fi
done
echo "  总计: $MISSING 个文件缺少 Architecture 头"

echo ""
echo "=========================================="
echo "检测完成"
echo "=========================================="
```

---

### 5. Ruff 配置推荐（pyproject.toml）

> **⚠️ 配置合并说明**：以下配置是**追加**到现有 `[tool.ruff]` 配置的，保留原有的 select 规则，只添加 `D` 和 `PI`。

**推荐配置（追加到现有配置）**：

```toml
# 在现有 [tool.ruff] 配置中追加以下内容：

[tool.ruff]
# 在原有 select 基础上追加 D 和 PI
select = ["E", "F", "I", "N", "W", "UP", "D", "PI"]  # 添加 D(pydocstyle) 和 PI(pep8-import)

# 在原有 ignore 基础上追加
extend-ignore = [
    # 原有 ignore 项...
    # Docstring 格式（允许灵活格式）
    "D200",   # 允许单行 docstring
    "D203",   # 允许类前无额外空行
    "D213",   # 允许多行 docstring 第二行在左侧
    "D215",   # 允许节 underline 超过内容
    # Naming（部分太严格）
    "N802",   # 方法名大小写（已有代码风格）
    "N803",   # 参数名大小写
]

[tool.ruff.pydocstyle]
convention = "google"  # 指定 Google 风格作为默认
```

**⚠️ pydoclint 需单独安装**：

pydoclint 不是项目依赖，需手动安装后使用：

```bash
poetry add --group dev pydoclint
poetry run pydoclint src/
```

---

### 6. 实施建议

**Phase 1: 接入工具 + 问题分析（1-2 天）**
1. 在 `pyproject.toml` 中追加 Ruff D 规则
2. 运行 `poetry run ruff check src/ --select=D > issues.txt`
3. 分析问题数量和分布（哪些文件/模块问题最多）

**Phase 2: 自动修复 + 分批修复计划（2-3 天）**
1. 使用 `ruff check --fix` 自动修复可修复问题（D200/D205/D400 等）
2. 评估 D417（缺少参数文档）数量，制定手动修复计划
3. 按模块分批修复（如 domain/entities → domain/services → infrastructure/config）

**Phase 3: 手动修复 D417（5-7 天，分批次）**
- D417 涉及大量现有方法，需要逐个补充 Args 文档
- 建议按优先级：domain 层 > application 层 > infrastructure 层

**Phase 4: CI 集成 + 监控（1 天）**
- 配置 GitHub Actions workflow（见上方 CI 配置示例）
- 设置增量检查（仅检查变更文件）

**⚠️ 注意事项**：
- 既有代码修复**不阻塞**新功能开发，新代码**必须遵守**规范
- D107（`__init__` 文档）和 D417（参数文档）验收渐进式推进
- 建议每修复一批文件后运行检测，确认问题减少

**验收标准（分阶段）**：

| 阶段 | 验收规则 | 说明 |
|------|----------|------|
| Phase 1 | D100, D101, D102, D103 | 模块/类/公共方法/函数文档缺失（ERROR） |
| Phase 2 | D107, D417 | `__init__` 文档 + 参数文档（新增代码强制，既有代码渐进修复） |

**Phase 1 验收命令**：
```bash
poetry run ruff check src/ --select=D100,D101,D102,D103 --output-format=short
# 期望：无 ERROR 输出
```

**Phase 2 验收命令**：
```bash
poetry run ruff check src/ --select=D100,D101,D102,D103,D107,D417 --output-format=short
# 期望：D100/D101/D102/D103 无 ERROR；D107/D417 允许有 WARNING（既有代码渐进修复）
# 新增代码必须通过 D100/D101/D102/D103/D107/D417 全部检查
```

**CI 配置（完整示例）**：
```yaml
# .github/workflows/docstring-check.yml
name: Docstring Check

on:
  push:
    paths: ['src/**/*.py']
  pull_request:
    paths: ['src/**/*.py']

jobs:
  ruff-docstring:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache pip packages
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/poetry.lock') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install --with dev

      - name: Run docstring checks (Phase 1)
        run: |
          poetry run ruff check src/ --select=D100,D101,D102,D103 --output-format=github

      - name: Run all docstring checks (Phase 2)
        run: |
          poetry run ruff check src/ --select=D100,D101,D102,D103,D107,D417 --output-format=github
        continue-on-error: true  # Phase 2 暂不阻塞，仅警告
```

---

## 七、推荐实践（业界最佳标准）

### 1. Google Python Docstring Style（推荐）

```python
def func(arg1, arg2):
    """Summary line.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.

    Returns:
        Description of return value.

    Raises:
        ExceptionType: Description of when exception is raised.
    """
```

### 2. Sphinx-compatible format（如需生成文档）

```python
def func(arg1, arg2):
    """Summary line.

    :param arg1: Description of arg1
    :type arg1: str
    :param arg2: Description of arg2
    :type arg2: int
    :returns: Description of return value
    :rtype: bool
    :raises ExceptionType: Description of when exception is raised
    """
```

### 3. 简化风格（仅用于简单方法）

```python
def func(arg1):
    """Do something with arg1.

    Short emphasis on what the method does without full documentation.
    """
```

---

## 八、评审检查清单

### 代码审查时检查注释规范

**文件头检查**：
- [ ] 文件头包含 `Architecture:` 字段，明确标注层级
- [ ] domain 层文件头包含 `Constraints: 领域层零外部依赖`
- [ ] 文件头包含 `References:` 引用（如有 ADR/Story/SDD）

**类 docstring 检查**：
- [ ] 公共类有 docstring（使用 Google 风格）
- [ ] 包含 `Attributes:` 说明（适用于 dataclass/实体类）
- [ ] 包含 `Raises:` 说明（如有抛出异常）

**方法 docstring 检查**：
- [ ] 公共方法有 docstring
- [ ] 包含 `Args:` 说明所有参数
- [ ] 包含 `Returns:` 说明返回值
- [ ] 包含 `Raises:` 说明可能抛出的异常

**特殊情况检查**：
- [ ] `__init__` 方法有 docstring（D107）
- [ ] `__post_init__` 方法有 docstring（手动补充）
- [ ] Protocol/抽象类有完整接口文档
- [ ] 异常类有 docstring 说明何时抛出

### CI 检查项

- [ ] Ruff D 规则已添加到 `pyproject.toml`
- [ ] GitHub Actions 配置了 docstring 检查
- [ ] Phase 1 验收通过（D100/D101/D102/D103 无 ERROR）
- [ ] 新代码 PR 必须通过 D100/D101/D102/D103 检查
