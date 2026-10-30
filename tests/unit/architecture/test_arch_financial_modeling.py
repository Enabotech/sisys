"""SDD 架构约束验证：Story 5.12 财务建模与估值（四验证器 A/B/C/D）。

验证器 A：domain 两文件第三方 import 白名单空集（纯标准库——decimal/dataclasses/
statistics/typing 天然过 import-linter，比 sap 的 {pydantic} 更严）。
验证器 B：组合根外零实例化 + financial_exceptions 模块引用收窄（grep 口径：目标=
模块名字符串，白名单=异常注册三件 + tests/——引擎经包级 from src.domain.exceptions
import 转发导入不计）+ 三零断言（零事件/零 REST/零 catalog——OD-2/OD-3/OD-6 契约
承载）+ tests/fixtures/ 目录不存在可选断言（R5 缓解——防误建同名遮蔽 tests.fixtures
模块）。
验证器 C：Decimal 静态锚（两 domain 文件 from decimal import + calculate_dcf 签名
Decimal 注解）+ VO frozen 锚（11 类 @dataclass(frozen=True)）。
验证器 D：零抑制注释（交付文件五件 noqa/type: ignore/pylint: disable 零命中）。

Run with:
    poetry run pytest tests/unit/architecture/test_arch_financial_modeling.py -v
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"

#: domain 两交付文件（纯标准库白名单空集验证面）
VALUATION_FILE = SRC_DIR / "domain" / "value_objects" / "financial_valuation.py"
MODELING_FILE = SRC_DIR / "domain" / "services" / "financial_modeling.py"
#: 零抑制验证的交付文件五件（src 新建五件）
_SUPPRESSION_DELIVERY_FILES = [
    VALUATION_FILE,
    MODELING_FILE,
    SRC_DIR / "domain" / "exceptions" / "financial_exceptions.py",
    SRC_DIR / "application" / "services" / "financial_schemas.py",
    SRC_DIR / "application" / "use_cases" / "financial_modeling.py",
]
#: financial_exceptions 模块引用收窄白名单（异常注册三件——引擎/验收经包级转发导入不计）
_EXCEPTIONS_MODULE_ALLOWED = {
    "src/domain/exceptions/__init__.py",
    "src/domain/exceptions/_code_ranges.py",
    "src/interfaces/api/exception_handlers.py",
}


def _iter_python_files(root: Path) -> list[Path]:
    """遍历目录 Python 文件（跳过 __pycache__）。"""
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


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
    """全仓扫描目标类构造点（ast.Call——返回 path:lineno 清单）。"""
    sites: list[str] = []
    for python_file in _iter_python_files(SRC_DIR):
        tree = ast.parse(python_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                callee_name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if callee_name == target_class:
                    sites.append(f"{python_file.relative_to(REPO_ROOT)}:{node.lineno}")
    return sites


# ==== 验证器 A：domain 两文件第三方 import 白名单空集 ====


class TestValidatorAThirdPartyWhitelist:
    """domain 交付两文件纯标准库（第三方 import 白名单空集——比 sap 的 {pydantic} 更严）。"""

    @pytest.mark.parametrize("delivery_file", [VALUATION_FILE, MODELING_FILE], ids=["valuation", "modeling"])
    def test_file_exists(self, delivery_file: Path) -> None:
        """交付文件存在性。"""
        assert delivery_file.exists(), f"缺件: {delivery_file}"

    @pytest.mark.parametrize("delivery_file", [VALUATION_FILE, MODELING_FILE], ids=["valuation", "modeling"])
    def test_no_forbidden_third_party(self, delivery_file: Path) -> None:
        """第三方依赖白名单空集（非标准库且非 src 的 import 必须 ∈ ∅）。"""
        modules = _scan_file_top_imports(delivery_file)
        non_stdlib = {module for module in modules if module not in sys.stdlib_module_names and module != "src"}
        assert non_stdlib == set(), f"domain 文件不得含第三方依赖（白名单空集）: {non_stdlib}"

    @pytest.mark.parametrize("delivery_file", [VALUATION_FILE, MODELING_FILE], ids=["valuation", "modeling"])
    def test_stdlib_only_baseline(self, delivery_file: Path) -> None:
        """标准库基线（decimal/dataclasses/statistics/typing——import-linter 天然过）。"""
        modules = _scan_file_top_imports(delivery_file)
        assert "src" in modules, "domain 文件应 import src 领域模块（VO/异常）"
        assert modules - {"src"} <= sys.stdlib_module_names, "除 src 外必须全标准库"


# ==== 验证器 B：零实例化 + 引用收窄 + 三零 + fixtures 防遮蔽 ====


class TestValidatorBInstantiationAndBoundaries:
    """组合根外零实例化 + financial_exceptions 引用收窄 + 三零断言。"""

    def test_service_instantiation_only_in_composition_root_and_tests(self) -> None:
        """FinancialModelingService 构造点仅组合根（字符串 impl 注册——生产面零直接构造）。"""
        sites = _scan_instantiation_sites("FinancialModelingService")
        production_sites = [site for site in sites if not site.startswith("tests/")]
        assert all(site.startswith("src/composition_root.py") for site in production_sites), (
            f"组合根外生产实例化违例: {production_sites}（字符串 impl 语义下生产面应为空集或仅组合根）"
        )

    def test_use_case_instantiation_only_in_composition_root_and_tests(self) -> None:
        """FinancialModelingUseCase 构造点仅组合根 + tests/。"""
        sites = _scan_instantiation_sites("FinancialModelingUseCase")
        production_sites = [site for site in sites if not site.startswith("tests/")]
        assert all(site.startswith("src/composition_root.py") for site in production_sites), (
            f"组合根外生产实例化违例: {production_sites}"
        )

    def test_financial_exceptions_module_reference_narrowed(self) -> None:
        """financial_exceptions 模块名引用收窄（白名单=异常注册三件——引擎经包级转发导入不计）。"""
        offenders: list[str] = []
        for python_file in _iter_python_files(SRC_DIR):
            relative = python_file.relative_to(REPO_ROOT).as_posix()
            if relative in _EXCEPTIONS_MODULE_ALLOWED:
                continue
            if "financial_exceptions" in python_file.read_text(encoding="utf-8"):
                offenders.append(relative)
        assert offenders == [], f"financial_exceptions 引用越界（白名单外命中）: {offenders}"

    def test_zero_event_channel_entries(self) -> None:
        """三零之一：event_channels.yaml 零 financial 条目（计算服务无领域事件——DC-10）。"""
        event_channels = (REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
        assert "financial" not in event_channels, "零事件面违例：event_channels.yaml 含 financial"

    def test_zero_rest_paths(self) -> None:
        """三零之二：openapi.yaml 零 /financial 路径（OD-6——REST 面归 Story 20-1/20-2）。"""
        openapi_spec = (REPO_ROOT / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")
        assert "/financial" not in openapi_spec, "零 REST 面违例：openapi.yaml 含 /financial 路径"

    def test_zero_tool_catalog_entries(self) -> None:
        """三零之三：Tool catalog 与 Skills 零 financial 接入（OD-3——CFO 开放时整体接线）。"""
        catalog_source = (REPO_ROOT / "src" / "domain" / "entities" / "strategic_tool_catalog.py").read_text(encoding="utf-8")
        assert "FINANCIAL" not in catalog_source, "零 catalog 面违例：ToolCategory 含 FINANCIAL 枚举"
        skill_manifest = (REPO_ROOT / "src" / "application" / "skills" / "skill_manifest.py").read_text(encoding="utf-8")
        assert "financial" not in skill_manifest, "零 catalog 面违例：skill_manifest 含 financial slug"
        skills_dir = REPO_ROOT / "src" / "application" / "skills"
        financial_slugs = [child.name for child in skills_dir.iterdir() if "financial" in child.name.lower()]
        assert financial_slugs == [], f"零 catalog 面违例：skills/ 含 financial 目录 {financial_slugs}"

    def test_tests_fixtures_directory_absent(self) -> None:
        """tests/fixtures/ 目录不存在（R5 缓解——防 namespace package 遮蔽 tests.fixtures 模块回归）。"""
        fixtures_directory = REPO_ROOT / "tests" / "fixtures"
        assert not fixtures_directory.exists(), "tests/fixtures/ 目录不得存在（遮蔽 tests.fixtures 模块——OD-7）"


# ==== 验证器 C：Decimal 静态锚 + VO frozen 锚 ====


class TestValidatorCStaticAnchors:
    """Decimal 精度纪律静态锚 + VO frozen 锚。"""

    @pytest.mark.parametrize("delivery_file", [VALUATION_FILE, MODELING_FILE], ids=["valuation", "modeling"])
    def test_decimal_import_present(self, delivery_file: Path) -> None:
        """两 domain 文件含 from decimal import（Decimal 全程精度纪律——OD-5①）。"""
        source = delivery_file.read_text(encoding="utf-8")
        assert re.search(r"^from decimal import ", source, re.MULTILINE), "缺 from decimal import 静态锚"

    def test_engine_signatures_decimal_annotated(self) -> None:
        """引擎签名 Decimal 域（AST 注解检查——calculate_dcf 入参 VO 型 + 两统计法
        target_ebitda 裸参数注解 Decimal——输入零 float 钦定；CR1-9 补先例法对称锚）。"""
        tree = ast.parse(MODELING_FILE.read_text(encoding="utf-8"))
        methods = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "calculate_dcf" in methods, "calculate_dcf 方法缺失"
        assert "calculate_comparable_valuation" in methods, "calculate_comparable_valuation 方法缺失"
        assert "calculate_precedent_valuation" in methods, "calculate_precedent_valuation 方法缺失"
        # 两统计法 target_ebitda 均是引擎裸参数（非 VO 字段）——注解必须 Decimal（对称锚）
        for method_name in ("calculate_comparable_valuation", "calculate_precedent_valuation"):
            method_args = methods[method_name].args.args
            assert len(method_args) == 3, f"{method_name} 签名应为 (self, 集合, target_ebitda)"
            target_annotation_node = method_args[2].annotation
            assert target_annotation_node is not None, f"{method_name} 的 target_ebitda 注解缺失"
            target_annotation = ast.unparse(target_annotation_node)
            assert target_annotation == "Decimal", f"{method_name} 的 target_ebitda 注解应 Decimal，实测 {target_annotation}"
        # calculate_dcf 返回注解应为 DcfValuationResult（VO 域输出——字段全 Decimal）
        returns = methods["calculate_dcf"].returns
        assert returns is not None and "DcfValuationResult" in ast.unparse(returns), "返回注解应 DcfValuationResult"

    def test_vo_classes_all_frozen(self) -> None:
        """11 类 VO 全部 @dataclass(frozen=True)（不可变契约——schema_validator 先例）。"""
        tree = ast.parse(VALUATION_FILE.read_text(encoding="utf-8"))
        frozen_classes: set[str] = set()
        all_dataclasses: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and getattr(decorator.func, "id", "") == "dataclass":
                        all_dataclasses.add(node.name)
                        for keyword in decorator.keywords:
                            if keyword.arg == "frozen" and isinstance(keyword.value, ast.Constant) and keyword.value.value:
                                frozen_classes.add(node.name)
        assert len(all_dataclasses) == 11, f"VO 应 11 类，实测 {len(all_dataclasses)}: {sorted(all_dataclasses)}"
        assert all_dataclasses == frozen_classes, f"非 frozen VO: {all_dataclasses - frozen_classes}"

    def test_vo_class_names_complete(self) -> None:
        """11 类 VO 类名清单完备（数据模型节钦定清单）。"""
        tree = ast.parse(VALUATION_FILE.read_text(encoding="utf-8"))
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        expected = {
            "CashFlow",
            "CashFlowSchedule",
            "DcfAssumptions",
            "DcfValuationResult",
            "ComparableCompany",
            "ComparableSet",
            "MultiplesStats",
            "ComparableValuationResult",
            "PrecedentTransaction",
            "PrecedentTransactionSet",
            "PrecedentValuationResult",
        }
        assert expected <= class_names, f"VO 类缺失: {expected - class_names}"


# ==== 验证器 D：零抑制注释 ====


class TestValidatorDZeroSuppression:
    """交付文件五件零抑制注释（noqa/type: ignore/pylint: disable——红线 grep）。"""

    @pytest.mark.parametrize(
        "delivery_file",
        _SUPPRESSION_DELIVERY_FILES,
        ids=[path.name for path in _SUPPRESSION_DELIVERY_FILES],
    )
    def test_zero_suppression_comments(self, delivery_file: Path) -> None:
        """交付文件零抑制注释命中。"""
        source = delivery_file.read_text(encoding="utf-8")
        for marker in ("# noqa", "# type: ignore", "# pylint: disable"):
            assert marker not in source, f"抑制注释违例 {marker}: {delivery_file}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
