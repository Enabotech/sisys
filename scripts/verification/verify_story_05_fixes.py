#!/usr/bin/env python3
# Gitea 代码审查修复验证脚本 - Story 0.5
# 用途：验证所有 MEDIUM 和 LOW 问题已正确修复
# 使用：python verify_fixes.py
# mypy: disable-error-code="import-untyped"

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 需要安装 PyYAML: pip install pyyaml")
    sys.exit(1)


def check_file_exists(path: str, description: str) -> bool:
    """检查文件是否存在"""
    if Path(path).exists():
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"❌ {description} 文件不存在：{path}")
        return False


def check_yaml_syntax(path: str, description: str) -> bool:
    """检查 YAML 语法"""
    try:
        with open(path, encoding="utf-8") as f:
            list(yaml.safe_load_all(f))
        print(f"✓ {description} YAML 语法正确")
        return True
    except Exception as e:
        print(f"❌ {description} YAML 语法错误：{e}")
        return False


def check_middleware_config() -> bool:
    """验证 M1: Middleware 配置"""
    print("\n=== 验证 M1: Middleware 配置 ===")

    success = True

    # 检查 middleware.yaml 是否存在
    if not check_file_exists("deploy/kubernetes/gitea/middleware.yaml", "Middleware 配置"):
        return False

    # 检查 YAML 语法
    if not check_yaml_syntax("deploy/kubernetes/gitea/middleware.yaml", "Middleware"):
        return False

    # 检查内容
    with open("deploy/kubernetes/gitea/middleware.yaml", encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("stsSeconds: 31536000", "HSTS 配置"),
        ('customFrameOptionsValue: "DENY"', "点击劫持防护"),
        ("contentTypeNosniff: true", "MIME 嗅探防护"),
    ]

    for check_str, desc in checks:
        if check_str in content:
            print(f"  ✓ {desc} 已配置")
        else:
            print(f"  ❌ {desc} 未配置")
            success = False

    # 检查 ingress.yaml 引用 Middleware
    with open("deploy/kubernetes/gitea/ingress.yaml", encoding="utf-8") as f:
        ingress_content = f.read()

    if "traefik.ingress.kubernetes.io/router.middlewares: gitea-secure-headers@gitea" in ingress_content:
        print("  ✓ Ingress 已正确引用 Middleware")
    else:
        print("  ❌ Ingress 未引用 Middleware")
        success = False

    return success


def check_tls_config() -> bool:
    """验证 M2: TLS 证书配置说明"""
    print("\n=== 验证 M2: TLS 证书配置说明 ===")

    with open("deploy/kubernetes/gitea/ingress.yaml", encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("MVP 阶段", "MVP 说明"),
        ("自签名证书", "自签名证书说明"),
        ("生产环境", "生产环境说明"),
        ("cert-manager", "cert-manager 说明"),
        ("Let's Encrypt", "Let's Encrypt 说明"),
    ]

    success = True
    for check_str, desc in checks:
        if check_str in content:
            print(f"  ✓ {desc} 已注明")
        else:
            print(f"  ❌ {desc} 未注明")
            success = False

    return success


def check_secrets_config() -> bool:
    """验证 M3: Secrets 管理"""
    print("\n=== 验证 M3: Secrets 管理 ===")

    success = True

    # 检查 secrets.yaml
    if not check_file_exists("deploy/kubernetes/gitea/secrets.yaml", "Secrets 模板"):
        success = False

    if not check_file_exists("deploy/kubernetes/gitea/secrets-example.yaml", "Secrets 示例"):
        success = False

    # 检查 secrets.yaml 使用环境变量占位符
    with open("deploy/kubernetes/gitea/secrets.yaml", encoding="utf-8") as f:
        secrets_content = f.read()

    if "${GITEA_ADMIN_PASSWORD}" in secrets_content:
        print("  ✓ secrets.yaml 使用环境变量占位符")
    else:
        print("  ❌ secrets.yaml 未使用环境变量占位符")
        success = False

    # 检查 secrets-example.yaml 有警告说明
    with open("deploy/kubernetes/gitea/secrets-example.yaml", encoding="utf-8") as f:
        example_content = f.read()

    checks = [
        ("仅开发环境", "开发环境警告"),
        ("生产环境必须", "生产环境说明"),
        ("pragma: allowlist secret", "允许列表标记"),
    ]

    for check_str, desc in checks:
        if check_str in example_content:
            print(f"  ✓ {desc} 已注明")
        else:
            print(f"  ❌ {desc} 未注明")
            success = False

    return success


def check_file_list() -> bool:
    """验证 M4: 故事文件 File List"""
    print("\n=== 验证 M4: 故事文件 File List ===")

    story_path = "_bmad-output/implementation-artifacts/stories/0-5-gitea-code-hosting.md"

    if not Path(story_path).exists():
        print(f"  ❌ 故事文件不存在：{story_path}")
        return False

    with open(story_path, encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("middleware.yaml", "middleware.yaml 记录"),
        ("secrets-example.yaml", "secrets-example.yaml 记录"),
        ("M1 修复", "M1 修复记录"),
        ("M2 修复", "M2 修复记录"),
        ("M3 修复", "M3 修复记录"),
        ("M4 修复", "M4 修复记录"),
        ("Status: done", "故事状态更新为 done"),
    ]

    success = True
    for check_str, desc in checks:
        if check_str in content:
            print(f"  ✓ {desc}")
        else:
            print(f"  ❌ {desc} 缺失")
            success = False

    return success


def check_gitignore() -> bool:
    """验证 .gitignore 更新"""
    print("\n=== 验证 .gitignore 更新 ===")

    with open(".gitignore", encoding="utf-8") as f:
        content = f.read()

    if "secrets-example.yaml" in content:
        print("  ✓ .gitignore 包含 secrets-example.yaml 例外")
        return True
    else:
        print("  ❌ .gitignore 未包含 secrets-example.yaml 例外")
        return False


def check_sprint_status() -> bool:
    """验证 sprint-status.yaml 更新"""
    print("\n=== 验证 sprint-status.yaml 更新 ===")

    sprint_path = "_bmad-output/implementation-artifacts/sprint-status.yaml"

    if not Path(sprint_path).exists():
        print("  ❌ sprint-status.yaml 不存在")
        return False

    with open(sprint_path, encoding="utf-8") as f:
        content = f.read()

    if "0-5-gitea-code-hosting: done" in content:
        print("  ✓ Story 0.5 状态更新为 done")
        return True
    else:
        print("  ❌ Story 0.5 状态未更新为 done")
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("Story 0.5 代码审查修复验证")
    print("=" * 60)

    results = []

    results.append(("M1: Middleware 配置", check_middleware_config()))
    results.append(("M2: TLS 证书配置说明", check_tls_config()))
    results.append(("M3: Secrets 管理", check_secrets_config()))
    results.append(("M4: 故事文件 File List", check_file_list()))
    results.append((".gitignore 更新", check_gitignore()))
    results.append(("Sprint 状态更新", check_sprint_status()))

    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("✅ 所有验证通过！修复已完成。")
        return 0
    else:
        print("❌ 部分验证失败，请检查上述问题。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
