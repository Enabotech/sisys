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

## 六、批量修复工具

### 1. 检测脚本

```bash
#!/bin/bash
# 检测缺少标准文件头的模块
echo "=== 缺少标准文件头的文件 ==="
for f in $(find src -name "*.py" -type f); do
    if ! grep -q "Architecture:" "$f"; then
        echo "$f"
    fi
done

# 检测 Protocol 实现类无 docstring
echo "=== Protocol 实现类无 docstring ==="
grep -rn "class.*Impl\|class.*Async" src --include="*.py" | while read line; do
    file=$(echo "$line" | cut -d: -f1)
    class=$(echo "$line" | grep -oP "class \K[^:]+")
    # 检查下一行是否有 docstring
    line_num=$(echo "$line" | cut -d: -f2)
    next_line=$((line_num + 1))
    if ! sed -n "${next_line}p" "$file" | grep -q '"""'; then
        echo "$file: $class"
    fi
done
```

### 2. 修复脚本（示例）

```python
#!/usr/bin/env python3
"""注释标准化修复脚本."""

import re
from pathlib import Path

STANDARD_HEADER = '''"""{{module_name}} — {{description}}.

Architecture:
    Layer: {{layer}}
    Depends: {{depends}}
    Constraints: {{constraints}}

References:
{{references}}

Note:
    {{note}}
"""
'''

def fix_file_header(filepath: Path, layer: str, depends: str, constraints: str = ""):
    content = filepath.read_text()

    # 检查是否有标准文件头
    if "Architecture:" not in content:
        # 生成新的文件头
        module_name = filepath.stem
        description = content.split('"""')[1].split('\n')[0] if '"""' in content else "模块说明"

        new_header = f'''"""{module_name} — {description}.

Architecture:
    Layer: {layer}
    Depends: {depends}
    Constraints: {constraints}

Note:
    None
"""

'''
        # 替换现有文件头
        if content.startswith('"""'):
            end = content.find('"""', 3)
            content = new_header + content[end+3:]

        filepath.write_text(content)
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

## 八、实施建议

1. **优先修复 P0 问题**：Protocol 实现类、`__post_init__`、异常类
2. **统一风格**：建议 infrastructure 层使用英文，domain 层使用中文（保持领域术语一致性）
3. **添加 Architecture 信息**：所有文件头添加层和依赖说明
4. **批量修复**：使用脚本批量处理重复性问题
5. **Code Review 门槛**：将注释规范性纳入 PR review 检查清单
