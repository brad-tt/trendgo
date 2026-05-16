# TrendGo CLI Examples

Use these examples when the user needs a concrete command or when reconstructing a pending payload after backend recovery.

## HK Open Trade

```bash
python3 scripts/openclaw_client.py --intent open_trade --market HK \
  --note "54927牛证，14点入场价0.054，买3手，止损0.044，A级，趋势回踩" \
  --payload-json '{"fields":{"tradeTime":"14:00","sessionWindow":"mid_session","direction":"long","certificateSide":"bull","instrumentCode":"54927","setupType":"trend_pullback","abcGrade":"A","directionClear":true,"locationOk":true,"confirmationOk":true,"riskClear":true,"certificateFilterPassed":true,"entryPrice":0.054,"stopLoss":0.044,"positionSize":"3","followedPlan":true,"entryReason":"方向位置确认都清楚","instrumentType":"bull_bear_certificate","underlying":"HSI"}}'
```

## HK Close Trade

Single open trade can omit `tradeId`:

```bash
python3 scripts/openclaw_client.py --intent close_trade --market HK \
  --note "14:30 0.060 平仓，信号消失" \
  --payload-json '{"fields":{"exitTime":"14:30","exitPrice":0.060,"exitReason":"信号消失"}}'
```

## HK Close With Violation

```bash
python3 scripts/openclaw_client.py --intent close_trade --market HK \
  --note "15:00 平仓，0.038 出，应在0.044止损但拖延了" \
  --payload-json '{"fields":{"exitTime":"15:00","exitPrice":0.038,"exitReason":"最终止损","ruleViolation":true,"violationNote":"应在0.044止损，拖延到0.038才出场"}}'
```

## US Option Open

```bash
python3 scripts/openclaw_client.py --intent open_trade --market US \
  --note "AAPL 200 call，权利金3.20，买2张，止损权利金1.50，A级趋势回踩" \
  --payload-json '{"fields":{"tradeTime":"10:30","sessionWindow":"opening_30m","direction":"long","certificateSide":"call","instrumentCode":"AAPL","setupType":"trend_pullback","abcGrade":"A","directionClear":true,"locationOk":true,"confirmationOk":true,"riskClear":true,"certificateFilterPassed":true,"entryPrice":3.20,"stopLoss":1.50,"positionSize":"2","followedPlan":true,"entryReason":"趋势回踩，方向位置清楚","instrumentType":"stock_option","underlying":"AAPL"}}'
```

## Rule Event

```bash
python3 scripts/openclaw_client.py --intent rule_event --market HK \
  --payload-json '{"fields":{"eventTime":"14:35","eventType":"emotion_trigger","severity":"stop","triggerReason":"亏损后想追回","actionTaken":"暂停交易并复述规则"}}'
```

## Review

```bash
python3 scripts/openclaw_client.py --intent review --market HK \
  --payload-json '{"fields":{"bestTradeNote":"按计划止损","worstTradeNote":"入场偏急","executionIssue":"没有等二次确认","emotionIssue":"怕错过","riskIssue":"止损前犹豫","nextDayOneFix":"只做确认后的机会"}}'
```

