"""pytesseract 类型存根

基于 pytesseract v0.3+ 公开 API 提供完整类型定义。
pytesseract 是 Google Tesseract OCR 引擎的 Python 包装器。
覆盖 ImageParser 使用的方法。
来源: src/infrastructure/document_parsing/image_parser.py
"""

from typing import Any

import PIL.Image


class Output:
    """Tesseract 输出格式常量

    定义 image_to_data() 等方法的 output_type 参数有效值。
    """

    STRING: int
    DICT: int
    BYTES: int
    INT: int
    DATAFRAME: int


def image_to_string(
    image: PIL.Image.Image | str,
    lang: str = "eng",
    config: str = "",
    nice: bool = False,
    output_type: int = Output.STRING,
    timeout: float = 0,
) -> str: ...


def image_to_data(
    image: PIL.Image.Image | str,
    lang: str = "eng",
    config: str = "",
    nice: bool = False,
    output_type: int = Output.DICT,
    timeout: float = 0,
) -> dict[str, list[str]]: ...
