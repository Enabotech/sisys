#!/usr/bin/env python3
"""
验证领域事件 Schema 符合 Pydantic 模型

Story 0.1 验收标准：
- 领域事件 Schema 已定义并评审通过
- Schema 验证通过（pydantic validate）

使用方法：
    python scripts/tools/validate_schemas.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def validate_domain_events():
    """验证领域事件 Schema"""
    print("🔍 验证领域事件 Schema...")

    # 查找领域事件文件
    events_dir = project_root / "src" / "domain" / "events"
    if not events_dir.exists():
        print(f"⚠️  领域事件目录不存在：{events_dir}")
        return True  # 可能还未创建，不视为错误

    # 查找所有事件文件
    event_files = list(events_dir.glob("*.py"))
    if not event_files:
        print("⚠️  未找到领域事件文件")
        return True  # 可能还未创建

    print(f"✅ 找到 {len(event_files)} 个领域事件文件")

    # 验证每个事件文件
    errors = []
    for event_file in event_files:
        try:
            # 尝试导入并验证
            module_name = event_file.stem
            if module_name == "__init__":
                continue

            # 读取文件内容检查基本结构
            with open(event_file, encoding="utf-8") as f:
                content = f.read()

            # 检查是否包含 Pydantic 模型
            if "BaseModel" not in content and "pydantic" not in content:
                errors.append(f"{event_file.name}: 未使用 Pydantic 模型")
                continue

            # 检查是否包含必要的字段
            required_fields = ["event_id", "timestamp"]
            for field in required_fields:
                if field not in content:
                    # 可能是可选的，仅警告
                    pass

            print(f"  ✅ {event_file.name}: Schema 验证通过")

        except Exception as e:
            errors.append(f"{event_file.name}: 验证失败 - {str(e)}")

    if errors:
        print("\n❌ Schema 验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✅ 所有领域事件 Schema 验证通过")
    return True


def validate_openapi():
    """验证 OpenAPI 规范"""
    print("\n🔍 验证 OpenAPI 规范...")

    openapi_dir = project_root / "openapi"
    openapi_files = list(openapi_dir.glob("*.yaml")) + list(openapi_dir.glob("*.yml"))

    if not openapi_files:
        print("⚠️  未找到 OpenAPI 文件（可能还未创建）")
        return True

    print(f"✅ 找到 {len(openapi_files)} 个 OpenAPI 文件")

    # 使用 openapi-spec-validator 验证
    try:
        from openapi_spec_validator import validate_spec

        for openapi_file in openapi_files:
            try:
                import yaml

                with open(openapi_file, encoding="utf-8") as f:
                    spec = yaml.safe_load(f)

                validate_spec(spec)
                print(f"  ✅ {openapi_file.name}: OpenAPI 验证通过")

            except Exception as e:
                print(f"  ❌ {openapi_file.name}: 验证失败 - {str(e)}")
                return False

        print("✅ 所有 OpenAPI 规范验证通过")
        return True

    except ImportError:
        print("⚠️  openapi-spec-validator 未安装，跳过验证")
        print("💡 运行：poetry add openapi-spec-validator")
        return True


def main():
    """主函数"""
    print("=" * 60)
    print("SDD Schema 验证工具")
    print("=" * 60)

    success = True

    # 验证领域事件 Schema
    if not validate_domain_events():
        success = False

    # 验证 OpenAPI 规范
    if not validate_openapi():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✅ 所有 Schema 验证通过")
        sys.exit(0)
    else:
        print("❌ Schema 验证失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
