"""领域层版面检测结果与文本元素的 Bbox 匹配服务

基于空间 IoU（Intersection over Union）的贪心匹配算法，
将版面检测结果（BoundingBoxResult）与解析元素的 BoundingBox 按空间位置关联。
纯领域逻辑，零外部依赖。
"""

from __future__ import annotations

from src.domain.value_objects.parsed_document import BoundingBox, BoundingBoxResult

# IoU 匹配阈值：严格大于此值视为匹配
_IOU_THRESHOLD = 0.3


def _compute_iou(a: BoundingBox, b: BoundingBox) -> float:
    """计算两个 BoundingBox 的 IoU（Intersection over Union）

    Args:
        a: 第一个边界框
        b: 第二个边界框

    Returns:
        IoU 值，范围 [0.0, 1.0]
    """
    # 计算交集区域
    inter_x1 = max(a.x, b.x)
    inter_y1 = max(a.y, b.y)
    inter_x2 = min(a.x + a.width, b.x + b.width)
    inter_y2 = min(a.y + a.height, b.y + b.height)

    inter_width = max(0.0, inter_x2 - inter_x1)
    inter_height = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_width * inter_height

    area_a = a.width * a.height
    area_b = b.width * b.height
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def match_detections(
    detections: list[BoundingBoxResult],
    element_bboxes: list[BoundingBox],
) -> list[tuple[BoundingBoxResult, BoundingBox | None]]:
    """将版面检测结果与文本元素的 bbox 进行贪心匹配

    算法：
    1. 计算所有检测-元素对的 IoU
    2. 按 IoU 降序排列
    3. 贪心分配：最高 IoU 优先匹配，已匹配的检测和元素不再参与
    4. IoU 阈值 > 0.3（严格大于）才视为匹配
    5. 页面隔离：仅同页元素可匹配

    Args:
        detections: 版面检测结果列表
        element_bboxes: 待匹配的文本元素 bbox 列表

    Returns:
        列表，每项为 (detection, matched_bbox_or_none)
    """
    if not detections or not element_bboxes:
        return [(d, None) for d in detections]

    # 计算所有候选对
    candidates: list[tuple[float, int, int]] = []  # (iou, det_idx, bbox_idx)
    for di, det in enumerate(detections):
        for bi, bbox in enumerate(element_bboxes):
            # 页面隔离：仅同页匹配
            if det.bbox.page != bbox.page:
                continue
            iou = _compute_iou(det.bbox, bbox)
            if iou > _IOU_THRESHOLD:
                candidates.append((iou, di, bi))

    # 按 IoU 降序排列
    candidates.sort(key=lambda x: x[0], reverse=True)

    # 贪心匹配
    matched_detections: set[int] = set()
    matched_bboxes: set[int] = set()
    match_map: dict[int, int] = {}  # det_idx → bbox_idx

    for iou, di, bi in candidates:
        if di in matched_detections or bi in matched_bboxes:
            continue
        match_map[di] = bi
        matched_detections.add(di)
        matched_bboxes.add(bi)

    # 构建结果
    result: list[tuple[BoundingBoxResult, BoundingBox | None]] = []
    for di, det in enumerate(detections):
        if di in match_map:
            result.append((det, element_bboxes[match_map[di]]))
        else:
            result.append((det, None))

    return result
