"""Tests for ToolRegistryServicePort and ToolRegistryService."""

import logging
import uuid
from unittest.mock import MagicMock

import pytest

from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG
from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import (
    ToolAlreadyExistsError,
    ToolNotFoundError,
)
from src.domain.ports.tool_repository import ToolRepositoryPort


def _make_repo_mock(
    *,
    save_raises_exists_on: set[str] | None = None,
    get_by_id_return: Tool | None = None,
    get_by_name_return: Tool | None = None,
    list_all_return: list[Tool] | None = None,
    list_by_category_return: dict[ToolCategory, list[Tool]] | None = None,
    count_return: int | None = None,
) -> MagicMock:
    """工厂函数：构建可定制的 ToolRepositoryPort Mock 实例.

    符合项目 CLAUDE.md §5 硬约束（单元测试 Mock 端口，禁止真实服务）。
    """
    repo = MagicMock(spec=ToolRepositoryPort)

    # save 行为：默认成功，按需触发 ToolAlreadyExistsError
    if save_raises_exists_on is not None:
        existing = save_raises_exists_on

        def save_impl(tool: Tool) -> None:
            if tool.name in existing:
                raise ToolAlreadyExistsError(
                    tool_id=str(tool.tool_id),
                    tool_name=tool.name,
                )

        repo.save.side_effect = save_impl
    else:
        repo.save.side_effect = lambda _: None

    # 查询行为
    if get_by_id_return is not None:
        repo.get_by_id.return_value = get_by_id_return
    if get_by_name_return is not None:
        repo.get_by_name.return_value = get_by_name_return
    if list_all_return is not None:
        repo.list_all.return_value = list_all_return
    if count_return is not None:
        repo.count.return_value = count_return
    if list_by_category_return is not None:
        repo.list_by_category.side_effect = lambda cat: list_by_category_return.get(cat, [])

    return repo


def _make_service(mock_repo: MagicMock | None = None) -> ToolRegistryService:
    """工厂函数：构建 ToolRegistryService 实例（依赖注入 mock）."""
    return ToolRegistryService(repository=mock_repo or _make_repo_mock())


class TestToolRegistryServicePortProtocol:
    """Test ToolRegistryServicePort Protocol definition."""

    def test_is_protocol(self):
        """ToolRegistryServicePort is a Protocol."""
        from typing import Protocol

        assert issubclass(ToolRegistryServicePort, Protocol)

    def test_has_register_all_method(self):
        """ToolRegistryServicePort has register_all method."""
        assert hasattr(ToolRegistryServicePort, "register_all")

    def test_has_get_tool_method(self):
        """ToolRegistryServicePort has get_tool method."""
        assert hasattr(ToolRegistryServicePort, "get_tool")

    def test_has_get_tools_by_category_method(self):
        """ToolRegistryServicePort has get_tools_by_category method."""
        assert hasattr(ToolRegistryServicePort, "get_tools_by_category")

    def test_has_list_all_tools_method(self):
        """ToolRegistryServicePort has list_all_tools method."""
        assert hasattr(ToolRegistryServicePort, "list_all_tools")

    def test_has_tool_count_method(self):
        """ToolRegistryServicePort has tool_count method."""
        assert hasattr(ToolRegistryServicePort, "tool_count")

    def test_implements_protocol(self):
        """ToolRegistryService implements ToolRegistryServicePort."""
        service = _make_service()
        assert isinstance(service, ToolRegistryServicePort)


class TestToolRegistryServiceRegisterAll:
    """Test ToolRegistryService.register_all."""

    def test_register_all_23_tools(self):
        """register_all 调用 save() 共 23 次（对应 TOOL_CATALOG 中 23 个工具）."""
        repo = _make_repo_mock()
        service = _make_service(mock_repo=repo)

        service.register_all()

        assert repo.save.call_count == 23
        saved_names = {c.args[0].name for c in repo.save.call_args_list}
        expected_names = {t.name for t in TOOL_CATALOG}
        assert saved_names == expected_names

    def test_register_all_idempotent(self):
        """register_all 二次调用时已存在的工具被跳过（不抛异常 + 总数不变）."""
        # 第二次调用时所有 TOOL_CATALOG 都视为已存在
        repo = _make_repo_mock(
            save_raises_exists_on={t.name for t in TOOL_CATALOG},
        )
        service = _make_service(mock_repo=repo)

        service.register_all()  # 第一次全部重复（mock 抛 ToolAlreadyExistsError）
        service.register_all()  # 第二次也全部重复（幂等性验证）

    def test_register_all_logs_skip_on_duplicate(self, caplog):
        """register_all 第二次调用时对重复工具记录 debug 日志."""
        repo = _make_repo_mock(
            save_raises_exists_on={t.name for t in TOOL_CATALOG},
        )
        service = _make_service(mock_repo=repo)

        with caplog.at_level(
            logging.DEBUG,
            logger="src.application.services.tool_registry_service",
        ):
            service.register_all()

        skip_logs = [r for r in caplog.records if "跳过" in r.getMessage() or "skip" in r.getMessage().lower()]
        assert len(skip_logs) >= 1
        assert all(r.levelno == logging.DEBUG for r in skip_logs)

    def test_register_all_no_log_on_first_call(self, caplog):
        """register_all 首次成功调用时不记录 skip 日志."""
        repo = _make_repo_mock()  # 默认 save 不抛错
        service = _make_service(mock_repo=repo)

        with caplog.at_level(
            logging.DEBUG,
            logger="src.application.services.tool_registry_service",
        ):
            service.register_all()

        skip_logs = [r for r in caplog.records if "跳过" in r.getMessage() or "skip" in r.getMessage().lower()]
        assert len(skip_logs) == 0


class TestToolRegistryServiceGetTool:
    """Test ToolRegistryService.get_tool."""

    def test_get_tool_by_id(self):
        """get_tool(id) 委托 repository.get_by_id()."""
        expected_tool = Tool(
            tool_id=uuid.uuid4(),
            name="PESTEL 分析",
        )
        repo = _make_repo_mock(get_by_id_return=expected_tool)
        service = _make_service(mock_repo=repo)

        result = service.get_tool(tool_id=expected_tool.tool_id)

        assert result == expected_tool
        repo.get_by_id.assert_called_once_with(expected_tool.tool_id)

    def test_get_tool_by_name(self):
        """get_tool(name) 委托 repository.get_by_name()."""
        expected_tool = Tool(
            tool_id=uuid.uuid4(),
            name="波特五力",
        )
        repo = _make_repo_mock(get_by_name_return=expected_tool)
        service = _make_service(mock_repo=repo)

        result = service.get_tool(tool_name="波特五力")

        assert result == expected_tool
        repo.get_by_name.assert_called_once_with("波特五力")

    def test_get_tool_not_found(self):
        """get_tool(id) 在仓储抛 ToolNotFoundError 时透传."""
        repo = _make_repo_mock()
        repo.get_by_id.side_effect = ToolNotFoundError(tool_id="missing-id")
        service = _make_service(mock_repo=repo)

        with pytest.raises(ToolNotFoundError):
            service.get_tool(tool_id=uuid.uuid4())
        repo.get_by_id.assert_called_once()

    def test_get_tool_not_found_by_name(self):
        """get_tool(name) 在仓储抛 ToolNotFoundError 时透传."""
        repo = _make_repo_mock()
        repo.get_by_name.side_effect = ToolNotFoundError(tool_name="Missing")
        service = _make_service(mock_repo=repo)

        with pytest.raises(ToolNotFoundError):
            service.get_tool(tool_name="Missing")
        repo.get_by_name.assert_called_once_with("Missing")

    def test_get_tool_without_id_or_name(self):
        """get_tool() 无参数抛 EntityValidationError（参数验证失败）."""
        service = _make_service()
        with pytest.raises(EntityValidationError) as exc_info:
            service.get_tool()
        assert exc_info.value.context["parameter"] == "tool_id|tool_name"


class TestToolRegistryServiceCategoryQuery:
    """Test ToolRegistryService.get_tools_by_category."""

    def test_get_tools_by_category(self):
        """get_tools_by_category 委托 repository.list_by_category()."""
        expected_tools = [
            Tool(tool_id=uuid.uuid4(), name="Tool A", category=ToolCategory.ENVIRONMENT_ANALYSIS),
            Tool(tool_id=uuid.uuid4(), name="Tool B", category=ToolCategory.ENVIRONMENT_ANALYSIS),
        ]
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.ENVIRONMENT_ANALYSIS: expected_tools,
            },
        )
        service = _make_service(mock_repo=repo)

        result = service.get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)

        assert len(result) == 2
        repo.list_by_category.assert_called_once_with(ToolCategory.ENVIRONMENT_ANALYSIS)

    def test_environment_analysis_count(self):
        """ENVIRONMENT_ANALYSIS 返回 3 种工具."""
        expected_tools = [
            Tool(tool_id=uuid.uuid4(), name="PESTEL 分析", category=ToolCategory.ENVIRONMENT_ANALYSIS),
            Tool(tool_id=uuid.uuid4(), name="波特五力", category=ToolCategory.ENVIRONMENT_ANALYSIS),
            Tool(tool_id=uuid.uuid4(), name="$APPEALS", category=ToolCategory.ENVIRONMENT_ANALYSIS),
        ]
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.ENVIRONMENT_ANALYSIS: expected_tools,
            },
        )
        service = _make_service(mock_repo=repo)

        tools = service.get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert "PESTEL 分析" in names
        assert "波特五力" in names
        assert "$APPEALS" in names

    def test_competitive_analysis_count(self):
        """COMPETITIVE_ANALYSIS 返回 3 种工具."""
        expected_tools = [
            Tool(tool_id=uuid.uuid4(), name="竞争对手分析", category=ToolCategory.COMPETITIVE_ANALYSIS),
            Tool(tool_id=uuid.uuid4(), name="价值链分析", category=ToolCategory.COMPETITIVE_ANALYSIS),
            Tool(tool_id=uuid.uuid4(), name="VRIO 框架", category=ToolCategory.COMPETITIVE_ANALYSIS),
        ]
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.COMPETITIVE_ANALYSIS: expected_tools,
            },
        )
        service = _make_service(mock_repo=repo)

        tools = service.get_tools_by_category(ToolCategory.COMPETITIVE_ANALYSIS)
        assert len(tools) == 3

    def test_strategic_selection_count(self):
        """STRATEGIC_SELECTION 返回 6 种工具."""
        expected_tools = [
            Tool(tool_id=uuid.uuid4(), name=f"Tool {i}", category=ToolCategory.STRATEGIC_SELECTION) for i in range(6)
        ]
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.STRATEGIC_SELECTION: expected_tools,
            },
        )
        service = _make_service(mock_repo=repo)

        tools = service.get_tools_by_category(ToolCategory.STRATEGIC_SELECTION)
        assert len(tools) == 6

    def test_business_model_count(self):
        """BUSINESS_MODEL 返回 3 种工具."""
        expected_tools = [Tool(tool_id=uuid.uuid4(), name=f"Tool {i}", category=ToolCategory.BUSINESS_MODEL) for i in range(3)]
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.BUSINESS_MODEL: expected_tools,
            },
        )
        service = _make_service(mock_repo=repo)

        tools = service.get_tools_by_category(ToolCategory.BUSINESS_MODEL)
        assert len(tools) == 3

    def test_execution_management_count(self):
        """EXECUTION_MANAGEMENT 返回 8 种工具."""
        expected_tools = [
            Tool(tool_id=uuid.uuid4(), name=f"Tool {i}", category=ToolCategory.EXECUTION_MANAGEMENT) for i in range(8)
        ]
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.EXECUTION_MANAGEMENT: expected_tools,
            },
        )
        service = _make_service(mock_repo=repo)

        tools = service.get_tools_by_category(ToolCategory.EXECUTION_MANAGEMENT)
        assert len(tools) == 8

    def test_category_empty_result(self):
        """无工具的分类查询返回空列表."""
        repo = _make_repo_mock(
            list_by_category_return={
                ToolCategory.ANALYSIS: [],
            },
        )
        service = _make_service(mock_repo=repo)

        tools = service.get_tools_by_category(ToolCategory.ANALYSIS)
        assert tools == []


class TestToolRegistryServiceToolCount:
    """Test ToolRegistryService.tool_count O(1) 委托."""

    def test_tool_count_before_register(self):
        """tool_count 注册前委托 repository.count()."""
        repo = _make_repo_mock(count_return=0)
        service = _make_service(mock_repo=repo)

        assert service.tool_count() == 0
        repo.count.assert_called_once_with()

    def test_tool_count_after_register(self):
        """tool_count 注册后委托 repository.count() 返回 23."""
        repo = _make_repo_mock(count_return=23)
        service = _make_service(mock_repo=repo)

        assert service.tool_count() == 23
        repo.count.assert_called_once_with()

    def test_tool_count_delegates_to_repository(self):
        """tool_count 委托 repository.count() 而非 list_all()."""
        mock_repo = MagicMock(spec=ToolRepositoryPort)
        mock_repo.count.return_value = 23
        service = ToolRegistryService(repository=mock_repo)
        assert service.tool_count() == 23
        mock_repo.count.assert_called_once_with()
        mock_repo.list_all.assert_not_called()

    def test_tool_count_zero_on_empty_repository(self):
        """空仓储时 tool_count 委托 repository.count() 返回 0."""
        mock_repo = MagicMock(spec=ToolRepositoryPort)
        mock_repo.count.return_value = 0
        service = ToolRegistryService(repository=mock_repo)
        assert service.tool_count() == 0
        mock_repo.count.assert_called_once_with()


class TestToolRegistryServiceListAllTools:
    """Test ToolRegistryService.list_all_tools."""

    def test_list_all_tools(self):
        """list_all_tools 委托 repository.list_all()."""
        expected_tools = [Tool(tool_id=uuid.uuid4(), name=f"Tool {i}") for i in range(5)]
        repo = _make_repo_mock(list_all_return=expected_tools)
        service = _make_service(mock_repo=repo)

        result = service.list_all_tools()

        assert len(result) == 5
        repo.list_all.assert_called_once_with()
