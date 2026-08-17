"""应用层陈旧数据降权服务模块

为战略档案向量检索结果提供陈旧性降权功能。
通过对检索结果中的陈旧数据应用降权因子，降低其排序分数，确保新鲜数据优先展示。

设计决策：
- 降权因子为模块级常量 STALE_WEIGHT_FACTOR = 0.5
- 降权后按 (-score, id) 降序重排序，确保确定性排序
- 支持 payload 中 is_stale 标记直接判断（由 FactBecameStale 事件处理器写入 L3）
- 支持兜底查询：通过 archive_repo.find() 批量查询 L2 判断（archive_repo 可用时）
- 适用集合：strategic_archive collection（payload 含 archive_id 字段）
"""

from __future__ import annotations

import logging

from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.l3_vector import SearchResult

logger = logging.getLogger(__name__)

# 降权因子常量：陈旧数据分数乘以 0.5
STALE_WEIGHT_FACTOR = 0.5


class StalenessWeightService:
    """陈旧数据降权服务

    对战略档案向量检索结果执行陈旧性降权处理。
    通过 L3 payload 中的 is_stale 标记或 L2 兜底查询判断陈旧性，
    对陈旧数据应用降权因子后重排序。
    """

    def __init__(
        self,
        archive_repo: ArchiveRepositoryPort | None = None,
    ) -> None:
        """初始化陈旧数据降权服务

        Args:
            archive_repo: 档案仓储端口（可选，None 时跳过兜底查询）
        """
        self._archive_repo = archive_repo

    async def apply_staleness_weight(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """对检索结果列表执行陈旧性降权

        降权逻辑：
        1. payload 中 is_stale=True 的结果分数 *= STALE_WEIGHT_FACTOR
        2. payload 中无 is_stale 标记但 archive_repo 可用时，批量查询 L2 判断
        3. archive_repo 不可用且无标记时跳过降权
        4. 降权后按 (-score, id) 降序重排序

        Args:
            results: 检索结果列表（SearchResult 列表）

        Returns:
            降权后的结果列表（长度不变，只调整 score 和顺序）
        """
        if not results:
            return []

        # 第一步：为每个结果计算陈旧性
        staleness_map: dict[str, bool] = {}
        missing_ids: list[str] = []

        for r in results:
            payload = r.get("payload", {}) if isinstance(r, dict) else {}
            is_stale = payload.get("is_stale") if isinstance(payload, dict) else None
            if is_stale is True:
                staleness_map[str(r["id"])] = True
            elif is_stale is False:
                staleness_map[str(r["id"])] = False
            else:
                # 无 is_stale 标记，加入兜底查询列表
                archive_id = payload.get("archive_id") if isinstance(payload, dict) else None
                if archive_id and self._archive_repo is not None:
                    missing_ids.append(str(archive_id))
                staleness_map[str(r["id"])] = False

        # 第二步：批量兜底查询（避免 N+1）
        if missing_ids and self._archive_repo is not None:
            try:
                from uuid import UUID

                uuids = [UUID(aid) for aid in missing_ids if self._is_valid_uuid(aid)]
                if uuids:
                    query = ArchiveQuery(archive_ids=uuids, limit=1000)
                    archives = await self._archive_repo.find(query)
                    archive_stale_map: dict[str, bool] = {}
                    for a in archives:
                        archive_stale_map[str(a.archive_id)] = a.is_stale()

                    # 更新缺失标记的结果
                    for r in results:
                        rid = str(r["id"])
                        if rid in staleness_map and not staleness_map[rid]:
                            payload = r.get("payload", {}) if isinstance(r, dict) else {}
                            aid = payload.get("archive_id") if isinstance(payload, dict) else None
                            if aid and archive_stale_map.get(str(aid)):
                                staleness_map[rid] = True
            except Exception as e:
                logger.warning("Staleness weight batch query failed: %s", e)

        # 第三步：应用降权因子
        weighted: list[SearchResult] = []
        for r in results:
            rid = str(r["id"])
            if staleness_map.get(rid):
                new_score = r["score"] * STALE_WEIGHT_FACTOR
                weighted.append(SearchResult(id=r["id"], score=new_score, payload=r.get("payload", {})))
            else:
                weighted.append(r)

        # 第四步：按 (-score, id) 降序重排序
        weighted.sort(key=lambda x: (-x["score"], str(x["id"])))

        return weighted

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """检查字符串是否为有效 UUID"""
        try:
            from uuid import UUID

            UUID(value)
            return True
        except (ValueError, AttributeError):
            return False


__all__ = [
    "STALE_WEIGHT_FACTOR",
    "StalenessWeightService",
]
