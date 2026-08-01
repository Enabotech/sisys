"""OCR 命令行接口

提供 OCR 命令行工具，支持指定页数识别和输出到指定位置。
使用 argparse 标准库（零额外依赖），通过 pyproject.toml 注册为 sisys-ocr 入口点。

架构约束：
- 位于 interfaces 层，不得直接 import infrastructure 层
- 通过 importlib 动态加载适配器实现（与 composition_root 的 impl 字符串模式一致）

运行方式：
    sisys-ocr <file> [options]
    poetry run sisys-ocr <file> [options]

参数：
    file            PDF 或图像文件路径（位置参数）
    -p, --pages     页码范围，如 "1-5,10,20-30"（默认全部）
    -o, --output    输出文件路径（默认 stdout）
    --url           PaddleOCR-VL API 地址（默认 http://localhost:8080）
    --timeout       超时时间（默认 300s）
    -q, --quiet     静默模式（仅输出 JSON，不输出日志到 stderr）

示例：
    sisys-ocr document.pdf
    sisys-ocr document.pdf -p 1-5,10 -o result.json
    sisys-ocr document.pdf -p 1-3 --url http://ocr-server:8080
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ===================================================================
# 页码范围解析
# ===================================================================


def parse_page_spec(spec: str) -> list[int]:
    """解析页码范围字符串

    支持格式：
    - 单页: "3" → [3]
    - 范围: "1-5" → [1, 2, 3, 4, 5]
    - 组合: "1-5,10,20-30" → [1..5, 10, 20..30]
    - 混合: "1,3,5-7" → [1, 3, 5, 6, 7]

    Args:
        spec: 页码范围字符串

    Returns:
        排序后的页码列表（1-indexed）

    Raises:
        ValueError: 格式错误或页码无效
    """
    pages: set[int] = set()
    parts = spec.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            # 范围格式: "start-end"
            try:
                start_str, end_str = part.split("-", 1)
                start = int(start_str.strip())
                end = int(end_str.strip())
            except (ValueError, AttributeError) as e:
                raise ValueError(f"页码范围格式无效: '{part}'，应为 'start-end' 格式") from e

            if start < 1:
                raise ValueError(f"页码必须为正整数，起始值: {start}")
            if end < start:
                raise ValueError(f"页码范围结束值({end})必须大于等于起始值({start})")

            pages.update(range(start, end + 1))
        else:
            # 单页格式: "N"
            try:
                page = int(part)
            except ValueError as e:
                raise ValueError(f"页码格式无效: '{part}'，应为正整数") from e

            if page < 1:
                raise ValueError(f"页码必须为正整数，实际值: {page}")

            pages.add(page)

    if not pages:
        raise ValueError("页码范围为空，请指定有效页码")

    return sorted(pages)


# ===================================================================
# 适配器工厂（通过 importlib 动态加载，避免 interfaces→infrastructure 直接 import）
# ===================================================================

_ADAPTER_MODULE = "src.infrastructure.document_parsing.paddleocr_vl_adapter"
_ADAPTER_CLASS = "PaddleOCRVLAdapter"


def _create_ocr_adapter(base_url: str = "http://localhost:8080", timeout: float = 300.0) -> Any:
    """通过动态导入创建 OCR 适配器实例

    使用 importlib 而非直接 import，遵循六边形架构 interfaces→infrastructure 依赖约束。
    与 composition_root.py 中 impl 字符串延迟加载模式一致。

    Args:
        base_url: PaddleOCR-VL API 地址
        timeout: HTTP 请求超时时间

    Returns:
        OCRPort 实现实例
    """
    module = importlib.import_module(_ADAPTER_MODULE)
    adapter_cls = getattr(module, _ADAPTER_CLASS)
    instance = adapter_cls(base_url=base_url, timeout=timeout)
    return instance


# ===================================================================
# OCR 识别核心逻辑
# ===================================================================


async def ocr_recognize(
    file_path: str,
    page_numbers: list[int] | None = None,
    base_url: str = "http://localhost:8080",
    timeout: float = 300.0,
) -> list[dict[str, Any]]:
    """对指定文件执行 OCR 识别

    Args:
        file_path: 文件路径
        page_numbers: 需要 OCR 的页码列表，None 表示全部
        base_url: PaddleOCR-VL API 地址
        timeout: 超时时间（秒）

    Returns:
        OCR 结果列表（已序列化为 dict）

    Raises:
        FileNotFoundError: 文件不存在
        OCRConnectionError: OCR 服务不可达
        OCRProcessingError: OCR 处理失败
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    adapter = _create_ocr_adapter(base_url=base_url, timeout=timeout)
    try:
        results = await adapter.recognize(file_path, page_numbers)
        return [r.to_dict() for r in results]
    finally:
        await adapter.close()


# ===================================================================
# 参数解析
# ===================================================================


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器

    Returns:
        配置完成的 ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        prog="sisys-ocr",
        description="SISYS OCR 命令行工具 — 对扫描件/图像 PDF 执行 OCR 识别",
        epilog="示例: sisys-ocr document.pdf -p 1-5,10 -o result.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 位置参数：文件路径
    parser.add_argument(
        "file",
        type=str,
        help="PDF 或图像文件路径",
    )

    # 选项参数
    parser.add_argument(
        "-p",
        "--pages",
        type=str,
        default=None,
        metavar="PAGES",
        help='页码范围，如 "1-5,10,20-30"（默认全部页面）',
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="输出文件路径（默认输出到 stdout）",
    )

    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8080",
        metavar="URL",
        help="PaddleOCR-VL API 地址（默认 http://localhost:8080）",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        metavar="SECONDS",
        help="HTTP 请求超时时间（默认 300s）",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="静默模式（仅输出 JSON，不输出日志到 stderr）",
    )

    return parser


# ===================================================================
# 主入口
# ===================================================================


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口

    Args:
        argv: 命令行参数（默认使用 sys.argv[1:]）

    Returns:
        退出码（0=成功，1=错误）
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # 配置日志
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # 解析页码范围
    page_numbers: list[int] | None = None
    if args.pages:
        try:
            page_numbers = parse_page_spec(args.pages)
            logger.info("指定页码范围: %s → %d 页", args.pages, len(page_numbers))
        except ValueError as e:
            logger.error("页码范围解析失败: %s", e)
            return 1

    # 执行 OCR 识别
    try:
        logger.info("开始 OCR 识别: %s", os.path.basename(args.file))
        if page_numbers:
            logger.info("处理页码: %s", page_numbers)

        results = asyncio.run(
            ocr_recognize(
                file_path=args.file,
                page_numbers=page_numbers,
                base_url=args.url,
                timeout=args.timeout,
            )
        )

        # 序列化输出
        output_data = {
            "file": os.path.basename(args.file),
            "total_pages": len(results),
            "pages": results,
        }
        json_str = json.dumps(output_data, ensure_ascii=False, indent=2)

        # 输出到文件或 stdout
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info("OCR 结果已写入: %s (%d 页)", args.output, len(results))
        else:
            print(json_str)

        return 0

    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:
        logger.error("OCR 识别失败: %s", e, exc_info=not args.quiet)
        return 1


# ===================================================================
# 模块入口
# ===================================================================

if __name__ == "__main__":
    sys.exit(main())
