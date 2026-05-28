#!/usr/bin/env python3
"""使用 CloakBrowser 引擎执行 AWS Builder ID 注册（本地或 VPS）。"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault("BROWSER_ENGINE", "cloak")
sys.path.insert(0, str(ROOT / "src"))

from runners.main import run  # noqa: E402

if __name__ == "__main__":
    run()
