#!/usr/bin/env python3
"""Smoke test for the Agent workflow intake endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402


def main() -> int:
    client = TestClient(api_server.app)

    open_response = client.post(
        "/api/agent/workflow/intake",
        json={
            "tradeDate": "2026-05-12",
            "market": "HK",
            "rawNote": "恒指突然拉起来，我想追一笔做多，但止损还没想清楚。",
            "commit": False,
        },
    )
    if open_response.status_code >= 400:
        raise SystemExit(f"workflow open intent failed with HTTP {open_response.status_code}: {open_response.text}")
    open_body = open_response.json()
    if open_body.get("intent") != "open_trade":
        raise SystemExit("workflow did not classify open_trade correctly")
    if open_body.get("suggestedEndpoint") != "/api/agent/intake/open":
        raise SystemExit("workflow suggestedEndpoint mismatch for open_trade")
    if not isinstance(open_body.get("intentConfidence"), (int, float)):
        raise SystemExit("workflow intentConfidence missing for open_trade")
    if not open_body.get("nextAction"):
        raise SystemExit("workflow nextAction missing for open_trade")

    review_response = client.post(
        "/api/agent/workflow/intake",
        json={
            "tradeDate": "2026-05-12",
            "market": "HK",
            "rawNote": "复盘：执行问题很大，情绪问题也明显，明天只改一件事。",
            "commit": False,
        },
    )
    if review_response.status_code >= 400:
        raise SystemExit(f"workflow review intent failed with HTTP {review_response.status_code}: {review_response.text}")
    review_body = review_response.json()
    if review_body.get("intent") != "review":
        raise SystemExit("workflow did not classify review correctly")
    if review_body.get("suggestedEndpoint") != "/api/agent/intake/review":
        raise SystemExit("workflow suggestedEndpoint mismatch for review")
    if not isinstance(review_body.get("intentConfidence"), (int, float)):
        raise SystemExit("workflow intentConfidence missing for review")
    if not review_body.get("nextAction"):
        raise SystemExit("workflow nextAction missing for review")

    print("\nAgent workflow intake API replay passed.")
    print(f"- intents: {open_body.get('intent')}, {review_body.get('intent')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
