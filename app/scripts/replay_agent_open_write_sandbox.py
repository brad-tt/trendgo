#!/usr/bin/env python3
"""Sandbox replay for the Agent open-trade write path.

This script uses the real FastAPI endpoint and the real SQLite write path,
then restores the database and local state before exiting.
"""

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
    assert_expected_subset,
    assert_ok,
    create_sandbox_day,
    load_lifecycle_samples,
    restored_sandbox,
)

CONFIG = SandboxConfig()


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent open write sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    samples = load_lifecycle_samples()
    sample = samples["openTrades"][0]
    client = TestClient(api_server.app)

    create_sandbox_day(client, CONFIG)

    payload = {
        **sample["trade"],
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "rawNote": sample.get("rawNote", ""),
        "agentNote": "sandbox write replay; should be restored after test",
        "suspectedDistortions": sample.get("suspectedDistortions", []),
    }
    write_response = client.post("/api/agent/trades/open", json=payload)
    assert_ok(write_response.status_code, write_response.text, "agent open trade")
    body = write_response.json()

    trades = body.get("day", {}).get("trades", [])
    if len(trades) != 1:
        raise AssertionError(f"expected exactly 1 sandbox trade, got {len(trades)}")
    trade = trades[0]
    if trade.get("instrumentCode") != sample["trade"]["instrumentCode"]:
        raise AssertionError("sandbox trade instrument code mismatch")

    actual_rule_ids = {item["ruleId"] for item in body.get("ruleHits", [])}
    actual_route_ids = {item["routeId"] for item in body.get("knowledgeRoutes", [])}
    assert_expected_subset("rule hits", sample.get("expectedRuleIds", []), actual_rule_ids)
    assert_expected_subset("knowledge routes", sample.get("expectedRouteIds", []), actual_route_ids)

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_trades = stored_record.get("trades", [])
    if len(stored_trades) != 1:
        raise AssertionError(f"expected 1 SQLite sandbox trade, got {len(stored_trades)}")


if __name__ == "__main__":
    raise SystemExit(main())
