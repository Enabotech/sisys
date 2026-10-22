"""YamlAgentConfigLoader 单元测试（Story 5-1）

覆盖 CEO Agent 基础配置 YAML 加载器（infrastructure 层）：
- 正常加载：YAML 字段 → AgentConfig 值对象完整映射（capabilities.* list→tuple 显式转换）
- 失败路径（全部抛 AgentConfigError EXCEPTION_440）：文件缺失 / YAML 语法错 /
  空文件 / role 不匹配 / agent 段必填缺失 / capabilities 整段缺失 /
  空列表（falsy 拦截）/ 非列表标量（isinstance 守卫防逐字符展开）/
  state_ttl 非整数（防裸 TypeError 逃逸）
- 未知键策略：Schema 外多余键忽略（前向兼容——DC-3 回填期新旧配置共存），
  加载成功且字段不受污染

全部用例 tmp_path 真实文件 IO，零 mock。

Run with:
    poetry run pytest tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.entities.agent import AgentRole
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import AgentConfigError

# 合法配置模板（与 configs/agents/ceo_agent.yaml 生产资产同构）
VALID_YAML = """\
agent:
  name: "CEO Agent"
  version: "1.0.0"
  description: "首席执行官 Agent，MVP 单 Agent 方案的战略规划执行者"
identity:
  role: "ceo"
capabilities:
  responsibilities: ["战略方向", "最终决策", "高管协调"]
  domain_knowledge: ["宏观趋势", "竞争格局", "战略意图"]
llm_config:
  preferred_model: null
eip_config:
  default_isolation_level: "L4"
memory_config:
  state_ttl: 86400
"""


def _write_config(tmp_path: Path, content: str, filename: str = "ceo_agent.yaml") -> Path:
    """向 tmp_path 写入真实 YAML 配置文件。"""
    config_file = tmp_path / filename
    config_file.write_text(content, encoding="utf-8")
    return config_file


async def _load(tmp_path: Path, role: AgentRole = AgentRole.CEO):
    """构造加载器并执行加载（config_dir 注入 tmp_path）。"""
    from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

    loader = YamlAgentConfigLoader(config_dir=tmp_path)
    return await loader.load(role)


# ===================================================================
# 正常加载与字段映射
# ===================================================================


class TestLoadSuccess:
    """合法配置加载与 YAML→值对象完整映射。"""

    async def test_load_valid_config(self, tmp_path: Path) -> None:
        _write_config(tmp_path, VALID_YAML)
        config = await _load(tmp_path)
        assert config.role == AgentRole.CEO
        assert config.name == "CEO Agent"
        assert config.version == "1.0.0"
        assert config.description.startswith("首席执行官")

    async def test_capabilities_list_to_tuple(self, tmp_path: Path) -> None:
        """capabilities.* YAML list → tuple[str, ...] 显式转换。"""
        _write_config(tmp_path, VALID_YAML)
        config = await _load(tmp_path)
        assert config.responsibilities == ("战略方向", "最终决策", "高管协调")
        assert config.domain_knowledge == ("宏观趋势", "竞争格局", "战略意图")
        assert isinstance(config.responsibilities, tuple)

    async def test_preferred_model_null_is_none(self, tmp_path: Path) -> None:
        _write_config(tmp_path, VALID_YAML)
        config = await _load(tmp_path)
        assert config.preferred_model is None

    async def test_state_ttl_mapped(self, tmp_path: Path) -> None:
        _write_config(tmp_path, VALID_YAML.replace("state_ttl: 86400", "state_ttl: 3600"))
        config = await _load(tmp_path)
        assert config.state_ttl == 3600

    async def test_unknown_keys_ignored(self, tmp_path: Path) -> None:
        """未知键策略（定稿）：Schema 外多余键忽略，加载成功且字段不受污染。"""
        polluted = VALID_YAML + "unknown_top_level:\n  whatever: 1\nagent_extra: true\n"
        _write_config(tmp_path, polluted)
        config = await _load(tmp_path)
        assert config.name == "CEO Agent"
        assert config.state_ttl == 86400

    async def test_builtin_repo_config_loadable(self, tmp_path: Path) -> None:
        """仓库内置 configs/agents/ceo_agent.yaml（默认目录锚定）可加载成功。"""
        from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

        loader = YamlAgentConfigLoader()
        config = await loader.load(AgentRole.CEO)
        assert config.role == AgentRole.CEO
        assert config.version == "1.0.0"


# ===================================================================
# 失败路径（全部 EXCEPTION_440）
# ===================================================================


class TestLoadFailures:
    """三类失败路径 + 边界形态，全部抛 AgentConfigError(440)。"""

    async def test_file_missing(self, tmp_path: Path) -> None:
        """文件缺失（目录空，不发任何异常之外的 IO）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"
        assert exc_info.value.message, "消息面向调用方可理解"

    async def test_yaml_syntax_error(self, tmp_path: Path) -> None:
        """YAML 语法错（scanner error → 440，不泄露全文）。"""
        _write_config(tmp_path, "agent: [unclosed\n  bad indent\n}}}")
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_empty_file(self, tmp_path: Path) -> None:
        """空文件（safe_load 返回 None → 440 非 AttributeError）。"""
        _write_config(tmp_path, "")
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_role_mismatch(self, tmp_path: Path) -> None:
        """identity.role 与请求角色不匹配 → 440。"""
        _write_config(tmp_path, VALID_YAML.replace('role: "ceo"', 'role: "sys"'))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path, AgentRole.CEO)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_role_value_invalid(self, tmp_path: Path) -> None:
        """identity.role 非枚举值 → 440（禁止裸 ValueError 逃逸）。"""
        _write_config(tmp_path, VALID_YAML.replace('role: "ceo"', 'role: "战略决策者"'))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path, AgentRole.CEO)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_agent_section_missing(self, tmp_path: Path) -> None:
        """agent 段整段缺失（必填字段缺失）→ 440。"""
        broken = 'identity:\n  role: "ceo"\ncapabilities:\n  responsibilities: ["a"]\n  domain_knowledge: ["b"]\n'
        _write_config(tmp_path, broken)
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_capabilities_section_missing(self, tmp_path: Path) -> None:
        """capabilities 段缺失 → 440。"""
        _write_config(tmp_path, VALID_YAML.split("capabilities:")[0])
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_empty_responsibilities_list(self, tmp_path: Path) -> None:
        """空列表（responsibilities: []）→ 440（防 is None 式漏检——VO falsy 判空是唯一防线）。"""
        _write_config(tmp_path, VALID_YAML.replace('["战略方向", "最终决策", "高管协调"]', "[]"))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_scalar_capabilities_string(self, tmp_path: Path) -> None:
        """capabilities.* 非列表标量（字符串）→ 440（禁止 tuple(str) 逐字符静默展开）。"""
        _write_config(tmp_path, VALID_YAML.replace('["战略方向", "最终决策", "高管协调"]', "战略方向"))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_state_ttl_string(self, tmp_path: Path) -> None:
        """state_ttl 字符串 → 440（禁止裸 TypeError 逃逸）。"""
        _write_config(tmp_path, VALID_YAML.replace("state_ttl: 86400", 'state_ttl: "86400"'))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_state_ttl_float(self, tmp_path: Path) -> None:
        _write_config(tmp_path, VALID_YAML.replace("state_ttl: 86400", "state_ttl: 86400.5"))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_config_path_occupied_by_directory(self, tmp_path: Path) -> None:
        """配置路径被目录占位 → 440（OSError 家族统一包装，禁裸 IsADirectoryError 逃逸）。"""
        (tmp_path / "ceo_agent.yaml").mkdir()
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_non_utf8_encoding_rejected(self, tmp_path: Path) -> None:
        """GBK 编码内容 → 440（UnicodeDecodeError 家族统一包装——中文配置被错误编码保存即触发）。"""
        (tmp_path / "ceo_agent.yaml").write_bytes('agent:\n  name: "首席执行官"\n'.encode("gbk"))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"
        assert exc_info.value.context["reason"] == "配置文件编码非法（需 UTF-8）", "reason 分级锚定（防解析层行为漂移）"

    async def test_preferred_model_non_string_rejected(self, tmp_path: Path) -> None:
        """preferred_model 非字符串标量 → 440（防配置手误被静默吞为 None）。"""
        _write_config(tmp_path, VALID_YAML.replace("preferred_model: null", "preferred_model: 123"))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_isolation_level_non_string_rejected(self, tmp_path: Path) -> None:
        """default_isolation_level 非字符串 → 440（防静默回落 L4 掩盖配置错误）。"""
        _write_config(tmp_path, VALID_YAML.replace('default_isolation_level: "L4"', "default_isolation_level: 5"))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"

    @pytest.mark.parametrize(
        ("section", "broken"),
        [
            ("llm_config", "llm_config: 123\n"),
            ("eip_config", "eip_config: []\n"),
            ("memory_config", 'memory_config: "86400"\n'),
        ],
    )
    async def test_optional_section_non_dict_rejected(self, tmp_path: Path, section: str, broken: str) -> None:
        """可选段非映射结构（标量/列表/字符串）→ 440（防静默回落默认值掩盖配置错误）。"""
        head = VALID_YAML.split("llm_config:")[0].rstrip() + "\n"  # 合法头部 + 单坏段（其余可选段合法缺失）
        _write_config(tmp_path, head + broken)
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"
        assert section in exc_info.value.context.get("reason", ""), "reason 须指明段名"

    async def test_optional_sections_missing_fall_back_to_defaults(self, tmp_path: Path) -> None:
        """三可选段整体缺失 → 加载成功且回落默认值（None/L4/86400——可选段契约正向锚定）。"""
        _write_config(tmp_path, VALID_YAML.split("llm_config:")[0].rstrip() + "\n")
        config = await _load(tmp_path)
        assert config.preferred_model is None
        assert config.default_isolation_level == "L4"
        assert config.state_ttl == 86400

    async def test_error_context_carries_role_and_reason(self, tmp_path: Path) -> None:
        """异常 context 携带 role/config_path/reason（不泄露绝对路径内部细节）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        error = exc_info.value
        assert error.context.get("role") == "ceo"
        assert error.context.get("reason")


# ===================================================================
# Story 5-4: str→IsolationLevel 转换守卫（D6 回填——枚举 SSOT 通道）
# ===================================================================


class TestIsolationLevelConversion:
    """default_isolation_level 字符串→枚举转换（loader 只做转换合法性，不做 MVP 白名单）。

    分层口径（R1-F03/F04）: 非法枚举值字符串 "L9" → 440（部署资产缺陷族）；
    合法枚举 "L1"（越 MVP 白名单）放行 → 实体 initialize 446 拒绝（运行时
    用户错误族）——输入通道决定异常族，禁止 loader 拦 L1「修平」。
    """

    async def test_valid_l4_string_converts_to_enum(self, tmp_path: Path) -> None:
        """合法 "L4" → IsolationLevel.L4_HARD 枚举实例（SSOT 枚举绑定）。"""
        _write_config(tmp_path, VALID_YAML)
        config = await _load(tmp_path)
        assert config.default_isolation_level is IsolationLevel.L4_HARD

    async def test_invalid_l9_raises_440_chinese_reason(self, tmp_path: Path) -> None:
        """非法枚举值 "L9" → 440（reason 中文自然语言——对齐 role 先例风格）。"""
        _write_config(tmp_path, VALID_YAML.replace('default_isolation_level: "L4"', 'default_isolation_level: "L9"'))
        with pytest.raises(AgentConfigError) as exc_info:
            await _load(tmp_path)
        assert exc_info.value.code == "EXCEPTION_440"
        assert "非法隔离等级值" in exc_info.value.context.get("reason", "")

    async def test_missing_section_falls_back_l4_enum(self, tmp_path: Path) -> None:
        """eip_config 段缺失 → 回落 L4 枚举（既有定稿语义保留——L128 语义原样）。"""
        yaml_without_eip = VALID_YAML.replace('eip_config:\n  default_isolation_level: "L4"\n', "")
        _write_config(tmp_path, yaml_without_eip)
        config = await _load(tmp_path)
        assert config.default_isolation_level is IsolationLevel.L4_HARD

    async def test_empty_string_falls_back_l4_enum(self, tmp_path: Path) -> None:
        """空串 → 回落 L4 枚举（既有定稿语义保留——空串等价缺失）。"""
        _write_config(tmp_path, VALID_YAML.replace('default_isolation_level: "L4"', 'default_isolation_level: ""'))
        config = await _load(tmp_path)
        assert config.default_isolation_level is IsolationLevel.L4_HARD

    async def test_null_falls_back_l4_enum(self, tmp_path: Path) -> None:
        """YAML null → 回落 L4 枚举（既有定稿语义保留）。"""
        _write_config(tmp_path, VALID_YAML.replace('default_isolation_level: "L4"', "default_isolation_level: null"))
        config = await _load(tmp_path)
        assert config.default_isolation_level is IsolationLevel.L4_HARD

    async def test_l1_valid_enum_passes_no_mvp_whitelist(self, tmp_path: Path) -> None:
        """合法枚举 "L1" loader 放行（is L1_FUSED——MVP 白名单归实体 initialize 446）。

        AC-2「配置 L1 → 446」路径依赖此分层: loader 拦 L1 将使实体守卫
        不可达（446 验收断言面消失）。
        """
        _write_config(tmp_path, VALID_YAML.replace('default_isolation_level: "L4"', 'default_isolation_level: "L1"'))
        config = await _load(tmp_path)
        assert config.default_isolation_level is IsolationLevel.L1_FUSED
