"""应用层自动触发处理器模块

自动触发机制的事件监听适配器，监听事件总线上的领域事件
并传递给 AutoTriggerService 进行处理

参考: Story 1.14a SDD规范定义
参考: or.md 系统公理一 (trigger→route→execute)

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections.abc import Callable

from src.domain.events.base import DomainEvent
from src.domain.events.listener import EventListener
from src.domain.services.auto_trigger_service import AutoTriggerService

logger = logging.getLogger(__name__)


class AutoTriggerHandler:
    """事件监听器，桥接事件总线与 AutoTriggerService

    注册领域事件处理器，将处理委托给 AutoTriggerService 领域服务

    这是接口适配层——将事件总线接口适配为 AutoTriggerService 接口，
    同时保持六边形架构合规（领域层保持隔离）

    使用后台线程及其独立事件循环，安全地将同步事件处理器桥接到异步 AutoTriggerService

    Attributes:
        MAX_CONCURRENT_TASKS: 最大并发任务数（默认 100）
        TASK_TIMEOUT: 单任务超时秒数（默认 300）
    """

    # Concurrency control parameters
    MAX_CONCURRENT_TASKS: int = 100
    """最大并发事件处理任务数"""

    TASK_TIMEOUT: float = 300.0
    """单个事件处理任务的超时秒数"""

    def __init__(
        self,
        auto_trigger_service: AutoTriggerService,
        event_listener: EventListener,
    ) -> None:
        """初始化自动触发监听器

        Args:
            auto_trigger_service: 处理触发的领域服务
            event_listener: 用于注册处理器的事件监听器
        """
        self._auto_trigger_service = auto_trigger_service
        self._event_listener = event_listener
        self._registered_event_types = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CheckpointRecovered",
            "CorrectionClassified",
            "CorrectionApproved",
            "IsolationLevelSwitched",
            "HeartbeatTriggered",
            "StrategicDeviationWarning",
            "AuditEvent",
        ]
        # Background thread for async processing
        self._event_queue: queue.Queue[tuple[str, DomainEvent]] = queue.Queue(maxsize=1000)
        self._worker_thread: threading.Thread | None = None
        self._running = False

    def register_handlers(self) -> None:
        """注册所有支持的领域事件类型的处理器

        每个处理器根据事件类型委托给对应的 AutoTriggerService 方法
        """
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        for event_type in self._registered_event_types:
            handler = self._create_handler(event_type)
            self._event_listener.on_event(event_type, handler)
            logger.debug("Registered handler for event type: %s", event_type)

    def _create_handler(self, event_type: str) -> Callable[[DomainEvent], None]:
        """为指定事件类型创建处理函数

        Args:
            event_type: 要处理的事件类型

        Returns:
            处理指定类型事件的处理函数
        """

        def handle_event(event: DomainEvent) -> None:
            """处理领域事件并触发处理流程

            Args:
                event: 待处理的领域事件
            """
            try:
                # Queue the event for async processing in background thread
                self._event_queue.put_nowait((event_type, event))
            except queue.Full:
                logger.warning("Event queue full, dropping event: %s", event_type)
            except Exception as e:
                logger.error("Failed to queue event %s: %s", event_type, e)

        return handle_event

    def _worker_loop(self) -> None:
        """后台工作线程循环，并发处理事件

        使用 create_task() + gather() 实现高吞吐事件处理
        通过 MAX_CONCURRENT_TASKS 控制并发，防止资源耗尽
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pending_tasks: set[asyncio.Task] = set()

        try:
            while self._running:
                try:
                    # 从队列获取事件（非阻塞，timeout=0.1）
                    event_type, event = self._event_queue.get(timeout=0.1)

                    # 等待如果达到最大并发
                    if len(pending_tasks) >= self.MAX_CONCURRENT_TASKS:
                        done, pending_tasks = loop.run_until_complete(
                            asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
                        )
                        for task in done:
                            exc = task.exception()
                            if exc:
                                logger.error("Task failed: %s", exc)

                    # 创建带超时的新任务
                    async def _process_with_timeout():
                        return await asyncio.wait_for(
                            self._process_event(event_type, event),
                            timeout=self.TASK_TIMEOUT,
                        )

                    task = loop.create_task(_process_with_timeout())
                    pending_tasks.add(task)

                except queue.Empty:
                    # 队列空时等待已提交的任务完成
                    if pending_tasks:
                        done, pending_tasks = loop.run_until_complete(
                            asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
                        )
                        for task in done:
                            exc = task.exception()
                            if exc:
                                logger.error("Task failed: %s", exc)
                except Exception as e:
                    logger.error("Error in worker loop: %s", e)
        finally:
            # 取消所有待完成的任务
            for task in pending_tasks:
                task.cancel()
            # 等待所有任务完成（最多 5 秒）
            if pending_tasks:
                loop.run_until_complete(asyncio.wait(pending_tasks, timeout=5.0))
            loop.close()

    def stop(self) -> None:
        """停止后台工作线程"""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

    async def _process_event(self, event_type: str, event: DomainEvent) -> None:
        """异步处理领域事件

        Args:
            event_type: 正在处理的事件类型
            event: 待处理的领域事件
        """
        try:
            if event_type == "HeartbeatTriggered":
                # HeartbeatTriggered requires special handling
                from src.domain.events.heartbeat_events import HeartbeatTriggered

                heartbeat_event = HeartbeatTriggered.from_dict(event.to_dict())
                triggered = await self._auto_trigger_service.on_heartbeat_event(heartbeat_event)
            else:
                # Standard domain event processing
                triggered = await self._auto_trigger_service.on_domain_event(event)

            if triggered is not None:
                logger.info("Trigger processed: type=%s, session_id=%s", triggered.trigger_type, triggered.session_id)
            else:
                logger.warning("AutoTriggerService returned None for event: %s", event_type)

        except Exception as e:
            logger.error("Failed to process event %s: %s", event_type, e)

    @property
    def registered_event_types(self) -> list[str]:
        """返回此监听器处理的事件类型列表

        Returns:
            已注册的事件类型名称列表
        """
        return list(self._registered_event_types)
