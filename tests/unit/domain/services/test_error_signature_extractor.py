"""Story 4.7: ErrorSignatureExtractor 领域服务单元测试.

覆盖 STDERR 归一化签名（路径/行号/时间戳/内存地址剥离 + 数值/引号串模板化 +
尾部锚定 stderr[-2000:]）、violations 归一化签名（排序去序 + path 数组索引模板化 +
message 模板化——R8-19）、同根因收敛（幂等前提）、空输入与输出形态。

TDD 红→绿：本文件先于 src/domain/services/error_signature_extractor.py 实现（Subtask 1.4）。
"""

from __future__ import annotations

import re

from src.domain.services.error_signature_extractor import ErrorSignatureExtractor

_SIG_HEX = re.compile(r"^[0-9a-f]{64}$")


def _extractor() -> ErrorSignatureExtractor:
    """构造提取器实例（纯函数无状态）."""
    return ErrorSignatureExtractor()


class TestStderrSignature:
    """STDERR 归一化签名."""

    def test_output_is_64_hex(self) -> None:
        """输出恒为 64 hex 完整 sha256 hexdigest."""
        sig = _extractor().extract("Traceback ... ValueError: bad")
        assert _SIG_HEX.match(sig)

    def test_empty_input_produces_stable_signature(self) -> None:
        """空输入可处理且稳定（389-LLM 子路径 violations 双空形态）。"""
        sig1 = _extractor().extract("")
        sig2 = _extractor().extract("")
        assert _SIG_HEX.match(sig1)
        assert sig1 == sig2

    def test_numeric_values_templated(self) -> None:
        """数值 → <N>：不同数值同根因收敛同签名（Sentry message templating 对标）."""
        sig_a = _extractor().extract("IndexError: list index out of range at 3")
        sig_b = _extractor().extract("IndexError: list index out of range at 57")
        assert sig_a == sig_b

    def test_quoted_strings_templated(self) -> None:
        """引号串 → <S>：KeyError 不同键名收敛同签名（防消息内插值分裂）."""
        sig_a = _extractor().extract("KeyError: 'market'")
        sig_b = _extractor().extract("KeyError: 'competitor'")
        assert sig_a == sig_b

    def test_file_paths_stripped(self) -> None:
        """路径剥离：不同安装路径同根因收敛."""
        sig_a = _extractor().extract('File "/home/alice/sisys/tools/analysis.py", line 2\\nValueError: bad')
        sig_b = _extractor().extract('File "/opt/bob/app/tools/analysis.py", line 2\\nValueError: bad')
        assert sig_a == sig_b

    def test_line_numbers_irrelevant(self) -> None:
        """行号剥离：同行不同行号收敛."""
        sig_a = _extractor().extract("line 12: failure")
        sig_b = _extractor().extract("line 345: failure")
        assert sig_a == sig_b

    def test_timestamps_irrelevant(self) -> None:
        """时间戳剥离：不同时刻同根因收敛."""
        sig_a = _extractor().extract("2026-10-09 12:00:00 ERROR connection lost")
        sig_b = _extractor().extract("2026-10-09 18:45:23 ERROR connection lost")
        assert sig_a == sig_b

    def test_memory_addresses_irrelevant(self) -> None:
        """内存地址剥离：0x 地址不分裂签名."""
        sig_a = _extractor().extract("object at 0x7f8b2c004a60 crashed")
        sig_b = _extractor().extract("object at 0x7ff31a9c2f10 crashed")
        assert sig_a == sig_b

    def test_different_root_cause_different_signature(self) -> None:
        """不同根因不合并（归一化不可过度——根因关键词保留）."""
        sig_a = _extractor().extract("KeyError: 'market'")
        sig_b = _extractor().extract("ValueError: invalid literal")
        assert sig_a != sig_b

    def test_tail_anchored_last_2000_chars(self) -> None:
        """尾部锚定：stderr[-2000:] 窗口外的头部噪声不参与哈希（头部截断实现会切根因）."""
        root_cause = "ZeroDivisionError: division by zero"
        tail = root_cause + "x" * (2000 - len(root_cause))  # 恰 2000 字符（占满锚定窗口）
        head_a = "noise-a\\n" * 600  # 4800 字符头部噪声（窗口外）
        head_b = "DIFFERENT-noise-b\\n" * 600
        sig_a = _extractor().extract(head_a + tail)
        sig_b = _extractor().extract(head_b + tail)
        # 不同头部均在窗口外——不参与哈希
        assert sig_a == sig_b
        # 窗口内容恰为 tail——根因行全参与（头部截断 [:2000] 实现会同时丢失根因）
        assert sig_a == _extractor().extract(tail)

    def test_tail_root_cause_must_participate(self) -> None:
        """末尾根因行参与哈希（不同末尾不同签名）."""
        sig_a = _extractor().extract("prefix\\n" + "ZeroDivisionError: division by zero")
        sig_b = _extractor().extract("prefix\\n" + "KeyError: 'x'")
        assert sig_a != sig_b


class TestViolationsSignature:
    """violations 归一化签名（389-Schema 子路径）."""

    def test_violations_output_is_64_hex(self) -> None:
        """输出恒 64 hex."""
        sig = _extractor().extract_from_violations(({"path": "result", "expected": "^OK_", "message": "mismatch"},))
        assert _SIG_HEX.match(sig)

    def test_order_independent(self) -> None:
        """排序去序：条目顺序不影响签名."""
        v1 = {"path": "result", "expected": "^OK_", "message": "does not match"}
        v2 = {"path": "plan", "expected": "string", "message": "is not a string"}
        sig_a = _extractor().extract_from_violations((v1, v2))
        sig_b = _extractor().extract_from_violations((v2, v1))
        assert sig_a == sig_b

    def test_array_index_templated(self) -> None:
        """path 数组索引 → <I>：索引漂移收敛（$.output[3] 与 [5] 同签名——R8-19）."""
        v_a = {"path": "$.output[3].value", "expected": "string", "message": "item 3 is not a string"}
        v_b = {"path": "$.output[5].value", "expected": "string", "message": "item 5 is not a string"}
        sig_a = _extractor().extract_from_violations((v_a,))
        sig_b = _extractor().extract_from_violations((v_b,))
        assert sig_a == sig_b

    def test_message_templated(self) -> None:
        """message 同套 <N>/<S> 模板化：插值分裂收敛."""
        v_a = {"path": "$.factor", "expected": "integer", "message": "value 'x' at position 3 invalid"}
        v_b = {"path": "$.factor", "expected": "integer", "message": "value 'y' at position 9 invalid"}
        sig_a = _extractor().extract_from_violations((v_a,))
        sig_b = _extractor().extract_from_violations((v_b,))
        assert sig_a == sig_b

    def test_different_paths_different_signature(self) -> None:
        """不同 path 不合并."""
        v_a = {"path": "$.result", "expected": "^OK_", "message": "mismatch"}
        v_b = {"path": "$.plan", "expected": "^OK_", "message": "mismatch"}
        assert _extractor().extract_from_violations((v_a,)) != _extractor().extract_from_violations((v_b,))

    def test_empty_violations_stable(self) -> None:
        """空 violations 可处理且稳定."""
        sig_a = _extractor().extract_from_violations(())
        sig_b = _extractor().extract_from_violations(())
        assert _SIG_HEX.match(sig_a)
        assert sig_a == sig_b

    def test_object_form_violations_supported(self) -> None:
        """支持 SchemaViolation 对象形态（.path/.expected/.message 属性）与 dict 混合输入."""

        class _V:
            path = "$.result"
            expected = "^OK_"
            message = "mismatch"

        dict_sig = _extractor().extract_from_violations(({"path": "$.result", "expected": "^OK_", "message": "mismatch"},))
        obj_sig = _extractor().extract_from_violations((_V(),))
        assert dict_sig == obj_sig


class TestDeterminism:
    """确定性（幂等前提）."""

    def test_same_input_same_signature(self) -> None:
        """同输入恒同签名（跨进程/跨时刻稳定——sha256 确定性）."""
        stderr = 'Traceback (most recent call last):\\n  File "t.py", line 2\\nKeyError: 42'
        assert _extractor().extract(stderr) == _extractor().extract(stderr)
