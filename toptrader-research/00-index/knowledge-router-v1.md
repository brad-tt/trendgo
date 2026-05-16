# 知识路由索引 v1

## 定位

本文件是 Agent 调用 `toptrader-research` 的路由层。

它不替代应急手册和能力包，只负责回答一个问题：当 Joe 爸描述某种状态时，Agent 应该推送哪一个最相关的剧本或训练包。

## 路由字段

| 字段 | 含义 |
|---|---|
| `route_id` | 稳定路由编号 |
| `distortion_type` | 失真大类 |
| `trigger_phrases` | 典型触发描述 |
| `primary_playbook` | 首选应急手册 |
| `capability_pack` | 对应长期训练包 |
| `first_action` | Agent 先推送的一个动作 |

## 第一批路由

| route_id | distortion_type | trigger_phrases | primary_playbook | capability_pack | first_action |
|---|---|---|---|---|---|
| KR-001 | fomo | 怕错过、想追、行情已经动了、别人都上车了 | `06-workflows/fear-of-missing-out-playbook-v1.md` | `08-reading-path/emotional-control-pack-v1.md` | 先用一句话说明设置；说不清就跳过 |
| KR-002 | revenge_trading | 想赚回来、想翻本、上一笔很痛、不能就这样输 | `06-workflows/revenge-trading-prevention-playbook-v1.md` | `08-reading-path/emotional-control-pack-v1.md` | 下一笔重要交易前暂停，识别是在恢复资本还是恢复情绪 |
| KR-003 | impulsive_entry | 手痒、坐不住、没无效点也想进、反应式入场 | `06-workflows/impulsive-trade-reduction-playbook-v1.md` | `08-reading-path/execution-discipline-pack-v1.md` | 入场前写无效点和一条反证 |
| KR-004 | overtrading | 交易太多、越做越碎、频率上升但质量下降 | `06-workflows/overtrading-control-playbook-v1.md` | `08-reading-path/execution-discipline-pack-v1.md` | 给最近交易贴标签：计划内、机会型、无聊驱动 |
| KR-005 | hesitation | 该做不敢做、有效设置出现但冻结、怕亏导致错过 | `06-workflows/hesitation-under-pressure-playbook-v1.md` | `08-reading-path/execution-discipline-pack-v1.md` | 判断犹豫来自设置不清，还是来自结果恐惧 |
| KR-006 | post_loss_emotion | 刚亏完、痛苦止损后、亏损感觉很个人化 | `06-workflows/post-loss-reset-playbook-v1.md` | `08-reading-path/emotional-control-pack-v1.md` | 区分流程内亏损和流程破坏造成的亏损 |
| KR-007 | drawdown_pressure | 连续亏损、回撤扩大、信心扭曲、风险行为变差 | `06-workflows/drawdown-recovery-playbook-v1.md` | `08-reading-path/risk-management-pack-v1.md` | 先判断回撤来自优势失效、执行失败还是环境不匹配 |
| KR-008 | tilt | 情绪升级、挫败、愤怒、越做越乱、进攻性突然上升 | `06-workflows/tilt-control-playbook-v1.md` | `08-reading-path/emotional-control-pack-v1.md` | 下一笔重要交易前暂停，降低仓位或频率 |
| KR-009 | decision_fatigue | 后半段判断变差、耐心下降、什么都显得紧迫 | `06-workflows/decision-fatigue-playbook-v1.md` | `08-reading-path/risk-management-pack-v1.md` | 如果心智清晰度下降，减少活动并简化决策 |
| KR-010 | low_conviction | 设置模糊但诱人、行动需求强于清晰度、低信念交易 | `06-workflows/low-conviction-trade-filter-playbook-v1.md` | `08-reading-path/execution-discipline-pack-v1.md` | 不能一句话说清设置、不知道无效点，就不交易 |
| KR-011 | missed_move_regret | 错过行情、后悔、想补偿、想追下一个机会 | `06-workflows/missed-move-recovery-playbook-v1.md` | `08-reading-path/emotional-control-pack-v1.md` | 区分后悔和机会；原始入场消失后不要编造替代入场 |
| KR-012 | overconfidence | 大赚后信心过高、连胜后想放大、标准开始放松 | `06-workflows/post-win-overconfidence-playbook-v1.md` | `08-reading-path/risk-management-pack-v1.md` | 近期盈利后不自动加仓，不降低标准 |
| KR-013 | regime_shift | 熟悉方法突然失效、价格行为变了、叙事变化很快 | `06-workflows/regime-shift-response-playbook-v1.md` | `08-reading-path/market-understanding-pack-v1.md` | 写一条市场环境笔记，区分执行错误和背景变化 |
| KR-014 | loss_of_selectivity | 太多设置看起来够好、平庸交易变多、标准下滑 | `06-workflows/loss-of-selectivity-playbook-v1.md` | `08-reading-path/execution-discipline-pack-v1.md` | 如果平均质量下降，提高门槛而不是降低门槛 |
| KR-015 | confidence_damage | 糟糕时期后不敢做、信心受损、对流程信任下降 | `06-workflows/confidence-rebuild-playbook-v1.md` | `08-reading-path/review-and-learning-pack-v1.md` | 用更小、更清晰、更符合流程的交易重建证据 |

## 能力包路由

| capability | 什么时候用 | pack |
|---|---|---|
| execution_discipline | 知道该怎么做但做不到，常见犹豫、冲动、流程破坏 | `08-reading-path/execution-discipline-pack-v1.md` |
| emotional_control | 盈亏后情绪波动大，下一笔被情绪污染 | `08-reading-path/emotional-control-pack-v1.md` |
| risk_management | 无效点不清、仓位过大、亏损纪律弱 | `08-reading-path/risk-management-pack-v1.md` |
| review_learning | 有记录但没有行为修正，重复错误没有下降 | `08-reading-path/review-and-learning-pack-v1.md` |
| market_understanding | 经常误读环境，执着单一故事，适应慢 | `08-reading-path/market-understanding-pack-v1.md` |

## Agent 使用方式

1. 先根据用户描述匹配一个 `route_id`。
2. 如果同时命中多个路由，只推送最紧急的一个；优先级为：硬风控风险、报复交易、情绪失控、FOMO、过度交易。
3. 先推 `first_action`，不要一次推完整材料。
4. 用户愿意继续时，再打开 `primary_playbook` 的对应问题和检查清单。
5. 周复盘时再推荐 `capability_pack`，不要在盘中推长材料。

## 维护规则

- 新增路由必须对应一个真实存在的 playbook 或能力包。
- 不把整篇研究材料复制进本文件。
- Agent 对失真的判断先标记为“疑似”，由 Joe 爸确认后才进入正式统计。
- 每周只选择一个主要能力包作为训练焦点。
