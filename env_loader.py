"""
Load .env from the project root so any script (app.py, scripts/*.py) gets env vars.
Call load_project_env(__file__) at the start of each entry point.
"""

import os
from pathlib import Path

def load_project_env(caller_file=None):
    """Load .env from project root (directory containing .env). Tries caller's path then cwd."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        import sys
        print("Warning: python-dotenv not installed. .env will not be loaded. Run: pip install -r requirements.txt", file=sys.stderr)
        return

    loaded = False

    # 1. Walk up from the script that called us until we find .env
    if caller_file:
        root = Path(caller_file).resolve().parent
        for _ in range(5):
            env_path = root / ".env"
            if env_path.is_file():
                load_dotenv(env_path)
                loaded = True
                break
            parent = root.parent
            if parent == root:
                break
            root = parent

    # 2. Fallback: current working directory
    if not loaded:
        cwd_env = Path.cwd() / ".env"
        if cwd_env.is_file():
            load_dotenv(cwd_env)
