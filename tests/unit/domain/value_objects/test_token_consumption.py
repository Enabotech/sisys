"""TokenConsumption 值对象单元测试.

验证 Token 消耗值对象的不变量约束：total_tokens == prompt_tokens + completion_tokens，
所有字段非负，frozen dataclass 不可变
"""

from __future__ import annotations

import dataclasses

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.token_consumption import TokenConsumption


class TestTokenConsumptionCreation:
    """TokenConsumption 创建测试."""

    def test_basic_creation(self) -> None:
        """基本创建."""
        tc = TokenConsumption(prompt_tokens=256, completion_tokens=512)
        assert tc.prompt_tokens == 256
        assert tc.completion_tokens == 512
        assert tc.total_tokens == 768

    def test_zero_tokens(self) -> None:
        """零 Token 创建."""
        tc = TokenConsumption(prompt_tokens=0, completion_tokens=0)
        assert tc.total_tokens == 0

    def test_prompt_only(self) -> None:
        """仅 prompt tokens."""
        tc = TokenConsumption(prompt_tokens=100, completion_tokens=0)
        assert tc.total_tokens == 100


class TestTokenConsumptionInvariant:
    """TokenConsumption 不变量测试."""

    def test_total_tokens_equals_sum(self) -> None:
        """total_tokens 必须等于 prompt + completion."""
        tc = TokenConsumption(prompt_tokens=300, completion_tokens=200)
        assert tc.total_tokens == 500

    def test_negative_prompt_tokens_raises(self) -> None:
        """负数 prompt_tokens 必须抛出 ValueError."""
        with pytest.raises(EntityValidationError, match="prompt_tokens"):
            TokenConsumption(prompt_tokens=-1, completion_tokens=100)

    def test_negative_completion_tokens_raises(self) -> None:
        """负数 completion_tokens 必须抛出 ValueError."""
        with pytest.raises(EntityValidationError, match="completion_tokens"):
            TokenConsumption(prompt_tokens=100, completion_tokens=-1)


class TestTokenConsumptionFrozen:
    """TokenConsumption frozen 测试."""

    def test_frozen_immutable(self) -> None:
        """frozen dataclass 不可变."""
        tc = TokenConsumption(prompt_tokens=100, completion_tokens=200)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(tc, "prompt_tokens", 999)

    def test_frozen_total_immutable(self) -> None:
        """total_tokens 也不可变."""
        tc = TokenConsumption(prompt_tokens=100, completion_tokens=200)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(tc, "total_tokens", 999)


class TestTokenConsumptionEquality:
    """TokenConsumption 相等性测试."""

    def test_equal_values(self) -> None:
        """相同值的 TokenConsumption 相等."""
        tc1 = TokenConsumption(prompt_tokens=100, completion_tokens=200)
        tc2 = TokenConsumption(prompt_tokens=100, completion_tokens=200)
        assert tc1 == tc2

    def test_different_values(self) -> None:
        """不同值的 TokenConsumption 不等."""
        tc1 = TokenConsumption(prompt_tokens=100, completion_tokens=200)
        tc2 = TokenConsumption(prompt_tokens=100, completion_tokens=300)
        assert tc1 != tc2
