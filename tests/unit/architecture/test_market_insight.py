"""Story 6-2 — 市场洞察类型化架构约束验证测试（SDD Task 6）。

四验证器（形态对齐 6-1 test_blm_planning_arch.py 验证器 A 形态）：
- 验证器 A：domain 零依赖（扩展后 blm_phases.py AST/import 扫描零第三方——
  structured_output 扩展为 dict[str, Any] | None 标准库形态承载）
- 验证器 B：Schema 落位（六类型化 Schema 仅存在于应用层
  blm_planning_prompts.py；src/domain/ 全目录零 pydantic import——结构
  断言 + 源码 grep 双形态）
- 验证器 C：扁平化守卫（本 Story 特有——六 Schema 全字段类型白名单
  {str, float, list[str]} 反射断言；model_fields 注解解析——嵌套
  BaseModel/list[dict]/Optional 即红）
- 验证器 D：服务分派零硬编码（run_insight_step 源码不含六 Schema 类名
  字面量——分派仅经 SSOT 映射 MARKET_INSIGHT_STEP_SCHEMA）

Run with:
    poetry run pytest tests/unit/architecture/test_market_insight.py -v
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

#: 6-2 扩展的 domain 文件（零第三方依赖红线覆盖面）
BLM_PHASES = SRC_ROOT / "domain" / "value_objects" / "blm_phases.py"

#: 六类型化 Schema 钦定落位（应用层——pydantic 边界合法域）
PROMPTS_MODULE = SRC_ROOT / "application" / "services" / "blm_planning_prompts.py"
SERVICE_MODULE = SRC_ROOT / "application" / "services" / "blm_planning_service.py"

#: 六 Schema 类名（独立构造字面量——验证器 B/C/D 共用）
TYPED_SCHEMA_NAMES: tuple[str, ...] = (
    "TrendInsightSchema",
    "MarketCustomerInsightSchema",
    "CompetitionInsightSchema",
    "SelfInsightSchema",
    "OpportunityInsightSchema",
    "OpportunityGapInsightSchema",
)

#: 第三方黑名单（6-1 test_blm_planning_arch.py 先例集合）
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

#: domain 零依赖合法顶层（标准库 + src 同层引用判别）
_DOMAIN_ALLOWED_TOP_LEVELS: frozenset[str] = frozenset({"src", "__future__"} | set(sys.stdlib_module_names))


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


# ===================================================================
# 验证器 A：domain 零依赖（扩展后复核）
# ===================================================================


class TestDomainZeroDependencies:
    """验证器 A：blm_phases.py 扩展后仍纯标准库（六边形红线）。"""

    def test_blm_phases_exists(self) -> None:
        """交付件在位。"""
        assert BLM_PHASES.is_file(), f"缺少 domain 交付件: {BLM_PHASES}"

    def test_no_third_party_imports(self) -> None:
        """黑名单零命中（pydantic 对象渗入防线——structured_output 用标准库 dict 承载）。"""
        for module in _extract_imports(BLM_PHASES):
            top = module.split(".")[0]
            assert top not in FORBIDDEN_IMPORTS, f"blm_phases.py 引入第三方依赖: {module}（domain 零外部依赖红线）"

    def test_only_stdlib_and_domain_layer(self) -> None:
        """仅标准库 + src.domain 同层引用（不反向依赖 application/infrastructure）。"""
        for module in _extract_imports(BLM_PHASES):
            if module == "__future__":
                continue
            if module.startswith("src."):
                second = module.split(".")[1]
                assert second == "domain", f"blm_phases.py 反向依赖: {module}（domain 只能依赖 domain）"
            else:
                assert module.split(".")[0] in _DOMAIN_ALLOWED_TOP_LEVELS - {"src"}, f"blm_phases.py 非标准库 import: {module}"

    def test_structured_output_is_stdlib_annotation(self) -> None:
        """structured_output 字段注解为标准库形态 dict[str, Any] | None（非 pydantic 类型）。

        实锚形态（R1-F9）：get_type_hints 解析类型 + dataclasses.fields 取默认值——
        注解漂移（如改 Optional[dict] 形态）与默认值漂移双红，注释/文档字符串
        同文不再误绿。
        """
        import dataclasses
        import sys as _sys
        from typing import Any, get_type_hints

        _sys.path.insert(0, str(SRC_ROOT.parent))
        from src.domain.value_objects.blm_phases import InsightStepResult

        hints = get_type_hints(InsightStepResult)
        assert hints["structured_output"] == dict[str, Any] | None, (
            f"structured_output 注解应为 dict[str, Any] | None（实测 {hints['structured_output']}——R1 两层声明）"
        )
        field_map = {f.name: f for f in dataclasses.fields(InsightStepResult)}
        assert "structured_output" in field_map, "structured_output 字段缺失"
        assert field_map["structured_output"].default is None, "structured_output 默认值应为 None（6-1 兼容形态）"


# ===================================================================
# 验证器 B：Schema 落位（六类型化 Schema 仅应用层）
# ===================================================================


class TestSchemaPlacement:
    """验证器 B：pydantic Schema 仅存在于应用层（domain 全目录零 pydantic）。"""

    def test_six_schemas_defined_only_in_prompts_module(self) -> None:
        """结构断言：六类定义仅出现在 blm_planning_prompts.py（class 语句级）。"""
        for py_file in SRC_ROOT.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for name in TYPED_SCHEMA_NAMES:
                if f"class {name}(" in content:
                    assert py_file == PROMPTS_MODULE, (
                        f"{name} 定义越界: {py_file}（钦定落位 blm_planning_prompts.py——pydantic 仅应用层）"
                    )

    def test_domain_directory_zero_pydantic_import(self) -> None:
        """源码 grep 形态：src/domain/ 全目录零 pydantic import（六边形红线双承载）。"""
        for py_file in (SRC_ROOT / "domain").rglob("*.py"):
            for module in _extract_imports(py_file):
                assert module.split(".")[0] != "pydantic", f"{py_file.relative_to(SRC_ROOT)} 引入 pydantic（domain 零依赖红线）"

    def test_six_schemas_exported(self) -> None:
        """六类均在 __all__ 导出（模块契约完整性——import 实锚形态，R1-F9）。

        直接 import 模块断言成员资格：从 __all__ 删除某名时必红（源文件任何
        带引号字符串不再误绿）。
        """
        import sys as _sys

        _sys.path.insert(0, str(SRC_ROOT.parent))
        from src.application.services import blm_planning_prompts as prompts_module

        exported = set(prompts_module.__all__)
        for name in TYPED_SCHEMA_NAMES:
            assert name in exported, f"{name} 未在 __all__ 导出"

    def test_ssot_mapping_in_prompts_module(self) -> None:
        """SSOT 映射 MARKET_INSIGHT_STEP_SCHEMA 定义于 prompts 模块（形态 A 独立 dict）。"""
        content = PROMPTS_MODULE.read_text(encoding="utf-8")
        assert "MARKET_INSIGHT_STEP_SCHEMA: dict[MarketInsightStep, type[BaseModel]]" in content, (
            "SSOT 映射形态 A 钦定：独立 dict[MarketInsightStep, type[BaseModel]]（Subtask 0.1）"
        )


# ===================================================================
# 验证器 C：扁平化守卫（本 Story 特有——OD-5）
# ===================================================================


class TestFlatSchemaGuard:
    """验证器 C：六 Schema 全字段类型白名单 {str, float, list[str]}（声明面同集——R1-5）。"""

    def test_all_fields_within_whitelist(self) -> None:
        """model_fields 注解解析——嵌套 BaseModel/list[dict]/Optional 即红
        （GLM-5.3 anthropic 端点嵌套 Schema 服务端栈溢出——OD-5）。"""
        import sys as _sys

        _sys.path.insert(0, str(SRC_ROOT.parent))
        from src.application.services.blm_planning_prompts import (
            CompetitionInsightSchema,
            MarketCustomerInsightSchema,
            OpportunityGapInsightSchema,
            OpportunityInsightSchema,
            SelfInsightSchema,
            TrendInsightSchema,
        )

        whitelist = {str, float, list[str]}
        # 显式联合类型注解：保留具体类身份（裸推导会 join 成 type[BaseModel]，
        # mypy 对其 model_fields 访问报 ModelMetaclass attr-defined——R1 修复）
        typed_schema_union = (
            type[TrendInsightSchema]
            | type[MarketCustomerInsightSchema]
            | type[CompetitionInsightSchema]
            | type[SelfInsightSchema]
            | type[OpportunityInsightSchema]
            | type[OpportunityGapInsightSchema]
        )
        all_schemas: dict[str, typed_schema_union] = {
            "TrendInsightSchema": TrendInsightSchema,
            "MarketCustomerInsightSchema": MarketCustomerInsightSchema,
            "CompetitionInsightSchema": CompetitionInsightSchema,
            "SelfInsightSchema": SelfInsightSchema,
            "OpportunityInsightSchema": OpportunityInsightSchema,
            "OpportunityGapInsightSchema": OpportunityGapInsightSchema,
        }
        for name, schema_cls in all_schemas.items():
            for field_name, field in schema_cls.model_fields.items():
                annotation = field.annotation
                matched = any(annotation == allowed for allowed in whitelist)
                assert matched, (
                    f"{name}.{field_name} 注解 {annotation} 越出扁平化白名单 {{str, float, list[str]}}"
                    f"（OD-5——嵌套/Optional/int 禁入；与 AC-1 声明面同集）"
                )

    def test_no_nested_model_types(self) -> None:
        """无嵌套 BaseModel 字段（结构断言——注解源类不是 BaseModel 子类）。"""
        from pydantic import BaseModel

        from src.application.services.blm_planning_prompts import MARKET_INSIGHT_STEP_SCHEMA

        for schema_cls in MARKET_INSIGHT_STEP_SCHEMA.values():
            for field in schema_cls.model_fields.values():
                annotation = field.annotation
                if isinstance(annotation, type):
                    assert not issubclass(annotation, BaseModel), (
                        f"{schema_cls.__name__} 字段注解 {annotation.__name__} 是嵌套 BaseModel（OD-5 禁入）"
                    )


# ===================================================================
# 验证器 D：服务分派零硬编码
# ===================================================================


class TestServiceDispatchZeroHardcode:
    """验证器 D：run_insight_step 分派仅经 SSOT 映射（防 if-else 硬编码回潮）。"""

    def test_run_insight_step_source_no_schema_literals(self) -> None:
        """run_insight_step 源码不含六 Schema 类名字面量（分派仅经查表）。"""
        import inspect

        from src.application.services.blm_planning_service import BlmPlanningService

        source = inspect.getsource(BlmPlanningService.run_insight_step)
        for name in TYPED_SCHEMA_NAMES:
            assert name not in source, f"run_insight_step 含 {name} 字面量（分派应仅经 MARKET_INSIGHT_STEP_SCHEMA 查表——AC-1）"

    def test_dispatch_via_ssot_mapping(self) -> None:
        """分派语句经 SSOT 映射（查表存在性锚）。"""
        import inspect

        from src.application.services.blm_planning_service import BlmPlanningService

        source = inspect.getsource(BlmPlanningService.run_insight_step)
        assert "MARKET_INSIGHT_STEP_SCHEMA[step]" in source, (
            "run_insight_step 应经 MARKET_INSIGHT_STEP_SCHEMA[step] 查表分派（SSOT 映射——AC-1）"
        )

    def test_structured_output_filled_from_model_dump(self) -> None:
        """structured_output 填充经 model_dump（信封挂载锚）。"""
        import inspect

        from src.application.services.blm_planning_service import BlmPlanningService

        source = inspect.getsource(BlmPlanningService.run_insight_step)
        assert "structured_output=schema_result.model_dump()" in source, (
            "structured_output 应以 schema_result.model_dump() 填充（AC-1 扁平化挂载）"
        )
