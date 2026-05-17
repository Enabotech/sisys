"""基础设施层敏感数据检测服务模块

基于 SensitiveDataDetectorPort 接口实现 PII、商业秘密、金融数据等敏感信息的正则表达式检测

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from src.domain.entities.sensitive_data_result import SensitiveDataResult, SensitiveType
from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort

if TYPE_CHECKING:
    pass


class SensitiveDataDetectorImpl(SensitiveDataDetectorPort):
    """敏感数据检测服务实现，使用正则表达式检测 PII、商业秘密和金融数据"""

    # PII 正则表达式（不使用 \b 词边界，支持中文文本）
    _CHINESE_ID_PATTERN = re.compile(r"\d{17}[\dXx]")
    _PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
    _EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    # 金融数据正则表达式
    _BANK_ACCOUNT_PATTERN = re.compile(r"\d{16,19}")
    _CREDIT_CARD_PATTERN = re.compile(r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}")

    # 商业秘密关键词
    _TRADE_SECRET_KEYWORDS = [
        "核心技术配方",
        "商业秘密",
        "保密",
        "机密",
        "客户列表",
        "战略计划",
        "最高机密",
        "专有技术",
    ]

    def detect_sensitive_data(self, content: str) -> SensitiveDataResult:
        """检测敏感数据

        Args:
            content: 待检测内容

        Returns:
            SensitiveDataResult 包含检测结果
        """
        sensitive_types: list[SensitiveType] = []
        confidence = 1.0
        labels: list[str] = []

        # 检测 PII
        pii_types = self._detect_pii(content)
        if pii_types:
            sensitive_types.extend(pii_types)

        # 检测商业秘密
        if self._detect_trade_secret(content):
            sensitive_types.append(SensitiveType.TRADE_SECRET)

        # 检测金融数据
        if self._detect_financial(content):
            sensitive_types.append(SensitiveType.FINANCIAL)

        # 计算置信度
        if sensitive_types:
            confidence = self._calculate_confidence(content, sensitive_types)

        # 生成源数据哈希
        source_hash = hashlib.sha256(content.encode()).hexdigest()

        return SensitiveDataResult(
            source_data_hash=source_hash,
            sensitive_types=tuple(sensitive_types),
            confidence=confidence,
            labels=tuple(labels),
        )

    def _detect_pii(self, content: str) -> list[SensitiveType]:
        """检测 PII 数据

        Args:
            content: 待检测内容

        Returns:
            PII 类型列表
        """
        pii_types = []

        if self._CHINESE_ID_PATTERN.search(content):
            pii_types.append(SensitiveType.PII)

        if self._PHONE_PATTERN.search(content):
            pii_types.append(SensitiveType.PII)

        if self._EMAIL_PATTERN.search(content):
            pii_types.append(SensitiveType.PII)

        return pii_types

    def _detect_trade_secret(self, content: str) -> bool:
        """检测商业秘密

        Args:
            content: 待检测内容

        Returns:
            True 如果包含商业秘密关键词
        """
        for keyword in self._TRADE_SECRET_KEYWORDS:
            if keyword in content:
                return True
        return False

    def _detect_financial(self, content: str) -> bool:
        """检测金融数据

        Args:
            content: 待检测内容

        Returns:
            True 如果包含金融数据
        """
        if self._BANK_ACCOUNT_PATTERN.search(content):
            return True
        if self._CREDIT_CARD_PATTERN.search(content):
            return True
        return False

    def _calculate_confidence(self, content: str, sensitive_types: list[SensitiveType]) -> float:
        """计算检测置信度

        Args:
            content: 待检测内容
            sensitive_types: 检测到的敏感类型

        Returns:
            置信度 0.0-1.0
        """
        if not sensitive_types:
            return 0.0

        # 基础置信度
        confidence = 0.85

        # PII 检测置信度调整
        if SensitiveType.PII in sensitive_types:
            # 检查是否有格式正确的身份证
            if self._CHINESE_ID_PATTERN.search(content):
                confidence = max(confidence, 0.95)
            else:
                confidence = max(confidence, 0.80)

        # 商业秘密检测置信度
        if SensitiveType.TRADE_SECRET in sensitive_types:
            confidence = max(confidence, 0.85)

        # 金融数据检测置信度
        if SensitiveType.FINANCIAL in sensitive_types:
            confidence = max(confidence, 0.90)

        return confidence
