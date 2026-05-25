"""分层覆盖率门禁检查脚本

用途：
    按模块分层检查代码覆盖率，执行差异化门禁：
    - domain: ≥90%（核心业务逻辑，零容忍未测试路径）
    - application: ≥85%（用例编排，高价值业务流）
    - overall: ≥80%（系统级质量基线）

使用：
    poetry run python scripts/check_coverage_gates.py

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import subprocess
import sys


def check_coverage(path: str, threshold: int) -> tuple[bool, float]:
    """检查指定路径的覆盖率是否达到阈值

    Args:
        path: 要检查的代码路径（如 "src/domain"）
        threshold: 覆盖率阈值（如 90）

    Returns:
        tuple[bool, float]: (是否通过, 实际覆盖率)
    """
    result = subprocess.run(
        ["coverage", "report", "--include", f"{path}/*", "--fail-under", str(threshold)],
        capture_output=True,
        text=True,
    )

    # 从输出中提取实际覆盖率
    coverage_value = 0.0
    for line in result.stdout.splitlines():
        if "TOTAL" in line:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    coverage_value = float(parts[-1].replace("%", ""))
                except ValueError:
                    pass

    return result.returncode == 0, coverage_value


def main():
    """执行分层覆盖率检查"""
    print("=" * 60)
    print("分层覆盖率门禁检查")
    print("=" * 60)

    checks = [
        ("src/domain", 90, "核心业务逻辑"),
        ("src/application", 85, "用例编排"),
        ("src", 80, "系统整体"),
    ]

    results = []
    all_pass = True

    for path, threshold, description in checks:
        passed, coverage = check_coverage(path, threshold)
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append((path, threshold, coverage, description, status))
        if not passed:
            all_pass = False

        print(f"{description} ({path}):")
        print(f"  要求: ≥{threshold}%  实际: {coverage:.1f}%  {status}")

    print("=" * 60)

    if all_pass:
        print("✅ 所有覆盖率门禁通过")
        sys.exit(0)
    else:
        print("❌ 覆盖率门禁未通过，请补充测试")
        sys.exit(1)


if __name__ == "__main__":
    main()
