"""Story 6-3 — Checkpoint 面架构约束验证测试（SDD 规范验证——非 TDD 单元测试）。

四验证器（Task 6 钦定，形态沿 6-1 test_blm_planning_arch.py）：
A. domain 零依赖——checkpoint_snapshot.py/entities/checkpoint.py/recovery_mode.py
   三文件 AST/import 扫描零第三方（import-linter 之外的行为级双防线）；
B. 服务落位——CheckpointService 仅存在于应用层 / 端口仅存在于 application/ports /
   服务不 import infrastructure；
C. 发布点落位守护——CheckpointReached 发布调用仅存在于 checkpoint 应用服务面
   （正向存在性 + 负向 blm_planning 四文件零引用——与契约测试 4.2 双防线）；
D. 公理二链路守护——checkpoint_service 源码压缩调用先于 take_notes 不可达
   （源码级调用序断言 take_notes 先于 compress；compress→archive 序由
   Task 2 调用序断言承载——R2A-15 分工声明）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/architecture/test_checkpoint.py -v
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

#: Story 6-3 domain 面文件（扩展/激活/纯函数三文件——验证器 A 扫描面）
CHECKPOINT_DOMAIN_FILES: tuple[Path, ...] = (
    SRC_ROOT / "domain" / "entities" / "checkpoint_snapshot.py",
    SRC_ROOT / "domain" / "entities" / "checkpoint.py",
    SRC_ROOT / "domain" / "services" / "recovery_mode.py",
)

#: domain 层第三方依赖黑名单（6-1 验证器 A 同款）
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "pydantic",
        "sqlalchemy",
        "redis",
        "fastapi",
        "typer",
        "langgraph",
        "prefect",
        "qdrant_client",
        "minio",
        "neo4j",
        "aio_pika",
        "litellm",
        "instructor",
        "asyncpg",
        "httpx",
        "yaml",
        "dotenv",
    }
)

#: domain 允许的顶层 import 前缀（标准库 + src.domain 同层）
_DOMAIN_ALLOWED_TOP_LEVELS: frozenset[str] = frozenset({"src", "__future__"} | set(sys.stdlib_module_names))

#: 发布点守护——blm_planning 四文件（OD-4 零触碰钦定）
BLM_PLANNING_FOUR_FILES: tuple[str, ...] = (
    "application/services/blm_planning_service.py",
    "application/use_cases/run_blm_planning.py",
    "application/use_cases/get_blm_planning_status.py",
    "application/services/blm_planning_prompts.py",
)


def _extract_imports(file_path: Path) -> list[str]:
    """提取全部 import 目标（ast.walk——覆盖函数内延迟 import）。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return targets


def _extract_method_order(file_path: Path, method_name: str) -> list[str]:
    """提取指定方法体内按源码序出现的调用名（验证器 D 调用序断言锚）。

    R1 审查 FR-19：ast.walk 是 BFS——跨语句不同深度的调用理论上可乱序（当前
    take_notes/compress 同深度源码序成立属侥幸）；按 lineno 排序使提取器
    确定性地反映源码序（嵌套表达式/except 块形态下同样可靠）。
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name:
            calls: list[tuple[int, str]] = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    if isinstance(func, ast.Attribute):
                        calls.append((sub.lineno, func.attr))
                    elif isinstance(func, ast.Name):
                        calls.append((sub.lineno, func.id))
            return [name for _, name in sorted(calls, key=lambda item: item[0])]
    return []


class TestDomainZeroDependencies:
    """验证器 A——domain 零依赖（三文件黑名单 + 白名单双形态）。"""

    def test_domain_files_exist(self) -> None:
        """三文件存在性前置（缺失即断言面失效）。"""
        for file_path in CHECKPOINT_DOMAIN_FILES:
            assert file_path.is_file(), f"domain 文件缺失: {file_path}"

    def test_no_third_party_imports(self) -> None:
        """黑名单零命中（pydantic/sqlalchemy/redis/langgraph 等全禁）。"""
        for file_path in CHECKPOINT_DOMAIN_FILES:
            for module in _extract_imports(file_path):
                top = module.split(".")[0]
                assert top not in FORBIDDEN_IMPORTS, f"{file_path.name} 引入第三方依赖: {module}（domain 零外部依赖红线）"

    def test_only_stdlib_and_domain_layer(self) -> None:
        """仅标准库 + src.domain 同层引用（不 import application/infrastructure）。"""
        for file_path in CHECKPOINT_DOMAIN_FILES:
            for module in _extract_imports(file_path):
                top = module.split(".")[0]
                if top == "src":
                    second = module.split(".")[1]
                    assert second == "domain", f"{file_path.name} 跨层 import: {module}（domain 仅可引用 domain）"
                else:
                    assert top in _DOMAIN_ALLOWED_TOP_LEVELS, f"{file_path.name} 非法 import: {module}"


class TestServicePlacement:
    """验证器 B——服务落位（应用层唯一 + 端口落位 + 不越层）。"""

    def test_checkpoint_service_only_in_application(self) -> None:
        """CheckpointService 类定义仅存在于应用层 services（精确词边界——
        端口类 CheckpointServicePort 不误命中）。"""
        definers: list[str] = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            content = path.read_text(encoding="utf-8")
            if "class CheckpointService:" in content or "class CheckpointService(" in content:
                definers.append(str(path.relative_to(SRC_ROOT)))
        assert definers == ["application/services/checkpoint_service.py"], (
            f"CheckpointService 定义位实测={definers} 期望仅应用层 services"
        )

    def test_port_only_in_application_ports(self) -> None:
        """CheckpointServicePort/恢复视图 DTO 仅存在于 application/ports/checkpoint.py。"""
        port_file = SRC_ROOT / "application" / "ports" / "checkpoint.py"
        assert port_file.is_file(), "端口文件缺失（application/ports/checkpoint.py）"
        content = port_file.read_text(encoding="utf-8")
        assert "class CheckpointServicePort" in content
        assert "class CheckpointRecoveryView" in content

    def test_service_does_not_import_infrastructure(self) -> None:
        """checkpoint 服务/端口/用例不 import infrastructure（越层红线）。"""
        targets = (
            SRC_ROOT / "application" / "services" / "checkpoint_service.py",
            SRC_ROOT / "application" / "ports" / "checkpoint.py",
            SRC_ROOT / "application" / "use_cases" / "create_checkpoint.py",
        )
        for file_path in targets:
            for module in _extract_imports(file_path):
                if module.startswith("src."):
                    second = module.split(".")[1]
                    assert second in {"domain", "application"}, (
                        f"{file_path.name} 越层 import: {module}（应用层仅可依赖 domain/application）"
                    )

    def test_no_local_protocol_definition_in_service(self) -> None:
        """服务文件内禁止本地定义 Protocol/Port 抽象（6-1/6-2 纪律沿袭）。"""
        service_src = (SRC_ROOT / "application" / "services" / "checkpoint_service.py").read_text(encoding="utf-8")
        tree = ast.parse(service_src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Protocol":
                        raise AssertionError(f"服务文件本地定义 Protocol: {node.name}（端口必须在 application/ports 注册）")


class TestPublishPointPlacement:
    """验证器 C——发布点落位守护（正向存在 + 负向四文件零引用——OD-4）。"""

    def test_publish_call_in_checkpoint_service(self) -> None:
        """正向：checkpoint 应用服务含 CheckpointReached 构造与 publish 调用。"""
        content = (SRC_ROOT / "application" / "services" / "checkpoint_service.py").read_text(encoding="utf-8")
        assert "CheckpointReached(" in content, "⑤步发布构造缺失"
        assert "_event_publisher.publish" in content, "发布调用缺失"

    def test_blm_planning_four_files_zero_reference(self) -> None:
        """负向：blm_planning 四文件零 CheckpointReached 引用（OD-4 零触碰）。"""
        for relative in BLM_PLANNING_FOUR_FILES:
            content = (SRC_ROOT / relative).read_text(encoding="utf-8")
            assert "CheckpointReached" not in content, f"{relative} 不得引用 CheckpointReached（发布点唯一落位——OD-4）"


class TestAxiomTwoChainGuard:
    """验证器 D——公理二链路守护（源码级调用序：take_notes 先于 compress）。

    compress→archive 序由 Task 2 单测调用序断言承载（运行时证据）；本验证器
    守护源码结构序（静态证据）——R2A-15 分工声明。
    """

    def test_take_notes_precedes_compress_in_source(self) -> None:
        """create_checkpoint 方法体内 take_notes 调用先于 compress 调用（源码序）。"""
        service_file = SRC_ROOT / "application" / "services" / "checkpoint_service.py"
        calls = _extract_method_order(service_file, "create_checkpoint")
        try:
            take_notes_index = calls.index("take_notes")
        except ValueError as error:
            raise AssertionError("create_checkpoint 无 take_notes 调用（公理二前置缺失）") from error
        try:
            compress_index = calls.index("compress")
        except ValueError as error:
            raise AssertionError("create_checkpoint 无 compress 调用（压缩步骤缺失）") from error
        assert take_notes_index < compress_index, "公理二违规：compress 调用先于 take_notes（压缩前必须持久化——系统公理二）"

    def test_verify_persisted_indirect_guarantee(self) -> None:
        """公理二校验的间接保证声明：ContextCompressor.compress 内置
        verify_persisted 前置校验（context_compressor.py 源码锚——零改动复用）。"""
        compressor_src = (SRC_ROOT / "domain" / "services" / "context_compressor.py").read_text(encoding="utf-8")
        assert "verify_persisted" in compressor_src, "ContextCompressor 前置校验缺失（公理二校验链断裂——3.x 既有资产回归）"
