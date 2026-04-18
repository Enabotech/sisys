"""Shared pytest configuration."""

import sys
from pathlib import Path

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
