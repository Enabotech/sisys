"""onnxruntime 类型存根

基于 onnxruntime v1.17+ 公开 API 提供完整类型定义。
onnxruntime 是 ONNX 模型的跨平台推理引擎，核心类为 InferenceSession。
覆盖 OnnxLayoutDetector 使用的方法。
来源: src/infrastructure/document_parsing/onnx_layout_detector.py
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray


class NodeArg:
    """ONNX 模型节点参数 — 描述输入/输出张量的元信息

    通过 InferenceSession.get_inputs() / get_outputs() 获取。
    """

    name: str
    type: str | None
    shape: list[int | str] | None


class InferenceSession:
    """ONNX 推理会话 — 加载模型并执行推理

    支持 CPU（CPUExecutionProvider）和 GPU（CUDAExecutionProvider）两种推理提供者。
    会话创建后通过 run() 方法执行前向推理。
    """

    def __init__(
        self,
        model_path: str,
        providers: list[str] | None = None,
        sess_options: Any = None,
    ) -> None: ...

    def get_inputs(self) -> list[NodeArg]: ...
    def get_outputs(self) -> list[NodeArg]: ...

    def run(
        self,
        output_names: list[str] | None,
        input_feed: dict[str, NDArray[np.float32]],
    ) -> list[NDArray[np.float32]]: ...
