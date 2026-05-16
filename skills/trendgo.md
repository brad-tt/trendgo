---
name: trendgo
description: Record and review trading activity in TrendGo from natural language. Use when the user wants to log an open trade, close trade, rule/discipline event, daily review, validation, premarket plan, stop-flow handling, or asks about TrendGo trading records. Trigger examples include 记一笔, 开仓, 平仓, 复盘, 纪律事件, 牛证, 熊证, call, put, option, 今天交易结束了.
---

# TrendGo Trading Skill

TrendGo is a local-first trading record and review workbench at `app`.
Use this skill as the Agent layer: parse the user's natural language, keep incomplete fields in conversation state, and write only structured payloads to TrendGo.

## Backend

Default backend:

```bash
cd app
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

Preferred CLI:

```bash
cd app
python3 scripts/openclaw_client.py --intent <intent> --market HK --payload-json '{"fields": {...}}' --note "<original user text>"
```

Use `committed=true` / CLI `已写入: 是` as the only completion signal. If the API is unreachable, tell the user to start TrendGo or start the local backend when appropriate.

## Intent Routing

- `open_trade`: user describes buying/opening a position.
- `close_trade`: user describes selling/closing/exiting a position.
- `rule_event`: user reports discipline/risk/emotion violation or forced pause/stop.
- `review`: user gives postmarket review, daily issue, next-day fix, validation, or says trading has ended.

Do not submit vague market commentary as a record. Ask whether it is a trade, rule event, or review.

## Conversation Pending State

When fields are missing, do not write a database draft. Keep a pending payload in the current conversation:

- `intent`, `market`, `tradeDate`
- `rawNotes[]`
- `fields`
- `missingFields`

Tell the user: `这笔还没有写入；你补完这些字段后，我会直接写入正式记录。`

Merge later user replies into the same pending payload. Once required fields are complete, submit automatically. Do not ask for a second confirmation unless:

- user says `先别写`, `只是讨论`, `等我确认`, or similar
- a field conflicts with the pending payload
- multiple open trades make close target ambiguous
- existing context or API feedback has `stop` / `critical`
- intent is uncertain

## Missing Field Priority

Ask for only the most important 1-3 gaps.

1. Core write/risk fields: time, instrument code, entry/exit price, position size, stop loss or invalidation condition.
2. Trade quality fields: setup type, direction, location, confirmation, certificate filter, session, ABC grade.
3. Review extras: emotion, screenshots, notes, detailed explanation.

If the user says `止损清楚，还没有出现止损`, this is not a stop value. Ask: `我需要的是止损价或失效条件，不是当前是否已经触发止损。`

## Field Rules

Never invent price, size, stop, instrument code, trade id, emotion, or review conclusions.

Normalize common expressions before commit:

- `突破回踩`, `趋势回踩`, `回踩守住`, `回踩确认` -> `setupType=trend_pullback`
- `开盘突破`, `突破确认`, `确认突破` -> `setupType=opening_breakout`
- `假突破追单`, `追单` -> `setupType=false_breakout_chase`
- `控制不住`, `冲动`, `手痒` -> `emotionState=impulsive`
- `控制不住`, `冲动`, `急着进` -> `preTradeEmotion=rushed`
- `不服气`, `硬要做` -> `preTradeEmotion=defiant`
- `怕错过` -> `preTradeEmotion=fomo`
- `想赚回来`, `翻本` -> `preTradeEmotion=recover_loss`

Do not infer `postTradeEmotion`. Submit it only when the user explicitly states the emotion after exiting; otherwise omit it.

## Commit Examples

Open trade:

```bash
python3 scripts/openclaw_client.py \
  --intent open_trade \
  --market HK \
  --note "54927牛证入场价0.054买3手，止损0.044，A级，趋势回踩，方向位置确认都清楚" \
  --payload-json '{"fields":{"tradeTime":"14:00","sessionWindow":"mid_session","direction":"long","certificateSide":"bull","instrumentCode":"54927","setupType":"trend_pullback","abcGrade":"A","directionClear":true,"locationOk":true,"confirmationOk":true,"riskClear":true,"certificateFilterPassed":true,"entryPrice":0.054,"stopLoss":0.044,"positionSize":"3","followedPlan":true,"entryReason":"方向位置确认都清楚","instrumentType":"bull_bear_certificate","underlying":"HSI"}}'
```

Close trade:

```bash
python3 scripts/openclaw_client.py \
  --intent close_trade \
  --market HK \
  --note "14:30 0.060 平仓，信号消失" \
  --payload-json '{"fields":{"exitTime":"14:30","exitPrice":0.060,"exitReason":"信号消失"}}'
```

If the close includes `止损慢`, `扛单`, `未按计划止损`, or similar execution violation, include:

- `ruleViolation=true`
- `violationNote="<user's violation fact>"`

Do not only write a separate rule event and lose the trade-level violation.

Rule event:

```bash
python3 scripts/openclaw_client.py \
  --intent rule_event \
  --market HK \
  --payload-json '{"fields":{"eventTime":"14:35","eventType":"emotion_trigger","severity":"stop","triggerReason":"亏损后想追回","actionTaken":"暂停交易并复述规则"}}'
```

Review:

```bash
python3 scripts/openclaw_client.py \
  --intent review \
  --market HK \
  --payload-json '{"fields":{"bestTradeNote":"按计划止损","worstTradeNote":"入场偏急","executionIssue":"没有等二次确认","emotionIssue":"怕错过","riskIssue":"止损前犹豫","nextDayOneFix":"只做确认后的机会"}}'
```

## Risk And Feedback

If API response includes `autoEventId`, explain that it is an automatic risk review reminder, not a rejection of the trade.

If response or day read-back has `severity=stop` / `critical`:

1. Say new entries stop now.
2. Ask user to confirm pause.
3. Allow only close/risk handling for open positions.
4. Ask user to restate the violation reason and next action.

`observe_first` is not a violation by itself. If a clear signal appears and direction/location/confirmation/risk/filter pass, record the trade without treating observation as `forced_pause`.

## End-Of-Day Review

When the user says `今天交易结束了` or after HK close:

1. Read today's TrendGo context.
2. Summarize trade count, PnL, discipline events, review status, validation status.
3. Ask 2-3 short questions: main issue, one fix for tomorrow, whether intraday records and postmarket review are complete.
4. If stop/critical exists, say no more new entries today.
5. Write review/validation only from user-confirmed content.

Use Codex automations only if the user asks to schedule recurring premarket/review reminders.

