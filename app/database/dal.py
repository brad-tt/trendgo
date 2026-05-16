#!/usr/bin/env python3
"""SQLite data access layer for TopTrader."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from core.utils import clean_text, meaningful_text, to_bool_int, to_float, to_int

DB_PATH = Path(__file__).resolve().parent / "toptrader.db"
REVIEW_TEXT_FIELDS = [
    "best_trade_note",
    "worst_trade_note",
    "execution_issue",
    "emotion_issue",
    "risk_issue",
    "next_day_one_fix",
]


def normalize_pnl(value: Any) -> tuple[str, float | None]:
    text = clean_text(value)
    return text, to_float(text)


def normalize_source_path(value: Any) -> str:
    text = clean_text(value)
    if not text:
        raise ValueError("source_record_path is required.")
    path = Path(text)
    return str(path)


def sqlite_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def register_functions(conn: sqlite3.Connection) -> None:
    conn.create_function("meaningful_text", 1, meaningful_text)


def ensure_agent_observation_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_observation (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          daily_record_id INTEGER NOT NULL,
          observation_id TEXT NOT NULL,
          source_order INTEGER NOT NULL DEFAULT 0,
          trade_date TEXT NOT NULL,
          market TEXT NOT NULL,
          linked_trade_id TEXT NOT NULL DEFAULT '',
          linked_event_id TEXT NOT NULL DEFAULT '',
          observation_type TEXT NOT NULL DEFAULT '',
          severity TEXT NOT NULL DEFAULT 'info',
          source TEXT NOT NULL DEFAULT 'agent_question',
          summary TEXT NOT NULL DEFAULT '',
          evidence TEXT NOT NULL DEFAULT '',
          user_response TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'open',
          review_required INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (daily_record_id) REFERENCES daily_record(id) ON DELETE CASCADE
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_observation_daily_observation_id
          ON agent_observation(daily_record_id, observation_id);
        CREATE INDEX IF NOT EXISTS idx_agent_observation_daily_record_id
          ON agent_observation(daily_record_id);
        CREATE INDEX IF NOT EXISTS idx_agent_observation_trade_date
          ON agent_observation(trade_date);
        CREATE INDEX IF NOT EXISTS idx_agent_observation_linked_trade_id
          ON agent_observation(linked_trade_id);
        CREATE INDEX IF NOT EXISTS idx_agent_observation_type
          ON agent_observation(observation_type);
        CREATE INDEX IF NOT EXISTS idx_agent_observation_status
          ON agent_observation(status);
        CREATE INDEX IF NOT EXISTS idx_agent_observation_severity
          ON agent_observation(severity);
        """
    )


def get_db_path(db_path: Path | None = None) -> Path:
    path = (db_path or DB_PATH).resolve()
    if not path.exists():
        raise FileNotFoundError(f"TopTrader SQLite database not found: {path}")
    return path


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = get_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    register_functions(conn)
    ensure_agent_observation_schema(conn)
    return conn


def ensure_workspace_state_row(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO workspace_state (id, current_market, current_trade_date, theme, updated_at)
        VALUES (1, 'HK', DATE('now'), 'dark', CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO NOTHING
        """
    )


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        ensure_workspace_state_row(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def resolve_daily_record_id(
    conn: sqlite3.Connection,
    *,
    daily_record_id: int | None = None,
    trial_day_number: int | None = None,
    source_record_path: str | None = None,
) -> int:
    if daily_record_id is not None:
        return daily_record_id
    if trial_day_number is not None:
        row = conn.execute(
            "SELECT id FROM daily_record WHERE trial_day_number = ?",
            (trial_day_number,),
        ).fetchone()
        if row:
            return int(row["id"])
    if source_record_path:
        row = conn.execute(
            "SELECT id FROM daily_record WHERE source_record_path = ?",
            (normalize_source_path(source_record_path),),
        ).fetchone()
        if row:
            return int(row["id"])
    raise ValueError("Unable to resolve daily_record_id.")


def extract_sections(record_dict: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = record_dict.get("base", {})
    pre_market = record_dict.get("pre_market", record_dict.get("pre_market_status", {}))
    workbench = record_dict.get("workbench", record_dict.get("daily_workbench", {}))
    playbook = record_dict.get("playbook", {})
    return base, pre_market, workbench, playbook


def upsert_daily_record_row(
    conn: sqlite3.Connection,
    *,
    base: dict[str, Any],
    pre_market: dict[str, Any],
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    source_record_path: str,
) -> int:
    params = {
        "trial_day_number": to_int(base.get("day_number")),
        "trade_date": clean_text(base.get("trade_date")),
        "market": clean_text(base.get("market")),
        "primary_instrument": clean_text(base.get("primary_instrument")),
        "trial_mode": clean_text(base.get("record_mode") or base.get("trial_mode")) or "production",
        "operator": clean_text(base.get("operator")),
        "record_owner": clean_text(base.get("record_owner")),
        "source_record_path": normalize_source_path(source_record_path),
        "trading_today": to_bool_int(pre_market.get("trading_today", True)),
        "pre_market_state": clean_text(pre_market.get("state")) or "normal",
        "follow_normal_rules": to_bool_int(pre_market.get("follow_normal_rules", True)),
        "key_reminder": clean_text(pre_market.get("key_reminder")),
        "pre_market_note": clean_text(pre_market.get("note")),
        "trading_mode": clean_text(workbench.get("trading_mode")) or "hsi_bull_bear_certificate",
        "main_direction": clean_text(workbench.get("main_direction")) or "undecided",
        "upper_pressure": clean_text(workbench.get("upper_pressure")),
        "lower_support": clean_text(workbench.get("lower_support")),
        "pivot_level": clean_text(workbench.get("pivot_level")),
        "no_trade_scenarios": "",
        "hard_stop_conditions": "",
        "current_state": clean_text(workbench.get("current_state")) or "unset",
        "post_market_summary": clean_text(workbench.get("post_market_summary")),
        "capital_used": to_float(workbench.get("capital_used")),
        "profit_target_pct": to_float(workbench.get("profit_target_pct")),
        "hk_watchlist": clean_text(workbench.get("hk_watchlist")),
        "us_watchlist": clean_text(workbench.get("us_watchlist")),
        "opening_plan": clean_text(playbook.get("opening_plan")),
        "focus_setup": clean_text(playbook.get("focus_setup")),
        "open_30_key_signal": clean_text(playbook.get("open_30_key_signal")),
        "certificate_filter_note": clean_text(playbook.get("certificate_filter_note")),
        "abnormal_plan": clean_text(playbook.get("abnormal_plan")),
        "option_session_plan": clean_text(playbook.get("option_session_plan")),
        "focus_tickers": clean_text(playbook.get("focus_tickers")),
        "option_focus_setup": clean_text(playbook.get("option_focus_setup")),
        "option_entry_signal": clean_text(playbook.get("option_entry_signal")),
        "option_contract_filter": clean_text(playbook.get("option_contract_filter")),
        "option_risk_plan": clean_text(playbook.get("option_risk_plan")),
        "option_event_risk_plan": clean_text(playbook.get("option_event_risk_plan")),
    }
    conn.execute(
        """
        INSERT INTO daily_record (
          trial_day_number, trade_date, market, primary_instrument, trial_mode, operator, record_owner, source_record_path,
          trading_today, pre_market_state, follow_normal_rules, key_reminder, pre_market_note,
          trading_mode, main_direction, upper_pressure, lower_support, pivot_level, no_trade_scenarios,
          hard_stop_conditions, current_state, post_market_summary, capital_used, profit_target_pct, hk_watchlist, us_watchlist,
          opening_plan, focus_setup, open_30_key_signal, certificate_filter_note, abnormal_plan,
          option_session_plan, focus_tickers, option_focus_setup, option_entry_signal, option_contract_filter,
          option_risk_plan, option_event_risk_plan, updated_at
        ) VALUES (
          :trial_day_number, :trade_date, :market, :primary_instrument, :trial_mode, :operator, :record_owner, :source_record_path,
          :trading_today, :pre_market_state, :follow_normal_rules, :key_reminder, :pre_market_note,
          :trading_mode, :main_direction, :upper_pressure, :lower_support, :pivot_level, :no_trade_scenarios,
          :hard_stop_conditions, :current_state, :post_market_summary, :capital_used, :profit_target_pct, :hk_watchlist, :us_watchlist,
          :opening_plan, :focus_setup, :open_30_key_signal, :certificate_filter_note, :abnormal_plan,
          :option_session_plan, :focus_tickers, :option_focus_setup, :option_entry_signal, :option_contract_filter,
          :option_risk_plan, :option_event_risk_plan, CURRENT_TIMESTAMP
        )
        ON CONFLICT(trade_date, market) DO UPDATE SET
          trial_day_number = excluded.trial_day_number,
          primary_instrument = excluded.primary_instrument,
          trial_mode = excluded.trial_mode,
          operator = excluded.operator,
          record_owner = excluded.record_owner,
          source_record_path = excluded.source_record_path,
          trading_today = excluded.trading_today,
          pre_market_state = excluded.pre_market_state,
          follow_normal_rules = excluded.follow_normal_rules,
          key_reminder = excluded.key_reminder,
          pre_market_note = excluded.pre_market_note,
          trading_mode = excluded.trading_mode,
          main_direction = excluded.main_direction,
          upper_pressure = excluded.upper_pressure,
          lower_support = excluded.lower_support,
          pivot_level = excluded.pivot_level,
          no_trade_scenarios = excluded.no_trade_scenarios,
          hard_stop_conditions = excluded.hard_stop_conditions,
          current_state = excluded.current_state,
          post_market_summary = excluded.post_market_summary,
          capital_used = excluded.capital_used,
          profit_target_pct = excluded.profit_target_pct,
          hk_watchlist = excluded.hk_watchlist,
          us_watchlist = excluded.us_watchlist,
          opening_plan = excluded.opening_plan,
          focus_setup = excluded.focus_setup,
          open_30_key_signal = excluded.open_30_key_signal,
          certificate_filter_note = excluded.certificate_filter_note,
          abnormal_plan = excluded.abnormal_plan,
          option_session_plan = excluded.option_session_plan,
          focus_tickers = excluded.focus_tickers,
          option_focus_setup = excluded.option_focus_setup,
          option_entry_signal = excluded.option_entry_signal,
          option_contract_filter = excluded.option_contract_filter,
          option_risk_plan = excluded.option_risk_plan,
          option_event_risk_plan = excluded.option_event_risk_plan,
          updated_at = CURRENT_TIMESTAMP
        """,
        params,
    )
    row = conn.execute(
        "SELECT id FROM daily_record WHERE trade_date = ? AND market = ?",
        (params["trade_date"], params["market"]),
    ).fetchone()
    if row is None:
        raise ValueError("Unable to resolve daily_record_id after upsert.")
    return int(row["id"])


def save_daily_record(
    record_dict: dict[str, Any],
    *,
    source_record_path: str | None = None,
    db_path: Path | None = None,
) -> int:
    base, pre_market, workbench, playbook = extract_sections(record_dict)
    resolved_path = source_record_path or record_dict.get("source_record_path")
    with get_connection(db_path) as conn:
        return upsert_daily_record_row(
            conn,
            base=base,
            pre_market=pre_market,
            workbench=workbench,
            playbook=playbook,
            source_record_path=clean_text(resolved_path),
        )


def upsert_trade_row(
    conn: sqlite3.Connection,
    *,
    daily_record_id: int,
    trade_dict: dict[str, Any],
    source_order: int = 0,
) -> int:
    params = {
        "daily_record_id": daily_record_id,
        "trade_id": clean_text(trade_dict.get("trade_id")),
        "source_order": source_order,
        "trade_date": clean_text(trade_dict.get("trade_date")),
        "trade_time": clean_text(trade_dict.get("trade_time")),
        "market": clean_text(trade_dict.get("market")),
        "instrument_code": clean_text(trade_dict.get("instrument_code")),
        "certificate_side": clean_text(trade_dict.get("certificate_side")),
        "instrument_type": clean_text(trade_dict.get("instrument_type")),
        "underlying": clean_text(trade_dict.get("underlying")),
        "direction": clean_text(trade_dict.get("direction")),
        "session_window": clean_text(trade_dict.get("session_window")),
        "setup_type": clean_text(trade_dict.get("setup_type")),
        "abc_grade": clean_text(trade_dict.get("abc_grade")),
        "setup_score": to_float(trade_dict.get("setup_score")),
        "entry_reason": clean_text(trade_dict.get("entry_reason")),
        "setup_validated": None if trade_dict.get("setup_validated") is None else to_bool_int(trade_dict.get("setup_validated")),
        "direction_clear": None if trade_dict.get("direction_clear") is None else to_bool_int(trade_dict.get("direction_clear")),
        "location_ok": None if trade_dict.get("location_ok") is None else to_bool_int(trade_dict.get("location_ok")),
        "confirmation_ok": None if trade_dict.get("confirmation_ok") is None else to_bool_int(trade_dict.get("confirmation_ok")),
        "risk_clear": None if trade_dict.get("risk_clear") is None else to_bool_int(trade_dict.get("risk_clear")),
        "certificate_filter_passed": None if trade_dict.get("certificate_filter_passed") is None else to_bool_int(trade_dict.get("certificate_filter_passed")),
        "abnormal_scenario": clean_text(trade_dict.get("abnormal_scenario")) or "none",
        "entry_price": to_float(trade_dict.get("entry_price")),
        "stop_loss": to_float(trade_dict.get("stop_loss")),
        "target_price": to_float(trade_dict.get("target_price")),
        "position_size": clean_text(trade_dict.get("position_size")),
        "exit_time": clean_text(trade_dict.get("exit_time")),
        "exit_price": to_float(trade_dict.get("exit_price")),
        "pnl_amount": to_float(trade_dict.get("pnl_amount")),
        "risk_reward_ratio": to_float(trade_dict.get("risk_reward_ratio")),
        "exit_reason": clean_text(trade_dict.get("exit_reason")),
        "followed_plan": to_bool_int(trade_dict.get("followed_plan")),
        "emotion_state": clean_text(trade_dict.get("emotion_state")),
        "pre_trade_emotion": clean_text(trade_dict.get("pre_trade_emotion")),
        "post_trade_emotion": clean_text(trade_dict.get("post_trade_emotion")) or "unset",
        "rule_violation": to_bool_int(trade_dict.get("rule_violation")),
        "violation_note": clean_text(trade_dict.get("violation_note")),
        "result": clean_text(trade_dict.get("result")),
        "screenshot_note": clean_text(trade_dict.get("screenshot_note")),
        "review_note": clean_text(trade_dict.get("review_note")),
    }
    conn.execute(
        """
        INSERT INTO trade_record (
          daily_record_id, trade_id, source_order, trade_date, trade_time, market, instrument_code,
          certificate_side, instrument_type, underlying, direction, session_window, setup_type, abc_grade,
          setup_score, entry_reason, setup_validated, direction_clear, location_ok, confirmation_ok, risk_clear,
          certificate_filter_passed, abnormal_scenario, entry_price, stop_loss, target_price, position_size,
          exit_time, exit_price, pnl_amount, risk_reward_ratio, exit_reason, followed_plan, emotion_state,
          pre_trade_emotion, post_trade_emotion, rule_violation, violation_note, result, screenshot_note,
          review_note, updated_at
        ) VALUES (
          :daily_record_id, :trade_id, :source_order, :trade_date, :trade_time, :market, :instrument_code,
          :certificate_side, :instrument_type, :underlying, :direction, :session_window, :setup_type, :abc_grade,
          :setup_score, :entry_reason, :setup_validated, :direction_clear, :location_ok, :confirmation_ok, :risk_clear,
          :certificate_filter_passed, :abnormal_scenario, :entry_price, :stop_loss, :target_price, :position_size,
          :exit_time, :exit_price, :pnl_amount, :risk_reward_ratio, :exit_reason, :followed_plan, :emotion_state,
          :pre_trade_emotion, :post_trade_emotion, :rule_violation, :violation_note, :result, :screenshot_note,
          :review_note, CURRENT_TIMESTAMP
        )
        ON CONFLICT(daily_record_id, trade_id) DO UPDATE SET
          daily_record_id = excluded.daily_record_id,
          source_order = excluded.source_order,
          trade_date = excluded.trade_date,
          trade_time = excluded.trade_time,
          market = excluded.market,
          instrument_code = excluded.instrument_code,
          certificate_side = excluded.certificate_side,
          instrument_type = excluded.instrument_type,
          underlying = excluded.underlying,
          direction = excluded.direction,
          session_window = excluded.session_window,
          setup_type = excluded.setup_type,
          abc_grade = excluded.abc_grade,
          setup_score = excluded.setup_score,
          entry_reason = excluded.entry_reason,
          setup_validated = excluded.setup_validated,
          direction_clear = excluded.direction_clear,
          location_ok = excluded.location_ok,
          confirmation_ok = excluded.confirmation_ok,
          risk_clear = excluded.risk_clear,
          certificate_filter_passed = excluded.certificate_filter_passed,
          abnormal_scenario = excluded.abnormal_scenario,
          entry_price = excluded.entry_price,
          stop_loss = excluded.stop_loss,
          target_price = excluded.target_price,
          position_size = excluded.position_size,
          exit_time = excluded.exit_time,
          exit_price = excluded.exit_price,
          pnl_amount = excluded.pnl_amount,
          risk_reward_ratio = excluded.risk_reward_ratio,
          exit_reason = excluded.exit_reason,
          followed_plan = excluded.followed_plan,
          emotion_state = excluded.emotion_state,
          pre_trade_emotion = excluded.pre_trade_emotion,
          post_trade_emotion = excluded.post_trade_emotion,
          rule_violation = excluded.rule_violation,
          violation_note = excluded.violation_note,
          result = excluded.result,
          screenshot_note = excluded.screenshot_note,
          review_note = excluded.review_note,
          updated_at = CURRENT_TIMESTAMP
        """,
        params,
    )
    row = conn.execute(
        "SELECT id FROM trade_record WHERE daily_record_id = ? AND trade_id = ?",
        (daily_record_id, params["trade_id"]),
    ).fetchone()
    return int(row["id"])


def replace_trades(
    *,
    trial_day_number: int | None = None,
    daily_record_id: int | None = None,
    source_record_path: str | None = None,
    trades: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=daily_record_id,
            trial_day_number=trial_day_number,
            source_record_path=source_record_path,
        )
        conn.execute("DELETE FROM trade_record WHERE daily_record_id = ?", (resolved_id,))
        for index, trade in enumerate(trades, start=1):
            upsert_trade_row(conn, daily_record_id=resolved_id, trade_dict=trade, source_order=index)
        return resolved_id


def insert_trade(
    trade_dict: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> int:
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=to_int(trade_dict.get("daily_record_id")),
            trial_day_number=to_int(trade_dict.get("trial_day_number")),
            source_record_path=clean_text(trade_dict.get("source_record_path")),
        )
        source_order = to_int(trade_dict.get("source_order")) or 0
        return upsert_trade_row(conn, daily_record_id=resolved_id, trade_dict=trade_dict, source_order=source_order)


def upsert_rule_event_row(
    conn: sqlite3.Connection,
    *,
    daily_record_id: int,
    event_dict: dict[str, Any],
    source_order: int = 0,
) -> int:
    params = {
        "daily_record_id": daily_record_id,
        "event_id": clean_text(event_dict.get("event_id")),
        "source_order": source_order,
        "event_date": clean_text(event_dict.get("date") or event_dict.get("event_date")),
        "event_time": clean_text(event_dict.get("time") or event_dict.get("event_time")),
        "market": clean_text(event_dict.get("market")),
        "event_type": clean_text(event_dict.get("event_type")),
        "severity": clean_text(event_dict.get("severity")),
        "trigger_reason": clean_text(event_dict.get("trigger_reason")),
        "action_taken": clean_text(event_dict.get("action_taken")),
        "follow_up_note": clean_text(event_dict.get("follow_up_note")),
        "linked_trade_id": clean_text(event_dict.get("linked_trade_id")),
    }
    conn.execute(
        """
        INSERT INTO rule_event (
          daily_record_id, event_id, source_order, event_date, event_time, market, event_type,
          severity, trigger_reason, action_taken, follow_up_note, linked_trade_id, updated_at
        ) VALUES (
          :daily_record_id, :event_id, :source_order, :event_date, :event_time, :market, :event_type,
          :severity, :trigger_reason, :action_taken, :follow_up_note, :linked_trade_id, CURRENT_TIMESTAMP
        )
        ON CONFLICT(daily_record_id, event_id) DO UPDATE SET
          daily_record_id = excluded.daily_record_id,
          source_order = excluded.source_order,
          event_date = excluded.event_date,
          event_time = excluded.event_time,
          market = excluded.market,
          event_type = excluded.event_type,
          severity = excluded.severity,
          trigger_reason = excluded.trigger_reason,
          action_taken = excluded.action_taken,
          follow_up_note = excluded.follow_up_note,
          linked_trade_id = excluded.linked_trade_id,
          updated_at = CURRENT_TIMESTAMP
        """,
        params,
    )
    row = conn.execute(
        "SELECT id FROM rule_event WHERE daily_record_id = ? AND event_id = ?",
        (daily_record_id, params["event_id"]),
    ).fetchone()
    return int(row["id"])


def replace_rule_events(
    *,
    trial_day_number: int | None = None,
    daily_record_id: int | None = None,
    source_record_path: str | None = None,
    events: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=daily_record_id,
            trial_day_number=trial_day_number,
            source_record_path=source_record_path,
        )
        conn.execute("DELETE FROM rule_event WHERE daily_record_id = ?", (resolved_id,))
        for index, event in enumerate(events, start=1):
            upsert_rule_event_row(conn, daily_record_id=resolved_id, event_dict=event, source_order=index)
        return resolved_id


def insert_rule_event(
    event_dict: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> int:
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=to_int(event_dict.get("daily_record_id")),
            trial_day_number=to_int(event_dict.get("trial_day_number")),
            source_record_path=clean_text(event_dict.get("source_record_path")),
        )
        source_order = to_int(event_dict.get("source_order")) or 0
        return upsert_rule_event_row(conn, daily_record_id=resolved_id, event_dict=event_dict, source_order=source_order)


def next_agent_observation_id(
    conn: sqlite3.Connection,
    *,
    daily_record_id: int,
    trade_date: str,
) -> str:
    prefix = f"AO-{clean_text(trade_date)}-"
    rows = conn.execute(
        """
        SELECT observation_id
        FROM agent_observation
        WHERE daily_record_id = ? AND observation_id LIKE ?
        """,
        (daily_record_id, f"{prefix}%"),
    ).fetchall()
    max_number = 0
    for row in rows:
        value = clean_text(row["observation_id"])
        suffix = value.removeprefix(prefix)
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"{prefix}{max_number + 1:03d}"


def upsert_agent_observation_row(
    conn: sqlite3.Connection,
    *,
    daily_record_id: int,
    observation_dict: dict[str, Any],
    source_order: int = 0,
) -> int:
    trade_date = clean_text(observation_dict.get("trade_date"))
    observation_id = clean_text(observation_dict.get("observation_id"))
    if not observation_id:
        observation_id = next_agent_observation_id(
            conn,
            daily_record_id=daily_record_id,
            trade_date=trade_date,
        )
    params = {
        "daily_record_id": daily_record_id,
        "observation_id": observation_id,
        "source_order": source_order,
        "trade_date": trade_date,
        "market": clean_text(observation_dict.get("market")),
        "linked_trade_id": clean_text(observation_dict.get("linked_trade_id")),
        "linked_event_id": clean_text(observation_dict.get("linked_event_id")),
        "observation_type": clean_text(observation_dict.get("observation_type")),
        "severity": clean_text(observation_dict.get("severity")) or "info",
        "source": clean_text(observation_dict.get("source")) or "agent_question",
        "summary": clean_text(observation_dict.get("summary")),
        "evidence": clean_text(observation_dict.get("evidence")),
        "user_response": clean_text(observation_dict.get("user_response")),
        "status": clean_text(observation_dict.get("status")) or "open",
        "review_required": to_bool_int(observation_dict.get("review_required")),
    }
    conn.execute(
        """
        INSERT INTO agent_observation (
          daily_record_id, observation_id, source_order, trade_date, market, linked_trade_id,
          linked_event_id, observation_type, severity, source, summary, evidence,
          user_response, status, review_required, updated_at
        ) VALUES (
          :daily_record_id, :observation_id, :source_order, :trade_date, :market, :linked_trade_id,
          :linked_event_id, :observation_type, :severity, :source, :summary, :evidence,
          :user_response, :status, :review_required, CURRENT_TIMESTAMP
        )
        ON CONFLICT(daily_record_id, observation_id) DO UPDATE SET
          daily_record_id = excluded.daily_record_id,
          source_order = excluded.source_order,
          trade_date = excluded.trade_date,
          market = excluded.market,
          linked_trade_id = excluded.linked_trade_id,
          linked_event_id = excluded.linked_event_id,
          observation_type = excluded.observation_type,
          severity = excluded.severity,
          source = excluded.source,
          summary = excluded.summary,
          evidence = excluded.evidence,
          user_response = excluded.user_response,
          status = excluded.status,
          review_required = excluded.review_required,
          updated_at = CURRENT_TIMESTAMP
        """,
        params,
    )
    row = conn.execute(
        "SELECT id FROM agent_observation WHERE daily_record_id = ? AND observation_id = ?",
        (daily_record_id, params["observation_id"]),
    ).fetchone()
    return int(row["id"])


def replace_agent_observations(
    *,
    trial_day_number: int | None = None,
    daily_record_id: int | None = None,
    source_record_path: str | None = None,
    observations: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=daily_record_id,
            trial_day_number=trial_day_number,
            source_record_path=source_record_path,
        )
        conn.execute("DELETE FROM agent_observation WHERE daily_record_id = ?", (resolved_id,))
        for index, observation in enumerate(observations, start=1):
            upsert_agent_observation_row(
                conn,
                daily_record_id=resolved_id,
                observation_dict=observation,
                source_order=index,
            )
        return resolved_id


def insert_agent_observation(
    observation_dict: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> int:
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=to_int(observation_dict.get("daily_record_id")),
            trial_day_number=to_int(observation_dict.get("trial_day_number")),
            source_record_path=clean_text(observation_dict.get("source_record_path")),
        )
        source_order = to_int(observation_dict.get("source_order")) or 0
        return upsert_agent_observation_row(
            conn,
            daily_record_id=resolved_id,
            observation_dict=observation_dict,
            source_order=source_order,
        )


def upsert_daily_review_row(
    conn: sqlite3.Connection,
    *,
    daily_record_id: int,
    base: dict[str, Any],
    review: dict[str, Any],
    validation: dict[str, Any],
) -> int:
    pnl_text, pnl_amount = normalize_pnl(review.get("pnl"))
    minimum_process_passed = (
        validation.get("pre_market_done") is True
        and validation.get("intraday_record_complete") is True
        and validation.get("post_market_review_done") is True
    )
    params = {
        "daily_record_id": daily_record_id,
        "review_date": clean_text(review.get("review_date")) or clean_text(base.get("trade_date")),
        "market": clean_text(review.get("market")) or clean_text(base.get("market")),
        "primary_instrument": clean_text(review.get("primary_instrument")) or clean_text(base.get("primary_instrument")),
        "pnl_text": pnl_text,
        "pnl_amount": pnl_amount,
        "trade_count": to_int(review.get("trade_count")),
        "win_rate": clean_text(review.get("win_rate")),
        "max_loss_trade": clean_text(review.get("max_loss_trade")),
        "best_trade_note": clean_text(review.get("best_trade_note")),
        "worst_trade_note": clean_text(review.get("worst_trade_note")),
        "market_issue": clean_text(review.get("market_issue")),
        "execution_issue": clean_text(review.get("execution_issue")),
        "emotion_issue": clean_text(review.get("emotion_issue")),
        "risk_issue": clean_text(review.get("risk_issue")),
        "setup_issue": clean_text(review.get("setup_issue")),
        "next_day_one_fix": clean_text(review.get("next_day_one_fix")),
        "pre_market_done": to_bool_int(validation.get("pre_market_done")),
        "intraday_record_complete": to_bool_int(validation.get("intraday_record_complete")),
        "post_market_review_done": to_bool_int(validation.get("post_market_review_done")),
        "impulsive_trade_detected": to_bool_int(validation.get("impulsive_trade_detected")),
        "no_stop_loss_trade_detected": to_bool_int(validation.get("no_stop_loss_trade_detected")),
        "emotional_overtrade_detected": to_bool_int(validation.get("emotional_overtrade_detected")),
        "no_trade_day": to_bool_int(validation.get("no_trade_day")),
        "no_trade_note": clean_text(validation.get("no_trade_note")),
        "main_issue_of_day": clean_text(validation.get("main_issue_of_day")),
        "main_improvement_of_day": clean_text(validation.get("main_improvement_of_day")),
        "minimum_process_passed": to_bool_int(minimum_process_passed),
    }
    conn.execute(
        """
        INSERT INTO daily_review (
          daily_record_id, review_date, market, primary_instrument, pnl_text, pnl_amount, trade_count, win_rate,
          max_loss_trade, best_trade_note, worst_trade_note, market_issue, execution_issue, emotion_issue,
          risk_issue, setup_issue, next_day_one_fix, pre_market_done, intraday_record_complete,
          post_market_review_done, impulsive_trade_detected, no_stop_loss_trade_detected,
          emotional_overtrade_detected, no_trade_day, no_trade_note, main_issue_of_day,
          main_improvement_of_day, minimum_process_passed, updated_at
        ) VALUES (
          :daily_record_id, :review_date, :market, :primary_instrument, :pnl_text, :pnl_amount, :trade_count, :win_rate,
          :max_loss_trade, :best_trade_note, :worst_trade_note, :market_issue, :execution_issue, :emotion_issue,
          :risk_issue, :setup_issue, :next_day_one_fix, :pre_market_done, :intraday_record_complete,
          :post_market_review_done, :impulsive_trade_detected, :no_stop_loss_trade_detected,
          :emotional_overtrade_detected, :no_trade_day, :no_trade_note, :main_issue_of_day,
          :main_improvement_of_day, :minimum_process_passed, CURRENT_TIMESTAMP
        )
        ON CONFLICT(daily_record_id) DO UPDATE SET
          review_date = excluded.review_date,
          market = excluded.market,
          primary_instrument = excluded.primary_instrument,
          pnl_text = excluded.pnl_text,
          pnl_amount = excluded.pnl_amount,
          trade_count = excluded.trade_count,
          win_rate = excluded.win_rate,
          max_loss_trade = excluded.max_loss_trade,
          best_trade_note = excluded.best_trade_note,
          worst_trade_note = excluded.worst_trade_note,
          market_issue = excluded.market_issue,
          execution_issue = excluded.execution_issue,
          emotion_issue = excluded.emotion_issue,
          risk_issue = excluded.risk_issue,
          setup_issue = excluded.setup_issue,
          next_day_one_fix = excluded.next_day_one_fix,
          pre_market_done = excluded.pre_market_done,
          intraday_record_complete = excluded.intraday_record_complete,
          post_market_review_done = excluded.post_market_review_done,
          impulsive_trade_detected = excluded.impulsive_trade_detected,
          no_stop_loss_trade_detected = excluded.no_stop_loss_trade_detected,
          emotional_overtrade_detected = excluded.emotional_overtrade_detected,
          no_trade_day = excluded.no_trade_day,
          no_trade_note = excluded.no_trade_note,
          main_issue_of_day = excluded.main_issue_of_day,
          main_improvement_of_day = excluded.main_improvement_of_day,
          minimum_process_passed = excluded.minimum_process_passed,
          updated_at = CURRENT_TIMESTAMP
        """,
        params,
    )
    row = conn.execute("SELECT id FROM daily_review WHERE daily_record_id = ?", (daily_record_id,)).fetchone()
    return int(row["id"])


def save_daily_review(
    record_dict: dict[str, Any],
    *,
    daily_record_id: int | None = None,
    trial_day_number: int | None = None,
    source_record_path: str | None = None,
    db_path: Path | None = None,
) -> int:
    base = record_dict.get("base", {})
    review = record_dict.get("review", record_dict.get("review_record", {}))
    validation = record_dict.get("validation", record_dict.get("trial_validation_record", {}))
    with get_connection(db_path) as conn:
        resolved_id = resolve_daily_record_id(
            conn,
            daily_record_id=daily_record_id,
            trial_day_number=trial_day_number or to_int(base.get("day_number")),
            source_record_path=source_record_path,
        )
        return upsert_daily_review_row(
            conn,
            daily_record_id=resolved_id,
            base=base,
            review=review,
            validation=validation,
        )


def save_record_bundle(
    record_dict: dict[str, Any],
    *,
    source_record_path: str | None = None,
    db_path: Path | None = None,
) -> int:
    base, pre_market, workbench, playbook = extract_sections(record_dict)
    resolved_path = source_record_path or record_dict.get("source_record_path")
    if not resolved_path:
        raise ValueError("source_record_path is required for save_record_bundle.")
    trades = list(record_dict.get("trades", []))
    events = list(record_dict.get("events", []))
    observations = list(record_dict.get("observations", []))
    has_observations = "observations" in record_dict
    review = record_dict.get("review", {})
    validation = record_dict.get("validation", {})
    with get_connection(db_path) as conn:
        daily_record_id = upsert_daily_record_row(
            conn,
            base=base,
            pre_market=pre_market,
            workbench=workbench,
            playbook=playbook,
            source_record_path=clean_text(resolved_path),
        )
        conn.execute("DELETE FROM trade_record WHERE daily_record_id = ?", (daily_record_id,))
        for index, trade in enumerate(trades, start=1):
            upsert_trade_row(conn, daily_record_id=daily_record_id, trade_dict=trade, source_order=index)
        conn.execute("DELETE FROM rule_event WHERE daily_record_id = ?", (daily_record_id,))
        for index, event in enumerate(events, start=1):
            upsert_rule_event_row(conn, daily_record_id=daily_record_id, event_dict=event, source_order=index)
        if has_observations:
            conn.execute("DELETE FROM agent_observation WHERE daily_record_id = ?", (daily_record_id,))
            for index, observation in enumerate(observations, start=1):
                upsert_agent_observation_row(
                    conn,
                    daily_record_id=daily_record_id,
                    observation_dict=observation,
                    source_order=index,
                )
        upsert_daily_review_row(
            conn,
            daily_record_id=daily_record_id,
            base=base,
            review=review,
            validation=validation,
        )
        return daily_record_id


def build_base_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "day_number": row["trial_day_number"],
        "trade_date": row["trade_date"],
        "market": row["market"],
        "primary_instrument": row["primary_instrument"],
        "record_mode": row["trial_mode"],
        "operator": row["operator"],
        "record_owner": row["record_owner"],
    }


def build_pre_market_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trading_today": row["trading_today"] == 1,
        "state": row["pre_market_state"],
        "follow_normal_rules": row["follow_normal_rules"] == 1,
        "key_reminder": row["key_reminder"],
        "note": row["pre_market_note"],
    }


def build_workbench_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trading_mode": row["trading_mode"],
        "main_direction": row["main_direction"],
        "upper_pressure": row["upper_pressure"],
        "lower_support": row["lower_support"],
        "pivot_level": row["pivot_level"],
        "current_state": row["current_state"],
        "post_market_summary": row["post_market_summary"],
        "capital_used": row["capital_used"],
        "profit_target_pct": row["profit_target_pct"],
        "hk_watchlist": row.get("hk_watchlist", ""),
        "us_watchlist": row.get("us_watchlist", ""),
    }


def build_playbook_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "opening_plan": row["opening_plan"],
        "focus_setup": row["focus_setup"],
        "open_30_key_signal": row["open_30_key_signal"],
        "certificate_filter_note": row["certificate_filter_note"],
        "abnormal_plan": row["abnormal_plan"],
        "option_session_plan": row["option_session_plan"],
        "focus_tickers": row["focus_tickers"],
        "option_focus_setup": row["option_focus_setup"],
        "option_entry_signal": row["option_entry_signal"],
        "option_contract_filter": row["option_contract_filter"],
        "option_risk_plan": row["option_risk_plan"],
        "option_event_risk_plan": row["option_event_risk_plan"],
    }


def build_review_dict(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "review_date": "",
            "market": "",
            "primary_instrument": "",
            "pnl": "",
            "trade_count": None,
            "win_rate": "",
            "max_loss_trade": "",
            "best_trade_note": "",
            "worst_trade_note": "",
            "market_issue": "",
            "execution_issue": "",
            "emotion_issue": "",
            "risk_issue": "",
            "setup_issue": "",
            "next_day_one_fix": "",
        }
    return {
        "review_date": row["review_date"],
        "market": row["market"],
        "primary_instrument": row["primary_instrument"],
        "pnl": row["pnl_text"],
        "trade_count": row["trade_count"],
        "win_rate": row["win_rate"],
        "max_loss_trade": row["max_loss_trade"],
        "best_trade_note": row["best_trade_note"],
        "worst_trade_note": row["worst_trade_note"],
        "market_issue": row["market_issue"],
        "execution_issue": row["execution_issue"],
        "emotion_issue": row["emotion_issue"],
        "risk_issue": row["risk_issue"],
        "setup_issue": row["setup_issue"],
        "next_day_one_fix": row["next_day_one_fix"],
    }


def build_trade_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trade_id": row["trade_id"],
        "trade_date": row["trade_date"],
        "trade_time": row["trade_time"],
        "market": row["market"],
        "instrument_code": row["instrument_code"],
        "certificate_side": row["certificate_side"],
        "instrument_type": row["instrument_type"],
        "underlying": row["underlying"],
        "direction": row["direction"],
        "session_window": row["session_window"],
        "setup_type": row["setup_type"],
        "abc_grade": row["abc_grade"],
        "setup_score": row["setup_score"],
        "entry_reason": row["entry_reason"],
        "setup_validated": None if row["setup_validated"] is None else row["setup_validated"] == 1,
        "direction_clear": None if row["direction_clear"] is None else row["direction_clear"] == 1,
        "location_ok": None if row["location_ok"] is None else row["location_ok"] == 1,
        "confirmation_ok": None if row["confirmation_ok"] is None else row["confirmation_ok"] == 1,
        "risk_clear": None if row["risk_clear"] is None else row["risk_clear"] == 1,
        "certificate_filter_passed": None if row["certificate_filter_passed"] is None else row["certificate_filter_passed"] == 1,
        "abnormal_scenario": row["abnormal_scenario"],
        "entry_price": row["entry_price"],
        "stop_loss": row["stop_loss"],
        "target_price": row["target_price"],
        "position_size": row["position_size"],
        "exit_time": row["exit_time"],
        "exit_price": row["exit_price"],
        "pnl_amount": row["pnl_amount"],
        "risk_reward_ratio": row["risk_reward_ratio"],
        "exit_reason": row["exit_reason"],
        "followed_plan": row["followed_plan"] == 1,
        "emotion_state": row["emotion_state"],
        "pre_trade_emotion": row["pre_trade_emotion"],
        "post_trade_emotion": row["post_trade_emotion"],
        "rule_violation": row["rule_violation"] == 1,
        "violation_note": row["violation_note"],
        "result": row["result"],
        "screenshot_note": row["screenshot_note"],
        "review_note": row["review_note"],
    }


def build_rule_event_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "date": row["event_date"],
        "time": row["event_time"],
        "market": row["market"],
        "event_type": row["event_type"],
        "severity": row["severity"],
        "trigger_reason": row["trigger_reason"],
        "action_taken": row["action_taken"],
        "follow_up_note": row["follow_up_note"],
        "linked_trade_id": row["linked_trade_id"],
    }


def build_agent_observation_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": row["observation_id"],
        "trade_date": row["trade_date"],
        "market": row["market"],
        "linked_trade_id": row["linked_trade_id"],
        "linked_event_id": row["linked_event_id"],
        "observation_type": row["observation_type"],
        "severity": row["severity"],
        "source": row["source"],
        "summary": row["summary"],
        "evidence": row["evidence"],
        "user_response": row["user_response"],
        "status": row["status"],
        "review_required": row["review_required"] == 1,
    }


def build_validation_dict(row: dict[str, Any] | None, trial_day_number: int | None, trade_date: str, market: str, primary_instrument: str) -> dict[str, Any]:
    if row is None:
        return {
            "trial_day_number": trial_day_number,
            "date": trade_date,
            "market": market,
            "primary_instrument": primary_instrument,
            "pre_market_done": False,
            "intraday_record_complete": False,
            "post_market_review_done": False,
            "impulsive_trade_detected": False,
            "no_stop_loss_trade_detected": False,
            "emotional_overtrade_detected": False,
            "no_trade_day": False,
            "no_trade_note": "",
            "main_issue_of_day": "",
            "main_improvement_of_day": "",
        }
    return {
        "trial_day_number": trial_day_number,
        "date": trade_date,
        "market": market,
        "primary_instrument": primary_instrument,
        "pre_market_done": row["pre_market_done"] == 1,
        "intraday_record_complete": row["intraday_record_complete"] == 1,
        "post_market_review_done": row["post_market_review_done"] == 1,
        "impulsive_trade_detected": row["impulsive_trade_detected"] == 1,
        "no_stop_loss_trade_detected": row["no_stop_loss_trade_detected"] == 1,
        "emotional_overtrade_detected": row["emotional_overtrade_detected"] == 1,
        "no_trade_day": row["no_trade_day"] == 1,
        "no_trade_note": row["no_trade_note"],
        "main_issue_of_day": row["main_issue_of_day"],
        "main_improvement_of_day": row["main_improvement_of_day"],
    }


def get_daily_record(trial_day_number: int, *, db_path: Path | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        daily_row = conn.execute(
            "SELECT * FROM daily_record WHERE trial_day_number = ?",
            (trial_day_number,),
        ).fetchone()
        if daily_row is None:
            return None
        daily = dict(daily_row)
        trades = [
            build_trade_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM trade_record WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        events = [
            build_rule_event_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM rule_event WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        observations = [
            build_agent_observation_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM agent_observation WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        review_row = sqlite_row_to_dict(
            conn.execute(
                "SELECT * FROM daily_review WHERE daily_record_id = ?",
                (daily["id"],),
            ).fetchone()
        )
        return {
            "content": "",
            "source_record_path": daily["source_record_path"],
            "base": build_base_dict(daily),
            "pre_market": build_pre_market_dict(daily),
            "workbench": build_workbench_dict(daily),
            "playbook": build_playbook_dict(daily),
            "trades": trades,
            "events": events,
            "observations": observations,
            "review": build_review_dict(review_row),
            "validation": build_validation_dict(
                review_row,
                trial_day_number=daily["trial_day_number"],
                trade_date=daily["trade_date"],
                market=daily["market"],
                primary_instrument=daily["primary_instrument"],
            ),
        }


def get_latest_day_number_for_trade_date(trade_date: str, *, db_path: Path | None = None) -> int | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT trial_day_number
            FROM daily_record
            WHERE trade_date = ?
            ORDER BY trial_day_number DESC
            LIMIT 1
            """,
            (trade_date,),
        ).fetchone()
        if row is None:
            return None
        return int(row["trial_day_number"])


def get_latest_day_number_on_or_before(trade_date: str, *, db_path: Path | None = None) -> int | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT trial_day_number
            FROM daily_record
            WHERE trade_date <= ?
            ORDER BY trade_date DESC, trial_day_number DESC
            LIMIT 1
            """,
            (trade_date,),
        ).fetchone()
        if row is None:
            return None
        return int(row["trial_day_number"])


def get_daily_record_by_source_path(source_record_path: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    normalized_path = normalize_source_path(source_record_path)
    with get_connection(db_path) as conn:
        daily_row = conn.execute(
            "SELECT * FROM daily_record WHERE source_record_path = ?",
            (normalized_path,),
        ).fetchone()
        if daily_row is None:
            return None
        daily = dict(daily_row)
        trades = [
            build_trade_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM trade_record WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        events = [
            build_rule_event_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM rule_event WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        observations = [
            build_agent_observation_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM agent_observation WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        review_row = sqlite_row_to_dict(
            conn.execute(
                "SELECT * FROM daily_review WHERE daily_record_id = ?",
                (daily["id"],),
            ).fetchone()
        )
        return {
            "content": "",
            "source_record_path": daily["source_record_path"],
            "base": build_base_dict(daily),
            "pre_market": build_pre_market_dict(daily),
            "workbench": build_workbench_dict(daily),
            "playbook": build_playbook_dict(daily),
            "trades": trades,
            "events": events,
            "observations": observations,
            "review": build_review_dict(review_row),
            "validation": build_validation_dict(
                review_row,
                trial_day_number=daily["trial_day_number"],
                trade_date=daily["trade_date"],
                market=daily["market"],
                primary_instrument=daily["primary_instrument"],
            ),
        }


def get_daily_record_by_date_market(
    trade_date: str,
    market: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        daily_row = conn.execute(
            """
            SELECT *
            FROM daily_record
            WHERE trade_date = ? AND market = ?
            LIMIT 1
            """,
            (clean_text(trade_date), clean_text(market)),
        ).fetchone()
        if daily_row is None:
            return None
        daily = dict(daily_row)
        trades = [
            build_trade_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM trade_record WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        events = [
            build_rule_event_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM rule_event WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        observations = [
            build_agent_observation_dict(dict(row))
            for row in conn.execute(
                "SELECT * FROM agent_observation WHERE daily_record_id = ? ORDER BY source_order, id",
                (daily["id"],),
            ).fetchall()
        ]
        review_row = sqlite_row_to_dict(
            conn.execute(
                "SELECT * FROM daily_review WHERE daily_record_id = ?",
                (daily["id"],),
            ).fetchone()
        )
        return {
            "content": "",
            "source_record_path": daily["source_record_path"],
            "base": build_base_dict(daily),
            "pre_market": build_pre_market_dict(daily),
            "workbench": build_workbench_dict(daily),
            "playbook": build_playbook_dict(daily),
            "trades": trades,
            "events": events,
            "observations": observations,
            "review": build_review_dict(review_row),
            "validation": build_validation_dict(
                review_row,
                trial_day_number=daily["trial_day_number"],
                trade_date=daily["trade_date"],
                market=daily["market"],
                primary_instrument=daily["primary_instrument"],
            ),
        }


def get_latest_record_for_market(
    market: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    normalized_market = clean_text(market)
    if not normalized_market:
        return None
    with get_connection(db_path) as conn:
        daily_row = conn.execute(
            """
            SELECT trade_date
            FROM daily_record
            WHERE market = ?
            ORDER BY trade_date DESC, trial_day_number DESC
            LIMIT 1
            """,
            (normalized_market,),
        ).fetchone()
    if daily_row is None:
        return None
    return get_daily_record_by_date_market(
        clean_text(daily_row["trade_date"]),
        normalized_market,
        db_path=db_path,
    )


def get_recent_records_for_market(
    market: str | None = None,
    limit: int = 8,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        filter_sql = ""
        params: list[Any] = []
        normalized_market = clean_text(market)
        if normalized_market and normalized_market != "ALL":
            filter_sql = "WHERE dr.market = ?"
            params.append(normalized_market)
        params.append(limit)
        rows = conn.execute(
            f"""
            WITH trade_stats AS (
              SELECT
                daily_record_id,
                COUNT(*) AS trade_count
              FROM trade_record
              GROUP BY daily_record_id
            )
            SELECT
              dr.id,
              dr.trial_day_number,
              dr.trade_date,
              dr.market,
              dr.primary_instrument,
              dr.trading_mode,
              dr.current_state,
              dr.source_record_path,
              COALESCE(ts.trade_count, 0) AS trade_count,
              CASE
                WHEN rv.pnl_text <> ''
                 AND rv.trade_count IS NOT NULL
                 AND rv.best_trade_note <> ''
                 AND rv.worst_trade_note <> ''
                 AND rv.execution_issue <> ''
                 AND rv.emotion_issue <> ''
                 AND rv.risk_issue <> ''
                 AND rv.next_day_one_fix <> '' THEN 1
                ELSE 0
              END AS review_done,
              CASE
                WHEN rv.pre_market_done = 1
                 AND rv.intraday_record_complete = 1
                 AND rv.post_market_review_done = 1
                 AND ((rv.no_trade_day = 1 AND rv.no_trade_note <> '') OR (rv.no_trade_day = 0 AND rv.main_issue_of_day <> '')) THEN 1
                ELSE 0
              END AS validation_done
            FROM daily_record dr
            LEFT JOIN trade_stats ts ON ts.daily_record_id = dr.id
            LEFT JOIN daily_review rv ON rv.daily_record_id = dr.id
            {filter_sql}
            ORDER BY dr.trade_date DESC, dr.market, dr.trial_day_number DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [
            {
                **dict(row),
                "review_done": bool(row["review_done"]),
                "validation_done": bool(row["validation_done"]),
            }
            for row in rows
        ]


def get_workspace_state(*, db_path: Path | None = None) -> dict[str, Any]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM workspace_state WHERE id = 1").fetchone()
        if row is None:
            return {
                "current_market": "HK",
                "current_trade_date": "",
                "theme": "dark",
            }
        return dict(row)


def save_workspace_state(
    *,
    current_market: str | None = None,
    current_trade_date: str | None = None,
    theme: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    with get_connection(db_path) as conn:
        existing = dict(conn.execute("SELECT * FROM workspace_state WHERE id = 1").fetchone())
        next_market = clean_text(current_market) or existing["current_market"]
        next_trade_date = clean_text(current_trade_date) or existing["current_trade_date"]
        next_theme = clean_text(theme) or existing["theme"]
        conn.execute(
            """
            UPDATE workspace_state
            SET current_market = ?, current_trade_date = ?, theme = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (next_market, next_trade_date, next_theme),
        )
    return get_workspace_state(db_path=db_path)


def get_recent_records(limit: int = 8, *, db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            WITH trade_stats AS (
              SELECT
                daily_record_id,
                COUNT(*) AS trade_count
              FROM trade_record
              GROUP BY daily_record_id
            )
            SELECT
              dr.id,
              dr.trial_day_number,
              dr.trade_date,
              dr.market,
              dr.primary_instrument,
              dr.trading_mode,
              dr.current_state,
              dr.source_record_path,
              COALESCE(ts.trade_count, 0) AS trade_count,
              CASE
                WHEN rv.pnl_text <> ''
                 AND rv.trade_count IS NOT NULL
                 AND rv.best_trade_note <> ''
                 AND rv.worst_trade_note <> ''
                 AND rv.execution_issue <> ''
                 AND rv.emotion_issue <> ''
                 AND rv.risk_issue <> ''
                 AND rv.next_day_one_fix <> '' THEN 1
                ELSE 0
              END AS review_done,
              CASE
                WHEN rv.pre_market_done = 1
                 AND rv.intraday_record_complete = 1
                 AND rv.post_market_review_done = 1
                 AND ((rv.no_trade_day = 1 AND rv.no_trade_note <> '') OR (rv.no_trade_day = 0 AND rv.main_issue_of_day <> '')) THEN 1
                ELSE 0
              END AS validation_done
            FROM daily_record dr
            LEFT JOIN trade_stats ts ON ts.daily_record_id = dr.id
            LEFT JOIN daily_review rv ON rv.daily_record_id = dr.id
            ORDER BY dr.trial_day_number DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                **dict(row),
                "review_done": bool(row["review_done"]),
                "validation_done": bool(row["validation_done"]),
            }
            for row in rows
        ]


def get_trades_by_date(trade_date: str, *, db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
              t.*,
              dr.trial_day_number
            FROM trade_record t
            JOIN daily_record dr ON dr.id = t.daily_record_id
            WHERE t.trade_date = ?
            ORDER BY dr.trial_day_number, t.source_order, t.id
            """,
            (trade_date,),
        ).fetchall()
        return [
            {
                **build_trade_dict(dict(row)),
                "trial_day_number": row["trial_day_number"],
            }
            for row in rows
        ]


def review_hub_base_cte(limit_days: int | None, market: str | None = None) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    scope_limit_sql = ""
    scope_where_sql = ""
    if limit_days is not None:
        scope_limit_sql = "LIMIT :limit_days"
        params["limit_days"] = limit_days
    normalized_market = clean_text(market)
    if normalized_market and normalized_market != "ALL":
        scope_where_sql = "WHERE market = :market"
        params["market"] = normalized_market
    sql = f"""
    WITH scope AS (
      SELECT id
      FROM daily_record
      {scope_where_sql}
      ORDER BY trial_day_number DESC
      {scope_limit_sql}
    ),
    trade_stats AS (
      SELECT
        t.daily_record_id,
        COUNT(*) AS trade_count,
        SUM(CASE WHEN t.rule_violation = 1 THEN 1 ELSE 0 END) AS violation_count,
        SUM(CASE WHEN t.followed_plan = 1 THEN 1 ELSE 0 END) AS followed_yes,
        SUM(CASE WHEN t.followed_plan IN (0, 1) THEN 1 ELSE 0 END) AS followed_total,
        SUM(CASE WHEN t.result = 'win' THEN 1 ELSE 0 END) AS win_count,
        SUM(CASE WHEN t.result = 'loss' THEN 1 ELSE 0 END) AS loss_count,
        SUM(CASE WHEN t.result = 'breakeven' THEN 1 ELSE 0 END) AS breakeven_count,
        SUM(CASE WHEN t.session_window = 'opening_30m' THEN 1 ELSE 0 END) AS opening_30_count,
        SUM(CASE WHEN t.direction_clear = 0 OR t.location_ok = 0 OR t.confirmation_ok = 0 OR t.risk_clear = 0 THEN 1 ELSE 0 END) AS phase2_check_fail_count,
        SUM(CASE WHEN t.certificate_filter_passed = 0 THEN 1 ELSE 0 END) AS certificate_filter_fail_count,
        SUM(CASE WHEN COALESCE(t.abnormal_scenario, '') NOT IN ('', 'none') THEN 1 ELSE 0 END) AS abnormal_count,
        SUM(CASE WHEN t.pnl_amount IS NOT NULL THEN t.pnl_amount ELSE 0 END) AS pnl_total,
        SUM(CASE WHEN t.pnl_amount IS NOT NULL THEN 1 ELSE 0 END) AS pnl_count
      FROM trade_record t
      WHERE t.daily_record_id IN (SELECT id FROM scope)
      GROUP BY t.daily_record_id
    ),
    event_stats AS (
      SELECT
        e.daily_record_id,
        COUNT(*) AS event_count
      FROM rule_event e
      WHERE e.daily_record_id IN (SELECT id FROM scope)
      GROUP BY e.daily_record_id
    ),
    base AS (
      SELECT
        dr.id AS daily_record_id,
        dr.source_record_path,
        dr.trial_day_number,
        dr.trade_date,
        dr.market,
        dr.primary_instrument,
        dr.trading_mode,
        dr.current_state,
        CASE WHEN dr.trading_mode = 'us_stock_options' THEN dr.option_session_plan ELSE dr.opening_plan END AS active_plan,
        CASE WHEN dr.trading_mode = 'us_stock_options' THEN dr.option_focus_setup ELSE dr.focus_setup END AS active_setup,
        COALESCE(ts.trade_count, 0) AS trade_count,
        CASE WHEN COALESCE(ts.trade_count, 0) > 0 THEN 1 ELSE 0 END AS has_trades,
        COALESCE(es.event_count, 0) AS event_count,
        COALESCE(ts.violation_count, 0) AS violation_count,
        COALESCE(ts.followed_yes, 0) AS followed_yes,
        COALESCE(ts.followed_total, 0) AS followed_total,
        COALESCE(ts.win_count, 0) AS win_count,
        COALESCE(ts.loss_count, 0) AS loss_count,
        COALESCE(ts.breakeven_count, 0) AS breakeven_count,
        COALESCE(ts.opening_30_count, 0) AS opening_30_count,
        COALESCE(ts.phase2_check_fail_count, 0) AS phase2_check_fail_count,
        COALESCE(ts.certificate_filter_fail_count, 0) AS certificate_filter_fail_count,
        COALESCE(ts.abnormal_count, 0) AS abnormal_count,
        CASE
          WHEN ts.pnl_count > 0 THEN ts.pnl_total
          WHEN COALESCE(ts.trade_count, 0) > 0 AND rv.pnl_amount IS NOT NULL THEN rv.pnl_amount
          ELSE NULL
        END AS snapshot_pnl,
        CASE
          WHEN dr.main_direction NOT IN ('', 'undecided')
           AND dr.current_state NOT IN ('', 'unset')
           AND dr.capital_used IS NOT NULL
           AND dr.profit_target_pct IS NOT NULL
           AND TRIM(dr.upper_pressure) <> ''
           AND TRIM(dr.lower_support) <> ''
           AND TRIM(dr.pivot_level) <> '' THEN 1
          ELSE 0
        END AS workbench_ready,
        CASE
          WHEN rv.pnl_text <> ''
           AND rv.trade_count IS NOT NULL
           AND rv.best_trade_note <> ''
           AND rv.worst_trade_note <> ''
           AND rv.execution_issue <> ''
           AND rv.emotion_issue <> ''
           AND rv.risk_issue <> ''
           AND rv.next_day_one_fix <> '' THEN 1
          ELSE 0
        END AS review_done,
        CASE
          WHEN rv.pre_market_done = 1
           AND rv.intraday_record_complete = 1
           AND rv.post_market_review_done = 1
           AND ((rv.no_trade_day = 1 AND rv.no_trade_note <> '') OR (rv.no_trade_day = 0 AND rv.main_issue_of_day <> '')) THEN 1
          ELSE 0
        END AS validation_done,
        CASE WHEN rv.trade_count IS NOT NULL AND rv.trade_count <> COALESCE(ts.trade_count, 0) THEN 1 ELSE 0 END AS review_trade_count_mismatch,
        CASE
          WHEN rv.pnl_amount IS NOT NULL
           AND ts.pnl_count > 0
           AND ABS(rv.pnl_amount - ts.pnl_total) > 1e-9 THEN 1
          ELSE 0
        END AS review_pnl_mismatch,
        CASE WHEN rv.no_trade_day = 1 AND (COALESCE(ts.trade_count, 0) > 0 OR COALESCE(es.event_count, 0) > 0) THEN 1 ELSE 0 END AS no_trade_conflict,
        (
          meaningful_text(rv.best_trade_note)
          + meaningful_text(rv.worst_trade_note)
          + meaningful_text(rv.execution_issue)
          + meaningful_text(rv.emotion_issue)
          + meaningful_text(rv.risk_issue)
          + meaningful_text(rv.next_day_one_fix)
        ) AS meaningful_review_field_count,
        CASE
          WHEN rv.no_trade_day = 1 THEN meaningful_text(rv.no_trade_note)
          ELSE meaningful_text(rv.main_issue_of_day)
        END AS validation_note_ok,
        COALESCE(rv.no_trade_day, 0) AS no_trade_day,
        CASE WHEN meaningful_text(rv.no_trade_note) = 1 THEN rv.no_trade_note ELSE '' END AS no_trade_note,
        CASE WHEN meaningful_text(rv.main_issue_of_day) = 1 THEN rv.main_issue_of_day ELSE '' END AS main_issue,
        CASE WHEN meaningful_text(rv.main_improvement_of_day) = 1 THEN rv.main_improvement_of_day ELSE '' END AS main_improvement,
        CASE WHEN meaningful_text(rv.next_day_one_fix) = 1 THEN rv.next_day_one_fix ELSE '' END AS next_fix,
        COALESCE(rv.impulsive_trade_detected, 0) AS impulsive_flag,
        COALESCE(rv.no_stop_loss_trade_detected, 0) AS stop_loss_flag,
        COALESCE(rv.emotional_overtrade_detected, 0) AS overtrade_flag
      FROM daily_record dr
      LEFT JOIN trade_stats ts ON ts.daily_record_id = dr.id
      LEFT JOIN event_stats es ON es.daily_record_id = dr.id
      LEFT JOIN daily_review rv ON rv.daily_record_id = dr.id
      WHERE dr.id IN (SELECT id FROM scope)
    ),
    decorated AS (
      SELECT
        *,
        CASE
          WHEN review_done = 0 THEN 0
          WHEN validation_done = 0 THEN 0
          WHEN review_trade_count_mismatch = 1 THEN 0
          WHEN review_pnl_mismatch = 1 THEN 0
          WHEN no_trade_conflict = 1 THEN 0
          WHEN meaningful_review_field_count < 4 THEN 0
          WHEN validation_note_ok = 0 THEN 0
          ELSE 1
        END AS trusted_sample
      FROM base
    )
    """
    return sql, params


def quality_issues_from_row(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if row["review_done"] != 1:
        issues.append("复盘未完整")
    if row["validation_done"] != 1:
        issues.append("验证未完整")
    if row["review_trade_count_mismatch"] == 1:
        issues.append("复盘交易数与真实交易数不一致")
    if row["review_pnl_mismatch"] == 1:
        issues.append("复盘盈亏与真实交易盈亏不一致")
    if row["no_trade_conflict"] == 1:
        issues.append("空仓标记与盘中事实冲突")
    if row["review_done"] == 1 and row["validation_done"] == 1:
        if row["meaningful_review_field_count"] < 4 or row["validation_note_ok"] != 1:
            issues.append("复盘文本像占位值")
    return issues


def get_review_hub_day_rows(
    *,
    limit_days: int | None = 5,
    filter_trusted: bool = False,
    market: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    base_cte, params = review_hub_base_cte(limit_days, market)
    params["filter_trusted"] = 1 if filter_trusted else 0
    sql = base_cte + """
    SELECT *
    FROM decorated
    WHERE (:filter_trusted = 0 OR trusted_sample = 1)
    ORDER BY trial_day_number DESC
    """
    with get_connection(db_path) as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    snapshots = []
    for row in rows:
        snapshots.append(
            {
                "path": row["source_record_path"],
                "day": row["trial_day_number"],
                "trade_date": row["trade_date"],
                "market": row["market"],
                "state": row["current_state"] or "未填",
                "trade_count": row["trade_count"],
                "has_trades": bool(row["has_trades"]),
                "violation_count": row["violation_count"],
                "pnl_value": row["snapshot_pnl"],
                "review_done": bool(row["review_done"]),
                "validation_done": bool(row["validation_done"]),
                "workbench_ready": bool(row["workbench_ready"]),
                "followed_yes": row["followed_yes"],
                "followed_total": row["followed_total"],
                "win_count": row["win_count"],
                "loss_count": row["loss_count"],
                "breakeven_count": row["breakeven_count"],
                "opening_30_count": row["opening_30_count"],
                "phase2_check_fail_count": row["phase2_check_fail_count"],
                "certificate_filter_fail_count": row["certificate_filter_fail_count"],
                "abnormal_count": row["abnormal_count"],
                "trading_mode": row["trading_mode"],
                "active_plan": row["active_plan"],
                "active_setup": row["active_setup"],
                "trusted_sample": bool(row["trusted_sample"]),
                "quality_issues": quality_issues_from_row(row),
                "no_trade_day": bool(row["no_trade_day"]),
                "no_trade_note": row["no_trade_note"],
                "main_issue": row["main_issue"],
                "main_improvement": row["main_improvement"],
                "next_fix": row["next_fix"],
                "impulsive_flag": bool(row["impulsive_flag"]),
                "stop_loss_flag": bool(row["stop_loss_flag"]),
                "overtrade_flag": bool(row["overtrade_flag"]),
            }
        )
    return snapshots


def get_review_hub_stats(
    *,
    limit_days: int | None = 5,
    filter_trusted: bool = False,
    market: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    base_cte, params = review_hub_base_cte(limit_days, market)
    params["filter_trusted"] = 1 if filter_trusted else 0
    filtered_cte = base_cte + """
    , filtered AS (
      SELECT *
      FROM decorated
      WHERE (:filter_trusted = 0 OR trusted_sample = 1)
    )
    """
    with get_connection(db_path) as conn:
        def run_filtered_query(query_body: str) -> list[dict[str, Any]]:
            # 这里统一复用同一个 params：
            # params 用于 top_setups
            # params 用于 top_active_plans
            # params 用于 top_active_setups
            # params 用于 recent_issues / recent_fixes / recent_no_trade_notes
            return [dict(row) for row in conn.execute(filtered_cte + query_body, params).fetchall()]

        summary_row = dict(
            conn.execute(
                filtered_cte
                + """
                SELECT
                  COUNT(*) AS day_count,
                  SUM(has_trades) AS trade_day_count,
                  SUM(no_trade_day) AS no_trade_day_count,
                  SUM(CASE WHEN snapshot_pnl IS NOT NULL THEN snapshot_pnl ELSE 0 END) AS total_pnl,
                  AVG(snapshot_pnl) AS avg_daily_pnl,
                  SUM(trade_count) AS trade_count,
                  SUM(violation_count) AS violation_count,
                  SUM(review_done) AS review_done_days,
                  SUM(validation_done) AS validation_done_days,
                  SUM(followed_yes) AS followed_yes,
                  SUM(followed_total) AS followed_total,
                  SUM(win_count) AS win_count,
                  SUM(loss_count) AS loss_count,
                  SUM(breakeven_count) AS breakeven_count,
                  SUM(impulsive_flag) AS impulsive_days,
                  SUM(stop_loss_flag) AS stop_loss_days,
                  SUM(overtrade_flag) AS overtrade_days,
                  SUM(opening_30_count) AS opening_30_trade_count,
                  SUM(phase2_check_fail_count) AS phase2_check_fail_count,
                  SUM(certificate_filter_fail_count) AS certificate_filter_fail_count,
                  SUM(abnormal_count) AS abnormal_trade_count
                FROM filtered
                """,
                params,
            ).fetchone()
        )

        top_setups = run_filtered_query(
            """
                SELECT
                  t.setup_type,
                  COUNT(*) AS count
                FROM filtered f
                JOIN trade_record t ON t.daily_record_id = f.daily_record_id
                WHERE t.setup_type <> ''
                GROUP BY t.setup_type
                ORDER BY count DESC, t.setup_type
                LIMIT 3
                """
        )
        top_active_plans = run_filtered_query(
            """
                SELECT
                  active_plan,
                  COUNT(*) AS count
                FROM filtered
                WHERE active_plan <> ''
                GROUP BY active_plan
                ORDER BY count DESC, active_plan
                LIMIT 2
                """
        )
        top_active_setups = run_filtered_query(
            """
                SELECT
                  active_setup,
                  COUNT(*) AS count
                FROM filtered
                WHERE active_setup <> ''
                GROUP BY active_setup
                ORDER BY count DESC, active_setup
                LIMIT 2
                """
        )
        recent_issues = run_filtered_query(
            """
                SELECT
                  trial_day_number,
                  trade_date,
                  main_issue
                FROM filtered
                WHERE main_issue <> ''
                ORDER BY trial_day_number DESC
                LIMIT 3
                """
        )
        recent_fixes = run_filtered_query(
            """
                SELECT
                  trial_day_number,
                  trade_date,
                  next_fix
                FROM filtered
                WHERE next_fix <> ''
                ORDER BY trial_day_number DESC
                LIMIT 3
                """
        )
        recent_no_trade_notes = run_filtered_query(
            """
                SELECT
                  trial_day_number,
                  trade_date,
                  no_trade_note
                FROM filtered
                WHERE no_trade_note <> ''
                ORDER BY trial_day_number DESC
                LIMIT 3
                """
        )
        # SQLite 不支持在单次查询里同时返回多个聚合结果集和多个 TOP-N 列表，
        # 因此这里保持 6 次独立 execute，但共用同一连接和 params。

    return {
        "day_count": int(summary_row["day_count"] or 0),
        "trade_day_count": int(summary_row["trade_day_count"] or 0),
        "no_trade_day_count": int(summary_row["no_trade_day_count"] or 0),
        "total_pnl": summary_row["total_pnl"],
        "avg_daily_pnl": summary_row["avg_daily_pnl"],
        "trade_count": int(summary_row["trade_count"] or 0),
        "violation_count": int(summary_row["violation_count"] or 0),
        "review_done_days": int(summary_row["review_done_days"] or 0),
        "validation_done_days": int(summary_row["validation_done_days"] or 0),
        "followed_yes": int(summary_row["followed_yes"] or 0),
        "followed_total": int(summary_row["followed_total"] or 0),
        "win_count": int(summary_row["win_count"] or 0),
        "loss_count": int(summary_row["loss_count"] or 0),
        "breakeven_count": int(summary_row["breakeven_count"] or 0),
        "impulsive_days": int(summary_row["impulsive_days"] or 0),
        "stop_loss_days": int(summary_row["stop_loss_days"] or 0),
        "overtrade_days": int(summary_row["overtrade_days"] or 0),
        "opening_30_trade_count": int(summary_row["opening_30_trade_count"] or 0),
        "phase2_check_fail_count": int(summary_row["phase2_check_fail_count"] or 0),
        "certificate_filter_fail_count": int(summary_row["certificate_filter_fail_count"] or 0),
        "abnormal_trade_count": int(summary_row["abnormal_trade_count"] or 0),
        "top_setups": top_setups,
        "top_active_plans": top_active_plans,
        "top_active_setups": top_active_setups,
        "recent_issues": recent_issues,
        "recent_fixes": recent_fixes,
        "recent_no_trade_notes": recent_no_trade_notes,
    }
