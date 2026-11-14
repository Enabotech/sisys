"""CLI 输出格式化器包（Story 7-1——三态分发 + 共享参数类型别名）。

三态契约（Task 0.2 冻结表）：
    - json: 单行紧凑信封（ensure_ascii=False）——stdout 纯净可 pipe
    - table: 两遍法动态列宽表格
    - pretty: 人类可读多行中文（缺省态——整合命令沿用既有 ``_print_*``）

共享参数类型别名（Annotated[typer.Option]——命令级签名注入，尾随位置生效；
app 级 callback 选项只能出现在子命令之前与尾随位置冲突，typer 0.24 venv
实证 exit 2，故逐命令签名注入——AC-3 钦定）。
"""

from __future__ import annotations

import enum
from typing import Annotated, Any

import typer

from src.domain.exceptions import ValidationError
from src.interfaces.cli.formatters.json_formatter import build_envelope, render_json
from src.interfaces.cli.formatters.pretty_formatter import render_pretty
from src.interfaces.cli.formatters.table_formatter import render_table

__all__ = [
    "DryRunOption",
    "FormatOption",
    "MockOption",
    "YesOption",
    "build_envelope",
    "enum_value",
    "format_result",
    "render_json",
    "render_pretty",
    "render_table",
]

# 合法格式值域（缺省 pretty——AC-2 钦定）
_FORMAT_CHOICES: tuple[str, ...] = ("json", "table", "pretty")


def enum_value(value: Any) -> str:
    """枚举值安全提取（R1-F4——str()/f-string 对 (str,Enum) 双泄漏类名的防御）。

    Python 3.11 下 ``(str, Enum)`` 混入式枚举的 ``str()`` 与 f-string 输出均为
    ``"类名.成员名"`` 形态（如 ``"ToolStatus.ACTIVE"``）——JSON 信封机器可消费
    契约（P1 原则）被破坏。本函数统一提取 ``.value``。

    Args:
        value: 任意值（枚举成员或纯 str/其他标量）

    Returns:
        枚举成员的 ``.value``；非枚举形态 ``str()`` 兜底（纯 str 无 ``value``
        属性，hasattr 判定双形态安全）
    """
    return value.value if hasattr(value, "value") else str(value)


# 共享 Agent 参数类型别名（逐命令签名注入——Task 2/3 消费）
# --format 值域解析层 Enum 化（R1-F2：非法值原先静默落 pretty 分支真实执行
# exit 0——typer 对 Enum 注解自动渲染 choices 并在解析层拒绝 exit 2，
# 「Python 类型注解驱动」选型原生形态；formatter 纯函数层 201 值域守卫
# 保留为双保险纵深）
class OutputFormat(str, enum.Enum):
    """输出格式三态枚举（AC-2 钦定值域——str 混入兼容既有 str 比较消费位）。"""

    JSON = "json"
    TABLE = "table"
    PRETTY = "pretty"


FormatOption = Annotated[
    OutputFormat,
    typer.Option("--format", help="输出格式：json/table/pretty（缺省 pretty）"),
]
YesOption = Annotated[bool, typer.Option("--yes", help="非交互确认（确认门命令等价兼容入口 --confirm）")]
DryRunOption = Annotated[bool, typer.Option("--dry-run", help="仅校验与回显动作清单，不执行真实调用（client 语义）")]
MockOption = Annotated[
    bool,
    typer.Option(
        "--mock",
        help="模拟执行：零副作用返回 mock 标记输出（输出恒为 JSON 信封——与 --format 无关，机器可读钦定）",
    ),
]


def format_result(
    fmt: str,
    *,
    command: str,
    data: dict[str, Any],
    mock: bool = False,
    echo: dict[str, Any] | None = None,
) -> str:
    """按格式三态分发渲染（json/table/pretty——缺省 pretty）。

    Args:
        fmt: 格式值（json/table/pretty；空串按缺省 pretty）
        command: 命令全名（信封构造用）
        data: CLI 视图 dict 载荷（table 态消费 rows 键或整体键值）
        mock: mock 标记（透传信封）
        echo: mock 参数回显（透传信封）

    Returns:
        渲染后文本（调用方 print 到 stdout）

    Raises:
        ValidationError: EXCEPTION_201——非法格式值（值域守卫在入口层 Typer
            choices 之外的双保险——formatter 纯函数层防御）
    """
    effective = fmt if fmt else "pretty"
    if effective not in _FORMAT_CHOICES:
        raise ValidationError(
            message=f"不支持的输出格式: {effective!r}（合法值: json/table/pretty）",
            context={"format": effective, "choices": list(_FORMAT_CHOICES)},
        )
    if effective == "json":
        return render_json(build_envelope(command=command, data=data, mock=mock, echo=echo))
    if effective == "table":
        return _render_table_from_data(data)
    return render_pretty(data)


def _render_table_from_data(data: dict[str, Any]) -> str:
    """从数据 dict 提取表格（rows 键优先——清单语义；否则整体标量键值）。"""
    list_values = [value for value in data.values() if isinstance(value, list)]
    for value in list_values:
        if value and isinstance(value[0], dict):
            headers = list(value[0].keys())
            rows = [[str(item.get(header, "")) for header in headers] for item in value]
            return render_table(headers, rows)
    # 空态可辨识（R1-F11）：data 含清单键但全部为空时渲染空态行（空清单退化为
    # 标量单格不可辨识——对照 pretty/json 态均有空态语义）
    if list_values:
        return render_table(["(empty)"], [["（空清单）"]])
    scalar = {key: str(val) for key, val in data.items() if not isinstance(val, (list, dict))}
    if not scalar:
        return render_table(["(empty)"], [[""]])
    headers = list(scalar.keys())
    return render_table(headers, [list(scalar.values())])
