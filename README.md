# TrendGo

TrendGo 是一个本地优先的交易记录、执行纪律和复盘工作台。当前主线是 Agent 原生解析：用户用自然语言描述交易，Agent/Skill 负责理解和补齐结构化字段，后端只做校验、计算、写入和展示。

## 当前权威文档

- `README.md`：项目入口和文档地图。
- `TOPTRADER_SKILL_USAGE.md`：TrendGo Skill 的实际使用说明。
- `app/README.md`：后端、前端、脚本和接口开发说明。
- `app/AI_HANDOFF.md`：给下一位开发者或 Agent 的当前实现交接。
- `BOUNDARIES.md`：数据、Agent、前端、规则和知识边界。
- `PROGRESS.md`：当前完成度和推荐下一步。
- `skills/trendgo.md`：仓库内 Skill 源文件。
- `~/.agents/skills/trendgo/SKILL.md`：可选的本机已安装 Skill。

历史 bug 台账和一次性测试准备文档已经删除。后续判断当前结构时，以以上文档和代码为准。

## 产品结构

```text
用户自然语言
  -> Agent / Skill 解析意图与字段
  -> 缺字段时追问用户
  -> 字段齐全后调用结构化 CLI
  -> POST /api/agent/commit
  -> 后端校验、计算、自动建工作台、写 SQLite 和记录文件
  -> 前端展示与纠错
```

核心原则：

- Agent 是自然语言理解层。
- 后端不是 NLP 服务，不再负责从口述中猜字段。
- 后端仍保留必要校验，防止脏数据和错误状态。
- 只有返回 `committed=true` 或 CLI 显示 `已写入: 是`，才算完成记录。

## 运行方式

后端默认端口是 `8526`：

```bash
cd app
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

也可以用启动脚本：

```bash
cd app
python3 start.py
```

如果端口冲突：

```bash
cd app
TOPTRADER_PORT=8527 python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8527
```

前端开发模式：

```bash
cd app/frontend
npm install
npm run dev
```

默认前端代理到 `http://127.0.0.1:8526`。如果后端换端口：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8527 npm run dev
```

访问：

- 后端静态入口：`http://127.0.0.1:8526/premarket`
- Vite 开发入口：以终端输出为准，通常是 `http://127.0.0.1:5173/premarket`

## Agent 主接口

当前主路径：

- `GET /api/agent/contract`：确认当前后端是否支持结构化 Agent commit。
- `POST /api/agent/commit`：结构化写入开仓、平仓、纪律事件、复盘。

`/api/agent/intake/*`、`/api/agent/workflow/intake` 和 `/api/agent/session` 仍作为 legacy compatibility 保留，不是 Skill 主路径。

## CLI 主路径

结构化提交：

```bash
cd app
python3 scripts/openclaw_client.py \
  --intent open_trade \
  --market HK \
  --note "54927牛证，14点入场价0.054，买3手，止损0.044，A级机会。" \
  --payload-json '{"fields":{"tradeTime":"14:00","sessionWindow":"mid_session","direction":"long","certificateSide":"bull","instrumentCode":"54927","setupType":"opening_breakout","abcGrade":"A","entryPrice":0.054,"stopLoss":0.044,"positionSize":"3","entryReason":"A级机会","instrumentType":"bull_bear_certificate","underlying":"HSI"}}'
```

旧 `--note` 自然语言模式只作为兼容 fallback，不作为新 Skill 的默认路径。

## 数据与目录

- `app/database/toptrader.db`：SQLite 主数据源。
- `app/05-daily-ops/records/`：Markdown 交易日归档和兼容副本。
- `app/frontend/src/`：React 前端源码。
- `trading-system/`：交易规则与执行知识源。
- `toptrader-research/`：训练剧本、能力包和知识路由源。
- `docs/`：产品愿景和系统整合参考。

每日记录文件属于数据归档，不是待清理文档。

## 推荐校验

后端和 Agent：

```bash
cd app
python3 -m py_compile api_server.py local_web.py db_init.py database/dal.py core/*.py scripts/*.py
python3 scripts/replay_agent_commit_sandbox.py
python3 scripts/replay_agent_open_write_sandbox.py
python3 scripts/replay_agent_close_write_sandbox.py
python3 scripts/replay_agent_rule_event_write_sandbox.py
python3 scripts/replay_agent_review_write_sandbox.py
```

前端：

```bash
cd app/frontend
npm install
npm run build
```

规则索引或知识路由改动后：

```bash
cd app
python3 scripts/validate_agent_indexes.py
```
