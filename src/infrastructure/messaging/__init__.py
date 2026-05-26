"""基础设施层消息总线包

提供领域事件的多通道传输能力，包括 Redis Pub/Sub 实时通道、
RabbitMQ 可靠通道（Outbox 模式）以及内存事件总线实现
"""
