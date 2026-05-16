#!/usr/bin/env python3
"""Markdown record IO and canonicalization helpers for TopTrader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.utils import clean_text


def locate_yaml_block(content: str, heading: str) -> tuple[int, int]:
    marker = f"## {heading}"
    section_start = content.find(marker)
    if section_start == -1:
        raise ValueError(f"Missing section: {heading}")
    fence_start = content.find("```yaml", section_start)
    if fence_start == -1:
        raise ValueError(f"Missing yaml block for section: {heading}")
    block_start = fence_start + len("```yaml")
    fence_end = content.find("```", block_start)
    if fence_end == -1:
        raise ValueError(f"Unterminated yaml block for section: {heading}")
    return block_start, fence_end


def read_yaml_section(content: str, heading: str) -> Any:
    block_start, fence_end = locate_yaml_block(content, heading)
    block = content[block_start:fence_end].strip()
    if not block:
        return {}
    return yaml.safe_load(block) or {}


def read_optional_yaml_section(content: str, heading: str) -> Any:
    try:
        return read_yaml_section(content, heading)
    except ValueError:
        return {}


def render_yaml_section(heading: str, value: Any) -> str:
    dumped = yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    ).strip()
    return f"## {heading}\n```yaml\n{dumped}\n```"


def write_yaml_section(content: str, heading: str, value: Any) -> str:
    block_start, fence_end = locate_yaml_block(content, heading)
    dumped = render_yaml_section(heading, value).split("```yaml\n", 1)[1].rsplit("\n```", 1)[0]
    return content[:block_start] + "\n" + dumped + "\n" + content[fence_end:]


def write_yaml_section_or_insert(content: str, heading: str, value: Any, *, before_heading: str | None = None) -> str:
    try:
        return write_yaml_section(content, heading, value)
    except ValueError:
        section = render_yaml_section(heading, value)
        if before_heading:
            marker = f"## {before_heading}"
            marker_start = content.find(marker)
            if marker_start != -1:
                return content[:marker_start].rstrip() + "\n\n" + section + "\n\n" + content[marker_start:].lstrip()
        return content.rstrip() + "\n\n" + section + "\n"


def remove_markdown_section(content: str, heading: str) -> str:
    marker = f"## {heading}"
    section_start = content.find(marker)
    if section_start == -1:
        return content
    next_heading = content.find("\n## ", section_start + len(marker))
    prefix = content[:section_start].rstrip()
    if next_heading == -1:
        return prefix + "\n"
    suffix = content[next_heading + 1 :].lstrip()
    return prefix + "\n\n" + suffix


def as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def has_meaningful_trade_value(key: str, value: Any) -> bool:
    if key == "post_trade_emotion" and clean_text(value) == "unset":
        return False
    return has_value(value)


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value is True
    return clean_text(value) != ""


def is_filled_trade(trade: dict[str, Any]) -> bool:
    meaningful_keys = [
        "trade_time",
        "instrument_code",
        "certificate_side",
        "direction",
        "setup_type",
        "abc_grade",
        "setup_score",
        "entry_reason",
        "setup_validated",
        "entry_price",
        "stop_loss",
        "target_price",
        "position_size",
        "exit_time",
        "exit_price",
        "pnl_amount",
        "risk_reward_ratio",
        "exit_reason",
        "emotion_state",
        "pre_trade_emotion",
        "post_trade_emotion",
        "violation_note",
        "result",
        "screenshot_note",
        "review_note",
    ]
    return any(has_meaningful_trade_value(key, trade.get(key)) for key in meaningful_keys) or trade.get("rule_violation") is True


def is_filled_rule_event(event: dict[str, Any]) -> bool:
    meaningful_keys = [
        "time",
        "event_type",
        "severity",
        "trigger_reason",
        "action_taken",
        "follow_up_note",
        "linked_trade_id",
    ]
    return any(has_value(event.get(key)) for key in meaningful_keys)


def canonical_review(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_date": review.get("review_date"),
        "market": review.get("market"),
        "primary_instrument": review.get("primary_instrument"),
        "pnl": review.get("pnl") or review.get("pnl_result") or "",
        "trade_count": review.get("trade_count") if review.get("trade_count") is not None else review.get("total_trades"),
        "win_rate": review.get("win_rate") or "",
        "max_loss_trade": review.get("max_loss_trade") or "",
        "best_trade_note": review.get("best_trade_note") or review.get("main_good_action") or "",
        "worst_trade_note": review.get("worst_trade_note") or review.get("main_bad_action") or "",
        "market_issue": review.get("market_issue") or "",
        "execution_issue": review.get("execution_issue") or "",
        "emotion_issue": review.get("emotion_issue") or "",
        "risk_issue": review.get("risk_issue") or "",
        "setup_issue": review.get("setup_issue") or "",
        "next_day_one_fix": review.get("next_day_one_fix") or review.get("next_day_focus") or review.get("key_lesson") or "",
    }


def canonical_validation(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "trial_day_number": validation.get("trial_day_number"),
        "date": validation.get("date"),
        "market": validation.get("market"),
        "primary_instrument": validation.get("primary_instrument"),
        "pre_market_done": validation.get("pre_market_done") is True,
        "intraday_record_complete": validation.get("intraday_record_complete") is True,
        "post_market_review_done": validation.get("post_market_review_done") is True,
        "impulsive_trade_detected": validation.get("impulsive_trade_detected") is True,
        "no_stop_loss_trade_detected": validation.get("no_stop_loss_trade_detected") is True,
        "emotional_overtrade_detected": validation.get("emotional_overtrade_detected") is True,
        "no_trade_day": validation.get("no_trade_day") is True,
        "no_trade_note": validation.get("no_trade_note") or "",
        "main_issue_of_day": validation.get("main_issue_of_day") or validation.get("main_failure_point") or "",
        "main_improvement_of_day": validation.get("main_improvement_of_day") or validation.get("improvement_note") or "",
    }


def canonical_workbench(workbench: dict[str, Any]) -> dict[str, Any]:
    return {
        "trading_mode": clean_text(workbench.get("trading_mode")) or "hsi_bull_bear_certificate",
        "main_direction": clean_text(workbench.get("main_direction")) or "undecided",
        "upper_pressure": workbench.get("upper_pressure") or "",
        "lower_support": workbench.get("lower_support") or "",
        "pivot_level": workbench.get("pivot_level") or "",
        "current_state": clean_text(workbench.get("current_state")) or "unset",
        "post_market_summary": workbench.get("post_market_summary") or "",
        "capital_used": workbench.get("capital_used"),
        "profit_target_pct": workbench.get("profit_target_pct"),
        "hk_watchlist": workbench.get("hk_watchlist") or "",
        "us_watchlist": workbench.get("us_watchlist") or "",
    }


def canonical_playbook(playbook: dict[str, Any]) -> dict[str, Any]:
    return {
        "opening_plan": clean_text(playbook.get("opening_plan")),
        "focus_setup": clean_text(playbook.get("focus_setup")),
        "open_30_key_signal": playbook.get("open_30_key_signal") or "",
        "certificate_filter_note": playbook.get("certificate_filter_note") or "",
        "abnormal_plan": playbook.get("abnormal_plan") or "",
        "option_session_plan": clean_text(playbook.get("option_session_plan")),
        "focus_tickers": playbook.get("focus_tickers") or "",
        "option_focus_setup": clean_text(playbook.get("option_focus_setup")),
        "option_entry_signal": playbook.get("option_entry_signal") or "",
        "option_contract_filter": playbook.get("option_contract_filter") or "",
        "option_risk_plan": playbook.get("option_risk_plan") or "",
        "option_event_risk_plan": playbook.get("option_event_risk_plan") or "",
    }


def load_record(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    base = read_yaml_section(content, "Base Fields")
    pre_market = read_yaml_section(content, "Pre-Market Status").get("pre_market_status", {})
    workbench = canonical_workbench(
        read_optional_yaml_section(content, "Daily Workbench").get("daily_workbench", {})
    )
    hsi_playbook = read_optional_yaml_section(content, "HSI Playbook").get("hsi_playbook", {})
    us_options_playbook = read_optional_yaml_section(content, "US Options Playbook").get("us_options_playbook", {})
    playbook = canonical_playbook({**hsi_playbook, **us_options_playbook})
    trade_records = as_list(read_yaml_section(content, "Trade Record Container").get("trade_records", []))
    rule_events = as_list(read_yaml_section(content, "Rule Event Container").get("rule_events", []))
    review = canonical_review(read_yaml_section(content, "Review Record Container").get("review_record", {}))
    validation = canonical_validation(
        read_yaml_section(content, "Trial Validation Record Container").get("trial_validation_record", {})
    )
    filled_trades = [trade for trade in trade_records if is_filled_trade(trade)]
    filled_events = [event for event in rule_events if is_filled_rule_event(event)]
    return {
        "content": content,
        "base": base,
        "pre_market": pre_market,
        "workbench": workbench,
        "playbook": playbook,
        "trades": filled_trades,
        "events": filled_events,
        "review": review,
        "validation": validation,
    }
