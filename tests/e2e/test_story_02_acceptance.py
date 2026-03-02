#!/usr/bin/env python3
"""
Story 0.2: CI/CD 流水线验收测试脚本

验证所有验收标准和任务完成情况
"""

import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent.parent


def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(text):
    print(f"\n[STEP] {text}")
    print("-" * 40)


def check_file_exists(path, description):
    """检查文件是否存在"""
    if path.exists():
        print(f"[OK] {description}: {path}")
        return True
    else:
        print(f"[FAIL] {description} 不存在：{path}")
        return False


def check_yaml_syntax(path):
    """检查 YAML 语法（简单验证）"""
    try:
        content = path.read_text(encoding="utf-8")
        # 简单检查 YAML 基本结构
        if "name:" in content and "on:" in content and "jobs:" in content:
            print(f"[OK] YAML 结构正确：{path}")
            return True
        else:
            print(f"[FAIL] YAML 缺少关键字段：{path}")
            return False
    except Exception as e:
        print(f"[FAIL] 读取 YAML 失败 {path}: {e}")
        return False


def test_acceptance_criteria_1():
    """AC 1: 代码提交触发 CI/CD"""
    print_step("验收标准 1: 代码提交触发 CI/CD")

    checks = [
        (ROOT / ".github/workflows/ci.yml", "CI 工作流配置"),
        (ROOT / ".github/workflows/cd.yml", "CD 工作流配置"),
    ]

    passed = all(check_file_exists(path, desc) for path, desc in checks)

    # 检查 CI 配置关键字
    ci_content = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    if "on:" in ci_content and ("push:" in ci_content or "pull_request:" in ci_content):
        print("[OK] CI 触发器配置正确")
    else:
        print("[FAIL] CI 触发器配置缺失")
        passed = False

    return passed


def test_acceptance_criteria_2():
    """AC 2: PR 触发 CI 检查"""
    print_step("验收标准 2: PR 触发代码检查")

    ci_content = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    checks = [
        ("pull_request:" in ci_content, "PR 触发器"),
        ("ruff" in ci_content or "lint" in ci_content, "代码规范检查"),
        ("pytest" in ci_content or "test" in ci_content, "单元测试"),
        ("bandit" in ci_content or "safety" in ci_content or "security" in ci_content, "安全扫描"),
    ]

    passed = True
    for check, name in checks:
        if check:
            print(f"[OK] {name} 已配置")
        else:
            print(f"[FAIL] {name} 未配置")
            passed = False

    return passed


def test_acceptance_criteria_3():
    """AC 3: main 分支触发 CD 部署"""
    print_step("验收标准 3: main 分支触发 CD 部署")

    cd_content = (ROOT / ".github/workflows/cd.yml").read_text(encoding="utf-8")

    checks = [
        ("push:" in cd_content and "main" in cd_content, "main 分支触发器"),
        ("docker" in cd_content.lower() or "image" in cd_content, "Docker 镜像构建"),
        ("ghcr.io" in cd_content or "registry" in cd_content, "镜像仓库推送"),
        ("deploy" in cd_content.lower(), "部署配置"),
        ("health" in cd_content.lower(), "健康检查"),
    ]

    passed = True
    for check, name in checks:
        if check:
            print(f"[OK] {name} 已配置")
        else:
            print(f"[FAIL] {name} 未配置")
            passed = False

    return passed


def test_task_completion():
    """检查所有任务完成情况"""
    print_step("任务完成情况检查")

    # Task 1: GitHub Actions 配置
    print("\nTask 1: GitHub Actions 工作流配置")
    task1 = check_file_exists(ROOT / ".github/workflows/ci.yml", "CI 工作流")
    task1 &= check_file_exists(ROOT / ".github/workflows/cd.yml", "CD 工作流")

    # Task 2: CI 流水线实现
    print("\nTask 2: CI 流水线实现")
    ci_content = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    task2_checks = [
        ("cache" in ci_content.lower(), "缓存配置"),
        ("poetry" in ci_content.lower(), "Poetry 依赖安装"),
        ("coverage" in ci_content.lower(), "覆盖率报告"),
    ]
    task2 = all(check for check, _ in task2_checks)
    for check, name in task2_checks:
        print(f"  [{'OK' if check else 'FAIL'}] {name}")

    # Task 3: CD 流水线实现
    print("\nTask 3: CD 流水线实现")
    cd_content = (ROOT / ".github/workflows/cd.yml").read_text(encoding="utf-8")
    task3_checks = [
        ("docker/build-push-action" in cd_content, "Docker 构建推送"),
        ("deploy" in cd_content.lower(), "部署配置"),
        ("health" in cd_content.lower(), "健康检查"),
    ]
    task3 = all(check for check, _ in task3_checks)
    for check, name in task3_checks:
        print(f"  [{'OK' if check else 'FAIL'}] {name}")

    # Task 4: Docker 配置
    print("\nTask 4: Docker 配置优化")
    task4 = check_file_exists(ROOT / "docker/Dockerfile.prod", "生产 Dockerfile")
    task4 &= check_file_exists(ROOT / "docker/docker-compose.prod.yml", "生产 Compose")
    task4 &= check_file_exists(ROOT / "docker/docker-compose.test.yml", "测试 Compose")

    # Task 5: Secrets 管理
    print("\nTask 5: 环境变量与 Secrets 管理")
    task5 = check_file_exists(ROOT / ".env.example", "环境变量模板")
    # Secrets 配置在 GitHub 上手动完成

    # Task 6: 监控与日志
    print("\nTask 6: 监控与日志")
    task6_checks = [
        ("upload-artifact" in ci_content or "upload-artifact" in cd_content, "日志上传"),
        (
            "notify" in cd_content.lower()
            or "slack" in cd_content.lower()
            or "ding" in cd_content.lower(),
            "通知配置",
        ),
    ]
    task6 = all(check for check, _ in task6_checks)
    for check, name in task6_checks:
        print(f"  [{'OK' if check else 'FAIL'}] {name}")

    return all([task1, task2, task3, task4, task5, task6])


def test_supporting_files():
    """检查支持文件"""
    print_step("支持文件检查")

    files = [
        (ROOT / "scripts/testing/run_tests.sh", "测试运行脚本"),
        (ROOT / "scripts/testing/run_coverage.sh", "覆盖率报告脚本"),
        (ROOT / "scripts/testing/clean_test_data.py", "测试数据清理"),
        (ROOT / ".pre-commit-config.yaml", "Pre-commit 配置"),
        (ROOT / "docs/developer/testing_guide.md", "测试指南文档"),
        (ROOT / "docs/developer/cicd_quick_reference.md", "CI/CD 参考文档"),
    ]

    return all(check_file_exists(path, desc) for path, desc in files)


def main():
    """运行所有验收测试"""
    print_header("Story 0.2: CI/CD 流水线验收测试")

    tests = [
        ("验收标准 1: CI/CD 触发", test_acceptance_criteria_1),
        ("验收标准 2: PR 检查", test_acceptance_criteria_2),
        ("验收标准 3: CD 部署", test_acceptance_criteria_3),
        ("任务完成情况", test_task_completion),
        ("支持文件", test_supporting_files),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[FAIL] 测试 {name} 异常：{e}")
            results.append((name, False))

    # 总结
    print_header("验收测试总结")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name}: {status}")

    print("\n" + "=" * 60)
    print(f"结果：{passed_count}/{total_count} 通过")
    print("=" * 60)

    if passed_count == total_count:
        print("\n[SUCCESS] 所有验收标准通过！")
        print("\nStory 0.2 状态：READY FOR REVIEW")
        print("\n下一步操作：")
        print("1. 在 GitHub 上配置 Secrets")
        print("2. 推送代码到仓库触发 CI/CD")
        print("3. 验证流水线执行结果")
        return 0
    else:
        print("\n[FAIL] 部分验收标准未通过，请检查失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())
