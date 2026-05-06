"""
测试辅助模块 - Kubernetes 和 ArgoCD 测试工具

提供通用的测试辅助函数和 fixture，避免代码重复。
"""

import subprocess
from pathlib import Path

import pytest


def get_sudo_password() -> str:
    """
    获取 sudo 密码（从 QWEN.md 或环境变量）

    Returns:
        sudo 密码，如果未找到则返回空字符串
    """
    # 从 QWEN.md 读取密码
    qwem_path = Path(__file__).parents[2] / "QWEN.md"
    if qwem_path.exists():
        content = qwem_path.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "sudo 密码" in line:
                return line.replace("sudo 密码", "").strip()
    return ""


def run_kubectl(args: list, check: bool = False, timeout: int = 30) -> subprocess.CompletedProcess:
    """
    运行 kubectl 命令（带 sudo 权限）

    Args:
        args: kubectl 命令参数列表
        check: 是否检查命令执行结果（失败则抛出异常）
        timeout: 命令超时时间（秒）

    Returns:
        subprocess.CompletedProcess 结果对象

    Note:
        由于 pytest 捕获输出会干扰 sudo 密码输入，
        建议在测试中使用 pytest.skip() 处理权限问题，
        或配置 sudo 免密码（/etc/sudoers）
    """
    try:
        # 尝试直接使用 sudo（依赖 sudo 配置）
        cmd = f"sudo kubectl {' '.join(args)}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0:
            return result

        # 如果是权限问题，返回结果让调用者处理
        return result

    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(args=cmd, returncode=-1, stdout="", stderr="命令超时")
        if check:
            pytest.fail(f"kubectl 命令超时（>{timeout}秒）")
        return result
    except Exception as e:
        result = subprocess.CompletedProcess(args=cmd, returncode=-1, stdout="", stderr=str(e))
        if check:
            pytest.fail(f"kubectl 命令异常：{e}")
        return result


def kubectl_available() -> bool:
    """
    检查 kubectl 是否可用

    Returns:
        True 如果 kubectl 可用，False 否则
    """
    result = run_kubectl(["version", "--client"])
    return result.returncode == 0


def get_namespace_pods(namespace: str) -> list:
    """
    获取指定命名空间的 Pod 列表

    Args:
        namespace: Kubernetes 命名空间

    Returns:
        Pod 名称列表，如果无法访问则返回空列表
    """
    result = run_kubectl(["get", "pods", "-n", namespace, "-o", "jsonpath={.items[*].metadata.name}"])
    if result.returncode == 0:
        return result.stdout.strip().split() if result.stdout.strip() else []
    return []


def get_secret_value(namespace: str, secret_name: str, key: str) -> str | None:
    """
    获取 Kubernetes Secret 的值

    Args:
        namespace: 命名空间
        secret_name: Secret 名称
        key: Secret 中的键

    Returns:
        Secret 值（base64 解码后），如果获取失败则返回 None
    """
    import base64

    result = run_kubectl(["get", "secret", secret_name, "-n", namespace, "-o", f"jsonpath={{.data.{key}}}"])

    if result.returncode == 0 and result.stdout.strip():
        try:
            return base64.b64decode(result.stdout.strip()).decode("utf-8")
        except Exception:
            return None
    return None


# pytest fixtures


@pytest.fixture(scope="session")
def kubectl_available_fixture() -> bool:
    """Fixture: 检查 kubectl 是否可用"""
    return kubectl_available()


@pytest.fixture(scope="session")
def sudo_password() -> str:
    """Fixture: 提供 sudo 密码"""
    return get_sudo_password()


@pytest.fixture
def argocd_namespace() -> str:
    """Fixture: ArgoCD 命名空间"""
    return "argocd"


@pytest.fixture
def gitea_namespace() -> str:
    """Fixture: Gitea 命名空间"""
    return "gitea"
