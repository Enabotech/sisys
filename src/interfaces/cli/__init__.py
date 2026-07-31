"""接口层 CLI 模块

CLI 适配器，基于 argparse 框架提供命令行接口。
当前提供：
- sisys-ocr: OCR 识别命令行工具（支持指定页数、输出到指定位置）
"""

from src.interfaces.cli.ocr_cli import main as ocr_main

__all__ = [
    "ocr_main",
]
