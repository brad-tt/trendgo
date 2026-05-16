#!/usr/bin/env python3
"""Sandbox replay for rule-event create, update, and delete paths."""

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

    print("\nAgent rule-event write sandbox replay passed.")
    print(f"- test date: {CONFIG.trade_date}")
    print("- create/update/delete covered: yes")
    print("- database restored: yes")
    print("- test record files removed: yes")
    return 0


def run_sandbox_replay() -> None:
    samples = load_lifecycle_samples()
    sample = samples["ruleEvents"][0]
    client = TestClient(api_server.app)

    create_sandbox_day(client, CONFIG)
    created = create_rule_event(client, sample["event"])
    event = created["day"]["events"][0]
    event_id = event["eventId"]
    if event.get("severity") != sample["event"]["severity"]:
        raise AssertionError("created rule-event severity mismatch")

    updated_payload = {
        **sample["event"],
        "severity": "critical",
        "actionTaken": sample["event"]["actionTaken"] + " 沙盒更新确认。",
    }
    update_response = client.put(
        f"/api/day-records/rule-events/{event_id}",
        params={"tradeDate": CONFIG.trade_date, "market": CONFIG.market},
        json=updated_payload,
    )
    assert_ok(update_response.status_code, update_response.text, "update sandbox rule event")
    updated_event = update_response.json()["day"]["events"][0]
    if updated_event.get("severity") != "critical":
        raise AssertionError("updated rule-event severity mismatch")
    if "沙盒更新确认" not in updated_event.get("actionTaken", ""):
        raise AssertionError("updated rule-event action note missing")

    stored_record = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_record:
        raise AssertionError("sandbox daily record was not written to SQLite")
    if len(stored_record.get("events", [])) != 1:
        raise AssertionError("expected 1 SQLite sandbox rule event after update")

    delete_response = client.delete(
        f"/api/day-records/rule-events/{event_id}",
        params={"tradeDate": CONFIG.trade_date, "market": CONFIG.market},
    )
    assert_ok(delete_response.status_code, delete_response.text, "delete sandbox rule event")
    if delete_response.json()["day"]["events"]:
        raise AssertionError("sandbox rule event was not deleted from response")

    stored_after_delete = dal.get_daily_record_by_date_market(CONFIG.trade_date, CONFIG.market)
    if not stored_after_delete:
        raise AssertionError("sandbox daily record missing after delete")
    if stored_after_delete.get("events"):
        raise AssertionError("sandbox rule event was not deleted from SQLite")


def create_rule_event(client: TestClient, event: dict) -> dict:
    payload = {
        **event,
        "tradeDate": CONFIG.trade_date,
        "market": CONFIG.market,
    }
    response = client.post("/api/day-records/rule-events", json=payload)
    assert_ok(response.status_code, response.text, "create sandbox rule event")
    return response.json()


if __name__ == "__main__":
    raise SystemExit(main())
