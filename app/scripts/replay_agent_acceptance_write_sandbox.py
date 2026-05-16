#!/usr/bin/env python3
"""Sandbox replay for acceptance review and closeout path."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import api_server  # noqa: E402
import local_web  # noqa: E402
from database import dal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scripts.agent_sandbox_utils import (  # noqa: E402
    SandboxConfig,
    assert_ok,
    create_sandbox_day,
    load_lifecycle_samples,
    restored_sandbox,
)

CONFIG = SandboxConfig()


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent acceptance write sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- review, validation, closeout covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    samples = load_lifecycle_samples()
    open_sample = samples["openTrades"][0]
    close_sample = samples["closeTrades"][0]
    review_sample = samples["reviews"][0]["review"]
    client = TestClient(api_server.app)

    create_sandbox_day(client, CONFIG)
    trade_id = create_and_close_trade(client, open_sample, close_sample)

    payload = {
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "bestTradeNote": "唯一一笔止损执行是对的，没有继续扛单。",
        "worstTradeNote": review_sample["worstTradeNote"],
        "executionIssue": review_sample["executionIssue"],
        "emotionIssue": review_sample["emotionIssue"],
        "riskIssue": review_sample["riskIssue"],
        "nextDayOneFix": review_sample["nextDayOneFix"],
        "winRate": "0%",
        "maxLossTrade": trade_id,
        "marketIssue": review_sample["marketIssue"],
        "setupIssue": review_sample["setupIssue"],
        "preMarketDone": True,
        "intradayRecordComplete": True,
        "postMarketReviewDone": True,
        "impulsiveTradeDetected": True,
        "noStopLossTradeDetected": False,
        "emotionalOvertradeDetected": False,
        "noTradeDay": False,
        "noTradeNote": "",
        "mainIssueOfDay": "追单前没有把反证和退出条件说完整。",
        "mainImprovementOfDay": "下一笔开仓前先完整复述风险，再允许执行。",
    }
    response = client.post("/api/day-records/review/acceptance", json=payload)
    assert_ok(response.status_code, response.text, "save sandbox acceptance review")
    body = response.json()
    day = body["day"]
    review = day["review"]
    validation = day["validation"]
    closeout = day["closeout"]
    if review.get("tradeCount") != 1:
        raise AssertionError("acceptance review tradeCount mismatch")
    if review.get("maxLossTrade") != trade_id:
        raise AssertionError("acceptance review maxLossTrade mismatch")
    if validation.get("postMarketReviewDone") is not True:
        raise AssertionError("acceptance validation postMarketReviewDone mismatch")
    if closeout.get("exists") is not True:
        raise AssertionError("acceptance closeout was not generated")

    closeout_path = local_web.CLOSEOUTS_DIR / f"{CONFIG.trade_date}-{CONFIG.market}-closeout-draft.md"
    if not closeout_path.exists():
        raise AssertionError("sandbox closeout file missing on disk")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_review = stored_record.get("review", {})
    stored_validation = stored_record.get("validation", {})
    if stored_review.get("trade_count") != 1:
        raise AssertionError("SQLite acceptance review trade_count mismatch")
    if stored_validation.get("post_market_review_done") is not True:
        raise AssertionError("SQLite acceptance validation post_market_review_done mismatch")


def create_and_close_trade(client: TestClient, open_sample: dict, close_sample: dict) -> str:
    open_payload = {
        **open_sample["trade"],
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "rawNote": open_sample.get("rawNote", ""),
        "agentNote": "sandbox acceptance replay setup trade; should be restored after test",
        "suspectedDistortions": open_sample.get("suspectedDistortions", []),
    }
    open_response = client.post("/api/agent/trades/open", json=open_payload)
    assert_ok(open_response.status_code, open_response.text, "create sandbox open trade")
    trade = open_response.json()["day"]["trades"][0]
    trade_id = trade["tradeId"]

    close_payload = {
        **open_sample["trade"],
        **close_sample["exit"],
    }
    close_response = client.put(
        f"/api/day-records/trades/{trade_id}",
        params={"tradeDate": CONFIG.trade_date, "market": CONFIG.market},
        json=close_payload,
    )
    assert_ok(close_response.status_code, close_response.text, "close sandbox trade")
    return trade_id


if __name__ == "__main__":
    raise SystemExit(main())
