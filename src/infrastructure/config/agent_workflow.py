"""基础设施层 Agent 工作流装配工厂模块

agent_workflow_use_case 端口注册工厂（Story 5.8 交付——组合根装配用）。
归宿注记（用户裁定 2026-10-31：组合根零私有函数纪律——工厂迁至
infrastructure/config/，组合根仅装配）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_agent_workflow_use_case(resolver: Any) -> Any:
    """Story 5.8 — agent_workflow_use_case 注册工厂（def 承载 try/except——lambda 语法不可能）。

    第六依赖 evaluation_harness 经 resolve_optional 可选注入（audit_service 先例
    ——注册缺失/构造失败降级 None）；评估接线配置错误（不在 resolve_optional
    默认 fallback_on 内）被本工厂捕获降级 None：评估面损失不阻断主链（可观测
    附加面哲学——风险 #9，ConfigurationError 非 RuntimeError 子类故须显式捕获；
    SINGLETON 失败不缓存，后续 resolve 重试不残留毒化）。

    适用面注记（CR1-F16——实测收窄；R2 勘误：原「评估独有失败面（a）」实为下述
    窗口的子情形——resolver lambda 的子 resolve 异常已被 resolve_optional 默认
    fallback_on 吸收，逃逸的 ConfigurationError 与 llm_client 同源自 env）：本防护
    的净值场景是 **llm_client 单例已缓存后 env 中途损坏**（或测试 override
    llm_client 后注入坏 env）的窗口形态——若 UDMR_* env 损坏发生在冷启动，主链
    五 resolve 先经 llm_client→build_default_llm_config→from_env 同源 101 失败
    （预存面：llm_client 无 from_env 防护，非 5.8 引入——CR1-DF1 登记），工厂
    降级触发但 use case 仍失败。
    """
    use_case_cls = __import__(
        "src.application.use_cases.run_agent_workflow",
        fromlist=["RunAgentWorkflowUseCase"],
    ).RunAgentWorkflowUseCase
    from src.domain.exceptions import ConfigurationError

    try:
        evaluation_harness = resolver.resolve_optional("agent_evaluation")
    except ConfigurationError as error:
        logger.warning("评估接线降级跳过（agent_evaluation 构造失败——评估面损失不阻断主链）: %s", error)
        evaluation_harness = None
    # Story 5.9 — 第七依赖同款降级防护（agent_drift resolve_optional 可选接线：
    # 检测器构造失败 → None 不阻断 bootstrap；CR1-DF2[5.8] 一并处置——降级路径
    # 测试覆盖经 5-9 验收 AC-4.1 承载）
    try:
        drift_detector = resolver.resolve_optional("agent_drift")
    except ConfigurationError as error:
        logger.warning("漂移检测接线降级跳过（agent_drift 构造失败——漂移检测面损失不阻断主链）: %s", error)
        drift_detector = None
    # Story 5.10 — 第八依赖同款降级防护（agent_checkpoint resolve_optional 可选
    # 接线：Recorder 构造失败 → None 不阻断 bootstrap；CR1-DF2[5.8] 家族延续——
    # 降级路径测试覆盖经 5-10 验收 AC-4.1 承载。同窗纪律（R1-F1）：本注入与第八
    # 构造参数 + record 块三者同一 Task 落地（参数不存在窗口注入 kwarg 必 TypeError）
    try:
        checkpoint_recorder = resolver.resolve_optional("agent_checkpoint")
    except ConfigurationError as error:
        logger.warning("评估历史接线降级跳过（agent_checkpoint 构造失败——持久化面损失不阻断主链）: %s", error)
        checkpoint_recorder = None
    return use_case_cls(
        agent_repository=resolver.resolve("agent_repository"),
        agent_profile_use_case=resolver.resolve("agent_profile_use_case"),
        agent_engine=resolver.resolve("agent_engine"),
        agent_workflow_service=resolver.resolve("agent_workflow_service"),
        isolation_guard=resolver.resolve("isolation_guard_service"),
        evaluation_harness=evaluation_harness,
        drift_detector=drift_detector,
        checkpoint_recorder=checkpoint_recorder,
    )
