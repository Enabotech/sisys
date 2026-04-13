"""RabbitMQ 配置模型。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RabbitMQConfig:
    """RabbitMQ 连接配置。

    用于 RabbitMQ 可靠事件传输通道（异步路径）。
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

        环境变量:
            RABBITMQ_HOST: RabbitMQ 主机地址 (默认: localhost)
            RABBITMQ_PORT: RabbitMQ 端口 (默认: 5672)
            RABBITMQ_VHOST: 虚拟主机 (默认: /)
            RABBITMQ_USERNAME: 用户名 (默认: guest)
            RABBITMQ_PASSWORD: 密码 (默认: guest)
            RABBITMQ_EXCHANGE: 交换机名称 (默认: sisys.events.reliable)
            RABBITMQ_PREFETCH: 预取数量 (默认: 10)
            RABBITMQ_HEARTBEAT: 心跳间隔秒数 (默认: 60)
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
