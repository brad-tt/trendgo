#!/usr/bin/env python3
"""Sandbox replay for uncovered real-interaction Agent scenarios."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import api_server  # noqa: E402
from database import dal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scripts.agent_sandbox_utils import SandboxConfig, assert_ok, create_sandbox_day, restored_sandbox  # noqa: E402


CONFIG = SandboxConfig(trade_date="2099-01-05")


def main() -> int:
    with restored_sandbox(CONFIG):
        results = run_sandbox_replay()

    print("\nAgent uncovered scenario sandbox replay completed.")
    print(f"- test date: {CONFIG.trade_date}")
    for result in results:
        print(f"- {result}")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> list[str]:
    client = TestClient(api_server.app)
    create_sandbox_day(client, CONFIG)
    results: list[str] = []

    first_id = commit_open(client, code="341021", entry=0.055, position="200000", grade="B")
    second_id = commit_open(client, code="341022", entry=0.061, position="100000", grade="A")
    ambiguous = commit_close(client, exit_price=0.058, trade_id="")
    if ambiguous.get("committed") is not False or "trade_id" not in ambiguous.get("missingFields", []):
        raise AssertionError(f"multi-open ambiguous close should require trade_id: {ambiguous}")
    results.append("multi-open ambiguous close requires trade_id: pass")

    duplicate_id = commit_open(client, code="341021", entry=0.059, position="50000", grade="A")
    if duplicate_id == first_id:
        raise AssertionError("duplicate-code open reused an existing trade id")
    results.append("same-code second open creates separate trade id: pass")

    b_grade_body = commit_open_body(client, code="341099", entry=0.07, position="1000000", grade="B")
    b_rule_ids = {hit.get("ruleId") for hit in b_grade_body.get("ruleHits", [])}
    if "SETUP-ABC-007" not in b_rule_ids:
        raise AssertionError(f"B-grade large position did not return B-grade rule hit: {b_grade_body.get('ruleHits')}")
    results.append("B-grade large position returns SETUP-ABC-007 warning: pass")

    closed = commit_close(client, exit_price=0.035, trade_id=first_id, rule_violation=True)
    closed_trade = next(trade for trade in closed["day"]["trades"] if trade["tradeId"] == first_id)
    if closed_trade.get("result") != "loss":
        raise AssertionError(f"bull loss close expected result=loss, got {closed_trade.get('result')!r}")
    if round(float(closed_trade.get("pnlAmount") or 0), 6) != -4000.0:
        raise AssertionError(f"bull loss close expected pnl=-4000, got {closed_trade.get('pnlAmount')!r}")
    if closed_trade.get("ruleViolation") is not True:
        raise AssertionError("exit-stage ruleViolation did not persist")
    results.append("bull loss pnl and exit-stage violation persistence: pass")

    stop_event = commit_rule_event(client, linked_trade_id=first_id)
    if stop_event.get("committed") is not True or not stop_event.get("autoEventId"):
        raise AssertionError(f"stop rule event did not commit: {stop_event}")
    after_stop = commit_open_body(client, code="341088", entry=0.08, position="10000", grade="A")
    stop_events = [
        event
        for event in after_stop["day"].get("events", [])
        if event.get("linkedTradeId") == after_stop["day"]["trades"][-1]["tradeId"]
    ]
    if after_stop.get("committed") is not True:
        raise AssertionError("current backend should still record already-happened facts after stop")
    if not any(event.get("severity") in {"stop", "warning"} for event in stop_events):
        raise AssertionError("post-stop open did not link a discipline/risk event")
    results.append("post-stop open still commits as fact and links discipline event: current behavior")

    incomplete_review = client.post(
        "/api/agent/commit",
        json={
            "intent": "review",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "fields": {"executionIssue": "今天做得不好"},
        },
    )
    assert_ok(incomplete_review.status_code, incomplete_review.text, "incomplete review commit")
    incomplete_review_body = incomplete_review.json()
    if incomplete_review_body.get("committed") is not False:
        raise AssertionError("incomplete review should not commit")
    missing = set(incomplete_review_body.get("missingFields", []))
    expected_missing = {"best_trade_note", "worst_trade_note", "emotion_issue", "risk_issue", "next_day_one_fix"}
    if not expected_missing.issubset(missing):
        raise AssertionError(f"incomplete review missing fields mismatch: {missing}")
    results.append("incomplete review returns missing fields without writing: pass")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    if len(stored_record.get("trades", [])) < 5:
        raise AssertionError("expected sandbox trades to persist during replay")
    return results


def commit_open_body(
    client: TestClient,
    *,
    code: str,
    entry: float,
    position: str,
    grade: str,
) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "open_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": f"{code} 牛证开仓，{grade}级，沙盒测试",
            "fields": {
                "tradeTime": "10:00",
                "sessionWindow": "mid_session",
                "direction": "long",
                "certificateSide": "bull",
                "instrumentCode": code,
                "setupType": "trend_pullback",
                "abcGrade": grade,
                "directionClear": True,
                "locationOk": True,
                "confirmationOk": True,
                "riskClear": True,
                "certificateFilterPassed": True,
                "entryPrice": entry,
                "stopLoss": round(entry - 0.005, 4),
                "targetPrice": round(entry + 0.01, 4),
                "positionSize": position,
                "followedPlan": True,
                "entryReason": "沙盒测试：方向、位置、确认和过滤都通过。",
                "instrumentType": "bull_bear_certificate",
                "underlying": "HSI",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured open commit")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"open did not commit: {body}")
    return body


def commit_open(client: TestClient, *, code: str, entry: float, position: str, grade: str) -> str:
    body = commit_open_body(client, code=code, entry=entry, position=position, grade=grade)
    return body["day"]["trades"][-1]["tradeId"]


def commit_close(
    client: TestClient,
    *,
    exit_price: float,
    trade_id: str = "",
    rule_violation: bool = False,
) -> dict:
    fields = {
        "exitTime": "10:20",
        "exitPrice": exit_price,
        "exitReason": "沙盒测试平仓。",
    }
    if trade_id:
        fields["tradeId"] = trade_id
    if rule_violation:
        fields["ruleViolation"] = True
        fields["violationNote"] = "止损慢了，不自觉扛单。"
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "close_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "沙盒测试平仓",
            "fields": fields,
        },
    )
    assert_ok(response.status_code, response.text, "structured close commit")
    return response.json()


def commit_rule_event(client: TestClient, *, linked_trade_id: str) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "rule_event",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "沙盒 stop 事件：亏损后暂停",
            "fields": {
                "eventTime": "10:30",
                "eventType": "rule_violation",
                "severity": "stop",
                "triggerReason": "沙盒测试：止损执行失败后暂停。",
                "actionTaken": "停止新开仓，只允许复盘和风险处理。",
                "linkedTradeId": linked_trade_id,
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured rule event commit")
    return response.json()


if __name__ == "__main__":
    raise SystemExit(main())
