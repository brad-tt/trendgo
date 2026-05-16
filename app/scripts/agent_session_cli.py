#!/usr/bin/env python3
"""Thin CLI wrapper for the Agent session endpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Agent session against the local TopTrader API.")
    parser.add_argument("--note", required=True, help="Natural-language trading note.")
    parser.add_argument("--date", default="", help="Trade date in YYYY-MM-DD format.")
    parser.add_argument("--market", default="HK", help="Market code: HK or US.")
    parser.add_argument("--auto-commit", action="store_true", help="Allow session to commit when intake is writable.")
    parser.add_argument("--state", default="normal", help="Current state hint.")
    parser.add_argument("--focus", default="", help="Optional focus hint.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = TestClient(api_server.app)
    payload = {
        "tradeDate": args.date or None,
        "market": args.market,
        "rawNote": args.note,
        "autoCommit": args.auto_commit,
        "currentState": args.state,
        "focus": args.focus,
    }
    payload = {key: value for key, value in payload.items() if value not in {"", None}}
    response = client.post("/api/agent/session", json=payload)
    if response.status_code >= 400:
        raise SystemExit(f"Agent session failed with HTTP {response.status_code}: {response.text}")

    body = response.json()
    print(f"intent: {body.get('intent')}")
    print(f"intent_confidence: {body.get('intentConfidence')}")
    print(f"next_action: {body.get('nextAction')}")
    print(f"auto_committed: {body.get('autoCommitted')}")

    workflow = body.get("workflow", {})
    result = workflow.get("result", {})
    follow_ups = result.get("followUpQuestions") or []
    if follow_ups:
        print("follow_up_questions:")
        for item in follow_ups:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
