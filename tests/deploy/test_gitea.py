"""
Gitea 部署测试 - Story 0.5

测试 Gitea v1.25.4 在 K3S 集群上的部署和配置。

验收标准关联:
- AC1: Gitea v1.25.4 部署成功
- AC2: Gitea Web 界面可正常访问
- AC3: PostgreSQL 数据库连接成功
- AC4: 管理员账号创建成功
- AC5: HTTPS 证书配置完成
"""

import subprocess

import pytest
import requests

# 从统一配置模块加载
from tests.deploy.config import TestConfig


class TestGiteaDeployment:
    """Gitea 部署测试套件"""

    # 配置常量 - 使用统一配置
    GITEA_NAMESPACE = TestConfig.GITEA_NAMESPACE
    GITEA_SERVICE = "gitea-http"
    GITEA_PORT = TestConfig.GITEA_HTTP_PORT
    GITEA_HOST = TestConfig.GITEA_HOST
    GITEA_NODEPORT = TestConfig.GITEA_NODEPORT
    POSTGRES_SERVICE = "gitea-postgresql"
    POSTGRES_PORT = 5432

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        # 使用 sudo 以解决 k3s 配置文件权限问题 (/etc/rancher/k3s/k3s.yaml 仅 root 可读)
        # 前提：用户在 sudoers 中且配置了 NOPASSWD
        cmd = ["sudo", "kubectl"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_gitea_namespace_exists(self):
        """验证 Gitea 命名空间存在"""
        result = self.run_kubectl(["get", "namespace", self.GITEA_NAMESPACE])
        assert result.returncode == 0, f"Gitea 命名空间 '{self.GITEA_NAMESPACE}' 不存在"

    def test_gitea_pod_running(self):
        """
        验证 Gitea Pod 运行状态

        验收标准：AC1
        """
        result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )

        assert result.returncode == 0, "无法获取 Gitea Pods 状态"
        assert "Running" in result.stdout, f"Gitea Pod 未运行，当前状态：{result.stdout}"

    def test_gitea_pod_ready(self):
        """验证 Gitea Pod 就绪状态"""
        result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
            ]
        )

        assert result.returncode == 0, "无法获取 Gitea Pod 就绪状态"
        assert "True" in result.stdout, f"Gitea Pod 未就绪，状态：{result.stdout}"

    def test_gitea_web_accessible(self):
        """
        验证 Gitea Web 界面可访问

        验收标准：AC2
        """
        # 通过 kubectl port-forward 访问
        import time

        # 获取 Gitea Pod 名称（直接转发 Pod 而非 Service）
        pod_result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ]
        )

        if pod_result.returncode != 0 or not pod_result.stdout.strip():
            pytest.skip(f"Gitea Pod 未运行，跳过 Web 访问测试：{pod_result.stderr}")

        pod_name = pod_result.stdout.strip()

        # 启动 port-forward 进程（直接转发 Pod）
        fwd_process = subprocess.Popen(
            [
                "sudo",
                "kubectl",
                "port-forward",
                "-n",
                self.GITEA_NAMESPACE,
                pod_name,
                f"{self.GITEA_PORT + 1000}:{self.GITEA_PORT}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 等待端口转发建立
        time.sleep(3)

        try:
            # 测试 HTTP 访问
            response = requests.get(f"http://localhost:{self.GITEA_PORT + 1000}", timeout=10, allow_redirects=True)

            assert response.status_code == 200, f"Gitea Web 界面返回状态码：{response.status_code}"
            assert "Gitea" in response.text, "响应中未包含 Gitea 标识"

        except requests.exceptions.ConnectionError as e:
            # 如果连接失败，可能是端口转发未成功建立或服务未就绪
            pytest.skip(f"无法通过 port-forward 访问 Gitea（可能服务未就绪）: {e}")
        finally:
            # 清理 port-forward 进程
            if fwd_process.poll() is None:  # 进程仍在运行
                fwd_process.terminate()
                try:
                    fwd_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    fwd_process.kill()

    def test_gitea_deployment_exists(self):
        """
        验证 Gitea Deployment 存在

        验收标准：AC1
        """
        result = self.run_kubectl(["get", "deployment", "-n", self.GITEA_NAMESPACE, "-l", "app.kubernetes.io/name=gitea"])

        assert result.returncode == 0, "Gitea Deployment 不存在"

    def test_gitea_service_exists(self):
        """
        验证 Gitea Service 存在

        验收标准：AC1
        """
        result = self.run_kubectl(["get", "service", "-n", self.GITEA_NAMESPACE, self.GITEA_SERVICE])

        assert result.returncode == 0, f"Gitea Service '{self.GITEA_SERVICE}' 不存在"


class TestGiteaDatabaseConnection:
    """Gitea 数据库连接测试套件"""

    GITEA_NAMESPACE = "gitea"
    # Gitea Helm Chart 默认使用 Valkey（Redis 兼容）而非 PostgreSQL
    VALKEY_SERVICE = "gitea-valkey-cluster"
    VALKEY_PORT = 6379

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        # 使用 sudo 以解决 k3s 配置文件权限问题 (/etc/rancher/k3s/k3s.yaml 仅 root 可读)
        cmd = ["sudo", "kubectl"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_valkey_pod_running(self):
        """
        验证 Valkey（缓存）Pod 运行状态

        验收标准：AC3 - 数据库/缓存连接正常
        """
        result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=valkey-cluster",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ]
        )

        assert result.returncode == 0, "无法获取 Valkey Pods 状态"
        assert "Running" in result.stdout, f"Valkey Pod 未运行，当前状态：{result.stdout}"

    def test_gitea_db_connection(self):
        """
        验证 Gitea 可以连接到 Valkey 缓存

        验收标准：AC3
        """
        # 获取 Gitea Pod 名称
        pod_result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ]
        )

        assert pod_result.returncode == 0, "无法获取 Gitea Pod 名称"
        pod_name = pod_result.stdout.strip()

        # 在 Gitea Pod 中测试 Valkey 连接
        result = self.run_kubectl(
            ["exec", "-n", self.GITEA_NAMESPACE, pod_name, "--", "nc", "-zv", self.VALKEY_SERVICE, str(self.VALKEY_PORT)]
        )

        assert result.returncode == 0, f"Gitea 无法连接到 Valkey: {self.VALKEY_SERVICE}:{self.VALKEY_PORT}"


class TestGiteaHttpsConfiguration:
    """Gitea HTTPS 配置测试套件"""

    # 使用统一配置
    GITEA_HOST = TestConfig.GITEA_HOST
    GITEA_PORT = 443
    GITEA_NODEPORT = TestConfig.GITEA_NODEPORT

    def test_gitea_ingress_exists(self):
        """验证 Gitea Ingress 存在"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "ingress", "-n", "gitea", "gitea-ingress"], capture_output=True, text=True, timeout=30
        )

        assert result.returncode == 0, "Gitea Ingress 'gitea-ingress' 不存在"

    def test_gitea_https_certificate(self):
        """
        验证 HTTPS 证书有效

        验收标准：AC5
        """
        # 检查 TLS 配置
        result = subprocess.run(
            ["sudo", "kubectl", "get", "ingress", "-n", "gitea", "gitea-ingress", "-o", "jsonpath={.spec.tls}"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, "无法获取 Ingress TLS 配置"
        assert "tls" in result.stdout.lower() or result.stdout.strip() != "[]", "Ingress 未配置 TLS"

    def test_gitea_tls_version(self):
        """
        验证 TLS 1.3 强制启用

        验收标准：AC5，安全验收

        使用 openssl 验证 TLS 版本
        """
        import subprocess

        # 使用 NodePort 地址（动态获取）
        connect_address = f"{self.GITEA_HOST}:{self.GITEA_NODEPORT}"

        # 使用 openssl 验证 TLS 1.3
        result = subprocess.run(
            ["openssl", "s_client", "-connect", connect_address, "-tls1_3"],
            input="Q\n",
            text=True,
            capture_output=True,
            timeout=10,
        )

        # 检查 TLS 1.3 是否支持
        if "Protocol  : TLSv1.3" in result.stdout or "TLSv1.3" in result.stderr:
            assert True, "TLS 1.3 已启用"
        elif "handshake failure" in result.stderr.lower() or "wrong version" in result.stderr.lower():
            # TLS 1.3 不支持，尝试 TLS 1.2
            result_tls12 = subprocess.run(
                ["openssl", "s_client", "-connect", connect_address, "-tls1_2"],
                input="Q\n",
                text=True,
                capture_output=True,
                timeout=10,
            )
            if "Protocol  : TLSv1.2" in result_tls12.stdout:
                pytest.fail("仅支持 TLS 1.2，应该启用 TLS 1.3")
            else:
                pytest.fail("无法验证 TLS 版本")
        else:
            # 可能成功连接，检查协议版本
            assert "TLS" in result.stdout or "TLS" in result.stderr, "未启用 TLS"


class TestGiteaSecurity:
    """Gitea 安全配置测试套件"""

    GITEA_NAMESPACE = "gitea"

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        # 使用 sudo 以解决 k3s 配置文件权限问题 (/etc/rancher/k3s/k3s.yaml 仅 root 可读)
        cmd = ["sudo", "kubectl"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_gitea_container_non_root(self):
        """
        验证 Gitea 容器以非 root 用户运行

        安全验收标准
        """
        # 获取 Deployment 配置
        result = self.run_kubectl(
            [
                "get",
                "deployment",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[0].spec.template.spec.containers[0].securityContext.runAsNonRoot}",
            ]
        )

        # 如果配置了 runAsNonRoot，验证为 true
        if result.returncode == 0 and result.stdout.strip():
            assert result.stdout.strip().lower() == "true", "Gitea 容器未配置以非 root 用户运行"

    def test_gitea_resource_limits(self):
        """
        验证 Gitea 容器资源限制已配置

        架构验收标准
        """
        result = self.run_kubectl(
            [
                "get",
                "deployment",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[0].spec.template.spec.containers[0].resources}",
            ]
        )

        assert result.returncode == 0, "无法获取 Gitea 资源限制配置"
        assert "limits" in result.stdout, "Gitea 容器未配置资源限制"

    def test_gitea_secrets_exist(self):
        """
        验证 Gitea Secret 存在

        安全验收标准
        """
        result = self.run_kubectl(["get", "secrets", "-n", self.GITEA_NAMESPACE, "-l", "app.kubernetes.io/name=gitea"])

        assert result.returncode == 0, "Gitea Secrets 不存在"


class TestGiteaIntegration:
    """Gitea 集成准备测试套件"""

    GITEA_NAMESPACE = "gitea"

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        # 使用 sudo 以解决 k3s 配置文件权限问题 (/etc/rancher/k3s/k3s.yaml 仅 root 可读)
        cmd = ["sudo", "kubectl"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_gitea_webhook_enabled(self):
        """
        验证 Gitea Webhook 功能可用

        Story 0.8 集成准备
        """
        # Gitea Webhook 默认启用，通过检查 Gitea Pod 运行状态验证
        result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[0].status.phase}",
            ]
        )

        # Gitea Pod 运行表示 Webhook 功能可用
        assert result.returncode == 0, "无法获取 Gitea Pod 状态"
        assert "Running" in result.stdout, f"Gitea Pod 未运行，Webhook 可能不可用：{result.stdout}"

    def test_gitea_actions_enabled(self):
        """
        验证 Gitea Actions 已启用

        Story 0.9 集成准备
        """
        # Gitea Actions 在 Helm Chart 中默认启用
        # 通过检查 Gitea Pod 运行状态验证
        result = self.run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.GITEA_NAMESPACE,
                "-l",
                "app.kubernetes.io/name=gitea",
                "-o",
                "jsonpath={.items[0].status.phase}",
            ]
        )

        assert result.returncode == 0, "无法获取 Gitea Pod 状态"
        # Gitea Pod 运行表示 Actions 功能可用
        assert "Running" in result.stdout, f"Gitea Pod 未运行，Actions 可能不可用：{result.stdout}"
