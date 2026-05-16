#!/usr/bin/env python3
"""Agent-facing policy hints for rule and knowledge routing."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from core.utils import clean_text

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
RULE_CATALOG_PATH = WORKSPACE_ROOT / "trading-system" / "00-index" / "rules-catalog-v1.md"
KNOWLEDGE_ROUTER_PATH = WORKSPACE_ROOT / "toptrader-research" / "00-index" / "knowledge-router-v1.md"


FALLBACK_RULES: dict[str, dict[str, str]] = {
    "PROCESS-DAILY-004": {
        "rule_id": "PROCESS-DAILY-004",
        "severity": "red",
        "trigger": "当天触发硬熔断",
        "action": "不再讨论新机会",
        "source": "00-index/作战中枢.md",
    },
    "SETUP-ABC-001": {
        "rule_id": "SETUP-ABC-001",
        "severity": "red",
        "trigger": "止损说不清",
        "action": "直接降为 C 级，不做",
        "source": "05-setups/A-B-C级机会评分表.md",
    },
    "SETUP-ABC-005": {
        "rule_id": "SETUP-ABC-005",
        "severity": "red",
        "trigger": "方向、位置、确认三项里有两项说不清",
        "action": "直接降为 C 级，不做",
        "source": "05-setups/A-B-C级机会评分表.md",
    },
    "SETUP-ABC-007": {
        "rule_id": "SETUP-ABC-007",
        "severity": "yellow",
        "trigger": "机会评分 7-9 分",
        "action": "B 级机会，只允许小仓试错",
        "source": "05-setups/A-B-C级机会评分表.md",
    },
    "SETUP-ABC-008": {
        "rule_id": "SETUP-ABC-008",
        "severity": "red",
        "trigger": "机会评分 6 分及以下",
        "action": "C 级机会，不做",
        "source": "05-setups/A-B-C级机会评分表.md",
    },
    "PROCESS-DAILY-003": {
        "rule_id": "PROCESS-DAILY-003",
        "severity": "red",
        "trigger": "连亏后想用更大仓位翻本",
        "action": "禁止加大仓位",
        "source": "00-index/作战中枢.md",
    },
    "RISK-SOFT-001": {
        "rule_id": "RISK-SOFT-001",
        "severity": "yellow",
        "trigger": "明显情绪化",
        "action": "降仓、暂停或只观察",
        "source": "04-risk-control/软规则.md",
    },
    "RISK-SOFT-002": {
        "rule_id": "RISK-SOFT-002",
        "severity": "yellow",
        "trigger": "想报复性翻本",
        "action": "暂停，复述交易理由；不清楚就不做",
        "source": "04-risk-control/软规则.md",
    },
}


def clean_agent_text(value: Any) -> str:
    return clean_text(value).lower()


@lru_cache(maxsize=1)
def load_rule_catalog() -> dict[str, dict[str, str]]:
    rows = parse_markdown_table(
        RULE_CATALOG_PATH,
        required_columns=["rule_id", "type", "severity", "trigger", "action", "source"],
    )
    catalog = {row["rule_id"]: row for row in rows if row.get("rule_id")}
    return {**FALLBACK_RULES, **catalog}


@lru_cache(maxsize=1)
def load_knowledge_router() -> dict[str, dict[str, str]]:
    rows = parse_markdown_table(
        KNOWLEDGE_ROUTER_PATH,
        required_columns=[
            "route_id",
            "distortion_type",
            "trigger_phrases",
            "primary_playbook",
            "capability_pack",
            "first_action",
        ],
    )
    return {row["route_id"]: normalize_knowledge_route(row) for row in rows if row.get("route_id")}


def parse_markdown_table(path: Path, *, required_columns: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    active = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            header = None
            active = False
            continue
        cells = [clean_markdown_cell(cell) for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        if header is None:
            header = cells
            active = all(column in header for column in required_columns)
            continue
        if all(set(cell) <= {"-"} for cell in cells if cell):
            continue
        if not active:
            continue
        if len(cells) < len(header):
            continue
        row = dict(zip(header, cells))
        rows.append(row)
    return rows


def clean_markdown_cell(value: str) -> str:
    text = clean_text(value)
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        return text[1:-1]
    return text


def normalize_knowledge_route(row: dict[str, str]) -> dict[str, str]:
    return {
        "route_id": row.get("route_id", ""),
        "distortion_type": row.get("distortion_type", ""),
        "trigger_phrases": row.get("trigger_phrases", ""),
        "playbook": prefix_research_path(row.get("primary_playbook", "")),
        "capability_pack": prefix_research_path(row.get("capability_pack", "")),
        "first_action": row.get("first_action", ""),
    }


def prefix_research_path(value: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("toptrader-research/"):
        return text
    return f"toptrader-research/{text}"


def rule_hit(rule_id: str, *, message: str = "") -> dict[str, str]:
    rule = load_rule_catalog().get(rule_id, FALLBACK_RULES.get(rule_id, {}))
    action = clean_text(rule.get("action"))
    trigger = clean_text(rule.get("trigger"))
    return {
        "rule_id": rule_id,
        "severity": clean_text(rule.get("severity")) or "yellow",
        "message": clean_text(message) or action or trigger or rule_id,
        "source": clean_text(rule.get("source")) or str(RULE_CATALOG_PATH.relative_to(WORKSPACE_ROOT)),
    }


def build_rule_hits_for_trade(trade: dict[str, Any], *, auto_event_id: str = "") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []

    if trade.get("rule_violation") is True:
        hits.append(rule_hit("PROCESS-DAILY-004", message=clean_agent_text(trade.get("violation_note")) or "交易已标记为规则违规。"))

    if not trade.get("risk_clear"):
        hits.append(rule_hit("SETUP-ABC-001", message="止损或风险不清，按规则直接降为 C 级，不做。"))

    failed_checks = []
    if trade.get("direction_clear") is False:
        failed_checks.append("方向不清")
    if trade.get("location_ok") is False:
        failed_checks.append("位置不合理")
    if trade.get("confirmation_ok") is False:
        failed_checks.append("确认信号不足")
    if len(failed_checks) >= 2:
        hits.append(rule_hit("SETUP-ABC-005", message="方向、位置、确认三项里有两项说不清：" + "、".join(failed_checks) + "。"))

    if trade.get("abc_grade") == "C":
        hits.append(rule_hit("SETUP-ABC-008", message="C 级机会不做。"))
    elif trade.get("abc_grade") == "B":
        hits.append(rule_hit("SETUP-ABC-007", message="B 级机会只允许小仓试错。"))

    if trade.get("followed_plan") is False:
        hits.append(rule_hit("PROCESS-DAILY-003", message="这笔交易未按计划执行，盘后需要单列复盘。"))

    if clean_agent_text(trade.get("pre_trade_emotion")) in {"fomo", "recover_loss", "defiant", "rushed"}:
        hits.append(rule_hit("RISK-SOFT-001", message="开仓前情绪存在风险，需要降仓、暂停或只观察。"))

    if clean_agent_text(trade.get("emotion_state")) in {"revenge", "impulsive"}:
        hits.append(rule_hit("RISK-SOFT-002", message="交易状态疑似报复或冲动，必须暂停复述交易理由。"))

    if auto_event_id:
        hits.append(rule_hit("PROCESS-DAILY-004", message=f"系统已自动联动纪律事件：{auto_event_id}。"))

    return unique_by_rule_and_message(hits)


ROUTE_ALIASES: dict[str, str] = {
    "fomo": "KR-001",
    "怕错过": "KR-001",
    "想追": "KR-001",
    "追": "KR-001",
    "recover_loss": "KR-002",
    "revenge": "KR-002",
    "赚回来": "KR-002",
    "翻本": "KR-002",
    "报复": "KR-002",
    "impulsive": "KR-003",
    "rushed": "KR-003",
    "冲动": "KR-003",
    "手痒": "KR-003",
    "low_quality_lure": "KR-010",
    "低质量": "KR-010",
    "profit_giveback": "KR-012",
    "回吐": "KR-012",
}


def build_knowledge_routes_for_trade(
    *,
    trade: dict[str, Any],
    raw_note: str = "",
    agent_note: str = "",
    suspected_distortions: list[str] | None = None,
) -> list[dict[str, str]]:
    keys = {
        clean_agent_text(raw_note),
        clean_agent_text(agent_note),
        clean_agent_text(trade.get("pre_trade_emotion")),
        clean_agent_text(trade.get("emotion_state")),
        clean_agent_text(trade.get("abnormal_scenario")),
    }
    keys.update(clean_agent_text(item) for item in suspected_distortions or [])

    router = load_knowledge_router()
    route_candidates: list[dict[str, str]] = []
    joined = " ".join(key for key in keys if key)
    for alias, route_id in ROUTE_ALIASES.items():
        if alias in keys or alias in joined:
            route = router.get(route_id)
            if route:
                route_candidates.append(route)

    return unique_by_route_id(route_candidates)[:3]


def unique_by_rule_and_message(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique_items: list[dict[str, str]] = []
    for item in items:
        key = item["rule_id"] + item["message"]
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def unique_by_route_id(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique_items: list[dict[str, str]] = []
    for item in items:
        if item["route_id"] in seen:
            continue
        seen.add(item["route_id"])
        unique_items.append(item)
    return unique_items
