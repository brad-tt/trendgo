#!/usr/bin/env python3
"""Generate a TopTrader daily record container for a trial day."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

DEFAULT_MARKET = "HK"
DEFAULT_INSTRUMENT = "HSI bull/bear certificate"
TRADING_MODE_OPTIONS = ["hsi_bull_bear_certificate", "us_stock_options"]
MODE_DEFAULTS = {
    "hsi_bull_bear_certificate": {
        "market": "HK",
        "instrument": "HSI bull/bear certificate",
        "instrument_type": "bull_bear_certificate",
        "underlying": "HSI",
        "side_comment": "bull / bear",
    },
    "us_stock_options": {
        "market": "US",
        "instrument": "US stock options",
        "instrument_type": "stock_option",
        "underlying": "TSLA",
        "side_comment": "call / put",
    },
}
DEFAULT_OPERATOR = "Joe 爸"
DEFAULT_RECORD_OWNER = "战神"
DEFAULT_OUTPUT_DIR = Path("05-daily-ops/records")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a daily TopTrader record container markdown file."
    )
    parser.add_argument(
        "day",
        type=int,
        help="Trial day number, e.g. 1 for Day 1.",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Trade date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--trading-mode",
        choices=TRADING_MODE_OPTIONS,
        default="hsi_bull_bear_certificate",
        help="Main trading mode for the day. Defaults to hsi_bull_bear_certificate.",
    )
    parser.add_argument(
        "--market",
        default=None,
        help=f"Market code. Defaults by --trading-mode.",
    )
    parser.add_argument(
        "--instrument",
        default=None,
        help="Primary instrument. Defaults by --trading-mode.",
    )
    parser.add_argument(
        "--operator",
        default=DEFAULT_OPERATOR,
        help=f"Trading operator. Defaults to {DEFAULT_OPERATOR}.",
    )
    parser.add_argument(
        "--record-owner",
        default=DEFAULT_RECORD_OWNER,
        help=f"Record owner. Defaults to {DEFAULT_RECORD_OWNER}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.day < 1:
        raise SystemExit("day must be a positive integer")
    try:
        date.fromisoformat(args.date)
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD format") from exc
    defaults = MODE_DEFAULTS[args.trading_mode]
    args.market = args.market or defaults["market"]
    args.instrument = args.instrument or defaults["instrument"]


def output_path(output_dir: Path, day: int, trade_date: str) -> Path:
    del day
    return output_dir / f"{trade_date}-record-container.md"


def render_container(
    *,
    day: int,
    trade_date: str,
    trading_mode: str,
    market: str,
    instrument: str,
    operator: str,
    record_owner: str,
) -> str:
    trade_id = f"TT-{trade_date}-001"
    event_id = f"RE-{trade_date}-001"
    mode_defaults = MODE_DEFAULTS[trading_mode]
    instrument_type = mode_defaults["instrument_type"]
    underlying = mode_defaults["underlying"]
    side_comment = mode_defaults["side_comment"]
    if trading_mode == "us_stock_options":
        playbook_section = """## US Options Playbook
```yaml
us_options_playbook:
  option_session_plan: ""
  focus_tickers: ""
  option_focus_setup: ""
  option_entry_signal: ""
  option_contract_filter: ""
  option_risk_plan: ""
  option_event_risk_plan: ""
```
"""
    else:
        playbook_section = """## HSI Playbook
```yaml
hsi_playbook:
  opening_plan: ""
  focus_setup: ""
  open_30_key_signal: ""
  certificate_filter_note: ""
  abnormal_plan: ""
```
"""

    return f"""# TopTrader {trade_date} Record Container

## Naming Convention
- File: `{trade_date}-record-container.md`
- Trade ID: `{trade_id}` then increment the final sequence per trade
- Rule Event ID: `{event_id}` then increment the final sequence per event

## Base Fields
```yaml
day_number: {day}
trade_date: {trade_date}
market: {market}
primary_instrument: {instrument}
record_mode: production
operator: {operator}
record_owner: {record_owner}
```

## Pre-Market Status
```yaml
pre_market_status:
  trading_today: true
  state: normal   # normal / tired / irritated / sleep_poor / unstable / other
  follow_normal_rules: true
  key_reminder: ""
  note: ""
```

## Daily Workbench
```yaml
daily_workbench:
  trading_mode: {trading_mode}
  main_direction: undecided
  upper_pressure: ""
  lower_support: ""
  pivot_level: ""
  current_state: unset
  post_market_summary: ""
  capital_used: null
  profit_target_pct: null
  hk_watchlist: ""
  us_watchlist: ""
```

{playbook_section}

## Trade Record Container
Add one item per trade.

```yaml
trade_records:
  - trade_id: {trade_id}
    trade_date: {trade_date}
    trade_time: ""
    market: {market}
    instrument_code: ""
    certificate_side: ""   # {side_comment}
    instrument_type: {instrument_type}
    underlying: {underlying}
    direction: ""          # long / short
    session_window: ""     # opening_30m / mid_session / late_session
    setup_type: ""         # opening_breakout / pullback_reclaim / orb_continuation / vwap_reclaim / trend_pullback / support_reversal / failed_breakdown / clear_observe / false_breakout_chase / reverse_after_stop / emotional_trade / revenge_trade / itchy_hand_trade / profit_giveback / recovery_after_losing_streak / iv_chase / other
    abc_grade: ""          # A / B / C
    setup_score: null
    entry_reason: ""
    setup_validated: null
    direction_clear: null
    location_ok: null
    confirmation_ok: null
    risk_clear: null
    certificate_filter_passed: null
    abnormal_scenario: none   # none / open_whipsaw / stop_then_reverse / profit_giveback / low_quality_lure / iv_spike / spread_widen / news_event / other
    entry_price: null
    stop_loss: null
    target_price: null
    position_size: ""
    exit_time: ""
    exit_price: null
    pnl_amount: null
    risk_reward_ratio: null
    exit_reason: ""
    followed_plan: true
    emotion_state: ""      # stable / anxious / revenge / impulsive
    pre_trade_emotion: ""  # stable / rushed / defiant / fomo / recover_loss
    post_trade_emotion: unset  # unset / stable / satisfied / regret / rushed / defiant
    rule_violation: false
    violation_note: ""
    result: ""             # win / loss / breakeven
    screenshot_note: ""
    review_note: ""
```

## Rule Event Container
Only fill when a discipline, risk, or emotion event occurs.

```yaml
rule_events:
  - event_id: {event_id}
    date: {trade_date}
    time: ""
    market: {market}
    event_type: ""         # rule_violation / emotion_trigger / forced_pause / forced_stop / overtrade_signal
    severity: ""           # warning / stop / critical
    trigger_reason: ""
    action_taken: ""
    follow_up_note: ""
    linked_trade_id: ""
```

## Review Record Container
Fill one item after market close.

```yaml
review_record:
  review_date: {trade_date}
  market: {market}
  primary_instrument: {instrument}
  pnl: ""
  trade_count: null
  win_rate: ""
  max_loss_trade: ""
  best_trade_note: ""
  worst_trade_note: ""
  market_issue: ""
  execution_issue: ""
  emotion_issue: ""
  risk_issue: ""
  setup_issue: ""
  next_day_one_fix: ""
```

## Trial Validation Record Container
Fill after the daily review.

```yaml
trial_validation_record:
  trial_day_number: {day}
  date: {trade_date}
  market: {market}
  primary_instrument: {instrument}
  pre_market_done: false
  intraday_record_complete: false
  post_market_review_done: false
  impulsive_trade_detected: false
  no_stop_loss_trade_detected: false
  emotional_overtrade_detected: false
  no_trade_day: false
  no_trade_note: ""
  main_issue_of_day: ""
  main_improvement_of_day: ""
```

## Closeout Order
1. Complete `trade_records`
2. Complete `rule_events`
3. Complete `review_record`
4. Complete `trial_validation_record`
"""


def main() -> None:
    args = parse_args()
    validate_args(args)

    path = output_path(args.output_dir, args.day, args.date)
    if path.exists() and not args.force:
        raise SystemExit(f"output file already exists: {path}; use --force to overwrite")

    content = render_container(
        day=args.day,
        trade_date=args.date,
        trading_mode=args.trading_mode,
        market=args.market,
        instrument=args.instrument,
        operator=args.operator,
        record_owner=args.record_owner,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
