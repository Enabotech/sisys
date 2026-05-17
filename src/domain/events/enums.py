"""SISYS 领域层 事件相关枚举模块

所有枚举均使用Python标准库enum模块（无外部依赖）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from enum import Enum


class DeviationType(str, Enum):
    """战略偏差类型。"""

    BUDGET_OVERUN = "budget_overrun"  # 预算超支
    TIMELINE_DELAY = "timeline_delay"  # 时间线延迟
    SCOPE_CREEP = "scope_creep"  # 范围蔓延
    QUALITY_DROP = "quality_drop"  # 质量下降
    RESOURCE_SHORTAGE = "resource_shortage"  # 资源短缺
    STRATEGY_MISALIGN = "strategy_misalign"  # 战略偏差


class DeviationLevel(str, Enum):
    """战略偏差严重级别。"""

    MINOR = "minor"  # 轻微
    MODERATE = "moderate"  # 中等
    SEVERE = "severe"  # 严重


class CorrectionType(str, Enum):
    """纠正分类类型。"""

    L0 = "L0"  # 拼写/格式
    L1 = "L1"  # 参数/权重调整
    L2 = "L2"  # 约束变更
    L3 = "L3"  # 假设/逻辑/策略变更


class IsolationLevel(str, Enum):
    """EIP（弹性隔离协议）级别。"""

    L4_HARD = "L4"  # 硬隔离（默认）
    L3_SOFT = "L3"  # 软隔离
    L2_COLLAB = "L2"  # 协作模式
    L1_FUSED = "L1"  # 融合模式


class RecoveryMode(str, Enum):
    """检查点恢复模式。"""

    REPLAY = "Replay"  # 强一致性
    OVERRIDE = "Override"  # 弱一致性
