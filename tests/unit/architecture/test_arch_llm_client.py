"""LLM 客户端架构约束测试

验证六边形架构约束：
- 领域层零外部依赖
- LLMClientPort 位于领域层
- LitellmLLMClient 位于基础设施层
- 依赖方向正确（infrastructure → domain）
"""

from __future__ import annotations

import ast

from src.domain.ports.llm_client import LLMClientPort


class TestArchLLMClient:
    """LLM 客户端架构约束测试"""

    DOMAIN_PORT_PATH = "src/domain/ports/llm_client.py"
    INFRA_LLM_DIR = "src/infrastructure/external_services/llm"

    def test_domain_port_zero_external_dependencies(self) -> None:
        """验证 src/domain/ports/llm_client.py 零外部依赖（仅标准库）"""
        import os

        filepath = self.DOMAIN_PORT_PATH
        root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
        full_path = os.path.abspath(os.path.join(root, filepath))

        with open(full_path, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # 允许标准库和 src 项目内部导入
                    if not alias.name.startswith("src.") and not alias.name.startswith(
                        ("typing", "dataclasses", "os", "abc", "__future__", "re", "enum", "uuid", "inspect")
                    ):
                        raise AssertionError(f"领域层禁止外部依赖: {alias.name} 在 {filepath} 中导入")
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.module
                    and not node.module.startswith("src.")
                    and not node.module.startswith(
                        ("typing", "dataclasses", "os", "abc", "__future__", "re", "enum", "uuid", "inspect")
                    )
                ):
                    # 允许相对导入
                    if not node.module.startswith("."):
                        raise AssertionError(f"领域层禁止外部依赖: {node.module} 在 {filepath} 中导入")

    def test_llm_client_port_in_domain_layer(self) -> None:
        """验证 LLMClientPort 位于领域层"""
        assert LLMClientPort.__module__.startswith("src.domain."), (
            f"LLMClientPort 应在领域层，实际位于 {LLMClientPort.__module__}"
        )

    def test_domain_does_not_import_infrastructure(self) -> None:
        """验证领域层不导入基础设施层"""
        import os

        root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
        domain_dir = os.path.abspath(os.path.join(root, "src", "domain"))

        for dirpath, _, filenames in os.walk(domain_dir):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                filepath = os.path.join(dirpath, filename)
                with open(filepath, encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        # 检查所有导入语句
                        module_parts = []
                        if isinstance(node, ast.ImportFrom):
                            module_parts = (node.module or "").split(".")
                        else:
                            for alias in node.names:
                                module_parts = alias.name.split(".")

                        if len(module_parts) >= 2 and module_parts[0] == "src" and module_parts[1] == "infrastructure":
                            raise AssertionError(
                                f"领域层禁止导入基础设施层: {filepath} 导入了 {getattr(node, 'module', node.names[0].name)}"
                            )
