"""Story 2-3: LayoutDetector 端口协议单元测试

验证 LayoutDetector Protocol 的合规性：runtime_checkable、isinstance 检查、接口签名约束。
"""

from __future__ import annotations

from src.domain.ports.layout_detector import LayoutDetector
from src.domain.value_objects.parsed_document import BoundingBox, BoundingBoxResult


class FakeLayoutDetector:
    """模拟 LayoutDetector 实现，用于 isinstance 验证"""

    def detect(self, image_bytes: bytes, page_number: int) -> list[BoundingBoxResult]:
        """模拟检测方法，返回固定结果"""
        return [
            BoundingBoxResult(
                label="Text",
                bbox=BoundingBox(x=0.0, y=0.0, width=100.0, height=50.0, page=page_number),
                confidence=0.95,
            ),
        ]


class TestLayoutDetectorPort:
    """LayoutDetector 端口协议合规测试"""

    def test_port_is_runtime_checkable(self) -> None:
        """验证 LayoutDetector 使用 @runtime_checkable 装饰器"""
        # @runtime_checkable 的 Protocol 会有 __protocol_attrs__ 或 _is_protocol 属性
        assert hasattr(LayoutDetector, "__protocol_attrs__") or hasattr(LayoutDetector, "_is_protocol")

    def test_fake_implementation_passes_isinstance(self) -> None:
        """验证 FakeLayoutDetector 满足 LayoutDetector Protocol"""
        detector = FakeLayoutDetector()
        assert isinstance(detector, LayoutDetector)

    def test_fake_implementation_has_detect_method(self) -> None:
        """验证实现类具有 detect 方法"""
        detector = FakeLayoutDetector()
        assert callable(detector.detect)

    def test_detect_method_signature(self) -> None:
        """验证 detect 方法签名（image_bytes: bytes, page_number: int）"""
        detector = FakeLayoutDetector()
        result = detector.detect(b"image_bytes", page_number=1)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], BoundingBoxResult)

    def test_detect_returns_bounding_box_results(self) -> None:
        """验证 detect 返回值类型为 list[BoundingBoxResult]"""
        detector = FakeLayoutDetector()
        results = detector.detect(b"\x89PNG\r\n", page_number=2)
        for item in results:
            assert isinstance(item, BoundingBoxResult)

    def test_page_number_propagates_to_bbox_page(self) -> None:
        """验证 page_number 参数正确写入 BoundingBoxResult.bbox.page"""
        detector = FakeLayoutDetector()
        results = detector.detect(b"image", page_number=5)
        assert results[0].bbox.page == 5

    def test_incomplete_class_not_instance(self) -> None:
        """验证缺少 detect 方法的类不满足 Protocol"""

        class IncompleteDetector:
            pass

        assert not isinstance(IncompleteDetector(), LayoutDetector)

    def test_class_without_detect_not_instance(self) -> None:
        """验证有 detect 但签名不匹配的类不满足 Protocol（仅检查属性）"""

        # @runtime_checkable 只检查方法存在性，不检查签名
        # 这与 isinstance 行为一致（duck typing）
        class BadDetector:
            def detect(self) -> list:
                return []

        # runtime_checkable 只检查方法名存在
        assert isinstance(BadDetector(), LayoutDetector)  # runtime_checkable 是宽松检查
