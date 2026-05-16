#!/usr/bin/env python3
"""FastAPI JSON backend for TrendGo."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import local_web
from core import agent_intake
from core import agent_policy
from core.hsi_range_provider import HSIRangeError, ResilientHSIRangeProvider
from core import record_io
from core import trading_policy
from core import workspace_state
from core.utils import clean_text as shared_clean_text
from core.utils import to_float as shared_to_float
from database import dal

USD_HKD_RATE = 7.8  # 默认值；未来可从配置文件读取
HSI_RANGE_PROVIDER = ResilientHSIRangeProvider()

SETUP_VALUE_ALIASES: dict[str, str] = {
    "突破回踩": "trend_pullback",
    "趋势回踩": "trend_pullback",
    "回踩守住": "trend_pullback",
    "回踩确认": "trend_pullback",
    "回踩站回": "trend_pullback",
    "开盘突破": "opening_breakout",
    "突破确认": "opening_breakout",
    "确认突破": "opening_breakout",
    "假突破追单": "false_breakout_chase",
    "追单": "false_breakout_chase",
    "观察": "clear_observe",
    "先看": "clear_observe",
}

EMOTION_STATE_ALIASES: dict[str, str] = {
    "控制不住": "impulsive",
    "冲动": "impulsive",
    "手痒": "impulsive",
    "报复": "revenge",
    "翻本": "revenge",
    "赚回来": "revenge",
    "焦虑": "anxious",
    "紧张": "anxious",
    "稳定": "stable",
    "平静": "stable",
}

PRE_TRADE_EMOTION_ALIASES: dict[str, str] = {
    "控制不住": "rushed",
    "冲动": "rushed",
    "手痒": "rushed",
    "急着进": "rushed",
    "着急": "rushed",
    "不服气": "defiant",
    "不服": "defiant",
    "硬要做": "defiant",
    "硬来": "defiant",
    "怕错过": "fomo",
    "想赚回来": "recover_loss",
    "赚回来": "recover_loss",
    "翻本": "recover_loss",
    "稳定": "stable",
    "平静": "stable",
}

POST_TRADE_EMOTION_ALIASES: dict[str, str] = {
    "后悔": "regret",
    "满意": "satisfied",
    "踏实": "satisfied",
    "着急": "rushed",
    "不服": "defiant",
    "稳定": "stable",
    "平静": "stable",
}


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def camelize_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {to_camel(str(key)): camelize_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [camelize_keys(item) for item in value]
    return value


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CountItem(CamelModel):
    label: str
    count: int


class TimelineNote(CamelModel):
    day_number: int
    trade_date: str
    note: str


class ArtifactItem(CamelModel):
    title: str
    path: str


class RecentRecordItem(CamelModel):
    day_number: int
    trade_date: str
    market: str
    primary_instrument: str
    trading_mode: str
    current_state: str
    trade_count: int
    review_done: bool
    validation_done: bool
    source_record_path: str
    closeout_label: str
    is_current: bool


class AppStateResponse(CamelModel):
    current_market: str = "HK"
    current_day_number: int | None = None
    current_trade_date: str = ""
    current_record_path: str = ""
    current_closeout_path: str = ""
    current_summary_path: str = ""
    current_audit_path: str = ""
    theme: str = "dark"
    today_records: dict[str, bool] = Field(default_factory=lambda: {"HK": False, "US": False})
    review_hub_window: str
    review_hub_sample_filter: str
    recent_records: list[RecentRecordItem]
    recent_closeouts: list[ArtifactItem]
    recent_summaries: list[ArtifactItem]
    recent_audits: list[ArtifactItem]
    usd_hkd_rate: float = 7.8


class CloseoutPayload(CamelModel):
    path: str = ""
    exists: bool
    legacy: bool
    stale: bool
    preview: str = ""


class ArtifactPreviewResponse(CamelModel):
    path: str = ""
    title: str = ""
    exists: bool
    preview: str = ""


class DailyRecordResponse(CamelModel):
    source_record_path: str
    is_current: bool
    base: dict[str, Any]
    pre_market: dict[str, Any]
    workbench: dict[str, Any]
    playbook: dict[str, Any]
    trades: list[dict[str, Any]]
    events: list[dict[str, Any]]
    observations: list[dict[str, Any]] = Field(default_factory=list)
    review: dict[str, Any]
    validation: dict[str, Any]
    closeout: CloseoutPayload


class ReviewHubStatsResponse(CamelModel):
    day_count: int
    trade_day_count: int
    no_trade_day_count: int
    total_pnl: float | None = None
    avg_daily_pnl: float | None = None
    trade_count: int
    violation_count: int
    review_done_days: int
    validation_done_days: int
    closeout_synced_days: int
    followed_yes: int
    followed_total: int
    plan_follow_rate: float | None = None
    win_count: int
    loss_count: int
    breakeven_count: int
    impulsive_days: int
    stop_loss_days: int
    overtrade_days: int
    opening_30_trade_count: int
    phase2_check_fail_count: int
    certificate_filter_fail_count: int
    abnormal_trade_count: int
    top_setups: list[CountItem]
    top_active_plans: list[CountItem]
    top_active_setups: list[CountItem]
    recent_issues: list[TimelineNote]
    recent_fixes: list[TimelineNote]
    recent_no_trade_notes: list[TimelineNote]


class ReviewHubDayRowResponse(CamelModel):
    path: str
    day: int
    trade_date: str
    market: str
    state: str
    trade_count: int
    has_trades: bool
    violation_count: int
    pnl_value: float | None = None
    review_done: bool
    validation_done: bool
    workbench_ready: bool
    followed_yes: int
    followed_total: int
    win_count: int
    loss_count: int
    breakeven_count: int
    opening_30_count: int
    phase2_check_fail_count: int
    certificate_filter_fail_count: int
    abnormal_count: int
    trading_mode: str
    active_plan: str
    active_setup: str
    trusted_sample: bool
    quality_issues: list[str]
    no_trade_day: bool
    no_trade_note: str
    main_issue: str
    main_improvement: str
    next_fix: str
    impulsive_flag: bool
    stop_loss_flag: bool
    overtrade_flag: bool
    is_current: bool
    is_editable: bool
    closeout_label: str
    closeout_synced: bool


class HSIRangeSnapshotResponse(CamelModel):
    update_time: str = ""
    last_price: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    turnover: float | None = None


class HSIRangeIntradayResponse(CamelModel):
    range_points: float
    range_pct: float
    rank_pct: float
    position_pct: float
    p75_left_pct: float
    p90_left_pct: float
    p75_left_points: float
    p90_left_points: float


class HSIRangeStatusResponse(CamelModel):
    level: str
    label: str
    message: str


class HSIRangeStatsResponse(CamelModel):
    lookback: int
    start_date: str
    end_date: str
    mean_pct: float
    median_pct: float
    p75_pct: float
    p90_pct: float
    max_pct: float
    mean_points: float
    median_points: float
    p75_points: float
    p90_points: float
    max_points: float


class HSIRangeStateResponse(CamelModel):
    ok: bool
    code: str = ""
    name: str = ""
    generated_at: str = ""
    snapshot: HSIRangeSnapshotResponse | None = None
    intraday: HSIRangeIntradayResponse | None = None
    status: HSIRangeStatusResponse | None = None
    stats: HSIRangeStatsResponse | None = None
    warnings: list[str] = []
    error: str = ""


class ActionResponse(CamelModel):
    message: str


class TodoItemResponse(CamelModel):
    text: str
    target: str = ""


class WorkflowStepResponse(CamelModel):
    label: str
    note: str
    target: str = ""
    done: bool


class HealthItemResponse(CamelModel):
    level: str
    text: str
    target: str = ""


class DecisionStatusResponse(CamelModel):
    status: str
    label: str
    action: str
    blockers: list[str] = []
    cautions: list[str] = []
    strengths: list[str] = []


class RiskStatusResponse(CamelModel):
    status: str
    label: str
    action: str
    blockers: list[str] = []
    cautions: list[str] = []
    strengths: list[str] = []
    pnl_total: float | None = None
    target_amount: float | None = None
    trade_count: int
    filter_label: str = ""


class ExecutionLockResponse(CamelModel):
    status: str
    label: str
    action: str
    reasons: list[str] = []


class DaySummaryResponse(CamelModel):
    capital_used: str
    profit_target_pct: str
    pnl_total: str
    pnl_pct: str
    target_distance: str
    trade_count: str
    violation_count: str
    grade_counts: str


class ReviewDefaultsResponse(CamelModel):
    pnl: str
    trade_count: str
    pnl_hint: str
    trade_count_hint: str


class PreviousContextResponse(CamelModel):
    day: str = ""
    trade_date: str = ""
    trading_mode: str = ""
    next_fix: str = ""
    improvement: str = ""
    main_issue: str = ""
    plan: str = ""
    setup: str = ""


class DayDiagnosticsResponse(CamelModel):
    todo_items: list[TodoItemResponse]
    workflow_steps: list[WorkflowStepResponse]
    record_health_items: list[HealthItemResponse]
    decision_gate: DecisionStatusResponse
    risk_state: RiskStatusResponse
    execution_lock: ExecutionLockResponse
    day_summary: DaySummaryResponse
    review_defaults: ReviewDefaultsResponse
    previous_context: PreviousContextResponse


class WorkspaceOverviewResponse(CamelModel):
    state: AppStateResponse
    current_day: DailyRecordResponse | None = None
    diagnostics: DayDiagnosticsResponse | None = None


class ArtifactsOverviewResponse(CamelModel):
    current_closeout: ArtifactPreviewResponse
    current_summary: ArtifactPreviewResponse
    current_audit: ArtifactPreviewResponse
    recent_closeouts: list[ArtifactItem]
    recent_summaries: list[ArtifactItem]
    recent_audits: list[ArtifactItem]


class HistoryOverviewResponse(CamelModel):
    window: str
    sample_filter: str
    stats: ReviewHubStatsResponse
    days: list[ReviewHubDayRowResponse]


class StateActionResponse(ActionResponse):
    state: AppStateResponse


class DayActionResponse(ActionResponse):
    day: DailyRecordResponse
    auto_event_id: str = ""


class AgentRuleHit(CamelModel):
    rule_id: str = Field(alias="ruleId")
    severity: str
    message: str
    source: str


class AgentKnowledgeRoute(CamelModel):
    route_id: str = Field(alias="routeId")
    distortion_type: str = Field(alias="distortionType")
    trigger_phrases: str = Field(default="", alias="triggerPhrases")
    playbook: str
    capability_pack: str = Field(default="", alias="capabilityPack")
    first_action: str = Field(alias="firstAction")


class AgentTradeOpenResponse(DayActionResponse):
    rule_hits: list[AgentRuleHit] = Field(default_factory=list, alias="ruleHits")
    knowledge_routes: list[AgentKnowledgeRoute] = Field(default_factory=list, alias="knowledgeRoutes")


class AgentTradeOpenIntakeRequest(CamelModel):
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    market: str = "HK"
    raw_note: str = Field(alias="rawNote")
    commit: bool = False
    current_state: str = Field(default="normal", alias="currentState")
    focus: str = ""
    trading_mode: str | None = Field(default=None, alias="tradingMode")
    agent_note: str = Field(default="", alias="agentNote")
    suspected_distortions: list[str] = Field(default_factory=list, alias="suspectedDistortions")


class AgentTradeOpenIntakeResponse(ActionResponse):
    raw_note: str = Field(alias="rawNote")
    proposal: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    missing_labels: list[str] = Field(default_factory=list, alias="missingLabels")
    warnings: list[str] = []
    follow_up_questions: list[str] = Field(default_factory=list, alias="followUpQuestions")
    can_write: bool = Field(alias="canWrite")
    committed: bool
    context: "AgentContextResponse | None" = None
    preview_rule_hits: list[AgentRuleHit] = Field(default_factory=list, alias="previewRuleHits")
    preview_knowledge_routes: list[AgentKnowledgeRoute] = Field(default_factory=list, alias="previewKnowledgeRoutes")
    day: DailyRecordResponse | None = None
    auto_event_id: str = Field(default="", alias="autoEventId")
    rule_hits: list[AgentRuleHit] = Field(default_factory=list, alias="ruleHits")
    knowledge_routes: list[AgentKnowledgeRoute] = Field(default_factory=list, alias="knowledgeRoutes")


class AgentTradeCloseIntakeRequest(CamelModel):
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    market: str = "HK"
    raw_note: str = Field(alias="rawNote")
    commit: bool = False
    agent_note: str = Field(default="", alias="agentNote")


class AgentTradeCloseIntakeResponse(ActionResponse):
    raw_note: str = Field(alias="rawNote")
    proposal: dict[str, Any]
    target_trade_id: str = Field(default="", alias="targetTradeId")
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    missing_labels: list[str] = Field(default_factory=list, alias="missingLabels")
    warnings: list[str] = []
    follow_up_questions: list[str] = Field(default_factory=list, alias="followUpQuestions")
    can_write: bool = Field(alias="canWrite")
    committed: bool
    context: "AgentContextResponse | None" = None
    pnl_preview: float | None = Field(default=None, alias="pnlPreview")
    result_preview: str = Field(default="", alias="resultPreview")
    day: DailyRecordResponse | None = None


class AgentRuleEventIntakeRequest(CamelModel):
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    market: str = "HK"
    raw_note: str = Field(alias="rawNote")
    commit: bool = False
    agent_note: str = Field(default="", alias="agentNote")


class AgentRuleEventIntakeResponse(ActionResponse):
    raw_note: str = Field(alias="rawNote")
    proposal: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    missing_labels: list[str] = Field(default_factory=list, alias="missingLabels")
    warnings: list[str] = []
    follow_up_questions: list[str] = Field(default_factory=list, alias="followUpQuestions")
    can_write: bool = Field(alias="canWrite")
    committed: bool
    context: "AgentContextResponse | None" = None
    day: DailyRecordResponse | None = None


class AgentReviewIntakeRequest(CamelModel):
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    market: str = "HK"
    raw_note: str = Field(alias="rawNote")
    commit: bool = False
    agent_note: str = Field(default="", alias="agentNote")


class AgentReviewIntakeResponse(ActionResponse):
    raw_note: str = Field(alias="rawNote")
    proposal: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    missing_labels: list[str] = Field(default_factory=list, alias="missingLabels")
    warnings: list[str] = []
    follow_up_questions: list[str] = Field(default_factory=list, alias="followUpQuestions")
    can_write: bool = Field(alias="canWrite")
    committed: bool
    context: "AgentContextResponse | None" = None
    day: DailyRecordResponse | None = None


class AgentWorkflowIntakeRequest(CamelModel):
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    market: str = "HK"
    raw_note: str = Field(alias="rawNote")
    commit: bool = False
    current_state: str = Field(default="normal", alias="currentState")
    focus: str = ""
    trading_mode: str | None = Field(default=None, alias="tradingMode")
    agent_note: str = Field(default="", alias="agentNote")
    suspected_distortions: list[str] = Field(default_factory=list, alias="suspectedDistortions")


class AgentWorkflowIntakeResponse(ActionResponse):
    intent: str
    intent_confidence: float = Field(alias="intentConfidence")
    suggested_endpoint: str = Field(alias="suggestedEndpoint")
    next_action: str = Field(alias="nextAction")
    context: "AgentContextResponse"
    result: dict[str, Any]


class AgentSessionRequest(CamelModel):
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    market: str = "HK"
    raw_note: str = Field(alias="rawNote")
    auto_commit: bool = False
    current_state: str = Field(default="normal", alias="currentState")
    focus: str = ""
    trading_mode: str | None = Field(default=None, alias="tradingMode")
    agent_note: str = Field(default="", alias="agentNote")
    suspected_distortions: list[str] = Field(default_factory=list, alias="suspectedDistortions")


class AgentSessionResponse(ActionResponse):
    intent: str
    intent_confidence: float = Field(alias="intentConfidence")
    next_action: str = Field(alias="nextAction")
    auto_committed: bool = Field(alias="autoCommitted")
    context: "AgentContextResponse"
    workflow: dict[str, Any]


class AgentCommitRequest(CamelModel):
    intent: str
    trade_date: str = Field(default="", alias="tradeDate")
    market: str = "HK"
    fields: dict[str, Any] = Field(default_factory=dict)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    raw_note: str = Field(default="", alias="rawNote")
    agent_note: str = Field(default="", alias="agentNote")
    current_state: str = Field(default="normal", alias="currentState")
    focus: str = ""
    trading_mode: str | None = Field(default=None, alias="tradingMode")
    suspected_distortions: list[str] = Field(default_factory=list, alias="suspectedDistortions")


class AgentCommitResponse(ActionResponse):
    committed: bool
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    missing_labels: list[str] = Field(default_factory=list, alias="missingLabels")
    feedback_messages: list[str] = Field(default_factory=list, alias="feedbackMessages")
    day: DailyRecordResponse | None = None
    auto_event_id: str = Field(default="", alias="autoEventId")
    target_trade_id: str = Field(default="", alias="targetTradeId")
    rule_hits: list[AgentRuleHit] = Field(default_factory=list, alias="ruleHits")
    knowledge_routes: list[AgentKnowledgeRoute] = Field(default_factory=list, alias="knowledgeRoutes")


class AgentContextTodayResponse(CamelModel):
    date: str
    market: str
    session_status: str = Field(alias="sessionStatus")
    session_label: str = Field(alias="sessionLabel")
    trading_mode: str = Field(alias="tradingMode")
    main_direction: str = Field(alias="mainDirection")
    plan_summary: str = Field(alias="planSummary")
    intraday_pnl: float | None = Field(default=None, alias="intradayPnl")
    trades_done: int = Field(alias="tradesDone")
    violations_today: int = Field(alias="violationsToday")
    review_done: bool = Field(alias="reviewDone")
    validation_done: bool = Field(alias="validationDone")
    next_action: str = Field(alias="nextAction")


class AgentContextRecentPatternsResponse(CamelModel):
    top_distortions: list[str] = Field(default_factory=list, alias="topDistortions")
    high_risk_contexts: list[str] = Field(default_factory=list, alias="highRiskContexts")
    weekly_focus: str = Field(alias="weeklyFocus")
    recent_issue: str = Field(default="", alias="recentIssue")
    recent_fix: str = Field(default="", alias="recentFix")


class AgentContextStageResponse(CamelModel):
    current_stage: str = Field(alias="currentStage")
    stage_label: str = Field(alias="stageLabel")
    progress: int
    stage_description: str = Field(alias="stageDescription")


class AgentContextResponse(CamelModel):
    today: AgentContextTodayResponse
    recent_patterns: AgentContextRecentPatternsResponse = Field(alias="recentPatterns")
    stage: AgentContextStageResponse


class StartDayRequest(CamelModel):
    day_number: int | None = Field(default=None, alias="dayNumber")
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), alias="tradeDate")
    current_state: str = Field(default="normal", alias="currentState")
    focus: str = ""
    trading_mode: str = Field(default="hsi_bull_bear_certificate", alias="tradingMode")


class ReviewHubPreferenceRequest(CamelModel):
    window: str
    sample_filter: str = Field(alias="sampleFilter")


class CurrentDayRequest(CamelModel):
    day_number: int = Field(alias="dayNumber")


class CurrentMarketRequest(CamelModel):
    market: str


class ThemePreferenceRequest(CamelModel):
    theme: str


class DayKeyRequest(CamelModel):
    trade_date: str = Field(alias="tradeDate")
    market: str


class CurrentRecordRequest(CamelModel):
    trade_date: str = Field(alias="tradeDate")
    market: str


class WorkbenchWriteRequest(CamelModel):
    trading_today: bool = Field(default=True, alias="tradingToday")
    pre_market_state: str = Field(default="normal", alias="preMarketState")
    follow_normal_rules: bool = Field(default=True, alias="followNormalRules")
    key_reminder: str = Field(default="", alias="keyReminder")
    pre_market_note: str = Field(default="", alias="preMarketNote")
    trading_mode: str = Field(alias="tradingMode")
    main_direction: str = Field(alias="mainDirection")
    current_state: str = Field(alias="currentState")
    upper_pressure: str = Field(default="", alias="upperPressure")
    lower_support: str = Field(default="", alias="lowerSupport")
    pivot_level: str = Field(default="", alias="pivotLevel")
    post_market_summary: str = Field(default="", alias="postMarketSummary")
    capital_used: float | None = Field(default=None, alias="capitalUsed")
    profit_target_pct: float | None = Field(default=None, alias="profitTargetPct")
    hk_watchlist: str = Field(default="", alias="hkWatchlist")
    us_watchlist: str = Field(default="", alias="usWatchlist")
    playbook_preset: str = Field(default="", alias="playbookPreset")
    opening_plan: str = Field(default="", alias="openingPlan")
    focus_setup: str = Field(default="", alias="focusSetup")
    open_30_key_signal: str = Field(default="", alias="open30KeySignal")
    certificate_filter_note: str = Field(default="", alias="certificateFilterNote")
    abnormal_plan: str = Field(default="", alias="abnormalPlan")
    option_playbook_preset: str = Field(default="", alias="optionPlaybookPreset")
    option_session_plan: str = Field(default="", alias="optionSessionPlan")
    focus_tickers: str = Field(default="", alias="focusTickers")
    option_focus_setup: str = Field(default="", alias="optionFocusSetup")
    option_entry_signal: str = Field(default="", alias="optionEntrySignal")
    option_contract_filter: str = Field(default="", alias="optionContractFilter")
    option_risk_plan: str = Field(default="", alias="optionRiskPlan")
    option_event_risk_plan: str = Field(default="", alias="optionEventRiskPlan")


class TradeWriteRequest(CamelModel):
    trade_time: str = Field(default="", alias="tradeTime")
    session_window: str = Field(alias="sessionWindow")
    direction: str
    certificate_side: str = Field(alias="certificateSide")
    instrument_code: str = Field(alias="instrumentCode")
    setup_type: str = Field(alias="setupType")
    abc_grade: str = Field(alias="abcGrade")
    direction_clear: bool = Field(alias="directionClear")
    location_ok: bool = Field(alias="locationOk")
    confirmation_ok: bool = Field(alias="confirmationOk")
    risk_clear: bool = Field(alias="riskClear")
    certificate_filter_passed: bool = Field(alias="certificateFilterPassed")
    entry_price: float = Field(alias="entryPrice")
    stop_loss: float = Field(alias="stopLoss")
    position_size: str = Field(alias="positionSize")
    followed_plan: bool = Field(default=True, alias="followedPlan")
    rule_violation: bool = Field(default=False, alias="ruleViolation")
    result: str | None = None
    entry_reason: str = Field(alias="entryReason")
    instrument_type: str = Field(alias="instrumentType")
    underlying: str
    abnormal_scenario: str = Field(default="none", alias="abnormalScenario")
    auto_rule_event: bool = Field(default=True, alias="autoRuleEvent")
    post_trade_emotion: str = Field(default="unset", alias="postTradeEmotion")
    setup_score: float | None = Field(default=None, alias="setupScore")
    setup_validated: bool | None = Field(default=None, alias="setupValidated")
    target_price: float | None = Field(default=None, alias="targetPrice")
    exit_time: str = Field(default="", alias="exitTime")
    exit_price: float | None = Field(default=None, alias="exitPrice")
    pnl_amount: float | None = Field(default=None, alias="pnlAmount")
    risk_reward_ratio: float | None = Field(default=None, alias="riskRewardRatio")
    exit_reason: str = Field(default="", alias="exitReason")
    emotion_state: str = Field(default="", alias="emotionState")
    pre_trade_emotion: str = Field(default="", alias="preTradeEmotion")
    violation_note: str = Field(default="", alias="violationNote")
    screenshot_note: str = Field(default="", alias="screenshotNote")
    review_note: str = Field(default="", alias="reviewNote")


class RuleEventWriteRequest(CamelModel):
    event_time: str = Field(alias="eventTime")
    event_type: str = Field(alias="eventType")
    severity: str
    trigger_reason: str = Field(alias="triggerReason")
    action_taken: str = Field(alias="actionTaken")
    follow_up_note: str = Field(default="", alias="followUpNote")
    linked_trade_id: str = Field(default="", alias="linkedTradeId")


class AgentObservationWriteRequest(CamelModel):
    observation_id: str = Field(default="", alias="observationId")
    linked_trade_id: str = Field(default="", alias="linkedTradeId")
    linked_event_id: str = Field(default="", alias="linkedEventId")
    observation_type: str = Field(alias="observationType")
    severity: str = "info"
    source: str = "agent_question"
    summary: str
    evidence: str = ""
    user_response: str = Field(default="", alias="userResponse")
    status: str = "open"
    review_required: bool = Field(default=False, alias="reviewRequired")


class RuleEventPresetRequest(CamelModel):
    preset_key: str = Field(alias="presetKey")


class ReviewWriteRequest(CamelModel):
    pnl: str
    trade_count: int = Field(alias="tradeCount")
    best_trade_note: str = Field(alias="bestTradeNote")
    worst_trade_note: str = Field(alias="worstTradeNote")
    execution_issue: str = Field(alias="executionIssue")
    emotion_issue: str = Field(alias="emotionIssue")
    risk_issue: str = Field(alias="riskIssue")
    next_day_one_fix: str = Field(alias="nextDayOneFix")
    win_rate: str = Field(default="", alias="winRate")
    max_loss_trade: str = Field(default="", alias="maxLossTrade")
    market_issue: str = Field(default="", alias="marketIssue")
    setup_issue: str = Field(default="", alias="setupIssue")


class ValidationWriteRequest(CamelModel):
    pre_market_done: bool = Field(alias="preMarketDone")
    intraday_record_complete: bool = Field(alias="intradayRecordComplete")
    post_market_review_done: bool = Field(alias="postMarketReviewDone")
    impulsive_trade_detected: bool = Field(default=False, alias="impulsiveTradeDetected")
    no_stop_loss_trade_detected: bool = Field(default=False, alias="noStopLossTradeDetected")
    emotional_overtrade_detected: bool = Field(default=False, alias="emotionalOvertradeDetected")
    no_trade_day: bool = Field(default=False, alias="noTradeDay")
    no_trade_note: str = Field(default="", alias="noTradeNote")
    main_issue_of_day: str = Field(default="", alias="mainIssueOfDay")
    main_improvement_of_day: str = Field(default="", alias="mainImprovementOfDay")


class AcceptanceReviewWriteRequest(CamelModel):
    pnl: str | None = None
    trade_count: int | None = Field(default=None, alias="tradeCount")
    best_trade_note: str | None = Field(default=None, alias="bestTradeNote")
    worst_trade_note: str | None = Field(default=None, alias="worstTradeNote")
    execution_issue: str | None = Field(default=None, alias="executionIssue")
    emotion_issue: str | None = Field(default=None, alias="emotionIssue")
    risk_issue: str | None = Field(default=None, alias="riskIssue")
    next_day_one_fix: str | None = Field(default=None, alias="nextDayOneFix")
    win_rate: str | None = Field(default=None, alias="winRate")
    max_loss_trade: str | None = Field(default=None, alias="maxLossTrade")
    market_issue: str | None = Field(default=None, alias="marketIssue")
    setup_issue: str | None = Field(default=None, alias="setupIssue")
    pre_market_done: bool | None = Field(default=None, alias="preMarketDone")
    intraday_record_complete: bool | None = Field(default=None, alias="intradayRecordComplete")
    post_market_review_done: bool | None = Field(default=None, alias="postMarketReviewDone")
    impulsive_trade_detected: bool | None = Field(default=None, alias="impulsiveTradeDetected")
    no_stop_loss_trade_detected: bool | None = Field(default=None, alias="noStopLossTradeDetected")
    emotional_overtrade_detected: bool | None = Field(default=None, alias="emotionalOvertradeDetected")
    no_trade_day: bool | None = Field(default=None, alias="noTradeDay")
    no_trade_note: str | None = Field(default=None, alias="noTradeNote")
    main_issue_of_day: str | None = Field(default=None, alias="mainIssueOfDay")
    main_improvement_of_day: str | None = Field(default=None, alias="mainImprovementOfDay")


class SyncReviewNumbersRequest(CamelModel):
    after_action: str = Field(default="", alias="afterAction")


class CloseoutGenerateRequest(CamelModel):
    regenerate: bool = False


class ArtifactGenerateRequest(CamelModel):
    regenerate: bool = False


class WorkbenchByKeyRequest(DayKeyRequest, WorkbenchWriteRequest):
    pass


class TradeByKeyRequest(DayKeyRequest, TradeWriteRequest):
    pass


class AgentTradeOpenRequest(TradeByKeyRequest):
    raw_note: str = Field(default="", alias="rawNote")
    agent_note: str = Field(default="", alias="agentNote")
    suspected_distortions: list[str] = Field(default_factory=list, alias="suspectedDistortions")


class RuleEventByKeyRequest(DayKeyRequest, RuleEventWriteRequest):
    pass


class AgentObservationByKeyRequest(DayKeyRequest, AgentObservationWriteRequest):
    pass


class RuleEventPresetByKeyRequest(DayKeyRequest, RuleEventPresetRequest):
    pass


class ReviewByKeyRequest(DayKeyRequest, ReviewWriteRequest):
    pass


class ValidationByKeyRequest(DayKeyRequest, ValidationWriteRequest):
    pass


class SyncReviewNumbersByKeyRequest(DayKeyRequest, SyncReviewNumbersRequest):
    pass


class AcceptanceReviewByKeyRequest(DayKeyRequest, AcceptanceReviewWriteRequest):
    pass


class CloseoutByKeyRequest(DayKeyRequest, CloseoutGenerateRequest):
    pass


def form_scalar(value: Any) -> str:
    """把单个值序列化为 form 字符串。布尔值转为 'true'/'false'。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def model_to_form(payload: BaseModel) -> dict[str, list[str]]:
    """适配器：把 Pydantic 模型转为 local_web.* 函数期望的 form-dict 格式。

    历史原因：local_web.py 的所有写函数最初设计为接收 HTTP form 数据
    （dict[str, list[str]]），现在通过此函数把 JSON payload 适配过去。

    TODO(Phase 3)：逐步改造 local_web 的各写函数接受普通 dict，
    届时可删除此适配器。
    """
    raw = payload.model_dump(exclude_none=True, by_alias=False)
    return {key: [form_scalar(value)] for key, value in raw.items()}


def dict_to_form(raw: dict[str, Any]) -> dict[str, list[str]]:
    """适配器：把普通 dict 转为 local_web.* 函数期望的 form-dict 格式。

    TODO(Phase 3)：同 model_to_form，届时可删除。
    """
    return {key: [form_scalar(value)] for key, value in raw.items() if value is not None}


def normalize_alias_value(value: Any, valid_values: set[str], aliases: dict[str, str], raw_note: str = "") -> Any:
    text = shared_clean_text(value)
    if not text:
        return value
    if text in valid_values:
        return text
    haystack = f"{text} {raw_note}".lower()
    for alias, normalized in aliases.items():
        if alias.lower() in haystack:
            return normalized
    return value


def normalize_agent_commit_fields(intent: str, fields: dict[str, Any], raw_note: str = "") -> dict[str, Any]:
    normalized = {**fields}
    if intent == "open_trade":
        if "setupType" in normalized or "setup_type" in normalized:
            key = "setupType" if "setupType" in normalized else "setup_type"
            normalized[key] = normalize_alias_value(
                normalized.get(key),
                set(local_web.SETUP_OPTIONS),
                SETUP_VALUE_ALIASES,
                raw_note,
            )
        if "emotionState" in normalized or "emotion_state" in normalized:
            key = "emotionState" if "emotionState" in normalized else "emotion_state"
            normalized[key] = normalize_alias_value(
                normalized.get(key),
                set(local_web.EMOTION_OPTIONS),
                EMOTION_STATE_ALIASES,
                raw_note,
            )
        if "preTradeEmotion" in normalized or "pre_trade_emotion" in normalized:
            key = "preTradeEmotion" if "preTradeEmotion" in normalized else "pre_trade_emotion"
            normalized[key] = normalize_alias_value(
                normalized.get(key),
                set(local_web.PRE_TRADE_EMOTION_OPTIONS),
                PRE_TRADE_EMOTION_ALIASES,
                raw_note,
            )
    if intent == "close_trade" and ("postTradeEmotion" in normalized or "post_trade_emotion" in normalized):
        key = "postTradeEmotion" if "postTradeEmotion" in normalized else "post_trade_emotion"
        normalized[key] = normalize_alias_value(
            normalized.get(key),
            set(local_web.POST_TRADE_EMOTION_OPTIONS),
            POST_TRADE_EMOTION_ALIASES,
            "",
        )
    return normalized


def normalize_trade_updates(trade: dict[str, Any]) -> dict[str, Any]:
    normalized = {**trade}
    normalized["trade_time"] = local_web.normalize_trade_clock(normalized.get("trade_time"), "trade_time")
    normalized["exit_time"] = local_web.normalize_trade_clock(normalized.get("exit_time"), "exit_time")

    exit_price = shared_to_float(normalized.get("exit_price"))
    if exit_price is not None:
        position_size_value = shared_to_float(normalized.get("position_size"))
        if position_size_value is None:
            raise bad_request("要自动计算盈亏，请把仓位填写为数字数量。")
        normalized["exit_price"] = exit_price
        normalized["pnl_amount"] = local_web.calculate_trade_pnl_amount(
            shared_clean_text(normalized.get("direction")),
            normalized.get("entry_price"),
            exit_price,
            position_size_value,
        )
        normalized["result"] = local_web.infer_trade_result(
            shared_clean_text(normalized.get("direction")),
            normalized.get("entry_price"),
            exit_price,
        )
    else:
        normalized.pop("exit_price", None)
        normalized.pop("pnl_amount", None)
        normalized.pop("result", None)

    if not normalized.get("exit_time"):
        normalized.pop("exit_time", None)

    return normalized


def latest_day_number() -> int | None:
    records = dal.get_recent_records(limit=1)
    if not records:
        return None
    return int(records[0]["trial_day_number"])


def preferred_day_number(reference_date: date | None = None) -> int | None:
    target_date = (reference_date or date.today()).isoformat()
    exact_match = dal.get_latest_day_number_for_trade_date(target_date)
    if exact_match is not None:
        return exact_match

    on_or_before = dal.get_latest_day_number_on_or_before(target_date)
    if on_or_before is not None:
        return on_or_before

    return latest_day_number()


def day_label(day_number: int) -> str:
    record = dal.get_daily_record(day_number)
    if record:
        trade_date = shared_clean_text(record["base"].get("trade_date"))
        if trade_date:
            return trade_date
    return f"编号 {day_number}"


def ensure_latest_day(day_number: int) -> None:
    preferred = preferred_day_number()
    if preferred is not None and day_number != preferred:
        raise bad_request(f"历史交易日只读。当前只允许修改当日交易日 {day_label(preferred)}。")


def trade_currency(trade: dict[str, Any], *, trading_mode: str = "", market: str = "") -> str:
    instrument_type = shared_clean_text(trade.get("instrument_type"))
    certificate_side = shared_clean_text(trade.get("certificate_side"))
    resolved_mode = shared_clean_text(trading_mode)
    resolved_market = shared_clean_text(trade.get("market")) or market
    if (
        resolved_mode == "us_stock_options"
        or resolved_market == "US"
        or instrument_type == "stock_option"
        or certificate_side in {"call", "put"}
    ):
        return "USD"
    return "HKD"


def money_to_hkd(value: Any, currency: str) -> float | None:
    amount = shared_to_float(value)
    if amount is None:
        return None
    if currency == "USD":
        amount *= USD_HKD_RATE
    return round(amount, 2)


def enrich_trade_money(trade: dict[str, Any], *, trading_mode: str, market: str) -> dict[str, Any]:
    currency = trade_currency(trade, trading_mode=trading_mode, market=market)
    return {
        **trade,
        "currency": currency,
        "pnl_amount_hkd": money_to_hkd(trade.get("pnl_amount"), currency),
    }


def snapshot_pnl_to_hkd(snapshot: dict[str, Any]) -> float | None:
    currency = (
        "USD"
        if shared_clean_text(snapshot.get("trading_mode")) == "us_stock_options"
        or shared_clean_text(snapshot.get("market")) == "US"
        else "HKD"
    )
    return money_to_hkd(snapshot.get("pnl_value"), currency)


def not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def require_latest_day(day_number: int) -> int:
    """FastAPI 依赖项：确保 day_number 是最新交易日，否则抛 400。

    用法：在路由函数签名里加 day_number: int = Depends(require_latest_day)
    注意：FastAPI 会把路径参数 {day_number} 自动传给这里。
    """
    ensure_latest_day(day_number)
    return day_number


def _compute_closeout_label(item: dict[str, Any]) -> str:
    source_path = shared_clean_text(item.get("source_record_path"))
    try:
        record_path = workspace_state.resolve_path(source_path, root=local_web.ROOT)
    except Exception:
        return "否"
    if not record_path.exists():
        return "否"
    exists, legacy, stale = local_web.closeout_status_for_record(
        record_path,
        {
            "day_number": item.get("trial_day_number"),
            "trade_date": item.get("trade_date"),
        },
    )
    return local_web.closeout_status_label(exists=exists, legacy=legacy, stale=stale)


def recent_record_item_from_db(
    item: dict[str, Any],
    *,
    current_record_path: Path | None,
    closeout_label: str = "否",
) -> RecentRecordItem:
    source_path = shared_clean_text(item.get("source_record_path"))
    try:
        record_path = workspace_state.resolve_path(source_path, root=local_web.ROOT)
    except Exception:
        record_path = None
    is_current = bool(
        current_record_path
        and source_path
        and record_path
        and record_path.resolve() == current_record_path.resolve()
    )
    return RecentRecordItem(
        day_number=int(item["trial_day_number"] or 0),
        trade_date=shared_clean_text(item["trade_date"]),
        market=shared_clean_text(item["market"]),
        primary_instrument=shared_clean_text(item["primary_instrument"]),
        trading_mode=shared_clean_text(item["trading_mode"]),
        current_state=shared_clean_text(item["current_state"]),
        trade_count=int(item["trade_count"]),
        review_done=bool(item["review_done"]),
        validation_done=bool(item["validation_done"]),
        source_record_path=source_path,
        closeout_label=closeout_label,
        is_current=is_current,
    )


def artifact_item_from_path(path: Path) -> ArtifactItem:
    return ArtifactItem(
        title=local_web.markdown_title(path),
        path=workspace_state.relative_path(path, root=local_web.ROOT),
    )


def artifact_preview_from_path(path: Path | None) -> ArtifactPreviewResponse:
    if path is None:
        return ArtifactPreviewResponse(path="", title="", exists=False, preview="")
    return artifact_preview(path)


def resolve_market_record(
    *,
    market: str,
    preferred_trade_date: str,
) -> tuple[str, dict[str, Any] | None]:
    normalized_market = shared_clean_text(market) or "HK"
    resolved_trade_date = shared_clean_text(preferred_trade_date) or date.today().isoformat()
    record = dal.get_daily_record_by_date_market(resolved_trade_date, normalized_market)
    if record:
        return resolved_trade_date, record
    fallback = dal.get_latest_record_for_market(normalized_market)
    if not fallback:
        return resolved_trade_date, None
    fallback_trade_date = shared_clean_text(fallback["base"].get("trade_date")) or resolved_trade_date
    return fallback_trade_date, fallback


def latest_open_record_for_market(market: str) -> tuple[str, dict[str, Any] | None]:
    normalized_market = shared_clean_text(market).upper() or "HK"
    for item in dal.get_recent_records_for_market(normalized_market, limit=32):
        trade_date = shared_clean_text(item.get("trade_date"))
        if not trade_date:
            continue
        record = dal.get_daily_record_by_date_market(trade_date, normalized_market)
        if record and any(not trade.get("exit_time") and trade.get("exit_price") is None for trade in record.get("trades", [])):
            return trade_date, record
    return "", None


def resolve_agent_commit_trade_date(intent: str, trade_date: str, market: str) -> str:
    normalized_date = shared_clean_text(trade_date)
    if normalized_date:
        return normalized_date
    normalized_market = shared_clean_text(market).upper() or "HK"
    normalized_intent = shared_clean_text(intent)
    if normalized_intent == "open_trade":
        return date.today().isoformat()
    if normalized_intent == "close_trade":
        open_date, _ = latest_open_record_for_market(normalized_market)
        if open_date:
            return open_date
    latest_record = dal.get_latest_record_for_market(normalized_market)
    if latest_record:
        return shared_clean_text(latest_record["base"].get("trade_date")) or date.today().isoformat()
    return date.today().isoformat()


def sync_local_state_from_record(record: dict[str, Any]) -> None:
    source_path = shared_clean_text(record.get("source_record_path"))
    if not source_path:
        return
    try:
        record_path = workspace_state.resolve_path(source_path, root=local_web.ROOT)
        if not record_path.exists():
            return
        state = local_web.load_state()
        workspace_state.update_state_from_record(
            state=state,
            path=record_path,
            record=record,
            closeout_path_from_base=local_web.closeout_path_from_base,
            relative_path_func=lambda path: workspace_state.relative_path(path, root=local_web.ROOT),
        )
        local_web.save_state(state)
    except Exception:
        return


def build_state_response() -> AppStateResponse:
    local_web.ensure_sqlite_ready()
    workspace = dal.get_workspace_state()
    state = local_web.load_state()
    current_market = shared_clean_text(workspace.get("current_market")) or "HK"
    preferred_trade_date = shared_clean_text(workspace.get("current_trade_date")) or shared_clean_text(state.trade_date) or date.today().isoformat()
    current_trade_date, current_market_record = resolve_market_record(
        market=current_market,
        preferred_trade_date=preferred_trade_date,
    )
    if current_market_record and current_trade_date != preferred_trade_date:
        dal.save_workspace_state(current_market=current_market, current_trade_date=current_trade_date)
    current_record_path = workspace_state.current_record_path(state, root=local_web.ROOT)
    today_trade_date = date.today().isoformat()
    today_records = {
        "HK": dal.get_daily_record_by_date_market(today_trade_date, "HK") is not None,
        "US": dal.get_daily_record_by_date_market(today_trade_date, "US") is not None,
    }
    if current_market_record:
        source_record_path = shared_clean_text(current_market_record.get("source_record_path"))
        if source_record_path:
            try:
                market_record_path = workspace_state.resolve_path(source_record_path, root=local_web.ROOT)
                if market_record_path.exists():
                    if not current_record_path or current_record_path.resolve() != market_record_path.resolve():
                        sync_local_state_from_record(current_market_record)
                    current_record_path = market_record_path
            except Exception:
                pass
    db_records = dal.get_recent_records_for_market(current_market, limit=8)
    recent_records = [
        recent_record_item_from_db(
            item,
            current_record_path=current_record_path,
            closeout_label=_compute_closeout_label(item),
        )
        for item in db_records
    ]
    recent_closeouts = [
        artifact_item_from_path(path)
        for path in local_web.find_recent_files(local_web.CLOSEOUTS_DIR, "*.md")
    ]
    recent_summaries = [
        artifact_item_from_path(path)
        for path in local_web.find_recent_files(local_web.SUMMARIES_DIR, "*summary*.md")
    ]
    recent_audits = [
        artifact_item_from_path(path)
        for path in local_web.find_recent_files(local_web.SUMMARIES_DIR, "*audit*.md")
    ]
    return AppStateResponse(
        current_market=current_market,
        current_day_number=workspace_state.parse_day_number(state.day),
        current_trade_date=current_trade_date,
        current_record_path=shared_clean_text(current_market_record.get("source_record_path")) if current_market_record else "",
        current_closeout_path=shared_clean_text(state.current_closeout_path),
        current_summary_path=shared_clean_text(state.current_summary_path),
        current_audit_path=shared_clean_text(state.current_audit_path),
        theme=shared_clean_text(workspace.get("theme")) or "dark",
        today_records=today_records,
        review_hub_window=state.review_hub_window,
        review_hub_sample_filter=state.review_hub_sample_filter,
        recent_records=recent_records,
        recent_closeouts=recent_closeouts,
        recent_summaries=recent_summaries,
        recent_audits=recent_audits,
        usd_hkd_rate=USD_HKD_RATE,
    )


def build_day_diagnostics_response(record: dict[str, Any], record_path: Path) -> DayDiagnosticsResponse:
    state = local_web.load_state()
    current_record_path = workspace_state.current_record_path(state, root=local_web.ROOT)
    record_editable = bool(current_record_path and record_path.resolve() == current_record_path.resolve())
    closeout = build_closeout_payload(record_path)
    todo_items = [
        TodoItemResponse(text=text, target=target)
        for text, target in local_web.build_todo_items(
            record_path=record_path,
            record_editable=record_editable,
            workbench=record["workbench"],
            playbook=record["playbook"],
            trades=record["trades"],
            events=record["events"],
            review=record["review"],
            validation=record["validation"],
            closeout_exists=closeout.exists,
            closeout_legacy=closeout.legacy,
            closeout_stale=closeout.stale,
        )
    ]
    workflow_steps = [
        WorkflowStepResponse(label=label, note=note, target=target, done=done)
        for label, note, target, done in local_web.build_workflow_steps(
            record_path=record_path,
            workbench=record["workbench"],
            trades=record["trades"],
            events=record["events"],
            review=record["review"],
            validation=record["validation"],
            closeout_exists=closeout.exists,
            closeout_legacy=closeout.legacy,
            closeout_stale=closeout.stale,
        )
    ]
    record_health_items = [
        HealthItemResponse(level=level, text=text, target=target)
        for level, text, target in local_web.build_record_health_items(
            record_path=record_path,
            record_editable=record_editable,
            workbench=record["workbench"],
            playbook=record["playbook"],
            trades=record["trades"],
            events=record["events"],
            review=record["review"],
            validation=record["validation"],
            closeout_exists=closeout.exists,
            closeout_legacy=closeout.legacy,
            closeout_stale=closeout.stale,
        )
    ]
    trading_mode = local_web.normalize_trading_mode(record["workbench"].get("trading_mode"))
    decision_gate = trading_policy.build_decision_gate(
        workbench=record["workbench"],
        playbook=record["playbook"],
        events=record["events"],
        trading_mode=trading_mode,
        display_value=local_web.display_value,
        field_label=local_web.field_label,
    )
    risk_state = trading_policy.build_risk_state(
        workbench=record["workbench"],
        trades=record["trades"],
        events=record["events"],
        trading_mode=trading_mode,
        filter_label=local_web.filter_label_for_mode(trading_mode),
        format_number=local_web.format_number,
    )
    execution_lock = trading_policy.build_execution_lock(decision_gate, risk_state)
    day_summary = local_web.build_day_summary(record["workbench"], record["trades"])
    review_defaults = local_web.build_review_defaults(record["review"], record["trades"])
    previous_context = local_web.previous_record_context(
        record_path,
        [workspace_state.resolve_path(shared_clean_text(item["source_record_path"]), root=local_web.ROOT) for item in dal.get_recent_records(limit=32)],
    )
    return DayDiagnosticsResponse(
        todo_items=todo_items,
        workflow_steps=workflow_steps,
        record_health_items=record_health_items,
        decision_gate=DecisionStatusResponse(**decision_gate),
        risk_state=RiskStatusResponse(**risk_state),
        execution_lock=ExecutionLockResponse(**execution_lock),
        day_summary=DaySummaryResponse(**day_summary),
        review_defaults=ReviewDefaultsResponse(**review_defaults),
        previous_context=PreviousContextResponse(**previous_context),
    )


def build_workspace_overview_response() -> WorkspaceOverviewResponse:
    state = build_state_response()
    if not state.current_record_path:
        return WorkspaceOverviewResponse(state=state, current_day=None, diagnostics=None)
    record_path = workspace_state.resolve_path(state.current_record_path, root=local_web.ROOT)
    record = local_web.load_record_db_first(record_path)
    return WorkspaceOverviewResponse(
        state=state,
        current_day=build_daily_record_response_from_record(record, record_path),
        diagnostics=build_day_diagnostics_response(record, record_path),
    )


def build_artifacts_overview_response() -> ArtifactsOverviewResponse:
    state = build_state_response()
    loaded_state = local_web.load_state()
    current_closeout_path = workspace_state.current_closeout_path(loaded_state, root=local_web.ROOT)
    current_summary_path = workspace_state.current_summary_path(loaded_state, root=local_web.ROOT) or local_web.expected_trial_summary_path()
    current_audit_path = workspace_state.current_audit_path(loaded_state, root=local_web.ROOT) or local_web.expected_field_audit_path()
    return ArtifactsOverviewResponse(
        current_closeout=artifact_preview_from_path(current_closeout_path),
        current_summary=artifact_preview_from_path(current_summary_path),
        current_audit=artifact_preview_from_path(current_audit_path),
        recent_closeouts=state.recent_closeouts,
        recent_summaries=state.recent_summaries,
        recent_audits=state.recent_audits,
    )


def build_history_overview_response(
    window: str | None = None,
    sample_filter: str | None = None,
) -> HistoryOverviewResponse:
    state = local_web.load_state()
    workspace = dal.get_workspace_state()
    current_market = shared_clean_text(workspace.get("current_market")) or "HK"
    resolved_window = local_web.normalize_review_hub_window(window or state.review_hub_window)
    resolved_filter = local_web.normalize_review_hub_sample_filter(sample_filter or state.review_hub_sample_filter)
    return HistoryOverviewResponse(
        window=resolved_window,
        sample_filter=resolved_filter,
        stats=build_review_hub_stats_response(resolved_window, resolved_filter, current_market),
        days=build_review_hub_day_rows_response(resolved_window, resolved_filter, current_market),
    )


def get_record_path_for_day(day_number: int) -> Path:
    local_web.ensure_sqlite_ready()
    record = dal.get_daily_record(day_number)
    if not record:
        raise not_found(f"找不到该日期对应的交易记录。")
    source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        raise not_found(f"该交易日缺少 source_record_path。")
    path = workspace_state.resolve_path(source_record_path, root=local_web.ROOT)
    if not path.exists():
        raise not_found(f"找不到记录文件：{source_record_path}")
    return path


def get_file_record_for_day(day_number: int) -> tuple[Path, dict[str, Any]]:
    path = get_record_path_for_day(day_number)
    return path, record_io.load_record(path)


def get_file_record_for_key(trade_date: str, market: str) -> tuple[Path, dict[str, Any], int]:
    record = dal.get_daily_record_by_date_market(trade_date, market)
    if not record:
        raise not_found(f"找不到 {trade_date} 的{ '港股' if market == 'HK' else '美股' }工作台。")
    day_number = int(record["base"]["day_number"] or 0)
    source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        fallback_path = local_web.RECORDS_DIR / f"{trade_date}-{market}-record-container.md"
        if not fallback_path.exists():
            raise not_found("目标工作台缺少记录路径。")
        fallback_record = record_io.load_record(fallback_path)
        local_web.save_record_bundle_dual_write(
            fallback_path,
            fallback_record,
            fallback_path.read_text(encoding="utf-8"),
        )
        repaired = dal.get_daily_record_by_date_market(trade_date, market)
        if repaired:
            record = repaired
            day_number = int(record["base"]["day_number"] or day_number or 0)
            source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        raise not_found("目标工作台缺少记录路径。")
    path = workspace_state.resolve_path(source_record_path, root=local_web.ROOT)
    if not path.exists():
        raise not_found(f"找不到记录文件：{source_record_path}")
    return path, record_io.load_record(path), day_number


def market_to_trading_mode(market: str, instrument_type: str = "") -> str:
    normalized_market = shared_clean_text(market).upper()
    normalized_type = shared_clean_text(instrument_type)
    if normalized_market == "US" or normalized_type == "stock_option":
        return "us_stock_options"
    return "hsi_bull_bear_certificate"


def ensure_day_record_for_key(
    trade_date: str,
    market: str,
    *,
    trading_mode: str,
    current_state: str = "normal",
    focus: str = "",
) -> tuple[Path, dict[str, Any], int]:
    try:
        return get_file_record_for_key(trade_date, market)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    create_or_load_day(
        StartDayRequest(
            tradeDate=trade_date,
            currentState=current_state,
            focus=focus,
            tradingMode=trading_mode,
        )
    )
    return get_file_record_for_key(trade_date, market)


def build_closeout_payload(record_path: Path, *, preview_override: str = "") -> CloseoutPayload:
    record = local_web.load_record_db_first(record_path)
    base = record["base"]
    closeout_path = local_web.closeout_path_from_base(base)
    exists, legacy, stale = local_web.closeout_status_for_record(record_path, base)
    preview = preview_override
    if not preview and closeout_path.exists():
        preview = closeout_path.read_text(encoding="utf-8")
    return CloseoutPayload(
        path=workspace_state.relative_path(closeout_path, root=local_web.ROOT) if closeout_path.exists() else "",
        exists=exists,
        legacy=legacy,
        stale=stale,
        preview=preview,
    )


def build_closeout_payload_from_output(output_path: Path, *, preview: str = "") -> CloseoutPayload:
    exists = output_path.exists()
    final_preview = preview or (output_path.read_text(encoding="utf-8") if exists else "")
    legacy = local_web.is_legacy_english_closeout(final_preview) if final_preview else False
    return CloseoutPayload(
        path=workspace_state.relative_path(output_path, root=local_web.ROOT) if exists else "",
        exists=exists,
        legacy=legacy,
        stale=False,
        preview=final_preview,
    )


def build_daily_record_response_from_record(record: dict[str, Any], record_path: Path) -> DailyRecordResponse:
    state = local_web.load_state()
    current_record_path = workspace_state.current_record_path(state, root=local_web.ROOT)
    is_current = bool(current_record_path and record_path.resolve() == current_record_path.resolve())
    trading_mode = shared_clean_text(record["workbench"].get("trading_mode"))
    market = shared_clean_text(record["base"].get("market"))
    trades = [
        enrich_trade_money(trade, trading_mode=trading_mode, market=market)
        for trade in record["trades"]
    ]
    return DailyRecordResponse(
        source_record_path=workspace_state.relative_path(record_path, root=local_web.ROOT),
        is_current=is_current,
        base=camelize_keys(record["base"]),
        pre_market=camelize_keys(record["pre_market"]),
        workbench=camelize_keys(record["workbench"]),
        playbook=camelize_keys(record["playbook"]),
        trades=camelize_keys(trades),
        events=camelize_keys(record["events"]),
        observations=camelize_keys(record.get("observations", [])),
        review=camelize_keys(record["review"]),
        validation=camelize_keys(record["validation"]),
        closeout=build_closeout_payload(record_path),
    )


def build_daily_record_response(day_number: int) -> DailyRecordResponse:
    record = dal.get_daily_record(day_number)
    if not record:
        raise not_found("找不到该日期对应的交易记录。")
    record_path = workspace_state.resolve_path(shared_clean_text(record["source_record_path"]), root=local_web.ROOT)
    return build_daily_record_response_from_record(record, record_path)


def build_daily_record_response_from_path(source_path: str) -> DailyRecordResponse:
    clean_path = shared_clean_text(source_path)
    if not clean_path:
        raise bad_request("缺少记录路径。")
    record_path = workspace_state.resolve_path(clean_path, root=local_web.ROOT)
    try:
        record_path.resolve().relative_to(local_web.RECORDS_DIR.resolve())
    except ValueError as exc:
        raise bad_request("记录路径必须位于交易记录目录。") from exc
    if not record_path.exists():
        raise not_found(f"找不到记录文件：{clean_path}")
    record = dal.get_daily_record_by_source_path(workspace_state.relative_path(record_path, root=local_web.ROOT))
    if not record:
        record = local_web.load_record_db_first(record_path)
    return build_daily_record_response_from_record(record, record_path)


def build_daily_record_response_by_key(trade_date: str, market: str) -> DailyRecordResponse:
    record = dal.get_daily_record_by_date_market(trade_date, market)
    if not record:
        raise not_found(f"找不到 {trade_date} 的{ '港股' if market == 'HK' else '美股' }工作台。")
    source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        raise not_found("目标工作台缺少记录路径。")
    record_path = workspace_state.resolve_path(source_record_path, root=local_web.ROOT)
    return build_daily_record_response_from_record(record, record_path)


def update_current_day_state(record_path: Path, record: dict[str, Any]) -> AppStateResponse:
    state = local_web.load_state()
    market = shared_clean_text(record["base"].get("market")) or "HK"
    trade_date = shared_clean_text(record["base"].get("trade_date")) or date.today().isoformat()
    dal.save_workspace_state(current_market=market, current_trade_date=trade_date)
    workspace_state.update_state_from_record(
        state=state,
        path=record_path,
        record=record,
        closeout_path_from_base=local_web.closeout_path_from_base,
        relative_path_func=lambda path: workspace_state.relative_path(path, root=local_web.ROOT),
    )
    local_web.save_state(state)
    return build_state_response()


def count_item(label: str, count: int) -> CountItem:
    return CountItem(label=label, count=count)


def timeline_note_from_item(item: dict[str, Any], key: str) -> TimelineNote:
    return TimelineNote(
        day_number=int(item["trial_day_number"]),
        trade_date=shared_clean_text(item["trade_date"]),
        note=shared_clean_text(item[key]),
    )


def build_review_hub_stats_response(window: str, sample_filter: str, market: str | None = None) -> ReviewHubStatsResponse:
    limit_days = local_web.review_hub_window_limit(window)
    filter_trusted = sample_filter == "trusted"
    stats = dal.get_review_hub_stats(limit_days=limit_days, filter_trusted=filter_trusted, market=market)
    state = local_web.load_state()
    current_record_path = workspace_state.current_record_path(state, root=local_web.ROOT)
    rows = []
    for snapshot in dal.get_review_hub_day_rows(limit_days=limit_days, filter_trusted=filter_trusted, market=market):
        enriched = local_web.enrich_review_hub_snapshot_from_sqlite(snapshot, current_record_path=current_record_path)
        enriched["pnl_value"] = snapshot_pnl_to_hkd(enriched)
        rows.append(enriched)
    closeout_synced_days = sum(1 for row in rows if row["closeout_synced"])
    pnl_values = [row["pnl_value"] for row in rows if row["pnl_value"] is not None]
    total_pnl = round(sum(pnl_values), 2) if pnl_values else None
    avg_daily_pnl = round(total_pnl / len(pnl_values), 2) if total_pnl is not None and pnl_values else None
    plan_follow_rate = None
    if stats["followed_total"] > 0:
        plan_follow_rate = stats["followed_yes"] / stats["followed_total"] * 100
    return ReviewHubStatsResponse(
        day_count=stats["day_count"],
        trade_day_count=stats["trade_day_count"],
        no_trade_day_count=stats["no_trade_day_count"],
        total_pnl=total_pnl,
        avg_daily_pnl=avg_daily_pnl,
        trade_count=stats["trade_count"],
        violation_count=stats["violation_count"],
        review_done_days=stats["review_done_days"],
        validation_done_days=stats["validation_done_days"],
        closeout_synced_days=closeout_synced_days,
        followed_yes=stats["followed_yes"],
        followed_total=stats["followed_total"],
        plan_follow_rate=plan_follow_rate,
        win_count=stats["win_count"],
        loss_count=stats["loss_count"],
        breakeven_count=stats["breakeven_count"],
        impulsive_days=stats["impulsive_days"],
        stop_loss_days=stats["stop_loss_days"],
        overtrade_days=stats["overtrade_days"],
        opening_30_trade_count=stats["opening_30_trade_count"],
        phase2_check_fail_count=stats["phase2_check_fail_count"],
        certificate_filter_fail_count=stats["certificate_filter_fail_count"],
        abnormal_trade_count=stats["abnormal_trade_count"],
        top_setups=[count_item(local_web.display_value(item["setup_type"], default=item["setup_type"]), int(item["count"])) for item in stats["top_setups"]],
        top_active_plans=[count_item(local_web.display_value(item["active_plan"], default=item["active_plan"]), int(item["count"])) for item in stats["top_active_plans"]],
        top_active_setups=[count_item(local_web.display_value(item["active_setup"], default=item["active_setup"]), int(item["count"])) for item in stats["top_active_setups"]],
        recent_issues=[timeline_note_from_item(item, "main_issue") for item in stats["recent_issues"]],
        recent_fixes=[timeline_note_from_item(item, "next_fix") for item in stats["recent_fixes"]],
        recent_no_trade_notes=[timeline_note_from_item(item, "no_trade_note") for item in stats["recent_no_trade_notes"]],
    )


def build_review_hub_day_rows_response(window: str, sample_filter: str, market: str | None = None) -> list[ReviewHubDayRowResponse]:
    limit_days = local_web.review_hub_window_limit(window)
    filter_trusted = sample_filter == "trusted"
    state = local_web.load_state()
    current_record_path = workspace_state.current_record_path(state, root=local_web.ROOT)
    rows = []
    for snapshot in dal.get_review_hub_day_rows(limit_days=limit_days, filter_trusted=filter_trusted, market=market):
        enriched = local_web.enrich_review_hub_snapshot_from_sqlite(snapshot, current_record_path=current_record_path)
        enriched["pnl_value"] = snapshot_pnl_to_hkd(enriched)
        rows.append(ReviewHubDayRowResponse(**camelize_keys(enriched)))
    return rows


def infer_top_distortions_from_stats(stats: dict[str, Any], recent_issues: list[dict[str, Any]]) -> list[str]:
    distortions: list[str] = []
    if int(stats.get("impulsive_days") or 0) > 0:
        distortions.append("impulsive_entry")
    if int(stats.get("stop_loss_days") or 0) > 0:
        distortions.append("no_stop_loss")
    if int(stats.get("overtrade_days") or 0) > 0:
        distortions.append("emotional_overtrade")
    issue_text = " ".join(shared_clean_text(item.get("main_issue")) for item in recent_issues).lower()
    if "fomo" in issue_text or "怕错过" in issue_text:
        distortions.append("fomo")
    if "报复" in issue_text or "赚回来" in issue_text or "翻本" in issue_text:
        distortions.append("revenge")
    seen: set[str] = set()
    unique: list[str] = []
    for item in distortions:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:3]


def summarize_plan(record: dict[str, Any]) -> str:
    workbench = record["workbench"]
    playbook = record["playbook"]
    trading_mode = local_web.normalize_trading_mode(workbench.get("trading_mode"))
    main_direction = local_web.display_value(workbench.get("main_direction")) or "未定"
    plan = local_web.display_value(local_web.playbook_plan_value(playbook, trading_mode), default=local_web.playbook_plan_value(playbook, trading_mode)) or "未定"
    setup = local_web.display_value(local_web.playbook_setup_value(playbook, trading_mode), default=local_web.playbook_setup_value(playbook, trading_mode)) or "未定"
    return f"主方向 {main_direction}；主计划 {plan}；主练形态 {setup}"


def build_agent_context_response(*, trade_date: str | None = None, market: str | None = None) -> AgentContextResponse:
    workspace = dal.get_workspace_state()
    resolved_market = shared_clean_text(market or workspace.get("current_market")).upper() or "HK"
    preferred_trade_date = shared_clean_text(trade_date or workspace.get("current_trade_date")) or date.today().isoformat()
    resolved_trade_date, record = resolve_market_record(
        market=resolved_market,
        preferred_trade_date=preferred_trade_date,
    )
    if not record:
        raise not_found(f"当前{ '港股' if resolved_market == 'HK' else '美股' }工作台在 {preferred_trade_date} 尚未创建。")

    source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        raise not_found("当前工作台缺少记录路径。")
    record_path = workspace_state.resolve_path(source_record_path, root=local_web.ROOT)
    closeout = build_closeout_payload(record_path)
    trading_mode = local_web.normalize_trading_mode(record["workbench"].get("trading_mode"))
    decision_gate = trading_policy.build_decision_gate(
        workbench=record["workbench"],
        playbook=record["playbook"],
        events=record["events"],
        trading_mode=trading_mode,
        display_value=local_web.display_value,
        field_label=local_web.field_label,
    )
    risk_state = trading_policy.build_risk_state(
        workbench=record["workbench"],
        trades=record["trades"],
        events=record["events"],
        trading_mode=trading_mode,
        filter_label=local_web.filter_label_for_mode(trading_mode),
        format_number=local_web.format_number,
    )
    stage = local_web.current_workflow_stage(
        record_path=record_path,
        record_editable=True,
        workbench=record["workbench"],
        playbook=record["playbook"],
        trades=record["trades"],
        events=record["events"],
        review=record["review"],
        validation=record["validation"],
        closeout_exists=closeout.exists,
        closeout_legacy=closeout.legacy,
        closeout_stale=closeout.stale,
    )
    stats = dal.get_review_hub_stats(limit_days=10, filter_trusted=False, market=resolved_market)
    recent_issues = stats.get("recent_issues", [])
    recent_fixes = stats.get("recent_fixes", [])
    top_distortions = infer_top_distortions_from_stats(stats, recent_issues)
    high_risk_contexts = [
        shared_clean_text(item.get("main_issue"))
        for item in recent_issues
        if shared_clean_text(item.get("main_issue"))
    ][:3]
    weekly_focus = (
        shared_clean_text(recent_fixes[0].get("next_fix"))
        if recent_fixes
        else shared_clean_text(record["review"].get("next_day_one_fix"))
        or shared_clean_text(record["validation"].get("main_improvement_of_day"))
        or "先把交易事实和纪律执行说清楚。"
    )
    next_action = shared_clean_text(risk_state.get("action")) or shared_clean_text(decision_gate.get("action")) or stage.get("note", "")
    violation_count = sum(1 for trade in record["trades"] if trade.get("rule_violation") is True)

    return AgentContextResponse(
        today=AgentContextTodayResponse(
            date=resolved_trade_date,
            market=resolved_market,
            sessionStatus=shared_clean_text(stage.get("key")) or "setup",
            sessionLabel=shared_clean_text(stage.get("label")) or "未开始",
            tradingMode=trading_mode,
            mainDirection=shared_clean_text(record["workbench"].get("main_direction")) or "undecided",
            planSummary=summarize_plan(record),
            intradayPnl=risk_state.get("pnl_total"),
            tradesDone=len(record["trades"]),
            violationsToday=violation_count,
            reviewDone=local_web.is_review_done(record["review"]),
            validationDone=local_web.is_validation_done(record["validation"]),
            nextAction=next_action,
        ),
        recentPatterns=AgentContextRecentPatternsResponse(
            topDistortions=top_distortions,
            highRiskContexts=high_risk_contexts,
            weeklyFocus=weekly_focus,
            recentIssue=shared_clean_text(recent_issues[0].get("main_issue")) if recent_issues else "",
            recentFix=shared_clean_text(recent_fixes[0].get("next_fix")) if recent_fixes else "",
        ),
        stage=AgentContextStageResponse(
            currentStage=shared_clean_text(stage.get("key")) or "setup",
            stageLabel=shared_clean_text(stage.get("label")) or "未开始",
            progress=int(stage.get("progress") or 0),
            stageDescription=shared_clean_text(stage.get("note")) or "",
        ),
    )


def validate_trade_dict(trade: dict[str, Any]) -> None:
    for required_key in ["instrument_code", "entry_reason", "position_size"]:
        if not local_web.clean_text(trade.get(required_key)):
            raise bad_request(f"请填写{local_web.field_label(required_key)}。")
    result = local_web.clean_text(trade.get("result"))
    if result and result not in local_web.RESULT_OPTIONS:
        raise bad_request("结果无效。")
    if trade["emotion_state"] and trade["emotion_state"] not in local_web.EMOTION_OPTIONS:
        raise bad_request("情绪状态无效。")
    if trade["pre_trade_emotion"] and trade["pre_trade_emotion"] not in local_web.PRE_TRADE_EMOTION_OPTIONS:
        raise bad_request("开仓前情绪无效。")
    if trade["post_trade_emotion"] and trade["post_trade_emotion"] not in local_web.POST_TRADE_EMOTION_OPTIONS:
        raise bad_request("平仓后情绪无效。")
    if trade["instrument_type"] not in local_web.INSTRUMENT_TYPE_OPTIONS:
        raise bad_request("工具类型无效。")
    if trade["underlying"] not in local_web.UNDERLYING_OPTIONS:
        raise bad_request("底层标的无效。")


def validate_rule_event_dict(event: dict[str, Any]) -> None:
    for required_key in ["time", "trigger_reason", "action_taken"]:
        if not local_web.clean_text(event.get(required_key)):
            label_key = "event_time" if required_key == "time" else required_key
            raise bad_request(f"请填写{local_web.field_label(label_key)}。")
    if local_web.clean_text(event.get("event_type")) not in local_web.EVENT_TYPE_OPTIONS:
        raise bad_request("纪律事件类型无效。")
    if local_web.clean_text(event.get("severity")) not in local_web.SEVERITY_OPTIONS:
        raise bad_request("纪律事件级别无效。")


def preview_agent_open_feedback(
    proposal: dict[str, Any],
    *,
    raw_note: str = "",
    agent_note: str = "",
    suspected_distortions: list[str] | None = None,
) -> tuple[list[AgentRuleHit], list[AgentKnowledgeRoute]]:
    hits = [
        AgentRuleHit(**hit)
        for hit in agent_policy.build_rule_hits_for_trade(proposal)
    ]
    routes = [
        AgentKnowledgeRoute(**route)
        for route in agent_policy.build_knowledge_routes_for_trade(
            trade=proposal,
            raw_note=raw_note,
            agent_note=agent_note,
            suspected_distortions=suspected_distortions,
        )
    ]
    return hits, routes


def allowed_trade_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        key: raw[key]
        for key in TradeWriteRequest.model_fields
        if key in raw
    }


def missing_label_for_trade_field(key: str) -> str:
    if key == "trade_id":
        return "交易编号"
    return local_web.field_label(key)


def missing_labels_for_fields(fields: list[str]) -> list[str]:
    return [missing_label_for_trade_field(field) for field in fields]


def canonical_agent_field_name(name: str) -> str:
    for model_cls in [TradeWriteRequest, RuleEventWriteRequest, ReviewWriteRequest]:
        for field_name, field_info in model_cls.model_fields.items():
            if name in {field_name, str(field_info.alias)}:
                return field_name
    if name == "tradeId":
        return "trade_id"
    return name


def validation_missing_fields(exc: ValidationError) -> list[str]:
    missing: list[str] = []
    for error in exc.errors():
        if error.get("type") != "missing":
            continue
        loc = error.get("loc") or []
        if not loc:
            continue
        missing.append(canonical_agent_field_name(str(loc[-1])))
    return dedupe_strings(missing)


def build_not_written_feedback(missing_fields: list[str]) -> list[str]:
    if "stop_loss" in missing_fields:
        return ["这笔还没有写入；止损缺口需要补止损价或失效条件，不是当前是否已经触发止损。"]
    if missing_fields:
        labels = "、".join(missing_labels_for_fields(prioritize_missing_fields(missing_fields))[:3])
        return [f"这笔还没有写入；优先补：{labels}。"]
    return ["这笔还没有写入。"]


def build_commit_feedback(
    *,
    intent: str,
    day: DailyRecordResponse | None,
    auto_event_id: str = "",
) -> list[str]:
    feedback: list[str] = []
    session_status = shared_clean_text((day.base if day else {}).get("session_status"))
    if day and intent in {"open_trade", "close_trade"} and session_status in {"review", "closeout", "done"}:
        feedback.append("当前处在盘后阶段，本次按补录盘中交易处理。")
    if auto_event_id:
        feedback.append(f"{auto_event_id} 是自动风险复核提醒，不是否定当前交易；下一笔前重新确认方向、位置、确认、风险和工具过滤。")
    severe_events = [event for event in (day.events if day else []) if shared_clean_text(event.get("severity")) in {"stop", "critical"}]
    if severe_events:
        feedback.append("检测到 stop/critical 纪律事件：现在停止新开仓；如有持仓，只处理平仓和风控，并先复述违规原因和下一步动作。")
    return dedupe_strings(feedback)


def agent_commit_not_written(message: str, missing_fields: list[str]) -> AgentCommitResponse:
    return AgentCommitResponse(
        message=message,
        committed=False,
        missingFields=missing_fields,
        missingLabels=missing_labels_for_fields(missing_fields),
        feedbackMessages=build_not_written_feedback(missing_fields),
    )


def build_open_intake_follow_up_questions(
    proposal: dict[str, Any],
    missing_fields: list[str],
    context: AgentContextResponse,
) -> list[str]:
    prompts: list[str] = []
    lowered_note = shared_clean_text(proposal.get("entry_reason")).lower()
    prompt_map = {
        "trade_time": "这笔准备在几点开仓？请给我 HH:MM。",
        "session_window": "这是开盘 30 分钟、中段，还是尾盘的机会？",
        "direction": "这笔是做多还是做空？",
        "certificate_side": "如果是牛熊证，请明确是牛证还是熊证；如果是期权，请说是 call 还是 put。",
        "instrument_code": "请补一下具体的标的代码。",
        "setup_type": "这笔属于什么形态？例如开盘突破、回踩确认、假突破追单。",
        "abc_grade": "这笔你判断是 A、B 还是 C 级？",
        "entry_price": "请补开仓价。",
        "stop_loss": "请明确止损价或失效条件；我需要的是价位/条件，不是当前是否已经触发止损。",
        "position_size": "请补仓位数量。",
        "underlying": "请补底层标的，例如 HSI、TSLA、NVDA。",
    }
    for field in prioritize_missing_fields(missing_fields):
        if field in prompt_map:
            prompts.append(prompt_map[field])

    if "stop_loss" in missing_fields and any(token in lowered_note for token in ["止损清楚", "没出现止损", "没有出现止损"]):
        prompts.insert(0, "我需要的是止损价或失效条件，不是当前是否已经触发止损。")
    if shared_clean_text(context.today.session_status) in {"review", "closeout", "done"}:
        prompts.append("当前系统已经处在盘后阶段，确认这是一笔补录开仓，而不是今天的新开仓。")
    if "fomo" in [shared_clean_text(item) for item in context.recent_patterns.top_distortions]:
        prompts.append("最近高频问题里有 FOMO，这笔是否存在怕错过或追单情绪？")
    if not proposal.get("risk_clear"):
        prompts.append("先把止损和反证条件说完整，再决定是否允许提交。")

    return prioritize_follow_up_questions(dedupe_strings(prompts), missing_fields)[:3]


def build_close_intake_follow_up_questions(
    proposal: dict[str, Any],
    missing_fields: list[str],
    context: AgentContextResponse,
    *,
    open_trade_count: int,
    needs_trade_id: bool,
) -> list[str]:
    prompts: list[str] = []
    prompt_map = {
        "trade_id": "请明确要平的是哪一笔交易编号。",
        "exit_time": "请补平仓时间，格式用 HH:MM。",
        "exit_price": "请补平仓价。",
        "exit_reason": "请补平仓原因，是止损、止盈，还是保本退出？",
    }
    for field in missing_fields:
        if field in prompt_map:
            prompts.append(prompt_map[field])

    if needs_trade_id and open_trade_count > 1:
        prompts.append("今天有多笔未平仓交易，请先说清要平哪一笔。")
    if shared_clean_text(context.today.session_status) in {"pre_market", "intraday"}:
        prompts.append("当前系统仍在盘中阶段，确认这笔是真的已经平仓，而不是提前写盘后结论。")
    return prioritize_follow_up_questions(dedupe_strings(prompts), missing_fields)[:3]


CORE_OPEN_MISSING_FIELDS = {
    "trade_time",
    "instrument_code",
    "entry_price",
    "position_size",
    "stop_loss",
}
QUALITY_OPEN_MISSING_FIELDS = {
    "setup_type",
    "direction",
    "certificate_side",
    "session_window",
    "direction_clear",
    "location_ok",
    "confirmation_ok",
    "risk_clear",
    "certificate_filter_passed",
    "abc_grade",
}


def prioritize_missing_fields(missing_fields: list[str]) -> list[str]:
    core = [field for field in missing_fields if field in CORE_OPEN_MISSING_FIELDS]
    quality = [field for field in missing_fields if field in QUALITY_OPEN_MISSING_FIELDS]
    rest = [field for field in missing_fields if field not in CORE_OPEN_MISSING_FIELDS and field not in QUALITY_OPEN_MISSING_FIELDS]
    return [*core, *quality, *rest]


def prioritize_follow_up_questions(prompts: list[str], missing_fields: list[str]) -> list[str]:
    if not missing_fields:
        return prompts
    prioritized_fields = prioritize_missing_fields(missing_fields)
    ordered: list[str] = []
    for field in prioritized_fields:
        label = local_web.field_label(field)
        ordered.extend(prompt for prompt in prompts if label in prompt or field in prompt)
    ordered.extend(prompt for prompt in prompts if prompt not in ordered)
    return dedupe_strings(ordered)


def dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        text = shared_clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def resolve_close_target_trade(record: dict[str, Any], requested_trade_id: str = "") -> tuple[dict[str, Any] | None, bool]:
    normalized_trade_id = shared_clean_text(requested_trade_id)
    open_trades = [trade for trade in record["trades"] if not trade.get("exit_time") and trade.get("exit_price") is None]
    if normalized_trade_id:
        for trade in record["trades"]:
            if shared_clean_text(trade.get("trade_id")) == normalized_trade_id:
                return trade, False
        return None, False
    if len(open_trades) == 1:
        return open_trades[0], False
    return None, len(open_trades) != 1


def build_agent_close_preview(trade: dict[str, Any], close_updates: dict[str, Any]) -> tuple[float | None, str]:
    merged = normalize_trade_updates({**trade, **close_updates})
    return shared_to_float(merged.get("pnl_amount")), shared_clean_text(merged.get("result"))


def write_agent_close_trade(
    *,
    record_path: Path,
    record: dict[str, Any],
    trade: dict[str, Any],
    close_updates: dict[str, Any],
    trade_date: str,
    market: str,
) -> DailyRecordResponse:
    merged = {
        **trade,
        **close_updates,
        "review_note": "\n".join(
            item
            for item in [
                shared_clean_text(trade.get("review_note")),
                shared_clean_text(close_updates.get("review_note")),
            ]
            if item
        ),
    }
    payload = TradeWriteRequest.model_validate(allowed_trade_payload(merged))
    mutate_trade_record(record_path, record, shared_clean_text(trade.get("trade_id")), payload)
    return build_daily_record_response_by_key(trade_date, market)


def build_rule_event_intake_follow_up_questions(
    proposal: dict[str, Any],
    missing_fields: list[str],
    context: AgentContextResponse,
) -> list[str]:
    prompts: list[str] = []
    prompt_map = {
        "event_time": "请补纪律事件发生时间，格式用 HH:MM。",
        "event_type": "这是违规、情绪触发、暂停信号，还是停手事件？",
        "severity": "这次是 warning、stop，还是 critical？",
        "trigger_reason": "请说清这次为什么触发纪律事件。",
        "action_taken": "这次你具体采取了什么动作？例如暂停、停手、复述理由。",
    }
    for field in missing_fields:
        if field in prompt_map:
            prompts.append(prompt_map[field])
    if "revenge" in [shared_clean_text(item) for item in context.recent_patterns.top_distortions]:
        prompts.append("最近高频问题里有 revenge，确认这次是否与亏损后想赚回来有关。")
    return dedupe_strings(prompts)[:4]


def build_review_intake_follow_up_questions(
    proposal: dict[str, Any],
    missing_fields: list[str],
    context: AgentContextResponse,
) -> list[str]:
    prompts: list[str] = []
    prompt_map = {
        "best_trade_note": "请补一句今天最好的一笔或最好动作。",
        "worst_trade_note": "请补一句今天最差的一笔或最差问题。",
        "execution_issue": "请单独说清执行问题。",
        "emotion_issue": "请单独说清情绪问题。",
        "risk_issue": "请单独说清风控问题。",
        "next_day_one_fix": "请说清明天只改哪一件事。",
    }
    for field in missing_fields:
        if field in prompt_map:
            prompts.append(prompt_map[field])
    if shared_clean_text(context.today.session_status) in {"pre_market", "intraday"}:
        prompts.append("当前系统还没进入盘后阶段，确认你现在是在做正式复盘，而不是盘中备注。")
    if shared_clean_text(context.recent_patterns.weekly_focus):
        prompts.append(f"本周焦点是：{context.recent_patterns.weekly_focus}")
    return dedupe_strings(prompts)[:4]


def write_agent_rule_event(
    *,
    record_path: Path,
    record: dict[str, Any],
    proposal: dict[str, Any],
    trade_date: str,
    market: str,
) -> tuple[DailyRecordResponse, str]:
    event_id = local_web.add_rule_event(record_path, dict_to_form(proposal))
    updated_record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, updated_record)
    day = build_daily_record_response_by_key(trade_date, market)
    if event_id and not any(shared_clean_text(event.get("event_id") or event.get("eventId")) == event_id for event in response_to_dict(day).get("events", [])):
        raise bad_request("纪律事件写入后读回失败，未确认持久化。")
    return day, event_id


def write_agent_review(
    *,
    record_path: Path,
    record: dict[str, Any],
    proposal: dict[str, Any],
    trade_date: str,
    market: str,
) -> DailyRecordResponse:
    defaults = local_web.build_review_defaults(record["review"], record["trades"])
    payload = {
        "pnl": defaults["pnl"],
        "trade_count": int(defaults["trade_count"] or 0),
        "best_trade_note": proposal.get("best_trade_note", ""),
        "worst_trade_note": proposal.get("worst_trade_note", ""),
        "execution_issue": proposal.get("execution_issue", ""),
        "emotion_issue": proposal.get("emotion_issue", ""),
        "risk_issue": proposal.get("risk_issue", ""),
        "next_day_one_fix": proposal.get("next_day_one_fix", ""),
        "win_rate": proposal.get("win_rate", ""),
        "max_loss_trade": proposal.get("max_loss_trade", ""),
        "market_issue": proposal.get("market_issue", ""),
        "setup_issue": proposal.get("setup_issue", ""),
    }
    local_web.save_review(record_path, dict_to_form(payload))
    updated_record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, updated_record)
    return build_daily_record_response_by_key(trade_date, market)


def response_to_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=True)


def latest_trade_id(day: DailyRecordResponse | None) -> str:
    if day is None:
        return ""
    trades = response_to_dict(day).get("trades", [])
    if not trades:
        return ""
    return shared_clean_text(trades[-1].get("tradeId") or trades[-1].get("trade_id"))


def persist_agent_observations(
    observations: list[dict[str, Any]],
    *,
    trade_date: str,
    market: str,
    default_linked_trade_id: str = "",
    default_linked_event_id: str = "",
) -> None:
    if not observations:
        return
    record = dal.get_daily_record_by_date_market(trade_date, market)
    if not record:
        raise bad_request("找不到目标工作台，未写入 Agent observation。")
    source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        raise bad_request("目标工作台缺少记录路径，未写入 Agent observation。")
    existing_count = len(record.get("observations", []))
    for index, raw_observation in enumerate(observations, start=existing_count + 1):
        try:
            payload = AgentObservationByKeyRequest.model_validate(
                {
                    **raw_observation,
                    "tradeDate": trade_date,
                    "market": market,
                    "linkedTradeId": raw_observation.get("linkedTradeId")
                    or raw_observation.get("linked_trade_id")
                    or default_linked_trade_id,
                    "linkedEventId": raw_observation.get("linkedEventId")
                    or raw_observation.get("linked_event_id")
                    or default_linked_event_id,
                }
            )
        except ValidationError as exc:
            missing = ", ".join(validation_missing_fields(exc)) or "observation"
            raise bad_request(f"Agent observation 字段不完整，未写入：{missing}") from exc
        dal.insert_agent_observation(
            {
                **payload.model_dump(by_alias=False),
                "source_record_path": source_record_path,
                "source_order": index,
            }
        )


def model_input_subset(model_cls: type[BaseModel], raw: dict[str, Any]) -> dict[str, Any]:
    return {
        key: raw[key]
        for key in model_cls.model_fields
        if key in raw
    }


def workflow_intent_confidence(intent: str, raw_note: str) -> float:
    lowered = shared_clean_text(raw_note).lower()
    if intent == "open_trade":
        return 0.86 if any(token in lowered for token in ["开仓", "牛证", "熊证", "call", "put", "做多", "做空"]) else 0.68
    if intent == "close_trade":
        return 0.9 if any(token in lowered for token in ["平仓", "出场", "止盈", "止损离场"]) else 0.7
    if intent == "rule_event":
        return 0.88 if any(token in lowered for token in ["停手", "暂停", "违规", "报复", "情绪"]) else 0.7
    if intent == "review":
        return 0.9 if any(token in lowered for token in ["复盘", "执行问题", "情绪问题", "明天只改"]) else 0.72
    return 0.25


def workflow_next_action(intent: str, result: dict[str, Any], context: AgentContextResponse) -> str:
    follow_ups = result.get("followUpQuestions") or []
    if follow_ups:
        return shared_clean_text(follow_ups[0]) or shared_clean_text(context.today.next_action)
    if result.get("committed") is True:
        return "已写入系统，下一步继续口述后续动作或进入盘后复盘。"
    if intent == "unknown":
        return "先明确这段口述属于开仓、平仓、纪律事件还是复盘。"
    return shared_clean_text(context.today.next_action) or "继续补齐缺失字段。"


def write_agent_open_trade(payload: AgentTradeOpenRequest) -> AgentTradeOpenResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, _ = get_file_record_for_key(payload.trade_date, market)
    normalized_payload = normalize_trade_updates(payload.model_dump(exclude_none=True, by_alias=False))
    raw_note = shared_clean_text(payload.raw_note)
    agent_note = shared_clean_text(payload.agent_note)
    review_notes = [shared_clean_text(normalized_payload.get("review_note"))]
    if raw_note:
        review_notes.append(f"Agent原始口述：{raw_note}")
    if agent_note:
        review_notes.append(f"Agent处理备注：{agent_note}")
    normalized_payload["review_note"] = "\n".join(note for note in review_notes if note)

    auto_event_id = local_web.add_trade(record_path, dict_to_form(normalized_payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    created_trade = record["trades"][-1] if record["trades"] else normalized_payload
    message = "Agent 开仓记录已写入。"
    if auto_event_id:
        message += f" 已联动纪律事件：{auto_event_id}。"
    rule_hits, knowledge_routes = preview_agent_open_feedback(
        created_trade,
        raw_note=payload.raw_note,
        agent_note=payload.agent_note,
        suspected_distortions=payload.suspected_distortions,
    )
    return AgentTradeOpenResponse(
        message=message,
        day=build_daily_record_response_by_key(payload.trade_date, market),
        auto_event_id=auto_event_id,
        rule_hits=rule_hits,
        knowledge_routes=knowledge_routes,
    )


def commit_open_trade(payload: AgentCommitRequest, trade_date: str, market: str) -> AgentCommitResponse:
    trading_mode = shared_clean_text(payload.trading_mode) or market_to_trading_mode(
        market,
        shared_clean_text(payload.fields.get("instrumentType") or payload.fields.get("instrument_type")),
    )
    try:
        trade_payload = AgentTradeOpenRequest.model_validate(
            {
                **payload.fields,
                "tradeDate": trade_date,
                "market": market,
                "rawNote": payload.raw_note,
                "agentNote": payload.agent_note,
                "suspectedDistortions": payload.suspected_distortions,
            }
        )
    except ValidationError as exc:
        return agent_commit_not_written("结构化开仓字段还不够，未写入。", validation_missing_fields(exc))

    ensure_day_record_for_key(
        trade_date,
        market,
        trading_mode=trading_mode,
        current_state=payload.current_state,
        focus=payload.focus,
    )
    committed = write_agent_open_trade(trade_payload)
    created_trade_id = latest_trade_id(committed.day)
    persist_agent_observations(
        payload.observations,
        trade_date=trade_date,
        market=market,
        default_linked_trade_id=created_trade_id,
        default_linked_event_id=committed.auto_event_id,
    )
    day = build_daily_record_response_by_key(trade_date, market)
    return AgentCommitResponse(
        message=committed.message,
        committed=True,
        day=day,
        autoEventId=committed.auto_event_id,
        ruleHits=committed.rule_hits,
        knowledgeRoutes=committed.knowledge_routes,
        feedbackMessages=build_commit_feedback(intent="open_trade", day=day, auto_event_id=committed.auto_event_id),
    )


def commit_close_trade(payload: AgentCommitRequest, trade_date: str, market: str) -> AgentCommitResponse:
    try:
        record_path, record, _ = get_file_record_for_key(trade_date, market)
    except HTTPException:
        return agent_commit_not_written(f"找不到 {trade_date} 的{ '港股' if market == 'HK' else '美股' }工作台，未写入平仓。", ["trade_id"])

    requested_trade_id = shared_clean_text(payload.fields.get("tradeId") or payload.fields.get("trade_id"))
    target_trade, needs_trade_id = resolve_close_target_trade(record, requested_trade_id)
    missing_fields: list[str] = []
    if needs_trade_id:
        missing_fields.append("trade_id")
    for key in ["exitTime", "exitPrice", "exitReason"]:
        value = payload.fields.get(key)
        if value in {"", None}:
            missing_fields.append(canonical_agent_field_name(key))
    if requested_trade_id and target_trade is None:
        return agent_commit_not_written(f"找不到交易：{requested_trade_id}，未写入平仓。", ["trade_id"])
    if target_trade is None:
        return agent_commit_not_written("没有可自动匹配的未平仓交易，未写入平仓。", missing_fields or ["trade_id"])
    if missing_fields:
        return agent_commit_not_written("结构化平仓字段还不够，未写入。", dedupe_strings(missing_fields))

    close_updates = {
        "trade_id": requested_trade_id,
        "exit_time": payload.fields.get("exitTime") or payload.fields.get("exit_time"),
        "exit_price": payload.fields.get("exitPrice") or payload.fields.get("exit_price"),
        "exit_reason": payload.fields.get("exitReason") or payload.fields.get("exit_reason"),
        "post_trade_emotion": payload.fields.get("postTradeEmotion") or payload.fields.get("post_trade_emotion") or "unset",
        "review_note": "\n".join(
            item
            for item in [
                f"Agent原始口述：{shared_clean_text(payload.raw_note)}" if shared_clean_text(payload.raw_note) else "",
                f"Agent处理备注：{shared_clean_text(payload.agent_note)}" if shared_clean_text(payload.agent_note) else "",
            ]
            if item
        ),
    }
    if "ruleViolation" in payload.fields or "rule_violation" in payload.fields:
        close_updates["rule_violation"] = payload.fields.get("ruleViolation") if "ruleViolation" in payload.fields else payload.fields.get("rule_violation")
    if "violationNote" in payload.fields or "violation_note" in payload.fields:
        close_updates["violation_note"] = payload.fields.get("violationNote") or payload.fields.get("violation_note") or ""
    day = write_agent_close_trade(
        record_path=record_path,
        record=record,
        trade=target_trade,
        close_updates=close_updates,
        trade_date=trade_date,
        market=market,
    )
    target_trade_id = shared_clean_text(target_trade.get("trade_id"))
    persist_agent_observations(
        payload.observations,
        trade_date=trade_date,
        market=market,
        default_linked_trade_id=target_trade_id,
    )
    day = build_daily_record_response_by_key(trade_date, market)
    return AgentCommitResponse(
        message="Agent 平仓记录已写入。",
        committed=True,
        day=day,
        targetTradeId=target_trade_id,
        feedbackMessages=build_commit_feedback(intent="close_trade", day=day),
    )


def commit_rule_event(payload: AgentCommitRequest, trade_date: str, market: str) -> AgentCommitResponse:
    try:
        event_payload = RuleEventByKeyRequest.model_validate(
            {
                **payload.fields,
                "tradeDate": trade_date,
                "market": market,
            }
        )
    except ValidationError as exc:
        return agent_commit_not_written("结构化纪律事件字段还不够，未写入。", validation_missing_fields(exc))

    record_path, record, _ = ensure_day_record_for_key(
        trade_date,
        market,
        trading_mode=market_to_trading_mode(market),
    )
    event_data = event_payload.model_dump(by_alias=False)
    event_data["follow_up_note"] = "\n".join(
        item
        for item in [
            shared_clean_text(event_data.get("follow_up_note")),
            f"Agent原始口述：{shared_clean_text(payload.raw_note)}" if shared_clean_text(payload.raw_note) else "",
            f"Agent处理备注：{shared_clean_text(payload.agent_note)}" if shared_clean_text(payload.agent_note) else "",
        ]
        if item
    )
    day, event_id = write_agent_rule_event(
        record_path=record_path,
        record=record,
        proposal=event_data,
        trade_date=trade_date,
        market=market,
    )
    persist_agent_observations(
        payload.observations,
        trade_date=trade_date,
        market=market,
        default_linked_event_id=event_id,
    )
    day = build_daily_record_response_by_key(trade_date, market)
    return AgentCommitResponse(
        message="Agent 纪律事件已写入。",
        committed=True,
        day=day,
        autoEventId=event_id,
        feedbackMessages=build_commit_feedback(intent="rule_event", day=day, auto_event_id=event_id),
    )


def commit_review(payload: AgentCommitRequest, trade_date: str, market: str) -> AgentCommitResponse:
    required = ["bestTradeNote", "worstTradeNote", "executionIssue", "emotionIssue", "riskIssue", "nextDayOneFix"]
    missing = [canonical_agent_field_name(key) for key in required if payload.fields.get(key) in {"", None}]
    if missing:
        return agent_commit_not_written("结构化复盘字段还不够，未写入。", missing)

    record_path, record, _ = ensure_day_record_for_key(
        trade_date,
        market,
        trading_mode=market_to_trading_mode(market),
    )
    proposal = {
        "best_trade_note": payload.fields.get("bestTradeNote") or payload.fields.get("best_trade_note") or "",
        "worst_trade_note": payload.fields.get("worstTradeNote") or payload.fields.get("worst_trade_note") or "",
        "execution_issue": payload.fields.get("executionIssue") or payload.fields.get("execution_issue") or "",
        "emotion_issue": payload.fields.get("emotionIssue") or payload.fields.get("emotion_issue") or "",
        "risk_issue": payload.fields.get("riskIssue") or payload.fields.get("risk_issue") or "",
        "next_day_one_fix": payload.fields.get("nextDayOneFix") or payload.fields.get("next_day_one_fix") or "",
        "win_rate": payload.fields.get("winRate") or payload.fields.get("win_rate") or "",
        "max_loss_trade": payload.fields.get("maxLossTrade") or payload.fields.get("max_loss_trade") or "",
        "market_issue": payload.fields.get("marketIssue") or payload.fields.get("market_issue") or "",
        "setup_issue": payload.fields.get("setupIssue") or payload.fields.get("setup_issue") or "",
    }
    day = write_agent_review(
        record_path=record_path,
        record=record,
        proposal=proposal,
        trade_date=trade_date,
        market=market,
    )
    persist_agent_observations(payload.observations, trade_date=trade_date, market=market)
    day = build_daily_record_response_by_key(trade_date, market)
    return AgentCommitResponse(
        message="Agent 复盘已写入。",
        committed=True,
        day=day,
        feedbackMessages=build_commit_feedback(intent="review", day=day),
    )


def commit_agent_payload(payload: AgentCommitRequest) -> AgentCommitResponse:
    intent = shared_clean_text(payload.intent)
    if intent not in {"open_trade", "close_trade", "rule_event", "review"}:
        return agent_commit_not_written("未知 intent，未写入。", ["intent"])
    market = shared_clean_text(payload.market).upper() or "HK"
    if market not in {"HK", "US"}:
        return agent_commit_not_written("market 只支持 HK 或 US，未写入。", ["market"])
    payload.fields = normalize_agent_commit_fields(intent, payload.fields, payload.raw_note)
    trade_date = resolve_agent_commit_trade_date(intent, payload.trade_date, market)
    if intent == "open_trade":
        return commit_open_trade(payload, trade_date, market)
    if intent == "close_trade":
        return commit_close_trade(payload, trade_date, market)
    if intent == "rule_event":
        return commit_rule_event(payload, trade_date, market)
    return commit_review(payload, trade_date, market)


def mutate_trade_record(record_path: Path, record: dict[str, Any], trade_id: str, payload: TradeWriteRequest) -> dict[str, Any]:
    trades = list(record["trades"])
    try:
        index = next(index for index, trade in enumerate(trades) if local_web.clean_text(trade.get("trade_id")) == trade_id)
    except StopIteration as exc:
        raise not_found(f"找不到交易：{trade_id}") from exc
    existing = trades[index]
    updates = normalize_trade_updates(payload.model_dump(exclude_none=True, by_alias=False))
    merged = {
        **existing,
        **updates,
        "trade_id": trade_id,
        "trade_date": existing["trade_date"],
        "market": existing["market"],
    }
    validate_trade_dict(merged)
    trades[index] = merged
    content = local_web.write_yaml_section(record["content"], "Trade Record Container", {"trade_records": trades})
    updated_record = {**record, "trades": trades}
    local_web.save_record_bundle_dual_write(record_path, updated_record, content)
    update_current_day_state(record_path, updated_record)
    return updated_record


def mutate_trade(day_number: int, trade_id: str, payload: TradeWriteRequest) -> DailyRecordResponse:
    record_path, record = get_file_record_for_day(day_number)
    mutate_trade_record(record_path, record, trade_id, payload)
    return build_daily_record_response(day_number)


def delete_trade(day_number: int, trade_id: str) -> DailyRecordResponse:
    record_path, record = get_file_record_for_day(day_number)
    trades = [trade for trade in record["trades"] if local_web.clean_text(trade.get("trade_id")) != trade_id]
    if len(trades) == len(record["trades"]):
        raise not_found(f"找不到交易：{trade_id}")
    events = [event for event in record["events"] if local_web.clean_text(event.get("linked_trade_id")) != trade_id]
    content = local_web.write_yaml_section(record["content"], "Trade Record Container", {"trade_records": trades})
    content = local_web.write_yaml_section(content, "Rule Event Container", {"rule_events": events})
    updated_record = {**record, "trades": trades, "events": events}
    local_web.save_record_bundle_dual_write(record_path, updated_record, content)
    update_current_day_state(record_path, updated_record)
    return build_daily_record_response(day_number)


def mutate_rule_event_record(record_path: Path, record: dict[str, Any], event_id: str, payload: RuleEventWriteRequest) -> dict[str, Any]:
    events = list(record["events"])
    try:
        index = next(index for index, event in enumerate(events) if local_web.clean_text(event.get("event_id")) == event_id)
    except StopIteration as exc:
        raise not_found(f"找不到纪律事件：{event_id}") from exc
    existing = events[index]
    merged = {
        **existing,
        "event_id": event_id,
        "date": existing["date"],
        "market": existing["market"],
        "time": local_web.normalize_trade_clock(payload.event_time, "event_time"),
        "event_type": payload.event_type,
        "severity": payload.severity,
        "trigger_reason": payload.trigger_reason,
        "action_taken": payload.action_taken,
        "follow_up_note": payload.follow_up_note,
        "linked_trade_id": payload.linked_trade_id,
    }
    validate_rule_event_dict(merged)
    events[index] = merged
    content = local_web.write_yaml_section(record["content"], "Rule Event Container", {"rule_events": events})
    updated_record = {**record, "events": events}
    local_web.save_record_bundle_dual_write(record_path, updated_record, content)
    update_current_day_state(record_path, updated_record)
    return updated_record


def mutate_rule_event(day_number: int, event_id: str, payload: RuleEventWriteRequest) -> DailyRecordResponse:
    record_path, record = get_file_record_for_day(day_number)
    mutate_rule_event_record(record_path, record, event_id, payload)
    return build_daily_record_response(day_number)


def delete_rule_event_record(record_path: Path, record: dict[str, Any], event_id: str) -> dict[str, Any]:
    events = [event for event in record["events"] if local_web.clean_text(event.get("event_id")) != event_id]
    if len(events) == len(record["events"]):
        raise not_found(f"找不到纪律事件：{event_id}")
    content = local_web.write_yaml_section(record["content"], "Rule Event Container", {"rule_events": events})
    updated_record = {**record, "events": events}
    local_web.save_record_bundle_dual_write(record_path, updated_record, content)
    update_current_day_state(record_path, updated_record)
    return updated_record


def delete_rule_event(day_number: int, event_id: str) -> DailyRecordResponse:
    record_path, record = get_file_record_for_day(day_number)
    delete_rule_event_record(record_path, record, event_id)
    return build_daily_record_response(day_number)


def artifact_preview(path: Path) -> ArtifactPreviewResponse:
    preview = path.read_text(encoding="utf-8") if path.exists() else ""
    return ArtifactPreviewResponse(
        path=local_web.relative_path(path) if path.exists() else "",
        title=local_web.markdown_title(path) if path.exists() else "",
        exists=path.exists(),
        preview=preview,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    local_web.ensure_sqlite_ready()
    yield


app = FastAPI(title="TrendGo API", version=local_web.APP_VERSION, lifespan=lifespan)


@app.exception_handler(ValueError)
async def handle_value_error(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})

FRONTEND_DIST = local_web.ROOT / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"


@app.get("/api/state", response_model=AppStateResponse)
def get_state() -> AppStateResponse:
    return build_state_response()


@app.get("/api/workspace/overview", response_model=WorkspaceOverviewResponse)
def get_workspace_overview() -> WorkspaceOverviewResponse:
    return build_workspace_overview_response()


@app.put("/api/state/review-hub", response_model=StateActionResponse)
def update_review_hub_state(payload: ReviewHubPreferenceRequest) -> StateActionResponse:
    state = local_web.load_state()
    state.review_hub_window = local_web.normalize_review_hub_window(payload.window)
    state.review_hub_sample_filter = local_web.normalize_review_hub_sample_filter(payload.sample_filter)
    local_web.save_state(state)
    return StateActionResponse(message="复盘中心筛选状态已更新。", state=build_state_response())


@app.put("/api/state/current-day", response_model=StateActionResponse)
def switch_current_day(payload: CurrentDayRequest) -> StateActionResponse:
    ensure_latest_day(payload.day_number)
    record_path, record = get_file_record_for_day(payload.day_number)
    state = update_current_day_state(record_path, record)
    return StateActionResponse(message=f"已载入交易日 {day_label(payload.day_number)}。", state=state)


@app.put("/api/state/current-record", response_model=StateActionResponse)
def switch_current_record(payload: CurrentRecordRequest) -> StateActionResponse:
    market = shared_clean_text(payload.market).upper()
    record = dal.get_daily_record_by_date_market(payload.trade_date, market)
    if not record:
        raise not_found(f"找不到 {payload.trade_date} 的{ '港股' if market == 'HK' else '美股' }工作台。")
    source_path = shared_clean_text(record.get("source_record_path"))
    if not source_path:
        raise not_found("目标工作台缺少记录路径。")
    record_path = workspace_state.resolve_path(source_path, root=local_web.ROOT)
    state = update_current_day_state(record_path, record)
    return StateActionResponse(message=f"已载入 {payload.trade_date} 的{ '港股' if market == 'HK' else '美股' }工作台。", state=state)


@app.put("/api/state/current-market", response_model=StateActionResponse)
def switch_current_market(payload: CurrentMarketRequest) -> StateActionResponse:
    market = shared_clean_text(payload.market).upper()
    if market not in {"HK", "US"}:
        raise bad_request("market 只支持 HK 或 US。")
    workspace = dal.save_workspace_state(current_market=market)
    preferred_trade_date = shared_clean_text(workspace.get("current_trade_date")) or date.today().isoformat()
    trade_date, record = resolve_market_record(
        market=market,
        preferred_trade_date=preferred_trade_date,
    )
    if record:
        dal.save_workspace_state(current_market=market, current_trade_date=trade_date)
        sync_local_state_from_record(record)
    return StateActionResponse(message=f"已切换到{ '港股' if market == 'HK' else '美股' }工作台。", state=build_state_response())


@app.put("/api/state/theme", response_model=StateActionResponse)
def switch_theme(payload: ThemePreferenceRequest) -> StateActionResponse:
    theme = shared_clean_text(payload.theme)
    if theme not in {"dark", "light"}:
        raise bad_request("theme 只支持 dark 或 light。")
    dal.save_workspace_state(theme=theme)
    return StateActionResponse(message="主题已更新。", state=build_state_response())


@app.post("/api/days", response_model=DayActionResponse)
def create_or_load_day(payload: StartDayRequest) -> DayActionResponse:
    trade_date = payload.trade_date
    current_state = payload.current_state or "normal"
    focus = payload.focus
    trading_mode = local_web.require_choice(payload.trading_mode, "trading_mode", local_web.TRADING_MODE_OPTIONS)
    record_path, _, created = local_web.run_daily_generator("1", trade_date, current_state, focus, trading_mode)
    record = local_web.load_record(record_path)
    local_web.save_record_bundle_dual_write(record_path, record, record_path.read_text(encoding="utf-8"))
    market = shared_clean_text(record["base"].get("market")) or ("US" if trading_mode == "us_stock_options" else "HK")
    dal.save_workspace_state(current_market=market, current_trade_date=trade_date)
    update_current_day_state(record_path, record)
    message = "已创建交易日。" if created else "交易日已存在，已重新载入。"
    return DayActionResponse(message=message, day=build_daily_record_response_from_record(record, record_path))


@app.get("/api/days/{day_number}", response_model=DailyRecordResponse)
def get_day(day_number: int) -> DailyRecordResponse:
    return build_daily_record_response(day_number)


@app.get("/api/current-trading-day", response_model=DailyRecordResponse)
def get_current_trading_day() -> DailyRecordResponse:
    workspace = dal.get_workspace_state()
    market = shared_clean_text(workspace.get("current_market")) or "HK"
    preferred_trade_date = shared_clean_text(workspace.get("current_trade_date")) or date.today().isoformat()
    trade_date, record = resolve_market_record(
        market=market,
        preferred_trade_date=preferred_trade_date,
    )
    if record and trade_date != preferred_trade_date:
        dal.save_workspace_state(current_market=market, current_trade_date=trade_date)
    if not record:
        raise not_found(f"当前{ '港股' if market == 'HK' else '美股' }工作台在 {trade_date} 尚未创建。")
    source_record_path = shared_clean_text(record.get("source_record_path"))
    if not source_record_path:
        raise not_found("当前工作台缺少记录路径。")
    record_path = workspace_state.resolve_path(source_record_path, root=local_web.ROOT)
    sync_local_state_from_record(record)
    return build_daily_record_response_from_record(record, record_path)


@app.get("/api/agent/context", response_model=AgentContextResponse)
def get_agent_context(
    trade_date: str | None = Query(default=None, alias="tradeDate"),
    market: str | None = Query(default=None),
) -> AgentContextResponse:
    return build_agent_context_response(trade_date=trade_date, market=market)


@app.get("/api/agent/contract")
def get_agent_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "appVersion": local_web.APP_VERSION,
        "agentCommit": True,
        "commitEndpoint": "/api/agent/commit",
        "intents": ["open_trade", "close_trade", "rule_event", "review"],
    }


@app.get("/api/records", response_model=DailyRecordResponse)
def get_record_by_path(path: str = Query(...)) -> DailyRecordResponse:
    return build_daily_record_response_from_path(path)


@app.get("/api/days/{day_number}/diagnostics", response_model=DayDiagnosticsResponse)
def get_day_diagnostics(day_number: int) -> DayDiagnosticsResponse:
    record = dal.get_daily_record(day_number)
    if not record:
        raise not_found("找不到该日期对应的交易记录。")
    record_path = local_web.resolve_path(local_web.clean_text(record["source_record_path"]))
    return build_day_diagnostics_response(record, record_path)


@app.get("/api/review-hub/stats", response_model=ReviewHubStatsResponse)
def get_review_hub_stats(
    window: str | None = Query(default=None),
    sample_filter: str | None = Query(default=None, alias="sampleFilter"),
) -> ReviewHubStatsResponse:
    state = local_web.load_state()
    workspace = dal.get_workspace_state()
    current_market = shared_clean_text(workspace.get("current_market")) or "HK"
    resolved_window = local_web.normalize_review_hub_window(window or state.review_hub_window)
    resolved_filter = local_web.normalize_review_hub_sample_filter(sample_filter or state.review_hub_sample_filter)
    return build_review_hub_stats_response(resolved_window, resolved_filter, current_market)


@app.get("/api/review-hub/days", response_model=list[ReviewHubDayRowResponse])
def get_review_hub_days(
    window: str | None = Query(default=None),
    sample_filter: str | None = Query(default=None, alias="sampleFilter"),
) -> list[ReviewHubDayRowResponse]:
    state = local_web.load_state()
    workspace = dal.get_workspace_state()
    current_market = shared_clean_text(workspace.get("current_market")) or "HK"
    resolved_window = local_web.normalize_review_hub_window(window or state.review_hub_window)
    resolved_filter = local_web.normalize_review_hub_sample_filter(sample_filter or state.review_hub_sample_filter)
    return build_review_hub_day_rows_response(resolved_window, resolved_filter, current_market)


@app.get("/api/history/overview", response_model=HistoryOverviewResponse)
def get_history_overview(
    window: str | None = Query(default=None),
    sample_filter: str | None = Query(default=None, alias="sampleFilter"),
) -> HistoryOverviewResponse:
    return build_history_overview_response(window=window, sample_filter=sample_filter)


@app.get("/api/market/hsi-range/state", response_model=HSIRangeStateResponse)
def get_hsi_range_state() -> HSIRangeStateResponse:
    try:
        return HSIRangeStateResponse(**HSI_RANGE_PROVIDER.state())
    except Exception as exc:
        message = str(exc)
        if isinstance(exc, HSIRangeError):
            message = str(exc)
        return HSIRangeStateResponse(
            ok=False,
            generated_at=date.today().isoformat(),
            error=message,
        )


@app.put("/api/days/{day_number}/workbench", response_model=DayActionResponse)
def save_workbench(
    payload: WorkbenchWriteRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    local_web.save_workbench(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="每日作战台已保存。", day=build_daily_record_response(day_number))


@app.put("/api/day-records/workbench", response_model=DayActionResponse)
def save_workbench_by_key(payload: WorkbenchByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    local_web.save_workbench(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="每日作战台已保存。", day=build_daily_record_response_by_key(payload.trade_date, market))


@app.post("/api/days/{day_number}/trades", response_model=DayActionResponse)
def create_trade(
    payload: TradeWriteRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    normalized_payload = normalize_trade_updates(payload.model_dump(exclude_none=True, by_alias=False))
    auto_event_id = local_web.add_trade(record_path, dict_to_form(normalized_payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    message = "交易记录已写入。"
    if auto_event_id:
        message += f" 已联动纪律事件：{auto_event_id}。"
    return DayActionResponse(message=message, day=build_daily_record_response(day_number), auto_event_id=auto_event_id)


@app.post("/api/day-records/trades", response_model=DayActionResponse)
def create_trade_by_key(payload: TradeByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    normalized_payload = normalize_trade_updates(payload.model_dump(exclude_none=True, by_alias=False))
    auto_event_id = local_web.add_trade(record_path, dict_to_form(normalized_payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    message = "交易记录已写入。"
    if auto_event_id:
        message += f" 已联动纪律事件：{auto_event_id}。"
    return DayActionResponse(message=message, day=build_daily_record_response_by_key(payload.trade_date, market), auto_event_id=auto_event_id)


@app.post("/api/agent/trades/open", response_model=AgentTradeOpenResponse)
def agent_open_trade(payload: AgentTradeOpenRequest) -> AgentTradeOpenResponse:
    return write_agent_open_trade(payload)


@app.post("/api/agent/commit", response_model=AgentCommitResponse)
def agent_commit(payload: AgentCommitRequest) -> AgentCommitResponse:
    return commit_agent_payload(payload)


@app.post("/api/agent/intake/open", response_model=AgentTradeOpenIntakeResponse)
def agent_intake_open_trade(payload: AgentTradeOpenIntakeRequest) -> AgentTradeOpenIntakeResponse:
    market = shared_clean_text(payload.market).upper() or "HK"
    trading_mode = shared_clean_text(payload.trading_mode) or market_to_trading_mode(market)
    context = build_agent_context_response(trade_date=payload.trade_date, market=market)
    proposal, missing_fields, warnings = agent_intake.parse_open_trade_note(
        payload.raw_note,
        market=market,
        trading_mode=trading_mode,
    )
    can_write = not missing_fields
    follow_up_questions = build_open_intake_follow_up_questions(proposal, missing_fields, context)
    preview_rule_hits: list[AgentRuleHit] = []
    preview_knowledge_routes: list[AgentKnowledgeRoute] = []

    if can_write:
        validate_trade_dict(proposal)
        preview_rule_hits, preview_knowledge_routes = preview_agent_open_feedback(
            proposal,
            raw_note=payload.raw_note,
            agent_note=payload.agent_note,
            suspected_distortions=payload.suspected_distortions,
        )

    if payload.commit and not can_write:
        return AgentTradeOpenIntakeResponse(
            message="口述已解析，但字段还不够，未写入。",
            raw_note=payload.raw_note,
            proposal=camelize_keys(proposal),
            missing_fields=missing_fields,
            missing_labels=[local_web.field_label(key) for key in missing_fields],
            warnings=warnings,
            follow_up_questions=follow_up_questions,
            can_write=False,
            committed=False,
            context=context,
            preview_rule_hits=preview_rule_hits,
            preview_knowledge_routes=preview_knowledge_routes,
        )

    if payload.commit and can_write:
        ensure_day_record_for_key(
            payload.trade_date,
            market,
            trading_mode=trading_mode,
            current_state=payload.current_state,
            focus=payload.focus,
        )
        committed_response = write_agent_open_trade(
            AgentTradeOpenRequest.model_validate(
                {
                    **proposal,
                    "trade_date": payload.trade_date,
                    "market": market,
                    "raw_note": payload.raw_note,
                    "agent_note": payload.agent_note,
                    "suspected_distortions": payload.suspected_distortions,
                }
            )
        )
        return AgentTradeOpenIntakeResponse(
            message="口述解析完成，已写入交易记录。",
            raw_note=payload.raw_note,
            proposal=camelize_keys(proposal),
            missing_fields=[],
            missing_labels=[],
            warnings=warnings,
            follow_up_questions=follow_up_questions,
            can_write=True,
            committed=True,
            context=context,
            preview_rule_hits=preview_rule_hits,
            preview_knowledge_routes=preview_knowledge_routes,
            day=committed_response.day,
            auto_event_id=committed_response.auto_event_id,
            rule_hits=committed_response.rule_hits,
            knowledge_routes=committed_response.knowledge_routes,
        )

    return AgentTradeOpenIntakeResponse(
        message="口述已解析，等待确认写入。",
        raw_note=payload.raw_note,
        proposal=camelize_keys(proposal),
        missing_fields=missing_fields,
        missing_labels=[local_web.field_label(key) for key in missing_fields],
        warnings=warnings,
        follow_up_questions=follow_up_questions,
        can_write=can_write,
        committed=False,
        context=context,
        preview_rule_hits=preview_rule_hits,
        preview_knowledge_routes=preview_knowledge_routes,
    )


@app.post("/api/agent/intake/close", response_model=AgentTradeCloseIntakeResponse)
def agent_intake_close_trade(payload: AgentTradeCloseIntakeRequest) -> AgentTradeCloseIntakeResponse:
    market = shared_clean_text(payload.market).upper() or "HK"
    context = build_agent_context_response(trade_date=payload.trade_date, market=market)
    record_path, record, _ = get_file_record_for_key(payload.trade_date, market)
    proposal, missing_fields, warnings = agent_intake.parse_close_trade_note(payload.raw_note)
    target_trade, needs_trade_id = resolve_close_target_trade(record, proposal.get("trade_id", ""))
    if needs_trade_id and "trade_id" not in missing_fields:
        missing_fields = ["trade_id", *missing_fields]
    can_write = not missing_fields and target_trade is not None
    follow_up_questions = build_close_intake_follow_up_questions(
        proposal,
        missing_fields,
        context,
        open_trade_count=len([trade for trade in record["trades"] if not trade.get("exit_time") and trade.get("exit_price") is None]),
        needs_trade_id=needs_trade_id,
    )
    pnl_preview = None
    result_preview = ""
    if can_write and target_trade is not None:
        pnl_preview, result_preview = build_agent_close_preview(target_trade, proposal)

    if payload.commit and can_write and target_trade is not None:
        close_updates = {
            **proposal,
            "review_note": "\n".join(
                item
                for item in [
                    f"Agent原始口述：{shared_clean_text(payload.raw_note)}" if shared_clean_text(payload.raw_note) else "",
                    f"Agent处理备注：{shared_clean_text(payload.agent_note)}" if shared_clean_text(payload.agent_note) else "",
                ]
                if item
            ),
        }
        day = write_agent_close_trade(
            record_path=record_path,
            record=record,
            trade=target_trade,
            close_updates=close_updates,
            trade_date=payload.trade_date,
            market=market,
        )
        return AgentTradeCloseIntakeResponse(
            message="平仓口述解析完成，已写入交易记录。",
            raw_note=payload.raw_note,
            proposal=camelize_keys(proposal),
            target_trade_id=shared_clean_text(target_trade.get("trade_id")),
            missing_fields=[],
            missing_labels=[],
            warnings=warnings,
            follow_up_questions=follow_up_questions,
            can_write=True,
            committed=True,
            context=context,
            pnl_preview=pnl_preview,
            result_preview=result_preview,
            day=day,
        )

    return AgentTradeCloseIntakeResponse(
        message="平仓口述已解析，等待确认写入。" if can_write else "平仓口述已解析，但字段还不够，未写入。",
        raw_note=payload.raw_note,
        proposal=camelize_keys(proposal),
        target_trade_id=shared_clean_text(target_trade.get("trade_id")) if target_trade else "",
        missing_fields=missing_fields,
        missing_labels=[missing_label_for_trade_field(key) for key in missing_fields],
        warnings=warnings,
        follow_up_questions=follow_up_questions,
        can_write=can_write,
        committed=False,
        context=context,
        pnl_preview=pnl_preview,
        result_preview=result_preview,
    )


@app.post("/api/agent/intake/rule-event", response_model=AgentRuleEventIntakeResponse)
def agent_intake_rule_event(payload: AgentRuleEventIntakeRequest) -> AgentRuleEventIntakeResponse:
    market = shared_clean_text(payload.market).upper() or "HK"
    context = build_agent_context_response(trade_date=payload.trade_date, market=market)
    if payload.commit:
        trading_mode = market_to_trading_mode(market)
        record_path, record, _ = ensure_day_record_for_key(
            payload.trade_date,
            market,
            trading_mode=trading_mode,
        )
    else:
        try:
            record_path, record, _ = get_file_record_for_key(payload.trade_date, market)
        except HTTPException:
            record_path = local_web.RECORDS_DIR / f"{payload.trade_date}-{market}-record-container.md"
            record = {"trades": [], "events": [], "review": {}, "validation": {}}
    proposal, missing_fields, warnings = agent_intake.parse_rule_event_note(payload.raw_note)
    can_write = not missing_fields
    follow_up_questions = build_rule_event_intake_follow_up_questions(proposal, missing_fields, context)

    if payload.commit and can_write:
        proposal["follow_up_note"] = "\n".join(
            item
            for item in [
                shared_clean_text(proposal.get("follow_up_note")),
                f"Agent原始口述：{shared_clean_text(payload.raw_note)}" if shared_clean_text(payload.raw_note) else "",
                f"Agent处理备注：{shared_clean_text(payload.agent_note)}" if shared_clean_text(payload.agent_note) else "",
            ]
            if item
        )
        day, _ = write_agent_rule_event(
            record_path=record_path,
            record=record,
            proposal=proposal,
            trade_date=payload.trade_date,
            market=market,
        )
        return AgentRuleEventIntakeResponse(
            message="纪律事件口述解析完成，已写入记录。",
            raw_note=payload.raw_note,
            proposal=camelize_keys(proposal),
            missing_fields=[],
            missing_labels=[],
            warnings=warnings,
            follow_up_questions=follow_up_questions,
            can_write=True,
            committed=True,
            context=context,
            day=day,
        )

    return AgentRuleEventIntakeResponse(
        message="纪律事件口述已解析，等待确认写入。" if can_write else "纪律事件口述已解析，但字段还不够，未写入。",
        raw_note=payload.raw_note,
        proposal=camelize_keys(proposal),
        missing_fields=missing_fields,
        missing_labels=[missing_label_for_trade_field(key) for key in missing_fields],
        warnings=warnings,
        follow_up_questions=follow_up_questions,
        can_write=can_write,
        committed=False,
        context=context,
    )


@app.post("/api/agent/intake/review", response_model=AgentReviewIntakeResponse)
def agent_intake_review(payload: AgentReviewIntakeRequest) -> AgentReviewIntakeResponse:
    market = shared_clean_text(payload.market).upper() or "HK"
    context = build_agent_context_response(trade_date=payload.trade_date, market=market)
    if payload.commit:
        trading_mode = market_to_trading_mode(market)
        record_path, record, _ = ensure_day_record_for_key(
            payload.trade_date,
            market,
            trading_mode=trading_mode,
        )
    else:
        try:
            record_path, record, _ = get_file_record_for_key(payload.trade_date, market)
        except HTTPException:
            record_path = local_web.RECORDS_DIR / f"{payload.trade_date}-{market}-record-container.md"
            record = {"trades": [], "events": [], "review": {}, "validation": {}}
    proposal, missing_fields, warnings = agent_intake.parse_review_note(payload.raw_note)
    can_write = not missing_fields
    follow_up_questions = build_review_intake_follow_up_questions(proposal, missing_fields, context)

    if payload.commit and can_write:
        proposal["market_issue"] = proposal.get("market_issue", "")
        proposal["setup_issue"] = proposal.get("setup_issue", "")
        day = write_agent_review(
            record_path=record_path,
            record=record,
            proposal=proposal,
            trade_date=payload.trade_date,
            market=market,
        )
        return AgentReviewIntakeResponse(
            message="复盘口述解析完成，已写入记录。",
            raw_note=payload.raw_note,
            proposal=camelize_keys(proposal),
            missing_fields=[],
            missing_labels=[],
            warnings=warnings,
            follow_up_questions=follow_up_questions,
            can_write=True,
            committed=True,
            context=context,
            day=day,
        )

    return AgentReviewIntakeResponse(
        message="复盘口述已解析，等待确认写入。" if can_write else "复盘口述已解析，但字段还不够，未写入。",
        raw_note=payload.raw_note,
        proposal=camelize_keys(proposal),
        missing_fields=missing_fields,
        missing_labels=[missing_label_for_trade_field(key) for key in missing_fields],
        warnings=warnings,
        follow_up_questions=follow_up_questions,
        can_write=can_write,
        committed=False,
        context=context,
    )


@app.post("/api/agent/workflow/intake", response_model=AgentWorkflowIntakeResponse)
def agent_workflow_intake(payload: AgentWorkflowIntakeRequest) -> AgentWorkflowIntakeResponse:
    intent = agent_intake.classify_intake_intent(payload.raw_note)
    market = shared_clean_text(payload.market).upper() or "HK"
    context = build_agent_context_response(trade_date=payload.trade_date, market=market)
    raw = payload.model_dump(by_alias=False)
    confidence = workflow_intent_confidence(intent, payload.raw_note)

    if intent == "open_trade":
        result = agent_intake_open_trade(
            AgentTradeOpenIntakeRequest.model_validate(model_input_subset(AgentTradeOpenIntakeRequest, raw))
        )
        result_dict = response_to_dict(result)
        return AgentWorkflowIntakeResponse(
            message="已识别为开仓口述。",
            intent=intent,
            intentConfidence=confidence,
            suggestedEndpoint="/api/agent/intake/open",
            nextAction=workflow_next_action(intent, result_dict, context),
            context=context,
            result=result_dict,
        )
    if intent == "close_trade":
        result = agent_intake_close_trade(
            AgentTradeCloseIntakeRequest.model_validate(model_input_subset(AgentTradeCloseIntakeRequest, raw))
        )
        result_dict = response_to_dict(result)
        return AgentWorkflowIntakeResponse(
            message="已识别为平仓口述。",
            intent=intent,
            intentConfidence=confidence,
            suggestedEndpoint="/api/agent/intake/close",
            nextAction=workflow_next_action(intent, result_dict, context),
            context=context,
            result=result_dict,
        )
    if intent == "rule_event":
        result = agent_intake_rule_event(
            AgentRuleEventIntakeRequest.model_validate(model_input_subset(AgentRuleEventIntakeRequest, raw))
        )
        result_dict = response_to_dict(result)
        return AgentWorkflowIntakeResponse(
            message="已识别为纪律事件口述。",
            intent=intent,
            intentConfidence=confidence,
            suggestedEndpoint="/api/agent/intake/rule-event",
            nextAction=workflow_next_action(intent, result_dict, context),
            context=context,
            result=result_dict,
        )
    if intent == "review":
        result = agent_intake_review(
            AgentReviewIntakeRequest.model_validate(model_input_subset(AgentReviewIntakeRequest, raw))
        )
        result_dict = response_to_dict(result)
        return AgentWorkflowIntakeResponse(
            message="已识别为盘后复盘口述。",
            intent=intent,
            intentConfidence=confidence,
            suggestedEndpoint="/api/agent/intake/review",
            nextAction=workflow_next_action(intent, result_dict, context),
            context=context,
            result=result_dict,
        )

    unknown_result = {
        "rawNote": payload.raw_note,
        "followUpQuestions": [
            "这段口述是开仓、平仓、纪律事件，还是盘后复盘？",
            f"当前系统阶段是：{context.stage.stage_label}。",
        ],
    }
    return AgentWorkflowIntakeResponse(
        message="暂时无法判断这段口述属于哪一类，请明确是开仓、平仓、纪律事件还是复盘。",
        intent="unknown",
        intentConfidence=confidence,
        suggestedEndpoint="",
        nextAction=workflow_next_action("unknown", unknown_result, context),
        context=context,
        result=unknown_result,
    )


@app.post("/api/agent/session", response_model=AgentSessionResponse)
def agent_session(payload: AgentSessionRequest) -> AgentSessionResponse:
    workflow = agent_workflow_intake(
        AgentWorkflowIntakeRequest.model_validate(
            {
                "trade_date": payload.trade_date,
                "market": payload.market,
                "raw_note": payload.raw_note,
                "commit": payload.auto_commit,
                "current_state": payload.current_state,
                "focus": payload.focus,
                "trading_mode": payload.trading_mode,
                "agent_note": payload.agent_note,
                "suspected_distortions": payload.suspected_distortions,
            }
        )
    )
    result = workflow.result
    auto_committed = bool(result.get("committed") is True)
    if payload.auto_commit and workflow.intent == "unknown":
        auto_committed = False
    return AgentSessionResponse(
        message=workflow.message,
        intent=workflow.intent,
        intentConfidence=workflow.intent_confidence,
        nextAction=workflow.next_action,
        autoCommitted=auto_committed,
        context=workflow.context,
        workflow=response_to_dict(workflow),
    )


@app.put("/api/days/{day_number}/trades/{trade_id}", response_model=DayActionResponse)
def update_trade(
    payload: TradeWriteRequest,
    day_number: int = Depends(require_latest_day),
    trade_id: str = "",
) -> DayActionResponse:
    return DayActionResponse(message=f"交易 {trade_id} 已更新。", day=mutate_trade(day_number, trade_id, payload))


@app.put("/api/day-records/trades/{trade_id}", response_model=DayActionResponse)
def update_trade_by_key(
    payload: TradeWriteRequest,
    trade_id: str,
    tradeDate: str = Query(...),
    market: str = Query(...),
) -> DayActionResponse:
    normalized_market = shared_clean_text(market).upper()
    record_path, record, _ = get_file_record_for_key(tradeDate, normalized_market)
    mutate_trade_record(record_path, record, trade_id, payload)
    return DayActionResponse(
        message=f"交易 {trade_id} 已更新。",
        day=build_daily_record_response_by_key(tradeDate, normalized_market),
    )


@app.delete("/api/days/{day_number}/trades/{trade_id}", response_model=DayActionResponse)
def remove_trade(day_number: int = Depends(require_latest_day), trade_id: str = "") -> DayActionResponse:
    return DayActionResponse(message=f"交易 {trade_id} 已删除。", day=delete_trade(day_number, trade_id))


@app.delete("/api/day-records/trades/{trade_id}", response_model=DayActionResponse)
def remove_trade_by_key(
    trade_id: str,
    tradeDate: str = Query(...),
    market: str = Query(...),
) -> DayActionResponse:
    _, _, day_number = get_file_record_for_key(tradeDate, shared_clean_text(market).upper())
    return DayActionResponse(message=f"交易 {trade_id} 已删除。", day=delete_trade(day_number, trade_id))


@app.post("/api/days/{day_number}/rule-events", response_model=DayActionResponse)
def create_rule_event(
    payload: RuleEventWriteRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    local_web.add_rule_event(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="纪律事件已写入。", day=build_daily_record_response(day_number))


@app.post("/api/day-records/rule-events", response_model=DayActionResponse)
def create_rule_event_by_key(payload: RuleEventByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    local_web.add_rule_event(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="纪律事件已写入。", day=build_daily_record_response_by_key(payload.trade_date, market))


@app.post("/api/day-records/observations", response_model=DayActionResponse)
def create_agent_observation_by_key(payload: AgentObservationByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, _ = get_file_record_for_key(payload.trade_date, market)
    dal.insert_agent_observation(
        {
            **payload.model_dump(by_alias=False),
            "source_record_path": workspace_state.relative_path(record_path, root=local_web.ROOT),
        }
    )
    return DayActionResponse(
        message="Agent observation 已写入。",
        day=build_daily_record_response_by_key(payload.trade_date, market),
    )


@app.post("/api/days/{day_number}/rule-events/presets", response_model=DayActionResponse)
def create_rule_event_preset(
    payload: RuleEventPresetRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    event_id = local_web.add_rule_event_preset(record_path, payload.preset_key)
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message=f"快捷纪律事件已写入：{event_id}。", day=build_daily_record_response(day_number))


@app.post("/api/day-records/rule-events/presets", response_model=DayActionResponse)
def create_rule_event_preset_by_key(payload: RuleEventPresetByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    event_id = local_web.add_rule_event_preset(record_path, payload.preset_key)
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message=f"快捷纪律事件已写入：{event_id}。", day=build_daily_record_response_by_key(payload.trade_date, market))


@app.put("/api/days/{day_number}/rule-events/{event_id}", response_model=DayActionResponse)
def update_rule_event(
    payload: RuleEventWriteRequest,
    day_number: int = Depends(require_latest_day),
    event_id: str = "",
) -> DayActionResponse:
    return DayActionResponse(message=f"纪律事件 {event_id} 已更新。", day=mutate_rule_event(day_number, event_id, payload))


@app.put("/api/day-records/rule-events/{event_id}", response_model=DayActionResponse)
def update_rule_event_by_key(
    payload: RuleEventWriteRequest,
    event_id: str,
    tradeDate: str = Query(...),
    market: str = Query(...),
) -> DayActionResponse:
    normalized_market = shared_clean_text(market).upper()
    record_path, record, _ = get_file_record_for_key(tradeDate, normalized_market)
    mutate_rule_event_record(record_path, record, event_id, payload)
    return DayActionResponse(
        message=f"纪律事件 {event_id} 已更新。",
        day=build_daily_record_response_by_key(tradeDate, normalized_market),
    )


@app.delete("/api/days/{day_number}/rule-events/{event_id}", response_model=DayActionResponse)
def remove_rule_event(day_number: int = Depends(require_latest_day), event_id: str = "") -> DayActionResponse:
    return DayActionResponse(message=f"纪律事件 {event_id} 已删除。", day=delete_rule_event(day_number, event_id))


@app.delete("/api/day-records/rule-events/{event_id}", response_model=DayActionResponse)
def remove_rule_event_by_key(
    event_id: str,
    tradeDate: str = Query(...),
    market: str = Query(...),
) -> DayActionResponse:
    normalized_market = shared_clean_text(market).upper()
    record_path, record, _ = get_file_record_for_key(tradeDate, normalized_market)
    delete_rule_event_record(record_path, record, event_id)
    return DayActionResponse(
        message=f"纪律事件 {event_id} 已删除。",
        day=build_daily_record_response_by_key(tradeDate, normalized_market),
    )


@app.put("/api/days/{day_number}/review", response_model=DayActionResponse)
def save_review(
    payload: ReviewWriteRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    local_web.save_review(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="复盘已保存。", day=build_daily_record_response(day_number))


@app.put("/api/day-records/review", response_model=DayActionResponse)
def save_review_by_key(payload: ReviewByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    local_web.save_review(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="复盘已保存。", day=build_daily_record_response_by_key(payload.trade_date, market))


@app.put("/api/days/{day_number}/validation", response_model=DayActionResponse)
def save_validation(
    payload: ValidationWriteRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    local_web.save_validation(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="归档验证已保存。", day=build_daily_record_response(day_number))


@app.put("/api/day-records/validation", response_model=DayActionResponse)
def save_validation_by_key(payload: ValidationByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    local_web.save_validation(record_path, model_to_form(payload))
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message="归档验证已保存。", day=build_daily_record_response_by_key(payload.trade_date, market))


@app.post("/api/days/{day_number}/review/sync-numbers", response_model=DayActionResponse)
def sync_review_numbers(
    payload: SyncReviewNumbersRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    pnl_text, trade_count = local_web.sync_review_numbers(record_path)
    message = f"复盘数字已同步：交易 {trade_count} 笔，盈亏 HK$ {pnl_text}。"
    if payload.after_action == "closeout":
        output_path, _, _ = local_web.run_closeout_generator(record_path, force=True)
        message += f" 归档草稿已更新：{local_web.relative_path(output_path)}。"
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message=message, day=build_daily_record_response(day_number))


@app.post("/api/day-records/review/sync-numbers", response_model=DayActionResponse)
def sync_review_numbers_by_key(payload: SyncReviewNumbersByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, day_number = get_file_record_for_key(payload.trade_date, market)
    pnl_text, trade_count = local_web.sync_review_numbers(record_path)
    message = f"复盘数字已同步：交易 {trade_count} 笔，盈亏 HK$ {pnl_text}。"
    if payload.after_action == "closeout":
        output_path, _, _ = local_web.run_closeout_generator(record_path, force=True)
        message += f" 归档草稿已更新：{local_web.relative_path(output_path)}。"
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(message=message, day=build_daily_record_response_by_key(payload.trade_date, market))


@app.post("/api/days/{day_number}/review/acceptance", response_model=DayActionResponse)
def save_acceptance_review(
    payload: AcceptanceReviewWriteRequest,
    day_number: int = Depends(require_latest_day),
) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    pnl_text, trade_count = local_web.save_acceptance_review(record_path, model_to_form(payload))
    output_path, _, _ = local_web.run_closeout_generator(record_path, force=True)
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    message = f"终局验收复盘已保存：交易 {trade_count} 笔，盈亏 HK$ {pnl_text}。归档草稿已更新：{local_web.relative_path(output_path)}。"
    return DayActionResponse(message=message, day=build_daily_record_response(day_number))


@app.post("/api/day-records/review/acceptance", response_model=DayActionResponse)
def save_acceptance_review_by_key(payload: AcceptanceReviewByKeyRequest) -> DayActionResponse:
    market = shared_clean_text(payload.market).upper()
    record_path, _, _ = get_file_record_for_key(payload.trade_date, market)
    pnl_text, trade_count = local_web.save_acceptance_review(record_path, model_to_form(payload))
    output_path, _, _ = local_web.run_closeout_generator(record_path, force=True)
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    message = f"终局验收复盘已保存：交易 {trade_count} 笔，盈亏 HK$ {pnl_text}。归档草稿已更新：{local_web.relative_path(output_path)}。"
    return DayActionResponse(
        message=message,
        day=build_daily_record_response_by_key(payload.trade_date, market),
    )


@app.post("/api/days/{day_number}/close-no-trade", response_model=DayActionResponse)
def close_no_trade_day(day_number: int = Depends(require_latest_day)) -> DayActionResponse:
    record_path, _ = get_file_record_for_day(day_number)
    output_path, _ = local_web.close_no_trade_day(record_path)
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(
        message=f"空仓日复盘、验证和归档已完成：{local_web.relative_path(output_path)}。",
        day=build_daily_record_response(day_number),
    )


@app.post("/api/day-records/close-no-trade", response_model=DayActionResponse)
def close_no_trade_day_by_key(day_key: DayKeyRequest) -> DayActionResponse:
    market = shared_clean_text(day_key.market).upper()
    record_path, _, day_number = get_file_record_for_key(day_key.trade_date, market)
    output_path, _ = local_web.close_no_trade_day(record_path)
    record = local_web.load_record_db_first(record_path)
    update_current_day_state(record_path, record)
    return DayActionResponse(
        message=f"空仓日复盘、验证和归档已完成：{local_web.relative_path(output_path)}。",
        day=build_daily_record_response_by_key(day_key.trade_date, market),
    )


@app.get("/api/days/{day_number}/closeout", response_model=CloseoutPayload)
def get_closeout(day_number: int) -> CloseoutPayload:
    record_path, _ = get_file_record_for_day(day_number)
    return build_closeout_payload(record_path)


@app.get("/api/day-records/closeout", response_model=CloseoutPayload)
def get_closeout_by_key(
    tradeDate: str = Query(...),
    market: str = Query(...),
) -> CloseoutPayload:
    record_path, _, _ = get_file_record_for_key(tradeDate, shared_clean_text(market).upper())
    return build_closeout_payload(record_path)


@app.post("/api/days/{day_number}/closeout", response_model=CloseoutPayload)
def generate_closeout(
    payload: CloseoutGenerateRequest,
    day_number: int = Depends(require_latest_day),
) -> CloseoutPayload:
    record_path, _ = get_file_record_for_day(day_number)
    output_path, preview, _ = local_web.run_closeout_generator(record_path, force=payload.regenerate)
    state = local_web.load_state()
    state.current_closeout_path = local_web.relative_path(output_path)
    local_web.save_state(state)
    return build_closeout_payload_from_output(output_path, preview=preview)


@app.post("/api/day-records/closeout", response_model=CloseoutPayload)
def generate_closeout_by_key(payload: CloseoutByKeyRequest) -> CloseoutPayload:
    market = shared_clean_text(payload.market).upper()
    record_path, _, _ = get_file_record_for_key(payload.trade_date, market)
    output_path, preview, _ = local_web.run_closeout_generator(record_path, force=payload.regenerate)
    state = local_web.load_state()
    state.current_closeout_path = local_web.relative_path(output_path)
    local_web.save_state(state)
    return build_closeout_payload_from_output(output_path, preview=preview)


@app.get("/api/artifacts/trial-summary", response_model=ArtifactPreviewResponse)
def get_trial_summary() -> ArtifactPreviewResponse:
    path = local_web.current_summary_path(local_web.load_state()) or local_web.expected_trial_summary_path()
    return artifact_preview(path)


@app.post("/api/artifacts/trial-summary", response_model=ArtifactPreviewResponse)
def generate_trial_summary(payload: ArtifactGenerateRequest) -> ArtifactPreviewResponse:
    path, _, _ = local_web.run_trial_summary_generator(force=payload.regenerate)
    state = local_web.load_state()
    state.current_summary_path = local_web.relative_path(path)
    local_web.save_state(state)
    return artifact_preview(path)


@app.get("/api/artifacts/field-audit", response_model=ArtifactPreviewResponse)
def get_field_audit() -> ArtifactPreviewResponse:
    path = local_web.current_audit_path(local_web.load_state()) or local_web.expected_field_audit_path()
    return artifact_preview(path)


@app.post("/api/artifacts/field-audit", response_model=ArtifactPreviewResponse)
def generate_field_audit(payload: ArtifactGenerateRequest) -> ArtifactPreviewResponse:
    path, _, _ = local_web.run_field_audit_generator(force=payload.regenerate)
    state = local_web.load_state()
    state.current_audit_path = local_web.relative_path(path)
    local_web.save_state(state)
    return artifact_preview(path)


@app.get("/api/artifacts/overview", response_model=ArtifactsOverviewResponse)
def get_artifacts_overview() -> ArtifactsOverviewResponse:
    return build_artifacts_overview_response()


if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
if FRONTEND_DIST.exists():
    app.mount("/favicon.svg", StaticFiles(directory=FRONTEND_DIST), name="frontend-favicon")
    app.mount("/icons.svg", StaticFiles(directory=FRONTEND_DIST), name="frontend-icons")


@app.get("/{catchall:path}", response_model=None)
async def serve_spa(catchall: str) -> FileResponse | JSONResponse:
    if catchall.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "API route not found"})

    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Frontend dist not found. Please run 'npm run build' in frontend directory."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=local_web.DEFAULT_HOST, port=int(os.environ.get("TOPTRADER_PORT", "8526")))
