# 测试框架配置指南

本文档介绍 Sisyphus 系统的测试框架配置，包括 pytest 优化、CI/CD 集成和各类测试支持。

## 目录

- [1. pytest 配置优化](#1-pytest-配置优化)
- [2. 与新 CI/CD 集成](#2-与新-cicd-集成)
- [3. K3S 测试支持](#3-k3s-测试支持)
- [4. Harbor 镜像测试](#4-harbor-镜像测试)
- [5. ArgoCD 部署测试](#5-argocd-部署测试)

---

## 1. pytest 配置优化

### 1.1 核心配置文件

```ini
# pytest.ini
[pytest]
# 基本配置
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 命令行选项
addopts =
    -v                      # 详细输出
    --strict-markers        # 严格标记
    --tb=short              # 简短回溯
    --color=yes             # 彩色输出
    --cov=src               # 覆盖率
    --cov-report=term-missing  # 终端覆盖率报告
    --cov-report=xml        # XML 格式
    --cov-report=html       # HTML 格式
    --junitxml=junit.xml    # JUnit XML
    --maxfail=5             # 最大失败数
    -ra                     # 显示所有跳过和失败

# 标记定义
markers =
    unit: 单元测试
    integration: 集成测试
    e2e: 端到端测试
    slow: 慢速测试
    db: 需要数据库
    k3s: 需要 K3S 集群
    harbor: 需要 Harbor
    argocd: 需要 ArgoCD
    api: API 测试
    ui: UI 测试

# 过滤器
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
    ignore::ResourceWarning

# 超时配置（需要 pytest-timeout）
timeout = 300
timeout_method = thread

# 异步配置（需要 pytest-asyncio）
asyncio_mode = auto
```

### 1.2 项目结构

```
tests/
├── __init__.py
├── conftest.py              # 全局 fixtures
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_utils.py
│   └── test_services.py
├── integration/             # 集成测试
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_api.py
│   ├── test_harbor.py
│   └── test_kubernetes.py
├── e2e/                     # 端到端测试
│   ├── __init__.py
│   ├── test_workflow.py
│   └── test_deployment.py
├── k3s/                     # K3S 测试
│   ├── __init__.py
│   ├── test_cluster.py
│   └── test_workloads.py
├── fixtures/                # 测试数据
│   ├── __init__.py
│   ├── sample_configs/
│   └── test_data/
└── utils/                   # 测试工具
    ├── __init__.py
    ├── helpers.py
    └── mocks.py
```

### 1.3 全局 fixtures

```python
# tests/conftest.py
import os
import pytest
import asyncio
from pathlib import Path
from typing import Generator, AsyncGenerator
import yaml

# ============ 会话级 fixtures ============

@pytest.fixture(scope="session")
def test_config() -> dict:
    """加载测试配置"""
    config_path = Path(__file__).parent / "fixtures" / "test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

@pytest.fixture(scope="session")
def test_env() -> str:
    """获取测试环境"""
    return os.getenv("TEST_ENV", "test")

# ============ 数据库 fixtures ============

@pytest.fixture(scope="session")
def db_url(test_config: dict) -> str:
    """数据库连接 URL"""
    db = test_config.get("database", {})
    return f"postgresql://{db.get('user')}:{db.get('password')}@{db.get('host')}:{db.get('port')}/{db.get('name')}_test"

@pytest.fixture(scope="function")
async def db_connection(db_url: str) -> AsyncGenerator:
    """数据库连接"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(db_url, echo=False)

    # 创建表
    async with engine.begin() as conn:
        # 导入所有模型
        from src.models import Base
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

# ============ API 测试 fixtures ============

@pytest.fixture(scope="function")
async def api_client() -> AsyncGenerator:
    """API 测试客户端"""
    from httpx import AsyncClient, ASGITransport
    from src.app import create_app

    app = create_app(testing=True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

@pytest.fixture(scope="function")
def auth_token() -> str:
    """生成测试用认证 token"""
    import jwt
    from datetime import datetime, timedelta

    payload = {
        "sub": "test-user",
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")

# ============ K3S fixtures ============

@pytest.fixture(scope="session")
def k3s_available() -> bool:
    """检查 K3S 是否可用"""
    import subprocess
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

@pytest.fixture(scope="function")
def k3s_namespace() -> Generator:
    """创建测试命名空间"""
    import subprocess
    import uuid

    namespace = f"test-{uuid.uuid4().hex[:8]}"

    # 创建命名空间
    subprocess.run(
        ["kubectl", "create", "namespace", namespace],
        check=True,
        capture_output=True
    )

    yield namespace

    # 清理命名空间
    subprocess.run(
        ["kubectl", "delete", "namespace", namespace, "--force"],
        capture_output=True
    )

# ============ Harbor fixtures ============

@pytest.fixture(scope="session")
def harbor_config(test_config: dict) -> dict:
    """Harbor 配置"""
    return test_config.get("harbor", {})

@pytest.fixture(scope="function")
def harbor_project(harbor_config: dict) -> Generator:
    """创建临时 Harbor 项目"""
    import requests
    import uuid

    project_name = f"test-{uuid.uuid4().hex[:8]}"

    # 创建项目
    session = requests.Session()
    session.auth = (harbor_config["username"], harbor_config["password"])

    response = session.post(
        f"{harbor_config['url']}/api/v2.0/projects",
        json={"project_name": project_name, "public": False},
        verify=False
    )
    response.raise_for_status()

    yield project_name

    # 删除项目
    session.delete(
        f"{harbor_config['url']}/api/v2.0/projects/{project_name}",
        verify=False
    )

# ============ ArgoCD fixtures ============

@pytest.fixture(scope="session")
def argocd_config(test_config: dict) -> dict:
    """ArgoCD 配置"""
    return test_config.get("argocd", {})

@pytest.fixture(scope="function")
def argocd_app(argocd_config: dict) -> Generator:
    """创建临时 ArgoCD 应用"""
    import requests
    import uuid

    app_name = f"test-{uuid.uuid4().hex[:8]}"

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {argocd_config['token']}",
        "Content-Type": "application/json"
    })

    # 创建应用
    response = session.post(
        f"{argocd_config['url']}/api/v1/applications",
        json={
            "metadata": {"name": app_name, "namespace": "default"},
            "spec": {
                "source": {
                    "repoURL": "https://github.com/test/repo.git",
                    "targetRevision": "HEAD",
                    "path": "manifests"
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default"
                }
            }
        },
        verify=False
    )
    response.raise_for_status()

    yield app_name

    # 删除应用
    session.delete(
        f"{argocd_config['url']}/api/v1/applications/{app_name}",
        params={"cascade": True},
        verify=False
    )

# ============ 标记辅助 ============

def requires_k3s():
    """K3S 测试标记"""
    return pytest.mark.k3s

def requires_harbor():
    """Harbor 测试标记"""
    return pytest.mark.harbor

def requires_argocd():
    """ArgoCD 测试标记"""
    return pytest.mark.argocd

def slow_test():
    """慢速测试标记"""
    return pytest.mark.slow
```

### 1.4 测试配置

```yaml
# tests/fixtures/test_config.yaml
database:
  host: localhost
  port: 5432
  name: sisys_test
  user: test
  password: testpass

harbor:
  url: https://harbor.example.com
  username: test_user
  password: test_password
  project: test-project

argocd:
  url: https://argocd.example.com
  token: test_token
  namespace: default

k3s:
  kubeconfig: ~/.kube/config
  namespace: test

kubernetes:
  context: test-cluster
```

---

## 2. 与新 CI/CD 集成

### 2.1 Gitea Actions 配置

```yaml
# .gitea/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: '3.12'
  REGISTRY: harbor.example.com

jobs:
  # ========== 单元测试 ==========
  unit-tests:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run Unit Tests
        run: |
          pytest tests/unit \
            --cov=src \
            --cov-report=xml \
            --cov-report=html \
            --junitxml=junit-unit.xml \
            --cov-fail-under=80 \
            -m "not slow"

      - name: Upload Coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: unit-test-results
          path: junit-unit.xml

  # ========== 集成测试 ==========
  integration-tests:
    runs-on: docker
    needs: unit-tests
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: sisys_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run Integration Tests
        run: |
          pytest tests/integration \
            --db-url=postgresql://test:testpass@postgres:5432/sisys_test \
            --junitxml=junit-integration.xml \
            -m "integration and not slow"

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: integration-test-results
          path: junit-integration.xml

  # ========== K3S 测试 ==========
  k3s-tests:
    runs-on: docker
    needs: integration-tests
    steps:
      - uses: actions/checkout@v4

      - name: Setup K3S
        run: |
          # 启动 K3S 容器
          docker run -d --name k3s-test \
            --privileged \
            -p 6443:6443 \
            rancher/k3s:latest

          # 等待 K3S 就绪
          until docker exec k3s-test kubectl get nodes | grep Ready; do
            sleep 5
          done

          # 复制 kubeconfig
          docker cp k3s-test:/etc/rancher/k3s/k3s.yaml ~/.kube/config

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run K3S Tests
        run: |
          pytest tests/k3s \
            --junitxml=junit-k3s.xml \
            -m "k3s"

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: k3s-test-results
          path: junit-k3s.xml

      - name: Cleanup K3S
        if: always()
        run: docker rm -f k3s-test

  # ========== Harbor 测试 ==========
  harbor-tests:
    runs-on: docker
    needs: integration-tests
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run Harbor Tests
        run: |
          pytest tests/integration/test_harbor.py \
            --junitxml=junit-harbor.xml \
            -m "harbor"
        env:
          HARBOR_URL: ${{ secrets.HARBOR_URL }}
          HARBOR_USERNAME: ${{ secrets.HARBOR_USERNAME }}
          HARBOR_PASSWORD: ${{ secrets.HARBOR_PASSWORD }}

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: harbor-test-results
          path: junit-harbor.xml

  # ========== ArgoCD 测试 ==========
  argocd-tests:
    runs-on: docker
    needs: k3s-tests
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run ArgoCD Tests
        run: |
          pytest tests/integration/test_argocd.py \
            --junitxml=junit-argocd.xml \
            -m "argocd"
        env:
          ARGOCD_URL: ${{ secrets.ARGOCD_URL }}
          ARGOCD_TOKEN: ${{ secrets.ARGOCD_TOKEN }}

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: argocd-test-results
          path: junit-argocd.xml

  # ========== 测试报告汇总 ==========
  test-report:
    runs-on: docker
    needs: [unit-tests, integration-tests, k3s-tests, harbor-tests, argocd-tests]
    if: always()
    steps:
      - uses: actions/checkout@v4

      - name: Download All Test Results
        uses: actions/download-artifact@v4
        with:
          pattern: "*-test-results"
          path: test-results/

      - name: Generate Test Report
        run: |
          # 合并 JUnit XML
          pip install junitparser
          junitparser merge test-results/*/junit-*.xml junit-final.xml

      - name: Upload Final Report
        uses: actions/upload-artifact@v4
        with:
          name: test-report
          path: junit-final.xml
```

### 2.2 测试覆盖率报告

```yaml
# .gitea/workflows/coverage-report.yml
name: Coverage Report

on:
  workflow_run:
    workflows: ["Test Suite"]
    types:
      - completed

jobs:
  coverage:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Download Coverage Report
        uses: actions/download-artifact@v4
        with:
          name: coverage-report
          path: coverage/

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Coverage Tools
        run: pip install coverage

      - name: Generate Coverage Badge
        run: |
          coverage json
          python scripts/generate_badge.py

      - name: Upload Badge
        uses: actions/upload-artifact@v4
        with:
          name: coverage-badge
          path: coverage-badge.svg
```

---

## 3. K3S 测试支持

### 3.1 K3S 测试工具类

```python
# tests/utils/k3s_helper.py
import subprocess
import time
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

class K3SHelper:
    """K3S 测试辅助类"""

    def __init__(self, kubeconfig: str = None):
        self.kubeconfig = kubeconfig or str(Path.home() / ".kube" / "config")
        self.env = {"KUBECONFIG": self.kubeconfig}

    def run_kubectl(self, *args, timeout: int = 30) -> subprocess.CompletedProcess:
        """运行 kubectl 命令"""
        cmd = ["kubectl"] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self.env
        )

    def wait_for_pod_ready(
        self,
        pod_name: str,
        namespace: str,
        timeout: int = 120
    ) -> bool:
        """等待 Pod 就绪"""
        start = time.time()
        while time.time() - start < timeout:
            result = self.run_kubectl(
                "get", "pod", pod_name,
                "-n", namespace,
                "-o", "jsonpath={.status.phase}"
            )
            if result.stdout == "Running":
                return True
            time.sleep(2)
        return False

    def wait_for_deployment_ready(
        self,
        deployment_name: str,
        namespace: str,
        timeout: int = 120
    ) -> bool:
        """等待 Deployment 就绪"""
        result = self.run_kubectl(
            "rollout", "status",
            f"deployment/{deployment_name}",
            "-n", namespace,
            "--timeout", f"{timeout}s"
        )
        return result.returncode == 0

    def apply_manifest(self, manifest_path: Path) -> bool:
        """应用 Kubernetes 清单"""
        result = self.run_kubectl("apply", "-f", str(manifest_path))
        return result.returncode == 0

    def get_service_url(self, service_name: str, namespace: str) -> Optional[str]:
        """获取服务 URL"""
        result = self.run_kubectl(
            "get", "service", service_name,
            "-n", namespace,
            "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"
        )
        return result.stdout if result.stdout else None

    def get_pod_logs(self, pod_name: str, namespace: str) -> str:
        """获取 Pod 日志"""
        result = self.run_kubectl(
            "logs", pod_name,
            "-n", namespace
        )
        return result.stdout

    def port_forward(
        self,
        resource: str,
        local_port: int,
        remote_port: int,
        namespace: str
    ) -> subprocess.Popen:
        """端口转发"""
        cmd = [
            "kubectl", "port-forward",
            f"{resource}",
            f"{local_port}:{remote_port}",
            "-n", namespace
        ]
        return subprocess.Popen(cmd, env=self.env)

    def cleanup_namespace(self, namespace: str) -> bool:
        """清理命名空间"""
        result = self.run_kubectl("delete", "namespace", namespace, "--force")
        return result.returncode == 0
```

### 3.2 K3S 测试示例

```python
# tests/k3s/test_cluster.py
import pytest
import time
from pathlib import Path
from tests.utils.k3s_helper import K3SHelper

pytestmark = [pytest.mark.k3s, pytest.mark.slow]

class TestK3SCluster:
    """K3S 集群测试"""

    @pytest.fixture
    def k3s(self) -> K3SHelper:
        return K3SHelper()

    def test_cluster_info(self, k3s: K3SHelper):
        """测试集群信息"""
        result = k3s.run_kubectl("cluster-info")
        assert result.returncode == 0
        assert "Kubernetes control plane" in result.stdout

    def test_node_ready(self, k3s: K3SHelper):
        """测试节点状态"""
        result = k3s.run_kubectl(
            "get", "nodes",
            "-o", "jsonpath={.items[0].status.conditions[?(@.type==\"Ready\")].status}"
        )
        assert result.stdout == "True"

    def test_system_pods(self, k3s: K3SHelper):
        """测试系统 Pod"""
        result = k3s.run_kubectl(
            "get", "pods",
            "-n", "kube-system",
            "-o", "jsonpath={.items[*].status.phase}"
        )
        phases = result.stdout.split()
        assert "Running" in phases

class TestWorkloadDeployment:
    """工作负载部署测试"""

    @pytest.fixture
    def k3s(self) -> K3SHelper:
        return K3SHelper()

    @pytest.fixture
    def test_namespace(self, k3s: K3SHelper) -> str:
        import uuid
        namespace = f"test-{uuid.uuid4().hex[:8]}"
        k3s.run_kubectl("create", "namespace", namespace)
        yield namespace
        k3s.cleanup_namespace(namespace)

    def test_deploy_application(
        self,
        k3s: K3SHelper,
        test_namespace: str
    ):
        """测试应用部署"""
        manifest = Path(__file__).parent / "fixtures" / "test-app.yaml"

        # 部署应用
        assert k3s.apply_manifest(manifest)

        # 等待就绪
        assert k3s.wait_for_deployment_ready("test-app", test_namespace)

        # 验证 Pod 运行
        assert k3s.wait_for_pod_ready("test-app", test_namespace)

    def test_service_exposure(
        self,
        k3s: K3SHelper,
        test_namespace: str
    ):
        """测试服务暴露"""
        manifest = Path(__file__).parent / "fixtures" / "test-service.yaml"

        # 部署服务
        assert k3s.apply_manifest(manifest)

        # 等待服务就绪
        time.sleep(5)

        # 获取服务信息
        result = k3s.run_kubectl(
            "get", "service", "test-app",
            "-n", test_namespace
        )
        assert result.returncode == 0
```

### 3.3 K3S 测试清单

```yaml
# tests/k3s/fixtures/test-app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  namespace: test
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
        - name: app
          image: harbor.example.com/sisys/test-app:latest
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

---

## 4. Harbor 镜像测试

### 4.1 Harbor 测试工具类

```python
# tests/utils/harbor_helper.py
import requests
from typing import Dict, Any, List, Optional

class HarborHelper:
    """Harbor 测试辅助类"""

    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False  # 测试环境跳过证书验证

    def create_project(
        self,
        name: str,
        public: bool = False
    ) -> Dict[str, Any]:
        """创建项目"""
        response = self.session.post(
            f"{self.url}/api/v2.0/projects",
            json={"project_name": name, "public": public}
        )
        response.raise_for_status()
        return response.json()

    def delete_project(self, name: str) -> bool:
        """删除项目"""
        response = self.session.delete(
            f"{self.url}/api/v2.0/projects/{name}"
        )
        return response.status_code == 200

    def list_repositories(self, project: str) -> List[Dict[str, Any]]:
        """列出仓库"""
        response = self.session.get(
            f"{self.url}/api/v2.0/projects/{project}/repositories"
        )
        response.raise_for_status()
        return response.json()

    def get_artifact(
        self,
        project: str,
        repository: str,
        reference: str
    ) -> Dict[str, Any]:
        """获取镜像信息"""
        response = self.session.get(
            f"{self.url}/api/v2.0/projects/{project}/repositories/{repository}/artifacts/{reference}"
        )
        response.raise_for_status()
        return response.json()

    def delete_artifact(
        self,
        project: str,
        repository: str,
        reference: str
    ) -> bool:
        """删除镜像"""
        response = self.session.delete(
            f"{self.url}/api/v2.0/projects/{project}/repositories/{repository}/artifacts/{reference}"
        )
        return response.status_code == 200

    def scan_artifact(
        self,
        project: str,
        repository: str,
        reference: str
    ) -> Dict[str, Any]:
        """扫描镜像"""
        response = self.session.post(
            f"{self.url}/api/v2.0/projects/{project}/repositories/{repository}/artifacts/{reference}/scan"
        )
        response.raise_for_status()

        # 等待扫描完成
        import time
        time.sleep(10)

        # 获取扫描结果
        response = self.session.get(
            f"{self.url}/api/v2.0/projects/{project}/repositories/{repository}/artifacts/{reference}"
        )
        return response.json()

    def get_scan_report(
        self,
        project: str,
        repository: str,
        reference: str
    ) -> Dict[str, Any]:
        """获取扫描报告"""
        response = self.session.get(
            f"{self.url}/api/v2.0/projects/{project}/repositories/{repository}/artifacts/{reference}/additions/vulnerabilities"
        )
        response.raise_for_status()
        return response.json()
```

### 4.2 Harbor 测试示例

```python
# tests/integration/test_harbor.py
import pytest
import requests
from tests.utils.harbor_helper import HarborHelper

pytestmark = pytest.mark.harbor

class TestHarborIntegration:
    """Harbor 集成测试"""

    @pytest.fixture
    def harbor(self) -> HarborHelper:
        return HarborHelper(
            url=os.getenv("HARBOR_URL", "https://harbor.example.com"),
            username=os.getenv("HARBOR_USERNAME"),
            password=os.getenv("HARBOR_PASSWORD")
        )

    @pytest.fixture
    def test_project(self, harbor: HarborHelper) -> str:
        import uuid
        project_name = f"test-{uuid.uuid4().hex[:8]}"
        harbor.create_project(project_name)
        yield project_name
        harbor.delete_project(project_name)

    def test_project_creation(self, harbor: HarborHelper):
        """测试项目创建"""
        import uuid
        project_name = f"test-{uuid.uuid4().hex[:8]}"

        result = harbor.create_project(project_name)
        assert result["name"] == project_name

        # 清理
        harbor.delete_project(project_name)

    def test_image_push(
        self,
        harbor: HarborHelper,
        test_project: str
    ):
        """测试镜像推送"""
        import subprocess

        # 构建测试镜像
        dockerfile = Path(__file__).parent / "fixtures" / "Dockerfile.test"
        image_tag = f"{os.getenv('HARBOR_URL')}/{test_project}/test-image:test"

        result = subprocess.run(
            ["docker", "build", "-t", image_tag, "-f", str(dockerfile), "."],
            capture_output=True
        )
        assert result.returncode == 0

        # 登录 Harbor
        login_result = subprocess.run(
            ["docker", "login", os.getenv("HARBOR_URL"),
             "-u", os.getenv("HARBOR_USERNAME"),
             "-p", os.getenv("HARBOR_PASSWORD")],
            capture_output=True
        )
        assert login_result.returncode == 0

        # 推送镜像
        push_result = subprocess.run(
            ["docker", "push", image_tag],
            capture_output=True
        )
        assert push_result.returncode == 0

    def test_image_scan(
        self,
        harbor: HarborHelper,
        test_project: str
    ):
        """测试镜像扫描"""
        # 使用已知镜像测试
        artifact = harbor.get_artifact(
            test_project,
            "test-image",
            "test"
        )

        # 触发扫描
        scan_result = harbor.scan_artifact(
            test_project,
            "test-image",
            "test"
        )

        # 获取扫描报告
        report = harbor.get_scan_report(
            test_project,
            "test-image",
            "test"
        )

        assert "vulnerability_summary" in report
```

---

## 5. ArgoCD 部署测试

### 5.1 ArgoCD 测试工具类

```python
# tests/utils/argocd_helper.py
import requests
import time
from typing import Dict, Any, Optional

class ArgoCDHelper:
    """ArgoCD 测试辅助类"""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        self.session.verify = False

    def create_application(
        self,
        name: str,
        repo_url: str,
        target_revision: str = "HEAD",
        path: str = "manifests",
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """创建应用"""
        response = self.session.post(
            f"{self.url}/api/v1/applications",
            json={
                "metadata": {
                    "name": name,
                    "namespace": namespace
                },
                "spec": {
                    "source": {
                        "repoURL": repo_url,
                        "targetRevision": target_revision,
                        "path": path
                    },
                    "destination": {
                        "server": "https://kubernetes.default.svc",
                        "namespace": namespace
                    },
                    "syncPolicy": {
                        "automated": {
                            "prune": True,
                            "selfHeal": True
                        }
                    }
                }
            }
        )
        response.raise_for_status()
        return response.json()

    def delete_application(self, name: str, namespace: str = "default") -> bool:
        """删除应用"""
        response = self.session.delete(
            f"{self.url}/api/v1/applications/{namespace}/{name}",
            params={"cascade": True}
        )
        return response.status_code == 200

    def sync_application(
        self,
        name: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """同步应用"""
        response = self.session.post(
            f"{self.url}/api/v1/applications/{namespace}/{name}/sync",
            json={}
        )
        response.raise_for_status()
        return response.json()

    def wait_for_sync(
        self,
        name: str,
        namespace: str = "default",
        timeout: int = 300
    ) -> bool:
        """等待同步完成"""
        start = time.time()
        while time.time() - start < timeout:
            app = self.get_application(name, namespace)
            status = app.get("status", {}).get("sync", {}).get("status")
            health = app.get("status", {}).get("health", {}).get("status")

            if status == "Synced" and health == "Healthy":
                return True

            time.sleep(5)

        return False

    def get_application(
        self,
        name: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """获取应用信息"""
        response = self.session.get(
            f"{self.url}/api/v1/applications/{namespace}/{name}"
        )
        response.raise_for_status()
        return response.json()

    def get_application_resources(
        self,
        name: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """获取应用资源"""
        response = self.session.get(
            f"{self.url}/api/v1/applications/{namespace}/{name}/resource-tree"
        )
        response.raise_for_status()
        return response.json()

    def rollback_application(
        self,
        name: str,
        revision: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """回滚应用"""
        response = self.session.post(
            f"{self.url}/api/v1/applications/{namespace}/{name}/rollback",
            json={"id": revision}
        )
        response.raise_for_status()
        return response.json()
```

### 5.2 ArgoCD 测试示例

```python
# tests/integration/test_argocd.py
import pytest
import os
from tests.utils.argocd_helper import ArgoCDHelper

pytestmark = pytest.mark.argocd

class TestArgoCDIntegration:
    """ArgoCD 集成测试"""

    @pytest.fixture
    def argocd(self) -> ArgoCDHelper:
        return ArgoCDHelper(
            url=os.getenv("ARGOCD_URL", "https://argocd.example.com"),
            token=os.getenv("ARGOCD_TOKEN")
        )

    @pytest.fixture
    def test_app(self, argocd: ArgoCDHelper) -> str:
        import uuid
        app_name = f"test-{uuid.uuid4().hex[:8]}"

        argocd.create_application(
            name=app_name,
            repo_url="https://github.com/test/manifests.git",
            path="test"
        )

        yield app_name

        argocd.delete_application(app_name)

    def test_application_creation(self, argocd: ArgoCDHelper):
        """测试应用创建"""
        import uuid
        app_name = f"test-{uuid.uuid4().hex[:8]}"

        result = argocd.create_application(
            name=app_name,
            repo_url="https://github.com/test/manifests.git"
        )

        assert result["metadata"]["name"] == app_name

        # 清理
        argocd.delete_application(app_name)

    def test_application_sync(
        self,
        argocd: ArgoCDHelper,
        test_app: str
    ):
        """测试应用同步"""
        # 触发同步
        argocd.sync_application(test_app)

        # 等待同步完成
        synced = argocd.wait_for_sync(test_app, timeout=120)
        assert synced

    def test_application_health(
        self,
        argocd: ArgoCDHelper,
        test_app: str
    ):
        """测试应用健康状态"""
        # 同步后检查健康状态
        argocd.sync_application(test_app)
        argocd.wait_for_sync(test_app)

        app = argocd.get_application(test_app)
        health_status = app.get("status", {}).get("health", {}).get("status")

        assert health_status == "Healthy"

    def test_application_rollback(
        self,
        argocd: ArgoCDHelper,
        test_app: str
    ):
        """测试应用回滚"""
        # 获取当前 revision
        app = argocd.get_application(test_app)
        current_revision = app.get("status", {}).get("history", [{}])[-1].get("id")

        if current_revision and current_revision > 1:
            # 回滚到上一个版本
            result = argocd.rollback_application(
                test_app,
                str(current_revision - 1)
            )

            assert result is not None

class TestGitOpsWorkflow:
    """GitOps 工作流测试"""

    @pytest.fixture
    def argocd(self) -> ArgoCDHelper:
        return ArgoCDHelper(
            url=os.getenv("ARGOCD_URL"),
            token=os.getenv("ARGOCD_TOKEN")
        )

    def test_full_deployment_workflow(self, argocd: ArgoCDHelper):
        """测试完整部署工作流"""
        import uuid

        app_name = f"test-{uuid.uuid4().hex[:8]}"

        # 1. 创建应用
        argocd.create_application(
            name=app_name,
            repo_url=os.getenv("GITOPS_REPO_URL"),
            path="apps/test"
        )

        # 2. 同步应用
        argocd.sync_application(app_name)

        # 3. 等待健康
        assert argocd.wait_for_sync(app_name, timeout=180)

        # 4. 验证资源
        resources = argocd.get_application_resources(app_name)
        assert len(resources.get("resources", [])) > 0

        # 5. 清理
        argocd.delete_application(app_name)
```

---

## 附录：测试运行命令

```bash
# 运行所有测试
pytest

# 运行特定类型测试
pytest -m unit           # 单元测试
pytest -m integration    # 集成测试
pytest -m k3s            # K3S 测试
pytest -m harbor         # Harbor 测试
pytest -m argocd         # ArgoCD 测试

# 运行特定目录测试
pytest tests/unit/
pytest tests/integration/
pytest tests/k3s/

# 运行特定文件测试
pytest tests/unit/test_config.py

# 运行特定测试函数
pytest tests/unit/test_config.py::test_load_config

# 带覆盖率报告
pytest --cov=src --cov-report=html

# 并行执行测试
pytest -n auto

# 显示最慢的测试
pytest --durations=10

# 失败后停止
pytest -x

# 重新运行失败的测试
pytest --lf

# 详细输出
pytest -v

# 显示本地变量
pytest -l

# 生成 JUnit 报告
pytest --junitxml=junit.xml
```
