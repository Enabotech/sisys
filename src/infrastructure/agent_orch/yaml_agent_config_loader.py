"""基础设施层 Agent 配置 YAML 加载器模块（Story 5-1 — CEO Agent 实例化 MVP）

实现应用层 AgentConfigLoader 端口：从 configs/agents/{role}_agent.yaml
加载 CEO Agent 基础配置并构造领域值对象 AgentConfig。

设计要点：
- YAML 解析严格限定本模块（domain 层零 yaml 依赖——六边形硬约束）
- asyncio.to_thread 包装同步 yaml.safe_load（不引入 aiofiles 新依赖）
- 配置目录仓库根锚定（Path(__file__) 四级上溯，对齐 event_bus_config_loader
  先例），CLI 任意 cwd 可用；构造注入可覆盖（测试传 tmp_path）
- 未知键策略（定稿）：忽略 Schema 外未知键（前向兼容——DC-3 回填期新旧
  配置共存）
- 全部失败路径统一抛 AgentConfigError(EXCEPTION_440)，消息面向调用方可
  理解（不泄露 YAML 全文/绝对路径/堆栈）
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, NoReturn

import yaml

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.domain.entities.agent import AgentRole
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import AgentConfigError
from src.domain.value_objects.agent_config import AgentConfig

# 仓库根锚定的默认配置目录（src/infrastructure/agent_orch/ 上溯 4 级 → 仓库根/configs/agents）
DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "configs" / "agents"


class YamlAgentConfigLoader(AgentConfigLoader):
    """Agent 基础配置 YAML 加载器（AgentConfigLoader 端口的 infrastructure 实现）

    配置文件命名：{role.value}_agent.yaml（如 ceo_agent.yaml）。
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """初始化加载器

        Args:
            config_dir: 配置目录（默认仓库根 configs/agents——锚定不依赖 cwd；
                测试可注入 tmp_path）
        """
        self._config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR

    async def load(self, role: AgentRole) -> AgentConfig:
        """加载指定角色的基础配置并构造值对象

        Args:
            role: Agent 角色

        Returns:
            AgentConfig 领域值对象

        Raises:
            AgentConfigError: 配置文件缺失 / YAML 解析失败 / 空文件 / role
                不匹配 / 必填字段无效 / capabilities 非列表 / state_ttl 非整数
                （均 EXCEPTION_440）
        """
        config_path = self._config_dir / f"{role.value}_agent.yaml"
        path_display = f"configs/agents/{config_path.name}"  # 相对路径形态，不泄露绝对路径

        def _fail(reason: str, message: str | None = None) -> NoReturn:
            raise AgentConfigError(role=role.value, config_path=path_display, reason=reason, message=message or reason)

        if not config_path.exists():
            _fail("配置文件不存在", f"Agent 配置文件不存在: {path_display}")

        data = await asyncio.to_thread(self._read_yaml, config_path, role.value, path_display)
        if not isinstance(data, dict):
            # 空文件（safe_load 返回 None）或顶层非映射结构
            _fail("配置文件为空或顶层结构非法", f"Agent 配置文件为空或顶层结构非法: {path_display}")

        # identity.role：字符串 → 枚举（非法值与不匹配统一 440，禁止裸 ValueError 逃逸）
        identity = self._section(data, "identity", role.value, path_display)
        role_str = identity.get("role")
        if not isinstance(role_str, str) or not role_str.strip():
            _fail("identity.role 缺失或非字符串")
        try:
            configured_role = AgentRole(role_str.strip().lower())
        except ValueError:
            _fail(f"identity.role 非法枚举值: {role_str}")
        if configured_role is not role:
            _fail(f"配置角色 {configured_role.value} 与请求角色 {role.value} 不匹配")

        # agent 段：name/version/description 必填非空字符串
        agent_section = self._section(data, "agent", role.value, path_display)

        def _required_str(field: str) -> str:
            value = agent_section.get(field)
            if not isinstance(value, str) or not value.strip():
                _fail(f"agent.{field} 缺失或为非空字符串要求不满足")
            return value

        name = _required_str("name")
        description = _required_str("description")
        version = _required_str("version")

        # capabilities.*：isinstance(list) 守卫再转 tuple（禁止 tuple(str) 逐字符静默展开）
        capabilities = self._section(data, "capabilities", role.value, path_display)
        responsibilities = self._string_list(capabilities, "responsibilities", role.value, path_display)
        domain_knowledge = self._string_list(capabilities, "domain_knowledge", role.value, path_display)

        # 可选段语义（定稿）：None（YAML null）/ 缺失 / 空 dict → 回落默认值（合法）；
        # 非 None 非 dict（标量/列表/字符串）→ 440（防配置手误被静默吞为默认值——
        # 守卫作用于 or {} 归一化之前的 raw 值，防 [] 被 falsy 归一绕过）
        llm_raw = data.get("llm_config")
        if llm_raw is not None and not isinstance(llm_raw, dict):
            _fail("llm_config 段必须为映射结构")
        # llm_config.preferred_model：null/缺失 → None（空串由 VO 归一化）；非字符串标量显式 440
        llm_config = llm_raw or {}
        preferred_model_raw = llm_config.get("preferred_model") if isinstance(llm_config, dict) else None
        if preferred_model_raw is not None and not isinstance(preferred_model_raw, str):
            _fail("llm_config.preferred_model 必须为字符串或 null")
        preferred_model: str | None = preferred_model_raw if isinstance(preferred_model_raw, str) else None

        eip_raw = data.get("eip_config")
        if eip_raw is not None and not isinstance(eip_raw, dict):
            _fail("eip_config 段必须为映射结构")
        # eip_config.default_isolation_level：缺失/空串/null 回落 L4（Story 5-4 枚举化——
        # 语义原样保留）；非字符串显式 440；字符串→IsolationLevel 转换守卫（禁裸
        # IsolationLevel(value) 的 ValueError 逃逸——对齐 identity.role 先例）；
        # 不做 MVP 白名单（"L1" 合法枚举放行 → 实体 initialize 446 拒绝——输入通道分层）
        eip_config = eip_raw or {}
        isolation_raw = eip_config.get("default_isolation_level") if isinstance(eip_config, dict) else None
        if isolation_raw is not None and not isinstance(isolation_raw, str):
            _fail("eip_config.default_isolation_level 必须为字符串")
        isolation_str = isolation_raw if isinstance(isolation_raw, str) and isolation_raw else "L4"
        try:
            default_isolation_level = IsolationLevel(isolation_str)
        except ValueError:
            _fail(f"eip_config.default_isolation_level 非法隔离等级值: {isolation_str}")

        # eip_config.allowed_tools：缺失 → 空元组（fail-closed 安全默认——L4 下全拒）；
        # 非 list 显式 440；元素逐个 str + 非空白守卫（白名单条目必须是有效工具名——
        # 中文名含半角空格/$ 等特殊字符逐字节保真，禁归一改写）；
        # 去重保序是 loader 新引入行为（dict.fromkeys 模式——配置容错，Story 5.5）
        allowed_raw = eip_config.get("allowed_tools") if isinstance(eip_config, dict) else None
        allowed_tools: tuple[str, ...] = ()
        if allowed_raw is not None:
            if not isinstance(allowed_raw, list):
                _fail("eip_config.allowed_tools 必须为字符串列表")
            for item in allowed_raw:
                if not isinstance(item, str) or not item.strip():
                    _fail(f"eip_config.allowed_tools 元素必须为非空白字符串（实际 {item!r}）")
            allowed_tools = tuple(dict.fromkeys(allowed_raw))

        memory_raw = data.get("memory_config")
        if memory_raw is not None and not isinstance(memory_raw, dict):
            _fail("memory_config 段必须为映射结构")
        # memory_config.state_ttl：缺失默认 86400；非整数（字符串/浮点/布尔）显式拦截
        memory_config = memory_raw or {}
        state_ttl_raw = memory_config.get("state_ttl") if isinstance(memory_config, dict) else None
        if state_ttl_raw is None:
            state_ttl: int = 86400
        elif isinstance(state_ttl_raw, bool) or not isinstance(state_ttl_raw, int):
            _fail("memory_config.state_ttl 必须为整数")
        else:
            state_ttl = state_ttl_raw

        # 构造值对象（空列表/越界等剩余校验由 VO __post_init__ 兜底，同抛 440）
        return AgentConfig(
            role=role,
            name=name,
            description=description,
            version=version,
            responsibilities=tuple(responsibilities),
            domain_knowledge=tuple(domain_knowledge),
            preferred_model=preferred_model,
            state_ttl=state_ttl,
            default_isolation_level=default_isolation_level,
            allowed_tools=allowed_tools,
        )

    @staticmethod
    def _read_yaml(path: Path, role: str, path_display: str) -> Any:
        """同步读取并解析 YAML（经 asyncio.to_thread 调度，避免阻塞事件循环）。

        全部失败路径统一抛 AgentConfigError(440)——open/read/parse 三阶段异常
        逐类包装，禁裸内置异常（OSError/UnicodeDecodeError/ValueError 家族）逃逸：
        - yaml.YAMLError：语法/结构解析失败
        - UnicodeDecodeError：内容非 UTF-8（ValueError 子类——中文配置被错误
          编码保存即触发）
        - OSError：文件不可读（目录占位/无权限/TOCTOU 删除）

        三类异常互无继承交集（分支顺序无关）。
        """
        try:
            with open(path, encoding="utf-8") as stream:
                return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise AgentConfigError(
                role=role,
                config_path=path_display,
                reason="YAML 解析失败",
                message=f"Agent 配置 YAML 解析失败: {path.name}",
                cause=exc,
            ) from exc
        except UnicodeDecodeError as exc:
            raise AgentConfigError(
                role=role,
                config_path=path_display,
                reason="配置文件编码非法（需 UTF-8）",
                message=f"Agent 配置文件编码非法（需 UTF-8）: {path.name}",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise AgentConfigError(
                role=role,
                config_path=path_display,
                reason="配置文件不可读",
                message=f"Agent 配置文件不可读: {path.name}",
                cause=exc,
            ) from exc

    @staticmethod
    def _section(data: dict[str, Any], section: str, role: str, path_display: str) -> dict[str, Any]:
        """提取顶层子段（缺失/非映射 → 440；未知键不在此校验）"""
        value = data.get(section)
        if not isinstance(value, dict):
            raise AgentConfigError(
                role=role,
                config_path=path_display,
                reason=f"{section} 段缺失或结构非法",
                message=f"Agent 配置 {section} 段缺失或结构非法",
            )
        return value

    @staticmethod
    def _string_list(section: dict[str, Any], key: str, role: str, path_display: str) -> list[str]:
        """提取字符串列表字段（isinstance(list) 守卫 + 元素类型校验）"""
        value = section.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise AgentConfigError(
                role=role,
                config_path=path_display,
                reason=f"capabilities.{key} 必须为字符串列表",
                message=f"Agent 配置 capabilities.{key} 必须为字符串列表",
            )
        return value


__all__ = ["YamlAgentConfigLoader", "DEFAULT_CONFIG_DIR"]
