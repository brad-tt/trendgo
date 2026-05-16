#!/usr/bin/env python3
"""Workspace state and path helpers for TopTrader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from core.utils import clean_text


@dataclass
class AppState:
    day: str = ""
    trade_date: str = date.today().isoformat()
    state: str = "normal"
    focus: str = ""
    current_record_path: str = ""
    current_closeout_path: str = ""
    current_summary_path: str = ""
    current_audit_path: str = ""
    review_hub_window: str = "5"
    review_hub_sample_filter: str = "all"


def load_state(
    *,
    state_file: Path,
    normalize_review_hub_window,
    normalize_review_hub_sample_filter,
) -> AppState:
    state = AppState()
    if not state_file.exists():
        return state
    for line in state_file.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if hasattr(state, key):
            setattr(state, key, value.replace("\\n", "\n"))
    state.review_hub_window = normalize_review_hub_window(state.review_hub_window)
    state.review_hub_sample_filter = normalize_review_hub_sample_filter(state.review_hub_sample_filter)
    return state


def save_state(*, state: AppState, state_file: Path) -> None:
    def one_line(value: str) -> str:
        return value.replace("\n", "\\n")

    lines = [
        f"day={one_line(state.day)}",
        f"trade_date={one_line(state.trade_date)}",
        f"state={one_line(state.state)}",
        f"focus={one_line(state.focus)}",
        f"current_record_path={one_line(state.current_record_path)}",
        f"current_closeout_path={one_line(state.current_closeout_path)}",
        f"current_summary_path={one_line(state.current_summary_path)}",
        f"current_audit_path={one_line(state.current_audit_path)}",
        f"review_hub_window={one_line(state.review_hub_window)}",
        f"review_hub_sample_filter={one_line(state.review_hub_sample_filter)}",
    ]
    state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_recent_files(directory: Path, suffix: str, limit: int = 8) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(suffix), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def find_files(directory: Path, suffix: str) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(suffix))


def parse_day_number(value: Any) -> int | None:
    try:
        return int(clean_text(value))
    except ValueError:
        return None


def parse_iso_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def next_weekday(value: date) -> date:
    next_date = value + timedelta(days=1)
    while next_date.weekday() >= 5:
        next_date += timedelta(days=1)
    return next_date


def suggested_start_day_values(
    *,
    state: AppState,
    record_paths: list[Path],
    load_record: Callable[[Path], dict[str, Any]],
) -> tuple[str, str]:
    best_day: int | None = None
    best_date: date | None = None
    for path in record_paths:
        try:
            base = load_record(path)["base"]
        except Exception:
            continue
        day_number = parse_day_number(base.get("day_number"))
        trade_date = parse_iso_date(base.get("trade_date"))
        if day_number is None:
            continue
        if best_day is None or day_number > best_day:
            best_day = day_number
            best_date = trade_date

    if best_day is not None:
        suggested_date = next_weekday(best_date or date.today())
        return str(best_day + 1), suggested_date.isoformat()

    fallback_day = clean_text(state.day) or "1"
    fallback_date = clean_text(state.trade_date) or date.today().isoformat()
    return fallback_day, fallback_date


def format_trade_date(value: Any) -> str:
    trade_date = parse_iso_date(value)
    text = clean_text(value)
    if not trade_date:
        return text or "未设置"
    weekday = "一二三四五六日"[trade_date.weekday()]
    return f"{trade_date.isoformat()} 周{weekday}"


def record_day_number(path: Path, *, load_record: Callable[[Path], dict[str, Any]]) -> int | None:
    try:
        return parse_day_number(load_record(path)["base"].get("day_number"))
    except Exception:
        return None


def active_record_path(record_paths: list[Path], *, load_record: Callable[[Path], dict[str, Any]]) -> Path | None:
    best_path: Path | None = None
    best_day: int | None = None
    for path in record_paths:
        day_number = record_day_number(path, load_record=load_record)
        if day_number is None:
            continue
        if best_day is None or day_number > best_day:
            best_day = day_number
            best_path = path
    if best_path:
        return best_path
    if not record_paths:
        return None
    return max(record_paths, key=lambda path: path.stat().st_mtime)


def latest_record_path(records_dir: Path, *, load_record: Callable[[Path], dict[str, Any]]) -> Path | None:
    records = find_files(records_dir, "*.md")
    active = active_record_path(records, load_record=load_record)
    if active:
        return active
    recent = find_recent_files(records_dir, "*.md", limit=1)
    return recent[0] if recent else None


def is_active_record_path(path: Path | None, record_paths: list[Path], *, load_record: Callable[[Path], dict[str, Any]]) -> bool:
    if not path:
        return False
    active = active_record_path(record_paths, load_record=load_record)
    return bool(active and path.resolve() == active.resolve())


def relative_path(path: Path, *, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


def resolve_path(raw_path: str, *, root: Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("Path must stay inside the TopTrader project.") from exc
    return path


def current_record_path(state: AppState, *, root: Path) -> Path | None:
    if not state.current_record_path:
        return None
    path = resolve_path(state.current_record_path, root=root)
    return path if path.exists() else None


def current_closeout_path(state: AppState, *, root: Path) -> Path | None:
    if not state.current_closeout_path:
        return None
    path = resolve_path(state.current_closeout_path, root=root)
    return path if path.exists() else None


def current_summary_path(state: AppState, *, root: Path) -> Path | None:
    if not state.current_summary_path:
        return None
    path = resolve_path(state.current_summary_path, root=root)
    return path if path.exists() else None


def current_audit_path(state: AppState, *, root: Path) -> Path | None:
    if not state.current_audit_path:
        return None
    path = resolve_path(state.current_audit_path, root=root)
    return path if path.exists() else None


def update_state_from_record(
    *,
    state: AppState,
    path: Path,
    record: dict[str, Any],
    closeout_path_from_base,
    relative_path_func,
) -> None:
    base = record["base"]
    pre_market = record["pre_market"]
    state.current_record_path = relative_path_func(path)
    state.day = clean_text(base.get("day_number"))
    state.trade_date = clean_text(base.get("trade_date")) or state.trade_date
    state.state = clean_text(pre_market.get("state")) or state.state
    state.focus = clean_text(pre_market.get("key_reminder")) or state.focus
    closeout_path = closeout_path_from_base(base)
    state.current_closeout_path = relative_path_func(closeout_path) if closeout_path.exists() else ""
