# =============================================================================
# SISYS 测试环境配置解析
# =============================================================================
# 用途：根据不同测试环境（Local/CI/K8s）自动适配服务连接参数
# Story: 20-1 (sisys-testing-refactor) - Phase 2
# =============================================================================

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


class TestEnvironment(Enum):
    """测试环境枚举"""

    LOCAL = "local"  # 本地开发环境
    CI = "ci"  # CI/CD 环境
    K8S = "k8s"  # Kubernetes 集群环境


@dataclass
class RedisConfig:
    """Redis 配置"""

    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db: int = 0
    ssl: bool = False

    @property
    def url(self) -> str:
        """生成 Redis URL"""
        auth = f":{self.password}@" if self.password else ""
        ssl = "s" if self.ssl else ""
        return f"redis{ssl}://{auth}{self.host}:{self.port}/{self.db}"


@dataclass
class PostgreSQLConfig:
    """PostgreSQL 配置"""

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    database: str = "sisys"
    ssl: bool = False

    @property
    def url(self) -> str:
        """生成 PostgreSQL URL"""
        ssl_mode = "sslmode=require" if self.ssl else "sslmode=disable"
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?{ssl_mode}"


@dataclass
class QdrantConfig:
    """Qdrant 配置"""

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: str | None = None
    https: bool = False
    timeout: float = 30.0

    @property
    def url(self) -> str:
        """生成 Qdrant URL"""
        scheme = "https" if self.https else "http"
        return f"{scheme}://{self.host}:{self.port}"


@dataclass
class MinIOConfig:
    """MinIO 配置"""

    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "sisys"
    region: str = "us-east-1"
    secure: bool = False


@dataclass
class Neo4jConfig:
    """Neo4j 配置"""

    host: str = "localhost"
    http_port: int = 7474
    bolt_port: int = 7687
    username: str = "neo4j"
    password: str = "password123"
    database: str = "neo4j"

    @property
    def bolt_url(self) -> str:
        """生成 Neo4j Bolt URL"""
        return f"bolt://{self.host}:{self.bolt_port}"


@dataclass
class RabbitMQConfig:
    """RabbitMQ 配置"""

    host: str = "localhost"
    port: int = 5672
    mgmt_port: int = 15672
    username: str = "guest"
    password: str = "guest"
    vhost: str = "/"

    @property
    def url(self) -> str:
        """生成 RabbitMQ URL"""
        return f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{self.vhost}"


@dataclass
class TestEnvConfig:
    """测试环境完整配置"""

    env: TestEnvironment = TestEnvironment.LOCAL
    redis: RedisConfig = field(default_factory=RedisConfig)
    postgres: PostgreSQLConfig = field(default_factory=PostgreSQLConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    minio: MinIOConfig = field(default_factory=MinIOConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    rabbitmq: RabbitMQConfig = field(default_factory=RabbitMQConfig)


# =============================================================================
# 环境检测函数
# =============================================================================


def _is_running_in_k8s() -> bool:
    """检测是否运行在 Kubernetes 集群中"""
    # 检查 IN_CLUSTER 模式
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return True
    # 检查 token 文件
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        return True
    return False


def _is_running_in_container() -> bool:
    """检测是否运行在容器中"""
    # 检查 .dockerenv 文件
    if os.path.exists("/.dockerenv"):
        return True
    # 检查 cgroup 信息
    try:
        with open("/proc/1/cgroup") as f:
            content = f.read()
            if "docker" in content or "containerd" in content or "cri" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass
    return False


# =============================================================================
# 环境配置映射
# =============================================================================

LOCAL_CONFIG = TestEnvConfig(
    env=TestEnvironment.LOCAL,
    redis=RedisConfig(host="localhost", port=6379),
    postgres=PostgreSQLConfig(host="localhost", port=5432),
    qdrant=QdrantConfig(host="localhost", port=6333, grpc_port=6334),
    minio=MinIOConfig(endpoint="localhost:9000"),
    neo4j=Neo4jConfig(host="localhost", http_port=7474, bolt_port=7687),
    rabbitmq=RabbitMQConfig(host="localhost", port=5672, mgmt_port=15672),
)

CI_CONFIG = TestEnvConfig(
    env=TestEnvironment.CI,
    redis=RedisConfig(host="host.docker.internal", port=6379),
    postgres=PostgreSQLConfig(host="host.docker.internal", port=5432),
    qdrant=QdrantConfig(host="host.docker.internal", port=6333, grpc_port=6334),
    minio=MinIOConfig(endpoint="host.docker.internal:9000"),
    neo4j=Neo4jConfig(host="host.docker.internal", http_port=7474, bolt_port=7687),
    rabbitmq=RabbitMQConfig(host="host.docker.internal", port=5672, mgmt_port=15672),
)

K8S_CONFIG = TestEnvConfig(
    env=TestEnvironment.K8S,
    redis=RedisConfig(host="sisys-redis", port=6379),
    postgres=PostgreSQLConfig(host="sisys-postgres", port=5432),
    qdrant=QdrantConfig(host="sisys-qdrant", port=6333, grpc_port=6334),
    minio=MinIOConfig(endpoint="sisys-minio:9000"),
    neo4j=Neo4jConfig(host="sisys-neo4j", http_port=7474, bolt_port=7687),
    rabbitmq=RabbitMQConfig(host="sisys-rabbitmq", port=5672, mgmt_port=15672),
)

TEST_CONFIG = TestEnvConfig(
    env=TestEnvironment.LOCAL,
    redis=RedisConfig(host="localhost", port=6380),  # 测试专用端口
    postgres=PostgreSQLConfig(host="localhost", port=5433),
    qdrant=QdrantConfig(host="localhost", port=6335, grpc_port=6336),
    minio=MinIOConfig(endpoint="localhost:9010"),
    neo4j=Neo4jConfig(host="localhost", http_port=7475, bolt_port=7688),
    rabbitmq=RabbitMQConfig(host="localhost", port=5673, mgmt_port=15673),
)


# =============================================================================
# 全局单例
# =============================================================================

_test_env_config: TestEnvConfig | None = None
_test_env_lock = threading.Lock()


def resolve_env() -> TestEnvironment:
    """解析当前测试环境

    检测优先级（从高到低）:
    1. SISYS_TEST_ENV 环境变量（最高优先级）
    2. CI 环境变量（如 GITHUB_ACTIONS, GITLAB_CI 等）
    3. Kubernetes 检测（KUBERNETES_SERVICE_HOST 或 token 文件）
    4. 容器检测（.dockerenv 或 cgroup）
    5. 默认返回 LOCAL
    """
    # 最高优先级：显式设置的环境变量
    explicit_env = os.getenv("SISYS_TEST_ENV", "").lower()
    if explicit_env:
        if explicit_env == "ci":
            return TestEnvironment.CI
        elif explicit_env == "k8s" or explicit_env == "kubernetes":
            return TestEnvironment.K8S
        elif explicit_env == "local":
            return TestEnvironment.LOCAL
        elif explicit_env == "test":
            return TestEnvironment.LOCAL
        else:
            raise ValueError(f"Unknown SISYS_TEST_ENV value: {explicit_env}")

    # CI 环境变量检测
    ci_vars = [
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_HOME",
        "BUILDKITE",
        "CIRCLECI",
        "TRAVIS",
        "BITBUCKET_COMMIT",
        "TEAMCITY_VERSION",
    ]
    for var in ci_vars:
        if os.getenv(var):
            return TestEnvironment.CI

    # Kubernetes 检测
    if _is_running_in_k8s():
        return TestEnvironment.K8S

    # 容器检测
    if _is_running_in_container():
        return TestEnvironment.CI

    # 默认本地环境
    return TestEnvironment.LOCAL


def get_test_env() -> TestEnvConfig:
    """获取测试环境配置（单例）

    支持从环境变量覆盖服务主机地址:
    - REDIS_HOST, REDIS_PORT
    - POSTGRES_HOST, POSTGRES_PORT
    - QDRANT_HOST, QDRANT_PORT, QDRANT_GRPC_PORT
    - MINIO_HOST
    - NEO4J_HOST
    - RABBITMQ_HOST, RABBITMQ_PORT
    """
    global _test_env_config

    if _test_env_config is not None:
        return _test_env_config

    with _test_env_lock:
        # 双重检查锁定
        if _test_env_config is not None:
            return _test_env_config

        # 加载 .env 作为基础配置
        load_dotenv(ROOT / ".env", override=False)

        env = resolve_env()

        # 根据环境选择基础配置
        if env == TestEnvironment.CI:
            base_config = CI_CONFIG
        elif env == TestEnvironment.K8S:
            base_config = K8S_CONFIG
        elif env == TestEnvironment.LOCAL:
            if os.getenv("SISYS_USE_TEST_PORTS", "").lower() in ("1", "true", "yes"):
                base_config = TEST_CONFIG
            else:
                base_config = LOCAL_CONFIG
        else:
            base_config = LOCAL_CONFIG

        # 从环境变量覆盖主机地址
        _test_env_config = _override_config_from_env(base_config)

        return _test_env_config


def _override_config_from_env(base_config: TestEnvConfig) -> TestEnvConfig:
    """从环境变量覆盖配置"""
    import copy

    config = copy.deepcopy(base_config)

    # Redis
    if redis_host := os.getenv("REDIS_HOST"):
        config.redis.host = redis_host
    if redis_port := os.getenv("REDIS_PORT"):
        config.redis.port = int(redis_port)

    # PostgreSQL
    if pg_host := os.getenv("POSTGRES_HOST"):
        config.postgres.host = pg_host
    if pg_port := os.getenv("POSTGRES_PORT"):
        config.postgres.port = int(pg_port)

    # Qdrant
    if qdrant_host := os.getenv("QDRANT_HOST"):
        config.qdrant.host = qdrant_host
    if qdrant_port := os.getenv("QDRANT_PORT"):
        config.qdrant.port = int(qdrant_port)
    if qdrant_grpc_port := os.getenv("QDRANT_GRPC_PORT"):
        config.qdrant.grpc_port = int(qdrant_grpc_port)

    # MinIO
    if minio_host := os.getenv("MINIO_HOST"):
        # MinIO endpoint 格式是 host:port
        config.minio.endpoint = f"{minio_host}:9000"

    # Neo4j
    if neo4j_host := os.getenv("NEO4J_HOST"):
        config.neo4j.host = neo4j_host

    # RabbitMQ
    if rmq_host := os.getenv("RABBITMQ_HOST"):
        config.rabbitmq.host = rmq_host
    if rmq_port := os.getenv("RABBITMQ_PORT"):
        config.rabbitmq.port = int(rmq_port)

    return config


def reset_test_env() -> None:
    """重置测试环境配置（用于测试隔离）"""
    global _test_env_config

    with _test_env_lock:
        _test_env_config = None
