"""Shared pytest configuration."""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 加载 .env 到环境变量（override=False 不覆盖已存在的变量如 SISYS_TEST_ENV）
load_dotenv(ROOT / ".env", override=False)
