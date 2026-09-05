"""M4 · 启动后端（FastAPI + SSE）。

python scripts/serve.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.app import main  # noqa: E402

if __name__ == "__main__":
    main()
