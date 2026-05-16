#!/usr/bin/env python3
"""Sandbox replay for natural-language review intake."""

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

    print("\nAgent natural-language review intake sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- parse-only and commit path covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    samples = load_lifecycle_samples()
    open_sample = samples["openTrades"][0]
    close_sample = samples["closeTrades"][0]
    client = TestClient(api_server.app)

    create_sandbox_day(client, CONFIG)
    create_and_close_trade(client, open_sample, close_sample)

    incomplete = client.post(
        "/api/agent/intake/review",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "今天主要还是执行和情绪都有问题。",
            "commit": False,
        },
    )
    assert_ok(incomplete.status_code, incomplete.text, "parse incomplete review intake")
    incomplete_body = incomplete.json()
    if incomplete_body.get("committed") is not False:
        raise AssertionError("incomplete review intake should not commit")
    if not incomplete_body.get("followUpQuestions"):
        raise AssertionError("incomplete review intake should return follow-up questions")

    complete = client.post(
        "/api/agent/intake/review",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": (
                "最好：唯一一笔交易按预设止损执行，没有扩大亏损。"
                "最差：FOMO 追单本身就不是计划内。"
                "执行问题：没有等到方向和确认同时满足。"
                "情绪问题：怕错过影响了进场。"
                "风控问题：开仓前止损定义还是不够快。"
                "明天只改：每次出手前先口述止损和反证。"
            ),
            "commit": True,
            "agentNote": "sandbox nl review intake commit",
        },
    )
    assert_ok(complete.status_code, complete.text, "commit complete review intake")
    body = complete.json()
    if body.get("committed") is not True:
        raise AssertionError("complete review intake should commit")
    review = (body.get("day") or {}).get("review") or {}
    if not review.get("bestTradeNote"):
        raise AssertionError("review intake bestTradeNote missing")
    if not review.get("nextDayOneFix"):
        raise AssertionError("review intake nextDayOneFix missing")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    if not stored_record.get("review", {}).get("best_trade_note"):
        raise AssertionError("SQLite review intake best_trade_note missing")


def create_and_close_trade(client: TestClient, open_sample: dict, close_sample: dict) -> None:
    open_payload = {
        **open_sample["trade"],
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
        "rawNote": open_sample.get("rawNote", ""),
        "agentNote": "sandbox nl review intake setup trade; should be restored after test",
        "suspectedDistortions": open_sample.get("suspectedDistortions", []),
    }
    open_response = client.post("/api/agent/trades/open", json=open_payload)
    assert_ok(open_response.status_code, open_response.text, "create sandbox open trade for review intake")
    trade_id = open_response.json()["day"]["trades"][0]["tradeId"]

    close_payload = {**open_sample["trade"], **close_sample["exit"]}
    close_response = client.put(
        f"/api/day-records/trades/{trade_id}",
        params={"tradeDate": CONFIG.trade_date, "market": CONFIG.market},
        json=close_payload,
    )
    assert_ok(close_response.status_code, close_response.text, "close sandbox trade for review intake")


if __name__ == "__main__":
    raise SystemExit(main())
