#!/usr/bin/env python3
"""One-click local launcher for TrendGo."""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
import os
from pathlib import Path

import uvicorn

import local_web

ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT / "frontend" / "dist"
DEFAULT_PORT = int(os.environ.get("TOPTRADER_PORT", "8526"))


def open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}/premarket")


def main() -> None:
    print("TrendGo: 正在启动本地工作台...")

    if not FRONTEND_DIST.exists():
        print("TrendGo: 未找到前端构建产物。")
        print("TrendGo: 请先进入 frontend 目录执行 'npm run build'。")
        sys.exit(1)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "api_server:app",
        host=local_web.DEFAULT_HOST,
        port=DEFAULT_PORT,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
