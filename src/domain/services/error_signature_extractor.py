"""错误签名提取领域服务（Story 4.7 AC-5）

纯函数归一化签名提取——同根因不同表层输出收敛为同一签名（案例库幂等前提）：

- STDERR 路径：剥离路径/行号/时间戳/内存地址 + 数值 → ``<N>`` / 引号串 → ``<S>``
  模板化（Sentry message templating 对标，防 ``KeyError: 'x'`` 类消息内插值分裂签名）
- 尾部锚定：签名计算取 ``stderr[-2000:]``（traceback 根因行在末尾，头部截断
  会切掉根因致错误合并；事件/prompt 展示仍可头部截断）
- violations 路径：排序去序 + path 数组索引 → ``<I>``（``$.output[3]`` 与
  ``$.output[5]`` 随 LLM 输出结构漂移——R8-19）+ message 同套 ``<N>/<S>`` 模板化
- 输出恒为完整 sha256 hexdigest（64 hex）——与 ErrorCase 列宽/实体不变量三处口径同一

已知边界（R8-18/R8-30，Story 登记）：
- over-merging——``<S>`` 抹平引号内类型名（``'int' and 'str'`` 与 ``'int' and 'list'``
  收敛同签名）；缓解 = 案例命中按 error_category 二次过滤
- stderr 含 dict/set repr 键序不稳定、异常链中间包装层数漂移可致签名分裂——
  低频形态 V1 不处理（deferred 随真实语料评估）
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

__all__ = ["ErrorSignatureExtractor"]

# 尾部锚定窗口（traceback 根因行在末尾）
_TAIL_ANCHOR_LENGTH = 2000

# 十六进制内存地址（先于数值规则处理，避免 0x7f8b 被拆为多个 <N>）
_MEMORY_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")

# 文件系统路径（Unix 绝对/相对路径段，含扩展名）
_FILE_PATH_RE = re.compile(r"(?:[A-Za-z]:)?(?:/[\w.\-]+)+")

# 数值（时间戳/行号/计数统一模板化）
_NUMERIC_RE = re.compile(r"\d+")

# 引号串（单/双引号非贪婪匹配——键名/值内插统一抹平）
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")

# violations path 中的数组索引（$.output[3].value → $.output[<I>].value）
_ARRAY_INDEX_RE = re.compile(r"\[\d+]")

# 模板化占位符
_N_PLACEHOLDER = "<N>"
_S_PLACEHOLDER = "<S>"
_I_PLACEHOLDER = "[<I>]"


def _normalize_text(text: str) -> str:
    """文本归一化（路径/地址/数值/引号串模板化）.

    处理顺序有依赖：内存地址 → 文件路径 → 数值 → 引号串
    （0x 地址须先于数值整体消解，避免 hex 数字碎片参与数值模板化后残留歧义；
    引号串最后处理，避免路径/数值规则作用于引号内容时序错位）。

    Args:
        text: 原始文本（STDERR 或 violation message）

    Returns:
        归一化文本
    """
    result = _MEMORY_ADDR_RE.sub("<ADDR>", text)
    result = _FILE_PATH_RE.sub("<PATH>", result)
    result = _NUMERIC_RE.sub(_N_PLACEHOLDER, result)
    result = _QUOTED_RE.sub(_S_PLACEHOLDER, result)
    return result


class ErrorSignatureExtractor:
    """错误签名提取器（纯函数，无状态）

    两入口：
    - extract(stderr)：382-EXECUTION 主路径（STDERR 归一化 + 尾部锚定）
    - extract_from_violations(violations)：389-Schema 子路径（排序去序 + 索引模板化）
    """

    @staticmethod
    def extract(stderr: str) -> str:
        """从 STDERR 提取归一化签名（尾部锚定 2000 字符）.

        Args:
            stderr: 原始 STDERR 文本（可为空——389-LLM 子路径无 STDERR 形态）

        Returns:
            64 hex 完整 sha256 hexdigest
        """
        tail = stderr[-_TAIL_ANCHOR_LENGTH:] if stderr else ""
        normalized = _normalize_text(tail)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _violation_fields(violation: Any) -> tuple[str, str, str]:
        """提取 violation 三元组（兼容 dict 与对象属性两形态）.

        Args:
            violation: dict 形态（SchemaViolation.to_dict()——389 context 生产形态）
                或含 path/expected/message 属性的对象

        Returns:
            (path, expected, message) 三元组（缺省空串）
        """
        if isinstance(violation, dict):
            return (
                str(violation.get("path", "")),
                str(violation.get("expected", "")),
                str(violation.get("message", "")),
            )
        return (
            str(getattr(violation, "path", "") or ""),
            str(getattr(violation, "expected", "") or ""),
            str(getattr(violation, "message", "") or ""),
        )

    @staticmethod
    def extract_from_violations(violations: Iterable[Any]) -> str:
        """从 Schema violations 提取归一化签名（389-Schema 子路径）.

        归一化规则（R8-19 完备化）：
        - 排序去序：条目按归一化三元组排序（LLM 输出条目顺序不稳定）
        - path 数组索引 → ``[<I>]``：``$.output[3]`` 与 ``$.output[5]`` 同根因收敛
        - message 应用同套 ``<N>``/``<S>`` 模板化（插值分裂收敛）
        - expected 原样保留（Schema 断言文本为结构信息）

        Args:
            violations: violation 集合（dict 或对象形态混合）

        Returns:
            64 hex 完整 sha256 hexdigest
        """
        normalized_items: list[str] = []
        for violation in violations:
            path, expected, message = ErrorSignatureExtractor._violation_fields(violation)
            norm_path = _ARRAY_INDEX_RE.sub(_I_PLACEHOLDER, _normalize_text(path))
            norm_expected = expected
            norm_message = _normalize_text(message)
            normalized_items.append(f"{norm_path}|{norm_expected}|{norm_message}")
        normalized_items.sort()
        joined = "\n".join(normalized_items)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()
