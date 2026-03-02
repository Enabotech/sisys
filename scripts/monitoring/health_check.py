#!/usr/bin/env python3
"""
sisys - Development Environment Health Check Script

This script verifies that all development services are running correctly.

Usage:
    python3 scripts/monitoring/health_check.py

Requirements:
    - Docker Compose (v2 plugin recommended: 'docker compose')
    - Python 3.11+
    - python-dotenv (optional, for environment variable checking)
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent  # scripts/monitoring/ -> project root
sys.path.insert(0, str(project_root))


def get_docker_compose_command():
    """Detect whether to use 'docker compose' (v2) or 'docker-compose' (v1)."""
    try:
        # Try docker compose (v2 - plugin version) first
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return ["docker", "compose"]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # Try docker-compose (v1 - standalone version)
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return ["docker-compose"]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Default to docker compose (v2)
    return ["docker", "compose"]


def check_docker_services():
    """Check if all Docker services are running."""
    print("🔍 Checking Docker services...")

    services = [
        ("sisys-postgres", "5432", "PostgreSQL"),
        ("sisys-redis", "6379", "Redis"),
        ("sisys-qdrant", "6333", "Qdrant"),
        ("sisys-minio", "9000", "MinIO"),
        ("sisys-neo4j", "7474", "Neo4j"),
    ]

    docker_compose_cmd = get_docker_compose_command()
    print(f"  → Using: {' '.join(docker_compose_cmd)}")

    all_healthy = True
    docker_dir = project_root / "docker"

    for container_name, port, service_name in services:
        try:
            result = subprocess.run(
                docker_compose_cmd + ["ps", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=docker_dir,
                timeout=10
            )

            if result.returncode == 0 and container_name in result.stdout:
                # Parse JSON output or check for "Up" status
                if "running" in result.stdout.lower() or "up" in result.stdout.lower() or "healthy" in result.stdout.lower():
                    print(f"  ✓ {service_name}: {container_name} running on port {port}")
                else:
                    print(f"  ⚠ {service_name}: {container_name} status unknown")
            else:
                # Fallback: check if container exists via docker ps
                ps_result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "Up" in ps_result.stdout:
                    print(f"  ✓ {service_name}: {container_name} running on port {port}")
                else:
                    print(f"  ✗ {service_name}: {container_name} not running")
                    all_healthy = False

        except subprocess.TimeoutExpired:
            print(f"  ✗ {service_name}: Timeout checking status")
            all_healthy = False
        except Exception as e:
            print(f"  ✗ {service_name}: Error checking - {e}")
            all_healthy = False

    return all_healthy


def check_python_environment():
    """Check if Python environment is set up correctly."""
    print("\n🔍 Checking Python environment...")

    # Check Python version
    print_step("Python version...")
    try:
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"  ✓ Python: {result.stdout.strip()}")
            # Check if version >= 3.11
            version_str = result.stdout.strip().split()[-1]
            try:
                major, minor = map(int, version_str.split('.')[:2])
                if major < 3 or (major == 3 and minor < 11):
                    print(f"  ⚠ Warning: Python 3.11+ required, found {major}.{minor}")
                    print(f"  → Install Python 3.11+ or use pyenv/conda")
            except (ValueError, IndexError):
                pass
        else:
            print(f"  ✗ Python3 not found")
            return False
    except Exception as e:
        print(f"  ✗ Error checking Python: {e}")
        return False

    # Check Poetry installation
    print_step("Poetry installation...")
    try:
        result = subprocess.run(
            ["poetry", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"  ✓ Poetry: {result.stdout.strip()}")
        else:
            print(f"  ✗ Poetry: Not installed")
            print(f"  → Install: curl -sSL https://install.python-poetry.org | python3 -")
    except FileNotFoundError:
        print(f"  ✗ Poetry: Not installed")
        print(f"  → Install: curl -sSL https://install.python-poetry.org | python3 -")
    except Exception as e:
        print(f"  ✗ Error checking Poetry: {e}")

    # Check if virtual environment exists
    print_step("Virtual environment...")
    venv_path = project_root / ".venv"
    if venv_path.exists():
        print(f"  ✓ Virtual environment: {venv_path}")
    else:
        print(f"  → Virtual environment not created yet")
        print(f"  → Run: poetry install")

    return True  # Don't fail - user can install later


def print_step(text):
    """Print step header."""
    print(f"  {text}")


def check_environment_variables():
    """Check if environment variables are set."""
    print("\n🔍 Checking environment variables...")

    import os

    env_file = project_root / ".env"

    if not env_file.exists():
        print(f"  ✗ .env file not found")
        print(f"  → Please copy .env.example to .env and configure it")
        print(f"  → Command: cp .env.example .env")
        return False

    print(f"  ✓ .env file found: {env_file}")

    # Try to use python-dotenv if available, otherwise parse manually
    try:
        from dotenv import dotenv_values
        env_values = dotenv_values(env_file)
    except ImportError:
        # Manual parsing fallback
        print(f"  → python-dotenv not installed, using manual parsing")
        env_values = {}
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        env_values[key.strip()] = value.strip()
        except Exception as e:
            print(f"  ✗ Error reading .env file: {e}")
            return False

    required_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "QDRANT_URL",
        "MINIO_ENDPOINT",
        "NEO4J_URI",
    ]

    all_set = True
    for var in required_vars:
        value = env_values.get(var) or os.getenv(var)
        if value:
            print(f"  ✓ {var}: Set")
        else:
            print(f"  ✗ {var}: Not set")
            all_set = False

    return all_set


def main():
    """Run all health checks."""
    print("=" * 60)
    print("sisys - Development Environment Health Check")
    print("=" * 60)
    
    checks = [
        ("Docker Services", check_docker_services),
        ("Python Environment", check_python_environment),
        ("Environment Variables", check_environment_variables),
    ]
    
    results = []
    for name, check_func in checks:
        results.append((name, check_func()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ Passed" if passed else "✗ Failed"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✅ All checks passed! Development environment is ready.")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
