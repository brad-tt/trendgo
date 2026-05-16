# TrendGo US Options

Use this reference when the user mentions US market, stock options, call, put, SPY, QQQ, AAPL, TSLA, NVDA, or option premium.

## Market Mapping

| Concept | HK bull/bear certificate | US stock option |
|---|---|---|
| `market` | `HK` | `US` |
| `instrumentType` | `bull_bear_certificate` | `stock_option` |
| `certificateSide` | `bull` / `bear` | `call` / `put` |
| `underlying` | `HSI` or component | US ticker |
| `stopLoss` | certificate stop price | option premium stop |
| `positionSize` | lots / units | contracts |

Do not default to `US`; the user should mention a US ticker, option, call/put, or US context.

## Required Open Fields

Use the same `open_trade` fields as the main schema, with:

- `market=US`
- `instrumentType=stock_option`
- `certificateSide=call` or `put`
- `instrumentCode` as ticker or option identifier stated by user
- `underlying` as ticker
- `entryPrice` as option premium
- `stopLoss` as stop premium
- `positionSize` as contract count

## Risk Notes

Apply option-specific caution when:

- no option premium stop is stated
- user is betting direction around earnings or major events
- spread is too wide
- contract filter is unclear
- user chases IV

Do not invent strike, expiry, IV, or spread. If user does not provide them and they matter for the task, ask.

## Example

```bash
python3 scripts/openclaw_client.py --intent open_trade --market US \
  --note "AAPL 200 call，权利金3.20，买2张，止损权利金1.50，A级趋势回踩" \
  --payload-json '{"fields":{"tradeTime":"10:30","sessionWindow":"opening_30m","direction":"long","certificateSide":"call","instrumentCode":"AAPL","setupType":"trend_pullback","abcGrade":"A","directionClear":true,"locationOk":true,"confirmationOk":true,"riskClear":true,"certificateFilterPassed":true,"entryPrice":3.20,"stopLoss":1.50,"positionSize":"2","followedPlan":true,"entryReason":"趋势回踩，方向位置清楚","instrumentType":"stock_option","underlying":"AAPL"}}'
```

PnL formula remains `(exitPrice - entryPrice) * positionSize`. Backend handles display conversion where applicable.

