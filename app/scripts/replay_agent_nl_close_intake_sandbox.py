#!/usr/bin/env python3
"""Sandbox replay for natural-language close-trade intake."""

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

    print("\nAgent natural-language close intake sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- parse-only and commit path covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    samples = load_lifecycle_samples()
    open_sample = samples["openTrades"][0]
    client = TestClient(api_server.app)

    create_sandbox_day(client, CONFIG)
    trade_id = create_open_trade(client, open_sample)

    incomplete_response = client.post(
        "/api/agent/intake/close",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "这笔先平掉，但价格还没记。",
            "commit": False,
        },
    )
    assert_ok(incomplete_response.status_code, incomplete_response.text, "parse incomplete close intake")
    incomplete_body = incomplete_response.json()
    if incomplete_body.get("committed") is not False:
        raise AssertionError("incomplete close intake should not commit")
    if incomplete_body.get("canWrite") is not False:
        raise AssertionError("incomplete close intake should not be writable")
    if not incomplete_body.get("followUpQuestions"):
        raise AssertionError("incomplete close intake should return follow-up questions")

    complete_response = client.post(
        "/api/agent/intake/close",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "10:18 平仓 0.095，理由：到达预设止损，按计划离场，情绪稳定。",
            "commit": True,
            "agentNote": "sandbox nl close intake commit",
        },
    )
    assert_ok(complete_response.status_code, complete_response.text, "commit complete close intake")
    body = complete_response.json()
    if body.get("committed") is not True:
        raise AssertionError("complete close intake should commit")
    if body.get("targetTradeId") != trade_id:
        raise AssertionError("close intake targetTradeId mismatch")
    if body.get("resultPreview") != "loss":
        raise AssertionError("close intake resultPreview mismatch")
    day = body.get("day") or {}
    trades = day.get("trades") or []
    if len(trades) != 1:
        raise AssertionError(f"expected 1 committed close trade, got {len(trades)}")
    trade = trades[0]
    if trade.get("tradeId") != trade_id:
        raise AssertionError("close intake committed tradeId mismatch")
    if trade.get("exitPrice") != 0.095:
        raise AssertionError("close intake exitPrice mismatch")
    if trade.get("result") != "loss":
        raise AssertionError("close intake result mismatch")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_trade = stored_record.get("trades", [])[0]
    if stored_trade.get("trade_id") != trade_id:
        raise AssertionError("SQLite close intake trade_id mismatch")
    if stored_trade.get("result") != "loss":
        raise AssertionError("SQLite close intake result mismatch")


def create_open_trade(client: TestClient, sample: dict) -> str:
    payload = {
        **sample["trade"],
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "rawNote": sample.get("rawNote", ""),
        "agentNote": "sandbox nl close intake setup trade; should be restored after test",
        "suspectedDistortions": sample.get("suspectedDistortions", []),
    }
    response = client.post("/api/agent/trades/open", json=payload)
    assert_ok(response.status_code, response.text, "create sandbox open trade for close intake")
    return response.json()["day"]["trades"][0]["tradeId"]


if __name__ == "__main__":
    raise SystemExit(main())
