"""SDD 架构约束验证测试——Story 5.9 CUSUM 漂移检测（AC-4.2 全量承载）。

三验证器 + 零抑制（test_arch_evaluation.py 同款结构——5.8 AST 验证器直接模板）：

- 验证器 A：application 触碰文件第三方白名单（agent_drift.py/run_agent_workflow.py/
  ports/__init__.py——零新增第三方断言：本 Story application 触碰面纯标准库 +
  既有 opentelemetry）；
- 验证器 B：domain 触碰白名单域（_STORY59 业务符号在 domain/ports|services|
  entities|value_objects 零命中[词边界正则] + **DriftDetected 允许在 domain/events
  命中**[本 Story 与 5.8 的差异面——5.8 零 events 触碰，本 Story 新增领域事件：
  漂移是领域告警语义] + DriftDetectionError 仅在 exceptions 三件内）+ 组合根外
  零实例化（CUSUMDriftDetector 构造点仅 composition_root.py + tests/）+ 依赖方向
  （cusum_detector.py import src.application/src.domain——infrastructure→application/
  domain 合法面锚定）+ drift_events.py/evaluation_exceptions.py 标准库零外部依赖；
- 验证器 C：主链漂移块静态锚（execute 体内 update 调用 + DRIFT_DETECTED 常量引用
  [ast.Attribute 与 ast.Name 双形态] + is_drifted 分支 + trigger_recalibration 调用
  在位）+ use case 七依赖签名基线（第七参数默认 None）+ cusum_detector.py 标准库
  零外部依赖断言（OD-2 实现面证据——numpy/scipy 零引入）。

Run with:
    poetry run pytest tests/unit/architecture/test_arch_drift_detection.py -v
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

#: application 触碰文件（本 Story 交付/修改——验证器 A 扫描目标）
_APPLICATION_TARGET_FILES = [
    SRC_DIR / "application" / "ports" / "agent_drift.py",
    SRC_DIR / "application" / "ports" / "__init__.py",
    SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
]

#: application 既有第三方基线（run_agent_workflow 的 opentelemetry——本 Story 零新增）
_ALLOWED_THIRD_PARTY = {"opentelemetry"}

#: Story 5.9 业务符号（验证器 B 词边界扫描——services 域零触碰红线）
_STORY59_BUSINESS_SYMBOLS = ("CUSUMDriftDetector", "DriftDetectionPort", "DriftAssessment")

#: 验证器 C 七依赖签名基线（use case 构造签名——5-8 六依赖 + 5-9 第七可选依赖）
_USE_CASE_INIT_PARAMS = [
    "agent_repository",
    "agent_profile_use_case",
    "agent_engine",
    "agent_workflow_service",
    "isolation_guard",
    "evaluation_harness",
    "drift_detector",
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
    """扫描 src/ 全目录构造点（返回 repo 相对路径:行号 清单——ast.Name/Attribute 双形态）。"""
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
    """验证器 A：application 触碰文件第三方白名单（零新增第三方断言）。"""

    @pytest.mark.parametrize("target", _APPLICATION_TARGET_FILES, ids=[p.name for p in _APPLICATION_TARGET_FILES])
    def test_no_forbidden_third_party(self, target: Path) -> None:
        """黑名单第三方零引入（fastapi/sqlalchemy/redis/numpy/scipy 等）。"""
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
            "numpy",
            "scipy",
        }
        assert target.is_file(), f"application 触碰文件缺失: {target}"
        modules = _scan_file_top_imports(target)
        assert modules & forbidden == set(), f"{target.name} 禁入第三方: {modules & forbidden}"

    @pytest.mark.parametrize("target", _APPLICATION_TARGET_FILES, ids=[p.name for p in _APPLICATION_TARGET_FILES])
    def test_third_party_within_baseline(self, target: Path) -> None:
        """白名单基线（本 Story 零新增——非标准库 ⊆ {opentelemetry}）。"""
        modules = _scan_file_top_imports(target)
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= _ALLOWED_THIRD_PARTY, f"{target.name} 白名单外第三方: {non_stdlib - _ALLOWED_THIRD_PARTY}"

    def test_agent_drift_port_file_pure_stdlib(self) -> None:
        """端口文件纯标准库专项（agent_tracing/agent_evaluation 同款断言）。"""
        modules = _scan_file_top_imports(SRC_DIR / "application" / "ports" / "agent_drift.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"端口文件应零第三方依赖（实际 {non_stdlib}）"


class TestValidatorBDomainTouchAndInstantiation:
    """验证器 B：domain 触碰白名单域 + 组合根外零实例化 + 依赖方向。"""

    def test_domain_business_directories_zero_story59_symbols(self) -> None:
        """业务四目录零触碰红线（ports/services/entities/value_objects——词边界正则）。"""
        business_dirs = [
            SRC_DIR / "domain" / "ports",
            SRC_DIR / "domain" / "services",
            SRC_DIR / "domain" / "entities",
            SRC_DIR / "domain" / "value_objects",
        ]
        for directory in business_dirs:
            for py_file in directory.rglob("*.py"):
                source = py_file.read_text(encoding="utf-8")
                for symbol in _STORY59_BUSINESS_SYMBOLS:
                    pattern = rf"\b{re.escape(symbol)}\b"
                    assert not re.search(pattern, source), f"domain 业务域零触碰红线: {py_file} 含 {symbol}"

    def test_drift_detected_allowed_in_domain_events(self) -> None:
        """DriftDetected 允许且应在 domain/events（本 Story 与 5.8 的差异面——漂移是
        领域告警语义，与 StrategicDeviationWarning 同族）。"""
        events_hits = [
            py_file
            for py_file in (SRC_DIR / "domain" / "events").rglob("*.py")
            if "DriftDetected" in py_file.read_text(encoding="utf-8")
        ]
        assert any(p.name == "drift_events.py" for p in events_hits), "DriftDetected 应在 domain/events（白名单域）"

    def test_drift_detection_error_only_in_exception_files(self) -> None:
        """DriftDetectionError 仅在 exceptions 三件内（存在性正向锚 + 白名单）。"""
        exception_hits: list[Path] = []
        for py_file in (SRC_DIR / "domain" / "exceptions").rglob("*.py"):
            if "DriftDetectionError" in py_file.read_text(encoding="utf-8"):
                exception_hits.append(py_file)
        assert exception_hits, "DriftDetectionError 应存在于 exceptions（正向锚）"
        allowed = {"evaluation_exceptions.py", "_code_ranges.py", "__init__.py"}
        for hit in exception_hits:
            assert hit.name in allowed, f"DriftDetectionError 应仅在 exceptions 三件内: {hit}"

    def test_cusum_detector_instantiation_only_in_composition_root(self) -> None:
        """组合根外零实例化（src/ 内 CUSUMDriftDetector 构造点仅 composition_root）。"""
        sites = _scan_instantiation_sites("CUSUMDriftDetector")
        assert sites, "组合根应至少一处 CUSUMDriftDetector 实例化（注册 lambda——正向锚）"
        violations = [s for s in sites if not s.startswith("src/composition_root.py")]
        assert not violations, f"组合根外实例化点: {violations}"

    def test_cusum_detector_imports_application_and_domain(self) -> None:
        """依赖方向锚（infrastructure→application/domain 合法面——import 模块前缀断言）。"""
        source = (SRC_DIR / "infrastructure" / "monitoring" / "cusum_detector.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert any(m.startswith("src.application") for m in modules), "应 import application 端口（DriftDetectionPort 族）"
        assert any(m.startswith("src.domain") for m in modules), "应 import domain 端口/事件（EventPublisher 族）"

    def test_drift_events_pure_stdlib(self) -> None:
        """drift_events.py 标准库零外部依赖（domain events 体系铁律）。"""
        modules = _scan_file_top_imports(SRC_DIR / "domain" / "events" / "drift_events.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"drift_events.py 应零外部依赖（实际 {non_stdlib}）"

    def test_evaluation_exceptions_pure_stdlib(self) -> None:
        """evaluation_exceptions.py 标准库零外部依赖（451 追加后维持）。"""
        modules = _scan_file_top_imports(SRC_DIR / "domain" / "exceptions" / "evaluation_exceptions.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"evaluation_exceptions.py 应零外部依赖（实际 {non_stdlib}）"


class TestValidatorCMainChainStaticAnchorAndSignature:
    """验证器 C：主链漂移块静态锚 + 七依赖签名 + 检测器零外部依赖。"""

    def _get_execute_node(self) -> tuple[ast.AsyncFunctionDef | ast.FunctionDef, str]:
        target_path = SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py"
        source = target_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
                return node, source
        pytest.fail("run_agent_workflow.py 应存在 execute 方法")

    def test_execute_calls_drift_update(self) -> None:
        """execute 体内 update 调用在位（漂移块静态锚①）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert "await self._drift_detector.update(" in segment, "execute 体内应有 update 调用"

    def test_execute_references_drift_detected_constant(self) -> None:
        """DRIFT_DETECTED 常量引用（ast.Attribute 形态——ast.Name 双形态兜底）。"""
        node, source = self._get_execute_node()
        attr_names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        name_ids = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        assert "DRIFT_DETECTED" in attr_names or "DRIFT_DETECTED" in name_ids, (
            "execute 体内应引用 SpanAttributeKeys.DRIFT_DETECTED（Attribute/Name 双形态）"
        )

    def test_execute_has_is_drifted_branch_and_trigger(self) -> None:
        """is_drifted 分支 + trigger_recalibration 调用在位（静态锚③④）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert "is_drifted" in segment, "execute 体内应有 is_drifted 分支"
        assert "trigger_recalibration" in segment, "execute 体内应有 trigger_recalibration 调用"
        assert "is_recording" in segment, "span 写入应有 is_recording 守卫"

    def test_drift_block_after_eval_keys(self) -> None:
        """漂移块在评估三键之后（评估先于漂移——序列数据源依赖序）。"""
        target_path = SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py"
        source_lines = target_path.read_text(encoding="utf-8").splitlines()
        eval_key_lines = [i for i, line in enumerate(source_lines, start=1) if "EVAL_CONFIDENCE_ACCURACY" in line]
        drift_lines = [i for i, line in enumerate(source_lines, start=1) if "DRIFT_DETECTED" in line]
        assert eval_key_lines and drift_lines, "评估三键与 DRIFT_DETECTED 均应在位（正向锚）"
        assert min(drift_lines) > max(eval_key_lines), "漂移块应在评估三键写入之后（评估产物消费序）"

    def test_use_case_seven_dependency_signature(self) -> None:
        """七依赖签名基线（第七参数 drift_detector 默认 None——尾部追加）。"""
        import inspect

        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
        assert params == _USE_CASE_INIT_PARAMS, f"构造签名漂移: {params}"
        default = inspect.signature(RunAgentWorkflowUseCase.__init__).parameters["drift_detector"].default
        assert default is None

    def test_cusum_detector_pure_stdlib(self) -> None:
        """cusum_detector.py 标准库零外部依赖（OD-2 实现面证据——numpy/scipy 零引入）。"""
        modules = _scan_file_top_imports(SRC_DIR / "infrastructure" / "monitoring" / "cusum_detector.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"cusum_detector.py 应纯标准库（实际 {non_stdlib}）"


class TestArchNoSuppressionComments:
    """本 Story 触碰文件零抑制注释（noqa/type: ignore/pylint: disable 全禁——红线）。"""

    @pytest.mark.parametrize(
        "relative",
        [
            "src/application/ports/agent_drift.py",
            "src/application/use_cases/run_agent_workflow.py",
            "src/domain/events/drift_events.py",
            "src/domain/exceptions/evaluation_exceptions.py",
            "src/domain/exceptions/_code_ranges.py",
            "src/domain/exceptions/__init__.py",
            "src/infrastructure/monitoring/cusum_detector.py",
            "src/infrastructure/messaging/channel_router.py",
            "src/composition_root.py",
        ],
    )
    def test_no_suppression_comments(self, relative: str) -> None:
        """交付文件零 noqa/type: ignore/pylint: disable。"""
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for suppression in ("# noqa", "# type: ignore", "# pylint: disable"):
            assert suppression not in source, f"{relative} 含抑制注释 {suppression}（红线禁止）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
