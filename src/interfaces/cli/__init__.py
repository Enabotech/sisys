"""接口层 CLI 命令适配器模块

命令定义适配器（argparse/Typer）。进程入口（bootstrap 装配与 main()）
已上移 src/entrypoints/ 组装层（D1 方案 A）；本包承载命令解析与
业务转发。document_commands 为未接线存量（无挂载点，勿仿）。
"""

__all__: list[str] = []
