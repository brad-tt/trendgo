# TrendGo Workflows

Use this reference for context reads, multi-position close, end-of-day closeout, backend unreachable handling, and CLI result interpretation.

## Read Context

Use `tradeDate`, not `trade_date`.

```bash
curl "http://127.0.0.1:8526/api/agent/context?market=HK"
curl "http://127.0.0.1:8526/api/agent/context?market=US"
curl "http://127.0.0.1:8526/api/agent/context?tradeDate=2026-05-16&market=HK"
```

Summarize in Chinese; do not output raw JSON.

Important context content to inspect:

- current date / market / stage
- trade count and PnL
- open trades / unresolved positions
- discipline events and highest severity
- review and validation status

Read context before:

- answering "today status" questions
- deciding whether new entries are allowed
- EOD closeout
- review writing
- close trade when target is ambiguous

## Multi-Position Close

When the user says "平掉刚才那笔" or gives an ambiguous close and multiple open trades may exist:

1. Call `/api/agent/context`.
2. List open trades with instrument, direction/side, entry price, and `tradeId`.
3. Ask which one to close.
4. Submit `close_trade` only after `tradeId` is clear.

Example response:

```text
当前有 2 笔未平仓：
1. 54927 牛证，入场 0.054（ID: TT-2026-05-16-001）
2. 65882 牛证，入场 0.071（ID: TT-2026-05-16-002）
请问平的是哪一笔？
```

## EOD Closeout

Triggers: `今天交易结束了`, `准备复盘`, `可以收了吗`, `归档`, `今天能关了吗`.

Steps:

1. Read context.
2. Summarize facts in no more than 6 lines:
   - total trades / closed / open
   - total PnL
   - discipline event count and highest severity
   - review status and validation status
3. If `stop` or `critical` exists, say no more new entries today.
4. Ask at most 2-3 questions:
   - 今天最主要的执行问题是什么？
   - 明天只改一件事是什么？
   - 盘中记录和盘后复盘都完成了吗？
5. Write review only from user answers.
6. If validation is incomplete, guide user to complete premarket, intraday record, and postmarket review checks.

## Backend Unreachable

If CLI returns `API unreachable` or contract check fails:

1. Say TrendGo backend is not running and nothing was written.
2. Continue collecting fields in conversation pending state.
3. Provide a complete CLI command that can be run after backend starts.
4. Do not say "已记录" or "已写入".

Backend start command:

```bash
cd app
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

## CLI Result Interpretation

Success:

```text
已写入: 是
```

Treat as complete and summarize the written record.

Missing fields:

```text
已写入: 否
缺失字段:
```

Keep pending payload and ask for only the top 1-3 missing fields.

Stop/critical:

```text
### 停手处理
```

Stop new entries. Existing-position close and risk handling remain allowed.

Auto event:

```text
autoEventId / 联动纪律事件
```

Explain that it is an automatic risk review reminder, not rejection of the current trade.

