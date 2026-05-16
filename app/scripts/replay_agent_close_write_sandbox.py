#!/usr/bin/env python3
"""Sandbox replay for the Agent close-trade write path."""

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

    print("\nAgent close write sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    samples = load_lifecycle_samples()
    open_sample = samples["openTrades"][0]
    close_sample = samples["closeTrades"][0]
    client = TestClient(api_server.app)

    create_sandbox_day(client, CONFIG)
    open_body = create_open_trade(client, open_sample)
    trade = open_body["day"]["trades"][0]
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
    body = close_response.json()
    updated_trade = body["day"]["trades"][0]

    expected_result = close_sample["expectedResult"]
    expected_pnl = float(close_sample["expectedPnlAmount"])
    if updated_trade.get("result") != expected_result:
        raise AssertionError(f"expected close result {expected_result!r}, got {updated_trade.get('result')!r}")
    if round(float(updated_trade.get("pnlAmount") or 0), 6) != round(expected_pnl, 6):
        raise AssertionError(f"expected close pnl {expected_pnl!r}, got {updated_trade.get('pnlAmount')!r}")
    for key in ["exitTime", "exitPrice", "exitReason", "postTradeEmotion"]:
        if updated_trade.get(key) in {"", None}:
            raise AssertionError(f"missing updated close field {key}")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_trade = stored_record.get("trades", [])[0]
    if stored_trade.get("result") != expected_result:
        raise AssertionError("SQLite sandbox trade close result mismatch")


def create_open_trade(client: TestClient, sample: dict) -> dict:
    payload = {
        **sample["trade"],
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "rawNote": sample.get("rawNote", ""),
        "agentNote": "sandbox close replay setup trade; should be restored after test",
        "suspectedDistortions": sample.get("suspectedDistortions", []),
    }
    response = client.post("/api/agent/trades/open", json=payload)
    assert_ok(response.status_code, response.text, "create sandbox open trade")
    return response.json()


if __name__ == "__main__":
    raise SystemExit(main())
