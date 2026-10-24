"""跨 Agent 穿透探针安全套件（Story 5.5 — Agent 三重硬隔离强制执行验证）。

安全审计资产: 21 条穿透探针矩阵（PROBE_MATRIX 单真源常量——穷举枚举断言
非采样置信）+ 8 条辅助用例（对照 4 + 透传 2 + 纯函数直调 1 + 目录真实名
守护 1——不计入拦截率分子分母，OWASP 授权回归正负用例并存惯例）。

探针矩阵审计表（与 PROBE_MATRIX 逐条对应——id 即矩阵编号）:

| #    | 面     | 资源/工具                | 操作    | 前置等级 | 预期 |
|------|--------|--------------------------|---------|---------|------|
| P-01 | Prompt | PROFILE                  | READ    | A=L4    | 448 |
| P-02 | Prompt | SYSTEM_PROMPT            | READ    | A=L4    | 448 |
| P-03 | Prompt | WORKFLOW_CONTEXT         | READ    | A=L4    | 448 |
| P-04 | Prompt | WORKFLOW_CONTEXT         | WRITE   | A=L4    | 448 |
| P-05 | Prompt | SESSION                  | READ    | A=L4    | 448 |
| P-06 | Prompt | SANDBOX_SESSION          | READ    | A=L4    | 448 |
| P-07 | Prompt | SYSTEM_PROMPT            | WRITE   | A=L4    | 448 |
| T-01 | 工具   | 白名单外工具（窄配置）    | EXECUTE | A=L4    | 449 |
| T-02 | 工具   | TOOL_EXECUTION_HISTORY   | READ    | A=L4    | 448 |
| T-03 | 工具   | TOOL_EXECUTION_HISTORY   | WRITE   | A=L4    | 448 |
| T-04 | 工具   | 白名单外工具（目录真实名，窄配置）| EXECUTE | A=L4 | 449 |
| D-01 | 数据   | AGENT_STATE              | READ    | A=L4    | 448 |
| D-02 | 数据   | AGENT_STATE              | WRITE   | A=L4    | 448 |
| D-03 | 数据   | ISOLATION_STATE          | READ    | A=L4    | 448 |
| D-04 | 数据   | ISOLATION_STATE          | WRITE   | A=L4    | 448 |
| D-05 | 数据   | SESSION                  | WRITE   | A=L4    | 448 |
| D-06 | 数据   | MEMORY                   | READ    | A=L4    | 448 |
| D-07 | 数据   | MEMORY                   | WRITE   | A=L4    | 448 |
| D-08 | 数据   | BLACKBOARD（shared）     | WRITE   | A=L4    | 449（READ_ONLY）|
| D-09 | 数据   | BLACKBOARD（shared）     | WRITE   | A=L3（切换）| 449（受限写 MVP 拒）|
| D-10 | 数据   | SHARED_WORKSPACE（shared）| WRITE  | A=L4    | 449（READ_ONLY）|

统计: 448×16 + 449×5 = 21，拦截率断言面 = 21/21。「面」列是攻击后果审计归类
（读上下文/提示词类→Prompt 泄露；状态/记忆/历史类→数据面；同资源 READ/WRITE
可分属两面）；分派轴是 ProbeSpec.face（T-02/T-03 的 TOOL_EXECUTION_HISTORY 资源
访问走 ensure_agent_access——face="access"，R3-F2 词汇碰撞消歧）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_isolation_security.py -v

归属（2026-10-24 用户裁定）: 探针套件归入集成测试范畴（原规划 tests/security
独立目录 + security marker + 覆盖率专项裁撤——专项不合适，复用集成既有基建
real_redis fixture 与 CI integration job 挂载面，marker 非必要不新增）。

测试隔离:
    - function 级 A/B fixture（每探针独立实例化——杜绝等级切换跨探针污染；
      D-09/T-01/T-04 用例内自建 A + 窄 loader/切换，fixture 产物仅 B 复用为 target）
    - _RecordingEventPublisher 是事件发布端口记录替身（RabbitMQ 基础设施豁免面
      ——非被测面 mock）；守卫链四件全真实（安全测试 = 验收级真实服务纪律）
    - 双键清理 + exists 复核（禁 delete_pattern/flush）
    - T-01/T-04 配置篡改: ceo_agent.yaml 全文复制 tmp 仅收窄 allowed_tools
      （5-4 AC-2.3 先例）+ 基线锚断言（loader 读回白名单恰为收窄集）
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from src.domain.events.enums import IsolationLevel
from src.domain.value_objects.isolation_access import (
    AccessOperation,
    IsolationResource,
    IsolationViolationKind,
    decide_isolation_access,
)
from src.domain.value_objects.isolation_policy import get_isolation_policy
from src.infrastructure.storage.redis.key_builder import build_key

# 归入集成族（2026-10-24 用户裁定——marker 非必要不新增，探针需真实 Redis）
pytestmark = [
    pytest.mark.redis,
    pytest.mark.integration,
]

REPO_ROOT = Path(__file__).resolve().parents[2]


class ProbeSpec(NamedTuple):
    """单条穿透探针定义（id 即矩阵编号——审计可对照）。"""

    id: str
    face: str  # 分派轴: "access"（资源访问）| "tool"（工具白名单）
    resource: IsolationResource | None
    tool_name: str | None
    operation: AccessOperation | None
    level: IsolationLevel | None  # None=保持默认 L4；非 None=用例内先服务级切换
    expected_code: str


PROBE_MATRIX: tuple[ProbeSpec, ...] = (
    # ===== Prompt 面（P-01~P-07——读上下文/提示词类资源，攻击后果=Prompt 泄露）=====
    ProbeSpec(
        id="P-01",
        face="access",
        resource=IsolationResource.PROFILE,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="P-02",
        face="access",
        resource=IsolationResource.SYSTEM_PROMPT,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="P-03",
        face="access",
        resource=IsolationResource.WORKFLOW_CONTEXT,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="P-04",
        face="access",
        resource=IsolationResource.WORKFLOW_CONTEXT,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="P-05",
        face="access",
        resource=IsolationResource.SESSION,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="P-06",
        face="access",
        resource=IsolationResource.SANDBOX_SESSION,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="P-07",
        face="access",
        resource=IsolationResource.SYSTEM_PROMPT,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    # ===== 工具面（T-01~T-04）=====
    ProbeSpec(
        id="T-01",
        face="tool",
        resource=None,
        tool_name="绝不在白名单的虚构工具",
        operation=None,
        level=None,
        expected_code="EXCEPTION_449",
    ),
    ProbeSpec(
        id="T-02",
        face="access",
        resource=IsolationResource.TOOL_EXECUTION_HISTORY,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="T-03",
        face="access",
        resource=IsolationResource.TOOL_EXECUTION_HISTORY,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="T-04",
        face="tool",
        resource=None,
        tool_name="GE-麦肯锡矩阵",
        operation=None,
        level=None,
        expected_code="EXCEPTION_449",
    ),
    # ===== 数据面（D-01~D-10——状态/记忆/历史类资源）=====
    ProbeSpec(
        id="D-01",
        face="access",
        resource=IsolationResource.AGENT_STATE,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-02",
        face="access",
        resource=IsolationResource.AGENT_STATE,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-03",
        face="access",
        resource=IsolationResource.ISOLATION_STATE,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-04",
        face="access",
        resource=IsolationResource.ISOLATION_STATE,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-05",
        face="access",
        resource=IsolationResource.SESSION,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-06",
        face="access",
        resource=IsolationResource.MEMORY,
        tool_name=None,
        operation=AccessOperation.READ,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-07",
        face="access",
        resource=IsolationResource.MEMORY,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_448",
    ),
    ProbeSpec(
        id="D-08",
        face="access",
        resource=IsolationResource.BLACKBOARD,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_449",
    ),
    ProbeSpec(
        id="D-09",
        face="access",
        resource=IsolationResource.BLACKBOARD,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=IsolationLevel.L3_SOFT,
        expected_code="EXCEPTION_449",
    ),
    ProbeSpec(
        id="D-10",
        face="access",
        resource=IsolationResource.SHARED_WORKSPACE,
        tool_name=None,
        operation=AccessOperation.WRITE,
        level=None,
        expected_code="EXCEPTION_449",
    ),
)


# ===================================================================
# 组装与 fixture（function 级 A/B——每探针独立实例化）
# ===================================================================


class _RecordingEventPublisher:
    """事件发布端口记录替身（基础设施豁免面——RabbitMQ 非被测面）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _assemble_guard_chain(redis_client: Any, config_loader: Any = None) -> dict[str, Any]:
    """手动组装守卫真实链（场景级客户端——禁 resolve 发命令纪律）。

    Args:
        redis_client: 场景级 Redis 客户端（integration conftest real_redis fixture——复用既有基建）。
        config_loader: 配置加载器（None 时经 resolve 取生产实例；窄配置探针
            传入 tmp config_dir 的 YamlAgentConfigLoader——配置篡改通道）。

    Returns:
        组装链字典（guard/instantiate_use_case/isolation_service/agent_repository/
        recorder/config_loader）。
    """
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    effective_loader = config_loader if config_loader is not None else resolve("agent_config_loader")
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = _RecordingEventPublisher()
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=effective_loader,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=effective_loader,
    )
    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=effective_loader,
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    return {
        "guard": guard,
        "instantiate_use_case": instantiate_use_case,
        "isolation_service": isolation_service,
        "agent_repository": agent_repository,
        "recorder": recorder,
        "config_loader": effective_loader,
    }


def _make_narrow_loader(tmp_path: Path, allowlist: tuple[str, ...]) -> Any:
    """配置篡改: ceo_agent.yaml 全文复制 tmp 仅替换 allowed_tools（基线锚前置）。

    生产 yaml 保持宽白名单（5-3 主链兼容）；探针判别力经收窄获得
    （5-4 AC-2.3 驱动先例——最小 yaml 过不了 loader 逐段强校验）。
    """
    import yaml as yaml_lib

    from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

    source = REPO_ROOT / "configs" / "agents" / "ceo_agent.yaml"
    data = yaml_lib.safe_load(source.read_text(encoding="utf-8"))
    data["eip_config"]["allowed_tools"] = list(allowlist)
    target = tmp_path / "ceo_agent.yaml"
    target.write_text(yaml_lib.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    shutil.copystat(source, target)
    return YamlAgentConfigLoader(config_dir=tmp_path)


@pytest.fixture
async def guard_chain(real_redis: Any) -> Any:
    """function 级 A/B fixture（每探针独立实例化默认 L4 A/B + 双键登记清理）。"""
    from src.domain.entities.agent import AgentRole

    chain = _assemble_guard_chain(real_redis)
    instantiation_a = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
    instantiation_b = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
    chain["agent_a"] = instantiation_a.agent_id
    chain["agent_b"] = instantiation_b.agent_id
    chain["agent_ids"] = [instantiation_a.agent_id, instantiation_b.agent_id]
    yield chain

    # teardown: 双键精确删除 + exists 复核（delete 幂等——被测删除键二次删无害）
    for agent_id in chain["agent_ids"]:
        for namespace in ("agent", "isolation"):
            await real_redis.delete(build_key(namespace, str(agent_id)))
    for agent_id in chain["agent_ids"]:
        for namespace in ("agent", "isolation"):
            key = build_key(namespace, str(agent_id))
            assert not await real_redis.exists(key), f"探针键未清理: {key}"


# ===================================================================
# 21 条穿透探针（参数化——独立用例 id 可对照矩阵审计）
# ===================================================================


@pytest.mark.parametrize("probe", PROBE_MATRIX, ids=[p.id for p in PROBE_MATRIX])
async def test_probe_cross_agent_access(probe: ProbeSpec, guard_chain: Any, tmp_path: Path, real_redis: Any) -> None:
    """单条穿透探针: 按 face 分派 ensure_agent_access / ensure_tool_access，
    断言异常类型 + code + context 关键字段（安全审计资产——矩阵见模块 docstring）。"""
    from src.domain.entities.agent import AgentRole
    from src.domain.exceptions import IsolationAccessViolationError, IsolationOperationForbiddenError

    expected_cls = IsolationAccessViolationError if probe.expected_code == "EXCEPTION_448" else IsolationOperationForbiddenError
    chain = guard_chain
    actor_id = chain["agent_a"]
    target_id = chain["agent_b"]

    # 特殊三条用例内自建 actor（窄配置/等级切换——fixture 的 A/B 中仅 B 复用为 target）:
    # T-01/T-04 窄 loader 链（配置篡改 + 基线锚）；D-09 默认链 + 服务级切 L3
    if probe.id in ("T-01", "T-04"):
        narrow_allowlist = ("PESTEL 分析",)  # 收窄到单工具——判别力最大化
        narrow_loader = _make_narrow_loader(tmp_path, narrow_allowlist)
        # 基线锚: loader 读回白名单恰为收窄集（篡改前置验证——防配置篡改静默失效）
        narrow_config = await narrow_loader.load(AgentRole.CEO)
        assert narrow_config.allowed_tools == narrow_allowlist, "窄配置基线锚失败（配置篡改未生效）"
        narrow_chain = _assemble_guard_chain(real_redis, config_loader=narrow_loader)
        narrow_instantiation = await narrow_chain["instantiate_use_case"].execute(role=AgentRole.CEO)
        chain = narrow_chain
        actor_id = narrow_instantiation.agent_id
        target_id = guard_chain["agent_b"]  # target 复用 fixture 的 B（等级状态无关判定）
        guard_chain["agent_ids"].append(narrow_instantiation.agent_id)
    elif probe.level is not None:  # D-09: 服务级切换 actor 到 L3
        await chain["isolation_service"].switch_isolation_level(actor_id, probe.level, f"探针-{probe.id}-切换")

    try:
        if probe.face == "tool":
            with pytest.raises(expected_cls) as exc_info:
                await chain["guard"].ensure_tool_access(actor_id, probe.tool_name or "")
        else:
            with pytest.raises(expected_cls) as exc_info:
                await chain["guard"].ensure_agent_access(actor_id, target_id, probe.resource, probe.operation)
    finally:
        # 窄链自建 actor 的双键即时清理（fixture teardown 只清登记名单——此处补删）
        if probe.id in ("T-01", "T-04"):
            for namespace in ("agent", "isolation"):
                await real_redis.delete(build_key(namespace, str(actor_id)))

    error = exc_info.value
    assert error.code == probe.expected_code, f"{probe.id}: code 漂移 {error.code}"
    if probe.expected_code == "EXCEPTION_448":
        assert probe.resource is not None and probe.operation is not None, f"{probe.id}: 448 探针必为 access 面"
        assert error.context["actor_agent_id"] == str(actor_id)
        assert error.context["target_agent_id"] == str(target_id)
        assert error.context["resource"] == probe.resource.value
        assert error.context["operation"] == probe.operation.value
        assert "隔离" in error.context["reason"], f"{probe.id}: reason 须含等级名 {error.context['reason']!r}"
    else:
        assert error.context["agent_id"] == str(actor_id)
        assert "reason" in error.context
        if probe.face == "tool":
            assert probe.tool_name in error.context["reason"], f"{probe.id}: reason 须含工具名"


# ===================================================================
# 7 条辅助用例（对照 4 + 透传 2 + 纯函数直调 1——不计入拦截率分子分母）
# ===================================================================


async def test_allow_self_private_resource_read(guard_chain: Any) -> None:
    """放行对照①: 自身 private 资源读（actor==target——矩阵 private+self 格）。"""
    await guard_chain["guard"].ensure_agent_access(
        guard_chain["agent_a"], guard_chain["agent_a"], IsolationResource.PROFILE, AccessOperation.READ
    )


async def test_allow_blackboard_read_l4(guard_chain: Any) -> None:
    """放行对照②: BLACKBOARD READ L4（shared+READ 全等级放行——防一刀切过阻断）。"""
    await guard_chain["guard"].ensure_agent_access(
        guard_chain["agent_a"], guard_chain["agent_b"], IsolationResource.BLACKBOARD, AccessOperation.READ
    )


async def test_allow_tool_in_allowlist_l4(guard_chain: Any) -> None:
    """放行对照③: 白名单内工具 L4（经 AgentConfig.allowed_tools 真源——生产宽白名单）。"""
    await guard_chain["guard"].ensure_tool_access(guard_chain["agent_a"], "PESTEL 分析")


async def test_allow_ensure_agent_executable_l4_policy(guard_chain: Any) -> None:
    """放行对照④: ensure_agent_executable 放行返回 L4 策略（三维度断言——
    第三方法主路径覆盖）。"""
    from src.domain.value_objects.isolation_policy import DataIsolationMode

    policy = await guard_chain["guard"].ensure_agent_executable(guard_chain["agent_a"])
    assert policy.prompt_isolation is True
    assert policy.tool_isolation is True
    assert policy.data_isolation is DataIsolationMode.READ_ONLY


async def test_passthrough_443_random_uuid(guard_chain: Any) -> None:
    """守卫透传①: 443 随机 UUID（经 ensure_agent_executable 自体形态——不产生键零残留）。"""
    from src.domain.exceptions import AgentNotFoundError

    with pytest.raises(AgentNotFoundError):
        await guard_chain["guard"].ensure_agent_executable(uuid.uuid4())


async def test_passthrough_447_isolation_key_missing(guard_chain: Any, real_redis: Any) -> None:
    """守卫透传②: 447 删 actor A 侧隔离键（单边语义——guard 只取 actor state，
    删 target 键将得 448 非 447；A 真实创建已登记 fixture 双键清理）。"""
    from src.domain.exceptions import IsolationStateNotInitializedError

    await real_redis.delete(build_key("isolation", str(guard_chain["agent_a"])))
    with pytest.raises(IsolationStateNotInitializedError):
        await guard_chain["guard"].ensure_agent_executable(guard_chain["agent_a"])


def test_pure_decide_l1_forward_and_invariants() -> None:
    """纯函数直调: L1 前向格（private+cross 放行 + shared WRITE 放行）+ 242 不变量
    （补 isolation_access 的 L1 分支/校验分支安全侧覆盖——零 IO 纯端口级）。"""
    from src.domain.exceptions import EntityValidationError

    policy = get_isolation_policy(IsolationLevel.L1_FUSED)
    decision = decide_isolation_access(
        policy, cross_agent=True, resource=IsolationResource.PROFILE, operation=AccessOperation.READ
    )
    assert decision.allowed is True
    shared_write = decide_isolation_access(
        policy, cross_agent=True, resource=IsolationResource.BLACKBOARD, operation=AccessOperation.WRITE
    )
    assert shared_write.allowed is True

    with pytest.raises(EntityValidationError):
        from src.domain.value_objects.isolation_access import IsolationAccessDecision

        IsolationAccessDecision(allowed=True, violation=IsolationViolationKind.ACCESS_VIOLATION, reason="矛盾")


def test_t04_tool_name_in_catalog() -> None:
    """目录真实名守护: T-04 探针名必须真实存在于 TOOL_CATALOG（R3-F2——把
    「TOOL_CATALOG 真实存在名」从文档属性升级为程序属性，目录改名/删名即红）。"""
    from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

    t04 = next(p for p in PROBE_MATRIX if p.id == "T-04")
    assert t04.tool_name in {t.name for t in TOOL_CATALOG}, "T-04 探针名不在 TOOL_CATALOG（目录演化未同步探针）"
