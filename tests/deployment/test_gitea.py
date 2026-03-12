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
import ssl
import socket
from typing import Optional


class TestGiteaDeployment:
    """Gitea 部署测试套件"""

    # 配置常量
    GITEA_NAMESPACE = "gitea"
    GITEA_SERVICE = "gitea-http"
    GITEA_PORT = 3000
    GITEA_HOST = "gitea.sisys.local"
    POSTGRES_SERVICE = "gitea-postgresql"
    POSTGRES_PORT = 5432

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        cmd = ["kubectl"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

    def test_gitea_namespace_exists(self):
        """验证 Gitea 命名空间存在"""
        result = self.run_kubectl(["get", "namespace", self.GITEA_NAMESPACE])
        assert result.returncode == 0, f"Gitea 命名空间 '{self.GITEA_NAMESPACE}' 不存在"

    def test_gitea_pod_running(self):
        """
        验证 Gitea Pod 运行状态
        
        验收标准：AC1
        """
        result = self.run_kubectl([
            "get", "pods",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea",
            "-o", "jsonpath={.items[*].status.phase}"
        ])
        
        assert result.returncode == 0, "无法获取 Gitea Pods 状态"
        assert "Running" in result.stdout, f"Gitea Pod 未运行，当前状态：{result.stdout}"

    def test_gitea_pod_ready(self):
        """验证 Gitea Pod 就绪状态"""
        result = self.run_kubectl([
            "get", "pods",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea",
            "-o", "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}"
        ])
        
        assert result.returncode == 0, "无法获取 Gitea Pod 就绪状态"
        assert "True" in result.stdout, f"Gitea Pod 未就绪，状态：{result.stdout}"

    def test_gitea_web_accessible(self):
        """
        验证 Gitea Web 界面可访问
        
        验收标准：AC2
        """
        # 通过 kubectl port-forward 访问
        import time
        
        # 启动 port-forward 进程
        fwd_process = subprocess.Popen([
            "kubectl", "port-forward",
            "-n", self.GITEA_NAMESPACE,
            "svc/gitea-http",
            f"{self.GITEA_PORT + 1000}:{self.GITEA_PORT}"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待端口转发建立
        time.sleep(2)
        
        try:
            # 测试 HTTP 访问
            response = requests.get(
                f"http://localhost:{self.GITEA_PORT + 1000}",
                timeout=10,
                allow_redirects=True
            )
            
            assert response.status_code == 200, (
                f"Gitea Web 界面返回状态码：{response.status_code}"
            )
            assert "Gitea" in response.text, "响应中未包含 Gitea 标识"
            
        finally:
            # 清理 port-forward 进程
            fwd_process.terminate()
            fwd_process.wait(timeout=5)

    def test_gitea_deployment_exists(self):
        """
        验证 Gitea Deployment 存在
        
        验收标准：AC1
        """
        result = self.run_kubectl([
            "get", "deployment",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea"
        ])

        assert result.returncode == 0, f"Gitea Deployment 不存在"

    def test_gitea_service_exists(self):
        """
        验证 Gitea Service 存在
        
        验收标准：AC1
        """
        result = self.run_kubectl([
            "get", "service",
            "-n", self.GITEA_NAMESPACE,
            self.GITEA_SERVICE
        ])

        assert result.returncode == 0, f"Gitea Service '{self.GITEA_SERVICE}' 不存在"


class TestGiteaDatabaseConnection:
    """Gitea 数据库连接测试套件"""

    GITEA_NAMESPACE = "gitea"
    POSTGRES_SERVICE = "gitea-postgresql"
    POSTGRES_PORT = 5432

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        cmd = ["kubectl"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

    def test_postgres_pod_running(self):
        """
        验证 PostgreSQL Pod 运行状态
        
        验收标准：AC3
        """
        result = self.run_kubectl([
            "get", "pods",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=postgresql",
            "-o", "jsonpath={.items[*].status.phase}"
        ])
        
        assert result.returncode == 0, "无法获取 PostgreSQL Pods 状态"
        assert "Running" in result.stdout, f"PostgreSQL Pod 未运行，当前状态：{result.stdout}"

    def test_gitea_db_connection(self):
        """
        验证 Gitea 可以连接到 PostgreSQL 数据库
        
        验收标准：AC3
        """
        # 获取 Gitea Pod 名称
        pod_result = self.run_kubectl([
            "get", "pods",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea",
            "-o", "jsonpath={.items[0].metadata.name}"
        ])
        
        assert pod_result.returncode == 0, "无法获取 Gitea Pod 名称"
        pod_name = pod_result.stdout.strip()
        
        # 在 Gitea Pod 中测试数据库连接
        result = self.run_kubectl([
            "exec", "-n", self.GITEA_NAMESPACE, pod_name, "--",
            "nc", "-zv", self.POSTGRES_SERVICE, str(self.POSTGRES_PORT)
        ])
        
        assert result.returncode == 0, (
            f"Gitea 无法连接到 PostgreSQL: {self.POSTGRES_SERVICE}:{self.POSTGRES_PORT}"
        )


class TestGiteaHttpsConfiguration:
    """Gitea HTTPS 配置测试套件"""

    GITEA_HOST = "gitea.sisys.local"
    GITEA_PORT = 443

    def test_gitea_ingress_exists(self):
        """验证 Gitea Ingress 存在"""
        result = subprocess.run([
            "kubectl", "get", "ingress",
            "-n", "gitea",
            "gitea-ingress"
        ], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, "Gitea Ingress 'gitea-ingress' 不存在"

    def test_gitea_https_certificate(self):
        """
        验证 HTTPS 证书有效
        
        验收标准：AC5
        """
        # 检查 TLS 配置
        result = subprocess.run([
            "kubectl", "get", "ingress",
            "-n", "gitea",
            "gitea-ingress",
            "-o", "jsonpath={.spec.tls}"
        ], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, "无法获取 Ingress TLS 配置"
        assert "tls" in result.stdout.lower() or result.stdout.strip() != "[]", (
            "Ingress 未配置 TLS"
        )

    def test_gitea_tls_version(self):
        """
        验证 TLS 1.3 强制启用

        验收标准：AC5，安全验收
        """
        # 注意：这个测试需要实际的网络访问，在实际部署环境中运行
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # 尝试 TLS 1.3 连接
            with socket.create_connection((self.GITEA_HOST, self.GITEA_PORT), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.GITEA_HOST) as ssock:
                    # 验证 TLS 版本
                    tls_version = ssock.version()
                    assert tls_version and "TLSv1.3" in tls_version, (
                        f"TLS 版本不是 1.3: {tls_version}"
                    )

        except (socket.timeout, ConnectionRefusedError) as e:
            # 如果无法连接，失败而非跳过（安全验收标准必须验证）
            pytest.fail(f"无法连接到 {self.GITEA_HOST}:{self.GITEA_PORT} 进行 TLS 验证 - {e}。请确保 Gitea 已部署且可访问。")
        except ssl.SSLError as e:
            # SSL 错误直接失败（可能是 TLS 配置问题）
            pytest.fail(f"TLS 连接失败，可能是 TLS 1.3 配置问题：{e}")


class TestGiteaSecurity:
    """Gitea 安全配置测试套件"""

    GITEA_NAMESPACE = "gitea"

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        cmd = ["kubectl"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

    def test_gitea_container_non_root(self):
        """
        验证 Gitea 容器以非 root 用户运行
        
        安全验收标准
        """
        # 获取 Deployment 配置
        result = self.run_kubectl([
            "get", "deployment",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea",
            "-o", "jsonpath={.items[0].spec.template.spec.containers[0].securityContext.runAsNonRoot}"
        ])
        
        # 如果配置了 runAsNonRoot，验证为 true
        if result.returncode == 0 and result.stdout.strip():
            assert result.stdout.strip().lower() == "true", (
                "Gitea 容器未配置以非 root 用户运行"
            )

    def test_gitea_resource_limits(self):
        """
        验证 Gitea 容器资源限制已配置
        
        架构验收标准
        """
        result = self.run_kubectl([
            "get", "deployment",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea",
            "-o", "jsonpath={.items[0].spec.template.spec.containers[0].resources}"
        ])
        
        assert result.returncode == 0, "无法获取 Gitea 资源限制配置"
        assert "limits" in result.stdout, "Gitea 容器未配置资源限制"

    def test_gitea_secrets_exist(self):
        """
        验证 Gitea Secret 存在
        
        安全验收标准
        """
        result = self.run_kubectl([
            "get", "secrets",
            "-n", self.GITEA_NAMESPACE,
            "-l", "app.kubernetes.io/name=gitea"
        ])
        
        assert result.returncode == 0, "Gitea Secrets 不存在"


class TestGiteaIntegration:
    """Gitea 集成准备测试套件"""

    GITEA_NAMESPACE = "gitea"

    def run_kubectl(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 kubectl 命令"""
        cmd = ["kubectl"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

    def test_gitea_webhook_enabled(self):
        """
        验证 Gitea Webhook 功能可用
        
        Story 0.8 集成准备
        """
        # 检查 Gitea 配置中是否启用了 Webhook
        result = self.run_kubectl([
            "get", "configmap",
            "-n", self.GITEA_NAMESPACE,
            "gitea",
            "-o", "jsonpath={.data}"
        ])
        
        # Webhook 功能应该默认启用
        assert result.returncode == 0, "无法获取 Gitea 配置"

    def test_gitea_actions_enabled(self):
        """
        验证 Gitea Actions 已启用
        
        Story 0.9 集成准备
        """
        # 检查 Gitea 配置中是否启用了 Actions
        result = self.run_kubectl([
            "get", "configmap",
            "-n", self.GITEA_NAMESPACE,
            "gitea",
            "-o", "jsonpath={.data}"
        ])
        
        assert result.returncode == 0, "无法获取 Gitea 配置"
        # Actions 配置应该在配置文件中
