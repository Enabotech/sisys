"""DocLayNet 文档版面检测技术调研报告

针对 SISYS 项目 Epic 2 Story 2.3 文档版面信息保留需求，调研 DocLayNet 模型及相关替代方案，
涵盖模型架构、ONNX 推理、许可证合规、中文支持等维度，给出 MVP 推荐方案及六边形架构集成策略。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

# DocLayNet 文档版面检测技术调研报告

> 文档版本：1.0.0
> 创建日期：2026-05-25
> 最后更新：2026-05-25
> 关联 Epic：Epic 2 — 文档上传与解析
> 关联 Story：Story 2.3 — 文档版面信息保留
> 状态：待评审

---

## 1. 背景与目标

SISYS Epic 2 Story 2.3 要求在文档解析过程中保留版面信息（元素坐标 x, y, width, height），
采用 DocLayNet 标准格式输出。需要支持 ONNX 格式实现跨平台推理，便于在不同部署环境中运行。

### 1.1 需求分析

| 需求项 | 说明 |
|--------|------|
| 版面元素坐标 | 输出 bounding box（x, y, width, height），格式对齐 DocLayNet 标准 |
| ONNX 推理 | 模型需可导出为 ONNX 格式，使用 onnxruntime 跨平台推理 |
| 六边形架构 | 模型推理逻辑封装在 infrastructure 层，domain 层定义版面元素端口接口 |
| 许可证合规 | SISYS 为企业商业软件，需避免 AGPL 等 copyleft 限制 |
| 中文支持 | 企业文档以中文为主，需支持中文版面分析 |

### 1.2 调研范围

1. DocLayNet 模型及其衍生模型（Docling Layout、DocLayout-YOLO）
2. ONNX 推理方案及性能
3. 替代方案（PaddleOCR PP-Structure、Unstructured.io、DocTR）
4. MVP 推荐方案与架构集成策略

---

## 2. DocLayNet 数据集概述

### 2.1 基本信息

| 属性 | 详情 |
|------|------|
| 发布方 | IBM Research（Deep Search 团队，现 DS4SD / docling-project） |
| 论文 | DocLayNet: A Large Human-Annotated Dataset for Document-Layout Analysis (KDD 2022) |
| 数据规模 | 80,863 页人工标注文档 |
| 标注格式 | COCO 格式（bounding box + polygon segmentation mask） |
| 数据集许可证 | CDLA-Permissive-1.0（社区数据许可协议，允许商业使用） |
| 论文许可证 | CC-BY 4.0 |

### 2.2 版面元素类型（11 类）

DocLayNet 定义了 11 种标准版面元素类型：

| 编号 | 类别名 | 说明 |
|------|--------|------|
| 1 | Caption | 图表说明文字 |
| 2 | Footnote | 页脚注释 |
| 3 | Formula | 数学公式 |
| 4 | List-item | 列表项（有序/无序） |
| 5 | Page-footer | 页脚区域 |
| 6 | Page-header | 页眉区域 |
| 7 | Picture | 图片/插图 |
| 8 | Section-header | 章节标题 |
| 9 | Table | 表格 |
| 10 | Text | 正文段落 |
| 11 | Title | 文档/页面标题 |

### 2.3 文档覆盖范围

DocLayNet 数据集涵盖 6 大文档领域，每个领域来源不同：

| 领域 | 来源示例 |
|------|----------|
| Financial Reports | 年报、季报、财报 |
| Government Reports | 政府公文、法规文件 |
| Law | 法律文书、合同 |
| Patent | 专利文档 |
| Science | 学术论文 |
| Manual | 技术手册、操作指南 |

---

## 3. DocLayNet 模型生态

DocLayNet 是一个数据集（dataset），而非单一模型。基于该数据集训练的模型有多个，以下按架构分类。

### 3.1 Docling Layout（IBM DS4SD 官方）

IBM Docling 项目提供的版面检测模型，是 DocLayNet 生态的官方继承者。

| 属性 | 详情 |
|------|------|
| 项目地址 | https://github.com/docling-project/docling |
| 当前默认模型 | docling-layout-heron |
| 架构 | RT-DETR（Real-Time DEtection TRansformer） |
| HuggingFace（PyTorch） | https://huggingface.co/docling-project/docling-layout-heron |
| HuggingFace（ONNX） | https://huggingface.co/docling-project/docling-layout-heron-onnx |
| 许可证 | MIT（代码），模型许可证需参考原始包 |
| 安装方式 | `pip install docling` |
| 输出格式 | JSON，包含 bounding box 坐标 |

**模型变体与性能**（来源：arXiv:2509.11720 "Advanced Layout Analysis Models for Docling"）：

| 模型 | mAP | 相对基线提升 | 推理速度（A100） |
|------|-----|-------------|-----------------|
| heron（默认） | ~74%+ | +20.6% | ~28 ms/页 |
| heron-101（最佳） | 78% | +23.9% | ~28 ms/页 |

**架构细节（RT-DETR）**：

- **Backbone**：ResNet 系列（R18/R34/R50/R101，按模型规模选择）
- **Encoder**：高效混合编码器，解耦尺度内交互和跨尺度融合
- **Decoder**：Transformer 解码器
- **Head**：FFN 直接预测，内置可学习 NMS（无需传统 NMS 后处理）
- **特点**：首个基于 DETR 的实时端到端目标检测器

**ONNX 模型文件大小**：RT-DETR 模型导出 ONNX 后，典型大小范围为 ~30 MB（R18）到 ~200+ MB（R101）。

### 3.2 DocLayout-YOLO（OpenDataLab）

基于 Ultralytics YOLO-v10 构建的实时文档版面检测模型。

| 属性 | 详情 |
|------|------|
| 项目地址 | https://github.com/opendatalab/DocLayout-YOLO |
| 架构 | YOLO-v10 |
| 许可证 | AGPL-3.0（Ultralytics 框架强制），商业使用需购买 Enterprise License |
| 安装方式 | `pip install doclayout-yolo` |
| 训练数据 | DocStructBench（包含 DocLayNet）+ DocSynth300K 合成数据 |

**性能基准**：

| 训练集 | DocSynth300K 预训练 | imgsz | AP50 | mAP |
|--------|-------------------|-------|------|-----|
| D4LA | 否 | 1600 | 81.7 | 69.8 |
| D4LA | 是 | 1600 | 82.4 | 70.3 |
| DocLayNet | 否 | 1120 | 93.0 | 77.7 |
| DocLayNet | 是 | 1120 | 93.4 | 79.7 |

**ONNX 导出**：

```python
from doclayout_yolo import YOLOv10

model = YOLOv10("doclayout_yolo_docstructbench_imgsz1024.pt")
model.export(format="onnx")
# 导出后推理速度可提升最多 43%
```

HuggingFace 上有社区预导出的 ONNX 版本：
https://huggingface.co/wybxc/DocLayout-YOLO-DocStructBench-onnx

**许可证风险**：

DocLayout-YOLO 基于 Ultralytics 框架，受 AGPL-3.0 许可证约束。AGPL 要求：
- 衍生作品必须以相同许可证开源
- 网络服务使用也需开源
- 商业闭源部署需购买 Ultralytics Enterprise License

**结论：SISYS 作为企业商业软件，直接使用 DocLayout-YOLO 存在许可证合规风险，不建议作为首选方案。**

---

## 4. ONNX 推理方案

### 4.1 onnxruntime Python SDK

onnxruntime 是 Microsoft 维护的高性能推理引擎，支持 CPU 和 GPU 推理。

**安装**：

```bash
# CPU 版本
pip install onnxruntime

# GPU 版本（需要 CUDA 12.x）
pip install onnxruntime-gpu
```

**基本推理代码**：

```python
import onnxruntime as ort
import numpy as np

# 创建推理会话（CPU）
session = ort.InferenceSession(
    "docling-layout-heron.onnx",
    providers=["CPUExecutionProvider"]
)

# 创建推理会话（GPU）
session_gpu = ort.InferenceSession(
    "docling-layout-heron.onnx",
    providers=["CUDAExecutionProvider"]
)

# 执行推理
inputs = {"images": preprocessed_image}  # numpy array
outputs = session.run(None, inputs)
# outputs: bounding boxes + class labels + confidence scores
```

### 4.2 GPU vs CPU 推理性能

| 执行提供者 | 硬件要求 | 典型推理速度 | 适用场景 |
|-----------|----------|-------------|----------|
| CPUExecutionProvider | 无特殊要求 | ~100-200 ms/页 | 开发测试、低吞吐量场景 |
| CUDAExecutionProvider | NVIDIA GPU + CUDA 12.x | ~20-30 ms/页 | 生产环境、高吞吐量 |

**性能优化建议**：

- GPU 推理最常见的瓶颈是 CPU-GPU 数据传输，应尽量批量处理
- ONNX 模型可利用图优化（graph optimization）进一步加速
- onnxruntime 1.17+ 对 Transformer 类模型有专项优化

### 4.3 Docling Layout ONNX 方案

Docling 项目已提供预导出的 ONNX 模型（docling-layout-heron-onnx），无需手动转换：

- **ONNX 模型地址**：https://huggingface.co/docling-project/docling-layout-heron-onnx
- **下载量**：每月 2,680+ 次
- **文件大小**：根据 RT-DETR backbone 不同，估计 30-200 MB 范围
- **输入**：预处理后的文档页面图像（numpy array）
- **输出**：bounding boxes + class labels + confidence scores

---

## 5. 替代方案对比

### 5.1 综合对比表

| 维度 | Docling Layout (RT-DETR) | DocLayout-YOLO | PaddleOCR PP-Structure | Unstructured.io | DocTR |
|------|--------------------------|----------------|------------------------|-----------------|-------|
| **架构** | RT-DETR | YOLO-v10 | PP-DocLayoutV3 (PaddlePaddle) | 混合（OCR + Transformer） | PyTorch 深度学习 |
| **中文支持** | 良好（DocLayNet 含中文文档） | 良好 | **最佳**（百度出品，中文原生支持） | 基础（依赖 OCR 引擎） | 基础（依赖检测模型） |
| **ONNX 支持** | **原生支持**（官方提供 ONNX 导出） | 支持（Ultralytics 导出） | **部分支持**（V2 不支持 ONNX 导出） | 有限 | 支持（通过 onnxtr） |
| **许可证** | **MIT**（代码） | **AGPL-3.0**（Ultralytics） | Apache-2.0 | Apache-2.0 | **Apache-2.0** |
| **安装复杂度** | 低（`pip install docling`） | 低（`pip install doclayout-yolo`） | **高**（依赖 PaddlePaddle 框架） | 中（多种依赖可选） | 低（`pip install python-doctr`） |
| **模型大小** | 30-200 MB | 20-100 MB | 50-150 MB | 100+ MB（多模型） | 50-100 MB |
| **版面元素类型** | 11 类（DocLayNet 标准） | 11 类（DocLayNet 标准） | **23 类**（PP-DocLayout 最丰富） | 可变（依赖分区策略） | 基础（文本区域为主） |
| **成熟度** | 高（IBM/LF AI 项目） | 中（学术界项目） | 高（百度工业级） | 高（商业化运营） | 中（Mindee/PyTorch 生态） |
| **维护活跃度** | 活跃（docling-project） | 活跃（opendatalab） | **最活跃**（PaddlePaddle 主力项目） | 活跃（Unstructured-IO） | 活跃（PyTorch 生态） |

### 5.2 各方案详细分析

#### 5.2.1 PaddleOCR PP-Structure

**优势**：
- 中文支持最佳，PaddlePaddle 是百度主导的深度学习框架，中文文档处理能力强
- PP-DocLayoutV3 支持 23 种版面元素类型，覆盖面最广
- Apache-2.0 许可证，商业使用无风险
- PaddleOCR 3.0 技术报告（arXiv:2507.05595）详细展示了 PP-StructureV3 的改进

**劣势**：
- ONNX 支持不完整：PP-DocLayoutV2 目前不支持 ONNX 转换（社区讨论确认）
- 依赖 PaddlePaddle 框架，安装和部署复杂度高（尤其 GPU 版本）
- Python 3.11+ 兼容性需验证（PaddlePaddle 对新 Python 版本支持常滞后）
- 与 SISYS 现有技术栈（无 PaddlePaddle 依赖）不一致

**许可证**：Apache-2.0，商业友好。

#### 5.2.2 Unstructured.io

**优势**：
- 支持 60+ 种文件格式，覆盖面广
- Apache-2.0 许可证（开源核心库）
- 提供分区策略（by_title 等）实现版面分析
- 商业化运营（有 SaaS 平台和企业支持）

**劣势**：
- 版面检测能力依赖内部多个模型的组合，不够专精
- 非轻量级解决方案，依赖链较长
- 开源版本功能受限，高级功能需要付费平台
- ONNX 导出支持有限
- 定位更偏向"文档 ETL"而非"版面检测"

**许可证**：Apache-2.0（开源核心库），SaaS 平台有商业定价。

#### 5.2.3 DocTR（Mindee）

**优势**：
- Apache-2.0 许可证，PyTorch 生态官方成员
- ONNX 支持通过 onnxtr（PyPI 包）实现，与 docTR 保持同步
- 端到端 OCR 流水线（检测 + 识别）
- 安装简单（`pip install python-doctr`）

**劣势**：
- 版面分析能力相对基础，主要聚焦于文本区域检测
- 不直接输出 DocLayNet 标准的 11 类版面元素
- 需要额外开发才能满足"版面元素类型分类"需求
- 对复杂版面（表格、图片混排）的处理能力有限

**许可证**：Apache-2.0，商业友好。

#### 5.2.4 DocLayout-YOLO

**优势**：
- 实时推理速度最快（YOLO 架构优势）
- DocLayNet 基准测试 mAP 达到 79.7%（预训练后）
- HuggingFace 模型下载便捷
- 社区活跃，ONNX 导出有预构建版本

**劣势**：
- **AGPL-3.0 许可证**：Ultralytics 框架强制 AGPL，商业闭源使用需购买 Enterprise License
- 这是 SISYS 作为企业商业软件的主要合规障碍
- 商业许可证费用需联系 Ultralytics 获取报价

**许可证**：AGPL-3.0（开源使用），Enterprise License（商业闭源使用，需付费）。

---

## 6. MVP 推荐方案

### 6.1 首选方案：Docling Layout（RT-DETR）+ ONNX Runtime

**推荐理由**：

1. **许可证合规**：Docling 代码 MIT 许可，模型由 docling-project（IBM/LF AI）维护，无 AGPL 风险
2. **原生 ONNX 支持**：官方提供预导出的 ONNX 模型（docling-layout-heron-onnx），无需手动转换
3. **DocLayNet 标准**：直接输出 DocLayNet 11 类版面元素，与 Story 2.3 需求完全对齐
4. **架构契合**：MIT 许可 + onnxruntime 轻量依赖，符合 SISYS 六边形架构 domain 层零依赖原则
5. **成熟度高**：IBM/LF AI 基金会项目，有长期维护保障
6. **部署简单**：`pip install onnxruntime` 即可推理，无需 PaddlePaddle/Ultralytics 等重框架

**MVP 实施路径**：

```
阶段 1：基础集成（Story 2.3）
├── domain 层：定义 LayoutElement 值对象 + LayoutDetector 端口接口
├── infrastructure 层：实现 OnnxLayoutDetector（onnxruntime 推理）
├── 模型文件：下载 docling-layout-heron-onnx，放入 MinIO 模型仓库
└── 输出格式：DocLayNet 标准 11 类 bounding box

阶段 2：性能优化（后续迭代）
├── GPU 推理支持（CUDAExecutionProvider）
├── 批量页面处理（多页并行推理）
└── 模型缓存与预热（减少首次推理延迟）
```

### 6.2 备选方案

如果 Docling Layout ONNX 在实际测试中效果不佳，可按以下优先级降级：

| 优先级 | 方案 | 切换条件 |
|--------|------|----------|
| 1（首选） | Docling Layout ONNX | 默认方案 |
| 2 | DocTR + onnxtr | 若版面分类精度不足，用 DocTR 的检测能力补充 |
| 3 | PaddleOCR PP-Structure | 若中文文档效果不佳，且能接受 PaddlePaddle 依赖 |

### 6.3 六边形架构集成策略

#### 端口接口设计（domain 层）

```python
# src/domain/document_layout/ports.py

class LayoutDetector(Protocol):
    """文档版面检测端口接口

    定义文档版面元素检测的抽象接口，所有实现必须在 infrastructure 层。
    ONNX 推理逻辑不泄漏到 domain 层。
    """

    def detect(self, page_image: bytes, page_number: int) -> list[LayoutElement]:
        """检测文档页面中的版面元素

        Args:
            page_image: 页面图像的二进制数据（PNG/JPEG）
            page_number: 页码（从 1 开始）

        Returns:
            检测到的版面元素列表
        """
        ...
```

#### 值对象设计（domain 层）

```python
# src/domain/document_layout/entities.py

@dataclass(frozen=True)
class BoundingBox:
    """边界框值对象，对齐 DocLayNet 标准格式

    Attributes:
        x: 左上角 x 坐标（像素）
        y: 左上角 y 坐标（像素）
        width: 宽度（像素）
        height: 高度（像素）
    """
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class LayoutElement:
    """版面元素值对象

    Attributes:
        label: DocLayNet 标准类别名（如 Text, Table, Picture 等）
        bbox: 边界框
        confidence: 检测置信度 [0, 1]
        page_number: 所在页码
    """
    label: str  # DocLayNet 11 类之一
    bbox: BoundingBox
    confidence: float
    page_number: int
```

#### 实现类设计（infrastructure 层）

```python
# src/infrastructure/document_layout/onnx_layout_detector.py

class OnnxLayoutDetector:
    """基于 onnxruntime 的版面检测实现

    使用 Docling Layout ONNX 模型（docling-layout-heron-onnx）进行推理。

    Note:
        模型文件在初始化时从 MinIO 模型仓库下载到本地缓存。
    """

    def __init__(self, model_path: str, device: str = "cpu") -> None:
        """初始化 ONNX 推理会话

        Args:
            model_path: ONNX 模型文件路径
            device: 推理设备，"cpu" 或 "cuda"
        """
        provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
        self._session = ort.InferenceSession(model_path, providers=[provider])
```

#### 端口注册（composition_root.py）

```python
# 在 PortSpec 中注册，支持 SINGLETON 生命周期
PortSpec(
    name="layout_detector",
    interface=LayoutDetector,
    impl="infrastructure.document_layout.onnx_layout_detector.OnnxLayoutDetector",
    lifetime="SINGLETON",
)
```

---

## 7. 关键风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Docling Layout ONNX 模型文件较大（可能 100+ MB） | 部署包体积增大 | 模型文件独立存储在 MinIO，按需下载 |
| RT-DETR 推理速度在 CPU 上较慢（~100-200 ms/页） | 大文档处理耗时 | 生产环境使用 GPU 推理；支持异步批量处理 |
| DocLayNet 标签体系不包含某些中文特有版面元素 | 中文文档版面分类不够精细 | 后续迭代考虑 PP-DocLayout 的 23 类体系 |
| onnxruntime 版本兼容性 | 模型无法加载 | 锁定 onnxruntime 版本，CI 中验证兼容性 |
| Docling 项目模型更新迭代 | 模型 API 变化 | 使用稳定版本号，不追踪最新版 |

---

## 8. 参考资料

| 资源 | 链接 |
|------|------|
| DocLayNet 论文 | https://arxiv.org/abs/2206.01062 |
| DocLayNet 数据集（HuggingFace） | https://huggingface.co/datasets/docling-project/DocLayNet |
| Docling 项目（GitHub） | https://github.com/docling-project/docling |
| Docling Layout Heron 模型 | https://huggingface.co/docling-project/docling-layout-heron |
| Docling Layout Heron ONNX | https://huggingface.co/docling-project/docling-layout-heron-onnx |
| Docling 高级版面分析论文 | https://arxiv.org/abs/2509.11720 |
| DocLayout-YOLO（GitHub） | https://github.com/opendatalab/DocLayout-YOLO |
| PaddleOCR（GitHub） | https://github.com/PaddlePaddle/PaddleOCR |
| PP-DocLayout 论文 | https://arxiv.org/abs/2503.17213 |
| Unstructured.io（GitHub） | https://github.com/Unstructured-IO/unstructured |
| DocTR（GitHub） | https://github.com/mindee/doctr |
| onnxruntime CUDA Provider | https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html |
| onnxtr（DocTR ONNX 版本） | https://pypi.org/project/onnxtr/ |
| Ultralytics 许可证 | https://www.ultralytics.com/license |
| RT-DETR（GitHub） | https://github.com/lyuwenyu/RT-DETR |
