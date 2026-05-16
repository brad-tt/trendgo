#!/usr/bin/env python3
"""Dry-run replay for Agent trade lifecycle samples.

This validates policy and field-normalization behavior without writing to
SQLite or daily record files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import local_web  # noqa: E402
from core import agent_policy  # noqa: E402

SAMPLES_PATH = Path(__file__).with_name("agent_trade_lifecycle_samples.json")


def main() -> int:
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    replay_open_trades(samples.get("openTrades", []), failures)
    replay_close_trades(samples.get("closeTrades", []), failures)
    replay_rule_events(samples.get("ruleEvents", []), failures)
    replay_reviews(samples.get("reviews", []), failures)

    if failures:
        print("\nAgent lifecycle sample replay failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    total = sum(len(samples.get(key, [])) for key in ["openTrades", "closeTrades", "ruleEvents", "reviews"])
    print("\nAgent lifecycle sample replay passed.")
    print(f"- samples: {total}")
    return 0


def replay_open_trades(samples: list[dict[str, Any]], failures: list[str]) -> None:
    print("Open trades:")
    for sample in samples:
        name = sample["name"]
        trade = camel_to_snake_dict(sample["trade"])
        rule_hits = agent_policy.build_rule_hits_for_trade(trade)
        routes = agent_policy.build_knowledge_routes_for_trade(
            trade=trade,
            raw_note=sample.get("rawNote", ""),
            agent_note=sample.get("agentNote", ""),
            suspected_distortions=sample.get("suspectedDistortions", []),
        )
        rule_ids = {item["rule_id"] for item in rule_hits}
        route_ids = {item["route_id"] for item in routes}
        print(f"  {name}: rules={format_ids(rule_ids)} routes={format_ids(route_ids)}")
        assert_expected(name, "rules", sample.get("expectedRuleIds", []), rule_ids, failures)
        assert_expected(name, "routes", sample.get("expectedRouteIds", []), route_ids, failures)


def replay_close_trades(samples: list[dict[str, Any]], failures: list[str]) -> None:
    print("Close trades:")
    for sample in samples:
        name = sample["name"]
        existing = camel_to_snake_dict(sample["existingTrade"])
        exit_payload = camel_to_snake_dict(sample["exit"])
        direction = existing["direction"]
        entry_price = existing["entry_price"]
        exit_price = exit_payload["exit_price"]
        position_size = existing["position_size"]
        result = local_web.infer_trade_result(direction, entry_price, exit_price)
        pnl_amount = local_web.calculate_trade_pnl_amount(direction, entry_price, exit_price, position_size)
        print(f"  {name}: result={result} pnl={pnl_amount}")
        if result != sample["expectedResult"]:
            failures.append(f"{name}: expected result {sample['expectedResult']!r}, got {result!r}")
        if round(float(pnl_amount or 0), 6) != round(float(sample["expectedPnlAmount"]), 6):
            failures.append(f"{name}: expected pnl {sample['expectedPnlAmount']!r}, got {pnl_amount!r}")
        for field in ["exit_time", "exit_reason", "post_trade_emotion"]:
            if not exit_payload.get(field):
                failures.append(f"{name}: missing close field {field}")


def replay_rule_events(samples: list[dict[str, Any]], failures: list[str]) -> None:
    print("Rule events:")
    for sample in samples:
        name = sample["name"]
        event = camel_to_snake_dict(sample["event"])
        text = " ".join(str(value) for value in event.values())
        rule_ids = detect_rule_ids_from_text(text)
        route_ids = detect_route_ids_from_text(text)
        print(f"  {name}: rules={format_ids(rule_ids)} routes={format_ids(route_ids)}")
        assert_expected(name, "rules", sample.get("expectedRuleIds", []), rule_ids, failures)
        assert_expected(name, "routes", sample.get("expectedRouteIds", []), route_ids, failures)
        for field in ["event_time", "event_type", "severity", "trigger_reason", "action_taken"]:
            if not event.get(field):
                failures.append(f"{name}: missing event field {field}")


def replay_reviews(samples: list[dict[str, Any]], failures: list[str]) -> None:
    print("Reviews:")
    for sample in samples:
        name = sample["name"]
        review = camel_to_snake_dict(sample["review"])
        text = " ".join(str(value) for value in review.values())
        found_keywords = {keyword for keyword in sample.get("expectedKeywords", []) if keyword.lower() in text.lower()}
        print(f"  {name}: keywords={format_ids(found_keywords)}")
        assert_expected(name, "keywords", sample.get("expectedKeywords", []), found_keywords, failures)
        for field in ["pnl", "trade_count", "execution_issue", "emotion_issue", "risk_issue", "next_day_one_fix"]:
            if review.get(field) in {"", None}:
                failures.append(f"{name}: missing review field {field}")


def detect_rule_ids_from_text(text: str) -> set[str]:
    rules = set()
    lowered = text.lower()
    for rule_id, rule in agent_policy.load_rule_catalog().items():
        if rule_id.lower() in lowered:
            rules.add(rule_id)
    return rules


def detect_route_ids_from_text(text: str) -> set[str]:
    routes = set()
    lowered = text.lower()
    for route_id in agent_policy.load_knowledge_router():
        if route_id.lower() in lowered:
            routes.add(route_id)
    for alias, route_id in agent_policy.ROUTE_ALIASES.items():
        if alias in lowered:
            routes.add(route_id)
    return routes


def assert_expected(name: str, label: str, expected: list[str], actual: set[str], failures: list[str]) -> None:
    missing = set(expected) - actual
    if missing:
        failures.append(f"{name}: missing {label} {sorted(missing)}")


def format_ids(values: set[str]) -> str:
    return ", ".join(sorted(values)) or "-"


def camel_to_snake_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {camel_to_snake(key): value for key, value in data.items()}


def camel_to_snake(value: str) -> str:
    chars: list[str] = []
    for char in value:
        if char.isupper():
            chars.append("_")
            chars.append(char.lower())
        else:
            chars.append(char)
    return "".join(chars).lstrip("_")


if __name__ == "__main__":
    raise SystemExit(main())
