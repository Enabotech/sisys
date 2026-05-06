"""Shared pytest configuration."""

import sys
from pathlib import Path

from tests.environments import get_test_env

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 触发 .env 加载（确保所有 os.getenv() 都能读到配置）
get_test_env()
