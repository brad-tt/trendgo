# TrendGo Skill 使用说明

## 现在的产品结构

TrendGo 现在分成三层：

1. **用户**
   - 用自然语言说交易、平仓、纪律事件或复盘。
   - 不需要自己记字段名，也不需要直接操作数据库。

2. **Agent / Skill**
   - Agent 是自然语言理解层。
   - Agent 负责判断用户意图，并把口述整理成结构化字段。
   - 字段不够时，Agent 必须追问；不能编造价格、仓位、止损、标的代码、交易编号。
   - 字段齐全后，Agent 调用 TrendGo Skill 的 CLI 结构化提交。

3. **TrendGo 后端**
   - 后端不再负责从自然语言里猜字段。
   - 后端负责校验字段、计算盈亏、自动创建工作台、写入 SQLite/记录文件、返回写入结果。
   - 后端仍保留必要校验，避免错误数据入库。

新的主链路是：

```text
用户口述
  -> Agent 判断意图
  -> Agent 提取结构化字段
  -> 缺字段则追问
  -> 字段齐全后调用 Skill CLI
  -> /api/agent/commit 写入
  -> 返回 committed / missingFields / message
```

只有返回 `committed=true` 或 CLI 显示 `已写入: 是`，才算真正完成记录。

## 会话内待补

字段不足时不写数据库草稿，也不写正式交易。Agent 只在当前对话里保留 pending payload：

```text
intent / market / tradeDate / rawNotes[] / fields / missingFields
```

Agent 追问时要明确说明：

```text
这笔还没有写入；你补完这些字段后，我会直接写入正式交易。
```

用户补齐字段后，Agent 合并字段并自动调用结构化提交，不需要用户额外说“确认写入”。如果用户说“先别写”“只是讨论”“等我确认”，或者字段前后冲突，则改为显式确认。

## 支持的四类意图

### 1. 开仓：`open_trade`

用于记录一笔新交易。

常见口述：

```text
54927牛证，14点入场价0.054，买3手，止损0.044，A级机会，方向位置确认都清楚。
```

Agent 需要提取的核心字段：

- `tradeTime`：开仓时间
- `sessionWindow`：交易时段，例如 `mid_session`
- `direction`：`long` 或 `short`
- `certificateSide`：`bull` / `bear` / `call` / `put`
- `instrumentCode`：标的代码
- `setupType`：形态
- `abcGrade`：`A` / `B` / `C`
- `entryPrice`：入场价
- `stopLoss`：止损
- `positionSize`：仓位数量
- `entryReason`：入场理由
- `instrumentType`：工具类型
- `underlying`：底层标的

提交示例：

```bash
cd app

python3 scripts/openclaw_client.py \
  --intent open_trade \
  --market HK \
  --note "54927牛证，14点入场价0.054，买3手，止损0.044，A级机会，方向位置确认都清楚。" \
  --payload-json '{"fields":{"tradeTime":"14:00","sessionWindow":"mid_session","direction":"long","certificateSide":"bull","instrumentCode":"54927","setupType":"opening_breakout","abcGrade":"A","directionClear":true,"locationOk":true,"confirmationOk":true,"riskClear":true,"certificateFilterPassed":true,"entryPrice":0.054,"stopLoss":0.044,"positionSize":"3","followedPlan":true,"entryReason":"方向位置确认都清楚","instrumentType":"bull_bear_certificate","underlying":"HSI"}}'
```

如果当天工作台不存在，后端会自动创建。

## 2. 平仓：`close_trade`

用于给已有交易补平仓信息。

常见口述：

```text
14:30 0.060 平仓，信号消失。
```

核心字段：

- `tradeId`：交易编号。只有一笔未平仓时可以省略。
- `exitTime`：平仓时间
- `exitPrice`：平仓价
- `exitReason`：平仓原因
- `postTradeEmotion`：平仓后情绪，可选

提交示例：

```bash
python3 scripts/openclaw_client.py \
  --intent close_trade \
  --market HK \
  --note "14:30 0.060 平仓，信号消失。" \
  --payload-json '{"fields":{"exitTime":"14:30","exitPrice":0.060,"exitReason":"信号消失","postTradeEmotion":"stable"}}'
```

规则：

- 如果只有一笔未平仓交易，后端会自动匹配。
- 如果有多笔未平仓交易，后端会返回缺 `trade_id`，Agent 必须追问用户要平哪一笔。
- 平仓不会自动创建空工作台，因为没有交易可平。
- 如果平仓阶段出现止损拖延、扛单、未按计划止损等违规事实，Agent 应在平仓 payload 中提交 `ruleViolation=true` 和 `violationNote`，让违规事实落到目标交易上。

盈亏计算统一为：

```text
(exitPrice - entryPrice) * positionSize
```

不再按 `direction` 翻转。

## 3. 纪律事件：`rule_event`

用于记录违规、情绪触发、暂停、停手等事件。

常见口述：

```text
14:35 亏损后想追回，暂停交易，先复述规则。
```

核心字段：

- `eventTime`
- `eventType`
- `severity`
- `triggerReason`
- `actionTaken`
- `followUpNote`，可选
- `linkedTradeId`，可选

提交示例：

```bash
python3 scripts/openclaw_client.py \
  --intent rule_event \
  --market HK \
  --payload-json '{"fields":{"eventTime":"14:35","eventType":"emotion_trigger","severity":"stop","triggerReason":"亏损后想追回","actionTaken":"暂停交易并复述规则"}}'
```

如果目标日期工作台不存在，后端会自动创建。

## 4. 复盘：`review`

用于写盘后复盘。

常见口述：

```text
今天最好的是按计划止损，最差是入场太急，明天只改一件事：等二次确认。
```

核心字段：

- `bestTradeNote`
- `worstTradeNote`
- `executionIssue`
- `emotionIssue`
- `riskIssue`
- `nextDayOneFix`
- `marketIssue`，可选
- `setupIssue`，可选

提交示例：

```bash
python3 scripts/openclaw_client.py \
  --intent review \
  --market HK \
  --payload-json '{"fields":{"bestTradeNote":"按计划止损","worstTradeNote":"入场偏急","executionIssue":"没有等二次确认","emotionIssue":"怕错过","riskIssue":"止损前犹豫","nextDayOneFix":"只做确认后的机会"}}'
```

复盘的 `pnl` 和 `tradeCount` 可以由后端基于当天交易默认生成。

## Agent 使用规则

### 必须追问的情况

以下字段不能猜：

- 价格：入场价、平仓价、止损价
- 仓位：数量、手数
- 标的代码
- 交易编号
- 用户没有明确表达的平仓原因或复盘结论

例子：

```text
用户：54927牛证买3手，A级机会。
Agent：还缺入场价和止损价，这笔暂时没有写入。入场价和止损是多少？
```

### 可以默认的情况

低风险上下文字段可以默认：

- `market=HK`
- 港股牛熊证默认 `instrumentType=bull_bear_certificate`
- 港股默认 `underlying=HSI`
- 明显牛证可设 `certificateSide=bull`
- 明显熊证可设 `certificateSide=bear`

但默认值要符合用户原话，不能反向猜。

## CLI 返回怎么读

成功写入：

```text
已写入: 是
结果: Agent 开仓记录已写入。
```

字段不足：

```text
已写入: 否
缺失字段:
- 入场价
- 止损

下一步：请补齐以上字段后再次提交；本次没有写入。
```

这时 Agent 应该继续追问用户，不要说“已记录”。

## Legacy fallback

旧的后端自然语言解析入口还保留，但不是主路径：

```bash
python3 scripts/openclaw_client.py --note "<用户原始口述>" --auto-commit
```

只在临时兼容或排查问题时使用。正式使用应该走 `--intent` + `--payload-json`。

## 启动后端

```bash
cd app
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

如果 CLI 返回 API unreachable，先确认后端是否启动、端口是否是 `8526`。
