#!/usr/bin/env python3
"""Pure record-validation helpers shared across TopTrader modules."""

from __future__ import annotations

from typing import Any, Iterable

from core.utils import clean_text, numeric_almost_equal, to_float, trade_pnl_total

REVIEW_REQUIRED_KEYS = (
    "pnl",
    "trade_count",
    "best_trade_note",
    "worst_trade_note",
    "execution_issue",
    "emotion_issue",
    "risk_issue",
    "next_day_one_fix",
)

VALIDATION_REQUIRED_BOOL_KEYS = (
    "pre_market_done",
    "intraday_record_complete",
    "post_market_review_done",
)

WORKBENCH_REQUIRED_KEYS = (
    "main_direction",
    "current_state",
    "capital_used",
    "profit_target_pct",
)

HSI_PLAYBOOK_REQUIRED_KEYS = (
    "opening_plan",
    "focus_setup",
    "open_30_key_signal",
    "certificate_filter_note",
    "abnormal_plan",
)

US_PLAYBOOK_REQUIRED_KEYS = (
    "option_session_plan",
    "focus_tickers",
    "option_focus_setup",
    "option_entry_signal",
    "option_contract_filter",
    "option_risk_plan",
    "option_event_risk_plan",
)


def abnormal_scenario_recorded(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def has_meaningful_workbench_value(key: str, value: Any) -> bool:
    text = clean_text(value)
    if key == "main_direction" and text == "undecided":
        return False
    if key == "current_state" and text == "unset":
        return False
    return text != ""


def has_meaningful_playbook_value(value: Any) -> bool:
    return clean_text(value) != ""


def phase2_trade_checks_passed(trade: dict[str, Any]) -> bool | None:
    check_values = [
        trade.get("direction_clear"),
        trade.get("location_ok"),
        trade.get("confirmation_ok"),
        trade.get("risk_clear"),
    ]
    if not any(value in {True, False} for value in check_values):
        return None
    return all(value is True for value in check_values)


def phase2_trade_record_complete(trade: dict[str, Any]) -> bool:
    return (
        clean_text(trade.get("session_window")) != ""
        and trade.get("direction_clear") in {True, False}
        and trade.get("location_ok") in {True, False}
        and trade.get("confirmation_ok") in {True, False}
        and trade.get("risk_clear") in {True, False}
        and trade.get("certificate_filter_passed") in {True, False}
        and abnormal_scenario_recorded(trade.get("abnormal_scenario"))
    )


def trade_failed_check_keys(trade: dict[str, Any]) -> list[str]:
    failed = []
    for key in ["direction_clear", "location_ok", "confirmation_ok", "risk_clear"]:
        if trade.get(key) is False:
            failed.append(key)
    if trade.get("certificate_filter_passed") is False:
        failed.append("certificate_filter_passed")
    return failed


def trade_needs_risk_event(
    trade: dict[str, Any],
    *,
    risky_setup_types: Iterable[str],
    risky_pre_trade_emotions: Iterable[str],
) -> bool:
    abnormal_scenario = clean_text(trade.get("abnormal_scenario"))
    setup_type = clean_text(trade.get("setup_type"))
    pre_trade_emotion = clean_text(trade.get("pre_trade_emotion"))
    emotion_state = clean_text(trade.get("emotion_state"))
    return (
        trade.get("rule_violation") is True
        or bool(trade_failed_check_keys(trade))
        or trade.get("certificate_filter_passed") is False
        or abnormal_scenario not in {"", "none"}
        or setup_type in set(risky_setup_types)
        or pre_trade_emotion in set(risky_pre_trade_emotions)
        or emotion_state in {"revenge", "impulsive"}
    )


def has_risk_event_coverage(
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    risky_setup_types: Iterable[str],
    risky_pre_trade_emotions: Iterable[str],
) -> bool:
    if not any(
        trade_needs_risk_event(
            trade,
            risky_setup_types=risky_setup_types,
            risky_pre_trade_emotions=risky_pre_trade_emotions,
        )
        for trade in trades
    ):
        return True
    risk_event_types = {"rule_violation", "emotion_trigger", "forced_pause", "forced_stop", "overtrade_signal"}
    return any(clean_text(event.get("event_type")) in risk_event_types for event in events)


def is_review_done(review: dict[str, Any]) -> bool:
    return all(clean_text(review.get(key)) for key in REVIEW_REQUIRED_KEYS)


def is_validation_done(validation: dict[str, Any]) -> bool:
    bools_ok = all(validation.get(key) is True for key in VALIDATION_REQUIRED_BOOL_KEYS)
    if not bools_ok:
        return False
    if validation.get("no_trade_day") is True:
        return clean_text(validation.get("no_trade_note")) != ""
    return clean_text(validation.get("main_issue_of_day")) != ""


def missing_review_keys(review: dict[str, Any]) -> list[str]:
    return [key for key in REVIEW_REQUIRED_KEYS if clean_text(review.get(key)) == ""]


def missing_validation_keys(validation: dict[str, Any]) -> list[str]:
    missing = [key for key in VALIDATION_REQUIRED_BOOL_KEYS if validation.get(key) is not True]
    if validation.get("no_trade_day") is True:
        if clean_text(validation.get("no_trade_note")) == "":
            missing.append("no_trade_note")
    elif clean_text(validation.get("main_issue_of_day")) == "":
        missing.append("main_issue_of_day")
    return missing


def missing_workbench_keys(workbench: dict[str, Any]) -> list[str]:
    return [key for key in WORKBENCH_REQUIRED_KEYS if not has_meaningful_workbench_value(key, workbench.get(key))]


def missing_playbook_keys(playbook: dict[str, Any], trading_mode: str) -> list[str]:
    required_keys = (
        US_PLAYBOOK_REQUIRED_KEYS
        if clean_text(trading_mode) == "us_stock_options"
        else HSI_PLAYBOOK_REQUIRED_KEYS
    )
    return [key for key in required_keys if not has_meaningful_playbook_value(playbook.get(key))]


def is_workbench_ready(workbench: dict[str, Any]) -> bool:
    return not missing_workbench_keys(workbench)


def is_meaningful_review_sentence(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return False
    compact = "".join(char for char in text if char.isalnum())
    if len(compact) < 4:
        return False
    if compact.isdigit():
        return False
    return True


def review_text_quality_issue_keys(
    review: dict[str, Any],
    validation: dict[str, Any],
    *,
    review_text_quality_fields: Iterable[str],
) -> list[str]:
    issue_keys = [
        key
        for key in review_text_quality_fields
        if not is_meaningful_review_sentence(review.get(key))
    ]
    validation_key = "no_trade_note" if validation.get("no_trade_day") is True else "main_issue_of_day"
    if not is_meaningful_review_sentence(validation.get(validation_key)):
        issue_keys.append(validation_key)
    return issue_keys


def review_text_quality_ok(
    review: dict[str, Any],
    validation: dict[str, Any],
    *,
    review_text_quality_fields: Iterable[str],
) -> bool:
    meaningful_review_fields = sum(
        1
        for key in review_text_quality_fields
        if is_meaningful_review_sentence(review.get(key))
    )
    validation_key = "no_trade_note" if validation.get("no_trade_day") is True else "main_issue_of_day"
    return meaningful_review_fields >= 4 and is_meaningful_review_sentence(validation.get(validation_key))


def review_hub_quality_issues(
    *,
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    review_text_quality_fields: Iterable[str],
) -> list[str]:
    issues = []
    if not is_review_done(review):
        issues.append("复盘未完整")
    if not is_validation_done(validation):
        issues.append("验证未完整")
    review_trade_count = clean_text(review.get("trade_count"))
    if review_trade_count and review_trade_count != str(len(trades)):
        issues.append("复盘交易数与真实交易数不一致")
    review_pnl = to_float(review.get("pnl"))
    trades_pnl = trade_pnl_total(trades)
    if review_pnl is not None and trades_pnl is not None and not numeric_almost_equal(review_pnl, trades_pnl):
        issues.append("复盘盈亏与真实交易盈亏不一致")
    if validation.get("no_trade_day") is True and (trades or events):
        issues.append("空仓标记与盘中事实冲突")
    if is_review_done(review) and is_validation_done(validation) and not review_text_quality_ok(
        review,
        validation,
        review_text_quality_fields=review_text_quality_fields,
    ):
        labels = review_text_quality_issue_keys(
            review,
            validation,
            review_text_quality_fields=review_text_quality_fields,
        )
        label_text = "、".join(labels[:8])
        issues.append(f"复盘文本像占位值：{label_text}" if label_text else "复盘文本像占位值")
    return issues


def build_acceptance_gate(
    *,
    record_path_present: bool,
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
    trading_mode: str,
    playbook_title: str,
    filter_label: str,
    review_text_quality_fields: Iterable[str],
    risky_setup_types: Iterable[str],
    risky_pre_trade_emotions: Iterable[str],
) -> dict[str, Any]:
    quality_issues = review_hub_quality_issues(
        trades=trades,
        events=events,
        review=review,
        validation=validation,
        review_text_quality_fields=review_text_quality_fields,
    )
    intraday_done = bool(trades or events) or (
        validation.get("no_trade_day") is True and validation.get("intraday_record_complete") is True
    )
    trade_records_complete = all(phase2_trade_record_complete(trade) for trade in trades)
    checks = [
        {
            "key": "active_day",
            "label": "当日可验收",
            "passed": bool(record_path_present and record_editable),
            "target": "#today-section",
            "detail": "需要载入当前最新交易日，历史交易日不作为本轮验收入口。",
        },
        {
            "key": "pre_market",
            "label": "盘前专项完整",
            "passed": is_workbench_ready(workbench) and not missing_playbook_keys(playbook, trading_mode),
            "target": "#workbench-section",
            "detail": f"作战台和{playbook_title}都要补齐。",
        },
        {
            "key": "intraday",
            "label": "盘中事实完整",
            "passed": intraday_done,
            "target": "#trade-section",
            "detail": "有交易 / 纪律事实，或明确完成空仓日闭环。",
        },
        {
            "key": "phase2_trade_fields",
            "label": "主战交易字段完整",
            "passed": trade_records_complete,
            "target": "#trade-section",
            "detail": f"每笔交易都要有时段、四条件、{filter_label}和异常场景。",
        },
        {
            "key": "risk_event_coverage",
            "label": "风险动作已覆盖",
            "passed": has_risk_event_coverage(
                trades,
                events,
                risky_setup_types=risky_setup_types,
                risky_pre_trade_emotions=risky_pre_trade_emotions,
            ),
            "target": "#event-section",
            "detail": "违规、异常、情绪风险或过滤失败要有纪律事件覆盖。",
        },
        {
            "key": "review_validation",
            "label": "复盘验证完成",
            "passed": is_review_done(review) and is_validation_done(validation),
            "target": "#review-section",
            "detail": "盘后复盘和归档验证都要完成。",
        },
        {
            "key": "sample_trusted",
            "label": "记录完整",
            "passed": not quality_issues,
            "target": "#review-section",
            "detail": "；".join(quality_issues) if quality_issues else "复盘、验证和交易事实一致。",
        },
        {
            "key": "closeout_synced",
            "label": "归档同步",
            "passed": closeout_exists and not closeout_legacy and not closeout_stale,
            "target": "#closeout-section",
            "detail": "归档草稿必须存在、为新版中文格式，且不落后于记录文件。",
        },
    ]
    passed_count = sum(1 for check in checks if check["passed"])
    failed = [check for check in checks if not check["passed"]]
    return {
        "passed": not failed,
        "label": "通过" if not failed else "未通过",
        "passed_count": passed_count,
        "total": len(checks),
        "checks": checks,
        "failed": failed,
        "first_target": failed[0]["target"] if failed else "#record-preview",
    }


def build_workflow_stage(
    *,
    record_path_present: bool,
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
    trading_mode: str,
    playbook_title: str,
    review_text_quality_fields: Iterable[str],
) -> dict[str, Any]:
    if not record_path_present:
        return {"key": "setup", "label": "未开始", "progress": 0, "note": "先创建或载入当天记录。"}
    if not record_editable:
        return {"key": "history", "label": "历史只读", "progress": 100, "note": "当前载入的是历史交易日；只查看，不再回改旧记录。"}
    if is_review_done(review) and is_validation_done(validation):
        quality_issues = review_hub_quality_issues(
            trades=trades,
            events=events,
            review=review,
            validation=validation,
            review_text_quality_fields=review_text_quality_fields,
        )
        if quality_issues:
            return {"key": "acceptance", "label": "验收修复", "progress": 92, "note": "复盘文本或事实一致性还需要补齐。"}
        if closeout_exists and not closeout_legacy and not closeout_stale:
            return {"key": "done", "label": "已归档", "progress": 100, "note": "当天记录、复盘、验证和归档已对齐。"}
        return {"key": "closeout", "label": "等待归档", "progress": 84, "note": "复盘和验证已齐，下一步生成或更新归档。"}
    if trades or events or validation.get("intraday_record_complete") is True:
        return {"key": "review", "label": "盘后复盘", "progress": 66, "note": "已有盘中事实，下一步完成复盘和验证。"}
    if not missing_workbench_keys(workbench) and not missing_playbook_keys(playbook, trading_mode):
        return {"key": "intraday", "label": "盘中执行", "progress": 42, "note": "盘前计划已具备，等待交易事实或空仓闭环。"}
    return {"key": "pre_market", "label": "盘前准备", "progress": 18, "note": f"先补齐作战台和{playbook_title}。"}


def build_next_action(
    *,
    stage: dict[str, Any],
    record_path_present: bool,
    record_editable: bool,
    trades: list[dict[str, Any]],
    events: list[dict[str, Any]],
    review: dict[str, Any],
    validation: dict[str, Any],
    closeout_exists: bool,
    closeout_legacy: bool,
    closeout_stale: bool,
    acceptance_gate: dict[str, Any],
    execution_lock: dict[str, Any],
    workbench_missing_labels: list[str],
    playbook_missing_labels: list[str],
    review_missing_labels: list[str],
    validation_missing_labels: list[str],
    closeout_status_label: str,
) -> dict[str, Any]:
    if not record_path_present:
        return {
            "stage": stage,
            "level": "warn",
            "title": "先创建或载入交易日",
            "body": "没有交易日记录时，后面的决策门、风控和归档都没有源数据。",
            "target": "#today-section",
            "button": "去创建 / 载入",
            "details": [],
        }
    if not record_editable:
        return {
            "stage": stage,
            "level": "neutral",
            "title": "当前是历史交易日",
            "body": "历史记录保持只读，避免复盘后回改旧数据。",
            "target": "#review-hub",
            "button": "查看历史记录",
            "details": [],
        }

    if workbench_missing_labels or playbook_missing_labels:
        missing = workbench_missing_labels + playbook_missing_labels
        return {
            "stage": stage,
            "level": "warn",
            "title": "先补齐盘前作战",
            "body": "盘前信息不完整时，不要直接进入交易记录。",
            "target": "#workbench-section",
            "button": "补作战台",
            "details": missing[:6],
        }

    if clean_text(execution_lock.get("status")) == "locked":
        return {
            "stage": stage,
            "level": "danger",
            "title": clean_text(execution_lock.get("label")),
            "body": clean_text(execution_lock.get("action")),
            "target": "#event-section",
            "button": "记录纪律动作",
            "details": list(execution_lock.get("reasons", []))[:5],
        }
    if clean_text(execution_lock.get("status")) == "caution" and not trades:
        return {
            "stage": stage,
            "level": "warn",
            "title": "先观察，不急着开仓",
            "body": "当前不是完全可执行状态。先观察，只有出现清晰 A/B 级机会再记录事实。",
            "target": "#command-center",
            "button": "看驾驶舱",
            "details": list(execution_lock.get("reasons", []))[:5],
        }

    if not trades and not events:
        return {
            "stage": stage,
            "level": "neutral",
            "title": "等待盘中事实",
            "body": "如果出现合格交易就记录；如果全天无交易，盘后用空仓闭环归档。",
            "target": "#trade-section",
            "button": "去记录交易",
            "details": ["无交易时盘后使用一键空仓闭环"],
        }

    if review_missing_labels:
        return {
            "stage": stage,
            "level": "warn",
            "title": "完成盘后复盘",
            "body": "已有盘中事实后，先把当日好坏动作、执行、情绪、风控和明日只改写清楚。",
            "target": "#review-section",
            "button": "去复盘",
            "details": review_missing_labels[:6],
        }

    if validation_missing_labels:
        return {
            "stage": stage,
            "level": "warn",
            "title": "完成归档验证",
            "body": "复盘后补齐流程验证，确认盘前、盘中、盘后是否闭环。",
            "target": "#validation-section",
            "button": "去验证",
            "details": validation_missing_labels[:6],
        }

    if not acceptance_gate.get("passed"):
        failed = acceptance_gate.get("failed", [])
        return {
            "stage": stage,
            "level": "warn",
            "title": "补齐单日验收缺口",
            "body": "当前主战按 1 个真实交易日验收；还有验收项未通过。",
            "target": acceptance_gate.get("first_target") or "#command-center",
            "button": "处理验收缺口",
            "details": [check["label"] + "：" + check["detail"] for check in failed[:6]],
        }

    if not closeout_exists or closeout_legacy or closeout_stale:
        return {
            "stage": stage,
            "level": "warn",
            "title": "生成或更新归档",
            "body": "复盘和验证已齐，最后把当天结论同步到归档草稿。",
            "target": "#closeout-section",
            "button": "去归档",
            "details": [closeout_status_label],
        }

    return {
        "stage": stage,
        "level": "ok",
        "title": "当日闭环已完成",
        "body": "记录、复盘、验证和归档已经对齐，可以只读回看。",
        "target": "#record-preview",
        "button": "查看记录",
        "details": [],
    }

