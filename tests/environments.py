# =============================================================================
# SISYS 测试环境配置解析
# =============================================================================
# 用途：根据不同测试环境（Local/CI/K8s）自动适配服务连接参数
# Story: 90-1 (sisys-testing-refactor) - Phase 2
# =============================================================================

from __future__ import annotations

import copy
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dotenv import dotenv_values

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
class AppConfig:
    """应用配置"""

    jwt_secret_key: str = ""
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


@dataclass
class EmbeddingConfig:
    """Embedding API 配置"""

    api_url: str = "http://localhost:8001"
    api_timeout: float = 30.0


@dataclass
class RapidOCRConfig:
    """RapidOCR 本地推理配置"""

    model_dir: str = ""
    max_concurrency: int = 1


@dataclass
class LLMConfig:
    """LLM API 配置（对齐 LLMConfig.from_env() 读取的 LLM_* 变量）"""

    api_type: str = "openai"
    model: str = "qwen2.5:7b"
    endpoint: str | None = None
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    timeout: float = 600.0


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
    app: AppConfig = field(default_factory=AppConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    rapidocr: RapidOCRConfig = field(default_factory=RapidOCRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


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
    llm=LLMConfig(api_type="openai", model="qwen2.5:7b", endpoint="http://localhost:11434", timeout=600.0),
)

CI_CONFIG = TestEnvConfig(
    env=TestEnvironment.CI,
    redis=RedisConfig(host="host.docker.internal", port=6379),
    postgres=PostgreSQLConfig(host="host.docker.internal", port=5432),
    qdrant=QdrantConfig(host="host.docker.internal", port=6333, grpc_port=6334),
    minio=MinIOConfig(endpoint="host.docker.internal:9000"),
    neo4j=Neo4jConfig(host="host.docker.internal", http_port=7474, bolt_port=7687),
    rabbitmq=RabbitMQConfig(host="host.docker.internal", port=5672, mgmt_port=15672),
    llm=LLMConfig(api_type="openai", model="qwen2.5:7b", endpoint="http://host.docker.internal:11434", timeout=600.0),
)

K8S_CONFIG = TestEnvConfig(
    env=TestEnvironment.K8S,
    redis=RedisConfig(host="sisys-redis", port=6379),
    postgres=PostgreSQLConfig(host="sisys-postgres", port=5432),
    qdrant=QdrantConfig(host="sisys-qdrant", port=6333, grpc_port=6334),
    minio=MinIOConfig(endpoint="sisys-minio:9000"),
    neo4j=Neo4jConfig(host="sisys-neo4j", http_port=7474, bolt_port=7687),
    rabbitmq=RabbitMQConfig(host="sisys-rabbitmq", port=5672, mgmt_port=15672),
    llm=LLMConfig(api_type="openai", model="qwen2.5:7b", endpoint="http://sisys-ollama:11434", timeout=600.0),
)

TEST_CONFIG = TestEnvConfig(
    env=TestEnvironment.LOCAL,
    redis=RedisConfig(host="localhost", port=6380),  # 测试专用端口
    postgres=PostgreSQLConfig(host="localhost", port=5433),
    qdrant=QdrantConfig(host="localhost", port=6335, grpc_port=6336),
    minio=MinIOConfig(endpoint="localhost:9010"),
    neo4j=Neo4jConfig(host="localhost", http_port=7475, bolt_port=7688),
    rabbitmq=RabbitMQConfig(host="localhost", port=5673, mgmt_port=15673),
    llm=LLMConfig(api_type="openai", model="qwen2.5:7b", endpoint="http://localhost:11434", timeout=600.0),
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


def _use_test_ports_active(config: TestEnvConfig | None = None) -> bool:
    """测试端口开关生效判定（单一真源——三调用位共享防判定式漂移）。

    判定式若在多处复制漂移（真值集/合取条件不一致），Layer 1 选择与
    Layer 3/sync 门控会层间分叉（选了 TEST_CONFIG 却不跳过端口覆盖）——
    统一收敛到本函数（R2-F05）。

    Args:
        config: 已选配置（None 时仅判开关——get_test_env Layer 1 选择位
            处于 LOCAL 分支内，env 已知为 LOCAL）
    """
    if config is not None and config.env != TestEnvironment.LOCAL:
        return False
    return os.getenv("SISYS_USE_TEST_PORTS", "").lower() in ("1", "true", "yes")


def get_test_env() -> TestEnvConfig:
    """获取测试环境配置（单例）

    三层配置覆盖链（从低到高优先级）：
    Layer 1: 环境检测 + 预设配置
        → resolve_env() 自动检测环境类型（CI/K8S/LOCAL）
        → 选择对应预设配置（CI_CONFIG/K8S_CONFIG/LOCAL_CONFIG/TEST_CONFIG）
        → SISYS_USE_TEST_PORTS=1 切换到独立测试端口
    Layer 2: .env 文件填充
        → 仅填充 Layer 1 输出中的空值/默认值，不覆盖已有值
    Layer 3: os.environ 显式设置
        → 绝对最高优先级，不可被任何机制覆盖（端口例外：SISYS_USE_TEST_PORTS
          生效时端口类覆盖跳过——防第三方库 import 副作用[如 conftest 模块级
          litellm import 触发 load_dotenv]注入 dev 端口击穿测试端口隔离）
        → _sync_config_to_environ() 使用 setdefault 确保生产代码也能读取
          （端口类在测试端口模式下强制覆写——防与 Config.from_env() 分叉）
    """
    global _test_env_config

    if _test_env_config is not None:
        return _test_env_config

    with _test_env_lock:
        if _test_env_config is not None:
            return _test_env_config

        # Layer 1: 环境检测 + 预设配置（合并为单一步骤）
        env = resolve_env()
        if env == TestEnvironment.CI:
            config = copy.deepcopy(CI_CONFIG)
        elif env == TestEnvironment.K8S:
            config = copy.deepcopy(K8S_CONFIG)
        elif env == TestEnvironment.LOCAL:
            # 端口切换内嵌在 LOCAL 分支中
            if _use_test_ports_active():
                config = copy.deepcopy(TEST_CONFIG)
            else:
                config = copy.deepcopy(LOCAL_CONFIG)
        else:
            config = copy.deepcopy(LOCAL_CONFIG)

        # Layer 2: .env 文件填充（仅填充空值/默认值）
        env_values = dotenv_values(ROOT / ".env")
        _apply_dotenv_if_empty(config, env_values)

        # Layer 3: os.environ 显式设置覆盖（最高优先级）
        config = _override_config_from_env(config)

        # 同步到 os.environ，确保生产代码的 Config.from_env() 也能读取
        _sync_config_to_environ(config)

        _test_env_config = config
        return _test_env_config


def _apply_dotenv_if_empty(config: TestEnvConfig, env_values) -> None:
    """用 .env 填充环境配置中的空值/默认值"""
    # Redis
    if config.redis.host in ("localhost", "") or not config.redis.host:
        if host := env_values.get("REDIS_HOST"):
            config.redis.host = host
    if config.redis.port in (6379, 0) or not config.redis.port:
        if port := env_values.get("REDIS_PORT"):
            config.redis.port = int(port)

    # PostgreSQL
    if config.postgres.host in ("localhost", "") or not config.postgres.host:
        if host := env_values.get("POSTGRES_HOST"):
            config.postgres.host = host
    if config.postgres.port in (5432, 0) or not config.postgres.port:
        if port := env_values.get("POSTGRES_PORT"):
            config.postgres.port = int(port)

    # Qdrant
    if config.qdrant.host in ("localhost", "") or not config.qdrant.host:
        if host := env_values.get("QDRANT_HOST"):
            config.qdrant.host = host
    if config.qdrant.port in (6333, 0) or not config.qdrant.port:
        if port := env_values.get("QDRANT_PORT"):
            config.qdrant.port = int(port)

    # MinIO - endpoint 是 "host:port" 格式
    if not config.minio.endpoint or config.minio.endpoint in ("localhost:9000", ""):
        if host := env_values.get("MINIO_HOST"):
            config.minio.endpoint = f"{host}:9000"

    # Neo4j
    if config.neo4j.host in ("localhost", "") or not config.neo4j.host:
        if host := env_values.get("NEO4J_HOST"):
            config.neo4j.host = host

    # RabbitMQ
    if config.rabbitmq.host in ("localhost", "") or not config.rabbitmq.host:
        if host := env_values.get("RABBITMQ_HOST"):
            config.rabbitmq.host = host

    # 应用配置
    if not config.app.jwt_secret_key:
        if key := env_values.get("JWT_SECRET_KEY"):
            config.app.jwt_secret_key = key
    if not config.app.secret_key:
        if key := env_values.get("SECRET_KEY"):
            config.app.secret_key = key
    if not config.app.algorithm or config.app.algorithm == "HS256":
        if alg := env_values.get("ALGORITHM"):
            config.app.algorithm = alg

    # Embedding API 配置
    if not config.embedding.api_url:
        if url := env_values.get("EMBEDDING_API_URL"):
            config.embedding.api_url = url

    # RapidOCR 配置
    if not config.rapidocr.model_dir:
        if model_dir := env_values.get("RAPIDOCR_MODEL_DIR"):
            config.rapidocr.model_dir = model_dir
    if max_concurrency := env_values.get("RAPIDOCR_MAX_CONCURRENCY"):
        config.rapidocr.max_concurrency = int(max_concurrency)

    # LLM API 配置
    if not config.llm.api_type or config.llm.api_type == "openai":
        if api_type := env_values.get("LLM_API_TYPE"):
            config.llm.api_type = api_type
    if not config.llm.model or config.llm.model == "qwen2.5:7b":
        if model := env_values.get("LLM_MODEL"):
            config.llm.model = model
    if not config.llm.endpoint:
        if endpoint := env_values.get("LLM_ENDPOINT"):
            config.llm.endpoint = endpoint
    if not config.llm.api_key:
        if api_key := env_values.get("LLM_API_KEY"):
            config.llm.api_key = api_key
    if config.llm.temperature == 0.7:
        if temp := env_values.get("LLM_TEMPERATURE"):
            try:
                config.llm.temperature = float(temp)
            except ValueError:
                pass
    if config.llm.max_tokens is None:
        if max_tokens := env_values.get("LLM_MAX_TOKENS"):
            try:
                config.llm.max_tokens = int(max_tokens)
            except ValueError:
                pass
    if config.llm.timeout == 600.0:
        if timeout := env_values.get("LLM_TIMEOUT"):
            try:
                config.llm.timeout = float(timeout)
            except ValueError:
                pass


def _override_config_from_env(base_config: TestEnvConfig) -> TestEnvConfig:
    """从环境变量覆盖配置（端口例外：测试端口开关生效时端口覆盖跳过）"""
    import copy

    config = copy.deepcopy(base_config)

    # CI/K8S 等远程环境中，os.environ 中的 localhost 可能来自第三方库
    # （如 litellm 导入时 dotenv.load_dotenv()）的副作用，而非用户显式设置。
    # 此类环境的预设 host 不是 localhost，故 localhost 一律视为注入污染，跳过不覆盖。
    _is_remote_env = config.env in (TestEnvironment.CI, TestEnvironment.K8S)

    # SISYS_USE_TEST_PORTS 生效（LOCAL 分支选中 TEST_CONFIG）时，端口类 env 覆盖
    # 跳过：测试端口开关是显式意图，权威高于 os.environ——第三方库 import 副作用
    # （conftest 模块级 litellm import 触发 load_dotenv 将 .env 的 dev 端口注入
    # os.environ）不得击穿测试端口隔离（测试静默读写 dev 6379/5432 实例）。
    _use_test_ports = _use_test_ports_active(config)

    # Redis
    if redis_host := os.getenv("REDIS_HOST"):
        if not (_is_remote_env and redis_host == "localhost"):
            config.redis.host = redis_host
    if (redis_port := os.getenv("REDIS_PORT")) and not _use_test_ports:
        config.redis.port = int(redis_port)

    # PostgreSQL
    if pg_host := os.getenv("POSTGRES_HOST"):
        if not (_is_remote_env and pg_host == "localhost"):
            config.postgres.host = pg_host
    if (pg_port := os.getenv("POSTGRES_PORT")) and not _use_test_ports:
        config.postgres.port = int(pg_port)

    # Qdrant
    if qdrant_host := os.getenv("QDRANT_HOST"):
        if not (_is_remote_env and qdrant_host == "localhost"):
            config.qdrant.host = qdrant_host
    if (qdrant_port := os.getenv("QDRANT_PORT")) and not _use_test_ports:
        config.qdrant.port = int(qdrant_port)
    if (qdrant_grpc_port := os.getenv("QDRANT_GRPC_PORT")) and not _use_test_ports:
        config.qdrant.grpc_port = int(qdrant_grpc_port)

    # MinIO（endpoint 是 host:port 派生值——测试端口模式下整体跳过，
    # 防 host 分支内联重建 endpoint 绕过端口守卫）
    if (minio_host := os.getenv("MINIO_HOST")) and not _use_test_ports:
        if not (_is_remote_env and minio_host == "localhost"):
            minio_port = os.getenv("MINIO_API_PORT", "9000")
            config.minio.endpoint = f"{minio_host}:{minio_port}"
    if minio_access_key := os.getenv("MINIO_ACCESS_KEY"):
        config.minio.access_key = minio_access_key
    if minio_secret_key := os.getenv("MINIO_SECRET_KEY"):
        config.minio.secret_key = minio_secret_key
    if minio_bucket := os.getenv("MINIO_BUCKET"):
        config.minio.bucket = minio_bucket

    # Neo4j
    if neo4j_host := os.getenv("NEO4J_HOST"):
        if not (_is_remote_env and neo4j_host == "localhost"):
            config.neo4j.host = neo4j_host

    # RabbitMQ
    if rmq_host := os.getenv("RABBITMQ_HOST"):
        if not (_is_remote_env and rmq_host == "localhost"):
            config.rabbitmq.host = rmq_host
    if (rmq_port := os.getenv("RABBITMQ_PORT")) and not _use_test_ports:
        config.rabbitmq.port = int(rmq_port)
    if (rmq_mgmt_port := os.getenv("RABBITMQ_MGMT_PORT")) and not _use_test_ports:
        config.rabbitmq.mgmt_port = int(rmq_mgmt_port)
    if rmq_username := os.getenv("RABBITMQ_USERNAME"):
        config.rabbitmq.username = rmq_username
    if rmq_password := os.getenv("RABBITMQ_PASSWORD"):
        config.rabbitmq.password = rmq_password

    # 应用配置
    if jwt_key := os.getenv("JWT_SECRET_KEY"):
        config.app.jwt_secret_key = jwt_key
    if secret_key := os.getenv("SECRET_KEY"):
        config.app.secret_key = secret_key

    # Embedding API 配置
    if api_url := os.getenv("EMBEDDING_API_URL"):
        config.embedding.api_url = api_url

    # RapidOCR 配置
    if model_dir := os.getenv("RAPIDOCR_MODEL_DIR"):
        config.rapidocr.model_dir = model_dir
    if max_concurrency := os.getenv("RAPIDOCR_MAX_CONCURRENCY"):
        config.rapidocr.max_concurrency = int(max_concurrency)

    # LLM API 配置
    if api_type := os.getenv("LLM_API_TYPE"):
        config.llm.api_type = api_type
    if model := os.getenv("LLM_MODEL"):
        config.llm.model = model
    if endpoint := os.getenv("LLM_ENDPOINT"):
        config.llm.endpoint = endpoint
    if api_key := os.getenv("LLM_API_KEY"):
        config.llm.api_key = api_key
    if temp := os.getenv("LLM_TEMPERATURE"):
        try:
            config.llm.temperature = float(temp)
        except ValueError:
            pass
    if max_tokens := os.getenv("LLM_MAX_TOKENS"):
        try:
            config.llm.max_tokens = int(max_tokens)
        except ValueError:
            pass
    if timeout := os.getenv("LLM_TIMEOUT"):
        try:
            config.llm.timeout = float(timeout)
        except ValueError:
            pass

    return config


def _sync_config_to_environ(config: TestEnvConfig) -> None:
    """将最终测试环境配置同步到 os.environ

    确保生产代码的 Config.from_env()（读 os.getenv）也能拿到与测试环境一致的值。

    覆盖策略：
    - 对 host 类变量（如 REDIS_HOST/POSTGRES_HOST 等）：使用 setdefault。若 os.environ
      中已有非 localhost 的显式值则尊重之；若仅剩 localhost（第三方库如 litellm
      导入时 dotenv.load_dotenv() 注入的污染值），则强制覆盖为计算出的正确 host，
      保证生产代码 Config.from_env() 与 get_test_env() 解析一致。
    - 对端口类变量：SISYS_USE_TEST_PORTS 生效时强制覆写——第三方库 import 副作用
      注入的 dev 端口（如 REDIS_PORT=6379）已在 os.environ，setdefault 是 no-op，
      生产代码 Config.from_env() 会与测试端口解析分叉（split-brain）。
    - 其余变量：使用 setdefault，尊重用户显式设置（最高优先级）。

    Args:
        config: 计算完成的测试环境配置
    """
    # 远程环境（CI/K8S）中 localhost 是 litellm 等第三方库导入副作用注入的污染值，
    # 需强制覆盖为计算出的正确 host，避免生产代码 Config.from_env() 读到错误值
    _is_remote_env = config.env in (TestEnvironment.CI, TestEnvironment.K8S)

    # 测试端口模式下端口类变量强制覆写（理由见 docstring——与 _override_config_from_env
    # 的端口守卫配对，双向闭合测试端口隔离）
    _use_test_ports = _use_test_ports_active(config)

    def _set_port_env(key: str, value: str) -> None:
        """设置端口类环境变量（测试端口模式强制覆写，否则 setdefault 尊重显式值）"""
        if _use_test_ports:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)

    def _set_host_env(key: str, value: str) -> None:
        """设置 host 类环境变量

        远程环境下若当前值为 localhost（污染值），强制覆盖；否则 setdefault 尊重显式值。
        """
        if _is_remote_env and os.getenv(key) == "localhost":
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)

    # Redis
    _set_host_env("REDIS_HOST", config.redis.host)
    _set_port_env("REDIS_PORT", str(config.redis.port))
    if config.redis.password:
        os.environ.setdefault("REDIS_PASSWORD", config.redis.password)

    # PostgreSQL
    _set_host_env("POSTGRES_HOST", config.postgres.host)
    _set_port_env("POSTGRES_PORT", str(config.postgres.port))
    os.environ.setdefault("POSTGRES_USERNAME", config.postgres.username)
    os.environ.setdefault("POSTGRES_PASSWORD", config.postgres.password)
    os.environ.setdefault("POSTGRES_DATABASE", config.postgres.database)

    # Qdrant
    _set_host_env("QDRANT_HOST", config.qdrant.host)
    _set_port_env("QDRANT_PORT", str(config.qdrant.port))
    _set_port_env("QDRANT_GRPC_PORT", str(config.qdrant.grpc_port))

    # Neo4j
    _set_host_env("NEO4J_HOST", config.neo4j.host)
    _set_port_env("NEO4J_HTTP_PORT", str(config.neo4j.http_port))
    _set_port_env("NEO4J_BOLT_PORT", str(config.neo4j.bolt_port))

    # RabbitMQ
    _set_host_env("RABBITMQ_HOST", config.rabbitmq.host)
    _set_port_env("RABBITMQ_PORT", str(config.rabbitmq.port))
    _set_port_env("RABBITMQ_MGMT_PORT", str(config.rabbitmq.mgmt_port))
    os.environ.setdefault("RABBITMQ_USERNAME", config.rabbitmq.username)
    os.environ.setdefault("RABBITMQ_PASSWORD", config.rabbitmq.password)

    # MinIO - endpoint 是 "host:port" 格式，host 部分同样可能被污染。
    # 生产 MinIOConfig.from_env 读 MINIO_HOST+MINIO_API_PORT（非 endpoint）——
    # 测试端口模式下两键一并强覆写（endpoint 解析回填），防 MinIO 腿 split-brain
    # （R2-F02：.env 注入的 MINIO_API_PORT=9000 会使 from_env 得 9000 ≠ 测试 9010）
    if _use_test_ports:
        os.environ["MINIO_ENDPOINT"] = config.minio.endpoint
        _endpoint_parts = config.minio.endpoint.rsplit(":", 1)
        if len(_endpoint_parts) == 2:  # 守卫：endpoint 恒含端口（四预设均含；异常形态跳过覆写不炸）
            os.environ["MINIO_HOST"] = _endpoint_parts[0]
            os.environ["MINIO_API_PORT"] = _endpoint_parts[1]
    elif _is_remote_env and (os.getenv("MINIO_HOST") == "localhost" or os.getenv("MINIO_ENDPOINT") == "localhost:9000"):
        os.environ["MINIO_ENDPOINT"] = config.minio.endpoint
    else:
        os.environ.setdefault("MINIO_ENDPOINT", config.minio.endpoint)
    os.environ.setdefault("MINIO_ACCESS_KEY", config.minio.access_key)
    os.environ.setdefault("MINIO_SECRET_KEY", config.minio.secret_key)
    os.environ.setdefault("MINIO_BUCKET", config.minio.bucket)

    # 应用配置
    if config.app.jwt_secret_key:
        os.environ.setdefault("JWT_SECRET_KEY", config.app.jwt_secret_key)
    if config.app.secret_key:
        os.environ.setdefault("SECRET_KEY", config.app.secret_key)

    # Embedding API 配置
    os.environ.setdefault("EMBEDDING_API_URL", config.embedding.api_url)

    # RapidOCR 配置
    os.environ.setdefault("RAPIDOCR_MODEL_DIR", config.rapidocr.model_dir)
    os.environ.setdefault("RAPIDOCR_MAX_CONCURRENCY", str(config.rapidocr.max_concurrency))

    # LLM API 配置
    os.environ.setdefault("LLM_API_TYPE", config.llm.api_type)
    os.environ.setdefault("LLM_MODEL", config.llm.model)
    if config.llm.endpoint:
        os.environ.setdefault("LLM_ENDPOINT", config.llm.endpoint)
    if config.llm.api_key:
        os.environ.setdefault("LLM_API_KEY", config.llm.api_key)
    os.environ.setdefault("LLM_TEMPERATURE", str(config.llm.temperature))
    if config.llm.max_tokens is not None:
        os.environ.setdefault("LLM_MAX_TOKENS", str(config.llm.max_tokens))
    os.environ.setdefault("LLM_TIMEOUT", str(config.llm.timeout))


def reset_test_env() -> None:
    """重置测试环境配置（用于测试隔离）"""
    global _test_env_config

    with _test_env_lock:
        _test_env_config = None
