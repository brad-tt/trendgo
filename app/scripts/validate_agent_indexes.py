#!/usr/bin/env python3
"""Validate Agent rule and knowledge indexes.

This script checks the Markdown indexes that feed core.agent_policy:

- ../trading-system/00-index/rules-catalog-v1.md
- ../toptrader-research/00-index/knowledge-router-v1.md
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import agent_policy  # noqa: E402


REQUIRED_RULE_IDS = {
    "PROCESS-DAILY-003",
    "PROCESS-DAILY-004",
    "RISK-SOFT-001",
    "RISK-SOFT-002",
    "SETUP-ABC-001",
    "SETUP-ABC-005",
    "SETUP-ABC-007",
    "SETUP-ABC-008",
}

REQUIRED_ROUTE_IDS = {
    "KR-001",
    "KR-002",
    "KR-003",
    "KR-010",
    "KR-012",
}

VALID_SEVERITIES = {"red", "yellow", "green"}


def main() -> int:
    errors: list[str] = []

    agent_policy.load_rule_catalog.cache_clear()
    agent_policy.load_knowledge_router.cache_clear()
    rules = agent_policy.load_rule_catalog()
    routes = agent_policy.load_knowledge_router()

    validate_rules(rules, errors)
    validate_routes(routes, errors)
    validate_aliases(routes, errors)

    if errors:
        print("Agent index validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Agent index validation passed.")
    print(f"- rules: {len(rules)}")
    print(f"- routes: {len(routes)}")
    print(f"- aliases: {len(agent_policy.ROUTE_ALIASES)}")
    return 0


def validate_rules(rules: dict[str, dict[str, str]], errors: list[str]) -> None:
    if len(rules) < 40:
        errors.append(f"expected at least 40 rules, found {len(rules)}")

    for rule_id in sorted(REQUIRED_RULE_IDS):
        if rule_id not in rules:
            errors.append(f"missing required rule: {rule_id}")

    for rule_id, rule in sorted(rules.items()):
        if rule.get("rule_id") != rule_id:
            errors.append(f"{rule_id}: rule_id field mismatch")
        if rule.get("severity") not in VALID_SEVERITIES:
            errors.append(f"{rule_id}: invalid severity {rule.get('severity')!r}")
        for field in ["trigger", "action", "source"]:
            if not rule.get(field):
                errors.append(f"{rule_id}: missing {field}")
        source = rule.get("source", "")
        if source and not (WORKSPACE_ROOT / "trading-system" / source).exists():
            errors.append(f"{rule_id}: source path does not exist: trading-system/{source}")


def validate_routes(routes: dict[str, dict[str, str]], errors: list[str]) -> None:
    if len(routes) < 15:
        errors.append(f"expected at least 15 routes, found {len(routes)}")

    for route_id in sorted(REQUIRED_ROUTE_IDS):
        if route_id not in routes:
            errors.append(f"missing required route: {route_id}")

    for route_id, route in sorted(routes.items()):
        if route.get("route_id") != route_id:
            errors.append(f"{route_id}: route_id field mismatch")
        for field in ["distortion_type", "trigger_phrases", "playbook", "capability_pack", "first_action"]:
            if not route.get(field):
                errors.append(f"{route_id}: missing {field}")
        for field in ["playbook", "capability_pack"]:
            path = route.get(field, "")
            if path and not (WORKSPACE_ROOT / path).exists():
                errors.append(f"{route_id}: {field} path does not exist: {path}")


def validate_aliases(routes: dict[str, dict[str, str]], errors: list[str]) -> None:
    for alias, route_id in sorted(agent_policy.ROUTE_ALIASES.items()):
        if route_id not in routes:
            errors.append(f"alias {alias!r} points to missing route {route_id}")


if __name__ == "__main__":
    raise SystemExit(main())
