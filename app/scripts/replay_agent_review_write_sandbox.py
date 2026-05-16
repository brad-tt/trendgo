#!/usr/bin/env python3
"""Sandbox replay for review write path."""

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
    load_lifecycle_samples,
    restored_sandbox,
)

CONFIG = SandboxConfig()


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent review write sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
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

    review_payload = {
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "pnl": "-100",
        "tradeCount": 1,
        "bestTradeNote": "唯一一笔交易按预设止损执行，没有扩大亏损。",
        "worstTradeNote": review_sample["worstTradeNote"],
        "executionIssue": review_sample["executionIssue"],
        "emotionIssue": review_sample["emotionIssue"],
        "riskIssue": review_sample["riskIssue"],
        "nextDayOneFix": review_sample["nextDayOneFix"],
        "winRate": "0%",
        "maxLossTrade": trade_id,
        "marketIssue": review_sample["marketIssue"],
        "setupIssue": review_sample["setupIssue"],
    }
    review_response = client.put("/api/day-records/review", json=review_payload)
    assert_ok(review_response.status_code, review_response.text, "save sandbox review")
    body = review_response.json()
    review = body["day"]["review"]
    if review.get("pnl") != "-100":
        raise AssertionError(f"expected review pnl '-100', got {review.get('pnl')!r}")
    if review.get("tradeCount") != 1:
        raise AssertionError(f"expected review tradeCount 1, got {review.get('tradeCount')!r}")
    if review.get("maxLossTrade") != trade_id:
        raise AssertionError("saved review maxLossTrade mismatch")
    for key in ["bestTradeNote", "worstTradeNote", "executionIssue", "emotionIssue", "riskIssue", "nextDayOneFix"]:
        if not review.get(key):
            raise AssertionError(f"missing saved review field {key}")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_review = stored_record.get("review", {})
    if stored_review.get("pnl") != "-100":
        raise AssertionError("SQLite sandbox review pnl mismatch")
    if stored_review.get("trade_count") != 1:
        raise AssertionError("SQLite sandbox review trade_count mismatch")


def create_and_close_trade(client: TestClient, open_sample: dict, close_sample: dict) -> str:
    open_payload = {
        **open_sample["trade"],
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "rawNote": open_sample.get("rawNote", ""),
        "agentNote": "sandbox review replay setup trade; should be restored after test",
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
