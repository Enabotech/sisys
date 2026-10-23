"""安全测试套件专属配置（Story 5.5 — Agent 三重硬隔离穿透探针）。

- security_redis fixture: 场景级 Redis 客户端 + ping 门控 skip
  （对齐 tests/integration/conftest.py real_redis 形态的精简版——探针需真实
  Redis 6380 隔离键空间；function scope 场景独立防状态污染）
- pytestmark 纪律: 套件测试文件自带 [security, redis, integration] 三 marker
  （语义上属集成族——CI 挂 integration job 一致）

Author:
    agimtech <enabotech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import redis.asyncio as aioredis

from tests.environments import get_test_env


@pytest.fixture
async def security_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """提供安全套件专用真实 Redis 连接（场景级 + ping 门控动态 skip）。

    使用 get_test_env() 标准化测试环境配置（SISYS_USE_TEST_PORTS=1 下端口
    6380 测试专用实例）；function scope 确保每探针用例独立，避免状态污染。
    """
    config = get_test_env()

    client = aioredis.Redis(
        host=config.redis.host,
        port=config.redis.port,
        password=config.redis.password,
        decode_responses=True,
    )

    # 连通性门控（ping 失败动态 skip——禁写死 @pytest.mark.skip）
    try:
        await client.ping()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Redis not available: {exc}")

    yield client

    await client.close()
