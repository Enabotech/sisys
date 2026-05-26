"""爬虫服务全局配置模块

使用 dataclass + from_env() 模式，不依赖 Pydantic

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CrawlerSettings:
    """爬虫服务全局配置"""

    # ── 服务配置 ──
    host: str = ""  # 空字符串表示监听所有接口，等同于 0.0.0.0
    port: int = 8900

    # ── 爬取默认参数 ──
    max_depth: int = 3
    max_concurrent_requests: int = 8
    download_delay: float = 1.0
    download_timeout: int = 30
    max_files_per_task: int = 1000
    max_file_size_mb: int = 2048
    respect_robots_txt: bool = True
    retry_times: int = 3
    retry_http_codes: tuple[int, ...] = (500, 502, 503, 504, 408, 429)

    # ── 文件格式白名单 ──
    allowed_extensions: tuple[str, ...] = (
        "pdf",
        "txt",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "xls",
        "xlsx",
        "csv",
        "jpeg",
        "jpg",
        "png",
        "gif",
        "md",
        "markdown",
        "zip",
        "tar",
        "gz",
        "bz2",
    )

    # ── 命名配置 ──
    max_filename_length: int = 200
    filename_conflict_strategy: str = "append_hash"

    # ── 存储配置 ──
    storage_backend: str = "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket_prefix: str = "sisys"
    minio_secure: bool = False
    local_output_dir: str = "./crawl_output"

    # ── RabbitMQ 配置 ──
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_exchange: str = "sisys.events"

    @classmethod
    def from_env(cls) -> CrawlerSettings:
        """从环境变量加载配置（前缀 CRAWLER_）

        Returns:
            CrawlerSettings 实例
        """
        return cls(
            host=os.getenv("CRAWLER_HOST", ""),
            port=int(os.getenv("CRAWLER_PORT", "8900")),
            max_depth=int(os.getenv("CRAWLER_MAX_DEPTH", "3")),
            max_concurrent_requests=int(os.getenv("CRAWLER_MAX_CONCURRENT_REQUESTS", "8")),
            download_delay=float(os.getenv("CRAWLER_DOWNLOAD_DELAY", "1.0")),
            download_timeout=int(os.getenv("CRAWLER_DOWNLOAD_TIMEOUT", "30")),
            max_files_per_task=int(os.getenv("CRAWLER_MAX_FILES_PER_TASK", "1000")),
            max_file_size_mb=int(os.getenv("CRAWLER_MAX_FILE_SIZE_MB", "2048")),
            respect_robots_txt=os.getenv("CRAWLER_RESPECT_ROBOTS_TXT", "true").lower() == "true",
            retry_times=int(os.getenv("CRAWLER_RETRY_TIMES", "3")),
            storage_backend=os.getenv("CRAWLER_STORAGE_BACKEND", "minio"),
            minio_endpoint=os.getenv("CRAWLER_MINIO_ENDPOINT", "localhost:9000"),
            minio_access_key=os.getenv("CRAWLER_MINIO_ACCESS_KEY", ""),
            minio_secret_key=os.getenv("CRAWLER_MINIO_SECRET_KEY", ""),
            minio_bucket_prefix=os.getenv("CRAWLER_MINIO_BUCKET_PREFIX", "sisys"),
            minio_secure=os.getenv("CRAWLER_MINIO_SECURE", "false").lower() == "true",
            local_output_dir=os.getenv("CRAWLER_LOCAL_OUTPUT_DIR", "./crawl_output"),
            max_filename_length=int(os.getenv("CRAWLER_MAX_FILENAME_LENGTH", "200")),
            filename_conflict_strategy=os.getenv("CRAWLER_FILENAME_CONFLICT_STRATEGY", "append_hash"),
            rabbitmq_host=os.getenv("CRAWLER_RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("CRAWLER_RABBITMQ_PORT", "5672")),
            rabbitmq_exchange=os.getenv("CRAWLER_RABBITMQ_EXCHANGE", "sisys.events"),
        )
