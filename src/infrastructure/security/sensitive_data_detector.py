"""Sensitive Data Detector.

Detects sensitive data types (PII, trade secrets, financial data, etc.)
using regex patterns and keyword matching.

Reference: Story 1.11 Data Sovereignty Isolation - AC-1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import SensitiveDataType

if TYPE_CHECKING:
    pass


@dataclass
class DetectionResult:
    """Result of sensitive data detection.

    Attributes:
        is_sensitive: Whether sensitive data was detected.
        sensitive_type: Type of sensitive data detected.
        confidence: Detection confidence (0.0-1.0).
        labels: List of detected labels/markers.
        detection_method: Method used for detection (regex, keyword).
        matched_pattern: The pattern that matched (if any).
    """

    is_sensitive: bool = False
    sensitive_type: SensitiveDataType = SensitiveDataType.PII
    confidence: float = 0.0
    labels: list[str] = field(default_factory=list)
    detection_method: str = ""
    matched_pattern: str = ""


class SensitiveDataDetector:
    """Detector for sensitive data types.

    Uses regex patterns for structured PII (ID cards, phone numbers, etc.)
    and keyword matching for trade secrets and contextual data.
    """

    def __init__(self, min_confidence: float = 0.95) -> None:
        """Initialize detector with configuration.

        Args:
            min_confidence: Minimum confidence threshold for detection.
        """
        self.min_confidence = min_confidence

        # PII regex patterns (structured data with specific formats)
        # Note: Using lookbehind/lookahead instead of \b for Chinese text compatibility
        self._pii_patterns: dict[str, tuple[re.Pattern, float, SensitiveDataType]] = {
            "china_id": (
                re.compile(r"(?<![0-9])[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9])"),
                0.99,
                SensitiveDataType.PII,
            ),
            "phone_cn": (
                re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
                0.98,
                SensitiveDataType.PII,
            ),
            "email": (
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
                0.95,
                SensitiveDataType.PII,
            ),
            "credit_card": (
                re.compile(r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)"),
                0.95,
                SensitiveDataType.FINANCIAL,
            ),
        }

        # Financial data patterns (bank accounts, etc.)
        self._financial_patterns: dict[str, tuple[re.Pattern, float, SensitiveDataType]] = {
            "bank_account_cn": (
                re.compile(r"(?<!\d)(?:6222|6217|6235|6229|6011)\d{10,15}(?!\d)"),
                0.95,
                SensitiveDataType.FINANCIAL,
            ),
        }

        # Trade secret keywords
        self._trade_secret_keywords: set[str] = {
            "机密",
            "秘密",
            "绝密",
            "机密文件",
            "内部资料",
            "核心配方",
            "技术方案",
            "商业计划",
            "客户名单",
            "供应商名单",
            "定价策略",
            "净利润",
            "毛利率",
            "营业收入",
            "研发投入",
            "专利技术",
            "专有技术",
            "商业机密",
        }

        # Biometric keywords
        self._biometric_keywords: set[str] = {
            "指纹",
            "人脸",
            "虹膜",
            "声纹",
            "掌纹",
            "生物特征",
            "fingerprint",
            "face recognition",
            "biometric",
        }

        # Minor-related keywords (for PIPL enhanced protection)
        self._minor_keywords: set[str] = {
            "未成年",
            "儿童",
            "学生",
            "小学生",
            "中学生",
            "高中生",
            "minor",
            "child",
        }

        # Custom patterns for user-defined sensitive types
        self._custom_patterns: dict[str, tuple[re.Pattern, float, SensitiveDataType]] = {}

    def add_custom_rule(self, pattern: str, sensitive_type: str, confidence: float = 0.95) -> None:
        """Add a custom detection rule.

        Args:
            pattern: Regex pattern to match.
            sensitive_type: Type name for the sensitive data.
            confidence: Detection confidence (0.0-1.0).
        """
        self._custom_patterns[sensitive_type] = (
            re.compile(pattern),
            confidence,
            SensitiveDataType.CUSTOM,
        )

    def detect(self, text: str | None) -> DetectionResult:
        """Detect sensitive data in text.

        Args:
            text: Text to analyze.

        Returns:
            DetectionResult with detection results.
        """
        if not text:
            return DetectionResult()

        # Check financial patterns first (more specific)
        for label, (pattern, confidence, dtype) in self._financial_patterns.items():
            if pattern.search(text) and confidence >= self.min_confidence:
                return DetectionResult(
                    is_sensitive=True,
                    sensitive_type=dtype,
                    confidence=confidence,
                    labels=[label],
                    detection_method="regex",
                    matched_pattern=label,
                )

        # Check for PII patterns
        for label, (pattern, confidence, dtype) in self._pii_patterns.items():
            if pattern.search(text) and confidence >= self.min_confidence:
                return DetectionResult(
                    is_sensitive=True,
                    sensitive_type=dtype,
                    confidence=confidence,
                    labels=[label],
                    detection_method="regex",
                    matched_pattern=label,
                )

        # Check for custom patterns
        for type_name, (pattern, confidence, dtype) in self._custom_patterns.items():
            if pattern.search(text) and confidence >= self.min_confidence:
                return DetectionResult(
                    is_sensitive=True,
                    sensitive_type=dtype,
                    confidence=confidence,
                    labels=[type_name],
                    detection_method="regex",
                    matched_pattern=type_name,
                )

        # Check for trade secrets via keywords
        # Use Unicode NFKC normalization to prevent homograph attacks
        import unicodedata

        normalized_text = unicodedata.normalize("NFKC", text)
        matched_keywords: list[str] = []
        for keyword in self._trade_secret_keywords:
            if keyword in normalized_text:
                matched_keywords.append(keyword)

        if matched_keywords:
            keyword_confidence = min(0.95, 0.8 + 0.05 * len(matched_keywords))
            if keyword_confidence >= self.min_confidence:
                return DetectionResult(
                    is_sensitive=True,
                    sensitive_type=SensitiveDataType.TRADE_SECRET,
                    confidence=keyword_confidence,
                    labels=matched_keywords[:5],  # Limit labels
                    detection_method="keyword",
                    matched_pattern="trade_secret_keyword",
                )

        # Check for biometric data
        for keyword in self._biometric_keywords:
            if keyword.lower() in text.lower():
                if 0.95 >= self.min_confidence:
                    return DetectionResult(
                        is_sensitive=True,
                        sensitive_type=SensitiveDataType.BIOMETRIC,
                        confidence=0.95,
                        labels=["biometric_data"],
                        detection_method="keyword",
                        matched_pattern=keyword,
                    )

        # Check for minor-related data
        for keyword in self._minor_keywords:
            # Skip if preceded by "非" (e.g., "非未成年人" should not match "未成年")
            if keyword in text:
                # Find position and check if preceded by "非"
                pos = text.find(keyword)
                if pos > 0 and text[pos - 1] == "非":
                    continue
                # Check if age indicator is present - find ALL ages and use minimum
                age_pattern = re.compile(r"\b(\d+)\s*岁\b")
                matches = age_pattern.findall(text)
                if matches:
                    ages = [int(m) for m in matches]
                    min_age = min(ages)  # Use minimum age for strictest PIPL protection
                    if min_age < 14:
                        if 0.95 >= self.min_confidence:
                            return DetectionResult(
                                is_sensitive=True,
                                sensitive_type=SensitiveDataType.MINOR,
                                confidence=0.95,
                                labels=[keyword, f"age_{min_age}"],
                                detection_method="keyword",
                                matched_pattern=keyword,
                            )

        return DetectionResult()

    def detect_all(self, text: str | None) -> list[DetectionResult]:
        """Detect all sensitive data types in text.

        Args:
            text: Text to analyze.

        Returns:
            List of DetectionResult for each sensitive type found.
        """
        if not text:
            return []

        results: list[DetectionResult] = []
        found_patterns: set[str] = set()

        # Check financial patterns first
        for label, (pattern, confidence, dtype) in self._financial_patterns.items():
            if pattern.search(text) and label not in found_patterns and confidence >= self.min_confidence:
                results.append(
                    DetectionResult(
                        is_sensitive=True,
                        sensitive_type=dtype,
                        confidence=confidence,
                        labels=[label],
                        detection_method="regex",
                        matched_pattern=label,
                    )
                )
                found_patterns.add(label)

        # Check all PII patterns
        for label, (pattern, confidence, dtype) in self._pii_patterns.items():
            if pattern.search(text) and label not in found_patterns and confidence >= self.min_confidence:
                results.append(
                    DetectionResult(
                        is_sensitive=True,
                        sensitive_type=dtype,
                        confidence=confidence,
                        labels=[label],
                        detection_method="regex",
                        matched_pattern=label,
                    )
                )
                found_patterns.add(label)

        # Check trade secrets
        matched_keywords: list[str] = []
        for keyword in self._trade_secret_keywords:
            if keyword in text:
                matched_keywords.append(keyword)

        if matched_keywords:
            keyword_confidence = min(0.95, 0.8 + 0.05 * len(matched_keywords))
            if keyword_confidence >= self.min_confidence:
                results.append(
                    DetectionResult(
                        is_sensitive=True,
                        sensitive_type=SensitiveDataType.TRADE_SECRET,
                        confidence=keyword_confidence,
                        labels=matched_keywords[:5],
                        detection_method="keyword",
                        matched_pattern="trade_secret_keyword",
                    )
                )

        # Check for biometric data
        for keyword in self._biometric_keywords:
            if keyword.lower() in text.lower():
                if 0.95 >= self.min_confidence:
                    results.append(
                        DetectionResult(
                            is_sensitive=True,
                            sensitive_type=SensitiveDataType.BIOMETRIC,
                            confidence=0.95,
                            labels=["biometric_data"],
                            detection_method="keyword",
                            matched_pattern=keyword,
                        )
                    )
                    break  # Only report biometric once

        # Check for minor-related data
        for keyword in self._minor_keywords:
            # Skip if preceded by "非" (e.g., "非未成年人" should not match)
            pos = text.find(keyword)
            if pos > 0 and text[pos - 1] == "非":
                continue
            # Check if age indicator is present
            age_pattern = re.compile(r"\b(\d+)\s*岁\b")
            matches = age_pattern.findall(text)
            if matches:
                ages = [int(m) for m in matches]
                min_age = min(ages)
                if min_age <= 14:
                    if 0.95 >= self.min_confidence:
                        results.append(
                            DetectionResult(
                                is_sensitive=True,
                                sensitive_type=SensitiveDataType.MINOR,
                                confidence=0.95,
                                labels=[keyword, f"age_{min_age}"],
                                detection_method="keyword",
                                matched_pattern=keyword,
                            )
                        )
                        break  # Only report minor once

        return results
