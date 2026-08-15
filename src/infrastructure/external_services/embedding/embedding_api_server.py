"""BGE-M3 嵌入 API 服务端

通过 FastAPI + ModelInferenceEngine 将 BGE-M3 封装为独立 HTTP 服务。
Docker Compose 独立部署，通过 POST /v1/embeddings 提供 Dense/Sparse 编码。

架构变更：
- v1.0: 直接使用 BGEM3FlagModel（无锁，有竞态条件）
- v1.1: 使用 _embed_lock + _sanitize_dense_vectors（线程安全锁）
- v2.0: 使用 ModelInferenceEngine + SafeBGE3Model（重构版，消除冗余操作）

架构参考: architecture.md §4.3 嵌入模型配置 — API 模式独立部署
依赖: fastapi, uvicorn
线程安全策略: ModelInferenceEngine 内部使用 threading.Lock 串行化模型推理
输出向量经 np.nan_to_num 防御性净化，确保 JSON 序列化零失败
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.infrastructure.external_services.embedding.model_inference_engine import (
    ModelInferenceEngine,
)

logger = logging.getLogger(__name__)

# 全局推理引擎实例
_engine: ModelInferenceEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan 上下文管理器

    替代已弃用的 @app.on_event("startup")，管理模型加载/卸载生命周期。
    """
    global _engine
    load_model()
    yield
    # Shutdown: 释放模型和 GPU 资源
    if _engine is not None:
        _engine.unload()
        _engine = None
        logger.info("模型资源已释放")


app = FastAPI(title="SISYS Embedding API", version="2.0.0", lifespan=lifespan)


def _validate_model_path(path: str) -> bool:
    """验证模型路径是否包含有效的模型文件

    Args:
        path: 模型目录路径

    Returns:
        True 如果目录存在且包含必要的模型文件（config.json 或 pytorch_model.bin/safetensors）
    """
    if not path or not os.path.isdir(path):
        return False
    # 检查是否存在模型配置文件和权重文件
    has_config = os.path.isfile(os.path.join(path, "config.json"))
    has_weights = any(os.path.isfile(os.path.join(path, f)) for f in ["pytorch_model.bin", "model.safetensors"])
    return has_config and has_weights


def _detect_device() -> tuple[str, bool]:
    """检测可用设备并返回设备名称和 fp16 标志

    Returns:
        (device_name, use_fp16) tuple
    """
    requested_device = os.getenv("EMBEDDING_MODEL_DEVICE", "cuda")

    if requested_device == "cuda":
        try:
            import torch

            if torch.cuda.is_available():
                logger.info("CUDA 可用，使用 GPU 加速")
                return "cuda", True
            else:
                logger.warning("CUDA 不可用，降级至 CPU")
                return "cpu", False
        except ImportError:
            logger.warning("torch 未安装，降级至 CPU")
            return "cpu", False

    return requested_device, False


def load_model() -> None:
    """服务启动时加载 BGE-M3 模型，请求间复用

    加载策略：
    1. 检查 EMBEDDING_MODEL_PATH 是否包含有效模型文件
    2. 若有效则从本地加载，否则从 HuggingFace Hub 下载
    3. 自动检测 CUDA 可用性，无 GPU 时降级至 CPU

    若加载失败，设置引擎内部错误状态，healthcheck 将返回 unavailable 状态
    """
    global _engine

    model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    local_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    device, use_fp16 = _detect_device()

    # 优先本地路径（需验证包含模型文件）
    if _validate_model_path(local_path):
        logger.info("从本地路径加载模型: %s (device=%s, fp16=%s)", local_path, device, use_fp16)
        load_path = local_path
    else:
        if local_path:
            logger.warning("本地路径无效或无模型文件: %s，将从 HuggingFace Hub 下载", local_path)
        logger.info("从 HuggingFace Hub 加载模型: %s (device=%s, fp16=%s)", model_name, device, use_fp16)
        load_path = model_name

    _engine = ModelInferenceEngine(
        model_path=load_path,
        device=device,
        use_fp16=use_fp16,
    )
    _engine.load()


class EmbedRequest(BaseModel):
    """嵌入请求模型

    Attributes:
        texts: 待编码文本列表（至少 1 条，无上限，由 GPU 内存自然约束）
        return_sparse: 是否返回稀疏词汇权重
    """

    texts: list[str] = Field(..., min_length=1, description="待编码文本列表")
    return_sparse: bool = Field(False, description="是否返回稀疏词汇权重")


class EmbedResponse(BaseModel):
    """嵌入响应模型

    Attributes:
        dense: 稠密向量列表（每项 1024 维 float）
        sparse: 稀疏向量列表（仅 return_sparse=True 时有值）
    """

    dense: list[list[float]]
    sparse: list[dict] | None = None


class HealthResponse(BaseModel):
    """健康检查响应模型

    Attributes:
        status: 服务状态（ok/loading/unavailable）
        model: 模型名称
        device: 运行设备（cuda/cpu）
        error: 错误信息（仅 status=unavailable 时有值）
    """

    status: str
    model: str
    device: str
    error: str | None = None


@app.get("/health", response_model=HealthResponse)
async def health() -> dict:
    """健康检查端点

    Returns:
        服务状态、模型名称、设备、错误信息（若有）

    Raises:
        HTTPException 503: 模型未加载
    """
    global _engine

    if _engine is not None and _engine.is_ready:
        return {
            "status": "ok",
            "model": os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
            "device": os.getenv("EMBEDDING_MODEL_DEVICE", "cuda"),
            "error": None,
        }

    raise HTTPException(
        status_code=503,
        detail={
            "status": "unavailable",
            "model": os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
            "device": os.getenv("EMBEDDING_MODEL_DEVICE", "cuda"),
            "error": _engine.load_error if _engine is not None else "Engine not initialized",
        },
    )


@app.post("/v1/embeddings", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> dict:
    """嵌入编码端点

    使用同步 def（非 async），FastAPI 自动在线程池中执行，
    避免 ModelInferenceEngine.encode() 的同步推理阻塞事件循环。
    线程安全由 ModelInferenceEngine 内部 threading.Lock 保证。

    Args:
        req: 嵌入请求

    Returns:
        {"dense": [[...], ...], "sparse": [...] | null}

    Raises:
        HTTPException 503: 模型未加载
    """
    global _engine

    if _engine is None or not _engine.is_ready:
        error_detail = _engine.load_error if _engine is not None else "Engine not initialized"
        raise HTTPException(
            status_code=503,
            detail=f"Embedding model not available: {error_detail}",
        )

    return _engine.encode(req.texts, return_sparse=req.return_sparse)
