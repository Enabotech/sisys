"""PhoenixTracer 架构约束验证测试（Story 5.7 — Task 5：SDD 架构约束验证）

三验证器（test_arch_isolation_switch_log 同款形态——REPO_ROOT + 目标文件常量 +
AST 扫描 helper + 参数化验证器类）：
A. application 触碰文件第三方 import 白名单（本 Story 新建 application 第三方
   防线——importlinter 只限层间方向不限第三方；允许 opentelemetry[DC-3：应用
   侧手动插桩标准 API 包]，黑名单取 domain 契约同款清单）；
B. domain 零触碰（本 Story 新增符号 grep 零命中 + domain 零 import opentelemetry）
   + 组合根外零实例化（PhoenixTracer( 构造点仅组合根）；
C. 装饰器静态锚（六阶段 + execute 方法 __wrapped__ 在位）+ 构造签名不变
   （R3-14：「纯附加装饰」具体化为 inspect.signature 对照 5-3 基线）。

Run with:
    poetry run pytest tests/unit/architecture/test_arch_phoenix_tracer.py -v
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

# 验证器 A 目标文件（application 层——本 Story 触碰面；ports/__init__.py 聚合
# 导出也是触碰文件——R3-12）
_APPLICATION_TARGET_FILES = [
    SRC_DIR / "application" / "tracing.py",
    SRC_DIR / "application" / "ports" / "agent_tracing.py",
    SRC_DIR / "application" / "ports" / "__init__.py",
    SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
    SRC_DIR / "application" / "services" / "agent_workflow_service.py",
]

#: application 层允许的第三方顶层模块（DC-3：application 只碰 opentelemetry
#: API 包——与 logging 同级定位的横切标准 API；SDK 归 infrastructure）
_APPLICATION_ALLOWED_THIRD_PARTY = {"opentelemetry"}

#: 第三方黑名单（domain 契约同款清单——重依赖/框架型包禁入 application）
_APPLICATION_FORBIDDEN_IMPORTS = {
    "pydantic",
    "fastapi",
    "sqlalchemy",
    "redis",
    "typer",
    "langgraph",
    "prefect",
    "yaml",
    "minio",
    "qdrant",
    "neo4j",
}

#: 本 Story 新增符号（domain 零触碰断言锚——grep 在 src/domain/ 零命中）
_STORY57_SYMBOLS = (
    "PhoenixTracer",
    "PhoenixConfig",
    "AgentTracingPort",
    "SpanAttributeKeys",
    "SpanNames",
    "PHOENIX_TRACING_ENABLED",
    "PHOENIX_OTLP_ENDPOINT",
    "PHOENIX_PROJECT_NAME",
    "PHOENIX_TRACES_SAMPLER_ARG",
)

#: 构造签名基线（R3-14——5-3 基线清单，「装饰器纯附加零构造签名变化」具体化）
_SERVICE_INIT_PARAMS = [
    "llm_client",
    "tool_execution_service",
    "skill_loader",
    "tool_registry_service",
    "isolation_guard",
    "per_call_timeout_sec",
    "base_config",
]
_USE_CASE_INIT_PARAMS = [
    "agent_repository",
    "agent_profile_use_case",
    "agent_engine",
    "agent_workflow_service",
    "isolation_guard",
]

#: 六阶段方法名（验证器 C——package_evidence 方法名 + span 名末段 package 的
#: 分工：span 名对齐 executed_phases 枚举）
_SIX_PHASE_METHODS = ("perceive", "plan", "execute", "verify", "reflect", "package_evidence")


def _scan_file_imports(path: Path) -> set[str]:
    """AST 扫描文件全部 import（ast.walk 覆盖函数内延迟 import）——顶层模块名集合."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
            # from . import xxx 相对导入（node.module None）——level>=1 属同层
    return modules


def _scan_instantiation_sites(class_name: str) -> list[str]:
    """AST 扫描 src/ 全目录的类实例化点（相对路径:行号）。"""
    violations: list[str] = []
    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if name == class_name:
                    violations.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}")
    return violations


class TestValidatorAApplicationThirdPartyWhitelist:
    """验证器 A：application 触碰文件第三方 import 白名单（opentelemetry 允许）."""

    @pytest.mark.parametrize("target", _APPLICATION_TARGET_FILES, ids=[p.name for p in _APPLICATION_TARGET_FILES])
    def test_no_forbidden_third_party_imports(self, target: Path) -> None:
        """黑名单断言：pydantic/fastapi/sqlalchemy/redis 等禁入 application 触碰文件."""
        imports = _scan_file_imports(target)
        assert imports & _APPLICATION_FORBIDDEN_IMPORTS == set(), (
            f"{target.name} 禁入第三方 import: {imports & _APPLICATION_FORBIDDEN_IMPORTS}"
        )

    @pytest.mark.parametrize("target", _APPLICATION_TARGET_FILES, ids=[p.name for p in _APPLICATION_TARGET_FILES])
    def test_third_party_only_opentelemetry(self, target: Path) -> None:
        """白名单断言：非标准库第三方仅 opentelemetry（标准库经 sys 精确判定）."""
        import sys

        imports = _scan_file_imports(target)
        non_stdlib = {m for m in imports if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= _APPLICATION_ALLOWED_THIRD_PARTY, (
            f"{target.name} 白名单外第三方: {non_stdlib - _APPLICATION_ALLOWED_THIRD_PARTY}"
        )


class TestValidatorBDomainZeroTouchAndRootOnlyInstantiation:
    """验证器 B：domain 零触碰 + 组合根外零实例化."""

    def test_domain_zero_story57_symbols(self) -> None:
        """domain 零触碰：本 Story 新增符号在 src/domain/ 全目录零命中."""
        for py_file in (SRC_DIR / "domain").rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for symbol in _STORY57_SYMBOLS:
                assert symbol not in source, f"domain 零触碰红线: {py_file} 含 {symbol}"

    def test_domain_zero_opentelemetry_import(self) -> None:
        """domain 零 import opentelemetry（追踪非领域概念——domain 零依赖原则）."""
        for py_file in (SRC_DIR / "domain").rglob("*.py"):
            imports = _scan_file_imports(py_file)
            assert "opentelemetry" not in imports, f"domain 禁 import opentelemetry: {py_file}"

    def test_phoenix_tracer_instantiation_only_in_composition_root(self) -> None:
        """组合根外零实例化：PhoenixTracer( 构造点仅 composition_root.py."""
        sites = _scan_instantiation_sites("PhoenixTracer")
        assert sites, "组合根应至少一处 PhoenixTracer 实例化（Story 5.7 注册 lambda）"
        outside = [s for s in sites if not s.startswith("src/composition_root.py")]
        assert outside == [], f"组合根外实例化点: {outside}"


class TestValidatorCDecoratorAnchorsAndSignatureStability:
    """验证器 C：装饰器静态锚 + 构造签名不变（纯附加装饰具体化——R3-14）."""

    def test_six_phase_methods_decorated(self) -> None:
        """六阶段方法 __wrapped__ 在位 + __name__ 不变（装饰器静态锚）."""
        from src.application.services.agent_workflow_service import AgentWorkflowService

        for phase in _SIX_PHASE_METHODS:
            method = getattr(AgentWorkflowService, phase)
            assert hasattr(method, "__wrapped__"), f"六阶段方法 {phase} 应有 @trace 装饰器"
            assert method.__name__ == phase

    def test_execute_use_case_decorated(self) -> None:
        """RunAgentWorkflowUseCase.execute __wrapped__ 在位（根 span 静态锚）."""
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        assert hasattr(RunAgentWorkflowUseCase.execute, "__wrapped__")
        assert RunAgentWorkflowUseCase.execute.__name__ == "execute"

    def test_service_constructor_signature_unchanged(self) -> None:
        """AgentWorkflowService 构造签名与 5-3 基线一致（零构造签名变化）."""
        from src.application.services.agent_workflow_service import AgentWorkflowService

        params = list(inspect.signature(AgentWorkflowService.__init__).parameters)[1:]
        assert params == _SERVICE_INIT_PARAMS, f"构造签名漂移: {params}"

    def test_use_case_constructor_signature_unchanged(self) -> None:
        """RunAgentWorkflowUseCase 构造签名与 5-3 基线一致（零构造签名变化）."""
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
        assert params == _USE_CASE_INIT_PARAMS, f"构造签名漂移: {params}"

    def test_execute_signature_unchanged(self) -> None:
        """execute 方法签名不变（agent_id/task 两参数——纯附加装饰）."""
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.execute).parameters)[1:]
        assert params == ["agent_id", "task"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
