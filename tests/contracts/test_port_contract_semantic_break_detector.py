"""SemanticBreakDetector 端口契约测试

验证 SemanticBreakDetector Protocol 的合规性。
端口实现推迟至 Epic 3 Story 3.7 检索评估数据触发。
"""

from __future__ import annotations

import inspect

from src.domain.ports.semantic_break_detector import SemanticBreakDetector


class TestSemanticBreakDetectorContract:
    """测试 SemanticBreakDetector 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(SemanticBreakDetector, "_is_runtime_protocol")
        assert SemanticBreakDetector._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_protocol_inherits_protocol(self) -> None:
        """验证继承自 Protocol

        通过检查 _is_protocol 属性验证 Protocol 合规性。
        Protocol 是 typing special form，issubclass 在 mypy 下有类型兼容问题，
        故改用属性检查代替。
        """
        assert hasattr(SemanticBreakDetector, "_is_protocol")

    def test_detect_breaks_method_exists(self) -> None:
        """验证 detect_breaks 方法存在"""
        assert hasattr(SemanticBreakDetector, "detect_breaks")
        method = getattr(SemanticBreakDetector, "detect_breaks")
        assert callable(method)

    def test_detect_breaks_method_signature(self) -> None:
        """验证 detect_breaks 方法签名"""
        method = getattr(SemanticBreakDetector, "detect_breaks")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "segments" in params
        assert "threshold" in params
        # 检查参数顺序
        assert params == ["self", "segments", "threshold"]

    def test_detect_breaks_return_type(self) -> None:
        """验证 detect_breaks 返回类型"""
        method = getattr(SemanticBreakDetector, "detect_breaks")
        sig = inspect.signature(method)
        assert sig.return_annotation == "list[int]"

    def test_detect_breaks_is_async(self) -> None:
        """验证 detect_breaks 是异步方法"""
        method = getattr(SemanticBreakDetector, "detect_breaks")
        assert inspect.iscoroutinefunction(method)

    def test_detect_breaks_threshold_default(self) -> None:
        """验证 threshold 参数默认值为 0.65"""
        method = getattr(SemanticBreakDetector, "detect_breaks")
        sig = inspect.signature(method)
        threshold_param = sig.parameters["threshold"]
        assert threshold_param.default == 0.65

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockDetector:
            """模拟合规实现"""

            async def detect_breaks(
                self,
                segments: list[str],
                threshold: float = 0.65,
            ) -> list[int]:
                return []

        detector = MockDetector()
        assert isinstance(detector, SemanticBreakDetector)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadDetector:
            """缺少 detect_breaks 方法"""

            pass

        detector = BadDetector()
        assert not isinstance(detector, SemanticBreakDetector)

    def test_domain_layer_zero_external_deps(self) -> None:
        """验证端口文件仅使用标准库和领域层类型"""
        import ast
        from pathlib import Path

        port_file = Path("src/domain/ports/semantic_break_detector.py")
        with open(port_file) as f:
            tree = ast.parse(f.read())

        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        # 允许的导入：标准库 + typing + src.domain 内部
        allowed = {"__future__", "typing", "src", "abc", "collections", "dataclasses", "enum", "inspect"}
        external = imports - allowed

        # src.domain 内部模块是允许的
        external = {m for m in external if not m.startswith("src")}

        assert not external, f"领域端口引入了外部依赖: {external}"


__all__ = ["TestSemanticBreakDetectorContract"]
