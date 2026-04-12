"""Code quality gate tests.

These tests verify that CI/CD quality tools are properly configured.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class TestPyprojectConfig:
    """Test that pyproject.toml has quality tool configuration."""

    def test_pyproject_exists(self):
        """pyproject.toml must exist."""
        assert (ROOT / "pyproject.toml").exists()

    def test_pyproject_has_ruff_config(self):
        """pyproject.toml has [tool.ruff] section."""
        content = (ROOT / "pyproject.toml").read_text()
        assert "[tool.ruff" in content


class TestPreCommitConfig:
    """Test that pre-commit hooks are configured."""

    def test_pre_commit_config_exists(self):
        """.pre-commit-config.yaml must exist."""
        assert (ROOT / ".pre-commit-config.yaml").exists()


class TestRuffCheck:
    """Test Ruff code quality check."""

    def test_ruff_check_passes(self):
        """Ruff check passes on src/ directory."""
        result = subprocess.run(
            ["ruff", "check", "src/"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        # Allow exit code 0 (pass) or 1 with no actual errors
        # (ruff returns 1 when files need formatting but no rule violations)
        assert result.returncode in (0,), f"Ruff check failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"


class TestImportLint:
    """Test import-linter dependency checks."""

    def test_importlinter_config_exists(self):
        """.importlinter config file must exist."""
        assert (ROOT / ".importlinter").exists()
