"""MemoryService — 记忆服务（领域层）。

负责接收用户记忆请求、协调压缩（通过协议注入）、双层写入、发布 MemoryChanged 事件。

依赖倒置：
- TextExtractorProtocol：文本提取接口
- CompressorProtocol：压缩接口
- EventPublisherProtocol：事件发布接口（可选）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.events.memory_events import MemoryChanged


@dataclass
class MemoryVersionConflictError(Exception):
    """版本冲突异常。"""

    memory_id: str
    message: str = "版本冲突"


@dataclass
class MemoryNotFoundError(Exception):
    """记忆不存在异常。"""

    memory_id: str
    message: str = "记忆不存在"


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

    memory_id: str
    user_id: str
    content: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass
class MemoryDeleteRequest:
    """记忆删除请求。"""

    memory_id: str
    user_id: str


@dataclass
class Memory:
    """记忆聚合根。"""

    memory_id: str
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

    协调 L1 压缩、存储写入、事件发布。
    使用依赖倒置注入 TextExtractor 和 Compressor。
    """

    def __init__(
        self,
        text_extractor,  # TextExtractorProtocol
        compressor,  # CompressorProtocol
        event_publisher=None,  # EventPublisherProtocol | None
    ):
        """初始化 MemoryService。

        Args:
            text_extractor: 文本提取器（依赖倒置）
            compressor: 压缩器（依赖倒置）
            event_publisher: 事件发布器（可选）
        """
        self._text_extractor = text_extractor
        self._compressor = compressor
        self._event_publisher = event_publisher

        # 内部状态：存储的记忆（实际实现应使用仓储）
        self._memories: dict[str, Memory] = {}

    def save(self, request: MemorySaveRequest) -> Memory:
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
        memory_id = str(uuid.uuid4())
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

        # 4. 存储
        self._memories[memory_id] = memory

        # 5. 发布事件
        self._publish_memory_changed(
            memory_id=memory_id,
            user_id=request.user_id,
            name=request.name,
            change_type="create",
            is_automatic=False,
            old_value=None,
            new_value={"name": request.name, "path": path},
        )

        return memory

    def update(self, request: MemoryUpdateRequest) -> Memory:
        """更新记忆。

        Args:
            request: 记忆更新请求

        Returns:
            Memory：更新的记忆

        Raises:
            MemoryNotFoundError: 如果记忆不存在
            MemoryVersionConflictError: 如果版本冲突
        """
        if request.memory_id not in self._memories:
            raise MemoryNotFoundError(request.memory_id)

        memory = self._memories[request.memory_id]
        old_value = {"name": memory.name, "content": memory.content}

        # 重新提取和压缩（如果内容变更）
        if request.content is not None:
            extraction = self._text_extractor.extract(request.content)
            compression = self._compressor.compress(extraction.content)
            memory.content = compression.compressed

        if request.name is not None:
            memory.name = request.name

        if request.description is not None:
            memory.description = request.description

        memory.version += 1
        memory.updated_at = datetime.now(UTC)

        self._publish_memory_changed(
            memory_id=request.memory_id,
            user_id=request.user_id,
            name=memory.name,
            change_type="update",
            is_automatic=False,
            old_value=old_value,
            new_value={"name": memory.name, "content": memory.content},
        )

        return memory

    def delete(self, request: MemoryDeleteRequest) -> None:
        """删除记忆。

        Args:
            request: 记忆删除请求

        Raises:
            MemoryNotFoundError: 如果记忆不存在
        """
        if request.memory_id not in self._memories:
            raise MemoryNotFoundError(request.memory_id)

        memory = self._memories[request.memory_id]
        old_value = {"name": memory.name, "path": memory.path}

        del self._memories[request.memory_id]

        self._publish_memory_changed(
            memory_id=request.memory_id,
            user_id=request.user_id,
            name=memory.name,
            change_type="delete",
            is_automatic=False,
            old_value=old_value,
            new_value=None,
        )

    def list(self, user_id: str) -> list[Memory]:
        """列出用户所有记忆。

        Args:
            user_id: 用户 ID

        Returns:
            list[Memory]：记忆列表
        """
        return [m for m in self._memories.values() if m.user_id == user_id]

    def get(self, memory_id: str) -> Memory:
        """获取记忆。

        Args:
            memory_id: 记忆 ID

        Returns:
            Memory：记忆

        Raises:
            MemoryNotFoundError: 如果记忆不存在
        """
        if memory_id not in self._memories:
            raise MemoryNotFoundError(memory_id)
        return self._memories[memory_id]

    def _publish_memory_changed(
        self,
        memory_id: str,
        user_id: str,
        name: str,
        change_type: str,
        is_automatic: bool,
        old_value: dict | None,
        new_value: dict | None,
    ) -> None:
        """发布 MemoryChanged 事件。

        Args:
            memory_id: 记忆 ID
            user_id: 用户 ID
            name: 记忆名称
            change_type: 变更类型
            is_automatic: 是否自动触发
            old_value: 旧值
            new_value: 新值
        """
        if self._event_publisher is None:
            return

        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type=change_type,
            is_automatic=is_automatic,
            old_value=old_value,
            new_value=new_value,
        )
        self._event_publisher.publish(event)
