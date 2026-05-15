"""Shared pytest configuration."""

import sys
from pathlib import Path

import pytest

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_once() -> None:
    """Bootstrap the port registry once per test session."""
    from src.composition_root import bootstrap

    bootstrap()
