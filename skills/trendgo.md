---
name: trendgo
description: 记录和管理 TrendGo 交易活动，支持自然语言输入。用于开仓、平仓、纪律事件、盘后复盘、validation/归档闭环、上下文读取、未平仓查询、盘前计划、EOD closeout、stop-flow 处理。触发词包括：记一笔、开仓、买入、入场、平仓、止损、出场、清仓、复盘、今天交易结束了、盘后总结、今天怎么样、当前状态、未平仓、还能不能开仓、归档、验证、收盘确认、牛证、熊证、call、put、期权。
---

# TrendGo Trading Skill

TrendGo is a local-first trading record and review workbench. Use this skill as the Agent layer: parse natural language, keep incomplete fields in conversation state, and write only structured payloads to TrendGo.

## Backend And CLI

Default backend:

```bash
cd app
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

Preferred write path:

```bash
cd app
python3 scripts/openclaw_client.py --intent <intent> --market HK --payload-json '{"fields": {...}}' --note "<original user text>"
```

Only `committed=true` or CLI `已写入: 是` means the record is complete. Any missing-field, proposal, pending payload, CLI command, or API error is not a completed record.

## Reference Loading

Keep this file as the high-frequency workflow. Load references only when needed:

- Constructing payloads or checking enums: `references/fields.md`
- Context read, multi-position close, EOD closeout, backend unreachable, CLI result handling: `references/workflows.md`
- US stock options: `references/us-options.md`
- Knowledge routes and first-action prompts: `references/knowledge-routing.md`
- Complete command examples: `references/examples.md`

## Intent Routing

- `read_context`: user asks 今日状态、今天怎么样、未平仓、当前还能不能开仓、今天做了几笔. Call `GET /api/agent/context`.
- `open_trade`: user describes opening/buying/entering a position.
- `close_trade`: user describes closing/exiting/stopping out. If target is ambiguous, read context and ask for `tradeId`.
- `rule_event`: user reports discipline, risk, emotion, pause, stop, or overtrade event.
- `review`: user gives postmarket review, daily issue, or next-day fix.
- `eod_closeout`: user says 今天交易结束了、归档、今天能收了吗、收盘确认. Read context, summarize status, then guide review/validation.

Do not turn vague market commentary into a record. Ask whether it is a trade, rule event, or review.

## Read Context

Use actual backend query names:

```bash
curl "http://127.0.0.1:8526/api/agent/context?market=HK"
curl "http://127.0.0.1:8526/api/agent/context?tradeDate=2026-05-16&market=HK"
```

Read context before:

- answering current status / can I open / how many trades / open positions
- writing a review
- EOD closeout
- close trade when multiple open positions may exist
- stop/critical follow-up decisions

Summarize in Chinese; do not dump raw JSON.

## Conversation Pending State

When fields are missing, do not write a database draft or pretend the record is done. Keep a pending payload in the current conversation:

- `intent`, `market`, `tradeDate`
- `rawNotes[]`
- `fields`
- `missingFields`

Tell the user: `这笔还没有写入；你补完这些字段后，我会直接写入正式记录。`

Merge later user replies into the same pending payload. Once required fields are complete, submit automatically. Require explicit confirmation only when:

- user says `先别写`, `只是讨论`, `等我确认`, or similar
- new fields conflict with pending fields
- multiple open trades make close target ambiguous
- context/API response has `stop` or `critical`
- intent is uncertain

## Missing Field Priority

Ask only the most important 1-3 gaps:

1. Core write/risk fields: time, instrument code, entry/exit price, position size, stop loss or invalidation condition.
2. Trade quality fields: setup type, direction, location, confirmation, certificate/call/put side, session, ABC grade.
3. Review extras: emotion, screenshot notes, detailed explanation.

If user says `止损清楚` or `还没有触发止损`, do not treat that as a stop value. Ask: `我需要的是止损价或失效条件，不是当前是否已经触发止损。`

## Field Rules

Never invent:

- entry/exit/stop price
- position size
- instrument code
- trade id
- user emotion
- review conclusion

Low-risk defaults are allowed only when supported by context:

- default `market=HK` if the user gives no market and the workflow is HK-focused
- HK bull/bear certificate implies `instrumentType=bull_bear_certificate`
- HK default underlying can be `HSI`
- obvious 牛证/熊证 maps to `bull`/`bear`; obvious call/put maps to `call`/`put`

Normalize fields before commit. If uncertain, read `references/fields.md`.

## Open Trade

Extract required structured fields, normalize enums, and submit `--intent open_trade` only when safe fields are complete. Target workbench is auto-created by the backend if missing.

For HK bull/bear certificates, make sure direction, certificate side, entry price, stop loss, position size, setup, ABC grade, and four checks are explicit enough. For US options, read `references/us-options.md`.

`observe_first` is not a violation. If a clear signal appears and direction/location/confirmation/risk/filter pass, record the trade without treating observation as `forced_pause`.

## Close Trade

Required fields are `exitTime`, `exitPrice`, and `exitReason`; `tradeId` is required when more than one open trade exists.

If there may be multiple open trades, call context first, list open positions, and ask which `tradeId` to close.

If close text contains stop-delay, holding past stop, 扛单, 未按计划止损, or similar execution violation, include:

- `ruleViolation=true`
- `violationNote="<user's violation fact>"`

Do not only create a separate rule event and lose the trade-level violation. Do not infer `postTradeEmotion`; submit it only when explicitly stated.

## Rule Event

Use `--intent rule_event` for explicit rule, risk, emotion, pause, stop, forced stop, or overtrade events. Required fields are event time, event type, severity, trigger reason, and action taken.

If linked to a known trade, include `linkedTradeId`.

## Review And EOD Closeout

Before review or EOD closeout, call context and summarize:

- trade count / closed / open positions
- PnL if available
- discipline event count and highest severity
- review status and validation status

Ask at most 2-3 short questions:

1. 今天最主要的执行问题是什么？
2. 明天只改一件事是什么？
3. 盘中记录和盘后复盘都完成了吗？

Write review only from user-confirmed content. If validation is not complete, guide the user to complete premarket, intraday record, and postmarket review checks.

## Risk And Feedback

If API response includes `autoEventId`, explain that it is an automatic risk review reminder, not a rejection of the trade.

If response or context includes `severity=stop` or `critical`:

1. Say new entries stop now.
2. Allow only close/risk handling for open positions.
3. Ask user to confirm pause.
4. Ask user to restate the violation reason and next action.

普通 caution / yellow route does not block auto-commit by itself. `stop` / `critical` blocks new entries.

## Backend Unreachable

If CLI/API is unreachable:

1. Say TrendGo backend is not running and the record is not written.
2. Continue collecting fields in pending payload.
3. Provide the complete CLI command to run after backend starts.
4. Do not say `已记录`, `已写入`, or equivalent.

Backend start command:

```bash
cd app
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

## Legacy Fallback

Legacy natural-language backend parsing remains compatibility-only:

```bash
python3 scripts/openclaw_client.py --note "<original user text>" --auto-commit
```

Formal writes should use `--intent` + `--payload-json`.

