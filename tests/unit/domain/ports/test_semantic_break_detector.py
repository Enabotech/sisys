"""SemanticBreakDetector Protocol 合约测试。

验证运行时可检查协议的结构合规性：
- 必须包含 detect_breaks 方法
- 协议签名与文档一致
- runtime_checkable 能正确判断合规/不合规
"""

from __future__ import annotations

from src.domain.ports.semantic_break_detector import SemanticBreakDetector


class _ValidDetector:
    """最小合规实现（仅验证协议形状，不验证行为）。"""

    async def detect_breaks(self, segments: list[str], threshold: float = 0.65) -> list[int]:
        return []


class _InvalidDetector:
    """缺失 detect_breaks 方法的不合规实现。"""

    async def detect_wrong_method(self, segments: list[str]) -> list[int]:
        return []


class TestSemanticBreakDetectorProtocol:
    """验证 SemanticBreakDetector Protocol 结构约束。"""

    def test_valid_implementation_satisfies_protocol(self) -> None:
        detector = _ValidDetector()
        assert isinstance(detector, SemanticBreakDetector)

    def test_invalid_implementation_fails_protocol(self) -> None:
        detector = _InvalidDetector()
        assert not isinstance(detector, SemanticBreakDetector)

    def test_protocol_has_detect_breaks(self) -> None:
        assert hasattr(SemanticBreakDetector, "detect_breaks")

    def test_detect_breaks_default_threshold(self) -> None:
        """确认协议定义的默认阈值为 0.65。"""
        import inspect

        sig = inspect.signature(SemanticBreakDetector.detect_breaks)
        param = sig.parameters.get("threshold")
        assert param is not None
        assert param.default == 0.65
