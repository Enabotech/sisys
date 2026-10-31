"""基础设施层 Agent 追踪接线模块

agent_tracing 端口 initialize 接线单元（Story 5.7 交付——bootstrap 装配用）。
归宿注记（用户裁定 2026-10-31：组合根零私有函数纪律——接线单元迁至
infrastructure/config/，组合根仅装配）。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def wire_agent_tracing() -> None:
    """Story 5.7 — agent_tracing 端口 initialize 接线（独立可调用单元——负路径直测）。

    try 罩住整段（resolve + isinstance + initialize——R2-6）：lambda 构造期
    from_env 的 101 抛在 resolve 时发生，只包 initialize 罩不住；配置 typo 只
    损失观测面不阻断主链启动（DC-7 旁路哲学——追踪连「拒绝主链」语义都没有）。
    enabled=false 时 initialize 返回 False NoOp 零开销。
    """
    try:
        from src.application.ports.agent_tracing import AgentTracingPort
        from src.domain.exceptions import ConfigurationError
        from src.domain.ports.resolver import get_resolver

        tracer = get_resolver().resolve("agent_tracing")
        if isinstance(tracer, AgentTracingPort):
            tracer.initialize()
    except ConfigurationError as error:
        logger.warning("agent_tracing 初始化降级跳过（NoOp 态——追踪配置错误不阻断主链）: %s", error)
