"""Event-related enumerations.

All enums use Python standard library enum module (no external dependencies).
"""

from __future__ import annotations

from enum import Enum


class DeviationLevel(str, Enum):
    """Strategic deviation severity levels."""

    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class CorrectionType(str, Enum):
    """Correction classification types."""

    L0 = "L0"  # Spelling/formatting
    L1 = "L1"  # Parameter/weight adjustment
    L2 = "L2"  # Constraint change
    L3 = "L3"  # Assumption/logic/strategy change


class IsolationLevel(str, Enum):
    """EIP (Elastic Isolation Protocol) levels."""

    L4_HARD = "L4"  # Hard isolation (default)
    L3_SOFT = "L3"  # Soft isolation
    L2_COLLAB = "L2"  # Collaboration mode
    L1_FUSED = "L1"  # Fused mode


class RecoveryMode(str, Enum):
    """Checkpoint recovery modes."""

    REPLAY = "Replay"  # Strong consistency
    OVERRIDE = "Override"  # Weak consistency
