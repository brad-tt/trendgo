# TrendGo Fields And Enums

Use this reference when constructing payloads, checking enum values, or resolving uncertain field mappings.

## Defaults

- `market=HK` may be used when no market is stated and the workflow is HK-focused.
- HK bull/bear certificates: `instrumentType=bull_bear_certificate`.
- HK default underlying: `underlying=HSI`.
- Obvious 牛证 -> `certificateSide=bull`; obvious 熊证 -> `certificateSide=bear`.
- Obvious call/put -> `certificateSide=call` / `certificateSide=put`.

Do not infer price, size, stop, instrument code, trade id, emotion, or review conclusion.

## Session Window

| User expression | Enum |
|---|---|
| 开盘 / 早盘 / 9点多 / 开盘前30分钟 | `opening_30m` |
| 盘中 / 午后 / 中段 | `mid_session` |
| 尾盘 / 收盘前 / 3点后 / 下午3点 | `late_session` |

## Setup Type

| User expression | Enum |
|---|---|
| 突破回踩 / 趋势回踩 / 回踩守住 / 回踩确认 / 回踩站回 | `trend_pullback` |
| 开盘突破 / 突破确认 / 确认突破 | `opening_breakout` |
| 回踩站回压力位 / 支撑反转 | `pullback_reclaim` |
| 假突破追单 / 追单 | `false_breakout_chase` |
| 止损后反手 / 打止损后追 | `reverse_after_stop` |
| 观察 / 先看 / 只看 | `clear_observe` |
| 美股 ORB / 开盘区间突破 | `orb_continuation` |
| VWAP 回踩 / 均价线回踩 | `vwap_reclaim` |
| 支撑反转 / 双底 | `support_reversal` |
| 假跌破 / failed breakdown | `failed_breakdown` |
| 追 IV / 财报波动 | `iv_chase` |
| 冲动 / 手痒 / 无逻辑 | `emotional_trade` |
| 报复 / 翻本交易 | `revenge_trade` |
| 手痒单 / 无效逻辑 | `itchy_hand_trade` |
| 盈利回吐 / 手感好继续加 | `profit_giveback` |
| 其他 | `other` |

## Emotion Fields

### emotionState

Valid values: `stable`, `anxious`, `revenge`, `impulsive`.

| User expression | Enum |
|---|---|
| 控制不住 / 冲动 / 手痒 | `impulsive` |
| 报复 / 翻本 / 赚回来 | `revenge` |
| 焦虑 / 紧张 | `anxious` |
| 稳定 / 平静 | `stable` |

### preTradeEmotion

Valid values: `stable`, `rushed`, `defiant`, `fomo`, `recover_loss`.

| User expression | Enum |
|---|---|
| 控制不住 / 冲动 / 手痒 / 急着进 / 着急 | `rushed` |
| 不服气 / 不服 / 硬要做 / 硬来 | `defiant` |
| 怕错过 / 想追 | `fomo` |
| 想赚回来 / 翻本 / 赚回来 | `recover_loss` |
| 稳定 / 平静 | `stable` |

### postTradeEmotion

Only submit when the user explicitly states the emotion after exiting.

| User expression | Enum |
|---|---|
| 后悔 | `regret` |
| 满意 / 踏实 | `satisfied` |
| 着急 | `rushed` |
| 不服 | `defiant` |
| 稳定 / 平静 | `stable` |

## Open Trade Fields

| Field | Meaning | Required |
|---|---|---|
| `tradeTime` | Open time, HH:MM | yes |
| `sessionWindow` | `opening_30m` / `mid_session` / `late_session` | yes |
| `direction` | `long` or `short` | yes |
| `certificateSide` | HK `bull`/`bear`; US `call`/`put` | yes |
| `instrumentCode` | Code or ticker | yes |
| `setupType` | normalized setup enum | yes |
| `abcGrade` | `A` / `B` / `C` | yes |
| `entryPrice` | Entry price | yes |
| `stopLoss` | Stop price or option premium stop | yes |
| `positionSize` | Size, lots, shares, or contracts as user stated | yes |
| `entryReason` | Short entry reason | yes |
| `instrumentType` | `bull_bear_certificate` or `stock_option` | yes |
| `underlying` | `HSI`, ticker, or `other` | yes |
| `directionClear` | direction clear | yes |
| `locationOk` | location acceptable | yes |
| `confirmationOk` | confirmation present | yes |
| `riskClear` | stop/risk clear | yes |
| `certificateFilterPassed` | certificate/contract filter passed | yes |
| `followedPlan` | followed plan | optional, default true |
| `preTradeEmotion` | opening emotion | optional |
| `emotionState` | intraday emotion state | optional |
| `targetPrice` | target price | optional |
| `abnormalScenario` | abnormal scenario, default `none` | optional |

## Close Trade Fields

| Field | Meaning | Required |
|---|---|---|
| `exitTime` | Exit time, HH:MM | yes |
| `exitPrice` | Exit price | yes |
| `exitReason` | Exit reason | yes |
| `tradeId` | target trade id | required when multiple open trades |
| `postTradeEmotion` | after-exit emotion | optional; only if explicit |
| `ruleViolation` | trade-level execution violation | optional |
| `violationNote` | violation fact | required if `ruleViolation=true` |

If the close includes stop delay, holding past stop, 扛单, or 未按计划止损, set `ruleViolation=true` and include `violationNote`.

## Rule Event Fields

| Field | Meaning | Required |
|---|---|---|
| `eventTime` | Event time, HH:MM | yes |
| `eventType` | event type enum | yes |
| `severity` | `warning` / `stop` / `critical` | yes |
| `triggerReason` | trigger reason | yes |
| `actionTaken` | action taken | yes |
| `followUpNote` | follow-up note | optional |
| `linkedTradeId` | linked trade id | optional |

### eventType

| User expression | Enum |
|---|---|
| 违规了 / 没按规则做 | `rule_violation` |
| 情绪触发 / 情绪失控 | `emotion_trigger` |
| 强制暂停 / 主动暂停 / 先停一下 | `forced_pause` |
| 停手 / 今天不做了 / 强制停止 | `forced_stop` |
| 做太多了 / 过度交易 | `overtrade_signal` |

### severity

| User expression | Enum |
|---|---|
| 注意 / 提醒 / 黄色警告 | `warning` |
| 停手 / 红色 / 要求暂停 | `stop` |
| 最严重 / 必须停 / 严重违规 | `critical` |

## Review Fields

| Field | Meaning | Required |
|---|---|---|
| `bestTradeNote` | best execution today | yes |
| `worstTradeNote` | worst execution today | yes |
| `executionIssue` | execution issue | yes |
| `emotionIssue` | emotion issue | yes |
| `riskIssue` | risk issue | yes |
| `nextDayOneFix` | one fix for next day | yes |
| `marketIssue` | market judgment issue | optional |
| `setupIssue` | setup/opportunity issue | optional |

Review conclusions must come from user-confirmed content. PnL and trade count are computed by backend from the day record.

