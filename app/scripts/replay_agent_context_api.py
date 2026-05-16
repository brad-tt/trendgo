#!/usr/bin/env python3
"""Smoke test for the Agent context endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402


def main() -> int:
    client = TestClient(api_server.app)
    response = client.get("/api/agent/context")
    if response.status_code >= 400:
        raise SystemExit(f"Agent context failed with HTTP {response.status_code}: {response.text}")
    body = response.json()

    today = body.get("today", {})
    recent_patterns = body.get("recentPatterns", {})
    stage = body.get("stage", {})

    for key in ["date", "market", "sessionStatus", "tradingMode", "planSummary", "tradesDone", "violationsToday"]:
        if key not in today:
            raise SystemExit(f"today.{key} missing from agent context")
    for key in ["topDistortions", "highRiskContexts", "weeklyFocus"]:
        if key not in recent_patterns:
            raise SystemExit(f"recentPatterns.{key} missing from agent context")
    for key in ["currentStage", "stageLabel", "progress", "stageDescription"]:
        if key not in stage:
            raise SystemExit(f"stage.{key} missing from agent context")

    print("\nAgent context API replay passed.")
    print(f"- market: {today.get('market')}")
    print(f"- date: {today.get('date')}")
    print(f"- stage: {stage.get('currentStage')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
