"""基础设施层 Markdown 档案加载器（Story 5-2 — Agent 身份档案加载）

MarkdownAgentProfileLoader——AgentProfileLoader 端口的文件系统实现：
按角色寻址 profile_root/{role.value}/ 固定名六档案（IDENTITY/CODE/SOUL/USER/
MEMORY/HEARTBEAT.md），逐文件读取并校验（判空主检位——context.profile_path
携带文件名即 DC-5 观测锚点），六字段齐后一次构造 AgentProfile VO（VO 校验兜底）。

结构模板：yaml_agent_config_loader.py（5-1）——目录锚定四级上溯 /
asyncio.to_thread 包装同步 IO（不引入 aiofiles）/ 三阶段异常包装 /
未知文件忽略（前向兼容——V1 新增档案文件期新旧共存）。

校验规则（DC-5 定稿）：
- 每档案 strip 后非空（空串/纯空白/纯换行 → 442）
- 单文件 ≤ PROFILE_FILE_MAX_BYTES（65536 字节口径——stat().st_size，
  与常量名 MAX_BYTES 对齐；len(content) 字符口径中文下差至 3 倍不用）
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Final

from src.application.ports.agent_profile_loader import AgentProfileLoader
from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentProfileError
from src.domain.value_objects.agent_profile import AgentProfile

#: 档案根目录默认锚定：仓库根（四级上溯：infrastructure/agent_orch/本文件 → src → 仓库根）
DEFAULT_PROFILE_ROOT = Path(__file__).parent.parent.parent.parent / "configs" / "agents" / "profiles"

#: 单档案大小上限（字节口径——资产随代码分发无恶意大文件面，64KB 对正常 <5KB 资产约 13 倍余量）
PROFILE_FILE_MAX_BYTES: Final[int] = 65536

#: 六档案固定名 → AgentProfile 字段映射（or.md 四.1.[1] 枚举序）
_FILE_TO_FIELD: Final[dict[str, str]] = {
    "IDENTITY.md": "identity",
    "CODE.md": "code_of_conduct",
    "SOUL.md": "soul",
    "USER.md": "user_preferences",
    "MEMORY.md": "memory",
    "HEARTBEAT.md": "heartbeat",
}


class MarkdownAgentProfileLoader(AgentProfileLoader):
    """Markdown 档案加载器（文件系统实现，无连接状态——每次调用即时读文件，MVP 无缓存层）。

    Attributes:
        _profile_root: 档案根目录（默认仓库根锚定不依赖 cwd；测试传 tmp_path 覆盖）
    """

    def __init__(self, profile_root: Path | None = None) -> None:
        """初始化加载器。

        Args:
            profile_root: 档案根目录（None 时用 DEFAULT_PROFILE_ROOT 仓库根锚定）
        """
        self._profile_root = Path(profile_root) if profile_root is not None else DEFAULT_PROFILE_ROOT

    async def load(self, role: AgentRole, agent_id: uuid.UUID) -> AgentProfile:
        """加载角色六档案并组装 AgentProfile。

        寻址契约：profile_root / role.value / 固定名（角色子目录层级）；
        目录内 Schema 外未知文件忽略（前向兼容）。

        Args:
            role: Agent 角色（决定寻址子目录）
            agent_id: 档案归属锚点（透传进 VO）

        Returns:
            AgentProfile: 六档案值对象

        Raises:
            AgentProfileError: EXCEPTION_442——目录缺失/文件缺失/不可读/编码非法/
                内容空白/超大小上限（VO 构造兜底路径的校验失败同样 442 透传）
        """
        profile_dir = self._profile_root / role.value
        if not profile_dir.is_dir():
            raise AgentProfileError(
                role=role.value,
                profile_path=self._display(profile_dir),
                reason="档案目录缺失",
            )

        contents: dict[str, str] = {}
        for file_name in _FILE_TO_FIELD:
            contents[file_name] = await self._read_profile_file(role, profile_dir / file_name)

        return AgentProfile(
            agent_id=agent_id,
            role=role,
            identity=contents["IDENTITY.md"],
            code_of_conduct=contents["CODE.md"],
            soul=contents["SOUL.md"],
            user_preferences=contents["USER.md"],
            memory=contents["MEMORY.md"],
            heartbeat=contents["HEARTBEAT.md"],
        )

    async def _read_profile_file(self, role: AgentRole, path: Path) -> str:
        """读取并校验单档案文件（判空主检位——context 携带文件名）。

        Args:
            role: Agent 角色（context 定位用）
            path: 档案文件绝对路径

        Returns:
            str: 文件文本内容

        Raises:
            AgentProfileError: 文件缺失/不可读/编码非法/超限/内容空白（统一 442）
        """
        path_display = self._display(path)

        def _fail(reason: str, cause: Exception | None = None) -> AgentProfileError:
            return AgentProfileError(role=role.value, profile_path=path_display, reason=reason, cause=cause)

        # 大小上限判定（字节口径：读前 stat，避免超限文件全量读入内存）
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise _fail("档案文件缺失或不可读", cause=exc) from exc
        if size > PROFILE_FILE_MAX_BYTES:
            raise _fail(f"档案文件超过 64KB 上限（{size} 字节 > {PROFILE_FILE_MAX_BYTES}）")

        # 读取（显式 UTF-8——裸 read_text 依赖 locale，非 UTF-8 locale 下中文资产会误判 442）
        try:
            content = await asyncio.to_thread(Path.read_text, path, encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise _fail("档案文件编码非法（需 UTF-8）", cause=exc) from exc
        except OSError as exc:
            raise _fail("档案文件不可读", cause=exc) from exc

        # 判空主检（strip 后非空——空串/纯空白/纯换行三形态；VO 兜底路径不携带文件名）
        if not content.strip():
            raise _fail("档案内容纯空白")

        return content

    @staticmethod
    def _display(path: Path) -> str:
        """构造相对路径形态的展示路径（不泄露绝对路径）。

        Args:
            path: 档案绝对路径

        Returns:
            str: configs/agents/profiles/{role}/{file} 相对形态
        """
        parts = path.parts
        marker = "profiles"
        if marker in parts:
            index = len(parts) - 1 - parts[::-1].index(marker)
            return "/".join(parts[index:])
        return path.name
