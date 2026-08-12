"""领域层词典管理端口与值对象模块

定义 DomainDictionaryPort、DictionaryConsumerPort 协议契约及其值对象
（DictionaryEntry、DictionaryQuery、DictionarySnapshot）。
遵循六边形架构：领域层零外部依赖，仅使用 Python 标准库。

设计约束：
- DomainDictionaryPort 是 typing.Protocol，使用 @runtime_checkable
- DictionaryConsumerPort 是 typing.Protocol，使用 @runtime_checkable
- DictionaryEntry/DictionaryQuery/DictionarySnapshot 是 frozen dataclass
- 所有字段通过构造器传入，不可变设计
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.domain.exceptions import EntityValidationError


@dataclass(frozen=True)
class DictionaryEntry:
    """词典词条值对象

    Attributes:
        term: 词条文本（业务唯一键，必填非空）
        entity_type: 实体类型（PERSON/ORG/LOC/PRODUCT/CONCEPT/...）
        category: 词条类别（strategy/finance/market/tech/org/general）
        active: 是否启用
        version: 词条版本
        created_by: 创建者
        created_at: 创建时间（ISO 字符串）
        updated_at: 更新时间（ISO 字符串）
    """

    term: str = ""
    entity_type: str = ""
    category: str = "general"
    active: bool = True
    version: int = 1
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        """验证 term 非空"""
        if not self.term or not self.term.strip():
            raise EntityValidationError(
                message="term must not be empty",
                context={"entity": "DictionaryEntry", "field": "term", "value": self.term},
            )


@dataclass(frozen=True)
class DictionaryQuery:
    """词典查询值对象（DDD Query Object 模式）

    Attributes:
        category: 按类别过滤
        entity_type: 按实体类型过滤
        active_only: 仅返回启用词条
        page: 页码
        page_size: 每页条数（≤100）
    """

    category: str | None = None
    entity_type: str | None = None
    active_only: bool = True
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        """验证查询参数范围"""
        if self.page_size > 100:
            raise EntityValidationError(
                message="page_size must not exceed 100",
                context={"query": "DictionaryQuery", "field": "page_size", "value": self.page_size},
            )
        if self.page_size < 1:
            raise EntityValidationError(
                message="page_size must be >= 1",
                context={"query": "DictionaryQuery", "field": "page_size", "value": self.page_size},
            )
        if self.page < 1:
            raise EntityValidationError(
                message="page must be >= 1",
                context={"query": "DictionaryQuery", "field": "page", "value": self.page},
            )


@dataclass(frozen=True)
class DictionarySnapshot:
    """词典快照值对象

    Attributes:
        snapshot_id: 快照 ID
        version: 词典版本号
        entries: 快照词条
        created_by: 创建者
        created_at: 创建时间
        change_summary: 变更摘要
    """

    snapshot_id: str = ""
    version: int = 0
    entries: tuple[DictionaryEntry, ...] = field(default_factory=tuple)
    created_by: str = ""
    created_at: str = ""
    change_summary: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DomainDictionaryPort(Protocol):
    """领域词典管理端口协议

    定义词条 CRUD、快照管理、回滚等核心方法。
    领域层定义契约，基础设施层实现 PostgreSQL 仓储。
    """

    async def list_entries(self, query: DictionaryQuery) -> list[DictionaryEntry]:
        """按查询条件列出词条

        Args:
            query: 查询条件（分类/类型/分页）

        Returns:
            符合条件的词条列表
        """
        ...

    async def get_entry(self, term: str) -> DictionaryEntry | None:
        """按词条名查询

        Args:
            term: 词条文本

        Returns:
            DictionaryEntry 或 None（不存在）
        """
        ...

    async def add_entry(self, entry: DictionaryEntry) -> DictionaryEntry:
        """添加词条

        Args:
            entry: 待添加的词条

        Returns:
            已保存的词条（含生成的元数据）

        Raises:
            DictionaryEntryConflictError: 词条已存在
        """
        ...

    async def update_entry(self, term: str, entry: DictionaryEntry) -> DictionaryEntry:
        """修改词条

        Args:
            term: 要修改的词条名
            entry: 新的词条数据

        Returns:
            更新后的词条

        Raises:
            DictionaryNotFoundError: 词条不存在
            DictionaryVersionConflictError: 版本冲突
        """
        ...

    async def delete_entry(self, term: str) -> None:
        """删除词条

        Args:
            term: 要删除的词条名

        Raises:
            DictionaryNotFoundError: 词条不存在
        """
        ...

    async def get_active_dictionary(self) -> list[tuple[str, str]]:
        """获取活动词典（仅 active=True 的词条）

        返回格式为 (词条, 实体类型) 列表，
        直接对接 RuleBasedExtractor.reload_dictionary() 输入格式。

        Returns:
            list[tuple[str, str]]: (词条, 实体类型) 列表
        """
        ...

    async def create_snapshot(self, created_by: str) -> DictionarySnapshot:
        """创建词典快照

        Args:
            created_by: 创建者

        Returns:
            创建的词典快照
        """
        ...

    async def rollback(self, version: int) -> None:
        """回滚至指定版本

        Args:
            version: 目标词典版本号

        Raises:
            DictionaryNotFoundError: 目标版本不存在
        """
        ...

    async def list_snapshots(self) -> list[DictionarySnapshot]:
        """列出所有快照

        Returns:
            快照列表（按版本降序）
        """
        ...


@runtime_checkable
class DictionaryConsumerPort(Protocol):
    """词典消费端端口协议

    定义"词典消费端热更新能力"的抽象契约。
    遵循接口隔离原则（ISP），RuleBasedExtractor 同时实现
    EntityExtractionPort 与 DictionaryConsumerPort。
    """

    def reload_dictionary(self, dictionary: list[tuple[str, str]]) -> None:
        """热更新词典

        将完整词典（词条, 实体类型）列表热注入消费端运行时状态，
        无需重启系统即可生效。

        Args:
            dictionary: (词条, 实体类型) 列表
        """
        ...


__all__ = [
    "DomainDictionaryPort",
    "DictionaryConsumerPort",
    "DictionaryEntry",
    "DictionaryQuery",
    "DictionarySnapshot",
]
