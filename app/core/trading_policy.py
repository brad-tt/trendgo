#!/usr/bin/env python3
"""Pure trading-policy helpers shared across TopTrader modules."""

from __future__ import annotations

from typing import Any, Iterable

from core.record_checks import has_meaningful_playbook_value, phase2_trade_checks_passed
from core.utils import clean_text, to_float, trade_pnl_total


def build_decision_gate(
    *,
    workbench: dict[str, Any],
    playbook: dict[str, Any],
    events: list[dict[str, Any]],
    trading_mode: str,
    display_value,
    field_label,
) -> dict[str, Any]:
    blockers: list[str] = []
    cautions: list[str] = []
    strengths: list[str] = []

    if any(clean_text(event.get("event_type")) == "forced_stop" for event in events):
        blockers.append("已有当日停手事件")
    if any(clean_text(event.get("severity")) == "critical" for event in events):
        blockers.append("已有 critical 级纪律事件")

    current_state = clean_text(workbench.get("current_state"))
    main_direction = clean_text(workbench.get("main_direction"))
    opening_plan = clean_text(playbook.get("opening_plan"))
    focus_setup = clean_text(playbook.get("focus_setup"))
    option_session_plan = clean_text(playbook.get("option_session_plan"))
    option_focus_setup = clean_text(playbook.get("option_focus_setup"))

    if current_state in {"defiant", "unfit"}:
        blockers.append(f"当前状态={display_value(current_state)}")
    elif current_state in {"impatient", "tired"}:
        cautions.append(f"当前状态={display_value(current_state)}")
    elif current_state == "stable":
        strengths.append("状态稳定")

    if main_direction in {"", "undecided", "observe"}:
        cautions.append("当日主方向未明确")
    else:
        strengths.append(f"主方向={display_value(main_direction)}")

    if trading_mode == "us_stock_options":
        if not option_session_plan:
            cautions.append("期权时段计划未选")
        elif option_session_plan in {"clear_no_trade", "avoid_event_risk"}:
            cautions.append(f"期权时段计划偏防守：{display_value(option_session_plan)}")
        else:
            strengths.append(f"期权时段计划={display_value(option_session_plan)}")

        if not option_focus_setup:
            cautions.append("期权主练形态未选")
        else:
            strengths.append(f"期权主练形态={display_value(option_focus_setup)}")

        for key in ["focus_tickers", "option_entry_signal", "option_contract_filter", "option_risk_plan", "option_event_risk_plan"]:
            if not has_meaningful_playbook_value(playbook.get(key)):
                cautions.append(f"缺少{field_label(key)}")
    else:
        if not opening_plan:
            cautions.append("开盘计划未选")
        elif opening_plan in {"observe_first", "clear_no_trade"}:
            cautions.append(f"开盘计划偏防守：{display_value(opening_plan)}")
        else:
            strengths.append(f"开盘计划={display_value(opening_plan)}")

        if not focus_setup:
            cautions.append("主练形态未选")
        else:
            strengths.append(f"主练形态={display_value(focus_setup)}")

        for key in ["open_30_key_signal", "certificate_filter_note", "abnormal_plan"]:
            if not has_meaningful_playbook_value(playbook.get(key)):
                cautions.append(f"缺少{field_label(key)}")

    if blockers:
        status = "blocked"
        label = "禁止开新仓"
        action = "只允许记录、复盘、归档；如果要记录事实，也必须自动带出纪律事件。"
    elif cautions:
        status = "observe_only"
        label = "只观察 / 等确认"
        action = "可以继续观察和补计划；开新仓必须重新通过四条件和工具过滤。"
    else:
        status = "ready"
        label = "可执行"
        action = "只做计划内 A/B 级机会，仍按四条件和工具过滤逐笔确认。"

    return {
        "status": status,
        "label": label,
        "action": action,
        "blockers": blockers,
        "cautions": cautions,
        "strengths": strengths,
    }


def build_risk_state(
    *,
    workbench: dict[str, Any],
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    trading_mode: str,
    filter_label: str,
    format_number,
) -> dict[str, Any]:
    pnl_total = trade_pnl_total(trades)
    capital = to_float(workbench.get("capital_used"))
    target_pct = to_float(workbench.get("profit_target_pct"))
    target_amount = capital * target_pct / 100 if capital and target_pct is not None else None
    trade_count = len(trades)
    violations = sum(1 for trade in trades if trade.get("rule_violation") is True)
    failed_checks = sum(1 for trade in trades if phase2_trade_checks_passed(trade) is False)
    filter_fail = sum(1 for trade in trades if trade.get("certificate_filter_passed") is False)
    abnormal_count = sum(1 for trade in trades if clean_text(trade.get("abnormal_scenario")) not in {"", "none"})
    forced_stop_events = [event for event in events if clean_text(event.get("event_type")) == "forced_stop"]
    critical_events = [event for event in events if clean_text(event.get("severity")) == "critical"]
    pause_events = [
        event
        for event in events
        if clean_text(event.get("event_type")) in {"forced_pause", "overtrade_signal"}
        or clean_text(event.get("severity")) == "stop"
    ]

    blockers: list[str] = []
    cautions: list[str] = []
    strengths: list[str] = []

    if forced_stop_events:
        blockers.append("已有当日停手事件")
    if critical_events:
        blockers.append("已有 critical 级纪律事件")
    if target_amount and pnl_total is not None and pnl_total <= -target_amount:
        blockers.append(f"亏损已达到当日风险阈值 {format_number(-target_amount)}")

    if violations:
        cautions.append(f"已有违规交易 {violations} 笔")
    if failed_checks:
        cautions.append(f"四条件未齐交易 {failed_checks} 笔")
    if filter_fail:
        cautions.append(f"{filter_label}未过 {filter_fail} 笔")
    if abnormal_count:
        cautions.append(f"异常场景交易 {abnormal_count} 笔")
    if pause_events:
        cautions.append(f"暂停 / 过度交易信号 {len(pause_events)} 次")
    if target_amount and pnl_total is not None and pnl_total >= target_amount:
        cautions.append(f"盈利已达目标 {format_number(target_amount)}，进入保护利润模式")
    if trade_count >= 3:
        cautions.append(f"交易次数已到 {trade_count} 笔，防止用数量替代质量")

    if pnl_total is not None:
        strengths.append(f"当前盈亏 {format_number(pnl_total)}")
    if target_amount is not None:
        strengths.append(f"目标金额 {format_number(target_amount)}")

    if blockers:
        status = "stop"
        label = "停止开新仓"
        action = "只允许记录、复盘和归档；不得继续新增交易。"
    elif any("盈利已达目标" in item for item in cautions):
        status = "protect_profit"
        label = "保护利润"
        action = "默认停止加单；只有重新通过 A 级机会和决策门，才允许记录下一笔。"
    elif cautions:
        status = "cooldown"
        label = "降频复核"
        action = "下一笔前必须重新通过决策门、四条件、工具过滤和情绪复核。"
    else:
        status = "normal"
        label = "风险正常"
        action = "继续按计划执行，不放宽机会质量。"

    return {
        "status": status,
        "label": label,
        "action": action,
        "blockers": blockers,
        "cautions": cautions,
        "strengths": strengths,
        "pnl_total": pnl_total,
        "target_amount": target_amount,
        "trade_count": trade_count,
        "filter_label": filter_label,
    }


def build_execution_lock(decision_gate: dict[str, Any], risk_state: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if decision_gate.get("blockers"):
        reasons.extend(clean_text(item) for item in decision_gate["blockers"] if clean_text(item))
    if risk_state.get("blockers"):
        reasons.extend(clean_text(item) for item in risk_state["blockers"] if clean_text(item))
    if clean_text(decision_gate.get("status")) == "blocked" or clean_text(risk_state.get("status")) == "stop":
        return {
            "status": "locked",
            "label": "禁止开新仓",
            "action": "可以记录已经发生的事实，但系统会自动带出纪律 / 风控事件。",
            "reasons": reasons or ["决策门或风险控制器已经触发硬拦截"],
        }

    cautions: list[str] = []
    if clean_text(decision_gate.get("status")) == "observe_only":
        cautions.append(clean_text(decision_gate.get("label")) or "只观察")
        cautions.extend(clean_text(item) for item in decision_gate.get("cautions", [])[:3] if clean_text(item))
    if clean_text(risk_state.get("status")) in {"cooldown", "protect_profit"}:
        cautions.append(clean_text(risk_state.get("label")) or "风险复核")
        cautions.extend(clean_text(item) for item in risk_state.get("cautions", [])[:3] if clean_text(item))
    if cautions:
        return {
            "status": "caution",
            "label": "开仓前必须复核",
            "action": "仍可记录事实；如果继续开仓，默认保留自动纪律联动。",
            "reasons": cautions,
        }

    return {
        "status": "open",
        "label": "允许按计划记录",
        "action": "只记录计划内且通过四条件和工具过滤的交易。",
        "reasons": [],
    }

