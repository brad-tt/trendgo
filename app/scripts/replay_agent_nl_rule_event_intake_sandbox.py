#!/usr/bin/env python3
"""Sandbox replay for natural-language rule-event intake."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import api_server  # noqa: E402
from database import dal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scripts.agent_sandbox_utils import SandboxConfig, assert_ok, create_sandbox_day, restored_sandbox  # noqa: E402

CONFIG = SandboxConfig()


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent natural-language rule-event intake sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- parse-only and commit path covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    client = TestClient(api_server.app)
    create_sandbox_day(client, CONFIG)

    incomplete = client.post(
        "/api/agent/intake/rule-event",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "刚刚情绪有点上头，先暂停一下。",
            "commit": False,
        },
    )
    assert_ok(incomplete.status_code, incomplete.text, "parse incomplete rule-event intake")
    incomplete_body = incomplete.json()
    if incomplete_body.get("committed") is not False:
        raise AssertionError("incomplete rule-event intake should not commit")
    if not incomplete_body.get("followUpQuestions"):
        raise AssertionError("incomplete rule-event intake should return follow-up questions")

    complete = client.post(
        "/api/agent/intake/rule-event",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "11:16 触发原因：刚亏损后想马上赚回来。处理动作：暂停交易，先复述交易理由；不清楚就不做。 stop",
            "commit": True,
            "agentNote": "sandbox nl rule-event intake commit",
        },
    )
    assert_ok(complete.status_code, complete.text, "commit complete rule-event intake")
    body = complete.json()
    if body.get("committed") is not True:
        raise AssertionError("complete rule-event intake should commit")
    day = body.get("day") or {}
    events = day.get("events") or []
    if len(events) != 1:
        raise AssertionError(f"expected 1 committed rule event, got {len(events)}")
    event = events[0]
    if event.get("eventType") != "emotion_trigger":
        raise AssertionError("rule-event intake eventType mismatch")
    if event.get("severity") != "stop":
        raise AssertionError("rule-event intake severity mismatch")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    if len(stored_record.get("events", [])) != 1:
        raise AssertionError("expected 1 SQLite rule event from intake")


if __name__ == "__main__":
    raise SystemExit(main())
