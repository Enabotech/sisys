"""领域层 文档格式值对象

17 种文档格式的 MIME 类型映射与格式校验。
支持 15 种文档格式 + 2 种压缩格式：pdf, txt, doc, docx, ppt, pptx, xls, xlsx, csv,
jpeg（含 .jpg/.jpeg 双扩展名）, png, gif, markdown（含 .md）, html, rtf, zip, tar。
"""

from __future__ import annotations

# 17 种格式 → MIME 类型映射（扩展名全部小写）
SUPPORTED_FORMATS: dict[str, str] = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "html": "text/html",
    "rtf": "application/rtf",
    "zip": "application/zip",
    "tar": "application/x-tar",
}

# 反向映射：MIME 类型 → 主扩展名（用于规范化输出）
_MIME_TO_PRIMARY_EXT: dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/csv": "csv",
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "text/markdown": "markdown",
    "text/html": "html",
    "application/rtf": "rtf",
    "application/zip": "zip",
    "application/x-tar": "tar",
}

# 压缩格式扩展名集合
ARCHIVE_EXTENSIONS: frozenset[str] = frozenset({"zip", "tar"})

# 文档格式扩展名集合（排除 .jpg/.md 等别名，仅保留主扩展名）
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        "pdf",
        "txt",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "xls",
        "xlsx",
        "csv",
        "jpeg",
        "png",
        "gif",
        "markdown",
        "html",
        "rtf",
    }
)


def get_mime_type(filename: str) -> str | None:
    """根据文件名扩展名获取 MIME 类型

    Args:
        filename: 文件名（大小写不敏感）

    Returns:
        MIME 类型字符串，不支持的格式返回 None
    """
    ext = _extract_extension(filename)
    if ext is None:
        return None
    return SUPPORTED_FORMATS.get(ext)


def get_extension(mime_type: str) -> str | None:
    """根据 MIME 类型获取主扩展名

    Args:
        mime_type: MIME 类型字符串

    Returns:
        主扩展名（小写），未知 MIME 类型返回 None
    """
    return _MIME_TO_PRIMARY_EXT.get(mime_type)


def is_supported(filename: str, mime_type: str | None = None) -> bool:
    """校验文件格式是否受支持

    支持双向校验：仅扩展名校验，或扩展名+MIME 类型双向匹配校验。

    Args:
        filename: 文件名（大小写不敏感）
        mime_type: 可选的 MIME 类型，传入时必须与扩展名映射一致

    Returns:
        True 表示格式受支持且匹配
    """
    ext = _extract_extension(filename)
    if ext is None:
        return False

    expected_mime = SUPPORTED_FORMATS.get(ext)
    if expected_mime is None:
        return False

    if mime_type is not None and mime_type != expected_mime:
        return False

    return True


def _extract_extension(filename: str) -> str | None:
    """从文件名中提取小写扩展名

    Args:
        filename: 文件名

    Returns:
        小写扩展名（不含点），无扩展名时返回 None
    """
    if not filename or "." not in filename:
        return None
    # rsplit 取最后一个点后的部分作为扩展名
    ext = filename.rsplit(".", 1)[-1].lower()
    if not ext:
        return None
    return ext
