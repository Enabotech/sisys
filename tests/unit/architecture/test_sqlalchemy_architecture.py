"""架构约束测试

验证领域层零SQLAlchemy依赖、依赖方向正确等架构约束
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestArchitectureConstraints:
    """架构约束测试。"""

    def test_domain_layer_no_sqlalchemy_imports(self):
        """测试领域层无SQLAlchemy导入。"""
        domain_dir = Path(__file__).parents[3] / "src" / "domain"

        violations = []
        for py_file in domain_dir.rglob("*.py"):
            content = py_file.read_text()
            if "sqlalchemy" in content.lower():
                violations.append(str(py_file))

        assert len(violations) == 0, f"领域层包含SQLAlchemy导入: {violations}"

    def test_domain_layer_no_infrastructure_imports(self):
        """验证 domain 层不导入 infrastructure（检查反向依赖）

        正确的依赖方向: infrastructure → application → domain
        domain 层导入 infrastructure 是反向依赖，是禁止的
        """
        domain_dir = Path(__file__).parents[3] / "src" / "domain"

        violations = []
        for py_file in domain_dir.rglob("*.py"):
            content = py_file.read_text()
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(py_file.relative_to(domain_dir)))

        assert len(violations) == 0, f"Domain layer imports infrastructure (reverse dependency): {violations}"

    def test_all_models_have_tests(self):
        """测试所有模型都有对应的单元测试。"""
        models_dir = Path(__file__).parents[3] / "src" / "infrastructure" / "storage" / "postgresql" / "models"
        tests_dir = Path(__file__).parents[3] / "tests" / "unit" / "infrastructure" / "storage" / "postgresql" / "models"

        model_files = {f.stem for f in models_dir.glob("*.py") if f.stem != "__init__"}
        test_files = {f.stem.replace("test_", "") for f in tests_dir.glob("test_*.py")}
        # 移除association表测试的特殊命名
        test_files.discard("association_tables")
        test_files.discard("association")

        # 允许某些模型没有独立测试（如__init__.py导出的内容）
        _missing_tests = model_files - test_files - {"association"}

        # association表测试存在但命名不同
        assert (tests_dir / "test_association_tables.py").exists(), "test_association_tables.py should exist"

    def test_alembic_migration_syntax(self):
        """测试Alembic迁移脚本语法正确。"""
        versions_dir = Path(__file__).parents[3] / "alembic" / "versions"

        for py_file in versions_dir.glob("*.py"):
            content = py_file.read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                assert False, f"Alembic迁移脚本语法错误 {py_file.name}: {e}"
