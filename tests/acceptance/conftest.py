"""验收测试环境配置

在验收测试 session 开始时，将 get_test_env() 计算出的环境配置
同步到 os.environ，确保 composition_root 的 Config.from_env()
能读到正确的服务地址（CI/K8s/本地测试端口）。

仅影响验收测试，不污染单元测试的默认环境。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

import pytest

from tests.environments import _sync_config_to_environ, get_test_env


@pytest.fixture(scope="session", autouse=True)
def _sync_acceptance_env() -> None:
    """验收测试 session 启动时同步环境配置到 os.environ"""
    config = get_test_env()
    _sync_config_to_environ(config)
