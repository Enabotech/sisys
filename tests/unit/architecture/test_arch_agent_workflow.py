"""SDD 架构约束验证测试（Story 5-3 — 验证器 A-E）

六边形架构约束的静态验证（AST 扫描——test_langgraph_architecture.py 先例）：
- 验证器 A：domain 零外部依赖（chain_of_thought.py / task_evidence.py /
  agent_exceptions.py 禁 pydantic/langgraph 等外部导入）
- 验证器 B：图工厂依赖方向（infrastructure 图文件 import 白名单——
  application.ports.agent_workflow 合法 / application.services 实现类非法）
- 验证器 C：SAP 落位（src/interfaces/sap/ 存在 + message.py pydantic 可用 +
  domain 无 SAP 反向引用）
- 验证器 D：组合根外零实例化（LangGraphEngine / AgentWorkflowService 全仓
  AST 扫描禁业务代码直接实例化）
- 验证器 E：prompt 模块零 IO（agent_workflow_prompts / agent_workflow_context
  纯函数断言——禁 open/socket/requests/httpx 导入）
- 循环依赖检测：ruff/isort 承载（不引入 pylint）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_agent_workflow.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# 仓库根锚定（不依赖 cwd——tests/unit/architecture/ 下 4 层 parent）
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"

#: domain 零外部依赖红线——禁导入的顶层模块（验证器 A）
_FORBIDDEN_DOMAIN_IMPORTS = {
    "pydantic",
    "langgraph",
    "langchain",
    "prefect",
    "fastapi",
    "sqlalchemy",
    "redis",
    "neo4j",
    "qdrant",
    "minio",
    "litellm",
    "httpx",
    "requests",
}


def _scan_file_imports(file_path: Path) -> set[str]:
    """扫描文件顶层 import 的模块名集合（test_langgraph_architecture 先例形态）。"""
    if not file_path.exists():
        return set()
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue  # 相对导入是本地模块
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def _iter_python_files(directory: Path) -> list[Path]:
    """迭代目录下全部 .py 文件（排除 __pycache__）。"""
    return [f for f in directory.rglob("*.py") if "__pycache__" not in f.parts]


# ===================================================================
# 验证器 A：domain 零外部依赖
# ===================================================================


class TestValidatorADomainPurity:
    """验证器 A：本 Story 新增 domain 模块零外部依赖。"""

    @pytest.mark.parametrize(
        "domain_file",
        [
            "value_objects/chain_of_thought.py",
            "value_objects/task_evidence.py",
            "exceptions/agent_exceptions.py",
        ],
    )
    def test_new_domain_files_no_external_imports(self, domain_file: str) -> None:
        """新增 VO/异常文件禁 pydantic/langgraph 等外部导入。"""
        file_path = SRC_DIR / "domain" / domain_file
        assert file_path.exists(), f"文件缺失: {domain_file}"
        external = _scan_file_imports(file_path) - {"__future__", "typing", "dataclasses", "src", "uuid", "enum", "collections"}
        assert not external & _FORBIDDEN_DOMAIN_IMPORTS, f"{domain_file} 引入外部依赖: {external & _FORBIDDEN_DOMAIN_IMPORTS}"

    def test_domain_layer_no_pydantic_langgraph(self) -> None:
        """整个 domain 层禁 pydantic/langgraph（import-linter 红线的测试面冗余绊线）。"""
        domain_dir = SRC_DIR / "domain"
        for py_file in _iter_python_files(domain_dir):
            imports = _scan_file_imports(py_file)
            assert not imports & {"pydantic", "langgraph", "langchain"}, (
                f"{py_file.relative_to(REPO_ROOT)} 违反 domain 零外部依赖红线"
            )


# ===================================================================
# 验证器 B：图工厂依赖方向
# ===================================================================


class TestValidatorBGraphFactoryDependencies:
    """验证器 B：infrastructure 图文件 import 白名单（端口合法/实现类非法）。"""

    def test_graph_file_imports_application_port_only(self) -> None:
        """图工厂 import 白名单：application.ports.agent_workflow 合法；
        application.services 实现类非法（DC-1——编排与逻辑分离）。"""
        graph_file = SRC_DIR / "infrastructure" / "agent_orch" / "graphs" / "single_agent_workflow_graph.py"
        assert graph_file.exists(), "图工厂文件缺失"
        tree = ast.parse(graph_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("src.application.services"):
                    pytest.fail(f"图工厂禁止 import 应用层实现类: {node.module}")
                if node.module == "src.application.ports.agent_workflow":
                    continue  # 端口方向合法

    def test_engine_imports_port_not_service(self) -> None:
        """引擎对 workflow_service 的类型引用限端口（TYPE_CHECKING 下）。"""
        engine_file = SRC_DIR / "infrastructure" / "agent_orch" / "langgraph_engine.py"
        source = engine_file.read_text(encoding="utf-8")
        assert "from src.application.ports.agent_workflow import AgentWorkflowServicePort" in source, (
            "引擎应经端口类型引用工作流服务"
        )


# ===================================================================
# 验证器 C：SAP 落位
# ===================================================================


class TestValidatorCSapPlacement:
    """验证器 C：src/interfaces/sap/ 落位 + domain 无 SAP 反向引用。"""

    def test_sap_package_exists(self) -> None:
        """src/interfaces/sap/ 目录存在（architecture §13.5 钦定位）。"""
        sap_dir = SRC_DIR / "interfaces" / "sap"
        assert sap_dir.exists(), "src/interfaces/sap/ 目录缺失"
        assert (sap_dir / "message.py").exists()
        assert (sap_dir / "types.py").exists()

    def test_sap_message_uses_pydantic(self) -> None:
        """message.py pydantic 可用（interfaces 层 Pydantic 合规——BaseModel 子类断言）。"""
        import pydantic

        from src.interfaces.sap.message import SAPMessage

        # BaseModel 子类断言：可导入之外进一步锚定「Pydantic 模型」语义（退化为 dataclass 即红）
        assert issubclass(SAPMessage, pydantic.BaseModel)

    def test_domain_has_no_sap_reference(self) -> None:
        """domain 层无 SAP 反向引用（SAP 是接口层协议——依赖方向单向）。"""
        domain_dir = SRC_DIR / "domain"
        for py_file in _iter_python_files(domain_dir):
            source = py_file.read_text(encoding="utf-8")
            assert "interfaces.sap" not in source, f"{py_file} 反向引用 interfaces.sap（方向违例）"


# ===================================================================
# 验证器 D：组合根外零实例化
# ===================================================================


class TestValidatorDCompositionRootOnlyInstantiation:
    """验证器 D：LangGraphEngine/AgentWorkflowService 禁业务代码直接实例化。"""

    @pytest.mark.parametrize(
        "class_name,allowed_paths",
        [
            ("LangGraphEngine", {"src/composition_root.py"}),
            ("AgentWorkflowService", {"src/composition_root.py"}),
        ],
    )
    def test_no_direct_instantiation_outside_composition_root(self, class_name: str, allowed_paths: set[str]) -> None:
        """src/ AST 扫描：类实例化调用（Name/Attribute 为目标类名）仅允许
        组合根（业务代码禁直接 new——组装纪律；tests/ 不在扫描面，原
        "tests/" 白名单永不匹配——R1-F12 冗余清理）。"""
        violations: list[str] = []
        for py_file in _iter_python_files(SRC_DIR):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            if any(rel.startswith(allowed.rstrip("/")) for allowed in allowed_paths):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                target = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if target == class_name:
                    violations.append(rel)
        assert not violations, f"{class_name} 在组合根外被直接实例化: {violations}"


# ===================================================================
# 验证器 E：prompt 模块零 IO
# ===================================================================


class TestValidatorEPromptModulePure:
    """验证器 E：prompt/装配器模块零 IO（纯函数——禁 open/socket/网络导入）。"""

    @pytest.mark.parametrize(
        "module_file",
        [
            "application/services/agent_workflow_prompts.py",
            "application/services/agent_workflow_context.py",
        ],
    )
    def test_prompt_modules_no_io(self, module_file: str) -> None:
        """模块禁 IO 导入（open 内建不可静态禁——导入面足够：无 aiofiles/
        httpx/requests/socket/pathlib 读取调用面由纯函数形态保证）。"""
        file_path = SRC_DIR / module_file
        assert file_path.exists(), f"模块缺失: {module_file}"
        imports = _scan_file_imports(file_path)
        io_imports = {"aiofiles", "httpx", "requests", "socket", "asyncio"} & imports
        assert not io_imports, f"{module_file} 含 IO 导入: {io_imports}"

    def test_prompt_functions_pure(self) -> None:
        """prompt 构造函数是纯函数（同输入同输出——确定性抽查）。"""
        from src.application.services.agent_workflow_prompts import build_perceive_prompt

        first = build_perceive_prompt("任务 A")
        second = build_perceive_prompt("任务 A")
        assert first == second, "纯函数应确定性（同输入同输出）"
        assert "任务 A" in first


__all__ = [
    "TestValidatorADomainPurity",
    "TestValidatorBGraphFactoryDependencies",
    "TestValidatorCSapPlacement",
    "TestValidatorDCompositionRootOnlyInstantiation",
    "TestValidatorEPromptModulePure",
]
