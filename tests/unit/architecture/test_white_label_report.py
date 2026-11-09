"""Story 6-11 白标报告基础——SDD 架构约束验证（四验证器——白名单形态）.

与 6-9/6-10「纯三零」形态分立：本 Story 是 6-5a/6-5b 同构的全层 Story（合法
domain/application/infrastructure 增量），验证器 C 采用 **白名单形态**（OD-14）：
白名单=三层全量合法 brand 词族新文件集 8 个 .py（domain 2+application 4+
infra 2；fonts 资产文件名无 brand 词族归目录单列）+渲染器修改既有单列——
**集合等值比较（==）双向判别**（漏列红+多列红——`<=` 子集比较多列静默）。

Run with:
    poetry run pytest tests/unit/architecture/test_white_label_report.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
PORT_FILE = SRC_ROOT / "application" / "ports" / "brand_template.py"
PDF_PORT_FILE = SRC_ROOT / "application" / "ports" / "pdf_report.py"
SERVICE_FILE = SRC_ROOT / "application" / "services" / "brand_template_service.py"
SAVE_USE_CASE_FILE = SRC_ROOT / "application" / "use_cases" / "save_brand_template.py"
LIST_USE_CASE_FILE = SRC_ROOT / "application" / "use_cases" / "list_brand_templates.py"
ENTITY_FILE = SRC_ROOT / "domain" / "entities" / "brand_template.py"
REPOSITORY_PORT_FILE = SRC_ROOT / "domain" / "ports" / "brand_template_repository.py"
MODEL_FILE = SRC_ROOT / "infrastructure" / "storage" / "postgresql" / "models" / "brand_template.py"
REPO_IMPL_FILE = SRC_ROOT / "infrastructure" / "storage" / "postgresql" / "repository" / "brand_template_repository.py"
RENDERER_FILE = SRC_ROOT / "infrastructure" / "reporting" / "reportlab_pdf_renderer.py"
CLI_ENTRY = SRC_ROOT / "entrypoints" / "agent_cli.py"
COMPOSITION_ROOT = SRC_ROOT / "composition_root.py"

#: 服务层 src.* import 白名单前缀（六边形方向：application→application/domain）
SERVICE_ALLOWED_PREFIXES: tuple[str, ...] = ("src.application.", "src.domain.")

#: 禁第三方 import（domain 零依赖纪律的实体/端口面）
FORBIDDEN_IMPORTS: frozenset[str] = frozenset({"pydantic", "sqlalchemy", "redis", "asyncpg", "reportlab"})


def _imports_of(path: Path) -> set[str]:
    """AST 解析模块级 import 名集合（from X import Y 取 X；import X.Y 取 X.Y）."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


class TestVerifierAPlacement:
    """验证器 A：交付文件落位守护（三层落位+VO/端口/常量 AST 断言）."""

    def test_delivery_files_exist_per_layer(self) -> None:
        """八交付文件三层落位（domain 2+application 4+infra 2——OD-14 白名单集成员）."""
        for path in (
            ENTITY_FILE,
            REPOSITORY_PORT_FILE,
            PORT_FILE,
            SERVICE_FILE,
            SAVE_USE_CASE_FILE,
            LIST_USE_CASE_FILE,
            MODEL_FILE,
            REPO_IMPL_FILE,
        ):
            assert path.is_file(), f"交付文件缺失: {path}"

    def test_entity_and_ports_class_definitions(self) -> None:
        """实体+双端口+预设常量+VO 的 AST 定义断言（BrandTemplate 实体/
        BrandTemplateRepositoryProtocol/BrandTemplateServicePort/
        BrandRenderSpec/ColorSchemePreset/FontPreset 类定义与常量在位）."""
        entity_tree = ast.parse(ENTITY_FILE.read_text(encoding="utf-8"))
        entity_classes = {node.name for node in ast.walk(entity_tree) if isinstance(node, ast.ClassDef)}
        assert "BrandTemplate" in entity_classes

        repo_port_tree = ast.parse(REPOSITORY_PORT_FILE.read_text(encoding="utf-8"))
        repo_classes = {node.name for node in ast.walk(repo_port_tree) if isinstance(node, ast.ClassDef)}
        assert "BrandTemplateRepositoryProtocol" in repo_classes

        port_tree = ast.parse(PORT_FILE.read_text(encoding="utf-8"))
        port_classes = {node.name for node in ast.walk(port_tree) if isinstance(node, ast.ClassDef)}
        for expected in ("ColorSchemePreset", "FontPreset", "BrandTemplateServicePort"):
            assert expected in port_classes, f"{expected} 应定义于 application ports 文件"
        assignment_targets = set()
        for node in ast.walk(port_tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assignment_targets.add(node.target.id)
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                assignment_targets.add(node.targets[0].id)
        for constant_name in ("COLOR_SCHEME_PRESETS", "FONT_PRESETS", "BRAND_ASSETS_BUCKET_TYPE"):
            assert constant_name in assignment_targets, f"{constant_name} 应定义于 ports 文件"

        pdf_port_tree = ast.parse(PDF_PORT_FILE.read_text(encoding="utf-8"))
        pdf_port_classes = {node.name for node in ast.walk(pdf_port_tree) if isinstance(node, ast.ClassDef)}
        assert "BrandRenderSpec" in pdf_port_classes, "BrandRenderSpec 应定义于 pdf_report ports 文件"

    def test_domain_layer_zero_third_party(self) -> None:
        """domain 交付（实体+仓储端口）零第三方 import（import-linter 之外的测试面双保险）."""
        for path in (ENTITY_FILE, REPOSITORY_PORT_FILE):
            root_modules = {name.split(".")[0] for name in _imports_of(path)}
            for root in root_modules:
                assert root not in FORBIDDEN_IMPORTS, f"{path.name} 禁第三方依赖: {root}"

    def test_service_imports_within_hexagonal_whitelist(self) -> None:
        """服务 src.* import 白名单（application→application/domain——六边形方向）."""
        imports = _imports_of(SERVICE_FILE)
        src_imports = {name for name in imports if name.startswith("src.")}
        assert src_imports, "服务应含 src 依赖（空集即锚失效）"
        for name in sorted(src_imports):
            assert name.startswith(SERVICE_ALLOWED_PREFIXES), f"依赖方向违例: {name}（白名单外）"

    def test_use_case_import_direction(self) -> None:
        """双用例 import 方向（application→application/domain 禁越层）."""
        for path in (SAVE_USE_CASE_FILE, LIST_USE_CASE_FILE):
            imports = _imports_of(path)
            src_imports = {name for name in imports if name.startswith("src.")}
            assert src_imports, "用例应含 src 依赖（空集即锚失效）"
            for name in sorted(src_imports):
                assert name.startswith(("src.application.", "src.domain.")), f"用例依赖方向违例: {name}"


class TestVerifierBZeroPublish:
    """验证器 B：品牌模板服务零事件发布守护（配置面零订阅方——OD-2 零事件第十连）."""

    def test_service_source_zero_publish_tokens(self) -> None:
        """服务源码 publish token 零出现（品牌配置面零事件）。"""
        source = SERVICE_FILE.read_text(encoding="utf-8")
        for token in ("publish", "event_publisher"):
            assert token not in source, f"品牌服务应零 {token}（OD-2 零事件第十连）"

    def test_service_source_zero_domain_event_construction(self) -> None:
        """服务 AST 零领域事件构造（pkgutil 全子模块导入后 DomainEvent 子类全集比对）."""
        import importlib
        import pkgutil

        import src.domain.events as events_pkg
        from src.domain.events.base import DomainEvent

        for module_info in pkgutil.iter_modules(events_pkg.__path__):
            importlib.import_module(f"{events_pkg.__name__}.{module_info.name}")
        assert hasattr(events_pkg, "RAGIndexed"), "事件包导入 sanity：RAGIndexed 应在位"

        def _walk_subclasses(cls: type) -> set[str]:
            names: set[str] = set()
            for sub in cls.__subclasses__():
                names.add(sub.__name__)
                names |= _walk_subclasses(sub)
            return names

        event_names = _walk_subclasses(DomainEvent)
        module_tree = ast.parse(SERVICE_FILE.read_text(encoding="utf-8"))
        for node in ast.walk(module_tree):
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
                if called is not None and called in event_names:
                    raise AssertionError(f"品牌服务禁事件构造位: {called}（行 {node.lineno}）")


class TestVerifierCBrandWhitelist:
    """验证器 C：brand 词族文件白名单形态（OD-14——三层全量 8 文件+fonts 目录+渲染器单列；
    与 6-9/6-10「纯三零」形态分立：本 Story 有合法 infra 增量）。"""

    def test_brand_word_files_exactly_whitelisted(self) -> None:
        """src 全仓 brand 词族文件 == 白名单 8 .py + 渲染器既有单列（集合等值==双向判别：
        漏列红+多列红——`<=` 子集比较多列静默无判别）。"""
        expected = {
            "src/domain/entities/brand_template.py",
            "src/domain/ports/brand_template_repository.py",
            "src/application/ports/brand_template.py",
            "src/application/services/brand_template_service.py",
            "src/application/use_cases/save_brand_template.py",
            "src/application/use_cases/list_brand_templates.py",
            "src/infrastructure/storage/postgresql/models/brand_template.py",
            "src/infrastructure/storage/postgresql/repository/brand_template_repository.py",
        }
        actual = {
            str(path.relative_to(SRC_ROOT.parent))
            for path in SRC_ROOT.rglob("*.py")
            if "brand" in path.name or "brand" in str(path.relative_to(SRC_ROOT)).lower()
        }
        # 渲染器是修改既有文件（文件名无 brand 词族）——单列不在此集合
        assert actual == expected, f"brand 词族文件集漂移：多列 {actual - expected} / 漏列 {expected - actual}"

    def test_fonts_asset_directory_in_place(self) -> None:
        """fonts 资产目录单列（资产文件名无 brand 词族不入白名单集——OD-14 目录单列）。"""
        fonts_dir = SRC_ROOT / "infrastructure" / "reporting" / "fonts"
        assert fonts_dir.is_dir(), "fonts 资产目录缺失"
        ttf_files = list(fonts_dir.glob("*.ttf"))
        assert ttf_files, "fonts 目录应含 TTF 资产"

    def test_renderer_brand_extension_in_place(self) -> None:
        """渲染器品牌三件扩展在场（platypus.Image 导入+TTFont 注册通道+brand 参数——
        修改既有文件单列的运行面锚）."""
        source = RENDERER_FILE.read_text(encoding="utf-8")
        assert "TTFont" in source, "渲染器缺 TTFont 注册通道（品牌字体三件之一）"
        assert "ImageReader" in source, "渲染器缺 ImageReader（logo 位图三件之一）"
        assert "brand: BrandRenderSpec | None = None" in source, "渲染器缺 brand 可选参"

    def test_domain_new_files_still_hexagonal(self) -> None:
        """domain 层新增面仍守六边形（实体+端口零第三方——与 6-9/6-10 纯三零的 domain 面同标）."""
        # 已由 test_domain_layer_zero_third_party 承载——本用例是白名单形态的结构对称位
        assert ENTITY_FILE.is_file() and REPOSITORY_PORT_FILE.is_file()


class TestVerifierDCLIWiring:
    """验证器 D：CLI 品牌命令族接线（缩进敏感精确锚+组合根注册锚）."""

    def test_cli_has_brand_template_save_subcommand(self) -> None:
        """agent_cli.py 含 brand-template-save add_parser 注册（8 空格缩进逐字锚）。"""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert 'add_parser(\n        "brand-template-save"' in source, "CLI 缺 brand-template-save 注册（缩进敏感锚）"
        assert 'add_parser(\n        "brand-template-list"' in source, "CLI 缺 brand-template-list 注册（缩进敏感锚）"

    def test_cli_report_generate_brand_parameter(self) -> None:
        """report-generate --brand-template 扩展参数锚（同入口扩展——OD-7）。"""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert '"--brand-template"' in source, "CLI 缺 --brand-template 参数定义"

    def test_cli_dispatch_branches_resolve_use_cases(self) -> None:
        """分发分支+use_case resolve 调用锚（接线完整性）。"""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert 'args.command == "brand-template-save"' in source
        assert 'args.command == "brand-template-list"' in source
        assert 'resolve("save_brand_template_use_case")' in source
        assert 'resolve("list_brand_templates_use_case")' in source

    def test_composition_root_four_new_registrations(self) -> None:
        """组合根 4 新注册块锚（注册名+session_factory/l4/服务依赖注入链）。"""
        source = COMPOSITION_ROOT.read_text(encoding="utf-8")
        for name in (
            "brand_template_repository",
            "brand_template_service",
            "save_brand_template_use_case",
            "list_brand_templates_use_case",
        ):
            assert f'name="{name}"' in source, f"组合根缺 {name} 注册"
        assert 'resolver.resolve("session_factory")' in source, "仓储注册缺 session_factory 注入锚"

    def test_composition_root_three_version_upgrades(self) -> None:
        """组合根 3 处版本升级锚（v1.1.0+compatibility——pdf_renderer/pdf 服务/consultant_view）。"""
        source = COMPOSITION_ROOT.read_text(encoding="utf-8")
        upgrade_anchors = (
            'name="pdf_renderer"',
            'name="pdf_report_generation_service"',
            'name="consultant_view_service"',
        )
        for anchor in upgrade_anchors:
            block = source.split(anchor)[1].split("register_port(")[0]
            assert 'version="v1.1.0"' in block, f"{anchor} 块缺 v1.1.0 版本"
            assert 'compatibility=("v1.0.0",)' in block, f"{anchor} 块缺兼容元组"
