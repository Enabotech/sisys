"""SDD 架构约束验证测试——Story 5.10 CheckpointWithEvaluation 集成（AC-4.2 全量承载）。

三验证器 + 零抑制（test_arch_drift_detection.py 同款结构——5.9 AST 验证器直接模板）：

- 验证器 A：application 触碰文件第三方白名单（agent_checkpoint.py/
  evaluation_checkpoint_recorder.py/run_agent_workflow.py/ports/__init__.py——
  零新增第三方断言：本 Story application 触碰面纯标准库 + 既有 opentelemetry）；
- 验证器 B：domain 触碰白名单域（_STORY510 业务符号在 domain/ports|services|
  entities|value_objects 零命中[词边界正则] + **events 全域零命中**[OD-6 契约——
  本 Story 与 5.9 的差异面：5.9 新增 DriftDetected 事件入 events 白名单域，本
  Story 事件零改动零触碰] + EvaluationHistoryError 仅在 exceptions 三件内）+
  组合根外零实例化（EvaluationCheckpointRecorder 构造点仅 composition_root.py）
  + 依赖方向（evaluation_checkpoint_recorder.py import src.application/src.domain
  ——application→domain 合法面锚定 + infrastructure/interfaces 零 import）；
- 验证器 C：主链 record 块静态锚（execute 体内 record 调用 +
  result.evidence.confidence 引用 + 内层 except EvaluationHistoryError 分支 +
  **漂移块之前顺序锚**[AST await 节点行号序——record < drift update]）+ use case
  八依赖签名基线（第八参数默认 None）+ agent_checkpoint.py/
  evaluation_checkpoint_recorder.py 标准库零外部依赖断言。

Run with:
    poetry run pytest tests/unit/architecture/test_arch_checkpoint_evaluation.py -v
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
    SRC_DIR / "application" / "ports" / "agent_checkpoint.py",
    SRC_DIR / "application" / "ports" / "__init__.py",
    SRC_DIR / "application" / "services" / "evaluation_checkpoint_recorder.py",
    SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
]

#: application 既有第三方基线（run_agent_workflow 的 opentelemetry——本 Story 零新增）
_ALLOWED_THIRD_PARTY = {"opentelemetry"}

#: Story 5.10 业务符号（验证器 B 词边界扫描——业务四目录零触碰红线）
_STORY510_BUSINESS_SYMBOLS = (
    "CheckpointWithEvaluation",
    "AgentCheckpointPort",
    "EvaluationCheckpointRecorder",
    "EvaluationCheckpoint",
)

#: 验证器 C 八依赖签名基线（use case 构造签名——5-8 六 + 5-9 七 + 5-10 第八可选依赖）
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

    def test_agent_checkpoint_port_file_pure_stdlib(self) -> None:
        """端口文件纯标准库专项（agent_tracing/agent_evaluation/agent_drift 同款断言）。"""
        modules = _scan_file_top_imports(SRC_DIR / "application" / "ports" / "agent_checkpoint.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"端口文件应零第三方依赖（实际 {non_stdlib}）"

    def test_recorder_file_pure_stdlib(self) -> None:
        """Recorder 实现文件纯标准库专项（asyncio + dataclass——存储委托注入端口，无 redis import）。"""
        modules = _scan_file_top_imports(SRC_DIR / "application" / "services" / "evaluation_checkpoint_recorder.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"Recorder 应零第三方依赖（实际 {non_stdlib}）"


class TestValidatorBDomainTouchAndInstantiation:
    """验证器 B：domain 触碰面收窄 + events 零触碰 + 组合根外零实例化 + 依赖方向。"""

    def test_domain_business_directories_zero_story510_symbols(self) -> None:
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
                for symbol in _STORY510_BUSINESS_SYMBOLS:
                    pattern = rf"\b{re.escape(symbol)}\b"
                    assert not re.search(pattern, source), f"domain 业务域零触碰红线: {py_file} 含 {symbol}"

    def test_domain_events_zero_touch(self) -> None:
        """events 全域零命中（OD-6 契约——本 Story 与 5.9 的差异面：CheckpointReached
        不发布，事件通道 yaml + DEFAULT_MAPPINGS 零改动，事件目录零触碰）。"""
        for py_file in (SRC_DIR / "domain" / "events").rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for symbol in ("CheckpointWithEvaluation", "EvaluationHistoryError", "EvaluationCheckpoint"):
                pattern = rf"\b{re.escape(symbol)}\b"
                assert not re.search(pattern, source), f"events 零触碰红线（OD-6）: {py_file} 含 {symbol}"

    def test_evaluation_history_error_only_in_exception_files(self) -> None:
        """EvaluationHistoryError 仅在 exceptions 三件内（存在性正向锚 + 白名单）。"""
        exception_hits: list[Path] = []
        for py_file in (SRC_DIR / "domain" / "exceptions").rglob("*.py"):
            if "EvaluationHistoryError" in py_file.read_text(encoding="utf-8"):
                exception_hits.append(py_file)
        assert exception_hits, "EvaluationHistoryError 应存在于 exceptions（正向锚）"
        allowed = {"evaluation_exceptions.py", "_code_ranges.py", "__init__.py"}
        for hit in exception_hits:
            assert hit.name in allowed, f"EvaluationHistoryError 应仅在 exceptions 三件内: {hit}"

    def test_recorder_instantiation_only_in_composition_root(self) -> None:
        """组合根外零实例化（src/ 内 EvaluationCheckpointRecorder 构造点仅 composition_root）。"""
        sites = _scan_instantiation_sites("EvaluationCheckpointRecorder")
        assert sites, "组合根应至少一处 EvaluationCheckpointRecorder 实例化（注册 lambda——正向锚）"
        violations = [s for s in sites if not s.startswith("src/composition_root.py")]
        assert not violations, f"组合根外实例化点: {violations}"

    def test_recorder_imports_application_and_domain_only(self) -> None:
        """依赖方向锚（application→application/domain 合法面 + infrastructure/interfaces 零 import）。"""
        source = (SRC_DIR / "application" / "services" / "evaluation_checkpoint_recorder.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert any(m.startswith("src.application") for m in modules), "应 import application 端口（AgentCheckpointPort 族）"
        assert any(m.startswith("src.domain") for m in modules), "应 import domain 端口/实体/异常（R2 组合注入面）"
        assert not any(m.startswith("src.infrastructure") or m.startswith("src.interfaces") for m in modules), (
            "application 不得 import infrastructure/interfaces"
        )

    def test_evaluation_exceptions_pure_stdlib(self) -> None:
        """evaluation_exceptions.py 标准库零外部依赖（452 追加后维持）。"""
        modules = _scan_file_top_imports(SRC_DIR / "domain" / "exceptions" / "evaluation_exceptions.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"evaluation_exceptions.py 应零外部依赖（实际 {non_stdlib}）"


class TestValidatorCMainChainStaticAnchorAndSignature:
    """验证器 C：主链 record 块静态锚 + 八依赖签名 + 两新文件零外部依赖。"""

    def _get_execute_node(self) -> tuple[ast.AsyncFunctionDef | ast.FunctionDef, str]:
        target_path = SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py"
        source = target_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
                return node, source
        pytest.fail("run_agent_workflow.py 应存在 execute 方法")

    def test_execute_calls_checkpoint_record(self) -> None:
        """execute 体内 record 调用在位（record 块静态锚①——None 守卫）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert "_checkpoint_recorder" in segment, "execute 体内应有 record 块（None 守卫）"
        assert "await self._checkpoint_recorder.record(" in segment, "execute 体内应有 record 调用"

    def test_execute_references_predicted_confidence(self) -> None:
        """predicted=result.evidence.confidence 引用在位（静态锚②——V1-EV3 兑现锚）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert "result.evidence.confidence" in segment, "execute 体内应有 predicted 从 evidence.confidence 直传"

    def test_execute_has_inner_evaluation_history_catch(self) -> None:
        """内层 except EvaluationHistoryError 分支在位（静态锚③——452 独立降级网）。"""
        node, source = self._get_execute_node()
        segment = ast.get_source_segment(source, node) or ""
        assert "except EvaluationHistoryError" in segment, "record 块应有内层 452 独立 catch"

    def test_record_block_before_drift_block(self) -> None:
        """漂移块之前顺序锚（静态锚④——AST await 节点行号序：record < drift update）。"""
        node, _ = self._get_execute_node()
        record_lineno = None
        drift_lineno = None
        for sub in ast.walk(node):
            if isinstance(sub, ast.Await) and isinstance(sub.value, ast.Call):
                func = sub.value.func
                func_name = getattr(func, "attr", None) or getattr(func, "id", None)
                if func_name == "record":
                    record_lineno = sub.lineno
                if func_name == "update":
                    drift_lineno = sub.lineno
        assert record_lineno is not None, "应找到 record 调用 await 节点"
        assert drift_lineno is not None, "应找到漂移 update 调用 await 节点"
        assert record_lineno < drift_lineno, (
            f"record 块应在漂移块之前（record@{record_lineno} < drift@{drift_lineno}——DC-3 位序钦定）"
        )

    def test_use_case_eight_dependency_signature(self) -> None:
        """八依赖签名基线（第八参数 checkpoint_recorder 默认 None——尾部追加）。"""
        import inspect

        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
        assert params == _USE_CASE_INIT_PARAMS, f"构造签名漂移: {params}"
        default = inspect.signature(RunAgentWorkflowUseCase.__init__).parameters["checkpoint_recorder"].default
        assert default is None

    def test_agent_checkpoint_module_pure_stdlib(self) -> None:
        """agent_checkpoint.py 标准库零外部依赖（端口文件铁律）。"""
        modules = _scan_file_top_imports(SRC_DIR / "application" / "ports" / "agent_checkpoint.py")
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"agent_checkpoint.py 应纯标准库（实际 {non_stdlib}）"


class TestArchNoSuppressionComments:
    """本 Story 触碰文件零抑制注释（noqa/type: ignore/pylint: disable 全禁——红线）。"""

    @pytest.mark.parametrize(
        "relative",
        [
            # src 触碰面（9 件——新建 2 + 存量触碰 7）
            "src/application/ports/agent_checkpoint.py",
            "src/application/ports/__init__.py",
            "src/application/services/evaluation_checkpoint_recorder.py",
            "src/application/use_cases/run_agent_workflow.py",
            "src/domain/exceptions/evaluation_exceptions.py",
            "src/domain/exceptions/_code_ranges.py",
            "src/domain/exceptions/__init__.py",
            "src/composition_root.py",
            "src/interfaces/api/exception_handlers.py",
            # 测试交付面（本 Story 新建 7 件 + 存量触碰 9 件）
            "tests/unit/application/test_agent_checkpoint_model.py",
            "tests/unit/application/services/test_evaluation_checkpoint_recorder.py",
            "tests/contracts/test_port_contract_agent_checkpoint.py",
            "tests/integration/test_integration_checkpoint_evaluation.py",
            "tests/acceptance/test_acceptance_checkpoint_evaluation.py",
            "tests/unit/application/use_cases/test_run_agent_workflow.py",
            "tests/unit/domain/exceptions/test_evaluation_exceptions.py",
            "tests/unit/architecture/test_arch_phoenix_tracer.py",
            "tests/acceptance/test_acceptance_phoenix_tracer.py",
            "tests/acceptance/test_acceptance_agent_evaluation.py",
            "tests/acceptance/test_acceptance_drift_detection.py",
            # 排除（勿「补全」）：架构验证器文件（本文件与 test_arch_evaluation/
            # test_arch_drift_detection）自身源码含抑制注释字符串字面量（断言
            # 目标——子串扫描自毙）；test_exception_handlers.py 含存量合法
            # 豁免债（N817/N814 ruff import 别名——非本 Story 面，随全仓豁免
            # 债清理任务处置，见 deferred-work）
        ],
    )
    def test_no_suppression_comments(self, relative: str) -> None:
        """交付文件零 noqa/type: ignore/pylint: disable。"""
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for suppression in ("# noqa", "# type: ignore", "# pylint: disable"):
            assert suppression not in source, f"{relative} 含抑制注释 {suppression}（红线禁止）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
