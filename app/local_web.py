#!/usr/bin/env python3
"""TrendGo compatibility layer.

This module still provides legacy-compatible record IO, state handling,
and write orchestration used by the current FastAPI backend.

The old standalone local HTTP workbench has been retired.
"""

from __future__ import annotations

import argparse
from collections import Counter
import html
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
import db_init
from core import record_checks
from core import record_io
from core import trading_policy
from core import workspace_state
from core.utils import clean_text as shared_clean_text
from core.utils import format_number as shared_format_number
from core.utils import numeric_almost_equal as shared_numeric_almost_equal
from core.utils import trade_pnl_total as shared_trade_pnl_total
from core.utils import to_float as shared_to_float
from database import dal

ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8522
APP_VERSION = "v0.12"
RECORDS_DIR = ROOT / "05-daily-ops" / "records"
CLOSEOUTS_DIR = ROOT / "05-daily-ops" / "closeouts"
SUMMARIES_DIR = ROOT / "05-daily-ops" / "summaries"
SCRIPT_DAILY = ROOT / "scripts" / "generate_daily_record.py"
SCRIPT_CLOSEOUT = ROOT / "scripts" / "generate_closeout_draft.py"
SCRIPT_TRIAL_SUMMARY = ROOT / "scripts" / "generate_trial_summary.py"
SCRIPT_FIELD_AUDIT = ROOT / "scripts" / "audit_record_fields.py"
DEFAULT_MARKET = "HK"
DEFAULT_INSTRUMENT = "HSI bull/bear certificate"
STATE_FILE = ROOT / ".toptrader_local_web_state.env"
SQLITE_BOOTSTRAPPED = False
USD_HKD_RATE = 7.8

STATE_OPTIONS = ["normal", "tired", "irritated", "sleep_poor", "unstable", "other"]
REVIEW_HUB_WINDOW_OPTIONS = ["5", "10", "all"]
REVIEW_HUB_SAMPLE_FILTER_OPTIONS = ["trusted", "all"]
DIRECTION_OPTIONS = ["long", "short"]
TRADING_MODE_OPTIONS = ["hsi_bull_bear_certificate", "us_stock_options"]
MAIN_DIRECTION_OPTIONS = ["undecided", "long", "short", "observe"]
WORKBENCH_STATE_OPTIONS = ["unset", "stable", "impatient", "defiant", "tired", "unfit"]
OPENING_PLAN_OPTIONS = ["breakout_if_confirmed", "pullback_only", "observe_first", "clear_no_trade"]
PLAYBOOK_FOCUS_SETUP_OPTIONS = ["opening_breakout", "pullback_reclaim", "clear_observe", "other"]
US_OPTION_SESSION_PLAN_OPTIONS = ["wait_first_15m", "trend_continuation", "pullback_only", "breakout_if_confirmed", "clear_no_trade", "avoid_event_risk"]
US_OPTION_FOCUS_SETUP_OPTIONS = ["orb_continuation", "vwap_reclaim", "trend_pullback", "support_reversal", "failed_breakdown", "clear_observe", "other"]
CERTIFICATE_SIDE_OPTIONS = ["bear", "bull", "call", "put"]
SESSION_WINDOW_OPTIONS = ["opening_30m", "mid_session", "late_session"]
SETUP_OPTIONS = [
    "opening_breakout",
    "pullback_reclaim",
    "clear_observe",
    "false_breakout_chase",
    "reverse_after_stop",
    "emotional_trade",
    "revenge_trade",
    "itchy_hand_trade",
    "profit_giveback",
    "recovery_after_losing_streak",
    "orb_continuation",
    "vwap_reclaim",
    "trend_pullback",
    "support_reversal",
    "failed_breakdown",
    "iv_chase",
    "other",
]
GRADE_OPTIONS = ["A", "B", "C"]
EMOTION_OPTIONS = ["stable", "anxious", "revenge", "impulsive"]
PRE_TRADE_EMOTION_OPTIONS = ["stable", "rushed", "defiant", "fomo", "recover_loss"]
POST_TRADE_EMOTION_OPTIONS = ["unset", "stable", "satisfied", "regret", "rushed", "defiant"]
RESULT_OPTIONS = ["win", "loss", "breakeven"]
EVENT_TYPE_OPTIONS = ["rule_violation", "emotion_trigger", "forced_pause", "forced_stop", "overtrade_signal"]
SEVERITY_OPTIONS = ["warning", "stop", "critical"]
ABNORMAL_SCENARIO_OPTIONS = ["none", "open_whipsaw", "stop_then_reverse", "profit_giveback", "low_quality_lure", "iv_spike", "spread_widen", "news_event", "other"]
INSTRUMENT_TYPE_OPTIONS = ["bull_bear_certificate", "stock_option"]
UNDERLYING_OPTIONS = ["HSI", "TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "META", "MSFT", "other"]
PLAYBOOK_QUICK_PRESETS = {
    "confirmed_breakout": {
        "label": "确认突破",
        "opening_plan": "breakout_if_confirmed",
        "focus_setup": "opening_breakout",
        "open_30_key_signal": "只看方向一致、关键位突破后有确认；没有回踩确认不抢第一笔。",
        "certificate_filter_note": "只选成交活跃、价差可接受、强制收回距离安全的牛熊证；过滤不过不做。",
        "abnormal_plan": "如果开盘乱甩或假突破频繁，先暂停观察，不用第一笔证明反应速度。",
    },
    "pullback_confirm": {
        "label": "回踩确认",
        "opening_plan": "pullback_only",
        "focus_setup": "pullback_reclaim",
        "open_30_key_signal": "先等第一段方向出来，再看回踩关键位是否守住；没有二次确认不追。",
        "certificate_filter_note": "优先选距离安全、波动可控的牛熊证；回踩确认前不提前埋单。",
        "abnormal_plan": "止损后如果立刻反向拉回，先确认市场是否真的变了，不因不服气反手。",
    },
    "observe_first": {
        "label": "先观察",
        "opening_plan": "observe_first",
        "focus_setup": "clear_observe",
        "open_30_key_signal": "前 30 分钟先判断主线，不急着交易；方向、位置、确认、风险任一项不清楚就等。",
        "certificate_filter_note": "只做过滤完全通过的标的；看不懂价格跳动或价差不舒服就放弃。",
        "abnormal_plan": "遇到剧烈乱甩、低质量机会连续诱惑时，回到观察模式，不临场发明新规则。",
    },
    "no_trade_if_unclear": {
        "label": "不清晰不做",
        "opening_plan": "clear_no_trade",
        "focus_setup": "clear_observe",
        "open_30_key_signal": "当日只接受清晰 A 级机会；没有清晰方向和关键位确认，开盘前 30 分钟可以完全不做。",
        "certificate_filter_note": "牛熊证过滤不过直接判定为不做，不用换一个更刺激的标的来补偿。",
        "abnormal_plan": "异常场景下默认降级处理：暂停、复核、必要时停手，不把空仓当失败。",
    },
}
US_OPTION_QUICK_PRESETS = {
    "first_15m_trend": {
        "label": "先等15分钟",
        "option_session_plan": "wait_first_15m",
        "option_focus_setup": "orb_continuation",
        "focus_tickers": "TSLA / NVDA / SPY / QQQ",
        "option_entry_signal": "先等前 15 分钟方向和 VWAP 关系清楚，只做放量延续或回踩不破的机会。",
        "option_contract_filter": "只选近月高流动性合约；价差过宽、成交稀薄、IV 异常拉高时不做。",
        "option_risk_plan": "单笔先定义最大亏损，亏损到预设金额直接退出，不用补仓摊平。",
        "option_event_risk_plan": "财报、FOMC、CPI、盘后消息前后默认降频；看不懂 IV 就不交易。",
    },
    "vwap_reclaim": {
        "label": "VWAP 收复",
        "option_session_plan": "pullback_only",
        "option_focus_setup": "vwap_reclaim",
        "focus_tickers": "TSLA / NVDA",
        "option_entry_signal": "只做价格重新站回 VWAP 后的二次确认，不在第一根大阳线追 CALL。",
        "option_contract_filter": "优先 delta 适中、成交活跃、bid/ask 可接受的合约；不买深虚值彩票单。",
        "option_risk_plan": "入场前写清失效点，跌回 VWAP 下方或确认失败直接减仓/退出。",
        "option_event_risk_plan": "如果消息驱动导致跳空过大，先观察，不用期权追第一段情绪。",
    },
    "defensive_no_trade": {
        "label": "防守不做",
        "option_session_plan": "clear_no_trade",
        "option_focus_setup": "clear_observe",
        "focus_tickers": "SPY / QQQ",
        "option_entry_signal": "只接受方向、位置、成交量、风险都清楚的 A 级机会；没有就空仓。",
        "option_contract_filter": "价差、IV、到期日、流动性任一项不舒服，直接过滤。",
        "option_risk_plan": "当日不靠加仓追回；连续两次低质量冲动，直接停手。",
        "option_event_risk_plan": "重大数据或财报窗口不做临场猜方向。",
    },
}
RISKY_SETUP_TYPES = {"emotional_trade", "revenge_trade", "itchy_hand_trade", "profit_giveback", "recovery_after_losing_streak", "iv_chase"}
RISKY_PRE_TRADE_EMOTIONS = {"rushed", "defiant", "fomo", "recover_loss"}
ABNORMAL_SCENARIO_GUIDANCE = {
    "open_whipsaw": "开盘剧烈乱甩：先不出手，等第一轮假动作过去，再确认方向是否稳定。",
    "stop_then_reverse": "止损后反向拉回：不急着追回，先确认市场是否真的改变，不因不服气立刻反手。",
    "profit_giveback": "盈利快速回吐：优先保护利润，节奏变乱先减仓或走人。",
    "low_quality_lure": "低质量机会诱惑：回到检查清单，只做 A 级机会，宁可错过。",
    "iv_spike": "IV 突然拉高：不要追高买权，先确认波动率和价差是否仍可接受。",
    "spread_widen": "价差突然变宽：默认不成交，避免滑点吞掉盈亏比。",
    "news_event": "消息 / 财报事件：先降频，只有消息方向和价格行为都确认才允许继续。",
    "other": "其他异常：默认降级处理，暂停复核，不临场发明新规则。",
}
RULE_EVENT_PRESETS = {
    "open_whipsaw_pause": {
        "label": "开盘乱甩暂停",
        "event_type": "forced_pause",
        "severity": "warning",
        "trigger_reason": "开盘剧烈乱甩，方向稳定性不足。",
        "action_taken": "暂停开新仓，等第一轮假动作过去，再重新检查方向、位置、确认、风险。",
    },
    "stop_reverse_pause": {
        "label": "止损后反手冲动",
        "event_type": "emotion_trigger",
        "severity": "stop",
        "trigger_reason": "刚止损后想立刻反手或追回。",
        "action_taken": "强制暂停，先确认市场是否真的改变；没有重新通过四条件，不允许反手。",
    },
    "profit_protect": {
        "label": "盈利回吐保护",
        "event_type": "forced_pause",
        "severity": "warning",
        "trigger_reason": "盈利单开始快速回吐，节奏有变乱风险。",
        "action_taken": "优先保护利润，复核是否减仓或离场，不把浮盈当成已赚到的钱。",
    },
    "low_quality_stop": {
        "label": "低质量诱惑停手",
        "event_type": "overtrade_signal",
        "severity": "stop",
        "trigger_reason": "连续出现低质量机会诱惑，想用数量弥补不清晰。",
        "action_taken": "当天只允许 A 级机会；如果仍想连续出手，进入停手状态。",
    },
    "manual_stop_day": {
        "label": "当日停手",
        "event_type": "forced_stop",
        "severity": "critical",
        "trigger_reason": "状态、纪律或市场节奏已经不适合继续交易。",
        "action_taken": "当日停止开新仓，只允许记录、复盘和归档。",
    },
}
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
    "wait_first_15m": "先等 15 分钟",
    "trend_continuation": "趋势延续",
    "avoid_event_risk": "避开事件风险",
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
    "positive": "盈利",
    "negative": "亏损",
    "flat": "持平",
    "good": "好",
    "average": "一般",
    "poor": "差",
    "true": "是",
    "false": "否",
    "trusted": "记录完整",
    "all": "全部记录",
}
FIELD_LABELS = {
    "day": "交易日编号",
    "record_path": "记录文件",
    "trading_mode": "模式",
    "main_direction": "当日主方向",
    "current_state": "当前状态",
    "post_market_summary": "盘后总结",
    "capital_used": "当日使用本金",
    "profit_target_pct": "盈利目标%",
    "hk_watchlist": "港股关注池",
    "us_watchlist": "美股关注池",
    "opening_plan": "开盘计划",
    "focus_setup": "主练形态",
    "open_30_key_signal": "开盘 30 分钟关键信号",
    "certificate_filter_note": "牛熊证过滤提醒",
    "abnormal_plan": "异常场景预案",
    "option_session_plan": "期权时段计划",
    "focus_tickers": "主看股票池",
    "option_focus_setup": "期权主练形态",
    "option_entry_signal": "期权入场信号",
    "option_contract_filter": "期权合约过滤",
    "option_risk_plan": "期权风控计划",
    "option_event_risk_plan": "事件风险预案",
    "trade_time": "开仓时间",
    "instrument_code": "标的",
    "certificate_side": "牛/熊证 / Call/Put",
    "instrument_type": "工具类型",
    "underlying": "底层标的",
    "direction": "方向",
    "session_window": "交易时段",
    "setup_type": "形态",
    "abc_grade": "机会等级",
    "setup_score": "评分",
    "entry_reason": "入场逻辑",
    "setup_validated": "形态确认",
    "direction_clear": "方向明确",
    "location_ok": "位置合理",
    "confirmation_ok": "确认出现",
    "risk_clear": "止损清楚",
    "certificate_filter_passed": "工具过滤通过",
    "abnormal_scenario": "异常场景",
    "entry_price": "入场价",
    "stop_loss": "止损",
    "target_price": "目标价",
    "position_size": "仓位",
    "exit_time": "平仓时间",
    "exit_price": "平仓点",
    "pnl_amount": "盈亏金额",
    "risk_reward_ratio": "盈亏比",
    "exit_reason": "平仓原因",
    "followed_plan": "是否按计划",
    "emotion_state": "情绪状态",
    "pre_trade_emotion": "开仓前情绪",
    "post_trade_emotion": "平仓后情绪",
    "rule_violation": "是否违规",
    "violation_note": "违规说明",
    "result": "结果",
    "screenshot_note": "交易截图",
    "review_note": "复盘备注",
    "event_time": "时间",
    "event_type": "类型",
    "severity": "严重级别",
    "trigger_reason": "触发原因",
    "action_taken": "采取动作",
    "follow_up_note": "后续说明",
    "linked_trade_id": "关联交易",
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
    "pre_market_done": "盘前完成",
    "intraday_record_complete": "盘中记录完成",
    "post_market_review_done": "盘后复盘完成",
    "impulsive_trade_detected": "出现冲动交易",
    "no_stop_loss_trade_detected": "出现无止损 / 止损失守",
    "emotional_overtrade_detected": "出现情绪化过度交易",
    "no_trade_day": "无交易日",
    "no_trade_note": "空仓说明",
    "main_issue_of_day": "当日主要问题",
    "main_improvement_of_day": "当日主要改进",
}

REVIEW_TEXT_QUALITY_FIELDS = [
    "best_trade_note",
    "worst_trade_note",
    "execution_issue",
    "emotion_issue",
    "risk_issue",
    "next_day_one_fix",
]

REVIEW_TEXT_QUALITY_PROMPTS = {
    "best_trade_note": {
        "target": "#review-best-trade-note",
        "prompt": "写清具体交易编号或等待动作、好在哪里、下次要保留什么。",
        "skeleton": "TT-____ / 等待动作____；好在____；继续保留____。",
    },
    "worst_trade_note": {
        "target": "#review-worst-trade-note",
        "prompt": "写清最差的一笔或最危险的动作、问题是什么、当时怎么触发。",
        "skeleton": "TT-____ / 差点犯错____；问题是____；触发原因____。",
    },
    "execution_issue": {
        "target": "#review-execution-issue",
        "prompt": "写执行动作偏差，聚焦有没有提前、追单、犹豫、复核不足。",
        "skeleton": "执行偏差____；发生在____；下次用____拦住。",
    },
    "emotion_issue": {
        "target": "#review-emotion-issue",
        "prompt": "写真实情绪状态，说明有没有急、怕错过、想追回或想证明。",
        "skeleton": "情绪____；触发点____；对动作的影响____。",
    },
    "risk_issue": {
        "target": "#review-risk-issue",
        "prompt": "写风险动作是否清楚，重点看止损、仓位、过滤和停手。",
        "skeleton": "风险点____；止损/仓位/过滤____；修正动作____。",
    },
    "next_day_one_fix": {
        "target": "#review-next-day-one-fix",
        "prompt": "只收成一个明天可执行动作，不写大而泛的目标。",
        "skeleton": "明天只改____；触发条件____；不满足就____。",
    },
    "main_issue_of_day": {
        "target": "#validation-main-issue-of-day",
        "prompt": "写当天最主要问题，和复盘区的问题归因保持一致。",
        "skeleton": "当天主问题____；来自____；优先处理____。",
    },
    "no_trade_note": {
        "target": "#validation-no-trade-note",
        "prompt": "空仓日写等待依据和差点破规则的时刻，不能只写无交易。",
        "skeleton": "空仓原因____；等待依据____；差点破规则____。",
    },
}


AppState = workspace_state.AppState


def clean_text(value: Any) -> str:
    return shared_clean_text(value)


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value is True
    return clean_text(value) != ""


def load_state() -> AppState:
    return workspace_state.load_state(
        state_file=STATE_FILE,
        normalize_review_hub_window=normalize_review_hub_window,
        normalize_review_hub_sample_filter=normalize_review_hub_sample_filter,
    )


def save_state(state: AppState) -> None:
    workspace_state.save_state(state=state, state_file=STATE_FILE)


def normalize_review_hub_window(value: Any) -> str:
    text = clean_text(value)
    if text in REVIEW_HUB_WINDOW_OPTIONS:
        return text
    return "5"


def review_hub_window_limit(value: str) -> int | None:
    window = normalize_review_hub_window(value)
    if window == "all":
        return None
    return int(window)


def review_hub_window_label(value: str) -> str:
    window = normalize_review_hub_window(value)
    return "全部交易日" if window == "all" else f"近 {window} 日"


def normalize_review_hub_sample_filter(value: Any) -> str:
    text = clean_text(value)
    if text in REVIEW_HUB_SAMPLE_FILTER_OPTIONS:
        return text
    return "all"


def review_hub_sample_filter_label(value: str) -> str:
    return display_value(normalize_review_hub_sample_filter(value))


def normalize_trading_mode(value: Any) -> str:
    text = clean_text(value)
    return text if text in TRADING_MODE_OPTIONS else "hsi_bull_bear_certificate"


def market_for_trading_mode(trading_mode: str) -> str:
    return "US" if normalize_trading_mode(trading_mode) == "us_stock_options" else DEFAULT_MARKET


def instrument_for_trading_mode(trading_mode: str) -> str:
    return "US stock options" if normalize_trading_mode(trading_mode) == "us_stock_options" else DEFAULT_INSTRUMENT


def playbook_title_for_mode(trading_mode: str) -> str:
    return "美股期权专项卡" if normalize_trading_mode(trading_mode) == "us_stock_options" else "恒指专项卡"


def filter_label_for_mode(trading_mode: str) -> str:
    return "期权合约过滤" if normalize_trading_mode(trading_mode) == "us_stock_options" else "牛熊证过滤"


def trade_filter_label(trade: dict[str, Any]) -> str:
    instrument_type = clean_text(trade.get("instrument_type"))
    side = clean_text(trade.get("certificate_side"))
    underlying = clean_text(trade.get("underlying"))
    if instrument_type == "stock_option" or side in {"call", "put"} or underlying in {"TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "META", "MSFT"}:
        return "期权合约过滤"
    if instrument_type == "bull_bear_certificate":
        return "牛熊证过滤"
    return "工具过滤"


def playbook_plan_value(playbook: dict[str, Any], trading_mode: str) -> str:
    if normalize_trading_mode(trading_mode) == "us_stock_options":
        return clean_text(playbook.get("option_session_plan"))
    return clean_text(playbook.get("opening_plan"))


def playbook_setup_value(playbook: dict[str, Any], trading_mode: str) -> str:
    if normalize_trading_mode(trading_mode) == "us_stock_options":
        return clean_text(playbook.get("option_focus_setup"))
    return clean_text(playbook.get("focus_setup"))


def default_instrument_for_mode(trading_mode: str) -> tuple[str, str]:
    if normalize_trading_mode(trading_mode) == "us_stock_options":
        return "US", "US stock options"
    return DEFAULT_MARKET, DEFAULT_INSTRUMENT


def side_options_for_mode(trading_mode: str) -> list[str]:
    if normalize_trading_mode(trading_mode) == "us_stock_options":
        return ["call", "put"]
    return ["bear", "bull"]


def instrument_type_options_for_mode(trading_mode: str) -> list[str]:
    if normalize_trading_mode(trading_mode) == "us_stock_options":
        return ["stock_option"]
    return ["bull_bear_certificate"]


def underlying_options_for_mode(trading_mode: str) -> list[str]:
    if normalize_trading_mode(trading_mode) == "us_stock_options":
        return ["TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "META", "MSFT", "other"]
    return ["HSI"]


def find_recent_files(directory: Path, suffix: str, limit: int = 8) -> list[Path]:
    return workspace_state.find_recent_files(directory, suffix, limit)


def find_files(directory: Path, suffix: str) -> list[Path]:
    return workspace_state.find_files(directory, suffix)


def latest_record_path() -> Path | None:
    return workspace_state.latest_record_path(RECORDS_DIR, load_record=load_record)


def parse_day_number(value: Any) -> int | None:
    return workspace_state.parse_day_number(value)


def parse_iso_date(value: Any) -> date | None:
    return workspace_state.parse_iso_date(value)


def next_weekday(value: date) -> date:
    return workspace_state.next_weekday(value)


def suggested_start_day_values(state: AppState, record_paths: list[Path]) -> tuple[str, str]:
    return workspace_state.suggested_start_day_values(
        state=state,
        record_paths=record_paths,
        load_record=load_record,
    )


def format_trade_date(value: Any) -> str:
    return workspace_state.format_trade_date(value)


def record_day_number(path: Path) -> int | None:
    return workspace_state.record_day_number(path, load_record=load_record)


def active_record_path(record_paths: list[Path]) -> Path | None:
    return workspace_state.active_record_path(record_paths, load_record=load_record)


def is_active_record_path(path: Path | None, record_paths: list[Path]) -> bool:
    return workspace_state.is_active_record_path(path, record_paths, load_record=load_record)


def relative_path(path: Path) -> str:
    return workspace_state.relative_path(path, root=ROOT)


def resolve_path(raw_path: str) -> Path:
    return workspace_state.resolve_path(raw_path, root=ROOT)


def locate_yaml_block(content: str, heading: str) -> tuple[int, int]:
    return record_io.locate_yaml_block(content, heading)


def read_yaml_section(content: str, heading: str) -> Any:
    return record_io.read_yaml_section(content, heading)


def read_optional_yaml_section(content: str, heading: str) -> Any:
    return record_io.read_optional_yaml_section(content, heading)


def render_yaml_section(heading: str, value: Any) -> str:
    return record_io.render_yaml_section(heading, value)


def write_yaml_section(content: str, heading: str, value: Any) -> str:
    return record_io.write_yaml_section(content, heading, value)


def write_yaml_section_or_insert(content: str, heading: str, value: Any, *, before_heading: str | None = None) -> str:
    return record_io.write_yaml_section_or_insert(content, heading, value, before_heading=before_heading)


def remove_markdown_section(content: str, heading: str) -> str:
    return record_io.remove_markdown_section(content, heading)


def as_list(value: Any) -> list[dict[str, Any]]:
    return record_io.as_list(value)


def is_filled_trade(trade: dict[str, Any]) -> bool:
    return record_io.is_filled_trade(trade)


def has_meaningful_trade_value(key: str, value: Any) -> bool:
    return record_io.has_meaningful_trade_value(key, value)


def has_meaningful_workbench_value(key: str, value: Any) -> bool:
    if key == "main_direction" and clean_text(value) == "undecided":
        return False
    if key == "current_state" and clean_text(value) == "unset":
        return False
    return has_value(value)


def has_meaningful_playbook_value(value: Any) -> bool:
    return clean_text(value) != ""


def is_filled_rule_event(event: dict[str, Any]) -> bool:
    return record_io.is_filled_rule_event(event)


def canonical_review(review: dict[str, Any]) -> dict[str, Any]:
    return record_io.canonical_review(review)


def canonical_validation(validation: dict[str, Any]) -> dict[str, Any]:
    return record_io.canonical_validation(validation)


def canonical_workbench(workbench: dict[str, Any]) -> dict[str, Any]:
    return record_io.canonical_workbench(workbench)


def canonical_playbook(playbook: dict[str, Any]) -> dict[str, Any]:
    return record_io.canonical_playbook(playbook)


def load_record(path: Path) -> dict[str, Any]:
    return record_io.load_record(path)


def next_id(prefix: str, trade_date: str, items: list[dict[str, Any]], key: str) -> str:
    stem = f"{prefix}-{trade_date}-"
    max_sequence = 0
    for item in items:
        item_id = clean_text(item.get(key))
        if not item_id.startswith(stem):
            continue
        suffix = item_id.removeprefix(stem)
        if suffix.isdigit():
            max_sequence = max(max_sequence, int(suffix))
    return f"{stem}{max_sequence + 1:03d}"


def form_value(form: dict[str, list[str]], key: str, default: str = "") -> str:
    return (form.get(key) or [default])[0].strip()


def form_bool(form: dict[str, list[str]], key: str) -> bool:
    return form_value(form, key).lower() in {"1", "true", "yes", "on"}


def field_label(field_name: str) -> str:
    return FIELD_LABELS.get(field_name, field_name)


def parse_number(value: str, field_name: str, *, required: bool = True) -> float | None:
    value = value.strip()
    if not value:
        if required:
            raise ValueError(f"请填写{field_label(field_name)}。")
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field_label(field_name)}必须是数字。") from exc


def parse_int(value: str, field_name: str, *, required: bool = True) -> int | None:
    value = value.strip()
    if not value:
        if required:
            raise ValueError(f"请填写{field_label(field_name)}。")
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_label(field_name)}必须是整数。") from exc


def parse_optional_bool(value: str) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def number_value(value: Any) -> float | None:
    return shared_to_float(value)


def normalize_trade_clock(value: Any, field_name: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if ":" in text:
        parts = text.split(":")
        if len(parts) in {2, 3} and all(part.isdigit() for part in parts[:2]):
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
    elif text.isdigit() and len(text) in {3, 4}:
        hour = int(text[:-2])
        minute = int(text[-2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    raise ValueError(f"{field_label(field_name)}格式需为 HH:MM。")


def infer_trade_result(direction: str, entry_price: Any, exit_price: Any) -> str:
    del direction
    entry_value = number_value(entry_price)
    exit_value = number_value(exit_price)
    if entry_value is None or exit_value is None:
        return ""
    signed_move = exit_value - entry_value
    if signed_move > 1e-9:
        return "win"
    if signed_move < -1e-9:
        return "loss"
    return "breakeven"


def calculate_trade_pnl_amount(direction: str, entry_price: Any, exit_price: Any, position_size: Any) -> float | None:
    del direction
    entry_value = number_value(entry_price)
    exit_value = number_value(exit_price)
    size_value = number_value(position_size)
    if entry_value is None or exit_value is None or size_value is None:
        return None
    signed_move = exit_value - entry_value
    return round(signed_move * size_value, 4)


def trade_currency(trade: dict[str, Any], *, trading_mode: str = "", market: str = "") -> str:
    instrument_type = clean_text(trade.get("instrument_type"))
    certificate_side = clean_text(trade.get("certificate_side"))
    resolved_market = clean_text(trade.get("market")) or market
    if (
        normalize_trading_mode(trading_mode) == "us_stock_options"
        or resolved_market == "US"
        or instrument_type == "stock_option"
        or certificate_side in {"call", "put"}
    ):
        return "USD"
    return "HKD"


def money_to_hkd(value: Any, currency: str) -> float | None:
    amount = number_value(value)
    if amount is None:
        return None
    if currency == "USD":
        amount *= USD_HKD_RATE
    return round(amount, 2)


def trade_pnl_amount_hkd(trade: dict[str, Any], *, trading_mode: str = "", market: str = "") -> float | None:
    return money_to_hkd(trade.get("pnl_amount"), trade_currency(trade, trading_mode=trading_mode, market=market))


def trade_pnl_total_hkd(trades: list[dict[str, Any]], *, trading_mode: str = "", market: str = "") -> float | None:
    values = [
        trade_pnl_amount_hkd(trade, trading_mode=trading_mode, market=market)
        for trade in trades
    ]
    values = [value for value in values if value is not None]
    return round(sum(values), 2) if values else None


def trade_win_rate_text(trades: list[dict[str, Any]]) -> str:
    if not trades:
        return ""
    wins = sum(1 for trade in trades if clean_text(trade.get("result")) == "win")
    return format_number(wins / len(trades) * 100, suffix="%")


def numeric_almost_equal(left: float | None, right: float | None, *, tolerance: float = 1e-9) -> bool:
    return shared_numeric_almost_equal(left, right, tolerance=tolerance)


def require_choice(value: str, field_name: str, allowed: list[str]) -> str:
    if value not in allowed:
        allowed_labels = "、".join(display_label(option) for option in allowed)
        raise ValueError(f"{field_label(field_name)}只能选择：{allowed_labels}。")
    return value


def update_state_from_record(state: AppState, path: Path, record: dict[str, Any]) -> None:
    workspace_state.update_state_from_record(
        state=state,
        path=path,
        record=record,
        closeout_path_from_base=closeout_path_from_base,
        relative_path_func=relative_path,
    )


def current_record_path(state: AppState) -> Path | None:
    return workspace_state.current_record_path(state, root=ROOT)


def current_closeout_path(state: AppState) -> Path | None:
    return workspace_state.current_closeout_path(state, root=ROOT)


def current_summary_path(state: AppState) -> Path | None:
    return workspace_state.current_summary_path(state, root=ROOT)


def current_audit_path(state: AppState) -> Path | None:
    return workspace_state.current_audit_path(state, root=ROOT)


def ensure_sqlite_ready() -> None:
    global SQLITE_BOOTSTRAPPED
    if SQLITE_BOOTSTRAPPED:
        return
    db_init.init_db(dal.DB_PATH)
    for path in find_files(RECORDS_DIR, "*.md"):
        try:
            record = load_record(path)
            dal.save_record_bundle(record, source_record_path=relative_path(path))
        except Exception:
            continue
    SQLITE_BOOTSTRAPPED = True


def load_record_db_first(path: Path) -> dict[str, Any]:
    try:
        ensure_sqlite_ready()
        record = dal.get_daily_record_by_source_path(relative_path(path))
        if record:
            return record
    except Exception:
        pass
    return load_record(path)


def load_record_db_first_with_content(path: Path) -> dict[str, Any]:
    record = load_record_db_first(path)
    if not clean_text(record.get("content")) and path.exists():
        record = {**record, "content": path.read_text(encoding="utf-8")}
    return record


def save_record_bundle_dual_write(record_path: Path, record: dict[str, Any], content: str) -> None:
    ensure_sqlite_ready()
    dal.save_record_bundle(record, source_record_path=relative_path(record_path))
    record_path.write_text(content, encoding="utf-8")


def set_pre_market(content: str, current_state: str, focus: str) -> str:
    section = read_yaml_section(content, "Pre-Market Status")
    pre_market = section.get("pre_market_status", {})
    pre_market["state"] = current_state
    pre_market["key_reminder"] = focus
    section["pre_market_status"] = pre_market
    return write_yaml_section(content, "Pre-Market Status", section)


def run_daily_generator(day: str, trade_date: str, current_state: str, focus: str, trading_mode: str) -> tuple[Path, str, bool]:
    del day
    trading_mode = normalize_trading_mode(trading_mode)
    market, instrument = default_instrument_for_mode(trading_mode)
    final_path = RECORDS_DIR / f"{trade_date}-{market}-record-container.md"
    if final_path.exists():
        return final_path, final_path.read_text(encoding="utf-8"), False

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            sys.executable,
            str(SCRIPT_DAILY),
            "1",
            "--date",
            trade_date,
            "--trading-mode",
            trading_mode,
            "--market",
            market,
            "--instrument",
            instrument,
            "--output-dir",
            tmpdir,
        ]
        completed = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "daily generator failed")
        generated_tmp = Path(completed.stdout.strip().splitlines()[-1])
        content = generated_tmp.read_text(encoding="utf-8")

    final_content = set_pre_market(content, current_state, focus)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(final_content, encoding="utf-8")
    return final_path, final_content, True


def closeout_path_from_base(base: dict[str, Any]) -> Path:
    trade_date = clean_text(base.get("trade_date")) or "unknown-date"
    market = clean_text(base.get("market")) or "UNKNOWN"
    return CLOSEOUTS_DIR / f"{trade_date}-{market}-closeout-draft.md"


def expected_closeout_path(record_path: Path) -> Path:
    record = load_record(record_path)
    return closeout_path_from_base(record["base"])


def closeout_status_for_record(record_path: Path, base: dict[str, Any]) -> tuple[bool, bool, bool]:
    closeout_path = closeout_path_from_base(base)
    if not closeout_path.exists():
        return False, False, False
    try:
        legacy = is_legacy_english_closeout(closeout_path.read_text(encoding="utf-8"))
        stale = record_path.stat().st_mtime > closeout_path.stat().st_mtime
    except OSError:
        return True, False, False
    return True, legacy, stale


def record_path_for_closeout(closeout_path: Path) -> Path | None:
    suffix = "-closeout-draft.md"
    name = closeout_path.name
    if not name.endswith(suffix):
        return None
    base_name = name[: -len(suffix)]
    return RECORDS_DIR / f"{base_name}-record-container.md"


def require_markdown_file(raw_path: str, directory: Path, label: str) -> Path:
    path = resolve_path(raw_path)
    if not path.exists():
        raise ValueError(f"找不到{label}：{raw_path}")
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError as exc:
        raise ValueError(f"{label}必须位于 {relative_path(directory)}。") from exc
    if path.suffix != ".md":
        raise ValueError(f"{label}必须是 Markdown 文件。")
    return path


def run_closeout_generator(record_path: Path, *, force: bool) -> tuple[Path, str, bool]:
    output_path = expected_closeout_path(record_path)
    if output_path.exists() and not force:
        return output_path, output_path.read_text(encoding="utf-8"), False

    cmd = [
        sys.executable,
        str(SCRIPT_CLOSEOUT),
        str(record_path),
        "--output-dir",
        str(CLOSEOUTS_DIR),
    ]
    if force:
        cmd.append("--force")
    completed = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "closeout generator failed")
    output_path = Path(completed.stdout.strip().splitlines()[-1])
    return output_path, output_path.read_text(encoding="utf-8"), True


def expected_trial_summary_path() -> Path:
    return SUMMARIES_DIR / "TopTrader-trial-summary.md"


def run_trial_summary_generator(*, force: bool) -> tuple[Path, str, bool]:
    output_path = expected_trial_summary_path()
    if output_path.exists() and not force:
        return output_path, output_path.read_text(encoding="utf-8"), False

    cmd = [
        sys.executable,
        str(SCRIPT_TRIAL_SUMMARY),
        "--records-dir",
        str(RECORDS_DIR),
        "--output-dir",
        str(SUMMARIES_DIR),
    ]
    if force:
        cmd.append("--force")
    completed = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "trial summary generator failed")
    output_path = Path(completed.stdout.strip().splitlines()[-1])
    return output_path, output_path.read_text(encoding="utf-8"), True


def expected_field_audit_path() -> Path:
    return SUMMARIES_DIR / "TopTrader-field-audit.md"


def run_field_audit_generator(*, force: bool) -> tuple[Path, str, bool]:
    output_path = expected_field_audit_path()
    if output_path.exists() and not force:
        return output_path, output_path.read_text(encoding="utf-8"), False

    cmd = [
        sys.executable,
        str(SCRIPT_FIELD_AUDIT),
        "--records-dir",
        str(RECORDS_DIR),
        "--output-dir",
        str(SUMMARIES_DIR),
    ]
    if force:
        cmd.append("--force")
    completed = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "field audit generator failed")
    output_path = Path(completed.stdout.strip().splitlines()[-1])
    return output_path, output_path.read_text(encoding="utf-8"), True


def save_workbench(record_path: Path, form: dict[str, list[str]]) -> None:
    record = load_record(record_path)
    trading_mode = require_choice(form_value(form, "trading_mode"), "trading_mode", TRADING_MODE_OPTIONS)
    playbook_preset_key = form_value(form, "playbook_preset")
    if playbook_preset_key and playbook_preset_key not in PLAYBOOK_QUICK_PRESETS:
        raise ValueError("恒指专项卡快速方案无效。")
    playbook_preset = PLAYBOOK_QUICK_PRESETS.get(playbook_preset_key, {})
    option_preset_key = form_value(form, "option_playbook_preset")
    if option_preset_key and option_preset_key not in US_OPTION_QUICK_PRESETS:
        raise ValueError("美股期权专项卡快速方案无效。")
    option_preset = US_OPTION_QUICK_PRESETS.get(option_preset_key, {})

    def playbook_value(key: str) -> str:
        raw_value = form_value(form, key)
        if not playbook_preset:
            return raw_value
        preset_value = clean_text(playbook_preset.get(key))
        if key in {"opening_plan", "focus_setup"} and preset_value:
            return preset_value
        return raw_value or preset_value

    def option_playbook_value(key: str) -> str:
        raw_value = form_value(form, key)
        if not option_preset:
            return raw_value
        preset_value = clean_text(option_preset.get(key))
        if key in {"option_session_plan", "option_focus_setup"} and preset_value:
            return preset_value
        return raw_value or preset_value

    workbench = {
        "trading_mode": trading_mode,
        "main_direction": require_choice(form_value(form, "main_direction"), "main_direction", MAIN_DIRECTION_OPTIONS),
        "upper_pressure": form_value(form, "upper_pressure"),
        "lower_support": form_value(form, "lower_support"),
        "pivot_level": form_value(form, "pivot_level"),
        "current_state": require_choice(form_value(form, "current_state"), "current_state", WORKBENCH_STATE_OPTIONS),
        "post_market_summary": form_value(form, "post_market_summary"),
        "capital_used": parse_number(form_value(form, "capital_used"), "capital_used", required=False),
        "profit_target_pct": parse_number(form_value(form, "profit_target_pct"), "profit_target_pct", required=False),
        "hk_watchlist": form_value(form, "hk_watchlist"),
        "us_watchlist": form_value(form, "us_watchlist"),
    }
    pre_market = {
        "trading_today": form_bool(form, "trading_today"),
        "state": form_value(form, "pre_market_state") or "normal",
        "follow_normal_rules": form_bool(form, "follow_normal_rules"),
        "key_reminder": form_value(form, "key_reminder"),
        "note": form_value(form, "pre_market_note"),
    }
    hsi_playbook = {
        "opening_plan": (
            require_choice(playbook_value("opening_plan"), "opening_plan", OPENING_PLAN_OPTIONS)
            if trading_mode == "hsi_bull_bear_certificate"
            else ""
        ),
        "focus_setup": (
            require_choice(playbook_value("focus_setup"), "focus_setup", PLAYBOOK_FOCUS_SETUP_OPTIONS)
            if trading_mode == "hsi_bull_bear_certificate"
            else ""
        ),
        "open_30_key_signal": playbook_value("open_30_key_signal"),
        "certificate_filter_note": playbook_value("certificate_filter_note"),
        "abnormal_plan": playbook_value("abnormal_plan"),
    }
    us_options_playbook = {
        "option_session_plan": (
            require_choice(option_playbook_value("option_session_plan"), "option_session_plan", US_OPTION_SESSION_PLAN_OPTIONS)
            if trading_mode == "us_stock_options"
            else option_playbook_value("option_session_plan")
        ),
        "focus_tickers": option_playbook_value("focus_tickers"),
        "option_focus_setup": (
            require_choice(option_playbook_value("option_focus_setup"), "option_focus_setup", US_OPTION_FOCUS_SETUP_OPTIONS)
            if trading_mode == "us_stock_options"
            else option_playbook_value("option_focus_setup")
        ),
        "option_entry_signal": option_playbook_value("option_entry_signal"),
        "option_contract_filter": option_playbook_value("option_contract_filter"),
        "option_risk_plan": option_playbook_value("option_risk_plan"),
        "option_event_risk_plan": option_playbook_value("option_event_risk_plan"),
    }
    content = write_yaml_section_or_insert(
        record["content"],
        "Pre-Market Status",
        {"pre_market_status": pre_market},
        before_heading="Daily Workbench",
    )
    content = write_yaml_section_or_insert(
        content,
        "Daily Workbench",
        {"daily_workbench": workbench},
        before_heading="Trade Record Container",
    )
    if trading_mode == "us_stock_options":
        content = remove_markdown_section(content, "HSI Playbook")
        content = write_yaml_section_or_insert(
            content,
            "US Options Playbook",
            {"us_options_playbook": us_options_playbook},
            before_heading="Trade Record Container",
        )
    else:
        content = write_yaml_section_or_insert(
            content,
            "HSI Playbook",
            {"hsi_playbook": hsi_playbook},
            before_heading="Trade Record Container",
        )
        content = remove_markdown_section(content, "US Options Playbook")
    updated_record = {
        **record,
        "pre_market": pre_market,
        "workbench": workbench,
        "playbook": canonical_playbook({**hsi_playbook, **us_options_playbook}),
    }
    save_record_bundle_dual_write(record_path, updated_record, content)


def trade_failed_check_labels(trade: dict[str, Any]) -> list[str]:
    return [field_label(key) for key in record_checks.trade_failed_check_keys(trade)]


def hsi_decision_gate(
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    return trading_policy.build_decision_gate(
        workbench=workbench,
        playbook=playbook,
        events=events,
        trading_mode=normalize_trading_mode(workbench.get("trading_mode")),
        display_value=display_value,
        field_label=field_label,
    )


def risk_controller(
    workbench: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    return trading_policy.build_risk_state(
        workbench=workbench,
        trades=trades,
        events=events,
        trading_mode=trading_mode,
        filter_label=filter_label_for_mode(trading_mode),
        format_number=format_number,
    )


def execution_lock(decision_gate: dict[str, Any], risk_state: dict[str, Any]) -> dict[str, Any]:
    return trading_policy.build_execution_lock(decision_gate, risk_state)


def abnormal_scenario_recorded(value: Any) -> bool:
    return record_checks.abnormal_scenario_recorded(value)


def phase2_trade_record_complete(trade: dict[str, Any]) -> bool:
    return record_checks.phase2_trade_record_complete(trade)


def trade_needs_risk_event(trade: dict[str, Any]) -> bool:
    return record_checks.trade_needs_risk_event(
        trade,
        risky_setup_types=RISKY_SETUP_TYPES,
        risky_pre_trade_emotions=RISKY_PRE_TRADE_EMOTIONS,
    )


def has_risk_event_coverage(trades: list[dict[str, Any]], events: list[dict[str, Any]]) -> bool:
    return record_checks.has_risk_event_coverage(
        trades,
        events,
        risky_setup_types=RISKY_SETUP_TYPES,
        risky_pre_trade_emotions=RISKY_PRE_TRADE_EMOTIONS,
    )


def phase2_one_day_acceptance_gate(
    *,
    record_path: Path | None,
    record_editable: bool,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
) -> dict[str, Any]:
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    return record_checks.build_acceptance_gate(
        record_path_present=record_path is not None,
        record_editable=record_editable,
        workbench=workbench,
        playbook=playbook,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        closeout_exists=closeout_exists,
        closeout_legacy=closeout_legacy,
        closeout_stale=closeout_stale,
        trading_mode=trading_mode,
        playbook_title=playbook_title_for_mode(trading_mode),
        filter_label=filter_label_for_mode(trading_mode),
        review_text_quality_fields=REVIEW_TEXT_QUALITY_FIELDS,
        risky_setup_types=RISKY_SETUP_TYPES,
        risky_pre_trade_emotions=RISKY_PRE_TRADE_EMOTIONS,
    )


def current_workflow_stage(
    *,
    record_path: Path | None,
    record_editable: bool,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
) -> dict[str, Any]:
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    return record_checks.build_workflow_stage(
        record_path_present=record_path is not None,
        record_editable=record_editable,
        workbench=workbench,
        playbook=playbook,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        closeout_exists=closeout_exists,
        closeout_legacy=closeout_legacy,
        closeout_stale=closeout_stale,
        trading_mode=trading_mode,
        playbook_title=playbook_title_for_mode(trading_mode),
        review_text_quality_fields=REVIEW_TEXT_QUALITY_FIELDS,
    )


def next_action_engine(
    *,
    record_path: Path | None,
    record_editable: bool,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
    decision_gate: dict[str, Any],
    risk_state: dict[str, Any],
    acceptance_gate: dict[str, Any],
) -> dict[str, Any]:
    stage = current_workflow_stage(
        record_path=record_path,
        record_editable=record_editable,
        workbench=workbench,
        playbook=playbook,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        closeout_exists=closeout_exists,
        closeout_legacy=closeout_legacy,
        closeout_stale=closeout_stale,
    )
    workbench_missing = missing_workbench_labels(workbench)
    playbook_missing = missing_playbook_labels(playbook, workbench.get("trading_mode"))
    lock = execution_lock(decision_gate, risk_state)
    review_missing = missing_review_labels(review)
    validation_missing = missing_validation_labels(validation)
    return record_checks.build_next_action(
        stage=stage,
        record_path_present=record_path is not None,
        record_editable=record_editable,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        closeout_exists=closeout_exists,
        closeout_legacy=closeout_legacy,
        closeout_stale=closeout_stale,
        acceptance_gate=acceptance_gate,
        execution_lock=lock,
        workbench_missing_labels=workbench_missing,
        playbook_missing_labels=playbook_missing,
        review_missing_labels=review_missing,
        validation_missing_labels=validation_missing,
        closeout_status_label=closeout_status_label(
            exists=closeout_exists,
            legacy=closeout_legacy,
            stale=closeout_stale,
        ),
    )


def decision_gate_event_fields(
    decision_gate: dict[str, Any],
    trade: dict[str, Any],
    *,
    trade_date: str,
    market: str,
) -> dict[str, Any] | None:
    status = clean_text(decision_gate.get("status"))
    if status == "ready":
        return None
    if status == "observe_only":
        return None

    reasons = decision_gate.get("blockers") or decision_gate.get("cautions") or []
    reason_text = "、".join(clean_text(reason) for reason in reasons if clean_text(reason))
    if not reason_text:
        reason_text = clean_text(decision_gate.get("label")) or "盘前决策门未通过"

    return {
        "date": trade_date,
        "time": trade.get("trade_time"),
        "market": market,
        "event_type": "rule_violation" if status == "blocked" else "forced_pause",
        "severity": "stop" if status == "blocked" else "warning",
        "trigger_reason": f"开仓时决策门状态为“{decision_gate.get('label')}”：{reason_text}。",
        "action_taken": clean_text(decision_gate.get("action")) or "暂停复核，不继续加仓。",
        "follow_up_note": "由盘前决策门自动带出。",
        "linked_trade_id": trade.get("trade_id"),
    }


def risk_controller_event_fields(
    risk_state: dict[str, Any],
    trade: dict[str, Any],
    *,
    trade_date: str,
    market: str,
) -> dict[str, Any] | None:
    status = clean_text(risk_state.get("status"))
    if status in {"", "normal"}:
        return None

    reasons = risk_state.get("blockers") or risk_state.get("cautions") or []
    reason_text = "、".join(clean_text(reason) for reason in reasons if clean_text(reason))
    if not reason_text:
        reason_text = clean_text(risk_state.get("label")) or "当日风险状态需要复核"

    event_type = "forced_stop" if status == "stop" else "forced_pause"
    severity = "critical" if status == "stop" else "warning"
    return {
        "date": trade_date,
        "time": trade.get("trade_time"),
        "market": market,
        "event_type": event_type,
        "severity": severity,
        "trigger_reason": f"开仓时风险控制器状态为“{risk_state.get('label')}”：{reason_text}。",
        "action_taken": clean_text(risk_state.get("action")) or "暂停复核，不继续加仓。",
        "follow_up_note": "由风险控制器自动带出。",
        "linked_trade_id": trade.get("trade_id"),
    }


def trade_auto_rule_event_fields(
    trade: dict[str, Any],
    *,
    trade_date: str,
    market: str,
    decision_gate: dict[str, Any] | None = None,
    risk_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    failed_checks = trade_failed_check_labels(trade)
    abnormal_scenario = clean_text(trade.get("abnormal_scenario"))
    setup_type = clean_text(trade.get("setup_type"))
    pre_trade_emotion = clean_text(trade.get("pre_trade_emotion"))
    emotion_state = clean_text(trade.get("emotion_state"))

    if trade.get("rule_violation") is True:
        return {
            "date": trade_date,
            "time": trade.get("trade_time"),
            "market": market,
            "event_type": "rule_violation",
            "severity": "stop",
            "trigger_reason": clean_text(trade.get("violation_note")) or "交易记录已标记为规则违规。",
            "action_taken": "立即暂停，回到四条件和工具过滤检查；如果已经触发停手条件，当天不再加仓。",
            "follow_up_note": "由交易记录自动带出。",
            "linked_trade_id": trade.get("trade_id"),
        }

    if failed_checks:
        return {
            "date": trade_date,
            "time": trade.get("trade_time"),
            "market": market,
            "event_type": "rule_violation",
            "severity": "warning",
            "trigger_reason": "进场检查未通过：" + "、".join(failed_checks) + "。",
            "action_taken": "暂停复核，不继续加仓；下一笔必须重新通过方向、位置、确认、风险和工具过滤。",
            "follow_up_note": "由交易记录自动带出。",
            "linked_trade_id": trade.get("trade_id"),
        }

    if risk_state:
        risk_event = risk_controller_event_fields(risk_state, trade, trade_date=trade_date, market=market)
        if risk_event:
            return risk_event

    if decision_gate:
        gate_event = decision_gate_event_fields(decision_gate, trade, trade_date=trade_date, market=market)
        if gate_event:
            return gate_event

    if abnormal_scenario and abnormal_scenario != "none":
        return {
            "date": trade_date,
            "time": trade.get("trade_time"),
            "market": market,
            "event_type": "forced_pause",
            "severity": "warning",
            "trigger_reason": f"交易落在异常场景：{display_value(abnormal_scenario)}。",
            "action_taken": "按异常场景预案处理，先暂停复核，不临场发明新规则。",
            "follow_up_note": "由交易记录自动带出。",
            "linked_trade_id": trade.get("trade_id"),
        }

    if setup_type in RISKY_SETUP_TYPES or pre_trade_emotion in RISKY_PRE_TRADE_EMOTIONS or emotion_state in {"revenge", "impulsive"}:
        reasons = []
        if setup_type in RISKY_SETUP_TYPES:
            reasons.append(f"形态={display_value(setup_type)}")
        if pre_trade_emotion in RISKY_PRE_TRADE_EMOTIONS:
            reasons.append(f"开仓前情绪={display_value(pre_trade_emotion)}")
        if emotion_state in {"revenge", "impulsive"}:
            reasons.append(f"情绪状态={display_value(emotion_state)}")
        return {
            "date": trade_date,
            "time": trade.get("trade_time"),
            "market": market,
            "event_type": "emotion_trigger",
            "severity": "warning",
            "trigger_reason": " / ".join(reasons) + "。",
            "action_taken": "暂停复核情绪状态，只允许重新通过 A 级机会检查后再考虑下一笔。",
            "follow_up_note": "由交易记录自动带出。",
            "linked_trade_id": trade.get("trade_id"),
        }

    return None


def add_trade(record_path: Path, form: dict[str, list[str]]) -> str:
    record = load_record_db_first_with_content(record_path)
    base = record["base"]
    trade_date = clean_text(base.get("trade_date"))
    market = clean_text(base.get("market")) or DEFAULT_MARKET
    trades = record["trades"]
    events = record["events"]
    trading_mode = normalize_trading_mode(record["workbench"].get("trading_mode"))
    default_instrument_type = "stock_option" if trading_mode == "us_stock_options" else "bull_bear_certificate"
    default_underlying = "TSLA" if trading_mode == "us_stock_options" else "HSI"
    new_trade = {
        "trade_id": next_id("TT", trade_date, trades, "trade_id"),
        "trade_date": trade_date,
        "trade_time": normalize_trade_clock(form_value(form, "trade_time"), "trade_time"),
        "market": market,
        "instrument_code": form_value(form, "instrument_code"),
        "certificate_side": require_choice(form_value(form, "certificate_side"), "certificate_side", CERTIFICATE_SIDE_OPTIONS),
        "instrument_type": form_value(form, "instrument_type", default_instrument_type) or default_instrument_type,
        "underlying": form_value(form, "underlying", default_underlying) or default_underlying,
        "direction": require_choice(form_value(form, "direction"), "direction", DIRECTION_OPTIONS),
        "session_window": require_choice(
            form_value(form, "session_window", "mid_session"),
            "session_window",
            SESSION_WINDOW_OPTIONS,
        ),
        "setup_type": require_choice(form_value(form, "setup_type"), "setup_type", SETUP_OPTIONS),
        "abc_grade": require_choice(form_value(form, "abc_grade"), "abc_grade", GRADE_OPTIONS),
        "setup_score": parse_number(form_value(form, "setup_score"), "setup_score", required=False),
        "entry_reason": form_value(form, "entry_reason"),
        "setup_validated": parse_optional_bool(form_value(form, "setup_validated")),
        "direction_clear": require_choice(form_value(form, "direction_clear"), "direction_clear", ["true", "false"]) == "true",
        "location_ok": require_choice(form_value(form, "location_ok"), "location_ok", ["true", "false"]) == "true",
        "confirmation_ok": require_choice(form_value(form, "confirmation_ok"), "confirmation_ok", ["true", "false"]) == "true",
        "risk_clear": require_choice(form_value(form, "risk_clear"), "risk_clear", ["true", "false"]) == "true",
        "certificate_filter_passed": require_choice(
            form_value(form, "certificate_filter_passed"), "certificate_filter_passed", ["true", "false"]
        )
        == "true",
        "abnormal_scenario": require_choice(
            form_value(form, "abnormal_scenario", "none"), "abnormal_scenario", ABNORMAL_SCENARIO_OPTIONS
        ),
        "entry_price": parse_number(form_value(form, "entry_price"), "entry_price"),
        "stop_loss": parse_number(form_value(form, "stop_loss"), "stop_loss"),
        "target_price": parse_number(form_value(form, "target_price"), "target_price", required=False),
        "position_size": form_value(form, "position_size"),
        "exit_time": normalize_trade_clock(form_value(form, "exit_time"), "exit_time"),
        "exit_price": parse_number(form_value(form, "exit_price"), "exit_price", required=False),
        "pnl_amount": parse_number(form_value(form, "pnl_amount"), "pnl_amount", required=False),
        "risk_reward_ratio": parse_number(form_value(form, "risk_reward_ratio"), "risk_reward_ratio", required=False),
        "exit_reason": form_value(form, "exit_reason"),
        "followed_plan": require_choice(form_value(form, "followed_plan"), "followed_plan", ["true", "false"]) == "true",
        "emotion_state": form_value(form, "emotion_state"),
        "pre_trade_emotion": form_value(form, "pre_trade_emotion"),
        "post_trade_emotion": form_value(form, "post_trade_emotion"),
        "rule_violation": require_choice(form_value(form, "rule_violation"), "rule_violation", ["true", "false"]) == "true",
        "violation_note": form_value(form, "violation_note"),
        "result": "",
        "screenshot_note": form_value(form, "screenshot_note"),
        "review_note": form_value(form, "review_note"),
    }
    raw_result = form_value(form, "result")
    new_trade["result"] = (
        require_choice(raw_result, "result", RESULT_OPTIONS)
        if raw_result
        else infer_trade_result(new_trade["direction"], new_trade["entry_price"], new_trade["exit_price"])
    )
    if new_trade["pnl_amount"] is None and new_trade["exit_price"] is not None:
        new_trade["pnl_amount"] = calculate_trade_pnl_amount(
            new_trade["direction"],
            new_trade["entry_price"],
            new_trade["exit_price"],
            new_trade["position_size"],
        )

    for required_key in ["instrument_code", "entry_reason", "position_size"]:
        if not clean_text(new_trade.get(required_key)):
            raise ValueError(f"请填写{field_label(required_key)}。")
    if new_trade["emotion_state"] and new_trade["emotion_state"] not in EMOTION_OPTIONS:
        raise ValueError("情绪状态无效。")
    if new_trade["pre_trade_emotion"] and new_trade["pre_trade_emotion"] not in PRE_TRADE_EMOTION_OPTIONS:
        raise ValueError("开仓前情绪无效。")
    if new_trade["post_trade_emotion"] and new_trade["post_trade_emotion"] not in POST_TRADE_EMOTION_OPTIONS:
        raise ValueError("平仓后情绪无效。")
    if new_trade["instrument_type"] not in INSTRUMENT_TYPE_OPTIONS:
        raise ValueError("工具类型无效。")
    if new_trade["underlying"] not in UNDERLYING_OPTIONS:
        raise ValueError("底层标的无效。")

    auto_event = None
    if form_bool(form, "auto_rule_event"):
        decision_gate = hsi_decision_gate(record["workbench"], record["playbook"], events)
        risk_state = risk_controller(record["workbench"], trades, events)
        auto_event = trade_auto_rule_event_fields(
            new_trade,
            trade_date=trade_date,
            market=market,
            decision_gate=decision_gate,
            risk_state=risk_state,
        )
        if auto_event:
            auto_event = {"event_id": next_id("RE", trade_date, events, "event_id"), **auto_event}

    updated_trades = trades + [new_trade]
    updated_events = events + [auto_event] if auto_event else events
    content = write_yaml_section(record["content"], "Trade Record Container", {"trade_records": updated_trades})
    if auto_event:
        content = write_yaml_section(content, "Rule Event Container", {"rule_events": updated_events})
    updated_record = {
        **record,
        "trades": updated_trades,
        "events": updated_events,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)
    return clean_text(auto_event.get("event_id")) if auto_event else ""


def add_rule_event_preset(record_path: Path, preset_key: str) -> str:
    if preset_key not in RULE_EVENT_PRESETS:
        raise ValueError("纪律事件快捷动作无效。")
    record = load_record_db_first_with_content(record_path)
    base = record["base"]
    trade_date = clean_text(base.get("trade_date"))
    market = clean_text(base.get("market")) or DEFAULT_MARKET
    events = record["events"]
    preset = RULE_EVENT_PRESETS[preset_key]
    new_event = {
        "event_id": next_id("RE", trade_date, events, "event_id"),
        "date": trade_date,
        "time": datetime.now().strftime("%H:%M"),
        "market": market,
        "event_type": preset["event_type"],
        "severity": preset["severity"],
        "trigger_reason": preset["trigger_reason"],
        "action_taken": preset["action_taken"],
        "follow_up_note": "由快捷纪律动作写入。",
        "linked_trade_id": "",
    }
    updated_events = events + [new_event]
    content = write_yaml_section(record["content"], "Rule Event Container", {"rule_events": updated_events})
    updated_record = {
        **record,
        "events": updated_events,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)
    return clean_text(new_event["event_id"])


def add_rule_event(record_path: Path, form: dict[str, list[str]]) -> str:
    record = load_record_db_first_with_content(record_path)
    base = record["base"]
    trade_date = clean_text(base.get("trade_date"))
    market = clean_text(base.get("market")) or DEFAULT_MARKET
    events = record["events"]
    new_event = {
        "event_id": next_id("RE", trade_date, events, "event_id"),
        "date": trade_date,
        "time": normalize_trade_clock(form_value(form, "event_time"), "event_time"),
        "market": market,
        "event_type": require_choice(form_value(form, "event_type"), "event_type", EVENT_TYPE_OPTIONS),
        "severity": require_choice(form_value(form, "severity"), "severity", SEVERITY_OPTIONS),
        "trigger_reason": form_value(form, "trigger_reason"),
        "action_taken": form_value(form, "action_taken"),
        "follow_up_note": form_value(form, "follow_up_note"),
        "linked_trade_id": form_value(form, "linked_trade_id"),
    }
    for required_key in ["time", "trigger_reason", "action_taken"]:
        if not clean_text(new_event.get(required_key)):
            label_key = "event_time" if required_key == "time" else required_key
            raise ValueError(f"请填写{field_label(label_key)}。")

    updated_events = events + [new_event]
    content = write_yaml_section(record["content"], "Rule Event Container", {"rule_events": updated_events})
    updated_record = {
        **record,
        "events": updated_events,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)
    return clean_text(new_event["event_id"])


def save_review(record_path: Path, form: dict[str, list[str]]) -> None:
    record = load_record_db_first_with_content(record_path)
    base = record["base"]
    trades = record["trades"]
    trading_mode = normalize_trading_mode(record["workbench"].get("trading_mode"))
    market = clean_text(base.get("market")) or DEFAULT_MARKET
    trade_count_default = len(trades)
    pnl_total_hkd = trade_pnl_total_hkd(trades, trading_mode=trading_mode, market=market)
    pnl_value = format_number(pnl_total_hkd if pnl_total_hkd is not None else 0)
    trade_count_value = form_value(form, "trade_count")
    review = {
        "review_date": clean_text(base.get("trade_date")),
        "market": market,
        "primary_instrument": clean_text(base.get("primary_instrument")) or DEFAULT_INSTRUMENT,
        "pnl": pnl_value,
        "trade_count": parse_int(trade_count_value or str(trade_count_default), "trade_count"),
        "win_rate": trade_win_rate_text(trades),
        "max_loss_trade": form_value(form, "max_loss_trade"),
        "best_trade_note": form_value(form, "best_trade_note"),
        "worst_trade_note": form_value(form, "worst_trade_note"),
        "market_issue": form_value(form, "market_issue"),
        "execution_issue": form_value(form, "execution_issue"),
        "emotion_issue": form_value(form, "emotion_issue"),
        "risk_issue": form_value(form, "risk_issue"),
        "setup_issue": form_value(form, "setup_issue"),
        "next_day_one_fix": form_value(form, "next_day_one_fix"),
    }
    for required_key in [
        "pnl",
        "best_trade_note",
        "worst_trade_note",
        "execution_issue",
        "emotion_issue",
        "risk_issue",
        "next_day_one_fix",
    ]:
        if not clean_text(review.get(required_key)):
            raise ValueError(f"请填写{field_label(required_key)}。")
    placeholder_keys = [
        key for key in REVIEW_TEXT_QUALITY_FIELDS if not is_meaningful_review_sentence(review.get(key))
    ]
    if placeholder_keys:
        labels = "、".join(field_label(key) for key in placeholder_keys)
        raise ValueError(f"复盘文字仍像占位值，请补成当天事实：{labels}。")

    content = write_yaml_section(record["content"], "Review Record Container", {"review_record": review})
    updated_record = {
        **record,
        "review": review,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)


def sync_review_numbers(record_path: Path) -> tuple[str, int]:
    record = load_record(record_path)
    base = record["base"]
    trades = record["trades"]
    review = dict(record["review"])
    trading_mode = normalize_trading_mode(record["workbench"].get("trading_mode"))
    market = clean_text(base.get("market")) or DEFAULT_MARKET
    pnl_total = trade_pnl_total_hkd(trades, trading_mode=trading_mode, market=market)
    pnl_text = format_number(pnl_total if pnl_total is not None else 0)
    review.update(
        {
            "review_date": clean_text(base.get("trade_date")),
            "market": market,
            "primary_instrument": clean_text(base.get("primary_instrument")) or DEFAULT_INSTRUMENT,
            "pnl": pnl_text,
            "trade_count": len(trades),
            "win_rate": trade_win_rate_text(trades),
        }
    )
    content = write_yaml_section(record["content"], "Review Record Container", {"review_record": review})
    updated_record = {
        **record,
        "review": review,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)
    return pnl_text, len(trades)


def save_validation(record_path: Path, form: dict[str, list[str]]) -> None:
    record = load_record(record_path)
    base = record["base"]
    force_no_trade_day = record["pre_market"].get("trading_today") is False
    no_trade_day = force_no_trade_day or form_bool(form, "no_trade_day")
    validation = {
        "trial_day_number": base.get("day_number"),
        "date": clean_text(base.get("trade_date")),
        "market": clean_text(base.get("market")) or DEFAULT_MARKET,
        "primary_instrument": clean_text(base.get("primary_instrument")) or DEFAULT_INSTRUMENT,
        "pre_market_done": form_bool(form, "pre_market_done"),
        "intraday_record_complete": form_bool(form, "intraday_record_complete"),
        "post_market_review_done": form_bool(form, "post_market_review_done"),
        "impulsive_trade_detected": form_bool(form, "impulsive_trade_detected"),
        "no_stop_loss_trade_detected": form_bool(form, "no_stop_loss_trade_detected"),
        "emotional_overtrade_detected": form_bool(form, "emotional_overtrade_detected"),
        "no_trade_day": no_trade_day,
        "no_trade_note": form_value(form, "no_trade_note"),
        "main_issue_of_day": form_value(form, "main_issue_of_day"),
        "main_improvement_of_day": form_value(form, "main_improvement_of_day"),
    }
    if no_trade_day:
        if not validation["intraday_record_complete"]:
            raise ValueError("无交易日也需要勾选盘中记录完成。")
        if not clean_text(validation["no_trade_note"]):
            raise ValueError("请填写空仓说明。")
        if not is_meaningful_review_sentence(validation["no_trade_note"]):
            raise ValueError("空仓说明仍像占位值，请补成当天事实。")
    elif not validation["main_issue_of_day"]:
        raise ValueError("请填写当日主要问题。")
    elif not is_meaningful_review_sentence(validation["main_issue_of_day"]):
        raise ValueError("当日主要问题仍像占位值，请补成当天事实。")

    content = write_yaml_section(
        record["content"],
        "Trial Validation Record Container",
        {"trial_validation_record": validation},
    )
    updated_record = {
        **record,
        "validation": validation,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)


def save_acceptance_review(record_path: Path, form: dict[str, list[str]]) -> tuple[str, int]:
    record = load_record(record_path)
    base = record["base"]
    trades = record["trades"]
    existing_review = record["review"]
    existing_validation = record["validation"]
    force_no_trade_day = record["pre_market"].get("trading_today") is False
    pnl_total = trade_pnl_total(trades)
    pnl_text = format_number(pnl_total if pnl_total is not None else 0)

    def form_or_existing(key: str, source: dict[str, Any]) -> str:
        return form_value(form, key) if key in form else clean_text(source.get(key))

    def bool_or_existing(key: str) -> bool:
        return form_bool(form, key) if key in form else existing_validation.get(key) is True

    review = {
        "review_date": clean_text(base.get("trade_date")),
        "market": clean_text(base.get("market")) or DEFAULT_MARKET,
        "primary_instrument": clean_text(base.get("primary_instrument")) or DEFAULT_INSTRUMENT,
        "pnl": pnl_text,
        "trade_count": len(trades),
        "win_rate": form_or_existing("win_rate", existing_review),
        "max_loss_trade": form_or_existing("max_loss_trade", existing_review),
        "best_trade_note": form_or_existing("best_trade_note", existing_review),
        "worst_trade_note": form_or_existing("worst_trade_note", existing_review),
        "market_issue": form_or_existing("market_issue", existing_review),
        "execution_issue": form_or_existing("execution_issue", existing_review),
        "emotion_issue": form_or_existing("emotion_issue", existing_review),
        "risk_issue": form_or_existing("risk_issue", existing_review),
        "setup_issue": form_or_existing("setup_issue", existing_review),
        "next_day_one_fix": form_or_existing("next_day_one_fix", existing_review),
    }
    placeholder_keys = [
        key for key in REVIEW_TEXT_QUALITY_FIELDS if not is_meaningful_review_sentence(review.get(key))
    ]
    if placeholder_keys:
        labels = "、".join(field_label(key) for key in placeholder_keys)
        raise ValueError(f"复盘文字仍像占位值，请补成当天事实：{labels}。")

    no_trade_day = force_no_trade_day or bool_or_existing("no_trade_day")
    validation = {
        "trial_day_number": base.get("day_number"),
        "date": clean_text(base.get("trade_date")),
        "market": clean_text(base.get("market")) or DEFAULT_MARKET,
        "primary_instrument": clean_text(base.get("primary_instrument")) or DEFAULT_INSTRUMENT,
        "pre_market_done": bool_or_existing("pre_market_done"),
        "intraday_record_complete": bool_or_existing("intraday_record_complete"),
        "post_market_review_done": bool_or_existing("post_market_review_done"),
        "impulsive_trade_detected": bool_or_existing("impulsive_trade_detected"),
        "no_stop_loss_trade_detected": bool_or_existing("no_stop_loss_trade_detected"),
        "emotional_overtrade_detected": bool_or_existing("emotional_overtrade_detected"),
        "no_trade_day": no_trade_day,
        "no_trade_note": form_or_existing("no_trade_note", existing_validation),
        "main_issue_of_day": form_or_existing("main_issue_of_day", existing_validation),
        "main_improvement_of_day": form_or_existing("main_improvement_of_day", existing_validation),
    }
    if no_trade_day:
        if not validation["intraday_record_complete"]:
            raise ValueError("无交易日也需要勾选盘中记录完成。")
        if not is_meaningful_review_sentence(validation["no_trade_note"]):
            raise ValueError("空仓说明仍像占位值，请补成当天事实。")
    elif not is_meaningful_review_sentence(validation["main_issue_of_day"]):
        raise ValueError("当日主要问题仍像占位值，请补成当天事实。")

    content = write_yaml_section(record["content"], "Review Record Container", {"review_record": review})
    content = write_yaml_section(
        content,
        "Trial Validation Record Container",
        {"trial_validation_record": validation},
    )
    updated_record = {
        **record,
        "review": review,
        "validation": validation,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)
    return pnl_text, len(trades)


def close_no_trade_day(record_path: Path) -> tuple[Path, str]:
    record = load_record(record_path)
    if record["trades"] or record["events"]:
        raise ValueError("当前已经有交易或纪律事实，不能使用一键空仓归档。")
    base = record["base"]
    workbench = record["workbench"]
    playbook = record["playbook"]
    trade_date = clean_text(base.get("trade_date"))
    market = clean_text(base.get("market")) or DEFAULT_MARKET
    instrument = clean_text(base.get("primary_instrument")) or DEFAULT_INSTRUMENT
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    pre_market_done = is_workbench_ready(workbench) and not missing_playbook_labels(playbook, workbench.get("trading_mode"))
    filter_label = filter_label_for_mode(trading_mode)
    time_quality_text = "美股开盘首段" if trading_mode == "us_stock_options" else "开盘 30 分钟"
    no_trade_note = (
        f"按计划空仓：没有出现同时满足方向、位置、确认、风险和{filter_label}的机会。"
        if pre_market_done
        else "空仓归档：当天没有真实交易；盘前计划仍需补齐后再作为完整记录统计。"
    )
    review = {
        "review_date": trade_date,
        "market": market,
        "primary_instrument": instrument,
        "pnl": "0",
        "trade_count": 0,
        "win_rate": "",
        "max_loss_trade": "",
        "best_trade_note": "没有为了开仓而开仓，保留了交易质量。",
        "worst_trade_note": "复核是否有清晰 A 级机会被错过；如果没有，空仓是正确动作。",
        "market_issue": "",
        "execution_issue": "无交易日重点确认是否遵守盘前计划和禁做场景。",
        "emotion_issue": "未因手痒、怕错过或想证明自己而强行交易。",
        "risk_issue": "没有新增风险暴露。",
        "setup_issue": "",
        "next_day_one_fix": f"继续只做四条件齐全且{filter_label}通过的机会。",
    }
    validation = {
        "trial_day_number": base.get("day_number"),
        "date": trade_date,
        "market": market,
        "primary_instrument": instrument,
        "pre_market_done": pre_market_done,
        "intraday_record_complete": True,
        "post_market_review_done": True,
        "impulsive_trade_detected": False,
        "no_stop_loss_trade_detected": False,
        "emotional_overtrade_detected": False,
        "no_trade_day": True,
        "no_trade_note": no_trade_note,
        "main_issue_of_day": "",
        "main_improvement_of_day": f"把空仓也当作执行记录，继续提高{time_quality_text}的选择质量。",
    }
    content = write_yaml_section(record["content"], "Review Record Container", {"review_record": review})
    content = write_yaml_section(
        content,
        "Trial Validation Record Container",
        {"trial_validation_record": validation},
    )
    updated_record = {
        **record,
        "review": review,
        "validation": validation,
    }
    save_record_bundle_dual_write(record_path, updated_record, content)
    output_path, preview, _ = run_closeout_generator(record_path, force=True)
    return output_path, preview


def is_review_done(review: dict[str, Any]) -> bool:
    return record_checks.is_review_done(review)


def is_validation_done(validation: dict[str, Any]) -> bool:
    return record_checks.is_validation_done(validation)


def missing_review_labels(review: dict[str, Any]) -> list[str]:
    return [field_label(key) for key in record_checks.missing_review_keys(review)]


def missing_validation_labels(validation: dict[str, Any]) -> list[str]:
    return [field_label(key) for key in record_checks.missing_validation_keys(validation)]


def is_workbench_ready(workbench: dict[str, Any]) -> bool:
    return record_checks.is_workbench_ready(workbench)


def missing_workbench_labels(workbench: dict[str, Any]) -> list[str]:
    return [field_label(key) for key in record_checks.missing_workbench_keys(workbench)]


def missing_playbook_labels(playbook: dict[str, Any], trading_mode: str) -> list[str]:
    return [field_label(key) for key in record_checks.missing_playbook_keys(playbook, normalize_trading_mode(trading_mode))]


def completion_text(*, done: int, total: int) -> str:
    return f"{done}/{total}"


def workbench_completion(workbench: dict[str, Any]) -> tuple[int, int, list[str]]:
    missing = missing_workbench_labels(workbench)
    total = 7
    return total - len(missing), total, missing


def playbook_completion(playbook: dict[str, Any], trading_mode: str) -> tuple[int, int, list[str]]:
    missing = missing_playbook_labels(playbook, trading_mode)
    total = 7 if normalize_trading_mode(trading_mode) == "us_stock_options" else 5
    return total - len(missing), total, missing


def review_completion(review: dict[str, Any]) -> tuple[int, int, list[str]]:
    missing = missing_review_labels(review)
    total = 8
    return total - len(missing), total, missing


def validation_completion(validation: dict[str, Any]) -> tuple[int, int, list[str]]:
    missing = missing_validation_labels(validation)
    total = 4
    return total - len(missing), total, missing


def bool_label(value: bool) -> str:
    return "是" if value else "否"


def display_label(value: Any) -> str:
    text = clean_text(value)
    return DISPLAY_LABELS.get(text, text)


def selected_options(options: list[str], current: str, *, empty_label: str | None = None) -> str:
    rows = []
    if empty_label is not None:
        rows.append(f'<option value="">{html.escape(empty_label)}</option>')
    for option in options:
        selected = " selected" if option == current else ""
        safe = html.escape(option)
        label = html.escape(display_label(option))
        rows.append(f'<option value="{safe}"{selected}>{label}</option>')
    return "\n".join(rows)


def path_options(paths: list[Path], current: str, *, empty_label: str | None = None) -> str:
    rows = []
    if empty_label is not None:
        rows.append(f'<option value="">{html.escape(empty_label)}</option>')
    for path in paths:
        value = relative_path(path)
        selected = " selected" if value == current else ""
        safe = html.escape(value)
        rows.append(f'<option value="{safe}"{selected}>{safe}</option>')
    return "\n".join(rows)


def boolean_options(
    current: str = "",
    *,
    empty_label: str | None = None,
    true_label: str = "是",
    false_label: str = "否",
    true_first: bool = False,
) -> str:
    rows = []
    if empty_label is not None:
        rows.append(f'<option value="">{html.escape(empty_label)}</option>')
    options = [("true", true_label), ("false", false_label)] if true_first else [("false", false_label), ("true", true_label)]
    for value, label in options:
        selected = " selected" if value == current else ""
        rows.append(f'<option value="{value}"{selected}>{html.escape(label)}</option>')
    return "\n".join(rows)


def checked(value: bool) -> str:
    return " checked" if value else ""


def open_attr(value: bool) -> str:
    return " open" if value else ""


def esc_html(value: Any) -> str:
    return html.escape(str(value or ""))


def display_value(value: Any, default: str = "未填写") -> str:
    text = clean_text(value)
    if not text:
        return default
    return display_label(text)


def display_bool_value(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未填写"


def join_lines(items: list[str]) -> str:
    return "<br>".join(esc_html(item) for item in items if clean_text(item))


def render_key_values(items: list[tuple[str, Any]]) -> str:
    cells = []
    for label, value in items:
        cells.append(
            f'<div class="kv"><span>{esc_html(label)}</span><strong>{esc_html(display_value(value))}</strong></div>'
        )
    return f'<div class="kv-grid">{"".join(cells)}</div>'


def render_key_values_present(items: list[tuple[str, Any]]) -> str:
    filtered = [(label, value) for label, value in items if has_value(value)]
    if not filtered:
        return '<p class="muted">暂无已填写内容。</p>'
    return render_key_values(filtered)


def render_inline_stats(items: list[tuple[str, str]], *, quiet: bool = False) -> str:
    if not items:
        return ""
    class_name = "inline-stats quiet" if quiet else "inline-stats"
    cells = []
    for label, value in items:
        cells.append(
            f'<div class="inline-stat"><span>{esc_html(label)}</span><strong>{esc_html(value)}</strong></div>'
        )
    return f'<div class="{class_name}">{"".join(cells)}</div>'


def render_playbook_quick_presets(disabled: str) -> str:
    buttons = []
    for key, preset in PLAYBOOK_QUICK_PRESETS.items():
        buttons.append(
            f'<button class="secondary preset-button" type="submit" name="playbook_preset" value="{esc_html(key)}"{disabled}>'
            f'{esc_html(preset["label"])}</button>'
        )
    return '<div class="quick-preset-row">' + "".join(buttons) + "</div>"


def render_us_option_quick_presets(disabled: str) -> str:
    buttons = []
    for key, preset in US_OPTION_QUICK_PRESETS.items():
        buttons.append(
            f'<button class="secondary preset-button" type="submit" name="option_playbook_preset" value="{esc_html(key)}"{disabled}>'
            f'{esc_html(preset["label"])}</button>'
        )
    return '<div class="quick-preset-row">' + "".join(buttons) + "</div>"


def render_opening_30_status(playbook: dict[str, Any]) -> str:
    return render_inline_stats(
        [
            ("开盘计划", display_value(playbook.get("opening_plan"))),
            ("主练形态", display_value(playbook.get("focus_setup"))),
            ("关键信号", "已写" if has_value(playbook.get("open_30_key_signal")) else "未写"),
            ("牛熊过滤", "已写" if has_value(playbook.get("certificate_filter_note")) else "未写"),
            ("异常预案", "已写" if has_value(playbook.get("abnormal_plan")) else "未写"),
        ],
        quiet=True,
    )


def render_us_options_status(playbook: dict[str, Any]) -> str:
    return render_inline_stats(
        [
            ("时段计划", display_value(playbook.get("option_session_plan"))),
            ("主看股票", "已写" if has_value(playbook.get("focus_tickers")) else "未写"),
            ("主练形态", display_value(playbook.get("option_focus_setup"))),
            ("入场信号", "已写" if has_value(playbook.get("option_entry_signal")) else "未写"),
            ("合约过滤", "已写" if has_value(playbook.get("option_contract_filter")) else "未写"),
            ("事件风险", "已写" if has_value(playbook.get("option_event_risk_plan")) else "未写"),
        ],
        quiet=True,
    )


def render_decision_gate(decision_gate: dict[str, Any]) -> str:
    status = clean_text(decision_gate.get("status"))
    status_class = {
        "ready": "gate-ready",
        "observe_only": "gate-caution",
        "blocked": "gate-blocked",
    }.get(status, "gate-caution")
    details = []
    blockers = [clean_text(item) for item in decision_gate.get("blockers", []) if clean_text(item)]
    cautions = [clean_text(item) for item in decision_gate.get("cautions", []) if clean_text(item)]
    strengths = [clean_text(item) for item in decision_gate.get("strengths", []) if clean_text(item)]
    if blockers:
        details.append(render_simple_notes("硬阻断", blockers, empty_text="暂无硬阻断。"))
    if cautions:
        details.append(render_simple_notes("待确认", cautions[:6], empty_text="暂无待确认项。"))
    if strengths:
        details.append(render_simple_notes("已就绪", strengths[:5], empty_text="暂无已就绪项。"))
    return f"""
      <div class="decision-gate {status_class}">
        <div>
          <span>开盘决策门</span>
          <strong>{esc_html(decision_gate.get("label"))}</strong>
          <p>{esc_html(decision_gate.get("action"))}</p>
        </div>
        <div class="decision-gate-notes">
          {''.join(details)}
        </div>
      </div>
    """


def render_risk_controller(risk_state: dict[str, Any]) -> str:
    status = clean_text(risk_state.get("status"))
    status_class = {
        "normal": "gate-ready",
        "cooldown": "gate-caution",
        "protect_profit": "gate-caution",
        "stop": "gate-blocked",
    }.get(status, "gate-caution")
    blockers = [clean_text(item) for item in risk_state.get("blockers", []) if clean_text(item)]
    cautions = [clean_text(item) for item in risk_state.get("cautions", []) if clean_text(item)]
    strengths = [clean_text(item) for item in risk_state.get("strengths", []) if clean_text(item)]
    details = []
    if blockers:
        details.append(render_simple_notes("硬风控", blockers, empty_text="暂无硬风控。"))
    if cautions:
        details.append(render_simple_notes("风险提示", cautions[:6], empty_text="暂无风险提示。"))
    if strengths:
        details.append(render_simple_notes("风险数据", strengths[:4], empty_text="暂无风险数据。"))
    return f"""
      <div class="decision-gate {status_class}">
        <div>
          <span>风险控制器</span>
          <strong>{esc_html(risk_state.get("label"))}</strong>
          <p>{esc_html(risk_state.get("action"))}</p>
        </div>
        <div class="decision-gate-notes">
          {''.join(details)}
        </div>
      </div>
    """


def render_workflow_stage_bar(stage: dict[str, Any]) -> str:
    progress = max(0, min(100, int(stage.get("progress") or 0)))
    return f"""
      <div class="stage-bar">
        <div class="stage-bar-top">
          <span>当前阶段</span>
          <strong>{esc_html(stage.get("label"))}</strong>
        </div>
        <div class="stage-track"><span style="width:{progress}%"></span></div>
        <p>{esc_html(stage.get("note"))}</p>
      </div>
    """


def render_next_action(next_action: dict[str, Any]) -> str:
    level = clean_text(next_action.get("level")) or "neutral"
    details = [clean_text(item) for item in next_action.get("details", []) if clean_text(item)]
    details_html = ""
    if details:
        details_html = '<ul class="next-action-details">' + "".join(f"<li>{esc_html(item)}</li>" for item in details) + "</ul>"
    return f"""
      <div class="next-action next-action-{esc_html(level)}">
        <div>
          <span>下一步动作</span>
          <strong>{esc_html(next_action.get("title"))}</strong>
          <p>{esc_html(next_action.get("body"))}</p>
          {details_html}
        </div>
        <a class="next-action-button" href="{esc_html(next_action.get("target") or "#today-section")}">{esc_html(next_action.get("button") or "查看")}</a>
      </div>
    """


def render_execution_lock_banner(lock: dict[str, Any]) -> str:
    status = clean_text(lock.get("status")) or "open"
    reasons = [clean_text(item) for item in lock.get("reasons", []) if clean_text(item)]
    reason_text = "；".join(reasons[:4])
    reason_html = f"<p>{esc_html(reason_text)}</p>" if reason_text else ""
    return f"""
      <div class="execution-lock execution-lock-{esc_html(status)}">
        <strong>交易执行锁：{esc_html(lock.get("label"))}</strong>
        <span>{esc_html(lock.get("action"))}</span>
        {reason_html}
      </div>
    """


def render_acceptance_gate(acceptance_gate: dict[str, Any]) -> str:
    passed = acceptance_gate.get("passed") is True
    class_name = "acceptance-pass" if passed else "acceptance-fail"
    rows = []
    for check in acceptance_gate.get("checks", []):
        status = "通过" if check.get("passed") else "未过"
        status_class = "check-pass" if check.get("passed") else "check-fail"
        rows.append(
            f'<li class="{status_class}">'
            f'<a href="{esc_html(check.get("target") or "#command-center")}">'
            f'<strong>{esc_html(check.get("label"))}</strong>'
            f'<span>{esc_html(status)} · {esc_html(check.get("detail"))}</span>'
            "</a>"
            "</li>"
        )
    return f"""
      <div class="acceptance-gate {class_name}">
        <div class="acceptance-head">
          <div>
            <span>主战单日验收</span>
            <strong>{esc_html(acceptance_gate.get("label"))}</strong>
          </div>
          <div class="acceptance-score">{esc_html(str(acceptance_gate.get("passed_count")))} / {esc_html(str(acceptance_gate.get("total")))}</div>
        </div>
        <ul class="acceptance-checks">{''.join(rows)}</ul>
      </div>
    """


def render_acceptance_repair_panel(
    acceptance_gate: dict[str, Any],
    record_input: str,
    disabled: str,
    review: dict[str, Any],
    validation: dict[str, Any],
) -> str:
    if acceptance_gate.get("passed") is True:
        return '<p class="muted">单日验收已通过，不需要修复动作。</p>'
    failed_keys = {check.get("key") for check in acceptance_gate.get("failed", [])}
    actions = []
    if "phase2_trade_fields" in failed_keys:
        actions.append(
            '<a class="repair-link" href="#trade-section">检查交易字段</a>'
            '<span>补齐每笔交易的时段、四条件、工具过滤和异常场景。</span>'
        )
    if "sample_trusted" in failed_keys:
        actions.append(
            '<form method="post" action="/sync-review-numbers#review-section">'
            f'<input type="hidden" name="record_path" value="{record_input}">'
            '<input type="hidden" name="after_action" value="closeout">'
            f'<button class="secondary small-button" type="submit"{disabled}>同步复盘数字并更新归档</button>'
            '</form>'
            '<span>只同步交易数和盈亏；复盘文字如果仍是占位值，需要到盘后复盘手工改成真实结论。</span>'
        )
        actions.append(
            '<a class="repair-link" href="#review-quality-assistant">修复复盘文字</a>'
            f'<span>需要真人补齐：{esc_html("、".join(review_text_quality_issue_labels(review, validation)) or "复盘结论")}。</span>'
        )
    if "closeout_synced" in failed_keys:
        actions.append(
            '<form method="post" action="/closeout#closeout-preview">'
            f'<input type="hidden" name="record_path" value="{record_input}">'
            '<input type="hidden" name="regenerate" value="true">'
            f'<button class="secondary small-button" type="submit"{disabled}>重新生成归档</button>'
            '</form>'
            '<span>用当前记录强制覆盖生成最新归档草稿。</span>'
        )
    if not actions:
        actions.append('<a class="repair-link" href="#command-center">查看验收项</a><span>按未通过项逐项处理。</span>')
    rows = "".join(f"<li>{action}</li>" for action in actions)
    return f"""
      <div class="acceptance-repair">
        <h3>验收修复台</h3>
        <ul>{rows}</ul>
      </div>
    """


def render_acceptance_review_textarea(name: str, label: str, value: Any, prompt: str, disabled: str) -> str:
    return (
        '<div class="acceptance-review-field">'
        f'<label for="acceptance-{esc_html(name)}">{esc_html(label)}</label>'
        f'<textarea id="acceptance-{esc_html(name)}" name="{esc_html(name)}" required{disabled}>'
        f'{esc_html(clean_text(value))}</textarea>'
        f'<span>{esc_html(prompt)}</span>'
        '</div>'
    )


def render_review_quality_assistant(
    review: dict[str, Any],
    validation: dict[str, Any],
    record_input: str,
    disabled: str,
    trades: list[dict[str, Any]],
) -> str:
    if not is_review_done(review) or not is_validation_done(validation):
        return ""
    if review_text_quality_ok(review, validation):
        return ""
    review_defaults = build_review_defaults(review, trades)
    items = review_text_quality_issue_items(review, validation)
    rows = []
    for item in items:
        skeleton_html = f'<code>{esc_html(item["skeleton"])}</code>' if item.get("skeleton") else ""
        rows.append(
            '<li>'
            f'<a class="repair-link" href="{esc_html(item["target"])}">定位</a>'
            '<div class="repair-prompt-body">'
            f'<strong>{esc_html(item["label"])}</strong>'
            f'<span>{esc_html(item["prompt"])}</span>'
            f'{skeleton_html}'
            f'<em>当前：{esc_html(item["current"])}</em>'
            '</div>'
            '</li>'
        )
    review_fields = []
    for key in REVIEW_TEXT_QUALITY_FIELDS:
        meta = REVIEW_TEXT_QUALITY_PROMPTS.get(key, {})
        review_fields.append(
            render_acceptance_review_textarea(
                key,
                field_label(key),
                review.get(key),
                meta.get("prompt", "补成能对应当天事实的完整句子。"),
                disabled,
            )
        )
    validation_key = "no_trade_note" if validation.get("no_trade_day") is True else "main_issue_of_day"
    validation_meta = REVIEW_TEXT_QUALITY_PROMPTS.get(validation_key, {})
    validation_field = render_acceptance_review_textarea(
        validation_key,
        field_label(validation_key),
        validation.get(validation_key),
        validation_meta.get("prompt", "补成能对应当天事实的完整句子。"),
        disabled,
    )
    return f"""
      <div class="review-quality-assistant" id="review-quality-assistant">
        <div class="repair-assistant-head">
          <span>记录完整性缺口</span>
          <strong>复盘文字需要补成当天事实</strong>
        </div>
        <ul class="repair-prompt-list">{''.join(rows)}</ul>
        <form class="acceptance-final-form" method="post" action="/save-acceptance-review#command-center">
          <input type="hidden" name="record_path" value="{record_input}">
          <div class="acceptance-final-head">
            <div>
              <strong>终局验收复盘</strong>
              <span>客观数字按当前交易事实锁定：交易 {esc_html(review_defaults["trade_count_hint"])} 笔，盈亏 {esc_html(review_defaults["pnl_hint"])}。</span>
            </div>
            <button type="submit"{disabled}>保存终局复盘并更新归档</button>
          </div>
          <div class="acceptance-review-grid">{''.join(review_fields)}{validation_field}</div>
        </form>
      </div>
    """


def render_previous_context(previous_context: dict[str, str]) -> str:
    if not previous_context:
        return '<p class="muted">暂无上一交易日可继承改进。</p>'
    lines = []
    if previous_context.get("next_fix"):
        lines.append(f"上一日只改：{previous_context['next_fix']}")
    if previous_context.get("improvement"):
        lines.append(f"上一日改进：{previous_context['improvement']}")
    if previous_context.get("main_issue"):
        lines.append(f"上一日问题：{previous_context['main_issue']}")
    plan_bits = [
        display_value(previous_context.get("plan")) if previous_context.get("plan") else "",
        display_value(previous_context.get("setup")) if previous_context.get("setup") else "",
    ]
    plan_text = " / ".join(bit for bit in plan_bits if bit)
    if plan_text:
        mode_text = display_value(previous_context.get("trading_mode")) if previous_context.get("trading_mode") else "主战"
        lines.append(f"上一日{mode_text}计划：{plan_text}")
    title = f"继承 {previous_context.get('trade_date') or '-'}"
    return render_simple_notes(title, lines, empty_text="上一日没有可继承改进。")


def render_phase2_command_center(
    *,
    decision_gate: dict[str, Any],
    risk_state: dict[str, Any],
    acceptance_gate: dict[str, Any],
    next_action: dict[str, Any],
    previous_context: dict[str, str],
    record_input: str,
    page_disabled: str,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
) -> str:
    failed_phase2 = sum(1 for trade in trades if phase2_trade_checks_passed(trade) is False)
    filter_fail = sum(1 for trade in trades if trade.get("certificate_filter_passed") is False)
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    filter_label = filter_label_for_mode(trading_mode)
    if trading_mode == "us_stock_options":
        plan_label = display_value(playbook.get("option_session_plan"))
        setup_label = display_value(playbook.get("option_focus_setup"))
    else:
        plan_label = display_value(playbook.get("opening_plan"))
        setup_label = display_value(playbook.get("focus_setup"))
    abnormal_trades = [
        trade for trade in trades if clean_text(trade.get("abnormal_scenario")) not in {"", "none"}
    ]
    stop_events = [
        event for event in events if clean_text(event.get("event_type")) in {"forced_pause", "forced_stop"}
    ]
    current_abnormal_guidance = []
    for trade in abnormal_trades[-3:]:
        scenario = clean_text(trade.get("abnormal_scenario"))
        guidance = ABNORMAL_SCENARIO_GUIDANCE.get(scenario)
        if guidance:
            current_abnormal_guidance.append(f"{clean_text(trade.get('trade_id'))}：{guidance}")

    return f"""
      <section class="card wide" id="command-center">
        <h2>{esc_html(display_value(trading_mode))}主战驾驶舱</h2>
        <p class="muted">这一层把盘前决策、盘中纪律和复盘记录质量收成一个产品主路径；Phase 3 美股期权也挂在同一条主干上。</p>
        {render_workflow_stage_bar(next_action["stage"])}
        {render_next_action(next_action)}
        {render_decision_gate(decision_gate)}
        {render_risk_controller(risk_state)}
        {render_acceptance_gate(acceptance_gate)}
        {render_acceptance_repair_panel(acceptance_gate, record_input, page_disabled, review, validation)}
        <div class="status-grid command-metrics">
          <div class="metric"><span>主方向</span><strong>{esc_html(display_value(workbench.get("main_direction")))}</strong></div>
          <div class="metric"><span>主计划</span><strong>{esc_html(plan_label)}</strong></div>
          <div class="metric"><span>主练形态</span><strong>{esc_html(setup_label)}</strong></div>
          <div class="metric"><span>四条件未齐</span><strong>{failed_phase2}</strong></div>
          <div class="metric"><span>{esc_html(filter_label)}未过</span><strong>{filter_fail}</strong></div>
          <div class="metric"><span>异常交易</span><strong>{len(abnormal_trades)}</strong></div>
          <div class="metric"><span>暂停 / 停手事件</span><strong>{len(stop_events)}</strong></div>
        </div>
        {render_previous_context(previous_context)}
        {render_simple_notes("异常场景处理", current_abnormal_guidance, empty_text="当前交易记录里还没有异常场景交易。")}
      </section>
    """


def render_rule_event_preset_buttons(disabled: str) -> str:
    buttons = []
    for key, preset in RULE_EVENT_PRESETS.items():
        buttons.append(
            f'<button class="secondary preset-button" type="submit" name="preset_key" value="{esc_html(key)}"{disabled}>'
            f'{esc_html(preset["label"])}</button>'
        )
    return '<div class="quick-preset-row">' + "".join(buttons) + "</div>"


def format_number(value: float | None, *, suffix: str = "") -> str:
    return shared_format_number(value, suffix=suffix)


def build_day_summary(workbench: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, str]:
    capital = number_value(workbench.get("capital_used"))
    target_pct = number_value(workbench.get("profit_target_pct"))
    pnl_values = [number_value(trade.get("pnl_amount")) for trade in trades]
    pnl_total = sum(value for value in pnl_values if value is not None)
    has_pnl = any(value is not None for value in pnl_values)
    pnl_pct = pnl_total / capital * 100 if capital and has_pnl else None
    target_amount = capital * target_pct / 100 if capital and target_pct is not None else None
    target_distance = target_amount - pnl_total if target_amount is not None and has_pnl else None
    violations = sum(1 for trade in trades if trade.get("rule_violation") is True)
    grade_counts = {grade: sum(1 for trade in trades if clean_text(trade.get("abc_grade")) == grade) for grade in GRADE_OPTIONS}
    return {
        "capital_used": format_number(capital),
        "profit_target_pct": format_number(target_pct, suffix="%"),
        "pnl_total": format_number(pnl_total if has_pnl else None),
        "pnl_pct": format_number(pnl_pct, suffix="%"),
        "target_distance": format_number(target_distance),
        "trade_count": str(len(trades)),
        "violation_count": str(violations),
        "grade_counts": " · ".join(f"{grade} {grade_counts[grade]}" for grade in GRADE_OPTIONS),
    }


def build_review_defaults(review: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, str]:
    pnl_values = [number_value(trade.get("pnl_amount")) for trade in trades]
    pnl_values = [value for value in pnl_values if value is not None]
    derived_pnl_number = sum(pnl_values) if pnl_values else None
    derived_pnl = format_number(derived_pnl_number) if derived_pnl_number is not None else ""
    derived_trade_count = str(len(trades))
    review_pnl = clean_text(review.get("pnl"))
    review_trade_count = clean_text(review.get("trade_count"))
    review_pnl_number = number_value(review_pnl)
    pnl_mismatch = (
        derived_pnl_number is not None
        and review_pnl_number is not None
        and not numeric_almost_equal(review_pnl_number, derived_pnl_number)
    )
    trade_count_mismatch = bool(review_trade_count and review_trade_count != derived_trade_count)
    return {
        "pnl": derived_pnl if pnl_mismatch else review_pnl or derived_pnl,
        "trade_count": derived_trade_count if trade_count_mismatch else review_trade_count or derived_trade_count,
        "pnl_hint": derived_pnl or "--",
        "trade_count_hint": derived_trade_count,
    }


def render_day_summary_metrics(summary: dict[str, str]) -> str:
    items = [
        ("当日使用本金", summary["capital_used"]),
        ("盈利目标%", summary["profit_target_pct"]),
        ("当日盈亏", summary["pnl_total"]),
        ("当日盈亏%", summary["pnl_pct"]),
        ("距目标", summary["target_distance"]),
        ("交易次数", summary["trade_count"]),
        ("违规", summary["violation_count"]),
        ("A/B/C", summary["grade_counts"]),
    ]
    return "".join(
        f'<div class="metric"><span>{esc_html(label)}</span><strong>{esc_html(value)}</strong></div>'
        for label, value in items
    )


def trade_pnl_total(trades: list[dict[str, Any]]) -> float | None:
    return shared_trade_pnl_total(trades)


def phase2_trade_checks_passed(trade: dict[str, Any]) -> bool | None:
    return record_checks.phase2_trade_checks_passed(trade)


def previous_record_context(current_path: Path | None, record_paths: list[Path]) -> dict[str, str]:
    if not current_path:
        return {}
    current_day = record_day_number(current_path)
    if current_day is None:
        return {}
    candidates = [
        path
        for path in record_paths
        if path.resolve() != current_path.resolve()
        and (record_day_number(path) is not None)
        and (record_day_number(path) or 0) < current_day
    ]
    if not candidates:
        return {}
    previous_path = sorted(candidates, key=lambda path: record_day_number(path) or -1, reverse=True)[0]
    try:
        previous = load_record(previous_path)
    except Exception:
        return {}
    review = previous["review"]
    validation = previous["validation"]
    playbook = previous["playbook"]
    base = previous["base"]
    workbench = previous["workbench"]
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    return {
        "day": clean_text(base.get("day_number")),
        "trade_date": clean_text(base.get("trade_date")),
        "trading_mode": trading_mode,
        "next_fix": clean_text(review.get("next_day_one_fix")),
        "improvement": clean_text(validation.get("main_improvement_of_day")),
        "main_issue": clean_text(validation.get("main_issue_of_day")),
        "plan": playbook_plan_value(playbook, trading_mode),
        "setup": playbook_setup_value(playbook, trading_mode),
    }


def is_meaningful_review_sentence(value: Any) -> bool:
    return record_checks.is_meaningful_review_sentence(value)


def review_text_quality_ok(review: dict[str, Any], validation: dict[str, Any]) -> bool:
    return record_checks.review_text_quality_ok(
        review,
        validation,
        review_text_quality_fields=REVIEW_TEXT_QUALITY_FIELDS,
    )


def review_text_quality_issue_items(review: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, str]]:
    items = []
    issue_keys = set(
        record_checks.review_text_quality_issue_keys(
            review,
            validation,
            review_text_quality_fields=REVIEW_TEXT_QUALITY_FIELDS,
        )
    )
    for key in REVIEW_TEXT_QUALITY_FIELDS:
        if key not in issue_keys:
            continue
        meta = REVIEW_TEXT_QUALITY_PROMPTS.get(key, {})
        items.append(
            {
                "key": key,
                "label": field_label(key),
                "target": meta.get("target", "#review-section"),
                "prompt": meta.get("prompt", "补成能对应当天事实的完整句子。"),
                "skeleton": meta.get("skeleton", ""),
                "current": clean_text(review.get(key)) or "空",
            }
        )
    validation_key = "no_trade_note" if validation.get("no_trade_day") is True else "main_issue_of_day"
    validation_value = validation.get(validation_key)
    if validation_key in issue_keys:
        meta = REVIEW_TEXT_QUALITY_PROMPTS.get(validation_key, {})
        items.append(
            {
                "key": validation_key,
                "label": field_label(validation_key),
                "target": meta.get("target", "#validation-section"),
                "prompt": meta.get("prompt", "补成能对应当天事实的完整句子。"),
                "skeleton": meta.get("skeleton", ""),
                "current": clean_text(validation_value) or "空",
            }
        )
    return items


def review_text_quality_issue_labels(review: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    return [item["label"] for item in review_text_quality_issue_items(review, validation)]


def review_hub_quality_issues(
    *,
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
) -> list[str]:
    return record_checks.review_hub_quality_issues(
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        review_text_quality_fields=REVIEW_TEXT_QUALITY_FIELDS,
    )


def format_ratio_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "--"
    return format_number(numerator / denominator * 100, suffix="%")


def enrich_review_hub_snapshot_from_sqlite(
    snapshot: dict[str, Any],
    *,
    current_record_path: Path | None,
) -> dict[str, Any]:
    path_text = clean_text(snapshot.get("path"))
    record_path: Path | None = None
    try:
        record_path = resolve_path(path_text) if path_text else None
    except Exception:
        record_path = None
    closeout_exists, closeout_legacy, closeout_stale = (False, False, False)
    if record_path and record_path.exists():
        closeout_exists, closeout_legacy, closeout_stale = closeout_status_for_record(
            record_path,
            {"day_number": snapshot.get("day"), "trade_date": snapshot.get("trade_date")},
        )
    return {
        **snapshot,
        "state": display_value(snapshot.get("state"), default="未填"),
        "is_current": bool(current_record_path and record_path and record_path.resolve() == current_record_path.resolve()),
        "is_editable": bool(current_record_path and record_path and record_path.resolve() == current_record_path.resolve()),
        "closeout_label": closeout_status_label(
            exists=closeout_exists,
            legacy=closeout_legacy,
            stale=closeout_stale,
        ),
        "closeout_synced": closeout_exists and not closeout_legacy and not closeout_stale,
    }


def build_review_hub_summary_from_sqlite(stats: dict[str, Any], snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    day_count = int(stats.get("day_count") or 0)
    return {
        "day_count": day_count,
        "trade_day_count": int(stats.get("trade_day_count") or 0),
        "no_trade_day_count": int(stats.get("no_trade_day_count") or 0),
        "total_pnl": format_number(stats.get("total_pnl")),
        "avg_daily_pnl": format_number(stats.get("avg_daily_pnl")),
        "trade_count": str(int(stats.get("trade_count") or 0)),
        "violation_count": str(int(stats.get("violation_count") or 0)),
        "review_done": f"{int(stats.get('review_done_days') or 0)}/{day_count}" if day_count else "0/0",
        "validation_done": f"{int(stats.get('validation_done_days') or 0)}/{day_count}" if day_count else "0/0",
        "closeout_synced": f"{sum(1 for snapshot in snapshots if snapshot['closeout_synced'])}/{day_count}" if day_count else "0/0",
        "plan_follow_rate": format_ratio_percent(int(stats.get("followed_yes") or 0), int(stats.get("followed_total") or 0)),
        "win_loss_flat": " / ".join(
            [
                f"赢 {int(stats.get('win_count') or 0)}",
                f"亏 {int(stats.get('loss_count') or 0)}",
                f"平 {int(stats.get('breakeven_count') or 0)}",
            ]
        ),
        "impulsive_days": int(stats.get("impulsive_days") or 0),
        "stop_loss_days": int(stats.get("stop_loss_days") or 0),
        "overtrade_days": int(stats.get("overtrade_days") or 0),
        "opening_30_trade_count": int(stats.get("opening_30_trade_count") or 0),
        "phase2_check_fail_count": int(stats.get("phase2_check_fail_count") or 0),
        "certificate_filter_fail_count": int(stats.get("certificate_filter_fail_count") or 0),
        "abnormal_trade_count": int(stats.get("abnormal_trade_count") or 0),
        "top_setups": [
            (display_value(item["setup_type"], default=item["setup_type"]), item["count"])
            for item in stats.get("top_setups", [])
            if clean_text(item.get("setup_type"))
        ],
        "top_active_plans": [
            (display_value(item["active_plan"], default=item["active_plan"]), item["count"])
            for item in stats.get("top_active_plans", [])
            if clean_text(item.get("active_plan"))
        ],
        "top_active_setups": [
            (display_value(item["active_setup"], default=item["active_setup"]), item["count"])
            for item in stats.get("top_active_setups", [])
            if clean_text(item.get("active_setup"))
        ],
        "recent_issues": [
            f"{item['trade_date']}：{item['main_issue']}"
            for item in stats.get("recent_issues", [])
            if clean_text(item.get("main_issue"))
        ],
        "recent_fixes": [
            f"{item['trade_date']}：{item['next_fix']}"
            for item in stats.get("recent_fixes", [])
            if clean_text(item.get("next_fix"))
        ],
        "recent_no_trade_notes": [
            f"{item['trade_date']}：{item['no_trade_note']}"
            for item in stats.get("recent_no_trade_notes", [])
            if clean_text(item.get("no_trade_note"))
        ],
    }


def render_review_hub_metrics(summary: dict[str, Any]) -> str:
    items = [
        ("交易天数", str(summary["day_count"])),
        ("有交易日", str(summary["trade_day_count"])),
        ("空仓日", str(summary["no_trade_day_count"])),
        ("总盈亏", summary["total_pnl"]),
        ("交易日日均盈亏", summary["avg_daily_pnl"]),
        ("总交易数", summary["trade_count"]),
        ("违规次数", summary["violation_count"]),
        ("按计划率", summary["plan_follow_rate"]),
        ("开盘时段交易", str(summary["opening_30_trade_count"])),
        ("四条件未齐", str(summary["phase2_check_fail_count"])),
        ("工具过滤未过", str(summary["certificate_filter_fail_count"])),
        ("异常场景交易", str(summary["abnormal_trade_count"])),
        ("赢 / 亏 / 平", summary["win_loss_flat"]),
        ("复盘完整", summary["review_done"]),
        ("验证完整", summary["validation_done"]),
        ("归档同步", summary["closeout_synced"]),
    ]
    return "".join(
        f'<div class="metric"><span>{esc_html(label)}</span><strong>{esc_html(str(value))}</strong></div>'
        for label, value in items
    )


def render_review_hub_day_table(snapshots: list[dict[str, Any]]) -> str:
    if not snapshots:
        return '<p class="muted">暂无可用于复盘中心的交易日记录。</p>'

    rows = []
    for snapshot in snapshots:
        mode_parts = []
        if snapshot["is_current"]:
            mode_parts.append("当前")
        if snapshot["is_editable"]:
            mode_parts.append("可编辑")
        else:
            mode_parts.append("只读")
        if snapshot["no_trade_day"]:
            mode_parts.append("空仓日")
        if snapshot["trusted_sample"]:
            mode_parts.append("完整")
        else:
            mode_parts.append("有缺口")
        quality_note = "；".join(snapshot["quality_issues"]) if snapshot["quality_issues"] else "记录完整"
        button_label = "当前" if snapshot["is_current"] else ("载入" if snapshot["is_editable"] else "查看")
        disabled = " disabled" if snapshot["is_current"] else ""
        rows.append(
            "<tr>"
            f"<td><strong>{esc_html(snapshot['trade_date'])}</strong><br><span>{esc_html(' / '.join(mode_parts))}</span></td>"
            f"<td>{esc_html(display_value(snapshot.get('trading_mode')))}<br><span>{esc_html(snapshot['state'])}</span></td>"
            f"<td>{esc_html(str(snapshot['trade_count']))}<br><span>违规 {esc_html(str(snapshot['violation_count']))}</span></td>"
            f"<td>{esc_html(format_number(snapshot['pnl_value']))}</td>"
            f"<td>{esc_html(bool_label(snapshot['review_done']))} / {esc_html(bool_label(snapshot['validation_done']))}<br><span>{esc_html(quality_note)}</span></td>"
            f"<td>{esc_html(snapshot['closeout_label'])}</td>"
            f'<td><form method="post" action="/load-record#review-hub"><input type="hidden" name="record_path" value="{esc_html(snapshot["path"])}"><button class="secondary small-button" type="submit"{disabled}>{button_label}</button></form></td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="compact-table"><thead><tr>'
        "<th>交易日</th><th>日期 / 状态</th><th>交易</th><th>盈亏</th><th>复盘 / 验证</th><th>归档</th><th>查看</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_simple_notes(title: str, lines: list[str], *, empty_text: str) -> str:
    if not lines:
        return f'<div class="note-block"><h3>{esc_html(title)}</h3><p class="muted">{esc_html(empty_text)}</p></div>'
    items = "".join(f"<li>{esc_html(line)}</li>" for line in lines)
    return f'<div class="note-block"><h3>{esc_html(title)}</h3><ul class="note-list">{items}</ul></div>'


def render_top_setup_tags(items: list[tuple[str, int]], *, empty_text: str = "最近几天还没有可统计的交易形态。") -> str:
    if not items:
        return f'<p class="muted">{esc_html(empty_text)}</p>'
    tags = "".join(
        f'<span class="setup-tag"><strong>{esc_html(name)}</strong><span>{esc_html(str(count))}</span></span>'
        for name, count in items
    )
    return f'<div class="setup-tag-row">{tags}</div>'


def render_review_hub_sample_quality(
    all_snapshots: list[dict[str, Any]],
    visible_snapshots: list[dict[str, Any]],
    sample_filter: str,
) -> str:
    low_trust = [snapshot for snapshot in all_snapshots if not snapshot["trusted_sample"]]
    if normalize_review_hub_sample_filter(sample_filter) == "all":
        if not low_trust:
            return '<p class="muted">当前显示全部记录；历史交易日保持只读。</p>'
        return (
            f'<p class="muted">当前显示全部记录，其中 {len(low_trust)} 个交易日存在记录缺口，仅作为历史事实保留。</p>'
        )

    excluded = [snapshot for snapshot in all_snapshots if not snapshot["trusted_sample"]]
    if not excluded:
        return '<p class="muted">当前范围内记录完整。</p>'
    lines = [
        f"{snapshot['trade_date']}：{'；'.join(snapshot['quality_issues'])}"
        for snapshot in excluded[:4]
    ]
    suffix = "" if len(excluded) <= 4 else f"；另有 {len(excluded) - 4} 个交易日已过滤"
    return (
        f'<p class="muted">当前统计只使用 {len(visible_snapshots)} 个完整记录，已过滤 {len(excluded)} 个记录缺口交易日{suffix}。</p>'
        + render_simple_notes("记录缺口", lines, empty_text="暂无记录缺口。")
    )


def render_trade_table(trades: list[dict[str, Any]]) -> str:
    if not trades:
        return '<p class="muted">暂无真实交易记录。</p>'

    rows = []
    for trade in trades:
        filter_label = trade_filter_label(trade)
        prices = [
            f"入场 {trade.get('entry_price')}" if has_value(trade.get("entry_price")) else "",
            f"止损 {trade.get('stop_loss')}" if has_value(trade.get("stop_loss")) else "",
            f"目标 {trade.get('target_price')}" if has_value(trade.get("target_price")) else "",
            f"平仓 {trade.get('exit_price')}" if has_value(trade.get("exit_price")) else "",
        ]
        pnl_lines = [
            f"盈亏 {trade.get('pnl_amount')}" if has_value(trade.get("pnl_amount")) else "",
            f"盈亏比 {trade.get('risk_reward_ratio')}" if has_value(trade.get("risk_reward_ratio")) else "",
        ]
        detail_lines = [
            (
                f"时段：{display_value(trade.get('session_window'))}"
                + (
                    f"；异常：{display_value(trade.get('abnormal_scenario'))}"
                    if clean_text(trade.get("abnormal_scenario")) not in {"", "none"}
                    else ""
                )
            )
            if has_value(trade.get("session_window")) or clean_text(trade.get("abnormal_scenario")) not in {"", "none"}
            else "",
            (
                "四条件："
                + " / ".join(
                    [
                        f"方向{display_bool_value(trade.get('direction_clear'))}",
                        f"位置{display_bool_value(trade.get('location_ok'))}",
                        f"确认{display_bool_value(trade.get('confirmation_ok'))}",
                        f"风险{display_bool_value(trade.get('risk_clear'))}",
                    ]
                )
            )
            if any(trade.get(key) in {True, False} for key in ["direction_clear", "location_ok", "confirmation_ok", "risk_clear"])
            else "",
            f"{filter_label}：{display_bool_value(trade.get('certificate_filter_passed'))}"
            if trade.get("certificate_filter_passed") in {True, False}
            else "",
            f"入场逻辑：{clean_text(trade.get('entry_reason'))}" if clean_text(trade.get("entry_reason")) else "",
            f"平仓原因：{clean_text(trade.get('exit_reason'))}" if clean_text(trade.get("exit_reason")) else "",
            f"违规说明：{clean_text(trade.get('violation_note'))}" if clean_text(trade.get("violation_note")) else "",
            f"截图：{clean_text(trade.get('screenshot_note'))}" if clean_text(trade.get("screenshot_note")) else "",
            f"复盘备注：{clean_text(trade.get('review_note'))}" if clean_text(trade.get("review_note")) else "",
        ]
        emotion_lines = [
            f"开仓前 {display_value(trade.get('pre_trade_emotion'))}" if has_value(trade.get("pre_trade_emotion")) else "",
            f"平仓后 {display_value(trade.get('post_trade_emotion'))}" if has_value(trade.get("post_trade_emotion")) else "",
        ]
        setup_line = esc_html(display_value(trade.get("setup_type")))
        if has_value(trade.get("abc_grade")) or has_value(trade.get("setup_score")):
            setup_line += f"<br><span>{esc_html(display_value(trade.get('abc_grade')))} / 评分 {esc_html(display_value(trade.get('setup_score')))}</span>"
        tool_meta = " / ".join(
            display_value(trade.get(key))
            for key in ["underlying", "certificate_side", "instrument_type"]
            if has_value(trade.get(key))
        ) or display_value(trade.get("instrument_type"))
        rows.append(
            "<tr>"
            f"<td><code>{esc_html(clean_text(trade.get('trade_id')) or '未编号')}</code></td>"
            f"<td>{esc_html(display_value(trade.get('trade_time')))}<br><span>平仓 {esc_html(display_value(trade.get('exit_time')))}</span></td>"
            f"<td>{esc_html(display_value(trade.get('direction')))}</td>"
            f"<td>{esc_html(display_value(trade.get('instrument_code')))}<br><span>{esc_html(tool_meta)}</span></td>"
            f"<td>{setup_line}</td>"
            f"<td>{esc_html(' / '.join(item for item in prices if item) or '未填写')}</td>"
            f"<td>{esc_html(' / '.join(item for item in pnl_lines if item) or display_value(trade.get('result')))}</td>"
            f"<td>{esc_html(display_bool_value(trade.get('followed_plan')))} / 违规 {esc_html(display_bool_value(trade.get('rule_violation')))}</td>"
            f"<td>{esc_html(' / '.join(item for item in emotion_lines if item) or display_value(trade.get('emotion_state')))}</td>"
            f"<td>{join_lines(detail_lines) or '未填写'}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>ID</th><th>时间</th><th>方向</th><th>工具</th><th>形态 / 等级</th><th>价格</th><th>盈亏</th><th>计划 / 违规</th><th>情绪</th><th>说明</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_event_table(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<p class="muted">暂无真实纪律事件。</p>'

    rows = []
    for event in events:
        detail_lines = [
            f"触发原因：{clean_text(event.get('trigger_reason'))}" if clean_text(event.get("trigger_reason")) else "",
            f"采取动作：{clean_text(event.get('action_taken'))}" if clean_text(event.get("action_taken")) else "",
            f"后续说明：{clean_text(event.get('follow_up_note'))}" if clean_text(event.get("follow_up_note")) else "",
        ]
        rows.append(
            "<tr>"
            f"<td><code>{esc_html(clean_text(event.get('event_id')) or '未编号')}</code></td>"
            f"<td>{esc_html(display_value(event.get('time')))}</td>"
            f"<td>{esc_html(display_value(event.get('event_type')))}</td>"
            f"<td>{esc_html(display_value(event.get('severity')))}</td>"
            f"<td>{esc_html(display_value(event.get('linked_trade_id'), '不关联交易'))}</td>"
            f"<td>{join_lines(detail_lines) or '未填写'}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>ID</th><th>时间</th><th>类型</th><th>级别</th><th>关联交易</th><th>说明</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_record_readable_view(record: dict[str, Any], _record_path: Path) -> str:
    trades = record["trades"]
    events = record["events"]
    review = record["review"]
    validation = record["validation"]
    workbench = record["workbench"]
    playbook = record["playbook"]
    validation_passed = (
        validation.get("pre_market_done") is True
        and validation.get("intraday_record_complete") is True
        and validation.get("post_market_review_done") is True
    )

    workbench_items = [
        ("模式", workbench.get("trading_mode")),
        ("当日主方向", None if clean_text(workbench.get("main_direction")) == "undecided" else workbench.get("main_direction")),
        ("当前状态", None if clean_text(workbench.get("current_state")) == "unset" else workbench.get("current_state")),
        ("当日使用本金", workbench.get("capital_used")),
        ("盈利目标%", workbench.get("profit_target_pct")),
        ("盘后总结", workbench.get("post_market_summary")),
    ]
    workbench_view = render_key_values_present(workbench_items)
    trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    if trading_mode == "us_stock_options":
        playbook_items = [
            ("期权时段计划", playbook.get("option_session_plan")),
            ("主看股票池", playbook.get("focus_tickers")),
            ("期权主练形态", playbook.get("option_focus_setup")),
            ("期权入场信号", playbook.get("option_entry_signal")),
            ("期权合约过滤", playbook.get("option_contract_filter")),
            ("期权风控计划", playbook.get("option_risk_plan")),
            ("事件风险预案", playbook.get("option_event_risk_plan")),
        ]
    else:
        playbook_items = [
            ("开盘计划", playbook.get("opening_plan")),
            ("主练形态", playbook.get("focus_setup")),
            ("开盘 30 分钟关键信号", playbook.get("open_30_key_signal")),
            ("牛熊证过滤提醒", playbook.get("certificate_filter_note")),
            ("异常场景预案", playbook.get("abnormal_plan")),
        ]
    playbook_view = render_key_values_present(playbook_items)
    record_overview = render_inline_stats(
        [
            ("交易", str(len(trades))),
            ("纪律", str(len(events))),
            ("复盘", bool_label(is_review_done(review))),
            ("验证", bool_label(is_validation_done(validation))),
        ],
        quiet=True,
    )
    review_core_items = [
        ("当日盈亏", review.get("pnl")),
        ("交易数", review.get("trade_count")),
        ("最好的一笔 / 最好动作", review.get("best_trade_note")),
        ("最差的一笔 / 最差问题", review.get("worst_trade_note")),
        ("执行问题", review.get("execution_issue")),
        ("情绪问题", review.get("emotion_issue")),
        ("风控问题", review.get("risk_issue")),
        ("明天只改 1 件事", review.get("next_day_one_fix")),
    ]
    review_optional_items = [
        ("胜率", review.get("win_rate")),
        ("最大亏损单", review.get("max_loss_trade")),
        ("行情问题", review.get("market_issue")),
        ("形态问题", review.get("setup_issue")),
    ]
    review_items = review_core_items + [(label, value) for label, value in review_optional_items if has_value(value)]
    review_view = render_key_values_present(review_items)
    validation_items = []
    if validation.get("pre_market_done") is True or validation.get("intraday_record_complete") is True or validation.get("post_market_review_done") is True:
        validation_items.extend(
            [
                ("盘前完成", display_bool_value(validation.get("pre_market_done"))),
                ("盘中记录完成", display_bool_value(validation.get("intraday_record_complete"))),
                ("盘后复盘完成", display_bool_value(validation.get("post_market_review_done"))),
                ("最小流程通过", "是" if validation_passed else "否"),
            ]
        )
    if validation.get("impulsive_trade_detected") is True:
        validation_items.append(("出现冲动交易", "是"))
    if validation.get("no_stop_loss_trade_detected") is True:
        validation_items.append(("出现无止损 / 止损失守", "是"))
    if validation.get("emotional_overtrade_detected") is True:
        validation_items.append(("出现情绪化过度交易", "是"))
    if validation.get("no_trade_day") is True:
        validation_items.append(("无交易日", "是"))
    if has_value(validation.get("no_trade_note")):
        validation_items.append(("空仓说明", validation.get("no_trade_note")))
    if has_value(validation.get("main_issue_of_day")):
        validation_items.append(("当日主要问题", validation.get("main_issue_of_day")))
    if has_value(validation.get("main_improvement_of_day")):
        validation_items.append(("当日主要改进", validation.get("main_improvement_of_day")))
    validation_view = render_key_values_present(validation_items)

    return f"""
      <div class="readable-preview">
        {record_overview}
        <section class="preview-block">
          <h3>每日作战台</h3>
          {workbench_view}
        </section>
        <section class="preview-block">
          <h3>{esc_html(playbook_title_for_mode(trading_mode))}</h3>
          {playbook_view}
        </section>
        <section class="preview-block">
          <h3>交易记录</h3>
          {render_trade_table(trades)}
        </section>
        <section class="preview-block">
          <h3>纪律事件</h3>
          {render_event_table(events)}
        </section>
        <section class="preview-block">
          <h3>盘后复盘</h3>
          {review_view}
        </section>
        <section class="preview-block">
          <h3>归档验证</h3>
          {validation_view}
        </section>
      </div>
    """


def render_markdown_readable_view(content: str) -> str:
    if not clean_text(content):
        return '<p class="muted">暂无归档草稿。</p>'

    def close_blocks() -> None:
        nonlocal in_list, table_rows
        if in_list:
            parts.append("</ul>")
            in_list = False
        if table_rows:
            header = table_rows[0]
            body = table_rows[1:]
            parts.append('<div class="table-wrap"><table><thead><tr>')
            parts.extend(f"<th>{esc_html(cell)}</th>" for cell in header)
            parts.append("</tr></thead><tbody>")
            for row in body:
                parts.append("<tr>")
                parts.extend(f"<td>{esc_html(cell)}</td>" for cell in row)
                parts.append("</tr>")
            parts.append("</tbody></table></div>")
            table_rows = []

    def table_cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    def is_table_separator(line: str) -> bool:
        cells = table_cells(line)
        return bool(cells) and all(cell.replace(":", "").replace("-", "").strip() == "" for cell in cells)

    parts: list[str] = ['<div class="markdown-preview">']
    in_list = False
    table_rows: list[list[str]] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            close_blocks()
            continue
        if line.startswith("### "):
            close_blocks()
            parts.append(f"<h4>{esc_html(line[4:])}</h4>")
        elif line.startswith("## "):
            close_blocks()
            parts.append(f"<h3>{esc_html(line[3:])}</h3>")
        elif line.startswith("# "):
            close_blocks()
            parts.append(f"<h3>{esc_html(line[2:])}</h3>")
        elif line.startswith("- "):
            if table_rows:
                close_blocks()
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{esc_html(line[2:])}</li>")
        elif line.startswith("|") and line.endswith("|"):
            if in_list:
                close_blocks()
            if not is_table_separator(line):
                table_rows.append(table_cells(line))
        else:
            close_blocks()
            parts.append(f"<p>{esc_html(line)}</p>")
    close_blocks()
    parts.append("</div>")
    return "".join(parts)


def raw_markdown_details(title: str, content: str) -> str:
    if not clean_text(content):
        return ""
    return f"""
      <details class="raw-markdown">
        <summary>{esc_html(title)}</summary>
        <pre>{esc_html(content)}</pre>
      </details>
    """


def is_legacy_english_closeout(content: str) -> bool:
    text = clean_text(content)
    if not text:
        return False
    first_lines = "\n".join(text.splitlines()[:10])
    return "Closeout Draft" in first_lines and "归档草稿" not in first_lines


def closeout_status_label(*, exists: bool, legacy: bool, stale: bool) -> str:
    if not exists:
        return "否"
    if legacy and stale:
        return "旧版英文 / 需更新"
    if legacy:
        return "旧版英文"
    if stale:
        return "需更新"
    return "是"


def build_todo_items(
    *,
    record_path: Path | None,
    record_editable: bool,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
) -> list[tuple[str, str]]:
    if not record_path:
        return [("创建或载入当天记录。", "#today-section")]
    if not record_editable:
        return [("当前载入的是历史交易日；只查看，不再回改旧记录。", "")]

    items: list[tuple[str, str]] = []
    workbench_missing = missing_workbench_labels(workbench)
    if workbench_missing:
        items.append((f"补齐每日作战台（缺 {len(workbench_missing)} 项）。", "#workbench-section"))
    playbook_missing = missing_playbook_labels(playbook, workbench.get("trading_mode"))
    if playbook_missing:
        items.append((f"补齐{playbook_title_for_mode(workbench.get('trading_mode'))}（缺 {len(playbook_missing)} 项）。", "#workbench-section"))
    decision_gate = hsi_decision_gate(workbench, playbook, events)
    if decision_gate["status"] != "ready":
        items.append((f"开盘决策门：{decision_gate['label']}。", "#command-center"))
    risk_state = risk_controller(workbench, trades, events)
    if risk_state["status"] != "normal":
        items.append((f"风险控制器：{risk_state['label']}。", "#command-center"))

    review_missing = missing_review_labels(review)
    if review_missing:
        items.append((f"补齐盘后复盘（缺 {len(review_missing)} 项）。", "#review-section"))

    validation_missing = missing_validation_labels(validation)
    if validation_missing:
        items.append((f"补齐归档验证（缺 {len(validation_missing)} 项）。", "#validation-section"))

    if not closeout_exists:
        items.append(("生成归档草稿。", "#closeout-section"))
    elif closeout_legacy:
        items.append(("重新生成中文归档草稿。", "#closeout-section"))
    elif closeout_stale:
        items.append(("重新生成最新归档草稿。", "#closeout-section"))

    return items or [("当日闭环已完成。", "")]


def build_workflow_steps(
    *,
    record_path: Path | None,
    workbench: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
) -> list[tuple[str, str, str, bool]]:
    intraday_done = bool(trades or events) or validation.get("intraday_record_complete") is True
    closeout_done = closeout_exists and not closeout_legacy and not closeout_stale
    return [
        ("交易日", "已载入记录" if record_path else "先创建或载入", "#today-section", record_path is not None),
        ("作战台", "盘前已就绪" if is_workbench_ready(workbench) else "盘前待补齐", "#workbench-section", is_workbench_ready(workbench)),
        ("盘中", "已有盘中事实" if intraday_done else "等待交易/纪律记录", "#trade-section", intraday_done),
        ("复盘", "复盘已完整" if is_review_done(review) else "复盘待补齐", "#review-section", is_review_done(review)),
        (
            "验证",
            "验证已完整" if is_validation_done(validation) else "验证待补齐",
            "#validation-section",
            is_validation_done(validation),
        ),
        (
            "归档",
            "草稿已同步" if closeout_done else closeout_status_label(exists=closeout_exists, legacy=closeout_legacy, stale=closeout_stale),
            "#closeout-section",
            closeout_done,
        ),
    ]


def render_workflow_steps(steps: list[tuple[str, str, str, bool]]) -> str:
    rows = []
    for label, note, target, done in steps:
        status = " done" if done else ""
        rows.append(
            f'<a class="workflow-step{status}" href="{esc_html(target)}">'
            f"<strong>{esc_html(label)}</strong>"
            f"<span>{esc_html(note)}</span>"
            "</a>"
        )
    return '<div class="workflow-steps">' + "".join(rows) + "</div>"


def build_record_health_items(
    *,
    record_path: Path | None,
    record_editable: bool,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
) -> list[tuple[str, str, str]]:
    if not record_path:
        return [("warn", "还没有载入交易日记录。", "#today-section")]
    if not record_editable:
        return [("ok", "这是历史交易日记录；只查看，不再回改旧记录。", "")]

    items: list[tuple[str, str, str]] = []
    workbench_missing = missing_workbench_labels(workbench)
    if workbench_missing:
        items.append(("warn", f"每日作战台还缺 {len(workbench_missing)} 项。", "#workbench-section"))
    playbook_missing = missing_playbook_labels(playbook, workbench.get("trading_mode"))
    if playbook_missing:
        items.append(("warn", f"{playbook_title_for_mode(workbench.get('trading_mode'))}还缺 {len(playbook_missing)} 项。", "#workbench-section"))
    decision_gate = hsi_decision_gate(workbench, playbook, events)
    if decision_gate["status"] == "blocked":
        items.append(("warn", f"开盘决策门为{decision_gate['label']}，不能继续开新仓。", "#command-center"))
    elif decision_gate["status"] == "observe_only":
        items.append(("warn", f"开盘决策门为{decision_gate['label']}，新交易必须重新确认。", "#command-center"))
    risk_state = risk_controller(workbench, trades, events)
    if risk_state["status"] == "stop":
        items.append(("warn", f"风险控制器为{risk_state['label']}，不能继续开新仓。", "#command-center"))
    elif risk_state["status"] in {"cooldown", "protect_profit"}:
        items.append(("warn", f"风险控制器为{risk_state['label']}，下一笔前必须复核。", "#command-center"))

    if not trades and not events and validation.get("intraday_record_complete") is not True:
        items.append(("warn", "还没有盘中交易或纪律事实；如果当日确实无交易，盘后验证里勾选盘中记录完成。", "#validation-section"))
    if validation.get("no_trade_day") is True and (trades or events):
        items.append(("warn", "验证里标记了无交易日，但当前已经有交易或纪律事实。", "#validation-section"))
    if validation.get("no_trade_day") is True and clean_text(validation.get("no_trade_note")) == "":
        items.append(("warn", "无交易日已勾选，但还没有填写空仓说明。", "#validation-section"))

    review_trade_count = clean_text(review.get("trade_count"))
    if review_trade_count and review_trade_count != str(len(trades)):
        items.append(("warn", f"复盘交易数是 {review_trade_count}，当前真实交易记录是 {len(trades)}。", "#review-section"))

    review_pnl = number_value(review.get("pnl"))
    trade_pnl_values = [number_value(trade.get("pnl_amount")) for trade in trades]
    trade_pnl_values = [value for value in trade_pnl_values if value is not None]
    trade_pnl_total = sum(trade_pnl_values) if trade_pnl_values else None
    if trade_pnl_total is not None and review_pnl is not None and not numeric_almost_equal(review_pnl, trade_pnl_total):
        items.append(
            (
                "warn",
                f"复盘当日盈亏是 {format_number(review_pnl)}，当前交易汇总盈亏是 {format_number(trade_pnl_total)}。",
                "#review-section",
            )
        )

    if (trades or events) and validation.get("intraday_record_complete") is not True:
        items.append(("warn", "已经有盘中事实，但验证区还没确认盘中记录完成。", "#validation-section"))

    review_missing = missing_review_labels(review)
    if review_missing:
        items.append(("warn", f"复盘还缺 {len(review_missing)} 项。", "#review-section"))

    validation_missing = missing_validation_labels(validation)
    if validation_missing:
        items.append(("warn", f"验证还缺 {len(validation_missing)} 项。", "#validation-section"))

    if not closeout_exists:
        items.append(("warn", "还没有归档草稿。", "#closeout-section"))
    elif closeout_legacy:
        items.append(("warn", "当前归档草稿是旧版英文格式。", "#closeout-section"))
    elif closeout_stale:
        items.append(("warn", "记录比归档草稿更新，需要重新生成归档。", "#closeout-section"))

    return items or [("ok", "记录、复盘、验证、归档都已对齐。", "")]


def render_record_health(items: list[tuple[str, str, str]]) -> str:
    rows = []
    for level, text, target in items:
        body = esc_html(text)
        if target:
            body = f'<a href="{esc_html(target)}">{body}</a>'
        rows.append(f'<li class="{esc_html(level)}">{body}</li>')
    return '<ul class="health-list">' + "".join(rows) + "</ul>"


def render_todo_items(items: list[tuple[str, str]]) -> str:
    rows = []
    for text, target in items:
        if target:
            rows.append(f'<li><a href="{esc_html(target)}">{esc_html(text)}</a></li>')
        else:
            rows.append(f"<li>{esc_html(text)}</li>")
    return '<ul class="todo-list">' + "".join(rows) + "</ul>"


def render_recent_record_list(
    paths: list[Path],
    current_path: str,
    active_path: Path | None,
    *,
    compact: bool = False,
) -> str:
    if not paths:
        return '<ul class="recent-records"><li>暂无</li></ul>'

    rows = []
    for path in paths:
        rel_path = relative_path(path)
        is_active = bool(active_path and path.resolve() == active_path.resolve())
        is_current = rel_path == current_path
        try:
            item = load_record(path)
            base = item["base"]
            closeout_exists, closeout_legacy, closeout_stale = closeout_status_for_record(path, base)
            label = display_value(base.get("trade_date"))
            if compact:
                meta = (
                    f"交易 {len(item['trades'])} · "
                    f"复盘 {bool_label(is_review_done(item['review']))} · "
                    f"归档 {closeout_status_label(exists=closeout_exists, legacy=closeout_legacy, stale=closeout_stale)}"
                )
            else:
                meta = (
                    f"交易 {len(item['trades'])} · 纪律 {len(item['events'])} · "
                    f"复盘 {bool_label(is_review_done(item['review']))} · "
                    f"验证 {bool_label(is_validation_done(item['validation']))} · "
                    f"归档 {closeout_status_label(exists=closeout_exists, legacy=closeout_legacy, stale=closeout_stale)}"
                )
        except Exception:
            label = path.name
            meta = "记录读取失败"
        current = " current" if is_current else ""
        disabled = " disabled" if is_current else ""
        if is_active:
            status_label = "当前可编辑"
        elif is_current:
            status_label = "当前查看"
        else:
            status_label = "历史只读"
        button_label = "当前" if is_current else "载入"
        rows.append(
            f'<li class="recent-record{current}">'
            '<div class="recent-record-main">'
            f"<strong>{esc_html(label)}</strong>"
            f"<span>{esc_html(meta)}</span>"
            f'<span class="record-mode">{esc_html(status_label)}</span>'
            f"<code>{esc_html(rel_path)}</code>"
            "</div>"
            '<form method="post" action="/load-record#today-section">'
            f'<input type="hidden" name="record_path" value="{esc_html(rel_path)}">'
            f'<button class="secondary" type="submit"{disabled}>{button_label}</button>'
            "</form>"
            "</li>"
        )
    return '<ul class="recent-records">' + "".join(rows) + "</ul>"


def markdown_title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = clean_text(line)
            if text.startswith("# "):
                return text[2:].strip()
    except Exception:
        return path.name
    return path.name


def render_recent_artifact_list(paths: list[Path], current_path: str, action: str, *, compact: bool = False) -> str:
    if not paths:
        return '<ul class="recent-artifacts"><li>暂无</li></ul>'

    rows = []
    for path in paths:
        rel_path = relative_path(path)
        current = " current" if rel_path == current_path else ""
        disabled = " disabled" if rel_path == current_path else ""
        button_label = "当前" if rel_path == current_path else "查看"
        title = markdown_title(path)
        if compact and len(title) > 30:
            title = title[:30].rstrip() + "..."
        rows.append(
            f'<li class="recent-artifact{current}">'
            '<div class="recent-artifact-main">'
            f"<strong>{esc_html(title)}</strong>"
            f"<code>{esc_html(rel_path)}</code>"
            "</div>"
            f'<form method="post" action="{esc_html(action)}">'
            f'<input type="hidden" name="path" value="{esc_html(rel_path)}">'
            f'<button class="secondary" type="submit"{disabled}>{button_label}</button>'
            "</form>"
            "</li>"
        )
    return '<ul class="recent-artifacts">' + "".join(rows) + "</ul>"


def page_layout(
    *,
    state: AppState,
    flash: str = "",
    error: str = "",
    preview_override: str = "",
    review_form_override: dict[str, list[str]] | None = None,
    validation_form_override: dict[str, list[str]] | None = None,
) -> str:
    ensure_sqlite_ready()
    record_path = current_record_path(state)
    record: dict[str, Any] | None = None
    record_preview = ""
    closeout_preview = ""
    summary_preview = ""
    audit_preview = ""
    closeout_exists = False
    closeout_stale = False
    summary_exists = False
    audit_exists = False
    if record_path:
        record = load_record_db_first(record_path)
        record_preview = record_path.read_text(encoding="utf-8")
        closeout_path = expected_closeout_path(record_path)
        closeout_exists = closeout_path.exists()
        if closeout_exists:
            state.current_closeout_path = relative_path(closeout_path)
            closeout_preview = closeout_path.read_text(encoding="utf-8")
            closeout_stale = record_path.stat().st_mtime > closeout_path.stat().st_mtime
        else:
            state.current_closeout_path = ""
    else:
        closeout_path = current_closeout_path(state)
        if closeout_path:
            closeout_exists = True
            closeout_preview = closeout_path.read_text(encoding="utf-8")
            state.current_closeout_path = relative_path(closeout_path)
        else:
            state.current_closeout_path = ""
    summary_path = current_summary_path(state) or expected_trial_summary_path()
    if summary_path.exists():
        summary_exists = True
        state.current_summary_path = relative_path(summary_path)
        summary_preview = summary_path.read_text(encoding="utf-8")
    audit_path = current_audit_path(state) or expected_field_audit_path()
    if audit_path.exists():
        audit_exists = True
        state.current_audit_path = relative_path(audit_path)
        audit_preview = audit_path.read_text(encoding="utf-8")
    if preview_override:
        closeout_preview = preview_override
    closeout_legacy = is_legacy_english_closeout(closeout_preview)

    all_record_paths = find_files(RECORDS_DIR, "*.md")
    active_path = active_record_path(all_record_paths)
    record_is_current = is_active_record_path(record_path, all_record_paths)
    record_editable = record_path is not None and record_is_current
    recent_records = find_recent_files(RECORDS_DIR, "*.md")
    historical_records = [
        path for path in recent_records if not active_path or path.resolve() != active_path.resolve()
    ]
    recent_closeouts = find_recent_files(CLOSEOUTS_DIR, "*.md")
    recent_summaries = find_recent_files(SUMMARIES_DIR, "*summary*.md")
    recent_audits = find_recent_files(SUMMARIES_DIR, "*audit*.md")
    start_day_value, start_trade_date_value = suggested_start_day_values(state, all_record_paths)
    trades = record["trades"] if record else []
    events = record["events"] if record else []
    review = record["review"] if record else {}
    validation = record["validation"] if record else {}
    workbench = record["workbench"] if record else canonical_workbench({})
    playbook = record["playbook"] if record else canonical_playbook({})
    review_defaults = build_review_defaults(review, trades)
    workbench_done, workbench_total, workbench_missing = workbench_completion(workbench)
    playbook_done, playbook_total, playbook_missing = playbook_completion(playbook, workbench.get("trading_mode"))
    review_done_count, review_total, review_missing = review_completion(review)
    validation_done_count, validation_total, validation_missing = validation_completion(validation)
    day_summary = build_day_summary(workbench, trades)
    day_summary_html = render_day_summary_metrics(day_summary)
    trade_ids = [clean_text(trade.get("trade_id")) for trade in trades if clean_text(trade.get("trade_id"))]
    decision_gate = hsi_decision_gate(workbench, playbook, events)
    risk_state = risk_controller(workbench, trades, events)
    acceptance_gate = phase2_one_day_acceptance_gate(
        record_path=record_path,
        record_editable=record_is_current,
        workbench=workbench,
        playbook=playbook,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        closeout_exists=closeout_exists,
        closeout_legacy=closeout_legacy,
        closeout_stale=closeout_stale,
    )
    next_action = next_action_engine(
        record_path=record_path,
        record_editable=record_is_current,
        workbench=workbench,
        playbook=playbook,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        closeout_exists=closeout_exists,
        closeout_legacy=closeout_legacy,
        closeout_stale=closeout_stale,
        decision_gate=decision_gate,
        risk_state=risk_state,
        acceptance_gate=acceptance_gate,
    )
    trade_execution_lock = execution_lock(decision_gate, risk_state)
    execution_lock_html = render_execution_lock_banner(trade_execution_lock)
    previous_context = previous_record_context(record_path, all_record_paths)
    record_input_for_forms = esc_html(state.current_record_path)
    page_disabled_for_forms = "" if record_path and record_editable else " disabled"
    command_center_html = render_phase2_command_center(
        decision_gate=decision_gate,
        risk_state=risk_state,
        acceptance_gate=acceptance_gate,
        next_action=next_action,
        previous_context=previous_context,
        record_input=record_input_for_forms,
        page_disabled=page_disabled_for_forms,
        workbench=workbench,
        playbook=playbook,
        trades=trades,
        events=events,
        review=review,
        validation=validation,
    )
    review_hub_window = normalize_review_hub_window(state.review_hub_window)
    review_hub_sample_filter = normalize_review_hub_sample_filter(state.review_hub_sample_filter)
    all_review_hub_snapshots = [
        enrich_review_hub_snapshot_from_sqlite(snapshot, current_record_path=record_path)
        for snapshot in dal.get_review_hub_day_rows(
            limit_days=review_hub_window_limit(review_hub_window),
            filter_trusted=False,
        )
    ]
    review_hub_snapshots = [
        enrich_review_hub_snapshot_from_sqlite(snapshot, current_record_path=record_path)
        for snapshot in dal.get_review_hub_day_rows(
            limit_days=review_hub_window_limit(review_hub_window),
            filter_trusted=review_hub_sample_filter == "trusted",
        )
    ]
    review_hub_summary = build_review_hub_summary_from_sqlite(
        dal.get_review_hub_stats(
            limit_days=review_hub_window_limit(review_hub_window),
            filter_trusted=review_hub_sample_filter == "trusted",
        ),
        review_hub_snapshots,
    )
    review_hub_metrics_html = render_review_hub_metrics(review_hub_summary)
    review_hub_day_table_html = render_review_hub_day_table(review_hub_snapshots)
    review_hub_sample_quality_html = render_review_hub_sample_quality(
        all_review_hub_snapshots,
        review_hub_snapshots,
        review_hub_sample_filter,
    )
    review_hub_flags_html = render_inline_stats(
        [
            ("冲动交易日", str(review_hub_summary["impulsive_days"])),
            ("止损失守日", str(review_hub_summary["stop_loss_days"])),
            ("过度交易日", str(review_hub_summary["overtrade_days"])),
        ],
        quiet=True,
    )
    review_hub_issue_notes = render_simple_notes(
        "最近主要问题",
        review_hub_summary["recent_issues"],
        empty_text="最近几天还没有明确填写“当日主要问题”。",
    )
    review_hub_fix_notes = render_simple_notes(
        "最近明日只改",
        review_hub_summary["recent_fixes"],
        empty_text="最近几天还没有明确填写“明天只改 1 件事”。",
    )
    review_hub_no_trade_notes = render_simple_notes(
        "最近空仓说明",
        review_hub_summary["recent_no_trade_notes"],
        empty_text="最近几天还没有专门记录空仓说明。",
    )
    review_hub_setups_html = render_top_setup_tags(review_hub_summary["top_setups"])
    review_hub_active_plan_html = render_top_setup_tags(
        review_hub_summary["top_active_plans"], empty_text="最近几天还没有可统计的主计划。"
    )
    review_hub_active_setup_html = render_top_setup_tags(
        review_hub_summary["top_active_setups"], empty_text="最近几天还没有可统计的主练形态。"
    )
    opening_30_status_html = render_opening_30_status(playbook)
    us_options_status_html = render_us_options_status(playbook)
    active_playbook_title = playbook_title_for_mode(workbench.get("trading_mode"))
    active_trading_mode = normalize_trading_mode(workbench.get("trading_mode"))
    active_filter_label = filter_label_for_mode(active_trading_mode)
    trade_instrument_default = "stock_option" if active_trading_mode == "us_stock_options" else "bull_bear_certificate"
    trade_underlying_default = "TSLA" if active_trading_mode == "us_stock_options" else "HSI"
    trade_side_label = "Call / Put" if active_trading_mode == "us_stock_options" else "牛/熊证"
    trade_side_options = side_options_for_mode(active_trading_mode)
    trade_instrument_type_options = instrument_type_options_for_mode(active_trading_mode)
    trade_underlying_options = underlying_options_for_mode(active_trading_mode)
    def esc(value: Any) -> str:
        return html.escape(str(value or ""))

    def input_value(data: dict[str, Any], key: str) -> str:
        return esc(clean_text(data.get(key)))

    def form_has_value(form: dict[str, list[str]] | None, key: str) -> bool:
        return bool(form and key in form)

    def review_form_value(key: str, fallback: str = "") -> str:
        if review_form_override and key in review_form_override:
            return esc(form_value(review_form_override, key, fallback))
        if key == "pnl":
            return esc(review_defaults["pnl"])
        if key == "trade_count":
            return esc(review_defaults["trade_count"])
        return input_value(review, key)

    def validation_form_value(key: str, fallback: str = "") -> str:
        if validation_form_override and key in validation_form_override:
            return esc(form_value(validation_form_override, key, fallback))
        return input_value(validation, key)

    def validation_checked(key: str) -> bool:
        if validation_form_override and key in validation_form_override:
            return form_bool(validation_form_override, key)
        return validation.get(key) is True

    linked_trade_options = ['<option value="">不关联交易</option>'] + [
        f'<option value="{esc(trade_id)}">{esc(trade_id)}</option>' for trade_id in trade_ids
    ]
    record_input = esc(state.current_record_path)
    page_disabled = "" if record_path and record_editable else " disabled"
    if record_path and not record_is_current:
        record_mode_text = "历史只读"
        record_mode_notice = '<p class="warn-inline">当前载入的是历史交易日记录。历史数据只查看，不再回改旧文件。</p>'
    else:
        record_mode_text = "当前可编辑" if record_editable else "未载入"
        record_mode_notice = ""
    if active_trading_mode == "us_stock_options":
        active_playbook_form_html = f"""
        <div class="form-section">
          <h3>美股期权专项卡</h3>
          <p class="section-note">Phase 3 主干入口：先固定股票池、时段计划、入场信号、合约过滤、单笔风险和事件风险，不把港股牛熊证模板硬套到晚间期权。</p>
          {us_options_status_html}
          <p class="section-note">快速套用会保存当前表单，并用预设补齐美股期权主干字段。</p>
          {render_us_option_quick_presets(page_disabled)}
          <div class="field-grid">
            <div><label>期权时段计划</label><select name="option_session_plan"{page_disabled}>{selected_options(US_OPTION_SESSION_PLAN_OPTIONS, clean_text(playbook.get("option_session_plan")), empty_label="选择")}</select></div>
            <div><label>期权主练形态</label><select name="option_focus_setup"{page_disabled}>{selected_options(US_OPTION_FOCUS_SETUP_OPTIONS, clean_text(playbook.get("option_focus_setup")), empty_label="选择")}</select></div>
          </div>
          <label>主看股票池</label><textarea name="focus_tickers"{page_disabled}>{input_value(playbook, "focus_tickers")}</textarea>
          <label>期权入场信号</label><textarea name="option_entry_signal"{page_disabled}>{input_value(playbook, "option_entry_signal")}</textarea>
          <label>期权合约过滤</label><textarea name="option_contract_filter"{page_disabled}>{input_value(playbook, "option_contract_filter")}</textarea>
          <label>期权风控计划</label><textarea name="option_risk_plan"{page_disabled}>{input_value(playbook, "option_risk_plan")}</textarea>
          <label>事件风险预案</label><textarea name="option_event_risk_plan"{page_disabled}>{input_value(playbook, "option_event_risk_plan")}</textarea>
        </div>
        """
    else:
        active_playbook_form_html = f"""
        <div class="form-section">
          <h3>恒指专项卡</h3>
          <p class="section-note">把开盘前 30 分钟打法、主练形态、牛熊证过滤和异常场景预案先写死，盘中就少靠感觉临场发挥。</p>
          {opening_30_status_html}
          <p class="section-note">快速套用会保存当前表单，并用预设补齐开盘计划、主练形态和空白专项文本。</p>
          {render_playbook_quick_presets(page_disabled)}
          <div class="field-grid">
            <div><label>开盘计划</label><select name="opening_plan"{page_disabled}>{selected_options(OPENING_PLAN_OPTIONS, clean_text(playbook.get("opening_plan")), empty_label="选择")}</select></div>
            <div><label>主练形态</label><select name="focus_setup"{page_disabled}>{selected_options(PLAYBOOK_FOCUS_SETUP_OPTIONS, clean_text(playbook.get("focus_setup")), empty_label="选择")}</select></div>
          </div>
          <label>开盘 30 分钟关键信号</label><textarea name="open_30_key_signal"{page_disabled}>{input_value(playbook, "open_30_key_signal")}</textarea>
          <label>牛熊证过滤提醒</label><textarea name="certificate_filter_note"{page_disabled}>{input_value(playbook, "certificate_filter_note")}</textarea>
          <label>异常场景预案</label><textarea name="abnormal_plan"{page_disabled}>{input_value(playbook, "abnormal_plan")}</textarea>
        </div>
        """
    review_optional_open = any(
        form_has_value(review_form_override, key) or has_value(review.get(key))
        for key in ["win_rate", "max_loss_trade", "market_issue", "setup_issue"]
    )
    validation_flags_open = any(
        validation_checked(key)
        for key in ["impulsive_trade_detected", "no_stop_loss_trade_detected", "emotional_overtrade_detected"]
    )
    no_trade_candidate = not trades and not events
    main_issue_required = "" if validation_checked("no_trade_day") else " required"
    record_readable = (
        render_record_readable_view(record, record_path)
        if record and record_path
        else '<p class="muted">暂无记录文件。先创建或载入交易日记录。</p>'
    )
    closeout_readable = render_markdown_readable_view(closeout_preview)
    summary_readable = render_markdown_readable_view(summary_preview).replace("暂无归档草稿。", "暂无阶段总结。")
    audit_readable = render_markdown_readable_view(audit_preview).replace("暂无归档草稿。", "暂无字段体检。")
    record_raw_details = raw_markdown_details("查看原始 Record Markdown", record_preview)
    closeout_raw_details = raw_markdown_details("查看原始归档 Markdown", closeout_preview)
    summary_raw_details = raw_markdown_details("查看原始阶段总结 Markdown", summary_preview)
    audit_raw_details = raw_markdown_details("查看原始字段体检 Markdown", audit_preview)
    closeout_legacy_notice = (
        '<p class="warn-inline">当前归档草稿是旧版英文格式。勾选「重新生成并覆盖草稿」后，会用现有记录生成中文归档草稿。</p>'
        if closeout_legacy
        else ""
    )
    closeout_stale_notice = (
        '<p class="warn-inline">记录文件比归档草稿更新。当前预览可能不是最新结论，建议勾选「重新生成并覆盖草稿」。</p>'
        if closeout_exists and closeout_stale
        else ""
    )
    closeout_empty_hint = ""
    if not closeout_preview:
        blockers = []
        if workbench_missing:
            blockers.append(f"作战台 {len(workbench_missing)} 项")
        if playbook_total and playbook_missing:
            blockers.append(f"专项卡 {len(playbook_missing)} 项")
        if review_missing:
            blockers.append(f"复盘 {len(review_missing)} 项")
        if validation_missing:
            blockers.append(f"验证 {len(validation_missing)} 项")
        if blockers:
            closeout_empty_hint = (
                '<p class="muted">当前还没生成归档。先补齐：' + esc_html(" / ".join(blockers)) + "。</p>"
            )
        else:
            closeout_empty_hint = '<p class="muted">当前可以直接生成归档草稿。</p>'
    todo_html = render_todo_items(
        build_todo_items(
            record_path=record_path,
            record_editable=record_is_current,
            workbench=workbench,
            playbook=playbook,
            trades=trades,
            events=events,
            review=review,
            validation=validation,
            closeout_exists=closeout_exists,
            closeout_legacy=closeout_legacy,
            closeout_stale=closeout_stale,
        )
    )
    workflow_html = render_workflow_steps(
        build_workflow_steps(
            record_path=record_path,
            workbench=workbench,
            trades=trades,
            events=events,
            review=review,
            validation=validation,
            closeout_exists=closeout_exists,
            closeout_legacy=closeout_legacy,
            closeout_stale=closeout_stale,
        )
    )
    title_date = format_trade_date(state.trade_date or start_trade_date_value)
    title_day = "当日交易日"
    next_day_button_label = "新建交易日"
    next_day_hint = f"建议日期 {start_trade_date_value}" if clean_text(start_trade_date_value) else ""
    review_hub_window_controls = "".join(
        (
            f'<form class="filter-form" method="post" action="/set-review-hub-window#review-hub">'
            f'<input type="hidden" name="review_hub_window" value="{option}">'
            f'<button class="filter-pill{" active" if review_hub_window == option else ""}" type="submit">{esc(review_hub_window_label(option))}</button>'
            "</form>"
        )
        for option in REVIEW_HUB_WINDOW_OPTIONS
    )
    review_hub_sample_filter_controls = "".join(
        (
            f'<form class="filter-form" method="post" action="/set-review-hub-sample-filter#review-hub">'
            f'<input type="hidden" name="review_hub_sample_filter" value="{option}">'
            f'<button class="filter-pill{" active" if review_hub_sample_filter == option else ""}" type="submit">{esc(review_hub_sample_filter_label(option))}</button>'
            "</form>"
        )
        for option in REVIEW_HUB_SAMPLE_FILTER_OPTIONS
    )
    closeout_meta_html = render_inline_stats(
        [
            ("记录状态", record_mode_text),
            ("复盘完成", bool_label(is_review_done(review))),
            ("验证完成", bool_label(is_validation_done(validation))),
            ("归档状态", closeout_status_label(exists=closeout_exists, legacy=closeout_legacy, stale=closeout_stale)),
        ],
        quiet=True,
    )
    phase_meta_html = render_inline_stats(
        [
            ("阶段总结", bool_label(summary_exists)),
            ("字段体检", bool_label(audit_exists)),
        ],
        quiet=True,
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TrendGo 本地工作台 {APP_VERSION}</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f2f4f7; color: #1f2937; line-height: 1.5; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 1.9rem; margin: 0; line-height: 1.15; }}
    h2 {{ font-size: 1.2rem; margin: 0 0 12px; font-weight: 700; }}
    h3 {{ font-size: 1rem; margin: 0 0 10px; }}
    .page-stack {{ display: grid; gap: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; align-items: start; }}
    .wide {{ grid-column: 1 / -1; }}
    .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 18px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04); }}
    .card:target {{ outline: 2px solid #9ca3af; outline-offset: 2px; }}
    .hero-card {{ padding: 22px; background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); }}
    .hero-top {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 14px; }}
    .eyebrow {{ margin: 0 0 8px; font-size: 0.82rem; color: #64748b; font-weight: 700; }}
    .hero-note {{ margin: 10px 0 0; max-width: 760px; color: #475569; font-size: 0.94rem; }}
    .hero-meta {{ min-width: 220px; display: flex; flex-direction: column; align-items: flex-end; gap: 8px; text-align: right; }}
    .meta-label {{ font-size: 0.8rem; color: #64748b; font-weight: 600; }}
    .hero-date {{ font-size: 1.16rem; font-weight: 700; color: #0f172a; }}
    .hero-pills {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .pill {{ display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px; border: 1px solid #dbe3ec; background: #eef2f7; color: #334155; font-size: 0.82rem; font-weight: 600; white-space: nowrap; }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 16px; }}
    .action-form {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 0; }}
    .action-form button {{ margin-top: 0; }}
    .action-hint {{ color: #64748b; font-size: 0.84rem; }}
    .tab-radio {{ display: none; }}
    .tab-bar {{ display: flex; gap: 0; position: sticky; top: 0; z-index: 10; background: #fff; border-bottom: 2px solid #e5e7eb; margin: 0 -24px; padding: 0 24px; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    .tab-bar label {{ display: inline-flex; align-items: center; padding: 14px 18px; font-size: 0.94rem; font-weight: 600; color: #64748b; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: color 0.15s, border-color 0.15s; white-space: nowrap; user-select: none; }}
    .tab-bar label:hover {{ color: #1f2937; }}
    #tab-today:checked ~ .tab-bar label[for="tab-today"],
    #tab-workbench:checked ~ .tab-bar label[for="tab-workbench"],
    #tab-review:checked ~ .tab-bar label[for="tab-review"],
    #tab-hub:checked ~ .tab-bar label[for="tab-hub"] {{ color: #111827; border-bottom-color: #111827; }}
    .tab-panel {{ display: none; }}
    .tab-panels {{ display: grid; gap: 16px; }}
    #tab-today:checked ~ .tab-panels #panel-today {{ display: block; }}
    #tab-workbench:checked ~ .tab-panels #panel-workbench {{ display: block; }}
    #tab-review:checked ~ .tab-panels #panel-review {{ display: block; }}
    #tab-hub:checked ~ .tab-panels #panel-hub {{ display: block; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .filter-form {{ margin: 0; }}
    .filter-pill {{ margin-top: 0; padding: 7px 11px; border-radius: 999px; background: #e2e8f0; color: #1f2937; }}
    .filter-pill.active {{ background: #111827; color: #fff; }}
    .dashboard-grid {{ display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.95fr); gap: 16px; align-items: start; }}
    .dashboard-panel {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; background: rgba(255, 255, 255, 0.92); min-width: 0; }}
    .dashboard-side {{ display: grid; gap: 12px; }}
    .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 10px; }}
    .command-metrics {{ margin-top: 14px; }}
    .decision-gate {{ display: grid; grid-template-columns: minmax(220px, 0.72fr) minmax(0, 1.28fr); gap: 14px; border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; background: #f8fafc; }}
    .decision-gate + .decision-gate {{ margin-top: 12px; }}
    .decision-gate span {{ display: block; color: #64748b; font-size: 0.82rem; font-weight: 700; }}
    .decision-gate strong {{ display: block; margin-top: 2px; font-size: 1.26rem; color: #0f172a; }}
    .decision-gate p {{ margin: 8px 0 0; color: #475569; }}
    .decision-gate-notes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .decision-gate-notes .note-block + .note-block {{ margin-top: 0; }}
    .stage-bar {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px 14px; background: #fff; margin-bottom: 12px; }}
    .stage-bar-top {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
    .stage-bar-top span {{ color: #64748b; font-size: 0.82rem; font-weight: 700; }}
    .stage-bar-top strong {{ font-size: 1rem; }}
    .stage-track {{ height: 8px; border-radius: 999px; background: #e5e7eb; overflow: hidden; margin: 10px 0 8px; }}
    .stage-track span {{ display: block; height: 100%; background: #111827; border-radius: inherit; }}
    .stage-bar p {{ margin: 0; color: #475569; font-size: 0.88rem; }}
    .next-action {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 14px; align-items: center; border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; margin-bottom: 12px; background: #f8fafc; }}
    .next-action span {{ display: block; color: #64748b; font-size: 0.82rem; font-weight: 700; }}
    .next-action strong {{ display: block; margin-top: 2px; font-size: 1.18rem; color: #0f172a; }}
    .next-action p {{ margin: 7px 0 0; color: #475569; }}
    .next-action-ok {{ border-color: #86efac; background: #f0fdf4; }}
    .next-action-warn {{ border-color: #fde68a; background: #fffbeb; }}
    .next-action-danger {{ border-color: #fecdd3; background: #fff1f2; }}
    .next-action-neutral {{ border-color: #dbe3ec; background: #f8fafc; }}
    .next-action-button {{ display: inline-flex; align-items: center; justify-content: center; min-height: 38px; border-radius: 8px; padding: 9px 12px; background: #111827; color: #fff; text-decoration: none; white-space: nowrap; }}
    .next-action-details {{ margin: 8px 0 0; padding-left: 18px; color: #334155; }}
    .execution-lock {{ border: 1px solid #dbe3ec; border-radius: 10px; padding: 11px 12px; margin-bottom: 12px; background: #f8fafc; }}
    .execution-lock strong, .execution-lock span {{ display: block; }}
    .execution-lock span {{ color: #475569; margin-top: 2px; }}
    .execution-lock p {{ margin: 7px 0 0; color: #475569; }}
    .execution-lock-open {{ border-color: #86efac; background: #f0fdf4; }}
    .execution-lock-caution {{ border-color: #fde68a; background: #fffbeb; }}
    .execution-lock-locked {{ border-color: #fecdd3; background: #fff1f2; }}
    .acceptance-gate {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; margin-top: 12px; background: #fff; }}
    .acceptance-pass {{ border-color: #86efac; background: #f0fdf4; }}
    .acceptance-fail {{ border-color: #fde68a; background: #fffbeb; }}
    .acceptance-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .acceptance-head span {{ display: block; color: #64748b; font-size: 0.82rem; font-weight: 700; }}
    .acceptance-head strong {{ display: block; font-size: 1.2rem; margin-top: 2px; }}
    .acceptance-score {{ border-radius: 999px; background: rgba(17, 24, 39, 0.08); padding: 7px 10px; font-weight: 800; white-space: nowrap; }}
    .acceptance-checks {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; list-style: none; padding: 0; margin: 12px 0 0; }}
    .acceptance-checks li {{ border: 1px solid #e5e7eb; border-radius: 8px; background: rgba(255, 255, 255, 0.78); }}
    .acceptance-checks a {{ display: block; color: inherit; text-decoration: none; padding: 9px 10px; }}
    .acceptance-checks strong, .acceptance-checks span {{ display: block; }}
    .acceptance-checks span {{ color: #64748b; font-size: 0.82rem; margin-top: 2px; }}
    .acceptance-checks .check-pass {{ border-color: #bbf7d0; }}
    .acceptance-checks .check-fail {{ border-color: #fde68a; }}
    .acceptance-repair {{ border: 1px dashed #cbd5e1; border-radius: 10px; padding: 12px 14px; margin-top: 12px; background: #f8fafc; }}
    .acceptance-repair h3 {{ margin-bottom: 8px; }}
    .acceptance-repair ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }}
    .acceptance-repair li {{ display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: center; }}
    .acceptance-repair span {{ color: #64748b; font-size: 0.84rem; }}
    .repair-link {{ display: inline-flex; align-items: center; justify-content: center; min-height: 34px; border-radius: 8px; padding: 7px 10px; background: #475569; color: #fff; text-decoration: none; white-space: nowrap; }}
    .review-quality-assistant {{ border: 1px solid #fed7aa; border-radius: 10px; padding: 13px 14px; margin: 12px 0 14px; background: #fff7ed; }}
    .repair-assistant-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 10px; }}
    .repair-assistant-head span {{ color: #9a3412; font-size: 0.8rem; font-weight: 800; }}
    .repair-assistant-head strong {{ color: #111827; font-size: 1rem; }}
    .repair-prompt-list {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 9px; }}
    .repair-prompt-list li {{ display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: start; }}
    .repair-prompt-body {{ display: grid; gap: 4px; min-width: 0; }}
    .repair-prompt-body strong, .repair-prompt-body span, .repair-prompt-body em, .repair-prompt-body code {{ overflow-wrap: anywhere; }}
    .repair-prompt-body span {{ color: #475569; font-size: 0.86rem; }}
    .repair-prompt-body code {{ display: block; border: 1px solid #fed7aa; border-radius: 8px; padding: 7px 8px; background: rgba(255, 255, 255, 0.82); color: #7c2d12; white-space: normal; }}
    .repair-prompt-body em {{ color: #9a3412; font-style: normal; font-size: 0.82rem; }}
    .acceptance-final-form {{ display: grid; gap: 12px; border-top: 1px solid #fed7aa; margin-top: 12px; padding-top: 12px; }}
    .acceptance-final-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .acceptance-final-head strong, .acceptance-final-head span {{ display: block; }}
    .acceptance-final-head span {{ color: #64748b; font-size: 0.85rem; margin-top: 2px; }}
    .acceptance-final-head button {{ margin-top: 0; white-space: nowrap; }}
    .acceptance-review-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }}
    .acceptance-review-field {{ display: grid; gap: 5px; }}
    .acceptance-review-field label {{ margin-top: 0; }}
    .acceptance-review-field textarea {{ min-height: 92px; }}
    .acceptance-review-field span {{ color: #64748b; font-size: 0.8rem; }}
    .gate-ready {{ border-color: #86efac; background: #f0fdf4; }}
    .gate-caution {{ border-color: #fde68a; background: #fffbeb; }}
    .gate-blocked {{ border-color: #fecdd3; background: #fff1f2; }}
    .metric {{ border: 1px solid #e5e7eb; border-radius: 9px; padding: 11px 12px; background: #f8fafc; min-width: 0; }}
    .metric span {{ display: block; color: #6b7280; font-size: 0.82rem; }}
    .metric strong {{ display: block; overflow-wrap: anywhere; margin-top: 2px; }}
    .workflow-steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin: 0; }}
    .workflow-step {{ display: block; min-width: 0; border: 1px solid #e5e7eb; border-radius: 9px; padding: 10px; background: #fff7ed; color: inherit; text-decoration: none; }}
    .workflow-step.done {{ background: #ecfdf3; border-color: #bbf7d0; }}
    .workflow-step strong, .workflow-step span {{ display: block; overflow-wrap: anywhere; }}
    .workflow-step span {{ color: #6b7280; font-size: 0.82rem; margin-top: 2px; }}
    .artifact-paths {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; margin-top: 14px; }}
    .artifact-path {{ border: 1px dashed #cbd5e1; border-radius: 10px; padding: 10px 12px; background: rgba(255, 255, 255, 0.95); min-width: 0; }}
    .artifact-path strong {{ display: block; margin-bottom: 6px; }}
    .inline-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin: 0 0 14px; }}
    .inline-stats.quiet {{ margin-bottom: 0; }}
    .inline-stat {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; background: #fff; min-width: 0; }}
    .inline-stat span {{ display: block; color: #6b7280; font-size: 0.78rem; }}
    .inline-stat strong {{ display: block; margin-top: 2px; overflow-wrap: anywhere; font-size: 0.92rem; }}
    .form-shell {{ display: grid; gap: 14px; }}
    .form-section {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px; background: #fbfcfd; }}
    .form-section h3 {{ margin: 0 0 4px; font-size: 0.95rem; }}
    .section-note {{ margin: 0 0 10px; color: #64748b; font-size: 0.85rem; }}
    .form-actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .form-actions button {{ margin-top: 0; }}
    .quick-preset-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }}
    .preset-button {{ margin-top: 0; padding: 8px 11px; }}
    .preview-block {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb; }}
    .preview-block:first-of-type {{ margin-top: 14px; }}
    .preview-block h3 {{ margin-bottom: 10px; }}
    .low-priority {{ border-style: dashed; background: #fcfcfd; }}
    .low-priority summary {{ color: #475569; }}
    .nested-low-priority {{ margin-top: 12px; }}
    .review-hub-grid {{ display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.9fr); gap: 16px; margin-top: 14px; align-items: start; }}
    .compact-table th, .compact-table td {{ font-size: 0.88rem; }}
    .compact-table td form {{ margin: 0; }}
    .small-button {{ padding: 7px 10px; margin-top: 0; }}
    .note-block + .note-block {{ margin-top: 16px; }}
    .note-list {{ margin: 8px 0 0; padding-left: 18px; }}
    .note-list li {{ margin: 6px 0; color: #334155; }}
    .setup-tag-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .setup-tag {{ display: inline-flex; align-items: center; gap: 8px; border: 1px solid #dbe3ec; border-radius: 999px; padding: 6px 10px; background: #fff; color: #334155; font-size: 0.84rem; }}
    .setup-tag strong {{ font-size: 0.84rem; }}
    .empty-day-box {{ border: 1px solid #dbe3ec; border-radius: 10px; padding: 12px 14px; background: #f8fafc; }}
    .field-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }}
    .kv-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }}
    .kv {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 9px 10px; background: #fafafa; min-width: 0; }}
    .kv span {{ display: block; color: #6b7280; font-size: 0.8rem; }}
    .kv strong {{ display: block; overflow-wrap: anywhere; white-space: pre-wrap; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ color: #4b5563; background: #f9fafb; font-weight: 700; }}
    td span {{ color: #6b7280; font-size: 0.82rem; }}
    label {{ display: block; font-size: 0.9rem; margin: 10px 0 5px; font-weight: 600; }}
    input, select, textarea {{ width: 100%; min-width: 0; border: 1px solid #d1d5db; border-radius: 8px; padding: 9px 10px; font: inherit; background: #fff; color: #111827; }}
    textarea {{ min-height: 82px; resize: vertical; }}
    button {{ border: 0; border-radius: 8px; padding: 10px 14px; margin-top: 12px; background: #111827; color: #fff; font: inherit; cursor: pointer; }}
    button.secondary {{ background: #475569; }}
    button:disabled {{ background: #9ca3af; cursor: not-allowed; }}
    .notice {{ padding: 11px 12px; border-radius: 8px; margin: 0; }}
    .ok {{ background: #ecfdf3; color: #166534; border: 1px solid #bbf7d0; }}
    .err {{ background: #fff1f2; color: #b42318; border: 1px solid #fecdd3; }}
    .warn-inline {{ background: #fffbeb; color: #92400e; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 12px; }}
    .todo-list {{ list-style: none; padding-left: 0; }}
    .todo-list li {{ margin: 6px 0; padding: 8px 10px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; }}
    .todo-list a {{ color: inherit; display: block; text-decoration: none; }}
    .todo-list a:hover {{ color: #111827; text-decoration: underline; }}
    .health-list {{ list-style: none; padding-left: 0; }}
    .health-list li {{ margin: 6px 0; padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }}
    .health-list li.ok {{ background: #ecfdf3; border-color: #bbf7d0; color: #166534; }}
    .health-list li.warn {{ background: #fffbeb; border-color: #fde68a; color: #92400e; }}
    .health-list a {{ color: inherit; display: block; text-decoration: none; }}
    .health-list a:hover {{ text-decoration: underline; }}
    .recent-records, .recent-artifacts {{ list-style: none; padding-left: 0; }}
    .recent-record, .recent-artifact {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 12px; align-items: center; margin: 8px 0; padding: 9px 10px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }}
    .recent-record.current, .recent-artifact.current {{ border-color: #9ca3af; background: #f3f4f6; }}
    .recent-record strong, .recent-record span, .recent-record code, .recent-artifact strong, .recent-artifact code {{ display: block; }}
    .recent-record span {{ color: #6b7280; font-size: 0.84rem; margin: 3px 0; }}
    .recent-record .record-mode {{ color: #374151; font-weight: 700; }}
    .recent-record form, .recent-artifact form {{ margin: 0; }}
    .recent-record button, .recent-artifact button {{ margin-top: 0; padding: 8px 12px; white-space: nowrap; }}
    code {{ background: #eef2ff; padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #111827; color: #e5eefb; padding: 12px; border-radius: 8px; overflow-x: auto; max-height: 520px; }}
    ul {{ padding-left: 18px; margin: 8px 0; }}
    .muted {{ color: #6b7280; font-size: 0.9rem; }}
    .inline-check {{ display: flex; align-items: center; gap: 8px; margin-top: 10px; }}
    .inline-check input {{ width: auto; }}
    .check-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 4px 12px; }}
    .form-details, .stage-tools, .history-details {{ margin-top: 12px; border: 1px solid #e5e7eb; border-radius: 10px; padding: 0 14px 14px; background: #f8fafc; }}
    .form-details summary, .stage-tools summary, .history-details summary {{ cursor: pointer; color: #374151; font-weight: 700; padding: 10px 0; }}
    .readable-preview h3, .markdown-preview h3 {{ margin-top: 18px; }}
    .markdown-preview h4 {{ margin: 12px 0 6px; }}
    .markdown-preview p {{ margin: 8px 0; }}
    .raw-markdown {{ margin-top: 14px; border-top: 1px solid #e5e7eb; padding-top: 10px; }}
    .raw-markdown summary {{ cursor: pointer; color: #374151; font-weight: 700; }}
    @media (max-width: 900px) {{
      main {{ padding: 16px; }}
      .tab-bar {{ margin: 0 -16px; padding: 0 16px; }}
      .tab-bar label {{ padding: 12px 14px; font-size: 0.86rem; }}
      .hero-top {{ flex-direction: column; }}
      .hero-meta {{ align-items: flex-start; text-align: left; min-width: 0; }}
      .hero-pills {{ justify-content: flex-start; }}
      .dashboard-grid {{ grid-template-columns: 1fr; }}
      .decision-gate {{ grid-template-columns: 1fr; }}
      .next-action {{ grid-template-columns: 1fr; }}
      .next-action-button {{ width: 100%; }}
      .acceptance-repair li {{ grid-template-columns: 1fr; }}
      .review-hub-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<main>
  <div class="page-stack">
  {f'<div class="notice ok">{esc(flash)}</div>' if flash else ''}
  {f'<div class="notice err">{esc(error)}</div>' if error else ''}

  <input class="tab-radio" type="radio" name="tab" id="tab-today" checked>
  <input class="tab-radio" type="radio" name="tab" id="tab-workbench">
  <input class="tab-radio" type="radio" name="tab" id="tab-review">
  <input class="tab-radio" type="radio" name="tab" id="tab-hub">
  <div class="tab-bar">
    <label for="tab-today">当日交易日</label>
    <label for="tab-workbench">作战台</label>
    <label for="tab-review">复盘 & 归档</label>
    <label for="tab-hub">复盘中心</label>
  </div>
  <div class="tab-panels">
  <div class="tab-panel" id="panel-today">

  <section class="card hero-card" id="today-section">
    <div class="hero-top">
      <div>
        <p class="eyebrow">TrendGo 本地工作台 {APP_VERSION}</p>
        <h1>当日交易日工作台</h1>
        <p class="hero-note">盘前计划、盘中事实、盘后复盘和归档都集中在这一页完成，历史交易日只保留查看入口。</p>
      </div>
      <div class="hero-meta">
        <span class="meta-label">交易日期</span>
        <time class="hero-date">{esc(title_date)}</time>
        <div class="hero-pills">
          <span class="pill">{esc(title_day)}</span>
          <span class="pill">{esc(record_mode_text)}</span>
          <span class="pill">状态 {esc(display_value(workbench.get("current_state")))}</span>
        </div>
      </div>
    </div>

    <div class="hero-actions">
      <form class="action-form" method="post" action="/start-day#today-section">
        <input type="hidden" name="day" value="{esc(start_day_value)}">
        <input type="hidden" name="trade_date" value="{esc(start_trade_date_value)}">
        <select name="trading_mode" aria-label="新建交易日模式">
          {selected_options(TRADING_MODE_OPTIONS, active_trading_mode)}
        </select>
        <button type="submit">{esc(next_day_button_label)}</button>
        <span class="action-hint">{esc(next_day_hint)}</span>
      </form>
      <form class="action-form" method="post" action="/load-latest-record#today-section">
        <button class="secondary" type="submit"{" disabled" if not active_path else ""}>载入当日交易日</button>
      </form>
    </div>

    {record_mode_notice}

    <div class="dashboard-grid">
      <div class="dashboard-panel">
        <h2>当日交易日概览</h2>
        <div class="status-grid">
          <div class="metric"><span>交易日期</span><strong>{esc(state.trade_date or "未设置")}</strong></div>
          <div class="metric"><span>状态</span><strong>{esc(display_value(workbench.get("current_state")))}</strong></div>
          <div class="metric"><span>交易数</span><strong>{len(trades)}</strong></div>
          <div class="metric"><span>纪律事件</span><strong>{len(events)}</strong></div>
          <div class="metric"><span>复盘</span><strong>{bool_label(is_review_done(review))}</strong></div>
          <div class="metric"><span>验证</span><strong>{bool_label(is_validation_done(validation))}</strong></div>
          <div class="metric"><span>归档</span><strong>{closeout_status_label(exists=closeout_exists, legacy=closeout_legacy, stale=closeout_stale)}</strong></div>
          {day_summary_html}
        </div>
        <h3 style="margin-top:16px;">闭环进度</h3>
        {workflow_html}
        <div class="artifact-paths">
          <div class="artifact-path">
            <strong>记录文件</strong>
            <code>{esc(state.current_record_path or "未生成")}</code>
          </div>
          <div class="artifact-path">
            <strong>归档草稿</strong>
            <code>{esc(state.current_closeout_path or "未生成")}</code>
          </div>
        </div>
      </div>

      <div class="dashboard-side">
        <div class="dashboard-panel">
          <h3>当日交易日待办</h3>
          {todo_html}
        </div>
        <details class="history-details low-priority">
          <summary>历史查看（记录 {len(historical_records)} / 归档 {len(recent_closeouts)}）</summary>
          <p class="muted">历史交易日只保留查看入口；最新交易日继续记录和归档。</p>
          <details class="history-details nested-low-priority">
            <summary>历史记录</summary>
            {render_recent_record_list(historical_records, state.current_record_path, active_path, compact=True)}
          </details>
          <details class="history-details nested-low-priority">
            <summary>历史归档</summary>
            {render_recent_artifact_list(recent_closeouts, state.current_closeout_path, "/load-closeout#closeout-preview", compact=True)}
          </details>
        </details>
      </div>
    </div>
  </section>

  {command_center_html}

  </div><!-- /panel-today -->
  <div class="tab-panel" id="panel-hub">

  <section class="grid">
    <div class="card wide" id="review-hub">
      <h2>复盘中心（{esc(review_hub_window_label(review_hub_window))}）</h2>
      <p class="muted">这里只看最近几天的执行结果和重复问题，不改历史记录源文档，也不引入单独数据库。</p>
      <div class="filter-row" aria-label="复盘中心范围">
        {review_hub_window_controls}
        {review_hub_sample_filter_controls}
      </div>
      {review_hub_sample_quality_html}
      <div class="status-grid">
        {review_hub_metrics_html}
      </div>
      <div class="review-hub-grid">
        <div class="dashboard-panel">
          <h3>最近交易日</h3>
          <p class="section-note">当日和历史日放在同一张复盘表里，便于连续看状态；历史日只查看，不再回改旧记录。</p>
          {review_hub_day_table_html}
        </div>
        <div class="dashboard-panel">
          <h3>重复信号</h3>
          {review_hub_flags_html}
          <h3 style="margin-top:16px;">最近主计划</h3>
          {review_hub_active_plan_html}
          <h3 style="margin-top:16px;">最近主练形态</h3>
          {review_hub_active_setup_html}
          <h3 style="margin-top:16px;">最近常见形态</h3>
          {review_hub_setups_html}
          {review_hub_issue_notes}
          {review_hub_fix_notes}
          {review_hub_no_trade_notes}
        </div>
      </div>
    </div>
  </section>
  </div><!-- /panel-hub -->
  <div class="tab-panel" id="panel-workbench">

  <section class="grid">
    <div class="card wide" id="workbench-section">
      <h2>每日作战台</h2>
      <p class="muted">基础作战台 {esc(completion_text(done=workbench_done, total=workbench_total))}{f'；还缺：{esc("、".join(workbench_missing))}' if workbench_missing else '；盘前关键位与资金目标已就绪。'}{(f' {esc(active_playbook_title)} {esc(completion_text(done=playbook_done, total=playbook_total))}；还缺：{esc("、".join(playbook_missing))}。' if playbook_total and playbook_missing else f' {esc(active_playbook_title)} {esc(completion_text(done=playbook_done, total=playbook_total))}；主干计划已齐。')}</p>
      <form class="form-shell" method="post" action="/save-workbench#workbench-section">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <h3>核心计划</h3>
          <p class="section-note">先写方向、状态和资金目标，这一组决定当天是否具备开工条件。</p>
          <div class="field-grid">
            <div><label>模式</label><select name="trading_mode"{page_disabled}>{selected_options(TRADING_MODE_OPTIONS, clean_text(workbench.get("trading_mode")) or "hsi_bull_bear_certificate")}</select></div>
            <div><label>当日主方向</label><select name="main_direction"{page_disabled}>{selected_options(MAIN_DIRECTION_OPTIONS, clean_text(workbench.get("main_direction")) or "undecided")}</select></div>
            <div><label>当前状态</label><select name="current_state"{page_disabled}>{selected_options(WORKBENCH_STATE_OPTIONS, clean_text(workbench.get("current_state")) or "unset")}</select></div>
            <div><label>当日使用本金</label><input name="capital_used" type="number" step="any" value="{input_value(workbench, "capital_used")}"{page_disabled}></div>
            <div><label>盈利目标%</label><input name="profit_target_pct" type="number" step="any" value="{input_value(workbench, "profit_target_pct")}"{page_disabled}></div>
          </div>
        </div>
        {active_playbook_form_html}
        <details class="form-details low-priority">
          <summary>补充作战字段</summary>
          <label>盘后总结</label><textarea name="post_market_summary"{page_disabled}>{input_value(workbench, "post_market_summary")}</textarea>
        </details>
        <div class="form-actions">
          <button type="submit"{page_disabled}>保存作战台</button>
        </div>
      </form>
    </div>
  </section>

  <section class="grid">
    <div class="card" id="trade-section">
      <h2>盘中记录 / 交易</h2>
      {execution_lock_html}
      <form class="form-shell" method="post" action="/add-trade#record-preview">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <h3>关键事实</h3>
          <p class="section-note">先记时间、方向、形态、四条件、价格、仓位和结果；{esc(display_value(active_trading_mode))}交易先把进场条件讲清楚，再谈盈亏。</p>
          <div class="field-grid">
            <div><label>开仓时间</label><input name="trade_time" placeholder="10:12"{page_disabled}></div>
            <div><label>方向</label><select name="direction"{page_disabled}>{selected_options(DIRECTION_OPTIONS, "", empty_label="选择")}</select></div>
            <div><label>{esc(trade_side_label)}</label><select name="certificate_side" required{page_disabled}>{selected_options(trade_side_options, "", empty_label="选择")}</select></div>
            <div><label>标的</label><input name="instrument_code" required{page_disabled}></div>
            <div><label>形态</label><select name="setup_type"{page_disabled}>{selected_options(SETUP_OPTIONS, "", empty_label="选择")}</select></div>
            <div><label>机会等级</label><select name="abc_grade"{page_disabled}>{selected_options(GRADE_OPTIONS, "", empty_label="选择")}</select></div>
            <div><label>方向明确</label><select name="direction_clear" required{page_disabled}>{boolean_options("", empty_label="选择", true_first=True)}</select></div>
            <div><label>位置合理</label><select name="location_ok" required{page_disabled}>{boolean_options("", empty_label="选择", true_first=True)}</select></div>
            <div><label>确认出现</label><select name="confirmation_ok" required{page_disabled}>{boolean_options("", empty_label="选择", true_first=True)}</select></div>
            <div><label>止损清楚</label><select name="risk_clear" required{page_disabled}>{boolean_options("", empty_label="选择", true_first=True)}</select></div>
            <div><label>{esc(active_filter_label)}通过</label><select name="certificate_filter_passed" required{page_disabled}>{boolean_options("", empty_label="选择", true_first=True)}</select></div>
            <div><label>入场价</label><input name="entry_price" type="number" step="any" required{page_disabled}></div>
            <div><label>止损</label><input name="stop_loss" type="number" step="any" required{page_disabled}></div>
            <div><label>仓位</label><input name="position_size" required{page_disabled}></div>
            <div><label>盈亏金额（可留空自动计算）</label><input name="pnl_amount" type="number" step="any"{page_disabled}></div>
            <div><label>是否按计划</label><select name="followed_plan" required{page_disabled}>{boolean_options("true", true_first=True)}</select></div>
            <div><label>是否违规</label><select name="rule_violation" required{page_disabled}>{boolean_options("false")}</select></div>
            <div><label>结果（可留空自动判断）</label><select name="result"{page_disabled}>{selected_options(RESULT_OPTIONS, "", empty_label="自动判断")}</select></div>
          </div>
          <label class="inline-check"><input type="checkbox" name="auto_rule_event" checked{page_disabled}>异常 / 未过检查时自动写纪律事件</label>
          <label>入场逻辑</label><textarea name="entry_reason" required{page_disabled}></textarea>
        </div>
        <details class="form-details low-priority">
          <summary>补充字段（平仓 / 异常场景 / 情绪 / 备注）</summary>
          <div class="field-grid">
            <div><label>平仓时间</label><input name="exit_time" placeholder="10:25"{page_disabled}></div>
            <div><label>平仓价格</label><input name="exit_price" type="number" step="any"{page_disabled}></div>
            <div><label>目标</label><input name="target_price" type="number" step="any"{page_disabled}></div>
            <div><label>盈亏比</label><input name="risk_reward_ratio" type="number" step="any"{page_disabled}></div>
            <div><label>评分</label><input name="setup_score" type="number" step="any"{page_disabled}></div>
            <div><label>异常场景</label><select name="abnormal_scenario"{page_disabled}>{selected_options(ABNORMAL_SCENARIO_OPTIONS, "none")}</select></div>
            <div><label>开仓前情绪</label><select name="pre_trade_emotion"{page_disabled}>{selected_options(PRE_TRADE_EMOTION_OPTIONS, "", empty_label="未填写")}</select></div>
            <div><label>平仓后情绪</label><select name="post_trade_emotion"{page_disabled}>{selected_options(POST_TRADE_EMOTION_OPTIONS, "unset")}</select></div>
            <div><label>工具类型</label><select name="instrument_type" required{page_disabled}>{selected_options(trade_instrument_type_options, trade_instrument_default)}</select></div>
            <div><label>形态确认</label><select name="setup_validated"{page_disabled}>{boolean_options("", empty_label="未填写", true_label="已确认", false_label="未确认", true_first=True)}</select></div>
            <div><label>情绪</label><select name="emotion_state"{page_disabled}>{selected_options(EMOTION_OPTIONS, "", empty_label="未填写")}</select></div>
          </div>
          <label>平仓原因</label><textarea name="exit_reason"{page_disabled}></textarea>
          <label>交易截图</label><textarea name="screenshot_note" placeholder="先填写截图路径或说明；暂不做图片上传。"{page_disabled}></textarea>
          <label>违规说明</label><textarea name="violation_note"{page_disabled}></textarea>
          <label>复盘备注</label><textarea name="review_note"{page_disabled}></textarea>
        </details>
        <div class="form-actions">
          <button type="submit"{page_disabled}>写入交易记录</button>
        </div>
      </form>
    </div>

    <div class="card" id="event-section">
      <h2>盘中记录 / 纪律事件</h2>
      <form class="form-shell" method="post" action="/add-rule-event-preset#record-preview">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <h3>快捷纪律动作</h3>
          <p class="section-note">盘中出现典型异常时先一键落纪律动作，再按需要补充手工说明。</p>
          {render_rule_event_preset_buttons(page_disabled)}
        </div>
      </form>
      <form class="form-shell" method="post" action="/add-rule-event#record-preview">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <h3>关键事实</h3>
          <p class="section-note">纪律事件先记发生时间、类型、级别，再把触发原因和处理动作写清楚。</p>
          <div class="field-grid">
            <div><label>时间</label><input name="event_time" placeholder="11:07" required{page_disabled}></div>
            <div><label>类型</label><select name="event_type" required{page_disabled}>{selected_options(EVENT_TYPE_OPTIONS, "", empty_label="选择")}</select></div>
            <div><label>严重级别</label><select name="severity" required{page_disabled}>{selected_options(SEVERITY_OPTIONS, "", empty_label="选择")}</select></div>
          </div>
          <label>触发原因</label><textarea name="trigger_reason" required{page_disabled}></textarea>
          <label>采取动作</label><textarea name="action_taken" required{page_disabled}></textarea>
        </div>
        <details class="form-details low-priority">
          <summary>补充字段</summary>
          <div class="field-grid">
            <div><label>关联交易</label><select name="linked_trade_id"{page_disabled}>{"".join(linked_trade_options)}</select></div>
          </div>
          <label>后续说明</label><textarea name="follow_up_note"{page_disabled}></textarea>
        </details>
        <div class="form-actions">
          <button type="submit"{page_disabled}>写入纪律事件</button>
        </div>
      </form>
    </div>
  </section>
  </div><!-- /panel-workbench -->
  <div class="tab-panel" id="panel-review">

  <section class="grid">
    <div class="card" id="review-section">
      <h2>盘后复盘</h2>
      <p class="muted">完成度 {esc(completion_text(done=review_done_count, total=review_total))}{f'；还缺：{esc("、".join(review_missing))}' if review_missing else '；复盘主结论已齐。'}</p>
      {('<div class="empty-day-box"><strong>无交易日提示</strong><p class="section-note">如果当日空仓，复盘区仍然照常填写，但“最好的一笔 / 最好动作”可以写成最好的等待或克制动作，“最差的一笔 / 最差问题”可以写成最想追单或差点破规则的时刻。</p></div>' if no_trade_candidate else '')}
      {render_review_quality_assistant(review, validation, record_input, page_disabled, trades)}
      <form class="form-shell" method="post" action="/save-review#review-section">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <h3>结果回看</h3>
          <p class="section-note">先确认当日的结果面，再写好坏动作和核心问题。</p>
          <div class="field-grid">
            <div><label>当日盈亏</label><input name="pnl" value="{review_form_value("pnl")}" required{page_disabled}></div>
            <div><label>交易数</label><input name="trade_count" type="number" min="0" value="{review_form_value("trade_count")}" required{page_disabled}></div>
          </div>
          <p class="muted">默认已按当前交易记录带出：交易 {esc(review_defaults["trade_count_hint"])} 笔，当日盈亏 {esc(review_defaults["pnl_hint"])}。</p>
          <label for="review-best-trade-note">最好的一笔 / 最好动作</label><textarea id="review-best-trade-note" name="best_trade_note" required{page_disabled}>{review_form_value("best_trade_note")}</textarea>
          <label for="review-worst-trade-note">最差的一笔 / 最差问题</label><textarea id="review-worst-trade-note" name="worst_trade_note" required{page_disabled}>{review_form_value("worst_trade_note")}</textarea>
        </div>
        <div class="form-section">
          <h3>问题归因</h3>
          <p class="section-note">把当日最关键的执行、情绪、风控问题讲清楚，最后收成明天只改的一件事。</p>
          <label for="review-execution-issue">执行问题</label><textarea id="review-execution-issue" name="execution_issue" required{page_disabled}>{review_form_value("execution_issue")}</textarea>
          <label for="review-emotion-issue">情绪问题</label><textarea id="review-emotion-issue" name="emotion_issue" required{page_disabled}>{review_form_value("emotion_issue")}</textarea>
          <label for="review-risk-issue">风控问题</label><textarea id="review-risk-issue" name="risk_issue" required{page_disabled}>{review_form_value("risk_issue")}</textarea>
          <label for="review-next-day-one-fix">明天只改 1 件事</label><textarea id="review-next-day-one-fix" name="next_day_one_fix" required{page_disabled}>{review_form_value("next_day_one_fix")}</textarea>
        </div>
        <details class="form-details low-priority"{open_attr(review_optional_open)}>
          <summary>补充复盘字段</summary>
          <div class="field-grid">
            <div><label>胜率</label><input name="win_rate" value="{review_form_value("win_rate")}"{page_disabled}></div>
          </div>
          <label>最大亏损单</label><textarea name="max_loss_trade"{page_disabled}>{review_form_value("max_loss_trade")}</textarea>
          <label>行情问题</label><textarea name="market_issue"{page_disabled}>{review_form_value("market_issue")}</textarea>
          <label>形态问题</label><textarea name="setup_issue"{page_disabled}>{review_form_value("setup_issue")}</textarea>
        </details>
        <div class="form-actions">
          <button type="submit"{page_disabled}>保存复盘</button>
          <button class="secondary" type="submit" name="after_action" value="closeout"{page_disabled}>保存复盘并更新归档</button>
        </div>
      </form>
    </div>

    <div class="card" id="validation-section">
      <h2>验证与归档</h2>
      <p class="muted">完成度 {esc(completion_text(done=validation_done_count, total=validation_total))}{f'；还缺：{esc("、".join(validation_missing))}' if validation_missing else '；验证主结论已齐。'}</p>
      <form class="form-shell" method="post" action="/save-validation#validation-section">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <h3>最低闭环确认</h3>
          <p class="section-note">先确认盘前、盘中、盘后三步是否完成，再落当天主要问题。</p>
          <div class="check-grid">
            <label class="inline-check"><input type="checkbox" name="pre_market_done"{checked(validation_checked("pre_market_done"))}{page_disabled}>盘前完成</label>
            <label class="inline-check"><input type="checkbox" name="intraday_record_complete"{checked(validation_checked("intraday_record_complete"))}{page_disabled}>盘中记录完成</label>
            <label class="inline-check"><input type="checkbox" name="post_market_review_done"{checked(validation_checked("post_market_review_done"))}{page_disabled}>盘后复盘完成</label>
          </div>
          <label for="validation-main-issue-of-day">当日主要问题</label><textarea id="validation-main-issue-of-day" name="main_issue_of_day"{main_issue_required}{page_disabled}>{validation_form_value("main_issue_of_day")}</textarea>
        </div>
        <div class="form-section">
          <h3>无交易日闭环</h3>
          <p class="section-note">如果当日按计划空仓，没有真实交易或纪律事件，就在这里单独归档；此时会用空仓说明替代“当日主要问题”作为验证完成条件。</p>
          <label class="inline-check"><input type="checkbox" name="no_trade_day"{checked(validation_checked("no_trade_day"))}{page_disabled}>当日是无交易日 / 空仓日</label>
          <label for="validation-no-trade-note">空仓说明</label><textarea id="validation-no-trade-note" name="no_trade_note"{page_disabled}>{validation_form_value("no_trade_note")}</textarea>
        </div>
        <details class="form-details low-priority"{open_attr(validation_flags_open)}>
          <summary>补充验证字段</summary>
          <label>当日主要改进</label><textarea name="main_improvement_of_day"{page_disabled}>{validation_form_value("main_improvement_of_day")}</textarea>
          <div class="check-grid">
            <label class="inline-check"><input type="checkbox" name="impulsive_trade_detected"{checked(validation_checked("impulsive_trade_detected"))}{page_disabled}>出现冲动交易</label>
            <label class="inline-check"><input type="checkbox" name="no_stop_loss_trade_detected"{checked(validation_checked("no_stop_loss_trade_detected"))}{page_disabled}>出现无止损 / 止损失守</label>
            <label class="inline-check"><input type="checkbox" name="emotional_overtrade_detected"{checked(validation_checked("emotional_overtrade_detected"))}{page_disabled}>出现情绪化过度交易</label>
          </div>
        </details>
        <div class="form-actions">
          <button type="submit"{page_disabled}>保存验证</button>
          <button class="secondary" type="submit" name="after_action" value="closeout"{page_disabled}>保存验证并更新归档</button>
        </div>
      </form>

      <h3>一键空仓闭环</h3>
      <form class="form-shell" method="post" action="/close-no-trade-day#closeout-preview">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <p class="section-note">当天没有交易和纪律事件时，可以一键写入空仓复盘、验证并更新归档；已有盘中事实时会被拦截。</p>
        </div>
        <div class="form-actions">
          <button class="secondary" type="submit"{page_disabled}>空仓日复盘并归档</button>
        </div>
      </form>

      <h3 id="closeout-section">归档草稿</h3>
      {closeout_meta_html}
      <form class="form-shell" method="post" action="/closeout#closeout-preview">
        <input type="hidden" name="record_path" value="{record_input}">
        <div class="form-section">
          <p class="section-note">归档只负责把当天结论整理成草稿。已有草稿时默认先看现有内容，只有勾选覆盖才会重算。</p>
          <label class="inline-check"><input type="checkbox" name="regenerate"{page_disabled}>重新生成并覆盖草稿</label>
          {closeout_legacy_notice}
          {closeout_stale_notice}
        </div>
        <div class="form-actions">
          <button class="secondary" type="submit"{page_disabled}>生成 / 查看归档草稿</button>
        </div>
      </form>

    </div>
  </section>

  <section class="grid">
    <div class="card wide" id="record-preview">
      <h2>记录预览</h2>
      <p class="muted">默认先看中文整理版；原始 Markdown 只放在折叠区里，排查时再打开。</p>
      {record_readable}
      {record_raw_details}
    </div>
    <div class="card wide" id="closeout-preview">
      <h2>归档预览</h2>
      <p class="muted">这里优先看当天归档内容；如果需要确认生成源，再展开原始 Markdown。</p>
      {closeout_legacy_notice}
      {closeout_stale_notice}
      {closeout_empty_hint}
      {closeout_meta_html}
      {closeout_readable}
      {closeout_raw_details}
    </div>
    <div class="card wide">
      <details class="stage-tools low-priority" id="phase-tools">
        <summary>阶段工具（低频）</summary>
        <p class="muted">阶段总结和字段体检只用于阶段复盘、字段收敛或排查；日常交易闭环不需要打开。</p>
        {phase_meta_html}
        <p><strong>阶段总结：</strong><code>{esc(state.current_summary_path or "未生成")}</code></p>
        <p><strong>字段体检：</strong><code>{esc(state.current_audit_path or "未生成")}</code></p>

        <h3>生成工具</h3>
        <form method="post" action="/trial-summary#phase-tools">
          <label class="inline-check"><input type="checkbox" name="regenerate">重新生成并覆盖总结</label>
          <button class="secondary" type="submit">生成 / 查看阶段总结</button>
        </form>
        <form method="post" action="/field-audit#phase-tools">
          <label class="inline-check"><input type="checkbox" name="regenerate">重新生成并覆盖体检</label>
          <button class="secondary" type="submit">生成 / 查看字段体检</button>
        </form>

        <h3>最近总结</h3>
        {render_recent_artifact_list(recent_summaries, state.current_summary_path, "/load-summary#phase-tools")}
        <h3>最近体检</h3>
        {render_recent_artifact_list(recent_audits, state.current_audit_path, "/load-audit#phase-tools")}

        <details class="history-details nested-low-priority">
          <summary>阶段总结预览</summary>
          {summary_readable}
          {summary_raw_details}
        </details>
        <details class="history-details nested-low-priority">
          <summary>字段体检预览</summary>
          {audit_readable}
          {audit_raw_details}
        </details>
      </details>
    </div>
  </section>
  </div><!-- /panel-review -->
  </div><!-- /tab-panels -->
  </div>
</main>
<script>
(function() {{
  var radios = document.querySelectorAll('.tab-bar input[name=tab]');
  var active = sessionStorage.getItem('ttActiveTab');
  if (active) {{
    var el = document.getElementById(active);
    if (el) el.checked = true;
  }}
  radios.forEach(function(r) {{
    r.addEventListener('change', function() {{
      sessionStorage.setItem('ttActiveTab', this.id);
    }});
  }});
}})();
</script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TrendGo local web workbench.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    raise SystemExit(
        "local_web.py 的旧独立 HTTP 页面已移除。"
        "请使用新版 FastAPI/React 工作台（默认 127.0.0.1:8526）。"
    )


if __name__ == "__main__":
    main()
