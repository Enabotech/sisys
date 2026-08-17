"""StalenessWeightService 降权服务单元测试

验证陈旧数据降权计算、重排序和降级策略。
遵循 Mock 端口策略（仅单元测试允许）。
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.application.services.staleness_weight_service import (
    STALE_WEIGHT_FACTOR,
    StalenessWeightService,
)
from src.domain.ports.archive_repository import ArchiveRepositoryPort
from src.domain.ports.l3_vector import SearchResult


def _make_search_result(
    result_id: str = "strategic_archive:11111111-1111-1111-1111-111111111111",
    score: float = 0.9,
    is_stale: bool | None = None,
    stale_reason: str | None = None,
    archive_id: str | None = "11111111-1111-1111-1111-111111111111",
) -> SearchResult:
    """创建测试用 SearchResult"""
    payload: dict[str, Any] = {"archive_id": archive_id} if archive_id else {}
    if is_stale is not None:
        payload["is_stale"] = is_stale
    if stale_reason is not None:
        payload["stale_reason"] = stale_reason
    return SearchResult(
        id=result_id,
        score=score,
        payload=payload,
    )


def _make_repo() -> Any:
    """创建 Mock 档案仓储"""
    return AsyncMock(spec=ArchiveRepositoryPort)


class TestStalenessWeightService:
    """StalenessWeightService 核心降权逻辑测试"""

    def test_constructor_accepts_none_repo(self) -> None:
        """构造函数接受 archive_repo=None"""
        service = StalenessWeightService(archive_repo=None)
        assert service._archive_repo is None

    def test_constructor_accepts_repo(self) -> None:
        """构造函数接受 archive_repo"""
        repo = _make_repo()
        service = StalenessWeightService(archive_repo=repo)
        assert service._archive_repo is repo

    @pytest.mark.asyncio
    async def test_stale_result_score_reduced(self) -> None:
        """is_stale=True 的结果分数 score *= STALE_WEIGHT_FACTOR"""
        service = StalenessWeightService(archive_repo=None)
        results = [
            _make_search_result(result_id="a", score=0.9, is_stale=True),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert len(weighted) == 1
        assert weighted[0]["score"] == pytest.approx(0.9 * STALE_WEIGHT_FACTOR)

    @pytest.mark.asyncio
    async def test_fresh_result_score_unchanged(self) -> None:
        """is_stale=False 的结果分数不变"""
        service = StalenessWeightService(archive_repo=None)
        results = [
            _make_search_result(result_id="a", score=0.9, is_stale=False),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert len(weighted) == 1
        assert weighted[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_no_is_stale_with_repo_fallback(self) -> None:
        """payload 无 is_stale 标记但 archive_repo 可用时，通过 is_stale() 判断"""
        from datetime import UTC, datetime

        from src.domain.entities.strategic_archive import StrategicArchive

        repo = _make_repo()
        # 构造一个陈旧档案（valid_until 已过期）
        archive = StrategicArchive(
            archive_id=cast(Any, "11111111-1111-1111-1111-111111111111"),
            plan_id=cast(Any, "22222222-2222-2222-2222-222222222222"),
            valid_until=datetime(2021, 1, 1, tzinfo=UTC),
        )
        service = StalenessWeightService(archive_repo=repo)
        repo.find.return_value = [archive]

        results = [
            _make_search_result(
                result_id="strategic_archive:11111111-1111-1111-1111-111111111111",
                score=0.9,
                is_stale=None,  # 无 is_stale 标记
                archive_id="11111111-1111-1111-1111-111111111111",
            ),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert len(weighted) == 1
        assert weighted[0]["score"] == pytest.approx(0.9 * STALE_WEIGHT_FACTOR)
        assert repo.find.called

    @pytest.mark.asyncio
    async def test_no_is_stale_no_repo_skip(self) -> None:
        """archive_repo 不可用且 payload 无 is_stale 标记时跳过降权"""
        service = StalenessWeightService(archive_repo=None)
        results = [
            _make_search_result(result_id="a", score=0.9, is_stale=None),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert len(weighted) == 1
        assert weighted[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_archive_deleted_skipped(self) -> None:
        """archive_repo.get_by_id 返回 None 时视为非陈旧，score 不变"""
        repo = _make_repo()
        repo.find.return_value = []  # 找不到对应档案
        service = StalenessWeightService(archive_repo=repo)

        results = [
            _make_search_result(
                result_id="a",
                score=0.9,
                is_stale=None,
                archive_id="11111111-1111-1111-1111-111111111111",
            ),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert len(weighted) == 1
        assert weighted[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        """空结果列表返回空列表"""
        service = StalenessWeightService(archive_repo=None)
        weighted = await service.apply_staleness_weight([])
        assert weighted == []

    @pytest.mark.asyncio
    async def test_all_fresh_scores_unchanged(self) -> None:
        """所有结果均非陈旧时分数不变、顺序不变"""
        service = StalenessWeightService(archive_repo=None)
        results = [
            _make_search_result(result_id="a", score=0.9, is_stale=False),
            _make_search_result(result_id="b", score=0.8, is_stale=False),
            _make_search_result(result_id="c", score=0.7, is_stale=False),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert [r["score"] for r in weighted] == [0.9, 0.8, 0.7]
        assert [r["id"] for r in weighted] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_mixed_stale_and_fresh_sorting(self) -> None:
        """混合陈旧/新鲜结果：陈旧数据降权后位于新鲜数据之后"""
        service = StalenessWeightService(archive_repo=None)
        # 新鲜 0.9 > 陈旧 0.8*0.5=0.4 > 新鲜 0.3... 但需要检查排序
        results = [
            _make_search_result(result_id="a", score=0.9, is_stale=False),  # fresh 0.9
            _make_search_result(result_id="b", score=0.8, is_stale=True),  # stale 0.4
            _make_search_result(result_id="c", score=0.7, is_stale=True),  # stale 0.35
            _make_search_result(result_id="d", score=0.5, is_stale=False),  # fresh 0.5
        ]
        weighted = await service.apply_staleness_weight(results)
        # 期望排序：a(0.9) > d(0.5) > b(0.4) > c(0.35)
        assert len(weighted) == 4
        assert weighted[0]["id"] == "a"  # 0.9
        assert weighted[1]["id"] == "d"  # 0.5
        assert weighted[2]["id"] == "b"  # 0.4
        assert weighted[3]["id"] == "c"  # 0.35

    @pytest.mark.asyncio
    async def test_tie_breaking_by_id(self) -> None:
        """分数相同时按 id 字典序确定性排序"""
        service = StalenessWeightService(archive_repo=None)
        # 两个 stale 结果分数相同（0.8*0.5=0.4）
        results = [
            _make_search_result(result_id="b", score=0.8, is_stale=True),
            _make_search_result(result_id="a", score=0.8, is_stale=True),
        ]
        weighted = await service.apply_staleness_weight(results)
        # 分数相同：0.4 vs 0.4，按 id 升序：a < b
        assert weighted[0]["id"] == "a"
        assert weighted[1]["id"] == "b"

    @pytest.mark.asyncio
    async def test_batch_query_avoids_n_plus_one(self) -> None:
        """批量收集缺失标记的 archive_id，一次查询批量判断"""
        from datetime import UTC, datetime

        from src.domain.entities.strategic_archive import StrategicArchive

        repo = _make_repo()
        # 两个档案都是陈旧的
        archive1 = StrategicArchive(
            archive_id=cast(Any, "11111111-1111-1111-1111-111111111111"),
            plan_id=cast(Any, "22222222-2222-2222-2222-222222222222"),
            valid_until=datetime(2021, 1, 1, tzinfo=UTC),
        )
        archive2 = StrategicArchive(
            archive_id=cast(Any, "33333333-3333-3333-3333-333333333333"),
            plan_id=cast(Any, "44444444-4444-4444-4444-444444444444"),
            valid_until=datetime(2020, 6, 1, tzinfo=UTC),
        )
        repo.find.return_value = [archive1, archive2]
        service = StalenessWeightService(archive_repo=repo)

        results = [
            _make_search_result(
                result_id="strategic_archive:11111111-1111-1111-1111-111111111111",
                score=0.9,
                is_stale=None,
                archive_id="11111111-1111-1111-1111-111111111111",
            ),
            _make_search_result(
                result_id="strategic_archive:33333333-3333-3333-3333-333333333333",
                score=0.8,
                is_stale=None,
                archive_id="33333333-3333-3333-3333-333333333333",
            ),
        ]
        weighted = await service.apply_staleness_weight(results)
        # 两次降权，一次 find 调用（批量）
        assert repo.find.call_count == 1
        assert len(weighted) == 2
        assert weighted[0]["score"] == pytest.approx(0.9 * STALE_WEIGHT_FACTOR)
        assert weighted[1]["score"] == pytest.approx(0.8 * STALE_WEIGHT_FACTOR)

    @pytest.mark.asyncio
    async def test_no_archive_id_in_payload_skips(self) -> None:
        """payload 中无 archive_id 字段时跳过降权"""
        service = StalenessWeightService(archive_repo=None)
        results = [
            SearchResult(
                id="some-other-point",
                score=0.9,
                payload={},  # 无 archive_id
            ),
        ]
        weighted = await service.apply_staleness_weight(results)
        assert len(weighted) == 1
        assert weighted[0]["score"] == 0.9
