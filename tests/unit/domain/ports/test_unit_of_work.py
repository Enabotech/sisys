"""Task 6 TDD Tests — UnitOfWork (AC-6)."""

from __future__ import annotations

from abc import ABC

import pytest

from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class TestUnitOfWorkInterface:
    """UnitOfWork abstract interface tests."""

    def test_unit_of_work_is_abc(self):
        """UnitOfWork should be an abstract base class."""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert issubclass(UnitOfWork, ABC)

    def test_unit_of_work_has_begin_method(self):
        """UnitOfWork should declare begin() method."""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "begin")

    def test_unit_of_work_has_commit_method(self):
        """UnitOfWork should declare commit() method."""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "commit")

    def test_unit_of_work_has_rollback_method(self):
        """UnitOfWork should declare rollback() method."""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "rollback")

    def test_unit_of_work_has_close_method(self):
        """UnitOfWork should declare close() method."""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "close")


class TestPostgreSQLUnitOfWork:
    """PostgreSQLUnitOfWork implementation tests."""

    def test_postgresql_unit_of_work_can_be_instantiated(self):
        """PostgreSQLUnitOfWork can be instantiated with session."""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()
            assert uow is not None
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_begin_starts_transaction(self):
        """begin() should start a transaction."""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.begin()
            mock_session.begin.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_commit_commits_transaction(self):
        """commit() should commit the transaction."""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.commit()
            mock_session.commit.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_rollback_rolls_back_transaction(self):
        """rollback() should roll back the transaction."""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.rollback()
            mock_session.rollback.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        """close() should close the session."""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.close()
            mock_session.close.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self):
        """UnitOfWork should support context manager protocol."""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            async with uow:
                pass
        finally:
            reset_session(token)
