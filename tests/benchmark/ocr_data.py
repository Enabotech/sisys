"""OCR 基准测试数据集配置

包含 6 个真实 PDF 文档的元数据和预期结果参考（ground truth）。
用于 OCR 准确率测试和性能基准测试。

数据集分类：
- 少年时系列（3 个）：扫描件为主，含少量嵌入噪声文本（~36 字符/页）
  → 混合 PDF，部分页触发 OCR，部分页跳过
- 费恩曼物理学讲义系列（3 个）：纯扫描件，零嵌入文本
  → 全部触发 OCR
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# =========================================================================
# 数据集根目录
# =========================================================================
OCR_DATA_DIR = Path("/mnt/x/.data/raw/ocr")


@dataclass(frozen=True)
class OCRDocumentSpec:
    """单个 OCR 测试文档的规格说明

    Attributes:
        filename: 文件名
        display_name: 显示名称（中文）
        total_pages: 总页数
        file_size_mb: 文件大小（MB）
        is_scanned: 是否为纯扫描件（无嵌入文本层）
        has_embedded_text: 是否含嵌入文本
        embedded_text_chars_per_page: 嵌入文本密度（平均字符/页）
        expected_ocr_pages: 预期触发 OCR 的页数范围
        ground_truth_keywords: 预期 OCR 能识别的关键词列表
        language: 主要语言
    """

    filename: str
    display_name: str
    total_pages: int
    file_size_mb: int
    is_scanned: bool
    has_embedded_text: bool
    embedded_text_chars_per_page: float = 0.0
    expected_ocr_pages: tuple[int, int] = (0, 0)
    ground_truth_keywords: tuple[str, ...] = ()
    language: str = "zh-CN"

    @property
    def path(self) -> Path:
        return OCR_DATA_DIR / self.filename


# =========================================================================
# 数据集定义
# =========================================================================

# --- 少年时系列（混合 PDF：扫描件 + 少量嵌入文本） ---
SHAONIANSHI_36 = OCRDocumentSpec(
    filename="少年时-36-数学在西方.pdf",
    display_name="少年时·数学在西方",
    total_pages=134,
    file_size_mb=44,
    is_scanned=False,
    has_embedded_text=True,
    embedded_text_chars_per_page=36.0,
    expected_ocr_pages=(100, 134),
    ground_truth_keywords=(
        "数学",
        "西方",
        "几何",
        "代数",
        "概率",
        "欧几里得",
        "笛卡尔",
        "牛顿",
        "莱布尼茨",
        "少年时",
        "数学在西方",
    ),
    language="zh-CN",
)

SHAONIANSHI_50 = OCRDocumentSpec(
    filename="少年时-50-结构机器人.pdf",
    display_name="少年时·结构机器人",
    total_pages=140,
    file_size_mb=128,
    is_scanned=False,
    has_embedded_text=True,
    embedded_text_chars_per_page=36.0,
    expected_ocr_pages=(100, 140),
    ground_truth_keywords=(
        "结构",
        "机器人",
        "机械",
        "齿轮",
        "连杆",
        "电机",
        "传感器",
        "控制",
        "少年时",
        "结构机器人",
    ),
    language="zh-CN",
)

SHAONIANSHI_60 = OCRDocumentSpec(
    filename="少年时-60-探究意识的本质.pdf",
    display_name="少年时·探究意识的本质",
    total_pages=135,
    file_size_mb=144,
    is_scanned=False,
    has_embedded_text=True,
    embedded_text_chars_per_page=36.0,
    expected_ocr_pages=(100, 135),
    ground_truth_keywords=(
        "意识",
        "本质",
        "探究",
        "大脑",
        "神经",
        "认知",
        "心理",
        "哲学",
        "少年时",
        "探究意识的本质",
    ),
    language="zh-CN",
)

# --- 费恩曼物理学讲义系列（纯扫描件 PDF） ---
FEYNMAN_1 = OCRDocumentSpec(
    filename="费恩曼物理学讲义-1.pdf",
    display_name="费恩曼物理学讲义·卷一",
    total_pages=588,
    file_size_mb=28,
    is_scanned=True,
    has_embedded_text=False,
    expected_ocr_pages=(550, 588),
    ground_truth_keywords=(
        "费恩曼",
        "物理",
        "力学",
        "电磁",
        "量子",
        "Feynman",
        "Physics",
        "力学",
        "热力学",
        "相对论",
        "牛顿",
    ),
    language="zh-CN",
)

FEYNMAN_2 = OCRDocumentSpec(
    filename="费恩曼物理学讲义-2.pdf",
    display_name="费恩曼物理学讲义·卷二",
    total_pages=623,
    file_size_mb=25,
    is_scanned=True,
    has_embedded_text=False,
    expected_ocr_pages=(580, 623),
    ground_truth_keywords=(
        "费恩曼",
        "物理",
        "电磁学",
        "场",
        "麦克斯韦",
        "Feynman",
        "电磁场",
        "电动力学",
        "电磁感应",
        "波动",
    ),
    language="zh-CN",
)

FEYNMAN_3 = OCRDocumentSpec(
    filename="费恩曼物理学讲义-3.pdf",
    display_name="费恩曼物理学讲义·卷三",
    total_pages=377,
    file_size_mb=20,
    is_scanned=True,
    has_embedded_text=False,
    expected_ocr_pages=(350, 377),
    ground_truth_keywords=(
        "费恩曼",
        "物理",
        "量子力学",
        "薛定谔",
        "波函数",
        "Feynman",
        "Quantum",
        "量子",
        "原子",
        "粒子",
        "散射",
    ),
    language="zh-CN",
)

# =========================================================================
# 测试分组
# =========================================================================

ALL_DOCUMENTS: tuple[OCRDocumentSpec, ...] = (
    SHAONIANSHI_36,
    SHAONIANSHI_50,
    SHAONIANSHI_60,
    FEYNMAN_1,
    FEYNMAN_2,
    FEYNMAN_3,
)

SMALL_DOCUMENTS: tuple[OCRDocumentSpec, ...] = (
    SHAONIANSHI_36,
    FEYNMAN_1,
    FEYNMAN_3,
)

LARGE_DOCUMENTS: tuple[OCRDocumentSpec, ...] = (
    SHAONIANSHI_50,
    SHAONIANSHI_60,
    FEYNMAN_2,
)

# 准确率测试用（中等大小，包含中英文）
ACCURACY_TEST_DOCUMENTS: tuple[OCRDocumentSpec, ...] = (
    SHAONIANSHI_36,
    FEYNMAN_1,
)

# 性能测试用（覆盖小/中/大）
PERF_TEST_DOCUMENTS: tuple[OCRDocumentSpec, ...] = (
    SHAONIANSHI_36,  # 44MB, 134页
    FEYNMAN_1,  # 28MB, 588页
    SHAONIANSHI_50,  # 128MB, 140页
)
