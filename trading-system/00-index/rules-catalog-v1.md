# 规则索引 v1

## 定位

本文件是 Agent 可引用的规则索引层，不替代原始规则文档。

原始规则仍以 `trading-system` 中的规则文件为准。本索引用于让 Agent 在盘前、盘中、复盘时稳定引用同一批规则编号。

## 字段说明

| 字段 | 含义 |
|---|---|
| `rule_id` | 稳定规则编号 |
| `type` | hard / soft / setup / process |
| `severity` | red / yellow / green |
| `trigger` | 触发条件 |
| `action` | 触发后的动作 |
| `source` | 原始来源文件 |

## 核心规则

| rule_id | type | severity | trigger | action | source |
|---|---|---|---|---|---|
| RISK-HARD-001 | hard | red | 单笔计划亏损达到 5% | 必须离场，不再讨论观点 | `04-risk-control/硬规则.md` |
| RISK-HARD-002 | hard | yellow | 单笔亏损达到 3% | 进入预警，准备执行止损 | `04-risk-control/硬规则.md` |
| RISK-HARD-003 | hard | yellow | 连续亏损 2 次 | 进入预警，只允许 A 级机会 | `04-risk-control/硬规则.md` |
| RISK-HARD-004 | hard | red | 连续亏损 3 次 | 停止交易 1 小时 | `04-risk-control/硬规则.md` |
| RISK-HARD-005 | hard | red | 单日亏损达到 10% | 当天停止交易，不再讨论新机会 | `04-risk-control/硬规则.md` |
| RISK-HARD-006 | hard | red | 当日交易次数超过 10 次 | 必须停止交易 | `04-risk-control/硬规则.md` |
| RISK-HARD-007 | hard | yellow | 当天盈利 5%+ | 后续只做 A 级机会 | `04-risk-control/硬规则.md` |
| RISK-HARD-008 | hard | yellow | 盈利 5%+ 后出现第一笔回吐 | 主动降频 | `04-risk-control/硬规则.md` |
| RISK-HARD-009 | hard | red | 风控线触发 | 只执行动作，不争论观点 | `04-risk-control/硬规则.md` |
| RISK-HARD-010 | hard | red | 明显情绪失控 | 先停 15-30 分钟，再做恢复状态确认 | `04-risk-control/硬规则.md` |
| RISK-SOFT-001 | soft | yellow | 明显情绪化 | 降仓、暂停或只观察 | `04-risk-control/软规则.md` |
| RISK-SOFT-002 | soft | yellow | 想报复性翻本 | 暂停，复述交易理由；不清楚就不做 | `04-risk-control/软规则.md` |
| RISK-SOFT-003 | soft | yellow | 连续乱单 | 降仓或暂停 | `04-risk-control/软规则.md` |
| RISK-SOFT-004 | soft | yellow | 没有清晰逻辑却想出手 | 只观察，不出手 | `04-risk-control/软规则.md` |
| ERROR-STOP-001 | hard | yellow | 明知没逻辑还出手 | 高度警惕，盘后单列复盘 | `04-risk-control/错误清单与停手条件.md` |
| ERROR-STOP-002 | hard | yellow | 止损拖延 | 高度警惕，盘后单列复盘 | `04-risk-control/错误清单与停手条件.md` |
| ERROR-STOP-003 | hard | yellow | 因怕错过而追高 | 高度警惕，盘后单列复盘 | `04-risk-control/错误清单与停手条件.md` |
| ERROR-STOP-004 | hard | yellow | 明显情绪化还加仓 | 高度警惕并降级 | `04-risk-control/错误清单与停手条件.md` |
| ERROR-STOP-005 | hard | red | 单笔到止损线仍不走 | 立即停手 | `04-risk-control/错误清单与停手条件.md` |
| ERROR-STOP-006 | hard | red | 连亏后报复性加仓 | 立即停手 | `04-risk-control/错误清单与停手条件.md` |
| ERROR-STOP-007 | hard | red | 当日亏损触及上限还想继续 | 立即停手 | `04-risk-control/错误清单与停手条件.md` |
| SETUP-ABC-001 | setup | red | 止损说不清 | 直接降为 C 级，不做 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-002 | setup | red | 只是怕错过 | 直接降为 C 级，不做 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-003 | setup | red | 连亏后想翻本 | 直接降为 C 级，不做 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-004 | setup | red | 情绪明显不稳 | 直接降为 C 级，不做 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-005 | setup | red | 方向、位置、确认三项里有两项说不清 | 直接降为 C 级，不做 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-006 | setup | green | 机会评分 10-12 分 | A 级机会，允许正常仓位但必须有止损 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-007 | setup | yellow | 机会评分 7-9 分 | B 级机会，只允许小仓试错 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-008 | setup | red | 机会评分 6 分及以下 | C 级机会，不做 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-ABC-009 | setup | yellow | 连亏或情绪不稳 | 所有机会自动降一级 | `05-setups/A-B-C级机会评分表.md` |
| SETUP-CHECK-001 | setup | red | 交易前检查清单有 2 个以上问题答不清 | 默认不做 | `05-setups/交易前检查清单.md` |
| OPTION-ABC-001 | setup | red | 美股期权没有止损权利金 | 直接降为 C 级，不做 | `05-setups/美股期权A-B-C级机会评分表.md` |
| OPTION-ABC-002 | setup | red | 财报或重大消息前后赌方向 | 直接降为 C 级，不做 | `05-setups/美股期权A-B-C级机会评分表.md` |
| OPTION-ABC-003 | setup | red | 合约点差明显过大 | 直接降为 C 级，不做 | `05-setups/美股期权A-B-C级机会评分表.md` |
| OPTION-ABC-004 | setup | green | 期权评分 10-14 分 | A 级机会，允许正常张数但先定止损权利金 | `05-setups/美股期权A-B-C级机会评分表.md` |
| OPTION-ABC-005 | setup | yellow | 期权评分 7-9 分 | B 级机会，只允许小张数试错 | `05-setups/美股期权A-B-C级机会评分表.md` |
| OPTION-ABC-006 | setup | red | 期权评分 6 分及以下 | C 级机会，不做 | `05-setups/美股期权A-B-C级机会评分表.md` |
| PROCESS-DAILY-001 | process | red | 没有日志 | 不算复盘完成 | `00-index/作战中枢.md` |
| PROCESS-DAILY-002 | process | red | 没有止损 | 不允许开仓 | `00-index/作战中枢.md` |
| PROCESS-DAILY-003 | process | red | 连亏后想用更大仓位翻本 | 禁止加大仓位 | `00-index/作战中枢.md` |
| PROCESS-DAILY-004 | process | red | 当天触发硬熔断 | 不再讨论新机会 | `00-index/作战中枢.md` |

## Agent 使用方式

盘中判断时按以下顺序执行：

1. 先检查 `hard` 规则，命中 red 时直接要求停手或禁止开仓。
2. 再检查 `setup` 规则，判断 A/B/C 机会。
3. 再检查 `soft` 规则，给出黄色提醒、降仓或暂停建议。
4. 最后记录命中的 `rule_id`，用于盘后复盘和周度统计。

## 维护规则

- 新增规则必须先改原始来源文件，再补充本索引。
- 禁止只改本索引、不改原文。
- `rule_id` 一旦用于真实记录，不再改名；需要废弃时新增状态说明。
- Agent 可以提出修改建议，但不能自动让规则生效。
