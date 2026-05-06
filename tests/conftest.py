"""Shared pytest configuration."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ===========================================================================
# 环境初始化层（必须在其他模块 import 之前执行）
# ===========================================================================
# CI 环境不加载 .env 文件，使用 get_test_env() 获取配置
# .env 文件包含 localhost 地址，会覆盖 CI 环境的正确配置
if os.getenv("SISYS_TEST_ENV") != "ci":
    load_dotenv(ROOT / ".env", override=True)
