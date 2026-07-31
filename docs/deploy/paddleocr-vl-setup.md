# PaddleOCR-VL-1.6 部署指南

## 概述

本文档描述 PaddleOCR-VL-1.6 的 Docker 部署方案，用于 SISYS 系统的 OCR 扫描件解析。
PaddleOCR-VL 是百度 PaddleOCR 最新 VLM 系列，支持 109 种语言的高精度 OCR 识别，
同时具备版面分析和文档理解能力。

## 部署架构

```
SISYS Application → paddleocr-vl-api:8080 → paddleocr-vl-vllm:8118
                                          (vLLM推理引擎)
```

- `paddleocr-vl-api`：对外 API 服务（端口 8080），接收 base64 编码的 PDF/图像
- `paddleocr-vl-vllm`：内部 vLLM 推理引擎（端口 8118），仅 API 服务访问

## 前置要求

| 项目 | 要求 | 说明 |
|------|------|------|
| GPU | RTX 5090 (Blackwell SM120, 32GB GDDR7) | 推荐，其他 NVIDIA GPU 需确认兼容性 |
| CUDA | ≥ 12.9 | 驱动版本必须满足 Blackwell 架构支持 |
| Docker | ≥ 19.03 | 支持 GPU device reservation |
| Docker Compose | ≥ 2.0 | 用于一键启动所有服务 |
| 磁盘空间 | ≥ 50GB | 镜像拉取约 23GB，运行时需额外空间 |

## 快速启动

### 1. 拉取镜像（首次部署，约 30-60 分钟）

```bash
cd deploy/app
docker compose pull paddleocr-vl-api paddleocr-vl-vllm
```

镜像来源（已推送至本地 Harbor）：
- `harbor.sisys.local/sisys/tools/paddlepaddle/paddleocr-vl:latest-nvidia-gpu-sm120-offline` (~10GB)
- `harbor.sisys.local/sisys/tools/paddlepaddle/paddleocr-genai-vllm-server:latest-nvidia-gpu-sm120-offline` (~13GB)

### 2. 验证镜像已拉取

```bash
docker image inspect harbor.sisys.local/sisys/tools/paddlepaddle/paddleocr-vl:latest-nvidia-gpu-sm120-offline
docker image inspect harbor.sisys.local/sisys/tools/paddlepaddle/paddleocr-genai-vllm-server:latest-nvidia-gpu-sm120-offline
```

### 3. 启动所有服务

```bash
cd deploy/app
docker compose up -d
```

此命令将启动所有基础服务（Redis/PostgreSQL/Qdrant/MinIO/Neo4j/RabbitMQ/embedding-api）
以及 PaddleOCR-VL 两服务（paddleocr-vl-api + paddleocr-vl-vllm）。

### 4. 验证服务状态

```bash
docker compose ps
```

预期输出应包含：
- `sisys-paddleocr-vl-vllm` — healthy（启动需 2-5 分钟，模型加载较慢）
- `sisys-paddleocr-vl-api` — healthy（依赖 vllm 服务健康后启动）

### 5. 测试 API

```bash
# 测试健康检查
curl -X GET http://localhost:8080/health

# 测试 OCR 接口（需要准备 base64 编码的 PDF）
curl -X POST http://localhost:8080/layout-parsing \
  -H "Content-Type: application/json" \
  -d '{"file": "<base64_encoded_pdf>", "fileType": 0}'
```

## GPU 配置说明

### GPU 内存分配

| 参数 | 值 | 说明 |
|------|------|------|
| `gpu-memory-utilization` | 0.15 | 0.9B 模型 + vLLM KV cache 约需 4-6GB，0.15 × 32GB = 4.8GB，配合 `--enforce-eager` 禁用 CUDA graph 节省额外 2-3GB |
| GPU 显存要求 | ≥ 6GB | 推荐 ≥ 8GB |

### GPU 分配方式

两服务通过 `deploy.resources.reservations.devices` 分配 GPU，使用 `count: 1`（与 `embedding-api` 一致），
避免硬编码 `device_ids`。

### 非 GPU 环境

非 GPU 环境下 `docker compose up -d` 的行为与现有 `embedding-api` 一致：
GPU reservation 的缺失会导致容器启动失败，此限制非 PaddleOCR-VL 引入的新问题。

## 离线部署说明

所有镜像已推送至本地 Harbor 仓库：
- 镜像地址前缀：`harbor.sisys.local/sisys/tools/paddlepaddle/`
- 镜像后缀：`-offline`（无需外网拉取）

## API 调用方式

### 请求格式

```python
import base64
import httpx

async with httpx.AsyncClient(timeout=300.0) as client:
    with open(file_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "file": b64_data,
        "fileType": 0,  # 0=PDF, 1=image
    }
    resp = await client.post(
        "http://localhost:8080/layout-parsing",
        json=payload,
    )
    resp.raise_for_status()
    result = resp.json()["result"]
```

### 响应格式

```json
{
  "result": {
    "layoutParsingResults": [
      {
        "pageIndex": 0,
        "prunedResult": {
          "parsing_res_list": [
            {
              "block_bbox": [0.05, 0.05, 0.9, 0.1],
              "block_label": "title",
              "block_content": "## 标题",
              "block_id": 0,
              "confidence": 0.98
            }
          ]
        }
      }
    ]
  }
}
```

## 注意事项

1. **启动顺序**：vLLM 服务需先启动并加载模型（2-5 分钟），API 服务依赖于 vLLM healthy
2. **共享内存**：`shm_size: 2g` 足够 vLLM 推理使用（从 64g 降低至 2g，节省 ~62GB 虚拟内存映射）
3. **Python 兼容性**：PaddleOCR 支持 3.9-3.13，与项目 Python 3.11+ 兼容
4. **vLLM 与 Transformers 冲突**：vLLM 和 Transformers 库版本存在冲突，Docker 方式天然隔离
5. **强烈不建议直接调用 VLM 推理服务（8118）**：必须通过 API 服务（8080）的 `/layout-parsing` 端点调用
6. **模型/镜像不纳入 git**：大文件由 Docker 镜像管理，`.gitignore` 已忽略相关目录

## 故障排除

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 容器启动失败 | GPU 不可用 | 检查 `nvidia-smi` 输出，确认 CUDA 驱动版本 ≥ 12.9 |
| vLLM 启动超时 | 模型加载慢 | 增加 `start_period` 至 600s |
| API 返回 502 | vLLM 未就绪 | 检查 `docker logs sisys-paddleocr-vl-vllm` |
| GPU OOM | `gpu-memory-utilization` 过高或未启用 `--enforce-eager` | 降低至 0.15 或添加 `--enforce-eager` 参数；检查 `docker logs sisys-paddleocr-vl-vllm` |
