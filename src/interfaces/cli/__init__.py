"""接口层 CLI 命令适配器模块

命令定义适配器（argparse/Typer）。进程入口（bootstrap 装配与 main()）
已上移 src/entrypoints/ 组装层（D1 方案 A）；本包承载命令解析与
业务转发。统一 sisys 入口经 ``main.create_cli_app(resolve)`` 工厂装配
（Story 7-1 交付）。
"""

__all__: list[str] = []
