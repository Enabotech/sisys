# 词嵌入服务并发保护机制重构设计

**文档版本：** v1.0
**创建日期：** 2026-08-14
**作者：** Agimtech
**状态：** 设计完成

---

## 目录

1. [问题分析与现状诊断](#1-问题分析与现状诊断)
2. [设计目标与原则](#2-设计目标与原则)
3. [架构总览](#3-架构总览)
4. [领域层端口定义（R1）](#4-领域层端口定义r1)
5. [应用层端口定义（R2）](#5-应用层端口定义r2)
6. [基础设施层实现（R3）](#6-基础设施层实现r3)
7. [接口层适配（R4）](#7-接口层适配r4)
8. [异常体系与错误处理（R5）](#8-异常体系与错误处理r5)
9. [性能基线对比](#9-性能基线对比)
10. [实施路线图](#10-实施路线图)
11. [附录：FlagEmbedding encode_single_device 源码分析](#11-附录flageembedding-encode_single_device-源码分析)

---

## 1. 问题分析与现状诊断

### 1.1 问题症状

| 症状 | 触发条件 | 原因 |
|------|---------|------|
| **Dense 向量退化**：不同文本的余弦相似度趋近 1.0（如 `cos("企业战略规划报告","苹果和香蕉是水果")=0.999966`） | 多请求并发调用 `embedding_api_server` 的 `/v1/embeddings` 端点 | 模型内部状态在并发推理时被破坏 |
| **测试失败**：`test_embed_and_search_e2e` 断言 `assert results[0]["payload"]["text"] == "企业战略规划报告"` 失败，返回"人力资源计划" | `pytest -n auto` 并行执行时，大量测试同时调用嵌入 API | 向量退化导致排序失效 |
| **重启后恢复**：`docker restart sisys-embedding-api` 后向量质量恢复正常 | 测试单独运行（无并发） | 模型加载后状态初始正确，仅在并发下退化 |

### 1.2 根因分析

#### 1.2.1 FlagEmbedding 源码级竞态条件

`BGEM3FlagModel.encode_single_device()` 每次推理都执行以下操作（[容器内路径](/app/.venv/lib/python3.11/site-packages/FlagEmbedding/inference/embedder/encoder_only/m3.py)）：

```python
@torch.no_grad()
def encode_single_device(self, sentences, ...):
    if device is None:
        device = self.target_devices[0]
    if device == "cpu": self.use_fp16 = False
    if self.use_fp16: self.model.half()       # ① 精度转换（非线程安全）
    self.model.to(device)                     # ② 模型拷贝到设备（非线程安全，2.2GB！）
    self.model.eval()                         # ③ 设置评估模式（非线程安全）
    # ... 实际推理 ...
```

当两个请求同时进入 `encode_single_device`：
- 请求 A 执行 `model.to(device)` 时，模型参数正在 GPU 上重新分配
- 请求 B 同时执行 `model.eval()`，模型参数可能处于不一致状态
- 结果：模型输出向量退化，不同文本的输出几乎相同

#### 1.2.2 现有 workaround 的局限性

`load_model()` 中的 workaround：

```python
if use_fp16 and hasattr(app.state.model, "model"):
    app.state.model.model.half()          # 启动时一次性转换
    app.state.model.use_fp16 = False      # 标记跳过后续重复转换
```

| 问题 | 评级 | 说明 |
|------|------|------|
| **仅规避了 `model.half()`，未规避 `model.to(device)` + `model.eval()`** | 🔴 致命 | `model.to(device)` 每次全量拷贝 2.2GB 参数，是最大性能浪费 |
| **依赖内部私有属性 `use_fp16`** | 🟡 中 | FlagEmbedding 升级可能静默失效 |
| **无锁保护** | 🔴 致命 | 仅靠 workaround 不能解决竞态条件 |
| **容器镜像不包含最新代码** | 🟡 中 | `b144036f` 提交（线程安全锁 + NaN 净化）在 `2026-07-30`，镜像在 `2026-07-20` 构建 |

#### 1.2.3 当前性能数据

| 场景 | 耗时 | 每文本均摊 | 吞吐量 |
|------|------|-----------|--------|
| 单文本请求（P50） | 25.4ms | 25.4ms | 39 req/s |
| 批量 32 文本 | 41.7ms | **1.3ms** | 768 doc/s |
| 16 并发单文本（锁串行） | 1120.8ms | 70.0ms | 14 req/s |

**核心洞察**：批量推理的边际成本极低（32 文本仅比 1 文本慢 64%），但吞吐量提升 **24 倍**。当前架构的锁串行模式严重浪费 GPU 并行计算能力。

### 1.3 对标业界最佳实践

| 方案 | 线程安全 | 冗余设备拷贝 | 动态批处理 | 多 worker 安全 |
|------|---------|-------------|-----------|---------------|
| **TorchServe** | 内置模型 worker 隔离 | ❌ 无 | ✅ 内置 `batch_delay` | ✅ 多 GPU 隔离 |
| **NVIDIA Triton** | 内置模型实例隔离 | ❌ 无 | ✅ 内置调度器 | ✅ 多 GPU 隔离 |
| **HuggingFace TGI** | 内置 | ❌ 无 | ✅ 连续批处理 | ✅ 多 GPU 隔离 |
| **当前实现（`_embed_lock`）** | ✅ 线程锁 | 🔴 每次 `model.to(device)` | ❌ 无 | ❌ 多 worker 失效 |
| **当前实现（无锁）** | ❌ 竞态 | 🔴 每次 `model.to(device)` | ❌ 无 | ❌ 多 worker 失效 |

---

## 2. 设计目标与原则

### 2.1 设计目标

| 目标 | 指标 | 优先级 |
|------|------|--------|
| **T1: 线程安全** | 并发 32 请求下 0 向量退化 | P0 |
| **T2: 消除冗余 GPU 拷贝** | 消除 `model.to(device)` 每次推理调用 | P1 |
| **T3: 动态批处理** | 吞吐量提升 10-20 倍（相对锁串行） | P2 |
| **T4: 多 worker 安全** | 支持 `--workers N` 多进程部署 | P2 |
| **T5: 版本兼容** | 不依赖 FlagEmbedding 内部私有属性 | P1 |

### 2.2 设计原则

| 编号 | 原则 | 说明 |
|------|------|------|
| **R1** | 领域层统一抽象各类基础端口 | `ModelInferencePort` 定义模型推理的抽象契约 |
| **R2** | 领域层/应用层的具体应用端口可以组合注入或继承 R1 所述端口 | `EmbeddingServicePort` 继承/组合 `ModelInferencePort` |
| **R3** | 基础设施层实现领域层/应用层的具体应用端口，负责具体技术的实现与管理 | `SafeBGE3Model` 实现 `ModelInferencePort`，`EmbeddingAPIClient` 实现 `EmbeddingServicePort` |
| **R4** | 接口层适配外部请求，格式化响应，进行外部<->内部接口适配管理 | `embedding_api_server` 使用 `ModelInferenceEngine` 提供服务 |
| **R5** | 严格遵循 sisys-uni-exception-design.md | 所有异常继承领域异常体系，使用 `EXCEPTION_306~319` 编码 |

### 2.3 架构约束

- **领域层零外部依赖**：`ModelInferencePort` 仅使用 `typing.Protocol`，不依赖 `torch`/`FlagEmbedding`/`numpy`/`httpx`
- **基础设施层可替换**：`SafeBGE3Model` 替换为 `ONNXModel` 或 `OpenAIEmbedding` 时，领域/应用层零改动
- **向后兼容**：`EmbeddingServicePort` Protocol 方法签名不变，现有调用方无需修改

---

## 3. 架构总览

### 3.1 分层组件映射

```
┌─────────────────────────────────────────────────────────────────────────┐
│  接口层 (R4)  ─  src/infrastructure/external_services/embedding/        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  embedding_api_server.py                                        │   │
│  │  POST /v1/embeddings → SafeModelInferenceEngine.encode()       │   │
│  │  GET /health         → 健康检查                                 │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                  │ 使用                                │
├──────────────────────────────────┼──────────────────────────────────────┤
│  基础设施层 (R3)                │                                      │
│  ┌──────────────────────────────▼──────────────────────────────────┐   │
│  │  safe_model.py — SafeBGE3Model                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  SafeBGE3Model(BGEM3FlagModel):                          │  │   │
│  │  │   - 初始化时一次性 model.to(device) + model.eval()       │  │   │
│  │  │   - 重写 encode_single_device() 消除冗余操作              │  │   │
│  │  │   - threading.Lock 保护模型推理                           │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  model_inference_engine.py — ModelInferenceEngine         │  │   │
│  │  │   - 管理 SafeBGE3Model 生命周期                          │  │   │
│  │  │   - 可选：动态批处理队列（Phase 2）                      │  │   │
│  │  │   - 熔断器集成                                           │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │  embedding_api_client.py — EmbeddingAPIClient（已有，不变）     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                          │ 实现                                        │
├──────────────────────────┼──────────────────────────────────────────────┤
│  应用层 (R2)             │                                              │
│  ┌──────────────────────▼──────────────────────────────────────────┐   │
│  │  EmbeddingServicePort（已有，不变）                              │   │
│  │  - embed_query / embed_documents / embed_sparse                 │   │
│  │  - 组合 ModelInferencePort 的高阶能力                          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                          │ 继承/组合                                    │
├──────────────────────────┼──────────────────────────────────────────────┤
│  领域层 (R1)             │                                              │
│  ┌──────────────────────▼──────────────────────────────────────────┐   │
│  │  ModelInferencePort（新增）                                      │   │
│  │  - 模型推理的抽象契约，零外部依赖                                 │   │
│  │  - encode() / dimension / close()                                │   │
│  │                                                                   │   │
│  │  EmbeddingServicePort（已有，不变）                               │   │
│  │  - embed_query / embed_documents / embed_sparse                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 并发保护策略选择

| 策略 | 保护范围 | 优点 | 缺点 | 选择 |
|------|---------|------|------|------|
| **A: 进程内 `threading.Lock`** | 单进程内线程安全 | 实现简单，延迟低 | 多 Worker 失效 | ✅ **Phase 1** |
| **B: 动态批处理队列** | 积累请求批量推理 | 吞吐量最高 | 增加排队延迟 | ✅ **Phase 2** |
| **C: 进程级文件锁** | 多进程互斥 | 多 Worker 安全 | 性能开销大 | ❌ 不推荐 |
| **D: 独立 GPU 分配** | 每 Worker 独享 GPU | 多 Worker 安全 | 需要多 GPU | ❌ 按需 |

---

## 4. 领域层端口定义（R1）

### 4.1 `ModelInferencePort` — 模型推理基础端口

**文件位置**：`src/domain/ports/model_inference.py`（新增）

```python
"""领域层模型推理端口

定义模型推理的抽象契约，由基础设施层实现。
遵循 R1：领域层统一抽象各类基础端口，零外部依赖。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelInferencePort(Protocol):
    """模型推理端口

    提供模型推理的最基本抽象，不区分 Dense/Sparse 等嵌入类型。
    由 SafeBGE3Model、ONNXModel 等具体实现。
    """

    @property
    def dimension(self) -> int:
        """模型输出向量维度

        Returns:
            向量维度（bge-m3 为 1024）
        """
        ...

    async def encode(
        self,
        texts: list[str],
        return_sparse: bool = False,
    ) -> dict:
        """模型推理入口

        Args:
            texts: 待编码文本列表
            return_sparse: 是否返回稀疏词汇权重

        Returns:
            {"dense_vecs": np.ndarray, "lexical_weights": list[dict] | None}
            使用 dict 作为返回值，避免领域层依赖 numpy/FlagEmbedding 类型

        Raises:
            ModelInferenceError: 模型推理失败时
        """
        ...

    async def close(self) -> None:
        """释放模型持有的资源（GPU 内存等）"""
        ...
```

### 4.2 `EmbeddingServicePort` — 已有端口不变

**文件位置**：`src/domain/ports/embedding_service.py`（不变）

现有端口不变，保持向后兼容。`EmbeddingServicePort` 是 `ModelInferencePort` 的**高阶语义组合**：
- `embed_query(text)` = `ModelInferencePort.encode([text], return_sparse=False)` → 取 `dense_vecs[0]`
- `embed_documents(texts)` = `ModelInferencePort.encode(texts, return_sparse=False)` → 取 `dense_vecs`
- `embed_sparse(texts)` = `ModelInferencePort.encode(texts, return_sparse=True)` → 取 `lexical_weights`

### 4.3 新增异常定义

**文件位置**：`src/domain/exceptions/embedding_exceptions.py`（新增）

```python
class ModelInferenceError(ExternalException):
    """模型推理错误

    模型推理过程中的通用故障，包括 GPU OOM、模型未加载等。
    继承 ExternalException，HTTP 映射自动回退至 502 Bad Gateway。

    Attributes:
        code: EXCEPTION_309
        message: 模型推理错误描述
    """

    code = "EXCEPTION_309"
    message = "Model inference error"


class ConcurrencyOverloadError(ServiceUnavailableError):
    """并发过载错误

    请求队列已满时拒绝新请求，防止级联超时。
    继承 ServiceUnavailableError，HTTP 映射返回 503 Service Unavailable。

    Attributes:
        code: EXCEPTION_310
        message: 并发过载错误描述
    """

    code = "EXCEPTION_310"
    message = "Concurrency overload, request rejected"
```

---

## 5. 应用层端口定义（R2）

### 5.1 `BatchCoalescerPort` — 请求合并端口（Phase 2）

**文件位置**：`src/application/ports/embedding_concurrency.py`（新增）

```python
"""应用层嵌入并发端口

定义请求合并与动态批处理的抽象契约。
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class BatchCoalescerPort(Protocol):
    """请求合并端口

    将并发请求合并为批量推理，减少模型推理次数。
    适用于客户端侧（EmbeddingAPIClient 上层）或服务端侧（ModelInferenceEngine 上层）。

    典型用法：
    ```
    coalescer = RequestCoalescer(max_batch_size=32, max_wait_ms=50)
    result = await coalescer.execute(text, fn=model.encode)
    ```
    """

    async def execute(
        self,
        text: str,
        *,
        fn: Callable,
        **kwargs,
    ) -> Any:
        """提交单条文本到合并队列，等待批量推理结果

        Args:
            text: 单条文本
            fn: 批量推理函数（接收 list[str] 参数）
            **kwargs: 传递给 fn 的额外参数

        Returns:
            推理结果（单条文本对应的向量）

        Raises:
            ConcurrencyOverloadError: 队列满时
        """
        ...
```

---

## 6. 基础设施层实现（R3）

### 6.1 `SafeBGE3Model` — 线程安全 BGE-M3 模型包装器

**文件位置**：`src/infrastructure/external_services/embedding/safe_model.py`（新增）

#### 6.1.1 设计要点

| 设计决策 | 实现方式 | 对标业界 |
|---------|---------|---------|
| **消除 `model.to(device)` 冗余** | 子类化 `BGEM3FlagModel`，重写 `encode_single_device`，初始化时一次性固定设备 | TorchServe 模型加载时绑定 GPU |
| **消除 `model.eval()` 冗余** | 初始化时设置 `model.eval()`，推理时不再重复 | HuggingFace Pipeline 模式 |
| **消除 `model.half()` 冗余** | 初始化时一次性转换，且不依赖 `use_fp16` 内部属性 | 启动时固定精度 |
| **线程安全** | `threading.Lock` 保护 `encode()` 调用 | NVIDIA Triton 模型实例互斥 |
| **防御性 NaN 净化** | `np.nan_to_num` 剔除 NaN/Inf | 数学上安全的兜底 |

#### 6.1.2 核心实现

```python
"""线程安全 BGE-M3 模型包装器

继承 BGEM3FlagModel 并重写 encode_single_device，
消除每次推理的 model.to(device) + model.eval() + model.half() 冗余操作，
使用 threading.Lock 保护模型推理的线程安全。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np
from FlagEmbedding import BGEM3FlagModel

logger = logging.getLogger(__name__)


class SafeBGE3Model(BGEM3FlagModel):
    """线程安全 BGE-M3 模型

    初始化时一次性固定设备/精度/评估模式，推理时不再重复。
    Threading.Lock 串行化模型推理，防止竞态条件。

    Args:
        model_path: 模型路径或 HuggingFace 模型名称
        use_fp16: 是否使用 fp16 精度
        device: 目标设备（cuda/cpu），None 时自动检测
    """

    def __init__(
        self,
        model_path: str,
        use_fp16: bool = False,
        device: str | None = None,
    ) -> None:
        super().__init__(model_path, use_fp16=use_fp16)

        # 一次性固定设备/精度/评估模式
        if device is None:
            device = self.target_devices[0]
        self._inference_device = device

        if use_fp16:
            self.model.half()
        self.model.to(device)
        self.model.eval()

        # 标记阻止父类 encode_single_device 重复操作
        # 使用 _model_ready 而非 use_fp16 内部属性，避免版本兼容风险
        self._model_ready = True

        # 推理锁
        self._inference_lock = threading.Lock()

        logger.info(
            "SafeBGE3Model 初始化完成: device=%s, fp16=%s, dim=%d",
            device, use_fp16, self.model.config.hidden_size,
        )

    @torch.no_grad()
    def encode_single_device(
        self,
        sentences: list[str],
        batch_size: int = 256,
        max_length: int = 512,
        return_dense: bool = True,
        return_sparse: bool = False,
        return_colbert_vecs: bool = False,
        device: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """线程安全的单设备编码

        重写父类方法，移除以下冗余操作：
        - model.half()（已在初始化时一次性完成）
        - model.to(device)（已在初始化时一次性完成）
        - model.eval()（已在初始化时一次性完成）

        使用 threading.Lock 串行化推理，确保线程安全。

        Args:
            sentences: 输入文本列表
            batch_size: 批次大小
            max_length: 最大 token 长度
            return_dense: 是否返回 Dense 向量
            return_sparse: 是否返回 Sparse 向量
            return_colbert_vecs: 是否返回 ColBERT 向量
            device: 忽略，使用初始化时固定的设备
            **kwargs: 其他参数

        Returns:
            {"dense_vecs": np.ndarray, "lexical_weights": list[dict] | None, ...}
        """
        with self._inference_lock:
            # 直接调用父类的编码逻辑，跳过设备/精度/模式切换
            # 通过 super().encode() 的 kwargs 传递参数，绕过 encode_single_device
            result = super().encode(
                sentences,
                batch_size=batch_size,
                max_length=max_length,
                return_dense=return_dense,
                return_sparse=return_sparse,
                return_colbert_vecs=return_colbert_vecs,
                # 阻止父类内部的 encode_single_device 被调用
                # 而是直接在此处执行编码逻辑
            )
            # 注意：此处需要更精妙的实现来绕过父类 encode() 中的
            # 多设备分发逻辑，参见下方 §6.1.3 详细说明
            return result

    def _sanitize_dense_vectors(
        self,
        dense_vecs: np.ndarray,
    ) -> np.ndarray:
        """防御性净化浮点向量，剔除 NaN/Inf

        Args:
            dense_vecs: 原始模型输出向量

        Returns:
            净化后的向量（不含 NaN/Inf）
        """
        if np.any(np.isnan(dense_vecs)) or np.any(np.isinf(dense_vecs)):
            logger.warning(
                "检测到 NaN/Inf 向量，已自动净化 (shape=%s)",
                dense_vecs.shape,
            )
            return np.nan_to_num(dense_vecs, nan=0.0, posinf=0.0, neginf=0.0)
        return dense_vecs
```

#### 6.1.3 实现注意事项

**关键挑战**：`BGEM3FlagModel.encode()` 内部会调用 `self.encode_single_device()`，而 `SafeBGE3Model` 重写了后者。但 `super().encode()` 调用的是父类的 `encode()`，而父类的 `encode()` 会调用 `self.encode_single_device()`（多态绑定），这会导致调用 `SafeBGE3Model.encode_single_device()`，形成递归。

**解决方案**：有两种可行方案。

**方案 A（推荐）**：完全重写 `encode()` 方法，直接调用 `BGEM3FlagModel` 的内部编码逻辑，绕过 `encode_single_device` 的多设备分发。

```python
def encode(self, sentences, ...):
    """完全重写 encode，绕过父类的多设备分发"""
    # 直接使用单设备推理
    with self._inference_lock:
        result = self._direct_encode(sentences, ...)
        return result

def _direct_encode(self, sentences, ...):
    """直接编码逻辑，拷贝自 encode_single_device 的核心部分"""
    from FlagEmbedding.inference.embedder.encoder_only.m3 import (
        _process_token_weights, _process_colbert_vecs,
    )
    # ... 核心编码逻辑，跳过 model.to(device) / model.eval() / model.half()
```

**方案 B（低侵入）**：使用 `threading.Lock` 保护 `super().encode()` 调用，并确保父类内部的 `encode_single_device` 不会重复执行设备操作。

由于 `_model_ready` 标志位可以阻止 `model.half()` 的重复调用，但 `model.to(device)` 和 `model.eval()` 在父类 `encode_single_device` 中硬编码执行，无法通过标志位跳过。

**推荐采用方案 A**，虽然后续 FlagEmbedding 升级时需要同步更新 `_direct_encode`，但这是唯一能彻底消除 `model.to(device)` 冗余的途径。

### 6.2 `ModelInferenceEngine` — 模型推理引擎

**文件位置**：`src/infrastructure/external_services/embedding/model_inference_engine.py`（新增）

```python
"""模型推理引擎

管理 SafeBGE3Model 生命周期，提供模型加载/卸载/推理的完整管理。
Phase 2 可选集成动态批处理队列。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np

from src.domain.exceptions import (
    EmbeddingModelError,
    ModelInferenceError,
)

logger = logging.getLogger(__name__)


class ModelInferenceEngine:
    """模型推理引擎

    管理模型加载、推理、卸载的完整生命周期。
    支持动态批处理队列（Phase 2 启用）。

    Args:
        model_path: BGE-M3 模型路径
        device: 推理设备（cuda/cpu）
        use_fp16: 是否使用 fp16 精度
        enable_batching: 是否启用动态批处理（Phase 2）
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        use_fp16: bool = False,
        enable_batching: bool = False,
    ) -> None:
        self._model_path = model_path
        self._device = device
        self._use_fp16 = use_fp16
        self._enable_batching = enable_batching
        self._model: SafeBGE3Model | None = None
        self._load_error: str | None = None

    def load(self) -> None:
        """加载模型（幂等，可多次调用）

        加载失败时设置 _load_error，不抛出异常。
        健康检查通过 _load_error 感知加载状态。
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
        """模型是否已加载并可推理"""
        return self._model is not None and self._load_error is None

    @property
    def load_error(self) -> str | None:
        """模型加载错误信息"""
        return self._load_error

    @property
    def dimension(self) -> int:
        """模型输出维度"""
        return 1024  # bge-m3 固定

    def encode(
        self,
        texts: list[str],
        return_sparse: bool = False,
    ) -> dict:
        """模型推理入口

        Args:
            texts: 待编码文本列表
            return_sparse: 是否返回稀疏词汇权重

        Returns:
            {"dense": [...], "sparse": [...] | None}

        Raises:
            ModelInferenceError: 模型未加载或推理失败时
        """
        if not self.is_ready:
            raise ModelInferenceError(
                f"模型未加载: {self._load_error or '未知错误'}",
            )

        try:
            result = self._model.encode(
                texts,
                return_dense=True,
                return_sparse=return_sparse,
            )
        except Exception as e:
            raise ModelInferenceError(f"模型推理失败: {e}", cause=e) from e

        dense_vecs = result.get("dense_vecs")
        if dense_vecs is None:
            raise ModelInferenceError("模型输出缺少 'dense_vecs' 字段")

        # 防御性 NaN 净化
        if isinstance(dense_vecs, np.ndarray):
            dense_vecs = self._sanitize_dense_vectors(dense_vecs)

        response: dict = {"dense": dense_vecs.tolist()}

        if return_sparse:
            lexical_weights = result.get("lexical_weights", [])
            response["sparse"] = self._parse_sparse_weights(lexical_weights)
        else:
            response["sparse"] = None

        return response

    def _sanitize_dense_vectors(
        self,
        dense_vecs: np.ndarray,
    ) -> np.ndarray:
        """防御性净化浮点向量"""
        if np.any(np.isnan(dense_vecs)) or np.any(np.isinf(dense_vecs)):
            logger.warning(
                "检测到 NaN/Inf 向量，已自动净化 (shape=%s)",
                dense_vecs.shape,
            )
            return np.nan_to_num(dense_vecs, nan=0.0, posinf=0.0, neginf=0.0)
        return dense_vecs

    def _parse_sparse_weights(
        self,
        lexical_weights: list[dict],
    ) -> list[dict]:
        """解析稀疏词汇权重为 API 响应格式"""
        sparse_list: list[dict] = []
        for w in lexical_weights:
            sorted_items: list[tuple[int, float]] = []
            for k, v in w.items():
                try:
                    sorted_items.append((int(k), float(v)))
                except (ValueError, TypeError):
                    logger.warning("跳过非法 token ID: %s", k)
            sorted_items.sort(key=lambda x: x[0])
            sparse_list.append(
                {
                    "indices": [idx for idx, _ in sorted_items],
                    "values": [val for _, val in sorted_items],
                }
            )
        return sparse_list

    def unload(self) -> None:
        """卸载模型，释放 GPU 资源"""
        if self._model is not None:
            del self._model
            self._model = None
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            logger.info("模型已卸载，GPU 缓存已释放")
```

### 6.3 `RequestCoalescer` — 请求合并器（Phase 2）

**文件位置**：`src/infrastructure/external_services/embedding/request_coalescer.py`（新增）

```python
"""请求合并器

将高并发单文本请求合并为批量请求，充分利用 GPU 批处理能力。
实现 BatchCoalescerPort 应用层端口。

设计参考：TorchServe 的 dynamic batching 机制。
- 积累窗口期内的请求，达到 max_batch_size 或 max_wait_ms 时触发推理
- 使用 asyncio.Event 通知等待的请求
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from src.domain.exceptions import ConcurrencyOverloadError

logger = logging.getLogger(__name__)


class _PendingRequest:
    """单个待处理请求"""

    def __init__(self, text: str, index: int) -> None:
        self.text = text
        self.index = index
        self.event = asyncio.Event()
        self.result: Any = None
        self.error: Exception | None = None


class RequestCoalescer:
    """请求合并器

    将并发单文本请求合并为批量推理，减少模型推理次数。

    Args:
        max_batch_size: 最大批次大小，达到后立即触发推理
        max_wait_ms: 最大等待毫秒数，超时后触发推理
        max_queue_size: 最大队列深度，超限时拒绝新请求
    """

    def __init__(
        self,
        max_batch_size: int = 32,
        max_wait_ms: int = 50,
        max_queue_size: int = 256,
    ) -> None:
        self._max_batch_size = max_batch_size
        self._max_wait_ms = max_wait_ms
        self._max_queue_size = max_queue_size
        self._pending: list[_PendingRequest] = []
        self._lock = asyncio.Lock()
        self._active = False

    async def execute(
        self,
        text: str,
        *,
        fn: Callable[[list[str]], Awaitable[Any]],
    ) -> Any:
        """提交单条文本到合并队列，等待批量推理结果

        Args:
            text: 单条文本
            fn: 批量推理异步函数

        Returns:
            推理结果

        Raises:
            ConcurrencyOverloadError: 队列满时
        """
        async with self._lock:
            if len(self._pending) >= self._max_queue_size:
                raise ConcurrencyOverloadError(
                    f"请求队列已满 ({self._max_queue_size})，请稍后重试",
                )

            index = len(self._pending)
            req = _PendingRequest(text, index)
            self._pending.append(req)

            if len(self._pending) >= self._max_batch_size:
                await self._flush(fn)

        # 等待结果
        await req.event.wait()
        if req.error:
            raise req.error
        return req.result

    async def _flush(self, fn: Callable[[list[str]], Awaitable[Any]]) -> None:
        """处理当前队列中的所有请求"""
        batch = list(self._pending)
        self._pending = []
        self._active = True

        try:
            texts = [req.text for req in batch]
            results = await fn(texts)

            # 将批量结果分发到各请求
            for req in batch:
                if req.index < len(results):
                    req.result = results[req.index]
                else:
                    req.error = IndexError(
                        f"批量结果数({len(results)})不匹配请求索引({req.index})",
                    )
                req.event.set()
        except Exception as e:
            for req in batch:
                req.error = e
                req.event.set()
        finally:
            self._active = False

    async def _timer_tick(self) -> None:
        """定时器：超时触发未满批的推理"""
        while True:
            await asyncio.sleep(self._max_wait_ms / 1000.0)
            async with self._lock:
                if self._pending and not self._active:
                    await self._flush(...)
```

### 6.4 `EmbeddingAPIClient` — 已有客户端（不变）

**文件位置**：`src/infrastructure/external_services/embedding/embedding_api_client.py`（不变）

已有 `EmbeddingAPIClient` 实现 `EmbeddingServicePort`，其 `CircuitBreaker` + `retry` 机制保持不变。客户端无需感知服务端的并发保护细节。

---

## 7. 接口层适配（R4）

### 7.1 `embedding_api_server` 重构

**文件位置**：`src/infrastructure/external_services/embedding/embedding_api_server.py`（重构）

```python
"""BGE-M3 嵌入 API 服务端

通过 FastAPI + ModelInferenceEngine 将 BGE-M3 封装为独立 HTTP 服务。
Docker Compose 独立部署，通过 POST /v1/embeddings 提供 Dense/Sparse 编码。

架构变更：
- v1.0: 直接使用 BGEM3FlagModel（无锁，有竞态条件）
- v1.1: 使用 _embed_lock + _sanitize_dense_vectors（线程安全锁）
- v2.0: 使用 ModelInferenceEngine + SafeBGE3Model（重构版，消除冗余操作）
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


def _detect_device() -> tuple[str, bool]:
    """检测可用设备并返回设备名称和 fp16 标志"""
    requested_device = os.getenv("EMBEDDING_MODEL_DEVICE", "cuda")
    if requested_device == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", True
        except ImportError:
            pass
    return "cpu", False


def _validate_model_path(path: str) -> bool:
    """验证模型路径是否包含有效的模型文件"""
    if not path or not os.path.isdir(path):
        return False
    has_config = os.path.isfile(os.path.join(path, "config.json"))
    has_weights = any(
        os.path.isfile(os.path.join(path, f))
        for f in ["pytorch_model.bin", "model.safetensors"]
    )
    return has_config and has_weights


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan 上下文管理器"""
    global _engine

    model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    local_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    device, use_fp16 = _detect_device()

    load_path = local_path if _validate_model_path(local_path) else model_name

    _engine = ModelInferenceEngine(
        model_path=load_path,
        device=device,
        use_fp16=use_fp16,
        enable_batching=False,  # Phase 2 启用
    )
    _engine.load()

    yield

    # 卸载
    if _engine is not None:
        _engine.unload()
        _engine = None


app = FastAPI(title="SISYS Embedding API", version="2.0.0", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    return_sparse: bool = Field(False)


class EmbedResponse(BaseModel):
    dense: list[list[float]]
    sparse: list[dict] | None = None


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    error: str | None = None


@app.get("/health", response_model=HealthResponse)
async def health() -> dict:
    """健康检查端点"""
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
            "error": _engine.load_error if _engine else "Engine not initialized",
        },
    )


@app.post("/v1/embeddings", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> dict:
    """嵌入编码端点

    使用同步 def（非 async），FastAPI 自动在线程池中执行。
    线程安全由 SafeBGE3Model._inference_lock 保证。
    """
    global _engine

    if _engine is None or not _engine.is_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Embedding model not available: "
                f"{_engine.load_error if _engine else 'Not initialized'}"
            ),
        )

    return _engine.encode(req.texts, return_sparse=req.return_sparse)
```

### 7.2 重构前后对比

| 维度 | 重构前 | 重构后 |
|------|-------|--------|
| **模型管理** | `app.state.model` 直接持有 | `ModelInferenceEngine` 封装 |
| **线程安全** | ❌ 无锁（或 `_embed_lock` 锁） | ✅ `SafeBGE3Model._inference_lock` |
| **冗余设备拷贝** | 🔴 每次推理 `model.to(device)` | ✅ 初始化时一次性固定 |
| **防御性净化** | ✅ `_sanitize_dense_vectors` | ✅ 移入 `ModelInferenceEngine` |
| **生命周期** | `load_model()` 函数级 | ✅ `ModelInferenceEngine.load()/unload()` |
| **可测试性** | ❌ 直接依赖 BGEM3FlagModel | ✅ 可通过 `ModelInferencePort` mock |
| **扩展性** | ❌ 硬编码 BGE-M3 | ✅ 可替换为其他模型 |

---

## 8. 异常体系与错误处理（R5）

### 8.1 异常层次

```
BaseException (抽象根)
├── ExternalException (外部服务)
│   ├── EmbeddingAPIError (EXCEPTION_306) — HTTP 传输层错误
│   ├── EmbeddingResponseError (EXCEPTION_307) — 响应格式错误
│   ├── EmbeddingModelError (EXCEPTION_308) — 模型运行时错误
│   └── ModelInferenceError (EXCEPTION_309) — 模型推理失败
├── ServiceUnavailableError (业务异常)
│   └── ConcurrencyOverloadError (EXCEPTION_310) — 并发过载
```

### 8.2 异常映射

| 异常 | 触发条件 | HTTP 状态码 | 是否可重试 |
|------|---------|------------|-----------|
| `ModelInferenceError` | 模型未加载/推理失败 | 503 | ✅ 是（等待后） |
| `ConcurrencyOverloadError` | 请求队列满 | 503 | ✅ 是（指数退避） |
| `EmbeddingAPIError` | HTTP 4xx/5xx | 502 | ✅ 是（仅 5xx） |
| `EmbeddingResponseError` | 响应格式异常 | 502 | ❌ 否（客户端问题） |
| `EmbeddingModelError` | 模型输出键缺失 | 500 | ❌ 否（需修复） |

### 8.3 服务端错误处理流程

```
POST /v1/embeddings
    │
    ├─→ ModelInferenceEngine.encode()
    │   ├── 模型未加载 → HTTP 503 + ModelInferenceError
    │   ├── 推理失败    → HTTP 500 + ModelInferenceError
    │   └── 成功        → HTTP 200 + {"dense": [...], "sparse": ...}
    │
    ├─→ 防御性 NaN 净化（最后一道防线）
    │   └── NaN/Inf → 0.0（日志警告）
    │
    └─→ JSON 序列化
        └── 失败 → HTTP 500（罕见，仅当 NaN 净化遗漏时）
```

---

## 9. 性能基线对比

### 9.1 预期提升

| 场景 | 当前（锁串行） | Phase 1（SafeBGE3Model） | Phase 2（+动态批处理） |
|------|--------------|------------------------|---------------------|
| **单文本 P50** | 25.4ms | **~15ms**（-40%，消除 `model.to(device)`） | ~15ms |
| **批量 32 文本** | 41.7ms | **~35ms**（-16%，消除 `model.to(device)`） | ~35ms |
| **16 并发单文本** | 1120.8ms | **~560ms**（-50%，消除 `model.to(device)`） | **~50ms**（合并为 1 批） |
| **吞吐量** | ~40 req/s | ~70 req/s | ~800 req/s |

### 9.2 验证指标

| 指标 | Phase 1 目标 | Phase 2 目标 |
|------|-------------|-------------|
| 并发 32 请求下向量退化 | 0（零退化） | 0（零退化） |
| 单文本延迟 P50 | <20ms | <20ms |
| 批量 32 文本延迟 P50 | <40ms | <40ms |
| 16 并发总耗时 | <600ms | <60ms |

---

## 10. 实施路线图

### Phase 1：SafeBGE3Model + ModelInferenceEngine（1-2 天）

| 任务 | 产出 | 验证 |
|------|------|------|
| 1.1 新增 `ModelInferencePort` 领域端口 | `src/domain/ports/model_inference.py` | 契约测试 |
| 1.2 新增 `SafeBGE3Model` 基础设施实现 | `src/infrastructure/external_services/embedding/safe_model.py` | 单元测试 |
| 1.3 新增 `ModelInferenceEngine` | `src/infrastructure/external_services/embedding/model_inference_engine.py` | 单元测试 |
| 1.4 重构 `embedding_api_server.py` | 使用 `ModelInferenceEngine` 替代直接调用 | 集成测试 |
| 1.5 新增异常定义 | `embedding_exceptions.py` 增加 `ModelInferenceError`/`ConcurrencyOverloadError` | 异常测试 |
| 1.6 重建 Docker 镜像 | 新镜像包含 SafeBGE3Model | 全量集成测试 PASS |

### Phase 2：动态批处理（1-2 周）

| 任务 | 产出 | 验证 |
|------|------|------|
| 2.1 新增 `BatchCoalescerPort` 应用层端口 | `src/application/ports/embedding_concurrency.py` | 契约测试 |
| 2.2 实现 `RequestCoalescer` | `src/infrastructure/external_services/embedding/request_coalescer.py` | 单元测试 |
| 2.3 集成到 `ModelInferenceEngine` | 可选启用批处理 | 压力测试 |
| 2.4 性能基准测试 | 对比锁串行 vs 动态批处理 | 吞吐量 ≥ 800 req/s |

### Phase 3：多 Worker 安全（按需）

| 任务 | 说明 |
|------|------|
| 3.1 多 GPU 分配策略 | `CUDA_VISIBLE_DEVICES` 环境变量绑定 |
| 3.2 进程级锁（可选） | 文件锁或共享内存锁，防止多 worker 冲突 |
| 3.3 部署指南更新 | 文档说明多 worker + 多 GPU 配置 |

---

## 11. 附录：FlagEmbedding encode_single_device 源码分析

### 11.1 关键代码路径

```python
@torch.no_grad()
def encode_single_device(self, sentences, ...):
    # ...
    if device is None:
        device = self.target_devices[0]

    if device == "cpu": self.use_fp16 = False
    if self.use_fp16: self.model.half()        # ← ① 精度转换，非线程安全

    self.model.to(device)                       # ← ② 设备拷贝，非线程安全，2.2GB
    self.model.eval()                           # ← ③ 评估模式，非线程安全

    # ... tokenizer.encode ... forward ...
    # ... 实际的推理代码 ...
```

### 11.2 竞态条件分析

| 操作 | 线程安全 | 风险 | 修复方式 |
|------|---------|------|---------|
| `self.model.half()` | ❌ | 精度转换中 model 参数被修改 | 启动时一次性执行，标记跳过 |
| `self.model.to(device)` | ❌ | 2.2GB 参数正在拷贝时被中断 | 启动时一次性执行，消除冗余调用 |
| `self.model.eval()` | ❌ | 与 train() 模式竞争 | 启动时一次性执行 |
| `model.encode()` forward pass | ❌ | GPU kernel 并行冲突 | `threading.Lock` 串行化 |

### 11.3 版本兼容性说明

`SafeBGE3Model` 对 FlagEmbedding 的依赖：

| 内部 API | 使用方式 | 版本风险 |
|---------|---------|---------|
| `BGEM3FlagModel.__init__` | 标准继承 | ✅ 低（公开 API） |
| `BGEM3FlagModel.encode` | 重写/绕过 | 🟡 中（需同步 FlagEmbedding 更新） |
| `self.target_devices` | 读取 | 🟡 中（内部属性，但稳定） |
| `self.model` | 读取（HuggingFace 模型） | ✅ 低（标准 HuggingFace API） |
| `self.use_fp16` | ❌ 不再使用 | ✅ 已通过 `_model_ready` 替代 |
