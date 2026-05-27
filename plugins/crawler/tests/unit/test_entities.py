"""实体与值对象单元测试

TDD 阶段：绿
验证 CrawlTask/CrawledFile/CrawlResult 的基本行为

"""

from __future__ import annotations

import os
import tempfile

import pytest

from plugins.crawler.core.entities import CrawledFile, CrawlResult, CrawlTask
from plugins.crawler.core.value_objects import CrawlStatus, FileMetadata, NamingCandidate


class TestCrawlStatus:
    """CrawlStatus 枚举测试"""

    def test_all_statuses(self) -> None:
        """应包含 5 种状态"""
        assert len(CrawlStatus) == 5
        assert CrawlStatus.PENDING.value == "pending"
        assert CrawlStatus.COMPLETED.value == "completed"


class TestNamingCandidate:
    """NamingCandidate 值对象测试"""

    def test_frozen(self) -> None:
        """NamingCandidate 应不可变"""
        candidate = NamingCandidate(filename="test.pdf", strategy_name="hash", confidence=0.5)

        with pytest.raises(AttributeError):
            setattr(candidate, "filename", "other.pdf")


class TestFileMetadata:
    """FileMetadata 值对象测试"""

    def test_default_empty(self) -> None:
        """默认值应全为空"""
        meta = FileMetadata()
        assert meta.title == ""
        assert meta.author == ""

    def test_frozen(self) -> None:
        """FileMetadata 应不可变"""
        meta = FileMetadata(title="test")

        with pytest.raises(AttributeError):
            setattr(meta, "title", "other")


class TestCrawlTask:
    """CrawlTask 实体测试"""

    def test_auto_task_id(self) -> None:
        """应自动生成 task_id"""
        task = CrawlTask()
        assert task.task_id
        assert len(task.task_id) == 36  # UUID 格式

    def test_frozen(self) -> None:
        """CrawlTask 应不可变"""
        task = CrawlTask()

        with pytest.raises(AttributeError):
            setattr(task, "domains", ("example.com",))

    def test_from_dict(self) -> None:
        """应从字典创建"""
        data = {
            "domains": ["example.com"],
            "seed_urls": ["https://example.com/docs"],
            "max_depth": 5,
            "allowed_extensions": ["pdf", "docx"],
            "url_patterns": {"include": ["/docs/"], "exclude": ["/login"]},
        }
        task = CrawlTask.from_dict(data)
        assert task.domains == ("example.com",)
        assert task.seed_urls == ("https://example.com/docs",)
        assert task.max_depth == 5
        assert task.allowed_extensions == ("pdf", "docx")
        assert task.url_include == ("/docs/",)
        assert task.url_exclude == ("/login",)


class TestCrawledFile:
    """CrawledFile 实体测试"""

    def test_required_fields(self) -> None:
        """必填字段应正确赋值"""
        f = CrawledFile(
            url="https://example.com/test.pdf",
            file_path="./test.pdf",
            file_name="test.pdf",
            file_size=1024,
            content_type="application/pdf",
            file_extension="pdf",
            smart_name="Test Document.pdf",
            naming_strategy="metadata_title",
            task_id="task-1",
        )
        assert f.url == "https://example.com/test.pdf"
        assert f.file_size == 1024
        assert f.parent_url == ""  # 默认值

    def test_frozen(self) -> None:
        """CrawledFile 应不可变"""
        f = CrawledFile(
            url="u",
            file_path="p",
            file_name="n",
            file_size=0,
            content_type="c",
            file_extension="e",
            smart_name="s",
            naming_strategy="strat",
            task_id="t",
        )

        with pytest.raises(AttributeError):
            setattr(f, "url", "other")


class TestCrawlResult:
    """CrawlResult 实体测试"""

    def test_initial_state(self) -> None:
        """初始状态应为 PENDING"""
        result = CrawlResult(task_id="t1")
        assert result.status == CrawlStatus.PENDING
        assert result.files == []
        assert result.total_size_bytes == 0

    def test_add_file(self) -> None:
        """添加文件应累加大小"""
        result = CrawlResult(task_id="t1")
        f = CrawledFile(
            url="u",
            file_path="p",
            file_name="n",
            file_size=100,
            content_type="c",
            file_extension="e",
            smart_name="s",
            naming_strategy="strat",
            task_id="t1",
        )
        result.add_file(f)
        assert len(result.files) == 1
        assert result.total_size_bytes == 100

    def test_mark_running(self) -> None:
        """mark_running 应设置状态和时间"""
        result = CrawlResult(task_id="t1")
        result.mark_running()
        assert result.status == CrawlStatus.RUNNING
        assert result.started_at is not None

    def test_mark_completed(self) -> None:
        """mark_completed 应设置状态和时间"""
        result = CrawlResult(task_id="t1")
        result.mark_completed()
        assert result.status == CrawlStatus.COMPLETED
        assert result.completed_at is not None

    def test_to_dict(self) -> None:
        """to_dict 应包含所有关键字段"""
        result = CrawlResult(task_id="t1")
        result.mark_running()
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "running"
        assert d["files_crawled"] == 0

    # ── 认证配置测试 ──

    def test_default_auth_fields(self) -> None:
        """默认认证字段应为空"""
        task = CrawlTask()
        assert task.auth_storage_state_path == ""
        assert task.auth_headers == {}

    def test_from_dict_with_auth(self) -> None:
        """from_dict 应正确映射认证字段"""
        auth_path = os.path.join(tempfile.gettempdir(), "auth.json")
        data = {
            "domains": ["example.com"],
            "auth_storage_state_path": auth_path,
            "auth_headers": {"Authorization": "Bearer token"},
        }
        task = CrawlTask.from_dict(data)
        assert task.auth_storage_state_path == auth_path
        assert task.auth_headers == {"Authorization": "Bearer token"}

    def test_from_dict_without_auth(self) -> None:
        """from_dict 不传认证字段应使用默认值"""
        data = {"domains": ["example.com"]}
        task = CrawlTask.from_dict(data)
        assert task.auth_storage_state_path == ""
        assert task.auth_headers == {}
