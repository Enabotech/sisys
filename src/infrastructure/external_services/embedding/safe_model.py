"""线程安全 BGE-M3 模型包装器

继承 BGEM3FlagModel 并通过 threading.Lock 保护模型推理的线程安全。
初始化时一次性固定设备/精度/评估模式，阻止父类 encode_single_device 的重复操作。

设计决策：
- 使用 threading.Lock 而非 asyncio.Lock：FastAPI 的同步 def 在线程池中执行，
  模型推理本身是同步阻塞操作，threading.Lock 是正确选择
- 不重写 encode_single_device：PyTorch model.to(device) 在设备已就绪时是幂等操作，
  无实际 GPU 拷贝开销。仅需通过 use_fp16=False 阻止 model.half() 重复调用
- 不重写 encode()：通过 lock 保护 super().encode() 的完整调用链，包括
  tokenizer.encode → model.forward → output processing 的完整路径

架构参考：architecture.md §4.3 嵌入模型配置 — API 模式独立部署
异常规范：sisys-uni-exception-design.md — 使用统一异常层次结构
"""

from __future__ import annotations

import logging
import threading
from typing import Any, cast

logger = logging.getLogger(__name__)


class SafeBGE3Model:
    """线程安全 BGE-M3 模型

    继承 BGEM3FlagModel 并通过 threading.Lock 保护模型推理。
    初始化时一次性固定设备/精度/评估模式，推理时不再重复执行 model.half()。

    线程安全策略：
    - threading.Lock 串行化 encode() 调用，防止并发请求下
      encode_single_device() 内 model.to(device) + model.eval() 非原子操作
      导致模型精度状态被部分重置，输出 NaN/Inf
    - 初始化时执行 model.half() + model.to(device) + model.eval() 后，
      设置 use_fp16=False 阻止父类 encode_single_device 重复调用 model.half()

    Args:
        model_path: 模型路径或 HuggingFace 模型名称
        use_fp16: 是否使用 fp16 精度（初始化时一次性应用）
        device: 目标设备（cuda/cpu），None 时自动检测使用 self.target_devices[0]
    """

    _model: Any  # BGEM3FlagModel 实例，运行时动态确定类型
    _inference_lock: threading.Lock
    _device: str
    _use_fp16: bool

    def __init__(
        self,
        model_path: str,
        use_fp16: bool = False,
        device: str | None = None,
    ) -> None:
        """初始化 SafeBGE3Model

        Args:
            model_path: 模型路径或 HuggingFace 模型名称
            use_fp16: 是否使用 fp16 精度（初始化时一次性应用）
            device: 目标设备，None 时自动检测
        """
        # 延迟导入 FlagEmbedding：仅在实例化时加载，模块导入时不触发
        # 避免 pytest 收集阶段（含 xdist 多 worker）无谓加载 3 秒的 FlagEmbedding
        from FlagEmbedding import BGEM3FlagModel as _BGEM3FlagModel

        self._model = _BGEM3FlagModel(model_path, use_fp16=use_fp16)

        # 确定目标设备
        if device is None:
            device = self._model.target_devices[0]

        # 一次性固定设备/精度/评估模式
        if use_fp16:
            self._model.model.half()
        self._model.model.to(device)
        self._model.model.eval()

        # 阻止父类 encode_single_device 每次推理重复调用 model.half()
        self._model.use_fp16 = False

        # 推理锁
        self._inference_lock = threading.Lock()
        self._device = device
        self._use_fp16 = use_fp16

        logger.info(
            "SafeBGE3Model 初始化完成: device=%s, fp16=%s",
            device,
            use_fp16,
        )

    @property
    def model(self) -> Any:
        """内部 BGEM3FlagModel 实例"""
        return self._model

    def encode(
        self,
        sentences: str | list[str],
        return_dense: bool = True,
        return_sparse: bool = False,
        return_colbert_vecs: bool = False,
        batch_size: int = 256,
        max_length: int = 8192,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """线程安全的模型编码入口

        Args:
            sentences: 输入文本（字符串或字符串列表）
            return_dense: 是否返回 Dense 向量
            return_sparse: 是否返回 Sparse 词汇权重
            return_colbert_vecs: 是否返回 ColBERT 向量
            batch_size: 推理批次大小
            max_length: 最大 token 长度
            **kwargs: 传递给父类 encode() 的额外参数

        Returns:
            {"dense_vecs": np.ndarray, "lexical_weights": list[dict] | None, ...}
        """
        with self._inference_lock:
            return cast(
                dict[str, Any],
                self._model.encode(
                    sentences,
                    return_dense=return_dense,
                    return_sparse=return_sparse,
                    return_colbert_vecs=return_colbert_vecs,
                    batch_size=batch_size,
                    max_length=max_length,
                    **kwargs,
                ),
            )


__all__ = [
    "SafeBGE3Model",
]
