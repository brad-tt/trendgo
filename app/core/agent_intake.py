#!/usr/bin/env python3
"""Heuristic natural-language intake helpers for Agent trade input."""

from __future__ import annotations

import re
from typing import Any

from core.utils import clean_text, to_float

REQUIRED_TRADE_FIELDS = [
    "trade_time",
    "session_window",
    "direction",
    "certificate_side",
    "instrument_code",
    "setup_type",
    "abc_grade",
    "direction_clear",
    "location_ok",
    "confirmation_ok",
    "risk_clear",
    "certificate_filter_passed",
    "entry_price",
    "stop_loss",
    "position_size",
    "followed_plan",
    "entry_reason",
    "instrument_type",
    "underlying",
]

REQUIRED_CLOSE_FIELDS = [
    "exit_time",
    "exit_price",
    "exit_reason",
]

REQUIRED_RULE_EVENT_FIELDS = [
    "event_time",
    "event_type",
    "severity",
    "trigger_reason",
    "action_taken",
]

REQUIRED_REVIEW_FIELDS = [
    "best_trade_note",
    "worst_trade_note",
    "execution_issue",
    "emotion_issue",
    "risk_issue",
    "next_day_one_fix",
]

SETUP_PATTERNS = [
    ("false_breakout_chase", ["假突破追", "追单", "追进去", "fomo"]),
    ("revenge_trade", ["报复", "赚回来", "翻本"]),
    ("profit_giveback", ["盈利回吐", "回吐", "手感好继续加"]),
    ("iv_chase", ["iv", "财报", "赌方向", "波动率"]),
    ("trend_pullback", ["突破回踩", "趋势回踩", "趋势回调", "回踩守住", "回踩确认", "回踩后重新站回", "回踩站回"]),
    ("opening_breakout", ["开盘突破", "突破确认", "确认突破"]),
    ("orb_continuation", ["orb", "开盘延续"]),
    ("vwap_reclaim", ["vwap 收复", "vwap收复", "站回vwap"]),
    ("pullback_reclaim", ["收复回踩"]),
    ("support_reversal", ["支撑反转", "支撑位反转"]),
    ("failed_breakdown", ["跌破失败", "假跌破"]),
    ("clear_observe", ["观察", "先看", "不急"]),
]

ABNORMAL_PATTERNS = [
    ("low_quality_lure", ["低质量", "诱惑"]),
    ("stop_then_reverse", ["止损后反手", "反手追回", "止损后想反手"]),
    ("profit_giveback", ["盈利回吐", "回吐"]),
    ("news_event", ["财报", "消息", "数据夜", "cpi", "fomc"]),
    ("iv_spike", ["iv", "波动率飙升"]),
    ("spread_widen", ["价差变宽", "点差变宽"]),
    ("open_whipsaw", ["开盘乱甩", "开盘来回扫"]),
]

UNDERLYING_PATTERNS = [
    ("HSI", ["恒指", "hsi"]),
    ("TSLA", ["tsla", "特斯拉"]),
    ("NVDA", ["nvda", "英伟达"]),
    ("SPY", ["spy"]),
    ("QQQ", ["qqq"]),
    ("AAPL", ["aapl", "苹果"]),
    ("AMD", ["amd"]),
    ("META", ["meta"]),
    ("MSFT", ["msft", "微软"]),
]


def parse_open_trade_note(raw_note: str, *, market: str = "", trading_mode: str = "") -> tuple[dict[str, Any], list[str], list[str]]:
    note = clean_text(raw_note)
    lowered = note.lower()
    normalized_market = clean_text(market).upper()
    warnings: list[str] = []

    proposal: dict[str, Any] = {
        "trade_time": extract_time(note),
        "session_window": "",
        "direction": "",
        "certificate_side": "",
        "instrument_code": extract_instrument_code(note),
        "setup_type": infer_setup_type(lowered),
        "abc_grade": extract_abc_grade(note),
        "direction_clear": infer_bool(lowered, positives=["方向清楚", "方向明确"], negatives=["方向不清", "方向没看清"]),
        "location_ok": infer_bool(lowered, positives=["位置合理", "位置可以"], negatives=["位置不好", "位置不合理"]),
        "confirmation_ok": infer_bool(lowered, positives=["确认到位", "确认成立", "确认信号有"], negatives=["没有确认", "确认不足"]),
        "risk_clear": infer_bool(lowered, positives=["止损清楚", "风险清楚", "止损明确"], negatives=["止损不清", "风险不清", "还没想清楚止损"]),
        "certificate_filter_passed": infer_bool(lowered, positives=["过滤通过", "价差可接受", "流动性可以"], negatives=["过滤不过", "价差太宽", "流动性太差"]),
        "entry_price": extract_number_after(note, ["入场", "开仓", "买在"]),
        "stop_loss": extract_number_after(note, ["止损", "防守"]),
        "position_size": extract_position_size(note),
        "followed_plan": infer_followed_plan(lowered),
        "rule_violation": infer_rule_violation(lowered),
        "entry_reason": extract_reason(note),
        "instrument_type": infer_instrument_type(lowered, normalized_market, trading_mode),
        "underlying": infer_underlying(lowered, normalized_market),
        "abnormal_scenario": infer_abnormal_scenario(lowered),
        "auto_rule_event": True,
        "post_trade_emotion": "unset",
        "exit_reason": "",
        "exit_time": "",
        "emotion_state": infer_emotion_state(lowered),
        "pre_trade_emotion": infer_pre_trade_emotion(lowered),
        "violation_note": extract_violation_note(note),
        "screenshot_note": "",
        "review_note": "",
        "target_price": None,
        "setup_score": None,
        "setup_validated": None,
    }

    proposal["certificate_side"] = infer_certificate_side(lowered, proposal["direction"], proposal["instrument_type"])
    proposal["direction"] = infer_direction(lowered, proposal["certificate_side"])
    proposal["session_window"] = infer_session_window(lowered, proposal["trade_time"])

    if proposal["instrument_type"] == "bull_bear_certificate" and not proposal["instrument_code"]:
        warnings.append("未识别到 instrumentCode，建议在口述中明确标的代码。")
    if proposal["entry_reason"] == note:
        warnings.append("未识别到单独的理由字段，已使用整段口述作为 entryReason。")

    missing = missing_required_trade_fields(proposal)
    return proposal, missing, warnings


def parse_close_trade_note(raw_note: str) -> tuple[dict[str, Any], list[str], list[str]]:
    note = clean_text(raw_note)
    lowered = note.lower()
    warnings: list[str] = []

    proposal: dict[str, Any] = {
        "trade_id": extract_trade_id(note),
        "exit_time": extract_time(note),
        "exit_price": extract_number_after(note, ["平仓", "出场", "卖在", "止盈", "止损"]),
        "exit_reason": extract_reason(note),
        "post_trade_emotion": infer_post_trade_emotion(lowered),
        "review_note": "",
    }
    if proposal["exit_reason"] == note:
        warnings.append("未识别到单独的平仓原因字段，已使用整段口述作为 exitReason。")
    missing = missing_required_close_fields(proposal)
    return proposal, missing, warnings


def parse_rule_event_note(raw_note: str) -> tuple[dict[str, Any], list[str], list[str]]:
    note = clean_text(raw_note)
    lowered = note.lower()
    warnings: list[str] = []
    proposal = {
        "event_time": extract_time(note),
        "event_type": infer_rule_event_type(lowered),
        "severity": infer_rule_event_severity(lowered),
        "trigger_reason": extract_labeled_text(note, ["触发原因", "原因"]) or note,
        "action_taken": extract_labeled_text(note, ["处理动作", "动作", "采取"]) or infer_rule_event_action(lowered),
        "follow_up_note": extract_labeled_text(note, ["补充", "备注"]),
        "linked_trade_id": extract_trade_id(note),
    }
    if proposal["trigger_reason"] == note:
        warnings.append("未识别到单独的触发原因字段，已使用整段口述作为 triggerReason。")
    missing = missing_required_rule_event_fields(proposal)
    return proposal, missing, warnings


def parse_review_note(raw_note: str) -> tuple[dict[str, Any], list[str], list[str]]:
    note = clean_text(raw_note)
    warnings: list[str] = []
    proposal = {
        "best_trade_note": extract_labeled_text(note, ["最好的一笔", "最好动作", "最好"]),
        "worst_trade_note": extract_labeled_text(note, ["最差的一笔", "最差问题", "最差"]),
        "execution_issue": extract_labeled_text(note, ["执行问题", "执行"]),
        "emotion_issue": extract_labeled_text(note, ["情绪问题", "情绪"]),
        "risk_issue": extract_labeled_text(note, ["风控问题", "风险问题", "风控", "风险"]),
        "next_day_one_fix": extract_labeled_text(note, ["明天只改", "下一步只改", "明天改"]),
        "market_issue": extract_labeled_text(note, ["行情问题", "市场问题"]),
        "setup_issue": extract_labeled_text(note, ["形态问题", "setup问题"]),
        "max_loss_trade": extract_trade_id(note),
        "win_rate": "",
    }
    missing = missing_required_review_fields(proposal)
    if missing:
        warnings.append("复盘口述更适合按“最好/最差/执行/情绪/风控/明天只改”结构表达。")
    return proposal, missing, warnings


def classify_intake_intent(raw_note: str) -> str:
    lowered = clean_text(raw_note).lower()
    if any(token in lowered for token in ["平仓", "出场", "止盈", "止损离场", "保本退出"]):
        return "close_trade"
    if any(token in lowered for token in ["纪律事件", "停手", "暂停交易", "报复", "违规", "情绪触发"]):
        return "rule_event"
    if all(token in lowered for token in ["执行", "情绪"]) or "明天只改" in lowered or "复盘" in lowered:
        return "review"
    trade_like_score = 0
    if extract_instrument_code(raw_note):
        trade_like_score += 1
    if extract_number_after(raw_note, ["入场", "开仓", "买在"]) is not None:
        trade_like_score += 1
    if extract_number_after(raw_note, ["止损", "防守"]) is not None:
        trade_like_score += 1
    if extract_position_size(raw_note):
        trade_like_score += 1
    if extract_abc_grade(raw_note):
        trade_like_score += 1
    if any(token in lowered for token in ["开仓", "做多", "做空", "牛证", "熊证", "call", "put"]) or trade_like_score >= 3:
        return "open_trade"
    return "unknown"


def missing_required_trade_fields(proposal: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_TRADE_FIELDS:
        value = proposal.get(key)
        if isinstance(value, bool):
            continue
        if value in {None, ""}:
            missing.append(key)
    return missing


def missing_required_close_fields(proposal: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_CLOSE_FIELDS:
        value = proposal.get(key)
        if value in {None, ""}:
            missing.append(key)
    return missing


def missing_required_rule_event_fields(proposal: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_RULE_EVENT_FIELDS:
        value = proposal.get(key)
        if value in {None, ""}:
            missing.append(key)
    return missing


def missing_required_review_fields(proposal: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_REVIEW_FIELDS:
        value = proposal.get(key)
        if value in {None, ""}:
            missing.append(key)
    return missing


def extract_time(note: str) -> str:
    match = re.search(r"(?<!\d)([0-2]?\d:\d{2})(?!\d)", note)
    return match.group(1) if match else ""


def extract_instrument_code(note: str) -> str:
    labeled = re.search(r"(?:标的|代码|编号)\s*[:：]?\s*([0-9]{4,6})", note, flags=re.IGNORECASE)
    if labeled:
        return labeled.group(1)
    for match in re.findall(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b", note):
        if any(char.isdigit() for char in match) or "-" in match:
            return match
    certificate_code = re.search(r"(?<!\d)([0-9]{4,6})(?=\s*(?:牛证|熊证|call|put|入场|买|卖|$))", note, flags=re.IGNORECASE)
    if certificate_code:
        return certificate_code.group(1)
    return ""


def extract_trade_id(note: str) -> str:
    match = re.search(r"\bTT-\d{4}-\d{2}-\d{2}-\d{3}\b", note)
    return match.group(0) if match else ""


def extract_abc_grade(note: str) -> str:
    match = re.search(r"\b([ABCabc])\s*级", note)
    return match.group(1).upper() if match else ""


def extract_number_after(note: str, labels: list[str]) -> float | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}(?:价|价格)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)", note, flags=re.IGNORECASE)
        if match:
            return to_float(match.group(1))
        reverse_match = re.search(rf"([0-9]+(?:\.[0-9]+)?)\s*{re.escape(label)}", note, flags=re.IGNORECASE)
        if reverse_match:
            return to_float(reverse_match.group(1))
    return None


def extract_position_size(note: str) -> str:
    match = re.search(r"(?:仓位|数量|手数|买|卖)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:手|张|份)?", note, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:手|张|份)", note, flags=re.IGNORECASE)
    if not match:
        return ""
    raw = match.group(1)
    return raw[:-2] if raw.endswith(".0") else raw


def extract_reason(note: str) -> str:
    match = re.search(r"(?:理由|原因)\s*[:：]\s*(.+)$", note)
    if match:
        return clean_text(match.group(1))
    return clean_text(note)


def extract_labeled_text(note: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:：]\s*([^。；\n]+)", note, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_violation_note(note: str) -> str:
    lowered = note.lower()
    if any(term in lowered for term in ["fomo", "追单", "报复", "翻本", "违规"]):
        return clean_text(note)
    return ""


def infer_setup_type(lowered: str) -> str:
    for setup_type, patterns in SETUP_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return setup_type
    return ""


def infer_abnormal_scenario(lowered: str) -> str:
    for scenario, patterns in ABNORMAL_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return scenario
    return "none"


def infer_underlying(lowered: str, market: str) -> str:
    for underlying, patterns in UNDERLYING_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return underlying
    return "HSI" if market == "HK" else ""


def infer_instrument_type(lowered: str, market: str, trading_mode: str) -> str:
    mode = clean_text(trading_mode)
    if mode == "us_stock_options":
        return "stock_option"
    if mode == "hsi_bull_bear_certificate":
        return "bull_bear_certificate"
    if any(token in lowered for token in ["call", "put", "期权", "option"]):
        return "stock_option"
    if any(token in lowered for token in ["牛证", "熊证", "bear cert", "bull cert"]):
        return "bull_bear_certificate"
    return "bull_bear_certificate" if market == "HK" else ""


def infer_certificate_side(lowered: str, direction: str, instrument_type: str) -> str:
    if any(token in lowered for token in ["call", "买call", "做call"]):
        return "call"
    if any(token in lowered for token in ["put", "买put", "做put"]):
        return "put"
    if "牛证" in lowered or "bull" in lowered:
        return "bull"
    if "熊证" in lowered or "bear" in lowered:
        return "bear"
    if instrument_type == "bull_bear_certificate":
        if direction == "long":
            return "bull"
        if direction == "short":
            return "bear"
    return ""


def infer_direction(lowered: str, certificate_side: str) -> str:
    if any(token in lowered for token in ["做多", "看多", "long"]):
        return "long"
    if any(token in lowered for token in ["做空", "看空", "short"]):
        return "short"
    if certificate_side in {"bull", "call"}:
        return "long"
    if certificate_side in {"bear", "put"}:
        return "short"
    return ""


def infer_session_window(lowered: str, trade_time: str) -> str:
    if any(token in lowered for token in ["开盘", "opening", "早盘"]):
        return "opening_30m"
    if any(token in lowered for token in ["尾盘", "late", "收盘前"]):
        return "late_session"
    if trade_time:
        hour = int(trade_time.split(":", 1)[0])
        if hour <= 10:
            return "opening_30m"
    return "mid_session" if trade_time else ""


def infer_followed_plan(lowered: str) -> bool | None:
    if any(token in lowered for token in ["按计划", "计划内"]):
        return True
    if any(token in lowered for token in ["没按计划", "不按计划", "追单", "临场起意", "fomo"]):
        return False
    return None


def infer_rule_violation(lowered: str) -> bool:
    return any(token in lowered for token in ["违规", "追单", "报复", "翻本", "fomo"])


def infer_pre_trade_emotion(lowered: str) -> str:
    if any(token in lowered for token in ["fomo", "怕错过"]):
        return "fomo"
    if any(token in lowered for token in ["赚回来", "翻本", "亏损后"]):
        return "recover_loss"
    if any(token in lowered for token in ["控制不住", "冲动", "手痒", "着急", "急着", "赶紧"]):
        return "rushed"
    if any(token in lowered for token in ["不服", "硬来"]):
        return "defiant"
    if any(token in lowered for token in ["平静", "稳定"]):
        return "stable"
    return ""


def infer_emotion_state(lowered: str) -> str:
    if any(token in lowered for token in ["报复", "revenge"]):
        return "revenge"
    if any(token in lowered for token in ["控制不住", "冲动", "手痒", "fomo"]):
        return "impulsive"
    if any(token in lowered for token in ["焦虑", "紧张", "anxious"]):
        return "anxious"
    if any(token in lowered for token in ["稳定", "平静"]):
        return "stable"
    return ""


def infer_post_trade_emotion(lowered: str) -> str:
    explicit_exit_emotion = any(token in lowered for token in ["平仓后", "出来后", "出掉后", "卖出后", "退出后"])
    if not explicit_exit_emotion:
        return "unset"
    if any(token in lowered for token in ["后悔", "regret"]):
        return "regret"
    if any(token in lowered for token in ["满意", "踏实", "satisfied"]):
        return "satisfied"
    if any(token in lowered for token in ["着急", "赶紧"]):
        return "rushed"
    if any(token in lowered for token in ["不服", "defiant"]):
        return "defiant"
    if any(token in lowered for token in ["稳定", "平静", "按计划"]):
        return "stable"
    return "unset"


def infer_rule_event_type(lowered: str) -> str:
    if any(token in lowered for token in ["情绪", "报复", "赚回来", "翻本", "fomo"]):
        return "emotion_trigger"
    if any(token in lowered for token in ["停手", "停止开新仓", "forced_stop"]):
        return "forced_stop"
    if any(token in lowered for token in ["暂停", "pause", "先停一下"]):
        return "forced_pause"
    if any(token in lowered for token in ["过度交易", "手痒", "连续出手"]):
        return "overtrade_signal"
    if any(token in lowered for token in ["违规", "破坏规则"]):
        return "rule_violation"
    return ""


def infer_rule_event_severity(lowered: str) -> str:
    if any(token in lowered for token in ["critical", "停手", "停止开新仓", "严重"]):
        return "critical"
    if any(token in lowered for token in ["stop", "暂停", "先停一下"]):
        return "stop"
    if any(token in lowered for token in ["提醒", "warning", "注意"]):
        return "warning"
    return ""


def infer_rule_event_action(lowered: str) -> str:
    if any(token in lowered for token in ["停手", "停止开新仓"]):
        return "当日停止开新仓，只允许记录和复盘。"
    if any(token in lowered for token in ["暂停", "先停一下"]):
        return "暂停交易，先复述交易理由；不清楚就不做。"
    if any(token in lowered for token in ["复盘", "回看"]):
        return "先记录事件，再回到规则和剧本复核。"
    return ""


def infer_bool(lowered: str, *, positives: list[str], negatives: list[str]) -> bool | None:
    if any(token in lowered for token in negatives):
        return False
    if any(token in lowered for token in positives):
        return True
    return None
