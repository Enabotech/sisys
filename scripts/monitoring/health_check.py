#!/usr/bin/env python3
"""
sisys - Development Environment Health Check Script

This script verifies that all development services are running correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_docker_services():
    """Check if all Docker services are running."""
    import subprocess
    
    print("🔍 Checking Docker services...")
    
    services = [
        ("postgres", "5432"),
        ("redis", "6379"),
        ("qdrant", "6333"),
        ("minio", "9000"),
        ("neo4j", "7474"),
    ]
    
    all_healthy = True
    
    for service, port in services:
        try:
            result = subprocess.run(
                ["docker-compose", "ps", service],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if "Up" in result.stdout and "healthy" in result.stdout:
                print(f"  ✓ {service}: Up (healthy) on port {port}")
            elif "Up" in result.stdout:
                print(f"  ⚠ {service}: Up (port {port}) - health check pending")
            else:
                print(f"  ✗ {service}: Not running")
                all_healthy = False
        except Exception as e:
            print(f"  ✗ {service}: Error checking - {e}")
            all_healthy = False
    
    return all_healthy


def check_python_environment():
    """Check if Python environment is set up correctly."""
    print("\n🔍 Checking Python environment...")
    
    try:
        import poetry
        print(f"  ✓ Poetry: {poetry.__version__}")
    except ImportError:
        print(f"  ✗ Poetry: Not installed")
        return False
    
    try:
        import fastapi
        print(f"  ✓ FastAPI: {fastapi.__version__}")
    except ImportError:
        print(f"  ✗ FastAPI: Not installed")
        return False
    
    try:
        import sqlalchemy
        print(f"  ✓ SQLAlchemy: {sqlalchemy.__version__}")
    except ImportError:
        print(f"  ✗ SQLAlchemy: Not installed")
        return False
    
    return True


def check_environment_variables():
    """Check if environment variables are set."""
    print("\n🔍 Checking environment variables...")
    
    from dotenv import load_dotenv
    import os
    
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print(f"  ✗ .env file not found")
        print(f"  → Please copy .env.example to .env and configure it")
        return False
    
    load_dotenv(env_file)
    
    required_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "QDRANT_URL",
        "MINIO_ENDPOINT",
        "NEO4J_URI",
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
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
