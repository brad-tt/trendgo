#!/usr/bin/env python3
"""Sandbox replay for natural-language open-trade intake."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import api_server  # noqa: E402
from database import dal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scripts.agent_sandbox_utils import SandboxConfig, assert_ok, restored_sandbox  # noqa: E402

CONFIG = SandboxConfig()


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent natural-language intake sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- parse-only and commit path covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    client = TestClient(api_server.app)

    incomplete_response = client.post(
        "/api/agent/intake/open",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "恒指突然拉起来，我想追一笔做多，但止损还没想清楚。",
            "commit": False,
        },
    )
    assert_ok(incomplete_response.status_code, incomplete_response.text, "parse incomplete intake note")
    incomplete_body = incomplete_response.json()
    if incomplete_body.get("committed") is not False:
        raise AssertionError("incomplete intake note should not commit")
    if incomplete_body.get("canWrite") is not False:
        raise AssertionError("incomplete intake note should not be writable")
    if not incomplete_body.get("missingFields"):
        raise AssertionError("incomplete intake note should report missing fields")
    if not incomplete_body.get("followUpQuestions"):
        raise AssertionError("incomplete intake note should return follow-up questions")
    if not incomplete_body.get("context"):
        raise AssertionError("incomplete intake note should include context")

    complete_response = client.post(
        "/api/agent/intake/open",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": (
                "10:05 开盘后做恒指牛证 HSI-CERT-B，做多，回踩确认，B级，方向清楚，位置合理，"
                "确认到位，止损清楚，过滤通过，入场 0.088，止损 0.080，仓位 5000，按计划执行。"
                "理由：回踩关键位后重新站回。"
            ),
            "commit": True,
            "agentNote": "sandbox nl intake commit",
        },
    )
    assert_ok(complete_response.status_code, complete_response.text, "commit complete intake note")
    body = complete_response.json()
    if body.get("committed") is not True:
        raise AssertionError("complete intake note should commit")
    if body.get("canWrite") is not True:
        raise AssertionError("complete intake note should be writable")
    if not body.get("context"):
        raise AssertionError("complete intake note should include context")
    day = body.get("day") or {}
    trades = day.get("trades") or []
    if len(trades) != 1:
        raise AssertionError(f"expected 1 committed trade, got {len(trades)}")
    trade = trades[0]
    if trade.get("instrumentCode") != "HSI-CERT-B":
        raise AssertionError("committed intake trade instrumentCode mismatch")
    if trade.get("abcGrade") != "B":
        raise AssertionError("committed intake trade abcGrade mismatch")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_trades = stored_record.get("trades", [])
    if len(stored_trades) != 1:
        raise AssertionError(f"expected 1 SQLite intake trade, got {len(stored_trades)}")


if __name__ == "__main__":
    raise SystemExit(main())
