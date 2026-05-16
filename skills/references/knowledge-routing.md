# TrendGo Knowledge Routing

Use this reference when the user describes emotional or behavioral risk and the Agent should provide a concise training cue.

## Principle

In intraday flows, push only the relevant `first_action`. Do not dump full playbooks.

Knowledge routing should not block auto-commit by itself. Only `stop`, `critical`, or red hard-rule conditions block new entries. Ordinary caution/yellow routes can be shown before or after write depending on urgency.

## When To Route

Route when:

- `preTradeEmotion` is `fomo`, `recover_loss`, `defiant`, or `rushed`
- user says 怕错过, 想追回来, 坐不住, 不服气, 想翻本
- API returns red / stop / critical rules
- user describes abnormal emotional state after losses or overtrading

## Suggested Format

```text
[KR-002 | 报复交易] 先做一件事：下一笔重要交易前暂停，区分你是在恢复资本还是恢复情绪。
```

If the route is stop/critical, ask for pause confirmation and do not continue new-entry discussion.

## Common Routes

| Trigger | Route | First action |
|---|---|---|
| 怕错过 / 想追 / fomo | KR-001 | 先用一句话说明设置；说不清就跳过 |
| 想赚回来 / 翻本 / recover_loss | KR-002 | 下一笔重要交易前暂停，区分恢复资本还是恢复情绪 |
| 手痒 / 坐不住 / 冲动 | KR-003 | 入场前写无效点和一条反证 |
| 做太多了 / 过度交易 | KR-004 | 给最近交易贴标签：计划内、机会型、无聊驱动 |
| 犹豫 / 该做不敢做 | KR-005 | 判断犹豫来自设置不清，还是结果恐惧 |
| 刚亏完 / 止损后痛苦 | KR-006 | 区分流程内亏损和流程破坏造成的亏损 |
| 连续亏损 / 回撤扩大 | KR-007 | 先判断回撤来自优势失效、执行失败还是环境不匹配 |
| 情绪升级 / 越做越乱 | KR-008 | 下一笔重要交易前暂停，降仓或降频 |

