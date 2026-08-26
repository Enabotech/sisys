"""基础设施层重排序配置模块

RerankerConfig 提供重排序 API 的配置参数，通过 from_env() 从环境变量加载。
必需（非可选）：重排序功能依赖此配置。
"""

from __future__ import annotations

import dataclasses
import os


@dataclasses.dataclass(frozen=True)
class RerankerConfig:
    """重排序 API 配置

    Attributes:
        model: 重排序模型名称（如 BAAI/bge-reranker-v2-m3）
        top_k: 默认 Top-K 数量
        timeout: API 超时（秒）
        api_key: API 密钥
        base_url: API 端点
    """

    model: str = "BAAI/bge-reranker-v2-m3"
    top_k: int = 20
    timeout: int = 10
    api_key: str | None = None
    base_url: str | None = None

    def __repr__(self) -> str:
        """脱敏表示：不暴露 api_key 明文

        默认 dataclass __repr__ 会输出 api_key 明文，可能导致凭据泄露到日志。
        """
        api_key_repr = "***" if self.api_key else "None"
        return (
            f"RerankerConfig(model={self.model!r}, top_k={self.top_k!r}, "
            f"timeout={self.timeout!r}, api_key={api_key_repr}, base_url={self.base_url!r})"
        )

    @classmethod
    def from_env(cls) -> RerankerConfig:
        """从环境变量加载配置

        Returns:
            RerankerConfig 实例
        """
        return cls(
            model=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            top_k=int(os.getenv("RERANKER_TOP_K", "20")),
            timeout=int(os.getenv("RERANKER_TIMEOUT", "10")),
            api_key=os.getenv("RERANKER_API_KEY"),
            base_url=os.getenv("RERANKER_BASE_URL"),
        )


__all__ = ["RerankerConfig"]
