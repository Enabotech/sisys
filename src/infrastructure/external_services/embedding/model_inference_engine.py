"""模型推理引擎

管理 SafeBGE3Model 生命周期，提供模型加载/卸载/推理的完整管理。
实现 ModelInferencePort 领域端口。

职责范围：
- 模型加载/卸载（生命周期管理）
- 推理入口（encode）
- 输出向量 NaN/Inf 防御性净化
- Sparse 权重格式化（FlagEmbedding lexical_weights → API 响应格式）

设计决策：
- 模型加载失败时不抛出异常，而是记录 load_error 供健康检查感知
- 推理失败时抛出 ModelInferenceError 统一异常
- 静态类锁：防止多实例并发推理竞争（服务进程内单例）

架构参考：architecture.md §4.3 嵌入模型配置 — API 模式独立部署
异常规范：sisys-uni-exception-design.md — 使用统一异常层次结构
"""

from __future__ import annotations

import logging
import threading
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from src.domain.exceptions import ModelInferenceError
from src.infrastructure.external_services.embedding.safe_model import SafeBGE3Model

logger = logging.getLogger(__name__)


class ModelInferenceEngine:
    """模型推理引擎

    管理模型加载、推理、卸载的完整生命周期。
    作为 ModelInferencePort 的实现，供 embedding_api_server 等接口层使用。

    Args:
        model_path: BGE-M3 模型路径或 HuggingFace 模型名称
        device: 推理设备（cuda/cpu）
        use_fp16: 是否使用 fp16 精度
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        use_fp16: bool = True,
    ) -> None:
        self._model_path = model_path
        self._device = device
        self._use_fp16 = use_fp16
        self._model: SafeBGE3Model | None = None
        self._load_error: str | None = None
        # 推理锁：静态类锁，防止多实例并发推理竞争
        # 单 worker 模式下所有请求共享同一静态锁，串行化模型推理
        self._inference_lock = threading.Lock()

    def load(self) -> None:
        """加载模型（幂等，可多次调用）

        加载失败时设置 _load_error 供健康检查感知，不抛出异常。
        """
        if self._model is not None:
            return

        try:
            self._model = SafeBGE3Model(
                model_path=self._model_path,
                use_fp16=self._use_fp16,
                device=self._device,
            )
            self._load_error = None
            logger.info("模型加载成功: %s (device=%s)", self._model_path, self._device)
        except Exception as e:
            self._load_error = str(e)
            logger.error("模型加载失败: %s", e)

    @property
    def is_ready(self) -> bool:
        """模型是否已加载并可推理

        Returns:
            True 表示模型已加载且无错误
        """
        return self._model is not None and self._load_error is None

    @property
    def load_error(self) -> str | None:
        """模型加载错误信息

        Returns:
            加载错误描述，未失败时返回 None
        """
        return self._load_error

    @property
    def dimension(self) -> int:
        """模型输出向量维度

        Returns:
            向量维度（bge-m3 固定为 1024）
        """
        return 1024

    def encode(
        self,
        texts: list[str],
        return_sparse: bool = False,
    ) -> dict:
        """模型推理入口

        Args:
            texts: 待编码文本列表（至少 1 条）
            return_sparse: 是否返回稀疏词汇权重

        Returns:
            {"dense": list[list[float]], "sparse": list[dict] | None}
            - dense: 经 L2 归一化的浮点向量列表
            - sparse: 稀疏向量列表（仅 return_sparse=True 时有值）

        Raises:
            ModelInferenceError: 模型未加载或推理失败时
        """
        if not self.is_ready:
            raise ModelInferenceError(
                f"模型未加载: {self._load_error or '未知错误'}",
            )

        # 串行化模型推理：FlagEmbedding encode_single_device() 非线程安全
        # 并发调用时 model.to(device) + model.eval() 非原子操作，
        # 可能导致模型精度状态被部分重置，输出 NaN/Inf
        try:
            with self._inference_lock:
                model = self._model
                assert model is not None  # is_ready 已保证
                result: dict[str, Any] = cast(
                    dict[str, Any],
                    model.encode(
                        texts,
                        return_dense=True,
                        return_sparse=return_sparse,
                    ),
                )
        except Exception as e:
            logger.exception(
                "模型推理失败 (texts=%d, return_sparse=%s)",
                len(texts),
                return_sparse,
            )
            raise ModelInferenceError(f"模型推理失败: {e}", cause=e) from e

        # 校验模型输出结构：防止 FlagEmbedding 版本变更导致键名变化
        if "dense_vecs" not in result:
            logger.error("模型输出缺少 'dense_vecs' 键，实际键: %s", list(result.keys()))
            raise ModelInferenceError("模型输出缺少 'dense_vecs' 键")

        dense_vecs = result["dense_vecs"]
        if len(dense_vecs) != len(texts):
            logger.error("模型输出向量数(%d)与请求数(%d)不匹配", len(dense_vecs), len(texts))
            raise ModelInferenceError(f"向量数不匹配: {len(dense_vecs)} != {len(texts)}")

        # 防御性净化：剔除 NaN/Inf 确保 JSON 序列化兼容
        dense_vecs = self._sanitize_dense_vectors(dense_vecs)

        response: dict = {"dense": np.asarray(dense_vecs).tolist()}

        if return_sparse:
            if "lexical_weights" not in result:
                logger.error("模型输出缺少 'lexical_weights' 键（return_sparse=True）")
                raise ModelInferenceError("模型输出缺少 'lexical_weights' 键")
            response["sparse"] = self._parse_sparse_weights(result["lexical_weights"])
        else:
            response["sparse"] = None

        return response

    def _sanitize_dense_vectors(
        self,
        dense_vecs: Any,
    ) -> npt.NDArray[np.floating]:
        """防御性净化浮点向量，剔除 NaN/Inf 确保 JSON 序列化兼容

        Starlette 0.37.2 JSONResponse 默认 allow_nan=False，
        NaN/Inf 会导致 json.dumps 抛出 ValueError → HTTP 500。
        浮点推理在 fp16 精度下偶现 NaN/Inf（并发竞争、GPU 数值不稳定等），
        此函数作为最后一道防线，将不安全值替换为 0.0。

        Args:
            dense_vecs: 原始模型输出向量

        Returns:
            净化后的向量（不含 NaN/Inf）
        """
        arr = np.asarray(dense_vecs)
        if not np.any(np.isnan(arr)) and not np.any(np.isinf(arr)):
            return arr
        logger.warning(
            "检测到 NaN/Inf 向量，已自动净化 (shape=%s, nan_count=%d, inf_count=%d)",
            arr.shape,
            int(np.sum(np.isnan(arr))),
            int(np.sum(np.isinf(arr))),
        )
        return cast(npt.NDArray[np.floating], np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0))

    def _parse_sparse_weights(self, lexical_weights: list[dict]) -> list[dict]:
        """解析 FlagEmbedding 稀疏词汇权重为 API 响应格式

        保证返回列表长度与输入 lexical_weights 长度一致，
        即使某条文本的所有 token ID 解析失败，也会返回空 indices/values。

        Args:
            lexical_weights: FlagEmbedding 返回的词汇权重列表（键为 token ID 字符串）

        Returns:
            格式化的稀疏向量列表 [{"indices": [...], "values": [...]}, ...]
        """
        sparse_list: list[dict] = []
        for w in lexical_weights:
            sorted_items: list[tuple[int, float]] = []
            for k, v in w.items():
                try:
                    sorted_items.append((int(k), float(v)))
                except (ValueError, TypeError):
                    logger.warning("跳过非法 token ID: %s", k)
            sorted_items.sort(key=lambda x: x[0])
            # 即使 sorted_items 为空也必须 append，保证输出长度与输入一致
            sparse_list.append(
                {
                    "indices": [idx for idx, _ in sorted_items],
                    "values": [val for _, val in sorted_items],
                }
            )
        return sparse_list

    def unload(self) -> None:
        """卸载模型，释放 GPU 资源

        幂等：重复调用安全。
        """
        if self._model is not None:
            del self._model
            self._model = None
            self._load_error = None
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            logger.info("模型已卸载，GPU 缓存已释放")


__all__ = [
    "ModelInferenceEngine",
]
