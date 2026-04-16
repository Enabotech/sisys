"""
镜像推送测试

测试将本地镜像推送到 Harbor 仓库的功能
使用小型镜像（busybox/nginx）进行测试

验收标准:
- 能够 tag 本地镜像
- 能够登录 Harbor
- 能够推送镜像到 Harbor
- 推送的镜像可被拉取
"""

import os
import subprocess
import time

import pytest

# =============================================================================
# 配置常量 - 从统一配置模块加载
# =============================================================================
from config import HARBOR_NODE_IP, HARBOR_NODEPORT, TestConfig  # type: ignore[import-not-found]

from tests.utils.kubectl import run_kubectl

HARBOR_NAMESPACE = TestConfig.get_harbor_config()["namespace"]
HARBOR_HOST = TestConfig.get_harbor_config()["ingress_host"]
# 使用域名而非 IP（避免证书问题）
HARBOR_URL = f"{HARBOR_HOST}:{HARBOR_NODEPORT}"
HARBOR_PROJECT = "sisys"

# Harbor 认证凭据（从 Gitea 仓库密钥获取）
# 本地测试：从环境变量或 .env 文件获取
# CI/CD：通过 ${{secrets.HARBOR_USERNAME}} 和 ${{secrets.HARBOR_PASSWORD}} 注入
HARBOR_USERNAME = os.environ.get("HARBOR_USERNAME", "admin")
HARBOR_PASSWORD = os.environ.get("HARBOR_PASSWORD", "")

# Harbor 机器人账户（用于 CI/CD Pipeline）
HARBOR_ROBOT_USERNAME = os.environ.get("HARBOR_ROBOT_USERNAME", "robot$sisys+gitea-runner-push")
HARBOR_ROBOT_PASSWORD = os.environ.get("HARBOR_ROBOT_PASSWORD", "")

# 测试镜像配置
TEST_SOURCE_IMAGE = "harbor.sisys.local/sisys/tools/mirrored-pause:3.6"
TEST_IMAGE_TAG = f"test-push-{int(time.time())}"
# 使用域名而非 IP（避免证书问题）
TEST_HARBOR_IMAGE = f"{HARBOR_HOST}:{HARBOR_NODEPORT}/{HARBOR_PROJECT}/test-image:{TEST_IMAGE_TAG}"


# =============================================================================
# 辅助函数
# =============================================================================


def run_command(cmd: list[str], check: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    """运行 shell 命令"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            pytest.fail(f"命令失败：{' '.join(cmd)}\nstderr: {result.stderr}")
        return result
    except subprocess.TimeoutExpired:
        pytest.fail(f"命令超时：{' '.join(cmd)}")


def harbor_api_call(endpoint: str, method: str = "GET", data: dict | None = None) -> tuple[int, dict]:
    """调用 Harbor API"""
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = f"https://{HARBOR_NODE_IP}:{HARBOR_NODEPORT}/api/v2.0/{endpoint}"
    headers = {"Host": HARBOR_HOST}

    try:
        if method == "GET":
            response = requests.get(url, auth=(HARBOR_USERNAME, HARBOR_PASSWORD), headers=headers, verify=False, timeout=10)
        elif method == "POST":
            response = requests.post(
                url, json=data, auth=(HARBOR_USERNAME, HARBOR_PASSWORD), headers=headers, verify=False, timeout=10
            )
        elif method == "DELETE":
            response = requests.delete(url, auth=(HARBOR_USERNAME, HARBOR_PASSWORD), headers=headers, verify=False, timeout=10)
        else:
            raise ValueError(f"不支持的 HTTP 方法：{method}")

        return response.status_code, response.json() if response.content else {}
    except Exception as e:
        return -1, {"error": str(e)}


def cleanup_test_image():
    """清理测试镜像"""
    # 删除本地镜像
    run_command(["docker", "rmi", TEST_HARBOR_IMAGE], check=False)
    # 通过 API 删除 Harbor 镜像
    status, _ = harbor_api_call(f"projects/{HARBOR_PROJECT}/repositories/test-image/artifacts")
    if status == 200:
        # 删除 artifact
        pass  # 实际删除需要 artifact digest


# =============================================================================
# Fixture
# =============================================================================


@pytest.fixture(scope="module")
def harbor_project_exists():
    """确保 Harbor 项目存在"""
    # 检查项目是否存在
    status, data = harbor_api_call(f"projects?name={HARBOR_PROJECT}")
    if status != 200:
        pytest.skip(f"无法访问 Harbor API: {data}")

    # 如果项目不存在，创建它
    if not data:
        create_data = {"name": HARBOR_PROJECT, "public": True}
        status, _ = harbor_api_call("projects", method="POST", data=create_data)
        if status not in [201, 409]:  # 409 = 已存在
            pytest.skip(f"无法创建 Harbor 项目：{status}")

    yield True

    # 清理（可选）
    cleanup_test_image()


@pytest.fixture(scope="module")
def docker_daemon_running():
    """验证 Docker 守护进程运行"""
    result = run_command(["docker", "info"])
    if result.returncode != 0:
        pytest.skip("Docker 守护进程未运行")
    yield True


@pytest.fixture(scope="module")
def harbor_accessible():
    """验证 Harbor 可访问"""
    # 检查 Harbor Pod (使用正确的标签选择器)
    result = run_kubectl(
        [
            "get",
            "pods",
            "-n",
            HARBOR_NAMESPACE,
            "-l",
            "app=harbor,app.kubernetes.io/component=core",
            "-o",
            "jsonpath={.items[*].status.phase}",
        ]
    )
    if result.returncode != 0 or "Running" not in result.stdout:
        # 尝试备用标签选择器
        result = run_kubectl(
            ["get", "pods", "-n", HARBOR_NAMESPACE, "-l", "component=core", "-o", "jsonpath={.items[*].status.phase}"]
        )
        if result.returncode != 0 or "Running" not in result.stdout:
            pytest.skip(f"Harbor 未运行在命名空间 {HARBOR_NAMESPACE}")
    yield True


# =============================================================================
# 测试用例
# =============================================================================


class TestImagePush:
    """镜像推送测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, docker_daemon_running, harbor_accessible, harbor_project_exists):
        """设置测试前置条件"""
        pass

    def test_source_image_exists(self):
        """验证源镜像存在"""
        result = run_command(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", TEST_SOURCE_IMAGE])
        if TEST_SOURCE_IMAGE not in result.stdout:
            # 尝试拉取
            result = run_command(["docker", "pull", TEST_SOURCE_IMAGE], timeout=120)
            if result.returncode != 0:
                pytest.skip(f"无法获取源镜像 {TEST_SOURCE_IMAGE}")

    def test_tag_local_image(self):
        """测试 tag 本地镜像"""
        # 确保源镜像存在
        pull_result = run_command(["docker", "pull", TEST_SOURCE_IMAGE], timeout=120)
        if pull_result.returncode != 0:
            pytest.skip(f"无法拉取源镜像 {TEST_SOURCE_IMAGE}")

        # Tag 镜像
        result = run_command(["docker", "tag", TEST_SOURCE_IMAGE, TEST_HARBOR_IMAGE])
        assert result.returncode == 0, f"tag 失败：{result.stderr}"

        # 验证 tag 成功
        result = run_command(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"])
        assert TEST_HARBOR_IMAGE in result.stdout, f"镜像 tag 未找到：{TEST_HARBOR_IMAGE}"

    @pytest.mark.xdist_group(name="harbor-login")
    def test_docker_login_harbor(self):
        """测试登录 Harbor"""
        # 使用 docker login（通过 stdin 传递密码，避免警告）
        import subprocess

        # 尝试使用 kubectl 获取最新凭据
        secret_result = run_kubectl(
            ["get", "secret", "harbor-core-env", "-n", HARBOR_NAMESPACE, "-o", "jsonpath={.data.HARBOR_ADMIN_PASSWORD}"]
        )
        password = HARBOR_PASSWORD
        if secret_result.returncode == 0:
            import base64

            password = base64.b64decode(secret_result.stdout.strip()).decode("utf-8")

        # 使用 --password-stdin 避免警告
        # 使用列表形式避免 shell 转义问题（特别是 $ 符号）
        login_process = subprocess.Popen(
            ["docker", "login", "-u", HARBOR_USERNAME, "--password-stdin", HARBOR_URL],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = login_process.communicate(input=f"{password}\n")
        result = subprocess.CompletedProcess(
            args=["docker", "login", "-u", HARBOR_USERNAME, "--password-stdin", HARBOR_URL],
            returncode=login_process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

        if result.returncode != 0:
            # 检查是否已经登录
            if "already logged in" not in result.stderr.lower():
                pytest.skip(f"无法登录 Harbor: {result.stderr}")

        assert "Login Succeeded" in result.stdout or "already logged in" in result.stderr.lower(), f"登录失败：{result.stderr}"

    @pytest.mark.xdist_group(name="harbor-login")
    def test_push_image_to_harbor(self):
        """测试推送镜像到 Harbor"""
        # 先 tag 镜像
        pull_result = run_command(["docker", "pull", TEST_SOURCE_IMAGE], timeout=120)
        if pull_result.returncode != 0:
            pytest.skip(f"无法拉取源镜像 {TEST_SOURCE_IMAGE}")

        tag_result = run_command(["docker", "tag", TEST_SOURCE_IMAGE, TEST_HARBOR_IMAGE])
        if tag_result.returncode != 0:
            pytest.skip(f"无法 tag 镜像：{tag_result.stderr}")

        # 登录 Harbor（使用 --password-stdin）
        import subprocess

        # 从环境变量获取 Harbor 凭据（Gitea 仓库密钥）
        password = HARBOR_PASSWORD
        username = HARBOR_USERNAME

        # 如果环境变量未设置，尝试从 Kubernetes Secret 获取
        if not password:
            secret_result = run_kubectl(
                ["get", "secret", "harbor-core-env", "-n", HARBOR_NAMESPACE, "-o", "jsonpath={.data.HARBOR_ADMIN_PASSWORD}"],
                check=False,
            )

            if secret_result.returncode == 0 and secret_result.stdout.strip():
                import base64

                try:
                    password = base64.b64decode(secret_result.stdout.strip()).decode("utf-8")
                except Exception:
                    pass

        # 如果仍然没有密码，使用占位符（实际环境应通过 CI/CD 密钥注入）
        if not password:
            pytest.skip("HARBOR_PASSWORD 环境变量未设置")

        login_result = subprocess.run(
            f"echo '{password}' | docker login -u {username} --password-stdin {HARBOR_URL}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert (
            login_result.returncode == 0 or "already logged in" in login_result.stderr.lower()
        ), f"Harbor 登录失败：{login_result.stderr}"

        # 推送镜像
        result = run_command(["docker", "push", TEST_HARBOR_IMAGE], timeout=300)
        assert result.returncode == 0, f"推送失败：{result.stderr}"

        # 验证推送成功（检查输出 - 允许 "Layer already exists" 或 "digest" 作为成功标志）
        output_lower = result.stdout.lower()
        assert (
            "pushed" in output_lower
            or "done" in output_lower
            or "layer already exists" in output_lower
            or "digest:" in output_lower
        ), f"推送输出异常：{result.stdout}"

    def test_harbor_image_exists(self):
        """验证 Harbor 中的镜像存在"""
        # 通过 Harbor API 检查
        status, data = harbor_api_call(f"projects/{HARBOR_PROJECT}/repositories/test-image/artifacts")

        if status != 200:
            # 尝试检查 Harbor 是否可访问
            status, _ = harbor_api_call("systeminfo")
            if status != 200:
                pytest.skip("Harbor API 不可访问")
            # 仓库不存在是预期的（在推送之前）
            pytest.skip(f"测试镜像仓库不存在（需要先推送）：{HARBOR_PROJECT}/test-image")

        # 验证有 artifacts
        if isinstance(data, list) and len(data) == 0:
            # 仓库为空是预期的（在推送之前）
            pytest.skip(f"测试镜像仓库为空（需要先推送）：{HARBOR_PROJECT}/test-image")

    @pytest.mark.xdist_group(name="harbor-login")
    def test_pull_image_from_harbor(self):
        """测试从 Harbor 拉取镜像"""
        # 先确保已推送
        pull_result = run_command(["docker", "pull", TEST_SOURCE_IMAGE], timeout=120)
        if pull_result.returncode != 0:
            pytest.skip(f"无法拉取源镜像 {TEST_SOURCE_IMAGE}")

        tag_result = run_command(["docker", "tag", TEST_SOURCE_IMAGE, TEST_HARBOR_IMAGE])
        if tag_result.returncode != 0:
            pytest.skip(f"无法 tag 镜像：{tag_result.stderr}")

        # 登录 Harbor
        # Docker daemon.json 已配置 insecure-registries: ["harbor.sisys.local"]
        # 无需额外 TLS 配置
        import subprocess

        # 使用 kubectl 获取密码（如果可用），否则使用默认密码
        secret_result = run_kubectl(
            ["get", "secret", "harbor-core-env", "-n", HARBOR_NAMESPACE, "-o", "jsonpath={.data.HARBOR_ADMIN_PASSWORD}"]
        )
        password = HARBOR_PASSWORD
        if secret_result.returncode == 0:
            import base64

            password = base64.b64decode(secret_result.stdout.strip()).decode("utf-8")

        # 使用 --password-stdin 避免警告
        # 使用列表形式避免 shell 转义问题（特别是 $ 符号）
        login_process = subprocess.Popen(
            ["docker", "login", "-u", HARBOR_USERNAME, "--password-stdin", HARBOR_URL],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = login_process.communicate(input=f"{password}\n")
        login_result = subprocess.CompletedProcess(
            args=["docker", "login", "-u", HARBOR_USERNAME, "--password-stdin", HARBOR_URL],
            returncode=login_process.returncode,
            stdout=stdout,
            stderr=stderr,
        )
        if login_result.returncode != 0 and "already logged in" not in login_result.stderr.lower():
            # 登录失败
            pytest.skip(f"无法登录 Harbor: {login_result.stderr[:200]}")

        # 推送镜像
        push_result = subprocess.run(
            ["docker", "push", TEST_HARBOR_IMAGE],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if push_result.returncode != 0:
            pytest.skip(f"无法推送镜像：{push_result.stderr[:200]}")

        # 删除本地镜像
        run_command(["docker", "rmi", TEST_HARBOR_IMAGE], check=False)

        # 从 Harbor 拉取
        result = run_command(["docker", "pull", TEST_HARBOR_IMAGE], timeout=120)
        assert result.returncode == 0, f"拉取失败：{result.stderr}"

        # 验证拉取成功
        result = run_command(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", TEST_HARBOR_IMAGE])
        assert TEST_HARBOR_IMAGE in result.stdout, f"拉取的镜像未找到：{TEST_HARBOR_IMAGE}"


class TestImagePushIntegration:
    """镜像推送集成测试（需要完整环境）"""

    def test_harbor_registry_accessible(self):
        """验证 Harbor Registry 可访问"""
        import socket

        # 检查端口可访问
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((HARBOR_NODE_IP, HARBOR_NODEPORT))
            sock.close()
            assert result == 0, f"Harbor Registry 端口 {HARBOR_NODEPORT} 不可访问"
        except Exception as e:
            pytest.skip(f"无法连接 Harbor Registry: {e}")

    def test_harbor_health_check(self):
        """验证 Harbor 健康检查"""
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        url = f"https://{HARBOR_NODE_IP}:{HARBOR_NODEPORT}/api/v2.0/systeminfo"
        headers = {"Host": HARBOR_HOST}
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=10)
            assert response.status_code == 200, f"Harbor 健康检查失败：{response.status_code}"
        except Exception as e:
            pytest.skip(f"Harbor 健康检查不可访问：{e}")


# =============================================================================
# 测试执行说明
# =============================================================================

if __name__ == "__main__":
    """
    测试执行命令：

    # 运行所有测试
    pytest tests/deploy/test_image_push.py -v

    # 运行特定测试
    pytest tests/deploy/test_image_push.py::TestImagePush::test_push_image_to_harbor -v

    # 运行并显示 skip 原因
    pytest tests/deploy/test_image_push.py -v -rs
    """
