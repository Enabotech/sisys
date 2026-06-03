"""BGE-M3 嵌入 API 服务端

通过 FastAPI + FlagEmbedding 将 BGE-M3 封装为独立 HTTP 服务。
Docker Compose 独立部署，通过 POST /v1/embeddings 提供 Dense/Sparse 编码。

架构参考: architecture.md §4.3 嵌入模型配置 — API 模式独立部署
依赖: fastapi, FlagEmbedding, uvicorn
"""

from __future__ import annotations

from fastapi import FastAPI
from FlagEmbedding import BGEM3FlagModel
from pydantic import BaseModel, Field

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


@app.on_event("startup")
def load_model() -> None:
    """服务启动时加载 BGE-M3 模型，请求间复用"""
    import os

    model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    local_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    use_fp16 = os.getenv("EMBEDDING_MODEL_DEVICE", "cuda") == "cuda"

    if local_path and os.path.isdir(local_path):
        app.state.model = BGEM3FlagModel(local_path, use_fp16=use_fp16)
    else:
        app.state.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)


@app.get("/health")
async def health() -> dict:
    """健康检查端点

    Returns:
        {"status": "ok", "model": "BAAI/bge-m3"}
    """
    return {"status": "ok", "model": "BAAI/bge-m3"}


@app.post("/v1/embeddings", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> dict:
    """嵌入编码端点

    Args:
        req: 嵌入请求

    Returns:
        {"dense": [[...], ...], "sparse": [...] | null}
    """
    model: BGEM3FlagModel = app.state.model
    result = model.encode(
        req.texts,
        return_dense=True,
        return_sparse=req.return_sparse,
    )

    response: dict = {"dense": result["dense_vecs"].tolist()}

    if req.return_sparse:
        lexical_weights = result["lexical_weights"]
        response["sparse"] = [
            {"indices": [int(k) for k in w.keys()], "values": [float(v) for v in w.values()]} for w in lexical_weights
        ]
    else:
        response["sparse"] = None

    return response
