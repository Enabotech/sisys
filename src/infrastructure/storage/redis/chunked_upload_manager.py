"""基础设施层分片上传状态管理器

通过 L1CachePort（Redis）管理分片上传状态，支持断点续传。
JSON 序列化存储结构化状态，asyncio.Lock 保证并发安全。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from src.domain.ports.l1_cache import L1CachePort
from src.domain.value_objects.upload_limits import CHUNKED_UPLOAD_TTL, get_chunk_size

# Redis key 前缀
_CHUNKED_UPLOAD_PREFIX = "chunked_upload:"


class ChunkedUploadState:
    """分片上传状态数据结构"""

    def __init__(
        self,
        upload_id: str,
        filename: str,
        file_size: int,
        chunk_size: int,
        uploaded_parts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.upload_id = upload_id
        self.filename = filename
        self.file_size = file_size
        self.chunk_size = chunk_size
        self.uploaded_parts = uploaded_parts or []

    def to_json(self) -> str:
        return json.dumps(
            {
                "upload_id": self.upload_id,
                "filename": self.filename,
                "file_size": self.file_size,
                "chunk_size": self.chunk_size,
                "uploaded_parts": self.uploaded_parts,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> ChunkedUploadState:
        obj = json.loads(data)
        return cls(
            upload_id=obj["upload_id"],
            filename=obj["filename"],
            file_size=obj["file_size"],
            chunk_size=obj["chunk_size"],
            uploaded_parts=obj.get("uploaded_parts", []),
        )


class ChunkedUploadManager:
    """分片上传状态管理器

    通过 L1CachePort 操作 Redis，使用 JSON 序列化存储分片状态。
    asyncio.Lock 保证同一 upload_id 的分片状态串行更新。
    """

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, cache: L1CachePort) -> None:
        self._cache = cache

    def _get_lock(self, upload_id: str) -> asyncio.Lock:
        if upload_id not in self._locks:
            self._locks[upload_id] = asyncio.Lock()
        return self._locks[upload_id]

    def _redis_key(self, upload_id: str) -> str:
        return f"{_CHUNKED_UPLOAD_PREFIX}{upload_id}"

    async def init_upload(self, filename: str, file_size: int) -> dict[str, Any]:
        """初始化分片上传

        Args:
            filename: 文件名
            file_size: 文件总大小（字节）

        Returns:
            {"upload_id": str, "chunk_size": int, "total_parts": int}
        """
        chunk_size = get_chunk_size(file_size)
        if chunk_size == 0:
            chunk_size = file_size

        upload_id = uuid.uuid4().hex
        state = ChunkedUploadState(
            upload_id=upload_id,
            filename=filename,
            file_size=file_size,
            chunk_size=chunk_size,
        )

        await self._cache.set(
            self._redis_key(upload_id),
            state.to_json(),
            ttl=CHUNKED_UPLOAD_TTL,
        )

        total_parts = (file_size + chunk_size - 1) // chunk_size
        return {
            "upload_id": upload_id,
            "chunk_size": chunk_size,
            "total_parts": total_parts,
        }

    async def upload_part(self, upload_id: str, part_number: int, etag: str) -> dict[str, Any]:
        """记录已上传的分片

        Args:
            upload_id: 上传会话 ID
            part_number: 分片编号
            etag: 分片 ETag

        Returns:
            {"uploaded_parts": int}

        Raises:
            ValueError: upload_id 不存在或分片乱序
        """
        lock = self._get_lock(upload_id)
        async with lock:
            state = await self._get_state(upload_id)
            if state is None:
                raise ValueError(f"upload_id {upload_id} 不存在或已过期")

            for part in state.uploaded_parts:
                if part["part_number"] == part_number:
                    raise ValueError(f"分片 {part_number} 已上传")

            state.uploaded_parts.append({"part_number": part_number, "etag": etag})
            await self._cache.set(
                self._redis_key(upload_id),
                state.to_json(),
                ttl=CHUNKED_UPLOAD_TTL,
            )

        return {"uploaded_parts": len(state.uploaded_parts)}

    async def complete_upload(self, upload_id: str) -> ChunkedUploadState:
        """完成分片上传

        Args:
            upload_id: 上传会话 ID

        Returns:
            ChunkedUploadState 完整状态

        Raises:
            ValueError: upload_id 不存在
        """
        state = await self._get_state(upload_id)
        if state is None:
            raise ValueError(f"upload_id {upload_id} 不存在或已过期")

        await self._cache.delete(self._redis_key(upload_id))
        return state

    async def resume_upload(self, upload_id: str) -> dict[str, Any] | None:
        """查询分片上传状态（断点续传）

        Args:
            upload_id: 上传会话 ID

        Returns:
            状态字典或 None（upload_id 不存在）
        """
        state = await self._get_state(upload_id)
        if state is None:
            return None
        return {
            "upload_id": state.upload_id,
            "filename": state.filename,
            "file_size": state.file_size,
            "chunk_size": state.chunk_size,
            "uploaded_parts": state.uploaded_parts,
            "remaining_parts": self._remaining_parts(state),
        }

    async def _get_state(self, upload_id: str) -> ChunkedUploadState | None:
        data = await self._cache.get(self._redis_key(upload_id))
        if data is None:
            return None
        return ChunkedUploadState.from_json(data)

    def _remaining_parts(self, state: ChunkedUploadState) -> list[int]:
        total = (state.file_size + state.chunk_size - 1) // state.chunk_size
        uploaded = {p["part_number"] for p in state.uploaded_parts}
        return [i for i in range(1, total + 1) if i not in uploaded]
