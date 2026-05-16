#!/usr/bin/env python3
"""Generate a TopTrader end-of-day closeout draft from a single daily record container."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from core import record_checks

DEFAULT_OUTPUT_DIR = Path("05-daily-ops/closeouts")
DISPLAY_LABELS = {
    "normal": "正常",
    "tired": "疲惫",
    "irritated": "烦躁",
    "sleep_poor": "睡眠差",
    "unstable": "状态不稳",
    "other": "其他",
    "hsi_bull_bear_certificate": "恒指牛熊证",
    "us_stock_options": "美股期权",
    "undecided": "未定",
    "observe": "观望",
    "unset": "未填",
    "impatient": "偏急",
    "defiant": "不服",
    "unfit": "不适合交易",
    "breakout_if_confirmed": "只做确认后突破",
    "pullback_only": "优先等回踩确认",
    "observe_first": "先观察，不抢第一笔",
    "clear_no_trade": "不清晰就不做",
    "wait_first_15m": "先等 15 分钟",
    "trend_continuation": "趋势延续",
    "avoid_event_risk": "避开事件风险",
    "bull": "牛证",
    "bear": "熊证",
    "call": "Call",
    "put": "Put",
    "long": "做多",
    "short": "做空",
    "opening_30m": "开盘前 30 分钟",
    "mid_session": "盘中常规时段",
    "late_session": "尾段 / 后段",
    "opening_breakout": "开盘突破",
    "pullback_reclaim": "回踩确认",
    "clear_observe": "明确观望",
    "orb_continuation": "开盘区间突破延续",
    "vwap_reclaim": "VWAP 收复",
    "trend_pullback": "趋势回踩",
    "support_reversal": "支撑反转",
    "failed_breakdown": "跌破失败反转",
    "false_breakout_chase": "假突破误追",
    "reverse_after_stop": "止损后反手",
    "emotional_trade": "情绪单",
    "revenge_trade": "报复单",
    "itchy_hand_trade": "手痒单",
    "profit_giveback": "盈利后回吐",
    "recovery_after_losing_streak": "连亏后恢复",
    "iv_chase": "IV 拉高后追单",
    "A": "A 级",
    "B": "B 级",
    "C": "C 级",
    "stable": "稳定",
    "anxious": "焦虑 / 急躁",
    "revenge": "报复性冲动",
    "impulsive": "冲动",
    "rushed": "急",
    "fomo": "怕错过",
    "recover_loss": "想翻本",
    "satisfied": "满意",
    "regret": "后悔",
    "win": "盈利",
    "loss": "亏损",
    "breakeven": "持平",
    "positive": "盈利",
    "negative": "亏损",
    "flat": "持平",
    "good": "好",
    "average": "一般",
    "poor": "差",
    "rule_violation": "规则违规",
    "emotion_trigger": "情绪触发",
    "forced_pause": "强制暂停",
    "forced_stop": "当日停手",
    "overtrade_signal": "过度交易信号",
    "warning": "预警",
    "stop": "暂停 / 中断",
    "critical": "严重",
    "none": "无",
    "open_whipsaw": "开盘剧烈乱甩",
    "stop_then_reverse": "止损后立刻反向拉回",
    "low_quality_lure": "连续低质量机会诱惑",
    "iv_spike": "IV 突然拉高",
    "spread_widen": "价差突然变宽",
    "news_event": "消息 / 财报事件",
    "bull_bear_certificate": "牛熊证",
    "stock_option": "股票期权",
    "HSI": "恒生指数",
    "TSLA": "TSLA",
    "NVDA": "NVDA",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "AAPL": "AAPL",
    "AMD": "AMD",
    "META": "META",
    "MSFT": "MSFT",
    "HSI bull/bear certificate": "恒指牛熊证",
    "US stock options": "美股期权",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an end-of-day closeout draft from a daily record container markdown file."
    )
    parser.add_argument(
        "record_file",
        type=Path,
        help="Path to a single-day record container markdown file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional explicit output file path. Defaults to 05-daily-ops/closeouts/<derived-name>.md",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional explicit output directory. Output filename still follows the default derived naming convention.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def extract_yaml_block(content: str, heading: str) -> Any:
    marker = f"## {heading}"
    start = content.find(marker)
    if start == -1:
        raise SystemExit(f"missing section: {heading}")
    fence_start = content.find("```yaml", start)
    if fence_start == -1:
        raise SystemExit(f"missing yaml block for section: {heading}")
    block_start = fence_start + len("```yaml")
    fence_end = content.find("```", block_start)
    if fence_end == -1:
        raise SystemExit(f"unterminated yaml block for section: {heading}")
    block = content[block_start:fence_end].strip()
    return yaml.safe_load(block)


def extract_optional_yaml_block(content: str, heading: str) -> Any:
    try:
        return extract_yaml_block(content, heading)
    except SystemExit:
        return {}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"null", "none"}:
        return ""
    return text


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


def format_number_text(value: Any) -> str:
    numeric = number_value(value)
    if numeric is None:
        return clean_text(value)
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def total_pnl_text(trades: list[dict[str, Any]]) -> str:
    values = [number_value(trade.get("pnl_amount")) for trade in trades]
    values = [value for value in values if value is not None]
    if not values:
        return ""
    return format_number_text(sum(values))


def sentence(value: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    return text if text[-1] in ".!?。！？" else f"{text}。"


def bool_text(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未填写"


def display_label(value: Any, default: str = "未填写") -> str:
    text = clean_text(value)
    if not text:
        return default
    return DISPLAY_LABELS.get(text, text)


def normalize_trading_mode(value: Any) -> str:
    text = clean_text(value)
    return text if text in {"hsi_bull_bear_certificate", "us_stock_options"} else "hsi_bull_bear_certificate"


def playbook_title_for_mode(trading_mode: Any) -> str:
    return "美股期权专项卡" if normalize_trading_mode(trading_mode) == "us_stock_options" else "恒指专项卡"


def filter_label_for_mode(trading_mode: Any) -> str:
    return "期权合约过滤" if normalize_trading_mode(trading_mode) == "us_stock_options" else "牛熊证过滤"


def trade_filter_label(trade: dict[str, Any], trading_mode: Any) -> str:
    instrument_type = clean_text(trade.get("instrument_type"))
    side = clean_text(trade.get("certificate_side"))
    underlying = clean_text(trade.get("underlying"))
    if normalize_trading_mode(trading_mode) == "us_stock_options" or instrument_type == "stock_option" or side in {"call", "put"} or underlying in {"TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "META", "MSFT"}:
        return "期权合约过滤"
    if instrument_type == "bull_bear_certificate":
        return "牛熊证过滤"
    return "工具过滤"


def count_if(items: list[dict[str, Any]], key: str, expected: Any) -> int:
    return sum(1 for item in items if item.get(key) == expected)


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


def has_meaningful_trade_value(key: str, value: Any) -> bool:
    if key == "post_trade_emotion" and clean_text(value) == "unset":
        return False
    return has_value(value)


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


def as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
        "no_trade_day": validation.get("no_trade_day"),
        "no_trade_note": validation.get("no_trade_note"),
        "main_issue_of_day": validation.get("main_issue_of_day") or validation.get("main_failure_point"),
        "main_improvement_of_day": validation.get("main_improvement_of_day") or validation.get("improvement_note"),
        "minimum_process_passed": validation.get("minimum_process_passed"),
    }


def canonical_workbench(workbench: dict[str, Any]) -> dict[str, Any]:
    return {
        "trading_mode": workbench.get("trading_mode") or "hsi_bull_bear_certificate",
        "main_direction": workbench.get("main_direction") or "undecided",
        "upper_pressure": workbench.get("upper_pressure") or "",
        "lower_support": workbench.get("lower_support") or "",
        "pivot_level": workbench.get("pivot_level") or "",
        "current_state": workbench.get("current_state") or "unset",
        "post_market_summary": workbench.get("post_market_summary") or "",
        "capital_used": workbench.get("capital_used"),
        "profit_target_pct": workbench.get("profit_target_pct"),
    }


def canonical_playbook(playbook: dict[str, Any]) -> dict[str, Any]:
    return {
        "opening_plan": playbook.get("opening_plan") or "",
        "focus_setup": playbook.get("focus_setup") or "",
        "open_30_key_signal": playbook.get("open_30_key_signal") or "",
        "certificate_filter_note": playbook.get("certificate_filter_note") or "",
        "abnormal_plan": playbook.get("abnormal_plan") or "",
        "option_session_plan": playbook.get("option_session_plan") or "",
        "focus_tickers": playbook.get("focus_tickers") or "",
        "option_focus_setup": playbook.get("option_focus_setup") or "",
        "option_entry_signal": playbook.get("option_entry_signal") or "",
        "option_contract_filter": playbook.get("option_contract_filter") or "",
        "option_risk_plan": playbook.get("option_risk_plan") or "",
        "option_event_risk_plan": playbook.get("option_event_risk_plan") or "",
    }


def build_workbench_draft(workbench: dict[str, Any]) -> list[str]:
    workbench = canonical_workbench(workbench)
    capital = format_number_text(workbench.get("capital_used")) or "未填写"
    target = format_number_text(workbench.get("profit_target_pct"))
    target_text = f"{target}%" if target else "未填写"
    lines = [
        f"- 执行模式：{display_label(workbench.get('trading_mode'))}；主方向：{display_label(workbench.get('main_direction'))}；当前状态：{display_label(workbench.get('current_state'))}。",
        f"- 资金与目标：当日使用本金 {capital}；盈利目标 {target_text}。",
    ]
    if clean_text(workbench.get("post_market_summary")):
        lines.append(f"- 盘后一句话：{sentence(workbench.get('post_market_summary'))}")
    return lines


def build_playbook_draft(playbook: dict[str, Any], workbench: dict[str, Any]) -> list[str]:
    playbook = canonical_playbook(playbook)
    trading_mode = normalize_trading_mode(canonical_workbench(workbench).get("trading_mode"))
    if not any(clean_text(playbook.get(key)) for key in playbook):
        return [f"- 当日还没有单独填写{playbook_title_for_mode(trading_mode)}。"]
    if trading_mode == "us_stock_options":
        return [
            f"- 期权时段计划：{display_label(playbook.get('option_session_plan'))}。",
            f"- 主看股票池：{clean_text(playbook.get('focus_tickers')) or '未填写'}。",
            f"- 期权主练形态：{display_label(playbook.get('option_focus_setup'))}。",
            f"- 期权入场信号：{sentence(playbook.get('option_entry_signal') or '未填写')}",
            f"- 期权合约过滤：{sentence(playbook.get('option_contract_filter') or '未填写')}",
            f"- 期权风控计划：{sentence(playbook.get('option_risk_plan') or '未填写')}",
            f"- 事件风险预案：{sentence(playbook.get('option_event_risk_plan') or '未填写')}",
        ]
    lines = [
        f"- 开盘计划：{display_label(playbook.get('opening_plan'))}。",
        f"- 主练形态：{display_label(playbook.get('focus_setup'))}。",
        f"- 开盘 30 分钟关键信号：{sentence(playbook.get('open_30_key_signal') or '未填写')}",
        f"- 牛熊证过滤提醒：{sentence(playbook.get('certificate_filter_note') or '未填写')}",
        f"- 异常场景预案：{sentence(playbook.get('abnormal_plan') or '未填写')}",
    ]
    return lines


def phase2_trade_checks_passed(trade: dict[str, Any]) -> bool | None:
    return record_checks.phase2_trade_checks_passed(trade)


def summarize_trades(
    trades: list[dict[str, Any]],
    validation: dict[str, Any],
    workbench: dict[str, Any],
) -> tuple[list[str], list[str]]:
    trades = [trade for trade in trades if is_filled_trade(trade)]
    validation = canonical_validation(validation)
    trading_mode = normalize_trading_mode(canonical_workbench(workbench).get("trading_mode"))
    filter_label = filter_label_for_mode(trading_mode)
    if not trades:
        if validation.get("no_trade_day") is True:
            note = clean_text(validation.get("no_trade_note")) or "已标记为空仓日。"
            return (
                ["- 交易数：0", "- 当日按空仓日归档，没有真实交易。"],
                [f"- 空仓说明：{sentence(note)}"]
            )
        return (
            ["- 交易数：0", "- 源记录里没有填写真实交易。"],
            ["- 暂无单笔交易细节；如果当天有交易事实，最终归档前需要先补齐。"]
        )

    wins = count_if(trades, "result", "win")
    losses = count_if(trades, "result", "loss")
    breakevens = count_if(trades, "result", "breakeven")
    violations = sum(1 for trade in trades if trade.get("rule_violation") is True)
    followed = sum(1 for trade in trades if trade.get("followed_plan") is True)
    validated = sum(1 for trade in trades if trade.get("setup_validated") is True)
    not_validated = sum(1 for trade in trades if trade.get("setup_validated") is False)
    opening_30_count = sum(1 for trade in trades if clean_text(trade.get("session_window")) == "opening_30m")
    phase2_check_fail_count = sum(1 for trade in trades if phase2_trade_checks_passed(trade) is False)
    certificate_filter_fail_count = sum(1 for trade in trades if trade.get("certificate_filter_passed") is False)
    abnormal_count = sum(1 for trade in trades if clean_text(trade.get("abnormal_scenario")) not in {"", "none"})

    summary = [
        f"- 当日共交易 {len(trades)} 笔，结果分布为：盈利 {wins} / 亏损 {losses} / 持平 {breakevens}。",
        f"- 计划执行：按计划 {followed} 笔；偏离计划 {len(trades) - followed} 笔；违规标记 {violations} 笔。",
        f"- 形态确认：已确认 {validated} / 未确认 {not_validated} / 未填写 {len(trades) - validated - not_validated}。",
        f"- 主战关键检查：开盘时段交易 {opening_30_count} 笔；四条件未齐 {phase2_check_fail_count} 笔；{filter_label}未过 {certificate_filter_fail_count} 笔；异常场景交易 {abnormal_count} 笔。",
    ]

    details = []
    for trade in trades:
        trade_id = clean_text(trade.get("trade_id")) or "[缺少 trade_id]"
        direction = display_label(trade.get("direction"), "方向未填")
        certificate_side = display_label(trade.get("certificate_side"), "")
        instrument_type = display_label(trade.get("instrument_type"), "")
        underlying = display_label(trade.get("underlying"), "")
        setup_type = display_label(trade.get("setup_type"), "形态未填")
        grade = display_label(trade.get("abc_grade"), "等级未填")
        setup_score = format_number_text(trade.get("setup_score")) or clean_text(trade.get("setup_score"))
        result = display_label(trade.get("result"), "结果未填")
        entry_reason = clean_text(trade.get("entry_reason")) or "入场逻辑未填写"
        emotion_state = display_label(trade.get("emotion_state"), "")
        pre_trade_emotion = display_label(trade.get("pre_trade_emotion"), "")
        post_trade_emotion = display_label(trade.get("post_trade_emotion"), "")
        session_window = display_label(trade.get("session_window"), "")
        abnormal_scenario = display_label(trade.get("abnormal_scenario"), "")
        exit_time = clean_text(trade.get("exit_time"))
        exit_price = format_number_text(trade.get("exit_price")) or clean_text(trade.get("exit_price"))
        pnl_amount = format_number_text(trade.get("pnl_amount")) or clean_text(trade.get("pnl_amount"))
        risk_reward_ratio = format_number_text(trade.get("risk_reward_ratio")) or clean_text(trade.get("risk_reward_ratio"))
        exit_reason = clean_text(trade.get("exit_reason"))
        followed_plan = bool_text(trade.get("followed_plan"))
        screenshot_note = clean_text(trade.get("screenshot_note"))
        review_note = clean_text(trade.get("review_note"))
        violation_note = clean_text(trade.get("violation_note"))

        setup_bits = f"{setup_type}，{grade}"
        if setup_score:
            setup_bits += f"，评分 {setup_score}"
        tool_bits = " / ".join(bit for bit in [underlying, instrument_type, certificate_side] if bit)
        line = f"- {trade_id}：{direction}{f'，{tool_bits}' if tool_bits else ''}，{setup_bits}，结果 {result}。入场逻辑：{sentence(entry_reason)}"
        if exit_time or exit_price or pnl_amount or risk_reward_ratio:
            line += f" 平仓：{exit_time or '时间未填'} / {exit_price or '点位未填'}；盈亏：{pnl_amount or '未填'}；盈亏比：{risk_reward_ratio or '未填'}。"
        if exit_reason:
            line += f" 平仓原因：{sentence(exit_reason)}"
        line += f" 按计划：{followed_plan}。"
        phase2_checks = [
            f"方向 {bool_text(trade.get('direction_clear'))}",
            f"位置 {bool_text(trade.get('location_ok'))}",
            f"确认 {bool_text(trade.get('confirmation_ok'))}",
            f"风险 {bool_text(trade.get('risk_clear'))}",
        ]
        if session_window:
            line += f" 时段：{session_window}。"
        line += " 四条件：" + " / ".join(phase2_checks) + "。"
        if trade.get("certificate_filter_passed") in {True, False}:
            line += f" {trade_filter_label(trade, trading_mode)}：{bool_text(trade.get('certificate_filter_passed'))}。"
        if clean_text(trade.get("abnormal_scenario")) not in {"", "none"}:
            line += f" 异常场景：{abnormal_scenario}。"
        emotion_bits = [bit for bit in [f"开仓前 {pre_trade_emotion}" if pre_trade_emotion else "", f"平仓后 {post_trade_emotion}" if post_trade_emotion else "", f"记录情绪 {emotion_state}" if emotion_state else ""] if bit]
        if emotion_bits:
            line += " 情绪：" + "；".join(emotion_bits) + "。"
        if screenshot_note:
            line += f" 截图备注：{sentence(screenshot_note)}"
        if trade.get("rule_violation") is True:
            line += f" 已标记违规{f'：{sentence(violation_note)}' if violation_note else '。'}"
        elif review_note:
            line += f" 复盘备注：{sentence(review_note)}"
        details.append(line)

    return summary, details


def summarize_rule_events(events: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    events = [event for event in events if is_filled_rule_event(event)]
    if not events:
        return (
            ["- 纪律事件数：0", "- 没有单独记录纪律、情绪、暂停或停手事件。"],
            ["- 如果当天有接近违规、暂停或停手决策，最终归档前可以手动补充。"]
        )

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for event in events:
        event_type = clean_text(event.get("event_type")) or "未填写"
        severity = clean_text(event.get("severity")) or "未填写"
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1

    summary = [
        f"- 纪律事件 {len(events)} 条。",
        "- 事件类型：" + "，".join(f"{display_label(k)}={v}" for k, v in sorted(by_type.items())) + "。",
        "- 严重级别：" + "，".join(f"{display_label(k)}={v}" for k, v in sorted(by_severity.items())) + "。",
    ]

    details = []
    for event in events:
        event_id = clean_text(event.get("event_id")) or "[缺少 event_id]"
        event_type = display_label(event.get("event_type"), "类型未填")
        severity = display_label(event.get("severity"), "级别未填")
        trigger_reason = clean_text(event.get("trigger_reason")) or "触发原因未填写"
        action_taken = clean_text(event.get("action_taken")) or "采取动作未填写"
        follow_up = clean_text(event.get("follow_up_note"))
        linked_trade = clean_text(event.get("linked_trade_id"))

        line = f"- {event_id}：{event_type}（{severity}）。触发：{sentence(trigger_reason)} 处理：{sentence(action_taken)}"
        if linked_trade:
            line += f" 关联交易：{linked_trade}。"
        if follow_up:
            line += f" 后续说明：{sentence(follow_up)}"
        details.append(line)

    return summary, details


def build_review_draft(review: dict[str, Any], trades: list[dict[str, Any]]) -> list[str]:
    review = canonical_review(review)
    pnl = display_label(review.get("pnl"), total_pnl_text(trades) or "[确认当日盈亏]")
    trade_count = clean_text(review.get("trade_count")) or str(len(trades)) or "[按交易记录确认]"
    best_trade_note = clean_text(review.get("best_trade_note")) or "[当天最好的一笔，或最好的克制动作]"
    worst_trade_note = clean_text(review.get("worst_trade_note")) or "[当天最差的一笔，或最需要修正的问题]"
    execution_issue = clean_text(review.get("execution_issue")) or "[如有执行问题，在这里写]"
    emotion_issue = clean_text(review.get("emotion_issue")) or "[如有情绪问题，在这里写]"
    risk_issue = clean_text(review.get("risk_issue")) or "[如有风控问题，在这里写]"
    next_day_one_fix = clean_text(review.get("next_day_one_fix")) or "[下一交易日只改一件事]"
    extras = []
    if clean_text(review.get("market_issue")):
        extras.append(f"行情：{clean_text(review.get('market_issue'))}")
    if clean_text(review.get("setup_issue")):
        extras.append(f"形态：{clean_text(review.get('setup_issue'))}")
    if clean_text(review.get("win_rate")):
        extras.append(f"胜率：{clean_text(review.get('win_rate'))}")
    if clean_text(review.get("max_loss_trade")):
        extras.append(f"最大亏损单：{clean_text(review.get('max_loss_trade'))}")

    return [
        f"- 当日结果先看事实：当日盈亏 {pnl}，交易 {trade_count} 笔。",
        f"- 做得最好的是：{best_trade_note}",
        f"- 最需要修正的是：{worst_trade_note}",
        f"- 执行判断：{execution_issue}",
        f"- 情绪判断：{emotion_issue}",
        f"- 风控判断：{risk_issue}",
        *([f"- 其他补充：{'；'.join(extras)}。"] if extras else []),
        f"- 明天只改一件事：{next_day_one_fix}",
    ]


def build_validation_draft(validation: dict[str, Any]) -> list[str]:
    validation = canonical_validation(validation)
    main_issue = clean_text(validation.get("main_issue_of_day")) or "[当日主要问题；如果流程通过，也要写一句说明]"
    improvement = clean_text(validation.get("main_improvement_of_day")) or "[下一次最主要的改进动作]"
    no_trade_note = clean_text(validation.get("no_trade_note"))
    minimum_process = validation.get("minimum_process_passed")
    if minimum_process is None:
        minimum_process = (
            validation.get("pre_market_done") is True
            and validation.get("intraday_record_complete") is True
            and validation.get("post_market_review_done") is True
        )

    lines = [
        f"- 流程完成度：盘前 {bool_text(validation.get('pre_market_done'))} / 盘中 {bool_text(validation.get('intraday_record_complete'))} / 盘后 {bool_text(validation.get('post_market_review_done'))} / 最小流程 {bool_text(minimum_process)}。",
        f"- 异常信号：冲动交易 {bool_text(validation.get('impulsive_trade_detected'))}；无止损或止损失守 {bool_text(validation.get('no_stop_loss_trade_detected'))}；情绪化过度交易 {bool_text(validation.get('emotional_overtrade_detected'))}。",
    ]
    if validation.get("no_trade_day") is True:
        lines.append(f"- 当日按无交易日归档：{no_trade_note or '空仓说明未填写'}")
    else:
        lines.append(f"- 当日主要问题：{main_issue}")
    lines.append(f"- 下一次最主要改进：{improvement}")
    return lines


def build_closeout_overview(
    *,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
) -> list[str]:
    review = canonical_review(review)
    validation = canonical_validation(validation)
    workbench = canonical_workbench(workbench)
    playbook = canonical_playbook(playbook)
    direction = display_label(workbench.get("main_direction"))
    state = display_label(workbench.get("current_state"))
    mode = display_label(workbench.get("trading_mode"))
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    pnl = display_label(review.get("pnl"), total_pnl_text(trades) or "未填写")
    process_passed = (
        validation.get("pre_market_done") is True
        and validation.get("intraday_record_complete") is True
        and validation.get("post_market_review_done") is True
    )
    lines = [
        f"当日按 {mode} 模式执行，主方向 {direction}，交易状态 {state}。全天共交易 {len(trades)} 笔，纪律事件 {len(events)} 条，当日盈亏 {pnl}，最小流程{'通过' if process_passed else '未通过'}。",
    ]
    if validation.get("no_trade_day") is True:
        lines.append(f"当日按空仓日处理：{clean_text(validation.get('no_trade_note')) or '空仓说明未填写'}。")
    if trading_mode == "us_stock_options":
        if clean_text(playbook.get("option_session_plan")) or clean_text(playbook.get("option_focus_setup")):
            lines.append(
                f"盘前专项计划是：期权时段计划 {display_label(playbook.get('option_session_plan'))}；期权主练形态 {display_label(playbook.get('option_focus_setup'))}。"
            )
        if clean_text(playbook.get("focus_tickers")):
            lines.append(f"主看股票池：{clean_text(playbook.get('focus_tickers'))}。")
    else:
        if clean_text(playbook.get("opening_plan")) or clean_text(playbook.get("focus_setup")):
            lines.append(
                f"盘前专项计划是：开盘计划 {display_label(playbook.get('opening_plan'))}；主练形态 {display_label(playbook.get('focus_setup'))}。"
            )
    capital = format_number_text(workbench.get("capital_used"))
    target = format_number_text(workbench.get("profit_target_pct"))
    if capital or target:
        target_text = f"{target}%" if target else "未填写"
        lines.append(f"盘前资金与目标设定：本金 {capital or '未填写'}，盈利目标 {target_text}。")
    if clean_text(validation.get("main_issue_of_day")) or clean_text(review.get("next_day_one_fix")):
        lines.append(
            f"当日最主要的问题是：{clean_text(validation.get('main_issue_of_day')) or '未填写'}；明天先改：{clean_text(review.get('next_day_one_fix')) or clean_text(validation.get('main_improvement_of_day')) or '未填写'}。"
        )
    if clean_text(workbench.get("post_market_summary")):
        lines.append(f"盘后一句话：{sentence(workbench.get('post_market_summary'))}")
    return lines


def derive_output_path(record_file: Path, trade_date: str, day_number: Any, output_dir: Path | None = None) -> Path:
    base_dir = output_dir or DEFAULT_OUTPUT_DIR
    market = "UNKNOWN"
    try:
        content = record_file.read_text(encoding="utf-8")
        base_fields = extract_yaml_block(content, "Base Fields")
        market = clean_text(base_fields.get("market")) or "UNKNOWN"
    except Exception:
        pass
    return base_dir / f"{trade_date}-{market}-closeout-draft.md"


def render_markdown(
    *,
    record_file: Path,
    base_fields: dict[str, Any],
    workbench: dict[str, Any],
    overview_lines: list[str],
    workbench_draft: list[str],
    playbook_draft: list[str],
    trade_summary: list[str],
    trade_details: list[str],
    rule_summary: list[str],
    rule_details: list[str],
    review_draft: list[str],
    validation_draft: list[str],
) -> str:
    trade_date = clean_text(base_fields.get("trade_date")) or "unknown-date"
    market = clean_text(base_fields.get("market")) or "未填写"
    instrument = display_label(base_fields.get("primary_instrument"), "未填写")
    operator = clean_text(base_fields.get("operator")) or "未填写"
    playbook_title = playbook_title_for_mode(canonical_workbench(workbench).get("trading_mode"))

    def lines(items: list[str]) -> str:
        return "\n".join(items)

    return f"""# TopTrader {trade_date} 归档草稿

## 来源信息
- 交易日期：{trade_date}
- 市场：{market}
- 主要工具：{instrument}
- 操作者：{operator}

## 当日结论
{lines(overview_lines)}

## 作战计划回看
{lines(workbench_draft)}

## {playbook_title}
{lines(playbook_draft)}

## 交易与纪律
{lines(trade_summary)}

### 单笔交易
{lines(trade_details)}

{lines(rule_summary)}

### 纪律事件
{lines(rule_details)}

## 复盘判断
{lines(review_draft)}

## 明日动作
{lines(validation_draft)}

## 人工复核
- 确认源记录里是否还有未补齐的结果、等级、形态字段。
- 如果聊天上下文有结构化字段没覆盖到的细节，在最终归档里补一句。
- 这份草稿是归档起点，不是强制结论。
"""


def main() -> None:
    args = parse_args()
    if not args.record_file.exists():
        raise SystemExit(f"record file not found: {args.record_file}")

    content = args.record_file.read_text(encoding="utf-8")
    base_fields = extract_yaml_block(content, "Base Fields")
    trades = as_list(extract_yaml_block(content, "Trade Record Container").get("trade_records", []))
    rule_events = as_list(extract_yaml_block(content, "Rule Event Container").get("rule_events", []))
    review_record = extract_yaml_block(content, "Review Record Container").get("review_record", {})
    validation_record = extract_yaml_block(content, "Trial Validation Record Container").get("trial_validation_record", {})
    workbench = extract_optional_yaml_block(content, "Daily Workbench").get("daily_workbench", {})
    hsi_playbook = extract_optional_yaml_block(content, "HSI Playbook").get("hsi_playbook", {})
    us_options_playbook = extract_optional_yaml_block(content, "US Options Playbook").get("us_options_playbook", {})
    playbook = {**hsi_playbook, **us_options_playbook}

    workbench_draft = build_workbench_draft(workbench)
    playbook_draft = build_playbook_draft(playbook, workbench)
    trade_summary, trade_details = summarize_trades(trades, validation_record, workbench)
    rule_summary, rule_details = summarize_rule_events(rule_events)
    review_draft = build_review_draft(review_record, [trade for trade in trades if is_filled_trade(trade)])
    validation_draft = build_validation_draft(validation_record)
    overview_lines = build_closeout_overview(
        workbench=workbench,
        playbook=playbook,
        trades=[trade for trade in trades if is_filled_trade(trade)],
        events=[event for event in rule_events if is_filled_rule_event(event)],
        review=review_record,
        validation=validation_record,
    )

    trade_date = clean_text(base_fields.get("trade_date")) or "unknown-date"
    day_number = base_fields.get("day_number")
    output_path = args.output or derive_output_path(
        args.record_file,
        trade_date,
        day_number,
        output_dir=args.output_dir,
    )

    if output_path.exists() and not args.force:
        raise SystemExit(f"output file already exists: {output_path}; use --force to overwrite")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_markdown(
            record_file=args.record_file,
            base_fields=base_fields,
            workbench=workbench,
            overview_lines=overview_lines,
            workbench_draft=workbench_draft,
            playbook_draft=playbook_draft,
            trade_summary=trade_summary,
            trade_details=trade_details,
            rule_summary=rule_summary,
            rule_details=rule_details,
            review_draft=review_draft,
            validation_draft=validation_draft,
        ),
        encoding="utf-8",
    )
    print(output_path)


if __name__ == "__main__":
    main()
