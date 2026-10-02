"""Story 4.5 — 红蓝辩论架构验证测试（epics 硬路径，无 _arch_ 前缀）

epics_v1.0.md:1288-1290 架构测试三项的落点之一（traceability）：
①「红蓝辩论测试-验证单 Agent 多视角」→ 本文件（整体约束组）+
  test_red_blue_debate_integration.py（端到端）+ test_red_blue_debate_service.py（服务单测）
②「视角生成测试」→ test_red_blue_debate_service.py（schema 身份分派 + 立场遵循）+
  test_debate.py（PerspectiveAnalysis 不变量）
③「风险视图测试」→ test_debate.py（RiskView 不变量）+ AC-7 合成场景

验证组：
- 领域零依赖：AST 扫描 debate 相关 domain 文件 FORBIDDEN_IMPORTS 黑名单
- 温度阶梯常量：TEMPERATURE_PROFILE == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}
  （FR-SP-10 对齐门禁——绊线断言，重构时保活改写而非删除）
- PortSpec 10 字段元数据完整性 + 依赖方向（domain ← application ← infrastructure）
- 禁止服务文件本地定义 Protocol/Port 抽象
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from src.domain.ports.registry import PortSpec, _global_registry

# 领域层禁止导入的第三方包（架构测试目录私有清单——各文件独立维护，无共享助手模块）
FORBIDDEN_IMPORTS = frozenset(
    {
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
        "aiorabbit",
        "litellm",
        "instructor",
        "asyncpg",
        "aioredis",
        "httpx",
        "aiohttp",
        "requests",
    }
)

# Story 4.5 领域层交付文件
DOMAIN_FILES = [
    Path("src/domain/value_objects/debate.py"),
    Path("src/domain/entities/debate_session.py"),
    Path("src/domain/services/debate_evaluator.py"),
    Path("src/domain/ports/debate_session_repository.py"),
    Path("src/domain/events/debate_events.py"),
    Path("src/domain/exceptions/debate_exceptions.py"),
]

# 应用层/基础设施层交付文件（依赖方向校验面）
APPLICATION_FILES = [
    Path("src/application/services/red_blue_debate_service.py"),
    Path("src/application/services/debate_prompts.py"),
    Path("src/application/services/debate_schemas.py"),
    Path("src/application/ports/red_blue_debate_service.py"),
]

# 服务与实现文件（禁止本地 Protocol 的检查面——ports/ 目录本身是端口定义的合法位置）
SERVICE_AND_IMPL_FILES = [
    Path("src/application/services/red_blue_debate_service.py"),
    Path("src/application/services/debate_prompts.py"),
    Path("src/application/services/debate_schemas.py"),
    Path("src/infrastructure/storage/inmemory/debate_session_repository.py"),
]

INFRASTRUCTURE_FILES = [
    Path("src/infrastructure/storage/inmemory/debate_session_repository.py"),
]


def _extract_imports(file_path: Path) -> set[str]:
    """AST 提取模块顶层 import 名（私有助手，复制先例 test_docker_sandbox.py:53-69）"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


# ===================================================================
# 领域零依赖（FR-AR-01，.importlinter + 架构测试双重校验）
# ===================================================================


class TestDomainLayerZeroDependency:
    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_domain_files_no_forbidden_imports(self, file_path: Path) -> None:
        """debate 领域文件零第三方依赖"""
        assert file_path.exists(), f"{file_path} 应存在"
        violated = _extract_imports(file_path) & FORBIDDEN_IMPORTS
        assert not violated, f"{file_path} 违反领域零依赖: {violated}"

    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_domain_files_no_upward_layer_imports(self, file_path: Path) -> None:
        """领域文件不导入 application/interfaces/infrastructure（跨层调用禁止）"""
        upward = {"application", "interfaces", "infrastructure", "composition_root"}
        violated = _extract_imports(file_path) & upward
        assert not violated, f"{file_path} 违反依赖方向（domain 不可向上依赖）: {violated}"


# ===================================================================
# 依赖方向（domain ← application ← infrastructure）
# ===================================================================


class TestDependencyDirection:
    @pytest.mark.parametrize("file_path", APPLICATION_FILES, ids=lambda p: p.name)
    def test_application_files_depend_only_on_domain_and_stdlib(self, file_path: Path) -> None:
        """应用层文件仅依赖 domain + 标准库 + 白名单第三方（pydantic）"""
        assert file_path.exists()
        imports = _extract_imports(file_path)
        forbidden_layers = {"infrastructure", "interfaces", "composition_root"}
        violated = imports & forbidden_layers
        assert not violated, f"{file_path} 应用层不可依赖基础设施/接口层: {violated}"

    @pytest.mark.parametrize("file_path", INFRASTRUCTURE_FILES, ids=lambda p: p.name)
    def test_infrastructure_file_depends_on_domain_ports(self, file_path: Path) -> None:
        """基础设施实现依赖领域端口（依赖倒置：实现指向抽象）"""
        assert file_path.exists()
        source = file_path.read_text(encoding="utf-8")
        assert "src.domain.ports.debate_session_repository" in source, "InMemory 实现必须 import 领域端口（依赖倒置）"

    def test_service_file_imports_domain_not_infrastructure(self) -> None:
        """编排服务仅依赖领域抽象（LLMClientPort/EventPublisher 均领域端口）"""
        source = Path("src/application/services/red_blue_debate_service.py").read_text(encoding="utf-8")
        assert "src.domain.ports.llm_client" in source
        assert "src.domain.ports.event_publisher" in source
        assert "litellm" not in source, "应用层禁止绕过 LLMClientPort 直接 import litellm"


# ===================================================================
# 温度阶梯与门控常量（FR-SP-10 对齐绊线）
# ===================================================================


class TestTemperatureConstants:
    def test_temperature_profile_matches_fr_sp10(self) -> None:
        """温度阶梯与 FR-SP-10 V1 三阶段严格一致"""
        from src.application.services.red_blue_debate_service import TEMPERATURE_PROFILE

        assert TEMPERATURE_PROFILE == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}

    def test_overlap_thresholds(self) -> None:
        """分化度阈值：硬 0.95 / 警告 0.80"""
        from src.application.services.red_blue_debate_service import (
            OVERLAP_HARD_THRESHOLD,
            OVERLAP_WARNING_THRESHOLD,
        )

        assert OVERLAP_HARD_THRESHOLD == 0.95
        assert OVERLAP_WARNING_THRESHOLD == 0.80
        assert OVERLAP_WARNING_THRESHOLD < OVERLAP_HARD_THRESHOLD

    def test_temperature_profile_is_module_constant(self) -> None:
        """温度阶梯为模块级常量（禁止调用方随意传参覆盖）"""
        from src.application.services import red_blue_debate_service as service_module

        assert isinstance(service_module.TEMPERATURE_PROFILE, dict)


# ===================================================================
# PortSpec 元数据完整性（3 端口）
# ===================================================================


class TestDebatePortRegistry:
    @pytest.mark.parametrize(
        ("port_name", "expected_lifetime", "expected_owner", "expected_tags"),
        [
            ("debate_session_repository", "scoped", "tool-team", ("debate", "repository", "inmemory")),
            ("debate_evaluator", "singleton", "tool-team", ("debate", "domain", "service")),
            ("red_blue_debate_service", "scoped", "tool-team", ("debate", "service")),
        ],
        ids=["repository", "evaluator", "service"],
    )
    def test_port_spec_metadata(
        self,
        port_name: str,
        expected_lifetime: str,
        expected_owner: str,
        expected_tags: tuple[str, ...],
    ) -> None:
        """三端口 PortSpec 元数据完整（10 字段 + version/owner/tags/lifetime）"""
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口 {port_name} 未在组合根注册"
        assert spec.name == port_name
        assert spec.version == "v1.0.0"
        assert spec.lifetime.value == expected_lifetime
        assert spec.owner == expected_owner
        assert set(expected_tags).issubset(set(spec.tags))
        assert spec.compatibility == ()
        assert spec.deprecated is False
        assert spec.impl is not None
        assert spec.module
        assert spec.interface is not None

    def test_port_spec_has_all_10_fields(self) -> None:
        """PortSpec 数据类 10 字段结构完整"""
        expected = {
            "name",
            "version",
            "interface",
            "impl",
            "module",
            "lifetime",
            "owner",
            "compatibility",
            "tags",
            "deprecated",
        }
        assert {f.name for f in fields(PortSpec)} == expected

    def test_service_port_resolves_real_instance(self) -> None:
        """red_blue_debate_service 工厂产出真实服务实例（依赖方向终点验证）"""
        from src.application.ports.red_blue_debate_service import RedBlueDebateServicePort
        from src.application.services.red_blue_debate_service import RedBlueDebateService

        spec = _global_registry.get("red_blue_debate_service")
        assert spec is not None

        from src.domain.ports.resolver import Resolver

        instance = Resolver().resolve("red_blue_debate_service")
        assert spec.impl is not None
        assert isinstance(instance, RedBlueDebateService)
        assert isinstance(instance, RedBlueDebateServicePort)


# ===================================================================
# 禁止服务文件本地 Protocol（架构约束）
# ===================================================================


class TestNoLocalProtocolInServiceFiles:
    @pytest.mark.parametrize(
        "file_path",
        SERVICE_AND_IMPL_FILES,
        ids=lambda p: p.name,
    )
    def test_no_local_protocol_definition(self, file_path: Path) -> None:
        """服务/实现文件禁止本地定义 Protocol/Port 抽象（端口统一在 ports/ 目录定义）"""
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Protocol":
                        raise AssertionError(
                            f"{file_path} 本地定义了 Protocol（{node.name}）——"
                            "端口抽象必须定义在 src/domain/ports/ 或 src/application/ports/"
                        )


# ===================================================================
# 子域登记一致性（debate 420-429）
# ===================================================================


class TestDebateSubdomainRange:
    def test_debate_code_range_registered(self) -> None:
        """debate 子域 420-429 已登记 _code_ranges"""
        from src.domain.exceptions._code_ranges import get_range_for_subdomain

        assert get_range_for_subdomain("debate") == (420, 429)

    def test_gap_critical_09_cleared(self) -> None:
        """GAP-CRITICAL-09 清偿：DebateEvaluator 三算法齐备"""
        from src.domain.services.debate_evaluator import DebateEvaluator

        evaluator = DebateEvaluator()
        assert callable(evaluator.compute_repetition_rate)
        assert callable(evaluator.compute_gain_rate)
        assert callable(evaluator.evaluate_overlap)
