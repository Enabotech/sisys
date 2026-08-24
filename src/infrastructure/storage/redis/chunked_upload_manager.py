"""基础设施层分片上传状态管理器

通过 L1CachePort（Redis）管理分片上传状态，支持断点续传。
JSON 序列化存储结构化状态，Redis 分布式锁保证跨进程并发安全。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.ports.l1_cache import L1CachePort
from src.domain.value_objects.upload_limits import CHUNKED_UPLOAD_TTL, get_chunk_size

_T = TypeVar("_T")

# Redis key 前缀
_CHUNKED_UPLOAD_PREFIX = "chunked_upload:"
_LOCK_PREFIX = "chunked_upload_lock:"
_LOCK_TTL = 30  # 分布式锁 TTL（秒）


class ChunkedUploadState:
    """分片上传状态数据结构"""

    def __init__(
        self,
        upload_id: str,
        filename: str,
        file_size: int,
        chunk_size: int,
        uploaded_parts: list[dict[str, Any]] | None = None,
        minio_upload_id: str | None = None,
        object_key: str | None = None,
        metadata: str | None = None,
    ) -> None:
        self.upload_id = upload_id
        self.filename = filename
        self.file_size = file_size
        self.chunk_size = chunk_size
        self.uploaded_parts = uploaded_parts or []
        self.minio_upload_id = minio_upload_id
        self.object_key = object_key
        self.metadata = metadata

    def to_json(self) -> str:
        return json.dumps(
            {
                "upload_id": self.upload_id,
                "filename": self.filename,
                "file_size": self.file_size,
                "chunk_size": self.chunk_size,
                "uploaded_parts": self.uploaded_parts,
                "minio_upload_id": self.minio_upload_id,
                "object_key": self.object_key,
                "metadata": self.metadata,
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
            minio_upload_id=obj.get("minio_upload_id"),
            object_key=obj.get("object_key"),
            metadata=obj.get("metadata"),
        )


class ChunkedUploadManager:
    """分片上传状态管理器

    通过 L1CachePort 操作 Redis，使用 JSON 序列化存储分片状态。
    Redis 分布式锁保证跨进程并发安全（多 Worker 部署）。
    """

    # 进程内协程锁仅用于保护 _lock_owners 字典写入，避免 asyncio 竞态
    _owner_lock: asyncio.Lock = asyncio.Lock()
    _lock_owners: dict[str, str] = {}

    def __init__(self, cache: L1CachePort) -> None:
        self._cache = cache

    async def _acquire_lock(self, upload_id: str) -> bool:
        """获取 Redis 分布式锁（SET NX）

        Returns:
            True 表示成功获取锁，False 表示锁已被其他进程持有
        """
        lock_key = f"{_LOCK_PREFIX}{upload_id}"
        owner = uuid.uuid4().hex
        acquired = await self._cache.set_nx(lock_key, owner, ttl=_LOCK_TTL)
        if acquired:
            async with self._owner_lock:
                self._lock_owners[upload_id] = owner
        return acquired

    async def _release_lock(self, upload_id: str) -> None:
        """释放 Redis 分布式锁（仅释放自己的锁，避免误删）"""
        async with self._owner_lock:
            owner = self._lock_owners.pop(upload_id, None)
        if owner is None:
            return
        lock_key = f"{_LOCK_PREFIX}{upload_id}"
        # Lua 脚本确保原子释放：仅当 owner 匹配时删除
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        end
        return 0
        """
        await self._cache.eval(lua_script, keys=[lock_key], args=[owner])

    async def _run_locked(self, upload_id: str, fn: Callable[[], Awaitable[_T]]) -> _T:
        """在分布式锁保护下执行操作

        使用 Redis SET NX 实现分布式锁，超时重试机制保证可用性。

        Args:
            upload_id: 上传会话 ID
            fn: 需要加锁执行的异步函数

        Returns:
            fn 的返回值
        """
        retries = 3
        for attempt in range(retries):
            if await self._acquire_lock(upload_id):
                try:
                    return await fn()
                finally:
                    await self._release_lock(upload_id)
            else:
                if attempt < retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
        raise ConflictError(message=f"upload_id {upload_id} 正被其他进程处理，请稍后重试")

    def _redis_key(self, upload_id: str) -> str:
        return f"{_CHUNKED_UPLOAD_PREFIX}{upload_id}"

    async def init_upload(
        self,
        filename: str,
        file_size: int,
        minio_upload_id: str | None = None,
        object_key: str | None = None,
        metadata: str | None = None,
    ) -> dict[str, Any]:
        """初始化分片上传

        Args:
            filename: 文件名
            file_size: 文件总大小（字节）
            minio_upload_id: MinIO 分片上传会话 ID
            object_key: MinIO 对象键
            metadata: 文档元数据 JSON 字符串（可选，用于持久化）

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
            minio_upload_id=minio_upload_id,
            object_key=object_key,
            metadata=metadata,
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
        """记录已上传的分片（支持幂等重试）

        分布式锁保护 + 幂等检查：客户端重试已成功的分片不会报错。

        Args:
            upload_id: 上传会话 ID
            part_number: 分片编号
            etag: 分片 ETag

        Returns:
            {"uploaded_parts": int}

        Raises:
            NotFoundError: upload_id 不存在
            ConflictError: 锁冲突，其他进程正在处理
        """

        async def _do_upload_part() -> dict[str, Any]:
            state = await self._get_state(upload_id)
            if state is None:
                raise NotFoundError(message=f"upload_id {upload_id} 不存在或已过期")

            # 幂等检查：如果 part_number 已存在，直接返回成功
            for p in state.uploaded_parts:
                if p["part_number"] == part_number:
                    return {"uploaded_parts": len(state.uploaded_parts)}

            # 校验分片顺序：next 必须是已上传分片数 + 1
            expected_next = len(state.uploaded_parts) + 1
            if part_number != expected_next:
                raise ConflictError(message=f"分片乱序：期望第 {expected_next} 个分片，实际收到第 {part_number} 个")

            state.uploaded_parts.append({"part_number": part_number, "etag": etag})
            await self._cache.set(
                self._redis_key(upload_id),
                state.to_json(),
                ttl=CHUNKED_UPLOAD_TTL,
            )
            return {"uploaded_parts": len(state.uploaded_parts)}

        return await self._run_locked(upload_id, _do_upload_part)

    async def complete_upload(self, upload_id: str) -> ChunkedUploadState:
        """完成分片上传（分布式锁保护）

        Args:
            upload_id: 上传会话 ID

        Returns:
            ChunkedUploadState 完整状态

        Raises:
            NotFoundError: upload_id 不存在
        """

        async def _do_complete() -> ChunkedUploadState:
            state = await self._get_state(upload_id)
            if state is None:
                raise NotFoundError(message=f"upload_id {upload_id} 不存在或已过期")

            await self._cache.delete(self._redis_key(upload_id))
            return state

        return await self._run_locked(upload_id, _do_complete)

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

    async def get_multipart_info(self, upload_id: str) -> dict[str, str | None] | None:
        """获取 MinIO 分片上传上下文信息

        Args:
            upload_id: 上传会话 ID

        Returns:
            {"minio_upload_id": str, "object_key": str} 或 None
        """
        state = await self._get_state(upload_id)
        if state is None:
            return None
        return {
            "minio_upload_id": state.minio_upload_id,
            "object_key": state.object_key,
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
