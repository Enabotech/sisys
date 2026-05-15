"""Architecture validation tests for UoW transaction boundary.

Validates hexagonal architecture compliance and transaction boundary enforcement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

ROOT = Path(__file__).parents[5]


class TestUoWTransactionBoundary:
    """Validates transaction boundary enforcement + hexagonal architecture compliance."""

    def test_uow_provides_session_property(self) -> None:
        """UoW provides session property for EventHandler to extract."""
        from unittest.mock import MagicMock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
            PostgreSQLUnitOfWork,
        )

        mock_session = MagicMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            assert hasattr(uow, "session")
        finally:
            reset_session(token)

    def test_uow_prevents_double_commit_on_same_instance(self) -> None:
        """Guard prevents duplicate commit on the same UoW instance."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from src.domain.exceptions import InvalidStateError
        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
            PostgreSQLUnitOfWork,
        )

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.begin = AsyncMock()

        async def test_double_commit():
            token = set_session(mock_session)
            try:
                uow = PostgreSQLUnitOfWork()
                async with uow:
                    await uow.commit()
                    # Second commit on SAME instance should raise
                    with pytest.raises(InvalidStateError, match="Already committed"):
                        await uow.commit()
            finally:
                reset_session(token)

        asyncio.run(test_double_commit())

    def test_uow_prevents_rollback_after_commit_on_same_instance(self) -> None:
        """Guard prevents rollback after commit on the same instance."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from src.domain.exceptions import InvalidStateError
        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
            PostgreSQLUnitOfWork,
        )

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.begin = AsyncMock()

        async def test_rollback_after_commit():
            token = set_session(mock_session)
            try:
                uow = PostgreSQLUnitOfWork()
                async with uow:
                    await uow.commit()
                    # Rollback after commit on SAME instance should raise
                    with pytest.raises(InvalidStateError, match="Already committed"):
                        await uow.rollback()
            finally:
                reset_session(token)

        asyncio.run(test_rollback_after_commit())

    def test_uow_exits_without_error_without_explicit_commit(self) -> None:
        """Async with block without explicit commit should auto-commit."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
            PostgreSQLUnitOfWork,
        )

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.begin = AsyncMock()

        async def test_auto_commit():
            token = set_session(mock_session)
            try:
                uow = PostgreSQLUnitOfWork()
                async with uow:
                    pass  # No explicit commit, should auto-commit on exit
                # After exiting with no exception and no explicit commit, commit was called
                assert mock_session.commit.called
            finally:
                reset_session(token)

        asyncio.run(test_auto_commit())


class TestHexagonalDependencyDirection:
    """Validates hexagonal architecture dependency direction."""

    def test_domain_layer_does_not_import_postgresql_uow(self) -> None:
        """Domain layer must not import PostgreSQLUnitOfWork."""
        domain_files = list((ROOT / "src" / "domain").rglob("*.py"))

        violations = []
        for f in domain_files:
            if f.name == "__init__.py":
                continue
            content = f.read_text()
            if "PostgreSQLUnitOfWork" in content or "infrastructure.messaging.unit_of_work" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, f"Domain layer imports infrastructure UoW: {violations}"

    def test_domain_ports_use_protocol_not_abc(self) -> None:
        """Domain ports should use Protocol for structural typing."""
        unit_of_work_path = ROOT / "src" / "domain" / "ports" / "unit_of_work.py"
        content = unit_of_work_path.read_text()

        assert "class UnitOfWork(Protocol)" in content, "UnitOfWork should use Protocol"

    def test_outbox_repository_protocol_not_abc(self) -> None:
        """OutboxRepository should use Protocol for structural typing."""
        outbox_path = ROOT / "src" / "domain" / "ports" / "outbox.py"
        content = outbox_path.read_text()

        assert "class OutboxRepository(Protocol)" in content, "OutboxRepository should use Protocol"


class TestEventHandlerDependency:
    """Validates EventHandler depends on UnitOfWork interface, not concrete implementation."""

    def test_event_handlers_use_unit_of_work_interface(self) -> None:
        """EventHandlers should depend on UnitOfWork interface."""
        handler_files = list((ROOT / "src" / "application" / "event_handlers").rglob("*.py"))

        if not handler_files:
            pytest.skip("No event handler files found")

        violations = []
        for f in handler_files:
            if f.name == "__init__.py":
                continue
            content = f.read_text()

            if "PostgreSQLUnitOfWork" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, f"EventHandlers directly depend on PostgreSQLUnitOfWork: {violations}"

    def test_unit_of_work_interface_exported_from_domain_ports(self) -> None:
        """UnitOfWork interface should be exported from domain ports."""
        ports_init = ROOT / "src" / "domain" / "ports" / "__init__.py"
        content = ports_init.read_text()

        assert "UnitOfWork" in content, "UnitOfWork not exported from domain/ports/__init__.py"
