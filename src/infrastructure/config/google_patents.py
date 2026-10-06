"""基础设施层 google-patents（BigQuery 公共专利数据集）配置（Story 4.1f Task 9 / D-09）

Google Patents Public Datasets（BigQuery `patents-public-data.patents.publications`，
IFI CLAIMS 维护——全球书目含 CN 99.96%，SSRN 2025/2026 验证）：
- 认证：GCP 服务账号 JSON（RS256 JWT → OAuth2 access_token，scope=bigquery.readonly）
  ——BigQuery 不支持 API key；程序化访问需绑定 Billing 的 GCP 项目（免费层内 $0）
- 免费配额：1 TiB/月查询字节（totalBytesProcessed 精确计费口径）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.domain.exceptions import ConfigurationError

_DEFAULT_API_URL = "https://bigquery.googleapis.com"

# timeout 下限（秒）——服务端 timeoutMs 从 config.timeout 派生（减提前量），
# timeout 过小会破坏「timeoutMs 恒小于 client timeout」派生不变量（httpx 先超时
# 触发非幂等重试三重计费），构造期 fail-fast 拦截
_MIN_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class GooglePatentsConfig:
    """google-patents BigQuery 配置（凭据双门 + 5 变量 + 双门合取条件注册）

    Attributes:
        credentials_path: GCP 服务账号 JSON 路径（env: GOOGLE_APPLICATION_CREDENTIALS——
            GCP 标准变量；repr 脱敏 JSON 内容不落 repr，路径本身非密钥）
        project_id: GCP 项目 ID（env: GOOGLE_PATENTS_PROJECT_ID——查询计费归属项目）
        api_url: BigQuery REST 基础地址（env: GOOGLE_PATENTS_API_URL）
        timeout: 请求超时秒数（env: GOOGLE_PATENTS_TIMEOUT——下限 3.0s，保 timeoutMs
            派生不变量）
        ttl_seconds: 缓存 TTL（env: GOOGLE_PATENTS_TTL_SECONDS——数据集月/周频更新，
            7 天保守缓存）

    Note:
        OAuth2 令牌端点（token_uri）取自服务账号 JSON 内标准字段——GCP 语义上
        属凭据文件而非环境配置（Q2-F8：原 token_url 环境旋钮从未被适配器消费，
        已删除防误导排障）。
    """

    credentials_path: str = ""
    project_id: str = ""
    api_url: str = _DEFAULT_API_URL
    timeout: float = 30.0
    ttl_seconds: int = 604800

    def __post_init__(self) -> None:
        """构造期校验（101 fail-fast）：双门合取 + timeout 下限。

        timeout 下限校验置于构造层（Q3/R3Q-4——from_env 与直构造两路径统一守护；
        过小 timeout 破坏「timeoutMs 恒小于 client timeout」派生不变量，httpx 先
        超时会触发非幂等 jobs.query 重试三重计费）。
        """
        if not self.credentials_path or not self.project_id:
            raise ConfigurationError(
                message=(
                    "google-patents 缺少 GCP 凭据配置（请设置环境变量 GOOGLE_APPLICATION_CREDENTIALS"
                    "（服务账号 JSON 路径）与 GOOGLE_PATENTS_PROJECT_ID（GCP 项目 ID）——"
                    "BigQuery 不支持 API key，程序化访问需绑定 Billing 的项目）"
                ),
                context={"source_name": "google-patents", "field": "credentials_path"},
            )
        if self.timeout < _MIN_TIMEOUT_SECONDS:
            raise ConfigurationError(
                message=(
                    f"google-patents timeout 不得低于 {_MIN_TIMEOUT_SECONDS}s，当前值: {self.timeout}"
                    "（服务端 timeoutMs 从 timeout 派生——过小会破坏两层超时派生不变量）"
                ),
                context={"source_name": "google-patents", "field": "timeout"},
            )

    @classmethod
    def from_env(cls) -> GooglePatentsConfig:
        """从环境变量加载配置（GOOGLE_APPLICATION_CREDENTIALS 等 5 变量）。

        Raises:
            ConfigurationError: 双门任一缺失 / 凭据文件不存在 / 数值解析失败 /
                timeout 低于下限（3.0s——__post_init__ 构造期统一守护）
        """
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        project_id = os.getenv("GOOGLE_PATENTS_PROJECT_ID", "")
        timeout_raw = os.getenv("GOOGLE_PATENTS_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("GOOGLE_PATENTS_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"GOOGLE_PATENTS_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"GOOGLE_PATENTS_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"GOOGLE_PATENTS_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            credentials_path=credentials_path,
            project_id=project_id,
            api_url=os.getenv("GOOGLE_PATENTS_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


def credentials_file_exists(credentials_path: str) -> bool:
    """双门条件注册辅助：凭据路径非空且文件存在（组合根注册判定用）。"""
    return bool(credentials_path) and Path(credentials_path).is_file()


__all__ = ["GooglePatentsConfig", "credentials_file_exists"]
