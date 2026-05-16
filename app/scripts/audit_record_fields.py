#!/usr/bin/env python3
"""Audit TopTrader record field usage from daily record containers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RECORDS_DIR = Path("05-daily-ops/records")
DEFAULT_OUTPUT_DIR = Path("05-daily-ops/summaries")
DEFAULT_OUTPUT_NAME = "TopTrader-field-audit.md"

DISPLAY_LABELS = {
    "trade_id": "交易 ID",
    "trade_date": "交易日期",
    "trade_time": "时间",
    "market": "市场",
    "instrument_code": "工具代码",
    "instrument_type": "工具类型",
    "underlying": "底层标的",
    "direction": "方向",
    "setup_type": "形态",
    "abc_grade": "机会等级",
    "entry_reason": "入场逻辑",
    "setup_validated": "形态确认",
    "entry_price": "入场价",
    "stop_loss": "止损",
    "target_price": "目标价",
    "position_size": "仓位",
    "emotion_state": "情绪状态",
    "rule_violation": "是否违规",
    "violation_note": "违规说明",
    "result": "结果",
    "review_note": "复盘备注",
    "event_id": "纪律事件 ID",
    "date": "日期",
    "time": "时间",
    "event_type": "事件类型",
    "severity": "严重级别",
    "trigger_reason": "触发原因",
    "action_taken": "采取动作",
    "follow_up_note": "后续说明",
    "linked_trade_id": "关联交易",
    "review_date": "复盘日期",
    "primary_instrument": "主要工具",
    "pnl": "当日盈亏",
    "trade_count": "交易数",
    "win_rate": "胜率",
    "max_loss_trade": "最大亏损单",
    "best_trade_note": "最好的一笔 / 最好动作",
    "worst_trade_note": "最差的一笔 / 最差问题",
    "market_issue": "行情问题",
    "execution_issue": "执行问题",
    "emotion_issue": "情绪问题",
    "risk_issue": "风控问题",
    "setup_issue": "形态问题",
    "next_day_one_fix": "明天只改 1 件事",
    "trial_day_number": "试跑日",
    "pre_market_done": "盘前完成",
    "intraday_record_complete": "盘中记录完成",
    "post_market_review_done": "盘后复盘完成",
    "impulsive_trade_detected": "出现冲动交易",
    "no_stop_loss_trade_detected": "出现无止损 / 止损失守",
    "emotional_overtrade_detected": "出现情绪化过度交易",
    "main_issue_of_day": "当日主要问题",
    "main_improvement_of_day": "当日主要改进",
}

TRADE_FIELDS = [
    "trade_id",
    "trade_date",
    "trade_time",
    "market",
    "instrument_code",
    "instrument_type",
    "underlying",
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
    "rule_violation",
    "violation_note",
    "result",
    "review_note",
]
RULE_EVENT_FIELDS = [
    "event_id",
    "date",
    "time",
    "market",
    "event_type",
    "severity",
    "trigger_reason",
    "action_taken",
    "follow_up_note",
    "linked_trade_id",
]
REVIEW_FIELDS = [
    "review_date",
    "market",
    "primary_instrument",
    "pnl",
    "trade_count",
    "win_rate",
    "max_loss_trade",
    "best_trade_note",
    "worst_trade_note",
    "market_issue",
    "execution_issue",
    "emotion_issue",
    "risk_issue",
    "setup_issue",
    "next_day_one_fix",
]
VALIDATION_FIELDS = [
    "trial_day_number",
    "date",
    "market",
    "primary_instrument",
    "pre_market_done",
    "intraday_record_complete",
    "post_market_review_done",
    "impulsive_trade_detected",
    "no_stop_loss_trade_detected",
    "emotional_overtrade_detected",
    "main_issue_of_day",
    "main_improvement_of_day",
]

LEGACY_FIELD_MAP = {
    "total_trades": "trade_count",
    "pnl_result": "pnl",
    "execution_score": "已废弃：不进入 v0.2",
    "main_good_action": "best_trade_note",
    "main_bad_action": "worst_trade_note",
    "key_lesson": "next_day_one_fix",
    "next_day_focus": "next_day_one_fix",
    "minimum_process_passed": "由三个完成度字段推导",
    "main_failure_point": "main_issue_of_day",
    "improvement_note": "main_improvement_of_day",
}


@dataclass
class FieldUsage:
    field: str
    filled: int
    total: int

    @property
    def rate(self) -> float:
        return self.filled / self.total if self.total else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit TopTrader daily record field usage.")
    parser.add_argument("record_files", nargs="*", type=Path)
    parser.add_argument("--records-dir", type=Path, default=DEFAULT_RECORDS_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"null", "none"}:
        return ""
    return text


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    return clean_text(value) != ""


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def field_label(field: str) -> str:
    return DISPLAY_LABELS.get(field, field)


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
        "review_date": review.get("review_date"),
        "market": review.get("market"),
        "primary_instrument": review.get("primary_instrument"),
        "pnl": review.get("pnl") or review.get("pnl_result"),
        "trade_count": review.get("trade_count") if review.get("trade_count") is not None else review.get("total_trades"),
        "win_rate": review.get("win_rate"),
        "max_loss_trade": review.get("max_loss_trade"),
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
    return {
        "trial_day_number": validation.get("trial_day_number"),
        "date": validation.get("date"),
        "market": validation.get("market"),
        "primary_instrument": validation.get("primary_instrument"),
        "pre_market_done": validation.get("pre_market_done"),
        "intraday_record_complete": validation.get("intraday_record_complete"),
        "post_market_review_done": validation.get("post_market_review_done"),
        "impulsive_trade_detected": validation.get("impulsive_trade_detected"),
        "no_stop_loss_trade_detected": validation.get("no_stop_loss_trade_detected"),
        "emotional_overtrade_detected": validation.get("emotional_overtrade_detected"),
        "main_issue_of_day": validation.get("main_issue_of_day") or validation.get("main_failure_point"),
        "main_improvement_of_day": validation.get("main_improvement_of_day") or validation.get("improvement_note"),
    }


def load_record(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    return {
        "path": path,
        "base": extract_yaml_block(content, "Base Fields"),
        "trades": [
            trade
            for trade in as_list(extract_yaml_block(content, "Trade Record Container").get("trade_records", []))
            if is_filled_trade(trade)
        ],
        "events": [
            event
            for event in as_list(extract_yaml_block(content, "Rule Event Container").get("rule_events", []))
            if is_filled_rule_event(event)
        ],
        "review_raw": extract_yaml_block(content, "Review Record Container").get("review_record", {}),
        "validation_raw": extract_yaml_block(content, "Trial Validation Record Container").get("trial_validation_record", {}),
    }


def usage_for(items: list[dict[str, Any]], fields: list[str]) -> list[FieldUsage]:
    total = len(items)
    return [FieldUsage(field, sum(1 for item in items if has_value(item.get(field))), total) for field in fields]


def recommendation(usage: FieldUsage, *, identity_field: bool = False) -> str:
    if usage.total == 0:
        return "暂无记录"
    if identity_field:
        return "保留为系统字段"
    if usage.rate >= 0.8:
        return "保留"
    if usage.rate >= 0.4:
        return "保留但观察"
    if usage.filled == 0:
        return "可考虑降为可选 / 暂藏"
    return "观察"


def usage_table(usages: list[FieldUsage], identity_fields: set[str] | None = None) -> str:
    identity_fields = identity_fields or set()
    lines = [
        "| 字段 | 中文 | 有值 / 记录 | 使用率 | 建议 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for usage in usages:
        rate = f"{usage.rate:.0%}" if usage.total else "-"
        lines.append(
            f"| `{usage.field}` | {field_label(usage.field)} | {usage.filled}/{usage.total} | {rate} | {recommendation(usage, identity_field=usage.field in identity_fields)} |"
        )
    return "\n".join(lines)


def collect_record_files(args: argparse.Namespace) -> list[Path]:
    if args.record_files:
        return sorted(args.record_files)
    if not args.records_dir.exists():
        return []
    return sorted(args.records_dir.glob("*.md"))


def render_markdown(records: list[dict[str, Any]]) -> str:
    trades = [trade for record in records for trade in record["trades"]]
    events = [event for record in records for event in record["events"]]
    reviews = [canonical_review(record["review_raw"]) for record in records]
    validations = [canonical_validation(record["validation_raw"]) for record in records]

    legacy_hits: list[str] = []
    for record in records:
        path = display_path(record["path"])
        for field in record["review_raw"]:
            if field in LEGACY_FIELD_MAP:
                legacy_hits.append(f"- `{path}`：`{field}` → `{LEGACY_FIELD_MAP[field]}`")
        for field in record["validation_raw"]:
            if field in LEGACY_FIELD_MAP:
                legacy_hits.append(f"- `{path}`：`{field}` → `{LEGACY_FIELD_MAP[field]}`")

    source_lines = "\n".join(f"- `{display_path(record['path'])}`" for record in records) or "- 未找到记录文件。"

    return f"""# TopTrader 结构化记录字段体检

## 来源记录
{source_lines}

## 记录规模
- 交易日记录：{len(records)}
- 真实交易记录：{len(trades)}
- 真实纪律事件：{len(events)}
- 复盘记录：{len(reviews)}
- 试跑验证记录：{len(validations)}

## 结论
- 当前字段层已经能支撑记录、归档和阶段总结，但记录仍少，不适合一次性大删字段。
- v0.2 字段收敛应先做“可选 / 暂藏 / 继续观察”，不要改底层 key。
- 最优先处理的是旧字段漂移和盘后复盘空字段，而不是新增字段。

## Trade Record 字段使用
{usage_table(usage_for(trades, TRADE_FIELDS), identity_fields={"trade_id", "trade_date", "market", "instrument_type", "underlying"})}

## Rule Event 字段使用
{usage_table(usage_for(events, RULE_EVENT_FIELDS), identity_fields={"event_id", "date", "market"})}

## Review Record 字段使用
{usage_table(usage_for(reviews, REVIEW_FIELDS), identity_fields={"review_date", "market", "primary_instrument"})}

## Trial Validation 字段使用
{usage_table(usage_for(validations, VALIDATION_FIELDS), identity_fields={"trial_day_number", "date", "market", "primary_instrument"})}

## 旧字段漂移
{chr(10).join(legacy_hits) if legacy_hits else "- 未发现旧字段漂移。"}

## v0.2 字段收敛建议
- Web 表单继续写 canonical 字段，不回写旧字段。
- 原始 Markdown 兼容旧字段读取，但新生成记录只使用 canonical 字段。
- Review 中 `win_rate`、`max_loss_trade`、`market_issue`、`setup_issue` 保持可选。
- Trial Validation 中三个检测字段保持可选但默认明确为 `false`，避免回看歧义。
- 暂时不删除 `target_price`、`emotion_state`、`review_note`，但在界面上可继续保持非必填。
"""


def main() -> None:
    args = parse_args()
    records = []
    for path in collect_record_files(args):
        if not path.exists():
            raise SystemExit(f"record file not found: {path}")
        try:
            records.append(load_record(path))
        except Exception as exc:
            raise SystemExit(f"failed to load {path}: {exc}") from exc

    output_path = args.output or args.output_dir / DEFAULT_OUTPUT_NAME
    if output_path.exists() and not args.force:
        raise SystemExit(f"output file already exists: {output_path}; use --force to overwrite")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(records), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
