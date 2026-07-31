"""领域层扫描页检测服务

提供纯函数式扫描页检测逻辑，判断 PDF 页面是否需要 OCR。
通过文本密度法（逐页计算字符数）识别扫描件页面。

设计理由：
- 逐页独立比较确保混合 PDF（部分文本页+部分扫描页）正确识别
- 阈值常量 SCANNED_PAGE_TEXT_DENSITY_THRESHOLD 为经验值（50 字符/页），
  需在 Task 0 使用真实扫描件样本验证
- 纯函数实现，零外部依赖，可在领域层实现
"""

from __future__ import annotations

from src.domain.value_objects.parsed_document import ParsedPage

# 扫描页文本密度阈值（单页字符数低于此值判定为扫描页）
# 经验值：50 字符/页，含页码/页眉等少量噪声文本的扫描件仍可正确触发 OCR
# 可通过环境变量 SISYS_SCANNED_PAGE_THRESHOLD 覆盖
SCANNED_PAGE_TEXT_DENSITY_THRESHOLD: int = 50


def detect_scanned_pages(
    pages: list[ParsedPage],
    threshold: int | None = None,
) -> list[int]:
    """检测需要 OCR 的扫描页页码列表

    逐页独立计算文本密度（字符数），低于阈值则判定为扫描页。
    空页面（0 字符）判定为扫描页触发 OCR。
    恰好等于阈值的页面不触发 OCR（非扫描页）。

    纯函数实现，零外部依赖。阈值可通过参数传入，未指定时使用默认值。
    支持通过 SISYS_SCANNED_PAGE_THRESHOLD 环境变量覆盖默认值。

    Args:
        pages: 文档解析后的页面列表
        threshold: 文本密度阈值，None 则使用默认值或环境变量覆盖

    Returns:
        需要 OCR 的页码列表（1-indexed，与 ParsedPage.page_number 一致）

    Raises:
        ValueError: 环境变量 SISYS_SCANNED_PAGE_THRESHOLD 非数字
    """
    if not pages:
        return []

    if threshold is None:
        from os import environ

        env_val = environ.get("SISYS_SCANNED_PAGE_THRESHOLD")
        if env_val is not None:
            try:
                threshold = int(env_val)
            except ValueError:
                raise ValueError(f"SISYS_SCANNED_PAGE_THRESHOLD 环境变量必须为整数，实际值: {env_val}")
        else:
            threshold = SCANNED_PAGE_TEXT_DENSITY_THRESHOLD

    scanned_pages: list[int] = []
    for page in pages:
        char_count = sum(len(element.content) for element in page.texts)
        if char_count < threshold:
            scanned_pages.append(page.page_number)

    return scanned_pages


__all__ = [
    "SCANNED_PAGE_TEXT_DENSITY_THRESHOLD",
    "detect_scanned_pages",
]
