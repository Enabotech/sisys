"""领域层成本计算服务模块

基于路由类型、模型定价和 Token 消耗计算实际成本
领域层零外部依赖，注入原始浮点值
"""

from __future__ import annotations

from src.domain.value_objects.token_consumption import TokenConsumption


class CostCalculator:
    """成本计算领域服务

    基于 route_type + selected_model + pricing 计算实际成本
    注入原始值（不依赖 CloudModelConfig 配置对象）

    成本公式: (prompt_tokens × input_price + completion_tokens × output_price) / 1000

    Attributes:
        _local_input_price: 本地模型输入单价（元/1K tokens）
        _local_output_price: 本地模型输出单价（元/1K tokens）
        _cloud_input_price: 云端模型输入单价（元/1K tokens）
        _cloud_output_price: 云端模型输出单价（元/1K tokens）
        _model_pricing_map: 模型特定定价映射
    """

    def __init__(
        self,
        local_input_price: float,
        local_output_price: float,
        cloud_input_price: float,
        cloud_output_price: float,
        model_pricing_map: dict[str, dict[str, float]],
    ) -> None:
        """初始化成本计算器.

        Args:
            local_input_price: 本地模型输入单价（元/1K tokens）
            local_output_price: 本地模型输出单价（元/1K tokens）
            cloud_input_price: 云端模型输入单价（元/1K tokens）
            cloud_output_price: 云端模型输出单价（元/1K tokens）
            model_pricing_map: 模型特定定价映射，格式 {"model_name": {"input": float, "output": float}}
        """
        self._local_input_price = local_input_price
        self._local_output_price = local_output_price
        self._cloud_input_price = cloud_input_price
        self._cloud_output_price = cloud_output_price
        self._model_pricing_map = model_pricing_map

    def calculate(self, consumption: TokenConsumption, route_type: str, model: str) -> float:
        """计算实际成本.

        Args:
            consumption: Token 消耗值对象
            route_type: 路由类型（local/cloud）
            model: 模型标识符

        Returns:
            实际成本（元）
        """
        input_price, output_price = self._resolve_prices(route_type, model)
        cost = (consumption.prompt_tokens * input_price + consumption.completion_tokens * output_price) / 1000
        return cost

    def _resolve_prices(self, route_type: str, model: str) -> tuple[float, float]:
        """解析定价.

        优先使用 model_pricing_map 中的模型特定定价，回退到默认定价.

        Args:
            route_type: 路由类型（local/cloud）
            model: 模型标识符

        Returns:
            (input_price, output_price) 元组
        """
        if model in self._model_pricing_map:
            pricing = self._model_pricing_map[model]
            return pricing["input"], pricing["output"]

        if route_type == "cloud":
            return self._cloud_input_price, self._cloud_output_price
        return self._local_input_price, self._local_output_price
