"""CostCalculator 领域服务单元测试.

验证成本计算服务的准确性和边界条件：
- 本地/云端路由成本计算
- 零 Token 输入成本为 0
- 未匹配模型使用默认定价
- 领域层零外部依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import pytest

from src.domain.services.cost_calculator import CostCalculator
from src.domain.value_objects.token_consumption import TokenConsumption


class TestCostCalculatorLocalRoute:
    """本地路由成本计算测试."""

    @pytest.fixture
    def calculator(self) -> CostCalculator:
        """创建默认定价的 CostCalculator."""
        return CostCalculator(
            local_input_price=0.002,
            local_output_price=0.002,
            cloud_input_price=0.02,
            cloud_output_price=0.02,
            model_pricing_map={},
        )

    def test_local_route_cost(self, calculator: CostCalculator) -> None:
        """本地路由成本：256 prompt × ¥0.002/1K + 512 completion × ¥0.002/1K = ¥0.001536."""
        consumption = TokenConsumption(prompt_tokens=256, completion_tokens=512)
        cost = calculator.calculate(consumption, route_type="local", model="qwen2.5:7b")
        assert abs(cost - 0.001536) < 1e-9

    def test_local_route_zero_tokens(self, calculator: CostCalculator) -> None:
        """零 Token 本地路由成本为 0."""
        consumption = TokenConsumption(prompt_tokens=0, completion_tokens=0)
        cost = calculator.calculate(consumption, route_type="local", model="qwen2.5:7b")
        assert cost == 0.0


class TestCostCalculatorCloudRoute:
    """云端路由成本计算测试."""

    @pytest.fixture
    def calculator(self) -> CostCalculator:
        """创建默认定价的 CostCalculator."""
        return CostCalculator(
            local_input_price=0.002,
            local_output_price=0.002,
            cloud_input_price=0.02,
            cloud_output_price=0.02,
            model_pricing_map={},
        )

    def test_cloud_route_cost(self, calculator: CostCalculator) -> None:
        """云端路由成本：512 prompt × ¥0.02/1K + 1024 completion × ¥0.02/1K = ¥0.03072."""
        consumption = TokenConsumption(prompt_tokens=512, completion_tokens=1024)
        cost = calculator.calculate(consumption, route_type="cloud", model="MiniMax-M2.7")
        assert abs(cost - 0.03072) < 1e-9

    def test_cloud_route_zero_tokens(self, calculator: CostCalculator) -> None:
        """零 Token 云端路由成本为 0."""
        consumption = TokenConsumption(prompt_tokens=0, completion_tokens=0)
        cost = calculator.calculate(consumption, route_type="cloud", model="MiniMax-M2.7")
        assert cost == 0.0


class TestCostCalculatorModelPricing:
    """模型特定定价测试."""

    def test_model_specific_pricing(self) -> None:
        """模型特定定价覆盖默认定价."""
        calculator = CostCalculator(
            local_input_price=0.002,
            local_output_price=0.002,
            cloud_input_price=0.02,
            cloud_output_price=0.02,
            model_pricing_map={
                "deepseek-v3": {"input": 0.001, "output": 0.002},
            },
        )
        consumption = TokenConsumption(prompt_tokens=1000, completion_tokens=1000)
        # deepseek-v3 使用 model_pricing_map 中的定价
        cost = calculator.calculate(consumption, route_type="cloud", model="deepseek-v3")
        expected = (1000 * 0.001 + 1000 * 0.002) / 1000
        assert abs(cost - expected) < 1e-9

    def test_unknown_model_uses_default(self) -> None:
        """未知模型使用默认云端定价."""
        calculator = CostCalculator(
            local_input_price=0.002,
            local_output_price=0.002,
            cloud_input_price=0.02,
            cloud_output_price=0.02,
            model_pricing_map={
                "deepseek-v3": {"input": 0.001, "output": 0.002},
            },
        )
        consumption = TokenConsumption(prompt_tokens=512, completion_tokens=1024)
        # unknown-model 不在 model_pricing_map 中，使用默认云端定价
        cost = calculator.calculate(consumption, route_type="cloud", model="unknown-model")
        assert abs(cost - 0.03072) < 1e-9


class TestCostCalculatorFormula:
    """成本公式验证测试."""

    def test_formula_accuracy(self) -> None:
        """成本公式: (prompt × input_price + completion × output_price) / 1000."""
        calculator = CostCalculator(
            local_input_price=0.003,
            local_output_price=0.005,
            cloud_input_price=0.04,
            cloud_output_price=0.06,
            model_pricing_map={},
        )
        consumption = TokenConsumption(prompt_tokens=500, completion_tokens=300)
        cost = calculator.calculate(consumption, route_type="local", model="test")
        expected = (500 * 0.003 + 300 * 0.005) / 1000
        assert abs(cost - expected) < 1e-9

    def test_large_token_count(self) -> None:
        """大 Token 数量计算."""
        calculator = CostCalculator(
            local_input_price=0.002,
            local_output_price=0.002,
            cloud_input_price=0.02,
            cloud_output_price=0.02,
            model_pricing_map={},
        )
        consumption = TokenConsumption(prompt_tokens=100000, completion_tokens=50000)
        cost = calculator.calculate(consumption, route_type="cloud", model="test")
        expected = (100000 * 0.02 + 50000 * 0.02) / 1000
        assert abs(cost - expected) < 1e-9
