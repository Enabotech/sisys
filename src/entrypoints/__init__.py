"""进程入口层（组装层，Story 5-1 D1 方案 A 落地）

进程入口与应用装配器（Clean Architecture 的 Main 组件——"the dirtiest,
lowest-level component"，架构圈外的终极细节）：负责 bootstrap 装配、
后台服务生命周期管理与进程退出契约，经组合根通道获取实现。

层定位：与 composition_root 同级的组装层，不属于三层
（interfaces/application/domain）中任何一层——不触发任何 import-linter
契约的 source 面；可依赖 composition_root 与 interfaces（路由/命令适配器）。

当前入口：
- agent_cli: sisys-agent 命令行（Agent 实例化）
- ocr_cli: sisys-ocr 命令行（OCR 识别）
- api_app: FastAPI 应用工厂（含 lifespan 轮询器管理）
"""
