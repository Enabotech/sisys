"""Story 6-4 — SDD 架构约束验证测试（五验证器 A~E）。

epics L2218 钦定文件名（tests/unit/architecture/test_json_chain_of_thought.py
——同名冲突检查实证零冲突）。形态对齐 6-3 test_checkpoint.py（SRC_ROOT +
AST 级 helper + 精确词边界 grep 断言——非 TDD 单元测试，验证架构约束遵守）：

- 验证器 A——EVIDENCE_PACKAGE 唯一构造位（全 src 构造点扫描：枚举定义处
  + chain_of_thought_archive_service.py 唯一构造位——激活唯一性守护）
- 验证器 B——服务落位（ChainOfThoughtArchiveService 定义唯一/端口落位
  application/ports/实现落位 application/services/组合根注册/禁本地 Protocol）
- 验证器 C——归档依赖契约稳定（6-4 代码审查 CR1-F4：原「零 diff」git 断言
  仅在未提交窗口有判别力、提交后 CI 恒真失效——转结构断言持久守护：
  archive_plan 七参数签名/ArchiveType 枚举值域/ChainOfThought VO 五字段）
- 验证器 D——BLM 挂接点（三方法挂接段存在性+尾参可选注入+回传通道三件套
  存在性 R1-F1+chain_records 不进快照 state_data 七键恒定+不进事件 payload
  投影白名单五键恒定）
- 验证器 E——负向契约断言面（四文件零 CheckpointReached 引用+零思维链
  事件登记缺席断言+planning 段 485-489 预留码零占用——CR1-F4 同源转持久
  缺席断言，锚定 6-4 专属 token 防既有 445 类名误伤）

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/architecture/test_json_chain_of_thought.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
REPO_ROOT = Path(__file__).resolve().parents[3]

#: 6-4 交付件锚（服务/端口/用例三文件）
CHAIN_SERVICE_FILE = SRC_ROOT / "application" / "services" / "chain_of_thought_archive_service.py"
CHAIN_PORT_FILE = SRC_ROOT / "application" / "ports" / "chain_of_thought_archive.py"
CHAIN_USE_CASE_FILE = SRC_ROOT / "application" / "use_cases" / "get_blm_chain_trace.py"

#: 归档服务与实体（验证器 C 零触碰对象）
ARCHIVE_SERVICE_FILE = SRC_ROOT / "application" / "services" / "strategic_archive_service.py"
ARCHIVE_ENTITY_FILE = SRC_ROOT / "domain" / "entities" / "strategic_archive.py"

#: 快照七键契约（OD-8——chain_records 不进 Redis state_data）
SNAPSHOT_SEVEN_KEYS = {
    "plan_id",
    "phase",
    "current_step",
    "completed_steps",
    "total_steps",
    "degraded_steps",
    "timeline",
}

#: AgentDecided 投影五键白名单（DC-11——chain_records/VO 禁入 payload）
PROJECTION_FIVE_KEYS = {"workflow_status", "task_summary", "chain_summary", "evidence_ref", "retry_count"}


def _read(path: Path) -> str:
    """读源文件（UTF-8）。"""
    return path.read_text(encoding="utf-8")


#: 四守护文件（验证器 E 缺席断言对象——事件通道/路由/码段/异常映射）
GUARD_FILES: dict[str, Path] = {
    "configs/event_channels.yaml": REPO_ROOT / "configs" / "event_channels.yaml",
    "channel_router.py": SRC_ROOT / "infrastructure" / "messaging" / "channel_router.py",
    "_code_ranges.py": SRC_ROOT / "domain" / "exceptions" / "_code_ranges.py",
    "exception_handlers.py": SRC_ROOT / "interfaces" / "api" / "exception_handlers.py",
}


# ===================================================================
# 验证器 A：EVIDENCE_PACKAGE 唯一构造位
# ===================================================================


class TestValidatorAEvidencePackageUniqueConstruction:
    """A——ArchiveType.EVIDENCE_PACKAGE 全 src 构造点扫描（激活唯一性）。"""

    def test_evidence_package_construction_sites_unique(self) -> None:
        """构造位唯一：枚举定义处（strategic_archive.py）+ 组装归档服务一处
        代码级构造（ArchiveType.EVIDENCE_PACKAGE 成员引用）——其余全 src 零
        出现（CR1-F9 如实化：正则为全 token 行扫描含注释/docstring 文本，
        当前全 src 许可外零 token 含文本命中——过严方向守护，非恒真）。"""
        occurrences: list[tuple[str, int]] = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            for line_no, line in enumerate(_read(path).splitlines(), start=1):
                # 代码级构造判据：ArchiveType.EVIDENCE_PACKAGE 成员引用（排除
                # 纯 docstring/help 文本——strip 后非赋值/传参形态）
                if re.search(r"ArchiveType\.EVIDENCE_PACKAGE", line):
                    occurrences.append((str(path.relative_to(SRC_ROOT)), line_no))
        service_relative = "application/services/chain_of_thought_archive_service.py"
        enum_relative = "domain/entities/strategic_archive.py"
        service_construction = [occ for occ in occurrences if occ[0] == service_relative]
        assert service_construction, "组装归档服务缺 EVIDENCE_PACKAGE 构造（首激活缺失）"
        others = [occ for occ in occurrences if occ[0] not in (enum_relative, service_relative)]
        assert not others, f"ArchiveType.EVIDENCE_PACKAGE 代码级引用出现于许可外文件（唯一构造位违例）: {others}"

    def test_construction_passes_enum_member_not_string(self) -> None:
        """构造传枚举成员非裸 str（实体 validate :90-94 拒绝裸 str——R1-P3 补注）。"""
        service_text = _read(CHAIN_SERVICE_FILE)
        assert "archive_type=ArchiveType.EVIDENCE_PACKAGE" in service_text, (
            "归档调用必须显式传枚举成员（archive_type=ArchiveType.EVIDENCE_PACKAGE）"
        )


# ===================================================================
# 验证器 B：服务落位
# ===================================================================


class TestValidatorBServicePlacement:
    """B——定义唯一/四层落位/组合根注册/禁本地 Protocol。"""

    def test_service_definition_unique_in_src(self) -> None:
        """ChainOfThoughtArchiveService 定义位唯一（精确词边界）。"""
        pattern = re.compile(r"^class ChainOfThoughtArchiveService\(", re.MULTILINE)
        definition_files = [
            str(path.relative_to(SRC_ROOT)) for path in sorted(SRC_ROOT.rglob("*.py")) if pattern.search(_read(path))
        ]
        assert definition_files == ["application/services/chain_of_thought_archive_service.py"], (
            f"服务定义位漂移: {definition_files}"
        )

    def test_port_in_application_ports(self) -> None:
        """端口协议落位 application/ports/（@runtime_checkable Protocol）。"""
        port_text = _read(CHAIN_PORT_FILE)
        assert "@runtime_checkable" in port_text
        assert "class ChainOfThoughtArchiveServicePort(Protocol)" in port_text
        assert "class StepChainMaterial" in port_text
        assert "class ChainRecord" in port_text
        assert "class ChainOfThoughtTraceView" in port_text

    def test_use_case_in_application_use_cases(self) -> None:
        """追溯用例落位 application/use_cases/。"""
        assert CHAIN_USE_CASE_FILE.exists()
        assert "class GetBlmChainTraceUseCase" in _read(CHAIN_USE_CASE_FILE)

    def test_composition_root_registers_both_ports(self) -> None:
        """组合根注册两端口（chain_of_thought_archive_service + blm_chain_trace_use_case）。"""
        root_text = _read(SRC_ROOT / "composition_root.py")
        assert 'name="chain_of_thought_archive_service"' in root_text
        assert 'name="blm_chain_trace_use_case"' in root_text

    def test_no_local_protocol_in_service_file(self) -> None:
        """服务文件禁本地 Protocol 定义（端口抽象统一落端口文件——红线）。"""
        service_text = _read(CHAIN_SERVICE_FILE)
        assert "Protocol" not in service_text, "服务文件不得本地定义 Protocol 抽象"


# ===================================================================
# 验证器 C：归档依赖契约稳定
# ===================================================================


class TestValidatorCArchiveContractStable:
    """C——6-4 挂接依赖的归档服务/实体/VO 契约面恒定。

    6-4 代码审查 CR1-F4 修订：原「零 diff」git 断言仅在未提交窗口有判别力
    （提交后 CI 干净检出 diff 恒空 → 恒真失效），转结构断言持久守护契约面
    ——行为级覆盖（集成①/验收 S5 真实链）承载其余零改动语义。
    """

    def test_archive_plan_signature_seven_params(self) -> None:
        """archive_plan 七参数签名恒定（6-4 挂接依赖面——phoenix_tracer R3-14
        inspect.signature 构造签名不变断言同款先例）。"""
        import inspect

        from src.application.services.strategic_archive_service import StrategicArchiveService

        params = list(inspect.signature(StrategicArchiveService.archive_plan).parameters)
        assert params == [
            "self",
            "plan_id",
            "plan_type",
            "archive_type",
            "assumptions",
            "decision_basis",
            "execution_deviation",
            "evidence_blob",
        ], f"archive_plan 签名漂移（6-4 挂接依赖面断裂风险）: {params}"

    def test_archive_type_enum_domain_stable(self) -> None:
        """ArchiveType 枚举值域恒定（EVIDENCE_PACKAGE 复用激活不扩值域——
        6-4 是唯一构造位，值域漂移即枚举契约变更）。"""
        from src.domain.entities.strategic_archive import ArchiveType

        assert [member.name for member in ArchiveType] == [
            "ASSUMPTION",
            "DECISION",
            "DEVIATION",
            "EVIDENCE_PACKAGE",
        ], "ArchiveType 枚举值域漂移（6-4 复用前提断裂）"

    def test_chain_of_thought_vo_five_fields_stable(self) -> None:
        """ChainOfThought VO 五字段恒定（domain 复用契约面——五字段名清单
        与冻结表逐一对应，字段漂移即组装映射表失配）。"""
        from dataclasses import fields

        from src.domain.value_objects.chain_of_thought import ChainOfThought

        field_names = [field.name for field in fields(ChainOfThought)]
        assert field_names == [
            "input_summary",
            "reflection",
            "tools_used",
            "constraints_check",
            "final_answer",
        ], f"ChainOfThought VO 字段漂移（组装映射冻结表失配）: {field_names}"


# ===================================================================
# 验证器 D：BLM 挂接点 + 回传通道三件套 + 快照/事件零污染
# ===================================================================


class TestValidatorDBlmHookupAndChannels:
    """D——挂接段/尾参/三件套/state_data 七键/投影五键。"""

    def test_three_methods_hookup_segments_present(self) -> None:
        """三方法挂接段存在（各方法末尾 _compose_and_archive_chain 调用×3）。"""
        service_text = _read(SRC_ROOT / "application" / "services" / "blm_planning_service.py")
        hookup_calls = service_text.count("await self._compose_and_archive_chain(")
        assert hookup_calls == 3, f"三方法挂接段实测={hookup_calls} 处 期望=3（gap/六子/synthesis）"

    def test_tail_param_optional_injection(self) -> None:
        """尾参可选注入（chain_archive_service: ... | None = None）。"""
        service_text = _read(SRC_ROOT / "application" / "services" / "blm_planning_service.py")
        assert "chain_archive_service: ChainOfThoughtArchiveServicePort | None = None" in service_text, (
            "尾参形态漂移（可选注入应为 None 缺省——None 时零挂接等价性）"
        )

    def test_run_state_accumulation_field(self) -> None:
        """回传三件套①：_PlanRunState.chain_records 累积位。"""
        service_text = _read(SRC_ROOT / "application" / "services" / "blm_planning_service.py")
        assert "self.chain_records: list[ChainRecord] = []" in service_text

    def test_port_protocol_seventh_method(self) -> None:
        """回传三件套②：BlmPlanningServicePort 协议追加 project_chain_records
        （CR1-F3 精确类型锚——元素 ChainRecord 非 Any 弱化形态）。"""
        port_text = _read(SRC_ROOT / "application" / "ports" / "blm_planning.py")
        assert "def project_chain_records(self, plan_id: str) -> list[ChainRecord]" in port_text
        assert "from src.application.ports.chain_of_thought_archive import ChainRecord" in port_text

    def test_graph_adapters_chain_records_writes(self) -> None:
        """回传三件套③：sp_blm_graph 三类节点适配器 chain_records 直写行 ≥3 处。"""
        graph_text = _read(SRC_ROOT / "infrastructure" / "agent_orch" / "graphs" / "sp_blm_graph.py")
        write_count = graph_text.count('"chain_records": service.project_chain_records(')
        assert write_count >= 3, f"图适配器直写行实测={write_count} 处 期望≥3（八节点对称）"

    def test_chain_records_not_in_snapshot_state_data(self) -> None:
        """chain_records 不进快照 state_data（OD-8——to_state_data 七键恒定）。"""
        service_text = _read(SRC_ROOT / "application" / "services" / "blm_planning_service.py")
        to_state_data_block = re.search(r"def to_state_data\(self\).*?return \{(.*?)\}", service_text, re.DOTALL)
        assert to_state_data_block is not None, "to_state_data 方法缺失"
        block_text = to_state_data_block.group(1)
        assert "chain_records" not in block_text, "chain_records 渗入快照 state_data（OD-8 违例）"
        for key in SNAPSHOT_SEVEN_KEYS:
            assert f'"{key}"' in block_text, f"快照七键缺 {key}（契约漂移）"

    def test_chain_records_not_in_event_payload(self) -> None:
        """chain_records/ChainRecord 不进事件 payload（投影白名单五键恒定——DC-11）。"""
        engine_text = _read(SRC_ROOT / "infrastructure" / "agent_orch" / "langgraph_engine.py")
        spblm_block = re.search(r'elif graph_name == "SpBlmGraph".*?decision_result = \{(.*?)\}', engine_text, re.DOTALL)
        assert spblm_block is not None, "SpBlmGraph 投影分支缺失"
        block_text = spblm_block.group(1)
        for key in PROJECTION_FIVE_KEYS:
            assert f'"{key}"' in block_text, f"投影五键缺 {key}（白名单漂移）"
        assert "chain_records" not in block_text or "final_answer" in block_text, (
            "投影分支引用 chain_records 必须经末条 final_answer 纯标量取值（VO 禁入 payload）"
        )

    def test_result_default_tail_field(self) -> None:
        """BlmPlanningResult 默认尾字段 chain_records（零破坏——OD-9②；
        CR1-F3 精确类型锚——AC-2 钦定 tuple[ChainRecord, ...]）。"""
        port_text = _read(SRC_ROOT / "application" / "ports" / "blm_planning.py")
        assert "chain_records: tuple[ChainRecord, ...] = ()" in port_text

    def test_sp_blm_state_key_added(self) -> None:
        """SpBlmState 加 chain_records 键（TypedDict total=False 零破坏）。"""
        schemas_text = _read(SRC_ROOT / "infrastructure" / "agent_orch" / "schemas.py")
        assert "chain_records: list[Any]" in schemas_text


# ===================================================================
# 验证器 E：负向契约断言面零修改复跑
# ===================================================================


class TestValidatorENegativeContractFace:
    """E——四文件零 CheckpointReached 引用（6-4 改动 blm_planning_service.py
    不引入该引用即零适配通过——test_event_channel_mapping_blm_planning.py
    既有两用例的守护基础）。"""

    BLM_DELIVERY_FILES = (
        "application/services/blm_planning_service.py",
        "application/use_cases/run_blm_planning.py",
        "application/use_cases/get_blm_planning_status.py",
        "application/services/blm_planning_prompts.py",
    )

    def test_no_checkpoint_reached_in_blm_delivery_files(self) -> None:
        """四文件零 CheckpointReached 引用（6-3 语义分立守护——零修改通过实证）。"""
        for relative in self.BLM_DELIVERY_FILES:
            content = _read(SRC_ROOT / relative)
            assert "CheckpointReached" not in content, f"{relative} 不得引用 CheckpointReached（6.3 语义分立——负向契约面违例）"

    def test_delivery_files_no_chain_vo_event_references(self) -> None:
        """6-4 新事件红线守护面：交付文件零思维链事件类型构造（零新事件——OD-6）。"""
        for relative in (
            "application/services/blm_planning_service.py",
            "application/services/chain_of_thought_archive_service.py",
        ):
            content = _read(SRC_ROOT / relative)
            for marker in ("ChainOfThoughtCreated(", "ChainArchived(", "BlmChainDecided("):
                assert marker not in content, f"{relative} 构造思维链专属事件 {marker}（零新事件违例——OD-6）"

    def test_guard_files_no_chain_event_registration(self) -> None:
        """四守护文件零思维链事件登记（零新事件——OD-6 持久缺席断言）。

        CR1-F4 修订：原 git diff 断言提交后恒真失效——转 token 缺席断言。
        token 锚定 6-4 事件名族（chain_of_thought/ChainArchived/BlmChain——
        实测四文件零命中）；不含 ChainOfThought 大驼峰（既有 445 类
        ChainOfThoughtValidationError 是 5-3 合法登记非事件）与裸 chain
        子串（撞 ToolChainExecuted 既有登记）。
        """
        event_tokens = ("chain_of_thought", "ChainArchived", "BlmChain")
        for name, path in GUARD_FILES.items():
            content = _read(path)
            for token in event_tokens:
                assert token not in content, f"{name} 出现思维链事件登记 {token}（零新事件违例——OD-6）"

    def test_reserved_code_range_485_489_unoccupied(self) -> None:
        """planning 段 485-489 预留码零占用（零新异常——OD-6 持久缺席断言）。

        _code_ranges.py:186-190 钦定 486-489 留 6-6 恢复执行面——本断言在
        6-6 落地新增 EXCEPTION_486+ 时**预期让位更新**（届时按 6-6 实占码段
        收窄缺席区间，非违例）。
        """
        check_targets = {
            **GUARD_FILES,
            "domain/": SRC_ROOT / "domain",
        }
        for name, path in check_targets.items():
            if path.is_dir():
                file_paths = sorted(path.rglob("*.py"))
            else:
                file_paths = [path]
            for file_path in file_paths:
                content = _read(file_path)
                for code in range(485, 490):
                    assert f"EXCEPTION_{code}" not in content, (
                        f"{name} 出现预留码 EXCEPTION_{code} 占用（零新异常违例——OD-6；6-6 落地时本断言让位更新）"
                    )
