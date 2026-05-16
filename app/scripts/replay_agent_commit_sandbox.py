#!/usr/bin/env python3
"""Sandbox replay for the structured Agent commit endpoint."""

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
    restored_sandbox,
)

CONFIG = SandboxConfig(trade_date="2099-01-04")


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent structured commit sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- open/close/rule-event/missing trade id/pnl covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    client = TestClient(api_server.app)
    alias_body = commit_alias_normalized_open(client)
    alias_trade = alias_body["day"]["trades"][-1]
    if alias_trade.get("setupType") != "trend_pullback":
        raise AssertionError("open_trade did not normalize Chinese setup label")
    if alias_trade.get("emotionState") != "impulsive":
        raise AssertionError("open_trade did not normalize emotionState alias")
    if alias_trade.get("preTradeEmotion") != "rushed":
        raise AssertionError("open_trade did not normalize preTradeEmotion alias")
    if not any("自动风险复核提醒" in item for item in alias_body.get("feedbackMessages", [])):
        raise AssertionError("auto event feedback did not explain risk review")
    commit_close_by_trade_id(client, alias_trade["tradeId"])
    close_intake = client.post(
        "/api/agent/session",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "因为是冲动下单了，所以我把这笔交易按原开仓价平掉。11:55。",
            "autoCommit": False,
        },
    )
    assert_ok(close_intake.status_code, close_intake.text, "close intake emotion inference")
    close_proposal = close_intake.json()["workflow"]["result"].get("proposal", {})
    if close_proposal.get("postTradeEmotion") != "unset":
        raise AssertionError("close intake inferred postTradeEmotion without explicit user statement")
    stop_loss_follow_up = client.post(
        "/api/agent/session",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "刚买了546325牛证，0.036进，10万仓位，止损清楚，现在还没出现止损。",
            "autoCommit": False,
        },
    )
    assert_ok(stop_loss_follow_up.status_code, stop_loss_follow_up.text, "stop loss follow-up")
    follow_ups = stop_loss_follow_up.json()["workflow"]["result"].get("followUpQuestions", [])
    if not follow_ups or "止损价或失效条件" not in follow_ups[0]:
        raise AssertionError("stop loss follow-up did not clarify price/invalid condition")

    observe_body = commit_observe_first_open(client)
    if observe_body.get("autoEventId"):
        raise AssertionError("observe_first open should not create a persisted auto event")
    if any(event.get("eventType") == "forced_pause" for event in observe_body["day"].get("events", [])):
        raise AssertionError("observe_first open should not persist forced_pause")
    observe_trade_id = observe_body["day"]["trades"][-1]["tradeId"]
    violation_body = commit_violation_close(client, trade_id=observe_trade_id)
    violation_trade = next(trade for trade in violation_body["day"]["trades"] if trade["tradeId"] == observe_trade_id)
    if violation_trade.get("ruleViolation") is not True:
        raise AssertionError("close_trade did not persist ruleViolation")
    if "止损慢" not in (violation_trade.get("violationNote") or ""):
        raise AssertionError("close_trade did not persist violationNote")

    open_body = commit_open(client)
    trade = open_body["day"]["trades"][-1]
    trade_id = trade["tradeId"]
    if trade["instrumentCode"] != "54927":
        raise AssertionError("structured commit did not preserve instrumentCode")
    if float(trade["entryPrice"]) != 0.054:
        raise AssertionError("structured commit did not preserve entryPrice")

    close_body = commit_close_without_trade_id(client)
    closed_trade = next(trade for trade in close_body["day"]["trades"] if trade["tradeId"] == trade_id)
    if close_body.get("targetTradeId") != trade_id:
        raise AssertionError("single open trade was not auto-selected for close")
    if closed_trade.get("result") != "win":
        raise AssertionError(f"expected close result win, got {closed_trade.get('result')!r}")
    if round(float(closed_trade.get("pnlAmount") or 0), 6) != 60.0:
        raise AssertionError(f"expected pnl 60.0, got {closed_trade.get('pnlAmount')!r}")
    commit_open(client, instrument_code="54928", entry_price=0.07, position_size="10000")
    commit_open(client, instrument_code="54929", entry_price=0.08, position_size="10000")
    ambiguous = client.post(
        "/api/agent/commit",
        json={
            "intent": "close_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "fields": {
                "exitTime": "15:10",
                "exitPrice": 0.09,
                "exitReason": "多笔未平仓时测试缺交易编号。",
            },
        },
    )
    assert_ok(ambiguous.status_code, ambiguous.text, "ambiguous close commit")
    ambiguous_body = ambiguous.json()
    if ambiguous_body.get("committed") is not False:
        raise AssertionError("ambiguous close should not commit")
    if "trade_id" not in ambiguous_body.get("missingFields", []):
        raise AssertionError("ambiguous close should require trade_id")

    event_body = commit_rule_event(client)
    event_id = event_body.get("autoEventId")
    if not event_id:
        raise AssertionError("structured rule-event commit did not return event id")
    events = event_body["day"]["events"]
    if not any(event.get("eventId") == event_id and event.get("eventType") == "emotion_trigger" for event in events):
        raise AssertionError("structured rule-event commit was not present in response read-back")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    if len(stored_record.get("trades", [])) != 5:
        raise AssertionError("expected five trades after structured commit replay")
    if not any(event.get("event_id") == event_id and event.get("event_type") == "emotion_trigger" for event in stored_record.get("events", [])):
        raise AssertionError("structured rule-event commit was not persisted to SQLite")


def commit_open(
    client: TestClient,
    *,
    instrument_code: str = "54927",
    entry_price: float = 0.054,
    position_size: str = "1000",
) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "open_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "结构化开仓 sandbox",
            "fields": {
                "tradeTime": "14:00",
                "sessionWindow": "mid_session",
                "direction": "short",
                "certificateSide": "bear",
                "instrumentCode": instrument_code,
                "setupType": "opening_breakout",
                "abcGrade": "A",
                "directionClear": True,
                "locationOk": True,
                "confirmationOk": True,
                "riskClear": True,
                "certificateFilterPassed": True,
                "entryPrice": entry_price,
                "stopLoss": round(entry_price - 0.01, 4),
                "positionSize": position_size,
                "followedPlan": True,
                "entryReason": "方向、位置、确认和风险都清楚。",
                "instrumentType": "bull_bear_certificate",
                "underlying": "HSI",
                "abnormalScenario": "none",
                "preTradeEmotion": "stable",
                "emotionState": "stable",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured open commit")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"structured open did not commit: {body}")
    return body


def commit_alias_normalized_open(client: TestClient) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "open_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "控制不住又下了一单，形态是突破回踩。",
            "fields": {
                "tradeTime": "09:55",
                "sessionWindow": "opening_30m",
                "direction": "long",
                "certificateSide": "bull",
                "instrumentCode": "546324",
                "setupType": "突破回踩",
                "abcGrade": "A",
                "directionClear": True,
                "locationOk": True,
                "confirmationOk": True,
                "riskClear": True,
                "certificateFilterPassed": True,
                "entryPrice": 0.036,
                "stopLoss": 0.03,
                "positionSize": "100000",
                "followedPlan": True,
                "entryReason": "趋势回踩确认。",
                "instrumentType": "bull_bear_certificate",
                "underlying": "HSI",
                "abnormalScenario": "none",
                "preTradeEmotion": "控制不住",
                "emotionState": "控制不住",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured alias normalized open commit")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"structured alias open did not commit: {body}")
    return body


def commit_observe_first_open(client: TestClient) -> dict:
    client.post(
        "/api/days/by-key/workbench",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "tradingMode": "hsi_bull_bear_certificate",
            "mainDirection": "undecided",
            "currentState": "stable",
            "upperPressure": "",
            "lowerSupport": "",
            "pivotLevel": "",
            "postMarketSummary": "",
            "capitalUsed": None,
            "profitTargetPct": None,
            "hkWatchlist": "",
            "usWatchlist": "",
            "playbookPreset": "",
            "openingPlan": "observe_first",
            "focusSetup": "clear_observe",
            "open30KeySignal": "先观察，等明确信号。",
            "certificateFilterNote": "过滤必须通过。",
            "abnormalPlan": "乱甩不做。",
            "optionPlaybookPreset": "",
            "optionSessionPlan": "",
            "focusTickers": "",
            "optionFocusSetup": "",
            "optionEntrySignal": "",
            "optionContractFilter": "",
            "optionRiskPlan": "",
            "optionEventRiskPlan": "",
        },
    )
    return commit_open(client, instrument_code="341021", entry_price=0.055, position_size="200000")


def commit_close_without_trade_id(client: TestClient) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "close_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "结构化平仓 sandbox",
            "fields": {
                "exitTime": "14:30",
                "exitPrice": 0.114,
                "exitReason": "信号消失，按计划平仓。",
                "postTradeEmotion": "stable",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured close commit")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"structured close did not commit: {body}")
    return body


def commit_close_by_trade_id(client: TestClient, trade_id: str) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "close_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "映射测试交易平仓。",
            "fields": {
                "tradeId": trade_id,
                "exitTime": "10:05",
                "exitPrice": 0.038,
                "exitReason": "映射测试结束。",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured close by trade id")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"structured close by trade id did not commit: {body}")
    return body


def commit_violation_close(client: TestClient, *, trade_id: str) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "close_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "止损慢了，不自觉扛单，导致巨额亏损。",
            "fields": {
                "tradeId": trade_id,
                "exitTime": "10:20",
                "exitPrice": 0.035,
                "exitReason": "止损慢了，不自觉扛单。",
                "ruleViolation": True,
                "violationNote": "止损慢了，不自觉扛单。",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured violation close commit")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"structured violation close did not commit: {body}")
    return body


def commit_rule_event(client: TestClient) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "rule_event",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "纪律事件：亏了以后想报复性加仓，需要暂停",
            "fields": {
                "eventTime": "15:20",
                "eventType": "emotion_trigger",
                "severity": "stop",
                "triggerReason": "亏损后想报复性加仓",
                "actionTaken": "暂停交易",
            },
        },
    )
    assert_ok(response.status_code, response.text, "structured rule-event commit")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"structured rule-event did not commit: {body}")
    return body


if __name__ == "__main__":
    raise SystemExit(main())
