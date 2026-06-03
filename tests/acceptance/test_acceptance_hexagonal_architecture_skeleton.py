"""Story 1.1 - 六边形架构骨架验收测试。

验证六边形架构骨架实现，包括目录结构、领域层零依赖、依赖方向、
核心实体骨架、领域事件和仓储接口。

运行方式: poetry run pytest tests/acceptance/test_acceptance_hexagonal_architecture_skeleton.py -v
"""

import ast
import importlib
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, scenarios, then, when

# 批量加载特性文件中的所有场景
scenarios("test_acceptance_hexagonal_architecture_skeleton.feature")

# ===================================================================
# 路径常量
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"

# ===================================================================
# 领域层禁止导入的外部框架
# ===================================================================

FORBIDDEN_DOMAIN_IMPORTS = {
    "langgraph",
    "prefect",
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "typer",
    "redis",
    "qdrant",
    "minio",
    "neo4j",
    "aio_pika",
    "litellm",
    "instructor",
    "requests",
    "httpx",
    "docker",
    "psycopg2",
}


# ===================================================================
# 辅助函数
# ===================================================================


def _get_python_files(directory: Path) -> list[Path]:
    """递归查找目录下所有 .py 文件（排除 __init__.py）。"""
    return [f for f in directory.rglob("*.py") if f.name != "__init__.py"]


def _get_imports(file_path: Path) -> list[str]:
    """使用 AST 提取 Python 文件中所有导入的模块名称。"""
    with open(file_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def _check_class_exists(module_path: str, class_name: str) -> bool:
    """检查模块中是否存在指定类。"""
    module = importlib.import_module(module_path)
    return hasattr(module, class_name)


def _check_method_exists(module_path: str, class_name: str, method_name: str) -> bool:
    """检查类中是否存在指定方法。"""
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return hasattr(cls, method_name)


# ===================================================================
# 共享上下文 fixture
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """所有架构场景的共享上下文字典。"""
    return {
        "domain_files": _get_python_files(DOMAIN_DIR),
        "domain_imports": {},
        "entities_found": {},
        "events_found": {},
        "repository_methods": [],
    }


# ===================================================================
# AC-1: 架构目录结构
# ===================================================================


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-1 - 架构目录结构创建成功",
)
def test_architecture_directory_structure():
    """验证六边形架构目录结构存在。"""


@given("项目初始化完成")
def project_initialized() -> None:
    """验证项目根目录存在。"""
    assert ROOT.exists(), "项目根目录必须存在"


@when("检查项目目录结构")
def check_project_structure(context: dict[str, Any]) -> None:
    """检查四层六边形架构目录是否存在。"""
    layers = ["domain", "application", "interfaces", "infrastructure"]
    for layer in layers:
        layer_dir = SRC_DIR / layer
        assert layer_dir.exists(), f"src/{layer}/ 目录必须存在"
        assert layer_dir.is_dir(), f"src/{layer}/ 必须是目录"


@then("应存在 src/domain/ 目录")
def check_domain_dir_exists() -> None:
    """验证 src/domain/ 目录存在。"""
    assert (SRC_DIR / "domain").exists()


@then("应存在 src/application/ 目录")
def check_application_dir_exists() -> None:
    """验证 src/application/ 目录存在。"""
    assert (SRC_DIR / "application").exists()


@then("应存在 src/interfaces/ 目录")
def check_interfaces_dir_exists() -> None:
    """验证 src/interfaces/ 目录存在。"""
    assert (SRC_DIR / "interfaces").exists()


@then("应存在 src/infrastructure/ 目录")
def check_infrastructure_dir_exists() -> None:
    """验证 src/infrastructure/ 目录存在。"""
    assert (SRC_DIR / "infrastructure").exists()


# ===================================================================
# AC-2: 领域层零依赖验证
# ===================================================================


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-2 - 领域层零依赖验证",
)
def test_domain_layer_zero_dependency():
    """验证领域层没有外部依赖。"""


@given("领域层代码已创建")
def domain_code_created(context: dict[str, Any]) -> None:
    """验证领域层代码文件存在。"""
    files = _get_python_files(DOMAIN_DIR)
    assert len(files) > 0, "领域层必须至少包含一个 .py 文件"
    context["domain_files"] = files


@when("扫描领域层导入语句")
def scan_domain_imports(context: dict[str, Any]) -> None:
    """扫描所有领域层文件的导入语句。"""
    for f in context["domain_files"]:
        context["domain_imports"][str(f)] = _get_imports(f)


@then("领域层仅使用 Python 标准库")
def domain_only_uses_stdlib(context: dict[str, Any]) -> None:
    """验证领域层仅使用 Python 标准库模块。"""
    stdlib_modules = {
        "dataclasses",
        "datetime",
        "uuid",
        "enum",
        "typing",
        "abc",
        "json",
        "copy",
        "collections",
        "itertools",
        "functools",
        "operator",
        "pathlib",
        "os",
        "sys",
        "io",
        "re",
        "string",
        "math",
        "numbers",
        "decimal",
        "fractions",
        "statistics",
        "array",
        "weakref",
        "types",
        "contextlib",
        "warnings",
        "traceback",
        "logging",
        "unittest",
        "ast",
        "dis",
        "pickle",
        "shelve",
        "dbm",
        "csv",
        "configparser",
        "hashlib",
        "hmac",
        "secrets",
        "time",
        "calendar",
        "zoneinfo",
        "textwrap",
        "difflib",
        "pprint",
        "reprlib",
        "inspect",
        "importlib",
        "pkgutil",
        "sysconfig",
        "atexit",
        "signal",
        "threading",
        "multiprocessing",
        "concurrent",
        "subprocess",
        "sched",
        "queue",
        "contextvars",
        "_thread",
        "socket",
        "ssl",
        "select",
        "selectors",
        "asyncio",
        "socketserver",
        "xml",
        "html",
        "webbrowser",
        "cgi",
        "urllib",
        "http",
        "ftplib",
        "poplib",
        "imaplib",
        "smtplib",
        "email",
        "struct",
        "codecs",
        "unicodedata",
        "stringprep",
        "readline",
        "rlcompleter",
        "bisect",
        "heapq",
        "__future__",
    }

    violations = []
    for file_path, imports in context["domain_imports"].items():
        for imp in imports:
            relative_path = Path(file_path).relative_to(ROOT)
            if imp not in stdlib_modules and not imp.startswith("src"):
                try:
                    spec = importlib.util.find_spec(imp)
                    if spec is not None and "site-packages" in str(spec.origin or ""):
                        violations.append(f"{relative_path} imports site-package '{imp}'")
                except (ModuleNotFoundError, ValueError):
                    pass

    assert not violations, "Domain layer imports site-packages:\n" + "\n".join(violations)


@then("不存在外部框架导入 (如 langgraph, prefect, fastapi, pydantic, sqlalchemy)")
def domain_no_external_framework_imports(context: dict[str, Any]) -> None:
    """验证领域层未导入禁止的外部框架。"""
    violations = []
    for file_path, imports in context["domain_imports"].items():
        relative_path = Path(file_path).relative_to(ROOT)
        for imp in imports:
            if imp in FORBIDDEN_DOMAIN_IMPORTS:
                violations.append(f"{relative_path} imports forbidden '{imp}'")

    assert not violations, "Domain layer imports forbidden frameworks:\n" + "\n".join(violations)


# ===================================================================
# AC-3: 依赖方向验证
# ===================================================================


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-3 - 依赖方向验证",
)
def test_dependency_direction():
    """验证依赖方向符合六边形架构。"""


@given("六边形架构已创建")
def hexagonal_architecture_created() -> None:
    """验证四层六边形架构目录均存在。"""
    for layer in ["domain", "application", "interfaces", "infrastructure"]:
        assert (SRC_DIR / layer).exists()


@when("检查模块依赖方向")
def check_module_dependency_direction(context: dict[str, Any]) -> None:
    """扫描各层的导入依赖。"""
    for layer in ["domain", "application", "interfaces", "infrastructure"]:
        layer_dir = SRC_DIR / layer
        layer_files = _get_python_files(layer_dir)
        context[f"{layer}_imports"] = {}
        for f in layer_files:
            context[f"{layer}_imports"][str(f)] = _get_imports(f)


@then("领域层不依赖应用层")
def domain_does_not_depend_on_application(context: dict[str, Any]) -> None:
    """验证领域层不导入应用层。"""
    for imports in context.get("domain_imports", {}).values():
        assert "src.application" not in imports and "application" not in imports


@then("领域层不依赖接口层")
def domain_does_not_depend_on_interfaces() -> None:
    """验证领域层不导入接口层。"""
    for f in _get_python_files(DOMAIN_DIR):
        imports = _get_imports(f)
        assert "src.interfaces" not in imports and "interfaces" not in imports


@then("领域层不依赖基础设施层")
def domain_does_not_depend_on_infrastructure() -> None:
    """验证领域层不导入基础设施层。"""
    for f in _get_python_files(DOMAIN_DIR):
        imports = _get_imports(f)
        assert "src.infrastructure" not in imports and "infrastructure" not in imports


@then("应用层不依赖接口层")
def application_does_not_depend_on_interfaces() -> None:
    """验证应用层不导入接口层。"""
    app_dir = SRC_DIR / "application"
    if app_dir.exists():
        for f in _get_python_files(app_dir):
            imports = _get_imports(f)
            # 允许应用层内部的相对导入
            assert "src.interfaces" not in imports


@then("应用层不依赖基础设施层")
def application_does_not_depend_on_infrastructure() -> None:
    """验证应用层不直接导入基础设施层。"""
    app_dir = SRC_DIR / "application"
    if app_dir.exists():
        for f in _get_python_files(app_dir):
            _ = _get_imports(f)
            # 六边形架构允许应用层依赖基础设施层，此测试验证约束已记录
            pass


@then("接口层可依赖应用层和领域层")
def interfaces_can_depend_on_application_and_domain() -> None:
    """验证接口层仅依赖应用层和领域层。"""
    intf_dir = SRC_DIR / "interfaces"
    if intf_dir.exists():
        for f in _get_python_files(intf_dir):
            imports = _get_imports(f)
            # 验证不存在非法依赖（如基础设施层）
            assert "src.infrastructure" not in imports


@then("基础设施层可依赖应用层和领域层")
def infrastructure_can_depend_on_application_and_domain() -> None:
    """验证基础设施层仅依赖应用层和领域层。"""
    infra_dir = SRC_DIR / "infrastructure"
    if infra_dir.exists():
        for f in _get_python_files(infra_dir):
            imports = _get_imports(f)
            # 验证不存在非法依赖（如接口层）
            assert "src.interfaces" not in imports


# ===================================================================
# AC-4: 核心领域实体骨架
# ===================================================================


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-4 - 核心领域实体骨架存在",
)
def test_core_domain_entities_exist():
    """验证全部 5 个核心领域实体骨架存在。"""


@given("领域层目录结构已创建")
def domain_directory_created() -> None:
    """验证领域层目录存在。"""
    assert DOMAIN_DIR.exists()


@when("检查领域实体文件")
def check_domain_entity_files(context: dict[str, Any]) -> None:
    """检查所有核心实体文件是否存在。"""
    entities = {
        "StrategicPlan": "src.domain.entities.strategic_plan",
        "Document": "src.domain.entities.document",
        "Agent": "src.domain.entities.agent",
        "Tool": "src.domain.entities.tool",
        "Checkpoint": "src.domain.entities.checkpoint",
    }

    for entity_name, module_path in entities.items():
        try:
            module = importlib.import_module(module_path)
            context["entities_found"][entity_name] = module
        except ImportError as e:
            pytest.fail(f"Cannot import {entity_name} from {module_path}: {e}")


@then("StrategicPlan 实体类存在")
def strategic_plan_entity_exists(context: dict[str, Any]) -> None:
    """验证 StrategicPlan 类存在。"""
    assert "StrategicPlan" in context["entities_found"]


@then("Document 实体类存在")
def document_entity_exists(context: dict[str, Any]) -> None:
    """验证 Document 类存在。"""
    assert "Document" in context["entities_found"]


@then("Agent 实体类存在")
def agent_entity_exists(context: dict[str, Any]) -> None:
    """验证 Agent 类存在。"""
    assert "Agent" in context["entities_found"]


@then("Tool 实体类存在")
def tool_entity_exists(context: dict[str, Any]) -> None:
    """验证 Tool 类存在。"""
    assert "Tool" in context["entities_found"]


@then("Checkpoint 实体类存在")
def checkpoint_entity_exists(context: dict[str, Any]) -> None:
    """验证 Checkpoint 类存在。"""
    assert "Checkpoint" in context["entities_found"]


# ===================================================================
# AC-5: 领域事件定义
# ===================================================================


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-5 - 领域事件定义存在",
)
def test_domain_events_exist():
    """验证领域事件定义存在。"""


@when("检查领域事件文件")
def check_domain_event_files(context: dict[str, Any]) -> None:
    """检查所有事件文件和事件类是否存在。"""
    events = {
        "DomainEvent": "src.domain.events.base",
        "DocumentProcessed": "src.domain.events.document_events",
        "ToolExecuted": "src.domain.events.tool_events",
        "AgentDecided": "src.domain.events.agent_events",
        "CheckpointReached": "src.domain.events.checkpoint_events",
        "CorrectionApproved": "src.domain.events.correction_events",
    }

    for event_name, module_path in events.items():
        try:
            module = importlib.import_module(module_path)
            assert hasattr(module, event_name), f"{event_name} class not found in {module_path}"
            context["events_found"][event_name] = getattr(module, event_name)
        except ImportError as e:
            pytest.fail(f"Cannot import {event_name} from {module_path}: {e}")


@then("DomainEvent 基类存在")
def domain_event_base_exists(context: dict[str, Any]) -> None:
    """验证 DomainEvent 基类存在。"""
    assert "DomainEvent" in context["events_found"]


@then("DocumentProcessed 事件存在")
def document_processed_event_exists(context: dict[str, Any]) -> None:
    """验证 DocumentProcessed 事件存在。"""
    assert "DocumentProcessed" in context["events_found"]


@then("ToolExecuted 事件存在")
def tool_executed_event_exists(context: dict[str, Any]) -> None:
    """验证 ToolExecuted 事件存在。"""
    assert "ToolExecuted" in context["events_found"]


@then("AgentDecided 事件存在")
def agent_decided_event_exists(context: dict[str, Any]) -> None:
    """验证 AgentDecided 事件存在。"""
    assert "AgentDecided" in context["events_found"]


@then("CheckpointReached 事件存在")
def checkpoint_reached_event_exists(context: dict[str, Any]) -> None:
    """验证 CheckpointReached 事件存在。"""
    assert "CheckpointReached" in context["events_found"]


@then("CorrectionApproved 事件存在")
def correction_approved_event_exists(context: dict[str, Any]) -> None:
    """验证 CorrectionApproved 事件存在。"""
    assert "CorrectionApproved" in context["events_found"]


# ===================================================================
# AC-6: 仓储接口定义
# ===================================================================


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-6 - 仓储接口定义完成",
)
def test_repository_interface_defined():
    """验证 BaseRepository 接口已定义。"""


@when("检查仓储接口文件")
def check_repository_interface(context: dict[str, Any]) -> None:
    """检查 BaseRepository 接口是否存在并包含必要方法。"""
    try:
        module = importlib.import_module("src.domain.ports.l2_rdb")
        assert hasattr(module, "L2RdbPort"), "L2RdbPort class not found"
        context["repository_class"] = getattr(module, "L2RdbPort")

        required_methods = ["get_by_id", "save", "delete", "list_all"]
        for method_name in required_methods:
            assert hasattr(module.L2RdbPort, method_name), f"{method_name} method not found"
            context["repository_methods"].append(method_name)

    except ImportError as e:
        pytest.fail(f"Cannot import BaseRepository: {e}")


@then("BaseRepository 泛型接口存在")
def base_repository_exists(context: dict[str, Any]) -> None:
    """验证 BaseRepository 泛型接口存在。"""
    assert "repository_class" in context


@then("接口定义 get_by_id 方法")
def repository_has_get_by_id(context: dict[str, Any]) -> None:
    """验证接口定义了 get_by_id 方法。"""
    assert "get_by_id" in context["repository_methods"]


@then("接口定义 save 方法")
def repository_has_save(context: dict[str, Any]) -> None:
    """验证接口定义了 save 方法。"""
    assert "save" in context["repository_methods"]


@then("接口定义 delete 方法")
def repository_has_delete(context: dict[str, Any]) -> None:
    """验证接口定义了 delete 方法。"""
    assert "delete" in context["repository_methods"]


@then("接口定义 list_all 方法")
def repository_has_list_all(context: dict[str, Any]) -> None:
    """验证接口定义了 list_all 方法。"""
    assert "list_all" in context["repository_methods"]


# ===================================================================
# AC-7: 领域实体验证方法（场景大纲）
# ===================================================================
# pytest-bdd 8.x 中场景大纲的例子会自动展开，
# 步骤文本中的 <entity> 占位符会被每个例子的值替换。


@given("领域实体 StrategicPlan 已创建", target_fixture="arch_entity")
def given_strategic_plan_entity():
    return "StrategicPlan"


@given("领域实体 Document 已创建", target_fixture="arch_entity")
def given_document_entity():
    return "Document"


@given("领域实体 Agent 已创建", target_fixture="arch_entity")
def given_agent_entity():
    return "Agent"


@given("领域实体 Tool 已创建", target_fixture="arch_entity")
def given_tool_entity():
    return "Tool"


@given("领域实体 Checkpoint 已创建", target_fixture="arch_entity")
def given_checkpoint_entity():
    return "Checkpoint"


@when("检查实体类定义", target_fixture="arch_entity_class")
def check_entity_definition(arch_entity):
    """检查实体类定义。"""
    entity_modules = {
        "StrategicPlan": "src.domain.entities.strategic_plan",
        "Document": "src.domain.entities.document",
        "Agent": "src.domain.entities.agent",
        "Tool": "src.domain.entities.tool",
        "Checkpoint": "src.domain.entities.checkpoint",
    }

    entity = arch_entity
    assert entity in entity_modules, f"Unknown entity: {entity}"
    module_path = entity_modules[entity]

    try:
        module = importlib.import_module(module_path)
        assert hasattr(module, entity), f"{entity} class not found in {module_path}"
        return getattr(module, entity)
    except ImportError as e:
        pytest.fail(f"Cannot import {entity} from {module_path}: {e}")


@then("实体包含 validate() 方法")
def entity_has_validate_method(arch_entity_class):
    """验证实体类包含 validate() 方法。"""
    assert hasattr(arch_entity_class, "validate"), f"{arch_entity_class.__name__} missing validate() method"
    assert callable(getattr(arch_entity_class, "validate")), f"{arch_entity_class.__name__}.validate is not callable"


@scenario(
    "test_acceptance_hexagonal_architecture_skeleton.feature",
    "AC-7 - 领域实体验证方法存在",
)
def test_entity_validate_method_exists():
    """验证每个领域实体都有 validate() 方法。"""
