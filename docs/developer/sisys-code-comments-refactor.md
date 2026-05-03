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
    Depends: <允许的外部依赖（仅 domain 层需声明标准库）>
    Constraints: <特殊约束或限制>

References:
    - ADR-<N>: <决策标题>
    - Story <ID>: <故事标题>
    - SDD §<section>: <架构文档章节>

Note:
    <重要说明、P0 约束、或暂时未实现的功能>
"""
```

**示例（domain 层）：**

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

**示例（infrastructure 层）：**

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
    """<职责简述>.

    使用场景: <何时使用、如何创建实例>

    与其他组件的关系:
        - 依赖: <依赖的组件>
        - 被依赖: <依赖此类的组件>

    状态机/约束: <如适用>

    Attributes:
        <attr1>: <类型> — <描述>
        <attr2>: <类型> — <描述>

    Raises:
        <Exception>: <何时抛出>
    """
```

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
class <ServiceName>Protocol(Protocol):
    """<服务接口名称> — <接口职责>.

    此接口定义 <服务> 的核心操作契约。
    实现类必须满足此接口定义的所有方法语义。

    Args:
        <common_init_args>: <类型> — <描述>

    Methods:
        <method_name>(<args>) -> <return_type>:
            <方法职责一句话>
    """
```

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
# 检测缺少标准文件头的模块
echo "=== 缺少标准文件头的文件 (检查 Architecture: 关键字) ==="
for f in $(find src -name "*.py" -type f); do
    if ! grep -q "Architecture:" "$f"; then
        echo "$f"
    fi
done
```

#### 检测文档缺失（D100-D107）

```bash
#!/bin/bash
echo "=== 缺少文档的公共定义 ==="
poetry run ruff check src/ --select=D100,D101,D102,D103,D104,D105,D106,D107

echo "=== 缺少参数文档的方法 ==="
poetry run ruff check src/ --select=D417
```

#### 检测 docstring 格式问题

```bash
#!/bin/bash
echo "=== docstring 格式问题 ==="
poetry run ruff check src/ --select=D200,D201,D202,D203,D204,D205 --output-format=text

echo "=== 内容规范问题 ==="
poetry run ruff check src/ --select=D400,D401,D402,D403 --output-format=text
```

#### 综合检测脚本

```bash
#!/bin/bash
# sisys 代码注释综合检测脚本

set -e

echo "=========================================="
echo "sisys 代码注释规范性检测"
echo "=========================================="

# 1. 检查缺少文档的公共定义
echo ""
echo "[1/5] 检查缺少文档的公共定义..."
poetry run ruff check src/ --select=D100,D101,D102,D103,D104,D105,D106,D107 --output-format=short 2>/dev/null || true

# 2. 检查缺少 __init__ 文档
echo ""
echo "[2/5] 检查缺少 __init__ 文档..."
poetry run ruff check src/ --select=D107 --output-format=short 2>/dev/null || true

# 3. 检查缺少参数文档
echo ""
echo "[3/5] 检查缺少参数文档..."
poetry run ruff check src/ --select=D417 --output-format=short 2>/dev/null || true

# 4. 检查 docstring 格式问题
echo ""
echo "[4/5] 检查 docstring 格式问题..."
poetry run ruff check src/ --select=D200,D201,D202,D203,D204,D205,D400,D401 --output-format=short 2>/dev/null || true

# 5. 检查缺少标准文件头（无 Architecture 关键字）
echo ""
echo "[5/5] 检查缺少标准文件头..."
for f in $(find src -name "*.py" -type f); do
    if ! grep -q "Architecture:" "$f"; then
        echo "  MISSING: $f"
    fi
done

echo ""
echo "=========================================="
echo "检测完成"
echo "=========================================="
```

---

### 5. Ruff 配置推荐（pyproject.toml）

```toml
# ============================================
# sisys - Ruff 配置
# ============================================

[tool.ruff]
line-length = 128
target-version = "py311"

# 启用规则
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "W",    # pycodestyle warnings
    "UP",   # pyupgrade
    "D",    # pydocstyle (docstring)
    "PI",   # pep8-impiort (，禁止绝对导入)
]

# 忽略规则
ignore = [
    # Docstring 格式（允许灵活格式）
    "D200",   # 允许单行 docstring
    "D203",   # 允许类前无额外空行
    "D213",   # 允许多行 docstring 第二行在左侧
    "D215",   # 允许节 underline 超过内容
    # Naming（部分太严格）
    "N802",   # 方法名大小写（已有代码风格）
    "N803",   # 参数名大小写
]

# 排除目录
extend-exclude = [
    ".claude/",
    ".qwen/",
    "_bmad/",
    ".git/",
    "__pycache__/",
    "*.egg-info/",
    ".venv/",
    "venv/",
]

[tool.ruff.pydocstyle]
convention = "google"  # 指定 Google 风格作为默认
```

---

### 6. 实施建议

**Phase 1: 接入工具（1 天）**
1. 在 `pyproject.toml` 中添加 Ruff D 规则
2. 运行 `poetry run ruff check src/ --select=D > issues.txt`
3. 评估问题数量和严重性

**Phase 2: 批量修复（2-3 天）**
1. 使用 `ruff check --fix` 自动修复可修复问题
2. 手动修复 D417（缺少参数文档）
3. 补充缺失的 docstring

**Phase 3: CI 集成**
```yaml
# .github/workflows/lint.yml
- name: Run Ruff docstring checks
  run: poetry run ruff check src/ --select=D --output-format=github
```

**验收标准**：
- ✅ `ruff check src/ --select=D100,D101,D102,D103,D107,D417` 无输出
- ✅ 所有公共模块/类/方法有文档
- ✅ 所有参数有 Args 说明
- ✅ 所有 Returns/Raises 有说明

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

## 八、实施建议

1. **优先修复 P0 问题**：Protocol 实现类、`__post_init__`、异常类
2. **统一风格**：建议 infrastructure 层使用英文，domain 层使用中文（保持领域术语一致性）
3. **添加 Architecture 信息**：所有文件头添加层和依赖说明
4. **批量修复**：使用脚本批量处理重复性问题
5. **Code Review 门槛**：将注释规范性纳入 PR review 检查清单
