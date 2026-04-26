"""MemoryService — 记忆服务（领域层）。

负责接收用户记忆请求、协调压缩（通过协议注入）、双层写入、发布 MemoryChanged 事件。

依赖倒置：
- TextExtractorService：文本提取接口
- CompressorService：压缩接口
- FileMemoryAdapter：L0 文件系统适配器（可选，用于双层存储）
- MemoryMetadataRepositoryProtocol：记忆元数据仓储（使用 PostgreSQL L2 持久化）
- MemoryChangeHistoryRepositoryProtocol：记忆变更历史仓储
- EventPublisherProtocol：事件发布接口（可选）

架构来源: architecture.md §11.2.5
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.memory_events import MemoryChanged


@dataclass
class MemoryVersionConflictError(Exception):
    """版本冲突异常。"""

    memory_id: UUID
    message: str = "版本冲突"

    def __init__(self, memory_id: UUID, message: str = "版本冲突"):
        self.memory_id = memory_id
        super().__init__(message)


@dataclass
class MemoryNotFoundError(Exception):
    """记忆不存在异常。"""

    memory_id: UUID
    message: str = "记忆不存在"

    def __init__(self, memory_id: UUID, message: str = "记忆不存在"):
        self.memory_id = memory_id
        super().__init__(message)


@dataclass
class MemorySaveRequest:
    """记忆保存请求。"""

    user_id: str
    name: str
    content: str
    memory_type: str = "user"  # 'user' | 'feedback' | 'project' | 'reference'
    description: str = ""


@dataclass
class MemoryUpdateRequest:
    """记忆更新请求。"""

    memory_id: UUID
    user_id: str
    content: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass
class MemoryDeleteRequest:
    """记忆删除请求。"""

    memory_id: UUID
    user_id: str


@dataclass
class Memory:
    """记忆聚合根。"""

    memory_id: UUID
    user_id: str
    name: str
    content: str
    memory_type: str
    description: str
    path: str
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MemoryService:
    """记忆服务（领域层）。

    协调 L1 压缩、存储写入（L2 PostgreSQL）、事件发布。
    使用依赖倒置注入 TextExtractor、Compressor 和 Repositories。
    """

    def __init__(
        self,
        text_extractor,  # TextExtractorService
        compressor,  # CompressorService
        metadata_repository,  # MemoryMetadataRepositoryProtocol
        history_repository,  # MemoryChangeHistoryRepositoryProtocol
        file_adapter=None,  # FileMemoryAdapter | None
        event_publisher=None,  # EventPublisherProtocol | None
    ):
        """初始化 MemoryService。

        Args:
            text_extractor: 文本提取器（依赖倒置）
            compressor: 压缩器（依赖倒置）
            metadata_repository: 记忆元数据仓储（PostgreSQL L2 持久化）
            history_repository: 记忆变更历史仓储（append-only）
            file_adapter: L0 文件系统适配器（可选，用于双层存储）
            event_publisher: 事件发布器（可选）
        """
        self._text_extractor = text_extractor
        self._compressor = compressor
        self._metadata_repository = metadata_repository
        self._history_repository = history_repository
        self._file_adapter = file_adapter
        self._event_publisher = event_publisher

    async def save(self, request: MemorySaveRequest) -> Memory:
        """保存记忆。

        Args:
            request: 记忆保存请求

        Returns:
            Memory：创建的记忆

        Raises:
            MemoryVersionConflictError: 如果版本冲突
        """
        # 1. 提取记忆核心内容
        extraction = self._text_extractor.extract(request.content)

        # 2. 压缩内容
        compression = self._compressor.compress(extraction.content)

        # 3. 创建记忆
        memory_id = uuid.uuid4()
        path = f"{request.memory_type}/{memory_id}.md"
        memory = Memory(
            memory_id=memory_id,
            user_id=request.user_id,
            name=request.name,
            content=compression.compressed,
            memory_type=request.memory_type,
            description=request.description,
            path=path,
            version=1,
        )

        # 4. 写入 L2 PostgreSQL（通过仓储）
        from src.domain.entities.memory_change_history import MemoryChangeHistory
        from src.domain.entities.memory_metadata import MemoryMetadata

        metadata = MemoryMetadata(
            memory_id=memory_id,
            name=request.name,
            type=request.memory_type,
            user_id=request.user_id,
            description=request.description,
            path=path,
            version=1,
        )
        await self._metadata_repository.save(metadata)

        # 5. 记录历史（append-only）
        history = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=1,
            change_type="create",
            changed_by=request.user_id,
            changed_fields={"name": request.name, "content": compression.compressed},
            diff_summary=f"创建记忆: {request.name}",
        )
        await self._history_repository.save(history)

        # 6. 写入 L0 文件系统（双层存储）
        await self._write_to_l0(memory_id, request.memory_type, compression.compressed, request.name, request.description)

        # 7. 发布事件
        await self._publish_memory_changed(
            memory_id=memory_id,
            user_id=request.user_id,
            name=request.name,
            change_type="create",
            is_automatic=False,
            old_value=None,
            new_value={"name": request.name, "path": path},
        )

        return memory

    async def update(self, request: MemoryUpdateRequest) -> Memory:
        """更新记忆。

        Args:
            request: 记忆更新请求

        Returns:
            Memory：更新的记忆

        Raises:
            MemoryNotFoundError: 如果记忆不存在
            MemoryVersionConflictError: 如果版本冲突
        """
        # 获取现有记忆
        metadata = await self._metadata_repository.get_by_id(request.memory_id)
        if metadata is None:
            raise MemoryNotFoundError(request.memory_id)

        old_value = {"name": metadata.name, "content": ""}

        # 重新提取和压缩（如果内容变更）
        if request.content is not None:
            extraction = self._text_extractor.extract(request.content)
            compression = self._compressor.compress(extraction.content)
            metadata.description = compression.compressed
            new_content = compression.compressed
        else:
            new_content = metadata.description

        if request.name is not None:
            metadata.name = request.name

        if request.description is not None:
            metadata.description = request.description

        # 递增版本
        metadata.bump_version()

        # 更新仓储
        await self._metadata_repository.save(metadata)

        # 记录历史
        from src.domain.entities.memory_change_history import MemoryChangeHistory

        history = MemoryChangeHistory.create(
            memory_id=request.memory_id,
            version=metadata.version,
            change_type="update",
            changed_by=request.user_id,
            changed_fields={"name": [old_value["name"], metadata.name], "content": [old_value["content"], new_content]},
            diff_summary=f"更新记忆: {old_value['name']} -> {metadata.name}",
        )
        await self._history_repository.save(history)

        # 写入 L0 文件系统（双层存储）
        await self._write_to_l0(request.memory_id, metadata.type, new_content or "", metadata.name, metadata.description)

        await self._publish_memory_changed(
            memory_id=request.memory_id,
            user_id=request.user_id,
            name=metadata.name,
            change_type="update",
            is_automatic=False,
            old_value=old_value,
            new_value={"name": metadata.name, "content": new_content},
        )

        return Memory(
            memory_id=metadata.memory_id,
            user_id=metadata.user_id,
            name=metadata.name,
            content=new_content or "",
            memory_type=metadata.type,
            description=metadata.description,
            path=metadata.path,
            version=metadata.version,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
        )

    async def delete(self, request: MemoryDeleteRequest) -> None:
        """删除记忆。

        Args:
            request: 记忆删除请求

        Raises:
            MemoryNotFoundError: 如果记忆不存在
        """
        metadata = await self._metadata_repository.get_by_id(request.memory_id)
        if metadata is None:
            raise MemoryNotFoundError(request.memory_id)

        old_value = {"name": metadata.name, "path": metadata.path}

        # 软删除
        await self._metadata_repository.delete(request.memory_id)

        # 记录历史（append-only，delete 操作也记录）
        from src.domain.entities.memory_change_history import MemoryChangeHistory

        history = MemoryChangeHistory.create(
            memory_id=request.memory_id,
            version=metadata.version + 1,
            change_type="delete",
            changed_by=request.user_id,
            changed_fields=None,
            diff_summary=f"删除记忆: {metadata.name}",
        )
        await self._history_repository.save(history)

        # 删除 L0 文件系统（双层存储）
        await self._delete_from_l0(request.memory_id, metadata.type)

        await self._publish_memory_changed(
            memory_id=request.memory_id,
            user_id=request.user_id,
            name=metadata.name,
            change_type="delete",
            is_automatic=False,
            old_value=old_value,
            new_value=None,
        )

    async def list(self, user_id: str) -> list[Memory]:
        """列出用户所有记忆。

        Args:
            user_id: 用户 ID

        Returns:
            list[Memory]：记忆列表
        """
        metadata_list = await self._metadata_repository.list_by_user(user_id)
        memories = []
        for metadata in metadata_list:
            histories = await self._history_repository.get_by_memory_id(metadata.memory_id)
            # 获取最新内容（从历史记录中查找）
            latest_content = ""
            for h in reversed(histories):
                if h.change_type == "create":
                    latest_content = h.changed_fields.get("content", "")
                    break
                elif h.change_type == "update":
                    latest_content = h.changed_fields.get("content", [""])[-1]
            memories.append(
                Memory(
                    memory_id=metadata.memory_id,
                    user_id=metadata.user_id,
                    name=metadata.name,
                    content=latest_content,
                    memory_type=metadata.type,
                    description=metadata.description,
                    path=metadata.path,
                    version=metadata.version,
                    created_at=metadata.created_at,
                    updated_at=metadata.updated_at,
                )
            )
        return memories

    async def get(self, memory_id: UUID) -> Memory:
        """获取记忆。

        Args:
            memory_id: 记忆 ID

        Returns:
            Memory：记忆

        Raises:
            MemoryNotFoundError: 如果记忆不存在
        """
        metadata = await self._metadata_repository.get_by_id(memory_id)
        if metadata is None:
            raise MemoryNotFoundError(memory_id)

        histories = await self._history_repository.get_by_memory_id(memory_id)
        latest_content = ""
        for h in reversed(histories):
            if h.change_type == "create":
                latest_content = h.changed_fields.get("content", "")
                break
            elif h.change_type == "update":
                latest_content = h.changed_fields.get("content", [""])[-1]

        return Memory(
            memory_id=metadata.memory_id,
            user_id=metadata.user_id,
            name=metadata.name,
            content=latest_content,
            memory_type=metadata.type,
            description=metadata.description,
            path=metadata.path,
            version=metadata.version,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
        )

    async def _write_to_l0(
        self,
        memory_id: UUID,
        memory_type: str,
        content: str,
        name: str,
        description: str,
    ) -> None:
        """写入 L0 文件系统（双层存储）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            content: 记忆内容
            name: 记忆名称
            description: 记忆描述
        """
        if self._file_adapter is None:
            return

        # 构建 MD 文件内容
        md_content = self._build_md_content(name, description, memory_type, content)

        # 在线程池中执行同步文件写入，避免阻塞事件循环
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._file_adapter.write(str(memory_id), memory_type, md_content),
        )

        # 注意：MEMORY.md 索引更新由 MemoryChangedListener 事件驱动，不再在此处同步更新

    def _build_md_content(self, name: str, description: str, memory_type: str, content: str) -> str:
        """构建 MD 文件内容。

        Args:
            name: 记忆名称
            description: 记忆描述
            memory_type: 记忆类型
            content: 记忆内容

        Returns:
            MD 格式文件内容
        """
        import uuid

        lines = [
            "---",
            f"name: {name}",
            f"description: {description}",
            f"type: {memory_type}",
            f"originSessionId: {uuid.uuid4()}",
            "---",
            content,
        ]
        return "\n".join(lines)

    async def _delete_from_l0(self, memory_id: UUID, memory_type: str) -> None:
        """从 L0 文件系统删除（双层存储）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
        """
        if self._file_adapter is None:
            return

        # 在线程池中执行同步文件删除
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._file_adapter.delete(str(memory_id), memory_type),
        )

        # 注意：MEMORY.md 索引移除由 MemoryChangedListener 事件驱动，不再在此处同步更新

    async def _publish_memory_changed(
        self,
        memory_id: UUID,
        user_id: str,
        name: str,
        change_type: str,
        is_automatic: bool,
        old_value: dict | None,
        new_value: dict | None,
    ) -> None:
        """发布 MemoryChanged 事件。"""
        if self._event_publisher is None:
            return

        event = MemoryChanged(
            memory_id=str(memory_id),
            user_id=user_id,
            name=name,
            change_type=change_type,
            is_automatic=is_automatic,
            old_value=old_value,
            new_value=new_value,
        )
        self._event_publisher.publish(event)
