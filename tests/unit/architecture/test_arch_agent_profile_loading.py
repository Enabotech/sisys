"""Story 5.2: 架构约束测试 — Agent 身份档案加载

验证（六边形架构四层约束 + 组合根唯一装配 + SkillSelector 无打分）：
1. 验证器 A——domain 零依赖 + 零 application import：5-2 涉及的 domain 三文件
   （agent_profile.py / agent_events.py / agent_exceptions.py）无第三方 import
   且无 src.application import（**本 Story 特有断言**：AgentProfile 不含
   ToolMetadata 的架构防线——ToolMetadata 属 application 层，domain 依赖
   application 违反方向矩阵，DC-7 分层裁定）
2. 验证器 B——依赖方向：MarkdownAgentProfileLoader 不 import application/
   interfaces（档案 Markdown 读取严格限定基础设施层）；agent_cli 不 import
   infrastructure；用例仅依赖 domain + application 端口
3. 验证器 C——组合根唯一装配：三个实现类（MarkdownAgentProfileLoader /
   SkillSelector / LoadAgentProfileUseCase）在 src/ 下仅 composition_root.py
   与自身定义文件出现实例化（AST Call 扫描——5-1 D9(c) AST 化先例）
4. 验证器 D——SkillSelector 无打分断言：selector.py 源码 AST 扫描不含
   排序/权重调用（sorted/score/weight 标识符零命中——GAP-CRITICAL-08b
   合规的机器验证）
5. 验证器 E——循环依赖检测用 ruff（--select I，不引入 pylint）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_agent_profile_loading.py -v
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "src"
REPO_ROOT = SRC_ROOT.parent

# Story 5.2 新增/修改的 domain 层文件
DOMAIN_FILES = [
    SRC_ROOT / "domain" / "value_objects" / "agent_profile.py",
    SRC_ROOT / "domain" / "events" / "agent_events.py",
    SRC_ROOT / "domain" / "exceptions" / "agent_exceptions.py",
]

# domain 层禁止导入的外部包（对齐 test_arch_agent_instantiation.py 黑名单口径）
FORBIDDEN_IMPORTS = {
    "pydantic",
    "sqlalchemy",
    "redis",
    "fastapi",
    "typer",
    "langgraph",
    "prefect",
    "qdrant",
    "minio",
    "neo4j",
    "aio_pika",
    "litellm",
    "instructor",
    "asyncpg",
    "aioredis",
    "httpx",
    "yaml",
    "dotenv",
}

# 实现类 → (定义模块, 类名)；组合根唯一装配断言用
IMPL_CLASSES = {
    "MarkdownAgentProfileLoader": SRC_ROOT / "infrastructure" / "agent_orch" / "markdown_agent_profile_loader.py",
    "SkillSelector": SRC_ROOT / "application" / "skills" / "registry" / "selector.py",
    "LoadAgentProfileUseCase": SRC_ROOT / "application" / "use_cases" / "agent_profile_loading.py",
}

# SkillSelector 无打分断言的禁用标识符（GAP-CRITICAL-08b：零排序/零打分/零 Top-K）
FORBIDDEN_SCORING_IDENTIFIERS = {"sorted", "sort", "score", "weight", "ranking", "top_k"}


def _extract_imports(file_path: Path) -> list[str]:
    """从 Python 文件提取全部 import 的点分模块路径（ast.walk 覆盖函数内延迟 import）。"""
    if not file_path.exists():
        return []
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.append(node.module)
    return imports


def _top_layer(module_path: str) -> str:
    """剥离可选 src. 前缀后的顶层包名。"""
    return module_path.removeprefix("src.").split(".")[0]


# ============================================================
# 验证器 A: domain 零依赖 + 零 application import（DC-7 架构防线）
# ============================================================


class TestDomainZeroDependencies:
    """5-2 涉及的 domain 文件零第三方依赖 + 零 src.application import。"""

    def test_all_domain_files_exist(self) -> None:
        for file_path in DOMAIN_FILES:
            assert file_path.exists(), f"domain 文件缺失: {file_path}"

    def test_domain_files_no_external_imports(self) -> None:
        """domain 三文件无 FORBIDDEN_IMPORTS 黑名单命中（AST 扫描含延迟 import）。"""
        violations: list[str] = []
        for file_path in DOMAIN_FILES:
            for module_path in _extract_imports(file_path):
                if _top_layer(module_path) in FORBIDDEN_IMPORTS:
                    violations.append(f"{file_path.name}: {module_path}")
        assert not violations, f"domain 层第三方依赖违规: {violations}"

    def test_domain_files_no_application_import(self) -> None:
        """domain 三文件零 src.application import（AgentProfile 不含 ToolMetadata 的根因防线——DC-7）。"""
        violations: list[str] = []
        for file_path in DOMAIN_FILES:
            for module_path in _extract_imports(file_path):
                top = _top_layer(module_path)
                if module_path.startswith("src.application") or (top == "application" and module_path != "application"):
                    violations.append(f"{file_path.name}: {module_path}")
        assert not violations, f"domain 层 application import 违规（方向矩阵 domain ✗→ application）: {violations}"

    def test_agent_profile_imports_only_stdlib_and_domain(self) -> None:
        """agent_profile.py 仅标准库 + src.domain import（白名单式收紧断言）。"""
        allowed_stdlib = {"uuid", "dataclasses", "__future__"}
        file_path = DOMAIN_FILES[0]
        for module_path in _extract_imports(file_path):
            if module_path.startswith("src."):
                assert module_path.startswith("src.domain"), f"越层 import: {module_path}"
            else:
                assert module_path in allowed_stdlib, f"非白名单 import: {module_path}"


# ============================================================
# 验证器 B: 依赖方向（infrastructure/application/entrypoints 边界）
# ============================================================


class TestDependencyDirection:
    """MarkdownAgentProfileLoader / agent_cli / 用例的依赖方向合规。"""

    def test_profile_loader_no_application_or_interfaces_import(self) -> None:
        """MarkdownAgentProfileLoader 不 import application/interfaces（档案读取限定基础设施层）。

        注：端口 Protocol（AgentProfileLoader）位于 application.ports——实现类
        显式继承端口需要 import 该 Protocol，这是六边形架构的合法方向
        （infrastructure → application 端口）；本断言禁止的是业务语义依赖
        （application.use_cases / application.skills / interfaces.*）。
        """
        loader_path = IMPL_CLASSES["MarkdownAgentProfileLoader"]
        for module_path in _extract_imports(loader_path):
            if module_path.startswith("src."):
                top_layers = module_path.removeprefix("src.").split(".")
                if top_layers[0] == "application":
                    assert top_layers[1] == "ports", f"infrastructure 越层依赖 application 业务模块: {module_path}"
                else:
                    assert top_layers[0] in ("domain",), f"infrastructure 越层依赖: {module_path}"
            elif _top_layer(module_path) == "interfaces":
                raise AssertionError(f"infrastructure 依赖 interfaces: {module_path}")

    def test_agent_cli_no_infrastructure_import(self) -> None:
        """agent_cli 不 import infrastructure（入口层经组合根解析，不触碰实现）。"""
        cli_path = SRC_ROOT / "entrypoints" / "agent_cli.py"
        for module_path in _extract_imports(cli_path):
            if module_path.startswith("src."):
                top = module_path.removeprefix("src.").split(".")[0]
                assert top != "infrastructure", f"CLI 依赖 infrastructure: {module_path}"
            else:
                assert _top_layer(module_path) != "infrastructure"

    def test_use_case_only_domain_and_application_imports(self) -> None:
        """用例仅依赖 domain + application（端口/用例内模块）。"""
        use_case_path = IMPL_CLASSES["LoadAgentProfileUseCase"]
        for module_path in _extract_imports(use_case_path):
            if module_path.startswith("src."):
                top = module_path.removeprefix("src.").split(".")[0]
                assert top in ("domain", "application"), f"用例越层依赖: {module_path}"
            else:
                assert _top_layer(module_path) not in FORBIDDEN_IMPORTS, f"用例第三方依赖: {module_path}"


# ============================================================
# 验证器 C: 组合根唯一装配（AST Call 扫描）
# ============================================================


class TestCompositionRootOnlyAssembly:
    """三个实现类在 src/ 下仅自身定义文件与 composition_root.py 出现实例化。"""

    def test_impl_classes_instantiated_only_in_composition_root(self) -> None:
        composition = SRC_ROOT / "composition_root.py"
        assert composition.exists()
        for cls_name, definition in IMPL_CLASSES.items():
            assert definition.exists(), f"实现文件不存在: {definition}"
            # 全 src 扫描类名实例化（AST Call 扫描——func 名或属性名命中类名；
            # 覆盖直接调用 Cls(...) 与 __import__(...).Cls(...) 形态，且不受
            # docstring/注释文本与前缀同类名（FakeXxx(Cls)）的子串误报影响）
            offenders: list[str] = []
            for py_file in SRC_ROOT.rglob("*.py"):
                if py_file == definition or py_file == composition:
                    continue
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Name):
                            target = func.id
                        elif isinstance(func, ast.Attribute):
                            target = func.attr
                        else:
                            target = None
                        if target == cls_name:
                            offenders.append(str(py_file.relative_to(SRC_ROOT)))
                            break
            assert not offenders, f"{cls_name} 在组合根外被实例化: {offenders}"

    def test_composition_root_registers_all_three(self) -> None:
        source = (SRC_ROOT / "composition_root.py").read_text(encoding="utf-8")
        for cls_name in IMPL_CLASSES:
            assert cls_name in source, f"组合根未装配 {cls_name}"
        for port_name in ('"agent_profile_loader"', '"skill_selector"', '"agent_profile_use_case"'):
            assert port_name in source, f"组合根未注册端口 {port_name}"


# ============================================================
# 验证器 D: SkillSelector 无打分断言（GAP-CRITICAL-08b 机器验证）
# ============================================================


class TestSkillSelectorNoScoring:
    """selector.py 源码零排序/零打分标识符（关键词 40%+语义 60% 融合已废弃——D-1）。"""

    def test_no_scoring_identifiers_in_selector(self) -> None:
        """AST 扫描：sorted/score/weight/ranking/top_k 标识符零命中（Name/Attribute/函数定义全覆盖）。"""
        selector_path = IMPL_CLASSES["SkillSelector"]
        tree = ast.parse(selector_path.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_SCORING_IDENTIFIERS:
                offenders.append(f"L{node.lineno}: Name {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_SCORING_IDENTIFIERS:
                offenders.append(f"L{node.lineno}: Attribute .{node.attr}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FORBIDDEN_SCORING_IDENTIFIERS:
                offenders.append(f"L{node.lineno}: def {node.name}")
        assert not offenders, f"SkillSelector 含排序/打分代码（GAP-CRITICAL-08b 违规）: {offenders}"

    def test_selector_returns_in_slug_order(self) -> None:
        """返回序与 slug 清单一致的结构性验证：源码含 get_all_slugs 枚举且无 reverse 参数。"""
        source = IMPL_CLASSES["SkillSelector"].read_text(encoding="utf-8")
        assert "get_all_slugs()" in source, "SkillSelector 应以 get_all_slugs() 为枚举真源"
        assert "reverse" not in source, "枚举遍历不应引入反向参数（稳定序契约）"


# ============================================================
# 验证器 E: 循环依赖检测（ruff isort，不引入 pylint）
# ============================================================


class TestNoCircularImports:
    """ruff --select I 循环依赖检测（subprocess，不引入额外工具）。"""

    def test_ruff_isort_passes(self) -> None:
        targets = [
            str(IMPL_CLASSES["MarkdownAgentProfileLoader"]),
            str(IMPL_CLASSES["SkillSelector"]),
            str(IMPL_CLASSES["LoadAgentProfileUseCase"]),
            str(SRC_ROOT / "entrypoints" / "agent_cli.py"),
        ]
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select", "I", *targets],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"循环依赖/import 顺序违规:\n{result.stdout}"
