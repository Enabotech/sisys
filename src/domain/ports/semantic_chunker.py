"""语义分块端口模块

定义语义分块的核心端口契约，遵循六边形架构 R1 设计规则：
领域层抽象端口（Protocol），定义纯业务契约。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.semantic_chunk import ChunkingConfig, SemanticChunk
from src.domain.value_objects.parsed_document import ParsedDocument


@runtime_checkable
class SemanticChunkerPort(Protocol):
    """语义分块器端口协议

    对解析完成的结构化文档执行语义分块，基于规则驱动的边界检测和令牌预算聚合。

    算法流程：
    1. 遍历 ParsedDocument.pages（page_number 升序）
    2. 每页内按阅读顺序迭代元素的 content
    3. 检测语义边界并切分段落
    4. 按 ChunkingConfig 聚合段落为目标大小分块
    5. 生成 SemanticChunk 列表（含完整元数据）
    """

    async def chunk(
        self,
        parsed_doc: ParsedDocument,
        config: ChunkingConfig | None = None,
    ) -> list[SemanticChunk]:
        """对解析完成的结构化文档执行语义分块

        Args:
            parsed_doc: 解析完成的结构化文档（ParsedDocument）
            config: 分块配置（为 None 时使用 ChunkingConfig() 默认值）

        Returns:
            SemanticChunk 列表（按 chunk_index 升序；空文档返回空列表，不抛异常）

        Raises:
            ChunkingError: 分块算法内部异常（如不可序列化的数据结构）
        """
        ...


__all__ = [
    "SemanticChunkerPort",
]