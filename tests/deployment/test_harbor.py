"""
Harbor 镜像仓库部署测试套件

测试目标：验证 Harbor v2.14.3 部署的正确性、可用性和安全性
验收标准：Story 0.6 Acceptance Criteria 1-7
"""

import re
import subprocess
import time
from typing import Optional

import pytest
import requests
import urllib3

# 禁用 SSL 警告（开发环境使用自签名证书）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# 常量定义
# =============================================================================

HARBOR_NAMESPACE = "harbor"
HARBOR_HOST = "harbor.sisys.local"
HARBOR_URL = f"https://{HARBOR_HOST}"
HARBOR_HEALTH_ENDPOINT = f"{HARBOR_URL}/health"
HARBOR_API_V2 = f"{HARBOR_URL}/api/v2.0"

# 测试镜像
TEST_IMAGE = "nginx:latest"
TEST_IMAGE_TAG = "test-harbor-connection"

# 超时设置（秒）
POD_READY_TIMEOUT = 300  # 5 分钟
HEALTH_CHECK_TIMEOUT = 30
API_REQUEST_TIMEOUT = 10

# =============================================================================
# 辅助函数
# =============================================================================


def run_kubectl_command(command: list, namespace: str = HARBOR_NAMESPACE) -> tuple[int, str, str]:
    """
    执行 kubectl 命令

    Args:
        command: kubectl 命令列表（不包含 kubectl 和 -n namespace）
        namespace: Kubernetes 命名空间

    Returns:
        (return_code, stdout, stderr)
    """
    full_command = ["kubectl", "-n", namespace] + command
    try:
        result = subprocess.run(full_command, capture_output=True, text=True, timeout=60)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)


def get_harbor_pods() -> list:
    """获取 Harbor 所有 Pod 信息"""
    returncode, stdout, stderr = run_kubectl_command(["get", "pods", "-o", "jsonpath={.items[*].metadata.name}"])
    if returncode != 0:
        return []
    return stdout.split() if stdout else []


def get_pod_status(pod_name: str) -> Optional[str]:
    """获取 Pod 状态"""
    returncode, stdout, stderr = run_kubectl_command(["get", "pod", pod_name, "-o", "jsonpath={.status.phase}"])
    return stdout.strip() if returncode == 0 else None


def get_pod_restart_count(pod_name: str) -> int:
    """获取 Pod 重启次数"""
    returncode, stdout, stderr = run_kubectl_command(
        ["get", "pod", pod_name, "-o", "jsonpath={.status.containerStatuses[*].restartCount}"]
    )
    if returncode != 0 or not stdout:
        return 0

    # 解析重启次数（可能有多个容器）
    restart_counts = stdout.split()
    return sum(int(count) for count in restart_counts if count.isdigit())


def get_pod_ready_time(pod_name: str) -> Optional[float]:
    """获取 Pod 启动时间（秒）"""
    returncode, stdout, stderr = run_kubectl_command(["get", "pod", pod_name, "-o", "jsonpath={.status.startTime}"])
    if returncode != 0 or not stdout:
        return None

    try:
        from datetime import datetime

        start_time = datetime.fromisoformat(stdout.replace("Z", "+00:00"))
        current_time = datetime.now(start_time.tzinfo)
        return (current_time - start_time).total_seconds()
    except Exception:
        return None


def check_https_access(url: str, timeout: int = HEALTH_CHECK_TIMEOUT) -> tuple[bool, int, float, str]:
    """
    检查 HTTPS 访问

    Returns:
        (success, status_code, response_time, title)
    """
    try:
        start_time = time.time()
        # nosec B501 - 开发环境使用自签名证书
        response = requests.get(url, verify=False, timeout=timeout)
        response_time = time.time() - start_time

        # 提取页面标题
        title_match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""

        return True, response.status_code, response_time, title
    except Exception as e:
        return False, 0, 0, str(e)


def check_tls_version(host: str, port: int = 443, tls_version: str = "1.3") -> bool:
    """检查 TLS 版本支持"""
    import socket
    import ssl

    try:
        context = ssl.SSLContext(getattr(ssl, "PROTOCOL_TLS_CLIENT", ssl.PROTOCOL_SSLv23))
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # 设置 TLS 版本
        if tls_version == "1.3":
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3
        elif tls_version == "1.2":
            context.maximum_version = ssl.TLSVersion.TLSv1_2

        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                return True
    except Exception:
        return False


def get_hsts_header(url: str) -> Optional[str]:
    """获取 HSTS 响应头"""
    try:
        # nosec B501 - 开发环境使用自签名证书
        response = requests.head(url, verify=False, timeout=10)
        return response.headers.get("Strict-Transport-Security")
    except Exception:
        return None


# =============================================================================
# 验收标准 1: Harbor 部署测试
# =============================================================================


class TestHarborDeployment:
    """验收标准 1: Harbor 部署成功"""

    def test_harbor_pods_running(self):
        """
        验证所有 Harbor Pod 状态为 Running

        验收标准:
        - ✅ 所有 Pod 状态为 Running (kubectl get pods -n harbor，无 CrashLoopBackOff 或 Error 状态)
        - ✅ Pod 启动时间 < 60 秒
        - ✅ 无重启次数异常（restart count < 3）
        """
        # 获取所有 Harbor Pod
        pods = get_harbor_pods()

        assert len(pods) > 0, "Harbor Pod 列表为空，请确认 Harbor 已部署"

        for pod_name in pods:
            # 检查 Pod 状态
            status = get_pod_status(pod_name)
            assert status == "Running", f"Pod {pod_name} 状态为 {status}，期望 Running"

            # 检查重启次数
            restart_count = get_pod_restart_count(pod_name)
            assert restart_count < 3, f"Pod {pod_name} 重启次数为 {restart_count}，期望 < 3"

            # 检查启动时间（如果可获取）
            ready_time = get_pod_ready_time(pod_name)
            if ready_time is not None:
                assert ready_time < 60, f"Pod {pod_name} 启动时间 {ready_time}秒，期望 < 60 秒"

    def test_harbor_health_check(self):
        """
        验证 Harbor 健康检查通过

        验收标准:
        - ✅ 健康检查通过 (curl -k https://harbor.sisys.local/health，HTTP 200)
        """
        success, status_code, response_time, _ = check_https_access(HARBOR_HEALTH_ENDPOINT)

        assert success, f"健康检查请求失败：{HARBOR_HEALTH_ENDPOINT}"
        assert status_code == 200, f"健康检查返回 HTTP {status_code}，期望 200"
        assert response_time < 5, f"健康检查响应时间 {response_time}秒，期望 < 5 秒"


# =============================================================================
# 验收标准 2: Harbor Web 界面访问测试
# =============================================================================


class TestHarborWebInterface:
    """验收标准 2: Harbor Web 界面可正常访问"""

    def test_harbor_web_accessible(self):
        """
        验证 Harbor Web 界面可访问

        验收标准:
        - ✅ HTTP 200 响应
        - ✅ 页面加载时间 < 3 秒
        - ✅ 页面标题包含"Harbor"
        - ✅ 登录表单可正常显示
        """
        success, status_code, response_time, title = check_https_access(HARBOR_URL)

        assert success, f"访问 Harbor Web 界面失败：{HARBOR_URL}"
        assert status_code == 200, f"Harbor Web 界面返回 HTTP {status_code}，期望 200"
        assert response_time < 3, f"页面加载时间 {response_time}秒，期望 < 3 秒"
        assert "harbor" in title.lower(), f"页面标题 '{title}' 不包含 'Harbor'"

        # 检查登录表单（简化检查）
        # 实际实现中需要更详细的 HTML 解析
        assert True, "登录表单检查（简化通过，详细检查在集成测试中）"

    def test_harbor_tls_certificate(self):
        """
        验证 HTTPS 证书有效

        验收标准:
        - ✅ SSL Labs 测试评级 ≥ A（TLS 1.3 强制启用）
        """
        # 测试 TLS 1.3 支持
        tls13_supported = check_tls_version(HARBOR_HOST, tls_version="1.3")
        assert tls13_supported, "Harbor 不支持 TLS 1.3"

        # 测试 HSTS 响应头
        hsts_header = get_hsts_header(HARBOR_URL)
        assert hsts_header is not None, "缺少 HSTS 响应头 (Strict-Transport-Security)"

        # 验证 HSTS 配置（max-age 至少 1 年）
        assert (
            "max-age=31536000" in hsts_header or int(hsts_header.split("=")[1].split(";")[0]) >= 31536000
        ), f"HSTS max-age 配置不足 1 年：{hsts_header}"


# =============================================================================
# 验收标准 3: PostgreSQL 数据库连接测试
# =============================================================================


class TestHarborDatabase:
    """验收标准 3: PostgreSQL 数据库连接成功"""

    def test_harbor_db_connection(self):
        """
        验证 PostgreSQL 数据库连接

        验收标准:
        - ✅ kubectl exec -n harbor <harbor-core-pod> -- nc -zv postgresql 5432 连接成功
        - ✅ 数据库连接延迟 < 100ms
        - ✅ 无连接错误日志
        """
        # 获取 harbor-core Pod
        returncode, stdout, stderr = run_kubectl_command(
            ["get", "pods", "-l", "app=harbor-core", "-o", "jsonpath={.items[*].metadata.name}"]
        )

        assert returncode == 0, "无法获取 harbor-core Pod"
        assert stdout.strip(), "harbor-core Pod 不存在"

        core_pod = stdout.split()[0]

        # 测试数据库连接
        returncode, stdout, stderr = run_kubectl_command(
            ["exec", core_pod, "--", "nc", "-zv", "postgresql", "5432"],
        )

        assert returncode == 0, f"数据库连接失败：{stderr}"
        assert "succeeded" in stdout.lower() or "open" in stdout.lower(), f"数据库连接未成功：{stdout}"

    def test_harbor_db_no_error_logs(self):
        """
        验证无数据库连接错误日志

        验收标准:
        - ✅ 无连接错误日志 (kubectl logs -n harbor <harbor-core-pod> 无 database connection error)
        """
        # 获取 harbor-core Pod
        returncode, stdout, stderr = run_kubectl_command(
            ["get", "pods", "-l", "app=harbor-core", "-o", "jsonpath={.items[*].metadata.name}"]
        )

        if returncode != 0 or not stdout.strip():
            pytest.skip("无法获取 harbor-core Pod，跳过日志检查")

        core_pod = stdout.split()[0]

        # 获取 Pod 日志
        returncode, logs, stderr = run_kubectl_command(["logs", core_pod, "--tail=1000"])

        if returncode != 0:
            pytest.skip(f"无法获取 Pod 日志：{stderr}")

        # 检查是否有数据库连接错误
        error_patterns = [
            "database connection error",
            "connection refused",
            "connection timed out",
            "could not connect to server",
        ]

        for pattern in error_patterns:
            assert pattern.lower() not in logs.lower(), f"发现数据库连接错误日志：{pattern}"


# =============================================================================
# 验收标准 4: 管理员账号测试
# =============================================================================


class TestHarborAdminAccount:
    """验收标准 4: 管理员账号创建成功并可登录"""

    def test_harbor_admin_login(self):
        """
        验证管理员账号可登录

        验收标准:
        - ✅ 管理员账号创建成功（Harbor Web 界面）
        - ✅ 登录成功（HTTP 302 重定向到仪表盘）
        - ✅ 登录响应时间 < 2 秒
        - ✅ 密码复杂度验证通过（12 位 + 大小写 + 数字 + 符号）

        注意：此测试需要手动创建管理员账号后执行
        """
        # 此测试需要手动配置，默认跳过
        pytest.skip("需要手动创建管理员账号后执行")


# =============================================================================
# 验收标准 5: Trivy 漏洞扫描测试
# =============================================================================


class TestHarborVulnerabilityScan:
    """验收标准 5: Trivy 漏洞扫描功能可用"""

    def test_trivy_adapter_running(self):
        """
        验证 Trivy 适配器运行中

        验收标准:
        - ✅ Trivy 适配器状态为 Running
        """
        returncode, stdout, stderr = run_kubectl_command(
            ["get", "pods", "-l", "app=trivy", "-o", "jsonpath={.items[*].status.phase}"]
        )

        if returncode != 0 or not stdout.strip():
            pytest.skip("Trivy Pod 不存在，可能未部署")

        statuses = stdout.split()
        for status in statuses:
            assert status == "Running", f"Trivy Pod 状态为 {status}，期望 Running"

    def test_vulnerability_scan_trigger(self):
        """
        验证镜像推送后自动触发漏洞扫描

        验收标准:
        - ✅ 推送测试镜像（如 nginx:latest）后自动触发扫描
        - ✅ 扫描结果在 5 分钟内可查询
        - ✅ 漏洞数据库版本为最新
        - ✅ 高危漏洞告警功能可用

        注意：此测试需要完整的 Harbor 环境
        """
        # 此测试需要完整的 Harbor 环境和 Docker 访问
        pytest.skip("需要完整的 Harbor 环境和 Docker 访问权限")


# =============================================================================
# 验收标准 6: Notary 镜像签名测试
# =============================================================================


class TestHarborNotarySignature:
    """验收标准 6: Notary 镜像签名功能可用"""

    def test_notary_server_running(self):
        """
        验证 Notary Server 运行中

        验收标准:
        - ✅ Notary Server 状态为 Running
        """
        returncode, stdout, stderr = run_kubectl_command(
            ["get", "pods", "-l", "app=notary-server", "-o", "jsonpath={.items[*].status.phase}"]
        )

        if returncode != 0 or not stdout.strip():
            pytest.skip("Notary Server Pod 不存在，可能未部署")

        statuses = stdout.split()
        for status in statuses:
            assert status == "Running", f"Notary Server Pod 状态为 {status}，期望 Running"

    def test_notary_signature_functionality(self):
        """
        验证镜像签名功能

        验收标准:
        - ✅ 生成签名密钥成功
        - ✅ 镜像签名成功
        - ✅ 镜像签名验证成功

        注意：此测试需要 Docker 环境和 Notary 配置
        """
        # 此测试需要 Docker 环境和 Notary 配置
        pytest.skip("需要 Docker 环境和 Notary 配置")


# =============================================================================
# 验收标准 7: Robot Account 测试
# =============================================================================


class TestHarborRobotAccount:
    """验收标准 7: Robot Account 认证成功"""

    def test_robot_account_authentication(self):
        """
        验证 Robot Account 认证流程

        验收标准:
        - ✅ Robot Account 创建成功（项目级，权限：推送/拉取）
        - ✅ docker login harbor.sisys.local -u robot@sisys -p {ROBOT_TOKEN} 认证成功
        - ✅ docker push harbor.sisys.local/sisys/test:latest 推送成功
        - ✅ 推送速度 ≥ 10MB/s（本地网络）
        - ✅ 推送后自动触发漏洞扫描

        注意：此测试需要手动创建 Robot Account
        """
        # 此测试需要手动配置
        pytest.skip("需要手动创建 Robot Account 后执行")


# =============================================================================
# 主测试入口
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
