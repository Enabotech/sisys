"""BGE-M3 嵌入 API 服务端

通过 FastAPI + FlagEmbedding 将 BGE-M3 封装为独立 HTTP 服务。
Docker Compose 独立部署，通过 POST /v1/embeddings 提供 Dense/Sparse 编码。

架构参考: architecture.md §4.3 嵌入模型配置 — API 模式独立部署
依赖: fastapi, FlagEmbedding, uvicorn
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

app = FastAPI(title="SISYS Embedding API", version="1.0.0")


class EmbedRequest(BaseModel):
    """嵌入请求模型

    Attributes:
        texts: 待编码文本列表（1-64 条）
        return_sparse: 是否返回稀疏词汇权重
    """

    texts: list[str] = Field(..., min_length=1, max_length=64, description="待编码文本列表")
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
    has_weights = any(
        os.path.isfile(os.path.join(path, f))
        for f in ["pytorch_model.bin", "model.safetensors", "pytorch_model.bin.index.json"]
    )
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


@app.on_event("startup")
def load_model() -> None:
    """服务启动时加载 BGE-M3 模型，请求间复用

    加载策略：
    1. 检查 EMBEDDING_MODEL_PATH 是否包含有效模型文件
    2. 若有效则从本地加载，否则从 HuggingFace Hub 下载
    3. 自动检测 CUDA 可用性，无 GPU 时降级至 CPU

    若加载失败，设置 app.state.model = None，healthcheck 将返回 unavailable 状态
    """
    model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    local_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    device, use_fp16 = _detect_device()

    app.state.model = None
    app.state.model_name = model_name
    app.state.device = device
    app.state.load_error = None

    # 优先本地路径（需验证包含模型文件）
    if _validate_model_path(local_path):
        logger.info("从本地路径加载模型: %s (device=%s, fp16=%s)", local_path, device, use_fp16)
        load_path = local_path
    else:
        if local_path:
            logger.warning("本地路径无效或无模型文件: %s，将从 HuggingFace Hub 下载", local_path)
        logger.info("从 HuggingFace Hub 加载模型: %s (device=%s, fp16=%s)", model_name, device, use_fp16)
        load_path = model_name

    try:
        from FlagEmbedding import BGEM3FlagModel

        app.state.model = BGEM3FlagModel(load_path, use_fp16=use_fp16)
        logger.info("模型加载成功: %s", load_path)

    except Exception as e:
        logger.error("模型加载失败: %s", e)
        app.state.load_error = str(e)
        # 不抛出异常，让服务继续运行（healthcheck 会反映状态）


@app.get("/health", response_model=HealthResponse)
async def health() -> dict:
    """健康检查端点

    Returns:
        服务状态、模型名称、设备、错误信息（若有）

    Raises:
        HTTPException 503: 模型未加载
    """
    if app.state.model is not None:
        return {
            "status": "ok",
            "model": app.state.model_name,
            "device": app.state.device,
            "error": None,
        }

    from fastapi import HTTPException

    raise HTTPException(
        status_code=503,
        detail={
            "status": "unavailable",
            "model": app.state.model_name,
            "device": app.state.device,
            "error": app.state.load_error or "Model not loaded",
        },
    )


@app.post("/v1/embeddings", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> dict:
    """嵌入编码端点

    Args:
        req: 嵌入请求

    Returns:
        {"dense": [[...], ...], "sparse": [...] | null}

    Raises:
        HTTPException 503: 模型未加载
    """
    from fastapi import HTTPException

    if app.state.model is None:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding model not available: {app.state.load_error or 'Not loaded'}",
        )

    model = app.state.model
    result = model.encode(
        req.texts,
        return_dense=True,
        return_sparse=req.return_sparse,
    )

    response: dict = {"dense": result["dense_vecs"].tolist()}

    if req.return_sparse:
        lexical_weights = result["lexical_weights"]
        response["sparse"] = [
            {"indices": sorted(int(k) for k in w.keys()), "values": [float(w[k]) for k in sorted(w.keys(), key=int)]}
            for w in lexical_weights
        ]
    else:
        response["sparse"] = None

    return response
