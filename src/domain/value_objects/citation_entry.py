"""引文条目值对象（Story 6-5b——PDF 报告附录 C 引文索引的条目载体）。

evidence_refs 首消费的解析产物：每条 chunk_id 经三段链（收集→解析→组装）
解析为「文档名 + 页码 + 切片标识」溯源三元组条目。零外部依赖（domain 纯净）。

与 3-8 ``Citation`` VO 的语义分界（OD-6 裁定不复用）：检索溯源域产物含
text/start_offset/end_offset/bbox/confidence 检索语义字段且无 filename；
报告引文条目需要 filename 与解析状态（降级三态承载）——语义不同面。
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from src.domain.exceptions import EntityValidationError

__all__ = ["CitationEntry"]


@dataclass(frozen=True)
class CitationEntry:
    """引文条目（附录 C 单行——溯源三元组 + 解析降级状态）。

    解析降级三态冻结：``resolved``（解析成功）/ ``point_missing``
    （Qdrant 检索点缺失）/ ``document_missing``（documents 行缺失）；
    页码缺失是 resolved 的子形态非独立态（文档在而 chunks 元数据无该
    chunk_id——status 仍 resolved + page=0，渲染层 0 渲染为 ``-``）。

    Attributes:
        index: 引文索引（≥1——去重保序首现次序）。
        document_id: 文档标识（解析成功时非空 UUID 字符串；失败态空串——
            status 承载降级语义）。
        chunk_id: 切片标识（引文锚定标识——全量值，显示截断归渲染层）。
        filename: 文档名（解析成功时来源 documents 行；失败态空串）。
        page: 页码（≥1；不可得时 0——渲染层 0→``-``）。
        status: 解析状态（值域三元组 ``VALID_STATUSES``）。
    """

    #: status 合法值域（三元组冻结——降级状态机单源；ClassVar 非实例字段）
    VALID_STATUSES: ClassVar[tuple[str, ...]] = ("resolved", "point_missing", "document_missing")

    index: int
    document_id: str
    chunk_id: str
    filename: str
    page: int
    status: str

    def __post_init__(self) -> None:
        """不变量校验（六查——违例抛 EntityValidationError 242）。

        Raises:
            EntityValidationError: index < 1 / chunk_id 空串 / status 不在
                值域三元组 / page < 0 / document_id 非空但非 UUID 格式。
        """
        if self.index < 1:
            raise EntityValidationError(
                message="引文索引必须 ≥1（去重保序首现次序）",
                context={"entity": "CitationEntry", "field": "index", "index": self.index},
            )
        if not self.chunk_id:
            raise EntityValidationError(
                message="切片标识不可为空（引文锚定标识）",
                context={"entity": "CitationEntry", "field": "chunk_id"},
            )
        if self.status not in self.VALID_STATUSES:
            raise EntityValidationError(
                message=f"解析状态必须为 {self.VALID_STATUSES} 之一（三元组冻结——页码缺失是 resolved 子形态）",
                context={"entity": "CitationEntry", "field": "status", "status": self.status},
            )
        if self.page < 0:
            raise EntityValidationError(
                message="页码必须 ≥0（0 表不可得）",
                context={"entity": "CitationEntry", "field": "page", "page": self.page},
            )
        if self.document_id:
            try:
                uuid.UUID(self.document_id)
            except ValueError as error:
                raise EntityValidationError(
                    message="document_id 非空时必须为 UUID 字符串",
                    context={"entity": "CitationEntry", "field": "document_id"},
                ) from error
