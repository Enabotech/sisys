"""Shared pytest configuration."""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ===========================================================================
# 环境初始化层（必须在其他模块 import 之前执行）
# ===========================================================================
# override=False: 不覆盖已存在的环境变量（如 CI 中设置的 SISYS_TEST_ENV）
# .env 作为基础配置，已存在的环境变量保持不变
load_dotenv(ROOT / ".env", override=False)
