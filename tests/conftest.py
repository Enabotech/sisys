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
load_dotenv(ROOT / ".env", override=True)
