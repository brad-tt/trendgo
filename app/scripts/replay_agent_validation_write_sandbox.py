#!/usr/bin/env python3
"""Sandbox replay for validation write path."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import api_server  # noqa: E402
from database import dal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scripts.agent_sandbox_utils import (  # noqa: E402
    SandboxConfig,
    assert_ok,
    create_sandbox_day,
    restored_sandbox,
)

CONFIG = SandboxConfig()


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent validation write sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    client = TestClient(api_server.app)
    create_sandbox_day(client, CONFIG)

    payload = {
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "preMarketDone": True,
        "intradayRecordComplete": True,
        "postMarketReviewDone": True,
        "impulsiveTradeDetected": True,
        "noStopLossTradeDetected": False,
        "emotionalOvertradeDetected": False,
        "noTradeDay": False,
        "noTradeNote": "",
        "mainIssueOfDay": "进场前没有把反证说完整，执行节奏还是偏急。",
        "mainImprovementOfDay": "明天每次出手前先口述止损和反证，再允许点击执行。",
    }
    response = client.put("/api/day-records/validation", json=payload)
    assert_ok(response.status_code, response.text, "save sandbox validation")
    body = response.json()
    validation = body["day"]["validation"]
    if validation.get("preMarketDone") is not True:
        raise AssertionError("validation preMarketDone mismatch")
    if validation.get("mainIssueOfDay") != payload["mainIssueOfDay"]:
        raise AssertionError("validation mainIssueOfDay mismatch")
    if validation.get("mainImprovementOfDay") != payload["mainImprovementOfDay"]:
        raise AssertionError("validation mainImprovementOfDay mismatch")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_validation = stored_record.get("validation", {})
    if stored_validation.get("pre_market_done") is not True:
        raise AssertionError("SQLite sandbox validation pre_market_done mismatch")
    if stored_validation.get("main_issue_of_day") != payload["mainIssueOfDay"]:
        raise AssertionError("SQLite sandbox validation main_issue_of_day mismatch")


if __name__ == "__main__":
    raise SystemExit(main())
