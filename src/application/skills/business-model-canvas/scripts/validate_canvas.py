#!/usr/bin/env python3
"""商业模式画布 9 块校验脚本（确定性任务，代码优先）。

输入：9 块 JSON（stdin 或命令行参数）
格式：参考 references/canvas_template.json
输出：校验结果（缺失块 + 关键连接 VP↔CR、KR↔KA）

仅标准库，无外部依赖。
"""

from __future__ import annotations

import json
import sys

REQUIRED_BLOCKS = (
    "key_partners",
    "key_activities",
    "value_propositions",
    "customer_relationships",
    "customer_segments",
    "key_resources",
    "channels",
    "cost_structure",
    "revenue_streams",
)

# 关键连接关系（Osterwalder 经典 9 块映射）
CRITICAL_LINKS = [
    ("value_propositions", "customer_segments", "VP→CS 价值主张应匹配客户细分"),
    ("value_propositions", "customer_relationships", "VP→CR 价值主张应支撑客户关系"),
    ("key_activities", "value_propositions", "KA→VP 关键活动应支撑价值主张"),
    ("key_resources", "key_activities", "KR→KA 关键资源应支撑关键活动"),
    ("channels", "customer_segments", "CH→CS 渠道应触达客户细分"),
]


def validate(canvas: dict) -> dict:
    """校验 9 块完整性 + 关键连接关系。"""
    missing = [b for b in REQUIRED_BLOCKS if not canvas.get(b)]
    empty = [b for b in REQUIRED_BLOCKS if canvas.get(b) == []]

    link_violations = []
    for source, target, desc in CRITICAL_LINKS:
        if canvas.get(source) and not canvas.get(target):
            link_violations.append(f"{desc}: {source} 已填但 {target} 为空")

    is_valid = not missing and not link_violations
    return {
        "valid": is_valid,
        "missing_blocks": missing,
        "empty_blocks": empty,
        "link_violations": link_violations,
        "summary": (
            "OK：9 块全部填充 + 关键连接完整"
            if is_valid
            else f"不通过：缺失 {len(missing)} 块 / 连接违规 {len(link_violations)} 处"
        ),
    }


def main() -> int:
    if len(sys.argv) > 1:
        canvas = json.loads(sys.argv[1])
    else:
        canvas = json.loads(sys.stdin.read())

    result = validate(canvas)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
