"""SISYS 基础设施层 RabbitMQ 配置模块。

提供 RabbitMQ 连接配置，用于可靠事件传输通道。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RabbitMQConfig:
    """RabbitMQ 连接配置。

    用于 RabbitMQ 可靠事件传输通道（异步路径）。

    Attributes:
        host: RabbitMQ 主机地址
        port: RabbitMQ 端口
        virtual_host: 虚拟主机
        username: 用户名
        password: 密码
        exchange_name: 交换机名称
        exchange_type: 交换机类型
        prefetch_count: 预取数量
        heartbeat: 心跳间隔（秒）
    """

    host: str = "localhost"
    port: int = 5672
    virtual_host: str = "/"
    username: str = "guest"
    password: str = "guest"
    exchange_name: str = "sisys.events.reliable"
    exchange_type: str = "topic"
    prefetch_count: int = 10
    heartbeat: int = 60

    @classmethod
    def from_env(cls) -> RabbitMQConfig:
        """从环境变量加载配置。

        Args:
            无（从 os.environ 读取）

        Returns:
            RabbitMQConfig 实例
        """
        return cls(
            host=os.getenv("RABBITMQ_HOST", "localhost"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
            username=os.getenv("RABBITMQ_USERNAME", "guest"),
            password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            exchange_name=os.getenv("RABBITMQ_EXCHANGE", "sisys.events.reliable"),
            prefetch_count=int(os.getenv("RABBITMQ_PREFETCH", "10")),
            heartbeat=int(os.getenv("RABBITMQ_HEARTBEAT", "60")),
        )
