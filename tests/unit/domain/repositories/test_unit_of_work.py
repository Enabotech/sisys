"""Task 6 TDD Tests — UnitOfWork (AC-6)."""

from __future__ import annotations

from abc import ABC


class TestUnitOfWorkInterface:
    """UnitOfWork abstract interface tests."""

    def test_unit_of_work_is_abc(self):
        """UnitOfWork should be an abstract base class."""
        from src.domain.repositories.unit_of_work import UnitOfWork

        assert issubclass(UnitOfWork, ABC)

    def test_unit_of_work_has_begin_method(self):
        """UnitOfWork should declare begin() method."""
        from src.domain.repositories.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "begin")

    def test_unit_of_work_has_commit_method(self):
        """UnitOfWork should declare commit() method."""
        from src.domain.repositories.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "commit")

    def test_unit_of_work_has_rollback_method(self):
        """UnitOfWork should declare rollback() method."""
        from src.domain.repositories.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "rollback")

    def test_unit_of_work_has_close_method(self):
        """UnitOfWork should declare close() method."""
        from src.domain.repositories.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "close")


class TestPostgreSQLUnitOfWork:
    """PostgreSQLUnitOfWork implementation tests."""

    def test_postgresql_unit_of_work_can_be_instantiated(self):
        """PostgreSQLUnitOfWork can be instantiated with session."""
        from unittest import mock

        from src.domain.repositories.unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        uow = PostgreSQLUnitOfWork(session=mock_session)
        assert uow is not None

    def test_begin_starts_transaction(self):
        """begin() should start a transaction."""
        from unittest import mock

        from src.domain.repositories.unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        uow = PostgreSQLUnitOfWork(session=mock_session)

        import asyncio

        asyncio.get_event_loop().run_until_complete(uow.begin())
        mock_session.begin.assert_called_once()

    def test_commit_commits_transaction(self):
        """commit() should commit the transaction."""
        from unittest import mock

        from src.domain.repositories.unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        uow = PostgreSQLUnitOfWork(session=mock_session)

        import asyncio

        asyncio.get_event_loop().run_until_complete(uow.commit())
        mock_session.commit.assert_called_once()

    def test_rollback_rolls_back_transaction(self):
        """rollback() should roll back the transaction."""
        from unittest import mock

        from src.domain.repositories.unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        uow = PostgreSQLUnitOfWork(session=mock_session)

        import asyncio

        asyncio.get_event_loop().run_until_complete(uow.rollback())
        mock_session.rollback.assert_called_once()

    def test_close_closes_session(self):
        """close() should close the session."""
        from unittest import mock

        from src.domain.repositories.unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        uow = PostgreSQLUnitOfWork(session=mock_session)

        import asyncio

        asyncio.get_event_loop().run_until_complete(uow.close())
        mock_session.close.assert_called_once()

    def test_context_manager_protocol(self):
        """UnitOfWork should support context manager protocol."""
        from unittest import mock

        from src.domain.repositories.unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        uow = PostgreSQLUnitOfWork(session=mock_session)

        import asyncio

        # Test __aenter__ and __aexit__
        async def test_cm():
            async with uow:
                pass

        asyncio.get_event_loop().run_until_complete(test_cm())
