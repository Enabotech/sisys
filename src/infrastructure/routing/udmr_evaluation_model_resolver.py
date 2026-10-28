"""UdmrEvaluationModelResolver——评估模型 UDMR in-band 动态路由（Story 5.8 — FR-EV-02）。

仓内首个 per-call 动态路由消费方：``UDMRTask → UDMRService.decide() →
RoutingDecided.selected_model → per-call LLMConfig``——区别于既有 bootstrap 定格的
SSOT 静态接线（``build_default_llm_config`` 取第一个 enabled 云端配置——执行模型）。
epics L1782 AC 钦定「评估模型通过 UDMR 动态路由获取（非硬编码）」。

三分支决策表：
- **cloud**——从注入 cloud_configs 按 ``model == selected_model`` 匹配（非「第一个
  enabled」——区别锚），六连接字段照 ``_build_llm_config_from_cloud_model`` L312-332
  模板映射（该先例 timeout 取客户端基底且无生产调用方——仅字段面参考），timeout
  ← ``llm_timeout``（``build_default_llm_config`` config/llm.py L13-41 同款先例）；
- **local**——``dataclasses.replace(LLMConfig.from_env(), model=selected_model)``
  （本地连接字段随 from_env，模型名对齐路由产物）；from_env 的 ConfigurationError
  101 防御性包装 450（模型解析失败归降级网——运行期 env 损坏不得击穿主链）；
- **匹配失败**（selected_model 不在 cloud_configs——配置漂移）→ AgentEvaluationError
  450 携诊断 context（``{selected_model, available_models}``）——禁静默回退（静默
  错模型比显式失败更危险——评估结果可信性归零）。

依赖方向（六边形合法面）：infrastructure → application（实现
EvaluationModelResolverPort）+ domain（UDMRService/UDMRTask/LLMConfig）+
同层 infrastructure（CloudModelConfig 值）。
"""

from __future__ import annotations

import dataclasses
from uuid import uuid4

from src.application.ports.agent_evaluation import EvaluationModelResolverPort
from src.domain.exceptions import AgentEvaluationError, ConfigurationError
from src.domain.ports.llm_client import LLMConfig
from src.domain.services.udmr_service import UDMRService
from src.domain.value_objects.udmr_task import UDMRTask
from src.infrastructure.config.udmr import CloudModelConfig

__all__ = ["UdmrEvaluationModelResolver"]


class UdmrEvaluationModelResolver(EvaluationModelResolverPort):
    """评估模型解析器（EvaluationModelResolverPort 实现——UDMR in-band 消费方）。

    构造器注入原始值（不依赖 UDMRConfig 聚合——UDMRService 注册先例
    composition_root.py L1627-1647 纪律）；SINGLETON 语义安全（持 UDMRService
    单例引用 + 配置原始值，构造期定格无请求级状态）。

    judge 自评偏差知悉（风险 #10）：decide() 路由仅由健康/合规驱动，评估模型与
    执行模型可能是同一云端模型（业界实证 LLM judge 偏好自身风格 +4~+9 点）——
    运维在 UDMR cloud_configs/策略层将评估路由指向相异强模型（政策层调和）。

    Attributes:
        _udmr_service: UDMR 决策服务（合规→policy.route→健康检查→回退→事件→日志）。
        _cloud_configs: 本 resolver 依据的云端配置清单（per-call 匹配源）。
        _local_model: 本地模型名（与 UDMRService 的 local_model 对齐注入）。
        _llm_timeout: per-call 超时基底（秒——cloud 分支 timeout 来源）。
    """

    def __init__(
        self,
        udmr_service: UDMRService,
        cloud_configs: list[CloudModelConfig],
        local_model: str = "qwen2.5:7b",
        llm_timeout: int = 600,
    ) -> None:
        """初始化评估模型解析器。

        Args:
            udmr_service: 组合根注册的 UDMRService 实例（真实决策链）。
            cloud_configs: 云端模型配置清单（UDMRConfig.from_env().cloud_configs
                原始值注入——构造期定格）。
            local_model: 本地模型名（from_env 回退对齐）。
            llm_timeout: per-call 超时基底（秒）。
        """
        self._udmr_service = udmr_service
        self._cloud_configs = cloud_configs
        self._local_model = local_model
        self._llm_timeout = llm_timeout

    async def resolve_config(self, input_text: str) -> LLMConfig:
        """解析评估调用的 LLM 配置（UDMRTask → decide() → 路由产物匹配）。

        Args:
            input_text: 被评估文本（UDMRTask.input——合规检测与 token 估算输入）。

        Returns:
            LLMConfig: cloud 匹配条目或 local 形态的 per-call 配置。

        Raises:
            AgentEvaluationError: 450——路由产物匹配失败（配置漂移，禁静默回退）
                或 local 分支 from_env 配置解析失败（防御性包装——模型解析失败
                归降级网）。
        """
        task = UDMRTask(
            task_id=uuid4(),
            input=input_text,
            data_residency="CHINA_DOMESTIC",
            preferred_model="",
            allowed_models=[],
        )
        event = await self._udmr_service.decide(task)
        if event.route_type == "cloud":
            return self._match_cloud_config(event.selected_model)
        return self._build_local_config(event.selected_model)

    def _match_cloud_config(self, selected_model: str) -> LLMConfig:
        """cloud 路由匹配（按 model 精确匹配——非「第一个 enabled」）。

        Args:
            selected_model: 路由产物模型名。

        Returns:
            LLMConfig: 匹配条目的 per-call 配置。

        Raises:
            AgentEvaluationError: 450——匹配失败（配置漂移：policy 与 resolver 的
                cloud_configs 不一致——诊断 context 携 selected_model 与可用清单）。
        """
        for cloud in self._cloud_configs:
            if cloud.model == selected_model:
                return LLMConfig(
                    api_type=cloud.api_type,
                    model=cloud.model,
                    endpoint=cloud.endpoint,
                    api_key=cloud.api_key,
                    temperature=cloud.temperature,
                    max_tokens=cloud.max_tokens,
                    timeout=float(self._llm_timeout),
                )
        available = [cloud.model for cloud in self._cloud_configs]
        raise AgentEvaluationError(
            reason="model_resolution",
            message=f"评估模型路由产物匹配失败（配置漂移）：selected_model={selected_model} "
            f"不在 resolver cloud_configs 可用清单内",
            context_extra={
                "selected_model": selected_model,
                "available_models": "、".join(available) if available else "（空）",
            },
        )

    def _build_local_config(self, selected_model: str) -> LLMConfig:
        """local 路由配置（连接字段随 from_env，模型名对齐路由产物）。

        Args:
            selected_model: 路由产物模型名（= local_model）。

        Returns:
            LLMConfig: local 形态 per-call 配置。

        Raises:
            AgentEvaluationError: 450——from_env 抛 ConfigurationError 的防御性
                包装（现实现无校验静默回退默认[llm_client.py L46-96]实际不抛
                101——本包装是防御性契约，未来 from_env 加校验即活）。
        """
        try:
            base = LLMConfig.from_env()
        except ConfigurationError as error:
            raise AgentEvaluationError(
                reason="model_resolution",
                message=f"评估模型 local 路由配置解析失败: {error}",
                cause=error,
            ) from error
        return dataclasses.replace(base, model=selected_model)
