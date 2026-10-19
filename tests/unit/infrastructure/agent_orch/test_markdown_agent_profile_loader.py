"""MarkdownAgentProfileLoader 单元测试（Story 5-2 — Agent 身份档案加载）

tmp_path 真实文件 IO 零 mock 覆盖：
- 正常六档案加载（字段一致 + agent_id/role 透传——VO 归属锚点）
- 六类失败：目录缺失/单文件缺失/内容空白（三形态）/大小超限（字节口径）/
  编码非法（GBK 字节）/读取阶段不可读（同名目录形态——R1-F2 补，兑现
  Story L324「读取失败（OSError）」承诺）；一项边界：未知文件忽略（前向兼容）
- profile_path 相对形态守护（context 不含 tmp_path 绝对前缀——R1-F4 脱敏契约断言）
- 判空主检在加载器断言（context.profile_path 携带文件名——DC-5 观测锚点，
  防实现滑入 VO 兜底路径致 context 失文件名）
- 内置资产冒烟：默认 profile_root 加载 configs/agents/profiles/ceo/ 六档案成功

Run with:
    poetry run pytest tests/unit/infrastructure/agent_orch/test_markdown_agent_profile_loader.py -v
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentProfileError

#: 六档案固定名（与生产资产 configs/agents/profiles/ceo/ 一致）
FILE_NAMES = ("IDENTITY.md", "CODE.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md")


def _make_loader(profile_root: Path):
    """构造加载器（延迟 import——Story 5-2 新模块纪律）。"""
    from src.infrastructure.agent_orch.markdown_agent_profile_loader import MarkdownAgentProfileLoader

    return MarkdownAgentProfileLoader(profile_root=profile_root)


def _write_six_profiles(profile_dir: Path) -> None:
    """写入合法六档案（真实文件 IO）。"""
    profile_dir.mkdir(parents=True, exist_ok=True)
    contents = {
        "IDENTITY.md": "# IDENTITY\nCEO 首席执行官，负责战略方向、最终决策与高管协调。\n",
        "CODE.md": "# CODE\n行为准则：证据优先、角色隔离纪律、结论先行。\n",
        "SOUL.md": "# SOUL\n高管决策视角：宏观趋势、竞争格局、战略意图。\n",
        "USER.md": "# USER\n偏好简明扼要的结论先行表达。\n",
        "MEMORY.md": "# MEMORY\n暂无系统级记忆，此为加载占位。\n",
        "HEARTBEAT.md": "# HEARTBEAT\n心跳配置：默认每日频率占位。\n",
    }
    for name, content in contents.items():
        (profile_dir / name).write_text(content, encoding="utf-8")


async def _load(loader, role: AgentRole = AgentRole.CEO, agent_id: uuid.UUID | None = None):
    """执行加载（统一 agent_id 生成）。"""
    return await loader.load(role=role, agent_id=agent_id or uuid.uuid4())


# ===================================================================
# 正常加载
# ===================================================================


class TestSuccessfulLoad:
    """正常六档案加载（tmp_path 构造注入 profile_root）。"""

    async def test_load_returns_agent_profile_with_all_fields(self, tmp_path: Path) -> None:
        """六档案内容逐字段进入 AgentProfile。"""
        _write_six_profiles(tmp_path / "ceo")
        loader = _make_loader(tmp_path)
        profile = await _load(loader)
        assert "CEO" in profile.identity
        assert "行为准则" in profile.code_of_conduct
        assert "高管" in profile.soul
        assert "结论先行" in profile.user_preferences
        assert "占位" in profile.memory
        assert "心跳" in profile.heartbeat

    async def test_agent_id_and_role_passthrough(self, tmp_path: Path) -> None:
        """agent_id/role 透传进 VO（档案归属锚点断言）。"""
        _write_six_profiles(tmp_path / "ceo")
        loader = _make_loader(tmp_path)
        agent_id = uuid.uuid4()
        profile = await _load(loader, agent_id=agent_id)
        assert profile.agent_id == agent_id
        assert profile.role == AgentRole.CEO

    async def test_unknown_files_ignored(self, tmp_path: Path) -> None:
        """目录含 Schema 外未知文件（README.md）→ 六档案加载成功（前向兼容策略）。"""
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "README.md").write_text("# 非档案文件\n", encoding="utf-8")
        (tmp_path / "ceo" / "notes.txt").write_text("文本笔记", encoding="utf-8")
        loader = _make_loader(tmp_path)
        profile = await _load(loader)
        assert "CEO" in profile.identity, "未知文件不得污染六档案字段"


# ===================================================================
# 失败路径一：目录缺失
# ===================================================================


class TestDirectoryMissing:
    """profile_root 指向不存在路径 → 442。"""

    async def test_missing_directory_raises_442(self, tmp_path: Path) -> None:
        loader = _make_loader(tmp_path / "nonexistent")
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        assert "目录" in exc_info.value.context.get("reason", ""), "reason 应含目录缺失语义"
        # profile_path 相对形态守护（R1-F4——_display 突变为 str(path) 时此处必红）
        assert str(tmp_path) not in exc_info.value.context.get("profile_path", ""), (
            "context.profile_path 不得泄露绝对路径（脱敏契约）"
        )

    async def test_missing_role_subdirectory_raises_442(self, tmp_path: Path) -> None:
        """profile_root 存在但角色子目录缺失 → 442。"""
        tmp_path.mkdir(exist_ok=True)
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        assert "目录" in exc_info.value.context.get("reason", ""), "与孪生用例同 raise 位应同 reason 语义"


# ===================================================================
# 失败路径二：单文件缺失
# ===================================================================


class TestFileMissing:
    """单档案文件缺失 → 442 且 context 含文件名（判空主检在加载器）。"""

    async def test_missing_identity_file_raises_442_with_filename(self, tmp_path: Path) -> None:
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "IDENTITY.md").unlink()
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        assert "IDENTITY.md" in exc_info.value.context.get("profile_path", "")


# ===================================================================
# 失败路径二点五：读取阶段不可读（stat 成功但 read_text 抛 OSError）
# ===================================================================


class TestFileUnreadable:
    """同名目录构造：stat().st_size 有值（目录 4096）过大小检查 → read_text 抛
    IsADirectoryError（OSError 子族）→ 442「不可读」（读取阶段分支 L133-134）。

    构造形态选同名目录而非 chmod 0o000：权限形态在 root 环境失效需 skipif，
    目录形态全环境稳定（R1-F2——补齐 Story L324「读取失败（OSError）由 Task 2
    单测承接」承诺；此前仅覆盖 stat 阶段的「缺失」子集）。
    """

    async def test_directory_named_as_profile_file_raises_442(self, tmp_path: Path) -> None:
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "IDENTITY.md").unlink()
        (tmp_path / "ceo" / "IDENTITY.md").mkdir()  # 同名目录：stat 成功 + read 失败
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        # 精确匹配区分 stat 分支的同尾词「缺失或不可读」（评审员①微调）
        assert exc_info.value.context.get("reason", "") == "档案文件不可读", (
            "读取阶段 OSError 的 reason 应为不可读（区别于 stat 阶段的缺失或不可读）"
        )
        assert "IDENTITY.md" in exc_info.value.context.get("profile_path", "")
        # profile_path 相对形态守护（R1-F4——tmp_path 不入 context）
        assert str(tmp_path) not in exc_info.value.context.get("profile_path", ""), (
            "context.profile_path 不得泄露绝对路径（脱敏契约）"
        )


# ===================================================================
# 失败路径三：内容空白（三形态——判空主检在加载器）
# ===================================================================


class TestContentBlank:
    """档案内容纯空白（空串/纯空白/纯换行）→ 442 且 profile_path 含对应文件名。"""

    @pytest.mark.parametrize("blank_form", ["", "   \t  ", "\n\n\n"])
    async def test_blank_soul_raises_442_with_filename(self, tmp_path: Path, blank_form: str) -> None:
        """SOUL.md 三形态空白 → 442 且 context.profile_path 含 SOUL.md（DC-5 观测锚点）。"""
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "SOUL.md").write_text(blank_form, encoding="utf-8")
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        assert "SOUL.md" in exc_info.value.context.get("profile_path", ""), (
            "判空主检必须在加载器（context 携带文件名）——滑入 VO 兜底会失文件名"
        )
        assert "空白" in exc_info.value.context.get("reason", ""), "reason 应含空白语义（同码多因区分）"


# ===================================================================
# 失败路径四：大小超限（字节口径）
# ===================================================================


class TestSizeExceeded:
    """单档案超 64KB（>65536 字节）→ 442。"""

    async def test_oversized_file_raises_442(self, tmp_path: Path) -> None:
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "HEARTBEAT.md").write_bytes(b"x" * 65537)
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        assert "HEARTBEAT.md" in exc_info.value.context.get("profile_path", "")
        assert "64KB" in exc_info.value.context.get("reason", "") or "上限" in exc_info.value.context.get("reason", "")

    async def test_exact_65536_bytes_allowed(self, tmp_path: Path) -> None:
        """恰好 65536 字节不越界（≤ 上限含边界——AC-2.1「≤64KB」）。"""
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "HEARTBEAT.md").write_bytes(b"x" * 65536)
        loader = _make_loader(tmp_path)
        profile = await _load(loader)
        assert len(profile.heartbeat.encode("utf-8")) == 65536


# ===================================================================
# 失败路径五：编码非法
# ===================================================================


class TestEncodingInvalid:
    """非 UTF-8 编码文件 → 442（encoding 显式 utf-8 的 UnicodeDecodeError 包装）。"""

    async def test_gbk_encoded_file_raises_442(self, tmp_path: Path) -> None:
        """GBK 字节写文件（非 UTF-8 解码失败）→ 442 reason 含编码语义。"""
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "USER.md").write_bytes("中文内容".encode("gbk"))
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"
        assert "编码" in exc_info.value.context.get("reason", "")
        assert "USER.md" in exc_info.value.context.get("profile_path", "")

    async def test_undecodable_bytes_raises_442(self, tmp_path: Path) -> None:
        """任意不可解码字节 → 442。"""
        _write_six_profiles(tmp_path / "ceo")
        (tmp_path / "ceo" / "MEMORY.md").write_bytes(b"\xff\xfe\xfa\x00\x01")
        loader = _make_loader(tmp_path)
        with pytest.raises(AgentProfileError) as exc_info:
            await _load(loader)
        assert exc_info.value.code == "EXCEPTION_442"


# ===================================================================
# 内置资产冒烟（默认 profile_root）
# ===================================================================


class TestBuiltinAssetsSmoke:
    """默认 profile_root（仓库根四级上溯锚定）加载内置 CEO 档案。"""

    async def test_load_builtin_ceo_profiles(self) -> None:
        from src.infrastructure.agent_orch.markdown_agent_profile_loader import MarkdownAgentProfileLoader

        loader = MarkdownAgentProfileLoader()
        agent_id = uuid.uuid4()
        profile = await loader.load(role=AgentRole.CEO, agent_id=agent_id)
        assert profile.agent_id == agent_id
        assert profile.role == AgentRole.CEO
        assert "CEO" in profile.identity, "内置 IDENTITY 应含 CEO 语义锚点"
        for field_name in ("identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"):
            content = getattr(profile, field_name)
            assert isinstance(content, str) and content.strip(), f"内置档案 {field_name} 应非空"
