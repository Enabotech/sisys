"""SDD 架构约束验证：Story 5.11 SAP 协议（接口层横向协议落位与依赖方向守护）。

三验证器（test_arch_checkpoint_evaluation.py helper 先例——REPO_ROOT + AST 扫描 +
词边界正则 + 参数化）：
- A：bus.py 第三方 import 白名单 {pydantic}（标准库 sys.stdlib_module_names 天然过）
- B：组合根外零实例化 + domain 触碰面收窄 + events 零触碰（SAP 非领域事件）+
  依赖方向（application/infrastructure 零 import interfaces.sap——与
  test_arch_agent_workflow.py 既有 domain 守护互补）
- C：bus.py 静态锚（Protocol 四方法 + runtime_checkable + blackboard_visible 分支 +
  ensure_agent_access 调用 + version==0 检测）+ 零抑制注释

Run with:
    poetry run pytest tests/unit/architecture/test_arch_sap_protocol.py -v
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

# 仓库根锚定（不依赖 cwd——tests/unit/architecture/ 下 4 层 parent）
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"

BUS_FILE = SRC_DIR / "interfaces" / "sap" / "bus.py"
SAP_EXCEPTIONS_FILE = SRC_DIR / "domain" / "exceptions" / "sap_exceptions.py"
COMPOSITION_ROOT_FILE = SRC_DIR / "composition_root.py"
CONTRACT_TEST_FILE = REPO_ROOT / "tests" / "contracts" / "test_port_contract_sap_bus.py"

#: 验证器 A 白名单（SAPMessage 同文件族——pydantic 合法；asyncio/inspect/logging/uuid
#: 等标准库经 sys.stdlib_module_names 天然放行）
_ALLOWED_THIRD_PARTY = {"pydantic"}

#: 验证器 C 交付文件四件（零抑制注释红线）
_SUPPRESSION_DELIVERY_FILES = [
    BUS_FILE,
    SAP_EXCEPTIONS_FILE,
    COMPOSITION_ROOT_FILE,
    CONTRACT_TEST_FILE,
]


def _scan_file_top_imports(path: Path) -> set[str]:
    """扫描文件 import 模块名集合（Import/ImportFrom 取首段——相对导入跳过）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def _scan_instantiation_sites(target_class: str) -> list[str]:
    """扫描 src/ 全目录构造点（返回 repo 相对路径:行号 清单——ast.Name/Attribute 双形态）。"""
    sites: list[str] = []
    for py_file in SRC_DIR.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if name == target_class:
                    sites.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}")
    return sites


def _iter_python_files(directory: Path) -> list[Path]:
    """迭代目录下全部 .py 文件（排除 __pycache__）。"""
    return [f for f in directory.rglob("*.py") if "__pycache__" not in f.parts]


# ==== 验证器 A：bus.py 第三方 import 白名单 ====


class TestValidatorAThirdPartyWhitelist:
    """bus.py 第三方 import 白名单 {pydantic}（零新运行时依赖——5.7 OD-1 家族原则）。"""

    def test_bus_file_exists(self) -> None:
        """bus.py 存在（architecture L2172 规划钦定位兑现）。"""
        assert BUS_FILE.exists(), "src/interfaces/sap/bus.py 缺失"

    def test_no_forbidden_third_party(self) -> None:
        """黑名单断言：非标准库非本仓 import ∩ 白名单外 == ∅。"""
        modules = _scan_file_top_imports(BUS_FILE)
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= _ALLOWED_THIRD_PARTY, f"bus.py 出现白名单外第三方依赖: {non_stdlib - _ALLOWED_THIRD_PARTY}"

    def test_stdlib_only_baseline(self) -> None:
        """当前基线：纯标准库 + 本仓 import（pydantic 允许但未消费——SAPMessage 同族隔离）。"""
        modules = _scan_file_top_imports(BUS_FILE)
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"当前交付形态应零第三方直接依赖，实际 {non_stdlib}"


# ==== 验证器 B：实例化收窄 + domain 触碰面 + events 零触碰 + 依赖方向 ====


class TestValidatorBInstantiationAndDependencies:
    """组合根外零实例化 + SAP 异常定义点收窄 + events 零触碰 + 依赖方向单向。"""

    def test_inprocess_sap_bus_instantiation_only_in_composition_root(self) -> None:
        """InProcessSAPBus 构造点仅 composition_root.py（组合根唯一注册纪律）。"""
        sites = _scan_instantiation_sites("InProcessSAPBus")
        src_sites = [s for s in sites if not s.startswith("tests/")]
        assert all(s.startswith("src/composition_root.py") for s in src_sites), (
            f"组合根外出现 InProcessSAPBus 实例化: {src_sites}"
        )
        assert src_sites, "composition_root.py 应至少一处实例化（_build_sap_bus 工厂）"

    @pytest.mark.parametrize(
        "exception_class",
        ["SAPTimeoutError", "SAPBusStateError", "SAPBlackboardWriteError"],
    )
    def test_sap_exception_defined_only_in_registry(self, exception_class: str) -> None:
        """SAP 异常类定义仅在注册三件内的 sap_exceptions.py（唯一真源）。"""
        pattern = rf"^class {exception_class}\b"
        definition_files = [
            str(py_file.relative_to(REPO_ROOT))
            for py_file in _iter_python_files(SRC_DIR)
            if re.search(pattern, py_file.read_text(encoding="utf-8"), re.MULTILINE)
        ]
        assert definition_files == ["src/domain/exceptions/sap_exceptions.py"], (
            f"{exception_class} 应仅在 sap_exceptions.py 定义，实际 {definition_files}"
        )

    def test_event_channels_yaml_zero_sap_entries(self) -> None:
        """event_channels.yaml 零 SAP 条目（SAP 非领域事件——不进事件通道体系）。"""
        yaml_path = REPO_ROOT / "configs" / "event_channels.yaml"
        content = yaml_path.read_text(encoding="utf-8")
        assert "sap" not in content.lower(), "event_channels.yaml 不应出现 SAP 条目"

    def test_channel_router_zero_sap_references(self) -> None:
        """ChannelRouter 零 SAP 引用（5-3 职责边界钉死）。"""
        router_candidates = list((SRC_DIR / "application").rglob("*channel_router*.py")) + list(
            (SRC_DIR / "infrastructure").rglob("*channel_router*.py")
        )
        for router_file in router_candidates:
            content = router_file.read_text(encoding="utf-8").lower()
            assert "sap" not in content, f"{router_file} 出现 SAP 引用（职责边界违例）"

    def test_domain_events_zero_sap_references(self) -> None:
        """domain/events/ 零 SAP 引用（SAPMessage 非 DomainEvent）。"""
        events_dir = SRC_DIR / "domain" / "events"
        for py_file in _iter_python_files(events_dir):
            content = py_file.read_text(encoding="utf-8").lower()
            assert "sap" not in content, f"{py_file} 出现 SAP 引用（SAP 非领域事件违例）"

    def test_bus_imports_application_ports_legal(self) -> None:
        """依赖方向：bus.py import application.ports 合法（interfaces→application 单向）。"""
        source = BUS_FILE.read_text(encoding="utf-8")
        assert "from src.application.ports.public_blackboard import" in source, "应组合注入 PublicBlackboard"
        assert "from src.application.ports.isolation_guard import" in source, "应组合注入 IsolationGuardPort"

    def test_application_and_infrastructure_zero_sap_import(self) -> None:
        """application/infrastructure 零 import interfaces.sap（依赖方向单向守护——与
        test_arch_agent_workflow.py 的 domain 守护互补成三层全覆盖）。"""
        for layer in ("application", "infrastructure"):
            for py_file in _iter_python_files(SRC_DIR / layer):
                source = py_file.read_text(encoding="utf-8")
                assert "interfaces.sap" not in source, (
                    f"{py_file} 反向 import interfaces.sap（依赖方向违例——SAP 是接口层横向协议）"
                )


# ==== 验证器 C：bus.py 静态锚 + 零抑制注释 ====


class TestValidatorCStaticAnchors:
    """bus.py 静态锚（Protocol 四方法 + 装饰器 + 黑板桥三锚）+ 零抑制注释。"""

    def test_sap_bus_protocol_runtime_checkable(self) -> None:
        """SAPBus Protocol 存在 + @runtime_checkable 装饰（契约测试 isinstance 判别锚）。"""
        source = BUS_FILE.read_text(encoding="utf-8")
        assert "@runtime_checkable" in source, "SAPBus 应 @runtime_checkable"
        tree = ast.parse(source)
        protocol_methods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "SAPBus":
                for item in node.body:
                    if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)):
                        protocol_methods.add(item.name)
        assert protocol_methods == {"send", "subscribe", "wait_for_response", "close"}, (
            f"SAPBus Protocol 方法面应为四方法，实际 {protocol_methods}"
        )

    def test_blackboard_visible_branch_anchor(self) -> None:
        """黑板桥静态锚：blackboard_visible 条件分支存在（可见性开关是写入唯一闸门）。"""
        source = BUS_FILE.read_text(encoding="utf-8")
        assert "if message.blackboard_visible:" in source, "blackboard_visible 条件分支缺失"

    def test_guard_call_anchor(self) -> None:
        """守卫静态锚：ensure_agent_access 调用存在（§7.6 V1 RBAC+隔离等级承载）。"""
        source = BUS_FILE.read_text(encoding="utf-8")
        assert "ensure_agent_access" in source, "ensure_agent_access 守卫调用缺失"
        assert "IsolationResource.BLACKBOARD" in source, "守卫 resource 应为 BLACKBOARD"
        assert "AccessOperation.WRITE" in source, "守卫 operation 应为 WRITE"

    def test_version_zero_detection_anchor(self) -> None:
        """fail-loud 静态锚：version == 0 检测存在（OD-7 post 返 0 检测点）。"""
        source = BUS_FILE.read_text(encoding="utf-8")
        assert "if version == 0:" in source, "version==0 检测缺失（fail-loud OD-7）"

    def test_priority_queue_anchor(self) -> None:
        """优先级静态锚：_PRIORITY_RANK 出队序表存在（四级优先级协议语义）。"""
        source = BUS_FILE.read_text(encoding="utf-8")
        assert "_PRIORITY_RANK" in source, "优先级出队序表缺失"

    @pytest.mark.parametrize(
        "delivery_file",
        _SUPPRESSION_DELIVERY_FILES,
        ids=[p.name for p in _SUPPRESSION_DELIVERY_FILES],
    )
    def test_zero_suppression_comments(self, delivery_file: Path) -> None:
        """零抑制注释红线（交付文件四件——noqa/type: ignore/pylint: disable 零命中）。"""
        source = delivery_file.read_text(encoding="utf-8")
        for marker in ("# noqa", "# type: ignore", "# pylint: disable"):
            assert marker not in source, f"{delivery_file} 含抑制注释 {marker!r}（红线）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
