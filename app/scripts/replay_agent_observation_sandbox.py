#!/usr/bin/env python3
"""Sandbox replay for Agent observations as a separate record layer."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import api_server  # noqa: E402
from database import dal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scripts.agent_sandbox_utils import SandboxConfig, assert_ok, restored_sandbox  # noqa: E402

CONFIG = SandboxConfig(trade_date="2099-01-08")


def main() -> int:
    with restored_sandbox(CONFIG):
        run_sandbox_replay()

    print("\nAgent observation sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- observation linked to committed trade: yes")
    print("- observation-only API read-back: yes")
    print("- database restored: yes")
    return 0


def run_sandbox_replay() -> None:
    client = TestClient(api_server.app)
    seed_workbench(client)
    open_body = commit_open_with_observation(client)

    trade_id = open_body["day"]["trades"][-1]["tradeId"]
    observations = open_body["day"].get("observations", [])
    if len(observations) != 1:
        raise AssertionError(f"expected one observation in response read-back, got {len(observations)}")
    observation = observations[0]
    if observation.get("linkedTradeId") != trade_id:
        raise AssertionError(f"observation was not linked to created trade {trade_id}: {observation}")
    if observation.get("observationType") != "direction_shift":
        raise AssertionError(f"unexpected observation type: {observation}")
    if observation.get("status") != "review_required":
        raise AssertionError(f"unexpected observation status: {observation}")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    stored_observations = stored_record.get("observations", [])
    if not any(
        item.get("linked_trade_id") == trade_id and item.get("observation_type") == "direction_shift"
        for item in stored_observations
    ):
        raise AssertionError(f"SQLite read-back did not include linked direction_shift observation: {stored_observations}")

    standalone_body = create_standalone_observation(client, linked_trade_id=trade_id)
    all_observations = standalone_body["day"].get("observations", [])
    if len(all_observations) != 2:
        raise AssertionError(f"expected two observations after standalone insert, got {len(all_observations)}")
    if not any(item.get("observationType") == "risk_mismatch" for item in all_observations):
        raise AssertionError(f"standalone risk_mismatch observation missing: {all_observations}")


def seed_workbench(client: TestClient) -> None:
    response = client.post(
        "/api/days",
        json={
            "tradeDate": CONFIG.trade_date,
            "currentState": "stable",
            "focus": "Agent observation sandbox.",
            "tradingMode": CONFIG.trading_mode,
        },
    )
    assert_ok(response.status_code, response.text, "create sandbox day")
    response = client.put(
        "/api/day-records/workbench",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "tradingMode": CONFIG.trading_mode,
            "mainDirection": "long",
            "currentState": "stable",
            "openingPlan": "observe_first",
            "focusSetup": "opening_breakout",
            "open30KeySignal": "突破后回踩守住。",
        },
    )
    assert_ok(response.status_code, response.text, "seed sandbox workbench")


def commit_open_with_observation(client: TestClient) -> dict:
    response = client.post(
        "/api/agent/commit",
        json={
            "intent": "open_trade",
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "rawNote": "09:50 熊证535776，0.038开仓，仓位200000，止损0.035，出现高开回落信号。",
            "agentNote": "Agent发现盘前主方向做多，但盘中开熊证，已追问并得到用户解释。",
            "fields": {
                "tradeTime": "09:50",
                "sessionWindow": "opening_30m",
                "direction": "short",
                "certificateSide": "bear",
                "instrumentCode": "535776",
                "setupType": "opening_breakout",
                "abcGrade": "B",
                "directionClear": True,
                "locationOk": True,
                "confirmationOk": True,
                "riskClear": True,
                "certificateFilterPassed": True,
                "entryPrice": 0.038,
                "stopLoss": 0.035,
                "positionSize": "200000",
                "followedPlan": False,
                "entryReason": "出现高开回落信号。",
                "instrumentType": "bull_bear_certificate",
                "underlying": "HSI",
                "abnormalScenario": "open_whipsaw",
            },
            "observations": [
                {
                    "observationType": "direction_shift",
                    "severity": "warning",
                    "source": "agent_question",
                    "summary": "盘前主方向做多，但盘中开熊证，需要确认是否为有效方向切换。",
                    "evidence": "workbench.mainDirection=long; trade.direction=short; certificateSide=bear",
                    "userResponse": "出现高开回落信号。",
                    "status": "review_required",
                    "reviewRequired": True,
                }
            ],
        },
    )
    assert_ok(response.status_code, response.text, "commit open trade with observation")
    body = response.json()
    if body.get("committed") is not True:
        raise AssertionError(f"open trade with observation did not commit: {body}")
    return body


def create_standalone_observation(client: TestClient, *, linked_trade_id: str) -> dict:
    response = client.post(
        "/api/day-records/observations",
        json={
            "tradeDate": CONFIG.trade_date,
            "market": CONFIG.market,
            "linkedTradeId": linked_trade_id,
            "observationType": "risk_mismatch",
            "severity": "info",
            "source": "agent_follow_up",
            "summary": "B级机会的仓位基准仍缺少明确标准。",
            "evidence": "abcGrade=B; positionSize=200000",
            "userResponse": "系统里没有说明怎样算大仓位或小仓位。",
            "status": "open",
            "reviewRequired": True,
        },
    )
    assert_ok(response.status_code, response.text, "create standalone observation")
    return response.json()


if __name__ == "__main__":
    raise SystemExit(main())
