"""
测试配置模块 - 统一管理所有测试常量

用途:
    - 集中管理所有测试使用的常量（IP、端口、命名空间等）
    - 支持 NAT/Mirrored 网络模式自动检测
    - 支持环境变量覆盖
    - 避免硬编码和重复定义

配置优先级:
    环境变量 > 内置默认值 > 自动检测

使用方式:
    from config import TestConfig

    # 使用配置
    class TestSomething:
        def test_something(self):
            url = f"https://{TestConfig.get_harbor_node_ip()}:{TestConfig.HARBOR_NODEPORT}"
"""
import os
import subprocess
from typing import Any


class NetworkMode:
    """网络模式枚举"""

    NAT = "nat"
    MIRRORED = "mirrored"
    UNKNOWN = "unknown"


class TestConfig:
    """
    统一测试配置类

    所有测试应该从这里获取常量，而不是硬编码或各自定义

    配置优先级：
    环境变量 > 内置默认值 > 自动检测
    """

    # =============================================================================
    # 内置默认配置（所有配置都在这里）
    # =============================================================================

    # Harbor 默认配置
    HARBOR_DEFAULTS = {
        "node_ip": "localhost",
        "nodeport": 31448,  # 使用标准 HTTPS 端口（而非 31448）
        "namespace": "harbor",
        "ingress_host": "harbor.sisys.local",
        "admin_password": os.environ.get("HARBOR_PASSWORD", "your_harbor_admin_password_here"),  # 从环境变量或 CI/CD 密钥获取
    }

    # 测试超时配置（秒）
    TIMEOUTS = {
        "pod_ready": 300,  # 5 分钟
        "health_check": 30,  # 30 秒
        "api_request": 10,  # 10 秒
        "deployment_wait": 600,  # 10 分钟
        "image_push": 120,  # 2 分钟
    }

    # 测试镜像配置
    TEST_IMAGES = {
        "push_pull": "nginx:latest",
        "vulnerability_scan": "alpine:3.18",
        "cosign_sign": "nginx:1.21",
        "tag_prefix": "test-harbor-",
    }

    # 认证配置
    AUTHENTICATION = {
        "admin_username": "admin",
        "admin_password": "",  # 从环境变量 HARBOR_ADMIN_PASSWORD 读取
        "robot_account": {
            "enabled": False,
            "name": "robot$test-runner",
            "token": "",  # 从环境变量 HARBOR_ROBOT_TOKEN 读取
        },
    }

    # 测试用例配置
    TEST_CASES = {
        "enable_deployment_tests": True,
        "enable_web_interface_tests": True,
        "enable_database_tests": True,
        "enable_admin_account_tests": True,
        "enable_vulnerability_scan_tests": True,
        "enable_cosign_tests": False,
        "enable_robot_account_tests": False,
        "enable_integration_tests": False,
    }

    # CI/CD 配置
    CI_CD = {
        "ci_environment": False,
        "report_output": "test-reports/harbor",
        "coverage_output": "test-reports/harbor/coverage.xml",
        "junit_output": "test-reports/harbor/junit.xml",
    }

    # 日志配置
    LOGGING = {
        "level": "INFO",
        "file": "",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }

    # 高级配置
    ADVANCED = {
        "verify_ssl": False,
        "retry": {
            "max_attempts": 3,
            "delay": 5,
            "backoff": 2,
        },
        "concurrency": {
            "max_workers": 4,
            "max_connections": 10,
        },
    }

    # Gitea 默认配置
    GITEA_NAMESPACE = "gitea"
    GITEA_HTTP_PORT = 3000
    GITEA_NODEPORT = 30580
    GITEA_SSH_NODEPORT = 2222
    GITEA_HOST = "gitea.sisys.local"

    # ArgoCD 默认配置
    ARGOCD_NAMESPACE = "argocd"
    ARGOCD_NODEPORT = 31448
    ARGOCD_HOST = "argocd.sisys.local"

    # Harbor NodePort 配置（显式定义）
    HARBOR_NODEPORT = 31448
    HARBOR_HTTP_NODEPORT = 31080

    # K3S 配置
    K3S_NAMESPACE = "kube-system"
    TRAEFIK_NAMESPACE = "traefik"

    # =============================================================================
    # 网络配置 - 自动检测
    # =============================================================================

    @classmethod
    def detect_network_mode(cls) -> str:
        """检测当前 WSL2 网络模式"""
        try:
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
            ip = result.stdout.strip().split()[0]

            if ip.startswith("172."):
                return NetworkMode.NAT
            elif ip.startswith("192.168.") or ip.startswith("10."):
                return NetworkMode.MIRRORED
            else:
                return NetworkMode.UNKNOWN
        except Exception:
            return NetworkMode.UNKNOWN

    @classmethod
    def get_wsl2_ip(cls) -> str:
        """获取 WSL2 IP 地址"""
        try:
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
            return result.stdout.strip().split()[0]
        except Exception:
            return "127.0.0.1"

    # =============================================================================
    # Harbor 配置 - 内置配置 + 环境变量
    # =============================================================================

    @classmethod
    def get_harbor_config(cls) -> dict[str, Any]:
        """获取 Harbor 配置（合并默认配置和环境变量）"""
        # 基础配置
        config = cls.HARBOR_DEFAULTS.copy()

        # 环境变量覆盖（最高优先级）
        if os.getenv("HARBOR_NODE_IP"):
            config["node_ip"] = os.getenv("HARBOR_NODE_IP")
        if os.getenv("HARBOR_NODEPORT"):
            config["nodeport"] = int(os.getenv("HARBOR_NODEPORT", "31448"))
        if os.getenv("HARBOR_NAMESPACE"):
            config["namespace"] = os.getenv("HARBOR_NAMESPACE")
        if os.getenv("HARBOR_INGRESS_HOST"):
            config["ingress_host"] = os.getenv("HARBOR_INGRESS_HOST")

        return config

    @classmethod
    def get_timeout(cls, key: str) -> int:
        """获取超时配置"""
        return cls.TIMEOUTS.get(key, 30)

    @classmethod
    def get_test_image(cls, key: str = "push_pull") -> str:
        """获取测试镜像"""
        return cls.TEST_IMAGES.get(key, "nginx:latest")

    @classmethod
    def get_admin_credentials(cls) -> tuple[str, str]:
        """获取管理员凭证（支持环境变量）"""
        username = str(cls.AUTHENTICATION["admin_username"])
        password = os.getenv("HARBOR_ADMIN_PASSWORD", cls.AUTHENTICATION["admin_password"])
        return username, str(password)

    @classmethod
    def is_test_enabled(cls, test_type: str) -> bool:
        """检查测试类型是否启用"""
        return cls.TEST_CASES.get(test_type, False)

    @classmethod
    def get_harbor_node_ip(cls) -> str:
        """
        获取 Harbor 访问 IP

        NAT 模式：返回 localhost（通过 WSL2 端口转发）
        Mirrored 模式：返回实际 IP
        """
        # 环境变量优先
        env_ip = os.getenv("HARBOR_NODE_IP")
        if env_ip:
            return env_ip

        # 根据网络模式返回
        network_mode = cls.detect_network_mode()
        if network_mode == NetworkMode.NAT:
            return "localhost"
        else:
            return cls.get_wsl2_ip()

    @classmethod
    def get_harbor_url(cls, use_https: bool = True) -> str:
        """获取 Harbor URL"""
        ip = cls.get_harbor_node_ip()
        port = cls.get_harbor_config()["nodeport"]
        protocol = "https" if use_https else "http"
        return f"{protocol}://{ip}:{port}"

    # =============================================================================
    # Gitea 配置
    # =============================================================================

    GITEA_NAMESPACE = "gitea"
    GITEA_HTTP_PORT = 3000
    GITEA_NODEPORT = 30580
    GITEA_SSH_NODEPORT = 2222
    GITEA_HOST = "gitea.sisys.local"

    @classmethod
    def get_gitea_node_ip(cls) -> str:
        """获取 Gitea 访问 IP"""
        return cls.get_harbor_node_ip()  # 使用相同的逻辑

    @classmethod
    def get_gitea_url(cls, use_https: bool = True) -> str:
        """获取 Gitea URL"""
        ip = cls.get_gitea_node_ip()
        port = cls.GITEA_NODEPORT
        protocol = "https" if use_https else "http"
        return f"{protocol}://{ip}:{port}"

    # =============================================================================
    # ArgoCD 配置
    # =============================================================================

    ARGOCD_NAMESPACE = "argocd"
    ARGOCD_NODEPORT = 31448
    ARGOCD_HOST = "argocd.sisys.local"

    @classmethod
    def get_argocd_node_ip(cls) -> str:
        """获取 ArgoCD 访问 IP"""
        return cls.get_harbor_node_ip()

    @classmethod
    def get_argocd_url(cls, use_https: bool = True) -> str:
        """获取 ArgoCD URL"""
        ip = cls.get_argocd_node_ip()
        port = cls.ARGOCD_NODEPORT
        protocol = "https" if use_https else "http"
        return f"{protocol}://{ip}:{port}"

    # =============================================================================
    # K3S 集群配置
    # =============================================================================

    K3S_NAMESPACE = "kube-system"
    TRAEFIK_NAMESPACE = "traefik"

    # =============================================================================
    # 通用配置方法
    # =============================================================================

    @classmethod
    def get_nodeport(cls, service_name: str) -> int:
        """
        获取服务的 NodePort

        Args:
            service_name: 服务名称（harbor, gitea, argocd）

        Returns:
            NodePort 端口号
        """
        ports: dict[str, int] = {
            "harbor": int(cls.HARBOR_NODEPORT),
            "harbor-http": int(cls.HARBOR_HTTP_NODEPORT),
            "gitea": int(cls.GITEA_NODEPORT),
            "argocd": int(cls.ARGOCD_NODEPORT),
        }
        return ports.get(service_name.lower(), 31448)

    @classmethod
    def get_connect_address(cls, service_name: str) -> str:
        """
        获取服务连接地址（IP:Port）

        Args:
            service_name: 服务名称（harbor, gitea, argocd）

        Returns:
            连接地址字符串
        """
        ip = cls.get_harbor_node_ip()
        port = cls.get_nodeport(service_name)
        return f"{ip}:{port}"

    @classmethod
    def get_config_summary(cls) -> str:
        """获取配置摘要"""
        return f"""
测试配置摘要:
  网络模式：      {cls.detect_network_mode().upper()}
  WSL2 IP:        {cls.get_wsl2_ip()}

Harbor:
  Node IP:        {cls.get_harbor_node_ip()}
  NodePort:       {cls.HARBOR_NODEPORT}
  URL:            {cls.get_harbor_url()}

Gitea:
  Node IP:        {cls.get_gitea_node_ip()}
  NodePort:       {cls.GITEA_NODEPORT}
  URL:            {cls.get_gitea_url()}

ArgoCD:
  Node IP:        {cls.get_argocd_node_ip()}
  NodePort:       {cls.ARGOCD_NODEPORT}
  URL:            {cls.get_argocd_url()}

提示:
  - 可通过环境变量 HARBOR_NODE_IP 覆盖
  - NAT 模式使用 localhost 访问
  - Mirrored 模式使用实际 IP 访问
""".strip()


# =============================================================================
# 便捷常量（向后兼容）
# =============================================================================

# Harbor - 使用配置方法获取（延迟加载，支持环境变量覆盖）
HARBOR_NODE_IP = TestConfig.get_harbor_node_ip()
HARBOR_NODEPORT = TestConfig.get_harbor_config()["nodeport"]
HARBOR_NAMESPACE = TestConfig.get_harbor_config()["namespace"]
HARBOR_HOST = TestConfig.get_harbor_config()["ingress_host"]

# Gitea
GITEA_NODEPORT = TestConfig.GITEA_NODEPORT
GITEA_HOST = TestConfig.GITEA_HOST

# ArgoCD
ARGOCD_NODEPORT = TestConfig.ARGOCD_NODEPORT

# 网络配置
NETWORK_MODE = TestConfig.detect_network_mode()
WSL2_IP = TestConfig.get_wsl2_ip()


# =============================================================================
# pytest fixtures
# =============================================================================


def pytest_configure(config):
    """pytest 配置钩子"""
    # 注册自定义标记
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
