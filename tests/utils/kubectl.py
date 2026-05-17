"""
Kubernetes kubectl 工具模块

提供统一的 kubectl 命令执行接口，用于测试中操作 Kubernetes 集群

Usage:
    from tests.utils.kubectl import run_kubectl, KubectlError

    # 基本用法
    result = run_kubectl(["get", "pods", "-n", "default"])
    print(result.stdout)

    # 带错误检查
    try:
        result = run_kubectl(["get", "pod", "nonexistent"], check=True)
    except KubectlError as e:
        print(f"命令失败：{e}")

    # 指定命名空间
    result = run_kubectl(["get", "pods"], namespace="argocd")

    # 解析 JSON 输出
    pods = run_kubectl(["get", "pods", "-o", "json"], namespace="default").json()
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Any


class KubectlError(Exception):
    """kubectl 命令执行异常"""

    def __init__(self, command: list[str], returncode: int, stderr: str, stdout: str = ""):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout
        super().__init__(f"kubectl {' '.join(command)} 失败 (exit {returncode}): {stderr}")


@dataclass
class KubectlResult:
    """kubectl 命令执行结果"""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """解析 JSON 输出"""
        return json.loads(self.stdout)

    def check(self) -> "KubectlResult":
        """检查命令是否成功，失败则抛出异常"""
        if self.returncode != 0:
            raise KubectlError(self.command, self.returncode, self.stderr, self.stdout)
        return self


def run_kubectl(
    args: list[str],
    namespace: str | None = None,
    check: bool = False,
    timeout: int = 30,
    capture_output: bool = True,
    text: bool = True,
) -> KubectlResult:
    """
    执行 kubectl 命令

    Args:
        args: kubectl 命令参数（不包含 "kubectl"），如 ["get", "pods", "-n", "default"]
        namespace: 命名空间（可选），如果提供则自动添加 -n 参数
        check: 是否检查返回码，为 True 时失败会抛出 KubectlError
        timeout: 命令超时时间（秒）
        capture_output: 是否捕获输出（默认为 True）
        text: 是否以文本模式返回输出（默认为 True）

    Returns:
        KubectlResult: 命令执行结果（包含 stdout, stderr, returncode）

    Raises:
        KubectlError: 当 check=True 且命令失败时

    Examples:
        >>> result = run_kubectl(["get", "pods"])
        >>> print(result.stdout)

        >>> result = run_kubectl(["get", "pods"], namespace="argocd")
        >>> pods = result.json()

        >>> try:
        ...     result = run_kubectl(["get", "pod", "nonexistent"], check=True)
        ... except KubectlError as e:
        ...     print(f"错误：{e}")
    """
    # 构建命令
    cmd = ["kubectl"]

    # 添加命名空间参数
    if namespace:
        cmd.extend(["-n", namespace])

    # 添加用户参数
    cmd.extend(args)

    # 执行命令
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,  # 不自动抛出异常，我们自己处理
    )

    kubectl_result = KubectlResult(
        command=args,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )

    if check and result.returncode != 0:
        raise KubectlError(args, result.returncode, result.stderr, result.stdout)

    return kubectl_result


# =============================================================================
# 便捷函数（常用 kubectl 操作）
# =============================================================================


def get(
    resource: str,
    name: str | None = None,
    namespace: str | None = None,
    output: str = "",
    labels: str | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl get 命令

    Args:
        resource: 资源类型，如 "pods", "deployments", "services"
        name: 资源名称（可选）
        namespace: 命名空间
        output: 输出格式，如 "json", "yaml"
        labels: 标签选择器，如 "app=nginx"
        check: 是否检查错误

    Examples:
        >>> get("pods", namespace="default")
        >>> get("pod", "my-pod", namespace="default", output="json")
        >>> get("pods", labels="app=nginx", namespace="default")
    """
    args = ["get", resource]
    if name:
        args.append(name)
    if namespace:
        args.extend(["-n", namespace])
    if output:
        args.extend(["-o", output])
    if labels:
        args.extend(["-l", labels])

    result = run_kubectl(args, check=check)
    assert isinstance(result, KubectlResult)
    return result


def describe(
    resource: str,
    name: str,
    namespace: str | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl describe 命令

    Examples:
        >>> describe("pod", "my-pod", namespace="default")
    """
    args = ["describe", resource, name]
    if namespace:
        args.extend(["-n", namespace])

    result = run_kubectl(args, check=check)
    assert isinstance(result, KubectlResult)
    return result


def create(
    manifest: str,
    namespace: str | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl create 命令（从 YAML/JSON 字符串创建）

    Args:
        manifest: Kubernetes 资源清单（YAML 或 JSON 格式）
        namespace: 命名空间
        check: 是否检查错误

    Examples:
        >>> create('''
        ... apiVersion: v1
        ... kind: Pod
        ... metadata:
        ...   name: test-pod
        ... spec:
        ...   containers:
        ...   - name: nginx
        ...     image: nginx
        ... ''')
    """
    args = ["create", "-f", "-"]
    if namespace:
        args.extend(["-n", namespace])

    result = subprocess.run(
        ["kubectl"] + args,
        input=manifest,
        capture_output=True,
        text=True,
        check=check,
    )
    return KubectlResult(
        command=["kubectl"] + args,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def apply(
    manifest: str,
    namespace: str | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl apply 命令（从 YAML/JSON 字符串应用）

    Examples:
        >>> apply('''
        ... apiVersion: v1
        ... kind: ConfigMap
        ... metadata:
        ...   name: my-config
        ... data:
        ...   key: value
        ... ''')
    """
    args = ["apply", "-f", "-"]
    if namespace:
        args.extend(["-n", namespace])

    result = subprocess.run(
        ["kubectl"] + args,
        input=manifest,
        capture_output=True,
        text=True,
        check=check,
    )
    return KubectlResult(
        command=["kubectl"] + args,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def delete(
    resource: str,
    name: str | None = None,
    namespace: str | None = None,
    labels: str | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl delete 命令

    Examples:
        >>> delete("pod", "my-pod", namespace="default")
        >>> delete("pods", labels="app=test", namespace="default")
    """
    args = ["delete", resource]
    if name:
        args.append(name)
    if namespace:
        args.extend(["-n", namespace])
    if labels:
        args.extend(["-l", labels])

    return run_kubectl(args, check=check)


def wait(
    resource: str,
    name: str,
    condition: str = "Ready",
    namespace: str | None = None,
    timeout: str = "60s",
    check: bool = False,
) -> KubectlResult:
    """
    kubectl wait 命令

    Examples:
        >>> wait("pod", "my-pod", condition="Ready", namespace="default", timeout="120s")
    """
    args = [
        "wait",
        resource,
        name,
        "--for",
        f"condition={condition}",
        "--timeout",
        timeout,
    ]
    if namespace:
        args.extend(["-n", namespace])

    return run_kubectl(args, timeout=120, check=check)


def logs(
    pod: str,
    namespace: str | None = None,
    container: str | None = None,
    follow: bool = False,
    tail: int | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl logs 命令

    Examples:
        >>> logs("my-pod", namespace="default")
        >>> logs("my-pod", container="nginx", tail=100)
    """
    args = ["logs", pod]
    if namespace:
        args.extend(["-n", namespace])
    if container:
        args.extend(["-c", container])
    if follow:
        args.append("-f")
    if tail:
        args.extend(["--tail", str(tail)])

    return run_kubectl(args, timeout=60, check=check)


def exec_command(
    pod: str,
    command: list[str],
    namespace: str | None = None,
    container: str | None = None,
    check: bool = False,
) -> KubectlResult:
    """
    kubectl exec 命令

    Examples:
        >>> exec_command("my-pod", ["ls", "-la"], namespace="default")
        >>> exec_command("my-pod", ["cat", "/etc/config"], container="sidecar")
    """
    args = ["exec", pod, "--"]
    if namespace:
        args.extend(["-n", namespace])
    if container:
        args.extend(["-c", container])
    args.extend(command)

    return run_kubectl(args, check=check)


# =============================================================================
# 上下文管理器（用于临时资源）
# =============================================================================

from contextlib import contextmanager  # noqa: E402


@contextmanager
def temporary_resource(manifest: str, namespace: str | None = None):
    """
    上下文管理器：创建临时资源，退出时自动删除

    Args:
        manifest: Kubernetes 资源清单
        namespace: 命名空间

    Yields:
        str: 资源名称（从 manifest 中解析）

    Examples:
        >>> with temporary_resource(pod_manifest, namespace="default") as pod_name:
        ...     # 使用临时 Pod
        ...     result = exec_command(pod_name, ["echo", "hello"])
    """
    import yaml

    # 解析资源名称
    resource_data = yaml.safe_load(manifest)
    kind = resource_data["kind"].lower()
    name = resource_data["metadata"]["name"]

    try:
        # 创建资源
        create(manifest, namespace=namespace, check=True)
        yield name
    finally:
        # 删除资源
        delete(kind, name, namespace=namespace, check=False)
