"""Story 5.5 架构约束验证测试（Agent 三重硬隔离——验证器 A-D + 基建四件套）

覆盖 AC-6.3（架构合规）+ AC-6.4（安全测试基建就绪）:
- 基建验证器节: tests/security 四件套（目录三文件 + pyproject security marker
  [文本断言防漏注册——--strict-markers 收集期守卫] + CI integration job 挂载
  tests/security + Makefile test-security target 两段式覆盖率命令）
- 验证器 A: domain 零外部依赖（isolation_access.py / agent_exceptions.py AST 扫描）
- 验证器 B: 组合根外零实例化（IsolationGuardService——仅扫 src/ 面）
- 验证器 C: 端口方向（守卫服务与两接线点 import 白名单 + 接线静态锚 +
  判定真源防线[isolation_access 生产方白名单]）
- 验证器 D: lifetime 决策落地（SINGLETON 两行式收窄断言）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_agent_triple_isolation.py -v
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"


# ===================================================================
# 基建验证器节: 安全测试基建四件套（AC-6.4——文件存在性 + 配置文本断言）
# ===================================================================


class TestSecurityInfrastructureFourPiece:
    """tests/security 四件套就绪断言（基建不存在时断言真红——TDD 先行钉死预期形态）。

    落位本文件（tests/unit/architecture/）而非 tests/security 自身——断言本文件
    存在自指恒真（Task 4 循环 A 豁免条款注记）。
    """

    def test_security_suite_files_exist(self) -> None:
        """三文件存在性（目录 __init__ + conftest + 探针套件）。"""
        expected = [
            "tests/security/__init__.py",
            "tests/security/conftest.py",
            "tests/security/test_isolation_security.py",
        ]
        missing = [rel for rel in expected if not (REPO_ROOT / rel).exists()]
        assert not missing, f"安全测试基建文件缺失: {missing}"

    def test_pyproject_registers_security_marker(self) -> None:
        """pyproject markers 注册 security（--strict-markers 下未注册即收集期炸）。"""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert '"security:' in pyproject, "pyproject [tool.pytest.ini_options].markers 未注册 security"

    def test_ci_integration_job_mounts_security_suite(self) -> None:
        """CI integration-tests job pytest 命令含 tests/security（探针需真实 Redis——
        挂有 compose 服务栈的 job）。"""
        ci = (REPO_ROOT / ".gitea" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
        assert "tests/security" in ci, "CI integration job 未挂载 tests/security"

    def test_makefile_security_coverage_target(self) -> None:
        """Makefile test-security target（两段式覆盖率口径——D-2 偏离声明落地；
        禁 --cov=src.<module> 单段形态[仓库 coverage 配置陷阱]）。"""
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        assert "test-security:" in makefile, "Makefile 缺 test-security target"
        assert "tests/security" in makefile, "test-security 未跑 tests/security"
        assert "--fail-under=90" in makefile, "安全覆盖率专项未含 fail-under=90 门禁"
