# RapidOCR 本地部署指南

## 概述

SISYS 使用 RapidOCR 作为本地 OCR 引擎。RapidOCR 负责图像文字检测与识别；PDF 由应用按页渲染为图像后交给 OCRPort。版面检测、表格语义和公式处理仍由各自端口负责。

本方案不启动独立 OCR HTTP/vLLM 服务，敏感文档只在应用所在环境内处理。

## 运行时与依赖

- Python 3.11+
- `rapidocr==3.9.2`
- `onnxruntime`（CPU 环境）或与目标 CUDA/cuDNN 匹配的 GPU provider
- `Pillow`、`pypdfium2`
- 模型包、模型目录和 wheel hash 必须在发布清单中固定；生产环境禁止运行时下载模型

项目通过 Poetry 管理依赖：

```bash
poetry install
poetry check
```

RapidOCR 的模型目录可通过 `RAPIDOCR_MODEL_DIR` 指定。空值表示使用 RapidOCR 包默认模型配置。应用启动时按需初始化模型一次，避免每页重复加载。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `RAPIDOCR_MODEL_DIR` | 空 | 本地模型配置/模型根目录 |
| `RAPIDOCR_MAX_CONCURRENCY` | `1` | 单个模型实例的最大并发推理数 |
| `SISYS_SCANNED_PAGE_THRESHOLD` | `50` | 单页文本字符数低于此值时触发 OCR |

CPU 和 GPU 运行时应使用相互独立的环境，不要同时安装两个 ONNX Runtime wheel。GPU provider 必须在目标机器上通过实际推理自检确认，CPU 测试通过不能代替 GPU 验证。

## 启动自检

应用启动或首次解析时应确认：

1. `RAPIDOCR_MODEL_DIR` 可读（如配置）。
2. RapidOCR 模型可成功构造。
3. ONNX Runtime provider 可用。
4. 使用一张受控中英文样本完成一次热身推理。
5. 模型版本、文件 hash 和许可证记录在发布物料中。

模型初始化或推理失败时，适配器转换为统一领域 OCR 异常；不向 API 响应暴露模型路径、内部堆栈或原始文档内容。

## OCR 流程

```text
DocumentParsingService
  -> PDFParser 提取文本层
  -> 文本密度检测（每页 < 50 字符）
  -> PdfPageRenderer 逐页生成 PNG
  -> RapidOCRAdapter（asyncio.to_thread）
  -> OCRPageResult(page_number, ParsedElement[])
  -> confidence < 0.85 标记 needs_review
```

图像文件直接交给同一适配器。RapidOCR 返回的文本、score 和检测多边形被映射为 `ParsedElement`；边界框存为项目统一的归一化 `BoundingBox`，原始像素多边形仅作为元数据保留。

## 质量验证

```bash
poetry run pytest tests/unit/infrastructure/document_parsing/test_rapidocr_adapter.py -q
poetry run pytest tests/contracts/test_port_contract_ocr.py tests/unit/application/services/test_document_parsing_service_ocr.py -q
poetry run ruff check src/ tests/
poetry run mypy src/
```

准确率和性能必须使用版本化金标准数据集分别测量中文、英文、冷启动、热推理、PDF 渲染、单页 P95、批量吞吐、并发和峰值内存。清晰印刷中文/英文目标为至少 95%，最终报告应同时记录硬件、provider、模型版本和参数。

## 故障排查

| 问题 | 处理方式 |
|---|---|
| RapidOCR 未安装 | 检查 Poetry lock 和应用镜像依赖，重新构建发布镜像 |
| 模型初始化失败 | 检查模型目录、文件 hash、许可证和 ONNX Runtime provider |
| 识别结果为空 | 检查图像是否可读、渲染 DPI、模型语言配置和输入尺寸 |
| 推理阻塞事件循环 | 确认调用经过 `asyncio.to_thread`，不要在事件循环直接调用同步引擎 |
| 并发不稳定或内存过高 | 降低 `RAPIDOCR_MAX_CONCURRENCY`，重新执行热推理与压力基准 |
| PDF 页面失败 | 检查 `pypdfium2` 和页面编号；部分页面失败会保留原页并写入 `partial_ocr_failure` |

## 安全与合规

- 模型和临时图像不纳入 Git。
- 生产构建阶段预置并校验模型，禁止运行时从公网下载。
- OCR 结果遵循现有租户隔离、访问控制和审计策略。
- 日志只记录文件标识、页码、耗时、错误码和脱敏摘要，不记录完整文档内容。
- RapidOCR 软件、模型及 ONNX Runtime 的许可证必须在发布前完成合规审查。
