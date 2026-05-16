# TrendGo 顶层设计 v1

> 文档定位：这是整个系统的骨架文件。它不描述实现细节，只定义框架、数据流向、模块边界和运转机制。所有后续建设都应对照这份文档校准方向。

> 当前状态：这是产品愿景参考，不是当前实现契约。当前已落地的接口、端口、写入路径和回归命令以根目录 `README.md`、`app/README.md` 和 `TOPTRADER_SKILL_USAGE.md` 为准。文中提到的新增表和能力看板仍属于后续规划，尚未默认实施。

---

## 一、系统定位（一句话）

**一个以 AI Agent 为主交互界面、以结构化数据库为核心、以仪表盘为结果呈现的交易员共同进化系统。**

它不是工具集合，而是一个有机运转的闭环：你通过和 AI 对话完成每日交易记录与复盘，系统通过积累的真实数据不断校准自身，逐步形成专属于你的交易认知模型。

---

## 二、三个原材料系统的定位重划

在接入 Agent 层之前，已有三个系统，现在重新定义它们各自的角色：

| 系统 | 原角色 | 新角色 |
|---|---|---|
| `trading-system` | Obsidian 知识库，手动查阅 | **规则引擎的原料库**：硬规则、软规则、ABC评级、风控触发条件，以结构化格式注入 Agent System Prompt |
| `trade_dog`（TrendGo 前身） | 网页工具，手动填表 | **数据容器 + 展示层**：SQLite 是唯一真相来源，前端只负责只读展示 |
| `toptrader-research` | 静态文档，自行翻阅 | **动态知识路由库**：失真模式库、能力地图、剧本集，由 Agent 按需调取推送，不再靠人主动翻 |

---

## 三、整体架构（四层结构）

```
┌─────────────────────────────────────────────────────┐
│  Layer 0：交互层                                      │
│  Claude Code / Agent 对话界面                         │
│  → 你用自然语言输入，Agent 理解、解析、确认、反馈       │
└───────────────────────┬─────────────────────────────┘
                        │ 结构化写入 / 规则调取
┌───────────────────────▼─────────────────────────────┐
│  Layer 1：智能处理层                                  │
│  Agent 内核（System Prompt + Tools）                  │
│  ├─ 意图识别模块：判断盘前/开仓/平仓/事件/复盘         │
│  ├─ 信息提取模块：从自然语言映射到数据库字段            │
│  ├─ 规则校验模块：对照 trading-system 硬规则实时校验   │
│  ├─ 失真识别模块：匹配 toptrader-research 失真模式     │
│  └─ 分析生成模块：周报、月度 meta-review 生成          │
└───────────────────────┬─────────────────────────────┘
                        │ 读 / 写
┌───────────────────────▼─────────────────────────────┐
│  Layer 2：数据层                                      │
│  SQLite（toptrader.db）— 唯一真相来源                  │
│  ├─ 现有表：daily_record / trade_record /             │
│  │          rule_event / daily_review                 │
│  └─ 新增表：distortion_log / agent_memory /           │
│             capability_snapshot / system_config       │
└───────────────────────┬─────────────────────────────┘
                        │ 只读查询
┌───────────────────────▼─────────────────────────────┐
│  Layer 3：展示层                                      │
│  TrendGo Web 前端（React + FastAPI）                 │
│  → 仪表盘：盈亏概览 / 失真趋势 / 能力进展 / 规则遵守率  │
│  → 历史复查：交易流水 / 复盘归档 / 规则事件时间线       │
│  → 系统状态：当前 Agent 版本 / 规则配置 / 进化提案待确认│
└─────────────────────────────────────────────────────┘
```

---

## 四、数据架构（完整 Schema 设计）

### 4.1 现有表（保留，小幅扩展字段）

**`daily_record`** — 每日交易日记录（盘前计划）
- 现有字段完整，保留
- 新增：`distortion_count INTEGER DEFAULT 0`（当日识别到的失真次数）
- 新增：`capability_stage TEXT DEFAULT ''`（当日能力阶段标记）

**`trade_record`** — 每笔交易
- 现有字段完整，保留
- 新增：`distortion_type TEXT DEFAULT ''`（这笔交易关联的失真类型，如 FOMO / revenge / impulsive）
- 新增：`agent_flag TEXT DEFAULT ''`（Agent 对这笔交易的标注，如 "硬规则违反" / "软规则黄色" / "规范"）

**`rule_event`** — 纪律事件
- 现有字段完整，保留

**`daily_review`** — 盘后复盘
- 现有字段完整，保留
- 新增：`weekly_pattern_note TEXT DEFAULT ''`（本日复盘被纳入周分析后的补注）

### 4.2 新增表

**`distortion_log`** — 失真事件明细（系统进化的核心原材料）

```sql
CREATE TABLE distortion_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_date TEXT NOT NULL,
  event_time TEXT NOT NULL,
  market TEXT NOT NULL,
  
  distortion_type TEXT NOT NULL,
  -- 类型枚举（来自 toptrader-research 失真模式地图）：
  -- loss_driven / profit_driven / urgency_driven /
  -- pressure_driven / regime_shift / fatigue_driven
  
  distortion_subtype TEXT NOT NULL DEFAULT '',
  -- 子类型，如：revenge_trading / fomo / overconfidence /
  -- impulsive_entry / tilt / decision_fatigue
  
  trigger_context TEXT NOT NULL DEFAULT '',
  -- 触发情境描述（Agent 从自然语言中提取）
  
  playbook_pushed TEXT NOT NULL DEFAULT '',
  -- Agent 推送的对应剧本名称
  
  user_acknowledged INTEGER NOT NULL DEFAULT 0,
  -- 用户是否确认了这个失真标记（0=未确认/1=确认/2=否认）
  
  playbook_followed INTEGER,
  -- 用户是否真的按剧本处理（NULL=未记录/0=没有/1=有）
  
  linked_trade_id TEXT NOT NULL DEFAULT '',
  -- 关联的 trade_record.trade_id（如有）
  
  severity TEXT NOT NULL DEFAULT 'yellow',
  -- red（已影响行为）/ yellow（风险信号）/ green（已自我纠正）
  
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**`agent_memory`** — 用户个人画像（Agent 的长期记忆，随使用持续更新）

```sql
CREATE TABLE agent_memory (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  
  -- 能力阶段
  current_stage TEXT NOT NULL DEFAULT 'stabilizing',
  -- stabilizing（稳定交易员）/ building_edge（建立优势）/ advanced
  
  stage_updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- 主要失真档案（JSON 格式，存储每种失真的频次和趋势）
  distortion_profile TEXT NOT NULL DEFAULT '{}',
  -- 示例：{"fomo": {"count_30d": 8, "trend": "improving"},
  --        "revenge_trading": {"count_30d": 3, "trend": "stable"}}
  
  -- 当前本周训练焦点
  weekly_focus TEXT NOT NULL DEFAULT '',
  -- 对应 toptrader-research 的能力包名称
  
  -- 高风险情境档案（从数据中发现的个人规律）
  high_risk_patterns TEXT NOT NULL DEFAULT '{}',
  -- 示例：{"after_14:00": "情绪稳定性下降", "after_2_losses": "报复交易风险高"}
  
  -- 有效剧本排序（按历史使用效果排序）
  effective_playbooks TEXT NOT NULL DEFAULT '[]',
  
  -- 当前 System Prompt 版本号
  system_prompt_version TEXT NOT NULL DEFAULT 'v1.0',
  
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**`capability_snapshot`** — 能力阶段快照（月度，记录进化轨迹）

```sql
CREATE TABLE capability_snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_date TEXT NOT NULL,        -- 快照日期（月度）
  
  -- 五大能力评分（1-5 分，基于过去 30 天行为数据）
  market_understanding REAL,          -- 市场理解
  edge_identification REAL,           -- 优势识别
  risk_management REAL,               -- 风险管理
  execution_discipline REAL,          -- 执行纪律
  emotional_regulation REAL,          -- 情绪调节
  
  -- 数据支撑
  total_trades INTEGER,               -- 本月交易总数
  rule_violation_rate REAL,           -- 规则违反率
  abc_a_ratio REAL,                   -- A 级交易占比
  distortion_events INTEGER,          -- 失真事件总数
  
  -- Agent 的综合评估
  agent_assessment TEXT NOT NULL DEFAULT '',
  
  -- 下月训练优先级
  next_month_priority TEXT NOT NULL DEFAULT '',
  
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**`system_config`** — 系统配置与进化记录

```sql
CREATE TABLE system_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_date TEXT NOT NULL,
  config_type TEXT NOT NULL,
  -- rule_update / prompt_update / playbook_rerank / profile_update
  
  description TEXT NOT NULL DEFAULT '',
  -- 人类可读的变更说明
  
  before_value TEXT NOT NULL DEFAULT '',  -- 变更前（JSON）
  after_value TEXT NOT NULL DEFAULT '',   -- 变更后（JSON）
  
  proposed_by TEXT NOT NULL DEFAULT 'agent',
  -- agent（系统提案）/ user（用户主动修改）
  
  approved_by_user INTEGER NOT NULL DEFAULT 0,
  -- 0=待确认 / 1=已确认 / 2=已拒绝
  
  approved_at TEXT,
  effective_at TEXT,                      -- 实际生效时间
  
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 五、信息流设计

### 5.1 日常信息流（每个交易日）

```
你的自然语言输入
        │
        ▼
Agent 意图识别
   ├─ 盘前输入 ──→ 写入 daily_record（盘前计划字段）
   ├─ 开仓记录 ──→ 写入 trade_record（状态=持仓中）
   │               同步触发规则校验 → 如违反 → 写入 rule_event
   │               同步触发失真识别 → 如识别 → 写入 distortion_log
   ├─ 平仓记录 ──→ 更新 trade_record（补充 exit 信息）
   ├─ 异常事件 ──→ 写入 rule_event
   └─ 盘后复盘 ──→ 写入 daily_review
                   更新 daily_record.distortion_count
```

### 5.2 每周信息流

```
触发条件：每周五收盘后（或手动触发）

Agent 读取：
  过去 5 个交易日的
  ├─ distortion_log（失真事件汇总）
  ├─ trade_record（ABC 质量分布、盈亏）
  ├─ rule_event（违规统计）
  └─ daily_review（情绪标记）

生成：
  ├─ 本周行为模式报告（推送给你，用于复盘对话）
  ├─ 下周训练焦点推荐（写入 agent_memory.weekly_focus）
  └─ 失真档案更新（更新 agent_memory.distortion_profile）
```

### 5.3 月度信息流（系统自净化）

```
触发条件：每月月底（或 30 个交易日后）

Agent 读取：
  ├─ distortion_log（30 天失真全量）
  ├─ system_config（已有规则执行情况）
  ├─ agent_memory（当前用户画像）
  └─ capability_snapshot（上月快照，用于对比）

生成：
  ├─ 新的 capability_snapshot（写入）
  ├─ 系统进化提案（写入 system_config，status=待确认）
  │   内容可能包括：
  │   · 某软规则升级为硬规则（原因：过去 30 天违反 N 次但后果一致）
  │   · 某剧本降权（原因：推送 8 次，0 次真正执行）
  │   · 新增高风险情境（原因：数据显示每次 14:00 后失真率 >60%）
  │   · System Prompt 调整建议（针对你个人的表达习惯）
  └─ 需要你确认 → 你拍板 → approved_at 写入 → 生效
```

---

## 六、Agent 内核设计

### 6.1 System Prompt 的三层结构

```
┌──────────────────────────────────────────────────┐
│ 静态层（版本化，手动更新）                          │
│ · 你是谁：全职交易员，港股恒指 + 美股期权            │
│ · 核心原则：执行优先于预测，纪律优先于机会            │
│ · 交互风格：简洁、中文、不说废话                     │
└──────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────┐
│ 规则层（从 trading-system 提取，版本化）             │
│ · 硬规则（全量载入，不可违反）                       │
│   - 无止损不开仓                                    │
│   - 单日回撤超 X% 强制停手                          │
│   - ...                                            │
│ · 软规则（重点摘要，黄色提醒）                       │
│ · ABC 评级标准（完整载入）                           │
│ · 风控触发条件（完整载入）                           │
└──────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────┐
│ 动态层（每次对话前注入，从数据库实时读取）            │
│ · agent_memory（用户当前画像、本周训练焦点）          │
│ · 今日 daily_record 摘要（盘前计划是什么）            │
│ · 最近 3 次失真事件（上下文延续）                    │
│ · 当前能力阶段（决定反馈力度和路由方向）              │
└──────────────────────────────────────────────────┘
```

### 6.2 Agent 的工具集（Tool Use）

Agent 需要具备以下工具函数：

```
数据写入工具：
  write_daily_record()        盘前计划写入/更新
  write_trade_record()        开仓记录写入
  update_trade_exit()         平仓信息更新
  write_rule_event()          纪律事件记录
  write_daily_review()        复盘写入
  write_distortion_log()      失真事件记录

数据读取工具：
  get_today_summary()         今日当前状态
  get_open_positions()        当前持仓
  get_weekly_stats()          本周统计数据
  get_distortion_history()    失真历史（指定类型/时间范围）

知识库调取工具：
  get_playbook(distortion_type)        调取对应剧本核心内容
  get_capability_pack(focus)           调取当前训练焦点内容
  get_rule_detail(rule_id)             调取规则原文

系统工具：
  propose_system_change()     生成系统进化提案（待人确认）
  generate_weekly_report()    生成周度分析
  generate_capability_snapshot()  生成月度能力快照
```

---

## 七、展示层职责重划

前端从"数据录入工具"转型为"结果阅读面板"，页面职责如下：

| 页面 | 新职责 | 是否保留编辑入口 |
|---|---|---|
| 盘前准备 | 展示今日 Agent 已生成的盘前计划摘要 | 仅补充不超过 3 个字段 |
| 参考信息 | 恒指参数、观察标的（只读） | 否 |
| 盘中执行 | 实时交易流水、当前持仓、盈亏、失真事件时间线 | 否 |
| 盘后复盘 | 今日复盘内容展示（Agent 生成后在这里核对） | 可补充修改 |
| 进化看板（新增） | 失真趋势图、能力雷达图、本周焦点、待确认系统提案 | 仅确认/拒绝提案 |
| 历史复查 | 交易流水、规则事件、复盘归档（纯只读） | 否 |

---

## 八、三系统统一的边界规则

为防止建设过程中三个系统重新分裂，以下边界规则需固化：

1. **数据写入只有一个入口**：任何交易数据，只通过 Agent 写入 SQLite。前端不再有主动写入表单（只有极少数确认类操作例外）。

2. **规则只有一个来源**：`trading-system` 是规则原文的唯一来源。如需修改某条规则，改 trading-system 文档，再同步到 Agent System Prompt，前端展示的是最新版本。

3. **知识库只被调用，不被平铺**：`toptrader-research` 的内容不会全量展示给你，只由 Agent 按情境按需推送。你看到的永远是"当下最需要的那一个剧本/那一段能力描述"。

4. **系统配置变更必须经过你的拍板**：Agent 可以提案，但 `system_config` 表中任何 `proposed_by='agent'` 的条目，必须你确认后才能 `effective_at` 生效。系统不能自己修改自己的规则。

5. **展示层不驱动业务逻辑**：仪表盘只是 SQL 查询的可视化。如果某个数字看起来不对，去 Agent 里说，Agent 修正数据，仪表盘自动更新。不能在前端直接改数字。

---

## 九、共同进化的判断标准

系统是否真正在"进化"，不看功能多少，看这三个指标：

1. **Agent 对你的描述越来越少问追问题**：刚开始你说"开了一单"，Agent 要问 10 个字段；6 个月后，同样一句话，Agent 只需要确认 2 个，其余自动推断准确率 >90%。

2. **推送的剧本命中率提高**：第 1 个月推 5 个剧本，你觉得 2 个有用。第 6 个月推 2 个，你觉得 2 个都对。

3. **系统提案越来越精准**：第一次 meta-review 提案 8 条，你拒绝了 5 条。第三次提案 5 条，你拒绝了 1 条。

这三个趋势，就是"AI 在进化"最真实的证明。

---

## 十、当前优先建设顺序

基于"顶层设计先于落地"的原则，当前阶段的任务是：

```
Phase 0（当前）：顶层设计锁定
  ├─ 本文档确认
  ├─ 数据库 Schema 最终版确认（新增 4 张表）
  └─ Agent System Prompt 三层结构草稿确认

Phase 1：数据打通
  ├─ 新增 4 张表落库（distortion_log / agent_memory /
  │   capability_snapshot / system_config）
  ├─ 工具函数层（Tool Use）开发
  └─ Agent 能跑通：开仓描述 → 写入 trade_record + 触发校验

Phase 2：每日回路闭合
  ├─ 完整盘前→开仓→平仓→复盘链路
  ├─ 失真识别 + distortion_log 写入
  └─ 仪表盘接入新数据字段展示

Phase 3：分析层 + 系统自净化
  ├─ 周度分析报告生成
  ├─ 月度 capability_snapshot + system_config 提案
  └─ 进化看板上线
```

---

*v1.0 — 顶层框架版，数据 Schema 待最终确认后锁定*
