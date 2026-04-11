# pytest 夹具配置 - Installer 测试
import pytest
import os
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_sisys_home():
    """创建临时的 SISYS_HOME 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "Library" / "Application Support" / "Sisys"
        data_dir.mkdir(parents=True)
        yield data_dir


@pytest.fixture
def mock_docker_available(monkeypatch):
    """模拟 Docker 已安装"""
    def mock_which(cmd):
        if cmd == "docker":
            return "/usr/local/bin/docker"
        return None
    
    def mock_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "Docker version 24.0.0"
        return MockResult()
    
    monkeypatch.setattr("shutil.which", mock_which)


@pytest.fixture
def mock_docker_not_available(monkeypatch):
    """模拟 Docker 未安装"""
    def mock_which(cmd):
        return None
    
    monkeypatch.setattr("shutil.which", mock_which)


@pytest.fixture
def clean_launch_agent():
    """确保测试后清理 LaunchAgent"""
    agent_path = Path.home() / "Library" / "LaunchAgents" / "com.sisys.app.test.plist"
    yield agent_path
    if agent_path.exists():
        agent_path.unlink()


@pytest.fixture
def sample_docker_compose():
    """创建测试用的 docker-compose.yml"""
    compose_content = """
version: "3.8"
services:
  postgres:
    image: postgres:15-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 10s
      timeout: 5s
      retries: 5
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
  sisys:
    image: sisys/sisys:0.15
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8080:8080"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(compose_content)
        yield f.name
    Path(f.name).unlink(missing_ok=True)
