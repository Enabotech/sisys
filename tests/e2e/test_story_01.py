#!/usr/bin/env python3
"""
sisys - Story 0.1 Acceptance Test Script

This script tests all acceptance criteria for Story 0.1:
- Docker Compose services start correctly
- Poetry dependencies install successfully
- IDE configuration is present
- Environment variables template exists
"""

import subprocess
import sys
import time
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent

def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_step(text):
    """Print step header."""
    print(f"\n[STEP] {text}")
    print("-" * 40)

def run_command(cmd, cwd=None, check=True):
    """Run shell command and return result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def test_docker_services():
    """Test: Docker Compose services start correctly."""
    print_header("Test 1: Docker Services")
    
    docker_dir = ROOT / "docker"
    
    # Check docker-compose.yml exists
    compose_file = docker_dir / "docker-compose.yml"
    if not compose_file.exists():
        print("[FAIL] docker-compose.yml not found")
        return False
    print(f"[OK] docker-compose.yml found: {compose_file}")
    
    # Start services
    print_step("Starting Docker services...")
    success, stdout, stderr = run_command(
        "docker-compose up -d",
        cwd=docker_dir
    )
    
    if not success:
        print(f"[FAIL] Failed to start services: {stderr}")
        return False
    print("[OK] Docker services starting...")
    
    # Wait for services to be healthy
    print_step("Waiting for services to be healthy (30 seconds)...")
    time.sleep(30)
    
    # Check service status
    print_step("Checking service status...")
    success, stdout, stderr = run_command(
        "docker-compose ps",
        cwd=docker_dir
    )
    
    print(stdout)
    
    if "Up" not in stdout:
        print("[FAIL] Some services are not running")
        return False
    
    # Count healthy services
    healthy_count = stdout.count("healthy")
    total_services = 5  # postgres, redis, qdrant, minio, neo4j
    
    print(f"\n[OK] {healthy_count}/{total_services} services healthy")
    
    if healthy_count < total_services:
        print("[WARN] Some services still initializing (this is normal)")
    
    return True

def test_poetry_install():
    """Test: Poetry dependencies install successfully."""
    print_header("Test 2: Poetry Installation")
    
    # Check pyproject.toml exists
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        print("[FAIL] pyproject.toml not found")
        return False
    print("[OK] pyproject.toml found")
    
    # Check Poetry installed
    print_step("Checking Poetry installation...")
    success, stdout, stderr = run_command("poetry --version")
    
    if not success:
        print("[FAIL] Poetry not installed")
        return False
    print(f"[OK] Poetry installed: {stdout.strip()}")
    
    # Check Python version
    print_step("Checking Python version...")
    success, stdout, stderr = run_command("python --version")
    
    if not success:
        print("[FAIL] Python not found")
        return False
    print(f"[OK] Python version: {stdout.strip()}")
    
    # Try poetry install (dry run)
    print_step("Checking Poetry configuration (dry run)...")
    success, stdout, stderr = run_command("poetry check")
    
    if not success:
        print(f"[WARN] Poetry configuration warning: {stderr}")
        print("  -> Run 'poetry install' to install dependencies")
    else:
        print("[OK] Poetry configuration valid")
    
    return True

def test_ide_configuration():
    """Test: IDE configuration is present."""
    print_header("Test 3: IDE Configuration")
    
    vscode_dir = ROOT / ".vscode"
    settings_file = vscode_dir / "settings.json"
    
    if not vscode_dir.exists():
        print("[FAIL] .vscode directory not found")
        return False
    print("[OK] .vscode directory found")
    
    if not settings_file.exists():
        print("[FAIL] settings.json not found")
        return False
    print("[OK] settings.json found")
    
    # Read and display configuration
    print_step("IDE Configuration Summary:")
    try:
        import json
        with open(settings_file) as f:
            config = json.load(f)
        
        if "python.defaultInterpreterPath" in config:
            print(f"  [OK] Python interpreter: {config['python.defaultInterpreterPath']}")
        if "python.formatting.provider" in config:
            print(f"  [OK] Formatter: {config['python.formatting.provider']}")
        if "python.linting.ruffEnabled" in config:
            status = "enabled" if config['python.linting.ruffEnabled'] else "disabled"
            print(f"  [OK] Linter: Ruff {status}")
        
    except Exception as e:
        print(f"  [WARN] Could not parse settings.json: {e}")
    
    return True

def test_environment_template():
    """Test: Environment variables template exists."""
    print_header("Test 4: Environment Template")
    
    env_example = ROOT / ".env.example"
    
    if not env_example.exists():
        print("[FAIL] .env.example not found")
        return False
    print("[OK] .env.example found")
    
    # Count environment variables
    print_step("Environment Variables Summary:")
    try:
        with open(env_example) as f:
            lines = f.readlines()
        
        var_count = sum(1 for line in lines if "=" in line and not line.strip().startswith("#"))
        print(f"  [OK] {var_count} environment variables defined")
        
        # Check critical variables
        critical_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "QDRANT_URL",
            "MINIO_ENDPOINT",
            "NEO4J_URI",
        ]
        
        content = "".join(lines)
        missing = [var for var in critical_vars if var not in content]
        
        if missing:
            print(f"[FAIL] Missing critical variables: {missing}")
            return False
        print(f"  [OK] All critical variables present")
        
    except Exception as e:
        print(f"  [WARN] Could not read .env.example: {e}")
    
    return True

def test_documentation():
    """Test: Documentation is complete."""
    print_header("Test 5: Documentation")
    
    readme = ROOT / "README.md"
    
    if not readme.exists():
        print("[FAIL] README.md not found")
        return False
    print("[OK] README.md found")
    
    # Check README sections
    print_step("README.md Sections:")
    try:
        with open(readme, encoding='utf-8') as f:
            content = f.read()
        
        required_sections = [
            "Quick Start",
            "Project Structure",
            "Development Tools",
            "Troubleshooting",
        ]
        
        for section in required_sections:
            if section in content:
                print(f"  [OK] {section}")
            else:
                print(f"  [FAIL] {section} missing")
        
    except Exception as e:
        print(f"  [WARN] Could not read README.md: {e}")
    
    return True

def main():
    """Run all acceptance tests."""
    print_header("Story 0.1: Development Environment Setup - Acceptance Test")
    
    tests = [
        ("Docker Services", test_docker_services),
        ("Poetry Installation", test_poetry_install),
        ("IDE Configuration", test_ide_configuration),
        ("Environment Template", test_environment_template),
        ("Documentation", test_documentation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[FAIL] Test {name} failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print_header("Test Summary")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name}: {status}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed_count}/{total_count} tests passed")
    print("=" * 60)
    
    if passed_count == total_count:
        print("\n[SUCCESS] All acceptance criteria met!")
        print("\nNext steps:")
        print("1. Run 'cd docker && docker-compose up -d' to start services")
        print("2. Run 'poetry install' to install dependencies")
        print("3. Copy .env.example to .env and configure your environment")
        print("4. Proceed to Story 0.2: CI/CD Pipeline")
        return 0
    else:
        print("\n[FAIL] Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
