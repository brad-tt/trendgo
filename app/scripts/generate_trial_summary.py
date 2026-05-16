#!/usr/bin/env python3
"""Generate a TopTrader trial-stage summary from daily record containers."""

from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RECORDS_DIR = Path("05-daily-ops/records")
DEFAULT_OUTPUT_DIR = Path("05-daily-ops/summaries")
DEFAULT_OUTPUT_NAME = "TopTrader-trial-summary.md"

DISPLAY_LABELS = {
    "normal": "正常",
    "tired": "疲惫",
    "irritated": "烦躁",
    "sleep_poor": "睡眠差",
    "unstable": "状态不稳",
    "other": "其他",
    "long": "做多 / 牛证",
    "short": "做空 / 熊证",
    "opening_breakout": "开盘确认突破",
    "pullback_reclaim": "回踩确认再启动",
    "A": "A 级",
    "B": "B 级",
    "C": "C 级",
    "stable": "稳定",
    "anxious": "焦虑 / 急躁",
    "revenge": "报复性冲动",
    "impulsive": "冲动",
    "win": "盈利",
    "loss": "亏损",
    "breakeven": "持平",
    "positive": "盈利",
    "negative": "亏损",
    "flat": "持平",
    "rule_violation": "规则违规",
    "emotion_trigger": "情绪触发",
    "forced_pause": "强制暂停",
    "forced_stop": "当日停手",
    "overtrade_signal": "过度交易信号",
    "warning": "预警",
    "stop": "暂停 / 中断",
    "critical": "严重",
    "HSI bull/bear certificate": "恒指牛熊证",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a TopTrader trial-stage summary from daily record container markdown files."
    )
    parser.add_argument(
        "record_files",
        nargs="*",
        type=Path,
        help="Optional explicit record container files. Defaults to all markdown files under --records-dir.",
    )
    parser.add_argument(
        "--records-dir",
        type=Path,
        default=DEFAULT_RECORDS_DIR,
        help=f"Directory to scan when record files are not provided. Defaults to {DEFAULT_RECORDS_DIR}.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=f"Optional explicit output file path. Defaults to {DEFAULT_OUTPUT_DIR / DEFAULT_OUTPUT_NAME}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory when --output is not provided. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"null", "none"}:
        return ""
    return text


def display_label(value: Any, default: str = "未填写") -> str:
    text = clean_text(value)
    if not text:
        return default
    return DISPLAY_LABELS.get(text, text)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def bool_text(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未填写"


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value is True
    return clean_text(value) != ""


def extract_yaml_block(content: str, heading: str) -> Any:
    marker = f"## {heading}"
    start = content.find(marker)
    if start == -1:
        raise ValueError(f"missing section: {heading}")
    fence_start = content.find("```yaml", start)
    if fence_start == -1:
        raise ValueError(f"missing yaml block for section: {heading}")
    block_start = fence_start + len("```yaml")
    fence_end = content.find("```", block_start)
    if fence_end == -1:
        raise ValueError(f"unterminated yaml block for section: {heading}")
    block = content[block_start:fence_end].strip()
    return yaml.safe_load(block) or {}


def as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def is_filled_trade(trade: dict[str, Any]) -> bool:
    meaningful_keys = [
        "trade_time",
        "instrument_code",
        "direction",
        "setup_type",
        "abc_grade",
        "entry_reason",
        "setup_validated",
        "entry_price",
        "stop_loss",
        "target_price",
        "position_size",
        "emotion_state",
        "violation_note",
        "result",
        "review_note",
    ]
    return any(has_value(trade.get(key)) for key in meaningful_keys) or trade.get("rule_violation") is True


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
        "pnl": review.get("pnl") or review.get("pnl_result"),
        "trade_count": review.get("trade_count") if review.get("trade_count") is not None else review.get("total_trades"),
        "best_trade_note": review.get("best_trade_note") or review.get("main_good_action"),
        "worst_trade_note": review.get("worst_trade_note") or review.get("main_bad_action"),
        "market_issue": review.get("market_issue"),
        "execution_issue": review.get("execution_issue"),
        "emotion_issue": review.get("emotion_issue"),
        "risk_issue": review.get("risk_issue"),
        "setup_issue": review.get("setup_issue"),
        "next_day_one_fix": review.get("next_day_one_fix") or review.get("next_day_focus") or review.get("key_lesson"),
    }


def canonical_validation(validation: dict[str, Any]) -> dict[str, Any]:
    minimum_process = validation.get("minimum_process_passed")
    if minimum_process is None:
        minimum_process = (
            validation.get("pre_market_done") is True
            and validation.get("intraday_record_complete") is True
            and validation.get("post_market_review_done") is True
        )
    return {
        "pre_market_done": validation.get("pre_market_done"),
        "intraday_record_complete": validation.get("intraday_record_complete"),
        "post_market_review_done": validation.get("post_market_review_done"),
        "impulsive_trade_detected": validation.get("impulsive_trade_detected"),
        "no_stop_loss_trade_detected": validation.get("no_stop_loss_trade_detected"),
        "emotional_overtrade_detected": validation.get("emotional_overtrade_detected"),
        "no_trade_day": validation.get("no_trade_day") is True,
        "no_trade_note": validation.get("no_trade_note"),
        "minimum_process_passed": minimum_process,
        "main_issue_of_day": validation.get("main_issue_of_day") or validation.get("main_failure_point"),
        "main_improvement_of_day": validation.get("main_improvement_of_day") or validation.get("improvement_note"),
    }


def load_record(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    base = extract_yaml_block(content, "Base Fields")
    pre_market = extract_yaml_block(content, "Pre-Market Status").get("pre_market_status", {})
    trades = as_list(extract_yaml_block(content, "Trade Record Container").get("trade_records", []))
    events = as_list(extract_yaml_block(content, "Rule Event Container").get("rule_events", []))
    review = canonical_review(extract_yaml_block(content, "Review Record Container").get("review_record", {}))
    validation = canonical_validation(
        extract_yaml_block(content, "Trial Validation Record Container").get("trial_validation_record", {})
    )
    return {
        "path": path,
        "base": base,
        "pre_market": pre_market,
        "trades": [trade for trade in trades if is_filled_trade(trade)],
        "events": [event for event in events if is_filled_rule_event(event)],
        "review": review,
        "validation": validation,
    }


def record_sort_key(record: dict[str, Any]) -> tuple[int, str]:
    day = record["base"].get("day_number")
    try:
        day_number = int(day)
    except (TypeError, ValueError):
        day_number = 9999
    return day_number, clean_text(record["base"].get("trade_date"))


def required_missing(data: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if not has_value(data.get(key))]


def number_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: float | None) -> str:
    if value is None:
        return "未填写"
    if math.isfinite(value) and value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def trade_pnl_total(trades: list[dict[str, Any]]) -> float | None:
    pnl_values = [number_value(trade.get("pnl_amount")) for trade in trades]
    pnl_values = [value for value in pnl_values if value is not None]
    if not pnl_values:
        return None
    return sum(pnl_values)


def normalized_summary_text(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    return re.sub(r"^\s*\d+[\.\)、:：-]?\s*", "", text)


def is_meaningful_summary_text(value: Any) -> bool:
    text = normalized_summary_text(value)
    if not text:
        return False
    compact = "".join(char for char in text if char.isalnum())
    if len(compact) < 4:
        return False
    if compact.isdigit():
        return False
    return True


def summary_text_or_empty(value: Any) -> str:
    return normalized_summary_text(value) if is_meaningful_summary_text(value) else ""


def issue_text_for_summary(validation: dict[str, Any]) -> str:
    if validation.get("no_trade_day") is True:
        return summary_text_or_empty(validation.get("no_trade_note"))
    return summary_text_or_empty(validation.get("main_issue_of_day"))


def daily_pnl_for_summary(record: dict[str, Any]) -> str:
    trades = record["trades"]
    review = record["review"]
    validation = record["validation"]
    derived_pnl = trade_pnl_total(trades)
    if derived_pnl is not None:
        return format_number(derived_pnl)
    if validation.get("no_trade_day") is True:
        return "0"
    if not trades:
        return "未填写"

    review_pnl = clean_text(review.get("pnl"))
    if review_pnl in {"positive", "negative", "flat"}:
        return display_label(review_pnl)

    review_pnl_number = number_value(review_pnl)
    review_trade_count = clean_text(review.get("trade_count"))
    if review_pnl_number is not None and review_trade_count == str(len(trades)):
        return format_number(review_pnl_number)
    return "未填写"


def choose_next_priority(
    *,
    total_days: int,
    process_passed: int,
    emotional_overtrade_days: int,
    rule_events: int,
    missing_review_days: int,
) -> str:
    if total_days and process_passed < total_days:
        return "先降低每日流程摩擦，确保盘前、盘中、盘后动作每天能跑完。"
    if emotional_overtrade_days:
        return "优先强化盈利后和第一笔交易后的暂停复核，防止利润扩大冲动变成低质量加单。"
    if missing_review_days:
        return "优先收敛盘后复盘字段，让每天至少留下一个可比较的结论。"
    if rule_events:
        return "继续细化纪律事件触发阈值，确认 forced_pause / forced_stop 是否足够清晰。"
    return "维持当前轻量工作台，下一轮重点观察字段是否需要继续减法。"


def render_markdown(records: list[dict[str, Any]]) -> str:
    if not records:
        return "# TopTrader 试跑阶段总结\n\n未找到可汇总的交易日记录。\n"

    total_days = len(records)
    trade_count = sum(len(record["trades"]) for record in records)
    event_count = sum(len(record["events"]) for record in records)
    process_passed = sum(1 for record in records if record["validation"].get("minimum_process_passed") is True)
    pre_market_done = sum(1 for record in records if record["validation"].get("pre_market_done") is True)
    intraday_done = sum(1 for record in records if record["validation"].get("intraday_record_complete") is True)
    review_done = sum(1 for record in records if record["validation"].get("post_market_review_done") is True)
    emotional_days = sum(1 for record in records if record["validation"].get("emotional_overtrade_detected") is True)
    impulsive_days = sum(1 for record in records if record["validation"].get("impulsive_trade_detected") is True)
    no_stop_days = sum(1 for record in records if record["validation"].get("no_stop_loss_trade_detected") is True)
    violation_count = sum(1 for record in records for trade in record["trades"] if trade.get("rule_violation") is True)

    result_counter: Counter[str] = Counter()
    event_type_counter: Counter[str] = Counter()
    issue_lines: list[str] = []
    improvement_lines: list[str] = []
    missing_review_days = 0

    for record in records:
        day = clean_text(record["base"].get("day_number")) or "?"
        for trade in record["trades"]:
            result_counter[clean_text(trade.get("result")) or "未填写"] += 1
        for event in record["events"]:
            event_type_counter[clean_text(event.get("event_type")) or "未填写"] += 1

        review_missing = required_missing(
            record["review"],
            ["pnl", "trade_count", "best_trade_note", "worst_trade_note", "execution_issue", "emotion_issue", "risk_issue", "next_day_one_fix"],
        )
        if review_missing:
            missing_review_days += 1
        main_issue = issue_text_for_summary(record["validation"])
        if main_issue:
            issue_lines.append(f"- Day {day}：{main_issue}")
        improvement = summary_text_or_empty(record["validation"].get("main_improvement_of_day"))
        if improvement:
            improvement_lines.append(f"- Day {day}：{improvement}")

    next_priority = choose_next_priority(
        total_days=total_days,
        process_passed=process_passed,
        emotional_overtrade_days=emotional_days,
        rule_events=event_count,
        missing_review_days=missing_review_days,
    )

    source_lines = "\n".join(f"- `{display_path(record['path'])}`" for record in records)
    result_mix = " / ".join(f"{display_label(key)} {value}" for key, value in sorted(result_counter.items())) or "无真实交易结果"
    event_mix = " / ".join(f"{display_label(key)} {value}" for key, value in sorted(event_type_counter.items())) or "无纪律事件"

    day_rows = []
    for record in records:
        base = record["base"]
        validation = record["validation"]
        main_issue = issue_text_for_summary(validation)
        main_improvement = summary_text_or_empty(validation.get("main_improvement_of_day"))
        day_rows.append(
            "| "
            + " | ".join(
                [
                    clean_text(base.get("day_number")) or "?",
                    clean_text(base.get("trade_date")) or "未填写",
                    str(len(record["trades"])),
                    str(len(record["events"])),
                    bool_text(validation.get("minimum_process_passed")),
                    daily_pnl_for_summary(record),
                    main_issue or "未填写",
                    main_improvement or "未填写",
                ]
            )
            + " |"
        )

    return f"""# TopTrader 试跑阶段总结

## 来源记录
{source_lines}

## 总体结论
- 本轮按现有记录视作试跑完成；实际汇总交易日：{total_days} 天。
- 最小流程通过：{process_passed}/{total_days} 天。
- 盘前完成：{pre_market_done}/{total_days} 天；盘中记录完成：{intraday_done}/{total_days} 天；盘后复盘完成：{review_done}/{total_days} 天。
- 真实交易数：{trade_count}；纪律事件数：{event_count}；交易级违规标记：{violation_count}。
- 交易结果分布：{result_mix}。
- 纪律事件类型：{event_mix}。

## 协议五问
1. 这套 MVP 有没有真的被用起来？
   - 已经能通过本地记录容器、结构化字段、盘后草稿形成闭环；但流程完成度仍要看后续真实交易日能否稳定保持。
2. 哪些文件 / 能力必须保留？
   - 保留本地工作台、Trade Record、Rule Event、Review Record、Trial Validation Record、中文归档草稿。
3. 哪些文件 / 字段太重或重复？
   - 优先观察盘后复盘必填项和 Trial Validation 完成度字段；若继续出现空字段，再做字段减法。
4. 最大的执行问题有没有被看清？
   - 当前最明确的信号是盈利后继续加单 / 情绪化过度交易，以及流程未完成时数据会失真。
5. 下一轮最该优先优化哪一项？
   - {next_priority}

## 每日横向表
| Day | 日期 | 交易数 | 纪律事件 | 最小流程通过 | 当日盈亏 | 当日主要问题 | 当日主要改进 |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
{chr(10).join(day_rows)}

## 主要问题记录
{chr(10).join(issue_lines) if issue_lines else "- 暂无明确填写的当日主要问题。"}

## 改进动作记录
{chr(10).join(improvement_lines) if improvement_lines else "- 暂无明确填写的当日主要改进。"}

## 下一步建议
- 把 TopTrader 从“试跑验证”推进到“结构化记录层 v0.2 字段收敛”。
- 先不引入行情或多日 dashboard，继续保持 SQLite 为主查询源、Markdown 为本地归档副本。
- v0.2 的重点不是加字段，而是减少空字段、明确必填项、让归档输出更贴近真实盘后语言。
"""


def collect_record_files(args: argparse.Namespace) -> list[Path]:
    if args.record_files:
        return sorted(args.record_files)
    if not args.records_dir.exists():
        return []
    return sorted(args.records_dir.glob("*.md"))


def main() -> None:
    args = parse_args()
    record_files = collect_record_files(args)
    records = []
    for path in record_files:
        if not path.exists():
            raise SystemExit(f"record file not found: {path}")
        try:
            records.append(load_record(path))
        except Exception as exc:
            raise SystemExit(f"failed to load {path}: {exc}") from exc

    records = sorted(records, key=record_sort_key)
    output_path = args.output or args.output_dir / DEFAULT_OUTPUT_NAME
    if output_path.exists() and not args.force:
        raise SystemExit(f"output file already exists: {output_path}; use --force to overwrite")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(records), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
