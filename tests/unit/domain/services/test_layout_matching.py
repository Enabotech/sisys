"""Story 2-3: Bbox 匹配算法单元测试

验证空间 IoU 匹配逻辑：贪心匹配、阈值过滤、页面隔离、边缘情况处理。
"""

from __future__ import annotations

import pytest

from src.domain.value_objects.parsed_document import BoundingBox, BoundingBoxResult


def _bbox(x: float, y: float, w: float, h: float, page: int = 1) -> BoundingBox:
    """构造 BoundingBox 辅助函数"""
    return BoundingBox(x=x, y=y, width=w, height=h, page=page)


def _detection(label: str, x: float, y: float, w: float, h: float, page: int = 1, conf: float = 0.9) -> BoundingBoxResult:
    """构造 BoundingBoxResult 辅助函数"""
    return BoundingBoxResult(label=label, bbox=_bbox(x, y, w, h, page), confidence=conf)


class TestIoUCalculation:
    """IoU（Intersection over Union）计算测试"""

    def test_perfect_overlap_iou_is_1(self) -> None:
        """完全重叠时 IoU = 1.0"""
        from src.domain.services.layout_matching import _compute_iou

        a = _bbox(0, 0, 100, 100)
        b = _bbox(0, 0, 100, 100)
        assert _compute_iou(a, b) == 1.0

    def test_no_overlap_iou_is_0(self) -> None:
        """无重叠时 IoU = 0.0"""
        from src.domain.services.layout_matching import _compute_iou

        a = _bbox(0, 0, 50, 50)
        b = _bbox(100, 100, 50, 50)
        assert _compute_iou(a, b) == 0.0

    def test_partial_overlap_iou(self) -> None:
        """部分重叠时 IoU 正确计算"""
        from src.domain.services.layout_matching import _compute_iou

        # a: [0,0,100,100] 面积=10000
        # b: [50,50,100,100] 面积=10000
        # 交集: [50,50,50,50] 面积=2500
        # 并集: 10000+10000-2500=17500
        # IoU = 2500/17500 ≈ 0.143
        a = _bbox(0, 0, 100, 100)
        b = _bbox(50, 50, 100, 100)
        assert _compute_iou(a, b) == pytest.approx(2500 / 17500)

    def test_contained_box_iou(self) -> None:
        """一个框完全包含另一个"""
        from src.domain.services.layout_matching import _compute_iou

        a = _bbox(0, 0, 100, 100)  # 面积=10000
        b = _bbox(25, 25, 50, 50)  # 面积=2500
        # 交集=2500, 并集=10000
        assert _compute_iou(a, b) == pytest.approx(2500 / 10000)


class TestBboxMatching:
    """bbox 贪心匹配测试"""

    def test_single_element_matched(self) -> None:
        """单元素匹配成功"""
        from src.domain.services.layout_matching import match_detections

        detections = [_detection("Text", 10, 20, 100, 50)]
        bboxes = [_bbox(10, 20, 100, 50)]

        result = match_detections(detections, bboxes)
        assert len(result) == 1
        assert result[0][1] is not None  # 匹配成功

    def test_no_overlap_returns_none(self) -> None:
        """无重叠时返回 None"""
        from src.domain.services.layout_matching import match_detections

        detections = [_detection("Text", 0, 0, 50, 50)]
        bboxes = [_bbox(200, 200, 50, 50)]  # 完全不重叠

        result = match_detections(detections, bboxes)
        assert len(result) == 1
        assert result[0][1] is None  # 无匹配

    def test_iou_threshold_boundary_exactly_03_not_matched(self) -> None:
        """IoU 恰好 0.3 时不匹配（严格大于）"""
        from src.domain.services.layout_matching import match_detections

        # a: [0,0,100,100], b: [x,0,100,100]
        # overlap_width = 100-x, inter = (100-x)*100
        # IoU = inter/(20000-inter) = 0.3 → inter = 6000/1.3 ≈ 4615.38
        # → overlap_width = 46.154 → x = 53.846
        x_val = 100 - 6000 / (1.3 * 100)
        detections = [_detection("Text", 0, 0, 100, 100)]
        bboxes = [_bbox(x_val, 0, 100, 100)]

        result = match_detections(detections, bboxes)
        assert result[0][1] is None  # IoU 恰好 0.3，不匹配

    def test_iou_just_above_03_matched(self) -> None:
        """IoU 略高于 0.3 时匹配"""
        from src.domain.services.layout_matching import _compute_iou, match_detections

        # x 比阈值边界小 1，增加重叠面积
        x_val = 100 - 6000 / (1.3 * 100) - 1
        detections = [_detection("Text", 0, 0, 100, 100)]
        bboxes = [_bbox(x_val, 0, 100, 100)]

        iou = _compute_iou(_bbox(0, 0, 100, 100), _bbox(x_val, 0, 100, 100))
        assert iou > 0.3

        result = match_detections(detections, bboxes)
        assert result[0][1] is not None

    def test_perfect_overlap_matched(self) -> None:
        """IoU = 1.0 完全重叠时匹配"""
        from src.domain.services.layout_matching import match_detections

        detections = [_detection("Text", 10, 10, 100, 100)]
        bboxes = [_bbox(10, 10, 100, 100)]

        result = match_detections(detections, bboxes)
        assert result[0][1] is not None

    def test_different_pages_not_matched(self) -> None:
        """不同页面的元素不匹配"""
        from src.domain.services.layout_matching import match_detections

        detections = [_detection("Text", 0, 0, 100, 100, page=1)]
        bboxes = [_bbox(0, 0, 100, 100, page=2)]

        result = match_detections(detections, bboxes)
        assert result[0][1] is None  # 不同页面，不匹配

    def test_empty_detections(self) -> None:
        """空检测列表"""
        from src.domain.services.layout_matching import match_detections

        result = match_detections([], [_bbox(0, 0, 100, 100)])
        assert result == []

    def test_empty_bboxes(self) -> None:
        """空 bbox 列表"""
        from src.domain.services.layout_matching import match_detections

        result = match_detections([_detection("Text", 0, 0, 100, 100)], [])
        assert len(result) == 1
        assert result[0][1] is None

    def test_greedy_highest_iou_first(self) -> None:
        """贪心匹配：最高 IoU 优先"""
        from src.domain.services.layout_matching import match_detections

        # 两个检测，两个元素，但最佳匹配是交叉的
        det1 = _detection("Title", 0, 0, 100, 30)  # 与 bbox1 高 IoU
        det2 = _detection("Text", 0, 50, 100, 50)  # 与 bbox2 高 IoU
        bbox1 = _bbox(0, 0, 100, 30)
        bbox2 = _bbox(0, 50, 100, 50)

        result = match_detections([det1, det2], [bbox1, bbox2])
        # 每个检测应匹配到最佳 bbox
        matched_labels = {r[0].label for r in result if r[1] is not None}
        assert "Title" in matched_labels
        assert "Text" in matched_labels

    def test_one_to_one_matching(self) -> None:
        """一一对应：一个检测只匹配一个 bbox"""
        from src.domain.services.layout_matching import match_detections

        # 两个检测重叠同一个 bbox
        det1 = _detection("Text", 0, 0, 100, 100, conf=0.95)
        det2 = _detection("Text", 10, 10, 80, 80, conf=0.80)
        bbox1 = _bbox(0, 0, 100, 100)

        result = match_detections([det1, det2], [bbox1])
        matched_count = sum(1 for r in result if r[1] is not None)
        assert matched_count == 1  # 只有最高 IoU 的匹配成功
