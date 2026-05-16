#!/usr/bin/env python3
"""Initialize the SQLite database for TopTrader."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "database" / "toptrader.db"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS daily_record (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trial_day_number INTEGER,
  trade_date TEXT NOT NULL,
  market TEXT NOT NULL,
  primary_instrument TEXT NOT NULL,
  trial_mode TEXT NOT NULL DEFAULT 'production',
  operator TEXT NOT NULL,
  record_owner TEXT NOT NULL,
  source_record_path TEXT NOT NULL,

  trading_today INTEGER NOT NULL DEFAULT 1,
  pre_market_state TEXT NOT NULL DEFAULT 'normal',
  follow_normal_rules INTEGER NOT NULL DEFAULT 1,
  key_reminder TEXT NOT NULL DEFAULT '',
  pre_market_note TEXT NOT NULL DEFAULT '',

  trading_mode TEXT NOT NULL DEFAULT 'hsi_bull_bear_certificate',
  main_direction TEXT NOT NULL DEFAULT 'undecided',
  upper_pressure TEXT NOT NULL DEFAULT '',
  lower_support TEXT NOT NULL DEFAULT '',
  pivot_level TEXT NOT NULL DEFAULT '',
  no_trade_scenarios TEXT NOT NULL DEFAULT '',
  hard_stop_conditions TEXT NOT NULL DEFAULT '',
  current_state TEXT NOT NULL DEFAULT 'unset',
  post_market_summary TEXT NOT NULL DEFAULT '',
  capital_used REAL,
  profit_target_pct REAL,
  hk_watchlist TEXT NOT NULL DEFAULT '',
  us_watchlist TEXT NOT NULL DEFAULT '',

  opening_plan TEXT NOT NULL DEFAULT '',
  focus_setup TEXT NOT NULL DEFAULT '',
  open_30_key_signal TEXT NOT NULL DEFAULT '',
  certificate_filter_note TEXT NOT NULL DEFAULT '',
  abnormal_plan TEXT NOT NULL DEFAULT '',

  option_session_plan TEXT NOT NULL DEFAULT '',
  focus_tickers TEXT NOT NULL DEFAULT '',
  option_focus_setup TEXT NOT NULL DEFAULT '',
  option_entry_signal TEXT NOT NULL DEFAULT '',
  option_contract_filter TEXT NOT NULL DEFAULT '',
  option_risk_plan TEXT NOT NULL DEFAULT '',
  option_event_risk_plan TEXT NOT NULL DEFAULT '',

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_record_trade_date
  ON daily_record(trade_date);

CREATE INDEX IF NOT EXISTS idx_daily_record_trade_date_market
  ON daily_record(trade_date, market);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_record_trade_date_market_unique
  ON daily_record(trade_date, market);

CREATE INDEX IF NOT EXISTS idx_daily_record_trading_mode
  ON daily_record(trading_mode);

CREATE TABLE IF NOT EXISTS trade_record (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  daily_record_id INTEGER NOT NULL,
  trade_id TEXT NOT NULL,
  source_order INTEGER NOT NULL DEFAULT 0,

  trade_date TEXT NOT NULL,
  trade_time TEXT NOT NULL DEFAULT '',
  market TEXT NOT NULL,
  instrument_code TEXT NOT NULL DEFAULT '',
  certificate_side TEXT NOT NULL DEFAULT '',
  instrument_type TEXT NOT NULL DEFAULT '',
  underlying TEXT NOT NULL DEFAULT '',
  direction TEXT NOT NULL DEFAULT '',
  session_window TEXT NOT NULL DEFAULT '',
  setup_type TEXT NOT NULL DEFAULT '',
  abc_grade TEXT NOT NULL DEFAULT '',
  setup_score REAL,
  entry_reason TEXT NOT NULL DEFAULT '',
  setup_validated INTEGER,
  direction_clear INTEGER,
  location_ok INTEGER,
  confirmation_ok INTEGER,
  risk_clear INTEGER,
  certificate_filter_passed INTEGER,
  abnormal_scenario TEXT NOT NULL DEFAULT 'none',

  entry_price REAL,
  stop_loss REAL,
  target_price REAL,
  position_size TEXT NOT NULL DEFAULT '',
  exit_time TEXT NOT NULL DEFAULT '',
  exit_price REAL,
  pnl_amount REAL,
  risk_reward_ratio REAL,
  exit_reason TEXT NOT NULL DEFAULT '',

  followed_plan INTEGER NOT NULL DEFAULT 1,
  emotion_state TEXT NOT NULL DEFAULT '',
  pre_trade_emotion TEXT NOT NULL DEFAULT '',
  post_trade_emotion TEXT NOT NULL DEFAULT 'unset',
  rule_violation INTEGER NOT NULL DEFAULT 0,
  violation_note TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT '',
  screenshot_note TEXT NOT NULL DEFAULT '',
  review_note TEXT NOT NULL DEFAULT '',

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (daily_record_id) REFERENCES daily_record(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_record_daily_trade_id
  ON trade_record(daily_record_id, trade_id);

CREATE INDEX IF NOT EXISTS idx_trade_record_daily_record_id
  ON trade_record(daily_record_id);

CREATE INDEX IF NOT EXISTS idx_trade_record_trade_date
  ON trade_record(trade_date);

CREATE INDEX IF NOT EXISTS idx_trade_record_setup_type
  ON trade_record(setup_type);

CREATE INDEX IF NOT EXISTS idx_trade_record_underlying
  ON trade_record(underlying);

CREATE INDEX IF NOT EXISTS idx_trade_record_trade_id
  ON trade_record(trade_id);

CREATE TABLE IF NOT EXISTS rule_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  daily_record_id INTEGER NOT NULL,
  event_id TEXT NOT NULL,
  source_order INTEGER NOT NULL DEFAULT 0,

  event_date TEXT NOT NULL,
  event_time TEXT NOT NULL DEFAULT '',
  market TEXT NOT NULL,
  event_type TEXT NOT NULL DEFAULT '',
  severity TEXT NOT NULL DEFAULT '',
  trigger_reason TEXT NOT NULL DEFAULT '',
  action_taken TEXT NOT NULL DEFAULT '',
  follow_up_note TEXT NOT NULL DEFAULT '',
  linked_trade_id TEXT NOT NULL DEFAULT '',

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (daily_record_id) REFERENCES daily_record(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rule_event_daily_event_id
  ON rule_event(daily_record_id, event_id);

CREATE INDEX IF NOT EXISTS idx_rule_event_daily_record_id
  ON rule_event(daily_record_id);

CREATE INDEX IF NOT EXISTS idx_rule_event_event_date
  ON rule_event(event_date);

CREATE INDEX IF NOT EXISTS idx_rule_event_event_type
  ON rule_event(event_type);

CREATE INDEX IF NOT EXISTS idx_rule_event_event_id
  ON rule_event(event_id);

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

CREATE TABLE IF NOT EXISTS daily_review (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  daily_record_id INTEGER NOT NULL UNIQUE,

  review_date TEXT NOT NULL,
  market TEXT NOT NULL,
  primary_instrument TEXT NOT NULL,

  pnl_text TEXT NOT NULL DEFAULT '',
  pnl_amount REAL,
  trade_count INTEGER,
  win_rate TEXT NOT NULL DEFAULT '',
  max_loss_trade TEXT NOT NULL DEFAULT '',
  best_trade_note TEXT NOT NULL DEFAULT '',
  worst_trade_note TEXT NOT NULL DEFAULT '',
  market_issue TEXT NOT NULL DEFAULT '',
  execution_issue TEXT NOT NULL DEFAULT '',
  emotion_issue TEXT NOT NULL DEFAULT '',
  risk_issue TEXT NOT NULL DEFAULT '',
  setup_issue TEXT NOT NULL DEFAULT '',
  next_day_one_fix TEXT NOT NULL DEFAULT '',

  pre_market_done INTEGER NOT NULL DEFAULT 0,
  intraday_record_complete INTEGER NOT NULL DEFAULT 0,
  post_market_review_done INTEGER NOT NULL DEFAULT 0,
  impulsive_trade_detected INTEGER NOT NULL DEFAULT 0,
  no_stop_loss_trade_detected INTEGER NOT NULL DEFAULT 0,
  emotional_overtrade_detected INTEGER NOT NULL DEFAULT 0,
  no_trade_day INTEGER NOT NULL DEFAULT 0,
  no_trade_note TEXT NOT NULL DEFAULT '',
  main_issue_of_day TEXT NOT NULL DEFAULT '',
  main_improvement_of_day TEXT NOT NULL DEFAULT '',
  minimum_process_passed INTEGER NOT NULL DEFAULT 0,

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (daily_record_id) REFERENCES daily_record(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_daily_review_review_date
  ON daily_review(review_date);

CREATE INDEX IF NOT EXISTS idx_daily_review_minimum_process_passed
  ON daily_review(minimum_process_passed);

CREATE TABLE IF NOT EXISTS workspace_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  current_market TEXT NOT NULL DEFAULT 'HK',
  current_trade_date TEXT NOT NULL,
  theme TEXT NOT NULL DEFAULT 'dark',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the TopTrader SQLite database.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Database path. Defaults to {DEFAULT_DB_PATH.relative_to(ROOT)}.",
    )
    return parser.parse_args()


def init_db(db_path: Path = DEFAULT_DB_PATH) -> Path:
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        daily_record_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(daily_record)").fetchall()
        }
        if "hk_watchlist" not in daily_record_columns:
            conn.execute("ALTER TABLE daily_record ADD COLUMN hk_watchlist TEXT NOT NULL DEFAULT ''")
        if "us_watchlist" not in daily_record_columns:
            conn.execute("ALTER TABLE daily_record ADD COLUMN us_watchlist TEXT NOT NULL DEFAULT ''")
        conn.execute(
            """
            INSERT INTO workspace_state (id, current_market, current_trade_date, theme, updated_at)
            VALUES (1, 'HK', DATE('now'), 'dark', CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO NOTHING
            """
        )
        conn.commit()
    return db_path


def main() -> None:
    args = parse_args()
    db_path = init_db(args.db_path)
    print(db_path)


if __name__ == "__main__":
    main()
