"""
sisys - Pytest Configuration and Fixtures

This file contains shared fixtures and configuration for pytest tests.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def docker_compose_file(project_root):
    """Return the path to docker-compose.yml."""
    return project_root / "docker" / "docker-compose.yml"


@pytest.fixture(scope="session")
def docker_services(docker_compose_file):
    """
    Fixture to start Docker services before tests and stop them after.

    Usage:
        def test_something(docker_services):
            # Docker services are running
            pass
    """
    import subprocess

    # Start services
    subprocess.run(["docker-compose", "up", "-d"], cwd=docker_compose_file.parent, check=True)

    yield

    # Stop services
    subprocess.run(["docker-compose", "down"], cwd=docker_compose_file.parent, check=True)


@pytest.fixture
def story_01_acceptance_criteria():
    """Return Story 0.1 acceptance criteria."""
    return {
        "docker_compose": "docker-compose.yml exists and services start",
        "poetry_install": "poetry install succeeds",
        "ide_config": ".vscode/settings.json exists",
        "env_template": ".env.example exists with all required variables",
        "documentation": "README.md exists with complete sections",
    }
