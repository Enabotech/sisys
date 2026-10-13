"""Crawler API 响应模型单元测试

验证 _task_to_response 将 CrawlResult（含 CrawledFile 明细）完整映射为
API 响应——files 数组是 SISYS 摄取链（ChinaNBSAdapter 消费）的事实源契约。
"""

from __future__ import annotations

from plugins.crawler.api import _task_to_response
from plugins.crawler.core.entities import CrawledFile, CrawlResult
from plugins.crawler.core.value_objects import CrawlStatus


def _make_result_with_files() -> CrawlResult:
    """构造含两个文件明细的已完成 CrawlResult"""
    result = CrawlResult(task_id="task-001")
    result.mark_running()
    result.add_file(
        CrawledFile(
            url="https://www.stats.gov.cn/sj/zxfb/a.pdf",
            file_path="downloads/tmp123.pdf",
            file_name="a.pdf",
            file_size=1024,
            content_type="application/pdf",
            file_extension="pdf",
            smart_name="2026年统计公报.pdf",
            naming_strategy="link_text",
            task_id="task-001",
            parent_url="https://www.stats.gov.cn/sj/zxfb/",
            page_title="最新发布",
            link_text="2026年统计公报",
            stored_path="/data/crawl_output/2026年统计公报.pdf",
        )
    )
    result.add_failed_url("https://www.stats.gov.cn/broken.xlsx")
    result.mark_completed()
    return result


class TestTaskToResponse:
    """_task_to_response 契约映射测试"""

    def test_files_detail_in_response(self) -> None:
        """files 明细数组应完整出现在响应中（SISYS 摄取链事实源）"""
        response = _task_to_response(_make_result_with_files())

        assert response.files_crawled == 1
        assert response.files_failed == 1
        assert len(response.files) == 1
        file_entry = response.files[0]
        assert file_entry.url == "https://www.stats.gov.cn/sj/zxfb/a.pdf"
        assert file_entry.smart_name == "2026年统计公报.pdf"
        assert file_entry.stored_path == "/data/crawl_output/2026年统计公报.pdf"
        assert file_entry.page_title == "最新发布"
        assert file_entry.link_text == "2026年统计公报"
        assert file_entry.parent_url == "https://www.stats.gov.cn/sj/zxfb/"
        assert file_entry.file_size == 1024
        assert file_entry.file_extension == "pdf"

    def test_running_task_empty_files(self) -> None:
        """RUNNING 任务的 files 为空数组（响应结构恒定）"""
        result = CrawlResult(task_id="task-002")
        result.mark_running()
        response = _task_to_response(result)

        assert response.status == CrawlStatus.RUNNING.value
        assert response.files == []
        assert response.files_crawled == 0

    def test_response_model_serializable(self) -> None:
        """响应模型可 JSON 序列化（API 出口契约）"""
        response = _task_to_response(_make_result_with_files())
        data = response.model_dump()

        assert isinstance(data["files"], list)
        assert data["files"][0]["stored_path"] == "/data/crawl_output/2026年统计公报.pdf"
