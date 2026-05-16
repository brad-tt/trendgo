# TrendGo App

这是 TrendGo 当前主产品容器，包含 FastAPI 后端、SQLite 数据库、React 前端、Agent CLI 和回归脚本。

## 当前实现

- 后端入口：`api_server.py`
- 旧页面和 Markdown 双写逻辑：`local_web.py`
- 数据访问层：`database/dal.py`
- 数据库：`database/toptrader.db`
- 前端源码：`frontend/src`
- 前端构建产物：`frontend/dist`
- 交易日记录归档：`05-daily-ops/records`
- 归档草稿：`05-daily-ops/closeouts`
- 总结与审计产物：`05-daily-ops/summaries`

## 启动

默认后端端口是 `8526`：

```bash
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

或：

```bash
python3 start.py
```

端口冲突时：

```bash
TOPTRADER_PORT=8527 python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8527
```

`local_web.py` 是旧本地页面，默认端口 `8522`，不是当前 Agent 主入口。

## 前端开发

```bash
cd frontend
npm install
npm run dev
```

Vite 默认把 `/api` 代理到 `http://127.0.0.1:8526`。

如果后端不是 `8526`：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8527 npm run dev
```

构建：

```bash
cd frontend
npm run build
```

## Agent 接口

当前主路径：

- `GET /api/agent/contract`
- `POST /api/agent/commit`

`/api/agent/commit` 接收：

- `intent`：`open_trade` / `close_trade` / `rule_event` / `review`
- `market`
- `tradeDate`，可选
- `fields`
- `rawNote`
- `agentNote`，可选

响应统一包含：

- `committed`
- `message`
- `missingFields`
- `missingLabels`
- `day`
- `autoEventId`，如有

兼容接口仍保留：

- `/api/agent/intake/*`
- `/api/agent/workflow/intake`
- `/api/agent/session`

这些 legacy 接口可以用于旧脚本或回归，不是新 Skill 的主路径。

## Agent CLI

结构化写入：

```bash
python3 scripts/openclaw_client.py \
  --intent open_trade \
  --market HK \
  --note "用户原始口述" \
  --payload-json '{"fields":{}}'
```

CLI 会先检查 `/api/agent/contract`。后端不是当前版本时，会给出明确错误，不再默默打到旧服务。

旧自然语言 fallback：

```bash
python3 scripts/openclaw_client.py --market HK --note "用户原始口述"
```

这个模式只用于兼容，不作为 Agent 默认路径。

## 写入行为

- 开仓、纪律事件、复盘：目标工作台不存在时，后端会自动创建。
- 平仓：不会自动创建空工作台；没有可平仓交易时返回可理解错误或缺 `tradeId`。
- 不传日期时：
  - 开仓默认今天。
  - 平仓默认当前市场最近有未平仓交易的工作台。
  - 复盘和纪律事件默认当前市场最近工作台。
- 盈亏统一按 `(exitPrice - entryPrice) * positionSize` 计算。

## 回归

后端和 Agent：

```bash
python3 -m py_compile api_server.py local_web.py db_init.py database/dal.py core/*.py scripts/*.py
python3 scripts/replay_agent_commit_sandbox.py
python3 scripts/replay_agent_open_write_sandbox.py
python3 scripts/replay_agent_close_write_sandbox.py
python3 scripts/replay_agent_rule_event_write_sandbox.py
python3 scripts/replay_agent_review_write_sandbox.py
```

兼容链路需要时再跑：

```bash
python3 scripts/replay_agent_context_api.py
python3 scripts/replay_agent_workflow_intake_api.py
python3 scripts/replay_agent_trade_lifecycle_samples.py
python3 scripts/replay_agent_nl_open_intake_sandbox.py
python3 scripts/replay_agent_nl_close_intake_sandbox.py
python3 scripts/replay_agent_nl_rule_event_intake_sandbox.py
python3 scripts/replay_agent_nl_review_intake_sandbox.py
```

前端：

```bash
cd frontend
npm run build
```

## 文档

- `../TOPTRADER_SKILL_USAGE.md`：Skill 使用说明。
- `AI_HANDOFF.md`：当前开发交接。
- `WORKFLOW_GUIDE.md`：页面工作流说明。
- `frontend/README.md`：前端说明。
