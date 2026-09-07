#!/usr/bin/env python3
"""PESTEL 评分聚合脚本（确定性任务，代码优先）。

输入：6 维度评分 JSON（stdin 或命令行参数）
格式：{"P": 0.8, "E": 0.7, "S": 0.6, "T": 0.9, "En": 0.5, "L": 0.7}
输出：加权总分 + 机会威胁矩阵（stdout）

权重来自 references/scoring_matrix.json：
- P/E 各 0.20
- S/T/En/L 各 0.15

仅标准库，无外部依赖。
"""

from __future__ import annotations

import json
import sys

DIMENSION_WEIGHTS = {
    "P": 0.20,
    "E": 0.20,
    "S": 0.15,
    "T": 0.15,
    "En": 0.15,
    "L": 0.15,
}

DIMENSION_NAMES = {
    "P": "政治",
    "E": "经济",
    "S": "社会",
    "T": "技术",
    "En": "环境",
    "L": "法律",
}


def aggregate(scores: dict) -> dict:
    """计算加权总分 + 机会威胁分类。"""
    weighted_total = sum(scores.get(k, 0.0) * w for k, w in DIMENSION_WEIGHTS.items())
    weighted_total = round(weighted_total, 4)

    opportunities = [k for k, v in scores.items() if v >= 0.7]
    threats = [k for k, v in scores.items() if v <= 0.4]
    neutral = [k for k, v in scores.items() if 0.4 < v < 0.7]

    return {
        "weighted_total": weighted_total,
        "score_grade": "机会主导" if weighted_total >= 0.7 else "中性" if weighted_total >= 0.4 else "威胁主导",
        "opportunities": [f"{k}({DIMENSION_NAMES[k]}={scores[k]:.2f})" for k in opportunities],
        "threats": [f"{k}({DIMENSION_NAMES[k]}={scores[k]:.2f})" for k in threats],
        "neutral": [f"{k}({DIMENSION_NAMES[k]}={scores[k]:.2f})" for k in neutral],
    }


def main() -> int:
    if len(sys.argv) > 1:
        # 第一个参数作为 JSON 字符串
        scores = json.loads(sys.argv[1])
    else:
        # 从 stdin 读取
        scores = json.loads(sys.stdin.read())

    result = aggregate(scores)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
