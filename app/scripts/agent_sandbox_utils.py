#!/usr/bin/env python3
"""Shared helpers for Agent write-path sandbox replays."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import fcntl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import local_web  # noqa: E402
from database import dal  # noqa: E402

SAMPLES_PATH = Path(__file__).with_name("agent_trade_lifecycle_samples.json")
LOCK_PATH = PROJECT_ROOT / ".agent_sandbox.lock"


@dataclass(frozen=True)
class SandboxConfig:
    trade_date: str = "2099-01-03"
    market: str = "HK"
    trading_mode: str = "hsi_bull_bear_certificate"


def load_lifecycle_samples() -> dict:
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))


@contextmanager
def restored_sandbox(config: SandboxConfig) -> Iterator[None]:
    db_path = dal.DB_PATH
    state_path = local_web.STATE_FILE
    test_paths = sandbox_paths(config)

    LOCK_PATH.touch(exist_ok=True)
    with LOCK_PATH.open("r+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                db_backup = tmp / "toptrader.db.backup"
                state_backup = tmp / "state.env.backup"
                shutil.copy2(db_path, db_backup)
                state_existed = state_path.exists()
                if state_existed:
                    shutil.copy2(state_path, state_backup)

                try:
                    remove_paths(test_paths)
                    yield
                finally:
                    shutil.copy2(db_backup, db_path)
                    if state_existed:
                        shutil.copy2(state_backup, state_path)
                    elif state_path.exists():
                        state_path.unlink()
                    remove_paths(test_paths)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def sandbox_paths(config: SandboxConfig) -> list[Path]:
    return [
        local_web.RECORDS_DIR / f"{config.trade_date}-{config.market}-record-container.md",
        local_web.CLOSEOUTS_DIR / f"{config.trade_date}-{config.market}-closeout-draft.md",
        local_web.SUMMARIES_DIR / "TopTrader-trial-summary.md",
    ]


def create_sandbox_day(client, config: SandboxConfig) -> None:
    response = client.post(
        "/api/days",
        json={
            "tradeDate": config.trade_date,
            "currentState": "normal",
            "focus": "Agent sandbox write replay only.",
            "tradingMode": config.trading_mode,
        },
    )
    assert_ok(response.status_code, response.text, "create sandbox day")


def assert_ok(status_code: int, text: str, label: str) -> None:
    if status_code >= 400:
        raise AssertionError(f"{label} failed with HTTP {status_code}: {text}")


def assert_expected_subset(label: str, expected: list[str], actual: set[str]) -> None:
    missing = set(expected) - actual
    if missing:
        raise AssertionError(f"missing {label}: {sorted(missing)}; actual={sorted(actual)}")


def remove_paths(paths: list[Path]) -> None:
    for path in paths:
        if path.exists():
            path.unlink()
