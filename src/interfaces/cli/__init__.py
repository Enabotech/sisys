"""接口层 CLI 命令适配器模块

命令定义适配器（Typer——Story 7-1 统一入口）。进程入口（bootstrap 装配与
main()）在 src/entrypoints/ 组装层（D1 方案 A）；本包承载命令解析与业务
转发。document/tool/archive 命令已接线统一入口（interfaces/cli/main.py
挂载——Story 7-1；bootstrap/关池经 dispatch 组装期注入钩子，interfaces 层
禁 import entrypoints/composition_root——OD-16 传导链守卫）。
"""

__all__: list[str] = []
