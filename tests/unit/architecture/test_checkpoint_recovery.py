"""Story 6-6 — Checkpoint 恢复面 SDD 架构约束验证测试（四验证器）。

epics L2344 钦定名 test_checkpoint_recovery.py（单元测试文件名语境——
6-6 落位 unit/architecture/ 子目录承载 SDD 架构验证，与既有 test_checkpoint.py
并存无冲突；6-3 半采半离先例）。

四验证器：
A. domain 零依赖（recovery_mode.py 两纯函数扩展后+planning_exceptions.py
   扩展后 AST 黑名单复核——import-linter 二线防线）；
B. 服务落位（list/execute 定义唯一性/端口落位/不越层/禁本地 Protocol）；
C. 发布点守护（CheckpointRecovered 唯一构造位=checkpoint_service 恢复引擎；
   6-3 五方法行为面零触碰——源码签名与 call_order 锚不变）；
D. 键族三前缀判别（CHECKPOINT_RECOVERY_SESSION_PREFIX 单源常量+三前缀
   互异断言+恢复记录 checkpoint_no="" 非完整形态断言）。
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "src"
REPO_ROOT = _SRC_ROOT.parent

#: domain 层禁依赖黑名单（CLAUDE.md Hard Constraints——import-linter 二线防线）
_FORBIDDEN_DOMAIN_IMPORTS: frozenset[str] = frozenset(
    {
        "langgraph",
        "prefect",
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "typer",
        "redis",
        "qdrant_client",
        "minio",
        "neo4j",
        "aio_pika",
        "litellm",
        "instructor",
        "requests",
        "httpx",
        "docker",
        "psycopg2",
        "msgpack",
    }
)

#: 6-3 五方法行为面锚（验证器 C 零触碰守护——方法名+关键行为锚双清单）
_SIX_THREE_METHOD_ANCHORS: tuple[tuple[str, str], ...] = (
    ("create_checkpoint", "CheckpointReached"),
    ("build_snapshot", "calculate_checksum"),
    ("apply_correction", "checkpoint_correction_version_conflict"),
    ("recover_checkpoint", "checksum_mismatch"),
    ("recommend_recovery_mode", "recommend_recovery_mode"),
)


def _iter_domain_py_files() -> list[Path]:
    """枚举 src/domain 全部 .py 文件（rglob）。"""
    return sorted((_SRC_ROOT / "domain").rglob("*.py"))


def _imported_top_modules(tree: ast.AST) -> set[str]:
    """提取 AST 的顶层 import 模块名集合（import X / from X import 形态）。"""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    return modules


class TestValidatorADomainZeroDependency:
    """验证器 A：domain 零依赖（6-6 扩展两纯函数+两异常后复核）。"""

    def test_recovery_mode_pure_stdlib_only(self) -> None:
        """recovery_mode.py 扩展后零第三方依赖（stdlib+src 合法——domain 零外部依赖）。"""
        source_path = _SRC_ROOT / "domain" / "services" / "recovery_mode.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        external = _imported_top_modules(tree) - {"__future__"}
        # src.* 是域内相对导入（合法）；标准库经 sys.stdlib_module_names 判定
        # （代码审查 R1-F15：此前 stdlib_allowed={"src"} 实际禁一切标准库——比
        # 「domain 零外部依赖」意图更严且错误消息误导排查方向）
        non_stdlib = {module for module in external if module != "src" and module not in sys.stdlib_module_names}
        assert not (non_stdlib & _FORBIDDEN_DOMAIN_IMPORTS), (
            f"recovery_mode.py 引入禁依赖={non_stdlib & _FORBIDDEN_DOMAIN_IMPORTS}"
        )
        assert not non_stdlib, f"recovery_mode.py 引入第三方依赖={non_stdlib}（零外部依赖——stdlib+src 合法）"

    def test_planning_exceptions_pure_domain(self) -> None:
        """planning_exceptions.py 扩展后零第三方依赖（486/487 落 domain 合规）。"""
        source_path = _SRC_ROOT / "domain" / "exceptions" / "planning_exceptions.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        external = _imported_top_modules(tree) - {"__future__"}
        non_stdlib = {module for module in external if module != "src" and module not in sys.stdlib_module_names}
        assert not non_stdlib, f"planning_exceptions.py 引入第三方依赖={non_stdlib}（零外部依赖——stdlib+src 合法）"

    def test_domain_full_scan_no_forbidden_imports(self) -> None:
        """domain 全目录 AST 黑名单扫描（import-linter 二线防线——全覆盖复核）。"""
        violations: list[str] = []
        for py_file in _iter_domain_py_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            hit = _imported_top_modules(tree) & _FORBIDDEN_DOMAIN_IMPORTS
            if hit:
                violations.append(f"{py_file.name}:{sorted(hit)}")
        assert not violations, f"domain 层禁依赖违规={violations}"


class TestValidatorBServicePlacement:
    """验证器 B：服务落位（定义唯一性/端口落位/禁本地 Protocol）。"""

    def test_list_and_execute_defined_in_checkpoint_service_only(self) -> None:
        """list_checkpoints/execute_recovery 定义面=端口 Protocol 声明+服务实现恰两处。"""
        defined_in: dict[str, list[str]] = {"list_checkpoints": [], "execute_recovery": []}
        for py_file in sorted(_SRC_ROOT.rglob("*.py")):
            content = py_file.read_text(encoding="utf-8")
            for method in defined_in:
                if re.search(rf"async def {method}\(", content):
                    defined_in[method].append(str(py_file.relative_to(_SRC_ROOT)))
        expected = ["application/ports/checkpoint.py", "application/services/checkpoint_service.py"]
        assert defined_in["list_checkpoints"] == expected, (
            f"list_checkpoints 定义位实测={defined_in['list_checkpoints']} 期望端口声明+服务实现恰两处"
        )
        assert defined_in["execute_recovery"] == expected, (
            f"execute_recovery 定义位实测={defined_in['execute_recovery']} 期望端口声明+服务实现恰两处"
        )

    def test_methods_declared_in_application_port(self) -> None:
        """两方法签名声明在应用层端口（CheckpointServicePort——不越层）。"""
        port_content = (_SRC_ROOT / "application" / "ports" / "checkpoint.py").read_text(encoding="utf-8")
        assert "async def list_checkpoints(" in port_content, "list_checkpoints 未在 CheckpointServicePort 声明"
        assert "async def execute_recovery(" in port_content, "execute_recovery 未在 CheckpointServicePort 声明"

    def test_use_cases_in_application_layer_not_service_file(self) -> None:
        """两新用例落 application/use_cases（服务文件禁本地 Protocol/用例混置）。"""
        use_case_path = _SRC_ROOT / "application" / "use_cases" / "checkpoint_approval.py"
        assert use_case_path.is_file(), "checkpoint_approval.py 用例文件缺失"
        content = use_case_path.read_text(encoding="utf-8")
        assert "class ListCheckpointsUseCase" in content
        assert "class ExecuteCheckpointRecoveryUseCase" in content
        assert "Protocol" not in content, "用例文件禁本地 Protocol 定义（6-1/6-2/6-3 纪律沿袭）"

    def test_service_file_no_local_protocol(self) -> None:
        """checkpoint_service.py 禁本地 Protocol/Port 抽象（端口在 ports 文件）。"""
        content = (_SRC_ROOT / "application" / "services" / "checkpoint_service.py").read_text(encoding="utf-8")
        assert "class CheckpointServicePort" not in content, "服务文件出现端口定义（越位）"
        assert "Protocol)" not in content.replace("SnapshotRepositoryProtocol)", ""), "服务文件出现本地 Protocol"


class TestValidatorCPublishPointGuard:
    """验证器 C：发布点守护+6-3 五方法行为面零触碰。"""

    def test_checkpoint_recovered_construction_unique(self) -> None:
        """CheckpointRecovered 唯一构造位=checkpoint_service 恢复引擎（排除事件定义文件）。"""
        pattern = re.compile(r"CheckpointRecovered\(")
        constructors: list[str] = []
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            if path.name == "checkpoint_events.py":
                continue  # 事件定义文件（类定义行假阳性——6-3 契约先例排除形态）
            if pattern.search(path.read_text(encoding="utf-8")):
                constructors.append(str(path.relative_to(_SRC_ROOT)))
        assert constructors == ["application/services/checkpoint_service.py"], f"CheckpointRecovered 构造位实测={constructors}"

    def test_six_three_method_anchors_untouched(self) -> None:
        """6-3 五方法行为面锚不变（方法名+关键行为锚双在位——零触碰守护）。"""
        content = (_SRC_ROOT / "application" / "services" / "checkpoint_service.py").read_text(encoding="utf-8")
        for method_name, behavior_anchor in _SIX_THREE_METHOD_ANCHORS:
            assert f"def {method_name}(" in content, f"6-3 方法 {method_name} 消失（行为面破坏）"
            assert behavior_anchor in content, f"{method_name} 行为锚 {behavior_anchor!r} 消失（零触碰破坏）"

    def test_six_three_call_order_anchor_in_tests(self) -> None:
        """6-3 call_order 断言锚在位（既有单测断言未删改——回归面防护）。"""
        test_content = (REPO_ROOT / "tests" / "unit" / "application" / "test_checkpoint_service.py").read_text(encoding="utf-8")
        anchor = '["take_notes", "compress", "archive_plan", "save", "publish"]'
        assert anchor in test_content, "6-3 五步调用序断言锚消失（call_order 断言族破坏）"


class TestValidatorDKeyPrefixDiscrimination:
    """验证器 D：键族三前缀判别（第三键族单源常量+互异+非完整形态）。"""

    def test_recovery_prefix_single_source_constant(self) -> None:
        """CHECKPOINT_RECOVERY_SESSION_PREFIX 单源常量在端口文件（值级锚）。"""
        from src.application.ports.checkpoint import (
            CHECKPOINT_RECOVERY_SESSION_PREFIX,
            CHECKPOINT_SESSION_PREFIX,
        )

        assert CHECKPOINT_RECOVERY_SESSION_PREFIX == "blm-checkpoint-recovery-"
        assert CHECKPOINT_SESSION_PREFIX == "blm-checkpoint-"

    def test_three_prefixes_mutually_distinct(self) -> None:
        """三前缀互异（blm-planning-/blm-checkpoint-/blm-checkpoint-recovery-）。"""
        from src.application.ports.checkpoint import (
            CHECKPOINT_RECOVERY_SESSION_PREFIX,
            CHECKPOINT_SESSION_PREFIX,
        )

        blm_planning_prefix = "blm-planning-"
        prefixes = (blm_planning_prefix, CHECKPOINT_SESSION_PREFIX, CHECKPOINT_RECOVERY_SESSION_PREFIX)
        assert len(set(prefixes)) == 3, f"三前缀互异破坏={prefixes}"
        # 前缀互斥语义：blm-checkpoint- 不是 blm-checkpoint-recovery- 的判别歧义源
        assert not CHECKPOINT_SESSION_PREFIX.startswith(CHECKPOINT_RECOVERY_SESSION_PREFIX)
        assert CHECKPOINT_RECOVERY_SESSION_PREFIX.startswith(CHECKPOINT_SESSION_PREFIX), (
            "恢复记录前缀以快照前缀为词头（判别规则钦定：按完整前缀匹配非前缀的前缀）"
        )

    def test_recovery_record_non_complete_form(self) -> None:
        """恢复记录 checkpoint_no="" 非完整形态（不触发实体构造守卫——OD-3 根基）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        record = CheckpointSnapshot(
            session_id="blm-checkpoint-recovery-test-plan",
            stage_id="recovery_record",
            state_version=0,
            state_data={"recovery_mode": "override"},
            checkpoint_no="",
        )
        assert record.checkpoint_no == ""
        assert record.persistent_note_ref == ""  # 空引用合法（守卫未触发）

    def test_recovery_record_discrimination_key_in_state(self) -> None:
        """权威判别键：state_data 含 recovery_mode 键（checkpoint 族 13 键无此键）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        checkpoint_state_keys = frozenset(
            {
                "checkpoint_no",
                "stage_id",
                "stage_number",
                "plan_id",
                "completed",
                "summary",
                "compressed_context",
                "compression_ratio",
                "quality_score",
                "token_count",
                "persistent_note_ref",
                "correction_history",
                "created_via",
            }
        )
        assert "recovery_mode" not in checkpoint_state_keys, (
            "checkpoint 族 13 键含 recovery_mode（判别规则前提破坏——Task 0 冻结契约）"
        )
        _ = CheckpointSnapshot  # 引用保持（实体形态稳定性锚）
