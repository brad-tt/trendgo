#!/usr/bin/env python3
"""One-stop CLI for OpenClaw to call TrendGo Agent endpoints.

Usage:
  python3 scripts/openclaw_client.py --intent open_trade --payload-json '{"fields": {...}}'
  python3 scripts/openclaw_client.py --note "开仓 恒指牛证 28500 止损28400 仓位3手 A级 方向位置确认都清楚"
  python3 scripts/openclaw_client.py --note "复盘：今天执行问题很大，情绪也明显，明天只改一件事"
  python3 scripts/openclaw_client.py --note "纪律事件：连亏两笔后想追回来，暂停交易"
  python3 scripts/openclaw_client.py --note "平仓 盘尾信号消失了 1415出场"

Structured mode is the primary Agent path. Natural-language --note mode is
kept as a legacy fallback for the backend parser.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = os.environ.get("TOPTRADER_PORT", "8526")
DEFAULT_BASE = os.environ.get("TOPTRADER_API_BASE", f"http://127.0.0.1:{DEFAULT_PORT}")


def api_post(path: str, payload: dict) -> dict:
    url = f"{DEFAULT_BASE}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("detail", "")
        except Exception:
            detail = str(exc)
        raise SystemExit(f"TrendGo API 错误 [{exc.code}]: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"TrendGo API unreachable at {url}: {exc}") from exc


def api_get(path: str) -> dict:
    url = f"{DEFAULT_BASE}{path}"
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise SystemExit(
            f"TrendGo API contract check failed at {url} [{exc.code}]. "
            "当前端口可能仍运行旧后端；请重启当前 TrendGo 后端，"
            "或设置 TOPTRADER_API_BASE 指向当前后端。"
        ) from exc
    except URLError as exc:
        raise SystemExit(f"TrendGo API unreachable at {url}: {exc}") from exc


def ensure_structured_contract() -> None:
    body = api_get("/api/agent/contract")
    if body.get("agentCommit") is not True:
        raise SystemExit(
            "TrendGo API 不支持结构化 Agent commit。请重启当前项目后端，"
            "或设置 TOPTRADER_API_BASE 指向当前后端。"
        )


def build_proposal_summary(proposal: dict | None, missing: list[str] | None) -> list[str]:
    lines: list[str] = []
    if not proposal:
        return lines
    display = {
        "instrumentCode": "标的代码",
        "direction": "方向",
        "certificateSide": "牛熊方向",
        "setupType": "形态",
        "abcGrade": "ABC级别",
        "entryPrice": "入场价",
        "stopLoss": "止损",
        "positionSize": "仓位",
        "sessionWindow": "时段",
        "exitTime": "出场时间",
        "exitPrice": "出场价",
        "exitReason": "出场原因",
        "emotionState": "情绪状态",
        "preTradeEmotion": "开仓前情绪",
        "postTradeEmotion": "平仓后情绪",
        "ruleViolation": "是否违规",
        "followedPlan": "按计划执行",
        "directionClear": "方向清楚",
        "locationOk": "位置合理",
        "confirmationOk": "确认到位",
        "riskClear": "止损清楚",
        "eventType": "事件类型",
        "severity": "严重程度",
    }
    for key, label in display.items():
        value = proposal.get(key)
        if value is not None and value != "":
            lines.append(f"  {label}: {value}")
    return lines


def session(note: str, *, date: str = "", market: str = "HK", auto_commit: bool = False) -> dict:
    payload = {
        "tradeDate": date or None,
        "market": market,
        "rawNote": note,
        "autoCommit": auto_commit,
    }
    payload = {k: v for k, v in payload.items() if v not in {"", None}}
    return api_post("/api/agent/session", payload)


def structured_commit(
    *,
    intent: str,
    payload_json: str,
    date: str = "",
    market: str = "HK",
    note: str = "",
    agent_note: str = "",
) -> dict:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--payload-json 不是有效 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("--payload-json 必须是 JSON object。")

    if "fields" not in payload:
        payload = {"fields": payload}
    payload = {
        **payload,
        "intent": intent,
        "market": payload.get("market") or market,
        "rawNote": payload.get("rawNote") or note,
        "agentNote": payload.get("agentNote") or agent_note,
    }
    if date:
        payload["tradeDate"] = date
    return api_post("/api/agent/commit", payload)


def format_session_result(body: dict) -> str:
    lines: list[str] = []
    intent = body.get("intent", "unknown")
    confidence = body.get("intentConfidence", "unknown")
    next_action = body.get("nextAction", "unknown")
    auto_committed = body.get("autoCommitted", False)

    lines.append(f"## TrendGo Agent 解析结果")
    lines.append(f"")
    lines.append(f"- **意图**: {intent} (置信度: {confidence})")
    lines.append(f"- **下一步**: {next_action}")
    lines.append(f"- **已自动写入**: {'是' if auto_committed else '否'}")
    lines.append(f"")

    workflow = body.get("workflow", {})
    result = workflow.get("result", {})
    proposal = result.get("proposal") or result

    if proposal:
        missing = result.get("missingFields") or []
        lines.append("### 提取的字段")
        lines.append("")
        for line in build_proposal_summary(proposal, missing):
            lines.append(line)

        if missing:
            lines.append("")
            lines.append(f"### 缺失字段 ({len(missing)} 项)")
            for m in missing:
                lines.append(f"- {m}")

    hits = result.get("ruleHits") or []
    if hits:
        lines.append("")
        lines.append("### 命中的规则")
        for hit in hits:
            severity = hit.get("severity", "")
            rule_id = hit.get("ruleId", hit.get("rule_id", ""))
            msg = hit.get("message", "")
            lines.append(f"- **{rule_id}** [{severity}]: {msg}")

    routes = result.get("knowledgeRoutes") or []
    if routes:
        lines.append("")
        lines.append("### 推荐的知识路由")
        for route in routes:
            lines.append(f"- {route.get('routeId', '')}: {route.get('firstAction', '')}")

    follow_ups = result.get("followUpQuestions") or []
    if follow_ups:
        lines.append("")
        lines.append("### 需要追问")
        for q in follow_ups:
            lines.append(f"- {q}")

    return "\n".join(lines)


def format_commit_result(body: dict) -> str:
    lines: list[str] = []
    committed = bool(body.get("committed"))
    lines.append("## TrendGo Agent 写入结果")
    lines.append("")
    lines.append(f"- **已写入**: {'是' if committed else '否'}")
    lines.append(f"- **结果**: {body.get('message', '')}")
    target_trade_id = body.get("targetTradeId")
    if target_trade_id:
        lines.append(f"- **目标交易**: {target_trade_id}")
    auto_event_id = body.get("autoEventId")
    if auto_event_id:
        lines.append(f"- **联动纪律事件**: {auto_event_id}")
        lines.append("")
        lines.append("### 自动风控事件说明")
        lines.append("交易已正式写入；自动事件是风险复核提醒，不是否定当前交易。")
        lines.append("下一笔前需要重新确认方向、位置、确认、风险和工具过滤。")

    missing = body.get("missingLabels") or body.get("missingFields") or []
    if missing:
        lines.append("")
        lines.append(f"### 缺失字段 ({len(missing)} 项)")
        for item in missing:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("下一步：请补齐以上字段后再次提交；本次没有写入。")

    hits = body.get("ruleHits") or []
    if hits:
        lines.append("")
        lines.append("### 命中的规则")
        for hit in hits:
            lines.append(f"- **{hit.get('ruleId', '')}** [{hit.get('severity', '')}]: {hit.get('message', '')}")
    day = body.get("day") or {}
    severe_events = [
        event
        for event in (day.get("events") or [])
        if event.get("severity") in {"stop", "critical"}
    ]
    severe_hits = [
        hit
        for hit in hits
        if hit.get("severity") in {"stop", "critical", "red"}
    ]
    if severe_events or severe_hits:
        lines.append("")
        lines.append("### 停手处理")
        lines.append("- 现在停止新开仓。")
        lines.append("- 如果还有持仓，只允许处理平仓和风控。")
        lines.append("- 请复述触发停手的原因，并写下下一步动作。")

    routes = body.get("knowledgeRoutes") or []
    if routes:
        lines.append("")
        lines.append("### 推荐的知识路由")
        for route in routes:
            lines.append(f"- {route.get('routeId', '')}: {route.get('firstAction', '')}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="TrendGo Agent CLI for OpenClaw")
    parser.add_argument("--note", default="", help="Natural-language trading note (legacy fallback or raw note for structured commit).")
    parser.add_argument("--intent", choices=["open_trade", "close_trade", "rule_event", "review"], help="Structured Agent commit intent.")
    parser.add_argument("--payload-json", default="", help="Structured fields JSON. Use {'fields': {...}} or the fields object directly.")
    parser.add_argument("--agent-note", default="", help="Agent processing note for structured commit.")
    parser.add_argument("--date", default="", help="Trade date YYYY-MM-DD. Structured mode can omit this and let backend resolve it.")
    parser.add_argument("--market", default="HK", choices=["HK", "US"], help="Market.")
    parser.add_argument("--auto-commit", action="store_true", help="Auto-commit when fields are complete.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text.")
    args = parser.parse_args()

    if args.intent:
        if not args.payload_json:
            raise SystemExit("--intent 需要同时提供 --payload-json。")
        ensure_structured_contract()
        body = structured_commit(
            intent=args.intent,
            payload_json=args.payload_json,
            date=args.date,
            market=args.market,
            note=args.note,
            agent_note=args.agent_note,
        )
        if args.json:
            print(json.dumps(body, ensure_ascii=False, indent=2))
        else:
            print(format_commit_result(body))
        return 0

    if not args.note:
        raise SystemExit("请提供 --intent + --payload-json，或使用 legacy --note。")

    body = session(args.note, date=args.date, market=args.market, auto_commit=args.auto_commit)

    if args.json:
        print(json.dumps(body, ensure_ascii=False, indent=2))
    else:
        print(format_session_result(body))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
