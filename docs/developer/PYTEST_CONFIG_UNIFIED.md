# pytest 配置统一指南

**版本：** 1.0
**日期：** 2026-03-05
**状态：** ✅ 统一标准

---

## 📋 统一 pytest 配置

### pytest.ini (推荐)

```ini
# pytest.ini
[pytest]
# 基础配置
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto

# 标记系统
markers =
    unit: 单元测试（快速，无外部依赖）
    integration: 集成测试（需要数据库/外部服务）
    e2e: E2E 测试（完整用户旅程）
    slow: 慢速测试（>1 秒）
    database: 需要数据库的测试
    redis: 需要 Redis 的测试
    qdrant: 需要 Qdrant 的测试
    minio: 需要 MinIO 的测试
    neo4j: 需要 Neo4j 的测试
    llm: 需要 LLM API 的测试
    k3s: 需要 K3S 集群的测试
    harbor: 需要 Harbor 的测试
    argocd: 需要 ArgoCD 的测试
    gitea: 需要 Gitea 的测试

# 默认选项
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=term-missing:skip-covered
    --cov-fail-under=80
    -n auto
    --dist=loadfile

# 过滤器
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
    ignore::ResourceWarning

# 日志配置
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)s] %(name)s: %(message)s
log_cli_date_format = %Y-%m-%d %H:%M:%S

# 超时配置 (秒)
timeout = 300

# JUnit 配置 (CI/CD)
junit_family = xunit2
junit_logging = all
```

### pyproject.toml (替代方案)

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"

markers = [
    "unit: 单元测试（快速，无外部依赖）",
    "integration: 集成测试（需要数据库/外部服务）",
    "e2e: E2E 测试（完整用户旅程）",
    "slow: 慢速测试（>1 秒）",
    "database: 需要数据库的测试",
    "redis: 需要 Redis 的测试",
    "qdrant: 需要 Qdrant 的测试",
    "minio: 需要 MinIO 的测试",
    "neo4j: 需要 Neo4j 的测试",
    "llm: 需要 LLM API 的测试",
    "k3s: 需要 K3S 集群的测试",
    "harbor: 需要 Harbor 的测试",
    "argocd: 需要 ArgoCD 的测试",
    "gitea: 需要 Gitea 的测试",
]

addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--cov=src",
    "--cov-report=term-missing:skip-covered",
    "--cov-fail-under=80",
    "-n", "auto",
    "--dist=loadfile",
]

filterwarnings = [
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
    "ignore::ResourceWarning",
]

log_cli = true
log_cli_level = "INFO"
timeout = 300
junit_family = "xunit2"
junit_logging = "all"
```

---

## 📁 conftest.py 统一配置

```python
# tests/conftest.py
"""
全局 pytest 配置和 Fixture。

此文件包含所有测试共享的 Fixture 和配置。
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, AsyncGenerator
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool


# ========== 测试配置 ==========

@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """测试配置"""
    return {
        "database_url": "postgresql+asyncpg://test:test@localhost:5432/test_sisys",
        "redis_url": "redis://localhost:6379/15",
        "qdrant_url": "http://localhost:6333",
        "minio_url": "http://localhost:9000",
        "neo4j_url": "bolt://localhost:7687",
        "gitea_url": "http://gitea.sisys.local",
        "harbor_url": "http://harbor.sisys.local",
        "argocd_url": "http://argocd.sisys.local",
        "test_db_prefix": "test_",
    }


# ========== 数据库 Fixture ==========

@pytest.fixture(scope="session")
def test_engine(test_config: Dict[str, Any]):
    """创建测试数据库引擎"""
    engine = create_async_engine(
        test_config["database_url"],
        poolclass=StaticPool,
        echo=False,
    )
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    数据库会话 Fixture - 每个测试函数独立事务。

    测试完成后自动回滚，确保测试隔离。
    """
    async_sessionmaker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_sessionmaker()

    async with session.begin():
        yield session
        # 事务自动回滚（测试隔离）


@pytest.fixture(scope="function")
async def clean_database(db_session: AsyncSession):
    """
    清理数据库 Fixture - 每个测试前清理所有表。
    """
    # 按依赖顺序删除数据
    await db_session.execute(text("DELETE FROM event_outbox"))
    await db_session.execute(text("DELETE FROM routing_decision_log"))
    await db_session.execute(text("DELETE FROM strategic_plans"))
    await db_session.commit()
    yield db_session


# ========== 事件总线 Fixture ==========

@pytest.fixture(scope="function")
async def event_bus(mocker: MockerFixture) -> AsyncGenerator[EventBus, None]:
    """Mock 事件总线 - 用于单元测试"""
    mock_bus = mocker.AsyncMock(spec=EventBus)
    mock_bus.publish = mocker.AsyncMock()
    mock_bus.subscribe = mocker.AsyncMock()
    yield mock_bus


# ========== 测试数据构建器 ==========

@pytest.fixture
def strategic_plan_data() -> Dict[str, Any]:
    """战略规划测试数据"""
    return {
        "id": uuid.uuid4(),
        "plan_type": "SP",
        "status": "draft",
        "creator_id": "agent_ceo",
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def strategic_plan_builder():
    """战略规划测试数据构建器"""
    from tests.factories import StrategicPlanBuilder
    return StrategicPlanBuilder()


# ========== 时间工具 ==========

@pytest.fixture
def frozen_time():
    """冻结时间 Fixture - 用于可重复测试"""
    from freezegun import freeze_time
    with freeze_time("2026-03-05 10:00:00") as frozen:
        yield frozen


# ========== 异步测试支持 ==========

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 - 用于异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========== Mock 对象工厂 ==========

@pytest.fixture
def mock_llm_router(mocker: MockerFixture):
    """Mock LLM 路由器"""
    mock = mocker.AsyncMock()
    mock.route = mocker.AsyncMock(return_value={
        "selected_model": "ollama/qwen2.5-7b",
        "estimated_cost": 0.001,
        "estimated_latency": 500,
    })
    yield mock


@pytest.fixture
def mock_repository(mocker: MockerFixture):
    """Mock 仓储"""
    mock = mocker.AsyncMock()
    mock.get_by_id = mocker.AsyncMock()
    mock.find_all = mocker.AsyncMock()
    mock.add = mocker.AsyncMock()
    mock.update = mocker.AsyncMock()
    mock.delete = mocker.AsyncMock()
    yield mock


# ========== K3S 测试 Fixture ==========

@pytest.fixture(scope="session")
def k3s_config() -> Dict[str, str]:
    """K3S 测试配置"""
    return {
        "kubeconfig": os.path.expanduser("~/.kube/config"),
        "namespace": "sisys-test",
    }


@pytest.fixture(scope="session")
def k8s_client(k3s_config: Dict[str, str]):
    """K8s 客户端 Fixture"""
    from kubernetes import client, config
    config.load_kube_config(config_file=k3s_config["kubeconfig"])
    return {
        "core": client.CoreV1Api(),
        "apps": client.AppsV1Api(),
        "networking": client.NetworkingV1Api(),
    }


@pytest.fixture(scope="function")
def test_namespace(k8s_client, k3s_config: Dict[str, str]):
    """创建测试命名空间"""
    from kubernetes.client import V1Namespace, V1ObjectMeta
    import uuid

    ns_name = f"test-{uuid.uuid4().hex[:8]}"
    ns = V1Namespace(
        metadata=V1ObjectMeta(
            name=ns_name,
            labels={"env": "test", "managed-by": "pytest"}
        )
    )
    k8s_client["core"].create_namespace(body=ns)

    yield ns_name

    # 清理命名空间
    k8s_client["core"].delete_namespace(name=ns_name)


# ========== Harbor 测试 Fixture ==========

@pytest.fixture(scope="session")
def harbor_config() -> Dict[str, str]:
    """Harbor 测试配置"""
    return {
        "url": "http://harbor.sisys.local",
        "username": "admin",
        "password": "Harbor12345!",
    }


@pytest.fixture
def harbor_client(harbor_config: Dict[str, str]):
    """Harbor API 客户端 Fixture"""
    import requests
    from requests.auth import HTTPBasicAuth

    session = requests.Session()
    session.auth = HTTPBasicAuth(
        harbor_config["username"],
        harbor_config["password"]
    )
    session.base_url = harbor_config["url"]

    yield session

    session.close()


# ========== Gitea 测试 Fixture ==========

@pytest.fixture(scope="session")
def gitea_config() -> Dict[str, str]:
    """Gitea 测试配置"""
    return {
        "url": "http://gitea.sisys.local",
        "username": "admin",
        "password": "Admin12345!",
        "token": os.getenv("GITEA_TOKEN", ""),
    }


@pytest.fixture
def gitea_client(gitea_config: Dict[str, str]):
    """Gitea API 客户端 Fixture"""
    import requests

    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {gitea_config['token']}"
    })
    session.base_url = gitea_config["url"]

    yield session

    session.close()


# ========== ArgoCD 测试 Fixture ==========

@pytest.fixture(scope="session")
def argocd_config() -> Dict[str, str]:
    """ArgoCD 测试配置"""
    return {
        "url": "http://argocd.sisys.local",
        "username": "admin",
        "password": os.getenv("ARGOCD_PASSWORD", ""),
    }


@pytest.fixture
def argocd_client(argocd_config: Dict[str, str]):
    """ArgoCD API 客户端 Fixture"""
    import requests

    session = requests.Session()
    session.verify = False  # 测试环境忽略 SSL

    # 登录获取 token
    login_response = session.post(
        f"{argocd_config['url']}/api/v1/session",
        json={
            "username": argocd_config["username"],
            "password": argocd_config["password"]
        }
    )
    token = login_response.json()["token"]
    session.headers.update({"Authorization": f"Bearer {token}"})

    session.base_url = argocd_config["url"]

    yield session

    session.close()


# ========== 测试资源清理 ==========

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_resources():
    """会话级测试资源清理"""
    yield

    # 清理测试命名空间
    print("\n🧹 Cleaning up test resources...")

    # 清理 K8s 测试命名空间
    try:
        from kubernetes import client, config
        config.load_kube_config()
        v1 = client.CoreV1Api()
        namespaces = v1.list_namespace(label_selector="env=test")
        for ns in namespaces.items:
            v1.delete_namespace(name=ns.metadata.name)
        print("✅ Test namespaces cleaned up")
    except Exception as e:
        print(f"⚠️  Cleanup error: {e}")
```

---

## 📊 测试覆盖率配置

```toml
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/__init__.py",
    "*/conftest.py",
    "*/main.py",
]
branch = false

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]
show_missing = true
skip_covered = true
fail_under = 80

[tool.coverage.paths]
source = [
    "src/",
    "*/site-packages/",
]

[tool.coverage.html]
directory = "htmlcov"
title = "SISYS Coverage Report"

[tool.coverage.xml]
output = "coverage.xml"
```

---

## ✅ 验收清单

### 配置验收

- [ ] pytest.ini 或 pyproject.toml 配置完整
- [ ] conftest.py 包含所有共享 Fixture
- [ ] 覆盖率配置正确
- [ ] 标记系统配置完整

### 测试验收

- [ ] 单元测试可运行
- [ ] 集成测试可运行
- [ ] K3S 测试可运行
- [ ] Harbor/Gitea/ArgoCD 测试可运行

---

**实施状态：** ✅ 已应用到所有文档
