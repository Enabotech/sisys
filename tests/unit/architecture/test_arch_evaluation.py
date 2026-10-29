"""Story 5.8 架构约束验证器（A/B/C——SDD 规范验证测试）。

验证器 A：application 触碰文件第三方 import 白名单（pydantic/opentelemetry 允许
——5.7 验证器 A+ 全层基线 {opentelemetry, pydantic, yaml} 内零新增断言——
OD-1[5.7] 触发条件裁定不满足的实现面证据）。
验证器 B：domain 触碰收窄（_STORY58 业务符号在业务域五目录零命中 +
AgentEvaluationError 仅在 exceptions 三件内）+ 组合根外零实例化
（EvaluationHarness/UdmrEvaluationModelResolver 构造点仅 composition_root.py）+
依赖方向（resolver import src.application——infrastructure→application 合法面锚定）。
验证器 C：主链评估块静态锚（execute 体内 evaluate 调用 + SpanAttributeKeys 三常量
引用[Attribute 形态] + is_recording 守卫）+ use case 六依赖签名基线 +
evaluation_exceptions 标准库零外部依赖断言。

Run with:
    poetry run pytest tests/unit/architecture/test_arch_evaluation.py -v
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

#: Story 5.8 application 触碰文件（新建四 + 修改二含 ports/__init__.py 聚合导出）
_APPLICATION_TARGET_FILES = [
    SRC_DIR / "application" / "ports" / "agent_evaluation.py",
    SRC_DIR / "application" / "ports" / "__init__.py",
    SRC_DIR / "application" / "services" / "evaluation_harness.py",
    SRC_DIR / "application" / "services" / "evaluation_schemas.py",
    SRC_DIR / "application" / "services" / "evaluation_prompts.py",
    SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
]

#: 验证器 A 允许的第三方顶层模块（A+ 全层基线内——零白名单变更）
_ALLOWED_THIRD_PARTY = {"pydantic", "opentelemetry"}

#: 验证器 B 业务符号（domain 业务域五目录零命中）
_STORY58_BUSINESS_SYMBOLS = (
    "EvaluationHarness",
    "AgentEvaluationPort",
    "EvaluationModelResolverPort",
    "EvaluationResult",
    "HallucinationEvaluationSchema",
    "EVALUATION_WEIGHTS",
)

#: 验证器 C 八依赖签名基线（use case 构造签名——5-8 资产同步②对齐 + 5-9 扩七 + 5-10 扩八）
_USE_CASE_INIT_PARAMS = [
    "agent_repository",
    "agent_profile_use_case",
    "agent_engine",
    "agent_workflow_service",
    "isolation_guard",
    "evaluation_harness",
    "drift_detector",
    "checkpoint_recorder",
]


def _scan_file_top_imports(path: Path) -> set[str]:
    """扫描文件顶层 import 模块名集合（Import/ImportFrom 取首段——level>0 相对导入跳过）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def _scan_instantiation_sites(target_class: str) -> list[str]:
    """扫描 src/ 全目录构造点（返回 repo 相对路径:行号 清单）。"""
    sites: list[str] = []
    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if name == target_class:
                    sites.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}")
    return sites


class TestValidatorAApplicationThirdPartyWhitelist:
    """验证器 A：application 触碰文件第三方 import 白名单（OD-1[5.7] 不触发证据）。"""

    @pytest.mark.parametrize("target", _APPLICATION_TARGET_FILES, ids=[p.name for p in _APPLICATION_TARGET_FILES])
    def test_no_forbidden_third_party(self, target: Path) -> None:
        """触碰文件零白名单外第三方（fastapi/sqlalchemy/redis/litellm 等禁入）。"""
        forbidden = {
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
            "litellm",
            "httpx",
            "aiohttp",
        }
        assert target.is_file(), f"application 触碰文件缺失: {target}"
        modules = _scan_file_top_imports(target)
        assert modules & forbidden == set(), f"{target.name} 禁入第三方: {modules & forbidden}"

    @pytest.mark.parametrize("target", _APPLICATION_TARGET_FILES, ids=[p.name for p in _APPLICATION_TARGET_FILES])
    def test_third_party_within_baseline(self, target: Path) -> None:
        """非标准库第三方 ⊆ {pydantic, opentelemetry}（A+ 基线内——零白名单变更）。"""
        modules = _scan_file_top_imports(target)
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= _ALLOWED_THIRD_PARTY, f"{target.name} 白名单外第三方: {non_stdlib - _ALLOWED_THIRD_PARTY}"

    def test_agent_evaluation_port_file_pure_stdlib(self) -> None:
        """端口文件纯标准库零第三方（Protocol + dataclass + 常量——agent_tracing 同款）。"""
        modules = _scan_file_top_imports(SRC_DIR / "application" / "ports" / "agent_evaluation.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"端口文件应零第三方依赖，实际: {non_stdlib}"


class TestValidatorBDomainZeroTouchAndRootOnlyInstantiation:
    """验证器 B：domain 触碰收窄 + 组合根外零实例化 + 依赖方向。"""

    def test_domain_business_directories_zero_story58_symbols(self) -> None:
        """业务域五目录（ports/services/entities/value_objects/events）零业务符号。

        词边界匹配：检索域既有 ``RelevanceEvaluationResult``（relevance_evaluation.py
        L23 TypedDict——Task 0.2 契约文档显式甄别的撞名）不含 5.8 的
        EvaluationResult 符号——子串形态不误伤。
        """
        import re

        business_dirs = [
            SRC_DIR / "domain" / "ports",
            SRC_DIR / "domain" / "services",
            SRC_DIR / "domain" / "entities",
            SRC_DIR / "domain" / "value_objects",
            SRC_DIR / "domain" / "events",
        ]
        for directory in business_dirs:
            for py_file in directory.rglob("*.py"):
                source = py_file.read_text(encoding="utf-8")
                for symbol in _STORY58_BUSINESS_SYMBOLS:
                    pattern = rf"\b{re.escape(symbol)}\b"
                    assert not re.search(pattern, source), f"domain 业务域零触碰红线: {py_file} 含 {symbol}"

    def test_agent_evaluation_error_only_in_exception_files(self) -> None:
        """AgentEvaluationError 仅在 exceptions 三件（evaluation_exceptions/_code_ranges/__init__）。"""
        allowed = {"evaluation_exceptions.py", "_code_ranges.py", "__init__.py"}
        hits: list[Path] = []
        for py_file in (SRC_DIR / "domain" / "exceptions").rglob("*.py"):
            if "AgentEvaluationError" in py_file.read_text(encoding="utf-8"):
                hits.append(py_file)
        assert hits, "exceptions 应有 AgentEvaluationError 注册"
        for hit in hits:
            assert hit.name in allowed, f"AgentEvaluationError 应仅在 exceptions 三件内: {hit}"

    def test_evaluation_harness_instantiation_only_in_composition_root(self) -> None:
        """EvaluationHarness 构造点仅组合根（src/ 扫描——tests 豁免）。"""
        sites = _scan_instantiation_sites("EvaluationHarness")
        assert sites, "组合根应至少一处 EvaluationHarness 实例化（注册 lambda）"
        violations = [s for s in sites if not s.startswith("src/composition_root.py")]
        assert violations == [], f"组合根外实例化点: {violations}"

    def test_udmr_resolver_instantiation_only_in_composition_root(self) -> None:
        """UdmrEvaluationModelResolver 构造点仅组合根。"""
        sites = _scan_instantiation_sites("UdmrEvaluationModelResolver")
        assert sites, "组合根应至少一处 UdmrEvaluationModelResolver 实例化"
        violations = [s for s in sites if not s.startswith("src/composition_root.py")]
        assert violations == [], f"组合根外实例化点: {violations}"

    def test_resolver_imports_application_port(self) -> None:
        """依赖方向锚：resolver（infrastructure）import src.application 端口——合法面。"""
        resolver_path = SRC_DIR / "infrastructure" / "routing" / "udmr_evaluation_model_resolver.py"
        tree = ast.parse(resolver_path.read_text(encoding="utf-8"))
        imported_from_application = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.application"):
                imported_from_application = True
        assert imported_from_application, "resolver 应 import application 端口（infrastructure→application 合法面锚定）"

    def test_evaluation_exceptions_pure_stdlib(self) -> None:
        """evaluation_exceptions.py 标准库零外部依赖（domain 体系铁律）。"""
        modules = _scan_file_top_imports(SRC_DIR / "domain" / "exceptions" / "evaluation_exceptions.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"domain 异常文件应零外部依赖，实际: {non_stdlib}"


class TestValidatorCMainChainStaticAnchorAndSignature:
    """验证器 C：主链评估块静态锚 + 六依赖签名基线。"""

    def _get_execute_node(self) -> tuple[ast.AsyncFunctionDef | ast.FunctionDef, str]:
        """取 execute 方法 AST 节点与源文本。"""
        target_path = SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py"
        source = target_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
                return node, source
        pytest.fail("run_agent_workflow.py 应存在 execute 方法")

    def test_execute_calls_evaluate(self) -> None:
        """execute 体内有 evaluate 调用（评估块静态锚①）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert ".evaluate(" in segment, "execute 体内应有 evaluate 调用"

    def test_execute_has_is_recording_guard(self) -> None:
        """execute 体内有 is_recording 守卫（评估块静态锚②）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert "is_recording" in segment, "评估块应有 is_recording 守卫"

    def test_execute_references_three_span_constants(self) -> None:
        """execute 体内引用三常量（Attribute 形态——评估块静态锚③）。"""
        node, _ = self._get_execute_node()
        attr_names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        for constant in ("EVAL_HALLUCINATION_SCORE", "EVAL_CONTEXT_RELEVANCE", "EVAL_CONFIDENCE_ACCURACY"):
            assert constant in attr_names, f"execute 体内应引用 SpanAttributeKeys.{constant}（Attribute 形态）"

    def test_use_case_six_dependency_signature(self) -> None:
        """六依赖签名基线（第六参数 evaluation_harness 默认 None）。"""
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
        assert params == _USE_CASE_INIT_PARAMS, f"构造签名漂移: {params}"
        default = inspect.signature(RunAgentWorkflowUseCase.__init__).parameters["evaluation_harness"].default
        assert default is None

    def test_evaluation_block_after_ten_attribute_block(self) -> None:
        """评估块位置锚：三常量引用行号在 EVIDENCE_INPUT_HASH（MVP 十属性末键）之后。"""
        node, _ = self._get_execute_node()
        last_ten_attr_line = 0
        eval_first_line = 10**9
        for n in ast.walk(node):
            if isinstance(n, ast.Attribute):
                if n.attr == "EVIDENCE_INPUT_HASH":
                    last_ten_attr_line = max(last_ten_attr_line, n.lineno)
                if n.attr in ("EVAL_HALLUCINATION_SCORE", "EVAL_CONTEXT_RELEVANCE", "EVAL_CONFIDENCE_ACCURACY"):
                    eval_first_line = min(eval_first_line, n.lineno)
        assert last_ten_attr_line > 0, "MVP 十属性块应在位"
        assert eval_first_line < 10**9, "评估块三常量应在位"
        assert eval_first_line > last_ten_attr_line, "评估块应在 MVP 十属性块之后"


class TestArchNoSuppressionComments:
    """5.8 交付文件零抑制注释（noqa/type: ignore/pylint 红线）。"""

    @pytest.mark.parametrize(
        "relative",
        [
            "src/application/ports/agent_evaluation.py",
            "src/application/services/evaluation_harness.py",
            "src/application/services/evaluation_schemas.py",
            "src/application/services/evaluation_prompts.py",
            "src/infrastructure/routing/udmr_evaluation_model_resolver.py",
            "src/domain/exceptions/evaluation_exceptions.py",
            "src/application/use_cases/run_agent_workflow.py",
        ],
    )
    def test_no_suppression_comments(self, relative: str) -> None:
        """交付文件零 noqa/type: ignore/pylint: disable。"""
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for suppression in ("# noqa", "# type: ignore", "# pylint: disable"):
            assert suppression not in source, f"{relative} 含抑制注释 {suppression}（红线禁止）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
